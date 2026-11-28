from lib import *
from helpers import phased
from board_engine.motion import train_values

# 6. butterfly: one crank (axis z) at centre, two wings (rockers) each pushed by its own rod
c = (300, 150)
boards = [{'id': 'BASE', 'position': [0, 0, 0], 'size': [600, 320, 6]},
          {'id': 'CRANK', 'position': [270, 120, 6], 'size': [60, 60, 6], 'profile': {'shape': 'circle', 'center': [30, 30], 'diameter': 60}},
          {'id': 'WING-R', 'position': [490, 140, 6], 'size': [20, 90, 6]},
          {'id': 'WING-L', 'position': [90, 140, 6], 'size': [20, 90, 6]},
          bar('ROD-R', (320, 150), (500, 220), 12), bar('ROD-L', (280, 150), (100, 220), 18)]
motions = [rot('crank', ['CRANK'], [300, 150, 6], axis='z'),
           rot('wr', ['WING-R'], [500, 150, 6], axis='z', driver='crank',
               link={'rod': 'ROD-R', 'from': [320, 150, 12], 'to': [500, 220, 12]}),
           rot('wl', ['WING-L'], [100, 150, 6], axis='z', driver='crank',
               link={'rod': 'ROD-L', 'from': [280, 150, 18], 'to': [100, 220, 18]})]
r, _ = run('s06_butterfly_two_rods', design(boards, motions))
ms = r['design']['motions']
for a in (0, 45, 90, 180, 270):
    v = train_values(ms, 'crank', float(a))
    print(f'  crank {a:3d}: wr={v["wr"]:+.2f}  wl={v["wl"]:+.2f}  (mirror-sync would be wl == -wr)')

# 7. one hand crank (gear GA, axis y) drives a gear GB AND a rocker through a rod
def xz(b, y):                      # convert an xy bar into an xz-plane board
    return dict(b, position=[b['position'][0], y, b['position'][1]], size=[b['size'][0], 6, b['size'][1]])
BASE = {'id': 'BASE', 'position': [-250, 0, -200], 'size': [500, 6, 400]}
d = design([BASE, gear_xz('GA', 20, 3, 0, 0), gear_xz('GB', 30, 3, 75, 0),
            {'id': 'ARM', 'position': [-160, 6, 20], 'size': [20, 6, 90]},
            xz(bar('ROD', (-15, 0), (-150, 30), 0), 12)],
           [rot('A', ['GA'], [0, 6, 0]), rot('B', ['GB'], [75, 6, 0], driver='A'),
            rot('R', ['ARM'], [-150, 6, 100], driver='A', link={'rod': 'ROD', 'from': [-15, 12, 0], 'to': [-150, 12, 30]})])
d = phased(d)
r, _ = run('s07_one_crank_gear_plus_linkage', d)
ms = r['design']['motions']
for a in (0, 90, 180):
    print(f'  A={a}:', {k: round(v, 2) for k, v in train_values(ms, 'A', float(a)).items()})
