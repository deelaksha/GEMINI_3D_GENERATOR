"""
Real-world product scenarios: board identification, cutting dimensions, joints, gap / overlap detection,
manufacturing constraints, assembly feasibility and documentation — with actual dimensions.

Expected values are derived from the product geometry (furniture.py) and the catalogue rules
(manufacturing.MATERIALS / FASTENERS / validation.HINGE), never copied from engine output.
"""
import copy
import math

import pytest

from board_engine.autofix import auto_fix
from board_engine.cutlist import cut_list
from board_engine.examples.furniture import PRODUCTS, build, cube_storage, panel, Builder, PLY, OAK, PB18
from board_engine.geometry import oriented_rect, rotation_matrix
from board_engine.joining import check_joint, join
from board_engine.manufacturing import manufacturing_report
from board_engine.model import find_component, normalize_design
from board_engine.nesting import nest, verify_nesting
from board_engine.operations import OperationRejected, apply_operation
from board_engine.validation import validate_design
from board_engine.views import export, production_package


@pytest.fixture(scope='module')
def products():
    out = {}
    for name in PRODUCTS:
        d, failures = build(name)
        out[name] = (d, failures)
    return out


def codes(issues, severity=None):
    return [i['code'] for i in issues if severity is None or i['severity'] == severity]


def line(cl, cid):
    return next(l for l in cl['lines'] if cid in l['ids'])


def board(cl, cid):
    return next(b for b in cl['boards'] if b['id'] == cid)


def drills(m, cid, fastener=None):
    return [d for d in m['drilling'] if d['component'] == cid and (fastener is None or d['fastener'] == fastener)]


# ---------------------------------------------------------------------------
# Every product: builds through the join pipeline, valid, complete, manufacturable, documented
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('name', sorted(PRODUCTS))
def test_product_is_valid_manufacturable_and_documented(products, name):
    d, failures = products[name]
    assert failures == []
    v = validate_design(d)
    assert v['valid'] and v['complete'], codes(v['issues'])
    assert codes(v['issues'], 'warning') == []
    m = manufacturing_report(d)
    assert m['manufacturable'], [(i['code'], i['message']) for i in m['issues'] if i['severity'] == 'error']
    assert codes(m['issues'], 'warning') == []
    # Board identification: every component exactly once, ids stable = component ids
    cl = cut_list(d, m)
    ids = sorted(i for l in cl['lines'] for i in l['ids'])
    assert ids == sorted(c['id'] for c in d['components'])
    assert sum(l['quantity'] for l in cl['lines']) == len(d['components'])
    # Assembly plan covers every board, each once
    placed = []

    def walk(steps):
        for st in steps:
            placed.extend(st.get('base', []))
            if 'subassembly' in st:
                walk(st['subassembly'])
            elif 'add' in st:
                placed.extend(st['add'])
    for asm in m['assembly_plan']:
        walk(asm['steps'])
    assert sorted(set(placed)) == sorted(c['id'] for c in d['components'])
    # Production package: ready with kerf compensation, each sheet one stock board
    pkg = production_package(d, {'preset': 'board-2440x1220', 'spacing': 4, 'compensate_kerf': True})
    assert pkg['ready_for_production'], codes(pkg['blocking_issues'])
    stock = {s['index']: s['stock'] for s in pkg['nesting']['sheets']}
    for p in pkg['nesting']['placements']:
        assert p['thickness'] == stock[p['sheet']]['thickness']
    pdf, _mime, _n = export(pkg, 'pdf')
    assert pdf.startswith(b'%PDF')


# ---------------------------------------------------------------------------
# 1. Table
# ---------------------------------------------------------------------------

def test_table_dimensions_and_dowels(products):
    d, _ = products['table']
    m = manufacturing_report(d)
    cl = cut_list(d, m)
    top = line(cl, 'TOP')
    assert (top['finished_length'], top['finished_width'], top['thickness']) == (1200, 750, 25)
    assert top['material'] == 'Oak 25 mm' and top['grain'] == 'along length'
    legs = line(cl, 'LEG-FL')
    assert legs['quantity'] == 4 and (legs['finished_length'], legs['finished_width']) == (725, 70)
    # Long aprons span between the leg inner faces: 1200 - 2*30 - 2*25 = 1090
    assert line(cl, 'APRON-FRONT')['quantity'] == 2 and line(cl, 'APRON-FRONT')['finished_length'] == 1090
    # Leg top: 8 x 35 dowel, blind bore in the 25 mm oak top = min(35/2, 25 - 3) = 17.5; edge bore = 35 - 17.5 + 1
    top_bores = [x for x in drills(m, 'TOP') if x['joint'] == 'J-LEG-FL-TOP']
    leg_bores = [x for x in drills(m, 'LEG-FL') if x['joint'] == 'J-LEG-FL-TOP']
    assert len(top_bores) == len(leg_bores) == 2      # 70 mm edge: 2 dowels 25 mm from the ends
    assert all(x['depth'] == 17.5 and x['diameter'] == 8 and not x['through'] for x in top_bores)
    assert all(x['depth'] == 18.5 and x['type'] == 'edge_bore' for x in leg_bores)
    assert sorted(x['offset_along_edge'] for x in leg_bores) == [25.0, 45.0]


# ---------------------------------------------------------------------------
# 2. Bookshelf
# ---------------------------------------------------------------------------

def test_bookshelf_cut_sizes_banding_and_confirmats(products):
    d, _ = products['bookshelf']
    m = manufacturing_report(d)
    cl = cut_list(d, m)
    sides = line(cl, 'SIDE-L')
    assert sides['quantity'] == 2 and set(sides['ids']) == {'SIDE-L', 'SIDE-R'}   # through-drilled: interchangeable
    assert (sides['finished_length'], sides['finished_width']) == (1800, 300)
    assert (sides['blank_length'], sides['blank_width']) == (1800, 299)           # 1 mm front banding
    shelves = line(cl, 'SHELF-1')
    assert shelves['quantity'] == 5                                               # top, bottom, 3 shelves
    assert (shelves['finished_length'], shelves['blank_width']) == (764, 299)     # 800 - 2*18; 300 - 1
    # Confirmat 7x50 through the 18 mm side: 7 mm through hole, 5 mm x 32 mm pilot in the shelf edge
    side_holes = drills(m, 'SIDE-L', 'confirmat')
    assert side_holes and all(x['diameter'] == 7 and x['depth'] == 18 and x['through'] for x in side_holes)
    pilots = [x for x in drills(m, 'SHELF-2', 'confirmat')]
    assert len(pilots) == 4 and all(x['diameter'] == 5 and x['depth'] == 32 for x in pilots)
    # 300 mm deep: confirmats 50 mm from front and back (end distance), 2 per end
    assert sorted({x['offset_along_edge'] for x in pilots}) == [50.0, 250.0]
    # Back screws 3.5 x 25 through 6 mm hardboard: sides 1800 mm -> 30 mm ends, <=200 spacing -> 10 each
    assert len([x for x in drills(m, 'BACK') if x['joint'] == 'J-SIDE-L-BACK']) == 10
    assert cl['totals']['Particle board 18 mm (melamine) 18 mm']['banding_m'] == pytest.approx(
        (2 * 1800 + 5 * 764) / 1000, abs=1e-3)


# ---------------------------------------------------------------------------
# 3. Cabinet: doors, hinges, partition
# ---------------------------------------------------------------------------

def test_cabinet_hinges_doors_and_assembly(products):
    d, _ = products['cabinet']
    m = manufacturing_report(d)
    cups = drills(m, 'DOOR-L', 'hinge_cup')
    assert len(cups) == 2                                    # 716 mm door -> 2 hinges
    assert all(x['diameter'] == 35 and x['depth'] == 13 for x in cups)
    door = find_component(d, 'DOOR-L')
    # door local x = world x; hinge edge at local x = -198.25 (door 396.5 wide); cup centre 22.5 mm in
    assert all(abs(x['position'][0] - (-396.5 / 2 + 22.5)) < 1e-6 for x in cups)
    assert sorted(round(x['position'][1] + 716 / 2, 3) for x in cups) == [100.0, 616.0]   # 100 mm from the ends
    assert len(drills(m, 'SIDE-L', 'hinge_plate')) == 4      # 2 plates x 2 holes, 37 mm back on the side
    hinge = next(c for c in m['connections'] if c['joint'] == 'H-DOOR-L')
    assert hinge['relation'] == 'hinge'
    # Doors are hung last
    steps = m['assembly_plan'][0]['steps']
    assert {b for st in steps[-2:] for b in st['add']} == {'DOOR-L', 'DOOR-R'}
    assert door['thickness'] == 18


def test_hinge_moves_clear_of_a_shelf_at_hinge_height():
    from board_engine.examples.furniture import cabinet
    d, failures = cabinet(shelf_y=605.0).build()           # shelf face 605..623, nominal top hinge at y = 618
    assert failures == []
    m = manufacturing_report(d)
    adj = [i for i in m['issues'] if i['code'] == 'HINGE_POSITION_ADJUSTED' and 'DOOR-L' in i['components']]
    assert adj and 'SHELF' in adj[0]['components']
    cups = drills(m, 'DOOR-L', 'hinge_cup')
    assert all(abs((x['position'][1] + 358) - 616) > 1 for x in cups[1:])
    assert m['manufacturable']


# ---------------------------------------------------------------------------
# 4. Wardrobe
# ---------------------------------------------------------------------------

def test_wardrobe_compartments_and_tall_doors(products):
    d, _ = products['wardrobe']
    m = manufacturing_report(d)
    assert len(drills(m, 'DOOR-L', 'hinge_cup')) == 4       # 1996 mm door -> 4 hinges
    cl = cut_list(d, m)
    assert line(cl, 'SHELF-1')['quantity'] == 4
    assert line(cl, 'BACK-L')['finished_length'] == 2000 and line(cl, 'BACK-L')['finished_width'] == 509
    assert line(cl, 'BACK-R')['finished_width'] == 691


# ---------------------------------------------------------------------------
# 5. Drawer
# ---------------------------------------------------------------------------

def test_drawer_box_dimensions_and_dowel_depths(products):
    d, _ = products['drawer']
    m = manufacturing_report(d)
    cl = cut_list(d, m)
    fb = line(cl, 'DRW-FRONT')
    assert fb['quantity'] == 2 and (fb['finished_length'], fb['finished_width'], fb['thickness']) == (370, 150, 15)
    # 15 mm plywood side: dowel bore = min(17.5, 15 - 3) = 12; edge bore = 35 - 12 + 1 = 24; wall (15-8)/2 = 3.5
    face = [x for x in drills(m, 'DRW-SIDE-L') if x['fastener'] == 'dowel']
    edge = [x for x in drills(m, 'DRW-FRONT') if x['fastener'] == 'dowel']
    assert face and all(x['depth'] == 12 for x in face)
    assert edge and all(x['depth'] == 24 for x in edge)


# ---------------------------------------------------------------------------
# 6. L-shaped desk
# ---------------------------------------------------------------------------

def test_l_desk_edge_to_edge_dowels(products):
    d, _ = products['l-desk']
    m = manufacturing_report(d)
    seam = [b for b in m['fasteners'] if b['joint'] == 'M-TOPS']
    # 600 mm seam: 37 mm ends, span 526 / 160 -> 5 dowels; bores 35/2 + 0.5 = 18 mm into each 24 mm top
    assert len(seam) == 5
    assert all(x['depth'] == 18 for x in m['drilling'] if x['joint'] == 'M-TOPS')
    cl = cut_list(d, m)
    main = board(cl, 'TOP-MAIN')
    assert main['shape'] == 'rectangular' and (main['finished']['length'], main['finished']['width']) == (1400, 700)


# ---------------------------------------------------------------------------
# 7. Storage rack: repeated parts, staggered shared uprights
# ---------------------------------------------------------------------------

def test_storage_rack_groups_repeated_parts(products):
    d, _ = products['storage-rack']
    cl = cut_list(d)
    assert sum(l['quantity'] for l in cl['lines'] if l['name'].startswith('Shelf')) == 10
    assert all(l['finished_length'] == 600 for l in cl['lines'] if l['name'].startswith('Shelf'))


def test_unstaggered_shared_upright_is_rejected_with_reasons():
    from board_engine.examples.furniture import storage_rack
    b = storage_rack(stagger=0)
    for j in b.joints:      # confirmats from both faces of the shared upright everywhere
        if j.get('fasteners', {}).get('kind') == 'dowel':
            j['fasteners'] = {'kind': 'confirmat'}
    d, failures = b.build()
    assert failures == []                                   # geometry alone is fine...
    assert validate_design(d)['valid']
    m = manufacturing_report(d)                             # ...but it cannot be made
    assert not m['manufacturable']
    assert 'FASTENER_COLLISION' in codes(m['issues']) and 'TOOL_ACCESS_BLOCKED' in codes(m['issues'])
    pkg = production_package(d, {'preset': 'board-2440x1220', 'spacing': 4, 'compensate_kerf': True})
    assert not pkg['ready_for_production']


# ---------------------------------------------------------------------------
# 8. TV unit: several thicknesses and materials
# ---------------------------------------------------------------------------

def test_tv_unit_nests_each_stock_separately(products):
    d, _ = products['tv-unit']
    n = nest(d, {'preset': 'board-2440x1220', 'spacing': 4})
    stocks = [(s['stock']['material'], s['stock']['thickness']) for s in n['sheets']]
    assert stocks == [('Oak 25 mm', 25.0), ('Particle board 18 mm (melamine)', 18.0), ('MDF 16 mm', 16.0),
                      ('Hardboard 6 mm', 6.0)]
    assert n['issues'] == []
    # tampering: put the back on the oak sheet -> independent verification catches it
    bad = copy.deepcopy(n)
    next(p for p in bad['placements'] if p['id'] == 'BACK')['sheet'] = 0
    assert 'MIXED_STOCK_ON_SHEET' in codes(verify_nesting(d, bad))
    assert {s['stock']['thickness'] for s in n['stats']['by_stock']} == {25.0, 18.0, 16.0, 6.0}


# ---------------------------------------------------------------------------
# 9. Angled joints: bevelled mitres + inclined shelf
# ---------------------------------------------------------------------------

def test_mitred_stand_bevels_and_long_points(products):
    d, _ = products['mitred-stand']
    v = validate_design(d)
    assert 'COLLISION' not in codes(v['issues'])            # the bevel removes the square-cut overlap
    cl = cut_list(d)
    top = board(cl, 'TOP')
    # mid-plane length 2 * (300 - 9) = 582; each 45 deg bevel adds the long point t/2 * cot(45) = 9
    assert top['finished']['length'] == 582 and top['blank']['length'] == 600
    assert [b['bevel_deg'] for b in top['operations']['bevels']] == [45, 45]
    assert all(b['blade_tilt_deg'] == 45 for b in top['operations']['bevels'])
    leg = board(cl, 'LEG-L')
    assert leg['finished']['length'] == 441 and leg['blank']['length'] == 450
    shelf = board(cl, 'SHELF')
    assert shelf['orientation']['kind'] == 'inclined' and shelf['orientation']['tilt_deg'] == 15


def test_square_mitre_without_bevel_is_an_overlap():
    from board_engine.examples.furniture import mitred_stand
    b = mitred_stand()
    for j in b.joints:
        j.pop('bevel', None)
    d, failures = b.build()
    assert {f['joint'] for f in failures} == {'M-TOP-LEG-L', 'M-TOP-LEG-R'}
    assert all(any(c == 'PENETRATION' for c, _m in f['issues']) for f in failures)


# ---------------------------------------------------------------------------
# 10. Complex intersecting structure: 3 x 3 cube storage
# ---------------------------------------------------------------------------

def test_cube_storage_unstaggered_dowels_collide_and_suggestion_fixes_it():
    d, failures = cube_storage(stagger=False).build()
    assert failures == []
    m = manufacturing_report(d)
    col = [i for i in m['issues'] if i['code'] == 'FASTENER_COLLISION']
    assert col and all(i['distance'] == 0 for i in col)    # bores from both faces on one axis
    sug = col[0]['suggestion']
    assert sug['action'] == 'stagger_fasteners'
    # apply the suggested layout: that joint's collisions disappear (verified, not estimated)
    fixed = copy.deepcopy(d)
    next(j for j in fixed['joints'] if j['id'] == sug['joint'])['fasteners'] = sug['fasteners']
    after = manufacturing_report(fixed)
    assert not [i for i in after['issues'] if i['code'] == 'FASTENER_COLLISION'
                and sug['joint'] in (i['joint'], i['other_joint'])]


# ---------------------------------------------------------------------------
# Negative cases: wrong dimensions, offsets, missing boards, invalid connections
# ---------------------------------------------------------------------------

def _shelf_box(short=0.0):
    b = Builder('box', 'Box', '')
    b.add(panel('SIDE-L', 'L', 'C', [-400, 0, -150], [-382, 600, 150]))
    b.add(panel('SIDE-R', 'R', 'C', [382, 0, -150], [400, 600, 150]))
    b.add(panel('SHELF', 'S', 'C', [-382 + short / 2, 300, -150], [382 - short / 2, 318, 150]))
    return b


def test_shelf_two_mm_short_is_a_measured_gap():
    b = _shelf_box(short=2.0)
    b.butt('SHELF', '-x', 'SIDE-L', 'confirmat')
    d, failures = b.build()
    assert failures and failures[0]['issues'][0][0] == 'UNINTENDED_GAP'
    res = check_joint(normalize_design(b.design), b.joints[0])
    gap = next(i for i in res['issues'] if i['code'] == 'UNINTENDED_GAP')
    assert gap['gap'] == 1.0 and gap['suggestion']['delta'] == [-1.0, 0.0, 0.0]


def test_undeclared_near_miss_is_reported_with_correction():
    d = normalize_design(_shelf_box(short=2.0).design)
    m = manufacturing_report(d)
    gaps = [i for i in m['issues'] if i['code'] == 'POSSIBLE_GAP' and i['components'] == ['SHELF', 'SIDE-L']]
    assert gaps and gaps[0]['gap'] == 1.0 and gaps[0]['candidate_joint']['type'] == 'edge_butt'
    # touching boards with no joint: classified (T) with joint options
    d = normalize_design(_shelf_box().design)
    cont = [i for i in manufacturing_report(d)['issues'] if i['code'] == 'CONTACT_WITHOUT_JOINT']
    assert {tuple(i['components']) for i in cont} == {('SHELF', 'SIDE-L'), ('SHELF', 'SIDE-R')}
    assert all(i['relation'] == 'T' and i['options']['recommended']['fasteners'] == 'confirmat' for i in cont)


def test_incorrect_offset_is_detected_and_auto_corrected(products):
    d, _ = products['bookshelf']
    work = copy.deepcopy(d)
    with pytest.raises(OperationRejected) as e:      # attempted on a copy, as the API's batches do
        apply_operation(copy.deepcopy(work), {'op': 'translate', 'id': 'SHELF-2', 'delta': [1.5, 0, 0]})
    assert e.value.status == 'would_break_joints'
    # sliding along the side faces breaks nothing (no false positive)
    apply_operation(work, {'op': 'translate', 'id': 'SHELF-2', 'delta': [0, 40, 0]})
    assert validate_design(work)['valid']
    # forced offset -> detached joints -> deterministic auto-fix restores the exact position
    apply_operation(work, {'op': 'translate', 'id': 'SHELF-2', 'delta': [1.5, 0, 0], 'detach_broken_joints': True})
    assert not validate_design(work)['complete']
    fixed, report = auto_fix(work)
    assert report['complete']
    pos = find_component(fixed, 'SHELF-2')['placement']['position']
    orig = find_component(d, 'SHELF-2')['placement']['position']
    assert pos[0] == pytest.approx(orig[0], abs=1e-6) and pos[1] == pytest.approx(orig[1] + 40, abs=1e-6)


def test_missing_board_removes_its_connections_and_documentation(products):
    d, _ = products['bookshelf']
    work = copy.deepcopy(d)
    with pytest.raises(OperationRejected):
        apply_operation(work, {'op': 'delete_component', 'id': 'SIDE-R'})
    res = apply_operation(work, {'op': 'delete_component', 'id': 'SIDE-R', 'cascade': True})
    assert set(res['removed_joints']) == {j['id'] for j in d['joints'] if 'SIDE-R' in (j['a'], j['b'])}
    m = manufacturing_report(work)
    assert not drills(m, 'SIDE-R')
    assert len([x for x in drills(m, 'BACK') if x['joint'] == 'J-SIDE-R-BACK']) == 0
    assert 'SIDE-R' not in {i for l in cut_list(work, m)['lines'] for i in l['ids']}


def test_invalid_connections_are_refused():
    b = _shelf_box()
    d = normalize_design(b.design)
    # edge joint between parallel boards
    r = check_joint(d, {'id': 'X', 'type': 'edge_butt', 'a': 'SIDE-L', 'a_edge': 0, 'b': 'SIDE-R'})
    assert 'ORIENTATION_MISMATCH' in codes(r['issues'])
    # a 12 mm door cannot take a 13 mm deep hinge cup
    b = _shelf_box()
    b.add(panel('DOOR', 'D', 'Doors', [-398, 2, 151], [398, 598, 163], material={'name': 'MDF 12', 'type': 'mdf'}))
    b.hinge('DOOR', '-x', 'SIDE-L')
    _d, failures = b.build()
    assert failures and 'HINGE_CUP_TOO_DEEP' in [c for c, _m in failures[0]['issues']]


def test_fastener_engineering_limits():
    def one(fasteners, a_t=18.0, mat=PLY(18)):
        b = Builder('f', 'F', '', material=dict(mat, thickness=18.0))
        b.add(panel('SIDE', 'S', 'C', [-18, 0, -150], [0, 600, 150]))
        b.add(panel('SHELF', 'H', 'C', [0, 300, -150], [400, 300 + a_t, 150]))
        b.butt('SHELF', '-x', 'SIDE', fasteners)
        d, failures = b.build()
        assert failures == []
        return codes(manufacturing_report(d)['issues'], 'error')
    assert one('dowel') == []
    assert 'FASTENER_TOO_THICK_FOR_EDGE' in one('dowel', a_t=12.0)          # (12 - 8) / 2 = 2 < 3 mm wall
    assert 'FASTENER_TOO_SHORT' in one({'kind': 'screw', 'length': 25})      # 25 - 18 = 7 < 5 x 4 mm
    assert one('dowel', mat=PB18) == []                                      # particle board 18: (18-8)/2 = 5 >= 4
    assert 'FASTENER_TOO_THICK_FOR_EDGE' in one('dowel', a_t=15.0, mat=PB18)  # (15-8)/2 = 3.5 < 4 mm


def test_screw_breaking_out_of_a_short_board():
    b = Builder('f', 'F', '', material=PLY(18) | {'thickness': 18.0})
    b.add(panel('SIDE', 'S', 'C', [-18, 0, -150], [0, 600, 150]))
    b.add(panel('BLOCK', 'B', 'C', [0, 300, -150], [60, 318, 150]))
    b.butt('BLOCK', '-x', 'SIDE', {'kind': 'screw', 'length': 100})          # 82 mm into a 60 mm board
    d, failures = b.build()
    assert failures == []
    assert 'FASTENER_BREAKS_OUT' in codes(manufacturing_report(d)['issues'])


def test_assembly_needs_a_subassembly_but_is_feasible():
    """FRONT must slide left onto LEFT and down onto BASE: impossible as a single board, but the planner
    builds LEFT + FRONT + BACK first and pushes BASE up into them."""
    b = Builder('sub', 'Sub', '', material=PLY(18) | {'thickness': 18.0})
    b.add(panel('BASE', 'Base', 'C', [0, 0, 0], [300, 18, 300], grain='x'))
    b.add(panel('LEFT', 'Left', 'C', [0, 18, 0], [18, 300, 300], grain='x'))
    b.add(panel('BACK', 'Back', 'C', [18, 18, 0], [300, 300, 18], grain='x'))
    b.add(panel('FRONT', 'Front', 'C', [18, 18, 282], [300, 300, 300], grain='x'))
    for a, toward, r in (('LEFT', '-y', 'BASE'), ('BACK', '-x', 'LEFT'), ('BACK', '-y', 'BASE'),
                         ('FRONT', '-x', 'LEFT'), ('FRONT', '-y', 'BASE')):
        b.butt(a, toward, r, 'dowel')
    d, failures = b.build()
    assert failures == []
    m = manufacturing_report(d)
    assert m['manufacturable']
    steps = m['assembly_plan'][0]['steps']
    assert steps[-1]['add'] == ['BASE'] and steps[-1]['direction'] == [0.0, 1.0, 0.0]


def test_assembly_locked_by_a_cycle_of_perpendicular_dowels():
    """LEFT->BASE (Y), BACK->LEFT (X), BASE->BACK (Z): no board or pair can move along one direction."""
    b = Builder('lock', 'Lock', '', material=PLY(18) | {'thickness': 18.0})
    b.add(panel('BASE', 'Base', 'C', [0, 0, 0], [300, 18, 300], grain='x'))
    b.add(panel('LEFT', 'Left', 'C', [0, 18, -18], [18, 300, 300], grain='x'))
    b.add(panel('BACK', 'Back', 'C', [18, 0, -18], [300, 300, 0], grain='x'))
    b.butt('LEFT', '-y', 'BASE', 'dowel')
    b.butt('BACK', '-x', 'LEFT', 'dowel')
    b.butt('BASE', '-z', 'BACK', 'dowel')
    d, failures = b.build()
    assert failures == []
    assert validate_design(d)['valid']
    m = manufacturing_report(d)
    locked = [i for i in m['issues'] if i['code'] == 'ASSEMBLY_LOCKED']
    assert locked and set(locked[0]['components']) == {'BASE', 'LEFT', 'BACK'}
    # the planner's own suggestion works: change one joint to screws and it assembles
    for j in d['joints']:
        if j['a'] == 'BASE':
            j['fasteners'] = {'kind': 'screw', 'length': 40}
    assert 'ASSEMBLY_LOCKED' not in codes(manufacturing_report(d)['issues'])


def test_door_reveal_too_small():
    from board_engine.examples.furniture import cabinet, doors
    b = cabinet()
    b.design['components'] = [c for c in b.design['components'] if not c['id'].startswith('DOOR')]
    b.joints = [j for j in b.joints if j['type'] != 'hinge']
    doors(b, 800, 720, 560, reveal=0.5)
    d, failures = b.build()
    assert failures == []
    assert 'DOOR_GAP_TOO_SMALL' in codes(manufacturing_report(d)['issues'])


# ---------------------------------------------------------------------------
# Material / cutting constraints
# ---------------------------------------------------------------------------

def test_spacing_below_kerf_and_uncompensated_kerf_block_production(products):
    d, _ = products['bookshelf']
    pkg = production_package(d, {'preset': 'board-2440x1220', 'spacing': 2, 'compensate_kerf': True})
    assert 'SPACING_BELOW_KERF' in codes(pkg['blocking_issues'])            # 2 mm < 3.2 mm saw kerf
    pkg = production_package(d, {'preset': 'board-2440x1220', 'spacing': 4, 'compensate_kerf': False})
    assert 'KERF_NOT_COMPENSATED' in codes(pkg['blocking_issues'])          # 1.6 mm undersize > 0.3 tolerance


def test_saw_kerf_and_thick_tops_are_configurable():
    d = normalize_design({'id': 'k', 'material': {'thickness': 40, 'kerf': 4.4, 'type': 'solid_wood'},
                          'components': []})
    assert d['material']['kerf'] == 4.4 and d['material']['thickness'] == 40


def test_grain_direction_controls_nesting_rotation():
    d = normalize_design({'id': 'g', 'material': PB18 | {'thickness': 18.0}, 'sheet': {'width': 2440, 'height': 1220},
                          'components': [panel('A', 'A', 'G', [0, 0, 0], [1100, 18, 300], grain='x'),
                                         panel('B', 'B', 'G', [0, 100, 0], [300, 118, 1100], grain='y')]})
    n = nest(d, {'preset': 'board-2440x1220', 'spacing': 4})
    rot = {p['id']: p['rotation'] for p in n['placements']}
    assert rot == {'A': 0.0, 'B': 90.0}            # both end up with their grain along the 2440 mm sheet length
    assert all(p.get('grain_aligned') for p in n['placements'])


def test_material_constraints():
    d = normalize_design({'id': 'm', 'material': PB18 | {'thickness': 18.0},
                          'components': [panel('STRIP', 'S', 'G', [0, 0, 0], [600, 18, 20]),
                                         panel('ODD', 'O', 'G', [0, 100, 0], [600, 117, 300]),
                                         panel('OAKSHELF', 'Q', 'G', [0, 200, 0], [900, 225, 250],
                                               material=OAK(25), grain='y')]})
    c = codes(manufacturing_report(d)['issues'])
    assert 'PART_BELOW_MIN_SIZE' in c             # 20 mm particle-board strip
    assert 'NONSTANDARD_THICKNESS' in c           # 17 mm particle board
    assert 'GRAIN_ACROSS_LENGTH' in c             # oak shelf with grain across its 900 mm span


def test_edge_banding_reduces_blank_on_banded_edges_only():
    d = normalize_design({'id': 'b', 'material': PB18 | {'thickness': 18.0},
                          'components': [{'id': 'P', 'outline': [[0, 0], [600, 0], [600, 400], [0, 400]],
                                          'edge_banding': [{'edge': 0, 'thickness': 2.0}, {'edge': 1, 'thickness': 2.0},
                                                           {'edge': 2, 'thickness': 0.5}]}]})
    b = cut_list(d)['boards'][0]
    assert (b['finished']['length'], b['finished']['width']) == (600, 400)
    assert (b['blank']['length'], b['blank']['width']) == (598, 397.5)     # 600 - 2 (edge 1); 400 - 2 - 0.5


def test_cut_size_is_the_board_not_its_bounding_box():
    a = math.radians(30)
    pts = [[x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)]
           for x, y in [[-300, -150], [300, -150], [300, 150], [-300, 150]]]
    r = oriented_rect(pts)
    assert (round(r['length'], 6), round(r['width'], 6), round(r['angle'], 6)) == (600, 300, 30)
    d = normalize_design({'id': 'r', 'components': [{'id': 'P', 'outline': pts}], 'sheet': {'width': 2440, 'height': 1220}})
    b = cut_list(d)['boards'][0]
    assert b['shape'] == 'rectangular' and (b['finished']['length'], b['finished']['width']) == (600, 300)


# ---------------------------------------------------------------------------
# Identification stability and real-time re-validation
# ---------------------------------------------------------------------------

def _euler_xyz(R):
    y = math.asin(max(-1.0, min(1.0, R[0][2])))
    if abs(R[0][2]) < 0.9999999:
        x, z = math.atan2(-R[1][2], R[2][2]), math.atan2(-R[0][1], R[0][0])
    else:
        x, z = math.atan2(R[2][1], R[1][1]), 0.0
    return [math.degrees(v) for v in (x, y, z)]


def _summary(cl):
    return sorted((b['id'], b['finished']['length'], b['finished']['width'], b['thickness'], b['shape'],
                   tuple(sorted((c['joint'], c['with']) for c in b['connections']))) for b in cl['boards'])


def test_identification_is_stable_under_moving_and_rotating_the_model(products):
    d, _ = products['cabinet']
    base = _summary(cut_list(d))
    moved = copy.deepcopy(d)
    Ry = rotation_matrix([0, 90, 0])
    for c in moved['components']:
        p = c['placement']['position']
        c['placement']['position'] = [sum(Ry[i][k] * p[k] for k in range(3)) + off
                                      for i, off in zip(range(3), (500, 0, -300))]
        R = rotation_matrix(c['placement']['rotation'])
        c['placement']['rotation'] = _euler_xyz([[sum(Ry[i][k] * R[k][j] for k in range(3)) for j in range(3)]
                                                 for i in range(3)])
    assert validate_design(moved)['valid']
    assert manufacturing_report(moved)['manufacturable']
    assert _summary(cut_list(moved)) == base


def test_dimension_change_keeps_ids_and_updates_sizes():
    from board_engine.examples.furniture import bookshelf
    a, _ = bookshelf().build()
    b, failures = bookshelf(W=900.0).build()
    assert failures == []
    ca, cb = cut_list(a), cut_list(b)
    assert {x['id'] for x in ca['boards']} == {x['id'] for x in cb['boards']}
    assert line(cb, 'SHELF-1')['finished_length'] == 864 == line(ca, 'SHELF-1')['finished_length'] + 100


def test_thickness_change_is_rechecked_against_joints(products):
    d, _ = products['bookshelf']
    work = copy.deepcopy(d)
    with pytest.raises(OperationRejected) as e:     # 18 -> 25 mm side grows 3.5 mm into every shelf end
        apply_operation(work, {'op': 'update_component', 'id': 'SIDE-L', 'patch': {'thickness': 25}})
    pen = [i for i in e.value.issues if i.get('code') == 'PENETRATION']
    assert pen and pen[0]['overlap'] == 3.5


# ---------------------------------------------------------------------------
# Scale
# ---------------------------------------------------------------------------

def test_large_rack_hundreds_of_boards():
    """239 boards / 448 fastened joints. Time bounds are generous: they catch a return to all-pairs scans
    (the manufacturing check took 15 s before spatial hashing; it now takes about 2 s)."""
    import time
    from board_engine.examples.furniture import storage_rack
    b = storage_rack(bays=14, levels=16, H=2400)
    d = normalize_design(dict(b.design, joints=[dict(j, status='joined') for j in b.joints]))
    assert len(d['components']) == 239
    t = time.time()
    v = validate_design(d)
    m = manufacturing_report(d)
    cl = cut_list(d, m)
    elapsed = time.time() - t
    assert v['valid'] and m['manufacturable'] and m['summary']['fasteners'] == 1318
    assert sum(l['quantity'] for l in cl['lines']) == 239 and len(cl['lines']) == 5
    assert elapsed < 30, elapsed
