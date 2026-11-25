"""Failure injection through the real HTTP API (Flask test client, throw-away instance directory).

Every case records what was sent, what came back and whether the application stayed consistent. Nothing touches
./instance: BOARD_INSTANCE_DIR points at a temporary directory that is deleted afterwards.
"""
import copy
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

KEY = 'e2e-editor-key'
H = {'Authorization': f'Bearer {KEY}'}


def _app(tmp, rate_limit=600):
    os.environ.update(BOARD_INSTANCE_DIR=tmp, BOARD_API_KEYS=f'{KEY}:editor', BOARD_SKIP_SEED='1', LOG_LEVEL='ERROR')
    os.environ.pop('FIREBASE_SERVICE_ACCOUNT', None)
    for m in [m for m in sys.modules if m == 'app']:
        del sys.modules[m]
    import app as appmod
    appmod.app.config['BOARD_RATE_LIMIT'] = rate_limit
    appmod.app.config['TESTING'] = True
    return appmod.app


def run():
    from board_engine.canvas_prompt import EXAMPLE
    tmp = tempfile.mkdtemp(prefix='e2e-edge-')
    rows = []
    try:
        client = _app(tmp).test_client()

        def compile_(src, production=False):
            r = client.post('/api/v1/canvas/compile', json={'source': src, 'production': production}, headers=H)
            b = r.get_json(silent=True) or {}
            return r.status_code, b

        def add(cid, name, sent, status, body, expect, passed, note=''):
            errs = sorted({d['code'] for d in body.get('diagnostics', []) if d.get('severity') == 'error'}) if isinstance(body, dict) else []
            rows.append({'id': cid, 'case': name, 'sent': sent, 'http_status': status, 'error_codes': errs,
                         'api_error': (body.get('error') or {}).get('status') if isinstance(body, dict) else None,
                         'expected': expect, 'pass': bool(passed), 'note': note})

        good = json.dumps(EXAMPLE)

        def case_compile(cid, name, src, want_codes, sent=None):
            st, b = compile_(src)
            errs = {d['code'] for d in b.get('diagnostics', []) if d['severity'] == 'error'}
            add(cid, name, sent or (src[:120] + ('…' if len(src) > 120 else '')), st, b,
                f'HTTP 200, compiled=false, one of {want_codes}', st == 200 and b.get('compiled') is False and errs & set(want_codes))

        # --- prompt endpoint
        r = client.post('/api/v1/canvas/prompt', json={'title': ''}, headers=H)
        add('EC-01', 'Empty prompt (no product title)', {'title': ''}, r.status_code, r.get_json(), 'HTTP 4xx with a message',
            400 <= r.status_code < 500)
        long_req = 'shelf ' * 200_000
        r = client.post('/api/v1/canvas/prompt', json={'title': 'Shelf', 'requirements': long_req}, headers=H)
        b = r.get_json(silent=True) or {}
        add('EC-02', 'Extremely long prompt (1.2 MB of requirements)', f'{len(long_req)} chars', r.status_code, b,
            'rejected (413) or truncated, never a crash', r.status_code in (200, 413),
            note=f"prompt length returned: {len(b.get('prompt', ''))} chars (requirements are cut to 4000)" if r.status_code == 200
            else 'request body larger than MAX_CONTENT_LENGTH (2 MB) is refused by Flask')

        # --- AI response problems
        case_compile('EC-03', 'Invalid AI response (prose, no JSON)', 'Sorry, I cannot design that product.', ['JSON_SYNTAX', 'NOT_AN_OBJECT'])
        case_compile('EC-04', 'Malformed JSON', '{"boards": [ {"id": "A" "size": [1,2,3]} ]}', ['JSON_SYNTAX'])
        case_compile('EC-05', 'Partial generation (response cut off)', good[: len(good) // 2], ['JSON_SYNTAX'])
        case_compile('EC-06', 'Missing required fields (no boards)', json.dumps({k: v for k, v in EXAMPLE.items() if k != 'boards'}), ['NO_BOARDS'])
        case_compile('EC-07', 'Missing dimensions', json.dumps(dict(EXAMPLE, boards=[{"id": "TOP", "position": [0, 0, 0]}])), ['BOARD_GEOMETRY'])
        case_compile('EC-08', 'Negative dimensions', json.dumps(dict(EXAMPLE, boards=[dict(EXAMPLE['boards'][0], size=[-1200, 18, 600])])), ['BOARD_SIZE'])
        case_compile('EC-09', 'Zero thickness', json.dumps(dict(EXAMPLE, material=dict(EXAMPLE['material'], thickness=0))), ['MATERIAL_THICKNESS'])
        case_compile('EC-10', 'Extremely small board (0.3 mm thick material)', json.dumps(dict(EXAMPLE, material=dict(EXAMPLE['material'], thickness=0.3))),
                     ['MATERIAL_THICKNESS'])
        case_compile('EC-11', 'Extremely large dimensions (8 m board)', json.dumps(dict(EXAMPLE, boards=[dict(EXAMPLE['boards'][0], size=[8000, 18, 600])])),
                     ['BOARD_SIZE'])
        case_compile('EC-12', 'Duplicate IDs', json.dumps(dict(EXAMPLE, boards=EXAMPLE['boards'] + [EXAMPLE['boards'][0]])), ['DUPLICATE_BOARD_ID'])
        case_compile('EC-13', 'Missing component reference', json.dumps(dict(EXAMPLE, connections=EXAMPLE['connections'] + [
            {"id": "X", "type": "tab_slot", "board": "GHOST", "into": "TOP"}])), ['UNKNOWN_BOARD'])
        case_compile('EC-14', 'Circular / self reference', json.dumps(dict(EXAMPLE, connections=[
            {"id": "S", "type": "tab_slot", "board": "TOP", "into": "TOP"}])), ['SELF_CONNECTION', 'UNKNOWN_BOARD'])
        st, b = compile_(json.dumps(dict(EXAMPLE, connections=EXAMPLE['connections'] + [
            {"id": "R", "type": "tab_slot", "board": "TOP", "into": "LEG-L"}])))
        add('EC-15', 'Circular pair (A into B and B into A)', 'LEG-L into TOP plus TOP into LEG-L', st, b,
            'the reversed duplicate is ignored with a warning; design still compiles',
            st == 200 and b.get('compiled') and any(d['code'] == 'DUPLICATE_CONNECTION' for d in b['diagnostics']))
        case_compile('EC-16', 'Unsupported material', json.dumps(dict(EXAMPLE, material=dict(EXAMPLE['material'], type='steel'))), ['MATERIAL_TYPE'])
        prof = {"shape": "polygon", "points": [[i % 2 * 5 + 100, i * 0.2] for i in range(3000)]}
        case_compile('EC-17', 'Excessive polygon complexity (3000-point profile)',
                     json.dumps(dict(EXAMPLE, boards=[dict(EXAMPLE['boards'][1], profile=prof)] + EXAMPLE['boards'][2:])),
                     ['PROFILE_INVALID'], sent='LEG-L profile with 3000 points')
        st, b = compile_(json.dumps(dict(EXAMPLE, boards=[dict(EXAMPLE['boards'][0], hinge_side='left', colour_name='oak')] + EXAMPLE['boards'][1:])))
        add('EC-18', 'Unexpected properties', '"hinge_side", "colour_name" on a board', st, b,
            'compiles; unknown fields reported', st == 200 and b.get('compiled'),
            note='unknown fields are silently ignored (no warning) — see bug tracker' if not any(
                'unknown' in d['message'].lower() for d in b.get('diagnostics', [])) else 'unknown fields reported')
        big = '{"boards": [' + ','.join(['{"id": "B%d", "position": [0,0,0], "size": [10,18,10]}' % i for i in range(60000)]) + ']}'
        client.application.config['BOARD_TIME_BUDGET'] = 1       # large designs are accepted: just bound the run here
        r = client.post('/api/v1/canvas/compile', data=json.dumps({'source': big}), content_type='application/json', headers=H)
        body = json.dumps(r.get_json(silent=True))
        add('EC-19', 'Extremely large JSON response (≈3.5 MB)', f'{len(big)} chars', r.status_code, r.get_json(silent=True) or {},
            'accepted (no size refusal) and ends with a result or COMPILE_TIMEOUT, never a crash',
            r.status_code == 200 and 'SOURCE_TOO_LARGE' not in body and 'COMPILER_ERROR' not in body)
        client.application.config.pop('BOARD_TIME_BUDGET', None)

        # --- repeated requests: identical results
        outs = [compile_(good)[1] for _ in range(3)]
        same = len({json.dumps(o.get('summary'), sort_keys=True) + json.dumps(o.get('diagnostics'), sort_keys=True) for o in outs}) == 1
        add('EC-20', 'Repeated generation requests (3x same source)', 'EXAMPLE x3', 200, outs[0], 'identical results', same)

        # --- persistence, concurrency, exports
        r = client.post('/api/v1/canvas/save', json={'source': good, 'name': 'Edge table'}, headers=H)
        did = (r.get_json() or {}).get('design_id')
        rev = client.get(f'/api/v1/designs/{did}', headers=H).get_json()['design']['revision']
        p1 = client.patch(f'/api/v1/designs/{did}', json={'name': 'A', 'expected_revision': rev}, headers=H)
        p2 = client.patch(f'/api/v1/designs/{did}', json={'name': 'B', 'expected_revision': rev}, headers=H)
        add('EC-21', 'Concurrent editing with expected_revision', 'two renames at the same revision', p2.status_code, p2.get_json(),
            'first 200, second 409 conflict', p1.status_code == 200 and p2.status_code == 409)
        p3 = client.patch(f'/api/v1/designs/{did}', json={'name': 'C'}, headers=H)
        add('EC-22', 'Concurrent editing without expected_revision', 'rename without revision', p3.status_code, p3.get_json(),
            'accepted (last write wins) — this is what the Studio UI does', p3.status_code == 200,
            note='the Studio never sends expected_revision (BUG-010)')
        before = client.get(f'/api/v1/designs/{did}', headers=H).get_json()['design']
        bad = client.post(f'/api/v1/designs/{did}/operations', headers=H,
                          json={'operations': [{'op': 'translate', 'id': 'TOP', 'delta': [0, 0, 0]},
                                               {'op': 'delete_component', 'id': 'NOPE'}]})
        after = client.get(f'/api/v1/designs/{did}', headers=H).get_json()['design']
        add('EC-23', 'Failed batch operation leaves no partial change', 'translate + delete of a missing part', bad.status_code, bad.get_json(),
            '4xx and the stored design is unchanged', bad.status_code >= 400 and after['revision'] == before['revision']
            and after['components'] == before['components'])
        r = client.get(f'/api/v1/designs/{did}/export/svg?sheet=99&kerf=1', headers=H)
        add('EC-24', 'Failed file export (sheet out of range)', 'sheet=99', r.status_code, r.get_json(silent=True) or {},
            'HTTP 400, no file', r.status_code == 400)
        loose = copy.deepcopy(EXAMPLE)
        loose['boards'].append({"id": "LOOSE", "position": [300, 200, 60], "size": [400, 18, 280]})
        r = client.post('/api/v1/canvas/save', json={'source': json.dumps(loose), 'name': 'Floating'}, headers=H)
        fid = (r.get_json() or {}).get('design_id')
        r = client.get(f'/api/v1/designs/{fid}/export/dxf?sheet=1&kerf=1', headers=H)
        add('EC-25', 'Export of a design with a floating board', 'DXF export', r.status_code, r.get_json(silent=True) or {},
            'HTTP 409 not_ready_for_production (no manufacturing file)', r.status_code == 409,
            note='baseline lets it through: floating boards do not block production (BUG-007)' if r.status_code == 200 else '')

        # --- time budget for expensive geometry
        n, cell = 8, 150
        boards = [{"id": "BASE", "position": [0, 0, 0], "size": [n * cell, 6, n * cell]}]
        for i in range(1, n):
            boards += [{"id": f"X{i}", "position": [3, 6, i * cell], "size": [n * cell - 6, 150, 6]},
                       {"id": f"Z{i}", "position": [i * cell, 6, 3], "size": [6, 150, n * cell - 6]}]
        grid = json.dumps({"format": "board-design/v1", "product": {"name": "grid"}, "material": {"type": "plywood", "thickness": 6},
                           "boards": boards, "connections": "auto"})
        client.application.config['BOARD_TIME_BUDGET'] = 5
        t0 = time.time()
        st, b = compile_(grid, production=True)
        dt = time.time() - t0
        timed_out = any(d['code'] == 'COMPILE_TIMEOUT' for d in b.get('diagnostics', []))
        add('EC-26', 'Expensive collision detection under a 5 s budget (8x8 egg-crate, production on)', '15 boards, 91 joints',
            st, b, 'clear COMPILE_TIMEOUT within ~budget, no hang', timed_out and dt < 15,
            note=f'request took {dt:.1f} s' + ('' if timed_out else ' — no server-side time budget exists'))

        # --- rate limiting
        client2 = _app(tempfile.mkdtemp(prefix='e2e-rate-', dir=tmp), rate_limit=5).test_client()
        codes = [client2.get('/api/v1/designs', headers=H).status_code for _ in range(7)]
        add('EC-27', 'API rate limit', '7 requests with a 5/min limit', codes[-1], {}, 'HTTP 429 after 5', codes[:5] == [200] * 5 and codes[-1] == 429,
            note=f'status codes: {codes}')
        rows.append({'id': 'EC-28', 'case': 'Gemini API timeout / rate limit / network interruption', 'pass': None,
                     'expected': 'n/a', 'note': 'NOT APPLICABLE: the application never calls Gemini (prompt is copy-pasted).'})
        rows.append({'id': 'EC-29', 'case': 'Browser refresh during generation', 'pass': None, 'expected': 'draft restored',
                     'note': 'NOT EXECUTED (needs a browser). Code: canvas drafts autosave to localStorage (js/canvas/main.js:142-143).'})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {'cases': rows, 'summary': {'pass': sum(r['pass'] is True for r in rows), 'fail': sum(r['pass'] is False for r in rows),
                                       'not_applicable_or_not_executed': sum(r['pass'] is None for r in rows)}}


if __name__ == '__main__':
    print(json.dumps(run(), indent=1, default=str))
