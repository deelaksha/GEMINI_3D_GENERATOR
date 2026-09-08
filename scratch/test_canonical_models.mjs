globalThis.window = { location: { search: '' } };
globalThis.localStorage = { getItem: () => null, setItem: () => {} };

import { ConstructionObject } from '../js/models/model-schema.js';
import { PhysicalValidator } from '../js/validation/validator.js';
import { SimpleHouseModelData } from '../js/models/simple-house.js';
import { CathedralModelData } from '../js/models/cathedral.js';
import { TEMPLATES } from '../js/models/templates.js';

console.log('=== 1. Testing SimpleHouseModelData ===');
const house = new ConstructionObject(SimpleHouseModelData);
const auditHouse = PhysicalValidator.auditModel(house, 3.0);
console.log(`House: ${auditHouse.errorCount} errors, ${auditHouse.warningCount} warnings, passing: ${auditHouse.isPassing}`);
if (auditHouse.errorCount > 0) {
  console.log('House errors:', auditHouse.issues.filter(i => i.level === 'ERROR'));
}

console.log('\n=== 2. Testing CathedralModelData ===');
const cath = new ConstructionObject(CathedralModelData);
const auditCath = PhysicalValidator.auditModel(cath, 3.0);
console.log(`Cathedral: ${auditCath.errorCount} errors, ${auditCath.warningCount} warnings, passing: ${auditCath.isPassing}`);
if (auditCath.errorCount > 0) {
  console.log('Cathedral errors:', auditCath.issues.filter(i => i.level === 'ERROR'));
}

import { DesignParser } from '../js/services/design-parser.js';

console.log('\n=== 3. Testing MinimalBoxModel ===');
const boxRes = await DesignParser.parseAndValidate(TEMPLATES['minimal-box'].code);
console.log('Parse success:', boxRes.success);
const box = new ConstructionObject(boxRes.modelData);
const auditBox = PhysicalValidator.auditModel(box, 3.0);
console.log(`MinimalBox: ${auditBox.errorCount} errors, ${auditBox.warningCount} warnings, passing: ${auditBox.isPassing}`);
if (auditBox.errorCount > 0) {
  console.log('Box errors:', auditBox.issues.filter(i => i.level === 'ERROR'));
}
