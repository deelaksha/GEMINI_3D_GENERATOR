# Board Design Platform — Engine, API & AI Integration

This document covers the board-design platform added alongside the legacy JS workbench:
the authoritative Python geometry engine (`board_engine/`), the REST API (`board_api/`, served at
`/api/v1`), the Board Studio UI (`/`), production output, and how an AI agent drives it.

```
Board Studio (studio.html, js/studio/*)        AI agent (any HTTP client / LLM tool use)
              \                                     /
               \  cookie + X-Board-Client      Bearer API key
                v                                 v
             board_api  (auth, roles, rate limit, envelope, revisions)
                               |
             board_engine.operations   <-- the ONLY way state changes
                 |            |               |
          validation      joining        nesting / cutpaths / booklet
                 \            |               /
                  model + geometry (mm, +Y up, Euler XYZ)
                               |
                 store (instance/designs/*.json + history log)
```

The legacy JS workbench (`/assembly`, inspector, manufacturing, validation pages) is unchanged
apart from bug fixes; it keeps working on the JS models in `js/models/`.

## 1. Running

```bash
pip install -r requirements.txt
python start_server.py --port 5000          # opens http://localhost:5000/ (Board Studio)
python -m pytest tests/python -q            # engine, API and end-to-end tests
node tests/joint_fit_suite.mjs              # legacy JS validator suite
```

On first start the server seeds the example boat (built through the join pipeline) and, if no
keys are configured, generates an editor API key in `instance/api_keys.json` (printed to the log).

**Saving designs permanently (Firebase):** set `FIREBASE_SERVICE_ACCOUNT` to the JSON of a Firebase
service-account key (plain JSON or base64). Designs are then stored in Firestore collection
`board_designs` (history in a `history` sub-collection) and survive restarts and redeploys. Only the
server writes there — deploy the repo's `firestore.rules`, which deny browser access to
`board_designs` so every change goes through validation. `GET /api/v1/storage` shows the active backend.

**Serverless / read-only hosts (Vercel) without Firebase:** data goes to the system temp dir
(`/tmp/board-instance`) — per instance and lost on cold start. Set these environment variables:

| Variable | Why |
|---|---|
| `BOARD_SECRET` | signs studio session cookies so every instance accepts them (a deployment-derived fallback is used if unset) |
| `BOARD_API_KEYS` | `key:role,...` for AI agents — a generated key would differ per instance and is not retrievable |
| `FIREBASE_SERVICE_ACCOUNT` | Firebase service-account JSON — enables permanent Firestore storage |

## 2. Coordinate system (single convention everywhere)

| Item | Convention |
|---|---|
| Units | millimetres |
| World | right-handed, **+Y up** |
| Component | flat plate drawn in its **local XY plane**; thickness along local Z, centred (z ∈ [-t/2, t/2]) |
| Placement | `position [x,y,z]` + `rotation [rx,ry,rz]` in **degrees**, Euler order **XYZ** (R = Rx·Ry·Rz — identical to `THREE.Euler`) |
| Outline | counter-clockwise; clockwise input is reversed and reported |
| Rendering | the API returns `matrix_world` (column-major 4×4); the studio applies it directly |
| Sheets (2D) | origin top-left, +y down; parts shown from their local +Z face, never mirrored |

## 3. Data model

```jsonc
{
  "id": "boat", "name": "...", "revision": 7,
  "material": {"name": "Birch plywood 3 mm", "thickness": 3, "kerf": 0.15, "clearance": 0.1},
  "sheet": {"width": 600, "height": 400, "spacing": 6},
  "components": [{
    "id": "SIDE-AFT-PORT", "name": "...", "group": "Hull",
    "thickness": 3,                       // optional override (sails use 1.5)
    "grain_locked": false,                // nesting may not rotate when true
    "outline": [[-105.75,-25],[105.75,-25],[105.75,25],[-105.75,25]],
    "tabs": [{"id": "b1", "edge": 0, "offset": 52.9, "width": 20, "depth": 3}],
    "features": [{"id": "cockpit", "kind": "opening", "shape": "rect",
                  "center": [-105, 0], "width": 60, "height": 48, "angle": 0}],
    "placement": {"position": [-45.75, 28, -40], "rotation": [0, 0, 0]}
  }],
  "joints": [{"id": "J-AFT-PORT-b1", "type": "tab_slot", "a": "SIDE-AFT-PORT", "tab": "b1",
              "b": "HULL-BOTTOM", "status": "joined", "slot": "slot-J-AFT-PORT-b1",
              "repairs": [{"action": "create_slot", "...": "..."}]}]
}
```

Designs are **data, never code** (the legacy studio evaluates arbitrary JS; the API does not).

### Complex cuts (curves, shaped cut-outs, engraving)

```jsonc
{"id": "ARCH", "outline": [[-100,-150],[100,-150],[100,50], /* … arc points … */ [-100,50]],
 "arcs": [{"start": 2, "end": 22, "center": [0, 50], "radius": 100, "ccw": true}],
 "features": [
   {"id": "win",   "kind": "opening", "shape": "rect", "center": [0,-20], "width": 80, "height": 40, "corner_radius": 8},
   {"id": "heart", "kind": "opening", "shape": "polygon", "points": [[0,30],[30,60], /* … */], "arcs": [/* … */]}],
 "marks": [{"id": "name", "kind": "engrave", "points": [[-60,-130],[60,-130]], "depth": 0.5},
           {"id": "tray", "kind": "pocket",  "points": [[-30,100],[-10,100],[-10,120],[-30,120]], "depth": 2}]}
```

* Feature shapes: `rect` (optional `corner_radius`), `circle`, `polygon` (any outline; `points`, optional `arcs`).
* Curves are stored flattened (chord error ≤ 0.1 mm) so every check works on exact polygons; `arcs` records which
  vertex runs lie on a circle, and the SVG / DXF exporters write those runs as **true arcs** (SVG `A`, DXF bulge).
  Replacing an `outline` without new `arcs` drops the old arc data. Generate shapes with `board_engine.shapes`.
* `marks` are machined into the +Z face and never cut through: they are not holes for joint or collision checks.
  Validated: inside the board (`MARK_OUTSIDE_BOARD`), engrave ≤ half the thickness (`ENGRAVE_TOO_DEEP`), pockets
  keep the material's minimum remaining thickness (`POCKET_TOO_DEEP`), warning when over a cut-out (`MARK_OVER_CUTOUT`).
  A self-crossing polygon cut-out is `FEATURE_SELF_INTERSECTION`.

### Feature kinds — never interchangeable

| kind | meaning | engine behaviour |
|---|---|---|
| `slot` | receives a tab | matched to joints; generated/resized only by a safe repair; unused → `UNUSED_SLOT` warning (left as cut, never filled) |
| `hole` | functional hole (dowel, line) | never modified; a tab landing in it → `TAB_IN_HOLE` |
| `opening` | intentional design opening (cockpit, window, lightening hole) | never filled, moved or joined into; a tab landing in it → `TAB_IN_OPENING` |

### Joinery: glue-free by default

Designs carry `"joinery": "interlocking"` (default) or `"glue_allowed"`. Interlocking designs are for
cardboard / friction-fit board assembled **without glue**: every connection must be a mechanical
interlock (`tab_slot` — a tab locked through a slot). Glued joint types (`edge_butt`, `edge_mitre`,
`face_lap`) are refused with `GLUE_JOINT_NOT_ALLOWED`. The example boat is fully interlocking:
32 tab-and-slot joints, one generated slot per tab, every part held by at least one interlock.

### Joint types

| type | fields | physical meaning |
|---|---|---|
| `tab_slot` | `a` (has tab), `tab`, `b` (receiver), optional `slot` | tenon locked through a slot (glue-free) |
| `edge_butt` | `a`, `a_edge`, `b` | edge of A glued against the face of B (`glue_allowed` only) |
| `edge_mitre` | `a`, `a_edge`, `b`, `b_edge` | two edges meeting at a corner (`glue_allowed` only) |
| `face_lap` | `a`, `b` | parallel boards laminated face to face (`glue_allowed` only) |
| `hinge` | `a` (door), `a_edge` (hinge edge), `b` (carcass board), optional `count`, `gap` | overlay door on concealed 35 mm cup hinges (`glue_allowed` only) |

Furniture joints (`glue_allowed`) can carry **fasteners**: `edge_butt` and coplanar `edge_mitre` (dowels only)
take `"fasteners": {"kind": "screw" | "confirmat" | "dowel", "count"?, "diameter"?, "length"?, "end"?}` — `end`
is the distance from the contact ends to the first fastener, used to stagger fasteners at 4-way junctions.
`edge_mitre` takes `"bevel": true` for a true mitre (both edges bevelled to half the corner angle; saw / CNC).

### Furniture fields (all optional; existing designs are unchanged)

| Where | Field | Meaning |
|---|---|---|
| `material` | `type` | `plywood`, `mdf`, `particle_board`, `solid_wood`, `hardboard`, `cardboard`, `other` — selects the catalogue in `manufacturing.MATERIALS` |
| component | `material` | `{name?, type?}` override, e.g. a 6 mm hardboard back in a particle-board carcass |
| component | `grain` | `x` / `y` (local axis): nesting turns the part so its grain runs along the sheet's long side |
| component | `edge_banding` | `[{edge, thickness, material?}]` — the cut list shortens the blank on banded edges |

Limits for real furniture: thickness up to 50 mm (solid tops), kerf up to 6 mm (panel saws cut 3.2–4.8 mm).

## 4. Validation rules

### 4.1 Component (2D cut profile) — `validate_component`
| Code | Severity | Rule |
|---|---|---|
| `OUTLINE_SELF_INTERSECTION`, `CUT_PROFILE_SELF_INTERSECTION` | error | outline / outline+tabs must be a simple polygon |
| `DEGENERATE_OUTLINE`, `DEGENERATE_EDGE` | error | area ≥ 1 mm², no zero-length edges |
| `TAB_EDGE_INVALID`, `TAB_OUTSIDE_EDGE`, `TAB_OVERLAP` | error | tab on an existing edge with 0.5 mm shoulders, no overlapping tabs |
| `TAB_TOO_NARROW` | warning | tab width ≥ max(3 mm, thickness) |
| `FEATURE_OUTSIDE_OUTLINE` | error | cut-outs fully inside the profile (no accidental open notches) |
| `INSUFFICIENT_EDGE_MARGIN` / `NARROW_EDGE_MARGIN` | error / warning | ≥ 1.5 mm material bridge (3 mm recommended for slots) |
| `FEATURE_OVERLAP`, `FEATURE_SPACING` | error | cut-outs don't overlap; ≥ 1 mm apart |
| `FEATURE_TOO_SMALL` | error | ≥ 1 mm (cuttable) |
| `PART_EXCEEDS_SHEET` | error | fits the design sheet in some orientation |

### 4.2 Joint evaluation — `evaluate_joint` (tab_slot shown; others analogous)
1. **Orientation**: the tab's insertion direction must be parallel to the receiver's normal (≤ ~3°) → `ORIENTATION_MISMATCH`; a tab pointing away → `TAB_POINTS_AWAY`.
2. **Contact**: the tab shoulder must sit on the receiver face within ±0.25 mm → `UNINTENDED_GAP` / `PENETRATION`, each with `suggestion.delta` (the exact translation that fixes it).
3. **Engagement**: depth ≥ ½ receiver thickness (`TAB_TOO_SHORT`), warnings for not flush / protruding.
4. **Landing zone**: footprint inside the receiver outline (`TAB_OUTSIDE_RECEIVER`), not in an `opening`/`hole` (`TAB_IN_OPENING` / `TAB_IN_HOLE`).
5. **Slot**: a slot must overlap the footprint. None → `MISSING_SLOT` (**repairable**: `create_slot` with tab width + clearance × board thickness + clearance, at the exact position/angle). Wrong size → `SLOT_TOO_SMALL` / `SLOT_TOO_LOOSE` (**repairable**: `resize_slot`). Off-centre → `SLOT_MISALIGNED` (**not** auto-repaired: it is ambiguous whether the part or the slot is wrong; a `translate` suggestion is given). Rotated → `SLOT_ORIENTATION_MISMATCH`. Already used by another joint → `SLOT_ALREADY_USED`.

`edge_butt` checks perpendicularity, flushness (`EDGE_NOT_FLUSH`), direction (`EDGE_FACES_AWAY`), gap/penetration and contact length on real material (`NOT_IN_CONTACT`). `edge_mitre` checks coincident edges (`EDGES_NOT_COINCIDENT`). `face_lap` checks parallelism, face gap and shared face area (≥ 30 mm²).

### 4.3 Assembly — `find_collisions`
For every pair of plates (AABB pre-filter) the mid-plane intersection line is sampled every 0.5 mm
and tested against **real material** of both plates (cut outline incl. tabs, minus slots, holes and
openings, 0.25 mm contact tolerance). Parallel plates closer than (tA+tB)/2 are tested by projected
area. A tab correctly inside its slot is therefore *not* a collision; a tab without a slot, or two
unrelated parts occupying the same space, is `COLLISION` — reported once per contiguous region with
its world location.

### 4.4 Design level — `validate_design`
`DUPLICATE_COMPONENT_ID`, `DUPLICATE_COMPONENT` (same profile + placement), `DUPLICATE_JOINT`,
`JOINT_NOT_JOINED` (a detached connection, warning),
`JOINT_BROKEN` (a joined connection no longer fits after an edit), `UNUSED_SLOT`, `UNJOINED_TAB`,
`FLOATING_COMPONENT` (not connected to the main assembly by joined joints), plus all of the above.
`valid` = no errors; `complete` = valid and nothing floating, unjoined or detached.

## 5. Joining rules (`board_engine/joining.py`)
1. Reject structurally bad requests (unknown parts, duplicate id, already joined).
2. Evaluate the joint.
3. Any error **without** a safe repair rejects the join with reasons (`status: rejected`).
4. Errors **with** a safe repair are fixed only with `auto_repair=true`; otherwise `status: needs_repair` and the proposed repairs are returned — nothing changes.
5. Repairs are applied to a copy; the receiver is re-validated. A repair that would break margins/spacing/openings is discarded (`status: repair_unsafe`).
6. The joint is re-evaluated, then the whole design is validated; any **new** error rejects the join (`rejected_post_validation`).
7. Only then is the joint stored as `joined`, with the repairs it made recorded. Correct geometry is never modified.

Edits to joined parts are re-checked: an edit that breaks a joint is refused (`would_break_joints`)
unless `detach_broken_joints=true`, which marks those joints `detached`. Removing a joint (or a part
with `cascade`) also removes the slots that joint generated — and only those.

### 5.1 Automatic fixes (deterministic, no AI) — `board_engine/autofix.py`
Fixes are derived only from intended connections (joints), so the engine never guesses intent:

| Fix kind | When | Action |
|---|---|---|
| `translate` | `UNINTENDED_GAP`, `PENETRATION` (incl. a part sunk through its receiver), `SLOT_MISALIGNED`, `EDGES_NOT_COINCIDENT` | move the part by the computed offset, then re-join if detached |
| `rejoin` | a detached joint that fits again, or only needs a safe slot repair | re-join through the full join pipeline (`auto_repair`) |
| `repair` | a joined connection lost its slot fit | regenerate / resize the slot |

Guards: the fix runs on a copy; a moved part must not break any of its other joined connections;
the result is kept only if the design has no more errors than before. Problems without a safe fix
(`TAB_IN_OPENING`, `ORIENTATION_MISMATCH`, `TAB_OUTSIDE_RECEIVER`, …) are listed as `unfixable`
("needs a design decision") and never changed. **Auto-fix all** repeats plan → apply until nothing
applies (max 50 steps); a run that applies nothing does not create a new revision.

Validation responses from the API include `fixes`, `unfixable`, and a `fix_id` on each
`JOINT_BROKEN` / `JOINT_NOT_JOINED` issue. In the studio these appear as **Apply fix** buttons and an
**Auto-fix all** button in the Validation tab.

## 6. REST API (`/api/v1`)

Authentication: `Authorization: Bearer <key>` (or `X-API-Key`). Roles: **viewer** (read, validate,
check, export) < **editor** (+ all modifications) < **admin** (+ delete designs). Keys come from
`BOARD_API_KEYS="key:role,..."` or `instance/api_keys.json`. The studio uses an HttpOnly,
SameSite=Strict session cookie and must send `X-Board-Client: studio` (CSRF guard); the API sends no
CORS grant. Limits: 2 MB bodies, 600 requests/min per principal (`BOARD_RATE_LIMIT`), bounded
component/point/feature counts and coordinates.

Envelope: `{"ok": true, "revision": n, "result": ..., "validation": {valid, complete, summary, issues}}`
or `{"ok": false, "error": {"status", "message", "issues": [...]}}`. Status codes: 400 schema,
401/403 auth, 404, 409 stale `expected_revision` or not ready for production, 422 rejected by
validation, 429 rate limit. Every accepted mutation bumps `revision` and is recorded in `/history`.

| Method & path | Role | Purpose |
|---|---|---|
| `GET /api/v1/` · `GET /api/v1/tools` | public | contract · LLM tool definitions (JSON schema) |
| `GET /whoami` · `GET /sheet-presets` | viewer · public | principal · presets & tolerances |
| `GET /designs` · `POST /designs` | viewer · editor | list · create (components via validated add, joints via join pipeline) |
| `POST /designs/examples/boat` | editor | build the parametric boat (`params`: length, beam, depth, mast_height, thickness, …) |
| `GET /designs/{id}` · `DELETE /designs/{id}` | viewer · editor | design + summary · delete |
| `PATCH /designs/{id}` · `POST /designs/{id}/duplicate` | editor | rename / describe · copy under a new id |
| `GET /storage` | viewer | storage backend (`firestore` / `file`), persistence, config errors |
| `GET /designs/{id}/history` | viewer | audit log (actor, op, revision) |
| `POST /designs/{id}/validate` | viewer | full report |
| `GET /designs/{id}/model3d` | viewer | world matrices, cut outlines, features, state per component, bounds |
| `GET /designs/{id}/components[/{cid}]` | viewer | dimensions, edges (indices + world coords), tabs (world insertion direction), features |
| `POST /designs/{id}/components` | editor | add component |
| `PATCH /designs/{id}/components/{cid}` | editor | `{"patch": {...}, "detach_broken_joints": false}` |
| `POST /designs/{id}/components/{cid}/translate` | editor | `{"delta": [dx,dy,dz]}` — apply `suggestion.delta` |
| `DELETE /designs/{id}/components/{cid}?cascade=1` | editor | remove (and its joints / generated slots) |
| `POST|DELETE …/components/{cid}/features[/{fid}]` | editor | add / remove slot, hole, opening |
| `POST|DELETE …/components/{cid}/tabs[/{tid}]` | editor | add / remove tab |
| `GET /designs/{id}/joints` | viewer | joints with status, matched slot, repairs |
| `POST /designs/{id}/joints/check` | viewer | dry run → `fits`, issues, `repairs_available` |
| `POST /designs/{id}/joints` | editor | `{"joint": {...}, "auto_repair": bool}` → 201 joined / 422 with reasons |
| `DELETE /designs/{id}/joints/{jid}?keep_slots=0` | editor | unjoin |
| `GET /designs/{id}/fixes` | viewer | planned fixes + unfixable problems |
| `POST /designs/{id}/fixes/apply` | editor | `{"fix_id": "J-MAST-STEP:translate"}` (422 if stale or it would make things worse) |
| `POST /designs/{id}/fixes/auto` | editor | `{"max_steps": 50}` → steps applied, skipped, unfixable |
| `PUT /designs/{id}/material` | editor | change material; re-checks every joint |
| `POST /designs/{id}/operations` | editor | atomic batch (`add_component`, `update_component`, `translate`, `delete_component`, `add_feature`, `remove_feature`, `add_tab`, `remove_tab`, `join`, `unjoin`, `set_material`) |
| `GET /designs/{id}/layout2d?preset=A3&margin=10&spacing=5&rotation=orthogonal&kerf=1` | viewer | nesting + cutting paths + readiness |
| `GET /designs/{id}/export/{pdf|svg|dxf}?sheet=1&preset=A3&paper=A4&kerf=1[&force=1]` | viewer | production files (409 unless ready, `force=1` exports a marked draft) |
| `GET /designs/{id}/manufacturing?kerf=1` | viewer | manufacturability: fasteners, drilling, hinges, contacts and gaps, joint options, assembly plan, material limits (§9) |
| `GET /designs/{id}/cutlist` | viewer | board identification and grouped cut list (§9) |
| `POST /designs/examples/furniture/{product}` | editor | build a real product through the join pipeline (`table`, `bookshelf`, `cabinet`, `wardrobe`, `drawer`, `l-desk`, `storage-rack`, `tv-unit`, `mitred-stand`, `cube-storage`; numeric `params`) |

## 7. AI-agent workflow

`tools/ai_agent_demo.py` is a reference agent (stdlib HTTP) that performs the controlled loop:

1. requirement → 2. discover `/api/v1` + `/tools` → 3. derive parameters → 4. create components →
5. server validates 2D → 6. `joints/check` each intended connection → 7. on `UNINTENDED_GAP`,
`PENETRATION` or `SLOT_MISALIGNED` apply `suggestion.delta` via `translate`; on `TAB_IN_OPENING` move
the part (the opening is preserved); on `MISSING_SLOT` join with `auto_repair` → 8. every change is
re-validated by the server → 9. repeat until `valid && complete` → 10. fetch `model3d`, `layout2d`
and the PDF/SVG/DXF files.

```bash
python tools/ai_agent_demo.py --url http://127.0.0.1:5000 --key "$(jq -r '.keys[0].key' instance/api_keys.json)" --out out/
```

For LLM function calling, map `GET /api/v1/tools` entries (`name`, `description`, `input_schema`,
`http`) to your tool definitions; the agent never touches state except through these endpoints.

## 8. Production

* **Nesting** (`board_engine/nesting.py`): MaxRects best-short-side-fit on cut-profile bounding
  boxes, largest first, multiple sheets. **Each stock board (material, type, thickness) is nested on its own
  sheets** — an 18 mm side and a 6 mm back never share a sheet; every sheet records its `stock`, and the
  verification pass rejects `MIXED_STOCK_ON_SHEET`. Declared grain fixes the rotation (grain along the sheet's
  long side). Spacing below the kerf is `SPACING_BELOW_KERF` (neighbouring cuts would eat into parts). Presets `A4, A3, A2, Letter, Tabloid, board-600x400,
  board-800x600, board-1220x610, board-2440x1220` or custom `width/height`; `margin`, `spacing`,
  `rotation` (`orthogonal` = 0°/90°, or `none`), per-part `grain_locked`. Parts that cannot fit are
  reported (`PART_EXCEEDS_SHEET`), never placed outside the usable area. A second pass verifies
  real polygon overlap, spacing and boundaries. Stats: sheets, total/used/waste area, efficiency.
* **Cutting paths** (`board_engine/cutpaths.py`): one closed OUTER path per part (profile with tabs
  and notches) and one INNER path per slot/hole/opening; inner paths are ordered before their part's
  outer path. Optional kerf compensation (outer +kerf/2, inner −kerf/2, verified per edge). Checks:
  self-intersection, inner touching outer, overlapping or **duplicate** paths (duplicates dropped).
* **Exports**: SVG (mm units, layers `ENGRAVE` / `POCKET` (when present, machined first, `data-depth`) /
  `CUT_INNER` blue / `CUT_OUTER` red / `ENGRAVE_LABELS`; curves as true arcs), DXF R12 (same layers,
  `$INSUNITS`=mm, curves as bulges), PDF booklet (`board_engine/booklet.py`, dependency-free vector PDF):
  cover with project info, validation status, nesting stats and component schedule; one **1:1**
  cutting template per sheet (page size = sheet size, 50 mm scale-check bar, `PrintScaling /None`);
  one dimensioned drawing per component (standard scale, datum, feature/tab tables, assembly
  references, cutting instructions); an assembly sequence derived from the joint graph; page
  numbering and a title block on every page. PNG previews are rendered client-side from the SVG.

## 9. Manufacturing engineering & cut list

A design that is geometrically valid is not necessarily manufacturable. `board_engine/manufacturing.py`
checks what it takes to make and assemble it; `production_package` (layout, exports) includes its errors in
`ready_for_production`. Catalogue values (`MATERIALS`, `FASTENERS`, `HINGE`) are typical European / 32 mm
system figures — review them for your supplier.

| Area | Checks / output | Codes |
|---|---|---|
| Materials | stock thickness, minimum part width, grain across a solid-wood span, banding on short / joined / tabbed edges, uncompensated kerf larger than the cut tolerance | `NONSTANDARD_THICKNESS`, `PART_BELOW_MIN_SIZE`, `GRAIN_ACROSS_LENGTH`, `GRAIN_UNSPECIFIED` (info), `BANDING_ON_*`, `KERF_NOT_COMPENSATED` |
| Fasteners | positions along the real contact (end distance, max spacing, count); edge wall beside the bore; screw engagement; break-out of the far board or into cut-outs; face bores near an edge; drilling list per board (face bore: face, position, Ø, depth, through; edge bore: edge, offset, Ø, depth) | `FASTENER_TOO_THICK_FOR_EDGE`, `FASTENER_TOO_SHORT`, `FASTENER_BREAKS_OUT`, `FASTENER_IN_CUTOUT`, `FASTENER_NEAR_EDGE`, `FASTENER_TOO_CLOSE_TO_END`, `FASTENER_NO_CONTACT`, `DOWEL_SHALLOW`, `SINGLE_FASTENER` |
| Cross-checks | fastener bodies closer than r1+r2+2 mm (spatial hash), a fastener running into a third board, a board in the driver's line | `FASTENER_COLLISION` (with a **verified** `stagger_fasteners` suggestion), `FASTENER_HITS_BOARD`, `TOOL_ACCESS_BLOCKED` |
| Hinges | count from door height, cup bores (Ø35 × 13 at 22.5 mm), mounting-plate holes, hinge positions moved clear of shelves, door reveal | `HINGE_POSITION_ADJUSTED` (info), `HINGE_OBSTRUCTED`, `HINGE_CUP_OFF_DOOR`, `DOOR_GAP_TOO_SMALL`; in validation: `HINGE_CUP_TOO_DEEP`, `DOOR_NOT_OVER_CARCASS`, `DOOR_FACES_AWAY`, `HINGE_COUNT_LOW` |
| Connections | boards touching without a joint (L / T / face, with recommended joints and alternatives checked against thickness and material), near-miss gaps up to 5 mm with the exact `translate` delta, glue-only butt joints on particle board / MDF; hinged doors are excluded (their clearance is intentional) | `CONTACT_WITHOUT_JOINT`, `POSSIBLE_GAP`, `WEAK_JOINT` |
| Assembly | assembly by disassembly on a local blocking graph: tabs and dowels allow one sliding direction, butt / lap contacts forbid moving into the other board; strongly connected components give removable sub-assemblies. Output: ordered steps with sub-assemblies and approach directions (each step attaches to what is built, doors last), or the boards that lock each other | `ASSEMBLY_LOCKED`, `FASTEN_BEFORE_FITTING` (info) |

`board_engine/cutlist.py` identifies every board by its component id (stable under moving, rotating and
resizing) and reports: purpose (group), material, thickness, world orientation, **finished size from the
minimum-area rectangle of the cut profile** (not the bounding box), **blank size** (minus edge banding, plus
mitre long points `t/2·cot(φ/2)`), each edge (straight / angled, banding, bevel), operations (angled cuts,
notches, tabs, through cuts, bevels with blade tilt, drilling), connections, and `process` (`saw` / `cnc`).
Identical boards (same profile, cut-outs, banding and drilling, allowing the board to be turned over or end
for end) are grouped with a quantity. The PDF booklet adds a cut-list page, drilling tables on each component
drawing, and uses the validated assembly plan.

Not modelled yet: housing joints (dado / rabbet / groove), cam locks, biscuits, pocket screws, blind pockets,
CNC tool radius in inside corners, sweep paths for the assembly planner (it reasons from contacts only),
pre-mill allowance on edge banders.


## 9. AI Design Canvas (`/canvas`)

Design new products with any external AI (ChatGPT, Gemini, Claude) and compile the result with this generator.

1. **Describe** the product (title, requirements, material, thickness, joinery).
2. **Prompt**: `POST /api/v1/canvas/prompt` builds a self-contained prompt. It embeds the full format specification
   (`docs/board-design-format.md`, generated from the engine's own constants: tolerances, limits, id rules, material
   and fastener catalogues) and a complete valid example. Copy it into the AI.
3. **Code**: paste the AI's reply into the editor (CodeMirror). Code fences, prose around the JSON, `//` / `/* */`
   comments and trailing commas are tolerated. The source is **data only** — it is parsed as JSON and never executed.
4. **Compile** (`POST /api/v1/canvas/compile`, read-only): `board-design/v1` boards (axis-aligned world boxes) become
   engine components via `furniture.panel()`; each connection finds A's end face against B's broad face, places tabs
   and runs `joining.join()` (slots generated, gaps / overlaps / margins validated); then `validate_design()`, the
   3D model, nesting, cut paths, cut list and manufacturing summary. Diagnostics carry the board id, the source line
   and code-level **fixes**: *safe* ones (placement off by ≤ 2 mm) can be auto-applied; dimension changes are
   confirmed by the user. The envelope is `{"ok": true, "compiled": bool, ...}`.
5. **Preview / edit**: the studio's 3D and 2D engines render the result; selecting a board highlights its JSON and
   putting the cursor in a board selects it in 3D; position / size edits are written back into the code.
6. **Save** (`POST /api/v1/canvas/save`) always creates a **new project** (the code is stored in `design.source`);
   updating is only allowed for a project that was itself created by the canvas. **Import** (`POST
   /api/v1/canvas/import`) adds selected boards and their connections to an existing project through the normal
   validated operations (clashing ids get an `AI-` prefix). Native engine JSON (`components` / `joints`) is also accepted.
