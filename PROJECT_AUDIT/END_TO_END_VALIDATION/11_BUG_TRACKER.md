# 11 — Bug Tracker (end-to-end validation)

Continues `PROJECT_AUDIT/09_BUG_AND_ISSUE_TRACKER.md` (same ids). Status: **Fixed** (code changed, regression test
passes, test fails on the old code), **Open**, **Documented** (behaviour kept, prompt / docs explain it).

## Confirmed bugs

| ID | Sev | Title | Status | Fix (files) | Regression evidence |
|---|---|---|---|---|---|
| BUG-001 | S1 | Legacy pages execute JS from a world-writable Firestore collection | **Open** | needs a product decision (lock the rules / retire legacy pages) | — |
| BUG-002 | S1 | Hole smaller than the kerf → negative cut radius, "ready" | **Fixed** | `validation.validate_component` (`FEATURE_SMALLER_THAN_KERF`), `cutpaths.generate_cut_paths` (`CUT_PATH_DEGENERATE`) | test_bug002, NS-05 |
| BUG-003 | S2 | Long board ids crash the compiler | **Fixed** | `canvas._fit_id()` for every derived id; fallback label no longer uses `_i = None` | test_bug003 ×8 |
| BUG-004 | S1 | No CNC tool model / dog-bones; saw kerf on CNC cuts | **Open** | needs a process model | — |
| BUG-005 | S2 | Two tabs needing one through-slot; prompt silent | **Documented** | prompt rule (≥ 60 mm offset, both sides and above/below); engine rejects clearly | test_claim_boards_tabbing…, E2E-17 |
| BUG-006 | S2 | "Safe" cross-lap fix for boards cross-lap cannot join | **Fixed** | `canvas._cross_lap_cuttable()` | test_bug006 |
| BUG-007 | S2 | Floating boards reach production | **Fixed** | `support.py`; `UNSUPPORTED_COMPONENT` blocks compile and production; resting parts allowed | test_bug007 ×2, E2E-16, EC-25 |
| BUG-007b | S2 | `overall` dimension conflicts are only a warning | **Open** | product decision (warning kept) | E07 |
| BUG-008 | S2 | `set_material` thickness silently ignored on canvas designs | **Fixed** | `operations.op_set_material`: boards at the old stock thickness follow; broken joints rejected / detached | test_bug008 |
| BUG-009 | S3 | Out-of-range connection fields → `SCHEMA_ERROR` without location | **Fixed** | `canvas._compile_v1`: `CONNECTION_INVALID` / `BOARD_INVALID` with id + line | test_bug009 |
| BUG-010 | S2 | Studio never sends `expected_revision` | **Fixed** | `js/studio/main.js` (move/rotate, re-join), 409 → reload + message | EC-21 (API); UI syntax-checked |
| BUG-011 | S3 | Re-join not atomic | **Fixed** | `js/studio/api.js operations()`, `main.js` uses one batch | EC-23 (batch is all-or-nothing) |
| BUG-012 | S3 | Canvas drops edits made during a compile; stale "Compiled" | **Fixed** | `js/canvas/main.js compile()` queues a re-compile; phase-1 status guarded | browser BR-04 (fails on baseline) |
| BUG-013 | S3 | Ctrl/Cmd-S always creates a new project | **Fixed** | `js/canvas/main.js` extraKeys | browser BR-05 (3 → 1 project) |
| BUG-014 | S2 | Legacy XSS sinks | **Open** | legacy stack untouched | — |
| BUG-015 | S4 | 4 tests fail when the path contains `#` | **Fixed** | `tests/python/test_gap_detection.py` uses `Path.as_uri()` | 4 tests pass |
| BUG-016 | S2 | Every visitor is an editor; no ownership | **Open** | product decision | — |
| BUG-017 | S3 | Kerf compensation turns some DXF arcs into polylines | **Open** | — | — |
| BUG-018 | S4 | `apply_code_fix` loses comments/format | **Open** | — | — |
| BUG-019 | S2 | Canvas sheet choice ignores nesting allowances; falls back to a too-small sheet | **Fixed** (new) | `canvas._auto_sheet` measures the cut profile, same allowances as nesting, largest-stock fallback | test_bug019, E2E-02 |
| BUG-020 | S1 | Design with failed (detached) connections reported ready for production | **Fixed** (new) | `views.production_package` blocks on `JOINT_NOT_JOINED` | test_bug020; found via the old-prompt AI bookshelf |
| BUG-021 | S3 | No client timeout on Studio requests: UI could wait forever | **Fixed** (new) | `js/studio/api.js` default 150 s | code review; server budget answers first |
| BUG-022 | S3 | Canvas "update saved project" reset the revision to 1 (history lost) | **Fixed** (new) | `routes.canvas_save` uses `store.mutate` | test_versions_list_get_and_restore |
| BUG-023 | S3 | Repair prompt (new in this work) truncated the problem list at 40 lines | **Fixed** (new) | `canvas_prompt._problem_lines` groups repeats | AI round 2 failed → round 3 passed; test_repair_prompt_groups… |
| BUG-024 | S4 | Studio requests `/favicon.ico` → 404 console error | **Open** (cosmetic) | add an icon link | browser run |
| PERF-001 | S3 | Collision sampling super-linear (16×16 grid 45 s) | **Mitigated** | time budget (`deadline.py`); analytic path open | EC-26 |

## Feature gaps and findings (not bugs)

| ID | Item | Status |
|---|---|---|
| GAP-01 | No face-to-face joint in v1 | Open; documented in the prompt |
| GAP-02 | No bevelled joints (flared hulls, splayed legs) | Open; documented |
| GAP-03 | No round stock / moving parts | Open; documented; drawers modelled as resting boxes |
| GAP-04 | No parametric constraints in the Studio | Open |
| GAP-05 | No undo/redo in the Studio | Partly: versions + restore API [F]; no UI |
| GAP-06 | No hardware BOM | Open |
| GAP-07 | No structural strength analysis | By design; the support analysis disclaims it |
| GAP-11 | No explicit stability / support analysis | **Fixed** [F] `support.py` |
| GAP-12 | No version restore | **Fixed** [F] versions API (both stores) |
| J-1 | Dovetail / mortise names silently substituted | Documented in the prompt |
| J-3 | A too-deep tab is only a warning | Open |
| S-1 | No single-attachment / weak-attachment check | Open (SP-10) |
| E-1 | Unknown JSON fields dropped silently | Open |
| E-2 | Requirements cut to 4000 characters silently | Open |
| P-1 | Validation + support computed twice per compile | Open (+19 % corpus time) |
