"""
Read-only projections of a design for renderers, AI agents and production.
"""
from . import geometry as G
from .booklet import build_booklet
from .cutpaths import generate_cut_paths, sheet_dxf, sheet_svg
from .model import Plate, edge_frame, tab_geometry
from .nesting import nest
from .validation import component_states, validate_design


def _r(v, n=3):
    return [_r(x, n) for x in v] if isinstance(v, (list, tuple)) else round(v, n)


def component_view(design, comp):
    """Everything an agent needs to reason about one component, incl. edge indices for joints."""
    pl = Plate(design, comp)
    x0, y0, x1, y1 = pl.bbox2d
    n = len(comp['outline'])
    edges = []
    for i in range(n):
        a, d, nrm, L = edge_frame(comp['outline'], i)
        b = comp['outline'][(i + 1) % n]
        edges.append({'index': i, 'start': _r(a), 'end': _r(b), 'length': _r(L),
                      'outward_normal_local': _r(nrm),
                      'world_start': _r(pl.frame.to_world(a)), 'world_end': _r(pl.frame.to_world(b))})
    tabs = []
    for t in comp.get('tabs', []):
        if t['edge'] < n:
            tg = tab_geometry(comp, t)
            tabs.append(dict(t, world_root=_r(pl.frame.to_world(tg['root'])),
                             world_insertion_direction=_r(pl.frame.dir_to_world([tg['normal'][0], tg['normal'][1], 0]))))
    lo, hi = pl.world_aabb()
    return {
        'id': comp['id'], 'name': comp.get('name'), 'group': comp.get('group'),
        'thickness': pl.t, 'color': comp.get('color'), 'grain_locked': bool(comp.get('grain_locked')),
        'outline': comp['outline'], 'cut_outline': _r([list(p) for p in pl.cut]),
        'features': comp.get('features', []), 'tabs': tabs, 'edges': edges,
        'placement': comp['placement'], 'matrix_world': _r(pl.frame.matrix4(), 6),
        'world_normal': _r(pl.frame.normal),
        'dimensions_2d': {'width': _r(x1 - x0), 'height': _r(y1 - y0),
                          'area': _r(abs(G.signed_area(pl.cut)) - sum(abs(G.signed_area(p))
                                                                     for _f, p in pl.feature_polys), 1)},
        'world_bounds': {'min': _r(lo), 'max': _r(hi)},
    }


def model3d(design, report=None):
    report = report or validate_design(design)
    states = component_states(design, report)
    comps = [dict(component_view(design, c), state=states[c['id']]) for c in design['components']]
    if comps:
        lo = [min(c['world_bounds']['min'][i] for c in comps) for i in range(3)]
        hi = [max(c['world_bounds']['max'][i] for c in comps) for i in range(3)]
    else:
        lo = hi = [0, 0, 0]
    return {
        'id': design['id'], 'name': design['name'], 'revision': design['revision'],
        'units': 'mm', 'up_axis': 'Y', 'euler_order': 'XYZ',
        'material': design['material'],
        'joinery': design.get('joinery', 'interlocking'),
        'bounds': {'min': _r(lo), 'max': _r(hi), 'center': _r([(lo[i] + hi[i]) / 2 for i in range(3)])},
        'components': comps,
        'joints': design['joints'],
        'validation': {'valid': report['valid'], 'complete': report['complete'], 'summary': report['summary']},
    }


def production_package(design, opts=None):
    """Validate -> nest -> cut paths. The booklet/exports are rendered from this package."""
    opts = dict(opts or {})
    report = validate_design(design)
    nest_opts = {k: opts[k] for k in ('preset', 'width', 'height', 'orientation', 'margin', 'spacing',
                                      'rotation') if k in opts}
    # The printed title strip (scale bar + sheet info) lives below the usable area
    nest_opts['title_block'] = max(float(opts.get('title_block', 14.0)), 12.0)
    nesting = nest(design, nest_opts)
    cut = generate_cut_paths(design, nesting, compensate_kerf=bool(opts.get('compensate_kerf', False)),
                             include_labels=opts.get('labels', True))
    blocking = [i for i in report['issues'] if i['severity'] == 'error'] + \
        [i for i in nesting['issues'] if i['severity'] == 'error'] + cut['issues'] + \
        [dict(u, severity='error') for u in nesting['unplaced']]
    return {'design': design, 'validation': report, 'nesting': nesting, 'cut': cut,
            'ready_for_production': not blocking, 'blocking_issues': blocking}


def export(pkg, fmt, sheet=None, paper='A4'):
    d, n, c = pkg['design'], pkg['nesting'], pkg['cut']
    if fmt == 'pdf':
        return build_booklet(d, pkg['validation'], n, c, paper), 'application/pdf', f"{d['id']}-booklet.pdf"
    if sheet is None or not (0 <= sheet < n['sheet_count']):
        raise ValueError(f"sheet must be between 1 and {n['sheet_count']}")
    if fmt == 'svg':
        return sheet_svg(d, n, c, sheet), 'image/svg+xml', f"{d['id']}-sheet{sheet + 1}.svg"
    if fmt == 'dxf':
        return sheet_dxf(d, n, c, sheet), 'application/dxf', f"{d['id']}-sheet{sheet + 1}.dxf"
    raise ValueError("format must be pdf, svg or dxf (PNG previews are rendered client-side from the SVG)")
