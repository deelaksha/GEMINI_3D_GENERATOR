"""
The field contract of `board-design/v1`: which keys each part of a design may have, so a field the compiler would
silently ignore is reported instead (an AI that invents "bevel_angle" or misspells "connections" learns it at once).

`check_fields(data)` walks the raw design (before repeat / mirror / assemblies are expanded) and returns diagnostics:
  UNKNOWN_FIELD (warning)    a key no part of the compiler reads, with a did-you-mean when one is close;
  MISSPELLED_FIELD (error)   a top-level key that is a near miss of a known one which is absent ("conections"): the
                             design means something else than it says (here: every connection would be inferred);
  INVALID_VALUE (warning)    an optional number that is not a finite number, so its default is used instead.
Shapes inside "profile" and "decals" are checked by the shape code itself and are not walked here.
"""
import difflib
import math

SHAPE = {'shape', 'center', 'width', 'height', 'corner_radius', 'angle', 'diameter', 'sides', 'rotation', 'teeth',
         'module', 'pressure_angle', 'backlash', 'points', 'symmetric', 'corners', 'exponent', 'start', 'segments'}
TOP = {'format', 'product', 'material', 'joinery', 'sheet', 'boards', 'connections', 'motions', 'assemblies',
       'instances', 'plan', 'part', 'auto_connect', 'consolidate', 'mounting'}
PRODUCT = {'name', 'description', 'overall', 'mounting'}
MATERIAL = {'name', 'type', 'thickness', 'kerf', 'clearance', 'color', 'colour'}
SHEET = {'width', 'height'}
BOARD = {'id', 'name', 'group', 'position', 'size', 'thickness', 'material', 'grain', 'normal', 'note', 'openings',
         'edge_banding', 'profile', 'engravings', 'rotate', 'repeat', 'mirror', 'radial', 'living_hinge', 'color',
         'colour', 'colors', 'decals'}
OPENING = SHAPE | {'id', 'kind', 'size', 'note', 'repeat'}
ENGRAVING = SHAPE | {'id', 'kind', 'depth', 'closed', 'text', 'position', 'align', 'src', 'size', 'note', 'repeat'}
REPEAT = {'count', 'step', 'rows', 'layers', 'grow', 'morph'}
RADIAL = {'count', 'axis', 'center', 'sweep', 'start'}
MIRROR = {'axis', 'at'}
ROTATE = {'axis', 'angle', 'pivot'}
LIVING_HINGE = {'from', 'to', 'lines_along', 'spacing', 'cut', 'bridge'}
EDGE_BANDING = {'edge', 'thickness', 'material'}
CONNECTION = {'id', 'type', 'board', 'boards', 'into', 'tabs', 'tab_width', 'tab_depth', 'edge', 'into_edge', 'fingers',
              'fasteners', 'count', 'gap', 'bevel', 'end', 'note', 'slot'}
FASTENERS = {'kind', 'count', 'diameter', 'length', 'end'}
MOTION = {'id', 'type', 'boards', 'on', 'axis', 'direction', 'pivot', 'range', 'axle', 'driven_by', 'ratio', 'link',
          'note'}
AXLE = {'diameter'}
LINK = {'rod', 'from', 'to', 'pin'}
ASSEMBLY = {'id', 'boards', 'connections', 'motions'}
INSTANCE = {'assembly', 'id', 'offset', 'flip', 'rotate', 'repeat', 'mirror'}

# optional numbers whose bad value is otherwise replaced by the default without a word
NUMBERS = {'material': ('kerf', 'clearance'), 'connection': ('tabs', 'tab_width', 'tab_depth', 'fingers', 'gap')}


def _diag(severity, code, message, path):
    return {'severity': severity, 'code': code, 'message': message, 'path': path}


def _keys(obj, allowed, path, out):
    if not isinstance(obj, dict):
        return
    for k in obj:
        if k in allowed:
            continue
        near = difflib.get_close_matches(k, sorted(allowed), n=1, cutoff=0.75)
        hint = f" - did you mean '{near[0]}'?" if near else ''
        out.append(_diag('warning', 'UNKNOWN_FIELD', f"{path} has a field '{k}' that the compiler does not read; it is "
                                                     f"ignored{hint}", f'{path}.{k}'))


def _numbers(obj, keys, path, out):
    if not isinstance(obj, dict):
        return
    for k in keys:
        v = obj.get(k)
        if k in obj and not (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)):
            out.append(_diag('warning', 'INVALID_VALUE', f"{path}.{k} must be a number (it is {v!r}); the default is "
                                                         f"used instead", f'{path}.{k}'))


def _list(v):
    return v if isinstance(v, list) else []


def _name(item, path):
    return f"{path} '{item['id']}'" if isinstance(item, dict) and isinstance(item.get('id'), str) else path


def _board(b, path, out):
    _keys(b, BOARD, path, out)
    if not isinstance(b, dict):
        return
    for o in _list(b.get('openings')):
        _keys(o, OPENING, _name(o, f'{path} opening'), out)
    for e in _list(b.get('engravings')):
        _keys(e, ENGRAVING, _name(e, f'{path} engraving'), out)
    for e in _list(b.get('edge_banding')):
        _keys(e, EDGE_BANDING, f'{path} edge_banding', out)
    for key, allowed in (('repeat', REPEAT), ('radial', RADIAL), ('mirror', MIRROR)):
        _keys(b.get(key), allowed, f'{path} {key}', out)
    for r in (b.get('rotate') if isinstance(b.get('rotate'), list) else [b.get('rotate')]):
        _keys(r, ROTATE, f'{path} rotate', out)
    for h in (b.get('living_hinge') if isinstance(b.get('living_hinge'), list) else [b.get('living_hinge')]):
        _keys(h, LIVING_HINGE, f'{path} living_hinge', out)


def _connection(c, path, out):
    _keys(c, CONNECTION, path, out)
    _numbers(c, NUMBERS['connection'], path, out)
    if isinstance(c, dict):
        _keys(c.get('fasteners'), FASTENERS, f'{path} fasteners', out)


def _motion(m, path, out):
    _keys(m, MOTION, path, out)
    if isinstance(m, dict):
        _keys(m.get('axle'), AXLE, f'{path} axle', out)
        _keys(m.get('link'), LINK, f'{path} link', out)


def _parts(container, label, out):
    for b in _list(container.get('boards')):
        _board(b, _name(b, f'{label}board'), out)
    for c in _list(container.get('connections')):
        _connection(c, _name(c, f'{label}connection'), out)
    for m in _list(container.get('motions')):
        _motion(m, _name(m, f'{label}motion'), out)


def check_fields(data):
    """Diagnostics for unknown, misspelled and invalid fields of a raw board-design/v1 design (see module doc)."""
    out = []
    if not isinstance(data, dict) or ('components' in data and 'boards' not in data):
        return out                      # native engine format: validated by the engine's own schema
    for k in data:
        if k in TOP:
            continue
        near = difflib.get_close_matches(k, sorted(TOP - set(data)), n=1, cutoff=0.8)
        if near:
            out.append(_diag('error', 'MISSPELLED_FIELD', f"The design has '{k}' where '{near[0]}' is expected; as "
                                                          f"written, '{k}' is ignored. Rename it to '{near[0]}'.", k))
        else:
            hint = difflib.get_close_matches(k, sorted(TOP), n=1, cutoff=0.75)
            out.append(_diag('warning', 'UNKNOWN_FIELD', f"The design has a top-level field '{k}' that the compiler "
                                                         f"does not read; it is ignored"
                                                         f"{f' - did you mean {hint[0]!r}?' if hint else ''}", k))
    _keys(data.get('product'), PRODUCT, 'product', out)
    _keys(data.get('material'), MATERIAL, 'material', out)
    _numbers(data.get('material'), NUMBERS['material'], 'material', out)
    _keys(data.get('sheet'), SHEET, 'sheet', out)
    _parts(data, '', out)
    for a in _list(data.get('assemblies')):
        _keys(a, ASSEMBLY, _name(a, 'assembly'), out)
        if isinstance(a, dict):
            _parts(a, f"{_name(a, 'assembly')} ", out)
    for i in _list(data.get('instances')):
        _keys(i, INSTANCE, _name(i, 'instance'), out)
    return out
