/**
 * Universal 3D Assembly Engine (Three.js)
 * Completely generic: Renders any ConstructionObject without hardcoded models.
 */
import { GeometryEngine } from '../core/geometry.js';
import { ExplodeEngine } from './explode.js';
import { AssemblySequencer } from './sequencer.js';
import { AppState } from '../core/config.js';

export class Engine3D {
  constructor(containerElement, onPartSelected) {
    this.container = containerElement;
    this.onPartSelected = onPartSelected;

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.rootGroup = null;
    this.meshMap = new Map();

    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    this.isMouseDown = false;
    this.mouseX = 0;
    this.mouseY = 0;
    this.cameraAngleX = 0.55;
    this.cameraAngleY = -0.75;
    this.cameraDistance = 380;
    this.cameraTarget = new THREE.Vector3(0, 50, 0);

    this.initScene();
  }

  initScene() {
    const width = this.container.clientWidth || 800;
    const height = this.container.clientHeight || 600;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x060911);

    this.camera = new THREE.PerspectiveCamera(40, width / height, 1, 3000);
    this.updateCameraTransform();

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    this.container.innerHTML = '';
    this.container.appendChild(this.renderer.domElement);

    // Warm Architectural Studio Lighting
    const ambientLight = new THREE.AmbientLight(0xfff7ed, 0.85);
    this.scene.add(ambientLight);

    const sunLight = new THREE.DirectionalLight(0xffedd5, 0.95);
    sunLight.position.set(220, 350, 240);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 2048;
    sunLight.shadow.mapSize.height = 2048;
    sunLight.shadow.bias = -0.0001;
    this.scene.add(sunLight);

    const rimLight = new THREE.DirectionalLight(0x38bdf8, 0.45);
    rimLight.position.set(-220, 180, -220);
    this.scene.add(rimLight);

    // Grid Bed
    const grid = new THREE.GridHelper(600, 60, 0x1e293b, 0x0f172a);
    grid.position.y = -2;
    this.scene.add(grid);

    this.rootGroup = new THREE.Group();
    this.scene.add(this.rootGroup);

    this.bindEvents();
    this.animate();
  }

  loadModel(model, materialThickness) {
    // Clear existing
    while (this.rootGroup.children.length > 0) {
      this.rootGroup.remove(this.rootGroup.children[0]);
    }
    this.meshMap.clear();

    const parts = model.parts || [];
    parts.forEach(part => {
      const group = this.buildPartGroup(part, materialThickness);
      if (group) {
        this.rootGroup.add(group);
        this.meshMap.set(part.id, group);
      }
    });

    const { explodeFactor, activeStep, selectedPartId } = AppState.getState();
    ExplodeEngine.applyExplode(this.meshMap, parts, explodeFactor);
    AssemblySequencer.applyStepFilter(this.meshMap, parts, activeStep);
    this.updateHighlight(selectedPartId);
  }

  buildPartGroup(part, thickness) {
    let geoData = null;
    if (typeof part.generate2D === 'function') {
      try { geoData = part.generate2D(thickness, 0.15, 0.10); } catch (e) {}
    }
    if (!geoData && part.geometry && Array.isArray(part.geometry.outline)) {
      geoData = part.geometry;
    }
    if (!geoData || !Array.isArray(geoData.outline) || geoData.outline.length === 0) {
      const hw = (part.width || 40) / 2;
      const hl = (part.length || 40) / 2;
      geoData = { outline: [[-hw, -hl], [hw, -hl], [hw, hl], [-hw, hl]], cutouts: [] };
    }
    const geometry = GeometryEngine.createThreeExtrude(geoData, thickness);
    if (!geometry) return null;

    const group = new THREE.Group();
    group.userData = { partId: part.id, partData: part };

    const mat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(part.color || '#d4a373'),
      roughness: 0.72,
      metalness: 0.05
    });

    const mesh = new THREE.Mesh(geometry, mat);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData = { partId: part.id };
    group.add(mesh);

    // Laser cut edges
    const edges = new THREE.EdgesGeometry(geometry, 25);
    const lineMat = new THREE.LineBasicMaterial({
      color: 0x1e120d,
      linewidth: 1,
      transparent: true,
      opacity: 0.85
    });
    const wireframe = new THREE.LineSegments(edges, lineMat);
    wireframe.name = 'wireframe';
    const { showWireframe } = AppState.getState();
    wireframe.visible = showWireframe;
    group.add(wireframe);

    group.position.set(...part.assembledPos);
    group.rotation.set(...part.assembledRot);

    return group;
  }

  updateHighlight(selectedPartId) {
    this.meshMap.forEach((grp, id) => {
      const mesh = grp.children[0];
      if (!mesh) return;

      if (id === selectedPartId) {
        mesh.material.emissive = new THREE.Color(0x0284c7);
        mesh.material.emissiveIntensity = 0.55;
      } else {
        mesh.material.emissive = new THREE.Color(0x000000);
        mesh.material.emissiveIntensity = 0.0;
      }
    });
  }

  toggleWireframe(visible) {
    this.meshMap.forEach(grp => {
      const wf = grp.getObjectByName('wireframe');
      if (wf) wf.visible = visible;
    });
  }

  setCameraLook(targetVec, dist, angleX = 0.55, angleY = -0.75) {
    this.cameraTarget.copy(targetVec);
    this.cameraDistance = dist;
    this.cameraAngleX = angleX;
    this.cameraAngleY = angleY;
    this.updateCameraTransform();
  }

  updateCameraTransform() {
    const x = this.cameraTarget.x + this.cameraDistance * Math.cos(this.cameraAngleX) * Math.sin(this.cameraAngleY);
    const y = this.cameraTarget.y + this.cameraDistance * Math.sin(this.cameraAngleX);
    const z = this.cameraTarget.z + this.cameraDistance * Math.cos(this.cameraAngleX) * Math.cos(this.cameraAngleY);

    this.camera.position.set(x, y, z);
    this.camera.lookAt(this.cameraTarget);
  }

  onResize() {
    if (!this.container || !this.renderer || !this.camera) return;
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  bindEvents() {
    const el = this.renderer.domElement;

    el.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      this.isMouseDown = true;
      this.mouseX = e.clientX;
      this.mouseY = e.clientY;

      const rect = el.getBoundingClientRect();
      this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      this.raycaster.setFromCamera(this.mouse, this.camera);
      const intersects = this.raycaster.intersectObjects(this.rootGroup.children, true);

      if (intersects.length > 0) {
        let top = intersects[0].object;
        while (top && top.parent !== this.rootGroup) {
          top = top.parent;
        }
        if (top && top.userData && top.userData.partId) {
          if (this.onPartSelected) this.onPartSelected(top.userData.partId);
        }
      }
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.isMouseDown) return;
      const dx = e.clientX - this.mouseX;
      const dy = e.clientY - this.mouseY;
      this.mouseX = e.clientX;
      this.mouseY = e.clientY;

      this.cameraAngleY -= dx * 0.007;
      this.cameraAngleX += dy * 0.007;
      this.cameraAngleX = Math.max(-Math.PI / 2.2, Math.min(Math.PI / 2.2, this.cameraAngleX));
      this.updateCameraTransform();
    });

    window.addEventListener('mouseup', () => {
      this.isMouseDown = false;
    });

    el.addEventListener('wheel', (e) => {
      e.preventDefault();
      this.cameraDistance += e.deltaY * 0.28;
      this.cameraDistance = Math.max(30, Math.min(900, this.cameraDistance));
      this.updateCameraTransform();
    }, { passive: false });

    window.addEventListener('resize', () => this.onResize());
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  }
}
