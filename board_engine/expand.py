"""
Structure helpers of board-design/v1, expanded into plain boards and connections before compiling:

  "assemblies": [{"id", "boards": [...], "connections": [...]}] + "instances": [{"assembly", "id", "offset": [x, y, z],
      "repeat"?, "mirror"?}] -- a reusable sub-assembly; each instance's boards are "<instance>-<board id>".
  board "mirror": {"axis": "x"|"y"|"z", "at": mm} -- also build the mirror image across the plane axis = at ("<id>-M").
  board "repeat": {"count": 2 or more, "step": [dx, dy, dz]} -- an array of copies "<id>-1" .. "<id>-n".

Connections follow the copies: a connection naming a repeated board becomes one per copy (two repeated boards with
the same count pair up copy by copy); a mirrored board's connections are mirrored too ("+x" edges flip). `origin`
maps every generated id back to the id written in the source, so diagnostics still point at the right line.
"""
import copy

from .model import LIMITS

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
    if isinstance(b.get('rotate'), dict) and _vec3(b['rotate'].get('pivot')):
        b['rotate']['pivot'] = [b['rotate']['pivot'][i] + d[i] for i in range(3)]
    return b


def _thin_axis(b, t_default):
    t = b.get('thickness', t_default)
    if b.get('normal') in AX:
        return AX.index(b['normal'])
    thin = [i for i in range(3) if t is not None and abs(b['size'][i] - t) <= 0.01]
    return thin[0] if len(thin) == 1 else None


def _mirror_board(b, axis, at, t_default):
    """Mirror image of board b across the plane `axis` = at (face coordinates flipped where the axis lies in-plane)."""
    if b.get('rotate'):
        raise ExpandError(f"board '{b.get('id')}': tilted boards (\"rotate\") cannot be mirrored")
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
    return m


def _flip_dir(d, axis):
    return ('-' if d[0] == '+' else '+') + d[1:] if isinstance(d, str) and len(d) == 2 and d[1] == axis else d


def expand(data):
    """-> (expanded copy of data, origin {generated id: source id}). Raises ExpandError for an invalid helper."""
    if not any(k in data for k in ('assemblies', 'instances')) and not any(
            isinstance(b, dict) and (b.get('repeat') or b.get('mirror')) for b in data.get('boards') or []):
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
        for b in a.get('boards') or []:
            nb = _shift(b, off)
            nb['id'] = f"{inst['id']}-{b['id']}"
            nb.setdefault('group', inst['id'])
            for key in ('repeat', 'mirror'):
                if inst.get(key) and not nb.get(key):
                    nb[key] = inst[key]
            boards.append(nb)
            origin[nb['id']] = b['id']
        for c in a.get('connections') or []:
            nc = dict(c, board=f"{inst['id']}-{c.get('board')}", into=f"{inst['id']}-{c.get('into')}")
            if c.get('id'):
                nc['id'] = f"{inst['id']}-{c['id']}"
                origin[nc['id']] = c['id']
            if conns is None:
                conns = data['connections'] = []
            conns.append(nc)

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

    # 3. arrays
    copies, out = {}, []
    for b in boards:
        rp = b.pop('repeat', None)
        if rp is None:
            out.append(b)
            continue
        n, step = rp.get('count') if isinstance(rp, dict) else None, rp.get('step') if isinstance(rp, dict) else None
        if not (isinstance(n, int) and not isinstance(n, bool) and n >= 2 and _vec3(step)):
            raise ExpandError(f"board '{b.get('id')}': \"repeat\" must be {{\"count\": 2 or more, \"step\": [dx, dy, dz]}}")
        if len(out) + n > MAX_BOARDS:
            raise ExpandError(f"board '{b.get('id')}': \"repeat\" count {n} would make more than {MAX_BOARDS:,} boards")
        if not _vec3(b.get('position')):
            out.append(b)
            continue
        ids = []
        for k in range(n):
            nb = _shift(b, [step[i] * k for i in range(3)])
            nb['id'] = f"{b['id']}-{k + 1}"
            origin[nb['id']] = origin.get(b['id'], b['id'])
            ids.append(nb['id'])
            out.append(nb)
        copies[b['id']] = ids
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
