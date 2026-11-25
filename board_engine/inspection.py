"""
Geometric inspection: what a careful person would spot by eye on the assembled model, found by arithmetic on the
boards' real world extents (position .. position + size as laid out), with every calculation written out.

A "rigid unit" is a set of boards joined to each other by fixed connections (hinges excluded): a carcass, a drawer
box, a door, a loose lid. Inside one unit everything must fit exactly; between units (a drawer in its carcass, a door
in front of it) gaps are running clearances and edges need not line up.

  VISIBLE_GAP       two boards face each other across a thin slit (0.5 .. 10 mm) over a real overlap but do not touch:
                    a warning inside one rigid unit, an info note (running clearance) between units.
  UNJOINED_CONTACT  two boards of one rigid unit touch face to edge with no connection between them: a warning where
                    one rests on the other (vertical contact: nothing stops it lifting off), an info note side by side.
  MISALIGNED        two touching boards of one unit whose edges are almost flush (off by 0.5 .. 5 mm, not by a board
                    thickness): a step a person would see at the corner or an overhang past the board below.
  OFF_CENTRE        a board overhangs the boards it sits on at both ends by nearly, but not exactly, the same amount.
  MISMATCHED_PAIR   boards that are clearly twins (two legs, two sides, a row of shelves) but differ by 0.5 .. 5 mm in a
                    size or in their alignment; in a group of three or more the odd one out is named.
  UNEVEN_SPACING    three or more identical parallel boards in a row whose spacing is nearly but not exactly even.
  ASYMMETRIC        two identical boards placed as a mirror pair about the product's centre, but off by 0.5 .. 5 mm.
  HELD_FROM_ABOVE   a board whose every joint is a tab pushing UP into a board above it: glue-free, only friction holds
                    it and gravity pulls it out of its slots (rafter ends under a soffit, a shelf hung under a top).

Boards tilted off the axes are skipped (their boxes do not show their faces). Each issue carries `calc`: the lines of
arithmetic that prove it, and a `suggestion` move where one board can simply be shifted.
"""
import statistics
from collections import Counter

from . import geometry as G

AX = 'xyz'
TOUCH = 0.5                # mm: closer than this is contact
SLIT = 10.0                # mm: largest gap that still reads as "meant to touch"
STEP = 5.0                 # mm: largest edge offset that reads as a mistake rather than a deliberate inset
MIN_FACE = 10.0            # mm: two faces must overlap at least this much in both directions to be seen as facing
MAX_ISSUES = 60


def _f(v):
    return f'{v + 0.0:.1f}'          # + 0.0: never print "-0.0"


def _axis_aligned(plate):
    rot = plate.comp['placement'].get('rotation') or [0, 0, 0]
    return all(abs(r / 90.0 - round(r / 90.0)) < 1e-6 for r in rot)


def _body_box(plate):
    """World box of the board's body (its outline x thickness)."""
    x0, y0, x1, y1 = G.bbox(plate.outline)
    h = plate.t / 2.0
    pts = [plate.frame.to_world([x, y, z]) for x in (x0, x1) for y in (y0, y1) for z in (-h, h)]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def _overlap(a, b, i):
    return min(a[1][i], b[1][i]) - max(a[0][i], b[0][i])


def _gaps(a, b):
    return [max(0.0, b[0][i] - a[1][i], a[0][i] - b[1][i]) for i in range(3)]


def inspect(plates, joints=(), bodies=None):
    """plates: {id: Plate}; joints: the design's joints ({'a', 'b', 'type', 'status'}); bodies: {id: (min, max)} as the
    design placed each board (before joinery cuts fingers and tabs into its outline) -> {'issues', 'boards', ...}"""
    ids = [i for i in plates if _axis_aligned(plates[i])]
    box = {i: (bodies or {}).get(i) or _body_box(plates[i]) for i in ids}
    t = {i: plates[i].t for i in ids}
    size = {i: [box[i][1][k] - box[i][0][k] for k in range(3)] for i in ids}
    thin = {i: min(range(3), key=lambda k: size[i][k]) for i in ids}
    connected = {frozenset((j['a'], j['b'])) for j in joints}
    parent = {i: i for i in plates}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for j in joints:
        if j.get('status') == 'joined' and j.get('type') != 'hinge' and j['a'] in parent and j['b'] in parent:
            parent[find(j['a'])] = find(j['b'])
    rigid = lambda a, b: find(a) == find(b)
    deliberate = lambda d, a, b: any(abs(d - n * tt) <= 0.05 for tt in (t[a], t[b]) for n in (1, 2))
    issues, seen_clear = [], set()
    boards = {i: {'min': [round(v, 2) for v in box[i][0]], 'max': [round(v, 2) for v in box[i][1]],
                  'size': [round(v, 2) for v in size[i]]} for i in ids}

    def add(code, severity, components, message, calc, location=None, suggestion=None):
        issues.append({'code': code, 'severity': severity, 'components': components, 'message': message, 'calc': calc,
                       'location': location, **({'suggestion': suggestion} if suggestion else {})})

    def mid(a, b):
        return [round((max(box[a][0][k], box[b][0][k]) + min(box[a][1][k], box[b][1][k])) / 2, 1) for k in range(3)]

    def move(c, k, d):
        return {'action': 'translate', 'component': c, 'delta': [round(d, 3) if j == k else 0.0 for j in range(3)]}

    def _spacer(a, b, k):
        """A third board standing between the two faces and touching both (a riser, a block, a leg): the gap is
        held open on purpose and is not a misplacement."""
        A, B = box[a], box[b]
        lo_f, hi_f = (A[1][k], B[0][k]) if A[1][k] <= B[0][k] else (B[1][k], A[0][k])
        plane = [j for j in range(3) if j != k]
        for c in ids:
            if c in (a, b):
                continue
            C = box[c]
            # it must stand inside the area where the two faces overlap, not merely touch its rim (the ground under
            # two upright boards touches both of them but holds nothing apart)
            if C[0][k] <= lo_f + TOUCH and C[1][k] >= hi_f - TOUCH and all(
                    min(C[1][j], A[1][j], B[1][j]) - max(C[0][j], A[0][j], B[0][j]) > TOUCH for j in plane):
                return True
        return False

    touching = {i: [] for i in ids}
    # 1. pair by pair: slits, unjoined contact, almost-flush edges
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            a, b = ids[x], ids[y]
            A, B = box[a], box[b]
            g = _gaps(A, B)
            open_axes = [k for k in range(3) if g[k] > 0]
            same = rigid(a, b)
            if len(open_axes) == 1 and TOUCH < g[open_axes[0]] <= SLIT and frozenset((a, b)) not in connected:
                k = open_axes[0]
                face = [_overlap(A, B, j) for j in range(3) if j != k]
                key = (min(find(a), find(b)), max(find(a), find(b)), k, round(g[k], 1))
                if min(face) >= MIN_FACE and (same or key not in seen_clear) and not _spacer(a, b, k):
                    seen_clear.add(key)                 # between units: one note per unit pair, side and clearance
                    lo, hi = (a, b) if A[1][k] <= B[0][k] else (b, a)
                    gap = box[hi][0][k] - box[lo][1][k]
                    add('VISIBLE_GAP', 'warning' if same else 'info', [hi, lo],
                        f"A {gap:.1f} mm gap is visible between '{lo}' and '{hi}' along {AX[k]}: they face each other over "
                        f"{face[0]:.0f} × {face[1]:.0f} mm but do not touch."
                        + (f" Both belong to one rigid structure, so this is a misplacement: move '{hi}' by {-gap:g} mm "
                           f"along {AX[k]} so it sits on '{lo}', or connect them." if same else
                           " They are separate units (a drawer, a door, a lid, a module): fine as a running clearance."),
                        [f"{lo}.{AX[k]}max = {_f(box[lo][1][k])} mm", f"{hi}.{AX[k]}min = {_f(box[hi][0][k])} mm",
                         f"gap = {_f(box[hi][0][k])} - {_f(box[lo][1][k])} = {gap:.2f} mm (contact is <= {TOUCH} mm)",
                         f"facing area = {face[0]:.1f} × {face[1]:.1f} mm",
                         f"same rigid structure: {'yes' if same else 'no'}"],
                        mid(a, b), move(hi, k, -gap) if same else None)
            if max(g) > TOUCH:
                continue
            ov = [_overlap(A, B, k) for k in range(3)]
            # touching over a real area: at least MIN_FACE one way and a board's edge (its thickness) the other way
            edge = min(MIN_FACE, 0.9 * min(t[a], t[b]))
            contact = [k for k in range(3) if abs(ov[k]) <= TOUCH and min(ov[j] for j in range(3) if j != k) >= edge
                       and max(ov[j] for j in range(3) if j != k) >= MIN_FACE]
            if contact:
                touching[a].append(b)
                touching[b].append(a)
            if not same:
                continue                # edges only need to line up within one rigid unit
            if contact and frozenset((a, b)) not in connected:
                k = contact[0]
                lo, hi = (a, b) if A[1][k] <= B[0][k] + TOUCH else (b, a)
                c1, c2 = [ov[j] for j in range(3) if j != k]
                # the board that meets the other with an edge: is it its END (a shelf end, a rail end) or a long side?
                eb = [i for i in (a, b) if thin[i] != k]
                e = min(eb, key=lambda i: size[i][k]) if eb else None
                along = [j for j in range(3) if j != k and e is not None and j != thin[e]]
                end = bool(along) and size[e][along[0]] <= size[e][k] + 0.01
                other = (a if e == b else b) if e is not None else None
                # a thinner panel (a back, a divider) meeting thicker carcass boards is held in its own joints elsewhere
                captured = e is not None and t[e] < t[other] - 0.01
                bearing = (k == 1 or end) and not captured
                add('UNJOINED_CONTACT', 'warning' if bearing else 'info', [hi, lo],
                    (f"'{e}' ({t[e]:g} mm) meets the thicker '{other}' ({t[other]:g} mm) over {c1:.0f} × {c2:.0f} mm "
                     f"without a connection; as a captured panel it is held by its other joints." if captured else
                     f"'{hi}' rests on '{lo}' over {c1:.0f} × {c2:.0f} mm with no connection between them: nothing holds "
                     f"it down there (glue-free), so it can lift or slide. Add a connection (e.g. tab_slot '{lo}' into "
                     f"'{hi}' or the reverse)." if k == 1 else
                     f"The end of '{e}' butts against '{a if e == b else b}' over {c1:.0f} × {c2:.0f} mm with no connection: "
                     f"that end is unsupported and will sag or come loose. Add a connection (tab_slot '{e}' into "
                     f"'{a if e == b else b}')." if end else
                     f"'{a}' and '{b}' touch side by side over {c1:.0f} × {c2:.0f} mm with no connection between them; "
                     f"they are held only through other boards. Add a connection if they should be fixed together."),
                    [f"{lo}.{AX[k]}max = {_f(box[lo][1][k])} mm", f"{hi}.{AX[k]}min = {_f(box[hi][0][k])} mm",
                     f"|{_f(box[hi][0][k])} - {_f(box[lo][1][k])}| = {abs(box[hi][0][k] - box[lo][1][k]):.2f} mm <= {TOUCH} "
                     f"mm: touching", f"contact = {c1:.1f} × {c2:.1f} mm", f"connections between them: none",
                     f"contact direction: {AX[k]} ({'vertical: load bearing' if k == 1 else 'horizontal'})",
                     *([f"{e}: edge along {AX[along[0]]} = {size[e][along[0]]:.1f} mm <= its length along {AX[k]} = "
                        f"{size[e][k]:.1f} mm: it is the board's end"] if end and k != 1 else [])],
                    mid(a, b))
            for k in range(3):
                if min(size[a][k], size[b][k]) <= max(t[a], t[b]) + 0.01:
                    continue            # across a board's thickness edges are never "flush" by intent
                for side, name in ((0, 'min'), (1, 'max')):      # one report per pair and axis
                    d = abs(B[side][k] - A[side][k])
                    if not TOUCH < d <= STEP or deliberate(d, a, b):
                        continue
                    small = a if size[a][k] < size[b][k] else b
                    other = b if small == a else a
                    delta = box[other][side][k] - box[small][side][k]
                    add('MISALIGNED', 'warning', [small, other],
                        f"The {name} {AX[k]} edges of '{small}' and '{other}' are {d:.1f} mm apart: almost flush, so it shows "
                        f"as a step or overhang. Move '{small}' by {round(delta, 3):g} mm along {AX[k]} to line them up (or "
                        f"make the offset deliberate: >= {STEP:g} mm or one board thickness).",
                        [f"{a}.{AX[k]}{name} = {_f(A[side][k])} mm", f"{b}.{AX[k]}{name} = {_f(B[side][k])} mm",
                         f"offset = |{_f(B[side][k])} - {_f(A[side][k])}| = {d:.2f} mm (flush <= {TOUCH} mm, "
                         f"deliberate >= {STEP:g} mm or {t[a]:g} mm thickness)"],
                        mid(a, b), move(small, k, delta))
                    break

    # 2. overhangs that are nearly, but not exactly, equal at both ends
    for b in ids:
        under = [p for p in touching[b] if rigid(b, p)]
        if not under:
            continue
        for k in range(3):
            if k == thin[b]:
                continue
            pmin, pmax = min(box[p][0][k] for p in under), max(box[p][1][k] for p in under)
            o1, o2 = pmin - box[b][0][k], box[b][1][k] - pmax
            d = abs(o1 - o2)
            if o1 > TOUCH and o2 > TOUCH and TOUCH < d <= min(20.0, 0.35 * max(o1, o2)) and not deliberate(d, b, b):
                lo_p = min(under, key=lambda p: box[p][0][k])
                hi_p = max(under, key=lambda p: box[p][1][k])
                add('OFF_CENTRE', 'warning', [b] + under,
                    f"'{b}' overhangs the boards it sits on by {o1:.1f} mm at the {AX[k]}min end and {o2:.1f} mm at the "
                    f"{AX[k]}max end: nearly equal, so it looks off centre. Move '{b}' by {(o1 - o2) / 2:g} mm along {AX[k]} "
                    f"to centre it (or make the difference deliberate).",
                    [f"{b}: {AX[k]} {_f(box[b][0][k])} .. {_f(box[b][1][k])} mm",
                     f"boards it sits on ({', '.join(under[:6])}): {AX[k]} {_f(pmin)} ({lo_p}) .. {_f(pmax)} ({hi_p}) mm",
                     f"overhang {AX[k]}min = {_f(pmin)} - {_f(box[b][0][k])} = {o1:.2f} mm",
                     f"overhang {AX[k]}max = {_f(box[b][1][k])} - {_f(pmax)} = {o2:.2f} mm",
                     f"difference = |{o1:.2f} - {o2:.2f}| = {d:.2f} mm; centre by moving ({_f(o1)} - {_f(o2)}) / 2 = "
                     f"{(o1 - o2) / 2:+.2f} mm"],
                    [round(v, 1) for v in box[b][0]], move(b, k, (o1 - o2) / 2))

    # 3. twins that differ a little: two legs, two sides, a row of shelves
    tw = {i: i for i in ids}

    def tfind(x):
        while tw[x] != x:
            tw[x] = tw[tw[x]]
            x = tw[x]
        return x
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            a, b = ids[x], ids[y]
            g = _gaps(box[a], box[b])
            if thin[a] != thin[b] or max(g) <= TOUCH:
                continue
            s = max(range(3), key=lambda k: g[k])
            diffs = [size[a][k] - size[b][k] for k in range(3)] + [box[a][0][k] - box[b][0][k] for k in range(3) if k != s]
            if all(abs(v) <= STEP for v in diffs):
                tw[tfind(a)] = tfind(b)
    clusters = {}
    for i in ids:
        clusters.setdefault(tfind(i), []).append(i)
    for group in clusters.values():
        if len(group) < 2:
            continue
        spread = [max(box[i][0][k] for i in group) - min(box[i][0][k] for i in group) for k in range(3)]
        s = max(range(3), key=lambda k: spread[k])
        # positions are compared only along alignment axes: in a row (rafters, slats) the position along the row
        # varies by design, so any axis where the group spreads widely is a layout axis, not an alignment
        attrs = [('size', k) for k in range(3)] + [('position', k) for k in range(3)
                                                   if k != s and (len(group) == 2 or spread[k] <= 2 * STEP)]
        val = lambda i, at: size[i][at[1]] if at[0] == 'size' else box[i][0][at[1]]
        ref_of = {at: (statistics.median(val(i, at) for i in group) if len(group) > 2 else val(group[0], at)) for at in attrs}
        for i in (group if len(group) > 2 else group[1:]):
            dev = [(at, val(i, at) - ref_of[at]) for at in attrs]
            dev = [(at, d) for at, d in dev if TOUCH < abs(d) <= STEP and not deliberate(abs(d), i, i)]
            if not dev:
                continue
            ref_name = 'the others' if len(group) > 2 else f"'{group[0]}'"
            what = ', '.join(f"{'size' if at[0] == 'size' else 'position'} {AX[at[1]]} {d:+g} mm" for at, d in dev)
            pos_only = all(at[0] == 'position' for at, _d in dev)
            add('MISMATCHED_PAIR', 'warning', [i] + [g for g in group if g != i],
                f"'{i}' is the twin of {ref_name} ({', '.join(g for g in group if g != i)[:120]}) but differs by {what}. "
                + ("Line it up with them." if pos_only else "Make the twins the same size (or clearly different on purpose)."),
                [f"twins: {', '.join(group[:8])} (same thickness direction, sizes and alignment within {STEP:g} mm)",
                 *(f"{'size' if at[0] == 'size' else 'min'} {AX[at[1]]}: {i} = {_f(val(i, at))} mm, "
                   f"{'median of the others' if len(group) > 2 else group[0]} = {_f(ref_of[at])} mm -> {d:+.2f} mm"
                   for at, d in dev)],
                [round(v, 1) for v in box[i][0]],
                {'action': 'translate', 'component': i, 'delta': [round(-sum(d for at, d in dev if at == ('position', k)), 3)
                                                                  for k in range(3)]} if pos_only else None)

    # 4. rows of identical parallel boards with nearly even spacing
    rows = {}
    for i in ids:
        k = thin[i]
        key = (k, tuple(round(v) for v in size[i]), tuple(round(box[i][0][j]) for j in range(3) if j != k))
        rows.setdefault(key, []).append(i)
    for (k, _s, _p), row in rows.items():
        if len(row) < 3:
            continue
        row.sort(key=lambda i: box[i][0][k])
        pos = [box[i][0][k] for i in row]
        steps = [pos[n + 1] - pos[n] for n in range(len(pos) - 1)]
        def evenness(st):                # how many spacings share one value (within TOUCH)
            return max(sum(abs(q - v) <= TOUCH for q in st) for v in st)

        def moved(m, dlt):               # the spacings after moving board m by dlt along k
            p = list(pos)
            p[m] += dlt
            return [p[n + 1] - p[n] for n in range(len(p) - 1)]
        base, best = evenness(steps), None
        for m in range(len(row)):        # try putting each board where its neighbours say it belongs
            cands = ([steps[0] - steps[1]] if m == 0 else [steps[-2] - steps[-1]] if m == len(row) - 1 else
                     [(steps[m] - steps[m - 1]) / 2])
            for dlt in cands:
                if TOUCH < abs(dlt) <= 2 * STEP:
                    sc = evenness(moved(m, dlt))
                    if sc > base and (best is None or (sc, -abs(dlt)) > (best[0], -abs(best[2]))):
                        best = (sc, m, dlt)
        if best is None:
            continue                     # no single misplaced board: a deliberate layout (or a gradual one)
        _sc, culprit, delta = best
        after = moved(culprit, delta)
        ref = Counter(round(q * 2) / 2 for q in after).most_common(1)[0][0]
        bad = [(n, q) for n, q in enumerate(steps) if TOUCH < abs(q - ref) <= 2 * STEP]
        basis = (f"moving {row[culprit]} by {delta:+.2f} mm makes {best[0]} of {len(steps)} spacings equal "
                 f"({ref:g} mm); now {base}")
        if not bad:
            continue
        first = row[culprit if culprit is not None else bad[0][0] + 1]
        add('UNEVEN_SPACING', 'warning', [first] + [i for i in row if i != first],
            f"{len(row)} identical boards ({', '.join(row[:6])}{'...' if len(row) > 6 else ''}) are spaced almost "
            f"evenly along {AX[k]} ({ref:g} mm), but " + ', '.join(f"'{row[n]}' -> '{row[n + 1]}' is {s:g} mm" for n, s in bad[:4])
            + (f". Move '{first}' by {round(delta, 3):g} mm." if culprit is not None else '.')
            + " Use one spacing (\"repeat\" with a step does this exactly).",
            [f"{AX[k]} positions = " + ', '.join(f'{row[n]}: {_f(p)}' for n, p in enumerate(pos)),
             "spacings = " + ', '.join(_f(s) for s in steps), basis,
             *(f"{row[n]} -> {row[n + 1]}: {s:.2f} - {ref:.2f} = {s - ref:+.2f} mm" for n, s in bad[:4])],
            [round(v, 1) for v in box[first][0]], move(first, k, delta) if culprit is not None else None)

    # 5. mirror pairs that are not quite symmetric about the product centre
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
                            [round(v, 1) for v in box[right][0]], move(right, k, mr - ml))
    # 6. gravity: a board must sit on something, lock sideways or interlock; hanging on upward tabs is not enough
    floor_y = min((box[i][0][1] for i in ids), default=0.0)
    partners = {}
    for j in joints:
        if j.get('status') == 'joined':
            partners.setdefault(j['a'], []).append((j['b'], j.get('type')))
            partners.setdefault(j['b'], []).append((j['a'], j.get('type')))
    for i in ids:
        if not partners.get(i) or box[i][0][1] <= floor_y + TOUCH:
            continue
        above, held = [], False
        for o, kind in partners[i]:
            if kind != 'tab_slot' or o not in box:
                held = True                     # interlocking / glued / hinged, or a tilted partner: not judged here
                break
            if box[o][0][1] >= box[i][1][1] - TOUCH:
                if o not in above:              # one connection can be several joints (one per tab)
                    above.append(o)             # the partner is over it: the tab pushes up into the partner
            else:
                held = True                     # it sits on the partner, or the tab goes in sideways
                break
        if not held and above:
            add('HELD_FROM_ABOVE', 'warning', [i] + above,
                f"'{i}' only hangs from {', '.join(repr(o) for o in above)} on tabs pushing up into "
                f"{'it' if len(above) == 1 else 'them'}: glue-free, only friction holds it and gravity pulls it out of its "
                f"slots. Give it something to sit on (a ledge or wall plate it tabs down into), or a tab sideways into a wall.",
                [f"{i}: y {_f(box[i][0][1])} .. {_f(box[i][1][1])} mm",
                 *(f"{o}: y {_f(box[o][0][1])} .. {_f(box[o][1][1])} mm (above {i}: its tab points up)" for o in above),
                 f"joints of {i}: " + ', '.join(sorted({f"{k} with {o}" for o, k in partners[i]})),
                 'nothing under it and no sideways or interlocking joint'],
                [round(v, 1) for v in box[i][0]])
    issues.sort(key=lambda i: ({'error': 0, 'warning': 1, 'info': 2}[i['severity']], i['code']))
    return {'issues': issues[:MAX_ISSUES], 'boards': boards, 'skipped_tilted': [i for i in plates if i not in box]}
