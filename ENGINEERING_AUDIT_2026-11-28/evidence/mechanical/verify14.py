from lib import *
from board_engine import motion as M
from board_engine.model import build_plates
from board_engine.validation import plate_interference
import json
for name, mid, vals in (('s14a_tunnel_thin_arm', 'sw', [0, 1, 2, 2.5, 3, 4, 5]), ('s14b_tunnel_fast_driven', 'fast', [0, 20, 25, 30, 50])):
    d = json.load(open(f'json/{name}.json'))
    r = canvas.compile_source(json.dumps(d), run_production=False)
    des = r['design']; plates = build_plates(des)
    comps = {c['id']: c for c in des['components']}
    m = next(x for x in des['motions'] if x['id'] == mid)
    print(name, 'samples used:', M._samples(m)[0], 'deg step')
    for v in vals:
        p = M._moved(des, comps['ARM'], m, v)
        hits = plate_interference(p, plates['POST'])
        print(f'   ARM at {v:5}: interference with POST = {[(h["kind"], h.get("length", h.get("area"))) for h in hits]}')
