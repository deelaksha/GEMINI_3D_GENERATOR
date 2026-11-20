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
import copy
import math

from . import geometry as G
from .model import (INTERLOCKING_JOINTS, Plate, build_plates, feature_polygon, tab_geometry, edge_frame,
                    find_component, material_of, thickness_of)

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

    if design.get('joinery', 'interlocking') == 'interlocking' and joint['type'] not in INTERLOCKING_JOINTS:
        why = ('needs cabinet hardware' if joint['type'] == 'hinge' else 'only holds with glue')
        issues.append(issue('GLUE_JOINT_NOT_ALLOWED', 'error', 'joint',
                            f"'{jid}' is a {joint['type'].replace('_', ' ')} joint, which {why}. This design "
                            f"is glue-free (interlocking): connect '{a.id}' and '{b.id}' with a tab through a slot instead.",
                            [a.id, b.id], joint=jid))
        return {'ok': False, 'issues': issues, 'matched_slot': None, 'location': None}
    fn = {'tab_slot': _eval_tab_slot, 'edge_butt': _eval_edge_butt,
          'edge_mitre': _eval_edge_mitre, 'face_lap': _eval_face_lap, 'hinge': _eval_hinge}[joint['type']]
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
        if abs(z_root) <= tab['depth'] + b.t:
            # The shoulder has sunk through the receiver: a penetration with an exact correction
            need = (-1.0 if dot > 0 else 1.0) * b.t / 2.0
            move = G.v_scale(nb, need - z_root)
            issues.append(issue('PENETRATION', 'error', 'joint',
                                f"'{a.id}' has sunk {abs(z_root) + b.t / 2.0:.2f} mm through '{b.id}' at tab "
                                f"'{tab['id']}'; the shoulder must sit on the near face.", comps, joint=jid,
                                location=location, overlap=_r(abs(z_root) + b.t / 2.0),
                                suggestion={'action': 'translate', 'component': a.id, 'delta': _r(move, 3)}))
            return {'matched_slot': None, 'location': location}
        issues.append(issue('TAB_POINTS_AWAY', 'error', 'joint',
                            f"Tab '{tab['id']}' on '{a.id}' points away from '{b.id}'.", comps,
                            joint=jid, location=location))
        return {'matched_slot': None, 'location': location}

    # Shoulder gap sampled at both ends of the tab root and its centre (receiver-local z). A single
    # centre sample misses tilt: a board rotated by a few degrees lifts one end and sinks the other.
    side = 1.0 if z_root > 0 else -1.0 if z_root < 0 else (-1.0 if dot > 0 else 1.0)
    root_pts = [(tg['root'][0] + tg['dir'][0] * k * tab['width'] / 2.0, tg['root'][1] + tg['dir'][1] * k * tab['width'] / 2.0)
                for k in (-1, 0, 1)]
    gaps = [side * b.frame.to_local(a.frame.to_world([x, y, 0]))[2] - b.t / 2.0 for x, y in root_pts]
    gmax, gmin = max(gaps), min(gaps)
    spread = gmax - gmin
    measured = {'gaps': [round(g, 4) for g in gaps]}
    if gmax > tol['contact'] or gmin < -tol['contact']:
        extra = {}
        if spread <= 2 * tol['contact']:
            # A pure offset (or a tilt small enough that one move brings both ends inside tolerance):
            # moving A along the insertion direction by the mid value closes it.
            extra['suggestion'] = {'action': 'translate', 'component': a.id,
                                   'delta': _r(G.v_scale(ins_w, (gmax + gmin) / 2.0), 3)}
            tilt_txt = ''
        else:
            # A tilt: no translation brings both ends within tolerance; which board to rotate is a design choice.
            extra['tilt_deg'] = _r(math.degrees(math.atan2(spread, tab['width'])), 2)
            tilt_txt = (f" '{a.id}' is tilted {extra['tilt_deg']:.2f}° along tab '{tab['id']}' "
                        f"({gmin:+.2f} mm at one end, {gmax:+.2f} mm at the other) — rotate it square to '{b.id}'.")
        if gmax > tol['contact']:
            issues.append(issue('UNINTENDED_GAP', 'error', 'joint',
                                f"'{a.id}' stands {gmax:.2f} mm off the face of '{b.id}' at tab '{tab['id']}'. "
                                f"The shoulder must sit on the board." + tilt_txt, comps, joint=jid, location=location,
                                gap=_r(gmax), gaps=measured['gaps'], **extra))
        if gmin < -tol['contact']:
            issues.append(issue('PENETRATION', 'error', 'joint',
                                f"The body of '{a.id}' sinks {-gmin:.2f} mm into '{b.id}' beyond the tab shoulder."
                                + tilt_txt, comps, joint=jid, location=location, overlap=_r(-gmin),
                                gaps=measured['gaps'], **extra))

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
    # = the region the tab solid sweeps while crossing the receiver's thickness (receiver-local XY). For a
    # square tab this is exactly width x thickness; a lean or yaw within the orientation gate widens it,
    # and the required slot grows accordingly (no new tolerance: clearance is added as before).
    dir_b = b.frame.dir_to_local(a.frame.dir_to_world([tg['dir'][0], tg['dir'][1], 0]))
    angle = math.degrees(math.atan2(dir_b[1], dir_b[0]))
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    ins_b = b.frame.dir_to_local(ins_w)
    swept = []
    for kd in (-0.5, 0.5):
        for kn in (-0.5, 0.5):
            start = b.frame.to_local(a.frame.to_world([tg['root'][0] + tg['dir'][0] * kd * tab['width'],
                                                       tg['root'][1] + tg['dir'][1] * kd * tab['width'], kn * a.t]))
            for zf in (-b.t / 2.0, b.t / 2.0):
                s_ = (zf - start[2]) / ins_b[2]
                swept.append((start[0] + ins_b[0] * s_, start[1] + ins_b[1] * s_))
    us = [x * ca + y * sa for x, y in swept]
    vs = [-x * sa + y * ca for x, y in swept]
    len_eff, wid_eff = max(us) - min(us), max(vs) - min(vs)
    cu, cv = (max(us) + min(us)) / 2.0, (max(vs) + min(vs)) / 2.0
    centre = [cu * ca - cv * sa, cu * sa + cv * ca]
    clearance = design['material']['clearance']
    exp_len, exp_wid = len_eff + clearance, wid_eff + clearance
    footprint = G.rect_polygon(centre, len_eff, wid_eff, angle)

    if not all(G.point_in_polygon(p, b.cut) for p in footprint):
        issues.append(issue('TAB_OUTSIDE_RECEIVER', 'error', 'joint',
                            f"Tab '{tab['id']}' lands outside the outline of '{b.id}' — there is no material to "
                            f"receive it.", comps, joint=jid, location=location))
        return dict(measured, matched_slot=None, location=location)

    for f, poly in b.feature_polys:
        if f['kind'] == 'slot' or not G.polygons_overlap(footprint, poly):
            continue
        code = 'TAB_IN_OPENING' if f['kind'] == 'opening' else 'TAB_IN_HOLE'
        issues.append(issue(code, 'error', 'joint',
                            f"Tab '{tab['id']}' lands in {f['kind']} '{f['id']}' of '{b.id}'. "
                            f"That {f['kind']} is intentional and is preserved; the joint must be moved.",
                            comps, joint=jid, feature=f['id'], location=location))
        return dict(measured, matched_slot=None, location=location)

    # Locate the receiving slot
    slot = None
    if joint.get('slot'):
        slot = next((f for f in b.features if f['id'] == joint['slot']), None)
        if slot is None or slot['kind'] != 'slot':
            issues.append(issue('SLOT_NOT_FOUND', 'error', 'joint',
                                f"'{b.id}' has no slot '{joint['slot']}'.", comps, joint=jid))
            return dict(measured, matched_slot=None, location=location)
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
        return dict(measured, matched_slot=None, location=location)

    users = slot_users(design, b.id, slot['id'], exclude_joint=jid)
    if users:
        issues.append(issue('SLOT_ALREADY_USED', 'error', 'joint',
                            f"Slot '{slot['id']}' on '{b.id}' already receives joint '{users[0]}'.",
                            comps, joint=jid, feature=slot['id']))
        return dict(measured, matched_slot=slot['id'], location=location)

    off = math.hypot(slot['center'][0] - centre[0], slot['center'][1] - centre[1])
    if off > tol['slot_position']:
        delta_local = [slot['center'][0] - centre[0], slot['center'][1] - centre[1], 0]
        issues.append(issue('SLOT_MISALIGNED', 'error', 'joint',
                            f"Slot '{slot['id']}' on '{b.id}' is {off:.2f} mm away from where tab '{tab['id']}' "
                            f"arrives. Either move '{a.id}' or move the slot.", comps, joint=jid,
                            feature=slot['id'], location=location, offset=_r(off),
                            suggestion={'action': 'translate', 'component': a.id,
                                        'delta': _r(b.frame.dir_to_world(delta_local), 3)}))
        return dict(measured, matched_slot=slot['id'], location=location)

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
        return dict(measured, matched_slot=slot['id'], location=location)

    resize = None
    if s_len < exp_len - tol['slot_fit'] or s_wid < exp_wid - tol['slot_fit']:
        code = 'SLOT_TOO_SMALL'
        msg = (f"Slot '{slot['id']}' on '{b.id}' is {s_len:.2f} x {s_wid:.2f} mm; tab '{tab['id']}' needs "
               f"{exp_len:.2f} x {exp_wid:.2f} mm (swept tab + {clearance} mm clearance).")
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
    return dict(measured, matched_slot=slot['id'], location=location)


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
    # Contact length on receiver material, measured in B-local XY along A's mid-plane edge AND along both
    # of A's faces (offset +/- tA/2 along A's normal): the whole thickness of A must rest on B, not just its
    # mid-line (an edge hanging over B's end or straddling a slot/opening is otherwise missed).
    L = math.dist(l0[:2], l1[:2])
    contact_by_line = []
    # Face lines are inset by the contact tolerance: a face flush with b's end lies exactly on b's outline,
    # where point-in-polygon is undefined (a flush L-corner is fully supported, not overhanging).
    face = a.t / 2.0 - tol['contact']
    for off in (-face, 0.0, face):
        q0 = b.frame.to_local(G.v_add(w0, G.v_scale(a.frame.normal, off)))
        q1 = b.frame.to_local(G.v_add(w1, G.v_scale(a.frame.normal, off)))
        # Exact length of the line on b's material (outline minus cut-outs), r in [0, 1] along the edge
        ivs = _material_intervals(b, q0, [q1[0] - q0[0], q1[1] - q0[1]], 0.0)
        contact_by_line.append(_r(L * sum(max(0.0, min(r1, 1.0) - max(r0, 0.0)) for r0, r1 in ivs)))
    contact = contact_by_line[1]
    need = min(tol['min_contact_length'], L * 0.5)
    if max(contact_by_line) < need:
        issues.append(issue('NOT_IN_CONTACT', 'error', 'joint',
                            f"Edge {joint['a_edge']} of '{a.id}' only touches {max(contact_by_line):.1f} mm of '{b.id}' "
                            f"material.", comps, joint=jid, location=location, contact_length=_r(contact),
                            contact_by_line=contact_by_line))
    elif min(contact_by_line) < need:
        issues.append(issue('EDGE_PARTIALLY_SUPPORTED', 'warning', 'joint',
                            f"Only part of the {a.t:g} mm thickness of edge {joint['a_edge']} of '{a.id}' rests on "
                            f"'{b.id}' (contact along -t/2, mid, +t/2: "
                            f"{', '.join(f'{c:.1f}' for c in contact_by_line)} mm) — it overhangs an edge, slot or opening.",
                            comps, joint=jid, location=location, contact_by_line=contact_by_line))
    return {'location': location, 'contact_length': _r(contact), 'contact_by_line': contact_by_line}


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
        # Edge-to-edge in one plane: dowels (or a long-grain glue line in solid wood) make a real joint;
        # a plain glued edge of sheet material does not.
        solid = all(material_of(design, p.comp)['type'] == 'solid_wood' for p in (a, b))
        if not joint.get('fasteners') and not solid:
            issues.append(issue('COPLANAR_EDGE_JOINT', 'warning', 'joint',
                                f"'{a.id}' and '{b.id}' meet edge-to-edge in the same plane; this joint has no "
                                f"mechanical strength without dowels or a backing plate.", comps, joint=jid))
        return {'location': location, 'relation': 'edge_to_edge'}
    else:
        # Thickness check (world, in the plane perpendicular to the shared edge). The data model has square
        # edges only, so with coincident mid-plane edges the inner halves overlap. Along A the overlap is
        # (tB/2 + tA/2*cos(phi)) / sin(phi), phi = angle between the boards' material directions.
        _p, _d, nA2, _L = edge_frame(a.outline, joint['a_edge'])
        _p, _d, nB2, _L = edge_frame(b.outline, joint['b_edge'])
        uA = G.v_scale(a.frame.dir_to_world([nA2[0], nA2[1], 0]), -1.0)
        uB = G.v_scale(b.frame.dir_to_world([nB2[0], nB2[1], 0]), -1.0)
        phi = math.acos(max(-1.0, min(1.0, G.v_dot(uA, uB))))
        if joint.get('bevel') and math.sin(phi) > 1e-6:
            # Both edges cut on the bisector plane through the shared mid-plane edge: the boards then meet on
            # that plane with no overlap. Each board's face on the outside of the corner runs past the
            # mid-plane edge by (t/2)*cot(phi/2) (the long point) — the cut list sizes blanks from that.
            deg = math.degrees(phi)
            if abs(a.t - b.t) > tol['contact']:
                issues.append(issue('MITRE_THICKNESS_MISMATCH', 'warning', 'joint',
                                    f"Mitre '{jid}' joins a {a.t:g} mm and a {b.t:g} mm board; a bisecting bevel "
                                    f"leaves the outer faces {abs(a.t - b.t) / 2:.1f} mm out of line.", comps, joint=jid))
            bevel = {'corner_angle_deg': _r(deg, 2), 'bevel_deg': _r(deg / 2, 2), 'blade_tilt_deg': _r(90 - deg / 2, 2),
                     'long_point': {a.id: _r(a.t / 2 / math.tan(phi / 2), 3), b.id: _r(b.t / 2 / math.tan(phi / 2), 3)}}
            return {'location': location, 'relation': 'mitre', 'bevel': bevel}
        if math.sin(phi) > 1e-6:
            over_a = (b.t / 2.0 + a.t / 2.0 * math.cos(phi)) / math.sin(phi)
            over_b = (a.t / 2.0 + b.t / 2.0 * math.cos(phi)) / math.sin(phi)
            overlap = max(over_a, over_b)
            if overlap > tol['contact']:
                deg = math.degrees(phi)
                issues.append(issue('PENETRATION', 'error', 'joint',
                                    f"Square-cut edges of '{a.id}' and '{b.id}' meeting at {deg:.1f}° overlap "
                                    f"{overlap:.2f} mm through their thickness. A true mitre needs both edges "
                                    f"bevelled to {deg / 2:.1f}°, which flat cutting cannot produce — shorten one "
                                    f"board or use a tab and slot.", comps, joint=jid, location=location,
                                    overlap=_r(overlap), overlap_a=_r(over_a), overlap_b=_r(over_b),
                                    angle_deg=_r(deg, 2), bevel_deg=_r(deg / 2, 2)))
    return {'location': location}


HINGE = {'cup_diameter': 35.0, 'cup_depth': 13.0, 'cup_centre_from_edge': 22.5, 'end_distance': 100.0,
         'min_remaining': 3.0, 'default_gap': 2.0}


def hinge_count(length):
    """Hinges per door by door height (hardware makers' charts for 18-19 mm doors)."""
    return 2 if length <= 900 else 3 if length <= 1600 else 4 if length <= 2000 else 5


def _eval_hinge(design, a, b, joint, tol, issues):
    """Overlay door (a) hung on carcass board (b) by concealed cup hinges along door edge a_edge."""
    jid, comps = joint['id'], [a.id, b.id]
    if joint['a_edge'] >= len(a.outline):
        issues.append(issue('EDGE_INVALID', 'error', 'joint', f"'{a.id}' has no edge {joint['a_edge']}.", comps, joint=jid))
        return {'location': None}
    w0, w1 = _edge_world(a, joint['a_edge'])
    location = _r([(w0[i] + w1[i]) / 2 for i in range(3)])
    if abs(G.v_dot(a.frame.normal, b.frame.normal)) > tol['perpendicular']:
        issues.append(issue('ORIENTATION_MISMATCH', 'error', 'joint',
                            f"Door '{a.id}' must be square to carcass board '{b.id}' to hang on it.", comps,
                            joint=jid, location=location))
        return {'location': location}
    hinge_dir = G.v_norm(G.v_sub(w1, w0))
    if abs(G.v_dot(hinge_dir, b.frame.normal)) > tol['perpendicular']:
        issues.append(issue('HINGE_EDGE_MISALIGNED', 'error', 'joint',
                            f"Hinge edge {joint['a_edge']} of '{a.id}' does not run along '{b.id}'.", comps,
                            joint=jid, location=location))
        return {'location': location}
    # The carcass edge facing the door: the outline edge of b lying in a plane parallel to the door, nearest it.
    best = None
    for i in range(len(b.outline)):
        e0, e1 = _edge_world(b, i)
        z0, z1 = a.frame.to_local(e0)[2], a.frame.to_local(e1)[2]
        if abs(z0 - z1) <= tol['contact'] and (best is None or abs(z0 + z1) < abs(best[1])):
            best = (i, (z0 + z1) / 2.0)
    if best is None:
        issues.append(issue('NOT_IN_CONTACT', 'error', 'joint',
                            f"No edge of '{b.id}' faces door '{a.id}'.", comps, joint=jid, location=location))
        return {'location': location}
    b_edge, zc = best
    bc = b.frame.to_local(a.frame.to_world([0, 0, 0]))  # where the door's mid-plane sits relative to b
    pb, _d, nb2, _L = edge_frame(b.outline, b_edge)
    if nb2[0] * (bc[0] - pb[0]) + nb2[1] * (bc[1] - pb[1]) < 0:  # door must be outside b's front edge
        issues.append(issue('DOOR_FACES_AWAY', 'error', 'joint',
                            f"Door '{a.id}' is behind the edge of '{b.id}', not in front of it.", comps,
                            joint=jid, location=location))
        return {'location': location}
    gap = abs(zc) - a.t / 2.0
    allowed = joint.get('gap', HINGE['default_gap'])
    move = G.v_scale(a.frame.normal, -gap if zc > 0 else gap)
    if gap < -tol['contact']:
        issues.append(issue('PENETRATION', 'error', 'joint',
                            f"Door '{a.id}' sinks {-gap:.2f} mm into the front edge of '{b.id}'.", comps,
                            joint=jid, location=location, overlap=_r(-gap),
                            suggestion={'action': 'translate', 'component': a.id, 'delta': _r(move, 3)}))
    elif gap > allowed + tol['contact']:
        issues.append(issue('UNINTENDED_GAP', 'error', 'joint',
                            f"Door '{a.id}' stands {gap:.2f} mm off the front edge of '{b.id}' (hinge allows "
                            f"{allowed:g} mm).", comps, joint=jid, location=location, gap=_r(gap),
                            suggestion={'action': 'translate', 'component': a.id,
                                        'delta': _r(G.v_scale(move, (gap - allowed / 2.0) / gap), 3)}))
    # Overlay: how much of the carcass edge the door covers, measured in the door plane inward from its hinge
    # edge (b's faces are perpendicular to that direction). outer > 0 means the door overhangs b's outer face.
    _p, _d, na2, L = edge_frame(a.outline, joint['a_edge'])
    inward = a.frame.dir_to_world([-na2[0], -na2[1], 0])
    faces = [G.v_dot(G.v_sub(b.frame.to_world([0, 0, s * b.t / 2.0]), w0), inward) for s in (-1, 1)]
    outer, inner = min(faces), max(faces)
    overlay = inner - max(outer, 0.0)
    if overlay <= tol['contact']:
        issues.append(issue('DOOR_NOT_OVER_CARCASS', 'error', 'joint',
                            f"Door '{a.id}' does not overlap the edge of '{b.id}' (overlay {overlay:.1f} mm); an "
                            f"overlay hinge needs the door to cover the board edge.", comps, joint=jid, location=location))
    elif outer > tol['contact']:
        issues.append(issue('DOOR_OVERHANGS_CARCASS', 'warning', 'joint',
                            f"Door '{a.id}' overhangs the outer face of '{b.id}' by {outer:.1f} mm.", comps,
                            joint=jid, location=location))
    kind = 'full' if overlay >= b.t - 4.0 else 'half' if overlay >= b.t / 2.0 - 3.0 else 'partial'
    if a.t < HINGE['cup_depth'] + HINGE['min_remaining']:
        issues.append(issue('HINGE_CUP_TOO_DEEP', 'error', 'joint',
                            f"Door '{a.id}' is {a.t:g} mm thick; a {HINGE['cup_diameter']:g} mm hinge cup is "
                            f"{HINGE['cup_depth']:g} mm deep and needs at least "
                            f"{HINGE['cup_depth'] + HINGE['min_remaining']:g} mm.", comps, joint=jid))
    need = hinge_count(L)
    count = joint.get('count', need)
    if count < need:
        issues.append(issue('HINGE_COUNT_LOW', 'warning', 'joint',
                            f"Door '{a.id}' is {L:.0f} mm high and needs {need} hinges; {count} specified.",
                            comps, joint=jid))
    return {'location': location, 'relation': 'hinge', 'gap': _r(gap), 'overlay': _r(overlay),
            'overlay_kind': kind, 'hinge_count': count, 'carcass_edge': b_edge}


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


_INTERFERENCE_CACHE = {}


def plate_interference(a, b, tol=TOL):
    """Return a list of {'kind', 'length'|'area', 'location'} regions where two plates share material.

    Pure function of the two plates' geometry and the tolerances, so results are memoised per geometry
    pair: a join or edit changes one board, and every other pair is reused on the next validation."""
    if not _aabb_overlap(a, b, -0.01):
        return []
    key = (a.signature(), b.signature(), tol['contact'], tol['sample_step'])
    hit = _INTERFERENCE_CACHE.get(key)
    if hit is None:
        if len(_INTERFERENCE_CACHE) > 20000:
            _INTERFERENCE_CACHE.clear()
        hit = _INTERFERENCE_CACHE[key] = _plate_interference(a, b, tol)
    return copy.deepcopy(hit)


def _plate_interference(a, b, tol):
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
    pad = 2.0 * max(a.t, b.t) + 1.0
    ranges = []
    for pl in (a, b):
        x0, y0, x1, y1 = pl.bbox2d
        rr = _line_range_2d(pl.frame.to_local(p0), pl.frame.dir_to_local(u), (x0 - pad, y0 - pad, x1 + pad, y1 + pad))
        if not rr:
            return []
        ranges.append(rr)
    lo, hi = max(ranges[0][0], ranges[1][0]), min(ranges[0][1], ranges[1][1])
    if hi <= lo:
        return []
    # Solid-vs-solid test (not just mid-plane vs mid-plane): at every station s along the line, take the
    # cross-section of board P through its mid-plane and both faces (P-local) and intersect, in r, the part
    # that is P's material with the part that lies inside Q's thickness slab AND on Q's material (Q-local).
    # P's boundary is exact; Q's slab and outline are shrunk by the joining tolerance so touching faces,
    # tabs seated in slots and edges resting on faces are not collisions.
    step = tol['sample_step']
    hit_idx = set()
    for P, Q in ((a, b), (b, a)):
        vP = G.v_norm(G.v_cross(P.frame.normal, u))          # in P's plane, perpendicular to the line
        vp_loc, vq_loc = P.frame.dir_to_local(vP), Q.frame.dir_to_local(vP)
        n_st = int((hi - lo) / step) + 1
        for off in (-P.t / 2.0, 0.0, P.t / 2.0):
            base = G.v_add(p0, G.v_scale(P.frame.normal, off))
            # All sampling lines of this pass are parallel, so the stations whose line can touch a given
            # cut-out form one range: precompute it once instead of box-testing every cut-out per station.
            act_p = _station_features(P, base, u, vp_loc, lo, step, n_st)
            act_q = _station_features(Q, base, u, vq_loc, lo, step, n_st)
            for k in range(n_st):
                w = G.v_add(base, G.v_scale(u, lo + k * step))
                pq = Q.frame.to_local(w)
                ivs = _slab_interval(pq[2], vq_loc[2], Q.t / 2.0 - tol['contact'])   # cheapest test first
                if ivs:
                    ivs = _intersect(_material_intervals(P, P.frame.to_local(w), vp_loc, 0.0, act_p[k]), ivs)
                if ivs:
                    ivs = _intersect(ivs, _material_intervals(Q, pq, vq_loc, tol['contact'], act_q[k]))
                if any(r1 - r0 > 1e-6 for r0, r1 in ivs):
                    hit_idx.add(k)
    runs, cur = [], None
    for k in sorted(hit_idx):
        if cur and k - cur[1] <= 1:
            cur[1] = k
        else:
            cur = [k, k]
            runs.append(cur)
    # One entry per contiguous overlap region, so each region keeps a stable identity
    return [{'kind': 'crossing', 'length': _r((e - b0 + 1) * step),
             'location': _r(G.v_add(p0, G.v_scale(u, lo + (b0 + e) * step / 2.0)))} for b0, e in runs]


def _slab_interval(z0, vz, half):
    """r-interval where |z0 + vz*r| < half (receiver-local z)."""
    if half <= 0:
        return []
    if abs(vz) < 1e-12:
        return [(-1e9, 1e9)] if abs(z0) < half else []
    r0, r1 = (-half - z0) / vz, (half - z0) / vz
    return [(min(r0, r1), max(r0, r1))]


def _polygon_line_intervals(poly, p, v):
    """r-intervals where the 2D line p + v*r is inside polygon (even-odd)."""
    n = len(poly)
    return _edge_line_intervals([(poly[i], poly[(i + 1) % n]) for i in range(n)], p, v)


def _edge_line_intervals(edges, p, v):
    """Even-odd r-intervals from the polygon edges that the line can cross (edges it cannot cross add nothing)."""
    rs = []
    vv = v[0] * v[0] + v[1] * v[1]
    for q1, q2 in edges:
        # Half-open side rule (as in point-in-polygon): a vertex lying exactly on the line is counted on
        # one side only, so crossings always pair up even when stations hit vertices or collinear edges.
        d1 = v[0] * (q1[1] - p[1]) - v[1] * (q1[0] - p[0])
        d2 = v[0] * (q2[1] - p[1]) - v[1] * (q2[0] - p[0])
        if (d1 > 0) == (d2 > 0):
            continue
        t = d1 / (d1 - d2)
        x, y = q1[0] + (q2[0] - q1[0]) * t, q1[1] + (q2[1] - q1[1]) * t
        rs.append(((x - p[0]) * v[0] + (y - p[1]) * v[1]) / vv)
    rs.sort()
    return [(rs[i], rs[i + 1]) for i in range(0, len(rs) - 1, 2)]


def _station_features(plate, base_w, u_w, v_loc, lo, step, n):
    """Per station k (line through base + u*(lo + k*step) along v, plate-local), the cut-out polygons whose
    bounding box that line can cross; None where every station must test all cut-outs (point-crossing case)."""
    if math.hypot(v_loc[0], v_loc[1]) < 1e-9:
        return [None] * n
    p0 = plate.frame.to_local(base_w)
    uu = plate.frame.dir_to_local(u_w)
    kk = v_loc[0] * uu[1] - v_loc[1] * uu[0]          # d(point, s) = c(point) - s * kk
    if abs(kk) < 1e-12:
        return [None] * n

    def stations(points):
        cs = [v_loc[0] * (y - p0[1]) - v_loc[1] * (x - p0[0]) for x, y in points]
        s0, s1 = sorted((min(cs) / kk, max(cs) / kk))
        return (max(0, int(math.floor((s0 - lo) / step)) - 1), min(n - 1, int(math.ceil((s1 - lo) / step)) + 1))

    act = [([], []) for _ in range(n)]       # (outline edges, cut-out polygons) a station's line can cross
    cut = plate.cut
    for i in range(len(cut)):
        e = (cut[i], cut[(i + 1) % len(cut)])
        k0, k1 = stations(e)
        for k in range(k0, k1 + 1):
            act[k][0].append(e)
    for (f, poly), (x0, y0, x1, y1) in zip(plate.feature_polys, plate._feature_boxes):
        k0, k1 = stations(((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
        for k in range(k0, k1 + 1):
            act[k][1].append((f, poly))
    return act


def _material_intervals(plate, p, v, shrink, features=None):
    """r-intervals where local point p + v*r is solid material (outline minus cut-outs), shrunk by `shrink` mm.

    `features`: the cut-outs this line can touch (precomputed by _station_features); None = test them all."""
    vlen = math.hypot(v[0], v[1])
    if vlen < 1e-9:  # the line crosses this board's plane at a single point
        return [(-1e9, 1e9)] if plate.is_material([p[0], p[1]], shrink) else []
    if _line_misses_box(p, v, plate.bbox2d):
        return []
    if features is None:
        ivs = _polygon_line_intervals(plate.cut, p, v)
        candidates = zip(plate.feature_polys, plate._feature_boxes)
    else:
        edges, feats = features
        ivs = _edge_line_intervals(edges, p, v)
        candidates = ((fp, None) for fp in feats)
    for (_f, poly), box in candidates:
        if not ivs:
            break
        if box is not None and _line_misses_box(p, v, box):
            continue
        holes = _polygon_line_intervals(poly, p, v)
        if holes:
            ivs = _subtract(ivs, holes)
    d = shrink / vlen
    return [(r0 + d, r1 - d) for r0, r1 in ivs if r1 - r0 > 2 * d]


def _line_misses_box(p, v, box):
    x0, y0, x1, y1 = box
    sides = [v[0] * (y - p[1]) - v[1] * (x - p[0]) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    return all(d > 0 for d in sides) or all(d < 0 for d in sides)


def _intersect(xs, ys):
    out = []
    for a0, a1 in xs:
        for b0, b1 in ys:
            lo_, hi_ = max(a0, b0), min(a1, b1)
            if hi_ > lo_:
                out.append((lo_, hi_))
    return out


def _subtract(xs, holes):
    out = []
    for a0, a1 in xs:
        segs = [(a0, a1)]
        for h0, h1 in holes:
            nxt = []
            for s0, s1 in segs:
                if h1 <= s0 or h0 >= s1:
                    nxt.append((s0, s1))
                    continue
                if h0 > s0:
                    nxt.append((s0, h0))
                if h1 < s1:
                    nxt.append((h1, s1))
            segs = nxt
        out.extend(segs)
    return out


def _dist_point_segment3(p, a, b):
    ab = G.v_sub(b, a)
    L2 = G.v_dot(ab, ab)
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, G.v_dot(G.v_sub(p, a), ab) / L2))
    return G.v_len(G.v_sub(p, G.v_add(a, G.v_scale(ab, t))))


def find_collisions(design, plates, only=None, tol=TOL):
    ids = list(plates)
    out = []
    joined_pairs = {frozenset((j['a'], j['b'])) for j in design['joints'] if j.get('status') == 'joined'}
    # A bevelled mitre removes exactly the square-cut wedge along its shared edge (validated in _eval_edge_mitre).
    bevelled = {}
    for j in design['joints']:
        if j.get('status') == 'joined' and j['type'] == 'edge_mitre' and j.get('bevel') and j['a'] in plates \
                and j['b'] in plates and j['a_edge'] < len(plates[j['a']].outline):
            bevelled.setdefault(frozenset((j['a'], j['b'])), []).append(_edge_world(plates[j['a']], j['a_edge']))
    for i in range(len(ids)):
        for k in range(i + 1, len(ids)):
            a, b = plates[ids[i]], plates[ids[k]]
            if only and a.id not in only and b.id not in only:
                continue
            for hit in plate_interference(a, b, tol):
                edges = bevelled.get(frozenset((a.id, b.id)), [])
                if hit['kind'] == 'crossing' and any(
                        _dist_point_segment3(hit['location'], e0, e1) <= max(a.t, b.t) for e0, e1 in edges):
                    continue
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
            issues.append(issue('JOINT_NOT_JOINED', 'warning', 'joint',
                                f"Connection '{j['id']}' ({j['type']} {j['a']} -> {j['b']}) is {j.get('status') or 'not joined'}"
                                + (f" ({j['detached_reason']})" if j.get('detached_reason') else '') + '.',
                                [j['a'], j['b']], joint=j['id']))
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
        'complete': errors == 0 and not any(i['code'] in ('FLOATING_COMPONENT', 'UNJOINED_TAB', 'JOINT_NOT_JOINED')
                                            for i in issues),
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
