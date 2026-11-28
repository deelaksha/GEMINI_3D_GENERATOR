from lib import *
from board_engine import motion as M
from board_engine.model import build_plates
from board_engine.validation import plate_interference
import json, sys
def sweep(name, d):
    r = canvas.compile_source(json.dumps(d), run_production=False)
    errs = [x['code'] for x in r['diagnostics'] if x['severity'] == 'error']
    des = r['design']; comps = {c['id']: c for c in des['components']}
    ms = des['motions']; root = next(m for m in ms if not m.get('driven_by'))
    bad = []
    for k in range(0, 121):
        v = k * 0.5
        poses = M.board_poses(ms, M.train_values(ms, root['id'], v))
        a = M._placed(des, comps['G1'], poses['G1'][1]); b = M._placed(des, comps['G2'], poses['G2'][1])
        h = plate_interference(a, b)
        if h: bad.append((v, h[0]['kind'], h[0].get('area', h[0].get('length'))))
    print(f'{name}: compile errors={errs}; tooth interference at {len(bad)}/121 positions (0..60 deg, 0.5 step) e.g. {bad[:4]}')
d = json.load(open('json/s02b_gears_ok_phased.json')); sweep('s02b correct pair', d)
d = json.load(open('json/s02g_gears_pressure_angle_mismatch.json')); sweep('s02g PA 20 vs 28', d)
d = json.load(open('json/s02h_gears_6_teeth_pinion.json')); d['boards'][2]['profile']['rotation'] = 6
json.dump(d, open('json/s02h2_gears_6_teeth_phased.json', 'w'), indent=1); sweep('s02h2 6-tooth pinion phased', d)
