import json, copy, sys
sys.path.insert(0,'.')
from board_engine.canvas import compile_source, pretty_json
S=sys.argv[1]; D=json.load(open(S+'/example.json'))
def split(d, groupA='Frame', groupB='Frame', conn_type='butt'):
    bs=[b for b in d['boards'] if b['id']!='MODESTY']
    bs.append({'id':'MOD-A','name':'Modesty left','group':groupA,'position':[68,432,480],'size':[532,300,18]})
    bs.append({'id':'MOD-B','name':'Modesty right','group':groupB,'position':[600,432,480],'size':[532,300,18]})
    d['boards']=bs
    cs=[c for c in d['connections'] if c['board']!='MODESTY']
    cs+= [{'id':'MA-TOP','type':'tab_slot','board':'MOD-A','into':'TOP','tabs':2},{'id':'MB-TOP','type':'tab_slot','board':'MOD-B','into':'TOP','tabs':2},
          {'id':'MA-L','type':'tab_slot','board':'MOD-A','into':'LEG-L','tabs':1},{'id':'MB-R','type':'tab_slot','board':'MOD-B','into':'LEG-R','tabs':1}]
    if conn_type: cs.append({'id':'MA-MB','type':conn_type,'board':'MOD-A','into':'MOD-B'})
    d['connections']=cs; return d
def show(name, d):
    open(S+f'/cons_{name}.json','w').write(pretty_json(d))
    r=compile_source(pretty_json(d), run_production=False)
    m=r.get('consolidation') or {}
    ids=[c['id'] for c in r['design']['components']] if r.get('design') else None
    print(f"\n## {name}: ok={r['ok']} applied={m.get('applied')} groups={[(g['board'],g['from']) for g in m.get('groups',[])]} skipped={[(s['boards'],s['reason'][:60]) for s in m.get('skipped',[])]}")
    print('   final boards:', ids)
    if r.get('design'):
        for c in r['design']['components']:
            if c['id'] not in ('TOP','LEG-L','LEG-R','SHELF'): print('   ', c['id'], 'group=', c.get('group'), 'name=', c.get('name'))
        print('   joint types:', sorted({j.get('type') for j in r['design']['joints']}))
    print('   codes:', sorted({x['code'] for x in r['diagnostics'] if x['severity']!='info'}), [x['message'][:200] for x in r['diagnostics'] if x['code'] in('CONSOLIDATED',)])
show('A_diff_groups_butt', split(copy.deepcopy(D),'Door','Frame','butt'))
show('B_hinge_between', split(copy.deepcopy(D),'Frame','Frame','hinge'))
show('B2_no_conn', split(copy.deepcopy(D),'Frame','Frame',None))
d=split(copy.deepcopy(D)); d['motions']=[{'id':'flap','type':'rotate','boards':['MOD-B'],'on':'MOD-A','axis':'y','pivot':[600,432,489],'range':[0,30]}]
d['connections']=[c for c in d['connections'] if c['id'] not in ('MA-MB','MB-TOP','MB-R')]
show('C_moving_board', d)
d=split(copy.deepcopy(D),'Frame','Frame','butt'); d['boards'].append({'id':'FLAP','position':[300,232,480],'size':[200,200,18]})
d['motions']=[{'id':'flap','type':'rotate','boards':['FLAP'],'on':'MOD-A','axis':'z','pivot':[400,432,489],'range':[-10,10]}]
show('D_on_board_merged', d)
d=split(copy.deepcopy(D),'Frame','Frame','butt'); d['consolidate']=False; show('E_consolidate_false', d)
d=split(copy.deepcopy(D),'Frame','Frame','butt'); d['plan']={'steps':[{'boards':['MOD-A'],'text':'fit left modesty'},{'boards':['MOD-B'],'text':'fit right'}]}
show('F_plan_refs', d)
