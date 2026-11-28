from lib import *
import lib
lib.MAT = {'type': 'plywood', 'thickness': 18, 'kerf': 0.15}
boards = [{'id': 'SIDE-L', 'position': [0, 0, 0], 'size': [18, 400, 300]},
          {'id': 'SIDE-R', 'position': [282, 0, 0], 'size': [18, 400, 300]},
          {'id': 'BOTTOM', 'position': [18, 0, 0], 'size': [264, 18, 300]},
          {'id': 'TOP', 'position': [18, 382, 0], 'size': [264, 18, 300]},
          {'id': 'DOOR', 'position': [0, 0, 300], 'size': [300, 400, 18]}]
conns = [{'type': 'butt', 'board': 'BOTTOM', 'into': 'SIDE-L'}, {'type': 'butt', 'board': 'BOTTOM', 'into': 'SIDE-R'},
         {'type': 'butt', 'board': 'TOP', 'into': 'SIDE-L'}, {'type': 'butt', 'board': 'TOP', 'into': 'SIDE-R'},
         {'type': 'hinge', 'board': 'DOOR', 'into': 'SIDE-R', 'edge': '+x', 'count': 2, 'gap': 0}]
ok = rot('door', ['DOOR'], [300, 0, 318], axis='y', on='SIDE-R', axle=None, rng=(0, 100))
run('s11g_cabinet_door_hinge_ok', design(boards, [ok], conns, joinery='glue_allowed'))
bad = rot('door', ['DOOR'], [0, 0, 318], axis='y', on='SIDE-R', axle=None, rng=(-100, 0))
run('s11h_cabinet_door_hinge_on_right_pivot_on_left', design(boards, [bad], conns, joinery='glue_allowed'))
