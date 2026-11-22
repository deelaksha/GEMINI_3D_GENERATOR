# 07 — AI Prompt Update and Regeneration Analysis (incl. Phase 11 prompt optimisation)

## 1. Method and its limits

* **No Gemini.** The application has no Gemini integration and no key exists in this environment. The "AI" in this
  experiment is **two isolated Claude agents (Claude Opus 5.5)**. Each was allowed only to read its prompt files and write
  JSON answers: no repository access, no code execution. This measures the prompts with one capable model. Gemini
  results may differ and are **not verified**.
* Same four products, same settings, same engine (current, post-fix) for scoring:
  * **old prompt** = `build_prompt` at `bf1f44b`;
  * **new prompt** = upgraded `build_prompt`.
* One sample per product and condition: an indication, not a statistically significant comparison.
* All prompts, answers and follow-up messages are kept in `ai_runs/`. Scores: `ai_prompt_comparison.json`.
  Reproduce with `python tests/e2e/score_ai_outputs.py ai_runs/out_old ai_runs/out_new`.

## 2. Prompt changes (Phase 11) [F]

| Weakness found (old prompt) | Evidence | Change |
|---|---|---|
| No handling of missing / conflicting requirements | E07: overall mismatch still compiles | Instruction 1: choose standard values, write `Assumptions: …` |
| No list of unsupported products | guitar, flared boat, toy axles | "What this generator cannot build" with the alternative for each |
| Incomplete decomposition / hierarchy | — | Instruction 2: every board, short ids, one `group` per sub-assembly |
| Shared through-slot conflict not mentioned | wardrobe, stepped storage, desk | Rule: offset by ≥ 60 mm (both left/right and above/below) |
| Mitre convention undocumented | `EDGES_NOT_COINCIDENT` (03) | Mid-plane rule + tested example |
| Joint-name substitutions silent | dovetail → finger | "Joint names" section |
| No support / stability constraints | floating parts allowed | "Support and stability" + `product.mounting` |
| No fastener constraints | both AIs' cabinets blocked by fastener checks | Fastener rule from the catalogue (edge wall, engagement, staggering with `"end"`) |
| No hole-vs-kerf rule, no id length | BUG-002, BUG-003 | Rules + engine fixes |
| No self-check before answering | — | Instruction 10: 5-point self-check |
| No recovery path | user improvises | `build_repair_prompt` (diagnostics **and production blockers**, grouped) and `build_update_prompt` + endpoints + canvas buttons |
| Size | 29.1 k chars | 31.7 k chars (+9 %): new sections outweigh the compacted examples. Not reduced |

Not done: an explicit `parent` field, because nothing consumes it and the joint graph plus groups already define the
hierarchy (see 02). Prompting alone does not enforce geometry: every rule above is also checked
deterministically by the engine, and the claims are tested in `tests/python/test_prompt_upgrade.py`.

## 3. Results — first attempt (identical requirements)

| Product | Old prompt | New prompt |
|---|---|---|
| A Three-column bookshelf | ✘ **does not compile**: 12 `SLOT_ALREADY_USED` (equal shelf heights across dividers) + 24 warnings | ✔ 17 boards, 75/75 joints, 0 warnings, **ready** (middle column offset 100 mm, as the new rule says) |
| B Cabinet, door + 2 drawers | compiles, 41/41 joints; **not ready** (fastener collisions, tool access) | compiles, 40/40 joints; **not ready** (screws into a 6 mm back edge, short screws, collisions) |
| C Wall shelf | ✔ ready, but `TIP_OVER` warning: no way to say "wall-mounted" | ✔ ready, `mounting: "wall"`, 0 warnings |
| D Toy car with wheels on axles | compiles; **not ready**: axles modelled as 24 mm boards (`PART_BELOW_MIN_SIZE`), `OVERALL_MISMATCH`; wheels fixed to axles | ✔ ready: wheels and axles left out as the prompt instructs, 7 mm axle holes for bought axles, stated in the description |
| **Compiles** | 3/4 | **4/4** |
| **Ready for production** | 1/4 | **3/4** |
| Designs with warnings | 3/4 | **0/4** |
| States assumptions | 0/4 | **4/4** |

## 4. Results — repair round (Phase 7: iteration after errors)

| Design | Old: user pastes the error list by hand | New: generated repair prompt |
|---|---|---|
| A bookshelf | ✔ fixed in one round: moved 3 shelves, 15/18 boards kept identical | — (nothing to repair) |
| B cabinet | ✔ fixed in one round: 19/20 boards kept identical | ✘ round 2 **not fixed**: my repair prompt cut the list at 40 lines ("… and 10 more"), so the AI had to guess |
| B cabinet, round 3 | — | ✔ fixed after the repair prompt was corrected (repeats grouped, nothing truncated): 20/21 boards identical, ready |

This was a real defect in the new repair prompt, found by the experiment and fixed (`_problem_lines` groups repeats).
After the fix the repair prompt works. A raw pasted error list also worked well with a capable model. The repair
prompt's main value is the complete problem set (including production blockers) and the "keep everything else" instruction.

## 5. Results — update round (incremental change)

Change request: "Make the shelf 250 mm deep instead of 200 mm" (wall shelf C).

| | Old (plain request) | New (update prompt) |
|---|---|---|
| Compiles / ready | ✔ / ✔ (still `TIP_OVER`: no mounting) | ✔ / ✔ |
| Boards changed | shelf + both brackets; rail identical | shelf + both brackets; rail identical |
| Dependent geometry updated | brackets lengthened to keep supporting the deeper shelf | same |
| Change explained | in its reply only | in `product.description` assumptions |

Both preserved the unaffected board and updated the dependants. The update prompt made no measurable difference here.
The task was simple and the model capable.

## 6. What the application now does for updates and history

* **Preserve unaffected components**: the update prompt instructs it; the engine cannot enforce it. Preservation is
  measured board by board (`score_ai_outputs.preservation`), and all four update/repair rounds kept every unrelated board identical.
* **Recalculate joints, layouts, 3D, collisions, cutting, documents**: automatic. Every compile regenerates everything from the JSON (06 §3).
* **Version history and restore** [F]: every saved revision is snapshotted (file store: `versions/<id>/<rev>.json`, last
  100; Firestore: `versions` subcollection). `GET /designs/{id}/versions`, `GET …/versions/{rev}`, `POST …/restore`
  (non-destructive: it saves a new revision). The canvas "update saved project" no longer resets the revision to 1.
  Tested in `test_versions_list_get_and_restore` and `test_firestore_store_keeps_versions`. There is no restore button in the UI yet.
* **Not regenerating the whole design**: in the Studio, edits are per component. In the canvas, every compile is a full
  recompile of the JSON, which takes about 1 s for typical products and is deterministic. The AI is asked to change only
  the affected boards.
* **Conflicting / ambiguous / repeated updates**: the update prompt asks for the smallest reasonable interpretation, stated in the
  description. Not exercised beyond the rounds above.

## 7. Not tested

* Gemini specifically; several samples per condition; multi-step update chains longer than two rounds; changes such as
  "change the material thickness" by the AI (the engine side is covered by BUG-008).
