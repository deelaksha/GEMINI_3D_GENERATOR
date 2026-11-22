# 04 — Manufacturing and Production Validation

## 1. Check-by-check

| Area | Implementation | Evidence | Status |
|---|---|---|---|
| Sheet dimensions | `nesting.SHEET_PRESETS` (paper A4…Tabloid, boards 600×400 … 2440×1220); per-material `stock` lists in `manufacturing.MATERIALS`; canvas picks the first stock sheet that fits the largest part (`canvas._auto_sheet`) | E19 → `PART_EXCEEDS_SHEET` | ✔ |
| Material thickness | Catalogue of standard thicknesses per material; `NON_STANDARD_THICKNESS` / `NONSTANDARD_THICKNESS` warnings | E20 | ✔ |
| Cutting allowance / kerf | `material.kerf` (catalogue: **3.2 mm for every wood board**, 0.2 for cardboard; default design 0.15 mm). Compensation by polygon offset `kerf/2` (`cutpaths.offset_polygon`), circles by radius. `KERF_NOT_COMPENSATED` error when off and kerf/2 > cut tolerance | all scenarios | ⚠ see §2 |
| Kerf compensation correctness | `_offset_error` verifies each offset edge lies exactly kerf/2 out (`DIMENSION_DRIFT`); the slot test confirms width = t + clearance − kerf | `test_gap_detection` | ✔ for polygons; **✘ circles smaller than the kerf get a negative radius** (BUG-002) |
| CNC tool clearance | **Absent.** No tool diameter, no inside-corner radius, no dog-bone / T-bone relief (`grep -i "dog.?bone\|tool_diam\|router"` → nothing) | — | ✘ BUG-004 |
| Edge margins | Feature/slot to edge ≥ 1.5 mm (error), < 3 mm warning for slots; tab_slot inset checked at compile time (`SLOT_AT_EDGE`) | code, prompt | ✔ (laser-scale values; see §2) |
| Board nesting | MaxRects best-short-side-fit on **bounding boxes**, 0°/90° only, grain forces orientation, separate bins per stock key, polygon overlap verified after placement (`verify_nesting`) | all | ✔ correct, ⚠ low utilisation for shaped parts |
| Sheet utilisation | Reported (`efficiency_percent`, `waste_percent`, per stock) | chair 23.6 %, storage box 8.75 %, table 38 %, bookshelf 42 %, wardrobe 64 % | ⚠ see §3 |
| Joint tolerances | Slot = tab-board thickness + `clearance` (default 0.10 mm, example 0.2); loose > +0.3 mm rejected; slot position ±0.5 mm | `TOL` | ⚠ clearance is not compared with the material thickness tolerance (§2) |
| Assembly clearances | `manufacturing.plan_assembly` computes removal directions and an assembly order from contacts; `_access_order_issues` checks tool access (150 mm behind screws); door gaps `DOOR_MIN_GAP` | cabinet | ✔ |
| Cutting sequence | Per part: engrave/pocket → inner cut-outs → outer profile (`generate_cut_paths`, `order`) | code | ✔ correct order; no hold-down tabs, lead-ins or small-part handling |
| Part labelling | Part id placed at the point furthest from any edge (`cutpaths.label_point`), sized to fit; in SVG/DXF | cabinet: 5 labels on sheet 1 | ✔ |
| Assembly instructions | Booklet section "Assembly sequence" from the joint graph or the assembly plan (`booklet.assembly_sequence`, `_plan_rows`) | cabinet booklet: 12 pages | ✔ textual; no exploded 3D steps |
| Bill of materials | `cutlist.cut_list`: finished vs blank size, grain, process, banding, drilling, identical-part grouping, totals per material (m², banding m) | cabinet | ✔ boards; ✘ **no purchased-hardware list** (hinges, screws, dowels by size/qty); counts exist only inside `manufacturing.summary` / `fasteners` |
| Manufacturing drawings | PDF booklet: 1:1 cutting templates with a 50 mm scale bar, one dimensioned page per part, feature/tab tables | cabinet: 30 KB, 12 pages | ✔ |
| Drawings match 3D | Same `Plate` geometry feeds booklet, SVG, DXF and 3D (03 §2) | consistency check | ✔ |

## 2. Process-model findings

**BUG-004 — Tooling model mismatch for wood boards (confirmed by code, high impact).**
For plywood, MDF, particle board, solid wood and hardboard the catalogue kerf is 3.2 mm (a panel-saw blade,
`manufacturing.py:41-53`). Every glue-free joint (tab_slot slots, finger notches, cross-lap notches) is an **internal or
re-entrant cut**, which a panel saw cannot make. In practice these parts are cut on a CNC router, where:
* the "kerf" is the bit diameter (commonly 6 mm, sometimes 3–8 mm), not 3.2 mm;
* every inside corner gets a radius equal to the bit radius, so a square tab does **not** seat in a square slot without
  dog-bone or T-bone relief.

The engine models neither. The cut list itself classifies every part with slots, notches or cut-outs as
`process: 'cnc'` (`cutlist.py:152`), yet the same 3.2 mm saw kerf is used to compensate those CNC paths. Result: an 18 mm plywood design reports `ready_for_production: true` while its
slots and fingers cannot be assembled when cut on a router. Laser-cut thin stock (default 3 mm birch, kerf 0.15) is not affected.

**BUG-002 — Negative cut radius (confirmed by running it).**
`cutpaths.py:120` computes `radius = diameter/2 − kerf/2` without a lower bound. A 3 mm hole in 18 mm plywood
(kerf 3.2) gives `radius = -0.1`, and the package still says `ready_for_production: true` (`scenarios.py` E12).
`FEATURE_TOO_SMALL` only checks diameter ≥ 1 mm and ignores kerf/tool size.

**R-5 — Friction-fit clearance vs real stock thickness (potential).**
Slots are cut to *nominal* thickness + clearance (0.1–0.2 mm), but the catalogue's own `thickness_tol` for plywood is
±0.5 mm (`manufacturing.py:40`). `thickness_tol` is only used to classify standard thicknesses
(`manufacturing.py:881`). A sheet at the top of its tolerance will not fit its slots. Common practice is to measure the
stock and set the thickness, or to provide a test-fit coupon. Neither is prompted or generated.

**R-6 — Fixed spacing.** Canvas designs always get `spacing: 6.0` (`canvas.py:1032-1044`). With a 6 mm router bit there is
no material left between parts, and with a 3.2 mm saw kerf it is fine. Spacing should derive from the tool.

**R-7 — Edge-margin values are laser-scale.** `min_edge_margin` 1.5 mm and `rec_edge_margin` 3 mm are applied to 18 mm
plywood as well. A 3 mm bridge beside a slot in 18 mm plywood is fragile under a router. The prompt partly covers this
("use ≥ the board thickness for furniture"), but the engine does not enforce it.

## 3. Nesting quality (measured)

| Design | Stock chosen | Sheets | Efficiency |
|---|---|---|---|
| 02 chair (5 parts, 18 mm) | 2440×1220 | 1 | 23.6 % |
| 03a table | 2440×1220 | 2 | 38.4 % |
| 04 bookshelf | 2440×1220 | 3 | 41.6 % |
| 05 cabinet | 2440×1220 | 2 | 42.0 % |
| 07 storage box (6 mm, 300×200 box) | 2440×1220 | 1 | 8.8 % |
| 10 wardrobe (staggered, 14 parts) | 2440×1220 | 5 | 63.9 % |

Observations:
* Low percentages for small products are mostly honest: one full stock sheet per product. There is no "remnant / partial sheet" or
  "order cut-to-size" option, and the canvas picks the full stock sheet even for a desktop box, where a laser-bed size would be realistic.
* The table needs 2 sheets at 38 %: bounding-box nesting with only 0°/90° rotation, and every part is laid out on its own rectangle. No part-in-part or true-shape nesting.
* The plywood grain constraint is honoured (`_allowed_rotations`). Grain is `info`-level when unspecified (`GRAIN_UNSPECIFIED`).

## 4. Production readiness verdict per area

| Area | Ready? | Why |
|---|---|---|
| Laser cutting thin sheet (≤ 6 mm, kerf ≤ 0.3) | **Conditionally yes** | Geometry, kerf offset, cut order, labels and templates are sound, apart from BUG-002 for tiny holes |
| CNC routing of furniture board | **No** | No tool model, no inside-corner relief, kerf value wrong for the process (BUG-004) |
| Panel saw / cabinet shop (butt + fasteners + hinges) | **Partly** | Rectangles, drilling, banding and hinge cups are modelled. Hardware BOM is missing |
| Documentation | Yes for drawings and cut lists | Hardware BOM and exploded assembly views missing |
