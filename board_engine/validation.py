"""
Geometry validation pipeline.

Three layers, all returning lists of structured issues:

  1. validate_component()  - 2D cut-profile rules (outline, tabs, features, margins, sheet fit)
  2. evaluate_joint()      - does a proposed connection physically work? distinguishes
                             missing slot / wrong slot / gap / overlap / bad orientation /
                             tab landing in an intentional opening ...
  3. find_collisions()     - 3D interference between plates (mid-plane cross-section test
                             against real material: outline + tabs - slots/holes/openings)

validate_design() combines them with design-level checks (duplicates, unused slots,
broken joints, floating components).

Issue shape:
  {code, severity: error|warning|info, category, message,
   components: [...], joint?, feature?, location?: [x,y,z],
   repair?:     {action, ...}   # set only when the engine can SAFELY auto-correct it
   suggestion?: {...}}          # a hint the caller (user / AI agent) may apply
"""
import math

from . import geometry as G
from .model import (Plate, build_plates, feature_polygon, tab_geometry, edge_frame,
                    find_component, thickness_of)

TOL = {
    'contact': 0.25,          # mm: allowed gap/penetration at a mating surface
    'slot_position': 0.5,     # mm: slot centre vs tab footprint centre
    'slot_fit': 0.15,         # mm: allowed deviation from expected slot dimension
    'slot_loose': 0.6,        # mm: beyond expected+this a slot is considered loose
    'angle': 1.0,             # deg
    'parallel': 0.9995,       # |dot| of normals regarded as parallel
    'perpendicular': 0.03,    # |dot| of normals regarded as perpendicular
    'min_edge_margin': 1.5,   # mm: below this the bridge of material breaks
    'rec_edge_margin': 3.0,   # mm: recommended
    'min_feature_spacing': 1.0,
    'min_feature_size': 1.0,
    'min_tab_width': 3.0,
    'min_contact_length': 5.0,
    'min_lap_area': 30.0,     # mm^2
    'sample_step': 0.5,
}


def issue(code, severity, category, message, components=(), **extra):
    d = {'code': code, 'severity': severity, 'category': category, 'message': message,
         'components': list(components)}
    for k, v in extra.items():
        if v is not None:
            d[k] = v
    return d


def _r(v, n=2):
    if isinstance(v, (list, tuple)):
        return [round(x, n) for x in v]
    return round(v, n)


# ---------------------------------------------------------------------------
# 1. Component-level (2D) validation
# ---------------------------------------------------------------------------

def validate_component(design, comp, tol=TOL):
    out = []
    cid = comp['id']
    t = thickness_of(design, comp)
    outline = comp['outline']
    n = len(outline)

    for i in range(n):
        a, b = outline[i], outline[(i + 1) % n]
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 0.01:
            out.append(issue('DEGENERATE_EDGE', 'error', '2d',
                             f"'{cid}' outline edge {i} has zero length (duplicate vertex).", [cid], edge=i))
    if G.self_intersections(outline):
        out.append(issue('OUTLINE_SELF_INTERSECTION', 'error', '2d',
                         f"'{cid}' outline crosses itself; it cannot be cut as one piece.", [cid]))
        return out
    if abs(G.signed_area(outline)) < 1.0:
        out.append(issue('DEGENERATE_OUTLINE', 'error', '2d', f"'{cid}' outline has no area.", [cid]))
        return out

    # Tabs
    ids = set()
    for tab in comp.get('tabs', []):
        if tab['id'] in ids:
            out.append(issue('DUPLICATE_TAB_ID', 'error', '2d', f"'{cid}' has two tabs with id '{tab['id']}'.",
                             [cid], feature=tab['id']))
        ids.add(tab['id'])
        if tab['edge'] >= n:
            out.append(issue('TAB_EDGE_INVALID', 'error', '2d',
                             f"Tab '{tab['id']}' on '{cid}' references edge {tab['edge']} but the outline has {n} edges.",
                             [cid], feature=tab['id']))
            continue
        _a, _d, _n, L = edge_frame(outline, tab['edge'])
        lo, hi = tab['offset'] - tab['width'] / 2.0, tab['offset'] + tab['width'] / 2.0
        if lo < 0.5 or hi > L - 0.5:
            out.append(issue('TAB_OUTSIDE_EDGE', 'error', '2d',
                             f"Tab '{tab['id']}' on '{cid}' spans {lo:.1f}..{hi:.1f} mm but edge {tab['edge']} "
                             f"is only {L:.1f} mm long (needs 0.5 mm shoulders).", [cid], feature=tab['id']))
        if tab['width'] < max(tol['min_tab_width'], t):
            out.append(issue('TAB_TOO_NARROW', 'warning', 'manufacturing',
                             f"Tab '{tab['id']}' on '{cid}' is {tab['width']:.1f} mm wide; "
                             f"tabs narrower than {max(tol['min_tab_width'], t):.1f} mm snap easily.",
                             [cid], feature=tab['id']))
    tabs = [x for x in comp.get('tabs', []) if x['edge'] < n]
    for i in range(len(tabs)):
        for j in range(i + 1, len(tabs)):
            a, b = tabs[i], tabs[j]
            if a['edge'] == b['edge'] and abs(a['offset'] - b['offset']) < (a['width'] + b['width']) / 2.0 + 0.5:
                out.append(issue('TAB_OVERLAP', 'error', '2d',
                                 f"Tabs '{a['id']}' and '{b['id']}' on '{cid}' overlap on edge {a['edge']}.",
                                 [cid], feature=a['id']))

    cut = Plate(design, comp).cut
    if G.self_intersections(cut):
        out.append(issue('CUT_PROFILE_SELF_INTERSECTION', 'error', '2d',
                         f"'{cid}' cut profile (outline + tabs) crosses itself.", [cid]))

    # Features
    fids = set()
    polys = []
    for f in comp.get('features', []):
        if f['id'] in fids:
            out.append(issue('DUPLICATE_FEATURE_ID', 'error', '2d',
                             f"'{cid}' has two features with id '{f['id']}'.", [cid], feature=f['id']))
        fids.add(f['id'])
        poly = feature_polygon(f)
        polys.append((f, poly))
        size = f['diameter'] if f['shape'] == 'circle' else min(f['width'], f['height'])
        if size < tol['min_feature_size']:
            out.append(issue('FEATURE_TOO_SMALL', 'error', 'manufacturing',
                             f"Feature '{f['id']}' on '{cid}' is {size:.2f} mm; the laser cannot cut features "
                             f"below {tol['min_feature_size']} mm.", [cid], feature=f['id']))
        if not all(G.point_in_polygon(p, cut) for p in poly) or G.polygon_distance(poly, cut) == 0.0:
            out.append(issue('FEATURE_OUTSIDE_OUTLINE', 'error', '2d',
                             f"{f['kind'].capitalize()} '{f['id']}' on '{cid}' is not fully inside the outline "
                             f"(it would cut an open notch).", [cid], feature=f['id']))
            continue
        m = G.polygon_distance(poly, cut)
        if m < tol['min_edge_margin']:
            out.append(issue('INSUFFICIENT_EDGE_MARGIN', 'error', 'manufacturing',
                             f"{f['kind'].capitalize()} '{f['id']}' on '{cid}' is {m:.2f} mm from the edge "
                             f"(minimum {tol['min_edge_margin']} mm) — the bridge would break.",
                             [cid], feature=f['id'], margin=_r(m)))
        elif m < tol['rec_edge_margin'] and f['kind'] == 'slot':
            out.append(issue('NARROW_EDGE_MARGIN', 'warning', 'manufacturing',
                             f"Slot '{f['id']}' on '{cid}' is {m:.2f} mm from the edge "
                             f"(recommended {tol['rec_edge_margin']} mm).", [cid], feature=f['id'], margin=_r(m)))
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            (fa, pa), (fb, pb) = polys[i], polys[j]
            if G.polygons_overlap(pa, pb):
                out.append(issue('FEATURE_OVERLAP', 'error', '2d',
                                 f"Features '{fa['id']}' ({fa['kind']}) and '{fb['id']}' ({fb['kind']}) on '{cid}' overlap.",
                                 [cid], feature=fb['id'], other_feature=fa['id']))
            else:
                d = G.polygon_distance(pa, pb)
                if d < tol['min_feature_spacing']:
                    out.append(issue('FEATURE_SPACING', 'error', 'manufacturing',
                                     f"Features '{fa['id']}' and '{fb['id']}' on '{cid}' are only {d:.2f} mm apart "
                                     f"(minimum {tol['min_feature_spacing']} mm).",
                                     [cid], feature=fb['id'], other_feature=fa['id']))

    # Sheet fit
    x0, y0, x1, y1 = G.bbox(cut)
    w, h = x1 - x0, y1 - y0
    sw, sh = design['sheet']['width'], design['sheet']['height']
    if not ((w <= sw and h <= sh) or (h <= sw and w <= sh)):
        out.append(issue('PART_EXCEEDS_SHEET', 'error', 'manufacturing',
                         f"'{cid}' ({w:.1f} x {h:.1f} mm) does not fit on the {sw:.0f} x {sh:.0f} mm sheet.", [cid]))
    return out


# ---------------------------------------------------------------------------
# 2. Joint evaluation
# ---------------------------------------------------------------------------

def _find_tab(comp, tab_id):
    for t in comp.get('tabs', []):
        if t['id'] == tab_id:
            return t
    return None


def slot_users(design, comp_id, slot_id, exclude_joint=None):
    return [j['id'] for j in design['joints']
            if j.get('status') == 'joined' and j['type'] == 'tab_slot' and j['b'] == comp_id
            and j.get('slot') == slot_id and j['id'] != exclude_joint]


def evaluate_joint(design, plates, joint, tol=TOL):
    """Evaluate a joint spec against current geometry.

    Returns {'ok': bool, 'issues': [...], 'matched_slot': id|None, 'location': [x,y,z]|None}
    """
    issues = []
    a, b = plates.get(joint['a']), plates.get(joint['b'])
    jid = joint['id']
    if a is None or b is None:
        missing = [x for x in (joint['a'], joint['b']) if x not in plates]
        issues.append(issue('JOINT_REFERENCE_INVALID', 'error', 'joint',
                            f"Joint '{jid}' references missing component(s): {', '.join(missing)}.",
                            [joint['a'], joint['b']], joint=jid))
        return {'ok': False, 'issues': issues, 'matched_slot': None, 'location': None}
    if a.id == b.id:
        issues.append(issue('JOINT_SELF_REFERENCE', 'error', 'joint',
                            f"Joint '{jid}' connects '{a.id}' to itself.", [a.id], joint=jid))
        return {'ok': False, 'issues': issues, 'matched_slot': None, 'location': None}

    fn = {'tab_slot': _eval_tab_slot, 'edge_butt': _eval_edge_butt,
          'edge_mitre': _eval_edge_mitre, 'face_lap': _eval_face_lap}[joint['type']]
    res = fn(design, a, b, joint, tol, issues)
    res['issues'] = issues
    res['ok'] = not any(i['severity'] == 'error' for i in issues)
    return res


def _eval_tab_slot(design, a, b, joint, tol, issues):
    jid = joint['id']
    comps = [a.id, b.id]
    tab = _find_tab(a.comp, joint['tab'])
    if tab is None:
        issues.append(issue('TAB_NOT_FOUND', 'error', 'joint',
                            f"Component '{a.id}' has no tab '{joint['tab']}'.", comps, joint=jid))
        return {'matched_slot': None, 'location': None}
    if tab['edge'] >= len(a.outline):
        issues.append(issue('TAB_EDGE_INVALID', 'error', 'joint',
                            f"Tab '{tab['id']}' references a non-existent edge.", comps, joint=jid))
        return {'matched_slot': None, 'location': None}
    tg = tab_geometry(a.comp, tab)
    ins_w = a.frame.dir_to_world([tg['normal'][0], tg['normal'][1], 0])   # insertion direction
    root_w = a.frame.to_world([tg['root'][0], tg['root'][1], 0])
    location = _r(a.frame.to_world([tg['centre'][0], tg['centre'][1], 0]))
    nb = b.frame.normal
    dot = G.v_dot(ins_w, nb)

    if abs(dot) < tol['parallel'] - 0.0015:  # ~ >3 deg off the receiver normal
        ang = math.degrees(math.acos(min(1.0, abs(dot))))
        issues.append(issue('ORIENTATION_MISMATCH', 'error', 'joint',
                            f"Tab '{tab['id']}' on '{a.id}' would enter '{b.id}' at {ang:.1f}° from square; "
                            f"a tab must insert perpendicular to the receiving board face.",
                            comps, joint=jid, location=location, angle_error_deg=_r(ang, 1)))
        return {'matched_slot': None, 'location': location}

    root_b = b.frame.to_local(root_w)
    z_root = root_b[2]
    if abs(z_root) > 1e-6 and (z_root > 0) == (dot > 0):
        issues.append(issue('TAB_POINTS_AWAY', 'error', 'joint',
                            f"Tab '{tab['id']}' on '{a.id}' points away from '{b.id}'.", comps,
                            joint=jid, location=location))
        return {'matched_slot': None, 'location': location}

    gap = abs(z_root) - b.t / 2.0
    move = G.v_scale(ins_w, gap)  # moving A by this closes the gap / removes the overlap
    if gap > tol['contact']:
        issues.append(issue('UNINTENDED_GAP', 'error', 'joint',
                            f"'{a.id}' stands {gap:.2f} mm off the face of '{b.id}' at tab '{tab['id']}'. "
                            f"The shoulder must sit on the board.", comps, joint=jid, location=location,
                            gap=_r(gap), suggestion={'action': 'translate', 'component': a.id, 'delta': _r(move, 3)}))
    elif gap < -tol['contact']:
        issues.append(issue('PENETRATION', 'error', 'joint',
                            f"The body of '{a.id}' sinks {-gap:.2f} mm into '{b.id}' beyond the tab shoulder.",
                            comps, joint=jid, location=location, overlap=_r(-gap),
                            suggestion={'action': 'translate', 'component': a.id, 'delta': _r(move, 3)}))

    # Tab depth relative to the receiving board
    if tab['depth'] < b.t * 0.5:
        issues.append(issue('TAB_TOO_SHORT', 'error', 'joint',
                            f"Tab '{tab['id']}' is {tab['depth']:.2f} mm deep but '{b.id}' is {b.t:.2f} mm thick; "
                            f"it would not engage.", comps, joint=jid))
    elif tab['depth'] < b.t - tol['contact']:
        issues.append(issue('TAB_NOT_FLUSH', 'warning', 'joint',
                            f"Tab '{tab['id']}' ({tab['depth']:.2f} mm) does not pass through '{b.id}' ({b.t:.2f} mm).",
                            comps, joint=jid))
    elif tab['depth'] > b.t * 4:
        issues.append(issue('TAB_PROTRUDES', 'warning', 'joint',
                            f"Tab '{tab['id']}' protrudes {tab['depth'] - b.t:.1f} mm beyond '{b.id}'.",
                            comps, joint=jid))

    # Footprint of the tab on the receiver
    centre = [root_b[0], root_b[1]]
    dir_b = b.frame.dir_to_local(a.frame.dir_to_world([tg['dir'][0], tg['dir'][1], 0]))
    angle = math.degrees(math.atan2(dir_b[1], dir_b[0]))
    clearance = design['material']['clearance']
    exp_len, exp_wid = tab['width'] + clearance, a.t + clearance
    footprint = G.rect_polygon(centre, tab['width'], a.t, angle)

    if not all(G.point_in_polygon(p, b.cut) for p in footprint):
        issues.append(issue('TAB_OUTSIDE_RECEIVER', 'error', 'joint',
                            f"Tab '{tab['id']}' lands outside the outline of '{b.id}' — there is no material to "
                            f"receive it.", comps, joint=jid, location=location))
        return {'matched_slot': None, 'location': location}

    for f, poly in b.feature_polys:
        if f['kind'] == 'slot' or not G.polygons_overlap(footprint, poly):
            continue
        code = 'TAB_IN_OPENING' if f['kind'] == 'opening' else 'TAB_IN_HOLE'
        issues.append(issue(code, 'error', 'joint',
                            f"Tab '{tab['id']}' lands in {f['kind']} '{f['id']}' of '{b.id}'. "
                            f"That {f['kind']} is intentional and is preserved; the joint must be moved.",
                            comps, joint=jid, feature=f['id'], location=location))
        return {'matched_slot': None, 'location': location}

    # Locate the receiving slot
    slot = None
    if joint.get('slot'):
        slot = next((f for f in b.features if f['id'] == joint['slot']), None)
        if slot is None or slot['kind'] != 'slot':
            issues.append(issue('SLOT_NOT_FOUND', 'error', 'joint',
                                f"'{b.id}' has no slot '{joint['slot']}'.", comps, joint=jid))
            return {'matched_slot': None, 'location': location}
    else:
        best = None
        for f, poly in b.feature_polys:
            if f['kind'] != 'slot' or f['shape'] != 'rect':
                continue
            # Only a slot that actually overlaps the tab footprint is "the" slot for this tab;
            # a slot elsewhere belongs to another joint and must not be borrowed.
            d = math.hypot(f['center'][0] - centre[0], f['center'][1] - centre[1])
            if G.polygons_overlap(footprint, poly):
                if best is None or d < best[0]:
                    best = (d, f)
        slot = best[1] if best else None

    new_slot = {'id': f"slot-{jid}", 'kind': 'slot', 'shape': 'rect', 'center': _r(centre, 3),
                'width': round(exp_len, 3), 'height': round(exp_wid, 3), 'angle': round(angle, 3),
                'generated_by': jid}
    if slot is None:
        issues.append(issue('MISSING_SLOT', 'error', 'joint',
                            f"'{b.id}' has no slot to receive tab '{tab['id']}' of '{a.id}'. A "
                            f"{exp_len:.2f} x {exp_wid:.2f} mm slot is required at [{centre[0]:.2f}, {centre[1]:.2f}].",
                            comps, joint=jid, location=location,
                            repair={'action': 'create_slot', 'component': b.id, 'feature': new_slot}))
        return {'matched_slot': None, 'location': location}

    users = slot_users(design, b.id, slot['id'], exclude_joint=jid)
    if users:
        issues.append(issue('SLOT_ALREADY_USED', 'error', 'joint',
                            f"Slot '{slot['id']}' on '{b.id}' already receives joint '{users[0]}'.",
                            comps, joint=jid, feature=slot['id']))
        return {'matched_slot': slot['id'], 'location': location}

    off = math.hypot(slot['center'][0] - centre[0], slot['center'][1] - centre[1])
    if off > tol['slot_position']:
        delta_local = [slot['center'][0] - centre[0], slot['center'][1] - centre[1], 0]
        issues.append(issue('SLOT_MISALIGNED', 'error', 'joint',
                            f"Slot '{slot['id']}' on '{b.id}' is {off:.2f} mm away from where tab '{tab['id']}' "
                            f"arrives. Either move '{a.id}' or move the slot.", comps, joint=jid,
                            feature=slot['id'], location=location, offset=_r(off),
                            suggestion={'action': 'translate', 'component': a.id,
                                        'delta': _r(b.frame.dir_to_world(delta_local), 3)}))
        return {'matched_slot': slot['id'], 'location': location}

    # Express slot size along the tab direction
    rel = G.angle_diff_mod180(slot.get('angle', 0.0), angle)
    if rel <= tol['angle']:
        s_len, s_wid = slot['width'], slot['height']
    elif abs(rel - 90.0) <= tol['angle']:
        s_len, s_wid = slot['height'], slot['width']
    else:
        issues.append(issue('SLOT_ORIENTATION_MISMATCH', 'error', 'joint',
                            f"Slot '{slot['id']}' on '{b.id}' is rotated {rel:.1f}° relative to tab '{tab['id']}'.",
                            comps, joint=jid, feature=slot['id'], location=location))
        return {'matched_slot': slot['id'], 'location': location}

    resize = None
    if s_len < tab['width'] + clearance - tol['slot_fit'] or s_wid < a.t + clearance - tol['slot_fit']:
        code = 'SLOT_TOO_SMALL'
        msg = (f"Slot '{slot['id']}' on '{b.id}' is {s_len:.2f} x {s_wid:.2f} mm; tab '{tab['id']}' needs "
               f"{exp_len:.2f} x {exp_wid:.2f} mm (tab + {clearance} mm clearance).")
        resize = True
    elif s_wid > exp_wid + tol['slot_loose']:
        code = 'SLOT_TOO_LOOSE'
        msg = (f"Slot '{slot['id']}' on '{b.id}' is {s_wid:.2f} mm wide for a {a.t:.2f} mm board — "
               f"the joint would rattle.")
        resize = True
    if resize:
        fixed = dict(slot, center=_r(centre, 3), width=round(exp_len, 3), height=round(exp_wid, 3),
                     angle=round(angle, 3))
        issues.append(issue(code, 'error', 'joint', msg, comps, joint=jid, feature=slot['id'], location=location,
                            repair={'action': 'resize_slot', 'component': b.id, 'feature': fixed}))
    elif s_len > exp_len + 2 * tol['slot_loose']:
        issues.append(issue('SLOT_LONGER_THAN_TAB', 'warning', 'joint',
                            f"Slot '{slot['id']}' is {s_len - exp_len:.2f} mm longer than tab '{tab['id']}'.",
                            comps, joint=jid, feature=slot['id']))
    return {'matched_slot': slot['id'], 'location': location}


def _edge_world(plate, edge_index):
    n = len(plate.outline)
    p0 = plate.outline[edge_index % n]
    p1 = plate.outline[(edge_index + 1) % n]
    return plate.frame.to_world([p0[0], p0[1], 0]), plate.frame.to_world([p1[0], p1[1], 0])


def _eval_edge_butt(design, a, b, joint, tol, issues):
    jid, comps = joint['id'], [a.id, b.id]
    if joint['a_edge'] >= len(a.outline):
        issues.append(issue('EDGE_INVALID', 'error', 'joint', f"'{a.id}' has no edge {joint['a_edge']}.",
                            comps, joint=jid))
        return {'location': None}
    w0, w1 = _edge_world(a, joint['a_edge'])
    location = _r([(w0[i] + w1[i]) / 2 for i in range(3)])
    if abs(G.v_dot(a.frame.normal, b.frame.normal)) > tol['perpendicular']:
        issues.append(issue('ORIENTATION_MISMATCH', 'error', 'joint',
                            f"Edge butt joint needs '{a.id}' square to '{b.id}', but the boards are not perpendicular.",
                            comps, joint=jid, location=location))
        return {'location': location}
    l0, l1 = b.frame.to_local(w0), b.frame.to_local(w1)
    if abs(l0[2] - l1[2]) > tol['contact']:
        issues.append(issue('EDGE_NOT_FLUSH', 'error', 'joint',
                            f"Edge {joint['a_edge']} of '{a.id}' is tilted against the face of '{b.id}' "
                            f"({abs(l0[2] - l1[2]):.2f} mm out of plane).", comps, joint=jid, location=location))
        return {'location': location}
    _p, _d, n2, _L = edge_frame(a.outline, joint['a_edge'])
    out_w = a.frame.dir_to_world([n2[0], n2[1], 0])
    zmid = (l0[2] + l1[2]) / 2.0
    if abs(zmid) > 1e-6 and (G.v_dot(out_w, b.frame.normal) > 0) == (zmid > 0):
        issues.append(issue('EDGE_FACES_AWAY', 'error', 'joint',
                            f"Edge {joint['a_edge']} of '{a.id}' faces away from '{b.id}'.", comps,
                            joint=jid, location=location))
        return {'location': location}
    gap = abs(zmid) - b.t / 2.0
    move = G.v_scale(out_w, gap)
    if gap > tol['contact']:
        issues.append(issue('UNINTENDED_GAP', 'error', 'joint',
                            f"Edge {joint['a_edge']} of '{a.id}' is {gap:.2f} mm away from the face of '{b.id}'.",
                            comps, joint=jid, location=location, gap=_r(gap),
                            suggestion={'action': 'translate', 'component': a.id, 'delta': _r(move, 3)}))
    elif gap < -tol['contact']:
        issues.append(issue('PENETRATION', 'error', 'joint',
                            f"Edge {joint['a_edge']} of '{a.id}' penetrates {-gap:.2f} mm into '{b.id}'.",
                            comps, joint=jid, location=location, overlap=_r(-gap),
                            suggestion={'action': 'translate', 'component': a.id, 'delta': _r(move, 3)}))
    # Contact length on receiver material
    L = math.dist(l0[:2], l1[:2])
    steps = max(2, int(L / tol['sample_step']))
    hits = 0
    for k in range(steps + 1):
        s = k / steps
        p = [l0[0] + (l1[0] - l0[0]) * s, l0[1] + (l1[1] - l0[1]) * s]
        if b.is_material(p, 0.0):
            hits += 1
    contact = L * hits / (steps + 1)
    if contact < min(tol['min_contact_length'], L * 0.5):
        issues.append(issue('NOT_IN_CONTACT', 'error', 'joint',
                            f"Edge {joint['a_edge']} of '{a.id}' only touches {contact:.1f} mm of '{b.id}' material.",
                            comps, joint=jid, location=location, contact_length=_r(contact)))
    return {'location': location, 'contact_length': _r(contact)}


def _eval_edge_mitre(design, a, b, joint, tol, issues):
    jid, comps = joint['id'], [a.id, b.id]
    for p, e in ((a, joint['a_edge']), (b, joint['b_edge'])):
        if e >= len(p.outline):
            issues.append(issue('EDGE_INVALID', 'error', 'joint', f"'{p.id}' has no edge {e}.", comps, joint=jid))
            return {'location': None}
    a0, a1 = _edge_world(a, joint['a_edge'])
    b0, b1 = _edge_world(b, joint['b_edge'])
    location = _r([(a0[i] + a1[i]) / 2 for i in range(3)])
    d_same = max(math.dist(a0, b0), math.dist(a1, b1))
    d_swap = max(math.dist(a0, b1), math.dist(a1, b0))
    err = min(d_same, d_swap)
    if err > tol['contact'] * 2:
        pairs = ((a0, b0), (a1, b1)) if d_same <= d_swap else ((a0, b1), (a1, b0))
        delta = [sum(q[i] - p[i] for p, q in pairs) / 2.0 for i in range(3)]
        issues.append(issue('EDGES_NOT_COINCIDENT', 'error', 'joint',
                            f"Edge {joint['a_edge']} of '{a.id}' and edge {joint['b_edge']} of '{b.id}' are "
                            f"{err:.2f} mm apart; a corner joint needs coincident edges.", comps, joint=jid,
                            location=location, gap=_r(err),
                            suggestion={'action': 'translate', 'component': a.id, 'delta': _r(delta, 3)}))
    elif abs(G.v_dot(a.frame.normal, b.frame.normal)) > tol['parallel']:
        issues.append(issue('COPLANAR_EDGE_JOINT', 'warning', 'joint',
                            f"'{a.id}' and '{b.id}' meet edge-to-edge in the same plane; this joint has no "
                            f"mechanical strength without a backing plate.", comps, joint=jid))
    return {'location': location}


def _eval_face_lap(design, a, b, joint, tol, issues):
    jid, comps = joint['id'], [a.id, b.id]
    na, nb = a.frame.normal, b.frame.normal
    location = _r(a.world_centre())
    if abs(G.v_dot(na, nb)) < tol['parallel']:
        issues.append(issue('ORIENTATION_MISMATCH', 'error', 'joint',
                            f"Face lap joint needs '{a.id}' parallel to '{b.id}'.", comps, joint=jid))
        return {'location': location}
    sep = G.v_dot(G.v_sub(b.frame.p, a.frame.p), na)
    gap = abs(sep) - (a.t + b.t) / 2.0
    move = G.v_scale(na, gap if sep > 0 else -gap)
    if gap > tol['contact']:
        issues.append(issue('UNINTENDED_GAP', 'error', 'joint',
                            f"'{a.id}' and '{b.id}' are {gap:.2f} mm apart; laminated faces must touch.",
                            comps, joint=jid, gap=_r(gap),
                            suggestion={'action': 'translate', 'component': a.id, 'delta': _r(move, 3)}))
    elif gap < -tol['contact']:
        issues.append(issue('PENETRATION', 'error', 'joint',
                            f"'{a.id}' and '{b.id}' overlap {-gap:.2f} mm through their thickness.",
                            comps, joint=jid, overlap=_r(-gap),
                            suggestion={'action': 'translate', 'component': a.id, 'delta': _r(move, 3)}))
    area, centroid = _projected_overlap(a, b)
    if centroid:
        location = _r(centroid)
    if area < tol['min_lap_area']:
        issues.append(issue('NOT_IN_CONTACT', 'error', 'joint',
                            f"'{a.id}' and '{b.id}' share only {area:.1f} mm² of face (minimum {tol['min_lap_area']}).",
                            comps, joint=jid, contact_area=_r(area, 1)))
    return {'location': location, 'contact_area': _r(area, 1)}


def _grid(plate, max_points=6000):
    x0, y0, x1, y1 = plate.bbox2d
    step = max(0.5, math.sqrt(max((x1 - x0) * (y1 - y0), 1.0) / max_points))
    nx, ny = int((x1 - x0) / step) + 1, int((y1 - y0) / step) + 1
    for i in range(nx):
        for j in range(ny):
            yield [x0 + (i + 0.5) * step, y0 + (j + 0.5) * step], step


def _projected_overlap(a, b):
    area, acc, cnt = 0.0, [0.0, 0.0, 0.0], 0
    for p, step in _grid(a):
        if not a.is_material(p, 0.0):
            continue
        w = a.frame.to_world(p)
        q = b.frame.to_local(w)
        if b.is_material(q[:2], 0.0):
            area += step * step
            acc = G.v_add(acc, w)
            cnt += 1
    return area, (G.v_scale(acc, 1.0 / cnt) if cnt else None)


# ---------------------------------------------------------------------------
# 3. Assembly-level interference
# ---------------------------------------------------------------------------

def _aabb_overlap(a, b, pad=0.0):
    (alo, ahi), (blo, bhi) = a.world_aabb(), b.world_aabb()
    return all(alo[i] - pad < bhi[i] and blo[i] - pad < ahi[i] for i in range(3))


def _line_range_2d(p, u, bb):
    """Parameter interval where p + s*u lies within 2D bbox, or None."""
    lo, hi = -1e9, 1e9
    for k in range(2):
        mn, mx = bb[k], bb[k + 2]
        if abs(u[k]) < 1e-12:
            if p[k] < mn or p[k] > mx:
                return None
            continue
        s1, s2 = (mn - p[k]) / u[k], (mx - p[k]) / u[k]
        lo, hi = max(lo, min(s1, s2)), min(hi, max(s1, s2))
    return (lo, hi) if hi > lo else None


def plate_interference(a, b, tol=TOL):
    """Return a list of {'kind', 'length'|'area', 'location'} regions where two plates share material."""
    if not _aabb_overlap(a, b, -0.01):
        return []
    na, nb = a.frame.normal, b.frame.normal
    cr = G.v_cross(na, nb)
    if G.v_len(cr) < 1e-4:
        sep = abs(G.v_dot(G.v_sub(b.frame.p, a.frame.p), na))
        if sep >= (a.t + b.t) / 2.0 - tol['contact']:
            return []
        area, centroid = _projected_overlap(a, b)
        if area < 1.0:
            return []
        return [{'kind': 'parallel_overlap', 'area': _r(area, 1), 'location': _r(centroid)}]

    # Line of intersection of the two mid-planes
    u = G.v_norm(cr)
    da, db = G.v_dot(na, a.frame.p), G.v_dot(nb, b.frame.p)
    # point = (da*(nb x u) + db*(u x na)) / (u . (na x nb))
    denom = G.v_dot(u, cr)
    p0 = G.v_scale(G.v_add(G.v_scale(G.v_cross(nb, u), da), G.v_scale(G.v_cross(u, na), db)), 1.0 / denom)
    pa, ua = a.frame.to_local(p0), a.frame.dir_to_local(u)
    pb, ub = b.frame.to_local(p0), b.frame.dir_to_local(u)
    ra, rb = _line_range_2d(pa, ua, a.bbox2d), _line_range_2d(pb, ub, b.bbox2d)
    if not ra or not rb:
        return []
    lo, hi = max(ra[0], rb[0]), min(ra[1], rb[1])
    if hi <= lo:
        return []
    step = tol['sample_step']
    runs, cur = [], None
    s = lo
    while s <= hi:
        qa = [pa[0] + ua[0] * s, pa[1] + ua[1] * s]
        qb = [pb[0] + ub[0] * s, pb[1] + ub[1] * s]
        if a.is_material(qa, tol['contact']) and b.is_material(qb, tol['contact']):
            if cur and s - cur[1] <= step * 1.5:
                cur[1] = s
            else:
                cur = [s, s]
                runs.append(cur)
        s += step
    # One entry per contiguous overlap region, so each region keeps a stable identity
    return [{'kind': 'crossing', 'length': _r(e - b0 + step),
             'location': _r(G.v_add(p0, G.v_scale(u, (b0 + e) / 2.0)))} for b0, e in runs]


def find_collisions(design, plates, only=None, tol=TOL):
    ids = list(plates)
    out = []
    joined_pairs = {frozenset((j['a'], j['b'])) for j in design['joints'] if j.get('status') == 'joined'}
    for i in range(len(ids)):
        for k in range(i + 1, len(ids)):
            a, b = plates[ids[i]], plates[ids[k]]
            if only and a.id not in only and b.id not in only:
                continue
            for hit in plate_interference(a, b, tol):
                joined = frozenset((a.id, b.id)) in joined_pairs
                size = f"{hit['length']} mm" if 'length' in hit else f"{hit['area']} mm²"
                out.append(issue('COLLISION', 'error', 'assembly',
                                 f"Solid material of '{a.id}' and '{b.id}' occupies the same space ({size}) "
                                 f"near [{', '.join(f'{v:.1f}' for v in hit['location'])}]"
                                 + (" although they are joined — another tab/slot or a placement error." if joined
                                    else ". Add a joint (slot) or move one of them."),
                                 [a.id, b.id], location=hit['location'], interference=hit,
                                 between_joined_components=joined))
    return out


# ---------------------------------------------------------------------------
# Design-level validation
# ---------------------------------------------------------------------------

def _signature(design, c):
    r = lambda v: round(v, 2)
    return (tuple((r(x), r(y)) for x, y in Plate(design, c).cut),
            tuple(sorted((f['kind'], r(f['center'][0]), r(f['center'][1])) for f in c.get('features', []))),
            r(thickness_of(design, c)),
            tuple(r(v) for v in c['placement']['position']),
            tuple(r(v % 360) for v in c['placement']['rotation']))


def validate_design(design, tol=TOL):
    issues = []
    comps = design['components']

    seen = {}
    for c in comps:
        if c['id'] in seen:
            issues.append(issue('DUPLICATE_COMPONENT_ID', 'error', 'design',
                                f"Component id '{c['id']}' is used more than once.", [c['id']]))
        seen[c['id']] = c
    sigs = {}
    for c in comps:
        try:
            s = _signature(design, c)
        except Exception:  # degenerate geometry is reported by validate_component
            continue
        if s in sigs:
            issues.append(issue('DUPLICATE_COMPONENT', 'error', 'design',
                                f"'{c['id']}' is an exact duplicate of '{sigs[s]}' (same profile, same placement). "
                                f"Remove one or move it.", [c['id'], sigs[s]], duplicate_of=sigs[s]))
        else:
            sigs[s] = c['id']

    broken_geometry = set()
    for c in comps:
        ci = validate_component(design, c, tol)
        if any(i['code'] in ('DEGENERATE_OUTLINE', 'OUTLINE_SELF_INTERSECTION') for i in ci):
            broken_geometry.add(c['id'])
        issues.extend(ci)

    plates = {c['id']: Plate(design, c) for c in comps if c['id'] not in broken_geometry}

    # Joints
    keys = {}
    used_slots, used_tabs = set(), set()
    joined_adj = {c['id']: set() for c in comps}
    joint_results = {}
    for j in design['joints']:
        key = (j['type'], j['a'], j['b'], j.get('tab'), j.get('a_edge'), j.get('b_edge'))
        rkey = (j['type'], j['b'], j['a'], j.get('tab'), j.get('b_edge'), j.get('a_edge'))
        if key in keys or (j['type'] in ('face_lap', 'edge_mitre') and rkey in keys):
            issues.append(issue('DUPLICATE_JOINT', 'error', 'design',
                                f"Joint '{j['id']}' duplicates joint '{keys.get(key) or keys.get(rkey)}'.",
                                [j['a'], j['b']], joint=j['id']))
            continue
        keys[key] = j['id']
        if j.get('status') != 'joined':
            continue
        res = evaluate_joint(design, plates, j, tol)
        joint_results[j['id']] = res
        errs = [i for i in res['issues'] if i['severity'] == 'error']
        if errs:
            issues.append(issue('JOINT_BROKEN', 'error', 'joint',
                                f"Joined connection '{j['id']}' is no longer valid: {errs[0]['message']}",
                                [j['a'], j['b']], joint=j['id'], causes=errs,
                                suggestion=errs[0].get('suggestion')))
        issues.extend(i for i in res['issues'] if i['severity'] == 'warning')
        if j['type'] == 'tab_slot':
            used_tabs.add((j['a'], j['tab']))
            if res.get('matched_slot'):
                used_slots.add((j['b'], res['matched_slot']))
        if j['a'] in joined_adj and j['b'] in joined_adj:
            joined_adj[j['a']].add(j['b'])
            joined_adj[j['b']].add(j['a'])

    for c in comps:
        for f in c.get('features', []):
            if f['kind'] == 'slot' and (c['id'], f['id']) not in used_slots:
                issues.append(issue('UNUSED_SLOT', 'warning', 'design',
                                    f"Slot '{f['id']}' on '{c['id']}' receives no joint. It is left as cut — "
                                    f"if it is intentional, change its kind to 'opening'; otherwise join a tab to it "
                                    f"or delete it.", [c['id']], feature=f['id']))
        for t in c.get('tabs', []):
            if (c['id'], t['id']) not in used_tabs:
                issues.append(issue('UNJOINED_TAB', 'warning', 'design',
                                    f"Tab '{t['id']}' on '{c['id']}' is not joined to anything.",
                                    [c['id']], feature=t['id']))

    # Connectivity of the assembly
    if len(comps) > 1:
        groups, seen_ids = [], set()
        for cid in joined_adj:
            if cid in seen_ids:
                continue
            stack, grp = [cid], set()
            while stack:
                x = stack.pop()
                if x in grp:
                    continue
                grp.add(x)
                stack.extend(joined_adj[x] - grp)
            seen_ids |= grp
            groups.append(grp)
        groups.sort(key=len, reverse=True)
        for grp in groups[1:]:
            for cid in sorted(grp):
                issues.append(issue('FLOATING_COMPONENT', 'warning', 'assembly',
                                    f"'{cid}' is not joined to the main assembly"
                                    + (f" (it is only connected to {', '.join(sorted(grp - {cid}))})." if len(grp) > 1 else "."),
                                    [cid]))

    issues.extend(find_collisions(design, plates, tol=tol))

    errors = sum(1 for i in issues if i['severity'] == 'error')
    warnings = sum(1 for i in issues if i['severity'] == 'warning')
    joined = sum(1 for j in design['joints'] if j.get('status') == 'joined')
    return {
        'valid': errors == 0,
        'complete': errors == 0 and not any(i['code'] in ('FLOATING_COMPONENT', 'UNJOINED_TAB') for i in issues),
        'summary': {'errors': errors, 'warnings': warnings, 'components': len(comps),
                    'joints': len(design['joints']), 'joined': joined},
        'issues': issues,
    }


def component_states(design, report):
    """Map component id -> 'error' | 'joined' | 'cut' for renderers."""
    err = {c for i in report['issues'] if i['severity'] == 'error' for c in i.get('components', [])}
    joined = {x for j in design['joints'] if j.get('status') == 'joined' for x in (j['a'], j['b'])}
    return {c['id']: ('error' if c['id'] in err else 'joined' if c['id'] in joined else 'cut')
            for c in design['components']}
