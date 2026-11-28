"""
Kinematics for the motion checks (motion.check_motions / check_cycles): how far each part of a mechanism can move
per step, and a sweep that cannot step over a collision.

- rate:     mm a body's farthest point moves per degree (or mm) of the input - through gear / belt ratios, a
            connecting rod's table (its steepest slope) and every motion it rides on;
- step:     the input step that keeps a pair's relative travel per step under the running clearance (1 mm), so a
            thin arm or a fast follower cannot pass through a part between two checked positions;
- skip:     where two bodies' boxes are g mm apart, the next g / rate of input cannot bring them together (the box
            gap is a lower bound of their distance), so those positions are not tested (conservative advancement);
- contact:  the first touching position is bisected to 0.1 degree / mm between the last clear and the first hit;
- period:   a gear train repeats after one turn of its slowest member: a longer range is cut to one period;
- solids:   axles and rod pins are round bodies through the boards they pass, posed with whatever carries them;
- overlap:  parallel boards are compared by exact polygon overlap (shapely), crossing boards by plate_interference;
- envelope: a body's swept box over the travel, from coarse poses grown by what it can move between them.
The motion functions keep their messages; this module only decides which positions are checked and how.
"""
import copy
import math
from fractions import Fraction

from . import geometry as G
from .deadline import check as check_budget

AXES = ('x', 'y', 'z')
BISECT = 0.1             # degrees / mm: precision of a reported first contact
MIN_STEP = 1e-3          # degrees / mm: never step finer (a body 50 m from its axis)
PIN_SIDES = 16
COARSE = 72              # poses per side for a swept envelope
MAX_PERIOD = 360.0 * 60  # degrees of input: longer gear-train periods are not reduced


def box_gap(a, b):
    """Largest per-axis gap between two boxes (0 when they overlap): a lower bound of the distance between what they hold."""
    return max(max(0.0, b[0][i] - a[1][i], a[0][i] - b[1][i]) for i in range(3))


def _euler(R):
    from .canvas import _euler_xyz
    return _euler_xyz(R)


def material(p):
    """The plate's solid in its own 2-D frame (cut outline minus cut-outs), computed once per plate and shared by its
    posed copies."""
    poly = p.__dict__.get('_kin_material')
    if poly is None:
        import shapely
        from shapely.geometry import Polygon
        from shapely.validation import make_valid
        poly = make_valid(Polygon(p.cut))
        holes = [make_valid(Polygon(fp)) for _f, fp in p.feature_polys if len(fp) >= 3]
        if holes:
            poly = poly.difference(shapely.union_all(holes))
        p._kin_material = poly
    return poly


def posed(base, T):
    """The plate `base` moved by the rigid transform T = (R, t) after its own placement: a shallow copy that shares
    its outline, cut-outs and solid (nothing is rebuilt per position)."""
    material(base)
    R, t = T
    f = G.Frame.__new__(G.Frame)
    f.R = G.mat_mul(R, base.frame.R)
    f.p = [sum(R[i][j] * base.frame.p[j] for j in range(3)) + t[i] for i in range(3)]
    shape = base.signature()[4:]          # the outline part of the memo key, shared (not rebuilt) by every pose
    p = copy.copy(base)
    p.frame, p._aabb, p._kin_corners = f, None, None
    p.comp = dict(base.comp, placement={'position': f.p, 'rotation': _euler(f.R)})
    p._sig = (base.id, base.t, tuple(f.p), tuple(p.comp['placement']['rotation'])) + shape
    return p


def corners(p):
    """World corners of the plate's 2-D bounding box on both faces (its material lies in their hull)."""
    c = p.__dict__.get('_kin_corners')
    if c is None:
        x0, y0, x1, y1 = p.bbox2d
        h = p.t / 2.0
        c = p._kin_corners = [p.frame.to_world([x, y, z]) for x in (x0, x1) for y in (y0, y1) for z in (-h, h)]
    return c


def gap(a, b):
    """A lower bound of the distance between two plates' material: the largest separation of their bounding boxes
    along the world axes and along either plate's own axes (its outline box and its normal) - a separating-axis test
    of the two oriented boxes. Cheap; exact for a board lifting off or turning away from another."""
    g = box_gap(a.world_aabb(), b.world_aabb())
    ca, cb = corners(a), corners(b)
    for p in (a, b):
        for u in (p.frame.axis(0), p.frame.axis(1), p.frame.axis(2)):
            pa = [u[0] * w[0] + u[1] * w[1] + u[2] * w[2] for w in ca]
            pb = [u[0] * w[0] + u[1] * w[1] + u[2] * w[2] for w in cb]
            g = max(g, min(pb) - max(pa), min(pa) - max(pb))
    return g


def in_plane(motions, normal):
    """Whether every one of these motions keeps a board with this normal in its own layer: turning about an axis
    along the normal, or sliding across it. Then the board's slab along the normal never changes."""
    for m in motions:
        k = AXES.index(m['axis'] if m['type'] == 'rotate' else m['direction'])
        along = abs(normal[k]) > 1 - 1e-6
        if along != (m['type'] == 'rotate'):
            return False
    return True


def layer_gap(a, b):
    """Gap between the slabs (thickness layers) of two parallel plates, negative when they overlap; None when not
    parallel. Two plates that each stay in their layer cannot interfere while this is >= -contact tolerance."""
    na, nb = a.frame.normal, b.frame.normal
    if G.v_len(G.v_cross(na, nb)) >= 1e-4:
        return None
    ca, cb = G.v_dot(na, a.frame.p), G.v_dot(na, b.frame.p)
    return abs(ca - cb) - (a.t + b.t) / 2.0


def cyl_gap(cyl, box):
    """Distance from a part turning about a fixed axis - cyl = (axis, pivot, reach): it stays within that radius
    (a gear: its tip circle) - to a box, measured across the axis (a lower bound for every angle)."""
    if cyl is None:
        return 0.0
    axis, c, r = cyl
    k = AXES.index(axis)
    d = math.hypot(*[max(box[0][i] - c[i], 0.0, c[i] - box[1][i]) for i in range(3) if i != k])
    return d - r


def cyl_cyl_gap(a, b):
    """Distance between two parts each turning about its own fixed axis (parallel axes only, else 0)."""
    if a is None or b is None or a[0] != b[0]:
        return 0.0
    k = AXES.index(a[0])
    return math.hypot(*[a[1][i] - b[1][i] for i in range(3) if i != k]) - a[2] - b[2]


def interference(a, b):
    """Shared material of two plates, as validation.plate_interference reports it. Parallel plates: the exact area
    where their solids overlap (they must be closer than their half thicknesses less the contact tolerance)."""
    from .validation import TOL, plate_interference
    (alo, ahi), (blo, bhi) = a.world_aabb(), b.world_aabb()
    if not all(alo[i] + 0.01 < bhi[i] and blo[i] + 0.01 < ahi[i] for i in range(3)):
        return []
    na = a.frame.normal
    if G.v_len(G.v_cross(na, b.frame.normal)) >= 1e-4:
        return plate_interference(a, b)
    if abs(G.v_dot(G.v_sub(b.frame.p, a.frame.p), na)) >= (a.t + b.t) / 2.0 - TOL['contact']:
        return []
    from shapely import affinity
    o, ex, ey = a.frame.to_local(b.frame.p), a.frame.dir_to_local(b.frame.axis(0)), a.frame.dir_to_local(b.frame.axis(1))
    shared = material(a).intersection(affinity.affine_transform(material(b), [ex[0], ey[0], ex[1], ey[1], o[0], o[1]]))
    if shared.area < 1.0:
        return []
    c = shared.centroid
    return [{'kind': 'parallel_overlap', 'area': round(shared.area, 1),
             'location': [round(v, 3) for v in a.frame.to_world([c.x, c.y, 0.0])]}]


def axis_distance(axis, pivot, q):
    k = AXES.index(axis)
    return math.hypot(*[q[i] - pivot[i] for i in range(3) if i != k])


def vertices(p):
    """World corners of the plate's cut outline on both faces (its material lies in their hull)."""
    h = p.t / 2.0
    return [p.frame.to_world([x, y, z]) for x, y in p.cut for z in (-h, h)]


def reach(p, axis, pivot):
    """Farthest distance of the plate's material from a turning axis."""
    return max(axis_distance(axis, pivot, q) for q in vertices(p))


def cylinder(design, cid, axis, centre, diameter, span):
    """A round solid (an axle or a pin) as a plate: a polygon of PIN_SIDES sides, thin along `axis` over `span`."""
    from .model import Plate
    k = AXES.index(axis)
    pos = [float(v) for v in centre]
    pos[k] = (span[0] + span[1]) / 2.0
    r = diameter / 2.0
    outline = [[r * math.cos(2 * math.pi * i / PIN_SIDES), r * math.sin(2 * math.pi * i / PIN_SIDES)] for i in range(PIN_SIDES)]
    rot = {'x': [0.0, 90.0, 0.0], 'y': [-90.0, 0.0, 0.0], 'z': [0.0, 0.0, 0.0]}[axis]       # local z along the axis
    return Plate(design, {'id': cid, 'outline': outline, 'placement': {'position': pos, 'rotation': rot},
                          'thickness': span[1] - span[0], 'features': [], 'tabs': []})


def solids(design, plates, motions):
    """Axles and rod pins as round bodies: [{'id', 'plate', 'carrier': motion id moving it (None: static),
    'through': boards it passes (they have its hole)}]. Only those passing through two or more boards."""
    out = []

    def add(cid, axis, centre, d, through, carrier):
        through = [b for b in through if b in plates]
        if len(through) < 2:
            return
        k = AXES.index(axis)
        lo = min(plates[b].world_aabb()[0][k] for b in through)
        hi = max(plates[b].world_aabb()[1][k] for b in through)
        out.append({'id': cid, 'plate': cylinder(design, cid, axis, centre, d, (lo, hi)), 'carrier': carrier,
                    'through': set(through)})
    by_id = {m['id']: m for m in motions}
    for m in motions:
        if m['type'] == 'rotate' and m.get('axle') and m['axle'].get('boards'):
            add(f"axle-{m['id']}", m['axis'], m['pivot'], m['axle']['diameter'], m['axle']['boards'], m.get('parent'))
        lk, drv = m.get('link'), by_id.get(m.get('driven_by'))
        if lk and drv and drv['type'] == 'rotate':
            for end, point, carrier in (('crank', lk['from'], drv['id']), ('arm', lk['to'], m['id'])):
                holed = (lk.get('pins') or {}).get(end)
                if holed:
                    add(f"pin-{m['id']}-{end}", drv['axis'], point, lk['pin'], holed, carrier)
    return out


# ---------------------------------------------------------------------------------------------------------------
# how fast things move

def speeds(motions, root):
    """|d value / d root value| (its steepest) of every motion the root drives: ratios multiply, a rod's table gives
    its steepest slope. Motions it does not drive stay at rest (0)."""
    by_drv = {}
    for m in motions:
        by_drv.setdefault(m.get('driven_by'), []).append(m)
    out, todo = {root: 1.0}, [root]
    while todo:
        d = todo.pop()
        for m in by_drv.get(d, []):
            if m['id'] in out:
                continue
            if m.get('link'):
                t = m['link']['table']
                slope = max([abs((t[i + 1][1] - t[i][1]) / (t[i + 1][0] - t[i][0])) for i in range(len(t) - 1)
                             if t[i + 1][0] > t[i][0]] or [0.0])
            else:
                slope = abs(m.get('ratio') or 0.0)
            out[m['id']] = out[d] * slope
            todo.append(m['id'])
    return out


def chain(by_id, mid):
    out = []
    while mid is not None and mid in by_id and mid not in out:
        out.append(mid)
        mid = by_id[mid].get('parent')
    return out


def _sweep(m, r):
    """How far a point r mm from a motion's axis (rotate) can be carried by that motion over its range."""
    if m['type'] == 'rotate':
        return 2.0 * r
    return max(abs(v) for v in m['range'] or [0.0])


def rate(by_id, spd, mids, plate_reach):
    """mm per unit of input that points carried by the motions `mids` (innermost first) can move; plate_reach(m) ->
    the farthest distance of those points (at rest) from m's axis. Riding on a parent adds the parent's
    speed at the farthest the child can have carried them."""
    total, slack = 0.0, 0.0
    for mid in mids:
        m = by_id[mid]
        if m['type'] == 'rotate':
            r = plate_reach(m) + slack
            total += spd.get(mid, 0.0) * r * math.pi / 180.0
            slack += _sweep(m, r)
        else:
            total += spd.get(mid, 0.0)
            slack += _sweep(m, 0.0)
    return total


def plate_rate(by_id, spd, mids, plate):
    vs = vertices(plate)
    return rate(by_id, spd, mids, lambda m: max(axis_distance(m['axis'], m['pivot'], q) for q in vs))


def point_rate(by_id, spd, mids, q):
    return rate(by_id, spd, mids, lambda m: axis_distance(m['axis'], m['pivot'], q))


def rod_rate(by_id, spd, m, plate):
    """A rod spans the crank pin P and the follower pin Q: its points move at most |dP| plus its turn, which is at
    most (|dP| + |dQ|) / (in-plane rod length), times their distance from P."""
    lk, drv = m['link'], by_id[m['driven_by']]
    k = AXES.index(drv['axis'])
    flat = lambda a, b: math.hypot(*[a[i] - b[i] for i in range(3) if i != k])
    rp = point_rate(by_id, spd, chain(by_id, drv['id']), lk['from'])
    rq = point_rate(by_id, spd, chain(by_id, m['id']), lk['to'])
    ext = max(flat(q, lk['from']) for q in vertices(plate))
    return rp + (rp + rq) * ext / max(flat(lk['to'], lk['from']), 1.0)


def period(motions, root):
    """Input travel after which every part of the family is back where it started (a gear train: one turn of each
    member), or None (a slide, a rack, an irrational ratio)."""
    by_id = {m['id']: m for m in motions}
    if by_id[root]['type'] != 'rotate':
        return None
    turn = {root: Fraction(1)}             # member turns per input turn
    todo, out = [root], Fraction(360)
    while todo:
        d = todo.pop()
        for m in motions:
            if m.get('driven_by') != d or m['id'] in turn:
                continue
            if m.get('link'):
                turn[m['id']] = turn[d]    # a rod-driven part repeats with its crank
            elif m['type'] != 'rotate':
                return None
            else:
                r = Fraction(m['ratio']).limit_denominator(1000)
                if abs(float(r) - m['ratio']) > 1e-9 or r == 0:
                    return None
                turn[m['id']] = turn[d] * abs(r)
            todo.append(m['id'])
    for f in turn.values():                # input degrees for that member to turn a whole number of times: 360 / f
        p = Fraction(360) / f                # lcm(a/b, c/d) = lcm(a, c) / gcd(b, d) in lowest terms
        out = Fraction(out.numerator * p.numerator // math.gcd(out.numerator, p.numerator),
                       math.gcd(out.denominator, p.denominator))
    return float(out) if out <= MAX_PERIOD else None


def sides(rng, per=None):
    """[(sign, lo, hi)]: the travel on each side of the modelled position as distances from it (a range not starting
    at 0 starts at its nearer end), each cut to one period."""
    a, b = rng
    out = []
    if b > 0:
        lo = max(a, 0.0)
        out.append((1, lo, min(b, lo + per) if per else b))
    if a < 0:
        lo = max(-b, 0.0)
        out.append((-1, lo, min(-a, lo + per) if per else -a))
    return out


# ---------------------------------------------------------------------------------------------------------------
# the sweep

def steps(nominal, fine):
    """The scan step: at most `fine`, and a whole fraction of `nominal` so the nominal positions are visited."""
    if fine >= nominal:
        return nominal
    return nominal / math.ceil(nominal / max(fine, MIN_STEP) - 1e-9)


def scan(sign, lo, hi, step, gap, closing, hit, tight=None, need=0.0, every=None):
    """Positions sign * x for x from lo to hi (whole steps, hi last), nearest first, until the first collision.
    gap(v): a lower bound of the two bodies' distance at v (their box gap); closing: mm they can approach per unit
    of v; hit(v) -> shared material; tight(v) -> contacts of the part grown by `need` (the running clearance), judged
    on the `every` grid (the nominal 5 degree / slide step) and at the ends: rubbing is a matter of travel, and a part
    just leaving the board it rests on is not "tight". Positions the gap proves clear are skipped. -> (hit, tight): hit = (v of the first hit position, its hits, first
    contact bisected to BISECT), tight = (v, hits) at the first position closer than `need` (before any hit)."""
    step = max(step, MIN_STEP)
    x = lo if lo > 0 else min(step, hi)
    clear = 0.0 if lo <= 0 else None
    found = None
    while True:
        check_budget()
        v = sign * x
        g = gap(v)
        want = need if tight is not None and found is None else 0.0
        if g > want:
            free = g / closing if closing > 1e-12 else math.inf
            clear = min(x + free, hi) if clear is None else max(clear, min(x + free, hi))
            if x >= hi:
                break
            ahead = x + ((g - want) / closing if closing > 1e-12 else math.inf)
            nxt = max(math.floor(x / step + 1e-9) + 1, math.floor(min(ahead, hi) / step + 1e-9) + 1)
            x = min(nxt * step, hi)
            continue
        hits = hit(v) if g <= 0 else []
        if hits:
            a, b = min(clear, x) if clear is not None else x, x
            while b - a > BISECT:
                mid = (a + b) / 2.0
                if gap(sign * mid) <= 0 and hit(sign * mid):
                    b = mid
                else:
                    a = mid
            return (v, hits, sign * b), found
        if want > 0 and (every is None or x >= hi or x == lo or abs(x / every - round(x / every)) < 1e-6):
            close = tight(v)
            if close:
                found = (v, close)
        clear = x
        if x >= hi:
            break
        x = min((math.floor(x / step + 1e-9) + 1) * step, hi)
    return None, found


def envelope(pose_box, ranges, closing_step):
    """Swept box of a body: its box at COARSE poses per side (and at rest) grown by what it can move between two of
    them. pose_box(v) -> box; ranges: sides(); closing_step(dv) -> mm it moves over dv."""
    lo, hi = [list(c) for c in pose_box(0.0)]
    for sign, a, b in ranges:
        n = max(1, min(COARSE, math.ceil((b - a) / 1.0)))
        d = (b - a) / n
        grow = closing_step(d / 2.0)
        for i in range(n + 1):
            blo, bhi = pose_box(sign * (a + d * i))
            for k in range(3):
                lo[k] = min(lo[k], blo[k] - grow)
                hi[k] = max(hi[k], bhi[k] + grow)
    return lo, hi


def display(contact, grid, lo, end):
    """Round positions for a message: the first grid position at or past the contact (the range end at most) and
    the last grid position before it (the start of the side when the first position already touches)."""
    x = abs(contact)
    at = min(math.ceil(x / grid - 1e-9) * grid, abs(end))
    clear = (math.ceil(x / grid - 1e-9) - 1) * grid
    if clear < lo - 1e-9:
        clear = lo if x > lo + 1e-9 else 0.0
    s = 1 if contact > 0 else -1
    return round(s * at, 6) + 0.0, round(s * clear, 6) + 0.0
