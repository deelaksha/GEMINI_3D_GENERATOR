"""Mechanics audit 2026-11-28 (M-01..M-17): one test per acceptance row of MECHANICAL_ENGINEERING_GAP_ANALYSIS.md §5,
on the audit's own scenario files (copied to fixtures/mech)."""
import copy
import json
import math
import os
import re
import time

import pytest

from board_engine import canvas
from board_engine.motion import board_poses, train_values, _at

FIX = os.path.join(os.path.dirname(__file__), 'fixtures', 'mech')


@pytest.fixture(autouse=True)
def _no_snapshots(monkeypatch):
    monkeypatch.setattr(canvas, 'SNAPSHOT_DIR', None)


def load(name):
    with open(os.path.join(FIX, name + '.json')) as f:
        return json.load(f)


def compiled(d):
    return canvas.compile_source(json.dumps(d), run_production=False)


def diags(r, code, severity=None):
    return [x for x in r['diagnostics'] if x['code'] == code and (severity is None or x['severity'] == severity)]


def contact(msg):
    """The bisected first-contact value a MOTION_COLLISION message reports."""
    return float(re.search(r'first contact at (-?[\d.]+)', msg).group(1))


def first_touch(corner, half_width):
    """Angle (degrees, about +y through the origin) at which an arm along +x, half_width mm either side of its centre
    line, first touches a post corner (x, z): the corner's own angle less asin(half width / its distance). (The
    audit's 2.0 degrees for s14a is the corner's angle alone; with the 5 mm half width it is 0.98.)"""
    r = math.hypot(*corner)
    return math.degrees(math.atan2(-corner[1], corner[0]) - math.asin(half_width / r))


# 1 (M-01, M-16): no tunnelling - a thin arm and a fast follower are caught, at the analytic first contact
@pytest.mark.parametrize('name, board, angle', [('s14a_tunnel_thin_arm', 'POST', first_touch((293, -10), 5)),
                                                ('s14b_tunnel_fast_driven', 'POST', first_touch((230, -103), 5))])
def test_a_collision_between_two_sampled_positions_is_found_at_its_first_contact(name, board, angle):
    hits = [x for x in diags(compiled(load(name)), 'MOTION_COLLISION') if board in x['components']]
    assert hits, name
    assert abs(contact(hits[0]['message']) - angle) <= 0.5, (angle, hits[0]['message'])


def test_the_control_post_is_still_caught_where_it_was():
    hit = diags(compiled(load('s14a_control_post_at_5deg')), 'MOTION_COLLISION')
    assert hit and "'POST' at 5°" in hit[0]['message']


# 13 (M-16): contact angle to 0.1 degree instead of the 5 degree step
def test_the_lid_meets_the_shelf_at_the_analytic_angle():
    hit = diags(compiled(load('s09_lid_hits_shelf')), 'MOTION_COLLISION')
    assert hit and abs(contact(hit[0]['message']) - math.degrees(math.atan2(87, 96))) <= 0.5, hit[0]['message']
    assert "at 45°" in hit[0]['message'] and 'only to 40°' in hit[0]['message']     # the round limit stays


# 2 (M-02): independent motions against each other's moving poses
def test_two_independent_arms_that_meet_when_both_open_are_reported():
    r = compiled(load('s14e_two_independent_arms_meet'))
    w = diags(r, 'MOTION_INTERFERENCE', 'warning')
    assert w and "'a'" in w[0]['message'] and "'b'" in w[0]['message'], [x['code'] for x in r['diagnostics']]
    assert re.search(r"'a' at -?[\d.]+° and 'b' at -?[\d.]+°", w[0]['message']), w[0]['message']
    assert set(w[0]['components']) == {'ARM-A', 'ARM-B'}


# 3 (M-03): a connecting rod fixed to static structure locks the mechanism
def test_a_rod_tabbed_to_a_static_post_locks_the_mechanism():
    r = compiled(load('s08b_rod_tabbed_to_static_post'))
    lock = diags(r, 'MOTION_LOCKED', 'error')
    assert lock and 'C2-POST-ROD' in lock[0]['message'] and "'ROD'" in lock[0]['message'], lock
    assert not [x for x in diags(r, 'MOTION_COLLISION') if set(x['components']) == {'ROD', 'POST'}]


# 4 (M-04): ratio sign in mirrored instances
FLIPS = [None, 'x', 'y', 'z', ['x', 'z'], ['x', 'y'], ['y', 'z'], ['x', 'y', 'z']]


def test_a_flipped_rack_and_pinion_runs_with_its_teeth_in_every_flip():
    d = load('s11i_flipped_rack_and_pinion')
    d['instances'] = [dict({'assembly': 'M', 'id': f'I{n}', 'offset': [500 * n, 0, 0]}, **({'flip': f} if f else {}))
                      for n, f in enumerate(FLIPS)]
    r = compiled(d)
    ms = r['design']['motions']
    by = {m['id']: m for m in ms}
    comps = {c['id']: c for c in r['design']['components']}
    R = 30.0                                                    # pinion pitch radius (20 teeth, module 3)
    for n, f in enumerate(FLIPS):
        p = by[f'I{n}-p']
        piv = p['pivot']
        # the pitch point: on the pinion's pitch circle, toward the rack
        k = 'xyz'.index(p['axis'])
        others = [i for i in range(3) if i != k]
        box = rack_box(comps[f'I{n}-RACK'])
        mid = [(box[0][i] + box[1][i]) / 2 for i in range(3)]
        far = max(others, key=lambda i: abs(mid[i] - piv[i]))
        point = list(piv)
        point[far] += math.copysign(R, mid[far] - piv[far])
        v = 1.0 if p['range'][1] > 0 else -1.0
        poses = board_poses(ms, train_values(ms, p['id'], v))
        rest = board_poses(ms, {})
        tooth = [a - b for a, b in zip(_at(poses[f'I{n}-PIN'][1], point), point)]
        rack = [a - b for a, b in zip(_at(poses[f'I{n}-RACK'][1], [0, 0, 0]), _at(rest[f'I{n}-RACK'][1], [0, 0, 0]))]
        d_rack = 'xyz'.index(by[f'I{n}-rk']['direction'])
        assert abs(rack[d_rack]) > 0.4 and tooth[d_rack] == pytest.approx(rack[d_rack], abs=0.05), (f, tooth, rack)


def rack_box(comp):
    from board_engine.model import Plate
    return Plate({'material': {'thickness': 6}}, comp).world_aabb()


# 5 (M-05): instanced gear pairs stay fast. The motion checks were > 9.5 min for 10 pairs; the rest of the compile
# (validate_design's per-outline self-intersection test of 20 gears, ~9 s) is outside the motion code.
@pytest.mark.parametrize('name', ['s14d_timing_4_gearpairs', 's14d_timing_10_gearpairs'])
def test_instanced_gear_pairs_compile_quickly(name, monkeypatch):
    from board_engine import motion
    spent = [0.0]
    for fn in ('check_gears', 'check_motions', 'check_cycles'):
        def timed(*a, _f=getattr(motion, fn), **k):
            t = time.time()
            try:
                return _f(*a, **k)
            finally:
                spent[0] += time.time() - t
        monkeypatch.setattr(motion, fn, timed)
    t = time.time()
    r = compiled(load(name))
    assert spent[0] < 5.0 and time.time() - t < 60.0, (spent[0], time.time() - t)
    assert not diags(r, 'COMPILE_TIMEOUT') and not diags(r, 'MOTION_COLLISION') and r['ok']


# 6 (M-06): rod pins are solids
def test_a_crank_pin_passing_through_the_other_rod_is_a_collision():
    r = compiled(load('s06_butterfly_two_rods'))
    hits = [x for x in diags(r, 'MOTION_COLLISION') if 'ROD-R' in x['components']
            and any(c.startswith('pin-') for c in x['components'])]
    assert hits, [x['message'] for x in r['diagnostics'] if x['code'].startswith('MOTION')]
    assert 180 <= abs(contact(hits[0]['message'])) <= 220, hits[0]['message']


# M-13: running clearance for rods
def test_a_rod_rubbing_over_a_post_needs_a_running_gap():
    r = compiled(load('s08c_same_without_post_joint'))
    tight = diags(r, 'MOTION_CLEARANCE')
    assert any(set(x['components']) == {'ROD', 'POST'} for x in tight), [x['code'] for x in r['diagnostics']]
    assert r['ok'], 'a rubbing rod in a mechanism is a warning (it was accepted before)'


# 7 (M-07): change points
def test_a_parallelogram_reports_its_change_points():
    r = compiled(load('s05c_parallelogram_change_point'))
    cp = diags(r, 'LINKAGE_CHANGE_POINT', 'warning')
    assert cp and '0°' in cp[0]['message'] and '180°' in cp[0]['message'], [x['message'] for x in cp]


def test_a_crank_rocker_has_no_change_point():
    from test_linkage import crank_design
    r, _errors = crank_design_compiled(crank_design('rocker'))
    assert not diags(r, 'LINKAGE_CHANGE_POINT')


def crank_design_compiled(d):
    r = compiled(d)
    return r, [x for x in r['diagnostics'] if x['severity'] == 'error']


# 8 (M-08): an explicit ratio between meshing gears must be the tooth ratio
def test_an_explicit_ratio_between_meshing_gears_must_match_the_teeth():
    r = compiled(load('s02f_gears_with_wrong_explicit_ratio'))
    bad = diags(r, 'GEAR_RATIO', 'error')
    assert bad and '-0.6667' in bad[0]['message'], [x['code'] for x in r['diagnostics']]
    d = load('s02f_gears_with_wrong_explicit_ratio')
    d['motions'][1]['ratio'] = -20 / 30
    assert not diags(compiled(d), 'GEAR_RATIO')


# 9 (M-09): pivot and guide hardware
def test_a_rotation_without_pivot_hardware_and_a_slide_without_a_guide_are_warned():
    r = compiled(load('s13_rotate_without_any_pivot_hardware'))
    assert diags(r, 'MOTION_NO_PIVOT', 'warning') and r['ok']
    r = compiled(load('s13b_slide_with_no_guide'))
    assert diags(r, 'MOTION_NO_GUIDE', 'warning') and r['ok']


def test_a_wheel_on_an_axle_stays_clean():
    r = compiled(load('s01_wheel_axis_x'))
    assert r['ok'] and not [x for x in r['diagnostics'] if x['severity'] in ('error', 'warning')]


def test_a_drawer_between_its_sides_is_guided_and_a_lifted_lid_needs_no_guide():
    from test_motion import CHEST, _drawer
    assert not diags(compiled(_drawer(2)), 'MOTION_NO_GUIDE')
    d = copy.deepcopy(CHEST)
    d['connections'] = [c for c in d['connections'] if c['type'] != 'hinge']
    d['motions'] = [{'id': 'lift', 'type': 'slide', 'boards': ['LID'], 'on': 'FRONT', 'direction': 'y', 'range': [0, 150]}]
    assert not diags(compiled(d), 'MOTION_NO_GUIDE')
    assert not diags(compiled(CHEST), 'MOTION_NO_PIVOT')            # the hinge is its pivot


# 10 (M-10): hinge reconciled with the motion; the hinge gap is allowed at the mount
def test_a_hinge_on_the_other_edge_than_the_pivot_is_reported():
    r = compiled(load('s11h_cabinet_door_hinge_on_right_pivot_on_left'))
    assert diags(r, 'MOTION_HINGE_MISMATCH'), [x['code'] for x in r['diagnostics']]


def test_a_door_hung_with_the_default_hinge_gap_is_mounted():
    r = compiled(load('s11f_cabinet_door_hinge_gap2_spec_default'))
    assert not [x for x in r['diagnostics'] if x['severity'] == 'error'], \
        [(x['code'], x['message']) for x in r['diagnostics'] if x['severity'] == 'error']
    assert not diags(r, 'MOTION_HINGE_MISMATCH')
    assert not diags(compiled(load('s11g_cabinet_door_hinge_ok')), 'MOTION_HINGE_MISMATCH')


# 11 (M-11): axle supports and retention
def test_an_axle_support_is_drilled_and_an_unretained_axle_is_warned():
    d = load('s12a_axle_two_supports')
    d['motions'][0]['axle']['supports'] = ['WALL-R']
    r = compiled(d)
    walls = {c['id']: [f for f in c.get('features') or [] if f['id'] == 'axle-spin'] for c in r['design']['components']}
    assert walls['WALL-R'] and walls['WALL-L'] and walls['WHEEL']
    assert diags(r, 'AXLE_UNRETAINED', 'warning')
    assert not diags(r, 'UNKNOWN_FIELD')
    d['motions'][0]['axle']['retain'] = 'collar'
    assert not diags(compiled(d), 'AXLE_UNRETAINED')
    assert not diags(compiled(load('s12a_axle_two_supports')), 'AXLE_UNRETAINED')    # no supports declared: as before


def test_an_axle_support_off_the_axle_line_is_an_error():
    d = load('s12a_axle_two_supports')
    d['motions'][0]['axle']['supports'] = ['BASE']
    assert diags(compiled(d), 'MOTION_AXLE', 'error')


# 12 (M-12): pressure angle
def test_gears_with_different_pressure_angles_do_not_mesh():
    bad = diags(compiled(load('s02g_gears_pressure_angle_mismatch')), 'GEAR_MESH', 'error')
    assert bad and 'pressure angles differ' in bad[0]['message']
    assert not diags(compiled(load('s02b_gears_ok_phased')), 'GEAR_MESH')


# M-14: undeclared meshes and several inputs
def test_an_undeclared_mesh_and_several_inputs_are_warned():
    r = compiled(load('s10e_undeclared_mesh_independent_input'))
    w = diags(r, 'MOTION_UNDECLARED_MESH', 'warning')
    assert w and "'G2'" in w[0]['message'] and "'G3'" in w[0]['message'] and 'driven_by' in w[0]['message']
    assert diags(compiled(load('s10f_two_independent_inputs')), 'MOTION_INPUTS', 'warning')
    assert not diags(compiled(load('s02b_gears_ok_phased')), 'MOTION_INPUTS')


# M-15: the loop is printed as a loop
def test_a_driver_loop_names_both_motions():
    msgs = [x['message'] for x in diags(compiled(load('s10c_driven_by_cycle')), 'MOTION_INVALID')]
    assert msgs and all('drive' in m and 'follow' in m for m in msgs), msgs
    assert not any('(drive -> drive)' in m or '(follow -> follow)' in m for m in msgs)


# M-17: the 3D view gets the reachable range of a jammed crank
def test_a_jammed_crank_is_animated_only_where_it_can_turn():
    r = compiled(load('s05b_non_grashof'))
    crank = next(m for m in r['model3d']['motions'] if m['id'] == 'crank')
    assert crank['jam_range'][1] < 111 and crank['jam_range'][0] <= 0 <= crank['jam_range'][1]
    assert crank['range'] == [0.0, 360.0]
    r = compiled(load('s05c_parallelogram_change_point'))
    assert 'jam_range' not in next(m for m in r['model3d']['motions'] if m['id'] == 'crank')
