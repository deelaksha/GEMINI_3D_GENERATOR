"""
Board consolidation: many small flat pieces that lie in one plane and touch each other (fence posts and their rail,
the bars of a lattice window, the slats of a panel) are cut as ONE board instead - the same outline, the gaps
between them kept as cut-out openings - and the connections between them disappear.

    "consolidate": false         (top level; on by default - with false the compiler only reports what it would merge)

A group is merged when its boards are flat (not tilted), of the same thickness, material, colour and grain, in the
same plane, static (no motion moves them), and joined edge to edge into one piece. Plain rectangles are united
exactly (a rectilinear outline); shaped boards ("profile": arches, pickets, curves, silhouettes) are united with
shapely, curves as the fine polylines they are cut with. Enclosed gaps become openings. Connections between members
are dropped; connections and motion mounts from outside are moved to the merged board.
"""
import copy
import json
import re

AX = 'xyz'
EPS = 0.01                  # mm: edges this close touch
MAX_CELLS = 250_000         # grid cells of one union (beyond this the group is left as it is, with the reason)
SAFE_KEYS = {'id', 'name', 'group', 'position', 'size', 'thickness', 'material', 'grain', 'color', 'openings',
             'engravings', 'decals', 'note', 'description', 'profile'}
CONTACT = 1.0               # mm: shaped pieces must share at least this much edge (not just a corner) to be one board
BOARD_KEYS = ('board', 'from', 'a', 'board_a', 'source', 'part', 'child', 'tab_board')
INTO_KEYS = ('into', 'to', 'b', 'board_b', 'target', 'receiver', 'parent', 'onto', 'slot_board')


def _vec3(v):
    return isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)


def _thin(b, t_default):
    t = b.get('thickness', t_default)
    thin = [i for i in range(3) if t is not None and abs(b['size'][i] - t) <= EPS]
    return thin[0] if len(thin) == 1 else None


def _moving_boards(data, origin):
    names = set()
    for m in data.get('motions') or []:
        if isinstance(m, dict):
            names.update(n for n in m.get('boards') or [] if isinstance(n, str))
            rod = (m.get('link') or {}).get('rod') if isinstance(m.get('link'), dict) else None
            if isinstance(rod, str):
                names.add(rod)
    return names | {gen for gen, src in (origin or {}).items() if src in names}


def _why_not(b, t_default, moving):
    if not (isinstance(b, dict) and isinstance(b.get('id'), str) and _vec3(b.get('position')) and _vec3(b.get('size'))):
        return 'not a plain board'
    if b['id'] in moving:
        return 'it moves (a motion)'
    extra = set(b) - SAFE_KEYS
    if extra:
        return f"it has {', '.join(sorted(extra))} (shaped, tilted or special boards stay separate)"
    if _thin(b, t_default) is None:
        return 'its thin side is not clear'
    if isinstance(b.get('profile'), dict) and b['profile'].get('shape') == 'gear':
        return 'it is a gear'
    return None


def _shape(b, i, j):
    """The board's outline in plane coordinates (axes i, j): None for a plain rectangle, a shapely Polygon for a
    profile, or a string saying why it cannot be used."""
    prof = b.get('profile')
    if prof is None:
        return None
    try:
        from shapely.geometry import Polygon
    except ImportError:
        return 'shaped boards need the shapely package to be merged'
    from .shapes import ShapeError, shape_polygon
    try:
        pts = shape_polygon(prof)[0]
    except (ShapeError, TypeError, ValueError, KeyError, IndexError):
        return 'its profile is invalid'
    poly = Polygon([(b['position'][i] + p[0], b['position'][j] + p[1]) for p in pts])
    if not poly.is_valid or poly.area <= 0:
        return 'its profile is invalid'
    return poly


def _touch(a, b, i, j):
    """Rectangles a, b = (u0, v0, u1, v1) share an edge (not only a corner) or overlap."""
    du = min(a[2], b[2]) - max(a[0], b[0])
    dv = min(a[3], b[3]) - max(a[1], b[1])
    return (du > EPS and dv > -EPS) or (dv > EPS and du > -EPS)


def _union(rects):
    """Exact union of axis-aligned rectangles -> (outer loop, [hole loops]) as lists of [u, v] (outer counter-
    clockwise, holes clockwise), or (None, reason)."""
    us = sorted({r[0] for r in rects} | {r[2] for r in rects})
    vs = sorted({r[1] for r in rects} | {r[3] for r in rects})
    nu, nv = len(us) - 1, len(vs) - 1
    if nu * nv > MAX_CELLS:
        return None, f"too detailed to merge exactly ({nu * nv} grid cells)"
    ui = {u: k for k, u in enumerate(us)}
    vi = {v: k for k, v in enumerate(vs)}
    cov = [[False] * nv for _ in range(nu)]
    for r in rects:
        for a in range(ui[r[0]], ui[r[2]]):
            col = cov[a]
            for c in range(vi[r[1]], vi[r[3]]):
                col[c] = True
    on = lambda a, c: 0 <= a < nu and 0 <= c < nv and cov[a][c]
    for a in range(nu - 1):                        # two cells touching only at a corner: no valid single outline
        for c in range(nv - 1):
            if on(a, c) == on(a + 1, c + 1) != on(a + 1, c) == on(a, c + 1):
                return None, 'its pieces meet only at a corner somewhere'
    # directed boundary edges with the material on the left (counter-clockwise outside, clockwise around holes)
    nxt = {}
    for a in range(nu):
        for c in range(nv):
            if not cov[a][c]:
                continue
            if not on(a, c - 1):
                nxt[(a, c)] = (a + 1, c)
            if not on(a + 1, c):
                nxt[(a + 1, c)] = (a + 1, c + 1)
            if not on(a, c + 1):
                nxt[(a + 1, c + 1)] = (a, c + 1)
            if not on(a - 1, c):
                nxt[(a, c + 1)] = (a, c)
    loops = []
    while nxt:
        start = next(iter(nxt))
        loop, p = [], start
        while True:
            loop.append(p)
            p = nxt.pop(p)
            if p == start:
                break
        pts = [[us[a], vs[c]] for a, c in loop]
        keep = [pts[k] for k in range(len(pts))           # drop points in the middle of a straight run
                if (pts[k - 1][0] - pts[k][0]) * (pts[(k + 1) % len(pts)][1] - pts[k][1])
                != (pts[k - 1][1] - pts[k][1]) * (pts[(k + 1) % len(pts)][0] - pts[k][0])]
        area = sum(keep[k][0] * keep[(k + 1) % len(keep)][1] - keep[(k + 1) % len(keep)][0] * keep[k][1]
                   for k in range(len(keep))) / 2
        loops.append((area, keep))
    outer = [lp for ar, lp in loops if ar > 0]
    if len(outer) != 1:
        return None, 'its pieces do not form one connected board'
    return outer[0], [lp for ar, lp in loops if ar < 0]


def _shift_shape(s, du, dv):
    """A face-coordinate shape / engraving / decal moved by (du, dv)."""
    s = copy.deepcopy(s)
    mv = lambda p: [p[0] + du, p[1] + dv] if isinstance(p, list) and len(p) == 2 else p
    for k in ('center', 'position', 'start'):
        if k in s:
            s[k] = mv(s[k])
    if isinstance(s.get('points'), list):
        s['points'] = [mv(p) for p in s['points']]
    for seg in s.get('segments') or []:
        for kind in ('line', 'arc'):
            if kind == 'line' and isinstance(seg, dict) and 'line' in seg:
                seg['line'] = mv(seg['line'])
            elif kind == 'arc' and isinstance(seg, dict) and isinstance(seg.get('arc'), dict):
                for k in ('to', 'center'):
                    if k in seg['arc']:
                        seg['arc'][k] = mv(seg['arc'][k])
    return s


def _splits_repeat(members, families):
    ids = {b['id'] for b in members}
    for b in members:
        m = re.match(r'^(.*)-\d+$', b['id'])
        fam = families.get(m.group(1)) if m else None
        if fam and len(fam) > 1 and not fam <= ids:
            return m.group(1)
    return None


def _name(members, taken):
    ids = [b['id'] for b in members]
    pre = ids[0]
    for x in ids[1:]:
        while not x.startswith(pre):
            pre = pre[:-1]
    pre = re.sub(r'[-_.0-9]+$', '', pre) or re.sub(r'[-_.0-9]+$', '', ids[0]) or ids[0]
    base = pre[:17] + '-PANEL'
    name, n = base, 2
    while name in taken:
        name, n = f"{base}-{n}", n + 1
    return name


def _poly(r, shape):
    from shapely.geometry import box
    return shape if shape is not None else box(*r)


def _shaped_union(polys):
    """-> (outer loop, [hole loops]) of the union of shapely polygons, or (None, reason)."""
    from shapely.geometry import Polygon
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union
    u = unary_union(polys)
    if u.geom_type != 'Polygon':                      # pieces that only just touch: close the hairline seams
        u = u.buffer(EPS, join_style=2).buffer(-EPS, join_style=2)
    if u.geom_type != 'Polygon':
        return None, 'its pieces do not form one connected board'
    u = orient(u.simplify(1e-4, preserve_topology=True), 1.0)
    loop = lambda ring: [[x, y] for x, y in list(ring.coords)[:-1]]
    return loop(u.exterior), [loop(r) for r in u.interiors if Polygon(r).area > EPS]


def _merged(members, k, t, name, shapes=None):
    i, j = [x for x in range(3) if x != k]
    rects = [(b['position'][i], b['position'][j], b['position'][i] + b['size'][i], b['position'][j] + b['size'][j])
             for b in members]
    shapes = shapes or [None] * len(members)
    if all(s is None for s in shapes):
        outer, holes = _union(rects)
    else:
        outer, holes = _shaped_union([_poly(r, s) for r, s in zip(rects, shapes)])
    if outer is None:
        return None, holes
    u0, v0 = min(p[0] for p in outer), min(p[1] for p in outer)
    u1, v1 = max(p[0] for p in outer), max(p[1] for p in outer)
    first = members[0]
    pos = [0.0, 0.0, 0.0]
    pos[i], pos[j], pos[k] = u0, v0, first['position'][k]
    size = [0.0, 0.0, 0.0]
    size[i], size[j], size[k] = u1 - u0, v1 - v0, first['size'][k]
    out = {'id': name, **{key: first[key] for key in ('name', 'group', 'thickness', 'material', 'grain', 'color')
                          if key in first}, 'position': pos, 'size': size}
    if len(outer) != 4 or {(round(p[0], 6), round(p[1], 6)) for p in outer} != {(u0, v0), (u1, v0), (u1, v1), (u0, v1)}:
        out['profile'] = {'shape': 'polygon', 'points': [[round(p[0] - u0, 4), round(p[1] - v0, 4)] for p in outer]}
    openings = []
    for n, hole in enumerate(holes, 1):
        hu, hv = min(p[0] for p in hole), min(p[1] for p in hole)
        c = [0.0, 0.0, 0.0]
        c[i], c[j], c[k] = hu, hv, first['position'][k] + first['size'][k] / 2
        if len(hole) == 4 and len({round(p[0], 6) for p in hole}) == 2 and len({round(p[1], 6) for p in hole}) == 2:
            w, h = max(p[0] for p in hole) - hu, max(p[1] for p in hole) - hv
            c[i], c[j] = hu + w / 2, hv + h / 2
            openings.append({'id': f'gap-{n}', 'kind': 'opening', 'shape': 'rect', 'center': c, 'size': [w, h]})
        else:
            openings.append({'id': f'gap-{n}', 'kind': 'opening', 'shape': 'polygon', 'center': c,
                             'points': [[p[0] - hu, p[1] - hv] for p in reversed(hole)]})
    for b in members:                                  # what the pieces carried comes along
        du, dv = b['position'][i] - u0, b['position'][j] - v0
        openings += [dict(o, id=f"{b['id']}-{o.get('id', 'o')}") for o in b.get('openings') or [] if isinstance(o, dict)]
        for key in ('engravings', 'decals'):
            for s in b.get(key) or []:
                if isinstance(s, dict):
                    out.setdefault(key, []).append(dict(_shift_shape(s, du, dv), **({'id': f"{b['id']}-{s['id']}"}
                                                                                   if 'id' in s else {})))
    if openings:
        out['openings'] = openings
    return out, None


def plan(data, t_default, origin=None):
    """-> (groups [(merged board, member ids)], skipped [(member ids, reason)]) without changing anything."""
    boards = [b for b in data.get('boards') or [] if isinstance(b, dict)]
    moving = _moving_boards(data, origin)
    taken = {b.get('id') for b in boards}
    buckets = {}
    for b in boards:
        if _why_not(b, t_default, moving):
            continue
        k = _thin(b, t_default)
        key = (k, round(b['position'][k], 3), round(b['size'][k], 3),
               json.dumps([b.get(x) for x in ('material', 'color', 'grain')], sort_keys=True))
        buckets.setdefault(key, []).append(b)
    families = {}                                      # repeated boards: "<id>-1".."<id>-n" (all copies or none)
    for b in boards:
        if b.get('id') in (origin or {}):
            m = re.match(r'^(.*)-\d+$', b['id'])
            if m:
                families.setdefault(m.group(1), set()).add(b['id'])
    groups, skipped = [], []
    for (k, *_rest), bs in buckets.items():
        if len(bs) < 2:
            continue
        i, j = [x for x in range(3) if x != k]
        rect = [(b['position'][i], b['position'][j], b['position'][i] + b['size'][i], b['position'][j] + b['size'][j])
                for b in bs]
        shape = [_shape(b, i, j) for b in bs]
        for x in range(len(bs)):
            if isinstance(shape[x], str):
                skipped.append(([bs[x]['id']], shape[x]))
        live = [x for x in range(len(bs)) if not isinstance(shape[x], str)]
        parent = list(range(len(bs)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        order = sorted(live, key=lambda x: rect[x][0])
        for a_ix, a in enumerate(order):                # sweep along u: only rectangles whose u ranges meet
            for b in order[a_ix + 1:]:
                if rect[b][0] > rect[a][2] + EPS:
                    break
                if not _touch(rect[a], rect[b], i, j):
                    continue
                if shape[a] is not None or shape[b] is not None:   # shaped: the outlines themselves must share an edge
                    pa, pb = _poly(rect[a], shape[a]), _poly(rect[b], shape[b])
                    if pa.buffer(EPS).intersection(pb).area <= EPS * CONTACT:
                        continue
                parent[find(a)] = find(b)
        comp, shape_of = {}, {}
        for x in live:
            comp.setdefault(find(x), []).append(bs[x])
            shape_of[bs[x]['id']] = shape[x]
        for members in comp.values():
            if len(members) < 2:
                continue
            split = _splits_repeat(members, families)
            if split:
                skipped.append(([b['id'] for b in members], f"it would take only some copies of the repeated board '{split}'"))
                continue
            members.sort(key=lambda b: (b['position'][j], b['position'][i]))
            name = _name(members, taken)
            merged, why = _merged(members, k, t_default, name, [shape_of[b['id']] for b in members])
            if merged is None:
                skipped.append(([b['id'] for b in members], why))
                continue
            taken.add(name)
            groups.append((merged, [b['id'] for b in members]))
    return groups, skipped


def apply(data, groups):
    """Replace each group's boards by its merged board; drop connections inside a group and move the others (and
    motion mounts) to the merged board. -> number of connections removed."""
    to = {m: g['id'] for g, members in groups for m in members}
    first = {members[0]: g for g, members in groups}
    out = []
    for b in data.get('boards') or []:
        bid = b.get('id') if isinstance(b, dict) else None
        if bid in first:
            out.append(first[bid])
        elif bid not in to:
            out.append(b)
    data['boards'] = out
    removed, conns, first_ids = 0, data.get('connections'), set(to.values())
    if isinstance(conns, list):
        kept, seen = [], set()
        for c in conns:
            if not isinstance(c, dict):
                kept.append(c)
                continue
            ka = next((k for k in BOARD_KEYS if isinstance(c.get(k), str)), None)
            kb = next((k for k in INTO_KEYS if isinstance(c.get(k), str)), None)
            a, b = (to.get(c[ka], c[ka]) if ka else None), (to.get(c[kb], c[kb]) if kb else None)
            if a is not None and a == b:
                removed += 1                            # both ends are now one board
                continue
            c = dict(c, **({ka: a} if ka else {}), **({kb: b} if kb else {}))
            sig = (c.get('type', 'tab_slot'), a, b)
            if sig in seen and (a in first_ids or b in first_ids):
                removed += 1                            # the same joint again, now between the same two boards
                continue
            seen.add(sig)
            kept.append(c)
        data['connections'] = kept
    for m in data.get('motions') or []:
        if isinstance(m, dict) and m.get('on') in to:
            m['on'] = to[m['on']]
    return removed


def repeat_openings(data):
    """Expand openings written once with "repeat": {"count": n, "step": [dx, dy, dz]} (and "rows": {"count": m,
    "step": [...]} for a grid) into every copy - the gaps of a 30-picket fence or a lattice window in one line.
    -> problems [(board id, message)]."""
    bad = []
    ok = lambda r: isinstance(r, dict) and isinstance(r.get('count'), int) and 1 <= r['count'] <= 500 and _vec3(r.get('step'))
    for b in data.get('boards') or []:
        if not isinstance(b, dict) or not isinstance(b.get('openings'), list):
            continue
        out = []
        for o in b['openings']:
            if not (isinstance(o, dict) and ('repeat' in o or 'rows' in o)):
                out.append(o)
                continue
            rep, rows = o.get('repeat', {'count': 1, 'step': [0, 0, 0]}), o.get('rows', {'count': 1, 'step': [0, 0, 0]})
            if not (ok(rep) and ok(rows) and _vec3(o.get('center'))) or rep['count'] * rows['count'] > 5000:
                bad.append((b.get('id'), f"opening '{o.get('id', '?')}': \"repeat\" / \"rows\" must be {{\"count\": 1..500, "
                                         f"\"step\": [dx, dy, dz]}} (at most 5000 copies) with a \"center\"."))
                continue
            base = {k: v for k, v in o.items() if k not in ('repeat', 'rows')}
            for r in range(rows['count']):
                for c in range(rep['count']):
                    centre = [o['center'][x] + c * rep['step'][x] + r * rows['step'][x] for x in range(3)]
                    tag = f"{c + 1}" if rows['count'] == 1 else f"{r + 1}-{c + 1}"
                    out.append(dict(base, id=f"{o.get('id', 'opening')}-{tag}", center=centre))
        b['openings'] = out
    return bad


def consolidate(data, t_default, origin=None, do=False):
    """-> report {'boards_before', 'boards_after', 'groups': [...], 'skipped': [...], 'connections_removed', 'applied'}.
    With do=True the merge is made in `data`."""
    before = len(data.get('boards') or [])
    groups, skipped = plan(data, t_default, origin)
    removed = apply(data, groups) if do and groups else 0
    merged = sum(len(m) for _g, m in groups)
    return {'applied': bool(do and groups), 'boards_before': before, 'boards_after': before - merged + len(groups),
            'connections_removed': removed,
            'groups': [{'board': g['id'], 'from': m, 'openings': len([o for o in g.get('openings') or []
                                                                      if str(o.get('id', '')).startswith('gap-')])}
                       for g, m in groups],
            'skipped': [{'boards': ids, 'reason': why} for ids, why in skipped]}
