"""Geometry-only structural engineering: weak webs, what really holds each part (locked / lifts off / friction /
falls out), and how hard a crank works through a linkage's cycle."""
import copy
import json

import pytest

from board_engine import canvas
from board_engine.canvas_prompt import EXAMPLE
from board_engine.model import build_plates
from board_engine.structure import narrowest_web


@pytest.fixture(autouse=True)
def _no_snapshots(monkeypatch):
    monkeypatch.setattr(canvas, 'SNAPSHOT_DIR', None)


def compiled(d):
    return canvas.compile_source(json.dumps(d), run_production=False)


def plate(board, t=6):
    d = {'format': 'board-design/v1', 'product': {'name': 'p'}, 'material': {'type': 'plywood', 'thickness': t, 'kerf': 0.15},
         'boards': [board], 'connections': []}
    r = compiled(d)
    return r, build_plates(r['design'])[board['id']]


def codes(r, code):
    return [x for x in r['diagnostics'] if x['code'] == code]


def test_a_dumbbell_waist_narrower_than_the_board_is_a_weak_section():
    pts = [[0, 0], [60, 0], [60, 27], [100, 27], [100, 0], [160, 0], [160, 60], [100, 60], [100, 31], [60, 31], [60, 60], [0, 60]]
    r, pl = plate({'id': 'BONE', 'position': [0, 0, 0], 'size': [160, 60, 6], 'profile': {'shape': 'polygon', 'points': pts}})
    w = codes(r, 'WEAK_SECTION')
    assert w and w[0]['severity'] == 'warning' and '4.0 mm' in w[0]['message']
    assert narrowest_web(pl, 6)[0] == pytest.approx(4.0, abs=0.2)     # (the kerf moves the edges a little)


def test_a_hole_close_to_the_edge_leaves_a_weak_bridge_but_a_wide_one_does_not():
    board = lambda y: {'id': 'P', 'position': [0, 0, 0], 'size': [200, 100, 6],
                       'openings': [{'id': 'w', 'kind': 'opening', 'shape': 'rect', 'center': [100, y, 3], 'size': [80, 40]}]}
    assert codes(plate(board(76))[0], 'WEAK_SECTION')          # 100 - 96 = 4 mm left above the opening
    assert not codes(plate(board(70))[0], 'WEAK_SECTION')      # 10 mm


def test_pointed_tips_and_a_thick_board_are_not_weak():
    tooth = {'id': 'TOOTH', 'position': [0, 0, 0], 'size': [20, 60, 6],
             'profile': {'shape': 'polygon', 'points': [[0, 0], [20, 0], [10, 60]]}}
    assert not codes(plate(tooth)[0], 'WEAK_SECTION')
    gear = {'id': 'G', 'position': [0, 0, 0], 'size': [66, 66, 6], 'profile': {'shape': 'gear', 'center': [33, 33], 'teeth': 20, 'module': 3}}
    assert not codes(plate(gear)[0], 'WEAK_SECTION')


def test_the_example_table_is_locked_except_its_top_which_lifts_off():
    r = compiled(EXAMPLE)
    s = r['structure']
    assert s['checked'] and s['lifts_off'] == ['TOP'] and set(s['locked']) == {'LEG-L', 'LEG-R', 'MODESTY', 'SHELF'}
    assert not s['held_by_friction'] and not s['can_fall_out']


def test_a_part_held_only_from_above_can_fall_out():
    d = {'format': 'board-design/v1', 'product': {'name': 'sign'}, 'material': {'type': 'plywood', 'thickness': 18},
         'boards': [{'id': 'LEG-A', 'position': [0, 0, 0], 'size': [18, 400, 200]},
                    {'id': 'LEG-B', 'position': [482, 0, 0], 'size': [18, 400, 200]},
                    {'id': 'BEAM', 'position': [0, 400, 0], 'size': [500, 18, 200]},
                    {'id': 'SIGN', 'position': [200, 250, 91], 'size': [100, 150, 18]}],     # hangs from the beam
         'connections': [{'type': 'tab_slot', 'board': b, 'into': 'BEAM'} for b in ('LEG-A', 'LEG-B', 'SIGN')]}
    r = compiled(d)
    fall = codes(r, 'PART_CAN_FALL_OUT')
    assert [x['components'] for x in fall] == [['SIGN']] and '-y' in fall[0]['message']
    assert r['structure']['can_fall_out'] == ['SIGN']


def test_sides_held_only_by_tabs_going_into_them_are_held_by_friction():
    from test_canvas import bookshelf
    d = bookshelf()
    d['connections'] = [c for c in d['connections'] if c['board'] != 'BACK']      # no back panel to lock the sides
    d['boards'] = [b for b in d['boards'] if b['id'] != 'BACK']
    r = compiled(d)
    held = {x['components'][0] for x in codes(r, 'PART_HELD_BY_FRICTION')}
    assert held == set() or held <= {'SIDE-L', 'SIDE-R'}
    assert all(x['severity'] == 'info' for x in codes(r, 'PART_HELD_BY_FRICTION'))


def test_moving_parts_are_not_judged_for_retention():
    from test_linkage import crank_design
    r = compiled(crank_design('rocker'))
    assert not {'CRANK', 'ARM', 'ROD'} & {c for x in codes(r, 'PART_HELD_BY_FRICTION') for c in x['components']}


def test_the_crank_reports_its_drive_profile():
    from test_linkage import crank_design
    r = compiled(crank_design('slider'))
    drive = codes(r, 'LINKAGE_DRIVE')
    assert drive and drive[0]['severity'] == 'info' and 'turns back at' in drive[0]['message']
    peak = float(drive[0]['message'].split('x ')[1].split(' mm')[0])
    assert peak == pytest.approx(20.0, abs=1.5)                  # ~ the crank radius where the rod is square to it
