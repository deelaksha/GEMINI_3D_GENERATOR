from lib import *
import re
from board_engine.motion import train_values

BASE = {'id': 'BASE', 'position': [-200, 0, -200], 'size': [700, 6, 600]}


def phased(d, tries=4):
    """apply GEAR_PHASE fixes until none remain (uses the compiler's own fix)"""
    for _ in range(tries):
        r = canvas.compile_source(json.dumps(d), run_production=False)
        ph = [x for x in r['diagnostics'] if x['code'] == 'GEAR_PHASE']
        if not ph:
            return d
        for x in ph:
            gid = re.search(r"teeth of '([^']+)'", x['message']).group(1)
            want = float(re.search(r'to ([\d.\-]+) degrees', x['message']).group(1))
            next(b for b in d['boards'] if b['id'] == gid)['profile']['rotation'] = want
    return d

# 3a simple chain A(20) -> B(30) -> C(15): expected ratios B=-2/3, C=+4/3
d = design([BASE, gear_xz('GA', 20, 3, 0, 0), gear_xz('GB', 30, 3, 75, 0), gear_xz('GC', 15, 3, 75, 67.5)],
           [rot('A', ['GA'], [0, 6, 0]), rot('B', ['GB'], [75, 6, 0], driver='A'), rot('C', ['GC'], [75, 6, 67.5], driver='B')])
d = phased(d)
r, _ = run('s03a_train_simple', d)
ms = r['design']['motions']
print('  train_values at A=90:', train_values(ms, 'A', 90.0))

# 3b compound: A(12) -> B big(36)+ B small(12, stacked on B) -> C(36) on a spacer one layer up
ra = lambda z: 3 * z / 2 + 3
d = design([BASE, gear_xz('GA', 12, 3, 0, 0), gear_xz('GB', 36, 3, 72, 0), gear_xz('GBs', 12, 3, 72, 0, y=12),
            gear_xz('GC', 36, 3, 72, 72, y=12),
            {'id': 'SPACER', 'position': [72 - 20, 6, 72 - 20], 'size': [40, 6, 40]}],
           [rot('A', ['GA'], [0, 6, 0]), rot('B', ['GB', 'GBs'], [72, 6, 0], driver='A'),
            rot('C', ['GC'], [72, 12, 72], driver='B', on='SPACER')])
d = phased(d)
r, _ = run('s03b_train_compound', d)
ms = r['design']['motions']
print('  train_values at A=90:', train_values(ms, 'A', 90.0), ' expected C = 90*(1/3)*(1/3) = +10')


def crank_design(follower, crank_pin=(120, 150), disk=60, extra=(), to=None):
    c = (100, 150)
    boards = [{'id': 'BASE', 'position': [0, 0, 0], 'size': [420, 320, 6]},
              {'id': 'CRANK', 'position': [c[0] - disk / 2, c[1] - disk / 2, 6], 'size': [disk, disk, 6],
               'profile': {'shape': 'circle', 'center': [disk / 2, disk / 2], 'diameter': disk}}]
    motions = [rot('crank', ['CRANK'], [100, 150, 6], axis='z')]
    if follower == 'rocker':
        to = to or (300, 220)
        boards.append({'id': 'ARM', 'position': [290, 140, 6], 'size': [20, 90, 6]})
        motions.append(rot('rocker', ['ARM'], [300, 150, 6], axis='z', driver='crank'))
    else:
        to = to or (270, 150)
        boards.append({'id': 'SLIDER', 'position': [250, 140, 6], 'size': [40, 20, 6]})
        motions.append({'id': 'slider', 'type': 'slide', 'boards': ['SLIDER'], 'on': 'BASE', 'direction': 'x', 'driven_by': 'crank'})
    boards.append(bar('ROD', crank_pin, to, 12))
    motions[1]['link'] = {'rod': 'ROD', 'from': [crank_pin[0], crank_pin[1], 12], 'to': [to[0], to[1], 12]}
    return design(boards + list(extra), motions)

if __name__ == '__main__':
    r, _ = run('s04_slider_crank', crank_design('slider'))
    m = [x for x in r['design']['motions'] if x['id'] == 'slider'][0]
    print('  stroke =', m['range'][1] - m['range'][0], '(expect 2*20=40)')
    r, _ = run('s05a_crank_rocker', crank_design('rocker'))
    r, _ = run('s05b_non_grashof', crank_design('rocker', crank_pin=(160, 150), disk=140))
