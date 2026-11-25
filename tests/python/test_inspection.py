"""Geometric inspection: visible gaps, almost-flush edges, uneven rows and near-symmetric pairs, with calculations."""
import json

import pytest

from board_engine.canvas import compile_source

CODES = ('VISIBLE_GAP', 'MISALIGNED', 'UNEVEN_SPACING', 'ASYMMETRIC', 'OFF_CENTRE', 'MISMATCHED_PAIR', 'UNJOINED_CONTACT')


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
                         'facing area = 120.0 × 200.0 mm', 'same rigid structure: yes']
    assert g['fixes'][0]['edits'][0]['value'] == [6, 6, 0]


@pytest.mark.parametrize('gap, sev', [(0, None), (2, 'warning'), (9, 'warning'), (20, None)])   # one rigid structure
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
    assert u['board'] == 'S2' and u['calc'][2].startswith('moving S2 by -2.00 mm makes 3 of 3 spacings equal')
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


def table(**move):
    """A study-table-like frame: a top over two legs joined by a modesty panel; `move` shifts / resizes one board."""
    B = {'TOP': [[0, 732, 0], [1200, 18, 600]], 'LEG-L': [[50, 0, 20], [18, 732, 560]],
         'LEG-R': [[1132, 0, 20], [18, 732, 560]], 'MOD': [[68, 432, 480], [1064, 300, 18]]}
    for k, (pd, sd) in move.items():
        B[k] = [[B[k][0][j] + pd[j] for j in range(3)], [B[k][1][j] + sd[j] for j in range(3)]]
    conns = [('LEG-L', 'TOP'), ('LEG-R', 'TOP'), ('MOD', 'TOP'), ('MOD', 'LEG-L'), ('MOD', 'LEG-R')]
    d = {'format': 'board-design/v1', 'product': {'name': 't'}, 'material': {'type': 'plywood', 'thickness': 18},
         'boards': [{'id': k, 'position': v[0], 'size': v[1]} for k, v in B.items()],
         'connections': [dict(type='tab_slot', tabs=2, board=b, into=i) for b, i in conns]}
    return d


def found_in(d, code):
    r = compile_source(json.dumps(d), run_production=False)
    return [x for x in r['diagnostics'] if x['code'] == code and x['severity'] == 'warning']


def test_clean_table_has_no_findings():
    r = compile_source(json.dumps(table()), run_production=False)
    assert r['ok'] and not [x for x in r['diagnostics'] if x['code'] in CODES and x['severity'] != 'info']


def test_top_slightly_off_centre():
    o = found_in(table(TOP=([3, 0, 0], [0, 0, 0])), 'OFF_CENTRE')
    assert o and o[0]['board'] == 'TOP' and o[0]['calc'][-1].startswith('difference = |47.00 - 53.00| = 6.00 mm')
    assert o[0]['fixes'][0]['edits'][0]['value'] == [0, 732, 0]


def test_twin_legs_that_differ():
    m = found_in(table(**{'LEG-R': ([0, 0, 3], [0, 0, 0])}), 'MISMATCHED_PAIR')
    assert m and m[0]['board'] == 'LEG-R' and 'min z: LEG-R = 23.0 mm, LEG-L = 20.0 mm -> +3.00 mm' in m[0]['calc']
    assert m[0]['fixes'][0]['edits'][0]['value'] == [1132, 0, 20]
    m = found_in(table(**{'LEG-R': ([0, 0, 0], [0, 0, 2])}), 'MISMATCHED_PAIR')
    assert m and 'size z +2 mm' in m[0]['message'] and not m[0].get('fixes')


def test_board_resting_without_its_connection():
    d = table()
    d['connections'] = [c for c in d['connections'] if c['board'] != 'LEG-L' or c['into'] != 'TOP']
    u = found_in(d, 'UNJOINED_CONTACT')
    assert [x['components'] for x in u] == [['TOP', 'LEG-L']] and 'contact direction: y (vertical: load bearing)' in u[0]['calc']


def test_spacing_uses_the_repeated_step_not_a_deliberate_first_gap():
    ys = [80, 450, 853, 1250]                 # 370 (deliberate), 403, 397: shelf 3 is 3 mm high
    _r, found = build([{'id': 'L', 'position': [0, 6, 0], 'size': [6, 1300, 200]}]
                      + [{'id': f'S{i}', 'position': [6, y, 0], 'size': [100, 6, 200]} for i, y in enumerate(ys)],
                      [('L', 'BASE')] + [(f'S{i}', 'L') for i in range(4)])
    u = next(x for x in found if x['code'] == 'UNEVEN_SPACING')
    assert u['board'] == 'S2' and u['fixes'][0]['edits'][0]['value'] == [6, 850, 0]


def test_thin_board_standing_on_its_edge_without_a_connection():
    d = {'format': 'board-design/v1', 'product': {'name': 'box'}, 'material': {'type': 'plywood', 'thickness': 6},
         'boards': [{'id': 'BASE', 'position': [0, 0, 0], 'size': [240, 6, 160]},
                    {'id': 'FRONT', 'position': [0, 6, 154], 'size': [240, 88, 6]},
                    {'id': 'LEFT', 'position': [0, 6, 0], 'size': [6, 88, 154]}],
         'connections': [{'type': 'finger', 'board': 'LEFT', 'into': 'BASE'}, {'type': 'finger', 'board': 'FRONT', 'into': 'LEFT'}]}
    u = found_in(d, 'UNJOINED_CONTACT')
    assert [x['components'] for x in u] == [['FRONT', 'BASE']] and 'contact = 240.0 × 6.0 mm' in u[0]['calc']


def test_rail_end_without_its_connection():
    d = table()
    d['connections'] = [c for c in d['connections'] if not (c['board'] == 'MOD' and c['into'] == 'LEG-L')]
    u = found_in(d, 'UNJOINED_CONTACT')
    assert u and "The end of 'MOD' butts against 'LEG-L'" in u[0]['message'] and 'it is the board' in u[0]['calc'][-1]
