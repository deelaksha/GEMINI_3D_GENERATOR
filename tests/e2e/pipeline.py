"""Run one product through the whole pipeline and cross-check every representation.

compile (board-design/v1 or native) -> validation -> support analysis -> production package (nesting, kerf-compensated
cut paths, manufacturing, cut list) -> exports (PDF, SVG, DXF) -> consistency checks between the v1 source, the native
design, the 3D model, the nesting, the cut paths, the SVG/DXF files, the cut list and the reported waste.
"""
import json
import math
import re
import time
import traceback

from board_engine import geometry as G
from board_engine.canvas import compile_source, pretty_json
from board_engine.cutpaths import generate_cut_paths
from board_engine.model import Plate, build_plates
from board_engine.nesting import part_area
from board_engine.validation import validate_design
from board_engine.views import export, model3d, production_package

try:                                   # added by the support-analysis change; absent on the baseline
    from board_engine.support import support_report
except ImportError:                    # pragma: no cover
    support_report = None

AREA_TOL = 0.05      # mm^2: model3d rounds to 3 decimals, sheets to 4
LEN_TOL = 0.02       # mm


def _area_tol(poly):
    """Coordinates are rounded to 3 decimals for the 3D view: allow 1e-3 mm x perimeter."""
    return max(AREA_TOL, 1e-3 * sum(math.dist(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))))


def _codes(items, sev=None):
    return sorted({i['code'] for i in items if sev is None or i.get('severity') == sev})


def _native_design(name):
    if name == 'boat':
        from board_engine.examples.boat import build_design, load_seed
        try:
            return load_seed('boat')
        except (OSError, ValueError):
            return build_design('boat')[0]
    raise ValueError(name)


def consistency(design, source, pkg):
    """Compare the five representations. Returns a list of mismatch strings (empty = consistent)."""
    bad = []
    plates = build_plates(design)
    ids = [c['id'] for c in design['components']]
    # 1. v1 source boxes -> native components (unrotated, unprofiled boards must fill their box exactly)
    if source and isinstance(source.get('boards'), list):
        src_ids = [b['id'] for b in source['boards']]
        if sorted(src_ids) != sorted(ids):
            bad.append(f'source/native component sets differ: {sorted(set(src_ids) ^ set(ids))}')
        for b in source['boards']:
            pl = plates.get(b['id'])
            if pl is None or b.get('rotate'):
                continue
            outline_plate = Plate(design, dict(pl.comp, tabs=[]))
            lo, hi = outline_plate.world_aabb()
            # finger joints add fingers that reach into the partner's notches: allow up to the partner thickness
            slack = max([plates[j['b'] if j['a'] == b['id'] else j['a']].t for j in design['joints']
                         if j['type'] == 'finger' and b['id'] in (j['a'], j['b'])], default=0.0)
            want_lo, want_hi = b['position'], [b['position'][i] + b['size'][i] for i in range(3)]
            for i in range(3):
                d_lo, d_hi = want_lo[i] - lo[i], hi[i] - want_hi[i]      # > 0: beyond the box
                if b.get('profile') is None and not slack and (abs(d_lo) > LEN_TOL or abs(d_hi) > LEN_TOL):
                    bad.append(f"{b['id']}: 3D extent {[round(v, 3) for v in lo]}..{[round(v, 3) for v in hi]} != source box "
                               f"{want_lo}..{want_hi}")
                    break
                if d_lo > slack + LEN_TOL or d_hi > slack + LEN_TOL:
                    bad.append(f"{b['id']}: leaves its source box on axis {'xyz'[i]}")
                    break
            if abs(pl.t - float(b.get('thickness', source['material']['thickness']))) > 1e-9:
                bad.append(f"{b['id']}: thickness {pl.t} != source")
    # 2. native -> 3D model
    m3 = {c['id']: c for c in model3d(design, pkg['validation'])['components']}
    if sorted(m3) != sorted(ids):
        bad.append('3D component set differs from the design')
    for cid, c in m3.items():
        pl = plates[cid]
        if abs(abs(G.signed_area(c['cut_outline'])) - abs(G.signed_area(pl.cut))) > _area_tol(pl.cut):
            bad.append(f'{cid}: 3D outline area differs')
        if len(c['features']) != len(pl.features) or abs(c['thickness'] - pl.t) > 1e-9:
            bad.append(f'{cid}: 3D features/thickness differ')
        wl, wh = pl.world_aabb()
        if any(abs(c['world_bounds']['min'][i] - wl[i]) > 0.01 or abs(c['world_bounds']['max'][i] - wh[i]) > 0.01 for i in range(3)):
            bad.append(f'{cid}: 3D world bounds differ from the design placement')
    # 3. nesting: every part exactly once, inside the usable area, unrotated area preserved
    n = pkg['nesting']
    placed = [p['id'] for p in n['placements']]
    unplaced = [u['id'] for u in n['unplaced']]
    if sorted(placed + unplaced) != sorted(ids) or len(set(placed)) != len(placed):
        bad.append(f'nesting: parts missing or duplicated (placed {len(placed)}, unplaced {len(unplaced)}, parts {len(ids)})')
    ux0, uy0, ux1, uy1 = n['sheet']['usable']
    for p in n['placements']:
        x0, y0, x1, y1 = p['bbox']
        if x0 < ux0 - 1e-6 or y0 < uy0 - 1e-6 or x1 > ux1 + 1e-6 or y1 > uy1 + 1e-6:
            bad.append(f"nesting: {p['id']} leaves the usable sheet area")
        if abs(p['area'] - part_area(plates[p['id']])) > AREA_TOL:
            bad.append(f"nesting: {p['id']} area differs")
    # 4. waste arithmetic, recomputed independently
    st = n['stats']
    sheet_area = n['sheet']['width'] * n['sheet']['height']
    used = sum(part_area(plates[p]) for p in placed)
    total = n['sheet_count'] * sheet_area
    if abs(st['total_material_area'] - total) > 0.5 or abs(st['used_area'] - used) > 0.5 or \
            abs(st['waste_area'] - (total - used)) > 1.0 or (total and abs(st['efficiency_percent'] - 100 * used / total) > 0.01):
        bad.append(f'waste figures inconsistent: reported {st} vs total {total:.1f} used {used:.1f}')
    # 5. cut paths (uncompensated) == design profiles; compensated outer paths grow by ~kerf/2 x perimeter
    raw = generate_cut_paths(design, n, compensate_kerf=False, include_labels=False)
    outers = {p['part']: p for s in raw['sheets'] for p in s['paths'] if p['type'] == 'outer'}
    inners = {}
    for s in raw['sheets']:
        for p in s['paths']:
            if p['type'] == 'inner':
                inners[p['part']] = inners.get(p['part'], 0) + 1
    for pid in placed:
        pl = plates[pid]
        if abs(abs(G.signed_area(outers[pid]['points'])) - abs(G.signed_area(pl.cut))) > AREA_TOL:
            bad.append(f'cut path: {pid} outer area differs from the design')
        if inners.get(pid, 0) != len(pl.features):
            bad.append(f'cut path: {pid} has {inners.get(pid, 0)} inner paths for {len(pl.features)} cut-outs')
    half = pkg['cut']['kerf_compensation'] / 2
    for s in pkg['cut']['sheets']:
        for p in s['paths']:
            if p['type'] == 'outer' and half:
                pl = plates[p['part']]
                per = sum(math.dist(pl.cut[i], pl.cut[(i + 1) % len(pl.cut)]) for i in range(len(pl.cut)))
                grow = abs(G.signed_area(p['points'])) - abs(G.signed_area(pl.cut))
                if grow < 0 or grow > half * per + 4 * half * half * len(pl.cut) + 1:
                    bad.append(f"kerf: {p['part']} compensated area change {grow:.1f} mm² outside 0..{half * per:.1f}")
            if p.get('shape') == 'circle' and p['radius'] <= 0:
                bad.append(f"cut path: {p['id']} has a non-positive radius {p['radius']}")
    # 6. cut list
    cl = pkg['cut_list']
    if sorted(b['id'] for b in cl['boards']) != sorted(ids) or sum(l['quantity'] for l in cl['lines']) != len(ids):
        bad.append('cut list: boards differ from the design')
    for b in cl['boards']:
        if abs(b['thickness'] - plates[b['id']].t) > 1e-9:
            bad.append(f"cut list: {b['id']} thickness differs")
    return bad


def exports(design, pkg):
    """Generate every export (always as a forced draft so the files can be inspected) and sanity-check them."""
    out = {'gated': not pkg['ready_for_production']}
    try:
        pdf, _m, _n = export(pkg, 'pdf')
        pages = pdf.count(b'/Type /Page') - pdf.count(b'/Type /Pages')
        out['pdf'] = {'bytes': len(pdf), 'pages': pages, 'ok': pdf.startswith(b'%PDF') and pages >= pkg['nesting']['sheet_count'] + 1}
        svg_outer = dxf_outer = 0
        for i in range(pkg['nesting']['sheet_count']):
            svg, _m, _n = export(pkg, 'svg', i)
            dxf, _m, _n = export(pkg, 'dxf', i)
            svg_outer += len(re.findall(r'id="[^"]*/outer"', svg))
            dxf_outer += dxf.count('POLYLINE\n8\nCUT_OUTER\n')
        out['svg_outer_paths'], out['dxf_outer_polylines'] = svg_outer, dxf_outer
        n = len(pkg['nesting']['placements'])
        out['ok'] = out['pdf']['ok'] and svg_outer == n and dxf_outer == n
    except Exception as e:  # noqa: BLE001 — an export failure is a test result, not a harness crash
        out['ok'] = False
        out['error'] = f'{type(e).__name__}: {e}'
    return out


def run_case(case):
    rec = {'test_id': case['id'], 'title': case['title'], 'categories': case['categories'], 'prompt': case['prompt'],
           'source_kind': case['source'], 'expect': case['expect'], 'notes': case.get('notes', '')}
    t0 = time.time()
    try:
        if 'native_example' in case['design']:
            design = _native_design(case['design']['native_example'])
            rec['ai_response'] = None
            src_obj = None
            diags, compiled = [], True
        else:
            src_obj = case['design']
            text = pretty_json(src_obj)
            rec['ai_response'] = text
            r = compile_source(text, design_id=case['id'].lower(), run_production=False)
            diags, compiled, design = r['diagnostics'], r['ok'], r['design']
        rec['compiled'] = compiled
        rec['diagnostics'] = {'errors': _codes(diags, 'error'), 'warnings': _codes(diags, 'warning'),
                              'info': _codes(diags, 'info'),
                              'first_errors': [d['message'][:300] for d in diags if d['severity'] == 'error'][:5]}
        if design is None:
            rec['components'] = rec['joints'] = 0
            rec['stage_reached'] = 'compile'
            return rec
        rec['design_json'] = design
        rec['components'] = len(design['components'])
        rec['joints'] = len(design['joints'])
        rec['joined'] = sum(1 for j in design['joints'] if j.get('status') == 'joined')
        report = validate_design(design)
        rec['geometry_validation'] = {'valid': report['valid'], 'complete': report['complete'],
                                      'errors': _codes(report['issues'], 'error'), 'warnings': _codes(report['issues'], 'warning')}
        rec['collisions'] = sum(1 for i in report['issues'] if i['code'] == 'COLLISION')
        if support_report:
            s = support_report(design)
            rec['support'] = {k: s[k] for k in ('mounting', 'stable', 'stability_margin', 'centre_of_mass', 'status_counts')}
            rec['support']['issues'] = _codes(s['issues'])
            rec['support']['by_status'] = {st: sorted(c for c, v in s['components'].items() if v['status'] == st)
                                           for st in {v['status'] for v in s['components'].values()}}
        else:
            rec['support'] = 'not available (baseline: no support analysis in the engine)'
        pkg = production_package(design, {'compensate_kerf': True})
        n = pkg['nesting']
        rec['cutting'] = {'sheets': n['sheet_count'], 'placed': len(n['placements']), 'unplaced': [u['id'] for u in n['unplaced']],
                          'efficiency_percent': n['stats']['efficiency_percent'], 'waste_percent': n['stats']['waste_percent'],
                          'kerf': pkg['cut']['kerf_compensation'], 'cut_issues': _codes(pkg['cut']['issues'])}
        rec['ready_for_production'] = pkg['ready_for_production']
        rec['blocking'] = _codes(pkg['blocking_issues'])
        mism = consistency(design, src_obj, pkg)
        rec['consistency_2d_3d'] = {'ok': not mism, 'mismatches': mism[:10]}
        rec['exports'] = exports(design, pkg)
        rec['stage_reached'] = 'exports'
    except Exception as e:  # noqa: BLE001
        rec['harness_error'] = f'{type(e).__name__}: {e}'
        rec['traceback'] = traceback.format_exc()[-2000:]
    finally:
        rec['duration_s'] = round(time.time() - t0, 3)
    return rec


def verdict(rec):
    """Compare a record with the case expectation. -> list of failed expectations (empty = pass)."""
    e, fails = rec['expect'], []
    if 'harness_error' in rec:
        return [rec['harness_error']]
    if e.get('compiles') is not None and rec.get('compiled') != e['compiles']:
        fails.append(f"compiles={rec.get('compiled')} expected {e['compiles']}")
    if e.get('error_codes') and not set(e['error_codes']) <= set(rec.get('diagnostics', {}).get('errors', [])):
        fails.append(f"expected error codes {e['error_codes']}, got {rec.get('diagnostics', {}).get('errors')}")
    if not rec.get('compiled'):
        return fails
    if e.get('components') is not None and rec['components'] != e['components']:
        fails.append(f"components={rec['components']} expected {e['components']}")
    if e.get('ready') is not None and rec.get('ready_for_production') != e['ready']:
        fails.append(f"ready_for_production={rec.get('ready_for_production')} expected {e['ready']} (blocking {rec.get('blocking')})")
    if not rec['consistency_2d_3d']['ok']:
        fails.append('2D/3D consistency: ' + '; '.join(rec['consistency_2d_3d']['mismatches'][:3]))
    if not rec['exports'].get('ok'):
        fails.append(f"exports: {rec['exports']}")
    sup = rec.get('support')
    for key, status in (('resting', 'resting'), ('unsupported', 'unsupported')):
        if e.get(key):
            if not isinstance(sup, dict):
                fails.append(f'{key}: support analysis not available')
            elif not set(e[key]) <= set(sup['by_status'].get(status, [])):
                fails.append(f"{key}: expected {e[key]} to be {status}, got {sup['by_status']}")
    if e.get('tips'):
        if not isinstance(sup, dict):
            fails.append('tips: support analysis not available')
        elif sup['stable'] is not False:
            fails.append(f"expected the product to tip over; stable={sup['stable']}")
    return fails


def summary_row(rec):
    return {'test_id': rec['test_id'], 'compiled': rec.get('compiled'), 'components': rec.get('components'),
            'joints': rec.get('joints'), 'ready': rec.get('ready_for_production'),
            'consistent': (rec.get('consistency_2d_3d') or {}).get('ok'), 'duration_s': rec.get('duration_s')}


def dumps(obj):
    return json.dumps(obj, indent=1, default=str)
