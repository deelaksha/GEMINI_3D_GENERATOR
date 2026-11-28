import json, copy, time, sys, re
sys.path.insert(0,'.')
from board_engine.canvas import compile_source, pretty_json
S=sys.argv[1]
D=json.load(open(S+'/example.json'))
def run(name, src, prod=False, budget=60, show=8):
    t=time.time(); r=compile_source(src, run_production=prod, time_budget=budget); dt=time.time()-t
    n=len(r['design']['components']) if r.get('design') else None
    print(f"\n## {name}: ok={r['ok']} boards={n} t={dt:.2f}s len={len(src) if isinstance(src,str) else None}")
    seen=set()
    for d in r['diagnostics']:
        if d['severity'] in('error','warning') and d['code'] not in seen:
            seen.add(d['code']); 
            if len(seen)<=show: print('   ',d['severity'],d['code'],'|',d['message'][:150])
    return r
# unknown in motion with valid motion
d=copy.deepcopy(D); d['motions']=[{'id':'m1','type':'slide','boards':['SHELF'],'on':'LEG-L','direction':'z','range':[0,50],'springs':3,'damping':'soft'}]
d['color_scheme']='walnut'; d['boards'][0]['bevel_angle']=45; d['connections'][0]['hinge_type']='piano'; d['material']['grain_finish']='oiled'
r=run('unknown fields (top/board/conn/motion/material)', pretty_json(d))
print('   ALL codes:', sorted({x['code'] for x in r['diagnostics']}))
print('   any mention of unknown keys:', [x['code'] for x in r['diagnostics'] if re.search('springs|bevel|hinge_type|color_scheme|grain_finish|damping', x['message'])])
# misspelled known key
d=copy.deepcopy(D); d['boards'][1]['openings'][0]['diamter']=d['boards'][1]['openings'][0].pop('diameter'); run('misspelled key "diamter"', pretty_json(d))
d=copy.deepcopy(D); d['conections']=d.pop('connections'); r=run('misspelled "conections" (falls back to auto)', pretty_json(d))
print('   codes:', sorted({x['code'] for x in r['diagnostics']}))
# truncated at a board boundary: drop last 2 boards and all connections
src=pretty_json(D)
i=src.index('    {\n      "id": "MODESTY"')
cut=src[:i]
r=run('truncated after board 3 (incl trailing comma)', cut)
fx=[f for x in r['diagnostics'] for f in (x.get('fixes') or []) if f.get('kind')=='repair_json']
if fx:
    print('   repair summary:', fx[0]['summary'], 'safe=',fx[0]['safe'])
    r2=run('  -> repaired', fx[0]['source'])
    print('   codes:', sorted({x['code'] for x in r2['diagnostics']}))
    open(S+'/truncated_repaired.json','w').write(fx[0]['source'])
open(S+'/truncated.json','w').write(cut)
# 100k boards via repeat
d=copy.deepcopy(D); d['boards'].append({'id':'SLAT','position':[100,200,100],'size':[10,18,10],'repeat':{'count':100,'step':[11,0,0],'rows':{'count':100,'step':[0,0,11]},'layers':{'count':10,'step':[0,20,0]}}})
run('repeat 100x100x10=100000', pretty_json(d), budget=20)
d['boards'][-1]['repeat']['layers']['count']=11
run('repeat 110000', pretty_json(d), budget=20)
d['boards'][-1]['repeat']={'count':100,'step':[11,0,0],'rows':{'count':30,'step':[0,0,11]}}
run('repeat 3000 small slats (budget 20s)', pretty_json(d), budget=20)
