"""Cutting / nesting edge cases run on the real engine (native designs, so exact sizes can be injected)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from board_engine.canvas import compile_source  # noqa: E402
from board_engine.model import SchemaError, build_plates, normalize_design  # noqa: E402
from board_engine.nesting import nest, part_area  # noqa: E402
from board_engine.views import production_package  # noqa: E402


def _rect(cid, w, h, t=18, **kw):
    return dict({'id': cid, 'outline': [[0, 0], [w, 0], [w, h], [0, h]], 'thickness': t,
                 'placement': {'position': [0, 0, 0], 'rotation': [0, 0, 0]}}, **kw)


def _design(comps, sheet=(2440, 1220), kerf=3.2, mtype='plywood'):
    return normalize_design({'id': 'n', 'material': {'thickness': 18, 'kerf': kerf, 'type': mtype},
                             'sheet': {'width': sheet[0], 'height': sheet[1], 'spacing': 6}, 'components': comps, 'joints': []})


def run():
    rows = []

    def add(cid, name, expected, actual, ok):
        rows.append({'id': cid, 'case': name, 'expected': expected, 'actual': actual, 'pass': bool(ok)})

    # usable area of 2440 x 1220 with the production defaults: margin 10, title strip 14 -> 2420 x 1186
    n = nest(_design([_rect('EXACT', 2420, 1186)]), {'title_block': 14})
    add('NS-01', 'Part exactly the usable sheet area (2420 x 1186)', 'placed', {'placed': len(n['placements']), 'unplaced': n['unplaced']},
        len(n['placements']) == 1)
    n = nest(_design([_rect('BIG', 2421, 1186)]), {'title_block': 14})
    add('NS-02', 'Part 1 mm larger than the usable area', 'PART_EXCEEDS_SHEET', [u['code'] for u in n['unplaced']],
        [u['code'] for u in n['unplaced']] == ['PART_EXCEEDS_SHEET'])
    pkg = production_package(_design([_rect('NARROW', 600, 12)]), {'compensate_kerf': True})
    add('NS-03', 'Very narrow part (600 x 12 mm plywood)', 'PART_BELOW_MIN_SIZE blocks production',
        sorted({i['code'] for i in pkg['blocking_issues']}), 'PART_BELOW_MIN_SIZE' in {i['code'] for i in pkg['blocking_issues']})
    try:
        _design([_rect('K', 100, 100)], kerf=7.0)
        add('NS-04', 'Excessive kerf (7 mm)', 'schema error', 'accepted', False)
    except SchemaError as e:
        add('NS-04', 'Excessive kerf (7 mm)', 'schema error', str(e), True)
    pkg = production_package(_design([_rect('HOLE', 200, 200, features=[{'id': 'h', 'kind': 'hole', 'shape': 'circle',
                                                                          'center': [100, 100], 'diameter': 3}])]), {'compensate_kerf': True})
    add('NS-05', 'Hole smaller than the kerf', 'blocked (FEATURE_SMALLER_THAN_KERF / CUT_PATH_DEGENERATE)',
        sorted({i['code'] for i in pkg['blocking_issues']}), {'FEATURE_SMALLER_THAN_KERF'} & {i['code'] for i in pkg['blocking_issues']})
    d = _design([_rect('LONG', 1300, 200, grain='x'), _rect('TALL', 200, 1300, grain='y')])
    n = nest(d, {})
    rot = {p['id']: p['rotation'] for p in n['placements']}
    add('NS-06', 'Grain restriction: grain must run along the sheet length', 'LONG unrotated, TALL rotated 90°', rot,
        rot == {'LONG': 0.0, 'TALL': 90.0})
    n = nest(_design([_rect('G', 1300, 200, grain_locked=True), _rect('G2', 200, 1300, grain_locked=True)]), {})
    add('NS-07', 'Rotation forbidden (grain_locked) and part only fits rotated', 'G placed, G2 PART_EXCEEDS_SHEET',
        {'placed': [p['id'] for p in n['placements']], 'unplaced': [u['code'] for u in n['unplaced']]},
        [p['id'] for p in n['placements']] == ['G'] and [u['code'] for u in n['unplaced']] == ['PART_EXCEEDS_SHEET'])
    d = _design([_rect('T18', 500, 400), _rect('T6', 500, 400, t=6)])
    n = nest(d, {})
    stocks = {p['id']: p['sheet'] for p in n['placements']}
    add('NS-08', 'Different thicknesses never share a sheet', 'two sheets', {'sheets': n['sheet_count'], 'placement': stocks},
        n['sheet_count'] == 2 and stocks['T18'] != stocks['T6'])
    d = _design([_rect(f'P{i}', 400, 300) for i in range(12)])
    pkg = production_package(d, {'compensate_kerf': True})
    lines = pkg['cut_list']['lines']
    add('NS-09', 'Repeated components (12 identical parts)', 'one cut-list line x12, all placed, no overlaps',
        {'lines': [(l['part'], l['quantity']) for l in lines], 'placed': len(pkg['nesting']['placements']),
         'nest_issues': [i['code'] for i in pkg['nesting']['issues']]},
        len(lines) == 1 and lines[0]['quantity'] == 12 and len(pkg['nesting']['placements']) == 12 and not pkg['nesting']['issues'])
    st = pkg['nesting']['stats']
    used = sum(part_area(p) for p in build_plates(d).values())
    add('NS-10', 'Waste arithmetic', 'used = sum of part areas; waste = sheets x area - used',
        {'reported_used': st['used_area'], 'sum_parts': round(used, 1), 'reported_waste': st['waste_area'],
         'recomputed_waste': round(pkg['nesting']['sheet_count'] * 2440 * 1220 - used, 1)},
        abs(st['used_area'] - used) < 0.5 and abs(st['waste_area'] - (pkg['nesting']['sheet_count'] * 2440 * 1220 - used)) < 1)
    n = nest(_design([_rect(f'Q{i}', 1500, 1100) for i in range(3)]), {})
    add('NS-11', 'Impossible to share a sheet (3 parts each > half a sheet)', 'one sheet per part', {'sheets': n['sheet_count']},
        n['sheet_count'] == 3)
    prof = json.dumps({"format": "board-design/v1", "product": {"name": "irregular"}, "material": {"type": "plywood", "thickness": 18},
                       "connections": [], "boards": [{"id": f"S{i}", "position": [0, 0, 0], "size": [400, 18, 400],
                                                      "profile": {"shape": "regular_polygon", "center": [200, 200], "sides": 6, "diameter": 390}}
                                                     for i in range(1)] + [{"id": "C", "position": [500, 0, 0], "size": [300, 18, 300],
                                                                            "profile": {"shape": "circle", "center": [150, 150], "diameter": 300}}]})
    r = compile_source(prof)
    lay = r['layout']
    add('NS-12', 'Irregular shapes (hexagon, circle)', 'placed on bounding boxes, no overlap, ready',
        {'placed': len(lay['nesting']['placements']), 'issues': [i['code'] for i in lay['nesting']['issues']], 'ready': lay['ready_for_production']},
        len(lay['nesting']['placements']) == 2 and not lay['nesting']['issues'])
    rows.append({'id': 'NS-13', 'case': 'Shared-edge (common-line) cutting', 'expected': 'n/a', 'actual': 'not implemented',
                 'pass': None, 'note': 'parts are always separated by the spacing; no common-line cutting'})
    rows.append({'id': 'NS-14', 'case': 'True-shape nesting', 'expected': 'n/a', 'actual': 'not implemented',
                 'pass': None, 'note': 'bounding-box MaxRects, 0/90 degrees only'})
    return {'cases': rows, 'summary': {'pass': sum(r['pass'] is True for r in rows), 'fail': sum(r['pass'] is False for r in rows),
                                       'not_implemented': sum(r['pass'] is None for r in rows)}}


if __name__ == '__main__':
    print(json.dumps(run(), indent=1, default=str))
