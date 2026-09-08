import { SimpleHouseModelData } from '../js/models/simple-house.js';
import { ConnectorStandards } from '../js/core/connectors.js';
import { ConstructionObject } from '../js/models/model-schema.js';
import { PhysicalValidator } from '../js/validation/validator.js';

// Define authoritative joints for SimpleHouse
const houseJoints = [
  // Floor foundation mortise-tenons
  { id: 'J-H01-H02', sourcePart: 'H-02', targetPart: 'H-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 50, depth: 3.0 }, position: [0, 35], receiverAxis: 'X' },
  { id: 'J-H01-H03', sourcePart: 'H-03', targetPart: 'H-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 50, depth: 3.0 }, position: [0, -35], receiverAxis: 'X' },
  { id: 'J-H01-H04', sourcePart: 'H-04', targetPart: 'H-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 40, depth: 3.0 }, position: [-35, 0], receiverAxis: 'Y' },
  { id: 'J-H01-H05', sourcePart: 'H-05', targetPart: 'H-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 40, depth: 3.0 }, position: [35, 0], receiverAxis: 'Y' },

  // Wall corner interlocking tabs (H-04 and H-05 into H-02 and H-03)
  { id: 'J-H02-H04', sourcePart: 'H-04', targetPart: 'H-02', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 20, depth: 3.0 }, position: [-35, -10], receiverAxis: 'Y', connectorAxis: 'Y' },
  { id: 'J-H02-H05', sourcePart: 'H-05', targetPart: 'H-02', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 20, depth: 3.0 }, position: [35, -10], receiverAxis: 'Y', connectorAxis: 'Y' },
  { id: 'J-H03-H04', sourcePart: 'H-04', targetPart: 'H-03', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 20, depth: 3.0 }, position: [-35, -10], receiverAxis: 'Y', connectorAxis: 'Y' },
  { id: 'J-H03-H05', sourcePart: 'H-05', targetPart: 'H-03', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 20, depth: 3.0 }, position: [35, -10], receiverAxis: 'Y', connectorAxis: 'Y' },

  // Roof ridge apex contact
  { id: 'J-H07-H08', sourcePart: 'H-07', targetPart: 'H-08', type: 'contact', connectionType: 'roof-ridge' },

  // Roof resting on front and rear gable walls
  { id: 'J-H02-H07', sourcePart: 'H-07', targetPart: 'H-02', type: 'contact', connectionType: 'roof-gable' },
  { id: 'J-H02-H08', sourcePart: 'H-08', targetPart: 'H-02', type: 'contact', connectionType: 'roof-gable' },
  { id: 'J-H03-H07', sourcePart: 'H-07', targetPart: 'H-03', type: 'contact', connectionType: 'roof-gable' },
  { id: 'J-H03-H08', sourcePart: 'H-08', targetPart: 'H-03', type: 'contact', connectionType: 'roof-gable' },

  // Ridge cap beam sitting on top of the ridge
  { id: 'J-H07-H09', sourcePart: 'H-09', targetPart: 'H-07', type: 'contact', connectionType: 'ridge-cap' },
  { id: 'J-H08-H09', sourcePart: 'H-09', targetPart: 'H-08', type: 'contact', connectionType: 'ridge-cap' },

  // Chimney tab to right roof
  { id: 'J-H08-H10', sourcePart: 'H-10', targetPart: 'H-08', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 10, depth: 3.0 }, position: [0, 18], receiverAxis: 'X', connectorAxis: 'X' },

  // Door opening detail
  { id: 'J-H02-H06', sourcePart: 'H-06', targetPart: 'H-02', type: 'contact', connectionType: 'doorway' },

  // Corner gusset supports
  { id: 'J-H02-H11', sourcePart: 'H-11', targetPart: 'H-02', type: 'contact' },
  { id: 'J-H04-H11', sourcePart: 'H-11', targetPart: 'H-04', type: 'contact' },
  { id: 'J-H02-H12', sourcePart: 'H-12', targetPart: 'H-02', type: 'contact' },
  { id: 'J-H05-H12', sourcePart: 'H-12', targetPart: 'H-05', type: 'contact' }
];

const testHouse = {
  ...SimpleHouseModelData,
  joints: houseJoints,
  parts: SimpleHouseModelData.parts.map(p => {
    const pCopy = { ...p };

    if (p.id === 'H-01') {
      pCopy.generate2D = (t, kerf, clr) => ({
        outline: [[-50, -40], [50, -40], [50, 40], [-50, 40]],
        cutouts: ConnectorStandards.deriveCutoutsForPart('H-01', houseJoints, t, clr),
        engravings: [{ type: 'rect', x: -40, y: -30, w: 80, h: 60 }]
      });
    }

    if (p.id === 'H-02') {
      pCopy.assembledPos = (t = 3.0) => [0, 40 + t / 2, 35];
      pCopy.generate2D = (t, kerf, clr) => ({
        outline: [
          [-40, -40], [-25, -40], [-25, -40 - t], [25, -40 - t], [25, -40],
          [40, -40], [40, 10], [0, 45], [-40, 10]
        ],
        cutouts: [
          { x: 0, y: -22, w: 20, h: 36, arched: true },
          ...ConnectorStandards.deriveCutoutsForPart('H-02', houseJoints, t, clr)
        ],
        engravings: [{ type: 'circle', x: 0, y: 22, r: 8 }]
      });
    }

    if (p.id === 'H-03') {
      pCopy.assembledPos = (t = 3.0) => [0, 40 + t / 2, -35];
      pCopy.generate2D = (t, kerf, clr) => ({
        outline: [
          [-40, -40], [-25, -40], [-25, -40 - t], [25, -40 - t], [25, -40],
          [40, -40], [40, 10], [0, 45], [-40, 10]
        ],
        cutouts: [
          { x: 0, y: -10, w: 16, h: 22, arched: true },
          ...ConnectorStandards.deriveCutoutsForPart('H-03', houseJoints, t, clr)
        ],
        engravings: [{ type: 'circle', x: 0, y: 22, r: 8 }]
      });
    }

    if (p.id === 'H-04') {
      pCopy.assembledPos = (t = 3.0) => [-35, 25 + t / 2, 0];
      pCopy.generate2D = (t) => ({
        outline: [
          [-35, -25], [-20, -25], [-20, -25 - t], [20, -25 - t], [20, -25],
          [35, -25], [35, -20], [35 + t, -20], [35 + t, 0], [35, 0], [35, 25],
          [-35, 25], [-35, 0], [-35 - t, 0], [-35 - t, -20], [-35, -20]
        ],
        cutouts: [
          { x: -16, y: 2, w: 14, h: 18, arched: true },
          { x: 16, y: 2, w: 14, h: 18, arched: true }
        ],
        engravings: [{ type: 'line', x1: -30, y1: -18, x2: 30, y2: -18 }]
      });
    }

    if (p.id === 'H-05') {
      pCopy.assembledPos = (t = 3.0) => [35, 25 + t / 2, 0];
      pCopy.generate2D = (t) => ({
        outline: [
          [-35, -25], [-20, -25], [-20, -25 - t], [20, -25 - t], [20, -25],
          [35, -25], [35, -20], [35 + t, -20], [35 + t, 0], [35, 0], [35, 25],
          [-35, 25], [-35, 0], [-35 - t, 0], [-35 - t, -20], [-35, -20]
        ],
        cutouts: [
          { x: -16, y: 2, w: 14, h: 18, arched: true },
          { x: 16, y: 2, w: 14, h: 18, arched: true }
        ],
        engravings: [{ type: 'line', x1: -30, y1: -18, x2: 30, y2: -18 }]
      });
    }

    if (p.id === 'H-06') pCopy.assembledPos = (t = 3.0) => [0, 18.5 + t / 2, 36];

    if (p.id === 'H-07') {
      pCopy.assembledPos = (t = 3.0) => [-20 - (t / 2) * 0.6586, 67.5 + t / 2 + (t / 2) * 0.7525, 0];
      pCopy.assembledRot = [-Math.PI / 2, 0, Math.PI / 4.37];
      pCopy.generate2D = (t, kerf, clr) => ({
        outline: [[-28, -45], [28, -45], [28, 45], [-28, 45]],
        cutouts: ConnectorStandards.deriveCutoutsForPart('H-07', houseJoints, t, clr),
        engravings: []
      });
    }

    if (p.id === 'H-08') {
      pCopy.assembledPos = (t = 3.0) => [20 + (t / 2) * 0.6586, 67.5 + t / 2 + (t / 2) * 0.7525, 0];
      pCopy.assembledRot = [-Math.PI / 2, 0, -Math.PI / 4.37];
      pCopy.generate2D = (t, kerf, clr) => ({
        outline: [[-28, -45], [28, -45], [28, 45], [-28, 45]],
        cutouts: ConnectorStandards.deriveCutoutsForPart('H-08', houseJoints, t, clr),
        engravings: []
      });
    }

    if (p.id === 'H-09') {
      pCopy.assembledPos = (t = 3.0) => [0, 85 + 7 + t, 0];
      pCopy.assembledRot = [0, Math.PI / 2, 0];
    }

    if (p.id === 'H-10') {
      pCopy.assembledPos = (t = 3.0) => [20, 80 + t, 18];
      pCopy.assembledRot = [0, 0, 0];
    }

    if (p.id === 'H-11') pCopy.assembledPos = (t = 3.0) => [-30, 20 + t / 2, 25];
    if (p.id === 'H-12') pCopy.assembledPos = (t = 3.0) => [30, 20 + t / 2, 25];

    return pCopy;
  })
};

const obj = new ConstructionObject(testHouse);

[3.0, 4.0, 5.0].forEach(t => {
  const res = PhysicalValidator.auditModel(obj, t);
  console.log(`SimpleHouse ${t}mm: ${res.isPassing ? 'PASS' : 'FAIL'} (errors: ${res.errorCount}, warnings: ${res.warningCount})`);
  if (!res.isPassing) {
    console.log('Errors:', res.issues.filter(i => i.level === 'ERROR'));
  }
});
