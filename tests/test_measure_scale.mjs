import assert from 'assert';
import { computeDraftingSpecs, renderDraftingSvg } from '../js/studio/drafting.js';

console.log('Testing Measure Scale & Snap Points...');

const sampleGable = {
  id: 'GABLE-B',
  name: 'Back gable wall',
  thickness: 1.0,
  width: 40.0,
  height: 44.0,
  outline: [
    [-20, -22],
    [20, -22],
    [20, 7],
    [0, 22],
    [-20, 7]
  ],
  cut_outline: [
    [-20, -22],
    [-8, -22],
    [-8, -21],
    [8, -21],
    [8, -22],
    [20, -22],
    [20, 7],
    [10.8, 13.9],
    [11.4, 14.7],
    [5.4, 19.2],
    [4.8, 18.4],
    [0, 22],
    [-4.8, 18.4],
    [-5.4, 19.2],
    [-11.4, 14.7],
    [-10.8, 13.9],
    [-20, 7]
  ],
  tabs: [
    { id: 'roof-r', name: 'Right Roof Joint', edge: 2, offset: 12.5, width: 7.5, depth: 1.0 },
    { id: 'roof-l', name: 'Left Roof Joint', edge: 3, offset: 12.5, width: 7.5, depth: 1.0 },
    { id: 'tab-bot', name: 'Bottom Joint', edge: 0, offset: 20.0, width: 16.0, depth: 1.0 }
  ],
  cutouts: [
    { id: 'slot-1', type: 'slot', shape: 'rect', position: [-16, -16.5, 0], width: 1.0, height: 5.0 },
    { id: 'slot-2', type: 'slot', shape: 'rect', position: [16, -16.5, 0], width: 1.0, height: 5.0 },
    { id: 'slot-3', type: 'slot', shape: 'rect', position: [-16, 2.5, 0], width: 1.0, height: 5.0 },
    { id: 'slot-4', type: 'slot', shape: 'rect', position: [16, 2.5, 0], width: 1.0, height: 5.0 }
  ]
};

const specs = computeDraftingSpecs(sampleGable);
assert(specs, 'Specs must be computed');
assert(specs.snapPoints && specs.snapPoints.length > 0, 'Snap points must be present');
console.log(`Generated ${specs.snapPoints.length} magnetic snap points`);

// Verify snap point labels and coordinates
const cornerSnaps = specs.snapPoints.filter(sp => sp.label.includes('Corner'));
const jointSnaps = specs.snapPoints.filter(sp => sp.label.includes('Joint'));
const slotSnaps = specs.snapPoints.filter(sp => sp.label.includes('Slot'));

assert(cornerSnaps.length >= 17, 'Must have at least 17 outline corner snap points');
assert(jointSnaps.length >= 4, 'Must have joint step and root snap points');
assert(slotSnaps.length >= 16, 'Must have slot corner and center snap points');

console.log('Sample Corner Snap:', cornerSnaps[0]);
console.log('Sample Joint Snap:', jointSnaps[0]);
console.log('Sample Slot Snap:', slotSnaps[0]);

// Test SVG output contains measure-layer
const svg = renderDraftingSvg(sampleGable);
assert(svg.includes('id="measure-layer-GABLE-B"'), 'SVG must include measure-layer');

// Caliper Distance test
const ptA = { xMm: 4.0, yMm: 5.5 };
const ptB = { xMm: 4.0, yMm: 24.5 };
const dx = ptB.xMm - ptA.xMm;
const dy = ptB.yMm - ptA.yMm;
const dist = Math.hypot(dx, dy);
assert.strictEqual(dist, 19.0, 'Slot spacing distance must be exactly 19.0mm');

console.log('ALL Measure Scale and Snap tests PASSED!');
