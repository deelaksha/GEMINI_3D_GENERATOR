# Test Execution Report

**Environment:**
- Linux 7.0.0-43, Python 3.12.3, Node v18.19.1.
- An isolated venv with `requirements-dev.txt` installed: Flask 3.1.3, shapely 2.2.0, pytest 9.2.0, anthropic 2.14.0, plus `pytest-timeout`.
- All runs used `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`, and the compile snapshot cache stayed in memory, so **nothing was written into the project tree**.
- **No LLM API key** was configured or used.

**Result vocabulary:** PASS, FAIL, PARTIAL (works with a defect), NOT TESTED (with the blocker), INFO (measurement).
**Failure attribution:** *SW* = deterministic software; *LLM* = model output; *ENV* = environment or harness.

Raw outputs are in `evidence/`:
- `baseline/pytest_baseline.txt`, `baseline/node_tests.txt`;
- `performance/results.jsonl`, `performance/corpus.jsonl`;
- probe designs in `geometry/cases/`, `mechanical/json/`, `pipeline/`.

---

## 1. Baseline: existing test suites

| Suite | Command | Result | Time |
|---|---|---|---|
| Python (`tests/python`, 45 files incl. the uncommitted `test_generators.py`) | `python -m pytest tests/python -p no:cacheprovider -q --timeout=600` | **671 passed, 0 failed, 0 skipped** | 289.7 s wall; peak RSS 207 MB |
| JS `tests/joint_fit_suite.mjs` | `node tests/joint_fit_suite.mjs` | PASS ("53 / 53 CHECKS PASSED") | <5 s |
| JS `tests/test_drafting_math.mjs` | `node …` | PASS (prints success) | <5 s |
| JS `tests/test_measure_scale.mjs` | `node …` | PASS | <5 s |
| JS `tests/test_slant_dims.mjs` | `node …` | PASS | <5 s |
| JS `tests/test_slant_joint_dims.mjs` | `node …` | PASS | <5 s |
| `tests/e2e/*.py` (browser smoke, AI scoring) | — | NOT TESTED: needs a running server plus browser automation; `score_ai_outputs.py` needs LLM outputs | — |

Note on the JS runs: these scripts print their own verdict, and the exit status was captured through a pipe (`| tail`). The printed verdicts are the evidence.

**Slowest Python tests:**
- `test_e2e_agent::…boat` 16.9 s;
- `test_scale::…parallel_checks` 15.9 s;
- `test_scale::…200_operations` 14.8 s;
- `test_api::test_boat_example_and_production_exports` 13.8 s.

**Coverage gaps in the existing suite** (each is where this audit found a defect):
- no test of the LLM transport failure modes (truncation, refusal, multi-part on the server path);
- no AI-fix acceptance test;
- no completeness test;
- no "every construction the prompt recommends compiles" test;
- no shallow-angle or narrow-strip collision test;
- no motion tunnelling test;
- no rod-lock test;
- no flipped ratio test;
- no NaN test;
- no schema unknown-field test;
- no anonymous-delete test.

---

## 2. Corpus: every bundled and real AI-generated design (production on)

`evidence/performance/corpus.py` → `corpus.jsonl`. `ok` = compiled without errors; `ready` = `layout.ready_for_production`.

| Design | Source | Boards | ok | ready | Errors | Time s | Attribution |
|---|---|---|---|---|---|---|---|
| prompt EXAMPLE (study table) | prompt | 5 | ✔ | ✔ | – | 0.91 | – |
| prompt COMPLEX_EXAMPLE (cottage) | prompt | 7 | ✔ | ✔ | – | 0.54 | – |
| prompt STRUCTURES_EXAMPLE (organiser) | prompt | 8 | ✔ | ✔ | – | 2.20 | – |
| examples/boat_seed | repo | 14 | ✔ | ✔ | – | 0.64 | – |
| examples/my_home | repo | 341 | ✔ | ✔ | – | 19.58 | – |
| fixtures/ai_birdhouse | real LLM | 7 | ✔ | ✔ | – (8 warnings) | 0.44 | – |
| fixtures/ai_bookshelf | real LLM | 8 | ✔ | ✔ | – | 1.81 | – |
| fixtures/ai_cabinet | real LLM | 7 | ✔ | ✔ | – | 3.23 | – |
| fixtures/ai_winerack | real LLM | 8 | ✔ | ✔ | – | 1.89 | – |
| fixtures/titanic_unjoined | real LLM | 92 | ✘ | ✘ | 78: SLOT_ALREADY_USED 22, MISSING_SLOT 22, COLLISION 16, UNATTACHED_BOARD 10, NO_CONTACT 4, TAB_OUTSIDE_RECEIVER 4 | 6.73 | LLM (a complex ship: shared slots, overlaps, unjoined parts) |
| village_house | fixture | 21 | ✔ | ✔ | – | 4.56 | – |
| ai_runs/out_old/A | real LLM (old prompt) | 18 | ✘ | ✘ | SLOT_ALREADY_USED 12 | 6.32 | LLM |
| ai_runs/out_old/A2 (repaired) | real LLM | 18 | ✔ | ✔ | – | 5.59 | – |
| ai_runs/out_old/B, B2 | real LLM | 20 | ✔ | ✘ / ✔ | – (22 warnings) | 0.15 | LLM (warnings) |
| ai_runs/out_old/C, C2 | real LLM | 4 | ✔ | ✔ | – | 0.36 | – |
| ai_runs/out_old/D | real LLM | 13 | ✘ | ✘ | OVERALL_MISMATCH | 0.68 | LLM |
| ai_runs/out_new/A | real LLM (31.7k prompt) | 17 | ✔ | ✔ | – | 7.05 | – |
| ai_runs/out_new/B | real LLM | 21 | ✔ | **✘ (50 blocking)** | – | 0.13 | LLM + UX (F-22: `ok` while not ready) |
| ai_runs/out_new/B2 / B3 | real LLM | 21 | ✔ | ✘ (13) / ✔ | – | 0.13 | LLM |
| ai_runs/out_new/C, C2, D | real LLM | 4–6 | ✔ | ✔ | – | 0.4–0.6 | – |

**Observation:** every real LLM design in the repo that compiles clean is simple furniture or a small toy. The only complex product (the ship) has 78 errors. There is no LLM evidence at all for the current 98k prompt.

---

## 3. Product scenarios requested in §16

### 3.1 LLM-generated product scenarios: NOT TESTED

**Blocker:** generation needs `GEMINI_API_KEY` or `ANTHROPIC_API_KEY`. None is configured, and paid usage was not approved. The affected scenarios are:

| Category | Scenarios |
|---|---|
| Architectural | simple wooden house, Victorian mansion, Japanese temple, castle, IT technology park, fantasy theme park |
| Transportation | aeroplane with enclosed fuselage, steam locomotive with wheel linkage, automobile with steering, ship |
| Mechanical | butterfly, multi-mechanism by one crank |

**Estimated cost to run:**
- 12 products × 2 providers × 2 prompt versions ≈ 48 generations of ~25k input / ≤64k output tokens, plus repairs.
- This is the measurement plan in `PROMPT_ENGINEERING_AUDIT.md` §7.

### 3.2 Deterministic proxies that *were* executed for those scenarios

These test what the engine can represent and validate for each category, independently of any LLM.

| Scenario | Proxy executed | Result | Verdict |
|---|---|---|---|
| Simple wooden house (complete) | prompt COMPLEX_EXAMPLE cottage | ok, ready | PASS |
| House **missing roof** | `geometry/cases/V1_cottage_no_roof_R_nooverall.json` | **ok=True** | FAIL (SW: no completeness check, F-04) |
| House missing roof + wall | `V2_cottage_no_roof_no_wall_nooverall.json` | **ok=True** | FAIL (SW, F-04) |
| Open box (organiser without front) | `V3_organiser_no_front.json` | **ok=True** | FAIL (SW, F-04) |
| Large building, many boards | `examples/my_home.json` (341 boards) | ok, 19.6 s with production | PASS |
| Village / theme park scale (repeated buildings) | perf "cottages" family (instances of the cottage), 49–1,925 boards | compiles; time is linear in boards (§5) | INFO |
| Ship hull | real LLM `titanic_unjoined.json` | 78 errors | FAIL (LLM) |
| Aeroplane slotted construction (profiled fuselage × profiled wing) | `prompt/probe.py` | `JOINT_NEEDS_PLAIN_BOARD` | FAIL (SW capability gap / prompt mismatch, F-11) |
| Curved fuselage via morph ribs on a keel | `prompt/probe2.py` (prompt's own example) | 0 errors, 5 warnings (MISMATCHED_PAIR, MISALIGNED) | PARTIAL (F-15) |
| Polygonal tower / radial structure | `geometry/cases/E1_radial_spokes_hub_overlap.json`, `prompt/probe2.py` radial blades | collision detected; radial copies warn MISALIGNED | PARTIAL |
| Sloped roof intersection (tilted tab_slot) | COMPLEX_EXAMPLE, `J17_tilted_tabslot_gap.json` | joined; non-parallel edge → NO_CONTACT | PASS |

### 3.3 Mechanical scenarios (executed, deterministic)

All files are in `evidence/mechanical/json/`. **(R)** = re-run by the lead auditor.

| # | Scenario | Expected | Actual | Result |
|---|---|---|---|---|
| 1 | Single rotating axle (`s01_wheel_axis_x`) | joined, axle holes | clean, Ø6 holes, dowel ≈16 mm, 0.07 s | PASS |
| 2 | Two meshing gears (`s02a/b`) | clean once phased | GEAR_PHASE fix "rotation 6", then clean, 1.2 s | PASS |
| 2b | Wrong centre distance / module / plane (`s02c/d/e`) | GEAR_MESH errors | GEAR_MESH with calculation | PASS |
| 2c | Pressure angle 20° vs 28° (`s02g`) | error | none | FAIL (SW, M-12) |
| 3 | Multi-stage gear train (`s03a`, `s03b`) | correct ratio and direction | B=−60°, C=+120° at A=90°; compound 1/9 | PASS |
| 4 | Crank-driven reciprocating (`s04_slider_crank`) | stroke 2r | 40.0 mm | PASS |
| 5 | Four-bar (`s05a`), non-Grashof (`s05b`) | clean / jam | clean / LINKAGE_JAM at 110° | PASS |
| 5c | Parallelogram change point (`s05c`) | change-point diagnostic | silent branch flip | FAIL (SW, M-07) |
| 6 | Butterfly, synchronised wings (`s06`) | solved, collisions found | solved; pin-through-rod for 33° not reported | PARTIAL (SW, M-06) |
| 7 | One crank → gear train + linkage (`s07`) | continuous | continuous | PASS |
| 8a | Moving board locked by tab_slot (`s08a`) | MOTION_LOCKED | MOTION_LOCKED | PASS |
| 8b | Rod locked by tab_slot to post (`s08b_rod_tabbed_to_static_post`) (R) | MOTION_LOCKED | only MOTION_COLLISION | FAIL (SW, M-03) |
| 9 | Collision during motion: lid hits shelf (`s09`) | collision with angle | "at 45°, freely to 40°" (true 42.2°) | PASS (coarse) |
| 9b | Thin arm tunnelling (`s14a_tunnel_thin_arm`) (R) | collision | none (control at 5° caught) | FAIL (SW, M-01) |
| 9c | Fast driven follower (`s14b`) | collision | none | FAIL (SW, M-01) |
| 9d | Two independent arms meet (`s14e`) | interference | none | FAIL (SW, M-02) |
| 10 | Disconnected transmission: driven_by missing (`s10a`), gear not meshing (`s10b`), cycle (`s10c`) | errors | MOTION_INVALID / GEAR_MESH / MOTION_INVALID (message text wrong) | PASS (cosmetic M-15) |
| 11 | Rack far from pinion (`s11a`), belt wrong ratio (`s11b`) | errors | accepted | FAIL (SW, M-08) |
| 11b | Flipped rack-and-pinion instance (`s11i`) | same direction | rack runs the wrong way | FAIL (SW, M-04) |
| 11c | Hinge edge ≠ motion pivot (`s11h`) | error | ok, 0 diagnostics | FAIL (SW, M-10) |
| 12 | Rotate without pivot hardware (`s13`) (R); slide without guide (`s13b`) (R) | warning or error | ok=True, 0 diagnostics | FAIL (SW, M-09) |
| 13 | 20 instanced wheels (`s14c`) | fast | 1.02 s | PASS |
| 14 | 4 / 10 instanced gear pairs (`s14d`) | < 10 s | 159 s (timeout at 90 s budget) / >9.5 min | FAIL (SW perf, M-05) |

### 3.4 Negative and boundary tests (requested list)

| Test | Input | Expected | Actual | Result | Attr. |
|---|---|---|---|---|---|
| Missing board (roof) | V1/V2/V3 cases | completeness error | ok=True | FAIL | SW |
| Floating component | `N1_isolated.json` | ISOLATED_BOARD | ISOLATED_BOARD | PASS | – |
| Disconnected group | `N2_disconnected_group.json` | DISCONNECTED | DISCONNECTED | PASS | – |
| Touching, not joined | `N3_not_joined_touching.json` | NOT_JOINED | NOT_JOINED | PASS | – |
| Non-touching, bbox-near | `C2_board_in_L_notch.json`, `C4a_*` | ISOLATED / DISCONNECTED | NOT_JOINED "touches it" (wrong advice) | PARTIAL | SW (F-18) |
| Duplicate board id | `J11_duplicate_board_id.json` | error | DUPLICATE_BOARD_ID | PASS | – |
| Duplicate board, identical geometry | `J16_two_walls_same_place_same_side.json` | DUPLICATE / COLLISION | merged by consolidation, ok=True | FAIL | SW (F-13) |
| Duplicate slot (opposite sides) | `J06_duplicate_slot_opposite_sides.json` | error | SLOT_ALREADY_USED + COLLISION | PASS | – |
| Slot too close to edge | `J09_slot_near_edge.json` | error | SLOT_AT_EDGE | PASS | – |
| Tab on opening | `J08_tab_on_opening.json` | error | TAB_IN_OPENING | PASS | – |
| Connection gap 5 mm | `J14_gap_5mm.json` | error | CONNECTION_GAP | PASS | – |
| Self connection | `J13_self_connection.json` | error | SELF_CONNECTION | PASS | – |
| Incorrect thickness (no axis equals thickness) (R) | EXAMPLE with LEG-L size `[20, 732, 560]` on 18 mm stock | error | THICKNESS_MISMATCH | PASS | – |
| Invalid polygon (bow-tie) | `T04_selfintersect_profile.json` | reject | OUTLINE_SELF_INTERSECTION | PASS | – |
| Profile outside box | `T06_profile_outside_box.json` | reject | PROFILE_INVALID | PASS | – |
| Invalid rotation (4 compound steps; docs say ≤3) | geometry probe | reject | accepted | FAIL (minor) | SW (G-11) |
| Shallow-tilt overlap | `C6*` (R) | COLLISION | none | FAIL | SW (F-05) |
| Narrow parallel overlap strip | `C8_large_parallel_strip_5mm/10mm.json` (R) | COLLISION | none | FAIL | SW (F-05) |
| Collision during motion | `s09` | MOTION_COLLISION | reported | PASS | – |
| Disconnected mechanical transmission | `s10a`, `s10b` | error | error | PASS | – |
| Impossible assembly sequence | `A2_box_with_trapped_inner.json`, `A1`, `A3`, `A4` | ASSEMBLY_LOCKED | planner found valid orders for all probes; a truly locked case was not constructed; planner output dropped from the compile result (F-17) | PARTIAL / NOT FULLY TESTED | SW |
| Oversized prompt | requirements > 4,000 chars | reported | silently truncated to 4,000 (`routes.py`) | FAIL (minor) | SW |
| Oversized design (20k boards from 237 bytes) | `pipeline/t_dos.py` | stop within budget (22 s) | 730 s, 857 MB, then COMPILE_TIMEOUT | FAIL | SW (F-08) |
| 100k-board cap | repeat 100×100×10 | STRUCTURE_INVALID | STRUCTURE_INVALID | PASS | – |
| Truncated LLM response (at board boundary) | EXAMPLE cut before `MODESTY` (R) | error | safe repair → **ok=True, 3/5 boards, ready_for_production** | **FAIL (Critical)** | SW (F-01) |
| Truncated LLM response (mid-token) | cut at 50/80/95 % | error | JSON_SYNTAX → repaired → BOARD_GEOMETRY error | PASS (by chance) | – |
| Gemini `MAX_TOKENS` through ai-generate (stub) | `pipeline/t_maxtok.py` | 502 / flagged | 200 with partial text | FAIL | SW (F-01) |
| Malformed JSON (comments, trailing commas, prose + fence) | pipeline tests 22–23 | compile | compile | PASS | – |
| Deep nesting 100k | pipeline test 16 | clean error | JSON_TOO_DEEP | PASS | – |
| NaN / Infinity | (R) | BOARD_GEOMETRY only | + COMPILER_ERROR (design lost); 500 on integer-fix route | FAIL | SW (F-16) |
| Unsupported schema field | `color_scheme`, `bevel_angle`, `hinge_type`, `springs` | warning | silent | FAIL | SW (F-12) |
| Misspelled `"conections"` | pipeline `t2.py` | error | ok=True, joints auto-inferred | FAIL | SW (F-12) |
| Unknown `format` version | `totally-other/v9` | error | warning, ok=True | FAIL | SW (E-11) |
| Repeated repair failure | stubbed `/ai-fix` returning a regressed design (`t_aifix.py`) | rejected / stall detected | accepted, `changed: true` | FAIL | SW (F-03) |
| Safe fix on a repeated board | `pipeline/t_fixgen.py` | applies | KeyError → 422, UI retries | FAIL | SW (F-21) |
| Consolidation across groups / hinge | `t_cons.py` A/B | kept separate | merged; hinge dropped | FAIL | SW (F-13) |
| Kerf direction | `t_mfg.py` | outer +k/2, holes −k/2 | correct (203.2 mm outer, 40.9 × 2.9 slot path) | PASS | – |
| Anonymous session deletes another's design | `t_flask.py` | 403 | 200 | FAIL | SW (F-09) |
| AI hourly quota with a new session | `t_flask.py` | still limited | bypassed | FAIL | SW (F-09) |
| Path traversal (/docs, /js, /css; 6 variants) | `t_flask.py` | 404 | 404 | PASS | – |
| CSRF header missing | `t_flask.py` | 401 | 401 | PASS | – |

**Totals for the probe and negative sets:**

| Area | Cases | Pass | Fail | Partial |
|---|---|---|---|---|
| Geometry | 60 table rows (≈75 design files; some rows cover variants) | 43 | 10 | 7 |
| Pipeline | 44 | 22 | 19 | 3 |
| Mechanical | about 55 runs | full table in `evidence/mechanical/mech_audit.md` | | |

The geometry counts come from the table in `evidence/geometry/geom_audit.md` (section "Test cases run").

---

## 4. Prompt measurements (deterministic)

| Prompt | chars | ≈ tokens |
|---|---|---|
| generation, no images | 98,359 | 24.6k |
| generation, images | 103,021 | 25.8k |
| repair, 5.2k-char design | 79,728 | 19.9k |
| repair, `my_home.json` (341 boards) | 396,936 | ~99k |
| update, 5.2k-char design | 89,825 | 22.5k |
| `hard_constraints("1200 x 600 x 750 mm desk, 18 mm plywood, simple realistic")` (R) | → `x: 750 mm`, `a size: 18 mm`, `detail level: 5` | FAIL (F-10) |

LLM response time, output tokens and repair iterations: **NOT TESTED** (no API key).

---

## 5. Performance and scalability (measured)

**Harness:** `evidence/performance/one.py`, one subprocess per size, with stage times from the compiler's own progress reporter and peak RSS from `getrusage`. The machine was idle apart from this test.

### 5.1 Family "slats"

Vertical fins tab_slotted into one base: a worst case for one receiving board.

| Boards | Production | Total s | parse | geometry | joints | dimensions | joint_validation | collisions | model | Peak RSS MB | ok |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 51 | off | 0.91 | 0.01 | 0.02 | 0.16 | 0.02 | 0.01 | 0.61 | 0.09 | 22 | ✔ |
| 101 | off | 1.75 | 0.01 | 0.02 | 0.32 | 0.02 | 0.01 | 1.18 | 0.18 | 25 | ✔ |
| 301 | off | 8.95 | 0.02 | 0.11 | 2.80 | 0.07 | 0.05 | 5.30 | 0.60 | 34 | ✔ |
| 501 | off | 17.94 | 0.03 | 0.18 | 6.84 | 0.11 | 0.12 | 9.65 | 1.00 | 42 | ✔ |
| 1,001 | off | 61.42 | 0.04 | 0.29 | 28.05 | 0.22 | 0.38 | 30.28 | 2.15 | 64 | ✔ |
| 2,001 | off | 220.10 | 0.15 | 0.70 | 119.49 | 0.45 | 1.22 | 93.46 | 4.64 | 107 | ✘ (base exceeds sheet: expected) |
| 5,001 | off | **> 900 (killed by harness timeout)** | – | – | – | – | – | – | – | – | NOT COMPLETED |
| 51 | on | 1.35 | | | 0.15 | | | 1.07 | | 22 | ✔ |
| 301 | on | 12.04 | | | 2.38 | | | 8.85 | | 36 | ✔ |
| 1,001 | on | 120.22 | | | 26.77 | | | 90.04 | | 88 | ✔ |
| 2,001 | on | **689.58** | 0.15 | 0.65 | 111.15 | 0.90 | 2.95 | **570.00** | 3.78 | 217 | ✘ (base exceeds sheet: expected) |

With production on, the collision stage grows from 90 s (1,001 boards) to 570 s (2,001 boards), ×6.3 for twice the boards. The production pass adds work that the progress reporter books under the collision stage. This is consistent with the "validation and support computed twice per compile" item P-1 from the prior audit, but the production pass was **not profiled** in this audit.

### 5.2 Family "cottages"

Instances of the cottage example, 7 boards each, including 2 tilted roof panels. Each cottage is a separate structure, so DISCONNECTED errors are expected.

| Boards | Total s | joints | collisions | Peak RSS MB | Errors |
|---|---|---|---|---|---|
| 49 | 2.99 | 0.22 | 2.36 | 42 | DISCONNECTED (expected) |
| 98 | 5.80 | 0.35 | 4.77 | 46 | DISCONNECTED (expected) |
| 240 | 14.22 | 0.86 | 11.81 | 58 | + BOARD_SIZE / BOARD_INVALID (ENV) |
| 482 | 29.14 | 1.42 | 24.41 | 79 | same (ENV) |
| 959 | 56.51 | 2.77 | 46.70 | 120 | same (ENV) |
| 1,925 | 119.12 | 5.92 | 97.96 | 203 | same (ENV) |
| 3,105 (of 5,000 requested) | 198.53 | 9.60 | 157.65 | 316 | 1,824 BOARD_SIZE (ENV: grid exceeded ±5,000 mm, so most boards invalid; not representative) |

The BOARD_SIZE / BOARD_INVALID errors come from the harness: its 20-column grid exceeds the ±5,000 mm coordinate limit. They are not engine defects.

### 5.3 Interpretation

- **Cottages:** time is linear, about 0.06 s per board, dominated by the collision stage. Boards are spread over many small receivers.
- **Slats:** the `joints` stage is **quadratic** (×4.3 per doubling) and the collision stage super-linear (×3.1 per doubling). Here many tabs share one receiving board.

**Profile** (cProfile, 600 slats, 57 s):

| Function | Calls | Cumulative s | Note |
|---|---|---|---|
| `validation._eval_tab_slot` → `geometry.polygons_overlap` | 360,000 (= 600²) | 17.6 | 5.8 M `segments_intersect`; slot lookup scans every feature of the receiving board with no bbox pre-filter |
| `validation._station_features` | 7,200 | 13.1 | |
| `joining.join` → `evaluate_joint` | 3 per join | | joints re-evaluated |

Root cause: see ENGINEERING_AUDIT_REPORT F-08.

**Other measurements:**
- **Time-budget enforcement** (pipeline `t_dos.py`): a 20,000-board expansion ran 730 s against a 22 s budget, with 857 MB RSS. A 4,000-board case ran 6.0 s against 0.89 s.
- **Mechanisms:** instanced gear pairs 1.3 s / 78 s / 159 s for 1 / 2 / 4 pairs (M-05).
- **Not measured:**
  - LLM latency and token usage (no key);
  - browser render time and GPU memory (no browser automation in this audit);
  - repair iterations to convergence (needs an LLM).

---

## 6. Reproduction quick reference

```bash
cd /home/sonic-claude2/deelaksha/desighn/GEMINI_3D_GENERATOR
python -m venv /tmp/gv && /tmp/gv/bin/pip install -r requirements-dev.txt pytest-timeout
PYTHONDONTWRITEBYTECODE=1 /tmp/gv/bin/python -m pytest tests/python -p no:cacheprovider -q
# a probe design
PYTHONDONTWRITEBYTECODE=1 /tmp/gv/bin/python -c "
import sys; sys.path.insert(0,'.')
from board_engine.canvas import compile_source
r = compile_source(open('ENGINEERING_AUDIT_2026-11-28/evidence/geometry/cases/V1_cottage_no_roof_R_nooverall.json').read(), run_production=False)
print(r['ok'], [(d['severity'], d['code']) for d in r['diagnostics']])"
# scaling
PYTHONDONTWRITEBYTECODE=1 /tmp/gv/bin/python ENGINEERING_AUDIT_2026-11-28/evidence/performance/one.py slats 1000 0
```

Some evidence scripts in `evidence/*/` contain absolute paths to the auditor's scratch directory. Point them at `ENGINEERING_AUDIT_2026-11-28/evidence/...` before re-running.
