"""Laser workflow features: test-fit piece / measured thickness, job report, shared cut lines, living hinges,
text engraving, resizing, true-shape nesting, LightBurn export."""
import copy
import importlib
import io
import json
import zipfile

import pytest

from board_engine.canvas import compile_source

LASER = {'kerf': 0.15, 'sheet': {'width': 600, 'height': 400}}
BOX = {'format': 'board-design/v1', 'product': {'name': 'Laser box'}, 'material': {'type': 'plywood', 'thickness': 6},
       'boards': [{'id': 'BASE', 'position': [0, 0, 0], 'size': [200, 6, 150]},
                  {'id': 'WALL', 'position': [30, 6, 60], 'size': [140, 80, 6]}],
       'connections': [{'id': 'W-B', 'type': 'tab_slot', 'board': 'WALL', 'into': 'BASE', 'tabs': 2}]}


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    import os
    os.environ.update(BOARD_INSTANCE_DIR=str(tmp_path_factory.mktemp('laser')), BOARD_API_KEYS='ed:editor,vw:viewer',
                      BOARD_SKIP_SEED='1')
    import app as app_module
    importlib.reload(app_module)
    yield app_module.app.test_client()
    for k in ('BOARD_INSTANCE_DIR', 'BOARD_API_KEYS', 'BOARD_SKIP_SEED'):
        os.environ.pop(k, None)


VW = {'Authorization': 'Bearer vw'}


# --- 1. measured thickness, slot fit, test-fit piece -------------------------------------------------------

def test_measured_thickness_and_fit_size_the_slots():
    mat = lambda m: compile_source(json.dumps(BOX), run_production=False, machine=m)['design']['material']
    assert mat(LASER)['clearance'] == 0.1                                     # the design's default stays
    assert mat(dict(LASER, measured=6.2, fit=0.1))['clearance'] == pytest.approx(0.3)   # slot = 6.2 + 0.1
    assert mat(dict(LASER, measured=5.8, fit=0.15))['clearance'] == 0.0      # thinner board: never a negative slot


def test_test_fit_piece(client):
    r = client.post('/api/v1/canvas/test-fit', headers=VW, json={'thickness': 5.8, 'machine': LASER})
    assert r.status_code == 200 and r.mimetype == 'image/svg+xml'
    svg = r.data.decode()
    assert svg.count('id="COMB/outer"') == 1 and 'data-text="+0.1"' in svg and 'data-text="-0.1"' in svg
    assert 'kerf compensation 0.15 mm' in svg and '<text' not in svg              # labels are single-stroke paths
    assert client.post('/api/v1/canvas/test-fit', headers=VW, json={'thickness': 5.8, 'format': 'dxf'}).mimetype == 'application/dxf'
    assert client.post('/api/v1/canvas/test-fit', headers=VW, json={'thickness': 99}).status_code == 400
    assert client.post('/api/v1/canvas/compile', headers=VW,
                       json={'source': json.dumps(BOX), 'machine': dict(LASER, fit=5)}).status_code == 400
    z = zipfile.ZipFile(io.BytesIO(client.post('/api/v1/canvas/export', headers=VW,
                                               json={'source': json.dumps(BOX), 'machine': dict(LASER, measured=6.1)}).data))
    assert any(n.endswith('-test-fit.svg') for n in z.namelist())
    assert 'data-text="6.1 mm"' in z.read(next(n for n in z.namelist() if n.endswith('-test-fit.svg'))).decode()


# --- 6. laser job report ------------------------------------------------------------------------------------

def test_job_report_lengths_time_and_cost():
    from board_engine.jobreport import path_length
    assert path_length({'shape': 'polyline', 'points': [[0, 0], [100, 0], [100, 50], [0, 50]], 'closed': True}) == 300
    assert path_length({'shape': 'circle', 'radius': 10}) == pytest.approx(62.83, abs=0.01)
    r = compile_source(json.dumps(BOX), machine=LASER)
    job = r['job']
    t = job['totals']
    # outlines alone are > 2 * (200 + 150) + 2 * (140 + 80) mm; slots and tabs add a little
    assert t['sheets'] == 1 and 1.14 < t['cut_length_m'] < 1.5 and t['pierces'] >= 4 and t['minutes'] > 0
    assert 'material_cost' not in t and job['cut_speed'] == 10
    fast = compile_source(json.dumps(BOX), machine=dict(LASER, cut_speed=20, sheet_price=4.5))['job']
    assert fast['totals']['minutes'] < t['minutes'] and fast['totals']['material_cost'] == 4.5


def test_job_report_in_the_readme(client):
    z = zipfile.ZipFile(io.BytesIO(client.post('/api/v1/canvas/export', headers=VW,
                                               json={'source': json.dumps(BOX), 'machine': dict(LASER, sheet_price=3)}).data))
    readme = z.read(next(n for n in z.namelist() if n.endswith('README.txt'))).decode()
    assert 'Job        : 1 sheet(s), cut' in readme and 'material 3' in readme and 'sheet 1: cut' in readme


# --- 7. shared cut lines ------------------------------------------------------------------------------------

TILES = {'format': 'board-design/v1', 'product': {'name': 'Tiles'}, 'material': {'type': 'plywood', 'thickness': 3},
         'boards': [{'id': f'T{i}', 'position': [i * 200, 0, 0], 'size': [100, 3, 80]} for i in range(6)], 'connections': []}


def _seg_dist(p, a, b):
    import math
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy or 1e-12
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def test_shared_cut_lines_cut_every_edge_once():
    from board_engine.views import production_package
    shared_m = dict(LASER, shared_edges=True)
    design = compile_source(json.dumps(TILES), run_production=False, machine=shared_m)['design']
    assert design['sheet']['spacing'] == 0.15
    plain = production_package(design, {'compensate_kerf': True, 'shared_edges': False})
    shared = production_package(design, {'compensate_kerf': True})
    assert not plain['nesting']['issues'] and shared['ready_for_production']
    lines = [(p['points'], p.get('closed', True)) for p in shared['cut']['sheets'][0]['paths'] if p['type'] == 'outer']
    segs = [(pts[i], pts[(i + 1) % len(pts)]) for pts, closed in lines for i in range(len(pts) if closed else len(pts) - 1)]
    assert any(not closed for _pts, closed in lines)                       # some edges really are shared
    # every point of every part's full outline is still cut by some line (no part left attached)
    for p in plain['cut']['sheets'][0]['paths']:
        if p['type'] != 'outer':
            continue
        pts = p['points']
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            for k in range(11):
                q = (a[0] + (b[0] - a[0]) * k / 10, a[1] + (b[1] - a[1]) * k / 10)
                assert min(_seg_dist(q, c, d) for c, d in segs) < 0.02, (p['id'], q)
    j_plain = compile_source(json.dumps(TILES), machine=LASER)['job']['totals']['cut_length_m']
    j_shared = compile_source(json.dumps(TILES), machine=shared_m)['job']['totals']['cut_length_m']
    assert j_shared < j_plain * 0.85


# --- 4. living hinges ---------------------------------------------------------------------------------------

HINGE = {'format': 'board-design/v1', 'product': {'name': 'Hinge panel'}, 'material': {'type': 'plywood', 'thickness': 3},
         'boards': [{'id': 'PANEL', 'position': [0, 0, 0], 'size': [200, 120, 3],
                     'living_hinge': {'from': [60, 10], 'to': [140, 110], 'lines_along': 'v'}}], 'connections': []}


def test_living_hinge_pattern_and_cut_files():
    from board_engine.hinge import hinge_lines
    lines = hinge_lines(0, 0, 100, 4, 'u', 2, 20, 5)                    # 3 rows of 20 mm cuts, bridges 5 mm
    assert len({ln[0][1] for ln in lines}) == 3 and all(ln[1][0] - ln[0][0] <= 20 + 1e-9 for ln in lines)
    assert lines[0][0][0] == 0 and min(ln[0][0] for ln in lines if ln[0][1] == 2) == 0   # odd row offset, clipped
    r = compile_source(json.dumps(HINGE), machine=LASER)
    assert r['ok'] and r['layout']['ready_for_production']
    comp = r['model3d']['components'][0]
    assert comp['hinges'] and len(comp['hinges'][0]['lines']) > 100
    hinge_paths = [p for p in r['layout']['cut']['sheets'][0]['paths'] if p.get('feature_kind') == 'hinge']
    assert hinge_paths and all(p['type'] == 'inner' and p['closed'] is False for p in hinge_paths)
    outer = next(p for p in r['layout']['cut']['sheets'][0]['paths'] if p['type'] == 'outer')
    assert max(p['order'] for p in hinge_paths) < outer['order']          # cut before the outline frees the part


@pytest.mark.parametrize('patch', [{'from': [1, 10]}, {'lines_along': 'w'}, {'spacing': 0.1}])
def test_living_hinge_mistakes_are_errors(patch):
    d = copy.deepcopy(HINGE)
    d['boards'][0]['living_hinge'].update(patch)
    r = compile_source(json.dumps(d), run_production=False)
    assert 'HINGE_INVALID' in {x['code'] for x in r['diagnostics'] if x['severity'] == 'error'}


# --- 5. engraved text and images ----------------------------------------------------------------------------

PNG = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')
SIGN = {'format': 'board-design/v1', 'product': {'name': 'Sign'}, 'material': {'type': 'plywood', 'thickness': 3},
        'boards': [{'id': 'SIGN', 'position': [0, 0, 0], 'size': [160, 60, 3], 'engravings': [
            {'kind': 'engrave', 'text': 'Hello 2026!', 'position': [80, 25], 'height': 8, 'align': 'center'},
            {'kind': 'image', 'src': PNG, 'position': [5, 5], 'size': [20, 20]}]}], 'connections': []}


def test_text_and_image_engraving():
    from board_engine.strokefont import text_strokes, text_width
    assert text_width('AB', 6) == 10 and len(text_strokes('H', 0, 0, 6)) == 3
    assert text_strokes('?', 0, 0, 6) == text_strokes('☃', 0, 0, 6)          # unknown characters draw as '?'
    r = compile_source(json.dumps(SIGN), machine=LASER)
    assert r['ok'] and r['layout']['ready_for_production']
    comp = r['model3d']['components'][0]
    assert len(comp['marks']) > 10 and comp['marks'][0]['note'] == 'Hello 2026!'
    assert comp['images'] and 'src' not in comp['images'][0]                      # 3D gets the outline only
    sheet = r['layout']['cut']['sheets'][0]
    assert sheet['images'] and len(sheet['images'][0]['corners']) == 3 and r['job']['totals']['engrave_length_m'] > 0


def test_image_and_labels_in_the_cut_files(client):
    z = zipfile.ZipFile(io.BytesIO(client.post('/api/v1/canvas/export', headers=VW,
                                               json={'source': json.dumps(SIGN), 'machine': LASER}).data))
    svg = z.read(next(n for n in z.namelist() if n.endswith('-sheet1.svg'))).decode()
    assert '<g id="ENGRAVE_IMAGE">' in svg and 'href="data:image/png' in svg and 'transform="matrix(' in svg
    assert 'data-text="SIGN"' in svg and '<text' not in svg                         # part label as stroke paths


@pytest.mark.parametrize('patch', [{'text': ''}, {'height': 1}, {'align': 'middle'}, {'position': [150, 25]}])
def test_text_engraving_mistakes(patch):
    d = copy.deepcopy(SIGN)
    d['boards'][0]['engravings'][0].update(patch)
    errs = {x['code'] for x in compile_source(json.dumps(d), run_production=False)['diagnostics'] if x['severity'] == 'error'}
    assert errs & {'ENGRAVING_INVALID', 'MARK_OUTSIDE_BOARD'}


def test_image_engraving_mistakes():
    d = copy.deepcopy(SIGN)
    d['boards'][0]['engravings'][1]['src'] = 'https://example.com/logo.png'
    assert 'ENGRAVING_INVALID' in {x['code'] for x in compile_source(json.dumps(d), run_production=False)['diagnostics']}


# --- 3. parametric resize -----------------------------------------------------------------------------------

def test_resize_keeps_thickness_and_every_joint():
    from board_engine.canvas_prompt import EXAMPLE
    from board_engine.resize import resize_design
    new, ext = resize_design(EXAMPLE, {'length': 1560, 'depth': 780})
    assert ext == {'length': 1560, 'height': 750, 'depth': 780} and new['product']['overall']['length'] == 1560
    r = compile_source(json.dumps(new), run_production=False)
    assert r['ok'] and r['summary']['joined'] == r['summary']['joints'] == 13
    old = {b['id']: b for b in EXAMPLE['boards']}
    for b in new['boards']:                                   # the thickness size of every board is unchanged
        assert 18 in b['size'] and all(isinstance(v, int) for v in b['size'] + b['position'])
    assert {b['id'] for b in new['boards']} == set(old)


def test_resize_endpoint(client):
    from board_engine.canvas_prompt import COMPLEX_EXAMPLE, EXAMPLE
    r = client.post('/api/v1/canvas/resize', headers=VW, json={'source': json.dumps(BOX), 'length': 300})
    assert r.status_code == 200 and r.json['overall']['length'] == 300
    assert compile_source(r.json['source'], run_production=False)['ok']
    assert client.post('/api/v1/canvas/resize', headers=VW, json={'source': json.dumps(COMPLEX_EXAMPLE), 'length': 300}).status_code == 422
    assert client.post('/api/v1/canvas/resize', headers=VW, json={'source': json.dumps(EXAMPLE), 'height': 40}).status_code == 422
    assert client.post('/api/v1/canvas/resize', headers=VW, json={'source': '{', 'length': 300}).status_code == 422
    assert client.post('/api/v1/canvas/resize', headers=VW, json={'source': json.dumps(BOX), 'length': 1}).status_code == 400


# --- 8. true-shape nesting ----------------------------------------------------------------------------------

def _triangles(n):
    return {'format': 'board-design/v1', 'product': {'name': 'Triangles'}, 'material': {'type': 'plywood', 'thickness': 3},
            'boards': [{'id': f'T{i}', 'position': [i * 300, 0, 0], 'size': [200, 150, 3],
                        'profile': {'shape': 'polygon', 'points': [[0, 0], [200, 0], [100, 150]]}} for i in range(n)],
            'connections': []}


def test_true_shape_nesting_saves_sheets_and_stays_exact():
    from board_engine import nesting
    from board_engine.views import production_package
    design = compile_source(json.dumps(_triangles(8)), run_production=False, machine=LASER)['design']
    saved = nesting.TRUE_SHAPE_MAX_PARTS
    try:
        nesting.TRUE_SHAPE_MAX_PARTS = 0
        boxes = nesting.nest(design, {'title_block': 14.0})
    finally:
        nesting.TRUE_SHAPE_MAX_PARTS = saved
    shaped = nesting.nest(design, {'title_block': 14.0})
    assert boxes['sheet_count'] == 2 and shaped['sheet_count'] == 1
    assert shaped['issues'] == [] and not shaped['unplaced']                   # the independent polygon check agrees
    assert {p['rotation'] for p in shaped['placements']} & {180.0, 270.0}      # parts turned to interlock
    pkg = production_package(design, {'compensate_kerf': True})
    assert pkg['ready_for_production'] and pkg['nesting']['sheet_count'] == 1


def test_raster_covers_the_shape():
    from board_engine.nesting import _raster, _runs
    rows, w, h, ox, oy = _raster([[0, 0], [10, 0], [10, 10], [0, 10]], 1.0, 0.5)
    assert (w, h) == (11, 11) and all(m == (1 << 11) - 1 for m in rows)       # a square plus its growth fills the grid
    assert _runs(0b1110011) == [(0, 2), (4, 3)]


# --- 9. LightBurn project ------------------------------------------------------------------------------------

def test_lightburn_project_structure(client):
    import math
    import re
    import xml.etree.ElementTree as ET
    z = zipfile.ZipFile(io.BytesIO(client.post('/api/v1/canvas/export', headers=VW,
                                               json={'source': json.dumps(SIGN), 'machine': dict(LASER, cut_speed=12)}).data))
    name = next(n for n in z.namelist() if n.endswith('-sheet1.lbrn2'))
    root = ET.fromstring(z.read(name))
    assert root.tag == 'LightBurnProject' and root.get('FormatVersion') == '1'
    layers = {c.find('name').get('Value'): (c.get('type'), c.find('index').get('Value'), c.find('speed').get('Value'))
              for c in root.findall('CutSetting')}
    assert layers['Cut outline'] == ('Cut', '2', '12') and layers['Engrave'][1] == '6' and layers['Labels'][1] == '0'
    for sh in root.findall('Shape'):
        assert sh.get('Type') in ('Path', 'Ellipse') and sh.get('CutIndex') in {v[1] for v in layers.values()}
        if sh.get('Type') == 'Path':
            verts = re.findall(r'V([-\d.]+) ([-\d.]+)c0x1c1x1', sh.find('VertList').text)
            prims = sh.find('PrimList').text
            assert verts and (prims == 'LineClosed' or prims == ''.join(f'L{i} {i + 1}' for i in range(len(verts) - 1)))
            assert all(0 <= float(x) <= 600 and 0 <= float(y) <= 400 for x, y in verts)   # on the bed, y up


def test_lightburn_arcs_become_short_lines():
    import math
    from board_engine.lightburn import _points
    pts = [[10 * math.cos(math.radians(a)), 10 * math.sin(math.radians(a))] for a in (0, 45, 90)] + [[-10, 10], [-10, 0]]
    out = _points({'points': pts, 'arcs': [{'start': 0, 'end': 2, 'center': [0, 0]}], 'closed': True})
    on_arc = [q for q in out if abs(math.hypot(*q) - 10) < 1e-6]
    assert len(out) > 30 and len(on_arc) >= 30                           # 90 deg of r = 10 in ~0.5 mm steps


# --- 2. direct AI generation (provider calls replaced by a stub: no network, no cost) -------------------------

ED = {'Authorization': 'Bearer ed'}


def test_ai_provider_selection(monkeypatch):
    from board_engine import ai_client
    for k in ('GEMINI_API_KEY', 'ANTHROPIC_API_KEY', 'AI_PROVIDER', 'GEMINI_MODEL', 'ANTHROPIC_MODEL'):
        monkeypatch.delenv(k, raising=False)
    assert ai_client.provider() == (None, None)
    with pytest.raises(ai_client.AIError):
        ai_client.complete('x')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-test')
    assert ai_client.provider() == ('claude', 'claude-opus-5-5')
    monkeypatch.setenv('GEMINI_API_KEY', 'g-test')
    assert ai_client.provider()[0] == 'gemini'
    monkeypatch.setenv('AI_PROVIDER', 'claude')
    assert ai_client.provider()[0] == 'claude'


def test_ai_status_never_shows_the_key(client, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'secret-key-123')
    monkeypatch.delenv('AI_PROVIDER', raising=False)
    r = client.get('/api/v1/canvas/ai-status', headers=VW)
    assert r.json['provider'] == 'gemini' and 'secret-key-123' not in r.data.decode()


def test_ai_generate_and_fix_flow(client, monkeypatch):
    from board_engine import ai_client
    prompts = []
    broken = copy.deepcopy(BOX)
    broken['boards'][1]['position'][1] = 10                                # wall 4 mm above the base: a gap error
    replies = iter([f"Here you go:\n```json\n{json.dumps(broken)}\n```\nEnjoy!", json.dumps(BOX)])
    monkeypatch.setattr(ai_client, 'complete', lambda p: (prompts.append(p), next(replies))[1])
    monkeypatch.setenv('GEMINI_API_KEY', 'g')
    r = client.post('/api/v1/canvas/ai-generate', headers=ED, json={'title': 'Box', 'thickness': 6, 'machine': LASER})
    assert r.status_code == 200 and json.loads(r.json['source']) == broken    # prose stripped, JSON kept
    assert 'Laser box' not in prompts[0] and '600 × 400 mm bed' in prompts[0]  # the strict prompt with the laser settings
    f = client.post('/api/v1/canvas/ai-fix', headers=ED, json={'source': r.json['source'], 'machine': LASER}).json
    assert f['changed'] and json.loads(f['source']) == BOX and 'CONNECTION_GAP' in prompts[1]
    assert '{"patch": {' in prompts[1]                  # the server's repair asks for a patch, not the whole design
    clean = client.post('/api/v1/canvas/ai-fix', headers=ED, json={'source': json.dumps(BOX), 'machine': LASER}).json
    assert {k: clean[k] for k in ('ok', 'source', 'problems', 'changed')} == \
        {'ok': True, 'source': json.dumps(BOX), 'problems': 0, 'changed': False} and len(prompts) == 2
    assert clean['accepted'] is True


def test_ai_errors_and_permissions(client, monkeypatch):
    from board_engine import ai_client

    def boom(_p):
        raise ai_client.AIError('Gemini answered HTTP 429: quota')
    monkeypatch.setattr(ai_client, 'complete', boom)
    r = client.post('/api/v1/canvas/ai-generate', headers=ED, json={'title': 'Box'})
    assert r.status_code == 502 and 'quota' in r.json['error']['message']
    assert client.post('/api/v1/canvas/ai-generate', headers=VW, json={'title': 'Box'}).status_code == 403
    assert client.post('/api/v1/canvas/ai-generate', headers=ED, json={}).status_code == 400


def test_gemini_request_shape(monkeypatch):
    from board_engine import ai_client
    sent = {}

    class Resp:
        status_code = 200

        def json(self):
            return {'candidates': [{'content': {'parts': [{'text': '{"boards": []}'}]}}]}

    def fake_post(url, **kw):
        sent.update(url=url, **kw)
        return Resp()
    import requests
    monkeypatch.setattr(requests, 'post', fake_post)
    monkeypatch.setenv('GEMINI_API_KEY', 'g-key')
    monkeypatch.delenv('AI_PROVIDER', raising=False)
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-test')
    assert ai_client.complete('design a box') == '{"boards": []}'
    assert sent['url'].endswith('/models/gemini-test:generateContent') and sent['headers']['x-goog-api-key'] == 'g-key'
    assert 'g-key' not in sent['url'] and sent['json']['contents'][0]['parts'][0]['text'] == 'design a box'


def test_claude_request_shape(monkeypatch):
    import types
    import anthropic
    from board_engine import ai_client
    seen = {}

    def message(stop, text):
        return types.SimpleNamespace(stop_reason=stop, content=[types.SimpleNamespace(type='text', text=text)])

    class FakeStream:
        def __init__(self, msg):
            self.msg = msg

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return self.msg

    result = {'msg': message('end_turn', '{"boards": []}')}

    class FakeClient:
        def __init__(self, **kw):
            self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(stream=self.stream))

        def stream(self, **kw):
            seen.update(kw)
            return FakeStream(result['msg'])
    monkeypatch.setattr(anthropic, 'Anthropic', FakeClient)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('ANTHROPIC_MODEL', raising=False)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-test')
    assert ai_client.complete('design a box') == '{"boards": []}'
    assert seen['model'] == 'claude-opus-5-5' and seen['fallbacks'] == 'default'
    assert seen['betas'] == ['server-side-fallback-2026-07-01'] and seen['messages'][0]['content'] == 'design a box'
    result['msg'] = message('refusal', '')
    with pytest.raises(ai_client.AIError, match='declined'):
        ai_client.complete('x')
