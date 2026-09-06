/**
 * Built-in Design Templates
 * Provides instant starter templates for the in-browser Code Editor.
 */

export const TEMPLATES = {
  'minimal-box': {
    id: 'minimal-box',
    name: 'Minimal Interlocking Box (4 Parts)',
    category: 'Starter / Minimal',
    description: 'A clean 4-piece orthogonal interlocking cube with mortise-and-tenon slots illustrating standard slot/tab tolerances.',
    code: `/**
 * Minimal Interlocking Box (4 Parts)
 * Standard 3mm sheet thickness design with 0.1mm fit clearance.
 */
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
      assembledPos: [0, 1.5, 0],
      assembledRot: [-Math.PI / 2, 0, 0],
      generate2D: (t, kerf, clr) => ({
        outline: [
          [-25, -25], [25, -25], [25, 25], [-25, 25]
        ],
        cutouts: [
          { x: 0, y: 20, w: 20, h: (t || 3.0) + (clr || 0.1), tabId: 'N-SLOT' },
          { x: 0, y: -20, w: 20, h: (t || 3.0) + (clr || 0.1), tabId: 'S-SLOT' },
          { x: 20, y: 0, w: (t || 3.0) + (clr || 0.1), h: 20, tabId: 'E-SLOT' }
        ]
      }),
      geometry: {
        outline: [
          [-25, -25], [25, -25], [25, 25], [-25, 25]
        ],
        cutouts: [
          // North slot
          { x: 0, y: 20, w: 20, h: 3.2, tabId: 'N-SLOT' },
          // South slot
          { x: 0, y: -20, w: 20, h: 3.2, tabId: 'S-SLOT' },
          // East slot
          { x: 20, y: 0, w: 3.2, h: 20, tabId: 'E-SLOT' }
        ]
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
      assembledPos: [0, 16.5, 20],
      assembledRot: [0, 0, 0],
      generate2D: (t) => {
        const th = t || 3.0;
        return {
          outline: [
            [-25, 15], [25, 15], [25, -15],
            [10, -15], [10, -15 - th], [-10, -15 - th], [-10, -15],
            [-25, -15]
          ],
          cutouts: []
        };
      },
      geometry: {
        // Wall outline with bottom tenon tab
        outline: [
          [-25, 15], [25, 15], [25, -15],
          [10, -15], [10, -18], [-10, -18], [-10, -15],
          [-25, -15]
        ],
        cutouts: []
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
      assembledPos: [0, 16.5, -20],
      assembledRot: [0, 0, 0],
      generate2D: (t) => {
        const th = t || 3.0;
        return {
          outline: [
            [-25, 15], [25, 15], [25, -15],
            [10, -15], [10, -15 - th], [-10, -15 - th], [-10, -15],
            [-25, -15]
          ],
          cutouts: []
        };
      },
      geometry: {
        // Wall outline with bottom tenon tab
        outline: [
          [-25, 15], [25, 15], [25, -15],
          [10, -15], [10, -18], [-10, -18], [-10, -15],
          [-25, -15]
        ],
        cutouts: []
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
      width: 40,
      length: 30,
      assembledPos: [20, 16.5, 0],
      assembledRot: [0, Math.PI / 2, 0],
      generate2D: (t) => {
        const th = t || 3.0;
        return {
          outline: [
            [-20, 15], [20, 15], [20, -15],
            [10, -15], [10, -15 - th], [-10, -15 - th], [-10, -15],
            [-20, -15]
          ],
          cutouts: []
        };
      },
      geometry: {
        // East wall with bottom tenon tab
        outline: [
          [-20, 15], [20, 15], [20, -15],
          [10, -15], [10, -18], [-10, -18], [-10, -15],
          [-20, -15]
        ],
        cutouts: []
      },
      connections: [
        { partId: 'B-01', type: 'tab-slot', description: 'Bottom tab into Base East slot' }
      ]
    }
  ]
};

export default MinimalBoxModel;
`
  }
};
