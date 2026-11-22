"""Audit scenarios: AI-style board-design/v1 sources for 10 product categories, compiled by the real engine."""
import json, sys, time, copy
sys.path.insert(0, sys.argv[1])
from board_engine.canvas import compile_source
from board_engine.canvas_prompt import EXAMPLE

P18 = {"name": "Birch plywood 18 mm", "type": "plywood", "thickness": 18}
P6 = {"name": "Birch plywood 6 mm", "type": "plywood", "thickness": 6}

def B(i, pos, size, **kw):
    return dict(id=i, name=i, position=pos, size=size, **kw)

def C(i, t, a, b, **kw):
    return dict(id=i, type=t, board=a, into=b, **kw)

S = {}

# 1. Guitar (flat display guitar): curved body profile, sound hole, neck lying ON the body face
S['01-guitar'] = {"format": "board-design/v1", "product": {"name": "Display guitar", "overall": {"length": 1000, "height": 360, "depth": 30}},
    "material": P6, "boards": [
        B("BODY", [0, 0, 0], [450, 360, 6], profile={"shape": "ellipse", "center": [225, 180], "width": 450, "height": 360},
          openings=[{"id": "hole", "kind": "opening", "shape": "circle", "center": [300, 180, 3], "diameter": 90}]),
        B("NECK", [380, 155, 6], [620, 50, 6]),
        B("HEAD", [1000 - 6, 140, 0], [6, 80, 30])],
    "connections": [C("neck-body", "tab_slot", "NECK", "BODY"), C("head-neck", "tab_slot", "HEAD", "NECK")]}

# 2. Wooden chair: profiled sides, seat, backrest tilted 8 deg
side_prof = {"shape": "polygon", "points": [[0, 0], [0, 420], [450, 420], [450, 60], [850, 60], [850, 0]]}
S['02-chair'] = {"format": "board-design/v1", "product": {"name": "Plywood chair", "overall": {"length": 454, "height": 850, "depth": 420}},
    "material": P18, "boards": [
        B("SIDE-L", [0, 0, 0], [18, 850, 420], profile=side_prof),
        B("SIDE-R", [436, 0, 0], [18, 850, 420], profile=side_prof),
        B("SEAT", [18, 400, 60], [418, 18, 340]),
        B("BACK", [18, 560, 20], [418, 240, 18], rotate={"axis": "x", "angle": -8}),
        B("STRETCHER", [18, 120, 200], [418, 80, 18])],
    "connections": [C("s-l", "tab_slot", "SEAT", "SIDE-L"), C("s-r", "tab_slot", "SEAT", "SIDE-R"),
                    C("b-l", "tab_slot", "BACK", "SIDE-L"), C("b-r", "tab_slot", "BACK", "SIDE-R"),
                    C("st-l", "tab_slot", "STRETCHER", "SIDE-L"), C("st-r", "tab_slot", "STRETCHER", "SIDE-R")]}

# 3a. Table: the prompt's own example. 3b. same with the classic mistake (legs = overall height)
S['03a-table'] = copy.deepcopy(EXAMPLE)
t = copy.deepcopy(EXAMPLE)
for b in t['boards']:
    if b['id'].startswith('LEG'):
        b['size'][1] = 750
S['03b-table-leg-mistake'] = t

# 4. Bookshelf 800 x 1800 x 300, connections inferred ("auto")
shelves = [B(f"SHELF-{k}", [18, y, 0], [764, 18, 294]) for k, y in enumerate((60, 400, 750, 1100, 1450, 1760))]
S['04-bookshelf-auto'] = {"format": "board-design/v1", "product": {"name": "Bookshelf", "overall": {"length": 800, "height": 1800, "depth": 300}},
    "material": P18, "boards": [B("SIDE-L", [0, 0, 0], [18, 1800, 300]), B("SIDE-R", [782, 0, 0], [18, 1800, 300])] + shelves
    + [B("BACK", [18, 78, 294], [764, 1682, 6], thickness=6)], "connections": "auto"}

# 5. Kitchen base cabinet with hinged door (glue allowed)
S['05-cabinet-door'] = {"format": "board-design/v1", "product": {"name": "Base cabinet", "overall": {"length": 600, "height": 720, "depth": 580}},
    "material": P18, "joinery": "glue_allowed", "boards": [
        B("SIDE-L", [0, 0, 0], [18, 720, 560]), B("SIDE-R", [582, 0, 0], [18, 720, 560]),
        B("BOTTOM", [18, 50, 0], [564, 18, 560]), B("TOP", [18, 684, 0], [564, 18, 560]),
        B("SHELF", [18, 360, 30], [564, 18, 500]),
        B("BACK", [18, 68, 10], [564, 616, 18]),
        B("DOOR", [0, 0, 562], [600, 720, 18])],
    "connections": [C("b-l", "tab_slot", "BOTTOM", "SIDE-L"), C("b-r", "tab_slot", "BOTTOM", "SIDE-R"),
                    C("t-l", "tab_slot", "TOP", "SIDE-L"), C("t-r", "tab_slot", "TOP", "SIDE-R"),
                    C("sh-l", "butt", "SHELF", "SIDE-L", fasteners="dowel"), C("sh-r", "butt", "SHELF", "SIDE-R", fasteners="dowel"),
                    C("bk-l", "tab_slot", "BACK", "SIDE-L"), C("bk-r", "tab_slot", "BACK", "SIDE-R"),
                    C("bk-b", "tab_slot", "BACK", "BOTTOM"), C("bk-t", "tab_slot", "TOP", "BACK"),
                    C("door", "hinge", "DOOR", "SIDE-L", edge="-x", count=2, gap=2)]}

# 6. Flat-bottom punt: flared sides tilted 15 deg about z... about the length axis (x)
S['06-boat-punt'] = {"format": "board-design/v1", "product": {"name": "Punt model", "overall": {"length": 600, "height": 120, "depth": 260}},
    "material": P6, "boards": [
        B("BOTTOM", [0, 0, 0], [600, 6, 220]),
        B("SIDE-B", [0, 6, 20], [600, 110, 6], rotate={"axis": "x", "angle": 15, "pivot": [0, 6, 23]}),
        B("SIDE-F", [0, 6, 194], [600, 110, 6], rotate={"axis": "x", "angle": -15, "pivot": [0, 6, 197]}),
        B("TRANSOM", [20, 6, 26], [6, 100, 168]), B("BOW", [574, 6, 26], [6, 100, 168])],
    "connections": [C("sb", "tab_slot", "SIDE-B", "BOTTOM"), C("sf", "tab_slot", "SIDE-F", "BOTTOM"),
                    C("tr", "tab_slot", "TRANSOM", "BOTTOM"), C("bw", "tab_slot", "BOW", "BOTTOM")]}

# 7. Storage box with finger corners and a loose lid
S['07-storage-box'] = {"format": "board-design/v1", "product": {"name": "Storage box", "overall": {"length": 300, "height": 156, "depth": 200}},
    "material": P6, "boards": [
        B("BASE", [0, 0, 0], [300, 6, 200]),
        B("FRONT", [0, 6, 194], [300, 144, 6]), B("BACK", [0, 6, 0], [300, 144, 6]),
        B("LEFT", [0, 6, 6], [6, 144, 188]), B("RIGHT", [294, 6, 6], [6, 144, 188]),
        B("LID", [0, 150, 0], [300, 6, 200])],
    "connections": [C("f-b", "finger", "FRONT", "BASE"), C("k-b", "finger", "BACK", "BASE"),
                    C("l-b", "finger", "LEFT", "BASE"), C("r-b", "finger", "RIGHT", "BASE"),
                    C("l-k", "finger", "LEFT", "BACK"), C("l-f", "finger", "LEFT", "FRONT"),
                    C("r-k", "finger", "RIGHT", "BACK"), C("r-f", "finger", "RIGHT", "FRONT")]}

# 8. Computer desk: table + CPU shelf + keyboard tray + drawer box resting on a runner board
desk = copy.deepcopy(EXAMPLE)
desk['product'] = {"name": "Computer desk", "overall": {"length": 1200, "height": 750, "depth": 600}}
desk['boards'] += [B("TRAY", [400, 640, 100], [400, 18, 350]),
                   B("DRW-BOT", [700, 560, 60], [300, 18, 380]), B("DRW-F", [700, 578, 422], [300, 100, 18])]
desk['connections'] += [C("tray-top", "tab_slot", "TRAY", "TOP"), C("drw", "tab_slot", "DRW-F", "DRW-BOT")]
S['08-computer-desk'] = desk

# 9. Wooden toy car: profiled sides with axle holes, floor, 4 wheels next to the sides, axle as a 6x6 strip
S['09-toy-car'] = {"format": "board-design/v1", "product": {"name": "Toy car", "overall": {"length": 200, "height": 90, "depth": 100}},
    "material": P6, "boards": [
        B("SIDE-B", [0, 10, 20], [200, 70, 6], profile={"shape": "path", "start": [0, 0], "segments": [
            {"line": [200, 0]}, {"line": [200, 35]}, {"line": [140, 40]}, {"arc": {"to": [60, 40], "radius": 45}}, {"line": [0, 35]}]},
          openings=[{"id": "ax1", "kind": "hole", "shape": "circle", "center": [40, 20, 23], "diameter": 6.4},
                    {"id": "ax2", "kind": "hole", "shape": "circle", "center": [160, 20, 23], "diameter": 6.4}]),
        B("SIDE-F", [0, 10, 74], [200, 70, 6]),
        B("FLOOR", [10, 30, 26], [180, 6, 48]),
        B("WHEEL-1", [15, 0, 11], [50, 50, 6], profile={"shape": "circle", "center": [25, 25], "diameter": 50}),
        B("AXLE-1", [37, 17, 5], [6, 6, 90], normal="x")],
    "connections": [C("fl-b", "tab_slot", "FLOOR", "SIDE-B"), C("fl-f", "tab_slot", "FLOOR", "SIDE-F")]}

# 10. Wardrobe: 2 bays, middle divider, 6 shelves, back, 2 hinged doors
wb = [B("SIDE-L", [0, 0, 0], [18, 2000, 550]), B("SIDE-R", [982, 0, 0], [18, 2000, 550]),
      B("BOTTOM", [18, 80, 0], [964, 18, 550]), B("TOP", [18, 1960, 0], [964, 18, 550]),
      B("MID", [491, 98, 30], [18, 1862, 520]), B("BACK", [18, 98, 10], [964, 1862, 6], thickness=6)]
wc = [C("b-l", "tab_slot", "BOTTOM", "SIDE-L"), C("b-r", "tab_slot", "BOTTOM", "SIDE-R"),
      C("t-l", "tab_slot", "TOP", "SIDE-L"), C("t-r", "tab_slot", "TOP", "SIDE-R"),
      C("m-b", "tab_slot", "MID", "BOTTOM"), C("m-t", "tab_slot", "MID", "TOP")]
for k, y in enumerate((500, 900, 1300)):
    wb += [B(f"SH-L{k}", [18, y, 30], [473, 18, 520]), B(f"SH-R{k}", [509, y, 30], [473, 18, 520])]
    wc += [C(f"shl{k}a", "tab_slot", f"SH-L{k}", "SIDE-L"), C(f"shl{k}b", "tab_slot", f"SH-L{k}", "MID"),
           C(f"shr{k}a", "tab_slot", f"SH-R{k}", "MID"), C(f"shr{k}b", "tab_slot", f"SH-R{k}", "SIDE-R")]
wb += [B("DOOR-L", [0, 0, 552], [499, 2000, 18]), B("DOOR-R", [501, 0, 552], [499, 2000, 18])]
wc += [C("dl", "hinge", "DOOR-L", "SIDE-L", edge="-x", count=4), C("dr", "hinge", "DOOR-R", "SIDE-R", edge="+x", count=4)]
S['10-wardrobe'] = {"format": "board-design/v1", "product": {"name": "Wardrobe", "overall": {"length": 1000, "height": 2000, "depth": 570}},
                    "material": P18, "joinery": "glue_allowed", "boards": wb, "connections": wc + [{"id": "auto-back", "type": "tab_slot", "board": "BACK", "into": "BOTTOM"}]}

# ---- Robustness / AI-failure inputs
E = {}
E['E01-invalid-json'] = '{"format": "board-design/v1", "boards": [ {"id": "A", "position": [0,0,0] "size": [1,2,3]} ]}'
E['E02-javascript'] = 'const design = { boards: [] };\nexport default design;'
E['E03-prose-plus-fence'] = 'Sure! Here is the design:\n```json\n' + json.dumps(EXAMPLE) + '\n```\nLet me know!'
E['E04-trailing-commas-comments'] = json.dumps(EXAMPLE).replace('"boards": [', '"boards": [ // the panels\n').replace('}]', '},]')
E['E05-missing-material'] = json.dumps({k: v for k, v in EXAMPLE.items() if k != 'material'})
E['E06-no-dimensions-size'] = json.dumps(dict(EXAMPLE, boards=[{"id": "TOP", "position": [0, 0, 0]}]))
E['E07-conflicting-overall'] = json.dumps(dict(EXAMPLE, product=dict(EXAMPLE['product'], overall={"length": 1500, "height": 750, "depth": 600})))
E['E08-thickness-mismatch'] = json.dumps(dict(EXAMPLE, boards=[dict(b, size=[b['size'][0], 20, b['size'][2]]) if b['id'] == 'TOP' else b for b in EXAMPLE['boards']]))
E['E09-unknown-type'] = json.dumps(dict(EXAMPLE, connections=[dict(c, type='glue') for c in EXAMPLE['connections']]))
E['E10-alias-types-names'] = json.dumps(dict(EXAMPLE, connections=[{"id": c['id'], "type": "mortise_and_tenon", "from": c['board'].lower(), "to": c['into']} for c in EXAMPLE['connections']]))
long_a, long_b = 'A' * 40, 'B' * 40
E['E11-long-ids-auto'] = json.dumps({"format": "board-design/v1", "material": P18, "boards": [
    B(long_a, [0, 0, 0], [600, 18, 400]), B(long_b, [100, 18, 100], [18, 300, 200])], "connections": "auto"})
E['E12-small-hole-sawkerf'] = json.dumps({"format": "board-design/v1", "material": P18, "connections": [], "boards": [
    B("P", [0, 0, 0], [300, 18, 200], openings=[{"id": "pin", "kind": "hole", "shape": "circle", "center": [150, 9, 100], "diameter": 3}])]})
E['E13-hinge-count-out-of-range'] = json.dumps(dict(S['05-cabinet-door'], connections=[dict(c, count=12) if c['type'] == 'hinge' else c for c in S['05-cabinet-door']['connections']]))
E['E14-duplicate-boards'] = json.dumps(dict(EXAMPLE, boards=EXAMPLE['boards'] + [dict(EXAMPLE['boards'][0], id='TOP-2')]))
E['E15-floating-board'] = json.dumps(dict(EXAMPLE, boards=EXAMPLE['boards'] + [B("ORPHAN", [2000, 0, 0], [300, 18, 300])]))
E['E16-opening-outside-board'] = json.dumps(dict(EXAMPLE, boards=[dict(b, openings=[{"id": "x", "kind": "hole", "shape": "circle", "center": [1500, 741, 300], "diameter": 40}]) if b['id'] == 'TOP' else b for b in EXAMPLE['boards']]))
E['E17-empty'] = '   '
E['E18-native-format'] = json.dumps({"id": "n", "material": {"thickness": 3}, "components": [{"id": "A", "outline": [[0, 0], [50, 0], [50, 50], [0, 50]]}], "joints": []})
E['E19-huge-thin-board'] = json.dumps({"format": "board-design/v1", "material": P18, "connections": [], "boards": [B("BIG", [0, 0, 0], [3000, 18, 1500])]})
E['E20-thickness-not-standard'] = json.dumps(dict(EXAMPLE, material=dict(P18, thickness=17), boards=[dict(b, size=[17 if v == 18 else v for v in b['size']]) for b in EXAMPLE['boards']]))


def summarise(name, src):
    t0 = time.time()
    r = compile_source(src if isinstance(src, str) else json.dumps(src))
    dt = time.time() - t0
    d = r['diagnostics']
    codes = lambda sev: sorted({x['code'] for x in d if x['severity'] == sev})
    lay = r.get('layout') or {}
    nest = lay.get('nesting') or {}
    out = {'name': name, 'ok': r['ok'], 'secs': round(dt, 2), 'summary': r.get('summary'),
           'errors': codes('error'), 'warnings': codes('warning'), 'info': codes('info'),
           'first_errors': [x['message'][:240] for x in d if x['severity'] == 'error'][:4],
           'sheets': nest.get('sheet_count'), 'efficiency': (nest.get('stats') or {}).get('efficiency_percent'),
           'ready_for_production': lay.get('ready_for_production'),
           'blocking': sorted({b.get('code') for b in lay.get('blocking_issues', []) if isinstance(b, dict)}),
           'cut_issues': sorted({i['code'] for i in (lay.get('cut') or {}).get('issues', [])}),
           'cut_kerf': (lay.get('cut') or {}).get('kerf_compensation')}
    if name.startswith('E12') and lay.get('cut'):
        out['hole_radius'] = [p.get('radius') for s in lay['cut']['sheets'] for p in s['paths'] if p.get('shape') == 'circle']
    return out


if __name__ == '__main__':
    which = sys.argv[2] if len(sys.argv) > 2 else 'all'
    res = [summarise(k, v) for k, v in {**S, **E}.items() if which == 'all' or k.startswith(which)]
    print(json.dumps(res, indent=1))
