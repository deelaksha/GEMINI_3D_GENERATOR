# 10 — Regression Test Results

Machine-readable summary of everything below: **`test_results.json`** (plus the per-suite JSON files listed in §3).

## 1. Before / after

| Suite | What it runs | Baseline (`bf1f44b`) | After | Kind |
|---|---|---|---|---|
| pytest `tests/python` | unit, API, integration, regression | 300 pass, 4 fail (harness: `#` in path) | **369 pass, 0 fail** | executed |
| Product corpus `tests/e2e/run_e2e.py` | 18 products, full pipeline + 2D/3D + exports | 11 / 18 | **18 / 18** | executed (hand-written designs) |
| Joint matrix `joint_matrix.py` | 18 positive + 11 negative joint scenarios | 29 / 29 | 29 / 29 | executed |
| Failure injection `edge_cases.py` | 29 cases through the HTTP API | 25 pass, 2 fail, 2 n/a | **27 pass, 0 fail**, 2 n/a | executed (2 not applicable / not executed) |
| Support matrix `support_matrix.py` | 10 hanging / support scenarios | — (no analysis existed) | 9 / 10 (SP-10 open gap) | executed |
| Nesting `nesting_cases.py` | 14 cutting / nesting edge cases | NS-05 fails (negative radius) | 12 pass, 2 not implemented | executed |
| Propagation `propagation.py` | one edit → 3D, 2D, cut list, SVG, DXF | pass | pass | executed |
| Browser `browser_smoke.py` (headless Chrome) | Studio/Canvas load, compile, edit-during-compile, Ctrl-S | 3 / 5 | **5 / 5** | executed |
| AI prompt comparison | 4 products × old/new prompt + repair/update rounds | old: 1/4 ready on first attempt | new: 3/4 ready on first attempt | executed with Claude agents, **not Gemini** |

## 2. Regression tests for every confirmed bug — shown to fail on the old code

The new test files were copied into a clean checkout of `bf1f44b` and run there
(`regression_tests_on_baseline.txt`): **35 failed, 25 passed**. On the fixed tree, all of them pass. The 25 that pass on the
baseline are controls (e.g. a hole larger than the kerf) and checks of engine behaviour the prompt now documents.

| Bug | Regression test(s) | Fails on baseline |
|---|---|---|
| BUG-002 sub-kerf hole → negative radius | `test_bug002_feature_smaller_than_kerf_is_rejected` | ✔ |
| BUG-003 long ids crash | `test_bug003_long_board_ids_compile[*]` (8 cases) | ✔ 8/8 |
| BUG-006 unsafe "safe" fix | `test_bug006_no_safe_cross_lap_fix_for_a_profiled_board` | ✔ |
| BUG-007 floating parts ready / resting parts | `test_bug007_unsupported_board_blocks_compile_and_production`, `test_bug007_resting_lid_is_allowed_and_reported` | ✔ |
| BUG-008 set_material no-op | `test_bug008_set_material_thickness_reaches_canvas_boards` | ✔ |
| BUG-009 errors without location | `test_bug009_connection_option_error_names_the_connection` | ✔ |
| BUG-012 edit dropped during compile | browser BR-04 | ✔ (baseline status "Compiled · 11 boards" for stale text) |
| BUG-013 Ctrl-S duplicates | browser BR-05 | ✔ (3 projects created) |
| BUG-015 `#` in path | the 4 existing `test_slot_and_kerf_match_js_profile` cases | ✔ |
| BUG-019 sheet too small | `test_bug019_auto_sheet_fits_a_1200_mm_back_panel`, corpus E2E-02 | ✔ |
| BUG-020 detached joints ready | `test_bug020_detached_connections_block_production` | added after the baseline run; the scenario is the old-prompt bookshelf, which was "ready" with 12 detached joints |
| Support analysis | 5 tests + corpus E2E-03/05/08/09/15/16 | ✔ |
| Time budget | `test_time_budget_stops_compile_with_a_clear_diagnostic`, edge case EC-26 | ✔ |
| Versions / restore | `test_versions_list_get_and_restore`, `test_firestore_store_keeps_versions` | ✔ |
| Prompt rules | `tests/python/test_prompt_upgrade.py` (16) | 5 fail on baseline (new text / builders); the engine-claim tests pass on both, as intended |

BUG-010 (expected_revision) and BUG-011 (atomic re-join) are verified at API level (EC-21, EC-23). The UI changes were
syntax-checked and exercised by BR-01…05, but not by a dedicated browser test for a conflict or a failed re-join (open).

## 3. Result files

| File | Content |
|---|---|
| `test_results.json` | combined summary (all suites, per-case corpus rows, AI scores) |
| `e2e_results_baseline.json`, `e2e_results.json` | full records per product: prompt, AI response (design JSON), compiled design, counts, validation, collisions, support, cutting, consistency, exports, duration, failures |
| `joint_matrix_baseline.json`, `joint_matrix.json` | joint scenarios |
| `edge_cases_baseline.json`, `edge_cases.json` | failure injection |
| `support_matrix.json`, `nesting_cases.json`, `propagation.json` | Phases 4, 5, 6 |
| `browser_baseline.json`, `browser_after.json` | headless Chrome runs |
| `regression_tests_on_baseline.txt` | new tests run against the old code |
| `ai_prompt_comparison.json`, `ai_runs/` | AI experiment (prompts, answers, follow-ups, scores) |
| `pytest_final.txt` | last full pytest summary line |

## 4. How to re-run

```bash
pip install -r requirements.txt
python -m pytest tests/python -q                         # includes the corpus and joint matrix as tests
python tests/e2e/run_e2e.py                              # writes e2e_results.json
python tests/e2e/edge_cases.py > edge_cases.json         # and joint_matrix / support_matrix / nesting_cases / propagation
pip install playwright && python tests/e2e/browser_smoke.py   # optional, uses the local Chrome
python tests/e2e/score_ai_outputs.py <dir-with-AI-json> ...   # score AI answers
```

**Simulated / not verified:** no physical cutting or assembly was performed. Every manufacturing result is the
engine's own verdict, and the CNC tooling gap (BUG-004) means that verdict is optimistic for router-cut board.
