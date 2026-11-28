from lib import *

BASE = {'id': 'BASE', 'position': [0, 0, 0], 'size': [200, 6, 200]}
# 8a. flap standing on BASE, tab_slotted into it, rotates about x -> MOTION_LOCKED expected
flap = {'id': 'FLAP', 'position': [50, 6, 100], 'size': [100, 80, 6]}
d = design([BASE, flap], [rot('swing', ['FLAP'], [100, 6, 106], axis='x', axle=None, rng=(0, 80))],
           conns=[{'type': 'tab_slot', 'board': 'FLAP', 'into': 'BASE'}])
run('s08a_locked_tab_slot', d)

# 8b. connecting rod tab_slotted to the static base (rod is not in any motion's "boards")
import helpers as L
d = L.crank_design('rocker')
d['boards'].append({'id': 'POST', 'position': [200, 160, 6], 'size': [6, 30, 12]})   # static post under the rod layer
d['connections'] = [{'type': 'tab_slot', 'board': 'POST', 'into': 'BASE'},
                    {'type': 'butt', 'board': 'ROD', 'into': 'POST'}]
run('s08b_rod_fixed_to_static_post', d)

# 9. lid opening about the back top edge hits a shelf at ~57 deg
boards = [dict(BASE, size=[200, 6, 160]),
          {'id': 'FRONT', 'position': [0, 6, 0], 'size': [200, 50, 6]},
          {'id': 'BACK', 'position': [0, 6, 150], 'size': [200, 50, 6]},
          {'id': 'LID', 'position': [0, 56, 0], 'size': [200, 6, 156]},
          {'id': 'SHELF', 'position': [0, 149, 60], 'size': [200, 6, 45]}]
d = design(boards, [rot('lid', ['LID'], [0, 62, 156], axis='x', on='BACK', axle=None, rng=(0, 110))],
           conns=[{'type': 'tab_slot', 'board': 'FRONT', 'into': 'BASE'}, {'type': 'tab_slot', 'board': 'BACK', 'into': 'BASE'}])
run('s09_lid_hits_shelf', d)

# 10a. driven_by a motion that does not exist
G = {'id': 'BASE', 'position': [-200, 0, -200], 'size': [600, 6, 600]}
d = design([G, gear_xz('G1', 20, 3, 0, 0), gear_xz('G2', 30, 3, 75, 0, rot=6)],
           [rot('drive', ['G1'], [0, 6, 0]), rot('follow', ['G2'], [75, 6, 0], driver='nosuch')])
run('s10a_driven_by_missing', d)
# 10b. gear driven by a gear it cannot reach (150 mm apart instead of 75)
d = design([G, gear_xz('G1', 20, 3, 0, 0), gear_xz('G2', 30, 3, 150, 0)],
           [rot('drive', ['G1'], [0, 6, 0]), rot('follow', ['G2'], [150, 6, 0], driver='drive')])
r, _ = run('s10b_gear_driven_not_meshing', d)
# 10c. cycle
d = design([G, gear_xz('G1', 20, 3, 0, 0), gear_xz('G2', 30, 3, 75, 0, rot=6)],
           [rot('drive', ['G1'], [0, 6, 0], driver='follow'), rot('follow', ['G2'], [75, 6, 0], driver='drive')])
run('s10c_driven_by_cycle', d)
# 10d. self-drive
d = design([G, gear_xz('G1', 20, 3, 0, 0)], [rot('drive', ['G1'], [0, 6, 0], driver='drive')])
run('s10d_driven_by_self', d)
# 10e. gear G3 physically meshes with G2 but nobody declares it (unconstrained idler)
d = design([G, gear_xz('G1', 20, 3, 0, 0), gear_xz('G2', 30, 3, 75, 0, rot=6), gear_xz('G3', 20, 3, 75, 75)],
           [rot('drive', ['G1'], [0, 6, 0]), rot('follow', ['G2'], [75, 6, 0], driver='drive'),
            rot('idle', ['G3'], [75, 6, 75], rng=(0, 360))])
run('s10e_undeclared_mesh_independent_input', d)
# 10f. two independent inputs (two cranks) in one product: is it flagged?
d = design([G, gear_xz('G1', 20, 3, 0, 0), gear_xz('G2', 30, 3, 200, 0)],
           [rot('in1', ['G1'], [0, 6, 0]), rot('in2', ['G2'], [200, 6, 0])])
run('s10f_two_independent_inputs', d)
