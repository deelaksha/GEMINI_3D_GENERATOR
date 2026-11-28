import json, copy, time, sys, math
sys.path.insert(0, '/home/sonic-claude2/deelaksha/desighn/GEMINI_3D_GENERATOR')
from board_engine.canvas import compile_source, pretty_json
D = json.load(open('/tmp/claude-1002/-home-sonic-claude2-mythra/9b0b6ca6-d98e-48cf-ab1a-7d0386cce3f4/scratchpad/pipe_audit/example.json'))
def run(name, src, prod=False, budget=60):
    t=time.time()
    r = compile_source(src, run_production=prod, time_budget=budget)
    dt=time.time()-t
    codes = {}
    for d in r['diagnostics']:
        if d['severity'] in ('error','warning'): codes.setdefault(d['code'], d['message'][:140])
    n = len(r['design']['components']) if r.get('design') else None
    print(f"\n## {name}: ok={r['ok']} boards={n} t={dt:.2f}s")
    for k,v in list(codes.items())[:8]: print('   ', k, '|', v)
    return r
base = run('baseline', pretty_json(D))
# unknown fields
d = copy.deepcopy(D); d['color_scheme']='walnut'; d['boards'][0]['bevel_angle']=45; d['connections'][0]['hinge_type']='piano'
d['motions']=[{'id':'m1','boards':['SHELF'],'on':'LEG-L','type':'slide','axis':'z','travel':100,'springs':3}]
r=run('unknown fields', pretty_json(d))
print('   all codes:', sorted({x['code'] for x in r['diagnostics']}))
d = copy.deepcopy(D); d['format']='board-design/v2'; run('format v2', pretty_json(d))
d = copy.deepcopy(D); d['format']='totally-other/v9'; run('format other', pretty_json(d))
d = copy.deepcopy(D); d['boards'][1]['id']='TOP'; run('dup id', pretty_json(d))
d = copy.deepcopy(D); d['boards'][1]['id']='bad id!'; run('invalid id', pretty_json(d))
d = copy.deepcopy(D); d['boards'][1]['size']=['18','732','560']; run('string sizes', pretty_json(d))
s = pretty_json(D).replace('"size": [1200, 18, 600]','"size": [NaN, 18, 600]'); run('NaN size', s)
s = pretty_json(D).replace('"size": [1200, 18, 600]','"size": [Infinity, 18, 600]'); run('Infinity size', s)
d = copy.deepcopy(D); d['boards'][4]['size']=[-1064,18,400]; run('negative size', pretty_json(d))
d = copy.deepcopy(D); d['boards'][4]['position']=[6000,150,60]; run('coord 6000', pretty_json(d))
d = copy.deepcopy(D); d['boards'][4]['position']=[4900,150,60]; d['boards'][4]['size']=[4900,18,400]; run('pos+size 9800 (each <5000)', pretty_json(d))
d = copy.deepcopy(D); d['boards'][0]['size']=[1200,18,600]; d['boards'][0]['id']='TOP'; d['boards'][0]['position']=[0,732,0]; d['boards'][0]['name']='x'*100000; run('100k-char name', pretty_json(d))
s = '['*100000 + ']'*100000; run('deep nesting array', s)
s = '{"a":'*50000 + '1' + '}'*50000; run('deep nesting obj', s)
src = pretty_json(D)
for frac in (0.5, 0.8, 0.95):
    cut = src[:int(len(src)*frac)]
    r = run(f'truncated {frac}', cut)
    fx = [f for x in r['diagnostics'] for f in (x.get('fixes') or []) if f.get('kind')=='repair_json']
    if fx:
        r2 = run(f'  -> after applying repair_json fix (safe={fx[0]["safe"]})', fx[0]['source'])
s = src.replace('"format": "board-design/v1",', '"format": "board-design/v1", // comment\n /* block */').replace('"tabs": 2\n', '"tabs": 2,\n')
run('comments+trailing commas', s)
run('prose+fence', 'Here is your design:\n```json\n'+src+'\n```\nEnjoy!')
