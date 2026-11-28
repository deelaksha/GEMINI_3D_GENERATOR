"""Designs too large for one AI reply arrive in parts; pasted together they are merged into one design."""
import json
import os

from board_engine.canvas import apply_code_fix, compile_source

HOME = os.path.join(os.path.dirname(__file__), '..', '..', 'board_engine', 'examples', 'my_home.json')


def split(design, n):
    boards, conns = design['boards'], design['connections']
    head = {k: v for k, v in design.items() if k not in ('boards', 'connections')}
    parts = []
    for i in range(n):
        b = boards[i * len(boards) // n:(i + 1) * len(boards) // n]
        c = conns[i * len(conns) // n:(i + 1) * len(conns) // n]
        p = {'part': {'index': i + 1, 'of': n}, **(head if i == 0 else {}), 'boards': b, 'connections': c}
        parts.append(p)
    return parts


def as_chat(parts):
    return '\n\n'.join(f'Part {p["part"]["index"]}:\n```json\n{json.dumps(p, indent=1)}\n```\ncontinue' for p in parts)


def test_parts_pasted_as_code_blocks_are_merged_and_compile():
    design = json.load(open(HOME))
    r = compile_source(as_chat(split(design, 3)), run_production=False)
    d = r['diagnostics'][0]
    assert d['code'] == 'PARTS_MERGED' and d['parts'] == 3 and f"{len(design['boards'])} boards" in d['message']
    merged = apply_code_fix(as_chat(split(design, 3)), d['fixes'][0])
    full = compile_source(merged, run_production=False, time_budget=120)
    assert full['ok'] and full['summary']['boards'] == len(design['boards'])
    assert full['summary']['joined'] == full['summary']['joints']


def test_parts_pasted_as_raw_objects_in_any_order():
    parts = split(json.load(open(HOME)), 2)
    r = compile_source(json.dumps(parts[1]) + '\n' + json.dumps(parts[0]), run_production=False)
    assert r['diagnostics'][0]['code'] == 'PARTS_MERGED'


def test_a_missing_part_is_named():
    parts = split(json.load(open(HOME)), 3)
    r = compile_source(as_chat([parts[0], parts[2]]), run_production=False)
    d = r['diagnostics'][0]
    assert d['code'] == 'PART_MISSING' and d['missing'] == [2] and 'continue' in d['message']


def test_an_ordinary_design_is_untouched():
    design = json.load(open(HOME))
    r = compile_source('Here it is:\n```json\n' + json.dumps(design) + '\n```', run_production=False, time_budget=120)
    assert r['ok'] and not [d for d in r['diagnostics'] if d['code'] in ('PARTS_MERGED', 'PART_MISSING')]
    single = dict(design, part={'index': 1, 'of': 1})
    assert compile_source(json.dumps(single), run_production=False, time_budget=120)['ok']


def test_the_prompt_allows_large_and_multi_part_replies():
    from board_engine.canvas_prompt import IMAGE_SPEC, build_prompt
    p = build_prompt('', images=True)
    assert 'NO SIZE LIMIT' in p and 'MULTI-PART REPLIES' in p and '"part": {"index": 1, "of": N}' in p
    assert 'plan.reference' in IMAGE_SPEC and 'BUILD AND TICK OFF' in IMAGE_SPEC


def test_every_prompt_gives_the_ai_roles_criteria_and_known_mistakes():
    from board_engine.canvas_prompt import (COMMON_MISTAKES, DESIGN_TEAM, SUCCESS_CRITERIA, build_prompt,
                                            build_repair_prompt, build_update_prompt)
    gen = build_prompt('House', thickness=3, style='full')
    rep = build_repair_prompt('{}', [{'severity': 'error', 'code': 'X', 'message': 'm'}])
    upd = build_update_prompt('{}', 'add a shelf')
    assert DESIGN_TEAM in gen and all(r in gen for r in ('ANALYST', 'ARCHITECT', 'JOINERY ENGINEER', 'INSPECTOR'))
    assert 'DIAGNOSTICIAN' in rep and 'REPAIR ENGINEER' in rep and 'CHANGE ANALYST' in upd
    for p in (gen, rep, upd):
        assert SUCCESS_CRITERIA in p and COMMON_MISTAKES in p
        assert p.index('OUTPUT CONTRACT') < p.index('YOUR ROLE') < p.index('SPECIFICATION' if 'SPECIFICATION (' in p else '## ')


def test_file_delivery_prompts_and_setting(tmp_path):
    from board_engine.canvas_prompt import OUTPUT_CONTRACT, build_prompt, build_repair_prompt
    f = build_prompt('Steam Locomotive 482', machine={'file': True})
    assert '`steam_locomotive_482.json`' in f and 'script must CHECK' in f and 'MULTI-PART REPLIES' in f
    assert OUTPUT_CONTRACT not in f and 'downloadable file `steam_locomotive_482.json`' in f.rsplit('\n', 3)[-2]
    assert OUTPUT_CONTRACT in build_prompt('Steam Locomotive 482')                       # chat delivery unchanged
    src = json.dumps({'format': 'board-design/v1', 'product': {'name': 'Steam Locomotive 482'}, 'boards': []})
    assert '`steam_locomotive_482_fixed.json`' in build_repair_prompt(src, [], machine={'file': True})
    import importlib
    os.environ.update(BOARD_INSTANCE_DIR=str(tmp_path), BOARD_API_KEYS='vw:viewer', BOARD_SKIP_SEED='1')
    import app as app_module
    importlib.reload(app_module)
    c = app_module.app.test_client()
    r = c.post('/api/v1/canvas/prompt', headers={'Authorization': 'Bearer vw'}, json={'title': 'Loco', 'machine': {'file': True}})
    assert r.status_code == 200 and '`loco.json`' in r.json['prompt']
    for k in ('BOARD_INSTANCE_DIR', 'BOARD_API_KEYS', 'BOARD_SKIP_SEED'):
        os.environ.pop(k, None)
