import { DesignParser } from '../js/services/design-parser.js';
import { ConstructionObject } from '../js/models/model-schema.js';

async function run() {
  console.log('Testing dual-representation geometry in DesignParser & ConstructionObject...');

  // Test 1: Model with generate2D functions
  const codeWithGenerate2D = `
    export const DynamicModel = {
      id: 'dynamic-model',
      name: 'Dynamic Box Model',
      parts: [
        {
          id: 'D-01',
          name: 'Dynamic Plate',
          assembledPos: [0, 0, 0],
          generate2D: (t, kerf, clr) => ({
            outline: [[-20, -20], [20, -20], [20, 20], [-20, 20]],
            cutouts: [{ x: 0, y: 0, w: t + clr, h: 10 }]
          })
        }
      ]
    };
    export default DynamicModel;
  `;
  const res1 = await DesignParser.parseAndValidate(codeWithGenerate2D);
  if (!res1.success) {
    console.error('FAIL Test 1:', res1.error);
    process.exit(1);
  }
  console.log('PASS Test 1: generate2D model parsed successfully.');

  // Test 2: Model with static geometry outline
  const codeWithStaticGeo = `
    export const StaticModel = {
      id: 'static-model',
      name: 'Static Box Model',
      parts: [
        {
          id: 'S-01',
          name: 'Static Plate',
          assembledPos: [0, 0, 0],
          geometry: {
            outline: [[-30, -30], [30, -30], [30, 30], [-30, 30]],
            cutouts: []
          }
        }
      ]
    };
    export default StaticModel;
  `;
  const res2 = await DesignParser.parseAndValidate(codeWithStaticGeo);
  if (!res2.success) {
    console.error('FAIL Test 2:', res2.error);
    process.exit(1);
  }
  console.log('PASS Test 2: static geometry model parsed successfully.');

  // Test 3: ConstructionObject normalization
  const constr1 = new ConstructionObject(res1.modelData);
  const p1 = constr1.getPart('D-01');
  if (typeof p1.generate2D !== 'function' || !p1.geometry || !Array.isArray(p1.geometry.outline)) {
    console.error('FAIL Test 3a: p1 not dual-represented:', p1);
    process.exit(1);
  }

  const constr2 = new ConstructionObject(res2.modelData);
  const p2 = constr2.getPart('S-01');
  if (typeof p2.generate2D !== 'function' || !p2.geometry || !Array.isArray(p2.geometry.outline)) {
    console.error('FAIL Test 3b: p2 not dual-represented:', p2);
    process.exit(1);
  }

  // Test executing synthesized generate2D on static part
  const geoResult = p2.generate2D(3.0, 0.15, 0.10);
  if (!geoResult || geoResult.outline.length !== 4) {
    console.error('FAIL Test 3c: synthesized generate2D returned invalid outline:', geoResult);
    process.exit(1);
  }

  console.log('PASS Test 3: ConstructionObject successfully normalized both part styles.');
  console.log('\nALL DUAL-REPRESENTATION TESTS PASSED!');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
