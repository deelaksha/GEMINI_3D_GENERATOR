# 11 — AI Prompt Upgrade (proposal; source not modified)

> **Status (end-to-end validation):** this proposal has been implemented in `board_engine/canvas_prompt.py`, extended with the findings of the validation (mitre convention, joint names, support/mounting, fasteners, repair and update prompts). See `END_TO_END_VALIDATION/07_PROMPT_UPDATE_ANALYSIS.md`.

The audit rules say no source changes during the audit, so this file holds the upgraded prompt text ready to merge into
`board_engine/canvas_prompt.py`. **Every new rule below is backed by a scenario run** (06 / `repro/`). None is a guess about
engine behaviour.

## 1. Problems with the current prompt (measured)

| # | Problem | Evidence |
|---|---|---|
| P1 | The AI is never told what the generator **cannot** build, so it spends attempts on laminations, flared hulls, axles and drawers | 06: guitar, boat, toy, desk |
| P2 | The shared-through-slot conflict (shelves at equal height on both sides of a divider) is not mentioned | 06 wardrobe, BUG-005 |
| P3 | No guidance on missing or conflicting requirements; `overall` may contradict the boards, and it still compiles | E07 |
| P4 | No self-check step before answering | — |
| P5 | No id length guidance (long ids crash `auto`) | BUG-003 |
| P6 | No minimum hole size relative to the kerf | BUG-002 |
| P7 | ≈7.2 k tokens, 47 % examples; two examples printed with one number per line | 02 §2 |
| P8 | No follow-up "repair" prompt: users must improvise when sending diagnostics back to the AI | GAP-09 |

## 2. Changes to `build_prompt()` — INSTRUCTIONS block

Replace instructions 1–8 with:

```text
INSTRUCTIONS:
1. Read the requirements. If a dimension is missing, choose a standard value for this product. If two requirements
   conflict, follow the explicit number. In both cases write the decision in "product.description" as
   "Assumptions: …". Never leave a board without a size.
2. Decide the boards. Give each a short unique id (at most 24 characters: letters, digits, "-"), e.g. SIDE-L, SHELF-2.
3. Compute every position and size explicitly in millimetres — no formulas, variables or expressions.
4. Account for board thickness everywhere: boards touch exactly and never overlap
   (leg height = overall height − top thickness; inner width = overall width − 2 × side thickness).
5. Choose each joint from the geometry: end face on a face away from the edges → "tab_slot"; at an edge (box corner)
   → "finger"; boards crossing each other → "cross_lap". Inset tab_slot boards from the receiving board's edges by at
   least the board thickness.
6. Two boards must never tab into the same board at the same place from opposite sides (e.g. shelves on both sides of
   a centre divider): their tabs would need the same through-slot. Offset their heights by at least 60 mm
   (or 4 × the board thickness, whichever is larger).
7. Holes and openings must be at least twice the material's kerf across (table below; e.g. ≥ 8 mm for plywood or MDF).
8. Connect every board, directly or through others. A part that is intentionally loose (a lift-off lid) must be named in
   the description; it will be reported as floating.
9. Use only the fields, types and values in the specification; never invent fields.
10. SELF-CHECK before answering, and correct the JSON if any answer is "no":
    a. Does exactly one of each board's three sizes equal its thickness?
    b. For every connection, does the end face of "board" lie exactly on a face of "into" (gap 0)?
    c. Do the boards' combined extents equal product.overall in length, height and depth?
    d. Is any space occupied by two boards (other than boards that cross with a cross_lap)?
    e. Are all ids unique and at most 24 characters?
11. Return ONLY one ```json code block with the complete design; write number arrays on one line ([x, y, z]).
```

## 3. New spec section (insert in `spec_markdown()` before "## Geometry rules…")

```text
## What this generator cannot build (do not attempt; use the alternative)
- Boards joined face to face (laminations, a guitar neck glued on a body, a tray hanging parallel under a table top):
  no connection joins two parallel faces. Join them through perpendicular boards instead (hangers, cleats, a frame).
- Boards meeting at an angle other than 90°, except (a) a tilted board resting on an edge cut to exactly its pitch
  (roof on a gable) and (b) "mitre". A side tilted outwards cannot stand on a flat bottom; keep such sides vertical.
- Round or bent parts: dowels, axles, rods, wheels on axles, curved or kerf-bent panels. For a purchased dowel or axle,
  add a "hole" opening where it passes and leave the rod itself out of the design.
- Moving parts other than hinged doors: drawers on runners, sliding trays, wheels. Draw a drawer as a fixed box.
```

Each claim was checked against the engine:

| Claim | Evidence |
|---|---|
| No connection joins parallel faces | `probes.py` E: tab_slot/butt → `NO_CONTACT`, finger/cross_lap → `JOINT_NEEDS_PLAIN_BOARD` |
| Tray works through hangers | `probes.py` C: ok, 19 joints |
| Flared side on flat bottom fails | 06-boat-punt: `NO_CONTACT` |
| Roof-on-gable tilt works | Existing `COMPLEX_EXAMPLE` compiles with 0 errors (test-suite) |
| Holes for axles compile | 09-toy-car: the holed side compiles; only the drawn axle collides |
| Staggering by 60 mm resolves the divider conflict | `probes.py` B: 46/46 joints, 0 warnings; equal heights with different tab counts still fail |
| ≤ 24-char ids are safe | Run with `connections: "auto"`: 24-char ids → ok; 29 → `SCHEMA_ERROR` (tab id `auto-…-t1` > 64 chars); 30 → `COMPILER_ERROR` |
| Hole ≥ 2 × kerf | radius − kerf/2 > 0 needs diameter > kerf (BUG-002); 2× leaves margin |

## 4. Token reduction

Print `COMPLEX_EXAMPLE` and `STRUCTURES_EXAMPLE` with the project's existing `canvas.pretty_json` instead of `json.dumps(indent=2)`.
That puts number arrays on one line, as the `/canvas/spec` endpoint already does. Measured: examples 12 985 → 10 563 chars
(−2.4 k chars ≈ −600 tokens), and the AI copies the compact style into its answer, which shortens replies too.
No content changes. Keep all three examples: they are compiled by the test-suite and are the best guard against format drift.

## 5. New: repair prompt (for the Canvas "Copy errors for the AI" button)

```text
The board design generator compiled your JSON and reported the problems below. Return the COMPLETE corrected design
as one ```json block. Change only what is needed to fix these problems; keep every other board, id and dimension
unchanged. Each problem names the board or connection and, where available, an exact correction — apply it.

PROBLEMS:
{for each error and warning: "- [CODE] message (board X / connection Y, line N)" + " Fix: " + first fix title if any}

YOUR PREVIOUS JSON:
{source}
```

The diagnostics already carry `code`, `board`, `connection`, `line` and `fixes[].title` (`canvas.diag`), so this needs only a
small builder (`build_repair_prompt(source, diagnostics)`) plus a button. It closes the loop without an API integration.

## 6. Tests to add with the change

1. `spec_markdown()` contains the "cannot build" section; for each listed limitation, a scenario asserts the stated diagnostic
   (port `repro/probes.py` E, B, C and `scenarios.py` 06/09 into `tests/python/test_prompt_limits.py`).
2. `build_prompt()` mentions the 24-character id rule, and a design with 24-character ids and `"connections": "auto"` compiles.
3. Repair prompt: for the 03b leg-height design, `build_repair_prompt` lists both `CONNECTION_OVERLAP` errors with their fix titles.
4. The existing test `test_complex_structures.py:243-252` (spec embedded in prompt) keeps passing.

## 7. What the prompt cannot fix

BUG-002/003/006/007/008 and BUG-004 (tooling) are engine defects. The prompt rules only lower the chance an AI triggers them. Fix them in code (10, roadmap).
