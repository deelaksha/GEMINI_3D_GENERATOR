"""Colouring (toggle on / off) and structure helpers (repeat, mirror, assemblies, plan)."""
import copy
import importlib
import io
import json
import zipfile

import pytest

from board_engine.canvas import compile_source
from board_engine.colors import color_name, parse_color

OFF = {'kerf': 0.15, 'sheet': {'width': 600, 'height': 400}}
ON = dict(OFF, coloring=True)
HOUSE = {'format': 'board-design/v1', 'product': {'name': 'Toy house'},
         'material': {'type': 'plywood', 'thickness': 6, 'color': 'ivory'},
         'boards': [{'id': 'BASE', 'position': [0, 0, 0], 'size': [200, 6, 150], 'color': 'forestgreen'},
                    {'id': 'WALL', 'position': [30, 6, 60], 'size': [140, 80, 6],
                     'color': {'front': 'rgb(220, 20, 60)', 'back': '#fff', 'edges': [40, 40, 40]}},
                    {'id': 'POST', 'position': [100, 6, 20], 'size': [6, 50, 30]}],
         'connections': [{'id': 'W-B', 'type': 'tab_slot', 'board': 'WALL', 'into': 'BASE', 'tabs': 2},
                         {'id': 'P-B', 'type': 'tab_slot', 'board': 'POST', 'into': 'BASE', 'tabs': 1}]}


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    import os
    os.environ.update(BOARD_INSTANCE_DIR=str(tmp_path_factory.mktemp('color')), BOARD_API_KEYS='ed:editor,vw:viewer',
                      BOARD_SKIP_SEED='1')
    import app as app_module
    importlib.reload(app_module)
    yield app_module.app.test_client()
    for k in ('BOARD_INSTANCE_DIR', 'BOARD_API_KEYS', 'BOARD_SKIP_SEED'):
        os.environ.pop(k, None)


VW = {'Authorization': 'Bearer vw'}


# --- colours --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('value, hexc', [('#F00', '#ff0000'), ('#ff634780', '#ff6347'), ('rgb(255, 99, 71)', '#ff6347'),
                                         ('rgba(255,99,71,.5)', '#ff6347'), ('rgb(100% 0% 0%)', '#ff0000'),
                                         ('hsl(120, 100%, 25%)', '#008000'), (' Navy ', '#000080'), ([255, 99, 71], '#ff6347'),
                                         ({'r': 0, 'g': 0, 'b': 255}, '#0000ff'), ('walnut', '#5d432c')])
def test_colour_formats(value, hexc):
    assert parse_color(value) == hexc


def test_bad_colours_and_names():
    for bad in ('blurple', 'rgb(1, 2)', [300, 0, 0], True, None):
        with pytest.raises(ValueError):
            parse_color(bad)
    assert color_name('#ff6347') == 'tomato' and color_name('#fe6347') == 'tomato-ish'


def test_colouring_off_works_as_before():
    r = compile_source(json.dumps(HOUSE), machine=OFF)
    assert r['ok'] and not r.get('painting')
    assert 'COLORS_IGNORED' in {d['code'] for d in r['diagnostics']}
    assert all(not c.get('colors') for c in r['model3d']['components'])
    plain = compile_source(json.dumps(HOUSE), machine=OFF)['design']
    assert 'coloring' not in plain and all('color' not in p for p in compile_source(json.dumps(HOUSE), machine=OFF)['layout']['nesting']['placements'])


def test_colouring_on_faces_defaults_guide_and_outputs():
    r = compile_source(json.dumps(HOUSE), machine=ON)
    assert r['ok'] and r['layout']['ready_for_production']
    comps = {c['id']: c for c in r['model3d']['components']}
    assert comps['BASE']['colors'] == {'front': '#228b22', 'back': '#228b22', 'edges': '#228b22'}
    assert comps['WALL']['colors'] == {'front': '#dc143c', 'back': '#ffffff', 'edges': '#282828'}
    assert comps['POST']['colors']['front'] == parse_color('ivory')            # the material's default colour
    guide = {c['color']: c for c in r['painting']['colors']}
    assert guide['#dc143c']['parts'] == [{'id': 'WALL', 'faces': ['front']}] and guide['#dc143c']['name'] == 'crimson'
    assert guide['#228b22']['area_m2'] > 2 * 0.2 * 0.15 * 0.9                 # both faces of the 200 x 150 base
    lines = {ln['part']: ln for ln in r['cut_list']['lines']}
    assert lines['WALL']['colors']['back'] == '#ffffff'
    assert {p['color'] for p in r['layout']['nesting']['placements']} == {'#228b22', '#dc143c', parse_color('ivory')}
    sheet_preview = [b for b in compile_source(json.dumps(HOUSE), run_production=False, machine=ON)['design']['components']]
    assert all(b.get('colors') for b in sheet_preview)


def test_colour_sorted_sheets():
    together = compile_source(json.dumps(HOUSE), machine=ON)['layout']['nesting']
    sorted_ = compile_source(json.dumps(HOUSE), machine=dict(ON, color_sheets=True))['layout']['nesting']
    assert together['sheet_count'] == 1 and sorted_['sheet_count'] == 3
    assert {s['stock'].get('color') for s in sorted_['sheets']} == {'#228b22', '#dc143c', parse_color('ivory')}
    assert not sorted_['issues']
    by_sheet = {}
    for p in sorted_['placements']:
        by_sheet.setdefault(p['sheet'], set()).add(p['color'])
    assert all(len(c) == 1 for c in by_sheet.values())                       # one colour per sheet


def test_invalid_colour_is_an_error():
    d = copy.deepcopy(HOUSE)
    d['boards'][0]['color'] = 'blurple'
    r = compile_source(json.dumps(d), run_production=False, machine=ON)
    assert 'COLOR_INVALID' in {x['code'] for x in r['diagnostics'] if x['severity'] == 'error'}


def test_prompts_and_readme_follow_the_toggle(client):
    off = client.post('/api/v1/canvas/prompt', headers=VW, json={'title': 'Toy house', 'machine': OFF}).json['prompt']
    on = client.post('/api/v1/canvas/prompt', headers=VW, json={'title': 'Toy house', 'machine': ON}).json['prompt']
    assert '## Colours' not in off and '## Colours' in on and 'unique colours' in on
    bad = copy.deepcopy(HOUSE)
    bad['boards'][1]['position'][1] = 10
    rep = client.post('/api/v1/canvas/repair-prompt', headers=VW, json={'source': json.dumps(bad), 'machine': ON}).json['prompt']
    assert '## Colours' in rep and 'keep every board\'s colour' in rep
    upd = client.post('/api/v1/canvas/update-prompt', headers=VW,
                      json={'source': json.dumps(HOUSE), 'change': 'Add a chimney', 'machine': ON}).json['prompt']
    assert '## Colours' in upd
    z = zipfile.ZipFile(io.BytesIO(client.post('/api/v1/canvas/export', headers=VW,
                                               json={'source': json.dumps(HOUSE), 'machine': dict(ON, color_sheets=True)}).data))
    readme = z.read(next(n for n in z.namelist() if n.endswith('README.txt'))).decode()
    assert 'Painting   :' in readme and 'crimson #dc143c' in readme
    assert len([n for n in z.namelist() if n.endswith('.svg') and '-sheet' in n]) == 3


# --- structure helpers ------------------------------------------------------------------------------------------

UNIT = {'format': 'board-design/v1', 'product': {'name': 'Shelf unit'}, 'material': {'type': 'plywood', 'thickness': 6},
        'plan': {'assemblies': ['carcass'], 'steps': ['base', 'sides', 'shelves'], 'checks': ['symmetry']},
        'boards': [{'id': 'BASE', 'position': [-20, 0, 0], 'size': [440, 6, 200]},
                   {'id': 'SIDE', 'position': [0, 6, 20], 'size': [6, 300, 160], 'mirror': {'axis': 'x', 'at': 200}},
                   {'id': 'SHELF', 'position': [6, 60, 30], 'size': [388, 6, 120], 'repeat': {'count': 4, 'step': [0, 60, 0]}}],
        'connections': [{'id': 'S-B', 'type': 'tab_slot', 'board': 'SIDE', 'into': 'BASE', 'tabs': 2},
                        {'id': 'SH-S', 'type': 'tab_slot', 'board': 'SHELF', 'into': 'SIDE', 'tabs': 1}]}


def test_repeat_and_mirror():
    r = compile_source(json.dumps(UNIT), run_production=False)
    ids = [c['id'] for c in r['model3d']['components']]
    assert ids == ['BASE', 'SIDE', 'SIDE-M', 'SHELF-1', 'SHELF-2', 'SHELF-3', 'SHELF-4']
    assert r['ok'] and r['summary']['joined'] == r['summary']['joints'] == 12   # mirrored + repeated joints all hold
    side_m = next(c for c in r['model3d']['components'] if c['id'] == 'SIDE-M')
    assert side_m['world_bounds']['min'][0] == pytest.approx(394, abs=0.01)    # 2 * 200 - (0 + 6)


def test_assemblies_and_instances():
    d = {'format': 'board-design/v1', 'product': {'name': 'Two trays'}, 'material': {'type': 'plywood', 'thickness': 6},
         'assemblies': [{'id': 'TRAY', 'boards': [{'id': 'BOT', 'position': [0, 0, 0], 'size': [120, 6, 80]},
                                                  {'id': 'SIDE', 'position': [20, 6, 30], 'size': [80, 40, 6]}],
                         'connections': [{'id': 'J', 'type': 'tab_slot', 'board': 'SIDE', 'into': 'BOT', 'tabs': 1}]}],
         'instances': [{'assembly': 'TRAY', 'id': 'T1', 'offset': [0, 0, 0]}, {'assembly': 'TRAY', 'id': 'T2', 'offset': [200, 0, 0]}],
         'boards': [], 'connections': []}
    r = compile_source(json.dumps(d), run_production=False)
    assert sorted(c['id'] for c in r['model3d']['components']) == ['T1-BOT', 'T1-SIDE', 'T2-BOT', 'T2-SIDE']
    assert r['summary']['joined'] == 2 and {c['group'] for c in r['model3d']['components']} == {'T1', 'T2'}


def test_generated_ids_point_at_the_source_line():
    d = copy.deepcopy(UNIT)
    d['boards'][2]['size'][1] = 5                                            # shelf thickness wrong: error on every copy
    src = json.dumps(d, indent=2)
    r = compile_source(src, run_production=False)
    errs = [x for x in r['diagnostics'] if x['code'] == 'THICKNESS_MISMATCH']
    line = src.splitlines().index(next(l for l in src.splitlines() if '"SHELF"' in l)) + 1
    assert len(errs) == 4 and {e['line'] for e in errs} == {line}


@pytest.mark.parametrize('patch, word', [({'repeat': {'count': 1, 'step': [0, 1, 0]}}, 'repeat'),
                                         ({'mirror': {'axis': 'w', 'at': 0}}, 'mirror')])
def test_structure_mistakes(patch, word):
    d = copy.deepcopy(UNIT)
    d['boards'][0].update(patch)
    r = compile_source(json.dumps(d), run_production=False)
    errs = [x for x in r['diagnostics'] if x['code'] == 'STRUCTURE_INVALID']
    assert errs and word in errs[0]['message']


def test_resize_expands_the_structure_first():
    from board_engine.resize import resize_design
    new, ext = resize_design(UNIT, {'length': 500})
    assert ext['length'] == 500 and len(new['boards']) == 7 and not any('repeat' in b or 'mirror' in b for b in new['boards'])
    assert compile_source(json.dumps(new), run_production=False)['ok']
