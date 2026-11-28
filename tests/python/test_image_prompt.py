"""Reference images: the user attaches them in their AI chat; the prompts make them the specification."""
import importlib
import json
import os

import pytest

from board_engine.canvas_prompt import FINAL_REMINDER, IMAGE_SPEC, build_update_prompt
from board_engine.canvas_prompt import build_prompt as _build_prompt


def build_prompt(*a, **kw):
    """These tests pin the content of the full (long) prompt; the lean default is tested in test_prompt_lean.py."""
    return _build_prompt(*a, **dict(kw, style='full'))


def test_off_by_default_and_unchanged():
    p = build_prompt('Toy house', thickness=6)
    assert 'Reference images' not in p and 'attached image' not in p


def test_generation_prompt_makes_the_images_the_specification():
    p = build_prompt('', 'Height 300 mm', thickness=6, images=True)
    assert 'PRODUCT: The product shown in the attached image(s)' in p
    assert IMAGE_SPEC in p and p.index(IMAGE_SPEC) > p.index('## ')            # appended after the specification
    assert 'follow the text, on anything else the image' in p                   # sizes from text, the rest from the image
    assert 'h. PROJECTION CHECK: does the design match the attached image(s)' in p    # self-check item
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
    """The tilted-panel snippet the AI is told to copy must itself be a working tilted panel + truss + tile."""
    from board_engine.canvas import compile_source
    from board_engine.canvas_prompt import spec_markdown
    md = spec_markdown()
    sn = md[md.index('Snippet (a tilted panel'):]
    sn = sn[sn.index('```jsonc') + 8: sn.index('```', sn.index('```jsonc') + 8)]
    parts = json.loads('[' + sn.strip() + ']')
    d = {'format': 'board-design/v1', 'product': {'name': 's'}, 'material': {'type': 'plywood', 'thickness': 3, 'kerf': 0.15},
         'boards': [{'id': 'BELOW', 'position': [30, 78, 63], 'size': [300, 3, 180]}] + parts,
         'connections': [{'id': 'a', 'type': 'tab_slot', 'board': 'SUPPORT-1', 'into': 'BELOW', 'tabs': 1, 'tab_width': 12},
                         {'id': 'b', 'type': 'tab_slot', 'board': 'SUPPORT-1', 'into': 'PANEL-1', 'tabs': 1, 'tab_width': 10},
                         {'id': 'c', 'type': 'tab_slot', 'board': 'PIECE-1', 'into': 'PANEL-1', 'tabs': 1, 'tab_width': 8}]}
    r = compile_source(json.dumps(d), run_production=False)
    assert r['ok'] and r['summary']['joined'] == 3 and not [x for x in r['diagnostics'] if x['severity'] in ('error', 'warning')]


def test_production_blockers_reach_the_fix_prompt_with_their_full_count(client):
    """A design that compiles clean but cannot be cut (parts below the router minimum) must still get a fix prompt,
    and when more than 50 parts are affected the prompt says how many more there are."""
    h = {'Authorization': 'Bearer vw'}
    ribs = [{'id': f'RIB{i}', 'position': [10 + 12 * i, 6, 20], 'size': [6, 8, 40]} for i in range(60)]
    d = {'format': 'board-design/v1', 'product': {'name': 'ribs'}, 'material': {'type': 'plywood', 'thickness': 6},
         'boards': [{'id': 'BASE', 'position': [0, 0, 0], 'size': [740, 6, 80]}] + ribs,
         'connections': [{'id': f'r{i}', 'type': 'tab_slot', 'board': f'RIB{i}', 'into': 'BASE', 'tabs': 1, 'tab_width': 6}
                         for i in range(60)]}
    r = client.post('/api/v1/canvas/compile', headers=h, json={'source': json.dumps(d), 'repair_prompt': True}).json
    lay = r['layout']
    assert not lay['ready_for_production'] and lay['blocking_total'] >= 60 and len(lay['blocking_issues']) == 50
    assert 'PART_BELOW_MIN_SIZE' in r['repair_prompt'] and 'more production problem(s)' in r['repair_prompt']


def test_every_generation_prompt_carries_the_precision_and_realism_rules():
    from board_engine.canvas_prompt import FIDELITY_OVERRIDE, PRECISION_PROTOCOL, REALISM_PLAYBOOK
    p = build_prompt('Clock tower', thickness=3)
    assert PRECISION_PROTOCOL in p and REALISM_PLAYBOOK in p and '"datums"' in p and 'NUMERIC SELF-AUDIT' in p
    assert FIDELITY_OVERRIDE not in p                                   # free design: creativity is wanted


def test_with_images_fidelity_beats_creativity_and_the_clone_is_measured():
    from board_engine.canvas_prompt import DESIGN_QUALITY, FIDELITY_OVERRIDE
    p = build_prompt('', 'Width 400 mm', thickness=3, images=True)
    assert p.index(FIDELITY_OVERRIDE) > p.index(DESIGN_QUALITY)         # read after (and over) the creativity rules
    for step in ('CALIBRATE THE SCALE', 'MEASURE ON A GRID', 'TRACE THE OUTLINES', 'PROJECTION CHECK', 'within 2%'):
        assert step in IMAGE_SPEC, step
    assert 'METROLOGIST' in p and 'PROJECTION CHECK' in p
    upd = build_update_prompt('{"boards": []}', '', images=True)
    assert FIDELITY_OVERRIDE in upd and IMAGE_SPEC in upd


def test_explicit_numbers_become_hard_constraints():
    from board_engine.canvas_prompt import hard_constraints
    h = hard_constraints('Overall width 400 mm, height 35 cm, scale 1:50, 12 columns, highly detailed, doors that open')
    for want in ('Overall width: 400 mm', 'height: 350 mm', 'model scale 1:50', 'columns: exactly 12', 'detail level: 5',
                 'movement'):
        assert want in h, want
    assert hard_constraints('') == '' and 'HARD CONSTRAINTS' in build_prompt('Pagoda', 'height 600 mm')
    assert 'HARD CONSTRAINTS' in build_update_prompt('{}', 'make it 500 mm wide')


def test_the_repair_prompt_names_the_likely_root_causes():
    from board_engine.canvas_prompt import build_repair_prompt
    diags = [{'severity': 'error', 'code': c, 'message': 'x', 'board': 'ROOF-L'} for c in ('COLLISION', 'CONNECTION_GAP', 'TAB_IN_OPENING')]
    diags.append({'severity': 'error', 'code': 'COLLISION', 'message': 'y', 'board': 'WALL'})
    p = build_repair_prompt('{}', diags)
    assert 'LIKELY ROOT CAUSES' in p and '- ROOF-L: 3 problems' in p and '- WALL:' not in p


def test_the_advanced_example_compiles_clean_and_shows_the_working_method():
    import json as _json
    from board_engine import canvas
    from board_engine.canvas_prompt import ADVANCED_EXAMPLE, spec_markdown
    r = canvas.compile_source(_json.dumps(ADVANCED_EXAMPLE), run_production=False, machine={'coloring': True})
    assert r['ok'] and not [d for d in r['diagnostics'] if d['severity'] in ('error', 'warning')]
    assert set(ADVANCED_EXAMPLE['plan']) >= {'reference', 'datums', 'checks'} and 'a framed structure cloned from a reference' in spec_markdown()
    assert not r['structure']['held_by_friction'] and not r['structure']['can_fall_out']


def test_the_worked_superellipse_points_are_right():
    import math
    import re as _re
    from board_engine.canvas_prompt import PRECISION_PROTOCOL
    for deg, u, v in _re.findall(r'(\d+) -> \((\d+), (\d+)\)', PRECISION_PROTOCOL.replace('t 0', '0')):
        t = math.radians(int(deg))
        c, s = math.cos(t), math.sin(t)
        assert (round(60 + 60 * math.copysign(abs(c) ** 0.8, c)), round(40 + 40 * math.copysign(abs(s) ** 0.8, s))) == (int(u), int(v))


def test_red_team_and_failure_patterns_are_in_the_prompt():
    from board_engine.canvas_prompt import ANTI_PATTERNS
    p = build_prompt('Pagoda', thickness=3)
    assert ANTI_PATTERNS in p and 'RED TEAM' in p


def test_the_plan_layout_asks_for_joints_and_a_written_audit():
    from board_engine.canvas_prompt import ADVANCED_EXAMPLE
    p = build_prompt('Pagoda', thickness=3)
    assert '"joints": one line per sub-assembly' in p and '"audit": at least 10 boards recomputed' in p
    assert {'joints', 'audit'} <= set(ADVANCED_EXAMPLE['plan'])
    assert 'a size seen in\n   two views' in IMAGE_SPEC


def test_the_method_is_universal_not_tied_to_a_subject():
    from board_engine.canvas_prompt import SIGNS_OF_LIFE, UNIVERSAL_METHOD
    prompts = [build_prompt(t, thickness=3) for t in ('Japanese temple', 'Mechanical dragon', 'Desk lamp',
                                                      'Something nobody has made before')]
    for p in prompts:                                   # every subject gets the same full method
        assert UNIVERSAL_METHOD in p and SIGNS_OF_LIFE in p and 'IDENTITY FIRST' in p
    for form in ('FLAT PARTS', 'BOX VOLUMES', 'FRAMES AND SKELETONS', 'SMOOTH AND ORGANIC VOLUMES', 'TAPERING AND SEGMENTED',
                 'REPEATED ELEMENTS', 'SHELLS AND SWEEPS', 'SURFACE DETAIL', 'MOVING PARTS'):
        assert form in UNIVERSAL_METHOD, form
    assert 'RECIPE - ' not in prompts[0] and 'GESTURE' in SIGNS_OF_LIFE and 'NATURAL VARIATION' in SIGNS_OF_LIFE
    # a plain change keeps to precision (audit P-16: the creative blocks invited a redesign); asking for more detail
    # or a new look brings the method back
    assert UNIVERSAL_METHOD not in build_update_prompt('{}', 'add a balcony')
    assert UNIVERSAL_METHOD in build_update_prompt('{}', 'make it more detailed and realistic')


def test_the_creative_brief_and_scope_work_for_any_title():
    from board_engine.canvas_prompt import creative_brief, scope
    for title in ('Pagoda', 'A gift for my sister', 'Clock'):
        b = creative_brief(title)
        assert 'Identity:' in b and 'Life:' in b and b.count(' | ') == 2 and creative_brief(title) == b
    assert creative_brief('Pagoda') != creative_brief('Clock')          # different titles, different directions
    assert creative_brief('Pagoda', images=True) == ''                  # with a reference, the reference is the brief
    assert 'multi-part' in scope('x') and 'script' in scope('x', machine={'file': True})
    p = build_prompt('Pagoda')
    assert 'CREATIVE BRIEF' in p and 'museum quality' in p and 'SCOPE:' in p
    assert 'CREATIVE BRIEF' not in build_prompt('', images=True)



def test_nothing_in_the_prompt_is_tied_to_one_kind_of_object():
    import re as _re
    p = build_prompt('Anything', thickness=3, images=True, machine={'coloring': True})
    for word in ('torii', 'pagoda', 'temple', 'nuki', 'kasagi', 'podium', 'rafter tails', 'bracket sets', 'eave sweeps'):
        assert not _re.search(word, p, _re.I), word


def test_the_geometry_card_contact_equations_hold_for_every_working_joint():
    """The card's tab_slot equation is exactly what the bundled examples (which compile clean) satisfy."""
    from board_engine.canvas_prompt import ADVANCED_EXAMPLE, COMPLEX_EXAMPLE, EXAMPLE, STRUCTURES_EXAMPLE
    checked = 0
    for d in (EXAMPLE, COMPLEX_EXAMPLE, STRUCTURES_EXAMPLE, ADVANCED_EXAMPLE):
        t = d['material']['thickness']
        boards = {b['id']: b for b in d['boards']}
        for c in d['connections']:
            a, b = boards.get(c.get('board')), boards.get(c.get('into'))
            if c.get('type', 'tab_slot') != 'tab_slot' or not a or not b or b.get('rotate') or a.get('rotate'):
                continue
            k = next(i for i in range(3) if abs(b['size'][i] - b.get('thickness', t)) < 0.01)
            plus = a['position'][k] == b['position'][k] + b['size'][k]
            minus = a['position'][k] + a['size'][k] == b['position'][k]
            assert plus or minus, (c, k)
            checked += 1
    assert checked >= 10


def test_the_prompt_carries_the_geometry_card_joint_table_and_assembly_order():
    from board_engine.canvas_prompt import ASSEMBLY_ORDER, GEOMETRY_CARD, JOINT_DECISION, build_repair_prompt
    p = build_prompt('Anything', thickness=3)
    assert GEOMETRY_CARD in p and JOINT_DECISION in p and ASSEMBLY_ORDER in p and 'SCORE the design 1-5' in p
    assert GEOMETRY_CARD in build_repair_prompt('{}', []) and GEOMETRY_CARD in build_update_prompt('{}', 'x')
    assert 'is 66-90 mm from the object' in IMAGE_SPEC
