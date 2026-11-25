"""
LightBurn project (.lbrn2) for one cutting sheet: the layers already set to cut / engrave with the user's speeds,
in the order the job must run (engrave, labels, inner cuts, outlines).

Format (LightBurn does not publish it; checked against real .lbrn2 files written by LightBurn 1.x / 2.x):
  <CutSetting type="Cut"> with index (palette colour: 0 black, 1 blue, 2 red, 3 green, 6 cyan), name, minPower /
  maxPower (%), speed (mm/s), priority (run order). A <Shape Type="Path" CutIndex=..> holds
  <VertList>V<x> <y>c0x1c1x1...</VertList> (straight vertices) and <PrimList>: "LineClosed" for a closed polygon,
  "L0 1L1 2..." for an open one; circles are <Shape Type="Ellipse" Rx Ry> centred by their XForm.
  Millimetres, +y up (the sheet's y-down coordinates are flipped). Arcs are written as short lines.
Power values are starting points: set them once for your laser and material, LightBurn keeps them per layer.
Raster images are not included (use the SVG for those).
"""
import math
from xml.sax.saxutils import quoteattr

from .cutpaths import label_strokes, path_segments
from .jobreport import CUT_SPEED, ENGRAVE_SPEED

# path type -> (palette index, layer name, run order, cut?)
LAYERS = {'engrave': (6, 'Engrave', 0, False), 'pocket': (3, 'Pocket', 1, False), 'label': (0, 'Labels', 2, False),
          'inner': (1, 'Cut inner first', 3, True), 'outer': (2, 'Cut outline', 4, True)}
ARC_STEP = 0.5   # mm of arc per line segment


def _fmt(v):
    return f'{v:.4f}'.rstrip('0').rstrip('.') or '0'


def _points(p):
    """Path vertices with arcs expanded to short lines (sheet coordinates)."""
    start, segs = path_segments(p['points'], p.get('arcs'), p.get('closed', True))
    pts, prev = [start], start
    for sg in segs:
        if sg[0] == 'A':
            _end, c, r, sweep = sg[1], sg[2], sg[3], sg[4]
            a0 = math.atan2(prev[1] - c[1], prev[0] - c[0])
            n = max(2, int(math.ceil(abs(r * sweep) / ARC_STEP)))
            pts += [[c[0] + r * math.cos(a0 + sweep * k / n), c[1] + r * math.sin(a0 + sweep * k / n)] for k in range(1, n)]
        pts.append(sg[1])
        prev = sg[1]
    if p.get('closed', True) and len(pts) > 1 and math.dist(pts[0], pts[-1]) < 1e-6:
        pts.pop()
    return pts


def _path_shape(index, pts, closed, H):
    verts = ''.join(f'V{_fmt(x)} {_fmt(H - y)}c0x1c1x1' for x, y in pts)
    prims = 'LineClosed' if closed else ''.join(f'L{i} {i + 1}' for i in range(len(pts) - 1))
    return (f'    <Shape Type="Path" CutIndex="{index}">\n        <XForm>1 0 0 1 0 0</XForm>\n'
            f'        <VertList>{verts}</VertList>\n        <PrimList>{prims}</PrimList>\n    </Shape>')


def sheet_lbrn2(design, nesting, cut, index, machine=None, labels=True):
    m = machine or {}
    cut_speed, engrave_speed = m.get('cut_speed') or CUT_SPEED, m.get('engrave_speed') or ENGRAVE_SPEED
    H = float(nesting['sheet']['height'])
    sheet = cut['sheets'][index]
    by_layer = {k: [] for k in LAYERS}
    for p in sorted(sheet['paths'], key=lambda q: q['order']):
        idx = LAYERS[p['type']][0]
        if p['shape'] == 'circle':
            r = _fmt(p['radius'])
            by_layer[p['type']].append(f'    <Shape Type="Ellipse" CutIndex="{idx}" Rx="{r}" Ry="{r}">\n'
                                       f'        <XForm>1 0 0 1 {_fmt(p["center"][0])} {_fmt(H - p["center"][1])}</XForm>\n'
                                       f'    </Shape>')
        else:
            by_layer[p['type']].append(_path_shape(idx, _points(p), p.get('closed', True), H))
    if labels:
        for lb in sheet['labels']:
            by_layer['label'] += [_path_shape(LAYERS['label'][0], st, False, H) for st in label_strokes(lb)]
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<LightBurnProject AppVersion="1.6.00" FormatVersion="1" MaterialHeight="0" MirrorX="False" MirrorY="False">',
           f'    <!-- {quoteattr(design["name"])[1:-1]} | sheet {index + 1} of {nesting["sheet_count"]} | mm, 1:1 | '
           f'kerf compensation {cut["kerf_compensation"]} mm (set the layer kerf offset to 0) -->']
    for kind, (idx, name, prio, is_cut) in sorted(LAYERS.items(), key=lambda kv: kv[1][2]):
        if not by_layer[kind]:
            continue
        power, speed = (60, cut_speed) if is_cut else (20, engrave_speed)
        out += ['    <CutSetting type="Cut">', f'        <index Value="{idx}"/>', f'        <name Value={quoteattr(name)}/>',
                f'        <minPower Value="{power}"/>', f'        <maxPower Value="{power}"/>',
                f'        <speed Value="{_fmt(speed)}"/>', '        <numPasses Value="1"/>',
                f'        <priority Value="{prio}"/>', '    </CutSetting>']
    for kind, (_idx, _n, _prio, _c) in sorted(LAYERS.items(), key=lambda kv: kv[1][2]):
        out += by_layer[kind]
    out.append('</LightBurnProject>')
    return '\n'.join(out) + '\n'
