"""Gears: the involute "gear" shape, gear trains ("driven_by"), the mesh checks and turned / flipped gears."""
import copy
import json
import math

import pytest

from board_engine import canvas
from board_engine import geometry as G
from board_engine.expand import quarter_turn, transform_board
from board_engine.shapes import gear_geometry, shape_polygon


@pytest.fixture(autouse=True)
def _no_snapshots(monkeypatch):
    monkeypatch.setattr(canvas, 'SNAPSHOT_DIR', None)


def gear_board(bid, z, m, centre, rot=0.0):
    ra = m * z / 2 + m
    return {'id': bid, 'position': [centre[0] - ra, 6, centre[1] - ra], 'size': [2 * ra, 6, 2 * ra],
            'profile': {'shape': 'gear', 'center': [ra, ra], 'teeth': z, 'module': m, 'rotation': rot}}


def motion(mid, board, centre, driver=None):
    mo = {'id': mid, 'type': 'rotate', 'boards': [board], 'on': 'BASE', 'axis': 'y', 'pivot': [centre[0], 6, centre[1]],
          'axle': {'diameter': 6}}
    return dict(mo, driven_by=driver) if driver else dict(mo, range=[0, 360])


def train(gears, links):
    """gears: [(id, teeth, centre, rotation)]; links: {driven id: driver id} (motion ids are 'm-' + board id)."""
    return {'format': 'board-design/v1', 'product': {'name': 'gears'},
            'material': {'type': 'plywood', 'thickness': 6, 'kerf': 0.15},
            'boards': [{'id': 'BASE', 'position': [-200, 0, -200], 'size': [600, 6, 600]}]
                      + [gear_board(g, z, 3, c, r) for g, z, c, r in gears],
            'connections': [],
            'motions': [motion('m-' + g, g, c, ('m-' + links[g]) if g in links else None) for g, _z, c, _r in gears]}


def compiled(d):
    r = canvas.compile_source(json.dumps(d), run_production=False)
    return r, {x['code'] for x in r['diagnostics'] if x['severity'] == 'error'}


def need_rotation(za, zb, a_rot, beta_deg):
    beta, fa = math.radians(beta_deg), math.radians(a_rot)
    return math.degrees(beta + math.pi - (math.pi - za * (beta - fa)) / zb)


def test_the_gear_shape_is_a_proper_involute_outline():
    pts, _ = shape_polygon({'shape': 'gear', 'center': [0, 0], 'teeth': 24, 'module': 3})
    g = gear_geometry(24, 3)
    radii = [math.hypot(*p) for p in pts]
    assert min(radii) == pytest.approx(g['root']) and max(radii) == pytest.approx(g['tip'])
    assert G.signed_area(pts) > 0
    peaks = sum(1 for i in range(len(radii)) if radii[i] >= g['tip'] - 1e-6 and radii[i - 1] < g['tip'] - 1e-6)
    assert peaks == 24                                                     # one tip land per tooth


def test_a_meshing_pair_compiles_clean_and_turns_at_the_tooth_ratio():
    r, errors = compiled(train([('G1', 20, [80, 100], 0), ('G2', 30, [155, 100], need_rotation(20, 30, 0, 0))],
                               {'G2': 'G1'}))
    assert not errors, errors
    follow = next(m for m in r['model3d']['motions'] if m['id'] == 'm-G2')
    assert follow['driven_by'] == 'm-G1' and follow['ratio'] == pytest.approx(-20 / 30)
    assert follow['range'] == pytest.approx([-240, 0])


@pytest.mark.parametrize('za, zb, a_rot, beta', [(20, 30, 0, 0), (12, 40, 7, 37), (25, 25, -4, 135), (16, 21, 11, -100)])
def test_teeth_interleave_at_the_computed_rotation_and_clash_half_a_tooth_off(za, zb, a_rot, beta):
    d = 3 * (za + zb) / 2
    cb = [d * math.cos(math.radians(beta)), d * math.sin(math.radians(beta))]
    good = need_rotation(za, zb, a_rot, beta)
    _r, errors = compiled(train([('A', za, [0, 0], a_rot), ('B', zb, cb, good)], {'B': 'A'}))
    assert not errors & {'COLLISION', 'GEAR_PHASE', 'GEAR_MESH'}, errors
    r, errors = compiled(train([('A', za, [0, 0], a_rot), ('B', zb, cb, good + 180 / zb)], {'B': 'A'}))
    assert {'COLLISION', 'GEAR_PHASE'} <= errors                          # the clash is real, and explained
    fix = next(f for x in r['diagnostics'] if x['code'] == 'GEAR_PHASE' for f in x['fixes'])
    rot = fix['edits'][0]['value']['rotation']
    assert ((rot - good) / (360 / zb)) % 1 == pytest.approx(0, abs=1e-3) or ((rot - good) / (360 / zb)) % 1 == pytest.approx(1, abs=1e-3)


def test_wrong_spacing_is_reported_with_the_move_that_fixes_it():
    r, errors = compiled(train([('G1', 20, [80, 100], 0), ('G2', 30, [160, 100], 6)], {'G2': 'G1'}))
    mesh = next(x for x in r['diagnostics'] if x['code'] == 'GEAR_MESH')
    assert 'must be 75 mm apart' in mesh['message'] and mesh['fixes'][0]['edits'][0]['value'] == [107.0, 6.0, 52.0]


def test_a_chain_of_three_gears_multiplies_the_ratios():
    r1 = need_rotation(20, 30, 0, 0)
    r2 = need_rotation(30, 15, r1, 0)
    r, errors = compiled(train([('G1', 20, [0, 0], 0), ('G2', 30, [75, 0], r1), ('G3', 15, [142.5, 0], r2)],
                               {'G2': 'G1', 'G3': 'G2'}))
    assert not errors, errors
    ms = {m['id']: m for m in r['model3d']['motions']}
    assert ms['m-G3']['ratio'] == pytest.approx(-2.0) and ms['m-G3']['range'] == pytest.approx([0, 480])


def test_driver_loops_and_missing_ratios_are_explained():
    d = train([('G1', 20, [0, 0], 0), ('G2', 30, [75, 0], 6)], {'G2': 'G1'})
    d['motions'][0] = dict(d['motions'][0], driven_by='m-G2')
    d['motions'][0].pop('range')
    msgs = [x['message'] for x in compiled(d)[0]['diagnostics'] if x['code'] == 'MOTION_INVALID']
    assert any('loop' in m for m in msgs)
    d = train([('G1', 20, [0, 0], 0)], {})
    d['boards'].append({'id': 'WHEEL', 'position': [150, 6, -40], 'size': [80, 6, 80]})
    d['motions'].append({'id': 'w', 'type': 'rotate', 'boards': ['WHEEL'], 'on': 'BASE', 'axis': 'y',
                         'pivot': [190, 6, 0], 'driven_by': 'm-G1'})
    msgs = [x['message'] for x in compiled(d)[0]['diagnostics'] if x['code'] == 'MOTION_INVALID']
    assert any('give a "ratio"' in m for m in msgs)


def test_a_turned_or_flipped_gear_stays_a_gear_exactly_where_the_turn_puts_it():
    from board_engine.expand import _apply
    from board_engine.model import Plate

    def outline(board):
        d = {'format': 'board-design/v1', 'product': {'name': 't'},
             'material': {'type': 'plywood', 'thickness': 6, 'kerf': 0.15}, 'boards': [board], 'connections': []}
        r = canvas.compile_source(json.dumps(d), run_production=False)
        pl = Plate(r['design'], r['design']['components'][0])
        return sorted(tuple(round(v, 1) + 0.0 for v in pl.frame.to_world([q[0], q[1], 0.0])) for q in pl.cut)
    b = gear_board('G', 20, 3, [80, 100], 15)
    ref = outline(b)
    for M in (quarter_turn('y', 90), quarter_turn('x', 180), ((1, 0, 0), (0, 1, 0), (0, 0, -1))):
        t = transform_board(b, M, 6)
        assert t['profile']['shape'] == 'gear' and t['profile']['teeth'] == 20      # still a gear: its mesh is checked
        want = sorted(tuple(round(v, 1) + 0.0 for v in _apply(M, list(q))) for q in ref)
        got = outline(t)
        assert len(got) == len(want) and all(abs(x - y) <= 0.15 for p, q in zip(got, want) for x, y in zip(p, q))


def test_the_gear_example_in_the_prompt_compiles_clean():
    from board_engine.canvas_prompt import spec_markdown
    spec = spec_markdown()
    block = spec[spec.index('## Gears'):]
    block = block[block.index('```jsonc') + 8:block.index('```', block.index('```jsonc') + 8)]
    boards_txt, motions_txt = block.split('"motions":')
    boards = json.loads('[' + boards_txt.strip().rstrip(',') + ']')
    motions = json.loads(motions_txt.strip())
    d = {'format': 'board-design/v1', 'product': {'name': 'gears'}, 'material': {'type': 'plywood', 'thickness': 6, 'kerf': 0.15},
         'boards': [{'id': 'BASE', 'position': [0, 0, 0], 'size': [300, 6, 200]}] + boards, 'connections': [],
         'motions': motions}
    r, errors = compiled(d)
    assert not errors, errors
    assert {m['id'] for m in r['model3d']['motions']} == {'drive', 'follow'}
