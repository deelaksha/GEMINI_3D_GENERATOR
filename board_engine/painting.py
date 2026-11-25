"""
Painting guide (colouring on): per colour, which parts and faces get it and the paint area, so finishes can be bought
and applied before or after cutting. Face area = the board's cut profile minus its cut-outs; edge area = outline and
cut-out perimeters x thickness.
"""
import math

from .colors import color_name
from .model import Plate
from .nesting import part_area


def _perimeter(poly):
    return sum(math.dist(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def painting_guide(design):
    colors = {}
    for comp in design['components']:
        cols = comp.get('colors')
        if not cols:
            continue
        pl = Plate(design, comp)
        face = part_area(pl)
        edges = (_perimeter(pl.cut) + sum(_perimeter(poly) for _f, poly in pl.feature_polys)) * pl.t
        for side, area in (('front', face), ('back', face), ('edges', edges)):
            c = colors.setdefault(cols[side], {'color': cols[side], 'name': color_name(cols[side]), 'parts': {}, 'area_mm2': 0.0})
            c['parts'].setdefault(comp['id'], []).append(side)
            c['area_mm2'] += area
    out = [{'color': c['color'], 'name': c['name'], 'area_m2': round(c['area_mm2'] / 1e6, 4),
            'parts': [{'id': pid, 'faces': faces} for pid, faces in sorted(c['parts'].items())]}
           for c in sorted(colors.values(), key=lambda c: -c['area_mm2'])]
    return {'colors': out, 'note': 'Areas are one coat on the finished part; add the usual allowance for waste and coats.'}


def painting_lines(guide):
    """The guide as text lines for the cut-file README."""
    out = ['Painting   : ' + ', '.join(f"{c['name']} {c['color']} {c['area_m2']:g} m2" for c in guide['colors'])]
    for c in guide['colors']:
        parts = '; '.join(f"{p['id']} ({'/'.join(p['faces'])})" for p in c['parts'])
        out.append(f"  {c['name']} {c['color']}: {parts}")
    return out
