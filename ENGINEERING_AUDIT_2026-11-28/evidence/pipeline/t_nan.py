import json, sys, traceback
sys.path.insert(0,'.')
import board_engine.canvas as C
from board_engine.canvas import pretty_json
D=json.load(open(sys.argv[1]))
s=pretty_json(D).replace('"size": [1200, 18, 600]','"size": [NaN, 18, 600]')
data, src, off, d = C.parse_source(s)
res={'ok':False,'format':None,'diagnostics':[],'design':None,'source_map':{}}
try: C._compile_v1(data, src, off, 'x', res, False)
except Exception: traceback.print_exc()
