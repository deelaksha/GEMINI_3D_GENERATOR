"""The optional visual check (audit 2026-11-28, phase 10): views of the compiled model go to a vision AI once; what it
sees becomes problems for one targeted repair. No real AI is called."""
import base64
import copy
import json
import os
import sys
import types

import pytest

from board_engine.canvas_prompt import EXAMPLE
from board_engine.critique import CritiqueError, critique_problems, decode_views, parse_critique

PNG = 'data:image/png;base64,' + base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'0' * 100).decode()


def test_views_must_be_small_png_or_jpeg_data_urls():
    assert decode_views([PNG])[0][0] == 'image/png'
    for bad in ([], [PNG] * 5, ['data:image/gif;base64,R0lG'], ['http://example.com/a.png'],
                ['data:image/png;base64,' + base64.b64encode(b'0' * 1_600_000).decode()]):
        with pytest.raises(CritiqueError):
            decode_views(bad)


def test_the_critique_is_validated_and_becomes_problems():
    c = parse_critique('```json\n{"recognisable": 3, "discrepancies": [{"component": "ROOF", "issue": "missing", '
                       '"severity": "high", "where": "right side", "fix": "add the right roof panel"}, '
                       '{"issue": "sparkly", "severity": "??"}]}\n```')
    assert c['recognisable'] == 3 and c['discrepancies'][1]['issue'] == 'other'
    probs = critique_problems(c)
    assert probs[0]['code'] == 'VISUAL_MISSING' and probs[0]['severity'] == 'error' and probs[1]['severity'] == 'warning'
    with pytest.raises(CritiqueError):
        parse_critique('looks great!')


def test_images_reach_both_providers(monkeypatch):
    import requests
    from board_engine import ai_client
    sent = {}

    class R:
        status_code = 200

        def json(self):
            return {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{}'}]}}]}
    monkeypatch.setenv('GEMINI_API_KEY', 'k')
    monkeypatch.setattr(requests, 'post', lambda *a, **kw: (sent.update(kw['json']), R())[1])
    ai_client.complete('look', images=[('image/png', 'AAAA')])
    assert sent['contents'][0]['parts'][0] == {'inline_data': {'mime_type': 'image/png', 'data': 'AAAA'}}

    captured = {}

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            blk = types.SimpleNamespace(type='text', text='{}')
            return types.SimpleNamespace(stop_reason='end_turn', content=[blk])
    mod = types.ModuleType('anthropic')
    mod.Anthropic = lambda **kw: types.SimpleNamespace(beta=types.SimpleNamespace(messages=types.SimpleNamespace(
        stream=lambda **kw: (captured.update(kw), Stream())[1])))
    for n in ('RateLimitError', 'APIStatusError', 'APIConnectionError'):
        setattr(mod, n, type(n, (Exception,), {}))
    monkeypatch.setitem(sys.modules, 'anthropic', mod)
    monkeypatch.delenv('GEMINI_API_KEY')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'k')
    ai_client.complete('look', images=[('image/jpeg', 'BBBB')])
    first = captured['messages'][0]['content'][0]
    assert first['type'] == 'image' and first['source']['media_type'] == 'image/jpeg'


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    os.environ.update(BOARD_INSTANCE_DIR=str(tmp_path_factory.mktemp('visual')), BOARD_API_KEYS='ed:editor',
                      BOARD_SKIP_SEED='1')
    import importlib
    import app as appmod
    importlib.reload(appmod)
    yield appmod.app.test_client()
    for k in ('BOARD_INSTANCE_DIR', 'BOARD_API_KEYS', 'BOARD_SKIP_SEED'):
        os.environ.pop(k, None)


ED = {'Authorization': 'Bearer ed'}


def test_critique_endpoint_and_one_visual_repair(client, monkeypatch):
    from board_engine import ai_client
    seen = []
    crit = {'recognisable': 4, 'discrepancies': [{'component': 'SHELF', 'issue': 'misplaced', 'severity': 'medium',
                                                  'where': 'too low', 'fix': 'raise the shelf to 200 mm'}]}
    monkeypatch.setattr(ai_client, 'complete', lambda p, images=None: (seen.append((p, images)), json.dumps(crit))[1])
    monkeypatch.setattr(ai_client, 'provider', lambda: ('gemini', 'stub'))
    src = json.dumps(EXAMPLE)
    r = client.post('/api/v1/canvas/ai-critique', headers=ED, json={'source': src, 'views': [PNG, PNG], 'title': 'Desk'})
    assert r.status_code == 200 and r.json['problems'][0]['code'] == 'VISUAL_MISPLACED' and len(seen[0][1]) == 2
    assert client.post('/api/v1/canvas/ai-critique', headers=ED, json={'source': src, 'views': []}).status_code == 400

    moved = copy.deepcopy(EXAMPLE)                      # the AI's repair: the shelf raised, nothing else changed
    moved['boards'][4]['position'][1] = 200
    prompts = []
    monkeypatch.setattr(ai_client, 'complete', lambda p, images=None: (prompts.append(p), json.dumps(
        {'patch': {'boards': [moved['boards'][4]]}}))[1])
    f = client.post('/api/v1/canvas/ai-fix', headers=ED, json={'source': src, 'visual': r.json['problems']}).json
    assert 'VISUAL_MISPLACED' in prompts[0] and f['accepted'] is True and f['changed'] is True
    assert json.loads(f['source'])['boards'][4]['position'][1] == 200
