/**
 * 2D cut-sheet workspace. Renders /layout2d output (nested sheets + cutting paths) in real
 * millimetres. Sheets are laid side by side; pan with drag, zoom with the wheel.
 */
const NS = 'http://www.w3.org/2000/svg';
const GAP = 40;
const KIND_COLOR = { slot: 'var(--slot)', opening: 'var(--opening)', hole: 'var(--hole)' };

const el = (tag, attrs = {}, parent) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
};
const ptsToD = (pts) => 'M' + pts.map((p) => `${p[0]},${p[1]}`).join('L') + 'Z';
const circleD = ([cx, cy], r) => `M${cx - r},${cy}a${r},${r} 0 1,0 ${2 * r},0a${r},${r} 0 1,0 ${-2 * r},0Z`;

export class Sheet2D {
  constructor(svg, { onSelect, onHover, scalebar, onCursor } = {}) {
    this.svg = svg;
    this.onSelect = onSelect;
    this.onHover = onHover;
    this.onCursor = onCursor;
    this.scalebarEl = scalebar;
    this.view = { x: 0, y: 0, w: 1000, h: 600 };
    this.labels = true;
    this.mode = 'design';
    this.groups = new Map();
    this._bind();
    new ResizeObserver(() => this._apply()).observe(svg);
  }

  load(layout, { mode = 'design', states = {} } = {}) {
    this.layout = layout;
    this.mode = mode;
    this.svg.innerHTML = '';
    this.groups.clear();
    const sheet = layout.nesting.sheet;
    const defs = el('defs', {}, this.svg);
    const pat = el('pattern', { id: 'grid10', width: 10, height: 10, patternUnits: 'userSpaceOnUse' }, defs);
    el('path', { d: 'M10 0H0V10', fill: 'none', stroke: 'rgba(0,0,0,.06)', 'stroke-width': 0.3 }, pat);
    const world = (this.world = el('g', {}, this.svg));

    layout.cut.sheets.forEach((s, i) => {
      const ox = i * (sheet.width + GAP);
      const g = el('g', { transform: `translate(${ox},0)` }, world);
      el('rect', { x: 0, y: 0, width: sheet.width, height: sheet.height, rx: 1.5,
        fill: mode === 'production' ? '#f4f1ea' : '#e9dcc4', stroke: '#000', 'stroke-opacity': 0.25, 'stroke-width': 0.4 }, g);
      el('rect', { x: 0, y: 0, width: sheet.width, height: sheet.height, fill: 'url(#grid10)' }, g);
      const [ux0, uy0, ux1, uy1] = sheet.usable;
      el('rect', { x: ux0, y: uy0, width: ux1 - ux0, height: uy1 - uy0, fill: 'none', stroke: '#6b7280',
        'stroke-width': 0.3, 'stroke-dasharray': '3 2', opacity: 0.7 }, g);
      const t = el('text', { x: 0, y: -6, 'font-size': 8, fill: '#8b96a6', 'font-family': 'Inter, sans-serif' }, g);
      t.textContent = `Sheet ${i + 1} / ${layout.cut.sheets.length} · ${sheet.name} ${sheet.width} × ${sheet.height} mm`;

      const byPart = new Map();
      s.paths.forEach((p) => {
        if (!byPart.has(p.part)) byPart.set(p.part, []);
        byPart.get(p.part).push(p);
      });
      for (const [part, paths] of byPart) {
        const pg = el('g', { 'data-part': part, class: 'part' }, g);
        const outer = paths.find((p) => p.type === 'outer');
        const inner = paths.filter((p) => p.type === 'inner');
        const d = ptsToD(outer.points) + inner.map((p) => (p.shape === 'circle' ? circleD(p.center, p.radius) : ptsToD(p.points))).join('');
        const state = states[part];
        const body = el('path', { d, 'fill-rule': 'evenodd', fill: mode === 'production' ? '#fffdf8' : '#d6b483',
          stroke: 'none', class: 'part-body' }, pg);
        if (state === 'error') body.setAttribute('fill', '#e9a4a4');
        for (const p of inner) {
          const attrs = { fill: 'none', stroke: KIND_COLOR[p.feature_kind] || 'var(--slot)', 'stroke-width': 0.45,
            'vector-effect': 'non-scaling-stroke' };
          if (p.feature_kind === 'opening') attrs['stroke-dasharray'] = '4 2';
          p.shape === 'circle' ? el('circle', { ...attrs, cx: p.center[0], cy: p.center[1], r: p.radius }, pg)
            : el('path', { ...attrs, d: ptsToD(p.points) }, pg);
        }
        el('path', { d: ptsToD(outer.points), fill: 'none', stroke: 'var(--cut)', 'stroke-width': 1.1,
          'vector-effect': 'non-scaling-stroke', class: 'outline' }, pg);
        const lab = s.labels.find((l) => l.part === part);
        if (lab) {
          const tx = el('text', { x: lab.position[0], y: lab.position[1] + lab.size * 0.35, 'font-size': lab.size,
            'text-anchor': 'middle', fill: '#3b2a18', 'font-family': 'Inter, sans-serif', 'font-weight': 600,
            class: 'label' }, pg);
          tx.textContent = part;
        }
        const pm = layout.nesting.placements.find((p) => p.id === part);
        this.groups.set(part, { g: pg, ox, bbox: pm?.bbox, sheet: i });
      }
    });
    this.setLabels(this.labels);
    this.setSelected(this.selected);
    if (!this._fitted) { this.fit(); this._fitted = true; }
  }

  setLabels(on) {
    this.labels = on;
    this.svg.querySelectorAll('.label').forEach((t) => (t.style.display = on ? '' : 'none'));
  }

  setSelected(id) {
    this.selected = id;
    for (const [pid, it] of this.groups) {
      const sel = pid === id;
      const o = it.g.querySelector('.outline');
      o.setAttribute('stroke', sel ? 'var(--accent)' : 'var(--cut)');
      o.setAttribute('stroke-width', sel ? 2.2 : 1.1);
      it.g.querySelector('.part-body').style.filter = sel ? 'brightness(1.12) saturate(1.2)' : '';
    }
  }

  fit() {
    if (!this.layout) return;
    const s = this.layout.nesting.sheet, n = this.layout.cut.sheets.length || 1;
    const W = n * s.width + (n - 1) * GAP, H = s.height;
    this.view = { x: -20, y: -24, w: W + 40, h: H + 44 };
    this._apply();
  }

  focus(id) {
    const it = this.groups.get(id);
    if (!it?.bbox) return;
    const [x0, y0, x1, y1] = it.bbox;
    const pad = 30;
    this.view = { x: it.ox + x0 - pad, y: y0 - pad, w: x1 - x0 + 2 * pad, h: y1 - y0 + 2 * pad };
    this._apply();
  }

  _apply() {
    const r = this.svg.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const ar = r.width / r.height;
    let { x, y, w, h } = this.view;
    if (w / h > ar) { const nh = w / ar; y -= (nh - h) / 2; h = nh; } else { const nw = h * ar; x -= (nw - w) / 2; w = nw; }
    this.view = { x, y, w, h };
    this.svg.setAttribute('viewBox', `${x} ${y} ${w} ${h}`);
    this.pxPerMm = r.width / w;
    if (this.scalebarEl) {
      const nice = [1, 2, 5, 10, 20, 50, 100, 200, 500].find((v) => v * this.pxPerMm >= 60) || 1000;
      this.scalebarEl.innerHTML = `${nice} mm<i style="width:${nice * this.pxPerMm}px"></i>`;
    }
  }

  _toMm(e) {
    const r = this.svg.getBoundingClientRect();
    return [this.view.x + ((e.clientX - r.left) / r.width) * this.view.w, this.view.y + ((e.clientY - r.top) / r.height) * this.view.h];
  }

  _bind() {
    let drag = null;
    this.svg.addEventListener('wheel', (e) => {
      e.preventDefault();
      const [mx, my] = this._toMm(e);
      const k = Math.exp(e.deltaY * 0.0015);
      const v = this.view;
      this.view = { x: mx - (mx - v.x) * k, y: my - (my - v.y) * k, w: v.w * k, h: v.h * k };
      this._apply();
    }, { passive: false });
    this.svg.addEventListener('pointerdown', (e) => {
      drag = { x: e.clientX, y: e.clientY, v: { ...this.view }, moved: false };
      this.svg.setPointerCapture(e.pointerId);
    });
    this.svg.addEventListener('pointermove', (e) => {
      const [mx, my] = this._toMm(e);
      if (this.layout) {
        const s = this.layout.nesting.sheet;
        const i = Math.floor(mx / (s.width + GAP));
        this.onCursor?.(i >= 0 && i < this.layout.cut.sheets.length ? `sheet ${i + 1}  x ${(mx - i * (s.width + GAP)).toFixed(1)}  y ${my.toFixed(1)} mm` : '');
      }
      if (!drag) {
        const part = e.target.closest?.('.part')?.dataset.part || null;
        this.onHover?.(part, e);
        return;
      }
      const r = this.svg.getBoundingClientRect();
      const dx = ((e.clientX - drag.x) / r.width) * drag.v.w, dy = ((e.clientY - drag.y) / r.height) * drag.v.h;
      if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) > 3) {
        drag.moved = true;
        this.svg.classList.add('panning');
      }
      this.view = { ...drag.v, x: drag.v.x - dx, y: drag.v.y - dy };
      this._apply();
    });
    this.svg.addEventListener('pointerup', (e) => {
      if (drag && !drag.moved) {
        // pointer capture retargets events to the svg, so hit-test the actual element under the cursor
        const hit = document.elementFromPoint(e.clientX, e.clientY);
        this.onSelect?.(hit?.closest?.('.part')?.dataset.part || null);
      }
      drag = null;
      this.svg.classList.remove('panning');
    });
    this.svg.addEventListener('pointerleave', () => this.onHover?.(null));
  }
}
