"""Browser end-to-end checks (optional: needs `pip install playwright` and a local Chrome; not in requirements.txt).

    python tests/e2e/browser_smoke.py [--root <checkout>] [--out results.json]

Starts the app from <checkout> on a free port with a throw-away instance directory, then drives the real UI:
  BR-01 Studio loads without console errors        BR-02 Canvas loads without console errors
  BR-03 Canvas: paste the example, compile -> 0 problems, 3D model on screen
  BR-04 Canvas: edit while a compile is running -> the latest text is what ends up compiled  (BUG-012)
  BR-05 Canvas: Ctrl-S twice -> one project, not two                                       (BUG-013)
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

KEY = 'browser-e2e-key'


def _free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _designs(base):
    req = urllib.request.Request(base + '/api/v1/designs', headers={'Authorization': f'Bearer {KEY}'})
    return json.load(urllib.request.urlopen(req))['designs']


def run(root):
    from playwright.sync_api import sync_playwright
    sys.path.insert(0, root)
    from board_engine.canvas_prompt import EXAMPLE
    tmp = tempfile.mkdtemp(prefix='e2e-browser-')
    port = _free_port()
    env = dict(os.environ, BOARD_INSTANCE_DIR=tmp, BOARD_API_KEYS=f'{KEY}:editor', BOARD_SKIP_SEED='1', LOG_LEVEL='ERROR',
               PYTHONPATH=root)
    env.pop('FIREBASE_SERVICE_ACCOUNT', None)
    server = subprocess.Popen([sys.executable, '-c', f'import app; app.app.run(host="127.0.0.1", port={port})'],
                              cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f'http://127.0.0.1:{port}'
    rows = []
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base + '/canvas', timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)

            def page_with_log():
                pg = browser.new_context().new_page()
                pg.errors = []
                # Chrome's automatic /favicon.ico request 404s on the Studio (no icon declared): cosmetic, ignored here
                pg.on('console', lambda m: m.type == 'error' and 'favicon' not in (m.location or {}).get('url', '')
                      and pg.errors.append(f"{m.text} {(m.location or {}).get('url', '')}"))
                pg.on('pageerror', lambda e: pg.errors.append(str(e)))
                pg.on('response', lambda r: r.status >= 400 and pg.errors.append(f'HTTP {r.status} {r.url}'))
                return pg

            pg = page_with_log()
            pg.goto(base + '/studio')
            pg.wait_for_function('window.__studioReady === true', timeout=30000)
            rows.append({'id': 'BR-01', 'case': 'Studio loads', 'pass': not pg.errors, 'console_errors': pg.errors[:5]})

            pg = page_with_log()
            pg.goto(base + '/canvas')
            pg.wait_for_function('window.__canvasReady === true', timeout=30000)
            rows.append({'id': 'BR-02', 'case': 'Canvas loads', 'pass': not pg.errors, 'console_errors': pg.errors[:5]})

            def set_code(text):
                pg.evaluate('(t) => document.querySelector(".CodeMirror").CodeMirror.setValue(t)', text)

            def status():
                return pg.inner_text('#compile-status')

            def settle():
                pg.wait_for_function('!document.querySelector("#btn-compile").disabled', timeout=60000)
                time.sleep(0.5)
                pg.wait_for_function('!document.querySelector("#btn-compile").disabled', timeout=60000)
                # a compile opens the 3D view full screen; leave it so the editor can be used again
                pg.evaluate('() => document.fullscreenElement && document.exitFullscreen()')
                time.sleep(0.2)

            # the study table's 1200 mm top needs a large-format laser bed (the default 600 x 400 rightly rejects it)
            pg.select_option('#in-bed', '1300x900')
            set_code(json.dumps(EXAMPLE, indent=2))
            pg.click('#btn-compile')
            settle()
            meshes = pg.evaluate('() => document.querySelectorAll("canvas").length')
            rows.append({'id': 'BR-03', 'case': 'Compile the example', 'status': status(), 'problems': pg.inner_text('#diag-count'),
                         'canvas_elements': meshes, 'pass': pg.inner_text('#diag-count').strip() == '0' and meshes > 0 and not pg.errors,
                         'console_errors': pg.errors[:5]})

            # BUG-012: start a slow full compile (6x6 egg-crate, a few seconds), then replace the text with broken JSON
            # and press Ctrl+Enter while it is still running
            n, cell = 6, 150
            boards = [{"id": "BASE", "position": [0, 0, 0], "size": [n * cell, 6, n * cell]}]
            for i in range(1, n):
                boards += [{"id": f"X{i}", "position": [3, 6, i * cell], "size": [n * cell - 6, 150, 6]},
                           {"id": f"Z{i}", "position": [i * cell, 6, 3], "size": [6, 150, n * cell - 6]}]
            set_code(json.dumps({"format": "board-design/v1", "product": {"name": "grid"},
                                 "material": {"type": "plywood", "thickness": 6}, "boards": boards, "connections": "auto"}))
            pg.click('#btn-compile')
            set_code('{"format": "board-design/v1", "boards": [ broken')
            pg.evaluate('() => document.fullscreenElement && document.exitFullscreen()')   # back to the editor
            time.sleep(0.2)
            pg.click('.CodeMirror')                  # the shortcut is an editor key binding
            running = pg.evaluate('() => document.querySelector("#btn-compile").disabled')
            pg.keyboard.press('Control+Enter')
            settle()
            diag = pg.inner_text('#diag-list')
            code = pg.evaluate('() => document.querySelector(".CodeMirror").CodeMirror.getValue()')
            # the broken JSON is either reported, or (the usual case) repaired in the editor and its design error shown
            latest = 'JSON_SYNTAX' in diag or ('"broken"' in code and 'not compiled' in status() and 'grid' not in code)
            rows.append({'id': 'BR-04', 'case': 'Edit during a running compile', 'status': status(),
                         'compile_running_when_edited': running,
                         'pass': latest, 'note': 'the latest (broken) text must be compiled and its error shown',
                         'diagnostics_excerpt': diag[:200]})

            # BUG-013: save, then Ctrl-S twice -> still one project
            set_code(json.dumps(EXAMPLE, indent=2))
            pg.click('#btn-compile')
            settle()
            before = len(_designs(base))
            pg.click('#btn-save')
            time.sleep(1.5)
            pg.click('.CodeMirror')
            pg.keyboard.press('Control+S')
            time.sleep(1.5)
            pg.keyboard.press('Control+S')
            time.sleep(1.5)
            after = len(_designs(base))
            rows.append({'id': 'BR-05', 'case': 'Save then Ctrl-S twice', 'projects_created': after - before,
                         'pass': after - before == 1})
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
        shutil.rmtree(tmp, ignore_errors=True)
    return {'root': root, 'cases': rows, 'summary': {'pass': sum(r['pass'] for r in rows), 'total': len(rows)}}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    ap.add_argument('--out')
    a = ap.parse_args()
    res = run(os.path.abspath(a.root))
    text = json.dumps(res, indent=1)
    if a.out:
        open(a.out, 'w').write(text)
    print(text)
