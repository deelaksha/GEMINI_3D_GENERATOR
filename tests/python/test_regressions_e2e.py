"""Regression tests for the bugs confirmed by the end-to-end validation (PROJECT_AUDIT/END_TO_END_VALIDATION/11_BUG_TRACKER.md)."""
import copy
import json

import pytest

from board_engine.canvas import apply_code_fix, compile_source
from board_engine.canvas_prompt import EXAMPLE
from board_engine.operations import OperationRejected, apply_operation
from board_engine.views import production_package

P18 = {"type": "plywood", "thickness": 18}
P6 = {"type": "plywood", "thickness": 6}


def _src(boards, connections=None, material=P18, **top):
    d = {"format": "board-design/v1", "product": {"name": "t"}, "material": material, "boards": boards,
         "connections": [] if connections is None else connections}
    d.update(top)
    return json.dumps(d)


def _codes(r, sev='error'):
    return {d['code'] for d in r['diagnostics'] if d['severity'] == sev}


# BUG-002: a hole smaller than the kerf must never be cut (it came out with a negative radius) ------------------
def test_bug002_feature_smaller_than_kerf_is_rejected():
    r = compile_source(_src([{"id": "P", "position": [0, 0, 0], "size": [300, 18, 200],
                              "openings": [{"id": "pin", "kind": "hole", "shape": "circle", "center": [150, 9, 100], "diameter": 3}]}]))
    assert 'FEATURE_SMALLER_THAN_KERF' in _codes(r)
    assert not r['layout']['ready_for_production']
    radii = [p['radius'] for s in r['layout']['cut']['sheets'] for p in s['paths'] if p.get('shape') == 'circle']
    assert 'CUT_PATH_DEGENERATE' in {i['code'] for i in r['layout']['blocking_issues']} or all(x > 0 for x in radii)


def test_bug002_hole_wider_than_kerf_is_fine():
    r = compile_source(_src([{"id": "P", "position": [0, 0, 0], "size": [300, 18, 200],
                              "openings": [{"id": "pin", "kind": "hole", "shape": "circle", "center": [150, 9, 100], "diameter": 8}]}]))
    assert r['ok'] and r['layout']['ready_for_production']


# BUG-003: long board ids crashed the compiler when connections were inferred -----------------------------------
@pytest.mark.parametrize('n', [29, 30, 40, 64])
@pytest.mark.parametrize('connections', ['auto', 'explicit-without-id'])
def test_bug003_long_board_ids_compile(n, connections):
    a, b = 'A' * n, 'B' * n
    conns = 'auto' if connections == 'auto' else [{"type": "tab_slot", "board": b, "into": a}]
    r = compile_source(_src([{"id": a, "position": [0, 0, 0], "size": [600, 18, 400]},
                             {"id": b, "position": [100, 18, 100], "size": [18, 300, 200]}], conns))
    assert r['ok'], _codes(r)
    assert r['summary']['joined'] >= 1 and 'COMPILER_ERROR' not in _codes(r)


# BUG-006: a "safe" fix must never lead to a new error ----------------------------------------------------------
def test_bug006_no_safe_cross_lap_fix_for_a_profiled_board():
    side = {"id": "SIDE", "position": [0, 0, 20], "size": [200, 70, 6],
            "profile": {"shape": "polygon", "points": [[0, 0], [200, 0], [200, 60], [0, 70]]}}
    rod = {"id": "ROD", "position": [37, 17, 0], "size": [6, 30, 60]}
    r = compile_source(_src([side, rod], [], material=P6))
    safe = [f for d in r['diagnostics'] for f in (d.get('fixes') or []) if f.get('safe')]
    assert 'COLLISION' in _codes(r) and not any('cross_lap' in f['title'] for f in safe)


def test_bug006_safe_cross_lap_fix_still_offered_and_works_for_plain_crossing_boards():
    src = _src([{"id": "A", "position": [0, 0, 92], "size": [200, 100, 18]},
                {"id": "B", "position": [91, 0, 0], "size": [18, 100, 200]}], [])
    r = compile_source(src)
    safe = [f for d in r['diagnostics'] for f in (d.get('fixes') or []) if f.get('safe') and 'cross_lap' in f['title']]
    assert safe
    assert compile_source(apply_code_fix(src, safe[0]))['ok']


# BUG-007: a board that nothing holds must not reach the cutting files; a resting lid may -------------------------
def test_bug007_unsupported_board_blocks_compile_and_production():
    d = copy.deepcopy(EXAMPLE)
    d['boards'].append({"id": "LOOSE", "position": [300, 200, 60], "size": [400, 18, 280]})
    r = compile_source(json.dumps(d))
    assert 'ISOLATED_BOARD' in _codes(r) and not r['ok']
    pkg = production_package(r['design'], {'compensate_kerf': True})      # e.g. a saved / API design
    assert not pkg['ready_for_production'] and 'UNSUPPORTED_COMPONENT' in {i['code'] for i in pkg['blocking_issues']}
    ok = production_package(compile_source(json.dumps(EXAMPLE), run_production=False)['design'], {'compensate_kerf': True})
    assert ok['ready_for_production']


def test_bug007_resting_lid_is_allowed_and_reported():
    walls = [{"id": "BASE", "position": [0, 0, 0], "size": [300, 6, 200]},
             {"id": "FRONT", "position": [0, 6, 194], "size": [300, 144, 6]}, {"id": "BACK", "position": [0, 6, 0], "size": [300, 144, 6]},
             {"id": "LEFT", "position": [0, 6, 6], "size": [6, 144, 188]}, {"id": "RIGHT", "position": [294, 6, 6], "size": [6, 144, 188]},
             {"id": "LID", "position": [0, 150, 0], "size": [300, 6, 200]}]
    conns = [{"type": "finger", "board": a, "into": b} for a, b in (("FRONT", "BASE"), ("BACK", "BASE"), ("LEFT", "BASE"), ("RIGHT", "BASE"),
                                                                    ("LEFT", "BACK"), ("LEFT", "FRONT"), ("RIGHT", "BACK"), ("RIGHT", "FRONT"))]
    r = compile_source(_src(walls, conns, material=P6))
    assert r['ok'] and r['layout']['ready_for_production']
    assert 'NOT_JOINED' in _codes(r, 'warning') and not _codes(r) & {'ISOLATED_BOARD', 'NOT_JOINED', 'DISCONNECTED'}
    assert r['support']['components']['LID']['status'] == 'resting'


# BUG-008: changing the material thickness must change the boards (or be refused), never silently do nothing -------
def test_bug008_set_material_thickness_reaches_canvas_boards():
    d = compile_source(json.dumps(EXAMPLE), run_production=False)['design']
    with pytest.raises(OperationRejected):
        apply_operation(copy.deepcopy(d), {'op': 'set_material', 'material': {'thickness': 15}})
    res = apply_operation(d, {'op': 'set_material', 'material': {'thickness': 15}, 'detach_broken_joints': True})
    assert {c['thickness'] for c in d['components']} == {15.0} and res['detached_joints']


# BUG-009: out-of-range connection options are reported on the connection, with its line -----------------------
def test_bug009_connection_option_error_names_the_connection():
    d = {"format": "board-design/v1", "product": {"name": "c"}, "material": P18, "joinery": "glue_allowed",
         "boards": [{"id": "SIDE", "position": [0, 0, 0], "size": [18, 400, 300]}, {"id": "BACKP", "position": [18, 0, 0], "size": [300, 400, 18]},
                    {"id": "DOOR", "position": [0, 0, 302], "size": [318, 400, 18]}],
         "connections": [{"id": "corner", "type": "finger", "board": "BACKP", "into": "SIDE"},
                         {"id": "door", "type": "hinge", "board": "DOOR", "into": "SIDE", "edge": "-x", "count": 12}]}
    r = compile_source(json.dumps(d, indent=2))
    bad = [x for x in r['diagnostics'] if x['code'] == 'CONNECTION_INVALID']
    assert bad and bad[0]['connection'] == 'door' and bad[0].get('line') and 'SCHEMA_ERROR' not in _codes(r)


# BUG-019: the canvas sheet size must use the nesting's own allowances --------------------------------------------
def test_bug019_auto_sheet_fits_a_1200_mm_back_panel():
    boards = [{"id": "SIDE-L", "position": [0, 0, 0], "size": [18, 1800, 300]}, {"id": "SIDE-R", "position": [1182, 0, 0], "size": [18, 1800, 300]},
              {"id": "BOTTOM", "position": [18, 60, 0], "size": [1164, 18, 300]}, {"id": "TOP", "position": [18, 1760, 0], "size": [1164, 18, 300]},
              {"id": "BACK", "position": [18, 78, 294], "size": [1164, 1682, 6], "thickness": 6}]
    r = compile_source(_src(boards, 'auto'))
    assert r['ok'] and r['layout']['nesting']['unplaced'] == [] and r['layout']['ready_for_production']


# Support analysis ----------------------------------------------------------------------------------------------
def test_support_tip_over_and_cantilever():
    boards = [{"id": "TOP", "position": [0, 732, 0], "size": [1200, 18, 600]},
              {"id": "LEG-1", "position": [60, 0, 40], "size": [18, 732, 520]}, {"id": "LEG-2", "position": [260, 0, 40], "size": [18, 732, 520]}]
    r = compile_source(_src(boards, [{"type": "tab_slot", "board": "LEG-1", "into": "TOP"}, {"type": "tab_slot", "board": "LEG-2", "into": "TOP"}]))
    assert {'TIP_OVER', 'CANTILEVER'} <= _codes(r, 'warning') and r['support']['stable'] is False


def test_support_balanced_table_is_stable_without_warnings():
    r = compile_source(json.dumps(EXAMPLE))
    assert r['support']['stable'] is True and not {'TIP_OVER', 'CANTILEVER'} & _codes(r, 'warning')
    assert r['support']['stability_margin'] > 0


def test_support_wall_mounting_skips_tip_over_and_requires_valid_value():
    boards = [{"id": "RAIL", "position": [0, 0, 0], "size": [600, 218, 18]},
              {"id": "BRK", "position": [291, 0, 18], "size": [18, 200, 200]},
              {"id": "SHELF", "position": [0, 200, 18], "size": [600, 18, 200]}]
    conns = [{"type": "tab_slot", "board": "BRK", "into": "RAIL"}, {"type": "tab_slot", "board": "BRK", "into": "SHELF"},
             {"type": "tab_slot", "board": "SHELF", "into": "RAIL"}]
    d = json.loads(_src(boards, conns))
    d['product']['mounting'] = 'wall'
    r = compile_source(json.dumps(d))
    assert r['support']['mounting'] == 'wall' and 'TIP_OVER' not in _codes(r, 'warning') and 'WALL_MOUNTED' in _codes(r, 'info')
    assert r['design']['mounting'] == 'wall'
    d['product']['mounting'] = 'ceiling'
    assert 'MOUNTING' in _codes(compile_source(json.dumps(d)))


def test_support_report_never_claims_strength():
    from board_engine.support import support_report
    s = support_report(compile_source(json.dumps(EXAMPLE), run_production=False)['design'])
    assert 'not assessed' in s['disclaimer']


# Time budget (hang protection) -----------------------------------------------------------------------------------
def _grid(n=6, cell=150):
    boards = [{"id": "BASE", "position": [0, 0, 0], "size": [n * cell, 6, n * cell]}]
    for i in range(1, n):
        boards += [{"id": f"X{i}", "position": [3, 6, i * cell], "size": [n * cell - 6, 150, 6]},
                   {"id": f"Z{i}", "position": [i * cell, 6, 3], "size": [6, 150, n * cell - 6]}]
    return _src(boards, 'auto', material=P6)


def test_time_budget_stops_compile_with_a_clear_diagnostic():
    r = compile_source(_grid(), time_budget=0.2)
    assert not r['ok'] and r['design'] is None and 'COMPILE_TIMEOUT' in _codes(r)


def test_no_time_budget_means_no_limit():
    from board_engine.deadline import check, time_budget  # noqa: I001
    with time_budget(None):
        check()                              # no budget set: never raises
    with time_budget(60):
        with time_budget(None):              # None keeps the caller's budget
            check()


# Version history: every revision can be listed, read and restored (restoring is itself a new revision) -----------
@pytest.fixture(scope='module')
def api(tmp_path_factory):
    import importlib
    import os
    os.environ.update(BOARD_INSTANCE_DIR=str(tmp_path_factory.mktemp('versions')), BOARD_API_KEYS='ed:editor', BOARD_SKIP_SEED='1')
    import app as appmod
    importlib.reload(appmod)
    yield appmod.app.test_client()
    for k in ('BOARD_INSTANCE_DIR', 'BOARD_API_KEYS', 'BOARD_SKIP_SEED'):
        os.environ.pop(k, None)


def test_versions_list_get_and_restore(api):
    h = {'Authorization': 'Bearer ed'}
    did = api.post('/api/v1/canvas/save', headers=h, json={'source': json.dumps(EXAMPLE), 'name': 'V1'}).json['design_id']
    api.patch(f'/api/v1/designs/{did}', headers=h, json={'name': 'V2'})
    wider = copy.deepcopy(EXAMPLE)
    wider['product']['name'] = 'V3'
    r = api.post('/api/v1/canvas/save', headers=h, json={'source': json.dumps(wider), 'design_id': did})
    assert r.status_code == 201 and r.json['revision'] == 3          # canvas update keeps the history (was reset to 1)
    assert api.get(f'/api/v1/designs/{did}/versions', headers=h).json['versions'] == [1, 2, 3]
    assert api.get(f'/api/v1/designs/{did}/versions/1', headers=h).json['design']['name'] == 'V1'
    r = api.post(f'/api/v1/designs/{did}/restore', headers=h, json={'revision': 1})
    assert r.status_code == 200 and r.json['revision'] == 4
    cur = api.get(f'/api/v1/designs/{did}', headers=h).json['design']
    assert cur['name'] == 'V1' and cur['revision'] == 4
    assert api.post(f'/api/v1/designs/{did}/restore', headers=h, json={'revision': 99}).status_code == 404


def test_firestore_store_keeps_versions():
    from test_firestore_store import FakeFirestore
    from board_engine.firestore_store import FirestoreStore
    fs = FirestoreStore(project_id='p', http=FakeFirestore())
    d = compile_source(json.dumps(EXAMPLE), design_id='fsv', run_production=False)['design']
    fs.create(d)
    fs.mutate('fsv', lambda x: (dict(x, name='renamed'), None), 'rename')
    assert fs.versions('fsv') == [1, 2] and fs.get_version('fsv', 1)['name'] == EXAMPLE['product']['name']
    fs.delete('fsv')
    assert not any('/versions/' in p for p in fs._http.docs)


def test_resting_part_past_its_support_is_an_error():
    d = copy.deepcopy(EXAMPLE)
    d['boards'].append({"id": "PLANK", "position": [1000, 750, 100], "size": [600, 18, 200]})   # 400 of 600 mm off the top
    assert 'RESTING_OFF_SUPPORT' in _codes(compile_source(json.dumps(d)))
    d['boards'][-1]['position'][0] = 300                                                         # fully on the top
    assert 'RESTING_OFF_SUPPORT' not in _codes(compile_source(json.dumps(d)))


# BUG-020: a design whose connections failed to join (detached) must not be ready for production -----------------
def test_bug020_detached_connections_block_production():
    boards = [{"id": "BASE", "position": [0, 0, 0], "size": [600, 18, 300]}, {"id": "DIV", "position": [291, 18, 0], "size": [18, 400, 300]},
              {"id": "L", "position": [18, 200, 0], "size": [273, 18, 300]}, {"id": "R", "position": [309, 200, 0], "size": [273, 18, 300]},
              {"id": "SL", "position": [0, 18, 0], "size": [18, 400, 300]}, {"id": "SR", "position": [582, 18, 0], "size": [18, 400, 300]}]
    conns = [{"type": "tab_slot", "board": a, "into": b} for a, b in (("DIV", "BASE"), ("L", "DIV"), ("R", "DIV"), ("L", "SL"), ("R", "SR"))] + \
            [{"type": "finger", "board": "SL", "into": "BASE"}, {"type": "finger", "board": "SR", "into": "BASE"}]
    r = compile_source(_src(boards, conns), run_production=False)
    assert not r['ok'] and any(j.get('status') == 'detached' for j in r['design']['joints'])
    pkg = production_package(r['design'], {'compensate_kerf': True})
    assert not pkg['ready_for_production'] and 'JOINT_NOT_JOINED' in {i['code'] for i in pkg['blocking_issues']}


def test_repair_prompt_includes_production_blockers():
    from board_engine.canvas_prompt import build_repair_prompt
    p = build_repair_prompt('{}', [], [{'code': 'FASTENER_COLLISION', 'message': 'bores run into each other', 'severity': 'error'}])
    assert 'FASTENER_COLLISION' in p and 'bores run into each other' in p


def test_claim_no_fasteners_into_the_edge_of_6mm_boards():
    boards = [{"id": "SIDE", "position": [0, 0, 0], "size": [18, 400, 300]}, {"id": "BACK", "position": [18, 0, 0], "size": [400, 400, 6], "thickness": 6}]
    for kind in ('screw', 'confirmat', 'dowel'):
        r = compile_source(_src(boards, [{"type": "butt", "board": "BACK", "into": "SIDE", "fasteners": kind}], joinery='glue_allowed'))
        assert not r['layout']['ready_for_production'], kind


def test_firestore_versions_are_pruned_like_the_file_store(monkeypatch):
    from test_firestore_store import FakeFirestore
    import board_engine.firestore_store as fsmod
    monkeypatch.setattr(fsmod, 'KEEP_VERSIONS', 3)
    fs = fsmod.FirestoreStore(project_id='p', http=FakeFirestore())
    fs.create(compile_source(json.dumps(EXAMPLE), design_id='fsp', run_production=False)['design'])
    for i in range(5):
        fs.mutate('fsp', lambda x, i=i: (dict(x, name=f'n{i}'), None), 'rename')
    assert fs.versions('fsp') == [4, 5, 6]
