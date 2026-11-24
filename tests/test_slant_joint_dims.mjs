import assert from 'assert';
import { computeDraftingSpecs, renderDraftingSvg, renderDraftingGuide, formatDraftingSpecsText, formatGraphPointsText } from '../js/studio/drafting.js';

const comp = {
  id: 'GABLE-B',
  name: 'Back gable wall',
  material_thickness: 6,
  outline: [[-85.0, -119.6617], [85.0, -119.6617], [85.0, 48.3383], [0.0, 119.6618], [-85.0, 48.3383]],
  cut_outline: [
    [-85.0, -119.6617], [-39.5, -119.6617], [-39.5, -125.6617], [39.5, -125.6617], [39.5, -119.6617],
    [85.0, -119.6617], [85.0, 48.3383],
    [61.4519, 68.0975], [65.3087, 72.6937], [27.4048, 104.4989], [23.5481, 99.9026],
    [0.0, 119.6618],
    [-23.5480, 99.9026], [-27.4048, 104.4989], [-65.3086, 72.6938], [-61.4519, 68.0975],
    [-85.0, 48.3383]
  ],
  tabs: [
    { id: 'gb-floor-t1', edge: 0, offset: 85.0, width: 79.0, depth: 6.0 },
    { id: 'gb-roofr-t1', edge: 2, offset: 55.48, width: 49.48, depth: 6.0 },
    { id: 'gb-roofl-t1', edge: 3, offset: 55.48, width: 49.48, depth: 6.0 }
  ]
};

console.log('Testing GABLE-B drafting specs...');
const specs = computeDraftingSpecs(comp);

// 1. Verify apexCorner and shoulders
assert.strictEqual(specs.apexCorner.dir, 'top', 'apex dir should be top');
assert.strictEqual(Math.round(specs.apexCorner.shoulderY), 48, 'shoulderY should be around 48.3 mm, not tab tip');
assert.strictEqual(specs.apexCorner.run, 85, 'run should be 85 mm');
assert.strictEqual(Math.round(specs.apexCorner.rise), 71, 'rise should be around 71.3 mm');

// 2. Verify tabs detection
console.log('Detected tabs count:', specs.tabs.length);
assert.strictEqual(specs.tabs.length, 3, 'Should detect exactly 3 tabs (floor, right roof, left roof)');

const floorTab = specs.tabs.find(t => t.id === 'gb-floor-t1');
assert.ok(floorTab, 'Floor tab should be found');
assert.strictEqual(floorTab.width, 79, 'Floor tab width should be 79 mm');
assert.strictEqual(floorTab.depth, 6, 'Floor tab depth should be 6 mm');

const rightRoofTab = specs.tabs.find(t => t.locName.includes('Right Roof'));
assert.ok(rightRoofTab, 'Right roof slant tab should be found');
assert.strictEqual(rightRoofTab.id, 'gb-roofr-t1', 'Right roof tab id should be gb-roofr-t1');
assert.strictEqual(rightRoofTab.isSlant, true, 'Right roof tab should be marked as slant');
assert.strictEqual(rightRoofTab.width, 49.5, 'Right roof tab width should be 49.5 mm');
assert.strictEqual(rightRoofTab.depth, 6, 'Right roof tab depth should be 6 mm');
console.log('rightRoofTab distFromStart:', rightRoofTab.distFromStart, 'distFromEnd:', rightRoofTab.distFromEnd);
assert.ok(Math.abs(rightRoofTab.distFromStart - 30.7) <= 0.2, 'Right roof tab distFromStart should be ~30.7 mm from shoulder');
assert.ok(Math.abs(rightRoofTab.distFromEnd - 30.7) <= 0.2, 'Right roof tab distFromEnd should be ~30.7 mm to apex');
assert.strictEqual(rightRoofTab.startName, 'right shoulder');
assert.strictEqual(rightRoofTab.endName, 'apex peak');

const leftRoofTab = specs.tabs.find(t => t.locName.includes('Left Roof'));
console.log('leftRoofTab distFromStart:', leftRoofTab.distFromStart, 'distFromEnd:', leftRoofTab.distFromEnd);
assert.ok(leftRoofTab, 'Left roof slant tab should be found');
assert.strictEqual(leftRoofTab.id, 'gb-roofl-t1', 'Left roof tab id should be gb-roofl-t1');
assert.strictEqual(leftRoofTab.isSlant, true, 'Left roof tab should be marked as slant');
assert.strictEqual(leftRoofTab.width, 49.5, 'Left roof tab width should be 49.5 mm');
assert.strictEqual(leftRoofTab.depth, 6, 'Left roof tab depth should be 6 mm');
assert.ok(Math.abs(leftRoofTab.distFromStart - 30.7) <= 0.2, 'Left roof tab distFromStart should be ~30.7 mm from left shoulder');
assert.ok(Math.abs(leftRoofTab.distFromEnd - 30.7) <= 0.2, 'Left roof tab distFromEnd should be ~30.7 mm to apex');
assert.strictEqual(leftRoofTab.startName, 'left shoulder');
assert.strictEqual(leftRoofTab.endName, 'apex peak');

// 3. Verify SVG rendering
console.log('Testing SVG blueprint rendering...');
const svg = renderDraftingSvg(comp);
assert.ok(svg.includes('data-dim-id="tab-gb-roofr-t1"'), 'SVG should contain right roof tab dim-group');
assert.ok(svg.includes('data-dim-id="tab-gb-roofl-t1"'), 'SVG should contain left roof tab dim-group');
assert.ok(svg.includes('Joint: 49.5 mm (5.0 cm) · 6 mm'), 'SVG should contain joint width and depth pill');
assert.ok(svg.includes('<polygon class="gap-zone"'), 'SVG should contain gap-zone polygon for tabs');
assert.ok(svg.includes('data-dim-id="slant-dimension"'), 'SVG should still contain slant dimensions');

// 4. Verify Guide rendering
console.log('Testing Guide rendering...');
const guide = renderDraftingGuide(comp);
assert.ok(guide.includes('Edge Finger Tabs &amp; Slant Joints (3 joints)'), 'Guide should include section 3 header');
assert.ok(guide.includes('data-tab="gb-roofr-t1"'), 'Guide should contain data-tab="gb-roofr-t1" row');
assert.ok(guide.includes('data-tab="gb-roofl-t1"'), 'Guide should contain data-tab="gb-roofl-t1" row');
assert.ok(guide.includes('1. Scribe at'), 'Guide should include cutting sequence in table');
assert.ok(guide.includes('Scribe &amp; Cut Slant Roof Joint'), 'Guide should include slant roof joint in walkthrough');

// 5. Verify formatDraftingSpecsText
console.log('Testing plain text specs...');
const text = formatDraftingSpecsText(comp);
assert.ok(text.includes('--- 4. EDGE FINGER TABS & SLANT JOINTS ---'), 'Text should include Section 4 tabs header');
assert.ok(text.includes('gb-roofr-t1'), 'Text should list gb-roofr-t1');
assert.ok(text.includes('gb-roofl-t1'), 'Text should list gb-roofl-t1');
assert.ok(text.includes('Right Roof Slant Joint'), 'Text should list Right Roof Slant Joint');
assert.ok(text.includes('49.5 mm (5.0 cm) x 6 mm'), 'Text should show dimensions');
assert.ok(text.includes('from right shoulder'), 'Text should show scribe distance');

// 6. Verify formatGraphPointsText & graphPoints
console.log('Testing graph coordinates...');
const graphPoints = specs.graphPoints;
const rightRoot1 = graphPoints.find(gp => gp.desc.includes('gb-roofr-t1') || (gp.desc.includes('Right Roof Slant Joint') && gp.desc.includes('scribe root')));
assert.ok(rightRoot1, 'Graph points should label right roof tab scribe root');
console.log('Right root point:', rightRoot1);
assert.ok(rightRoot1.desc.includes('from right shoulder'), 'Graph point desc should include shoulder');
assert.ok(rightRoot1.desc.includes('Start 90° cut'), 'Graph point desc should mention 90° cut');

console.log('ALL slant joint validations PASSED with 100% precision!');
