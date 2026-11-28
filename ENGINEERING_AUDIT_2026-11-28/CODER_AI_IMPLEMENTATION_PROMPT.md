# Implementation Prompt for a Coding AI Agent

You are a senior engineer implementing fixes and new capabilities in an AI-driven flat-board (laser / CNC) 3D product design system. An engineering audit (2026-11-28) has already been done; its evidence is summarised here so you do **not** need to repeat the investigation. Work in the phases below, in order. Each phase must leave the full test suite green.

---

## 0. Project facts you need

- **Location:** `/home/sonic-claude2/deelaksha/desighn/GEMINI_3D_GENERATOR` (underscore). Git repository, `HEAD = 616b135`.
- **Uncommitted work exists:** `board_engine/canvas.py`, `canvas_prompt.py`, `expand.py`, `shapes.py`, `docs/board-design-format.md` and the new `tests/python/test_generators.py`. It adds spline, superellipse, the rows/layers/grow/morph and radial generators, and wildcard connections.
  - Ask the owner whether to commit it first.
  - Never discard it.
  - Create a feature branch before changing anything.
- **Stack:** Python 3.12, Flask (`app.py`, `board_api/routes.py`), engine in `board_engine/`, front end in plain ES modules (`canvas.html` + `js/canvas/*.js`, `studio.html` + `js/studio/*.js`). Legacy JS workbench: `index.html`, `inspector.html`, `manufacturing.html`, `validation.html`, `guide.html` + `js/{assembly,core,models,services,ui}`.
- **Run tests:**
  ```bash
  pip install -r requirements-dev.txt
  PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/python -q
  for f in tests/*.mjs; do node $f; done
  ```
  - **Baseline:** 671 Python tests pass, 0 fail, ≈290 s. All 5 `.mjs` files print a pass.
- **Audit artefacts:** `ENGINEERING_AUDIT_2026-11-28/`.
  - Read `ENGINEERING_AUDIT_REPORT.md` (findings F-01..F-24).
  - Read `MECHANICAL_ENGINEERING_GAP_ANALYSIS.md` (M-01..M-17).
  - Read `PROMPT_ENGINEERING_AUDIT.md` (P-01..P-24).
  - Read `ARCHITECTURE_IMPROVEMENT_PLAN.md`.
  - Use the reproduction inputs under `evidence/`:
    - `evidence/geometry/cases/*.json`
    - `evidence/mechanical/json/*.json`
    - `evidence/pipeline/*.json`
    - `evidence/pipeline/t_*.py`: offline stubs of Gemini and Claude; no API key needed.
  - Some evidence scripts contain absolute scratch paths. Re-point them, or turn them into proper pytest tests (preferred).
- **Never call a paid LLM API in tests.** Stub `requests.post` and the `anthropic` module, as `evidence/pipeline/t_maxtok.py` and `t_aifix.py` do.

### 0.1 Architecture summary (as built)

```
canvas UI ──/api/v1/canvas/ai-generate──► routes.canvas_ai_generate (routes.py:1026)
            build_prompt (canvas_prompt.py:1852, ~98k chars) ─► ai_client.complete (Gemini REST | Claude SDK)
            ─► _ai_reply_source ─► client compiles via /canvas/compile[-stream]
compile_source (canvas.py:1691) → parse_source (+json_repair, multi-part merge) → expand.expand
  → _compile_v1 (boards→components, rotate, profiles, openings) → connections (resolve/infer/cut)
  → consolidate (default on) → _finish (validation.validate_design, connectivity, support, structure,
  inspection, motion checks) → _tail (production: views.production_package → nesting, cutpaths, manufacturing)
repair: /canvas/ai-fix (routes.py:1052) → build_repair_prompt (canvas_prompt.py:2091) → complete → returned as-is
front end 3D/2D: renders backend outlines + matrices + cut paths (no geometry recomputed client-side)
```

**What is solid (do not rewrite):**
- the transforms;
- the joint evaluation (`validation._eval_tab_slot` etc.);
- kerf offsetting (`cutpaths`);
- the closed-form gears and linkages in `motion.py`;
- nesting;
- the backend-driven 3D view.

Extend these; don't replace them.

---

## 1. Global rules

1. **Test first.** For every finding, write a failing test that reproduces it before the fix. Use the evidence inputs. Commit each fix with its test.
2. **Surgical changes.** Match the surrounding style: dense docstrings, short helpers, diagnostics via `canvas.diag(severity, code, message, ...)` or `validation.issue(...)`. Don't reformat unrelated code.
3. **Backward compatibility.**
   - Every design in `board_engine/examples/`, `tests/python/fixtures/`, `PROJECT_AUDIT/END_TO_END_VALIDATION/ai_runs/out_*` and the prompt examples must compile with **the same or better** results.
   - Add a test that pins their error counts.
   - New strictness that could break saved designs starts as a **warning** in `board-design/v1`, and may become an error only in a new `board-design/v1.1`.
4. **The public API stays:** `compile_source(...)` keyword arguments, response keys, `/api/v1` routes, the `motion.py` public functions used by `canvas.py` and `viewport3d.js`. You may add keys.
5. **Determinism:** same input → same output. No randomness without a fixed seed.
6. **No new heavy dependencies.** Shapely is already available: use it for exact polygon operations and STRtree indexing.
7. **Keep the docs in sync.** `docs/board-design-format.md` is generated from `spec_markdown()`. Regenerate it, don't hand-edit it.

---

## 2. Phase 0: safety net

1. Create `tests/python/test_audit_regressions.py`.
   - Add one test per finding listed in phases 1–4, marked `@pytest.mark.xfail(strict=True, reason="F-xx")`.
   - Remove each `xfail` in the commit that fixes it.
2. Create `tests/python/test_prompt_claims.py`.
   - Compile every complete example embedded in `canvas_prompt.py` (`EXAMPLE`, `COMPLEX_EXAMPLE`, `STRUCTURES_EXAMPLE`, `ADVANCED_EXAMPLE`) and every `jsonc` snippet in `spec_markdown()` that is a complete board set.
   - Assert 0 errors. Assert 0 warnings, after F-15 lands.
3. Create `tests/python/test_corpus_pinned.py`. Pin the error codes and counts for every design under `board_engine/examples/`, `tests/python/fixtures/` and `PROJECT_AUDIT/END_TO_END_VALIDATION/ai_runs/out_*`. The current values are in `ENGINEERING_AUDIT_2026-11-28/evidence/performance/corpus.jsonl`.
4. Add `tools/bench_compile.py`.
   - Port it from `evidence/performance/one.py`: the slats and cottages families with stage timings.
   - Add a pytest marked `slow` asserting 1,001 slats < 70 s without production (today 61 s). Tighten this in phase 4.

**Exit:** the suite is green, with the new xfails showing as XFAIL.

---

## 3. Phase 1: AI pipeline correctness (Critical/High)

### 1.1 F-01: truncated LLM replies must never become passing designs
- **Files:** `board_engine/ai_client.py`, `board_engine/json_repair.py`, `board_engine/canvas.py` (`parse_source`, ≈L253-303), `js/canvas/main.js` L540-552, `board_api/routes.py` (ai-generate / ai-fix error mapping).
- **Do:**
  - **`_gemini`:** read `cand['finishReason']`. If it is `MAX_TOKENS` (or `SAFETY`, `RECITATION`, `OTHER`), raise `AIError` with a clear message, *even when text was returned*.
  - **`_claude`:** if `message.stop_reason == 'max_tokens'`, raise `AIError('… cut off at the output limit …')`.
  - **Return value:** `complete()` returns the text and the usage, and is logged without the prompt content.
  - **`json_repair`:** when the source ends inside an open array or object (unterminated at EOF), emit a diagnostic `JSON_TRUNCATED` (error) and mark any bracket-closing repair `safe: False`. A mid-file missing bracket stays repairable (non-safe).
  - **UI:** `main.js` must not auto-apply a fix whose diagnostic is `JSON_TRUNCATED`.
- **Tests:**
  - (a) stub `requests.post` returning `finishReason: 'MAX_TOKENS'` with partial text: `/api/v1/canvas/ai-generate` gives 502 `ai_failed`, and the message contains "cut off";
  - (b) the same for Claude with `stop_reason='max_tokens'`;
  - (c) `json.dumps(EXAMPLE)` truncated just before `{"id": "MODESTY"` gives `JSON_TRUNCATED` error, no `safe` fix, `ok=False`;
  - (d) a design with one missing `}` in the middle stays repairable (non-safe).

### 1.2 F-02: server transport must not ask for multi-part or tool delivery
- **Files:** `board_engine/canvas_prompt.py` (`OUTPUT_CONTRACT` L1401-1422, `scope()` L1636-1644, `_contract` L1818-1840, `build_prompt` L1852, `build_repair_prompt` L2091), `board_api/routes.py` L1026-1073.
- **Do:**
  - Add `transport='chat'|'server'` (default `'chat'`, so the copy-paste output stays byte-identical) to `build_prompt`, `build_repair_prompt` and `build_update_prompt`.
  - **Server mode:** no MULTI-PART text, no file-tool text, a single-reply budget sentence, and "output the bare JSON object" (Gemini runs in JSON MIME mode).
  - **Routes:** call with `transport='server'`. Drop `machine['file']` on server routes.
- **Tests:** the server-mode prompt contains none of `MULTI-PART`, `"continue"`, `file tool`; chat mode is unchanged (snapshot hash).

### 1.3 F-03: an AI fix must be verified before it is returned
- **Files:** `board_api/routes.py` `canvas_ai_fix` L1052-1073, new `board_engine/repair.py`, `js/canvas/main.js` `aiFixLoop` L273-310.
- **Do:**
  - Implement `accept_repair(old_src, old_res, new_src, new_res) -> {'accepted': bool, 'reasons': [...], 'diff': {...}}`. The candidate is accepted only if:
    - the lexicographic tuple `(errors, production_blocking, completeness_errors)` strictly decreases;
    - no board id present in the old *source* disappears, unless every disappearing id was named in a removal-related diagnostic;
    - the board count does not fall by more than the problems imply.
  - **In the route:**
    - apply all deterministic safe fixes first (loop until none apply, max 10);
    - only then call the LLM;
    - compile the reply with the same `machine` and `requirements`;
    - run `accept_repair` and return `{source, accepted, reasons, diff, before, after}`.
  - **Client:** stop when the server says not accepted, or when the diagnostic multiset (code, board) repeats (stall). Show the reasons.
- **Tests (stubbed LLM):**
  - a 1-board reply to the 5-board EXAMPLE with one error → `accepted: false`;
  - an improving reply → `accepted: true`;
  - identical errors twice → `stalled`.

### 1.4 F-10: requirements must be parsed correctly and passed everywhere
- **Files:** `canvas_prompt.py` `hard_constraints` L2059-2089 (`_DIM` L2056), `board_engine/requirements.py`, `routes.py` L762 (repair-prompt), L1039 (ai-generate), L1060 (ai-fix), `js/canvas/main.js` (send `requirements`, `material` and `joinery` on ai-generate and ai-fix).
- **Do:**
  - Rebuild `hard_constraints` on `requirements.parse_sizes` (it already parses `A x B x C unit` as length × depth × height).
  - Add `parse_material(text) -> {'type'?, 'thickness'?}` so "18 mm plywood" is a thickness, not a size.
  - Add `parse_detail_level(text)` with an explicit mapping (simple/basic → 2, standard → 3, detailed → 4, collector/museum → 5). Return None on conflicting words.
  - ai-generate honours the posted `material` and `joinery` (validated). ai-fix and repair-prompt compile with `requirements=`.
  - The repair prompt includes a delimited REQUIREMENTS block.
- **Tests:**
  - `hard_constraints("1200 x 600 x 750 mm desk, 18 mm plywood, simple realistic")` contains `length: 1200`, `depth: 600`, `height: 750` and `thickness: 18`, and no `x:` or `a size:`;
  - an ai-fix stub test receives a prompt containing `REQUIREMENT_MISMATCH` when the design is 100 mm too short.

### 1.5 F-16: NaN and Infinity
- **Files:** `canvas.py` `_num` / `_vec3` (≈L378-385), `find_non_integer_dimensions._is_float` L511-512.
- **Do:** reject non-finite numbers with `BOARD_GEOMETRY` (and the equivalent for profile, opening and motion numbers). `_is_float` returns False for non-finite values.
- **Tests:** a NaN or Inf size gives only `BOARD_GEOMETRY` (no `COMPILER_ERROR`), and `/canvas/integer-fix-prompt` returns 200.

### 1.6 F-12: schema contract, unknown fields, format version
- **Files:** new `board_engine/schema.py`; hooks in `canvas._compile_v1` and `_check_boards` (L432ff); `spec_markdown()` field tables; new route `GET /api/v1/canvas/schema`.
- **Do:**
  - Define the v1 schema once (dicts or dataclasses) covering every key the compiler consumes. Inventory them from `canvas.py`, `expand.py`, `shapes.py` and `motion.py`; the audit verified that every documented key is consumed.
  - Emit `UNKNOWN_FIELD` (warning) with a difflib did-you-mean, for the top level, boards, openings, engravings, connections, motions, assemblies and instances.
  - A top-level unknown key within edit distance 2 of a known one (`conections`) is an **error**, because it silently changes semantics today.
  - An unknown `format` value gives `FORMAT_UNSUPPORTED` (error). Keep `board-design/v1`.
  - Generate the JSON Schema for the route.
  - Add a test that fails if `spec_markdown()` mentions a field missing from the schema, or vice versa.
- **Tests:** `color_scheme` / `bevel_angle` / `hinge_type` / `springs` → `UNKNOWN_FIELD`; `"conections"` → error with "did you mean 'connections'"; `"format": "totally-other/v9"` → error.

### 1.7 F-21: safe fixes on generated boards
- **Files:** `canvas.py` `apply_code_fix` L2502ff, and where fixes are built for expanded ids (`_move_fix` / `_resize_fix` L1148-1163; `_ORIGIN` mapping set in `_compile_source`).
- **Do:** when a fix targets an id produced by expansion, map it back to the source element (via `_ORIGIN`) and edit that element. If the edit cannot be expressed exactly (for example, it would move one copy of a repeat), mark the fix `safe: False` with an explanation.
- **Tests:** `evidence/pipeline/t_fixgen.py` scenario: a safe fix on `SHELF-1` either applies and compiles, or is not offered as safe.

---

## 4. Phase 2: validation correctness

### 2.1 F-05: missed collisions
- **Files:** `board_engine/validation.py` `_plate_interference` L1195ff (the pad at L1213), `_grid` L1050, `_projected_overlap` L1066.
- **Do:**
  - **Non-parallel plates:** pad = max(2·max(t) + 1, (t_a + t_b) / (2·sin θ)), bounded by the plate extents, where θ is the angle between the normals.
  - **Parallel or coplanar plates:** compute the exact overlap with shapely (`Polygon(outline).difference(cutouts)` intersected) instead of the 6,000-point grid. Keep the existing message format and the area or volume fields.
- **Tests:**
  - `evidence/geometry/cases/C6_tilted_thin_sliver.json`, `C6b_*`, `C6c_*` and `C8_large_parallel_strip_{5,10,15,25}mm.json` → `COLLISION`, volume within ±10% of the Monte Carlo value (`evidence/geometry/mc_overlap.py`);
  - `C1_rotated_parallel_aabb_overlap_no_solid.json`, `C4b_disc_perp_corner.json` → no COLLISION.

### 2.2 F-13: consolidation must not hide errors or delete joints
- **Files:** `board_engine/consolidate.py` (`_touch` L85-89 and the merge driver).
- **Do:**
  - Merge only boards that share an edge **without area overlap**; overlapping boards keep reporting COLLISION / DUPLICATE_COMPONENT.
  - Never merge across different `group` values (unless a future opt-in flag says so), nor across `hinge`, motion-related or fastener joints.
  - Never merge boards with different `role`s (phase 5).
- **Tests:**
  - `evidence/geometry/cases/K1_coplanar_overlap_consolidated.json` → COLLISION;
  - `J16_two_walls_same_place_same_side.json` → DUPLICATE_COMPONENT or COLLISION;
  - `evidence/pipeline/cons_*.json` (A: different groups, B: hinge) → not merged, hinge kept;
  - existing `test_consolidate.py` passes.

### 2.3 F-17: assembly plan wiring
- **Files:** `canvas.py` L2318 (`('summary', 'assembly')` → include `'assembly_plan'`), `views.production_package`.
- **Do:** expose the plan in the compile result. Surface `ASSEMBLY_*` errors from `manufacturing.plan_assembly` as diagnostics, so `ok` reflects them.
- **Tests:** compile EXAMPLE with production on → `result['manufacturing']['assembly_plan']` has steps. Construct a design that the planner reports locked → `ok=False`.

### 2.4 F-18: connectivity must use solids
- **Files:** `board_engine/connectivity.py` L77-80.
- **Do:** after the bbox broad phase, confirm the touch with the plate geometry. Reuse the contact computation in `validation` / `manufacturing` (contacts). Boards that are only bbox-near are not "touching".
- **Tests:** `C2_board_in_L_notch.json` and `C4a_discs_coplanar_corner_boxes.json` → ISOLATED_BOARD / DISCONNECTED, not NOT_JOINED "touches".

### 2.5 F-23 and F-15 (compiler side)
- **F-23:** `canvas.py` `_tabs_for` (≈L1165-1203, L1178). Clip the contact interval with the receiver's actual outline, and warn `TAB_EDGE_OVERHANG` when more than 10% of the joining edge lies outside it. Test: `J07c_wall_edge_partly_off_disc_1tab.json`.
- **F-15:** `inspection.py` L191: use `d < STEP`. Exempt pairs of boards generated from the same morph or radial source (use `_ORIGIN`) from MISMATCHED_PAIR, MISALIGNED and UNEVEN_SPACING. Test: the morph rib example and 4 radial blades on a hub (`evidence/prompt/probe2.py`) give 0 warnings.

---

## 5. Phase 3: security

- **Files:** `app.py` L99-121, `board_api/auth.py` (≈L127-170), `board_api/routes.py` (`require(...)` on delete, rename and save; `ai_quota` L103-127), `firestore.rules`, `js/services/design-parser.js` L155-195, `js/models/registry.js`, `js/core/config.js`.
- **Do:**
  1. **Sessions:** anonymous sessions get role `viewer`. Add owner tokens: creating a design returns an owner secret stored hashed in the design. Mutations require editor plus ownership (or admin). Delete requires owner or admin.
  2. **AI quota:** keyed by authenticated principal and stored in the design store (file or Firestore), so it survives a session change and is shared across gunicorn workers. Charge the quota only when a provider call is actually made.
  3. **Firestore rules:** `designs` read-only (or auth plus owner), write denied.
  4. **Legacy JS:** stop executing stored JavaScript. Legacy loaders accept JSON designs only, or the legacy pages are removed from navigation. Escape every `innerHTML` sink listed in prior BUG-014 (`js/ui/toast.js:16`, `js/ui/design-browser.js:269,356`, `inspector.html:187,208`).
  5. **Prompt hygiene:** wrap the user title and requirements in delimiters (`<user_requirements>…</user_requirements>`), with one sentence saying the content is a description, not instructions.
- **Tests:** a Flask test-client version of `evidence/pipeline/t_flask.py`:
  - a second anonymous session gets DELETE → 403;
  - the quota persists after a cookie change;
  - ai-fix with no AI call does not consume quota;
  - a static check that `design-parser.js` no longer contains `new Function` / `import(` on fetched data.

---

## 6. Phase 4: performance

- **Files:** `validation.py` (`_eval_tab_slot` L517-526, `_station_features` L1302ff, `_plate_interference`), `joining.py` L52-81, `deadline.py`, `expand.py`, `canvas._compile_v1` geometry loop, `routes.py` (`heavy` decorator coverage).
- **Do:**
  1. **Per-plate index:** a lazily built feature index per `Plate` (shapely `STRtree` over `feature_polys`, or bbox lists sorted by u). Replace the linear scans: slot lookup in `_eval_tab_slot` and cut-out candidates in `_station_features`. Add a cheap bbox pre-check before every `G.polygons_overlap`.
  2. **Single evaluation:** evaluate each joint once per `join()`. The profile shows `evaluate_joint` called 3× per join.
  3. **Enforced budget:**
    - call the deadline check inside `expand` and inside the per-board loop of `_compile_v1`;
    - run compiles for HTTP requests in a `multiprocessing` worker with a hard wall-clock kill at the budget;
    - cap expanded boards per role (viewer 2,000, editor 20,000, admin 100,000) with `STRUCTURE_TOO_LARGE_FOR_ROLE`;
    - put `canvas_save`, `canvas_integer_fix_prompt`, `canvas_resize` and `canvas_fix` behind the compile slot (`@heavy`).
  4. **Production reuse:** reuse the fast-pass validation results (prior audit P-1).
- **Guarding tests:**
  - property test: indexed vs brute-force slot lookup on 300 random designs gives identical diagnostics;
  - benchmark (slow marker): 2,001 slats < 30 s without production and < 60 s with production (today 220 s and 690 s); joints-stage doubling ratio ≤ 2.5;
  - `evidence/pipeline/t_dos.py` scenario (20,000 boards, 1 s base budget) terminates within the scaled budget +10%.

---

## 7. Phase 5: intent layer (product understanding and completeness)

### 5.1 Design brief
- **New file:** `board_engine/brief.py`. Schema per `PROMPT_ENGINEERING_AUDIT.md` §6.1: `product_class`, `identity_features`, `overall_mm`, `detail_level`, `components[]` (`id`, `role`, `count`, `symmetric_pair`, `parent`, `construction`, `must_be_closed`, `intentional_openings`), `enclosures[]`, `mechanisms{input, transmission[]}`, `uncertainties[]`.
- **Validation:** schema, unique ids, parents, transmission references, sizes consistent with `requirements.parse_sizes`.
- **New prompt builder:** `build_brief_prompt(title, requirements, images, transport)`, ≤ 8k tokens.
- **New routes:** `POST /canvas/brief-prompt` (copy-paste), `POST /canvas/ai-brief` (server; returns the validated brief), and an endpoint to validate a pasted brief.
- **Storage:** `design['brief']` is stored by `canvas_save`. `compile_source(..., brief=None)` accepts it.

### 5.2 Board roles
- **Schema:** optional `"role"` on boards and assembly boards (inherited by instances; mirrored copies keep the role). Add it to the schema in `schema.py`.

### 5.3 Completeness checker
- **New file:** `board_engine/completeness.py`, called from `canvas._finish` when a brief is given.
- **Inventory:** per component, count the boards (or distinct instances) whose `role` matches → `COMPONENT_MISSING` / `COMPONENT_COUNT` (error).
- **Symmetric pairs:** mirrored within 1 mm → `ASYMMETRIC_PAIR` (warning).
- **Enclosures:** for each declared closed side, cast a grid of rays (spacing ≈ max(thickness, extent/40)) from outside the enclosure's bounding box towards its interior. A ray reaching the inner region without hitting any enclosure board solid is a hole sample.
  - Remove the samples that fall inside declared `kind: "opening"` features or brief `intentional_openings`.
  - Cluster the rest and report `ENCLOSURE_OPEN` with the side, the gap bbox and the nearest boards.
  - Use the existing plate solids, transforms and ray/plate tests (`geometry.py`).
- **No brief:** emit `NO_BRIEF` (info) only; behaviour is otherwise unchanged.

### 5.4 Generation conditioned on the brief
- **Prompt:** `build_prompt(..., brief=…)` inserts the brief JSON and the acceptance rule: "every component id is the role of ≥ count boards; every must_be_closed enclosure closed except listed openings".
- **Chunking:** when the brief's estimated board count exceeds the single-reply budget, generate per top-level component with shared datums and merge them via `canvas._merge_parts`.

### 5.5 Tests
- `evidence/geometry/cases/V1_cottage_no_roof_R_nooverall.json`, `V2_*`, `V3_organiser_no_front.json`, each paired with a hand-written brief → `COMPONENT_MISSING` / `ENCLOSURE_OPEN`.
- The complete cottage with its brief → no completeness diagnostics; its door, window and vent openings are not flagged.
- A pergola brief with no enclosure → no `ENCLOSURE_OPEN`.
- All pinned corpus designs (no brief) → unchanged except for `NO_BRIEF` info.

---

## 8. Phase 6: prompt restructuring

Follow `PROMPT_ENGINEERING_AUDIT.md` (P-01..P-24 and §6).

1. **Split the prompts:**
   - `build_brief_prompt`;
   - `build_prompt` (geometry, conditioned on the brief, transport-aware);
   - `build_patch_repair_prompt` (affected boards plus neighbours, relevant spec sections only, `{"patch": …}` reply);
   - `build_update_prompt` (no creative blocks unless asked).
2. **Patch application:** implement `apply_patch(source, patch)` in `repair.py`: replace or add by id, remove listed ids, keep all other text byte-identical where possible.
3. **Remove contradictions:**
   - output format stated once per transport (P-03);
   - one curve strategy (P-07);
   - one part-count rule tied to detail level (P-12);
   - pose via motions only (P-17);
   - integer rule exempting angles, and example points rounded (P-11);
   - joinery line (P-19);
   - grid resolution and colour conditionality in IMAGE_SPEC (P-20).
4. **Remove unbuildable advice** (P-08), or keep it only once phase 7 makes profiled cross_lap work. Add the missing "cannot build" items (P-09).
5. **Delete the mandatory plan audit, score and check-list text** (P-04). The brief replaces the inventory. Remove the false claim "the compiler measures every one of these".
6. **Deduplicate (P-14):** remove the "Native engine format" section from LLM prompts and print examples one board per line (P-13). Replace the plain study-table example with a compact organic example that uses keel + morph + radial + a wildcard connection + one motion, compiling with 0 warnings (pinned by `test_prompt_claims.py`).
7. **Document** gear `pressure_angle`, `backlash`, the outline point limit and decimal angles (P-21). Remove the ship leftover wording (P-22).
8. **Legacy prompt:** label `ai-prompt.txt` and `/api/prompt` as legacy, or point them to `/canvas/prompt` (P-22 legacy).
- **Size targets (tests):** generation prompt ≤ 45,000 chars (today 98,359); patch repair prompt for `board_engine/examples/my_home.json` ≤ 40,000 chars (today 396,936).

---

## 9. Phase 7: geometry capability

1. **Profiled cross_lap:**
   - **Files:** `canvas._cut_joint` (≈L1551-1616, the plain-board rule at L1567-1568), `_cross_lap_cuttable` L1456, `validation` cross_lap evaluation.
   - **Behaviour:** allow cross_lap between profiled boards when both outlines contain a straight, solid segment spanning the crossing line over the notch depth. The notch is cut half-depth from opposite edges. Reject with a precise reason otherwise.
   - **Tests:** a profiled fuselage crossing a profiled wing joins (the `evidence/prompt/probe.py` scenario), and a tree made of two crossed silhouettes joins.
2. **Face-to-face joint in v1:** expose the native `face_lap` as a v1 connection type (glue-allowed), with documentation.
3. **Detail-level-aware consolidation and role classification:** decorative coplanar parts with the same role may merge; structural and mechanism roles never merge.

---

## 10. Phase 8: mechanics

Implement `MECHANICAL_ENGINEERING_GAP_ANALYSIS.md` §4 in a new `board_engine/kinematics.py`, keeping the `motion.py` functions as adapters. Order of work:

1. **M-03:** the moving set includes rods and riders for lock detection.
2. **M-04:** the ratio sign on flipped instances (`expand._instance_motion` L581-613).
3. **M-01, M-16:** adaptive step Δθ ≤ c / r_max, bisection, no 72-sample cap (reduce the range modulo the period instead).
4. **M-05:** annulus broad phase, local-frame narrow phase, a tip-circle bound for gears.
5. **M-02:** motion-vs-motion interference on overlapping swept envelopes.
6. **M-06, M-13:** pin and axle solids; running clearance in the mechanism sweep.
7. **M-09, M-10, M-11:** MOTION_NO_PIVOT, MOTION_NO_GUIDE; the hinge reconciled with the motion; axle `supports`, `retain` and fit classes; a laser knuckle hinge.
8. **M-08, M-12:** typed `couple` for rack and belt with geometric checks; explicit ratio checked against teeth; pressure angle in GEAR_MESH.
9. **M-07, M-14:** branch tracking and LINKAGE_CHANGE_POINT; mobility count, undeclared mesh detection, multiple-input warning.
10. **Later:** cam and follower (support-function solver), crown or peg bevel gears, Ackermann steering as a horizontal four-bar.
11. **M-15, M-17:** cycle message text; jam-limited animation range exported to `viewport3d.js`.

**Tests:** the 14 acceptance rows in the gap analysis §5, using `evidence/mechanical/json/*`.

---

## 11. Phase 9: manufacturing process model

- **Files:** `manufacturing.py` L39-57, `cutpaths.py`, the `routes._machine` schema, `canvas_prompt` laser text.
- **Do:**
  - Add `machine.process: laser|router|saw` and `tool_diameter`. Kerf defaults by process (laser 0.15–0.2, router = bit diameter).
  - Dog-bone relief (circle of tool radius at each inside corner) for router processes on slots, finger notches and cross_lap notches.
  - Minimum web, part spacing and edge margins as process-dependent parameters.
- **Tests:** a router export of EXAMPLE has relief arcs at every slot corner. A laser export without an explicit kerf uses ≤ 0.3 mm.

---

## 12. Phase 10 (optional, budget-gated): visual feedback

- Render 4 standard views server-side, or capture them from the client.
- Send them with the brief (and reference images) to a vision-capable model once per design.
- Parse a structured discrepancy list into problems for **one** patch-repair round.
- Log the cost per design.
- Never loop.

---

## 13. Definition of done

1. **Tests:** all phases' tests pass. The original 671 Python tests and 5 JS tests still pass. No `xfail` remains for phases 1–4.
2. **Corpus:** every design in the pinned corpus compiles with the same or fewer errors, and no new error code appears on a previously clean design except deliberately added warnings.
3. **Truncation:** a truncated LLM reply can never yield `ok=True` (tests 1.1 a–c).
4. **Repair:** the AI-fix endpoint never returns an accepted candidate with more errors than its input, and the UI loop stops on a stall.
5. **Completeness:** for designs with a brief, missing mandatory components and undeclared open sides are errors. Declared openings are never flagged.
6. **Performance:** 2,001 slats compile in < 30 s without production. The 20k-board request stops within its budget. The 4-gear-pair instance compiles in < 10 s.
7. **Security:** anonymous users cannot mutate or delete designs. AI quota is per user across workers. No stored JS is executed.
8. **Prompts:** the size targets are met, and every example and recommended construction compiles (`test_prompt_claims.py`).
9. **Docs:** `docs/board-design-format.md` is regenerated, and a CHANGELOG entry lists new diagnostics and schema fields (`role`, `brief`, `axle.supports`, `couple`, `format v1.1`).
10. **LLM benchmark** (requires an approved budget; the owner runs it): 12 products × 2 providers, before and after phases 5–6. Record compile errors, completeness errors, board count, tokens, latency and repair rounds, and store the outputs as fixtures. Do not claim quality improvements without this measurement.

## 14. Things you must not do

- Do not rewrite the geometry engine, nesting or cut-path code wholesale. Make targeted changes with tests.
- Do not let the LLM compute motion frames, gear ratios or coordinates that software can derive.
- Do not auto-close openings to satisfy completeness. Only report undeclared gaps.
- Do not make unknown fields hard errors in `board-design/v1` (except near-miss top-level keys, per 1.6).
- Do not add paid API calls to tests, CI or start-up.
- Do not delete or overwrite `PROJECT_AUDIT/` or `ENGINEERING_AUDIT_2026-11-28/`.
