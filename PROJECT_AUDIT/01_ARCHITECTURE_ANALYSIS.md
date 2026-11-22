# 01 — Architecture Analysis

Audit date: 2026-11-22 · Commit audited: `bf1f44b` (main, clean) · Auditor: Claude (read-only audit; no source file modified)

## 0. Headline correction to the brief

The brief describes a "Gemini-powered" generator. **The code contains no Gemini (or any LLM) API integration.**
`grep -ri "gemini\|generativeai\|openai\|anthropic"` over `*.py, *.js, *.html` finds only UI text
(`canvas.html:80` "Paste into ChatGPT, Gemini or Claude", `studio.html:45`) and the legacy prompt header
(`ai-prompt.txt:4`). There is no API key handling, no model call, no retry logic, no streaming.

The actual AI workflow is **human-in-the-loop copy/paste**:

```
user ──► /canvas  "Prompt" form ──POST /api/v1/canvas/prompt──► canvas_prompt.build_prompt()  (≈29 k chars, ≈7.2 k tokens)
     ◄── prompt text (copy to clipboard)
user ──► pastes into Gemini / ChatGPT / Claude (outside the app) ──► copies the JSON reply
user ──► pastes into CodeMirror ──POST /api/v1/canvas/compile──► canvas.compile_source()
     ◄── diagnostics + model3d + nesting + cut paths + cut list
user ──► (fix buttons /canvas/fix) ──► Save (/canvas/save) or Import into an existing design (/canvas/import)
```

Consequence for this audit: "AI generation quality" cannot be measured by calling Gemini from this repo.
Phase 2 therefore tests the part the app owns — the prompt and the compiler's handling of AI-shaped output — using
(a) the 4 real AI outputs already stored as fixtures (`tests/python/fixtures/ai_*.json`) and (b) 30 AI-style
inputs written for this audit (`PROJECT_AUDIT/repro/scenarios.py`). No Gemini result is claimed anywhere.

## 1. Repository map (≈41.7 k lines tracked)

| Layer | Files | Role |
|---|---|---|
| HTTP server | `app.py` (Flask), `start.py`, `start_server.py` | Page routes, static files, seeds the example boat, picks storage |
| REST API | `board_api/routes.py` (639), `auth.py` (160), `contract.py` (181) | `/api/v1/*`: designs CRUD, operations, joints, fixes, layout, exports, canvas |
| Data model | `board_engine/model.py` (588) | Schema normalisation (`normalize_design`), `Plate` derived geometry, `cut_outline()` |
| AI format compiler | `board_engine/canvas.py` (1387) | `board-design/v1` JSON → native design; forgiving parse, connection inference, diagnostics with fixes |
| AI prompt | `board_engine/canvas_prompt.py` (908) | `build_prompt()`, `spec_markdown()`, 3 worked examples (table, cottage, organiser) |
| Shapes | `board_engine/shapes.py` (268) | rect/circle/ellipse/arch/regular_polygon/polygon/path → flattened polygons + arc metadata |
| Geometry | `board_engine/geometry.py` (362) | Vectors, Euler XYZ frames, polygon predicates, offsets, min-area rect |
| Joints | `board_engine/joining.py` (133) | `join()`: validate → safe repair (create/resize slot) → re-validate → commit |
| Validation | `board_engine/validation.py` (1476) | 2D part checks, 7 joint evaluators, solid-vs-solid collision, near-miss gaps, connectivity |
| Auto-fix | `board_engine/autofix.py` (136) | Plans and applies suggested translations |
| Operations | `board_engine/operations.py` (284) | Validated edit ops (add/update/translate/delete component, features, tabs, join/unjoin, material) |
| Nesting | `board_engine/nesting.py` (286) | MaxRects on bounding boxes, 0°/90°, grain-aware, per-stock grouping |
| Cut paths | `board_engine/cutpaths.py` (334) | Kerf offset, cut order (marks → inner → outer), SVG + DXF writers |
| Manufacturing | `board_engine/manufacturing.py` (992) | Material/fastener catalogues, fastener layout, hinge cups, assembly order planning |
| Cut list / BOM | `board_engine/cutlist.py` (245) | Per-board blank sizes, drilling, banding, identical-part grouping |
| Booklet | `board_engine/booklet.py` (598) | Hand-written PDF writer: sheets, dimensioned parts, cut list, assembly sequence |
| Views | `board_engine/views.py` (107) | `model3d()`, `production_package()`, `export()` |
| Storage | `board_engine/store.py` (125), `firestore_store.py` (223) | JSON files + history JSONL, or Firestore via service account |
| Examples | `board_engine/examples/{boat,furniture}.py`, `boat_seed.json` | Parametric example generators |
| New UI | `studio.html` + `js/studio/*`, `canvas.html` + `js/canvas/main.js` | Board Studio (view/edit/produce), AI Design Canvas |
| Legacy UI | `index.html`, `inspector.html`, `manufacturing.html`, `validation.html`, `guide.html` + `js/{assembly,core,manufacturing,models,services,ui,validation}` | Older in-browser "JS model file" workbench with its own geometry, nesting, validation, Firebase |
| Tests | `tests/python/*` (198 test functions → 304 collected), `tests/joint_fit_suite.mjs` | pytest + one Node script for the legacy JS |
| Dead dev scripts | `scratch/*.mjs`, `scratch/car_code_dump.js` (1900 lines), `scratch/verify_platform.py` | Unreferenced one-off scripts |

## 2. Two generations of the application (duplicated functionality)

| Concern | Legacy JS workbench (`/assembly`, `/inspector`, `/manufacturing`, `/validation`) | Current Python engine (`/`, `/canvas`) |
|---|---|---|
| Design format | Executable JS module (`ai-prompt.txt` asks AIs for JS) | Declarative JSON (`board-design/v1` or native) |
| Execution | `js/services/design-parser.js:155-195` — `import(blob)`, then data-URI, then `new Function` in the app origin | Nothing executed (`canvas.py` parses JSON) |
| Geometry/extrusion | `js/core/geometry.js:10` | `model.py` `Plate`, `cut_outline` |
| Nesting | `js/manufacturing/nester.js:7` | `nesting.py` |
| Validation/collision | `js/validation/validator.js:23`, OBB SAT in `js/core/connectors.js:285-325` | `validation.py` |
| 3D viewer | `js/assembly/engine3d.js` | `js/studio/viewport3d.js` |
| Persistence | Firestore collection `designs` from the browser (`firestore.rules`: `allow read, write: if true`) | Server-side file store or Firestore `board_designs` (deny-all to browsers) |
| AI prompt | `ai-prompt.txt` (3 225 lines, served at `/ai-prompt.txt`, `/api/prompt`) | `canvas_prompt.build_prompt()` |

The two stacks share no code. The legacy stack is still linked from the Studio ("Legacy JS workbench",
`studio.html:57`) and is the source of the most serious security finding (see 09, BUG-001).

## 3. End-to-end workflow trace (current stack)

1. **Prompt** — `POST /api/v1/canvas/prompt` (`routes.py:537`) → `build_prompt(title, requirements, material, thickness, joinery)`
   (`canvas_prompt.py:869`). The spec text is generated from live engine constants (`TOL`, `LIMITS`, `MATERIALS`, `FASTENERS`,
   `CONNECTION_TYPES`), so the documented numbers cannot drift from the code.
2. **Parse** — `canvas.parse_source()` accepts fenced code, prose around JSON, `//` and `/* */` comments, trailing commas, BOM.
3. **Schema** — `_check_material`, `_check_boards`: each board is an axis-aligned box; exactly one size must equal its thickness
   (else `THICKNESS_MISMATCH` / `AMBIGUOUS_ORIENTATION`).
4. **Boards → components** — `_component()` calls `examples.furniture.panel()` to build a 2D outline + Euler placement; profiles,
   openings, engravings mapped from face/world coordinates; `rotate` applied last (`_apply_rotate`).
5. **Connections** — `_resolve_connections` (aliases, key synonyms, case/name references, duplicates), optional `_infer_connections`,
   `_classify_connections` (reversed pairs, tab_slot→finger at flush corners, →cross_lap for crossing boards).
6. **Cut joints** — finger and cross-lap cuts computed exactly on a grid (`_cut_outline`); tab_slot tabs laid out by `_tabs_for` / `_tab_layout`.
7. **Join** — every joint goes through `joining.join(..., auto_repair=True, whole_design_check=False)`; slots are created here.
8. **Validate** — `validation.validate_design` once for the whole design (`_finish`), issues mapped back to source lines and fixes.
9. **Produce** — `views.production_package`: validate again → `nest` → `generate_cut_paths(compensate_kerf=True)` → `manufacturing_report`
   → `cut_list`; `ready_for_production = not blocking`.
10. **Persist** — `/canvas/save` stores the compiled native design plus the original source; Studio edits go through
    `store.mutate()` with revision numbers and a JSONL audit history.
11. **Export** — `/designs/<id>/export/<pdf|svg|dxf>`; PDF booklet is generated by a hand-written PDF writer (`booklet.py`).

## 4. Coordinate systems (verified)

* World: millimetres, **+Y up**, X = length, Z = depth (`canvas_prompt.spec_markdown`; `views.model3d` returns `up_axis: 'Y'`, `euler_order: 'XYZ'`).
* Component: 2D outline in local XY, CCW enforced (`model.normalize_component` reverses CW outlines and adds a note),
  thickness centred on local z (`Plate.world_aabb` uses ±t/2).
* Sheet: origin top-left, +y down, parts never mirrored (`nesting.py` header).
* 3D viewer applies the backend `matrix_world` directly (`viewport3d.js:199`), so tilted boards render exactly as validated.

## 5. Storage, logging, error handling

* **Storage**: `DesignStore` writes `instance/designs/<id>.json` atomically (`tmp` + `os.replace`) and appends `<id>.history.jsonl`.
  Locks are `threading.RLock` per design (`store.py:37-41`) — **per process only**; multiple worker processes are not
  coordinated. Firestore is used when `FIREBASE_SERVICE_ACCOUNT` is set (`firestore_store.store_from_env`).
  On a read-only host the app silently falls back to the system temp dir (`app.py:29-47`, logged as a warning) — data is not persistent there.
* **Auth**: Bearer API keys (roles viewer/editor/admin) or a signed session cookie. **Every visitor of `/` or `/canvas`
  receives an editor session automatically** (`app.py:99-121`); there are no user accounts and no design ownership.
* **Rate limit**: in-memory sliding window per principal (`auth.py:111`), per process, default 600/min.
* **Errors**: `compile_source` never raises (catches `SchemaError` and any `Exception` as `COMPILER_ERROR`); API maps
  `SchemaError`, `NotFound`, `Conflict`, `NestingError`, `OperationRejected` to JSON errors. Logging via `logging` with `LOG_LEVEL`.
* No structured request logging, metrics, tracing or error reporting service.

## 6. Unnecessary / duplicated code (identified, not removed)

* Whole legacy JS stack duplicates the Python engine (section 2).
* `scratch/` — 16 dev scripts + a 1 900-line code dump; nothing references them.
* `ai-prompt.txt` (3 225 lines) — legacy JS prompt, superseded by `canvas_prompt.py`, still served at three URLs (`app.py:187-203`, including the misspelt `/ai-promtp.txt`).
* `canvas._check_boards` final line `return boards if ok else {k: v ...}` returns the same dict on both branches.
* Unused frontend API wrappers `Api.rebuildBoat`, `Api.exportUrl` (`js/studio/api.js:62,78`); unreachable rect branches `viewport3d.js:63-70`, `js/studio/main.js:352`.
* Docs: `docs/architecture.md` describes only the legacy stack ("PuzzleCore"); the current architecture is in `docs/board-api.md`.
