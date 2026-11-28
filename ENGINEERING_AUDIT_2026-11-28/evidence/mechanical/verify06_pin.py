from lib import *
from board_engine import geometry as G
from board_engine.motion import train_values, board_poses, _at
import json
d = json.load(open('json/s06_butterfly_two_rods.json'))
r = canvas.compile_source(json.dumps(d), run_production=False)
ms = r['design']['motions']
rodR = next(b for b in d['boards'] if b['id'] == 'ROD-R')
pts0 = [[rodR['position'][0] + u, rodR['position'][1] + v, 15.0] for u, v in rodR['profile']['points']]
hits = []
for a in range(0, 360):
    vals = train_values(ms, 'crank', float(a)); poses = board_poses(ms, vals)
    poly = [_at(poses['ROD-R'][1], p)[:2] for p in pts0]
    pinL = _at(poses['CRANK'][1], [280, 150, 9])[:2]            # ROD-L's crank pin, it spans z 6..24 through ROD-R's layer
    inside = G.point_in_polygon(pinL, poly)
    dist = G.dist_to_boundary(pinL, poly)
    if inside or dist < 2.0:
        hits.append((a, round(dist, 1), inside))
print('crank angles where the 4 mm ROD-L crank pin passes through ROD-R (layer z 12..18):', hits[:3], '...', hits[-3:] if hits else '', 'count', len(hits))
print('MOTION_COLLISION reported:', [x['message'][:120] for x in r['diagnostics'] if x['code'] == 'MOTION_COLLISION'])
