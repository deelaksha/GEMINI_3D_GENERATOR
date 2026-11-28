import json, sys, os, collections
sys.path.insert(0, os.getcwd())
from board_engine.canvas import compile_source
def run(name, d):
    r = compile_source(json.dumps(d), run_production=False)
    ds = r['diagnostics']
    print(name, 'errors', [ (x['code'], x['message'][:140]) for x in ds if x['severity']=='error'][:6])
    print('   warnings', collections.Counter(x['code'] for x in ds if x['severity']=='warning'))
    print('   boards built:', len((r.get('model3d') or {}).get('parts', []) or []) if isinstance(r.get('model3d'),dict) else r.get('summary'))
base = {"format":"board-design/v1","product":{"name":"t","description":"","overall":{"length":400,"height":200,"depth":300}},
        "material":{"type":"plywood","thickness":6}}
# 1. classic slotted aeroplane: profiled fuselage (normal z) x profiled wing (normal y), cross_lap
fus = {"id":"FUS","position":[0,0,147],"size":[400,100,6],"profile":{"shape":"spline","points":[[0,50],[60,80],[300,70],[400,95],[390,40],[200,20],[40,25]]}}
wing = {"id":"WING","position":[120,50,0],"size":[100,6,300],"profile":{"shape":"superellipse","center":[50,150],"width":100,"height":300,"exponent":4}}
run('1 profiled cross_lap aeroplane', dict(base, boards=[fus, wing], connections=[{"type":"cross_lap","board":"FUS","into":"WING"}]))
run('1b same, connections auto', dict(base, boards=[fus, wing], connections="auto"))
# 2. prompt's morph RIB example + KEEL, wildcard connection
rib = {"id": "RIB", "position": [0, 6, 0], "size": [6, 40, 60],
    "profile": {"shape": "polygon", "points": [[0, 15], [0, 45], [40, 60], [40, 0]]},
    "repeat": {"count": 9, "step": [40, 0, 0], "morph": [
      {"size": [6, 80, 140], "profile": {"shape": "polygon", "points": [[0, 35], [0, 105], [80, 140], [80, 0]]}, "shift": [0, 0, -40]},
      {"size": [6, 30, 40], "profile": {"shape": "polygon", "points": [[0, 10], [0, 30], [30, 40], [30, 0]]}, "shift": [0, 0, 10]}]}}
keel = {"id":"KEEL","position":[0,0,-20],"size":[340,6,120]}
run('2 prompt morph example + keel', dict(base, boards=[keel, rib], connections=[{"type": "tab_slot", "board": "RIB-*", "into": "KEEL"}]))
# 3. radial
disk = {"id":"HUB","position":[100,0,100],"size":[100,6,100]}
blade = {"id":"BL","position":[147,6,150],"size":[6,60,40],"radial":{"count":6,"axis":"y","center":[150,6,150]}}
run('3 radial blades', dict(base, boards=[disk, blade], connections=[{"type":"tab_slot","board":"BL-*","into":"HUB"}]))
