/**
 * Built-in Design Templates
 * Provides instant starter templates for the in-browser Code Editor.
 */
import { ConnectorStandards } from '../core/connectors.js';

export const MinimalBoxModel = {
  id: 'minimal-box',
  name: 'Minimal Interlocking Box',
  category: 'Starter / Minimal',
  description: '4-part orthogonal interlocking starter box.',
  difficulty: 'Level 1 — Starter (4 parts)',
  overallDimensions: { width: 60, length: 60, height: 40 },
  cameraBookmarks: [
    { name: 'Isometric View', eye: [80, 70, 90], target: [0, 15, 0], dist: 130 },
    { name: 'Top View', eye: [0, 120, 0], target: [0, 0, 0], dist: 120 }
  ],
  assemblySteps: [
    { num: 0, title: 'Full Box Assembly', desc: 'Assembled 4-part cube.' },
    { num: 1, title: 'Base Floor', desc: 'Lay down slotted base plate.', parts: ['B-01'] },
    { num: 2, title: 'Walls', desc: 'Slot in North, South, and East walls.', parts: ['B-02', 'B-03', 'B-04'] }
  ],
  manufacturingSheets: [
    { sheetNum: 1, name: 'box_sheet_01.svg', desc: 'Single 200x150mm cardstock sheet.', sheetW: 200, sheetH: 150, partIds: ['B-01', 'B-02', 'B-03', 'B-04'] }
  ],
  // Authoritative Single Source of Truth Joints (Requirements 1, 2, 3)
  joints: [
    {
      id: 'J-B02-B01',
      sourcePart: 'B-02',
      connectorPartId: 'B-02',
      targetPart: 'B-01',
      receiverPartId: 'B-01',
      type: 'mortise-tenon',
      sourceConnector: {
        type: 'tab',
        width: 20,
        depth: (t) => t
      },
      tabWidth: 20,
      tabDepth: (t) => t,
      connectorAxis: 'X',
      receiverAxis: 'X',
      position: [0, -20],
      insertionDirection: [0, -1, 0]
    },
    {
      id: 'J-B03-B01',
      sourcePart: 'B-03',
      connectorPartId: 'B-03',
      targetPart: 'B-01',
      receiverPartId: 'B-01',
      type: 'mortise-tenon',
      sourceConnector: {
        type: 'tab',
        width: 20,
        depth: (t) => t
      },
      tabWidth: 20,
      tabDepth: (t) => t,
      connectorAxis: 'X',
      receiverAxis: 'X',
      position: [0, 20],
      insertionDirection: [0, -1, 0]
    },
    {
      id: 'J-B04-B01',
      sourcePart: 'B-04',
      connectorPartId: 'B-04',
      targetPart: 'B-01',
      receiverPartId: 'B-01',
      type: 'mortise-tenon',
      sourceConnector: {
        type: 'tab',
        width: 20,
        depth: (t) => t
      },
      tabWidth: 20,
      tabDepth: (t) => t,
      connectorAxis: 'X',
      receiverAxis: 'Y',
      position: [20, 0],
      insertionDirection: [0, -1, 0]
    }
  ],
  parts: [
    {
      id: 'B-01',
      fileName: 'part_b01_base.svg',
      name: 'Base Floor Plate',
      category: 'Foundation',
      step: 1,
      sheet: 1,
      color: '#0284c7',
      thickness: 3.0,
      width: 50,
      length: 50,
      assembledPos: (t = 3.0) => [0, 0, 0],
      assembledRot: [-Math.PI / 2, 0, 0],
      generate2D: (t = 3.0, kerf = 0.15, clr = 0.10) => {
        const th = t || 3.0;
        const c = clr !== undefined ? clr : 0.10;
        const jList = MinimalBoxModel.joints.filter(j => j.targetPart === 'B-01' || j.receiverPartId === 'B-01');
        return {
          outline: [
            [-25, -25], [25, -25], [25, 25], [-25, 25]
          ],
          cutouts: jList.map(j => {
            const slot = ConnectorStandards.deriveReceiverSlot(j, th, c);
            return {
              x: j.position[0],
              y: j.position[1],
              w: slot.w,
              h: slot.h,
              jointId: j.id
            };
          })
        };
      },
      connections: [
        { partId: 'B-02', type: 'slot-tab', description: 'North Wall Tab into Base North Slot' },
        { partId: 'B-03', type: 'slot-tab', description: 'South Wall Tab into Base South Slot' },
        { partId: 'B-04', type: 'slot-tab', description: 'East Wall Tab into Base East Slot' }
      ]
    },
    {
      id: 'B-02',
      fileName: 'part_b02_north_wall.svg',
      name: 'North Wall',
      category: 'Wall',
      step: 2,
      sheet: 1,
      color: '#d97706',
      thickness: 3.0,
      width: 50,
      length: 30,
      assembledPos: (t = 3.0) => [0, 15 + t / 2, 20],
      assembledRot: [0, 0, 0],
      generate2D: (t = 3.0) => {
        const th = t || 3.0;
        const j = MinimalBoxModel.joints.find(j => j.sourcePart === 'B-02' || j.connectorPartId === 'B-02');
        const hwTab = (j?.tabWidth || 20) / 2;
        return {
          outline: [
            [-25, 15], [25, 15], [25, -15],
            [hwTab, -15], [hwTab, -15 - th], [-hwTab, -15 - th], [-hwTab, -15],
            [-25, -15]
          ],
          cutouts: []
        };
      },
      connections: [
        { partId: 'B-01', type: 'tab-slot', description: 'Bottom tab into Base North slot' }
      ]
    },
    {
      id: 'B-03',
      fileName: 'part_b03_south_wall.svg',
      name: 'South Wall',
      category: 'Wall',
      step: 2,
      sheet: 1,
      color: '#d97706',
      thickness: 3.0,
      width: 50,
      length: 30,
      assembledPos: (t = 3.0) => [0, 15 + t / 2, -20],
      assembledRot: [0, 0, 0],
      generate2D: (t = 3.0) => {
        const th = t || 3.0;
        const j = MinimalBoxModel.joints.find(j => j.sourcePart === 'B-03' || j.connectorPartId === 'B-03');
        const hwTab = (j?.tabWidth || 20) / 2;
        return {
          outline: [
            [-25, 15], [25, 15], [25, -15],
            [hwTab, -15], [hwTab, -15 - th], [-hwTab, -15 - th], [-hwTab, -15],
            [-25, -15]
          ],
          cutouts: []
        };
      },
      connections: [
        { partId: 'B-01', type: 'tab-slot', description: 'Bottom tab into Base South slot' }
      ]
    },
    {
      id: 'B-04',
      fileName: 'part_b04_east_wall.svg',
      name: 'East Wall',
      category: 'Wall',
      step: 2,
      sheet: 1,
      color: '#059669',
      thickness: 3.0,
      width: 37,
      length: 30,
      assembledPos: (t = 3.0) => [20, 15 + t / 2, 0],
      assembledRot: [0, Math.PI / 2, 0],
      generate2D: (t = 3.0) => {
        const th = t || 3.0;
        // Parametric width: clearance span between inner faces of North Wall (z=20-th/2) and South Wall (z=-20+th/2) is 40 - th
        const wallWidth = 40 - th;
        const hw = wallWidth / 2;
        const j = MinimalBoxModel.joints.find(j => j.sourcePart === 'B-04' || j.connectorPartId === 'B-04');
        const hwTab = (j?.tabWidth || 20) / 2;
        return {
          outline: [
            [-hw, 15], [hw, 15], [hw, -15],
            [hwTab, -15], [hwTab, -15 - th], [-hwTab, -15 - th], [-hwTab, -15],
            [-hw, -15]
          ],
          cutouts: []
        };
      },
      connections: [
        { partId: 'B-01', type: 'tab-slot', description: 'Bottom tab into Base East slot' }
      ]
    }
  ]
};

export const TEMPLATES = {
  'minimal-box': {
    id: 'minimal-box',
    name: 'Minimal Interlocking Box (4 Parts)',
    category: 'Starter / Minimal',
    description: 'A clean 4-piece orthogonal interlocking cube with mortise-and-tenon slots illustrating standard slot/tab tolerances.',
    model: MinimalBoxModel
  }
};

export default MinimalBoxModel;
