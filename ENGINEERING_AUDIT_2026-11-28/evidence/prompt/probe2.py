import json, sys, os, collections
sys.path.insert(0, os.getcwd())
from board_engine.canvas import compile_source
def run(name, d):
    r = compile_source(json.dumps(d), run_production=False)
    ds = r['diagnostics']
    print(name, 'errors', [ (x['code'], x['message'][:150]) for x in ds if x['severity']=='error'][:6])
    print('   warnings', collections.Counter(x['code'] for x in ds if x['severity']=='warning'), 'summary', {k:v for k,v in (r.get('summary') or {}).items() if k in ('boards','errors','warnings','parts')})
def base(l,h,d): return {"format":"board-design/v1","product":{"name":"t","description":"","overall":{"length":l,"height":h,"depth":d}},"material":{"type":"plywood","thickness":6}}
rib = {"id": "RIB", "position": [0, 6, 0], "size": [6, 40, 60],
    "profile": {"shape": "polygon", "points": [[0, 15], [0, 45], [40, 60], [40, 0]]},
    "repeat": {"count": 9, "step": [40, 0, 0], "morph": [
      {"size": [6, 80, 140], "profile": {"shape": "polygon", "points": [[0, 35], [0, 105], [80, 140], [80, 0]]}, "shift": [0, 0, -40]},
      {"size": [6, 30, 40], "profile": {"shape": "polygon", "points": [[0, 10], [0, 30], [30, 40], [30, 0]]}, "shift": [0, 0, 10]}]}}
keel = {"id":"KEEL","position":[-20,0,-20],"size":[380,6,120]}
run('2b morph example, keel extended', dict(base(380,86,140), boards=[keel, rib], connections=[{"type": "tab_slot", "board": "RIB-*", "into": "KEEL"}]))
disk = {"id":"HUB","position":[100,0,100],"size":[100,6,100]}
blade = {"id":"BL","position":[147,6,160],"size":[6,60,35],"radial":{"count":4,"axis":"y","center":[150,6,150]}}
run('3b radial 4 blades', dict(base(100,66,100), boards=[disk, blade], connections=[{"type":"tab_slot","board":"BL-*","into":"HUB"}]))
blade6 = dict(blade, radial={"count":6,"axis":"y","center":[150,6,150]})
run('3c radial 6 blades (60deg tilted copies)', dict(base(100,66,100), boards=[disk, blade6], connections=[{"type":"tab_slot","board":"BL-*","into":"HUB"}]))
r = compile_source(json.dumps(dict(base(380,86,140), boards=[keel, rib], connections=[{"type": "tab_slot", "board": "RIB-*", "into": "KEEL"}])), run_production=False)
for x in r['diagnostics']:
    if x['severity']=='warning': print('W', x['code'], x['message'][:220])
r = compile_source(json.dumps(dict(base(100,66,100), boards=[disk, blade], connections=[{"type":"tab_slot","board":"BL-*","into":"HUB"}])), run_production=False)
for x in r['diagnostics']:
    if x['severity']=='warning': print('W', x['code'], x['message'][:220])
