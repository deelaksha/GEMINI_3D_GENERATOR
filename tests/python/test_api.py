"""REST API: auth, roles, AI-style workflow, concurrency, exports."""
import importlib
import json

import pytest

from conftest import TAB_JOINT, base_plate, wall


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    inst = tmp_path_factory.mktemp('instance')
    import os
    os.environ['BOARD_INSTANCE_DIR'] = str(inst)
    os.environ['BOARD_API_KEYS'] = 'ed-key:editor,view-key:viewer,adm-key:admin'
    os.environ['BOARD_SKIP_SEED'] = '1'
    import app as app_module
    importlib.reload(app_module)
    app_module.app.config['TESTING'] = True
    yield app_module.app.test_client()
    for k in ('BOARD_INSTANCE_DIR', 'BOARD_API_KEYS', 'BOARD_SKIP_SEED'):
        os.environ.pop(k, None)


ED = {'Authorization': 'Bearer ed-key'}
VIEW = {'X-API-Key': 'view-key'}
ADM = {'Authorization': 'Bearer adm-key'}


def test_contract_and_tools_are_public(client):
    r = client.get('/api/v1/')
    assert r.status_code == 200 and 'endpoints' in r.json
    tools = client.get('/api/v1/tools').json['tools']
    assert {'join', 'check_joint', 'validate_design', 'apply_operations'} <= {t['name'] for t in tools}
    assert 'Access-Control-Allow-Origin' not in r.headers


def test_authentication_and_roles(client):
    assert client.get('/api/v1/designs').status_code == 401
    assert client.get('/api/v1/designs', headers={'Authorization': 'Bearer nope'}).status_code == 401
    assert client.get('/api/v1/designs', headers=VIEW).status_code == 200
    r = client.post('/api/v1/designs', headers=VIEW, json={'id': 'x', 'components': []})
    assert r.status_code == 403
    client.post('/api/v1/designs', headers=ED, json={'id': 'to-delete'})
    assert client.delete('/api/v1/designs/to-delete', headers=VIEW).status_code == 403
    assert client.delete('/api/v1/designs/to-delete', headers=ED).status_code == 200
    assert client.get('/api/v1/designs/to-delete', headers=VIEW).status_code == 404


def test_studio_session_requires_csrf_header(client):
    page = client.get('/')
    assert page.status_code == 200
    cookie = page.headers['Set-Cookie']
    assert 'HttpOnly' in cookie and 'SameSite=Strict' in cookie
    assert client.get('/api/v1/designs').status_code == 401               # cookie alone is not enough
    assert client.get('/api/v1/designs', headers={'X-Board-Client': 'studio'}).status_code == 200


def test_schema_errors_are_400(client):
    r = client.post('/api/v1/designs', headers=ED, data='not json', content_type='application/json')
    assert r.status_code == 400
    r = client.post('/api/v1/designs', headers=ED, json={'id': 'bad id with spaces'})
    assert r.status_code == 400 and r.json['error']['issues'][0]['path'] == 'id'


def test_ai_agent_workflow(client):
    # 1. create a design from components (validated on the way in)
    r = client.post('/api/v1/designs', headers=ED,
                    json={'id': 'shelf', 'name': 'Shelf', 'components': [base_plate(), wall()]})
    assert r.status_code == 201, r.json
    v = r.json['validation']
    assert not v['valid'] and any(i['code'] == 'COLLISION' for i in v['issues'])  # tab has no slot yet

    # 2. inspect
    comps = client.get('/api/v1/designs/shelf/components', headers=VIEW).json['components']
    wall_c = next(c for c in comps if c['id'] == 'WALL')
    assert wall_c['edges'][0]['length'] == 80 and wall_c['tabs'][0]['world_insertion_direction'] == [0, -1, 0]

    # 3. dry-run, then join without permission to repair -> 422 needs_repair, nothing saved
    chk = client.post('/api/v1/designs/shelf/joints/check', headers=VIEW, json={'joint': TAB_JOINT}).json
    assert chk['ok'] and not chk['fits'] and chk['repairs_available'][0]['action'] == 'create_slot'
    r = client.post('/api/v1/designs/shelf/joints', headers=ED, json={'joint': TAB_JOINT})
    assert r.status_code == 422 and r.json['error']['status'] == 'needs_repair'
    assert client.get('/api/v1/designs/shelf', headers=VIEW).json['revision'] == 1

    # 4. AI introduces a placement error, the join is rejected with a suggestion, AI applies it
    r = client.post('/api/v1/designs/shelf/components/WALL/translate', headers=ED, json={'delta': [0, 4, 0]})
    assert r.status_code == 200
    r = client.post('/api/v1/designs/shelf/joints', headers=ED, json={'joint': TAB_JOINT, 'auto_repair': True})
    assert r.status_code == 422
    gap = next(i for i in r.json['error']['issues'] if i['code'] == 'UNINTENDED_GAP')
    r = client.post('/api/v1/designs/shelf/components/WALL/translate', headers=ED,
                    json={'delta': gap['suggestion']['delta']})
    assert r.status_code == 200

    # 5. join with auto repair -> slot generated, design valid
    r = client.post('/api/v1/designs/shelf/joints', headers=ED, json={'joint': TAB_JOINT, 'auto_repair': True})
    assert r.status_code == 201, r.json
    assert r.json['result']['repairs_applied'][0]['action'] == 'create_slot'
    assert r.json['validation']['valid'] and r.json['validation']['complete']

    # 6. 3D model for rendering
    m = client.get('/api/v1/designs/shelf/model3d', headers=VIEW).json
    assert {c['state'] for c in m['components']} == {'joined'} and len(m['components'][0]['matrix_world']) == 16

    # 7. an edit that would break the joint is refused
    r = client.patch('/api/v1/designs/shelf/components/WALL', headers=ED,
                     json={'patch': {'placement': {'position': [0, 40, 0]}}})
    assert r.status_code == 422 and r.json['error']['status'] == 'would_break_joints'

    # 8. history records every accepted change with the actor
    hist = client.get('/api/v1/designs/shelf/history', headers=VIEW).json['history']
    assert [h['op'] for h in hist] == ['create', 'translate', 'translate', 'join']
    assert hist[-1]['actor'] == 'key:env:ed-k…'


def test_optimistic_concurrency(client):
    client.post('/api/v1/designs', headers=ED, json={'id': 'conc', 'components': [base_plate()]})
    r = client.post('/api/v1/designs/conc/components', headers=ED,
                    json={'component': wall(), 'expected_revision': 7})
    assert r.status_code == 409
    r = client.post('/api/v1/designs/conc/components', headers=ED, json={'component': wall(), 'expected_revision': 1})
    assert r.status_code == 201 and r.json['revision'] == 2


def test_batch_operations_atomic_via_api(client):
    client.post('/api/v1/designs', headers=ED, json={'id': 'batch', 'components': [base_plate(), wall()]})
    r = client.post('/api/v1/designs/batch/operations', headers=ED, json={'operations': [
        {'op': 'join', 'joint': TAB_JOINT, 'auto_repair': True},
        {'op': 'join', 'joint': {'id': 'J9', 'type': 'tab_slot', 'a': 'WALL', 'tab': 'nope', 'b': 'BASE'}}]})
    assert r.status_code == 422 and r.json['error']['failed_index'] == 1
    assert client.get('/api/v1/designs/batch/joints', headers=VIEW).json['joints'] == []


def test_boat_example_and_production_exports(client):
    r = client.post('/api/v1/designs/examples/boat', headers=ED, json={'id': 'boat-api'})
    assert r.status_code == 201 and r.json['join_failures'] == []
    assert r.json['validation']['valid'] and r.json['validation']['summary']['joined'] == 32
    lay = client.get('/api/v1/designs/boat-api/layout2d?preset=A3&kerf=1', headers=VIEW).json
    assert lay['ready_for_production'] and lay['nesting']['sheet_count'] == 2
    pdf = client.get('/api/v1/designs/boat-api/export/pdf?preset=A3', headers=VIEW)
    assert pdf.status_code == 200 and pdf.data[:8] == b'%PDF-1.4'
    svg = client.get('/api/v1/designs/boat-api/export/svg?preset=A3&sheet=2', headers=VIEW)
    assert svg.status_code == 200 and b'CUT_OUTER' in svg.data
    assert client.get('/api/v1/designs/boat-api/export/dxf?preset=A3&sheet=3', headers=VIEW).status_code == 400
    # parametric: a longer boat still assembles through the same pipeline
    r = client.post('/api/v1/designs/examples/boat', headers=ED, json={'id': 'boat-long', 'params': {'length': 360}})
    assert r.status_code == 201 and r.json['validation']['valid']


def test_export_refused_for_invalid_design(client):
    client.post('/api/v1/designs', headers=ED, json={'id': 'broken', 'components': [base_plate(), wall()]})
    r = client.get('/api/v1/designs/broken/export/pdf', headers=VIEW)
    assert r.status_code == 409 and r.json['error']['status'] == 'not_ready_for_production'
    r = client.get('/api/v1/designs/broken/export/pdf?force=1', headers=VIEW)
    assert r.status_code == 200 and b'DO NOT CUT' in __import__('zlib').decompress(
        r.data.split(b'stream\n')[1].split(b'\nendstream')[0])


def test_design_management_and_storage(client):
    st = client.get('/api/v1/storage', headers=VIEW).json
    assert st['backend'] == 'file' and st['persistent'] is True
    client.post('/api/v1/designs', headers=ED, json={'id': 'mgmt', 'name': 'Original', 'components': [base_plate()]})
    r = client.patch('/api/v1/designs/mgmt', headers=ED, json={'name': 'Renamed'})
    assert r.status_code == 200 and r.json['result']['name'] == 'Renamed'
    assert client.patch('/api/v1/designs/mgmt', headers=ED, json={'components': []}).status_code == 400
    r = client.post('/api/v1/designs/mgmt/duplicate', headers=ED, json={'id': 'mgmt-copy'})
    assert r.status_code == 201
    copy_ = client.get('/api/v1/designs/mgmt-copy', headers=VIEW).json['design']
    assert copy_['name'] == 'Renamed (copy)' and len(copy_['components']) == 1 and copy_['revision'] == 1
    assert client.post('/api/v1/designs/mgmt/duplicate', headers=ED, json={'id': 'mgmt-copy'}).status_code == 409
