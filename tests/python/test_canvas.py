"""AI Design Canvas: parse -> validate -> compile through the existing generator -> render / production."""
import copy
import importlib
import json

import pytest

from board_engine.canvas import FORMAT, apply_code_fix, compile_source, parse_source
from board_engine.canvas_prompt import EXAMPLE, build_prompt, spec_markdown
from board_engine.model import find_component
from board_engine.validation import TOL


def codes(res, severity=None):
    return [d['code'] for d in res['diagnostics'] if severity is None or d['severity'] == severity]


# --- three external-AI-style designs -----------------------------------------------------------

STUDY_TABLE_REPLY = """Sure! Here is the design for your Modern Wooden Study Table:

```json
{
  // board-design/v1 study table, 18 mm plywood
  "format": "board-design/v1",
  "product": {"name": "Modern Wooden Study Table", "overall": {"length": 1200, "height": 750, "depth": 600}},
  "material": {"name": "Birch plywood 18 mm", "type": "plywood", "thickness": 18, "clearance": 0.2},
  "boards": [
    {"id": "TOP", "name": "Top", "position": [0, 732, 0], "size": [1200, 18, 600]},
    {"id": "LEG-L", "name": "Left leg", "position": [50, 0, 20], "size": [18, 732, 560]},
    {"id": "LEG-R", "name": "Right leg", "position": [1132, 0, 20], "size": [18, 732, 560]},
    {"id": "SHELF", "name": "Shelf", "position": [68, 150, 60], "size": [1064, 18, 400]},   /* storage shelf */
  ],
  "connections": [
    {"id": "C1", "type": "tab_slot", "board": "LEG-L", "into": "TOP"},
    {"id": "C2", "type": "tab_slot", "board": "LEG-R", "into": "TOP"},
    {"id": "C3", "type": "tab_slot", "board": "SHELF", "into": "LEG-L"},
    {"id": "C4", "type": "tab_slot", "board": "SHELF", "into": "LEG-R"},
  ]
}
```
Let me know if you want drawers!"""


def bookshelf():
    shelves = [80, 450, 850, 1250]
    boards = [{"id": "TOP", "position": [0, 1782, 0], "size": [800, 18, 300]},
              {"id": "SIDE-L", "position": [20, 0, 10], "size": [18, 1782, 280]},
              {"id": "SIDE-R", "position": [762, 0, 10], "size": [18, 1782, 280]},
              {"id": "BACK", "position": [38, 30, 262], "size": [724, 1752, 18]}]
    conns = [{"type": "tab_slot", "board": "SIDE-L", "into": "TOP", "tabs": 2},
             {"type": "tab_slot", "board": "SIDE-R", "into": "TOP", "tabs": 2},
             {"type": "tab_slot", "board": "BACK", "into": "TOP", "tabs": 3},
             {"type": "tab_slot", "board": "BACK", "into": "SIDE-L", "tabs": 3},
             {"type": "tab_slot", "board": "BACK", "into": "SIDE-R", "tabs": 3}]
    for i, y in enumerate(shelves, 1):
        boards.append({"id": f"SHELF-{i}", "group": "Shelves", "position": [38, y, 10], "size": [724, 18, 252]})
        conns += [{"type": "tab_slot", "board": f"SHELF-{i}", "into": "SIDE-L", "tabs": 2},
                  {"type": "tab_slot", "board": f"SHELF-{i}", "into": "SIDE-R", "tabs": 2}]
    return {"format": FORMAT, "product": {"name": "Bookshelf", "overall": {"length": 800, "height": 1800, "depth": 300}},
            "material": {"type": "plywood", "thickness": 18, "clearance": 0.2}, "boards": boards, "connections": conns}


def cabinet():
    B = lambda i, p, s, g='Carcass': {"id": i, "group": g, "position": p, "size": s}
    boards = [B("TOP", [0, 882, 0], [1000, 18, 500]),
              B("SIDE-L", [20, 0, 10], [18, 882, 480]), B("SIDE-R", [962, 0, 10], [18, 882, 480]),
              B("BOTTOM", [38, 80, 10], [924, 18, 452]),
              B("DIVIDER", [491, 98, 10], [18, 784, 452]),
              B("SHELF-L", [38, 450, 10], [453, 18, 452], 'Shelves'), B("SHELF-R", [509, 520, 10], [453, 18, 452], 'Shelves'),
              B("BACK", [38, 80, 462], [924, 802, 18], 'Back'),
              B("PLINTH", [38, 0, 30], [924, 80, 18], 'Base')]
    pairs = [("SIDE-L", "TOP"), ("SIDE-R", "TOP"), ("BOTTOM", "SIDE-L"), ("BOTTOM", "SIDE-R"), ("DIVIDER", "BOTTOM"),
             ("DIVIDER", "TOP"), ("DIVIDER", "BACK"), ("SHELF-L", "SIDE-L"), ("SHELF-L", "DIVIDER"), ("SHELF-R", "DIVIDER"),
             ("SHELF-R", "SIDE-R"), ("BACK", "TOP"), ("BACK", "SIDE-L"), ("BACK", "SIDE-R"), ("PLINTH", "BOTTOM"),
             ("PLINTH", "SIDE-L"), ("PLINTH", "SIDE-R")]
    return {"format": FORMAT, "product": {"name": "Two-compartment cabinet", "overall": {"length": 1000, "height": 900, "depth": 500}},
            "material": {"type": "plywood", "thickness": 18, "clearance": 0.2}, "boards": boards,
            "connections": [{"id": f"{a}-{b}", "type": "tab_slot", "board": a, "into": b} for a, b in pairs]}


@pytest.mark.parametrize('name, source, boards', [
    ('study table (AI chat reply)', STUDY_TABLE_REPLY, 4),
    ('bookshelf', json.dumps(bookshelf(), indent=2), 8),
    ('two-compartment cabinet', json.dumps(cabinet(), indent=2), 9),
    ('bundled prompt example', json.dumps(EXAMPLE, indent=2), 5),
])
def test_ai_designs_compile_render_and_validate(name, source, boards):
    res = compile_source(source)
    assert res['ok'], [(d['code'], d['message']) for d in res['diagnostics'] if d['severity'] == 'error']
    assert codes(res, 'warning') == []
    s = res['summary']
    assert s['boards'] == boards and s['joined'] == s['joints'] > 0
    assert res['validation']['valid'] and res['validation']['complete']
    # rendered by the existing engine: one model3d component per board, every state joined
    assert {c['state'] for c in res['model3d']['components']} == {'joined'}
    assert len(res['model3d']['components']) == boards
    # existing production pipeline: nested on stock sheets, cut paths, ready to manufacture
    assert res['layout']['ready_for_production'] and res['layout']['nesting']['unplaced'] == []
    # every connection became tabs on A and generated slots on B (one slot per tab)
    d = res['design']
    slots = sum(1 for c in d['components'] for f in c.get('features', []) if f['kind'] == 'slot')
    assert slots == sum(len(c.get('tabs', [])) for c in d['components']) == s['joints']


def test_source_map_points_at_board_definitions():
    res = compile_source(STUDY_TABLE_REPLY)
    lines = STUDY_TABLE_REPLY.splitlines()
    for bid in ('TOP', 'LEG-L', 'SHELF'):
        assert f'"id": "{bid}"' in lines[res['source_map'][bid] - 1]


def test_board_dimensions_survive_compilation():
    res = compile_source(STUDY_TABLE_REPLY)
    top = next(c for c in res['model3d']['components'] if c['id'] == 'TOP')
    lo, hi = top['world_bounds']['min'], top['world_bounds']['max']
    assert [round(hi[i] - lo[i], 2) for i in range(3)] == [1200, 18, 600]
    leg = next(c for c in res['model3d']['components'] if c['id'] == 'LEG-L')
    assert leg['thickness'] == 18 and round(leg['world_bounds']['max'][1], 2) == 750   # tabs reach through the 18 mm top


# --- the mistakes external AIs actually make ---------------------------------------------------

def test_forgotten_board_thickness_is_explained_with_fixes():
    bad = copy.deepcopy(EXAMPLE)
    for b in bad['boards']:
        if b['id'].startswith('LEG'):
            b['size'][1] = 750          # legs drawn full height, ignoring the 18 mm top
    src = json.dumps(bad, indent=2)
    res = compile_source(src)
    over = [d for d in res['diagnostics'] if d['code'] == 'CONNECTION_OVERLAP']
    assert {d['board'] for d in over} == {'LEG-L', 'LEG-R'}
    assert all(d['gap'] == pytest.approx(-18.0) and 'thickness' in d['message'] for d in over)
    assert all(d['line'] for d in over)
    fixed = src
    for d in over:
        shorten = next(f for f in d['fixes'] if f['id'].startswith('resize-'))
        assert not shorten['safe']                       # changes a dimension: the user decides
        fixed = apply_code_fix(fixed, shorten)
    assert compile_source(fixed)['ok']


def test_small_misplacement_has_safe_fix():
    bad = copy.deepcopy(EXAMPLE)
    next(b for b in bad['boards'] if b['id'] == 'SHELF')['position'][0] = 69.5     # 1.5 mm off LEG-L
    res = compile_source(json.dumps(bad))
    d = next(d for d in res['diagnostics'] if d['code'] == 'CONNECTION_GAP')
    move = next(f for f in d['fixes'] if f['id'].startswith('move-'))
    assert move['safe'] and move['edits'][0]['value'][0] == pytest.approx(68.0)
    assert compile_source(apply_code_fix(json.dumps(bad), move))['ok']


def test_board_at_receiver_edge_needs_inset():
    bad = copy.deepcopy(EXAMPLE)
    # across the leg's thickness (x) the slot needs material of TOP on both sides; along the leg (z) tabs are inset
    bad['boards'][1]['position'][0] = 1            # LEG-L 1 mm from the left edge of TOP: too little for a slot
    res = compile_source(json.dumps(bad))
    d = next(d for d in res['diagnostics'] if d['code'] == 'SLOT_AT_EDGE')
    assert d['board'] == 'LEG-L' and str(TOL['min_edge_margin']) in d['message']


def test_board_flush_with_receiver_edge_becomes_a_finger_joint():
    corner = copy.deepcopy(EXAMPLE)
    corner['boards'][1]['position'][0] = 0         # LEG-L flush with the left edge of TOP: a box corner
    res = compile_source(json.dumps(corner))
    assert any(d['code'] == 'CONNECTION_TYPE_CHANGED' and 'LEG-L-TOP → finger' in d['message'] for d in res['diagnostics'])
    assert not any(d['code'] == 'SLOT_AT_EDGE' for d in res['diagnostics'])


@pytest.mark.parametrize('mutate, code', [
    (lambda d: d['boards'][0].update(size=[1200, 20, 600]), 'THICKNESS_MISMATCH'),
    (lambda d: d['boards'].append(dict(d['boards'][0])), 'DUPLICATE_BOARD_ID'),
    (lambda d: d['connections'].append({'type': 'tab_slot', 'board': 'LEG-L', 'into': 'NOPE'}), 'UNKNOWN_BOARD'),
    (lambda d: d['connections'].append({'type': 'glue', 'board': 'LEG-L', 'into': 'TOP'}), 'CONNECTION_TYPE'),
    (lambda d: d['connections'].append({'type': 'butt', 'board': 'SHELF', 'into': 'LEG-L'}), 'GLUE_JOINT_IN_INTERLOCKING'),
    (lambda d: d['connections'].append({'type': 'tab_slot', 'board': 'SHELF', 'into': 'TOP'}), 'NO_CONTACT'),
    (lambda d: d['boards'][0].update(position='0,0,0'), 'BOARD_GEOMETRY'),
    (lambda d: d.pop('material'), 'MATERIAL_MISSING'),
    (lambda d: d['boards'][0].update(id='top board!'), 'BOARD_ID'),
])
def test_invalid_designs_give_clear_diagnostics(mutate, code):
    bad = copy.deepcopy(EXAMPLE)
    mutate(bad)
    res = compile_source(json.dumps(bad, indent=2))
    assert not res['ok'] and code in codes(res, 'error')


def test_overall_dimension_mismatch_warns():
    bad = copy.deepcopy(EXAMPLE)
    bad['product']['overall']['height'] = 768
    assert 'OVERALL_MISMATCH' in codes(compile_source(json.dumps(bad)), 'warning')


def test_parse_tolerates_ai_formatting_and_reports_positions():
    data, _src, _off, diags = parse_source(STUDY_TABLE_REPLY)
    assert diags == [] and data['product']['name'] == 'Modern Wooden Study Table'
    _d, _s, _o, diags = parse_source('Here you go:\n```json\n{\n  "boards": [\n    {"id": "A",, }\n  ]\n}\n```')
    assert diags[0]['code'] == 'JSON_SYNTAX' and diags[0]['line'] == 5


def test_javascript_is_never_executed():
    js = "const design = { boards: [] };\nfetch('/api/v1/designs', {method: 'DELETE'});\nexport default design;"
    res = compile_source(js)
    assert not res['ok'] and res['diagnostics'][0]['code'] == 'JSON_SYNTAX'
    assert 'JavaScript' in res['diagnostics'][0]['message']


@pytest.mark.parametrize('src', ['', '   ', '[]', '42', '{"boards": "nope", "material": {"thickness": 18}}', 'x' * 10, '{'])
def test_garbage_never_raises(src):
    res = compile_source(src)
    assert res['ok'] is False and res['diagnostics']


def test_native_engine_format_is_accepted(boat):
    res = compile_source(json.dumps(boat))
    assert res['format'] == 'native' and res['ok'] and res['summary']['joined'] == len(boat['joints'])


def test_butt_and_hinge_connections_when_glue_allowed():
    d = copy.deepcopy(EXAMPLE)
    d['joinery'] = 'glue_allowed'
    d['connections'] = [c for c in d['connections'] if not c['id'].startswith('SHELF')]
    d['connections'] += [{'id': 'SHELF-L', 'type': 'butt', 'board': 'SHELF', 'into': 'LEG-L', 'fasteners': {'kind': 'confirmat'}},
                         {'id': 'SHELF-R', 'type': 'butt', 'board': 'SHELF', 'into': 'LEG-R', 'fasteners': 'dowel'}]
    res = compile_source(json.dumps(d))
    assert res['ok'], [d['message'] for d in res['diagnostics'] if d['severity'] == 'error']
    joints = {j['id']: j for j in res['design']['joints']}
    assert joints['SHELF-L']['type'] == 'edge_butt' and joints['SHELF-L']['fasteners']['kind'] == 'confirmat'


# --- prompt and specification -------------------------------------------------------------------

def test_prompt_is_self_contained_and_project_specific():
    p = build_prompt('Modern Wooden Study Table', 'Length 1200 mm, width 600 mm, height 750 mm, 18 mm boards, one shelf.',
                     material='plywood', thickness=18, joinery='interlocking')
    for needle in ('Modern Wooden Study Table', 'Length 1200 mm', 'Board thickness: 18 mm', FORMAT, 'X = length',
                   'Y = height', f"{TOL['contact']:g} mm", 'tab_slot', '```json', 'Return ONLY one'):
        assert needle in p, needle
    # the bundled example inside the spec is itself valid
    assert json.loads(spec_markdown().split('```json\n')[1].split('```')[0]) == EXAMPLE


# --- API ------------------------------------------------------------------------------------------

@pytest.fixture(scope='module')
def client(tmp_path_factory):
    import os
    os.environ.update(BOARD_INSTANCE_DIR=str(tmp_path_factory.mktemp('canvas')), BOARD_API_KEYS='ed:editor,vw:viewer',
                      BOARD_SKIP_SEED='1')
    import app as app_module
    importlib.reload(app_module)
    yield app_module.app.test_client()
    for k in ('BOARD_INSTANCE_DIR', 'BOARD_API_KEYS', 'BOARD_SKIP_SEED'):
        os.environ.pop(k, None)


ED, VW = {'Authorization': 'Bearer ed'}, {'Authorization': 'Bearer vw'}


def test_canvas_api_workflow(client):
    spec = client.get('/api/v1/canvas/spec').json
    assert spec['format'] == FORMAT and spec['example'] == EXAMPLE
    assert json.loads(spec['example_source']) == EXAMPLE and spec['example_source'].index('"format"') < spec['example_source'].index('"boards"')
    p = client.post('/api/v1/canvas/prompt', headers=VW, json={'title': 'Three-Door Wardrobe', 'requirements': '1800 x 2000 x 600'})
    assert p.status_code == 200 and 'Three-Door Wardrobe' in p.json['prompt']
    assert client.post('/api/v1/canvas/prompt', headers=VW, json={}).status_code == 400

    r = client.post('/api/v1/canvas/compile', headers=VW, json={'source': STUDY_TABLE_REPLY, 'production': False})
    assert r.status_code == 200 and r.json['ok'] and r.json['compiled'] and 'design' not in r.json
    assert len(r.json['model3d']['components']) == 4

    bad = client.post('/api/v1/canvas/compile', headers=VW, json={'source': '{"boards": ['}).json
    assert bad['ok'] and not bad['compiled'] and bad['diagnostics'][0]['code'] == 'JSON_SYNTAX'

    # save never overwrites: two saves -> two projects; the code is stored with the design
    assert client.post('/api/v1/canvas/save', headers=VW, json={'source': STUDY_TABLE_REPLY}).status_code == 403
    s1 = client.post('/api/v1/canvas/save', headers=ED, json={'source': STUDY_TABLE_REPLY}).json
    s2 = client.post('/api/v1/canvas/save', headers=ED, json={'source': STUDY_TABLE_REPLY, 'name': 'Copy'}).json
    assert s1['design_id'] != s2['design_id']
    saved = client.get(f"/api/v1/designs/{s1['design_id']}", headers=VW).json['design']
    assert saved['source']['code'] == STUDY_TABLE_REPLY and saved['source']['format'] == FORMAT
    # explicit update of a canvas design is allowed ...
    up = client.post('/api/v1/canvas/save', headers=ED, json={'source': json.dumps(EXAMPLE), 'design_id': s1['design_id']})
    assert up.status_code == 201 and up.json['design_id'] == s1['design_id']
    # ... but a project not made by the canvas is never overwritten
    client.post('/api/v1/designs', headers=ED, json={'id': 'manual', 'name': 'Manual project'})
    no = client.post('/api/v1/canvas/save', headers=ED, json={'source': json.dumps(EXAMPLE), 'design_id': 'manual'})
    assert no.status_code == 409
    assert client.post('/api/v1/canvas/save', headers=ED, json={'source': '{'}).status_code == 422

    # code-level fix via the API
    bad = copy.deepcopy(EXAMPLE)
    next(b for b in bad['boards'] if b['id'] == 'SHELF')['position'][0] = 69.5
    diag = next(d for d in client.post('/api/v1/canvas/compile', headers=VW, json={'source': json.dumps(bad), 'production': False})
                .json['diagnostics'] if d['code'] == 'CONNECTION_GAP')
    fixed = client.post('/api/v1/canvas/fix', headers=VW, json={'source': json.dumps(bad), 'fix': diag['fixes'][0]}).json
    assert client.post('/api/v1/canvas/compile', headers=VW, json={'source': fixed['source'], 'production': False}).json['compiled']


def _stream(client, source):
    r = client.post('/api/v1/canvas/compile-stream', headers=VW, json={'source': source, 'production': False})
    assert r.status_code == 200 and r.mimetype == 'application/x-ndjson'
    return [json.loads(line) for line in r.data.decode().splitlines()]


def _no_timestamps(res):
    for j in res.get('model3d', {}).get('joints', []):
        j.pop('joined_at', None)
    return res


def test_compile_stream_reports_real_stages_then_the_same_result(client):
    from board_api.routes import COMPILE_STAGES
    events = [e for e in _stream(client, json.dumps(EXAMPLE)) if e['type'] != 'heartbeat']
    progress, final = events[:-1], events[-1]
    assert final['type'] == 'result' and all(e['type'] == 'progress' for e in progress)
    order = [COMPILE_STAGES.index(e['stage']) for e in progress]
    assert order == sorted(order) and set(order) == set(range(len(COMPILE_STAGES)))      # every stage, in order
    assert all(0 <= e['done'] <= e['total'] for e in progress)
    plain = client.post('/api/v1/canvas/compile', headers=VW, json={'source': json.dumps(EXAMPLE), 'production': False}).json
    assert _no_timestamps(final['result']) == _no_timestamps(plain)


def test_compile_stream_stops_after_a_syntax_error(client):
    events = _stream(client, '{"boards": [')
    assert [e['type'] for e in events] == ['result']
    assert events[0]['result']['diagnostics'][0]['code'] == 'JSON_SYNTAX' and not events[0]['result']['compiled']


def test_compile_stream_is_cancelled_when_the_client_disconnects(client):
    import os
    import threading
    import time
    src = open(os.path.join(os.path.dirname(__file__), 'fixtures', 'village_house.json')).read()
    r = client.post('/api/v1/canvas/compile-stream', headers=VW, json={'source': src, 'production': False}, buffered=False)
    it = iter(r.response)
    assert json.loads(next(it))['type'] in ('progress', 'heartbeat')
    r.close()                                   # what the server sees when the browser aborts the request
    deadline = time.time() + 5
    while any(t.name == 'canvas-compile' for t in threading.enumerate()) and time.time() < deadline:
        time.sleep(0.05)
    assert not any(t.name == 'canvas-compile' for t in threading.enumerate())


def test_import_selected_boards_into_existing_design(client):
    client.post('/api/v1/designs', headers=ED, json={'id': 'host', 'name': 'Host', 'sheet': {'width': 2440, 'height': 1220}})
    r = client.post('/api/v1/canvas/import', headers=ED, json={'source': json.dumps(EXAMPLE), 'target': 'host',
                                                              'boards': ['TOP', 'LEG-L', 'LEG-R']})
    assert r.status_code == 200, r.json
    d = client.get('/api/v1/designs/host', headers=VW).json['design']
    assert {c['id'] for c in d['components']} == {'TOP', 'LEG-L', 'LEG-R'}
    assert len([j for j in d['joints'] if j['status'] == 'joined']) == 4      # 2 tabs per leg into the top
    again = client.post('/api/v1/canvas/import', headers=ED, json={'source': json.dumps(EXAMPLE), 'target': 'host',
                                                                  'boards': ['SHELF']})
    assert again.status_code == 200
    ids = {c['id'] for c in client.get('/api/v1/designs/host', headers=VW).json['design']['components']}
    assert 'SHELF' in ids


def test_format_docs_match_the_live_specification():
    import os
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'board-design-format.md')
    text = open(path).read()
    assert text.split('\n', 1)[1] == spec_markdown(), 'regenerate docs/board-design-format.md from spec_markdown()'


def test_large_user_design_compiles_quickly():
    """A real AI-generated design (21 boards, 49 connections -> 99 tab joints). It used to take ~146 s because
    every join re-validated the whole design; the canvas now validates once after all joins."""
    import os
    import time
    src = open(os.path.join(os.path.dirname(__file__), 'fixtures', 'village_house.json')).read()
    t = time.time()
    res = compile_source(src, run_production=False)
    elapsed = time.time() - t
    assert res['ok'], [d['message'] for d in res['diagnostics'] if d['severity'] == 'error']
    assert res['summary']['boards'] == 21 and res['summary']['joined'] == res['summary']['joints'] == 99
    assert res['validation']['valid'] and res['validation']['complete']
    assert elapsed < 30, f'compile took {elapsed:.1f} s'


def test_detect_non_integer_dimensions_and_prompt():
    from board_engine.canvas import find_non_integer_dimensions, compile_source
    from board_engine.canvas_prompt import build_integer_fix_prompt

    # 1. Design with floating-point dimensions
    bad_data = {
        'format': 'board-design/v1',
        'material': {'type': 'plywood', 'thickness': 1},
        'boards': [
            {'id': 'B1', 'size': [30.5, 38, 1], 'position': [0, 0, 0]},
            {'id': 'B2', 'size': [30, 38.2, 1], 'position': [0, 6.7, 0]}
        ]
    }
    issues = find_non_integer_dimensions(bad_data)
    assert len(issues) == 3
    assert any(i['field'] == 'size[0]' and i['board'] == 'B1' and i['value'] == 30.5 for i in issues)
    assert any(i['field'] == 'size[1]' and i['board'] == 'B2' and i['value'] == 38.2 for i in issues)
    assert any(i['field'] == 'position[1]' and i['board'] == 'B2' and i['value'] == 6.7 for i in issues)

    # 2. Prompt generation
    prompt = build_integer_fix_prompt('{}', issues)
    assert 'do NOT meet the integer millimetre requirement' in prompt
    assert 'Update the existing design ONLY for these specific dimensions' in prompt
    assert '30.5' in prompt and '38.2' in prompt

    # 3. Clean integer design has 0 issues
    clean_data = {
        'format': 'board-design/v1',
        'material': {'type': 'plywood', 'thickness': 1},
        'boards': [
            {'id': 'B1', 'size': [30, 38, 1], 'position': [0, 0, 0]},
            {'id': 'B2', 'size': [30, 38, 1], 'position': [0, 7, 0]}
        ]
    }
    assert find_non_integer_dimensions(clean_data) == []


def test_canvas_integer_fix_prompt_endpoint(client):
    import json
    src = json.dumps({
        'format': 'board-design/v1',
        'material': {'type': 'plywood', 'thickness': 1},
        'boards': [
            {'id': 'WALL', 'size': [30.2, 38, 1], 'position': [0, 0, 0]}
        ]
    })
    r = client.post('/api/v1/canvas/integer-fix-prompt', headers=VW, json={'source': src})
    assert r.status_code == 200
    res = r.json
    assert res['ok'] is True
    assert res['count'] >= 1
    assert 'Update the existing design ONLY for these specific dimensions' in res['prompt']

