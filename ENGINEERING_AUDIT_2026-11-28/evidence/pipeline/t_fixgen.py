import json, sys, copy
sys.path.insert(0,'.')
from board_engine.canvas import compile_source, pretty_json, apply_code_fix, CompileError
S=sys.argv[1]; D=json.load(open(S+'/example.json'))
def fixes_of(src):
    r=compile_source(src, run_production=False)
    return r, [(d['code'], f) for d in r['diagnostics'] for f in (d.get('fixes') or [])]
# (1) plain board 1 mm off -> fixes and apply
d=copy.deepcopy(D); d['boards'][4]['position'][0]=69  # SHELF 1mm gap at LEG-L
r,fx=fixes_of(pretty_json(d)); print('plain 1mm gap: ok',r['ok'], [(c,f['id'],f['safe'],[e.get('board') for e in f.get('edits',[])]) for c,f in fx][:6])
# (2) repeated shelf 1 mm off
d=copy.deepcopy(D); d['boards'][4]['position'][0]=69; d['boards'][4]['repeat']={'count':2,'step':[0,200,0]}
open(S+'/fix_repeat.json','w').write(pretty_json(d))
r,fx=fixes_of(pretty_json(d)); print('repeat 1mm gap: ok',r['ok'], [(c,f['id'],f['safe'],[e.get('board') for e in f.get('edits',[])]) for c,f in fx][:6])
for c,f in fx:
    if f.get('edits') and any(e.get('board') for e in f['edits']):
        try: apply_code_fix(pretty_json(d), f); print('  applied', f['id'])
        except (CompileError, KeyError) as e: print('  apply_code_fix FAILED', f['id'], type(e).__name__, e)
# (3) safe consolidation fix on consolidate:false
