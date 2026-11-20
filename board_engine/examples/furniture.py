"""
Real-world furniture built from generic board primitives (plain component/joint data, no engine knowledge).

World frame: mm, +Y up, front = +Z, right = +X, floor at y = 0. Every board is described by the world box it
occupies; the thin axis of the box is the board thickness:

    thin Y (horizontal):  rotation [-90, 0, 0]  local x = world x,  local y = -world z
    thin X (vertical):    rotation [0, 90, 0]   local x = -world z, local y = world y
    thin Z (vertical):    rotation [0, 0, 0]    local x = world x,  local y = world y

Joints name the edge of A that faces the receiving board by world direction ('+x', '-y', ...); the edge index
is computed from the placement so builders never hard-code indices. Every product is assembled through the
real join pipeline (joining.join); a rejected joint is returned as a failure, never skipped silently.
"""
import math

from ..geometry import Frame

PB18 = {'name': 'Particle board 18 mm (melamine)', 'type': 'particle_board', 'thickness': 18.0, 'kerf': 3.2,
        'clearance': 0.2}
HB6 = {'name': 'Hardboard 6 mm', 'type': 'hardboard'}
PLY = lambda t: {'name': f'Birch plywood {t:g} mm', 'type': 'plywood'}
OAK = lambda t: {'name': f'Oak {t:g} mm', 'type': 'solid_wood'}
MDF = lambda t: {'name': f'MDF {t:g} mm', 'type': 'mdf'}
SHEET = {'width': 2800.0, 'height': 2070.0, 'spacing': 4.0}
DIRS = {'+x': (1, 0, 0), '-x': (-1, 0, 0), '+y': (0, 1, 0), '-y': (0, -1, 0), '+z': (0, 0, 1), '-z': (0, 0, -1)}


def rect(w, h):
    return [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]]


def panel(cid, name, group, lo, hi, **kw):
    """Board filling the world box lo..hi (its thinnest extent is the thickness)."""
    size = [hi[i] - lo[i] for i in range(3)]
    centre = [round((hi[i] + lo[i]) / 2, 4) for i in range(3)]
    thin = min(range(3), key=lambda i: size[i])
    if thin == 1:
        outline, rot = rect(size[0], size[2]), [-90, 0, 0]
    elif thin == 0:
        outline, rot = rect(size[2], size[1]), [0, 90, 0]
    else:
        outline, rot = rect(size[0], size[1]), [0, 0, 0]
    c = {'id': cid, 'name': name, 'group': group, 'outline': outline, 'thickness': round(size[thin], 4),
         'placement': {'position': centre, 'rotation': rot}}
    c.update(kw)
    return c


def edge_facing(comp, direction):
    """Index of the outline edge of `comp` whose outward normal points along world `direction`."""
    f = Frame(comp['placement']['position'], comp['placement']['rotation'])
    want = DIRS[direction]
    pts = comp['outline']
    best = None
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        n = f.dir_to_world([(b[1] - a[1]) / L, -(b[0] - a[0]) / L, 0])
        d = sum(n[k] * want[k] for k in range(3))
        if best is None or d > best[0]:
            best = (d, i)
    return best[1]


class Builder:
    def __init__(self, design_id, name, description, material=PB18, sheet=SHEET, joinery='glue_allowed'):
        self.design = {'id': design_id, 'name': name, 'description': description, 'joinery': joinery,
                       'material': dict(material), 'sheet': dict(sheet), 'components': [], 'joints': []}
        self.comps = {}
        self.joints = []

    def add(self, comp):
        self.design['components'].append(comp)
        self.comps[comp['id']] = comp
        return comp

    def butt(self, a, toward, b, fasteners=None, jid=None):
        j = {'id': jid or f'J-{a}-{b}', 'type': 'edge_butt', 'a': a, 'a_edge': edge_facing(self.comps[a], toward),
             'b': b}
        if fasteners:
            j['fasteners'] = fasteners if isinstance(fasteners, dict) else {'kind': fasteners}
        self.joints.append(j)
        return j

    def mitre(self, a, a_dir, b, b_dir, bevel=True, fasteners=None, jid=None):
        j = {'id': jid or f'M-{a}-{b}', 'type': 'edge_mitre', 'a': a, 'a_edge': edge_facing(self.comps[a], a_dir),
             'b': b, 'b_edge': edge_facing(self.comps[b], b_dir)}
        if bevel:
            j['bevel'] = True
        if fasteners:
            j['fasteners'] = fasteners if isinstance(fasteners, dict) else {'kind': fasteners}
        self.joints.append(j)
        return j

    def hinge(self, door, hinge_side, carcass, jid=None, **kw):
        j = dict({'id': jid or f'H-{door}', 'type': 'hinge', 'a': door, 'a_edge': edge_facing(self.comps[door], hinge_side),
                  'b': carcass}, **kw)
        self.joints.append(j)
        return j

    def build(self):
        from ..joining import join
        from ..model import normalize_design
        design = normalize_design(self.design)
        failures = []
        for spec in self.joints:
            res = join(design, spec, auto_repair=True)
            if res['accepted']:
                design = res['design']
            else:
                failures.append({'joint': spec['id'], 'status': res['status'],
                                 'issues': [(i['code'], i['message']) for i in res['issues'] if i['severity'] == 'error']})
        return design, failures


# ---------------------------------------------------------------------------
# 1. Four-legged table
# ---------------------------------------------------------------------------

def table(L=1200.0, W=750.0, H=750.0, top_t=25.0, leg_t=25.0, leg_w=70.0, apron_h=100.0, apron_t=18.0):
    b = Builder('table', 'Dining table', 'Solid-oak top and legs, plywood aprons, all dowelled.', material=PLY(18))
    yt = H - top_t
    b.add(panel('TOP', 'Table top', 'Top', [-L / 2, yt, -W / 2], [L / 2, H, W / 2], material=OAK(top_t), grain='x'))
    xl, zl = L / 2 - 30 - leg_t / 2, W / 2 - 30 - leg_w / 2        # leg centres, 30 mm in from the top edge
    for sx, sz, n in ((-1, 1, 'FL'), (1, 1, 'FR'), (-1, -1, 'BL'), (1, -1, 'BR')):
        b.add(panel(f'LEG-{n}', f'Leg {n}', 'Legs', [sx * xl - leg_t / 2, 0, sz * zl - leg_w / 2],
                    [sx * xl + leg_t / 2, yt, sz * zl + leg_w / 2], material=OAK(leg_t), grain='y'))
    xi = xl - leg_t / 2                                              # leg inner faces
    for sz, n in ((1, 'FRONT'), (-1, 'BACK')):
        b.add(panel(f'APRON-{n}', f'{n.title()} apron', 'Frame', [-xi, yt - apron_h, sz * zl - apron_t / 2],
                    [xi, yt, sz * zl + apron_t / 2], grain='x'))
    zi = zl - apron_t / 2
    for sx, n in ((-1, 'LEFT'), (1, 'RIGHT')):
        x = sx * (xi - 60)
        b.add(panel(f'APRON-{n}', f'{n.title()} apron', 'Frame', [x - apron_t / 2, yt - apron_h, -zi],
                    [x + apron_t / 2, yt, zi], grain='x'))
    for n in ('FL', 'FR', 'BL', 'BR'):
        b.butt(f'LEG-{n}', '+y', 'TOP', 'dowel')
    for sz, n in ((1, 'FRONT'), (-1, 'BACK')):
        b.butt(f'APRON-{n}', '-x', f'LEG-{"F" if sz > 0 else "B"}L', 'dowel', jid=f'J-APRON-{n}-L')
        b.butt(f'APRON-{n}', '+x', f'LEG-{"F" if sz > 0 else "B"}R', 'dowel', jid=f'J-APRON-{n}-R')
        b.butt(f'APRON-{n}', '+y', 'TOP', 'dowel')
    for n in ('LEFT', 'RIGHT'):
        b.butt(f'APRON-{n}', '+z', 'APRON-FRONT', 'dowel')
        b.butt(f'APRON-{n}', '-z', 'APRON-BACK', 'dowel')
        b.butt(f'APRON-{n}', '+y', 'TOP', 'dowel')
    return b


# ---------------------------------------------------------------------------
# 2. Bookshelf with fixed shelves and a screwed-on back
# ---------------------------------------------------------------------------

def carcass(b, W, H, D, t=18.0, back=True, prefix=''):
    """Sides full height, top and bottom between them; back panel screwed onto the rear edges."""
    x = W / 2
    b.add(panel(f'{prefix}SIDE-L', 'Left side', 'Carcass', [-x, 0, -D / 2], [-x + t, H, D / 2], grain='y',
                edge_banding=[{'edge': 3, 'thickness': 1.0}]))
    b.add(panel(f'{prefix}SIDE-R', 'Right side', 'Carcass', [x - t, 0, -D / 2], [x, H, D / 2], grain='y',
                edge_banding=[{'edge': 3, 'thickness': 1.0}]))
    b.add(panel(f'{prefix}BOTTOM', 'Bottom', 'Carcass', [-x + t, 0, -D / 2], [x - t, t, D / 2], grain='x',
                edge_banding=[{'edge': 0, 'thickness': 1.0}]))
    b.add(panel(f'{prefix}TOP', 'Top', 'Carcass', [-x + t, H - t, -D / 2], [x - t, H, D / 2], grain='x',
                edge_banding=[{'edge': 0, 'thickness': 1.0}]))
    for part in ('BOTTOM', 'TOP'):
        b.butt(f'{prefix}{part}', '-x', f'{prefix}SIDE-L', 'confirmat')
        b.butt(f'{prefix}{part}', '+x', f'{prefix}SIDE-R', 'confirmat')
    if back:
        b.add(panel(f'{prefix}BACK', 'Back panel', 'Back', [-x, 0, -D / 2 - 6], [x, H, -D / 2], material=HB6))
        for part in ('SIDE-L', 'SIDE-R', 'TOP', 'BOTTOM'):
            b.butt(f'{prefix}{part}', '-z', f'{prefix}BACK', {'kind': 'screw', 'length': 25, 'diameter': 3.5})


def bookshelf(W=800.0, H=1800.0, D=300.0, shelves=3):
    b = Builder('bookshelf', 'Bookshelf', f'{W:g} x {H:g} x {D:g} mm particle-board bookshelf, {shelves} fixed shelves.')
    carcass(b, W, H, D)
    pitch = (H - 36) / (shelves + 1)
    for i in range(shelves):
        y = 18 + pitch * (i + 1) - 9
        b.add(panel(f'SHELF-{i + 1}', f'Shelf {i + 1}', 'Shelves', [-W / 2 + 18, y, -D / 2], [W / 2 - 18, y + 18, D / 2],
                    grain='x', edge_banding=[{'edge': 0, 'thickness': 1.0}]))
        b.butt(f'SHELF-{i + 1}', '-x', 'SIDE-L', 'confirmat')
        b.butt(f'SHELF-{i + 1}', '+x', 'SIDE-R', 'confirmat')
        b.butt(f'SHELF-{i + 1}', '-z', 'BACK', {'kind': 'screw', 'length': 25, 'diameter': 3.5})
    return b


# ---------------------------------------------------------------------------
# 3. Cabinet with two doors, a partition and a shelf
# ---------------------------------------------------------------------------

def doors(b, W, H, D, count=2, reveal=3.0, gap=1.0, edge_in=2.0, t=18.0, ids=('DOOR-L', 'DOOR-R'),
          carcass_ids=('SIDE-L', 'SIDE-R')):
    z0 = D / 2 + gap
    if count == 1:
        b.add(panel(ids[0], 'Door', 'Doors', [-W / 2 + edge_in, edge_in, z0], [W / 2 - edge_in, H - edge_in, z0 + t],
                    material=MDF(t), grain='y'))
        b.hinge(ids[0], '-x', carcass_ids[0], gap=gap + 1.0)
        return
    half = reveal / 2
    b.add(panel(ids[0], 'Left door', 'Doors', [-W / 2 + edge_in, edge_in, z0], [-half, H - edge_in, z0 + t],
                material=MDF(t), grain='y'))
    b.add(panel(ids[1], 'Right door', 'Doors', [half, edge_in, z0], [W / 2 - edge_in, H - edge_in, z0 + t],
                material=MDF(t), grain='y'))
    b.hinge(ids[0], '-x', carcass_ids[0], gap=gap + 1.0)
    b.hinge(ids[1], '+x', carcass_ids[1], gap=gap + 1.0)


def cabinet(W=800.0, H=720.0, D=560.0, shelf_y=340.0):
    b = Builder('cabinet', 'Base cabinet', 'Two-door cabinet with a centre partition and one shelf.')
    carcass(b, W, H, D)
    b.add(panel('PARTITION', 'Partition', 'Carcass', [-9, 18, -D / 2], [9, H - 18, D / 2], grain='y',
                edge_banding=[{'edge': 3, 'thickness': 1.0}]))
    b.butt('PARTITION', '-y', 'BOTTOM', 'confirmat')
    b.butt('PARTITION', '+y', 'TOP', 'confirmat')
    b.add(panel('SHELF', 'Shelf (left)', 'Shelves', [-W / 2 + 18, shelf_y, -D / 2 + 20], [-9, shelf_y + 18, D / 2 - 20],
                grain='x', edge_banding=[{'edge': 0, 'thickness': 1.0}]))
    b.butt('SHELF', '-x', 'SIDE-L', 'confirmat')
    b.butt('SHELF', '+x', 'PARTITION', 'confirmat')
    b.butt('PARTITION', '-z', 'BACK', {'kind': 'screw', 'length': 25, 'diameter': 3.5})
    doors(b, W, H, D)
    return b


# ---------------------------------------------------------------------------
# 4. Wardrobe: shelved compartment + hanging compartment, two doors, split back
# ---------------------------------------------------------------------------

def wardrobe(W=1200.0, H=2000.0, D=580.0, xp=-100.0, shelf_ys=(400, 800, 1200, 1600), hat_y=1700.0):
    b = Builder('wardrobe', 'Wardrobe', 'Two-door wardrobe: shelves on the left, hanging space with a hat shelf.')
    carcass(b, W, H, D, back=False)
    shelves = []
    b.add(panel('PARTITION', 'Partition', 'Carcass', [xp - 9, 18, -D / 2], [xp + 9, H - 18, D / 2], grain='y',
                edge_banding=[{'edge': 3, 'thickness': 1.0}]))
    b.butt('PARTITION', '-y', 'BOTTOM', 'confirmat')
    b.butt('PARTITION', '+y', 'TOP', 'confirmat')
    for i, y in enumerate(shelf_ys):
        sid = f'SHELF-{i + 1}'
        b.add(panel(sid, f'Shelf {i + 1}', 'Shelves', [-W / 2 + 18, y, -D / 2], [xp - 9, y + 18, D / 2 - 20], grain='x',
                    edge_banding=[{'edge': 0, 'thickness': 1.0}]))
        b.butt(sid, '-x', 'SIDE-L', 'confirmat')
        b.butt(sid, '+x', 'PARTITION', 'confirmat')
        shelves.append(sid)
    b.add(panel('HAT-SHELF', 'Hat shelf', 'Shelves', [xp + 9, hat_y, -D / 2], [W / 2 - 18, hat_y + 18, D / 2 - 20],
                grain='x', edge_banding=[{'edge': 0, 'thickness': 1.0}]))
    b.butt('HAT-SHELF', '-x', 'PARTITION', 'confirmat')
    b.butt('HAT-SHELF', '+x', 'SIDE-R', 'confirmat')
    # Back in two panels (a 1200 x 2000 back does not fit a 2070 mm sheet's usable width). The left panel covers
    # the whole partition edge so its screws land in full material; the split is on the partition's right face.
    b.add(panel('BACK-L', 'Back panel left', 'Back', [-W / 2, 0, -D / 2 - 6], [xp + 9, H, -D / 2], material=HB6))
    b.add(panel('BACK-R', 'Back panel right', 'Back', [xp + 9, 0, -D / 2 - 6], [W / 2, H, -D / 2], material=HB6))
    screw = {'kind': 'screw', 'length': 25, 'diameter': 3.5}
    b.butt('SIDE-L', '-z', 'BACK-L', screw)
    b.butt('SIDE-R', '-z', 'BACK-R', screw)
    for part, back in (('TOP', 'BACK-L'), ('TOP', 'BACK-R'), ('BOTTOM', 'BACK-L'), ('BOTTOM', 'BACK-R')):
        b.butt(part, '-z', back, screw, jid=f'J-{part}-{back}')
    b.butt('PARTITION', '-z', 'BACK-L', screw)
    for sid in shelves:
        b.butt(sid, '-z', 'BACK-L', screw)
    b.butt('HAT-SHELF', '-z', 'BACK-R', screw)
    doors(b, W, H, D)
    return b


# ---------------------------------------------------------------------------
# 5. Drawer box
# ---------------------------------------------------------------------------

def drawer(W=400.0, D=450.0, H=150.0, t=15.0, bottom_t=6.0):
    b = Builder('drawer', 'Drawer box', 'Plywood drawer: dowelled corners, bottom screwed on from below.',
                material=PLY(t), sheet={'width': 2440, 'height': 1220, 'spacing': 4})
    y0 = bottom_t
    b.add(panel('DRW-SIDE-L', 'Drawer side left', 'Drawer', [-W / 2, y0, -D / 2], [-W / 2 + t, y0 + H, D / 2], grain='x'))
    b.add(panel('DRW-SIDE-R', 'Drawer side right', 'Drawer', [W / 2 - t, y0, -D / 2], [W / 2, y0 + H, D / 2], grain='x'))
    b.add(panel('DRW-FRONT', 'Drawer front (inner)', 'Drawer', [-W / 2 + t, y0, D / 2 - t], [W / 2 - t, y0 + H, D / 2],
                grain='x'))
    b.add(panel('DRW-BACK', 'Drawer back', 'Drawer', [-W / 2 + t, y0, -D / 2], [W / 2 - t, y0 + H, -D / 2 + t], grain='x'))
    b.add(panel('DRW-BOTTOM', 'Drawer bottom', 'Drawer', [-W / 2, 0, -D / 2], [W / 2, bottom_t, D / 2], material=HB6))
    for p in ('DRW-FRONT', 'DRW-BACK'):
        b.butt(p, '-x', 'DRW-SIDE-L', 'dowel', jid=f'J-{p}-L')
        b.butt(p, '+x', 'DRW-SIDE-R', 'dowel', jid=f'J-{p}-R')
    for p in ('DRW-SIDE-L', 'DRW-SIDE-R', 'DRW-FRONT', 'DRW-BACK'):
        b.butt(p, '-y', 'DRW-BOTTOM', {'kind': 'screw', 'length': 25, 'diameter': 3.5})
    return b


# ---------------------------------------------------------------------------
# 6. L-shaped desk
# ---------------------------------------------------------------------------

def l_desk(L1=1400.0, D1=700.0, W2=600.0, L2=800.0, H=750.0, t=24.0, g=18.0):
    b = Builder('l-desk', 'L-shaped desk', 'Plywood L desk: main top and return top dowelled edge to edge, '
                'three gable supports.', material=PLY(18), sheet={'width': 2500, 'height': 1250, 'spacing': 4})
    yt = H - t
    x1 = L1 / 2 - W2                                  # the return starts here along the main top's back edge
    # Main top: back edge split at x1 so its right part matches the return's front edge exactly.
    #   local (x, y) = world (x, -z): back edge is local y = +D1/2
    main = [[-L1 / 2, -D1 / 2], [L1 / 2, -D1 / 2], [L1 / 2, D1 / 2], [x1, D1 / 2], [-L1 / 2, D1 / 2]]
    b.add({'id': 'TOP-MAIN', 'name': 'Main top', 'group': 'Tops', 'outline': main, 'thickness': t,
           'material': PLY(t), 'grain': 'x',
           'placement': {'position': [0, yt + t / 2, 0], 'rotation': [-90, 0, 0]}})
    b.add(panel('TOP-RETURN', 'Return top', 'Tops', [x1, yt, -D1 / 2 - L2], [L1 / 2, H, -D1 / 2], material=PLY(t),
                grain='y'))
    main_back = 2   # edge from (L1/2, D1/2) to (x1, D1/2)
    b.joints.append({'id': 'M-TOPS', 'type': 'edge_mitre', 'a': 'TOP-RETURN',
                     'a_edge': edge_facing(b.comps['TOP-RETURN'], '+z'), 'b': 'TOP-MAIN', 'b_edge': main_back,
                     'fasteners': {'kind': 'dowel'}})
    b.add(panel('GABLE-L', 'Left gable', 'Supports', [-L1 / 2, 0, -D1 / 2], [-L1 / 2 + g, yt, D1 / 2], grain='y'))
    # 1500 mm long: with vertical grain it would not fit a 2440 x 1220 sheet (grain runs along the sheet length)
    b.add(panel('GABLE-R', 'Right gable', 'Supports', [L1 / 2 - g, 0, -D1 / 2 - L2], [L1 / 2, yt, D1 / 2], grain='x'))
    b.add(panel('GABLE-B', 'Return end gable', 'Supports', [x1, 0, -D1 / 2 - L2], [L1 / 2 - g, yt, -D1 / 2 - L2 + g],
                grain='y'))
    b.butt('GABLE-L', '+y', 'TOP-MAIN', 'dowel')
    b.butt('GABLE-R', '+y', 'TOP-MAIN', 'dowel', jid='J-GABLE-R-MAIN')
    b.butt('GABLE-R', '+y', 'TOP-RETURN', 'dowel', jid='J-GABLE-R-RETURN')
    b.butt('GABLE-B', '+y', 'TOP-RETURN', 'dowel')
    b.butt('GABLE-B', '+x', 'GABLE-R', 'dowel')
    return b


# ---------------------------------------------------------------------------
# 7. Multi-level storage rack (two bays, staggered shelves on the shared upright)
# ---------------------------------------------------------------------------

def storage_rack(bays=2, levels=5, bay_w=600.0, H=1500.0, D=400.0, t=18.0, stagger=64.0):
    b = Builder('storage-rack', 'Storage rack', f'{bays}-bay, {levels}-level plywood rack; shelves of neighbouring '
                'bays are staggered so their screws never meet in the shared upright.', material=PLY(18),
                sheet={'width': 2440, 'height': 1220, 'spacing': 4})
    xs = [-(bays * (bay_w + t) + t) / 2 + i * (bay_w + t) for i in range(bays + 1)]
    for i, x in enumerate(xs):
        b.add(panel(f'UPRIGHT-{i + 1}', f'Upright {i + 1}', 'Uprights', [x, 0, -D / 2], [x + t, H, D / 2], grain='y'))
    pitch = (H - t) / (levels - 1)
    for k in range(bays):
        for lv in range(levels):
            y = min(max(lv * pitch + (stagger if k % 2 and 0 < lv < levels - 1 else 0.0), 0.0), H - t)
            sid = f'SHELF-{k + 1}-{lv + 1}'
            b.add(panel(sid, f'Shelf bay {k + 1} level {lv + 1}', 'Shelves', [xs[k] + t, y, -D / 2],
                        [xs[k + 1], y + t, D / 2], grain='x'))
            # Top and bottom shelves line up across bays: on every shared upright one side is dowelled with
            # staggered positions (confirmats from both faces would meet, and their heads be unreachable)
            aligned = k > 0 and not (0 < lv < levels - 1)
            b.butt(sid, '-x', f'UPRIGHT-{k + 1}', {'kind': 'dowel', 'end': 100, 'count': 2} if aligned else 'confirmat')
            b.butt(sid, '+x', f'UPRIGHT-{k + 2}', 'confirmat')
    return b


# ---------------------------------------------------------------------------
# 8. TV unit: four thicknesses / materials in one product
# ---------------------------------------------------------------------------

def tv_unit(W=1600.0, H=500.0, D=420.0):
    b = Builder('tv-unit', 'TV unit', 'Oak 25 mm top on an 18 mm particle-board carcass, 16 mm MDF doors, 6 mm back.')
    ch = H - 25
    b.add(panel('TOP', 'Top', 'Top', [-W / 2, ch, -D / 2 - 6], [W / 2, H, D / 2 + 20], material=OAK(25), grain='x'))
    b.add(panel('SIDE-L', 'Left side', 'Carcass', [-W / 2, 0, -D / 2], [-W / 2 + 18, ch, D / 2], grain='y'))
    b.add(panel('SIDE-R', 'Right side', 'Carcass', [W / 2 - 18, 0, -D / 2], [W / 2, ch, D / 2], grain='y'))
    b.add(panel('BOTTOM', 'Bottom', 'Carcass', [-W / 2 + 18, 0, -D / 2], [W / 2 - 18, 18, D / 2], grain='x'))
    xs = (-W / 6, W / 6)
    for i, x in enumerate(xs):
        b.add(panel(f'DIVIDER-{i + 1}', f'Divider {i + 1}', 'Carcass', [x - 9, 18, -D / 2], [x + 9, ch, D / 2], grain='y'))
        b.butt(f'DIVIDER-{i + 1}', '-y', 'BOTTOM', 'confirmat')
        b.butt(f'DIVIDER-{i + 1}', '+y', 'TOP', 'dowel')
    b.butt('BOTTOM', '-x', 'SIDE-L', 'confirmat')
    b.butt('BOTTOM', '+x', 'SIDE-R', 'confirmat')
    b.butt('SIDE-L', '+y', 'TOP', 'dowel')
    b.butt('SIDE-R', '+y', 'TOP', 'dowel')
    b.add(panel('BACK', 'Back panel', 'Back', [-W / 2, 0, -D / 2 - 6], [W / 2, ch, -D / 2], material=HB6))
    for p in ('SIDE-L', 'SIDE-R', 'BOTTOM', 'DIVIDER-1', 'DIVIDER-2'):
        b.butt(p, '-z', 'BACK', {'kind': 'screw', 'length': 25, 'diameter': 3.5})
    b.butt('BACK', '+y', 'TOP')   # back tucked under the overhanging top: glue line, held by the carcass screws
    # Outer compartments get one 16 mm MDF door each, hung on the sides
    z0 = D / 2 + 1.0
    b.add(panel('DOOR-L', 'Left door', 'Doors', [-W / 2 + 2, 2, z0], [xs[0] - 1.5, ch - 2, z0 + 16], material=MDF(16),
                grain='y'))
    b.add(panel('DOOR-R', 'Right door', 'Doors', [xs[1] + 1.5, 2, z0], [W / 2 - 2, ch - 2, z0 + 16], material=MDF(16),
                grain='y'))
    b.hinge('DOOR-L', '-x', 'SIDE-L', gap=2.0)
    b.hinge('DOOR-R', '+x', 'SIDE-R', gap=2.0)
    return b


# ---------------------------------------------------------------------------
# 9. Angled joints: mitred plant stand with an inclined shoe shelf
# ---------------------------------------------------------------------------

def mitred_stand(W=600.0, H=450.0, D=350.0, t=18.0, tilt=15.0):
    b = Builder('mitred-stand', 'Mitred stand', 'Top and legs joined by bevelled 45° mitres; inclined lower shelf.',
                material=PLY(18), sheet={'width': 2440, 'height': 1220, 'spacing': 4})
    xs, yt = W / 2 - t / 2, H - t / 2           # mid-plane corner line of the mitres
    b.add(panel('TOP', 'Top', 'Frame', [-xs, yt - t / 2, -D / 2], [xs, yt + t / 2, D / 2], grain='x'))
    b.add(panel('LEG-L', 'Left leg', 'Frame', [-xs - t / 2, 0, -D / 2], [-xs + t / 2, yt, D / 2], grain='y'))
    b.add(panel('LEG-R', 'Right leg', 'Frame', [xs - t / 2, 0, -D / 2], [xs + t / 2, yt, D / 2], grain='y'))
    b.mitre('TOP', '-x', 'LEG-L', '+y')
    b.mitre('TOP', '+x', 'LEG-R', '+y')
    # Inclined shelf between the legs, front edge lower (rotation about world X)
    inner = 2 * xs - t
    depth = D - 40
    b.add({'id': 'SHELF', 'name': 'Inclined shoe shelf', 'group': 'Shelves', 'outline': rect(inner, depth),
           'thickness': t, 'grain': 'x',
           'placement': {'position': [0, 150, 0], 'rotation': [-90 + tilt, 0, 0]}})
    b.butt('SHELF', '-x', 'LEG-L', 'dowel')
    b.butt('SHELF', '+x', 'LEG-R', 'dowel')
    return b


# ---------------------------------------------------------------------------
# 10. Complex intersecting structure: 3 x 3 cube storage
# ---------------------------------------------------------------------------

def cube_storage(n=3, cell=335.0, D=390.0, t=18.0, stagger=True):
    """Continuous outer box and horizontal shelves; dividers are short pieces between shelves. At every
    shelf the divider above and the one below meet the same spot from opposite faces, so their dowels are
    staggered (different end distances) — otherwise the bores would run into each other."""
    W = n * cell + (n + 1) * t
    b = Builder('cube-storage', 'Cube storage 3x3', '3 x 3 cube shelving with dowelled dividers between shelves.',
                material=PB18)
    carcass(b, W, W, D, back=False)
    xs = [-W / 2 + t + i * (cell + t) for i in range(n + 1)]          # left face of each vertical board
    ys = [t + i * (cell + t) for i in range(n)]                       # bottom of each cell
    for r in range(1, n):
        y = ys[r] - t
        b.add(panel(f'SHELF-{r}', f'Shelf {r}', 'Shelves', [-W / 2 + t, y, -D / 2], [W / 2 - t, y + t, D / 2], grain='x'))
        b.butt(f'SHELF-{r}', '-x', 'SIDE-L', 'confirmat')
        b.butt(f'SHELF-{r}', '+x', 'SIDE-R', 'confirmat')
    for r in range(n):
        below = 'BOTTOM' if r == 0 else f'SHELF-{r}'
        above = 'TOP' if r == n - 1 else f'SHELF-{r + 1}'
        for c in range(1, n):
            did = f'DIV-{r + 1}-{c}'
            x = xs[c] - t
            b.add(panel(did, f'Divider row {r + 1} / {c}', 'Dividers', [x, ys[r], -D / 2], [x + t, ys[r] + cell, D / 2],
                        grain='y'))
            # Odd rows: 2 dowels 70 mm from the ends; even rows: 3 dowels 37 mm from the ends (one at mid-depth),
            # so neighbouring rows never share a dowel axis
            f = {'kind': 'dowel', 'end': 70.0, 'count': 2} if (stagger and r % 2) else {'kind': 'dowel', 'end': 37.0, 'count': 3}
            b.butt(did, '-y', below, f)
            b.butt(did, '+y', above, f)
    return b


PRODUCTS = {'table': table, 'bookshelf': bookshelf, 'cabinet': cabinet, 'wardrobe': wardrobe, 'drawer': drawer,
            'l-desk': l_desk, 'storage-rack': storage_rack, 'tv-unit': tv_unit, 'mitred-stand': mitred_stand,
            'cube-storage': cube_storage}


def product_params(name):
    """Numeric parameters a product builder accepts (name -> default)."""
    import inspect
    return {k: v.default for k, v in inspect.signature(PRODUCTS[name]).parameters.items()
            if isinstance(v.default, (int, float)) and not isinstance(v.default, bool)}


def build(name, design_id=None, **params):
    b = PRODUCTS[name](**params)
    if design_id:
        b.design['id'] = design_id
    return b.build()
