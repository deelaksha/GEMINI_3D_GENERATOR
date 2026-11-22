# 05 — UI and Interactive Design Editor Analysis

Sources: frontend read-out (file:line references verified for the key claims), backend `board_engine/operations.py`,
and operation tests run for this audit (commands in §4).

## 1. Pages

| Page | URL | Stack | Purpose |
|---|---|---|---|
| Board Studio | `/`, `/studio` | `js/studio/{main,api,viewport3d,sheet2d,fullscreen}.js` → `/api/v1` | View 3D/2D, inspect, move/rotate, check/re-join joints, fixes, produce, export |
| AI Design Canvas | `/canvas` | `js/canvas/main.js` + CodeMirror → `/api/v1/canvas/*` | Prompt → paste AI JSON → compile → fix → save/import |
| Legacy workbench | `/assembly`, `/inspector`, `/manufacturing`, `/validation`, `/guide` | `js/assembly`, `js/core`, `js/models`, … (browser-only) | Older JS-model pipeline with its own geometry, nesting, validation, Firestore |

3D: three.js **r128** (cdnjs) + OrbitControls (`three@0.128.0`, jsdelivr), global build (`studio.html:10-11`). Every board is an
`ExtrudeGeometry` of the backend cut outline with holes, placed by the backend `matrix_world`.

## 2. Editing capabilities

| Capability | Studio | Canvas | Backend op | Dependent geometry updated? |
|---|---|---|---|---|
| Move | ✔ numeric XYZ (`js/studio/main.js:387-423`) | ✔ edit JSON `position` | `update_component` / `translate` | **No.** Joints are re-evaluated; broken ones are rejected (`would_break_joints`) or detached on request. Neighbours are never moved or resized |
| Rotate | ✔ Euler XYZ degrees | ✔ `rotate` | `update_component` | Same as move |
| Resize / change dimensions | ✘ | ✔ edit `size` → recompile | `update_component(outline)` (API only) | Canvas: everything is regenerated on recompile; Studio: n/a |
| Add / remove boards | ✘ (“Parts are added through the API”, `main.js:327`) | ✔ in JSON; "Import selected boards" into an existing design | `add_component`, `delete_component(cascade)` | Delete with cascade removes joints and their generated slots |
| Change material | ✘ (display only, `main.js:324`) | ✔ in JSON | `set_material` | **✘ BUG-008**: no effect on canvas-created designs (below) |
| Modify joints | Partial: "Check" (dry run), "Re-join" = unjoin + join (`main.js:424-439`) | ✔ in JSON | `join`, `unjoin`, `check_joint` | Join regenerates slots. Re-join is not atomic (BUG-011) |
| Adjust spacing | Nesting margin/spacing only (`main.js:557-567`) | — | query params | n/a |
| Undo / redo | ✘ | CodeMirror text undo only (`canvas/main.js:500-501`) | — (history JSONL is audit-only; no revert endpoint) | — |
| Save / reload | Auto-saved per operation, revisioned | Save / Save-as; draft in localStorage | `store.mutate` (revision + history) | — |
| Regenerate selected component | ✘ | ✘ | — | — |
| Concurrency control | ✘ never sends `expected_revision` (`js/studio/api.js:55-77`) | ✘ | supported (`routes.py:96`) | Lost updates possible (BUG-010) |

## 3. Does editing one component update dependent geometry? — **No (verified)**

The engine has **no parametric constraints**. Boards are independent rigid bodies, and joints are validated relations, not
drivers. Measured on the study-table example:

```
translate LEG-R by +20 mm (no detach)  → rejected: would_break_joints [LEG-R-TOP-t1, LEG-R-TOP-t2, MOD-R-t1, SHELF-R-t1, SHELF-R-t2]
translate LEG-R by +20 mm (detach=true) → accepted; design now: valid=False (COLLISION), FLOATING_COMPONENT,
                                          JOINT_NOT_JOINED, UNJOINED_TAB, UNUSED_SLOT; SHELF still ends at x=532 (not extended)
```

This is safe, because nothing is silently broken. But it means the Studio cannot make the common edit "make the table
100 mm wider". That edit is only possible by editing the v1 JSON in the Canvas and recompiling, where the user (or AI)
must recompute every dependent position by hand.

**BUG-008 (confirmed) — `set_material` thickness is ignored for canvas designs.** `canvas._component` writes an explicit
`comp['thickness'] = bd.t` on every board. `set_material {thickness: 15}` on the compiled study table returns success with
`detached_joints: []`, the design reports material thickness 15 mm, and every part is still 18 mm (`validate_design`: valid,
no issues). The material header and the parts now disagree, and so do stock name and part thickness in the cut list.

## 4. Reproduction

```bash
python -I PROJECT_AUDIT/repro/probes.py <repo>    # fixes, staggering, determinism
# editor propagation (inline script used in this audit):
#   compile EXAMPLE → apply_operation(translate LEG-R +20) → validate_design
#   compile EXAMPLE → apply_operation(set_material thickness 15) → validate_design
```

## 5. Confirmed frontend defects (verified in code)

| ID | Defect | Location |
|---|---|---|
| BUG-001 | Legacy pages import JS from the world-writable Firestore `designs` collection and run it in the app origin via `import(blob)` / `new Function` (stored XSS, then API calls with the visitor's editor session) | `firestore.rules:5-7`, `js/services/design-parser.js:155-195`, `js/models/registry.js:163-193`, `js/core/config.js:25` |
| BUG-010 | No optimistic concurrency from the UI | `js/studio/api.js:55-77` |
| BUG-011 | Re-join = `unjoin` then `join` as two requests; if join fails the joint stays deleted | `js/studio/main.js:436` |
| BUG-012 | Canvas compile drops edits made during a running compile (early return, live timer not rescheduled), and phase 1 reports "Compiled" for stale source | `js/canvas/main.js:226-237` |
| BUG-013 | Canvas Ctrl/Cmd-S always saves a new project, so repeated saves create duplicates | `js/canvas/main.js:48, 431-434` |
| BUG-014 | Legacy XSS sinks: `Toast.show` innerHTML with design names, design-browser cards (`d.name`, `d.thumbnail`), inspector `p.fileName` | `js/ui/toast.js:16`, `js/ui/design-browser.js:269,356`, `inspector.html:187,208` |

## 6. Potential risks

* 2D and 3D refreshed by separate requests with no revision check (`js/studio/main.js:155-169`).
* Full scene rebuild per edit, a cloned 512² texture per board (~1 MB GPU each), an always-on render loop with a 2048² shadow map,
  and an unthrottled raycast on pointermove (`viewport3d.js:145,163-169,176-213,320`). These are the scaling limits for large models.
* Grid helper removed but never disposed (`viewport3d.js:223`).
* The new UI escapes consistently (`esc()`); the remaining unescaped values are server-validated enums.
* There are no browser tests; `window.__studioReady` / `__canvasReady` hooks exist but nothing uses them.
