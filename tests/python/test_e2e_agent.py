"""End-to-end: start the real server process and drive it over HTTP with the reference AI agent."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture(scope='module')
def server(tmp_path_factory):
    inst = tmp_path_factory.mktemp('e2e-instance')
    port = free_port()
    env = dict(os.environ, BOARD_INSTANCE_DIR=str(inst), BOARD_API_KEYS='e2e-agent-key:editor', LOG_LEVEL='WARNING')
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, 'start_server.py'), '--port', str(port), '--no-browser'],
                            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    url = f'http://127.0.0.1:{port}'
    for _ in range(120):
        try:
            urllib.request.urlopen(url + '/api/v1/', timeout=1)
            break
        except OSError:
            time.sleep(0.25)
    else:
        proc.kill()
        raise RuntimeError(proc.stdout.read().decode())
    yield url
    proc.terminate()
    proc.wait(10)


def test_seeded_boat_and_studio_page(server):
    page = urllib.request.urlopen(server + '/')
    assert page.status == 200 and b'Board Studio' in page.read()
    assert 'board_session' in page.headers['Set-Cookie']
    req = urllib.request.Request(server + '/api/v1/designs/boat/validate', method='POST',
                                 headers={'Authorization': 'Bearer e2e-agent-key'})
    v = json.load(urllib.request.urlopen(req))['validation']
    assert v['valid'] and v['complete'] and v['summary']['joined'] == 33


def test_ai_agent_designs_corrects_and_produces_boat(server, tmp_path):
    from ai_agent_demo import run
    res = run(server, 'e2e-agent-key', out_dir=str(tmp_path))
    assert res['validation']['valid'] and res['validation']['complete']
    assert res['states'] == {'joined'} and res['ready']
    f = res['findings']
    assert f['rejections']['duplicate'] == 'DUPLICATE_COMPONENT'
    assert 'UNINTENDED_GAP' in f['rejections'] and 'TAB_IN_OPENING' in f['rejections']
    assert f['rejections']['invalid_join'] in ('ORIENTATION_MISMATCH', 'NOT_IN_CONTACT')
    assert f['repairs'] == 21
    files = sorted(p.name for p in tmp_path.iterdir())
    assert any(n.endswith('booklet.pdf') for n in files) and sum(n.endswith('.dxf') for n in files) == 2
