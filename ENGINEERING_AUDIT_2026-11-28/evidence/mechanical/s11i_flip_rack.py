from lib import *
from board_engine.motion import train_values, board_poses, _at
import math
# pinion z20 m3 (pitch R 30) at assembly origin, rack above it along +z touching the pitch line, rack slides along x
R = 30.0
pin = gear_xz('PIN', 20, 3, 0, 0)
rack = {'id': 'RACK', 'position': [-100, 6, 33], 'size': [200, 6, 20]}
pl = {'id': 'PL', 'position': [-110, 0, -40], 'size': [220, 6, 100]}
mot = [rot('p', ['PIN'], [0, 6, 0], on='PL', rng=(0, 90)),
       {'id': 'rk', 'type': 'slide', 'boards': ['RACK'], 'on': 'PL', 'direction': 'x', 'driven_by': 'p', 'ratio': R * math.pi / 180}]
insts = [{'assembly': 'M', 'id': 'A', 'offset': [0, 0, 0]},
         {'assembly': 'M', 'id': 'FZ', 'offset': [0, 0, 300], 'flip': 'z'},
         {'assembly': 'M', 'id': 'FX', 'offset': [400, 0, 0], 'flip': 'x'}]
d = {'format': 'board-design/v1', 'product': {'name': 'flip'}, 'material': MAT, 'boards': [], 'connections': [],
     'assemblies': [{'id': 'M', 'boards': [pl, pin, rack], 'connections': [], 'motions': mot}], 'instances': insts}
r, _ = run('s11i_flipped_rack_and_pinion', d, codes_only=True)
ms = r['design']['motions']
by = {m['id']: m for m in ms}
for i in ('A', 'FZ', 'FX'):
    p, k = by[f'{i}-p'], by[f'{i}-rk']
    piv = p['pivot']
    # contact point: pinion pitch point toward the rack centre line
    rk_c = [c for c in r['design']['components'] if c['id'] == f'{i}-RACK'][0]['placement']['position']
    zc = piv[2] + (R if rk_c[2] > piv[2] else -R)
    contact = [piv[0], piv[1], zc]
    v = 1.0 if p['range'][1] > 0 else -1.0                     # one degree inside the allowed range
    vals = train_values(ms, p['id'], v)
    poses = board_poses(ms, vals)
    moved = _at(poses[f'{i}-PIN'][1], contact)
    rack_dx = _at(poses[f'{i}-RACK'][1], [0, 0, 0])[0] - _at(board_poses(ms, {})[f'{i}-RACK'][1], [0, 0, 0])[0]
    print(f'  {i}: pinion range {p["range"]}, axis {p["axis"]}, rack dir {k["direction"]}, ratio {k["ratio"]:.4f}: '
          f'tooth surface dx = {moved[0]-contact[0]:+.3f} mm, rack dx = {rack_dx:+.3f} mm  -> {"OK" if abs(moved[0]-contact[0]-rack_dx) < 0.05 else "SLIPS / WRONG WAY"}')
