"""
Check a design against the sizes written in the requirements ("Length 1200 mm, width 600 mm, height 750 mm",
"1.2 m long", "height: 75 cm", "1200 x 600 x 750 mm" = length x depth x height).

Axes follow the design format: length = X, height = Y, depth = Z. "Width" is the depth when a length is also given
(furniture: length x width x height), otherwise the length. A size matches when it is within 1 % or 2 mm.
"""
import re

UNIT = {'mm': 1.0, 'cm': 10.0, 'm': 1000.0}
NOUNS = {'length': 'length', 'height': 'height', 'depth': 'depth', 'width': 'width'}        # come before the number
ADJECTIVES = {'long': 'length', 'high': 'height', 'tall': 'height', 'deep': 'depth', 'wide': 'width'}   # come after it
AXIS = {'length': 0, 'height': 1, 'depth': 2}
_N = r'(\d+(?:[.,]\d+)?)\s*(mm|cm|m)\b'


def parse_sizes(text):
    """{'length'|'height'|'depth': mm} found in free text."""
    if not isinstance(text, str):
        return {}
    t = text.lower()
    found = {}
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*[x×*]\s*(\d+(?:[.,]\d+)?)\s*[x×*]\s*' + _N, t)
    if m:
        k = UNIT[m.group(4)]
        found.update(length=float(m.group(1).replace(',', '.')) * k, depth=float(m.group(2).replace(',', '.')) * k,
                     height=float(m.group(3).replace(',', '.')) * k)
    for word, dim in NOUNS.items():
        for m in re.finditer(r'\b' + word + r'\b[^0-9\n]{0,12}?' + _N, t):            # "height: 750 mm"
            found.setdefault(dim, float(m.group(1).replace(',', '.')) * UNIT[m.group(2)])
    for word, dim in ADJECTIVES.items():
        for m in re.finditer(_N + r'\s*\b' + word + r'\b', t):                       # "600 mm deep"
            found.setdefault(dim, float(m.group(1).replace(',', '.')) * UNIT[m.group(2)])
    if 'width' in found:
        w = found.pop('width')
        found.setdefault('depth' if 'length' in found else 'length', w)
    return found


def check_requirements(text, extents):
    """extents: [x, y, z] mm of the built design -> issues for every stated size the design does not meet."""
    out = []
    for dim, want in parse_sizes(text).items():
        have = extents[AXIS[dim]]
        if abs(have - want) > max(2.0, want * 0.01):
            out.append({'code': 'REQUIREMENT_MISMATCH', 'severity': 'error', 'components': [],
                        'message': f"The requirements ask for a {dim} of {want:g} mm, but the design is {have:.0f} mm "
                                   f"({'XYZ'[AXIS[dim]]} axis). Resize the boards to the stated size.",
                        'dimension': dim, 'required': want, 'actual': round(have, 1),
                        'calc': [f"{dim} ({'XYZ'[AXIS[dim]]}) of the boards = max - min = {have:.2f} mm",
                                 f"required = {want:g} mm", f"difference = {have - want:+.2f} mm",
                                 f"allowed = max(2 mm, 1 % of {want:g}) = {max(2.0, want * 0.01):.2f} mm"]})
    return out
