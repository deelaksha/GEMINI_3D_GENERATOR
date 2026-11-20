/**
 * Canonical Reference Model: Level 1 Starter House (12 Pieces)
 * Section 22 & 36 of Master Context: Proves universal, reusable modularity.
 */

import { ConnectorStandards } from '../core/connectors.js';

export const SimpleHouseModelData = {
  id: 'simple-house',
  name: 'Country Gable House',
  category: 'Residential / Starter',
  description: '12-piece introductory zero-glue architectural puzzle with interlocking mortise-and-tenon walls, pitched roof, and gabled chimney.',
  difficulty: 'Level 1 — Beginner (12 parts)',
  joints: [
    // Floor foundation mortise-tenons
    { id: 'J-H01-H02', sourcePart: 'H-02', targetPart: 'H-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 50, depth: 3.0 }, position: [0, -35], receiverAxis: 'X' },
    { id: 'J-H01-H03', sourcePart: 'H-03', targetPart: 'H-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 50, depth: 3.0 }, position: [0, 35], receiverAxis: 'X' },
    { id: 'J-H01-H04', sourcePart: 'H-04', targetPart: 'H-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 40, depth: 3.0 }, position: [-35, 0], receiverAxis: 'Y' },
    { id: 'J-H01-H05', sourcePart: 'H-05', targetPart: 'H-01', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 40, depth: 3.0 }, position: [35, 0], receiverAxis: 'Y' },

    // Wall corner interlocking tabs (H-04 and H-05 into H-02 and H-03)
    { id: 'J-H02-H04', sourcePart: 'H-04', targetPart: 'H-02', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 20, depth: 3.0 }, position: [-35, -25], receiverAxis: 'Y', connectorAxis: 'Y' },
    { id: 'J-H02-H05', sourcePart: 'H-05', targetPart: 'H-02', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 20, depth: 3.0 }, position: [35, -25], receiverAxis: 'Y', connectorAxis: 'Y' },
    { id: 'J-H03-H04', sourcePart: 'H-04', targetPart: 'H-03', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 20, depth: 3.0 }, position: [35, -25], receiverAxis: 'Y', connectorAxis: 'Y' },
    { id: 'J-H03-H05', sourcePart: 'H-05', targetPart: 'H-03', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 20, depth: 3.0 }, position: [-35, -25], receiverAxis: 'Y', connectorAxis: 'Y' },

    // Roof ridge apex contact
    { id: 'J-H07-H08', sourcePart: 'H-07', targetPart: 'H-08', type: 'contact', connectionType: 'roof-ridge', worldPos: [0, 85, 0] },

    // Roof resting on front and rear gable walls
    { id: 'J-H02-H07', sourcePart: 'H-07', targetPart: 'H-02', type: 'contact', connectionType: 'roof-gable', worldPos: [-20, 68, 35] },
    { id: 'J-H02-H08', sourcePart: 'H-08', targetPart: 'H-02', type: 'contact', connectionType: 'roof-gable', worldPos: [20, 68, 35] },
    { id: 'J-H03-H07', sourcePart: 'H-07', targetPart: 'H-03', type: 'contact', connectionType: 'roof-gable', worldPos: [-20, 68, -35] },
    { id: 'J-H03-H08', sourcePart: 'H-08', targetPart: 'H-03', type: 'contact', connectionType: 'roof-gable', worldPos: [20, 68, -35] },

    // Ridge cap beam sitting on top of the ridge
    { id: 'J-H07-H09', sourcePart: 'H-09', targetPart: 'H-07', type: 'contact', connectionType: 'ridge-cap', worldPos: [0, 88, 0] },
    { id: 'J-H08-H09', sourcePart: 'H-09', targetPart: 'H-08', type: 'contact', connectionType: 'ridge-cap', worldPos: [0, 88, 0] },

    // Chimney tab to right roof
    { id: 'J-H08-H10', sourcePart: 'H-10', targetPart: 'H-08', type: 'mortise-tenon', sourceConnector: { type: 'tab', width: 10, depth: 3.0 }, position: [0, -18], receiverAxis: 'X', connectorAxis: 'X', worldPos: [20, 80, 18] },

    // Door opening detail
    { id: 'J-H02-H06', sourcePart: 'H-06', targetPart: 'H-02', type: 'contact', connectionType: 'doorway', worldPos: [0, 18, 36] },

    // Corner gusset supports
    { id: 'J-H02-H11', sourcePart: 'H-11', targetPart: 'H-02', type: 'contact', worldPos: [-30, 21.5, 34] },
    { id: 'J-H04-H11', sourcePart: 'H-11', targetPart: 'H-04', type: 'contact', worldPos: [-35, 21.5, 25] },
    { id: 'J-H02-H12', sourcePart: 'H-12', targetPart: 'H-02', type: 'contact', worldPos: [30, 21.5, 34] },
    { id: 'J-H05-H12', sourcePart: 'H-12', targetPart: 'H-05', type: 'contact', worldPos: [35, 21.5, 25] }
  ],
  cameraBookmarks: [
    { name: 'Isometric View', eye: [120, 110, 140], target: [0, 25, 0], dist: 220 },
    { name: 'Front Porch View', eye: [0, 20, 120], target: [0, 20, 0], dist: 130, select: 'H-06' },
    { name: 'Roof Pitch View', eye: [50, 80, 50], target: [0, 35, 0], dist: 140, select: 'H-07' }
  ],
  assemblySteps: [
    {
      num: 0,
      title: 'Full House Assembly (12 Parts)',
      desc: 'Finished country house with chimney and pitched roof.'
    },
    {
      num: 1,
      title: 'Foundation Floor & Front Door',
      desc: 'Lay the slotted foundation baseplate (H-01) flat and hinge or attach the front door panel (H-06).',
      parts: ['H-01', 'H-06']
    },
    {
      num: 2,
      title: 'Perimeter Wall Enclosure',
      desc: 'Slot the front wall (H-02), rear wall (H-03), left window wall (H-04), and right window wall (H-05) into the baseplate.',
      parts: ['H-02', 'H-03', 'H-04', 'H-05']
    },
    {
      num: 3,
      title: 'Internal Structural Braces',
      desc: 'Lock corner diagonal gusset braces (H-11, H-12) to square the wall frame against lateral deflection.',
      parts: ['H-11', 'H-12']
    },
    {
      num: 4,
      title: 'Pitched Roof Panels & Ridge Beam',
      desc: 'Position left roof slope (H-07) and right roof slope (H-08), interlocking them with ridge beam (H-09).',
      parts: ['H-07', 'H-08', 'H-09']
    },
    {
      num: 5,
      title: 'Gabled Chimney Finial',
      desc: 'Insert the interlocking gabled chimney (H-10) into the right roof slot to finish the build.',
      parts: ['H-10']
    }
  ],
  manufacturingSheets: [
    {
      sheetNum: 1,
      name: 'house_sheet_01.svg',
      desc: 'Complete 12-part layout nested onto a single 300x200mm cutting sheet.',
      sheetW: 320,
      sheetH: 220,
      layout: {
        'H-01': { x: 70, y: 60, r: 0 },
        'H-02': { x: 190, y: 55, r: 0 },
        'H-03': { x: 270, y: 55, r: 0 },
        'H-04': { x: 60, y: 155, r: 0 },
        'H-05': { x: 140, y: 155, r: 0 },
        'H-06': { x: 210, y: 130, r: 0 },
        'H-07': { x: 270, y: 140, r: 0 },
        'H-08': { x: 270, y: 190, r: 0 },
        'H-09': { x: 190, y: 185, r: 0 },
        'H-10': { x: 220, y: 185, r: 0 },
        'H-11': { x: 20, y: 200, r: 0 },
        'H-12': { x: 50, y: 200, r: 0 }
      }
    }
  ],
  parts: [
    {
      id: 'H-01',
      fileName: 'H-01_foundation_floor.svg',
      name: 'Foundation Floor Plate',
      category: 'Foundation',
      color: '#8c6239',
      step: 1,
      width: 100,
      length: 80,
      sheet: 1,
      fileSizeKB: '1.4 KB',
      assembledPos: [0, 0, 0],
      assembledRot: [-Math.PI / 2, 0, 0],
      explodeVec: [0, -35, 0],
      generate2D: (t, kerf, clr) => ({
        outline: [
          [-50, -40], [50, -40], [50, 40], [-50, 40]
        ],
        cutouts: ConnectorStandards.deriveCutoutsForPart('H-01', SimpleHouseModelData.joints, t, clr),
        engravings: [
          { type: 'rect', x: -40, y: -30, w: 80, h: 60 }
        ]
      }),
      connections: ['H-02', 'H-03', 'H-04', 'H-05', 'H-06']
    },
    {
      id: 'H-02',
      fileName: 'H-02_front_gabled_wall.svg',
      name: 'Front Gabled Wall & Doorframe',
      category: 'Structural',
      color: '#d4a373',
      step: 2,
      width: 80,
      length: 85,
      sheet: 1,
      fileSizeKB: '1.8 KB',
      assembledPos: (t = 3.0) => [0, 40 + t / 2, 35],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 45],
      generate2D: (t, kerf, clr) => ({
        outline: [
          [-40, -40], [-25, -40], [-25, -40 - t], [25, -40 - t], [25, -40],
          [40, -40], [40, 10], [0, 45], [-40, 10]
        ],
        cutouts: [
          { x: 0, y: -22, w: 20, h: 36, arched: true },
          ...ConnectorStandards.deriveCutoutsForPart('H-02', SimpleHouseModelData.joints, t, clr)
        ],
        engravings: [{ type: 'circle', x: 0, y: 22, r: 8 }]
      }),
      connections: ['H-01', 'H-04', 'H-05', 'H-06', 'H-07', 'H-08', 'H-09']
    },
    {
      id: 'H-03',
      fileName: 'H-03_rear_gabled_wall.svg',
      name: 'Rear Gabled Wall',
      category: 'Structural',
      color: '#d4a373',
      step: 2,
      width: 80,
      length: 85,
      sheet: 1,
      fileSizeKB: '1.6 KB',
      assembledPos: (t = 3.0) => [0, 40 + t / 2, -35],
      assembledRot: [0, Math.PI, 0],
      explodeVec: [0, 0, -45],
      generate2D: (t, kerf, clr) => ({
        outline: [
          [-40, -40], [-25, -40], [-25, -40 - t], [25, -40 - t], [25, -40],
          [40, -40], [40, 10], [0, 45], [-40, 10]
        ],
        cutouts: [
          { x: 0, y: -10, w: 16, h: 22, arched: true },
          ...ConnectorStandards.deriveCutoutsForPart('H-03', SimpleHouseModelData.joints, t, clr)
        ],
        engravings: [{ type: 'circle', x: 0, y: 22, r: 8 }]
      }),
      connections: ['H-01', 'H-04', 'H-05', 'H-07', 'H-08', 'H-09']
    },
    {
      id: 'H-04',
      fileName: 'H-04_left_window_wall.svg',
      name: 'Left Wall with Windows',
      category: 'Structural',
      color: '#c99a6b',
      step: 2,
      width: 70,
      length: 50,
      sheet: 1,
      fileSizeKB: '1.4 KB',
      assembledPos: (t = 3.0) => [-35, 25 + t / 2, 0],
      assembledRot: [0, Math.PI / 2, 0],
      explodeVec: [-45, 0, 0],
      generate2D: (t) => ({
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
      }),
      connections: ['H-01', 'H-02', 'H-03', 'H-07', 'H-11']
    },
    {
      id: 'H-05',
      fileName: 'H-05_right_window_wall.svg',
      name: 'Right Wall with Windows',
      category: 'Structural',
      color: '#c99a6b',
      step: 2,
      width: 70,
      length: 50,
      sheet: 1,
      fileSizeKB: '1.4 KB',
      assembledPos: (t = 3.0) => [35, 25 + t / 2, 0],
      assembledRot: [0, -Math.PI / 2, 0],
      explodeVec: [45, 0, 0],
      generate2D: (t) => ({
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
      }),
      connections: ['H-01', 'H-02', 'H-03', 'H-08', 'H-12']
    },
    {
      id: 'H-06',
      fileName: 'H-06_front_door.svg',
      name: 'Paneled Front Entrance Door',
      category: 'Details',
      color: '#a16207',
      step: 1,
      width: 18,
      length: 34,
      sheet: 1,
      fileSizeKB: '1.1 KB',
      assembledPos: (t = 3.0) => [0, 18.5 + t / 2, 36],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 55],
      generate2D: () => ({
        outline: [[-9, -17], [9, -17], [9, 17], [-9, 17]],
        cutouts: [],
        engravings: [
          { type: 'circle', x: 6, y: 0, r: 1.5 },
          { type: 'rect', x: -6, y: 2, w: 12, h: 10 },
          { type: 'rect', x: -6, y: -14, w: 12, h: 10 }
        ]
      }),
      connections: ['H-01', 'H-02']
    },
    {
      id: 'H-07',
      fileName: 'H-07_roof_left.svg',
      name: 'Left Pitch Gabled Roof',
      category: 'Roof',
      color: '#9c6644',
      step: 4,
      width: 90,
      length: 60,
      sheet: 1,
      fileSizeKB: '1.5 KB',
      assembledPos: (t = 3.0) => [-20 - (t / 2) * 0.6586, 67.5 + t / 2 + (t / 2) * 0.7525, 0],
      assembledRot: [-Math.PI / 2, -Math.PI / 4.37, 0], // THREE Euler XYZ: lay flat, then pitch the slope
      explodeVec: [-35, 35, 0],
      generate2D: (t, kerf, clr) => ({
        outline: [[-28, -45], [28, -45], [28, 45], [-28, 45]],
        cutouts: ConnectorStandards.deriveCutoutsForPart('H-07', SimpleHouseModelData.joints, t, clr),
        engravings: [
          { type: 'line', x1: -20, y1: -35, x2: 20, y2: -35 },
          { type: 'line', x1: -20, y1: 0, x2: 20, y2: 0 },
          { type: 'line', x1: -20, y1: 35, x2: 20, y2: 35 }
        ]
      }),
      connections: ['H-02', 'H-03', 'H-08', 'H-09']
    },
    {
      id: 'H-08',
      fileName: 'H-08_roof_right.svg',
      name: 'Right Pitch Gabled Roof',
      category: 'Roof',
      color: '#9c6644',
      step: 4,
      width: 90,
      length: 60,
      sheet: 1,
      fileSizeKB: '1.6 KB',
      assembledPos: (t = 3.0) => [20 + (t / 2) * 0.6586, 67.5 + t / 2 + (t / 2) * 0.7525, 0],
      assembledRot: [-Math.PI / 2, Math.PI / 4.37, 0], // THREE Euler XYZ: lay flat, then pitch the slope
      explodeVec: [35, 35, 0],
      generate2D: (t, kerf, clr) => ({
        outline: [[-28, -45], [28, -45], [28, 45], [-28, 45]],
        cutouts: ConnectorStandards.deriveCutoutsForPart('H-08', SimpleHouseModelData.joints, t, clr),
        engravings: [
          { type: 'line', x1: -20, y1: -35, x2: 20, y2: -35 },
          { type: 'line', x1: -20, y1: 0, x2: 20, y2: 0 },
          { type: 'line', x1: -20, y1: 35, x2: 20, y2: 35 }
        ]
      }),
      connections: ['H-02', 'H-03', 'H-07', 'H-09', 'H-10']
    },
    {
      id: 'H-09',
      fileName: 'H-09_roof_ridge_beam.svg',
      name: 'Locking Ridge Cap Beam',
      category: 'Roof',
      color: '#78350f',
      step: 4,
      width: 94,
      length: 14,
      sheet: 1,
      fileSizeKB: '1.2 KB',
      assembledPos: (t = 3.0) => [0, 85 + 7 + t, 0],
      assembledRot: [0, Math.PI / 2, 0],
      explodeVec: [0, 45, 0],
      generate2D: (t) => ({
        outline: [
          [-47, -7], [-47, 7], [47, 7], [47, -7]
        ],
        cutouts: [
          { x: -30, y: 0, w: t + 0.1, h: 8 },
          { x: 30, y: 0, w: t + 0.1, h: 8 }
        ],
        engravings: []
      }),
      connections: ['H-02', 'H-03', 'H-07', 'H-08']
    },
    {
      id: 'H-10',
      fileName: 'H-10_gabled_chimney.svg',
      name: 'Brickwork Gabled Chimney',
      category: 'Details',
      color: '#b91c1c',
      step: 5,
      width: 18,
      length: 32,
      sheet: 1,
      fileSizeKB: '1.2 KB',
      assembledPos: (t = 3.0) => [20, 80 + t, 18],
      assembledRot: [0, 0, 0],
      explodeVec: [24, 45, 18],
      generate2D: (t) => ({
        outline: [
          [-9, -16], [-5, -16], [-5, -16 - t], [5, -16 - t], [5, -16],
          [9, -16], [9, 16], [-9, 16]
        ],
        cutouts: [],
        engravings: [
          { type: 'line', x1: -7, y1: -6, x2: 7, y2: -6 },
          { type: 'line', x1: -7, y1: 2, x2: 7, y2: 2 },
          { type: 'line', x1: -7, y1: 10, x2: 7, y2: 10 }
        ]
      }),
      connections: ['H-08']
    },
    {
      id: 'H-11',
      fileName: 'H-11_corner_brace_left.svg',
      name: 'Front-Left Triangular Gusset',
      category: 'Support',
      color: '#713f12',
      step: 3,
      width: 24,
      length: 24,
      sheet: 1,
      fileSizeKB: '1.1 KB',
      assembledPos: (t = 3.0) => [-30, 20 + t / 2, 25],
      assembledRot: [0, Math.PI / 4, 0],
      explodeVec: [-38, 20, 40],
      generate2D: () => ({
        outline: [[-12, -12], [12, -12], [-12, 12]],
        cutouts: [{ x: -5, y: -5, w: 5, h: 5, arched: true }],
        engravings: []
      }),
      connections: ['H-02', 'H-04']
    },
    {
      id: 'H-12',
      fileName: 'H-12_corner_brace_right.svg',
      name: 'Front-Right Triangular Gusset',
      category: 'Support',
      color: '#713f12',
      step: 3,
      width: 24,
      length: 24,
      sheet: 1,
      fileSizeKB: '1.1 KB',
      assembledPos: (t = 3.0) => [30, 20 + t / 2, 25],
      assembledRot: [0, -Math.PI / 4, 0],
      explodeVec: [38, 20, 40],
      generate2D: () => ({
        outline: [[-12, -12], [12, -12], [-12, 12]],
        cutouts: [{ x: -5, y: -5, w: 5, h: 5, arched: true }],
        engravings: []
      }),
      connections: ['H-02', 'H-05']
    }
  ]
};
