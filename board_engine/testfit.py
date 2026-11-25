"""
Test-fit piece for the laser: find the slot clearance that fits the real board before cutting a whole job.

A comb with one slot per candidate clearance (slot = measured thickness + clearance) and a tab cut from the same
sheet. Push the tab into each slot; the snuggest one that still goes in by hand is the clearance to enter as the
"fit" in the laser settings. Written with the same writers as the cut files (layers, hairlines, kerf compensation).
"""
from .cutpaths import offset_polygon, sheet_dxf, sheet_svg

FITS = (-0.1, 0.0, 0.1, 0.2, 0.3)
TOOTH, MARGIN, TAB = 8.0, 6.0, (40.0, 25.0)


def _comb(t, fits):
    """CCW outline (y up) of the comb: slots open at the top edge, one per clearance, left to right."""
    depth = max(10.0, 2 * t)
    widths = [t + f for f in fits]
    w = TOOTH + sum(x + TOOTH for x in widths)
    h = depth + 16.0                       # room under the slots for the engraved values
    top, x, slots = [], w - TOOTH, []
    for sw in reversed(widths):            # walk the top edge right to left, dipping into each slot
        top += [[x, h], [x, h - depth], [x - sw, h - depth], [x - sw, h]]
        slots.append((x - sw / 2, sw))
        x -= sw + TOOTH
    return [[0.0, 0.0], [w, 0.0], [w, h]] + top + [[0.0, h]], w, h, list(reversed(slots)), depth


def test_fit_files(thickness, kerf, fits=FITS):
    """-> {'svg': str, 'dxf': str} for a comb + tab sized for `thickness` (mm) and compensated for `kerf` (mm)."""
    comb, cw, ch, slots, depth = _comb(thickness, fits)
    tw, th = TAB
    sheet_w, sheet_h = cw + tw + 3 * MARGIN, max(ch, th) + 2 * MARGIN
    to_sheet = lambda pts, ox, oy, height: [[round(ox + x, 4), round(oy + height - y, 4)] for x, y in pts]   # y down
    tab = [[0.0, 0.0], [tw, 0.0], [tw, th], [0.0, th]]
    half = kerf / 2.0
    paths = [
        {'id': 'COMB/outer', 'part': 'COMB', 'type': 'outer', 'shape': 'polyline', 'closed': True, 'order': 0,
         'points': to_sheet(offset_polygon(comb, half), MARGIN, MARGIN, ch)},
        {'id': 'TAB/outer', 'part': 'TAB', 'type': 'outer', 'shape': 'polyline', 'closed': True, 'order': 1,
         'points': to_sheet(offset_polygon(tab, half), 2 * MARGIN + cw, MARGIN, th)},
    ]
    size = 3.5
    labels = [{'part': 'COMB', 'text': f'{f:+.1f}', 'size': size,
               'position': [round(MARGIN + x, 3), round(MARGIN + depth + 5.0, 3)]} for (x, _w), f in zip(slots, fits)]
    labels.append({'part': 'TAB', 'text': f'{thickness:g} mm', 'size': size,
                   'position': [round(2 * MARGIN + cw + tw / 2, 3), round(MARGIN + th / 2, 3)]})
    design = {'name': f'Test fit {thickness:g} mm', 'material': {'name': f'{thickness:g} mm board', 'thickness': thickness}}
    nesting = {'sheet': {'width': round(sheet_w, 3), 'height': round(sheet_h, 3)}, 'sheet_count': 1, 'sheets': []}
    cut = {'kerf_compensation': kerf, 'sheets': [{'index': 0, 'paths': paths, 'labels': labels}]}
    return {'svg': sheet_svg(design, nesting, cut, 0), 'dxf': sheet_dxf(design, nesting, cut, 0),
            'slots': [{'clearance': f, 'slot_width': round(thickness + f, 3)} for f in fits]}
