globalThis.window = { location: { search: '' } };
globalThis.localStorage = { getItem: () => null, setItem: () => {} };

import { ConstructionObject } from '../js/models/model-schema.js';
import { PhysicalValidator } from '../js/validation/validator.js';
import { SheetNester } from '../js/manufacturing/nester.js';
import { GeometryEngine } from '../js/core/geometry.js';
import { ClassicCarModelData } from '../js/models/my-model.js';

async function test() {
  console.log('--- Testing ClassicCarModelData in my-model.js ---');
  const model = new ConstructionObject(ClassicCarModelData);
  console.log(`Model: "${model.name}" (${model.id}) with ${model.getPartCount()} parts.`);

  // 1. Audit
  const audit = PhysicalValidator.auditModel(model, 3.0);
  const errors = audit.issues.filter(i => i.level === 'ERROR');
  console.log(`Audit: ${audit.issues.length} total issues, ${errors.length} errors.`);
  if (errors.length > 0) {
    console.error('FAIL: Physical audit has errors:', errors);
    process.exit(1);
  }
  console.log('PASS: Physical fit audit has 0 errors!');

  // 2. 4 Manufacturing Sheets
  console.log('Manufacturing sheets:', model.manufacturingSheets.length);
  for (let s = 1; s <= model.manufacturingSheets.length; s++) {
    const res = SheetNester.generateSheetSVG(model, s, 3.0);
    console.log(`Sheet ${s} (${res.sheetDef.name}): ${res.partsCount} parts nested, SVG size: ${res.source.length} bytes.`);
    if (res.partsCount === 0 || !res.source.includes('<svg')) {
      console.error(`FAIL on sheet ${s}`);
      process.exit(1);
    }
  }
  console.log('PASS: All 4 sheets generated valid SVGs!');

  // 3. Standalone SVG for wheels, chassis, etc.
  const samplePartIds = ['CHASSIS-01', 'W-FL-FACE', 'TAIL-01', 'ROOF-01', 'GRILL-01'];
  for (const pid of samplePartIds) {
    const part = model.getPart(pid);
    const svg = GeometryEngine.generateStandalonePartSVG(part, 3.0);
    if (!svg || !svg.source || !svg.source.includes('<svg')) {
      console.error(`FAIL: Standalone SVG for ${pid}`);
      process.exit(1);
    }
  }
  console.log('PASS: Standalone SVGs work cleanly!');
  console.log('\n*** ALL TESTS PASSED SUCCESSFULLY! ***');
}

test().catch(err => {
  console.error(err);
  process.exit(1);
});
