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

Glue-free: every connection is a tab locked through a slot (cardboard / friction-fit board).
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
    'sail_thickness': None,   # None = same board as everything else (one sheet material)
}


def rect(w, h):
    """CCW rectangle centred on the origin. Edges: 0 bottom, 1 right, 2 top, 3 left."""
    return [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]]


def tab(tid, edge, offset, width, depth):
    return {'id': tid, 'edge': edge, 'offset': round(offset, 3), 'width': width, 'depth': depth}


def build_components(params=None):
    p = dict(DEFAULTS, **(params or {}))
    t = p['thickness']
    ts = p['sail_thickness'] or t
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

    # Straight aft sides (vertical, in world XY plane at z = +/-hb). They run past the transom to
    # the stern lip so the transom's side tabs land in solid material.
    aft_len = xsh - (xs - p['lip'])
    aft_cx = (xsh + xs - p['lip']) / 2
    for side, z in (('PORT', -hb), ('STBD', hb)):
        comps.append({'id': f'SIDE-AFT-{side}', 'name': f'Aft side panel ({side.lower()})', 'group': 'Hull',
                      'outline': rect(aft_len, H),
                      'tabs': [tab('b1', 0, aft_len * 0.25, 20, t), tab('b2', 0, aft_len * 0.75, 20, t),
                               tab('d1', 2, aft_len * 0.25, 20, t), tab('d2', 2, aft_len * 0.75, 20, t)],
                      'placement': {'position': [round(aft_cx, 3), y_side, z], 'rotation': [0, 0, 0]}})

    # Bow sides run from the shoulder to the stem, yawed about Y. Square-cut boards whose mid-planes meet at
    # angle phi overlap through their thickness by (t/2)(1+cos phi)/sin phi; shortening ONE board by that
    # amount turns the overlap into a clean corner (its end rests on the other's inner face). So the port bow
    # panel is shortened at the stem, and both bow panels at the shoulder (the aft sides stay full length).
    bow_dx, bow_len = xb - xsh, math.hypot(xb - xsh, hb)
    corner = lambda phi: (t / 2.0) * (1 + math.cos(phi)) / math.sin(phi)
    cut_stem = corner(2 * math.atan2(hb, bow_dx))
    cut_shoulder = corner(math.pi - math.atan2(hb, bow_dx))
    for side, z, sgn in (('PORT', -hb, -1), ('STBD', hb, 1)):
        ry = math.atan2(hb, bow_dx) * sgn
        fwd, aft = (cut_stem if side == 'PORT' else 0.0), cut_shoulder
        length = bow_len - fwd - aft
        shift = (aft - fwd) / 2.0                     # along the panel's local +x (towards the bow)
        cx, cz = (xsh + xb) / 2 + math.cos(ry) * shift, z / 2 - math.sin(ry) * shift
        comps.append({'id': f'SIDE-BOW-{side}', 'name': f'Bow side panel ({side.lower()})', 'group': 'Hull',
                      'outline': rect(round(length, 4), H),
                      'tabs': [tab('b1', 0, length / 2, 20, t), tab('d1', 2, length / 2, 20, t)],
                      'placement': {'position': [round(cx, 4), y_side, round(cz, 4)],
                                    'rotation': [0, round(math.degrees(ry), 4), 0]}})

    # Transverse boards (rotation ry = 90: local x -> world -z, normal -> +x). Besides the bottom and
    # deck tabs they carry a tab on each end that locks through a slot in the hull side.
    inner = B - t  # spans between the side inner faces
    transverse = [('TRANSOM', 'Transom', xs, None), ('BULKHEAD-1', 'Aft bulkhead', xs + 0.3 * L, 0.35),
                  ('BULKHEAD-2', 'Forward bulkhead', xs + 0.57 * L, 0.35)]
    for cid, name, x, hole in transverse:
        c = {'id': cid, 'name': name, 'group': 'Structure', 'outline': rect(inner, H),
             'tabs': [tab('b1', 0, inner / 2, 24, t), tab('d1', 2, inner / 2, 24, t),
                      tab('s1', 1, H / 2, 20, t), tab('s2', 3, H / 2, 20, t)],
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

    # Rudder hung on the transom's aft face (tab through the transom), stepping clear of the bottom lip.
    xa = xs - t / 2
    xr = xs - p['lip'] - 2
    rudder = [[xr, -0.4 * H], [xr, t + 5], [xa, t + 5], [xa, 0.9 * H], [xa - 0.07 * L, 0.9 * H],
              [xa - 0.1 * L, -0.4 * H]]
    hinge = 0.9 * H - (t + 5)
    comps.append({'id': 'RUDDER', 'name': 'Rudder', 'group': 'Appendages',
                  'outline': [[round(x, 3), round(y, 3)] for x, y in rudder],
                  'tabs': [tab('h1', 2, hinge / 2, min(16.0, hinge - 6), t)],
                  'placement': {'position': [0, 0, 0], 'rotation': [0, 0, 0]}})

    # Mast stands crosswise on the deck (tab into a deck slot) so the sails can lock into it.
    mast_x, mast_w = xs + 0.63 * L, max(10.0, ts + 7.0)
    deck_top = t + H + t
    comps.append({'id': 'MAST', 'name': 'Mast', 'group': 'Rig',
                  'outline': [[-mast_w / 2, 0], [mast_w / 2, 0], [mast_w / 2, p['mast_height']],
                              [-mast_w / 2, p['mast_height']]],
                  'tabs': [tab('step', 0, mast_w / 2, 6, t)],
                  'placement': {'position': [round(mast_x, 3), deck_top, 0], 'rotation': [0, 90, 0]}})

    # Sails in the centre plane, one on each side of the mast; tabs on the luff lock through mast slots.
    foot = deck_top + 10
    head = deck_top + p['mast_height'] * 0.9
    luff_main = head - foot
    main = [[mast_x - t / 2, foot], [mast_x - t / 2, head], [mast_x - 0.42 * L, foot]]   # edge 0 = luff
    comps.append({'id': 'SAIL-MAIN', 'name': 'Mainsail', 'group': 'Rig', 'color': '#f4efe6',
                  **({'thickness': ts} if ts != t else {}),
                  'outline': [[round(x, 3), round(y, 3)] for x, y in main],
                  'tabs': [tab('m1', 0, luff_main * 0.25, 14, t), tab('m2', 0, luff_main * 0.6, 14, t)],
                  'placement': {'position': [0, 0, 0], 'rotation': [0, 0, 0]}})
    jib_top = deck_top + p['mast_height'] * 0.75
    luff_jib = jib_top - (foot + 4)
    jib = [[mast_x + t / 2, foot + 4], [mast_x + 0.3 * L, foot + 4], [mast_x + t / 2, jib_top]]   # edge 2 = luff
    comps.append({'id': 'SAIL-JIB', 'name': 'Jib', 'group': 'Rig', 'color': '#f4efe6',
                  **({'thickness': ts} if ts != t else {}),
                  'outline': [[round(x, 3), round(y, 3)] for x, y in jib],
                  'tabs': [tab('j1', 2, luff_jib * 0.15, 14, t), tab('j2', 2, luff_jib * 0.55, 14, t)],
                  'placement': {'position': [0, 0, 0], 'rotation': [0, 0, 0]}})
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
    # Hull corners (shoulder, stem) need no joint of their own: every side panel is locked by its
    # tabs into the bottom and the deck.
    for cid in ('TRANSOM', 'BULKHEAD-1', 'BULKHEAD-2'):
        ts(f'J-{cid}-b1', cid, 'b1', 'HULL-BOTTOM')
        ts(f'J-{cid}-d1', cid, 'd1', 'DECK')
        # ry = 90: local +x edge (1) faces world -z (port), local -x edge (3) faces +z (starboard)
        ts(f'J-{cid}-PORT', cid, 's1', 'SIDE-AFT-PORT')
        ts(f'J-{cid}-STBD', cid, 's2', 'SIDE-AFT-STBD')
    ts('J-KEEL-1', 'KEEL', 'k1', 'HULL-BOTTOM')
    ts('J-KEEL-2', 'KEEL', 'k2', 'HULL-BOTTOM')
    ts('J-RUDDER', 'RUDDER', 'h1', 'TRANSOM')
    ts('J-MAST-STEP', 'MAST', 'step', 'DECK')
    for tid in ('m1', 'm2'):
        ts(f'J-SAIL-MAIN-{tid}', 'SAIL-MAIN', tid, 'MAST')
    for tid in ('j1', 'j2'):
        ts(f'J-SAIL-JIB-{tid}', 'SAIL-JIB', tid, 'MAST')
    return J


def build_design(design_id='boat', params=None):
    """Assemble the boat through the real join pipeline (slots are generated, never assumed)."""
    from ..model import normalize_design
    from ..joining import join
    p = dict(DEFAULTS, **(params or {}))
    design = normalize_design({
        'id': design_id, 'name': 'Day Sailer (board model)',
        'description': 'Glue-free parametric sailing boat: every part locks in with tabs and slots — bottom, four '
                       'hull side panels, transom, two bulkheads, deck with cockpit, keel, rudder, mast and two sails.',
        'joinery': 'interlocking',
        'material': {'name': f"Board {p['thickness']:g} mm (cardboard / MDF)", 'thickness': p['thickness'],
                     'clearance': 0.15},
        'components': build_components(p)})
    failures = []
    for spec in build_joints():
        res = join(design, spec, auto_repair=True)
        if res['accepted']:
            design = res['design']
        else:
            failures.append(res)
    return design, failures


SEED_PATH = __import__('os').path.join(__import__('os').path.dirname(__file__), 'boat_seed.json')


def load_seed(design_id='boat'):
    """The example boat as built by build_design(), shipped pre-built so server start-up does not spend seconds
    re-running ~30 joins. tests/python keeps the file identical to a fresh build (regenerate with write_seed())."""
    import json
    from ..model import normalize_design
    with open(SEED_PATH) as f:
        d = json.load(f)
    d['id'] = design_id
    return normalize_design(d)


def write_seed():
    import json
    design, failures = build_design('boat')
    assert not failures, failures
    for j in design['joints']:
        j.pop('joined_at', None)
    with open(SEED_PATH, 'w') as f:
        json.dump(design, f, indent=1)
    return design
