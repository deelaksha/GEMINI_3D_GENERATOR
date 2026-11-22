import json, sys, time, copy, tracemalloc
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from scenarios import S, B, C
from board_engine.canvas import compile_source
from board_engine.views import production_package, model3d
from board_engine import geometry as G
from board_engine.nesting import transform_point
# 2D (nested cut paths, no kerf) vs 3D (model3d) — same parts, same areas, same hole counts?
for name in ('02-chair','03a-table','04-bookshelf-auto','05-cabinet-door','07-storage-box'):
    r = compile_source(json.dumps(S[name]), run_production=False)
    d = r['design']; m3 = {c['id']: c for c in r['model3d']['components']}
    pkg = production_package(d, {'compensate_kerf': False})
    bad = []
    outers = {p['part']: p for s in pkg['cut']['sheets'] for p in s['paths'] if p['type'] == 'outer'}
    inners = {}
    for s in pkg['cut']['sheets']:
        for p in s['paths']:
            if p['type'] == 'inner': inners[p['part']] = inners.get(p['part'], 0) + 1
    for cid, c in m3.items():
        a3 = abs(G.signed_area(c['cut_outline'])); a2 = abs(G.signed_area(outers[cid]['points']))
        if abs(a3 - a2) > 0.01 or inners.get(cid, 0) != len(c['features']): bad.append((cid, round(a3,2), round(a2,2), inners.get(cid,0), len(c['features'])))
    missing = set(m3) - set(outers)
    print(f"{name}: parts3d={len(m3)} parts2d={len(outers)} missing={sorted(missing)} mismatches={bad}")

# Scale: N x N cubby grid with cross-laps + base, auto connections
for n in (4, 8, 12):
    cell, t, H = 150, 6, 150
    boards = [B("BASE", [0, 0, 0], [n*cell, t, n*cell])]
    for i in range(1, n):
        boards.append(B(f"X{i}", [3, t, i*cell], [n*cell-6, H, t]))
        boards.append(B(f"Z{i}", [i*cell, t, 3], [t, H, n*cell-6]))
    src = {"format": "board-design/v1", "product": {"name": f"grid{n}"}, "material": {"name": "ply 6", "type": "plywood", "thickness": 6},
           "boards": boards, "connections": "auto"}
    tracemalloc.start(); t0 = time.time(); r = compile_source(json.dumps(src)); dt = time.time() - t0
    peak = tracemalloc.get_traced_memory()[1] / 1e6; tracemalloc.stop()
    print(f"grid {n}x{n}: boards={r['summary'] and r['summary']['boards']} joints={r['summary'] and r['summary']['joints']} ok={r['ok']} secs={dt:.1f} peakMB={peak:.0f} errs={sorted({x['code'] for x in r['diagnostics'] if x['severity']=='error'})[:5]}")
