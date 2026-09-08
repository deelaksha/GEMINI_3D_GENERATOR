import { CathedralModelData } from '../js/models/cathedral.js';
import { ConnectorStandards } from '../js/core/connectors.js';
import { ConstructionObject } from '../js/models/model-schema.js';
import { PhysicalValidator } from '../js/validation/validator.js';

// Build authoritative joints for Cathedral
const cathedralJoints = [
  // CH-01 Baseplate floor mortises
  { id: 'J-CH01-CH02-1', sourcePart: 'CH-02', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 22, depth: 3.0 }, position: [-80, -36], cutoutWidth: 22, cutoutThickness: 3.1 },
  { id: 'J-CH01-CH02-2', sourcePart: 'CH-02', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 22, depth: 3.0 }, position: [-35, -36], cutoutWidth: 22, cutoutThickness: 3.1 },
  { id: 'J-CH01-CH04-1', sourcePart: 'CH-04', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 22, depth: 3.0 }, position: [-80, 36], cutoutWidth: 22, cutoutThickness: 3.1 },
  { id: 'J-CH01-CH04-2', sourcePart: 'CH-04', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 22, depth: 3.0 }, position: [-35, 36], cutoutWidth: 22, cutoutThickness: 3.1 },
  { id: 'J-CH01-CH03', sourcePart: 'CH-03', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 30, depth: 3.0 }, position: [80, -36], cutoutWidth: 30, cutoutThickness: 3.1 },
  { id: 'J-CH01-CH05', sourcePart: 'CH-05', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 30, depth: 3.0 }, position: [80, 36], cutoutWidth: 30, cutoutThickness: 3.1 },
  { id: 'J-CH01-CH08', sourcePart: 'CH-08', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 32, depth: 3.0 }, position: [-115, 0], receiverAxis: 'Y' },
  { id: 'J-CH01-CH09', sourcePart: 'CH-09', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 32, depth: 3.0 }, position: [115, 0], receiverAxis: 'Y' },
  { id: 'J-CH01-CH06', sourcePart: 'CH-06', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 24, depth: 3.0 }, position: [30, -80] },
  { id: 'J-CH01-CH07', sourcePart: 'CH-07', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 24, depth: 3.0 }, position: [30, 80] },
  { id: 'J-CH01-CH10', sourcePart: 'CH-10', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 45, depth: 3.0 }, position: [5, 0], receiverAxis: 'Y' },
  { id: 'J-CH01-CH15', sourcePart: 'CH-15', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 14, depth: 3.0 }, position: [-80, -55] },
  { id: 'J-CH01-CH16', sourcePart: 'CH-16', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 14, depth: 3.0 }, position: [-35, -55] },
  { id: 'J-CH01-CH17', sourcePart: 'CH-17', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 14, depth: 3.0 }, position: [-80, 55] },
  { id: 'J-CH01-CH18', sourcePart: 'CH-18', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 14, depth: 3.0 }, position: [-35, 55] },
  { id: 'J-CH01-CH26', sourcePart: 'CH-26', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 16, depth: 3.0 }, position: [-65, -18], receiverAxis: 'Y' },
  { id: 'J-CH01-CH27', sourcePart: 'CH-27', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 16, depth: 3.0 }, position: [-65, 18], receiverAxis: 'Y' },
  { id: 'J-CH01-CH28', sourcePart: 'CH-28', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 16, depth: 3.0 }, position: [-35, -18], receiverAxis: 'Y' },
  { id: 'J-CH01-CH29', sourcePart: 'CH-29', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 16, depth: 3.0 }, position: [-35, 18], receiverAxis: 'Y' },
  { id: 'J-CH01-CH30', sourcePart: 'CH-30', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 12, depth: 3.0 }, position: [-10, -22] },
  { id: 'J-CH01-CH31', sourcePart: 'CH-31', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 16, depth: 3.0 }, position: [85, 0], receiverAxis: 'Y' },
  { id: 'J-CH01-CH32', sourcePart: 'CH-32', targetPart: 'CH-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 10, depth: 3.0 }, position: [-95, 0], receiverAxis: 'X' },

  // Roof ridge finger joint
  { id: 'J-CH11-CH12', sourcePart: 'CH-11', targetPart: 'CH-12', type: 'edge-finger', connectionType: 'roof-ridge', tabWidth: 30, tabDepth: 3.0 },

  // Transept roof valley abuts
  { id: 'J-CH13-CH11', sourcePart: 'CH-13', targetPart: 'CH-11', type: 'valley-abut', connectionType: 'transept-valley' },
  { id: 'J-CH14-CH12', sourcePart: 'CH-14', targetPart: 'CH-12', type: 'valley-abut', connectionType: 'transept-valley' },

  // Rood screen transverse gable contact to roof underside
  { id: 'J-CH10-CH11', sourcePart: 'CH-10', targetPart: 'CH-11', type: 'contact', connectionType: 'gable-arch' },
  { id: 'J-CH10-CH12', sourcePart: 'CH-10', targetPart: 'CH-12', type: 'contact', connectionType: 'gable-arch' }
];

// Clone CathedralModelData and inject joints and parametric positions
const testCathedral = {
  ...CathedralModelData,
  joints: cathedralJoints,
  parts: CathedralModelData.parts.map(p => {
    const pCopy = { ...p };

    // CH-01 derive cutouts from joints
    if (p.id === 'CH-01') {
      pCopy.generate2D = (t, kerf, clr) => ({
        outline: [
          [-125, -40], [5, -40], [5, -85], [55, -85], [55, -40], [125, -40],
          [125, 40], [55, 40], [55, 85], [5, 85], [5, 40], [-125, 40]
        ],
        cutouts: ConnectorStandards.deriveCutoutsForPart('CH-01', cathedralJoints, t, clr),
        engravings: [
          { type: 'rect', x: -120, y: -35, w: 240, h: 70 },
          { type: 'rect', x: 10, y: -80, w: 40, h: 160 }
        ]
      });
    }

    // Pew backrest cutouts are decorative
    if (['CH-26', 'CH-27', 'CH-28', 'CH-29'].includes(p.id)) {
      pCopy.generate2D = (t) => ({
        outline: [
          [-15, -9], [-8, -9], [-8, -9 - t], [8, -9 - t], [8, -9],
          [15, -9], [15, 9], [-15, 9]
        ],
        cutouts: [{ x: 0, y: 2, w: 20, h: 4, type: 'decorative' }],
        engravings: [{ type: 'line', x1: -12, y1: -2, x2: 12, y2: -2 }]
      });
    }

    // CH-24 Flèche spire cutout margin fix
    if (p.id === 'CH-24') {
      pCopy.generate2D = (t) => ({
        outline: [
          [-12, -32.5], [-6, -32.5], [-6, -32.5 - t], [6, -32.5 - t], [6, -32.5],
          [12, -32.5], [0, 32.5]
        ],
        cutouts: [{ x: 0, y: -8, w: t + 0.1, h: 16 }],
        engravings: [{ type: 'line', x1: 0, y1: 30, x2: 0, y2: 5 }]
      });
    }

    // Vertical parts seated on baseplate CH-01 get parametric +t/2 elevation
    const standingOnBase = [
      'CH-02', 'CH-03', 'CH-04', 'CH-05', 'CH-06', 'CH-07', 'CH-08', 'CH-09', 'CH-10',
      'CH-15', 'CH-16', 'CH-17', 'CH-18', 'CH-26', 'CH-27', 'CH-28', 'CH-29', 'CH-30', 'CH-31', 'CH-32'
    ];
    if (standingOnBase.includes(p.id)) {
      const origPos = Array.isArray(p.assembledPos) ? p.assembledPos : [0, 0, 0];
      pCopy.assembledPos = (t = 3.0) => [origPos[0], origPos[1] + t / 2, origPos[2]];
    }

    // Bell towers: seated on top of CH-08 (parapet Y = 120, center Y = 120 + 45 = 165)
    if (p.id === 'CH-19') pCopy.assembledPos = (t = 3.0) => [-115, 165 + t / 2, -26];
    if (p.id === 'CH-20') pCopy.assembledPos = (t = 3.0) => [-103, 165 + t / 2, -36];
    if (p.id === 'CH-21') pCopy.assembledPos = (t = 3.0) => [-115, 165 + t / 2, 26];
    if (p.id === 'CH-22') pCopy.assembledPos = (t = 3.0) => [-103, 165 + t / 2, 36];

    // CH-11 and CH-12 cutout #2 edge margin fix (y: 20, h: 8)
    if (p.id === 'CH-11' || p.id === 'CH-12') {
      const origGen = p.generate2D;
      pCopy.generate2D = (t, kerf, clr) => {
        const geo = origGen(t, kerf, clr);
        geo.cutouts = [
          { x: 30, y: 15, w: 24, h: t + (clr || 0.1) },
          { x: 100, y: 20, w: t + (clr || 0.1), h: 8 }
        ];
        return geo;
      };
    }

    // CH-13 and CH-14 transept roof length fix: 44mm ([-22, 22]) to abut nave roof without solid penetration
    if (p.id === 'CH-13' || p.id === 'CH-14') {
      pCopy.generate2D = (t) => ({
        outline: [[-24, -22], [24, -22], [24, 22], [-24, 22]],
        cutouts: [],
        engravings: [{ type: 'line', x1: -22, y1: 0, x2: 22, y2: 0 }]
      });
    }

    return pCopy;
  })
};

const obj = new ConstructionObject(testCathedral);

[3.0, 4.0, 5.0].forEach(t => {
  const audit = PhysicalValidator.auditModel(obj, t);
  console.log(`Cathedral ${t}mm: ${audit.isPassing ? 'PASS' : 'FAIL'} (errors: ${audit.errorCount}, warnings: ${audit.warningCount})`);
  if (!audit.isPassing) {
    console.log('Errors:', audit.issues.filter(i => i.level === 'ERROR'));
  }
});
