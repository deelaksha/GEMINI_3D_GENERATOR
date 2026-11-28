# Prompt Engineering Audit

Scope:
- `board_engine/canvas_prompt.py`, working tree including the uncommitted +76-line diff;
- `board_engine/ai_client.py`;
- the canvas routes in `board_api/routes.py`;
- `js/canvas/main.js`, `canvas.html`;
- the legacy `ai-prompt.txt`.

The generated prompts, size measurements and probe scripts are in `evidence/prompt/`:
- `build_prompt_aeroplane*.txt`, `repair_*.txt`, `update_*.txt`, `sizes.json`;
- `probe*.py` / `.out` (compiler probes of prompt claims);
- `compile_runs.py` / `.out` (re-compilation of the earlier LLM outputs).

**Most important caveat:** the current prompt (98k characters) has **never been run against an LLM**. Every recorded LLM run (`PROJECT_AUDIT/END_TO_END_VALIDATION/ai_runs/`) used the earlier 31.7k-character prompt, with Claude agents, on furniture and toys. Every statement below about *how a model reacts* is therefore a reasoned expectation, labelled "needs LLM testing". Every statement about *what the prompt says vs what the compiler does* was verified.

---

## 1. Inventory of prompts

| Builder | Used by | Size (chars) | ≈ tokens | Asks the model to return |
|---|---|---|---|---|
| `spec_markdown()` | embedded in all below except integer-fix; `docs/board-design-format.md` | 63,937 | 16.0k | — |
| `build_prompt(...)` (no images) | `/canvas/prompt` (copy-paste), `/canvas/ai-generate` (server) | 98,359 | 24.6k | complete design + large `plan` |
| `build_prompt(..., images=True)` | copy-paste only | 103,021 | 25.8k | same + reference inventory |
| `build_repair_prompt` (5.2k source) | `/canvas/repair-prompt`, `/canvas/ai-fix` | 79,728 | 19.9k | complete design |
| `build_repair_prompt` (`my_home.json`, 341 boards) | same | 396,936 | ~99k | complete design (cannot fit the output limit) |
| `build_update_prompt` (5.2k source) | `/canvas/update-prompt` | 89,825 | 22.5k | complete design |
| `build_integer_fix_prompt` | `/canvas/integer-fix-prompt` | 8,552 | 2.1k | complete design |
| `ai-prompt.txt` (legacy) | `/api/prompt`, legacy nav modal | 85k | 21k | a JavaScript module in the old "PuzzleCore" format, which the canvas compiler does not accept |

- **Growth:** 29.1k (`bf1f44b`) → 31.7k (when the recorded LLM runs were made) → 98.4k now, a 3.1× increase with no measurement.
- **Largest sections of `build_prompt`:** Complex cuts 9.5k, connection reference 7.5k, INSTRUCTIONS 6.6k, cottage example 5.4k, Detailed models 5.4k. The four complete examples take 16.5k (17%).

## 2. What kind of designer the prompt asks for

The prompt asks one model call to be a five-person team: Analyst, Designer, Architect, Joinery engineer and Inspector (`DESIGN_TEAM`, L1427-1446). The team works "in your head; the only output is the JSON". It must also write a large `plan` with reference, datums, concept, economy, assemblies, steps, joints, an audit of 10 boards and self-scores (Instruction 2, L1930-1950).

**Assessment:**
- The prompt *does* try to make the model behave as an engineering designer, not just a JSON generator. Its domain content is rich and largely correct: datums, dimension chains, joint decision rules, the "ladder" for shapes that can't be made in one piece, and realism guidance.
- **The problem is structural.**
  - Planning, design, engineering and inspection are requested in one pass, in prose, and none of it is checked by software.
  - The `plan` is discarded by the compiler (`canvas.py:233-241` only merges it across parts).
  - The self-scores and "audits" consume output tokens that compete with the design itself (see P-02), and they create an illusion of verification.
  - `SUCCESS_CRITERIA` (L1448) says "the compiler measures every one of these … every inventory item present". That claim is false.

## 3. Findings

Format: ID · severity · classification · location · exact existing text · why it fails · proposed instruction or fix. Evidence files are in `evidence/prompt/`.

### P-01 · Critical · Confirmed bug: the server path asks for multi-part or file-tool delivery
- **Location:** `canvas_prompt.py:1411-1418` (OUTPUT_CONTRACT), `1636-1644` (`scope`), `1818-1840` (`_contract` file mode); `routes.py:1039`; `main.js:198,210` (`m.file = true` is sent to ai-generate).
- **Existing text:**
  - "MULTI-PART REPLIES: if the complete design will not fit in one reply, split it - never shorten it. … the user answers "continue" for the next part."
  - "Use your code / file tool: write a short script that BUILDS the design … Do NOT paste the JSON in the chat."
- **Why it fails:** `/canvas/ai-generate` makes one tool-less call and never says "continue". Part 1 compiles to `PART_MISSING`, which is then fed to `/ai-fix` as a "problem".
- **Proposed instruction (server transport):**
  > "You have exactly ONE reply and no tools. Reply with the complete design as one JSON object. Keep it within about 1,500 lines: express repetition with `repeat`, `radial`, `morph`, `mirror` and `assemblies` / `instances` rather than listing copies. If the object needs more, build the most important sub-assemblies fully and list what was omitted in `product.description`. Never split the answer into parts."
- **Code fix:** `build_prompt(..., transport='server')`; strip `machine.file` on server endpoints.

### P-02 · High · Confirmed bug: truncation is invisible
- **Location:** `ai_client.py:46` (`maxOutputTokens: 65536`), `:58-60`, `:73` (`max_tokens=64000`), `:86-90`.
- **Why it fails:** `finishReason=MAX_TOKENS` and `stop_reason=max_tokens` are ignored whenever any text came back. That leads straight to the critical silent-incomplete-design path (ENGINEERING_AUDIT_REPORT F-01). Thinking tokens (Gemini 2.5 Pro thinking; Claude effort `xhigh`) may count against these limits (needs testing).
- **Fix:** raise `AIError('truncated')`. Add to the prompt: "Your reply has a hard output limit; the plan, if any, is at most 40 short lines."

### P-03 · Medium · Prompt engineering issue: output-format contradictions
- **Existing text:**
  - "Reply with exactly ONE ```json code block" (L1402);
  - "Return **one** fenced ```json code block" (spec, L1369);
  - FINAL_REMINDER (L1424) and Instruction 11 (L1997);
  - meanwhile Gemini is called with `responseMimeType: application/json` (ai_client.py:46).
  - "do the work in your head; the only output is the JSON" (L1427) vs a mandatory large written `plan`.
- **Why it fails:** the format rule is stated 4 times, and in JSON mode a fence is impossible. `_extract` (canvas.py:99-107) copes with a bare object. If Gemini instead returns the fenced text as a JSON *string*, parsing breaks (needs LLM testing).
- **Proposed:** state the format once, per transport. Server: "Output the bare JSON object (no fences, no prose)." Copy-paste: keep the fence. Delete "in your head".

### P-04 · Medium · Prompt engineering issue: mandatory plan, ignored by software
- **Existing text:** Instruction 2 "PLAN FIRST: write a top-level "plan" before "boards" … "audit": at least 10 boards recomputed … "checks": the tick-off …"; f0b "SCORE the design 1-5 on …".
- **Defects:**
  - the spec's own plan field list names `"reference"?` twice (L991-992);
  - the plan example (L1115-1160) omits `steps` and `economy`, which other sections require.
- **Why it fails:** thousands of output tokens buy no verification. The real need (an inventory that software checks) is not met.
- **Proposed:** replace it with a *separate*, small, schema-validated **design brief** (see §6.1) that the compiler checks. In the generation prompt:
  > "Copy the design brief's component ids into each board's `role` field; do not write audits, scores or check lists."

### P-05 · High · Confirmed bug: `hard_constraints()` corrupts the requirements
- **Location:** `canvas_prompt.py:2056-2090`.
- **Reproduced:** `"1200 x 600 x 750 mm desk, 18 mm plywood, simple realistic"` gives:
  ```
  - x: 750 mm
  - a size: 18 mm
  - detail level: 5 (every visible element, fine detail included)
  ```
  `"A 200 mm long toy car"` gives `- A: 200 mm`.
- **Why it fails:** the model receives HARD CONSTRAINTS that contradict the user's intent and the compiler's own `L x D x H` rule (`requirements.parse_sizes` gets it right).
- **Fix:** build the HARD CONSTRAINTS block from `requirements.parse_sizes` plus explicit material and thickness parsing. Map detail words explicitly (simple → 2 … collector → 5), and emit nothing when the words conflict.

### P-06 · Medium · Confirmed bug: requirements are not on the repair path
- **Location:** `routes.py:762` and `:1060`: `compile_source(...)` without `requirements=`. `/canvas/compile` (`:848`) passes them.
- **Why it fails:** `REQUIREMENT_MISMATCH` never reaches the repair prompt, and the repair prompt has no REQUIREMENTS section.
- **Fix:** pass `requirements` on both routes and from `aiFixLoop`. Include a REQUIREMENTS block in the repair prompt.

### P-07 · Medium · Prompt engineering issue: three conflicting curve strategies (introduced by the diff)
- **Existing text:**
  - L921 "6-12 points make any organic outline … instead of 40-100 polygon points";
  - L1519 "compute the points from the curve … every 5-10 degrees or 5-20 mm" (plus a hand-computed 24-point superellipse, L1523-1527);
  - L1782 "polygon / path points … about every 5% of length along curves".
- **Proposed (replaces PRECISION 5 and IMAGE_SPEC 5):**
  > "Curves: `superellipse` for rounded sections, `spline` through 6-12 points for free outlines (mark straight tab edges with two `corners`), `arch` / path `arc` for circular arcs. Explicit polygons only for faceted shapes. Boards that rest on a curve use the same curve."

### P-08 · High · Prompt engineering issue: recommends constructions the compiler rejects
- **Existing text:**
  - L1101 "a tree or bush = a few interlocking silhouette boards (cross_lap them for volume)";
  - L1565 "ROUND AND CYLINDRICAL PARTS … stacked discs, cross-lapped pairs";
  - L1457-1458 "waffle / egg-crate frames, stacked contour slices";
  - L1232 "double it with a crossing piece (cross_lap)".
- **Evidence:** profiled cross_lap gives `JOINT_NEEDS_PLAIN_BOARD` (canvas.py:1567-1568); stacked discs give `NO_CONTACT` / `NOT_JOINED` (`probe.out`, `probe3.out`).
- **Proposed (until profiled cross_lap exists):**
  > "cross_lap joins only two PLAIN rectangles. A shaped board (any `profile`) joins by tab_slot along a straight edge onto a plain board. Never stack boards face to face. A round solid is radial fins on a hub, or ribs on a plain spine."
- **Better:** implement profiled cross_lap (ENGINEERING_AUDIT_REPORT F-11), then keep the original advice.

### P-09 · High · Missing capability (prompt omission): no slotted profiled cross-halving, and the "cannot build" list does not say so
- **Fix (if not implemented):** add to "What this generator cannot build":
  > "Two shaped boards slotted through each other (a wing through a fuselage profile): use a plain rectangular core where they cross, or tab one onto the other's face."

### P-10 · Medium · Confirmed bug: "0 warnings" is unattainable with the engine's own generators
- **Existing text:** SUCCESS_CRITERIA "0 errors and 0 warnings" (L1449); repair rule "Fix every [WARNING] too" (L2119); "clearly offset (>= 5 mm)" (L1283).
- **Evidence (`probe2.out`):**
  - the prompt's own morph rib example compiles with 0 errors, 2 × `MISMATCHED_PAIR` and 3 × `MISALIGNED`;
  - 4 radial blades give 4 × `MISALIGNED` "5.0 mm apart … (>= 5 mm)";
  - `inspection.py:191` uses `TOUCH < d <= STEP`, so an exact 5.0 mm offset is flagged while the message calls ≥ 5 mm deliberate.
- **Fix:** compiler: `d < STEP`, and exempt generated copies of one morph or radial from the twin and flush checks. Prompt:
  > "Target 0 errors; warnings are advice. Warnings between copies generated by morph / radial may be left."

### P-11 · Low · Prompt engineering issue: integer rule vs example decimals
- **Existing:** L865 "NEVER floating-point fractions"; L1722 "profile / opening / engraving coordinates are whole millimetres"; linkage example `[[7.6, 1.9], [206.2, 79.2], …]` (8 NON_INTEGER issues). Rotate angles like `28.0725` are allowed, but the prompt never says angles are exempt.
- **Fix:** round the example points; add "angles may have decimals".

### P-12 · Low · Prompt engineering issue: conflicting part-count philosophy
- **Existing:** "hundreds are fine; there is no part limit" (L1303); "a faithful model … often needs hundreds or thousands of boards" (L1407); "Fewer boards is fine …", "Judge a design … NOT by how many boards" (L1644, L1094); "keep the part count … as low as the concept allows".
- **Why it fails:** the model gets permission to explode the part count and an instruction to minimise it in the same prompt. With no detail-level control, it will pick arbitrarily.
- **Proposed single rule:**
  > "Part count follows the DETAIL LEVEL (1-5, given below). At every level: as few boards as the visible 3D depth needs; detail lying in one plane is ONE board's outline, openings and engravings. A higher level adds new visible features and depth layers, never more copies of the same part."

### P-13 · Medium · Token waste: bloated examples that show none of the new features
- `{json.dumps(EXAMPLE, indent=2)}` (L1375) prints one number per line, against Instruction 11 ("number arrays on one line").
- All examples: 18.6k as printed, 9.5k one-board-per-line.
- `spline`, `superellipse`, `morph` and `radial` appear in no complete example.
- **Fix:** one-board-per-line printing. Replace the plain study table with a compact organic example (keel + morph ribs + radial + wildcard connection + one motion) that compiles with 0 warnings, pinned by a test.

### P-14 · Medium · Repetition (≈10–15k characters recoverable)
- The output format is stated ×4, thickness arithmetic ×3, slot spacing ×4, and the self-check twice (Instruction 10 plus INSPECTOR) plus PRECISION 8.
- Silhouette and identity guidance is repeated in REALISM, ANTI_PATTERNS, CREATIVE BRIEF and SIGNS_OF_LIFE.
- "Native engine format (advanced)" (L1361-1366) documents a format the LLM must not use.
- **Fix:** one canonical rule list; delete the native-format section from LLM prompts.

### P-15 · High · Repair prompt does not scale and has no regression contract
- **Location:** `canvas_prompt.py:2091-2155`.
- **Good:** preserves ids, order and shaped boards; groups problems (≤60 distinct); puts loose parts first; adds LIKELY ROOT CAUSES.
- **Gaps:**
  - a full design is always returned;
  - the full 64k spec and full source are embedded (397k chars for `my_home`);
  - there is no list of invariants to preserve;
  - every warning must be fixed;
  - it references `plan.datums`, which most designs lack;
  - line numbers refer to the merged source, not "your previous JSON";
  - there is no limit on the number of boards touched.
- **Proposed instruction (with a compiler-side merge):**
  > "Return ONLY `{"patch": {"boards": [complete objects for changed or added boards, matched by id], "connections": [...], "remove": ["id", ...]}}`. Everything not listed stays exactly as it is. Change only the boards named in the problems and, if unavoidable, their direct neighbours. Do not rename ids."
- **Spec content:** embed only the spec sections the diagnostic codes refer to, plus a 2k field reference.

### P-16 · Medium · The update prompt invites redesign
- **Existing:** `build_update_prompt` (L2193-2256) embeds DESIGN_QUALITY ("A static product is the dull default"), REALISM_PLAYBOOK, UNIVERSAL_METHOD and SIGNS_OF_LIFE (≈10k), while its rule 2 says "Change only those".
- **Fix:** drop the creative blocks from update prompts unless the change asks for embellishment. Use the patch format.

### P-17 · Medium · "Signs of life" contradicts the motion and exactness rules
- **Existing:**
  - "GESTURE: … a lid or door slightly open" (L1580) vs "drawn at position 0 of every motion (closed lid, drawer in)" (L1127);
  - "NATURAL VARIATION: … vary slightly" (L1586) vs MISMATCHED_PAIR / UNEVEN_SPACING warnings;
  - "successive sections change by at most about 15%" (L1564) vs the morph example's +33% first step.
- **Proposed:**
  > "Pose is expressed through motions (their range), never by drawing a part open. Twins and spacing are exact; vary deliberately by ≥ 5 mm or one thickness."

  Fix the morph example to steps of ≤ 15%.

### P-18 · High · Missing capability: no completeness or closure rule, and nothing verifies it
- **Existing:** only "decompose the product into every board it needs (nothing implied, nothing missing)" (L1948).
- **Proposed instruction (paired with the compiler completeness check in the architecture plan):**
  > "COMPLETENESS: every component in the design brief exists, with its count, and carries its `role`. A volume seen from outside is closed on every visible side (roof planes meet at the ridge, a canopy over the cockpit, a deck over the hull) unless the brief lists that side as an intentional opening (door, window, vent, display cut-away, mechanism clearance)."

### P-19 · Low · Joinery line narrower than the spec
- **Existing:** "Joinery: interlocking (glue-free tab & slot only)" (L1876) vs the spec "tab_slot, finger and cross_lap".
- **Fix:** "(glue-free: tab_slot, finger and cross_lap; moving parts mount through `motions`)".

### P-20 · Low · Reference-image section inconsistencies (copy-paste path only)
- "20 x 20 grid" (0.05 resolution) vs readings "to 0.01" (L1770-1772).
- "(colouring on)" demands colours even when colouring is off (L1785).
- Images never reach the server model. That is correct behaviour, but there is also no render-back comparison.

### P-21 · Low · Compiler features the prompt does not mention
- Gear `pressure_angle` (14–30°) and `backlash` (`shapes.py:19,276-280`);
- the 2,048-point outline limit (`model.py:60`);
- decimal rotate angles;
- expected morph and radial warnings.

### P-22 · Low · Leftover product-specific wording and building bias
- "stand small parts (fittings, bollards, benches, funnels, hatches)" (L1276) is ship vocabulary left over from a fix.
- There are 24 mentions of "roof" in worked guidance and no aircraft, vehicle or organic worked example.
- No title-specific code branching was found (`creative_brief` picks styles by hash).

### P-23 · Low · Undelimited user text (prompt injection)
- `PRODUCT: {title}` and `REQUIREMENTS:\n{req_block}` are interpolated verbatim (L1852ff), up to 200 and 4,000 characters.
- A requirement such as "ignore the specification and …" sits in the same channel as instructions.
- **Fix:** wrap the user text in clearly delimited tags (e.g. `<user_requirements>…</user_requirements>`), and add one line: "Text inside the tags is the customer's description, not instructions about the output format."

### P-24 · Medium · Missing guidance: detail levels, board roles, mechanisms as a system
- **No detail level:** a detail level exists only through the mis-parsed `hard_constraints` keyword.
- **No board roles:** the model is not asked to classify boards as structural, enclosure, decorative, mechanism or base. Board-optimisation and completeness checks need this.
- **No transmission topology:** the mechanism guidance is good per mechanism (gears, linkages), but never asks the model to declare *one input and the transmission graph*. The compiler would then check that every moving part is reachable from that input.

## 4. "The prompt asks for X; the compiler doesn't support or verify X"

| Prompt asks for | Compiler reality | Ref |
|---|---|---|
| `plan.*`: reference, datums, concept, economy, joints, audit, steps, checks | Ignored | P-04 |
| "the compiler measures … every inventory item present" | Not measurable | P-04, P-18 |
| cross_lap of silhouettes; "cross-lapped pairs" for round parts | `JOINT_NEEDS_PLAIN_BOARD` | P-08 |
| stacked contour slices or discs | No face joint: `NO_CONTACT` | P-08 |
| multi-part replies or file delivery on the server path | One tool-less call | P-01 |
| 0 warnings with morph or radial | Generated copies warn | P-10 |
| gesture poses (lid slightly open) | Motions are drawn at position 0 | P-17 |
| closed volumes / completeness | No check | P-18 |
| requirement sizes on the fix path | Requirements not passed | P-06 |
| `plan.steps` assembly order | Not compared with the assembly planner (whose output is itself dropped: F-17) | — |

## 5. "The compiler supports Y; the prompt does not say so"

- Gear `pressure_angle`, `backlash`.
- The outline point limit of 2,048.
- Decimal angles.
- The assembly planner (`manufacturing.plan_assembly`): the prompt could tell the model that the order is computed, and stop asking it to write `plan.steps`.

A scripted check of every JSON key quoted in the prompts found every documented board, connection and motion field consumed by the engine. Only the plan sub-keys are unconsumed.

## 6. Proposed prompt architecture and improved prompts

The goal: **smaller prompts with one responsibility each, structured intermediate outputs, and every claim backed by a software check.** This needs at most three LLM calls per design (brief → geometry → targeted repair), plus an optional, budgeted vision critique. See `ARCHITECTURE_IMPROVEMENT_PLAN.md` §3.

### 6.1 Call 1: Design brief (planning). Target ≤ 8k-token prompt, ≤ 2k-token reply

```
SYSTEM
You are the lead product engineer for a flat-board (laser / CNC) model kit. Before any geometry is drawn you
produce a DESIGN BRIEF: what the product is, what it must contain, how it is structured, what moves, and what
must be open or closed. Output ONE JSON object matching the schema below. No prose.

Schema (abridged; full JSON Schema attached by the server):
{ "product_class": "building|vehicle_air|vehicle_land|vehicle_water|creature|furniture|mechanism|scene|other",
  "identity_features": [str, 3..6],                  // what makes it recognisable, in priority order
  "overall_mm": {"length": int, "height": int, "depth": int},
  "detail_level": 1..5,
  "components": [ { "id": "FUSELAGE", "role": "structure|enclosure|surface_detail|mechanism|base|decor",
                    "count": int, "symmetric_pair": bool, "parent": id|null,
                    "construction": "plain_panel|profiled_panel|ribs_on_spine|radial_fins|facets|layered_relief|gear|linkage",
                    "must_be_closed": bool, "intentional_openings": [ "door", "window x4", "cockpit_glazing" ] } ],
  "enclosures": [ { "id": "HULL", "components": [ids], "closed_sides": ["top","sides","front","back","bottom"],
                    "open_sides_reason": str|null } ],
  "mechanisms": { "input": {"kind": "hand_crank|motor|none", "component": id|null},
                  "transmission": [ { "from": id, "to": id, "via": "gear|rod|shared_axle|belt|rack" } ] },
  "uncertainties": [str]                             // what the description/reference does not determine
}

Rules:
- Components are what a viewer would name ("left wing", "roof plane south"), not boards.
- Mark must_be_closed for every volume seen from outside; list deliberate openings explicitly.
- detail_level: 1 silhouette only … 3 standard … 5 collector (adds depth layers and real features, never more copies).
- If a reference image is attached: list only what it shows plus hidden structure needed to build it; put guesses
  in "uncertainties".

<user_requirements>
{title}
{requirements}
</user_requirements>
```

The server validates the brief against the schema, applies explicit UI choices (material, thickness, detail, size), shows it to the user for a one-click edit, and passes it to call 2.

### 6.2 Call 2: Geometry generation. Target ≤ 35k-token prompt (spec subset), one reply

Keep the existing domain content, but restructure it:

1. **Contract** (transport-specific, stated once).
2. **The brief** (JSON) plus **acceptance rules**:
   > "every component id appears as the `role` of ≥ 1 board (`"role": "FUSELAGE"`), with the brief's count; every `must_be_closed` enclosure is closed except its listed openings."
3. **One canonical rule list:** geometry, joints, slots, integer rule, thickness arithmetic. Each rule appears once.
4. **Spec subset** chosen from the brief:
   - mechanisms present → Moving parts, Gears and Linkages sections;
   - `ribs_on_spine` → morph and ribs;
   - buildings → tilted panels;
   - always → board, connection and profile reference.

   Estimated 25–35k characters instead of 64k.
5. **Two compact examples**, printed one board per line, each pinned by a test to compile with 0 warnings.
6. Short realism guidance, merged from REALISM_PLAYBOOK, ANTI_PATTERNS and SIGNS_OF_LIFE with the contradictions removed (P-17).
7. Remove the self-scoring, audits and the 5-specialist role-play from the *output*. The checking is done by software.

For designs whose brief exceeds the one-reply budget, call 2 runs **per top-level component group**. Each call receives the brief, the datums, and the already-generated neighbour boards' ids and bounding boxes. The server merges the results (the multi-part merge machinery already exists in `canvas._merge_parts`).

### 6.3 Call 3: Targeted repair. Target ≤ 15k-token prompt

```
You repair a flat-board design. The compiler found the problems below. Return ONLY:
{"patch": {"boards": [complete objects for boards you change or add, matched by id],
           "connections": [complete objects you change or add], "remove": [ids]}}
Rules: change only boards named in the problems and, if unavoidable, their direct neighbours (listed below);
never rename ids; never remove a component's last board (component inventory below); keep every joint marked OK.
PROBLEMS (grouped, root causes first):            {≤ 30 grouped lines}
NEIGHBOURHOOD (the affected boards and their direct neighbours, one per line):   {...}
INVARIANTS: component inventory with counts; enclosures; joints currently OK: {n}
RELEVANT RULES: {only the spec sections referenced by the diagnostic codes}
```

The server applies the patch, recompiles, and accepts it only if the acceptance gate passes (ENGINEERING_AUDIT_REPORT F-03).

### 6.4 Optional call 4: Visual critique. Budgeted, at most 1 per design

- Render 4 standard views (front, side, top, ¾) from the compiled model.
- Send them, with the brief and the reference images if any, to a vision model.
- It answers with a structured discrepancy list: `{component, issue: missing|wrong_shape|wrong_count|wrong_proportion|open_surface, severity}`.
- The list feeds call 3 at most once. It is never an open-ended regeneration loop.

## 7. Measurement plan (required before and after prompt changes)

- **Product set:** 12 products, two per category (building, aircraft, land vehicle, ship, creature, mechanism), × 2 providers × 2 prompt versions.
- **Metrics per run:**
  - compile errors and warnings;
  - completeness score (brief components present, enclosures closed);
  - board count;
  - input and output tokens and latency;
  - repair rounds to 0 errors;
  - a human 1–5 recognisability rating from the 4 standard renders.
- **Cost:** about 48 generation calls plus repairs. Requires approved API budget, **not run in this audit**.
