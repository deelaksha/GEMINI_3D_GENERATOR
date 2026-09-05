/**
 * Authoritative Model Dataset: Grand Gothic Cathedral (32 Pieces)
 * Physical Zero-Glue Modular Assembly Architecture
 */

export const CathedralModelData = {
  id: 'cathedral',
  name: 'Grand Gothic Cathedral',
  category: 'Architectural / Heritage',
  description: '32-piece zero-glue cruciform gothic cathedral featuring flying buttresses, ribbed transepts, nave pews, and flèche spire.',
  difficulty: 'Level 2 — Intermediate (32 parts)',
  cameraBookmarks: [
    { name: 'Isometric View', eye: [180, 160, 220], target: [0, 50, 0], dist: 380 },
    { name: 'West Aisle (Pew View)', eye: [-118, 22, 0], target: [75, 18, 0], dist: 155, select: 'CH-32' },
    { name: 'Mid-Nave Pews', eye: [-45, 18, 0], target: [75, 18, 0], dist: 90, select: 'CH-26' },
    { name: 'Sanctuary High Altar', eye: [30, 20, 0], target: [95, 20, 0], dist: 65, select: 'CH-31' }
  ],
  assemblySteps: [
    {
      num: 0,
      title: 'Full Assembly (All 32 Parts)',
      desc: 'Complete assembled cathedral structure with zero glue.'
    },
    {
      num: 1,
      title: 'Foundation & Nave Liturgical Furnishings',
      desc: 'Insert the nave pew benches (CH-26 to CH-29), pulpit (CH-30), font (CH-32), and high altar (CH-31) into the cruciform baseplate mortises.',
      parts: ['CH-01', 'CH-26', 'CH-27', 'CH-28', 'CH-29', 'CH-30', 'CH-31', 'CH-32']
    },
    {
      num: 2,
      title: 'Nave Side Walls & Sanctuary Apse',
      desc: 'Erect west nave walls (CH-02, CH-04), east choir walls (CH-03, CH-05), rood screen (CH-10), and sanctuary apse (CH-09).',
      parts: ['CH-02', 'CH-03', 'CH-04', 'CH-05', 'CH-09', 'CH-10']
    },
    {
      num: 3,
      title: 'North & South Transept Wings',
      desc: 'Attach cross-arm facades with rose windows (CH-06, CH-07) and gabled transept roofs (CH-13, CH-14).',
      parts: ['CH-06', 'CH-07', 'CH-13', 'CH-14']
    },
    {
      num: 4,
      title: 'External Flying Buttresses',
      desc: 'Slot the 4 diagonal struts (CH-15 to CH-18) into the foundation anchors to absorb outward roof thrust.',
      parts: ['CH-15', 'CH-16', 'CH-17', 'CH-18']
    },
    {
      num: 5,
      title: 'Westwork Towers & Pitched Roofs',
      desc: 'Mount front facade (CH-08), twin bell tower walls (CH-19 to CH-22), and interlock nave roof pitches (CH-11, CH-12).',
      parts: ['CH-08', 'CH-19', 'CH-20', 'CH-21', 'CH-22', 'CH-11', 'CH-12']
    },
    {
      num: 6,
      title: 'Crossing Lantern Tower, Spire & Cross',
      desc: 'Crown the cathedral intersection with lantern tower (CH-23), flèche spire (CH-24), and apex cross finial (CH-25).',
      parts: ['CH-23', 'CH-24', 'CH-25']
    }
  ],
  manufacturingSheets: [
    {
      sheetNum: 1,
      name: 'sheet_01_structure.svg',
      desc: 'Main structural baseplate, perimeter nave walls, facade, apse, and roof planes.',
      sheetW: 400,
      sheetH: 300,
      layout: {
        'CH-01': { x: 130, y: 90, r: 0 },
        'CH-02': { x: 60, y: 220, r: 0 },
        'CH-04': { x: 175, y: 220, r: 0 },
        'CH-03': { x: 270, y: 220, r: 0 },
        'CH-05': { x: 350, y: 220, r: 0 },
        'CH-08': { x: 320, y: 70, r: 0 },
        'CH-09': { x: 260, y: 70, r: 0 },
        'CH-10': { x: 375, y: 70, r: 0 },
        'CH-06': { x: 310, y: 150, r: 0 },
        'CH-07': { x: 365, y: 150, r: 0 },
        'CH-11': { x: 115, y: 275, r: 0 },
        'CH-12': { x: 285, y: 275, r: 0 },
        'CH-13': { x: 40, y: 20, r: 0 },
        'CH-14': { x: 85, y: 20, r: 0 }
      }
    },
    {
      sheetNum: 2,
      name: 'sheet_02_furniture.svg',
      desc: 'Interior nave pews, pulpit, baptismal font, high altar, buttresses, and crossing spire.',
      sheetW: 400,
      sheetH: 300,
      layout: {
        'CH-15': { x: 40, y: 40, r: 0 },
        'CH-16': { x: 80, y: 40, r: 0 },
        'CH-17': { x: 120, y: 40, r: 0 },
        'CH-18': { x: 160, y: 40, r: 0 },
        'CH-19': { x: 210, y: 60, r: 0 },
        'CH-20': { x: 245, y: 60, r: 0 },
        'CH-21': { x: 280, y: 60, r: 0 },
        'CH-22': { x: 315, y: 60, r: 0 },
        'CH-23': { x: 360, y: 40, r: 0 },
        'CH-24': { x: 360, y: 110, r: 0 },
        'CH-25': { x: 360, y: 160, r: 0 },
        'CH-26': { x: 50, y: 120, r: 0 },
        'CH-27': { x: 100, y: 120, r: 0 },
        'CH-28': { x: 150, y: 120, r: 0 },
        'CH-29': { x: 200, y: 120, r: 0 },
        'CH-30': { x: 250, y: 120, r: 0 },
        'CH-31': { x: 300, y: 120, r: 0 },
        'CH-32': { x: 50, y: 180, r: 0 }
      }
    }
  ],
  parts: [
    // GROUP 1: BASEPLATE & FURNITURE
    {
      id: 'CH-01',
      fileName: 'CH-01_foundation_baseplate.svg',
      name: 'Cruciform Foundation Baseplate',
      category: 'Foundation',
      color: '#8c6239',
      step: 1,
      width: 250,
      length: 170,
      sheet: 1,
      fileSizeKB: '2.8 KB',
      assembledPos: [0, 0, 0],
      assembledRot: [-Math.PI / 2, 0, 0],
      explodeVec: [0, -50, 0],
      generate2D: (t, kerf, clr) => ({
        outline: [
          [-125, -40], [5, -40], [5, -85], [55, -85], [55, -40], [125, -40],
          [125, 40], [55, 40], [55, 85], [5, 85], [5, 40], [-125, 40]
        ],
        cutouts: [
          { x: -80, y: -36, w: 22, h: t + clr },
          { x: -35, y: -36, w: 22, h: t + clr },
          { x: -80, y: 36, w: 22, h: t + clr },
          { x: -35, y: 36, w: 22, h: t + clr },
          { x: 80, y: -36, w: 22, h: t + clr },
          { x: 80, y: 36, w: 22, h: t + clr },
          { x: -115, y: 0, w: t + clr, h: 32 },
          { x: 115, y: 0, w: t + clr, h: 32 },
          { x: 30, y: -80, w: 24, h: t + clr },
          { x: 30, y: 80, w: 24, h: t + clr },
          { x: 5, y: 0, w: t + clr, h: 45 },
          { x: -80, y: -55, w: 14, h: t + clr },
          { x: -35, y: -55, w: 14, h: t + clr },
          { x: -80, y: 55, w: 14, h: t + clr },
          { x: -35, y: 55, w: 14, h: t + clr },
          { x: -65, y: -18, w: 16, h: t + clr },
          { x: -65, y: 18, w: 16, h: t + clr },
          { x: -35, y: -18, w: 16, h: t + clr },
          { x: -35, y: 18, w: 16, h: t + clr },
          { x: -10, y: -22, w: 12, h: t + clr },
          { x: 85, y: 0, w: 16, h: t + clr },
          { x: -95, y: 0, w: 10, h: t + clr }
        ],
        engravings: [
          { type: 'rect', x: -120, y: -35, w: 240, h: 70 },
          { type: 'rect', x: 10, y: -80, w: 40, h: 160 }
        ]
      }),
      connections: ['CH-02', 'CH-03', 'CH-04', 'CH-05', 'CH-08', 'CH-09', 'CH-14', 'CH-15', 'CH-16', 'CH-17', 'CH-18', 'CH-26', 'CH-27', 'CH-28', 'CH-29', 'CH-30', 'CH-31', 'CH-32']
    },
    {
      id: 'CH-26',
      fileName: 'CH-26_nave_pew_row_01_left.svg',
      name: 'Nave Pew — Row 1 Left',
      category: 'Interior / Furniture',
      color: '#b08968',
      step: 1,
      width: 30,
      length: 18,
      sheet: 2,
      fileSizeKB: '1.2 KB',
      assembledPos: [-65, 9, -18],
      assembledRot: [0, Math.PI / 2, 0],
      explodeVec: [-65, 30, -35],
      generate2D: (t) => ({
        outline: [
          [-15, -9], [-8, -9], [-8, -9 - t], [8, -9 - t], [8, -9],
          [15, -9], [15, 9], [-15, 9]
        ],
        cutouts: [{ x: 0, y: 2, w: 20, h: 4 }],
        engravings: [{ type: 'line', x1: -12, y1: -2, x2: 12, y2: -2 }]
      }),
      connections: ['CH-01']
    },
    {
      id: 'CH-27',
      fileName: 'CH-27_nave_pew_row_01_right.svg',
      name: 'Nave Pew — Row 1 Right',
      category: 'Interior / Furniture',
      color: '#b08968',
      step: 1,
      width: 30,
      length: 18,
      sheet: 2,
      fileSizeKB: '1.2 KB',
      assembledPos: [-65, 9, 18],
      assembledRot: [0, Math.PI / 2, 0],
      explodeVec: [-65, 30, 35],
      generate2D: (t) => ({
        outline: [
          [-15, -9], [-8, -9], [-8, -9 - t], [8, -9 - t], [8, -9],
          [15, -9], [15, 9], [-15, 9]
        ],
        cutouts: [{ x: 0, y: 2, w: 20, h: 4 }],
        engravings: [{ type: 'line', x1: -12, y1: -2, x2: 12, y2: -2 }]
      }),
      connections: ['CH-01']
    },
    {
      id: 'CH-28',
      fileName: 'CH-28_nave_pew_row_02_left.svg',
      name: 'Nave Pew — Row 2 Left',
      category: 'Interior / Furniture',
      color: '#b08968',
      step: 1,
      width: 30,
      length: 18,
      sheet: 2,
      fileSizeKB: '1.2 KB',
      assembledPos: [-35, 9, -18],
      assembledRot: [0, Math.PI / 2, 0],
      explodeVec: [-35, 30, -35],
      generate2D: (t) => ({
        outline: [
          [-15, -9], [-8, -9], [-8, -9 - t], [8, -9 - t], [8, -9],
          [15, -9], [15, 9], [-15, 9]
        ],
        cutouts: [{ x: 0, y: 2, w: 20, h: 4 }],
        engravings: [{ type: 'line', x1: -12, y1: -2, x2: 12, y2: -2 }]
      }),
      connections: ['CH-01']
    },
    {
      id: 'CH-29',
      fileName: 'CH-29_nave_pew_row_02_right.svg',
      name: 'Nave Pew — Row 2 Right',
      category: 'Interior / Furniture',
      color: '#b08968',
      step: 1,
      width: 30,
      length: 18,
      sheet: 2,
      fileSizeKB: '1.2 KB',
      assembledPos: [-35, 9, 18],
      assembledRot: [0, Math.PI / 2, 0],
      explodeVec: [-35, 30, 35],
      generate2D: (t) => ({
        outline: [
          [-15, -9], [-8, -9], [-8, -9 - t], [8, -9 - t], [8, -9],
          [15, -9], [15, 9], [-15, 9]
        ],
        cutouts: [{ x: 0, y: 2, w: 20, h: 4 }],
        engravings: [{ type: 'line', x1: -12, y1: -2, x2: 12, y2: -2 }]
      }),
      connections: ['CH-01']
    },
    {
      id: 'CH-30',
      fileName: 'CH-30_elevated_gothic_pulpit.svg',
      name: 'Elevated Gothic Pulpit',
      category: 'Interior / Furniture',
      color: '#c99a6b',
      step: 1,
      width: 22,
      length: 32,
      sheet: 2,
      fileSizeKB: '1.3 KB',
      assembledPos: [-10, 16, -22],
      assembledRot: [0, Math.PI / 4, 0],
      explodeVec: [-10, 40, -45],
      generate2D: (t) => ({
        outline: [
          [-11, -16], [-6, -16], [-6, -16 - t], [6, -16 - t], [6, -16],
          [11, -16], [11, 16], [-11, 16]
        ],
        cutouts: [{ x: 0, y: 5, w: 8, h: 12, arched: true }],
        engravings: [{ type: 'rect', x: -8, y: -10, w: 16, h: 8 }]
      }),
      connections: ['CH-01']
    },
    {
      id: 'CH-31',
      fileName: 'CH-31_sanctuary_high_altar.svg',
      name: 'High Sanctuary Altar & Reredos',
      category: 'Interior / Furniture',
      color: '#e0a96d',
      step: 1,
      width: 32,
      length: 28,
      sheet: 2,
      fileSizeKB: '1.4 KB',
      assembledPos: [85, 14, 0],
      assembledRot: [0, Math.PI / 2, 0],
      explodeVec: [85, 35, 0],
      generate2D: (t) => ({
        outline: [
          [-16, -14], [-8, -14], [-8, -14 - t], [8, -14 - t], [8, -14],
          [16, -14], [16, 6], [8, 14], [-8, 14], [-16, 6]
        ],
        cutouts: [],
        engravings: [
          { type: 'cross', x: 0, y: 2, size: 10 },
          { type: 'line', x1: -12, y1: -6, x2: 12, y2: -6 }
        ]
      }),
      connections: ['CH-01']
    },
    {
      id: 'CH-32',
      fileName: 'CH-32_baptismal_font.svg',
      name: 'Octagonal Baptismal Font',
      category: 'Interior / Furniture',
      color: '#c99a6b',
      step: 1,
      width: 16,
      length: 22,
      sheet: 2,
      fileSizeKB: '1.1 KB',
      assembledPos: [-95, 11, 0],
      assembledRot: [0, 0, 0],
      explodeVec: [-95, 35, 0],
      generate2D: (t) => ({
        outline: [
          [-8, -11], [-5, -11], [-5, -11 - t], [5, -11 - t], [5, -11],
          [8, -11], [8, 11], [-8, 11]
        ],
        cutouts: [],
        engravings: [{ type: 'circle', x: 0, y: 3, r: 4 }]
      }),
      connections: ['CH-01']
    },

    // GROUP 2: WALLS & APSE
    {
      id: 'CH-02',
      fileName: 'CH-02_left_west_nave_wall.svg',
      name: 'Left West Nave Wall',
      category: 'Structural',
      color: '#d4a373',
      step: 2,
      width: 105,
      length: 65,
      sheet: 1,
      fileSizeKB: '2.1 KB',
      assembledPos: [-57, 32.5, -36],
      assembledRot: [0, 0, 0],
      explodeVec: [-57, 0, -55],
      generate2D: (t) => ({
        outline: [
          [-52.5, -32.5], [-35, -32.5], [-35, -32.5 - t], [-15, -32.5 - t], [-15, -32.5],
          [10, -32.5], [10, -32.5 - t], [30, -32.5 - t], [30, -32.5],
          [52.5, -32.5], [52.5, 32.5],
          [35, 32.5], [35, 32.5 - t], [20, 32.5 - t], [20, 32.5],
          [-20, 32.5], [-20, 32.5 - t], [-35, 32.5 - t], [-35, 32.5],
          [-52.5, 32.5]
        ],
        cutouts: [
          { x: -35, y: 0, w: 12, h: 32, arched: true },
          { x: 0, y: 0, w: 12, h: 32, arched: true },
          { x: 35, y: 0, w: 12, h: 32, arched: true },
          { x: -23, y: 15, w: t + 0.1, h: 10 },
          { x: 22, y: 15, w: t + 0.1, h: 10 }
        ],
        engravings: [{ type: 'line', x1: -50, y1: 22, x2: 50, y2: 22 }]
      }),
      connections: ['CH-01', 'CH-08', 'CH-10', 'CH-11', 'CH-15', 'CH-16']
    },
    {
      id: 'CH-03',
      fileName: 'CH-03_left_east_choir_wall.svg',
      name: 'Left East Choir Wall',
      category: 'Structural',
      color: '#d4a373',
      step: 2,
      width: 65,
      length: 65,
      sheet: 1,
      fileSizeKB: '1.8 KB',
      assembledPos: [85, 32.5, -36],
      assembledRot: [0, 0, 0],
      explodeVec: [85, 0, -55],
      generate2D: (t) => ({
        outline: [
          [-32.5, -32.5], [-15, -32.5], [-15, -32.5 - t], [15, -32.5 - t], [15, -32.5],
          [32.5, -32.5], [32.5, 32.5],
          [15, 32.5], [15, 32.5 - t], [0, 32.5 - t], [0, 32.5],
          [-32.5, 32.5]
        ],
        cutouts: [
          { x: -12, y: 0, w: 11, h: 32, arched: true },
          { x: 12, y: 0, w: 11, h: 32, arched: true }
        ],
        engravings: [{ type: 'line', x1: -30, y1: 22, x2: 30, y2: 22 }]
      }),
      connections: ['CH-01', 'CH-06', 'CH-09', 'CH-11']
    },
    {
      id: 'CH-04',
      fileName: 'CH-04_right_west_nave_wall.svg',
      name: 'Right West Nave Wall',
      category: 'Structural',
      color: '#d4a373',
      step: 2,
      width: 105,
      length: 65,
      sheet: 1,
      fileSizeKB: '2.1 KB',
      assembledPos: [-57, 32.5, 36],
      assembledRot: [0, Math.PI, 0],
      explodeVec: [-57, 0, 55],
      generate2D: (t) => ({
        outline: [
          [-52.5, -32.5], [-35, -32.5], [-35, -32.5 - t], [-15, -32.5 - t], [-15, -32.5],
          [10, -32.5], [10, -32.5 - t], [30, -32.5 - t], [30, -32.5],
          [52.5, -32.5], [52.5, 32.5],
          [35, 32.5], [35, 32.5 - t], [20, 32.5 - t], [20, 32.5],
          [-20, 32.5], [-20, 32.5 - t], [-35, 32.5 - t], [-35, 32.5],
          [-52.5, 32.5]
        ],
        cutouts: [
          { x: -35, y: 0, w: 12, h: 32, arched: true },
          { x: 0, y: 0, w: 12, h: 32, arched: true },
          { x: 35, y: 0, w: 12, h: 32, arched: true },
          { x: -23, y: 15, w: t + 0.1, h: 10 },
          { x: 22, y: 15, w: t + 0.1, h: 10 }
        ],
        engravings: [{ type: 'line', x1: -50, y1: 22, x2: 50, y2: 22 }]
      }),
      connections: ['CH-01', 'CH-08', 'CH-10', 'CH-12', 'CH-17', 'CH-18']
    },
    {
      id: 'CH-05',
      fileName: 'CH-05_right_east_choir_wall.svg',
      name: 'Right East Choir Wall',
      category: 'Structural',
      color: '#d4a373',
      step: 2,
      width: 65,
      length: 65,
      sheet: 1,
      fileSizeKB: '1.8 KB',
      assembledPos: [85, 32.5, 36],
      assembledRot: [0, Math.PI, 0],
      explodeVec: [85, 0, 55],
      generate2D: (t) => ({
        outline: [
          [-32.5, -32.5], [-15, -32.5], [-15, -32.5 - t], [15, -32.5 - t], [15, -32.5],
          [32.5, -32.5], [32.5, 32.5],
          [15, 32.5], [15, 32.5 - t], [0, 32.5 - t], [0, 32.5],
          [-32.5, 32.5]
        ],
        cutouts: [
          { x: -12, y: 0, w: 11, h: 32, arched: true },
          { x: 12, y: 0, w: 11, h: 32, arched: true }
        ],
        engravings: [{ type: 'line', x1: -30, y1: 22, x2: 30, y2: 22 }]
      }),
      connections: ['CH-01', 'CH-07', 'CH-09', 'CH-12']
    },
    {
      id: 'CH-09',
      fileName: 'CH-09_sanctuary_east_apse.svg',
      name: 'High Sanctuary Apse & East Window',
      category: 'Structural',
      color: '#ddb892',
      step: 2,
      width: 74,
      length: 105,
      sheet: 1,
      fileSizeKB: '2.3 KB',
      assembledPos: [115, 52.5, 0],
      assembledRot: [0, -Math.PI / 2, 0],
      explodeVec: [75, 0, 0],
      generate2D: (t) => ({
        outline: [
          [-37, -52.5], [-16, -52.5], [-16, -52.5 - t], [16, -52.5 - t], [16, -52.5],
          [37, -52.5], [37, 18], [0, 52.5], [-37, 18]
        ],
        cutouts: [
          { x: -14, y: 0, w: 7, h: 42, arched: true },
          { x: 0, y: 8, w: 9, h: 54, arched: true },
          { x: 14, y: 0, w: 7, h: 42, arched: true }
        ],
        engravings: [
          { type: 'circle', x: 0, y: 38, r: 5 },
          { type: 'cross', x: 0, y: 38, size: 5 }
        ]
      }),
      connections: ['CH-01', 'CH-03', 'CH-05', 'CH-11', 'CH-12']
    },
    {
      id: 'CH-10',
      fileName: 'CH-10_chancel_rood_arch.svg',
      name: 'Chancel Arch / Rood Screen',
      category: 'Structural',
      color: '#c99a6b',
      step: 2,
      width: 72,
      length: 90,
      sheet: 1,
      fileSizeKB: '1.9 KB',
      assembledPos: [5, 45, 0],
      assembledRot: [0, Math.PI / 2, 0],
      explodeVec: [5, 40, 0],
      generate2D: (t) => ({
        outline: [
          [-36, -45], [-22, -45], [-22, -45 - t], [22, -45 - t], [22, -45],
          [36, -45], [36, 18], [0, 45], [-36, 18]
        ],
        cutouts: [{ x: 0, y: -10, w: 38, h: 58, arched: true }],
        engravings: [{ type: 'cross', x: 0, y: 32, size: 8 }]
      }),
      connections: ['CH-01', 'CH-02', 'CH-04', 'CH-23']
    },

    // GROUP 3: TRANSEPT WINGS
    {
      id: 'CH-06',
      fileName: 'CH-06_north_transept_rose_facade.svg',
      name: 'North Transept Facade & Rose',
      category: 'Structural',
      color: '#ddb892',
      step: 3,
      width: 50,
      length: 95,
      sheet: 1,
      fileSizeKB: '1.9 KB',
      assembledPos: [30, 47.5, -85],
      assembledRot: [0, Math.PI, 0],
      explodeVec: [30, 0, -60],
      generate2D: (t) => ({
        outline: [
          [-25, -47.5], [-12, -47.5], [-12, -47.5 - t], [12, -47.5 - t], [12, -47.5],
          [25, -47.5], [25, 20], [0, 47.5], [-25, 20]
        ],
        cutouts: [
          { x: -10, y: -18, w: 8, h: 28, arched: true },
          { x: 10, y: -18, w: 8, h: 28, arched: true }
        ],
        engravings: [
          { type: 'circle', x: 0, y: 16, r: 11 },
          { type: 'cross', x: 0, y: 16, size: 9 }
        ]
      }),
      connections: ['CH-01', 'CH-03', 'CH-13']
    },
    {
      id: 'CH-07',
      fileName: 'CH-07_south_transept_rose_facade.svg',
      name: 'South Transept Facade & Rose',
      category: 'Structural',
      color: '#ddb892',
      step: 3,
      width: 50,
      length: 95,
      sheet: 1,
      fileSizeKB: '1.9 KB',
      assembledPos: [30, 47.5, 85],
      assembledRot: [0, 0, 0],
      explodeVec: [30, 0, 60],
      generate2D: (t) => ({
        outline: [
          [-25, -47.5], [-12, -47.5], [-12, -47.5 - t], [12, -47.5 - t], [12, -47.5],
          [25, -47.5], [25, 20], [0, 47.5], [-25, 20]
        ],
        cutouts: [
          { x: -10, y: -18, w: 8, h: 28, arched: true },
          { x: 10, y: -18, w: 8, h: 28, arched: true }
        ],
        engravings: [
          { type: 'circle', x: 0, y: 16, r: 11 },
          { type: 'cross', x: 0, y: 16, size: 9 }
        ]
      }),
      connections: ['CH-01', 'CH-05', 'CH-14']
    },
    {
      id: 'CH-13',
      fileName: 'CH-13_north_transept_roof.svg',
      name: 'North Transept Pitched Roof',
      category: 'Roof',
      color: '#9c6644',
      step: 3,
      width: 48,
      length: 50,
      sheet: 1,
      fileSizeKB: '1.1 KB',
      assembledPos: [30, 72, -62],
      assembledRot: [0, Math.PI / 2, Math.PI / 4],
      explodeVec: [30, 40, -50],
      generate2D: (t) => ({
        outline: [[-24, -25], [24, -25], [24, 25], [-24, 25]],
        cutouts: [],
        engravings: [{ type: 'line', x1: -22, y1: 0, x2: 22, y2: 0 }]
      }),
      connections: ['CH-06', 'CH-23']
    },
    {
      id: 'CH-14',
      fileName: 'CH-14_south_transept_roof.svg',
      name: 'South Transept Pitched Roof',
      category: 'Roof',
      color: '#9c6644',
      step: 3,
      width: 48,
      length: 50,
      sheet: 1,
      fileSizeKB: '1.1 KB',
      assembledPos: [30, 72, 62],
      assembledRot: [0, -Math.PI / 2, Math.PI / 4],
      explodeVec: [30, 40, 50],
      generate2D: (t) => ({
        outline: [[-24, -25], [24, -25], [24, 25], [-24, 25]],
        cutouts: [],
        engravings: [{ type: 'line', x1: -22, y1: 0, x2: 22, y2: 0 }]
      }),
      connections: ['CH-07', 'CH-23']
    },

    // GROUP 4: BUTTRESSES
    {
      id: 'CH-15',
      fileName: 'CH-15_buttress_north_west.svg',
      name: 'North-West Flying Buttress',
      category: 'Support',
      color: '#b08968',
      step: 4,
      width: 28,
      length: 45,
      sheet: 2,
      fileSizeKB: '1.4 KB',
      assembledPos: [-80, 22, -45],
      assembledRot: [0, 0, 0],
      explodeVec: [-80, 15, -45],
      generate2D: (t) => ({
        outline: [
          [-14, -22.5], [-7, -22.5], [-7, -22.5 - t], [7, -22.5 - t], [7, -22.5],
          [14, -22.5], [14, 5], [7, 22.5], [0, 22.5], [-14, 0]
        ],
        cutouts: [{ x: -2, y: -4, w: 9, h: 16, arched: true }],
        engravings: [{ type: 'line', x1: -8, y1: 10, x2: 6, y2: 18 }]
      }),
      connections: ['CH-01', 'CH-02']
    },
    {
      id: 'CH-16',
      fileName: 'CH-16_buttress_north_east.svg',
      name: 'North-East Flying Buttress',
      category: 'Support',
      color: '#b08968',
      step: 4,
      width: 28,
      length: 45,
      sheet: 2,
      fileSizeKB: '1.4 KB',
      assembledPos: [-35, 22, -45],
      assembledRot: [0, 0, 0],
      explodeVec: [-35, 15, -45],
      generate2D: (t) => ({
        outline: [
          [-14, -22.5], [-7, -22.5], [-7, -22.5 - t], [7, -22.5 - t], [7, -22.5],
          [14, -22.5], [14, 5], [7, 22.5], [0, 22.5], [-14, 0]
        ],
        cutouts: [{ x: -2, y: -4, w: 9, h: 16, arched: true }],
        engravings: [{ type: 'line', x1: -8, y1: 10, x2: 6, y2: 18 }]
      }),
      connections: ['CH-01', 'CH-02']
    },
    {
      id: 'CH-17',
      fileName: 'CH-17_buttress_south_west.svg',
      name: 'South-West Flying Buttress',
      category: 'Support',
      color: '#b08968',
      step: 4,
      width: 28,
      length: 45,
      sheet: 2,
      fileSizeKB: '1.4 KB',
      assembledPos: [-80, 22, 45],
      assembledRot: [0, Math.PI, 0],
      explodeVec: [-80, 15, 45],
      generate2D: (t) => ({
        outline: [
          [-14, -22.5], [-7, -22.5], [-7, -22.5 - t], [7, -22.5 - t], [7, -22.5],
          [14, -22.5], [14, 5], [7, 22.5], [0, 22.5], [-14, 0]
        ],
        cutouts: [{ x: -2, y: -4, w: 9, h: 16, arched: true }],
        engravings: [{ type: 'line', x1: -8, y1: 10, x2: 6, y2: 18 }]
      }),
      connections: ['CH-01', 'CH-04']
    },
    {
      id: 'CH-18',
      fileName: 'CH-18_buttress_south_east.svg',
      name: 'South-East Flying Buttress',
      category: 'Support',
      color: '#b08968',
      step: 4,
      width: 28,
      length: 45,
      sheet: 2,
      fileSizeKB: '1.4 KB',
      assembledPos: [-35, 22, 45],
      assembledRot: [0, Math.PI, 0],
      explodeVec: [-35, 15, 45],
      generate2D: (t) => ({
        outline: [
          [-14, -22.5], [-7, -22.5], [-7, -22.5 - t], [7, -22.5 - t], [7, -22.5],
          [14, -22.5], [14, 5], [7, 22.5], [0, 22.5], [-14, 0]
        ],
        cutouts: [{ x: -2, y: -4, w: 9, h: 16, arched: true }],
        engravings: [{ type: 'line', x1: -8, y1: 10, x2: 6, y2: 18 }]
      }),
      connections: ['CH-01', 'CH-04']
    },

    // GROUP 5: WESTWORK TOWERS & ROOFS
    {
      id: 'CH-08',
      fileName: 'CH-08_westwork_portal_facade.svg',
      name: 'Westwork Facade & Dual Portals',
      category: 'Structural',
      color: '#ddb892',
      step: 5,
      width: 78,
      length: 120,
      sheet: 1,
      fileSizeKB: '2.5 KB',
      assembledPos: [-115, 60, 0],
      assembledRot: [0, Math.PI / 2, 0],
      explodeVec: [-75, 0, 0],
      generate2D: (t) => ({
        outline: [
          [-39, -60], [-16, -60], [-16, -60 - t], [16, -60 - t], [16, -60],
          [39, -60], [39, 28], [0, 60], [-39, 28]
        ],
        cutouts: [
          { x: -14, y: -36, w: 14, h: 32, arched: true },
          { x: 14, y: -36, w: 14, h: 32, arched: true },
          { x: -28, y: 15, w: t + 0.1, h: 18 },
          { x: 28, y: 15, w: t + 0.1, h: 18 }
        ],
        engravings: [
          { type: 'circle', x: 0, y: 15, r: 15 },
          { type: 'cross', x: 0, y: 15, size: 12 }
        ]
      }),
      connections: ['CH-01', 'CH-02', 'CH-04', 'CH-11', 'CH-12', 'CH-19', 'CH-21']
    },
    {
      id: 'CH-19',
      fileName: 'CH-19_north_tower_front.svg',
      name: 'North Bell Tower Front Wall',
      category: 'Tower',
      color: '#c99a6b',
      step: 5,
      width: 24,
      length: 90,
      sheet: 2,
      fileSizeKB: '1.5 KB',
      assembledPos: [-115, 115, -26],
      assembledRot: [0, Math.PI / 2, 0],
      explodeVec: [-60, 35, -30],
      generate2D: (t) => ({
        outline: [
          [-12, -45], [-6, -45], [-6, -45 - t], [6, -45 - t], [6, -45],
          [12, -45], [12, 45], [-12, 45]
        ],
        cutouts: [{ x: 0, y: 14, w: 8, h: 26, arched: true }],
        engravings: [{ type: 'rect', x: -8, y: -20, w: 16, h: 18 }]
      }),
      connections: ['CH-08', 'CH-20']
    },
    {
      id: 'CH-20',
      fileName: 'CH-20_north_tower_side.svg',
      name: 'North Bell Tower Outer Wall',
      category: 'Tower',
      color: '#c99a6b',
      step: 5,
      width: 24,
      length: 90,
      sheet: 2,
      fileSizeKB: '1.4 KB',
      assembledPos: [-103, 115, -36],
      assembledRot: [0, 0, 0],
      explodeVec: [-50, 35, -45],
      generate2D: (t) => ({
        outline: [[-12, -45], [12, -45], [12, 45], [-12, 45]],
        cutouts: [{ x: 0, y: 14, w: 8, h: 26, arched: true }],
        engravings: [{ type: 'line', x1: -10, y1: -10, x2: 10, y2: -10 }]
      }),
      connections: ['CH-19']
    },
    {
      id: 'CH-21',
      fileName: 'CH-21_south_tower_front.svg',
      name: 'South Bell Tower Front Wall',
      category: 'Tower',
      color: '#c99a6b',
      step: 5,
      width: 24,
      length: 90,
      sheet: 2,
      fileSizeKB: '1.5 KB',
      assembledPos: [-115, 115, 26],
      assembledRot: [0, Math.PI / 2, 0],
      explodeVec: [-60, 35, 30],
      generate2D: (t) => ({
        outline: [
          [-12, -45], [-6, -45], [-6, -45 - t], [6, -45 - t], [6, -45],
          [12, -45], [12, 45], [-12, 45]
        ],
        cutouts: [{ x: 0, y: 14, w: 8, h: 26, arched: true }],
        engravings: [{ type: 'rect', x: -8, y: -20, w: 16, h: 18 }]
      }),
      connections: ['CH-08', 'CH-22']
    },
    {
      id: 'CH-22',
      fileName: 'CH-22_south_tower_side.svg',
      name: 'South Bell Tower Outer Wall',
      category: 'Tower',
      color: '#c99a6b',
      step: 5,
      width: 24,
      length: 90,
      sheet: 2,
      fileSizeKB: '1.4 KB',
      assembledPos: [-103, 115, 36],
      assembledRot: [0, Math.PI, 0],
      explodeVec: [-50, 35, 45],
      generate2D: (t) => ({
        outline: [[-12, -45], [12, -45], [12, 45], [-12, 45]],
        cutouts: [{ x: 0, y: 14, w: 8, h: 26, arched: true }],
        engravings: [{ type: 'line', x1: -10, y1: -10, x2: 10, y2: -10 }]
      }),
      connections: ['CH-21']
    },
    {
      id: 'CH-11',
      fileName: 'CH-11_nave_roof_left.svg',
      name: 'Left Pitch Nave & Choir Roof',
      category: 'Roof',
      color: '#9c6644',
      step: 5,
      width: 220,
      length: 56,
      sheet: 1,
      fileSizeKB: '2.4 KB',
      assembledPos: [0, 80, -22],
      assembledRot: [Math.PI / 3.9, 0, 0],
      explodeVec: [0, 50, -40],
      generate2D: (t) => ({
        outline: [
          [-110, -28], [110, -28], [110, 28],
          [80, 28], [80, 28 + t], [50, 28 + t], [50, 28],
          [10, 28], [10, 28 + t], [-20, 28 + t], [-20, 28],
          [-60, 28], [-60, 28 + t], [-90, 28 + t], [-90, 28],
          [-110, 28]
        ],
        cutouts: [
          { x: 30, y: 15, w: 24, h: t + 0.1 },
          { x: 100, y: 22, w: 10, h: t + 0.1 }
        ],
        engravings: [
          { type: 'line', x1: -105, y1: -14, x2: 105, y2: -14 },
          { type: 'line', x1: -105, y1: 0, x2: 105, y2: 0 },
          { type: 'line', x1: -105, y1: 14, x2: 105, y2: 14 }
        ]
      }),
      connections: ['CH-02', 'CH-03', 'CH-08', 'CH-09', 'CH-12', 'CH-23', 'CH-25']
    },
    {
      id: 'CH-12',
      fileName: 'CH-12_nave_roof_right.svg',
      name: 'Right Pitch Nave & Choir Roof',
      category: 'Roof',
      color: '#9c6644',
      step: 5,
      width: 220,
      length: 56,
      sheet: 1,
      fileSizeKB: '2.4 KB',
      assembledPos: [0, 80, 22],
      assembledRot: [-Math.PI / 3.9, 0, 0],
      explodeVec: [0, 50, 40],
      generate2D: (t) => ({
        outline: [
          [-110, -28], [110, -28],
          [110, 28], [110, 28 + t], [80, 28 + t], [80, 28],
          [50, 28], [50, 28 + t], [10, 28 + t], [10, 28],
          [-20, 28], [-20, 28 + t], [-60, 28 + t], [-60, 28],
          [-90, 28], [-90, 28 + t], [-110, 28 + t], [-110, 28]
        ],
        cutouts: [
          { x: 30, y: 15, w: 24, h: t + 0.1 },
          { x: 100, y: 22, w: 10, h: t + 0.1 }
        ],
        engravings: [
          { type: 'line', x1: -105, y1: -14, x2: 105, y2: -14 },
          { type: 'line', x1: -105, y1: 0, x2: 105, y2: 0 },
          { type: 'line', x1: -105, y1: 14, x2: 105, y2: 14 }
        ]
      }),
      connections: ['CH-04', 'CH-05', 'CH-08', 'CH-09', 'CH-11', 'CH-23', 'CH-25']
    },

    // GROUP 6: CROSSING LANTERN & SPIRE
    {
      id: 'CH-23',
      fileName: 'CH-23_crossing_lantern_tower.svg',
      name: 'Central Crossing Lantern Tower',
      category: 'Tower',
      color: '#b08968',
      step: 6,
      width: 36,
      length: 42,
      sheet: 2,
      fileSizeKB: '1.6 KB',
      assembledPos: [30, 108, 0],
      assembledRot: [0, 0, 0],
      explodeVec: [30, 50, 0],
      generate2D: (t) => ({
        outline: [
          [-18, -21], [-10, -21], [-10, -21 - t], [10, -21 - t], [10, -21],
          [18, -21], [18, 21], [-18, 21]
        ],
        cutouts: [
          { x: 0, y: 0, w: 10, h: 20, arched: true },
          { x: 0, y: 15, w: 12, h: t + 0.1 }
        ],
        engravings: [{ type: 'rect', x: -14, y: -16, w: 28, h: 32 }]
      }),
      connections: ['CH-10', 'CH-11', 'CH-12', 'CH-24']
    },
    {
      id: 'CH-24',
      fileName: 'CH-24_gothic_fleche_spire.svg',
      name: 'Gothic Flèche Crossing Spire',
      category: 'Tower',
      color: '#7f4f24',
      step: 6,
      width: 24,
      length: 65,
      sheet: 2,
      fileSizeKB: '1.3 KB',
      assembledPos: [30, 155, 0],
      assembledRot: [0, Math.PI / 4, 0],
      explodeVec: [30, 75, 0],
      generate2D: (t) => ({
        outline: [
          [-12, -32.5], [-6, -32.5], [-6, -32.5 - t], [6, -32.5 - t], [6, -32.5],
          [12, -32.5], [0, 32.5]
        ],
        cutouts: [{ x: 0, y: 0, w: t + 0.1, h: 30 }],
        engravings: [{ type: 'line', x1: 0, y1: 30, x2: 0, y2: 5 }]
      }),
      connections: ['CH-23']
    },
    {
      id: 'CH-25',
      fileName: 'CH-25_apex_sanctuary_cross.svg',
      name: 'Apex Sanctuary Cross Finial',
      category: 'Decorative',
      color: '#f59e0b',
      step: 6,
      width: 14,
      length: 28,
      sheet: 2,
      fileSizeKB: '1.1 KB',
      assembledPos: [100, 108, 0],
      assembledRot: [0, Math.PI / 2, 0],
      explodeVec: [100, 60, 0],
      generate2D: (t) => ({
        outline: [
          [-3, -14], [-3, -4], [-7, -4], [-7, 2], [-3, 2], [-3, 14],
          [3, 14], [3, 2], [7, 2], [7, -4], [3, -4], [3, -14]
        ],
        cutouts: [],
        engravings: [{ type: 'circle', x: 0, y: 0, r: 2.5 }]
      }),
      connections: ['CH-11', 'CH-12']
    }
  ]
};
