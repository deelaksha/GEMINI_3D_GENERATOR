"""
AI Design Canvas compiler: `board-design/v1` -> the engine's native design.

External AIs write a small declarative JSON document (never code; nothing is executed):

  {
    "format": "board-design/v1",
    "product":  {"name", "description", "overall": {"length", "height", "depth"}},
    "material": {"name", "type", "thickness", "kerf"?, "clearance"?},
    "joinery":  "interlocking" | "glue_allowed",                     (optional; derived from connections)
    "boards": [{"id", "name", "group", "position": [x, y, z], "size": [sx, sy, sz],
                "thickness"?, "material"?, "grain"?: "x"|"y"|"z", "openings"?: [...], "edge_banding"?: [...],
                "profile"?: shape, "engravings"?: [...], "rotate"?: {"axis", "angle", "pivot"?}}],
    "connections": [{"id"?, "type": "tab_slot"|"butt"|"hinge"|"mitre", "board", "into", ...}]
  }

A board is the axis-aligned world box position..position+size (mm, +Y up, X = length, Z = depth/front);
its thinnest extent is the board thickness. Complex cuts: a `profile` (any shape from shapes.py, in face
coordinates [u, v] from the box's minimum corner) replaces the rectangular outline, openings may use any shape,
and `engravings` add engrave / pocket marks. A board can be tilted with `rotate` (applied last: profile, openings,
engravings and edge directions all refer to the unrotated box). The compiler reuses the existing generator for everything:
furniture.panel() places boards, furniture.edge_facing() finds edges, joining.join() runs every connection
through the validation / safe-repair pipeline (slots are generated there), validate_design() and the
production package do the rest. Diagnostics carry the source line and, where possible, code-level fixes.
"""
import copy
import json
import math
import re

from . import geometry as G
from .examples.furniture import DIRS, edge_facing, panel
from .joining import join
from .manufacturing import FASTENERS, MATERIALS
from .model import (DEFAULT_MATERIAL, FASTENER_KINDS, ID_RE, JOINERY_MODES, LIMITS, MARK_KINDS, MATERIAL_TYPES,
                    SchemaError, edge_frame, normalize_design)
from .nesting import SHEET_PRESETS
from .shapes import ShapeError, arc_sweep, shape_polygon
from .validation import TOL, _edge_line_intervals, validate_design

FORMAT = 'board-design/v1'
CONNECTION_TYPES = ('tab_slot', 'butt', 'hinge', 'mitre')
AXES = 'xyz'
MAX_SOURCE = 1_000_000
SAFE_MOVE = 2.0     # mm: a placement correction this small is treated as unambiguous (auto-fixable)


class CompileError(Exception):
    pass


def diag(severity, code, message, *, path=None, board=None, connection=None, line=None, fixes=None, **extra):
    d = {'severity': severity, 'code': code, 'message': message}
    for k, v in (('path', path), ('board', board), ('connection', connection), ('line', line), ('fixes', fixes)):
        if v is not None:
            d[k] = v
    d.update({k: v for k, v in extra.items() if v is not None})
    return d


# ---------------------------------------------------------------------------
# 1. Parsing (tolerant of how AIs reply: code fences, prose, // comments, trailing commas)
# ---------------------------------------------------------------------------

def _extract(text):
    """Return (json_text, line_offset). Prefers the first ```json fenced block."""
    m = re.search(r'```(?:json|JSON|jsonc|json5)?[ \t]*\n(.*?)```', text, re.S)
    if m:
        return m.group(1), text[:m.start(1)].count('\n')
    first, last = text.find('{'), text.rfind('}')
    if first > 0 and last > first and text[:first].strip():
        return text[first:last + 1], text[:first].count('\n')
    return text, 0


def _strip_comments(src):
    """Blank out // and /* */ comments and trailing commas, preserving every line/column position."""
    out, i, n, in_str = list(src), 0, len(src), False
    while i < n:
        c = src[i]
        if in_str:
            if c == '\\':
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == '/' and i + 1 < n and src[i + 1] == '/':
            while i < n and src[i] != '\n':
                out[i] = ' '
                i += 1
            continue
        elif c == '/' and i + 1 < n and src[i + 1] == '*':
            while i < n and not (src[i] == '*' and i + 1 < n and src[i + 1] == '/'):
                if src[i] != '\n':
                    out[i] = ' '
                i += 1
            if i < n:
                out[i] = out[i + 1] = ' '
                i += 2
            continue
        i += 1
    return _strip_trailing_commas(''.join(out))


def _strip_trailing_commas(src):
    """Second pass (after comments are blanked): drop a comma that is followed only by whitespace and } or ]."""
    out, in_str, i, n = list(src), False, 0, len(src)
    while i < n:
        c = src[i]
        if in_str:
            if c == '\\':
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == ',':
            j = i + 1
            while j < n and src[j] in ' \t\r\n':
                j += 1
            if j < n and src[j] in '}]':
                out[i] = ' '
        i += 1
    return ''.join(out)


def parse_source(text):
    """-> (data, json_text, line_offset, diagnostics)."""
    if not isinstance(text, str) or not text.strip():
        return None, '', 0, [diag('error', 'EMPTY_SOURCE', 'Paste the design JSON returned by the AI.')]
    if len(text) > MAX_SOURCE:
        return None, '', 0, [diag('error', 'SOURCE_TOO_LARGE', f'Source is larger than {MAX_SOURCE} characters.')]
    text = text.lstrip('\ufeff')
    body, off = _extract(text)
    try:
        data = json.loads(_strip_comments(body))
    except json.JSONDecodeError as e:
        hint = ''
        if re.search(r'\b(function|const|let|var|=>|import|export)\b', text[:4000]):
            hint = (' This looks like JavaScript. The canvas only accepts the declarative JSON format '
                    '(nothing is executed) — ask the AI to return JSON only.')
        return None, body, off, [diag('error', 'JSON_SYNTAX', f'{e.msg} (line {e.lineno + off}, column {e.colno}).{hint}',
                                      line=e.lineno + off, column=e.colno)]
    if not isinstance(data, dict):
        return None, body, off, [diag('error', 'NOT_AN_OBJECT', 'The design must be a JSON object { ... }.', line=1 + off)]
    return data, body, off, []


def _id_line(src, ident, off):
    m = re.search(r'"id"\s*:\s*"' + re.escape(str(ident)) + r'"', src)
    return src[:m.start()].count('\n') + 1 + off if m else None


def _key_line(src, key, off):
    m = re.search(r'"' + re.escape(key) + r'"\s*:', src)
    return src[:m.start()].count('\n') + 1 + off if m else None


# ---------------------------------------------------------------------------
# 2. Schema checks for board-design/v1
# ---------------------------------------------------------------------------

def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _vec3(v):
    return isinstance(v, list) and len(v) == 3 and all(_num(x) for x in v)


class _Board:
    def __init__(self, raw, t_default):
        self.raw = raw
        self.id = raw['id']
        self.pos = [float(x) for x in raw['position']]
        self.size = [float(x) for x in raw['size']]
        self.t = float(raw.get('thickness', t_default))
        self.lo = self.pos
        self.hi = [self.pos[i] + self.size[i] for i in range(3)]
        thin = [i for i in range(3) if abs(self.size[i] - self.t) <= 0.01]
        normal = raw.get('normal')
        if normal in ('x', 'y', 'z'):
            thin = [AXES.index(normal)] if AXES.index(normal) in thin else []
        self.thin_candidates = thin
        self.thin = thin[0] if len(thin) == 1 else None
        self.inplane = [i for i in range(3) if i != self.thin] if self.thin is not None else []
        self.rot = raw.get('rotate')   # validated in _check_boards


def _check_material(m, diags, src, off):
    if not isinstance(m, dict):
        diags.append(diag('error', 'MATERIAL_MISSING', 'Add a "material" object with at least "thickness" (mm).',
                          path='material', line=_key_line(src, 'material', off)))
        return None
    if not _num(m.get('thickness')) or not (LIMITS['min_thickness'] <= m['thickness'] <= LIMITS['max_thickness']):
        diags.append(diag('error', 'MATERIAL_THICKNESS', f"material.thickness must be a number between "
                          f"{LIMITS['min_thickness']} and {LIMITS['max_thickness']} mm.", path='material.thickness',
                          line=_key_line(src, 'thickness', off)))
        return None
    if m.get('type') is not None and m['type'] not in MATERIAL_TYPES:
        diags.append(diag('error', 'MATERIAL_TYPE', f"material.type must be one of {list(MATERIAL_TYPES)}.",
                          path='material.type', line=_key_line(src, 'type', off)))
        return None
    mtype = m.get('type', 'other')
    cat = MATERIALS.get(mtype, {})
    out = {'name': str(m.get('name') or f"{mtype.replace('_', ' ').title()} {m['thickness']:g} mm"),
           'type': mtype, 'thickness': float(m['thickness']),
           'kerf': float(m['kerf']) if _num(m.get('kerf')) else float(cat.get('kerf', DEFAULT_MATERIAL['kerf'])),
           'clearance': float(m['clearance']) if _num(m.get('clearance')) else float(DEFAULT_MATERIAL['clearance'])}
    if cat and out['thickness'] not in cat['thicknesses']:
        diags.append(diag('warning', 'NON_STANDARD_THICKNESS',
                          f"{out['thickness']:g} mm is not a standard {mtype} thickness "
                          f"({', '.join(f'{t:g}' for t in cat['thicknesses'])}).", path='material.thickness'))
    return out


def _check_boards(data, mat, diags, src, off):
    raw = data.get('boards')
    if not isinstance(raw, list) or not raw:
        diags.append(diag('error', 'NO_BOARDS', 'Add a non-empty "boards" array.', path='boards',
                          line=_key_line(src, 'boards', off)))
        return {}
    if len(raw) > LIMITS['max_components']:
        diags.append(diag('error', 'TOO_MANY_BOARDS', f"At most {LIMITS['max_components']} boards are supported."))
        return {}
    boards, ok = {}, True
    for i, b in enumerate(raw):
        p = f'boards[{i}]'
        if not isinstance(b, dict):
            diags.append(diag('error', 'BOARD_NOT_OBJECT', f'{p} must be an object.', path=p))
            ok = False
            continue
        bid = b.get('id')
        line = _id_line(src, bid, off) if isinstance(bid, str) else None
        if not isinstance(bid, str) or not ID_RE.match(bid):
            diags.append(diag('error', 'BOARD_ID', f'{p}.id must be a unique id matching {ID_RE.pattern} '
                              f'(letters, digits, "-", "_", ".").', path=p + '.id', line=line))
            ok = False
            continue
        if bid in boards:
            diags.append(diag('error', 'DUPLICATE_BOARD_ID', f"Board id '{bid}' is used twice; ids must be unique.",
                              path=p + '.id', board=bid, line=line))
            ok = False
            continue
        bad = [k for k in ('position', 'size') if not _vec3(b.get(k))]
        if bad:
            diags.append(diag('error', 'BOARD_GEOMETRY', f"Board '{bid}': {' and '.join(bad)} must be [x, y, z] numbers in mm.",
                              path=p, board=bid, line=line))
            ok = False
            continue
        if any(s <= 0 for s in b['size']) or any(abs(v) > LIMITS['max_coord'] for v in b['size'] + b['position']):
            diags.append(diag('error', 'BOARD_SIZE', f"Board '{bid}': sizes must be > 0 and coordinates within "
                              f"±{LIMITS['max_coord']:g} mm.", path=p + '.size', board=bid, line=line))
            ok = False
            continue
        if b.get('thickness') is not None and not (_num(b['thickness']) and LIMITS['min_thickness'] <= b['thickness'] <= LIMITS['max_thickness']):
            diags.append(diag('error', 'BOARD_THICKNESS', f"Board '{bid}': thickness out of range.", path=p + '.thickness',
                              board=bid, line=line))
            ok = False
            continue
        rot = b.get('rotate')
        if rot is not None and not (isinstance(rot, dict) and rot.get('axis') in ('x', 'y', 'z') and _num(rot.get('angle'))
                                    and -360 <= rot['angle'] <= 360 and (rot.get('pivot') is None or _vec3(rot['pivot']))):
            diags.append(diag('error', 'BOARD_ROTATE', f"Board '{bid}': \"rotate\" must be {{\"axis\": \"x\"|\"y\"|\"z\", "
                              f"\"angle\": degrees, \"pivot\"?: [x, y, z]}} (pivot defaults to the board centre).",
                              path=p + '.rotate', board=bid, line=line))
            ok = False
            continue
        bd = _Board(b, mat['thickness'])
        if bd.thin is None:
            if not bd.thin_candidates:
                diags.append(diag('error', 'THICKNESS_MISMATCH',
                                  f"Board '{bid}': none of size {b['size']} equals its thickness {bd.t:g} mm. Boards are "
                                  f"flat panels: exactly one of size[x, y, z] must be the board thickness.",
                                  path=p + '.size', board=bid, line=line))
            else:
                diags.append(diag('error', 'AMBIGUOUS_ORIENTATION',
                                  f"Board '{bid}': several sizes equal the thickness; add \"normal\": \"x\"|\"y\"|\"z\" to say "
                                  f"which axis is the board's thickness direction.", path=p, board=bid, line=line))
            ok = False
            continue
        bd.line = line
        bd.index = i
        boards[bid] = bd
    return boards if ok else {k: v for k, v in boards.items()}


# ---------------------------------------------------------------------------
# 3. Boards -> engine components (furniture.panel)
# ---------------------------------------------------------------------------

def _frame(comp):
    return G.Frame(comp['placement']['position'], comp['placement']['rotation'])


def _local_axis_of(comp, world_axis):
    """Which local axis (0 = x, 1 = y) of a panel runs along `world_axis`."""
    f = _frame(comp)
    vx = f.dir_to_world([1, 0, 0])
    return 0 if abs(vx[world_axis]) > 0.5 else 1


def _face_mapper(bd, comp):
    """Board face coordinates [u, v] (mm from the box's minimum corner along its two in-plane axes, in x, y, z
    order) -> the component's local 2D frame. Used for profiles, shaped openings and engravings."""
    f = _frame(comp)
    iu, iv = bd.inplane
    mid = (bd.lo[bd.thin] + bd.hi[bd.thin]) / 2

    def to_local(uv):
        w = [0.0, 0.0, 0.0]
        w[iu], w[iv], w[bd.thin] = bd.lo[iu] + uv[0], bd.lo[iv] + uv[1], mid
        q = f.to_local(w)
        return [round(q[0], 4), round(q[1], 4)]
    return to_local


def _local_shape(spec, to_local, origin, name):
    """Shape spec in face coordinates (offset by origin) -> (local points, arcs, face points). Raises ShapeError."""
    pts, arcs = shape_polygon(spec, name)
    if len(pts) > LIMITS['max_outline_points']:
        raise ShapeError(f"{name} has {len(pts)} points after flattening curves (max {LIMITS['max_outline_points']})")
    face = [[origin[0] + x, origin[1] + y] for x, y in pts]
    loc = [to_local(q) for q in face]
    out_arcs = []
    for a in arcs:
        c = to_local([origin[0] + a['center'][0], origin[1] + a['center'][1]])
        n = len(loc)
        mid = loc[(a['start'] + ((a['end'] - a['start']) % n) // 2) % n]
        out_arcs.append(dict(a, center=c, ccw=arc_sweep(loc[a['start']], mid, loc[a['end']], c) > 0))  # handedness of the mapping
    return loc, out_arcs, face


def _euler_xyz(R):
    """Inverse of G.rotation_matrix (THREE 'XYZ' order), degrees."""
    ry = math.asin(max(-1.0, min(1.0, R[0][2])))
    if abs(R[0][2]) < 0.9999999:
        rx, rz = math.atan2(-R[1][2], R[2][2]), math.atan2(-R[0][1], R[0][0])
    else:
        rx, rz = math.atan2(R[2][1], R[1][1]), 0.0
    return [round(math.degrees(v), 6) for v in (rx, ry, rz)]


def _rotate_matrix(rot):
    return G.rotation_matrix([rot['angle'] if AXES[i] == rot['axis'] else 0.0 for i in range(3)])


def _apply_rotate(comp, rot):
    """Tilt a finished component by `rot` about its pivot (default: the board centre)."""
    Rr = _rotate_matrix(rot)
    c = comp['placement']['position']
    pivot = rot.get('pivot') or c
    rel = [c[i] - pivot[i] for i in range(3)]
    comp['placement'] = {'position': [round(pivot[i] + sum(Rr[i][k] * rel[k] for k in range(3)), 4) for i in range(3)],
                         'rotation': _euler_xyz(G.mat_mul(Rr, G.rotation_matrix(comp['placement']['rotation'])))}


def _component(bd, mat, diags):
    lo, hi = bd.lo, bd.hi
    kw = {}
    r = bd.raw
    if isinstance(r.get('material'), dict):
        kw['material'] = {k: r['material'][k] for k in ('name', 'type') if r['material'].get(k)}
    comp = panel(bd.id, str(r.get('name') or bd.id), str(r.get('group') or 'Boards'), lo, hi, **kw)
    comp['thickness'] = bd.t
    to_local = _face_mapper(bd, comp)
    su, sv = bd.size[bd.inplane[0]], bd.size[bd.inplane[1]]
    if r.get('profile') is not None:
        p = f"boards[{bd.index}].profile"
        try:
            pts, arcs, face = _local_shape(r['profile'], to_local, (0.0, 0.0), 'profile')
            out = [q for q in face if not (-0.01 <= q[0] <= su + 0.01 and -0.01 <= q[1] <= sv + 0.01)]
            if out:
                raise ShapeError(f"the profile leaves the board's box (e.g. point [{out[0][0]:g}, {out[0][1]:g}]); profile "
                                 f"coordinates are [u, v] from the box corner, within [0..{su:g}] × [0..{sv:g}] mm")
            comp['outline'] = pts
            if arcs:
                comp['arcs'] = arcs
        except ShapeError as e:
            diags.append(diag('error', 'PROFILE_INVALID', f"Board '{bd.id}': {e}.", path=p, board=bd.id, line=bd.line))
    if r.get('grain') in ('x', 'y', 'z'):
        g = AXES.index(r['grain'])
        if g == bd.thin:
            diags.append(diag('warning', 'GRAIN_ALONG_THICKNESS', f"Board '{bd.id}': grain cannot run along its thickness; ignored.",
                              board=bd.id, line=bd.line))
        else:
            comp['grain'] = 'x' if _local_axis_of(comp, g) == 0 else 'y'
    feats = []
    for k, o in enumerate(r.get('openings') or []):
        p = f"boards[{bd.index}].openings[{k}]"
        if not isinstance(o, dict) or not _vec3(o.get('center')):
            diags.append(diag('error', 'OPENING_INVALID', f"Board '{bd.id}': {p} needs \"center\": [x, y, z] (world mm).",
                              path=p, board=bd.id, line=bd.line))
            continue
        f = _frame(comp)
        c = f.to_local(o['center'])
        if abs(c[2]) > bd.t / 2 + 0.01:
            diags.append(diag('error', 'OPENING_OFF_BOARD', f"Board '{bd.id}': opening centre {o['center']} is not inside the board.",
                              path=p + '.center', board=bd.id, line=bd.line))
            continue
        feat = {'id': str(o.get('id') or f'opening-{k + 1}'), 'kind': o.get('kind', 'opening'),
                'shape': o.get('shape', 'circle' if o.get('diameter') else 'rect'), 'center': [round(c[0], 4), round(c[1], 4)]}
        if feat['shape'] not in ('rect', 'circle'):
            # any other shape: built in face coordinates around the centre, cut as a polygon (curves kept as arcs)
            spec = dict(o, center=[0.0, 0.0])
            sz = o.get('size')
            if isinstance(sz, list) and len(sz) == 2 and all(_num(v) for v in sz):
                spec['width'], spec['height'] = sz
            origin = [o['center'][bd.inplane[0]] - bd.lo[bd.inplane[0]], o['center'][bd.inplane[1]] - bd.lo[bd.inplane[1]]]
            try:
                pts, arcs, _face = _local_shape(spec, to_local, origin, p)
            except ShapeError as e:
                diags.append(diag('error', 'OPENING_INVALID', f"Board '{bd.id}': {e}.", path=p, board=bd.id, line=bd.line))
                continue
            feat.update(shape='polygon', points=pts, **({'arcs': arcs} if arcs else {}))
        elif feat['shape'] == 'circle':
            feat['diameter'] = o.get('diameter')
        else:
            sz = o.get('size')
            if not (isinstance(sz, list) and len(sz) == 2 and all(_num(v) for v in sz)):
                diags.append(diag('error', 'OPENING_INVALID', f"Board '{bd.id}': rectangular {p} needs \"size\": [a, b] along the "
                                  f"board's two in-plane world axes ({', '.join(AXES[i] for i in bd.inplane)}).",
                                  path=p + '.size', board=bd.id, line=bd.line))
                continue
            dims = dict(zip(bd.inplane, sz))
            lx_axis = next(i for i in bd.inplane if _local_axis_of(comp, i) == 0)
            ly_axis = next(i for i in bd.inplane if i != lx_axis)
            feat['width'], feat['height'], feat['angle'] = dims[lx_axis], dims[ly_axis], 0
            if _num(o.get('corner_radius')) and o['corner_radius'] > 0:
                feat['corner_radius'] = min(o['corner_radius'], min(sz) / 2)
        if o.get('note'):
            feat['note'] = str(o['note'])[:200]
        feats.append(feat)
    if feats:
        comp['features'] = feats
    banding = []
    for e in r.get('edge_banding') or []:
        if isinstance(e, dict) and e.get('edge') in DIRS:
            banding.append({'edge': edge_facing(comp, e['edge']), 'thickness': e.get('thickness', 1.0),
                            **({'material': e['material']} if e.get('material') else {})})
    if banding:
        comp['edge_banding'] = banding
    marks = []
    for k, m in enumerate(r.get('engravings') or []):
        p = f"boards[{bd.index}].engravings[{k}]"
        kind = m.get('kind', 'engrave') if isinstance(m, dict) else None
        if kind not in MARK_KINDS:
            diags.append(diag('error', 'ENGRAVING_INVALID', f"Board '{bd.id}': {p} must be an object with \"kind\": "
                              f"{' or '.join(repr(x) for x in MARK_KINDS)}.", path=p, board=bd.id, line=bd.line))
            continue
        try:
            if m.get('shape'):
                pts, arcs, _f = _local_shape(m, to_local, (0.0, 0.0), p)
                closed = True
            else:
                raw = m.get('points')
                if not (isinstance(raw, list) and len(raw) >= 2 and all(isinstance(q, list) and len(q) == 2 and all(_num(v) for v in q) for q in raw)):
                    raise ShapeError(f'{p} needs "points": [[u, v], ...] (face mm) or a "shape"')
                pts, arcs, closed = [to_local(q) for q in raw], [], bool(m.get('closed', False)) or kind == 'pocket'
        except ShapeError as e:
            diags.append(diag('error', 'ENGRAVING_INVALID', f"Board '{bd.id}': {e}.", path=p, board=bd.id, line=bd.line))
            continue
        mk = {'id': str(m.get('id') or f'{kind}-{k + 1}'), 'kind': kind, 'points': pts, 'closed': closed,
              **({'arcs': arcs} if arcs else {})}
        if m.get('depth') is not None:
            mk['depth'] = m['depth']
        elif kind == 'pocket':
            mk['depth'] = round(bd.t / 2, 3)
        if m.get('note'):
            mk['note'] = str(m['note'])[:200]
        marks.append(mk)
    if marks:
        comp['marks'] = marks
    return comp


# ---------------------------------------------------------------------------
# 4. Connections -> engine joints
# ---------------------------------------------------------------------------

def _overlap(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0)


def _contact(A, B, want=None):
    """Find A's end face that meets B's broad face. -> dict(axis, sign, gap, m, n) or None.

    Measured in world coordinates on the axis-aligned boxes: gap > 0 is open space, gap < 0 is penetration."""
    best = None
    for k in A.inplane:
        if k != B.thin:
            continue
        for e in (1, -1):
            if want and want != (k, e):
                continue
            a_face = A.hi[k] if e > 0 else A.lo[k]
            b_face = B.lo[k] if e > 0 else B.hi[k]
            gap = (b_face - a_face) * e
            m = next(i for i in A.inplane if i != k)
            n = A.thin
            if _overlap(A.lo[m], A.hi[m], B.lo[m], B.hi[m]) <= 0 or _overlap(A.lo[n], A.hi[n], B.lo[n], B.hi[n]) <= 0:
                continue
            if best is None or abs(gap) < abs(best['gap']):
                best = {'axis': k, 'sign': e, 'gap': gap, 'm': m, 'n': n}
    return best


def _dir(axis, sign):
    return ('+' if sign > 0 else '-') + AXES[axis]


def _move_fix(bd, axis, amount, title, safe):
    pos = list(bd.raw['position'])
    pos[axis] = round(pos[axis] + amount, 4)
    return {'id': f"move-{bd.id}-{AXES[axis]}", 'title': title, 'safe': safe,
            'edits': [{'board': bd.id, 'field': 'position', 'value': pos}]}


def _resize_fix(bd, axis, sign, amount, title):
    """Grow (amount > 0) or shrink the board at its `sign` end along `axis`."""
    size, pos = list(bd.raw['size']), list(bd.raw['position'])
    size[axis] = round(size[axis] + amount, 4)
    if sign < 0:
        pos[axis] = round(pos[axis] - amount, 4)
    return {'id': f"resize-{bd.id}-{AXES[axis]}", 'title': title, 'safe': False,
            'edits': [{'board': bd.id, 'field': 'size', 'value': size}, {'board': bd.id, 'field': 'position', 'value': pos}]}


def _tabs_for(comp, bd_a, bd_b, ct, conn, cid):
    """Tabs evenly spaced along A's contact edge, inset by A's thickness from the contact ends (world -> A-local).
    The contact edge is the straight outline edge lying on A's end face (for a plain board: its whole side; for a
    profiled board: the longest straight run of the profile on that face)."""
    k, e, m = ct['axis'], ct['sign'], ct['m']
    f = _frame(comp)
    face = bd_a.hi[k] if e > 0 else bd_a.lo[k]
    out = comp['outline']
    best = None
    for i in range(len(out)):
        w0, w1 = f.to_world([*out[i], 0.0]), f.to_world([*out[(i + 1) % len(out)], 0.0])
        if abs(w0[k] - face) > 0.01 or abs(w1[k] - face) > 0.01:
            continue
        lo_m = max(min(w0[m], w1[m]), bd_b.lo[m]) + bd_a.t
        hi_m = min(max(w0[m], w1[m]), bd_b.hi[m]) - bd_a.t
        if best is None or hi_m - lo_m > best[2] - best[1]:
            best = (i, lo_m, hi_m)
    if best is None:
        return None, (f"'{bd_a.id}' has no straight edge on its {_dir(k, e)} side (its profile does not reach that face of "
                      f"the box), so it cannot sit against '{bd_b.id}' there")
    edge, lo_m, hi_m = best
    region = hi_m - lo_m
    min_w = max(TOL['min_tab_width'], bd_a.t)
    if region < min_w:
        return None, f"the contact between '{bd_a.id}' and '{bd_b.id}' is only {max(region + 2 * bd_a.t, 0):.1f} mm long — too short for a tab"
    w, n, pitch, depth = _tab_layout(region, conn, bd_a.t, bd_b.t)
    a0, d, _nrm, _L = edge_frame(out, edge)
    tabs = []
    for i in range(n):
        wm = lo_m + (i + 0.5) * pitch
        pt = [0.0, 0.0, 0.0]
        pt[k], pt[m], pt[bd_a.thin] = face, wm, (bd_a.lo[bd_a.thin] + bd_a.hi[bd_a.thin]) / 2
        loc = f.to_local(pt)
        off = (loc[0] - a0[0]) * d[0] + (loc[1] - a0[1]) * d[1]
        tabs.append({'id': f'{cid}-t{i + 1}', 'edge': edge, 'offset': round(off, 4), 'width': round(w, 3),
                     'depth': round(float(depth), 3)})
    return tabs, None


def _tab_layout(region, conn, t_a, t_b):
    """-> (tab width, count, pitch, depth) for a contact region `region` mm long."""
    min_w = max(TOL['min_tab_width'], t_a)
    n = conn.get('tabs')
    if not (isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= 12):
        n = max(1, min(6, int(region // 250) + 1))
    pitch = region / n
    w = conn.get('tab_width')
    if not _num(w) or w <= 0:
        w = max(min_w, min(pitch * 0.5, pitch - t_a))
    w = min(w, pitch)
    depth = conn.get('tab_depth') if _num(conn.get('tab_depth')) else t_b
    return w, n, pitch, depth


def _add_fasteners(j, c, cid, cline, diags):
    f = c.get('fasteners')
    if isinstance(f, str):
        f = {'kind': f}
    if f is not None:
        if not isinstance(f, dict) or f.get('kind') not in FASTENER_KINDS:
            diags.append(diag('error', 'FASTENER_KIND', f"Connection '{cid}': fasteners.kind must be one of "
                              f"{list(FASTENER_KINDS)}.", connection=cid, line=cline))
            return False
        j['fasteners'] = f
    return True


PARALLEL_COS = math.cos(math.radians(0.5))


def _contact_tilted(ca, cb, t_a, t_b, only_edge=None):
    """General contact for tilted boards: a straight edge of A whose end face is parallel to a broad face of B and
    overlaps it. -> dict(edge, gap, normal, t0, t1, length) with the overlap t0..t1 in mm along the edge, or None.
    gap > 0 is open space between A's end face and B's face, gap < 0 is penetration."""
    fa, fb = _frame(ca), _frame(cb)
    nb = fb.normal
    out, n = ca['outline'], len(ca['outline'])
    na = fa.normal
    best = None
    for i in (range(n) if only_edge is None else [only_edge]):
        a0, b0 = out[i], out[(i + 1) % n]
        L = math.dist(a0, b0)
        if L < 1.0:
            continue
        ne = fa.dir_to_world([(b0[1] - a0[1]) / L, -(b0[0] - a0[0]) / L, 0.0])
        dp = sum(ne[q] * nb[q] for q in range(3))
        if abs(dp) < PARALLEL_COS:
            continue
        s = 1.0 if dp > 0 else -1.0
        nal = [nb[q] * s for q in range(3)]
        p0, p1 = fa.to_world([a0[0], a0[1], 0.0]), fa.to_world([b0[0], b0[1], 0.0])
        near = [fb.p[q] - nal[q] * t_b / 2 for q in range(3)]           # B's face on A's side
        gap = sum((near[q] - p0[q]) * nal[q] for q in range(3))
        if gap < -t_b:                    # A's end is already past B's far face: not touching this face
            continue
        # overlap: the edge line and both faces of A (± t_a/2) must run over B's outline
        edges_b = list(zip(cb['outline'], cb['outline'][1:] + cb['outline'][:1]))
        lo_t, hi_t = 0.0, 1.0
        for off in (0.0, t_a / 2, -t_a / 2):
            q0 = fb.to_local([p0[q] + na[q] * off for q in range(3)])
            q1 = fb.to_local([p1[q] + na[q] * off for q in range(3)])
            iv = [(max(r0, 0.0), min(r1, 1.0)) for r0, r1 in _edge_line_intervals(edges_b, q0, [q1[0] - q0[0], q1[1] - q0[1]])]
            iv = [x for x in iv if x[1] > x[0]]
            if not iv:
                lo_t = hi_t = 0.0
                break
            r0, r1 = max(iv, key=lambda x: x[1] - x[0])
            lo_t, hi_t = max(lo_t, r0), min(hi_t, r1)
        if hi_t - lo_t <= 1e-9:
            continue
        cand = {'edge': i, 'gap': gap, 'normal': nal, 't0': lo_t * L, 't1': hi_t * L, 'length': L}
        if best is None or (abs(gap), -(hi_t - lo_t) * L) < (abs(best['gap']), -(best['t1'] - best['t0'])):
            best = cand
    return best


def _tilted_move_fix(bd, delta, title):
    """Fix that moves board `bd` by the world vector `delta` (its position is pre-rotation; with an explicit pivot
    the tilt would turn the move, so it is un-rotated first)."""
    if bd.rot and bd.rot.get('pivot') is not None:
        R = _rotate_matrix(bd.rot)
        delta = [sum(R[k][q] * delta[k] for k in range(3)) for q in range(3)]
    pos = [round(bd.raw['position'][q] + delta[q], 4) for q in range(3)]
    return {'id': f'move-{bd.id}', 'title': title, 'safe': False, 'edits': [{'board': bd.id, 'field': 'position', 'value': pos}]}


def _connect_tilted(comps, comps0, A, B, c, cid, cline, ctype, want, joints, diags):
    """tab_slot / butt where either board is tilted with "rotate" (general orientation)."""
    a, b = A.id, B.id
    only = edge_facing(comps0[a], _dir(*want)) if want else None
    ct = _contact_tilted(comps[a], comps[b], A.t, B.t, only)
    if ct is None:
        diags.append(diag('error', 'NO_CONTACT', f"Connection '{cid}': no straight edge of '{a}' sits flat against a face of "
                          f"'{b}'. With \"rotate\", an edge of '{a}' must be parallel to a broad face of '{b}' and run over it "
                          f"(e.g. a gable's sloped top edge under a roof panel tilted to the same pitch).",
                          connection=cid, board=a, line=cline))
        return
    gap = ct['gap']
    if abs(gap) > TOL['contact']:
        delta = [ct['normal'][q] * gap for q in range(3)]          # moving A by this closes the gap
        move_a = _tilted_move_fix(A, delta, f"Move '{a}' {abs(gap):.2f} mm to touch '{b}'")
        move_b = _tilted_move_fix(B, [-v for v in delta], f"Move '{b}' {abs(gap):.2f} mm to touch '{a}'")
        # prefer moving the tilted board: the other one is usually locked square into the rest of the product
        fixes = [move_b, move_a] if (B.rot and not A.rot) else [move_a, move_b]
        fixes[0]['safe'] = abs(gap) <= SAFE_MOVE
        what = (f"stops {gap:.2f} mm short of" if gap > 0 else f"runs {-gap:.2f} mm into")
        diags.append(diag('error', 'CONNECTION_GAP' if gap > 0 else 'CONNECTION_OVERLAP',
                          f"Connection '{cid}': '{a}' {what} '{b}' (measured square to '{b}''s face).",
                          connection=cid, board=a, line=cline or A.line, gap=round(gap, 3), fixes=fixes))
        return
    if ctype == 'butt':
        j = {'id': cid, 'type': 'edge_butt', 'a': a, 'a_edge': ct['edge'], 'b': b}
        if _add_fasteners(j, c, cid, cline, diags):
            joints.append((j, c, cid, cline))
        return
    lo, hi = ct['t0'] + A.t, ct['t1'] - A.t
    if hi - lo < max(TOL['min_tab_width'], A.t):
        diags.append(diag('error', 'CONTACT_TOO_SHORT', f"Connection '{cid}': the contact between '{a}' and '{b}' is only "
                          f"{ct['t1'] - ct['t0']:.1f} mm long — too short for a tab.", connection=cid, line=cline))
        return
    w, n, pitch, depth = _tab_layout(hi - lo, c, A.t, B.t)
    tabs = [{'id': f'{cid}-t{i + 1}', 'edge': ct['edge'], 'offset': round(lo + (i + 0.5) * pitch, 4), 'width': round(w, 3),
             'depth': round(float(depth), 3)} for i in range(n)]
    comps[a].setdefault('tabs', []).extend(tabs)
    for t in tabs:
        joints.append(({'id': t['id'], 'type': 'tab_slot', 'a': a, 'tab': t['id'], 'b': b}, c, cid, cline))


def _parse_dir(v):
    if isinstance(v, str) and v in DIRS:
        return AXES.index(v[1]), (1 if v[0] == '+' else -1)
    return None


# ---------------------------------------------------------------------------
# 5. Compile
# ---------------------------------------------------------------------------

def _auto_sheet(design, mat, data):
    sh = data.get('sheet') if isinstance(data.get('sheet'), dict) else {}
    if _num(sh.get('width')) and _num(sh.get('height')):
        return {'width': float(sh['width']), 'height': float(sh['height']), 'spacing': 6.0}
    need = 0.0, 0.0
    for c in design['components']:
        xs = [p[0] for p in c['outline']]
        ys = [p[1] for p in c['outline']]
        w, h = max(xs) - min(xs) + 2 * mat['thickness'] + 20, max(ys) - min(ys) + 2 * mat['thickness'] + 20
        need = max(need[0], max(w, h)), max(need[1], min(w, h))
    stock = [tuple(s) for s in MATERIALS.get(mat['type'], {}).get('stock', [])]
    stock += sorted({tuple(sorted(v, reverse=True)) for v in SHEET_PRESETS.values()}, key=lambda s: s[0] * s[1])
    for W, H in stock:
        if max(W, H) >= need[0] and min(W, H) >= need[1]:
            return {'width': float(max(W, H)), 'height': float(min(W, H)), 'spacing': 6.0}
    return {'width': 2440.0, 'height': 1220.0, 'spacing': 6.0}


def compile_source(text, design_id='canvas-preview', run_production=True):
    """Compile AI-generated design text. Never raises for bad input; everything is a diagnostic."""
    data, src, off, diags = parse_source(text)
    result = {'ok': False, 'format': None, 'diagnostics': diags, 'design': None, 'source_map': {}}
    if data is None:
        return result
    try:
        if 'components' in data and 'boards' not in data:
            return _compile_native(data, design_id, result, run_production)
        return _compile_v1(data, src, off, design_id, result, run_production)
    except SchemaError as e:
        result['diagnostics'].append(diag('error', 'SCHEMA_ERROR', str(e), path=e.path))
    except Exception as e:  # last line of defence: compiler bugs must never take the page down
        result['diagnostics'].append(diag('error', 'COMPILER_ERROR', f'Internal compiler error: {type(e).__name__}: {e}'))
    return result


def _compile_native(data, design_id, result, run_production):
    result['format'] = 'native'
    d = dict(data)
    d.setdefault('id', design_id)
    design = normalize_design(d)
    pending = [j for j in design['joints'] if j.get('status') != 'joined']
    design['joints'] = [j for j in design['joints'] if j.get('status') == 'joined']
    for spec in pending:
        res = join(design, spec, auto_repair=True, whole_design_check=False)
        if res['accepted']:
            design = res['design']
        else:
            design['joints'].append(dict(spec, status='detached', detached_reason=res['status']))
    return _finish(design, result, {}, run_production)


def _compile_v1(data, src, off, design_id, result, run_production):
    diags = result['diagnostics']
    result['format'] = FORMAT
    if data.get('format') not in (None, FORMAT):
        diags.append(diag('warning', 'FORMAT_VERSION', f"\"format\" should be \"{FORMAT}\"; compiling as {FORMAT}.",
                          line=_key_line(src, 'format', off)))
    product = data.get('product') if isinstance(data.get('product'), dict) else {}
    if not product.get('name'):
        diags.append(diag('warning', 'PRODUCT_NAME', 'Add "product": {"name": ...} so the design can be identified.',
                          line=_key_line(src, 'product', off)))
    mat = _check_material(data.get('material'), diags, src, off)
    if mat is None:
        return result
    boards = _check_boards(data, mat, diags, src, off)
    if any(d['severity'] == 'error' for d in diags):
        return result
    source_map = {bid: bd.line for bid, bd in boards.items()}

    comps = {bid: _component(bd, mat, diags) for bid, bd in boards.items()}
    comps0 = copy.deepcopy(comps)      # unrotated: edge directions ("+x", ...) always refer to the unrotated box
    for bid, bd in boards.items():
        if bd.rot:
            _apply_rotate(comps[bid], bd.rot)

    # Connections
    conns = data.get('connections') or []
    if not isinstance(conns, list):
        diags.append(diag('error', 'CONNECTIONS_INVALID', '"connections" must be an array.', line=_key_line(src, 'connections', off)))
        return result
    types = {c.get('type', 'tab_slot') for c in conns if isinstance(c, dict)} & set(CONNECTION_TYPES)
    joinery = data.get('joinery') or ('interlocking' if types <= {'tab_slot'} else 'glue_allowed')
    if joinery not in JOINERY_MODES:
        diags.append(diag('error', 'JOINERY', f'"joinery" must be one of {list(JOINERY_MODES)}.', line=_key_line(src, 'joinery', off)))
        return result
    if joinery == 'interlocking' and not types <= {'tab_slot'}:
        diags.append(diag('error', 'GLUE_JOINT_IN_INTERLOCKING', f"Connections of type {sorted(types - {'tab_slot'})} need glue or "
                          f"hardware, but \"joinery\" is \"interlocking\" (glue-free). Use tab_slot or set \"joinery\": \"glue_allowed\".",
                          line=_key_line(src, 'joinery', off),
                          fixes=[{'id': 'joinery-glue', 'title': 'Set "joinery": "glue_allowed"', 'safe': False,
                                  'edits': [{'field': 'joinery', 'value': 'glue_allowed'}]}]))
        return result
    joints, seen = [], set()
    for i, c in enumerate(conns):
        p = f'connections[{i}]'
        if not isinstance(c, dict):
            diags.append(diag('error', 'CONNECTION_INVALID', f'{p} must be an object.', path=p))
            continue
        ctype = c.get('type', 'tab_slot')
        a, b = c.get('board'), c.get('into')
        cid = c.get('id') if isinstance(c.get('id'), str) and ID_RE.match(c['id']) else f"C{i + 1}-{a}-{b}"
        cline = _id_line(src, c['id'], off) if c.get('id') else None
        source_map[cid] = cline
        if cid in seen:
            diags.append(diag('error', 'DUPLICATE_CONNECTION_ID', f"Connection id '{cid}' is used twice.", connection=cid, line=cline))
            continue
        seen.add(cid)
        if ctype not in CONNECTION_TYPES:
            diags.append(diag('error', 'CONNECTION_TYPE', f"{p}: type must be one of {list(CONNECTION_TYPES)}.", path=p + '.type',
                              connection=cid, line=cline))
            continue
        missing = [x for x in (a, b) if x not in boards]
        if missing:
            diags.append(diag('error', 'UNKNOWN_BOARD', f"Connection '{cid}' refers to unknown board(s) {missing}.", path=p,
                              connection=cid, line=cline))
            continue
        if a == b:
            diags.append(diag('error', 'SELF_CONNECTION', f"Connection '{cid}' connects '{a}' to itself.", connection=cid, line=cline))
            continue
        A, B = boards[a], boards[b]
        if ctype == 'hinge':
            dirv = _parse_dir(c.get('edge'))
            if not dirv:
                diags.append(diag('error', 'HINGE_EDGE', f"Hinge '{cid}': add \"edge\": \"+x\"|\"-x\"|... — the side of door '{a}' "
                                  f"that carries the hinges.", connection=cid, line=cline))
                continue
            j = {'id': cid, 'type': 'hinge', 'a': a, 'a_edge': edge_facing(comps0[a], c['edge']), 'b': b}
            for k in ('count', 'gap'):
                if c.get(k) is not None:
                    j[k] = c[k]
            joints.append((j, c, cid, cline))
            continue
        if ctype == 'mitre':
            da, db = _parse_dir(c.get('edge')), _parse_dir(c.get('into_edge'))
            if not (da and db):
                diags.append(diag('error', 'MITRE_EDGES', f"Mitre '{cid}': give \"edge\" (on '{a}') and \"into_edge\" (on '{b}') as "
                                  f"\"+x\"|\"-x\"|\"+y\"|... directions.", connection=cid, line=cline))
                continue
            j = {'id': cid, 'type': 'edge_mitre', 'a': a, 'a_edge': edge_facing(comps0[a], c['edge']), 'b': b,
                 'b_edge': edge_facing(comps0[b], c['into_edge'])}
            if c.get('bevel', True):
                j['bevel'] = True
            if isinstance(c.get('fasteners'), dict):
                j['fasteners'] = c['fasteners']
            joints.append((j, c, cid, cline))
            continue
        want = _parse_dir(c.get('edge'))
        if A.rot or B.rot:
            _connect_tilted(comps, comps0, A, B, c, cid, cline, ctype, want, joints, diags)
            continue
        ct = _contact(A, B, want)
        if ct is None:
            diags.append(diag('error', 'NO_CONTACT', f"Connection '{cid}': no end face of '{a}' meets a broad face of '{b}'. For "
                              f"{ctype}, an edge of '{a}' must sit against the flat face of '{b}' (they must overlap side-on, "
                              f"and '{b}''s thickness axis must point at '{a}').", connection=cid, board=a, line=cline))
            continue
        k, e, gap = ct['axis'], ct['sign'], ct['gap']
        axis_name = AXES[k]
        if gap > TOL['contact'] or gap < -TOL['contact']:
            if gap > 0:
                msg = (f"Connection '{cid}': '{a}' stops {gap:.2f} mm short of '{b}' along {axis_name} — an unintended gap.")
                fixes = [_move_fix(A, k, gap * e, f"Move '{a}' {gap:.2f} mm along {_dir(k, e)} to touch '{b}'", abs(gap) <= SAFE_MOVE),
                         _resize_fix(A, k, e, gap, f"Extend '{a}' by {gap:.2f} mm towards '{b}'")]
                code = 'CONNECTION_GAP'
            else:
                pen = -gap
                msg = (f"Connection '{cid}': '{a}' runs {pen:.2f} mm into '{b}' along {axis_name}"
                       + (" — exactly its thickness: account for the board thickness (e.g. leg height = overall height − top "
                          "thickness)." if abs(pen - B.t) < 0.01 else " — boards overlap."))
                fixes = [_resize_fix(A, k, e, -pen, f"Shorten '{a}' by {pen:.2f} mm so it ends at the face of '{b}'"),
                         _move_fix(A, k, -pen * e, f"Move '{a}' {pen:.2f} mm away from '{b}'", pen <= SAFE_MOVE)]
                code = 'CONNECTION_OVERLAP'
            diags.append(diag('error', code, msg, connection=cid, board=a, line=cline or A.line, fixes=fixes,
                              gap=round(gap, 3)))
            continue
        if ctype == 'tab_slot':
            nax = ct['n']
            margin = min(A.lo[nax] - B.lo[nax], B.hi[nax] - A.hi[nax])
            if margin < TOL['min_edge_margin']:
                need = TOL['rec_edge_margin'] - margin
                inward = 1 if (A.lo[nax] - B.lo[nax]) < (B.hi[nax] - A.hi[nax]) else -1
                diags.append(diag('error', 'SLOT_AT_EDGE',
                                  f"Connection '{cid}': '{a}' is {max(margin, 0):.2f} mm from the edge of '{b}' along {AXES[nax]}. A slot "
                                  f"needs at least {TOL['min_edge_margin']} mm (recommended {TOL['rec_edge_margin']} mm) of '{b}' "
                                  f"around it — inset '{a}' or enlarge '{b}'.", connection=cid, board=a, line=cline or A.line,
                                  fixes=[_move_fix(A, nax, need * inward, f"Move '{a}' {need:.2f} mm inward along {AXES[nax]}", False),
                                         _resize_fix(B, nax, -inward, need, f"Enlarge '{b}' by {need:.2f} mm on that side")]))
                continue
            tabs, err = _tabs_for(comps[a], A, B, ct, c, cid)
            if err:
                diags.append(diag('error', 'CONTACT_TOO_SHORT', f"Connection '{cid}': {err}.", connection=cid, line=cline))
                continue
            comps[a].setdefault('tabs', []).extend(tabs)
            for t in tabs:
                joints.append(({'id': t['id'], 'type': 'tab_slot', 'a': a, 'tab': t['id'], 'b': b}, c, cid, cline))
        else:  # butt
            j = {'id': cid, 'type': 'edge_butt', 'a': a, 'a_edge': edge_facing(comps0[a], _dir(k, e)), 'b': b}
            if _add_fasteners(j, c, cid, cline, diags):
                joints.append((j, c, cid, cline))

    if any(d['severity'] == 'error' for d in diags):
        result['source_map'] = source_map
        return result

    design = normalize_design({
        'id': design_id, 'name': str(product.get('name') or 'AI design')[:200],
        'description': str(product.get('description') or '')[:2000], 'joinery': joinery, 'material': mat,
        'components': list(comps.values()), 'joints': []})
    design['sheet'] = _auto_sheet(design, mat, data)
    design['source'] = {'format': FORMAT, 'code': None}

    for j, c, cid, cline in joints:
        res = join(design, j, auto_repair=True, whole_design_check=False)
        if res['accepted']:
            design = res['design']
            continue
        errs = [i for i in res['issues'] if i['severity'] == 'error']
        first = errs[0] if errs else {'code': res['status'], 'message': res['status']}
        fixes = []
        sug = first.get('suggestion')
        if sug and sug.get('action') == 'translate' and sug['component'] in boards:
            bd = boards[sug['component']]
            delta = sug['delta']
            mag = math.sqrt(sum(v * v for v in delta))
            pos = [round(bd.raw['position'][i] + delta[i], 4) for i in range(3)]
            fixes.append({'id': f'move-{bd.id}', 'title': f"Move '{bd.id}' by [{', '.join(f'{v:g}' for v in delta)}] mm",
                          'safe': mag <= SAFE_MOVE, 'edits': [{'board': bd.id, 'field': 'position', 'value': pos}]})
        diags.append(diag('error', first['code'], f"Connection '{cid}' could not be joined ({res['status']}): {first['message']}",
                          connection=cid, board=j['a'], line=cline or boards[j['a']].line, fixes=fixes or None))
        design['joints'].append(dict(j, status='detached', detached_reason=first['code']))

    # Overall dimensions (the classic AI mistake: forgetting to subtract board thickness)
    ov = product.get('overall') if isinstance(product.get('overall'), dict) else {}
    corners = [_frame(cm).to_world([x, y, z]) for cm in design['components'] for x, y in cm['outline']
               for z in (-boards[cm['id']].t / 2, boards[cm['id']].t / 2)]
    lo = [min(q[i] for q in corners) for i in range(3)]
    hi = [max(q[i] for q in corners) for i in range(3)]
    for name, i in (('length', 0), ('height', 1), ('depth', 2)):
        if _num(ov.get(name)) and abs((hi[i] - lo[i]) - ov[name]) > 0.5:
            diags.append(diag('warning', 'OVERALL_MISMATCH', f"The boards span {hi[i] - lo[i]:.1f} mm in {AXES[i]} ({name}) but "
                              f"product.overall.{name} is {ov[name]:g} mm.", path=f'product.overall.{name}',
                              line=_key_line(src, name, off)))
    result['source_map'] = source_map
    return _finish(design, result, boards, run_production)


def _finish(design, result, boards, run_production):
    from .views import model3d, production_package
    diags = result['diagnostics']
    report = validate_design(design)
    known = {(d.get('connection'), d['code']) for d in diags}
    for i in report['issues']:
        if i['code'] in ('JOINT_NOT_JOINED',):
            continue
        comp = next((c for c in i.get('components', []) if c in boards), (i.get('components') or [None])[0])
        fixes = None
        sug = i.get('suggestion')
        if sug and sug.get('action') == 'translate' and sug.get('component') in boards:
            bd = boards[sug['component']]
            pos = [round(bd.raw['position'][k] + sug['delta'][k], 4) for k in range(3)]
            mag = math.sqrt(sum(v * v for v in sug['delta']))
            fixes = [{'id': f"move-{bd.id}", 'title': f"Move '{bd.id}' by [{', '.join(f'{v:g}' for v in sug['delta'])}] mm",
                      'safe': mag <= SAFE_MOVE, 'edits': [{'board': bd.id, 'field': 'position', 'value': pos}]}]
        diags.append(diag(i['severity'], i['code'], i['message'], board=comp,
                          line=boards[comp].line if comp in boards else None, components=i.get('components'),
                          location=i.get('location'), fixes=fixes))
    result['design'] = design
    result['validation'] = {'valid': report['valid'], 'complete': report['complete'], 'summary': report['summary']}
    result['model3d'] = model3d(design, report)
    if run_production and design['components']:
        try:
            pkg = production_package(design, {'compensate_kerf': True})
            result['layout'] = {'nesting': pkg['nesting'], 'cut': pkg['cut'], 'ready_for_production': pkg['ready_for_production'],
                                'blocking_issues': pkg['blocking_issues'][:50]}
            result['cut_list'] = pkg.get('cut_list')
            mfg = pkg.get('manufacturing') or {}
            result['manufacturing'] = {k: mfg[k] for k in ('summary', 'assembly') if k in mfg}
        except Exception as e:
            diags.append(diag('warning', 'PRODUCTION_UNAVAILABLE', f'Cut sheets could not be computed: {e}'))
    errors = sum(1 for d in diags if d['severity'] == 'error')
    result['summary'] = {'boards': len(design['components']), 'joints': len(design['joints']),
                         'joined': sum(1 for j in design['joints'] if j.get('status') == 'joined'),
                         'errors': errors, 'warnings': sum(1 for d in diags if d['severity'] == 'warning')}
    result['ok'] = errors == 0
    return result


def apply_code_fix(text, fix):
    """Apply a fix's edits to the source (re-serialised, 2-space indent). Used by tests and the API."""
    data, _src, _off, diags = parse_source(text)
    if data is None:
        raise CompileError(diags[0]['message'])
    by_id = {b.get('id'): b for b in data.get('boards', []) if isinstance(b, dict)}
    for ed in fix['edits']:
        if ed.get('board'):
            by_id[ed['board']][ed['field']] = ed['value']
        else:
            data[ed['field']] = ed['value']
    return pretty_json(data)


def pretty_json(data):
    """2-space JSON with number-only arrays on one line, so [x, y, z] stays readable (strings are never touched)."""
    text = json.dumps(data, indent=2)
    atom = r'-?[\d.eE+]+'
    return re.sub(r'\[\s*(' + atom + r'(?:\s*,\s*' + atom + r')*)\s*\]',
                  lambda m: '[' + ', '.join(x.strip() for x in m.group(1).split(',')) + ']', text)
