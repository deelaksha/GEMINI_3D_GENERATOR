"""
Board design data model.

A design is plain JSON (never executable code):

  design = {
    id, name, description, revision,
    material: {name, thickness, kerf, clearance, color},
    sheet:    {width, height, spacing},
    components: [component, ...],
    joints:     [joint, ...]
  }

  component = {
    id, name, group,
    thickness?            # overrides material.thickness
    color?                # optional finish tint
    outline: [[x, y], ...]      # base outline, CCW, local mm
    features: [                 # interior cut-outs
      {id, kind: 'slot' | 'hole' | 'opening', shape: 'rect' | 'circle',
       center: [x, y], width, height, angle, diameter, note?}
    ],
    tabs: [                     # tenons protruding from an outline edge
      {id, edge: <base outline edge index>, offset: <mm from edge start to tab centre>,
       width, depth}
    ],
    placement: {position: [x, y, z], rotation: [rx, ry, rz]}   # degrees, Euler XYZ
  }

Feature kinds have distinct meaning and are never interchangeable:
  slot    - receiver for a tab; must be referenced by a joint (else UNUSED_SLOT warning)
  hole    - functional hole (pivot, dowel, line hole); kept as-is
  opening - intentional design opening (cockpit, window, lightening hole); the
            engine never fills, moves or places joints inside it
"""
import contextvars
import copy
import math
import re

from . import geometry as G
from . import shapes as SH

FEATURE_KINDS = ('slot', 'hole', 'opening')
FEATURE_SHAPES = ('rect', 'circle', 'polygon')
MARK_KINDS = ('engrave', 'pocket')   # non-through machining: never holes for collision / joint checks
JOINT_TYPES = ('tab_slot', 'edge_butt', 'edge_mitre', 'face_lap', 'hinge', 'finger', 'cross_lap')
# Glue-free products (cardboard, friction-fit board) can only use mechanical interlocks.
JOINERY_MODES = ('interlocking', 'glue_allowed')
MOUNTINGS = ('floor', 'wall')   # how the product is held: standing on the floor (default) or fixed to a wall (support.py)
INTERLOCKING_JOINTS = ('tab_slot', 'finger', 'cross_lap')   # glue-free: finger = box corner, cross_lap = egg-crate
# Material families; manufacturing.MATERIALS holds their stock and tolerance data.
MATERIAL_TYPES = ('plywood', 'mdf', 'particle_board', 'solid_wood', 'hardboard', 'cardboard', 'other')
# Mechanical fasteners for edge_butt (and coplanar edge_mitre: dowel only); see manufacturing.FASTENERS.
FASTENER_KINDS = ('screw', 'confirmat', 'dowel')
GRAIN = ('none', 'x', 'y')   # grain direction in the component's local frame

LIMITS = {
    'max_components': 100_000,     # no practical limit; only stops a runaway "repeat" from freezing the server
    'max_outline_points': 2048,   # curved outlines are flattened (shapes.FLATTEN_TOL)
    'max_marks': 400,          # engraved text is one mark per stroke
    'max_hinge_lines': 5000,
    'max_features': 100_000,       # slots, holes, openings on one board (a base with hundreds of slats)
    'max_tabs': 32,
    'max_joints': 1_000_000,
    'max_coord': 5000.0,
    'min_thickness': 0.5,
    'max_thickness': 50.0,    # solid-wood worktops / table tops (38-40 mm)
    'max_kerf': 6.0,          # panel-saw blades cut 3.2-4.8 mm
}

DEFAULT_MATERIAL = {'name': 'Birch plywood 3 mm', 'thickness': 3.0, 'kerf': 0.15,
                    'clearance': 0.10, 'color': '#d9b98b'}
DEFAULT_SHEET = {'width': 600.0, 'height': 400.0, 'spacing': 6.0}

ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$')


class SchemaError(ValueError):
    """Raised when client-supplied data is structurally invalid."""

    def __init__(self, message, path=None):
        super().__init__(message)
        self.path = path

    def to_dict(self):
        return {'code': 'SCHEMA_ERROR', 'message': str(self), 'path': self.path}


# ---------------------------------------------------------------------------
# Input normalisation (structural validation only; geometry rules live in validation.py)
# ---------------------------------------------------------------------------

def _num(v, path, lo=None, hi=None):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise SchemaError(f'{path} must be a finite number', path)
    v = float(v)
    if lo is not None and v < lo:
        raise SchemaError(f'{path} must be >= {lo}', path)
    if hi is not None and v > hi:
        raise SchemaError(f'{path} must be <= {hi}', path)
    return v


def _vec(v, n, path, lim=LIMITS['max_coord']):
    if not isinstance(v, (list, tuple)) or len(v) != n:
        raise SchemaError(f'{path} must be an array of {n} numbers', path)
    return [_num(c, f'{path}[{i}]', -lim, lim) for i, c in enumerate(v)]


def check_id(value, path):
    if not isinstance(value, str) or not ID_RE.match(value):
        raise SchemaError(f'{path} must match {ID_RE.pattern}', path)
    return value


def _text(v, path, maxlen=200, default=''):
    if v is None:
        return default
    if not isinstance(v, str):
        raise SchemaError(f'{path} must be a string', path)
    return v[:maxlen]


def _points(raw, path, minimum):
    if not isinstance(raw, list) or not (minimum <= len(raw) <= LIMITS['max_outline_points']):
        raise SchemaError(f'{path} must have {minimum}..{LIMITS["max_outline_points"]} points', path)
    return [_vec(p, 2, f'{path}[{i}]') for i, p in enumerate(raw)]


def _arcs(raw, n, path):
    """Arc metadata: polygon vertices start..end lie on a circular arc (used to export true arcs)."""
    if not isinstance(raw, list):
        raise SchemaError(f'{path} must be a list', path)
    out = []
    for i, a in enumerate(raw):
        p = f'{path}[{i}]'
        if not isinstance(a, dict):
            raise SchemaError(f'{p} must be an object', p)
        st, en = a.get('start'), a.get('end')
        if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v < n for v in (st, en)):
            raise SchemaError(f'{p}.start/end must be vertex indices', p)
        out.append({'start': st, 'end': en, 'center': _vec(a.get('center'), 2, p + '.center'),
                    'radius': _num(a.get('radius'), p + '.radius', 0.001, LIMITS['max_coord']), 'ccw': bool(a.get('ccw'))})
    return out


def _marks(raw, path):
    if not isinstance(raw, list) or len(raw) > LIMITS['max_marks']:
        raise SchemaError(f'{path} must be a list of <= {LIMITS["max_marks"]}', path)
    return [normalize_mark(m, f'{path}[{i}]') for i, m in enumerate(raw)]


def _images(raw, path):
    """Raster engravings: {'id', 'src': data:image URI, 'corners': [top-left, top-right, bottom-left] local mm}."""
    if not isinstance(raw, list) or len(raw) > 8:
        raise SchemaError(f'{path} must be a list of <= 8 images', path)
    out = []
    for i, im in enumerate(raw):
        p = f'{path}[{i}]'
        if not (isinstance(im, dict) and isinstance(im.get('src'), str) and im['src'].startswith('data:image/')
                and len(im['src']) <= 400_000 and isinstance(im.get('corners'), list) and len(im['corners']) == 3):
            raise SchemaError(f'{p} must be {{"id", "src": data:image URI (<= 400 KB), "corners": 3 points}}', p)
        out.append({'id': check_id(im.get('id'), p + '.id'), 'src': im['src'],
                    'corners': [_vec(q, 2, f'{p}.corners[{k}]') for k, q in enumerate(im['corners'])]})
    return out


def _decals(raw, path):
    """Printed / painted artwork on a face: {'id', 'face': front|back, 'color': #rrggbb} plus 'points' (a filled
    polygon, local mm) or 'lines' + 'width' (lettering strokes). Never cut."""
    if not isinstance(raw, list) or len(raw) > 2000:
        raise SchemaError(f'{path} must be a list of <= 2000 decals', path)
    out = []
    for i, d in enumerate(raw):
        p = f'{path}[{i}]'
        if not (isinstance(d, dict) and d.get('face') in ('front', 'back') and isinstance(d.get('color'), str)
                and re.fullmatch(r'#[0-9a-fA-F]{6}', d['color'])):
            raise SchemaError(f'{p} must be {{"id", "face": "front"|"back", "color": #rrggbb, ...}}', p)
        e = {'id': check_id(d.get('id'), p + '.id'), 'face': d['face'], 'color': d['color']}
        if isinstance(d.get('points'), list) and len(d['points']) >= 3:
            e['points'] = [_vec(q, 2, f'{p}.points[{k}]') for k, q in enumerate(d['points'][:LIMITS['max_outline_points']])]
        elif isinstance(d.get('lines'), list) and d['lines']:
            e['lines'] = [[_vec(q, 2, f'{p}.lines[{k}]') for q in ln] for k, ln in enumerate(d['lines'][:500])
                          if isinstance(ln, list) and len(ln) >= 2]
            e['width'] = _num(d.get('width', 1), p + '.width', 0.05, 100)
        else:
            raise SchemaError(f'{p} needs "points" (a polygon) or "lines" (strokes)', p)
        out.append(e)
    return out


def _hinges(raw, path):
    """Living hinges: through-cut line segments (local mm) that let the board bend. Bending is not simulated."""
    if not isinstance(raw, list):
        raise SchemaError(f'{path} must be a list', path)
    out, total = [], 0
    for i, h in enumerate(raw):
        p = f'{path}[{i}]'
        lines = h.get('lines') if isinstance(h, dict) else None
        if not isinstance(lines, list) or not lines:
            raise SchemaError(f'{p}.lines must be a non-empty list of [[x, y], [x, y]] segments', p + '.lines')
        total += len(lines)
        if total > LIMITS['max_hinge_lines']:
            raise SchemaError(f'{path}: at most {LIMITS["max_hinge_lines"]} hinge cut lines per board', path)
        segs = []
        for k, ln in enumerate(lines):
            if not (isinstance(ln, list) and len(ln) == 2):
                raise SchemaError(f'{p}.lines[{k}] must be [[x, y], [x, y]]', f'{p}.lines[{k}]')
            segs.append([_vec(q, 2, f'{p}.lines[{k}]') for q in ln])
        out.append({'id': check_id(h.get('id'), p + '.id'), 'lines': segs})
    return out


def normalize_mark(m, path):
    """Engraving (polyline, open or closed) or pocket (closed, partial depth). Never cuts through the board."""
    if not isinstance(m, dict):
        raise SchemaError(f'{path} must be an object', path)
    kind = m.get('kind')
    if kind not in MARK_KINDS:
        raise SchemaError(f'{path}.kind must be one of {MARK_KINDS}', path + '.kind')
    closed = True if kind == 'pocket' else bool(m.get('closed', False))
    pts = _points(m.get('points'), path + '.points', 3 if closed else 2)
    arcs = m.get('arcs') or []
    if closed and G.signed_area(pts) < 0:
        pts, arcs = SH.reverse(pts, arcs)
    out = {'id': check_id(m.get('id'), path + '.id'), 'kind': kind, 'points': pts, 'closed': closed,
           'depth': _num(m.get('depth', 0.5 if kind == 'engrave' else None), path + '.depth', 0.05, LIMITS['max_thickness'])}
    if arcs:
        out['arcs'] = _arcs(arcs, len(pts), path + '.arcs')
    if m.get('note'):
        out['note'] = _text(m['note'], path + '.note')
    return out


def normalize_feature(f, path):
    if not isinstance(f, dict):
        raise SchemaError(f'{path} must be an object', path)
    kind = f.get('kind')
    if kind not in FEATURE_KINDS:
        raise SchemaError(f'{path}.kind must be one of {FEATURE_KINDS}', path + '.kind')
    shape = f.get('shape', 'rect')
    if shape not in FEATURE_SHAPES:
        raise SchemaError(f'{path}.shape must be one of {FEATURE_SHAPES}', path + '.shape')
    if shape == 'polygon':
        pts = _points(f.get('points'), path + '.points', 3)
        if G.signed_area(pts) < 0:
            pts, arcs = SH.reverse(pts, f.get('arcs') or [])
        else:
            arcs = f.get('arcs') or []
        x0, y0, x1, y1 = G.bbox(pts)
        center = _vec(f['center'], 2, path + '.center') if f.get('center') is not None else [(x0 + x1) / 2, (y0 + y1) / 2]
        out = {'id': check_id(f.get('id'), path + '.id'), 'kind': kind, 'shape': shape, 'center': center,
               'points': pts}
        if arcs:
            out['arcs'] = _arcs(arcs, len(pts), path + '.arcs')
    else:
        out = {'id': check_id(f.get('id'), path + '.id'), 'kind': kind, 'shape': shape,
               'center': _vec(f.get('center'), 2, path + '.center')}
    if shape == 'rect':
        out['width'] = _num(f.get('width'), path + '.width', 0.05, LIMITS['max_coord'])
        out['height'] = _num(f.get('height'), path + '.height', 0.05, LIMITS['max_coord'])
        out['angle'] = _num(f.get('angle', 0.0), path + '.angle', -360, 360)
        if f.get('corner_radius'):
            out['corner_radius'] = _num(f['corner_radius'], path + '.corner_radius', 0, min(out['width'], out['height']) / 2)
    elif shape == 'circle':
        out['diameter'] = _num(f.get('diameter'), path + '.diameter', 0.05, LIMITS['max_coord'])
    if f.get('note'):
        out['note'] = _text(f.get('note'), path + '.note')
    if f.get('generated_by'):
        out['generated_by'] = _text(f.get('generated_by'), path + '.generated_by', 64)
    return out


def normalize_tab(t, path):
    if not isinstance(t, dict):
        raise SchemaError(f'{path} must be an object', path)
    edge = t.get('edge')
    if isinstance(edge, bool) or not isinstance(edge, int) or edge < 0:
        raise SchemaError(f'{path}.edge must be a non-negative integer', path + '.edge')
    return {'id': check_id(t.get('id'), path + '.id'), 'edge': edge,
            'offset': _num(t.get('offset'), path + '.offset', 0, LIMITS['max_coord']),
            'width': _num(t.get('width'), path + '.width', 0.5, LIMITS['max_coord']),
            'depth': _num(t.get('depth'), path + '.depth', 0.1, 100.0),
            **({'protrude': True} if t.get('protrude') else {})}   # stands proud of the receiver on purpose


def normalize_component(c, path='component'):
    if not isinstance(c, dict):
        raise SchemaError(f'{path} must be an object', path)
    outline = c.get('outline')
    if not isinstance(outline, list) or not (3 <= len(outline) <= LIMITS['max_outline_points']):
        raise SchemaError(f'{path}.outline must have 3..{LIMITS["max_outline_points"]} points', path + '.outline')
    outline = [_vec(p, 2, f'{path}.outline[{i}]') for i, p in enumerate(outline)]
    notes = []
    outline_arcs = c.get('arcs') or []
    if G.signed_area(outline) < 0:
        outline, outline_arcs = SH.reverse(outline, outline_arcs)
        notes.append('outline was clockwise and has been normalised to counter-clockwise; '
                     'edge indices refer to the stored (CCW) outline')
    features = c.get('features') or []
    tabs = c.get('tabs') or []
    if not isinstance(features, list) or len(features) > LIMITS['max_features']:
        raise SchemaError(f'{path}.features must be a list of <= {LIMITS["max_features"]}', path + '.features')
    if not isinstance(tabs, list) or len(tabs) > LIMITS['max_tabs']:
        raise SchemaError(f'{path}.tabs must be a list of <= {LIMITS["max_tabs"]}', path + '.tabs')
    pl = c.get('placement') or {}
    if not isinstance(pl, dict):
        raise SchemaError(f'{path}.placement must be an object', path + '.placement')
    out = {
        'id': check_id(c.get('id'), path + '.id'),
        'name': _text(c.get('name'), path + '.name', default=c.get('id')),
        'group': _text(c.get('group'), path + '.group', 64, default='General'),
        'outline': outline,
        'features': [normalize_feature(f, f'{path}.features[{i}]') for i, f in enumerate(features)],
        'tabs': [normalize_tab(t, f'{path}.tabs[{i}]') for i, t in enumerate(tabs)],
        **({'arcs': _arcs(outline_arcs, len(outline), path + '.arcs')} if outline_arcs else {}),
        **({'marks': _marks(c.get('marks'), path + '.marks')} if c.get('marks') else {}),
        **({'hinges': _hinges(c.get('hinges'), path + '.hinges')} if c.get('hinges') else {}),
        **({'images': _images(c.get('images'), path + '.images')} if c.get('images') else {}),
        **({'decals': _decals(c.get('decals'), path + '.decals')} if c.get('decals') else {}),
        'placement': {
            'position': _vec(pl.get('position', [0, 0, 0]), 3, path + '.placement.position'),
            'rotation': _vec(pl.get('rotation', [0, 0, 0]), 3, path + '.placement.rotation', 720),
        },
    }
    if c.get('thickness') is not None:
        out['thickness'] = _num(c['thickness'], path + '.thickness',
                                LIMITS['min_thickness'], LIMITS['max_thickness'])
    if c.get('colors') is not None:            # per-face finish (colouring on): front / back / edges, #rrggbb
        cols = c['colors']
        if not (isinstance(cols, dict) and set(cols) <= {'front', 'back', 'edges'}
                and all(isinstance(v, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', v) for v in cols.values())):
            raise SchemaError(f'{path}.colors must be {{"front", "back", "edges"}} of #rrggbb', path + '.colors')
        out['colors'] = dict(cols)
    if c.get('color') is not None:
        col = _text(c.get('color'), path + '.color', 16)
        if not re.match(r'^#[0-9a-fA-F]{6}$', col):
            raise SchemaError(f'{path}.color must be #rrggbb', path + '.color')
        out['color'] = col
    if c.get('description'):
        out['description'] = _text(c.get('description'), path + '.description', 500)
    if c.get('grain_locked'):
        out['grain_locked'] = True  # nesting may not rotate this part (grain / print direction)
    if c.get('grain') not in (None, 'none'):
        if c['grain'] not in GRAIN:
            raise SchemaError(f'{path}.grain must be one of {GRAIN}', path + '.grain')
        out['grain'] = c['grain']  # visible grain runs along local x or y; nesting aligns it with the sheet grain
    if c.get('material') is not None:
        out['material'] = normalize_material_ref(c['material'], path + '.material')
    if c.get('edge_banding'):
        eb = c['edge_banding']
        if not isinstance(eb, list) or len(eb) > len(outline):
            raise SchemaError(f'{path}.edge_banding must be a list of <= {len(outline)} items', path + '.edge_banding')
        out['edge_banding'] = []
        for i, b in enumerate(eb):
            bp = f'{path}.edge_banding[{i}]'
            if not isinstance(b, dict):
                raise SchemaError(f'{bp} must be an object', bp)
            e = b.get('edge')
            if isinstance(e, bool) or not isinstance(e, int) or not (0 <= e < len(outline)):
                raise SchemaError(f'{bp}.edge must be an outline edge index', bp + '.edge')
            out['edge_banding'].append({'edge': e, 'thickness': _num(b.get('thickness'), bp + '.thickness', 0.3, 5.0),
                                        **({'material': _text(b['material'], bp + '.material', 64)}
                                           if b.get('material') else {})})
        if len({b['edge'] for b in out['edge_banding']}) != len(out['edge_banding']):
            raise SchemaError(f'{path}.edge_banding lists an edge twice', path + '.edge_banding')
    return out, notes


def normalize_material_ref(m, path):
    """Per-component material override: {name?, type?} (thickness stays on the component)."""
    if not isinstance(m, dict):
        raise SchemaError(f'{path} must be an object', path)
    out = {}
    if m.get('name'):
        out['name'] = _text(m['name'], path + '.name')
    if m.get('type') is not None:
        if m['type'] not in MATERIAL_TYPES:
            raise SchemaError(f'{path}.type must be one of {MATERIAL_TYPES}', path + '.type')
        out['type'] = m['type']
    return out


def normalize_fasteners(f, path):
    if not isinstance(f, dict):
        raise SchemaError(f'{path} must be an object', path)
    if f.get('kind') not in FASTENER_KINDS:
        raise SchemaError(f'{path}.kind must be one of {FASTENER_KINDS}', path + '.kind')
    out = {'kind': f['kind']}
    if f.get('count') is not None:
        n = f['count']
        if isinstance(n, bool) or not isinstance(n, int) or not (1 <= n <= 20):
            raise SchemaError(f'{path}.count must be an integer 1..20', path + '.count')
        out['count'] = n
    if f.get('diameter') is not None:
        out['diameter'] = _num(f['diameter'], path + '.diameter', 2.0, 20.0)
    if f.get('length') is not None:
        out['length'] = _num(f['length'], path + '.length', 5.0, 200.0)
    if f.get('end') is not None:   # distance of the first/last fastener from the contact ends (staggering)
        out['end'] = _num(f['end'], path + '.end', 5.0, 1000.0)
    return out


def normalize_joint(j, path='joint'):
    if not isinstance(j, dict):
        raise SchemaError(f'{path} must be an object', path)
    jtype = j.get('type')
    if jtype not in JOINT_TYPES:
        raise SchemaError(f'{path}.type must be one of {JOINT_TYPES}', path + '.type')
    out = {'id': check_id(j.get('id'), path + '.id'), 'type': jtype,
           'a': check_id(j.get('a'), path + '.a'), 'b': check_id(j.get('b'), path + '.b')}
    if jtype == 'tab_slot':
        out['tab'] = check_id(j.get('tab'), path + '.tab')
        if j.get('slot') is not None:
            out['slot'] = check_id(j.get('slot'), path + '.slot')
    if jtype in ('edge_butt', 'edge_mitre', 'hinge'):
        e = j.get('a_edge')
        if isinstance(e, bool) or not isinstance(e, int) or e < 0:
            raise SchemaError(f'{path}.a_edge must be a non-negative integer', path + '.a_edge')
        out['a_edge'] = e
    if jtype == 'edge_mitre':
        e = j.get('b_edge')
        if isinstance(e, bool) or not isinstance(e, int) or e < 0:
            raise SchemaError(f'{path}.b_edge must be a non-negative integer', path + '.b_edge')
        out['b_edge'] = e
        if j.get('bevel'):
            out['bevel'] = True   # both edges bevelled to half the corner angle (saw / CNC; not laser)
    if jtype in ('edge_butt', 'edge_mitre') and j.get('fasteners') is not None:
        out['fasteners'] = normalize_fasteners(j['fasteners'], path + '.fasteners')
    if jtype == 'hinge':
        # a = door, a_edge = its hinge edge, b = the carcass board it hangs on
        if j.get('count') is not None:
            n = j['count']
            if isinstance(n, bool) or not isinstance(n, int) or not (1 <= n <= 8):
                raise SchemaError(f'{path}.count must be an integer 1..8', path + '.count')
            out['count'] = n
        if j.get('gap') is not None:
            out['gap'] = _num(j['gap'], path + '.gap', 0.0, 5.0)
    for k in ('status', 'repairs', 'joined_at', 'detached_reason'):
        if k in j:
            out[k] = copy.deepcopy(j[k])
    return out


def _source(v):
    """Optional AI Design Canvas source ({format, code}) kept with a design so it can be reopened in the editor."""
    if not isinstance(v, dict) or not v.get('format'):
        return {}
    code = v.get('code')
    if code is not None and (not isinstance(code, str) or len(code) > 1_000_000):
        raise SchemaError('source.code must be a string of at most 1,000,000 characters', 'source.code')
    return {'source': {'format': _text(v['format'], 'source.format', 40), 'code': code}}


def _joinery(v):
    v = v or 'interlocking'
    if v not in JOINERY_MODES:
        raise SchemaError(f'joinery must be one of {JOINERY_MODES}', 'joinery')
    return v


def _mounting(v):
    """Optional; only stored when given, so existing designs are unchanged (absent = 'floor')."""
    if v is None:
        return {}
    if v not in MOUNTINGS:
        raise SchemaError(f'mounting must be one of {MOUNTINGS}', 'mounting')
    return {'mounting': v}


MOTION_AXES = ('x', 'y', 'z')


def normalize_motions(raw, comp_ids):
    """Stored moving parts (the canvas compiler's "motions"). A motion whose boards were deleted since is dropped; the
    rest keeps only its known fields."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise SchemaError('motions must be a list', 'motions')
    out = []
    for i, m in enumerate(raw):
        p = f'motions[{i}]'
        if not isinstance(m, dict) or m.get('type') not in ('rotate', 'slide'):
            raise SchemaError(f'{p}.type must be "rotate" or "slide"', p + '.type')
        boards = [b for b in m.get('boards') or [] if b in comp_ids]
        if not boards or m.get('on') not in comp_ids:
            continue
        rng = m.get('range')
        if not (isinstance(rng, list) and len(rng) == 2):
            raise SchemaError(f'{p}.range must be [from, to]', p + '.range')
        nm = {'id': check_id(m.get('id'), p + '.id'), 'type': m['type'], 'boards': boards, 'on': m['on'],
              'range': [_num(rng[0], p + '.range', -LIMITS['max_coord'], LIMITS['max_coord']),
                        _num(rng[1], p + '.range', -LIMITS['max_coord'], LIMITS['max_coord'])]}
        if isinstance(m.get('driven_by'), str):           # a gear train / belt: it follows that motion at "ratio"
            nm['driven_by'] = check_id(m['driven_by'], p + '.driven_by')
            nm['ratio'] = _num(m.get('ratio'), p + '.ratio', -1e6, 1e6)
        if m['type'] == 'rotate':
            if m.get('axis') not in MOTION_AXES or not (isinstance(m.get('pivot'), list) and len(m['pivot']) == 3):
                raise SchemaError(f'{p} needs "axis" and "pivot"', p)
            nm.update(axis=m['axis'], pivot=[_num(v, p + '.pivot', -LIMITS['max_coord'], LIMITS['max_coord']) for v in m['pivot']])
            if isinstance(m.get('axle'), dict):
                nm['axle'] = {'diameter': _num(m['axle'].get('diameter'), p + '.axle.diameter', 1, 50),
                              **({'boards': [b for b in m['axle']['boards'] if b in comp_ids]}
                                 if isinstance(m['axle'].get('boards'), list) else {})}
        else:
            if m.get('direction') not in MOTION_AXES:
                raise SchemaError(f'{p}.direction must be "x", "y" or "z"', p + '.direction')
            nm['direction'] = m['direction']
        out.append(nm)
    return out


def normalize_design(d):
    if not isinstance(d, dict):
        raise SchemaError('design must be an object')
    mat = dict(DEFAULT_MATERIAL)
    mat.update(d.get('material') or {})
    sheet = dict(DEFAULT_SHEET)
    sheet.update(d.get('sheet') or {})
    comps_in = d.get('components') or []
    joints_in = d.get('joints') or []
    if len(comps_in) > LIMITS['max_components']:
        raise SchemaError(f'too many components (>{LIMITS["max_components"]})', 'components')
    if len(joints_in) > LIMITS['max_joints']:
        raise SchemaError(f'too many joints (>{LIMITS["max_joints"]})', 'joints')
    comps = []
    for i, c in enumerate(comps_in):
        nc, _ = normalize_component(c, f'components[{i}]')
        comps.append(nc)
    motions = normalize_motions(d.get('motions'), {c['id'] for c in comps})
    return {
        'id': check_id(d.get('id'), 'id'),
        'name': _text(d.get('name'), 'name', default=d.get('id')),
        'description': _text(d.get('description'), 'description', 2000),
        'revision': int(d.get('revision', 0)),
        'material': {
            'name': _text(mat.get('name'), 'material.name'),
            'thickness': _num(mat.get('thickness'), 'material.thickness',
                              LIMITS['min_thickness'], LIMITS['max_thickness']),
            'kerf': _num(mat.get('kerf'), 'material.kerf', 0, LIMITS['max_kerf']),
            'clearance': _num(mat.get('clearance'), 'material.clearance', 0, 2),
            'color': _text(mat.get('color'), 'material.color', 16, '#d9b98b'),
            **({'type': normalize_material_ref({'type': mat['type']}, 'material')['type']}
               if mat.get('type') is not None else {}),
        },
        'sheet': {
            'width': _num(sheet.get('width'), 'sheet.width', 10, LIMITS['max_coord']),
            'height': _num(sheet.get('height'), 'sheet.height', 10, LIMITS['max_coord']),
            'spacing': _num(sheet.get('spacing'), 'sheet.spacing', 0, 100),
        },
        'components': comps,
        'joints': [normalize_joint(j, f'joints[{i}]') for i, j in enumerate(joints_in)],
        'joinery': _joinery(d.get('joinery')),
        **_mounting(d.get('mounting')),
        **_source(d.get('source')),
        **({'motions': motions} if motions else {}),
        'created': d.get('created'),
        'updated': d.get('updated'),
    }


# ---------------------------------------------------------------------------
# Derived geometry
# ---------------------------------------------------------------------------

def thickness_of(design, comp):
    return comp.get('thickness', design['material']['thickness'])


def material_of(design, comp):
    """Effective stock material of a component: {name, type, thickness}."""
    m = design['material']
    ref = comp.get('material') or {}
    return {'name': ref.get('name', m['name']), 'type': ref.get('type', m.get('type', 'other')),
            'thickness': thickness_of(design, comp)}


def feature_polygon(f):
    if f['shape'] == 'circle':
        return G.circle_polygon(f['center'], f['diameter'])
    if f['shape'] == 'polygon':
        return f['points']
    if f.get('corner_radius'):
        return feature_shape(f)[0]
    return G.rect_polygon(f['center'], f['width'], f['height'], f.get('angle', 0.0))


def feature_shape(f):
    """(points, arcs) of a cut-out, with arc metadata for true-arc export (circles are exported natively)."""
    if f['shape'] == 'polygon':
        return f['points'], f.get('arcs', [])
    if f['shape'] == 'rect' and f.get('corner_radius'):
        return SH.shape_polygon({'shape': 'rect', 'center': f['center'], 'width': f['width'], 'height': f['height'],
                                 'corner_radius': f['corner_radius'], 'angle': f.get('angle', 0.0)})
    return feature_polygon(f), []


def edge_frame(outline, edge_index):
    """Start point, unit direction, outward normal and length of a CCW outline edge."""
    n = len(outline)
    a = outline[edge_index % n]
    b = outline[(edge_index + 1) % n]
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    d = (dx / L, dy / L) if L > G.EPS else (1.0, 0.0)
    return a, d, (d[1], -d[0]), L


def tab_geometry(comp, tab):
    """Local geometry of a tab: root centre, protrusion normal, along-edge direction."""
    a, d, n, L = edge_frame(comp['outline'], tab['edge'])
    root = (a[0] + d[0] * tab['offset'], a[1] + d[1] * tab['offset'])
    centre = (root[0] + n[0] * tab['depth'] / 2.0, root[1] + n[1] * tab['depth'] / 2.0)
    return {'root': root, 'centre': centre, 'dir': d, 'normal': n, 'edge_length': L}


def cut_outline(comp):
    """Outer cut profile: base outline with tabs inserted on their edges."""
    outline = comp['outline']
    n = len(outline)
    by_edge = {}
    for t in comp.get('tabs', []):
        if t['edge'] < n:
            by_edge.setdefault(t['edge'], []).append(t)
    pts = []
    for i in range(n):
        a, d, nrm, L = edge_frame(outline, i)
        pts.append([a[0], a[1]])
        for t in sorted(by_edge.get(i, []), key=lambda t: t['offset']):
            s = t['offset'] - t['width'] / 2.0
            e = t['offset'] + t['width'] / 2.0
            p1 = [a[0] + d[0] * s, a[1] + d[1] * s]
            p4 = [a[0] + d[0] * e, a[1] + d[1] * e]
            p2 = [p1[0] + nrm[0] * t['depth'], p1[1] + nrm[1] * t['depth']]
            p3 = [p4[0] + nrm[0] * t['depth'], p4[1] + nrm[1] * t['depth']]
            pts.extend([p1, p2, p3, p4])
    return pts


class Plate:
    """Cached derived geometry for one component in one design state."""

    def __init__(self, design, comp):
        self.comp = comp
        self.id = comp['id']
        self.t = thickness_of(design, comp)
        self.frame = G.Frame(comp['placement']['position'], comp['placement']['rotation'])
        self.outline = comp['outline']
        self.cut = cut_outline(comp)
        self.features = comp.get('features', [])
        self.feature_polys = [(f, feature_polygon(f)) for f in self.features]
        self._feature_boxes = [G.bbox(poly) for _f, poly in self.feature_polys]
        self.bbox2d = G.bbox(self.cut)
        self._aabb = None

    def signature(self):
        """Hashable identity of this plate's solid geometry (thickness, placement, cut profile, cut-outs)."""
        if getattr(self, '_sig', None) is None:
            self._sig = (self.id, self.t, tuple(self.comp['placement']['position']),
                         tuple(self.comp['placement']['rotation']), tuple(map(tuple, self.cut)),
                         tuple(tuple(map(tuple, poly)) for _f, poly in self.feature_polys))
        return self._sig

    def world_aabb(self):
        if self._aabb is None:
            x0, y0, x1, y1 = self.bbox2d
            h = self.t / 2.0
            pts = [self.frame.to_world([x, y, z]) for x in (x0, x1) for y in (y0, y1) for z in (-h, h)]
            self._aabb = ([min(p[i] for p in pts) for i in range(3)],
                          [max(p[i] for p in pts) for i in range(3)])
        return self._aabb

    def world_centre(self):
        lo, hi = self.world_aabb()
        return [(lo[i] + hi[i]) / 2.0 for i in range(3)]

    def is_material(self, pt, tol):
        """True if local 2D point lies inside solid material, at least `tol` from any cut edge."""
        x, y = pt
        bx0, by0, bx1, by1 = self.bbox2d
        if x <= bx0 + tol or x >= bx1 - tol or y <= by0 + tol or y >= by1 - tol:
            return False
        if not G.point_in_polygon(pt, self.cut) or G.near_boundary(pt, self.cut, tol):
            return False
        for (_f, poly), (fx0, fy0, fx1, fy1) in zip(self.feature_polys, self._feature_boxes):
            if x < fx0 - tol or x > fx1 + tol or y < fy0 - tol or y > fy1 + tol:
                continue
            if G.point_in_polygon(pt, poly) or G.near_boundary(pt, poly, tol):
                return False
        return True

    def feature_at(self, pt):
        for f, poly in self.feature_polys:
            if G.point_in_polygon(pt, poly):
                return f
        return None


def build_plates(design):
    return {c['id']: Plate(design, c) for c in design['components']}


COMPONENT_POSITIONS = contextvars.ContextVar('component_positions', default=None)   # (count, {id: first index})


def component_index(design, cid):
    """Index of the first component with id `cid`, or None. While a joining loop has recorded the positions (the ids
    and their order do not change there) this is a lookup, checked against the list, instead of a scan."""
    comps = design['components']
    pos = COMPONENT_POSITIONS.get()
    if pos is not None and len(comps) == pos[0]:
        i = pos[1].get(cid)
        if i is not None and comps[i]['id'] == cid:
            return i
    for k, c in enumerate(comps):
        if c['id'] == cid:
            return k
    return None


def find_component(design, cid):
    i = component_index(design, cid)
    return None if i is None else design['components'][i]


def find_joint(design, jid):
    for j in design['joints']:
        if j['id'] == jid:
            return j
    return None
