# 06 — 2D and 3D Consistency

**Result: the representations agree for every product that compiles (13/13), and an edit reaches all of them.**
Implementation: `tests/e2e/pipeline.py::consistency()` (run per product), `tests/e2e/propagation.py` → `propagation.json`.

## 1. The representations compared

| # | Representation | Produced by |
|---|---|---|
| R1 | Original structured design (`board-design/v1` boxes) | the AI / user |
| R2 | Native design (2D outlines + placements, joints, slots) | `canvas.compile_source` |
| R3 | 3D geometry / assembled model | `views.model3d` (drawn by `viewport3d.js` with the backend `matrix_world`) |
| R4 | Cutting layout + cut paths | `nesting.nest`, `cutpaths.generate_cut_paths` |
| R5 | Production files and drawings | `sheet_svg`, `sheet_dxf`, `booklet.build_booklet`, `cutlist.cut_list` |

## 2. Checks (all automated, all products)

| Check | R1↔R2 | R2↔R3 | R2↔R4 | R4↔R5 | Tolerance |
|---|---|---|---|---|---|
| Component count / ids | ✔ | ✔ | ✔ (placed once each) | ✔ (SVG outer paths, DXF outer polylines, cut-list boards) | exact |
| Dimensions | ✔ every unrotated, unprofiled board's 3D extent = source box; profiled boards stay inside it; finger joints may add up to the partner's thickness | ✔ outline area | ✔ outer cut-path area | ✔ | 0.02 mm / 1e-3 mm × perimeter |
| Thickness | ✔ | ✔ | ✔ cut list | ✔ | exact |
| Placement / coordinates / axes | ✔ world extent | ✔ world bounds = placement | n/a (sheet frame, unmirrored by design) | ✔ DXF is y-flipped to match SVG/PDF (by design) | 0.01 mm |
| Rotation | tilted boards: placement from `_apply_rotate`; 3D uses the same matrix | ✔ | parts rotate only 0°/90° on the sheet | ✔ | — |
| Joint positions | slots generated from the joints; `evaluate_joint` re-checks tab-in-slot on every validation | ✔ same features | ✔ inner paths = features | ✔ | 0.5 mm position, 0.15 mm fit |
| Gaps / overlaps | validated once on R2; R3 draws the same solids | ✔ | — | — | contact 0.25 mm |
| Scale | mm throughout; PDF templates 1:1 with a 50 mm scale bar; DXF `$INSUNITS = 4` (mm) | ✔ | ✔ | ✔ | — |

The first audit's spot check (5 products) is now a regression test on every product (`test_e2e_pipeline.py`).

## 3. Modification propagation (verified)

`propagation.py` adds a 60 mm hole to the table top of a saved design through the API and re-reads everything:

| | before | after |
|---|---|---|
| revision in model3d / layout2d / cutlist | 1 / 1 / 1 | **2 / 2 / 2** |
| TOP features in 3D | 7 | **8** |
| TOP inner cut paths in 2D | 7 | **8** |
| hole in the SVG export | no | **yes** |
| DXF inner circles | 1 | **2** |

Every projection is recomputed from the stored design on each request, so no stale copy exists server-side.

## 4. Known, intentional differences

* Curves are flattened to ≤ 0.1 mm chords for 2D and 3D alike. With kerf compensation on, some DXF arcs become polylines
  (BUG-017, open): the geometry is the same, the CAM representation differs.
* Engravings/pockets appear as lines on the 3D face (no depth).
* The 3D view shows nominal geometry; the cut paths are kerf-compensated. The difference is exactly kerf/2 per edge and
  is checked.

## 5. Residual risk

* **R-4 (open)**: in the Studio the 2D and 3D panes come from separate requests without a revision comparison. Under a
  concurrent edit they can briefly show different revisions. The server data is consistent; the browser view may lag one refresh.
