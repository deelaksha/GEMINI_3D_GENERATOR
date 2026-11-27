"""Backend hardening: compile slots, JSON errors, health endpoint, security headers, no secrets in logs, cache keys."""
import importlib
import json
import logging
import os

import pytest

from test_canvas import EXAMPLE


@pytest.fixture()
def app_mod(tmp_path):
    os.environ.update(BOARD_INSTANCE_DIR=str(tmp_path), BOARD_API_KEYS='ed:editor,vw:viewer', BOARD_SKIP_SEED='1')
    import app as app_module
    importlib.reload(app_module)
    yield app_module
    for k in ('BOARD_INSTANCE_DIR', 'BOARD_API_KEYS', 'BOARD_SKIP_SEED'):
        os.environ.pop(k, None)


H = {'Authorization': 'Bearer vw'}


def test_compiles_are_limited_per_user(app_mod):
    c = app_mod.app.test_client()
    app_mod.app.config['BOARD_COMPILE_SLOTS'] = 0
    for path in ('/api/v1/canvas/compile', '/api/v1/canvas/compile-stream', '/api/v1/canvas/repair-prompt'):
        r = c.post(path, headers=H, json={'source': json.dumps(EXAMPLE)})
        assert r.status_code == 429 and r.json['error']['status'] == 'busy', path
    app_mod.app.config['BOARD_COMPILE_SLOTS'] = 2
    assert c.post('/api/v1/canvas/compile', headers=H, json={'source': json.dumps(EXAMPLE), 'production': False}).status_code == 200
    from board_api import routes
    assert routes._SLOTS == {}                                   # every slot was given back


def test_unexpected_api_errors_answer_json(app_mod, monkeypatch):
    import board_engine.canvas as canvas
    monkeypatch.setattr(canvas, 'compile_source', lambda *a, **k: 1 / 0)
    r = app_mod.app.test_client().post('/api/v1/canvas/compile', headers=H, json={'source': '{}'})
    assert r.status_code == 500 and r.is_json and r.json['error']['status'] == 'internal_error'


def test_health_and_security_headers(app_mod):
    r = app_mod.app.test_client().get('/api/v1/healthz')
    assert r.status_code == 200 and r.json['ok']
    assert r.headers['X-Content-Type-Options'] == 'nosniff' and r.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert 'Strict-Transport-Security' not in r.headers           # only over HTTPS


def test_a_generated_api_key_is_never_logged(tmp_path, caplog):
    from board_api.auth import KeyRing
    os.environ.pop('BOARD_API_KEYS', None)
    with caplog.at_level(logging.WARNING):
        ring = KeyRing(str(tmp_path))
    keys = [k for k in ring.keys]
    assert keys and not any(k in caplog.text for k in keys) and 'stored in' in caplog.text


def test_snapshots_from_other_engine_code_are_not_reused(tmp_path, monkeypatch):
    from board_engine import canvas as C
    monkeypatch.setattr(C, 'SNAPSHOT_DIR', str(tmp_path))
    src = json.dumps(EXAMPLE)
    C._SNAPSHOTS.clear()
    C.compile_source(src, run_production=False)
    assert len(os.listdir(tmp_path)) == 1
    monkeypatch.setattr(C, 'ENGINE_VERSION', 'another-build')
    C._SNAPSHOTS.clear()
    calls = []
    real = C._compile_source
    monkeypatch.setattr(C, '_compile_source', lambda *a, **k: calls.append(1) or real(*a, **k))
    assert C.compile_source(src, run_production=True)['ok'] and calls        # compiled in full, not from the old file


def test_rate_limiter_forgets_idle_users(tmp_path, monkeypatch):
    from board_api import auth
    ring = auth.KeyRing(str(tmp_path))
    t = [1000.0]
    monkeypatch.setattr(auth.time, 'time', lambda: t[0])
    for i in range(999):
        assert ring.rate_ok(f'session:{i}', 600)
    t[0] += 120                                                  # every one of them is now idle
    ring.rate_ok('session:new', 600)                             # the 1000th call sweeps
    assert list(ring._hits) == ['session:new']


def test_stream_gives_its_slot_back_even_if_never_read(app_mod):
    import time
    from board_api import routes
    c = app_mod.app.test_client()
    r = c.post('/api/v1/canvas/compile-stream', headers=H, json={'source': json.dumps(EXAMPLE)}, buffered=False)
    assert r.status_code == 200
    r.close()                                                     # the client goes away without reading anything
    for _ in range(200):
        if not routes._SLOTS:
            break
        time.sleep(0.05)
    assert routes._SLOTS == {}


def test_export_budget_follows_the_compiled_board_count(app_mod, monkeypatch):
    import copy
    from board_api import routes
    from board_engine import canvas
    seen = []
    real = routes.time_budget
    monkeypatch.setattr(routes, 'time_budget', lambda s: seen.append(s) or real(s))
    monkeypatch.setattr(canvas, 'BUDGET_BOARDS', 2)                # scale the effect down to a small design
    app_mod.app.config['BOARD_TIME_BUDGET'] = 90
    d = copy.deepcopy(EXAMPLE)
    shelf = next(b for b in d['boards'] if b['id'] == 'SHELF')
    shelf['repeat'] = {'count': 2, 'step': [0, 100, 0]}           # one "position" in the text, two boards
    app_mod.app.test_client().post('/api/v1/canvas/export', headers=H, json={'source': json.dumps(d), 'force': True})
    boards = len(canvas.compile_source(json.dumps(d), run_production=False)['design']['components'])
    assert seen and seen[-1] == 90 * boards / 2 > 90 and boards > json.dumps(d).count('"position"')


def test_the_process_wide_compile_cap_cannot_be_dodged_with_new_sessions(app_mod):
    from board_api import routes
    c = app_mod.app.test_client()
    app_mod.app.config['BOARD_COMPILE_TOTAL'] = 1
    routes._SLOTS['session:someone-else'] = 1                       # another user's compile is running
    try:
        r = c.post('/api/v1/canvas/compile', headers=H, json={'source': json.dumps(EXAMPLE)})
        assert r.status_code == 503 and r.json['error']['status'] == 'server_busy' and r.headers['Retry-After'] == '30'
    finally:
        routes._SLOTS.clear()
        app_mod.app.config['BOARD_COMPILE_TOTAL'] = 8


def test_paid_ai_calls_are_capped_per_user_and_per_day(app_mod, monkeypatch):
    from board_api import routes
    from board_engine import ai_client
    monkeypatch.setattr(ai_client, 'complete', lambda p: json.dumps(EXAMPLE))
    monkeypatch.setenv('GEMINI_API_KEY', 'g')
    c, ed = app_mod.app.test_client(), {'Authorization': 'Bearer ed'}
    routes._AI_CALLS.clear()
    app_mod.app.config.update(BOARD_AI_PER_HOUR=2, BOARD_AI_PER_DAY=3)
    try:
        codes = [c.post('/api/v1/canvas/ai-generate', headers=ed, json={'title': 'Box'}).status_code for _ in range(3)]
        assert codes == [200, 200, 429]                                    # hourly cap for this user
        routes._AI_CALLS['session:other'] = [__import__('time').time()]     # someone else's call
        routes._AI_CALLS['*'].append(routes._AI_CALLS['session:other'][0])
        r = c.post('/api/v1/canvas/ai-generate', headers={'Authorization': 'Bearer vw'}, json={'title': 'Box'})
        assert r.status_code in (403, 429)                                 # viewers may not; and the day is used up
        routes._AI_CALLS.pop('key:env:ed…', None)
        r = c.post('/api/v1/canvas/ai-generate', headers=ed, json={'title': 'Box'})
        assert r.status_code == 429 and r.json['error']['status'] == 'ai_daily_limit'
    finally:
        routes._AI_CALLS.clear()


def _start_keyring(folder, q):
    import sys
    sys.path.insert(0, os.getcwd())
    os.environ.pop('BOARD_API_KEYS', None)
    from board_api.auth import KeyRing
    ring = KeyRing(folder)
    q.put((ring._secret, sorted(ring.keys)))


def test_workers_starting_together_share_one_secret_and_key(tmp_path):
    import multiprocessing as mp
    ctx = mp.get_context('fork')
    q = ctx.Queue()
    procs = [ctx.Process(target=_start_keyring, args=(str(tmp_path), q)) for _ in range(6)]
    for p in procs:
        p.start()
    got = [q.get(timeout=30) for _ in procs]
    for p in procs:
        p.join()
    assert len({g[0] for g in got}) == 1 and len({tuple(g[1]) for g in got}) == 1


def _bump(folder, n):
    import sys
    sys.path.insert(0, os.getcwd())
    from board_engine.store import DesignStore
    st = DesignStore(folder)
    for _ in range(n):
        with st._lock('d'):                          # read - modify - write, like an update
            d = st.get('d')
            d['name'] = str(int(d['name']) + 1)
            st._write(d)


def test_saves_from_several_processes_are_never_lost(tmp_path):
    import multiprocessing as mp
    from board_engine.store import DesignStore
    from conftest import base_plate
    DesignStore(str(tmp_path)).create({'id': 'd', 'name': '0', 'components': [base_plate()], 'joints': []})
    ctx = mp.get_context('fork')
    procs = [ctx.Process(target=_bump, args=(str(tmp_path), 40)) for _ in range(4)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    assert DesignStore(str(tmp_path)).get('d')['name'] == '160'
