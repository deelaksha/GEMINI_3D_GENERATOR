import json, sys, os
sys.path.insert(0, os.getcwd())
from board_engine import canvas_prompt as cp
from board_engine.canvas import compile_source
OUT = sys.argv[1]
res = {}
def save(name, text):
    open(f'{OUT}/{name}.txt', 'w').write(text)
    res[name] = (len(text), len(text)//4)
save('spec_markdown', cp.spec_markdown())
save('build_prompt_aeroplane', cp.build_prompt('Aeroplane', '', None, None, 'interlocking', None, False))
save('build_prompt_aeroplane_images', cp.build_prompt('Aeroplane', '', None, None, 'interlocking', None, True))
save('build_prompt_machine', cp.build_prompt('Aeroplane', '', None, None, 'interlocking', {'kerf':0.2,'sheet':{'width':600,'height':400}}, False))
# broken design: use COMPLEX_EXAMPLE with a board moved
src = json.loads(json.dumps(cp.COMPLEX_EXAMPLE))
src['boards'][1]['position'][0] += 37
s_small = json.dumps(src, indent=1)
r = compile_source(s_small, run_production=False)
diags = r.get('diagnostics', []) if isinstance(r, dict) else r.diagnostics
print('broken small diag count', len(diags), sum(1 for d in diags if d.get('severity')=='error'))
save('repair_small', cp.build_repair_prompt(s_small, diags))
save('update_small', cp.build_update_prompt(s_small, 'Make it 100 mm wider'))
save('integer_fix_small', cp.build_integer_fix_prompt(s_small, [{'board':'X','field':'size','value':7.6,'suggested':8}]))
# big design: largest ai_runs output
big = open('PROJECT_AUDIT/END_TO_END_VALIDATION/ai_runs/out_new/B.json').read()
rb = compile_source(big, run_production=False)
save('repair_big', cp.build_repair_prompt(big, rb['diagnostics']))
save('update_big', cp.build_update_prompt(big, 'add a roof'))
res['_src_small_chars']=len(s_small); res['_src_big_chars']=len(big)
for k,v in res.items(): print(k, v)
json.dump(res, open(f'{OUT}/sizes.json','w'), indent=1)
