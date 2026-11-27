"""
Moving parts of a board design: "motions" that turn a group of boards about a pivot or slide it along an axis.

  "motions": [{"id", "type": "rotate", "boards": [ids], "on": id, "axis": "x"|"y"|"z", "pivot": [x, y, z],
               "range": [from, to] (degrees; 0 = as modelled), "axle"?: {"diameter": mm}}
            | {"id", "type": "slide", "boards": [ids], "on": id, "direction": "x"|"y"|"z", "range": [from, to] (mm)}]

The boards move together, mounted on the static board "on". An "axle" cuts a dowel hole of that diameter through
every board the pivot line passes square through (the moving boards and the mount): a real, glue-free pivot.
Checks (each with its calculation): the group touches its mount; a slide runs along the contact or straight off it
(a lid lifted off), never into it; no
fixed joint ties the group to the rest; and the group clears every other board through its whole travel.
"""
import math

from . import geometry as G
from .deadline import check as check_budget
from .expand import _thin_axis

AXES = ('x', 'y', 'z')
TOUCH = 0.5                 # mm: the group must be this close to its mount
CLEARANCE = 1.0             # mm: running gap a moving part needs to everything it passes (else it binds)
ROTATE_STEP = 5.0           # degrees between the positions checked along a rotation
MAX_SAMPLES = 72


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _vec3(v):
    return isinstance(v, list) and len(v) == 3 and all(_num(x) for x in v)


def parse_motions(data, origin, diags, diag, line=None):
    """Validate data["motions"] -> list of normalised motions; problems become MOTION_INVALID errors. Board ids may
    be written as the source id of a repeated / mirrored / instanced board: every generated copy then moves."""
    raw = data.get('motions')
    if raw is None:
        return []
    if not isinstance(raw, list):
        diags.append(diag('error', 'MOTION_INVALID', '"motions" must be a list of motions.', line=line))
        return []
    ids = {b.get('id') for b in data.get('boards') or [] if isinstance(b, dict)}
    copies = {}
    for gen, src in (origin or {}).items():
        if gen in ids:
            copies.setdefault(src, []).append(gen)
    out, taken, seen = [], {}, set()

    def bad(m, msg):
        diags.append(diag('error', 'MOTION_INVALID', f"Motion '{m.get('id', '?')}': {msg}", line=line))

    for m in raw:
        if not isinstance(m, dict) or not isinstance(m.get('id'), str) or not m['id']:
            diags.append(diag('error', 'MOTION_INVALID', 'Every motion needs an "id".', line=line))
            continue
        if m['id'] in seen:
            bad(m, 'the id is used twice.')
            continue
        seen.add(m['id'])
        kind = m.get('type')
        if kind not in ('rotate', 'slide'):
            bad(m, '"type" must be "rotate" or "slide".')
            continue
        names = m.get('boards')
        if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
            bad(m, '"boards" must list the ids of the boards that move.')
            continue
        boards, missing = [], []
        for n in names:
            found = [n] if n in ids else copies.get(n, [])
            if not found:
                missing.append(n)
            boards += [b for b in found if b not in boards]
        if missing:
            bad(m, f"unknown board(s) {', '.join(missing)}.")
            continue
        on = m.get('on')
        if on not in ids or on in boards:
            bad(m, '"on" must be the id of the static board it is mounted on (not one of the moving boards).')
            continue
        twice = [b for b in boards if b in taken]
        if twice:
            bad(m, f"board(s) {', '.join(twice)} already move with motion '{taken[twice[0]]}'.")
            continue
        rng, driver = m.get('range'), m.get('driven_by')
        if driver is not None and not isinstance(driver, str):
            bad(m, '"driven_by" must be the id of the motion that drives it.')
            continue
        if m.get('ratio') is not None and not (_num(m['ratio']) and m['ratio'] != 0):
            bad(m, '"ratio" must be a non-zero number (its turn / slide per degree or mm of the driver).')
            continue
        if driver is None and not (isinstance(rng, list) and len(rng) == 2 and all(_num(v) for v in rng) and rng[0] < rng[1]):
            bad(m, '"range" must be [from, to] with from < to (0 is the position as modelled).')
            continue
        mo = {'id': m['id'], 'type': kind, 'boards': boards, 'on': on,
              'range': [float(rng[0]), float(rng[1])] if driver is None else None}
        if driver is not None:
            mo['driven_by'] = driver
            if m.get('ratio') is not None:
                mo['ratio'] = float(m['ratio'])
        if kind == 'rotate':
            if m.get('axis') not in AXES or not _vec3(m.get('pivot')):
                bad(m, 'a rotation needs "axis": "x"|"y"|"z" and "pivot": [x, y, z] (a point on the turning axis).')
                continue
            if driver is None and not (-360 <= rng[0] and rng[1] <= 360):
                bad(m, 'a rotation range must lie within -360 .. 360 degrees.')
                continue
            axle = m.get('axle')
            if axle is not None and not (isinstance(axle, dict) and _num(axle.get('diameter')) and 1 <= axle['diameter'] <= 50):
                bad(m, '"axle" must be {"diameter": mm} between 1 and 50.')
                continue
            mo.update(axis=m['axis'], pivot=[float(v) for v in m['pivot']],
                      axle={'diameter': float(axle['diameter'])} if axle else None)
        else:
            if m.get('direction') not in AXES:
                bad(m, 'a slide needs "direction": "x"|"y"|"z".')
                continue
            mo['direction'] = m['direction']
        for b in boards:
            taken[b] = m['id']
        out.append(mo)
    return _link(out, find_gears(data), diags, diag, line)


def find_gears(data):
    """Boards whose profile is a "gear" shape (and are not tilted): id -> teeth, module, rotation, world centre, axis."""
    t_default = (data.get('material') or {}).get('thickness')
    out = {}
    for b in data.get('boards') or []:
        prof = b.get('profile') if isinstance(b, dict) else None
        if not (isinstance(prof, dict) and prof.get('shape') == 'gear' and not b.get('rotate')
                and _vec3(b.get('position')) and _vec3(b.get('size')) and isinstance(prof.get('center'), list)
                and isinstance(prof.get('teeth'), int) and _num(prof.get('module'))):
            continue
        thin = _thin_axis(b, t_default)
        if thin is None:
            continue
        i, j = [k for k in range(3) if k != thin]
        centre = list(b['position'])
        centre[i] += prof['center'][0]
        centre[j] += prof['center'][1]
        centre[thin] += b['size'][thin] / 2.0
        out[b['id']] = {'teeth': prof['teeth'], 'module': float(prof['module']), 'rotation': float(prof.get('rotation', 0)),
                        'centre': centre, 'thin': thin, 'span': (b['position'][thin], b['position'][thin] + b['size'][thin]),
                        'profile': prof}
    return out


def _link(motions, gears, diags, diag, line):
    """Resolve "driven_by": chains in order, the ratio from the meshing gears (or "ratio"), the range from the driver."""
    by_id = {m['id']: m for m in motions}
    done, out = set(), []

    def bad(m, msg):
        diags.append(diag('error', 'MOTION_INVALID', f"Motion '{m['id']}': {msg}", line=line))

    def resolve(m, path):
        if m['id'] in done:
            return True
        drv_id = m.get('driven_by')
        if drv_id is None:
            done.add(m['id'])
            return True
        if drv_id in path:
            bad(m, f"its drivers go round in a loop ({' -> '.join(path + [drv_id])}).")
            return False
        drv = by_id.get(drv_id)
        if drv is None or not resolve(drv, path + [m['id']]) or drv['range'] is None:
            if drv is None:
                bad(m, f"\"driven_by\" names no motion '{drv_id}'.")
            return False
        if 'ratio' not in m:
            pairs = [(a, b) for a in drv['boards'] if a in gears for b in m['boards'] if b in gears]
            if not pairs:
                bad(m, f"give a \"ratio\", or put meshing gears (a \"gear\" profile) in both it and '{drv_id}'.")
                return False
            dist = lambda ab: abs(math.dist(gears[ab[0]]['centre'], gears[ab[1]]['centre'])
                                  - gears[ab[0]]['module'] * (gears[ab[0]]['teeth'] + gears[ab[1]]['teeth']) / 2)
            a, b = min(pairs, key=dist)
            m['ratio'] = -gears[a]['teeth'] / gears[b]['teeth']       # meshing gears turn the other way
            m['gears'] = [a, b]
            m['mesh'] = {'driver': dict(gears[a], id=a), 'driven': dict(gears[b], id=b)}
        lo, hi = sorted(v * m['ratio'] + 0.0 for v in drv['range'])          # (+ 0.0: no -0.0)
        m['range'] = [lo, hi]
        done.add(m['id'])
        return True
    for m in motions:
        if resolve(m, []):
            out.append(m)
    return out


def add_axle_holes(data, motions, thickness, diags, diag):
    """Cut each axle's dowel hole into the raw boards its pivot line passes square through (before they are built)."""
    by_id = {b.get('id'): b for b in data.get('boards') or [] if isinstance(b, dict)}
    for m in motions:
        if m['type'] != 'rotate' or not m['axle']:
            continue
        k = AXES.index(m['axis'])
        holed, d = [], m['axle']['diameter']
        for bid in m['boards'] + [m['on']]:
            b = by_id.get(bid)
            if not b or b.get('rotate') or not (_vec3(b.get('position')) and _vec3(b.get('size'))):
                continue
            if _thin_axis(b, thickness) != k:
                continue                        # the axle runs along this board, not through it
            lo, size = b['position'], b['size']
            if not all(lo[i] + d / 2 < m['pivot'][i] < lo[i] + size[i] - d / 2 for i in range(3) if i != k):
                continue                        # the pivot line misses this board
            centre = list(m['pivot'])
            centre[k] = lo[k] + size[k] / 2.0
            b['openings'] = list(b.get('openings') or []) + [
                {'id': f"axle-{m['id']}", 'kind': 'hole', 'shape': 'circle', 'center': centre, 'diameter': d,
                 'note': f"axle of motion {m['id']}: Ø{d:g} mm dowel"}]
            holed.append(bid)
        moving = [b for b in holed if b in m['boards']]
        if not moving or m['on'] not in holed:
            diags.append(diag('error', 'MOTION_AXLE', f"Motion '{m['id']}': its axle along {m['axis']} through "
                              f"[{', '.join(f'{v:g}' for v in m['pivot'])}] must pass square through a moving board and "
                              f"through '{m['on']}' (both thin along {m['axis']}, the pivot inside both with room for the "
                              f"Ø{d:g} mm hole). It passes through: {', '.join(holed) or 'none of them'}."))
            continue
        span = [by_id[b] for b in holed]
        length = max(b['position'][k] + b['size'][k] for b in span) - min(b['position'][k] for b in span)
        m['axle']['boards'] = holed
        diags.append(diag('info', 'MOTION_AXLE', f"Motion '{m['id']}': cut a Ø{d:g} mm dowel about {math.ceil(length + 4)} mm "
                          f"long as its axle; it passes through {', '.join(holed)}."))


def _rotation(axis, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == 'x':
        return [[1, 0, 0], [0, c, -s], [0, s, c]]
    if axis == 'y':
        return [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def _moved(design, comp, m, value):
    """The plate of `comp` with its motion at `value` (degrees or mm)."""
    from .canvas import _euler_xyz
    from .model import Plate
    pos, rot = comp['placement']['position'], comp['placement']['rotation']
    if m['type'] == 'slide':
        k = AXES.index(m['direction'])
        pos = [pos[i] + (value if i == k else 0.0) for i in range(3)]
    else:
        R, p = _rotation(m['axis'], value), m['pivot']
        rel = [pos[i] - p[i] for i in range(3)]
        pos = [p[i] + sum(R[i][j] * rel[j] for j in range(3)) for i in range(3)]
        rot = _euler_xyz(G.mat_mul(R, G.rotation_matrix(rot)))
    return Plate(design, dict(comp, placement={'position': pos, 'rotation': rot}))


def _grown(design, comp, c):
    """The component grown by c on every side (outline and both faces), cut-outs left out: if this touches a board the
    real part does not, the running gap to that board is under c."""
    from .cutpaths import offset_polygon
    from .model import thickness_of
    outline = comp['outline'] if G.signed_area(comp['outline']) > 0 else list(reversed(comp['outline']))
    big = {k: v for k, v in comp.items() if k not in ('arcs', 'features', 'tabs')}
    big.update(outline=offset_polygon(outline, c), thickness=thickness_of(design, comp) + 2 * c, features=[])
    return big


def _axis_distance(m, q):
    """Distance of point q from a rotate motion's turning axis."""
    k = AXES.index(m['axis'])
    return math.hypot(*[q[i] - m['pivot'][i] for i in range(3) if i != k])


def _samples(m):
    """-> (step, positions to check): whole steps outwards from the modelled position (5 degrees, or about 1/48 of a slide), plus
    both ends of the range; nearest first, so the first collision found on each side is the nearest one."""
    a, b = m['range']
    step = ROTATE_STEP if m['type'] == 'rotate' else max(2.0, (b - a) / 48.0)
    step = max(step, (b - a) / MAX_SAMPLES)
    vals, k = {a, b}, 1
    while k * step < max(abs(a), abs(b)):
        for v in (k * step, -k * step):
            if a < v < b:
                vals.add(round(v, 9))
        k += 1
    return step, sorted((v for v in vals if abs(v) > 1e-9), key=lambda v: (abs(v), v))


def _box_gap(a, b):
    return max(max(0.0, b[0][i] - a[1][i], a[0][i] - b[1][i]) for i in range(3))


def check_motions(design, plates, motions):
    """-> issues (validation format) for every motion: mounting, fixed joints, slide direction, travel clearance."""
    from .validation import issue, plate_interference
    out = []
    comps = {c['id']: c for c in design['components']}
    trains = {m['id']: m['id'] for m in motions}

    def root(x):
        while trains[x] != x:
            x = trains[x]
        return x
    for m in motions:
        if m.get('driven_by') in trains:
            trains[root(m['id'])] = root(m['driven_by'])
    trains = {k: root(k) for k in trains}
    for m in motions:
        group = [b for b in m['boards'] if b in plates]
        if not group or m['on'] not in plates:
            continue
        unit = '°' if m['type'] == 'rotate' else ' mm'
        how = (f"turning about {m['axis']} through [{', '.join(f'{v:g}' for v in m['pivot'])}]" if m['type'] == 'rotate'
               else f"sliding along {m['direction']}")
        mount = plates[m['on']].world_aabb()
        gaps = {b: _box_gap(plates[b].world_aabb(), mount) for b in group}
        near = min(gaps, key=gaps.get)
        if gaps[near] > TOUCH:
            out.append(issue('MOTION_NOT_MOUNTED', 'error', 'assembly',
                             f"Motion '{m['id']}': the moving boards do not touch '{m['on']}', the board they are mounted on "
                             f"(closest: '{near}', {gaps[near]:.1f} mm away). Move them onto it or mount them on the board "
                             f"they touch.", group + [m['on']],
                             calc=[f"gap '{near}' - '{m['on']}' = {gaps[near]:.2f} mm (must be <= {TOUCH} mm)"]))
            continue
        moving = set(group)
        fixed = [j for j in design['joints'] if j.get('status') == 'joined' and j['type'] != 'hinge'
                 and (j['a'] in moving) != (j['b'] in moving)]
        if fixed:
            j = fixed[0]
            out.append(issue('MOTION_LOCKED', 'error', 'joint',
                             f"Motion '{m['id']}': '{j['a']}' and '{j['b']}' are joined by a fixed {j['type']} joint, so the "
                             f"moving boards cannot move. Remove that connection: the motion itself mounts them on "
                             f"'{m['on']}'" + (" (with its axle)." if m.get('axle') else " (add an \"axle\" for a pivot)."),
                             [j['a'], j['b']], joint=j['id'],
                             calc=[f"{len(fixed)} fixed joint(s) between moving and static boards: "
                                   + ', '.join(x['id'] for x in fixed[:6])]))
            continue
        if m['type'] == 'slide':
            k = AXES.index(m['direction'])
            lo, hi = plates[near].world_aabb()
            ov = [min(hi[i], mount[1][i]) - max(lo[i], mount[0][i]) for i in range(3)]
            normal = min(range(3), key=lambda i: ov[i])
            if normal == k:
                # straight off its support (a lid lifted off, a plug pulled out) is fine; straight into it is not
                side = 1 if lo[k] >= mount[1][k] - TOUCH else -1 if hi[k] <= mount[0][k] + TOUCH else 0
                into = [v for v in m['range'] if v * side < 0] if side else list(m['range'])
                if into:
                    away = ('+' if side > 0 else '-') + AXES[k] if side else None
                    out.append(issue('MOTION_SLIDE_BLOCKED', 'error', 'assembly',
                                     f"Motion '{m['id']}': '{near}' sits on '{m['on']}' across {AXES[k]}, so sliding to "
                                     f"{into[0]:g} mm along {AXES[k]} would push it into its support. "
                                     + (f"Lift it off instead (a range on the {away} side, e.g. [0, {abs(m['range'][1]) or 50:g}]) "
                                        f"or slide along the contact: {' or '.join(AXES[i] for i in range(3) if i != k)}."
                                        if side else f"Slide along the contact instead: "
                                        f"{' or '.join(AXES[i] for i in range(3) if i != k)}."), [near, m['on']],
                                     calc=[f"overlap of '{near}' and '{m['on']}' per axis: x {ov[0]:.1f}, y {ov[1]:.1f}, "
                                           f"z {ov[2]:.1f} mm -> contact across {AXES[normal]}",
                                           f"'{near}' is on the {'+' if side > 0 else '-' if side else '?'} side of "
                                           f"'{m['on']}'; range [{m['range'][0]:g}, {m['range'][1]:g}] mm"]))
                    continue
        hinged = {frozenset((j['a'], j['b'])) for j in design['joints'] if j.get('status') == 'joined' and j['type'] == 'hinge'}
        train = {b for t in motions if trains.get(t['id']) == trains.get(m['id']) for b in t['boards']}
        moving = moving | train         # gears of one train move together: their mesh is checked separately
        step, samples = _samples(m)
        posed = {}
        for v in samples:
            check_budget()
            posed[v] = {b: _moved(design, comps[b], m, v) for b in group}
        env = None
        for boards in posed.values():
            for p in boards.values():
                lo, hi = p.world_aabb()
                env = (lo, hi) if env is None else ([min(env[0][i], lo[i]) for i in range(3)],
                                                     [max(env[1][i], hi[i]) for i in range(3)])
        others = [s for s in plates if s not in moving and env and _box_gap(plates[s].world_aabb(), env) <= 0]
        first, tight = {}, {}                        # (static board, side of 0) -> (value, moving board, hit)
        grown = {b: _grown(design, comps[b], CLEARANCE) for b in group}
        # contact right at a hinge line is unavoidable: an edge closer to the axis than one step moves is not judged
        near_axis = CLEARANCE / max(math.sin(math.radians(step)), 1e-3) if m['type'] == 'rotate' else 0.0
        for v in samples:                            # outwards from 0, so the first hit is the nearest one
            for b, p in posed[v].items():
                big = None
                for s in others:
                    if (s, v > 0) in first or frozenset((b, s)) in hinged:
                        continue
                    if _box_gap(p.world_aabb(), plates[s].world_aabb()) > CLEARANCE:
                        continue
                    check_budget()
                    hits = plate_interference(p, plates[s]) if _box_gap(p.world_aabb(), plates[s].world_aabb()) <= 0 else []
                    if hits:
                        first[(s, v > 0)] = (v, b, hits[0])
                        continue
                    if s == m['on'] or (s, v > 0) in tight:
                        continue                     # it rests / runs on its mount by design
                    big = big or _moved(design, grown[b], m, v)
                    close = [h for h in plate_interference(big, plates[s])
                             if not (near_axis and h['kind'] != 'parallel_overlap' and h.get('location')
                                     and _axis_distance(m, h['location']) < near_axis)]
                    if close:
                        tight[(s, v > 0)] = (v, b, close[0])
        for (s, _side), (v, b, hit) in sorted(first.items(), key=lambda kv: abs(kv[1][0])):
            side = [x for x in samples if (x > 0) == (v > 0) and abs(x) < abs(v)]
            clear = side[-1] if side else 0.0
            size = f"{hit['length']} mm" if 'length' in hit else f"{hit['area']} mm²"
            limit = [m['range'][0], clear] if v > 0 else [clear, m['range'][1]]
            out.append(issue('MOTION_COLLISION', 'error', 'assembly',
                             f"Motion '{m['id']}': {how}, '{b}' runs into '{s}' at {v:g}{unit} (shared material {size}). "
                             f"It moves freely only to {clear:g}{unit}: limit the range to [{limit[0]:g}, {limit[1]:g}], "
                             f"or move the pivot / cut clearance into '{s}'.", [b, s],
                             location=hit.get('location'),
                             calc=[f"'{b}' {how}: positions checked every {step:g}{unit} over "
                                   f"[{m['range'][0]:g}, {m['range'][1]:g}]",
                                   f"first contact with '{s}' at {v:g}{unit}: {hit['kind']} {size}",
                                   f"last clear position on that side: {clear:g}{unit}"]))
        for (s, side), (v, b, hit) in sorted(tight.items(), key=lambda kv: abs(kv[1][0])):
            if (s, side) in first:
                continue                             # it collides there anyway
            out.append(issue('MOTION_CLEARANCE', 'error', 'assembly',
                             f"Motion '{m['id']}': {how}, '{b}' passes '{s}' with less than {CLEARANCE:g} mm to spare at "
                             f"{v:g}{unit}, so it would rub and bind. Leave a running gap of at least {CLEARANCE:g} mm "
                             f"(about 2 mm is safer): move or shrink '{b}' or '{s}' there.", [b, s],
                             location=hit.get('location'),
                             calc=[f"'{b}' grown by {CLEARANCE:g} mm on every side touches '{s}' at {v:g}{unit} "
                                   f"({hit['kind']}); the real parts do not touch, so the gap is under {CLEARANCE:g} mm",
                                   f"positions checked every {step:g}{unit} over [{m['range'][0]:g}, {m['range'][1]:g}]"
                                   + (f"; edges within {near_axis:.0f} mm of the turning axis (the hinge line) are not "
                                      f"judged" if near_axis else '')]))
    return out


GEAR_DISTANCE_TOL = 0.1     # mm: centre distance against module x (z1 + z2) / 2
GEAR_PHASE_TOL = 0.03       # of one tooth pitch: teeth that far off interleaving would clash


def check_gears(motions):
    """-> issues for every pair of meshing gears in a train: same module, parallel axles in one plane, each gear on
    its motion's axle, the centre distance module x (z1 + z2) / 2, and teeth that interleave (with the exact fix)."""
    from .validation import issue
    out, by_id = [], {m['id']: m for m in motions}
    for m in motions:
        mesh = m.get('mesh')
        if not mesh:
            continue
        a, b, drv = mesh['driver'], mesh['driven'], by_id.get(m['driven_by'])
        pair = [a['id'], b['id']]
        if abs(a['module'] - b['module']) > 1e-6:
            out.append(issue('GEAR_MESH', 'error', 'assembly',
                             f"Gears '{a['id']}' and '{b['id']}' cannot mesh: their modules differ ({a['module']:g} and "
                             f"{b['module']:g} mm). Meshing gears need the same module (tooth size).", pair,
                             calc=[f"module '{a['id']}' = {a['module']:g} mm, '{b['id']}' = {b['module']:g} mm"]))
            continue
        k = a['thin']
        if b['thin'] != k or min(a['span'][1], b['span'][1]) - max(a['span'][0], b['span'][0]) <= 0:
            out.append(issue('GEAR_MESH', 'error', 'assembly',
                             f"Gears '{a['id']}' and '{b['id']}' are not in one plane on parallel axles, so their teeth "
                             f"cannot meet. Put both on the same {AXES[k]} level, thin along {AXES[k]}.", pair,
                             calc=[f"'{a['id']}' thin along {AXES[a['thin']]}, {AXES[k]} {a['span'][0]:g}..{a['span'][1]:g} mm",
                                   f"'{b['id']}' thin along {AXES[b['thin']]}, {AXES[b['thin']]} "
                                   f"{b['span'][0]:g}..{b['span'][1]:g} mm"]))
            continue
        off_axis = []
        for g, mo in ((a, drv), (b, m)):
            if mo is None or mo['type'] != 'rotate':
                continue
            if mo.get('axis') != AXES[k]:
                off_axis.append(f"'{g['id']}' lies across {AXES[k]} but motion '{mo['id']}' turns about {mo.get('axis')}")
            else:
                d = math.hypot(*[g['centre'][i] - mo['pivot'][i] for i in range(3) if i != k])
                if d > GEAR_DISTANCE_TOL:
                    off_axis.append(f"'{g['id']}' centre [{', '.join(f'{v:g}' for v in g['centre'])}] is {d:.2f} mm from "
                                    f"motion '{mo['id']}' pivot [{', '.join(f'{v:g}' for v in mo['pivot'])}]")
        if off_axis:
            out.append(issue('GEAR_OFF_AXIS', 'error', 'assembly',
                             f"A gear must turn about its own centre: {'; '.join(off_axis)}. Put the motion's pivot (and "
                             f"axle) at the gear centre, its axis across the gear.", pair, calc=off_axis))
            continue
        i, j = [x for x in range(3) if x != k]
        za, zb, mod = a['teeth'], b['teeth'], a['module']
        need = mod * (za + zb) / 2.0
        du, dv = b['centre'][i] - a['centre'][i], b['centre'][j] - a['centre'][j]
        dist = math.hypot(du, dv)
        if abs(dist - need) > GEAR_DISTANCE_TOL:
            if dist > 1e-9:
                delta = [0.0, 0.0, 0.0]
                delta[i], delta[j] = du / dist * (need - dist), dv / dist * (need - dist)
            else:
                delta = [0.0, 0.0, 0.0]
                delta[i] = need
            out.append(issue('GEAR_MESH', 'error', 'assembly',
                             f"Gears '{a['id']}' ({za} teeth) and '{b['id']}' ({zb} teeth), module {mod:g}, must be "
                             f"{need:g} mm apart centre to centre; they are {dist:.2f} mm apart. Move '{b['id']}' (and "
                             f"its motion pivot) by [{', '.join(f'{v:.2f}' for v in delta)}] mm.", pair,
                             calc=[f"required = module x (z1 + z2) / 2 = {mod:g} x ({za} + {zb}) / 2 = {need:g} mm",
                                   f"actual = |centre '{b['id']}' - centre '{a['id']}'| = {dist:.2f} mm"],
                             suggestion={'action': 'translate', 'component': b['id'], 'delta': [round(v, 3) for v in delta]}))
            continue
        beta = math.atan2(dv, du)                       # in the shared face plane: u along axis i, v along j
        fa = math.radians(a['rotation'])
        need_b = beta + math.pi - (math.pi - za * (beta - fa)) / zb
        pitch = 2 * math.pi / zb
        diff = (math.radians(b['rotation']) - need_b + pitch / 2) % pitch - pitch / 2
        if abs(diff) > GEAR_PHASE_TOL * pitch:
            want = round(math.degrees(need_b) % math.degrees(pitch), 3)
            prof = dict(b['profile'], rotation=want)
            out.append(issue('GEAR_PHASE', 'error', 'assembly',
                             f"The teeth of '{b['id']}' land on the teeth of '{a['id']}' instead of between them: set its "
                             f"gear \"rotation\" to {want:g} degrees (any multiple of {math.degrees(pitch):g} more is the same).",
                             pair, calc=[f"line of centres at {math.degrees(beta):.3f} deg, '{a['id']}' rotation "
                                         f"{a['rotation']:g} deg, {za} : {zb} teeth",
                                         f"'{b['id']}' needs rotation = beta + 180 - (180 - z1 (beta - rot1)) / z2 = "
                                         f"{want:g} deg (mod {math.degrees(pitch):g}); it has {b['rotation']:g}"],
                             fixes=[{'id': f"gear-phase-{b['id']}", 'title': f"Turn gear '{b['id']}' to {want:g} degrees",
                                     'safe': True, 'edits': [{'board': b['id'], 'field': 'profile', 'value': prof}]}]))
    return out


def model_motions(motions):
    """Motions for the 3D view (world vectors; the view animates each over its range)."""
    out = []
    for m in motions:
        e = {'id': m['id'], 'type': m['type'], 'boards': m['boards'], 'on': m['on'], 'range': m['range'],
             **({'driven_by': m['driven_by'], 'ratio': m['ratio']} if m.get('driven_by') else {})}
        if m['type'] == 'rotate':
            e.update(axis=[1.0 if a == m['axis'] else 0.0 for a in AXES], pivot=m['pivot'])
        else:
            e['direction'] = [1.0 if a == m['direction'] else 0.0 for a in AXES]
        out.append(e)
    return out
