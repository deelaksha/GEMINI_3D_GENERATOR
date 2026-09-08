# AI Model Generation & File Structure Guide
## Universal 3D Physical Construction Puzzle Platform (PuzzleCore)

This document is the authoritative developer and AI prompt guide for creating, modifying, and replacing 3D puzzle models in this platform. 

Provide this file to any AI coding assistant so it understands the exact schema, coordinate systems, connector math, and file locations to output valid physical models.

---

## 1. Where to Create or Replace Your Model

### Option A: Create a New Model File (Recommended)
1. **Create your model file** in:
   ```
   d:/downloads/2-3D Basic/js/models/<your-model-name>.js
   ```
   *(Example: `js/models/robot.js`, `js/models/car.js`, `js/models/boat.js`)*

2. **Register your model** in:
   [`d:/downloads/2-3D Basic/js/models/registry.js`](file:///d:/downloads/2-3D%20Basic/js/models/registry.js)
   ```javascript
   import { YourModelData } from './your-model-name.js';

   // Inside ModelRegistryService constructor:
   this.registerModel(new ConstructionObject(YourModelData));
   ```

3. *(Optional)* **Set it as the default model** in:
   [`d:/downloads/2-3D Basic/js/core/config.js`](file:///d:/downloads/2-3D%20Basic/js/core/config.js)
   Change `'cathedral'` to your model's ID:
   ```javascript
   const savedModel = localStorage.getItem('PUZZLE_ACTIVE_MODEL') || 'your-model-id';
   ```

### Option B: Directly Replace an Existing Model
- To overwrite the Cathedral, edit: [`js/models/cathedral.js`](file:///d:/downloads/2-3D%20Basic/js/models/cathedral.js)
- To overwrite the Starter House, edit: [`js/models/simple-house.js`](file:///d:/downloads/2-3D%20Basic/js/models/simple-house.js)

---

## 2. Complete Model Data Schema

Every model must export a JavaScript object conforming to this exact structure:

```javascript
export const MyModelData = {
  // --- METADATA ---
  id: 'my-model-id',                  // Unique string identifier (no spaces)
  name: 'Display Name of Model',      // Human-readable title
  category: 'Vehicles / Architecture',// Category tag
  description: '1-2 sentence description of the physical puzzle.',
  difficulty: 'Level 1 — Beginner (12 parts)', // Target difficulty

  // --- CAMERA SIGHTLINE BOOKMARKS ---
  cameraBookmarks: [
    {
      name: 'Isometric View',
      eye: [140, 120, 160],           // [x, y, z] initial eye position
      target: [0, 30, 0],             // [x, y, z] target center point
      dist: 250                       // Camera distance
    },
    {
      name: 'Cockpit / Interior View',
      eye: [0, 25, 40],
      target: [0, 20, 0],
      dist: 80,
      select: 'PART-01'               // Automatically selects this part
    }
  ],

  // --- ASSEMBLY BUILD STAGES (Sequential) ---
  assemblySteps: [
    {
      num: 0,
      title: 'Full Model Assembly',
      desc: 'Complete assembled structure.'
    },
    {
      num: 1,
      title: 'Chassis / Baseplate Foundation',
      desc: 'Lay the slotted baseplate flat and insert lower elements.',
      parts: ['PART-01', 'PART-02']   // Array of Part IDs belonging to Step 1
    },
    {
      num: 2,
      title: 'Side Walls / Frame',
      desc: 'Erect lateral walls and interlock tabs into baseplate mortises.',
      parts: ['PART-03', 'PART-04']
    }
    // Add additional sequential steps (Step 3, Step 4, etc.)
  ],

  // --- 2D CUT SHEET NESTING (Manufacturing) ---
  manufacturingSheets: [
    {
      sheetNum: 1,
      name: 'sheet_01.svg',
      desc: 'Main cutting sheet layout.',
      sheetW: 400,                    // Sheet width in mm
      sheetH: 300,                    // Sheet height in mm
      layout: {
        // Placement of each part on the 2D sheet: { x: mm, y: mm, r: rotationDegrees }
        'PART-01': { x: 80, y: 70, r: 0 },
        'PART-02': { x: 220, y: 70, r: 0 },
        'PART-03': { x: 80, y: 200, r: 0 },
        'PART-04': { x: 220, y: 200, r: 0 }
      }
    }
  ],

  // --- PHYSICAL PARTS DEFINITION (Array of Part Objects) ---
  parts: [
    /* List of all individual part objects */
  ]
};
```

---

## 3. Part Schema & 2D Geometry Engine

Every piece in `parts: [...]` represents a real physical laser-cut part:

```javascript
{
  id: 'CH-01',                         // Unique Part ID (engraved on piece)
  fileName: 'CH-01_baseplate.svg',     // Standalone physical SVG filename
  name: 'Chassis Baseplate',           // Human-readable part name
  category: 'Foundation',              // Foundation | Structural | Roof | Details | Support
  color: '#8c6239',                    // 3D Preview HEX Color (wood, painted tones)
  step: 1,                             // Assembly sequence step (1 to N)
  width: 120,                          // Bounding width in mm
  length: 80,                          // Bounding length in mm
  sheet: 1,                            // Which manufacturing sheet it is nested on (1, 2, ...)
  fileSizeKB: '1.4 KB',

  // --- 3D POSITION & ORIENTATION ---
  assembledPos: [0, 0, 0],             // Final 3D position [X, Y, Z] in millimeters
  assembledRot: [-Math.PI / 2, 0, 0],  // Final 3D rotation [Euler radians: X, Y, Z]
  explodeVec: [0, -40, 0],             // Displacement vector [X, Y, Z] when exploded

  // --- PHYSICAL CONNECTIONS ---
  connections: ['CH-02', 'CH-03'],     // IDs of parts that physically interlock with this part

  // --- PARAMETRIC 2D CUT CONTOUR GENERATOR ---
  /**
   * Generates the 2D cutting and engraving profile.
   * @param {number} t - Material thickness (1.0, 2.0, 3.0, or 4.0 mm)
   * @param {number} kerf - Laser kerf compensation (typically 0.15 mm)
   * @param {number} clr - Slot clearance tolerance (typically 0.10 mm)
   */
  generate2D: (t, kerf, clr) => ({
    // 1. OUTER CUT OUTLINE (Red Laser Line): Closed 2D polygon [X, Y]
    // The part's local origin [0, 0] is authoritative and mapped 1:1 to local 3D (no centroid recentering).
    // All tab protrusions and receiver slots are positioned relative to this local origin.
    outline: [
      [-60, -40], [60, -40], [60, 40], [-60, 40]
    ],

    // 2. INTERNAL MORTISES / SLOTS (Red Laser Cutouts):
    // For slots receptive to thickness 't', slot thickness MUST equal (t + clr) or use ConnectorRegistry.deriveReceiverSlot(joint, t, clr).
    cutouts: [
      // Rectangular slot:
      { x: 0, y: -30, w: 30, h: t + clr },
      // Vertical slot:
      { x: -50, y: 0, w: t + clr, h: 25 },
      // Arched gothic window / door cutout:
      { x: 0, y: 0, w: 16, h: 28, arched: true }
    ],

    // 3. VECTOR SURFACE ENGRAVINGS (Sky Blue Laser Lines):
    engravings: [
      { type: 'line', x1: -40, y1: 0, x2: 40, y2: 0 },
      { type: 'rect', x: -20, y: -10, w: 40, h: 20 },
      { type: 'circle', x: 0, y: 0, r: 8 },
      { type: 'cross', x: 0, y: 15, size: 10 }
    ]
  })
}
```

---

## 4. Universal Physical Connector Rules (Zero-Glue)

To pass the built-in **Physical Feasibility Auditor** ([validation.html](file:///d:/downloads/2-3D%20Basic/validation.html)), follow these rules:

1. **Mortise Slot Width**:
   $$\text{Slot Width} = t + \text{clr} \quad (\text{typically } t + 0.10\,\text{mm})$$
   *Never hardcode slot thickness to a constant number like `3.0`.* Always use `t + clr` or `t + 0.10` so when the user selects $1\text{mm}$, $2\text{mm}$, $3\text{mm}$, or $4\text{mm}$, the slot resizes automatically.

2. **Tab Dimensions**:
   A tab protruding from an edge should extend by:
   $$\text{Tab Depth} = t \quad (\text{or } t + 0.2\,\text{mm})$$
   $$\text{Tab Width} = \text{Matching Slot Length}$$

3. **Step Reachability**:
   - Every part in Step $N$ ($N > 1$) must list at least one mating connection to a part from an earlier step ($< N$).
   - A roof or exterior panel cannot be added in Step 1 if the foundation is not yet placed.

4. **Explode Direction**:
   - Baseplates explode downward (`[0, -40, 0]`).
   - Roofs explode upward/outward (`[0, 50, 0]`).
   - Left walls explode negative-X or negative-Z (`[-50, 0, 0]`).
   - Right walls explode positive-X or positive-Z (`[50, 0, 0]`).

---

## 5. Ready-to-Use Tested Interlocking Reference Model

Here is a 4-piece fully interlocking model with foundation, left wall, right wall, and locking top roof beam that passes `DesignParser` and `PhysicalValidator` with **0 errors and 0 warnings**:

```javascript
export const ModelData = {
  id: 'interlocking-pavilion',
  name: 'Interlocking 4-Piece Pavilion',
  category: 'Architecture',
  description: 'Precision zero-glue interlocking 3D structure with foundation, side walls, and locking roof beam.',
  difficulty: 'Level 1 — Beginner (4 parts)',
  cameraBookmarks: [
    { name: 'Isometric View', eye: [90, 80, 100], target: [0, 25, 0], dist: 160 },
    { name: 'Front Elevation', eye: [0, 25, 120], target: [0, 25, 0], dist: 130 }
  ],
  assemblySteps: [
    { num: 0, title: 'Full Assembly', desc: 'Complete 4-piece rigid structure.' },
    { num: 1, title: 'Base Foundation', desc: 'Place the slotted base plate flat on the table.', parts: ['PV-01'] },
    { num: 2, title: 'Side Support Walls', desc: 'Insert left and right walls into base mortises.', parts: ['PV-02', 'PV-03'] },
    { num: 3, title: 'Locking Roof Beam', desc: 'Slide top roof beam across both walls to lock assembly.', parts: ['PV-04'] }
  ],
  manufacturingSheets: [
    {
      sheetNum: 1,
      name: 'pavilion_sheet_01.svg',
      desc: 'Main cutting sheet (3mm plywood).',
      sheetW: 300,
      sheetH: 200,
      layout: {
        'PV-01': { x: 55, y: 55, r: 0 },
        'PV-02': { x: 175, y: 55, r: 0 },
        'PV-03': { x: 175, y: 145, r: 0 },
        'PV-04': { x: 55, y: 145, r: 0 }
      }
    }
  ],
  parts: [
    {
      id: 'PV-01',
      fileName: 'PV-01_base_plate.svg',
      name: 'Foundation Baseplate',
      category: 'Foundation',
      color: '#8c6239',
      step: 1,
      width: 80,
      length: 70,
      sheet: 1,
      fileSizeKB: '1.2 KB',
      assembledPos: [0, 0, 0],
      assembledRot: [-Math.PI / 2, 0, 0],
      explodeVec: [0, -35, 0],
      connections: ['PV-02', 'PV-03'],
      generate2D: (t = 3.0, kerf = 0.15, clr = 0.10) => ({
        outline: [
          [-40, -35], [40, -35], [40, 35], [-40, 35]
        ],
        cutouts: [
          { x: -25, y: 0, w: t + clr, h: 30 },
          { x: 25, y: 0, w: t + clr, h: 30 }
        ],
        engravings: [
          { type: 'rect', x: -35, y: -30, w: 70, h: 60 }
        ]
      })
    },
    {
      id: 'PV-02',
      fileName: 'PV-02_left_wall.svg',
      name: 'Left Structural Wall',
      category: 'Structural',
      color: '#d4a373',
      step: 2,
      width: 50,
      length: 50,
      sheet: 1,
      fileSizeKB: '1.4 KB',
      assembledPos: [-25, 25, 0],
      assembledRot: [0, Math.PI / 2, 0],
      explodeVec: [-35, 0, 0],
      connections: ['PV-01', 'PV-04'],
      generate2D: (t = 3.0, kerf = 0.15, clr = 0.10) => ({
        outline: [
          [-25, -25],
          [-15, -25], [-15, -25 - t], [15, -25 - t], [15, -25],
          [25, -25], [25, 25], [-25, 25]
        ],
        cutouts: [
          { x: 0, y: 18, w: 20, h: t + clr }
        ],
        engravings: [
          { type: 'rect', x: -15, y: -15, w: 30, h: 25 },
          { type: 'line', x1: -15, y1: 10, x2: 15, y2: 10 }
        ]
      })
    },
    {
      id: 'PV-03',
      fileName: 'PV-03_right_wall.svg',
      name: 'Right Structural Wall',
      category: 'Structural',
      color: '#d4a373',
      step: 2,
      width: 50,
      length: 50,
      sheet: 1,
      fileSizeKB: '1.4 KB',
      assembledPos: [25, 25, 0],
      assembledRot: [0, -Math.PI / 2, 0],
      explodeVec: [35, 0, 0],
      connections: ['PV-01', 'PV-04'],
      generate2D: (t = 3.0, kerf = 0.15, clr = 0.10) => ({
        outline: [
          [-25, -25],
          [-15, -25], [-15, -25 - t], [15, -25 - t], [15, -25],
          [25, -25], [25, 25], [-25, 25]
        ],
        cutouts: [
          { x: 0, y: 18, w: 20, h: t + clr }
        ],
        engravings: [
          { type: 'rect', x: -15, y: -15, w: 30, h: 25 },
          { type: 'line', x1: -15, y1: 10, x2: 15, y2: 10 }
        ]
      })
    },
    {
      id: 'PV-04',
      fileName: 'PV-04_roof_beam.svg',
      name: 'Locking Roof Beam',
      category: 'Roof',
      color: '#b08968',
      step: 3,
      width: 66,
      length: 36,
      sheet: 1,
      fileSizeKB: '1.3 KB',
      assembledPos: [0, 43, 0],
      assembledRot: [-Math.PI / 2, 0, 0],
      explodeVec: [0, 35, 0],
      connections: ['PV-02', 'PV-03'],
      generate2D: (t = 3.0, kerf = 0.15, clr = 0.10) => ({
        outline: [
          [-25, -15],
          [25, -15],
          [25, -10], [25 + t, -10], [25 + t, 10], [25, 10],
          [25, 15],
          [-25, 15],
          [-25, 10], [-25 - t, 10], [-25 - t, -10], [-25, -10]
        ],
        cutouts: [],
        engravings: [
          { type: 'circle', x: 0, y: 0, r: 10 },
          { type: 'rect', x: -20, y: -12, w: 40, h: 24 }
        ]
      })
    }
  ]
};
export default ModelData;
```
