# 04 — Support and Hanging Analysis

## 1. Baseline: there was no support analysis

At `bf1f44b` the only related check was `FLOATING_COMPONENT` (`validation.py:1450`), a **warning** that a board has no
*joint* path to the largest joined group. It could not tell:
* a lid resting on a box from a board floating in mid-air (both "floating"), so production allowed both (BUG-007);
* whether a product tips over;
* whether a shelf hangs off one side.

## 2. What was implemented — `board_engine/support.py` [F]

`support_report(design)` is a deterministic analysis, used by the canvas compiler and `views.production_package`:

| Concept | Rule |
|---|---|
| Anchors | `mounting: "floor"` (default): boards touching the lowest y. `mounting: "wall"`: boards touching the back plane (lowest z) |
| joined | reachable from an anchor through **joined** joints |
| resting | not joined, but lies **on top of** a held board (undeclared face/edge contact with a vertical normal, upper board above), plus everything joined to it, e.g. a drawer box |
| unsupported | none of the above → `UNSUPPORTED_COMPONENT` **error**, which blocks production |
| Tip-over (floor) | centre of mass (area × thickness, uniform density, cut-outs subtracted) must lie inside the convex hull of the floor contact → else `TIP_OVER` warning; `LOW_STABILITY_MARGIN` info under 5 % of the footprint |
| Cantilever | a horizontal non-anchored board whose centre lies outside the area where its supporting boards meet it → `CANTILEVER` warning; for a **resting** board (no joint holds it) → `RESTING_OFF_SUPPORT` **error** (it falls off) |
| Wall | `WALL_MOUNTED` info naming the boards that need wall fixings (not designed or checked) |

Schema: an optional `mounting` field on the native design (`model._mounting`; stored only when given, so existing
designs are unchanged) and `product.mounting` in `board-design/v1`. Consumers traced: `normalize_design`,
canvas, support, prompt spec, docs, and the field-documentation test (`COMPILER_FIELDS`).

**Geometric connectivity is not structural strength.** The report carries this disclaimer and every message avoids
load claims: *"Geometric support and static tip-over check only (rigid boards, uniform density). Structural strength,
joint capacity and loads are not assessed."*

## 3. Scenario results (`tests/e2e/support_matrix.py` → `support_matrix.json`, 9/10)

| ID | Scenario | Result | Pass |
|---|---|---|---|
| SP-01 | Wall-mounted shelf, `mounting: wall` | `WALL_MOUNTED`, no tip-over | ✔ |
| SP-02 | Same shelf without `mounting` | `TIP_OVER` (stood on the bracket tips it cannot stand) | ✔ (shows why the field exists) |
| SP-03 | Suspended wall cabinet with a hinged (hanging) door | door `joined`, cabinet wall-anchored, compiles | ✔ |
| SP-04 | Loose box / drawer standing on a shelf | `resting`, production allowed | ✔ |
| SP-05 | Both legs at one end of a 1200 mm top | `TIP_OVER` + `CANTILEVER`, stable = false, margin −98 mm | ✔ |
| SP-06 | Top overhanging each leg by 100 mm | stable, no warnings | ✔ |
| SP-07 | Horizontal board in mid-air | `UNSUPPORTED_COMPONENT` error | ✔ |
| SP-08 | Vertical board hanging under the top by tabs | `joined` | ✔ (whether the tabs carry the load is **not** assessed) |
| SP-09 | Plank resting on the top, ⅔ over the edge | `RESTING_OFF_SUPPORT` error | ✔ (was a warning in the first version of this analysis; made an error because nothing holds a resting part) |
| SP-10 | Board attached by a single 80 mm hanger / one tab | compiles, **no warning** | ✘ open gap S-1: no single-attachment / weak-attachment check |

Corpus evidence (02): drawers, stacked modules and lids are `resting` (E2E-03/05/08/09); the cantilever table tips
(E2E-15); the floating shelf is now blocked (E2E-16); the wall shelf is accepted as wall-mounted (E2E-14).

## 4. Can each component be assembled?

Assembly feasibility is the existing `manufacturing.plan_assembly()`. It computes a removal order from the contact
graph with free directions per joint type, and reports locked groups. It ran for every compiled product (the booklet
contains the sequence). It was not changed and not independently verified product by product.

## 5. Open items

| ID | Gap | Proposal |
|---|---|---|
| S-1 | No single-point / weak-attachment check (SP-10) | Count distinct load paths per board and the total tab width; warn below a threshold, worded as a geometric hint |
| S-3 | Uniform density for all materials | Use per-material density if mixed materials matter |
| S-4 | No load cases, joint capacity or racking | Out of scope without engineering data; never implied by the UI |
