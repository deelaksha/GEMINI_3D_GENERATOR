from lib import *

# 1. wheel on a wall, axis x, axle
wall = {'id': 'WALL', 'position': [0, 0, 0], 'size': [6, 200, 200]}
wheel = {'id': 'WHEEL', 'position': [6, 60, 60], 'size': [6, 80, 80], 'profile': {'shape': 'circle', 'center': [40, 40], 'diameter': 80}}
r, _ = run('s01_wheel_axis_x', design([wall, wheel], [rot('spin', ['WHEEL'], [6, 100, 100], axis='x', on='WALL')]))
hole = [o for b in r['design']['components'] for o in (b.get('features') or []) if 'axle' in str(o)]
print('  axle features:', len(hole))

BASE = {'id': 'BASE', 'position': [-200, 0, -200], 'size': [600, 6, 600]}
# 2a correct pair (phase 0 -> let compiler tell phase)
d = design([BASE, gear_xz('G1', 20, 3, 0, 0), gear_xz('G2', 30, 3, 75, 0)],
           [rot('drive', ['G1'], [0, 6, 0]), rot('follow', ['G2'], [75, 6, 0], driver='drive')])
run('s02a_gears_ok_phase0', d)
# fix phase from the GEAR_PHASE fix value
import re
r, _ = run('s02a_gears_ok_phase0_again', d, codes_only=True)
ph = [x for x in r['diagnostics'] if x['code'] == 'GEAR_PHASE']
if ph:
    want = float(re.search(r'to ([\d.\-]+) degrees', ph[0]['message']).group(1))
    d2 = copy.deepcopy(d); d2['boards'][2]['profile']['rotation'] = want
    run('s02b_gears_ok_phased', d2)
# 2c wrong centre distance
d3 = copy.deepcopy(d); d3['boards'][2] = gear_xz('G2', 30, 3, 80, 0); d3['motions'][1]['pivot'] = [80, 6, 0]
run('s02c_gears_wrong_distance', d3)
# 2d mismatched module (distance correct for m=3 / m=2.5 average? use need for G2 m2.5: centre 3*20/2+2.5*30/2 = 67.5)
d4 = copy.deepcopy(d); d4['boards'][2] = gear_xz('G2', 30, 2.5, 67.5, 0); d4['motions'][1]['pivot'] = [67.5, 6, 0]
run('s02d_gears_mismatched_module', d4)
# 2e different planes: G2 stacked on a spacer at y=20
d5 = copy.deepcopy(d); d5['boards'][2] = gear_xz('G2', 30, 3, 75, 0, y=12)
d5['boards'].append({'id': 'SPACER', 'position': [60, 6, -15], 'size': [30, 6, 30]})
d5['motions'][1]['pivot'] = [75, 12, 0]; d5['motions'][1]['on'] = 'SPACER'
run('s02e_gears_different_planes', d5)
# 2f gear driven via explicit ratio (wrong ratio vs teeth) -> any check?
d6 = copy.deepcopy(d2 if ph else d); d6['motions'][1]['ratio'] = 5.0
run('s02f_gears_with_wrong_explicit_ratio', d6)
