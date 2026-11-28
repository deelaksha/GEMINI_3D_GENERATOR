# Motion / mechanism audit: board_engine (working tree, 2026-11-28)

Scope: `board_engine/motion.py` (940 lines), `expand.py` (`_instance_motion`, uncommitted working tree), `canvas.py` (motion parse/check wiring L1920-1922, L2150, L2236-2242), `shapes.py` (gear), `hinge.py`, `js/studio/viewport3d.js` (L416-490). The project was not modified. Every scenario is a board-design/v1 JSON file run through `canvas.compile_source(text, run_production=False)`.

S = `/tmp/claude-1002/-home-sonic-claude2-mythra/9b0b6ca6-d98e-48cf-ab1a-7d0386cce3f4/scratchpad/mech_audit`
- JSON: `S/json/*.json`. Builder scripts: `S/s01_02.py`, `s03_05.py`, `s05c.py`, `s06_07.py`, `s08_10.py`, `s08b.py`, `s08b_11.py`, `s11g.py`, `s11f.py`, `s11i_flip_rack.py`, `s12_14.py`, `s14c_timing.py`, `s14e.py`, `s02g.py`. Independent verifiers: `verify14.py`, `verify06_pin.py`, `verify_mesh.py`.
- Rerun any file: `cd S && PYTHONDONTWRITEBYTECODE=1 ../venv/bin/python -c "from lib import *; import json; run('x', json.load(open('json/<file>.json')))"`

## How it works

- **Kinematics:** the backend solves it deterministically. Gear and belt couplings are ratio chains (`_link` L180-266). Gear ratios come from the tooth counts, with the sign flipped per mesh. Four-bar and slider-crank linkages are solved in closed form as a circle-circle or line-circle intersection (`_solve_link` L308-335). The result is tabulated every max(2°, range/360) (`_link_table` L363-380).
- **Front end:** it does not solve anything. It takes the backend's `ratio` and `link.table` and applies `value(d)*ratio` or a linear table interpolation, then rebuilds the rod pose itself (viewport3d.js L439-490).
- **Checks:**
  - **Per motion** (`check_motions` L613-761): mount contact ≤ 0.5 mm, fixed joint (MOTION_LOCKED), slide direction, interference and a 1 mm clearance at sampled poses.
  - **Per mechanism** (`check_cycles` L764-835): interference only, with every part of a train posed together.
  - **Per mesh** (`check_gears` L842-921): module, plane, gear on its axle, centre distance ±0.1 mm, tooth phase.

## Scenario results (summary)

| # | Scenario (JSON) | Result |
|---|---|---|
| 1 | Wheel axis x + axle (`s01_wheel_axis_x`) | Clean, 0.07 s; Ø6 holes in WHEEL and WALL; "dowel about 16 mm" |
| 2 | Spur pair correct (`s02a`/`s02b`) | phase 0 → GEAR_PHASE "set rotation to 6"; once phased, clean, 1.2 s. A 0.5° sweep shows no tooth interference (`verify_mesh.py`) |
| 2 | Wrong centre (`s02c`), module (`s02d`), plane (`s02e`) | GEAR_MESH errors with calculation and a move fix |
| 2 | Pressure angle 20° vs 28° (`s02g`) | **No diagnostic** (M-12) |
| 2 | Explicit ratio 5 on meshing gears (`s02f`) | Only an indirect MOTION_COLLISION "at 5°" (M-08) |
| 3 | A20→B30→C15 (`s03a_train_simple`) | B = −2/3, C = −2 relative to B; at A = 90°: B = −60, C = +120. Correct, including the direction reversal at each mesh |
| 3 | Compound 12→36/12→36 (`s03b`) | C = +10 at A = 90 (1/9). Correct |
| 4 | Slider-crank (`s04_slider_crank`) | Stroke 40.0 = 2 × crank radius; LINKAGE_DRIVE info |
| 5 | Crank-rocker (`s05a`) | Range −1.07..32.2°, clean |
| 5 | Non-Grashof (`s05b`) | LINKAGE_JAM "at 110°… limit to [0,108]" plus LINKAGE_TRANSMISSION 9° |
| 5b | Parallelogram (`s05c`) | **Silent branch flip at 180°** (M-07) |
| 6 | Butterfly, two rods off one crank (`s06`) | Solved (wings equal at 0°/180°, 180° phase offset). **A pin passes through the other rod for 33 crank degrees with no report** (M-06) |
| 7 | One crank → gear + rocker (`s07`) | Transmission continuous: A = 90 → B = −60, R = −10.41 |
| 8 | Moving flap tab_slotted to base (`s08a`) | MOTION_LOCKED. Correct |
| 8 | **Rod** tab_slotted to a static post (`s08b`) | **No MOTION_LOCKED**; only "MOTION_COLLISION ROD/POST at 5°" (M-03) |
| 9 | Lid hits a shelf (`s09_lid_hits_shelf`) | MOTION_COLLISION "at 45°… freely only to 40°" (analytic contact ≈ 42.2°) |
| 10 | driven_by unknown (`s10a`) | MOTION_INVALID error; the motion is dropped, so G1/G2 cascade into a collision |
| 10 | Gear driven by a gear 150 mm away (`s10b`) | GEAR_MESH **error** (not a warning) |
| 10 | Cycle A↔B (`s10c`), self (`s10d`) | MOTION_INVALID, but the cycle path text is wrong (M-15) |
| 11 | Rack via ratio, 200 mm from pinion (`s11a`) | **Accepted silently** (M-08) |
| 11 | Pulleys Ø60/Ø120, ratio −3.7, no belt (`s11b`) | **Accepted silently** (M-08) |
| 11 | Bevel pair (`s11c`) | Rejected: GEAR_MESH "not in one plane" plus MOTION_AXLE |
| 11 | Hinged lid 6 mm (`s11d`) | HINGE_CUP_TOO_DEEP (cup hinge needs ≥ 16 mm) |
| 11 | Cabinet door, hinge gap 2 (spec default) (`s11f`) | **MOTION_NOT_MOUNTED** (M-10) |
| 11 | Hinge on +x edge, motion pivots on −x edge (`s11h`) | **ok = True, zero diagnostics** (M-10) |
| 11 | Flipped rack-and-pinion instances (`s11i`) | **Flip z instance: rack moves −0.524 mm while the tooth surface moves +0.524 mm** (M-04) |
| 12 | Wheel between two walls (`s12a`) | Hole only in WALL-L and WHEEL; nothing about the second support or retention; VISIBLE_GAP asks to close the wheel's running gap |
| 12 | Wheel 10 mm off its support (`s12b`) | MOTION_NOT_MOUNTED: spacers and washers cannot be expressed |
| 13 | Rotate with no axle or hinge (`s13`); slide with no guide (`s13b`) | **Zero diagnostics** (M-09) |
| 14 | Thin arm, post 2.57° into the sweep (`s14a`) | **Missed**; control post at 5° is caught (M-01) |
| 14 | Ratio-10 driven arm, post at 25° (`s14b`) | **Missed**: step becomes 50° (M-01) |
| 14 | 5 / 20 instanced wheel motions (`s14c_*`) | 0.29 s / 1.02 s |
| 14 | 1 / 2 / 4 / 10 instanced gear pairs (`s14d_*`) | 1.34 s / 78 s / 159 s / >9.5 min (killed). With the app's 90 s budget, n = 4 → COMPILE_TIMEOUT (M-05) |
| – | Two independent arms that meet when both are open (`s14e`) | **Not reported** (M-02) |

## Findings

### M-01: The sweep samples at a fixed 5° step (or a capped count), so parts tunnel through each other. Severity: High. Confirmed bug.
- **Where:** motion.py `_samples` L594-606 (`ROTATE_STEP=5.0` L27, `MAX_SAMPLES=72` L28). It is used by `check_motions` L697 and `check_cycles` L790. Driven motions get `step = max(5, range/72)`.
- **Existing vs expected:** a fixed angular step whatever the radius. A board's tip moves r·Δθ per step: 26 mm at r = 300 mm. A ratio-10 follower with range 3600° is sampled every 50°. Expected: a step bounded by the actual swept distance (r_max·Δθ ≤ the clearance or the thinnest part).
- **Reproduction:** `json/s14a_tunnel_thin_arm.json` (no MOTION_COLLISION) vs `s14a_control_post_at_5deg.json` (MOTION_COLLISION at 5°), and `json/s14b_tunnel_fast_driven.json`.
- **Proof:** `python verify14.py` uses the engine's own `_moved` + `plate_interference`:
  ```
  s14a ... 5.0 deg step:  ARM at 2: crossing 5.5 | 2.5: crossing 6.5 | 3: crossing 5.5 | 0 and 5: []
  s14b ... 50.0 deg step: ARM at 25: crossing 6.5 | 20, 30, 50: []
  ```
- **Impact:** collisions of long arms, fan blades or fast followers ship undetected. The parts break on first turn.
- **Proposed fix:** a deterministic step bound per motion.
  - Rotation: Δθ = min(5°, c / r_max), where r_max is the farthest board vertex from the axis and c = min(CLEARANCE, min part thickness).
  - Slide: Δs = c.
  - Trains: bound by the fastest member (|ratio|·r_max, or the table's max derivative for links).
  - Then do conservative advancement: after a clear sample, skip ahead only by gap / (r_max·ω). Refine the first hit by bisection, which also fixes M-16.
  - Remove the MAX_SAMPLES cap, or apply it only after reducing the range modulo the period (a 3600° gear repeats every 360°·lcm/teeth).
- **Regression risk:** more samples cost time (see M-05); pair it with tighter broad-phase culling.
- **Acceptance test:** s14a and s14b both report MOTION_COLLISION, with the first contact within 0.5° of the analytic 2.0° / 23°.

### M-02: Independent motions are only checked against each other's rest pose. Severity: High. Architectural limitation.
- **Where:** `check_motions` L708 (`others` = every plate not in this train, posed at rest), and `check_cycles` L774-776, which only groups one root's family.
- **Reproduction:** `json/s14e_two_independent_arms_meet.json`. Arm A (range 0..180) and arm B (−180..0) overlap in x = 50..150 when both are open. Output: only MOTION_AXLE info and WEAK_SECTION warnings.
- **Impact:** double doors, two lids, or a drawer under an open flap can collide in real use without a report.
- **Fix:** check each pair of motions whose swept envelopes (the `env` already computed at L702-707) overlap over the joint configuration space. That means a 2-D grid of samples at the M-01 step, or the extremes plus the boundary curve. Report "only when both open"-type collisions as a warning unless the user declares an interlock or sequence.
- **Acceptance test:** s14e reports MOTION_INTERFERENCE a/b with the angle pair.

### M-03: A connecting rod fixed to static structure is never reported as MOTION_LOCKED. Severity: High. Confirmed bug.
- **Where:** motion.py L646-648: `moving = set(group)`, and `fixed = [joints where (a in moving) != (b in moving)]`. The group is `m['boards']` only. The rod is in no motion's `boards` (parse L150-151 only marks it as `taken`). canvas.py L2237 adds rods to `moving` only to suppress warnings.
- **Reproduction:** `json/s08b_rod_tabbed_to_static_post.json` (`python s08b.py`). The joints come back as `('tab_slot','POST','ROD','joined')`, and the only error is `MOTION_COLLISION: Mechanism driven by 'crank': at 5° 'ROD' runs into 'POST' … (put a rod in its own layer…)`.
- **Impact:** a locked mechanism is described as a layering problem, so the LLM fixes the wrong thing.
- **Fix:** build the moving set as `boards ∪ rods ∪ riders` of the whole train. Flag any non-hinge joined joint that crosses train/static or two trains with different motion values. Generalise this to the joint graph in M-14.
- **Acceptance test:** s08b yields MOTION_LOCKED naming C2-POST-ROD.

### M-04: In mirrored (flipped) assembly instances, a ratio-driven rack/slide runs the wrong way. Severity: High. Confirmed bug.
- **Where:** expand.py `_instance_motion` L581-613. For a driver, `range` is negated when `flip = sgn·det(M) < 0` (L609-612). A driven motion's `ratio` is never adjusted. For a rotate→slide (or rotate→rotate on different axes) coupling, the rotation sense flips with det(M) while the slide sense flips with sgn of its own axis image, so the coupling sign must be multiplied by flip_driven/flip_driver.
- **Reproduction:** `python s11i_flip_rack.py` (`json/s11i_flipped_rack_and_pinion.json`):
  ```
  A : … tooth surface dx = +0.524 mm, rack dx = +0.524 mm -> OK
  FZ: … tooth surface dx = +0.524 mm, rack dx = -0.524 mm -> SLIPS / WRONG WAY
  FX: … tooth surface dx = -0.524 mm, rack dx = -0.524 mm -> OK
  ```
- **Impact:** wrong animation and wrong collision poses. A mirrored rack module that is in fact correct can be flagged, or a broken one passed. Gear-derived ratios are unaffected because they are recomputed after expansion.
- **Fix:** in `_instance_motion`, when `driven_by` and `ratio` are present, store `ratio *= flip_self * flip_driver`. That needs the driver's flip, so it requires a second pass over the instance's motions.
- **Acceptance test:** s11i prints OK for every flip (x, y, z, and combinations).

### M-05: The motion sweep explodes in cost with instanced gear trains, and the app's budget times out. Severity: High. Confirmed bug (performance).
- **Where:** `check_motions` L716-733. The candidate filter is `_box_gap(p.world_aabb(), …) <= CLEARANCE` on the AABB of a rotated square gear box (up to √2 × the gear diameter). Then `_grown` + `plate_interference` runs against involute outlines, and `model.is_material → geometry.near_boundary` is O(n·m) per point.
- **Evidence:** cProfile of n = 2 (`S/p2.prof`): `check_motions` 100.7 s, `check_cycles` 23.4 s, `near_boundary` 99.9 s. Pairs (count, s): I0-G2/I1-G2 152 calls, 23.5 s; I1-G2/I0-PL 162 calls, 19.8 s.
- **Timings:** 1 pair 1.34 s, 2 pairs 78 s, 4 pairs 159 s; `time_budget=90` → `COMPILE_TIMEOUT` (13 boards). 10 pairs had not finished after 9.5 min. Twenty single wheels take 1.0 s, so the problem is gear outlines plus neighbouring trains.
- **Fix:**
  - Use the swept annulus (r_min..r_max about the axis, over the thickness span) as the broad phase instead of the AABB.
  - Cache local-frame polygons and transform the other part into the mover's frame, so one 2-D test runs per sample.
  - Use a bounding circle for gears and pulleys (a gear sweeps exactly its tip circle).
  - Test against the identical instance once, and reuse the result for translated copies.
- **Acceptance test:** `s14d_timing_10_gearpairs.json` compiles in < 10 s.

### M-06: Pins and axles are not solids in any collision check. Severity: Medium. Confirmed missing capability.
- **Where:** `add_axle_holes` L515-549 cuts holes only. No pin or dowel body enters `check_motions` or `check_cycles`. A pin may also bridge a layer gap: the s06 ROD-L crank pin runs z 6..24 through ROD-R's layer, and nothing checks that the boards it joins are contiguous.
- **Reproduction:** `json/s06_butterfly_two_rods.json`, then `python verify06_pin.py`:
  ```
  crank angles where the 4 mm ROD-L crank pin passes through ROD-R: [(184..216)] count 33
  MOTION_COLLISION reported: []
  ```
- **Fix:** model each axle or pin as a cylinder body: its axis, its diameter, and a span from the first to the last holed board plus the protrusion. Attach it to the board it is fixed in (the crank for a crank pin), include it in both sweeps, and require the holed boards to be contiguous or flag the gap.
- **Acceptance test:** s06 reports a pin/ROD-R collision at about 184-216°.

### M-07: The linkage solver silently switches branch at change points. Severity: Medium. Confirmed bug.
- **Where:** `_solve_link` L335 picks `min(cands, key=|x-prev|)`. At h² ≈ 0 both roots coincide and the continuation is arbitrary. There is no change-point or toggle diagnostic.
- **Reproduction:** `json/s05c_parallelogram_change_point.json` (`python s05c.py`). A parallelogram (crank 20 = arm 20, rod 200 = ground 200) gives `(180, 180.0), (190, 171.8), (270, 101.4), (350, 12.2)` and range [0, 180]. The intended coupling (arm = crank) becomes an anti-parallelogram. The only outputs are LINKAGE_TRANSMISSION "down to 0°" and an info "turns back at 181°".
- **Impact:** the animation and collision poses follow one arbitrary branch of an indeterminate mechanism, and the real toy may lock or flip either way.
- **Fix:** detect h² < ε inside the range (a Grashof equality s + l = p + q, or a toggle) and emit LINKAGE_CHANGE_POINT with the crank angle. Carry the branch sign (sg) explicitly, keep it continuous, and only switch where the derivative says so.
- **Acceptance test:** s05c emits LINKAGE_CHANGE_POINT at 0° and 180°.

### M-08: Ratio couplings (rack, belt, explicit gear ratio) have no geometric check. Severity: Medium. Confirmed missing capability.
- **Where:** `_link` L248-258. Any non-zero `ratio` is accepted. `check_gears` only sees `m['mesh']`, which is set only when there is no `ratio`.
- **Reproduction:**
  - `s11a_rack_far_from_pinion.json`: the rack is 200 mm from the pinion, and the output is only MOTION_AXLE info.
  - `s11b_belt_wrong_ratio_no_belt.json`: pulleys Ø60/Ø120 should give +0.5 (same direction); the file gives −3.7, and no belt board exists. The output is only info.
  - `s02f`: meshing 20/30 gears with `ratio: 5` give only a MOTION_COLLISION, with no GEAR_* code.
- **Fix:**
  - Typed couplings: `"rack": {"pinion": gear id, "rack": board}` checks rack-pitch-line distance = r_pitch and the module, and derives ratio = π·m·z/360 mm/deg with the sign from geometry.
  - `"belt": {"pulleys": [a, b], "crossed"?: bool}` derives ratio = ∓D_a/D_b, checks a pulley groove or V-profile, the centre distance range, and the wrap angle, and optionally emits a belt length.
  - When both parts are gears, an explicit ratio must equal −z_a/z_b, or it is an error.
- **Acceptance test:** s11a gives RACK_MESH, s11b gives BELT_RATIO, s02f gives GEAR_RATIO.

### M-09: A revolute or prismatic joint is declared, not built: no axle or guide is required. Severity: Medium. Confirmed missing capability.
- **Where:** `parse_motions` L139-144 (the axle is optional) and `check_motions` (contact ≤ 0.5 mm only).
- **Reproduction:** `s13_rotate_without_any_pivot_hardware.json` (a flap turning about its centre on a wall face) and `s13b_slide_with_no_guide.json` both give 0 diagnostics. `s09` (a lid with no axle and no hinge) also gives no pivot warning.
- **Fix:**
  - A rotate motion without an axle, hinge or pin-joint gives MOTION_NO_PIVOT (warning, or error with interlocking joinery).
  - A slide without a captive guide (two opposing contacts or a slot/rail pair across the slide direction) gives MOTION_NO_GUIDE.
- **Acceptance test:** s13 → MOTION_NO_PIVOT; s13b → MOTION_NO_GUIDE; s01 stays clean.

### M-10: The hinge joint is not reconciled with the motion, and the spec contradicts itself. Severity: Medium. Confirmed bug and missing capability.
- **Where:** canvas.py L2042-2048 builds the hinge joint. motion.py L682 only exempts hinged pairs from collision. `TOUCH=0.5` (L25) conflicts with the hinge spec's default gap of 2 mm (docs "hinge" L188-192).
- **Reproduction:**
  - `s11h_cabinet_door_hinge_on_right_pivot_on_left.json`: the hinge is on the +x edge and the motion pivots about the −x edge. Result: ok = True, zero diagnostics.
  - `s11f_cabinet_door_hinge_gap2_spec_default.json`: MOTION_NOT_MOUNTED "2.0 mm away" for a door drawn exactly as the hinge spec says.
  - `s11d`: on 6 mm stock, HINGE_CUP_TOO_DEEP. Laser stock has no hinge option except the optional axle.
- **Fix:**
  - Derive the motion's axis and pivot from the hinge edge (or check that they match within 0.5 mm / 0.5°).
  - Measure mount contact against the hinged carcass board with the hinge gap allowed.
  - Add a laser-friendly knuckle or pin hinge: interleaved knuckles on both boards, with a dowel through them generated as an axle.
- **Acceptance test:** s11h → MOTION_HINGE_MISMATCH; s11f is clean.

### M-11: Axles have a single support, no retention and no spacers. Severity: Medium. Confirmed missing capability.
- **Where:** `add_axle_holes` L523 drills only `m['boards'] + [m['on']]`. L532-536 reports length = span + 4. Nothing addresses axial retention, a second bearing, a washer, or the hole fit.
- **Reproduction:**
  - `s12a_axle_two_supports.json`: WALL-R sits on the axle line 1 mm beyond the wheel and gets no hole (printout: `WALL-R axle holes: []`). Nothing says what keeps the wheel on.
  - In the same file, VISIBLE_GAP advises "move 'WALL-R' by -7 mm", which would clamp the wheel.
  - `s12b`: a wheel spaced 10 mm off its support → MOTION_NOT_MOUNTED, so a spacer is impossible unless it is drawn as a moving board.
- **Potential (untested):** both the moving and the static hole are cut at exactly Ø d, so there is no running-fit vs press-fit distinction. Check this in production cut files.
- **Fix:** make an axle element with `supports: [board ids]`. Drill all of them, check collinearity (true by construction), and check the span against support spacing. Require a retention feature on each free end: a press-fit hole in one part, a collar/washer board, or a cotter. Emit running-fit (+0.2 mm) and press-fit (−0.1 mm) holes. Suppress VISIBLE_GAP between boards that share an axle with a moving part between them.
- **Acceptance test:** s12a drills WALL-R when it is listed, and warns AXLE_UNRETAINED when no retention is declared.

### M-12: Gear compatibility checks only the module, not the pressure angle. Severity: Medium. Confirmed missing check.
- **Where:** `find_gears` L156-177 does not store `pressure_angle`; `check_gears` L853 compares only the module.
- **Reproduction:** `s02g_gears_pressure_angle_mismatch.json` (20° vs 28°) gives no error. `verify_mesh.py` shows no interference, but the base pitches differ (π·m·cos 20° vs cos 28°), so the action is not conjugate: the ratio varies, and the gears rattle or bind.
- **Note:** meshing pairs are excluded from the dynamic sweep (L772, L815). That is acceptable for matched standard gears (verified with 0/121 interferences for s02b), but it leaves this case to the static check alone.
- **Fix:** add the pressure angle (and the backlash sum vs kerf) to GEAR_MESH. Optionally warn when the contact ratio is < 1.2.
- **Acceptance test:** s02g → GEAR_MESH "pressure angles differ".

### M-13: Clearance is not checked for rods or train parts in the mechanism sweep. Severity: Low. Confirmed.
- **Where:** `check_cycles` L820 (interference only). The rod is never in `check_motions` groups (L630, L696).
- **Reproduction:** `s08c_same_without_post_joint.json`. The rod runs at 0 mm over POST for the whole cycle, with no MOTION_CLEARANCE.
- **Fix:** apply the same `_grown` 1 mm test in `check_cycles`.
- **Acceptance test:** s08c → MOTION_CLEARANCE ROD/POST.

### M-14: There is no degree-of-freedom or mobility analysis, and no single-input rule. Severity: Low to Medium. Architectural limitation.
- **Where:** no Grübler or Kutzbach count exists anywhere (grep for dof, mobility and over-constrain returns nothing). The motion graph is a tree by construction: one `driven_by` per motion and one motion per board.
- **Consequences:**
  - Over-constraint cannot even be expressed. A follower driven by two rods, or a gear meshing two drivers, is impossible, so real loops (a double crank, two gears into one) are unsupported.
  - Physical meshes that are not declared appear only as collisions (`s10e`: G3 meshing G2 with its own range → two MOTION_COLLISIONs, no hint to declare `driven_by`).
  - Two independent inputs are accepted silently (`s10f`), although the spec says "ONE input".
- **Fix:** build a joint graph (revolute, prismatic, gear, rack, belt, pin) from motions, axles, pins and detected meshes (any two gear boards within the centre-distance tolerance in one plane). Compute mobility, report the inputs and any undeclared couplings, and solve loops with a deterministic Newton step on the loop-closure equations seeded from the closed-form solution.

### M-15: Diagnostic text for cycles is wrong, and a missing driver cascades. Severity: Low. Confirmed bug (cosmetic).
- **Where:** `_link.resolve` L210-212. The message prints `path + [drv_id]` without the motion's own id.
- **Reproduction:** `s10c_driven_by_cycle.json` → "Motion 'follow': its drivers go round in a loop (drive -> drive)" and "Motion 'drive': … (follow -> follow)".
- **Second issue:** `s10a`: an unresolved motion is dropped, so its gear is treated as static and an extra MOTION_COLLISION follows.
- **Fix:** use `path + [m['id'], drv_id]`, and suppress collisions involving boards of rejected motions.

### M-16: The reported collision angle is only as fine as the sampling step. Severity: Low. Enhancement.
- **Reproduction:** `s09_lid_hits_shelf.json`: "runs into 'SHELF' at 45°… freely only to 40°". The analytic first contact (shelf corner at dy = 87, dz = −96 from the pivot) is atan(87/96) = 42.2°.
- **Fix:** bisect between the last clear and the first hit sample, down to 0.1°.

### M-17: The front end hides jams. Severity: Low. Potential issue requiring testing.
- **Where:** after LINKAGE_JAM, `_link_table` stops the table at the jam (L371-376). viewport3d.js `interp` (L443-450) clamps, so the crank keeps turning, the follower freezes, and the rod is redrawn between pins that are now further apart than its length (`rod()` L472-478 only rotates it). That is a visibly impossible pose.
- **Expected:** the animation stops the crank at the jam limit.
- **Fix:** export `jam_range` and limit the root's animated range to the reachable interval.

## Capability matrix

| Mechanism | Status | Evidence |
|---|---|---|
| Revolute about x/y/z with axle hole | Supported | s01: holes in both boards, dowel length |
| Revolute physically enforced (axle/hinge required) | Missing | s13, s09: no pivot hardware, no diagnostic (M-09) |
| Prismatic slide (along contact / lift-off) | Partial | MOTION_SLIDE_BLOCKED exists; no guide or captivity check (s13b, M-09) |
| Nested motions (rider on mover) | Supported | test_linkage riders; carried in `board_poses` |
| Spur gear pair, centre distance, module, plane, phase | Supported | s02a-e, verify_mesh 0/121 |
| Gear pressure angle compatibility | Missing | s02g (M-12) |
| Simple and compound gear trains, direction propagation | Supported | s03a (−2/3, then +4/3 overall), s03b (+1/9) |
| Explicit-ratio gear coupling checked against teeth | Missing | s02f (M-08) |
| Bevel / crossed-axis gears | Missing | s11c: GEAR_MESH "not in one plane" |
| Rack and pinion | Partial | ratio only, no geometry (s11a); wrong sign in z-flipped instances (s11i, M-04) |
| Belt / pulley | Partial | ratio only: no belt, distance, ratio or direction check (s11b) |
| Four-bar crank-rocker, Grashof jam | Supported | s05a, s05b LINKAGE_JAM with limits |
| Change-point / branch handling | Missing | s05c silent flip (M-07) |
| Slider-crank | Supported | s04, stroke = 2r |
| Cam (profiled cam plus follower contact) | Missing | only an eccentric acting as a crank (spec L343); no follower-contact solver |
| One input driving several mechanisms | Supported | s07, s06 |
| Steering / Ackermann / spatial linkages | Missing | links must be planar with the same axis (`_link_problem` L301-304) |
| Cabinet cup hinge plus motion | Partial | needs ≥ 16 mm; 2 mm gap → NOT_MOUNTED; axis not reconciled (M-10) |
| Laser knuckle / pin hinge | Missing | only the living-hinge kerf pattern, which is not simulated (hinge.py docstring) |
| Fixed joint locking a moving board | Supported | s08a MOTION_LOCKED |
| Fixed joint locking a rod | Missing | s08b (M-03) |
| Mid-travel collision with last clear position | Supported (coarse) | s09 (M-16 resolution) |
| Continuous collision (no tunnelling) | Missing | s14a/b (M-01) |
| Collision between independent motions | Missing | s14e (M-02) |
| Pin / axle solids in collision | Missing | s06 verify (M-06) |
| Running clearance for rods / trains | Missing | s08c (M-13) |
| Multi-support shaft, retention, washers, bushings, fit | Missing | s12a/b (M-11) |
| DOF / mobility, over/under-constraint | Missing | no code (M-14) |
| driven_by validation (missing, cycle, self) | Supported | s10a/c/d errors (text bug M-15) |
| Instanced / turned motions | Partial | 90° turns OK (tests); flip breaks ratio couplings (M-04); gear instances time out (M-05) |
| Front-end animation | Supported (from backend data) | ratio and table from backend; clamps on jam (M-17) |

## Recommended architecture (deterministic, no LLM-computed frames)

1. **Kinematic graph IR** built after expansion. Bodies are rigid board groups, and each pin and axle is its own body. Joints are typed: revolute (with a support list), prismatic (with a guide list), gear (z, m, pressure angle), rack, belt, pin-slot, and planar four-bar loop closure. The ratio and its sign are always derived from geometry, never from the LLM. `ratio` stays only as an escape hatch for an explicit "drive", with a mandatory geometric check.
2. **Mobility and consistency:** a Grübler count per planar subsystem, a list of inputs, detection of undeclared meshes and contacts, and lock detection over all fixed joints across bodies (this fixes M-03 and M-14).
3. **Solver:** the existing closed-form solutions, plus explicit branch tracking and change-point detection (M-07). Loops fall back to Newton on the closure equations, seeded from the closed form. Output a pose table per input.
4. **Collision:** a broad phase on swept annuli, a local-frame narrow phase, an adaptive step bounded by r_max·Δθ ≤ clearance, bisection of the first contact, and pairwise envelope tests across independent inputs (M-01, M-02, M-05, M-16).
5. **Manufacturability:** axle and pin solids, support and retention rules, fit-class holes, knuckle hinges (M-06, M-09, M-10, M-11).
6. **Front end** keeps consuming backend tables (including jam-limited ranges), so the 3D view and the checks never diverge.
