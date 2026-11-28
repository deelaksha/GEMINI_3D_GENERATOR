from lib import *
boards = [{'id': 'BASE', 'position': [0, 0, 0], 'size': [420, 320, 6]},
          {'id': 'CRANK', 'position': [70, 120, 6], 'size': [60, 60, 6], 'profile': {'shape': 'circle', 'center': [30, 30], 'diameter': 60}},
          {'id': 'ARM', 'position': [290, 70, 6], 'size': [20, 90, 6]},
          {'id': 'ROD', 'position': [110, 142, 12], 'size': [200, 16, 6]},
          {'id': 'POST', 'position': [150, 144, 6], 'size': [100, 6, 6], 'normal': 'y'}]
motions = [rot('crank', ['CRANK'], [100, 150, 6], axis='z'),
           rot('rocker', ['ARM'], [300, 80, 6], axis='z', driver='crank',
               link={'rod': 'ROD', 'from': [120, 150, 12], 'to': [300, 150, 12]})]
conns = [{'type': 'tab_slot', 'board': 'POST', 'into': 'BASE'}, {'type': 'tab_slot', 'board': 'POST', 'into': 'ROD'}]
r, _ = run('s08b_rod_tabbed_to_static_post', design(boards, motions, conns))
print('  joints:', [(j['type'], j['a'], j['b'], j.get('status')) for j in r['design']['joints']])
r, _ = run('s08c_same_without_post_joint', design(boards, motions, conns[:1]))
