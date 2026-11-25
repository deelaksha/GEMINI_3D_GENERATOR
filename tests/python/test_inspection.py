"""Geometric inspection: visible gaps, almost-flush edges, uneven rows and near-symmetric pairs, with calculations."""
import json

import pytest

from board_engine.canvas import compile_source

CODES = ('VISIBLE_GAP', 'MISALIGNED', 'UNEVEN_SPACING', 'ASYMMETRIC')


def build(extra, conns):
    d = {'format': 'board-design/v1', 'product': {'name': 't'}, 'material': {'type': 'plywood', 'thickness': 6},
         'boards': [{'id': 'BASE', 'position': [0, 0, 0], 'size': [300, 6, 200]}] + extra,
         'connections': [dict(type='tab_slot', tabs=2, board=b, into=i) for b, i in conns]}
    r = compile_source(json.dumps(d), run_production=False)
    return r, [x for x in r['diagnostics'] if x['code'] in CODES]


def two_sides(gap):
    return build([{'id': 'SIDE', 'position': [0, 6, 0], 'size': [6, 120, 200]},
                  {'id': 'PANEL', 'position': [6 + gap, 6, 0], 'size': [6, 120, 200]}], [('SIDE', 'BASE'), ('PANEL', 'BASE')])


def test_visible_gap_with_its_arithmetic_and_a_move():
    _r, found = two_sides(6)
    g = found[0]
    assert g['code'] == 'VISIBLE_GAP' and g['severity'] == 'warning' and g['components'] == ['PANEL', 'SIDE']
    assert g['calc'] == ['SIDE.xmax = 6.0 mm', 'PANEL.xmin = 12.0 mm', 'gap = 12.0 - 6.0 = 6.00 mm (contact is <= 0.5 mm)',
                         'facing area = 120.0 × 200.0 mm']
    assert g['fixes'][0]['edits'][0]['value'] == [6, 6, 0]


@pytest.mark.parametrize('gap, sev', [(0, None), (2, 'info'), (9, 'warning'), (20, None)])
def test_gap_sizes(gap, sev):
    _r, found = two_sides(gap)
    assert [g['severity'] for g in found if g['code'] == 'VISIBLE_GAP'] == ([sev] if sev else [])


def test_almost_flush_edge_is_misaligned_but_a_deliberate_inset_is_not():
    _r, found = build([{'id': 'SIDE', 'position': [0, 6, 2], 'size': [6, 120, 196]}], [('SIDE', 'BASE')])
    m = [x for x in found if x['code'] == 'MISALIGNED']
    assert len(m) == 1 and 'offset = |2.0 - 0.0| = 2.00 mm' in m[0]['calc'][2]
    assert m[0]['fixes'][0]['edits'][0]['value'] == [0, 6, 0]
    for inset in (6, 20):                     # one board thickness, or clearly deliberate
        _r, found = build([{'id': 'SIDE', 'position': [0, 6, inset], 'size': [6, 120, 200 - 2 * inset]}], [('SIDE', 'BASE')])
        assert not found


def test_one_misplaced_shelf_in_an_even_row():
    ys = [60, 120, 182, 240]
    _r, found = build([{'id': 'L', 'position': [0, 6, 0], 'size': [6, 300, 200]}]
                      + [{'id': f'S{i}', 'position': [6, y, 0], 'size': [100, 6, 200]} for i, y in enumerate(ys)],
                      [('L', 'BASE')] + [(f'S{i}', 'L') for i in range(4)])
    u = next(x for x in found if x['code'] == 'UNEVEN_SPACING')
    assert u['board'] == 'S2' and 'median spacing = 60.00 mm' in u['calc']
    assert u['fixes'][0]['edits'][0]['value'] == [6, 180, 0]


def test_deliberately_varied_spacing_is_left_alone():
    _r, found = build([{'id': 'L', 'position': [0, 6, 0], 'size': [6, 400, 200]}]
                      + [{'id': f'S{i}', 'position': [6, y, 0], 'size': [100, 6, 200]} for i, y in enumerate([60, 160, 300])],
                      [('L', 'BASE')] + [(f'S{i}', 'L') for i in range(3)])
    assert not [x for x in found if x['code'] == 'UNEVEN_SPACING']


def test_near_symmetric_pair():
    _r, found = build([{'id': 'LS', 'position': [0, 6, 0], 'size': [6, 120, 200]},
                       {'id': 'RS', 'position': [291, 6, 0], 'size': [6, 120, 200]}], [('LS', 'BASE'), ('RS', 'BASE')])
    a = next(x for x in found if x['code'] == 'ASYMMETRIC')
    assert a['calc'][-1] == 'difference = |0.00 - 3.00| = 3.00 mm' and a['fixes'][0]['edits'][0]['value'] == [294, 6, 0]
    _r, found = build([{'id': 'LS', 'position': [0, 6, 0], 'size': [6, 120, 200]},
                       {'id': 'RS', 'position': [294, 6, 0], 'size': [6, 120, 200]}], [('LS', 'BASE'), ('RS', 'BASE')])
    assert not found


def test_measurements_and_calculations_reach_the_result_and_the_fix_prompt():
    from board_engine.canvas_prompt import build_repair_prompt
    r, _found = two_sides(6)
    assert r['inspection']['boards']['PANEL'] == {'min': [12.0, 6.0, 0.0], 'max': [18.0, 126.0, 200.0], 'size': [6.0, 120.0, 200.0]}
    assert 'Calculation: SIDE.xmax = 6.0 mm; PANEL.xmin = 12.0 mm' in build_repair_prompt('{}', r['diagnostics'])
    floating = build([{'id': 'F', 'position': [0, 100, 0], 'size': [100, 6, 100]}], [])[0]
    iso = next(x for x in floating['diagnostics'] if x['code'] == 'ISOLATED_BOARD')
    assert iso['calc'][-1].startswith('distance = sqrt(0.0² + 94.0² + 0.0²) = 94.00 mm')


def test_eye_check_moves_always_ask_first():
    _r, found = two_sides(6)
    assert found[0]['fixes'] and not found[0]['fixes'][0]['safe']
