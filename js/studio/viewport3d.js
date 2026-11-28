/**
 * 3D assembly viewport. Geometry comes straight from /model3d: each component's cut outline
 * (outline + tabs), its features as holes, its thickness, and the world matrix computed by the
 * backend — the renderer never re-derives transforms, so 2D, 3D and validation always agree.
 */
/* global THREE */

const STATE_EDGE = { joined: 0x3b2a18, cut: 0xf2a93b, error: 0xf0535b };
const SELECT_EDGE = 0x7fb2ff;

function woodTexture(base = '#d9b98b', seed = 1) {
  const c = document.createElement('canvas');
  c.width = 512; c.height = 512;
  const g = c.getContext('2d');
  g.fillStyle = base;
  g.fillRect(0, 0, 512, 512);
  let s = seed * 9301;
  const rnd = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
  for (let i = 0; i < 140; i++) {
    const y = rnd() * 512, amp = 2 + rnd() * 7, freq = 0.004 + rnd() * 0.01, a = 0.04 + rnd() * 0.08;
    g.strokeStyle = rnd() > 0.5 ? `rgba(110,72,36,${a})` : `rgba(255,240,215,${a * 0.8})`;
    g.lineWidth = 0.6 + rnd() * 2.2;
    g.beginPath();
    for (let x = 0; x <= 512; x += 8) g.lineTo(x, y + Math.sin(x * freq + i) * amp);
    g.stroke();
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.encoding = THREE.sRGBEncoding;
  t.anisotropy = 4;
  return t;
}

function plyEdgeTexture() {
  const c = document.createElement('canvas');
  c.width = 64; c.height = 64;
  const g = c.getContext('2d');
  const plies = 5;
  for (let i = 0; i < plies; i++) {
    g.fillStyle = i % 2 ? '#b98d5a' : '#e2c597';
    g.fillRect(0, (i * 64) / plies, 64, 64 / plies);
  }
  g.fillStyle = 'rgba(80,50,20,.35)';
  for (let i = 1; i < plies; i++) g.fillRect(0, (i * 64) / plies - 0.6, 64, 1.2);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.encoding = THREE.sRGBEncoding;
  return t;
}

export function shapeFromComponent(comp) {
  const pts = comp.cut_outline;
  const shape = new THREE.Shape();
  pts.forEach(([x, y], i) => (i ? shape.lineTo(x, y) : shape.moveTo(x, y)));
  shape.closePath();
  for (const f of comp.features || []) {
    const hole = new THREE.Path();
    if (f.shape === 'circle') {
      hole.absarc(f.center[0], f.center[1], f.diameter / 2, 0, Math.PI * 2, true);
    } else if (f.polygon) {
      f.polygon.forEach(([x, y], i) => (i ? hole.lineTo(x, y) : hole.moveTo(x, y)));
      hole.closePath();
    } else {
      const a = THREE.MathUtils.degToRad(f.angle || 0), ca = Math.cos(a), sa = Math.sin(a);
      const hw = f.width / 2, hh = f.height / 2;
      [[-hw, -hh], [-hw, hh], [hw, hh], [hw, -hh]].forEach(([lx, ly], i) => {
        const x = f.center[0] + lx * ca - ly * sa, y = f.center[1] + lx * sa + ly * ca;
        i ? hole.lineTo(x, y) : hole.moveTo(x, y);
      });
      hole.closePath();
    }
    shape.holes.push(hole);
  }
  return shape;
}

// Engraving / pockets: drawn on the +Z face (they do not cut through, so they are not holes)
const MARK_COLOR = { engrave: 0x1d4ed8, pocket: 0x15803d };
function marksFromComponent(comp) {
  const hinge = (comp.hinges || []).map((h) => {      // living-hinge cuts: drawn on both faces (bending is not simulated)
    const pts = [];
    for (const z of [comp.thickness / 2 + 0.05, -comp.thickness / 2 - 0.05]) {
      for (const [a, b] of h.lines) pts.push(new THREE.Vector3(a[0], a[1], z), new THREE.Vector3(b[0], b[1], z));
    }
    return new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: 0x7a1d1d }));
  });
  const images = (comp.images || []).map((im) => {     // raster engraving: its outline on the +z face
    const z = comp.thickness / 2 + 0.05;
    const [tl, tr, bl] = im.corners, br = [tr[0] + bl[0] - tl[0], tr[1] + bl[1] - tl[1]];
    const pts = [tl, tr, br, bl].map(([x, y]) => new THREE.Vector3(x, y, z));
    return new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: 0x1d4ed8 }));
  });
  return hinge.concat(images, (comp.marks || []).map((m) => {
    const z = comp.thickness / 2 + 0.05;
    const pts = m.points.map(([x, y]) => new THREE.Vector3(x, y, z));
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: MARK_COLOR[m.kind] });
    return m.closed ? new THREE.LineLoop(geo, mat) : new THREE.Line(geo, mat);
  }));
}

export class Viewport3D {
  constructor(container, { onSelect, onHover } = {}) {
    this.container = container;
    this.onSelect = onSelect;
    this.onHover = onHover;
    this.items = new Map();
    this.explode = 0;
    this.showEdges = true;
    this.selected = null;
    this.bounds = null;
    this.moveMode = false;            // drag a board to pull it out (Shift + drag works in any mode)
    this.pulled = new Map();          // board id -> pull offset kept across recompiles
    this.partners = new Set();

    const r = (this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true }));
    r.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    r.outputEncoding = THREE.sRGBEncoding;
    r.toneMapping = THREE.ACESFilmicToneMapping;
    r.toneMappingExposure = 1.05;
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.PCFSoftShadowMap;
    r.setClearColor(0x000000, 0);
    container.appendChild(r.domElement);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(35, 1, 1, 20000);
    this.controls = new THREE.OrbitControls(this.camera, r.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.screenSpacePanning = true;
    this.controls.rotateSpeed = 0.7;

    this.scene.add(new THREE.HemisphereLight(0xf3efe8, 0x3a3127, 0.75));
    const sun = (this.sun = new THREE.DirectionalLight(0xfff4e2, 1.15));
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.bias = -0.0004;
    sun.shadow.normalBias = 0.6;
    this.scene.add(sun, sun.target);
    const fill = new THREE.DirectionalLight(0xbcd3ff, 0.35);
    fill.position.set(-1, 0.6, -1);
    this.scene.add(fill);

    this.ground = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.ShadowMaterial({ opacity: 0.28 }));
    this.ground.rotation.x = -Math.PI / 2;
    this.ground.receiveShadow = true;
    this.scene.add(this.ground);
    this.grid = null;

    this.root = new THREE.Group();
    this.scene.add(this.root);
    this.faceTex = woodTexture();
    this.sailTex = woodTexture('#efe8dc', 7);
    this.edgeTex = plyEdgeTexture();
    this.raycaster = new THREE.Raycaster();
    this.links = new THREE.Group();   // joint lines of the board that is pulled out
    this.links.renderOrder = 10;
    this.scene.add(this.links);
    this.info = document.createElement('div');
    this.info.className = 'pull-info';
    this.info.hidden = true;
    container.appendChild(this.info);

    this._bindPointer();
    new ResizeObserver(() => this.resize()).observe(container);
    this.resize();
    // Draw only when something changed (camera, a method call, a resize): redrawing an unchanged scene every frame
    // kept the page too busy to respond once a design had thousands of boards.
    this._dirty = true;
    this.controls.addEventListener('change', () => { this._dirty = true; });
    const loop = () => {
      requestAnimationFrame(loop);
      if (this.controls.update()) this._dirty = true;      // still gliding (damping)
      if (this.playing) this._motionTick(performance.now());
      if (!this._dirty) return;
      this._dirty = false;
      r.render(this.scene, this.camera);
    };
    loop();
  }

  resize() {
    const w = this.container.clientWidth || 1, h = this.container.clientHeight || 1;
    this.renderer.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  /** Painted finish (colouring on): one material per face - front (+z), back (-z), edges. */
  _paint(geo, colors) {
    const pos = geo.attributes.position, nrm = geo.attributes.normal;
    geo.clearGroups();
    let start = 0, cur = -1;
    for (let i = 0; i < pos.count; i += 3) {          // non-indexed: one triangle per 3 vertices
      const z = (nrm.getZ(i) + nrm.getZ(i + 1) + nrm.getZ(i + 2)) / 3;
      const m = z > 0.5 ? 0 : z < -0.5 ? 1 : 2;
      if (m !== cur) {
        if (cur >= 0) geo.addGroup(start, i - start, cur);
        start = i;
        cur = m;
      }
    }
    if (cur >= 0) geo.addGroup(start, pos.count - start, cur);
    // the renderer shades in linear light and outputs sRGB: convert so a paint colour shows as its own hex value
    return ['front', 'back', 'edges'].map((k) => new THREE.MeshStandardMaterial({
      color: new THREE.Color(colors[k]).convertSRGBToLinear(), roughness: 0.62, metalness: 0 }));
  }

  /** Printed decals (colouring on): each decorated face gets its own texture - the face colour with the artwork drawn
   *  on it in the part's local millimetres, which is what the extruded faces use as texture coordinates. */
  _decalMaterials(geo, comp) {
    const NATURAL = '#d9b98b';
    const colors = comp.colors || { front: NATURAL, back: NATURAL, edges: NATURAL };
    const mats = this._paint(geo, colors);                    // front (+z), back, edges
    const pts = comp.cut_outline || comp.outline;
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const x0 = Math.min(...xs), y0 = Math.min(...ys);
    const w = Math.max(...xs) - x0 || 1, h = Math.max(...ys) - y0 || 1;
    const s = Math.min(6, 2048 / Math.max(w, h));             // pixels per mm, at most 2048 px a side
    ['front', 'back'].forEach((face, i) => {
      const ds = comp.decals.filter((d) => d.face === face);
      if (!ds.length) return;
      const cv = document.createElement('canvas');
      cv.width = Math.max(2, Math.ceil(w * s));
      cv.height = Math.max(2, Math.ceil(h * s));
      const g = cv.getContext('2d');
      g.fillStyle = colors[face];
      g.fillRect(0, 0, cv.width, cv.height);
      const P = ([x, y]) => [(x - x0) * s, (y0 + h - y) * s];
      for (const d of ds) {
        g.fillStyle = g.strokeStyle = d.color;
        if (d.points) {
          g.beginPath();
          d.points.forEach((q, k) => (k ? g.lineTo(...P(q)) : g.moveTo(...P(q))));
          g.closePath();
          g.fill();
        } else {
          g.lineWidth = d.width * s;
          g.lineCap = g.lineJoin = 'round';
          for (const ln of d.lines) {
            g.beginPath();
            ln.forEach((q, k) => (k ? g.lineTo(...P(q)) : g.moveTo(...P(q))));
            g.stroke();
          }
        }
      }
      const tex = new THREE.CanvasTexture(cv);
      tex.encoding = THREE.sRGBEncoding;
      tex.anisotropy = 4;
      tex.repeat.set(1 / w, 1 / h);
      tex.offset.set(-x0 / w, -y0 / h);
      tex.name = 'decal';                                      // this board's alone: disposed with it (r128: no userData)
      mats[i].map = tex;
      mats[i].color.set('#ffffff');
    });
    return mats;
  }

  _materials(comp) {
    const t = comp.thickness;
    const light = comp.color && parseInt(comp.color.slice(1), 16) > 0xd8d8d8;
    // textures are shared (one per finish and thickness): a copy per board meant thousands of texture uploads
    const map = this._sharedMap(light ? 'sail' : 'face', () => {
      const m = (light ? this.sailTex : this.faceTex).clone();
      m.repeat.set(1 / 160, 1 / 160);
      return m;
    });
    const face = new THREE.MeshStandardMaterial({ map, roughness: 0.78, metalness: 0,
      color: new THREE.Color(light ? '#ffffff' : '#ffffff') });
    const edgeMap = this._sharedMap(`edge:${t}`, () => {
      const m = this.edgeTex.clone();
      m.repeat.set(1 / 30, 1 / t);
      return m;
    });
    const side = new THREE.MeshStandardMaterial({ map: edgeMap, roughness: 0.9, metalness: 0,
      color: new THREE.Color(light ? '#f2ede4' : '#ffffff') });
    return [face, side];
  }

  _sharedMap(key, make) {
    this._maps ??= new Map();
    if (!this._maps.has(key)) {
      const m = make();
      m.needsUpdate = true;
      this._maps.set(key, m);
    }
    return this._maps.get(key);
  }

  load(model) {
    for (const it of this.items.values()) {
      it.mesh.geometry.dispose();
      it.mesh.material.forEach((m) => { if (m.map?.name === 'decal') m.map.dispose(); m.dispose(); });  // shared textures stay
      it.edges.geometry.dispose();
      it.edges.material.dispose();
      it.marks?.forEach((m) => { m.geometry.dispose(); m.material.dispose(); });
      if (it.pull.lengthSq() > 0) this.pulled.set(it.comp.id, it.pull.clone());
    }
    this.root.clear();
    this.items.clear();
    this.model = model;
    this.motions = model.motions || [];
    this.playing = false;
    const c = model.bounds.center;
    this.center = new THREE.Vector3(...c);

    const shadows = model.components.length <= 4000;      // a shadow pass doubles the drawing of a huge model
    for (const comp of model.components) {
      const geo = new THREE.ExtrudeGeometry(shapeFromComponent(comp), { depth: comp.thickness, bevelEnabled: false, curveSegments: 32 });
      geo.translate(0, 0, -comp.thickness / 2);
      const mesh = new THREE.Mesh(geo, comp.decals?.length ? this._decalMaterials(geo, comp)
        : comp.colors ? this._paint(geo, comp.colors) : this._materials(comp));
      mesh.castShadow = mesh.receiveShadow = shadows;
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geo, 25),
        new THREE.LineBasicMaterial({ color: STATE_EDGE[comp.state] || STATE_EDGE.joined, transparent: true, opacity: 0.7 }));
      const inner = new THREE.Group();
      inner.matrixAutoUpdate = false;
      inner.matrix.fromArray(comp.matrix_world);
      inner.add(mesh, edges);
      const marks = marksFromComponent(comp);
      if (marks.length) inner.add(...marks);
      const outer = new THREE.Group();
      outer.add(inner);
      outer.userData.id = comp.id;
      mesh.userData.id = comp.id;
      this.root.add(outer);
      const wc = new THREE.Vector3(...comp.world_bounds.min).add(new THREE.Vector3(...comp.world_bounds.max)).multiplyScalar(0.5);
      this.items.set(comp.id, { comp, mesh, edges, marks, outer, dir: wc.sub(this.center), base: new THREE.Vector3(),
        pull: (this.pulled.get(comp.id) || new THREE.Vector3()).clone(), matrix: inner.matrix.clone() });
    }
    this.pulled.clear();
    this.jointPts = (model.joints || []).filter((j) => this.items.has(j.a) && this.items.has(j.b)).map((j) => ({ j, p: this._jointPoint(j) }));
    this._stage(model.bounds);
    this.setExplode(this.explode);
    this.setSelected(this.selected);
  }

  _stage(b) {
    const size = new THREE.Vector3(...b.max).sub(new THREE.Vector3(...b.min));
    const r = Math.max(size.x, size.y, size.z, 50);
    this.radius = r;
    const floor = b.min[1] - 0.2;
    this.ground.scale.set(r * 8, r * 8, 1);
    this.ground.position.set(b.center[0], floor, b.center[2]);
    if (this.grid) this.scene.remove(this.grid);
    const step = r > 1500 ? 100 : r > 500 ? 50 : 10, n = Math.ceil((r * 3) / step / 2) * 2;   // keep the grid readable at furniture scale
    this.grid = new THREE.GridHelper(n * step, n, 0x56606e, 0x2e3540);
    this.grid.material.transparent = true;
    this.grid.material.opacity = 0.35;
    this.grid.position.set(b.center[0], floor - 0.05, b.center[2]);
    this.scene.add(this.grid);
    const s = this.sun;
    s.position.set(b.center[0] + r * 0.9, b.center[1] + r * 1.6, b.center[2] + r * 0.7);
    s.target.position.set(...b.center);
    const cam = s.shadow.camera;
    cam.left = cam.bottom = -r * 1.2;
    cam.right = cam.top = r * 1.2;
    cam.near = 1;
    cam.far = r * 6;
    cam.updateProjectionMatrix();
    if (!this._framed) { this.view('iso'); this._framed = true; }
  }

  view(kind, b = this.model?.bounds) {
    if (!b) return;
    // Fit the bounding sphere into the narrower of the vertical / horizontal fields of view
    const sphere = new THREE.Vector3(...b.max).sub(new THREE.Vector3(...b.min)).length() / 2;
    const vfov = THREE.MathUtils.degToRad(this.camera.fov);
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * this.camera.aspect);
    const c = new THREE.Vector3(...b.center), r = (sphere / Math.sin(Math.min(vfov, hfov) / 2)) * 1.08;
    const dirs = { iso: [1, 0.62, 1.05], front: [0, 0.12, 1], side: [1, 0.12, 0], top: [0, 1, 0.0001] };
    const d = new THREE.Vector3(...(dirs[kind] || dirs.iso)).normalize().multiplyScalar(r);
    this.camera.position.copy(c).add(d);
    this.controls.target.copy(c);
    this.camera.near = r / 100;
    this.camera.far = r * 50;
    this.camera.updateProjectionMatrix();
    this.controls.update();
  }

  /** JPEG data URLs of the model from standard viewpoints (for the AI visual check); the camera is put back after. */
  snapshots(kinds = ['iso', 'front', 'side', 'top'], quality = 0.8) {
    if (!this.model) return [];
    const pos = this.camera.position.clone(), target = this.controls.target.clone();
    const shots = kinds.map((k) => {
      this.view(k);
      this.renderer.render(this.scene, this.camera);
      return this.renderer.domElement.toDataURL('image/jpeg', quality);
    });
    this.camera.position.copy(pos);
    this.controls.target.copy(target);
    this.controls.update();
    return shots;
  }

  focus(id) {
    const it = this.items.get(id);
    if (!it) return;
    const b = new THREE.Box3().setFromObject(it.outer);
    const c = b.getCenter(new THREE.Vector3());
    const offset = this.camera.position.clone().sub(this.controls.target);
    this.controls.target.copy(c);
    this.camera.position.copy(c).add(offset.setLength(Math.max(b.getSize(new THREE.Vector3()).length() * 2.5, this.radius * 1.2)));
  }

  focusPoint(p) {
    const offset = this.camera.position.clone().sub(this.controls.target);
    this.controls.target.set(...p);
    this.camera.position.copy(this.controls.target).add(offset.setLength(this.radius * 0.9));
  }

  setExplode(f) {
    this.explode = f;
    const k = f * this.radius * 0.45;
    for (const it of this.items.values()) {
      const d = it.dir.lengthSq() > 1e-6 ? it.dir.clone().normalize() : new THREE.Vector3(0, 1, 0);
      it.base.copy(d.multiplyScalar(k));
      this._place(it);
    }
    this._showLinks();
  }

  /** A board's group: exploded offset + pulled-out offset + its motion (turned about a pivot or slid). */
  _place(it) {
    it.outer.quaternion.copy(it.motionTurn || new THREE.Quaternion());
    it.outer.position.copy(it.base).add(it.pull);
    if (it.motionShift) it.outer.position.add(it.motionShift);
  }

  /** Animate every motion of the model (lids open, wheels turn, drawers slide) or put them back at rest. */
  playMotion(on) {
    this.playing = !!on && !!this.motions?.length;
    this._motionStart = performance.now();
    if (!this.playing) this._pose(() => 0);
  }

  _motionTick(now) {
    // rest -> one end of the range -> the other end -> rest, about 1.5 s per 90 degrees or 100 mm; a crank whose
    // rod jams turns only as far as the linkage can follow (jam_range), so no rod is drawn in an impossible pose
    this._pose((m) => {
      const [a, b] = m.jam_range || m.range, path = [0, b, a, 0].filter((v, i, l) => i === 0 || v !== l[i - 1]);
      const legs = path.slice(1).map((v, i) => Math.abs(v - path[i]));
      const total = legs.reduce((s, x) => s + x, 0) || 1;
      const per = m.type === 'rotate' ? 90 : 100;
      let d = (((now - this._motionStart) / 1500) * per) % total;
      for (let i = 0; i < legs.length; i += 1) {
        if (d <= legs[i]) return path[i] + (path[i + 1] - path[i]) * (legs[i] ? d / legs[i] : 0);
        d -= legs[i];
      }
      return 0;
    });
  }

  _pose(valueOf) {
    // a driven motion follows its driver: at its ratio (a gear train, a belt) or through its connecting rod (the
    // engine solved the linkage into a table); a motion mounted on a moving board rides on it (a jaw on a head)
    const ms = this.motions || [], byId = new Map(ms.map((m) => [m.id, m])), memo = new Map(), frames = new Map();
    const interp = (table, x) => {
      if (x <= table[0][0]) return table[0][1];
      for (let i = 1; i < table.length; i += 1) {
        const [x0, y0] = table[i - 1], [x1, y1] = table[i];
        if (x <= x1) return y0 + (y1 - y0) * ((x - x0) / (x1 - x0 || 1));
      }
      return table[table.length - 1][1];
    };
    const value = (m) => {
      if (!memo.has(m.id)) {
        const d = m.driven_by && byId.get(m.driven_by);
        memo.set(m.id, !d ? valueOf(m) : m.link ? interp(m.link.table, value(d)) : value(d) * m.ratio);
      }
      return memo.get(m.id);
    };
    const local = (m, v) => {      // x -> q x + t
      if (m.type !== 'rotate') return { q: new THREE.Quaternion(), t: new THREE.Vector3(...m.direction).multiplyScalar(v) };
      const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(...m.axis), THREE.MathUtils.degToRad(v));
      const p = new THREE.Vector3(...m.pivot);
      return { q, t: p.clone().sub(p.clone().applyQuaternion(q)) };    // turn about the pivot, not the origin
    };
    const at = (f, x) => new THREE.Vector3(...x).applyQuaternion(f.q).add(f.t);
    const then = (a, b) => ({ q: a.q.clone().multiply(b.q), t: b.t.clone().applyQuaternion(a.q).add(a.t) });
    const frame = (id) => {
      const m = id && byId.get(id);
      if (!m) return { q: new THREE.Quaternion(), t: new THREE.Vector3() };
      if (!frames.has(id)) frames.set(id, then(frame(m.parent), local(m, value(m))));
      return frames.get(id);
    };
    const rod = (m) => {           // the rod turns in its crank's plane to span its two pins
      const d = byId.get(m.driven_by), a = new THREE.Vector3(...d.axis);
      const P = at(local(d, value(d)), m.link.from), Q = at(local(m, value(m)), m.link.to);
      const flat = (v) => v.clone().sub(a.clone().multiplyScalar(v.dot(a)));
      const u0 = flat(new THREE.Vector3(...m.link.to).sub(new THREE.Vector3(...m.link.from))), u1 = flat(Q.clone().sub(P));
      const q = new THREE.Quaternion().setFromAxisAngle(a, Math.atan2(u0.clone().cross(u1).dot(a), u0.dot(u1)));
      return then(frame(m.parent), { q, t: P.sub(new THREE.Vector3(...m.link.from).applyQuaternion(q)) });
    };
    const put = (id, f) => {
      const it = this.items.get(id);
      if (!it) return;
      it.motionTurn = f.q;
      it.motionShift = f.t;
      this._place(it);
    };
    for (const m of ms) {
      for (const id of m.boards) put(id, frame(m.id));
      if (m.link && byId.has(m.driven_by)) put(m.link.rod, rod(m));
    }
  }

  /** World point where a joint sits at rest: the centre of its slot in the receiving board, else the middle of the
   *  overlap of the two boards' boxes (finger, cross-lap and hinge joints). */
  _jointPoint(j) {
    const b = this.items.get(j.b), a = this.items.get(j.a);
    const f = j.slot && b.comp.features?.find((x) => x.id === j.slot);
    if (f?.center) return new THREE.Vector3(f.center[0], f.center[1], 0).applyMatrix4(b.matrix);
    const lo = (c) => new THREE.Vector3(...c.world_bounds.min), hi = (c) => new THREE.Vector3(...c.world_bounds.max);
    return lo(a.comp).max(lo(b.comp)).add(hi(a.comp).min(hi(b.comp))).multiplyScalar(0.5);
  }

  /** Pull one board out of the assembly (offset in mm, world axes) or put it back (null). */
  setPull(id, v) {
    const it = this.items.get(id);
    if (!it) return;
    it.pull.copy(v || new THREE.Vector3());
    this._place(it);
    this._showLinks();
  }

  resetPulls() {
    for (const it of this.items.values()) it.pull.set(0, 0, 0);
    this.setExplode(this.explode);
  }

  setMoveMode(on) {
    this.moveMode = on;
    this.renderer.domElement.style.cursor = on ? 'grab' : '';
  }

  /** Lines from each joint of the pulled-out (else the selected) board to where it plugs into its partner. */
  _showLinks() {
    this.links.children.forEach((o) => { o.geometry.dispose(); o.material.dispose(); });
    this.links.clear();
    const out = [...this.items.values()].filter((it) => it.pull.lengthSq() > 0.01);
    const focus = this.items.get(this.dragging?.id) || out.find((it) => it.comp.id === this.selected) || out[out.length - 1];
    const prev = [...this.partners].join();
    this.partners = new Set();
    if (!focus) {
      this.info.hidden = true;
      if (prev) this.setSelected(this.selected);
      return;
    }
    const id = focus.comp.id, pos = [], col = [], rows = [];
    const ok = new THREE.Color(0x22c55e), bad = new THREE.Color(0xef4444);
    for (const { j, p } of this.jointPts) {
      if (j.a !== id && j.b !== id) continue;
      const other = j.a === id ? j.b : j.a, o = this.items.get(other);
      const pa = p.clone().add(focus.base).add(focus.pull), pb = p.clone().add(o.base).add(o.pull);
      const c = j.status === 'joined' ? ok : bad;
      pos.push(...pa.toArray(), ...pb.toArray());
      col.push(c.r, c.g, c.b, c.r, c.g, c.b);
      this.partners.add(other);
      rows.push({ other, type: j.type, status: j.status });
    }
    if (pos.length) {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
      g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
      const lines = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ vertexColors: true, depthTest: false, transparent: true }));
      const dots = new THREE.Points(g.clone(), new THREE.PointsMaterial({ vertexColors: true, size: 7, sizeAttenuation: false, depthTest: false }));
      lines.renderOrder = dots.renderOrder = 10;
      this.links.add(lines, dots);
    }
    const seen = new Map();
    for (const r of rows) {
      const k = `${r.other}|${r.type}|${r.status}`;
      seen.set(k, { ...r, n: (seen.get(k)?.n || 0) + 1 });
    }
    const esc = (t) => String(t).replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
    this.info.innerHTML = `<b>${esc(id)}</b> — ${rows.length ? `${rows.length} joint${rows.length === 1 ? '' : 's'}` : 'no joints: not attached to anything'}`
      + [...seen.values()].map((r) => `<div class="${r.status === 'joined' ? 'ok' : 'bad'}">${r.status === 'joined' ? '●' : '✕'} ${esc(r.other)} · ${esc(r.type)}${r.n > 1 ? ` ×${r.n}` : ''} · ${esc(r.status)}</div>`).join('')
      + '<div class="hint">Double-click a board to put it back</div>';
    this.info.hidden = false;
    if ([...this.partners].join() !== prev) this.setSelected(this.selected);
  }

  setEdges(on) {
    this.showEdges = on;
    for (const it of this.items.values()) it.edges.visible = on || it.comp.id === this.selected;
  }

  setSelected(id) {
    const changed = id !== this.selected;
    this.selected = id;
    if (changed && !this._linking && [...this.items.values()].some((it) => it.pull.lengthSq() > 0.01)) {
      this._linking = true;           // the pulled-out board whose joints are shown follows the selection
      this._showLinks();
      this._linking = false;
    }
    for (const [cid, it] of this.items) {
      const sel = cid === id, partner = this.partners.has(cid);
      it.mesh.material.forEach((m) => {
        m.emissive.setHex(sel ? 0x1d4ed8 : partner ? 0x0f766e : it.comp.state === 'error' ? 0x5a0d10 : 0x000000);
        m.emissiveIntensity = sel ? 0.32 : partner ? 0.35 : 0.25;
      });
      it.edges.material.color.setHex(sel ? SELECT_EDGE : STATE_EDGE[it.comp.state] || STATE_EDGE.joined);
      it.edges.material.opacity = sel ? 1 : 0.7;
      it.edges.visible = this.showEdges || sel;
    }
  }

  _ray(ev) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    const m = new THREE.Vector2(((ev.clientX - rect.left) / rect.width) * 2 - 1, -((ev.clientY - rect.top) / rect.height) * 2 + 1);
    this.raycaster.setFromCamera(m, this.camera);
    return this.raycaster;
  }

  _hit(ev) {
    return this._ray(ev).intersectObjects([...this.items.values()].map((i) => i.mesh), false)[0] || null;
  }

  _pick(ev) {
    return this._hit(ev)?.object.userData.id || null;
  }

  _bindPointer() {
    const el = this.renderer.domElement;
    let down = null;
    // capture phase: a drag that pulls a board must start before the orbit controls see the press
    el.addEventListener('pointerdown', (e) => {
      down = [e.clientX, e.clientY];
      if (e.button !== 0 || !(this.moveMode || e.shiftKey)) return;
      const hit = this._hit(e);
      if (!hit) return;
      e.stopImmediatePropagation();
      const id = hit.object.userData.id, it = this.items.get(id);
      const normal = this.camera.getWorldDirection(new THREE.Vector3());
      this.dragging = { id, plane: new THREE.Plane().setFromNormalAndCoplanarPoint(normal, hit.point), start: hit.point.clone(),
        pull: it.pull.clone() };
      el.setPointerCapture(e.pointerId);
      el.style.cursor = 'grabbing';
      this.onSelect?.(id);
    }, { capture: true });
    el.addEventListener('pointermove', (e) => {
      if (this.dragging) {
        const p = this._ray(e).ray.intersectPlane(this.dragging.plane, new THREE.Vector3());
        if (p) this.setPull(this.dragging.id, this.dragging.pull.clone().add(p.sub(this.dragging.start)));
        return;
      }
      if (!down) this.onHover?.(this._pick(e), e);
    });
    el.addEventListener('pointerup', (e) => {
      if (this.dragging) {
        this.dragging = null;
        el.style.cursor = this.moveMode ? 'grab' : '';
        this._showLinks();
      } else if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 4) this.onSelect?.(this._pick(e));
      down = null;
    });
    el.addEventListener('dblclick', (e) => {
      const id = this._pick(e);
      if (id && this.items.get(id).pull.lengthSq() > 0) this.setPull(id, null);
    });
    el.addEventListener('pointerleave', () => this.onHover?.(null));
  }
}

// Any method may change what is shown: ask for a fresh frame whenever one runs (the loop draws only on request).
for (const name of Object.getOwnPropertyNames(Viewport3D.prototype)) {
  const fn = Viewport3D.prototype[name];
  if (name === 'constructor' || typeof fn !== 'function') continue;
  Viewport3D.prototype[name] = function (...args) {
    this._dirty = true;
    return fn.apply(this, args);
  };
}
