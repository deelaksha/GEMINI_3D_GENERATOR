"""Performance (audit 2026-11-28, phase 4): the spatial indexes and incremental plates change nothing but speed; the
time budget really stops a compile; the per-caller board cap; joining stays near-linear in the number of slots."""
import json
import time

import pytest

from board_engine import canvas as C, model, validation
from board_engine.canvas_prompt import COMPLEX_EXAMPLE, EXAMPLE, STRUCTURES_EXAMPLE


def slats(n, step=21):
    cols = min(n, 100)
    rows = max(1, -(-n // cols))
    rep = {'count': cols, 'step': [step, 0, 0]}
    if rows > 1:
        rep['rows'] = {'count': rows, 'step': [0, 0, 80]}
    return {'format': 'board-design/v1', 'product': {'name': 'grid'}, 'material': {'type': 'plywood', 'thickness': 6},
            'boards': [{'id': 'BASE', 'position': [0, 0, 0], 'size': [20 + step * cols, 6, 40 + 80 * rows]},
                       {'id': 'S', 'position': [10, 6, 30], 'size': [6, 40, 50], 'repeat': rep}],
            'connections': [{'id': 'a', 'type': 'tab_slot', 'board': 'S*', 'into': 'BASE', 'tabs': 1}]}


def _norm(r):
    r = json.loads(json.dumps(r, default=str))
    for part in ('design', 'model3d'):
        for j in (r.get(part) or {}).get('joints', []):
            j.pop('joined_at', None)
    return json.dumps({k: r.get(k) for k in ('ok', 'diagnostics', 'design', 'summary')}, sort_keys=True)


def _brute_force(monkeypatch):
    """Every index off: full scans and a fresh plate per board, as before the phase-4 changes."""
    monkeypatch.setattr(validation, '_features_in', lambda plate, ax, lo, hi: list(range(len(plate.feature_polys))))
    monkeypatch.setattr(model.Plate, '_features_near_x', lambda self, x, tol: range(len(self._feature_boxes)))
    monkeypatch.setattr(model, 'plate_for', lambda design, comp: model.Plate(design, comp))
    monkeypatch.setattr(validation, 'plate_for', lambda design, comp: model.Plate(design, comp))
    from board_engine import joining
    monkeypatch.setattr(joining, 'plate_for', lambda design, comp: model.Plate(design, comp))


DESIGNS = [EXAMPLE, COMPLEX_EXAMPLE, STRUCTURES_EXAMPLE, slats(120), slats(40, step=7)]   # step 7: slots crowd


@pytest.mark.parametrize('k', range(len(DESIGNS)))
def test_indexes_give_exactly_the_brute_force_result(k, monkeypatch):
    src = json.dumps(DESIGNS[k])
    fast = _norm(C.compile_source(src, run_production=False))
    C._SNAPSHOTS.clear()
    validation._INTERFERENCE_CACHE.clear()
    _brute_force(monkeypatch)
    assert _norm(C.compile_source(src + ' ', run_production=False)) == fast


def test_the_board_cap_stops_an_oversized_expansion():
    r = C.compile_source(json.dumps(slats(300)), run_production=False, max_boards=200)
    assert not r['ok'] and r['diagnostics'][-1]['code'] == 'STRUCTURE_TOO_LARGE'
    assert C.compile_source(json.dumps(slats(150)), run_production=False, max_boards=250)['ok']     # 201 boards


def test_the_time_budget_stops_a_long_compile_near_its_limit():
    t = time.monotonic()
    r = C.compile_source(json.dumps(slats(3000)), run_production=False, time_budget=0.5)
    took = time.monotonic() - t
    assert any(d['code'] == 'COMPILE_TIMEOUT' for d in r['diagnostics'])
    assert took < 15, took          # scaled budget 0.5 s x 3001 / 900 boards = 1.7 s, plus the stage in progress


@pytest.mark.slow
def test_a_thousand_slots_in_one_board_compile_quickly():
    t = time.monotonic()
    r = C.compile_source(json.dumps(slats(1000)), run_production=False)
    assert r['ok'] and time.monotonic() - t < 40


def test_swept_self_intersections_equal_the_full_double_loop():
    import random
    from board_engine import geometry as G

    def brute(poly):
        n = len(poly)
        return [(i, j) for i in range(n) for j in range(i + 1, n) if (j + 1) % n != i and (i + 1) % n != j
                and G.segments_intersect(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n])]
    random.seed(5)
    for _ in range(1500):
        poly = [[random.uniform(0, 50), random.uniform(0, 50)] for _ in range(random.randint(3, 90))]
        if random.random() < 0.3:
            poly = [[round(x), round(y)] for x, y in poly]          # collinear and touching edges
        assert G.self_intersections(poly) == brute(poly)
