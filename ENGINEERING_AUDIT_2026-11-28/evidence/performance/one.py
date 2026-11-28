"""Compile one generated design; print JSON with stage timings, total, peak RSS. argv: family n production"""
import json, sys, time, resource, copy
sys.path.insert(0, '.')
from board_engine import canvas as C
from board_engine.progress import reporting
from board_engine.canvas_prompt import COMPLEX_EXAMPLE

def slats(n):
    cols = min(n, 100); rows = max(1, -(-n // cols))
    return {'format': 'board-design/v1', 'product': {'name': 'grid'}, 'material': {'type': 'plywood', 'thickness': 6},
            'boards': [{'id': 'BASE', 'position': [0, 0, 0], 'size': [20 + 21 * cols, 6, 40 + 80 * rows]},
                       {'id': 'S', 'position': [10, 6, 30], 'size': [6, 40, 50],
                        'repeat': {'count': cols, 'step': [21, 0, 0], **({'rows': {'count': rows, 'step': [0, 0, 80]}} if rows > 1 else {})}}],
            'connections': [{'id': 'a', 'type': 'tab_slot', 'board': 'S*', 'into': 'BASE', 'tabs': 1}]}

def cottages(n):
    # n = approx boards; cottage = 7 boards incl. 2 tilted roof panels; instances in a grid, unconnected to each other
    k = max(1, n // 7); cols = min(k, 20); rows = -(-k // cols)
    ex = copy.deepcopy(COMPLEX_EXAMPLE)
    asm = {'id': 'COT', 'boards': ex['boards'], 'connections': ex['connections']}
    inst = [{'assembly': 'COT', 'id': f'C{r}x{c}', 'offset': [c * 260, 0, r * 220]} for r in range(rows) for c in range(cols)][:k]
    return {'format': 'board-design/v1', 'product': {'name': 'village'}, 'material': ex['material'],
            'boards': [], 'connections': [], 'assemblies': [asm], 'instances': inst}

fam, n, prod = sys.argv[1], int(sys.argv[2]), sys.argv[3] == '1'
d = {'slats': slats, 'cottages': cottages}[fam](n)
src = json.dumps(d)
stages, t0 = {}, time.perf_counter()
last = ['start', t0]
def rep(stage, done, total, info):
    now = time.perf_counter()
    if stage != last[0]:
        stages[last[0]] = stages.get(last[0], 0) + now - last[1]; last[0], last[1] = stage, now
with reporting(rep):
    r = C.compile_source(src, run_production=prod, time_budget=None)
t = time.perf_counter() - t0
stages[last[0]] = stages.get(last[0], 0) + time.perf_counter() - last[1]
errs = {}
for x in r['diagnostics']:
    if x['severity'] == 'error': errs[x['code']] = errs.get(x['code'], 0) + 1
print(json.dumps({'family': fam, 'n_req': n, 'production': prod, 'src_chars': len(src),
                  'boards': (r.get('summary') or {}).get('boards'), 'joints': (r.get('summary') or {}).get('joints'),
                  'ok': r['ok'], 'total_s': round(t, 2), 'stages_s': {k: round(v, 2) for k, v in stages.items()},
                  'peak_rss_mb': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1), 'errors': errs}))
