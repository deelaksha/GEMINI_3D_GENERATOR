"""Mechanisms driven from one crank: connecting rods (four-bar rocker, slider-crank) solved over the whole cycle,
jams, pins, nested motions riding on moving parts, collisions part-way through the cycle, storage and the 3D model."""
import copy
import json
import math

import pytest

from board_engine import canvas
from board_engine.model import normalize_design
from board_engine.motion import board_poses, train_values


@pytest.fixture(autouse=True)
def _no_snapshots(monkeypatch):
    monkeypatch.setattr(canvas, 'SNAPSHOT_DIR', None)


def bar(bid, p, q, z, w=16.0, t=6.0):
    """A straight bar board (thin along z) with rounded-off ends past the pin points p and q."""
    d = [q[0] - p[0], q[1] - p[1]]
    n = math.hypot(*d)
    d = [d[0] / n, d[1] / n]
    o = [-d[1] * w / 2, d[0] * w / 2]
    pts = [[p[0] - 10 * d[0] + s * o[0], p[1] - 10 * d[1] + s * o[1]] for s in (1, -1)]
    pts = [pts[0], [q[0] + 10 * d[0] + o[0], q[1] + 10 * d[1] + o[1]], [q[0] + 10 * d[0] - o[0], q[1] + 10 * d[1] - o[1]], pts[1]]
    lo = [math.floor(min(x[0] for x in pts)) - 1, math.floor(min(x[1] for x in pts)) - 1]
    hi = [math.ceil(max(x[0] for x in pts)) + 1, math.ceil(max(x[1] for x in pts)) + 1]
    return {'id': bid, 'position': [lo[0], lo[1], z], 'size': [hi[0] - lo[0], hi[1] - lo[1], t],
            'profile': {'shape': 'polygon', 'points': [[x[0] - lo[0], x[1] - lo[1]] for x in reversed(pts)]}}


def crank_design(follower, crank_pin=(120, 150), disk=60, extra=()):
    """A back plate (thin along z), a crank disk turning on it about z and a follower pushed through a rod."""
    c = (100, 150)
    boards = [{'id': 'BASE', 'position': [0, 0, 0], 'size': [420, 320, 6]},
              {'id': 'CRANK', 'position': [c[0] - disk / 2, c[1] - disk / 2, 6], 'size': [disk, disk, 6],
               'profile': {'shape': 'circle', 'center': [disk / 2, disk / 2], 'diameter': disk}}]
    motions = [{'id': 'crank', 'type': 'rotate', 'boards': ['CRANK'], 'on': 'BASE', 'axis': 'z', 'pivot': [100, 150, 6],
                'range': [0, 360], 'axle': {'diameter': 6}}]
    if follower == 'rocker':
        to = (300, 220)
        boards.append({'id': 'ARM', 'position': [290, 140, 6], 'size': [20, 90, 6]})
        motions.append({'id': 'rocker', 'type': 'rotate', 'boards': ['ARM'], 'on': 'BASE', 'axis': 'z',
                        'pivot': [300, 150, 6], 'driven_by': 'crank', 'axle': {'diameter': 6}})
    else:
        to = (270, 150)
        boards.append({'id': 'SLIDER', 'position': [250, 140, 6], 'size': [40, 20, 6]})
        motions.append({'id': 'slider', 'type': 'slide', 'boards': ['SLIDER'], 'on': 'BASE', 'direction': 'x',
                        'driven_by': 'crank'})
    boards.append(bar('ROD', crank_pin, to, 12))
    motions[1]['link'] = {'rod': 'ROD', 'from': [crank_pin[0], crank_pin[1], 12], 'to': [to[0], to[1], 12]}
    return {'format': 'board-design/v1', 'product': {'name': 'linkage'},
            'material': {'type': 'plywood', 'thickness': 6, 'kerf': 0.15}, 'boards': boards + list(extra),
            'connections': [], 'motions': motions}


def compiled(d):
    r = canvas.compile_source(json.dumps(d), run_production=False)
    return r, [x for x in r['diagnostics'] if x['severity'] == 'error']


def link_of(r, mid):
    return next(m for m in r['design']['motions'] if m['id'] == mid)


def test_a_crank_rocker_is_solved_exactly_over_the_whole_turn():
    r, errors = compiled(crank_design('rocker'))
    assert not errors, [e['message'] for e in errors]
    m = link_of(r, 'rocker')
    table = m['link']['table']
    assert table[0][0] == 0 and table[-1][0] == 360 and len(table) > 100
    L = math.dist([120, 150], [300, 220])
    for v, th in table:                                          # the rod keeps its length at every crank position
        a, b = math.radians(v), math.radians(th)
        P = [100 + 20 * math.cos(a), 150 + 20 * math.sin(a)]
        Q = [300 + (0 * math.cos(b) - 70 * math.sin(b)), 150 + (0 * math.sin(b) + 70 * math.cos(b))]
        assert math.dist(P, Q) == pytest.approx(L, abs=1e-3)   # (the table keeps 4 decimals)
    assert table[-1][1] == pytest.approx(0, abs=1e-3)           # a full crank turn brings the rocker back
    assert 10 < m['range'][1] - m['range'][0] < 60               # it rocks to and fro, it does not spin
    codes = [x['code'] for x in r['diagnostics']]
    assert 'LINKAGE_TRANSMISSION' not in codes and 'MOTION_COLLISION' not in codes


def test_the_rod_is_pinned_with_real_holes_at_both_ends():
    r, _ = compiled(crank_design('rocker'))
    holes = {c['id']: sorted(f['id'] for f in c.get('features', []) if f['id'].startswith(('pin-', 'axle-')))
             for c in r['design']['components']}
    assert holes['ROD'] == ['pin-rocker-arm', 'pin-rocker-crank']
    assert 'pin-rocker-crank' in holes['CRANK'] and 'pin-rocker-arm' in holes['ARM']


def test_a_slider_crank_strokes_twice_the_crank_radius():
    r, errors = compiled(crank_design('slider'))
    assert not errors, [e['message'] for e in errors]
    m = link_of(r, 'slider')
    at = dict(m['link']['table'])
    assert at[180.0] == pytest.approx(-40.0, abs=1e-3)          # bottom dead centre: pin 2 x 20 mm back
    assert m['range'] == pytest.approx([-40.0, 0.0], abs=1e-3)


def test_a_crank_too_long_for_its_rocker_locks_and_says_where():
    d = crank_design('rocker', crank_pin=(160, 150), disk=140)
    r, errors = compiled(d)
    jam = [e for e in errors if e['code'] == 'LINKAGE_JAM']
    assert jam and 'Grashof' in jam[0]['message'] and any('rod' in c for c in jam[0]['calc'])


def test_a_pin_that_misses_the_rod_is_an_error():
    d = crank_design('rocker')
    d['motions'][1]['link']['to'] = [300, 160, 12]               # not on the rod any more
    _r, errors = compiled(d)
    assert 'MOTION_PIN' in [e['code'] for e in errors]


@pytest.mark.parametrize('change, words', [
    (lambda d: d['motions'][1].update(ratio=2), 'no "ratio"'),
    (lambda d: d['motions'][1].pop('driven_by'), 'needs "driven_by"'),
    (lambda d: d['motions'][1].update(axis='x'), 'same axis'),
    (lambda d: d['motions'][1]['link'].update(rod='CRANK'), 'board of its own'),
])
def test_malformed_links_are_explained(change, words):
    d = crank_design('rocker')
    change(d)
    _r, errors = compiled(d)
    assert any(words in e['message'] for e in errors), [e['message'] for e in errors]


def test_a_rod_that_hits_something_part_way_round_is_caught():
    stop = {'id': 'STOP', 'position': [140, 166, 12], 'size': [20, 14, 6]}   # clear of the rod as drawn, not at 90 deg
    r, _errors = compiled(crank_design('slider', extra=[stop]))
    hits = [x for x in r['diagnostics'] if x['code'] == 'MOTION_COLLISION']
    assert any(set(h['components']) == {'ROD', 'STOP'} and "driven by 'crank'" in h['message'] for h in hits), \
        [h['message'] for h in hits]


def nested():
    """A turntable with a block that slides on it, and a vane that swivels on the block: three levels."""
    return {'format': 'board-design/v1', 'product': {'name': 'nested'},
            'material': {'type': 'plywood', 'thickness': 6, 'kerf': 0.15},
            'boards': [{'id': 'BASE', 'position': [0, 0, 0], 'size': [400, 6, 400]},
                       {'id': 'DISK', 'position': [50, 6, 50], 'size': [300, 6, 300],
                        'profile': {'shape': 'circle', 'center': [150, 150], 'diameter': 300}},
                       {'id': 'BLOCK', 'position': [180, 12, 190], 'size': [40, 6, 20]},
                       {'id': 'FLAG', 'position': [190, 18, 195], 'size': [20, 40, 6]}],
            'connections': [],
            'motions': [{'id': 'spin', 'type': 'rotate', 'boards': ['DISK'], 'on': 'BASE', 'axis': 'y',
                         'pivot': [200, 6, 200], 'range': [0, 360], 'axle': {'diameter': 8}},
                        {'id': 'shift', 'type': 'slide', 'boards': ['BLOCK'], 'on': 'DISK', 'direction': 'x', 'range': [-60, 60]},
                        {'id': 'wave', 'type': 'rotate', 'boards': ['FLAG'], 'on': 'BLOCK', 'axis': 'y',
                         'pivot': [200, 18, 198], 'range': [-30, 30]}]}


def test_a_part_riding_on_a_moving_part_moves_with_it():
    r, errors = compiled(nested())
    assert not [e for e in errors if e['code'] != 'DISCONNECTED'], [e['message'] for e in errors]
    ms = {m['id']: m for m in r['design']['motions']}
    assert ms['shift']['parent'] == 'spin' and ms['wave']['parent'] == 'shift'
    poses = board_poses(r['design']['motions'], {'spin': 90.0, 'shift': 10.0, 'wave': 0.0})
    R, t = poses['BLOCK'][1]
    corner = [sum(R[i][j] * [180, 12, 190][j] for j in range(3)) + t[i] for i in range(3)]
    # slid 10 along x on the disk, then the disk turned 90 deg about y through (200, 200): x -> -z
    want = [200 + (190 - 200), 12, 200 - (190 - 200)]
    assert corner == pytest.approx(want, abs=1e-9)
    assert poses['FLAG'][1][1] == pytest.approx(t, abs=1e-9)    # the flag at rest on the block rides along
    assert next(c for c in r['model3d']['motions'] if c['id'] == 'wave')['parent'] == 'shift'


def test_mounts_in_a_loop_are_refused():
    d = nested()
    d['motions'][0]['on'] = 'FLAG'
    _r, errors = compiled(d)
    assert any('loop' in e['message'] for e in errors if e['code'] == 'MOTION_INVALID')


def test_a_parent_does_not_collide_with_what_rides_on_it():
    r, _ = compiled(nested())
    assert not [x for x in r['diagnostics'] if x['code'] in ('MOTION_COLLISION', 'MOTION_CLEARANCE')
                and {'DISK', 'BLOCK'} & set(x.get('components') or [])]


def test_train_values_follow_gears_and_rods_from_one_input():
    r, _ = compiled(crank_design('rocker'))
    ms = r['design']['motions']
    vals = train_values(ms, 'crank', 90.0)
    assert set(vals) == {'crank', 'rocker'}
    assert vals['rocker'] == pytest.approx(dict(link_of(r, 'rocker')['link']['table'])[90.0], abs=1e-3)


def test_links_and_parents_survive_the_store_and_reach_the_3d_model():
    from board_engine.views import model3d
    r, _ = compiled(crank_design('rocker'))
    stored = normalize_design(dict(r['design'], id='x'))
    m = next(x for x in stored['motions'] if x['id'] == 'rocker')
    assert m['link']['rod'] == 'ROD' and len(m['link']['table']) == len(link_of(r, 'rocker')['link']['table'])
    view = next(x for x in model3d(stored)['motions'] if x['id'] == 'rocker')
    assert view['link']['table'] and 'ratio' not in view


def test_a_reused_mechanism_works_in_every_turned_copy():
    d = crank_design('rocker')
    asm = {'id': 'mech', 'boards': d.pop('boards'), 'connections': [], 'motions': d.pop('motions')}
    d.update(assemblies=[asm], boards=[], instances=[{'assembly': 'mech', 'id': 'A', 'offset': [0, 0, 0]},
                                                     {'assembly': 'mech', 'id': 'B', 'offset': [1000, 0, 0],
                                                      'rotate': {'axis': 'y', 'angle': 90}}])
    r, errors = compiled(d)
    assert not [e for e in errors if e['code'] != 'DISCONNECTED'], [e['message'] for e in errors]
    a, b = link_of(r, 'A-rocker'), link_of(r, 'B-rocker')
    assert b['link']['rod'] == 'B-ROD' and b['axis'] == 'x'
    assert [v for _c, v in b['link']['table']] == pytest.approx([v for _c, v in a['link']['table']], abs=1e-3)


def test_the_linkage_example_in_the_prompt_compiles_clean():
    from board_engine.canvas_prompt import spec_markdown
    spec = spec_markdown()
    block = spec[spec.index('## Linkages'):]
    block = block[block.index('```jsonc') + 8:block.index('```', block.index('```jsonc') + 8)]
    boards_txt, motions_txt = block.split('"motions":')
    d = {'format': 'board-design/v1', 'product': {'name': 'flapper'}, 'material': {'type': 'plywood', 'thickness': 6, 'kerf': 0.15},
         'boards': json.loads('[' + boards_txt.strip().rstrip(',') + ']'), 'connections': [],
         'motions': json.loads(motions_txt.strip())}
    r, errors = compiled(d)
    assert not errors, [e['message'] for e in errors]
    assert next(m for m in r['model3d']['motions'] if m['id'] == 'flap')['link']['table']
    assert 'nested' in spec.lower() or 'rides on its parent' in spec
