import sys, os, json
sys.path.insert(0, os.getcwd())
from board_engine import canvas_prompt as cp
S = sys.argv[1]
for n in ('EXAMPLE','COMPLEX_EXAMPLE','STRUCTURES_EXAMPLE'):
    json.dump(getattr(cp, n), open(f'{S}/ex_{n}.json','w'), indent=1)
