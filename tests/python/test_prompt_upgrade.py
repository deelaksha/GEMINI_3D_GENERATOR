"""Every rule added to the AI prompt by the end-to-end validation is checked against the engine here."""
import json
import os

import pytest

from board_engine.canvas import compile_source
from board_engine.canvas_prompt import EXAMPLE, build_prompt, spec_markdown

P18 = {"type": "plywood", "thickness": 18}


def _c(boards, conns, **top):
    d = {"format": "board-design/v1", "product": {"name": "p"}, "material": top.pop('material', P18), "boards": boards,
         "connections": conns}
    d.update(top)
    return compile_source(json.dumps(d))


def _errs(r):
    return {d['code'] for d in r['diagnostics'] if d['severity'] == 'error'}


def test_prompt_states_the_new_rules():
    spec, prompt = spec_markdown(), build_prompt('Cabinet')
    for phrase in ('What this generator cannot build', 'at most 24 characters', "other board's mid-plane", '### Joint names',
                   'Support and stability', 'Offset them by at least 60 mm', 'twice the kerf', '"mounting"'):
        assert phrase in spec, phrase
    for phrase in ('Assumptions: …', 'SELF-CHECK', 'Is every board held?', 'number arrays on one line'):
        assert phrase in prompt, phrase


def test_claim_mitre_example_in_the_prompt_compiles():
    r = _c([{"id": "SIDE", "position": [0, 0, 0], "size": [18, 141, 200]}, {"id": "TOP", "position": [9, 132, 0], "size": [291, 18, 200]}],
           [{"id": "M", "type": "mitre", "board": "SIDE", "into": "TOP", "edge": "+y", "into_edge": "-x"}], joinery='glue_allowed')
    assert r['ok'] and r['design']['joints'][0]['status'] == 'joined'


def test_claim_mitre_drawn_to_the_outside_corner_is_rejected():
    r = _c([{"id": "SIDE", "position": [0, 0, 0], "size": [18, 150, 200]}, {"id": "TOP", "position": [0, 132, 0], "size": [300, 18, 200]}],
           [{"id": "M", "type": "mitre", "board": "SIDE", "into": "TOP", "edge": "+y", "into_edge": "-x"}], joinery='glue_allowed')
    assert 'EDGES_NOT_COINCIDENT' in _errs(r)


@pytest.mark.parametrize('dy, ok', [(0, False), (60, True)])
def test_claim_boards_tabbing_from_opposite_sides_must_be_offset(dy, ok):
    boards = [{"id": "BASE", "position": [0, 0, 0], "size": [600, 18, 300]}, {"id": "DIV", "position": [291, 18, 0], "size": [18, 400, 300]},
              {"id": "L", "position": [18, 200, 0], "size": [273, 18, 300]}, {"id": "R", "position": [309, 200 + dy, 0], "size": [273, 18, 300]},
              {"id": "SL", "position": [0, 18, 0], "size": [18, 400, 300]}, {"id": "SR", "position": [582, 18, 0], "size": [18, 400, 300]}]
    conns = [{"type": "tab_slot", "board": a, "into": b} for a, b in
             (("DIV", "BASE"), ("L", "DIV"), ("R", "DIV"), ("L", "SL"), ("R", "SR"))] + \
            [{"type": "finger", "board": "SL", "into": "BASE"}, {"type": "finger", "board": "SR", "into": "BASE"}]
    r = _c(boards, conns)
    assert r['ok'] == ok and (ok or 'SLOT_ALREADY_USED' in _errs(r))


@pytest.mark.parametrize('name, ok', [('dovetail', True), ('box_joint', True), ('dado', False), ('rabbet', False), ('cam_lock', False)])
def test_claim_joint_names(name, ok):
    r = _c([{"id": "BASE", "position": [0, 0, 0], "size": [300, 18, 200]}, {"id": "WALL", "position": [0, 18, 0], "size": [18, 150, 200]}],
           [{"id": "J", "type": name, "board": "WALL", "into": "BASE"}])
    assert r['ok'] == ok
    if ok:
        assert {j['type'] for j in r['design']['joints']} == {'finger'}


def test_claim_parallel_faces_cannot_be_joined():
    boards = [{"id": "TOP", "position": [0, 0, 0], "size": [400, 18, 300]}, {"id": "TRAY", "position": [50, -18, 50], "size": [300, 18, 200]}]
    for t in ('tab_slot', 'butt'):
        assert 'NO_CONTACT' in _errs(_c(boards, [{"id": "J", "type": t, "board": "TRAY", "into": "TOP"}], joinery='glue_allowed'))


def test_claim_board_held_by_nothing_is_an_error_but_a_resting_one_is_not():
    d = json.loads(json.dumps(EXAMPLE))
    d['boards'].append({"id": "BOX", "position": [300, 750, 200], "size": [200, 18, 150]})        # lies on the top
    d['product']['overall']['height'] += 18
    r = compile_source(json.dumps(d))
    assert r['ok'] and r['support']['components']['BOX']['status'] == 'resting'
    d['boards'][-1]['position'][1] = 900                                                           # in mid-air
    assert 'ISOLATED_BOARD' in _errs(compile_source(json.dumps(d)))


def test_repair_prompt_carries_the_diagnostics_and_the_source():
    from board_engine.canvas_prompt import build_repair_prompt
    bad = json.loads(json.dumps(EXAMPLE))
    for b in bad['boards']:
        if b['id'].startswith('LEG'):
            b['size'][1] = 750
    src = json.dumps(bad, indent=2)
    r = compile_source(src)
    p = build_repair_prompt(src, r['diagnostics'])
    assert p.count('CONNECTION_OVERLAP') == 2 and 'Suggested fix:' in p and '"LEG-L"' in p and 'keep every other board' in p


def test_update_prompt_asks_for_a_minimal_change():
    from board_engine.canvas_prompt import build_update_prompt
    p = build_update_prompt(json.dumps(EXAMPLE), 'Make the table 200 mm wider.')
    assert 'Make the table 200 mm wider.' in p and 'Change only those' in p and '"TOP"' in p


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    os.environ.update(BOARD_INSTANCE_DIR=str(tmp_path_factory.mktemp('prompt')), BOARD_API_KEYS='vw:viewer', BOARD_SKIP_SEED='1')
    import importlib
    import app as appmod
    importlib.reload(appmod)
    yield appmod.app.test_client()
    for k in ('BOARD_INSTANCE_DIR', 'BOARD_API_KEYS', 'BOARD_SKIP_SEED'):
        os.environ.pop(k, None)


def test_repair_and_update_prompt_endpoints(client):
    h = {'Authorization': 'Bearer vw'}
    r = client.post('/api/v1/canvas/repair-prompt', headers=h, json={'source': '{"boards": [ oops'})     # stops mid-design
    assert r.status_code == 200 and 'JSON_TRUNCATED' in r.json['prompt'] and 'CUT OFF' in r.json['prompt'] and r.json['problems'] == 1
    r = client.post('/api/v1/canvas/update-prompt', headers=h, json={'source': json.dumps(EXAMPLE), 'change': 'Add a second shelf.'})
    assert r.status_code == 200 and 'Add a second shelf.' in r.json['prompt']
    assert client.post('/api/v1/canvas/update-prompt', headers=h, json={'source': json.dumps(EXAMPLE)}).status_code == 400


def test_repair_prompt_groups_repeats_instead_of_truncating():
    # found by the AI experiment: a 40-line cut-off hid problems from the AI ("… and 10 more")
    from board_engine.canvas_prompt import build_repair_prompt
    diags = [{'severity': 'error', 'code': 'TOOL_ACCESS_BLOCKED', 'message': f'screw {i} blocked', 'board': 'D1-BOT'} for i in range(30)]
    diags += [{'severity': 'error', 'code': f'OTHER_{i}', 'message': f'problem {i}', 'board': f'B{i}'} for i in range(20)]
    p = build_repair_prompt('{}', diags)
    assert p.count('\n- [') == 21 and '(and 29 more like this)' in p and 'more distinct problems' not in p


def test_every_prompt_demands_code_only():
    """AIs answered the fix prompt with explanations: every prompt states the output contract up front, repeats it
    as its last line, and the follow-ups carry the specification so they also work in a fresh chat."""
    from board_engine.canvas_prompt import (FINAL_REMINDER, OUTPUT_CONTRACT, build_integer_fix_prompt, build_repair_prompt,
                                            build_update_prompt)
    bad = json.loads(json.dumps(EXAMPLE))
    next(b for b in bad['boards'] if b['id'] == 'LEG-R')['position'][1] = -6
    src = json.dumps(bad, indent=2)
    diags = compile_source(src)['diagnostics']
    prompts = {'generate': build_prompt('Cabinet'), 'repair': build_repair_prompt(src, diags),
               'integer': build_integer_fix_prompt(src, [{'board': 'TOP', 'field': 'size[0]', 'value': 1200.4, 'suggested': 1200,
                                                          'message': 'x'}]),
               'update': build_update_prompt(src, 'Add a second shelf.')}
    for name, p in prompts.items():
        assert OUTPUT_CONTRACT in p and p.index(OUTPUT_CONTRACT) < 1200, name          # stated before the task details
        assert p.rstrip().endswith(FINAL_REMINDER), name                               # and as the very last line
    for name in ('generate', 'repair', 'update'):
        assert spec_markdown() in prompts[name], name
    # suggested fixes carry the exact values the compiler computed
    assert 'boards["LEG-R"].position = [1132, 0, 20]' in prompts['repair'] or 'boards["LEG-R"].size' in prompts['repair']
    assert 'boards["TOP"].size[0]: 1200.4 → 1200' in prompts['integer']
