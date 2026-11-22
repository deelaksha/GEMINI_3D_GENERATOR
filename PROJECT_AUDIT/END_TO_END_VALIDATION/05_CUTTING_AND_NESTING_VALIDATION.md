# 05 — Cutting and Sheet Nesting Validation

Executed: `tests/e2e/nesting_cases.py` → `nesting_cases.json` (12 pass, 0 fail, 2 not implemented), plus the
nesting/cut-path consistency checks run on all 13 compiled corpus products (`e2e_results.json`).

## 1. Edge cases

| ID | Case | Result | Pass |
|---|---|---|---|
| NS-01 | Part exactly the usable area (2420 × 1186 on 2440 × 1220 with 10 mm margin + 14 mm title strip) | placed | ✔ |
| NS-02 | Part 1 mm larger | `PART_EXCEEDS_SHEET` | ✔ |
| NS-03 | Very narrow part (600 × 12 mm plywood) | `PART_BELOW_MIN_SIZE` blocks production | ✔ |
| NS-04 | Excessive kerf (7 mm) | schema error `material.kerf must be <= 6.0` | ✔ |
| NS-05 | Hole smaller than the kerf | [F] `FEATURE_SMALLER_THAN_KERF` + `CUT_PATH_DEGENERATE`, blocked. **Baseline produced a −0.1 mm radius and said ready (BUG-002)** | ✔ after fix |
| NS-06 | Grain restriction | grain-x part unrotated, grain-y part rotated 90° | ✔ |
| NS-07 | Rotation forbidden and part only fits rotated | placed one, other `PART_EXCEEDS_SHEET` | ✔ |
| NS-08 | Different thicknesses | separate sheets (stock key = name, type, thickness) | ✔ |
| NS-09 | 12 identical parts | one cut-list line ×12, all placed, no overlap issues | ✔ |
| NS-10 | Waste arithmetic | reported used 1 440 000 mm² = Σ part areas; waste = sheets × area − used (exact) | ✔ |
| NS-11 | Three parts each larger than half a sheet | 3 sheets | ✔ |
| NS-12 | Irregular shapes (hexagon, circle) | placed on bounding boxes, no overlap | ✔ |
| NS-13 | Shared-edge (common-line) cutting | not implemented | — |
| NS-14 | True-shape nesting | not implemented (bounding-box MaxRects, 0°/90°) | — |
| corpus | Zero / negative dimensions | `BOARD_SIZE` (EC-08), `MATERIAL_THICKNESS` (EC-09) | ✔ |
| corpus | Component larger than every stock sheet | [F] largest stock chosen, then `PART_EXCEEDS_SHEET` | ✔ |

## 2. Checks on every compiled product (13 corpus products)

| Check | Method | Result |
|---|---|---|
| Every component appears in the layout exactly once | placements + unplaced = design ids, no duplicate | ✔ 13/13 |
| No part leaves the sheet | placement bbox inside the usable rectangle | ✔ |
| No illegal overlaps | `verify_nesting` polygon check + `nesting.issues` empty | ✔ |
| Dimensions after nesting | uncompensated outer cut-path area = design part area (≤ 0.05 mm²) | ✔ |
| Cut-out count | inner paths = features per part | ✔ |
| Kerf compensation | compensated outer area grows by 0 … kerf/2 × perimeter (+ corner term) | ✔ |
| No degenerate paths | no non-positive radius, [F] no inverted offset polygon | ✔ |
| Material allocation | stock groups by (name, type, thickness); mixed-thickness bookshelf back on its own sheet | ✔ |
| Waste figures | recomputed independently from part polygons (cut profile − holes) and sheet count | ✔ 13/13 |
| Files | SVG outer paths = DXF outer polylines = placements | ✔ 13/13 |

## 3. Bugs found and fixed here

* **BUG-019 [F]**: the canvas picked a sheet with a rough allowance (2 × thickness + 20 mm) that ignored the 14 mm title
  strip, and fell back to 2440 × 1220 when nothing fitted. A 1200 mm-wide bookshelf back was therefore declared
  unfittable, although the catalogue's 2500 × 1250 stock fits it. It now measures the real cut profile with the nesting's
  own allowances and falls back to the largest stock (`test_bug019_auto_sheet_fits_a_1200_mm_back_panel`; corpus E2E-02).
* **BUG-002 [F]**: sub-kerf holes (NS-05).

## 4. Still open (manufacturing truth; see first audit 04)

* **BUG-004**: no CNC tool model (bit diameter, inside-corner dog-bones) and a 3.2 mm saw kerf applied to CNC-only cuts.
  "Ready for production" is still optimistic for router-cut furniture board.
* Bounding-box nesting only. Low utilisation is honest for small products on full stock (enclosure 5 %), but irregular
  parts waste space.
* No common-line cutting, no remnant reuse, no hold-down tabs, no lead-ins: the DXF is geometry for CAM, not tool paths.
