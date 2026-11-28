from lib import *
import lib
lib.MAT = {'type': 'plywood', 'thickness': 18, 'kerf': 0.15}
boards = [{'id': 'SIDE-L', 'position': [0, 0, 0], 'size': [18, 400, 300]},
          {'id': 'SIDE-R', 'position': [282, 0, 0], 'size': [18, 400, 300]},
          {'id': 'BOTTOM', 'position': [18, 0, 0], 'size': [264, 18, 300]},
          {'id': 'TOP', 'position': [18, 382, 0], 'size': [264, 18, 300]},
          {'id': 'DOOR', 'position': [0, 0, 302], 'size': [300, 400, 18]}]
conns = [{'type': 'butt', 'board': 'BOTTOM', 'into': 'SIDE-L'}, {'type': 'butt', 'board': 'BOTTOM', 'into': 'SIDE-R'},
         {'type': 'butt', 'board': 'TOP', 'into': 'SIDE-L'}, {'type': 'butt', 'board': 'TOP', 'into': 'SIDE-R'},
         {'type': 'hinge', 'board': 'DOOR', 'into': 'SIDE-R', 'edge': '+x', 'count': 2, 'gap': 2}]
ok = rot('door', ['DOOR'], [300, 0, 320], axis='y', on='SIDE-R', axle=None, rng=(0, 100))
run('s11f_cabinet_door_hinge_gap2_spec_default', design(boards, [ok], conns, joinery='glue_allowed'))


