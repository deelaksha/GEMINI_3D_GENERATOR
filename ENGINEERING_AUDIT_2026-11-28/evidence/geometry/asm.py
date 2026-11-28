import sys, os, json
sys.path.insert(0, os.getcwd())
from board_engine.canvas import compile_source
for p in sys.argv[1:]:
    r = compile_source(open(p).read(), run_production=True)
    print('==', os.path.basename(p), 'ok', r['ok'])
    for d in r['diagnostics']:
        if d['severity'] in ('error', 'warning'): print('  ', d['severity'], d['code'], d['message'][:220])
    m = r.get('manufacturing') or {}
    a = m.get('assembly')
    print('  assembly keys', list(a.keys()) if isinstance(a, dict) else type(a))
    if isinstance(a, dict):
        print('  ', json.dumps(a)[:900])
    lay = r.get('layout') or {}
    print('  ready', lay.get('ready_for_production'), 'blocking', [b.get('code') for b in lay.get('blocking_issues', [])][:10])
