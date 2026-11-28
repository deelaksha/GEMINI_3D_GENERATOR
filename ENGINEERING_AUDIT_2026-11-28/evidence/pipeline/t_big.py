import json, sys, time, resource
sys.path.insert(0,'.')
from board_engine.canvas import compile_source, parse_source, pretty_json
S=sys.argv[1]
D=json.load(open(S+'/example.json'))
# 10 MB: pad description (valid design)
d=dict(D); d['product']=dict(D['product'], description='x'*10_000_000)
src=pretty_json(d); t=time.time(); r=compile_source(src, run_production=False, time_budget=30)
print(f'10MB padded valid design: ok={r["ok"]} t={time.time()-t:.2f}s len={len(src)/1e6:.1f}MB desc stored len={len(r["design"].get("description",""))if r.get("design") else None}')
# ~4.9MB malformed (truncated) -> auto-repair runs before any time budget
h=json.load(open('board_engine/examples/my_home.json'))
s=pretty_json(h)
reps=int(4_900_000/len(s))
big='{"format":"board-design/v1","material":{"thickness":3},"boards":[' + ','.join([json.dumps(b) for _ in range(reps) for b in h['boards']])
big=big[:4_900_000]
for n in (1_000_000, 2_000_000, 4_900_000):
    t=time.time(); out=parse_source(big[:n]); dt=time.time()-t
    print(f'truncated malformed {n/1e6:.1f}MB: parse_source (incl. repair attempt) t={dt:.2f}s codes={[x["code"] for x in out[3]]} fix={bool(out[3][0].get("fixes"))}')
big2=big[:5_100_000] if len(big)>5_100_000 else big+' '*(5_100_000-len(big))
t=time.time(); out=parse_source(big2); print(f'5.1MB malformed: t={time.time()-t:.2f}s fix={bool(out[3][0].get("fixes"))}')
print('peak RSS MB', resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
