"""Compact authoring: generators that let a few lines describe what would otherwise take hundreds - spline,
superellipse and symmetric shapes, grid / graded repeats, radial copies and connections for many boards at once."""
import json
import math

import pytest

from board_engine import canvas
from board_engine import geometry as G
from board_engine.model import build_plates
from board_engine.shapes import ShapeError, shape_polygon

MAT = {'type': 'plywood', 'thickness': 6, 'kerf': 0.15}


@pytest.fixture(autouse=True)
def _no_snapshots(monkeypatch):
    monkeypatch.setattr(canvas, 'SNAPSHOT_DIR', None)


def compiled(boards, connections, **top):
    d = {'format': 'board-design/v1', 'product': {'name': 'g'}, 'material': MAT, 'boards': boards,
         'connections': connections, **top}
    r = canvas.compile_source(json.dumps(d), run_production=False)
    return r, [x for x in r['diagnostics'] if x['severity'] in ('error', 'warning')]


def test_a_spline_passes_through_its_points_and_stays_smooth():
    ctrl = [[0, 0], [50, 10], [100, 0], [90, 60], [50, 80], [10, 60]]
    pts, _arcs = shape_polygon({'shape': 'spline', 'points': ctrl})
    assert len(pts) > 6 * 4 and not G.self_intersections(pts)
    for c in ctrl:                                               # every control point lies on the curve
        assert min(math.dist(c, p) for p in pts) < 1e-6


def test_a_superellipse_matches_its_equation():
    pts, _ = shape_polygon({'shape': 'superellipse', 'center': [60, 40], 'width': 120, 'height': 80, 'exponent': 2.5, 'points': 24})
    assert [[round(v) for v in p] for p in pts[:7]] == [[120, 40], [118, 54], [113, 63], [105, 70], [94, 76], [80, 79], [60, 80]]
    with pytest.raises(ShapeError):
        shape_polygon({'shape': 'superellipse', 'center': [0, 0], 'width': 10, 'height': 10, 'exponent': 99})


def test_symmetric_halves_are_mirrored_without_doubling_the_axis_points():
    pts, _ = shape_polygon({'shape': 'polygon', 'points': [[50, 0], [100, 0], [100, 40], [70, 80], [50, 90]],
                            'symmetric': {'u': 50}})
    assert pts == [[50, 0], [100, 0], [100, 40], [70, 80], [50, 90], [30, 80], [0, 40], [0, 0]]
    half = shape_polygon({'shape': 'spline', 'points': [[0, 0], [40, 10], [60, 50], [0, 80]], 'symmetric': {'u': 0}})[0]
    assert min(p[0] for p in half) == pytest.approx(-max(p[0] for p in half), abs=1e-6)


def test_shaped_boards_compile_from_a_few_control_points():
    boards = [{'id': 'BASE', 'position': [0, 0, 0], 'size': [300, 6, 200]},
              {'id': 'LEAF', 'position': [50, 6, 97], 'size': [200, 150, 6],
               'profile': {'shape': 'spline', 'points': [[100, 0], [180, 0], [190, 60], [130, 140], [100, 150]],
                           'symmetric': {'u': 100}, 'corners': [0, 1, 7]}},      # a straight base to tab into BASE
              {'id': 'RIB', 'position': [130, 6, 20], 'size': [6, 80, 60],
               'profile': {'shape': 'superellipse', 'center': [40, 30], 'width': 80, 'height': 60, 'exponent': 3}}]
    r, problems = compiled(boards, [{'type': 'tab_slot', 'board': 'LEAF', 'into': 'BASE'}])
    assert 'LEAF' in {c['id'] for c in r['design']['components']}
    assert not [p for p in problems if p['code'] in ('PROFILE_INVALID', 'SHAPE_INVALID') or 'LEAF' in (p.get('board') or '')], problems


def test_radial_copies_are_exact_at_quarter_turns_and_tilted_between():
    boards = [{'id': 'BASE', 'position': [0, 0, 0], 'size': [400, 6, 400]},
              {'id': 'FIN', 'position': [240, 6, 197], 'size': [120, 80, 6], 'radial': {'count': 8, 'axis': 'y', 'center': [200, 6, 200]}}]
    r, problems = compiled(boards, [{'type': 'tab_slot', 'board': 'FIN-*', 'into': 'BASE'}])
    assert not problems, [p['message'] for p in problems]
    assert r['summary']['boards'] == 9 and r['summary']['joined'] == 8
    pl = build_plates(r['design'])
    lo, hi = pl['FIN-3'].world_aabb()                            # 90 deg about +y: x -> -z
    assert lo == pytest.approx([197, 0, 40], abs=0.01) and hi == pytest.approx([203, 86, 160], abs=0.01)
    assert next(c for c in r['design']['components'] if c['id'] == 'FIN-2')['placement']['rotation'] != [0.0, 0.0, 0.0]


def test_a_graded_grid_of_copies_from_one_board():
    boards = [{'id': 'BASE', 'position': [0, 0, 0], 'size': [600, 6, 300]},
              {'id': 'STEP', 'position': [20, 6, 20], 'size': [40, 100, 6],
               'repeat': {'count': 6, 'step': [60, 0, 0], 'grow': [0, -12, 0], 'rows': {'count': 3, 'step': [0, 0, 100]}}}]
    r, problems = compiled(boards, [{'type': 'tab_slot', 'board': 'STEP-*', 'into': 'BASE'}])
    assert not problems and r['summary']['boards'] == 19 and r['summary']['joined'] == 18
    sizes = {c['id']: build_plates(r['design'])[c['id']].world_aabb() for c in r['design']['components']}
    assert sizes['STEP-2-6'][1][1] - sizes['STEP-2-6'][0][1] == pytest.approx(100 - 5 * 12 + 6, abs=0.01)   # + tab depth


def test_many_boards_join_in_one_connection_line():
    boards = [{'id': 'BASE', 'position': [0, 0, 0], 'size': [300, 6, 100]}] + [
        {'id': f'P{k}', 'position': [20 + 60 * k, 6, 47], 'size': [20, 80, 6]} for k in range(4)]
    r, problems = compiled(boards, [{'id': 'posts', 'type': 'tab_slot', 'boards': ['P0', 'P1', 'P2', 'P3'], 'into': 'BASE'}])
    assert not problems and r['summary']['joined'] == 4
    r, problems = compiled(boards, [{'type': 'tab_slot', 'board': 'Q*', 'into': 'BASE'}])
    assert 'CONNECTION_INVALID' in [p['code'] for p in problems]


def test_generators_follow_an_assembly_instance_turned_a_quarter():
    asm = {'id': 'hub', 'boards': [{'id': 'PLATE', 'position': [0, 0, 0], 'size': [200, 6, 200]},
                                   {'id': 'FIN', 'position': [130, 6, 97], 'size': [60, 40, 6],
                                    'radial': {'count': 4, 'axis': 'y', 'center': [100, 6, 100]}}],
           'connections': [{'type': 'tab_slot', 'board': 'FIN', 'into': 'PLATE'}]}
    r, problems = compiled([], [], assemblies=[asm], instances=[{'assembly': 'hub', 'id': 'A', 'offset': [0, 0, 0]},
                                                               {'assembly': 'hub', 'id': 'B', 'offset': [500, 0, 0],
                                                                'rotate': {'axis': 'y', 'angle': 90}}])
    assert not [p for p in problems if p['code'] != 'DISCONNECTED'], [p['message'] for p in problems]
    assert r['summary']['boards'] == 10 and r['summary']['joined'] == 8


def test_the_prompt_teaches_compact_authoring():
    from board_engine.canvas_prompt import build_prompt, spec_markdown
    spec = spec_markdown()
    for word in ('"spline"', '"superellipse"', '"symmetric"', '"radial"', '"grow"', '"rows"', '"boards": [', 'SLAT-*'):
        assert word in spec, word
    assert 'COMPACT AUTHORING' in build_prompt('Anything')


def test_a_spline_never_leaves_the_bounds_of_its_points():
    ctrl = [[0, 0], [100, 0], [100, 100], [0, 100], [50, 50]]
    pts, _ = shape_polygon({'shape': 'spline', 'points': ctrl})
    assert all(0 <= p[0] <= 100 and 0 <= p[1] <= 100 for p in pts)


def test_a_mirrored_board_in_an_offset_instance_mirrors_about_the_moved_plane():
    from board_engine.expand import expand
    asm = {'id': 'a', 'boards': [{'id': 'S', 'position': [0, 0, 0], 'size': [6, 50, 50], 'mirror': {'axis': 'x', 'at': 50}}],
           'connections': []}
    d, _ = expand({'material': {'thickness': 6}, 'assemblies': [asm], 'boards': [],
                   'instances': [{'assembly': 'a', 'id': 'I', 'offset': [1000, 0, 0]}]})
    assert {b['id']: b['position'][0] for b in d['boards']} == {'I-S': 1000, 'I-S-M': 1094}


def test_spline_corners_keep_a_straight_edge_between_them():
    pts, _ = shape_polygon({'shape': 'spline', 'points': [[0, 0], [100, 0], [90, 60], [10, 60]], 'corners': [0, 1]})
    bottom = [p for p in pts if abs(p[1]) < 1e-9]
    assert [0, 0] in bottom and [100, 0] in bottom and all(p[1] >= -1e-9 for p in pts)


def _hull(**extra):
    """Ribs of a hull: one board, a section at each end and one in the middle - the compiler draws the rest."""
    rib = lambda h, w: {'shape': 'polygon', 'points': [[0, w // 4], [0, w - w // 4], [h, w], [h, 0]]}   # [u = y, v = z]
    return {'id': 'RIB', 'position': [0, 6, 0], 'size': [6, 40, 60], 'profile': rib(40, 60),
            'repeat': {'count': 9, 'step': [40, 0, 0],
                       'morph': [{'size': [6, 80, 140], 'profile': rib(80, 140), 'shift': [0, 0, -40]},
                                 {'size': [6, 30, 40], 'profile': rib(30, 40), 'shift': [0, 0, 10]}]}, **extra}


def test_morph_draws_every_section_between_a_few_keys():
    from board_engine.expand import expand
    d, _ = expand({'material': {'thickness': 6}, 'boards': [_hull()]})
    ribs = {b['id']: b for b in d['boards']}
    assert list(ribs) == [f'RIB-{k}' for k in range(1, 10)]
    assert ribs['RIB-1']['size'] == [6, 40, 60] and ribs['RIB-5']['size'] == [6, 80, 140] and ribs['RIB-9']['size'] == [6, 30, 40]
    assert ribs['RIB-5']['position'] == [160, 6, -40] and ribs['RIB-5']['profile']['points'][1] == [0, 105]
    depth = [ribs[f'RIB-{k}']['size'][2] for k in range(1, 10)]
    assert depth[0] < depth[1] < depth[2] < depth[3] < depth[4] > depth[5] > depth[6] > depth[7] > depth[8]   # a smooth swell
    assert all(isinstance(v, int) for b in ribs.values() for v in b['size'] + b['position'] + sum(b['profile']['points'], []))
    assert all(max(p[1] for p in b['profile']['points']) == b['size'][2] for b in ribs.values())   # each fits its board


def test_morphed_ribs_compile_and_join_a_keel_in_one_line():
    keel = {'id': 'KEEL', 'position': [-20, 0, -60], 'size': [380, 6, 180]}
    r, problems = compiled([keel, _hull()], [{'type': 'tab_slot', 'board': 'RIB-*', 'into': 'KEEL'}])
    assert not [p for p in problems if p['severity'] == 'error'], [p['message'] for p in problems]
    assert r['summary']['boards'] == 10 and r['summary']['joined'] == 9


def test_morph_rejects_sections_of_different_shape():
    from board_engine.expand import ExpandError, expand
    b = _hull()
    b['repeat']['morph'][0]['profile'] = {'shape': 'polygon', 'points': [[0, 0], [140, 0], [70, 80]]}
    with pytest.raises(ExpandError, match='differ in shape'):
        expand({'material': {'thickness': 6}, 'boards': [b]})
    b = _hull()
    b['repeat']['morph'][0]['rotate'] = {'axis': 'x', 'angle': 5}
    with pytest.raises(ExpandError, match='not'):
        expand({'material': {'thickness': 6}, 'boards': [b]})


def test_morphed_ribs_follow_an_instance_turned_and_a_mirror():
    from board_engine.expand import expand
    asm = {'id': 'h', 'boards': [_hull()], 'connections': []}
    d, _ = expand({'material': {'thickness': 6}, 'assemblies': [asm], 'boards': [],
                   'instances': [{'assembly': 'h', 'id': 'A', 'offset': [0, 0, 0]},
                                 {'assembly': 'h', 'id': 'B', 'offset': [1000, 0, 0], 'rotate': {'axis': 'y', 'angle': 180}}]})
    pl = {b['id']: b for b in d['boards']}
    for k in range(1, 10):                       # B is A turned half round y about its origin, then moved +1000 in x
        a, b = pl[f'A-RIB-{k}'], pl[f'B-RIB-{k}']
        assert b['size'] == a['size']
        assert b['position'] == [1000 - a['position'][0] - 6, a['position'][1], -a['position'][2] - a['size'][2]]
    d, _ = expand({'material': {'thickness': 6}, 'boards': [_hull(mirror={'axis': 'x', 'at': -10})]})
    pl = {b['id']: b for b in d['boards']}
    for k in range(1, 10):
        a, m = pl[f'RIB-{k}'], pl[f'RIB-M-{k}']
        assert m['size'] == a['size'] and m['position'] == [-20 - a['position'][0] - 6] + a['position'][1:]


def test_a_mirrored_row_runs_away_from_the_mirror():
    from board_engine.expand import expand
    d, _ = expand({'material': {'thickness': 6}, 'boards': [
        {'id': 'S', 'position': [10, 0, 0], 'size': [6, 50, 50], 'repeat': {'count': 3, 'step': [20, 0, 0]}, 'mirror': {'axis': 'x', 'at': 0}}]})
    assert sorted(b['position'][0] for b in d['boards']) == [-56, -36, -16, 10, 30, 50]


def test_the_spec_morph_example_compiles_as_written():
    from board_engine.canvas_prompt import build_prompt, spec_markdown
    spec = spec_markdown()
    block = spec[spec.index('{"id": "RIB"'):]
    rib = json.loads(block[:block.index('\n  ```')])
    assert rib['repeat'] == _hull()['repeat'] and rib['profile'] == _hull()['profile']
    assert '"board": "RIB-*", "into": "KEEL"' in spec and '"morph"' in build_prompt('Anything')
