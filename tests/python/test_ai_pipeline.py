"""AI pipeline correctness (audit 2026-11-28, phase 1): truncated replies, server transport, verified AI fixes,
requirements plumbing, non-finite numbers, unknown fields, safe fixes on generated boards. No real AI is called:
the provider HTTP / SDK calls are replaced by stubs."""
import json

import pytest

from board_engine.canvas import apply_code_fix, compile_source, pretty_json
from board_engine.canvas_prompt import EXAMPLE

SRC = json.dumps(EXAMPLE)


# F-01: a reply cut off at the output limit must never become a smaller design that passes -------------------------

def _cut_between_boards():
    """EXAMPLE cut off right before its 4th board, as a streaming reply stopped by the output limit would be."""
    return SRC[:SRC.index('{"id": "MODESTY"')]


def test_truncated_reply_is_reported_and_its_repair_is_not_safe():
    res = compile_source(_cut_between_boards(), run_production=False)
    d = res['diagnostics'][0]
    assert d['code'] == 'JSON_TRUNCATED' and d['severity'] == 'error' and not res['ok']
    assert d['fixes'] and not d['fixes'][0]['safe']          # the user decides; never applied automatically
    assert 'cut off' in d['message']


def test_mid_file_syntax_error_stays_a_safe_repair():
    text = pretty_json(EXAMPLE).replace('\n    },\n    {', '\n    }\n    {', 1)
    d = compile_source(text, run_production=False)['diagnostics'][0]
    assert d['code'] == 'JSON_SYNTAX' and d['fixes'][0]['safe']


class _Resp:
    def __init__(self, data, status=200):
        self.status_code, self._data = status, data

    def json(self):
        return self._data


def test_gemini_reply_stopped_at_the_token_limit_is_an_error(monkeypatch):
    import requests
    from board_engine import ai_client
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    reply = {'candidates': [{'finishReason': 'MAX_TOKENS', 'content': {'parts': [{'text': _cut_between_boards()}]}}]}
    monkeypatch.setattr(requests, 'post', lambda *a, **kw: _Resp(reply))
    with pytest.raises(ai_client.AIError, match='cut off'):
        ai_client.complete('design a table')


def test_gemini_complete_reply_is_returned(monkeypatch):
    import requests
    from board_engine import ai_client
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    reply = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': SRC}]}}]}
    monkeypatch.setattr(requests, 'post', lambda *a, **kw: _Resp(reply))
    assert ai_client.complete('design a table') == SRC


def _fake_anthropic(monkeypatch, stop_reason, text):
    import sys
    import types
    from board_engine import ai_client

    class Block:
        type = 'text'

        def __init__(self, t):
            self.text = t

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return types.SimpleNamespace(stop_reason=stop_reason, content=[Block(text)])

    class Client:
        def __init__(self, **kw):
            self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(stream=lambda **kw: Stream()))

    mod = types.ModuleType('anthropic')
    mod.Anthropic = Client
    for name in ('RateLimitError', 'APIStatusError', 'APIConnectionError'):
        setattr(mod, name, type(name, (Exception,), {}))
    monkeypatch.setitem(sys.modules, 'anthropic', mod)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    return ai_client


def test_claude_reply_stopped_at_max_tokens_is_an_error(monkeypatch):
    ai_client = _fake_anthropic(monkeypatch, 'max_tokens', _cut_between_boards())
    with pytest.raises(ai_client.AIError, match='cut off'):
        ai_client.complete('design a table')


def test_claude_complete_reply_is_returned(monkeypatch):
    ai_client = _fake_anthropic(monkeypatch, 'end_turn', SRC)
    assert ai_client.complete('design a table') == SRC


# F-02: the server makes ONE tool-less call, so its prompts must not ask for multi-part replies or a file ------------

import hashlib  # noqa: E402

from board_engine.canvas_prompt import build_prompt, build_repair_prompt, build_update_prompt  # noqa: E402

LASER = {'kerf': 0.15, 'sheet': {'width': 600, 'height': 400}}
CHAT_ONLY = ('MULTI-PART', '"continue"', 'file tool', 'downloadable file', 'multi-part')


def _server_prompts():
    d = [{'severity': 'error', 'code': 'X', 'message': 'boom'}]
    return [build_prompt('Castle', 'tall', None, None, 'interlocking', dict(LASER, file=True), False, transport='server'),
            build_repair_prompt(SRC, d, (), dict(LASER, file=True), transport='server'),
            build_update_prompt(SRC, 'wider', d, dict(LASER, file=True), transport='server')]


@pytest.mark.parametrize('i', range(3))
def test_server_prompts_ask_for_one_complete_reply(i):
    p = _server_prompts()[i]
    assert not [w for w in CHAT_ONLY if w in p]
    assert 'exactly ONE reply' in p


@pytest.mark.parametrize('style', ['lean', 'full'])
def test_chat_prompts_keep_their_multi_part_and_file_contracts(style):
    """The copy-paste prompts still tell an AI chat how to split a large design or deliver a file (the server's do not;
    see above). Phase 6 changed the default prompt to the lean one, so these are checked by content, not by hash."""
    p = build_prompt('Castle', 'tall', None, None, 'interlocking', LASER, False, style=style)
    assert 'MULTI-PART REPLIES' in p and '"continue"' in p
    assert 'file tool' in build_prompt('Castle', 'tall', None, None, None, dict(LASER, file=True), True, style=style)
    d = [{'severity': 'error', 'code': 'X', 'message': 'boom'}]
    assert 'MULTI-PART REPLIES' in build_repair_prompt(SRC, d, (), LASER)
    assert 'MULTI-PART REPLIES' in build_update_prompt(SRC, 'wider', d, LASER)


# F-03: an AI fix is compiled and accepted only when it is better and keeps the design's boards --------------------

import copy  # noqa: E402
import os  # noqa: E402

from board_engine.repair import accept_repair  # noqa: E402


def _broken_example():
    """EXAMPLE with LEG-R moved 7 mm outwards: SHELF and MODESTY no longer reach it (CONNECTION_GAP, no safe fix)."""
    d = copy.deepcopy(EXAMPLE)
    d['boards'][2]['position'][0] += 7
    return json.dumps(d)


def _res(src):
    return compile_source(src, run_production=False)


def test_a_fix_that_drops_boards_is_rejected():
    old = _broken_example()
    d = copy.deepcopy(EXAMPLE)
    d['boards'], d['connections'] = d['boards'][:1], []           # "fixed" by deleting everything but the top
    new = json.dumps(d)
    v = accept_repair(old, _res(old), new, _res(new))
    assert not v['accepted'] and set(v['removed']) >= {'LEG-L', 'LEG-R', 'SHELF'}
    assert any('removed' in r for r in v['reasons'])


def test_an_improving_fix_is_accepted():
    old = _broken_example()
    v = accept_repair(old, _res(old), SRC, _res(SRC))
    assert v['accepted'] and v['after']['errors'] < v['before']['errors'] and not v['removed']


def test_a_fix_that_changes_nothing_or_gets_worse_is_rejected():
    old = _broken_example()
    assert not accept_repair(old, _res(old), old, _res(old))['accepted']
    assert not accept_repair(SRC, _res(SRC), old, _res(old))['accepted']


def test_an_unparsable_reply_is_rejected():
    old = _broken_example()
    v = accept_repair(old, _res(old), 'Sorry, here is the design: {', _res('Sorry, here is the design: {'))
    assert not v['accepted']


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    os.environ.update(BOARD_INSTANCE_DIR=str(tmp_path_factory.mktemp('aipipe')), BOARD_API_KEYS='ed:editor',
                      BOARD_SKIP_SEED='1')
    import importlib
    import app as appmod
    importlib.reload(appmod)
    yield appmod.app.test_client()
    for k in ('BOARD_INSTANCE_DIR', 'BOARD_API_KEYS', 'BOARD_SKIP_SEED'):
        os.environ.pop(k, None)


ED = {'Authorization': 'Bearer ed'}


def _stub_ai(monkeypatch, reply, seen=None):
    from board_engine import ai_client

    def complete(prompt):
        if seen is not None:
            seen.append(prompt)
        return reply
    monkeypatch.setattr(ai_client, 'complete', complete)
    monkeypatch.setattr(ai_client, 'provider', lambda: ('gemini', 'stub'))


def test_ai_fix_endpoint_rejects_a_regressed_reply(client, monkeypatch):
    d = copy.deepcopy(EXAMPLE)
    d['boards'], d['connections'] = d['boards'][:1], []
    _stub_ai(monkeypatch, json.dumps(d))
    r = client.post('/api/v1/canvas/ai-fix', headers=ED, json={'source': _broken_example()})
    assert r.status_code == 200 and r.json['accepted'] is False and r.json['reasons']
    assert json.loads(r.json['source'])['boards'][2]['id'] == 'LEG-R'      # the design the user had is kept


def test_ai_fix_endpoint_accepts_an_improving_reply(client, monkeypatch):
    _stub_ai(monkeypatch, '```json\n' + SRC + '\n```')
    r = client.post('/api/v1/canvas/ai-fix', headers=ED, json={'source': _broken_example()})
    assert r.status_code == 200 and r.json['accepted'] is True and r.json['changed'] is True
    assert json.loads(r.json['source']) == EXAMPLE and r.json['after']['errors'] == 0


# F-10: requirements are read correctly and reach every AI step ------------------------------------------------------

from board_engine.canvas_prompt import hard_constraints  # noqa: E402
from board_engine.requirements import parse_detail_level, parse_material  # noqa: E402


def test_hard_constraints_read_a_size_triple_and_a_thickness():
    h = hard_constraints('1200 x 600 x 750 mm desk, 18 mm plywood, simple realistic')
    for want in ('length (X): 1200 mm', 'depth (Z): 600 mm', 'height (Y): 750 mm', 'board thickness: 18 mm',
                 'material: plywood'):
        assert want in h, want
    assert '- x:' not in h and 'a size' not in h and 'detail level' not in h       # "simple" vs "realistic": no guess


def test_hard_constraints_label_from_the_word_after_the_number():
    h = hard_constraints('A 200 mm long toy car')
    assert 'length (X): 200 mm' in h and '- A:' not in h
    h = hard_constraints('1:72 scale model, 400 mm long')          # nothing before the number after the comma
    assert 'length (X): 400 mm' in h and '- : ' not in h


@pytest.mark.parametrize('text,level', [('a simple stool', 2), ('basic shelf', 2), ('standard bookcase', 3),
                                        ('a detailed castle', 4), ('realistic steam engine', 4),
                                        ('highly detailed pagoda', 5), ('museum replica', 5), ('a chair', None),
                                        ('simple but highly detailed', None)])
def test_detail_level_words(text, level):
    assert parse_detail_level(text) == level


def test_material_and_thickness_words():
    assert parse_material('18 mm plywood desk') == {'type': 'plywood', 'thickness': 18.0}
    assert parse_material('made of 3mm MDF') == {'type': 'mdf', 'thickness': 3.0}
    assert parse_material('a pine bench') == {'type': 'solid_wood'}
    assert parse_material('a bench 400 mm long') == {}


def test_ai_generate_uses_the_chosen_material_and_joinery(client, monkeypatch):
    seen = []
    _stub_ai(monkeypatch, SRC, seen)
    r = client.post('/api/v1/canvas/ai-generate', headers=ED,
                    json={'title': 'Desk', 'material': 'mdf', 'joinery': 'glue_allowed'})
    assert r.status_code == 200 and '- Material type: mdf' in seen[0] and '- Joinery: glue_allowed' in seen[0]
    r = client.post('/api/v1/canvas/ai-generate', headers=ED, json={'title': 'Desk', 'material': 'unobtainium'})
    assert r.status_code == 400


def test_ai_fix_checks_and_sends_the_requirements(client, monkeypatch):
    seen = []
    _stub_ai(monkeypatch, SRC, seen)
    r = client.post('/api/v1/canvas/ai-fix', headers=ED, json={'source': SRC, 'requirements': 'length 1300 mm'})
    assert r.status_code == 200 and seen, 'a REQUIREMENT_MISMATCH must reach the AI'
    assert 'REQUIREMENT_MISMATCH' in seen[0] and 'length 1300 mm' in seen[0]


# F-16: NaN / Infinity are ordinary input errors, never a compiler crash ---------------------------------------------

@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf')])
def test_non_finite_numbers_are_reported_not_crashed_on(bad):
    d = copy.deepcopy(EXAMPLE)
    d['boards'][0]['size'][0] = bad
    d['product']['overall']['height'] = bad
    codes = {x['code'] for x in compile_source(json.dumps(d), run_production=False)['diagnostics']}
    assert 'BOARD_GEOMETRY' in codes and 'COMPILER_ERROR' not in codes


def test_integer_fix_prompt_survives_nan(client):
    d = copy.deepcopy(EXAMPLE)
    d['boards'][0]['position'][1] = float('nan')
    r = client.post('/api/v1/canvas/integer-fix-prompt', headers=ED, json={'source': json.dumps(d)})
    assert r.status_code == 200


# F-12: unknown, misspelled and invalid fields are reported instead of silently ignored -----------------------------

def _codes(d):
    r = compile_source(json.dumps(d), run_production=False)
    return r, [(x['severity'], x['code'], x['message']) for x in r['diagnostics']]


@pytest.mark.parametrize('where,key', [('top', 'color_scheme'), ('board', 'bevel_angle'), ('connection', 'hinge_type'),
                                       ('material', 'grain_finish')])
def test_unknown_fields_are_warned_about(where, key):
    d = copy.deepcopy(EXAMPLE)
    target = {'top': d, 'board': d['boards'][0], 'connection': d['connections'][0], 'material': d['material']}[where]
    target[key] = 1
    r, diags = _codes(d)
    hit = [m for s, c, m in diags if c == 'UNKNOWN_FIELD']
    assert r['ok'] and hit and key in hit[0] and all(s == 'warning' for s, c, m in diags if c == 'UNKNOWN_FIELD')


def test_unknown_motion_field_is_warned_about():
    d = copy.deepcopy(EXAMPLE)
    d['motions'] = [{'id': 'm', 'type': 'slide', 'boards': ['SHELF'], 'on': 'LEG-L', 'direction': 'z',
                     'range': [0, 10], 'springs': 2}]
    assert any(c == 'UNKNOWN_FIELD' and 'springs' in m for s, c, m in _codes(d)[1])


def test_a_misspelled_top_level_list_is_an_error_with_a_suggestion():
    d = copy.deepcopy(EXAMPLE)
    d['conections'] = d.pop('connections')
    r, diags = _codes(d)
    hit = [(s, m) for s, c, m in diags if c == 'MISSPELLED_FIELD']
    assert not r['ok'] and hit and hit[0][0] == 'error' and "'connections'" in hit[0][1]


def test_did_you_mean_on_a_board_key():
    d = copy.deepcopy(EXAMPLE)
    d['boards'][1]['openings'][0]['diamter'] = d['boards'][1]['openings'][0].pop('diameter')
    assert any(c == 'UNKNOWN_FIELD' and "'diameter'" in m for s, c, m in _codes(d)[1])


def test_an_unknown_format_is_an_error():
    d = dict(EXAMPLE, format='totally-other/v9')
    r, diags = _codes(d)
    assert not r['ok'] and ('error', 'FORMAT_UNSUPPORTED') in [(s, c) for s, c, m in diags]
    assert _codes(dict(EXAMPLE, format='board-design/v1.1'))[0]['ok']          # a v1 revision: warning only


@pytest.mark.parametrize('path,value', [(('material', 'clearance'), float('inf')), (('connections', 0, 'tabs'), 'x'),
                                        (('connections', 0, 'tab_width'), float('nan'))])
def test_invalid_optional_numbers_are_reported(path, value):
    d = copy.deepcopy(EXAMPLE)
    t = d
    for k in path[:-1]:
        t = t[k]
    t[path[-1]] = value
    assert any(c == 'INVALID_VALUE' and path[-1] in m for s, c, m in _codes(d)[1])


def test_no_unknown_field_warnings_on_any_shipped_design():
    import glob
    from board_engine.canvas_prompt import ADVANCED_EXAMPLE, COMPLEX_EXAMPLE, STRUCTURES_EXAMPLE
    srcs = [json.dumps(x) for x in (EXAMPLE, COMPLEX_EXAMPLE, STRUCTURES_EXAMPLE, ADVANCED_EXAMPLE)]
    root = os.path.join(os.path.dirname(__file__), '..', '..')
    for pat in ('board_engine/examples/*.json', 'tests/python/fixtures/*.json',
                'PROJECT_AUDIT/END_TO_END_VALIDATION/ai_runs/out_*/*.json'):
        for p in sorted(glob.glob(os.path.join(root, pat))):
            srcs.append(open(p).read())
    from board_engine.schema import check_fields
    from board_engine.canvas import parse_source
    for s in srcs:
        data = parse_source(s)[0]
        found = [d['message'] for d in check_fields(data) if d['code'] in ('UNKNOWN_FIELD', 'MISSPELLED_FIELD')]
        assert not found, found[:5]


# F-21: a fix on a board made by repeat / mirror / assemblies edits the source board, and is never "safe" -------------

from board_engine.canvas import CompileError  # noqa: E402


def _repeated_shelf_1mm_off():
    d = copy.deepcopy(EXAMPLE)
    d['boards'][4]['position'][0] = 69                       # SHELF 1 mm off LEG-L, then repeated twice
    d['boards'][4]['repeat'] = {'count': 2, 'step': [0, 200, 0]}
    return pretty_json(d)


def test_fixes_on_generated_boards_are_not_safe_and_apply_to_the_source():
    src = _repeated_shelf_1mm_off()
    res = compile_source(src, run_production=False)
    fixes = [f for d in res['diagnostics'] for f in d.get('fixes') or [] if f['id'].startswith('move-SHELF-1')]
    assert fixes and not any(f['safe'] for f in fixes)
    assert 'every copy' in fixes[0]['title']
    fixed = json.loads(apply_code_fix(src, fixes[0]))
    shelf = next(b for b in fixed['boards'] if b['id'] == 'SHELF')
    assert shelf['position'][0] == 68 and 'repeat' in shelf                    # the repeat moved as a whole
    after = compile_source(pretty_json(fixed), run_production=False)
    assert not [d for d in after['diagnostics'] if d['code'] in ('CONNECTION_GAP', 'CONNECTION_OVERLAP')]


def test_a_fix_naming_a_board_that_is_not_in_the_source_is_a_clear_error():
    with pytest.raises(CompileError, match='SHELF-9'):
        apply_code_fix(SRC, {'id': 'x', 'edits': [{'board': 'SHELF-9', 'field': 'position', 'value': [0, 0, 0]}]})
