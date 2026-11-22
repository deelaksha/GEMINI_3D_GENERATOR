# 09 — Bug and Issue Tracker

Severity: **S1** critical (security / wrong parts produced) · **S2** major (blocks a common use or gives a wrong verdict) ·
**S3** minor (poor diagnostics / UX) · **S4** cosmetic or test-only.
Status: **Confirmed-run** (reproduced by executing code) · **Confirmed-code** (traced in code, not executed) · **Potential** (risk, not reproduced).

## Confirmed bugs

| ID | Sev | Status | Title | Location | Reproduction → actual | Proposed fix |
|---|---|---|---|---|---|---|
| BUG-001 | S1 | Confirmed-code | Stored code execution: legacy pages execute JS from a world-writable Firestore collection in the app origin | `firestore.rules:5-7` (`allow read, write: if true`), `js/core/config.js:25` (`?model=`), `js/models/registry.js:163-193`, `js/services/design-parser.js:155-195` (`import(blob)`, `new Function`) | Anyone writes `designs/x` with `jsCode`; a victim opens `/inspector?model=x`; the code runs with the victim's `board_session` cookie and can send `X-Board-Client: studio` to `/api/v1` | Lock the `designs` rules (auth + owner), stop executing stored JS (legacy JSON only, or a sandboxed iframe on a separate origin), or retire the legacy pages |
| BUG-002 | S1 | Confirmed-run | Circles smaller than the kerf get a negative cut radius and are marked ready for production | `board_engine/cutpaths.py:120` | E12: Ø3 hole, kerf 3.2 → `radius: -0.1`, `ready_for_production: true` | Reject features whose size ≤ kerf (or tool Ø) in `validate_component`; clamp + error in `generate_cut_paths` |
| BUG-003 | S2 | Confirmed-run | Long board ids crash the compiler when connections are inferred | `board_engine/canvas.py:867` builds `auto-{A}-{B}` (can exceed the 64-char `ID_RE`); `canvas.py:1165` falls back to `f"C{i + 1}…"` with `i = None` | E11 (40-char ids) → `COMPILER_ERROR: TypeError`; 30-char ids → same; 29-char ids → `SCHEMA_ERROR` with no board/line (derived tab id `auto-…-t1` > 64 chars); 24-char ids → ok | Generate inferred ids that always match `ID_RE` (e.g. `auto-{n}`); never use `_i` when it is `None` |
| BUG-004 | S1 | Confirmed-code | No CNC tool model: slots, fingers and notches in wood board get no inside-corner relief and use a 3.2 mm saw kerf, while the cut list labels them `cnc` | `manufacturing.py:39-57` (kerf 3.2), `cutlist.py:152`, `cutpaths.generate_cut_paths`; no dog-bone code anywhere | Any 18 mm tab_slot design: square inside corners, `ready: true` | Add per-process tooling (`laser` / `router` with bit Ø / `saw`), dog-bone or T-bone relief on inside corners for router jobs, spacing ≥ bit Ø, kerf = bit Ø |
| BUG-005 | S2 | Confirmed-run | Shelves at equal height on both sides of a through-divider cannot be joined; no fix offered; prompt silent | `validation.py:439` `SLOT_ALREADY_USED`; `canvas_prompt.py` | 10-wardrobe → 6 × `SLOT_ALREADY_USED` + `COLLISION`; staggered 60 mm → ok | Short term: prompt rule (see 11). Engine: offer a "stagger by N mm" fix, or support a shared through-tab |
| BUG-006 | S2 | Confirmed-run | A fix marked `safe: true` (cross_lap) is offered for boards cross_lap can never join | `canvas.py:1336-1344` (`_finish`) vs `_cut_joint` plain-board rule | 09-toy-car: apply fix → `JOINT_NEEDS_PLAIN_BOARD` | Only offer cross_lap when both boards are plain, unrotated and pass `_crossing` with edge alignment; otherwise not `safe` |
| BUG-007 | S2 | Confirmed-run | Floating boards and stated-dimension conflicts do not block production | `validation.py:1450` (`FLOATING_COMPONENT` = warning), `canvas.py:1305` (`OVERALL_MISMATCH` = warning), `views.production_package` | E15, E07 → `ok: true`, `ready_for_production: true` | Make both blocking for production unless explicitly waived (`"loose": true` on a board; `overall` tolerance acknowledged) |
| BUG-008 | S2 | Confirmed-run | `set_material` thickness is a silent no-op on canvas designs; header and parts disagree | `canvas._component` sets `comp['thickness']` on every board; `operations.op_set_material` | Compile EXAMPLE → set thickness 15 → success, parts still 18 mm, valid | Don't pin per-board thickness when it equals the material; or have `set_material` update pinned boards / reject |
| BUG-009 | S3 | Confirmed-run | Out-of-range connection fields surface as a generic `SCHEMA_ERROR` without connection id or line | `canvas.py` passes hinge `count`/`gap`, fastener dicts, edge-banding thickness through unchecked; `compile_source` catches `SchemaError` | E13 → `joint.count must be an integer 1..8` | Validate in `_compile_v1` with `connection=`/`line=`; map `SchemaError.path` back to source |
| BUG-010 | S2 | Confirmed-code | UI never sends `expected_revision`; last write wins | `js/studio/api.js:55-77` vs `routes.py:96` | Two tabs editing one design | Send the loaded revision; show a conflict dialog on 409 |
| BUG-011 | S3 | Confirmed-code | Re-join is non-atomic (unjoin + join as two requests) | `js/studio/main.js:436` | Join fails → joint lost | Use `/operations` batch (`apply_batch` is all-or-nothing) |
| BUG-012 | S3 | Confirmed-code | Canvas drops edits made during a compile; status shows "Compiled" for stale source | `js/canvas/main.js:226-237` | Type during a compile | Queue a re-compile when source changed; guard phase-1 status like phase 2 |
| BUG-013 | S3 | Confirmed-code | Ctrl/Cmd-S in the canvas always creates a new project | `js/canvas/main.js:48, 431` (`save(update=false)`) | Press Ctrl-S twice → two designs | Ctrl-S updates `S.savedId` when set |
| BUG-014 | S2 | Confirmed-code | Legacy XSS sinks (design name, thumbnail, file name into `innerHTML`) | `js/ui/toast.js:16`, `js/ui/design-browser.js:269,356`, `inspector.html:187,208` | Design named `<img src=x onerror=…>` | Escape or use `textContent`; retire legacy pages |
| BUG-015 | S4 | Confirmed-run | 4 tests fail when the repo path contains `#` | `tests/python/test_gap_detection.py:294` | `ERR_MODULE_NOT_FOUND` (Node reads `#1` as a fragment) | Use `pathlib.Path(...).as_uri()` for the import specifier |
| BUG-016 | S2 | Confirmed-code | Every visitor gets an editor session; designs have no owner, so any visitor can modify or delete any design | `app.py:99-121`, `board_api/auth.py:127-141`, `routes.py:248-250` | Open `/`, call `DELETE /api/v1/designs/<id>` with the cookie + header | User accounts or at least per-session ownership; viewer by default |
| BUG-017 | S3 | Confirmed-run | Kerf compensation turns some true arcs into polylines in DXF | `cutpaths.path_segments` (`ARC_TOL`) after `offset_polygon` | Cottage example: 17 arcs → 14 with kerf | Offset arcs analytically (radius ± kerf/2) |
| BUG-018 | S4 | Confirmed-code | `apply_code_fix` re-serialises the whole source, losing comments and formatting | `canvas.py` `apply_code_fix` → `pretty_json` | Any fix | Patch by JSON path, preserving text |
| PERF-001 | S3 | Confirmed-run | Collision check dominates compile and grows super-linearly; very large egg-crates can exceed the 120 s client timeout | `validation._plate_interference`; `js/studio/api.js:66` | 8×8 grid 6.3 s, 12×12 22 s, 16×16 45 s (corrected: first report had tracemalloc on and said 54 s / 190 s) | Analytic axis-aligned path; background jobs (07 §4) |

## Feature gaps (product limitations, confirmed by scenario runs)

| ID | Gap | Evidence |
|---|---|---|
| GAP-01 | No face-to-face joint in `board-design/v1` (`face_lap` exists natively) | 01-guitar |
| GAP-02 | No bevelled edge joint for non-90° meetings (except mitre / roof-pitch) | 06-boat-punt |
| GAP-03 | No round stock (dowels/axles), no rotating or sliding parts (wheels, drawers) | 09-toy-car, 08 drawer |
| GAP-04 | No parametric constraints: editing one board never updates dependants | 05 §3 |
| GAP-05 | No undo/redo, no per-component regeneration, no add/resize/material editing in the Studio | 05 §2 |
| GAP-06 | No hardware BOM (hinges, screws, dowels by size/qty) in the cut list | 04 §1 |
| GAP-07 | No structural checks (stability, load, racking) | 06 chair |
| GAP-08 | No true-shape nesting, remnants or laser-bed presets in the canvas | 04 §3 |
| GAP-09 | No direct AI integration: diagnostics are not fed back to the AI automatically | 01 §0 |
| GAP-10 | No units field; inches or cm compile silently as mm | 03 R-3 |

## Potential risks (not reproduced)

| ID | Risk | Location |
|---|---|---|
| R-1 | Sampled collision detection (0.5 mm stations) could miss a very short overlap | `validation.py:44, 1045` |
| R-2 | Process-global interference cache shared across requests | `validation.py:992-1008` |
| R-4 | 2D/3D panes from different revisions under concurrent edits | `js/studio/main.js:155-169` |
| R-5 | Friction-fit clearance (0.1–0.2 mm) smaller than stock thickness tolerance (±0.5 mm plywood) | `manufacturing.py:40`, `validation.TOL` |
| R-6 | Fixed 6 mm part spacing regardless of tool | `canvas.py:1032-1044` |
| R-7 | Laser-scale edge margins (1.5/3 mm) applied to 18 mm board | `validation.TOL` |
| R-8 | Per-process locks and rate limit with multiple workers | `store.py:37-41`, `auth.py:111` |
| R-9 | Silent non-persistent storage on read-only hosts | `app.py:29-47` |
| R-10 | Frontend GPU memory growth with large models (per-board texture clones) | `js/studio/viewport3d.js:163-169` |

## Duplicated / unnecessary code (not changed)

* Legacy JS stack duplicating geometry, nesting, validation and 3D (01 §2), plus `ai-prompt.txt` (3 225 lines, served at 3 URLs including the typo `/ai-promtp.txt`).
* `scratch/` (16 scripts + a 1 900-line dump), unreferenced.
* `canvas._check_boards` identical return branches; `Api.rebuildBoat`, `Api.exportUrl` unused; unreachable rect branches in `viewport3d.js:63-70`, `js/studio/main.js:352`.
* `docs/architecture.md` describes only the legacy system.
