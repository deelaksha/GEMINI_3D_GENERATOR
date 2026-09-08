/**
 * Firebase Firestore & Local Storage Design Service
 * Provides complete CRUD operations for dynamic 3D designs with offline synchronization.
 */

import { 
  db, 
  collection, 
  doc, 
  getDoc, 
  getDocs, 
  setDoc, 
  deleteDoc, 
  query, 
  orderBy, 
  serverTimestamp 
} from '../core/firebase.js';

const DESIGNS_COLLECTION = 'designs';
const LOCAL_STORAGE_KEY = 'puzzlecore_designs_cache_v1';
const ACTIVE_DESIGN_KEY = 'puzzlecore_active_design_id';

class FirebaseDesignService {
  constructor() {
    this.isOnline = typeof navigator !== 'undefined' ? navigator.onLine : true;
    if (typeof window !== 'undefined' && window.addEventListener) {
      window.addEventListener('online', () => { this.isOnline = true; });
      window.addEventListener('offline', () => { this.isOnline = false; });
    }
  }

  /**
   * Reads cached designs from localStorage
   * @returns {Array<Object>}
   */
  getLocalCache() {
    try {
      const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      console.warn('[DesignService] Error reading local cache:', e);
      return [];
    }
  }

  /**
   * Updates cached designs in localStorage
   * @param {Array<Object>} designs
   */
  setLocalCache(designs) {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(designs));
    } catch (e) {
      console.warn('[DesignService] Error writing local cache:', e);
    }
  }

  /**
   * Lists all designs from Firestore (falling back to localStorage if offline or unavailable)
   * @returns {Promise<Array<Object>>}
   */
  async listDesigns() {
    const local = this.getLocalCache();
    if (!db) {
      console.info('[DesignService] Firestore unavailable, returning local cache.');
      return local;
    }

    try {
      const colRef = collection(db, DESIGNS_COLLECTION);
      const q = query(colRef, orderBy('updatedAt', 'desc'));
      const snapshot = await getDocs(q);

      const cloudDesigns = [];
      snapshot.forEach(docSnap => {
        const data = docSnap.data();
        cloudDesigns.push({
          ...data,
          id: docSnap.id,
          // Normalize timestamps
          createdAt: data.createdAt?.toDate ? data.createdAt.toDate().toISOString() : data.createdAt,
          updatedAt: data.updatedAt?.toDate ? data.updatedAt.toDate().toISOString() : data.updatedAt
        });
      });

      // Merge cloud designs with local-only drafts if any
      const cloudIds = new Set(cloudDesigns.map(d => d.id));
      const localOnly = local.filter(d => !cloudIds.has(d.id));
      const combined = [...cloudDesigns, ...localOnly];

      this.setLocalCache(combined);
      return combined;
    } catch (err) {
      console.warn('[DesignService] Failed to fetch cloud designs, using local cache:', err.message);
      return local;
    }
  }

  /**
   * Retrieves a single design by ID
   * @param {string} id 
   * @returns {Promise<Object|null>}
   */
  async getDesign(id) {
    if (!id) return null;
    const local = this.getLocalCache();
    const cached = local.find(d => d.id === id);

    if (!db) return cached || null;

    try {
      const docRef = doc(db, DESIGNS_COLLECTION, id);
      const snap = await getDoc(docRef);
      if (snap.exists()) {
        const data = snap.data();
        const design = {
          ...data,
          id: snap.id,
          createdAt: data.createdAt?.toDate ? data.createdAt.toDate().toISOString() : data.createdAt,
          updatedAt: data.updatedAt?.toDate ? data.updatedAt.toDate().toISOString() : data.updatedAt
        };
        // Update item in local cache
        const updated = local.filter(d => d.id !== id);
        updated.unshift(design);
        this.setLocalCache(updated);
        return design;
      }
    } catch (err) {
      console.warn(`[DesignService] Cloud fetch failed for design ${id}, using local cache:`, err.message);
    }

    return cached || null;
  }

  /**
   * Saves or updates a design in Firestore and localStorage
   * @param {Object} params
   * @returns {Promise<Object>} The saved design object
   */
  async saveDesign({
    id,
    name,
    category = 'General',
    description = '',
    jsCode,
    modelData = null,
    thumbnail = null,
    tags = []
  }) {
    if (!name || !name.trim()) throw new Error('Design name is required.');
    if (!jsCode || !jsCode.trim()) throw new Error('Design JavaScript code is required.');

    // Generate or sanitize ID
    const designId = id || this.generateSlug(name);
    const existing = await this.getDesign(designId);

    const nowIso = new Date().toISOString();
    const version = existing ? (existing.version || 1) + 1 : 1;
    const createdAt = existing ? existing.createdAt : nowIso;

    const payload = {
      id: designId,
      name: name.trim(),
      category: category.trim() || 'General',
      description: (description || '').trim(),
      jsCode: jsCode.trim(),
      partCount: modelData?.parts?.length || (existing?.partCount || 0),
      difficulty: modelData?.difficulty || (existing?.difficulty || 'Intermediate'),
      dimensions: modelData ? `${modelData.overallDimensions?.width || 0}x${modelData.overallDimensions?.length || 0}x${modelData.overallDimensions?.height || 0}mm` : (existing?.dimensions || ''),
      thumbnail: thumbnail || existing?.thumbnail || null,
      tags: Array.isArray(tags) ? tags : [],
      version,
      author: 'User',
      createdAt,
      updatedAt: nowIso
    };

    // 1. Always write to local storage first for resilience
    const local = this.getLocalCache();
    const idx = local.findIndex(d => d.id === designId);
    if (idx >= 0) {
      local[idx] = payload;
    } else {
      local.unshift(payload);
    }
    this.setLocalCache(local);
    localStorage.setItem(ACTIVE_DESIGN_KEY, designId);

    // 2. Attempt Firestore sync
    if (db) {
      try {
        const docRef = doc(db, DESIGNS_COLLECTION, designId);
        await setDoc(docRef, {
          ...payload,
          updatedAt: serverTimestamp(),
          createdAt: existing ? payload.createdAt : serverTimestamp()
        }, { merge: true });
        console.log(`[DesignService] Design "${name}" saved to Firestore (v${version})`);
      } catch (err) {
        console.warn('[DesignService] Cloud save failed, design kept in local cache:', err.message);
      }
    }

    return payload;
  }

  /**
   * Deletes a design by ID
   * @param {string} id 
   * @returns {Promise<boolean>}
   */
  async deleteDesign(id) {
    if (!id) return false;

    // Remove from local cache
    const local = this.getLocalCache().filter(d => d.id !== id);
    this.setLocalCache(local);

    if (db) {
      try {
        const docRef = doc(db, DESIGNS_COLLECTION, id);
        await deleteDoc(docRef);
        console.log(`[DesignService] Design "${id}" deleted from Firestore`);
      } catch (err) {
        console.warn(`[DesignService] Cloud delete failed for "${id}":`, err.message);
      }
    }

    return true;
  }

  /**
   * Duplicates an existing design with a new name and ID
   * @param {string} sourceId 
   * @param {string} newName 
   * @returns {Promise<Object>}
   */
  async duplicateDesign(sourceId, newName) {
    const source = await this.getDesign(sourceId);
    if (!source) throw new Error(`Source design "${sourceId}" not found.`);

    const targetName = newName || `${source.name} (Copy)`;
    const newId = this.generateSlug(targetName);

    // Update code if it has a hardcoded ID
    let updatedCode = source.jsCode;
    try {
      updatedCode = updatedCode.replace(/id:\s*['"][a-zA-Z0-9_-]+['"]/, `id: '${newId}'`);
      updatedCode = updatedCode.replace(/name:\s*['"][^'"]+['"]/, `name: '${targetName.replace(/'/g, "\\'")}'`);
    } catch (e) {
      // ignore
    }

    return await this.saveDesign({
      id: newId,
      name: targetName,
      category: source.category,
      description: source.description,
      jsCode: updatedCode,
      modelData: null,
      thumbnail: source.thumbnail,
      tags: source.tags
    });
  }

  /**
   * Generates a clean URL/document slug
   * @param {string} name 
   * @returns {string}
   */
  generateSlug(name) {
    const base = name.toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
    const rand = Math.random().toString(36).substring(2, 6);
    return `${base || 'design'}-${rand}`;
  }

  /**
   * Downloads the design as a standalone .js file
   * @param {Object} design 
   */
  exportDesignAsJS(design) {
    const blob = new Blob([design.jsCode], { type: 'text/javascript' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${design.id}.js`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  /**
   * Seeds initial built-in models into cache/Firestore if no designs exist
   * @param {Array<Object>} seedModels 
   */
  async seedInitialDesigns(seedModels = []) {
    const existing = await this.listDesigns();
    if (existing && existing.length > 0) return;

    console.info('[DesignService] No existing designs found. Seeding initial templates...');
    for (const seed of seedModels) {
      try {
        await this.saveDesign(seed);
      } catch (err) {
        console.warn('[DesignService] Seeding failed for model:', seed.name, err.message);
      }
    }
  }
}

export const DesignService = new FirebaseDesignService();
