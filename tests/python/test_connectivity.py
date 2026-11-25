"""Connectivity (one joined structure) and requirement-size checks."""
import json

import pytest

from board_engine.canvas import compile_source
from board_engine.requirements import check_requirements, parse_sizes

BASE = [{'id': 'BASE', 'position': [0, 0, 0], 'size': [300, 6, 200]},
        {'id': 'WALL', 'position': [40, 6, 80], 'size': [220, 120, 6]}]
JOIN = [{'id': 'W-B', 'type': 'tab_slot', 'board': 'WALL', 'into': 'BASE', 'tabs': 2}]


def build(extra=(), conns=(), requirements=None):
    d = {'format': 'board-design/v1', 'product': {'name': 't'}, 'material': {'type': 'plywood', 'thickness': 6},
         'boards': BASE + list(extra), 'connections': JOIN + list(conns)}
    return compile_source(json.dumps(d), run_production=False, requirements=requirements)


def issues(r, sev=None):
    return {d['code']: d for d in r['diagnostics'] if d['code'] in ('ISOLATED_BOARD', 'NOT_JOINED', 'DISCONNECTED',
                                                                     'REQUIREMENT_MISMATCH') and sev in (None, d['severity'])}


def test_one_joined_structure_is_clean():
    r = build()
    assert r['ok'] and not issues(r) and r['connectivity']['groups'] == [['BASE', 'WALL']]


def test_floating_board_is_an_error_with_a_move_that_closes_the_gap():
    r = build([{'id': 'FLOAT', 'position': [50, 200, 20], 'size': [100, 6, 60]}])
    i = issues(r, 'error')['ISOLATED_BOARD']
    assert not r['ok'] and i['components'][0] == 'FLOAT' and '74.0 mm' in i['message']
    assert r['connectivity']['isolated'] == ['FLOAT']


def test_loose_upright_board_touching_the_structure_is_an_error():
    r = build([{'id': 'POST', 'position': [150, 6, 20], 'size': [6, 80, 40]}])
    assert 'NOT_JOINED' in issues(r, 'error') and "'POST' / 'BASE'" in issues(r)['NOT_JOINED']['message']
    fixed = build([{'id': 'POST', 'position': [150, 6, 20], 'size': [6, 80, 40]}],
                  [{'id': 'P-B', 'type': 'tab_slot', 'board': 'POST', 'into': 'BASE', 'tabs': 1}])
    assert fixed['ok'] and not issues(fixed)


def test_flat_lid_resting_on_top_is_only_a_warning():
    r = build([{'id': 'LID', 'position': [40, 126, 60], 'size': [220, 6, 40]}])
    assert r['ok'] and 'NOT_JOINED' in issues(r, 'warning')


def test_group_apart_from_the_main_assembly_is_disconnected():
    r = build([{'id': 'A', 'position': [400, 0, 0], 'size': [100, 6, 100]},
               {'id': 'B', 'position': [420, 6, 40], 'size': [60, 50, 6]}],
              [{'id': 'B-A', 'type': 'tab_slot', 'board': 'B', 'into': 'A', 'tabs': 1}])
    i = issues(r, 'error')['DISCONNECTED']
    assert i['components'] == ['A', 'B'] and '100.0 mm' in i['message'] and not r['ok']


def test_follow_on_support_issues_are_not_repeated():
    r = build([{'id': 'FLOAT', 'position': [50, 200, 20], 'size': [100, 6, 60]}])
    assert not {d['code'] for d in r['diagnostics']} & {'UNSUPPORTED_COMPONENT', 'FLOATING_COMPONENT'}


@pytest.mark.parametrize('text, sizes', [
    ('Length 1200 mm, width 600 mm, height 750 mm.', {'length': 1200, 'depth': 600, 'height': 750}),
    ('1200 x 600 x 750 mm desk', {'length': 1200, 'depth': 600, 'height': 750}),
    ('A shelf 1.2 m long, 30 cm deep and height: 900mm', {'length': 1200, 'depth': 300, 'height': 900}),
    ('80 cm wide cabinet', {'length': 800}),
    ('three shelves, birch', {})])
def test_requirement_sizes_are_read(text, sizes):
    assert parse_sizes(text) == sizes


def test_requirement_sizes_are_checked():
    assert check_requirements('length 300 mm', [301, 0, 0]) == []
    r = build(requirements='Length 400 mm, height 126 mm, depth 200 mm')
    i = issues(r, 'error')['REQUIREMENT_MISMATCH']
    assert not r['ok'] and i['required'] == 400 and i['actual'] == 300
    assert len([d for d in r['diagnostics'] if d['code'] == 'REQUIREMENT_MISMATCH']) == 1
    assert build(requirements='Length 300 mm, height 126 mm')['ok']
