"""Validation correctness (audit 2026-11-28, phase 2): missed collisions, consolidation that hid errors, the assembly
plan in the compile result, connectivity from the real solids, tabs hanging off a shaped receiver, and inspection
warnings on generated copies. Fixture designs come from the audit's reproduction cases (tests/python/fixtures/geom)."""
import json
import os

import pytest

from board_engine.canvas import compile_source

FIX = os.path.join(os.path.dirname(__file__), 'fixtures', 'geom')


def load(name):
    with open(os.path.join(FIX, name + '.json')) as f:
        return f.read()


def codes(src, production=False):
    r = compile_source(src, run_production=production)
    return r, [(d['severity'], d['code']) for d in r['diagnostics']]


# 2.1 (F-05): collisions missed at shallow tilt angles and for narrow parallel overlaps ------------------------------

@pytest.mark.parametrize('case', ['C6_tilted_thin_sliver', 'C6b_shallow_tilt_3mm_penetration',
                                  'C6c_tilt_10deg_3mm_penetration', 'C6d_tilt_30deg_3mm_penetration'])
def test_tilted_boards_sinking_into_a_board_collide(case):
    assert ('error', 'COLLISION') in codes(load(case))[1]


@pytest.mark.parametrize('width', [5, 10, 15, 25])
def test_narrow_overlap_strips_of_large_parallel_boards_collide(width):
    r, cs = codes(load(f'C8_large_parallel_strip_{width}mm'))
    hit = [d for d in r['diagnostics'] if d['code'] == 'COLLISION']
    assert hit, cs
    assert f'({2400 * width:.1f} mm²)' in hit[0]['message']      # the exact shared area: 2400 mm long x the strip


@pytest.mark.parametrize('case', ['C1_rotated_parallel_aabb_overlap_no_solid', 'C4b_disc_perp_corner'])
def test_boxes_that_overlap_without_the_solids_do_not_collide(case):
    assert ('error', 'COLLISION') not in codes(load(case))[1]


# 2.2 (F-13): consolidation never merges across groups or moving joints, and reports redundant duplicates --------------

def _merged_pairs(r):
    return [set(g['from']) for g in (r.get('consolidation') or {}).get('groups', [])]


def test_boards_of_different_groups_are_not_merged():
    r, _ = codes(load('cons_A_diff_groups_butt'))
    assert not any({'MOD-A', 'MOD-B'} <= g for g in _merged_pairs(r))


def test_boards_joined_by_a_hinge_are_not_merged_and_the_hinge_stays():
    r, _ = codes(load('cons_B_hinge_between'))
    assert not any({'MOD-A', 'MOD-B'} <= g for g in _merged_pairs(r))
    # the hinge is not swallowed by a merge: it is checked (and here rejected for its own reasons) like any joint
    assert any(d['code'] == 'HINGE_EDGE' for d in r['diagnostics'])


def test_overlapping_pieces_of_one_panel_still_merge():
    """Drawing a panel from overlapping coplanar pieces (posts crossed by rails) is an authoring style: one board."""
    r, cs = codes(load('K1_coplanar_overlap_consolidated'))
    assert any({'WALL', 'WALL2'} <= g for g in _merged_pairs(r)) and ('warning', 'REDUNDANT_BOARD') not in cs


def test_a_duplicate_board_inside_another_is_reported():
    r, cs = codes(load('J16_two_walls_same_place_same_side'))
    hit = [d['message'] for d in r['diagnostics'] if d['code'] == 'REDUNDANT_BOARD']
    assert hit and 'WALL2' in hit[0] and 'WALL' in hit[0]


# 2.3 (F-17): the assembly plan reaches the compile result, and a locked assembly fails the compile ---------------------

def test_compile_result_carries_the_assembly_plan():
    from board_engine.canvas_prompt import EXAMPLE
    r = compile_source(json.dumps(EXAMPLE), run_production=True)
    plan = r['manufacturing']['assembly_plan']
    assert plan and plan[0]['steps'] and set(plan[0]['boards']) == {'TOP', 'LEG-L', 'LEG-R', 'MODESTY', 'SHELF'}


def test_a_locked_assembly_is_an_error_of_the_compile(monkeypatch):
    from board_engine import manufacturing
    from board_engine.canvas_prompt import EXAMPLE
    from board_engine.validation import issue
    locked = issue('ASSEMBLY_LOCKED', 'error', 'assembly', "Boards LEG-L, TOP lock each other.", ['LEG-L', 'TOP'])
    monkeypatch.setattr(manufacturing, 'plan_assembly', lambda *a, **kw: ([], [locked]))
    r = compile_source(json.dumps(EXAMPLE) + ' ', run_production=True)       # (a new source: no cached fast pass)
    assert not r['ok'] and ('error', 'ASSEMBLY_LOCKED') in [(d['severity'], d['code']) for d in r['diagnostics']]


# 2.4 (F-18): "touches" means the solids touch, not their bounding boxes ---------------------------------------------

@pytest.mark.parametrize('case', ['C2_board_in_L_notch', 'C4a_discs_coplanar_corner_boxes'])
def test_boards_whose_boxes_meet_but_solids_do_not_are_not_called_touching(case):
    r, cs = codes(load(case))
    assert not [d for d in r['diagnostics'] if d['code'] == 'NOT_JOINED'], cs
    assert {'ISOLATED_BOARD', 'DISCONNECTED'} & {c for _s, c in cs}


def test_boards_that_really_touch_are_still_not_joined_errors():
    from board_engine.canvas_prompt import EXAMPLE
    d = json.loads(json.dumps(EXAMPLE))
    d['connections'] = [c for c in d['connections'] if c['board'] != 'SHELF']      # the shelf still touches both legs
    d['auto_connect'] = False
    r, cs = codes(json.dumps(d))
    assert ('error', 'NOT_JOINED') in cs or ('error', 'UNATTACHED_BOARD') in cs or ('error', 'UNSUPPORTED_COMPONENT') in cs


# 2.5 (F-23): a joining edge hanging off a shaped receiver is reported ----------------------------------------------

def test_a_joining_edge_that_overhangs_a_round_receiver_is_warned_about():
    r, cs = codes(load('J07c_wall_edge_partly_off_disc_1tab'))
    hit = [d for d in r['diagnostics'] if d['code'] == 'TAB_EDGE_OVERHANG']
    assert hit and 30 <= hit[0]['overhang'] <= 90


def test_a_wall_well_inside_a_round_receiver_is_not_warned_about():
    d = json.loads(load('J07c_wall_edge_partly_off_disc_1tab'))
    d['boards'][1]['position'] = [50, 6, 97]
    d['boards'][1]['size'] = [100, 80, 6]
    assert 'TAB_EDGE_OVERHANG' not in {c for _s, c in codes(json.dumps(d))[1]}


# 2.5 (F-15): copies made by morph / radial are not "almost twins"; an offset of exactly 5 mm is deliberate -------------

def _base(l, h, d):
    return {'format': 'board-design/v1', 'product': {'name': 't', 'overall': {'length': l, 'height': h, 'depth': d}},
            'material': {'type': 'plywood', 'thickness': 6}}


def test_radial_copies_raise_no_alignment_warnings():
    hub = {'id': 'HUB', 'position': [100, 0, 100], 'size': [100, 6, 100]}
    blade = {'id': 'BL', 'position': [147, 6, 160], 'size': [6, 60, 35], 'radial': {'count': 4, 'axis': 'y', 'center': [150, 6, 150]}}
    d = dict(_base(100, 66, 100), boards=[hub, blade], connections=[{'type': 'tab_slot', 'board': 'BL-*', 'into': 'HUB'}])
    r, cs = codes(json.dumps(d))
    assert r['ok'] and not [c for s, c in cs if s == 'warning']


def test_morph_ribs_are_not_reported_as_mismatched_twins():
    rib = {'id': 'RIB', 'position': [0, 6, 0], 'size': [6, 40, 60],
           'profile': {'shape': 'polygon', 'points': [[0, 15], [0, 45], [40, 60], [40, 0]]},
           'repeat': {'count': 9, 'step': [40, 0, 0], 'morph': [
               {'size': [6, 80, 140], 'profile': {'shape': 'polygon', 'points': [[0, 35], [0, 105], [80, 140], [80, 0]]}, 'shift': [0, 0, -40]},
               {'size': [6, 30, 40], 'profile': {'shape': 'polygon', 'points': [[0, 10], [0, 30], [30, 40], [30, 0]]}, 'shift': [0, 0, 10]}]}}
    keel = {'id': 'KEEL', 'position': [-20, 0, -20], 'size': [380, 6, 120]}
    d = dict(_base(380, 86, 140), boards=[keel, rib], connections=[{'type': 'tab_slot', 'board': 'RIB-*', 'into': 'KEEL'}])
    assert 'MISMATCHED_PAIR' not in {c for _s, c in codes(json.dumps(d))[1]}


def test_an_edge_offset_of_exactly_5_mm_is_deliberate():
    from board_engine.canvas_prompt import EXAMPLE
    d = json.loads(json.dumps(EXAMPLE))
    d['boards'][1]['position'][0] = 55          # LEG-L 5 mm in from TOP's edge (was 50)
    d['boards'][4]['position'][0] = 73          # keep the shelf against it
    d['boards'][4]['size'][0] = 1059
    d['boards'][3]['position'][0] = 73
    d['boards'][3]['size'][0] = 1059
    r, cs = codes(json.dumps(d))
    assert not [x for x in r['diagnostics'] if x['code'] == 'MISALIGNED' and '5.0 mm' in x['message']]
