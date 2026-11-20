"""
Parametric sailing-boat example built only from generic board primitives.

Nothing here is known to the engine: the boat is plain component/joint data.
Hull plan (world XZ, bow at +X, +Y up):

      stern (-L/2)              shoulder (x_sh)          bow (+L/2)
        +--------------------------+
        |                          \\
        |   transom    bulkheads    > bow sides meet in a mitre
        |                          /
        +--------------------------+

Receiving slots are *not* drawn here: the joining pipeline detects that each tab needs a
slot and generates it (auto_repair). The deck cockpit and bulkhead lightening holes are
intentional openings and must survive every operation.
"""
import math

from ..geometry import offset_convex_polygon

DEFAULTS = {
    'length': 300.0,      # overall hull length at side mid-planes
    'beam': 80.0,         # hull width at side mid-planes
    'depth': 50.0,        # side height between bottom and deck
    'shoulder': 60.0,     # x where the bow taper starts
    'lip': 6.0,           # bottom/deck overhang beyond the hull sides
    'mast_height': 200.0,
    'thickness': 3.0,
    'sail_thickness': 1.5,
}


def rect(w, h):
    """CCW rectangle centred on the origin. Edges: 0 bottom, 1 right, 2 top, 3 left."""
    return [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]]


def tab(tid, edge, offset, width, depth):
    return {'id': tid, 'edge': edge, 'offset': round(offset, 3), 'width': width, 'depth': depth}


def build_components(params=None):
    p = dict(DEFAULTS, **(params or {}))
    t, ts = p['thickness'], p['sail_thickness']
    L, B, H = p['length'], p['beam'], p['depth']
    xs, xb, xsh = -L / 2, L / 2, p['shoulder']
    hb = B / 2
    y_side = t + H / 2          # side panel centre height (bottom top face at y = t)
    y_deck = t + H + t / 2
    comps = []

    # Bottom & deck share the hull plan, offset by the lip. Local (x, y) maps to world (x, -z).
    plan = [[xs, -hb], [xsh, -hb], [xb, 0.0], [xsh, hb], [xs, hb]]
    plate_plan = [[round(x, 3), round(y, 3)] for x, y in offset_convex_polygon(plan, p['lip'])]
    comps.append({'id': 'HULL-BOTTOM', 'name': 'Hull bottom', 'group': 'Hull',
                  'outline': plate_plan,
                  'placement': {'position': [0, t / 2, 0], 'rotation': [-90, 0, 0]}})
    cockpit_len, cockpit_w = 0.2 * L, 0.6 * B
    comps.append({'id': 'DECK', 'name': 'Deck', 'group': 'Deck',
                  'outline': plate_plan,
                  'features': [{'id': 'cockpit', 'kind': 'opening', 'shape': 'rect',
                                'center': [round(xs + 0.15 * L, 3), 0], 'width': cockpit_len,
                                'height': cockpit_w, 'angle': 0, 'note': 'Cockpit well (intentional opening)'}],
                  'placement': {'position': [0, y_deck, 0], 'rotation': [-90, 0, 0]}})

    # Straight aft sides (vertical, in world XY plane at z = +/-hb), flush with transom aft face.
    aft_len = xsh - (xs - t / 2)
    aft_cx = (xsh + xs - t / 2) / 2
    for side, z in (('PORT', -hb), ('STBD', hb)):
        comps.append({'id': f'SIDE-AFT-{side}', 'name': f'Aft side panel ({side.lower()})', 'group': 'Hull',
                      'outline': rect(aft_len, H),
                      'tabs': [tab('b1', 0, aft_len * 0.25, 20, t), tab('b2', 0, aft_len * 0.75, 20, t),
                               tab('d1', 2, aft_len * 0.25, 20, t), tab('d2', 2, aft_len * 0.75, 20, t)],
                      'placement': {'position': [round(aft_cx, 3), y_side, z], 'rotation': [0, 0, 0]}})

    # Bow sides run from the shoulder to the stem, yawed about Y.
    bow_dx, bow_len = xb - xsh, math.hypot(xb - xsh, hb)
    for side, z, sgn in (('PORT', -hb, -1), ('STBD', hb, 1)):
        ry = math.degrees(math.atan2(hb, bow_dx)) * sgn
        comps.append({'id': f'SIDE-BOW-{side}', 'name': f'Bow side panel ({side.lower()})', 'group': 'Hull',
                      'outline': rect(bow_len, H),
                      'tabs': [tab('b1', 0, bow_len / 2, 20, t), tab('d1', 2, bow_len / 2, 20, t)],
                      'placement': {'position': [round((xsh + xb) / 2, 3), y_side, z / 2],
                                    'rotation': [0, round(ry, 4), 0]}})

    # Transverse boards (rotation ry = 90: local x -> world -z, normal -> +x)
    inner = B - t  # fits between side inner faces
    transverse = [('TRANSOM', 'Transom', xs, None), ('BULKHEAD-1', 'Aft bulkhead', xs + 0.3 * L, 0.35),
                  ('BULKHEAD-2', 'Forward bulkhead', xs + 0.57 * L, 0.35)]
    for cid, name, x, hole in transverse:
        c = {'id': cid, 'name': name, 'group': 'Structure', 'outline': rect(inner, H),
             'tabs': [tab('b1', 0, inner / 2, 24, t), tab('d1', 2, inner / 2, 24, t)],
             'placement': {'position': [round(x, 3), y_side, 0], 'rotation': [0, 90, 0]}}
        if hole:
            c['features'] = [{'id': 'lightening', 'kind': 'opening', 'shape': 'circle', 'center': [0, 0],
                              'diameter': round(hole * min(inner, H), 2), 'note': 'Lightening hole (intentional)'}]
        comps.append(c)

    # Keel fin below the bottom (world XY plane, z = 0), tabs up into the bottom.
    kx0, kx1, kd = xs + 0.2 * L, xs + 0.67 * L, 0.6 * H
    keel = [[kx0 + 0.1 * L, -kd], [kx1 - 0.1 * L, -kd], [kx1, 0], [kx0, 0]]
    top_len = kx1 - kx0
    comps.append({'id': 'KEEL', 'name': 'Keel fin', 'group': 'Appendages', 'outline': keel,
                  'tabs': [tab('k1', 2, top_len * 0.43, 20, t), tab('k2', 2, top_len * 0.9, 16, t)],
                  'placement': {'position': [0, 0, 0], 'rotation': [0, 0, 0]}})

    # Rudder hung on the transom's aft face, stepping clear of the bottom lip.
    xa = xs - t / 2
    xr = xs - p['lip'] - 2
    rudder = [[xr, -0.4 * H], [xr, t + 5], [xa, t + 5], [xa, 0.9 * H], [xa - 0.07 * L, 0.9 * H],
              [xa - 0.1 * L, -0.4 * H]]
    comps.append({'id': 'RUDDER', 'name': 'Rudder', 'group': 'Appendages',
                  'outline': [[round(x, 3), round(y, 3)] for x, y in rudder],
                  'placement': {'position': [0, 0, 0], 'rotation': [0, 0, 0]}})

    # Mast stands on the deck with a tab into a deck slot.
    mast_x, mast_w = xs + 0.63 * L, 10.0
    deck_top = t + H + t
    comps.append({'id': 'MAST', 'name': 'Mast', 'group': 'Rig',
                  'outline': [[-mast_w / 2, 0], [mast_w / 2, 0], [mast_w / 2, p['mast_height']],
                              [-mast_w / 2, p['mast_height']]],
                  'tabs': [tab('step', 0, mast_w / 2, 6, t)],
                  'placement': {'position': [round(mast_x, 3), deck_top, 0], 'rotation': [0, 0, 0]}})

    # Sails laminated to opposite faces of the mast (face lap joints).
    z_sail = t / 2 + ts / 2
    luff_in = 2.0
    foot = deck_top + 10
    head = deck_top + p['mast_height'] * 0.9
    main = [[mast_x - mast_w / 2 + luff_in + 1, foot], [mast_x - mast_w / 2 + luff_in + 1, head],
            [mast_x - 0.42 * L, foot]]
    comps.append({'id': 'SAIL-MAIN', 'name': 'Mainsail', 'group': 'Rig', 'thickness': ts, 'color': '#f4efe6',
                  'outline': [[round(x, 3), round(y, 3)] for x, y in main],
                  'placement': {'position': [0, 0, z_sail], 'rotation': [0, 0, 0]}})
    jib = [[mast_x + mast_w / 2 - luff_in - 1, foot + 4], [mast_x + 0.3 * L, foot + 4],
           [mast_x + mast_w / 2 - luff_in - 1, deck_top + p['mast_height'] * 0.75]]
    comps.append({'id': 'SAIL-JIB', 'name': 'Jib', 'group': 'Rig', 'thickness': ts, 'color': '#f4efe6',
                  'outline': [[round(x, 3), round(y, 3)] for x, y in jib],
                  'placement': {'position': [0, 0, -z_sail], 'rotation': [0, 0, 0]}})
    return comps


def build_joints():
    """Intended connections. Slots are not specified: the joining pipeline finds/creates them."""
    J = []

    def ts(jid, a, tab_id, b):
        J.append({'id': jid, 'type': 'tab_slot', 'a': a, 'tab': tab_id, 'b': b})

    for side in ('PORT', 'STBD'):
        for tb in ('b1', 'b2'):
            ts(f'J-AFT-{side}-{tb}', f'SIDE-AFT-{side}', tb, 'HULL-BOTTOM')
        for td in ('d1', 'd2'):
            ts(f'J-AFT-{side}-{td}', f'SIDE-AFT-{side}', td, 'DECK')
        ts(f'J-BOW-{side}-b1', f'SIDE-BOW-{side}', 'b1', 'HULL-BOTTOM')
        ts(f'J-BOW-{side}-d1', f'SIDE-BOW-{side}', 'd1', 'DECK')
        J.append({'id': f'J-SHOULDER-{side}', 'type': 'edge_mitre', 'a': f'SIDE-BOW-{side}', 'a_edge': 3,
                  'b': f'SIDE-AFT-{side}', 'b_edge': 1})
    J.append({'id': 'J-STEM', 'type': 'edge_mitre', 'a': 'SIDE-BOW-PORT', 'a_edge': 1,
              'b': 'SIDE-BOW-STBD', 'b_edge': 1})
    for cid in ('TRANSOM', 'BULKHEAD-1', 'BULKHEAD-2'):
        ts(f'J-{cid}-b1', cid, 'b1', 'HULL-BOTTOM')
        ts(f'J-{cid}-d1', cid, 'd1', 'DECK')
        # ry = 90: local +x edge (1) faces world -z (port), local -x edge (3) faces +z (starboard)
        J.append({'id': f'J-{cid}-PORT', 'type': 'edge_butt', 'a': cid, 'a_edge': 1, 'b': 'SIDE-AFT-PORT'})
        J.append({'id': f'J-{cid}-STBD', 'type': 'edge_butt', 'a': cid, 'a_edge': 3, 'b': 'SIDE-AFT-STBD'})
    ts('J-KEEL-1', 'KEEL', 'k1', 'HULL-BOTTOM')
    ts('J-KEEL-2', 'KEEL', 'k2', 'HULL-BOTTOM')
    J.append({'id': 'J-RUDDER', 'type': 'edge_butt', 'a': 'RUDDER', 'a_edge': 2, 'b': 'TRANSOM'})
    ts('J-MAST-STEP', 'MAST', 'step', 'DECK')
    J.append({'id': 'J-SAIL-MAIN', 'type': 'face_lap', 'a': 'SAIL-MAIN', 'b': 'MAST'})
    J.append({'id': 'J-SAIL-JIB', 'type': 'face_lap', 'a': 'SAIL-JIB', 'b': 'MAST'})
    return J


def build_design(design_id='boat', params=None):
    """Assemble the boat through the real join pipeline (slots are generated, never assumed)."""
    from ..model import normalize_design
    from ..joining import join
    p = dict(DEFAULTS, **(params or {}))
    design = normalize_design({
        'id': design_id, 'name': 'Day Sailer (board model)',
        'description': 'Parametric sailing boat: bottom, four hull side panels, transom, two bulkheads, deck with '
                       'cockpit, keel, rudder, mast, mainsail and jib.',
        'material': {'name': f"Birch plywood {p['thickness']:g} mm", 'thickness': p['thickness']},
        'components': build_components(p)})
    failures = []
    for spec in build_joints():
        res = join(design, spec, auto_repair=True)
        if res['accepted']:
            design = res['design']
        else:
            failures.append(res)
    return design, failures
