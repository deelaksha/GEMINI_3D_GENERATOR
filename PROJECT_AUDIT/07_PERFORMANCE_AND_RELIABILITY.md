# 07 — Performance and Reliability

Environment: Linux, Python 3.12.3, single process, no other load. Timings are wall-clock from single runs. Treat them as
orders of magnitude, not benchmarks.

## 1. Measurements

### 1.1 Compile time (`compile_source`, production on)

| Design | Boards | Joints | Time |
|---|---|---|---|
| Chair | 5 | 8 | 0.4 s |
| Study table | 5 | 13 | 0.65 s |
| Base cabinet | 7 | 27 | 0.9 s |
| Wardrobe | 14 | 46 | 2.6 s |
| Bookshelf (auto connections) | 9 | 38 | 4.0 s |
| Egg-crate grid 8×8 (cross_lap, auto) | 15 | 91 | **6.3 s** |
| Egg-crate grid 12×12 | 23 | 198 | **22.2 s** (and `PART_EXCEEDS_SHEET`) |
| Egg-crate grid 16×16 | 31 | 330 | **44.6 s** |

> **Correction (2026-11-22, end-to-end validation):** the first version of this table reported 8.1 s / 54.1 s / 189.7 s for the 4×4 / 8×8 / 12×12 grids. Those runs had Python `tracemalloc` enabled, which inflated them several-fold. The numbers above are re-measured without it.
| Existing test "large rack, hundreds of boards" | — | — | 2.0 s (`test_real_world.py`) |

Peak Python heap (tracemalloc, separate run) stayed small: 1 / 3 / 6 MB for the 4×4 / 8×8 / 12×12 grids. **CPU, not memory, is the bottleneck.**

### 1.2 Hot spot (cProfile, 6×6 grid, production off, 6.3 s total)

| Function | Cumulative |
|---|---|
| `validation.find_collisions` → `plate_interference` → `_plate_interference` (35 pair evaluations) | **5.05 s (80 %)** |
| `_material_intervals` (241 665 calls), `_edge_line_intervals` (238 850 calls) | 3.0 s / 1.0 s |
| `joining.join` × 50 | 1.1 s |

The collision test samples every 0.5 mm along each intersection line, at 3 offsets, in both directions, and re-intersects
both boards' material intervals at each station. Cost grows with (crossing pairs × crossing length / 0.5 mm × cut-outs per board).
Egg-crate products, where every board crosses many others and each carries many notches, are the worst case.
`production_package` runs `validate_design` a second time after `_finish` already did. The interference cache absorbs most of it.

### 1.3 Test suite

`pytest tests/python`: **300 passed, 4 failed in 77 s**, peak RSS 62 MB. The 4 failures are a test-harness bug: the repo path
contains `#` (`MCLAG_#1`), and `test_gap_detection.py:294` builds a Node import specifier from the raw path, so Node reads `#1`
as a URL fragment. With a URL-encoded `file://` path the JS returns exactly the expected widths (1.06/0.96 and 3.1/2.95). (BUG-015)

`node tests/joint_fit_suite.mjs`: 47/47 checks passed (legacy JS only).

## 2. Failure conditions and bottlenecks

| Area | Finding | Evidence | Class |
|---|---|---|---|
| Synchronous compile | Compile runs inside the HTTP request. The canvas client aborts at **120 s** (`js/studio/api.js:66`); the server keeps computing (Flask has no cancellation). Compile time grows faster than linearly (16×16: 45 s); larger egg-crates will exceed it | §1.1 | Confirmed |
| Cost amplification | Every visitor of `/` or `/canvas` gets an **editor** session (`app.py:99-121`). Compile is open to any session and limited only by 600 req/min per session; new sessions are free. A few large designs keep every worker busy for minutes | code + §1.1 | Confirmed (exposure) |
| Server | Only `app.run()` (Werkzeug dev server) is provided (`app.py:304`, `start_server.py:149`); `python app.py` runs with `debug=True` on 127.0.0.1. No WSGI config, worker count, timeouts or health endpoint | code | Confirmed |
| Process-local state | Design locks (`store.py:37-41`), rate limiter (`auth.py:111`) and `_INTERFERENCE_CACHE` are per process. With >1 worker on the file store, two writers can interleave read-modify-write; revision checks only help if clients send `expected_revision`, which the UI never does | code | Potential |
| Persistence fallback | On a read-only filesystem the store moves to the temp dir and keeps working, with only a log warning (`app.py:29-47`); `/storage` reports `persistent=false` | code | Potential data loss on serverless |
| Gemini / AI failures | Not applicable inside the app (no API call). AI errors arrive as bad JSON or bad geometry, which are handled (02 §3) | — | — |
| Recovery from interrupted generation | Canvas drafts autosave to localStorage; studio edits are atomic per operation (`apply_batch` all-or-nothing, `os.replace` writes). Re-join is two requests (BUG-011) | code | Mostly OK |
| Concurrent compile edits | Edits made during a running compile are dropped (BUG-012) | `js/canvas/main.js:226` | Confirmed |
| Large 3D models | Per-board cloned textures (~1 MB GPU each), full rebuild per edit, continuous render loop, unthrottled hover raycast | `viewport3d.js` | Potential |
| Export | Cabinet booklet: 30 KB, 12 pages, built in-process. Not timed at scale | — | Not measured |
| Observability | `logging` only. No request ids, metrics or error tracking | code | Gap |

## 3. Reliability strengths (verified)

* `compile_source` never raises. Every failure is a diagnostic, and internal errors become `COMPILER_ERROR` (BUG-003 surfaced that way, not as a 500).
* Deterministic output for identical input (`probes.py` D).
* Atomic file writes, a JSONL audit trail, and all-or-nothing batches.
* Strict input limits (`model.LIMITS`, 2 MB request cap, 1 M-char source cap).

## 4. Recommendations (performance)

1. Move compile and production into a job (background worker + polling, or streaming), with a server-side time budget.
2. Collision check: broad-phase pairs by AABB (already done), then test notch/slot-adjusted rectangles analytically for
   axis-aligned board pairs, and fall back to sampling only for tilted or profiled boards. Every v1 board without `rotate` is axis-aligned, which is the common case.
3. Pass the `_finish` validation report into `production_package` instead of validating twice.
4. Require authentication beyond an automatic session for compile/save, or add a per-IP budget of CPU-seconds.
