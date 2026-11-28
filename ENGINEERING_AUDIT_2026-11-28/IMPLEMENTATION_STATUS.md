# Implementation status (phases 1–10 of CODER_AI_IMPLEMENTATION_PROMPT.md)

All work is uncommitted on `main` on top of `b8ee35d`. Phases 3, 8 and 9 were built in separate scratch worktrees by
parallel agents and merged by hand.

**Test status:**
- Python suite: 845 tests (the original 671 plus 174 new) in 13 new test files.
- The 5 JS test files pass.
- `node --check` passes on every edited JS file.

**Not tested:** no paid AI call was made. Every AI path is tested with stubs, and anything that needs a live model is
listed under "Not tested".

## Phase by phase

| Phase | Status | What changed (main files) | New tests |
|---|---|---|---|
| 1 AI pipeline | Done | Truncated replies are an error (`ai_client`, `json_repair`, `JSON_TRUNCATED`); server transport (`build_prompt(transport='server')`); verified AI fixes (`repair.accept_repair`, safe fixes first); requirements parsing and plumbing (`requirements.parse_material/parse_detail_level`, `hard_constraints`); NaN/Inf; field contract (`schema.py`: UNKNOWN_FIELD, MISSPELLED_FIELD, INVALID_VALUE, FORMAT_UNSUPPORTED); fixes on generated boards | `test_ai_pipeline.py` |
| 2 Validation | Done | Exact collisions at shallow tilt and for narrow parallel strips (`validation._plate_interference`, `_parallel_overlap`); consolidation never merges across groups, roles, hinges or fastened joints, and reports REDUNDANT_BOARD; assembly plan in the compile result and ASSEMBLY_* errors; connectivity from solids; TAB_EDGE_OVERHANG; morph/radial copy exemptions and the 5 mm boundary | `test_validation_audit.py` |
| 3 Security | Done (deploy pending) | Design ownership (`auth.may_change`, owner on create); AI quota per principal/IP in a shared file ledger, charged only on real calls; legacy JS runs no fetched code (parser is data-only by default, only the editor opts in); innerHTML sinks escaped; prompt text delimited; no CORS `*`, no path in `/api/status` | `test_security.py` |
| 4 Performance | Done (one item partial) | Per-plate feature index, incremental plates inside joining loops, near-only pair checks, `is_material` bisection, x-sweep `nearest`, swept and cached `self_intersections`, indexed assembly planner, budget checked at every progress point, per-caller board cap (`max_boards`), compile slot on save / integer-fix | `test_performance_audit.py` |
| 5 Intent layer | Done (chunking not done) | `brief.py` (schema + validation), board `role`, `completeness.py` (COMPONENT_MISSING/COUNT, ROLE_UNKNOWN, ASYMMETRIC_PAIR, ENCLOSURE_OPEN by inside-out sight lines that ignore shallow recesses and declared openings), `/canvas/brief-prompt`, `/canvas/ai-brief`, `/canvas/brief-check`, brief in generation, "Plan first" in the canvas UI | `test_completeness.py` |
| 6 Prompts | Done (LLM benchmark not run) | Lean default prompt (`style='lean'`; `'full'` kept for comparison); patch repair (`build_patch_repair_prompt`, `repair.apply_patch`) on the server fix path; update prompt without creative blocks for plain changes; spec corrected (angles, role, brief, pressure angle, outline limit, axle supports, adaptive sweep, linkage example, generic wording); legacy `/api/prompt` labelled | `test_prompt_lean.py` |
| 7 Geometry | Done (detail-level merging partial) | cross_lap between shaped boards: halving where outlines cross, or a closed slot that the other board passes through (`through`); `face_lap` (glued lamination) as a v1 connection; merging is role-aware | `test_cross_lap_shaped.py` |
| 8 Mechanics | Mostly done | `kinematics.py` + `motion.py`: adaptive sweep with bisection, annulus/tip-circle broad phase, motion-vs-motion MOTION_INTERFERENCE, pin/axle solids, rod lock, flipped-ratio sign, MOTION_NO_PIVOT/NO_GUIDE, hinge reconciliation, axle supports/retain, pressure angle, GEAR_RATIO, LINKAGE_CHANGE_POINT, undeclared mesh / multiple inputs, jam-limited animation | `test_mechanics_audit.py` |
| 9 Process | Done | `machine.process` laser/router/saw + `tool_diameter`; dog-bone reliefs for router; TOOL_TOO_LARGE / RELIEF_BREAKS_WEB; process kerf; router spacing; process in cut list, job report, booklet and README; output with no process is byte-identical to before | `test_process_model.py` |
| 10 Visual check | Done (live test not run) | `critique.py`, images for Gemini and Claude in `ai_client.complete(images=)`, `/canvas/ai-critique`, visual problems into one AI-fix round (`allow_equal` acceptance), "Visual check" button capturing 4 standard views (`Viewport3D.snapshots`) | `test_visual_check.py` |

## Measured results

| Measurement | Before | After |
|---|---|---|
| Truncated reply (3 of 5 boards) | `ok=True`, ready for production | JSON_TRUNCATED error, no safe fix |
| Generation prompt (no motion) | 98–100k chars | 44.8k (chat) / 43.8k (server); about 53k with the motion sections |
| Repair prompt, `my_home.json` | 397k chars, full design back | patch prompt under 40k (pinned by a test), patch back |
| 2,001 boards in one receiving board (no production) | 220 s | 36 s |
| 1,001 boards (no production) | 61 s | about 15 s |
| Production package, 600 boards | 33.5 s | 10.8 s |
| 20,000-board request, 1 s budget (scaled 22 s) | 734 s | 22.6 s |
| 10 instanced gear pairs | over 9.5 min | 4.0 s |
| Shallow-tilt / 10 mm parallel overlap | not reported | COLLISION with the exact area |
| Cottage with no roof (with brief) | `ok=True` | COMPONENT_COUNT + ENCLOSURE_OPEN top |

## Behaviour changes to know about

- **Anonymous access:** anonymous sessions can change only the designs they created. Seeded and older designs are read-only for them.
- **Truncated input:** text that stops mid-design is `JSON_TRUNCATED`, and its repair is never applied automatically.
- **Format errors:** unknown `format` values are an error. A near-miss top-level key (e.g. `conections`) is an error.
- **AI fix:**
  - it applies safe fixes first and may return without calling the AI;
  - an AI reply is used only if it is better;
  - the server asks for a patch instead of the whole design.
- **Default prompt:** the default generation prompt is the lean one. The old one is `style='full'`.
- **New warnings:** MOTION_NO_PIVOT, MOTION_NO_GUIDE, MOTION_INTERFERENCE, MOTION_INPUTS, AXLE_UNRETAINED, TAB_EDGE_OVERHANG, REDUNDANT_BOARD, UNKNOWN_FIELD. Not on any shipped design.

## Must be done by the owner

1. Deploy `firestore.rules` (legacy `designs` collection is now read-only for clients). It stays world-writable until
   deployed.
2. Run the LLM benchmark (PROMPT_ENGINEERING_AUDIT.md §7; roughly 48 generations) to compare `style='lean'` with
   `style='full'` and to try the brief + completeness flow and the visual check on real models.

## Not done / partial

- **Phase 4:**
  - No hard worker-process kill. The budget is cooperative, so a 4,000-board request can overrun its 4.4 s budget to about 10 s.
  - The 5,000-board benchmark was not re-run.
- **Phase 5:** no chunked per-component generation for designs too big for one reply.
- **Phase 7:** no detail-level-specific merging; merging is role-aware only.
- **Phase 8:**
  - Not built: laser knuckle hinge, typed rack/belt `couple`, explicit linkage branch tracking, DOF count, cams, bevel gears, steering.
  - Fit classes and VISIBLE_GAP suppression for axles were not added.
  - The prompt does not yet mention `axle.supports` / `retain` (the spec does).
- **Phase 9:**
  - Router reliefs in compensated output are drawn as plunge paths, not arcs.
  - Process-scaled edge margins in `validation.py` (R-7) were not applied.
- **Phase 3:**
  - No CSP or iframe sandbox for the legacy pages.
  - Ownership ends when the 12-hour session cookie expires.
  - The Studio shows a 403 when an anonymous user edits an example.

## Not tested

- Every live AI call: generation, brief, repair, update and visual check, with Gemini and with Claude.
- The canvas UI in a browser. The JS was only syntax-checked: the "Plan first" option, the "Visual check" button, the process controls, data-only legacy loading.
- Firestore with the new rules.
