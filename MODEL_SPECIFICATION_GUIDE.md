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
   * @param {number} t - Material thickness (2.0, 3.0, or 4.0 mm)
   * @param {number} kerf - Laser kerf compensation (typically 0.15 mm)
   * @param {number} clr - Slot clearance tolerance (typically 0.10 mm)
   */
  generate2D: (t, kerf, clr) => ({
    // 1. OUTER CUT OUTLINE (Red Laser Line): Closed 2D polygon [X, Y]
    // The part's local origin [0, 0] should be near the centroid.
    outline: [
      [-60, -40], [60, -40], [60, 40], [-60, 40]
    ],

    // 2. INTERNAL MORTISES / SLOTS (Red Laser Cutouts):
    // For slots receptive to thickness 't', slot width MUST equal (t + clr) or (t + 0.10).
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

To pass the built-in **Physical Feasibility Auditor** ([`validation.html`](file:///d:/downloads/2-3D%20Basic/validation.html)), follow these rules:

1. **Mortise Slot Width**:
   $$\text{Slot Width} = t + \text{clr} \quad (\text{typically } t + 0.10\,\text{mm})$$
   *Never hardcode slot thickness to a constant number like `3.0`.* Always use `t + clr` or `t + 0.10` so when the user selects $2\text{mm}$, $3\text{mm}$, or $4\text{mm}$, the slot resizes automatically.

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

## 5. Ready-to-Use Minimal Model Boilerplate

Here is a 3-piece minimal boilerplate that can be copied directly into `js/models/box.js`:

```javascript
export const BoxModelData = {
  id: 'simple-box',
  name: 'Interlocking Storage Cube',
  category: 'Starter / Primitive',
  description: '3-piece friction-fit box demonstrating perpendicular interlocking mortises.',
  difficulty: 'Level 1 — Beginner (3 parts)',
  cameraBookmarks: [
    { name: 'Isometric', eye: [80, 70, 90], target: [0, 20, 0], dist: 140 }
  ],
  assemblySteps: [
    { num: 0, title: 'Full Assembly', desc: 'Complete 3-piece box.' },
    { num: 1, title: 'Base Floor', desc: 'Place bottom plate.', parts: ['B-01'] },
    { num: 2, title: 'Left & Right Walls', desc: 'Insert walls into slots.', parts: ['B-02', 'B-03'] }
  ],
  manufacturingSheets: [
    {
      sheetNum: 1,
      name: 'box_sheet.svg',
      sheetW: 240,
      sheetH: 160,
      layout: {
        'B-01': { x: 60, y: 50, r: 0 },
        'B-02': { x: 170, y: 50, r: 0 },
        'B-03': { x: 170, y: 110, r: 0 }
      }
    }
  ],
  parts: [
    {
      id: 'B-01',
      fileName: 'B-01_base.svg',
      name: 'Floor Plate',
      category: 'Foundation',
      color: '#8c6239',
      step: 1,
      width: 60,
      length: 60,
      sheet: 1,
      fileSizeKB: '1.0 KB',
      assembledPos: [0, 0, 0],
      assembledRot: [-Math.PI / 2, 0, 0],
      explodeVec: [0, -30, 0],
      connections: ['B-02', 'B-03'],
      generate2D: (t, kerf, clr) => ({
        outline: [[-30, -30], [30, -30], [30, 30], [-30, 30]],
        cutouts: [
          { x: -20, y: 0, w: t + clr, h: 30 },
          { x: 20, y: 0, w: t + clr, h: 30 }
        ],
        engravings: [{ type: 'rect', x: -25, y: -25, w: 50, h: 50 }]
      })
    },
    {
      id: 'B-02',
      fileName: 'B-02_wall_left.svg',
      name: 'Left Wall',
      category: 'Structural',
      color: '#d4a373',
      step: 2,
      width: 40,
      length: 40,
      sheet: 1,
      fileSizeKB: '1.0 KB',
      assembledPos: [-20, 20, 0],
      assembledRot: [0, Math.PI / 2, 0],
      explodeVec: [-30, 0, 0],
      connections: ['B-01'],
      generate2D: (t) => ({
        outline: [
          [-20, -20], [-15, -20], [-15, -20 - t], [15, -20 - t], [15, -20],
          [20, -20], [20, 20], [-20, 20]
        ],
        cutouts: [{ x: 0, y: 0, w: 10, h: 10, arched: true }],
        engravings: []
      })
    },
    {
      id: 'B-03',
      fileName: 'B-03_wall_right.svg',
      name: 'Right Wall',
      category: 'Structural',
      color: '#d4a373',
      step: 2,
      width: 40,
      length: 40,
      sheet: 1,
      fileSizeKB: '1.0 KB',
      assembledPos: [20, 20, 0],
      assembledRot: [0, -Math.PI / 2, 0],
      explodeVec: [30, 0, 0],
      connections: ['B-01'],
      generate2D: (t) => ({
        outline: [
          [-20, -20], [-15, -20], [-15, -20 - t], [15, -20 - t], [15, -20],
          [20, -20], [20, 20], [-20, 20]
        ],
        cutouts: [{ x: 0, y: 0, w: 10, h: 10, arched: true }],
        engravings: []
      })
    }
  ]
};
```
