# 02 — Complex Product Structure Tests

**What was executed.** 18 products (`tests/e2e/products.py`) ran through the complete pipeline with `tests/e2e/run_e2e.py`,
first on the untouched engine (baseline, `e2e_results_baseline.json`) and again after the fixes (`e2e_results.json`).
**Source of the designs:** hand-written `board-design/v1` answers to each natural-language prompt, AI-style. They are
not Gemini output (no Gemini integration exists). Real AI-written designs are evaluated separately in 07.

Each case states its expected outcome before running. Unsupported products are expected to be **rejected**, not faked.
A case passes only if all of the following hold:
* compile result as expected;
* component count exact;
* production readiness as expected;
* the v1 source, native design, 3D model, nesting, cut paths, SVG, DXF and cut list agree (06);
* PDF/SVG/DXF exports generate;
* support status as expected.

## Results: baseline 11/18 → after fixes 18/18

| ID | Product | Categories | Boards / joints joined | Sheets · utilisation | Support | Ready | Baseline → After |
|---|---|---|---|---|---|---|---|
| E2E-01 | Serving board (profile, hole, engraving) | single-board, curved | 1 / 0 | 1 · 3.0 % | anchored | yes | PASS → PASS |
| E2E-02 | Three-column bookshelf, inferred joints | multi-board, compartments | 16 / 86 | 3 · 61.0 % | stable | **no → yes** | FAIL (BUG-019) → PASS |
| E2E-03 | Cabinet: hinged door + 2 drawers | compartments, removable, moving, nested | 18 / 47 | 3 · 51.8 % | 10 resting (drawers) | yes | FAIL (no support analysis) → PASS |
| E2E-04 | Chair (rigid version of a folding chair), 8° backrest | angled, moving | 5 / 8 | 1 · 23.6 % | stable | yes | PASS → PASS |
| E2E-05 | Computer desk: pedestal, drawer, hung tray, riser | asymmetric, compartments, removable | 16 / 41 | 2 · 65.1 % | 3 resting (drawer) | yes | FAIL (no support analysis) → PASS |
| E2E-06 | Stepped storage 1200/800/400 | asymmetric, compartments | 16 / 44 | 2 · 48.5 % | stable | yes | PASS → PASS |
| E2E-07 | Three-plate interlocking puzzle | complex joints | — | — | — | — | PASS → PASS (rejected: `JOINT_CUTS_INVALID`) |
| E2E-08 | Stackable modular cubes | modular, nested, removable | 8 / 8 | 1 · 39.1 % | upper cube resting | yes | FAIL (no support analysis) → PASS |
| E2E-09 | Electronics enclosure, vents, loose lid | removable, complex joints | 7 / 11 | 1 · 5.2 % | lid resting | yes | FAIL (no support analysis) → PASS |
| E2E-10 | Acoustic guitar | curved, unsupported | — | — | — | — | PASS → PASS (rejected: `NO_CONTACT`) |
| E2E-11 | Wooden boat (native example) | curved, angled | 14 / 32 | 1 · 46.8 % | stable | yes | PASS → PASS |
| E2E-12 | Punt, vertical sides | boat | 6 / 14 | 1 · 10.5 % | stable | yes | PASS → PASS |
| E2E-13 | Punt, flared sides | angled, unsupported | — | — | — | — | PASS → PASS (rejected: `NO_CONTACT`) |
| E2E-14 | Wall-mounted shelf, triangular brackets | hanging, angled | 4 / 5 | 1 · 9.9 % | wall-mounted | yes | PASS → PASS (now `mounting: wall`) |
| E2E-15 | Table with both legs at one end | hanging, unsupported structure | 4 / 6 | 1 · 50.4 % | **TIP_OVER, CANTILEVER** | yes | FAIL (no support analysis) → PASS |
| E2E-16 | Table + forgotten floating shelf | negative | 4 / 4 | — | **unsupported** | **yes → no** | FAIL (BUG-007) → PASS |
| E2E-17 | Stepped storage, shelves sharing a slot | negative | 16 / 40 of 44 | — | — | no | PASS → PASS (`SLOT_ALREADY_USED`) |
| E2E-18 | Enclosure, divider tab in a vent | negative | 7 / 10 of 11 | — | — | no | PASS → PASS (`TAB_IN_OPENING`) |

Utilisation is the area of all parts over the area of all sheets used (independently recomputed; see 05).
Low numbers are small products placed on full 2440 × 1220 stock.

## Per-product verification checklist

Checked by the harness for every product that compiles (13 of 18):

| Check | How | Result |
|---|---|---|
| All required components exist | v1 board ids = native ids = 3D ids = cut-list ids | ✔ all 13 |
| No duplicates | nesting places each id exactly once; `DUPLICATE_*` codes | ✔ |
| Correct dimensions / thickness | every unrotated board's 3D extent = its source box (±0.02 mm); finger joints may add up to the partner's thickness; thickness equal everywhere | ✔ |
| Correct orientation and position | world bounds of the 3D part = design placement (±0.01 mm) | ✔ |
| Hierarchy / parent-child | `group` per sub-assembly + joint graph; the support analysis gives each board a status and what it is joined to / rests on | ✔ derived; there is no explicit `parent` field (see note) |
| Assembly sequence | booklet assembly section and `manufacturing.assembly_plan` generated for all 13 | ✔ generated, not hand-verified per product |
| No disconnected components | [F] `UNSUPPORTED_COMPONENT` (E2E-16) | ✔ |
| No unsupported geometry | guitar, flared punt, three-plate puzzle rejected with a specific code | ✔ |

**Hierarchy note.** The format has no `parent` field. Product → group → board is the structure, and the physical
parent-child relation is the joint graph plus "rests on" contacts, which the support report exposes per board
(`components[id].joined_to / rests_on`). An explicit parent field was **not** added: nothing consumes it, and the
joint graph already defines the relation unambiguously.

## Authoring mistakes the engine caught

My first drafts of the corpus contained four realistic mistakes. Each was rejected with a precise message, which is
evidence that the validator works:

| Draft | Engine response |
|---|---|
| Desk modesty panel 32 mm below the top | `CONNECTION_GAP` "'MODESTY' stops 32.00 mm short of 'TOP'" |
| Stepped storage: equal shelf heights both sides of a shared panel | `SLOT_ALREADY_USED` ×6 (kept as negative test E2E-17) |
| Enclosure: divider tab under a vent | `TAB_IN_OPENING` (kept as E2E-18) |
| Desk: leg below and riser above the top at adjacent x | `SLOT_ALREADY_USED` + `COLLISION` → the "opposite sides" rule was widened in the prompt |

## Product categories the format cannot represent (verified rejections)

| Category | Example | Why | Engine response |
|---|---|---|---|
| Bent / curved-in-3D | Guitar ribs, boat hull | Boards are flat prisms | rejected |
| Laminated / face-to-face | Guitar neck on body | no parallel-face joint in v1 | `NO_CONTACT` |
| Bevelled meeting | Flared punt | no bevelled tab_slot | `NO_CONTACT` |
| Three-way interlock | Three-plate puzzle | halving notches split a board | `JOINT_CUTS_INVALID` |
| Moving mechanisms | Folding chair, sliding drawers | no pivot or slide joints; drawers drawn as resting boxes | modelled statically |
