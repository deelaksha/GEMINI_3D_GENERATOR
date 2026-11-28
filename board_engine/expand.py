"""
Structure helpers of board-design/v1, expanded into plain boards and connections before compiling:

  "assemblies": [{"id", "boards": [...], "connections": [...], "motions"?: [...]}] + "instances": [{"assembly", "id",
      "offset": [x, y, z], "flip"?: axis or [axes], "rotate"?: step or [steps], "repeat"?, "mirror"?}] -- a reusable
      sub-assembly; each instance's boards are "<instance>-<board id>". Flips, then quarter turns, are exact (every
      board stays square, all joints work); other angles tilt the whole instance about its origin.
  board "mirror": {"axis": "x"|"y"|"z", "at": mm} -- also build the mirror image across the plane axis = at ("<id>-M").
  board "repeat": {"count": 2 or more, "step": [dx, dy, dz], "rows"?: {"count", "step"}, "layers"?: {"count", "step"},
      "grow"?: [dx, dy, dz]} -- an array of copies "<id>-1" .. "<id>-n" (a grid: "<id>-<row>-<n>", with layers
      "<id>-<layer>-<row>-<n>"); "grow" adds to the size of each next copy along the row (tapering segments, stepped
      tiers, graded fins - plain boards only).
  board "radial": {"count": 2 or more, "axis": "x"|"y"|"z", "center": [x, y, z], "sweep"?: degrees (default 360),
      "start"?: degrees} -- copies "<id>-1" .. "<id>-n" turned round the axis through the centre (spokes, petals, the
      ribs of a dome); multiples of 90 degrees are exact copies, other angles add a tilt step.
  connections may name many boards at once: "boards": [ids] instead of "board", and "*" / "?" wildcards in "board",
  "boards" or "into" ("SLAT-*" -> every board whose id matches) - see expand_connection_patterns().

Connections follow the copies: a connection naming a repeated board becomes one per copy (two repeated boards with
the same count pair up copy by copy); a mirrored board's connections are mirrored too ("+x" edges flip). `origin`
maps every generated id back to the id written in the source, so diagnostics still point at the right line.
"""
import copy
import math

from .model import LIMITS
from .shapes import ShapeError, shape_polygon

AX = ('x', 'y', 'z')
MAX_BOARDS = LIMITS['max_components']     # a guard against a runaway count, far above any real design


class ExpandError(ValueError):
    pass


def _vec3(v):
    return isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)


def _shift(b, d):
    b = copy.deepcopy(b)
    b['position'] = [b['position'][i] + d[i] for i in range(3)]
    for o in b.get('openings') or []:
        if _vec3(o.get('center')):
            o['center'] = [o['center'][i] + d[i] for i in range(3)]
    for st in (b['rotate'] if isinstance(b.get('rotate'), list) else [b.get('rotate')]):   # one tilt or a list of steps
        if isinstance(st, dict) and _vec3(st.get('pivot')):
            st['pivot'] = [st['pivot'][i] + d[i] for i in range(3)]
    mr, rd = b.get('mirror'), b.get('radial')
    if isinstance(mr, dict) and mr.get('axis') in AX and isinstance(mr.get('at'), (int, float)):
        mr['at'] = mr['at'] + d[AX.index(mr['axis'])]          # the mirror plane moves with the board
    if isinstance(rd, dict) and _vec3(rd.get('center')):
        rd['center'] = [rd['center'][i] + d[i] for i in range(3)]
    for key in (b.get('repeat') or {}).get('morph') or [] if isinstance(b.get('repeat'), dict) else []:
        for o in (key.get('openings') or []) if isinstance(key, dict) else []:
            if isinstance(o, dict) and _vec3(o.get('center')):
                o['center'] = [o['center'][i] + d[i] for i in range(3)]
    return b


def _map_morph(b, m, fn, lin):
    """The morph keys of b's repeat follow a turn, flip or mirror (b -> m by fn): each key section is mapped as a
    whole board, and where its corner lands relative to m's is added to its shift."""
    rp = m.get('repeat')
    if not (isinstance(rp, dict) and isinstance(rp.get('morph'), list) and all(isinstance(k, dict) for k in rp['morph'])):
        return m                                    # (a malformed morph is reported when the copies are made)
    cur, out = {k: v for k, v in b.items() if k not in ('repeat', 'radial', 'mirror')}, []
    cur['shift'] = [0, 0, 0]
    for key in rp['morph']:
        cur = {**cur, **key}
        if not (_vec3(cur['shift']) and _vec3(cur.get('size'))):
            return m
        mk = fn({f: v for f, v in cur.items() if f != 'shift'})
        s = lin(cur['shift'])
        out.append({**{f: mk[f] for f in key if f in ('size', 'profile', 'openings') and f in mk},
                    'shift': [s[i] + mk['position'][i] - m['position'][i] for i in range(3)]})
    rp['morph'] = out
    return m


def _thin_axis(b, t_default):
    t = b.get('thickness', t_default)
    if b.get('normal') in AX:
        return AX.index(b['normal'])
    thin = [i for i in range(3) if t is not None and abs(b['size'][i] - t) <= 0.01]
    return thin[0] if len(thin) == 1 else None


def _mirror_board(b, axis, at, t_default):
    """Mirror image of board b across the plane `axis` = at (face coordinates flipped where the axis lies in-plane)."""
    if b.get('rotate'):                 # a tilted board: flip it about the plane exactly (its tilt is mirrored too)
        a = AX.index(axis)
        return _shift(transform_board(b, flip_matrix(axis), t_default), [2 * at if i == a else 0.0 for i in range(3)])
    thin = _thin_axis(b, t_default)
    if thin is None:
        raise ExpandError(f"board '{b.get('id')}': cannot tell which size is its thickness, so it cannot be mirrored")
    m = copy.deepcopy(b)
    a = AX.index(axis)
    m['position'][a] = 2 * at - (b['position'][a] + b['size'][a])
    inplane = [i for i in range(3) if i != thin]
    k = inplane.index(a) if a in inplane else None          # which face coordinate (u = 0, v = 1) flips, if any
    span = b['size'][a]
    flip = lambda uv: [span - uv[0], uv[1]] if k == 0 else [uv[0], span - uv[1]] if k == 1 else list(uv)
    flip_rel = lambda uv: [-uv[0], uv[1]] if k == 0 else [uv[0], -uv[1]] if k == 1 else list(uv)

    def shape(s, rel):
        f = flip_rel if rel else flip
        if isinstance(s.get('points'), list):
            s['points'] = [f(q) for q in s['points']]
        if isinstance(s.get('center'), list) and len(s['center']) == 2:
            s['center'] = f(s['center'])
        for seg in s.get('segments') or []:
            for key in ('to', 'line', 'from'):
                if isinstance(seg.get(key), list) and len(seg[key]) == 2:
                    seg[key] = f(seg[key])
            arc = seg.get('arc')
            if isinstance(arc, dict):
                if isinstance(arc.get('to'), list):
                    arc['to'] = f(arc['to'])
                if k is not None:
                    arc['clockwise'] = not arc.get('clockwise', False)
    if isinstance(m.get('profile'), dict):
        shape(m['profile'], False)
    for o in m.get('openings') or []:
        if _vec3(o.get('center')):
            o['center'][a] = 2 * at - o['center'][a]
        shape(o, True)
    for e in m.get('engravings') or []:
        if e.get('text') is not None and isinstance(e.get('position'), list):
            e['position'] = flip(e['position'])     # the text stays readable: its anchor moves, the alignment flips
            if k == 0:
                e['align'] = {'left': 'right', 'right': 'left'}.get(e.get('align', 'left'), 'center')
        elif e.get('kind') == 'image' and isinstance(e.get('position'), list) and isinstance(e.get('size'), list):
            p = flip(e['position'])
            e['position'] = [p[0] - e['size'][0], p[1]] if k == 0 else [p[0], p[1] - e['size'][1]] if k == 1 else p
        else:
            shape(e, False)
    hinges = m.get('living_hinge')
    for h in (hinges if isinstance(hinges, list) else [hinges] if isinstance(hinges, dict) else []):
        for key in ('from', 'to'):
            if isinstance(h.get(key), list):
                h[key] = flip(h[key])
    rp = m.get('repeat')
    for part in (rp, rp.get('rows'), rp.get('layers')) if isinstance(rp, dict) else ():
        if isinstance(part, dict) and _vec3(part.get('step')):
            part['step'][a] = -part['step'][a]      # the mirrored row runs the other way
    return _map_morph(b, m, lambda x: _mirror_board(x, axis, at, t_default), lambda v: [-v[i] if i == a else v[i] for i in range(3)])


IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def _mat(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _apply(M, v):
    return [sum(M[i][k] * v[k] for k in range(3)) for i in range(3)]


def _det(M):
    return (M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1]) - M[0][1] * (M[1][0] * M[2][2] - M[1][2] * M[2][0])
            + M[0][2] * (M[1][0] * M[2][1] - M[1][1] * M[2][0]))


def quarter_turn(axis, angle):
    """Signed-permutation matrix of a turn by a multiple of 90 degrees about a world axis (right-handed, as "rotate")."""
    q = int(round(angle / 90.0)) % 4
    c, s = (1, 0, -1, 0)[q], (0, 1, 0, -1)[q]
    return {'x': ((1, 0, 0), (0, c, -s), (0, s, c)), 'y': ((c, 0, s), (0, 1, 0), (-s, 0, c)),
            'z': ((c, -s, 0), (s, c, 0), (0, 0, 1))}[axis]


def flip_matrix(axis):
    return tuple(tuple((-1 if i == j == AX.index(axis) else int(i == j)) for j in range(3)) for i in range(3))


def _axis_image(M, k):
    """M maps world axis k to (sign, axis)."""
    col = [M[i][k] for i in range(3)]
    j = next(i for i in range(3) if col[i])
    return col[j], j


def _map_dir(M, d):
    """An edge direction "+x" .. "-z" under M."""
    if not (isinstance(d, str) and len(d) == 2 and d[0] in '+-' and d[1] in AX):
        return d
    s, j = _axis_image(M, AX.index(d[1]))
    return ('+' if (s > 0) == (d[0] == '+') else '-') + AX[j]


def transform_board(b, M, t_default):
    """Board b turned / flipped by M (a product of quarter turns and flips) about the origin: an exact copy whose
    profile, openings, engravings, decals, hinges, edges, grain, tilt, repeat and mirror all follow. Shapes become
    polygons in the new face coordinates (curves keep their flattened points); circles stay circles."""
    if M == IDENTITY:
        return copy.deepcopy(b)
    if not (_vec3(b.get('position')) and _vec3(b.get('size'))):
        return copy.deepcopy(b)                     # its own error is reported by the compiler
    thin = _thin_axis(b, t_default)
    if thin is None:
        raise ExpandError(f"board '{b.get('id')}': cannot tell which size is its thickness, so it cannot be turned "
                          f"or flipped")
    for e in b.get('engravings') or []:
        if isinstance(e, dict) and e.get('kind') == 'image':
            raise ExpandError(f"board '{b.get('id')}': a raster image engraving cannot be turned or flipped; add it to "
                              f"the turned copy in the app instead")
    m = copy.deepcopy(b)
    lo = list(b['position'])
    hi = [lo[i] + b['size'][i] for i in range(3)]
    a, c = _apply(M, lo), _apply(M, hi)
    lo2 = [min(a[i], c[i]) for i in range(3)]
    m['position'] = lo2
    m['size'] = [abs(c[i] - a[i]) for i in range(3)]
    inplane = [i for i in range(3) if i != thin]
    thin2 = _axis_image(M, thin)[1]
    inplane2 = [i for i in range(3) if i != thin2]
    if m.get('normal') in AX:
        m['normal'] = AX[_axis_image(M, AX.index(m['normal']))[1]]

    def world(uv, relative=False):
        w = [0.0, 0.0, 0.0] if relative else list(lo)
        w[inplane[0]] += uv[0]
        w[inplane[1]] += uv[1]
        return w

    def face(uv, relative=False):
        """Face point (or, relative, a face vector) [u, v] -> the turned board's face coordinates."""
        w = _apply(M, world(uv, relative))
        return [round(w[inplane2[0]] - (0.0 if relative else lo2[inplane2[0]]), 6),
                round(w[inplane2[1]] - (0.0 if relative else lo2[inplane2[1]]), 6)]
    eu, ev = face([1, 0], True), face([0, 1], True)
    mirrored = eu[0] * ev[1] - eu[1] * ev[0] < 0     # the face mapping reverses the winding

    def shape(spec, relative=False):
        """A shape spec mapped to the new face coordinates (relative: around [0, 0], e.g. an opening's shape)."""
        if spec.get('shape') == 'circle':
            return dict(spec, center=face(spec.get('center') or [0, 0], relative))
        if spec.get('shape') == 'gear' and isinstance(spec.get('rotation', 0), (int, float)):
            # a gear stays a gear (its mesh is checked): its centre moves and tooth 0 keeps pointing the same way
            # in the world; the teeth are symmetric, so a mirrored gear is the same gear turned
            r = math.radians(spec.get('rotation', 0))
            du, dv = face([math.cos(r), math.sin(r)], True)
            return dict(spec, center=face(spec.get('center') or [0, 0], relative),
                        rotation=round(math.degrees(math.atan2(dv, du)), 6))
        src = dict(spec, center=[0.0, 0.0]) if relative else spec
        sz = spec.get('size')
        if relative and isinstance(sz, list) and len(sz) == 2:
            src['width'], src['height'] = sz
        try:
            pts, _arcs = shape_polygon(src, 'shape')
        except ShapeError as e:
            raise ExpandError(f"board '{b.get('id')}': {e}")
        pts = [face(q, relative) for q in pts]
        if mirrored:
            pts.reverse()
        keep = {k: spec[k] for k in ('id', 'kind', 'depth', 'note', 'color', 'face') if k in spec}
        return dict(keep, shape='polygon', points=pts)

    if isinstance(m.get('profile'), dict):
        m['profile'] = shape(b['profile'])
    if isinstance(b.get('openings'), list):
        m['openings'] = []
        for o in b['openings']:
            o2 = copy.deepcopy(o)
            if isinstance(o, dict):
                kind = o.get('shape', 'circle' if o.get('diameter') else 'rect')
                if kind not in ('circle', 'rect'):            # its shape is relative to the centre: map it as a vector
                    o2 = dict(shape(o, relative=True), **{k: o[k] for k in ('id', 'kind', 'note') if k in o})
                elif kind == 'rect' and isinstance(o.get('size'), list) and len(o['size']) == 2:
                    dims = {_axis_image(M, inplane[k])[1]: o['size'][k] for k in range(2)}
                    o2['size'] = [dims[inplane2[0]], dims[inplane2[1]]]
                if _vec3(o.get('center')):
                    o2['center'] = _apply(M, o['center'])
            m['openings'].append(o2)

    def text_centre(e, h):
        """[u, v] centre of an engraved text box (baseline start + align)."""
        from .strokefont import text_width
        w = text_width(e['text'], h)
        x0 = e['position'][0] - {'left': 0.0, 'center': 0.5, 'right': 1.0}.get(e.get('align', 'left'), 0.0) * w
        return [x0 + w / 2, e['position'][1] + 5 * h / 12]
    for k, e in enumerate(m.get('engravings') or []):
        if not isinstance(e, dict):
            continue
        if e.get('text') is not None and isinstance(e.get('position'), list):
            h = e.get('height', 5)
            cu, cv = face(text_centre(e, h))
            e.update(position=[round(cu, 4), round(cv - 5 * h / 12, 4)], align='center')
        elif e.get('shape'):
            m['engravings'][k] = shape(e)
        elif isinstance(e.get('points'), list):
            e['points'] = [face(q) for q in e['points']]
    for k, d in enumerate(m.get('decals') or []):
        if not isinstance(d, dict):
            continue
        if d.get('text') is not None and isinstance(d.get('position'), list):
            d['position'] = face(d['position'])                 # decal lettering is placed by its centre
        elif d.get('shape'):
            m['decals'][k] = shape(d)
    hinges = m.get('living_hinge')
    for h in (hinges if isinstance(hinges, list) else [hinges] if isinstance(hinges, dict) else []):
        if isinstance(h.get('from'), list) and isinstance(h.get('to'), list):
            f, t = face(h['from']), face(h['to'])
            h['from'], h['to'] = [min(f[0], t[0]), min(f[1], t[1])], [max(f[0], t[0]), max(f[1], t[1])]
            along = eu if h.get('lines_along', 'u') == 'u' else ev
            h['lines_along'] = 'u' if abs(along[0]) > abs(along[1]) else 'v'
    for e in m.get('edge_banding') or []:
        if isinstance(e, dict):
            e['edge'] = _map_dir(M, e.get('edge'))
    if m.get('grain') in AX:
        m['grain'] = AX[_axis_image(M, AX.index(m['grain']))[1]]
    det = _det(M)
    steps = m.get('rotate')
    for st in (steps if isinstance(steps, list) else [steps] if isinstance(steps, dict) else []):
        if st.get('axis') in AX:
            sgn, j = _axis_image(M, AX.index(st['axis']))
            st['axis'] = AX[j]
            if isinstance(st.get('angle'), (int, float)):
                st['angle'] = st['angle'] * sgn * det            # a turn about -k is the opposite turn about +k
        if _vec3(st.get('pivot')):
            st['pivot'] = _apply(M, st['pivot'])
    rp = m.get('repeat')
    if isinstance(rp, dict):
        for part in (rp, rp.get('rows'), rp.get('layers')):
            if isinstance(part, dict) and _vec3(part.get('step')):
                part['step'] = _apply(M, part['step'])
        if _vec3(rp.get('grow')):
            rp['grow'] = [abs(v) for v in _apply(M, rp['grow'])]       # sizes stay positive along the turned axes
    rd = m.get('radial')
    if isinstance(rd, dict):
        if _vec3(rd.get('center')):
            rd['center'] = _apply(M, rd['center'])
        if rd.get('axis') in AX:
            sgn, j = _axis_image(M, AX.index(rd['axis']))
            rd['axis'] = AX[j]
            flip = sgn * det
            for k in ('sweep', 'start'):
                if isinstance(rd.get(k), (int, float)):
                    rd[k] = rd[k] * flip
            if flip < 0 and 'sweep' not in rd:
                rd['sweep'] = -360
    mr = m.get('mirror')
    if isinstance(mr, dict) and mr.get('axis') in AX and isinstance(mr.get('at'), (int, float)):
        sgn, j = _axis_image(M, AX.index(mr['axis']))
        mr['axis'], mr['at'] = AX[j], sgn * mr['at']
    return _map_morph(b, m, lambda x: transform_board(x, M, t_default), lambda v: _apply(M, v))


def transform_connection(c, M):
    """A connection between two transformed boards: its edge directions follow."""
    c = dict(c)
    for key in ('edge', 'into_edge'):
        if key in c:
            c[key] = _map_dir(M, c[key])
    return c


def _count(part, what, bid, required=True):
    n, step = part.get('count') if isinstance(part, dict) else None, part.get('step') if isinstance(part, dict) else None
    if not (isinstance(n, int) and not isinstance(n, bool) and n >= (2 if required else 1) and _vec3(step)):
        raise ExpandError(f"board '{bid}': \"{what}\" must be {{\"count\": {2 if required else 1} or more, \"step\": [dx, dy, dz]}}")
    return n, step


def _repeat(b, rp, t_default):
    """Copies of b along a row (and rows / layers of rows), each next one in a row grown by "grow"."""
    bid = b.get('id')
    n, step = _count(rp, 'repeat', bid)
    rows = _count(rp['rows'], 'repeat.rows', bid, False) if 'rows' in rp else (1, [0, 0, 0])
    layers = _count(rp['layers'], 'repeat.layers', bid, False) if 'layers' in rp else (1, [0, 0, 0])
    grow, morph = rp.get('grow'), rp.get('morph')
    if grow is not None and (not _vec3(grow) or b.get('profile') or b.get('rotate')):
        raise ExpandError(f"board '{bid}': \"repeat.grow\" must be [dx, dy, dz] mm and works on plain boards only "
                          f"(no profile or tilt)")
    if morph is not None:
        if grow is not None or not (isinstance(morph, list) and morph and all(isinstance(m, dict) and m for m in morph)):
            raise ExpandError(f"board '{bid}': \"repeat.morph\" must be a list of key sections ({{\"size\"?, \"profile\"?, "
                              f"\"openings\"?, \"shift\"?}}) and cannot be combined with \"grow\"")
        keys = _morph_keys(b, morph, bid)
    if n * rows[0] * layers[0] > MAX_BOARDS:
        raise ExpandError(f"board '{bid}': \"repeat\" would make more than {MAX_BOARDS:,} boards")
    out = []
    for la in range(layers[0]):
        for r in range(rows[0]):
            for k in range(n):
                nb, d = b, [step[i] * k + rows[1][i] * r + layers[1][i] * la for i in range(3)]
                if morph is not None:
                    nb = {**b, **_morph_at(keys, k / (n - 1), bid)}
                    d = [a + c for a, c in zip(d, nb.pop('shift'))]
                nb = _shift(nb, d)
                if morph is not None:
                    nb = _whole_section(nb, t_default)
                if grow:
                    nb['size'] = [nb['size'][i] + grow[i] * k for i in range(3)]
                    if min(nb['size']) <= 0:
                        raise ExpandError(f"board '{bid}': \"repeat.grow\" shrinks copy {k + 1} to nothing")
                tag = [str(x + 1) for x, many in ((la, layers[0] > 1), (r, rows[0] > 1 or layers[0] > 1), (k, True)) if many]
                nb['id'] = f"{bid}-{'-'.join(tag)}"
                out.append(nb)
    return out


def _whole(tree, key='', snap=None):
    """Numbers to whole mm (an exponent to 0.01); face points [u, v] go through snap when it is given."""
    if isinstance(tree, dict):
        return {k: _whole(v, k, snap) for k, v in tree.items()}
    if isinstance(tree, list):
        if snap and key in ('points', 'center', 'to', 'line', 'from') and len(tree) == 2 and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) for v in tree):
            return snap(tree)
        return [_whole(v, key, snap) for v in tree]
    if isinstance(tree, float):
        return round(tree, 2) if key == 'exponent' else int(round(tree))
    return tree


def _whole_section(b, t_default):
    """A morphed section in whole mm: both box corners and the profile's points are rounded on the world grid (so the
    outline still meets its box, and turned and mirrored copies stay exact); the box grows the odd millimetre a
    rounded curve may need."""
    thin = _thin_axis(b, t_default)
    if thin is None:
        return _whole(b)                            # reported by the compiler
    lo0 = b['position']
    lo, hi = [round(v) for v in lo0], [round(p + q) for p, q in zip(lo0, b['size'])]
    u, v = (i for i in range(3) if i != thin)
    snap = lambda q: [round(lo0[u] + q[0]) - lo[u], round(lo0[v] + q[1]) - lo[v]]
    b = {**b, **_whole({f: b[f] for f in ('openings',) if f in b}), 'position': lo, 'size': [q - p for p, q in zip(lo, hi)]}
    if isinstance(b.get('profile'), dict):
        b['profile'] = _whole(b['profile'], snap=snap)
        try:
            pts = shape_polygon(b['profile'])[0]
        except ShapeError:
            return b                                # reported by the compiler
        for j, ax in enumerate((u, v)):
            b['size'][ax] = max(b['size'][ax], math.ceil(max(p[j] for p in pts) - 1e-6))
    return b


def _blend(trees, weights, path):
    """Weighted sum of JSON trees of the same shape: numbers are mixed, lists and objects element by element,
    anything else must be equal in every tree."""
    a = trees[0]
    if all(isinstance(t, (int, float)) and not isinstance(t, bool) for t in trees):
        return float(sum(w * t for w, t in zip(weights, trees)))
    if all(isinstance(t, list) for t in trees) and len({len(t) for t in trees}) == 1:
        return [_blend([t[i] for t in trees], weights, f'{path}[{i}]') for i in range(len(a))]
    if all(isinstance(t, dict) for t in trees) and len({frozenset(t) for t in trees}) == 1:
        return {k: _blend([t[k] for t in trees], weights, f'{path}.{k}') for k in a}
    if all(t == a for t in trees):
        return copy.deepcopy(a)
    raise ExpandError(f"{path}: the morph sections differ in shape here (same shape kind, same number of points / "
                      f"openings and the same keys in every section)")


def _morph_keys(b, morph, bid):
    """Key sections: the board itself first, then each morph entry; a field a key leaves out carries over."""
    fields = {f for m in morph for f in m}
    bad = fields - {'size', 'profile', 'openings', 'shift'}
    if bad:
        raise ExpandError(f"board '{bid}': \"repeat.morph\" can change size, profile, openings and shift, not {sorted(bad)}")
    keys = [{f: copy.deepcopy(b.get(f, [0, 0, 0] if f == 'shift' else None)) for f in fields}]
    for m in morph:
        keys.append({**keys[-1], **m})
    for f in fields:
        if any(k[f] is None for k in keys):
            raise ExpandError(f"board '{bid}': \"repeat.morph\" changes \"{f}\" but the board has none to start from")
    return keys


def _morph_at(keys, t, bid):
    """The section at fraction t of the way along: a smooth curve through the keys (uniform Catmull-Rom, ends
    held), straight between them when there are only two."""
    n = len(keys) - 1
    x = min(t * n, n - 1e-12)
    i, u = int(x), x - int(x)
    if n == 1:
        return _blend(keys, [1 - u, u], f"board '{bid}' morph")
    p = [keys[max(i - 1, 0)], keys[i], keys[i + 1], keys[min(i + 2, n)]]
    w = [(-u ** 3 + 2 * u ** 2 - u) / 2, (3 * u ** 3 - 5 * u ** 2 + 2) / 2, (-3 * u ** 3 + 4 * u ** 2 + u) / 2, (u ** 3 - u ** 2) / 2]
    return _blend(p, w, f"board '{bid}' morph")


def _radial(b, rd, t_default):
    """Copies of b turned round an axis through a centre: exact copies at multiples of 90 degrees, otherwise the
    turn is added as a tilt step about the centre."""
    bid = b.get('id')
    n, c = rd.get('count') if isinstance(rd, dict) else None, rd.get('center') if isinstance(rd, dict) else None
    sweep, start = (rd.get('sweep', 360), rd.get('start', 0)) if isinstance(rd, dict) else (None, None)
    if not (isinstance(n, int) and not isinstance(n, bool) and 2 <= n <= 720 and rd.get('axis') in AX and _vec3(c)
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (sweep, start)) and abs(sweep) <= 360):
        raise ExpandError(f"board '{bid}': \"radial\" must be {{\"count\": 2..720, \"axis\": \"x\"|\"y\"|\"z\", "
                          f"\"center\": [x, y, z], \"sweep\"?: degrees, \"start\"?: degrees}}")
    gap = sweep / n if abs(abs(sweep) - 360) < 1e-9 else sweep / (n - 1)
    own = b.get('rotate')
    own = own if isinstance(own, list) else [own] if isinstance(own, dict) else []
    out = []
    for k in range(n):
        ang = start + gap * k
        if abs(ang / 90.0 - round(ang / 90.0)) < 1e-9:
            M = quarter_turn(rd['axis'], ang)
            mc = _apply(M, c)
            nb = _shift(transform_board(b, M, t_default), [c[i] - mc[i] for i in range(3)])
        else:
            if len(own) >= 4:
                raise ExpandError(f"board '{bid}': a radial copy at {ang:g} degrees would need a 5th tilt step")
            nb = copy.deepcopy(b)
            nb['rotate'] = copy.deepcopy(own) + [{'axis': rd['axis'], 'angle': round(ang, 6), 'pivot': list(c)}]
        nb['id'] = f"{bid}-{k + 1}"
        out.append(nb)
    return out


def expand_connection_patterns(data):
    """Connections written for many boards at once: "boards": [ids] instead of "board", and "*" / "?" wildcards in
    "board", "boards" or "into". Many boards into one, one into many, or two equal lists paired in order.
    -> problems [(connection label, message)]."""
    from fnmatch import fnmatchcase
    conns = data.get('connections')
    if not isinstance(conns, list):
        return []
    ids = [b['id'] for b in data.get('boards') or [] if isinstance(b, dict) and isinstance(b.get('id'), str)]
    wild = lambda x: isinstance(x, str) and ('*' in x or '?' in x)
    pick = lambda x: [i for i in ids if fnmatchcase(i, x)] if wild(x) else [x]
    out, bad = [], []
    for c in conns:
        many = isinstance(c, dict) and isinstance(c.get('boards'), list)
        if not (isinstance(c, dict) and (many or wild(c.get('board')) or wild(c.get('into')))):
            out.append(c)
            continue
        label = c.get('id') or c.get('board') or 'connection'
        a = [i for x in (c['boards'] if many else [c.get('board')]) for i in pick(x)]
        b = pick(c.get('into'))
        if not a or not b:
            bad.append((label, f"no board matches {c.get('boards') if many else c.get('board')!r} / {c.get('into')!r}"))
            continue
        if len(a) > 1 and len(b) > 1 and len(a) != len(b):
            bad.append((label, f"{len(a)} boards into {len(b)} boards: give one side a single board, or equal counts"))
            continue
        pairs = list(zip(a, b)) if len(a) == len(b) else [(x, b[0]) for x in a] if len(b) == 1 else [(a[0], y) for y in b]
        base = {k: v for k, v in c.items() if k != 'boards'}
        for n, (x, y) in enumerate(pairs, 1):
            if x == y:
                continue
            nc = dict(base, board=x, into=y)
            if c.get('id'):
                nc['id'] = f"{c['id']}-{n}" if len(pairs) > 1 else c['id']
            out.append(nc)
    data['connections'] = out
    return bad


def _instance_transform(inst):
    """-> (M, tilt): an instance's "flip" ("x"|"y"|"z" or a list) then "rotate" (a step or a list) as an exact
    quarter-turn / flip matrix, plus tilt steps when some angle is not a multiple of 90 degrees (then the whole
    instance tilts about its origin; finger and cross-lap joints cannot follow a tilt)."""
    M = IDENTITY
    flips = inst.get('flip')
    for f in (flips if isinstance(flips, list) else [flips] if flips is not None else []):
        if f not in AX:
            raise ExpandError(f"instance '{inst['id']}': \"flip\" must be \"x\", \"y\" or \"z\" (or a list of them)")
        M = _mat(flip_matrix(f), M)
    rot = inst.get('rotate')
    steps = rot if isinstance(rot, list) else [rot] if rot is not None else []
    for st in steps:
        if not (isinstance(st, dict) and st.get('axis') in AX and isinstance(st.get('angle'), (int, float))
                and not isinstance(st.get('angle'), bool) and -360 <= st['angle'] <= 360
                and (st.get('pivot') is None or _vec3(st['pivot']))):
            raise ExpandError(f"instance '{inst['id']}': \"rotate\" must be {{\"axis\": \"x\"|\"y\"|\"z\", \"angle\": "
                              f"degrees}} or a list of them")
    if all(abs(st['angle'] / 90.0 - round(st['angle'] / 90.0)) < 1e-9 and st.get('pivot') is None for st in steps):
        for st in steps:
            M = _mat(quarter_turn(st['axis'], st['angle']), M)
        return M, []
    return M, [{k: st[k] for k in ('axis', 'angle', 'pivot') if k in st} for st in steps]


def _instance_motion(mo, iid, M, off, origin):
    """An assembly's motion for one instance: its boards renamed, its pivot / axis / direction turned with it."""
    mo = copy.deepcopy(mo)
    for k in ('id',):
        if isinstance(mo.get(k), str):
            origin[f"{iid}-{mo[k]}"] = mo[k]
            mo[k] = f"{iid}-{mo[k]}"
    if isinstance(mo.get('boards'), list):
        mo['boards'] = [f"{iid}-{b}" for b in mo['boards']]
    if isinstance(mo.get('on'), str):
        mo['on'] = f"{iid}-{mo['on']}"
    if isinstance(mo.get('driven_by'), str):
        mo['driven_by'] = f"{iid}-{mo['driven_by']}"
    if isinstance(mo.get('axle'), dict) and isinstance(mo['axle'].get('boards'), list):
        mo['axle']['boards'] = [f"{iid}-{b}" for b in mo['axle']['boards']]
    if _vec3(mo.get('pivot')):
        mo['pivot'] = [v + off[i] for i, v in enumerate(_apply(M, mo['pivot']))]
    lk = mo.get('link')
    if isinstance(lk, dict):
        if isinstance(lk.get('rod'), str):
            lk['rod'] = f"{iid}-{lk['rod']}"
        for k in ('from', 'to'):
            if _vec3(lk.get(k)):
                lk[k] = [v + off[i] for i, v in enumerate(_apply(M, lk[k]))]
    key = 'axis' if mo.get('type') == 'rotate' else 'direction'
    if mo.get(key) in AX:
        sgn, j = _axis_image(M, AX.index(mo[key]))
        mo[key] = AX[j]
        flip = sgn * (_det(M) if key == 'axis' else 1)      # a turn about -k / a slide along -k runs the other way
        rng = mo.get('range')
        if flip < 0 and isinstance(rng, list) and len(rng) == 2 and all(isinstance(v, (int, float)) for v in rng):
            mo['range'] = [-rng[1], -rng[0]]
    return mo


def _flip_dir(d, axis):
    return ('-' if d[0] == '+' else '+') + d[1:] if isinstance(d, str) and len(d) == 2 and d[1] == axis else d


def expand(data):
    """-> (expanded copy of data, origin {generated id: source id}). Raises ExpandError for an invalid helper."""
    if not any(k in data for k in ('assemblies', 'instances')) and not any(
            isinstance(b, dict) and (b.get('repeat') or b.get('mirror') or b.get('radial')) for b in data.get('boards') or []):
        return data, {}
    data = copy.deepcopy(data)
    t_default = (data.get('material') or {}).get('thickness')
    boards = [b for b in data.get('boards') or [] if isinstance(b, dict)]
    conns = data.get('connections') if isinstance(data.get('connections'), list) else None
    origin = {}

    # 1. sub-assemblies
    asm = {a.get('id'): a for a in data.pop('assemblies', None) or [] if isinstance(a, dict)}
    for inst in data.pop('instances', None) or []:
        if not isinstance(inst, dict) or inst.get('assembly') not in asm or not isinstance(inst.get('id'), str):
            raise ExpandError('every instance needs "id" and "assembly" naming one of "assemblies"')
        off = inst.get('offset', [0, 0, 0])
        if not _vec3(off):
            raise ExpandError(f"instance '{inst['id']}': \"offset\" must be [x, y, z] mm")
        a = asm[inst['assembly']]
        M, tilt = _instance_transform(inst)
        for b in a.get('boards') or []:
            nb = _shift(transform_board(b, M, t_default), off)
            if tilt:                            # any other angle: the whole instance tilts about its origin
                own = nb.get('rotate')
                own = own if isinstance(own, list) else [own] if isinstance(own, dict) else []
                if len(own) + len(tilt) > 4:
                    raise ExpandError(f"instance '{inst['id']}': board '{b.get('id')}' would get more than 4 tilt steps")
                nb['rotate'] = own + [dict(st, pivot=[off[i] + (st.get('pivot') or [0, 0, 0])[i] for i in range(3)])
                                      for st in tilt]
            nb['id'] = f"{inst['id']}-{b['id']}"
            nb.setdefault('group', inst['id'])
            for key in ('repeat', 'mirror'):
                if inst.get(key) and not nb.get(key):
                    nb[key] = inst[key]
            boards.append(nb)
            origin[nb['id']] = b['id']
        for c in a.get('connections') or []:
            nc = dict(transform_connection(c, M), board=f"{inst['id']}-{c.get('board')}", into=f"{inst['id']}-{c.get('into')}")
            if c.get('id'):
                nc['id'] = f"{inst['id']}-{c['id']}"
                origin[nc['id']] = c['id']
            if conns is None:
                conns = data['connections'] = []
            conns.append(nc)
        for mo in a.get('motions') or []:      # each copy of the assembly gets its own working motion
            if not isinstance(mo, dict):
                continue
            if tilt:
                raise ExpandError(f"instance '{inst['id']}': its assembly has motions, so it can only be turned by "
                                  f"multiples of 90 degrees")
            data.setdefault('motions', []).append(_instance_motion(mo, inst['id'], M, off, origin))

    # 2. mirror images
    out = []
    for b in boards:
        out.append(b)
        mr = b.pop('mirror', None)
        if mr is None:
            continue
        if not (isinstance(mr, dict) and mr.get('axis') in AX and isinstance(mr.get('at'), (int, float))):
            raise ExpandError(f"board '{b.get('id')}': \"mirror\" must be {{\"axis\": \"x\"|\"y\"|\"z\", \"at\": mm}}")
        if not (_vec3(b.get('position')) and _vec3(b.get('size'))):
            continue                                # the board's own error is reported by the compiler
        m = _mirror_board(b, mr['axis'], mr['at'], t_default)
        m['id'] = f"{b['id']}-M"
        out.append(m)
        origin[m['id']] = origin.get(b['id'], b['id'])
        if conns:
            for c in list(conns):
                if b['id'] in (c.get('board'), c.get('into')):
                    nc = dict(c, board=m['id'] if c.get('board') == b['id'] else c.get('board'),
                              into=m['id'] if c.get('into') == b['id'] else c.get('into'))
                    for key in ('edge', 'into_edge'):
                        if key in nc:
                            nc[key] = _flip_dir(nc[key], mr['axis'])
                    if c.get('id'):
                        nc['id'] = f"{c['id']}-M"
                        origin[nc['id']] = origin.get(c['id'], c['id'])
                    conns.append(nc)
    boards = out

    # 3. arrays (rows, grids, graded rows) and radial copies
    copies, out = {}, []
    for b in boards:
        rp, rd = b.pop('repeat', None), b.pop('radial', None)
        if rp is None and rd is None:
            out.append(b)
            continue
        if rp is not None and rd is not None:
            raise ExpandError(f"board '{b.get('id')}': use \"repeat\" or \"radial\", not both (put one of them on an assembly instance)")
        if not _vec3(b.get('position')):
            out.append(b)
            continue
        made = _repeat(b, rp, t_default) if rp is not None else _radial(b, rd, t_default)
        if len(out) + len(made) > MAX_BOARDS:
            raise ExpandError(f"board '{b.get('id')}': its copies would make more than {MAX_BOARDS:,} boards")
        for nb in made:
            origin[nb['id']] = origin.get(b['id'], b['id'])
        out += made
        copies[b['id']] = [nb['id'] for nb in made]
    if len(out) > MAX_BOARDS:
        raise ExpandError(f'the structure expands to {len(out):,} boards, more than the {MAX_BOARDS:,} the server accepts')
    if copies and conns:
        new = []
        for c in conns:
            ca, cb = copies.get(c.get('board')), copies.get(c.get('into'))
            if not ca and not cb:
                new.append(c)
                continue
            if ca and cb and len(ca) != len(cb):
                raise ExpandError(f"connection '{c.get('id') or c.get('board')}': both boards repeat, with different counts")
            n = len(ca or cb)
            for k in range(n):
                nc = dict(c, board=ca[k] if ca else c.get('board'), into=cb[k] if cb else c.get('into'))
                if c.get('id'):
                    nc['id'] = f"{c['id']}-{k + 1}"
                    origin[nc['id']] = origin.get(c['id'], c['id'])
                new.append(nc)
        data['connections'] = new
    data['boards'] = out
    return data, origin
