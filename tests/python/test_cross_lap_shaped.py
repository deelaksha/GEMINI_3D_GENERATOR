"""cross_lap between shaped boards (audit 2026-11-28, phase 7): two silhouettes halved where they cross (a tree), and a
board slotted through another (a wing through a fuselage) - the standard flat-pack joints for organic objects."""
import json

from board_engine.canvas import compile_source
from board_engine.canvas_prompt import STRUCTURES_EXAMPLE

BASE = {'id': 'BASE', 'position': [-30, 0, -30], 'size': [160, 6, 160]}


def design(boards, connections):
    return json.dumps({'format': 'board-design/v1', 'product': {'name': 't'}, 'material': {'type': 'plywood', 'thickness': 6},
                       'boards': boards, 'connections': connections})


def errors(r):
    return [(d['code'], d['message'][:160]) for d in r['diagnostics'] if d['severity'] == 'error']


TREE = [[0, 0], [100, 0], [100, 10], [70, 10], [95, 60], [65, 60], [85, 110], [50, 150], [15, 110], [35, 60], [5, 60],
        [30, 10], [0, 10]]


def test_two_crossed_tree_silhouettes_are_halved_and_slot_together():
    a = {'id': 'TREE-A', 'position': [0, 6, 47], 'size': [100, 150, 6], 'profile': {'shape': 'polygon', 'points': TREE}}
    b = {'id': 'TREE-B', 'position': [47, 6, 0], 'size': [6, 150, 100],
         'profile': {'shape': 'polygon', 'points': [[y, x] for x, y in TREE]}}           # thin x: face = (y, z)
    r = compile_source(design([BASE, a, b], [{'id': 'X', 'type': 'cross_lap', 'board': 'TREE-A', 'into': 'TREE-B'},
                                             {'type': 'tab_slot', 'board': 'TREE-A', 'into': 'BASE'},
                                             {'type': 'tab_slot', 'board': 'TREE-B', 'into': 'BASE'}]), run_production=False)
    assert not errors(r), errors(r)
    joint = next(j for j in r['design']['joints'] if j['id'] == 'X')
    assert joint['type'] == 'cross_lap' and joint['status'] == 'joined'
    assert not any(d['code'] == 'COLLISION' for d in r['diagnostics'])


def test_a_wing_slots_through_a_profiled_fuselage():
    fus = {'id': 'FUS', 'position': [0, 6, 47], 'size': [300, 60, 6],
           'profile': {'shape': 'spline', 'points': [[0, 30], [40, 50], [150, 60], [280, 45], [300, 30], [280, 18], [150, 0],
                                                     [40, 8]], 'corners': [6]}}
    wing = {'id': 'WING', 'position': [110, 30, -100], 'size': [80, 6, 206],
            'profile': {'shape': 'polygon', 'points': [[0, 30], [80, 0], [80, 206], [0, 176]]}}    # tapered, swept tips
    r = compile_source(design([fus, wing], [{'id': 'W', 'type': 'cross_lap', 'board': 'WING', 'into': 'FUS'}]),
                       run_production=False)
    errs = [e for e in errors(r) if e[0] not in ('NOT_JOINED', 'UNSUPPORTED_COMPONENT', 'DISCONNECTED')]
    assert not errs, errs
    fuselage = next(c for c in r['design']['components'] if c['id'] == 'FUS')
    assert any(f['kind'] == 'slot' and f['id'].startswith('xlap-') for f in fuselage['features'])
    assert not any(d['code'] == 'COLLISION' for d in r['diagnostics'])
    assert next(j for j in r['design']['joints'] if j['id'] == 'W')['status'] == 'joined'


def test_plain_cross_laps_are_unchanged():
    r = compile_source(json.dumps(STRUCTURES_EXAMPLE), run_production=False)
    assert r['ok'] and sum(j['type'] == 'cross_lap' for j in r['design']['joints']) == 2


def test_finger_joints_still_need_plain_boards():
    a = {'id': 'A', 'position': [0, 6, 0], 'size': [100, 50, 6], 'profile': {'shape': 'rect', 'center': [50, 25],
                                                                           'width': 100, 'height': 50, 'corner_radius': 5}}
    r = compile_source(design([BASE, a], [{'type': 'finger', 'board': 'A', 'into': 'BASE'}]), run_production=False)
    assert any(c == 'JOINT_NEEDS_PLAIN_BOARD' for c, _m in errors(r))


def test_face_lap_laminates_two_parallel_boards_with_glue():
    body = {'id': 'BODY', 'position': [0, 0, 0], 'size': [200, 6, 100]}
    neck = {'id': 'NECK', 'position': [150, 6, 40], 'size': [150, 6, 20]}
    src = lambda joinery: json.dumps({'format': 'board-design/v1', 'product': {'name': 'guitar'}, 'joinery': joinery,
                                      'material': {'type': 'plywood', 'thickness': 6}, 'boards': [body, neck],
                                      'connections': [{'id': 'NB', 'type': 'laminate', 'board': 'NECK', 'into': 'BODY'}]})
    r = compile_source(src('glue_allowed'), run_production=False)
    assert not errors(r), errors(r)
    assert next(j for j in r['design']['joints'] if j['id'] == 'NB')['type'] == 'face_lap'
    assert any(c == 'GLUE_JOINT_IN_INTERLOCKING' for c, _m in errors(compile_source(src('interlocking'), run_production=False)))
