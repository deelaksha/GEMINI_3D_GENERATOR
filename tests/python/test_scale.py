"""Large designs: near-pair search instead of all pairs, parallel collision checks, and the prompt that asks for them."""
import json
import random

from board_engine import canvas, validation
from board_engine.geometry import near_pairs
from board_engine.model import build_plates


def _all_pairs(boxes, gap):
    d = len(boxes[0][0]) if boxes else 0
    return [(i, j) for i in range(len(boxes)) for j in range(i + 1, len(boxes))
            if all(boxes[i][0][k] <= boxes[j][1][k] + gap and boxes[j][0][k] <= boxes[i][1][k] + gap for k in range(d))]


def test_near_pairs_finds_exactly_the_pairs_a_full_double_loop_would():
    rnd = random.Random(7)
    for _ in range(300):
        dim, gap = rnd.choice((2, 3, 5)), rnd.choice((0, 0.5, 5, 50))
        boxes = []
        for _ in range(rnd.randint(0, 50)):
            lo = [rnd.choice((rnd.uniform(-500, 500), rnd.randint(-20, 20) * 5.0)) for _ in range(dim)]
            big = rnd.random() < 0.1                                   # a base plate under everything
            size = [0.0 if dim == 5 else rnd.uniform(500, 3000) if big else rnd.uniform(0, 300) for _ in range(dim)]
            boxes.append((lo, [lo[k] + size[k] for k in range(dim)]))
        assert near_pairs(boxes, gap) == _all_pairs(boxes, gap)


def test_parallel_collision_checks_match_checking_one_by_one(monkeypatch):
    from conftest import base_plate, wall
    design = {'id': 'd', 'components': [base_plate(), wall(), dict(wall(), id='WALL2')], 'joints': [],
              'material': {'type': 'plywood', 'thickness': 3}}
    plates = build_plates(design)
    pairs = [('BASE', 'WALL'), ('BASE', 'WALL2'), ('WALL', 'WALL2')] * 40
    validation._INTERFERENCE_CACHE.clear()
    one_by_one = [validation.plate_interference(plates[a], plates[b]) for a, b in pairs]
    validation._INTERFERENCE_CACHE.clear()
    monkeypatch.setattr(validation, 'PARALLEL_PAIRS', 0)
    monkeypatch.setattr(validation, 'engine_workers', lambda: 2)
    assert validation.parallel_interference(plates, pairs) == one_by_one
    assert any(one_by_one)                                     # the two identical walls really do collide


def test_compiles_the_same_with_and_without_parallel_checks(monkeypatch):
    src = open('board_engine/examples/my_home.json').read()
    def compiled():
        validation._INTERFERENCE_CACHE.clear()
        r = canvas.compile_source(src, run_production=False)
        return sorted((d['code'], d['severity'], d.get('board')) for d in r['diagnostics']), r['summary']
    monkeypatch.setattr(canvas, 'SNAPSHOT_DIR', None)
    sequential = compiled()
    monkeypatch.setattr(validation, 'PARALLEL_PAIRS', 0)
    monkeypatch.setattr(validation, 'engine_workers', lambda: 3)
    assert compiled() == sequential


def test_the_design_prompt_asks_for_rich_designs_and_explains_large_ones():
    from board_engine.canvas_prompt import DESIGN_QUALITY, DESIGN_TEAM, build_prompt
    p = build_prompt('Clock tower', '', None, 3, 'interlocking', style='full')
    assert DESIGN_QUALITY in p and 'DESIGNER' in DESIGN_TEAM and 'plan.concept' in p
    assert 'Very large models' in p and '"instances"' in p and 'creative AND economical' in p and 'plan.economy' in p


def test_fixes_keep_the_detail_and_change_requests_get_the_quality_rules():
    from board_engine.canvas_prompt import DESIGN_QUALITY, EXAMPLE, build_repair_prompt, build_update_prompt
    src = json.dumps(EXAMPLE)
    rep = build_repair_prompt(src, [{'severity': 'error', 'code': 'COLLISION', 'message': 'overlap'}])
    upd = build_update_prompt(src, 'make it more elegant')
    assert 'Never simplify to make a problem go away' in rep and DESIGN_QUALITY not in rep    # a fix stays a fix
    assert DESIGN_QUALITY in upd and 'never simplifying what is already shaped' in upd


def test_workers_are_stopped_when_the_time_budget_runs_out():
    import time
    import pytest
    from board_engine import parallel
    from board_engine.deadline import TimeBudgetExceeded
    calls = [0]

    def check():
        calls[0] += 1
        if calls[0] > 1:
            raise TimeBudgetExceeded(1)
    t = time.time()
    with pytest.raises(TimeBudgetExceeded):
        parallel.run([('time.sleep', (30,))] * 3, 3, check=check)
    assert time.time() - t < 15                                # the sleeping workers were killed, not waited for


def test_a_failing_worker_raises_instead_of_hanging():
    import pytest
    from board_engine import parallel
    assert parallel.run([('math.sqrt', (16,)), ('math.hypot', (3, 4))], 2) == [4.0, 5.0]
    with pytest.raises(RuntimeError, match='ValueError'):
        parallel.run([('math.sqrt', (-1,))], 1)


def test_the_joining_index_only_follows_a_list_that_grows_at_its_end():
    g = validation.GrowingJoints()
    j1 = {'id': 'a', 'type': 'tab_slot', 'a': 'X', 'b': 'Y', 'slot': 's1', 'status': 'joined'}
    j2 = {'id': 'b', 'type': 'tab_slot', 'a': 'Z', 'b': 'Y', 'slot': 's1', 'status': 'joined'}
    assert g.sync([j1]) and g.sync([j1, j2]) and g.slots[('Y', 's1')] == ['a', 'b']
    assert not g.sync([j1]) and not g.sync([dict(j1), dict(j2)])   # shorter, or another list: callers scan instead


def test_a_design_far_over_200_operations_imports_into_the_studio(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv('BOARD_INSTANCE_DIR', str(tmp_path))
    monkeypatch.setenv('BOARD_API_KEYS', 'ed:editor')
    monkeypatch.setenv('BOARD_SKIP_SEED', '1')
    monkeypatch.setattr(canvas, 'SNAPSHOT_DIR', None)
    import app as app_module
    importlib.reload(app_module)
    c, H = app_module.app.test_client(), {'Authorization': 'Bearer ed'}
    src = open('board_engine/examples/my_home.json').read()          # 341 boards + 466 joints = 807 operations
    c.post('/api/v1/designs', headers=H, json={'id': 'home', 'name': 'Home'})
    r = c.post('/api/v1/canvas/import', headers=H, json={'source': src, 'target': 'home'})
    assert r.status_code == 200, r.json
    d = c.get('/api/v1/designs/home', headers=H).json['design']
    assert len(d['components']) == 341 and len([j for j in d['joints'] if j['status'] == 'joined']) == 466
