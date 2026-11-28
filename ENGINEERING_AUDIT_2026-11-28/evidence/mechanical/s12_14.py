from lib import *
import time

# 12a. wheel between two walls: axle through WALL-L (on) and WHEEL; WALL-R 1 mm beyond the wheel is on the axle line
W = [{'id': 'BASE', 'position': [0, 0, 0], 'size': [40, 6, 200]},
     {'id': 'WALL-L', 'position': [0, 6, 0], 'size': [6, 200, 200]},
     {'id': 'WHEEL', 'position': [6, 60, 60], 'size': [6, 80, 80], 'profile': {'shape': 'circle', 'center': [40, 40], 'diameter': 80}},
     {'id': 'WALL-R', 'position': [13, 6, 0], 'size': [6, 200, 200]}]
r, _ = run('s12a_axle_two_supports', design(W, [rot('spin', ['WHEEL'], [6, 100, 100], axis='x', on='WALL-L')],
            conns=[{'type': 'tab_slot', 'board': 'WALL-L', 'into': 'BASE'}, {'type': 'tab_slot', 'board': 'WALL-R', 'into': 'BASE'}]))
for c in r['design']['components']:
    hs = [f.get('id') for f in c.get('features') or [] if 'axle' in str(f.get('id', ''))]
    print('  ', c['id'], 'axle holes:', hs)
# 12b. wheel spaced 10 mm off its support (a washer gap) -> refused?
W2 = copy.deepcopy(W[:3]); W2[2]['position'][0] = 16
run('s12b_wheel_spaced_off_support', design(W2, [rot('spin', ['WHEEL'], [6, 100, 100], axis='x', on='WALL-L')],
            conns=[{'type': 'tab_slot', 'board': 'WALL-L', 'into': 'BASE'}]))
# 13. rotate motion with no axle and no hinge: a flap on a wall turning about an arbitrary line
F = [{'id': 'WALL', 'position': [0, 0, 0], 'size': [6, 200, 200]},
     {'id': 'FLAP', 'position': [6, 60, 60], 'size': [6, 80, 80]}]
run('s13_rotate_without_any_pivot_hardware', design(F, [rot('spin', ['FLAP'], [6, 100, 100], axis='x', on='WALL', axle=None)]))
run('s13b_slide_with_no_guide', design(F, [{'id': 'sl', 'type': 'slide', 'boards': ['FLAP'], 'on': 'WALL', 'direction': 'z', 'range': [-50, 50]}]))

# 14a. tunnelling: long thin arm, small post 2.57 deg into its sweep (between the 0 and 5 deg samples)
BASE = {'id': 'BASE', 'position': [-320, 0, -320], 'size': [640, 6, 640]}
ARM = {'id': 'ARM', 'position': [-10, 6, -5], 'size': [310, 6, 10]}
POST = {'id': 'POST', 'position': [287, 6, -16], 'size': [6, 20, 6], 'normal': 'x'}
run('s14a_tunnel_thin_arm', design([BASE, ARM, POST], [rot('sw', ['ARM'], [0, 6, 0], rng=(0, 90))]))
# control: same post moved onto a sampled angle (5 deg: z = -25.3) -> must be caught
POST5 = dict(POST, position=[286, 6, -28])
run('s14a_control_post_at_5deg', design([BASE, ARM, POST5], [rot('sw', ['ARM'], [0, 6, 0], rng=(0, 90))]))
# 14b. ratio 10 belt drive: driven arm samples every 50 deg -> post at 25 deg
DISK = {'id': 'DISK', 'position': [-250, 6, -250], 'size': [60, 6, 60], 'profile': {'shape': 'circle', 'center': [30, 30], 'diameter': 60}}
import math
a = math.radians(25); x, z = 250 * math.cos(a), -250 * math.sin(a)
POST25 = {'id': 'POST', 'position': [round(x) - 3, 6, round(z) - 3], 'size': [6, 20, 6], 'normal': 'x'}
run('s14b_tunnel_fast_driven', design([BASE, dict(ARM, size=[270, 6, 10]), DISK, POST25],
    [rot('in', ['DISK'], [-220, 6, -220], rng=(0, 360)), rot('fast', ['ARM'], [0, 6, 0], driver='in', ratio=10)]))
print('  post centre angle =', math.degrees(math.atan2(-(round(z)), round(x))))
