import json, sys, os, glob, collections
sys.path.insert(0, os.getcwd())
from board_engine.canvas import compile_source, find_non_integer_dimensions
from board_engine import canvas_prompt as cp
rod = {"boards":[{"id": "ROD", "position": [106, 137, 12], "size": [208, 96, 6], "profile": {"shape": "polygon", "points": [[7.6, 1.9], [206.2, 79.2], [200.4, 94.1], [1.8, 16.8]]}}]}
print('ROD snippet non-integer issues:', len(find_non_integer_dimensions(rod)))
def summ(name, text):
    r = compile_source(text, run_production=False)
    d = r['diagnostics']
    e = collections.Counter(x['code'] for x in d if x['severity']=='error')
    w = collections.Counter(x['code'] for x in d if x['severity']=='warning')
    try:
        j = json.loads(text); nb = len(j.get('boards',[])); nc = len(j.get('connections',[])) if isinstance(j.get('connections'),list) else j.get('connections'); plan = 'plan' in j
        keys = sorted(j.keys())
    except Exception as ex:
        nb=nc=plan=keys=f'parse:{ex}'
    print(f"{name}: boards={nb} conns={nc} plan={plan} errors={sum(e.values())} warnings={sum(w.values())}")
    print('   E:', dict(e)); print('   W:', dict(w))
for k in ('EXAMPLE','COMPLEX_EXAMPLE','STRUCTURES_EXAMPLE','ADVANCED_EXAMPLE'):
    summ('prompt.'+k, json.dumps(getattr(cp,k)))
for f in sorted(glob.glob('PROJECT_AUDIT/END_TO_END_VALIDATION/ai_runs/out_*/*.json')):
    summ(f.split('ai_runs/')[1], open(f).read())
