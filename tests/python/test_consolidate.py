"""Board consolidation: flat pieces in one plane that touch are cut as one board (exact outline, gaps as openings,
internal connections gone); moving, shaped, differently coloured and partly repeated pieces stay separate; repeated
openings."""
import copy
import json

import pytest

from board_engine import canvas
from board_engine.consolidate import _union


@pytest.fixture(autouse=True)
def _no_snapshots(monkeypatch):
    monkeypatch.setattr(canvas, 'SNAPSHOT_DIR', None)


def fence(**top):
    boards = [{'id': 'BASE', 'position': [0, 0, 0], 'size': [400, 6, 100]}]
    boards += [{'id': f'POST-{k + 1}', 'position': [10 + 38 * k, 6, 50], 'size': [12, 120, 6], 'color': '#a33'} for k in range(10)]
    boards += [{'id': 'RAIL-TOP', 'position': [10, 100, 50], 'size': [354, 16, 6], 'color': '#a33'},
               {'id': 'RAIL-LOW', 'position': [10, 6, 50], 'size': [354, 16, 6], 'color': '#a33'}]
    conns = [{'type': 'tab_slot', 'board': f'POST-{k + 1}', 'into': 'BASE'} for k in range(10)] + \
            [{'type': 'tab_slot', 'board': 'RAIL-LOW', 'into': 'BASE'}]
    return {'format': 'board-design/v1', 'product': {'name': 'fence'}, **top,
            'material': {'type': 'plywood', 'thickness': 6, 'kerf': 0.15}, 'boards': boards, 'connections': conns}


def compiled(d):
    r = canvas.compile_source(json.dumps(d), run_production=False, machine={'coloring': True})
    return r, [x for x in r['diagnostics'] if x['severity'] == 'error']


def test_a_fence_of_posts_and_rails_becomes_one_panel_with_its_gaps_cut_out():
    r, errors = compiled(fence())
    assert not errors, [e['message'] for e in errors]
    panel = next(c for c in r['design']['components'] if c['id'] == 'POST-PANEL')
    assert len(r['design']['components']) == 2
    assert sorted(f['id'] for f in panel['features'] if f['id'].startswith('gap-')) == [f'gap-{k}' for k in range(1, 10)]
    rep = r['consolidation']
    assert rep['applied'] and rep['boards_before'] == 13 and rep['boards_after'] == 2 and rep['connections_removed'] == 10
    assert [d['code'] for d in r['diagnostics'] if d['code'].startswith('CONSOL')] == ['CONSOLIDATED']
    assert all(j['status'] == 'joined' for j in r['design']['joints']) and {j['a'] for j in r['design']['joints']} == {'POST-PANEL'}


def test_the_union_is_exact():
    outer, holes = _union([(0, 0, 10, 2), (0, 8, 10, 10), (0, 0, 2, 10), (8, 0, 10, 10), (4, 0, 6, 12)])
    area = lambda p: abs(sum(p[k][0] * p[(k + 1) % len(p)][1] - p[(k + 1) % len(p)][0] * p[k][1] for k in range(len(p)))) / 2
    assert area(outer) == 100 + 4 and len(holes) == 2 and sorted(area(h) for h in holes) == [12, 12]
    assert _union([(0, 0, 1, 1), (1, 1, 2, 2), (0, 1, 1, 3), (1, 2, 2, 3)])[0] is not None
    assert _union([(0, 0, 1, 1), (1, 1, 2, 2)])[0] is None             # meeting only at a corner


def test_with_consolidate_false_it_is_only_suggested_with_a_working_fix():
    src = json.dumps(fence(consolidate=False))
    r = canvas.compile_source(src, run_production=False)
    tip = next(d for d in r['diagnostics'] if d['code'] == 'CONSOLIDATE')
    assert 'can be cut as 1 board(s) instead of 12' in tip['message']
    fixed = canvas.apply_code_fix(src, tip['fixes'][0])
    assert canvas.compile_source(fixed, run_production=False)['ok']


def test_a_lattice_window_of_bars_becomes_one_panel():
    bars = [(0, 0, 200, 10), (0, 190, 200, 200), (0, 0, 10, 200), (190, 0, 200, 200)]       # frame
    bars += [(60 * k + 5, 0, 60 * k + 15, 200) for k in (1, 2)] + [(0, 60 * k + 5, 200, 60 * k + 15) for k in (1, 2)]
    boards = [{'id': 'SILL', 'position': [-20, 0, -20], 'size': [240, 6, 46]}]
    boards += [{'id': f'BAR-{n}', 'position': [u, 6 + v, 0], 'size': [u1 - u, v1 - v, 6]} for n, (u, v, u1, v1) in enumerate(bars)]
    d = {'format': 'board-design/v1', 'product': {'name': 'window'}, 'material': {'type': 'plywood', 'thickness': 6, 'kerf': 0.15},
         'boards': boards, 'connections': [{'type': 'tab_slot', 'board': 'BAR-0', 'into': 'SILL'}]}
    r, errors = compiled(d)
    assert not errors, [e['message'] for e in errors]
    panel = next(c for c in r['design']['components'] if c['id'].endswith('-PANEL'))
    assert len([f for f in panel['features'] if f['id'].startswith('gap-')]) == 9


def test_moving_and_differently_coloured_pieces_stay_separate_but_shaped_ones_join():
    d = fence()
    d['boards'][1]['color'] = '#00f'                                    # POST-1 another colour
    d['boards'][2]['profile'] = {'shape': 'polygon', 'points': [[0, 0], [12, 0], [12, 110], [6, 120], [0, 110]]}
    d['motions'] = [{'id': 'swing', 'type': 'rotate', 'boards': ['POST-3'], 'on': 'BASE', 'axis': 'x',
                     'pivot': [86, 6, 50], 'range': [0, 10]}]
    r = canvas.compile_source(json.dumps(d), run_production=False, machine={'coloring': True})
    merged = r['consolidation']['groups'][0]['from']
    assert not {'POST-1', 'POST-3'} & set(merged) and {'POST-2', 'POST-4'} <= set(merged)


def test_a_repeated_board_is_merged_whole_or_not_at_all():
    d = fence()
    d['boards'] = [b for b in d['boards'] if not b['id'].startswith('POST-')] + [
        {'id': 'POST', 'position': [10, 6, 50], 'size': [12, 120, 6], 'color': '#a33', 'repeat': {'count': 10, 'step': [38, 0, 0]}}]
    d['connections'] = [{'type': 'tab_slot', 'board': 'RAIL-LOW', 'into': 'BASE'}]
    r, errors = compiled(d)
    assert not errors and len(r['consolidation']['groups'][0]['from']) == 12
    d['boards'][-1]['repeat']['count'] = 11                             # the 11th post stands apart: no partial merge
    r = canvas.compile_source(json.dumps(d), run_production=False, machine={'coloring': True})
    assert not r['consolidation']['groups'] and 'some copies' in r['consolidation']['skipped'][0]['reason']


def test_openings_can_repeat_in_a_row_and_a_grid():
    d = {'format': 'board-design/v1', 'product': {'name': 'screen'}, 'material': {'type': 'plywood', 'thickness': 6, 'kerf': 0.15},
         'boards': [{'id': 'SCREEN', 'position': [0, 0, 0], 'size': [300, 200, 6],
                     'openings': [{'id': 'slit', 'kind': 'opening', 'shape': 'rect', 'center': [30, 50, 3], 'size': [10, 60],
                                   'repeat': {'count': 12, 'step': [20, 0, 0]}, 'rows': {'count': 2, 'step': [0, 100, 0]}}]}],
         'connections': []}
    r, errors = compiled(d)
    assert not errors, [e['message'] for e in errors]
    feats = r['design']['components'][0]['features']
    assert len(feats) == 24 and {f['id'] for f in feats} >= {'slit-1-1', 'slit-2-12'}
    d['boards'][0]['openings'][0]['repeat'] = {'count': 0, 'step': [1, 0, 0]}
    assert 'OPENING_INVALID' in [e['code'] for e in compiled(d)[1]]


def test_the_prompt_teaches_consolidation():
    from board_engine.canvas_prompt import spec_markdown
    spec = spec_markdown()
    assert '## Fewer, smarter boards' in spec and '"repeat"' in spec and 'consolidate' in spec


def picket(k):
    return {'id': f'PICKET-{k + 1}', 'position': [10 + 38 * k, 6, 50], 'size': [12, 130, 6], 'color': '#a33',
            'profile': {'shape': 'polygon', 'points': [[0, 0], [12, 0], [12, 120], [6, 130], [0, 120]]}}


def test_shaped_pickets_merge_with_their_rails_into_one_panel():
    d = fence()
    d['boards'] = [b for b in d['boards'] if not b['id'].startswith('POST-')] + [picket(k) for k in range(10)]
    d['connections'] = [{'type': 'tab_slot', 'board': 'RAIL-LOW', 'into': 'BASE'}]
    r, errors = compiled(d)
    assert not errors, [e['message'] for e in errors]
    assert len(r['design']['components']) == 2
    g = r['consolidation']['groups'][0]
    assert len(g['from']) == 12 and g['openings'] == 9
    panel = next(c for c in r['design']['components'] if c['id'] == g['board'])
    top = max(p[1] for p in panel['outline']) - min(p[1] for p in panel['outline'])
    assert top == pytest.approx(130, abs=0.2)                           # the pointed tops are kept


def test_an_arched_top_and_round_ornament_merge_with_the_frame():
    boards = [{'id': 'SILL', 'position': [-20, 0, -20], 'size': [240, 6, 46]},
              {'id': 'JAMB-L', 'position': [0, 6, 0], 'size': [20, 200, 6]},
              {'id': 'JAMB-R', 'position': [180, 6, 0], 'size': [20, 200, 6]},
              {'id': 'ARCH', 'position': [0, 186, 0], 'size': [200, 110, 6],      # a half-ring sitting on the jambs
               'profile': {'shape': 'path', 'start': [0, 0], 'segments': [
                   {'line': [20, 0]}, {'arc': {'to': [180, 0], 'radius': 80, 'clockwise': True}},
                   {'line': [200, 0]}, {'arc': {'to': [0, 0], 'radius': 100}}]}},
              {'id': 'SUN', 'position': [80, 270, 0], 'size': [40, 40, 6],
               'profile': {'shape': 'circle', 'center': [20, 20], 'diameter': 40}}]
    d = {'format': 'board-design/v1', 'product': {'name': 'gate'}, 'material': {'type': 'plywood', 'thickness': 6, 'kerf': 0.15},
         'boards': boards, 'connections': [{'type': 'tab_slot', 'board': 'JAMB-L', 'into': 'SILL'},
                                           {'type': 'tab_slot', 'board': 'JAMB-R', 'into': 'SILL'}]}
    r, errors = compiled(d)
    assert not errors, [e['message'] for e in errors]
    g = r['consolidation']['groups'][0]
    assert sorted(g['from']) == ['ARCH', 'JAMB-L', 'JAMB-R', 'SUN']
    assert len(r['design']['joints']) >= 1 and len(r['design']['components']) == 2


def test_shaped_pieces_touching_only_at_a_point_stay_apart():
    d = fence()
    d['boards'] = [d['boards'][0],
                   {'id': 'DIA-1', 'position': [0, 6, 50], 'size': [40, 40, 6],
                    'profile': {'shape': 'polygon', 'points': [[20, 0], [40, 20], [20, 40], [0, 20]]}},
                   {'id': 'DIA-2', 'position': [40, 6, 50], 'size': [40, 40, 6],
                    'profile': {'shape': 'polygon', 'points': [[20, 0], [40, 20], [20, 40], [0, 20]]}}]
    d['connections'] = []
    r = canvas.compile_source(json.dumps(d), run_production=False)
    assert not r['consolidation']['groups']


def test_without_shapely_shaped_boards_are_left_with_the_reason(monkeypatch):
    import builtins
    real = builtins.__import__
    monkeypatch.setattr(builtins, '__import__', lambda name, *a, **k: (_ for _ in ()).throw(ImportError(name))
                        if name.startswith('shapely') else real(name, *a, **k))
    d = fence()
    d['boards'] = [b for b in d['boards'] if not b['id'].startswith('POST-')] + [picket(k) for k in range(10)]
    r = canvas.compile_source(json.dumps(d), run_production=False)
    assert any('shapely' in s['reason'] for s in r['consolidation']['skipped'])
    assert not any(b.startswith('PICKET') for g in r['consolidation']['groups'] for b in g['from'])


def test_a_merge_that_would_not_fit_the_sheet_is_not_made():
    d = fence()
    for b in d['boards']:                              # stretch the fence to 700 mm: over a 600 x 400 laser bed
        if b['id'].startswith('RAIL'):
            b['size'][0] = 700
    d['boards'][0]['size'][0] = 760
    d['boards'] += [{'id': f'POST-{k + 11}', 'position': [10 + 38 * k, 6, 50], 'size': [12, 120, 6], 'color': '#a33'}
                    for k in range(10, 18)]
    laser = {'kerf': 0.15, 'sheet': {'width': 600, 'height': 400}, 'coloring': True}
    r = canvas.compile_source(json.dumps(d), run_production=False, machine=laser)
    assert not r['consolidation']['groups'] and 'larger than the stock sheet' in r['consolidation']['skipped'][0]['reason']
    r = canvas.compile_source(json.dumps(d), run_production=False, machine={'coloring': True})
    assert r['consolidation']['groups']                # plywood stock (2500 x 1250) takes it


def test_the_prompt_splits_what_one_piece_cannot_make():
    from board_engine.canvas_prompt import build_prompt, build_repair_prompt
    p = build_prompt('Anything')
    for step in ('TOO LARGE', 'CURVED IN TWO DIRECTIONS', 'CURVED IN ONE DIRECTION', 'MEETING AT AN ANGLE', 'TOO FRAGILE',
                 'TOO INTRICATE', 'CANNOT BE JOINED', 'A MECHANISM TOO COMPLEX'):
        assert step in p, step
    assert 'THROUGH A CONNECTOR' in p and 'Never drop, flatten or simplify a feature' in p
    assert 'never delete it' in build_repair_prompt('{}', [])
