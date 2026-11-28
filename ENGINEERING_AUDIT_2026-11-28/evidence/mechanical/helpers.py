from lib import *
import re

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

