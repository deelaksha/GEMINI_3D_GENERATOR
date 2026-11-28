"""The lean generation prompt (audit 2026-11-28, phase 6): half the size, no contradictions, every example it shows
compiles cleanly, and motion sections only when something moves."""
import json

import pytest

from board_engine import canvas_prompt as P
from board_engine.canvas import compile_source

LASER = {'kerf': 0.15, 'sheet': {'width': 600, 'height': 400}}


@pytest.mark.parametrize('transport', ['chat', 'server'])
def test_the_lean_prompt_is_under_45k_characters_and_half_the_full_one(transport):
    lean = P.build_prompt('Aeroplane', '', None, None, 'interlocking', LASER, transport=transport)
    full = P.build_prompt('Aeroplane', '', None, None, 'interlocking', LASER, transport=transport, style='full')
    assert len(lean) <= 45000 and len(lean) < 0.5 * len(full)


def test_motion_sections_only_when_something_moves():
    still = P.build_prompt('Bookshelf', 'three shelves')
    moving = P.build_prompt('Kinetic butterfly', 'wings flap from a hand crank')
    assert '## Linkages' not in still and '## Linkages' in moving and '## Gears' in moving
    brief = {'components': [{'id': 'X', 'count': 1, 'role': 'structure'}], 'enclosures': [],
             'mechanisms': {'input': {'kind': 'motor', 'component': None}, 'transmission': []}}
    assert '## Moving parts' in P.build_prompt('Sculpture', '', brief=brief)


def test_the_lean_example_compiles_with_no_problem_at_all():
    r = compile_source(json.dumps(P.lean_example()), run_production=True)
    assert r['ok'] and r['layout']['ready_for_production'] and r['completeness']['issues'] == 0
    assert not [d for d in r['diagnostics'] if d['severity'] in ('error', 'warning')]


def test_the_lean_prompt_drops_the_contradictions():
    p = P.build_prompt('Cottage', 'simple')
    for gone in ('slightly open', 'NATURAL VARIATION', 'SCORE the design', 'compiler measures every one',
                 'Native engine format', 'stacked discs', 'bollards'):
        assert gone not in p, gone
    assert 'DETAIL LEVEL: 2' in p and 'angles may have decimals' in p


def test_detail_level_comes_from_the_brief_first():
    brief = {'components': [{'id': 'X', 'count': 1, 'role': 'structure'}], 'enclosures': [], 'detail_level': 5,
             'mechanisms': {'input': {'kind': 'none', 'component': None}, 'transmission': []}}
    assert 'DETAIL LEVEL: 5' in P.build_prompt('Cottage', 'simple', brief=brief)


def test_spec_documents_what_the_compiler_reads():
    spec = P.spec_markdown()
    for field in ('"role"', '"brief"', 'pressure_angle', 'backlash', '2,048 points', '"supports"', '"retain"'):
        assert field in spec, field
    assert '[7.6, 1.9]' not in spec


# patch repair (server AI fix): a small prompt, a patch back, merged and checked ----------------------------------------

import copy  # noqa: E402
import os  # noqa: E402

from board_engine.canvas_prompt import EXAMPLE  # noqa: E402
from board_engine.repair import PatchError, apply_patch, neighbourhood  # noqa: E402


def test_apply_patch_replaces_adds_and_removes_by_id():
    src = json.dumps(EXAMPLE)
    out = json.loads(apply_patch(src, {'patch': {'boards': [dict(EXAMPLE['boards'][4], position=[68, 160, 60]),
                                                            {'id': 'NEW', 'position': [0, 0, 0], 'size': [10, 10, 18]}],
                                                 'remove': ['MOD-L']}}))
    ids = [b['id'] for b in out['boards']]
    assert out['boards'][4]['position'] == [68, 160, 60] and ids[-1] == 'NEW' and len(ids) == 6
    assert 'MOD-L' not in [c['id'] for c in out['connections']] and out['material'] == EXAMPLE['material']
    with pytest.raises(PatchError):
        apply_patch(src, {'boards': 'nope'})
    with pytest.raises(PatchError):
        apply_patch(src, {'hello': 1})


def test_the_patch_prompt_shows_only_the_problem_boards_and_their_neighbours():
    d = copy.deepcopy(EXAMPLE)
    d['boards'][2]['position'][0] += 7                    # LEG-R off: SHELF and MODESTY no longer reach it
    src = json.dumps(d)
    r = compile_source(src, run_production=False)
    focus, near = neighbourhood(src, r['diagnostics'])
    assert set(focus) >= {'SHELF', 'MODESTY'} and 'LEG-R' in set(focus) | set(near)
    p = P.build_patch_repair_prompt(src, r['diagnostics'])
    assert '{"patch": {' in p and 'CONNECTION_GAP' in p and '## Moving parts' not in p


def test_the_patch_repair_prompt_for_a_341_board_house_is_small():
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'board_engine', 'examples', 'my_home.json')
    d = json.load(open(path))
    first = next(b for b in d['boards'] if 'position' in b and not b.get('repeat'))
    first['position'][0] += 7                             # one board out of place
    src = json.dumps(d)
    r = compile_source(src, run_production=False)
    full = P.build_repair_prompt(src, r['diagnostics'])
    patch = P.build_patch_repair_prompt(src, r['diagnostics'])
    assert len(patch) <= 40000 and len(patch) < len(full) / 5, (len(patch), len(full))
