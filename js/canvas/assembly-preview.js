/**
 * Live assembly preview, drawn in the canvas's own 3D viewport while a design compiles.
 *
 * Geometry is the compiler's: after geometry generation the server streams each board's outline, cut-outs and
 * placement matrix, and the compile worker turns them into merged world-space buffers with the viewport's own
 * shape builder. Every board is in one mesh and one line set (two draw calls for any number of boards); the
 * per-board state lives in a vertex attribute (placed-at time, highlight time, error) and the fly-in / highlight
 * animation runs in the shader, so a state change costs one batched attribute upload per frame at most.
 *
 * Pending boards are wireframes at their final place; a board is assembled (flies in and turns solid) when the
 * compiler joins it; boards being joined or checked light up; boards with errors turn red.
 */
/* global THREE */

const PENDING = 1e6;
const JOINS = 'joints';

const SOLID_VS = `
attribute vec3 aDir; attribute vec3 aState;
uniform float uTime; uniform float uDur;
varying vec3 vNormal; varying float vShow; varying float vHi; varying float vErr;
void main() {
  float t = clamp((uTime - aState.x) / uDur, 0.0, 1.0);
  float e = 1.0 - pow(1.0 - t, 3.0);
  vShow = step(aState.x, uTime);
  vHi = exp(-max(uTime - aState.y, 0.0) * 3.0);
  vErr = aState.z;
  vNormal = normalize(normalMatrix * normal);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position + aDir * (1.0 - e), 1.0);
}`;
const SOLID_FS = `
uniform vec3 uWood; uniform vec3 uHi; uniform vec3 uErr;
varying vec3 vNormal; varying float vShow; varying float vHi; varying float vErr;
void main() {
  if (vShow < 0.5) discard;
  float light = 0.5 + 0.5 * max(dot(normalize(vNormal), normalize(vec3(0.35, 0.85, 0.55))), 0.0);
  vec3 c = mix(uWood, uErr, vErr) * light;
  gl_FragColor = vec4(mix(c, uHi, vHi * 0.6), 1.0);
}`;
const LINE_VS = `
attribute vec3 aDir; attribute vec3 aState;
uniform float uTime; uniform float uDur;
varying float vPending; varying float vHi; varying float vErr;
void main() {
  float shown = step(aState.x, uTime);
  float e = 1.0 - pow(1.0 - clamp((uTime - aState.x) / uDur, 0.0, 1.0), 3.0);
  vPending = 1.0 - shown;
  vHi = exp(-max(uTime - aState.y, 0.0) * 3.0);
  vErr = aState.z;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position + aDir * (1.0 - e) * shown, 1.0);
}`;
const LINE_FS = `
uniform vec3 uWire; uniform vec3 uEdge; uniform vec3 uHi; uniform vec3 uErr;
varying float vPending; varying float vHi; varying float vErr;
void main() {
  vec3 c = mix(mix(uEdge, uWire, vPending), uHi, vHi);
  gl_FragColor = vec4(mix(c, uErr, vErr), max(mix(0.35, 0.55, vPending), vHi));
}`;

export class AssemblyPreview {
  constructor(viewport) {
    this.v = viewport;
    this.active = false;
    this.group = null;
  }

  get shown() { return !!this.group; }

  /** A compile started: clear the stage and remember everything that happens until the geometry arrives. */
  begin() {
    this.end();
    this.active = true;
    this.t0 = performance.now();
    this.placedAt = new Map();
    this.hiAt = new Map();
    this.errors = new Set();
    this.joins = null;
    this.index = null;
    this.allPlaced = false;
    this.v.root.visible = false;            // the previous model makes way for the new design
  }

  /** Preview buffers from the compile worker. */
  show(p) {
    if (!this.active || this.group) return;
    const n = p.ids.length;
    this.index = new Map(p.ids.map((id, i) => [id, i]));
    this.ranges = { solid: p.solid, lines: p.lines };
    this.dur = Math.max(0.25, Math.min(0.8, 0.85 - n * 0.002));     // quicker fly-ins for bigger assemblies
    this.uniforms = { uTime: { value: 0 }, uDur: { value: this.dur }, uWood: { value: new THREE.Color(0xd9b98b) },
      uHi: { value: new THREE.Color(0x6aa1ff) }, uErr: { value: new THREE.Color(0xf2555d) },
      uWire: { value: new THREE.Color(0x6aa1ff) }, uEdge: { value: new THREE.Color(0x3b2a18) } };
    const solid = new THREE.BufferGeometry();
    solid.setAttribute('position', new THREE.BufferAttribute(p.pos, 3));
    solid.setAttribute('normal', new THREE.BufferAttribute(p.nrm, 3));
    solid.setAttribute('aDir', new THREE.BufferAttribute(p.dir, 3));
    solid.setAttribute('aState', new THREE.BufferAttribute(new Float32Array(p.pos.length), 3).setUsage(THREE.DynamicDrawUsage));
    const lines = new THREE.BufferGeometry();
    lines.setAttribute('position', new THREE.BufferAttribute(p.lpos, 3));
    lines.setAttribute('aDir', new THREE.BufferAttribute(p.ldir, 3));
    lines.setAttribute('aState', new THREE.BufferAttribute(new Float32Array(p.lpos.length), 3).setUsage(THREE.DynamicDrawUsage));
    this.group = new THREE.Group();
    this.group.add(
      new THREE.Mesh(solid, new THREE.ShaderMaterial({ uniforms: this.uniforms, vertexShader: SOLID_VS, fragmentShader: SOLID_FS })),
      new THREE.LineSegments(lines, new THREE.ShaderMaterial({ uniforms: this.uniforms, vertexShader: LINE_VS,
        fragmentShader: LINE_FS, transparent: true, depthWrite: false })));
    this.group.children.forEach((o) => { o.frustumCulled = false; });   // vertices move in the shader
    this.solidState = solid.attributes.aState;
    this.lineState = lines.attributes.aState;
    this.v.scene.add(this.group);
    this.v.renderer.shadowMap.autoUpdate = false;     // the preview casts no shadows: skip that pass while it shows
    // camera, grid and light follow this design's size; a slow turn shows it from every side
    this.v._framed = true;
    this.v._stage(p.bounds);
    this.v.view('iso', p.bounds);
    this.v.controls.autoRotate = !matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.v.controls.autoRotateSpeed = 1.4;
    this.dirty = new Set(p.ids);
    if (this.allPlaced) this.placeAll();
    this._tick();
  }

  /** A progress event from the compiler (see /canvas/compile-stream). */
  event(ev) {
    if (!this.active) return;
    if (ev.joins) this.joins = ev.joins;
    const now = this._now();
    if (ev.stage === JOINS && this.joins) {
      for (let i = 0; i < Math.min(ev.done, this.joins.length); i++) this.joins[i].forEach((id) => this._place(id, now));
      if (ev.done < ev.total) this._highlight(this.joins[ev.done], now);
    }
    const order = ['parse', 'geometry', JOINS];
    if (!this.allPlaced && (!order.includes(ev.stage) || (ev.stage === JOINS && ev.done >= ev.total))) this.placeAll();
    if (ev.board) this._highlight([ev.board], now);
    if (ev.a && ev.b) this._highlight([ev.a, ev.b], now);
  }

  /** Every board assembled, quickly staggered so a large design does not appear in one jump. */
  placeAll() {
    this.allPlaced = true;
    if (!this.index) return;               // applied when the geometry arrives
    const now = this._now();
    const ids = [...this.index.keys()];
    const step = Math.min(0.04, 1.2 / Math.max(ids.length, 1));
    let k = 0;
    for (const id of ids) if (!this.placedAt.has(id)) this._place(id, now + step * k++);
  }

  /** Boards the compiler reported errors on turn red (the design stays visible behind the failure panel). */
  markErrors(ids) {
    ids.forEach((id) => { this.errors.add(id); this.dirty?.add(id); });
  }

  /** Remove the preview and give the viewport back to the real model. */
  end() {
    this.active = false;
    cancelAnimationFrame(this._raf);
    if (this.group) {
      this.v.scene.remove(this.group);
      this.group.children.forEach((o) => { o.geometry.dispose(); o.material.dispose(); });
      this.group = null;
    }
    if (this.v.controls) this.v.controls.autoRotate = false;
    this.v.renderer.shadowMap.autoUpdate = true;
    this.v.root.visible = true;
  }

  _now() { return (performance.now() - this.t0) / 1000; }

  _place(id, t) {
    if (this.placedAt.has(id)) return;
    this.placedAt.set(id, t);
    this.dirty?.add(id);
  }

  _highlight(ids, t) {
    ids.forEach((id) => { this.hiAt.set(id, t); this.dirty?.add(id); });
  }

  // one batched attribute upload per frame, however many events arrived
  _tick() {
    this._raf = requestAnimationFrame(() => this._tick());
    this.uniforms.uTime.value = this._now();
    if (!this.dirty.size) return;
    for (const id of this.dirty) {
      const i = this.index.get(id);
      if (i === undefined) continue;
      const st = [this.placedAt.get(id) ?? PENDING, this.hiAt.get(id) ?? -PENDING, this.errors.has(id) ? 1 : 0];
      for (const [attr, [start, count]] of [[this.solidState, this.ranges.solid[i]], [this.lineState, this.ranges.lines[i]]]) {
        const a = attr.array;
        for (let k = start * 3; k < (start + count) * 3; k += 3) { a[k] = st[0]; a[k + 1] = st[1]; a[k + 2] = st[2]; }
      }
    }
    this.dirty.clear();
    this.solidState.needsUpdate = this.lineState.needsUpdate = true;
  }
}
