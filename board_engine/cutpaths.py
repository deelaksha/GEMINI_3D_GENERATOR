"""
Machine-independent cutting paths, plus SVG and DXF writers.

Each placed part yields:
  * one OUTER closed path (cut profile incl. tabs and notches) - cut last
  * one INNER closed path per feature (slots, holes, openings)  - cut first
Kerf compensation (optional) moves outer paths outward and inner paths inward by kerf/2 so
that the finished part keeps its design dimensions.
"""
import math

from . import geometry as G
from .model import Plate, find_component
from .nesting import transform_point

LAYERS = {'outer': ('CUT_OUTER', '#e11d48', 1), 'inner': ('CUT_INNER', '#2563eb', 5),
          'label': ('ENGRAVE_LABELS', '#111827', 7)}


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


def generate_cut_paths(design, nesting, compensate_kerf=False, include_labels=True):
    kerf = design['material']['kerf'] if compensate_kerf else 0.0
    half = kerf / 2.0
    sheets = [{'index': i, 'paths': [], 'labels': []} for i in range(nesting['sheet_count'])]
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
                path.update(shape='polyline', points=[tf(p) for p in (offset_polygon(poly, -half) if half else poly)],
                            _local=poly)
            inner.append(path)
        outer = {'id': f'{pl.id}/outer', 'part': pl.id, 'type': 'outer', 'closed': True, 'shape': 'polyline',
                 'points': [tf(p) for p in outer_local], '_local': pl.cut}

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
        for a in range(len(inner)):
            for b in range(a + 1, len(inner)):
                if not inner[a].get('_drop') and not inner[b].get('_drop') and \
                        G.polygons_overlap(inner[a]['_local'], inner[b]['_local']):
                    issues.append(_iss('OVERLAPPING_CUT_PATHS', pl.id,
                                       f"Cut paths '{inner[a]['id']}' and '{inner[b]['id']}' overlap."))
        # Dimension check: every compensated edge must lie exactly kerf/2 outside its design edge
        drift = _offset_error(pl.cut, outer_local, half)
        if drift > 0.005:
            issues.append(_iss('DIMENSION_DRIFT', pl.id, f"Cut path of '{pl.id}' deviates from design dimensions "
                                                          f"by {drift:.3f} mm."))

        order = len(sheet['paths'])
        for p in inner:
            if not p.pop('_drop', False):
                p.pop('_local')
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
    return {'kerf_compensation': kerf, 'sheets': sheets, 'issues': issues,
            'counts': {'outer': sum(1 for s in sheets for p in s['paths'] if p['type'] == 'outer'),
                       'inner': sum(1 for s in sheets for p in s['paths'] if p['type'] == 'inner')}}


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


def _fmt(v):
    return f'{v:.3f}'.rstrip('0').rstrip('.')


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------

def _esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def sheet_svg(design, nesting, cut, index, labels=True):
    sh = nesting['sheet']
    w, h = sh['width'], sh['height']
    sheet = cut['sheets'][index]
    out = [f'<?xml version="1.0" encoding="UTF-8"?>',
           f'<!-- {_esc(design["name"])} | sheet {index + 1} of {nesting["sheet_count"]} | '
           f'{_esc(design["material"]["name"])} | 1 user unit = 1 mm | kerf compensation '
           f'{cut["kerf_compensation"]} mm -->',
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(w)}mm" height="{_fmt(h)}mm" '
           f'viewBox="0 0 {_fmt(w)} {_fmt(h)}">',
           f'  <rect id="sheet-boundary" x="0" y="0" width="{_fmt(w)}" height="{_fmt(h)}" fill="none" '
           f'stroke="#9ca3af" stroke-width="0.2" stroke-dasharray="2 2"/>']
    for kind in ('inner', 'outer'):
        layer, color, _ = LAYERS[kind]
        out.append(f'  <g id="{layer}" fill="none" stroke="{color}" stroke-width="0.1">')
        for p in sorted((p for p in sheet['paths'] if p['type'] == kind), key=lambda p: p['order']):
            attrs = f'id="{_esc(p["id"])}" data-part="{_esc(p["part"])}" data-order="{p["order"]}"'
            if p.get('feature_kind'):
                attrs += f' data-kind="{p["feature_kind"]}"'
            if p['shape'] == 'circle':
                out.append(f'    <circle {attrs} cx="{_fmt(p["center"][0])}" cy="{_fmt(p["center"][1])}" '
                           f'r="{_fmt(p["radius"])}"/>')
            else:
                d = 'M' + ' L'.join(f'{_fmt(x)},{_fmt(y)}' for x, y in p['points']) + ' Z'
                out.append(f'    <path {attrs} d="{d}"/>')
        out.append('  </g>')
    if labels:
        layer, color, _ = LAYERS['label']
        out.append(f'  <g id="{layer}" fill="{color}" font-family="Helvetica, Arial, sans-serif" text-anchor="middle">')
        for lb in sheet['labels']:
            out.append(f'    <text x="{_fmt(lb["position"][0])}" y="{_fmt(lb["position"][1] + lb["size"] * 0.35)}" '
                       f'font-size="{_fmt(lb["size"])}">{_esc(lb["text"])}</text>')
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
            g(0, 'POLYLINE'); g(8, layer); g(66, 1); g(70, 1); g(10, 0.0); g(20, 0.0); g(30, 0.0)
            for x, y in p['points']:
                g(0, 'VERTEX'); g(8, layer); g(10, float(x)); g(20, H - y); g(30, 0.0)
            g(0, 'SEQEND'); g(8, layer)
    if labels:
        for lb in sheet['labels']:
            g(0, 'TEXT'); g(8, LAYERS['label'][0]); g(10, float(lb['position'][0])); g(20, H - lb['position'][1])
            g(30, 0.0); g(40, float(lb['size'])); g(1, lb['text']); g(72, 1); g(11, float(lb['position'][0]))
            g(21, H - lb['position'][1]); g(31, 0.0)
    g(0, 'ENDSEC'); g(0, 'EOF')
    return '\n'.join(L) + '\n'
