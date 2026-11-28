"""
Machine-independent cutting paths, plus SVG and DXF writers.

Each placed part yields:
  * one OUTER closed path (cut profile incl. tabs and notches) - cut last
  * one INNER closed path per feature (slots, holes, openings)  - cut first
  * ENGRAVE / POCKET paths (partial depth, never through)        - machined before any cut
Curved runs carry `arcs` (vertex index ranges on a circle) so SVG and DXF get TRUE arcs.
Kerf compensation (optional) moves outer paths outward and inner paths inward by kerf/2 so
that the finished part keeps its design dimensions.
Router process (design['process']): every inside corner of the material a round bit cannot reach (slot, finger and
cross-lap notch corners, tab roots) gets a dog-bone relief - a circle of the cut radius on the corner bisector that
passes through the corner. A compensated (tool-centre) path plunges along the bisector to the relief centre and back;
an uncompensated (part geometry) path carries the relief as a true arc. Each path lists its `reliefs`. Laser / saw /
no process: no relief.
"""
import math

from . import geometry as G
from .model import Plate, feature_shape, find_component
from .nesting import transform_point
from .shapes import arc_sweep

# Layer name, SVG colour, DXF colour index. The SVG colours are the pure RGB values of the DXF colours: laser drivers
# (Epilog, Universal, Trotec, LightBurn) assign cut / engrave settings by exact colour, so every operation has one.
LAYERS = {'outer': ('CUT_OUTER', '#FF0000', 1), 'inner': ('CUT_INNER', '#0000FF', 5),
          'engrave': ('ENGRAVE', '#00FFFF', 4), 'pocket': ('POCKET', '#00FF00', 3),
          'label': ('ENGRAVE_LABELS', '#000000', 7)}
HAIRLINE = 0.025  # mm (0.001 in): the stroke width print-driver lasers treat as a vector cut, not a raster fill
LEGEND = ('red CUT_OUTER = part outline (cut last) | blue CUT_INNER = slots / holes / openings (cut first) | '
          'cyan ENGRAVE, green POCKET = partial depth (machined before any cut) | black ENGRAVE_LABELS = part labels, '
          'single-line (optional) | ENGRAVE_IMAGE = raster images (SVG only)')
ARC_TOL = 0.02   # mm: an arc run is exported as a true arc only if its end points sit on the circle


def _map_arcs(src, arcs, dst):
    """Re-index arc runs from polygon `src` onto `dst` (e.g. the outline after tabs were inserted)."""
    if not arcs:
        return []
    index = {(round(p[0], 6), round(p[1], 6)): i for i, p in enumerate(dst)}
    out = []
    for a in arcs:
        i, j = index.get(tuple(round(v, 6) for v in src[a['start']])), index.get(tuple(round(v, 6) for v in src[a['end']]))
        n_src, n_dst = len(src), len(dst)
        if i is not None and j is not None and (j - i) % n_dst == (a['end'] - a['start']) % n_src:
            out.append(dict(a, start=i, end=j))
    return out


def path_segments(points, arcs, closed=True):
    """(start, [('L', p) | ('A', p, center, radius, sweep_rad)]) for a path in output coordinates.
    Arcs whose end points do not lie on their circle (e.g. a tab cut into a curved edge) fall back to lines."""
    n = len(points)
    by_start = {}
    for a in arcs or []:
        L = (a['end'] - a['start']) % n
        r0, r1 = math.dist(points[a['start']], a['center']), math.dist(points[a['end']], a['center'])
        if L >= 2 and abs(r0 - r1) <= ARC_TOL and (closed or a['end'] > a['start']):
            by_start[a['start']] = (a, L, r0)
    s0 = next(iter(by_start)) if closed and by_start else 0
    total = n if closed else n - 1
    segs, i, done = [], s0, 0
    while done < total:
        if i in by_start and done + by_start[i][1] <= total:
            a, L, r = by_start[i]
            j = (i + L) % n
            sweep = arc_sweep(points[i], points[(i + L // 2) % n], points[j], a['center'])
            if abs(sweep) > math.pi:          # split so every piece is <= 180 deg (DXF bulge, SVG flags stay simple)
                m = (i + L // 2) % n
                segs.append(('A', points[m], a['center'], r, arc_sweep(points[i], points[(i + L // 4) % n], points[m], a['center'])))
                segs.append(('A', points[j], a['center'], r, arc_sweep(points[m], points[(m + (L - L // 2) // 2) % n], points[j], a['center'])))
            else:
                segs.append(('A', points[j], a['center'], r, sweep))
            i, done = j, done + L
        else:
            i = (i + 1) % n
            segs.append(('L', points[i]))
            done += 1
    return points[s0], segs


def offset_polygon(poly, d):
    """Mitre offset of a CCW simple polygon by d (outward if d > 0). Intended for small d (kerf)."""
    n = len(poly)
    normals = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        normals.append(((b[1] - a[1]) / L, -(b[0] - a[0]) / L))
    out = []
    for i in range(n):
        n1, n2 = normals[i - 1], normals[i]
        k = max(1.0 + n1[0] * n2[0] + n1[1] * n2[1], 1e-6)
        out.append([poly[i][0] + d * (n1[0] + n2[0]) / k, poly[i][1] + d * (n1[1] + n2[1]) / k])
    return out


def label_point(plate):
    """A point well inside solid material for the engraved part ID."""
    x0, y0, x1, y1 = plate.bbox2d
    best, bd = [(x0 + x1) / 2, (y0 + y1) / 2], -1.0
    for i in range(1, 16):
        for j in range(1, 16):
            p = [x0 + (x1 - x0) * i / 16, y0 + (y1 - y0) * j / 16]
            if not plate.is_material(p, 0.0):
                continue
            d = G.dist_to_boundary(p, plate.cut)
            for _f, poly in plate.feature_polys:
                d = min(d, G.dist_to_boundary(p, poly))
            if d > bd:
                best, bd = p, d
    return best, max(bd, 0.0)


def _share_edges(sheet):
    """Common-line cutting: where an outline runs along a line another part's outline already cuts (parts nested one
    kerf apart, so their compensated outlines coincide), drop that stretch from the later outline. What is left of it
    becomes open paths. Only straight runs of outlines without arcs are shared."""
    tol = 0.01
    kept = []                                   # straight segments already being cut on this sheet
    out = []
    for p in sheet['paths']:
        if p['type'] != 'outer' or p.get('arcs') or p['shape'] != 'polyline':
            out.append(p)
            continue
        pts = p['points']
        n = len(pts)
        segs = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
        pieces, shared = [], False             # (segment index, t0, t1) still to cut, in path order
        for i, (a, b) in enumerate(segs):
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy)
            if L < 1e-9:
                continue
            ux, uy = dx / L, dy / L
            cuts = []
            for c, d in kept:
                if abs((d[0] - c[0]) * uy - (d[1] - c[1]) * ux) > tol * max(1.0, math.dist(c, d)):
                    continue                    # not parallel
                if abs((c[0] - a[0]) * uy - (c[1] - a[1]) * ux) > tol:
                    continue                    # parallel but not on the same line
                t0, t1 = sorted(((c[0] - a[0]) * ux + (c[1] - a[1]) * uy, (d[0] - a[0]) * ux + (d[1] - a[1]) * uy))
                lo, hi = max(0.0, t0), min(L, t1)
                if hi - lo > tol:
                    cuts.append((lo, hi))
                    shared = True
            t = 0.0
            for lo, hi in sorted(cuts):
                if lo > t + tol:
                    pieces.append((i, t, lo))
                t = max(t, hi)
            if t < L - tol:
                pieces.append((i, t, L))
        kept.extend(segs)
        if not shared:
            out.append(p)                       # nothing shared: the closed outline stays as it is
            continue
        at = lambda i, t: [round(segs[i][0][0] + (segs[i][1][0] - segs[i][0][0]) * t / math.dist(*segs[i]), 4),
                           round(segs[i][0][1] + (segs[i][1][1] - segs[i][0][1]) * t / math.dist(*segs[i]), 4)]
        runs, cur, last = [], None, None
        for i, t0, t1 in pieces:                # join pieces that continue one another into polylines
            start, end = at(i, t0), at(i, t1)
            if cur and last and math.dist(last, start) <= tol:
                cur.append(end)
            else:
                cur = [start, end]
                runs.append(cur)
            last = end
        if len(runs) > 1 and math.dist(runs[-1][-1], runs[0][0]) <= tol:
            runs[0] = runs.pop() + runs[0][1:]  # the run crossing the path's start point is one run
        for k, run in enumerate(runs):
            out.append(dict(p, id=f"{p['id']}#{k + 1}", points=run, closed=False, shared=True, part_outline=pts))
    sheet['paths'] = out


def corner_reliefs(poly, hole, r, arcs=None):
    """Dog-bone reliefs of one closed path (design coordinates): [(vertex, corner, centre, e_prev, e_next)] (e: unit
    vectors from the corner along its two edges) for every inside corner of the material - a convex vertex of a hole,
    a reflex vertex of an outline - where a bit of radius r would leave more than RELIEF_TOL of material. The relief circle (radius r) sits on the corner bisector and passes through the
    corner. Vertices inside true-arc runs are curves, not corners."""
    from .manufacturing import RELIEF_TOL
    n = len(poly)
    if r <= 0 or n < 3:
        return []
    curve = {(a['start'] + k) % n for a in arcs or [] for k in range(1, (a['end'] - a['start']) % n)}
    sign = 1.0 if G.signed_area(poly) > 0 else -1.0
    out = []
    for i in range(n):
        if i in curve:
            continue
        q, a, b = poly[i], poly[i - 1], poly[(i + 1) % n]
        la, lb = math.dist(q, a), math.dist(q, b)
        if la < 1e-9 or lb < 1e-9:
            continue
        ea, eb = ((a[0] - q[0]) / la, (a[1] - q[1]) / la), ((b[0] - q[0]) / lb, (b[1] - q[1]) / lb)
        turn = sign * (-ea[0] * eb[1] + ea[1] * eb[0])        # > 0: convex vertex of the polygon
        if (turn <= 1e-9) if hole else (turn >= -1e-9):
            continue
        half_angle = math.acos(max(-1.0, min(1.0, ea[0] * eb[0] + ea[1] * eb[1]))) / 2.0
        if half_angle < 1e-6 or r / math.sin(half_angle) - r <= RELIEF_TOL:
            continue
        ux, uy = ea[0] + eb[0], ea[1] + eb[1]
        L = math.hypot(ux, uy)
        out.append((i, q, [q[0] + ux / L * r, q[1] + uy / L * r], ea, eb))
    return out


def _with_reliefs(pts, design_pts, arcs, hole, r, compensated):
    """(points, arcs, reliefs) of a path with dog-bone reliefs inserted. Compensated tool-centre path: the bit plunges
    from the offset corner to the relief centre and back. Part geometry: the corner becomes a true arc of radius r."""
    rel = corner_reliefs(design_pts, hole, r, arcs)
    if not rel:
        return pts, arcs, []
    at = {i: (q, c, ea, eb) for i, q, c, ea, eb in rel}
    out, index, lobes = [], [], []
    for i, p in enumerate(pts):
        first = len(out)
        if i not in at:
            out.append(p)
        elif compensated:
            out += [p, at[i][1], p]
        else:
            q, c, ea, eb = at[i]
            t = 2 * (ea[0] * (c[0] - q[0]) + ea[1] * (c[1] - q[1]))     # chord from the corner to the circle: 2r cos
            A, B = [q[0] + ea[0] * t, q[1] + ea[1] * t], [q[0] + eb[0] * t, q[1] + eb[1] * t]
            sweep = arc_sweep(A, q, B, c)
            a0 = math.atan2(A[1] - c[1], A[0] - c[0])
            k = max(4, math.ceil(abs(sweep) / (math.pi / 18)))
            out += [A] + [[c[0] + r * math.cos(a0 + sweep * j / k), c[1] + r * math.sin(a0 + sweep * j / k)]
                          for j in range(1, k)] + [B]
            lobes.append({'start': first, 'end': len(out) - 1, 'center': c, 'radius': r, 'ccw': sweep > 0})
        index.append((first, len(out) - 1))
    arcs = [dict(a, start=index[a['start']][1], end=index[a['end']][0]) for a in arcs or []] + lobes
    return out, arcs, [(q, c) for _i, q, c, _a, _b in rel]


def _router_issues(pl, r, reliefs, inner, design):
    """Blocking issues of a routed part (design coordinates): a cut-out or notch the bit cannot clear (narrower than
    the bit, or an inside curve tighter than its radius), and reliefs that cut through or thin a web below the
    process minimum."""
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union
    from .manufacturing import RELIEF_TOL, process_limits
    count = lambda g: 0 if g.is_empty else len(getattr(g, 'geoms', [g]))
    outline = Polygon(pl.cut).buffer(0)
    holes = [Polygon(poly).buffer(0) for _f, poly in pl.feature_polys]
    disks = unary_union([Point(c).buffer(r, quad_segs=32) for _q, c in reliefs]) if reliefs else Polygon()
    material = outline.difference(unary_union(holes)) if holes else outline
    issues = []
    removed = unary_union([outline.buffer(2 * r + 1.0).difference(outline)] + holes + [disks])
    e = r - RELIEF_TOL / 2
    unreachable = removed.difference(removed.buffer(-e).buffer(e)).buffer(-RELIEF_TOL)
    if not unreachable.is_empty:
        tight = any(a['radius'] < r - 1e-6 for p in inner for a in p.get('arcs', [])) or \
            any(a['radius'] < r - 1e-6 for a in pl.comp.get('arcs', []))
        c = unreachable.representative_point()
        issues.append(_iss('INSIDE_RADIUS_BELOW_TOOL' if tight else 'TOOL_TOO_LARGE', pl.id,
                           f"'{pl.id}' has a cut-out, notch or inside curve the {2 * r:g} mm router bit cannot clear "
                           f"(near {c.x:.1f}, {c.y:.1f}): make it at least {2 * r:g} mm wide with inside radii of at "
                           f"least {r:g} mm, or use a smaller bit."))
    if reliefs:
        web = process_limits(design, pl.t)['min_web']
        left = material.difference(disks)
        thinnest = 0.0 if count(left) > count(material) else _thinnest_web(pl, r, reliefs, left, web)
        if thinnest is not None:
            issues.append(_iss('RELIEF_BREAKS_WEB', pl.id,
                               f"A dog-bone relief of the {2 * r:g} mm bit would cut through a web of '{pl.id}' or "
                               f"leave only {thinnest:.1f} mm of material there (at least {web:g} mm needed): move the "
                               f"cut-out away from the edge or the next cut-out, or use a smaller bit."))
    return issues


def _thinnest_web(pl, r, reliefs, left, web):
    """Thinnest material (mm) between a relief circle and any other edge of the part, measured straight through solid
    material, when it is below `web`; None when every relief leaves at least `web`. The two edges that meet at the
    relieved corner do not count (the relief is cut into them on purpose)."""
    from shapely.geometry import LineString
    rings = [pl.cut] + [poly for _f, poly in pl.feature_polys]
    segs = [(ring[i], ring[(i + 1) % len(ring)]) for ring in rings for i in range(len(ring))]
    worst = None
    for q, c in reliefs:
        for a, b in segs:
            if math.dist(a, q) < 1e-6 or math.dist(b, q) < 1e-6:
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            l2 = dx * dx + dy * dy
            t = 0.0 if l2 < 1e-12 else max(0.0, min(1.0, ((c[0] - a[0]) * dx + (c[1] - a[1]) * dy) / l2))
            p = (a[0] + t * dx, a[1] + t * dy)
            gap = math.dist(c, p) - r
            if gap >= web or (worst is not None and gap >= worst):
                continue
            if gap > 1e-6 and left.intersection(LineString([c, p])).length < gap - 1e-6:
                continue                        # the way to that edge crosses a cut-out, not a web
            worst = max(gap, 0.0)
    return worst


def generate_cut_paths(design, nesting, compensate_kerf=False, include_labels=True, shared_edges=False):
    from .manufacturing import tool_radius
    kerf = design['material']['kerf'] if compensate_kerf else 0.0
    half = kerf / 2.0
    tool = tool_radius(design)
    relief = (half or tool) if tool else 0.0      # radius the bit actually cuts: the compensation radius when compensated
    n_reliefs = 0
    sheets = [{'index': i, 'paths': [], 'labels': [], 'images': []} for i in range(nesting['sheet_count'])]
    issues = []
    for pm in nesting['placements']:
        comp = find_component(design, pm['id'])
        pl = Plate(design, comp)
        tf = lambda p: [round(v, 4) for v in transform_point(p, pm['rotation'], pm['tx'], pm['ty'])]
        sheet = sheets[pm['sheet']]
        outer_local = offset_polygon(pl.cut, half) if half else pl.cut
        inner = []
        for f, poly in pl.feature_polys:
            path = {'id': f"{pl.id}/{f['id']}", 'part': pl.id, 'type': 'inner', 'feature': f['id'],
                    'feature_kind': f['kind'], 'closed': True}
            if f['shape'] == 'circle':
                path.update(shape='circle', center=tf(f['center']), radius=round(f['diameter'] / 2 - half, 4),
                            _local=poly)
            else:
                pts, arcs = feature_shape(f)
                off = offset_polygon(pts, -half) if half else pts
                path['_collapsed'] = G.signed_area(off) * G.signed_area(pts) <= 0
                if relief:
                    off, arcs, rel = _with_reliefs(off, pts, arcs, True, relief, bool(half))
                    if rel:
                        path['reliefs'] = rel
                path.update(shape='polyline', points=[tf(p) for p in off], _local=poly)
                if arcs:
                    path['arcs'] = [dict(a, center=tf(a['center'])) for a in arcs]
            inner.append(path)
        outer_arcs = _map_arcs(comp['outline'], comp.get('arcs'), pl.cut)
        outer_pts, outer_rel = outer_local, []
        if relief:
            outer_pts, outer_arcs, outer_rel = _with_reliefs(outer_local, pl.cut, outer_arcs, False, relief, bool(half))
        outer = {'id': f'{pl.id}/outer', 'part': pl.id, 'type': 'outer', 'closed': True, 'shape': 'polyline',
                 'points': [tf(p) for p in outer_pts], '_local': pl.cut}
        if outer_arcs:
            outer['arcs'] = [dict(a, center=tf(a['center'])) for a in outer_arcs]
        marks = [{'id': f"{pl.id}/{m['id']}", 'part': pl.id, 'type': m['kind'], 'feature': m['id'], 'shape': 'polyline',
                  'closed': m['closed'], 'depth': m['depth'], 'points': [tf(p) for p in m['points']],
                  **({'arcs': [dict(a, center=tf(a['center'])) for a in m['arcs']]} if m.get('arcs') else {})}
                 for m in comp.get('marks', [])]

        # Validate this part's paths
        if G.self_intersections(outer_local):
            issues.append(_iss('CUT_PATH_SELF_INTERSECTION', pl.id, f"Outer cut path of '{pl.id}' self-intersects."))
        seen = {}
        for p in inner:
            sig = (p['shape'], tuple(map(tuple, p['points'])) if p['shape'] == 'polyline'
                   else (tuple(p['center']), p['radius']))
            if sig in seen:
                issues.append(_iss('DUPLICATE_CUT_PATH', pl.id,
                                   f"'{p['id']}' duplicates '{seen[sig]}'; the duplicate path was dropped "
                                   f"(it would be cut twice)."))
                p['_drop'] = True
                continue
            seen[sig] = p['id']
            if G.polygon_distance(p['_local'], pl.cut) <= 0.0:
                issues.append(_iss('INNER_PATH_CROSSES_OUTER', pl.id,
                                   f"Inner path '{p['id']}' touches or crosses the outer profile."))
        from .validation import _close_pairs        # only paths whose boxes meet can overlap (same pair order)
        for a, b in _close_pairs([p['_local'] for p in inner], 0.0):
            if not inner[a].get('_drop') and not inner[b].get('_drop') and \
                    G.polygons_overlap(inner[a]['_local'], inner[b]['_local']):
                issues.append(_iss('OVERLAPPING_CUT_PATHS', pl.id,
                                   f"Cut paths '{inner[a]['id']}' and '{inner[b]['id']}' overlap."))
        for p in inner:                 # a cut-out narrower than the kerf would come out inverted or with a negative radius
            if (p['shape'] == 'circle' and p['radius'] <= 0) or p.pop('_collapsed', False):
                issues.append(_iss('CUT_PATH_DEGENERATE', pl.id, f"Cut path '{p['id']}' collapses after kerf compensation "
                                                                  f"({kerf:g} mm kerf); the cut-out is too small for the tool."))
        # Dimension check: every compensated edge must lie exactly kerf/2 outside its design edge
        drift = _offset_error(pl.cut, outer_local, half)
        if drift > 0.005:
            issues.append(_iss('DIMENSION_DRIFT', pl.id, f"Cut path of '{pl.id}' deviates from design dimensions "
                                                          f"by {drift:.3f} mm."))
        if relief:
            kept = [p for p in inner if not p.get('_drop')]
            issues += _router_issues(pl, relief, outer_rel + [rc for p in kept for rc in p.get('reliefs', [])], kept, design)
            for p, rel in [(outer, outer_rel)] + [(p, p.get('reliefs', [])) for p in kept]:
                if rel:
                    p['reliefs'] = [{'corner': tf(q), 'center': tf(c), 'radius': round(relief, 4)} for q, c in rel]
                    n_reliefs += len(rel)

        for face in sorted({d['face'] for d in comp.get('decals', [])}) if comp.get('colors') else ():
            # the face colour is printed under the artwork (white lettering on a red board must not land on white paper)
            sheet.setdefault('print_base', []).append({'part': pl.id, 'face': face, 'color': comp['colors'][face],
                                                       'points': [tf(q) for q in pl.cut]})
        for d in comp.get('decals', []):        # printed artwork: never cut, exported as print sheets
            e = {'id': f"{pl.id}/{d['id']}", 'part': pl.id, 'face': d['face'], 'color': d['color']}
            if d.get('points'):
                e['points'] = [tf(q) for q in d['points']]
            else:
                e.update(lines=[[tf(q) for q in ln] for ln in d['lines']], width=d['width'])
            sheet.setdefault('decals', []).append(e)
        for im in comp.get('images', []):       # raster engraving: placed by its corners (top-left, top-right, bottom-left)
            sheet['images'].append({'id': f"{pl.id}/{im['id']}", 'part': pl.id, 'src': im['src'],
                                    'corners': [tf(q) for q in im['corners']]})
        for h in comp.get('hinges', []):        # living hinge: open through-cuts, never kerf-offset, cut before the outline
            inner += [{'id': f"{pl.id}/{h['id']}-{k + 1}", 'part': pl.id, 'type': 'inner', 'feature': h['id'],
                       'feature_kind': 'hinge', 'shape': 'polyline', 'closed': False, 'points': [tf(a), tf(b)]}
                      for k, (a, b) in enumerate(h['lines'])]
        order = len(sheet['paths'])
        for p in marks:                 # engrave / pocket while the part is still held by the sheet
            p['order'] = order
            order += 1
            sheet['paths'].append(p)
        for p in inner:
            if not p.pop('_drop', False):
                p.pop('_local', None)
                p['order'] = order
                order += 1
                sheet['paths'].append(p)
        outer.pop('_local')
        outer['order'] = order
        sheet['paths'].append(outer)
        if include_labels:
            lp, room = label_point(pl)
            size = max(2.0, min(6.0, room * 0.7))
            sheet['labels'].append({'part': pl.id, 'text': pl.id, 'position': tf(lp), 'size': round(size, 2)})
    if shared_edges:
        for sheet in sheets:
            _share_edges(sheet)
    counts = {'outer': sum(1 for s in sheets for p in s['paths'] if p['type'] == 'outer'),
              'inner': sum(1 for s in sheets for p in s['paths'] if p['type'] == 'inner')}
    marks = sum(1 for s in sheets for p in s['paths'] if p['type'] in ('engrave', 'pocket'))
    if marks:
        counts['marks'] = marks
    out = {'kerf_compensation': kerf, 'sheets': sheets, 'issues': issues, 'counts': counts}
    if design.get('process'):
        out['process'] = dict(design['process'], **({'relief_radius': round(relief, 4), 'reliefs': n_reliefs}
                                                    if relief else {}))
    return out


def _offset_error(orig, off, d):
    n = len(orig)
    worst = 0.0
    for i in range(n):
        a, b = orig[i], orig[(i + 1) % n]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 1e-9:
            continue
        nx, ny = (b[1] - a[1]) / L, -(b[0] - a[0]) / L
        for q in (off[i], off[(i + 1) % n]):
            worst = max(worst, abs((q[0] - a[0]) * nx + (q[1] - a[1]) * ny - d))
    return worst


def _iss(code, part, msg):
    return {'code': code, 'severity': 'error', 'components': [part], 'message': msg}


def label_strokes(lb):
    """A part label as single-stroke polylines in sheet coordinates (y down), centred on its position."""
    from .strokefont import text_strokes
    x, y, size = lb['position'][0], lb['position'][1], lb['size']
    base = y + size / 2                         # cap height = size; the label is centred vertically on y
    return [[(u, round(base - v, 4)) for u, v in stroke] for stroke in text_strokes(lb['text'], x, 0.0, size, 'center')]


def _fmt(v):
    return f'{v:.3f}'.rstrip('0').rstrip('.')


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------

def _esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _svg_d(p):
    start, segs = path_segments(p['points'], p.get('arcs'), p.get('closed', True))
    d = [f'M{_fmt(start[0])},{_fmt(start[1])}']
    for sg in segs:
        x, y = sg[1]
        if sg[0] == 'L':
            d.append(f'L{_fmt(x)},{_fmt(y)}')
        else:
            r, sweep = sg[3], sg[4]
            d.append(f'A{_fmt(r)},{_fmt(r)} 0 {int(abs(sweep) > math.pi)} {int(sweep > 0)} {_fmt(x)},{_fmt(y)}')
    return ' '.join(d) + (' Z' if p.get('closed', True) else '')


def sheet_print_svg(design, nesting, cut, index, face):
    """Print artwork of one sheet (colouring on), or None when it has none on that face: every part's decals at 1:1,
    placed exactly like the cut sheet, over each decorated part's face colour, with the part outlines as light-grey
    registration guides. Print it straight on
    the sheet (UV printer) or on paper / sticker film laid on it before cutting. The back is mirrored left to right, so
    it lines up once the sheet is turned over about its vertical edge."""
    sheet = cut['sheets'][index]
    decals = [d for d in sheet.get('decals', []) if d['face'] == face]
    if not decals:
        return None
    sh = nesting['sheet']
    w, h = sh['width'], sh['height']
    X = (lambda x: w - x) if face == 'back' else (lambda x: x)
    pts = lambda ps: ' '.join(f'{_fmt(X(x))},{_fmt(y)}' for x, y in ps)
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<!-- {_esc(design["name"])} | sheet {index + 1} of {nesting["sheet_count"]} | print artwork, {face} faces'
           + (' (mirrored: turn the sheet over about its vertical edge)' if face == 'back' else '')
           + ' | 1 user unit = 1 mm | grey outlines are registration guides, not cut -->',
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(w)}mm" height="{_fmt(h)}mm" viewBox="0 0 {_fmt(w)} {_fmt(h)}">',
           f'  <g id="FACE_COLOUR">']
    for b in sheet.get('print_base', []):
        if b['face'] == face:
            out.append(f'    <polygon data-part="{_esc(b["part"])}" fill="{b["color"]}" points="{pts(b["points"])}"/>')
    out += ['  </g>', '  <g id="GUIDES" fill="none" stroke="#bbbbbb" stroke-width="0.3">']
    for p in sheet['paths']:
        if p['type'] == 'outer' and p.get('points'):
            out.append(f'    <polygon data-part="{_esc(p["part"])}" points="{pts(p["points"])}"/>')
    out.append('  </g>')
    out.append('  <g id="PRINT">')
    for d in decals:
        attrs = f'id="{_esc(d["id"])}" data-part="{_esc(d["part"])}"'
        if d.get('points'):
            out.append(f'    <polygon {attrs} fill="{d["color"]}" points="{pts(d["points"])}"/>')
        else:
            for k, ln in enumerate(d['lines']):
                out.append(f'    <polyline id="{_esc(d["id"])}-{k + 1}" data-part="{_esc(d["part"])}" fill="none" '
                           f'stroke="{d["color"]}" stroke-width="{_fmt(d["width"])}" stroke-linecap="round" '
                           f'stroke-linejoin="round" points="{pts(ln)}"/>')
    out.append('  </g>')
    out.append('</svg>')
    return '\n'.join(out) + '\n'


def sheet_svg(design, nesting, cut, index, labels=True):
    from .booklet import sheet_stock_label
    sh = nesting['sheet']
    w, h = sh['width'], sh['height']
    sheet = cut['sheets'][index]
    out = [f'<?xml version="1.0" encoding="UTF-8"?>',
           f'<!-- {_esc(design["name"])} | sheet {index + 1} of {nesting["sheet_count"]} | '
           f'{_esc(sheet_stock_label(nesting, index, design["material"]))} | 1 user unit = 1 mm | kerf compensation '
           f'{cut["kerf_compensation"]} mm | the page is the sheet: nothing else is drawn, so nothing else is cut -->',
           f'<!-- {LEGEND} -->',
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(w)}mm" height="{_fmt(h)}mm" '
           f'viewBox="0 0 {_fmt(w)} {_fmt(h)}">']
    if sheet.get('images'):                     # raster engraving first, like the vector engraving
        out.append('  <g id="ENGRAVE_IMAGE">')
        for im in sheet['images']:
            (x0, y0), (x1, y1), (x2, y2) = im['corners']
            m = ' '.join(_fmt(v) for v in (x1 - x0, y1 - y0, x2 - x0, y2 - y0, x0, y0))
            out.append(f'    <image id="{_esc(im["id"])}" data-part="{_esc(im["part"])}" x="0" y="0" width="1" height="1" '
                       f'preserveAspectRatio="none" transform="matrix({m})" href="{_esc(im["src"])}"/>')
        out.append('  </g>')
    for kind in ('engrave', 'pocket', 'inner', 'outer'):
        layer, color, _ = LAYERS[kind]
        paths = sorted((p for p in sheet['paths'] if p['type'] == kind), key=lambda p: p['order'])
        if not paths and kind in ('engrave', 'pocket'):
            continue
        out.append(f'  <g id="{layer}" fill="none" stroke="{color}" stroke-width="{HAIRLINE}">')
        for p in paths:
            attrs = f'id="{_esc(p["id"])}" data-part="{_esc(p["part"])}" data-order="{p["order"]}"'
            if p.get('feature_kind'):
                attrs += f' data-kind="{p["feature_kind"]}"'
            if p.get('depth'):
                attrs += f' data-depth="{_fmt(p["depth"])}"'
            if p['shape'] == 'circle':
                out.append(f'    <circle {attrs} cx="{_fmt(p["center"][0])}" cy="{_fmt(p["center"][1])}" '
                           f'r="{_fmt(p["radius"])}"/>')
            else:
                out.append(f'    <path {attrs} d="{_svg_d(p)}"/>')
        out.append('  </g>')
    if labels and sheet['labels']:              # single-stroke text: engraved as lines, no font needed
        layer, color, _ = LAYERS['label']
        out.append(f'  <g id="{layer}" fill="none" stroke="{color}" stroke-width="{HAIRLINE}">')
        for lb in sheet['labels']:
            d = ' '.join('M' + ' L'.join(f'{_fmt(x)},{_fmt(y)}' for x, y in st) for st in label_strokes(lb))
            out.append(f'    <path data-part="{_esc(lb["part"])}" data-text="{_esc(lb["text"])}" d="{d}"/>')
        out.append('  </g>')
    out.append('</svg>')
    return '\n'.join(out) + '\n'


# ---------------------------------------------------------------------------
# DXF (AC1009 / R12 ASCII: readable by virtually every CAM package)
# ---------------------------------------------------------------------------

def sheet_dxf(design, nesting, cut, index, labels=True):
    sh = nesting['sheet']
    sheet = cut['sheets'][index]
    L = []

    def g(code, value):
        L.append(str(code))
        L.append(_fmt(value) if isinstance(value, float) else str(value))

    g(0, 'SECTION'); g(2, 'HEADER')
    g(9, '$ACADVER'); g(1, 'AC1009')
    g(9, '$INSUNITS'); g(70, 4)          # millimetres
    g(9, '$EXTMIN'); g(10, 0.0); g(20, 0.0)
    g(9, '$EXTMAX'); g(10, float(sh['width'])); g(20, float(sh['height']))
    g(0, 'ENDSEC')
    g(0, 'SECTION'); g(2, 'TABLES'); g(0, 'TABLE'); g(2, 'LAYER'); g(70, len(LAYERS))
    for _k, (name, _c, aci) in LAYERS.items():
        g(0, 'LAYER'); g(2, name); g(70, 0); g(62, aci); g(6, 'CONTINUOUS')
    g(0, 'ENDTAB'); g(0, 'ENDSEC')
    g(0, 'SECTION'); g(2, 'ENTITIES')
    H = float(sh['height'])  # DXF is y-up: flip the sheet so the drawing matches the SVG/PDF view
    for p in sorted(sheet['paths'], key=lambda p: p['order']):
        layer = LAYERS[p['type']][0]
        if p['shape'] == 'circle':
            g(0, 'CIRCLE'); g(8, layer); g(10, float(p['center'][0])); g(20, H - p['center'][1]); g(30, 0.0)
            g(40, float(p['radius']))
        else:
            closed = p.get('closed', True)
            # flip to y-up first so arc directions (bulge sign) are computed in DXF space
            flip = lambda q: [float(q[0]), H - q[1]]
            pts = [flip(q) for q in p['points']]
            start, segs = path_segments(pts, [dict(a, center=flip(a['center'])) for a in p.get('arcs', [])], closed)
            verts = [[start, 0.0]]
            for sg in segs:
                if sg[0] == 'A':
                    verts[-1][1] = math.tan(sg[4] / 4)
                verts.append([sg[1], 0.0])
            if closed:
                verts.pop()               # closing vertex == start; the polyline flag closes it
            g(0, 'POLYLINE'); g(8, layer); g(66, 1); g(70, 1 if closed else 0); g(10, 0.0); g(20, 0.0); g(30, 0.0)
            for (x, y), bulge in verts:
                g(0, 'VERTEX'); g(8, layer); g(10, x); g(20, y); g(30, 0.0)
                if bulge:
                    g(42, f'{bulge:.6f}')       # full precision: 3 decimals would bend the arc by ~0.01 mm
            g(0, 'SEQEND'); g(8, layer)
    if labels:                                  # single-stroke text as open polylines (CAM needs no font)
        for lb in sheet['labels']:
            g(999, f"label {lb['part']}")           # DXF comment: which part the strokes below name
            for st in label_strokes(lb):
                g(0, 'POLYLINE'); g(8, LAYERS['label'][0]); g(66, 1); g(70, 0); g(10, 0.0); g(20, 0.0); g(30, 0.0)
                for x, y in st:
                    g(0, 'VERTEX'); g(8, LAYERS['label'][0]); g(10, float(x)); g(20, H - y); g(30, 0.0)
                g(0, 'SEQEND'); g(8, LAYERS['label'][0])
    g(0, 'ENDSEC'); g(0, 'EOF')
    return '\n'.join(L) + '\n'
