"""Deterministic fixes: apply one, auto-fix all, and refusing what needs a design decision."""
import copy

import pytest

from board_engine.autofix import apply_fix, auto_fix, plan_fixes
from board_engine.joining import join
from board_engine.model import find_component, find_joint
from board_engine.operations import OperationRejected, apply_operation
from board_engine.validation import validate_design

from conftest import TAB_JOINT, base_plate, make, wall


def feature_count(d):
    return sum(len(c['features']) for c in d['components'])


@pytest.fixture
def joined(pair):
    return join(pair, TAB_JOINT, auto_repair=True)['design']


def test_detached_gap_is_fixed_by_one_translate(joined):
    apply_operation(joined, {'op': 'translate', 'id': 'WALL', 'delta': [0, 2, 0], 'detach_broken_joints': True})
    rep = validate_design(joined)
    assert 'JOINT_NOT_JOINED' in {i['code'] for i in rep['issues']} and not rep['complete']
    plan = plan_fixes(joined)
    assert [f['id'] for f in plan['fixes']] == ['J1:translate']
    assert plan['fixes'][0]['delta'] == pytest.approx([0, -2, 0], abs=1e-6)
    work, rec = apply_fix(joined, 'J1:translate')
    assert find_joint(work, 'J1')['status'] == 'joined'
    assert find_component(work, 'WALL')['placement']['position'] == pytest.approx([0, 23, 0])
    assert feature_count(work) == feature_count(joined)          # existing slot reused, no duplicate
    assert validate_design(work)['complete']


def test_sunk_through_part_gets_penetration_fix(joined):
    apply_operation(joined, {'op': 'translate', 'id': 'WALL', 'delta': [0, -4, 0], 'detach_broken_joints': True})
    plan = plan_fixes(joined)
    assert plan['fixes'][0]['cause'] == 'PENETRATION'
    work, _ = auto_fix(joined)[0], None
    assert validate_design(work)['complete']


def test_stale_fix_id_is_refused(joined):
    with pytest.raises(OperationRejected) as e:
        apply_fix(joined, 'J1:translate')
    assert e.value.status == 'fix_not_applicable'


def test_tab_in_intentional_opening_is_not_auto_fixed():
    opening = {'id': 'window', 'kind': 'opening', 'shape': 'rect', 'center': [0, 0], 'width': 30, 'height': 20}
    d = make(base_plate(features=[opening]), wall(),
             joints=[dict(TAB_JOINT, status='detached')])
    work, rep = auto_fix(d)
    assert rep['steps'] == [] and rep['unfixable'][0]['code'] == 'TAB_IN_OPENING'
    assert work == d                                              # nothing modified
    assert find_component(work, 'BASE')['features'][0]['kind'] == 'opening'


def test_fix_that_would_break_other_joints_is_skipped():
    # WALL is joined to BASE by a correct tab; a second, detached tab joint into a misplaced LID
    # would need WALL to move — which would break the good joint, so auto-fix must refuse.
    w = wall(tabs=[{'id': 't1', 'edge': 0, 'offset': 40, 'width': 20, 'depth': 3},
                   {'id': 't2', 'edge': 2, 'offset': 40, 'width': 20, 'depth': 3}])
    lid = base_plate(id='LID', placement={'position': [0, 46.5, 0], 'rotation': [-90, 0, 0]})  # 2 mm too high
    d = make(base_plate(), w, lid)
    d = join(d, TAB_JOINT, auto_repair=True)['design']
    d['joints'].append({'id': 'J2', 'type': 'tab_slot', 'a': 'WALL', 'tab': 't2', 'b': 'LID', 'status': 'detached'})
    work, rep = auto_fix(d)
    assert rep['steps'] == [] and rep['skipped'][0]['fix']['id'] == 'J2:translate'
    assert find_joint(work, 'J1')['status'] == 'joined'


def test_auto_fix_repairs_broken_boat(boat):
    b = copy.deepcopy(boat)
    apply_operation(b, {'op': 'translate', 'id': 'BULKHEAD-1', 'delta': [0, -3, 0], 'detach_broken_joints': True})
    apply_operation(b, {'op': 'translate', 'id': 'MAST', 'delta': [0, 2.5, 0], 'detach_broken_joints': True})
    assert validate_design(b)['summary']['errors'] > 0
    work, rep = auto_fix(b)
    assert rep['valid'] and rep['complete'] and rep['unfixable'] == []
    assert all(s['errors_after'] <= s['errors_before'] for s in rep['steps'])
    assert feature_count(work) == feature_count(boat)
    assert find_component(work, 'BULKHEAD-1')['placement'] == find_component(boat, 'BULKHEAD-1')['placement']


def test_fix_api(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv('BOARD_INSTANCE_DIR', str(tmp_path))
    monkeypatch.setenv('BOARD_API_KEYS', 'ed:editor,vw:viewer')
    monkeypatch.setenv('BOARD_SKIP_SEED', '1')
    import app as app_module
    importlib.reload(app_module)
    c = app_module.app.test_client()
    ED, VW = {'Authorization': 'Bearer ed'}, {'Authorization': 'Bearer vw'}
    c.post('/api/v1/designs', headers=ED, json={'id': 'fx', 'components': [base_plate(), wall()],
                                               'joints': [TAB_JOINT], 'auto_repair': True})
    c.post('/api/v1/designs/fx/components/WALL/translate', headers=ED,
           json={'delta': [0, 3, 0], 'detach_broken_joints': True})
    v = c.post('/api/v1/designs/fx/validate', headers=VW).json['validation']
    assert v['fixes'][0]['id'] == 'J1:translate'
    assert any(i.get('fix_id') == 'J1:translate' for i in v['issues'])
    assert c.post('/api/v1/designs/fx/fixes/apply', headers=VW, json={'fix_id': 'J1:translate'}).status_code == 403
    r = c.post('/api/v1/designs/fx/fixes/apply', headers=ED, json={'fix_id': 'J1:translate'})
    assert r.status_code == 200 and r.json['validation']['complete']
    assert c.post('/api/v1/designs/fx/fixes/apply', headers=ED, json={'fix_id': 'J1:translate'}).status_code == 422
    rev = r.json['revision']
    r = c.post('/api/v1/designs/fx/fixes/auto', headers=ED, json={})
    assert r.status_code == 200 and r.json['result']['steps'] == [] and r.json['revision'] == rev  # no-op not saved
    hist = [h['op'] for h in c.get('/api/v1/designs/fx/history', headers=VW).json['history']]
    assert hist[-1] == 'apply_fix'
