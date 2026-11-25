"""Boards that are only placed (every connection failed) are reported per board with the reason and the fix."""
import json
import os

import pytest

from board_engine.canvas import compile_source
from board_engine.canvas_prompt import build_repair_prompt

FIX = os.path.join(os.path.dirname(__file__), 'fixtures', 'titanic_unjoined.json')


@pytest.fixture(scope='module')
def titanic():
    src = open(FIX).read()
    return src, compile_source(src, run_production=False)


def unattached(r):
    return {d['message'].split("'")[1]: d for d in r['diagnostics'] if d['code'] == 'UNATTACHED_BOARD'}


def test_every_loose_part_of_the_reference_design_is_named(titanic):
    _src, r = titanic
    u = unattached(r)
    assert set(u) == {'BOW-PROW-P', 'BOW-PROW-S', 'CARGO-HATCH', 'DECK-BOLLARD', 'DECK-BOLLARD-S', 'LIFEBOAT-P',
                      'LIFEBOAT-S', 'PED-RIB', 'STERN-COUNTER-P', 'STERN-COUNTER-S'}
    assert all(d['severity'] == 'error' and 'NOT ATTACHED' in d['message'] for d in u.values())
    assert not r['ok']


def test_reasons_and_fixes(titanic):
    _src, r = titanic
    u = unattached(r)
    assert 'all 4 of 4 copies' in u['CARGO-HATCH']['message'] and 'two parallel faces cannot be joined' in u['CARGO-HATCH']['message']
    assert '5 of 8 copies' in u['DECK-BOLLARD']['message'] and "1.0 mm from the slot of 'HULL-PORT'" in u['DECK-BOLLARD']['message']
    assert "'PED-RIB-2' is on the slot of 'CRADLE-AFT'" in u['PED-RIB']['message'] and 'split the repeat' in u['PED-RIB']['message']
    assert "beyond the outline of 'MAIN-DECK'" in u['BOW-PROW-P']['message']
    assert u['CARGO-HATCH']['line'] and u['CARGO-HATCH']['copies'] == 4


def test_fix_prompt_leads_with_the_loose_parts(titanic):
    src, r = titanic
    p = build_repair_prompt(src, r['diagnostics'])
    problems = p.split('PROBLEMS:')[1]
    assert problems.strip().startswith('- [ERROR UNATTACHED_BOARD]')
    assert 'must be attached after your' in p


def test_a_whole_repeat_is_moved_when_one_move_clears_it():
    d = {'format': 'board-design/v1', 'product': {'name': 'deck'}, 'material': {'type': 'plywood', 'thickness': 6},
         'boards': [{'id': 'DECK', 'position': [0, 100, 0], 'size': [400, 6, 200]},
                    {'id': 'WALL', 'position': [0, 0, 20], 'size': [400, 100, 6]},
                    {'id': 'POST', 'position': [0, 0, 180], 'size': [400, 100, 6]},
                    {'id': 'PEG', 'position': [40, 106, 21], 'size': [20, 20, 6], 'repeat': {'count': 3, 'step': [120, 0, 0]}}],
         'connections': [{'id': 'w', 'type': 'tab_slot', 'board': 'WALL', 'into': 'DECK', 'tabs': 3},
                         {'id': 'p', 'type': 'tab_slot', 'board': 'POST', 'into': 'DECK', 'tabs': 3},
                         {'id': 'g', 'type': 'tab_slot', 'board': 'PEG', 'into': 'DECK', 'tabs': 1}]}
    r = compile_source(json.dumps(d), run_production=False)
    u = unattached(r)
    msg = u['PEG']['message']           # two copies sit on the wall's slot line: one move of the repeat clears them
    assert '2 of 3 copies' in msg and "Move 'PEG' (the whole repeat) by +17 mm along z: PEG z 21..27, WALL z 20..26 -> PEG z 38..44" in msg
