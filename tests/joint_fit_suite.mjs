// PUZZLECORE: AUTHORITATIVE PHYSICAL FIT & ASSEMBLY TEST SUITE
// Directly implements Section 28 (Mandatory Negative & Positive Tests) of the Master Directive.

globalThis.window = { location: { search: '' }, addEventListener: () => {}, dispatchEvent: () => {} };
globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {}, clear: () => {} };

import { ConstructionObject } from '../js/models/model-schema.js';
import { PhysicalValidator } from '../js/validation/validator.js';
import { ConnectorRegistry, ConnectorStandards } from '../js/core/connectors.js';
import { MinimalBoxModel } from '../js/models/templates.js';
import { SimpleHouseModelData } from '../js/models/simple-house.js';
import { CathedralModelData } from '../js/models/cathedral.js';

let passedTests = 0;
let totalTests = 0;

function assert(condition, message) {
  totalTests++;
  if (condition) {
    console.log(`  [PASS] ${message}`);
    passedTests++;
  } else {
    console.error(`  [FAIL] ${message}`);
    process.exitCode = 1;
  }
}

console.log('==============================================================================');
console.log('PUZZLECORE: MASTER DIRECTIVE 12-POINT PHYSICAL FIT TEST SUITE (SECTION 28)');
console.log('==============================================================================\n');

// -----------------------------------------------------------------------------
// TEST 1: Connector wider than receiver => FAIL
// -----------------------------------------------------------------------------
console.log('TEST 1: Connector wider than receiver => must FAIL');
{
  const testModel = {
    id: 'test-1-width-exceeded',
    name: 'Test 1 - Width Exceeded',
    materialThickness: 3.0,
    parts: [
      {
        id: 'BASE',
        name: 'Base Plate',
        materialThickness: 3.0,
        polygon: [[-30, -30], [30, -30], [30, 30], [-30, 30]],
        // Slot length is 20.0mm, thickness is 3.1mm
        cutouts: [{ x: 0, y: 0, w: 20.0, h: 3.1 }],
        assembledPos: [0, 0, 0],
        assembledRot: [0, 0, 0]
      },
      {
        id: 'TAB-PART',
        name: 'Tab Part with oversized 25mm tab',
        materialThickness: 3.0,
        // Tab width is 25mm (from -12.5 to 12.5), which is wider than the 20mm slot
        polygon: [
          [-20, 0], [-12.5, 0], [-12.5, -3], [12.5, -3], [12.5, 0],
          [20, 0], [20, 20], [-20, 20]
        ],
        cutouts: [],
        assembledPos: [0, 0, 1.5],
        assembledRot: [Math.PI / 2, 0, 0],
        connections: [{ targetPartId: 'BASE', type: 'tab_slot' }]
      }
    ]
  };

  const modelObj = new ConstructionObject(testModel);
  const audit = PhysicalValidator.auditModel(modelObj, 3.0);
  const hasError = audit.issues.some(i => i.level === 'ERROR' && i.code === 'CONNECTOR_EXCEEDS_RECEIVER');

  assert(!audit.isPassing, 'Oversized connector fails validation');
  assert(hasError, 'Validator flags CONNECTOR_EXCEEDS_RECEIVER');
}

// -----------------------------------------------------------------------------
// TEST 2: Correct dimensions but 90-degree orientation mismatch => FAIL
// -----------------------------------------------------------------------------
console.log('\nTEST 2: Correct dimensions but 90-degree orientation mismatch => must FAIL');
{
  const testModel = {
    id: 'test-2-orientation-mismatch',
    name: 'Test 2 - 90 deg Orientation Mismatch',
    materialThickness: 3.0,
    parts: [
      {
        id: 'BASE',
        name: 'Base Plate',
        materialThickness: 3.0,
        polygon: [[-30, -30], [30, -30], [30, 30], [-30, 30]],
        // Slot length extends along X in local 2D, Base assembledRot is [0,0,0] (slot is along World X)
        cutouts: [{ x: 0, y: 0, w: 20.0, h: 3.1 }],
        assembledPos: [0, 0, 0],
        assembledRot: [0, 0, 0]
      },
      {
        id: 'TAB-PART',
        name: 'Tab Part rotated 90 deg',
        materialThickness: 3.0,
        // Tab width is 20mm (matches slot length 20mm)
        polygon: [
          [-15, 0], [-10, 0], [-10, -3], [10, -3], [10, 0],
          [15, 0], [15, 20], [-15, 20]
        ],
        cutouts: [],
        assembledPos: [0, 0, 1.5],
        // Tab width rotated to extend along World Z while slot is along World X (90 deg crossed!)
        assembledRot: [Math.PI / 2, 0, Math.PI / 2],
        connections: [{ targetPartId: 'BASE', type: 'tab_slot' }]
      }
    ]
  };

  const modelObj = new ConstructionObject(testModel);
  const audit = PhysicalValidator.auditModel(modelObj, 3.0);
  const hasError = audit.issues.some(i => i.level === 'ERROR' && i.code === 'ORIENTATION_MISMATCH_90_DEG');

  assert(!audit.isPassing, '90-degree crossed orientation fails validation');
  assert(hasError, 'Validator flags ORIENTATION_MISMATCH_90_DEG');
}

// -----------------------------------------------------------------------------
// TEST 3: Two unrelated solid parts occupy the same volume => FAIL
// -----------------------------------------------------------------------------
console.log('\nTEST 3: Two unrelated solid parts occupy the same volume => must FAIL');
{
  const testModel = {
    id: 'test-3-solid-collision',
    name: 'Test 3 - Solid Volume Collision',
    materialThickness: 3.0,
    parts: [
      {
        id: 'PANEL-A',
        name: 'Panel A',
        materialThickness: 3.0,
        polygon: [[-20, -20], [20, -20], [20, 20], [-20, 20]],
        cutouts: [],
        assembledPos: [0, 0, 0],
        assembledRot: [0, 0, 0]
      },
      {
        id: 'PANEL-B',
        name: 'Panel B overlapping Panel A with no joint',
        materialThickness: 3.0,
        polygon: [[-20, -20], [20, -20], [20, 20], [-20, 20]],
        cutouts: [],
        assembledPos: [5, 5, 0],
        assembledRot: [0, 0, 0]
      }
    ]
  };

  const modelObj = new ConstructionObject(testModel);
  const audit = PhysicalValidator.auditModel(modelObj, 3.0);
  const hasError = audit.issues.some(i => i.level === 'ERROR' && i.code === 'UNRELATED_PARTS_COLLISION');

  assert(!audit.isPassing, 'Unrelated overlapping solid parts fail validation');
  assert(hasError, 'Validator flags UNRELATED_PARTS_COLLISION');
}

// -----------------------------------------------------------------------------
// TEST 4: Insufficient edge material (< 1.5mm) => FAIL
// -----------------------------------------------------------------------------
console.log('\nTEST 4: Insufficient edge material (< 1.5mm) => must FAIL');
{
  const testModel = {
    id: 'test-4-thin-edge-margin',
    name: 'Test 4 - Insufficient Edge Margin',
    materialThickness: 3.0,
    parts: [
      {
        id: 'MARGIN-TEST-PART',
        name: 'Part with slot placed 0.8mm from boundary edge',
        materialThickness: 3.0,
        polygon: [[-20, -20], [20, -20], [20, 20], [-20, 20]],
        // Slot top edge is at Y = 19.2, boundary is Y = 20.0 => margin is only 0.8mm (< 1.5mm min)
        cutouts: [{ x: 0, y: 17.65, w: 10, h: 3.1 }],
        assembledPos: [0, 0, 0],
        assembledRot: [0, 0, 0]
      }
    ]
  };

  const modelObj = new ConstructionObject(testModel);
  const audit = PhysicalValidator.auditModel(modelObj, 3.0);
  const hasError = audit.issues.some(i => i.level === 'ERROR' && i.code === 'INSUFFICIENT_EDGE_MARGIN');

  assert(!audit.isPassing, 'Slot with 0.8mm edge margin fails validation');
  assert(hasError, 'Validator flags INSUFFICIENT_EDGE_MARGIN');
}

// -----------------------------------------------------------------------------
// TEST 5: Insufficient slot spacing (< 1.0mm) => FAIL
// -----------------------------------------------------------------------------
console.log('\nTEST 5: Insufficient slot spacing (< 1.0mm) => must FAIL');
{
  const testModel = {
    id: 'test-5-slot-spacing',
    name: 'Test 5 - Insufficient Slot Spacing',
    materialThickness: 3.0,
    parts: [
      {
        id: 'SPACING-PART',
        name: 'Part with adjacent slots 0.5mm apart',
        materialThickness: 3.0,
        polygon: [[-30, -30], [30, -30], [30, 30], [-30, 30]],
        // Two slots with centers at y = -1.8 and y = 1.8, each height 3.1mm:
        // Gap between them is 3.6 - 3.1 = 0.5mm (< 1.0mm minimum spacing!)
        cutouts: [
          { x: 0, y: -1.8, w: 20, h: 3.1 },
          { x: 0, y: 1.8, w: 20, h: 3.1 }
        ],
        assembledPos: [0, 0, 0],
        assembledRot: [0, 0, 0]
      }
    ]
  };

  const modelObj = new ConstructionObject(testModel);
  const audit = PhysicalValidator.auditModel(modelObj, 3.0);
  const hasError = audit.issues.some(i => i.level === 'ERROR' && i.code === 'CUTOUT_SPACING_TOO_CLOSE');

  assert(!audit.isPassing, 'Slots placed 0.5mm apart fail validation');
  assert(hasError, 'Validator flags CUTOUT_SPACING_TOO_CLOSE');
}

// -----------------------------------------------------------------------------
// TEST 6: Half-lap depth insufficient => FAIL
// -----------------------------------------------------------------------------
console.log('\nTEST 6: Half-lap depth insufficient => must FAIL');
{
  const testModel = {
    id: 'test-6-half-lap-depth',
    name: 'Test 6 - Insufficient Half-Lap Depth',
    materialThickness: 3.0,
    parts: [
      {
        id: 'SPINE-01',
        name: 'Longitudinal Spine',
        materialThickness: 3.0,
        polygon: [[-50, -10], [50, -10], [50, 10], [-50, 10]],
        // Notch is only 3mm deep
        cutouts: [{ x: 0, y: 5, w: 3.1, h: 3 }],
        assembledPos: [0, 10, 0],
        assembledRot: [0, 0, 0],
        connections: ['BLK-01']
      },
      {
        id: 'BLK-01',
        name: 'Transverse Bulkhead',
        materialThickness: 3.0,
        polygon: [[-20, -10], [20, -10], [20, 10], [-20, 10]],
        // Notch is only 3mm deep. Total depth = 3 + 3 = 6mm (< 20mm overlap height!)
        cutouts: [{ x: 0, y: -5, w: 3.1, h: 3 }],
        assembledPos: [0, 10, 0],
        assembledRot: [0, Math.PI / 2, 0],
        connections: ['SPINE-01']
      }
    ]
  };

  const modelObj = new ConstructionObject(testModel);
  const audit = PhysicalValidator.auditModel(modelObj, 3.0);
  const hasError = audit.issues.some(i => i.level === 'ERROR' && i.code === 'HALF_LAP_INSUFFICIENT_DEPTH');

  assert(!audit.isPassing, 'Half-lap with insufficient cut depth fails validation');
  assert(hasError, 'Validator flags HALF_LAP_INSUFFICIENT_DEPTH');
}

// -----------------------------------------------------------------------------
// TEST 7: Illegal corner overlap => FAIL
// -----------------------------------------------------------------------------
console.log('\nTEST 7: Illegal corner overlap => must FAIL');
{
  // Two 90-degree corner plates placed without insetting thickness (both occupy corner volume)
  const testModel = {
    id: 'test-7-corner-overlap',
    name: 'Test 7 - Illegal Corner Overlap',
    materialThickness: 3.0,
    parts: [
      {
        id: 'WALL-NORTH',
        name: 'North Wall',
        materialThickness: 3.0,
        // Extends from X = -20 to 20, at Y = 10, Z = 0
        polygon: [[-20, -10], [20, -10], [20, 10], [-20, 10]],
        cutouts: [],
        assembledPos: [0, 10, 0],
        assembledRot: [0, 0, 0]
      },
      {
        id: 'WALL-EAST',
        name: 'East Wall passing through North Wall corner with no finger joint',
        materialThickness: 3.0,
        // Placed at X = 20, crossing through North Wall solid volume
        polygon: [[-10, -10], [10, -10], [10, 10], [-10, 10]],
        cutouts: [],
        assembledPos: [20, 10, 0],
        assembledRot: [0, Math.PI / 2, 0]
      }
    ]
  };

  const modelObj = new ConstructionObject(testModel);
  const audit = PhysicalValidator.auditModel(modelObj, 3.0);
  const hasError = audit.issues.some(i => i.level === 'ERROR' && (i.code === 'UNRELATED_PARTS_COLLISION' || i.msg.includes('SOLID-BODY COLLISION')));

  assert(!audit.isPassing, 'Illegal corner overlap fails validation');
  assert(hasError, 'Validator flags collision on un-inset corner overlap');
}

// -----------------------------------------------------------------------------
// TEST 8: Missing receiver => FAIL
// -----------------------------------------------------------------------------
console.log('\nTEST 8: Missing receiver => must FAIL');
{
  const testModel = {
    id: 'test-8-missing-receiver',
    name: 'Test 8 - Missing Receiver Slot',
    materialThickness: 3.0,
    parts: [
      {
        id: 'BASE-FLAT',
        name: 'Solid Base Plate with NO slot',
        materialThickness: 3.0,
        polygon: [[-30, -30], [30, -30], [30, 30], [-30, 30]],
        cutouts: [], // Intentionally empty: no slot to receive tab!
        assembledPos: [0, 0, 0],
        assembledRot: [0, 0, 0]
      },
      {
        id: 'WALL-TABBED',
        name: 'Wall with tenon tab expecting a slot',
        materialThickness: 3.0,
        polygon: [
          [-20, 0], [-10, 0], [-10, -3], [10, -3], [10, 0],
          [20, 0], [20, 20], [-20, 20]
        ],
        cutouts: [],
        assembledPos: [0, 0, 1.5],
        assembledRot: [Math.PI / 2, 0, 0],
        connections: ['BASE-FLAT']
      }
    ]
  };

  const modelObj = new ConstructionObject(testModel);
  const audit = PhysicalValidator.auditModel(modelObj, 3.0);
  const hasError = audit.issues.some(i => i.level === 'ERROR' && (i.code === 'MISSING_RECEIVER' || i.msg.includes('no matching receiver slot')));

  assert(!audit.isPassing, 'Tab connecting to plate without receiver fails validation');
  assert(hasError, 'Validator flags MISSING_RECEIVER');
}

// -----------------------------------------------------------------------------
// TEST 9: Connector penetration exceeds allowed joint penetration => FAIL
// -----------------------------------------------------------------------------
console.log('\nTEST 9: Connector penetration exceeds allowed joint penetration => must FAIL');
{
  const testModel = {
    id: 'test-9-excessive-penetration',
    name: 'Test 9 - Excessive Penetration',
    materialThickness: 3.0,
    parts: [
      {
        id: 'PLATE-A',
        name: 'Plate A',
        materialThickness: 3.0,
        polygon: [[-40, -40], [40, -40], [40, 40], [-40, 40]],
        cutouts: [{ x: 0, y: 0, w: 20.1, h: 3.1 }],
        assembledPos: [0, 0, 0],
        assembledRot: [0, 0, 0],
        connections: ['PLATE-B']
      },
      {
        id: 'PLATE-B',
        name: 'Plate B sunk deep into Plate A',
        materialThickness: 3.0,
        polygon: [[-30, -30], [30, -30], [30, 30], [-30, 30]],
        cutouts: [],
        // Placed so that entire 30mm solid body penetrates through Plate A (penetration volume ~ 1800mm^3)
        assembledPos: [0, 0, 0],
        assembledRot: [Math.PI / 2, 0, 0],
        connections: ['PLATE-A']
      }
    ]
  };

  const modelObj = new ConstructionObject(testModel);
  const audit = PhysicalValidator.auditModel(modelObj, 3.0);
  const hasError = audit.issues.some(i => i.level === 'ERROR' && (i.code === 'EXCESSIVE_SOLID_PENETRATION' || i.msg.includes('excessive solid volume')));

  assert(!audit.isPassing, 'Excessive solid penetration in declared joint fails validation');
  assert(hasError, 'Validator flags EXCESSIVE_SOLID_PENETRATION');
}

// -----------------------------------------------------------------------------
// TEST 10: Valid connector + receiver + clearance + orientation => PASS
// -----------------------------------------------------------------------------
console.log('\nTEST 10: Valid connector + receiver + clearance + orientation => must PASS');
{
  const testModel = {
    id: 'test-10-perfect-joint',
    name: 'Test 10 - Perfect Mechanical Joint',
    materialThickness: 3.0,
    parts: [
      {
        id: 'BASE-PLATE',
        name: 'Base Plate',
        materialThickness: 3.0,
        polygon: [[-30, -30], [30, -30], [30, 30], [-30, 30]],
        // Slot width: 20.1mm (20 + 0.1 clearance), thickness: 3.1mm
        cutouts: [{ x: 0, y: 0, w: 20.1, h: 3.1 }],
        assembledPos: [0, 0, 0],
        assembledRot: [0, 0, 0]
      },
      {
        id: 'UPRIGHT-WALL',
        name: 'Upright Wall with 20mm tab',
        materialThickness: 3.0,
        polygon: [
          [-20, 0], [-10, 0], [-10, -3], [10, -3], [10, 0],
          [20, 0], [20, 25], [-20, 25]
        ],
        cutouts: [],
        assembledPos: [0, 0, 1.5],
        assembledRot: [Math.PI / 2, 0, 0],
        connections: [{ targetPartId: 'BASE-PLATE', type: 'tab_slot' }]
      }
    ]
  };

  const modelObj = new ConstructionObject(testModel);
  const audit = PhysicalValidator.auditModel(modelObj, 3.0);

  assert(audit.isPassing, 'Valid mechanical joint passes validation (isPassing: true)');
  assert(audit.errorCount === 0, `Valid joint has 0 errors (found: ${audit.errorCount})`);
}

// -----------------------------------------------------------------------------
// TEST 11: Parts intentionally touch at valid mating surfaces => PASS
// -----------------------------------------------------------------------------
console.log('\nTEST 11: Parts intentionally touch at valid mating surfaces => must PASS');
{
  const testModel = {
    id: 'test-11-abutting-touch',
    name: 'Test 11 - Abutting Surfaces',
    materialThickness: 3.0,
    parts: [
      {
        id: 'TILE-LEFT',
        name: 'Tile Left',
        materialThickness: 3.0,
        polygon: [[-20, -10], [0, -10], [0, 10], [-20, 10]],
        cutouts: [],
        assembledPos: [0, 0, 0],
        assembledRot: [0, 0, 0]
      },
      {
        id: 'TILE-RIGHT',
        name: 'Tile Right',
        materialThickness: 3.0,
        polygon: [[0, -10], [20, -10], [20, 10], [0, 10]],
        cutouts: [],
        assembledPos: [0, 0, 0],
        assembledRot: [0, 0, 0]
      }
    ]
  };

  const modelObj = new ConstructionObject(testModel);
  const audit = PhysicalValidator.auditModel(modelObj, 3.0);

  assert(audit.isPassing, 'Abutting parts with zero solid penetration pass validation');
  assert(audit.errorCount === 0, `Abutting parts produce 0 errors (found: ${audit.errorCount})`);
}

// -----------------------------------------------------------------------------
// TEST 12: Material thickness changes update mating dimensions automatically => PASS
// -----------------------------------------------------------------------------
console.log('\nTEST 12: Material thickness changes update mating dimensions automatically => must PASS');
{
  const tab = { width: 22.0, depth: 3.0 };
  
  // Nominal 3mm thickness
  const slot3mm = ConnectorRegistry.deriveReceiverSlot(tab, 3.0, 0.1);
  // Re-parameterized for 4mm sheet
  const slot4mm = ConnectorRegistry.deriveReceiverSlot(tab, 4.0, 0.1);

  assert(Math.abs(slot3mm.thickness - 3.1) < 1e-4, 'Slot thickness for 3mm sheet is 3.1mm');
  assert(Math.abs(slot4mm.thickness - 4.1) < 1e-4, 'Slot thickness for 4mm sheet is 4.1mm');
  assert(Math.abs(slot3mm.width - 22.1) < 1e-4, 'Slot width incorporates 0.1mm clearance');
  assert(slot4mm.thickness > slot3mm.thickness, 'Receiver slot scales automatically with material thickness');
}

// -----------------------------------------------------------------------------
// TEST 13: Authoritative Joint Generation & Derivation Enforcement
// -----------------------------------------------------------------------------
console.log('\nTEST 13: Authoritative Joint Generation & Derivation Enforcement (Section 1, 2, 3)');
{
  // 1. Valid Joint generates matching tab and receiver
  const jointDef = {
    id: 'J-TEST-01',
    sourcePart: 'P-SRC',
    targetPart: 'P-TGT',
    type: 'mortise-tenon',
    sourceConnector: { type: 'tab', width: 25.0, depth: 3.0 },
    position: [0, 10],
    receiverAxis: 'X'
  };

  const slot = ConnectorStandards.deriveReceiverSlot(jointDef, 3.0, 0.10);
  assert(Math.abs(slot.w - 25.1) < 1e-4, 'Derived receiver slot width matches connector tab width + clearance (25.1mm)');
  assert(Math.abs(slot.h - 3.1) < 1e-4, 'Derived receiver slot thickness matches material thickness + clearance (3.1mm)');
  assert(slot.x === 0 && slot.y === 10, 'Derived receiver slot position matches joint position [0, 10]');

  // 2. Changing connector width updates receiver automatically
  const updatedJoint = {
    ...jointDef,
    sourceConnector: { type: 'tab', width: 34.0, depth: 3.0 }
  };
  const updatedSlot = ConnectorStandards.deriveReceiverSlot(updatedJoint, 3.0, 0.10);
  assert(Math.abs(updatedSlot.w - 34.1) < 1e-4, 'Updating connector width to 34mm automatically derives 34.1mm receiver slot');

  // 3. Manually mismatched receiver is rejected (JOINT_GEOMETRY_NOT_DERIVED)
  const mismatchedModel = {
    id: 'mismatched-model',
    joints: [jointDef],
    parts: [
      {
        id: 'P-SRC',
        width: 40, length: 40,
        polygon: [[-20, -20], [-12.5, -20], [-12.5, -23], [12.5, -23], [12.5, -20], [20, -20], [20, 20], [-20, 20]],
        cutouts: [],
        assembledPos: [0, 20, 0],
        assembledRot: [0, 0, 0]
      },
      {
        id: 'P-TGT',
        width: 60, length: 60,
        polygon: [[-30, -30], [30, -30], [30, 30], [-30, 30]],
        // Manually mismatched slot dimensions (18x3mm instead of 25.1x3.1mm)
        cutouts: [{ x: 0, y: 10, w: 18.0, h: 3.0 }],
        assembledPos: [0, 0, 0],
        assembledRot: [-Math.PI / 2, 0, 0]
      }
    ]
  };
  const auditMismatch = PhysicalValidator.auditModel(new ConstructionObject(mismatchedModel), 3.0);
  assert(!auditMismatch.isPassing, 'Model with manually mismatched receiver slot fails validation');
  assert(auditMismatch.issues.some(i => i.code === 'JOINT_GEOMETRY_NOT_DERIVED'), 'Validator issues JOINT_GEOMETRY_NOT_DERIVED error for hardcoded mismatch');

  // 4. Mechanical feature without Joint definition is rejected
  const unjointedModel = {
    id: 'unjointed-model',
    joints: [], // No authoritative joint declared
    parts: [
      {
        id: 'P-SRC-UNJ',
        connections: ['P-TGT-UNJ'],
        width: 40, length: 40,
        // Outline has a physical tenon tab protruding
        polygon: [[-20, -20], [-10, -20], [-10, -23], [10, -23], [10, -20], [20, -20], [20, 20], [-20, 20]],
        cutouts: [],
        assembledPos: [0, 20, 0],
        assembledRot: [0, 0, 0]
      },
      {
        id: 'P-TGT-UNJ',
        connections: ['P-SRC-UNJ'],
        width: 60, length: 60,
        polygon: [[-30, -30], [30, -30], [30, 30], [-30, 30]],
        cutouts: [], // Missing receiver for the tenon tab!
        assembledPos: [0, 0, 0],
        assembledRot: [-Math.PI / 2, 0, 0]
      }
    ]
  };
  const auditUnjointed = PhysicalValidator.auditModel(new ConstructionObject(unjointedModel), 3.0);
  assert(!auditUnjointed.isPassing, 'Model with undeclared tenon tab feature without receiver fails');
  assert(auditUnjointed.issues.some(i => i.code === 'MISSING_RECEIVER'), 'Validator flags undeclared mating feature with MISSING_RECEIVER');
}

// -----------------------------------------------------------------------------
// TEST 14: Narrow-Phase Collision & Joint-Localized Exemption (Section 4, 5)
// -----------------------------------------------------------------------------
console.log('\nTEST 14: Narrow-Phase Collision & Joint-Localized Exemption (Section 4, 5)');
{
  // 1. Collision outside joint locus is rejected (COLLISION_OUTSIDE_JOINT_LOCUS)
  const locusTestModel = {
    id: 'locus-test',
    joints: [
      {
        id: 'J-LOCUS-01',
        sourcePart: 'P-LOCUS-A',
        targetPart: 'P-LOCUS-B',
        type: 'mortise-tenon',
        sourceConnector: { type: 'tab', width: 20, depth: 3.0 },
        position: [0, 0],
        worldPos: [0, 0, 0] // Joint is centered at origin
      }
    ],
    parts: [
      {
        id: 'P-LOCUS-A',
        width: 120, length: 20,
        polygon: [[-60, -10], [60, -10], [60, 10], [-60, 10]],
        cutouts: [],
        assembledPos: [0, 0, 0],
        assembledRot: [0, 0, 0]
      },
      {
        id: 'P-LOCUS-B',
        width: 20, length: 120,
        // Part B intentionally touches at origin, but also penetrates at X=55 (55mm away from joint locus)
        polygon: [[-10, -60], [10, -60], [10, 60], [-10, 60]],
        cutouts: [{ x: 0, y: 0, w: 20.1, h: 3.1 }],
        assembledPos: [55, 0, 0], // Offset so solid body collision occurs far from joint!
        assembledRot: [0, 0, 0]
      }
    ]
  };
  const auditLocus = PhysicalValidator.auditModel(new ConstructionObject(locusTestModel), 3.0);
  assert(!auditLocus.isPassing, 'Connected parts colliding outside joint locus fail validation');
  assert(auditLocus.issues.some(i => i.code === 'COLLISION_OUTSIDE_JOINT_LOCUS' || i.code === 'UNRELATED_PARTS_COLLISION' || i.code === 'EXCESSIVE_SOLID_PENETRATION'), 'Collision outside joint locus correctly flagged as illegal penetration');

  // 2. Rotated non-intersecting solids with overlapping AABBs pass narrow-phase SAT
  // Two angled roof panels whose axis-aligned bounding boxes overlap, but separated in 3D:
  const obb1 = {
    center: [-25, 60, 0],
    halfSize: [28, 45, 1.5],
    axes: [
      [Math.cos(Math.PI / 4), Math.sin(Math.PI / 4), 0],
      [0, 0, 1],
      [-Math.sin(Math.PI / 4), Math.cos(Math.PI / 4), 0]
    ]
  };
  const obb2 = {
    center: [25, 60, 0],
    halfSize: [28, 45, 1.5],
    axes: [
      [Math.cos(-Math.PI / 4), Math.sin(-Math.PI / 4), 0],
      [0, 0, 1],
      [-Math.sin(-Math.PI / 4), Math.cos(-Math.PI / 4), 0]
    ]
  };
  const satSeparated = ConnectorStandards.testOBBOverlap(obb1, obb2);
  assert(!satSeparated.intersects, 'Narrow-phase OBB SAT correctly proves separated rotated roof panels do NOT collide');

  // 3. Rotated actually intersecting solids fail narrow-phase SAT
  const obbIntersecting = {
    center: [-5, 60, 0], // Moved close so solids deeply penetrate
    halfSize: [28, 45, 1.5],
    axes: [
      [Math.cos(-Math.PI / 4), Math.sin(-Math.PI / 4), 0],
      [0, 0, 1],
      [-Math.sin(-Math.PI / 4), Math.cos(-Math.PI / 4), 0]
    ]
  };
  const satIntersecting = ConnectorStandards.testOBBOverlap(obb1, obbIntersecting);
  assert(satIntersecting.intersects, 'Narrow-phase OBB SAT correctly detects physically intersecting rotated solids');
}

// -----------------------------------------------------------------------------
// TEST 15: Canonical Models Thickness Scaling Matrix (Section 6, 7, 8, 11)
// -----------------------------------------------------------------------------
console.log('\nTEST 15: Canonical Models Thickness Scaling Matrix (3mm, 4mm, 5mm)');
{
  const thicknesses = [3.0, 4.0, 5.0];

  // A. MinimalBoxModel at 3mm, 4mm, 5mm
  const boxObj = new ConstructionObject(MinimalBoxModel);
  thicknesses.forEach(t => {
    const res = PhysicalValidator.auditModel(boxObj, t);
    assert(res.isPassing && res.errorCount === 0, `MinimalBoxModel at ${t}mm: PASS (0 errors, ${res.warningCount} warnings)`);
  });

  // B. SimpleHouseModelData at 3mm, 4mm, 5mm
  const houseObj = new ConstructionObject(SimpleHouseModelData);
  thicknesses.forEach(t => {
    const res = PhysicalValidator.auditModel(houseObj, t);
    assert(res.isPassing && res.errorCount === 0, `SimpleHouseModelData at ${t}mm: PASS (0 errors, ${res.warningCount} warnings)`);
  });

  // C. CathedralModelData at 3mm, 4mm, 5mm
  const cathObj = new ConstructionObject(CathedralModelData);
  thicknesses.forEach(t => {
    const res = PhysicalValidator.auditModel(cathObj, t);
    assert(res.isPassing && res.errorCount === 0, `CathedralModelData at ${t}mm: PASS (0 errors, ${res.warningCount} warnings)`);
  });
}

console.log('\n==============================================================================');
console.log(`MASTER DIRECTIVE TEST SUITE: ${passedTests} / ${totalTests} CHECKS PASSED`);
if (passedTests === totalTests) {
  console.log('ALL ARCHITECTURAL INTEGRITY & VERIFICATION TESTS PASSED SUCCESSFULLY!');
} else {
  console.error(`SOME TESTS FAILED: ${totalTests - passedTests} failed`);
}
console.log('==============================================================================');

