"""Product completeness (audit 2026-11-28, phase 5): a design brief names the product's components and closed
enclosures; boards name their component with "role"; the compiler reports missing components and open sides, and
never flags a declared opening or an open side the brief allows."""
import copy
import json

import pytest

from board_engine.brief import validate_brief
from board_engine.canvas import compile_source
from board_engine.canvas_prompt import COMPLEX_EXAMPLE, STRUCTURES_EXAMPLE

COTTAGE_ROLES = {'FLOOR': 'FLOOR', 'GABLE-B': 'WALLS', 'GABLE-F': 'WALLS', 'SIDE-L': 'WALLS', 'SIDE-R': 'WALLS',
                 'ROOF-L': 'ROOF', 'ROOF-R': 'ROOF'}
COTTAGE_BRIEF = {'product_class': 'building', 'identity_features': ['pitched roof', 'arched door'],
                 'components': [{'id': 'FLOOR', 'role': 'base', 'count': 1},
                                {'id': 'WALLS', 'role': 'enclosure', 'count': 4, 'intentional_openings': ['door', 'window']},
                                {'id': 'ROOF', 'role': 'enclosure', 'count': 2, 'symmetric_pair': True}],
                 'enclosures': [{'id': 'HOUSE', 'components': ['FLOOR', 'WALLS', 'ROOF']}]}


def cottage(drop=(), brief=COTTAGE_BRIEF):
    d = copy.deepcopy(COMPLEX_EXAMPLE)
    d['boards'] = [dict(b, role=COTTAGE_ROLES[b['id']]) for b in d['boards'] if b['id'] not in drop]
    d['connections'] = [c for c in d['connections'] if c['board'] not in drop and c['into'] not in drop]
    d['product'].pop('overall', None)              # sizes are not what this test is about
    if brief is not None:
        d['brief'] = brief
    return d


def found(d):
    r = compile_source(json.dumps(d), run_production=False)
    return r, [(x['severity'], x['code'], x.get('side')) for x in r['diagnostics']
               if x['code'] in ('COMPONENT_MISSING', 'COMPONENT_COUNT', 'ROLE_UNKNOWN', 'ASYMMETRIC_PAIR', 'ENCLOSURE_OPEN',
                                'BRIEF_INVALID', 'BRIEF_WARNING')]


def test_the_complete_cottage_is_complete_and_its_door_and_windows_are_not_holes():
    r, f = found(cottage())
    assert f == [] and r['ok'] and r['completeness']['issues'] == 0


@pytest.mark.parametrize('drop,side', [(['ROOF-R'], 'top'), (['SIDE-L'], 'left'), (['GABLE-F'], 'front')])
def test_a_missing_part_is_a_missing_component_and_an_open_side(drop, side):
    r, f = found(cottage(drop))
    assert not r['ok'] and ('error', 'COMPONENT_COUNT', None) in f and ('error', 'ENCLOSURE_OPEN', side) in f


def test_a_whole_component_missing():
    _r, f = found(cottage(['ROOF-L', 'ROOF-R']))
    assert ('error', 'COMPONENT_MISSING', None) in f and ('error', 'ENCLOSURE_OPEN', 'top') in f


def test_a_side_the_brief_leaves_open_is_not_reported():
    brief = copy.deepcopy(COTTAGE_BRIEF)
    brief['components'][1]['count'] = 3
    brief['enclosures'][0]['closed_sides'] = ['top', 'bottom', 'left', 'right', 'back']
    brief['enclosures'][0]['open_sides_reason'] = 'a doll house: open at the front to play inside'
    r, f = found(cottage(['GABLE-F'], brief))
    assert f == [], f


def test_the_organiser_tray_open_at_the_top_by_design():
    d = copy.deepcopy(STRUCTURES_EXAMPLE)
    roles = {'BASE': 'BOX', 'FRONT': 'BOX', 'BACK': 'BOX', 'LEFT': 'BOX', 'RIGHT': 'BOX'}
    d['boards'] = [dict(b, role=roles.get(b['id'], 'DIVIDERS')) for b in d['boards']]
    d['brief'] = {'components': [{'id': 'BOX', 'count': 5}, {'id': 'DIVIDERS', 'count': 3}],
                  'enclosures': [{'id': 'TRAY', 'components': ['BOX'],
                                  'closed_sides': ['bottom', 'left', 'right', 'front', 'back']}]}
    assert found(d)[1] == []
    d['boards'] = [b for b in d['boards'] if b['id'] != 'FRONT']
    d['connections'] = [c for c in d['connections'] if 'FRONT' not in (c['board'], c['into'])]
    assert ('error', 'ENCLOSURE_OPEN', 'front') in found(d)[1]


def test_roles_follow_repeat_and_mirror_copies():
    d = cottage()
    d['brief'] = copy.deepcopy(COTTAGE_BRIEF)
    d['boards'] = [b for b in d['boards'] if b['id'] != 'ROOF-R']
    roof = next(b for b in d['boards'] if b['id'] == 'ROOF-L')
    roof['mirror'] = {'axis': 'x', 'at': 100}                  # ROOF-L-M stands in for ROOF-R
    d['connections'] = [dict(c, into='ROOF-L') if c['into'] == 'ROOF-R' else c for c in d['connections']]
    r, f = found(d)
    assert not [x for x in f if x[1] in ('COMPONENT_COUNT', 'COMPONENT_MISSING', 'ENCLOSURE_OPEN')], f


def test_an_unknown_role_is_warned_about():
    d = cottage()
    d['boards'][0]['role'] = 'PLINTH'
    _r, f = found(d)
    assert ('warning', 'ROLE_UNKNOWN', None) in f


def test_an_invalid_brief_is_reported_and_not_used():
    r, f = found(cottage(brief={'components': []}))
    assert ('error', 'BRIEF_INVALID', None) in f and 'completeness' not in r


def test_a_design_without_a_brief_is_unchanged():
    d = cottage(brief=None)
    r = compile_source(json.dumps(d), run_production=False)
    assert r['ok'] and 'completeness' not in r and not found(d)[1]


def test_brief_validation_details():
    b, probs = validate_brief({'product_class': 'spaceship', 'components': [{'id': 'HULL', 'count': 2, 'role': 'shiny'}],
                               'mechanisms': {'input': {'kind': 'pedal'}}})
    assert b['product_class'] == 'other' and b['components'][0]['role'] == 'structure'
    assert all(p['severity'] == 'warning' for p in probs) and len(probs) == 3
    assert validate_brief({'components': [{'id': 'A'}, {'id': 'A'}]})[0] is None
    assert validate_brief({'components': [{'id': 'A', 'parent': 'Z'}]})[0] is None
    assert validate_brief({'components': [{'id': 'A'}], 'enclosures': [{'id': 'E', 'components': ['B']}]})[0] is None


# the planning step over the API (AI stubbed) -------------------------------------------------------------------------

import os  # noqa: E402


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    os.environ.update(BOARD_INSTANCE_DIR=str(tmp_path_factory.mktemp('brief')), BOARD_API_KEYS='ed:editor',
                      BOARD_SKIP_SEED='1')
    import importlib
    import app as appmod
    importlib.reload(appmod)
    yield appmod.app.test_client()
    for k in ('BOARD_INSTANCE_DIR', 'BOARD_API_KEYS', 'BOARD_SKIP_SEED'):
        os.environ.pop(k, None)


ED = {'Authorization': 'Bearer ed'}


def _stub(monkeypatch, reply, seen):
    from board_engine import ai_client
    monkeypatch.setattr(ai_client, 'complete', lambda p: (seen.append(p), reply)[1])
    monkeypatch.setattr(ai_client, 'provider', lambda: ('gemini', 'stub'))


def test_ai_brief_returns_a_validated_brief(client, monkeypatch):
    seen = []
    _stub(monkeypatch, '```json\n' + json.dumps(COTTAGE_BRIEF) + '\n```', seen)
    r = client.post('/api/v1/canvas/ai-brief', headers=ED, json={'title': 'Cottage', 'requirements': 'simple'})
    assert r.status_code == 200 and r.json['brief']['components'][1]['id'] == 'WALLS'
    assert 'DESIGN BRIEF' in seen[0] and '<user_requirements>' in seen[0] and 'Output the bare JSON object' in seen[0]


def test_ai_brief_that_is_not_a_brief_is_an_error(client, monkeypatch):
    _stub(monkeypatch, 'Sure! Here is my plan: a lovely cottage.', [])
    assert client.post('/api/v1/canvas/ai-brief', headers=ED, json={'title': 'Cottage'}).status_code == 502


def test_brief_check_and_the_brief_reaching_the_geometry_prompt(client, monkeypatch):
    r = client.post('/api/v1/canvas/brief-check', headers=ED, json={'brief': json.dumps(COTTAGE_BRIEF)}).json
    assert r['valid'] and not r['problems']
    seen = []
    _stub(monkeypatch, json.dumps(cottage(brief=None)), seen)            # the AI's reply leaves the brief out
    r = client.post('/api/v1/canvas/ai-generate', headers=ED, json={'title': 'Cottage', 'brief': r['brief']})
    assert r.status_code == 200 and 'DESIGN BRIEF (the approved plan' in seen[0] and '"WALLS"' in seen[0]
    assert json.loads(r.json['source'])['brief']['components'][0]['id'] == 'FLOOR'     # put back: the AI left it out
    assert client.post('/api/v1/canvas/ai-generate', headers=ED,
                       json={'title': 'Cottage', 'brief': {'components': []}}).status_code == 400
    p = client.post('/api/v1/canvas/brief-prompt', headers=ED, json={'title': 'Aeroplane'}).json['prompt']
    assert 'enclosure' in p and '```json' in p
