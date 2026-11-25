"""
Geometric inspection: what a careful person would spot by eye on the assembled model, found by arithmetic on the
boards' real world extents (base outline x thickness, after placement), with every calculation written out.

  VISIBLE_GAP     two boards face each other across a thin slit (0.5 .. 10 mm) over a real overlap: they look meant to
                  touch. Up to 3 mm reads as a clearance (doors, drawers) and is only an info note.
  MISALIGNED      two touching boards whose edges are almost flush (off by 0.5 .. 5 mm, not by a board thickness):
                  a step a person would see at the corner or an overhang past the board below.
  UNEVEN_SPACING  three or more identical parallel boards in a row (shelves, slats) whose spacing is nearly but not
                  exactly even (one step off by 0.5 .. 5 mm; a larger difference is a deliberate layout).
  ASYMMETRIC      two identical boards placed as a mirror pair about the product's centre, but off by 0.5 .. 5 mm.

Boards tilted off the axes are skipped (their boxes do not show their faces). Each issue carries `calc`: the lines of
arithmetic that prove it, and a `suggestion` move where one board can simply be shifted.
"""
import statistics

from . import geometry as G

AX = 'xyz'
TOUCH = 0.5                # mm: closer than this is contact
SLIT = 10.0                # mm: largest gap that still reads as "meant to touch"
CLEARANCE = 3.0            # mm: gaps up to this are normal running clearances
STEP = 5.0                 # mm: largest edge offset that reads as a mistake rather than a deliberate inset
MIN_FACE = 10.0            # mm: two faces must overlap at least this much in both directions to be seen as facing
MAX_ISSUES = 40


def _f(v):
    return f'{v + 0.0:.1f}'          # + 0.0: never print "-0.0"


def _axis_aligned(plate):
    rot = plate.comp['placement'].get('rotation') or [0, 0, 0]
    return all(abs(r / 90.0 - round(r / 90.0)) < 1e-6 for r in rot)


def _body_box(plate):
    """World box of the board's body (its outline x thickness), without the tabs that reach into other boards."""
    x0, y0, x1, y1 = G.bbox(plate.outline)
    h = plate.t / 2.0
    pts = [plate.frame.to_world([x, y, z]) for x in (x0, x1) for y in (y0, y1) for z in (-h, h)]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def _overlap(a, b, i):
    return min(a[1][i], b[1][i]) - max(a[0][i], b[0][i])


def _gaps(a, b):
    return [max(0.0, b[0][i] - a[1][i], a[0][i] - b[1][i]) for i in range(3)]


def inspect(plates, joined_pairs=frozenset(), bodies=None, groups=None):
    """plates: {id: Plate}; joined_pairs: {frozenset({a, b})} held by a connection; bodies: {id: (min, max)} as the
    design placed each board (position .. position + size, before joinery cuts fingers and tabs into its outline);
    groups: [[ids]] of boards joined into one rigid unit. Between different units (a drawer in its carcass) gaps are
    running clearances and edges need not line up. -> {'issues': [...], 'boards': {...}}"""
    unit = {i: n for n, g in enumerate(groups or []) for i in g}
    seen_clear = set()
    ids = [i for i in plates if _axis_aligned(plates[i])]
    box = {i: (bodies or {}).get(i) or _body_box(plates[i]) for i in ids}
    t = {i: plates[i].t for i in ids}
    issues = []
    boards = {i: {'min': [round(v, 2) for v in box[i][0]], 'max': [round(v, 2) for v in box[i][1]],
                  'size': [round(box[i][1][k] - box[i][0][k], 2) for k in range(3)]} for i in ids}

    def add(code, severity, components, message, calc, location=None, suggestion=None):
        issues.append({'code': code, 'severity': severity, 'components': components, 'message': message, 'calc': calc,
                       'location': location, **({'suggestion': suggestion} if suggestion else {})})

    def mid(a, b):
        return [round((max(box[a][0][k], box[b][0][k]) + min(box[a][1][k], box[b][1][k])) / 2, 1) for k in range(3)]

    # 1. visible slits and 2. almost-flush edges, pair by pair
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            a, b = ids[x], ids[y]
            A, B = box[a], box[b]
            g = _gaps(A, B)
            open_axes = [k for k in range(3) if g[k] > 0]
            if len(open_axes) == 1 and TOUCH < g[open_axes[0]] <= SLIT and frozenset((a, b)) not in joined_pairs:
                k = open_axes[0]
                face = [_overlap(A, B, j) for j in range(3) if j != k]
                if min(face) >= MIN_FACE:
                    lo, hi = (a, b) if A[1][k] <= B[0][k] else (b, a)
                    gap = box[hi][0][k] - box[lo][1][k]
                    moving = unit.get(a, a) != unit.get(b, b)          # e.g. a drawer and the carcass around it
                    if moving and (min(unit.get(a, -1), unit.get(b, -1)), max(unit.get(a, -1), unit.get(b, -1)), k,
                                   round(gap, 1)) in seen_clear:
                        continue                # one note per unit, side and clearance
                    seen_clear.add((min(unit.get(a, -1), unit.get(b, -1)), max(unit.get(a, -1), unit.get(b, -1)), k,
                                    round(gap, 1)))
                    clear = gap <= CLEARANCE or moving
                    add('VISIBLE_GAP', 'info' if clear else 'warning', [hi, lo],
                        f"A {gap:.1f} mm gap is visible between '{lo}' and '{hi}' along {AX[k]}: they face each other over "
                        f"{face[0]:.0f} × {face[1]:.0f} mm but do not touch."
                        + (" They belong to separate units (a drawer, a lid, a module): fine as a running clearance."
                           if moving else " Fine as a running clearance (door, drawer, lid); otherwise close it." if clear else
                           f" Move '{hi}' by {-gap:g} mm along {AX[k]} so it sits on '{lo}', or connect them."),
                        [f"{lo}.{AX[k]}max = {_f(box[lo][1][k])} mm", f"{hi}.{AX[k]}min = {_f(box[hi][0][k])} mm",
                         f"gap = {_f(box[hi][0][k])} - {_f(box[lo][1][k])} = {gap:.2f} mm (contact is <= {TOUCH} mm)",
                         f"facing area = {face[0]:.1f} × {face[1]:.1f} mm"],
                        mid(a, b), None if clear else {'action': 'translate', 'component': hi,
                                                       'delta': [round(-gap, 3) if j == k else 0.0 for j in range(3)]})
            if max(g) > TOUCH or unit.get(a, a) != unit.get(b, b):
                continue                # edges only need to line up within one rigid unit
            # touching: compare the edges that lie side by side
            for k in range(3):
                if min(B[1][k] - B[0][k], A[1][k] - A[0][k]) <= max(t[a], t[b]) + 0.01:
                    continue            # across a board's thickness edges are never "flush" by intent
                for side, name in ((0, 'min'), (1, 'max')):      # one report per pair and axis
                    off = B[side][k] - A[side][k]
                    d = abs(off)
                    if not TOUCH < d <= STEP or any(abs(d - n * tt) <= 0.05 for tt in (t[a], t[b]) for n in (1, 2)):
                        continue
                    small = a if (A[1][k] - A[0][k]) < (B[1][k] - B[0][k]) else b
                    other = b if small == a else a
                    delta = round(box[other][side][k] - box[small][side][k], 3)
                    add('MISALIGNED', 'warning', [small, other],
                        f"The {name} {AX[k]} edges of '{small}' and '{other}' are {d:.1f} mm apart: almost flush, so it shows "
                        f"as a step or overhang. Move '{small}' by {delta:g} mm along {AX[k]} to line them up (or make the "
                        f"offset deliberate: >= {STEP:g} mm or one board thickness).",
                        [f"{a}.{AX[k]}{name} = {_f(A[side][k])} mm", f"{b}.{AX[k]}{name} = {_f(B[side][k])} mm",
                         f"offset = |{_f(B[side][k])} - {_f(A[side][k])}| = {d:.2f} mm (flush <= {TOUCH} mm, "
                         f"deliberate >= {STEP:g} mm or {t[a]:g} mm thickness)"],
                        mid(a, b), {'action': 'translate', 'component': small,
                                    'delta': [delta if j == k else 0.0 for j in range(3)]})
                    break

    # 3. rows of identical parallel boards with nearly even spacing
    def thin(i):
        s = boards[i]['size']
        return min(range(3), key=lambda k: s[k])
    rows = {}
    for i in ids:
        k = thin(i)
        key = (k, tuple(round(boards[i]['size'][j]) for j in range(3)),
               tuple(round(box[i][0][j]) for j in range(3) if j != k))
        rows.setdefault(key, []).append(i)
    for (k, _s, _p), row in rows.items():
        if len(row) < 3:
            continue
        row.sort(key=lambda i: box[i][0][k])
        pos = [box[i][0][k] for i in row]
        steps = [pos[n + 1] - pos[n] for n in range(len(pos) - 1)]
        med = statistics.median(steps)
        bad = [(n, s) for n, s in enumerate(steps) if TOUCH < abs(s - med) <= min(STEP, 0.1 * med)]   # more is deliberate
        if med > 0 and bad:
            # one misplaced board: the last step alone is off, or two neighbouring steps are off in opposite directions
            n0, s0 = bad[0]
            culprit = (n0 + 1 if len(bad) == 1 and n0 == len(steps) - 1 else
                       n0 + 1 if len(bad) == 2 and bad[1][0] == n0 + 1 and (s0 - med) * (bad[1][1] - med) < 0 else None)
            first = row[culprit if culprit is not None else n0 + 1]
            add('UNEVEN_SPACING', 'warning', [first] + [i for i in row if i != first],
                f"{len(row)} identical boards ({', '.join(row[:6])}{'...' if len(row) > 6 else ''}) are spaced almost "
                f"evenly along {AX[k]} ({med:g} mm), but " + ', '.join(f"'{row[n]}' -> '{row[n + 1]}' is {s:g} mm"
                                                                         for n, s in bad[:4])
                + ". Use one spacing (\"repeat\" with a step does this exactly).",
                [f"{AX[k]} positions = " + ', '.join(f'{row[n]}: {_f(p)}' for n, p in enumerate(pos)),
                 "spacings = " + ', '.join(_f(s) for s in steps), f"median spacing = {med:.2f} mm",
                 *(f"{row[n]} -> {row[n + 1]}: {s:.2f} - {med:.2f} = {s - med:+.2f} mm" for n, s in bad[:4])],
                [round(v, 1) for v in box[first][0]],
                {'action': 'translate', 'component': first, 'delta': [round(med - s0, 3) if j == k else 0.0 for j in range(3)]}
                if culprit is not None else None)

    # 4. mirror pairs that are not quite symmetric about the product centre
    if ids:
        lo = [min(box[i][0][k] for i in ids) for k in range(3)]
        hi = [max(box[i][1][k] for i in ids) for k in range(3)]
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                a, b = ids[x], ids[y]
                if boards[a]['size'] != boards[b]['size']:
                    continue
                for k in range(3):
                    if any(abs(box[a][0][j] - box[b][0][j]) > TOUCH for j in range(3) if j != k):
                        continue
                    left, right = (a, b) if box[a][0][k] < box[b][0][k] else (b, a)
                    ml, mr = box[left][0][k] - lo[k], hi[k] - box[right][1][k]
                    d = abs(ml - mr)
                    if box[right][0][k] - box[left][1][k] > 0 and TOUCH < d <= STEP and len(
                            [i for i in ids if boards[i]['size'] == boards[a]['size']]) == 2:
                        add('ASYMMETRIC', 'warning', [right, left],
                            f"'{left}' and '{right}' look like a mirror pair along {AX[k]}, but sit {d:.1f} mm off "
                            f"centre: {ml:.1f} mm from one end of the product, {mr:.1f} mm from the other.",
                            [f"product {AX[k]} = {_f(lo[k])} .. {_f(hi[k])} mm",
                             f"{left}: {_f(box[left][0][k])} - {_f(lo[k])} = {ml:.2f} mm from the {AX[k]}min end",
                             f"{right}: {_f(hi[k])} - {_f(box[right][1][k])} = {mr:.2f} mm from the {AX[k]}max end",
                             f"difference = |{ml:.2f} - {mr:.2f}| = {d:.2f} mm"],
                            [round(v, 1) for v in box[right][0]],
                            {'action': 'translate', 'component': right,
                             'delta': [round(mr - ml, 3) if j == k else 0.0 for j in range(3)]})
    issues.sort(key=lambda i: ({'error': 0, 'warning': 1, 'info': 2}[i['severity']], i['code']))
    return {'issues': issues[:MAX_ISSUES], 'boards': boards, 'skipped_tilted': [i for i in plates if i not in box]}
