"""
Connectivity analysis: is the product one joined structure?

Two graphs over the boards:
  * contact graph - boards whose real 3D extents touch or overlap (within `TOUCH` mm);
  * joint graph   - boards held together by a joined connection.
The main assembly is the joined group standing on the floor (most anchored boards), then the largest one. Then:
  ISOLATED_BOARD   (error)   a board that touches nothing: it floats in the air. Reported with the nearest board, the
                             gap and a move that closes it.
  NOT_JOINED       (error)   a group of boards that is not joined to the main assembly although it touches it: a
                             connection is missing. (Warning when the group rests on the assembly as a removable unit -
                             a drawer, a stacked module - or is one flat board lying on top, like a lift-off lid, which a
                             design may do on purpose; a single loose upright board falls over.)
  DISCONNECTED     (error)   a group that neither touches nor is joined to the main assembly: it hangs in the air
                             apart from it. Reported with the nearest board and the gap.
"""
import math

from . import geometry as G

TOUCH = 0.5          # mm: boxes closer than this touch


def _gap(a, b):
    """Per-axis gap (>= 0) between two world boxes ((lo, hi), (lo, hi)) and its length."""
    (alo, ahi), (blo, bhi) = a, b
    g = [max(0.0, blo[i] - ahi[i], alo[i] - bhi[i]) for i in range(3)]
    return g, math.sqrt(sum(v * v for v in g))


def _move(a, b):
    """Translation of box a that closes its gap to box b (along every axis with a gap)."""
    (alo, ahi), (blo, bhi) = a, b
    return [round(blo[i] - ahi[i], 3) if blo[i] > ahi[i] else round(bhi[i] - alo[i], 3) if alo[i] > bhi[i] else 0.0
            for i in range(3)]


def _calc(a, b, A, B):
    g, d = _gap(A, B)
    return [f"{a}: x {A[0][0]:.1f}..{A[1][0]:.1f}, y {A[0][1]:.1f}..{A[1][1]:.1f}, z {A[0][2]:.1f}..{A[1][2]:.1f} mm",
            f"{b}: x {B[0][0]:.1f}..{B[1][0]:.1f}, y {B[0][1]:.1f}..{B[1][1]:.1f}, z {B[0][2]:.1f}..{B[1][2]:.1f} mm",
            f"gap per axis = [{g[0]:.1f}, {g[1]:.1f}, {g[2]:.1f}] mm",
            f"distance = sqrt({g[0]:.1f}² + {g[1]:.1f}² + {g[2]:.1f}²) = {d:.2f} mm (touching is <= {TOUCH} mm)"]


def _mid(a, b):
    (alo, ahi), (blo, bhi) = a, b
    return [round((max(alo[i], blo[i]) + min(ahi[i], bhi[i])) / 2, 1) for i in range(3)]


def analyze(design, plates, support=None):
    """-> {'issues': [...], 'groups': [[ids]], 'main': [ids], 'isolated': [ids], 'not_joined': [[ids]]}"""
    ids = list(plates)
    if len(ids) < 2:
        return {'issues': [], 'groups': [ids], 'main': ids, 'isolated': [], 'not_joined': []}
    box = {i: plates[i].world_aabb() for i in ids}
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for j in design['joints']:
        if j.get('status') == 'joined' and j['a'] in parent and j['b'] in parent:
            parent[find(j['a'])] = find(j['b'])
    for m in design.get('motions') or []:          # a moving part is attached through its motion's mount
        for b in m['boards']:
            if b in parent and m['on'] in parent:
                parent[find(b)] = find(m['on'])
    groups = {}
    for i in ids:
        groups.setdefault(find(i), []).append(i)
    groups = sorted(groups.values(), key=lambda g: (-len(g), g[0]))
    touches = {i: set() for i in ids}
    for x, y in G.near_pairs([box[i] for i in ids], TOUCH):
        a, b = ids[x], ids[y]
        if _gap(box[a], box[b])[1] <= TOUCH:
            touches[a].add(b)
            touches[b].add(a)
    status = (support or {}).get('components', {})
    anchored = lambda g: sum(1 for i in g if status.get(i, {}).get('status') == 'anchored')
    volume = lambda g: sum((box[i][1][0] - box[i][0][0]) * (box[i][1][1] - box[i][0][1]) * (box[i][1][2] - box[i][0][2])
                           for i in g)
    main = max(groups, key=lambda g: (anchored(g), len(g), volume(g)))
    main_set = set(main)

    def nearest(group, others):
        best = None
        for a in group:
            for b in others:
                d = _gap(box[a], box[b])[1]
                if best is None or d < best[0]:
                    best = (d, a, b)
        return best
    issues, isolated, not_joined = [], [], []
    for g in groups:
        if g is main:
            continue
        gs = set(g)
        if len(g) == 1 and not touches[g[0]]:
            a = g[0]
            d, _a, b = nearest([a], [x for x in ids if x != a])
            isolated.append(a)
            issues.append({'code': 'ISOLATED_BOARD', 'severity': 'error', 'components': [a, b],
                           'message': f"'{a}' touches no other board: it floats {d:.1f} mm from '{b}', its nearest board. Move "
                                      f"it against the board it belongs to and add a connection.",
                           'location': _mid(box[a], box[b]), 'calc': _calc(a, b, box[a], box[b]),
                           'suggestion': {'action': 'translate', 'component': a, 'delta': _move(box[a], box[b])}})
            continue
        contact = sorted({(a, b) for a in g for b in touches[a] if b in main_set})
        names = ', '.join(f"'{x}'" for x in sorted(g)[:8]) + (f' and {len(g) - 8} more' if len(g) > 8 else '')
        what = f"Board {names} is" if len(g) == 1 else f"Boards {names} are"
        if contact:
            not_joined.append(sorted(g))
            # a removable unit (a drawer or stacked module: boards joined to each other) or a flat board lying on top
            resting = all(status.get(i, {}).get('status') == 'resting' for i in g) and (
                len(g) > 1 or box[g[0]][1][1] - box[g[0]][0][1] <= plates[g[0]].t + 0.01)
            pairs = ', '.join(f"'{a}' / '{b}'" for a, b in contact[:4])
            issues.append({'code': 'NOT_JOINED', 'severity': 'warning' if resting else 'error', 'components': sorted(gs),
                           'message': f"{what} not joined to the main assembly although {'it touches' if len(g) == 1 else 'they touch'} "
                                      f"it ({pairs}): add a connection there"
                                      + (" (it only rests on the assembly; fine for a lift-off lid, a drawer or a stacked "
                                         "module)." if resting else "."),
                           'location': _mid(box[contact[0][0]], box[contact[0][1]])})
        else:
            d, a, b = nearest(g, main)
            issues.append({'code': 'DISCONNECTED', 'severity': 'error', 'components': sorted(gs),
                           'message': f"{what} not joined to the main assembly and {'does' if len(g) == 1 else 'do'} not touch it: "
                                      f"'{a}' is {d:.1f} mm from '{b}'. Move {'it' if len(g) == 1 else 'them'} into contact and add "
                                      f"a connection.",
                           'location': _mid(box[a], box[b]), 'calc': _calc(a, b, box[a], box[b]),
                           **({'suggestion': {'action': 'translate', 'component': a, 'delta': _move(box[a], box[b])}}
                              if len(g) == 1 else {})})
    return {'issues': issues, 'groups': groups, 'main': main, 'isolated': isolated, 'not_joined': not_joined}
