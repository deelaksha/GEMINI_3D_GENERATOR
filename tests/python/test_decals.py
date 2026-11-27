"""Printed artwork ("decals"): validation, colouring gate, upright lettering, storage, 3D model and print sheets."""
import copy
import io
import json
import re
import zipfile

import pytest

from board_engine import canvas
from board_engine import geometry as G
from board_engine.canvas_prompt import EXAMPLE
from board_engine.model import normalize_design

COLOURED = {'coloring': True}


@pytest.fixture(autouse=True)
def _no_snapshots(monkeypatch):
    monkeypatch.setattr(canvas, 'SNAPSHOT_DIR', None)


def decorated(**decals):
    d = copy.deepcopy(EXAMPLE)
    for bid, items in decals.items():
        b = next(x for x in d['boards'] if x['id'] == bid.replace('_', '-'))
        b['color'] = {'all': '#7a1d1d'}
        b['decals'] = items
    return d


def compiled(d, machine=COLOURED):
    return canvas.compile_source(json.dumps(d), run_production=False, machine=machine)


def comp(r, cid):
    return next(c for c in r['design']['components'] if c['id'] == cid)


def test_decals_reach_the_3d_model_and_survive_the_store():
    r = compiled(decorated(TOP=[{'face': 'front', 'color': 'gold', 'shape': 'rect', 'center': [600, 300], 'width': 400, 'height': 200},
                                {'face': 'back', 'color': '#000', 'text': 'UNDER', 'position': [600, 300], 'height': 40}]))
    assert r['ok'] and [d['face'] for d in comp(r, 'TOP')['decals']] == ['front', 'back']
    assert comp(r, 'TOP')['decals'][0]['color'] == '#ffd700'
    assert len(next(c for c in r['model3d']['components'] if c['id'] == 'TOP')['decals']) == 2
    stored = normalize_design(dict(r['design'], id='x'))
    assert len(next(c for c in stored['components'] if c['id'] == 'TOP')['decals']) == 2


def test_without_colouring_decals_are_left_out_with_a_note():
    r = compiled(decorated(TOP=[{'face': 'front', 'color': 'gold', 'shape': 'circle', 'center': [100, 100], 'diameter': 50}]),
                 machine={})
    assert 'decals' not in comp(r, 'TOP') and 'COLORS_IGNORED' in [x['code'] for x in r['diagnostics']]


@pytest.mark.parametrize('decal, code', [
    ({'face': 'front', 'color': 'gold', 'shape': 'circle', 'center': [5000, 100], 'diameter': 50}, 'DECAL_OUTSIDE_BOARD'),
    ({'face': 'side', 'color': 'gold', 'shape': 'circle', 'center': [100, 100], 'diameter': 50}, 'DECAL_INVALID'),
    ({'face': 'front', 'color': 'not-a-colour', 'shape': 'circle', 'center': [100, 100], 'diameter': 50}, 'DECAL_INVALID'),
    ({'face': 'front', 'color': 'gold'}, 'DECAL_INVALID'),
    ({'face': 'front', 'color': 'gold', 'text': 'A VERY LONG SIGN THAT CANNOT FIT', 'position': [600, 300], 'height': 200},
     'DECAL_OUTSIDE_BOARD'),
])
def test_bad_decals_are_explained(decal, code):
    assert code in [x['code'] for x in compiled(decorated(TOP=[decal]))['diagnostics'] if x['severity'] == 'error']


def _reading(r, cid):
    """World direction the lettering runs in and the direction its letters point up (first stroke -> last stroke)."""
    c = comp(r, cid)
    f = G.Frame(c['placement']['position'], c['placement']['rotation'])
    lines = c['decals'][0]['lines']
    world = [[f.to_world([q[0], q[1], 0.0]) for q in ln] for ln in lines]
    first, last = world[0], world[-1]
    mid = lambda ln: [sum(p[k] for p in ln) / len(ln) for k in range(3)]
    run = G.v_sub(mid(last), mid(first))
    return run


def test_lettering_reads_left_to_right_on_a_top_and_on_a_side_panel():
    top = compiled(decorated(TOP=[{'face': 'front', 'color': 'gold', 'text': 'ABCDEF', 'position': [600, 300], 'height': 60}]))
    assert _reading(top, 'TOP')[0] > 0                  # on the top it runs along +x: read from the front of the product
    r = compiled(decorated(LEG_R=[{'face': 'front', 'color': 'white', 'text': 'ABCDEF', 'position': [366, 280], 'height': 50},
                                  {'face': 'back', 'color': 'white', 'text': 'ABCDEF', 'position': [366, 280], 'height': 50}]))
    c = comp(r, 'LEG-R')
    f = G.Frame(c['placement']['position'], c['placement']['rotation'])
    front_n = f.dir_to_world([0.0, 0.0, 1.0])
    for k, n in ((0, front_n), (1, G.v_scale(front_n, -1.0))):
        lines = c['decals'][k]['lines']
        a, b = f.to_world([*lines[0][0], 0.0]), f.to_world([*lines[-1][0], 0.0])
        right = G.v_cross([0.0, 1.0, 0.0], n)           # a reader outside that face sees "right" here
        assert G.v_dot(G.v_sub(b, a), right) > 0, f"decal {k} must read left to right from outside its face"


def test_print_sheets_come_with_the_cut_files_and_the_back_is_mirrored(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv('BOARD_INSTANCE_DIR', str(tmp_path))
    monkeypatch.setenv('BOARD_API_KEYS', 'ed:editor')
    monkeypatch.setenv('BOARD_SKIP_SEED', '1')
    import app as app_module
    importlib.reload(app_module)
    d = decorated(LEG_R=[{'face': 'front', 'color': 'white', 'text': 'FRONT', 'position': [366, 280], 'height': 50},
                         {'face': 'back', 'color': 'white', 'text': 'BACK', 'position': [366, 280], 'height': 50}])
    r = app_module.app.test_client().post('/api/v1/canvas/export', headers={'Authorization': 'Bearer ed'},
                                          json={'source': json.dumps(d), 'machine': COLOURED})
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.data))
    front = z.read(next(n for n in z.namelist() if n.endswith('-print-front.svg'))).decode()
    back = z.read(next(n for n in z.namelist() if n.endswith('-print-back.svg'))).decode()
    assert '#7a1d1d' in front and '#7a1d1d' in back            # the face colour is printed under the lettering
    width = float(re.search(r'viewBox="0 0 ([\d.]+)', front).group(1))
    guide = lambda s: [float(v) for v in re.search(r'id="GUIDES".*?points="([^"]+)"', s, re.S).group(1).replace(',', ' ').split()[::2]]
    assert guide(back) == pytest.approx([width - x for x in guide(front)], abs=1e-3)   # same outline, mirrored left-right


@pytest.mark.parametrize('board, pos', [('TOP', [500, 300]), ('LEG-R', [300, 250]), ('MODESTY', [500, 150])])
def test_engraved_text_is_never_mirrored(board, pos):
    """'TT' engraved on boards thin along y (the top), x (a leg) and z (the modesty panel): seen from outside the
    engraved face, the second T lies to the right of the first and the bars are above the stems - never a mirror image."""
    d = copy.deepcopy(EXAMPLE)
    b = next(x for x in d['boards'] if x['id'] == board)
    b['engravings'] = [{'kind': 'engrave', 'text': 'TT', 'position': pos, 'height': 40}]
    r = canvas.compile_source(json.dumps(d), run_production=False)
    assert r['ok'], [x['message'] for x in r['diagnostics'] if x['severity'] == 'error']
    c = comp(r, board)
    f = G.Frame(c['placement']['position'], c['placement']['rotation'])
    marks = [m for m in c['marks'] if m['id'].startswith('text-1')]
    assert len(marks) == 4                                         # two strokes per T: the bar, then the stem
    world = [[f.to_world([q[0], q[1], 0.0]) for q in m['points']] for m in marks]
    mid = lambda ln: [sum(p[k] for p in ln) / len(ln) for k in range(3)]
    bar1, stem1, bar2, stem2 = (mid(w) for w in world)
    right, up = G.v_sub(bar2, bar1), G.v_sub(bar1, stem1)
    n = f.dir_to_world([0.0, 0.0, 1.0])                             # engravings are on the front (+z) face
    assert G.v_dot(G.v_cross(right, up), n) > 0
