# 09 — Performance and Hang Analysis

Single process, Python 3.12.3, no other load, wall-clock from single runs. Treat the numbers as orders of magnitude.

## 1. Correction to the first audit

The first audit reported 54 s / 190 s for the 8×8 / 12×12 egg-crate grids. Those runs had `tracemalloc` enabled.
Re-measured without it: **8×8 → 6.3 s, 12×12 → 22.2 s, 16×16 (31 boards, 330 joints) → 44.6 s**. The first audit's
07, 08, 09 and 10 were corrected in place, with a note.

## 2. Where processing can hang (investigated)

| Risk | Finding | Status |
|---|---|---|
| Infinite loops in geometry | Every `while` loop in `board_engine` inspected: parsers advance an index, `_cut_outline` consumes edges, `manufacturing.disassemble` removes a non-empty proper subset per step, Tarjan SCC is standard, `autofix` is bounded by `max_steps ≤ 200`, Firestore paging ends on the last token | no unbounded loop found |
| Recursive generation | `disassemble` recursion depth ≤ number of boards (≤ 300) | bounded |
| Excessive polygon complexity | ≤ 2048 points per outline (EC-17), ≤ 64 features, ≤ 300 boards, ≤ 1000 joints | bounded |
| Extremely large JSON | 2 MB request cap → 413 (EC-19); 1 M-char source cap | bounded |
| Expensive collision detection | super-linear: 16×16 grid 44.6 s | [F] **time budget** |
| Infinite regeneration cycles | canvas "auto-fix safe issues" loops ≤ 10; server auto-fix ≤ 200 steps | bounded |
| Unresolved / circular dependencies | circular connection pairs deduplicated (EC-15); the joint graph is traversed with visited sets | bounded |
| Stalled Gemini requests | n/a (no Gemini call) | — |
| UI loading forever | baseline: canvas compile had a 120 s client timeout, **every other Studio request had none** (`timeout = 0`) | [F] default 150 s client timeout |
| Unresponsive 3D rendering | full scene rebuild per edit, per-board texture clones, always-on render loop (first audit) | open, not measured |
| Nesting time | MaxRects is O(parts² · free rectangles); 300 boards nest within the existing large-rack test (2 s) | acceptable |

## 3. Time budget, cancellation and progress [F]

* `board_engine/deadline.py`: `time_budget(seconds)` sets a context-local deadline. `check()` is called in the hot loops:
  collision pairs and sampling passes (`validation`), each join (`joining`), each nesting item (`nesting`) and the contact
  search (`manufacturing`). Exceeding it raises `TimeBudgetExceeded` **before anything is written**.
* `compile_source(..., time_budget=)` turns it into a `COMPILE_TIMEOUT` diagnostic with advice (split the design).
* API: canvas compile/save/import/repair/update pass `BOARD_TIME_BUDGET` (default 90 s); read-only heavy endpoints
  (`validate`, `model3d`, `layout2d`, `manufacturing`, `cutlist`, `export`) are wrapped by `@budgeted` → HTTP 503
  `time_budget_exceeded`. Mutating endpoints are **not** budgeted: a timeout after the store write would wrongly
  report failure for a saved change.
* Measured: an 8×8 grid with a 5 s budget returns `COMPILE_TIMEOUT` after 5.0 s (EC-26); with 0.2 s, 0.2 s (`test_time_budget_stops_compile_with_a_clear_diagnostic`).
* Cancellation: the browser aborts at 150 s (Studio) / 120 s (canvas compile). The server stops at its own budget.
  There is no explicit cancel button and no progress percentage: the canvas shows two phases ("compiling" → "preparing cut sheets").

## 4. Cost of the new checks

| | baseline | after |
|---|---|---|
| 18-product corpus, total | 29.1 s | 34.7 s (+19 %) |
| Cabinet with drawers (18 boards) | 4.4 s | 7.5 s |
| Bookshelf, inferred joints (16 boards) | 13.2 s | 13.7 s |
| Full pytest suite | 77 s (304 tests) | 112 s (368 tests) |

The increase comes from the support analysis. Its contact search (`manufacturing.find_contacts`, O(n²) board pairs ×
edges) runs in `_finish` and again in `production_package`. Passing the report through would remove the duplicate (open P-1).

## 5. Open

* **P-1**: compute validation and support once per compile and pass them to `production_package`.
* **P-2**: analytic collision test for axis-aligned board pairs (the common v1 case) instead of 0.5 mm sampling.
* **P-3**: background jobs with progress for very large designs; today the budget stops them instead.
* **P-4**: 3D rendering costs under large models were not measured (no GPU profiling in this environment).
