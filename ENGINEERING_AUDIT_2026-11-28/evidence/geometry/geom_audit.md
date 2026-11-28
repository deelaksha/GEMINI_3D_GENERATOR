# Geometry, joints and validation audit: GEMINI_3D_GENERATOR board engine

Scope: `board_engine/` working tree, including the uncommitted `expand.py`, `canvas.py` and `shapes.py` edits. No project file was modified.
SCR = `/tmp/claude-1002/-home-sonic-claude2-mythra/9b0b6ca6-d98e-48cf-ab1a-7d0386cce3f4/scratchpad/geom_audit`
Run any case from the project root:
`PYTHONDONTWRITEBYTECODE=1 SCR/../venv/bin/python SCR/run.py [-j] SCR/cases/<case>.json` (`-j` also dumps joints and components)
Helper scripts: `SCR/gen.py` builds every case. `SCR/mc_overlap.py` measures overlap volume by Monte Carlo as an independent ground truth. `SCR/verify_transform.py` compares world corners from the placement with `_tilt_points`. `SCR/kerf_check.py` checks the kerf offsets. `SCR/asm2.py` runs the assembly planner. `SCR/native_joined.py` checks native-format joints.

## How the engine works (verified)

- **Coordinates and transforms.** Each v1 board is an axis-aligned box. `_component` (canvas.py:764) builds a centred local 2D outline with a placement (centre plus Euler XYZ in degrees). `rotate` steps are applied afterwards by `_apply_rotate` (canvas.py:753): each step turns about its own pivot (default: the current centre) and the result goes back through `_euler_xyz` (canvas.py:724). The renderer, validation, nesting and cut paths all read the same `placement` through `G.Frame`. Profiles, openings, engravings and `edge` all describe the board **before** rotation, as docs/board-design-format.md:136 says.
- **Collision.** The broad phase is AABB (`G.near_pairs`, `_aabb_overlap`). The narrow phase is solid-against-solid:
  - Non-parallel plates (`_plate_interference`, validation.py:1195): exact 1D interval sampling along the line where the two mid-planes meet, with stations every 0.5 mm, three offsets across the thickness, and the outline and holes intersected exactly.
  - Parallel plates (`_projected_overlap`, validation.py:1066): a point grid of at most 6000 samples (`_grid`, validation.py:1050).
  - So collision is **not** AABB-based. Connectivity "touch" **is** AABB-based (connectivity.py:79).
- **Frontend.** `js/studio/viewport3d.js` (lines 2-4, 52, 310-319) extrudes the backend's `cut_outline` and `features[].polygon` and applies `matrix_world` from `views.model3d` (views.py:43-56). The live preview `_preview` (canvas.py:1766) sends the same outlines and matrices. `js/studio/sheet2d.js` draws the `/layout2d` cut paths, which are kerf-offset in production. Nothing is recomputed on the client, so 3D, 2D and validation share one geometry. The legacy `js/assembly/engine3d.js:180` uses `group.rotation.set` with its own part data. It is outside this pipeline and was not audited.

## Findings

### G-01: Tilted boards at a shallow angle can sink into another board without a COLLISION error (missed collision)
- **Severity:** High. **Classification:** Confirmed bug.
- **Where:** validation.py `_plate_interference`, lines 1212-1220 (`pad = 2.0*max(a.t,b.t)+1.0`, then `if not rr: return []`).
- **What happens now:** Before sampling, the function requires the line where the two mid-planes intersect to pass within `pad` (13 mm for 6 mm board) of both boards' 2D bounding boxes. When two boards meet at a small angle θ, that line lies about `(t_a+t_b)/(2·sin θ)` away from where the faces actually overlap, so the pair returns `[]` and no collision is reported.
- **Expected:** A COLLISION error whenever the solids share volume (beyond the contact tolerance).
- **Reproduction:** `SCR/cases/C6_tilted_thin_sliver.json` (1° tilt, 1 mm penetration), `C6b_shallow_tilt_3mm_penetration.json` (2°, 3 mm) and `C6c_tilt_10deg_3mm_penetration.json` (10°, 3 mm). The control case `C6d` (30°) is detected.
- **Actual output:**
  - C6b and C6c: `[error] NOT_JOINED ...` and no COLLISION.
  - C6: `[warning] NEAR_MISS_GAP: 'A' is 0.74 mm from 'B'`. This is wrong: the boards interpenetrate, they are not apart.
  - `mc_overlap.py` measures real overlap volumes of C6 = 2264 mm³, C6b = 12267 mm³ and C6c = 2383 mm³.
- **Impact:** A roof panel, sloped back or lectern sunk a few mm into a base passes collision checking whenever no connection is declared between the two boards. The parts cannot be assembled, yet the design reaches the cut files if nothing else fails.
- **Fix:** Make the pad depend on the angle, `pad = (a.t+b.t)/(2*max(sinθ, 1e-3)) + 1`, capped at the plate diagonal. Alternatively, derive the station range from the two face-plane intersection lines instead of the mid-plane line.
- **Regression risk:** Low to medium. More stations means more CPU on nearly parallel pairs, and seated tabs and touching faces must still pass through the `tol['contact']` shrink.
- **Acceptance test:** C6, C6b and C6c report COLLISION. C1, C4a, C4b and T01 still report none. The cottage example stays ok=True.

### G-02: Overlaps between large parallel boards are missed when narrower than about 20 mm (coarse sampling)
- **Severity:** High for furniture-scale designs. **Classification:** Confirmed bug.
- **Where:** validation.py `_grid` (line 1050, `max_points=6000`) as used by `_projected_overlap` (line 1066). The step comes from **a's full bbox** even when only a small window is sampled.
- **What happens now:** For a 2400×1200 board the step is √(2400·1200/6000) ≈ 21.9 mm, so a strip narrower than one grid step falls between samples. The area that is reported is also quantised: the 15 mm and 25 mm strips both report `52800.0 mm²`.
- **Reproduction:** `SCR/cases/C8_large_parallel_strip_{5,10,15,25}mm.json`. These are 18 mm boards with 9 mm interpenetration and a z overlap of w mm.
- **Actual output:**
  - 5 mm and 10 mm strips: no COLLISION, only NOT_JOINED. The real overlap for 10 mm is 214,358 mm³ (`mc_overlap.py`).
  - 15 mm and 25 mm strips: COLLISION, both with the same quantised area of 52800 mm².
- **Impact:** Boards stacked or doubled face to face with a slight overlap, a common AI placement slip, are accepted.
- **Fix:** Compute the overlap exactly, as a polygon intersection of a.cut minus holes with b.cut minus holes projected into a's plane. shapely is already a dependency through consolidate.py. The minimum fix is to compute `step` from the window area, not the whole plate.
- **Regression risk:** Low.
- **Acceptance test:** Every C8 case reports COLLISION with an area within 5 % of w × 2400 mm².

### G-03: Consolidation merges overlapping coplanar boards, which hides COLLISION and DUPLICATE_COMPONENT
- **Severity:** Medium. **Classification:** Confirmed bug (validation masking).
- **Where:** consolidate.py `_touch`, lines 85-89 (docstring: "share an edge ... **or overlap**"). It is called from `plan`, line 305. Consolidation is on by default.
- **What happens now:** Two coplanar boards that overlap, or are exact duplicates, are united into one panel before validation runs. The only report is `[info] CONSOLIDATED`, and the compile returns ok=True. This contradicts the module docstring, which says boards are merged when "joined edge to edge".
- **Reproduction:**
  - `K1_coplanar_overlap_consolidated.json` gives ok=True with only `CONSOLIDATED`.
  - The same geometry with `"consolidate": false` (`K2`) gives `[error] COLLISION ... (3922.0 mm²)`.
  - `J16_two_walls_same_place_same_side.json` (an exact duplicate) gives ok=True. With consolidation off (`K3`) it gives `DUPLICATE_COMPONENT`, `COLLISION` and `SLOT_ALREADY_USED`.
- **Impact:** A double-placed board, typical when an AI emits the same part twice, silently disappears. The real modelling error never reaches the author.
- **Fix:** In `_touch`, require the overlap area to be at most EPS² (edge sharing only). Groups whose members overlap should be left unmerged so that validation reports them, or should be merged with a warning `OVERLAPPING_PIECES_MERGED`.
- **Regression risk:** Low. Designs that rely on overlapping slats being merged would start reporting COLLISION, which is correct.
- **Acceptance test:** K1 and J16 give ok=False with COLLISION or DUPLICATE_COMPONENT. Edge-touching fence and lattice pieces still merge.

### G-04: Connectivity uses bounding boxes, so it claims boards touch when they do not
- **Severity:** Medium. **Classification:** Confirmed bug (wrong classification and wrong fix advice).
- **Where:** connectivity.py `analyze`, lines 76-81 (`touches` comes from `world_aabb` with `TOUCH=0.5`).
- **What happens now:** Boards whose boxes intersect are treated as touching. The engine then reports `NOT_JOINED ... although it touches it` and suggests adding a connection, instead of reporting `ISOLATED_BOARD` or `DISCONNECTED` with a move.
- **Reproduction:**
  - `C2_board_in_L_notch.json`: a post inside an L-shaped board's notch, no material contact.
  - `C4a_discs_coplanar_corner_boxes.json`: discs 127 mm apart between centres, which is 27 mm of air.
  - `C4b_disc_perp_corner.json` and `C1_rotated_parallel_aabb_overlap_no_solid.json`: 19.8 mm apart.
  - `mc_overlap.py` confirms 0 mm³ of contact in each case.
- **Actual output:** `[error] NOT_JOINED: Board 'D2' is not joined to the main assembly although it touches it ('D2' / 'D1')`.
- **Impact:** The severity stays error, so nothing is hidden. The message and the offered fix are wrong, though, and an autofix loop or an AI may add an impossible connection. NOT_JOINED is downgraded to a warning when support marks the group "resting". Whether that downgrade can be reached for a floating board whose box merely overlaps another was not reproduced (Potential).
- **Fix:** After the AABB broad phase, confirm contact with an exact distance: `plate_interference` with a negative tolerance, or a polygon-to-polygon 3D distance below TOUCH.
- **Regression risk:** Low.
- **Acceptance test:** C4a reports DISCONNECTED or ISOLATED_BOARD with a gap of about 27 mm. C2 reports ISOLATED_BOARD. N3 still reports NOT_JOINED.

### G-05: Nothing checks whether a model is visually complete (missing roof, open enclosure)
- **Severity:** Medium. **Classification:** Confirmed missing capability.
- **Where:** There is no such check in validation.py, inspection.py, structure.py or support.py. A search for enclosure, completeness or "roof" logic finds only prompt text.
- **What happens now:**
  - The cottage example with ROOF-R removed (`V1_cottage_no_roof_R_nooverall.json`) gives ok=True.
  - With both roofs and one wall removed (`V2_..._nooverall.json`) it is still ok=True.
  - The desk organiser with no FRONT wall (`V3_organiser_no_front.json`) gives ok=True with info messages only.
  - When `product.overall` is present, V1 and V2 fail only by accident, through `OVERALL_MISMATCH` (canvas.py:2183-2190).
- **Impact:** The validator checks structural and manufacturing validity only. It cannot tell a finished product from a half-built one, so an AI generator can drop panels and still get ok=True.
- **Proposed fix:**
  1. An optional `product.enclosure` / `"closed": true` intent, checked by ray casting from the interior centroid along ±x, ±y and ±z and along diagonals, reporting `OPEN_ENCLOSURE` with the open direction.
  2. A symmetry check: mirror-pair detection already exists (`MISMATCHED_PAIR`), so a lone tilted panel with no mirror partner could raise `MISSING_COUNTERPART`.
  3. Always reporting a missing overall-size match as a warning.
- **Regression risk:** Low if opt-in.
- **Acceptance test:** V1 without overall gives `OPEN_ENCLOSURE` or `MISSING_COUNTERPART` (warning or error).

### G-06: The compile result drops the assembly plan, and assembly errors do not set `ok`
- **Severity:** Low to medium.
- **Classification:** Confirmed bug (key mismatch). Potential issue (`ok` while locked).
- **Where:** canvas.py `_tail`, line 2318 (`{k: mfg[k] for k in ('summary','assembly') if k in mfg}`). `manufacturing_report` returns the plan as `'assembly_plan'` (manufacturing.py:1058).
- **What happens now:** `result['manufacturing']` contains only `['summary']`, so the sequence is never returned (`asm2.py` on A1, A3 and A4).
- **The planner itself works.** manufacturing.py:722 `plan_assembly` runs assembly-by-disassembly on a blocking graph with sub-assemblies. It found valid orders for:
  - A1, a closed 6-panel box joined by tabs and fingers: `base LFT; FRT, BCK, RGT along -x; BOT along +y; TOP along -y`.
  - A3, a 6-sided finger box.
  - A4, a shelf captured between two uprights.
- **ASSEMBLY_LOCKED path:** Its errors go into `layout.blocking_issues` (views.py:96-102) but never into `diagnostics`. `ok` counts diagnostics only (canvas.py:2338), so a locked design could return ok=True with ready_for_production=False. I could not construct a locked design, so this part is Potential.
- **Fix:** Use the `'assembly_plan'` key. Promote `ASSEMBLY_LOCKED` into the diagnostics when `run_production=True`.
- **Acceptance test:** A1 with `run_production=True` has `result['manufacturing']['assembly_plan'][0]['steps']`.

### G-07: A tab_slot is accepted when most of the joining edge hangs off the receiving board's profile
- **Severity:** Low to medium. **Classification:** Potential issue / Enhancement.
- **Where:** canvas.py `_tabs_for`, lines 1178-1179, clamps tab positions to the receiver's **box** (`bd_b.lo/hi`), not its profile. Only individual tabs are then checked (`TAB_OUTSIDE_RECEIVER`, validation.py:494).
- **Reproduction:** `J07c_wall_edge_partly_off_disc_1tab.json`. A 180 mm wall sits on a Ø200 disc, near the rim, where only about 120 mm of the wall's edge is over material. Result: ok=True with no warning. With `tabs: 3` (`J07d`), the two outer tabs are correctly rejected.
- **Impact:** A wall visibly overhangs into air past a round or concave base, and whether it is accepted depends on the tab count.
- **Fix:** Measure the contact length against the receiver outline (as `_contact_tilted` already does with `_edge_line_intervals`), place tabs only inside it, and warn `EDGE_PARTIALLY_SUPPORTED` when it is below about 80 % of the edge. The butt path already does this.
- **Acceptance test:** J07c warns, and its tabs stay within the part of the edge that is over material.

### G-08: Slot-to-slot spacing threshold is inconsistent with the engine's own advice
- **Severity:** Low. **Classification:** Enhancement / inconsistency.
- **Where:** validation.py:44 sets `min_feature_spacing = 1.0` mm. The hint text in canvas.py `_slot_neighbour` and `_ATTACH_HINT` says slots need at least 2×t, and the hints elsewhere say at least 20 mm.
- **Reproduction:** `J18_tabs_close_together.json`. Two walls 3 mm apart leave a 2.9 mm web between their slots in 6 mm ply. Result: ok=True with only `[warning] WEAK_SECTION ... 2.9 mm`.
- **Fix:** Use one constant, `max(1.0, t)`, for slot-to-slot spacing. Either make WEAK_SECTION between two slots an error, or document it as a warning.

### G-09: Duplicate and repeated connections are handled inconsistently
- **Severity:** Low. **Classification:** Confirmed bug (minor).
- **Duplicate ids:** The tab_slot pass reports `DUPLICATE_CONNECTION_ID` (`J12`). Finger and cross_lap connections skip the `seen` check (pass 1, canvas.py:2022-2024) and surface later as `JOINT_ID_EXISTS` from the join engine (`J12b`). Both cases are rejected; only the code differs.
- **Same pair, two types:** Deduplication keys on (pair, type) (canvas.py:1425), so a tab_slot plus a butt on the same edge are both joined with no warning (`J15_same_pair_two_types.json`, ok=True).
- **Fix:** Check ids once in `_resolve_connections`. Warn when one pair carries more than one joint on the same edge.

### G-10: A broken "joined" joint in a native design keeps status `joined` in the output
- **Severity:** Low. **Classification:** Confirmed (minor).
- **Where:** `_compile_native` (canvas.py:1821) keeps joints whose input status is `joined`. `validate_design` re-evaluates them and reports `JOINT_BROKEN`, which is correct, so a "joined" record **is** checked against real geometry. The returned joint still says `joined`, however, and connectivity (connectivity.py:66-68) unions the boards. A board moved 300 mm away (`N_native_joined_far.json`, built by `native_joined.py`) produces no ISOLATED_BOARD. ok is still False.
- **Fix:** Set the status to `broken` or `detached` when `JOINT_BROKEN` fires, before connectivity runs.

### G-11: The docs allow up to 3 compound rotate steps but the code accepts 4
- **Severity:** Info. **Classification:** Documentation inconsistency.
- **Where:** docs/board-design-format.md:140 says "a LIST of 1-3 such steps". canvas.py:479 accepts `1 <= len(rot) <= 4`.

### G-12: No dog-bone or T-bone relief for router-cut slots
- **Severity:** Medium for CNC routers, none for lasers. **Classification:** Confirmed missing capability (code search).
- **Evidence:**
  - The plywood catalogue kerf is 3.2 mm (manufacturing.py:43). T01 produces a 6.1 × 44.1 slot whose tool path is 2.9 × 40.9, which is the correct kerf offset.
  - A search for dogbone, t-bone or tool radius in `board_engine/` finds nothing.
  - A 3.2 mm bit leaves r = 1.6 mm in every inside corner of a slot and of a finger or cross-lap notch, so a square tab does not seat.
- **Fix:** When the kerf is at least 1 mm (router), add corner relief to inner slot paths and to inside corners of the outer profile.
- **Acceptance test:** A T01 production run on a router has slot paths with relief lobes of radius kerf/2.

## Checked and correct (no finding)

- **Euler, pivots and compound rotation:** `verify_transform.py` on T02 gives a world-corner error of at most 5.2e-5 mm across a single tilt, a pivot tilt, x-then-z, z-then-x (order respected) and a 3-step tilt, including the gimbal case ry = 90° (R2: `[90,90,0]`). det(R) = 1 everywhere.
- **Winding and orientation:**
  - Clockwise or mirrored profiles are reversed to CCW (canvas.py:783-786, model.py:297; T05). Feature polygons are normalised in `normalize_feature` (model.py:247).
  - Thickness orientation comes from the size that equals the thickness. When ambiguous, `normal` resolves it or `AMBIGUOUS_ORIENTATION` is raised.
- **Invalid shapes:** Self-intersecting profiles (T04, `OUTLINE_SELF_INTERSECTION`) and openings (T11, `FEATURE_SELF_INTERSECTION`) are rejected. A profile outside its box is rejected (T06). An opening crossing or touching the edge, or sitting in a concave notch, raises `FEATURE_OUTSIDE_OUTLINE` (T07, T08, T09). An off-plane opening raises `OPENING_OFF_BOARD` (T10).
- **Collision:** No false positives where only the boxes overlap (C1, C2, C4a, C4b). True intersections are detected (C1b, C3, C4c, C5, C6d, C7, K2, E1 spokes).
- **Joints:**
  - finger, cross_lap, butt, hinge, mitre and tilted tab_slot (cottage roof) are all joined.
  - Tilted with a non-parallel edge: `NO_CONTACT` (J17).
  - Duplicate slot from opposite sides: `SLOT_ALREADY_USED` plus COLLISION (J06).
  - Partial or notch receiver: `TAB_OUTSIDE_RECEIVER` (J07b, J07d, J07e).
  - Tab on an opening: `TAB_IN_OPENING` (J08).
  - Slot too close to the edge: `SLOT_AT_EDGE` (J09).
  - Unknown board: `UNKNOWN_BOARD` (J10). Duplicate board id: `DUPLICATE_BOARD_ID` (J11). Self connection: `SELF_CONNECTION` (J13).
  - 5 mm gap: `CONNECTION_GAP` plus `UNATTACHED_BOARD` (J14).
- **Fit and kerf:**
  - Slot width = t + clearance (6.1), and slot length = tab width + clearance (44.1 for a 44 tab).
  - Kerf is applied only in cut paths (cutpaths.py:171-233): outer paths +kerf/2 outward (203.2 mm for a 200 mm board), inner paths −kerf/2 inward (40.9 × 2.9). The direction is correct because outlines and features are normalised to CCW, and a `DIMENSION_DRIFT` self-check exists.
- **Connectivity codes:** `ISOLATED_BOARD` (N1), `DISCONNECTED` (N2), `NOT_JOINED` (N3) and `UNATTACHED_BOARD` (N4) all fire as documented.
- **Frontend:** Uses the API outlines and `matrix_world`; nothing is recomputed.

## Test cases run

| Case | Expected | Actual | Pass |
|---|---|---|---|
| T01 baseline tab_slot | ok | ok=True | ✔ |
| T02 rotations (6 tilt variants) | corners consistent | err ≤5e-5 mm | ✔ |
| T03 concave L profile | ok | ok=True | ✔ |
| T04 bow-tie profile | reject | OUTLINE_SELF_INTERSECTION | ✔ |
| T05 CW profile | normalised | area +30000, notch correct | ✔ |
| T06 profile outside box | reject | PROFILE_INVALID | ✔ |
| T07 opening crosses edge | reject | FEATURE_OUTSIDE_OUTLINE | ✔ |
| T08 opening touches edge | reject | FEATURE_OUTSIDE_OUTLINE | ✔ |
| T09 opening in L notch | reject | FEATURE_OUTSIDE_OUTLINE | ✔ |
| T10 opening off plane | reject | OPENING_OFF_BOARD | ✔ |
| T11 self-intersecting opening | reject | FEATURE_SELF_INTERSECTION | ✔ |
| T12 opening on tilted board | ok (pre-rotation coordinates) | ok=True | ✔ |
| C1 parallel tilted, boxes overlap, 19.8 mm apart | no COLLISION | none (but NOT_JOINED, G-04) | ✔/✘ |
| C1b coplanar tilted overlap | COLLISION | COLLISION 18150 mm² | ✔ |
| C2 post in L notch | no COLLISION, isolated | no COLLISION, NOT_JOINED "touches" | ✔/✘ (G-04) |
| C3 tilted X | COLLISION | COLLISION | ✔ |
| C4a discs, corner boxes | no COLLISION | none; NOT_JOINED "touches" | ✔/✘ (G-04) |
| C4b perpendicular disc, corner only | no COLLISION | none | ✔ |
| C4c perpendicular disc, real overlap | COLLISION | COLLISION 30.5 mm | ✔ |
| C5 axis-aligned overlap | COLLISION | COLLISION | ✔ |
| C6 1° tilt, 1 mm penetration | COLLISION | NEAR_MISS_GAP 0.74 mm | ✘ G-01 |
| C6b 2°, 3 mm | COLLISION | none | ✘ G-01 |
| C6c 10°, 3 mm | COLLISION | none | ✘ G-01 |
| C6d 30°, 3 mm | COLLISION | COLLISION | ✔ |
| C7 parallel penetration, small boards | COLLISION | COLLISION | ✔ |
| C8 large parallel 5 / 10 mm strip | COLLISION | none | ✘ G-02 |
| C8 large parallel 15 / 25 mm strip | COLLISION, true area | COLLISION, area quantised | ✔/✘ |
| J01 finger | joined | joined | ✔ |
| J02 cross_lap | joined | joined | ✔ |
| J03 butt | joined | joined | ✔ |
| J04 hinge | joined | joined | ✔ |
| J05 mitre | joined | joined | ✔ |
| J06 duplicate slot, opposite sides | reject | SLOT_ALREADY_USED + COLLISION | ✔ |
| J07c edge mostly off disc, 1 tab | warn | ok=True, silent | ✘ G-07 |
| J07b / J07d / J07e tabs off receiver | reject tabs | TAB_OUTSIDE_RECEIVER | ✔ |
| J08 tab on opening | reject | TAB_IN_OPENING | ✔ |
| J09 slot 1 mm from edge | reject | SLOT_AT_EDGE | ✔ |
| J10 unknown board | reject | UNKNOWN_BOARD | ✔ |
| J11 duplicate board id | reject | DUPLICATE_BOARD_ID | ✔ |
| J12 / J12b duplicate connection id | reject, same code | DUPLICATE_CONNECTION_ID / JOINT_ID_EXISTS | ✔ (G-09) |
| J13 self connection | reject | SELF_CONNECTION | ✔ |
| J14 5 mm gap | reject | CONNECTION_GAP | ✔ |
| J15 tab_slot + butt on same pair | warn | both joined, silent | ✘ G-09 |
| J16 identical duplicate wall | reject | consolidated, ok=True | ✘ G-03 |
| J17 tilted, non-parallel edge | reject | NO_CONTACT | ✔ |
| J18 slots 2.9 mm apart | error | WEAK_SECTION warning only | ~ G-08 |
| K1 coplanar overlap (consolidate on) | COLLISION | ok=True, CONSOLIDATED | ✘ G-03 |
| K2 / K3 same, consolidate off | COLLISION / DUPLICATE | reported | ✔ |
| A1 / A3 / A4 assembly order | plan | planner finds plan; dropped from compile result | ✔/✘ G-06 |
| N1 isolated | ISOLATED_BOARD | ISOLATED_BOARD | ✔ |
| N2 disconnected group | DISCONNECTED | DISCONNECTED | ✔ |
| N3 touching, not joined | NOT_JOINED | NOT_JOINED | ✔ |
| N4 failed connection | UNATTACHED_BOARD | UNATTACHED_BOARD | ✔ |
| N5 tilted board far away | ISOLATED | ISOLATED_BOARD | ✔ |
| native joined, 5 / 300 mm apart | JOINT_BROKEN | JOINT_BROKEN (status stays joined) | ✔/~ G-10 |
| V1 / V2 house missing roof (no overall) | incomplete | ok=True | ✘ G-05 |
| V3 organiser without front | incomplete | ok=True | ✘ G-05 |
| E1 radial spokes meeting at hub | COLLISION | COLLISION + SLOT_ALREADY_USED | ✔ |
| Kerf, T01 production | outer +3.2, slot −3.2 | 203.2 / 40.9 × 2.9 | ✔ |
| COMPLEX / STRUCTURES / my_home examples | ok | ok=True | ✔ |
