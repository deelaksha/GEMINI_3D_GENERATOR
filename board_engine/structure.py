"""
Structural engineering checks that need only the geometry (no material, no weights):

- Weak sections: a part whose outline (or the web between its outline and a cut-out, or between two cut-outs)
  narrows below its own thickness somewhere would snap there (WEAK_SECTION).
- Retention: whether the joints really lock a part or it merely touches: with the parts around it in place, which
  ways can it still move? A part blocked every way is locked; one that can only lift straight up is held by its own
  weight; one free sideways is held only by the friction of its fit (PART_HELD_BY_FRICTION, info); one free downwards
  would drop out under its own weight (PART_CAN_FALL_OUT, warning).
"""
import math

from . import geometry as G
from .deadline import check as check_budget

TOUCH = 0.5                  # mm: boxes closer than this are neighbours
PROBE = 2.0                  # mm: how far each part is pushed along each axis to see what holds it
WEB_MIN, WEB_CAP = 3.0, 8.0   # mm: a web must be as wide as the board is thick (at least 3, at most 8 mm asked)
WEB_GRACE = 0.1              # a web within 10% of the rule is accepted (the rule of thumb is not that sharp)
TIP_AREA = 3.0               # x limit²: a narrow place that would only break off less than this is a pointed tip
MAX_SEGMENTS = 400           # edges of one part's outline + cut-outs examined for narrow webs
RETENTION_MAX_PARTS = 3000   # beyond this the retention probe (6 moves per part) is left out, with a note
GLUED = ('butt', 'mitre', 'hinge', 'edge_butt')
LIFT = 0.7                   # a part free only within ~45 degrees of straight up (a roof panel) is held by its weight
AX = 'xyz'


def _loops(pl):
    """The closed boundary loops of a part: its outline and every through cut-out (as 2D polygons)."""
    return [pl.cut] + [poly for _f, poly in pl.feature_polys if len(poly) >= 3]


def _seg_dist(a, b, c, d):
    """-> (distance, point on ab, point on cd) between segments ab and cd."""
    if G.segments_intersect(a, b, c, d):
        return 0.0, a, c
    best = None
    for p, (q0, q1), on_first in ((a, (c, d), True), (b, (c, d), True), (c, (a, b), False), (d, (a, b), False)):
        dx, dy = q1[0] - q0[0], q1[1] - q0[1]
        L2 = dx * dx + dy * dy
        s = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - q0[0]) * dx + (p[1] - q0[1]) * dy) / L2))
        q = [q0[0] + s * dx, q0[1] + s * dy]
        dist = math.hypot(p[0] - q[0], p[1] - q[1])
        if best is None or dist < best[0]:
            best = (dist, p, q) if on_first else (dist, q, p)
    return best


def narrowest_web(pl, limit):
    """-> (width, point a, point b) of the narrowest web in the part below `limit` mm, or None. Two edges count
    when they belong to different loops (the bridge beside a cut-out), or lie far apart along the same loop and a
    real piece would break off across them (at least TIP_AREA x limit² of material: a waist, a slender arm) - the
    point of a tooth, a horn, a leaf or the cleft of a heart-shaped hole is slender by design and is not a web."""
    loops, segs = [], []
    for li, loop in enumerate(_loops(pl)):
        pts = loop[:-1] if len(loop) > 1 and loop[0] == loop[-1] else loop
        n, u = len(pts), 0.0
        if n < 3:
            continue
        per = sum(math.dist(pts[i], pts[(i + 1) % n]) for i in range(n))
        loops.append(pts)
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            ln = math.dist(a, b)
            if ln > 1e-9:
                segs.append((len(loops) - 1, i, a, b, u, u + ln, per))
            u += ln
    if len(segs) > MAX_SEGMENTS:
        return None

    def piece(li, i, p, j, q, forward):
        pts = loops[li]
        n = len(pts)
        if not forward:
            i, p, j, q = j, q, i, p
        k, ring = (i + 1) % n, [p]
        while k != (j + 1) % n:
            ring.append(pts[k])
            k = (k + 1) % n
        return abs(G.signed_area(ring + [q]))
    best = None
    for x in range(len(segs)):
        la, ia, a0, a1, u0, u1, per = segs[x]
        bx = (min(a0[0], a1[0]) - limit, min(a0[1], a1[1]) - limit, max(a0[0], a1[0]) + limit, max(a0[1], a1[1]) + limit)
        for y in range(x + 1, len(segs)):
            lb, ib, b0, b1, v0, v1, _per = segs[y]
            if max(b0[0], b1[0]) < bx[0] or min(b0[0], b1[0]) > bx[2] or max(b0[1], b1[1]) < bx[1] or min(b0[1], b1[1]) > bx[3]:
                continue
            d, p, q = _seg_dist(a0, a1, b0, b1)
            if d >= limit * (1 - WEB_GRACE) or d <= 1e-6 or (best and d >= best[0]):
                continue
            if la == lb:
                fwd, back = (v0 - u1) % per, (u0 - v1) % per
                if (v0 < u1 and u0 < v1) or min(fwd, back) <= 2.0 * d + 1e-6:
                    continue                      # neighbouring edges of one corner, not two sides of a web
                if piece(la, ia, p, ib, q, fwd <= back) < TIP_AREA * limit * limit:
                    continue                      # only a slender point would break off: a tip, not a web
            best = (d, p, q)
    return best


def check_weak_sections(design, plates, skip=()):
    """-> issues for parts that narrow below their thickness somewhere."""
    from .validation import issue
    out = []
    for cid, pl in plates.items():
        prof = pl.comp.get('profile') or {}
        if cid in skip or prof.get('shape') == 'gear':
            continue                              # gear teeth are slender by design (their mesh is checked)
        check_budget()
        limit = max(WEB_MIN, min(pl.t, WEB_CAP))
        got = narrowest_web(pl, limit)
        if not got:
            continue
        d, p, q = got
        mid = pl.frame.to_world([(p[0] + q[0]) / 2, (p[1] + q[1]) / 2, pl.t / 2])
        out.append(issue('WEAK_SECTION', 'warning', 'structure',
                         f"'{cid}' narrows to {d:.1f} mm near [{', '.join(f'{v:.0f}' for v in mid)}] - less than the "
                         f"{limit:g} mm a web of a {pl.t:g} mm board needs, so it would snap or crack there in use. Widen that web to at least "
                         f"{limit:g} mm (move the cut-out or the edge apart), or add a rib across it.", [cid],
                         location=[round(v, 2) for v in mid],
                         calc=[f"narrowest web = {d:.2f} mm between the edges at "
                               f"({p[0]:.1f}, {p[1]:.1f}) and ({q[0]:.1f}, {q[1]:.1f}) on the part",
                               f"rule: web >= board thickness, at least {WEB_MIN:g} mm and never more than {WEB_CAP:g} mm asked "
                               f"(here {limit:g} mm)"]))
    return out


def _shifted(design, pl, d, step):
    from .model import Plate
    pos = [v + step * d[i] for i, v in enumerate(pl.comp['placement']['position'])]
    return Plate(design, dict(pl.comp, placement={'position': pos, 'rotation': pl.comp['placement']['rotation']}))


def _name(d):
    k = max(range(3), key=lambda i: abs(d[i]))
    if abs(d[k]) > 0.999:
        return ('+' if d[k] > 0 else '-') + AX[k]
    return '[' + ', '.join(f'{v:.2f}' for v in d) + ']'


def _face_contact(a, b):
    """Unit normal (pointing from box a to box b) when the boxes touch face to face, else None."""
    ov = [min(a[1][i], b[1][i]) - max(a[0][i], b[0][i]) for i in range(3)]
    small = [i for i in range(3) if -TOUCH <= ov[i] <= TOUCH]
    if len(small) != 1 or any(ov[i] <= TOUCH for i in range(3) if i != small[0]):
        return None
    k = small[0]
    n = [0.0, 0.0, 0.0]
    n[k] = 1.0 if (b[0][k] + b[1][k]) > (a[0][k] + a[1][k]) else -1.0
    return n


def retention(design, plates, skip=()):
    """-> {part id: [free unit directions]} for every joined part (not those in `skip`), or None when the
    design is too large. What holds a part, with its neighbours where they are:
      - a tab in a slot lets the tab's part move only straight out of the slot (and the slotted part only the
        other way);
      - a face resting against another part stops it moving into that part;
      - the floor stops it moving down;
      - a cross-lap or finger joint is tried for real: the part is pushed PROBE mm and must not then share material.
    Directions tried: the six axes and every tab's pull-out direction."""
    from .validation import plate_interference
    joints = [j for j in design['joints'] if j.get('status') == 'joined']
    glued = design.get('joinery') == 'glue_allowed'
    held, glue_held, by_part = set(), set(), {}
    for j in joints:
        held.update((j['a'], j['b']))
        by_part.setdefault(j['a'], []).append(j)
        by_part.setdefault(j['b'], []).append(j)
        if glued and j['type'] in GLUED:
            glue_held.update((j['a'], j['b']))
    ids = [i for i in plates if i in held and i not in skip and i not in glue_held]
    if len(ids) > RETENTION_MAX_PARTS:
        return None
    every = list(plates)
    boxes = {i: plates[i].world_aabb() for i in every}
    floor = min(b[0][1] for b in boxes.values()) if boxes else 0.0
    near = {i: set() for i in every}
    for x, y in G.near_pairs([boxes[i] for i in every], TOUCH):
        near[every[x]].add(every[y])
        near[every[y]].add(every[x])
    axes = [[float(i == k) * s for i in range(3)] for k in range(3) for s in (1, -1)]
    out = {}
    for cid in ids:
        pl = plates[cid]
        only, probes, faces = [], [], []          # allowed rays (tabs), parts to push against, contact normals
        joined = set()
        for j in by_part.get(cid, []):
            o = j['b'] if j['a'] == cid else j['a']
            if o not in plates:
                continue
            joined.add(o)
            if j['type'] == 'tab_slot':
                n = plates[j['b']].frame.dir_to_world([0.0, 0.0, 1.0])
                side = G.v_dot(G.v_sub(plates[j['a']].world_centre(), plates[j['b']].world_centre()), n)
                ray = G.v_scale(n, 1.0 if side >= 0 else -1.0)
                only.append(ray if j['a'] == cid else G.v_scale(ray, -1.0))
            elif j['type'] in ('cross_lap', 'finger'):
                probes.append(o)
        for o in near[cid]:
            if o in joined and o not in probes:
                continue
            n = _face_contact(boxes[cid], boxes[o])
            if n:
                faces.append(n)
        free, tried = [], set()
        for d in axes + [r for r in only if _name(r)[0] == '[']:
            if _name(d) in tried:
                continue
            tried.add(_name(d))
            if any(G.v_dot(d, r) < 0.999 for r in only) or any(G.v_dot(d, n) > 1e-6 for n in faces):
                continue
            if d[1] < -1e-6 and boxes[cid][0][1] <= floor + TOUCH:
                continue                          # standing on the floor
            if probes:
                check_budget()
                moved = _shifted(design, pl, d, PROBE)
                if any(plate_interference(moved, plates[o]) and not plate_interference(pl, plates[o]) for o in probes):
                    continue
            free.append(d)
        out[cid] = free
    return out


def check_retention(design, plates, skip=()):
    """-> (issues, summary): parts their joints do not lock in place."""
    from .validation import issue
    free = retention(design, plates, skip)
    if free is None:
        return [], {'checked': False, 'reason': f"more than {RETENTION_MAX_PARTS} joined parts"}
    out, locked, lift, friction = [], [], [], []
    for cid, vecs in free.items():
        dirs = [_name(d) for d in vecs]
        down = [_name(d) for d in vecs if d[1] <= -LIFT]
        side = [_name(d) for d in vecs if -LIFT < d[1] < LIFT]   # steeply upwards it has to be lifted: its weight holds it
        calc = [f"with every other part in place, '{cid}' is free to move along {', '.join(dirs)} (tabs only pull "
                f"straight out of their slots, faces stop it moving into the part they rest on, the floor stops it "
                f"moving down)"]
        if not dirs:
            locked.append(cid)
        elif down:
            out.append(issue('PART_CAN_FALL_OUT', 'warning', 'structure',
                             f"'{cid}' can drop out along {' and '.join(down)}: its joints hold it only from above, so "
                             f"only the friction of the fit stops its own weight pulling it out. Turn its tabs to go in "
                             f"from above or sideways, rest it on a board below, or lock it with a cross-lap or a pin.",
                             [cid], calc=calc))
        elif side:
            friction.append(cid)
            out.append(issue('PART_HELD_BY_FRICTION', 'info', 'structure',
                             f"'{cid}' is held along {' and '.join(side)} only by the friction of its fit: nothing it is "
                             f"joined to or touches blocks that way, so a pull or a knock can work it loose. For a "
                             f"self-locking build add a joint that engages across that direction (a tab into a board "
                             f"beside it, a cross-lap, a pin or a wedge).", [cid], calc=calc))
        else:
            lift.append(cid)
    return out, {'checked': True, 'locked': sorted(locked), 'lifts_off': sorted(lift),
                 'held_by_friction': sorted(friction), 'can_fall_out': sorted(i['components'][0] for i in out
                                                                       if i['code'] == 'PART_CAN_FALL_OUT')}
