/**
 * 3D Thumbnail & Realtime Preview Generator
 * Renders high-fidelity isometric 3D snapshots from model definitions,
 * parses unrendered JS models, and provides interactive turntable preview rendering.
 */

import { GeometryEngine } from '../core/geometry.js';
import { DesignParser } from './design-parser.js';
import { ModelRegistry } from '../models/registry.js';
import { CathedralModelData } from '../models/cathedral.js';
import { SimpleHouseModelData } from '../models/simple-house.js';
import { ClassicCarModelData } from '../models/my-model.js';

class ThumbnailGeneratorService {
  constructor() {
    this.offscreenRenderer = null;
    this.offscreenCanvas = null;
    this.width = 360;
    this.height = 225;
  }

  /**
   * Initializes or gets the shared offscreen WebGL renderer
   */
  getRenderer() {
    if (typeof THREE === 'undefined') return null;
    if (!this.offscreenRenderer) {
      this.offscreenCanvas = document.createElement('canvas');
      this.offscreenCanvas.width = this.width;
      this.offscreenCanvas.height = this.height;

      this.offscreenRenderer = new THREE.WebGLRenderer({
        canvas: this.offscreenCanvas,
        antialias: true,
        alpha: false,
        preserveDrawingBuffer: true
      });
      this.offscreenRenderer.setSize(this.width, this.height, false);
      this.offscreenRenderer.setPixelRatio(1); // Standard pixel ratio for snappy thumbnails
      this.offscreenRenderer.shadowMap.enabled = true;
      this.offscreenRenderer.shadowMap.type = THREE.PCFSoftShadowMap;
    }
    return this.offscreenRenderer;
  }

  /**
   * Detects if an image data URL is missing, invalid, or pitch black (< 8 average brightness)
   * @param {string} dataUrl
   * @returns {Promise<boolean>}
   */
  async isBlackOrEmpty(dataUrl) {
    if (!dataUrl || typeof dataUrl !== 'string' || !dataUrl.startsWith('data:image/')) {
      return true;
    }
    if (dataUrl.length < 150) {
      return true;
    }

    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => {
        try {
          const c = document.createElement('canvas');
          c.width = 16;
          c.height = 16;
          const ctx = c.getContext('2d');
          if (!ctx) return resolve(false);
          ctx.drawImage(img, 0, 0, 16, 16);
          const pixels = ctx.getImageData(0, 0, 16, 16).data;
          let totalBrightness = 0;
          for (let i = 0; i < pixels.length; i += 4) {
            totalBrightness += (pixels[i] + pixels[i + 1] + pixels[i + 2]) / 3;
          }
          const avg = totalBrightness / 256;
          // Pitch black or near-total darkness (e.g. wiped WebGL buffer)
          resolve(avg < 8);
        } catch (e) {
          resolve(false);
        }
      };
      img.onerror = () => resolve(true);
      img.src = dataUrl;
    });
  }

  /**
   * Resolves raw input (object, jsCode, or id) into clean modelData
   */
  async resolveModelData(source) {
    if (!source) return null;

    if (typeof source === 'object') {
      if (Array.isArray(source.parts)) {
        return source;
      }
      if (source.modelData && Array.isArray(source.modelData.parts)) {
        return source.modelData;
      }
      if (source.isBlank) {
        return { id: source.id, name: source.name, parts: [] };
      }

      // Check ModelRegistry
      if (source.id && typeof ModelRegistry !== 'undefined') {
        try {
          const reg = ModelRegistry.getModel(source.id);
          if (reg && Array.isArray(reg.parts)) {
            return reg;
          }
        } catch (e) {}
      }

      // Check known built-in IDs and names
      const sId = (source.id || '').toLowerCase();
      const sName = (source.name || '').toLowerCase();

      if (sId === 'cathedral' || sName.includes('cathedral')) {
        return CathedralModelData;
      }
      if (sId === 'simple-house' || sName.includes('gable house') || sName.includes('simple house')) {
        return SimpleHouseModelData;
      }
      if (sId === 'classic-sports-coupe' || sId.startsWith('car') || sName.includes('coupe') || sName.includes('sports coupe')) {
        return ClassicCarModelData;
      }

      // Parse jsCode if present
      if (source.jsCode) {
        const parsed = await DesignParser.parseAndValidate(source.jsCode);
        if (parsed.success && parsed.modelData) {
          return parsed.modelData;
        }
      }
    } else if (typeof source === 'string') {
      const sLower = source.toLowerCase();
      if (sLower === 'cathedral') return CathedralModelData;
      if (sLower === 'simple-house') return SimpleHouseModelData;
      if (sLower === 'classic-sports-coupe') return ClassicCarModelData;

      const parsed = await DesignParser.parseAndValidate(source);
      if (parsed.success && parsed.modelData) {
        return parsed.modelData;
      }
    }
    return null;
  }

  /**
   * Builds Three.js group for a single part
   */
  buildPartMesh(part, defaultThickness = 3.0) {
    if (typeof THREE === 'undefined') return null;

    const thickness = part.thickness || defaultThickness;
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
    group.userData = { partId: part.id };

    const mat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(part.color || '#d4a373'),
      roughness: 0.65,
      metalness: 0.08
    });

    const mesh = new THREE.Mesh(geometry, mat);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    group.add(mesh);

    // Dark laser-cut burn edge wireframe
    try {
      const edges = new THREE.EdgesGeometry(geometry, 25);
      const lineMat = new THREE.LineBasicMaterial({
        color: 0x1e120d,
        linewidth: 1,
        transparent: true,
        opacity: 0.8
      });
      const wireframe = new THREE.LineSegments(edges, lineMat);
      group.add(wireframe);
    } catch (e) {}

    const pos = part.getAssembledPos ? part.getAssembledPos(3.0) : (Array.isArray(part.assembledPos) ? part.assembledPos : [0, 0, 0]);
    const rot = part.getAssembledRot ? part.getAssembledRot(3.0) : (Array.isArray(part.assembledRot) ? part.assembledRot : [0, 0, 0]);
    group.position.set(...pos);
    group.rotation.set(...rot);

    return group;
  }

  /**
   * Generates a high quality 3D isometric thumbnail data URL
   * @param {Object|string} modelSource - ConstructionObject, modelData, or jsCode
   * @param {Object} options
   * @returns {Promise<{thumbnail: string, partCount: number, dimensions: string, difficulty: string}>}
   */
  async generateThumbnail(modelSource, options = {}) {
    const modelData = await this.resolveModelData(modelSource);
    if (!modelData || !Array.isArray(modelData.parts)) {
      return null;
    }
    if (modelData.parts.length === 0) {
      return {
        thumbnail: null,
        partCount: 0,
        dimensions: '',
        difficulty: modelData.difficulty || 'Beginner',
        modelData
      };
    }

    const renderer = this.getRenderer();
    if (!renderer) return null;

    const width = options.width || this.width;
    const height = options.height || this.height;

    if (this.offscreenCanvas.width !== width || this.offscreenCanvas.height !== height) {
      this.offscreenCanvas.width = width;
      this.offscreenCanvas.height = height;
      renderer.setSize(width, height, false);
    }

    // Setup scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0f1d); // Sleek deep navy studio slate

    // Studio Lighting
    const ambientLight = new THREE.AmbientLight(0xfff7ed, 0.9);
    scene.add(ambientLight);

    const sunLight = new THREE.DirectionalLight(0xffedd5, 1.25);
    sunLight.position.set(200, 320, 220);
    sunLight.castShadow = true;
    scene.add(sunLight);

    const rimLight = new THREE.DirectionalLight(0x38bdf8, 0.65);
    rimLight.position.set(-200, 160, -200);
    scene.add(rimLight);

    const underLight = new THREE.DirectionalLight(0x1e293b, 0.4);
    underLight.position.set(0, -150, 0);
    scene.add(underLight);

    // Model root group
    const rootGroup = new THREE.Group();
    modelData.parts.forEach(part => {
      const pMesh = this.buildPartMesh(part);
      if (pMesh) rootGroup.add(pMesh);
    });

    scene.add(rootGroup);

    // Compute bounding box to frame camera perfectly
    const box = new THREE.Box3().setFromObject(rootGroup);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());

    // Center model at origin for symmetrical isometric rotation
    rootGroup.position.sub(center);

    // Camera setup
    const maxDim = Math.max(size.x, size.y, size.z, 25);
    const camera = new THREE.PerspectiveCamera(38, width / height, 1, 4000);
    const dist = maxDim * 1.75;

    camera.position.set(dist * 0.8, dist * 0.65, dist * 0.95);
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();

    // Subtle dark circular grid floor under the model
    const gridRadius = maxDim * 1.5;
    const gridHelper = new THREE.GridHelper(gridRadius, 14, 0x1e293b, 0x0f172a);
    gridHelper.position.y = -(size.y / 2) - 1;
    scene.add(gridHelper);

    // Synchronously render to canvas
    renderer.render(scene, camera);

    const thumbnail = renderer.domElement.toDataURL('image/jpeg', options.quality || 0.85);

    // Clean up scene resources
    while (rootGroup.children.length > 0) {
      const obj = rootGroup.children[0];
      rootGroup.remove(obj);
      if (obj.geometry) obj.geometry.dispose();
      if (obj.material) {
        if (Array.isArray(obj.material)) obj.material.forEach(m => m.dispose());
        else obj.material.dispose();
      }
    }

    const partCount = modelData.parts.length;
    const dimensions = modelData.overallDimensions 
      ? `${modelData.overallDimensions.width || Math.round(size.x)}x${modelData.overallDimensions.length || Math.round(size.z)}x${modelData.overallDimensions.height || Math.round(size.y)}mm`
      : `${Math.round(size.x)}x${Math.round(size.z)}x${Math.round(size.y)}mm`;

    return {
      thumbnail,
      partCount,
      dimensions,
      difficulty: modelData.difficulty || 'Level 2 — Intermediate',
      name: modelData.name || 'Untitled Model',
      modelData
    };
  }
}

export const ThumbnailGenerator = new ThumbnailGeneratorService();
