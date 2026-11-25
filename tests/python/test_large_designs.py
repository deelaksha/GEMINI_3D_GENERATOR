"""Large designs: no practical board limit, and the checks stay fast enough for hundreds of boards."""
import itertools
import json
import random
import time

from board_engine.canvas import compile_source
from board_engine.validation import _close_pairs, _subtract, _subtract_sorted


def slats(count_a, count_b, step=21):
    length = 20 + step * max(count_a, count_b)
    return {'format': 'board-design/v1', 'product': {'name': 'slat bench'}, 'material': {'type': 'plywood', 'thickness': 6},
            'boards': [{'id': 'BASE', 'position': [0, 0, 0], 'size': [length, 6, 200]},
                       {'id': 'SLAT-A', 'position': [10, 6, 30], 'size': [6, 40, 50], 'repeat': {'count': count_a, 'step': [step, 0, 0]}},
                       {'id': 'SLAT-B', 'position': [10, 6, 120], 'size': [6, 40, 50], 'repeat': {'count': count_b, 'step': [step, 0, 0]}}],
            'connections': [{'id': 'a', 'type': 'tab_slot', 'board': 'SLAT-A', 'into': 'BASE', 'tabs': 1},
                            {'id': 'b', 'type': 'tab_slot', 'board': 'SLAT-B', 'into': 'BASE', 'tabs': 1}]}


def test_310_boards_compile_within_the_budget():
    t = time.time()
    r = compile_source(json.dumps(slats(154, 155)), run_production=False, time_budget=90)
    codes = {d['code'] for d in r['diagnostics'] if d['severity'] == 'error'}
    assert r['summary']['boards'] == 310 and r['summary']['joined'] == r['summary']['joints'] == 309
    assert not codes & {'STRUCTURE_INVALID', 'TOO_MANY_BOARDS', 'COMPILE_TIMEOUT', 'SCHEMA_ERROR'}
    assert time.time() - t < 60


def test_repeat_counts_above_200_and_the_runaway_guard():
    d = slats(2, 2)
    d['boards'][1]['repeat']['count'] = 250
    r = compile_source(json.dumps(d), run_production=False, time_budget=1)
    assert 'STRUCTURE_INVALID' not in {x['code'] for x in r['diagnostics']}
    d['boards'][1]['repeat']['count'] = 2_000_000
    t = time.time()
    r = compile_source(json.dumps(d), run_production=False)
    err = next(x for x in r['diagnostics'] if x['code'] == 'STRUCTURE_INVALID')
    assert 'more than 100,000 boards' in err['message'] and time.time() - t < 2


def test_close_pairs_finds_exactly_the_pairs_a_full_loop_needs():
    random.seed(3)
    for _ in range(300):
        polys = [[(x, y), (x + w, y), (x + w, y + h), (x, y + h)] for x, y, w, h in
                 ((random.uniform(0, 300), random.uniform(0, 100), random.uniform(1, 20), random.uniform(1, 8)) for _ in range(25))]
        gap = random.choice([0.0, 1.5, 3.0])
        box = lambda p: (min(q[0] for q in p), max(q[0] for q in p), min(q[1] for q in p), max(q[1] for q in p))
        want = [(i, j) for i, j in itertools.combinations(range(len(polys)), 2)
                if max(box(polys[j])[0] - box(polys[i])[1], box(polys[i])[0] - box(polys[j])[1],
                       box(polys[j])[2] - box(polys[i])[3], box(polys[i])[2] - box(polys[j])[3]) <= gap]
        assert _close_pairs(polys, gap) == want


def test_batch_subtraction_equals_one_at_a_time():
    random.seed(1)
    for _ in range(5000):
        xs, cur = [], random.uniform(-20, 20)
        for _ in range(random.randint(1, 4)):
            a = cur + random.uniform(0.1, 20)
            cur = a + random.uniform(0.1, 30)
            xs.append((a, cur))
        holes = [(h, h + random.uniform(0, 25)) for h in (random.uniform(-10, 210) for _ in range(random.randint(2, 12)))]
        ref = xs
        for h in holes:
            ref = _subtract(ref, [h])
        clean = lambda ivs: [(round(a, 9), round(b, 9)) for a, b in ivs if b - a > 1e-9]
        assert clean(_subtract_sorted(xs, holes)) == clean(ref)
