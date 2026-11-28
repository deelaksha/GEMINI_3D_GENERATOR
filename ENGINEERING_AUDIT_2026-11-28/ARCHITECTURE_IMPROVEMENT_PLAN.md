# Architecture Improvement Plan

**Principle:** keep and extend the deterministic engine, which is the project's real asset. Shrink the LLM's job to what only an LLM can do, give it structured intermediate outputs, and check every claim in software. Do **not** build sixteen services or sixteen LLM calls.

---

## 1. Diagnosis in one paragraph

Today one LLM call receives a 98k-character prompt and must:
1. understand the product,
2. plan it,
3. design it creatively,
4. compute every coordinate,
5. choose joints, and
6. inspect its own work,

then return the full JSON in one reply. Software checks only geometry and joints. Product intent (components, closure, counts, mechanism topology) is never captured in a machine-readable form. "Missing roof" and "uncovered cockpit" are therefore invisible to the validator. Repair resends everything, and is accepted without checking that it improved anything. The engine downstream is accurate. The weak points are the *intent layer* and the *control loop*.

## 2. Target pipeline

```
             ┌──────────────────────────── LLM (≤ 3 calls + 1 optional) ───────────────────────────┐
user text ──►│ (1) DESIGN BRIEF (structured, small)      (2) GEOMETRY (per brief; chunked if large)   │
 + images    │        │                                        │                    (3) PATCH REPAIR│
             └────────┼────────────────────────────────────────┼─────────────────────────▲──────────┘
                      ▼                                        ▼                         │
             brief schema validation                compile_source (existing engine)     │
             + user confirm/edit (optional)          ├─ schema validation (NEW, F-12)     │
                      │                              ├─ expand / geometry / joints         │
                      │                              ├─ deterministic auto-repair (NEW)    │
                      └──────── brief ──────────────►├─ completeness vs brief (NEW, F-04) │
                                                     ├─ kinematics graph + sweep (NEW)    │
                                                     ├─ assembly plan (existing, wired)   │
                                                     ├─ consolidation (fixed predicate)   │
                                                     └─ production (process model)        │
                                                              │                          │
                                       acceptance gate (NEW): improved? ids kept? ───────┘ (bounded rounds,
                                                              │                              stall detection)
                                                              ▼
                                                   (4) optional VISUAL CRITIQUE (rendered views → vision model,
                                                       ≤ 1 per design) → discrepancies → (3) once
```

### 2.1 Mapping the 16 suggested stages onto this design

| Requested stage | Where it lives | LLM or deterministic |
|---|---|---|
| 1 User requirement interpreter | `requirements.py` extended (sizes, material, thickness, detail level, mounting) + brief call | Deterministic parse; LLM fills the rest in the brief |
| 2 Product understanding engine | Brief call (1) | LLM |
| 3 Reference-image analysis | Brief call (1) with images (copy-paste or a vision-capable server model) | LLM |
| 4 Engineering design planner | Brief call (1) | LLM |
| 5 Component inventory generator | Brief `components[]` | LLM produces; software validates |
| 6 Geometry generation | Call (2) | LLM (coordinates) + deterministic generators (repeat, morph, radial, instances) |
| 7 Mechanism planner | Brief `mechanisms` + motions in call (2) | LLM declares topology; software solves |
| 8 Deterministic constraint solver | `autofix.py` / new `repair_rules.py` | Deterministic |
| 9 Structural connectivity validator | Existing `connectivity.py`, `support.py`, `structure.py` (fix F-18) | Deterministic |
| 10 Motion simulation | `motion.py` → `kinematics.py` | Deterministic |
| 11 Visual completeness validator | New `completeness.py` (inventory, enclosure coverage, symmetry) + optional call (4) | Deterministic first; LLM vision optional |
| 12 Board optimisation | `consolidate.py` (fixed) + role-aware detail levels | Deterministic |
| 13 Assembly feasibility | Existing `manufacturing.plan_assembly` (wired into results) + insertion-path check later | Deterministic |
| 14 Targeted repair engine | Deterministic rules first, then call (3) with patch output + acceptance gate | Both |
| 15 Rendering and visual feedback | Existing 3D view + headless snapshot for call (4) | Deterministic render |
| 16 Final quality evaluator | Score from diagnostics + completeness + brief match (+ optional vision score) | Deterministic |

The result is **three mandatory LLM calls at most** (brief, geometry, repair), plus one optional vision critique. Everything else is software in the existing Python process.

## 3. New and changed components

### 3.1 Design brief (new, `board_engine/brief.py`)

- **Schema:** see `PROMPT_ENGINEERING_AUDIT.md` §6.1. It covers product class, identity features, overall size, detail level, components (id, role, count, construction, `must_be_closed`, intentional openings, symmetric pair, parent), enclosures, mechanisms (input and transmission edges) and uncertainties.
- **Deterministic validation:**
  - unique ids;
  - counts ≥ 1;
  - parents exist;
  - transmission edges reference mechanism components;
  - one input unless more are declared;
  - sizes agree with parsed requirements.
- **Storage:** stored with the design (`design['brief']`), versioned with it, and editable in the UI before geometry generation.
- **Backward compatibility:** a design without a brief compiles exactly as today. Completeness checks are skipped, with one info diagnostic `NO_BRIEF`.

### 3.2 Board roles (schema addition)

- **Field:** optional `"role": "<brief component id>"` on boards (and on assembly boards, inherited by instances).
- **Inference when absent:** from `group` name similarity (info diagnostic) so that old designs still get partial checks.

### 3.3 Completeness (new, `board_engine/completeness.py`)

| Check | Rule | Diagnostic |
|---|---|---|
| Inventory | each brief component has ≥ count boards (or instances) with that role | `COMPONENT_MISSING` (error), `COMPONENT_COUNT` (error) |
| Symmetry | `symmetric_pair` components are mirror images within 1 mm about the product's centre plane | `ASYMMETRIC_PAIR` (warning) |
| Enclosure closure | for each enclosure: sample rays from outside towards the enclosure's centroid on a grid per declared closed side (or voxelise the union of its boards at ~thickness resolution). Rays that reach the interior without hitting a board are holes. Holes are subtracted where they match declared `intentional_openings` or `kind: "opening"` features. The residual open area is clustered per side | `ENCLOSURE_OPEN` with the side, the bounding box of the gap and the nearest boards |
| Floating decoration | already covered (ISOLATED_BOARD etc.) | — |

Intentional openings are never closed automatically. Only *unexplained* open area is reported.

### 3.4 Schema contract (new, `board_engine/schema.py`)

- **Single source of truth:** one Python definition (dataclasses or pydantic) of `board-design/v1` (+ `v1.1` for role, brief link, axle supports and couple). From it, generate:
  - (a) the JSON Schema served at `/api/v1/canvas/schema`;
  - (b) the field-reference section of `spec_markdown()`;
  - (c) `UNKNOWN_FIELD` with did-you-mean.
- **Versioning:** `format` must be a known version (`FORMAT_UNSUPPORTED` otherwise). `v1` stays accepted.

### 3.5 Kinematics (new, `board_engine/kinematics.py`)

As specified in `MECHANICAL_ENGINEERING_GAP_ANALYSIS.md` §4:
- typed joints with hardware: axle supports, guides, couplings;
- mobility and lock detection;
- branch-tracked closed-form solver, with a Newton fallback for loops;
- adaptive-step swept collision with annulus broad phase and bisection;
- motion-vs-motion interference;
- pins and axles as solids.

`motion.py` keeps its public functions as thin adapters so the front end and existing tests are unaffected.

### 3.6 Repair loop (changed: `routes.py`, `canvas_prompt.py`, new `repair.py`)

1. **Deterministic first:**
   - apply all `safe` fixes (made correct for expanded ids, F-21);
   - integer snapping;
   - flush-alignment snaps within 0.5 mm;
   - slot staggering for `SLOT_ALREADY_USED` (move by the minimum spacing along the contact);
   - duplicate-id renaming;
   - NaN rejection.
2. **LLM patch repair:**
   - **Prompt:** the problem groups, the affected boards plus their direct neighbours, the invariants (inventory, joints currently OK) and the relevant spec sections.
   - **Reply:** `{"patch": {...}}` keyed by board id.
3. **Acceptance gate** `accept(old, new)`:
   - `(errors, blocking, completeness errors)` must not increase lexicographically, and must strictly decrease;
   - no inventory component lost;
   - no untouched board changed;
   - board count change only where the patch says.
4. **Loop control:**
   - at most 3 rounds;
   - stop when the same diagnostic multiset repeats (stall);
   - stop when two consecutive rounds don't improve;
   - report "needs human" with the remaining grouped problems.

### 3.7 Generation transport (changed: `ai_client.py`, `routes.py`, `canvas_prompt.py`)

- **Client:** `ai_client.complete()` returns `(text, finish, usage)` and raises on truncation, refusal and empty replies.
- **Transport flag:** `transport='server'|'chat'` in the prompt builders. Server mode has no multi-part, no file tool, a single-reply budget, and bare-JSON output for Gemini JSON mode.
- **Chunking:** above the single-reply budget, generate per top-level component (from the brief) with shared datums. Merge with the existing part-merge code, and compile after each chunk to catch interface errors early.
- **Job queue:** long AI calls run as background jobs (a job id plus polling or an SSE stream) instead of a synchronous request holding a compile slot (E-16).

### 3.8 Performance (changed: `validation.py`, `joining.py`, `deadline.py`, `consolidate.py`)

- **Spatial index per receiving plate:** an STRtree of feature polygons with a bbox pre-filter in `_eval_tab_slot` and `_station_features`.
- **Fewer evaluations:** evaluate each joint once per join.
- **Exact intersections:** shapely polygon intersection for parallel coplanar overlap (also fixes F-05).
- **Budget enforcement:** deadline checks inside `expand` and the per-board geometry loop. Compiles run in a worker process with a hard kill. The expanded board count is capped by role (viewer or anonymous: 2,000; editor: 20,000; admin: 100,000).
- **Production reuse:** the production pass reuses validation results already computed in the fast pass (prior P-1).

### 3.9 Security (changed: `app.py`, `auth.py`, `routes.py`, `firestore.rules`, legacy JS)

- **Sessions and ownership:** anonymous sessions are `viewer`. Editing needs a login or a signed owner token, and designs carry an `owner`. Delete needs owner or admin.
- **AI quota:** per authenticated user, held in a shared store, with a global daily cap shared across workers. It is charged only when a provider call is made.
- **Legacy stack:** lock the Firestore `designs` rules, stop executing stored JavaScript, and remove the legacy pages from navigation (or retire them).
- **Prompt hygiene:** delimit user text in prompts.

### 3.10 Manufacturing process model (changed: `manufacturing.py`, `cutpaths.py`)

- **Process selection:** `machine.process = laser|router|saw` with `tool_diameter`. Kerf defaults come from the process, not the material.
- **Router relief:** dog-bone or T-bone relief on inside corners of slots, fingers and notches.
- **Configurable constraints:** minimum web, part spacing and edge margins follow the process and the board thickness.

## 4. Phased roadmap

Ordering is by severity and dependency: correctness of what exists first, then intent capture, then advanced capability.

| Phase | Content | Depends on | Est. effort* | Exit criteria (measurable) |
|---|---|---|---|---|
| 0. Safety net | Add regression tests for every finding (all currently failing tests marked `xfail(strict=True)`); prompt-claims test; perf benchmark job | — | S | All new tests present; the 671 existing tests still pass |
| 1. AI pipeline correctness | F-01 truncation; F-02 transport; F-03 acceptance gate + loop control; F-10 requirements plumbing + `hard_constraints`; F-16 NaN; F-12 schema + unknown fields; F-21 safe fixes on expanded ids | 0 | M | xfail tests for F-01/02/03/10/12/16/21 flip to pass; stubbed MAX_TOKENS → 502; regressed fix rejected |
| 2. Validation correctness | F-05 collisions; F-13 consolidation predicate; F-17 assembly plan wiring; F-18 connectivity solids; F-23 tab overhang; F-15 inspection boundary + morph/radial exemptions | 0 | M | C6*, C8*, K1, J16, J07c, C2, C4a probes give the expected diagnostics; existing tests pass |
| 3. Security hardening | F-09 roles, ownership, quota; Firestore rules; legacy JS execution removed | 0 | M | Anonymous DELETE → 403; quota survives a session change; no `import(blob)` / `new Function` on stored data |
| 4. Performance | F-08 spatial index, single evaluation, enforced budget, worker kill; production reuse | 2 (shares validation code) | M | 2,001 slats < 30 s (no production) and < 60 s (production); 20k-board request stopped within budget +10%; joints stage doubling ratio ≤ 2.5 |
| 5. Intent layer | Brief schema + call; board roles; `completeness.py`; brief-aware prompt; UI to review the brief | 1 | L | V1/V2/V3 → COMPONENT_MISSING / ENCLOSURE_OPEN; declared windows and doors not flagged; designs without a brief unchanged |
| 6. Prompt restructuring | Modular prompts (brief / geometry / patch repair); contradictions removed; examples compacted and pinned; profiled-cross_lap advice aligned with phase 7 | 1, 5 | M | Generation prompt ≤ 45k chars; repair prompt for my_home ≤ 40k chars; every example compiles with 0 warnings; LLM benchmark (12 products × 2 providers) improves completeness and error counts vs baseline |
| 7. Geometry capability | Profiled cross_lap; face-to-face (`face_lap`) exposed in v1; detail-level-aware consolidation | 2 | M | Aeroplane probe (profiled fuselage × wing) joins; tree silhouette cross-lap joins |
| 8. Mechanics | Kinematic graph, mobility, adaptive sweep, motion-vs-motion, pin solids, axle supports and retention, rack and belt geometry, pressure angle, branch tracking, knuckle hinge; then cams, bevel (peg or crown) and steering | 2, 4 | L | All 14 acceptance rows in the mechanical gap analysis pass |
| 9. Manufacturing process | Process model, dog-bones, process-based kerf | — | S–M | Router export has relief ≥ tool radius; laser default kerf ≤ 0.3 mm |
| 10. Visual feedback (optional) | Headless render of 4 views; one budgeted vision critique feeding one patch round | 5, 6 | M | Critique round limited to 1; measured recognisability gain on the benchmark; cost per design logged |

\*S ≈ days, M ≈ 1–2 weeks, L ≈ 3–5 weeks for one engineer familiar with the code. These are rough planning estimates, not commitments.

## 5. Risks

| Risk | Mitigation |
|---|---|
| Schema strictness breaks existing saved designs | Unknown fields are a *warning* in v1; strict only in v1.1; a migration test over every stored and example design |
| Completeness false positives (decorative open structures, pergolas, skeleton models) | Enclosures are declared in the brief, not guessed; `open_sides_reason`; opening allow-list; warning severity for inferred (no-brief) checks |
| More LLM calls raise cost and latency | Brief call is small (≤ 2k output tokens); patch repair is smaller than today's full resend; optional vision call is capped at 1; per-design cost logged |
| Kinematic rewrite regresses existing animations | `motion.py` public API kept as adapters; existing motion, gear and linkage tests plus the mechanical acceptance set gate the change |
| Spatial-index refactor changes validation results | Property tests: indexed vs brute-force lookups on random designs must give identical diagnostics (pattern already used in `test_large_designs.py`) |
| Prompt changes cannot be validated without paid calls | Budget a fixed benchmark (≈48 generations); run it before and after phase 6; store outputs as fixtures |

## 6. Measurable acceptance criteria (programme level)

1. Every Critical and High finding has a regression test that failed before and passes after.
2. No design with fewer boards than the LLM produced reaches `ok=True` without an explicit diagnostic (truncation path).
3. For designs with a brief, a missing mandatory component or an undeclared open side always yields an error.
4. Compile of 2,000 boards (one receiving board) in < 30 s; 5,000 in < 120 s, without production.
5. The repair loop never returns a candidate with more errors than its input; it stops on a stall within 3 rounds.
6. The prompt sizes and contradictions from `PROMPT_ENGINEERING_AUDIT.md` are resolved, and a test pins the prompt sizes.
7. On the LLM benchmark set (12 products, 2 providers), after phases 5–6 versus before:
   - mean compile errors per design falls;
   - completeness errors fall to 0 for ≥ 80% of designs;
   - the human recognisability rating does not fall.

   Exact targets should be set from the first baseline measurement, which does not exist yet.
