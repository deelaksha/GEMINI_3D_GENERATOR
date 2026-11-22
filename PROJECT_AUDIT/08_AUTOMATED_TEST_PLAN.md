# 08 — Automated Test Plan

## 1. Current coverage (measured)

| Suite | Tests | Scope | Result today |
|---|---|---|---|
| `tests/python/test_geometry_validation.py` | 32 | 2D part checks, joints, collisions | pass |
| `tests/python/test_real_world.py` | 34 | Furniture generators, large rack | pass |
| `tests/python/test_gap_detection.py` | 25 | Gaps, near-miss, slot/kerf vs legacy JS | **4 fail** (BUG-015, harness only) |
| `tests/python/test_complex_structures.py` | 25 | Finger, cross-lap, the 4 real AI fixtures, prompt claims | pass |
| `tests/python/test_canvas.py` | 19 | Canvas parse/compile/fix/save/import, perf (6.3 s large design) | pass |
| `tests/python/test_complex_cuts.py` | 17 | Profiles, shaped openings, engravings, tilt; spec documents every field | pass |
| `tests/python/test_operations_production.py` | 15 | Operations, nesting, cut paths, exports | pass |
| `tests/python/test_api.py` | 11 | REST auth/roles, CRUD, exports | pass |
| `tests/python/test_autofix.py`, `test_fit_audit.py`, `test_firestore_store.py`, `test_e2e_agent.py` | 7+7+4+2 | Auto-fix, fit audit, Firestore (mocked), API agent E2E | pass |
| `tests/joint_fit_suite.mjs` | 47 checks | **Legacy JS only** | pass |
| Browser / UI | 0 | — | none |

Total: 304 collected, 300 pass in 77 s. Strong unit and integration coverage of the engine. **No browser tests, no tests for the
Studio/Canvas JS, no performance budget tests beyond one 6.3 s case, no security tests for the legacy stack.**

## 2. Strategy

| Layer | Tooling (no new framework unless noted) | What to add |
|---|---|---|
| Unit | pytest (existing) | Regression tests for every confirmed bug in §3 |
| AI-output validation | pytest + JSON corpus | Keep every real AI reply (pass or fail) under `tests/python/fixtures/ai/` with the model name, prompt hash and date; assert compile result and diagnostic codes. Grow the corpus from production paste logs (opt-in) |
| Prompt contract | pytest (existing pattern in `test_complex_cuts.py:253`) | Every rule in the prompt has a test proving the engine behaves that way, including the new "unsupported" rules (11) |
| Geometry invariants | pytest property tests (Hypothesis is optional; a seeded random generator is enough) | For random valid box layouts: 2D part areas = 3D part areas; every joined tab inside its slot; no collisions after successful compile; compile(x) == compile(x) |
| Manufacturing | pytest | Kerf offset never inverts a feature; every cut path closed and non-self-intersecting; a tool-diameter model once added (dog-bones present at every inside corner ≤ 90°) |
| API | pytest + Flask test client (existing) | Ownership and authz once added; `expected_revision` conflicts; canvas endpoints under size and time limits |
| Integration / E2E | Playwright (**new; justified**: no browser coverage exists and the `__studioReady`/`__canvasReady` hooks are already in place) | Canvas: paste → compile → fix → save → open in studio; Studio: move → joint detach dialog → re-join → export PDF |
| Performance | pytest with time budgets (marker `@pytest.mark.perf`) | Grid 6×6 < 5 s, bookshelf auto < 2 s, collision pairs/sec floor |
| Security | pytest + Playwright | Legacy `?model=` loading must not execute code from Firestore; XSS payload in design names |
| CI | Not present in repo | Add a workflow running pytest + node suite; quote the repo path or URL-encode it in tests (BUG-015) |

## 3. Reproducible test cases from this audit (expected vs actual)

All run with `python -I PROJECT_AUDIT/repro/scenarios.py <repo>` unless stated otherwise.

| TC | Input | Expected | Actual (commit `bf1f44b`) | Bug |
|---|---|---|---|---|
| TC-01 | E11: two boards with 40-char ids, `connections: "auto"` | Compiles, or a clear id-length diagnostic | `COMPILER_ERROR: TypeError: unsupported operand type(s) for +: 'NoneType' and 'int'` | BUG-003 |
| TC-02 | E12: Ø3 mm hole in 18 mm plywood, kerf 3.2 | Error `FEATURE_SMALLER_THAN_TOOL` (or similar); not ready | cut circle `radius = -0.1`, `ready_for_production: true` | BUG-002 |
| TC-03 | E15: extra board unconnected | Blocks production, or requires explicit `"loose": true` | ok=true, ready=true, warning only | BUG-007 |
| TC-04 | E07: `overall.length` 1500, boards span 1200 | Error, or requirement-mismatch blocks production | ok=true, warning only | BUG-007 |
| TC-05 | E13: hinge `count: 12` | Diagnostic naming connection `door` and its source line | `SCHEMA_ERROR joint.count must be an integer 1..8`, no connection, no line | BUG-009 |
| TC-06 | 09-toy-car, apply first `safe` fix | Safe fixes never introduce a new error | `JOINT_NEEDS_PLAIN_BOARD` | BUG-006 |
| TC-07 | 10-wardrobe, shelves at equal heights both sides of divider | Prompt warns, or engine offers a stagger / blind-slot fix | `SLOT_ALREADY_USED` ×6 + `COLLISION`, no fix offered | BUG-005 |
| TC-08 | Compile EXAMPLE, then `set_material {thickness: 15}` | Parts follow the new thickness, or op rejected | success, material 15 mm, all parts still 18 mm, valid | BUG-008 |
| TC-09 | 18 mm plywood part with slots: cut path inside corners | Inside corners relieved for tool radius | sharp corners; `process: 'cnc'` but kerf 3.2 saw value | BUG-004 |
| TC-10 | `pytest tests/python/test_gap_detection.py -k js_profile` in a path containing `#` | pass | 4 × `ERR_MODULE_NOT_FOUND` | BUG-015 |
| TC-11 | `consistency.py`: 2D nested outline area vs 3D `cut_outline` area, hole counts | equal | equal within 0.03 mm² rounding (pass) | — |
| TC-12 | Compile bookshelf twice | identical design | identical (pass) | — |
| TC-13 | 03b leg-height mistake, apply first fix per error repeatedly | converges to ok | converges to ok (pass) | — |
| TC-14 | 16×16 egg-crate grid | < 30 s | 44.6 s (8×8: 6.3 s; corrected from a tracemalloc-inflated 54 s) | PERF-001 |
| TC-15 | Studio: Re-join where join fails (Playwright) | joint unchanged | joint deleted | BUG-011 |
| TC-16 | Canvas: type during a running compile (Playwright) | latest text compiled | edit dropped; pill shows "Compiled" | BUG-012 |
| TC-17 | Legacy: Firestore `designs/x` with `jsCode` containing `fetch('/api/v1/designs',{method:'DELETE'...})`; open `/inspector?model=x` (**test project only**) | code not executed | executed in app origin (by code reading; not run against live Firestore) | BUG-001 |

## 4. Regression gates

1. All of §3 become pytest/Playwright tests (TC-01…TC-10 are pure pytest).
2. CI fails on any new `COMPILER_ERROR` across the scenario corpus.
3. Perf gate: the scenario corpus compiles under a total budget (current total for the 10 products: < 10 s).
