from lib import *
from board_engine.motion import train_values
boards = [{'id': 'BASE', 'position': [0, 0, 0], 'size': [420, 320, 6]},
          {'id': 'CRANK', 'position': [70, 120, 6], 'size': [60, 60, 6], 'profile': {'shape': 'circle', 'center': [30, 30], 'diameter': 60}},
          {'id': 'ARM', 'position': [270, 120, 6], 'size': [60, 60, 6], 'profile': {'shape': 'circle', 'center': [30, 30], 'diameter': 60}},
          bar('ROD', (120, 150), (320, 150), 12)]
mo = [rot('crank', ['CRANK'], [100, 150, 6], axis='z'),
      rot('arm', ['ARM'], [300, 150, 6], axis='z', driver='crank', link={'rod': 'ROD', 'from': [120, 150, 12], 'to': [320, 150, 12]})]
r, _ = run('s05c_parallelogram_change_point', design(boards, mo))
ms = r['design']['motions']
print('  crank -> arm (a parallelogram coupling should give arm == crank):',
      [(a, round(train_values(ms, 'crank', float(a))['arm'], 1)) for a in (0, 90, 170, 180, 190, 270, 350)])
t = next(m for m in ms if m['id'] == 'arm')['link']['table']
print('  table samples:', [row for row in t if row[0] in (0, 90, 178, 180, 182, 270, 358, 360)])
