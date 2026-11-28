import json, sys, time, resource
sys.path.insert(0,'.')
from board_engine.canvas import compile_source, pretty_json
src=json.dumps({'format':'board-design/v1','material':{'thickness':3},'boards':[{'id':'P','position':[0,0,0],'size':[10,3,10],'repeat':{'count':200,'step':[20,0,0],'rows':{'count':100,'step':[0,0,20]}}}],'connections':[]})
open(sys.argv[1]+'/dos_20k.json','w').write(src)
t=time.time(); r=compile_source(src, run_production=False, time_budget=1.0); dt=time.time()-t
print(f'request size {len(src)} bytes -> 20000 boards; time_budget=1s given, elapsed {dt:.1f}s, ok={r["ok"]}, codes={sorted({d["code"] for d in r["diagnostics"]})[:6]}')
print('peak RSS MB', round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024))
print('with default BOARD_TIME_BUDGET=90 the same request would be allowed min(900, 90*20000/900)=', min(900, 90*20000/900),'s')
