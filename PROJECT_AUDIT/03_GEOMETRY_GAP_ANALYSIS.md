# 03 — 2D-to-3D Geometry Gap Analysis

Evidence: code reading plus `PROJECT_AUDIT/repro/{scenarios,probes,consistency}.py`, run against commit `bf1f44b`.

## 1. Check-by-check

| Check | Implementation | Evidence | Status |
|---|---|---|---|
| Board dimensions | v1 board = axis-aligned box `position..position+size`; `_check_boards` rejects non-positive sizes and coordinates beyond ±5000 mm | E06, E19 | ✔ |
| Thickness | Exactly one `size` component must equal the thickness (tolerance 0.01 mm), else `THICKNESS_MISMATCH` / `AMBIGUOUS_ORIENTATION` (`canvas._Board`) | E08 | ✔ |
| Coordinate system | mm, +Y up, X length, Z depth; Euler XYZ (THREE order) in `geometry.rotation_matrix`; inverse in `canvas._euler_xyz` | `model3d.up_axis='Y'` | ✔ consistent across engine, 3D viewer and docs |
| Axis alignment | Untilted boards are axis-aligned by construction. `rotate` supports one axis per board only (no compound tilt in v1; native format allows full Euler) | — | ✔ / limitation |
| Face orientation | Outlines forced CCW (`model.normalize_component`, `normalize_feature`, marks), with a note when reversed | code | ✔ |
| Panel positioning | `furniture.panel()` builds the local frame; openings mapped world→local; `OPENING_OFF_BOARD` when the centre is not inside the thickness | E16 | ✔ |
| Duplicate boards | `DUPLICATE_BOARD_ID`; `DUPLICATE_COMPONENT` for an identical signature; an overlapping copy with a different id is caught as `COLLISION` | E14 | ✔ |
| Missing boards | **Not detectable.** Nothing compares the board list with the product requirement. Only connectivity (`FLOATING_COMPONENT`) and `OVERALL_MISMATCH` are checked, and both are warnings | E07, E15 | ✘ gap |
| Overlapping geometry | Solid-vs-solid sampling along the intersection line of the two mid-planes at 3 offsets, every 0.5 mm (`validation._plate_interference`); parallel boards by projected area | E14, wardrobe, toy car | ✔ but sampled (see R-1) |
| Incorrect gaps | Joint contact tolerance 0.25 mm (`TOL['contact']`); unjoined faces closer than 2 mm flagged `NEAR_MISS_GAP` | 05-cabinet warning | ✔ |
| Incorrect joints | 7 joint evaluators (`_eval_tab_slot`, `_eval_finger`, `_eval_cross_lap`, `_eval_edge_butt`, `_eval_edge_mitre`, `_eval_hinge`, `_eval_face_lap`); slot reuse → `SLOT_ALREADY_USED` | wardrobe | ✔ |
| Extrusion | 3D = `THREE.ExtrudeGeometry` of `cut_outline` with features as holes, depth = thickness (`viewport3d.js:51-75`) | frontend audit | ✔ |
| Self-intersection | `OUTLINE_SELF_INTERSECTION`, `CUT_PROFILE_SELF_INTERSECTION`, `FEATURE_SELF_INTERSECTION`, `CUT_PATH_SELF_INTERSECTION` | code | ✔ |
| Non-manifold geometry | Not applicable as a check: every part is a prism of one simple polygon with simple holes, which is manifold by construction once the self-intersection and `FEATURE_OUTSIDE_OUTLINE` checks pass | — | ✔ by design |
| Floating components | Connectivity over joined joints → `FLOATING_COMPONENT` **warning**; the design stays `valid` and `ready_for_production` | E15, 07 box lid | ⚠ BUG-007 |
| Incorrect scaling | Units are hard-wired to mm. There is no `units` field and no sanity check that sizes are plausible for the product (an AI answering in inches or cm produces a tiny product that compiles) | — | ⚠ R-3 |
| Stability / gravity | **Not checked**: tipping, centre of mass, load paths and racking resistance are all absent | — | ✘ gap |

## 2. Does the 2D design equal the 3D model? — **Yes (verified)**

For the chair, table, bookshelf, cabinet and storage box, every part's nested cut path (kerf off) was compared with the 3D
`model3d.cut_outline`:

| Design | Parts in 3D | Parts on sheets | Missing | Area difference | Hole-count mismatch |
|---|---|---|---|---|---|
| 02-chair | 5 | 5 | 0 | 0 | 0 |
| 03a-table | 5 | 5 | 0 | 0 | 0 |
| 04-bookshelf | 9 | 9 | 0 | ≤ 0.03 mm² (rounding) | 0 |
| 05-cabinet | 7 | 7 | 0 | ≤ 0.03 mm² (rounding) | 0 |
| 07-storage-box | 6 | 6 | 0 | ≤ 0.01 mm² (rounding) | 0 |

The match holds by construction: both views come from the same `Plate.cut` and `feature_polys` (`model.py`). The 3D
viewer places parts with the backend `matrix_world`, not by recomputing.

Residual differences, all known:
* Curves are flattened to ≤ 0.1 mm chords (`shapes.FLATTEN_TOL`). 2D and 3D both draw the polyline; `arcs` metadata is used only for SVG/DXF export.
* With kerf compensation on, some true arcs degrade to line segments in the DXF. Measured on the cottage example: 17 arcs without kerf, 14 with it, because offset points no longer lie on the stored circle (`cutpaths.path_segments`, `ARC_TOL = 0.02`). The cut is still dimensionally correct, but CAM gets polylines.
* Engrave/pocket marks are drawn as lines on the +Z face only, and pockets have no depth in 3D (`viewport3d.js:79-87`).
* The 2D and 3D panes in the Studio are fetched separately and their revisions are not compared (`js/studio/main.js:155-169`). A concurrent edit can show 2D and 3D from different revisions (R-4).

## 3. Confirmed geometry defects (details in 09)

| ID | Defect | Reproduction |
|---|---|---|
| BUG-003 | Auto-inferred connection ids longer than 64 characters crash the compiler (`TypeError`) | `scenarios.py` E11 |
| BUG-005 | Two shelves at the same height on both sides of a through-divider cannot both be tabbed; the engine has no blind or shared slot | `scenarios.py` 10-wardrobe; staggering by 60 mm fixes it (`probes.py` B) |
| BUG-006 | "Safe" cross_lap fix suggested for a profiled board, which cross_lap can never accept | `probes.py` A |
| BUG-007 | Floating boards and overall-dimension conflicts do not block production | E15, E07 |

## 4. Geometry the format cannot express (product-level gaps)

| Gap | Real products affected | Evidence |
|---|---|---|
| Face-to-face assembly (laminations, glued blocks, stacked layers) | Guitar neck on body, laminated legs, layered toys | 01-guitar: no v1 connection type is accepted (`probes.py` E). `face_lap` exists natively (`validation._eval_face_lap`) but is not exposed in `board-design/v1`. |
| Bevelled edges for non-90° meetings, except roof-pitch / mitre cases | Flared boat hulls, splayed legs, hoppers | 06-boat-punt `NO_CONTACT` |
| Curved or bent panels | Guitar ribs, boat hulls, kerf-bent parts | Not representable; boards are flat prisms |
| Round stock (dowels, axles, rods) | Toy wheels, rails, hanging rods | 09-toy-car: a square board as the axle collides and is below the minimum part size |
| Moving assemblies (drawers, sliding trays, wheels, lids) | Desks, toys, boxes | Only `hinge` exists; others end as floating or colliding |
| Compound rotation in v1 | Splayed chair legs | `rotate` takes one axis |

## 5. Potential risks (not reproduced as failures)

* **R-1 Sampled collision detection** — interference is sampled every 0.5 mm along the plane-intersection line
  (`TOL['sample_step']`). A collision shorter than one step along that line could fall between stations. Edges and
  faces of P are sampled at 3 offsets (−t/2, 0, +t/2), so most real overlaps are caught. Not reproduced.
* **R-2 Interference cache** — `_INTERFERENCE_CACHE` is a process-global dict cleared at 20 000 entries. It is keyed by full
  geometry signature, so it is correct, but it is unbounded in entry size and shared by all requests (memory, not correctness).
* **R-3 Units** — no `units` field; inches or cm compile silently as mm.
* **R-4 2D/3D revision skew** in the Studio UI under concurrent edits.
