/**
 * Compile loader: the overlay shown over the preview while a design compiles.
 *
 * Progress is driven only by the compiler's own stage events (see /canvas/compile-stream); each stage's share of
 * the bar is its measured share of compile time (collision checks dominate), and inside a stage the bar follows
 * the compiler's real item counts. The CSS 3D cabinet assembles one board per progress step. Everything that moves
 * continuously is a CSS transform/opacity animation, which the browser runs off the main thread, so the scene keeps
 * moving even while the 3D viewport builds a large model.
 */
const STAGES = [
  // id, label, unit of the compiler's item count, share of the bar (%)
  ['parse', 'Parsing JSON', null, 2],
  ['geometry', 'Generating geometry', 'board', 3],
  ['joints', 'Joining boards', 'joint', 22],
  ['dimensions', 'Validating dimensions', 'board', 4],
  ['joint_validation', 'Validating joints', 'joint', 4],
  ['collisions', 'Detecting gaps & overlaps', 'board pair', 50],
  ['model', 'Building 3D model', null, 5],
  ['render', 'Rendering', null, 10]
];

// CSS 3D cabinet (px, y down). Listed in assembly order; `from` is the exploded offset a board floats at.
const PARTS = [
  { c: [0, 61, 0], s: [184, 8, 90], from: [0, 70, 40] },          // bottom
  { c: [-96, 0, 0], s: [8, 130, 90], from: [-90, -20, 30] },      // left side
  { c: [96, 0, 0], s: [8, 130, 90], from: [90, -20, 30] },        // right side
  { c: [0, 0, -41], s: [184, 114, 8], from: [0, -10, -110] },     // back
  { c: [0, 0, 4], s: [184, 8, 82], from: [50, 10, 110] },         // shelf
  { c: [0, -30, 4], s: [8, 53, 82], from: [-40, -70, 120] },      // divider
  { c: [0, -61, 0], s: [200, 8, 96], from: [0, -100, 20] }        // top
];

const fmtTime = (ms) => {
  const s = ms / 1000;
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${(s % 60).toFixed(1).padStart(4, '0')}`;
};
const fmtDur = (s) => (s < 1 ? `${Math.max(1, Math.round(s * 1000))} ms` : `${s.toFixed(1)} s`);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function box([w, h, d]) {
  const f = (cls, fw, fh, tf) => `<i class="cl-face ${cls}" style="width:${fw}px;height:${fh}px;margin:${-fh / 2}px 0 0 ${-fw / 2}px;transform:${tf}"></i>`;
  return f('fz', w, h, `translateZ(${d / 2}px)`) + f('fz', w, h, `rotateY(180deg) translateZ(${d / 2}px)`)
    + f('fx', d, h, `rotateY(90deg) translateZ(${w / 2}px)`) + f('fx', d, h, `rotateY(-90deg) translateZ(${w / 2}px)`)
    + f('fy', w, d, `rotateX(90deg) translateZ(${h / 2}px)`) + f('fy', w, d, `rotateX(-90deg) translateZ(${h / 2}px)`);
}

export class CompileLoader {
  constructor(host, { onCancel, onHide } = {}) {
    this.onCancel = onCancel;
    this.onHide = onHide;
    this.el = document.createElement('div');
    this.el.className = 'cl';
    this.el.hidden = true;
    this.el.innerHTML = `
      <div class="cl-stage" aria-hidden="true">
        <div class="cl-hud tl mono">ASSEMBLY · ${PARTS.length} BOARDS</div>
        <div class="cl-hud tr mono">ISO · CAD</div>
        <div class="cl-scene"><div class="cl-world">
          <div class="cl-grid"></div>
          <div class="cl-ring"></div><div class="cl-ring r2"></div>
          <div class="cl-bounds">${box([216, 146, 112])}</div>
          <div class="cl-scan"></div>
          ${PARTS.map((p, i) => `<div class="cl-part" style="--x:${p.c[0]}px;--y:${p.c[1]}px;--z:${p.c[2]}px;--fx:${p.from[0]}px;--fy:${p.from[1]}px;--fz:${p.from[2]}px">
            <div class="cl-float" style="animation-delay:${-i * 0.37}s">${box(p.s)}</div></div>`).join('')}
        </div></div>
      </div>
      <div class="cl-info">
        <div class="cl-head">
          <div class="cl-head-text"><div class="cl-title">Compiling design</div><div class="cl-sub"></div></div>
          <div class="cl-time mono" title="Elapsed time">00:00.0</div>
        </div>
        <div class="cl-bar" role="progressbar" aria-label="Compile progress" aria-valuemin="0" aria-valuemax="100"><div class="cl-fill"></div></div>
        <div class="cl-meta"><span class="cl-pct mono">0%</span><span class="cl-hint">Press <kbd>Esc</kbd> to cancel</span></div>
        <ol class="cl-stages">${STAGES.map(([id, label]) => `<li data-st="${id}"><span class="cl-ico"></span><span class="cl-lbl">${label}</span><span class="cl-det mono"></span></li>`).join('')}</ol>
        <div class="cl-fail" hidden><div class="cl-fail-msg"></div></div>
        <div class="cl-actions"><button class="btn small" data-act="cancel">Cancel</button></div>
        <div class="cl-live" aria-live="polite"></div>
      </div>`;
    host.appendChild(this.el);
    this.q = (s) => this.el.querySelector(s);
    this.parts = [...this.el.querySelectorAll('.cl-part')];
    this.rows = Object.fromEntries([...this.el.querySelectorAll('[data-st]')].map((li) => [li.dataset.st, li]));
    this.q('[data-act="cancel"]').onclick = () => this.onCancel?.();
    this.active = false;
    new ResizeObserver(() => this._fit()).observe(this.q('.cl-stage'));
  }

  get busy() { return this.active && !this.done; }

  _fit() {
    const r = this.q('.cl-stage').getBoundingClientRect();   // scale so the exploded boards fit
    this.el.style.setProperty('--cl-scale', Math.max(0.4, Math.min(1.2, r.width / 470, r.height / 380)).toFixed(3));
  }

  start() {
    clearTimeout(this._hideT);
    this.st = Object.fromEntries(STAGES.map(([id]) => [id, { status: 'pending', frac: 0 }]));
    this.t0 = performance.now();
    this.lastServerT = 0;
    this.active = true;
    this.done = false;
    this.failed = false;
    this.el.className = 'cl';
    this.el.hidden = false;
    this.q('.cl-title').textContent = 'Compiling design';
    this.q('.cl-fail').hidden = true;
    this.q('.cl-hint').hidden = false;
    this._actions([['cancel', 'Cancel']]);
    Object.values(this.rows).forEach((li) => { li.className = ''; li.querySelector('.cl-det').textContent = ''; });
    this._set('parse', { status: 'active' });
    this._paint();
    this._fit();
    requestAnimationFrame(() => this.el.classList.add('show'));
    clearInterval(this._tick);
    this._tick = setInterval(() => { this.q('.cl-time').textContent = fmtTime(performance.now() - this.t0); }, 100);
  }

  /** A {stage, done, total, t} event from the compiler. */
  progress({ stage, done, total, t }) {
    if (!this.busy) return;
    const i = STAGES.findIndex(([id]) => id === stage);
    if (i < 0) return;
    STAGES.slice(0, i).forEach(([id]) => this.st[id].status !== 'done' && this._finishStage(id, t));
    const finished = !total || done >= total;
    const s = this.st[stage];
    s.frac = total ? Math.min(1, done / total) : 1;
    s.count = total ? [Math.min(done + (finished ? 0 : 1), total), total] : null;
    if (finished) this._finishStage(stage, t);
    else this._set(stage, { status: 'active' });
    this._paint();
  }

  /** Server work is finished; the page is now building the 3D view (render = 'active'). */
  rendering(serverT) {
    if (!this.busy) return;
    STAGES.slice(0, -1).forEach(([id]) => {
      if (this.st[id].status === 'pending' || this.st[id].status === 'active') {
        // a stage the compiler never reached was skipped (it stopped early); one it was in is complete
        if (this.st[id].status === 'active' || this.st[id].frac) this._finishStage(id, serverT);
        else this._set(id, { status: 'skipped' });
      }
    });
    this.renderT0 = performance.now();
    this._set('render', { status: 'active' });
    this._paint();
  }

  /** Model on screen: fill the bar, show the outcome briefly, then reveal the model. */
  complete(summary) {
    if (!this.busy) return Promise.resolve();
    Object.assign(this.st.render, { frac: 1, dur: (performance.now() - this.renderT0) / 1000 });
    this._set('render', { status: 'done' });
    this._stop();
    this.el.classList.add('ok');
    this.q('.cl-title').textContent = summary || 'Compiled';
    this._paint();
    return new Promise((resolve) => { this._hideT = setTimeout(() => { this.hide(); resolve(); }, 650); });
  }

  /** Show why compiling stopped. actions: [[id, label, primary?, handler]]. */
  fail({ title, message, actions }) {
    if (!this.active) return;
    const cur = STAGES.find(([id]) => this.st[id].status === 'active')?.[0] || 'parse';
    this._set(cur, { status: 'failed' });
    STAGES.forEach(([id]) => this.st[id].status === 'pending' && this._set(id, { status: 'skipped' }));
    this._stop();
    this.failed = true;
    this.el.classList.add('err');
    this.q('.cl-title').textContent = title;
    this.q('.cl-fail').hidden = false;
    this.q('.cl-fail-msg').textContent = message || '';
    this.q('.cl-hint').hidden = true;
    this._paint();
    this._actions(actions);
    this.q('.cl-actions .btn.primary')?.focus();
  }

  hide() {
    clearTimeout(this._hideT);
    this._stop();
    this.active = false;
    this.el.classList.remove('show');
    this.onHide?.();
    this._hideT = setTimeout(() => { this.el.hidden = true; }, 420);
  }

  _stop() {
    this.done = true;
    clearInterval(this._tick);
    this.q('.cl-time').textContent = fmtTime(performance.now() - this.t0);
  }

  _actions(list) {
    const box = this.q('.cl-actions');
    box.innerHTML = list.map(([id, label, primary]) => `<button class="btn small${primary ? ' primary' : ''}" data-act="${id}">${esc(label)}</button>`).join('');
    list.forEach(([id, , , fn]) => { box.querySelector(`[data-act="${id}"]`).onclick = fn || (() => this.onCancel?.()); });
  }

  _finishStage(id, t) {
    const s = this.st[id];
    s.frac = 1;
    if (s.count) s.count = [s.count[1], s.count[1]];
    if (t !== undefined) { s.dur = Math.max(0, t - this.lastServerT); this.lastServerT = t; }
    this._set(id, { status: 'done' });
    const next = STAGES[STAGES.findIndex(([x]) => x === id) + 1];
    if (next && this.st[next[0]].status === 'pending') this._set(next[0], { status: 'active' });
  }

  _set(id, patch) {
    const s = Object.assign(this.st[id], patch);
    const li = this.rows[id];
    li.className = s.status === 'pending' ? '' : s.status;
    if (s.status === 'active') {
      const [, label] = STAGES.find(([x]) => x === id);
      if (this.q('.cl-live').textContent !== label) this.q('.cl-live').textContent = label;
    }
  }

  _paint() {
    const pct = STAGES.reduce((sum, [id, , , w]) => sum + w * (this.st[id].status === 'skipped' && !this.failed ? 1 : this.st[id].frac), 0);
    const p = Math.min(100, Math.floor(pct));
    this.q('.cl-fill').style.transform = `scaleX(${pct / 100})`;
    this.q('.cl-pct').textContent = `${p}%`;
    this.q('.cl-bar').setAttribute('aria-valuenow', p);
    const placed = Math.round((pct / 100) * this.parts.length);
    this.parts.forEach((el, i) => el.classList.toggle('placed', i < placed));
    for (const [id, , unit] of STAGES) {
      const s = this.st[id];
      const det = this.rows[id].querySelector('.cl-det');
      det.textContent = s.status === 'done' && s.dur !== undefined ? fmtDur(s.dur)
        : s.status === 'active' && s.count && unit ? `${s.count[0]}/${s.count[1]}` : '';
    }
    const act = STAGES.find(([id]) => this.st[id].status === 'active');
    if (act && !this.done) {
      const [id, label, unit] = act;
      const c = this.st[id].count;
      this.q('.cl-sub').textContent = c && unit ? `${label} · ${unit} ${c[0]} of ${c[1]}` : `${label}…`;
    } else if (this.done) {
      this.q('.cl-sub').textContent = `${this.failed ? 'Stopped after' : 'Finished in'} ${fmtTime(performance.now() - this.t0)}`;
    }
  }
}
