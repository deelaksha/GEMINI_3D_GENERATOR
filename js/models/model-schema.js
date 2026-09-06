/**
 * Universal Object Model & Schema Validator
 * Sections 4, 5, 6 of Master Context: Authoritative structured object & part definition.
 */

export class ConstructionObject {
  constructor(data) {
    this.id = data.id || 'unnamed_object';
    this.name = data.name || 'Unnamed Construction Object';
    this.category = data.category || 'General';
    this.description = data.description || '';
    this.difficulty = data.difficulty || 'Level 2 - Intermediate';
    this.defaultScale = data.defaultScale || 1.0;
    this.parts = (data.parts || []).map(p => ConstructionObject.normalizePart(p));
    this.assemblies = data.assemblies || [];
    this.assemblySteps = data.assemblySteps || [];
    this.manufacturingSheets = data.manufacturingSheets || [];
    this.cameraBookmarks = data.cameraBookmarks || [];
  }

  /**
   * Normalizes a part definition to guarantee dual-representation:
   * both part.generate2D(t, kerf, clr) and part.geometry = { outline, cutouts }
   */
  static normalizePart(part) {
    if (!part || typeof part !== 'object') return part;

    // Clone or wrap part to avoid mutating frozen definitions
    const p = { ...part };

    // 1. If part has generate2D function, ensure geometry is also populated
    if (typeof p.generate2D === 'function') {
      try {
        const sampleGeo = p.generate2D(3.0, 0.15, 0.10);
        if (sampleGeo && Array.isArray(sampleGeo.outline)) {
          p.geometry = {
            outline: sampleGeo.outline,
            cutouts: sampleGeo.cutouts || []
          };
        }
      } catch (err) {
        console.warn(`[ConstructionObject] Error pre-evaluating generate2D for part ${p.id}:`, err);
      }
    } else if (p.geometry && Array.isArray(p.geometry.outline)) {
      // 2. If part has static geometry, synthesize generate2D
      const staticGeo = p.geometry;
      p.generate2D = function(thickness = 3.0, kerf = 0.15, clearance = 0.10) {
        return {
          outline: staticGeo.outline || [],
          cutouts: staticGeo.cutouts || []
        };
      };
    } else {
      // 3. Fallback rectangular geometry if neither is defined
      const w = p.width || 30;
      const l = p.length || 30;
      const hw = w / 2;
      const hl = l / 2;
      const fallbackGeo = {
        outline: [[-hw, -hl], [hw, -hl], [hw, hl], [-hw, hl]],
        cutouts: []
      };
      p.geometry = fallbackGeo;
      p.generate2D = function() {
        return fallbackGeo;
      };
    }

    return p;
  }

  getPart(partId) {
    return this.parts.find(p => p.id === partId);
  }

  getPartsForStep(stepNum) {
    if (stepNum === 0) return this.parts;
    return this.parts.filter(p => p.step <= stepNum);
  }

  getPartsForSheet(sheetNum) {
    return this.parts.filter(p => p.sheet === sheetNum);
  }

  getPartCount() {
    return this.parts.length;
  }
}
