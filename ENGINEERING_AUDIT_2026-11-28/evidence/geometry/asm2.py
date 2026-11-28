import sys, os, json
sys.path.insert(0, os.getcwd())
from board_engine.canvas import compile_source
from board_engine.manufacturing import manufacturing_report
for p in sys.argv[1:]:
    r = compile_source(open(p).read(), run_production=True)
    lay = r.get('layout') or {}
    print('==', os.path.basename(p), 'ok', r['ok'], 'ready', lay.get('ready_for_production'), 'blocking', [b.get('code') for b in lay.get('blocking_issues', [])][:8])
    print('   compile manufacturing keys:', list((r.get('manufacturing') or {}).keys()))
    print('   diag codes:', sorted({d['code'] for d in r['diagnostics']}))
    m = manufacturing_report(r['design'], compensate_kerf=True)
    print('   plan:', json.dumps(m['assembly_plan'])[:700])
    print('   asm issues:', [(i['code'], i['message'][:150]) for i in m['issues'] if 'ASSEMBL' in i['code'] or 'ACCESS' in i['code'] or 'LOCK' in i['code']])
