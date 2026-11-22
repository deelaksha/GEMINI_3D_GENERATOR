import json, sys, time, copy
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from scenarios import S, B, C
from board_engine.canvas import compile_source, apply_code_fix
def run(d): return compile_source(d if isinstance(d,str) else json.dumps(d))
def codes(r,sev='error'): return sorted({x['code'] for x in r['diagnostics'] if x['severity']==sev})

# A. 'safe' fixes: do they converge? (table mistake, toy car cross_lap suggestion)
for name in ('03b-table-leg-mistake','09-toy-car'):
    src=json.dumps(S[name]); r=run(src)
    safe=[f for d in r['diagnostics'] for f in (d.get('fixes') or []) if f.get('safe')]
    print(name,'errors',codes(r),'safe fixes',[f['title'] for f in safe][:4])
    for f in safe[:1]:
        src2=apply_code_fix(src,f); r2=run(src2); print('  after',f['id'],'-> ok',r2['ok'],codes(r2), [x['message'][:150] for x in r2['diagnostics'] if x['severity']=='error'][:2])
    # all non-safe first-fix per error
    if name.startswith('03b'):
        s=src
        for _ in range(5):
            r=run(s); errs=[d for d in r['diagnostics'] if d['severity']=='error' and d.get('fixes')]
            if not errs: break
            s=apply_code_fix(s,errs[0]['fixes'][0])
        print('  iterate first fixes ->',run(s)['ok'],codes(run(s)))

# B. wardrobe: shelves staggered across the divider
w=copy.deepcopy(S['10-wardrobe'])
for b in w['boards']:
    if b['id'].startswith('SH-R'): b['position'][1]+=60
r=run(w); print('wardrobe staggered ok',r['ok'],r.get('summary'),codes(r),codes(r,'warning'))
# B2: same height but different tab counts
w=copy.deepcopy(S['10-wardrobe'])
for c in w['connections']:
    if c['id'].startswith('shl') and c['id'].endswith('b'): c['tabs']=1
r=run(w); print('wardrobe tabs differ ok',r['ok'],codes(r))

# C. corrected desk: tray hung on two hangers tabbed into TOP
d=copy.deepcopy(S['08-computer-desk'])
d['boards']=[b for b in d['boards'] if not b['id'].startswith('DRW')]
d['connections']=[c for c in d['connections'] if c['id']!='drw']
for b in d['boards']:
    if b['id']=='TRAY': b['position']=[418,640,100]; b['size']=[364,18,350]
d['boards']+=[B("HANG-L",[400,640,100],[18,92,350]),B("HANG-R",[782,640,100],[18,92,350])]
d['connections']=[c for c in d['connections'] if c['id']!='tray-top']+[C("hl","tab_slot","HANG-L","TOP"),C("hr","tab_slot","HANG-R","TOP"),C("tl","tab_slot","TRAY","HANG-L"),C("tr","tab_slot","TRAY","HANG-R")]
r=run(d); print('desk corrected ok',r['ok'],r.get('summary'),codes(r),[x['message'][:200] for x in r['diagnostics'] if x['severity']=='error'][:2])

# D. determinism
a=run(S['04-bookshelf-auto']); b=run(S['04-bookshelf-auto'])
strip=lambda r: json.dumps({k:r[k] for k in ('model3d','layout','summary')},sort_keys=True).replace('joined_at','')
import re
norm=lambda r: re.sub(r'"joined_at": "[^"]*"','',json.dumps({k:r[k] for k in ('design','summary')},sort_keys=True))
print('deterministic (design+summary)',norm(a)==norm(b))

# E. guitar neck on face -> can it be expressed at all? try every v1 type
for t in ('tab_slot','butt','finger','cross_lap'):
    g=copy.deepcopy(S['01-guitar']); g['boards']=g['boards'][:2]; g['joinery']='glue_allowed'
    g['connections']=[C('n',t,'NECK','BODY')]
    r=run(g); print('guitar neck-on-face as',t,'->',codes(r))

# F. 3D vs 2D consistency: area of each nested part vs 3D outline area (same geometry?)
from board_engine import geometry as G
r=compile_source(json.dumps(S['07-storage-box']))
m3={c['id']:c for c in r['model3d']['components']}
print('model3d keys sample', list(next(iter(m3.values())).keys()))
