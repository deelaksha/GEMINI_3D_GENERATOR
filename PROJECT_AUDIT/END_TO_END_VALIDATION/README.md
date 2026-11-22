# End-to-End Validation — index

Baseline `bf1f44b` → fixes in the working tree (not committed). Every number comes from an executed run; the result
files are in this folder, with `test_results.json` as the machine-readable summary. AI-generated designs come from
isolated **Claude** agents (there is no Gemini integration). The product corpus is hand-written, AI-style.

| File | Topic |
|---|---|
| [01_PIPELINE_ANALYSIS.md](01_PIPELINE_ANALYSIS.md) | stage-by-stage trace, dependency map |
| [02_COMPLEX_PRODUCT_TESTS.md](02_COMPLEX_PRODUCT_TESTS.md) | 18 products, baseline 11/18 → 18/18 |
| [03_JOINT_VALIDATION.md](03_JOINT_VALIDATION.md) | 16 joint families, 11 negative scenarios |
| [04_SUPPORT_AND_HANGING_ANALYSIS.md](04_SUPPORT_AND_HANGING_ANALYSIS.md) | new support analysis, 10 scenarios |
| [05_CUTTING_AND_NESTING_VALIDATION.md](05_CUTTING_AND_NESTING_VALIDATION.md) | 14 nesting cases, waste arithmetic |
| [06_2D_3D_CONSISTENCY.md](06_2D_3D_CONSISTENCY.md) | five representations, edit propagation |
| [07_PROMPT_UPDATE_ANALYSIS.md](07_PROMPT_UPDATE_ANALYSIS.md) | prompt v2, old vs new AI runs, repair/update rounds, versions |
| [08_EDGE_CASE_AND_FAILURE_TESTS.md](08_EDGE_CASE_AND_FAILURE_TESTS.md) | 29 failure injections |
| [09_PERFORMANCE_AND_HANG_ANALYSIS.md](09_PERFORMANCE_AND_HANG_ANALYSIS.md) | hangs, time budget, cost |
| [10_REGRESSION_TEST_RESULTS.md](10_REGRESSION_TEST_RESULTS.md) | before/after for every suite |
| [11_BUG_TRACKER.md](11_BUG_TRACKER.md) | 30 items: 15 fixed, 1 mitigated, 2 documented, 12 open |
| [12_PRODUCTION_READINESS.md](12_PRODUCTION_READINESS.md) | verdict and remaining steps |
