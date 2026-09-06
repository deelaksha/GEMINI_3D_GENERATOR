globalThis.window = { location: { search: '' } };
globalThis.localStorage = { getItem: () => null, setItem: () => {} };

import { ModelRegistry } from '../js/models/registry.js';
import { PhysicalValidator } from '../js/validation/validator.js';
import { SheetNester } from '../js/manufacturing/nester.js';
import { GeometryEngine } from '../js/core/geometry.js';

async function verify() {
  console.log('--- Verifying Car Model in my-model.js ---');

  const model = ModelRegistry.getActiveModel();
  console.log(`Active Model: "${model.name}" (${model.id}) with ${model.getPartCount()} parts.`);

  if (model.id !== 'classic-sports-coupe') {
    console.error('FAIL: Expected active model classic-sports-coupe, got:', model.id);
    process.exit(1);
  }

  // 1. Audit physical fit
  const audit = PhysicalValidator.auditModel(model, 3.0);
  const errors = audit.issues.filter(i => i.level === 'ERROR');
  console.log(`Physical Audit: ${audit.issues.length} total issues, ${errors.length} errors.`);
  if (errors.length > 0) {
    console.error('FAIL: Physical audit has errors:', errors);
    process.exit(1);
  }
  console.log('PASS: Zero physical errors!');

  // 2. Check 4 2D Laser Sheets
  const sheets = model.manufacturingSheets || [];
  console.log(`Manufacturing Sheets: ${sheets.length}`);
  if (sheets.length < 4) {
    console.error('FAIL: Expected at least 4 sheets, found:', sheets.length);
    process.exit(1);
  }

  for (let s = 1; s <= sheets.length; s++) {
    const res = SheetNester.generateSheetSVG(model, s, 3.0);
    console.log(`Sheet ${s} (${res.sheetDef.name}): ${res.partsCount} parts nested, SVG length: ${res.source.length}`);
    if (res.partsCount === 0 || !res.source.includes('<svg')) {
      console.error(`FAIL: Sheet ${s} generated invalid SVG!`);
      process.exit(1);
    }
  }
  console.log('PASS: All 4 2D Cut Sheets generated valid SVGs!');

  // 3. Test 2D Standalone SVG for wheels, chassis, tail
  const samplePartIds = ['CHASSIS-01', 'W-FL-FACE', 'TAIL-01', 'ROOF-01'];
  for (const pid of samplePartIds) {
    const part = model.getPart(pid);
    const svg = GeometryEngine.generateStandalonePartSVG(part, 3.0);
    if (!svg || !svg.includes('<svg')) {
      console.error(`FAIL: Standalone SVG for ${pid} failed!`);
      process.exit(1);
    }
  }
  console.log('PASS: Standalone 2D Part SVGs generated cleanly!');

  console.log('\n*** ALL TESTS PASSED! CAR MODEL AND 2D CONNECTORS READY ***');
}

verify().catch(err => {
  console.error(err);
  process.exit(1);
});
