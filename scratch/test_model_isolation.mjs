if (!globalThis.document) {
  globalThis.document = {
    getElementById: () => null,
    querySelectorAll: () => [],
    createElement: () => ({ appendChild: () => {}, setAttribute: () => {}, classList: { add: () => {}, remove: () => {} } }),
    body: { appendChild: () => {}, removeChild: () => {} }
  };
}

import { AppState } from '../js/core/config.js';
import { ModelRegistry } from '../js/models/registry.js';
import { DesignService } from '../js/services/firebase-designs.js';
import { ConstructionObject } from '../js/models/model-schema.js';

function assert(condition, message) {
  if (!condition) {
    console.error(`❌ ASSERTION FAILED: ${message}`);
    process.exit(1);
  }
  console.log(`✅ PASS: ${message}`);
}

async function runTests() {
  console.log('====================================================');
  console.log('PUZZLECORE MODEL ISOLATION & LIFECYCLE TEST SUITE');
  console.log('====================================================\n');

  // TEST 1: Initial State & Default Model
  console.log('--- TEST 1: Default Model Verification ---');
  const defaultModel = ModelRegistry.getActiveModel();
  assert(defaultModel !== null && defaultModel !== undefined, 'Active model exists on startup');
  assert(defaultModel.id === 'classic-sports-coupe', `Default model ID is classic-sports-coupe (got ${defaultModel.id})`);
  assert(defaultModel.getPartCount() === 67, `Default model has 67 parts (got ${defaultModel.getPartCount()})`);
  assert(defaultModel.parts.some(p => p.id === 'CHASSIS-01'), 'Default model has CHASSIS-01 part');
  assert(defaultModel.assemblySteps.length > 0, 'Default model has assembly steps');

  // TEST 2: Blank Model Creation & Isolation
  console.log('\n--- TEST 2: Blank Model Creation (Custom Model 635) ---');
  const blankSlug = 'custom-model-635-a0zk';
  const blankName = 'Custom Model 635';

  const blankModel = ModelRegistry.createBlankModel(blankSlug, blankName);
  assert(blankModel !== null, 'Blank model created successfully');
  assert(blankModel.id === blankSlug, `Blank model ID matches ${blankSlug}`);
  assert(blankModel.name === blankName, `Blank model name matches ${blankName}`);
  assert(blankModel.getPartCount() === 0, `Blank model has exactly 0 parts (got ${blankModel.getPartCount()})`);
  assert(Array.isArray(blankModel.parts) && blankModel.parts.length === 0, 'Blank model parts is empty array');
  assert(blankModel.parts !== defaultModel.parts, 'Blank model parts array reference is NOT shared with default model');
  assert(blankModel.assemblySteps !== defaultModel.assemblySteps, 'Blank model assemblySteps reference is NOT shared with default model');
  assert(blankModel.manufacturingSheets !== defaultModel.manufacturingSheets, 'Blank model manufacturingSheets reference is NOT shared with default model');

  // TEST 3: Switching Active Model to Blank Model
  console.log('\n--- TEST 3: Active Model Resolution for Blank Model ---');
  AppState.setState({ activeModelId: blankSlug, selectedPartId: null, activeStep: 0 });
  
  const currentActive = ModelRegistry.getActiveModel();
  assert(currentActive.id === blankSlug, `Active model is now ${blankSlug}`);
  assert(currentActive.getPartCount() === 0, 'Active model reports 0 parts');
  assert(currentActive.getPart('CHASSIS-01') === undefined, 'Active model does NOT have CHASSIS-01 part');

  // Verify Vintage GT is still intact in the registry
  const vintageGT = ModelRegistry.getModel('classic-sports-coupe');
  assert(vintageGT.getPartCount() === 67, 'Vintage GT in registry is unchanged with 67 parts');
  assert(vintageGT.getPart('CHASSIS-01') !== undefined, 'Vintage GT still owns CHASSIS-01');

  // TEST 4: Non-existent Model Fallback Protection
  console.log('\n--- TEST 4: Non-Existent Model Query Safety ---');
  const unknown = ModelRegistry.getModel('non-existent-random-id-999');
  assert(unknown === null, 'Querying non-existent model returns null, NOT Vintage GT');

  // TEST 5: Second Blank Model Independence
  console.log('\n--- TEST 5: Multiple Blank Models Independence ---');
  const model2Slug = 'test-model-2-x1y2';
  const model2 = ModelRegistry.createBlankModel(model2Slug, 'Test Model 2');
  
  assert(model2.id === model2Slug, 'Second blank model created');
  assert(model2.parts !== blankModel.parts, 'model2.parts is independent from blankModel.parts');
  assert(model2.parts.length === 0, 'model2 has 0 parts');

  // Add dummy part to model 2 to verify mutation isolation
  model2.parts.push({ id: 'PART-TEST-2', name: 'Test Piece', fileName: 'PART-TEST-2.svg', width: 20, length: 20 });
  assert(model2.getPartCount() === 1, 'model2 now has 1 part');
  assert(blankModel.getPartCount() === 0, 'blankModel STILL has 0 parts (mutation isolated)');
  assert(vintageGT.getPartCount() === 67, 'Vintage GT STILL has 67 parts (mutation isolated)');

  // TEST 6: Persistence & Hydration via DesignService
  console.log('\n--- TEST 6: DesignService Storage & Hydration ---');
  await DesignService.saveDesign({
    id: blankSlug,
    name: blankName,
    category: 'Custom Designs',
    description: 'Isolated test blank canvas',
    jsCode: '/* custom blank code */',
    modelData: {
      id: blankSlug,
      name: blankName,
      parts: []
    }
  });

  const retrieved = await DesignService.getDesign(blankSlug);
  assert(retrieved !== null, 'Design retrieved from DesignService');
  assert(retrieved.id === blankSlug, 'Retrieved design has correct ID');
  assert(retrieved.partCount === 0, 'Retrieved design has partCount 0');

  // TEST 7: Switch back to Vintage GT then back to Custom Model
  console.log('\n--- TEST 7: Switching Back and Forth ---');
  AppState.setState({ activeModelId: 'classic-sports-coupe', selectedPartId: 'CHASSIS-01' });
  const activeVintage = ModelRegistry.getActiveModel();
  assert(activeVintage.id === 'classic-sports-coupe', 'Active model switched back to classic-sports-coupe');
  assert(activeVintage.getPartCount() === 67, 'Vintage GT still has 67 parts');

  AppState.setState({ activeModelId: blankSlug, selectedPartId: null });
  const activeBlankAgain = ModelRegistry.getActiveModel();
  assert(activeBlankAgain.id === blankSlug, 'Active model switched back to blank model');
  assert(activeBlankAgain.getPartCount() === 0, 'Blank model still has 0 parts');

  console.log('\n====================================================');
  console.log('🎉 ALL MODEL ISOLATION & LIFECYCLE TESTS PASSED!');
  console.log('====================================================');
}

runTests().catch(err => {
  console.error('Test runner encountered fatal error:', err);
  process.exit(1);
});
