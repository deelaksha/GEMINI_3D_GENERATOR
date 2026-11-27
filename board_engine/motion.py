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
        rng = m.get('range')
        if not (isinstance(rng, list) and len(rng) == 2 and all(_num(v) for v in rng) and rng[0] < rng[1]):
            bad(m, '"range" must be [from, to] with from < to (0 is the position as modelled).')
            continue
        mo = {'id': m['id'], 'type': kind, 'boards': boards, 'on': on, 'range': [float(rng[0]), float(rng[1])]}
        if kind == 'rotate':
            if m.get('axis') not in AXES or not _vec3(m.get('pivot')):
                bad(m, 'a rotation needs "axis": "x"|"y"|"z" and "pivot": [x, y, z] (a point on the turning axis).')
                continue
            if not (-360 <= rng[0] and rng[1] <= 360):
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
        first = {}                                   # (static board, side of 0) -> (value, moving board, hit)
        for v in samples:                            # outwards from 0, so the first hit is the nearest one
            for b, p in posed[v].items():
                for s in others:
                    if (s, v > 0) in first or frozenset((b, s)) in hinged:
                        continue
                    if _box_gap(p.world_aabb(), plates[s].world_aabb()) > 0:
                        continue
                    check_budget()
                    hits = plate_interference(p, plates[s])
                    if hits:
                        first[(s, v > 0)] = (v, b, hits[0])
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
    return out


def model_motions(motions):
    """Motions for the 3D view (world vectors; the view animates each over its range)."""
    out = []
    for m in motions:
        e = {'id': m['id'], 'type': m['type'], 'boards': m['boards'], 'on': m['on'], 'range': m['range']}
        if m['type'] == 'rotate':
            e.update(axis=[1.0 if a == m['axis'] else 0.0 for a in AXES], pivot=m['pivot'])
        else:
            e['direction'] = [1.0 if a == m['direction'] else 0.0 for a in AXES]
        out.append(e)
    return out
