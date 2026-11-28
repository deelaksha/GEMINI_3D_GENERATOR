import json, sys, time, cProfile, pstats
sys.path.insert(0,'.')
from board_engine.canvas import compile_source
src=json.dumps({'format':'board-design/v1','material':{'thickness':3},'boards':[{'id':'P','position':[0,0,0],'size':[10,3,10],'repeat':{'count':100,'step':[20,0,0],'rows':{'count':40,'step':[0,0,20]}}}],'connections':[]})
pr=cProfile.Profile(); t=time.time(); pr.enable(); r=compile_source(src, run_production=False, time_budget=0.2); pr.disable()
print(f'4000 boards, budget 0.2s (scaled to {0.2*4000/900:.2f}s): elapsed {time.time()-t:.1f}s ok={r["ok"]} codes={sorted({d["code"] for d in r["diagnostics"]})[:8]}')
pstats.Stats(pr).sort_stats('cumulative').print_stats(25)
