import json, sys, time, glob, os
sys.path.insert(0, '.')
from board_engine import canvas as C
from board_engine.canvas_prompt import EXAMPLE, COMPLEX_EXAMPLE, STRUCTURES_EXAMPLE
items = [('prompt:EXAMPLE', json.dumps(EXAMPLE)), ('prompt:COMPLEX_EXAMPLE', json.dumps(COMPLEX_EXAMPLE)),
         ('prompt:STRUCTURES_EXAMPLE', json.dumps(STRUCTURES_EXAMPLE))]
for p in sorted(glob.glob('board_engine/examples/*.json') + glob.glob('tests/python/fixtures/*.json')
                + glob.glob('PROJECT_AUDIT/END_TO_END_VALIDATION/ai_runs/out_*/*.json')):
    items.append((p, open(p).read()))
for name, src in items:
    t = time.perf_counter()
    try:
        r = C.compile_source(src, run_production=True, time_budget=120)
    except Exception as e:
        print(json.dumps({'name': name, 'crash': repr(e)})); continue
    dt = time.perf_counter() - t
    sev = {}
    codes = {}
    for d in r['diagnostics']:
        sev[d['severity']] = sev.get(d['severity'], 0) + 1
        if d['severity'] == 'error': codes[d['code']] = codes.get(d['code'], 0) + 1
    lay = r.get('layout') or {}
    print(json.dumps({'name': name, 'ok': r['ok'], 'boards': (r.get('summary') or {}).get('boards'),
                      'joints': (r.get('summary') or {}).get('joints'), 'sev': sev, 'error_codes': codes,
                      'blocking': len(lay.get('blocking_issues') or []), 'sheets': (lay.get('nesting') or {}).get('sheet_count') if isinstance(lay.get('nesting'), dict) else lay.get('sheet_count'),
                      'ready': lay.get('ready_for_production'), 's': round(dt, 2)}))
