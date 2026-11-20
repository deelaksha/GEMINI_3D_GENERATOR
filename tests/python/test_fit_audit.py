"""Fit / gap audit: break a clean, fully joined design by known amounts and check exactly what is reported.

Tolerances under test (validation.TOL): contact 0.25 mm, slot_fit 0.15 mm (tight side), slot_loose 0.3 mm
(loose side), slot_position 0.5 mm; near-miss window (contact, 2 mm]; tab protrusion > contact beyond the depth
needed to pass through the receiver.
"""
import copy
import json
import math

import pytest

from board_engine import geometry as G
from board_engine.canvas import compile_source
from board_engine.canvas_prompt import COMPLEX_EXAMPLE, EXAMPLE
from board_engine.validation import validate_design
try:
    from board_engine.validation import NEAR_MISS
except ImportError:     # not implemented yet
    NEAR_MISS = None

J = 'gf-floor-t1'          # front gable -> floor (square joint)
R = 'gf-roofl-t1'          # front gable -> left roof (35 deg tilted joint)


@pytest.fixture(scope='module')
def base():
    d = compile_source(json.dumps(COMPLEX_EXAMPLE), run_production=False)['design']
    rep = validate_design(d)
    assert rep['valid'] and all(j['status'] == 'joined' for j in d['joints'])
    return d


def comp(d, cid):
    return next(c for c in d['components'] if c['id'] == cid)


def reported(d, about):
    """{code: severity} of the errors / warnings that mention `about` (a component or joint id)."""
    return {i['code']: i['severity'] for i in validate_design(d)['issues']
            if i['severity'] in ('error', 'warning') and (about in i.get('components', []) or about in json.dumps(i))}


def slot_of(d, jid):
    j = next(j for j in d['joints'] if j['id'] == jid)
    return next(f for f in comp(d, j['b'])['features'] if f['id'] == j['slot'])


def slot_dim(d, jid, which, delta):
    f = slot_of(d, jid)
    thick = 'width' if f['width'] < f['height'] else 'height'
    f[thick if which == 'thick' else ({'width': 'height', 'height': 'width'}[thick])] += delta


def slot_shift(d, jid, delta):
    f = slot_of(d, jid)
    a = math.radians(f.get('angle', 0))
    ux, uy = (math.cos(a), math.sin(a)) if f['width'] >= f['height'] else (-math.sin(a), math.cos(a))
    f['center'] = [f['center'][0] + ux * delta, f['center'][1] + uy * delta]


def tab(d, cid, tid):
    return next(t for t in comp(d, cid)['tabs'] if t['id'] == tid)


def move(d, cid, vec):
    p = comp(d, cid)['placement']['position']
    for i in range(3):
        p[i] += vec[i]


ROOF_N = [-math.sin(math.radians(35)), math.cos(math.radians(35)), 0.0]     # ROOF-L face normal


def _case(base, mutate):
    d = copy.deepcopy(base)
    mutate(d)
    return d


# (title, mutate, about, expected) - expected None = nothing reported, else {code: severity} that must appear
AUDIT = [
    ('board lifted 0.2 (within contact)', lambda d: move(d, 'GABLE-F', [0, 0.2, 0]), 'GABLE-F', None),
    ('board lifted 0.3', lambda d: move(d, 'GABLE-F', [0, 0.3, 0]), 'GABLE-F', {'JOINT_BROKEN': 'error'}),
    ('board lifted 1.0', lambda d: move(d, 'GABLE-F', [0, 1.0, 0]), 'GABLE-F', {'JOINT_BROKEN': 'error'}),
    ('board pushed in 0.2', lambda d: move(d, 'GABLE-F', [0, -0.2, 0]), 'GABLE-F', None),
    ('board pushed in 0.3', lambda d: move(d, 'GABLE-F', [0, -0.3, 0]), 'GABLE-F', {'JOINT_BROKEN': 'error', 'COLLISION': 'error'}),
    ('tilted roof off 0.2', lambda d: move(d, 'ROOF-L', [v * 0.2 for v in ROOF_N]), 'ROOF-L', None),
    ('tilted roof off 0.5', lambda d: move(d, 'ROOF-L', [v * 0.5 for v in ROOF_N]), 'ROOF-L', {'JOINT_BROKEN': 'error'}),
    ('tilted roof into gables 0.5', lambda d: move(d, 'ROOF-L', [-v * 0.5 for v in ROOF_N]), 'ROOF-L', {'JOINT_BROKEN': 'error', 'COLLISION': 'error'}),
    ('slot 0.1 narrow (within slot_fit)', lambda d: slot_dim(d, J, 'thick', -0.1), J, None),
    ('slot 0.3 narrow', lambda d: slot_dim(d, J, 'thick', -0.3), J, {'JOINT_BROKEN': 'error'}),
    ('slot 0.2 wide (within slot_loose)', lambda d: slot_dim(d, J, 'thick', 0.2), J, None),
    ('slot 0.4 wide', lambda d: slot_dim(d, J, 'thick', 0.4), J, {'JOINT_BROKEN': 'error'}),
    ('slot 0.7 wide', lambda d: slot_dim(d, J, 'thick', 0.7), J, {'JOINT_BROKEN': 'error'}),
    ('tilted slot 0.3 narrow', lambda d: slot_dim(d, R, 'thick', -0.3), R, {'JOINT_BROKEN': 'error'}),
    ('tilted slot 0.4 wide', lambda d: slot_dim(d, R, 'thick', 0.4), R, {'JOINT_BROKEN': 'error'}),
    ('slot 0.5 shorter than tab', lambda d: slot_dim(d, J, 'long', -0.5), J, {'JOINT_BROKEN': 'error'}),
    ('slot 2 mm longer than tab', lambda d: slot_dim(d, J, 'long', 2.0), J, {'SLOT_LONGER_THAN_TAB': 'warning'}),
    ('slot shifted 0.4 (within slot_position)', lambda d: slot_shift(d, J, 0.4), J, None),
    ('slot shifted 0.6', lambda d: slot_shift(d, J, 0.6), J, {'JOINT_BROKEN': 'error'}),
    ('tab 0.3 short of the far face', lambda d: tab(d, 'GABLE-F', J).__setitem__('depth', 5.7), J, {'TAB_NOT_FLUSH': 'warning'}),
    ('tab flush', lambda d: None, J, None),
    ('tab 0.1 proud (within contact)', lambda d: tab(d, 'GABLE-F', J).__setitem__('depth', 6.1), J, None),
    ('tab 0.3 proud', lambda d: tab(d, 'GABLE-F', J).__setitem__('depth', 6.3), J, {'TAB_PROTRUDES': 'warning'}),
    ('tab 1.0 proud', lambda d: tab(d, 'GABLE-F', J).__setitem__('depth', 7.0), J, {'TAB_PROTRUDES': 'warning'}),
    ('tab 1.0 proud, marked intentional', lambda d: tab(d, 'GABLE-F', J).update(depth=7.0, protrude=True), J, None),
    ('wall slid into an unjoined board', lambda d: move(d, 'SIDE-L', [0, 0, -0.5]), 'SIDE-L', {'COLLISION': 'error'}),
]


@pytest.mark.parametrize('title, mutate, about, expected', AUDIT, ids=[a[0] for a in AUDIT])
def test_fit_and_gap_audit(base, title, mutate, about, expected):
    got = reported(_case(base, mutate), about)
    if expected is None:
        assert not got, f'{title}: expected nothing, got {got}'
    else:
        missing = {k: v for k, v in expected.items() if got.get(k) != v}
        assert not missing, f'{title}: expected {expected}, got {got}'


def test_messages_state_the_measured_amount(base):
    msgs = lambda d: ' '.join(i['message'] for i in validate_design(d)['issues'])
    assert 'stands 1.00 mm off the face' in msgs(_case(base, lambda d: move(d, 'GABLE-F', [0, 1.0, 0])))
    assert '6.80 mm wide for a 6.00 mm board' in msgs(_case(base, lambda d: slot_dim(d, J, 'thick', 0.7)))
    assert '0.60 mm away from where tab' in msgs(_case(base, lambda d: slot_shift(d, J, 0.6)))
    assert 'protrudes 1.00 mm' in msgs(_case(base, lambda d: tab(d, 'GABLE-F', J).__setitem__('depth', 7.0)))


# ---------------------------------------------------------------------------
# Near misses: faces almost touching where no joint was declared
# ---------------------------------------------------------------------------

def _unjoin(d, a, b):
    gone = {j['id'] for j in d['joints'] if {j['a'], j['b']} == {a, b}}
    d['joints'] = [j for j in d['joints'] if j['id'] not in gone]
    for c in d['components']:
        c['tabs'] = [t for t in c.get('tabs', []) if t['id'] not in gone]
        c['features'] = [f for f in c.get('features', []) if not any(g in f['id'] for g in gone)]


def _shorten_back(d, cid, gap):
    """Pull the -z end of a board back by `gap` (pure end gap, nothing else moves)."""
    c = comp(d, cid)
    f = G.Frame(c['placement']['position'], c['placement']['rotation'])
    zs = [f.to_world([x, y, 0])[2] for x, y in c['outline']]
    dz = f.dir_to_local([0, 0, 1])
    c['outline'] = [[x + dz[0] * gap, y + dz[1] * gap] if abs(z - min(zs)) < 1e-6 else [x, y]
                    for (x, y), z in zip(c['outline'], zs)]


@pytest.mark.parametrize('gap, warned', [(0.0, False), (0.2, False), (0.5, True), (2.0, True), (3.0, False)])
def test_end_face_near_miss_without_a_joint(base, gap, warned):
    d = copy.deepcopy(base)
    _unjoin(d, 'SIDE-L', 'GABLE-B')
    _shorten_back(d, 'SIDE-L', gap)
    near = [i for i in validate_design(d)['issues'] if i['code'] == 'NEAR_MISS_GAP']
    assert bool(near) == warned, near
    if warned:
        assert set(near[0]['components']) == {'SIDE-L', 'GABLE-B'} and abs(near[0]['gap'] - gap) < 0.01
        assert near[0]['severity'] == 'warning'


@pytest.mark.parametrize('gap, warned', [(0.0, False), (0.3, True), (1.5, True), (2.5, False)])
def test_stacked_faces_near_miss(gap, warned):
    """A loose board lying (unjoined) on top of another: its bottom face is `gap` above the other's top face."""
    d = copy.deepcopy(EXAMPLE)
    d['boards'].append({'id': 'TRAY', 'name': 'Tray', 'group': 'Top', 'position': [300, 750 + gap, 100],
                        'size': [400, 18, 300]})
    design = compile_source(json.dumps(d), run_production=False)['design']
    near = [i for i in validate_design(design)['issues'] if i['code'] == 'NEAR_MISS_GAP']
    assert bool(near) == warned, near
    if warned:
        assert set(near[0]['components']) == {'TRAY', 'TOP'} and abs(near[0]['gap'] - gap) < 0.01


def test_near_miss_window_is_contact_to_two_millimetres():
    from board_engine.validation import TOL
    assert NEAR_MISS == 2.0 and TOL['slot_loose'] == 0.3


def _shipped_designs():
    from board_engine.examples import boat, furniture
    import os
    out = [('boat', boat.build_design()[0])] + [(name, furniture.build(name)[0]) for name in furniture.PRODUCTS]
    house = os.path.join(os.path.dirname(__file__), 'fixtures', 'village_house.json')
    out.append(('village_house', compile_source(open(house).read(), run_production=False)['design']))
    for nm, src in (('study_table', EXAMPLE), ('cottage', COMPLEX_EXAMPLE)):
        out.append((nm, compile_source(json.dumps(src), run_production=False)['design']))
    return out


def test_shipped_designs_raise_no_false_near_miss_or_protrusion_warnings():
    for name, d in _shipped_designs():
        bad = [(i['code'], i['message']) for i in validate_design(d)['issues']
               if i['code'] in ('NEAR_MISS_GAP', 'TAB_PROTRUDES')]
        assert not bad, f'{name}: {bad[:3]}'


def test_hinged_doors_keep_their_running_clearance_without_warnings():
    """The wardrobe partition stops 1 mm behind the closed door on purpose; doors are moving parts."""
    from board_engine.examples import furniture
    d = furniture.build('wardrobe')[0]
    assert any(j['type'] == 'hinge' and j['a'] == 'DOOR-L' for j in d['joints'])
    assert not [i for i in validate_design(d)['issues'] if i['code'] == 'NEAR_MISS_GAP']
