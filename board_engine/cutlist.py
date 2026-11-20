"""
Board identification and cut list: the physical boards to make, not their 3D bounding boxes.

For every component:
  * identity     - id (the stable component id: it survives moves, rotations and resizing), name,
                   purpose (group), material, thickness, world orientation
  * size         - finished length x width from the minimum-area rectangle of the cut profile (independent
                   of how the board is drawn or placed); rectangular vs shaped (true area, perimeter)
  * blank        - the size to cut on the saw: finished size minus edge banding on banded edges, plus the
                   long-point allowance on bevelled mitre edges; each adjustment is listed
  * edges        - length, straight / angled (angle to the length axis), banding, what it is joined to
  * operations   - angled cuts, notches (inside corners), tabs, slots / holes / openings (through cuts),
                   bevels, face and edge drilling (from manufacturing.py)
  * connections  - every joint of the board with the other board, the edge or face involved

Identical boards (same profile, cut-outs, banding and drilling, allowing the board to be turned over or
end for end) are grouped into one cut-list line with a quantity.
"""
import math

from . import geometry as G
from .manufacturing import manufacturing_report
from .model import build_plates, edge_frame, material_of
from .validation import _r, evaluate_joint


def _orientation(plate):
    n = plate.frame.normal
    ny = abs(n[1])
    if ny > 0.9995:
        return {'kind': 'horizontal', 'normal': _r(n, 3)}
    if ny < 0.0175:
        axis = 'X' if abs(n[0]) > 0.9995 else 'Z' if abs(n[2]) > 0.9995 else None
        out = {'kind': 'vertical', 'normal': _r(n, 3)}
        if axis:
            out['faces'] = axis
        else:
            out['yaw_deg'] = _r(math.degrees(math.atan2(n[0], n[2])), 2)
        return out
    return {'kind': 'inclined', 'normal': _r(n, 3), 'tilt_deg': _r(math.degrees(math.acos(min(1.0, ny))), 2)}


def _reflex_vertices(poly):
    n = len(poly)
    out = []
    for i in range(n):
        a, b, c = poly[i - 1], poly[i], poly[(i + 1) % n]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) < -1e-9:
            out.append(i)
    return out


def _is_rect(poly):
    pts = [poly[i] for i in range(len(poly))
           if abs((poly[i][0] - poly[i - 1][0]) * (poly[(i + 1) % len(poly)][1] - poly[i][1]) -
                  (poly[i][1] - poly[i - 1][1]) * (poly[(i + 1) % len(poly)][0] - poly[i][0])) > 1e-6]
    if len(pts) != 4:
        return False
    r = G.oriented_rect(pts)
    return abs(abs(G.signed_area(pts)) - r['length'] * r['width']) < 1e-3 * max(1.0, r['length'] * r['width'])


def _connections(design, comp_id, joint_results):
    out = []
    for j in design['joints']:
        if comp_id not in (j['a'], j['b']):
            continue
        other = j['b'] if j['a'] == comp_id else j['a']
        c = {'joint': j['id'], 'type': j['type'], 'with': other, 'status': j.get('status')}
        if j['type'] == 'tab_slot':
            c['where'] = f"tab {j['tab']}" if j['a'] == comp_id else f"slot {j.get('slot', '?')}"
        elif j['type'] in ('edge_butt', 'hinge'):
            c['where'] = f"edge {j['a_edge']}" if j['a'] == comp_id else 'face'
        elif j['type'] == 'edge_mitre':
            c['where'] = f"edge {j['a_edge'] if j['a'] == comp_id else j['b_edge']}"
        else:
            c['where'] = 'face'
        if j.get('fasteners'):
            c['fasteners'] = j['fasteners']['kind']
        out.append(c)
    return out


def board_entry(design, plate, joint_results, drills):
    comp = plate.comp
    cid = comp['id']
    rect = G.oriented_rect(plate.cut)
    ax = (math.cos(math.radians(rect['angle'])), math.sin(math.radians(rect['angle'])))
    rectangular = _is_rect(plate.cut) and not comp.get('tabs')
    n = len(comp['outline'])
    banding = {b['edge']: b for b in comp.get('edge_banding', [])}
    bevels = {}
    for j in design['joints']:
        res = joint_results.get(j['id']) or {}
        if j['type'] == 'edge_mitre' and res.get('bevel') and cid in (j['a'], j['b']):
            e = j['a_edge'] if j['a'] == cid else j['b_edge']
            bevels[e] = dict(res['bevel'], joint=j['id'], long_point_allowance=res['bevel']['long_point'][cid])
    edges, inward, adjustments = [], [0.0] * n, []
    for i in range(n):
        a, d, _nrm, L = edge_frame(comp['outline'], i)
        ang = math.degrees(math.atan2(d[0] * ax[1] - d[1] * ax[0], d[0] * ax[0] + d[1] * ax[1]))
        rel = abs(ang) % 180.0
        rel = min(rel, 180.0 - rel)              # 0 = along the length, 90 = across
        straight = min(rel, abs(90.0 - rel)) < 0.05
        e = {'index': i, 'length': _r(L, 2), 'cut': 'straight' if straight else 'angled'}
        if not straight:
            e['angle_to_length_deg'] = _r(rel, 2)
        if i in banding:
            e['banding'] = banding[i]
            inward[i] += banding[i]['thickness']
            adjustments.append(f"edge {i}: -{banding[i]['thickness']:g} mm for edge banding")
        if i in bevels:
            e['bevel'] = bevels[i]
            inward[i] -= bevels[i]['long_point_allowance']
            adjustments.append(f"edge {i}: +{bevels[i]['long_point_allowance']:g} mm long point of the "
                               f"{bevels[i]['bevel_deg']:g}° mitre bevel")
        edges.append(e)
    blank_outline = G.offset_edges(comp['outline'], inward) if any(inward) else comp['outline']
    if any(inward) and comp.get('tabs'):
        from .model import cut_outline
        blank_outline = cut_outline(dict(comp, outline=blank_outline))
    elif not any(inward):
        blank_outline = plate.cut
    blank = G.oriented_rect(blank_outline)
    area = abs(G.signed_area(plate.cut)) - sum(abs(G.signed_area(p)) for _f, p in plate.feature_polys)
    ops = {
        'straight_edges': sum(1 for e in edges if e['cut'] == 'straight'),
        'angled_cuts': [{'edge': e['index'], 'angle_to_length_deg': e['angle_to_length_deg']}
                        for e in edges if e['cut'] == 'angled'],
        'notches': [{'vertex': i, 'at': _r(comp['outline'][i], 2)} for i in _reflex_vertices(comp['outline'])],
        'tabs': [{'id': t['id'], 'edge': t['edge'], 'offset': t['offset'], 'width': t['width'], 'depth': t['depth']}
                 for t in comp.get('tabs', [])],
        'through_cuts': [dict({'id': f['id'], 'kind': f['kind'], 'shape': f['shape'], 'center': _r(f['center'], 2)},
                              **({'diameter': f['diameter']} if f['shape'] == 'circle' else
                                 {'width': f['width'], 'height': f['height'], 'angle': f.get('angle', 0.0)}))
                         for f in comp.get('features', [])],
        'bevels': [{'edge': e, **{k: v for k, v in b.items() if k != 'long_point'}} for e, b in sorted(bevels.items())],
        'drilling': [{k: v for k, v in d.items() if k != 'component'} for d in drills if d['component'] == cid],
    }
    process = 'saw' if rectangular and not ops['through_cuts'] and not ops['notches'] else 'cnc'
    grain = comp.get('grain')
    m = material_of(design, comp)
    entry = {
        'id': cid, 'name': comp.get('name', cid), 'purpose': comp.get('group', ''),
        'material': m['name'], 'material_type': m['type'], 'thickness': plate.t,
        'shape': 'rectangular' if rectangular else 'shaped',
        'finished': {'length': _r(rect['length'], 2), 'width': _r(rect['width'], 2),
                     'length_axis_deg': _r(rect['angle'], 3)},
        'blank': {'length': _r(blank['length'], 2), 'width': _r(blank['width'], 2)},
        'adjustments': adjustments,
        'area_mm2': _r(area, 1), 'perimeter_mm': _r(sum(e['length'] for e in edges), 1),
        'grain': 'none' if not grain else
                 ('along length' if abs(math.cos(math.radians(rect['angle'] - (0.0 if grain == 'x' else 90.0)))) > 0.5
                  else 'along width'),
        'orientation': _orientation(plate),
        'process': process,
        'edges': edges,
        'operations': ops,
        'connections': _connections(design, cid, joint_results),
    }
    entry['_sig'] = _signature(comp, plate, rect, drills, banding, bevels)
    return entry


def _signature(comp, plate, rect, drills, banding, bevels):
    """Shape identity in the board's own blank frame, minimised over turning the board over / end for end."""
    a = math.radians(rect['angle'])
    ux, uy = math.cos(a), math.sin(a)
    o = rect['origin']
    L, W = rect['length'], rect['width']

    def canon(p, flip_u, flip_v):
        u = (p[0] - o[0]) * ux + (p[1] - o[1]) * uy
        v = -(p[0] - o[0]) * uy + (p[1] - o[1]) * ux
        return (round(L - u if flip_u else u, 1), round(W - v if flip_v else v, 1))

    best = None
    n = len(comp['outline'])
    for fu in (False, True):
        for fv in (False, True):
            over = fu != fv   # an odd number of flips = the board is turned over: +z and -z faces swap
            verts = tuple(sorted(canon(p, fu, fv) for p in plate.cut))
            feats = tuple(sorted((f['kind'], canon(f['center'], fu, fv), round(f.get('diameter', 0), 1),
                                  round(f.get('width', 0), 1), round(f.get('height', 0), 1)) for f in comp['features']))
            band = tuple(sorted((canon(comp['outline'][e], fu, fv), canon(comp['outline'][(e + 1) % n], fu, fv),
                                 b['thickness']) for e, b in banding.items()))
            bev = tuple(sorted((canon(comp['outline'][e], fu, fv), canon(comp['outline'][(e + 1) % n], fu, fv),
                                b['bevel_deg']) for e, b in bevels.items()))
            dr = tuple(sorted((d['type'], canon(d['position'], fu, fv), d['diameter'], d['depth'],
                               '' if 'face' not in d or d.get('through') else
                               ({'+z': '-z', '-z': '+z'}[d['face']] if over else d['face']))
                              for d in drills if d['component'] == comp['id']))
            sig = (verts, feats, band, bev, dr)
            if best is None or sig < best:
                best = sig
    return best


def cut_list(design, mfg=None):
    """Per-board identification plus the grouped cut list (quantities of identical boards)."""
    mfg = mfg or manufacturing_report(design)
    plates = build_plates(design)
    joint_results = {j['id']: evaluate_joint(design, plates, j) for j in design['joints']
                     if j['a'] in plates and j['b'] in plates}
    boards = [board_entry(design, plates[c['id']], joint_results, mfg['drilling']) for c in design['components']]
    groups = {}
    for b in boards:
        key = (b['material'], b['material_type'], b['thickness'], b['grain'], b['_sig'])
        groups.setdefault(key, []).append(b)
    lines = []
    for key, members in groups.items():
        f = members[0]
        lines.append({'part': f['id'] if len(members) == 1 else f"{f['id']} (x{len(members)})",
                      'ids': [m['id'] for m in members], 'quantity': len(members), 'name': f['name'],
                      'material': f['material'], 'thickness': f['thickness'],
                      'finished_length': f['finished']['length'], 'finished_width': f['finished']['width'],
                      'blank_length': f['blank']['length'], 'blank_width': f['blank']['width'],
                      'grain': f['grain'], 'shape': f['shape'], 'process': f['process'],
                      'banded_edges': sum(1 for e in f['edges'] if 'banding' in e),
                      'drilling': len(f['operations']['drilling'])})
    lines.sort(key=lambda r: (r['material'], -r['thickness'], -r['blank_length'] * r['blank_width'], r['part']))
    for b in boards:
        b.pop('_sig')
    totals = {}
    for b in boards:
        k = f"{b['material']} {b['thickness']:g} mm"
        t = totals.setdefault(k, {'boards': 0, 'area_m2': 0.0, 'banding_m': 0.0})
        t['boards'] += 1
        t['area_m2'] = round(t['area_m2'] + b['area_mm2'] / 1e6, 4)
        t['banding_m'] = round(t['banding_m'] + sum(e['length'] for e in b['edges'] if 'banding' in e) / 1000, 3)
    return {'units': 'mm', 'note': 'Finished = designed part size. Blank = size to cut (banding and mitre long '
                                   'points applied). Kerf falls on the waste side of every cut.',
            'boards': boards, 'lines': lines, 'totals': totals}
