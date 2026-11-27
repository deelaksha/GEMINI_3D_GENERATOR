"""Compound tilts: "rotate" as a list of steps (flared roof corners, hip pieces) - geometry, joints, compatibility."""
import copy
import json
import math

import pytest

from board_engine import canvas
from board_engine import geometry as G
from board_engine.model import build_plates


@pytest.fixture(autouse=True)
def _no_snapshots(monkeypatch):
    monkeypatch.setattr(canvas, 'SNAPSHOT_DIR', None)


def _rot(axis, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return {'x': [[1, 0, 0], [0, c, -s], [0, s, c]], 'y': [[c, 0, s], [0, 1, 0], [-s, 0, c]],
            'z': [[c, -s, 0], [s, c, 0], [0, 0, 1]]}[axis]


def design(rotate, extra=()):
    return {'format': 'board-design/v1', 'product': {'name': 'flare'},
            'material': {'type': 'plywood', 'thickness': 3, 'kerf': 0.15},
            'boards': [{'id': 'BASE', 'position': [0, 0, 0], 'size': [400, 3, 400]},
                       {'id': 'P', 'position': [100, 80, 100], 'size': [200, 3, 150], 'rotate': rotate}, *extra],
            'connections': []}


def test_a_compound_tilt_turns_the_board_by_each_step_in_order():
    steps = [{'axis': 'x', 'angle': 30}, {'axis': 'z', 'angle': 12}]
    r = canvas.compile_source(json.dumps(design(steps)), run_production=False)
    p = build_plates(r['design'])['P']
    centre = [200, 81.5, 175]
    R = G.mat_mul(_rot('z', 12), _rot('x', 30))                       # x first, then z (world axes)
    want = []
    for x in (100, 300):
        for z in (100, 250):
            for y in (80, 83):
                rel = [x - centre[0], y - centre[1], z - centre[2]]
                want.append([centre[i] + sum(R[i][k] * rel[k] for k in range(3)) for i in range(3)])
    lo = [min(q[i] for q in want) for i in range(3)]
    hi = [max(q[i] for q in want) for i in range(3)]
    got = p.world_aabb()
    assert got[0] == pytest.approx(lo, abs=0.01) and got[1] == pytest.approx(hi, abs=0.01)


def test_one_step_in_a_list_is_exactly_the_single_tilt():
    single = canvas.compile_source(json.dumps(design({'axis': 'x', 'angle': 28, 'pivot': [100, 80, 250]})), run_production=False)
    listed = canvas.compile_source(json.dumps(design([{'axis': 'x', 'angle': 28, 'pivot': [100, 80, 250]}])), run_production=False)
    pick = lambda r: next(c for c in r['design']['components'] if c['id'] == 'P')['placement']
    assert pick(single) == pick(listed)


def test_a_piece_with_the_same_compound_tilt_stands_on_the_panel_and_joins():
    steps = [{'axis': 'x', 'angle': 30, 'pivot': [100, 80, 250]}, {'axis': 'z', 'angle': 10, 'pivot': [100, 80, 250]}]
    tile = {'id': 'TILE', 'position': [150, 83, 160], 'size': [60, 12, 3], 'rotate': copy.deepcopy(steps)}
    d = design(steps, [tile])
    d['connections'] = [{'type': 'tab_slot', 'board': 'TILE', 'into': 'P'}]
    r = canvas.compile_source(json.dumps(d), run_production=False)
    j = [x for x in r['design']['joints'] if {x['a'], x['b']} == {'TILE', 'P'}]
    assert j and j[0]['status'] == 'joined', [x['message'] for x in r['diagnostics'] if x['severity'] == 'error']


@pytest.mark.parametrize('bad', [[], [{'axis': 'x', 'angle': 10}] * 5, [{'axis': 'q', 'angle': 10}], [{'axis': 'x'}]])
def test_a_malformed_compound_tilt_is_explained(bad):
    r = canvas.compile_source(json.dumps(design(bad)), run_production=False)
    assert 'BOARD_ROTATE' in [x['code'] for x in r['diagnostics'] if x['severity'] == 'error']


def test_the_move_fix_closes_a_gap_under_a_compound_tilt():
    """Both steps turn about a fixed pivot, so the suggested move must be undone through both of them, last first."""
    steps = [{'axis': 'x', 'angle': 30, 'pivot': [100, 80, 250]}, {'axis': 'z', 'angle': 10, 'pivot': [100, 80, 250]}]
    tile = {'id': 'TILE', 'position': [150, 85, 160], 'size': [40, 4, 3], 'rotate': copy.deepcopy(steps)}  # 2 mm off
    d = design(steps, [tile])
    d['connections'] = [{'type': 'tab_slot', 'board': 'TILE', 'into': 'P'}]
    r = canvas.compile_source(json.dumps(d), run_production=False)
    fix = next(f for x in r['diagnostics'] if x['code'] == 'CONNECTION_GAP' for f in x.get('fixes') or [] if f['id'] == 'move-TILE')
    next(b for b in d['boards'] if b['id'] == 'TILE')['position'] = fix['edits'][0]['value']
    r = canvas.compile_source(json.dumps(d), run_production=False)
    assert [j['status'] for j in r['design']['joints'] if {j['a'], j['b']} == {'TILE', 'P'}] == ['joined']
