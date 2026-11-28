/**
 * Universal Model Registry
 * Allows dynamic registration and retrieval of any construction model.
 * Integrates with static seed models and dynamic Firebase/Local designs.
 */
import { ConstructionObject } from './model-schema.js';
import * as CustomModelModule from './my-model.js';
import { CathedralModelData } from './cathedral.js';
import { SimpleHouseModelData } from './simple-house.js';
import { AppState } from '../core/config.js';
import { DesignService } from '../services/firebase-designs.js';
import { DesignParser } from '../services/design-parser.js';

// Dynamically extract the custom model object regardless of variable name
const detectedCustomModel = CustomModelModule.MyModelData 
  || CustomModelModule.default 
  || Object.values(CustomModelModule).find(val => val && typeof val === 'object' && val.id && Array.isArray(val.parts));

class ModelRegistryService {
  constructor() {
    this.models = new Map();
    this.listeners = new Set();

    // Register built-in default models
    if (detectedCustomModel) {
      this.registerModel(new ConstructionObject(detectedCustomModel));
    }
    this.registerModel(new ConstructionObject(CathedralModelData));
    this.registerModel(new ConstructionObject(SimpleHouseModelData));

    // Register any stored cloud/local designs
    this.hydrateFromStorage();
  }

  /**
   * Subscribe to registry changes (e.g. when new models are saved or updated)
   */
  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify() {
    for (const listener of this.listeners) {
      try {
        listener(this.getAllModels());
      } catch (err) {
        console.error('[ModelRegistry] Listener error:', err);
      }
    }
  }

  registerModel(modelInstance) {
    if (!modelInstance || !modelInstance.id) return;
    this.models.set(modelInstance.id, modelInstance);
    this.notify();
  }

  createBlankModel(id, name) {
    if (!id) {
      id = DesignService.generateSlug(name || 'Custom Model');
    }
    const cleanModel = new ConstructionObject({
      id: id,
      name: name || 'Custom Model',
      category: 'Custom Designs',
      description: 'Blank construction puzzle design canvas.',
      difficulty: 'Level 1 - Beginner',
      defaultScale: 1.0,
      parts: [],
      assemblies: [],
      assemblySteps: [],
      manufacturingSheets: [],
      cameraBookmarks: []
    });
    this.registerModel(cleanModel);
    return cleanModel;
  }

  getDefaultModel() {
    return this.models.get('classic-sports-coupe') 
      || (detectedCustomModel && this.models.get(detectedCustomModel.id))
      || this.models.get('cathedral') 
      || this.getAllModels()[0] 
      || null;
  }

  getModel(modelId) {
    if (!modelId) {
      return this.getDefaultModel();
    }
    if (this.models.has(modelId)) return this.models.get(modelId);
    if (modelId === 'car-j4ir' && this.models.has('classic-sports-coupe')) {
      return this.models.get('classic-sports-coupe');
    }
    // Check local storage cache before giving up
    try {
      const cached = DesignService.getLocalCache().find(d => d.id === modelId);
      if (cached) {
        if (cached.modelData) {
          const obj = new ConstructionObject(cached.modelData);
          this.registerModel(obj);
          return obj;
        }
      }
    } catch (e) {}

    return null;
  }

  getActiveModel() {
    const { activeModelId } = AppState.getState();
    let model = this.getModel(activeModelId);
    if (!model) {
      if (activeModelId) {
        // Create an isolated blank model for this specific active ID so it never borrows another model's data
        model = this.createBlankModel(activeModelId, 'Custom Model');
      } else {
        model = this.getDefaultModel();
      }
    }
    return model;
  }

  getAllModels() {
    return Array.from(this.models.values());
  }

  /**
   * Registers a dynamic design from its model data (or a JSON model definition in jsCode). Stored JavaScript is
   * never run here: designs come from Firestore, the local cache or a ?model= link, and anyone could have written them.
   */
  async registerDynamicDesign(design) {
    try {
      let modelData = design.modelData;
      if (!modelData && design.jsCode) {
        const parsed = await DesignParser.parseAndValidate(design.jsCode, { allowCode: false });
        if (parsed.success) {
          modelData = parsed.modelData;
        }
      }

      if (modelData) {
        // Ensure ID matches
        modelData.id = design.id || modelData.id;
        if (design.name) modelData.name = design.name;
        const constrObj = new ConstructionObject(modelData);
        this.registerModel(constrObj);
        return constrObj;
      } else if (design.id) {
        // Clean blank/custom design registered without parts yet
        const constrObj = this.createBlankModel(design.id, design.name);
        return constrObj;
      }
    } catch (err) {
      console.warn('[ModelRegistry] Failed to register dynamic design:', design.id, err);
    }
    return null;
  }

  /**
   * Hydrates the registry with cached designs from local storage
   */
  hydrateFromStorage() {
    try {
      const cached = DesignService.getLocalCache();
      for (const item of cached) {
        if (item.modelData) {
          this.registerModel(new ConstructionObject(item.modelData));
        } else if (item.jsCode) {
          DesignParser.parseAndValidate(item.jsCode, { allowCode: false }).then(res => {
            if (res.success && res.modelData) {
              res.modelData.id = item.id || res.modelData.id;
              if (item.name) res.modelData.name = item.name;
              this.registerModel(new ConstructionObject(res.modelData));
            }
          }).catch(() => {});
        }
      }
    } catch (err) {
      console.warn('[ModelRegistry] Could not hydrate from storage cache:', err);
    }
  }

  /**
   * Ensures a model is loaded into the registry, fetching from storage/parser if necessary
   */
  async ensureModelLoaded(modelId) {
    if (!modelId) return this.getActiveModel();
    if (this.models.has(modelId)) return this.models.get(modelId);
    try {
      const design = await DesignService.getDesign(modelId);
      if (design) {
        const loaded = await this.registerDynamicDesign(design);
        if (loaded) return loaded;
      }
    } catch (e) {
      console.warn('[ModelRegistry] Could not load design:', modelId, e);
    }
    return this.getModel(modelId);
  }

  importCustomJSON(jsonString) {
    try {
      const parsed = JSON.parse(jsonString);
      if (!parsed.id || !Array.isArray(parsed.parts)) {
        throw new Error("Model JSON must have an 'id' and 'parts' array.");
      }
      const newModel = new ConstructionObject(parsed);
      this.registerModel(newModel);
      AppState.setState({ activeModelId: newModel.id, selectedPartId: newModel.parts[0]?.id || null });
      return { success: true, model: newModel };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }
}

export const ModelRegistry = new ModelRegistryService();
