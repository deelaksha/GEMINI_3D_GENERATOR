"""
Manufacturing engineering: what it takes to actually make and assemble a design.

A geometrically valid design (validation.py) is not necessarily manufacturable. This module adds:

  * material catalogue      - standard thicknesses, tolerances, minimum part size, grain, drilling limits
  * fastener engineering    - positions of screws / confirmat screws / dowels on butt and edge-to-edge
                              joints; edge-wall, engagement, break-out, end-distance checks; drilling
                              operations (face and edge bores) for every board
  * hinge engineering       - cup-hinge bores on doors and mounting-plate holes on the carcass, hinge
                              positions moved clear of shelves, doors that would rub
  * fastener cross-checks   - fasteners colliding with each other or passing through a third board,
                              screw heads that cannot be reached with a driver
  * connection assistant    - boards that touch without a declared joint, near-miss gaps (with the exact
                              correction), L / T / edge-to-edge classification and the joints that suit
                              each (alternatives, never applied automatically)
  * assembly planning       - assembly-by-disassembly on a local blocking graph: finds an order (with
                              sub-assemblies) in which every board can be brought into place along its
                              tab / dowel insertion directions, or reports that the design locks itself
  * material constraints    - non-standard thickness, parts below the minimum size, grain across a
                              solid-wood span, edge banding on edges that cannot take it

Everything is derived from the design geometry and the tables below; nothing is guessed. The tables are
typical catalogue values (European board sizes, 32 mm system hardware) — review them for your supplier.

Coordinate conventions are those of geometry.py. Drilling positions are given in the board's local XY
(the same frame as its outline); `face` is '+z' or '-z' (local), edge bores name the outline edge.
"""
import math

from . import geometry as G
from .deadline import check as check_budget
from .model import build_plates, edge_frame, material_of, tab_geometry
from .validation import HINGE, TOL, _edge_world, _material_intervals, _r, evaluate_joint, hinge_count, issue

# ---------------------------------------------------------------------------
# Catalogues
# ---------------------------------------------------------------------------

MATERIALS = {
    'plywood': {'thicknesses': [3, 4, 6, 9, 12, 15, 18, 21, 24, 27, 30], 'thickness_tol': 0.5, 'cut_tol': 0.3,
                'min_part': 25.0, 'grain': True, 'edge_wall': 3.0, 'face_remaining': 3.0, 'kerf': 3.2,
                'stock': [[2440, 1220], [2500, 1250], [1525, 1525]]},
    'mdf': {'thicknesses': [3, 6, 9, 12, 15, 16, 18, 19, 22, 25, 30], 'thickness_tol': 0.3, 'cut_tol': 0.2,
            'min_part': 25.0, 'grain': False, 'edge_wall': 4.0, 'face_remaining': 3.0, 'kerf': 3.2,
            'stock': [[2440, 1220], [2800, 2070]]},
    'particle_board': {'thicknesses': [8, 10, 12, 16, 18, 19, 22, 25, 28, 30, 38], 'thickness_tol': 0.3,
                       'cut_tol': 0.3, 'min_part': 30.0, 'grain': False, 'edge_wall': 4.0, 'face_remaining': 4.0,
                       'kerf': 3.2, 'stock': [[2800, 2070], [2440, 1220]]},
    'solid_wood': {'thicknesses': [12, 15, 18, 20, 22, 25, 27, 30, 32, 38, 40, 45], 'thickness_tol': 0.5,
                   'cut_tol': 0.5, 'min_part': 20.0, 'grain': True, 'edge_wall': 3.0, 'face_remaining': 3.0,
                   'kerf': 3.2, 'stock': [[2400, 600], [3000, 1200]]},
    'hardboard': {'thicknesses': [2.5, 3, 3.2, 4, 5, 6], 'thickness_tol': 0.2, 'cut_tol': 0.3, 'min_part': 20.0,
                  'grain': False, 'edge_wall': None, 'face_remaining': 1.5, 'kerf': 3.2,
                  'stock': [[2440, 1220], [2745, 1220]]},
    'cardboard': {'thicknesses': [1.5, 2, 3, 4, 5, 6], 'thickness_tol': 0.3, 'cut_tol': 0.2, 'min_part': 5.0,
                  'grain': False, 'edge_wall': None, 'face_remaining': None, 'kerf': 0.2,
                  'stock': [[1000, 700], [1200, 800]]},
}

# diameter: body; bore_a: hole in the edge of board A; bore_b: hole in the face of board B (through for screws)
FASTENERS = {
    'screw': {'diameter': 4.0, 'length': 40.0, 'bore_a': 2.5, 'bore_b': 4.5, 'through_b': True,
              'min_engagement': 5.0, 'end': 30.0, 'min_end': 20.0, 'max_spacing': 200.0},
    'confirmat': {'diameter': 7.0, 'length': 50.0, 'bore_a': 5.0, 'bore_b': 7.0, 'through_b': True,
                  'min_engagement': 4.0, 'end': 50.0, 'min_end': 32.0, 'max_spacing': 250.0},
    'dowel': {'diameter': 8.0, 'length': 35.0, 'bore_a': 8.0, 'bore_b': 8.0, 'through_b': False,
              'min_engagement': 0.0, 'end': 37.0, 'min_end': 25.0, 'max_spacing': 160.0},
}
FASTENER_GAP = 2.0          # mm of material between two fastener bodies
TOOL_ACCESS = 150.0         # mm of free line needed behind a screw head (drill / driver)
GAP_SEARCH = 5.0            # mm: boards closer than this without a joint are reported as a possible gap
HINGE_ARM = {'depth': 60.0, 'half_width': 25.0, 'height': 20.0, 'plate_setback': 37.0, 'plate_pitch': 32.0}
DOOR_MIN_GAP = 2.0          # mm between neighbouring doors
STAGGER_SUGGESTIONS = 20    # joints per report that get a verified re-layout suggestion


def material_spec(design, comp):
    return MATERIALS.get(material_of(design, comp)['type'])


def fastener_spec(f):
    spec = dict(FASTENERS[f['kind']])
    if f.get('diameter'):
        k = f['diameter'] / spec['diameter']
        spec.update(diameter=f['diameter'], bore_a=spec['bore_a'] * k, bore_b=spec['bore_b'] * k)
    if f.get('length'):
        spec['length'] = f['length']
    if f.get('end'):
        spec['end'] = f['end']
    return spec


# ---------------------------------------------------------------------------
# Fasteners
# ---------------------------------------------------------------------------

def _contact_run(a, b, w0, w1):
    """Longest run [s0, s1] (fractions of edge w0->w1) where the edge rests on b's material (exact)."""
    q0, q1 = b.frame.to_local(w0), b.frame.to_local(w1)
    best = None
    for r0, r1 in _material_intervals(b, q0, [q1[0] - q0[0], q1[1] - q0[1]], 0.0):
        r0, r1 = max(r0, 0.0), min(r1, 1.0)
        if r1 - r0 > 1e-9 and (best is None or r1 - r0 > best[1] - best[0]):
            best = [r0, r1]
    return best


def _layout(length, f, spec):
    """Positions (mm from run start) of the fasteners along a contact run of `length` mm."""
    end = spec['end']
    if length < 2 * end:
        end = length / 2.0 if length < 2 * spec['min_end'] + 1e-9 else spec['min_end']
    span = max(0.0, length - 2 * end)
    n = f.get('count') or (1 if span < 1e-9 else 2 + max(0, math.ceil(span / spec['max_spacing']) - 1))
    if n == 1:
        return [length / 2.0], length / 2.0
    return [end + span * i / (n - 1) for i in range(n)], end


def joint_fasteners(design, plates, joint, tol=TOL):
    """Fastener bodies and drilling operations of one fastened joint, plus the issues they raise."""
    f = joint.get('fasteners')
    a, b = plates.get(joint['a']), plates.get(joint['b'])
    if not f or a is None or b is None or joint['a_edge'] >= len(a.outline):
        return [], [], []
    spec = fastener_spec(f)
    jid, comps, issues, bodies, drills = joint['id'], [a.id, b.id], [], [], []
    w0, w1 = _edge_world(a, joint['a_edge'])
    _p, _d, na2, La = edge_frame(a.outline, joint['a_edge'])
    d_in = G.v_scale(a.frame.dir_to_world([na2[0], na2[1], 0]), -1.0)      # from the edge into A
    coplanar = joint['type'] == 'edge_mitre'
    if coplanar and f['kind'] != 'dowel':
        issues.append(issue('FASTENER_NOT_APPLICABLE', 'error', 'fastener',
                            f"'{jid}': edge-to-edge joints take dowels, not {f['kind']} fasteners.", comps, joint=jid))
        return [], [], issues
    if not coplanar and abs(G.v_dot(d_in, b.frame.normal)) < 1 - 1e-3:
        return [], [], []   # geometry is wrong; evaluate_joint already reports it
    if coplanar:
        _p, _d, nb2, _L = edge_frame(b.outline, joint['b_edge'])
        run = [0.0, 1.0]
        length = La
    else:
        run = _contact_run(a, b, w0, w1)
        if run is None:
            issues.append(issue('FASTENER_NO_CONTACT', 'error', 'fastener',
                                f"'{jid}': the mid-line of the {a.t:g} mm edge of '{a.id}' does not rest on solid "
                                f"material of '{b.id}', so no {f['kind']} can be placed.", comps, joint=jid))
            return [], [], issues
        length = (run[1] - run[0]) * La
    pos, end = _layout(length, f, spec)
    if end < spec['min_end'] - 1e-6:
        issues.append(issue('FASTENER_TOO_CLOSE_TO_END', 'error', 'fastener',
                            f"'{jid}': the {length:.0f} mm contact only leaves {end:.0f} mm from the end for a "
                            f"{f['kind']} (minimum {spec['min_end']:g} mm) — the board end would split.",
                            comps, joint=jid, contact_length=_r(length)))
    if len(pos) == 1 and not f.get('count'):
        issues.append(issue('SINGLE_FASTENER', 'warning', 'fastener',
                            f"'{jid}' has room for only one {f['kind']}; the joint can pivot about it.",
                            comps, joint=jid))
    ma, mb = material_spec(design, a.comp), material_spec(design, b.comp)
    wall = (a.t - spec['bore_a']) / 2.0
    need_wall = (ma or {}).get('edge_wall') or 2.0
    if (ma or {}).get('edge_wall', 0) is None or wall < need_wall:
        issues.append(issue('FASTENER_TOO_THICK_FOR_EDGE', 'error', 'fastener',
                            f"'{jid}': a {spec['bore_a']:g} mm bore in the {a.t:g} mm edge of '{a.id}' leaves "
                            f"{wall:.1f} mm of material each side (needs {need_wall:g} mm"
                            + (", or this material cannot take edge fasteners" if (ma or {}).get('edge_wall', 0) is None
                               else '') + ").", comps, joint=jid, wall=_r(wall)))
    if coplanar:
        depth_b = spec['length'] / 2.0 + 0.5
        depth_a = spec['length'] / 2.0 + 0.5
        wall_b = (b.t - spec['bore_b']) / 2.0
        if wall_b < ((mb or {}).get('edge_wall') or 2.0):
            issues.append(issue('FASTENER_TOO_THICK_FOR_EDGE', 'error', 'fastener',
                                f"'{jid}': a {spec['bore_b']:g} mm dowel bore leaves {wall_b:.1f} mm in the edge of '{b.id}'.",
                                comps, joint=jid, wall=_r(wall_b)))
    elif spec['through_b']:
        depth_b = b.t
        depth_a = spec['length'] - b.t
        if depth_a < spec['min_engagement'] * spec['diameter']:
            issues.append(issue('FASTENER_TOO_SHORT', 'error', 'fastener',
                                f"'{jid}': a {spec['length']:g} mm {f['kind']} through {b.t:g} mm '{b.id}' only "
                                f"engages {depth_a:.1f} mm of '{a.id}' (needs {spec['min_engagement'] * spec['diameter']:.0f} mm).",
                                comps, joint=jid, engagement=_r(depth_a)))
    else:   # dowel: blind bore in the face of b
        remaining = (mb or {}).get('face_remaining') or 2.0
        depth_b = min(spec['length'] / 2.0, b.t - remaining)
        depth_a = spec['length'] - depth_b + 1.0     # 1 mm glue reservoir at the bottom of the edge bore
        if depth_b < 0.3 * spec['length']:
            issues.append(issue('DOWEL_SHALLOW', 'error' if depth_b <= 3 else 'warning', 'fastener',
                                f"'{jid}': '{b.id}' is {b.t:g} mm thick, so the {spec['length']:g} mm dowel can only "
                                f"go {depth_b:.1f} mm into it (leaving {remaining:g} mm).", comps, joint=jid,
                                depth=_r(depth_b)))
    # Per-fastener geometry
    for i, s_mm in enumerate(pos):
        s = run[0] + s_mm / La
        P = G.v_add(w0, G.v_scale(G.v_sub(w1, w0), s))                   # on A's edge, mid-plane
        fid = f"{jid}/{f['kind']}{i + 1}"
        start, end_pt = G.v_sub(P, G.v_scale(d_in, depth_b)), G.v_add(P, G.v_scale(d_in, depth_a))
        bodies.append({'id': fid, 'joint': jid, 'kind': f['kind'], 'start': start, 'end': end_pt, 'end_used': end,
                       'radius': spec['diameter'] / 2.0, 'boards': [a.id, b.id], 'head': start if spec['through_b'] else None,
                       'axis': d_in})
        pa = a.frame.to_local(P)
        drills.append({'id': fid + '/a', 'component': a.id, 'joint': jid, 'type': 'edge_bore', 'edge': joint['a_edge'],
                       'position': _r(pa[:2], 2), 'offset_along_edge': _r(s * La, 2), 'diameter': _r(spec['bore_a'], 2),
                       'depth': _r(depth_a, 2), 'fastener': f['kind']})
        # Tip must stay inside A's material
        tip = a.frame.to_local(end_pt)
        if not a.is_material([tip[0], tip[1]], spec['bore_a'] / 2.0):
            issues.append(issue('FASTENER_BREAKS_OUT', 'error', 'fastener',
                                f"'{fid}': the {depth_a:.0f} mm bore into '{a.id}' leaves the board or runs into a "
                                f"cut-out.", comps, joint=jid, location=_r(end_pt)))
        if coplanar:
            pb = b.frame.to_local(P)
            drills.append({'id': fid + '/b', 'component': b.id, 'joint': jid, 'type': 'edge_bore',
                           'edge': joint['b_edge'], 'position': _r(pb[:2], 2), 'diameter': _r(spec['bore_b'], 2),
                           'depth': _r(depth_b, 2), 'fastener': f['kind']})
            continue
        # Face bore in B: on the face away from A (through) or the face A rests on (blind dowel)
        pb = b.frame.to_local(P)
        a_side = 1.0 if G.v_dot(G.v_sub(a.world_centre(), b.frame.p), b.frame.normal) > 0 else -1.0
        face = a_side if not spec['through_b'] else -a_side
        drills.append({'id': fid + '/b', 'component': b.id, 'joint': jid, 'type': 'face_bore',
                       'face': '+z' if face > 0 else '-z', 'position': _r(pb[:2], 2),
                       'diameter': _r(spec['bore_b'], 2), 'depth': _r(depth_b, 2),
                       'through': bool(spec['through_b']), 'fastener': f['kind'],
                       **({'countersink': True} if f['kind'] == 'screw' else {})})
        hit = next((ft for ft, poly in b.feature_polys
                    if G.point_in_polygon(pb[:2], poly) or G.dist_to_boundary(pb[:2], poly) < spec['bore_b'] / 2.0), None)
        if hit:
            issues.append(issue('FASTENER_IN_CUTOUT', 'error', 'fastener',
                                f"'{fid}' lands in {hit['kind']} '{hit['id']}' of '{b.id}'.", comps, joint=jid,
                                feature=hit['id'], location=_r(P)))
        elif G.dist_to_boundary(pb[:2], b.cut) < spec['bore_b'] / 2.0 + ((mb or {}).get('face_remaining') or 2.0):
            issues.append(issue('FASTENER_NEAR_EDGE', 'error', 'fastener',
                                f"'{fid}' is {G.dist_to_boundary(pb[:2], b.cut):.1f} mm from the edge of '{b.id}' — "
                                f"the bore would break out.", comps, joint=jid, location=_r(P)))
    return bodies, drills, issues


def _seg_dist(p1, q1, p2, q2):
    """Minimum distance between 3D segments p1q1 and p2q2."""
    d1, d2, r = G.v_sub(q1, p1), G.v_sub(q2, p2), G.v_sub(p1, p2)
    a, e, f = G.v_dot(d1, d1), G.v_dot(d2, d2), G.v_dot(d2, r)
    if a < 1e-12 and e < 1e-12:
        return G.v_len(r)
    if a < 1e-12:
        s, t = 0.0, max(0.0, min(1.0, f / e))
    else:
        c = G.v_dot(d1, r)
        if e < 1e-12:
            s, t = max(0.0, min(1.0, -c / a)), 0.0
        else:
            b = G.v_dot(d1, d2)
            den = a * e - b * b
            s = max(0.0, min(1.0, (b * f - c * e) / den)) if den > 1e-12 else 0.0
            t = (b * s + f) / e
            if t < 0:
                s, t = max(0.0, min(1.0, -c / a)), 0.0
            elif t > 1:
                s, t = max(0.0, min(1.0, (b - c) / a)), 1.0
    return G.v_len(G.v_sub(G.v_add(p1, G.v_scale(d1, s)), G.v_add(p2, G.v_scale(d2, t))))


def _in_solid(plate, w, shrink=0.0):
    q = plate.frame.to_local(w)
    return abs(q[2]) < plate.t / 2.0 - shrink and plate.is_material([q[0], q[1]], shrink)


def _boards_on_line(plates, start, direction, length, exclude, step=2.0):
    """Ids of boards whose solid lies on the line start + direction * [0, length]."""
    hits = []
    end = G.v_add(start, G.v_scale(direction, length))
    lo = [min(start[i], end[i]) for i in range(3)]
    hi = [max(start[i], end[i]) for i in range(3)]
    for pid, pl in plates.items():
        if pid in exclude:
            continue
        blo, bhi = pl.world_aabb()
        if any(bhi[i] < lo[i] or blo[i] > hi[i] for i in range(3)):
            continue
        n = max(1, int(length / step))
        if any(_in_solid(pl, G.v_add(start, G.v_scale(direction, length * k / n)), 0.25) for k in range(n + 1)):
            hits.append(pid)
    return hits


def _body_box(p, pad):
    r = p['radius'] + pad
    return ([min(p['start'][i], p['end'][i]) - r for i in range(3)], [max(p['start'][i], p['end'][i]) + r for i in range(3)])


def _near_pairs(bodies, others=None, cell=100.0):
    """Index pairs (i, k) of bodies whose padded boxes share a grid cell (spatial hash, no all-pairs scan).
    With `others`, pairs are (index in bodies, index in others)."""
    grid = {}
    pool = bodies if others is None else others
    for k, q in enumerate(pool):
        lo, hi = _body_box(q, FASTENER_GAP)
        for x in range(int(lo[0] // cell), int(hi[0] // cell) + 1):
            for y in range(int(lo[1] // cell), int(hi[1] // cell) + 1):
                for z in range(int(lo[2] // cell), int(hi[2] // cell) + 1):
                    grid.setdefault((x, y, z), []).append(k)
    pairs = set()
    for i, p in enumerate(bodies):
        lo, hi = _body_box(p, FASTENER_GAP)
        for x in range(int(lo[0] // cell), int(hi[0] // cell) + 1):
            for y in range(int(lo[1] // cell), int(hi[1] // cell) + 1):
                for z in range(int(lo[2] // cell), int(hi[2] // cell) + 1):
                    for k in grid.get((x, y, z), ()):
                        if others is not None or k > i:
                            pairs.add((i, k))
    return sorted(pairs)


def check_fasteners(design, plates, bodies):
    issues = []
    for i, k in _near_pairs(bodies):
        p, q = bodies[i], bodies[k]
        if p['joint'] == q['joint']:
            continue
        d = _seg_dist(p['start'], p['end'], q['start'], q['end'])
        need = p['radius'] + q['radius'] + FASTENER_GAP
        if d < need:
            mid = [(p['start'][j] + p['end'][j] + q['start'][j] + q['end'][j]) / 4 for j in range(3)]
            issues.append(issue('FASTENER_COLLISION', 'error', 'fastener',
                                f"'{p['id']}' and '{q['id']}' pass {d:.1f} mm apart (need {need:.1f} mm): the "
                                f"bores run into each other. Stagger one joint's fasteners (set its 'end' "
                                f"distance), use a different fastener, or offset the boards.",
                                sorted(set(p['boards'] + q['boards'])), joint=p['joint'], other_joint=q['joint'],
                                location=_r(mid), distance=_r(d)))
    for p in bodies:
        L = math.dist(p['start'], p['end'])
        u = G.v_norm(G.v_sub(p['end'], p['start']))
        through = _boards_on_line(plates, p['start'], u, L, set(p['boards']))
        for other in through:
            issues.append(issue('FASTENER_HITS_BOARD', 'error', 'fastener',
                                f"'{p['id']}' runs into '{other}'.", p['boards'] + [other], joint=p['joint']))
        if p['head'] is not None:
            p['blocked_by'] = _boards_on_line(plates, p['head'], G.v_scale(u, -1.0), TOOL_ACCESS, set(p['boards']))
    return issues


def stagger_suggestion(design, plates, joint_id, bodies):
    """A fastener layout (end distance, count) for `joint_id` that clears every other joint's fasteners and
    still satisfies its own rules — verified by re-running the layout, never estimated."""
    j = next(x for x in design['joints'] if x['id'] == joint_id)
    others = [b for b in bodies if b['joint'] != joint_id]
    spec = fastener_spec(j['fasteners'])
    current = j['fasteners'].get('count') or sum(1 for b in bodies if b['joint'] == joint_id)
    for count in sorted({current, 2, current + 1, max(2, current - 1)}, key=lambda c: (abs(c - current), c)):
        for k in range(0, 40):
            end = spec['min_end'] + 5.0 * k
            trial = dict(j, fasteners=dict(j['fasteners'], end=end, count=count))
            mine, _dr, iss = joint_fasteners(design, plates, trial)
            if not mine or any(x['severity'] == 'error' for x in iss):
                continue
            if all(_seg_dist(mine[i]['start'], mine[i]['end'], others[k]['start'], others[k]['end'])
                   >= mine[i]['radius'] + others[k]['radius'] + FASTENER_GAP for i, k in _near_pairs(mine, others)):
                return {'action': 'stagger_fasteners', 'joint': joint_id,
                        'fasteners': {k2: v for k2, v in trial['fasteners'].items()},
                        'message': f"Use {count} {j['fasteners']['kind']}s starting {end:g} mm from the ends on "
                                   f"'{joint_id}'."}
    return None


# ---------------------------------------------------------------------------
# Hinges
# ---------------------------------------------------------------------------

def joint_hinges(design, plates, joint, eval_res, tol=TOL):
    """Cup bores on the door, mounting-plate holes on the carcass; positions moved clear of shelves."""
    a, b = plates.get(joint['a']), plates.get(joint['b'])
    if a is None or b is None or eval_res.get('relation') != 'hinge':
        return [], []
    jid, comps, issues, drills = joint['id'], [a.id, b.id], [], []
    w0, w1 = _edge_world(a, joint['a_edge'])
    L = math.dist(w0, w1)
    u = G.v_norm(G.v_sub(w1, w0))
    _p, _d, na2, _L = edge_frame(a.outline, joint['a_edge'])
    inward = a.frame.dir_to_world([-na2[0], -na2[1], 0])
    # Door back face = the face towards the carcass
    back = 1.0 if G.v_dot(G.v_sub(b.world_centre(), a.frame.p), a.frame.normal) > 0 else -1.0
    to_back = G.v_scale(a.frame.normal, back)
    # Carcass inner face: the face of b on the door's inward side
    inner_face = 1.0 if G.v_dot(inward, b.frame.normal) > 0 else -1.0
    n = eval_res['hinge_count']
    end = min(HINGE['end_distance'], L / 4.0)
    nominal = [end + (L - 2 * end) * i / (n - 1) for i in range(n)] if n > 1 else [L / 2.0]
    others = {pid: pl for pid, pl in plates.items() if pid not in (a.id, b.id)}

    def arm_clear(s):
        # The hinge arm sweeps a box on b's inner face behind the door edge: depth x half-width x height
        base = G.v_add(G.v_add(w0, G.v_scale(u, s)), G.v_scale(to_back, a.t / 2.0))
        pts = []
        for dd in (2.0, HINGE_ARM['depth'] / 2, HINGE_ARM['depth']):
            for ww in (-HINGE_ARM['half_width'], 0.0, HINGE_ARM['half_width']):
                for hh in (b.t / 2.0 + 2.0, b.t / 2.0 + HINGE_ARM['height']):
                    off = G.v_add(G.v_scale(to_back, dd), G.v_scale(u, ww))
                    q = b.frame.to_local(G.v_add(base, off))
                    pts.append(b.frame.to_world([q[0], q[1], inner_face * hh]))
        return [pid for pid, pl in others.items() if any(_in_solid(pl, w, 0.25) for w in pts)]

    positions = []
    for s0 in nominal:
        chosen, blockers = None, arm_clear(s0)
        if not blockers:
            chosen = s0
        else:
            for k in range(1, 20):
                for s in (s0 + 8 * k, s0 - 8 * k):
                    if end * 0.5 <= s <= L - end * 0.5 and not arm_clear(s):
                        chosen = s
                        break
                if chosen is not None:
                    break
            if chosen is None:
                issues.append(issue('HINGE_OBSTRUCTED', 'error', 'hinge',
                                    f"Hinge at {s0:.0f} mm on door '{a.id}' collides with {', '.join(blockers)} and no "
                                    f"clear position exists within 150 mm.", comps + blockers, joint=jid))
                continue
            issues.append(issue('HINGE_POSITION_ADJUSTED', 'info', 'hinge',
                                f"Hinge on door '{a.id}' moved from {s0:.0f} mm to {chosen:.0f} mm to clear "
                                f"{', '.join(blockers)}.", comps + blockers, joint=jid))
        positions.append(chosen)
    for i, s in enumerate(positions):
        cup = G.v_add(G.v_add(w0, G.v_scale(u, s)), G.v_scale(inward, HINGE['cup_centre_from_edge']))
        pc = a.frame.to_local(cup)
        drills.append({'id': f'{jid}/cup{i + 1}', 'component': a.id, 'joint': jid, 'type': 'face_bore',
                       'face': '+z' if back > 0 else '-z', 'position': _r(pc[:2], 2),
                       'diameter': HINGE['cup_diameter'], 'depth': HINGE['cup_depth'], 'through': False,
                       'fastener': 'hinge_cup'})
        if not a.is_material(pc[:2], HINGE['cup_diameter'] / 2.0 + 2.0):
            issues.append(issue('HINGE_CUP_OFF_DOOR', 'error', 'hinge',
                                f"Hinge cup {i + 1} of '{a.id}' does not fit in solid door material.", comps, joint=jid))
        for k in (-1, 1):
            hole = G.v_add(G.v_add(w0, G.v_scale(u, s + k * HINGE_ARM['plate_pitch'] / 2.0)),
                           G.v_scale(to_back, a.t / 2.0 + eval_res.get('gap', 0) + HINGE_ARM['plate_setback']))
            ph = b.frame.to_local(hole)
            drills.append({'id': f'{jid}/plate{i + 1}{"ab"[k > 0]}', 'component': b.id, 'joint': jid,
                           'type': 'face_bore', 'face': '+z' if inner_face > 0 else '-z', 'position': _r(ph[:2], 2),
                           'diameter': 5.0, 'depth': 12.0, 'through': False, 'fastener': 'hinge_plate'})
            if not b.is_material(ph[:2], 4.0):
                issues.append(issue('HINGE_PLATE_OFF_CARCASS', 'error', 'hinge',
                                    f"Mounting-plate hole for hinge {i + 1} of '{a.id}' misses '{b.id}'.", comps,
                                    joint=jid))
    return drills, issues


def door_gaps(design, plates):
    """Neighbouring coplanar doors must keep a reveal so they do not rub when opening."""
    doors = sorted({j['a'] for j in design['joints'] if j['type'] == 'hinge' and j['a'] in plates})
    issues = []
    for i in range(len(doors)):
        for k in range(i + 1, len(doors)):
            p, q = plates[doors[i]], plates[doors[k]]
            if abs(G.v_dot(p.frame.normal, q.frame.normal)) < TOL['parallel'] or \
                    abs(G.v_dot(G.v_sub(q.frame.p, p.frame.p), p.frame.normal)) > 1.0:
                continue
            qp = [p.frame.to_local(q.frame.to_world(v))[:2] for v in q.cut]
            d = G.polygon_distance(p.cut, qp)
            if d < DOOR_MIN_GAP - 1e-6:
                issues.append(issue('DOOR_GAP_TOO_SMALL', 'error' if d <= 0.0 else 'warning', 'hinge',
                                    f"Doors '{p.id}' and '{q.id}' are {d:.1f} mm apart (need {DOOR_MIN_GAP:g} mm "
                                    f"reveal) — they would rub or clash when opened.", [p.id, q.id], gap=_r(d)))
    return issues


# ---------------------------------------------------------------------------
# Connections: classification, undeclared contacts, near-miss gaps, joint alternatives
# ---------------------------------------------------------------------------

def _edge_relation(a, b, w0, w1, a_edge):
    """'L' when A's edge sits at an end of B (A flush with B's edge), 'T' when it lands mid-board."""
    _p, _d, na2, _L = edge_frame(a.outline, a_edge)
    for off in (-a.t / 2.0, a.t / 2.0):
        mid = G.v_add(G.v_scale(G.v_add(w0, w1), 0.5), G.v_scale(a.frame.normal, off))
        q = b.frame.to_local(mid)
        if G.dist_to_boundary([q[0], q[1]], b.cut) <= TOL['contact'] + 0.5:
            return 'L'
    return 'T'


def recommend_joints(design, a, b, relation):
    """Joints that suit this connection, each checked against the board thicknesses and materials."""
    if design.get('joinery', 'interlocking') == 'interlocking':
        return {'recommended': {'type': 'tab_slot', 'reason': 'glue-free design: tab locked through a slot'},
                'alternatives': [], 'unsuitable': []}
    ma, mb = material_of(design, a.comp), material_of(design, b.comp)
    sa = MATERIALS.get(ma['type']) or {}
    cands = []

    def fastened(kind, why):
        spec = FASTENERS[kind]
        need = sa.get('edge_wall', 2.0)
        if need is None:
            return {'type': 'edge_butt', 'fasteners': kind, 'ok': False,
                    'reason': f"{ma['type']} edges cannot take {kind}s"}
        wall = (a.t - spec['bore_a']) / 2.0
        if wall < need:
            return {'type': 'edge_butt', 'fasteners': kind, 'ok': False,
                    'reason': f"{a.t:g} mm edge of '{a.id}' leaves {wall:.1f} mm beside a {spec['bore_a']:g} mm bore "
                              f"(needs {need:g})"}
        if spec['through_b'] and spec['length'] - b.t < spec['min_engagement'] * spec['diameter']:
            return {'type': 'edge_butt', 'fasteners': kind, 'ok': False,
                    'reason': f"standard {spec['length']:g} mm {kind} is too short through {b.t:g} mm '{b.id}'"}
        return {'type': 'edge_butt', 'fasteners': kind, 'ok': True, 'reason': why}

    if relation in ('L', 'T'):
        if ma['type'] in ('particle_board', 'mdf'):
            cands.append(fastened('confirmat', 'standard carcass screw for particle board / MDF; head visible on '
                                               f"the outside of '{b.id}'"))
            cands.append(fastened('dowel', 'concealed; glue + dowels, needs clamping'))
            cands.append(fastened('screw', 'quick; low pull-out strength in board edges'))
        else:
            cands.append(fastened('dowel', 'concealed; glue + dowels'))
            cands.append(fastened('screw', f"strong in {ma['type'].replace('_', ' ')}; head visible on '{b.id}'"))
            cands.append(fastened('confirmat', 'strong; head visible'))
        if relation == 'L':
            same = abs(a.t - b.t) < 0.5
            cands.append({'type': 'edge_mitre', 'bevel': True, 'ok': same,
                          'reason': 'hides both board edges (needs a tilting saw blade, glue and clamping)' if same
                          else 'mitre needs equal board thickness'})
        cands.append({'type': 'dado / rabbet', 'ok': False, 'reason': 'housing joints are not modelled yet'})
    elif relation == 'face':
        cands.append({'type': 'face_lap', 'ok': True, 'reason': 'glue (+ screws from the hidden face)'})
    elif relation == 'edge_to_edge':
        cands.append({'type': 'edge_mitre', 'fasteners': 'dowel', 'ok': min(a.t, b.t) >= 12,
                      'reason': 'dowelled edge joint' if min(a.t, b.t) >= 12 else 'too thin for dowels'})
        if ma['type'] == mb['type'] == 'solid_wood':
            cands.append({'type': 'edge_mitre', 'ok': True, 'reason': 'long-grain glue joint'})
    ok = [c for c in cands if c['ok']]
    return {'recommended': ok[0] if ok else None, 'alternatives': ok[1:],
            'unsuitable': [c for c in cands if not c['ok']]}


def find_contacts(design, plates, tol=TOL):
    """Undeclared board-to-board contacts and near-miss gaps (edge on face, face on face)."""
    declared = {frozenset((j['a'], j['b'])) for j in design['joints']}
    # Hinged doors move: their clearance to the carcass is intentional (overlaps are collisions anyway)
    doors = {j['a'] for j in design['joints'] if j['type'] == 'hinge'}
    out = []
    ids = sorted(p for p in plates if p not in doors)
    for i in range(len(ids)):
        check_budget()
        for k in range(len(ids)):
            if i == k:
                continue
            a, b = plates[ids[i]], plates[ids[k]]
            if frozenset((a.id, b.id)) in declared:
                continue
            (alo, ahi), (blo, bhi) = a.world_aabb(), b.world_aabb()
            if any(alo[d] > bhi[d] + GAP_SEARCH or blo[d] > ahi[d] + GAP_SEARCH for d in range(3)):
                continue
            dot = abs(G.v_dot(a.frame.normal, b.frame.normal))
            if dot < tol['perpendicular']:
                for e in range(len(a.outline)):
                    w0, w1 = _edge_world(a, e)
                    l0, l1 = b.frame.to_local(w0), b.frame.to_local(w1)
                    if abs(l0[2] - l1[2]) > tol['contact'] or math.dist(w0, w1) < 5.0:
                        continue
                    _p, _d, na2, _L = edge_frame(a.outline, e)
                    out_w = a.frame.dir_to_world([na2[0], na2[1], 0])
                    zmid = (l0[2] + l1[2]) / 2.0
                    if (G.v_dot(out_w, b.frame.normal) > 0) == (zmid > 0) and abs(zmid) > 1e-6:
                        continue   # edge faces away from b
                    gap = abs(zmid) - b.t / 2.0
                    if gap < -tol['contact'] or gap > GAP_SEARCH:
                        continue
                    run = _contact_run(a, b, w0, w1)
                    if run is None or (run[1] - run[0]) * math.dist(w0, w1) < tol['min_contact_length']:
                        continue
                    rel = _edge_relation(a, b, w0, w1, e)
                    rec = {'a': a.id, 'a_edge': e, 'b': b.id, 'relation': rel, 'gap': _r(gap),
                           'contact_length': _r((run[1] - run[0]) * math.dist(w0, w1)),
                           'normal': b.frame.normal if zmid > 0 else G.v_scale(b.frame.normal, -1.0),
                           'joint': {'type': 'edge_butt', 'a': a.id, 'a_edge': e, 'b': b.id}}
                    if gap > tol['contact']:
                        rec['delta'] = _r(G.v_scale(out_w, gap), 3)
                    out.append(rec)
            elif dot > tol['parallel'] and i < k:
                sep = G.v_dot(G.v_sub(b.frame.p, a.frame.p), a.frame.normal)
                gap = abs(sep) - (a.t + b.t) / 2.0
                if -tol['contact'] <= gap <= GAP_SEARCH:
                    from .validation import _projected_overlap
                    area, _c = _projected_overlap(a, b)
                    if area >= tol['min_lap_area']:
                        rec = {'a': a.id, 'b': b.id, 'relation': 'face', 'gap': _r(gap), 'contact_area': _r(area, 1),
                               'normal': G.v_scale(a.frame.normal, 1.0 if sep < 0 else -1.0),
                               'joint': {'type': 'face_lap', 'a': a.id, 'b': b.id}}
                        if gap > tol['contact']:
                            rec['delta'] = _r(G.v_scale(a.frame.normal, gap if sep > 0 else -gap), 3)
                        out.append(rec)
    return out


def analyse_connections(design, plates, joint_results):
    """Classify every declared joint and every undeclared contact; recommend joints."""
    conns = []
    for j in design['joints']:
        a, b = plates.get(j['a']), plates.get(j['b'])
        if a is None or b is None:
            continue
        res = joint_results.get(j['id'], {})
        if j['type'] in ('edge_butt', 'tab_slot'):
            if j['type'] == 'edge_butt' and j['a_edge'] < len(a.outline):
                w0, w1 = _edge_world(a, j['a_edge'])
                rel = _edge_relation(a, b, w0, w1, j['a_edge'])
            else:
                rel = 'T'
        else:
            rel = res.get('relation') or {'face_lap': 'face', 'edge_mitre': 'mitre', 'hinge': 'hinge',
                                          'finger': 'L', 'cross_lap': 'X'}[j['type']]
        c = {'joint': j['id'], 'type': j['type'], 'a': j['a'], 'b': j['b'], 'relation': rel,
             'fasteners': (j.get('fasteners') or {}).get('kind'), 'status': j.get('status')}
        if j['type'] in ('edge_butt', 'edge_mitre') and design.get('joinery') == 'glue_allowed':
            c['options'] = recommend_joints(design, a, b, rel if rel != 'mitre' else 'L')
        conns.append(c)
    return conns


# ---------------------------------------------------------------------------
# Assembly planning (assembly by disassembly on a local blocking graph)
# ---------------------------------------------------------------------------

def _constraints(design, plates, contacts):
    """Per connection: (x, y, kind, axis). 'slide': x may only leave y along +axis (y along -axis);
    'contact': x may not move along -axis relative to y (it rests on y)."""
    cons = []
    for j in design['joints']:
        if j.get('status') != 'joined' or j['a'] not in plates or j['b'] not in plates:
            continue
        a, b = plates[j['a']], plates[j['b']]
        if j['type'] == 'tab_slot':
            tab = next((t for t in a.comp['tabs'] if t['id'] == j['tab']), None)
            if tab is None or tab['edge'] >= len(a.outline):
                continue
            tg = tab_geometry(a.comp, tab)
            ins = a.frame.dir_to_world([tg['normal'][0], tg['normal'][1], 0])
            cons.append((a.id, b.id, 'slide', G.v_scale(ins, -1.0), j['id']))
        elif j['type'] in ('edge_butt', 'edge_mitre', 'hinge'):
            if j['a_edge'] >= len(a.outline):
                continue
            _p, _d, na2, _L = edge_frame(a.outline, j['a_edge'])
            away = G.v_scale(a.frame.dir_to_world([na2[0], na2[1], 0]), -1.0)     # A leaves B along d_in
            if j['type'] == 'hinge':
                side = 1.0 if G.v_dot(G.v_sub(a.frame.p, b.world_centre()), a.frame.normal) > 0 else -1.0
                away = G.v_scale(a.frame.normal, side)
            elif j['type'] == 'edge_mitre' and abs(G.v_dot(a.frame.normal, b.frame.normal)) < TOL['parallel']:
                away = G.v_norm(G.v_sub(a.world_centre(), b.world_centre()))
            kind = 'slide' if (j.get('fasteners') or {}).get('kind') == 'dowel' else 'contact'
            cons.append((a.id, b.id, kind, away, j['id']))
        elif j['type'] == 'face_lap':
            n = G.v_scale(a.frame.normal, 1.0 if G.v_dot(G.v_sub(a.frame.p, b.frame.p), a.frame.normal) > 0 else -1.0)
            cons.append((a.id, b.id, 'contact', n, j['id']))
        elif j['type'] in ('finger', 'cross_lap'):
            # A leaves B away from B's face (finger) / out of its halving notch along the crossing (cross-lap)
            if j['type'] == 'finger':
                n = b.frame.normal
                away = G.v_scale(n, 1.0 if G.v_dot(G.v_sub(a.world_centre(), b.world_centre()), n) > 0 else -1.0)
            else:
                from .validation import cross_lap_exit
                away = cross_lap_exit(a, b)
                if away is None:
                    continue
            cons.append((a.id, b.id, 'slide', away, j['id']))
    for c in contacts:
        if c['gap'] <= TOL['contact']:
            n = c['normal']   # points from b towards a
            cons.append((c['a'], c['b'], 'contact', n, None))
    return cons


def _free(kind, axis, m, mover_is_x):
    d = G.v_dot(axis, m) * (1.0 if mover_is_x else -1.0)
    return d > 1 - 1e-3 if kind == 'slide' else d > -1e-3


def _sccs(nodes, edges):
    index, low, on, stack, out, counter = {}, {}, set(), [], [], [0]

    def strong(v):
        work = [(v, iter(edges.get(v, ())))]
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        while work:
            node, it = work[-1]
            nxt = next(it, None)
            if nxt is None:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[node])
                if low[node] == index[node]:
                    comp = set()
                    while True:
                        w = stack.pop()
                        on.discard(w)
                        comp.add(w)
                        if w == node:
                            break
                    out.append(comp)
            elif nxt not in index:
                index[nxt] = low[nxt] = counter[0]
                counter[0] += 1
                stack.append(nxt)
                on.add(nxt)
                work.append((nxt, iter(edges.get(nxt, ()))))
            elif nxt in on:
                low[node] = min(low[node], index[nxt])
    for v in nodes:
        if v not in index:
            strong(v)
    return out


def plan_assembly(design, plates, contacts, bodies):
    """Assembly order with sub-assemblies, or the boards that lock each other. Returns (plan, issues)."""
    cons = _constraints(design, plates, contacts)
    doors = {j['a'] for j in design['joints'] if j['type'] == 'hinge'}   # hung last, once the carcass is square
    dirs = []
    for _x, _y, _k, axis, _j in cons:
        for s in (1.0, -1.0):
            v = G.v_scale(axis, s)
            if G.v_len(v) > 0.5 and not any(G.v_dot(v, d) > 1 - 1e-4 for d in dirs):
                dirs.append(v)
    issues = []

    def disassemble(group):
        """Returns a list of removal steps for `group` (reverse = assembly), or None if locked."""
        group = set(group)
        steps = []
        while len(group) > 1:
            best = None
            local = [c for c in cons if c[0] in group and c[1] in group]
            for m in dirs:
                edges = {}
                for x, y, kind, axis, _j in local:
                    if not _free(kind, axis, m, True):
                        edges.setdefault(x, set()).add(y)      # x moving along m is blocked by y
                    if not _free(kind, axis, m, False):
                        edges.setdefault(y, set()).add(x)
                comps = _sccs(sorted(group), edges)
                where = {v: i for i, c in enumerate(comps) for v in c}
                for i, c in enumerate(comps):
                    if len(c) == len(group):
                        continue
                    if any(where[w] != i for v in c for w in edges.get(v, ())):
                        continue   # not a sink: something outside blocks it
                    # Prefer parts that are attached to the rest (so, reversed, every step connects to what
                    # is already built) and leave the rest in one piece; then the smallest part; then the
                    # direction that pulls most squarely off its contacts.
                    rest = group - c
                    links = [(x, y, axis) for x, y, _k, axis, _j in local if (x in c) != (y in c)]
                    pull = sum(G.v_dot(m, axis) if x in c else -G.v_dot(m, axis) for x, y, axis in links)
                    key = (not links, not _connected(rest, local), not c <= doors, len(c), -pull)
                    if best is None or key < best[2]:
                        best = (c, m, key)
            if best is None:
                return None, group
            part, m, _key = best
            if len(part) > 1:
                sub, stuck = disassemble(part)
                if sub is None:
                    return None, stuck
                steps.append({'remove': sorted(part), 'direction': _r(m, 3), 'subassembly': sub})
            else:
                steps.append({'remove': sorted(part), 'direction': _r(m, 3)})
            group -= part
        return steps, None

    plan = []
    # Independent assemblies (nothing joined or touching between them) are planned separately
    adj = {p: set() for p in plates}
    for x, y, *_ in cons:
        adj[x].add(y)
        adj[y].add(x)
    seen = set()
    for start in sorted(plates):
        if start in seen:
            continue
        grp, stack = set(), [start]
        while stack:
            v = stack.pop()
            if v not in grp:
                grp.add(v)
                stack.extend(adj[v] - grp)
        seen |= grp
        steps, stuck = disassemble(grp)
        if steps is None:
            issues.append(issue('ASSEMBLY_LOCKED', 'error', 'assembly',
                                f"Boards {', '.join(sorted(stuck))} lock each other: no board or sub-assembly can be "
                                f"brought into place along its tab / dowel directions. Change one joint to screws "
                                f"or reorient a tab.", sorted(stuck)))
            continue
        plan.append({'boards': sorted(grp), 'steps': _assembly_steps(steps, grp)})
    issues += _access_order_issues(design, plan, bodies)
    return plan, issues


def _connected(nodes, cons):
    nodes = set(nodes)
    if len(nodes) <= 1:
        return True
    adj = {v: set() for v in nodes}
    for x, y, *_ in cons:
        if x in nodes and y in nodes:
            adj[x].add(y)
            adj[y].add(x)
    start = next(iter(nodes))
    seen, stack = {start}, [start]
    while stack:
        for w in adj[stack.pop()] - seen:
            seen.add(w)
            stack.append(w)
    return seen == nodes


def _assembly_steps(removal, group):
    """Reverse a removal list into assembly steps: [{add: [...], direction, subassembly?}] starting from a base."""
    base = sorted(set(group) - {b for s in removal for b in s['remove']})
    steps = [{'base': base}]
    for s in reversed(removal):
        st = {'add': s['remove'], 'direction': [-v for v in s['direction']]}
        if 'subassembly' in s:
            st['subassembly'] = _assembly_steps(s['subassembly'], s['remove'])
        steps.append(st)
    return steps


def _flatten(steps, out):
    """Order in which boards become part of the assembly (sub-assemblies first, then merged)."""
    for st in steps:
        if 'base' in st:
            out.append(set(st['base']))
        elif 'subassembly' in st:
            _flatten(st['subassembly'], out)
            out.append(set(st['add']))
        else:
            out.append(set(st['add']))
    return out


def _access_order_issues(design, plan, bodies):
    """A screw is driven when both its boards are present; a board in the driver's line must come later."""
    issues = []
    for asm in plan:
        order = {}
        for i, grp in enumerate(_flatten(asm['steps'], [])):
            for b in grp:
                order.setdefault(b, i)
        for p in bodies:
            if not p.get('blocked_by') or p['boards'][0] not in order:
                continue
            when = max(order.get(b, 0) for b in p['boards'])
            late = [c for c in p['blocked_by'] if order.get(c, -1) > when]
            early = [c for c in p['blocked_by'] if c not in late]
            if early:
                issues.append(issue('TOOL_ACCESS_BLOCKED', 'error', 'assembly',
                                    f"The head of '{p['id']}' cannot be reached: {', '.join(early)} is in the way of the "
                                    f"driver and is fitted before this joint can be fastened.",
                                    p['boards'] + early, joint=p['joint']))
            elif late:
                issues.append(issue('FASTEN_BEFORE_FITTING', 'info', 'assembly',
                                    f"Drive '{p['id']}' before fitting {', '.join(late)}.", p['boards'] + late,
                                    joint=p['joint']))
    return issues


# ---------------------------------------------------------------------------
# Material constraints
# ---------------------------------------------------------------------------

def material_issues(design, plates, compensate_kerf=None):
    issues = []
    for pid, pl in plates.items():
        m = material_of(design, pl.comp)
        spec = MATERIALS.get(m['type'])
        rect = G.oriented_rect(pl.cut)
        if spec:
            if not any(abs(pl.t - t) <= spec['thickness_tol'] for t in spec['thicknesses']):
                issues.append(issue('NONSTANDARD_THICKNESS', 'warning', 'material',
                                    f"'{pid}' is {pl.t:g} mm {m['type'].replace('_', ' ')}; stock thicknesses are "
                                    f"{', '.join(f'{t:g}' for t in spec['thicknesses'])} mm.", [pid]))
            if rect['width'] < spec['min_part']:
                issues.append(issue('PART_BELOW_MIN_SIZE', 'error', 'material',
                                    f"'{pid}' is only {rect['width']:.1f} mm wide; {m['type'].replace('_', ' ')} parts "
                                    f"narrower than {spec['min_part']:g} mm cannot be cut safely.", [pid],
                                    width=_r(rect['width'])))
            if spec['grain'] and not pl.comp.get('grain'):
                issues.append(issue('GRAIN_UNSPECIFIED', 'info', 'material',
                                    f"'{pid}' has no grain direction; nesting may turn it either way.", [pid]))
        g = pl.comp.get('grain')
        if g and m['type'] == 'solid_wood' and rect['length'] > 2 * rect['width']:
            along = abs(math.cos(math.radians(rect['angle'] - (0.0 if g == 'x' else 90.0)))) > 0.5
            if not along:
                issues.append(issue('GRAIN_ACROSS_LENGTH', 'warning', 'material',
                                    f"Solid-wood '{pid}' ({rect['length']:.0f} x {rect['width']:.0f} mm) has its grain "
                                    f"across its length — it will be weak and may crack.", [pid]))
        joined_edges = {j['a_edge'] for j in design['joints'] if j['a'] == pid and 'a_edge' in j}
        for eb in pl.comp.get('edge_banding', []):
            _a, _d, _n, L = edge_frame(pl.outline, eb['edge'])
            if L < 20.0:
                issues.append(issue('BANDING_ON_SHORT_EDGE', 'warning', 'material',
                                    f"Edge {eb['edge']} of '{pid}' is {L:.1f} mm long — too short for an edge bander.",
                                    [pid]))
            if eb['edge'] in joined_edges:
                issues.append(issue('BANDING_ON_JOINED_EDGE', 'warning', 'material',
                                    f"Edge {eb['edge']} of '{pid}' is banded but butts against another board.", [pid]))
            if any(t['edge'] == eb['edge'] for t in pl.comp.get('tabs', [])):
                issues.append(issue('BANDING_ON_TABBED_EDGE', 'error', 'material',
                                    f"Edge {eb['edge']} of '{pid}' carries a tab and cannot be edge-banded.", [pid]))
    if compensate_kerf is False:
        kerf = design['material']['kerf']
        tight = min((MATERIALS.get(material_of(design, pl.comp)['type']) or {'cut_tol': None})['cut_tol'] or 1e9
                    for pl in plates.values()) if plates else 1e9
        if kerf / 2.0 > tight:
            issues.append(issue('KERF_NOT_COMPENSATED', 'error', 'material',
                                f"Cut paths are not kerf-compensated: every part would come out {kerf / 2:.2f} mm "
                                f"undersize per edge (tolerance {tight:g} mm). Enable kerf compensation.", []))
    return issues


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def manufacturing_report(design, compensate_kerf=None, validation=None):
    """Everything needed to judge whether the design can be made and assembled."""
    plates = build_plates(design)
    joint_results, issues, bodies, drills = {}, [], [], []
    for j in design['joints']:
        if j['a'] not in plates or j['b'] not in plates:
            continue
        res = evaluate_joint(design, plates, j)
        joint_results[j['id']] = res
        if j.get('fasteners'):
            bd, dr, iss = joint_fasteners(design, plates, j)
            bodies += bd
            drills += dr
            issues += iss
        if j['type'] == 'hinge' and res['ok']:
            dr, iss = joint_hinges(design, plates, j, res)
            drills += dr
            issues += iss
    issues += check_fasteners(design, plates, bodies)
    # One verified stagger suggestion per joint, for the first STAGGER_SUGGESTIONS joints (a design with
    # hundreds of collisions needs a layout change, not hundreds of individual suggestions)
    suggested = {}
    for i in issues:
        if i['code'] == 'FASTENER_COLLISION':
            jid = i['other_joint']
            if jid not in suggested and len(suggested) < STAGGER_SUGGESTIONS:
                suggested[jid] = stagger_suggestion(design, plates, jid, bodies)
            if suggested.get(jid):
                i['suggestion'] = suggested[jid]
    issues += door_gaps(design, plates)
    contacts = find_contacts(design, plates)
    for c in contacts:
        if 'delta' in c:
            issues.append(issue('POSSIBLE_GAP', 'warning', 'connection',
                                f"'{c['a']}'" + (f" edge {c['a_edge']}" if 'a_edge' in c else '') +
                                f" stops {c['gap']:.2f} mm short of '{c['b']}' and no joint connects them — an "
                                f"unintended gap? Moving '{c['a']}' by {c['delta']} closes it.", [c['a'], c['b']],
                                gap=c['gap'], suggestion={'action': 'translate', 'component': c['a'], 'delta': c['delta']},
                                candidate_joint=c['joint']))
        else:
            a, b = plates[c['a']], plates[c['b']]
            issues.append(issue('CONTACT_WITHOUT_JOINT', 'warning', 'connection',
                                f"'{c['a']}' touches '{c['b']}' ({c['relation']}) but no joint connects them.",
                                [c['a'], c['b']], relation=c['relation'], candidate_joint=c['joint'],
                                options=recommend_joints(design, a, b, c['relation'])))
    plan, asm_issues = plan_assembly(design, plates, contacts, bodies)
    issues += asm_issues
    issues += material_issues(design, plates, compensate_kerf)
    for j in design['joints']:
        if j['type'] == 'edge_butt' and not j.get('fasteners') and design.get('joinery') == 'glue_allowed' \
                and j['a'] in plates and material_of(design, plates[j['a']].comp)['type'] in ('particle_board', 'mdf'):
            issues.append(issue('WEAK_JOINT', 'warning', 'connection',
                                f"'{j['id']}' is a glue-only butt joint on the edge of "
                                f"{material_of(design, plates[j['a']].comp)['type'].replace('_', ' ')} '{j['a']}', "
                                f"which holds poorly. Add confirmat screws or dowels.", [j['a'], j['b']], joint=j['id']))
    errors = sum(1 for i in issues if i['severity'] == 'error')
    return {'manufacturable': errors == 0,
            'summary': {'errors': errors, 'warnings': sum(1 for i in issues if i['severity'] == 'warning'),
                        'fasteners': len(bodies), 'drilling_operations': len(drills)},
            'issues': issues, 'drilling': drills,
            'fasteners': [{k: (_r(v, 2) if k in ('start', 'end') else v) for k, v in b.items()
                           if k not in ('axis', 'head', 'end_used')} for b in bodies],
            'connections': analyse_connections(design, plates, joint_results),
            'contacts': [{k: v for k, v in c.items() if k != 'normal'} for c in contacts],
            'assembly_plan': plan}
