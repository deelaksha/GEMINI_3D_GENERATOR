"""Support / hanging scenarios for the support analysis (board_engine/support.py). Prints and returns one row per case."""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from board_engine.canvas import compile_source  # noqa: E402
from board_engine.canvas_prompt import EXAMPLE  # noqa: E402

P18 = {"type": "plywood", "thickness": 18}
SHELF = [{"id": "RAIL", "position": [0, 0, 0], "size": [600, 218, 18]},
         {"id": "BRK-L", "position": [100, 0, 18], "size": [18, 200, 200],
          "profile": {"shape": "polygon", "points": [[0, 0], [200, 0], [200, 200], [180, 200]]}},
         {"id": "BRK-R", "position": [482, 0, 18], "size": [18, 200, 200],
          "profile": {"shape": "polygon", "points": [[0, 0], [200, 0], [200, 200], [180, 200]]}},
         {"id": "SHELF", "position": [0, 200, 18], "size": [600, 18, 200]}]
SHELF_C = [{"type": "tab_slot", "board": a, "into": b} for a, b in
           (("BRK-L", "RAIL"), ("BRK-R", "RAIL"), ("BRK-L", "SHELF"), ("BRK-R", "SHELF"), ("SHELF", "RAIL"))]


def _run(boards, conns, mounting=None, joinery=None):
    d = {"format": "board-design/v1", "product": {"name": "s"}, "material": P18, "boards": boards, "connections": conns}
    if mounting:
        d['product']['mounting'] = mounting
    if joinery:
        d['joinery'] = joinery
    r = compile_source(json.dumps(d), run_production=False)
    s = r.get('support') or {}
    return {'compiled': r['ok'], 'errors': sorted({x['code'] for x in r['diagnostics'] if x['severity'] == 'error'}),
            'support_codes': sorted({x['code'] for x in r['diagnostics'] if x['code'] in
                                     ('UNSUPPORTED_COMPONENT', 'RESTING_COMPONENT', 'CANTILEVER', 'TIP_OVER', 'LOW_STABILITY_MARGIN', 'WALL_MOUNTED')}),
            'stable': s.get('stable'), 'margin': s.get('stability_margin'),
            'status': {k: v['status'] for k, v in (s.get('components') or {}).items()}}


def cases():
    ex = copy.deepcopy(EXAMPLE)
    rows = []

    def add(cid, name, expect, res, check, note=''):
        rows.append({'id': cid, 'case': name, 'expected': expect, 'actual': res, 'pass': bool(check(res)), 'note': note})

    add('SP-01', 'Wall-mounted shelf (mounting: wall)', 'WALL_MOUNTED, no tip-over',
        _run(SHELF, SHELF_C, 'wall'), lambda r: 'WALL_MOUNTED' in r['support_codes'] and 'TIP_OVER' not in r['support_codes'])
    add('SP-02', 'Same shelf without "mounting"', 'judged as standing on the floor -> TIP_OVER',
        _run(SHELF, SHELF_C), lambda r: 'TIP_OVER' in r['support_codes'],
        'shows why the mounting field is needed: stood on the floor, the bracket tips cannot hold it')
    cab = [{"id": "BACK", "position": [18, 0, 0], "size": [564, 400, 18]}, {"id": "SIDE-L", "position": [0, 0, 0], "size": [18, 400, 300]},
           {"id": "SIDE-R", "position": [582, 0, 0], "size": [18, 400, 300]}, {"id": "BOT", "position": [18, 20, 18], "size": [564, 18, 282]},
           {"id": "DOOR", "position": [0, 0, 302], "size": [600, 400, 18]}]
    cc = [{"type": "finger", "board": "SIDE-L", "into": "BACK"}, {"type": "finger", "board": "SIDE-R", "into": "BACK"},
          {"type": "tab_slot", "board": "BOT", "into": "SIDE-L"}, {"type": "tab_slot", "board": "BOT", "into": "SIDE-R"},
          {"type": "tab_slot", "board": "BOT", "into": "BACK"}, {"type": "hinge", "board": "DOOR", "into": "SIDE-L", "edge": "-x"}]
    add('SP-03', 'Suspended wall cabinet with a hanging (hinged) door', 'door joined; cabinet wall-anchored',
        _run(cab, cc, 'wall', 'glue_allowed'), lambda r: r['status'].get('DOOR') == 'joined' and r['compiled'])
    drawer = copy.deepcopy(ex)
    drawer['boards'].append({"id": "BOX", "position": [400, 168, 100], "size": [300, 18, 300]})   # rests on the shelf
    r = compile_source(json.dumps(drawer), run_production=False)
    add('SP-04', 'Loose box / drawer standing on a shelf', 'resting (removable), production allowed',
        {'status': r['support']['components']['BOX']['status'], 'compiled': r['ok']}, lambda r: r['status'] == 'resting' and r['compiled'])
    add('SP-05', 'Cantilever: both legs at one end of a 1200 mm top', 'TIP_OVER + CANTILEVER',
        _run([{"id": "TOP", "position": [0, 732, 0], "size": [1200, 18, 600]},
              {"id": "L1", "position": [60, 0, 40], "size": [18, 732, 520]}, {"id": "L2", "position": [260, 0, 40], "size": [18, 732, 520]}],
             [{"type": "tab_slot", "board": "L1", "into": "TOP"}, {"type": "tab_slot", "board": "L2", "into": "TOP"}]),
        lambda r: {'TIP_OVER', 'CANTILEVER'} <= set(r['support_codes']))
    add('SP-06', 'Moderate overhang (top 100 mm past each leg)', 'stable, no warnings',
        _run([{"id": "TOP", "position": [0, 732, 0], "size": [1200, 18, 600]},
              {"id": "L1", "position": [100, 0, 40], "size": [18, 732, 520]}, {"id": "L2", "position": [1082, 0, 40], "size": [18, 732, 520]}],
             [{"type": "tab_slot", "board": "L1", "into": "TOP"}, {"type": "tab_slot", "board": "L2", "into": "TOP"}]),
        lambda r: r['stable'] and not set(r['support_codes']) & {'TIP_OVER', 'CANTILEVER'})
    floating = copy.deepcopy(ex)
    floating['boards'].append({"id": "LOOSE", "position": [300, 300, 60], "size": [400, 18, 280]})
    r = compile_source(json.dumps(floating), run_production=False)
    add('SP-07', 'Unsupported horizontal board in mid-air', 'UNSUPPORTED_COMPONENT error',
        {'errors': sorted({x['code'] for x in r['diagnostics'] if x['severity'] == 'error'})},
        lambda r: 'UNSUPPORTED_COMPONENT' in r['errors'])
    hang = copy.deepcopy(ex)
    hang['boards'].append({"id": "SIGN", "position": [500, 532, 200], "size": [200, 200, 18]})       # hangs under the top
    hang['connections'].append({"id": "SIGN-TOP", "type": "tab_slot", "board": "SIGN", "into": "TOP"})
    r = compile_source(json.dumps(hang), run_production=False)
    add('SP-08', 'Vertical board suspended under the top by tabs only', 'joined (hanging load on tabs not assessed)',
        {'status': r['support']['components']['SIGN']['status'], 'compiled': r['ok']}, lambda r: r['status'] == 'joined',
        'LIMITATION: geometric hold only; whether the tabs carry the hanging load is not calculated')
    over = copy.deepcopy(ex)
    over['boards'].append({"id": "PLANK", "position": [1000, 750, 100], "size": [600, 18, 200]})     # 400 of 600 mm past the top's edge
    r = compile_source(json.dumps(over), run_production=False)
    add('SP-09', 'Plank resting on the top, two thirds hanging over its edge', 'RESTING_OFF_SUPPORT error (it falls off)',
        {'status': r['support']['components']['PLANK']['status'],
         'codes': sorted({x['code'] for x in r['diagnostics'] if x.get('board') == 'PLANK'})},
        lambda r: 'RESTING_OFF_SUPPORT' in r['codes'])
    one = copy.deepcopy(ex)
    one['boards'].append({"id": "HOOK", "position": [590, 600, 300], "size": [18, 132, 80]})       # 80 mm wide hanger under the top
    one['connections'].append({"id": "HOOK-TOP", "type": "tab_slot", "board": "HOOK", "into": "TOP", "tabs": 1})
    r = compile_source(json.dumps(one), run_production=False)
    add('SP-10', 'Component attached at a single small point (one 80 mm hanger, one tab)', 'flagged as weakly attached',
        {'status': (r.get('support') or {}).get('components', {}).get('HOOK', {}).get('status'), 'compiled': r['ok'],
         'codes': sorted({x['code'] for x in r['diagnostics'] if x.get('board') == 'HOOK' and x['severity'] != 'error'}),
         'errors': [x['message'][:160] for x in r['diagnostics'] if x['severity'] == 'error'][:2]},
        lambda r: bool(r['codes']), 'NOT IMPLEMENTED: no single-attachment check; reported as an open gap')
    return rows


if __name__ == '__main__':
    rows = cases()
    print(json.dumps({'cases': rows, 'summary': {'pass': sum(r['pass'] for r in rows), 'total': len(rows)}}, indent=1))
