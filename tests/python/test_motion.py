"""Moving parts ("motions"): axle holes, mounting, fixed joints, slide direction and clearance through the travel."""
import copy
import json

import pytest

from board_engine import canvas

T = 18
TURNTABLE = {'format': 'board-design/v1', 'product': {'name': 'turntable'}, 'material': {'type': 'plywood', 'thickness': 6},
             'boards': [{'id': 'BASE', 'position': [0, 0, 0], 'size': [300, 6, 300]},
                        {'id': 'DISK', 'position': [50, 6, 50], 'size': [200, 6, 200],
                         'profile': {'shape': 'circle', 'center': [100, 100], 'diameter': 200}}],
             'connections': [],
             'motions': [{'id': 'spin', 'type': 'rotate', 'boards': ['DISK'], 'on': 'BASE', 'axis': 'y',
                          'pivot': [150, 6, 150], 'range': [0, 360], 'axle': {'diameter': 8}}]}
CHEST = {'format': 'board-design/v1', 'product': {'name': 'chest'}, 'material': {'type': 'plywood', 'thickness': T},
         'joinery': 'glue_allowed',
         'boards': [{'id': 'BOTTOM', 'position': [0, 0, 0], 'size': [600, T, 400]},
                    {'id': 'FRONT', 'position': [0, T, 0], 'size': [600, 300, T]},
                    {'id': 'BACK', 'position': [0, T, 400 - T], 'size': [600, 300, T]},
                    {'id': 'SIDE-L', 'position': [0, T, T], 'size': [T, 300, 400 - 2 * T]},
                    {'id': 'SIDE-R', 'position': [600 - T, T, T], 'size': [T, 300, 400 - 2 * T]},
                    {'id': 'LID', 'position': [0, 300 + T, 0], 'size': [600, T, 400]}],
         'connections': [{'type': 'finger', 'board': b, 'into': 'BOTTOM'} for b in ('FRONT', 'BACK', 'SIDE-L', 'SIDE-R')]
                        + [{'type': 'finger', 'board': s, 'into': w} for s in ('SIDE-L', 'SIDE-R') for w in ('FRONT', 'BACK')]
                        + [{'type': 'hinge', 'board': 'LID', 'into': 'BACK', 'edge': '+z', 'count': 2}],
         'motions': [{'id': 'open', 'type': 'rotate', 'boards': ['LID'], 'on': 'BACK', 'axis': 'x',
                      'pivot': [0, 300 + T, 400], 'range': [0, 100]}]}


@pytest.fixture(autouse=True)
def _no_snapshots(monkeypatch):
    monkeypatch.setattr(canvas, 'SNAPSHOT_DIR', None)


def compiled(d):
    return canvas.compile_source(json.dumps(d), run_production=False)


def codes(r, severity=None):
    return [x['code'] for x in r['diagnostics'] if severity is None or x['severity'] == severity]


def test_a_turntable_on_an_axle_compiles_with_its_holes_and_reaches_the_3d_view():
    r = compiled(TURNTABLE)
    assert r['ok'] and not codes(r, 'error') and not codes(r, 'warning')
    holes = {c['id']: [f for f in c['features'] if f['id'] == 'axle-spin'] for c in r['design']['components']}
    assert holes['DISK'] and holes['BASE'], 'the axle hole is cut through the disk and the base'
    assert any('Ø8 mm dowel' in x['message'] for x in r['diagnostics'] if x['code'] == 'MOTION_AXLE')
    m = r['model3d']['motions'][0]
    assert m['boards'] == ['DISK'] and m['axis'] == [0.0, 1.0, 0.0] and m['range'] == [0.0, 360.0]


def test_a_part_in_the_way_is_found_at_the_angle_it_is_hit_with_the_range_that_clears():
    d = copy.deepcopy(TURNTABLE)
    d['boards'][1] = {'id': 'DISK', 'position': [50, 6, 140], 'size': [200, 6, 20]}               # an arm, 100 mm reach
    d['boards'].append({'id': 'POST', 'position': [140, 6, 220], 'size': [20, 60, 6]})            # 70 mm from the pivot
    d['connections'] = [{'type': 'tab_slot', 'board': 'POST', 'into': 'BASE'}]
    hit = [x for x in compiled(d)['diagnostics'] if x['code'] == 'MOTION_COLLISION']
    assert len(hit) == 1 and "'POST' at 75°" in hit[0]['message'] and 'only to 70°' in hit[0]['message']
    assert any('every 5°' in line for line in hit[0]['calc'])


def test_a_hinged_lid_opens_freely_but_not_into_its_own_box():
    r = compiled(CHEST)
    assert r['ok'] and not [c for c in codes(r) if c.startswith('MOTION_') and c != 'MOTION_AXLE']
    assert 'CANTILEVER' not in codes(r) and 'UNJOINED_CONTACT' not in codes(r)       # a lid rests on the box by design
    d = copy.deepcopy(CHEST)
    d['motions'][0]['range'] = [-100, 0]
    hits = [x for x in compiled(d)['diagnostics'] if x['code'] == 'MOTION_COLLISION']
    assert {x['components'][1] for x in hits} >= {'FRONT', 'SIDE-L', 'SIDE-R'}


def test_a_fixed_joint_to_the_static_part_locks_the_motion():
    d = copy.deepcopy(TURNTABLE)
    d['boards'].append({'id': 'POST', 'position': [140, 6, 20], 'size': [20, 60, 6]})
    d['connections'] = [{'type': 'tab_slot', 'board': 'POST', 'into': 'BASE'}]
    d['motions'] = [{'id': 'swing', 'type': 'rotate', 'boards': ['POST'], 'on': 'BASE', 'axis': 'y',
                     'pivot': [150, 6, 23], 'range': [0, 90]}]
    assert 'MOTION_LOCKED' in codes(compiled(d), 'error')


def test_a_slide_must_run_along_its_support_and_the_group_must_touch_it():
    d = copy.deepcopy(TURNTABLE)
    d['motions'] = [{'id': 'push', 'type': 'slide', 'boards': ['DISK'], 'on': 'BASE', 'direction': 'y', 'range': [-20, 50]}]
    blocked = [x for x in compiled(d)['diagnostics'] if x['code'] == 'MOTION_SLIDE_BLOCKED']
    assert blocked and 'push it into its support' in blocked[0]['message'] and 'Lift it off instead' in blocked[0]['message']
    d['motions'][0]['direction'] = 'x'
    d['boards'][1]['position'] = [50, 20, 50]                                       # lifted 14 mm off the base
    assert 'MOTION_NOT_MOUNTED' in codes(compiled(d), 'error')


@pytest.mark.parametrize('motion, text', [
    ({'id': 'a', 'type': 'spin', 'boards': ['DISK'], 'on': 'BASE'}, '"type"'),
    ({'id': 'a', 'type': 'slide', 'boards': ['NOPE'], 'on': 'BASE', 'direction': 'x', 'range': [0, 9]}, 'unknown board'),
    ({'id': 'a', 'type': 'slide', 'boards': ['DISK'], 'on': 'DISK', 'direction': 'x', 'range': [0, 9]}, '"on"'),
    ({'id': 'a', 'type': 'slide', 'boards': ['DISK'], 'on': 'BASE', 'direction': 'x', 'range': [9, 0]}, '"range"'),
    ({'id': 'a', 'type': 'rotate', 'boards': ['DISK'], 'on': 'BASE', 'axis': 'q', 'range': [0, 9]}, '"axis"'),
])
def test_invalid_motions_are_explained(motion, text):
    d = dict(copy.deepcopy(TURNTABLE), motions=[motion])
    bad = [x['message'] for x in compiled(d)['diagnostics'] if x['code'] == 'MOTION_INVALID']
    assert bad and text in bad[0]


def test_an_axle_that_misses_the_boards_is_reported():
    d = copy.deepcopy(TURNTABLE)
    d['motions'][0]['axis'] = 'x'                       # the boards are thin along y: an x axle cannot pass through
    assert 'MOTION_AXLE' in codes(compiled(d), 'error')


def test_motions_survive_the_import_into_the_studio_and_reach_its_3d_view(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv('BOARD_INSTANCE_DIR', str(tmp_path))
    monkeypatch.setenv('BOARD_API_KEYS', 'ed:editor')
    monkeypatch.setenv('BOARD_SKIP_SEED', '1')
    import app as app_module
    importlib.reload(app_module)
    c, H = app_module.app.test_client(), {'Authorization': 'Bearer ed'}
    assert c.post('/api/v1/designs', headers=H, json={'id': 'shop', 'name': 'Shop'}).status_code in (200, 201)
    r = c.post('/api/v1/canvas/import', headers=H, json={'source': json.dumps(TURNTABLE), 'target': 'shop'})
    assert r.status_code == 200, r.json
    stored = c.get('/api/v1/designs/shop', headers=H).json['design']
    assert stored['motions'][0]['boards'] == ['DISK'] and stored['motions'][0]['axle']['diameter'] == 8.0
    m3d = c.get('/api/v1/designs/shop/model3d', headers=H).json
    assert m3d['motions'][0]['axis'] == [0.0, 1.0, 0.0]
    # a second turntable (400 mm along) into the same design: boards and the motion get new names, the first stays
    moved = copy.deepcopy(TURNTABLE)
    for b in moved['boards']:
        b['position'][0] += 400
    moved['motions'][0]['pivot'][0] += 400
    assert c.post('/api/v1/canvas/import', headers=H, json={'source': json.dumps(moved), 'target': 'shop'}).status_code == 200
    ms = c.get('/api/v1/designs/shop', headers=H).json['design']['motions']
    assert [(m['id'], m['boards']) for m in ms] == [('spin', ['DISK']), ('AI-spin', ['AI-DISK'])]
    # deleting a moving board drops its motion instead of breaking the design
    assert c.delete('/api/v1/designs/shop/components/AI-DISK', headers=H).status_code == 200
    assert [m['id'] for m in c.get('/api/v1/designs/shop', headers=H).json['design']['motions']] == ['spin']


def test_designs_without_motions_are_stored_exactly_as_before():
    from board_engine.model import normalize_design
    from conftest import base_plate
    assert 'motions' not in normalize_design({'id': 'd', 'components': [base_plate()], 'joints': []})


def test_a_lid_lifts_straight_off_but_not_into_what_is_above_it():
    d = copy.deepcopy(CHEST)
    d['connections'] = [c for c in d['connections'] if c['type'] != 'hinge']        # a loose lid, lifted off
    d['motions'] = [{'id': 'lift', 'type': 'slide', 'boards': ['LID'], 'on': 'FRONT', 'direction': 'y', 'range': [0, 150]}]
    r = compiled(d)
    assert not [c for c in codes(r, 'error') if c.startswith('MOTION_')], codes(r, 'error')
    assert r['model3d']['motions'][0]['direction'] == [0.0, 1.0, 0.0]
    d['boards'].append({'id': 'SHELF-ABOVE', 'position': [0, 420, 0], 'size': [600, T, 400]})   # 84 mm above the lid
    hit = [x for x in compiled(d)['diagnostics'] if x['code'] == 'MOTION_COLLISION']
    assert hit and "'SHELF-ABOVE'" in hit[0]['message']


def _drawer(gap):
    """A drawer bottom sliding out along z between two side walls, `gap` mm from each."""
    return {'format': 'board-design/v1', 'product': {'name': 'drawer'}, 'material': {'type': 'plywood', 'thickness': 6},
            'boards': [{'id': 'RUNNER', 'position': [0, 0, 0], 'size': [300, 6, 300]},
                       {'id': 'SIDE-L', 'position': [20, 6, 0], 'size': [6, 100, 300]},
                       {'id': 'SIDE-R', 'position': [274, 6, 0], 'size': [6, 100, 300]},
                       {'id': 'DRAWER', 'position': [26 + gap, 6, 10], 'size': [248 - 2 * gap, 6, 280]}],
            'connections': [{'type': 'tab_slot', 'board': 'SIDE-L', 'into': 'RUNNER'},
                            {'type': 'tab_slot', 'board': 'SIDE-R', 'into': 'RUNNER'}],
            'motions': [{'id': 'pull', 'type': 'slide', 'boards': ['DRAWER'], 'on': 'RUNNER', 'direction': 'z',
                         'range': [0, 200]}]}


def test_a_drawer_needs_a_running_gap_to_its_sides():
    tight = [x for x in compiled(_drawer(0))['diagnostics'] if x['code'] == 'MOTION_CLEARANCE']
    assert {x['components'][1] for x in tight} == {'SIDE-L', 'SIDE-R'} and 'would rub and bind' in tight[0]['message']
    assert not [c for c in codes(compiled(_drawer(2)), 'error') if c.startswith('MOTION_')]


def test_a_wheel_needs_a_running_gap_to_the_wall_beside_it():
    def wheel(gap):
        return {'format': 'board-design/v1', 'product': {'name': 'wheel'}, 'material': {'type': 'plywood', 'thickness': 6},
                'boards': [{'id': 'BASE', 'position': [0, 0, 0], 'size': [300, 6, 300]},
                           {'id': 'DISK', 'position': [50, 6, 50], 'size': [200, 6, 200],
                            'profile': {'shape': 'circle', 'center': [100, 100], 'diameter': 200}},
                           {'id': 'WALL', 'position': [250 + gap, 6, 0], 'size': [6, 60, 300]}],
                'connections': [{'type': 'tab_slot', 'board': 'WALL', 'into': 'BASE'}],
                'motions': [{'id': 'spin', 'type': 'rotate', 'boards': ['DISK'], 'on': 'BASE', 'axis': 'y',
                             'pivot': [150, 6, 150], 'range': [0, 360], 'axle': {'diameter': 8}}]}
    assert 'MOTION_CLEARANCE' in codes(compiled(wheel(0.5)), 'error')
    assert not [c for c in codes(compiled(wheel(3)), 'error') if c.startswith('MOTION_')]
