"""Turning and flipping reused pieces: exact quarter turns and flips of instances, any-angle instance tilts,
mirrored tilted boards and motions carried by assemblies."""
import copy
import itertools
import json

import pytest

from board_engine import canvas
from board_engine.canvas_prompt import EXAMPLE
from board_engine.expand import _apply, transform_board
from board_engine.model import Plate, build_plates


@pytest.fixture(autouse=True)
def _no_snapshots(monkeypatch):
    monkeypatch.setattr(canvas, 'SNAPSHOT_DIR', None)


def table_assembly(instances):
    return {'format': 'board-design/v1', 'product': {'name': 'tables'}, 'material': EXAMPLE['material'],
            'assemblies': [{'id': 'table', 'boards': EXAMPLE['boards'], 'connections': EXAMPLE['connections']}],
            'instances': instances, 'boards': []}


def world_points(design, prefix):
    """Every outline / feature point of the boards of one instance, in world coordinates (sorted)."""
    out = []
    for c in design['components']:
        if not c['id'].startswith(prefix + '-'):
            continue
        pl = Plate(design, c)
        for poly in [pl.cut] + [p for _f, p in pl.feature_polys]:
            out += [tuple(round(v, 1) + 0.0 for v in pl.frame.to_world([q[0], q[1], 0.0])) for q in poly]
    return sorted(out)


def same(a, b, tol=0.15):
    return len(a) == len(b) and all(abs(x - y) <= tol for p, q in zip(a, b) for x, y in zip(p, q))


def moved(points, M, offset=(0, 0, 0)):
    return sorted(tuple(round(v + o, 1) + 0.0 for v, o in zip(_apply(M, list(p)), offset)) for p in points)


def compiled(d):
    """-> (result, errors); copies standing apart are separate structures, so DISCONNECTED is not an error here."""
    r = canvas.compile_source(json.dumps(d), run_production=False)
    return r, [x['message'] for x in r['diagnostics'] if x['severity'] == 'error' and x['code'] != 'DISCONNECTED']


@pytest.mark.parametrize('turn', [90, 180, 270])
def test_a_quarter_turned_instance_is_the_original_turned_with_every_joint(turn):
    M = {90: ((0, 0, 1), (0, 1, 0), (-1, 0, 0)), 180: ((-1, 0, 0), (0, 1, 0), (0, 0, -1)),
         270: ((0, 0, -1), (0, 1, 0), (1, 0, 0))}[turn]                       # about y, right-handed
    r, errors = compiled(table_assembly([{'assembly': 'table', 'id': 'A', 'offset': [0, 0, 0]},
                                         {'assembly': 'table', 'id': 'B', 'offset': [3000, 0, 0],
                                          'rotate': {'axis': 'y', 'angle': turn}}]))
    assert not errors, errors
    assert all(j['status'] == 'joined' for j in r['design']['joints']) and len(r['design']['joints']) == 2 * 13
    assert same(world_points(r['design'], 'B'), moved(world_points(r['design'], 'A'), M, (3000, 0, 0)))


def test_a_flipped_instance_is_the_mirror_image_and_still_joins():
    r, errors = compiled(table_assembly([{'assembly': 'table', 'id': 'A', 'offset': [0, 0, 0]},
                                         {'assembly': 'table', 'id': 'F', 'offset': [0, 0, 3000], 'flip': 'z'}]))
    assert not errors, errors
    assert all(j['status'] == 'joined' for j in r['design']['joints'])
    flip_z = ((1, 0, 0), (0, 1, 0), (0, 0, -1))
    assert same(world_points(r['design'], 'F'), moved(world_points(r['design'], 'A'), flip_z, (0, 0, 3000)))


def test_seats_all_round_a_ground_by_turning_one_assembly():
    seats = [{'assembly': 'table', 'id': f'S{k}', 'offset': off, 'rotate': {'axis': 'y', 'angle': 90 * k}}
             for k, off in enumerate([[0, 0, -2000], [-2000, 0, 0], [0, 0, 2000], [2000, 0, 0]])]
    r, errors = compiled(table_assembly(seats))
    assert not errors and len(r['design']['joints']) == 4 * 13
    assert all(j['status'] == 'joined' for j in r['design']['joints'])


def test_any_other_angle_tilts_the_whole_instance_about_its_origin():
    r, errors = compiled(table_assembly([{'assembly': 'table', 'id': 'T', 'offset': [500, 0, 500],
                                          'rotate': {'axis': 'y', 'angle': 30}}]))
    assert not errors, errors
    top = next(c for c in r['design']['components'] if c['id'] == 'T-TOP')
    assert top['placement']['rotation'] != [0.0, 0.0, 0.0] and all(j['status'] == 'joined' for j in r['design']['joints'])


def test_a_tilted_board_can_be_mirrored():
    d = {'format': 'board-design/v1', 'product': {'name': 'roof'}, 'material': {'type': 'plywood', 'thickness': 3, 'kerf': 0.15},
         'boards': [{'id': 'R', 'position': [100, 80, 100], 'size': [200, 3, 150],
                     'rotate': [{'axis': 'x', 'angle': 30, 'pivot': [100, 80, 250]}, {'axis': 'z', 'angle': 10}],
                     'mirror': {'axis': 'x', 'at': 400}}], 'connections': []}
    r, errors = compiled(d)
    assert not [e for e in errors if 'mirror' in e.lower()]
    plates = build_plates(r['design'])
    a, b = plates['R'].world_aabb(), plates['R-M'].world_aabb()
    assert b[0][0] == pytest.approx(800 - a[1][0], abs=0.01) and b[1][0] == pytest.approx(800 - a[0][0], abs=0.01)
    assert b[0][1:] == pytest.approx(a[0][1:], abs=0.01) and b[1][1:] == pytest.approx(a[1][1:], abs=0.01)


def test_an_assembly_carries_its_motion_into_every_turned_or_flipped_copy():
    spinner = {'id': 'spinner',
               'boards': [{'id': 'BASE', 'position': [0, 0, 0], 'size': [300, 6, 300]},
                          {'id': 'DISK', 'position': [50, 6, 50], 'size': [200, 6, 200],
                           'profile': {'shape': 'circle', 'center': [100, 100], 'diameter': 200}}],
               'connections': [],
               'motions': [{'id': 'spin', 'type': 'rotate', 'boards': ['DISK'], 'on': 'BASE', 'axis': 'y',
                            'pivot': [150, 6, 150], 'range': [0, 90], 'axle': {'diameter': 8}}]}
    d = {'format': 'board-design/v1', 'product': {'name': 'spinners'}, 'material': {'type': 'plywood', 'thickness': 6},
         'assemblies': [spinner], 'boards': [],
         'instances': [{'assembly': 'spinner', 'id': 'A', 'offset': [0, 0, 0]},
                       {'assembly': 'spinner', 'id': 'B', 'offset': [1000, 0, 0], 'rotate': {'axis': 'y', 'angle': 90}},
                       {'assembly': 'spinner', 'id': 'C', 'offset': [2000, 0, 0], 'flip': 'x'}]}
    r, errors = compiled(d)
    assert not errors, errors
    ms = {m['id']: m for m in r['model3d']['motions']}
    assert set(ms) == {'A-spin', 'B-spin', 'C-spin'} and ms['B-spin']['boards'] == ['B-DISK']
    assert ms['B-spin']['pivot'] == [1150.0, 6.0, -150.0]                 # (150, 150) turned 90 about y, then offset
    assert ms['C-spin']['range'] == [-90.0, 0.0]                          # a mirror image turns the other way
    holes = [c['id'] for c in r['design']['components'] if any(f['id'].startswith('axle-') for f in c.get('features', []))]
    assert sorted(holes) == ['A-BASE', 'A-DISK', 'B-BASE', 'B-DISK', 'C-BASE', 'C-DISK']


def test_turning_or_flipping_a_board_by_every_combination_is_exact():
    """All 48 combinations of quarter turns and flips, on a board with a profile, openings, an engraving and a decal."""
    b = {'id': 'B', 'position': [20, 30, 40], 'size': [160, 6, 90],
         'profile': {'shape': 'polygon', 'points': [[0, 0], [160, 0], [160, 60], [100, 90], [0, 90]]},
         'openings': [{'id': 'p', 'kind': 'opening', 'shape': 'regular_polygon', 'center': [80, 33, 60], 'sides': 5,
                       'diameter': 18}, {'id': 'r', 'kind': 'opening', 'shape': 'rect', 'center': [50, 33, 70],
                                         'size': [24, 14]}],
         'engravings': [{'id': 'e', 'kind': 'engrave', 'shape': 'polygon', 'points': [[10, 10], [40, 12], [25, 30]]}]}

    def geom(board):
        d = {'format': 'board-design/v1', 'product': {'name': 't'}, 'material': {'type': 'plywood', 'thickness': 6, 'kerf': 0.15},
             'boards': [board], 'connections': []}
        r = canvas.compile_source(json.dumps(d), run_production=False)
        c = r['design']['components'][0]
        pl = Plate(r['design'], c)
        polys = [pl.cut] + [p for _f, p in pl.feature_polys] + [m['points'] for m in c.get('marks', [])]
        return sorted(tuple(round(v, 1) + 0.0 for v in pl.frame.to_world([q[0], q[1], 0.0])) for poly in polys for q in poly)
    ref = geom(b)
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            M = tuple(tuple(signs[i] if perm[i] == j else 0 for j in range(3)) for i in range(3))
            assert same(geom(transform_board(b, M, 6)), moved(ref, M)), M


def test_the_prompt_teaches_turning_flipping_and_motions_in_assemblies():
    from board_engine.canvas_prompt import build_prompt
    p = build_prompt('Stadium', '', None, 3, 'interlocking', style='full')
    assert '"flip"' in p and 'multiples of 90° are exact' in p and 'copied into every instance' in p
    assert 'moved, not turned' not in p
