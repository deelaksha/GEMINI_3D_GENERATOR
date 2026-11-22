"""End-to-end product corpus.

Each case is a natural-language requirement plus the `board-design/v1` answer an AI could give to it. The designs are
hand-written for testing (AI-style, not output of Gemini); `source` says so. `expect` records what a correct engine
must report, so every case is a regression test, including the ones that must FAIL (unsupported products).
"""
import copy

P18 = {"name": "Birch plywood 18 mm", "type": "plywood", "thickness": 18}
P6 = {"name": "Birch plywood 6 mm", "type": "plywood", "thickness": 6}


def B(i, pos, size, **kw):
    return dict(id=i, name=kw.pop('name', i), group=kw.pop('group', 'Boards'), position=pos, size=size, **kw)


def C(i, t, a, b, **kw):
    return dict(id=i, type=t, board=a, into=b, **kw)


def v1(name, material, boards, connections, overall=None, **top):
    d = {"format": "board-design/v1", "product": {"name": name}, "material": material, "boards": boards,
         "connections": connections}
    if overall:
        d['product']['overall'] = dict(zip(('length', 'height', 'depth'), overall))
    d.update(top)
    return d


CASES = []


def case(cid, title, categories, prompt, design, expect, notes=''):
    CASES.append({'id': cid, 'title': title, 'categories': categories, 'prompt': prompt, 'design': design,
                  'expect': expect, 'notes': notes, 'source': 'hand-written AI-style design (not Gemini output)'})


# E2E-01 single board: serving board with handle, hanging hole and engraving -----------------------------------
case('E2E-01', 'Serving board', ['single-board', 'curved'],
     'A 400 x 250 mm serving board from 18 mm plywood with a handle, a 20 mm hanging hole and an engraved line.',
     v1('Serving board', P18, [
         B('BOARD', [0, 0, 0], [400, 18, 250],
           profile={"shape": "polygon", "corner_radius": 10,
                    "points": [[0, 0], [330, 0], [330, 85], [400, 85], [400, 165], [330, 165], [330, 250], [0, 250]]},
           openings=[{"id": "hang", "kind": "hole", "shape": "circle", "center": [375, 9, 125], "diameter": 20}],
           engravings=[{"id": "line", "kind": "engrave", "depth": 0.5, "points": [[30, 30], [300, 30]]}])],
        [], overall=(400, 18, 250)),
     {'compiles': True, 'ready': True, 'components': 1})

# E2E-02 multi-compartment bookshelf: 3 columns, staggered shelves, recessed back, inferred joints --------------
_bs = [B('SIDE-L', [0, 0, 0], [18, 1800, 300]), B('SIDE-R', [1182, 0, 0], [18, 1800, 300]),
       B('BOTTOM', [18, 60, 0], [1164, 18, 300]), B('TOP', [18, 1760, 0], [1164, 18, 300]),
       B('DIV-1', [400, 78, 0], [18, 1682, 294]), B('DIV-2', [782, 78, 0], [18, 1682, 294]),
       B('BACK', [18, 78, 294], [1164, 1682, 6], thickness=6)]
for col, (x0, x1, ys) in enumerate(((18, 400, (400, 800, 1200)), (418, 782, (500, 1000, 1400)), (800, 1182, (450, 900, 1300)))):
    _bs += [B(f'SH-{col + 1}{k + 1}', [x0, y, 0], [x1 - x0, 18, 294], group='Shelves') for k, y in enumerate(ys)]
case('E2E-02', 'Multi-compartment bookshelf', ['multi-board', 'compartments'],
     'A 1200 x 1800 x 300 mm bookshelf in 18 mm plywood with three columns, three shelves per column, a plinth '
     'and a 6 mm back. Glue-free.',
     v1('Three-column bookshelf', P18, _bs, 'auto', overall=(1200, 1800, 300)),
     {'compiles': True, 'ready': True, 'components': 16})

# E2E-03 cabinet with a hinged door and two drawers (drawers modelled as boxes resting on runner shelves) ------
_cab = [B('SIDE-L', [0, 0, 0], [18, 800, 560]), B('SIDE-R', [882, 0, 0], [18, 800, 560]),
        B('BOTTOM', [18, 80, 0], [864, 18, 560]), B('TOP', [18, 764, 0], [864, 18, 560]),
        B('DIV', [441, 98, 0], [18, 666, 560]), B('BACK', [18, 98, 10], [423, 666, 6], thickness=6),
        B('RUNNER', [459, 420, 0], [423, 18, 560]),
        B('DOOR', [0, 0, 562], [450, 800, 18], group='Doors')]
_cc = [C('b-l', 'tab_slot', 'BOTTOM', 'SIDE-L'), C('b-r', 'tab_slot', 'BOTTOM', 'SIDE-R'),
       C('t-l', 'tab_slot', 'TOP', 'SIDE-L'), C('t-r', 'tab_slot', 'TOP', 'SIDE-R'),
       C('d-b', 'tab_slot', 'DIV', 'BOTTOM'), C('d-t', 'tab_slot', 'DIV', 'TOP'),
       C('bk-l', 'tab_slot', 'BACK', 'SIDE-L'), C('bk-d', 'tab_slot', 'BACK', 'DIV'),
       C('r-d', 'tab_slot', 'RUNNER', 'DIV'), C('r-r', 'tab_slot', 'RUNNER', 'SIDE-R'),
       C('door', 'hinge', 'DOOR', 'SIDE-L', edge='-x', count=2)]
for k, y0 in enumerate((98, 438)):        # drawer k sits on BOTTOM (k=0) or RUNNER (k=1); 5 mm side clearance
    x0, x1, z0, z1, h = 464, 877, 20, 540, 300
    p = f'DR{k + 1}-'
    _cab += [B(p + 'BOT', [x0, y0, z0], [x1 - x0, 18, z1 - z0], group='Drawers'),
             B(p + 'FRONT', [x0, y0 + 18, z1 - 18], [x1 - x0, h, 18], group='Drawers'),
             B(p + 'BACK', [x0, y0 + 18, z0], [x1 - x0, h, 18], group='Drawers'),
             B(p + 'L', [x0, y0 + 18, z0 + 18], [18, h, z1 - z0 - 36], group='Drawers'),
             B(p + 'R', [x1 - 18, y0 + 18, z0 + 18], [18, h, z1 - z0 - 36], group='Drawers')]
    _cc += [C(p + 'f', 'finger', p + 'FRONT', p + 'BOT'), C(p + 'k', 'finger', p + 'BACK', p + 'BOT'),
            C(p + 'l', 'tab_slot', p + 'L', p + 'BOT'), C(p + 'r', 'tab_slot', p + 'R', p + 'BOT'),
            C(p + 'lf', 'finger', p + 'L', p + 'FRONT'), C(p + 'lk', 'finger', p + 'L', p + 'BACK'),
            C(p + 'rf', 'finger', p + 'R', p + 'FRONT'), C(p + 'rk', 'finger', p + 'R', p + 'BACK')]
case('E2E-03', 'Cabinet with door and drawers', ['multi-board', 'compartments', 'removable', 'moving', 'nested'],
     'A 900 x 800 x 580 mm cabinet: left bay with a hinged door, right bay with two drawers. 18 mm plywood.',
     v1('Door and drawer cabinet', P18, _cab, _cc, overall=(900, 800, 580), joinery='glue_allowed'),
     {'compiles': True, 'components': 18, 'resting': ['DR1-BOT', 'DR2-BOT']},
     'Drawers are drawn as boxes resting on their runners: the format has no sliding joint.')

# E2E-04 chair with tilted backrest (a folding mechanism is not representable; the fixed chair is) -------------
_prof = {"shape": "polygon", "points": [[0, 0], [0, 420], [450, 420], [450, 60], [850, 60], [850, 0]]}
case('E2E-04', 'Chair (fixed version of a folding chair)', ['angled', 'moving'],
     'A folding chair, 450 mm wide, seat at 418 mm, backrest leaning back 8 degrees. 18 mm plywood.',
     v1('Plywood chair', P18, [
         B('SIDE-L', [0, 0, 0], [18, 850, 420], profile=_prof), B('SIDE-R', [436, 0, 0], [18, 850, 420], profile=_prof),
         B('SEAT', [18, 400, 60], [418, 18, 340]),
         B('BACK', [18, 560, 20], [418, 240, 18], rotate={"axis": "x", "angle": -8}),
         B('STRETCHER', [18, 120, 200], [418, 80, 18])],
        [C('s-l', 'tab_slot', 'SEAT', 'SIDE-L'), C('s-r', 'tab_slot', 'SEAT', 'SIDE-R'),
         C('b-l', 'tab_slot', 'BACK', 'SIDE-L'), C('b-r', 'tab_slot', 'BACK', 'SIDE-R'),
         C('st-l', 'tab_slot', 'STRETCHER', 'SIDE-L'), C('st-r', 'tab_slot', 'STRETCHER', 'SIDE-R')],
        overall=(454, 850, 420)),
     {'compiles': True, 'ready': True, 'components': 5},
     'Folding (pivots) is not representable; this is the rigid equivalent.')

# E2E-05 complex computer desk: asymmetric, pedestal with drawer, tray on hangers, monitor riser ---------------
_dk = [B('TOP', [0, 732, 0], [1400, 18, 700]),
       B('LEG-R', [1332, 0, 30], [18, 732, 640]),
       B('PED-L', [50, 0, 30], [18, 732, 640]), B('PED-R', [468, 0, 30], [18, 732, 640]),
       B('PED-BOT', [68, 60, 30], [400, 18, 640]), B('PED-SH', [68, 400, 30], [400, 18, 640]),
       B('MODESTY', [486, 432, 600], [846, 300, 18]),
       B('HANG-L', [700, 640, 100], [18, 92, 350]), B('HANG-R', [1082, 640, 100], [18, 92, 350]),
       B('TRAY', [718, 640, 100], [364, 18, 350]),
       B('RISER-L', [500, 750, 40], [18, 100, 220]), B('RISER-R', [1150, 750, 40], [18, 100, 220]),
       B('RISER', [518, 832, 40], [632, 18, 220]),
       B('DRW-BOT', [73, 418, 40], [390, 18, 600], group='Drawer'), B('DRW-F', [73, 436, 622], [390, 150, 18], group='Drawer'),
       B('DRW-K', [73, 436, 40], [390, 150, 18], group='Drawer')]
_dc = [C('pl-t', 'tab_slot', 'PED-L', 'TOP'), C('pr-t', 'tab_slot', 'PED-R', 'TOP'), C('lr-t', 'tab_slot', 'LEG-R', 'TOP'),
       C('pb-l', 'tab_slot', 'PED-BOT', 'PED-L'), C('pb-r', 'tab_slot', 'PED-BOT', 'PED-R'),
       C('ps-l', 'tab_slot', 'PED-SH', 'PED-L'), C('ps-r', 'tab_slot', 'PED-SH', 'PED-R'),
       C('m-p', 'tab_slot', 'MODESTY', 'PED-R'), C('m-l', 'tab_slot', 'MODESTY', 'LEG-R'), C('m-t', 'tab_slot', 'MODESTY', 'TOP'),
       C('hl', 'tab_slot', 'HANG-L', 'TOP'), C('hr', 'tab_slot', 'HANG-R', 'TOP'),
       C('tl', 'tab_slot', 'TRAY', 'HANG-L'), C('tr', 'tab_slot', 'TRAY', 'HANG-R'),
       C('rl', 'tab_slot', 'RISER-L', 'TOP'), C('rr', 'tab_slot', 'RISER-R', 'TOP'),
       C('ri-l', 'tab_slot', 'RISER', 'RISER-L'), C('ri-r', 'tab_slot', 'RISER', 'RISER-R'),
       C('df', 'tab_slot', 'DRW-F', 'DRW-BOT'), C('dk', 'tab_slot', 'DRW-K', 'DRW-BOT')]
case('E2E-05', 'Complex computer desk', ['multi-board', 'asymmetric', 'compartments', 'removable'],
     'A 1400 x 750 x 700 mm computer desk: left pedestal with a shelf and a drawer, right leg panel, modesty panel, '
     'keyboard tray hung under the top and a monitor riser on top. 18 mm plywood.',
     v1('Computer desk', P18, _dk, _dc, overall=(1400, 850, 700)),
     {'compiles': True, 'components': 16, 'resting': ['DRW-BOT']})

# E2E-06 multi-level stepped storage (asymmetric heights) ------------------------------------------------------
_st = [B('S0', [0, 0, 0], [18, 1200, 350]), B('S1', [400, 0, 0], [18, 1200, 350]),
       B('S2', [800, 0, 0], [18, 800, 350]), B('S3', [1200, 0, 0], [18, 400, 350]),
       B('CAP0', [0, 1200, 0], [418, 18, 350]), B('CAP1', [418, 800, 0], [400, 18, 350]),
       B('CAP2', [818, 400, 0], [400, 18, 350])]
# shelf heights differ across every shared side panel (two tabs cannot share one through-slot)
for col, (x0, ys) in enumerate(((18, (60, 380, 700, 1020)), (418, (130, 450, 640)), (818, (60, 250)))):
    _st += [B(f'SH{col}{k}', [x0, y, 0], [382, 18, 350], group='Shelves') for k, y in enumerate(ys)]
case('E2E-06', 'Stepped multi-level storage', ['multi-board', 'asymmetric', 'compartments'],
     'A stepped storage unit with three columns of 1200, 800 and 400 mm height, 1218 x 350 mm footprint, 18 mm plywood.',
     v1('Stepped storage', P18, _st, 'auto', overall=(1218, 1218, 350)),
     {'compiles': True, 'components': len(_st)})

# E2E-07 mechanical puzzle: three mutually perpendicular interlocking plates (cross-laps between every pair) ----
case('E2E-07', 'Three-plate interlocking puzzle', ['complex-joints', 'mechanical'],
     'A wooden puzzle: three 120 mm square 6 mm plates that slot together at right angles through each other.',
     v1('Three-plate puzzle', P6, [
         B('PX', [57, 0, 0], [6, 120, 120]), B('PY', [0, 57, 0], [120, 6, 120]), B('PZ', [0, 0, 57], [120, 120, 6])],
        [C('xy', 'cross_lap', 'PX', 'PY'), C('xz', 'cross_lap', 'PX', 'PZ'), C('yz', 'cross_lap', 'PY', 'PZ')]),
     {'compiles': False},
     'Three plates crossing in all three axes cannot be assembled with simple halving notches (each pair needs '
     'notches from opposite edges that block the third plate); the engine must reject it, not produce it.')

# E2E-08 modular furniture: two identical open cubes stacked (top cube rests on the bottom one) ---------------
def _cube(p, y0):
    s, t = 400, 18
    return ([B(p + 'BASE', [0, y0, 0], [s, t, s], group=p), B(p + 'TOP', [0, y0 + s - t, 0], [s, t, s], group=p),
             B(p + 'L', [0, y0 + t, 20], [t, s - 2 * t, s - 40], group=p), B(p + 'R', [s - t, y0 + t, 20], [t, s - 2 * t, s - 40], group=p)],
            [C(p + 'l-b', 'tab_slot', p + 'L', p + 'BASE'), C(p + 'r-b', 'tab_slot', p + 'R', p + 'BASE'),
             C(p + 'l-t', 'tab_slot', p + 'L', p + 'TOP'), C(p + 'r-t', 'tab_slot', p + 'R', p + 'TOP')])


_m1b, _m1c = _cube('M1-', 0)
_m2b, _m2c = _cube('M2-', 400)
case('E2E-08', 'Stackable modular cubes', ['modular', 'nested', 'removable'],
     'Two identical 400 mm open storage cubes in 18 mm plywood that stack on top of each other.',
     v1('Modular cubes', P18, _m1b + _m2b, _m1c + _m2c, overall=(400, 800, 400)),
     {'compiles': True, 'components': 8, 'resting': ['M2-BASE']})

# E2E-09 multi-part enclosure: finger-jointed box, divider, vents, cable hole, engraved loose lid ---------------
case('E2E-09', 'Electronics enclosure', ['multi-board', 'removable', 'complex-joints', 'curved'],
     'A 240 x 100 x 160 mm enclosure in 6 mm plywood: finger-jointed walls, an internal divider, vent slots, '
     'a 20 mm cable hole and a lift-off engraved lid.',
     v1('Enclosure', P6, [
         B('BASE', [0, 0, 0], [240, 6, 160]),
         B('FRONT', [0, 6, 154], [240, 88, 6], openings=[{"id": f"vent{x}", "kind": "opening", "shape": "rect",
                                                           "center": [x, 50, 157], "size": [8, 40], "corner_radius": 4}
                                                          for x in (40, 70, 170, 200)]),
         B('BACK', [0, 6, 0], [240, 88, 6], openings=[{"id": "cable", "kind": "hole", "shape": "circle", "center": [200, 40, 3], "diameter": 20}]),
         B('LEFT', [0, 6, 6], [6, 88, 148]), B('RIGHT', [234, 6, 6], [6, 88, 148]),
         B('DIV', [117, 6, 6], [6, 70, 148]),
         B('LID', [0, 94, 0], [240, 6, 160], engravings=[{"id": "logo", "kind": "engrave", "shape": "circle", "center": [120, 80], "diameter": 40}])],
        [C('f-b', 'finger', 'FRONT', 'BASE'), C('k-b', 'finger', 'BACK', 'BASE'), C('l-b', 'finger', 'LEFT', 'BASE'),
         C('r-b', 'finger', 'RIGHT', 'BASE'), C('l-k', 'finger', 'LEFT', 'BACK'), C('l-f', 'finger', 'LEFT', 'FRONT'),
         C('r-k', 'finger', 'RIGHT', 'BACK'), C('r-f', 'finger', 'RIGHT', 'FRONT'),
         C('d-b', 'tab_slot', 'DIV', 'BASE'), C('d-f', 'tab_slot', 'DIV', 'FRONT'), C('d-k', 'tab_slot', 'DIV', 'BACK')],
        overall=(240, 100, 160)),
     {'compiles': True, 'components': 7, 'resting': ['LID']})

# E2E-10 acoustic guitar: bent sides and laminated parts are outside the flat-board model ----------------------
case('E2E-10', 'Acoustic guitar', ['curved', 'unsupported'],
     'An acoustic guitar: 500 x 380 mm body with a 90 mm sound hole, 100 mm deep, neck and headstock.',
     v1('Acoustic guitar', P6, [
         B('TOPPLATE', [0, 94, 0], [500, 6, 380], profile={"shape": "ellipse", "center": [250, 190], "width": 500, "height": 380},
           openings=[{"id": "sound", "kind": "opening", "shape": "circle", "center": [330, 97, 190], "diameter": 90}]),
         B('BACKPLATE', [0, 0, 0], [500, 6, 380], profile={"shape": "ellipse", "center": [250, 190], "width": 500, "height": 380}),
         B('NECK', [490, 100, 165], [600, 6, 50])],
        [C('n-t', 'tab_slot', 'NECK', 'TOPPLATE')]),
     {'compiles': False, 'supported': False},
     'Bent ribs, a laminated neck joint and carved parts cannot be expressed; the engine must reject, not fake it.')

# E2E-11 wooden boat (native format, the repository's own parametric boat) ------------------------------------
case('E2E-11', 'Wooden boat (native example)', ['curved', 'angled', 'multi-board'],
     'The built-in parametric boat model (native engine format).', {'native_example': 'boat'},
     {'compiles': True, 'ready': True})

# E2E-12 flat-bottom punt with vertical sides (supported) and E2E-13 the same with flared sides (unsupported) ---
_punt = [B('BOTTOM', [0, 0, 0], [600, 6, 220]),
         B('SIDE-B', [0, 6, 20], [600, 110, 6]), B('SIDE-F', [0, 6, 194], [600, 110, 6]),
         B('TRANSOM', [20, 6, 26], [6, 100, 168]), B('BOW', [574, 6, 26], [6, 100, 168]),
         B('SEAT', [280, 70, 26], [80, 6, 168])]
_pc = [C('sb', 'tab_slot', 'SIDE-B', 'BOTTOM'), C('sf', 'tab_slot', 'SIDE-F', 'BOTTOM'),
       C('tr', 'tab_slot', 'TRANSOM', 'BOTTOM'), C('bw', 'tab_slot', 'BOW', 'BOTTOM'),
       C('tr-b', 'tab_slot', 'TRANSOM', 'SIDE-B'), C('tr-f', 'tab_slot', 'TRANSOM', 'SIDE-F'),
       C('bw-b', 'tab_slot', 'BOW', 'SIDE-B'), C('bw-f', 'tab_slot', 'BOW', 'SIDE-F'),
       C('se-b', 'tab_slot', 'SEAT', 'SIDE-B'), C('se-f', 'tab_slot', 'SEAT', 'SIDE-F')]
case('E2E-12', 'Punt model, vertical sides', ['multi-board', 'boat'],
     'A 600 mm flat-bottom punt model in 6 mm plywood with vertical sides, transom, bow board and a seat.',
     v1('Punt (vertical sides)', P6, _punt, _pc, overall=(600, 116, 220)),
     {'compiles': True, 'ready': True, 'components': 6})
_flared = copy.deepcopy(_punt)
for b in _flared:
    if b['id'] == 'SIDE-B':
        b['rotate'] = {"axis": "x", "angle": 15, "pivot": [0, 6, 23]}
    if b['id'] == 'SIDE-F':
        b['rotate'] = {"axis": "x", "angle": -15, "pivot": [0, 6, 197]}
case('E2E-13', 'Punt model, flared sides', ['angled', 'boat', 'unsupported'],
     'The same punt with sides flared outwards by 15 degrees.',
     v1('Punt (flared)', P6, _flared, _pc[:4]),
     {'compiles': False, 'supported': False}, 'Needs bevelled edges, which the format cannot express.')

# E2E-14 wall-mounted shelf (hanging): back rail, two triangular brackets, shelf; nothing touches the floor ------
_br = {"shape": "polygon", "points": [[0, 0], [200, 0], [200, 200]]}     # u = y (height), v = z (depth)
case('E2E-14', 'Wall-mounted shelf', ['hanging', 'angled'],
     'A 600 mm wall shelf, 200 mm deep, screwed to the wall through a back rail, with two triangular brackets.',
     v1('Wall shelf', P18, [
         B('RAIL', [0, 0, 0], [600, 218, 18]),
         B('BRK-L', [100, 0, 18], [18, 200, 200], profile={"shape": "polygon", "points": [[0, 0], [200, 0], [200, 200], [180, 200]]}),
         B('BRK-R', [482, 0, 18], [18, 200, 200], profile={"shape": "polygon", "points": [[0, 0], [200, 0], [200, 200], [180, 200]]}),
         B('SHELF', [0, 200, 18], [600, 18, 200])],
        [C('bl', 'tab_slot', 'BRK-L', 'RAIL'), C('br', 'tab_slot', 'BRK-R', 'RAIL'),
         C('sl', 'tab_slot', 'BRK-L', 'SHELF'), C('sr', 'tab_slot', 'BRK-R', 'SHELF'), C('sh', 'tab_slot', 'SHELF', 'RAIL')],
        overall=(600, 218, 218), mounting='wall'),
     {'compiles': True, 'components': 4})

# E2E-15 cantilever table: both legs at one end of a long top -> tips over --------------------------------------
case('E2E-15', 'Cantilever table (tips over)', ['hanging', 'unsupported-structure'],
     'A 1200 mm long table top carried by two leg panels near its left end.',
     v1('Cantilever table', P18, [
         B('TOP', [0, 732, 0], [1200, 18, 600]),
         B('LEG-1', [60, 0, 40], [18, 732, 520]), B('LEG-2', [260, 0, 40], [18, 732, 520]),
         B('RAIL', [78, 500, 300], [182, 100, 18])],
        [C('l1', 'tab_slot', 'LEG-1', 'TOP'), C('l2', 'tab_slot', 'LEG-2', 'TOP'),
         C('r1', 'tab_slot', 'RAIL', 'LEG-1'), C('r2', 'tab_slot', 'RAIL', 'LEG-2')], overall=(1200, 750, 600)),
     {'compiles': True, 'components': 4, 'tips': True})

# E2E-16 floating board: a shelf drawn in mid-air, connected to nothing --------------------------------------
case('E2E-16', 'Table with a floating board', ['negative', 'unsupported-structure'],
     'A small table with an extra shelf that the AI forgot to connect.',
     v1('Table + floating shelf', P18, [
         B('TOP', [0, 482, 0], [600, 18, 400]), B('LEG-L', [40, 0, 40], [18, 482, 320]), B('LEG-R', [542, 0, 40], [18, 482, 320]),
         B('LOOSE', [100, 200, 60], [400, 18, 280])],
        [C('l', 'tab_slot', 'LEG-L', 'TOP'), C('r', 'tab_slot', 'LEG-R', 'TOP')], overall=(600, 500, 400)),
     {'compiles': False, 'error_codes': ['UNSUPPORTED_COMPONENT'], 'ready': False, 'components': 4, 'unsupported': ['LOOSE']})

# E2E-17 negative: shelves at equal heights on both sides of a shared panel (two tabs, one through-slot) -------
_neg = copy.deepcopy(CASES[[c['id'] for c in CASES].index('E2E-06')]['design'])
for b in _neg['boards']:
    if b['id'] == 'SH10':
        b['position'][1] = 60          # same height as SH00 on the other side of S1
case('E2E-17', 'Stepped storage, shelves sharing a slot', ['negative', 'complex-joints'],
     'The stepped storage unit with two shelves at the same height on both sides of a shared side panel.',
     _neg, {'compiles': False, 'error_codes': ['SLOT_ALREADY_USED']})

# E2E-18 negative: an internal divider whose tab lands in a vent opening -------------------------------------
_neg = copy.deepcopy(CASES[[c['id'] for c in CASES].index('E2E-09')]['design'])
for b in _neg['boards']:
    if b['id'] == 'FRONT':
        b['openings'].append({"id": "vent-mid", "kind": "opening", "shape": "rect", "center": [120, 50, 157], "size": [8, 40]})
case('E2E-18', 'Enclosure, divider tab lands in a vent', ['negative', 'complex-joints'],
     'The enclosure with a vent slot exactly where the divider meets the front wall.',
     _neg, {'compiles': False, 'error_codes': ['TAB_IN_OPENING']})
