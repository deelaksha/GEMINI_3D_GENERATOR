import sys, os, json, math, itertools
sys.path.insert(0, os.getcwd())
from board_engine.canvas import compile_source, _tilt_points
from board_engine import geometry as G
from board_engine.model import build_plates
d = json.load(open(sys.argv[1]))
r = compile_source(json.dumps(d), run_production=False)
comps = {c['id']: c for c in r['design']['components']}
plates = build_plates(r['design'])
worst = 0
for b in d['boards']:
    c = comps[b['id']]; f = G.Frame(c['placement']['position'], c['placement']['rotation'])
    lo = b['position']; hi = [lo[i] + b['size'][i] for i in range(3)]
    box = [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    exp, _ = _tilt_points(b.get('rotate'), box, [(lo[i]+hi[i])/2 for i in range(3)]) if b.get('rotate') else (box, None)
    t = c['thickness']
    got = [f.to_world([x, y, s]) for x, y in c['outline'] for s in (-t/2, t/2)]
    # each expected corner should match some got corner (for rect boards)
    if not b.get('profile'):
        err = max(min(math.dist(e, g) for g in got) for e in exp)
    else:
        # profile: check got points inside expected tilted AABB hull: use inverse tilt not needed; compare AABBs
        def bb(ps): return [min(p[i] for p in ps) for i in range(3)], [max(p[i] for p in ps) for i in range(3)]
        err = None
    # model3d matrix vs frame
    worst = max(worst, err or 0)
    det = None
    R = G.rotation_matrix(c['placement']['rotation'])
    det = (R[0][0]*(R[1][1]*R[2][2]-R[1][2]*R[2][1]) - R[0][1]*(R[1][0]*R[2][2]-R[1][2]*R[2][0]) + R[0][2]*(R[1][0]*R[2][1]-R[1][1]*R[2][0]))
    print(b['id'], 'rot', c['placement']['rotation'], 'corner_err', None if err is None else round(err, 6), 'det', round(det, 6), 'area_sign', round(G.signed_area(c['outline']), 1))
m3 = r.get('model3d') or {}
print('model3d keys', list(m3.keys())[:10])
if m3.get('meshes') or m3.get('components') or m3.get('parts'):
    k = next(k for k in ('meshes', 'components', 'parts') if m3.get(k))
    print('model3d sample', json.dumps(m3[k][0])[:600])
print('WORST', worst)
