"""
Moving parts of a board design: "motions" that turn a group of boards about a pivot or slide it along an axis.

  "motions": [{"id", "type": "rotate", "boards": [ids], "on": id, "axis": "x"|"y"|"z", "pivot": [x, y, z],
               "range": [from, to] (degrees; 0 = as modelled), "axle"?: {"diameter": mm}}
            | {"id", "type": "slide", "boards": [ids], "on": id, "direction": "x"|"y"|"z", "range": [from, to] (mm)}]

The boards move together, mounted on the board "on" - a static board, or a board moved by another motion (a jaw on a
head on a neck: the child rides on its parent and moves relative to it). A motion "driven_by" a crank may be pushed
through a connecting rod instead of a ratio: "link": {"rod": board id, "from": pin on the crank [x, y, z], "to": pin on
this motion's boards [x, y, z], "pin"?: {"diameter": mm}} - a four-bar (rocker) or slider-crank, solved exactly at every
crank position; the rod is a real moving part pinned at both ends. An "axle" cuts a dowel hole of that diameter through
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
RETAIN = ('collar', 'press', 'cotter', 'washer', 'wedge')   # what keeps an axle in its supports (axle.retain)


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
            bad(m, '"on" must be the id of the board it is mounted on (not one of the moving boards).')
            continue
        twice = [b for b in boards if b in taken]
        if twice:
            bad(m, f"board(s) {', '.join(twice)} already move with motion '{taken[twice[0]]}'.")
            continue
        rng, driver = m.get('range'), m.get('driven_by')
        if driver is not None and not isinstance(driver, str):
            bad(m, '"driven_by" must be the id of the motion that drives it.')
            continue
        link = m.get('link')
        if link is not None:
            if not (isinstance(link, dict) and isinstance(link.get('rod'), str) and _vec3(link.get('from'))
                    and _vec3(link.get('to'))):
                bad(m, '"link" must be {"rod": board id, "from": [x, y, z] (pin on the crank), "to": [x, y, z] (pin on '
                       'this motion\'s boards), "pin"?: {"diameter": mm}}.')
                continue
            pin = link.get('pin')
            if pin is not None and not (isinstance(pin, dict) and _num(pin.get('diameter')) and 1 <= pin['diameter'] <= 20):
                bad(m, '"link.pin" must be {"diameter": mm} between 1 and 20.')
                continue
            rod = link['rod']
            if driver is None or m.get('ratio') is not None:
                bad(m, 'a "link" needs "driven_by" (the crank motion that pushes the rod) and no "ratio" (the rod sets it).')
                continue
            if rod not in ids or rod in boards or rod == on or rod in taken:
                bad(m, f"the rod '{rod}' must be a board of its own that no motion moves (not '{on}' or a moving board).")
                continue
            length = math.dist(link['from'], link['to'])
            if length < 1:
                bad(m, 'the rod\'s pins "from" and "to" must be apart.')
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
        if m.get('_flip') in (-1, 1):
            mo['_flip'] = m['_flip']        # mirrored assembly instance: a "ratio" coupling changes sense with it
        if link is not None:
            mo['link'] = {'rod': link['rod'], 'from': [float(v) for v in link['from']], 'to': [float(v) for v in link['to']],
                          'pin': float((link.get('pin') or {}).get('diameter', 4)), 'length': length}
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
            sup = (axle or {}).get('supports')
            if sup is not None and not (isinstance(sup, list) and all(isinstance(n, str) for n in sup)):
                bad(m, '"axle.supports" must list the ids of the boards that also carry the axle.')
                continue
            unknown = [n for n in sup or [] if n not in ids and not copies.get(n)]
            if unknown:
                bad(m, f"\"axle.supports\" names unknown board(s) {', '.join(unknown)}.")
                continue
            supports = [g for n in sup or [] for g in ([n] if n in ids else copies[n])]
            if (axle or {}).get('retain') is not None and axle['retain'] not in RETAIN:
                bad(m, f'"axle.retain" must be one of {", ".join(RETAIN)} (what keeps the axle and the parts on it in place).')
                continue
            mo.update(axis=m['axis'], pivot=[float(v) for v in m['pivot']],
                      axle={'diameter': float(axle['diameter']),
                            **({'supports': supports} if sup is not None else {}),
                            **({'retain': axle['retain']} if axle.get('retain') is not None else {})} if axle else None)
        else:
            if m.get('direction') not in AXES:
                bad(m, 'a slide needs "direction": "x"|"y"|"z".')
                continue
            mo['direction'] = m['direction']
        for b in boards + ([link['rod']] if link is not None else []):
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
                        'pressure_angle': float(prof['pressure_angle']) if _num(prof.get('pressure_angle')) else 20.0,
                        'profile': prof}
    return out


def _link(motions, gears, diags, diag, line):
    """Resolve "driven_by": chains in order, the ratio from the meshing gears (or "ratio"), the range from the driver."""
    by_id = {m['id']: m for m in motions}
    done, out = set(), []

    def bad(m, msg):
        diags.append(diag('error', 'MOTION_INVALID', f"Motion '{m['id']}': {msg}", line=line))
    mover = {b: m['id'] for m in motions for b in m['boards']}
    rods = {m['link']['rod'] for m in motions if m.get('link')}
    for m in motions:
        m['parent'] = mover.get(m['on'])            # mounted on a moving board: it rides on that motion
    for m in list(motions):
        seen, p = [m['id']], m['parent']
        while p is not None and p not in seen:
            seen.append(p)
            p = by_id[p]['parent']
        if m['on'] in rods or p is not None:
            bad(m, f"it cannot be mounted on the connecting rod '{m['on']}'." if m['on'] in rods else
                f"its mounts go round in a loop ({' -> '.join(seen + [p])}): each motion must ride on a board that "
                f"does not ride on it.")
            motions.remove(m)
            by_id.pop(m['id'])

    def resolve(m, path):
        if m['id'] in done:
            return True
        drv_id = m.get('driven_by')
        if drv_id is None:
            done.add(m['id'])
            return True
        if drv_id in path or drv_id == m['id']:
            loop = path[path.index(drv_id):] if drv_id in path else []
            bad(m, f"its drivers go round in a loop ({' -> '.join(loop + [m['id'], drv_id])}).")
            return False
        drv = by_id.get(drv_id)
        if drv is None or not resolve(drv, path + [m['id']]) or drv['range'] is None:
            if drv is None:
                bad(m, f"\"driven_by\" names no motion '{drv_id}'.")
            return False
        if m.get('link'):
            problem = _link_problem(drv, m)
            if problem:
                bad(m, problem)
                return False
            table, jams, worst = _link_table(drv, m)
            m['link']['table'] = table
            m['range'] = [min(v for _d, v in table), max(v for _d, v in table)]
            calc = _link_calc(drv, m)
            for v, last in jams:
                unit = '°'
                lo, hi = (last, drv['range'][1]) if v < 0 else (drv['range'][0], last)
                diags.append(diag('error', 'LINKAGE_JAM', f"Motion '{m['id']}': at {v:g}{unit} of '{drv['id']}' the rod "
                                  f"'{m['link']['rod']}' ({m['link']['length']:.1f} mm) can no longer reach between its pins, "
                                  f"so the mechanism locks there. Limit '{drv['id']}' to [{lo:g}, {hi:g}]{unit}, or change the "
                                  f"lengths: a crank turns all the way round only when it is the shortest link and shortest "
                                  f"+ longest <= the other two (Grashof).", line=line, calc=calc + [
                                      f"last position reached: {last:g}{unit} of '{drv['id']}'"]))
            if worst < TRANSMISSION_MIN:
                diags.append(diag('warning', 'LINKAGE_TRANSMISSION', f"Motion '{m['id']}': the rod '{m['link']['rod']}' "
                                  f"pushes almost along the arm it drives (transmission angle down to {worst:.0f}°, best "
                                  f"is 90°), so it needs a lot of force there and may stall or flex. Move the pins so the "
                                  f"rod meets the arm closer to square.", line=line,
                                  calc=calc + [f"worst transmission angle over the cycle = {worst:.1f}° "
                                               f"(below {TRANSMISSION_MIN:g}° the drive binds)"]))
            flips = _change_points(drv, m, table)
            if flips:
                where = ', '.join(f'{v:g}°' for v in flips)
                diags.append(diag('warning', 'LINKAGE_CHANGE_POINT', f"Motion '{m['id']}': at {where} of '{drv['id']}' the "
                                  f"crank, the rod '{m['link']['rod']}', the arm and the frame line up (a change point: "
                                  f"shortest + longest link = the other two), so from there the linkage can carry on "
                                  f"either way - as drawn or crossed over - and the real one may flip or lock. Make "
                                  f"shortest + longest shorter than the other two, or keep '{drv['id']}' clear of "
                                  f"{'that angle' if len(flips) == 1 else 'those angles'}.", line=line,
                                  calc=calc + [f"all four pivots in line at {where} of '{drv['id']}' (the rod meets the "
                                               f"arm at 0° or 180° there)"]))
            drive = _drive_profile(drv, m, table)
            if drive:
                diags.append(diag('info', 'LINKAGE_DRIVE', drive[0], line=line, calc=calc + drive[1]))
            done.add(m['id'])
            return True
        if 'ratio' in m:
            m['ratio'] *= m.get('_flip', 1) * drv.get('_flip', 1)      # a mirrored copy: both senses as mirrored
            meshing = [(a, b) for a in drv['boards'] if a in gears for b in m['boards'] if b in gears
                       if _meshes(gears[a], gears[b], GEAR_DISTANCE_TOL)]
            if meshing:
                a, b = meshing[0]
                want = -gears[a]['teeth'] / gears[b]['teeth']
                if abs(m['ratio'] - want) > 1e-6 * max(1.0, abs(want)):
                    diags.append(diag('error', 'GEAR_RATIO', f"Motion '{m['id']}': its gear '{b}' meshes with '{a}' of "
                                      f"'{drv_id}', so it turns at {want:.4g} (the other way, {gears[a]['teeth']} : "
                                      f"{gears[b]['teeth']} teeth), not at the \"ratio\" {m['ratio']:g} written. Remove "
                                      f"\"ratio\" (meshing gears set it) or write {want:.6g}.", line=line,
                                      calc=[f"ratio = -z_driver / z_driven = -{gears[a]['teeth']} / {gears[b]['teeth']} "
                                            f"= {want:.6g}", f"written: {m['ratio']:g}"]))
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
    _check_inputs(out, gears, diags, diag, line)
    return out


def _meshes(a, b, tol):
    """Whether two gears (find_gears) are in one plane, of one module, at the meshing centre distance (within tol)."""
    return (a['thin'] == b['thin'] and min(a['span'][1], b['span'][1]) - max(a['span'][0], b['span'][0]) > 0
            and abs(a['module'] - b['module']) < 1e-6
            and abs(math.dist(a['centre'], b['centre']) - a['module'] * (a['teeth'] + b['teeth']) / 2) <= tol)


MESH_FIND_TOL = 0.5         # mm: two gears this close to their meshing distance are taken to mesh


def _check_inputs(motions, gears, diags, diag, line):
    """M-14: meshing gears whose motions are independent (an undeclared coupling), and mechanisms with more than one
    input (the spec's rule: one crank or motor drives everything)."""
    by_id = {m['id']: m for m in motions}

    def root(mid):
        seen = []
        while by_id[mid].get('driven_by') in by_id and mid not in seen:
            seen.append(mid)
            mid = by_id[mid]['driven_by']
        return mid
    owner = {b: m['id'] for m in motions for b in m['boards'] if b in gears}
    declared = {frozenset(m['gears']) for m in motions if m.get('gears')}
    ids = sorted(owner)
    for x, a in enumerate(ids):
        for b in ids[x + 1:]:
            ma, mb = owner[a], owner[b]
            if root(ma) == root(mb) or frozenset((a, b)) in declared or not _meshes(gears[a], gears[b], MESH_FIND_TOL):
                continue
            free = mb if by_id[mb].get('driven_by') is None else ma
            other = ma if free == mb else mb
            diags.append(diag('warning', 'MOTION_UNDECLARED_MESH', f"Gears '{a}' (motion '{ma}') and '{b}' (motion "
                              f"'{mb}') mesh, but their motions are independent, so the compiler moves each on its own and "
                              f"their teeth clash. Give '{free}' \"driven_by\": \"{other}\" (and no \"range\") so it "
                              f"follows, or move the gears apart.", line=line,
                              calc=[f"centre distance {math.dist(gears[a]['centre'], gears[b]['centre']):.2f} mm = module x "
                                    f"(z1 + z2) / 2 = {gears[a]['module'] * (gears[a]['teeth'] + gears[b]['teeth']) / 2:g} mm"]))
    kids = {}
    for m in motions:
        kids.setdefault(root(m['id']), []).append(m)
    inputs = [r for r, ms in kids.items() if by_id[r].get('driven_by') is None
              and any(m.get('driven_by') or m.get('link') or any(b in gears for b in m['boards']) for m in ms)]
    if len(inputs) > 1:
        diags.append(diag('warning', 'MOTION_INPUTS', f"The mechanism has {len(inputs)} independent inputs "
                          f"({', '.join(repr(i) for i in inputs)}): each turns on its own. A machine normally has ONE input - "
                          f"a hand crank or motor - that drives the rest (\"driven_by\"); if they really are separate "
                          f"mechanisms, keep them apart.", line=line,
                          calc=[f"input '{i}' drives {', '.join(m['id'] for m in kids[i]) }" for i in inputs]))


TRANSMISSION_MIN = 30.0     # degrees: a rod meeting its arm flatter than this binds instead of driving it
IDENTITY = ([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], [0.0, 0.0, 0.0])


def _local(m, v):
    """Transform (R, t) of a motion at value v, in the frame of the board it is mounted on (x -> R x + t)."""
    if m['type'] == 'slide':
        k = AXES.index(m['direction'])
        return IDENTITY[0], [v if i == k else 0.0 for i in range(3)]
    R, p = _rotation(m['axis'], v), m['pivot']
    return R, [p[i] - sum(R[i][j] * p[j] for j in range(3)) for i in range(3)]


def _then(a, b):
    """The transform b followed by a."""
    return G.mat_mul(a[0], b[0]), [sum(a[0][i][j] * b[1][j] for j in range(3)) + a[1][i] for i in range(3)]


def _at(T, x):
    return [sum(T[0][i][j] * x[j] for j in range(3)) + T[1][i] for i in range(3)]


def _plane(k):
    """The two axes across axis k, in the order a positive turn about k runs (x: y->z, y: z->x, z: x->y)."""
    return (k + 1) % 3, (k + 2) % 3


def _link_problem(drv, m):
    if drv['type'] != 'rotate':
        return f"the rod must be pushed by a turning crank: '{drv['id']}' slides."
    if drv.get('parent') != m.get('parent'):
        return f"the crank '{drv['id']}' and this motion must be mounted on the same frame (both static, or both riding on one motion)."
    if m['type'] == 'rotate' and m['axis'] != drv['axis']:
        return f"a rocker must turn about the same axis as its crank ({drv['axis']}): the linkage works in one plane."
    if m['type'] == 'slide' and m['direction'] == drv['axis']:
        return f"a slider must move across the crank's axis ({drv['axis']}), in the plane the crank turns in."
    return None


def _solve_link(drv, m, v, prev):
    """Value of the linked motion m with its crank drv at v: the position where the rod again spans its length,
    nearest to prev (the linkage moves continuously). None if the rod cannot reach (the mechanism locks)."""
    lk = m['link']
    P, to, L = _at(_local(drv, v), lk['from']), lk['to'], lk['length']
    if m['type'] == 'rotate':
        k = AXES.index(m['axis'])
        i, j = _plane(k)
        c = m['pivot']
        qx, qy, px, py = to[i] - c[i], to[j] - c[j], P[i] - c[i], P[j] - c[j]
        rho, D, d2 = math.hypot(qx, qy), math.hypot(px, py), L * L - (to[k] - P[k]) ** 2
        if d2 < 0 or D < 1e-9 or rho < 1e-9:
            return None
        a = (rho * rho - d2 + D * D) / (2 * D)          # circle of the arm's pin meets the circle the rod reaches
        h2 = rho * rho - a * a
        if h2 < -1e-6 * rho * rho:
            return None
        base, delta, phi0 = math.atan2(py, px), math.atan2(math.sqrt(max(0.0, h2)), a), math.atan2(qy, qx)
        cands = [math.degrees(base + sg * delta - phi0) for sg in (1, -1)]
        cands = [prev + ((x - prev + 180.0) % 360.0 - 180.0) for x in cands]
    else:
        k = AXES.index(m['direction'])
        w = [to[x] - P[x] for x in range(3)]
        disc = w[k] ** 2 - (sum(x * x for x in w) - L * L)
        if disc < -1e-9:
            return None
        cands = [-w[k] + sg * math.sqrt(max(0.0, disc)) for sg in (1, -1)]
    return min(cands, key=lambda x: abs(x - prev))


def _rod_local(drv, m, v_drv, v):
    """Transform of the rod in the frame both are mounted on: it turns in the crank's plane to span its two pins."""
    lk = m['link']
    k = AXES.index(drv['axis'])
    i, j = _plane(k)
    P, Q = _at(_local(drv, v_drv), lk['from']), _at(_local(m, v), lk['to'])
    ang = lambda a, b: math.atan2(b[j] - a[j], b[i] - a[i])
    R = _rotation(drv['axis'], math.degrees(ang(P, Q) - ang(lk['from'], lk['to'])))
    return R, [P[x] - sum(R[x][y] * lk['from'][y] for y in range(3)) for x in range(3)]


def _transmission(drv, m, v_drv, v):
    """Transmission angle folded to 0..90 (90 = the rod pushes square on what it drives)."""
    lk = m['link']
    k = AXES.index(drv['axis'])
    i, j = _plane(k)
    P, Q = _at(_local(drv, v_drv), lk['from']), _at(_local(m, v), lk['to'])
    rod = (P[i] - Q[i], P[j] - Q[j])
    e = AXES.index(m['direction']) if m['type'] == 'slide' else None
    other = (m['pivot'][i] - Q[i], m['pivot'][j] - Q[j]) if e is None else (float(e == i), float(e == j))
    cos = abs(rod[0] * other[0] + rod[1] * other[1]) / max(math.hypot(*rod) * math.hypot(*other), 1e-12)
    ang = math.degrees(math.acos(min(1.0, cos)))        # 0..90 between the rod and the arm / the slide line
    return ang if e is None else 90.0 - ang             # an arm is pushed best square on, a slider straight along


def _link_table(drv, m):
    """-> ([(crank value, motion value)] over the crank's range, jams [(where, last reached)], worst transmission)."""
    a, b = drv['range']
    step = max(2.0, (b - a) / 360.0)
    rows, jams, worst = {0.0: 0.0}, [], _transmission(drv, m, 0.0, 0.0)
    for end in (min(a, 0.0), max(b, 0.0)):
        n, prev, last = max(1, math.ceil(abs(end) / step)), 0.0, 0.0
        for k in range(1, n + 1):
            v = end * k / n
            got = _solve_link(drv, m, v, prev)
            if got is None:
                if a - 1e-9 <= v <= b + 1e-9:
                    jams.append((round(v, 3), round(last, 3)))
                break
            rows[v], prev, last = got, got, v
            if a - 1e-9 <= v <= b + 1e-9:
                worst = min(worst, _transmission(drv, m, v, got))
    return sorted([round(v, 4) + 0.0, round(x, 4) + 0.0] for v, x in rows.items() if a - 1e-9 <= v <= b + 1e-9), jams, worst


def _change_points(drv, m, table):
    """Crank values (within the solved table) where a four-bar's crank lines up with its frame and the rod with the
    arm: there the two ways the linkage can be assembled meet (a parallelogram may turn crossed). [] for a slider."""
    if m['type'] != 'rotate' or len(table) < 2:
        return []
    lk, k = m['link'], AXES.index(drv['axis'])
    i, j = _plane(k)
    c, q, to = drv['pivot'], m['pivot'], lk['to']
    psi = math.degrees(math.atan2(q[j] - c[j], q[i] - c[i]))            # the frame line, seen from the crank axle
    phi = math.degrees(math.atan2(lk['from'][j] - c[j], lk['from'][i] - c[i]))
    lo, hi = table[0][0], table[-1][0]
    v, out = psi - phi + math.ceil((lo - (psi - phi)) / 180.0 - 1e-9) * 180.0, []
    while v <= hi + 1e-9:
        P = _at(_local(drv, v), lk['from'])
        rho, D = math.hypot(to[i] - q[i], to[j] - q[j]), math.hypot(P[i] - q[i], P[j] - q[j])
        d2 = lk['length'] ** 2 - (to[k] - P[k]) ** 2
        if D > 1e-9 and rho > 1e-9:
            a = (rho * rho - d2 + D * D) / (2 * D)
            if abs(rho * rho - a * a) <= 1e-4 * rho * rho and not any(abs((v - w + 180.0) % 360.0 - 180.0) < 1e-6 for w in out):
                out.append(round(v, 3) + 0.0)
        v += 180.0
    return out


def _drive_profile(drv, m, table):
    """-> (message, calc) on how hard the crank works through the cycle: the follower's speed per degree of crank
    (its inverse is the mechanical advantage), where it peaks and where the follower turns back."""
    if len(table) < 3:
        return None
    rate = [((table[i + 1][1] - table[i][1]) / (table[i + 1][0] - table[i][0]), (table[i][0] + table[i + 1][0]) / 2)
            for i in range(len(table) - 1) if table[i + 1][0] > table[i][0]]
    if not rate:
        return None
    peak, at = max(rate, key=lambda r: abs(r[0]))
    back = [round(rate[i][1]) for i in range(1, len(rate)) if rate[i - 1][0] * rate[i][0] < 0]
    turns = f" It turns back at {', '.join(f'{v:g}°' for v in back)} of the crank (the ends of its stroke)." if back else ''
    if m['type'] == 'rotate':
        msg = (f"Motion '{m['id']}': the crank '{drv['id']}' needs up to {abs(peak):.2f} x the torque it delivers to "
               f"'{m['id']}' (near {at:.0f}° of the crank, where the arm moves {abs(peak):.2f}° per crank degree).{turns}")
        calc = [f"torque at the crank = torque on the arm x d(arm angle) / d(crank angle); peak {abs(peak):.3f} at {at:.0f}°"]
    else:
        arm = abs(peak) * 180 / math.pi
        msg = (f"Motion '{m['id']}': the crank '{drv['id']}' needs up to the slider's force x {arm:.1f} mm of torque "
               f"(near {at:.0f}° of the crank, where the slider moves {abs(peak):.2f} mm per crank degree).{turns}")
        calc = [f"torque at the crank = slider force x d(slide) / d(crank angle in radians); peak {arm:.2f} mm at {at:.0f}°"]
    return msg, calc


def _link_calc(drv, m):
    lk = m['link']
    k = AXES.index(drv['axis'])
    i, j = _plane(k)
    flat = lambda p, q: math.hypot(p[i] - q[i], p[j] - q[j])
    out = [f"crank '{drv['id']}': pin {flat(lk['from'], drv['pivot']):.1f} mm from its axle",
           f"rod '{lk['rod']}': {lk['length']:.1f} mm between pins"]
    if m['type'] == 'rotate':
        out += [f"arm of '{m['id']}': pin {flat(lk['to'], m['pivot']):.1f} mm from its axle",
                f"frame: axles {flat(drv['pivot'], m['pivot']):.1f} mm apart"]
    return out


def _interp(table, x):
    import bisect
    xs = [r[0] for r in table]
    i = bisect.bisect_left(xs, x)
    if i <= 0:
        return table[0][1]
    if i >= len(xs):
        return table[-1][1]
    (x0, y0), (x1, y1) = table[i - 1], table[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0 or 1.0)


def train_values(motions, root, v):
    """Values of every motion driven (through gears, belts and rods) from `root` when it is at v."""
    by_id = {m['id']: m for m in motions}
    kids = {}
    for m in motions:
        kids.setdefault(m.get('driven_by'), []).append(m)
    vals, todo = {root: v}, [root]
    while todo:
        d = todo.pop()
        for m in kids.get(d, []):
            if m['id'] in vals:
                continue
            if m.get('link'):
                guess = _interp(m['link']['table'], vals[d])
                got = _solve_link(by_id[d], m, vals[d], guess)
                vals[m['id']] = guess if got is None else got
            else:
                vals[m['id']] = vals[d] * m['ratio']
            todo.append(m['id'])
    return vals


def board_poses(motions, values):
    """World transform of every moving board (and connecting rod) with each motion at values[id] (default 0): a
    motion riding on a moving board moves with it."""
    by_id, memo, out = {m['id']: m for m in motions}, {}, {}

    def frame(mid):
        if mid is None:
            return IDENTITY
        if mid not in memo:
            m = by_id[mid]
            memo[mid] = _then(frame(m.get('parent')), _local(m, values.get(mid, 0.0)))
        return memo[mid]
    for m in motions:
        for b in m['boards']:
            out[b] = (m['id'], frame(m['id']))
        if m.get('link'):
            drv = by_id[m['driven_by']]
            out[m['link']['rod']] = ('rod:' + m['id'], _then(frame(m.get('parent')), _rod_local(
                drv, m, values.get(drv['id'], 0.0), values.get(m['id'], 0.0))))
    return out


def _inside_profile(b, point, k, r):
    """Whether a hole of radius r at point lies inside the board's shaped outline (a plain board: its box)."""
    from .shapes import shape_polygon
    prof = b.get('profile')
    if not isinstance(prof, dict):
        return True
    i, j = [x for x in range(3) if x != k]
    q = [point[i] - b['position'][i], point[j] - b['position'][j]]
    try:
        got = shape_polygon(prof)
    except Exception:
        return True                     # the profile's own error is reported by the compiler
    if got[0] == 'circle':
        return math.dist(q, got[1]) <= got[2] / 2 - r
    return G.point_in_polygon(q, got[0]) and G.dist_to_boundary(q, got[0]) >= r


def _cut_hole(by_id, thickness, bids, point, k, d, hid, note):
    """Cut a round hole of diameter d along axis k at point into each listed raw board it passes square through."""
    holed = []
    for bid in bids:
        b = by_id.get(bid)
        if not b or b.get('rotate') or not (_vec3(b.get('position')) and _vec3(b.get('size'))):
            continue
        if _thin_axis(b, thickness) != k:
            continue
        lo, size = b['position'], b['size']
        if not all(lo[i] + d / 2 < point[i] < lo[i] + size[i] - d / 2 for i in range(3) if i != k):
            continue
        if not _inside_profile(b, point, k, d / 2):
            continue
        centre = list(point)
        centre[k] = lo[k] + size[k] / 2.0
        b['openings'] = list(b.get('openings') or []) + [
            {'id': hid, 'kind': 'hole', 'shape': 'circle', 'center': centre, 'diameter': d, 'note': note}]
        holed.append(bid)
    return holed


def add_axle_holes(data, motions, thickness, diags, diag):
    by_id = {b.get('id'): b for b in data.get('boards') or [] if isinstance(b, dict)}
    motion_of = {m['id']: m for m in motions}
    for m in motions:
        if m['type'] != 'rotate' or not m['axle']:
            continue
        k = AXES.index(m['axis'])
        d = m['axle']['diameter']
        supports = [b for b in m['axle'].get('supports') or [] if b not in m['boards'] and b != m['on']]
        holed = _cut_hole(by_id, thickness, m['boards'] + [m['on']] + supports, m['pivot'], k, d, f"axle-{m['id']}",
                          f"axle of motion {m['id']}: Ø{d:g} mm dowel")
        moving = [b for b in holed if b in m['boards']]
        if not moving or m['on'] not in holed:
            diags.append(diag('error', 'MOTION_AXLE', f"Motion '{m['id']}': its axle along {m['axis']} through "
                              f"[{', '.join(f'{v:g}' for v in m['pivot'])}] must pass square through a moving board and "
                              f"through '{m['on']}' (both thin along {m['axis']}, the pivot inside both with room for the "
                              f"Ø{d:g} mm hole). It passes through: {', '.join(holed) or 'none of them'}."))
            continue
        missed = [b for b in supports if b not in holed]
        if missed:
            diags.append(diag('error', 'MOTION_AXLE', f"Motion '{m['id']}': its axle along {m['axis']} through "
                              f"[{', '.join(f'{v:g}' for v in m['pivot'])}] does not pass square through the support(s) "
                              f"{', '.join(missed)} listed in \"axle.supports\" (each must be thin along {m['axis']}, with the "
                              f"pivot inside it and room for the Ø{d:g} mm hole). Move them onto the axle line or leave "
                              f"them out of \"supports\"."))
        span = [by_id[b] for b in holed]
        length = max(b['position'][k] + b['size'][k] for b in span) - min(b['position'][k] for b in span)
        m['axle']['boards'] = holed
        diags.append(diag('info', 'MOTION_AXLE', f"Motion '{m['id']}': cut a Ø{d:g} mm dowel about {math.ceil(length + 4)} mm "
                          f"long as its axle; it passes through {', '.join(holed)}."))
        if m['axle'].get('supports') is not None and not m['axle'].get('retain'):
            diags.append(diag('warning', 'AXLE_UNRETAINED', f"Motion '{m['id']}': nothing keeps its Ø{d:g} mm axle (through "
                              f"{', '.join(holed)}) from sliding out, or the parts on it from sliding along it. Add "
                              f"\"retain\" to the axle: \"collar\" or \"washer\" (a small board fixed on each free end), "
                              f"\"press\" (a press-fit hole in one support), \"cotter\" or \"wedge\" (a cross pin).",
                              calc=[f"axle about {math.ceil(length + 4)} mm long through {len(holed)} boards; no "
                                    f"\"retain\" given"]))
    for m in motions:
        lk, drv = m.get('link'), motion_of.get(m.get('driven_by'))
        if not lk or not drv or drv['type'] != 'rotate':
            continue
        k, d, rod = AXES.index(drv['axis']), lk['pin'], lk['rod']
        for end, point, side in (('crank', lk['from'], drv['boards']), ('arm', lk['to'], m['boards'])):
            holed = _cut_hole(by_id, thickness, side + [rod], point, k, d, f"pin-{m['id']}-{end}",
                              f"{end} pin of the rod of motion {m['id']}: Ø{d:g} mm dowel")
            lk.setdefault('pins', {})[end] = holed          # the pin is a solid through these (kinematics.solids)
            if rod not in holed or not set(holed) & set(side):
                diags.append(diag('error', 'MOTION_PIN', f"Motion '{m['id']}': the rod's {end} pin at "
                                  f"[{', '.join(f'{v:g}' for v in point)}] must pass square through the rod '{rod}' and a "
                                  f"board of '{(drv if end == 'crank' else m)['id']}' (all thin along {drv['axis']}, with "
                                  f"room for the Ø{d:g} mm hole). It passes through: {', '.join(holed) or 'none of them'}."))


def _rotation(axis, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == 'x':
        return [[1, 0, 0], [0, c, -s], [0, s, c]]
    if axis == 'y':
        return [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def _placed(design, comp, T):
    """The plate of `comp` moved by the transform T."""
    from .canvas import _euler_xyz
    from .model import Plate
    pos, rot = comp['placement']['position'], comp['placement']['rotation']
    if T[0] is not IDENTITY[0]:
        rot = _euler_xyz(G.mat_mul(T[0], G.rotation_matrix(rot)))
    return Plate(design, dict(comp, placement={'position': _at(T, pos), 'rotation': rot}))


def _moved(design, comp, m, value):
    """The plate of `comp` with its motion at `value` (degrees or mm)."""
    return _placed(design, comp, _local(m, value))


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


GUIDE_GAP = 3.0             # mm: a board this close beside a sliding part, on both sides across the slide, guides it
HINGE_SLACK = 2.0           # mm: a motion's axis may lie this far beyond door thickness + gap from its hinge edge


def _fmt(v):
    return f"{round(v, 1) + 0.0:g}"


def _hinge_gap(j):
    from .validation import HINGE
    return float(j.get('gap', HINGE['default_gap']))


def _guided(plates, group, others, k, mount):
    """Whether boards on both sides across the slide direction k (within GUIDE_GAP, beside it along the slide) hold
    the sliding group in line, or the slide runs straight off its mount (a lid lifted off needs no guide)."""
    boxes = [plates[b].world_aabb() for b in group]
    lo = [min(b[0][i] for b in boxes) for i in range(3)]
    hi = [max(b[1][i] for b in boxes) for i in range(3)]
    ov = [min(hi[i], mount[1][i]) - max(lo[i], mount[0][i]) for i in range(3)]
    if min(range(3), key=lambda i: ov[i]) == k:
        return True
    for i in (x for x in range(3) if x != k):
        j = 3 - i - k
        side = {-1: False, 1: False}
        for s in others:
            slo, shi = plates[s].world_aabb()
            if min(shi[j], hi[j]) - max(slo[j], lo[j]) <= 0 or min(shi[k], hi[k]) - max(slo[k], lo[k]) <= 0:
                continue
            if lo[i] - GUIDE_GAP <= shi[i] <= lo[i] + TOUCH:
                side[-1] = True
            if hi[i] - TOUCH <= slo[i] <= hi[i] + GUIDE_GAP:
                side[1] = True
        if side[-1] and side[1]:
            return True
    return False


def _hinge_mismatch(design, plates, m, j):
    """-> (message, calc) when a rotate motion does not turn about the hinge edge of the door it moves, else None."""
    from .model import edge_frame
    door = plates.get(j['a'])
    if door is None or not isinstance(j.get('a_edge'), int) or not 0 <= j['a_edge'] < len(door.outline):
        return None
    a, d, _n, L = edge_frame(door.outline, j['a_edge'])
    p0, p1 = door.frame.to_world([a[0], a[1], 0.0]), door.frame.to_world([a[0] + d[0] * L, a[1] + d[1] * L, 0.0])
    mid = [(p0[i] + p1[i]) / 2.0 for i in range(3)]
    k = AXES.index(m['axis'])
    along = abs(p1[k] - p0[k]) / max(math.dist(p0, p1), 1e-9)
    dist = _axis_distance(m, mid)
    tol = door.t + _hinge_gap(j) + HINGE_SLACK
    if along >= math.cos(math.radians(5)) and dist <= tol:
        return None
    run = max(range(3), key=lambda i: abs(p1[i] - p0[i]))
    want = [round(v, 1) + 0.0 for v in mid]
    want[run] = m['pivot'][run] if run == k else want[run]
    msg = (f"Motion '{m['id']}': the hinge '{j['id']}' is on the edge of '{j['a']}' that runs along {AXES[run]} through "
           f"[{', '.join(_fmt(v) for v in mid)}], but the motion turns about {m['axis']} through "
           f"[{', '.join(f'{v:g}' for v in m['pivot'])}]"
           + (f", {dist:.0f} mm from that edge." if along >= math.cos(math.radians(5)) else ", across that edge.")
           + f" A hinged door turns about its hinge edge: set \"axis\": \"{AXES[run]}\" and the pivot on that edge (about "
             f"[{', '.join(f'{v:g}' for v in want)}]), or put the hinge on the edge it turns about.")
    return msg, [f"hinge edge of '{j['a']}': from [{', '.join(_fmt(v) for v in p0)}] to [{', '.join(_fmt(v) for v in p1)}]",
                 f"motion axis {m['axis']} through [{', '.join(f'{v:g}' for v in m['pivot'])}]: {dist:.1f} mm from the edge "
                 f"(at most {tol:g} mm = door {door.t:g} + hinge gap {_hinge_gap(j):g} + {HINGE_SLACK:g})"]


def check_motions(design, plates, motions):
    """-> issues (validation format) for every motion: mounting, fixed joints (of its boards and its rod), pivot /
    guide hardware and the hinge, slide direction, travel clearance (kinematics.scan: no part moves more than the
    running clearance between two checked positions; the first contact is bisected)."""
    from .validation import TOL, issue
    from . import kinematics as K
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
    rod_of = lambda t: [t['link']['rod']] if t.get('link') else []
    joined = [j for j in design['joints'] if j.get('status') == 'joined']
    hinges = [j for j in joined if j['type'] == 'hinge']
    hinged = {frozenset((j['a'], j['b'])) for j in hinges}
    solid = K.solids(design, plates, motions)
    grown = {}
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
        # a door hangs on its hinges up to the hinge gap off the carcass
        allow = TOUCH + max([_hinge_gap(j) for j in hinges if m['on'] in (j['a'], j['b'])
                             and {j['a'], j['b']} & set(group)] or [0.0])
        if gaps[near] > allow:
            out.append(issue('MOTION_NOT_MOUNTED', 'error', 'assembly',
                             f"Motion '{m['id']}': the moving boards do not touch '{m['on']}', the board they are mounted on "
                             f"(closest: '{near}', {gaps[near]:.1f} mm away). Move them onto it or mount them on the board "
                             f"they touch.", group + [m['on']],
                             calc=[f"gap '{near}' - '{m['on']}' = {gaps[near]:.2f} mm (must be <= {allow:g} mm)"]))
            continue
        moving = set(group)
        fixed = [j for j in joined if j['type'] != 'hinge' and (j['a'] in moving) != (j['b'] in moving)]
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
        rod = m['link']['rod'] if m.get('link') else None
        tied = [j for j in joined if rod in (j['a'], j['b'])] if rod in plates else []
        if tied:                                     # a connecting rod is held only by its two pins
            j = tied[0]
            other = j['b'] if j['a'] == rod else j['a']
            out.append(issue('MOTION_LOCKED', 'error', 'joint',
                             f"Motion '{m['id']}': its connecting rod '{rod}' is fixed to '{other}' by the {j['type']} joint "
                             f"'{j['id']}', so the mechanism cannot move. Remove that connection: the rod is held only by "
                             f"its two pins and must move freely between them.", [rod, other], joint=j['id'],
                             calc=[f"{len(tied)} fixed joint(s) on the rod '{rod}': " + ', '.join(x['id'] for x in tied[:6])]))
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
            if not _guided(plates, group, [s for s in plates if s not in moving], k, mount):
                out.append(issue('MOTION_NO_GUIDE', 'warning', 'assembly',
                                 f"Motion '{m['id']}': nothing keeps {', '.join(repr(b) for b in group)} on its line while "
                                 f"it slides along {m['direction']}: it rests on '{m['on']}' but no board runs beside it on "
                                 f"both sides across the slide, so it would wander or tip. Add a guide - a rail or side "
                                 f"board on each side (with a 1-2 mm running gap), or a slot it runs in.", group + [m['on']],
                                 calc=[f"no boards within {GUIDE_GAP:g} mm on both sides of the group across "
                                       f"{' or '.join(AXES[i] for i in range(3) if i != k)}"]))
        else:
            own = [j for j in hinges if {j['a'], j['b']} & moving]
            if not m.get('axle') and not own:
                out.append(issue('MOTION_NO_PIVOT', 'warning', 'assembly',
                                 f"Motion '{m['id']}': nothing physically holds {', '.join(repr(b) for b in group)} on its "
                                 f"turning axis ({m['axis']} through [{', '.join(f'{v:g}' for v in m['pivot'])}]), so the "
                                 f"part would fall off or wobble. Add \"axle\": {{\"diameter\": 6}} (a dowel through the "
                                 f"pivot, the moving board and '{m['on']}') or hang it on a hinge connection.",
                                 group + [m['on']], calc=['no "axle" and no hinge connection on the moving boards']))
            for j in own:
                bad = _hinge_mismatch(design, plates, m, j) if j['a'] in moving else None
                if bad:
                    out.append(issue('MOTION_HINGE_MISMATCH', 'warning', 'joint', bad[0], [j['a'], j['b']], joint=j['id'],
                                     calc=bad[1]))
        in_train = {t['id'] for t in motions if trains.get(t['id']) == trains.get(m['id'])}
        train = {b for t in motions if t['id'] in in_train for b in t['boards'] + rod_of(t)}
        # whatever rides on this motion (a jaw on a head) moves rigidly with it, unless the train drives it as well
        riders, grew = [], True
        carried = {m['id']}
        while grew:
            grew = False
            for t in motions:
                if t['id'] not in carried and t.get('parent') in carried and t['id'] not in in_train:
                    carried.add(t['id'])
                    riders += [b for b in t['boards'] + rod_of(t) if b in plates and b not in train]
                    grew = True
        moving = moving | train | set(riders)     # a train moves together: its mesh and rods are checked separately
        group = group + riders
        nominal, _ = _samples(m)
        grid = ROTATE_STEP if m['type'] == 'rotate' else 1.0          # round positions in the messages
        ranges = K.sides(m['range'], 360.0 if m['type'] == 'rotate' else None)
        speed = {b: K.reach(plates[b], m['axis'], m['pivot']) * math.pi / 180.0 if m['type'] == 'rotate' else 1.0
                 for b in group}
        cache = {}

        def pose(b, v, base=None):
            key = (b, base is not None, round(v, 9))
            if key not in cache:
                cache[key] = K.posed(base or plates[b], _local(m, v))
            return cache[key]
        static = [(s, plates[s], None) for s in plates if s not in moving]
        static += [(x['id'], x['plate'], x['through']) for x in solid
                   if x['carrier'] is None or (x['carrier'] not in in_train and x['carrier'] not in carried)]
        first, tight, flat = {}, {}, {}              # (static board, side of 0) -> first contact
        # contact right at a hinge line is unavoidable: an edge closer to the axis than one step moves is not judged
        near_axis = CLEARANCE / max(math.sin(math.radians(nominal)), 1e-3) if m['type'] == 'rotate' else 0.0
        for b in group:
            env = K.envelope(lambda v: K.posed(plates[b], _local(m, v)).world_aabb(), ranges, lambda dv: speed[b] * dv)
            step = K.steps(nominal, CLEARANCE / speed[b]) if speed[b] > 1e-12 else nominal
            flat[b] = K.in_plane([m], plates[b].frame.normal)
            cyl = (m['axis'], m['pivot'], speed[b] * 180.0 / math.pi) if m['type'] == 'rotate' else None
            for s, ps, through in static:
                sbox = ps.world_aabb()
                if (through and b in through) or frozenset((b, s)) in hinged or K.box_gap(env, sbox) > CLEARANCE:
                    continue
                cg = K.cyl_gap(cyl, sbox)                # it never leaves the circle its farthest point sweeps
                if cg > CLEARANCE:
                    continue
                lg = K.layer_gap(plates[b], ps) if flat[b] else None      # in its own layer, and ps parallel to it
                if lg is not None and lg >= CLEARANCE - TOL['contact']:
                    continue
                check_budget()
                close = None
                if s != m['on'] and through is None:
                    if b not in grown:
                        from .model import Plate
                        grown[b] = Plate(design, _grown(design, comps[b], CLEARANCE))
                    close = (lambda v, b=b, ps=ps: [
                        h for h in K.interference(pose(b, v, grown[b]), ps)
                        if not (near_axis and h['kind'] != 'parallel_overlap' and h.get('location')
                                and _axis_distance(m, h['location']) < near_axis)])
                for sign, lo, hi in ranges:
                    hit, tt = K.scan(sign, lo, hi, step, lambda v, b=b, ps=ps, cg=cg: max(K.gap(pose(b, v), ps), cg),
                                     speed[b], (lambda v: []) if lg is not None and lg >= -TOL['contact'] else
                                     (lambda v, b=b, ps=ps: K.interference(pose(b, v), ps)), close, CLEARANCE, nominal)
                    key = (s, sign > 0)
                    if hit and (key not in first or abs(hit[2]) < abs(first[key][3])):
                        first[key] = (hit[0], b, hit[1][0], hit[2], lo, hi, step)
                    if tt and (key not in tight or abs(tt[0]) < abs(tight[key][0])):
                        tight[key] = (tt[0], b, tt[1][0], step)
        span = f"[{m['range'][0]:g}, {m['range'][1]:g}]"
        for (s, _side), (v, b, hit, c, lo, end, step) in sorted(first.items(), key=lambda kv: abs(kv[1][3])):
            at, clear = K.display(c, grid, lo, end)
            size = f"{hit['length']} mm" if 'length' in hit else f"{hit['area']} mm²"
            limit = [m['range'][0], clear] if c > 0 else [clear, m['range'][1]]
            out.append(issue('MOTION_COLLISION', 'error', 'assembly',
                             f"Motion '{m['id']}': {how}, '{b}' runs into '{s}' at {at:g}{unit} (first contact at "
                             f"{_fmt(c)}{unit}, shared material {size}). It moves freely only to {clear:g}{unit}: limit "
                             f"the range to [{limit[0]:g}, {limit[1]:g}], or move the pivot / cut clearance into '{s}'.",
                             [b, s], location=hit.get('location'),
                             calc=[f"'{b}' {how}: checked over {span} in steps of at most {step:.3g}{unit} (no point of it "
                                   f"moves more than {CLEARANCE:g} mm per step; positions its distance proves clear are "
                                   f"skipped), the first contact bisected to {K.BISECT:g}{unit}; round positions every "
                                   f"{grid:g}{unit}",
                                   f"first contact with '{s}' at {_fmt(c)}{unit}: {hit['kind']} {size}",
                                   f"last clear round position on that side: {clear:g}{unit}"]))
        for (s, side), (v, b, hit, step) in sorted(tight.items(), key=lambda kv: abs(kv[1][0])):
            if (s, side) in first:
                continue                             # it collides there anyway
            out.append(issue('MOTION_CLEARANCE', 'error', 'assembly',
                             f"Motion '{m['id']}': {how}, '{b}' passes '{s}' with less than {CLEARANCE:g} mm to spare at "
                             f"{_fmt(v)}{unit}, so it would rub and bind. Leave a running gap of at least {CLEARANCE:g} mm "
                             f"(about 2 mm is safer): move or shrink '{b}' or '{s}' there.", [b, s],
                             location=hit.get('location'),
                             calc=[f"'{b}' grown by {CLEARANCE:g} mm on every side touches '{s}' at {_fmt(v)}{unit} "
                                   f"({hit['kind']}); the real parts do not touch, so the gap is under {CLEARANCE:g} mm",
                                   f"positions checked over {span} in steps of at most {step:.3g}{unit}"
                                   + (f"; edges within {near_axis:.0f} mm of the turning axis (the hinge line) are not "
                                      f"judged" if near_axis else '')]))
    return out


class _Train:
    """A root motion with everything it drives (gears, belts, rods) and everything riding on those, posed at any
    value of the root: its bodies (boards, rods, and the axles / pins they carry) with the speed of each."""

    def __init__(self, design, plates, motions, root, solid):
        from . import kinematics as K
        self.motions, self.root = motions, root
        self.by_id = by_id = {m['id']: m for m in motions}
        family = set(train_values(motions, root['id'], 0.0))
        grew = True
        while grew:                                       # and everything that rides on the train
            grew = False
            for t in motions:
                if t['id'] not in family and t.get('parent') in family:
                    family.add(t['id'])
                    grew = True
        self.family = family
        own = set(family) | set(K.chain(by_id, root['id']))          # and the (resting) motions the root rides on
        self.own = [m for m in motions if m['id'] in own]
        spd = K.speeds(motions, root['id'])
        self.bodies = {}                                  # id -> {key, plate, rate, rod, through}
        for t in motions:
            if t['id'] not in family:
                continue
            for b in t['boards']:
                if b in plates:
                    self.bodies[b] = {'key': t['id'], 'plate': plates[b], 'through': None, 'rod': False,
                                      'rate': K.plate_rate(by_id, spd, K.chain(by_id, t['id']), plates[b]),
                                      'cyl': self._cyl(t, plates[b]), 'flat': self._flat(t['id'], plates[b])}
            if t.get('link') and t['link']['rod'] in plates:
                r = t['link']['rod']
                self.bodies[r] = {'key': 'rod:' + t['id'], 'plate': plates[r], 'through': None, 'rod': True,
                                  'rate': K.rod_rate(by_id, spd, t, plates[r]), 'cyl': None,
                                  'flat': self._flat(t['driven_by'], plates[r]) and self._flat(t['id'], plates[r])}
        for x in solid:
            if x['carrier'] in family:
                self.bodies[x['id']] = {'key': x['carrier'], 'plate': x['plate'], 'through': x['through'], 'rod': False,
                                        'rate': K.plate_rate(by_id, spd, K.chain(by_id, x['carrier']), x['plate']),
                                        'cyl': self._cyl(by_id[x['carrier']], x['plate']),
                                        'flat': self._flat(x['carrier'], x['plate'])}
        self.unit = '°' if root['type'] == 'rotate' else ' mm'
        self.nominal = _samples(root)[0]
        self.grid = ROTATE_STEP if root['type'] == 'rotate' else 1.0
        self.ranges = K.sides(root['range'], K.period(motions, root['id']))
        self._frames, self._posed, self._env = {}, {}, {}

    def _flat(self, mid, plate):
        """Whether the body stays in its layer (every motion carrying it turns about its normal or slides across it).
        A rod turns in its crank's plane, so it qualifies when both its crank and its follower do."""
        from . import kinematics as K
        return K.in_plane([self.by_id[x] for x in K.chain(self.by_id, mid)], plate.frame.normal)

    @staticmethod
    def _cyl(t, plate):
        """(axis, pivot, reach) when the body turns about an axis fixed in the world (its motion rides on nothing)."""
        from . import kinematics as K
        if t['type'] != 'rotate' or t.get('parent') is not None:
            return None
        return t['axis'], t['pivot'], K.reach(plate, t['axis'], t['pivot'])

    def frame(self, body, v):
        key = round(v, 9)
        if key not in self._frames:
            self._frames[key] = board_poses(self.own, train_values(self.own, self.root['id'], v))
        poses, bd = self._frames[key], self.bodies[body]
        if body in poses:
            return poses[body][1]
        carrier = self.by_id[bd['key']]                   # an axle or pin: the frame of the motion carrying it
        return poses[carrier['boards'][0]][1]

    def pose(self, body, v):
        from . import kinematics as K
        key = (body, round(v, 9))
        if key not in self._posed:
            if len(self._posed) > 20000:
                self._posed.clear()
            self._posed[key] = K.posed(self.bodies[body]['plate'], self.frame(body, v))
        return self._posed[key]

    def env(self, body):
        from . import kinematics as K
        if body not in self._env:
            r = self.bodies[body]['rate']
            self._env[body] = K.envelope(lambda v: self.pose(body, v).world_aabb(), self.ranges, lambda dv: r * dv)
        return self._env[body]

    def step(self, rate):
        from . import kinematics as K
        return K.steps(self.nominal, CLEARANCE / rate) if rate > 1e-12 else self.nominal


def _trains(design, plates, motions):
    from . import kinematics as K
    solid = K.solids(design, plates, motions)
    return solid, [_Train(design, plates, motions, r, solid) for r in motions
                   if not r.get('driven_by') and r['range'] is not None]


def check_cycles(design, plates, motions, reported=()):
    """-> issues for every mechanism (a crank or gear with everything it drives, and all that rides on them): the
    whole cycle is stepped through with every part posed where the mechanism puts it - rods, rockers, sliders,
    nested parts, axles and rod pins at once - and any two parts that run into each other are reported (pairs in
    `reported` excepted), as is a rod passing anything static closer than the running clearance (a warning). Then
    independent motions are checked against each other's moving poses (check_interference)."""
    from .validation import TOL, issue
    from . import kinematics as K
    comps = {c['id']: c for c in design['components']}
    joints = [j for j in design['joints'] if j.get('status') == 'joined']
    hinged = {frozenset((j['a'], j['b'])) for j in joints if j['type'] == 'hinge'}
    joined = {frozenset((j['a'], j['b'])) for j in joints}         # a fixed joint locks (MOTION_LOCKED), not collides
    meshing = {frozenset(m['gears']) for m in motions if m.get('gears')}
    seen, out = set(map(frozenset, reported)), []
    solid, trains = _trains(design, plates, motions)
    grown = {}
    for tr in trains:
        if len(tr.family) < 2:
            continue                                      # a single motion is fully checked by check_motions
        root, unit, bodies = tr.root, tr.unit, tr.bodies
        boards = list(bodies)
        static = [(s, plates[s], None) for s in plates if s not in bodies]
        static += [(x['id'], x['plate'], x['through']) for x in solid if x['id'] not in bodies]
        first, tight = {}, {}
        for x, b in enumerate(boards):
            bd = bodies[b]
            env = tr.env(b)
            pairs = [(s, ps, through, None) for s, ps, through in static if K.box_gap(env, ps.world_aabb()) <= CLEARANCE
                     and K.cyl_gap(bd['cyl'], ps.world_aabb()) <= CLEARANCE]
            pairs += [(o, None, bodies[o]['through'], o) for o in boards[x + 1:]
                      if bodies[o]['key'] != bd['key'] and K.box_gap(env, tr.env(o)) <= 0
                      and K.cyl_cyl_gap(bd['cyl'], bodies[o]['cyl']) <= 0]
            for s, ps, through, o in pairs:
                key = frozenset((b, s))
                if key in seen or key in hinged or key in meshing or key in joined:
                    continue
                if (through and b in through) or (bd['through'] and s in bd['through']):
                    continue                              # an axle / pin in its own holes
                lg = K.layer_gap(bd['plate'], ps if o is None else bodies[o]['plate']) \
                    if bd['flat'] and (o is None or bodies[o]['flat']) else None
                apart = lg is not None and lg >= -TOL['contact']          # in separate layers for good: never meet
                if apart and not (bd['rod'] and o is None and through is None and lg < CLEARANCE - TOL['contact']):
                    continue
                check_budget()
                closing = bd['rate'] + (bodies[o]['rate'] if o else 0.0)
                other = (lambda v, o=o: tr.pose(o, v)) if o else (lambda v, ps=ps: ps)
                close = None
                if bd['rod'] and o is None and through is None:
                    if b not in grown:
                        from .model import Plate
                        grown[b] = Plate(design, _grown(design, comps[b], CLEARANCE))
                    close = (lambda v, b=b, ps=ps: K.interference(K.posed(grown[b], tr.frame(b, v)), ps))
                elif o is None and (K.box_gap(env, ps.world_aabb()) > 0 or K.cyl_gap(bd['cyl'], ps.world_aabb()) > 0):
                    continue
                cg = K.cyl_gap(bd['cyl'], ps.world_aabb()) if o is None else K.cyl_cyl_gap(bd['cyl'], bodies[o]['cyl'])
                for sign, lo, hi in tr.ranges:
                    hit, tt = K.scan(sign, lo, hi, tr.step(closing),
                                     lambda v, b=b, cg=cg: max(K.gap(tr.pose(b, v), other(v)), cg), closing,
                                     (lambda v: []) if apart else (lambda v, b=b: K.interference(tr.pose(b, v), other(v))),
                                     close, CLEARANCE, tr.nominal)
                    if hit and (key not in first or abs(hit[2]) < abs(first[key][4])):
                        first[key] = (hit[0], b, s, hit[1][0], hit[2], lo, hi, tr.step(closing))
                    if tt and (key not in tight or abs(tt[0]) < abs(tight[key][0])):
                        tight[key] = (tt[0], b, s, tt[1][0], tr.step(closing))
        label = {x['id']: x['id'].split('-', 1)[0] for x in solid}
        what = lambda n: f"'{n}'" + (f" (the {label[n]} through {', '.join(sorted(next(x['through'] for x in solid if x['id'] == n)))})"
                                     if n in label else '')
        span = f"[{root['range'][0]:g}, {root['range'][1]:g}]"
        for v, b, s, hit, c, lo, end, step in sorted(first.values(), key=lambda r: abs(r[4])):
            at, clear = K.display(c, tr.grid, lo, end)
            size = f"{hit['length']} mm" if 'length' in hit else f"{hit['area']} mm²"
            out.append(issue('MOTION_COLLISION', 'error', 'assembly',
                             f"Mechanism driven by '{root['id']}': at {at:g}{unit} {what(b)} runs into {what(s)} (first "
                             f"contact at {_fmt(c)}{unit}, shared material {size}) - the parts it drives or carries "
                             f"collide part-way through the cycle. It runs freely only to {clear:g}{unit}: limit "
                             f"'{root['id']}' there, or move / reshape the parts (put a rod in its own layer, shorten an "
                             f"arm).", [b, s], location=hit.get('location'),
                             calc=[f"every part of the mechanism ({len(boards)} bodies, {len(tr.family)} motions) posed "
                                   f"over {span} of '{root['id']}' in steps of at most {step:.3g}{unit} (no point of "
                                   f"either moves more than {CLEARANCE:g} mm per step), the first contact bisected to "
                                   f"{K.BISECT:g}{unit}; round positions every {tr.grid:g}{unit}",
                                   f"first contact '{b}' - '{s}' at {_fmt(c)}{unit}: {hit['kind']} {size}"]))
        for key, (v, b, s, hit, step) in sorted(tight.items(), key=lambda kv: abs(kv[1][0])):
            if key in first:
                continue
            out.append(issue('MOTION_CLEARANCE', 'warning', 'assembly',
                             f"Mechanism driven by '{root['id']}': the rod '{b}' passes '{s}' with less than "
                             f"{CLEARANCE:g} mm to spare at {_fmt(v)}{unit}, so it would rub and bind. Leave a running gap "
                             f"of at least {CLEARANCE:g} mm (about 2 mm is safer): move the rod to its own layer or move "
                             f"'{s}'.", [b, s], location=hit.get('location'),
                             calc=[f"'{b}' grown by {CLEARANCE:g} mm on every side touches '{s}' at {_fmt(v)}{unit} "
                                   f"({hit['kind']}); the real parts do not touch, so the gap is under {CLEARANCE:g} mm",
                                   f"positions checked over {span} in steps of at most {step:.3g}{unit}"]))
    reported = seen | {frozenset(i['components']) for i in out if i['code'] == 'MOTION_COLLISION'}
    return out + check_interference(design, plates, motions, reported, trains)


INTERFERENCE_TESTS = 20000      # narrow-phase tests per pair of independent motions before giving up


def check_interference(design, plates, motions, reported=(), trains=None):
    """M-02: two independent motions (no driver in common, neither riding on the other) whose parts sweep through
    the same space: the joint travel is searched - each position of one against the other's positions, skipping
    where the boxes are apart - and the first pose where they meet is a MOTION_INTERFERENCE warning (each motion is
    clear on its own; they collide only when both are moved)."""
    from .validation import TOL, issue
    from . import kinematics as K
    if trains is None:
        trains = _trains(design, plates, motions)[1]
    joints = [j for j in design['joints'] if j.get('status') == 'joined']
    skip = set(map(frozenset, reported)) | {frozenset((j['a'], j['b'])) for j in joints}
    skip |= {frozenset(m['gears']) for m in motions if m.get('gears')}
    out = []
    for x, A in enumerate(trains):
        for B in trains[x + 1:]:
            if A.family & B.family:
                continue
            pairs = [(a, b) for a in A.bodies if A.bodies[a]['through'] is None
                     for b in B.bodies if B.bodies[b]['through'] is None
                     and frozenset((a, b)) not in skip and K.box_gap(A.env(a), B.env(b)) <= 0
                     and K.cyl_cyl_gap(A.bodies[a]['cyl'], B.bodies[b]['cyl']) <= 0
                     and not (A.bodies[a]['flat'] and B.bodies[b]['flat']
                              and _apart(K.layer_gap(A.bodies[a]['plate'], B.bodies[b]['plate']), TOL['contact']))]
            found = None
            for a, b in pairs:
                found = _joint_hit(A, B, a, b)
                if found:
                    break
            if not found:
                continue
            va, vb, hit = found
            size = f"{hit['length']} mm" if 'length' in hit else f"{hit['area']} mm²"
            ia, ib = A.root['id'], B.root['id']
            out.append(issue('MOTION_INTERFERENCE', 'warning', 'assembly',
                             f"Motions '{ia}' and '{ib}' move independently, but with '{ia}' at {_fmt(va)}{A.unit} and "
                             f"'{ib}' at {_fmt(vb)}{B.unit} '{a}' runs into '{b}' (shared material {size}). Each is clear "
                             f"on its own; they collide when both are moved. Limit one range, move the parts apart, or "
                             f"drive one from the other so they cannot meet.", [a, b], location=hit.get('location'),
                             calc=[f"'{ia}' over [{A.root['range'][0]:g}, {A.root['range'][1]:g}] against '{ib}' over "
                                   f"[{B.root['range'][0]:g}, {B.root['range'][1]:g}]: their swept boxes overlap",
                                   f"first meeting found at '{ia}' = {_fmt(va)}{A.unit}, '{ib}' = {_fmt(vb)}{B.unit}: "
                                   f"{hit['kind']} {size}"]))
    return out


def _apart(layer_gap, contact):
    return layer_gap is not None and layer_gap >= -contact


def _joint_hit(A, B, a, b):
    """First (va, vb, hit) where body a of train A meets body b of train B, both moved off rest; nearest va first.
    Each va is skipped ahead while a's box is clear of b's whole swept box."""
    from . import kinematics as K
    ra, rb = A.bodies[a]['rate'], B.bodies[b]['rate']
    ca, cb = A.bodies[a]['cyl'], B.bodies[b]['cyl']
    env_b, tests = B.env(b), [0]
    sa, sb = A.step(ra + rb), B.step(ra + rb)
    for sign, lo, hi in A.ranges:
        xa = max(lo, sa)
        while True:
            check_budget()
            va = sign * min(xa, hi)
            pa = A.pose(a, va)
            box = pa.world_aabb()
            g = max(K.box_gap(box, env_b), K.cyl_gap(cb, box))
            if g <= 0:
                for sgn, blo, bhi in B.ranges:
                    hit, _t = K.scan(sgn, blo, bhi, sb, lambda v: max(K.gap(pa, B.pose(b, v)),
                                                                      K.cyl_gap(ca, B.pose(b, v).world_aabb())), rb,
                                     lambda v: _counted(tests, K.interference(A.pose(a, va), B.pose(b, v))))
                    if hit:
                        return va, hit[0], hit[1][0]
                    if tests[0] > INTERFERENCE_TESTS:
                        return None
            if xa >= hi:
                break
            xa = min(hi, max(xa + sa, xa + (g / ra if ra > 1e-12 and g > 0 else 0.0)))
    return None


def _counted(tests, hits):
    tests[0] += 1
    return hits


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
        if abs(a['pressure_angle'] - b['pressure_angle']) > 1e-6:
            out.append(issue('GEAR_MESH', 'error', 'assembly',
                             f"Gears '{a['id']}' and '{b['id']}' cannot mesh smoothly: their pressure angles differ "
                             f"({a['pressure_angle']:g}° and {b['pressure_angle']:g}°), so their teeth are not conjugate - "
                             f"the drive would vary, rattle and bind. Give both the same \"pressure_angle\" (20 is "
                             f"standard).", pair,
                             calc=[f"base pitch = pi x module x cos(pressure angle): {math.pi * a['module'] * math.cos(math.radians(a['pressure_angle'])):.3f} "
                                   f"mm for '{a['id']}', {math.pi * b['module'] * math.cos(math.radians(b['pressure_angle'])):.3f} "
                                   f"mm for '{b['id']}' (must be equal)"]))
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


def _reachable(motions, m):
    """The part of a crank's range its connecting rods can follow (their tables stop where the linkage jams), or
    None when they follow all of it."""
    lo, hi = m['range']
    for t in motions:
        table = (t.get('link') or {}).get('table') if t.get('driven_by') == m['id'] else None
        if not table:
            continue
        step = max(2.0, (m['range'][1] - m['range'][0]) / 360.0) + 1e-6       # the table's own step (_link_table)
        a, b = table[0][0], table[-1][0]
        lo = max(lo, a) if a > m['range'][0] + step else lo
        hi = min(hi, b) if b < m['range'][1] - step else hi
    return None if [lo, hi] == list(m['range']) else [lo, hi]


def model_motions(motions):
    """Motions for the 3D view (world vectors; the view animates each over its range - a crank whose rod jams only
    over "jam_range", the part it can really turn)."""
    out = []
    for m in motions:
        e = {'id': m['id'], 'type': m['type'], 'boards': m['boards'], 'on': m['on'], 'range': m['range'],
             **({'driven_by': m['driven_by'], 'ratio': m['ratio']} if m.get('driven_by') and not m.get('link') else {}),
             **({'parent': m['parent']} if m.get('parent') else {})}
        if m.get('link'):
            lk = m['link']
            e.update(driven_by=m['driven_by'], link={'rod': lk['rod'], 'from': lk['from'], 'to': lk['to'],
                                                     'pin': lk['pin'], 'table': lk['table']})
        if m['type'] == 'rotate':
            e.update(axis=[1.0 if a == m['axis'] else 0.0 for a in AXES], pivot=m['pivot'])
        else:
            e['direction'] = [1.0 if a == m['direction'] else 0.0 for a in AXES]
        reach = _reachable(motions, m) if m.get('range') else None
        if reach:
            e['jam_range'] = reach
        out.append(e)
    return out
