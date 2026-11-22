# 03 — Joint and Connection Validation

Executed with `tests/e2e/joint_matrix.py` (results: `joint_matrix_baseline.json`, `joint_matrix.json`; identical on both).
Positive cases go through the AI format; negative cases inject one defect into a native design. The expected code was
fixed before running. Regression-tested in `tests/python/test_e2e_pipeline.py` and `test_prompt_upgrade.py`.

## 1. Requested joint families vs what the engine implements

| Requested | Engine type | Result | Notes |
|---|---|---|---|
| T-joint | `tab_slot` | ✔ joined | slot measured 18.10 mm for an 18 mm board = thickness + 0.10 clearance |
| Mortise and tenon | `tab_slot` (through) | ✔ joined, "normalised" warning | blind mortise not available |
| Interlocking | `tab_slot` | ✔ joined | |
| Corner joint | `finger` | ✔ joined | |
| Finger joint | `finger` | ✔ joined (5 fingers) | |
| Dovetail | `finger` | ✔ joined, but **substituted** | a "dovetail" is cut as a straight finger joint; only a "normalised" warning says so (finding J-1) |
| Butt | `edge_butt` | ✔ joined | glue_allowed only |
| Screw connection | `edge_butt` + screws | ✔ joined, drilling generated | |
| Dowel connection | `edge_butt` + dowels | ✔ joined | |
| Cross joint | `cross_lap` | ✔ joined | |
| Miter | `edge_mitre` | ✔ joined **only if each board is drawn to the other's mid-plane** | drawn to the outer corner → `EDGES_NOT_COINCIDENT`. This was undocumented in the prompt (finding J-2, [F] now documented with a tested example) |
| Lap | — | ✘ in v1 | "lap" is an alias of `cross_lap` and fails `NO_CROSSING`; a face-to-face lap exists only in the native format (`face_lap`) |
| Dado / housing | — | rejected `CONNECTION_TYPE` | not modelled (partial-depth cuts) |
| Rabbet | — | rejected `CONNECTION_TYPE` | not modelled |
| Removable / knock-down | — | rejected `CONNECTION_TYPE` | loose parts are handled by the support analysis ("resting") |
| Hinge (moving) | `hinge` | ✔ joined, cup drilling | overlay doors only |

## 2. Negative scenarios: all 11 detected

| Defect | Detected as | Severity |
|---|---|---|
| Joint wider than the board (90 mm tab on an 80 mm edge) | `TAB_OUTSIDE_EDGE` (+ `COLLISION`) | error |
| Joint deeper than material (6 mm tab into 3 mm board) | `TAB_PROTRUDES` | **warning** (joint accepted; finding J-3) |
| Incorrect orientation (wall parallel to base) | `ORIENTATION_MISMATCH` | error |
| Missing mating component | `JOINT_BROKEN` (cause `JOINT_REFERENCE_INVALID`) | error |
| Duplicate joint | `DUPLICATE_JOINT` | error |
| Misaligned slot (4 mm off) | `SLOT_MISALIGNED` | error, not auto-moved |
| Overlapping joints (two tabs on one edge) | `TAB_OVERLAP` (+ `CUT_PROFILE_SELF_INTERSECTION`) | error |
| Insufficient material around the joint (1 mm from edge) | `TAB_OUTSIDE_RECEIVER` | error |
| Loose fit (slot 0.9 mm too wide) | `SLOT_TOO_LOOSE` (auto-repair resizes it) | error / repairable |
| Gap at the joint (1 mm) | `UNINTENDED_GAP` | error |
| Glued joint in a glue-free design | `GLUE_JOINT_NOT_ALLOWED` | error |
| Two tabs needing one through-slot (corpus E2E-17) | `SLOT_ALREADY_USED` | error |
| Tab landing in an intentional opening (E2E-18) | `TAB_IN_OPENING` | error |

**Invalid joints are stopped before export**: every error above makes `ready_for_production` false, and the export
endpoint returns 409 without producing a file (EC-25 shows the same gate for a floating board).

## 3. Joint properties checked by the engine (code-traced)

| Property | Where | Tolerance |
|---|---|---|
| Joint width / depth vs edge and receiver | `validate_component` (`TAB_OUTSIDE_EDGE`, `TAB_TOO_NARROW`), `_eval_tab_slot` (`TAB_TOO_SHORT`, `TAB_NOT_FLUSH`, `TAB_PROTRUDES`) | 0.5 mm shoulders |
| Male/female alignment | `_eval_tab_slot` slot centre vs tab footprint | 0.5 mm |
| Tolerance / clearance | slot = t + clearance; loose beyond +0.3 mm | `TOL['slot_fit']` 0.15, `slot_loose` 0.3 |
| Interference | solid-vs-solid collision after joining | contact 0.25 mm |
| Structural connectivity | joint graph + [F] support analysis | — |
| Tool accessibility | `manufacturing._access_order_issues` (150 mm behind screws) | — |
| Manufacturing feasibility | edge margins, feature size, [F] feature ≥ kerf | 1.5 / 3 mm margins |

## 4. Findings

* **J-1 (open, documented)**: requested joint types that do not exist are silently mapped to the nearest one
  (dovetail → finger, mortise → through tab). Only a warning records it. [F] The prompt now says exactly what each
  name becomes; changing the engine to reject them would break forgiving AI input, so the substitution was kept.
* **J-2 (fixed in the prompt)**: mitre geometry convention documented with a compiled example (`test_claim_mitre_example_in_the_prompt_compiles`).
* **J-3 (open)**: a tab deeper than the receiver is a warning, not an error. Intentional proud tabs need `"protrude": true`,
  but an accidental one still reaches production with only a warning.
* Not modelled: dado, rabbet, blind mortise, sliding dovetail, knock-down fittings. All are rejected cleanly.
