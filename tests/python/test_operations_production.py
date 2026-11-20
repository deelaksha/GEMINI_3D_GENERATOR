"""Validated operations, nesting, cutting paths and production exports."""
import copy
import math
import re
import xml.etree.ElementTree as ET

import pytest

from board_engine.cutpaths import generate_cut_paths, sheet_dxf, sheet_svg
from board_engine.joining import join
from board_engine.model import find_component
from board_engine.nesting import NestingError, nest
from board_engine.operations import OperationRejected, apply_batch, apply_operation
from board_engine.views import export, production_package

from conftest import GOOD_SLOT, TAB_JOINT, base_plate, make, wall


@pytest.fixture
def joined(pair):
    return join(pair, TAB_JOINT, auto_repair=True)['design']


def test_add_component_rejects_invalid_and_duplicate(pair):
    with pytest.raises(OperationRejected) as e:
        apply_operation(pair, {'op': 'add_component',
                               'component': {'id': 'BAD', 'outline': [[0, 0], [10, 10], [10, 0], [0, 10]]}})
    assert e.value.issues[0]['code'] == 'OUTLINE_SELF_INTERSECTION'
    dup = copy.deepcopy(find_component(pair, 'WALL'))
    dup['id'] = 'WALL2'
    with pytest.raises(OperationRejected) as e:
        apply_operation(pair, {'op': 'add_component', 'component': dup})
    assert e.value.issues[0]['code'] == 'DUPLICATE_COMPONENT'
    with pytest.raises(OperationRejected):
        apply_operation(pair, {'op': 'add_component', 'component': dict(dup, id='WALL')})


def test_edit_that_breaks_joint_is_rejected_or_detached(joined):
    op = {'op': 'translate', 'id': 'WALL', 'delta': [0, 5, 0]}
    with pytest.raises(OperationRejected) as e:
        apply_operation(copy.deepcopy(joined), op)
    assert e.value.status == 'would_break_joints' and e.value.extra['broken_joints'] == ['J1']
    d = copy.deepcopy(joined)
    res = apply_operation(d, dict(op, detach_broken_joints=True))
    assert res['detached_joints'] == ['J1'] and d['joints'][0]['status'] == 'detached'


def test_moving_along_the_slot_axis_is_a_valid_edit_only_if_slot_follows(joined):
    with pytest.raises(OperationRejected):
        apply_operation(copy.deepcopy(joined), {'op': 'translate', 'id': 'WALL', 'delta': [3, 0, 0]})


def test_delete_cascade_removes_generated_slots_only(joined):
    keep = {'id': 'hole', 'kind': 'hole', 'shape': 'circle', 'center': [30, 10], 'diameter': 4}
    apply_operation(joined, {'op': 'add_feature', 'id': 'BASE', 'feature': keep})
    with pytest.raises(OperationRejected):
        apply_operation(copy.deepcopy(joined), {'op': 'delete_component', 'id': 'WALL'})
    res = apply_operation(joined, {'op': 'delete_component', 'id': 'WALL', 'cascade': True})
    assert res['removed_joints'] == ['J1']
    assert [f['id'] for f in find_component(joined, 'BASE')['features']] == ['hole']


def test_remove_slot_in_use_is_blocked(joined):
    with pytest.raises(OperationRejected) as e:
        apply_operation(joined, {'op': 'remove_feature', 'id': 'BASE', 'feature_id': 'slot-J1'})
    assert e.value.status == 'has_dependents'


def test_batch_is_atomic(pair):
    snap = copy.deepcopy(pair)
    with pytest.raises(OperationRejected) as e:
        apply_batch(pair, [{'op': 'join', 'joint': TAB_JOINT, 'auto_repair': True},
                           {'op': 'add_component', 'component': {'id': 'X', 'outline': [[0, 0], [1, 0], [1, 1e-9]]}}])
    assert e.value.extra['failed_index'] == 1
    assert pair == snap
    work, results = apply_batch(pair, [{'op': 'join', 'joint': TAB_JOINT, 'auto_repair': True}])
    assert work['joints'][0]['status'] == 'joined' and pair == snap


def test_material_change_rechecks_joints(joined):
    with pytest.raises(OperationRejected):
        apply_operation(copy.deepcopy(joined), {'op': 'set_material', 'material': {'thickness': 6.0}})


# --- nesting ------------------------------------------------------------------------------

def test_nesting_boat_on_a4_reports_oversize_parts(boat):
    n = nest(boat, {'preset': 'A4', 'margin': 10, 'spacing': 5})
    assert {u['id'] for u in n['unplaced']} == {'HULL-BOTTOM', 'DECK'}
    assert all(u['code'] == 'PART_EXCEEDS_SHEET' for u in n['unplaced'])


@pytest.mark.parametrize('opts', [{'preset': 'A3'}, {'preset': 'board-600x400'},
                                  {'width': 500, 'height': 350, 'spacing': 8, 'margin': 15}])
def test_nesting_places_everything_without_overlap(boat, opts):
    n = nest(boat, dict(opts, title_block=12))
    assert n['unplaced'] == [] and n['issues'] == []
    assert len(n['placements']) == 14 == len({p['id'] for p in n['placements']})
    ux0, uy0, ux1, uy1 = n['sheet']['usable']
    for p in n['placements']:
        x0, y0, x1, y1 = p['bbox']
        assert ux0 - 1e-6 <= x0 and y0 >= uy0 - 1e-6 and x1 <= ux1 + 1e-6 and y1 <= uy1 + 1e-6
    st = n['stats']
    assert st['total_material_area'] == pytest.approx(n['sheet_count'] * n['sheet']['width'] * n['sheet']['height'])
    assert st['efficiency_percent'] + st['waste_percent'] == pytest.approx(100, abs=0.02)


def test_grain_locked_parts_are_not_rotated(boat):
    d = copy.deepcopy(boat)
    for c in d['components']:
        c['grain_locked'] = True
    n = nest(d, {'preset': 'board-600x400', 'rotation': 'orthogonal'})
    assert all(p['rotation'] == 0 for p in n['placements'])
    tall = make({'id': 'TALL', 'grain_locked': True, 'outline': [[0, 0], [20, 0], [20, 380], [0, 380]]})
    n = nest(tall, {'preset': 'A3', 'margin': 10})  # 380 tall only fits if rotated
    assert n['unplaced'] and 'rotation not permitted' in n['unplaced'][0]['message']


def test_nesting_input_validation(boat):
    with pytest.raises(NestingError):
        nest(boat, {'preset': 'A0-giant'})
    with pytest.raises(NestingError):
        nest(boat, {'width': 100, 'height': 100, 'margin': 60})


# --- cutting paths & exports ---------------------------------------------------------------

def test_cut_paths_are_closed_unique_and_kerf_compensated(boat):
    n = nest(boat, {'preset': 'A3', 'title_block': 12})
    plain = generate_cut_paths(boat, n)
    comp = generate_cut_paths(boat, n, compensate_kerf=True)
    assert plain['issues'] == [] and comp['issues'] == []
    total_features = sum(len(c['features']) for c in boat['components'])
    assert plain['counts'] == {'outer': 14, 'inner': total_features}
    assert all(p['closed'] for s in comp['sheets'] for p in s['paths'])
    # inner paths are cut before their part's outer path
    for s in comp['sheets']:
        last_outer = {}
        for p in s['paths']:
            if p['type'] == 'outer':
                last_outer[p['part']] = p['order']
        assert all(p['order'] < last_outer[p['part']] for p in s['paths'] if p['type'] == 'inner')
    # circles shrink by kerf/2, a rectangular slot shrinks by kerf in both directions
    kerf = boat['material']['kerf']
    pc = {p['id']: p for s in plain['sheets'] for p in s['paths']}
    cc = {p['id']: p for s in comp['sheets'] for p in s['paths']}
    hole = 'BULKHEAD-1/lightening'
    assert cc[hole]['radius'] == pytest.approx(pc[hole]['radius'] - kerf / 2)
    slot = next(k for k, p in pc.items() if p.get('feature_kind') == 'slot')
    side = lambda pts: math.dist(pts[0], pts[1])
    assert side(cc[slot]['points']) == pytest.approx(side(pc[slot]['points']) - kerf, abs=1e-3)


def test_duplicate_cut_geometry_is_dropped():
    s = dict(GOOD_SLOT)
    d = make(base_plate(features=[s, dict(s, id='s1-copy')]))
    n = nest(d, {'preset': 'A4'})
    cut = generate_cut_paths(d, n)
    assert [i['code'] for i in cut['issues']].count('DUPLICATE_CUT_PATH') == 1
    assert cut['counts']['inner'] == 1


def test_svg_dxf_pdf_exports(boat):
    pkg = production_package(boat, {'preset': 'A3', 'compensate_kerf': True})
    assert pkg['ready_for_production'], pkg['blocking_issues']
    svg, mime, _ = export(pkg, 'svg', 0)
    root = ET.fromstring(svg.split('?>', 1)[1])
    assert root.get('width') == '420mm' and root.get('viewBox') == '0 0 420 297'
    assert {g.get('id') for g in root if g.tag.endswith('g')} >= {'CUT_OUTER', 'CUT_INNER', 'ENGRAVE_LABELS'}
    dxf, _, _ = export(pkg, 'dxf', 0)
    assert dxf.startswith('0\nSECTION') and dxf.rstrip().endswith('EOF')
    assert dxf.count('\nPOLYLINE\n') + dxf.count('\nCIRCLE\n') == len(pkg['cut']['sheets'][0]['paths'])
    pdf, mime, _ = export(pkg, 'pdf', paper='A4')
    assert pdf.startswith(b'%PDF-1.4') and pdf.rstrip().endswith(b'%%EOF')
    sizes = re.findall(rb'/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]', pdf)
    pages = len(sizes)
    assert pages == 1 + pkg['nesting']['sheet_count'] + 14 + 1
    # cutting template pages are exactly the sheet size in points (1:1)
    assert sizes[1] == (b'1190.55', b'841.89')
    with pytest.raises(ValueError):
        export(pkg, 'svg', 99)


def test_production_package_blocks_invalid_designs(pair):
    pkg = production_package(pair, {'preset': 'A4'})
    assert not pkg['ready_for_production']
    assert any(i['code'] == 'COLLISION' for i in pkg['blocking_issues'])
