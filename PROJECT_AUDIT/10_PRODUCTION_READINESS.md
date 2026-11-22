# 10 — Production Readiness and Implementation Roadmap

## 1. Verdict

**Not production-ready as a public multi-user service.** The core geometry engine is **close to production quality for
laser-cut, rectilinear products**. It is **not** ready for CNC-routed furniture or for products outside the flat-board model.

| Component | Ready? | Evidence |
|---|---|---|
| `board-design/v1` compiler (parse, schema, diagnostics, fixes) | **Yes, with 3 fixes** (BUG-003, BUG-006, BUG-009) | 02 §3: tolerant parsing, exact diagnoses, deterministic, never raises |
| Geometry validation (joints, collisions, gaps) | **Yes** for axis-aligned and tilted flat boards | 03; 300 passing tests; 2D = 3D verified |
| 2D/3D consistency | **Yes** | 03 §2: identical parts, areas and hole counts |
| Nesting | **Functional, low yield** | 04 §3: bounding-box MaxRects, 9–64 % utilisation |
| Cut paths (laser, thin stock) | **Yes after BUG-002** | Kerf offset verified; cut order correct |
| Cut paths (CNC router, furniture board) | **No** | BUG-004: no tool model or inside-corner relief |
| Production documents (booklet, cut list, SVG/DXF) | **Yes for boards; hardware BOM missing** | 04 §1 |
| Readiness verdict (`ready_for_production`) | **No — too permissive** | BUG-002, BUG-004, BUG-007 |
| Studio editor | **Viewer + limited editor** | 05: move/rotate/joints only; no undo, add, resize, material; BUG-008, 010, 011 |
| AI Canvas | **Yes for single users** | 05; BUG-012, 013 |
| AI integration ("Gemini-powered") | **Does not exist** | 01 §0 |
| Security / multi-user | **No** | BUG-001 (stored code execution), BUG-016 (anonymous editor, no ownership), BUG-014 |
| Scalability / ops | **No** | 07: sync compile, tens of seconds for large egg-crates, dev server only, per-process state, no observability |
| Test automation | **Strong engine tests; no UI, CI or perf gates** | 08 |

Nothing in this audit is marked ready without a measurement or a code trace behind it. The product scenarios are AI-*style*
inputs written for the audit, not live Gemini outputs.

## 2. Implementation roadmap

Ordered by risk reduction per unit of effort. Each item names its acceptance test (08 §3).

### Phase A — Safety and correctness (do first; small changes)
1. **Close BUG-001 / BUG-014**: set the Firestore `designs` rule to deny, or take the legacy pages offline. If they must stay, stop
   executing stored JS. Acceptance: TC-17.
2. **BUG-016**: issue *viewer* sessions by default and require a key or login for editor actions; add an `owner` field and enforce it on mutate/delete.
3. **BUG-002**: reject features ≤ kerf in `validate_component`; never emit a non-positive radius. TC-02.
4. **BUG-003**: inferred ids `auto-<n>`; never index with `_i=None`; truncate derived tab ids safely. TC-01.
5. **BUG-007**: `FLOATING_COMPONENT` and `OVERALL_MISMATCH` block `ready_for_production` unless waived. TC-03/04.
6. **BUG-008**: `set_material` updates pinned board thicknesses, or the canvas stops pinning equal thicknesses. TC-08.
7. **BUG-006, BUG-009**: safe-fix eligibility; connection-level validation with line numbers. TC-05/06.
8. **BUG-015**: `Path.as_uri()` in the JS cross-check test. TC-10.

### Phase B — Prompt upgrade and AI loop (small; no engine risk)
9. Apply `11_PROMPT_UPGRADE.md`: new instructions, "cannot build" section, `pretty_json` examples, repair-prompt button.
10. Store every pasted AI reply (opt-in) with model name and outcome, to measure the real first-pass success rate per model.
11. *Optional, needs a product decision*: direct Gemini/Claude API integration (prompt → JSON → compile → auto-repair loop ≤ N rounds).
    The repair prompt from step 9 is the core of that loop. Needs key management, cost limits and the Phase C job queue.

### Phase C — Manufacturing truth (medium)
12. **BUG-004 tooling model**: `process` per design (`laser` | `router` | `saw`) with tool Ø. Router: kerf = bit Ø, dog-bone
    relief at inside corners, spacing ≥ bit Ø, edge margins scaled to thickness. TC-09.
13. Fit test coupon and "measured thickness" input to address R-5.
14. Hardware BOM (hinges, screws, dowels by type, size and count) in the cut list and booklet (GAP-06).
15. Analytic arc offsets in kerf compensation (BUG-017).
16. Canvas: laser-bed and cut-to-size stock presets; better nesting (true-shape or at least part rotation in 90° steps plus remnant reuse).

### Phase D — Performance and operations (medium)
17. **PERF-001**: analytic interference for axis-aligned board pairs; reuse the validation report in `production_package`. Gate: 16×16 grid < 15 s.
18. Run compile and production as background jobs with a time budget; the UI polls or streams.
19. Production server (gunicorn/waitress + worker timeouts), shared lock and rate-limit store (or Firestore transactions), health endpoint, structured logs.

### Phase E — Editor and product scope (larger; needs product decisions)
20. Studio: send `expected_revision` (BUG-010); atomic re-join through `/operations` (BUG-011); fix canvas compile/save races (BUG-012/013).
21. Undo/redo through store history (a revert-to-revision endpoint).
22. Edit dimensions in the Studio by round-tripping to the v1 source: keep the v1 JSON as the editable truth and recompile, rather than adding a constraint solver.
23. Expose `face_lap` in `board-design/v1` (GAP-01); consider bevelled tab_slot (GAP-02) and round stock (GAP-03) only if products need them.
24. Retire or isolate the legacy JS workbench, `ai-prompt.txt` and `scratch/`; update `docs/architecture.md`.
25. Playwright E2E for Canvas and Studio; CI pipeline (08 §2).

## 3. Definition of "production-ready" for re-audit

* Phase A complete, with TC-01…TC-10 passing in CI.
* No S1 bugs open; BUG-004 resolved for every advertised process.
* 10-product scenario corpus: every supported product compiles; every unsupported one fails with a documented diagnostic.
* Perf gate met; compile cannot block a worker beyond its budget.
* Measured AI first-pass success rate published per model (Phase B step 10).
