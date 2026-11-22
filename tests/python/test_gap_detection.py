"""
Numeric verification of joint GAP / OVERLAP detection.

Coordinate space per check (stated because every number below depends on it):
  * tab/slot gap:      receiver-local z (signed distance of the tab shoulder from the receiver face)
  * edge butt gap:     receiver-local z of the mating edge
  * face lap gap:      separation of the two mid-planes along a's normal (world), minus (ta+tb)/2
  * mitre overlap:     in the plane perpendicular to the shared edge (world)
  * collisions:        each board's own local frame against the other board's thickness slab
Tolerances come only from TOL / design.material — no new numbers are introduced here.
"""
import copy
import json
import math
import os
import pathlib
import re
import shutil
import subprocess

import pytest

from board_engine.autofix import auto_fix, plan_fixes
from board_engine.cutpaths import generate_cut_paths
from board_engine.joining import check_joint, join
from board_engine.model import build_plates, find_component, normalize_design
from board_engine.nesting import nest
from board_engine.operations import apply_operation
from board_engine.validation import TOL, evaluate_joint, find_collisions, validate_design

from conftest import GOOD_SLOT, TAB_JOINT, base_plate, make, wall

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
TOLC = TOL['contact']


def errors(res):
    return [i for i in res['issues'] if i['severity'] == 'error']


def evaluate(d, joint):
    return evaluate_joint(d, build_plates(d), joint)


def by_code(res, code):
    return next(i for i in res['issues'] if i['code'] == code)


def apply_delta(d, comp_id, delta):
    pos = find_component(d, comp_id)['placement']['position']
    for k in range(3):
        pos[k] += delta[k]


def slotted_pair(**wall_kw):
    return make(base_plate(features=[copy.deepcopy(GOOD_SLOT)]), wall(**wall_kw))


# ---------------------------------------------------------------------------------------------
# 1. 90 degree tab/slot: flush, inside tolerance, gap, penetration (receiver-local z)
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize('offset, code', [(0.0, None), (0.1, None), (0.5, 'UNINTENDED_GAP'), (-0.5, 'PENETRATION')])
def test_tab_slot_gap_matrix(offset, code):
    d = slotted_pair()
    apply_delta(d, 'WALL', [0, offset, 0])
    res = evaluate(d, TAB_JOINT)
    assert res['gaps'] == pytest.approx([offset] * 3, abs=0.01)
    if code is None:
        assert res['ok']
        return
    i = by_code(res, code)
    assert i['components'] == ['WALL', 'BASE']
    assert i['gap' if offset > 0 else 'overlap'] == pytest.approx(abs(offset), abs=0.01)
    apply_delta(d, 'WALL', i['suggestion']['delta'])            # the suggested move must close it exactly
    after = evaluate(d, TAB_JOINT)
    assert after['ok'] and after['gaps'] == pytest.approx([0, 0, 0], abs=0.01)


def tilted_wall(deg, pivot_x):
    """Wall rotated `deg` about world Z, keeping the root point at local x = pivot_x on the base face."""
    a = math.radians(deg)
    lx, ly = pivot_x, -20.0
    wx, wy = lx * math.cos(a) - ly * math.sin(a), lx * math.sin(a) + ly * math.cos(a)
    return wall(placement={'position': [pivot_x - wx, 3.0 - wy, 0], 'rotation': [0, 0, deg]})


def test_tab_tilted_2deg_gap_at_one_end_only():
    # pivot on the x=-10 end of the 20 mm tab root: that end is flush, the other end lifts 20*sin(2°)
    d = make(base_plate(features=[copy.deepcopy(GOOD_SLOT)]), tilted_wall(2.0, -10.0))
    res = evaluate(d, TAB_JOINT)
    expect = 20 * math.sin(math.radians(2))
    assert res['gaps'][0] == pytest.approx(0.0, abs=0.01) and res['gaps'][2] == pytest.approx(expect, abs=0.01)
    i = by_code(res, 'UNINTENDED_GAP')
    assert i['gap'] == pytest.approx(expect, abs=0.01)
    assert i['tilt_deg'] == pytest.approx(2.0, abs=0.05)
    assert 'suggestion' not in i            # a translation cannot fix a tilt; which board to rotate is a decision
    assert 'J1' in {u['joint'] for u in plan_fixes(dict(d, joints=[dict(TAB_JOINT, status='detached')]))['unfixable']}


def test_tab_tilted_2deg_about_centre_reports_both_ends():
    d = make(base_plate(features=[copy.deepcopy(GOOD_SLOT)]), tilted_wall(2.0, 0.0))
    res = evaluate(d, TAB_JOINT)
    half = 10 * math.sin(math.radians(2))
    assert res['gaps'] == pytest.approx([-half, 0.0, half], abs=0.01)
    assert by_code(res, 'UNINTENDED_GAP')['gap'] == pytest.approx(half, abs=0.01)
    assert by_code(res, 'PENETRATION')['overlap'] == pytest.approx(half, abs=0.01)


def test_tab_leaning_3deg_does_not_fit_nominal_slot():
    # wall leans 3° about the tab-width axis (world X), pivoting on the root line: shoulder flush everywhere,
    # but the tilted tab sweeps 3/cos3° + 3*tan3° = 3.16 mm across the 3 mm board -> nominal 3.1 slot is too narrow
    a = math.radians(3)
    d = make(base_plate(features=[copy.deepcopy(GOOD_SLOT)]),
             wall(placement={'position': [0, 3 + 20 * math.cos(a), 20 * math.sin(a)], 'rotation': [3, 0, 0]}))
    res = evaluate(d, TAB_JOINT)
    assert res['gaps'] == pytest.approx([0, 0, 0], abs=0.01)
    i = by_code(res, 'SLOT_TOO_SMALL')
    swept = 3 / math.cos(a) + 3 * math.tan(a)
    assert i['repair']['feature']['height'] == pytest.approx(swept + 0.10, abs=0.01)


# ---------------------------------------------------------------------------------------------
# 2. Arbitrary angles
# ---------------------------------------------------------------------------------------------

def test_wall_yawed_60deg_gets_rotated_slot_and_exact_gap():
    # wall turned 60° about the vertical axis: slot must be generated at ±60° in base-local XY
    d = make(base_plate(), wall(placement={'position': [0, 23, 0], 'rotation': [0, 60, 0]}))
    res = join(d, TAB_JOINT, auto_repair=True)
    assert res['accepted']
    slot = find_component(res['design'], 'BASE')['features'][0]
    assert abs(((slot['angle'] + 90) % 180) - 90) == pytest.approx(60.0, abs=0.01)
    assert (slot['width'], slot['height']) == (pytest.approx(20.1), pytest.approx(3.1))
    dd = copy.deepcopy(res['design'])
    apply_delta(dd, 'WALL', [0, 0.5, 0])
    r = evaluate(dd, dict(TAB_JOINT, slot=slot['id']))
    assert by_code(r, 'UNINTENDED_GAP')['gap'] == pytest.approx(0.5, abs=0.01)


def test_wall_at_60deg_dihedral_cannot_insert():
    d = make(base_plate(), wall(placement={'position': [0, 23, 0], 'rotation': [30, 0, 0]}))
    assert errors(evaluate(d, TAB_JOINT))[0]['code'] == 'ORIENTATION_MISMATCH'


# ---------------------------------------------------------------------------------------------
# 3. T / cross-halving / corner butt / mitre
# ---------------------------------------------------------------------------------------------

def notched(cid, notch_from_top, depth, rot):
    """60 x 40 board with a (t+clr) notch of `depth` from the top or bottom edge, centred."""
    w = 3.1
    if notch_from_top:
        outline = [[-30, -20], [30, -20], [30, 20], [w / 2, 20], [w / 2, 20 - depth], [-w / 2, 20 - depth], [-w / 2, 20], [-30, 20]]
    else:
        outline = [[-30, -20], [-w / 2, -20], [-w / 2, -20 + depth], [w / 2, -20 + depth], [w / 2, -20], [30, -20], [30, 20], [-30, 20]]
    return {'id': cid, 'outline': outline, 'placement': {'position': [0, 0, 0], 'rotation': [0, rot, 0]}}


def test_cross_halving_correct_notches_do_not_collide():
    d = make(notched('A', True, 20, 0), notched('B', False, 20, 90))
    assert find_collisions(d, build_plates(d)) == []


def test_cross_halving_shallow_notches_collide():
    d = make(notched('A', True, 16, 0), notched('B', False, 16, 90))   # 4 mm of solid wood left crossing
    hits = find_collisions(d, build_plates(d))
    assert hits and {frozenset(h['components']) for h in hits} == {frozenset({'A', 'B'})}
    assert hits[0]['interference']['length'] == pytest.approx(8.0, abs=1.0)


def corner_pair(b_x):
    """A spans x in [-20, 20] (XY plane); B is a YZ-plane board at x = b_x (thickness 3)."""
    A = {'id': 'A', 'outline': [[-20, 0], [20, 0], [20, 20], [-20, 20]], 'placement': {'position': [0, 0, 0], 'rotation': [0, 0, 0]}}
    B = {'id': 'B', 'outline': [[-10, 0], [10, 0], [10, 20], [-10, 20]], 'placement': {'position': [b_x, 0, 0], 'rotation': [0, 90, 0]}}
    return make(A, B)


@pytest.mark.parametrize('overlap, expect', [(0.0, False), (0.2, False), (0.5, True), (1.0, True), (3.0, True)])
def test_corner_butt_through_thickness_overlap(overlap, expect):
    # A's end face at x = 20; B's near face at b_x - 1.5. overlap = 20 - (b_x - 1.5)
    d = corner_pair(21.5 - overlap)
    hits = find_collisions(d, build_plates(d))
    assert bool(hits) is expect, hits
    if expect:
        assert hits[0]['components'] == ['A', 'B']


@pytest.mark.parametrize('phi', [90.0, 47.9])
def test_square_edge_mitre_reports_thickness_overlap(phi):
    # interior angle phi between the boards; square-cut 3 mm edges overlap by (t/2)(1+cos phi)/sin phi
    A = {'id': 'A', 'outline': [[-20, 0], [0, 0], [0, 20], [-20, 20]], 'placement': {'position': [0, 0, 0], 'rotation': [0, 0, 0]}}
    # B's material runs from the shared edge (world Y axis) along local -x; yawing by -phi points it along
    # (-cos phi, 0, -sin phi), i.e. phi away from A's material direction (-1, 0, 0)
    B = {'id': 'B', 'outline': [[-20, 0], [0, 0], [0, 20], [-20, 20]], 'placement': {'position': [0, 0, 0], 'rotation': [0, -phi, 0]}}
    d = dict(make(A, B), joinery='glue_allowed')
    res = evaluate(d, {'id': 'M', 'type': 'edge_mitre', 'a': 'A', 'a_edge': 1, 'b': 'B', 'b_edge': 1})
    p = math.radians(phi)
    expect = 1.5 * (1 + math.cos(p)) / math.sin(p)
    i = by_code(res, 'PENETRATION')
    assert i['overlap'] == pytest.approx(expect, abs=0.01)
    assert i['bevel_deg'] == pytest.approx(phi / 2, abs=0.05)
    assert 'suggestion' not in i                        # which board to shorten is a design decision
    assert find_collisions(d, build_plates(d))          # and the assembly check sees the same solid overlap


def test_coplanar_edge_join_has_no_thickness_overlap():
    A = {'id': 'A', 'outline': [[-20, 0], [0, 0], [0, 20], [-20, 20]], 'placement': {'position': [0, 0, 0], 'rotation': [0, 0, 0]}}
    B = {'id': 'B', 'outline': [[0, 0], [20, 0], [20, 20], [0, 20]], 'placement': {'position': [0, 0, 0], 'rotation': [0, 0, 0]}}
    d = dict(make(A, B), joinery='glue_allowed')
    res = evaluate(d, {'id': 'M', 'type': 'edge_mitre', 'a': 'A', 'a_edge': 1, 'b': 'B', 'b_edge': 3})
    assert not any(i['code'] == 'PENETRATION' for i in res['issues'])


def butt_pair(b_x=0.0, features=()):
    A = {'id': 'A', 'outline': [[-20, -10], [20, -10], [20, 10], [-20, 10]],
         'placement': {'position': [0, 10, 0], 'rotation': [0, 90, 0]}}          # edge 1 faces world -z
    B = {'id': 'B', 'outline': [[-30, -10], [30, -10], [30, 10], [-30, 10]], 'features': list(features),
         'placement': {'position': [b_x, 10, -21.5], 'rotation': [0, 0, 0]}}
    return dict(make(A, B), joinery='glue_allowed')


BUTT = {'id': 'E', 'type': 'edge_butt', 'a': 'A', 'a_edge': 1, 'b': 'B'}


def test_edge_butt_thickness_overhanging_receiver_end_is_reported():
    d = butt_pair(b_x=29.5)        # B ends at x = -0.5: A's mid-plane lands 0.5 mm in, its +t/2 face hangs off
    res = evaluate(d, BUTT)
    i = by_code(res, 'EDGE_PARTIALLY_SUPPORTED')
    assert i['severity'] == 'warning' and min(i['contact_by_line']) == pytest.approx(0.0, abs=0.6)


def test_edge_butt_over_opening_narrower_than_thickness_is_partially_supported():
    hole = {'id': 'o', 'kind': 'opening', 'shape': 'rect', 'center': [0, 0], 'width': 2.0, 'height': 18}
    res = evaluate(butt_pair(features=[hole]), BUTT)
    assert not any(i['code'] == 'NOT_IN_CONTACT' for i in res['issues'])     # outer faces still rest on material
    assert by_code(res, 'EDGE_PARTIALLY_SUPPORTED')['severity'] == 'warning'


def test_edge_butt_over_opening_wider_than_thickness_is_not_in_contact():
    hole = {'id': 'o', 'kind': 'opening', 'shape': 'rect', 'center': [0, 0], 'width': 4.0, 'height': 18}
    assert by_code(evaluate(butt_pair(features=[hole]), BUTT), 'NOT_IN_CONTACT')['severity'] == 'error'


@pytest.mark.parametrize('qz, expect_delta', [(3.5, 0.5), (-3.5, -0.5)])
def test_face_lap_antiparallel_sign(qz, expect_delta):
    P = {'id': 'P', 'outline': [[-20, -10], [20, -10], [20, 10], [-20, 10]], 'placement': {'position': [0, 0, 0], 'rotation': [0, 0, 0]}}
    Q = {'id': 'Q', 'outline': [[-20, -10], [20, -10], [20, 10], [-20, 10]], 'placement': {'position': [0, 0, qz], 'rotation': [0, 180, 0]}}
    d = dict(make(P, Q), joinery='glue_allowed')
    i = by_code(evaluate(d, {'id': 'F', 'type': 'face_lap', 'a': 'P', 'b': 'Q'}), 'UNINTENDED_GAP')
    assert i['gap'] == pytest.approx(0.5, abs=0.01) and i['suggestion']['delta'][2] == pytest.approx(expect_delta, abs=0.01)
    apply_delta(d, 'P', i['suggestion']['delta'])
    assert evaluate(d, {'id': 'F', 'type': 'face_lap', 'a': 'P', 'b': 'Q'})['ok']


# ---------------------------------------------------------------------------------------------
# 4. Mixed thickness and per-material clearance (Python vs JS config.js)
# ---------------------------------------------------------------------------------------------

def test_3mm_tab_into_6mm_board():
    d = make(base_plate(thickness=6.0, placement={'position': [0, 3.0, 0], 'rotation': [-90, 0, 0]}),
             wall(placement={'position': [0, 26, 0], 'rotation': [0, 0, 0]}))        # base top face at y = 6
    res = join(d, TAB_JOINT, auto_repair=True)
    assert res['accepted'] and any(i['code'] == 'TAB_NOT_FLUSH' for i in res['issues'])
    slot = find_component(res['design'], 'BASE')['features'][0]
    assert slot['height'] == pytest.approx(3.0 + 0.10)                  # tab-board thickness + clearance
    dd = copy.deepcopy(res['design'])
    apply_delta(dd, 'WALL', [0, 0.5, 0])
    assert by_code(evaluate(dd, dict(TAB_JOINT, slot=slot['id'])), 'UNINTENDED_GAP')['gap'] == pytest.approx(0.5, abs=0.01)


def js_profiles():
    src = open(os.path.join(ROOT, 'js/core/config.js')).read()
    return [tuple(float(x) for x in m) for m in
            re.findall(r"thickness:\s*([\d.]+),\s*kerf:\s*([\d.]+),\s*clearance:\s*([\d.]+)", src)]


@pytest.mark.parametrize('t, kerf, clr', js_profiles())
def test_slot_and_kerf_match_js_profile(t, kerf, clr):
    d = normalize_design({'id': 'm', 'material': {'thickness': t, 'kerf': kerf, 'clearance': clr},
                          'components': [base_plate(placement={'position': [0, t / 2, 0], 'rotation': [-90, 0, 0]}),
                                         wall(tabs=[{'id': 't1', 'edge': 0, 'offset': 40, 'width': 20, 'depth': t}],
                                              placement={'position': [0, t + 20, 0], 'rotation': [0, 0, 0]})]})
    res = join(d, TAB_JOINT, auto_repair=True)
    assert res['accepted'], res['issues']
    slot = find_component(res['design'], 'BASE')['features'][0]
    assert slot['height'] == pytest.approx(t + clr, abs=1e-6)
    cut = generate_cut_paths(res['design'], nest(res['design'], {'preset': 'A4'}), compensate_kerf=True)
    p = next(x for s in cut['sheets'] for x in s['paths'] if x.get('feature_kind') == 'slot')['points']
    widths = sorted(math.dist(p[i], p[(i + 1) % 4]) for i in range(4))
    assert widths[0] == pytest.approx(t + clr - kerf, abs=1e-3)           # kerf applied once: kerf/2 per side
    node = shutil.which('node')
    if node:
        js = subprocess.run([node, '--input-type=module', '-e',
                             f"import {{ ConnectorStandards as C }} from '{pathlib.Path(ROOT, 'js/core/connectors.js').as_uri()}';"
                             f"console.log(JSON.stringify(C.calculateSlotDimensions({t}, {clr}, {kerf})))"],
                            capture_output=True, text=True, check=True)
        dims = json.loads(js.stdout)
        assert dims['width'] == pytest.approx(slot['height'], abs=1e-9)
        assert dims['kerfCompensatedWidth'] == pytest.approx(widths[0], abs=1e-3)


# ---------------------------------------------------------------------------------------------
# 5. Multi-board autofix and termination
# ---------------------------------------------------------------------------------------------

def test_autofix_board_with_four_joints_keeps_every_joint_closed(boat):
    b = copy.deepcopy(boat)
    apply_operation(b, {'op': 'translate', 'id': 'BULKHEAD-1', 'delta': [0, 1.2, 0], 'detach_broken_joints': True})
    work, rep = auto_fix(b)
    assert rep['valid'] and rep['complete']
    plates = build_plates(work)
    for j in work['joints']:
        if 'BULKHEAD-1' in (j['a'], j['b']):
            r = evaluate_joint(work, plates, j)
            assert r['ok'] and r['gaps'] == pytest.approx([0, 0, 0], abs=0.01), j['id']


def test_autofix_conflicting_demands_terminates_without_oscillation():
    # LID sits 2 mm too high for WALL's top tab while BASE is correct for its bottom tab: moving WALL up would
    # break the joined bottom joint, so the top joint must be reported as not auto-fixable — not ping-ponged.
    w = wall(tabs=[{'id': 't1', 'edge': 0, 'offset': 40, 'width': 20, 'depth': 3},
                   {'id': 't2', 'edge': 2, 'offset': 40, 'width': 20, 'depth': 3}])
    lid = base_plate(id='LID', placement={'position': [0, 46.5, 0], 'rotation': [-90, 0, 0]})
    d = join(make(base_plate(), w, lid), TAB_JOINT, auto_repair=True)['design']
    d['joints'].append({'id': 'J2', 'type': 'tab_slot', 'a': 'WALL', 'tab': 't2', 'b': 'LID', 'status': 'detached'})
    work, rep = auto_fix(d, max_steps=50)
    assert rep['steps'] == [] and [s['fix']['id'] for s in rep['skipped']] == ['J2:translate']
    assert evaluate_joint(work, build_plates(work), work['joints'][0])['gaps'] == pytest.approx([0, 0, 0], abs=0.01)


# ---------------------------------------------------------------------------------------------
# 6. Overlap without a joint, and degenerate input
# ---------------------------------------------------------------------------------------------

def test_overlapping_boards_without_joint_collide():
    d = make(base_plate(), wall(tabs=[], placement={'position': [0, 21, 0], 'rotation': [0, 0, 0]}))   # 2 mm into base
    hits = find_collisions(d, build_plates(d))
    assert hits and hits[0]['code'] == 'COLLISION' and set(hits[0]['components']) == {'BASE', 'WALL'}


def test_degenerate_input_never_raises():
    comps = [
        {'id': 'ZERO', 'outline': [[0, 0], [10, 0], [20, 0]]},                                     # no area
        {'id': 'DUPV', 'outline': [[0, 0], [0, 0], [10, 0], [10, 10]],                            # zero-length edge with a tab
         'tabs': [{'id': 't', 'edge': 0, 'offset': 0, 'width': 0.5, 'depth': 0.1}]},
        {'id': 'THIN', 'thickness': 0.5, 'outline': [[0, 0], [0.6, 0], [0.6, 0.6], [0, 0.6]],
         'tabs': [{'id': 't', 'edge': 0, 'offset': 0.3, 'width': 0.5, 'depth': 0.1}]},
        {'id': 'DUP1', 'outline': [[0, 0], [5, 0], [5, 5], [0, 5]]},
        {'id': 'DUP2', 'outline': [[0, 0], [5, 0], [5, 5], [0, 5]]},
    ]
    d = normalize_design({'id': 'deg', 'components': comps,
                          'joints': [{'id': 'J', 'type': 'tab_slot', 'a': 'DUPV', 'tab': 't', 'b': 'ZERO', 'status': 'detached'},
                                     {'id': 'K', 'type': 'tab_slot', 'a': 'THIN', 'tab': 't', 'b': 'DUP1'}]})
    rep = validate_design(d)
    assert not rep['valid']
    for spec in d['joints']:
        check_joint(d, spec)
        join(d, dict(spec, id=spec['id'] + 'x'), auto_repair=True)
    plan_fixes(d)
    auto_fix(d, max_steps=5)
    n = nest(d, {'preset': 'A4'})
    generate_cut_paths(d, n, compensate_kerf=True)


# ---------------------------------------------------------------------------------------------
# 7. Regressions found while fixing the above
# ---------------------------------------------------------------------------------------------

def test_line_intervals_are_well_formed_when_the_line_hits_vertices_or_edges():
    from board_engine.validation import _polygon_line_intervals
    tabbed = [[0, 0], [100, 0], [100, 10], [80, 10], [80, 13], [60, 13], [60, 10], [40, 10], [40, 13], [20, 13], [20, 10], [0, 10]]
    for y in (0.0, 10.0, 13.0, 11.5, 5.0):            # bottom edge, tab roots, tab tops, inside tabs, body
        ivs = _polygon_line_intervals(tabbed, [-5, y], [1, 0])
        assert all(r1 >= r0 for r0, r1 in ivs)
    assert _polygon_line_intervals(tabbed, [-5, 11.5], [1, 0]) == [(25.0, 45.0), (65.0, 85.0)]   # only the tabs


def test_boards_touching_at_tab_corners_are_not_collisions(boat):
    # was a false COLLISION (BULKHEAD-1 / KEEL) when a sampling station passed exactly through tab corners
    hits = find_collisions(boat, build_plates(boat))
    assert hits == []


def test_boat_hull_corners_neither_overlap_nor_open():
    # stem (47.9°) and shoulders (156°): one board is shortened by (t/2)(1+cos phi)/sin phi so the square-cut
    # end rests on the other board's inner face. Shortening it 0.5 mm less must bring the overlap back.
    from board_engine.examples import boat as B
    comps = B.build_components()
    d = normalize_design({'id': 'hull', 'components': comps})
    pairs = {frozenset(h['components']) for h in find_collisions(d, build_plates(d))}
    assert frozenset({'SIDE-BOW-PORT', 'SIDE-BOW-STBD'}) not in pairs
    port = next(c for c in comps if c['id'] == 'SIDE-BOW-PORT')
    for p in port['outline']:
        p[0] += 0.5 if p[0] > 0 else 0.0                # lengthen the forward (stem) end by 0.5 mm
    d = normalize_design({'id': 'hull2', 'components': comps})
    pairs = {frozenset(h['components']) for h in find_collisions(d, build_plates(d))}
    assert frozenset({'SIDE-BOW-PORT', 'SIDE-BOW-STBD'}) in pairs


def test_interference_cache_follows_geometry_changes():
    d = corner_pair(20.5)                                 # 1.0 mm overlap
    assert find_collisions(d, build_plates(d))
    find_component(d, 'B')['placement']['position'][0] = 21.5   # now just touching
    assert find_collisions(d, build_plates(d)) == []
