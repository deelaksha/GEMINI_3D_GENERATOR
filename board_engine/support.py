"""
Support analysis: what holds every board, does the product stand up, and what merely rests on something.

Model (geometric / static plausibility only):
  * Boards are rigid, of uniform density; gravity is -Y.
  * Anchors: boards touching the floor (lowest y) for `mounting: 'floor'`, or touching the wall plane (lowest z,
    the back) for `mounting: 'wall'`.
  * A joined joint holds both boards in any direction. An undeclared contact only carries weight when the upper
    board lies on top of the lower one (a lid on a box, a drawer on its runner, a stacked module): "resting".
  * Floor products: the centre of mass must lie inside the convex hull of the floor contact (tip-over test).
  * A horizontal board whose own centre of mass lies outside the area where its supporting boards meet it is a
    cantilever: it is held only through the bending stiffness of its joints.

It does NOT assess strength: no loads, stresses, joint capacity, racking or material properties. "Supported" means
"geometrically held", never "safe under load".
"""
from collections import defaultdict

from . import geometry as G
from .model import build_plates
from .validation import TOL, issue

ANCHOR_TOL = 0.5          # mm: a board within this of the floor / wall plane touches it
VERTICAL = 0.9            # |normal . y| above which a face counts as horizontal
LOW_MARGIN = 0.05         # stability margin below 5 % of the footprint size is reported

DISCLAIMER = ('Geometric support and static tip-over check only (rigid boards, uniform density). Structural strength, '
              'joint capacity and loads are not assessed.')


def _centroid(poly):
    """(area, cx, cy) of a simple polygon (absolute area)."""
    a = cx = cy = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        k = x0 * y1 - x1 * y0
        a += k
        cx += (x0 + x1) * k
        cy += (y0 + y1) * k
    if abs(a) < 1e-12:
        return 0.0, 0.0, 0.0
    return abs(a) / 2.0, cx / (3.0 * a), cy / (3.0 * a)


def _mass_centre(pl):
    """(volume, world centre) of a plate: cut profile minus its cut-outs, times thickness."""
    area, cx, cy = _centroid(pl.cut)
    mx, my = area * cx, area * cy
    for _f, poly in pl.feature_polys:
        fa, fx, fy = _centroid(poly)
        area -= fa
        mx -= fa * fx
        my -= fa * fy
    if area <= 1e-9:
        return 0.0, pl.world_centre()
    return area * pl.t, pl.frame.to_world([mx / area, my / area, 0.0])


def _world_vertices(pl):
    return [pl.frame.to_world([x, y, z]) for x, y in pl.cut for z in (-pl.t / 2.0, pl.t / 2.0)]


def _resting_contacts(design, plates, tol):
    """(upper, lower) pairs of undeclared boards where the upper one lies on top of the lower one."""
    from .manufacturing import find_contacts
    out = set()
    for c in find_contacts(design, plates, tol):
        if c['gap'] > tol['contact'] or abs(c['normal'][1]) < VERTICAL:
            continue
        a, b = plates[c['a']], plates[c['b']]
        upper, lower = (a, b) if a.world_centre()[1] > b.world_centre()[1] else (b, a)
        if upper.world_aabb()[0][1] >= lower.world_aabb()[1][1] - 2 * tol['contact']:   # really on top, not hanging under
            out.add((upper.id, lower.id))
    return out


def support_report(design, plates=None, tol=TOL):
    plates = plates if plates is not None else build_plates(design)
    mounting = design.get('mounting', 'floor')
    issues = []
    out = {'mounting': mounting, 'disclaimer': DISCLAIMER, 'components': {}, 'issues': issues,
           'centre_of_mass': None, 'footprint': [], 'stable': None, 'stability_margin': None, 'status_counts': {}}
    if not plates:
        return out
    lo = {pid: pl.world_aabb()[0] for pid, pl in plates.items()}
    if mounting == 'wall':
        plane = min(v[2] for v in lo.values())
        anchors = {pid for pid, v in lo.items() if v[2] <= plane + ANCHOR_TOL}
    else:
        plane = min(v[1] for v in lo.values())
        anchors = {pid for pid, v in lo.items() if v[1] <= plane + ANCHOR_TOL}

    joints = [j for j in design['joints'] if j.get('status') == 'joined' and j['a'] in plates and j['b'] in plates]
    adj = defaultdict(set)
    for j in joints:
        adj[j['a']].add(j['b'])
        adj[j['b']].add(j['a'])
    resting_pairs = _resting_contacts(design, plates, tol)

    status = {pid: 'anchored' for pid in anchors}
    rests_on = defaultdict(set)

    def spread(start, label):
        stack = list(start)
        while stack:
            x = stack.pop()
            for y in adj[x]:
                if y not in status:
                    status[y] = label
                    stack.append(y)
    spread(anchors, 'joined')
    changed = True
    while changed:                      # resting parts (and everything joined to them) carried by supported ones
        changed = False
        for upper, lower in sorted(resting_pairs):
            if lower in status:
                rests_on[upper].add(lower)
                if upper not in status:
                    status[upper] = 'resting'
                    spread([upper], 'resting')
                    changed = True
    for pid in plates:
        status.setdefault(pid, 'unsupported')
        out['components'][pid] = {'status': status[pid], 'joined_to': sorted(adj[pid]),
                                  **({'rests_on': sorted(rests_on[pid])} if rests_on[pid] else {})}
    counts = defaultdict(int)
    for s in status.values():
        counts[s] += 1
    out['status_counts'] = dict(counts)

    for pid in sorted(p for p, s in status.items() if s == 'unsupported'):
        issues.append(issue('UNSUPPORTED_COMPONENT', 'error', 'support',
                            f"'{pid}' is neither joined to the product nor resting on it: nothing holds it "
                            f"(it would fall). Connect it or remove it.", [pid]))
    seen = set()
    for pid in sorted(p for p, s in status.items() if s == 'resting'):   # one note per loose group of joined boards
        if pid in seen:
            continue
        group, stack = set(), [pid]
        while stack:
            x = stack.pop()
            if x not in group:
                group.add(x)
                stack.extend(y for y in adj[x] if status[y] == 'resting')
        seen |= group
        under = sorted({b for x in group for b in rests_on[x]} - group)
        issues.append(issue('RESTING_COMPONENT', 'info', 'support',
                            f"{', '.join(repr(x) for x in sorted(group))} {'is' if len(group) == 1 else 'are'} not joined to "
                            f"the product; {'it rests' if len(group) == 1 else 'they rest'} on "
                            f"{', '.join(repr(x) for x in under)} (a loose / removable part). Make sure that is intended.",
                            sorted(group)))

    # Cantilevers: horizontal, non-anchored boards whose centre lies outside the area where their supports meet them
    for pid, pl in plates.items():
        if status[pid] in ('anchored', 'unsupported') or abs(pl.frame.normal[1]) < VERTICAL:
            continue
        (hx0, _hy0, hz0), (hx1, _hy1, hz1) = pl.world_aabb()
        pts = []
        for other in adj[pid] | rests_on[pid]:
            (ox0, _oy0, oz0), (ox1, _oy1, oz1) = plates[other].world_aabb()
            x0, x1, z0, z1 = max(hx0, ox0), min(hx1, ox1), max(hz0, oz0), min(hz1, oz1)
            if x1 >= x0 and z1 >= z0:
                pts += [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]
        hull = G.convex_hull(pts) if pts else []
        _vol, c = _mass_centre(pl)
        if (len(hull) < 3 or not G.point_in_polygon([c[0], c[2]], hull)) and status[pid] == 'resting':
            issues.append(issue('RESTING_OFF_SUPPORT', 'error', 'support',
                                f"'{pid}' only rests on {', '.join(repr(x) for x in sorted(rests_on[pid] | adj[pid]))} and its centre "
                                f"is beyond that support: nothing holds it, so it falls off. Move it onto its support or join it.",
                                [pid]))
        elif len(hull) < 3 or not G.point_in_polygon([c[0], c[2]], hull):
            issues.append(issue('CANTILEVER', 'warning', 'support',
                                f"'{pid}' is held only on one side (its centre is outside the area where its supports meet it): "
                                f"it relies on the joints resisting bending. Support it on the opposite side or check its strength.",
                                [pid]))

    # Tip-over (floor products)
    vol = cx = cy = cz = 0.0
    for pl in plates.values():
        v, c = _mass_centre(pl)
        vol += v
        cx, cy, cz = cx + v * c[0], cy + v * c[1], cz + v * c[2]
    if vol > 0:
        out['centre_of_mass'] = [round(cx / vol, 2), round(cy / vol, 2), round(cz / vol, 2)]
    if mounting == 'floor' and out['centre_of_mass']:
        feet = [[v[0], v[2]] for pid in anchors for v in _world_vertices(plates[pid]) if v[1] <= plane + ANCHOR_TOL]
        hull = G.convex_hull(feet)
        out['footprint'] = [[round(x, 2), round(z, 2)] for x, z in hull]
        com = [out['centre_of_mass'][0], out['centre_of_mass'][2]]
        if len(hull) >= 3:
            inside = G.point_in_polygon(com, hull)
            margin = G.dist_to_boundary(com, hull) * (1 if inside else -1)
            out['stable'], out['stability_margin'] = inside, round(margin, 2)
            x0, z0, x1, z1 = G.bbox(hull)
            if not inside:
                issues.append(issue('TIP_OVER', 'warning', 'support',
                                    f"The centre of mass [{com[0]:.0f}, {com[1]:.0f}] (x, z) lies {-margin:.0f} mm outside the floor "
                                    f"footprint: the product tips over unless it is fixed to a wall.", [],
                                    location=out['centre_of_mass']))
            elif margin < LOW_MARGIN * min(x1 - x0, z1 - z0):
                issues.append(issue('LOW_STABILITY_MARGIN', 'info', 'support',
                                    f"The centre of mass is only {margin:.0f} mm inside the floor footprint; the product tips "
                                    f"easily.", [], location=out['centre_of_mass']))
        else:
            out['stable'] = False
            issues.append(issue('TIP_OVER', 'warning', 'support', 'The product touches the floor only along a line or point; '
                                'it cannot stand on its own.', []))
    elif mounting == 'wall':
        issues.append(issue('WALL_MOUNTED', 'info', 'support', f"Wall-mounted: {', '.join(sorted(anchors))} must be fixed to "
                            f"the wall with suitable fixings; the fixings are not designed or checked here.", sorted(anchors)))
    return out
