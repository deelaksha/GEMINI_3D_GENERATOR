/**
 * Universal Model Registry
 * Allows dynamic registration and retrieval of any construction model.
 */
import { ConstructionObject } from './model-schema.js';
import * as CustomModelModule from './my-model.js';
import { CathedralModelData } from './cathedral.js';
import { SimpleHouseModelData } from './simple-house.js';
import { AppState } from '../core/config.js';

// Dynamically extract the custom model object regardless of variable name
const detectedCustomModel = CustomModelModule.MyModelData 
  || CustomModelModule.default 
  || Object.values(CustomModelModule).find(val => val && typeof val === 'object' && val.id && Array.isArray(val.parts));

class ModelRegistryService {
  constructor() {
    this.models = new Map();
    if (detectedCustomModel) {
      this.registerModel(new ConstructionObject(detectedCustomModel));
    }
    this.registerModel(new ConstructionObject(CathedralModelData));
    this.registerModel(new ConstructionObject(SimpleHouseModelData));
  }

  registerModel(modelInstance) {
    this.models.set(modelInstance.id, modelInstance);
  }

  getModel(modelId) {
    if (this.models.has(modelId)) return this.models.get(modelId);
    if (detectedCustomModel && this.models.has(detectedCustomModel.id)) return this.models.get(detectedCustomModel.id);
    return this.models.get('cathedral');
  }

  getActiveModel() {
    const { activeModelId } = AppState.getState();
    return this.getModel(activeModelId);
  }

  getAllModels() {
    return Array.from(this.models.values());
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
