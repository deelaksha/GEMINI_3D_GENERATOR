# Engineering Audit, 2026-11-28: index

A read-only audit of the working tree at HEAD `616b135`, including its uncommitted edits. No existing project file was modified. Everything is in this folder.

| Document | Contents |
|---|---|
| [ENGINEERING_AUDIT_REPORT.md](ENGINEERING_AUDIT_REPORT.md) | Architecture as built, lifecycle trace with information-loss points, findings F-01..F-24, answers per audit section, scorecard |
| [PROMPT_ENGINEERING_AUDIT.md](PROMPT_ENGINEERING_AUDIT.md) | Every prompt measured; findings P-01..P-24 with exact text and replacements; proposed 3-call prompt architecture |
| [MECHANICAL_ENGINEERING_GAP_ANALYSIS.md](MECHANICAL_ENGINEERING_GAP_ANALYSIS.md) | Mechanism capability matrix, findings M-01..M-17, kinematic-graph design, acceptance table |
| [TEST_EXECUTION_REPORT.md](TEST_EXECUTION_REPORT.md) | Baseline (671 + 5 passing), corpus, product, mechanical and negative tests, prompt sizes, scaling 50–5,000 boards, NOT TESTED items |
| [ARCHITECTURE_IMPROVEMENT_PLAN.md](ARCHITECTURE_IMPROVEMENT_PLAN.md) | Target pipeline, mapping of the 16 suggested stages, phased roadmap, risks, acceptance criteria |
| [CODER_AI_IMPLEMENTATION_PROMPT.md](CODER_AI_IMPLEMENTATION_PROMPT.md) | Standalone implementation brief for a coding agent: phases, files, line numbers, tests, definition of done |
| `evidence/` | Specialist reports (`*/..._audit.md`), every probe design (JSON), scripts, raw outputs |

The `evidence/` folder holds four specialist reports:
- `prompt/prompt_audit.md`
- `geometry/geom_audit.md`
- `mechanical/mech_audit.md`
- `pipeline/pipe_audit.md`

The findings from these reports are consolidated in the documents above. The main report marks which findings were re-run independently (R).

**Important limitation:** no LLM was called (no API key, no paid usage approved), so the quality of AI generation with the current prompt is **unmeasured**. The AI transport failure modes were tested with offline stubs.
