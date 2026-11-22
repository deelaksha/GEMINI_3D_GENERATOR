# 02 — AI Generation Quality Analysis

## 1. What can and cannot be measured

* The app does not call Gemini (see 01 §0). **No live Gemini run was performed for this audit, and no Gemini success rate is claimed.**
* The repository holds **4 real AI outputs** (`tests/python/fixtures/ai_{bookshelf,birdhouse,winerack,cabinet}.json`).
  Commit `bf1f44b` says they came from "four independent AIs" that used the generated prompt, all compiling with 0 errors.
  The fixtures do not record which model wrote them, how many attempts it took, or whether they were edited, so
  **first-pass success rate is unknown**. They compile clean today (`test_ai_written_designs_compile_clean`, passing).
* What this audit measured: how the prompt is built, and how the compiler handles 30 AI-shaped inputs, including the typical
  LLM failure modes. Reproduce with `python -I PROJECT_AUDIT/repro/scenarios.py <repo>` (results in `repro/scenario_results.json`).

## 2. Prompt pipeline (`board_engine/canvas_prompt.py`)

| Property | Finding |
|---|---|
| Source of truth | Spec text is generated from engine constants (`TOL`, `LIMITS`, `MATERIALS`, `FASTENERS`, `CONNECTION_TYPES`, `JOINERY_MODES`, `HINGE`). Good: the documentation cannot drift from the code. Tests assert every documented field exists (`test_complex_cuts.py:253`). |
| Size | `build_prompt('Bookshelf', …)` = **28 873 chars, 999 lines, ≈7.2 k tokens**. |
| Worked examples | 3 complete examples = **47 %** of the prompt. `COMPLEX_EXAMPLE` and `STRUCTURES_EXAMPLE` are printed with `json.dumps(indent=2)`, which puts every number of every `[x, y, z]` on its own line. The same examples are 12 985 chars this way, 10 563 with the project's own `canvas.pretty_json` and 6 296 compact. |
| Structure | Role → task → product → requirements → 8 instructions → spec → 3 examples → usage note. There is no self-check step, no "if requirements are missing, state assumptions" rule and no list of unsupported product features (see §4). |
| Requirements input | Free text ≤ 4 000 chars plus optional material, thickness and joinery (`routes.py:537-550`). No image input. The brief's "images" input does not exist. |

## 3. Compiler behaviour on AI-shaped input (measured)

| # | Input | Result | Verdict |
|---|---|---|---|
| E01 | JSON with a missing comma | `JSON_SYNTAX` with line/column | ✔ good |
| E02 | JavaScript instead of JSON | `JSON_SYNTAX` + "This looks like JavaScript… ask the AI to return JSON only" | ✔ good |
| E03 | Prose + fenced ```json block | compiles (fence extracted) | ✔ good |
| E04 | `//` comments + trailing commas | compiles | ✔ good |
| E05 | No `material` | `MATERIAL_MISSING` | ✔ |
| E06 | Board with no `size` (missing dimensions) | `BOARD_GEOMETRY` | ✔ rejected; nothing is invented |
| E07 | `overall.length` 1500 but boards span 1200 (conflicting dimensions) | **compiles, ok=true**, only a `OVERALL_MISMATCH` warning | ⚠ a design that contradicts the stated requirement is "ready for production" |
| E08 | Top board 20 mm in an 18 mm material | `THICKNESS_MISMATCH` | ✔ |
| E09 | Unknown joint type `glue` | `CONNECTION_TYPE` lists the valid types | ✔ |
| E10 | `mortise_and_tenon`, keys `from`/`to`, lower-case ids | compiles; 3 "normalised" warnings teach the exact names | ✔ forgiving |
| E11 | 40-char board ids + `"connections": "auto"` | **`COMPILER_ERROR: TypeError: unsupported operand type(s) for +: 'NoneType' and 'int'`** | ✘ **BUG-003** |
| E13 | Hinge `count: 12` | `SCHEMA_ERROR joint.count must be an integer 1..8` with **no connection id and no line** | ⚠ BUG-009 |
| E14 | Duplicated board under a new id | 8 `COLLISION` errors | ✔ caught |
| E15 | Board not connected to anything | **ok=true, ready_for_production=true**, `FLOATING_COMPONENT` warning only | ⚠ BUG-007 |
| E16 | Opening centre outside the board | `FEATURE_OUTSIDE_OUTLINE` | ✔ |
| E17 | Empty paste | `EMPTY_SOURCE` | ✔ |
| E18 | Native engine format | compiles | ✔ |
| E19 | Part 3000 × 1500 mm | `PART_EXCEEDS_SHEET`, no split suggestion | ✔ (could suggest splitting) |
| 03b | Classic mistake: legs = overall height (no thickness subtraction) | `CONNECTION_OVERLAP` "…exactly its thickness: leg height = overall height − top thickness" plus resize/move fixes; applying the first fix per error converges to ok=true | ✔ excellent |
| — | Same input compiled twice | identical design + summary (ignoring `joined_at` timestamps) | ✔ deterministic |

## 4. Hallucination and failure classes the prompt does not prevent (measured in 06)

| Failure class | Example | What happens | In prompt? |
|---|---|---|---|
| Face-on-face assembly (lamination) | Guitar neck lying on the body face | `NO_CONTACT` for tab_slot/butt; finger/cross_lap refuse. **No v1 connection can express it**: `face_lap` exists in the engine but not in `board-design/v1`. | No |
| Angled meeting without bevel | Boat with flared sides on a flat bottom | `NO_CONTACT`: a tilted board's edge is never parallel to the flat face | No (only "same pitch" roof case) |
| Shared through-slot | Wardrobe shelves at the same height on both sides of a divider | `SLOT_ALREADY_USED` + `COLLISION`; staggering by 60 mm compiles clean | **No** |
| Moving parts | Drawer box, wheels on an axle, lid | Floating warnings or collisions; no slide, axle, rotating joint or loose-part concept | No |
| Round stock | Axle drawn as a 6 × 6 board | Collides with the round holes; `PART_BELOW_MIN_SIZE` | No |
| Parallel attachment | Keyboard tray connected "into" the top it hangs under | `NO_CONTACT`; it works once hanger boards are added | Partly (rule 1 says end face on face) |
| Over-long ids | Descriptive ids ≥ 30 chars | Crash with `auto` (BUG-003) | No |
| Very small holes | 3 mm pin hole in 18 mm plywood | Cut with a negative radius (BUG-002) | No |

## 5. Regeneration and iteration

* **Fix loop**: compile → diagnostics carry `fixes[]` with `edits` → `/canvas/fix` rewrites the JSON (`apply_code_fix`)
  → recompile. Verified convergence on the leg-height mistake.
* `apply_code_fix` **re-serialises the whole document** (`pretty_json`), so the AI's comments and key order are lost after the first fix.
* A fix marked `safe: true` can lead to a new error: the cross_lap suggestion for an axle through a profiled side
  (`canvas.py:1342`) gives `JOINT_NEEDS_PLAIN_BOARD` (BUG-006). The canvas "apply all safe fixes" loop (`js/canvas/main.js:353-361`) retries up to 10 times.
* **Regeneration after editing**: there is no "send diagnostics back to the AI" step. The user has to paste errors into
  the chatbot by hand. Studio edits change the native design, not the v1 source, so a design edited in the Studio cannot be
  round-tripped to the AI (`source.code` keeps the original paste only).
* No per-component regeneration exists (see 05).

## 6. Assessment

The compiler is the strongest part of the system. It is tolerant of LLM formatting, strict about geometry,
deterministic, and its diagnostics teach the exact fix. Remaining AI-quality risks:
1. Conflicting or missing requirements are not escalated (an overall-dimension mismatch is a warning).
2. The prompt does not tell the AI which product features are impossible, so the AI spends attempts on them.
3. The prompt costs ≈7 k tokens, half of it examples, with vertically exploded arrays.
4. There is no in-app loop that hands diagnostics back to the AI.

Prompt changes are proposed in `11_PROMPT_UPGRADE.md`.
