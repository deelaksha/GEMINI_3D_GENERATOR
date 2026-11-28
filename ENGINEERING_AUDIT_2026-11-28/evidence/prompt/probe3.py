import json, sys, os
sys.path.insert(0, os.getcwd())
from board_engine.canvas import compile_source
b = {"format":"board-design/v1","product":{"name":"t","description":"","overall":{"length":100,"height":12,"depth":100}},"material":{"type":"plywood","thickness":6}}
d1={"id":"D1","position":[0,0,0],"size":[100,6,100],"profile":{"shape":"circle","center":[50,50],"diameter":100}}
d2={"id":"D2","position":[10,6,10],"size":[80,6,80],"profile":{"shape":"circle","center":[40,40],"diameter":80}}
for conn in ([{"type":"tab_slot","board":"D2","into":"D1"}], "auto"):
    r = compile_source(json.dumps(dict(b, boards=[d1,d2], connections=conn)), run_production=False)
    print('stacked discs', conn if isinstance(conn,str) else 'tab_slot', [(x['severity'],x['code'],x['message'][:120]) for x in r['diagnostics'] if x['severity'] in ('error','warning')])
