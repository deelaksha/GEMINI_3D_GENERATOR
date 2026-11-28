import sys, os, json
sys.path.insert(0, os.getcwd())
from board_engine.canvas import compile_source
from board_engine import geometry as G
r = compile_source(open(sys.argv[1]).read(), run_production=True)
print('ok', r['ok'], 'kerf', r['design']['material']['kerf'], 'clearance', r['design']['material']['clearance'])
for c in r['design']['components']:
    print(c['id'], 'tabs', [(t['width'], t['depth']) for t in c.get('tabs', [])], 'slots', [(f['width'], f['height']) for f in c.get('features', []) if f['kind']=='slot'])
cut = r['layout']['cut']
print('kerf_compensation', cut['kerf_compensation'], 'issues', cut['issues'][:3])
for sh in cut['sheets']:
    for p in sh['paths']:
        if p['shape'] == 'polyline':
            bb = G.bbox(p['points'])
            print(p['id'], p['type'], 'bbox w/h', round(bb[2]-bb[0], 3), round(bb[3]-bb[1], 3), 'area', round(G.signed_area(p['points']), 2))
        else:
            print(p['id'], p['type'], p['shape'], p.get('radius'))
