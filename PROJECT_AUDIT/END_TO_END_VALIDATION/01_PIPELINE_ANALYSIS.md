# 01 — End-to-End Pipeline Analysis

Baseline commit `bf1f44b`. Every stage below was exercised by `tests/e2e/pipeline.py` on 18 products (see 02), and every
claim about data flow was checked by the consistency checks in that file. Legend: **[F]** = changed or added by this
validation (see 11 for the bug each change fixes).

## 1. The pipeline as built (not as described in the brief)

The brief's chain contains a "Gemini API" stage. **It does not exist**: the app makes no LLM call. The AI step is a
human copying a prompt into an external chat and pasting the JSON answer back. Everything else is in this repository.

```
 User requirement (title, free text ≤ 4000 chars, material, thickness, joinery)            canvas.html → js/canvas/main.js generatePrompt()
   │ POST /api/v1/canvas/prompt                                                              board_api/routes.py canvas_prompt()
   ▼
 Prompt construction                                                                         board_engine/canvas_prompt.py build_prompt(), spec_markdown()
   │   (+ [F] build_repair_prompt(), build_update_prompt(); POST /canvas/repair-prompt, /canvas/update-prompt)
   ▼
 ── external AI (Gemini / ChatGPT / Claude), outside the application ──
   ▼
 Structured design JSON (board-design/v1)  → pasted into CodeMirror                         js/canvas/main.js compile()
   │ POST /api/v1/canvas/compile  ([F] time budget, BOARD_TIME_BUDGET = 90 s)                 routes.canvas_compile()
   ▼
 Parsing (fences, prose, comments, trailing commas)                                          canvas.parse_source(), _extract(), _strip_comments()
 Schema validation (material, boards, thickness axis, rotate, [F] mounting)                  canvas._check_material(), _check_boards()
 Component generation (box → 2D outline + Euler placement; profile/openings/engravings)      canvas._component() → examples/furniture.panel(), shapes.shape_polygon()
 Tilt                                                                                         canvas._apply_rotate()
 Connection resolution / inference / classification                                           canvas._resolve_connections(), _infer_connections(), _classify_connections()
 Joint generation: finger & cross-lap cuts                                                    canvas._cut_joint(), _cut_outline()
                   tab_slot tabs                                                              canvas._tabs_for(), _tab_layout(), _connect_tilted()
                   slots + safe repair                                                        joining.join() → validation.evaluate_joint(), apply_repair()
 Native design normalisation ([F] errors mapped to board/line)                                model.normalize_design()
 Sheet choice ([F] measured cut profile + nesting allowances)                                 canvas._auto_sheet()
   ▼
 Assembly validation: 2D parts, joints, connectivity, collisions, near-miss gaps              validation.validate_design(), validate_component(), find_collisions(), find_near_misses()
 [F] Support analysis: anchored / joined / resting / unsupported, tip-over, cantilever        board_engine/support.py support_report()
   ▼
 3D geometry construction (outline+tabs, holes, world matrix)                                 views.model3d() → views.component_view(); drawn by js/studio/viewport3d.js
   ▼
 Production package                                                                           views.production_package()
   ├ Board nesting (MaxRects on bounding boxes, 0°/90°, grain)                                nesting.nest(), verify_nesting()
   ├ Cutting paths (kerf offset, order marks → inner → outer, [F] degenerate-path check)       cutpaths.generate_cut_paths()
   ├ Manufacturing (fasteners, hinges, drilling, assembly plan, material checks)              manufacturing.manufacturing_report()
   ├ Cut list / BOM                                                                            cutlist.cut_list()
   └ readiness = no blocking issue ([F] + support errors)                                      ready_for_production
   ▼
 Production drawings & manufacturing files: PDF booklet, SVG, DXF                             views.export() → booklet.build_booklet(), cutpaths.sheet_svg(), sheet_dxf()
   (export refused with 409 unless ready, or force=1 for a marked draft)                      routes.export_file()
   ▼
 Persistence: file store / Firestore, revisions, audit history, [F] full snapshots + restore  store.DesignStore, firestore_store.FirestoreStore; routes /versions, /restore
```

Studio path (editing an existing design): `PATCH /components/{cid}` · `POST /operations` · joints · fixes → `store.mutate()`
(revision-checked when the client sends `expected_revision`, [F] which the Studio now does) → `validate_design()` → the UI
re-fetches `model3d`, `validate`, `layout2d`.

## 2. Stage-by-stage verification

| Stage | Input → output | Data lost between stages? | Coordinates / dimensions | Error handling | Evidence |
|---|---|---|---|---|---|
| Prompt | form → text | Requirements are cut to 4000 chars (silently; EC-02) | Spec quotes live `TOL`, `LIMITS`, catalogue | 400 on empty title (EC-01) | `edge_cases.json` |
| Parse | text → dict | Unknown fields are **silently dropped** (EC-18) | — | `JSON_SYNTAX` with line/column, JS detection | EC-03…05 |
| Schema | dict → boards | — | exactly one size = thickness, ±5000 mm | 20+ codes, each with board + line | EC-06…17 |
| Components | boards → components | `group`/`name` kept; v1 `size` becomes outline + placement | box ↔ 3D extent checked for every board (finger fingers allowed) | `PROFILE_INVALID`, `OPENING_*` | consistency check 1 |
| Joints | connections → joints + slots | Duplicate pairs dropped with a warning | slot = thickness + clearance (18.10 mm measured) | detached joints carry `detached_reason` | `joint_matrix.json` |
| Validation | design → report | — | contact 0.25 mm, near-miss 2 mm | never raises (`test_degenerate_input_never_raises`) | 364 tests |
| Support [F] | design → statuses | — | COM from area × thickness, footprint hull | `UNSUPPORTED_COMPONENT` blocks production | 02, 04 |
| 3D | design → model3d | `arcs` metadata not used (curves pre-flattened, same in 2D) | world bounds = `Plate.world_aabb` for every part | — | consistency check 2 |
| Nesting | design → placements | none: every part placed once or listed unplaced | inside usable area; area preserved | `PART_EXCEEDS_SHEET`, `NESTING_FAILED` | consistency check 3 |
| Cut paths | nesting → paths | true arcs partly lost with kerf (BUG-017, open) | uncompensated outer area = part area; compensated grows by ≤ kerf/2 × perimeter | `CUT_PATH_*` ([F] `CUT_PATH_DEGENERATE`) | consistency check 5 |
| Cut list | design → BOM | no hardware list (GAP-06) | per-board thickness = design | — | consistency check 6 |
| Exports | package → PDF/SVG/DXF | — | SVG outer paths = DXF outer polylines = placements, for all 13 compiled products | 409 when not ready, 400 bad sheet | `exports` in `e2e_results.json` |

**Downstream stages receive updated data**: every API projection (`model3d`, `layout2d`, exports) is recomputed from the
stored design on each request. Nothing is cached between requests except the pure-geometry interference cache, which is
keyed by full geometry signature (`validation._INTERFERENCE_CACHE`). The only staleness found was in the browser, where
the 2D and 3D panes are fetched separately (R-4, open).

## 3. Dependency map (modules)

```
routes ─┬─ canvas ──┬─ canvas_prompt (spec, examples, [F] repair/update prompts)
        │           ├─ examples.furniture (panel, edge_facing)      ┌─ geometry
        │           ├─ shapes ─────────────────────────────────────┤
        │           ├─ joining ── validation ── model ─────────────┘
        │           ├─ [F] support ── manufacturing.find_contacts
        │           ├─ [F] deadline (time budget; also checked in validation, joining, nesting, manufacturing)
        │           └─ views ──┬─ nesting
        │                      ├─ cutpaths ── booklet (sheet label)
        │                      ├─ manufacturing ── validation
        │                      ├─ cutlist ── manufacturing
        │                      ├─ booklet
        │                      └─ [F] support
        ├─ operations ── joining, autofix, validation
        └─ store / firestore_store ([F] versions)
```

## 4. Duplicated or disconnected logic

| Item | Status |
|---|---|
| Legacy JS stack (`js/core/geometry.js`, `nester.js`, `validator.js`, `connectors.js`, `engine3d.js`) duplicates the Python engine and is not used by Studio/Canvas | Unchanged (out of scope; see first audit) |
| `validate_design` runs twice per compile with production (in `_finish` and in `production_package`) | Unchanged; interference cache absorbs most of it |
| `FLOATING_COMPONENT` (joint connectivity) vs [F] support analysis | Both kept: FLOATING still warns for separate floor-standing assemblies; in the canvas it is replaced by `RESTING_COMPONENT` / `UNSUPPORTED_COMPONENT` where the support analysis is more precise |
| `canvas._cut_joint` cross-lap preconditions vs `_finish` cross-lap fix | [F] one predicate `_cross_lap_cuttable()` now guards the fix |
| `_auto_sheet` allowance vs nesting allowance | [F] now the same numbers (10 mm margin, 14 mm title strip) |
