"""
Completeness: does the built design contain what its brief (brief.py) says the product is made of?

  COMPONENT_MISSING (error)   a brief component no board belongs to ("role": "<component id>")
  COMPONENT_COUNT   (error)   fewer boards with that role than the component's count
  ROLE_UNKNOWN      (warning) a board names a role that is not a brief component
  ASYMMETRIC_PAIR   (warning) a "symmetric_pair" component is not mirrored about the product's centre (x)
  ENCLOSURE_OPEN    (error)   a side of an enclosure that the brief says is closed lets the outside in

Enclosures are probed from the inside: points on a grid within the enclosure look out in all six directions. A point
whose sight lines mostly meet boards is inside; if its view towards a closed side meets nothing, that side has a hole
there. A sight line that meets a board inside one of its declared openings ("kind": "opening" / "hole": doors,
windows, vents) is blocked by a deliberate opening and never reported; slots count as closed (a tab fills them).
Geometric only: it says nothing about appearance beyond open / closed.
"""
from . import geometry as G

OPENING_KINDS = ('opening', 'hole')
GRID = 12                       # sample points per axis inside an enclosure (at most)
OPEN_FRACTION = 0.03            # holes below this share of the inside points are seams, not openings


def _issue(code, severity, message, components=(), **extra):
    return dict({'code': code, 'severity': severity, 'category': 'completeness', 'message': message,
                 'components': list(components)}, **extra)


def _ray_meets(plate, p0, d, length):
    """(what, t): 'board' | 'opening' | None that the ray p0 + t*d (0 <= t <= length) meets of this plate, and where."""
    n = plate.frame.normal
    denom = G.v_dot(n, d)
    if abs(denom) > 1e-6:
        t = G.v_dot(n, G.v_sub(plate.frame.p, p0)) / denom
        if not 0 <= t <= length:
            return None, None
        return _at(plate, plate.frame.to_local(G.v_add(p0, G.v_scale(d, t)))[:2]), t
    if abs(G.v_dot(n, G.v_sub(p0, plate.frame.p))) > plate.t / 2.0:
        return None, None           # parallel and outside the board's thickness
    steps = max(2, int(length / max(plate.t, 1.0)))
    for k in range(steps + 1):      # running along inside the board's thickness (an edge seen end-on)
        t = length * k / steps
        hit = _at(plate, plate.frame.to_local(G.v_add(p0, G.v_scale(d, t)))[:2])
        if hit:
            return hit, t
    return None, None


def _at(plate, q):
    if plate.is_material(q, 0.0):
        return 'board'
    if not G.point_in_polygon(q, plate.cut):
        return None
    f = plate.feature_at(q)
    if f is None:
        return None
    return 'opening' if f.get('kind') in OPENING_KINDS else 'board'      # a slot is filled by its tab


DIRS = {'top': (1, 1), 'bottom': (1, -1), 'left': (0, -1), 'right': (0, 1), 'front': (2, 1), 'back': (2, -1)}


def _sight(p, side, box, plates, boxes):
    """Distance from point p to the nearest board (or deliberate opening) towards `side`; None when the view leaves
    the box without meeting anything."""
    ax, sign = DIRS[side]
    d = [0.0, 0.0, 0.0]
    d[ax] = float(sign)
    length = (box[1][ax] - p[ax] if sign > 0 else p[ax] - box[0][ax]) + 1.0
    u, v = [k for k in range(3) if k != ax]
    best = None
    for pid, pl in plates.items():
        blo, bhi = boxes[pid]
        if not (blo[u] <= p[u] <= bhi[u] and blo[v] <= p[v] <= bhi[v]):
            continue
        if (sign > 0 and bhi[ax] < p[ax]) or (sign < 0 and blo[ax] > p[ax]):
            continue                # behind the point
        what, t = _ray_meets(pl, p, d, length if best is None else best)
        if what and (best is None or t < best):
            best = t
    return best


OPPOSITE = {'top': 'bottom', 'bottom': 'top', 'left': 'right', 'right': 'left', 'front': 'back', 'back': 'front'}


def _probe(box, plates, boxes):
    """-> (inside points, {side: [points that see out through that side]}). A sample point is inside the enclosure
    when at least 4 of its 6 sight lines meet a board (points under eaves, beside a wall or past the ends are not). It
    sees out through a side - a hole - when that sight line meets nothing while the one the other way crosses the
    enclosure (at least 15 mm or a tenth of its size): a shallow recess behind an inset wall is not a hole."""
    n = [max(3, min(GRID, int((box[1][k] - box[0][k]) / 6.0))) for k in range(3)]
    inside, holes = 0, {s: [] for s in DIRS}
    for i in range(n[0]):
        for j in range(n[1]):
            for k in range(n[2]):
                p = [box[0][a] + (box[1][a] - box[0][a]) * (idx + 0.5) / n[a] for a, idx in enumerate((i, j, k))]
                dist = {s: _sight(p, s, box, plates, boxes) for s in DIRS}
                out = [s for s in DIRS if dist[s] is None]
                if len(out) > 2:
                    continue
                inside += 1
                for s in out:
                    back = dist[OPPOSITE[s]]
                    ax = DIRS[s][0]
                    if back is not None and back >= max(15.0, 0.1 * (box[1][ax] - box[0][ax])):
                        holes[s].append(p)
    return inside, holes


def check(brief, plates, roles):
    """brief: a normalised brief; plates: {board id: Plate} of the compiled design; roles: {board id: role}."""
    issues = []
    comp_ids = {c['id'] for c in brief['components']}
    by_role = {}
    for bid, r in roles.items():
        if bid in plates:
            by_role.setdefault(r, []).append(bid)
    for c in brief['components']:
        have = sorted(by_role.get(c['id'], []))
        if not have:
            issues.append(_issue('COMPONENT_MISSING', 'error', f"The brief lists {c['count']} x '{c['id']}' ({c['role']}), "
                                 f"but no board has \"role\": \"{c['id']}\". Build it, or tag the boards that make it."))
        elif len(have) < c['count']:
            issues.append(_issue('COMPONENT_COUNT', 'error', f"The brief lists {c['count']} x '{c['id']}', but only "
                                 f"{len(have)} board(s) have that role ({', '.join(have[:6])}).", have))
    stray = sorted({r for r in by_role if r not in comp_ids})
    for r in stray:
        issues.append(_issue('ROLE_UNKNOWN', 'warning', f"Board(s) {', '.join(by_role[r][:6])} name the role '{r}', which is "
                             f"not a component of the brief: add it to the brief or fix the role.", by_role[r]))
    boxes = {pid: pl.world_aabb() for pid, pl in plates.items()}
    if boxes:
        cx = (min(b[0][0] for b in boxes.values()) + max(b[1][0] for b in boxes.values())) / 2.0
        for c in brief['components']:
            if not c['symmetric_pair']:
                continue
            have = by_role.get(c['id'], [])
            for bid in have:
                (lo, hi) = boxes[bid]
                mirrored = ([2 * cx - hi[0], lo[1], lo[2]], [2 * cx - lo[0], hi[1], hi[2]])
                if not any(all(abs(boxes[o][s][k] - mirrored[s][k]) <= 1.0 for s in (0, 1) for k in range(3))
                           for o in have):
                    issues.append(_issue('ASYMMETRIC_PAIR', 'warning', f"'{bid}' of the symmetric component "
                                         f"'{c['id']}' has no mirror image about the centre x = {cx:.1f} mm.", [bid]))
                    break
    for e in brief['enclosures']:
        members = [b for m in e['components'] for b in by_role.get(m, [])]
        if not members:
            continue                # its components are reported missing above
        box = ([min(boxes[b][0][k] for b in members) for k in range(3)], [max(boxes[b][1][k] for b in members) for k in range(3)])
        near_box = {pid: pl for pid, pl in plates.items()          # any board in the box may close it, not only members
                    if all(boxes[pid][0][k] <= box[1][k] and boxes[pid][1][k] >= box[0][k] for k in range(3))}
        inside, holes = _probe(box, near_box, boxes)
        for side in e['closed_sides']:
            misses = holes[side]
            if len(misses) < 2 or len(misses) <= OPEN_FRACTION * inside:
                continue
            ax = DIRS[side][0]
            u, v = [k for k in range(3) if k != ax]
            gap = ([min(p[k] for p in misses) for k in range(3)], [max(p[k] for p in misses) for k in range(3)])
            near = sorted(members, key=lambda b: sum(max(0.0, boxes[b][0][k] - gap[1][k], gap[0][k] - boxes[b][1][k]) ** 2
                                                     for k in (u, v)))[:3]
            issues.append(_issue('ENCLOSURE_OPEN', 'error',
                                 f"The {side} of '{e['id']}' is open where the brief says it is closed: "
                                 f"from {len(misses)} of {inside} points inside it the view to the {side} meets no "
                                 f"board (around {'xyz'[u]} {gap[0][u]:.0f}..{gap[1][u]:.0f}, {'xyz'[v]} "
                                 f"{gap[0][v]:.0f}..{gap[1][v]:.0f} mm, near {', '.join(near)}). Close it with a board, or "
                                 f"list the side as open in the brief if it is meant to be.", near, side=side,
                                 open_share=round(len(misses) / inside, 3)))
    return issues
