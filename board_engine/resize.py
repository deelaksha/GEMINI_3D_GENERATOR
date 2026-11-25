"""
Parametric resize of a board-design/v1 design: new overall length / height / depth without asking the AI again.

Along each axis, the stretches that are a board's thickness stay rigid and only the space between them stretches,
so every board keeps its thickness and every pair of touching faces still touches (they share an edge, and edges are
mapped by one monotonic function). Positions and sizes come out in whole millimetres (thicknesses stay exact).
Face coordinates (profiles, engravings, text, images, living hinges) and opening centres are mapped through the same
function; hole and opening sizes, text height and image size stay as they are.
"""
import copy

AXES = {'length': 0, 'height': 1, 'depth': 2}


class ResizeError(ValueError):
    pass


def _axis_map(boards, a, target):
    """Monotonic piecewise-linear map for axis a that brings the overall extent to `target`."""
    edges = sorted({v for b in boards for v in (b['lo'][a], b['hi'][a])})
    rigid = [(b['lo'][a], b['hi'][a]) for b in boards if b['thin'] == a]
    segs = [(x0, x1, any(r0 - 1e-6 <= (x0 + x1) / 2 <= r1 + 1e-6 for r0, r1 in rigid)) for x0, x1 in zip(edges, edges[1:])]
    fixed = sum(x1 - x0 for x0, x1, r in segs if r)
    free = sum(x1 - x0 for x0, x1, r in segs if not r)
    if target is None or abs(target - (edges[-1] - edges[0])) < 1e-9:
        return lambda x: x
    if free <= 0 or target - fixed < free * 0.05:
        raise ResizeError(f'{"length height depth".split()[a]} cannot be {target:g} mm: the board thicknesses alone take '
                          f'{fixed:g} mm along that axis')
    k = (target - fixed) / free
    new, exact = [round(edges[0])], round(edges[0])   # rigid stretches exact; the running position is rounded,
    for x0, x1, r in segs:                              # so rounding never adds up along the axis
        exact += (x1 - x0) if r else (x1 - x0) * k
        new.append(new[-1] + (x1 - x0) if r else max(new[-1] + 1, round(exact)))

    def f(x):
        if x <= edges[0]:
            return new[0] + (x - edges[0])
        for i, (x0, x1, _r) in enumerate(segs):
            if x <= x1 + 1e-9:
                return new[i] + (new[i + 1] - new[i]) * ((x - x0) / (x1 - x0) if x1 > x0 else 0.0)
        return new[-1] + (x - edges[-1])
    return f


def resize_design(data, target):
    """data: parsed board-design/v1 JSON; target: {'length'?, 'height'?, 'depth'?} mm -> new data (copy)."""
    data = copy.deepcopy(data)
    raw = data.get('boards')
    t_default = (data.get('material') or {}).get('thickness')
    if not isinstance(raw, list) or not raw or not t_default:
        raise ResizeError('the design needs "material.thickness" and "boards" to resize')
    boards = []
    for b in raw:
        if b.get('rotate'):
            raise ResizeError(f"board '{b.get('id')}' is tilted (\"rotate\"); resizing tilted designs is not supported")
        t = b.get('thickness', t_default)
        thin = [i for i in range(3) if abs(b['size'][i] - t) <= 0.01]
        if b.get('normal') in ('x', 'y', 'z'):
            thin = ['xyz'.index(b['normal'])]
        if len(thin) != 1:
            raise ResizeError(f"board '{b.get('id')}': cannot tell which size is its thickness")
        lo = list(map(float, b['position']))
        boards.append({'raw': b, 'lo': lo, 'hi': [lo[i] + b['size'][i] for i in range(3)], 'thin': thin[0]})
    maps = [_axis_map(boards, a, target.get(name)) for name, a in AXES.items()]
    num = lambda v: int(v) if float(v).is_integer() else round(v, 3)
    for bd in boards:
        b, lo, hi = bd['raw'], bd['lo'], bd['hi']
        iu, iv = [i for i in range(3) if i != bd['thin']]
        new_lo = [maps[i](lo[i]) for i in range(3)]
        face = lambda uv: [num(maps[iu](lo[iu] + uv[0]) - new_lo[iu]), num(maps[iv](lo[iv] + uv[1]) - new_lo[iv])]
        b['position'] = [num(v) for v in new_lo]
        b['size'] = [num(maps[i](hi[i]) - new_lo[i]) for i in range(3)]
        prof = b.get('profile')
        if isinstance(prof, dict) and isinstance(prof.get('points'), list):
            prof['points'] = [face(q) for q in prof['points']]
        for o in b.get('openings') or []:
            if isinstance(o.get('center'), list) and len(o['center']) == 3:
                o['center'] = [num(maps[i](o['center'][i])) for i in range(3)]
        for e in b.get('engravings') or []:
            if isinstance(e.get('points'), list):
                e['points'] = [face(q) for q in e['points']]
            if isinstance(e.get('position'), list):
                e['position'] = face(e['position'])
        hinges = b.get('living_hinge')
        for h in (hinges if isinstance(hinges, list) else [hinges] if isinstance(hinges, dict) else []):
            for k in ('from', 'to'):
                if isinstance(h.get(k), list):
                    h[k] = face(h[k])
    ext = {name: max(bd['raw']['position'][a] + bd['raw']['size'][a] for bd in boards)
           - min(bd['raw']['position'][a] for bd in boards) for name, a in AXES.items()}
    product = data.setdefault('product', {})
    if isinstance(product, dict):
        product['overall'] = dict(product.get('overall') or {}, **{k: num(v) for k, v in ext.items()})
    return data, ext
