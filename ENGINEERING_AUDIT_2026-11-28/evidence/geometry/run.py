import sys, json, os
sys.path.insert(0, os.getcwd())
from board_engine.canvas import compile_source
def run(path, prod=False, show_joints=False):
    txt = open(path).read()
    r = compile_source(txt, run_production=prod)
    print(f"== {os.path.basename(path)} ok={r.get('ok')}")
    for d in r.get('diagnostics', []):
        print(f"  [{d.get('severity')}] {d.get('code')}: {str(d.get('message'))[:260]}")
    des = r.get('design') or {}
    if show_joints:
        for j in des.get('joints', []):
            print("  J", j.get('id'), j.get('type'), j.get('a'), '->', j.get('b'), j.get('status'), j.get('detached_reason',''))
        for c in des.get('components', []):
            print("  C", c['id'], c['placement'], 'feat=', [(f['id'], f.get('kind'), f.get('center'), f.get('width'), f.get('height')) for f in c.get('features', [])][:6], 'tabs=', len(c.get('tabs', [])))
    return r
if __name__ == '__main__':
    prod = '--prod' in sys.argv; sj = '-j' in sys.argv
    for p in [a for a in sys.argv[1:] if not a.startswith('-')]:
        run(p, prod, sj)
