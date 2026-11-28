import sys, os, json, copy
sys.path.insert(0, os.getcwd())
from board_engine.canvas import compile_source
S = sys.argv[1]
r = compile_source(open(f'{S}/cases/T01_baseline_tabslot.json').read(), run_production=False)
d = copy.deepcopy(r['design'])
print('joints in', [(j['id'], j['status']) for j in d['joints']])
for name, dy in (('N_native_ok', 0), ('N_native_joined_gap5', 5), ('N_native_joined_far', 300)):
    dd = copy.deepcopy(d)
    for c in dd['components']:
        if c['id'] == 'WALL':
            c['placement']['position'][1] += dy
    json.dump(dd, open(f'{S}/cases/{name}.json', 'w'))
    rr = compile_source(json.dumps(dd), run_production=False)
    print('==', name, 'ok=', rr['ok'])
    for x in rr['diagnostics']:
        print('  ', x['severity'], x['code'], x['message'][:200])
    print('  joints out', [(j['id'], j.get('status')) for j in (rr.get('design') or {}).get('joints', [])])
