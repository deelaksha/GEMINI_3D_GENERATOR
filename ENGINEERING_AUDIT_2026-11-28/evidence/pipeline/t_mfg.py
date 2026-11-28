import json, sys, time, copy
sys.path.insert(0,'.')
from board_engine.canvas import compile_source, pretty_json
from board_engine.views import production_package
from board_engine import geometry as G
from board_engine.model import Plate
S=sys.argv[1]
def pkg_for(src, machine=None):
    r=compile_source(src, run_production=False, machine=machine)
    return r, production_package(r['design'], {'compensate_kerf': True})
D=json.load(open(S+'/example.json'))
r,p=pkg_for(pretty_json(D))
print('material kerf used (no machine, plywood 18):', p['cut']['kerf_compensation'])
for sh in p['cut']['sheets'][:1]:
    for path in sh['paths'][:40]:
        if path['shape']=='circle': print('  circle', path['id'], 'radius', path['radius'], '(design diameter 40 -> r 20)')
outer=[x for s in p['cut']['sheets'] for x in s['paths'] if x['type']=='outer']
inner=[x for s in p['cut']['sheets'] for x in s['paths'] if x['type']=='inner' and x['shape']=='polyline']
p0=production_package(r['design'], {'compensate_kerf': False})
o0={x['id']:x for s in p0['cut']['sheets'] for x in s['paths']}
A=lambda x: abs(G.signed_area(x['points']))
o=outer[0]; print('  outer', o['id'], 'compensated area', round(A(o)), 'uncompensated', round(A(o0[o['id']])))
i=inner[0]; print('  inner', i['id'], 'compensated area', round(A(i),1), 'uncompensated', round(A(o0[i['id']]),1))
print('  all outers grow:', all(A(x)>A(o0[x['id']]) for x in outer), '| all polyline inners shrink:', all(A(x)<A(o0[x['id']]) for x in inner), f'({len(outer)} outers, {len(inner)} inners)')
# 6mm plywood, CW profile
d=copy.deepcopy(D); 
print('\n6 mm plywood laser-ish design with no machine:')
d6=json.loads(json.dumps(D).replace('18','6')) 
r6=compile_source(pretty_json(d6), run_production=False); 
print('  kerf from catalogue:', r6['design']['material']['kerf'] if r6.get('design') else r6['diagnostics'][:2])
# nesting yield
n=p['nesting']; 
used=sum(abs(G.signed_area(Plate(r['design'], c).cut)) for c in r['design']['components'])
sheet=n['sheet']['width']*n['sheet']['height']
print('\nexample nesting: sheets', n['sheet_count'], 'sheet', n['sheet'], 'algo keys', [k for k in n if k not in('placements',)][:12])
print('  yield = part area / (sheets*sheet area) =', round(used/(n['sheet_count']*sheet)*100,1), '%')
src=open('board_engine/examples/my_home.json').read()
t=time.time(); rh,ph=pkg_for(src); dt=time.time()-t
n=ph['nesting']; used=sum(abs(G.signed_area(Plate(rh['design'], c).cut)) for c in rh['design']['components']); sheet=n['sheet']['width']*n['sheet']['height']
print(f'my_home: {len(rh["design"]["components"])} parts, sheets {n["sheet_count"]} of {n["sheet"]["width"]}x{n["sheet"]["height"]}, yield {used/(n["sheet_count"]*sheet)*100:.1f}%, method={n.get("method") or n.get("strategy")}, t={dt:.1f}s, kerf={ph["cut"]["kerf_compensation"]}')
print('  blocking', len(ph['blocking_issues']))
