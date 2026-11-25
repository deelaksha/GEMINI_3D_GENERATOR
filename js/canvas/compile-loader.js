/**
 * Compile progress: one thin bar along the top of the 3D view, so the live assembly behind it stays fully visible
 * (assembly-preview.js). Errors are reported by the status pill, the Problems panel and a toast.
 *
 * Progress is driven only by the compiler's own stage events (see /canvas/compile-stream); each stage's share of
 * the bar is its measured share of compile time (collision checks dominate), and inside a stage the bar follows
 * the compiler's real item counts.
 */
const STAGES = [
  // id, share of the bar (%)
  ['parse', 2], ['geometry', 3], ['joints', 22], ['dimensions', 4], ['joint_validation', 4],
  ['collisions', 50], ['model', 5], ['render', 10]
];

export class CompileLoader {
  constructor(host) {
    this.host = host;
    this.el = document.createElement('div');
    this.el.className = 'cl-bar';
    this.el.hidden = true;
    this.el.setAttribute('role', 'progressbar');
    this.el.setAttribute('aria-label', 'Compile progress');
    this.el.setAttribute('aria-valuemin', '0');
    this.el.setAttribute('aria-valuemax', '100');
    this.el.innerHTML = '<div class="cl-fill"></div>';
    host.appendChild(this.el);
    this.fill = this.el.firstChild;
    this.active = false;
  }

  get busy() { return this.active && !this.done; }

  start() {
    clearTimeout(this._hideT);
    this.frac = Object.fromEntries(STAGES.map(([id]) => [id, 0]));
    this.active = true;
    this.done = false;
    this.el.className = 'cl-bar';
    this.el.hidden = false;
    this.host.classList.add('cl-busy');
    this._paint();
  }

  /** A {stage, done, total} event from the compiler. */
  progress({ stage, done, total }) {
    if (!this.busy) return;
    const i = STAGES.findIndex(([id]) => id === stage);
    if (i < 0) return;
    STAGES.slice(0, i).forEach(([id]) => { this.frac[id] = 1; });       // earlier stages are finished
    this.frac[stage] = total ? Math.min(1, done / total) : 1;
    this._paint();
  }

  /** Server work is finished; the page is building the 3D model. */
  rendering() {
    if (!this.busy) return;
    STAGES.slice(0, -1).forEach(([id]) => { this.frac[id] = 1; });
    this._paint();
  }

  /** Model on screen: fill the bar and fade it out at once (no waiting on animations). */
  complete() {
    if (!this.busy) return;
    this.frac.render = 1;
    this._paint();
    this.el.classList.add('ok');
    this.hide();
  }

  hide() {
    clearTimeout(this._hideT);
    this.done = true;
    this.active = false;
    this.host.classList.remove('cl-busy');
    this.el.classList.add('out');
    this._hideT = setTimeout(() => { this.el.hidden = true; }, 400);
  }

  _paint() {
    const pct = STAGES.reduce((sum, [id, w]) => sum + w * this.frac[id], 0);
    this.fill.style.transform = `scaleX(${pct / 100})`;
    this.el.setAttribute('aria-valuenow', Math.floor(pct));
  }
}
