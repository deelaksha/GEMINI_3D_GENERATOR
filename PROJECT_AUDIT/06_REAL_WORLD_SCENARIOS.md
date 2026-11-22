# 06 — Real-World Product Scenarios

**Method.** Each product was written as an AI would write it: a `board-design/v1` JSON following the prompt's spec, with the
geometry chosen to be realistic, not tuned to pass. Each was compiled by the real engine (`compile_source`, production on,
kerf compensation on). No Gemini output is used (see 02 §1). Every number below comes from
`PROJECT_AUDIT/repro/scenarios.py` → `repro/scenario_results.json` and `repro/probes.py`.

Legend: ✔ correct · ⚠ works with caveats · ✘ fails / not supported. "Author error" marks a mistake in the test input
(kept, because an AI makes the same one), as distinct from an engine limitation.

## Summary

| # | Product | Compiles | Boards / joints | Sheets · utilisation | Ready for production | Key finding |
|---|---|---|---|---|---|---|
| 1 | Guitar (flat display) | ✘ | — | — | — | Neck on body face cannot be expressed (no face joint in v1) |
| 2 | Chair (profiled sides, 8° tilted back) | ✔ 0.4 s | 5 / 8 | 1 · 23.6 % | yes* | Tilted tab_slot works; no stability check |
| 3a | Table (prompt example) | ✔ 0.65 s | 5 / 13 | 2 · 38.4 % | yes* | Reference design clean |
| 3b | Table, legs = overall height | ✘ (correctly) | — | — | — | Exact diagnosis + fixes; converges |
| 4 | Bookshelf, `connections: "auto"` | ✔ 4.0 s | 9 / 38 | 3 · 41.6 % | yes* | Inference correct, 38 joints |
| 5 | Kitchen base cabinet + hinged door | ✔ 0.9 s | 7 / 27 | 2 · 42.0 % | yes* | Reversed pair auto-swapped; near-miss warning |
| 6 | Punt (flat-bottom boat, flared sides) | ✘ | — | — | — | Angled side-to-bottom joint unsupported |
| 7 | Storage box + loose lid | ✔ 0.5 s | 6 / 8 | 1 · 8.8 % | yes* | Finger box clean; lid "floating" but still ready |
| 8 | Computer desk + tray + drawer | ✘ → ✔ after redesign | 8 / 19 | — | — | Tray needs hangers (author error); drawer unsupported |
| 9 | Wooden toy car (wheels, axle) | ✘ | 5 / 2 | 1 · 1.2 % | no | No round stock or rotating parts; misleading "safe" fix |
| 10 | Wardrobe, 2 bays, 2 doors | ✘ → ✔ after staggering | 14 / 46 | 5 · 63.9 % | yes* | Shared through-slot conflict, not mentioned in prompt |

\* "Ready" is the engine's verdict. For 18 mm plywood it does not account for router tooling (BUG-004), so the real verdict is **no** for CNC.

## 1. Guitar — flat display guitar (6 mm plywood)
* **Input**: ellipse body profile 450×360, Ø90 sound hole, neck board lying on the body face, headstock.
* **Result**: `NO_CONTACT` for `neck-body`; `CONNECTION_OVERLAP` 12 mm for `head-neck` (author error: the headstock overlaps the neck end).
* **Probe** (`probes.py` E): neck-on-face tried as tab_slot → `NO_CONTACT`, butt → `NO_CONTACT`, finger and cross_lap → `JOINT_NEEDS_PLAIN_BOARD`.
* **Verdict**: profile, openings and curves are fine (✔). Component completeness ✘: a real guitar needs bent sides, a neck joint
  and a fretboard laminated on the neck, and none of these exist in the board model. The engine supports `face_lap` natively, but `board-design/v1` does not expose it.

## 2. Wooden chair (18 mm plywood)
* **Input**: two L-profiled sides (tall back leg), seat, stretcher, backrest tilted −8° about X.
* **Result**: ok, 8/8 joints joined, 0 warnings, 1 sheet, kerf-compensated paths, no cut issues.
* **Geometric correctness**: ✔ (collision-free, tilted tabs land in slots inside the profile).
* **Not evaluated by the engine**: stability (tip-over with a 100 kg sitter), racking strength of tab joints in 18 mm ply, ergonomic seat angle. ✘ gap.

## 3. Table
* **3a** (the prompt's own example): ok, 13 joints, 2 sheets at 38 %.
* **3b** (legs 750 instead of 732): `CONNECTION_OVERLAP` "runs 18.00 mm into 'TOP' — exactly its thickness: … leg height = overall height − top thickness",
  with resize/move fixes. Applying the first fix per error converges to ok=true (`probes.py` A). ✔ Best-in-class diagnostic.

## 4. Bookshelf 800×1800×300 (auto-inferred connections)
* 2 sides, 6 shelves (bottom at 60 mm for a plinth, top inset to 1760 to keep slot margin), 6 mm back.
* Result: ok, 38 joints inferred and joined, 4.0 s. ✔ The inference picked tab_slot for the shelves and handled the 6 mm back.
* Caveat: the top shelf had to be inset 40 mm from the side tops, because a shelf flush with the side's top edge is a `finger`
  corner, not a tab_slot (`SLOT_AT_EDGE`). The prompt explains this.

## 5. Kitchen base cabinet + door (glue allowed)
* Sides, bottom on a 50 mm plinth, top, dowelled shelf, recessed back tabbed on 4 edges, overlay door hinged on SIDE-L.
* Result: ok, 27 joints, warnings `CONNECTION_REVERSED` (deliberately reversed `TOP into BACK`, auto-swapped ✔) and `NEAR_MISS_GAP`.
* Manufacturing: 8 fasteners, 22 drilling operations (dowels + 35 mm hinge cups), 12-page PDF booklet, 5 engraved labels on sheet 1.
* Gaps: no hardware BOM (hinge model, dowel count) in the cut list; no drawer-runner or adjustable-shelf pin support.

## 6. Boat — flat-bottom punt (6 mm)
* Bottom, two sides flared ±15° about X pivoting on the bottom's edge, transom, bow.
* Result: `NO_CONTACT` for both sides. A tilted board's end face is square to the board, so it is never parallel to the
  flat bottom; v1 has no bevelled tab_slot. ✘
* The repository's own boat example (`board_engine/examples/boat.py`) is built in the native format with explicit outlines,
  so a boat is possible, but **not through the AI canvas format** with realistic flare.

## 7. Storage box with lid (6 mm)
* Base, 4 walls with 8 finger corners (including three-way corners), loose lid.
* Result: ok, 8 finger joints, `FLOATING_COMPONENT` for the lid, yet `ready_for_production: true`. ✔ geometry; ⚠ a loose lid is
  intended here, but the same warning hides genuinely forgotten connections (BUG-007).
* Utilisation 8.8 %: a 300×200 box placed on a 2440×1220 stock sheet (canvas default stock), where a laser-bed sheet would be realistic.

## 8. Computer desk
* As first written (an AI's likely draft): keyboard tray `tab_slot into TOP` while lying parallel under it → `NO_CONTACT`
  (author error, clearly diagnosed). Drawer front + bottom flagged and changed to `finger` automatically.
* Redesigned with two hanger boards (`probes.py` C): ok, 8 boards, 19 joints. ✔
* A real drawer (sliding box on runners) cannot be modelled; it can only be drawn as a fixed box. ✘

## 9. Wooden toy car (6 mm)
* Profiled side with arc roof and Ø6.4 axle holes, floor, wheel (circle profile), axle drawn as a 6×6 strip.
* Result: 4 `COLLISION` (square axle through round holes: its diagonal 8.5 mm > 6.4 mm, a correct detection), wheel floating,
  `PART_BELOW_MIN_SIZE` (axle narrower than 25 mm plywood minimum), `OVERALL_MISMATCH`.
* **BUG-006**: the engine offers "Add a cross_lap connection SIDE-B × AXLE-1" marked **safe**. Applying it yields
  `JOINT_NEEDS_PLAIN_BOARD`, because SIDE-B has a profile. A "safe" fix should never lead to a new error.
* Verdict: ✘ toys with wheels, axles or pegs need round-stock parts and rotating fits, which do not exist.

## 10. Wardrobe 1000×2000×570 (complex multi-panel)
* Two bays around a full-height divider, 3 shelf pairs, 6 mm back, 2 full-height overlay doors with 4 hinges each.
* As written (shelf pairs at the same heights): `SLOT_ALREADY_USED` ×6 + `COLLISION`. Each left shelf's tabs cut through-slots
  in the divider, and the right shelf's tabs land in the same slots. 40/46 joints joined.
* Staggering the right shelves by 60 mm: ok, 46/46 joints, 0 warnings, 5 sheets at 63.9 %. Different tab counts at equal height still fail.
* Verdict: ⚠ the engine is right that two tabs cannot share a through-slot. But the prompt never tells the AI, and there is no
  alternative joint (blind slot, or one shared tab passing through). This is a very common furniture layout. (BUG-005)

## Cross-cutting conclusions
1. **Rectilinear furniture** (tables, shelves, cabinets, boxes, wardrobes with staggered shelves) is handled well: correct geometry,
   correct joints, exact 2D/3D parity, production package.
2. **Anything curved in 3D, laminated, angled-without-bevel, round, or moving** is outside the model (guitar, boat, toy, drawers).
   The prompt does not say so, so the AI will try anyway.
3. **"Ready for production" is too generous**: it ignores tooling (BUG-004), floating parts and requirement mismatches (BUG-007),
   and tiny holes under kerf (BUG-002).
