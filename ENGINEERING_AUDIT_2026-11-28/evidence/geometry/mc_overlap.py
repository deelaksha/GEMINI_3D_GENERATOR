# independent ground truth: sample points in solid of each plate and test membership in the other (exact outline test)
import sys, os, json, random
sys.path.insert(0, os.getcwd())
from board_engine.canvas import compile_source
from board_engine.model import build_plates
from board_engine import geometry as G
random.seed(1)
for p in sys.argv[1:]:
    r = compile_source(open(p).read(), run_production=False)
    pl = build_plates(r['design']); ids = list(pl)
    a, b = pl[ids[0]], pl[ids[1]]
    x0, y0, x1, y1 = a.bbox2d
    N = 200000; hit = 0
    for _ in range(N):
        q = [random.uniform(x0, x1), random.uniform(y0, y1), random.uniform(-a.t/2*0.98, a.t/2*0.98)]
        if not G.point_in_polygon(q[:2], a.cut): continue
        w = a.frame.to_world(q); l = b.frame.to_local(w)
        if abs(l[2]) < b.t/2*0.98 and G.point_in_polygon(l[:2], b.cut): hit += 1
    vol = (x1-x0)*(y1-y0)*a.t*hit/N
    print(os.path.basename(p), 'overlap volume approx mm3 =', round(vol, 1))
