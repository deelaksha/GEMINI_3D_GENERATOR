# Mechanical Engineering Gap Analysis

**Scope:**
- `board_engine/motion.py` (940 lines);
- `expand.py` `_instance_motion` (working tree);
- the motion wiring in `canvas.py` (≈L1920-1922, L2150, L2236-2242);
- `shapes.py` (involute gear);
- `hinge.py`;
- `js/studio/viewport3d.js` L416-490 (animation).

**Method:** about 55 mechanism scenarios written as `board-design/v1` JSON and compiled with `canvas.compile_source(..., run_production=False)`.
- Each scenario file is in `evidence/mechanical/json/`, with its builder script and independent verifiers (`verify14.py`, `verify06_pin.py`, `verify_mesh.py`).
- The full specialist report, `evidence/mechanical/mech_audit.md`, has an output excerpt for every scenario.
- Items marked **(R)** were re-run independently by the lead auditor.

---

## 1. How motion works today (verified)

- **Declaration:** the LLM declares `motions`: `rotate` / `slide`, `boards`, `on`, `axis`/`direction`, `pivot`, `range`, optional `axle`, `driven_by`, `ratio`, and `link` (rod, from, to, pin).
- **Solving is deterministic and in the backend.**
  - Gear couplings are ratio chains, with ratios from the tooth counts and the sign flipped per mesh (`motion._link` L180-266).
  - Four-bar and slider-crank linkages are solved in closed form as circle-circle or line-circle intersections (`_solve_link` L308-335), tabulated over the input range (`_link_table` L363-380).
  - **The LLM never computes animation frames.** That is the correct architecture, and it should be kept.
- **Front end:** it applies the backend's ratio and table (`viewport3d.js` L439-490). Nothing is re-solved in the browser.
- **Checks:**
  - **Per motion** (`check_motions` L613-761): mount contact ≤ 0.5 mm, MOTION_LOCKED (a fixed joint between moving and static boards), slide direction, interference plus a 1 mm running clearance at sampled poses.
  - **Per mechanism** (`check_cycles` L764-835): all parts of a train posed together, interference only.
  - **Per gear mesh** (`check_gears` L842-921): module, common plane, gear on its axle, centre distance ±0.1 mm, tooth phase with an exact fix value (GEAR_PHASE).

## 2. Capability matrix

| Mechanism / capability | Status | Evidence (scenario file) |
|---|---|---|
| Rotating shaft / axle, axis x, y or z, with dowel holes and dowel length | **Supported** | `s01_wheel_axis_x`: Ø6 holes in WHEEL and WALL, "dowel about 16 mm" |
| Pivot hardware *required* (axle, hinge or pin) | **Missing** | `s13_rotate_without_any_pivot_hardware`: 0 diagnostics (R); `s09` lid has no pivot hardware and gets no warning |
| Bearings / bushings, running vs press fit | **Missing** | same hole diameter in moving and static boards (code); no bushing element |
| Multi-support shaft, collinearity, axial retention, spacers | **Missing** | `s12a`: second wall on the axle line gets no hole, nothing retains the wheel, and VISIBLE_GAP advises clamping it; `s12b`: a spacer cannot be expressed |
| Spur gear pair (module, plane, centre distance, phase) | **Supported** | `s02a-e`; `verify_mesh.py` 0/121 interfering samples for the phased pair |
| Gear pressure-angle compatibility | **Missing** | `s02g` 20° vs 28°: no diagnostic |
| Simple and compound gear trains, direction propagation | **Supported** | `s03a` A=90° → B=−60°, C=+120°; `s03b` compound 1/9 |
| Explicit ratio checked against teeth | **Missing** | `s02f` ratio 5 on 20/30 gears: only an indirect collision |
| Bevel / crossed-axis gears | **Missing** | `s11c`: GEAR_MESH "not in one plane" |
| Rack and pinion | **Partial** | ratio only: rack 200 mm from pinion accepted (`s11a`); runs the wrong way in z-flipped instances (`s11i`) |
| Belt / pulley | **Partial** | ratio only: wrong ratio and sign, no belt board, accepted (`s11b`) |
| Crankshaft / crank | **Supported** (as a rotate motion with a pin offset) | `s04`, `s05a` |
| Connecting rod | **Supported** | rod pinned at both ends, holes cut, posed through the cycle |
| Slider-crank (reciprocating motion) | **Supported** | `s04`: stroke 40.0 mm = 2 × crank radius |
| Four-bar crank-rocker (oscillating motion), Grashof jam | **Supported** | `s05a` clean; `s05b` LINKAGE_JAM "at 110° … limit to [0,108]" |
| Change point / branch tracking | **Missing** | `s05c` parallelogram silently flips to anti-parallelogram |
| Cam and follower (profiled lobe) | **Missing** | only an eccentric disc acting as a crank (the spec says so) |
| Hinge (cabinet cup) with motion | **Partial** | needs ≥ 16 mm boards; the spec's own default 2 mm gap → MOTION_NOT_MOUNTED (`s11f`); hinge edge vs pivot edge mismatch accepted silently (`s11h`) |
| Laser knuckle / pin hinge | **Missing** | only the living-hinge kerf pattern (not simulated) |
| Lever mechanisms | **Supported** as rotate plus link | — |
| Pulley systems, lifting | **Missing** (beyond the belt ratio) | — |
| Steering / Ackermann, spatial linkages | **Missing** | linkages must be planar with the same axis (`_link_problem` L301-304) |
| Prismatic slide | **Partial** | slide direction checked (MOTION_SLIDE_BLOCKED); no guide or captivity check (`s13b`: 0 diagnostics) |
| Nested motions (wing tip on wing, jaw on head) | **Supported** | test_linkage riders |
| One input (motor or hand crank) driving several mechanisms | **Supported** | `s07` gear plus rocker continuous; `s06` two rods off one crank, synchronised wings |
| Synchronised motion | **Supported** | via shared driver; `s06` 180° phase offset |
| Moving board locked by a static joint | **Supported** | `s08a` MOTION_LOCKED |
| Linkage rod locked by a static joint | **Missing** | `s08b`: no MOTION_LOCKED, only a misleading collision (R) |
| Mid-travel collision with last clear position | **Supported (coarse)** | `s09` "at 45° … freely only to 40°" (analytic contact 42.2°) |
| Continuous (no tunnelling) collision | **Missing** | `s14a` thin arm (R), `s14b` ratio-10 follower sampled every 50° |
| Collision between independent motions | **Missing** | `s14e` two arms meeting when both open: not reported |
| Pins and axles as solids | **Missing** | `s06`: a crank pin passes through the other rod for 33° of crank, not reported |
| Running clearance for rods / train parts | **Missing** | `s08c` rod at 0 mm over a post for the whole cycle |
| DOF / mobility; over- or under-constrained assemblies | **Missing** | no Grübler or Kutzbach code; `s10f` two independent inputs accepted silently |
| driven_by validation (missing, cycle, self) | **Supported** | `s10a`, `s10c`, `s10d` → MOTION_INVALID (cycle message text wrong) |
| Instanced / turned / flipped mechanisms | **Partial** | 90° turns fine; flip breaks ratio sign (`s11i`); instanced gear pairs explode in cost (`s14d`) |

**Distinction between joint kinds** (request §7). The current model distinguishes:

| Kind | Represented by |
|---|---|
| Static connection | `tab_slot`, `finger`, `cross_lap`, `butt`, `mitre` |
| Revolute | `rotate` motion (with optional axle) |
| Prismatic | `slide` motion |
| Driven vs passive | `driven_by` present or absent |
| Independent moving assembly | a root motion without `driven_by` |
| Mechanical constraint | gear mesh (checked), rod link (solved) |

It does **not** represent:
- the physical revolute or prismatic *hardware* (pins, guides, supports) as a requirement;
- closed kinematic loops other than the single four-bar or slider-crank;
- any count of degrees of freedom.

## 3. Findings

| ID | Severity | Classification | Location | Summary | Repro |
|---|---|---|---|---|---|
| M-01 | High | Confirmed bug | `motion._samples` L594-606 (`ROTATE_STEP=5.0` L27, `MAX_SAMPLES=72` L28) | Fixed 5° step and a 72-sample cap let parts tunnel. A tip at r = 300 mm moves 26 mm per step; a ratio-10 follower is sampled every 50° | `s14a_tunnel_thin_arm` (R), `s14b_tunnel_fast_driven`; `verify14.py` confirms overlap at 2–3° and 25° using the engine's own `plate_interference` |
| M-02 | High | Architectural limitation | `check_motions` L708 (others posed at rest); `check_cycles` L774-776 | Independent motions are never checked against each other's moving poses | `s14e_two_independent_arms_meet` |
| M-03 | High | Confirmed bug | `motion.py` L644-648 (`moving = set(group)`, rods excluded) | Rod tab_slotted to a static post: no MOTION_LOCKED; the error tells the user to "put the rod in its own layer" | `s08b_rod_tabbed_to_static_post` (R) |
| M-04 | High | Confirmed bug | `expand._instance_motion` L581-613 | Ratio sign not corrected when an instance is mirrored: rack −0.524 mm vs tooth surface +0.524 mm | `s11i_flipped_rack_and_pinion` |
| M-05 | High | Performance issue | `check_motions` L716-733: rotated-AABB broad phase + `near_boundary` O(n·m) on gear outlines | Instanced gear pairs: 1 pair 1.3 s, 2 pairs 78 s, 4 pairs 159 s (COMPILE_TIMEOUT at the 90 s budget), 10 pairs > 9.5 min | `s14d_timing_*`; profile in `evidence/mechanical/` |
| M-06 | Medium | Missing capability | `add_axle_holes` L515-549 (holes only) | Pins and axles are not solid bodies in any sweep | `s06_butterfly_two_rods`, `verify06_pin.py` |
| M-07 | Medium | Confirmed bug | `_solve_link` L335 (`min(|x−prev|)` branch pick) | Silent branch flip at change points | `s05c_parallelogram_change_point` |
| M-08 | Medium | Missing capability | `_link` L248-258 | Rack, belt and explicit ratios accepted without geometry | `s11a`, `s11b`, `s02f` |
| M-09 | Medium | Missing capability | `parse_motions` L139-144; `check_motions` | Rotate without pivot hardware and slide without a guide: 0 diagnostics | `s13` (R), `s13b` (R) |
| M-10 | Medium | Bug + missing | `canvas.py` L2042-2048, `motion.py` L682, `TOUCH=0.5` L25 | Hinge edge vs motion pivot not reconciled; hinge gap 2 mm (spec default) fails mounting; no laser hinge | `s11h`, `s11f`, `s11d` |
| M-11 | Medium | Missing capability | `add_axle_holes` L523, L532-536 | One support only; no retention, spacer or fit class | `s12a`, `s12b` |
| M-12 | Medium | Missing check | `find_gears` L156-177, `check_gears` L853 | Pressure angle not compared | `s02g` |
| M-13 | Low | Confirmed | `check_cycles` L820 | No running clearance check for rods / train parts | `s08c` |
| M-14 | Low–Med | Architectural limitation | (absent) | No mobility analysis; loops cannot be expressed; undeclared meshes only appear as collisions; multiple inputs accepted | `s10e`, `s10f` |
| M-15 | Low | Cosmetic bug | `_link.resolve` L210-212 | Cycle message prints `drive -> drive`; a dropped motion cascades into collisions | `s10c`, `s10a` |
| M-16 | Low | Enhancement | `_samples` | Collision angle only as precise as the step (no bisection) | `s09` |
| M-17 | Low | Potential (code only) | `viewport3d.js` L443-478 | After a jam the follower is clamped while the crank turns on, so the rod is drawn in an impossible pose | — |

## 4. How to represent mechanisms without the LLM computing frames

The current split of responsibilities is right: the LLM declares topology and intent, and software computes motion. The gap is that the *topology is too implicit* and the *hardware is optional*. Proposed design, all deterministic:

### 4.1 Kinematic graph IR (new module `board_engine/kinematics.py`, built after `expand`)

- **Bodies:** rigid groups of boards (from the motions' `boards` plus static structure). Every pin and axle is its own body with a cylinder solid.
- **Joints (typed):**
  - `revolute{axis, pivot, supports:[board], axle_diameter, fit: running|press}`
  - `prismatic{direction, guides:[board pairs], travel}`
  - `gear{a, b}`: module, teeth and **pressure angle** read from the profiles; ratio = −z_a/z_b derived, never written.
  - `rack{pinion, rack}`: pitch-line distance checked; ratio = π·m·z/360 mm/° with the sign from geometry.
  - `belt{pulleys, crossed}`: ratio = ∓D_a/D_b, centre-distance range and wrap angle checked.
  - `pin{body_a, body_b}`: rod ends.
  - `fixed`: every static connection.
- **LLM-facing schema change** (backwards compatible):
  - the current `motions` stay valid;
  - new optional `"axle": {"diameter", "supports": [...], "retain": "collar|press|cotter"}`, `"guide": [...]`, `"couple": {"type": "rack|belt", ...}`;
  - `ratio` stays only as an escape hatch, and is checked against the geometry when the coupling is recognisable.

### 4.2 Mobility and consistency
- A Grübler count per planar subsystem; the list of inputs; a warning when there is more than one input unless declared.
- Detect **undeclared couplings**: two gear boards in one plane within the centre-distance tolerance; a rod touching two moving bodies.
- **Lock detection** over *all* fixed joints between bodies with different motion values. This fixes M-03 and generalises MOTION_LOCKED.

### 4.3 Solver
- Keep the closed-form four-bar and slider-crank solutions.
- Add explicit branch tracking (carry the sign of the assembly mode) and **change-point detection** (h² < ε → LINKAGE_CHANGE_POINT with the angle).
- Arbitrary planar loops: Newton iteration on the loop-closure equations, seeded from the closed form, with a convergence report.
- Output one pose table per input. The front end keeps animating from it, including jam-limited ranges (fixes M-17).

### 4.4 Full-cycle collision
- **Broad phase:** swept annulus (r_min..r_max about the axis × thickness span) instead of the rotated AABB. Gears use their tip circle.
- **Narrow phase:** transform the other part into the mover's local frame and do one 2-D polygon test per sample. Use shapely or the existing plate machinery.
- **Adaptive step:** Δθ ≤ c / r_max, where c = min(running clearance, thinnest part). For trains, bound by the fastest member (|ratio|·r_max, or the max derivative of the link table).
- **Precision:** bisect to the first contact (fixes M-16).
- **Independent motions:** sample the product of their ranges, coarse then refined, wherever their swept envelopes overlap. Report MOTION_INTERFERENCE as a warning unless the user declares the motions mutually exclusive.
- **Pins and axles** are included as solids (M-06). The rod and driven-part running clearance is checked as for motions (M-13).

### 4.5 Manufacturability of the mechanism
- Rotate motions require a pivot: an axle, a hinge or a pin (M-09). Slides require a captive guide (M-09).
- **Axle element:** all listed supports drilled; span vs support spacing; a retention feature on every free end; running fit (+0.2 mm) vs press fit (−0.1 mm) holes. Suppress VISIBLE_GAP between supports that share an axle with a moving part between them (M-11).
- **Laser knuckle hinge:** interleaved knuckles on both boards plus a generated pin. Reconcile the hinge edge with the motion pivot, or derive the pivot from the hinge (M-10).
- **Gear checks:** add the pressure angle, the backlash vs kerf sum, and a contact-ratio warning below 1.2 (M-12).

### 4.6 Bevel gears, cams, steering (later phase)
- **Bevel:** a `bevel_gear` profile pair on perpendicular plates. The flat-board approximation is crown-and-pinion or a peg gear: the face gear's pegs (tabs) mesh with a spur. Check the shaft intersection and the cone geometry; ratio = −z_a/z_b.
- **Cam:** a cam profile (spline or polygon) on a rotating disc plus a follower (slide or rocker) with a roller or flat foot. Software computes follower displacement as the support function of the cam profile along the follower line. It is solvable exactly and deterministically, and gives the pressure angle (warn above 30°).
- **Steering:** an Ackermann trapezoid is a planar four-bar in the horizontal plane. It is supported once the four-bar solver accepts a vertical axis and a horizontal-plane loop, and the tie rod is a rod link.

## 5. Acceptance criteria (mechanics)

| # | Scenario | Required result |
|---|---|---|
| 1 | `s14a_tunnel_thin_arm`, `s14b_tunnel_fast_driven` | MOTION_COLLISION with the first contact within 0.5° of the analytic angle (2.0°, 23°) |
| 2 | `s14e_two_independent_arms_meet` | MOTION_INTERFERENCE naming both motions and the angle pair |
| 3 | `s08b_rod_tabbed_to_static_post` | MOTION_LOCKED naming the rod joint |
| 4 | `s11i_flipped_rack_and_pinion` | Rack displacement equals tooth-surface displacement for every flip combination |
| 5 | `s14d_timing_10_gearpairs` | Compiles in < 10 s |
| 6 | `s06_butterfly_two_rods` | Pin / ROD-R collision reported over ≈184–216° |
| 7 | `s05c_parallelogram_change_point` | LINKAGE_CHANGE_POINT at 0° and 180° |
| 8 | `s11a`, `s11b`, `s02f` | RACK_MESH, BELT_RATIO, GEAR_RATIO errors respectively |
| 9 | `s13`, `s13b` | MOTION_NO_PIVOT, MOTION_NO_GUIDE; `s01` stays clean |
| 10 | `s11h`, `s11f` | MOTION_HINGE_MISMATCH; `s11f` clean |
| 11 | `s12a` | A listed support is drilled; AXLE_UNRETAINED when no retention is declared |
| 12 | `s02g` | GEAR_MESH "pressure angles differ" |
| 13 | `s09` | Contact reported at 42.2° ± 0.5° |
| 14 | All existing `tests/python/test_motion.py`, `test_gears.py`, `test_linkage.py` | Still pass |
