# 08 — Edge Cases and Failure Injection

Executed through the real HTTP API with the Flask test client and a throw-away instance directory
(`tests/e2e/edge_cases.py` → `edge_cases_baseline.json`, `edge_cases.json`). `./instance` was never touched: every run
used `tempfile.mkdtemp()`, removed afterwards. Browser-level failures: `tests/e2e/browser_smoke.py` (07/10).

**Summary: baseline 25 pass / 2 fail / 2 not applicable → after 27 pass / 0 fail / 2 not applicable.**

| ID | Injected failure | Response | Baseline | After |
|---|---|---|---|---|
| EC-01 | Empty prompt | 400 `invalid_request` | ✔ | ✔ |
| EC-02 | 1.2 MB requirements | 200; requirements silently cut to 4000 chars (prompt 32.9 k) | ✔ | ✔ (silent truncation noted) |
| EC-03 | Prose instead of JSON | `JSON_SYNTAX` | ✔ | ✔ |
| EC-04 | Malformed JSON | `JSON_SYNTAX` with line/column | ✔ | ✔ |
| EC-05 | Partial generation (response cut in half) | `JSON_SYNTAX` | ✔ | ✔ |
| EC-06 | Missing required field (`boards`) | `NO_BOARDS` | ✔ | ✔ |
| EC-07 | Missing dimensions | `BOARD_GEOMETRY` | ✔ | ✔ |
| EC-08 | Negative dimensions | `BOARD_SIZE` | ✔ | ✔ |
| EC-09 | Zero thickness | `MATERIAL_THICKNESS` | ✔ | ✔ |
| EC-10 | 0.3 mm material | `MATERIAL_THICKNESS` | ✔ | ✔ |
| EC-11 | 8 m board | `BOARD_SIZE` | ✔ | ✔ |
| EC-12 | Duplicate ids | `DUPLICATE_BOARD_ID` | ✔ | ✔ |
| EC-13 | Missing component reference | `UNKNOWN_BOARD` (+ "did you mean") | ✔ | ✔ |
| EC-14 | Self reference | `SELF_CONNECTION` | ✔ | ✔ |
| EC-15 | Circular pair (A→B and B→A) | duplicate ignored with `DUPLICATE_CONNECTION`, compiles | ✔ | ✔ |
| EC-16 | Unsupported material `steel` | `MATERIAL_TYPE` | ✔ | ✔ |
| EC-17 | 3000-point profile | `PROFILE_INVALID` (max 2048 points) | ✔ | ✔ |
| EC-18 | Unexpected properties | compiles; unknown fields **silently ignored** | ✔ | ✔ (noted as open E-1) |
| EC-19 | 3.5 MB JSON | 413 (2 MB request limit) | ✔ | ✔ |
| EC-20 | Same source compiled 3× | identical summary and diagnostics | ✔ | ✔ |
| EC-21 | Concurrent edit with `expected_revision` | second request 409 `conflict` | ✔ | ✔ |
| EC-22 | Concurrent edit without revision | accepted (last write wins) | ✔ | ✔ ([F] the Studio now sends the revision) |
| EC-23 | Batch failing at step 2 | 404, stored design **unchanged** (no partial write) | ✔ | ✔ |
| EC-24 | Export of a non-existent sheet | 400, no file | ✔ | ✔ |
| EC-25 | Export of a design with a floating board | **baseline: 200 + DXF file** | ✘ | ✔ 409 `not_ready_for_production` |
| EC-26 | Expensive collision check, 5 s budget | **baseline: no budget, ran to completion** | ✘ | ✔ `COMPILE_TIMEOUT` at 5.0 s |
| EC-27 | API rate limit 5/min | 200 ×5 then 429 | ✔ | ✔ |
| EC-28 | Gemini timeout / rate limit / network | **not applicable**: the app never calls Gemini | — | — |
| EC-29 | Browser refresh during generation | **not executed** (drafts autosave to localStorage, `js/canvas/main.js:142`) | — | — |

## Failure properties

| Property | Evidence |
|---|---|
| No application crash | No 500 in any case; `compile_source` never raises; [F] `COMPILER_ERROR` for long ids fixed (BUG-003) |
| No corrupted design | EC-23 (all-or-nothing batch); atomic `os.replace` writes; [F] time budget raises before any write |
| No silent data loss | ✘ two remain: requirement text over 4000 chars and unknown JSON fields are dropped without a message (E-1, E-2) |
| Clear error messages | every case returns a code plus a message naming the board, connection or line |
| Safe recovery / retry | 409 and 429 are retryable; [F] the Studio reloads and asks the user to repeat on 409; [F] versions + restore |
| No invalid production files | [F] EC-25, BUG-002 (no negative radius), BUG-020 (detached joints block export) |

## Open

* **E-1**: unknown fields in AI JSON are dropped silently. Proposal: one info diagnostic listing them, so the AI learns.
* **E-2**: requirements are truncated to 4000 characters without telling the user.
* **E-3**: Firestore network failures surface as 500 `FirestoreError`. Not injected (no Firestore credentials in this environment).
