"""
Core geometry for flat-board (sheet material) products.

Coordinate conventions (used everywhere: engine, API, and the Three.js studio):
  * Units are millimetres.
  * World space is right-handed with +Y up.
  * Each component is a flat plate drawn in its own local XY plane. The plate
    occupies local z in [-t/2, +t/2] (centred on its mid-plane).
  * Placement = position [x, y, z] + rotation [rx, ry, rz] in DEGREES using the
    intrinsic Euler order 'XYZ' — identical to THREE.Euler's default, i.e. the
    rotation matrix is R = Rx · Ry · Rz. The API also returns the full 4x4
    world matrix so renderers never re-derive the transform.
"""
import math

EPS = 1e-9


# ---------------------------------------------------------------------------
# Small vector helpers (plain tuples/lists, no numpy dependency)
# ---------------------------------------------------------------------------

def v_add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def v_sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def v_scale(a, s):
    return [a[0] * s, a[1] * s, a[2] * s]


def v_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v_cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def v_len(a):
    return math.sqrt(v_dot(a, a))


def v_norm(a):
    n = v_len(a)
    return [a[0] / n, a[1] / n, a[2] / n] if n > EPS else [0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# Rigid transforms
# ---------------------------------------------------------------------------

def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def rotation_matrix(rotation_deg):
    """R = Rx · Ry · Rz (THREE.Euler order 'XYZ')."""
    rx, ry, rz = (math.radians(v) for v in rotation_deg)
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    Rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    Ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    Rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    return mat_mul(mat_mul(Rx, Ry), Rz)


class Frame:
    """World placement of a plate: local -> world and back."""

    def __init__(self, position, rotation_deg):
        self.p = [float(c) for c in position]
        self.R = rotation_matrix(rotation_deg)

    def axis(self, i):
        return [self.R[0][i], self.R[1][i], self.R[2][i]]

    @property
    def normal(self):
        return self.axis(2)

    def to_world(self, local):
        x, y = local[0], local[1]
        z = local[2] if len(local) > 2 else 0.0
        R = self.R
        return [R[0][0] * x + R[0][1] * y + R[0][2] * z + self.p[0],
                R[1][0] * x + R[1][1] * y + R[1][2] * z + self.p[1],
                R[2][0] * x + R[2][1] * y + R[2][2] * z + self.p[2]]

    def dir_to_world(self, local):
        x, y = local[0], local[1]
        z = local[2] if len(local) > 2 else 0.0
        R = self.R
        return [R[0][0] * x + R[0][1] * y + R[0][2] * z,
                R[1][0] * x + R[1][1] * y + R[1][2] * z,
                R[2][0] * x + R[2][1] * y + R[2][2] * z]

    def to_local(self, world):
        d = v_sub(world, self.p)
        R = self.R  # inverse of a rotation matrix is its transpose
        return [R[0][0] * d[0] + R[1][0] * d[1] + R[2][0] * d[2],
                R[0][1] * d[0] + R[1][1] * d[1] + R[2][1] * d[2],
                R[0][2] * d[0] + R[1][2] * d[1] + R[2][2] * d[2]]

    def dir_to_local(self, world):
        R = self.R
        return [R[0][0] * world[0] + R[1][0] * world[1] + R[2][0] * world[2],
                R[0][1] * world[0] + R[1][1] * world[1] + R[2][1] * world[2],
                R[0][2] * world[0] + R[1][2] * world[1] + R[2][2] * world[2]]

    def matrix4(self):
        """Column-major 4x4 (THREE.Matrix4.fromArray layout)."""
        R, p = self.R, self.p
        return [R[0][0], R[1][0], R[2][0], 0,
                R[0][1], R[1][1], R[2][1], 0,
                R[0][2], R[1][2], R[2][2], 0,
                p[0], p[1], p[2], 1]


# ---------------------------------------------------------------------------
# 2D polygon helpers
# ---------------------------------------------------------------------------

def signed_area(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a / 2.0


def bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_intersect(p1, p2, p3, p4):
    """Proper or touching intersection test for segments p1p2 and p3p4."""
    d1 = _orient(p3, p4, p1)
    d2 = _orient(p3, p4, p2)
    d3 = _orient(p1, p2, p3)
    d4 = _orient(p1, p2, p4)
    if ((d1 > EPS and d2 < -EPS) or (d1 < -EPS and d2 > EPS)) and \
       ((d3 > EPS and d4 < -EPS) or (d3 < -EPS and d4 > EPS)):
        return True

    def on_seg(a, b, c):
        return min(a[0], b[0]) - EPS <= c[0] <= max(a[0], b[0]) + EPS and \
            min(a[1], b[1]) - EPS <= c[1] <= max(a[1], b[1]) + EPS
    if abs(d1) <= EPS and on_seg(p3, p4, p1):
        return True
    if abs(d2) <= EPS and on_seg(p3, p4, p2):
        return True
    if abs(d3) <= EPS and on_seg(p1, p2, p3):
        return True
    if abs(d4) <= EPS and on_seg(p1, p2, p4):
        return True
    return False


def self_intersections(poly):
    """Return list of (i, j) edge index pairs that intersect (non-adjacent edges)."""
    n = len(poly)
    hits = []
    for i in range(n):
        a1, a2 = poly[i], poly[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            if segments_intersect(a1, a2, poly[j], poly[(j + 1) % n]):
                hits.append((i, j))
    return hits


def point_in_polygon(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            xint = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < xint:
                inside = not inside
        j = i
    return inside


def dist_point_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 < EPS else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    qx, qy = a[0] + t * dx, a[1] + t * dy
    return math.hypot(p[0] - qx, p[1] - qy)


def dist_to_boundary(p, poly):
    n = len(poly)
    return min(dist_point_segment(p, poly[i], poly[(i + 1) % n]) for i in range(n))


def near_boundary(p, poly, tol):
    """True if p is within tol of any polygon edge (early exit, bbox-rejected per segment)."""
    px, py = p
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if px < min(a[0], b[0]) - tol or px > max(a[0], b[0]) + tol or \
           py < min(a[1], b[1]) - tol or py > max(a[1], b[1]) + tol:
            continue
        if dist_point_segment(p, a, b) <= tol:
            return True
    return False


def polygon_distance(pa, pb):
    """Minimum distance between two polygon boundaries (0 if they cross)."""
    na, nb = len(pa), len(pb)
    for i in range(na):
        for j in range(nb):
            if segments_intersect(pa[i], pa[(i + 1) % na], pb[j], pb[(j + 1) % nb]):
                return 0.0
    d = min(dist_to_boundary(p, pb) for p in pa)
    return min(d, min(dist_to_boundary(p, pa) for p in pb))


def polygons_overlap(pa, pb):
    """True if the two polygon *areas* share interior points."""
    na, nb = len(pa), len(pb)
    for i in range(na):
        for j in range(nb):
            if segments_intersect(pa[i], pa[(i + 1) % na], pb[j], pb[(j + 1) % nb]):
                return True
    return point_in_polygon(pa[0], pb) or point_in_polygon(pb[0], pa)


def rect_polygon(center, width, height, angle_deg=0.0):
    cx, cy = center
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    hw, hh = width / 2.0, height / 2.0
    pts = []
    for lx, ly in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
        pts.append([cx + lx * ca - ly * sa, cy + lx * sa + ly * ca])
    return pts


def circle_polygon(center, diameter, segments=32):
    r = diameter / 2.0
    return [[center[0] + r * math.cos(2 * math.pi * i / segments),
             center[1] + r * math.sin(2 * math.pi * i / segments)] for i in range(segments)]


def offset_convex_polygon(poly, d):
    """Offset a CCW convex polygon outward by d (mitred corners)."""
    n = len(poly)
    lines = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        nx, ny = dy / L, -dx / L  # outward normal for CCW
        lines.append(((a[0] + nx * d, a[1] + ny * d), (dx, dy)))
    out = []
    for i in range(n):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        den = d1[0] * d2[1] - d1[1] * d2[0]
        t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        out.append([p1[0] + d1[0] * t, p1[1] + d1[1] * t])
    return out


def angle_diff_mod180(a, b):
    d = (a - b) % 180.0
    return min(d, 180.0 - d)


def convex_hull(points):
    """Andrew's monotone chain; CCW, no collinear points."""
    pts = sorted(set((float(p[0]), float(p[1])) for p in points))
    if len(pts) <= 2:
        return [list(p) for p in pts]

    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and _orient(h[-2], h[-1], p) <= EPS:
                h.pop()
            h.append(p)
        return h
    lower, upper = half(pts), half(reversed(pts))
    return [list(p) for p in lower[:-1] + upper[:-1]]


def oriented_rect(poly):
    """Minimum-area bounding rectangle (rotating calipers over the hull edges).

    Returns {'length', 'width', 'angle', 'origin'}: length >= width; `angle` (deg) is the direction of the
    length axis in the polygon's frame; `origin` is the rectangle corner with minimum (u, v) along
    (length axis, width axis). This is the blank a board is cut from, independent of how it is drawn.
    """
    hull = convex_hull(poly)
    best = None
    for i in range(len(hull)):
        a, b = hull[i], hull[(i + 1) % len(hull)]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < EPS:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        us = [p[0] * ux + p[1] * uy for p in hull]
        vs = [-p[0] * uy + p[1] * ux for p in hull]
        w, h = max(us) - min(us), max(vs) - min(vs)
        # prefer the axis-aligned candidate on (numerical) ties so rectangles drawn square stay at 0 deg
        key = (round(w * h, 6), round(min(abs(math.degrees(math.atan2(uy, ux))) % 90, 90 - abs(math.degrees(math.atan2(uy, ux))) % 90), 6))
        if best is None or key < best[0]:
            best = (key, ux, uy, min(us), min(vs), w, h)
    if best is None:
        return {'length': 0.0, 'width': 0.0, 'angle': 0.0, 'origin': [0.0, 0.0]}
    _k, ux, uy, u0, v0, w, h = best
    if h > w:  # make the long side the length axis (rotate the frame by +90 deg)
        ux, uy, u0, v0, w, h = -uy, ux, v0, -(u0 + w), h, w
    ang = math.degrees(math.atan2(uy, ux))
    if ang <= -90 + 1e-9 or ang > 90 + 1e-9:  # report the length axis pointing towards +x
        ux, uy, u0, v0 = -ux, -uy, -(u0 + w), -(v0 + h)
        ang = math.degrees(math.atan2(uy, ux))
    return {'length': w, 'width': h, 'angle': ang, 'origin': [u0 * ux - v0 * uy, u0 * uy + v0 * ux]}


def offset_edges(poly, inward):
    """Move each edge of a CCW simple polygon inward by inward[i] mm (negative = outward); vertices are
    re-intersected from the moved neighbouring edge lines (collinear neighbours keep the moved point)."""
    n = len(poly)
    lines = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L   # inward normal for CCW
        d = inward[i]
        lines.append(((a[0] + nx * d, a[1] + ny * d), (b[0] - a[0], b[1] - a[1])))
    out = []
    for i in range(n):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-12:
            out.append([p2[0], p2[1]])
            continue
        t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        out.append([p1[0] + d1[0] * t, p1[1] + d1[1] * t])
    return out
