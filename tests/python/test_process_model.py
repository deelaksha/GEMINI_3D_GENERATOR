"""Phase 9 (F-20 / E-13 / G-12 / BUG-004): the manufacturing process model.

machine.process ('laser' | 'router' | 'saw') + tool_diameter: kerf by process, dog-bone relief at every inside corner
for a router (and only for a router), blocking issues when the bit is too big or a relief would break a web, part
spacing that grows with the bit, and the process stated in the cut list, job report / README and booklet. Without a
process every output stays byte-identical to the code before Phase 9.

The canvas compiler (canvas.py) does not yet pass the machine's process on to the design; `_produce` therefore does
exactly what the export route does - compile, then production_package - with `apply_process` (the hook canvas.py is
to call) in between. `test_compile_source_applies_process` turns green once canvas.py calls it.
"""
import copy
import hashlib
import json
import math
import re

import pytest

from conftest import make
from board_engine.canvas import compile_source
from board_engine.canvas_prompt import EXAMPLE, STRUCTURES_EXAMPLE
from board_engine.cutpaths import corner_reliefs
from board_engine.jobreport import job_lines, job_report
from board_engine.lightburn import sheet_lbrn2
from board_engine.manufacturing import apply_process, machine_process, process_limits
from board_engine.validation import TOL
from board_engine.views import export, production_package

ROUTER6 = {'process': 'router', 'tool_diameter': 6}
LASER_MACHINE = {'kerf': 0.15, 'sheet': {'width': 1300, 'height': 900}}


def _produce(src, machine=None, compensate=True):
    res = compile_source(json.dumps(src), run_production=False, machine=machine)
    design = apply_process(copy.deepcopy(res['design']), machine)
    return production_package(design, {'compensate_kerf': compensate})


def _paths(pkg, kind=None):
    return [p for sh in pkg['cut']['sheets'] for p in sh['paths'] if kind is None or p.get('feature_kind') == kind]


# ---------------------------------------------------------------------------
# No process: byte-identical to the code before Phase 9
# ---------------------------------------------------------------------------

# sha256[:16] of each output, captured on the unmodified code (commit b8ee35d). The PDF is left out: its bytes depend
# on PYTHONHASHSEED (set iteration order) even before Phase 9. Re-capture only for a deliberate engine change.
BASELINE = {
    'EXAMPLE/laser': {'blocking': '4f53cda18c2baa0c', 'compile': 'e89ce2526e99f19f', 'cutlist': 'c745df5d4825d6d1',
                      'dxf': 'ff4641acc74f6882', 'job': 'd0e6d33a2cbdadbe', 'lbrn': '1048e61d00662eb8',
                      'nest': 'b5f6858f83853d81', 'svg': 'b5d97301907e3b96'},
    'EXAMPLE/none': {'blocking': '4f53cda18c2baa0c', 'compile': 'd870e99164af67f1', 'cutlist': 'c745df5d4825d6d1',
                     'dxf': '6a845af3492d82ea', 'job': 'c2e7658bcd82f44d', 'lbrn': '18c87ccddc6f4679',
                     'nest': '960a2207a10725ba', 'svg': 'a0ba42c96d695915'},
    'STRUCTURES/laser': {'blocking': '4f53cda18c2baa0c', 'compile': '3483b54138b427e0', 'cutlist': '6c87415d674c8c71',
                         'dxf': '07e37dfaee42d67d', 'job': 'ba8aa4e9c98644c1', 'lbrn': '09929f2d78140436',
                         'nest': '6d360346610f07c0', 'svg': '09ea089016ed92ff'},
    'STRUCTURES/none': {'blocking': '4f53cda18c2baa0c', 'compile': '1c52b539ccc9aa8f', 'cutlist': '6c87415d674c8c71',
                        'dxf': 'c7cd7063dc87fd75', 'job': 'e780b87a23de5e04', 'lbrn': 'b038d88867c01f8f',
                        'nest': 'a7a04d804d05092c', 'svg': '469abc98b7b7e015'},
}


@pytest.mark.parametrize('key', sorted(BASELINE))
def test_no_process_outputs_byte_identical(key):
    name, mname = key.split('/')
    src = {'EXAMPLE': EXAMPLE, 'STRUCTURES': STRUCTURES_EXAMPLE}[name]
    m = {'none': None, 'laser': LASER_MACHINE}[mname]
    H = lambda s: hashlib.sha256(s.encode()).hexdigest()[:16]
    pkg = _produce(src, m)
    design, n, cut = pkg['design'], pkg['nesting'], pkg['cut']
    sheets = range(n['sheet_count'])
    full = compile_source(json.dumps(src), machine=m)
    got = {'svg': H(''.join(export(pkg, 'svg', i)[0] for i in sheets)),
           'dxf': H(''.join(export(pkg, 'dxf', i)[0] for i in sheets)),
           'lbrn': H(''.join(sheet_lbrn2(design, n, cut, i, m) for i in sheets)),
           'cutlist': H(json.dumps(pkg['cut_list'], sort_keys=True, default=str)),
           'job': H('\n'.join(job_lines(job_report(n, cut, m)))),
           'nest': H(json.dumps(n, sort_keys=True, default=str)),
           'blocking': H(json.dumps(sorted(i['code'] for i in pkg['blocking_issues']))),
           'compile': H(json.dumps({k: full.get(k) for k in ('layout', 'cut_list', 'job', 'summary')},
                                   sort_keys=True, default=str))}
    assert got == BASELINE[key]
    assert 'process' not in design and 'process' not in cut and 'process' not in pkg['cut_list']


def test_no_process_keeps_defaults():
    assert machine_process(None) is None and machine_process({'kerf': 0.2}) is None
    d = {'material': {'type': 'plywood', 'kerf': 3.2, 'thickness': 18}}
    assert apply_process(d, {'kerf': 0.2}) == {'material': {'type': 'plywood', 'kerf': 3.2, 'thickness': 18}}
    assert process_limits(d) == {'min_web': TOL['min_edge_margin'], 'min_inside_radius': 0.0, 'part_spacing_min': None}


# ---------------------------------------------------------------------------
# Router: dog-bone relief
# ---------------------------------------------------------------------------

def test_router_example_has_relief_at_every_slot_corner():
    pkg = _produce(EXAMPLE, ROUTER6)
    r = 3.0
    assert pkg['design']['material']['kerf'] == 6.0                 # router kerf = bit diameter
    assert pkg['cut']['process'] == {'process': 'router', 'tool_diameter': 6.0, 'relief_radius': r,
                                     'reliefs': pkg['cut']['process']['reliefs']}
    slots = _paths(pkg, 'slot')
    assert len(slots) == 13
    for p in slots:
        rel = p['reliefs']
        assert len(rel) == 4, p['id']                                 # every corner of the rectangular slot
        assert len({tuple(x['corner']) for x in rel}) == 4
        for x in rel:
            assert x['radius'] >= r - 1e-9
            assert math.dist(x['corner'], x['center']) == pytest.approx(r, abs=1e-3)   # the circle meets the corner
            # the tool-centre path plunges to the relief centre, so the bit's edge reaches the corner
            assert any(math.dist(q, x['center']) < 1e-3 for q in p['points'])
    # tab roots (inside corners of the outlines) get reliefs too
    outers = {p['part']: p for p in _paths(pkg) if p['type'] == 'outer'}
    assert len(outers['SHELF']['reliefs']) == 8 and len(outers['MODESTY']['reliefs']) == 10
    assert not pkg['blocking_issues']


def test_router_relief_is_a_true_arc_in_every_output():
    """Uncompensated (part geometry) export: each slot corner is an arc of radius >= the bit radius in the SVG, the DXF
    (bulge) and the LightBurn file; compensated export: the plunge vertices reach the same centres everywhere."""
    raw = _produce(EXAMPLE, ROUTER6, compensate=False)
    svg = export(raw, 'svg', 0)[0]
    slot_d = re.search(r'id="TOP/slot-LEG-L-TOP-t1"[^>]* d="([^"]+)"', svg).group(1)
    radii = [float(a) for a in re.findall(r'A([\d.]+),', slot_d)]
    assert len(radii) >= 4 and min(radii) >= 3.0 - 1e-3
    dxf = export(raw, 'dxf', 0)[0]
    assert dxf.count('\n42\n') >= 4 * 13                              # bulged (arc) vertices: >= one per slot corner
    lb = sheet_lbrn2(raw['design'], raw['nesting'], raw['cut'], 0)
    plain = _produce(EXAMPLE, {'process': 'saw'}, compensate=False)
    assert lb.count('c0x1c1x1') > sheet_lbrn2(plain['design'], plain['nesting'], plain['cut'], 0).count('c0x1c1x1')
    comp = _produce(EXAMPLE, ROUTER6)
    centre = comp['cut']['sheets'][0]['paths']
    slot = next(p for p in centre if p['id'] == 'TOP/slot-LEG-L-TOP-t1')
    cx, cy = slot['reliefs'][0]['center']
    fmt = lambda v: f'{v:.3f}'.rstrip('0').rstrip('.')
    assert f'{fmt(cx)},{fmt(cy)}' in export(comp, 'svg', 0)[0]
    pdf = export(comp, 'pdf')[0]
    assert pdf.startswith(b'%PDF')


def test_corner_reliefs_only_where_the_bit_cannot_reach():
    square = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert len(corner_reliefs(square, True, 1.0)) == 4               # a square hole: every corner
    assert corner_reliefs(square, False, 1.0) == []                  # a square part: convex corners only
    notch = [[0, 0], [30, 0], [30, 10], [20, 10], [20, 5], [10, 5], [10, 10], [0, 10]]   # a finger notch
    assert sorted(i for i, *_ in corner_reliefs(notch, False, 1.0)) == [4, 5]
    i, q, c, _a, _b = corner_reliefs(notch, False, 1.0)[0]
    assert math.dist(q, c) == pytest.approx(1.0) and c[1] > q[1]     # on the bisector, in the removed notch
    octagon = [[math.cos(k * math.pi / 32), math.sin(k * math.pi / 32)] for k in range(64)]
    assert corner_reliefs([[10 * x, 10 * y] for x, y in octagon], True, 1.0) == []   # a fine curve is not a corner


def test_laser_and_saw_get_no_relief():
    for m in ({'process': 'laser'}, {'process': 'saw'}, None):
        pkg = _produce(STRUCTURES_EXAMPLE, m)
        assert not any('reliefs' in p for p in _paths(pkg)), m
        assert not any(p.get('arcs') for p in _paths(pkg, 'slot'))
    assert _produce(STRUCTURES_EXAMPLE, {'process': 'saw'})['cut']['kerf_compensation'] == 3.2


def test_router_cross_lap_and_finger_notches_relieved():
    pkg = _produce(STRUCTURES_EXAMPLE, {'process': 'router', 'tool_diameter': 3.175})
    outers = {p['part']: p for p in _paths(pkg) if p['type'] == 'outer'}
    assert outers['FRONT']['reliefs'] and outers['DIV-X']['reliefs']   # finger notches; cross_lap notch
    assert all(x['radius'] >= 3.175 / 2 - 1e-9 for p in outers.values() for x in p.get('reliefs', []))
    assert not pkg['blocking_issues']


def test_tool_too_large_for_slot_blocks():
    pkg = _produce(STRUCTURES_EXAMPLE, {'process': 'router', 'tool_diameter': 8})   # 6.1 mm slots and notches
    codes = {i['code'] for i in pkg['blocking_issues']}
    assert 'TOOL_TOO_LARGE' in codes
    assert not pkg['ready_for_production']


def _plate_with_slot(web):
    """A 100 x 60 plate with a 20 x 8 slot `web` mm from its bottom edge (own material: no joints needed)."""
    d = make({'id': 'P', 'outline': [[0, 0], [100, 0], [100, 60], [0, 60]],
              'features': [{'id': 's', 'kind': 'slot', 'shape': 'rect', 'center': [50, web + 4], 'width': 20,
                            'height': 8, 'angle': 0}]})
    d['material'].update(type='plywood', thickness=18.0, kerf=3.2)
    return d


@pytest.mark.parametrize('web, broken', [(20.0, False), (2.5, True)])
def test_relief_never_breaks_a_thin_web(web, broken):
    d = apply_process(_plate_with_slot(web), ROUTER6)
    pkg = production_package(d, {'compensate_kerf': True})
    codes = [i['code'] for i in pkg['cut']['issues']]
    assert ('RELIEF_BREAKS_WEB' in codes) is broken
    laser = apply_process(_plate_with_slot(web), {'process': 'laser'})
    assert 'RELIEF_BREAKS_WEB' not in [i['code'] for i in production_package(laser, {'compensate_kerf': True})['cut']['issues']]


# ---------------------------------------------------------------------------
# Kerf and process-dependent constraints
# ---------------------------------------------------------------------------

def test_laser_without_explicit_kerf_uses_laser_kerf():
    pkg = _produce(EXAMPLE, {'process': 'laser'})
    assert pkg['cut']['kerf_compensation'] <= 0.3
    assert pkg['design']['material']['kerf'] == 0.15
    # a kerf the user states wins: on the machine, or on the material
    assert _produce(EXAMPLE, dict(LASER_MACHINE, kerf=0.25, process='laser'))['cut']['kerf_compensation'] == 0.25
    src = copy.deepcopy(EXAMPLE)
    src['material']['kerf'] = 0.1
    assert _produce(src, {'process': 'laser'})['cut']['kerf_compensation'] == 0.1
    assert _produce(EXAMPLE)['cut']['kerf_compensation'] == 3.2        # no process: catalogue kerf, as before


def test_router_nesting_spacing_grows_with_tool():
    spacing = lambda m: _produce(EXAMPLE, m)['nesting']['sheet']['spacing']
    base = spacing(None)
    assert spacing({'process': 'laser'}) == base == spacing({'process': 'saw'})
    s3, s12 = spacing({'process': 'router', 'tool_diameter': 3}), spacing({'process': 'router', 'tool_diameter': 12})
    assert s3 >= 3 and s12 >= 12 + 1 and s12 > s3


def test_process_limits_scale_with_tool_and_thickness():
    d = lambda p, t=18: {'material': {'thickness': t}, **({'process': machine_process(p)} if p else {})}
    assert process_limits(d({'process': 'laser'}))['min_web'] == TOL['min_edge_margin']
    r = process_limits(d(ROUTER6))
    assert r['min_inside_radius'] == 3.0 and r['part_spacing_min'] > 6.0 and r['min_web'] >= 6.0
    assert process_limits(d({'process': 'saw'}, 18))['min_web'] > process_limits(d({'process': 'saw'}, 6))['min_web']


def test_machine_process_validation():
    with pytest.raises(ValueError):
        machine_process({'process': 'plasma'})
    with pytest.raises(ValueError):
        machine_process({'process': 'router', 'tool_diameter': 30})
    assert machine_process({'process': 'router'}) == {'process': 'router', 'tool_diameter': 6.0}
    assert machine_process({'process': 'router', 'kerf': 3.175}) == {'process': 'router', 'tool_diameter': 3.175}
    assert machine_process({'process': 'laser', 'tool_diameter': 2}) == {'process': 'laser'}


def test_routes_machine_validator():
    from board_api.routes import _machine
    from board_engine.model import SchemaError
    sheet = {'width': 1300, 'height': 900}
    assert _machine({'machine': {'kerf': 0.2, 'sheet': sheet}}) == {'kerf': 0.2, 'sheet': {'width': 1300.0, 'height': 900.0}}
    assert _machine({'machine': {'coloring': True}}) == {'coloring': True}
    assert _machine({'machine': {'process': 'laser', 'sheet': sheet}})['kerf'] == 0.15
    m = _machine({'machine': {'process': 'router', 'tool_diameter': 6, 'sheet': sheet}})
    assert m['kerf'] == 6.0 and m['process'] == 'router' and m['tool_diameter'] == 6.0
    assert _machine({'machine': {'process': 'router', 'tool_diameter': 3}}) == {'process': 'router', 'tool_diameter': 3.0}
    for bad in ({'process': 'plasma'}, {'process': 'router', 'tool_diameter': 0.1}, {'tool_diameter': 6},
                {'process': 'laser', 'kerf': 6, 'sheet': sheet}):
        with pytest.raises(SchemaError):
            _machine({'machine': bad})


# ---------------------------------------------------------------------------
# Cut list, job report (README) and booklet state the process
# ---------------------------------------------------------------------------

def test_outputs_state_process_and_tool():
    pkg = _produce(EXAMPLE, ROUTER6)
    cl = pkg['cut_list']
    assert cl['process']['process'] == 'router' and cl['process']['tool_diameter'] == 6.0
    assert cl['process']['label'] == 'CNC router, 6 mm bit' and cl['process']['kerf'] == 6.0
    assert {line['process'] for line in cl['lines']} == {'router'}
    lines = job_lines(job_report(pkg['nesting'], pkg['cut'], ROUTER6))
    assert lines[0].startswith('Process    : router, 6 mm bit, dog-bone relief (r 3 mm) at ')
    laser = _produce(EXAMPLE, {'process': 'laser'})
    assert {line['process'] for line in laser['cut_list']['lines']} == {'laser'}
    assert job_lines(job_report(laser['nesting'], laser['cut']))[0] == 'Process    : laser, no inside-corner relief'


def test_compile_source_applies_process():
    res = compile_source(json.dumps(EXAMPLE), machine=ROUTER6)
    assert res['layout']['cut']['process']['reliefs'] > 0
