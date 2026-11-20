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

function shapeFromComponent(comp) {
  const pts = comp.cut_outline;
  const shape = new THREE.Shape();
  pts.forEach(([x, y], i) => (i ? shape.lineTo(x, y) : shape.moveTo(x, y)));
  shape.closePath();
  for (const f of comp.features || []) {
    const hole = new THREE.Path();
    if (f.shape === 'circle') {
      hole.absarc(f.center[0], f.center[1], f.diameter / 2, 0, Math.PI * 2, true);
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

    this._bindPointer();
    new ResizeObserver(() => this.resize()).observe(container);
    this.resize();
    const loop = () => {
      requestAnimationFrame(loop);
      this.controls.update();
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

  _materials(comp) {
    const t = comp.thickness;
    const light = comp.color && parseInt(comp.color.slice(1), 16) > 0xd8d8d8;
    const map = (light ? this.sailTex : this.faceTex).clone();
    map.needsUpdate = true;
    map.repeat.set(1 / 160, 1 / 160);
    const face = new THREE.MeshStandardMaterial({ map, roughness: 0.78, metalness: 0,
      color: new THREE.Color(light ? '#ffffff' : '#ffffff') });
    const edgeMap = this.edgeTex.clone();
    edgeMap.needsUpdate = true;
    edgeMap.repeat.set(1 / 30, 1 / t);
    const side = new THREE.MeshStandardMaterial({ map: edgeMap, roughness: 0.9, metalness: 0,
      color: new THREE.Color(light ? '#f2ede4' : '#ffffff') });
    return [face, side];
  }

  load(model) {
    for (const it of this.items.values()) {
      it.mesh.geometry.dispose();
      it.mesh.material.forEach((m) => { m.map?.dispose(); m.dispose(); });
      it.edges.geometry.dispose();
      it.edges.material.dispose();
    }
    this.root.clear();
    this.items.clear();
    this.model = model;
    const c = model.bounds.center;
    this.center = new THREE.Vector3(...c);

    for (const comp of model.components) {
      const geo = new THREE.ExtrudeGeometry(shapeFromComponent(comp), { depth: comp.thickness, bevelEnabled: false, curveSegments: 32 });
      geo.translate(0, 0, -comp.thickness / 2);
      const mesh = new THREE.Mesh(geo, this._materials(comp));
      mesh.castShadow = mesh.receiveShadow = true;
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geo, 25),
        new THREE.LineBasicMaterial({ color: STATE_EDGE[comp.state] || STATE_EDGE.joined, transparent: true, opacity: 0.7 }));
      const inner = new THREE.Group();
      inner.matrixAutoUpdate = false;
      inner.matrix.fromArray(comp.matrix_world);
      inner.add(mesh, edges);
      const outer = new THREE.Group();
      outer.add(inner);
      outer.userData.id = comp.id;
      mesh.userData.id = comp.id;
      this.root.add(outer);
      const wc = new THREE.Vector3(...comp.world_bounds.min).add(new THREE.Vector3(...comp.world_bounds.max)).multiplyScalar(0.5);
      this.items.set(comp.id, { comp, mesh, edges, outer, dir: wc.sub(this.center) });
    }
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
    const step = 10, n = Math.ceil((r * 3) / step / 2) * 2;
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

  view(kind) {
    if (!this.model) return;
    // Fit the bounding sphere into the narrower of the vertical / horizontal fields of view
    const b = this.model.bounds;
    const sphere = new THREE.Vector3(...b.max).sub(new THREE.Vector3(...b.min)).length() / 2;
    const vfov = THREE.MathUtils.degToRad(this.camera.fov);
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * this.camera.aspect);
    const c = this.center, r = (sphere / Math.sin(Math.min(vfov, hfov) / 2)) * 1.08;
    const dirs = { iso: [1, 0.62, 1.05], front: [0, 0.12, 1], side: [1, 0.12, 0], top: [0, 1, 0.0001] };
    const d = new THREE.Vector3(...(dirs[kind] || dirs.iso)).normalize().multiplyScalar(r);
    this.camera.position.copy(c).add(d);
    this.controls.target.copy(c);
    this.camera.near = r / 100;
    this.camera.far = r * 50;
    this.camera.updateProjectionMatrix();
    this.controls.update();
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
      it.outer.position.copy(d.multiplyScalar(k));
    }
  }

  setEdges(on) {
    this.showEdges = on;
    for (const it of this.items.values()) it.edges.visible = on || it.comp.id === this.selected;
  }

  setSelected(id) {
    this.selected = id;
    for (const [cid, it] of this.items) {
      const sel = cid === id;
      it.mesh.material.forEach((m) => {
        m.emissive.setHex(sel ? 0x1d4ed8 : it.comp.state === 'error' ? 0x5a0d10 : 0x000000);
        m.emissiveIntensity = sel ? 0.32 : 0.25;
      });
      it.edges.material.color.setHex(sel ? SELECT_EDGE : STATE_EDGE[it.comp.state] || STATE_EDGE.joined);
      it.edges.material.opacity = sel ? 1 : 0.7;
      it.edges.visible = this.showEdges || sel;
    }
  }

  _pick(ev) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    const m = new THREE.Vector2(((ev.clientX - rect.left) / rect.width) * 2 - 1, -((ev.clientY - rect.top) / rect.height) * 2 + 1);
    this.raycaster.setFromCamera(m, this.camera);
    const hits = this.raycaster.intersectObjects([...this.items.values()].map((i) => i.mesh), false);
    return hits[0]?.object.userData.id || null;
  }

  _bindPointer() {
    const el = this.renderer.domElement;
    let down = null;
    el.addEventListener('pointerdown', (e) => (down = [e.clientX, e.clientY]));
    el.addEventListener('pointerup', (e) => {
      if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 4) this.onSelect?.(this._pick(e));
      down = null;
    });
    el.addEventListener('pointermove', (e) => { if (!down) this.onHover?.(this._pick(e), e); });
    el.addEventListener('pointerleave', () => this.onHover?.(null));
  }
}
