import { DesignParser } from '../js/services/design-parser.js';

async function test(name, code) {
  const res = await DesignParser.parseAndValidate(code);
  if (!res.success) {
    console.error(`FAIL [${name}]:`, res.error);
    process.exit(1);
  }
  console.log(`PASS [${name}]: found "${res.modelData.name}" (${res.modelData.id})`);
}

async function runAll() {
  await test('User exact code (const ClassicCarModelData = { ... })', `
    const ClassicCarModelData = {
      id: "classic-sports-coupe",
      name: "Vintage GT Sports Coupe (102 Parts)",
      parts: [
        { id: "P1", fileName: "p1.svg", name: "P1", width: 10, length: 10, assembledPos: [0,0,0], geometry: { outline: [[0,0],[10,0],[10,10],[0,10]] } }
      ]
    };
  `);

  await test('Multiple helper constants before model', `
    const THICKNESS = 3.0;
    const WHEEL_RADIUS = 15;
    const VehicleData = {
      id: "truck-01",
      name: "Heavy Cargo Truck",
      parts: [
        { id: "T1", fileName: "t1.svg", name: "T1", width: 20, length: 20, assembledPos: [0,0,0], geometry: { outline: [[0,0],[20,0],[20,20],[0,20]] } }
      ]
    };
  `);

  await test('Standard export default', `
    export default {
      id: "house-01",
      name: "Minimal House",
      parts: [
        { id: "H1", fileName: "h1.svg", name: "H1", width: 20, length: 20, assembledPos: [0,0,0], geometry: { outline: [[0,0],[20,0],[20,20],[0,20]] } }
      ]
    };
  `);

  await test('Standard export const', `
    export const StadiumModel = {
      id: "stadium-01",
      name: "Arena Bowl",
      parts: [
        { id: "S1", fileName: "s1.svg", name: "S1", width: 20, length: 20, assembledPos: [0,0,0], geometry: { outline: [[0,0],[20,0],[20,20],[0,20]] } }
      ]
    };
  `);

  await test('Bare object with parentheses', `
    ({
      id: "bare-01",
      name: "Bare Object Model",
      parts: [
        { id: "B1", fileName: "b1.svg", name: "B1", width: 20, length: 20, assembledPos: [0,0,0], geometry: { outline: [[0,0],[20,0],[20,20],[0,20]] } }
      ]
    })
  `);

  console.log('\nALL 5 PARSER VARIATION TESTS PASSED!');
}

runAll().catch(err => {
  console.error(err);
  process.exit(1);
});
