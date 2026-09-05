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
    this.parts = data.parts || [];
    this.assemblies = data.assemblies || [];
    this.assemblySteps = data.assemblySteps || [];
    this.manufacturingSheets = data.manufacturingSheets || [];
    this.cameraBookmarks = data.cameraBookmarks || [];
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
