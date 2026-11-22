# 12 — Production Readiness

## Verdict against the final objective

> *Prove that the application can reliably transform complex natural-language product requirements into complete,
> geometrically valid, correctly connected, collision-free, manufacturable 2D board designs, assembled 3D models,
> optimised cutting layouts and accurate production documentation.*

**Partly proven.**

| Claim | Proven? | Evidence | Limits |
|---|---|---|---|
| Natural language → design | **Partly** | With the upgraded prompt, a capable AI produced 4/4 compiling and 3/4 production-ready designs on the first attempt (07) | Claude agents, not Gemini; 1 sample each; there is no in-app AI call |
| Complete | **Yes, for what the format can express** | Component sets identical across source, 3D, nesting, cut list, files (13/13 products) | Bent, laminated, bevelled, round and moving parts are out of scope and are rejected or documented |
| Geometrically valid | **Yes** | 300 → 369 passing tests; validator caught every injected defect (11/11 joints, 27/27 API cases) | Collision check is sampled at 0.5 mm |
| Correctly connected | **Yes** | joint matrix; [F] detached joints now block production (BUG-020) | dovetail/dado-type joints are substituted or unavailable |
| Collision-free | **Yes** | every compiled corpus product: 0 collisions | — |
| Physically plausible support | **Yes (geometric)** [F] | support analysis: floating, resting, tip-over, cantilever (9/10 scenarios) | no strength / load assessment; no single-attachment check |
| Manufacturable | **Laser / thin stock: yes. CNC-routed board: no** | kerf, cut order, labels, templates verified | BUG-004: no tool radius, no dog-bones |
| Assembled 3D = 2D = files | **Yes** | 06: five representations agree; one edit reaches all of them | DXF arcs partly polylines with kerf |
| Optimised cutting layouts | **Valid, not optimal** | waste arithmetic exact; no overlaps; grain respected | bounding-box nesting, no common-line cutting |
| Accurate documentation | **Yes for boards** | PDF/SVG/DXF generated for all 13; counts match | no hardware BOM |
| Reliable under modification | **Yes** | propagation verified; versions + restore [F]; revision conflicts handled [F] | — |
| Reliable under failure | **Yes** | no crash, no partial write, clear errors; time budget [F]; client timeouts [F] | no Gemini failure modes to test |

## Readiness by component

| Component | Before this work | Now |
|---|---|---|
| Compiler & validation | strong, 4 correctness bugs | **ready** for supported product classes |
| Support / stability | absent | **ready (geometric)** |
| Production verdict | too permissive (floating, detached, sub-kerf) | **trustworthy for laser**; optimistic for CNC |
| Hang protection | none server-side, none in Studio UI | **in place** (90 s budget, 150 s client timeout) |
| Prompt + iteration loop | single prompt, no recovery | prompt v2 + repair + update prompts, endpoints, buttons |
| Version history | audit log only | **snapshots + restore API** (no UI) |
| Security / multi-user | not ready | **not ready** (BUG-001, BUG-014, BUG-016 open) |
| CNC manufacturing truth | not ready | **not ready** (BUG-004) |

## Before calling it production-ready (ordered)

1. **Security**: lock the legacy Firestore rules or retire the legacy pages (BUG-001/014); viewer-by-default sessions and design ownership (BUG-016).
2. **CNC process model** with tool diameter and dog-bone relief (BUG-004).
3. Decide the product policy for `overall` mismatches (BUG-007b) and add the single-attachment check (S-1).
4. Restore button and conflict dialog in the Studio UI; browser tests for both.
5. Compute validation and support once per compile (P-1); analytic collisions (P-2).
6. If direct Gemini integration is wanted: build it on the repair/update prompts, with the existing time budget, and
   publish a measured first-pass success rate per model.

## Change summary (this validation)

* **Engine:** `support.py` (new), `deadline.py` (new); fixes in `canvas.py`, `validation.py`, `cutpaths.py`, `views.py`,
  `operations.py`, `model.py` (optional `mounting`), `store.py` / `firestore_store.py` (versions), `canvas_prompt.py`
  (prompt v2, repair/update prompts).
* **API:** time budget, `/canvas/repair-prompt`, `/canvas/update-prompt`, `/designs/{id}/versions[/{rev}]`, `/restore`;
  canvas update keeps revisions.
* **UI:** revision checks and an atomic re-join in the Studio, a default request timeout, the canvas compile queue,
  Ctrl-S updates the saved project, "Fix prompt" and "Prompt for a change" buttons.
* **Tests:** `tests/e2e/` harness (corpus, joint matrix, edge cases, support, nesting, propagation, browser, AI scoring),
  `test_regressions_e2e.py`, `test_prompt_upgrade.py`, `test_e2e_pipeline.py`; `docs/board-design-format.md` regenerated.
