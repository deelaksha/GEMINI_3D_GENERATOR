"""Geometry, 2D validation, joint evaluation and 3D interference."""
import copy
import math

import pytest

from board_engine import geometry as G
from board_engine.joining import check_joint, join
from board_engine.model import SchemaError, build_plates, find_component, normalize_component
from board_engine.validation import evaluate_joint, find_collisions, validate_component, validate_design

from conftest import GOOD_SLOT, TAB_JOINT, base_plate, make, wall


def codes(issues, severity=None):
    return {i['code'] for i in issues if severity is None or i['severity'] == severity}


# --- coordinate system -------------------------------------------------------------------

def test_euler_order_matches_threejs_xyz():
    # THREE: Euler(90°, 90°, 0, 'XYZ') applied to +X gives +Y (R = Rx·Ry·Rz)
    f = G.Frame([0, 0, 0], [90, 90, 0])
    assert [round(v, 6) for v in f.dir_to_world([1, 0, 0])] == [0, 1, 0]


def test_frame_roundtrip_and_matrix():
    f = G.Frame([10, -5, 3], [12, -40, 77])
    p = [3.3, -7.1, 0.4]
    back = f.to_local(f.to_world(p))
    assert all(abs(a - b) < 1e-9 for a, b in zip(back, p))
    m = f.matrix4()
    assert m[12:15] == [10, -5, 3] and m[15] == 1


def test_clockwise_outline_is_normalised():
    c, notes = normalize_component({'id': 'X', 'outline': [[0, 0], [0, 10], [10, 10], [10, 0]]})
    assert G.signed_area(c['outline']) > 0 and notes


def test_schema_rejects_bad_input():
    with pytest.raises(SchemaError):
        normalize_component({'id': 'bad id!', 'outline': [[0, 0], [1, 0], [1, 1]]})
    with pytest.raises(SchemaError):
        normalize_component({'id': 'X', 'outline': [[0, 0], [1, 0]]})
    with pytest.raises(SchemaError):
        normalize_component({'id': 'X', 'outline': [[0, 0], [1, 0], [1, float('nan')]]})


# --- 2D component rules --------------------------------------------------------------------

def test_self_intersecting_outline_is_invalid():
    d = make({'id': 'BOW', 'outline': [[0, 0], [10, 10], [10, 0], [0, 10]]})
    assert 'OUTLINE_SELF_INTERSECTION' in codes(validate_component(d, d['components'][0]))


def test_feature_rules():
    feats = [{'id': 'out', 'kind': 'hole', 'shape': 'circle', 'center': [49, 0], 'diameter': 6},
             {'id': 'edge', 'kind': 'slot', 'shape': 'rect', 'center': [0, 28], 'width': 10, 'height': 3.1},
             {'id': 'o1', 'kind': 'opening', 'shape': 'rect', 'center': [-20, 0], 'width': 10, 'height': 10},
             {'id': 'o2', 'kind': 'opening', 'shape': 'rect', 'center': [-14, 0], 'width': 10, 'height': 10}]
    d = make(base_plate(features=feats))
    found = codes(validate_component(d, d['components'][0]))
    assert {'FEATURE_OUTSIDE_OUTLINE', 'INSUFFICIENT_EDGE_MARGIN', 'FEATURE_OVERLAP'} <= found


def test_tab_outside_edge_and_sheet_fit():
    d = make(wall(tabs=[{'id': 't', 'edge': 0, 'offset': 78, 'width': 20, 'depth': 3}]),
             {'id': 'HUGE', 'outline': [[0, 0], [900, 0], [900, 10], [0, 10]]})
    issues = validate_design(d)['issues']
    assert {'TAB_OUTSIDE_EDGE', 'PART_EXCEEDS_SHEET'} <= codes(issues)


def test_duplicate_component_detected(pair):
    dup = copy.deepcopy(find_component(pair, 'WALL'))
    dup['id'] = 'WALL-COPY'
    pair['components'].append(dup)
    assert 'DUPLICATE_COMPONENT' in codes(validate_design(pair)['issues'])


# --- joint evaluation ----------------------------------------------------------------------

def test_correct_existing_slot_is_used_not_modified(pair_with_slot):
    before = copy.deepcopy(find_component(pair_with_slot, 'BASE')['features'])
    res = join(pair_with_slot, TAB_JOINT)
    assert res['accepted'] and res['repairs_applied'] == []
    assert res['joint']['slot'] == 's1'
    assert find_component(res['design'], 'BASE')['features'] == before


def test_missing_slot_needs_repair_then_is_generated(pair):
    res = join(pair, TAB_JOINT)
    assert not res['accepted'] and res['status'] == 'needs_repair'
    assert 'MISSING_SLOT' in codes(res['issues'])
    assert find_component(pair, 'BASE')['features'] == []  # nothing changed

    res = join(pair, TAB_JOINT, auto_repair=True)
    assert res['accepted']
    slot = find_component(res['design'], 'BASE')['features'][0]
    assert slot['kind'] == 'slot' and slot['generated_by'] == 'J1'
    assert slot['width'] == pytest.approx(20.1) and slot['height'] == pytest.approx(3.1)
    assert slot['center'] == pytest.approx([0, 0], abs=1e-6)
    assert res['validation']['valid']


def test_missing_slot_causes_collision_until_joined(pair):
    assert 'COLLISION' in codes(validate_design(pair)['issues'])
    res = join(pair, TAB_JOINT, auto_repair=True)
    assert 'COLLISION' not in codes(res['validation']['issues'])


def test_undersized_slot_is_resized(pair):
    small = dict(GOOD_SLOT, width=15.0)
    d = make(base_plate(features=[small]), wall())
    res = join(d, TAB_JOINT, auto_repair=True)
    assert res['accepted'] and res['repairs_applied'][0]['action'] == 'resize_slot'
    assert find_component(res['design'], 'BASE')['features'][0]['width'] == pytest.approx(20.1)


def test_misaligned_slot_is_reported_not_auto_moved():
    d = make(base_plate(features=[dict(GOOD_SLOT, center=[3.0, 0])]), wall())
    res = join(d, TAB_JOINT, auto_repair=True)
    assert not res['accepted'] and 'SLOT_MISALIGNED' in codes(res['issues'])
    sug = next(i for i in res['issues'] if i['code'] == 'SLOT_MISALIGNED')['suggestion']
    assert sug['action'] == 'translate' and sug['delta'] == pytest.approx([3.0, 0, 0], abs=1e-6)


def test_tab_landing_in_intentional_opening_is_rejected_and_opening_preserved():
    opening = {'id': 'window', 'kind': 'opening', 'shape': 'rect', 'center': [0, 0], 'width': 30, 'height': 20}
    d = make(base_plate(features=[opening]), wall())
    res = join(d, TAB_JOINT, auto_repair=True)
    assert not res['accepted'] and 'TAB_IN_OPENING' in codes(res['issues'])
    feats = find_component(d, 'BASE')['features']
    assert [(f['id'], f['kind'], f['width'], f['height']) for f in feats] == [('window', 'opening', 30, 20)]


def test_intentional_opening_is_not_reported_as_gap(pair):
    opening = {'id': 'hatch', 'kind': 'opening', 'shape': 'circle', 'center': [-30, 10], 'diameter': 12}
    d = make(base_plate(features=[opening]), wall())
    res = join(d, TAB_JOINT, auto_repair=True)
    assert res['accepted']
    issues = res['validation']['issues']
    assert not any(i.get('feature') == 'hatch' for i in issues)
    assert any(f['id'] == 'hatch' and f['kind'] == 'opening' for f in find_component(res['design'], 'BASE')['features'])


def test_unused_slot_is_warned_not_filled():
    d = make(base_plate(features=[dict(GOOD_SLOT, id='spare', center=[30, 15])]))
    rep = validate_design(d)
    assert 'UNUSED_SLOT' in codes(rep['issues'], 'warning')
    assert find_component(d, 'BASE')['features'][0]['id'] == 'spare'


def test_gap_is_rejected_with_translation_suggestion(pair):
    find_component(pair, 'WALL')['placement']['position'][1] += 2.0
    res = join(pair, TAB_JOINT, auto_repair=True)
    assert not res['accepted'] and 'UNINTENDED_GAP' in codes(res['issues'])
    sug = next(i for i in res['issues'] if i['code'] == 'UNINTENDED_GAP')['suggestion']
    assert sug['delta'] == pytest.approx([0, -2.0, 0], abs=1e-6)
    find_component(pair, 'WALL')['placement']['position'][1] += sug['delta'][1]
    assert join(pair, TAB_JOINT, auto_repair=True)['accepted']


def test_penetration_is_rejected(pair):
    find_component(pair, 'WALL')['placement']['position'][1] -= 1.5
    res = join(pair, TAB_JOINT, auto_repair=True)
    assert not res['accepted'] and 'PENETRATION' in codes(res['issues'])


def test_wrong_orientation_cannot_join(pair):
    find_component(pair, 'WALL')['placement']['rotation'] = [0, 0, 30]
    res = join(pair, TAB_JOINT, auto_repair=True)
    assert not res['accepted'] and 'ORIENTATION_MISMATCH' in codes(res['issues'])


def test_tab_outside_receiver_cannot_join(pair):
    find_component(pair, 'WALL')['placement']['position'][0] = 70
    res = join(pair, TAB_JOINT, auto_repair=True)
    assert not res['accepted'] and 'TAB_OUTSIDE_RECEIVER' in codes(res['issues'])


def test_slot_too_close_to_edge_is_unsafe_repair(pair):
    find_component(pair, 'WALL')['placement']['position'][2] = 27.5  # generated slot would be 0.95 mm from edge
    res = join(pair, TAB_JOINT, auto_repair=True)
    assert not res['accepted'] and res['status'] == 'repair_unsafe'
    assert 'INSUFFICIENT_EDGE_MARGIN' in codes(res['issues'])
    assert find_component(pair, 'BASE')['features'] == []


def test_duplicate_join_rejected(pair):
    res = join(pair, TAB_JOINT, auto_repair=True)
    again = join(res['design'], dict(TAB_JOINT, id='J2'), auto_repair=True)
    assert not again['accepted'] and 'DUPLICATE_JOINT' in codes(again['issues'])


def test_check_joint_is_read_only(pair):
    snap = copy.deepcopy(pair)
    res = check_joint(pair, TAB_JOINT)
    assert not res['ok'] and res['repairs_available'][0]['action'] == 'create_slot'
    assert pair == snap


def test_edge_butt_and_face_lap():
    a = {'id': 'A', 'outline': [[-20, -10], [20, -10], [20, 10], [-20, 10]],
         'placement': {'position': [0, 10, 0], 'rotation': [0, 90, 0]}}
    b = {'id': 'B', 'outline': [[-30, -10], [30, -10], [30, 10], [-30, 10]],
         'placement': {'position': [0, 10, -21.5], 'rotation': [0, 0, 0]}}  # A edge 1 (local +x -> -z) on B face
    d = dict(make(a, b), joinery='glue_allowed')
    ok = join(d, {'id': 'E', 'type': 'edge_butt', 'a': 'A', 'a_edge': 1, 'b': 'B'})
    assert ok['accepted'], ok['issues']
    find_component(d, 'B')['placement']['position'][2] = -23.0
    bad = join(d, {'id': 'E', 'type': 'edge_butt', 'a': 'A', 'a_edge': 1, 'b': 'B'})
    assert 'UNINTENDED_GAP' in codes(bad['issues'])

    c = {'id': 'C', 'outline': [[0, 0], [10, 0], [10, 10], [0, 10]], 'thickness': 1.5,
         'placement': {'position': [-5, 5, -21.5 + 2.25], 'rotation': [0, 0, 0]}}
    d2 = dict(make(b, c), joinery='glue_allowed')
    assert join(d2, {'id': 'F', 'type': 'face_lap', 'a': 'C', 'b': 'B'})['accepted']
    find_component(d2, 'C')['placement']['position'][0] = 200
    assert 'NOT_IN_CONTACT' in codes(join(d2, {'id': 'F', 'type': 'face_lap', 'a': 'C', 'b': 'B'})['issues'])


def test_unrelated_overlapping_components_collide():
    a = {'id': 'A', 'outline': [[-20, -10], [20, -10], [20, 10], [-20, 10]],
         'placement': {'position': [0, 0, 0], 'rotation': [0, 0, 0]}}
    b = {'id': 'B', 'outline': [[-20, -10], [20, -10], [20, 10], [-20, 10]],
         'placement': {'position': [0, 0, 0], 'rotation': [0, 90, 0]}}  # crossing at 90°
    c = {'id': 'C', 'outline': [[-20, -10], [20, -10], [20, 10], [-20, 10]],
         'placement': {'position': [5, 0, 1.0], 'rotation': [0, 0, 0]}}  # parallel, overlapping thickness
    d = make(a, b, c)
    found = find_collisions(d, build_plates(d))
    pairs = {frozenset(i['components']) for i in found}
    assert frozenset({'A', 'B'}) in pairs and frozenset({'A', 'C'}) in pairs


def test_touching_parallel_boards_do_not_collide():
    a = {'id': 'A', 'outline': [[-20, -10], [20, -10], [20, 10], [-20, 10]],
         'placement': {'position': [0, 0, 0], 'rotation': [0, 0, 0]}}
    b = dict(copy.deepcopy(a), id='B', placement={'position': [5, 0, 3.0], 'rotation': [0, 0, 0]})
    d = make(a, b)
    assert find_collisions(d, build_plates(d)) == []


# --- boat (example product) -----------------------------------------------------------------

def test_boat_is_valid_complete_and_unique(boat):
    rep = validate_design(boat)
    assert rep['valid'] and rep['complete'], [i['message'] for i in rep['issues']]
    assert rep['summary']['warnings'] == 0
    ids = [c['id'] for c in boat['components']]
    assert len(ids) == len(set(ids)) == 14
    assert all(j['status'] == 'joined' for j in boat['joints'])


def test_boat_dimensions_and_thickness(boat):
    plates = build_plates(boat)
    bottom = plates['HULL-BOTTOM']
    x0, y0, x1, y1 = bottom.bbox2d
    assert (x1 - x0, y1 - y0) == (pytest.approx(320.77, abs=0.05), pytest.approx(92.0, abs=0.01))
    assert plates['HULL-BOTTOM'].t == 3.0 and plates['SAIL-MAIN'].t == 3.0   # one board material throughout
    # deck sits on top of the 50 mm sides: deck mid-plane at y = 3 + 50 + 1.5
    assert plates['DECK'].frame.p[1] == pytest.approx(54.5)
    lo, hi = plates['KEEL'].world_aabb()
    assert hi[1] == pytest.approx(3.0)  # keel tabs reach the top face of the bottom


def test_boat_openings_preserved_and_slots_generated(boat):
    deck = find_component(boat, 'DECK')
    kinds = [f['kind'] for f in deck['features']]
    assert kinds.count('opening') == 1 and kinds.count('slot') == 10
    for c in boat['components']:
        for f in c['features']:
            if f['kind'] == 'slot':
                assert f['generated_by'] in {j['id'] for j in boat['joints']}
    bh = find_component(boat, 'BULKHEAD-1')
    assert bh['features'][0]['kind'] == 'opening'


def test_glue_free_design_rejects_glued_joints():
    a = {'id': 'A', 'outline': [[-20, -10], [20, -10], [20, 10], [-20, 10]],
         'placement': {'position': [0, 10, 0], 'rotation': [0, 90, 0]}}
    b = {'id': 'B', 'outline': [[-30, -10], [30, -10], [30, 10], [-30, 10]],
         'placement': {'position': [0, 10, -21.5], 'rotation': [0, 0, 0]}}
    d = make(a, b)
    assert d['joinery'] == 'interlocking'                      # glue-free is the default
    for spec in ({'id': 'E', 'type': 'edge_butt', 'a': 'A', 'a_edge': 1, 'b': 'B'},
                 {'id': 'F', 'type': 'face_lap', 'a': 'A', 'b': 'B'},
                 {'id': 'G', 'type': 'edge_mitre', 'a': 'A', 'a_edge': 1, 'b': 'B', 'b_edge': 0}):
        res = join(d, spec, auto_repair=True)
        assert not res['accepted'] and res['issues'][0]['code'] == 'GLUE_JOINT_NOT_ALLOWED'


def test_boat_is_fully_interlocking(boat):
    """Cardboard, no glue: every connection must be a tab locked through a slot."""
    assert boat['joinery'] == 'interlocking'
    assert {j['type'] for j in boat['joints']} == {'tab_slot'}
    tabs = {(c['id'], t['id']) for c in boat['components'] for t in c['tabs']}
    joined_tabs = {(j['a'], j['tab']) for j in boat['joints']}
    assert tabs == joined_tabs                                 # every tab is used, none left dangling
    slots = [f for c in boat['components'] for f in c['features'] if f['kind'] == 'slot']
    assert len(slots) == len(boat['joints'])                   # exactly one slot per tab, no duplicates
    for c in boat['components']:                               # every part is held by at least one interlock
        assert any(c['id'] in (j['a'], j['b']) for j in boat['joints']), c['id']
