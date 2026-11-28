# Engineering Audit Report: GEMINI 3D Generator (board-design platform)

| | |
|---|---|
| Audit date | 2026-11-28 |
| Repository | `/home/sonic-claude2/deelaksha/desighn/GEMINI_3D_GENERATOR` (the path in the request, `GEMINI-3D-GENERATOR` with a hyphen, does not exist; the underscore directory is the project) |
| Revision audited | `HEAD = 616b135` plus **uncommitted working-tree edits** in `board_engine/canvas.py`, `canvas_prompt.py`, `expand.py`, `shapes.py`, `docs/board-design-format.md` and new `tests/python/test_generators.py`. The working tree was audited as it stood; nothing was modified |
| Method | Static reading of every engine module, plus **execution**: the full test suite, a corpus of all bundled and real AI-generated designs, about 200 targeted probe designs (geometry, joints, mechanisms, schema, security), and a scaling sweep from 50 to 5,000 boards. No paid LLM call was made (no API key is configured, and none was used) |
| Companion documents | `PROMPT_ENGINEERING_AUDIT.md`, `MECHANICAL_ENGINEERING_GAP_ANALYSIS.md`, `TEST_EXECUTION_REPORT.md`, `ARCHITECTURE_IMPROVEMENT_PLAN.md`, `CODER_AI_IMPLEMENTATION_PROMPT.md` |
| Evidence | `evidence/` holds the specialist reports (`evidence/*/*_audit.md`, with the full per-finding fields for every G-, M-, E- and P- id), every probe design (`evidence/geometry/cases/`, `evidence/mechanical/json/`, `evidence/pipeline/*.json`), the scripts and the raw outputs. Scripts were written for a scratch venv. Run them from the project root with any Python that has `requirements-dev.txt` installed, and adjust the hard-coded scratch paths in a few of them |

A previous audit exists in `PROJECT_AUDIT/` (2026-11-20/22). Where an item from it is still open, this report says so (`prior: BUG-xxx`).

---

## 1. Executive summary

The deterministic engine is **much stronger than the AI layer around it**. These were verified by running them:

- Geometry transforms are exact (to 5e-5 mm).
- Collision detection samples exact cross-sections, not bounding boxes.
- Every joint type is validated against real geometry.
- Kerf offsets go in the correct direction.
- Gears and four-bar and slider-crank linkages are solved in closed form in the backend.
- The 3D and 2D views draw the backend's own outlines and matrices.
- All 671 Python tests and all 5 JS test files pass.

The project's problems sit around that engine:

1. **The AI pipeline can silently produce wrong designs that pass.**
   - A reply truncated by the model's output limit is accepted. The UI's automatic "safe" JSON repair then turns it into a smaller design that compiles `ok=True` and `ready_for_production=True`. Reproduced: 3 of 5 boards, only an info diagnostic (**F-01**).
   - The AI-fix step accepts any reply without checking that it improved anything (**F-03**).
   - The server path sends the copy-paste prompt, which tells the model to answer in several parts and wait for "continue", but the server makes exactly one call (**F-02**).
2. **The system does not understand what it is building.**
   - There is no product model, component inventory or completeness check. A cottage with its roof removed, or an organiser with no front wall, compiles `ok=True` (**F-04**).
   - The `plan` the prompt demands is ignored by the compiler.
   - The only "requirements understanding" is a size regex, and its prompt-side twin mis-parses `1200 x 600 x 750 mm, 18 mm plywood` into `x: 750 mm` and `a size: 18 mm` (**F-10**).
3. **The prompt is a 98k-character (~25k-token) monolith** that asks one LLM call to be analyst, designer, architect, engineer and inspector, all "in its head".
   - It contains contradictions.
   - It recommends constructions the compiler rejects (cross-lapped profiled silhouettes, stacked slices) (**F-11**).
   - It demands "0 warnings", which the compiler's own `morph` and `radial` examples cannot meet (**F-15**).
   - The current 98k prompt has **never been measured against an LLM**. All recorded LLM runs used the earlier 31.7k prompt on furniture.
4. **Correctness holes in the deterministic checks:**
   - missed collisions at shallow tilt angles and for overlap strips under about 20 mm (**F-05**);
   - motion sweeps that let thin or fast parts tunnel through others, and independent motions never checked against each other (**F-06**);
   - connecting rods fixed to static parts that are not reported as locked, and a mirrored rack-and-pinion that runs the wrong way (**F-07**);
   - consolidation that silently swallows overlapping or duplicate boards and deletes hinges (**F-13**).
5. **Performance is quadratic in the number of slots on one receiving board.**
   - 1,000 boards took 61 s and 2,000 boards took 220 s without production.
   - The cooperative time budget can be overrun 30x: a 237-byte request ran 730 s (**F-08**).
6. **Security (prior items still open):**
   - every anonymous visitor is an `editor` and can delete any design, and the AI quota can be bypassed (**F-09**);
   - the legacy Firestore `designs` collection is world-writable and its JavaScript is executed by the legacy pages (prior BUG-001).

Mechanical capability is genuinely good for planar spur gears and planar linkages, and absent for bevel gears, cams, belts (ratio only), steering, multi-support shafts, pin and axle solids, mobility analysis and motion-vs-motion collision. See `MECHANICAL_ENGINEERING_GAP_ANALYSIS.md`.

---

## 2. Architecture as built (traced, not assumed)

### 2.1 Components

| Layer | Files | Role |
|---|---|---|
| Web pages | `canvas.html` + `js/canvas/*.js` (AI Design Canvas), `studio.html` + `js/studio/*.js` (Board Studio), legacy `index.html`, `inspector.html`, `manufacturing.html`, `validation.html`, `guide.html` + `js/{assembly,core,models,services,ui}` | Canvas: prompt, paste or AI-generate, compile, view and export. Studio: edit validated designs through the REST API. Legacy: a JS workbench that **executes design code** (`js/services/design-parser.js:160,174,182`) |
| HTTP | `app.py`, `board_api/routes.py` (1,210 lines), `auth.py`, `contract.py` | Flask, `/api/v1/*`. The canvas endpoints are under `/api/v1/canvas/*` |
| LLM | `board_engine/ai_client.py` | One synchronous text-only call: Gemini REST (`gemini-2.5-pro`, `responseMimeType: application/json`, `maxOutputTokens: 65536`) or Claude (`claude-opus-5-5`, `max_tokens: 64000`, effort `xhigh`). `TIMEOUT_S = 300` |
| Prompts | `board_engine/canvas_prompt.py` (2,256 lines) | `spec_markdown()` (64k chars), `build_prompt`, `build_repair_prompt`, `build_update_prompt`, `build_integer_fix_prompt`, `hard_constraints`. `docs/board-design-format.md` is generated from it. `ai-prompt.txt` (85k) is a **legacy** prompt for the JS workbench format |
| Compiler | `board_engine/canvas.py` (2,528 lines) | `compile_source` → `parse_source` (+ `json_repair.py`, multi-part merge) → `expand.py` (repeat, rows, layers, grow, morph, radial, mirror, assemblies and instances) → `_compile_v1` (board → native component, rotate, profiles, openings, engravings, colours) → connections (resolve, infer, classify, cut joints) → consolidation (`consolidate.py`) → `_finish` → `_tail` (production) |
| Geometry and validation | `geometry.py`, `model.py`, `shapes.py`, `joining.py`, `validation.py` (1,722 lines), `connectivity.py`, `support.py`, `structure.py`, `inspection.py`, `requirements.py` | Plates in local 2D with world frames. Joint evaluation, cross-section collision sampling, connectivity, support and stability, weak sections and retention, "eye-like" inspection, requirement sizes |
| Motion | `motion.py` (940 lines), `hinge.py` | Rotate and slide motions, gear ratio propagation, closed-form linkages, sampled sweep collision, axle holes |
| Manufacturing | `manufacturing.py`, `nesting.py`, `cutpaths.py`, `cutlist.py`, `booklet.py`, `lightburn.py`, `views.py`, `testfit.py`, `jobreport.py`, `painting.py` | Kerf-offset cut paths, MaxRects plus true-shape nesting, assembly plan, PDF booklet, SVG, DXF and LightBurn export |
| Storage | `store.py` (files), `firestore_store.py` | Versioned designs |

### 2.2 Lifecycle: from description to assembled model, with information loss

```
User (canvas.html)  title + requirements (+ material, thickness, joinery, machine, images)
   │
   ├─(A) Copy-paste path: POST /canvas/prompt → build_prompt(...)          ~98k chars
   │        user pastes into an external chat (images attached there) → pastes reply back
   │
   └─(B) Server path:     POST /canvas/ai-generate  (routes.py:1026-1049)
            build_prompt(title, req, material=None ❶, thickness, joinery='interlocking' ❷, machine, images=False ❸)
            ai_client.complete(prompt)  one call, no tools ❹; finishReason / stop_reason not checked ❺
            _ai_reply_source(reply)     outermost {...}
   ▼
compile_source(text, requirements)                         canvas.py:1691
   parse_source → json_repair (marks bracket-closing "safe") ❻ → multi-part merge
   expand (repeat/mirror/radial/assemblies)                 expand.py
   _compile_v1: boards → components; plan ignored ❼; unknown fields ignored ❽
   connections: resolve / infer ("auto"; a misspelled key → inferred) ❽
   consolidate (default ON): coplanar touching OR overlapping boards merged ❾
   _finish: validate_design (joints, collisions), connectivity, support, structure, inspection, motions
   _tail: production package (nesting, cut paths, manufacturing incl. assembly_plan ❿)
   ▼
UI: diagnostics, 3D/2D preview (backend outlines + matrices), "Auto-fix safe issues", "Fix with AI"
   └─ /canvas/ai-fix (routes.py:1052-1073): compile WITHOUT requirements ⓫ → build_repair_prompt
         (full spec + full source) → complete() → returned unverified ⓬ (UI loops up to 2 rounds)
   ▼
save / export zip (SVG, DXF, LBRN2, PDF booklet, test-fit, README)
```

Where information is lost or transformed wrongly. Each item was verified by running it or with a spy:

| # | Loss | Evidence |
|---|---|---|
| ❶❷ | Material and joinery posted by the client are replaced by `None` and `'interlocking'` | `routes.py:1039` and a spy in `evidence/pipeline/` (test 43) |
| ❸ | Reference images never reach the server LLM. The UI blocks "Generate with AI" when images are ticked, so images work only in the copy-paste path | `ai_client.py` text-only; `evidence/prompt/prompt_audit.md` |
| ❹ | Prompt instructs multi-part replies or "use your code/file tool"; the server makes one tool-less call | `canvas_prompt.py:1411-1418, 1824` (F-02) |
| ❺❻ | Truncated replies are accepted and then "safely" repaired into smaller designs | F-01 |
| ❼ | `plan` (reference, inventory, datums, checks) is ignored. It is only merged across parts (`canvas.py:233-241`) | F-04 |
| ❽ | Unknown fields are dropped silently. `"conections"` gives `ok=True` with inferred joints | F-12 |
| ❾ | Overlapping and duplicate coplanar boards are merged; hinges between coplanar boards are deleted | F-13 |
| ❿ | `manufacturing['assembly_plan']` is computed, but the compile result reads `mfg['assembly']`, so the plan never reaches the canvas UI | F-17 |
| ⓫ | `/ai-fix` and `/repair-prompt` compile without requirements: `REQUIREMENT_MISMATCH` never reaches the repair prompt | F-10 |
| ⓬ | The AI fix is never compiled or compared before being handed back | F-03 |

---

## 3. Findings

Severity: **Critical**, **High**, **Medium**, **Low**. Classification uses the requested vocabulary.

**Verification column:**
- **R** = reproduced independently by the lead auditor in this session;
- **S** = reproduced by a specialist probe (input file in `evidence/`);
- **C** = confirmed by code reading only.

The source ids (G-, M-, E-, P-) point to the specialist reports in `evidence/`, which carry the full field set for each item: reproduction, output excerpt, regression risk, acceptance test.

### 3.1 Findings index

| ID | Sev | Classification | Title | Source ids | Verif. |
|---|---|---|---|---|---|
| F-01 | Critical | Confirmed bug | Truncated LLM reply becomes a smaller design that passes and is "ready for production" | E-01, P-02 | R |
| F-02 | Critical | Confirmed bug | Server AI path sends multi-part and file-tool instructions to a single tool-less call | P-01 | R |
| F-03 | High | Confirmed bug | `/canvas/ai-fix` accepts any reply: no compile, no regression check, no id preservation, no stall detection | E-02 | S |
| F-04 | High | Architectural limitation / missing capability | No product understanding: no inventory, no completeness or enclosure check; the `plan` is ignored | G-05, P-04, P-18 | R/S |
| F-05 | High | Confirmed bug | Missed collisions: shallow tilt (<~30°) and parallel overlap strips <~20 mm | G-01, G-02 | R |
| F-06 | High | Confirmed bug / architectural limitation | Motion sweep tunnels (fixed 5°, ≤72 samples); independent motions not checked against each other | M-01, M-02 | R/S |
| F-07 | High | Confirmed bug | Rod fixed to a static part not `MOTION_LOCKED`; mirrored rack moves the wrong way | M-03, M-04 | R/S |
| F-08 | High | Performance issue | Quadratic slot matching and collision station features; time budget overrun up to 33x; instanced gear pairs time out | new, E-05, M-05 | R/S |
| F-09 | High | Confirmed bug / security | Anonymous editor sessions can delete any design and bypass the AI quota; world-writable Firestore plus legacy JS execution | E-08, E-09, prior BUG-001/016 | S/C |
| F-10 | High | Confirmed bug | Requirements mishandled: `hard_constraints` mis-parse; requirements dropped on ai-fix; material and joinery dropped on ai-generate | P-05, P-06, E (L1-L3) | R/S |
| F-11 | High | Prompt engineering issue | Prompt recommends constructions the compiler rejects (cross-lapped profiles, stacked slices or discs) | P-08, P-09 | S |
| F-12 | High | Confirmed missing capability | No formal schema: unknown or misspelled fields silently ignored; any `format` string accepted | E-03, E-11 | S |
| F-13 | Medium | Confirmed bug | Consolidation merges overlapping or duplicate boards (hides COLLISION), merges across groups, drops hinges | G-03, E-06 | R/S |
| F-14 | Medium | Architectural limitation / performance | Prompt 98k chars (~25k tokens); repair prompt re-embeds spec and full source (397k chars for my_home); full-JSON repair cannot scale | P-15, P-16, E-07 | S |
| F-15 | Medium | Prompt engineering issue | Contradictions: "0 warnings" vs warnings from the engine's own examples; integer rule vs example decimals; curve-density guidance ×3; pose rules; 5.0 mm inspection boundary bug | P-07, P-10, P-03 | S |
| F-16 | Medium | Confirmed bug | NaN / Infinity in a number crashes the compile (`COMPILER_ERROR`, design lost) and returns 500 from `/integer-fix-prompt` | E-04 | R |
| F-17 | Medium | Confirmed bug | Assembly plan dropped from compile result (key mismatch); `ASSEMBLY_LOCKED` only in production blockers | G-06 | R |
| F-18 | Medium | Confirmed bug | Connectivity uses bounding boxes, so it says boards touch when they don't and gives wrong advice | G-04 | S |
| F-19 | Medium | Confirmed missing capability | Mechanical hardware is declared, not modelled: no axle or guide required, pins and axles not solids, single-support axles, ratio couplings unchecked, hinge edge vs pivot mismatch accepted, linkage branch flip, pressure angle unchecked | M-06..M-12 | R/S |
| F-20 | Medium | Confirmed missing capability | Manufacturing process model: 3.2 mm saw kerf default for laser stock; no dog-bone relief for router | E-13, G-12, prior BUG-004 | S/C |
| F-21 | Medium | Confirmed bug | "Safe" fixes on generated (repeated) boards fail with KeyError; UI auto-fix retries the failing fix up to 10× | E-10 | S |
| F-22 | Low | Potential issue (UX) | `ok=True` (compiled) while production has up to 50 blocking issues; easy to misread as "done" | corpus | R |
| F-23 | Low | Potential issue requiring testing | tab_slot accepted when the joining edge overhangs a profiled receiver (tabs placed against its bbox) | G-07 | S |
| F-24 | Low | Mixed | Minor consistency items (see 3.4) | G-08..G-11, E-11, E-12, E-14..E-16, M-15, M-16 | S/C |

### 3.2 Critical findings (full detail)

#### F-01: Truncated LLM reply becomes a smaller design that passes and is "ready for production"
- **Severity / class:** Critical, confirmed bug.
- **Location:**
  - `board_engine/ai_client.py` `_gemini` L58-60: raises only if the text is empty; `finishReason == 'MAX_TOKENS'` is ignored.
  - `_claude` L86-90: only `refusal` is handled; `stop_reason == 'max_tokens'` is ignored.
  - `board_engine/json_repair.py`: closes open brackets, and the resulting fix is flagged `safe`.
  - `js/canvas/main.js` L540-552: the UI applies a `repair_json` fix automatically, once, and recompiles.
- **Existing behaviour:** A reply cut off by the output limit is returned as the design. If the cut falls between two array elements, bracket closing produces valid JSON with fewer boards. A missing `connections` key then triggers auto-inference, and the result compiles clean.
- **Expected:** a truncated reply is detected and reported as `AI_REPLY_TRUNCATED`. It is never auto-repaired into a design, and it is continued or regenerated in smaller pieces.
- **Root cause:** the provider stop signal is discarded; JSON repair cannot know that content is missing; "safe" is defined syntactically, not semantically.
- **Reproduction (lead, R):** `json.dumps(EXAMPLE)` cut just before `{"id": "MODESTY"` → `compile_source` gives `JSON_SYNTAX` with a safe fix → `apply_code_fix` → `compile_source(run_production=True)`. Result: `ok=True, boards=3 (of 5), ready_for_production=True`, diagnostics `[info CONNECTIONS_INFERRED]`. The specialist ran the same end-to-end with a stubbed Gemini `MAX_TOKENS` reply through `/canvas/ai-generate` (`evidence/pipeline/t_maxtok.py`, test 21).
- **User-visible impact:** missing walls, roofs or parts with a green status; cut files produced for an incomplete product. Most likely for exactly the large, detailed designs the prompt encourages ("NO SIZE LIMIT … hundreds or thousands of boards").
- **Proposed solution:**
  1. `ai_client` returns `(text, stop_reason, usage)` and raises `AIError('truncated')` on `MAX_TOKENS` / `max_tokens`.
  2. `json_repair` marks bracket-closing repairs as `safe: false` whenever the cut is at end-of-input (it can only be truncation), and emits `JSON_TRUNCATED` (error).
  3. UI never auto-applies a truncation repair.
  4. For large designs, generate per sub-assembly (see ARCHITECTURE_IMPROVEMENT_PLAN §3).
- **Dependencies:** none. **Regression risk:** low; legitimate missing-brace typos from hand edits would now need one click.
- **Acceptance tests:** (a) stubbed Gemini `finishReason=MAX_TOKENS` gives HTTP 502 `ai_truncated`; (b) stubbed Claude `stop_reason=max_tokens` behaves the same; (c) a design truncated at a board boundary gives `JSON_TRUNCATED` error, no safe fix, `ok=False`; (d) a mid-file missing `}` typo is still repairable (non-safe fix).

#### F-02: The server AI path sends multi-part and file-tool instructions to a single tool-less call
- **Severity / class:** Critical, confirmed bug.
- **Location:**
  - `board_api/routes.py` `canvas_ai_generate` L1026-1049 and `canvas_ai_fix` L1052-1073 call `build_prompt` / `build_repair_prompt`, built for the copy-paste chat.
  - `board_engine/canvas_prompt.py` `OUTPUT_CONTRACT` L1411-1418 ("MULTI-PART REPLIES … the user answers "continue""); `scope()` L1636-1644 ("above that decide the number of multi-part replies NOW"); `_contract` L1824 (with `machine.file`: "Use your code / file tool: write a short script …").
- **Existing:** For any design the model judges to need more than ~250 boards, the model is told to send part 1 and stop. The server never sends "continue", so the result is `PART_MISSING`. That goes to `/ai-fix`, which sends the same contract again. With the "AI delivers a .json file" switch, the model is told to use a tool it does not have.
- **Expected:** the server path uses a generation contract that matches its transport. Either single-reply generation with compact authoring (assemblies, instances, repeat), or orchestrated per-sub-assembly calls that the server merges.
- **Reproduction (R):** `build_prompt('Castle','',None,None,'interlocking',{'kerf':0.15,'sheet':{...}},False)` contains `MULTI-PART` and `continue` (98,629 chars). `routes.py:1039` uses this builder unchanged.
- **Impact:** large or detailed products, the very ones the user wants, cannot complete through "Generate with AI".
- **Fix:** add `transport='server'|'chat'` to `build_prompt` and `build_repair_prompt`. Server mode removes multi-part and file-tool text and adds a hard budget ("the JSON must stay under N KB; use assemblies, instances and repeat"). Above the budget, use the planner-driven chunked generation from the architecture plan. Reject `machine.file` on the server path.
- **Regression risk:** low (copy-paste text unchanged). **Acceptance:** the server-mode prompt contains none of `MULTI-PART`, `continue`, `file tool`, and a prompt snapshot test pins this.

### 3.3 High findings (full detail)

#### F-03: `/canvas/ai-fix` accepts any reply
- **Location:** `routes.py:1052-1073`; `js/canvas/main.js:273-310` (`aiFixLoop`, `AI_FIX_ROUNDS = 2`).
- **Existing:** The server compiles the old source, builds the repair prompt, calls the LLM and returns `{'source': reply, 'changed': True}`. The reply is never compiled. The UI loop stops after 2 rounds or when there are no errors. In the stubbed test, a 1-board reply to a 5-board design was accepted and then compiled "clean" (`evidence/pipeline/t_aifix.py`, test 28).
- **Expected:** compile the candidate server-side. Accept it only if:
  - errors decrease (lexicographic on `(errors, blocking, warnings)`);
  - no board ids or connections outside the reported problem set disappear (id-preservation diff);
  - board count does not drop by more than a tolerance unless the problems requested removal.

  Otherwise return the candidate as rejected, with the reason. Stop when the error multiset repeats (stall) or after N rounds.
- **Root cause:** the endpoint is a pass-through. There is no acceptance policy.
- **Fix:** an `accept_repair(old_res, new_res, old_src, new_src) -> (accepted, reasons, diff)` deterministic gate. Apply safe deterministic fixes *before* paying for an LLM round. Use a repair patch format (see F-14).
- **Acceptance:** stubbed regression reply → `accepted:false, reason:'boards removed: …'`; stubbed improving reply → accepted with the diff; identical error set twice → `stalled`.

#### F-04: No product understanding or completeness verification
- **Location:** there is no module for it. `requirements.py` only extracts sizes. `canvas.py:233-241` touches `plan` only to merge parts. `inspection.py` checks gaps and alignment, not coverage.
- **Existing:** All of these compile `ok=True` (`evidence/geometry/cases/V1_*`, `V2_*`, `V3_*`):
  - the prompt's own cottage with one roof panel removed;
  - the cottage with both roof panels and a wall removed;
  - the desk organiser with its front wall removed.

  The cottage cases fail only incidentally (`OVERALL_MISMATCH`) when `product.overall` happens to be given. The prompt claims "SUCCESS CRITERIA (the compiler measures every one of these): … every inventory item present". That is false.
- **Expected:** a structured, machine-checkable design brief: product class, mandatory components with counts, intentional openings, enclosures and symmetry. The compiler verifies it against the built geometry: presence by role and group, counts, closure of declared enclosures with declared openings excluded, and symmetry.
- **Root cause:** the architecture has one free-form LLM step and a geometry-only validator. "Completeness" lives only in prose.
- **Fix:** ARCHITECTURE_IMPROVEMENT_PLAN §3–4 (design brief schema, `completeness.py` with role-tagged boards, enclosure coverage via ray or voxel sampling, and opening allow-lists).
- **Acceptance:** the three V-cases produce `COMPONENT_MISSING` / `ENCLOSURE_OPEN` errors; the same designs with the parts present pass; a declared window or door opening is not flagged.

#### F-05: Missed collisions at shallow tilt and narrow parallel overlaps
- **Location:**
  - `board_engine/validation.py` `_plate_interference` L1212-1220: `pad = 2.0 * max(a.t, b.t) + 1.0` limits sampling around the mid-plane intersection line.
  - `_grid` / `_projected_overlap` L1050, L1066: at most 6,000 sample points, about a 22 mm grid on a 2400×1200 board.
- **Reproduction (R):**
  - `evidence/geometry/cases/C6b_shallow_tilt_3mm_penetration.json`: real overlap 2,264–12,267 mm³ (independent Monte Carlo `mc_overlap.py`); no `COLLISION` reported. The 30° control case is reported.
  - `C8_large_parallel_strip_10mm.json`: a 214,358 mm³ overlap, not reported.
  - In both files `ok=False` is caused only by an unrelated `NOT_JOINED`, so once joined, the overlap would pass.
- **Expected:** exact overlap detection for any angle and any strip width.
- **Fix:** widen the station range to `(t_a+t_b)/(2·sin θ)` (bounded by plate extents). For parallel coplanar or near-coplanar plates, compute the exact shapely polygon intersection (shapely is already a dependency) instead of grid sampling.
- **Acceptance:** C6, C6b, C6c and C8 (5, 10, 15 mm) report `COLLISION` with volume within ±10% of the Monte Carlo estimate; existing collision tests unchanged.

#### F-06: Motion sweep can tunnel; independent motions are not cross-checked
- **Location:** `board_engine/motion.py` `_samples` L594-606 (`ROTATE_STEP` 5°, slides ≈ range/48, capped at 72); motion-vs-motion handling around L708.
- **Reproduction:**
  - (R) `evidence/mechanical/json/s14a_tunnel_thin_arm.json`: the thin arm passes through the post with no `MOTION_COLLISION`. The control with the post at 5° (`s14a_control_post_at_5deg.json`) is caught.
  - (S) `s14b_tunnel_fast_driven.json`: a ratio-10 follower is effectively sampled every 50°.
  - (S) `s14e_two_independent_arms_meet.json`: two arms that collide when both are open are not reported.
- **Fix:** bound each step so the largest swept displacement of any vertex is ≤ the minimum clearance (adaptive step). Bisect to the first contact. Use swept-volume (annulus or capsule) broad-phase culling. For independent motions, check the product of their ranges (coarse grid plus refinement), or require the user to declare the motions mutually exclusive.
- **Acceptance:** s14a, s14b and s14e are reported; the s09 lid contact angle is reported within 0.5° of the analytic 42.2°.

#### F-07: Rods fixed to static parts are not "locked"; flipped rack runs the wrong way
- **Location:** `motion.py` L644-648: `fixed` joints are only those crossing the motion's own `group`, so the linkage rod is not in it. `expand.py` `_instance_motion` L581-613: the sign of `ratio` is not corrected when an instance is flipped.
- **Reproduction:**
  - (R) `s08b_rod_tabbed_to_static_post.json`: no `MOTION_LOCKED`, only a misleading `MOTION_COLLISION` ("put the rod in its own layer").
  - (S) `s11i_flipped_rack_and_pinion.json`: the rack moves −0.524 mm while the pinion tooth surface moves +0.524 mm.
- **Fix:** include rods (and any board carried by a driven motion) in the moving set for lock detection. When an instance flip changes the handedness of the coupling axis, negate the ratio (derive the rack direction from the geometry: tangent direction at the contact point).
- **Acceptance:** s08b gives `MOTION_LOCKED` naming the rod joint; s11i rack displacement equals the tooth-surface displacement in sign and magnitude.

#### F-08: Performance: quadratic stages and an unenforced time budget
- **Measured (R):** `evidence/performance/results.jsonl`. Slats tab_slotted into one base, no production:

  | boards | total s | joints s | collisions s | peak RSS MB |
  |---|---|---|---|---|
  | 51 | 0.91 | 0.16 | 0.61 | 22 |
  | 101 | 1.75 | 0.32 | 1.18 | 25 |
  | 301 | 8.95 | 2.80 | 5.30 | 34 |
  | 501 | 17.9 | 6.84 | 9.65 | 42 |
  | 1001 | 61.4 | 28.1 | 30.3 | 64 |
  | 2001 | 220.1 | 119.5 | 93.5 | 107 |
  | 5001 | >900 (killed by harness timeout) | – | – | – |

  The joints stage grows ×4.3 per doubling (quadratic). With production on, 1,001 boards take 120 s and 2,001 boards take **690 s**, of which 570 s is booked under the collision stage.
- **Root cause (profiled, R, `cProfile` of 600 slats, 57 s):**
  1. `validation._eval_tab_slot` L517-526 finds a tab's slot by calling `G.polygons_overlap(footprint, poly)` against *every* feature of the receiving board: 360,000 calls = 600², each a pure-Python segment-pair test (5.8 M `segments_intersect`). There is no bounding-box pre-check and no spatial index.
  2. `_plate_interference` → `_station_features` L1302ff loops over all cut-outs of the receiving plate per station: 7,200 calls, 13 s.
  3. Each join re-evaluates joints (`joining.join` → `evaluate_joint` ×3).
- **Budget (S):** `deadline.py` is cooperative and the per-board geometry loop never checks it. A 237-byte request expanding to 20,000 boards was given a 22 s scaled budget, ran 730 s and used 857 MB (`evidence/pipeline/t_dos.py`, test 27). The budget scales with the expanded board count up to `MAX_BUDGET` = 900 s, so an anonymous visitor can obtain 15 CPU-minutes per request. Compile slots don't cover `save`, `integer-fix-prompt`, `resize` and `fix`.
- **Instanced gears (S):** 1 gear pair 1.3 s, 2 pairs 78 s, 4 pairs 159 s (timeout) (`s14d_timing_*`).
- **Fix:**
  - bbox pre-filter plus an STRtree (shapely) or uniform grid per receiving plate for feature lookups; cache `feature_polys` bboxes;
  - evaluate each joint once per join;
  - check the deadline inside expansion and geometry loops; cap the expanded board count for anonymous or viewer roles;
  - run compiles in a worker process with a hard wall-clock kill;
  - put every compile-calling endpoint behind the compile slot.
- **Acceptance:** 2,001 slats < 30 s; 5,001 < 120 s (no production); joints stage scales ≤ n·log n (doubling ≤ ×2.5); 20k-board request terminated within budget +10%.

#### F-09: Access control and legacy code execution
- **Location:**
  - `app.py:99-121` (every page visit gets a session); `board_api/auth.py:150-157` (a session is role `editor`).
  - `routes.py` delete, rename and save need only `editor`; the `auth.py` docstring says delete needs `admin`.
  - `ai_quota` is per session and per process (`routes.py:103-127`).
  - `firestore.rules:5-7` (`allow read, write: if true` on `designs`); `js/services/design-parser.js:160,174,182` (`import(blobUrl)`, `new Function`).
- **Reproduction (S):** a second anonymous session deleted the first session's design (HTTP 200). A new session resets the hourly AI quota. The daily cap multiplies with gunicorn workers (`evidence/pipeline/t_flask.py`, tests 36, 38, 39). The Firestore → JS path was confirmed statically. It was not executed, because that would write to the live project.
- **Impact:** data loss by any visitor; paid-API cost exposure; stored script execution in the app origin (legacy pages).
- **Fix:**
  - default sessions get `viewer`; editing requires login or an owner token; per-design owner;
  - AI quota keyed by authenticated user and a shared store (Firestore or Redis), with the global cap shared across workers;
  - lock `designs` rules (auth plus owner), stop executing stored JS, and retire the legacy pages.
- **Acceptance:** an anonymous DELETE gives 403; quota persists across sessions and workers; legacy pages render a JSON-only design without `import()` / `new Function`.

#### F-10: Requirements mishandled across the pipeline
- **Location:**
  - `canvas_prompt.py` `hard_constraints` L2059-2089 (`_DIM` regex L2056);
  - `routes.py:1039` (ai-generate ignores material and joinery);
  - `routes.py:1061` (ai-fix compiles without `requirements`);
  - `routes.py:762` (repair-prompt likewise).
- **Reproduction (R):** `hard_constraints('1200 x 600 x 750 mm desk, 18 mm plywood, simple realistic')` returns `- x: 750 mm`, `- a size: 18 mm`, `- detail level: 5 (every visible element, fine detail included)`. The real requirement (L1200 × D600 × H750) is lost. A material thickness becomes a dimension constraint, and "simple" maps to maximum detail.
- **Fix:**
  - **Parsing:** reuse `requirements.parse_sizes` (which parses `A x B x C` correctly) as the single source of truth, and add parsing for material and thickness.
  - **Detail level:** map detail words explicitly (simple → 2, standard → 3, detailed → 4, collector → 5) and let explicit UI controls override them.
  - **Endpoints:** pass `requirements`, `material` and `joinery` through ai-generate, ai-fix and repair-prompt.
- **Acceptance:** that string yields length 1200, depth 600, height 750, a thickness of 18 and detail 2. An ai-fix compile includes `REQUIREMENT_MISMATCH` when it applies.

#### F-11: The prompt recommends constructions the compiler rejects
- **Location (quoted in `PROMPT_ENGINEERING_AUDIT.md` §4):** "a tree or bush = a few interlocking silhouette boards (cross_lap them for volume)" (spec "Fewer, smarter boards"). Also "stacked discs, cross-lapped pairs" and "stacked contour slices" in `DESIGN_QUALITY` / `UNIVERSAL_METHOD`.
- **Evidence (S):** `JOINT_NEEDS_PLAIN_BOARD` (cross_lap requires plain rectangles), `NO_CONTACT` / `UNATTACHED_BOARD` (face-stacked slices cannot be joined) (`evidence/prompt/probe*.py/.out`). A slotted aeroplane (profiled fuselage crossing a profiled wing) is not buildable, and the "cannot build" list does not say so.
- **Fix:** either extend `cross_lap` to profiled boards (the notch only needs a straight segment of both outlines at the crossing: a real capability that would unlock silhouettes, trees, animals and aeroplanes), or remove these recommendations. Recommended: **implement profiled cross_lap**, since it is the single most valuable geometric primitive for recognisable silhouettes.
- **Acceptance:** two profiled boards crossing at straight segments join with `cross_lap`; a prompt-claims test compiles every construction the prompt recommends.

#### F-12: No formal schema contract
- **Location:** `canvas.py` `_check_boards` L432ff and hand-written checks spread through `_compile_v1`; no JSON Schema anywhere.
- **Reproduction (S):** unknown keys (`color_scheme`, `bevel_angle`, `hinge_type`, `springs`) at the top, board, connection and motion level produce no diagnostic. `"conections"` gives `ok=True` with auto-inferred joints. `"format": "totally-other/v9"` gives only a warning (`evidence/pipeline/t2.py`, `t_schema.py`; tests 2–5).
- **Fix:** a JSON Schema (draft 2020-12) generated from one Python source of truth (dataclasses or pydantic) that also generates the spec tables in `spec_markdown()`.
  - `UNKNOWN_FIELD` warning with did-you-mean (difflib), and an error for unknown top-level keys that shadow known ones (`conections`).
  - `FORMAT_UNSUPPORTED` error for unknown format versions.
- **Acceptance:** each case above gives the new diagnostic; a schema-vs-spec test fails if a documented field is not in the schema or vice versa.

### 3.4 Medium and Low findings

| ID | Location | Existing → expected | Root cause | Fix | Acceptance |
|---|---|---|---|---|---|
| F-13 | `consolidate.py:85-89` `_touch` treats overlap as touching; group not considered; joints between merged boards dropped | Overlapping or duplicate coplanar boards merge silently (K1, J16 `ok=True`; with consolidation off: COLLISION / DUPLICATE_COMPONENT). Door + Frame merged and the hinge deleted (`t_cons` A/B) | Merge predicate too broad | Merge only on *edge contact without area overlap*, same `group` (or opt-in), never across `hinge` or motion joints. Report overlaps first | K1/J16 report COLLISION; hinge pair stays separate |
| F-14 | `canvas_prompt.py` `build_prompt`, `build_repair_prompt` L2091ff, `build_update_prompt` L2193ff | 98k-char generation prompt; repair 74k fixed plus source (397k chars for my_home); update prompt includes about 10k chars of "be creative" text; full JSON returned | Monolithic spec reused everywhere | Modular prompt sections selected by need; repair sends only relevant spec sections plus the affected boards' neighbourhood plus a JSON-Patch reply format keyed by board id | Repair prompt for my_home < 40k chars; patch applies and is validated |
| F-15 | `canvas_prompt.py` SUCCESS_CRITERIA L1448; examples L44ff/L678ff; `inspection.py:34,191` | "0 errors and 0 warnings" is unattainable for morph and radial (the engine's own example warns `MISMATCHED_PAIR`/`MISALIGNED`); integer rule vs `[7.6, 1.9]` example points; three conflicting curve-density rules; "lid slightly open" vs "drawn at position 0"; inspection flags an exact 5.0 mm offset while the message says "≥ 5 mm is deliberate" | Prompt grew by accretion; off-by-boundary comparison | Remove contradictions; suppress MISMATCHED_PAIR / MISALIGNED between generated copies of one morph or radial; use `>=` at the 5 mm boundary | Prompt-claims test: every example compiles with 0 warnings |
| F-16 | `canvas.py:511-512` `_is_float` → `round(nan)` | NaN/Inf gives `COMPILER_ERROR`, design lost; `/integer-fix-prompt` 500 | No finiteness check | `math.isfinite` check in `_vec3` / `_num` and `_is_float` | NaN size gives only `BOARD_GEOMETRY` |
| F-17 | `canvas.py:2318` reads `mfg['assembly']`; `manufacturing.py:1059` returns `assembly_plan` | Canvas result never has an assembly plan (the booklet reads the right key); `ASSEMBLY_LOCKED` only in `layout.blocking_issues` | Key mismatch | Read `assembly_plan`; surface ASSEMBLY_* in diagnostics | Compile result contains the plan; a locked design is `ok=False` |
| F-18 | `connectivity.py:77-80` uses `G.near_pairs` on bounding boxes | Post in an L-notch, discs 27 mm apart: "NOT_JOINED although it touches" plus "add a connection" advice | bbox proximity treated as touch | Confirm touch with the plate solids (the `validation` contact machinery) | C2/C4a cases say ISOLATED_BOARD / DISCONNECTED |
| F-19 | `motion.py` (see MECHANICAL gap analysis M-06..M-12) | Rotate without axle or hinge, and slide without guide, compile with no diagnostic (R: `s13_*`, `s13b_*`); pins not solid; one support per axle; rack and belt ratios unchecked geometrically; hinge edge vs pivot mismatch accepted; parallelogram branch flip; pressure angle unchecked | Mechanism declared, not modelled | Kinematic graph with typed joints (MECHANICAL plan) | See gap analysis acceptance list |
| F-20 | `manufacturing.py:39-57` (kerf 3.2 for all sheet types); `cutpaths.py` (no inside-corner relief) | 6 mm laser plywood exported with a 1.6 mm offset per side unless the laser panel is used; router slots get square inside corners, so tabs will not seat | No process model | `process: laser|router|saw` with tool diameter; dog-bone or T-bone relief for router; kerf from process | Router export has relief arcs ≥ tool radius; laser default kerf ≤ 0.3 mm |
| F-21 | `canvas.py` `apply_code_fix` on expanded ids (e.g. `SHELF-1`) | KeyError → 422; UI "Auto-fix safe issues" retries up to 10× | Fixes target expanded ids that do not exist in the source | Map fixes back to source via `_ORIGIN` (edit the repeat or generator) or mark them non-safe | Safe fix on a repeated board applies or is not offered |
| F-22 | `routes.py:858` (`compiled = res['ok']`), UI | `ai_runs/out_new/B.json`: `ok=True`, 50 production blockers, `ready=False` | Two notions of "done" | UI shows one status: Not compiled / Compiled with blockers / Ready | — |
| F-23 | `canvas.py:1178` (`_tabs_for` uses receiver bbox) | 60 of 180 mm of a wall edge overhanging a disc base: `ok=True` | Tab layout against bbox, not outline | Clip the contact interval with the receiver outline; warn on overhang | J07c warns |
| F-24 | various | G-08: slot web min 1 mm vs advice 2t. G-09: duplicate connection codes differ by type, and tab_slot + butt on one pair both accepted. G-10: a broken native joint stays `joined`. G-11: docs say ≤3 rotate steps, code accepts 4. E-11: format version. E-12: position and size bounds checked separately (9.8 m board). E-14: requirements pasted undelimited (prompt injection). E-15: CORS `*` and absolute path in `/api/status`. E-16: 300 s AI call vs proxy timeouts. M-15: cycle message prints `drive -> drive`. M-16: collision angle precision = step | — | See `evidence/*_audit.md` | — |

---

## 4. Answers to the audit questions (by section of the request)

- **§4 Product understanding:** none of the 12 planning activities is performed by software.
  - Classification, inventory, decomposition and completeness verification exist only as instructions inside one prompt, and their output (`plan`) is discarded.
  - A dedicated planning stage **is required** (ARCHITECTURE_IMPROVEMENT_PLAN §3). It should produce a small structured brief that software validates, not a free-text plan.
- **§5 Missing components:** the software distinguishes "structurally valid" (well covered) from "visually complete" (**not at all**). Intentional openings are already typed (`kind: "opening"` vs `"hole"`), which is the right foundation for distinguishing them from unintended gaps.
- **§6 Geometry:**
  - The same transformed plates feed validation, the 3D view (`viewport3d.js` extrudes backend outlines with backend matrices), the 2D sheets (backend cut paths) and nesting. No 2D/3D divergence was found.
  - Collision detection is exact cross-section sampling, not AABB. Its blind spots are F-05.
  - Connectivity alone uses bboxes (F-18).
- **§7 Mechanics:** see the gap analysis document. Planar spur gear trains and closed-form linkages are genuinely supported, and solved deterministically. That is the correct design: the LLM declares topology, and software computes motion.
- **§8 Joints:** the slot-claim conflict (`SLOT_ALREADY_USED`) is detected. Joints are verified geometrically, so a joint record is not trusted. An assembly planner exists (`manufacturing.plan_assembly`) and found valid orders for closed boxes, but its output is dropped from the canvas result (F-17).
- **§9 Board optimisation:** coplanar consolidation exists and is on by default, but its predicate is unsafe (F-13). There is no detail-level control beyond the prompt's own (mis-parsed) "detail level" (F-10). There is no classification of boards into structural, functional or decorative roles.
- **§10 Realism:** the geometric vocabulary is rich: spline, superellipse, arch, gear and path profiles; morph, radial and grow generators; tilted and compound-tilted panels; living hinges; engravings.
  - The most limiting gap is **profiled cross_lap** (F-11). Without it, recognisable 3D silhouettes (animals, aeroplanes, trees) can only be done as ribs on a keel.
  - The second is the lack of any visual feedback loop.
- **§11 Reference images:** used only in the copy-paste path. The server never sends images, and there is no render-and-compare loop.
- **§12 Schema:** see F-12. Repeat, mirror and instance expansion were exercised by the test suite and probes. Defects found there: a flipped instance's ratio sign (F-07) and safe fixes on expanded ids (F-21).
- **§13 Repair:** deterministic safe fixes exist (move, resize, swap, convert to cross_lap, JSON repair). LLM repair is unverified (F-03), resends everything (F-14), and is mixed with deterministic errors that software could fix.
- **§14 Assembly and manufacturing:** see F-17 and F-20. Manufacturing constraints are partly configurable (`machine` object: kerf, sheet, measured thickness, fit). Tool model and process are not.
- **§15 Performance:** see F-08. The LLM is the dominant latency in practice (one call, up to 300 s; not measured: no key). The compiler is the bottleneck above ~500 boards.
- **§17 Security:** see F-09, E-14, E-15. Positive results:
  - API keys are sent only in headers, never logged or returned to the browser;
  - path traversal is blocked (6 variants → 404);
  - the session cookie is HttpOnly and SameSite=Strict, with a CSRF header enforced;
  - image engravings are limited to PNG and JPEG ≤ 400 KB;
  - the 100k-board cap is enforced.

---

## 5. Quality scorecard (0–100)

**M** = based mainly on measurements in this audit; **Q** = qualitative engineering judgement (with the evidence it rests on). Criteria: 90+ production-grade with verified guarantees; 70–89 solid with known gaps; 50–69 works for common cases, important gaps; 30–49 partial; <30 largely missing.

| Category | Score | Basis | Evidence |
|---|---|---|---|
| Product understanding | 15 | Q | No classification, inventory or completeness in software; `plan` discarded; requirement parsing defective (F-04, F-10) |
| Prompt quality | 40 | Q+M | Rich domain content, but 98k chars, contradictions, unbuildable recommendations, wrong transport, never measured at its current size (F-02, F-11, F-14, F-15) |
| Geometric accuracy | 78 | M | Transforms exact; invalid profiles rejected; same geometry for render, validation and nesting; two classes of missed collisions (F-05) |
| Visual realism (capability) | 55 | Q | Strong profile and generator vocabulary; no profiled cross_lap; no visual feedback; realism depends on an unmeasured prompt |
| Component completeness | 10 | M | Roofless and wall-less models compile `ok=True` (F-04) |
| Mechanical functionality | 55 | M | Spur trains, crank-rocker, slider-crank and Grashof jam correct; tunnelling, rod lock, flip sign, no hardware model, no bevel, cam or belt geometry (F-06, F-07, F-19) |
| Joint correctness | 80 | M | All six types validated geometrically; slot conflicts detected; kerf direction right; minor gaps (F-23, F-24) |
| Assembly feasibility | 45 | M+Q | Planner exists and works on probes, but its output is dropped from the canvas result; no insertion-path collision (F-17) |
| Material efficiency | 60 | M | MaxRects + true-shape nesting (77.8% yield on the example table); consolidation unsafe; no detail-level control |
| Performance | 45 | M | Fine ≤300 boards (<10 s); quadratic above (2,000 boards 220 s); budget overrun 33× (F-08) |
| Repair intelligence | 35 | M | Good deterministic safe fixes; LLM repair unverified, full-resend, no stall detection (F-03, F-14, F-21) |
| Code maintainability | 60 | Q | Clear modules, extensive docstrings; very large files (`canvas.py` 2.5k, `canvas_prompt.py` 2.3k, `validation.py` 1.7k lines); prompt and spec text hand-maintained alongside code; legacy JS stack still shipped |
| Test coverage | 70 | M | 671 Python + 5 JS test files all pass; strong engine tests; no tests of LLM transport failure modes, AI-fix acceptance, completeness or prompt-vs-compiler claims (the gaps found here) |
| Production readiness | 35 | Q+M | Critical AI-pipeline bugs, open access model, legacy stored-JS execution, unenforced compute budget (F-01, F-02, F-08, F-09) |

---

## 6. What was not tested, and why

- **Live LLM generation** (all 16 product scenarios in request §16: Victorian mansion, aeroplane, locomotive and so on): **NOT TESTED**. No API key is configured, and paid calls were not approved. Generation quality for the current 98k prompt is therefore **unmeasured**. The AI transport failure modes were tested with offline stubs (F-01, F-03).
- **Firestore stored-script execution:** not executed (it would write to the live project). The code path was confirmed statically.
- **Browser rendering performance and memory** (WebGL with 1,000+ boards): not measured. The backend preview payload was measured indirectly (see TEST_EXECUTION_REPORT).
- **Physical strength and fit:** no physical testing. The engine itself disclaims strength analysis, and no claim of structural adequacy is made here.
