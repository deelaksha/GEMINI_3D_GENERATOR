"""Reference images: the user attaches them in their AI chat; the prompts make them the specification."""
import importlib
import json
import os

import pytest

from board_engine.canvas_prompt import FINAL_REMINDER, IMAGE_SPEC, build_prompt, build_update_prompt


def test_off_by_default_and_unchanged():
    p = build_prompt('Toy house', thickness=6)
    assert 'Reference images' not in p and 'attached image' not in p


def test_generation_prompt_makes_the_images_the_specification():
    p = build_prompt('', 'Height 300 mm', thickness=6, images=True)
    assert 'PRODUCT: The product shown in the attached image(s)' in p
    assert IMAGE_SPEC in p and p.index(IMAGE_SPEC) > p.index('## ')            # appended after the specification
    assert 'follow the text, on anything else the image' in p                   # sizes from text, the rest from the image
    assert 'h. Does the design match the attached image(s)' in p                # self-check item
    assert '"reference"' in p and p.rstrip().endswith(FINAL_REMINDER.rstrip())      # the strict reminder stays last


def test_change_prompt_with_images_and_no_text():
    src = json.dumps({'format': 'board-design/v1', 'product': {'name': 'x'}, 'material': {'type': 'plywood', 'thickness': 6},
                      'boards': [{'id': 'A', 'position': [0, 0, 0], 'size': [100, 6, 100]}], 'connections': []})
    p = build_update_prompt(src, '', images=True)
    assert 'Make the design match the attached reference image(s) exactly.' in p and 'REFERENCE IMAGES:' in p and IMAGE_SPEC in p
    assert 'REFERENCE IMAGES' not in build_update_prompt(src, 'Add a shelf')


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    os.environ.update(BOARD_INSTANCE_DIR=str(tmp_path_factory.mktemp('img')), BOARD_API_KEYS='vw:viewer', BOARD_SKIP_SEED='1')
    import app as app_module
    importlib.reload(app_module)
    yield app_module.app.test_client()
    for k in ('BOARD_INSTANCE_DIR', 'BOARD_API_KEYS', 'BOARD_SKIP_SEED'):
        os.environ.pop(k, None)


def test_routes(client):
    h = {'Authorization': 'Bearer vw'}
    assert client.post('/api/v1/canvas/prompt', headers=h, json={'title': ''}).status_code == 400
    r = client.post('/api/v1/canvas/prompt', headers=h, json={'title': '', 'images': True})
    assert r.status_code == 200 and 'Reference images' in r.json['prompt']
    src = json.dumps({'format': 'board-design/v1', 'product': {'name': 'x'}, 'material': {'type': 'plywood', 'thickness': 6},
                      'boards': [{'id': 'A', 'position': [0, 0, 0], 'size': [100, 6, 100]}], 'connections': []})
    assert client.post('/api/v1/canvas/update-prompt', headers=h, json={'source': src, 'change': ''}).status_code == 400
    r = client.post('/api/v1/canvas/update-prompt', headers=h, json={'source': src, 'change': '', 'images': True,
                                                                     'machine': {'coloring': True}})
    assert r.status_code == 200 and 'REFERENCE IMAGES' in r.json['prompt'] and '## Colours' in r.json['prompt']


def test_my_home_example_is_served_and_compiles_clean(client):
    from board_engine.canvas import compile_source
    h = {'Authorization': 'Bearer vw'}
    assert client.get('/api/v1/canvas/examples/nope', headers=h).status_code == 404
    r = client.get('/api/v1/canvas/examples/home', headers=h)
    assert r.status_code == 200
    res = compile_source(r.json['source'], run_production=False, time_budget=120, machine={'coloring': True})
    assert res['ok'] and res['summary']['boards'] >= 300 and res['summary']['joined'] == res['summary']['joints']
    assert not [d for d in res['diagnostics'] if d['severity'] in ('error', 'warning')]


def test_detailed_models_snippet_in_the_spec_compiles():
    """The roof snippet the AI is told to copy must itself be a working tilted panel + truss + tile."""
    from board_engine.canvas import compile_source
    from board_engine.canvas_prompt import spec_markdown
    md = spec_markdown()
    sn = md[md.index('Snippet (front roof slope'):]
    sn = sn[sn.index('```jsonc') + 8: sn.index('```', sn.index('```jsonc') + 8)]
    parts = json.loads('[' + sn.strip() + ']')
    d = {'format': 'board-design/v1', 'product': {'name': 's'}, 'material': {'type': 'plywood', 'thickness': 3, 'kerf': 0.15},
         'boards': [{'id': 'CEILING', 'position': [30, 78, 63], 'size': [300, 3, 180]}] + parts,
         'connections': [{'id': 'a', 'type': 'tab_slot', 'board': 'TRUSS-1', 'into': 'CEILING', 'tabs': 1, 'tab_width': 12},
                         {'id': 'b', 'type': 'tab_slot', 'board': 'TRUSS-1', 'into': 'R-F', 'tabs': 1, 'tab_width': 10},
                         {'id': 'c', 'type': 'tab_slot', 'board': 'TILE-F1', 'into': 'R-F', 'tabs': 1, 'tab_width': 8}]}
    r = compile_source(json.dumps(d), run_production=False)
    assert r['ok'] and r['summary']['joined'] == 3 and not [x for x in r['diagnostics'] if x['severity'] in ('error', 'warning')]
