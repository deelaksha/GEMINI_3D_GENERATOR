"""
2D shape library: arcs, rounded corners and standard shapes for complex cuts.

Every shape is flattened to a polygon (what the whole engine works with: validation, collisions, nesting,
cut paths) and, where it contains circular arcs, carries `arcs` metadata so exporters can write TRUE arcs
(SVG `A`, DXF bulges) instead of many short lines:

    arcs = [{'start': i, 'end': j, 'center': [cx, cy], 'radius': r, 'ccw': bool}, ...]

meaning polygon vertices i..j (inclusive, consecutive) lie on that arc. Flattening keeps the chord error
(sagitta) at or below FLATTEN_TOL so the polygon stays within cutting accuracy of the real curve.

Shape specs (all coordinates in the board's 2D frame, mm):
    {"shape": "rect", "center": [x, y], "width", "height", "corner_radius"?, "angle"?}
    {"shape": "circle", "center", "diameter"}
    {"shape": "ellipse", "center", "width", "height"}
    {"shape": "arch", "center", "width", "height"}              rectangle with a semicircular top
    {"shape": "regular_polygon", "center", "sides", "diameter", "rotation"?}
    {"shape": "gear", "center", "teeth", "module", "rotation"?, "pressure_angle"?, "backlash"?}   involute spur gear
    {"shape": "polygon", "points": [[x, y], ...], "corner_radius"?}
    {"shape": "path", "start": [x, y], "segments": [{"line": [x, y]} |
         {"arc": {"to": [x, y], "radius": r, "large": bool, "clockwise": bool}} |
         {"arc": {"to": [x, y], "center": [x, y], "clockwise": bool}}], "corner_radius"?}
"""
import math

FLATTEN_TOL = 0.1          # mm: max distance between a flattened chord and the true arc
MAX_ARC_SEGMENTS = 128     # per full circle
MAX_POINTS = 2048


class ShapeError(ValueError):
    pass


def _num(v, name, lo=None):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ShapeError(f'{name} must be a number')
    if lo is not None and v <= lo:
        raise ShapeError(f'{name} must be > {lo}')
    return float(v)


def _pt(v, name):
    if not (isinstance(v, (list, tuple)) and len(v) == 2):
        raise ShapeError(f'{name} must be [x, y]')
    return [_num(v[0], name), _num(v[1], name)]


def _steps(radius, sweep):
    if radius <= 0:
        return 1
    d = 2 * math.acos(max(-1.0, 1 - FLATTEN_TOL / radius)) if radius > FLATTEN_TOL else math.pi / 2
    d = max(d, 2 * math.pi / MAX_ARC_SEGMENTS)
    return max(2, int(math.ceil(abs(sweep) / d)))


class PathBuilder:
    """Builds a closed polygon from lines and arcs, recording arc runs."""

    def __init__(self, start):
        self.pts = [list(start)]
        self.arcs = []

    def line(self, p):
        if math.dist(self.pts[-1], p) > 1e-9:
            self.pts.append(list(p))

    def arc(self, end, center, ccw):
        p0 = self.pts[-1]
        r0, r1 = math.dist(center, p0), math.dist(center, end)
        if r0 < 1e-9 or abs(r0 - r1) > max(0.01, 1e-4 * r0):
            raise ShapeError(f'arc end point is not on the circle (radius {r0:.3f} vs {r1:.3f})')
        a0 = math.atan2(p0[1] - center[1], p0[0] - center[0])
        a1 = math.atan2(end[1] - center[1], end[0] - center[0])
        sweep = a1 - a0
        if ccw and sweep <= 0:
            sweep += 2 * math.pi
        if not ccw and sweep >= 0:
            sweep -= 2 * math.pi
        n = _steps(r0, sweep)
        start = len(self.pts) - 1
        for k in range(1, n + 1):
            a = a0 + sweep * k / n
            self.pts.append([center[0] + r0 * math.cos(a), center[1] + r0 * math.sin(a)])
        self.pts[-1] = list(end)
        self.arcs.append({'start': start, 'end': len(self.pts) - 1, 'center': [center[0], center[1]],
                          'radius': r0, 'ccw': bool(ccw)})

    def arc_radius(self, end, radius, large, clockwise):
        """SVG-style arc (circular): centre from end points, radius and flags."""
        p0 = self.pts[-1]
        dx, dy = end[0] - p0[0], end[1] - p0[1]
        d = math.hypot(dx, dy)
        if d < 1e-9:
            raise ShapeError('arc start and end are the same point')
        if radius < d / 2 - 1e-9:
            raise ShapeError(f'arc radius {radius:g} is smaller than half the chord ({d / 2:.3f})')
        h = math.sqrt(max(radius * radius - d * d / 4, 0.0))
        mx, my = (p0[0] + end[0]) / 2, (p0[1] + end[1]) / 2
        ux, uy = -dy / d, dx / d
        ccw = not clockwise
        # of the two possible centres, pick the one giving the requested sweep size
        sign = 1 if (large == ccw) else -1
        center = [mx - sign * ux * h, my - sign * uy * h]
        self.arc(end, center, ccw)

    def close(self):
        if len(self.pts) > 1 and math.dist(self.pts[0], self.pts[-1]) < 1e-9:
            self.pts.pop()
            for a in self.arcs:
                if a['end'] == len(self.pts):
                    a['end'] = 0        # arc ends on the first vertex
        return self.pts, self.arcs


def fillet(points, radius):
    """Round every corner of a closed polygon with `radius` (reduced where edges are too short)."""
    n = len(points)
    if radius <= 0 or n < 3:
        return [list(p) for p in points], []
    # orientation decides which side the centres lie on
    area = sum(points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1] for i in range(n)) / 2
    orient = 1 if area > 0 else -1
    lens = [math.dist(points[i], points[(i + 1) % n]) for i in range(n)]
    pts, arcs = [], []
    for i in range(n):
        p, a, b = points[i], points[i - 1], points[(i + 1) % n]
        v1 = [(a[0] - p[0]) / lens[i - 1], (a[1] - p[1]) / lens[i - 1]] if lens[i - 1] > 1e-9 else None
        v2 = [(b[0] - p[0]) / lens[i], (b[1] - p[1]) / lens[i]] if lens[i] > 1e-9 else None
        if not v1 or not v2:
            pts.append(list(p))
            continue
        cosang = max(-1.0, min(1.0, v1[0] * v2[0] + v1[1] * v2[1]))
        ang = math.acos(cosang)
        if ang < 1e-3 or abs(ang - math.pi) < 1e-3:
            pts.append(list(p))
            continue
        d = radius / math.tan(ang / 2)
        d = min(d, lens[i - 1] / 2, lens[i] / 2)
        r = d * math.tan(ang / 2)
        t1 = [p[0] + v1[0] * d, p[1] + v1[1] * d]
        t2 = [p[0] + v2[0] * d, p[1] + v2[1] * d]
        bis = [v1[0] + v2[0], v1[1] + v2[1]]
        bl = math.hypot(*bis)
        c = [p[0] + bis[0] / bl * (r / math.sin(ang / 2)), p[1] + bis[1] / bl * (r / math.sin(ang / 2))]
        cross = v1[0] * v2[1] - v1[1] * v2[0]          # >0: the corner turns left going a -> p -> b ?
        ccw = (cross < 0) == (orient > 0)
        pb = PathBuilder(t1)
        pb.arc(t2, c, ccw)
        start = len(pts)
        pts.extend(pb.pts)
        arcs.append({'start': start, 'end': len(pts) - 1, 'center': c, 'radius': r, 'ccw': ccw})
    return pts, arcs


def shape_polygon(spec, name='shape'):
    """-> (points, arcs) for a shape spec, or ('circle', center, diameter) handled by the caller."""
    if not isinstance(spec, dict):
        raise ShapeError(f'{name} must be an object')
    kind = spec.get('shape')
    cr = spec.get('corner_radius')
    cr = _num(cr, f'{name}.corner_radius', 0) if cr not in (None, 0) else 0.0
    if kind == 'rect':
        c = _pt(spec.get('center'), f'{name}.center')
        w, h = _num(spec.get('width'), f'{name}.width', 0), _num(spec.get('height'), f'{name}.height', 0)
        pts = [[c[0] - w / 2, c[1] - h / 2], [c[0] + w / 2, c[1] - h / 2], [c[0] + w / 2, c[1] + h / 2], [c[0] - w / 2, c[1] + h / 2]]
        pts, arcs = fillet(pts, min(cr, w / 2, h / 2)) if cr else (pts, [])
        ang = spec.get('angle') or 0
        if ang:
            pts, arcs = _rotate(pts, arcs, c, _num(ang, f'{name}.angle'))
        return pts, arcs
    if kind == 'circle':
        c = _pt(spec.get('center'), f'{name}.center')
        r = _num(spec.get('diameter'), f'{name}.diameter', 0) / 2
        pb = PathBuilder([c[0] + r, c[1]])
        pb.arc([c[0] - r, c[1]], c, True)
        pb.arc([c[0] + r, c[1]], c, True)
        return pb.close()
    if kind == 'ellipse':
        c = _pt(spec.get('center'), f'{name}.center')
        a, b = _num(spec.get('width'), f'{name}.width', 0) / 2, _num(spec.get('height'), f'{name}.height', 0) / 2
        n = _steps(max(a, b), 2 * math.pi)
        return [[c[0] + a * math.cos(2 * math.pi * k / n), c[1] + b * math.sin(2 * math.pi * k / n)] for k in range(n)], []
    if kind == 'arch':
        c = _pt(spec.get('center'), f'{name}.center')
        w, h = _num(spec.get('width'), f'{name}.width', 0), _num(spec.get('height'), f'{name}.height', 0)
        r = w / 2
        if h < r:
            raise ShapeError(f'{name}: an arch needs height >= width / 2')
        x0, y0 = c[0] - w / 2, c[1] - h / 2
        spring = y0 + h - r
        pb = PathBuilder([x0, y0])
        pb.line([x0 + w, y0])
        pb.line([x0 + w, spring])
        pb.arc([x0, spring], [c[0], spring], True)
        return pb.close()
    if kind == 'regular_polygon':
        c = _pt(spec.get('center'), f'{name}.center')
        n = spec.get('sides')
        if isinstance(n, bool) or not isinstance(n, int) or not 3 <= n <= 64:
            raise ShapeError(f'{name}.sides must be an integer 3..64')
        r = _num(spec.get('diameter'), f'{name}.diameter', 0) / 2
        rot = math.radians(_num(spec.get('rotation', 90), f'{name}.rotation'))
        pts = [[c[0] + r * math.cos(rot + 2 * math.pi * k / n), c[1] + r * math.sin(rot + 2 * math.pi * k / n)] for k in range(n)]
        return fillet(pts, cr) if cr else (pts, [])
    if kind == 'polygon':
        raw = spec.get('points')
        if not isinstance(raw, list) or len(raw) < 3:
            raise ShapeError(f'{name}.points needs at least 3 [x, y] points')
        pts = [_pt(p, f'{name}.points[{i}]') for i, p in enumerate(raw)]
        return fillet(pts, cr) if cr else (pts, [])
    if kind == 'path':
        pb = PathBuilder(_pt(spec.get('start'), f'{name}.start'))
        segs = spec.get('segments')
        if not isinstance(segs, list) or not segs:
            raise ShapeError(f'{name}.segments must be a non-empty list')
        for i, s in enumerate(segs):
            p = f'{name}.segments[{i}]'
            if isinstance(s, dict) and 'line' in s:
                pb.line(_pt(s['line'], p + '.line'))
            elif isinstance(s, dict) and isinstance(s.get('arc'), dict):
                a = s['arc']
                to = _pt(a.get('to'), p + '.arc.to')
                if a.get('center') is not None:
                    pb.arc(to, _pt(a['center'], p + '.arc.center'), not a.get('clockwise', False))
                else:
                    pb.arc_radius(to, _num(a.get('radius'), p + '.arc.radius', 0), bool(a.get('large')),
                                  bool(a.get('clockwise')))
            elif isinstance(s, (list, tuple)):
                pb.line(_pt(s, p))
            else:
                raise ShapeError(f'{p} must be {{"line": [x, y]}} or {{"arc": {{...}}}}')
        pts, arcs = pb.close()
        if cr:
            if arcs:
                raise ShapeError(f'{name}: corner_radius cannot be combined with arcs in a path')
            return fillet(pts, cr)
        return pts, arcs
    if kind == 'gear':
        c = _pt(spec.get('center'), f'{name}.center')
        z = spec.get('teeth')
        if isinstance(z, bool) or not isinstance(z, int) or not 6 <= z <= 100:
            raise ShapeError(f'{name}.teeth must be an integer 6..100')
        m = _num(spec.get('module'), f'{name}.module', 0)
        pa = _num(spec.get('pressure_angle', 20), f'{name}.pressure_angle', 0)
        bl = spec.get('backlash')
        bl = 0.05 * m if bl is None else _num(bl, f'{name}.backlash', -1e-12)
        if m > 50 or not 14 <= pa <= 30 or bl >= m:
            raise ShapeError(f'{name}: module must be at most 50 mm, pressure_angle 14..30 degrees, backlash < module')
        return gear_points(c, z, m, pa, bl, _num(spec.get('rotation', 0), f'{name}.rotation')), []
    raise ShapeError(f'{name}.shape must be one of rect, circle, ellipse, arch, regular_polygon, gear, polygon, path')


def gear_geometry(z, m, pa=20.0):
    """Radii of a standard spur gear: pitch, tip (addendum = module), root (dedendum = 1.25 module), base."""
    r = m * z / 2.0
    return {'pitch': r, 'tip': r + m, 'root': max(r - 1.25 * m, 0.25 * r), 'base': r * math.cos(math.radians(pa))}


def gear_points(c, z, m, pa=20.0, backlash=None, rotation=0.0):
    """Outline (counter-clockwise) of an involute spur gear: z teeth of module m, tooth 0 pointing at `rotation`
    degrees. The backlash (default 0.05 module) is taken off each tooth's thickness at the pitch circle, so two meshing
    gears touch without overlapping."""
    g = gear_geometry(z, m, pa)
    r, ra, rf, rb = g['pitch'], g['tip'], g['root'], g['base']
    a0 = math.radians(pa)
    inv = lambda a: math.tan(a) - a
    bl = 0.05 * m if backlash is None else backlash
    half = (math.pi * m / 2.0 - bl) / 2.0 / r          # half the tooth's angular thickness at the pitch circle

    def w(rho):                                         # half angular width of the tooth at radius rho
        return max(0.002, half + inv(a0) - inv(math.acos(min(1.0, rb / max(rho, rb)))))
    lo = max(rf, rb)
    flank = ([rf] if rf < rb else []) + [lo + (ra - lo) * k / 6.0 for k in range(7)]
    pt = lambda rho, ang: [c[0] + rho * math.cos(ang), c[1] + rho * math.sin(ang)]
    pts, rot = [], math.radians(rotation)
    for i in range(z):
        th = rot + 2 * math.pi * i / z
        pts += [pt(rho, th - w(rho)) for rho in flank]                          # leading flank, root to tip
        pts += [pt(ra, th - w(ra) + 2 * w(ra) * k / 3.0) for k in (1, 2)]        # tip
        pts += [pt(rho, th + w(rho)) for rho in reversed(flank)]                # trailing flank, tip to root
        nxt = th + 2 * math.pi / z
        a, b = th + w(flank[0]), nxt - w(flank[0])
        pts += [pt(rf, a + (b - a) * k / 4.0) for k in (1, 2, 3)]               # root arc to the next tooth
    return pts


def _rotate(pts, arcs, c, deg):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    rot = lambda p: [c[0] + (p[0] - c[0]) * ca - (p[1] - c[1]) * sa, c[1] + (p[0] - c[0]) * sa + (p[1] - c[1]) * ca]
    return [rot(p) for p in pts], [dict(x, center=rot(x['center'])) for x in arcs]


def reverse(points, arcs):
    """Reverse polygon winding, keeping arc metadata consistent."""
    n = len(points)
    rp = list(reversed(points))
    ra = [dict(a, start=(n - 1 - a['end']) % n, end=(n - 1 - a['start']) % n, ccw=not a['ccw']) for a in arcs]
    return rp, ra


def arc_sweep(p0, pm, p1, center):
    """Signed sweep (radians) of the arc p0 -> p1 that passes through pm (works in any handedness)."""
    a0 = math.atan2(p0[1] - center[1], p0[0] - center[0])
    am = math.atan2(pm[1] - center[1], pm[0] - center[0])
    a1 = math.atan2(p1[1] - center[1], p1[0] - center[0])
    ccw = (am - a0) % (2 * math.pi) < (a1 - a0) % (2 * math.pi)
    s = (a1 - a0) % (2 * math.pi)
    return s if ccw else s - 2 * math.pi


def transform_arcs(arcs, fn):
    return [dict(a, center=fn(a['center'])) for a in arcs]
