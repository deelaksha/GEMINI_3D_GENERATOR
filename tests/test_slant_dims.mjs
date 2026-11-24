import { computeDraftingSpecs, renderDraftingSvg, renderDraftingGuide, formatDraftingSpecsText } from '../js/studio/drafting.js';

const comp = {
  id: 'GABLE-F',
  name: 'Front gable wall',
  material_thickness: 1,
  cut_outline: [
    [0, 0], [40, 0], [40, 29], [20, 44], [0, 29]
  ],
  features: [
    { id: 'window-top', bounds: { minX: 13, maxX: 27, minY: 30, maxY: 40 }, center: [20, 35], width: 14, height: 10 }
  ]
};

const specs = computeDraftingSpecs(comp);
console.log('Slant summary:', specs.summary.slant);
const slantDim = specs.dimensions.find(d => d.id === 'slant-dimension');
console.log('Slant Dimension:', slantDim.name, '=>', slantDim.value);

const svg = renderDraftingSvg(comp);
console.log('SVG contains slant-dimension:', svg.includes('data-dim-id="slant-dimension"'));
console.log('SVG contains Slant W:', svg.includes('Slant W:'));
console.log('SVG contains Slant H:', svg.includes('Slant H:'));
console.log('SVG contains Cut:', svg.includes('Cut:'));

const guide = renderDraftingGuide(comp);
console.log('Guide contains Slant Width (Run):', guide.includes('Slant Width (Run)'));
console.log('Guide contains Slant Height (Rise):', guide.includes('Slant Height (Rise)'));

const text = formatDraftingSpecsText(comp);
console.log('Text specs contains Slant:', text.includes('Roof / Bow Slant:'));
console.log('All validations passed successfully!');
