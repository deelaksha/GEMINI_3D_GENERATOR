from lib import *
import helpers as H
import sys
N1 = [int(x) for x in sys.argv[1].split(",") if x]
N2 = [int(x) for x in sys.argv[2].split(",") if x]

def inst_design(asm_boards, asm_motions, n, step, base):
    return {'format': 'board-design/v1', 'product': {'name': 'timing'}, 'material': MAT,
            'boards': [base], 'connections': [],
            'assemblies': [{'id': 'MOD', 'boards': asm_boards, 'connections': [], 'motions': asm_motions}],
            'instances': [{'assembly': 'MOD', 'id': f'I{k}', 'offset': [step[0] * k, step[1] * k, step[2] * k]} for k in range(n)]}

# 20 x wheel-on-a-block module (1 motion each) on a shared base plate
blk = {'id': 'BLK', 'position': [0, 6, 0], 'size': [6, 100, 100]}
whl = {'id': 'WHL', 'position': [6, 20, 20], 'size': [6, 60, 60], 'profile': {'shape': 'circle', 'center': [30, 30], 'diameter': 60}}
for n in N1:
    d = inst_design([blk, whl], [rot('spin', ['WHL'], [6, 50, 50], axis='x', on='BLK')], n, [0, 0, 110],
                    {'id': 'BASE', 'position': [-20, 0, -10], 'size': [60, 6, 110 * n + 10]})
    run(f's14c_timing_{n}_wheels', d, codes_only=True)

# 10 x gear-pair module (20 motions)
g1 = gear_xz('G1', 20, 3, 40, 40, y=6); g2 = gear_xz('G2', 30, 3, 115, 40, y=6, rot=6)
pl = {'id': 'PL', 'position': [0, 0, 0], 'size': [170, 6, 90]}
for n in N2:
    d = inst_design([pl, g1, g2], [rot('a', ['G1'], [40, 6, 40], on='PL'), rot('b', ['G2'], [115, 6, 40], on='PL', driver='a')],
                    n, [0, 0, 100], {'id': 'BASE', 'position': [0, -6, 0], 'size': [170, 6, 100 * n]})
    run(f's14d_timing_{n}_gearpairs', d, codes_only=True)
