from lib import *
import helpers as L

# 8b. rod tab_slotted to a static post (rod is in no motion's "boards")
d = L.crank_design('rocker')
d['boards'].append({'id': 'POST', 'position': [200, 175, 6], 'size': [6, 12, 6], 'normal': 'x'})
d['connections'] = [{'type': 'tab_slot', 'board': 'POST', 'into': 'BASE'},
                    {'type': 'tab_slot', 'board': 'POST', 'into': 'ROD'}]
r, _ = run('s08b_rod_tabbed_to_static_post', d)
print('  joints:', [(j['type'], j['a'], j['b'], j.get('status')) for j in r['design']['joints']])

G = {'id': 'BASE', 'position': [-200, 0, -200], 'size': [600, 6, 600]}
# 11a. rack-and-pinion via ratio, rack placed 200 mm away from the pinion (no tooth contact at all)
pin = gear_xz('PIN', 20, 3, 0, 0)
rack = {'id': 'RACK', 'position': [-100, 6, 200], 'size': [200, 6, 20]}
d = design([G, pin, rack], [rot('p', ['PIN'], [0, 6, 0], rng=(0, 180)),
                            {'id': 'rk', 'type': 'slide', 'boards': ['RACK'], 'on': 'BASE', 'direction': 'x',
                             'driven_by': 'p', 'ratio': 0.5236}])
run('s11a_rack_far_from_pinion', d)
# 11b. belt/pulley: two plain disks 300 mm apart with ratio 0.5 and no belt board
P1 = {'id': 'P1', 'position': [-30, 6, -30], 'size': [60, 6, 60], 'profile': {'shape': 'circle', 'center': [30, 30], 'diameter': 60}}
P2 = {'id': 'P2', 'position': [240, 6, -60], 'size': [120, 6, 120], 'profile': {'shape': 'circle', 'center': [60, 60], 'diameter': 120}}
d = design([G, P1, P2], [rot('p1', ['P1'], [0, 6, 0]), rot('p2', ['P2'], [300, 6, 0], driver='p1', ratio=-3.7)])
run('s11b_belt_wrong_ratio_no_belt', d)
# 11c. bevel: G2 stands upright (thin along x) at the edge of G1
G2v = {'id': 'G2', 'position': [36, 6, -33], 'size': [6, 66, 66],
       'profile': {'shape': 'gear', 'center': [33, 33], 'teeth': 20, 'module': 3}}
d = design([G, gear_xz('G1', 20, 3, 0, 0), G2v],
           [rot('a', ['G1'], [0, 6, 0]), rot('b', ['G2'], [36, 39, 0], axis='x', driver='a')])
run('s11c_bevel_pair', d)
# 11d. hinge connection on a lid (glue_allowed)
B = {'id': 'BASE', 'position': [0, 0, 0], 'size': [200, 6, 160]}
boards = [B, {'id': 'BACK', 'position': [0, 6, 150], 'size': [200, 50, 6]},
          {'id': 'FRONT', 'position': [0, 6, 0], 'size': [200, 50, 6]},
          {'id': 'LID', 'position': [0, 56, 0], 'size': [200, 6, 156]}]
d = design(boards, [rot('lid', ['LID'], [0, 62, 156], axis='x', on='BACK', axle=None, rng=(0, 100))],
           conns=[{'type': 'tab_slot', 'board': 'FRONT', 'into': 'BASE'}, {'type': 'tab_slot', 'board': 'BACK', 'into': 'BASE'},
                  {'type': 'hinge', 'board': 'LID', 'into': 'BACK', 'edge': '+z'}], joinery='glue_allowed')
run('s11d_hinged_lid', d)
# 11e. hinge axis vs motion axis mismatch: hinge on LID's -z edge (front!) but motion pivots about the back edge
d2 = copy.deepcopy(d); d2['connections'][2]['into'] = 'FRONT'; d2['connections'][2]['edge'] = '-z'
run('s11e_hinge_on_front_motion_at_back', d2)
# 11f. cam: eccentric disk (rod pin off-centre) driving a slider: same as slider-crank (no follower contact)
