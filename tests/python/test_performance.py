"""Speed-ups that must not change results: snapshot reuse, articulation points, early nesting stop."""
import json
import random

from board_engine import canvas as C
from board_engine.manufacturing import _articulation_points, _connected
from test_canvas import EXAMPLE, cabinet


def _norm(r):
    r = json.loads(json.dumps(r, default=str))
    for d in r['diagnostics']:
        d.pop('joined_at', None)
    for part in ('design', 'model3d'):
        for j in (r.get(part) or {}).get('joints', []):
            j.pop('joined_at', None)
    return json.dumps(r, sort_keys=True)


def test_production_pass_from_the_fast_pass_snapshot_is_identical(tmp_path):
    src = json.dumps(cabinet(), indent=2)
    full = C.compile_source(src, run_production=True)
    C._SNAPSHOTS.clear()
    old_dir, C.SNAPSHOT_DIR = C.SNAPSHOT_DIR, str(tmp_path)
    try:
        C.compile_source(src, run_production=False)
        assert C._recall(next(iter(C._SNAPSHOTS))) is not None
        assert _norm(C.compile_source(src, run_production=True)) == _norm(full)
        C._SNAPSHOTS.clear()                                  # another worker process: the disk copy is used
        assert _norm(C.compile_source(src, run_production=True)) == _norm(full)
        other = C.compile_source(src.replace('"TOP"', '"TOP2"'), run_production=True)   # different code: full compile
        assert other['design'] and any(c['id'] == 'TOP2' for c in other['design']['components'])
    finally:
        C.SNAPSHOT_DIR = old_dir


def test_articulation_points_match_brute_force():
    random.seed(7)
    for _ in range(500):
        n = random.randint(2, 12)
        edges = {(v, random.randrange(v)) for v in range(1, n)}
        edges |= {tuple(random.sample(range(n), 2)) for _ in range(random.randint(0, 2 * n))}
        cons = [(a, b, 'k', None, None) for a, b in edges]
        assert _articulation_points(range(n), cons) == {v for v in range(n) if not _connected(set(range(n)) - {v}, cons)}


def test_nesting_early_stop_keeps_the_same_layout(monkeypatch):
    from board_engine import nesting
    d = C.compile_source(json.dumps(EXAMPLE), run_production=False)['design']
    fast = nesting.nest(d)
    monkeypatch.setattr(nesting.math, 'ceil', lambda v: -1)   # the bound is never reached: every order is tried
    assert json.dumps(nesting.nest(d), sort_keys=True) == json.dumps(fast, sort_keys=True)
