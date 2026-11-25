"""
Production booklet (PDF) generator.

A tiny dependency-free vector PDF writer is used so that every cutting template is drawn
in real millimetres: page size == sheet size and 1 mm == 72/25.4 pt. Printed at "actual
size / 100 %", templates are 1:1; every template carries a 50 mm scale-check bar.

Booklet contents:
  1. Cover: project info, material, validation status, nesting statistics, component schedule
  2. Cutting templates (one page per sheet, 1:1)
  3. Component drawings (one page per component: dimensions, feature & tab tables, joints)
  4. Assembly sequence (derived from the joint graph)
"""
import math
import time
import zlib

from . import geometry as G
from .model import Plate, find_component, material_of
from .nesting import SHEET_PRESETS

MM = 72.0 / 25.4
PAPER = {k: v for k, v in SHEET_PRESETS.items() if not k.startswith('board')}


class PDFDoc:
    def __init__(self):
        self.pages = []

    def page(self, w_mm, h_mm):
        p = PDFPage(w_mm, h_mm)
        self.pages.append(p)
        return p

    def to_bytes(self, title='Production booklet'):
        objs = []

        def add(body):
            objs.append(body)
            return len(objs)

        cat = add(None)
        pages = add(None)
        f1 = add(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
        f2 = add(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>')
        f3 = add(b'<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>')
        kids = []
        for p in self.pages:
            data = zlib.compress('\n'.join(p.ops).encode('latin-1'))
            content = add(b'<< /Length %d /Filter /FlateDecode >>\nstream\n' % len(data) + data + b'\nendstream')
            kids.append(add((f'<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 {p.W:.2f} {p.H:.2f}] '
                             f'/Resources << /Font << /F1 {f1} 0 R /F2 {f2} 0 R /F3 {f3} 0 R >> >> '
                             f'/Contents {content} 0 R >>').encode()))
        objs[cat - 1] = f'<< /Type /Catalog /Pages {pages} 0 R /ViewerPreferences << /PrintScaling /None >> >>'.encode()
        objs[pages - 1] = f'<< /Type /Pages /Kids [{" ".join(f"{k} 0 R" for k in kids)}] /Count {len(kids)} >>'.encode()
        info = add(f'<< /Title ({_pdf_str(title)}) /Producer (PuzzleCore Board Studio) >>'.encode('latin-1'))
        out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
        offsets = []
        for i, body in enumerate(objs, 1):
            offsets.append(len(out))
            out += f'{i} 0 obj\n'.encode() + body + b'\nendobj\n'
        xref = len(out)
        out += f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'.encode()
        for off in offsets:
            out += f'{off:010d} 00000 n \n'.encode()
        out += f'trailer\n<< /Size {len(objs) + 1} /Root {cat} 0 R /Info {info} 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
        return bytes(out)


def _pdf_str(s):
    s = str(s).encode('cp1252', errors='replace').decode('latin-1')
    return s.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _rgb(hexcol):
    h = hexcol.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


class PDFPage:
    """Drawing API in millimetres, origin top-left, +y down."""

    def __init__(self, w_mm, h_mm):
        self.w, self.h = w_mm, h_mm
        self.W, self.H = w_mm * MM, h_mm * MM
        self.ops = []

    def _p(self, x, y):
        return f'{x * MM:.3f} {self.H - y * MM:.3f}'

    def stroke(self, color='#111827', width=0.25, dash=None):
        r, g, b = _rgb(color)
        self.ops.append(f'{r:.3f} {g:.3f} {b:.3f} RG {width * MM:.3f} w')
        self.ops.append(f'[{" ".join(f"{d * MM:.2f}" for d in dash)}] 0 d' if dash else '[] 0 d')

    def fill(self, color):
        r, g, b = _rgb(color)
        self.ops.append(f'{r:.3f} {g:.3f} {b:.3f} rg')

    def line(self, x1, y1, x2, y2):
        self.ops.append(f'{self._p(x1, y1)} m {self._p(x2, y2)} l S')

    def poly(self, pts, close=True, mode='S'):
        ops = [f'{self._p(*pts[0])} m'] + [f'{self._p(*p)} l' for p in pts[1:]]
        self.ops.append(' '.join(ops) + (' h ' if close else ' ') + mode)

    def rect(self, x, y, w, h, mode='S'):
        self.ops.append(f'{x * MM:.3f} {self.H - (y + h) * MM:.3f} {w * MM:.3f} {h * MM:.3f} re {mode}')

    def circle(self, cx, cy, r, mode='S'):
        k = 0.5523 * r
        pts = [(cx + r, cy), (cx + r, cy + k), (cx + k, cy + r), (cx, cy + r), (cx - k, cy + r), (cx - r, cy + k),
               (cx - r, cy), (cx - r, cy - k), (cx - k, cy - r), (cx, cy - r), (cx + k, cy - r), (cx + r, cy - k),
               (cx + r, cy)]
        ops = [f'{self._p(*pts[0])} m']
        for i in range(1, 13, 3):
            ops.append(f'{self._p(*pts[i])} {self._p(*pts[i + 1])} {self._p(*pts[i + 2])} c')
        self.ops.append(' '.join(ops) + f' h {mode}')

    def text(self, x, y, s, size=3.0, font='F1', color='#111827', align='left'):
        """size in mm (cap-ish height ~ 0.7*size). y is the baseline."""
        pt = size * MM
        width = text_width(s, size, font)
        if align == 'center':
            x -= width / 2
        elif align == 'right':
            x -= width
        r, g, b = _rgb(color)
        self.ops.append(f'BT /{font} {pt:.2f} Tf {r:.3f} {g:.3f} {b:.3f} rg {self._p(x, y)} Td ({_pdf_str(s)}) Tj ET')


def text_width(s, size, font='F1'):
    factor = 0.6 if font == 'F3' else 0.56 if font == 'F2' else 0.52
    return len(str(s)) * size * factor


# ---------------------------------------------------------------------------
# Booklet layout helpers
# ---------------------------------------------------------------------------

STD_SCALES = [1, 1.5, 2, 2.5, 3, 4, 5, 10, 20]
INK, MUTED, LINE, ACCENT, CUT, INNER = '#111827', '#6b7280', '#9ca3af', '#0f4c81', '#e11d48', '#2563eb'


def _frame(pg, ctx, title, subtitle='', scale_txt='—', sheet_txt=''):
    m = 8.0
    pg.stroke(INK, 0.35)
    pg.rect(m, m, pg.w - 2 * m, pg.h - 2 * m)
    # Title block (bottom strip)
    tb_h, y0 = 12.0, pg.h - m - 12.0
    pg.line(m, y0, pg.w - m, y0)
    cols = [(m, 0.34, 'PRODUCT', ctx['product']), (None, 0.22, 'DRAWING', title),
            (None, 0.14, 'MATERIAL', ctx['material']), (None, 0.08, 'SCALE', scale_txt),
            (None, 0.10, 'SHEET' if sheet_txt else 'REV / DATE', sheet_txt or ctx['rev_date']),
            (None, 0.12, 'PAGE', '{PAGE}')]
    x, total = m, pg.w - 2 * m
    for _x, frac, label, value in cols:
        w = total * frac
        if x > m:
            pg.line(x, y0, x, pg.h - m)
        pg.text(x + 1.5, y0 + 3.6, label, 2.0, 'F1', MUTED)
        pg.text(x + 1.5, y0 + 9.2, _clip(value, w - 3, 3.2), 3.2, 'F2', INK)
        x += w
    if subtitle:
        pg.text(m + 4, m + 8, subtitle, 3.0, 'F1', MUTED)
    return CONTENT_BOX(pg)


def CONTENT_BOX(pg):
    m = 8.0
    return (m + 4, m + 12, pg.w - m - 4, pg.h - m - 12.0 - 4)


def mat_label(mat):
    name = mat['name']
    return name if f"{mat['thickness']:g} mm" in name else f"{name} ({mat['thickness']:g} mm)"


def sheet_stock_label(nesting, index, mat):
    """Stock board of one cutting sheet (sheets are never shared between materials/thicknesses)."""
    st = next((s['stock'] for s in nesting.get('sheets', []) if s['index'] == index), None)
    if not st:
        return mat_label(mat)
    label = mat_label({'name': st['material'], 'thickness': st['thickness']})
    if st.get('color'):
        from .colors import color_name
        label += f" - {color_name(st['color'])} ({st['color']})"
    return label


def _wrap(text, width_mm, size, font='F1'):
    lines, cur = [], ''
    for word in text.split():
        trial = f'{cur} {word}'.strip()
        if text_width(trial, size, font) > width_mm and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + ([cur] if cur else [])


def _clip(s, width_mm, size, font='F2'):
    s = str(s)
    while s and text_width(s, size, font) > width_mm:
        s = s[:-2] + '…' if len(s) > 2 else ''
        if s.endswith('……'):
            s = s[:-1]
    return s


def _table(pg, x, y, cols, rows, size=2.6, row_h=4.6, max_y=None, header=True):
    """cols = [(title, width_mm, align)]. Returns y after the table and rows not drawn."""
    widths = [c[1] for c in cols]
    total = sum(widths)
    if header:
        pg.fill('#e5e7eb')
        pg.rect(x, y, total, row_h, 'f')
        cx = x
        for title, w, align in cols:
            tx = cx + 1.2 if align == 'left' else cx + w - 1.2 if align == 'right' else cx + w / 2
            pg.text(tx, y + row_h - 1.3, title, size, 'F2', INK, align)
            cx += w
        y += row_h
    pg.stroke(LINE, 0.12)
    for i, row in enumerate(rows):
        if max_y is not None and y + row_h > max_y:
            return y, rows[i:]
        if i % 2:
            pg.fill('#f8fafc')
            pg.rect(x, y, total, row_h, 'f')
        cx = x
        for (title, w, align), val in zip(cols, row):
            txt = _clip(val, w - 2.4, size, 'F1')
            tx = cx + 1.2 if align == 'left' else cx + w - 1.2 if align == 'right' else cx + w / 2
            pg.text(tx, y + row_h - 1.3, txt, size, 'F1', INK, align)
            cx += w
        y += row_h
        pg.line(x, y, x + total, y)
    return y, []


def _dim_h(pg, x1, x2, y, label, size=2.6):
    pg.stroke(ACCENT, 0.18)
    pg.line(x1, y, x2, y)
    for x, s in ((x1, 1), (x2, -1)):
        pg.poly([(x, y), (x + 1.6 * s, y - 0.6), (x + 1.6 * s, y + 0.6)], True, 'B')
    pg.fill('#ffffff')
    w = text_width(label, size) + 2
    pg.rect((x1 + x2) / 2 - w / 2, y - size * 0.75, w, size * 1.1, 'f')
    pg.text((x1 + x2) / 2, y + size * 0.25, label, size, 'F2', ACCENT, 'center')


def _dim_v(pg, x, y1, y2, label, size=2.6):
    pg.stroke(ACCENT, 0.18)
    pg.line(x, y1, x, y2)
    for y, s in ((y1, 1), (y2, -1)):
        pg.poly([(x, y), (x - 0.6, y + 1.6 * s), (x + 0.6, y + 1.6 * s)], True, 'B')
    pg.fill('#ffffff')
    w = text_width(label, size) + 2
    pg.rect(x - w / 2, (y1 + y2) / 2 - size * 0.75, w, size * 1.1, 'f')
    pg.text(x, (y1 + y2) / 2 + size * 0.25, label, size, 'F2', ACCENT, 'center')


def assembly_sequence(design):
    """Order joined connections: start from the largest part, then build bottom-up (+Y is up),
    so structure is installed before the parts that close it (e.g. bulkheads before the deck)."""
    joined = [j for j in design['joints'] if j.get('status') == 'joined']
    if not design['components']:
        return []
    area = {c['id']: abs(G.signed_area(c['outline'])) for c in design['components']}
    height = {c['id']: Plate(design, c).world_centre()[1] for c in design['components']}
    base = max(area, key=area.get)
    placed, steps, remaining = {base}, [], list(joined)
    while remaining:
        progress = False
        for target in sorted({x for j in remaining for x in (j['a'], j['b'])} - placed,
                             key=lambda c: (round(height.get(c, 0), 1), -area.get(c, 0))):
            js = [j for j in remaining if (j['a'] == target and j['b'] in placed) or
                  (j['b'] == target and j['a'] in placed)]
            if js:
                steps.append({'component': target, 'joints': js})
                placed.add(target)
                remaining = [j for j in remaining if j not in js]
                progress = True
                break
        if not progress:
            inner = [j for j in remaining if j['a'] in placed and j['b'] in placed]
            if inner:
                steps.append({'component': None, 'joints': inner})
                remaining = [j for j in remaining if j not in inner]
            else:  # disconnected sub-assembly
                comp = remaining[0]['a']
                placed.add(comp)
                steps.append({'component': comp, 'joints': [], 'note': 'separate sub-assembly'})
    return [{'base': base}] + steps


def _joint_text(j):
    fx = (j.get('fasteners') or {}).get('kind')
    how = {'screw': 'screws', 'confirmat': 'confirmat screws', 'dowel': 'glue + dowels'}.get(fx, 'glue')
    if j['type'] == 'tab_slot':
        return f"tab '{j['tab']}' of {j['a']} into slot '{j.get('slot', '?')}' of {j['b']}"
    if j['type'] == 'edge_butt':
        return f"edge {j['a_edge']} of {j['a']} butts against face of {j['b']} ({how})"
    if j['type'] == 'edge_mitre':
        kind = 'bevelled mitre' if j.get('bevel') else 'corner'
        return f"edge {j['a_edge']} of {j['a']} meets edge {j['b_edge']} of {j['b']} ({kind}, {how})"
    if j['type'] == 'hinge':
        return f"hang door {j['a']} on {j['b']} (concealed cup hinges on edge {j['a_edge']})"
    if j['type'] == 'finger':
        return f"interleave the corner fingers of {j['a']} and {j['b']} (box joint, no glue)"
    if j['type'] == 'cross_lap':
        return f"slot {j['a']} and {j['b']} together at their halving notches (cross-lap, no glue)"
    return f"{j['a']} laminated face-to-face onto {j['b']} (glue)"


def _plan_rows(design, plan):
    """Rows for the validated assembly plan (manufacturing.plan_assembly): every step brings a board or a
    pre-built sub-assembly in along a direction that all its tabs / dowels allow."""
    joined = [j for j in design['joints'] if j.get('status') == 'joined']
    rows, n = [], [0]

    def dirtxt(v):
        names = {(1, 0, 0): '+X (right)', (-1, 0, 0): '-X (left)', (0, 1, 0): 'up', (0, -1, 0): 'down',
                 (0, 0, 1): '+Z (forward)', (0, 0, -1): '-Z (back)'}
        key = tuple(round(c) for c in v)
        return names.get(key, '[' + ', '.join(f'{c:.2f}' for c in v) + ']')

    def walk(steps, present, label):
        for st in steps:
            if 'base' in st:
                present |= set(st['base'])
                rows.append([str(n[0]), ', '.join(st['base']), f'Base {label}- lay out on the bench', ''])
                n[0] += 1
                continue
            if 'subassembly' in st:
                rows.append(['', ', '.join(st['add']), 'Pre-assemble this sub-assembly first:', ''])
                walk(st['subassembly'], set(), 'of the sub-assembly ')
            add = set(st['add'])
            js = [j for j in joined if (j['a'] in add and j['b'] in present) or (j['b'] in add and j['a'] in present)]
            for i, j in enumerate(js or [None]):
                rows.append([str(n[0]) if i == 0 else '', ', '.join(st['add']) if i == 0 else '',
                             (f"move {dirtxt(st['direction'])}: " if i == 0 else '') + (_joint_text(j) if j else ''),
                             j['id'] if j else ''])
            n[0] += 1
            present |= add
    for asm in plan:
        walk(asm['steps'], set(), '')
    return rows


def _cutlist_pages(doc, pw, ph, ctx, cutlist):
    cols = [('Part', 40, 'left'), ('Qty', 9, 'center'), ('Material', 46, 'left'), ('t', 8, 'right'),
            ('Finished L x W', 30, 'right'), ('Blank L x W', 30, 'right'), ('Grain', 18, 'left'),
            ('Band', 9, 'center'), ('Drill', 9, 'center')]
    rows = [[l['part'], str(l['quantity']), l['material'], f"{l['thickness']:g}",
             f"{l['finished_length']:.1f} x {l['finished_width']:.1f}", f"{l['blank_length']:.1f} x {l['blank_width']:.1f}",
             l['grain'], str(l['banded_edges']), str(l['drilling'])] for l in cutlist['lines']]
    first, rest = True, rows
    while rest or first:
        pg = doc.page(pw, ph)
        x0, y0, x1, y1 = _frame(pg, ctx, 'Cut list' + ('' if first else ' (cont.)'))
        if first:
            pg.text(x0, y0 + 2, 'CUT LIST', 4.0, 'F2', INK)
            for i, line in enumerate(_wrap(cutlist['note'], x1 - x0, 2.4)):
                pg.text(x0, y0 + 7 + i * 3.6, line, 2.4, 'F1', MUTED)
            y0 += 14
        yy, rest = _table(pg, x0, y0, cols, rest, size=2.3, row_h=4.2, max_y=y1)
        first = False


# ---------------------------------------------------------------------------
# Booklet
# ---------------------------------------------------------------------------

def build_booklet(design, report, nesting, cut, paper='A4', mfg=None, cutlist=None):
    if paper not in PAPER:
        raise ValueError(f"paper must be one of {sorted(PAPER)}")
    pw, ph = max(PAPER[paper]), min(PAPER[paper])  # landscape booklet pages
    mat = design['material']
    ctx = {'product': design['name'], 'material': mat_label(mat),
           'rev_date': f"r{design.get('revision', 0)} / {time.strftime('%Y-%m-%d')}"}
    doc = PDFDoc()
    comps = design['components']
    by_id = {p['id']: p for p in nesting['placements']}
    st = nesting['stats']

    # 1. Cover ------------------------------------------------------------------
    pg = doc.page(pw, ph)
    x0, y0, x1, y1 = _frame(pg, ctx, 'Production booklet')
    pg.text(x0, y0 + 6, design['name'], 8, 'F2', INK)
    pg.text(x0, y0 + 13, _clip(design.get('description', ''), x1 - x0, 3.2, 'F1'), 3.2, 'F1', MUTED)
    status = 'VALIDATED - READY FOR PRODUCTION' if report['valid'] else 'NOT VALID - DO NOT CUT'
    pg.fill('#dcfce7' if report['valid'] else '#fee2e2')
    pg.rect(x1 - 92, y0, 92, 10, 'f')
    pg.text(x1 - 46, y0 + 6.6, status, 3.2, 'F2', '#166534' if report['valid'] else '#991b1b', 'center')
    s = report['summary']
    info = [('Design ID', design['id']), ('Revision', str(design.get('revision', 0))),
            ('Material', mat['name']), ('Thickness', f"{mat['thickness']:g} mm"),
            ('Kerf / clearance', f"{mat['kerf']:g} / {mat['clearance']:g} mm"),
            ('Kerf compensation', f"{cut['kerf_compensation']:g} mm"),
            ('Components / joints', f"{s['components']} / {s['joined']} joined"),
            ('Validation', f"{s['errors']} errors, {s['warnings']} warnings"),
            ('Sheet', f"{nesting['sheet']['name']} {nesting['sheet']['width']:g} x {nesting['sheet']['height']:g} mm"),
            ('Sheets required', str(nesting['sheet_count'])),
            ('Material area', f"{st['total_material_area'] / 100:.1f} cm²"),
            ('Used / waste', f"{st['used_area'] / 100:.1f} cm² / {st['waste_percent']:.1f} %"),
            ('Nesting efficiency', f"{st['efficiency_percent']:.1f} %")]
    yy = y0 + 22
    for k, v in info:
        pg.text(x0, yy, k, 2.8, 'F1', MUTED)
        pg.text(x0 + 34, yy, v, 2.8, 'F2', INK)
        yy += 4.6
    tx = x0 + 100
    pg.text(tx, y0 + 20, 'COMPONENT SCHEDULE', 3.0, 'F2', ACCENT)
    cols = [('ID', 34, 'left'), ('Name', 52, 'left'), ('Group', 26, 'left'), ('Size (mm)', 30, 'right'),
            ('t', 10, 'right'), ('Sheet', 14, 'center'), ('Qty', 10, 'center')]
    rows = []
    for c in comps:
        pl = Plate(design, c)
        orr = G.oriented_rect(pl.cut)
        pm = by_id.get(c['id'])
        rows.append([c['id'], c.get('name', ''), c.get('group', ''), f"{orr['length']:.1f} x {orr['width']:.1f}",
                     f"{pl.t:g}", str(pm['sheet'] + 1) if pm else '—', '1'])
    yy, rest = _table(pg, tx, y0 + 22, cols, rows, max_y=y1)
    while rest:
        pg = doc.page(pw, ph)
        x0, y0, x1, y1 = _frame(pg, ctx, 'Component schedule (cont.)')
        yy, rest = _table(pg, x0, y0, cols, rest, max_y=y1)
    notes = ['Print cutting templates at 100 % / "actual size". Verify the 50 mm scale bar before cutting.',
             'Cut inner paths (blue) before outer profiles (red). Labels are engrave-only.',
             'Every part carries its ID; match IDs with the assembly sequence at the end of this booklet.']
    ny = max(yy, y0 + 22 + 4.6 * len(info)) + 8
    if ny + 16 < y1:
        pg.text(x0, ny, 'PRODUCTION NOTES', 3.0, 'F2', ACCENT)
        for i, n in enumerate(notes):
            pg.text(x0, ny + 5 + i * 4.4, f'{i + 1}. {n}', 2.7, 'F1', INK)

    if cutlist:
        _cutlist_pages(doc, pw, ph, ctx, cutlist)

    # 2. Cutting templates (1:1) -----------------------------------------------
    sw, sh = nesting['sheet']['width'], nesting['sheet']['height']
    for si, sheet in enumerate(cut['sheets']):
        pg = doc.page(sw, sh)
        pg.stroke(LINE, 0.2, dash=[2, 2])
        pg.rect(0.5, 0.5, sw - 1, sh - 1)
        for p in sorted(sheet['paths'], key=lambda p: p['order']):
            if p['type'] in ('engrave', 'pocket'):
                pg.stroke('#0ea5e9' if p['type'] == 'engrave' else '#16a34a', 0.15, dash=[1.5, 1])
            else:
                pg.stroke(CUT if p['type'] == 'outer' else INNER, 0.15)
            if p['shape'] == 'circle':
                pg.circle(p['center'][0], p['center'][1], p['radius'])
            else:
                pg.poly(p['points'], close=p.get('closed', True))
        for lb in sheet['labels']:
            pg.text(lb['position'][0], lb['position'][1] + lb['size'] * 0.35, lb['text'], lb['size'], 'F2', INK,
                    'center')
        # Scale check + sheet info inside the reserved title strip below the usable area
        m = nesting['sheet']['margin']
        base = sh - m - nesting['sheet']['title_block']
        pg.stroke(INK, 0.25)
        pg.rect(m, base + 1, 10, 10)
        pg.line(m + 14, base + 11, m + 64, base + 11)
        for k in range(6):
            pg.line(m + 14 + k * 10, base + (8.5 if k % 5 else 7.5), m + 14 + k * 10, base + 11)
        pg.text(m + 14, base + 5.5, '10 mm square  |  50 mm scale check', 2.2, 'F1', MUTED)
        info_txt = (f"{design['name']}  -  CUTTING SHEET {si + 1} OF {nesting['sheet_count']}  -  "
                    f"{sheet_stock_label(nesting, si, mat)}  -  SCALE 1:1 (print at 100 %)  -  "
                    f"kerf comp. {cut['kerf_compensation']:g} mm  -  page {{PAGE}}")
        pg.text(sw - m, base + 9, info_txt, 2.4, 'F2', INK, 'right')

    # 3. Component drawings -----------------------------------------------------
    joints = design['joints']
    for c in comps:
        pl = Plate(design, c)
        pg = doc.page(pw, ph)
        bx0, by0, bx1, by1 = pl.bbox2d
        W, H = bx1 - bx0, by1 - by0
        x0, y0, x1, y1 = CONTENT_BOX(pg)
        draw_w, draw_h = (x1 - x0) * 0.58, (y1 - y0) - 22
        need = max(W / (draw_w - 20), H / (draw_h - 20), 1e-6)
        scale = next((s for s in STD_SCALES if s >= need), math.ceil(need))
        k = 1.0 / scale
        scale_txt = f'1:{scale:g}'
        _frame(pg, ctx, f"{c['id']}", '', scale_txt)
        ox = x0 + 14 + (draw_w - 20 - W * k) / 2
        oy = y0 + 16 + (draw_h - 20 - H * k) / 2
        tf = lambda p: (ox + (p[0] - bx0) * k, oy + (by1 - p[1]) * k)  # y-up drawing, datum = lower-left
        pg.text(x0, y0 + 2, f"{c['id']}  -  {c.get('name', '')}", 4.6, 'F2', INK)
        pg.text(x0, y0 + 7.5, f"Group: {c.get('group', '')}   |   Thickness {pl.t:g} mm   |   Scale {scale_txt}   |   "
                              f"Datum: lower-left corner of bounding box", 2.6, 'F1', MUTED)
        pg.fill('#fbf6ee')
        pg.poly([tf(p) for p in pl.cut], True, 'f')
        pg.stroke(CUT, 0.3)
        pg.poly([tf(p) for p in pl.cut])
        frows = []
        for i, (f, poly) in enumerate(pl.feature_polys, 1):
            col = {'slot': INNER, 'hole': '#7c3aed', 'opening': '#059669'}[f['kind']]
            pg.stroke(col, 0.25, dash=[1.2, 0.8] if f['kind'] == 'opening' else None)
            pg.fill('#ffffff')
            if f['shape'] == 'circle':
                cx, cy = tf(f['center'])
                pg.circle(cx, cy, f['diameter'] / 2 * k, 'B')
                size = f"Ø {f['diameter']:.2f}"
            else:
                pg.poly([tf(p) for p in poly], True, 'B')
                bx = G.bbox(poly)
                size = f"{bx[2] - bx[0]:.2f} x {bx[3] - bx[1]:.2f}"
            cx, cy = tf(f['center'])
            pg.fill(col)
            pg.circle(cx, cy - 2.6, 1.6, 'f')
            pg.text(cx, cy - 1.9, str(i), 2.0, 'F2', '#ffffff', 'center')
            frows.append([str(i), f['id'], f['kind'], f"{f['center'][0] - bx0:.2f}, {f['center'][1] - by0:.2f}",
                          size, f"{f.get('angle', 0):.1f}°" if f['shape'] == 'rect' else '—'])
        # dimensions
        (lx, ly), (rx, ry) = tf((bx0, by0)), tf((bx1, by1))
        _dim_h(pg, lx, rx, ly + 7, f'{W:.2f}')
        _dim_v(pg, lx - 7, ry, ly, f'{H:.2f}')
        pg.stroke(MUTED, 0.15)
        pg.circle(lx, ly, 0.9)
        pg.text(lx + 1.5, ly + 3.5, 'datum', 2.0, 'F1', MUTED)

        tx = x0 + draw_w + 4
        tw = x1 - tx
        yy = y0 + 14
        pg.text(tx, yy, 'CUT FEATURES', 3.0, 'F2', ACCENT)
        yy, _ = _table(pg, tx, yy + 1.5, [('#', 6, 'center'), ('ID', tw * 0.28, 'left'), ('Kind', 14, 'left'),
                                          ('Centre x, y', 26, 'right'), ('Size', tw - 6 - tw * 0.28 - 14 - 26 - 12, 'right'),
                                          ('Angle', 12, 'right')],
                       frows or [['—', 'no interior cuts', '', '', '', '']], size=2.3, row_h=4.0, max_y=y1 - 50)
        if c.get('tabs'):
            pg.text(tx, yy + 5, 'TABS (tenons on outline)', 3.0, 'F2', ACCENT)
            trows = [[t['id'], str(t['edge']), f"{t['offset']:.2f}", f"{t['width']:.2f}", f"{t['depth']:.2f}"]
                     for t in c['tabs']]
            yy, _ = _table(pg, tx, yy + 6.5, [('ID', 18, 'left'), ('Edge', 12, 'center'), ('Offset', 18, 'right'),
                                              ('Width', 18, 'right'), ('Depth', 18, 'right')], trows, size=2.3,
                           row_h=4.0, max_y=y1 - 30)
        drills = [d for d in (mfg or {}).get('drilling', []) if d['component'] == c['id']]
        if drills:
            drows = []
            for n_, d in enumerate(drills, 1):
                dx, dy = tf(d['position'])
                pg.stroke('#b45309', 0.2)
                if d['type'] == 'face_bore':
                    pg.circle(dx, dy, max(d['diameter'] / 2 * k, 0.6))
                else:
                    pg.line(dx - 1.2, dy - 1.2, dx + 1.2, dy + 1.2)
                    pg.line(dx - 1.2, dy + 1.2, dx + 1.2, dy - 1.2)
                where = (f"face {d['face']}" + (' thru' if d.get('through') else '')) if d['type'] == 'face_bore' \
                    else f"edge {d['edge']}"
                drows.append([str(n_), where, f"{d['position'][0] - bx0:.1f}, {d['position'][1] - by0:.1f}",
                              f"{d['diameter']:g}", f"{d['depth']:g}", d['fastener']])
            pg.text(tx, yy + 5, 'DRILLING (from datum)', 3.0, 'F2', ACCENT)
            yy, more = _table(pg, tx, yy + 6.5, [('#', 6, 'center'), ('Where', 22, 'left'), ('x, y', 24, 'right'),
                                                 ('Ø', 9, 'right'), ('Depth', 11, 'right'), ('For', tw - 72, 'left')],
                              drows, size=2.2, row_h=3.8, max_y=y1 - 34)
            if more:
                pg.text(tx, yy + 3, f'+ {len(more)} more drilling operations (see the manufacturing report)', 2.2,
                        'F1', MUTED)
                yy += 3
        mine = [j for j in joints if j.get('status') == 'joined' and c['id'] in (j['a'], j['b'])]
        pg.text(tx, yy + 5, 'ASSEMBLY REFERENCES', 3.0, 'F2', ACCENT)
        jrows = [[j['id'], j['type'], j['b'] if j['a'] == c['id'] else j['a']] for j in mine]
        yy, _ = _table(pg, tx, yy + 6.5, [('Joint', tw * 0.45, 'left'), ('Type', tw * 0.2, 'left'),
                                          ('Mates with', tw * 0.35, 'left')],
                       jrows or [['—', '', '']], size=2.3, row_h=4.0, max_y=y1 - 14)
        pm = by_id.get(c['id'])
        instr = (f"Cut from {material_of(design, c)['name']} at {pl.t:g} mm thickness. "
                 + (f"Cutting sheet {pm['sheet'] + 1}, rotated {pm['rotation']:g} deg. " if pm else
                    'NOT NESTED: the part does not fit the selected sheet. ')
                 + 'Cut slots, holes and openings first and the outer profile last. '
                   'Openings are intentional design features - do not fill them.')
        pg.text(tx, yy + 6, 'CUTTING INSTRUCTIONS', 3.0, 'F2', ACCENT)
        for i, line in enumerate(_wrap(instr, tw, 2.4)):
            if yy + 11 + i * 3.8 < y1:
                pg.text(tx, yy + 11 + i * 3.8, line, 2.4, 'F1', INK)

    # 4. Assembly sequence --------------------------------------------------------
    plan = (mfg or {}).get('assembly_plan')
    seq = [] if plan else assembly_sequence(design)
    rows = _plan_rows(design, plan) if plan else []
    if seq:
        rows.append(['0', seq[0]['base'], 'Base component - lay flat on the bench', ''])
        for n, st_ in enumerate(seq[1:], 1):
            for i, j in enumerate(st_['joints'] or [None]):
                rows.append([str(n) if i == 0 else '', st_['component'] or '(close-out)' if i == 0 else '',
                             _joint_text(j) if j else st_.get('note', ''), j['id'] if j else ''])
    cols = [('Step', 12, 'center'), ('Add component', 42, 'left'), ('Connection', pw - 16 - 8 - 12 - 42 - 50, 'left'),
            ('Joint ID', 50, 'left')]
    rest = rows
    first = True
    while rest or first:
        pg = doc.page(pw, ph)
        x0, y0, x1, y1 = _frame(pg, ctx, 'Assembly sequence' + ('' if first else ' (cont.)'))
        _y, rest = _table(pg, x0, y0, cols, rest, size=2.5, row_h=4.4, max_y=y1)
        first = False

    total = len(doc.pages)
    for i, p in enumerate(doc.pages, 1):
        p.ops = [o.replace('{PAGE}', f'{i} of {total}') for o in p.ops]
    return doc.to_bytes(title=f"{design['name']} - production booklet")
