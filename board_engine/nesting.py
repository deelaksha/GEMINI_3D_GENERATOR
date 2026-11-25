"""
2D nesting of cut parts onto sheets (paper or board).

Algorithm: MaxRects on each part's cut-profile bounding box at the allowed orientations, opening new
sheets as needed. A few part orders (largest area first, longest side, width, height, perimeter) and two
placement rules (best short side fit, best area fit) are packed and the layout with the fewest sheets is
kept (ties keep the first: largest area, best short side fit). A final pass checks real polygon
overlap/spacing and the usable-area boundary.

Sheet coordinates: millimetres, origin top-left, +y down (paper / SVG convention). A part
is shown as seen from its local +z face, never mirrored:
    sheet = (R(rot)·p).x + tx,  -(R(rot)·p).y + ty
"""
import math

from . import geometry as G
from .deadline import check as check_budget
from .model import Plate, feature_polygon, material_of

SHEET_PRESETS = {
    'A4': (297.0, 210.0), 'A3': (420.0, 297.0), 'A2': (594.0, 420.0),
    'Letter': (279.4, 215.9), 'Tabloid': (431.8, 279.4),
    'board-600x400': (600.0, 400.0), 'board-800x600': (800.0, 600.0),
    'board-1220x610': (1220.0, 610.0), 'board-2440x1220': (2440.0, 1220.0),
}
ROTATION_MODES = ('none', 'orthogonal')


class NestingError(ValueError):
    pass


def resolve_sheet(opts, design):
    preset = opts.get('preset')
    if preset:
        if preset not in SHEET_PRESETS:
            raise NestingError(f"unknown sheet preset '{preset}'; choose one of {sorted(SHEET_PRESETS)}")
        w, h = SHEET_PRESETS[preset]
    else:
        w = float(opts.get('width', design['sheet']['width']))
        h = float(opts.get('height', design['sheet']['height']))
    if opts.get('orientation') == 'portrait':
        w, h = min(w, h), max(w, h)
    elif opts.get('orientation', 'landscape') == 'landscape':
        w, h = max(w, h), min(w, h)
    margin = float(opts.get('margin', 10.0))
    spacing = float(opts.get('spacing', design['sheet'].get('spacing', 6.0)))
    title = float(opts.get('title_block', 0.0))  # reserved strip at the bottom (printed title block)
    for name, v, lo, hi in (('width', w, 20, 5000), ('height', h, 20, 5000), ('margin', margin, 0, 200),
                            ('spacing', spacing, 0, 100), ('title_block', title, 0, 100)):
        if not (lo <= v <= hi):
            raise NestingError(f'{name} must be between {lo} and {hi} mm')
    usable = (margin, margin, w - margin, h - margin - title)
    if usable[2] - usable[0] < 10 or usable[3] - usable[1] < 10:
        raise NestingError('margins leave no usable area on the sheet')
    rot = opts.get('rotation', 'orthogonal')
    if rot not in ROTATION_MODES:
        raise NestingError(f'rotation must be one of {ROTATION_MODES}')
    return {'name': preset or 'custom', 'width': w, 'height': h, 'margin': margin, 'spacing': spacing,
            'title_block': title, 'usable': usable, 'rotation': rot}


def transform_point(p, rot, tx, ty):
    a = math.radians(rot)
    c, s = math.cos(a), math.sin(a)
    x, y = p[0] * c - p[1] * s, p[0] * s + p[1] * c
    return [x + tx, -y + ty]


def _rotated_bbox(poly, rot):
    pts = [transform_point(p, rot, 0, 0) for p in poly]
    return G.bbox(pts)


class _MaxRects:
    def __init__(self, x0, y0, x1, y1, rule='bssf'):
        self.free = [(x0, y0, x1 - x0, y1 - y0)]
        self.rule = rule

    def find(self, w, h):
        best = None
        for fx, fy, fw, fh in self.free:
            if w <= fw + 1e-9 and h <= fh + 1e-9:
                fit = (min(fw - w, fh - h), max(fw - w, fh - h))
                score = (fit + (fy, fx)) if self.rule == 'bssf' else (fw * fh - w * h,) + fit + (fy, fx)
                if best is None or score < best[0]:
                    best = (score, (fx, fy))
        return best

    def place(self, x, y, w, h):
        new = []
        for fx, fy, fw, fh in self.free:
            if x >= fx + fw or x + w <= fx or y >= fy + fh or y + h <= fy:
                new.append((fx, fy, fw, fh))
                continue
            if x > fx:
                new.append((fx, fy, x - fx, fh))
            if x + w < fx + fw:
                new.append((x + w, fy, fx + fw - x - w, fh))
            if y > fy:
                new.append((fx, fy, fw, y - fy))
            if y + h < fy + fh:
                new.append((fx, y + h, fw, fy + fh - y - h))
        # prune contained rectangles
        self.free = [r for i, r in enumerate(new)
                     if not any(j != i and r[0] >= o[0] - 1e-9 and r[1] >= o[1] - 1e-9 and
                                r[0] + r[2] <= o[0] + o[2] + 1e-9 and r[1] + r[3] <= o[1] + o[3] + 1e-9 and
                                (r != o or j < i)
                                for j, o in enumerate(new))]


def part_area(plate):
    a = abs(G.signed_area(plate.cut))
    for _f, poly in plate.feature_polys:
        a -= abs(G.signed_area(poly))
    return a


def stock_key(design, comp):
    """Parts may share a sheet only when they are cut from the same stock board."""
    m = material_of(design, comp)
    return (m['name'], m['type'], m['thickness'])


def _allowed_rotations(pl, sheet):
    """Rotations (deg) a part may take on the sheet. Declared grain must run along the sheet's long side
    (the grain of plywood / veneered and solid stock); grain_locked forbids rotation altogether."""
    grain = pl.comp.get('grain')
    if grain in ('x', 'y'):
        sheet_axis = 'x' if sheet['width'] >= sheet['height'] else 'y'
        return [0.0 if grain == sheet_axis else 90.0], True
    if sheet['rotation'] == 'orthogonal' and not pl.comp.get('grain_locked'):
        return [0.0, 90.0], False
    return [0.0], False


def nest(design, opts=None):
    opts = opts or {}
    sheet = resolve_sheet(opts, design)
    ux0, uy0, ux1, uy1 = sheet['usable']
    sp = sheet['spacing']
    plates = [Plate(design, c) for c in design['components']]

    groups, unplaced = {}, []
    for pl in plates:
        allowed, grain = _allowed_rotations(pl, sheet)
        options = []
        for r in allowed:
            x0, y0, x1, y1 = _rotated_bbox(pl.cut, r)
            w, h = x1 - x0, y1 - y0
            if w <= ux1 - ux0 + 1e-9 and h <= uy1 - uy0 + 1e-9:
                options.append((r, w, h, x0, y0))
        if not options:
            x0, y0, x1, y1 = pl.bbox2d
            unplaced.append({'id': pl.id, 'code': 'PART_EXCEEDS_SHEET',
                             'message': f"'{pl.id}' ({x1 - x0:.1f} x {y1 - y0:.1f} mm) does not fit the usable "
                                        f"{ux1 - ux0:.0f} x {uy1 - uy0:.0f} mm area"
                                        + (" with its grain along the sheet" if grain else
                                           " (rotation not permitted)" if len(allowed) == 1 else "") + "."})
            continue
        groups.setdefault(stock_key(design, pl.comp), []).append((pl, options, grain))

    sheets, placements = [], []
    # Thickest stock first, then by name: deterministic sheet numbering
    for key in sorted(groups, key=lambda k: (-k[2], k[0], k[1])):
        stock = {'material': key[0], 'type': key[1], 'thickness': key[2]}
        first = len(sheets)
        best = None
        for order in _ORDERS:
            items = sorted(groups[key], key=order)
            for rule in ('bssf', 'baf'):
                packed = _pack(items, (ux0, uy0, ux1, uy1), sp, rule)
                if best is None or (len(packed[1]), packed[0]) < (len(best[1]), best[0]):
                    best = packed            # fewer parts left over, then fewer sheets; ties keep the first
        nbins, placed, failed = best
        for pl, bi, r, fx, fy, w, h, bx0, by0, grain in placed:
            placements.append({'id': pl.id, 'name': pl.comp.get('name', pl.id), 'sheet': first + bi,
                               'rotation': r,
                               'tx': fx - bx0, 'ty': fy - by0,  # unrounded: rounding can push a part past the usable edge
                               'bbox': [round(fx, 3), round(fy, 3), round(fx + w, 3), round(fy + h, 3)],
                               'thickness': pl.t, 'area': round(part_area(pl), 2),
                               **({'grain_aligned': True} if grain else {})})
        unplaced.extend({'id': pl.id, 'code': 'NESTING_FAILED', 'message': f"Could not place '{pl.id}'."} for pl in failed)
        sheets.extend({'index': first + i, 'stock': stock} for i in range(nbins))

    nsheets = len(sheets)
    sheet_area = sheet['width'] * sheet['height']
    usable_area = (ux1 - ux0) * (uy1 - uy0)
    used = sum(p['area'] for p in placements)
    total = nsheets * sheet_area
    by_stock = []
    for sh in sheets:
        st = next((x for x in by_stock if x['stock'] == sh['stock']), None)
        if st is None:
            st = {'stock': sh['stock'], 'sheets': 0, 'used_area': 0.0}
            by_stock.append(st)
        st['sheets'] += 1
        st['used_area'] += sum(p['area'] for p in placements if p['sheet'] == sh['index'])
    for st in by_stock:
        st['used_area'] = round(st['used_area'], 1)
        st['efficiency_percent'] = round(100 * st['used_area'] / (st['sheets'] * sheet_area), 2)
    report = {
        'sheet': sheet,
        'sheet_count': nsheets,
        'sheets': sheets,
        'placements': placements,
        'unplaced': unplaced,
        'stats': {
            'total_material_area': round(total, 1),
            'usable_area': round(nsheets * usable_area, 1),
            'used_area': round(used, 1),
            'waste_area': round(total - used, 1),
            'waste_percent': round(100 * (total - used) / total, 2) if total else 0.0,
            'efficiency_percent': round(100 * used / total, 2) if total else 0.0,
            'usable_efficiency_percent': round(100 * used / (nsheets * usable_area), 2) if nsheets else 0.0,
            'by_stock': by_stock,
        },
    }
    report['issues'] = verify_nesting(design, report)
    return report


# part orders tried by the packer: largest area first (the original order, kept on ties), longest side, width,
# height, perimeter -- each on the part's largest allowed bounding box
_dims = lambda it: max(((o[1], o[2]) for o in it[1]), key=lambda wh: wh[0] * wh[1])
_ORDERS = (lambda it: -max(o[1] * o[2] for o in it[1]),
           lambda it: -max(max(o[1], o[2]) for o in it[1]),
           lambda it: -_dims(it)[0],
           lambda it: -_dims(it)[1],
           lambda it: -sum(_dims(it)))


def _pack(items, usable, sp, rule):
    """MaxRects-pack items in the given order. -> (sheets used, [(plate, sheet, rot, x, y, w, h, bx0, by0, grain)],
    [plates that fit no sheet])"""
    ux0, uy0, ux1, uy1 = usable
    bins, placed, failed = [], [], []
    for pl, options, grain in items:
        check_budget()
        for bi, mr in enumerate(bins + [None]):
            if mr is None:
                mr = _MaxRects(ux0, uy0, ux1 + sp, uy1 + sp, rule)  # spacing is added to every item's size
                bins.append(mr)
            best = None
            for r, w, h, bx0, by0 in options:
                hit = mr.find(w + sp, h + sp)
                if hit and (best is None or hit[0] < best[0]):
                    best = (hit[0], hit[1], r, w, h, bx0, by0)
            if best:
                _s, (fx, fy), r, w, h, bx0, by0 = best
                mr.place(fx, fy, w + sp, h + sp)
                placed.append((pl, bi, r, fx, fy, w, h, bx0, by0, grain))
                break
        else:
            failed.append(pl)
            if bins and not any(p[1] == len(bins) - 1 for p in placed):
                bins.pop()
    return len(bins), placed, failed


def placed_geometry(design, placement):
    """Cut outline + feature polygons of a placed part, in sheet coordinates."""
    from .model import find_component
    comp = find_component(design, placement['id'])
    pl = Plate(design, comp)
    tf = lambda p: transform_point(p, placement['rotation'], placement['tx'], placement['ty'])
    return {'outline': [tf(p) for p in pl.cut],
            'features': [{'feature': f, 'polygon': [tf(p) for p in poly],
                          'center': tf(f['center'])} for f, poly in pl.feature_polys]}


def verify_nesting(design, report):
    """Independent check: inside usable area, no polygon overlap, spacing respected."""
    issues = []
    ux0, uy0, ux1, uy1 = report['sheet']['usable']
    sp = report['sheet']['spacing']
    kerf = design['material']['kerf']
    if report['placements'] and sp < kerf - 1e-9:
        # The saw/laser removes `kerf` of material along every cut: closer parts are cut into by their neighbour.
        issues.append({'code': 'SPACING_BELOW_KERF', 'severity': 'error', 'components': [],
                       'message': f"Part spacing {sp:g} mm is less than the {kerf:g} mm kerf: neighbouring cuts "
                                  f"would eat into each other's parts. Use spacing >= {kerf:g} mm."})
    from .model import find_component
    stock_of = {s['index']: s['stock'] for s in report.get('sheets', [])}
    for p in report['placements']:
        st = stock_of.get(p['sheet'])
        key = stock_key(design, find_component(design, p['id']))
        if st is not None and (st['material'], st['type'], st['thickness']) != key:
            issues.append({'code': 'MIXED_STOCK_ON_SHEET', 'severity': 'error', 'components': [p['id']],
                           'message': f"'{p['id']}' ({key[0]}, {key[2]:g} mm) is placed on sheet {p['sheet'] + 1} "
                                      f"of {st['material']} {st['thickness']:g} mm."})
    geo = {p['id']: placed_geometry(design, p)['outline'] for p in report['placements']}
    for p in report['placements']:
        x0, y0, x1, y1 = G.bbox(geo[p['id']])
        if x0 < ux0 - 1e-6 or y0 < uy0 - 1e-6 or x1 > ux1 + 1e-6 or y1 > uy1 + 1e-6:
            issues.append({'code': 'OUTSIDE_USABLE_AREA', 'severity': 'error', 'components': [p['id']],
                           'message': f"'{p['id']}' extends outside the usable sheet area."})
    by_sheet = {}
    for p in report['placements']:
        by_sheet.setdefault(p['sheet'], []).append(p['id'])
    for si, ids in by_sheet.items():
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = geo[ids[i]], geo[ids[j]]
                ba, bb = G.bbox(a), G.bbox(b)
                if ba[0] - sp > bb[2] or bb[0] - sp > ba[2] or ba[1] - sp > bb[3] or bb[1] - sp > ba[3]:
                    continue
                if G.polygons_overlap(a, b):
                    issues.append({'code': 'NESTING_OVERLAP', 'severity': 'error', 'components': [ids[i], ids[j]],
                                   'message': f"'{ids[i]}' and '{ids[j]}' overlap on sheet {si + 1}."})
                elif G.polygon_distance(a, b) < sp - 1e-3:
                    issues.append({'code': 'NESTING_SPACING', 'severity': 'error', 'components': [ids[i], ids[j]],
                                   'message': f"'{ids[i]}' and '{ids[j]}' are closer than {sp} mm on sheet {si + 1}."})
    return issues
