"""
Laser job report: per sheet the cut and engrave length, the number of pierces, an estimated machine time from the
user's speeds, the offcut area, and the material cost when a sheet price is given.

Lengths are measured on the cut paths that go to the machine (true arc lengths, circles as 2*pi*r). The time is an
estimate: cutting and engraving at constant speed plus a fixed time per pierce; travel moves are not included.
"""
import math

from .cutpaths import label_strokes, path_segments

CUT_SPEED, ENGRAVE_SPEED, PIERCE_S = 10.0, 100.0, 0.3     # mm/s, mm/s, s per path start


def path_length(p):
    if p['shape'] == 'circle':
        return 2 * math.pi * p['radius']
    start, segs = path_segments(p['points'], p.get('arcs'), p.get('closed', True))
    total, prev = 0.0, start
    for sg in segs:
        total += abs(sg[3] * sg[4]) if sg[0] == 'A' else math.dist(prev, sg[1])
        prev = sg[1]
    return total


def job_report(nesting, cut, machine=None):
    m = machine or {}
    cut_speed, engrave_speed = m.get('cut_speed') or CUT_SPEED, m.get('engrave_speed') or ENGRAVE_SPEED
    sheet_area = nesting['sheet']['width'] * nesting['sheet']['height']
    sheets = []
    for sh in cut['sheets']:
        cut_len = sum(path_length(p) for p in sh['paths'] if p['type'] in ('outer', 'inner', 'hinge'))
        engrave_len = sum(path_length(p) for p in sh['paths'] if p['type'] in ('engrave', 'pocket')) + sum(
            math.dist(a, b) for lb in sh.get('labels', []) for st in label_strokes(lb) for a, b in zip(st, st[1:]))
        pierces = len(sh['paths'])
        used = sum(p['area'] for p in nesting['placements'] if p['sheet'] == sh['index'])
        seconds = cut_len / cut_speed + engrave_len / engrave_speed + pierces * PIERCE_S
        sheets.append({'sheet': sh['index'] + 1, 'cut_length_m': round(cut_len / 1000, 2),
                       'engrave_length_m': round(engrave_len / 1000, 2), 'pierces': pierces,
                       'minutes': round(seconds / 60, 1), 'offcut_m2': round((sheet_area - used) / 1e6, 3)})
    total = lambda k: round(sum(s[k] for s in sheets), 2)
    report = {'cut_speed': cut_speed, 'engrave_speed': engrave_speed, 'sheets': sheets,
              'totals': {'sheets': len(sheets), 'cut_length_m': total('cut_length_m'),
                         'engrave_length_m': total('engrave_length_m'), 'pierces': sum(s['pierces'] for s in sheets),
                         'minutes': round(sum(s['minutes'] for s in sheets), 1), 'offcut_m2': round(total('offcut_m2'), 3)},
              'note': 'Estimate: constant cut / engrave speed plus a pierce time per path; travel moves not included.'}
    if m.get('sheet_price') is not None:
        report['totals']['material_cost'] = round(len(sheets) * m['sheet_price'], 2)
    return report


def job_lines(report):
    """The report as text lines for the cut-file README."""
    t = report['totals']
    out = [f"Job        : {t['sheets']} sheet(s), cut {t['cut_length_m']:g} m, engrave {t['engrave_length_m']:g} m, "
           f"{t['pierces']} pierces, about {t['minutes']:g} min at {report['cut_speed']:g} mm/s cutting / "
           f"{report['engrave_speed']:g} mm/s engraving"
           + (f", material {t['material_cost']:g}" if 'material_cost' in t else '') + f" ({report['note']})"]
    out += [f"  sheet {s['sheet']}: cut {s['cut_length_m']:g} m, engrave {s['engrave_length_m']:g} m, {s['pierces']} pierces, "
            f"~{s['minutes']:g} min, offcut {s['offcut_m2']:g} m2" for s in report['sheets']]
    return out
