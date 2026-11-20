"""Several glue-free structures in one product (finger corners, egg-crate cross-laps, tabs) and a forgiving
connection compiler: typical AI mistakes are corrected with a warning instead of failing."""
import copy
import json

import pytest

from board_engine import geometry as G
from board_engine.canvas import _cut_outline, apply_code_fix, compile_source
from board_engine.canvas_prompt import EXAMPLE, STRUCTURES_EXAMPLE
from board_engine.shapes import ShapeError
from board_engine.validation import validate_design
from board_engine.views import export, production_package


def _codes(r, severity):
    return [d['code'] for d in r['diagnostics'] if d['severity'] == severity]


def _types(design):
    out = {}
    for j in design['joints']:
        out[j['type']] = out.get(j['type'], 0) + 1
    return out


# ---------------------------------------------------------------------------
# Outline cutter (exact rectilinear union / difference)
# ---------------------------------------------------------------------------

def test_cutter_handles_overlapping_corner_cuts_exactly():
    assert _cut_outline(100, 50, []) == [[0.0, 0.0], [100, 0.0], [100, 50], [0.0, 50]]
    o = _cut_outline(300, 200, [('v0', -0.05, 30.05, -6), ('u0', 5.95, 40, -6), ('v1', 0, 30, 6), ('v1', 60, 90, 6)])
    removed = 30.05 * 6 + 34.05 * 6 - 6 * 0.05                 # two notches sharing a corner region
    assert abs(G.signed_area(o) - (300 * 200 - removed + 2 * 30 * 6)) < 1e-6
    assert not G.self_intersections(o)


def test_cutter_refuses_cuts_that_split_the_board():
    with pytest.raises(ShapeError):
        _cut_outline(100, 50, [('v0', 40, 60, -50)])


# ---------------------------------------------------------------------------
# The multi-structure example
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def organiser():
    r = compile_source(json.dumps(STRUCTURES_EXAMPLE, indent=2))
    assert r['ok'], r['diagnostics']
    return r


def test_organiser_compiles_clean_with_all_three_glue_free_joints(organiser):
    s = organiser['summary']
    assert s['errors'] == 0 and s['warnings'] == 0 and s['joined'] == s['joints']
    assert _types(organiser['design']) == {'finger': 8, 'cross_lap': 2, 'tab_slot': 4}
    assert organiser['layout']['ready_for_production'] and organiser['layout']['cut']['issues'] == []
    assert organiser['design']['joinery'] == 'interlocking'


def test_organiser_goes_through_every_output(organiser):
    pkg = production_package(organiser['design'], {'compensate_kerf': True})
    assert {p['id'] for p in pkg['nesting']['placements']} == {b['id'] for b in STRUCTURES_EXAMPLE['boards']}
    for i in range(pkg['nesting']['sheet_count']):
        assert 'CUT_OUTER' in export(pkg, 'svg', i)[0] and 'POLYLINE' in export(pkg, 'dxf', i)[0]
    assert export(pkg, 'pdf')[0][:5] == b'%PDF-'
    steps = pkg['manufacturing']['assembly_plan']
    assert steps, 'an assembly order must be derived for finger / cross-lap joints too'


def test_connections_can_be_inferred_from_the_geometry():
    d = copy.deepcopy(STRUCTURES_EXAMPLE)
    d['connections'] = 'auto'
    r = compile_source(json.dumps(d), run_production=False)
    assert r['ok'], r['diagnostics']
    assert 'CONNECTIONS_INFERRED' in _codes(r, 'info')
    t = _types(r['design'])
    assert t['finger'] == 8 and t['cross_lap'] == 2 and t['tab_slot'] >= 3
    d.pop('connections')                                     # leaving it out means the same
    assert compile_source(json.dumps(d), run_production=False)['ok']


def test_auto_connect_adds_only_the_missing_connections():
    d = copy.deepcopy(STRUCTURES_EXAMPLE)
    d['connections'] = [c for c in d['connections'] if c['type'] == 'finger']
    d['auto_connect'] = True
    r = compile_source(json.dumps(d), run_production=False)
    assert r['ok'] and _types(r['design'])['cross_lap'] == 2


# ---------------------------------------------------------------------------
# Typical AI mistakes are corrected (with a warning that teaches the exact format)
# ---------------------------------------------------------------------------

def _c(d, i):
    return d['connections'][i]


MISTAKES = [
    ('board / into swapped', lambda d: _c(d, 0).update(board='TOP', into='LEG-L'), 'CONNECTION_REVERSED'),
    ('type spelled "tab-slot"', lambda d: _c(d, 0).__setitem__('type', 'tab-slot'), 'CONNECTION_TYPE_NORMALISED'),
    ('type spelled "Tab and Slot"', lambda d: _c(d, 0).__setitem__('type', 'Tab and Slot'), 'CONNECTION_TYPE_NORMALISED'),
    ('keys from / to', lambda d: d['connections'].__setitem__(0, {'id': 'X', 'type': 'tab_slot', 'from': 'LEG-L', 'to': 'TOP',
                                                                   'tabs': 2}), 'CONNECTION_KEYS_NORMALISED'),
    ('board id in lower case', lambda d: _c(d, 0).update(board='leg-l'), 'BOARD_REFERENCE_NORMALISED'),
    ('board referenced by name', lambda d: _c(d, 0).update(into='Table top'), 'BOARD_REFERENCE_NORMALISED'),
    ('duplicate and reversed duplicate', lambda d: d['connections'].extend([dict(_c(d, 0), id='DUP'),
                                                                            {'id': 'REV', 'board': 'TOP', 'into': 'LEG-L'}]),
     'DUPLICATE_CONNECTION'),
]


@pytest.mark.parametrize('title, mutate, warning', MISTAKES, ids=[m[0] for m in MISTAKES])
def test_common_ai_mistakes_compile_with_a_teaching_warning(title, mutate, warning):
    d = copy.deepcopy(EXAMPLE)
    mutate(d)
    r = compile_source(json.dumps(d, indent=2), run_production=False)
    assert r['ok'], (title, [(x['code'], x['message']) for x in r['diagnostics'] if x['severity'] == 'error'])
    assert warning in _codes(r, 'warning')
    assert r['summary']['joined'] == r['summary']['joints']


def test_box_corner_written_as_tab_slot_becomes_a_finger_joint():
    d = copy.deepcopy(STRUCTURES_EXAMPLE)
    for c in d['connections']:
        if c['type'] == 'finger':
            c['type'] = 'tab_slot'
    r = compile_source(json.dumps(d), run_production=False)
    assert r['ok'] and 'CONNECTION_TYPE_CHANGED' in _codes(r, 'warning')
    assert _types(r['design'])['finger'] == 8


def test_crossing_written_as_tab_slot_becomes_a_cross_lap():
    d = copy.deepcopy(STRUCTURES_EXAMPLE)
    for c in d['connections']:
        if c['type'] == 'cross_lap':
            c['type'] = 'tab_slot'
    r = compile_source(json.dumps(d), run_production=False)
    assert r['ok'] and _types(r['design'])['cross_lap'] == 2


def test_real_mistakes_stay_errors_with_a_helpful_fix():
    d = copy.deepcopy(EXAMPLE)
    d['connections'].append({'id': 'BAD', 'type': 'tab_slot', 'board': 'SHELF', 'into': 'TOP'})
    r = compile_source(json.dumps(d), run_production=False)
    e = next(x for x in r['diagnostics'] if x['code'] == 'NO_CONTACT')
    assert e['fixes'][0]['title'].startswith("Remove connection 'BAD'")
    assert compile_source(apply_code_fix(json.dumps(d), e['fixes'][0]), run_production=False)['ok']
    d = copy.deepcopy(EXAMPLE)
    d['connections'].append({'id': 'TYPO', 'type': 'tab_slot', 'board': 'SHELF', 'into': 'LEG-X'})
    e = next(x for x in compile_source(json.dumps(d), run_production=False)['diagnostics'] if x['code'] == 'UNKNOWN_BOARD')
    assert 'Did you mean' in e['message'] and 'LEG-' in e['message']
    d = copy.deepcopy(EXAMPLE)
    d['connections'].append({'id': 'G', 'type': 'glue', 'board': 'SHELF', 'into': 'LEG-L'})
    assert 'CONNECTION_TYPE' in _codes(compile_source(json.dumps(d), run_production=False), 'error')


def test_crossing_boards_without_a_connection_get_a_safe_cross_lap_fix():
    d = copy.deepcopy(EXAMPLE)
    d['boards'].append({'id': 'DIV', 'name': 'Divider', 'group': 'Shelves', 'position': [600, 168, 60], 'size': [18, 300, 440]})
    d['connections'].append({'id': 'DIV-SH', 'type': 'tab_slot', 'board': 'DIV', 'into': 'SHELF'})
    src = json.dumps(d, indent=2)
    r = compile_source(src, run_production=False)
    fix = next(f for x in r['diagnostics'] if x['code'] == 'COLLISION' for f in x.get('fixes') or [])
    assert fix['safe'] and 'cross_lap' in fix['title']
    r2 = compile_source(apply_code_fix(src, fix), run_production=False)
    assert r2['ok'] and _types(r2['design'])['cross_lap'] == 1


# ---------------------------------------------------------------------------
# Finger / cross-lap fit audit (tolerances: contact 0.25 mm, slot_position 0.5 mm, clearance from the material)
# ---------------------------------------------------------------------------

def _comp(d, cid):
    return next(c for c in d['components'] if c['id'] == cid)


def _move(d, cid, v):
    p = _comp(d, cid)['placement']['position']
    for i in range(3):
        p[i] += v[i]


def _plain(d, cid):
    c = _comp(d, cid)
    xs, ys = [q[0] for q in c['outline']], [q[1] for q in c['outline']]
    c['outline'] = [[min(xs) + 6, min(ys) + 6], [max(xs) - 6, min(ys) + 6], [max(xs) - 6, max(ys)], [min(xs) + 6, max(ys)]]


JOINT_AUDIT = [
    ('clean', lambda d: None, 'DIV-Z1', None),
    ('cross divider slid 0.04 (within clearance)', lambda d: _move(d, 'DIV-Z1', [0.04, 0, 0]), 'DIV-Z1', None),
    ('cross divider slid 0.6', lambda d: _move(d, 'DIV-Z1', [0.6, 0, 0]), 'DIV-Z1', 'NOTCH_MISALIGNED'),
    ('cross divider lifted 1', lambda d: _move(d, 'DIV-Z1', [0, 1, 0]), 'DIV-Z1', 'NOT_INTERLOCKED'),
    ('cross divider dropped 1', lambda d: _move(d, 'DIV-Z1', [0, -1, 0]), 'DIV-Z1', 'PENETRATION'),
    ('wall slid 1 along its corner', lambda d: _move(d, 'LEFT', [0, 0, 1.0]), 'LEFT', 'PENETRATION'),
    ('wall pulled out 0.5 (not flush)', lambda d: _move(d, 'LEFT', [-0.5, 0, 0]), 'LEFT', 'FINGER_NOT_FLUSH'),
    ('wall without its fingers', lambda d: _plain(d, 'LEFT'), 'LEFT', 'NOT_INTERLOCKED'),
]


@pytest.mark.parametrize('title, mutate, about, code', JOINT_AUDIT, ids=[a[0] for a in JOINT_AUDIT])
def test_finger_and_cross_lap_fit_audit(organiser, title, mutate, about, code):
    d = copy.deepcopy(organiser['design'])
    mutate(d)
    issues = [i for i in validate_design(d)['issues'] if i['severity'] in ('error', 'warning') and about in json.dumps(i)]
    found = {i['code'] for i in issues} | {c['code'] for i in issues for c in i.get('causes', [])}
    if code is None:
        assert not found, (title, found)
    else:
        assert code in found, (title, found)


def test_finger_and_cross_lap_are_glue_free(organiser):
    rep = validate_design(organiser['design'])
    assert not [i for i in rep['issues'] if i['code'] == 'GLUE_JOINT_NOT_ALLOWED']
