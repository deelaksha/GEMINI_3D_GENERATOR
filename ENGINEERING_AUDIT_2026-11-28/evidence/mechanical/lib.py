"""Scenario builders + runner for the mechanism audit (read-only on the project)."""
import json, math, os, sys, time, copy
sys.path.insert(0, '/home/sonic-claude2/deelaksha/desighn/GEMINI_3D_GENERATOR')
from board_engine import canvas
canvas.SNAPSHOT_DIR = None

OUT = os.path.dirname(os.path.abspath(__file__)) + '/json'
MAT = {'type': 'plywood', 'thickness': 6, 'kerf': 0.15}


def design(boards, motions, conns=(), name='audit', **extra):
    return dict({'format': 'board-design/v1', 'product': {'name': name}, 'material': MAT,
                 'boards': list(boards), 'connections': list(conns), 'motions': list(motions)}, **extra)


def gear_xz(bid, z, m, cx, cz, y=6, rot=0.0, t=6):
    """gear thin along y, centre (cx, cz) in the xz-plane, bottom face at y"""
    ra = m * z / 2 + m
    return {'id': bid, 'position': [cx - ra, y, cz - ra], 'size': [2 * ra, t, 2 * ra],
            'profile': {'shape': 'gear', 'center': [ra, ra], 'teeth': z, 'module': m, 'rotation': rot}}


def rot(mid, boards, pivot, axis='y', on='BASE', rng=(0, 360), driver=None, axle=6, **kw):
    mo = {'id': mid, 'type': 'rotate', 'boards': boards, 'on': on, 'axis': axis, 'pivot': list(pivot)}
    if axle:
        mo['axle'] = {'diameter': axle}
    if driver:
        mo['driven_by'] = driver
    else:
        mo['range'] = list(rng)
    mo.update(kw)
    return mo


def bar(bid, p, q, z, w=16.0, t=6.0):
    d = [q[0] - p[0], q[1] - p[1]]
    n = math.hypot(*d)
    d = [d[0] / n, d[1] / n]
    o = [-d[1] * w / 2, d[0] * w / 2]
    pts = [[p[0] - 10 * d[0] + s * o[0], p[1] - 10 * d[1] + s * o[1]] for s in (1, -1)]
    pts = [pts[0], [q[0] + 10 * d[0] + o[0], q[1] + 10 * d[1] + o[1]], [q[0] + 10 * d[0] - o[0], q[1] + 10 * d[1] - o[1]], pts[1]]
    lo = [math.floor(min(x[0] for x in pts)) - 1, math.floor(min(x[1] for x in pts)) - 1]
    hi = [math.ceil(max(x[0] for x in pts)) + 1, math.ceil(max(x[1] for x in pts)) + 1]
    return {'id': bid, 'position': [lo[0], lo[1], z], 'size': [hi[0] - lo[0], hi[1] - lo[1], t],
            'profile': {'shape': 'polygon', 'points': [[x[0] - lo[0], x[1] - lo[1]] for x in reversed(pts)]}}


def run(name, d, show_info=False, codes_only=False):
    path = f'{OUT}/{name}.json'
    with open(path, 'w') as f:
        json.dump(d, f, indent=1)
    t0 = time.time()
    r = canvas.compile_source(json.dumps(d), run_production=False)
    dt = time.time() - t0
    diags = r.get('diagnostics') or []
    print(f'=== {name}  ({dt:.2f}s)  {path}')
    for x in diags:
        if x['severity'] == 'info' and not show_info and not x['code'].startswith(('MOTION', 'LINKAGE', 'GEAR')):
            continue
        if codes_only:
            print(f"  [{x['severity']}] {x['code']}")
        else:
            print(f"  [{x['severity']}] {x['code']}: {x['message'][:400]}")
    ms = (r.get('design') or {}).get('motions') or []
    for m in ms:
        print(f"  motion {m['id']}: type={m['type']} range={m.get('range')} ratio={m.get('ratio')} driven_by={m.get('driven_by')}"
              f" parent={m.get('parent')} axle={m.get('axle')}")
    return r, dt
