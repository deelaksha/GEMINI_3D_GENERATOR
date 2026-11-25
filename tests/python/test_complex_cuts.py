"""Complex cuts: shape library, polygon / rounded cut-outs, engrave & pocket marks, true arcs in SVG / DXF,
and the AI canvas's profiles, shaped openings, engravings and tilted (rotated) boards."""
import copy
import json
import math
import re

import pytest

from board_engine import geometry as G
from board_engine.canvas import apply_code_fix, compile_source
from board_engine.canvas_prompt import COMPLEX_EXAMPLE
from board_engine.cutpaths import generate_cut_paths, path_segments
from board_engine.model import normalize_design
from board_engine.nesting import nest
from board_engine.shapes import FLATTEN_TOL, ShapeError, shape_polygon
from board_engine.validation import validate_design
from board_engine.views import export, model3d, production_package


def _runs(arc, n):
    return [(arc['start'] + k) % n for k in range((arc['end'] - arc['start']) % n + 1)]


@pytest.mark.parametrize('spec', [
    {'shape': 'rect', 'center': [0, 0], 'width': 100, 'height': 60, 'corner_radius': 10},
    {'shape': 'circle', 'center': [5, 5], 'diameter': 40},
    {'shape': 'arch', 'center': [0, 0], 'width': 60, 'height': 100},
    {'shape': 'polygon', 'points': [[0, 0], [100, 0], [100, 50], [50, 50], [50, 100], [0, 100]], 'corner_radius': 8},
    {'shape': 'path', 'start': [0, 0], 'segments': [{'line': [100, 0]}, {'line': [100, 40]},
                                                     {'arc': {'to': [0, 40], 'radius': 60}}]},
])
def test_shapes_are_simple_polygons_whose_arcs_stay_within_cutting_accuracy(spec):
    pts, arcs = shape_polygon(spec)
    assert not G.self_intersections(pts)
    for a in arcs:
        idx = _runs(a, len(pts))
        assert all(abs(math.dist(pts[i], a['center']) - a['radius']) < 1e-9 for i in idx)
        for i, j in zip(idx, idx[1:]):              # chord error (sagitta) of every flattened segment
            mid = [(pts[i][0] + pts[j][0]) / 2, (pts[i][1] + pts[j][1]) / 2]
            assert a['radius'] - math.dist(mid, a['center']) <= FLATTEN_TOL + 1e-9


def test_rounded_rectangle_area_matches_the_exact_value():
    pts, _ = shape_polygon({'shape': 'rect', 'center': [0, 0], 'width': 100, 'height': 60, 'corner_radius': 10})
    exact = 100 * 60 - (4 - math.pi) * 10 ** 2
    assert abs(G.signed_area(pts) - exact) < 0.01 * exact


@pytest.mark.parametrize('spec, msg', [
    ({'shape': 'arch', 'center': [0, 0], 'width': 60, 'height': 10}, 'height >= width / 2'),
    ({'shape': 'path', 'start': [0, 0], 'segments': [{'arc': {'to': [10, 0], 'radius': 2}}]}, 'smaller than half the chord'),
    ({'shape': 'blob'}, 'must be one of'),
    ({'shape': 'regular_polygon', 'center': [0, 0], 'sides': 2, 'diameter': 5}, 'sides'),
])
def test_impossible_shapes_are_rejected_with_a_reason(spec, msg):
    with pytest.raises(ShapeError, match=re.escape(msg)):
        shape_polygon(spec)


# ---------------------------------------------------------------------------
# Engine: an arched panel with a heart, a hexagon, a rounded window and marks
# ---------------------------------------------------------------------------

def _panel_design(**over):
    out, arcs = shape_polygon({'shape': 'arch', 'center': [0, 0], 'width': 200, 'height': 300})
    heart, harcs = shape_polygon({'shape': 'path', 'start': [0, 30], 'segments': [
        {'line': [30, 60]}, {'arc': {'to': [0, 80], 'radius': 19, 'large': True}},
        {'arc': {'to': [-30, 60], 'radius': 19, 'large': True}}]})
    comp = {'id': 'PANEL', 'outline': out, 'arcs': arcs,
            'features': [{'id': 'HEART', 'kind': 'opening', 'shape': 'polygon', 'points': heart, 'arcs': harcs},
                         {'id': 'HEX', 'kind': 'hole', 'shape': 'polygon',
                          'points': shape_polygon({'shape': 'regular_polygon', 'center': [0, -90], 'sides': 6, 'diameter': 40})[0]},
                         {'id': 'WIN', 'kind': 'opening', 'shape': 'rect', 'center': [0, -20], 'width': 80, 'height': 40,
                          'corner_radius': 8}],
            'marks': [{'id': 'NAME', 'kind': 'engrave', 'points': [[-60, -130], [60, -130]], 'depth': 0.5},
                      {'id': 'POCKET', 'kind': 'pocket', 'points': [[-30, 100], [-10, 100], [-10, 120], [-30, 120]], 'depth': 2}],
            'placement': {'position': [0, 0, 0], 'rotation': [0, 0, 0]}}
    comp.update(over)
    return normalize_design({'id': 'arch', 'name': 'Arch panel', 'material': {'name': 'Ply 6', 'type': 'plywood', 'thickness': 6, 'kerf': 0.2},
                             'components': [comp], 'joints': []})


def test_curved_panel_with_shaped_cutouts_and_marks_is_valid():
    rep = validate_design(_panel_design())
    assert rep['valid'], [i for i in rep['issues'] if i['severity'] != 'info']


@pytest.mark.parametrize('over, code', [
    ({'features': [{'id': 'BOW', 'kind': 'hole', 'shape': 'polygon', 'points': [[-20, 0], [20, 40], [20, 0], [-20, 40]]}],
      'marks': []}, 'FEATURE_SELF_INTERSECTION'),
    ({'marks': [{'id': 'OUT', 'kind': 'engrave', 'points': [[-60, 0], [400, 0]]}]}, 'MARK_OUTSIDE_BOARD'),
    ({'marks': [{'id': 'DEEP', 'kind': 'pocket', 'points': [[-30, 100], [-10, 100], [-10, 120]], 'depth': 4}]}, 'POCKET_TOO_DEEP'),
    ({'marks': [{'id': 'DEEP', 'kind': 'engrave', 'points': [[-60, -130], [60, -130]], 'depth': 4}]}, 'ENGRAVE_TOO_DEEP'),
])
def test_bad_cutouts_and_marks_are_errors(over, code):
    codes = {i['code'] for i in validate_design(_panel_design(**over))['issues'] if i['severity'] == 'error'}
    assert code in codes


def test_marks_are_machined_before_inner_cuts_and_the_outer_profile():
    d = _panel_design()
    cut = generate_cut_paths(d, nest(d, {}), compensate_kerf=True)
    order = [p['type'] for p in sorted(cut['sheets'][0]['paths'], key=lambda p: p['order'])]
    assert order == ['engrave', 'pocket', 'inner', 'inner', 'inner', 'outer']
    assert cut['counts'] == {'outer': 1, 'inner': 3, 'marks': 2} and cut['issues'] == []


def _svg_centre(p0, p1, r, large, sweep):
    """Centre of an SVG arc from its end points and flags (SVG 1.1 implementation notes, F.6.5)."""
    mx, my = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    k = math.sqrt(max(r * r - mx * mx - my * my, 0) / (mx * mx + my * my))
    if large == sweep:
        k = -k
    return [k * (my) + (p0[0] + p1[0]) / 2, k * (-mx) + (p0[1] + p1[1]) / 2]


def test_svg_arcs_are_true_arcs_with_correct_flags():
    d = _panel_design()
    pkg = production_package(d, {'compensate_kerf': False})
    paths = [p for p in pkg['cut']['sheets'][0]['paths'] if p.get('arcs')]
    assert {p.get('feature') for p in paths} == {'HEART', 'WIN', None}
    svg = export(pkg, 'svg', 0)
    svg = (svg[0] if isinstance(svg, tuple) else svg)
    svg = svg if isinstance(svg, str) else svg.decode()
    for p in paths:
        start, segs = path_segments(p['points'], p['arcs'])
        cur = start
        for sg in segs:
            if sg[0] == 'A':
                c = _svg_centre(cur, sg[1], sg[3], abs(sg[4]) > math.pi, sg[4] > 0)
                assert math.dist(c, sg[2]) < 1e-3, (p['id'], c, sg[2])
            cur = sg[1]
    assert len(re.findall(r' A[0-9.]+,', svg)) == 9          # heart 2 x 2 halves, window 4, arch top 1


def test_dxf_bulges_reproduce_the_arc_centres():
    d = _panel_design()
    pkg = production_package(d, {'compensate_kerf': False})
    dxf = export(pkg, 'dxf', 0)
    dxf = dxf[0] if isinstance(dxf, tuple) else dxf
    lines = (dxf if isinstance(dxf, str) else dxf.decode()).split('\n')
    pairs = list(zip(lines[0::2], lines[1::2]))
    H = pkg['nesting']['sheet']['height']
    arcs_world = [[a['center'][0], H - a['center'][1]] for p in pkg['cut']['sheets'][0]['paths'] for a in p.get('arcs', [])]
    checked, i = 0, 0
    while i < len(pairs):
        if pairs[i] == ('0', 'POLYLINE'):
            verts, i = [], i + 1
            while pairs[i] != ('0', 'SEQEND'):
                if pairs[i] == ('0', 'VERTEX'):
                    v = {'b': 0.0}
                    verts.append(v)
                elif verts and pairs[i][0] in ('10', '20', '42'):
                    verts[-1][{'10': 'x', '20': 'y', '42': 'b'}[pairs[i][0]]] = float(pairs[i][1])
                i += 1
            for k, v in enumerate(verts):
                if v['b']:
                    w = verts[(k + 1) % len(verts)]
                    sweep = 4 * math.atan(v['b'])
                    chord = math.dist((v['x'], v['y']), (w['x'], w['y']))
                    r = chord / (2 * math.sin(abs(sweep) / 2))
                    mx, my = (v['x'] + w['x']) / 2, (v['y'] + w['y']) / 2
                    h = r * math.cos(abs(sweep) / 2) * (1 if sweep > 0 else -1)
                    ux, uy = -(w['y'] - v['y']) / chord, (w['x'] - v['x']) / chord   # left normal of the chord
                    c = [mx + ux * h, my + uy * h] if abs(sweep) < math.pi else [mx, my]
                    assert min(math.dist(c, a) for a in arcs_world) < 1e-3
                    checked += 1
        i += 1
    assert checked == 9


def test_3d_view_carries_polygons_and_marks():
    c = model3d(_panel_design())['components'][0]
    assert sum(1 for f in c['features'] if 'polygon' in f) == 3 and len(c['marks']) == 2


# ---------------------------------------------------------------------------
# AI canvas: profiles, shaped openings, engravings, tilted roof
# ---------------------------------------------------------------------------

def _src(mutate=None):
    d = copy.deepcopy(COMPLEX_EXAMPLE)
    if mutate:
        mutate(d)
    return json.dumps(d, indent=2)


def _board(d, bid):
    return next(b for b in d['boards'] if b['id'] == bid)


def test_complex_example_compiles_clean_and_ready_for_production():
    r = compile_source(_src())
    assert r['ok'] and r['summary']['errors'] == 0 and r['summary']['warnings'] == 0, r['diagnostics']
    assert r['summary']['joined'] == r['summary']['joints'] == 12
    assert r['layout']['ready_for_production']
    comps = {c['id']: c for c in r['design']['components']}
    assert comps['FLOOR'].get('arcs') and len(comps['GABLE-B']['outline']) == 5
    assert sum(1 for f in comps['ROOF-L']['features'] if f['kind'] == 'slot') == 2      # one slot per gable
    assert {f['shape'] for f in comps['GABLE-F']['features']} >= {'polygon', 'circle'}
    assert [m['kind'] for m in comps['SIDE-R']['marks']] == ['pocket']


def test_tilted_roof_gap_is_reported_and_the_safe_fix_moves_the_roof():
    src = _src(lambda d: _board(d, 'ROOF-L')['position'].__setitem__(1, 157))
    r = compile_source(src, run_production=False)
    errs = [x for x in r['diagnostics'] if x['severity'] == 'error']
    # 1 mm lift; the example's whole-millimetre roof seats within 0.02 mm of exact (inside the contact tolerance)
    assert {x['code'] for x in errs} == {'CONNECTION_GAP'} and abs(errs[0]['gap'] - 1.0) < 0.05
    fix = errs[0]['fixes'][0]
    assert fix['safe'] and fix['edits'][0]['board'] == 'ROOF-L'
    fixed = compile_source(apply_code_fix(src, fix), run_production=False)
    assert fixed['ok'] and fixed['summary']['joined'] == 12


@pytest.mark.parametrize('mutate, code', [
    (lambda d: _board(d, 'ROOF-L')['rotate'].__setitem__('angle', 36), 'NO_CONTACT'),
    (lambda d: _board(d, 'ROOF-L').__setitem__('rotate', {'axis': 'q', 'angle': 3}), 'BOARD_ROTATE'),
    (lambda d: _board(d, 'GABLE-B')['profile']['points'].__setitem__(3, [100, 260]), 'PROFILE_INVALID'),
    (lambda d: _board(d, 'GABLE-B')['openings'][0]['segments'][1]['arc'].__setitem__('radius', 2), 'OPENING_INVALID'),
    (lambda d: _board(d, 'GABLE-F')['engravings'][0].__setitem__('points', [[60, 135], [260, 135]]), 'MARK_OUTSIDE_BOARD'),
    (lambda d: _board(d, 'SIDE-R')['engravings'][0].__setitem__('depth', 6), 'POCKET_TOO_DEEP'),
    (lambda d: _board(d, 'SIDE-R')['engravings'][0].__setitem__('kind', 'paint'), 'ENGRAVING_INVALID'),
])
def test_complex_cut_mistakes_are_compile_errors(mutate, code):
    r = compile_source(_src(mutate), run_production=False)
    assert code in {x['code'] for x in r['diagnostics'] if x['severity'] == 'error'}


def test_profile_without_a_straight_edge_on_the_contact_side_is_explained():
    def arch_wall(d):     # side wall (normal x: u = y, v = z) whose profile stops 20 mm short of its -z side
        _board(d, 'SIDE-L')['profile'] = {'shape': 'polygon', 'points': [[0, 20], [150, 20], [150, 148], [0, 148]]}
        d['connections'] = [c for c in d['connections'] if c['board'] != 'SIDE-L' or c['into'] == 'FLOOR']
        d['connections'].append({'id': 'sl-gb-x', 'type': 'tab_slot', 'board': 'SIDE-L', 'into': 'GABLE-B', 'edge': '-z'})
    r = compile_source(_src(arch_wall), run_production=False)
    errs = [x for x in r['diagnostics'] if x['severity'] == 'error']
    assert errs and errs[0]['code'] == 'CONTACT_TOO_SHORT' and 'no straight edge' in errs[0]['message']


# ---------------------------------------------------------------------------
# Whole-app consistency: every part, every output, the prompt and the agent API stay in sync
# ---------------------------------------------------------------------------

# Every field the board-design/v1 compiler (and shapes.py) reads. If the compiler learns a new field, add it here:
# the test then fails until the AI prompt documents it.
COMPILER_FIELDS = """format product name description overall length height depth material type thickness kerf clearance
joinery sheet width boards connections id group position size grain normal openings edge_banding edge profile
engravings rotate axis angle pivot kind shape center diameter corner_radius note points closed sides rotation start
segments line arc to radius large clockwise into into_edge tabs tab_width tab_depth fasteners count gap bevel fingers auto_connect
mounting""".split()


def test_ai_prompt_documents_every_field_the_compiler_accepts():
    from board_engine.canvas_prompt import build_prompt, spec_markdown
    spec = spec_markdown()
    missing = [k for k in COMPILER_FIELDS if not re.search(r'["`]' + k + r'["`]', spec)]
    assert not missing, f'document these fields in canvas_prompt.spec_markdown(): {missing}'
    prompt = build_prompt('Bird house')
    assert spec in prompt and 'rotate' in prompt and 'profile' in prompt


def test_agent_api_schema_matches_the_engine():
    from board_api.contract import COMPONENT, FEATURE, MARK
    from board_engine.model import FEATURE_KINDS, FEATURE_SHAPES, MARK_KINDS
    assert FEATURE['properties']['shape']['enum'] == list(FEATURE_SHAPES)
    assert FEATURE['properties']['kind']['enum'] == list(FEATURE_KINDS)
    assert MARK['properties']['kind']['enum'] == list(MARK_KINDS)
    assert {'arcs', 'marks', 'features', 'outline'} <= set(COMPONENT['properties'])


def test_editing_api_handles_arcs_and_marks():
    from board_engine.operations import apply_operation
    d = _panel_design()
    res = apply_operation(d, {'op': 'update_component', 'id': 'PANEL', 'patch': {
        'marks': [{'id': 'LOGO', 'kind': 'engrave', 'points': [[-20, -100], [20, -100]], 'depth': 0.4}]}})
    assert [m['id'] for m in res['component']['marks']] == ['LOGO'] and res['component'].get('arcs')
    # a new straight outline must not keep arc runs that index the old curved outline
    res = apply_operation(d, {'op': 'update_component', 'id': 'PANEL', 'patch': {
        'outline': [[-100, -150], [100, -150], [100, 150], [-100, 150]]}})
    assert 'arcs' not in res['component']
    res = apply_operation(d, {'op': 'add_feature', 'id': 'PANEL', 'component_id': 'PANEL', 'feature': {
        'id': 'TRI', 'kind': 'hole', 'shape': 'polygon', 'points': [[60, -60], [80, -60], [70, -45]]}})   # clear of the heart and window
    assert validate_design(d)['valid']


def test_every_part_of_the_complex_example_goes_through_every_output():
    from board_engine.cutlist import cut_list
    from board_engine.joining import check_joint
    r = compile_source(_src())
    d = r['design']
    # every tab really fits its slot (tilted roof joints included): gap and penetration within tolerance
    for j in d['joints']:
        res = check_joint(d, {k: v for k, v in j.items() if k in ('id', 'type', 'a', 'tab', 'b', 'slot', 'a_edge')})
        assert res['ok'], (j['id'], res['issues'])
    pkg = production_package(d, {'compensate_kerf': True})
    ids = {c['id'] for c in d['components']}
    placed = {p['id'] for p in pkg['nesting']['placements']}
    assert placed == ids and pkg['cut']['issues'] == []
    outers = {p['part'] for s in pkg['cut']['sheets'] for p in s['paths'] if p['type'] == 'outer'}
    assert outers == ids
    for i in range(pkg['nesting']['sheet_count']):
        for fmt in ('svg', 'dxf'):
            body = export(pkg, fmt, i)[0]
            assert all(cid in body for cid in placed if any(p['sheet'] == i and p['id'] == cid for p in pkg['nesting']['placements']))
    assert export(pkg, 'pdf')[0][:5] == b'%PDF-'
    boards = {b['id']: b for b in cut_list(d)['boards']}
    assert set(boards) == ids
    assert boards['FLOOR']['operations']['curves'] and boards['SIDE-R']['operations']['surface']
    assert all(boards[c]['process'] == 'cnc' for c in ('FLOOR', 'GABLE-F', 'SIDE-R'))
    view = {c['id']: c for c in model3d(d)['components']}
    assert set(view) == ids and view['GABLE-F']['marks'] and all('polygon' in f for f in view['GABLE-B']['features'])
