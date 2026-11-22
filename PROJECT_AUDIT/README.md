# Project Audit — index

Read-only audit of commit `bf1f44b` (2026-11-22). No existing source file was modified; everything is in this folder.

| File | Contents |
|---|---|
| [01_ARCHITECTURE_ANALYSIS.md](01_ARCHITECTURE_ANALYSIS.md) | System map, workflow trace, two app generations, storage/auth. **Note: no Gemini API integration exists** |
| [02_AI_GENERATION_ANALYSIS.md](02_AI_GENERATION_ANALYSIS.md) | Prompt pipeline, 20 AI-failure inputs, hallucination classes |
| [03_GEOMETRY_GAP_ANALYSIS.md](03_GEOMETRY_GAP_ANALYSIS.md) | Geometry checks, verified 2D = 3D parity, unsupported geometry |
| [04_MANUFACTURING_VALIDATION.md](04_MANUFACTURING_VALIDATION.md) | Kerf, tooling, nesting yield, BOM, drawings |
| [05_UI_AND_EDITOR_ANALYSIS.md](05_UI_AND_EDITOR_ANALYSIS.md) | Editor capability matrix, edit propagation, frontend defects |
| [06_REAL_WORLD_SCENARIOS.md](06_REAL_WORLD_SCENARIOS.md) | 10 products compiled and evaluated |
| [07_PERFORMANCE_AND_RELIABILITY.md](07_PERFORMANCE_AND_RELIABILITY.md) | Timings, profile hot spot, failure conditions |
| [08_AUTOMATED_TEST_PLAN.md](08_AUTOMATED_TEST_PLAN.md) | Coverage today, strategy, 17 reproducible test cases |
| [09_BUG_AND_ISSUE_TRACKER.md](09_BUG_AND_ISSUE_TRACKER.md) | 18 confirmed bugs + PERF-001, 10 feature gaps, risks |
| [10_PRODUCTION_READINESS.md](10_PRODUCTION_READINESS.md) | Verdict per component and phased roadmap |
| [11_PROMPT_UPGRADE.md](11_PROMPT_UPGRADE.md) | Upgraded AI prompt text (evidence-backed) + repair prompt |

## Reproduce

```bash
pip install -r requirements.txt
python -I PROJECT_AUDIT/repro/scenarios.py "$PWD"     # 10 products + 20 edge cases → JSON (matches repro/scenario_results.json)
python -I PROJECT_AUDIT/repro/probes.py "$PWD"        # fixes, staggering, desk redesign, determinism, face joints
python -I PROJECT_AUDIT/repro/consistency.py "$PWD"   # 2D vs 3D parity + egg-crate scale timings (~4 min)
python -m pytest tests/python -q                      # 300 pass, 4 fail only because the path contains '#'
```
