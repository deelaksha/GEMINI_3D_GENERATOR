# AI Prompt Generation & Design Engineering Guide

This document serves as the authoritative guide for prompting Large Language Models (LLMs) to generate valid, physically constructible, zero-glue 3D puzzle models for the **PuzzleCore Platform**.

---

## 1. Core Engineering Rules & Physical Constraints

When generating a model, the AI MUST adhere to these strict geometric and mechanical rules:

1. **Units & Coordinate System**:
   * All dimensions, coordinates, cutouts, and offsets are strictly in **millimeters (mm)**.
   * Coordinate space is Three.js **Right-Handed, Y-Up**:
     * `+X`: Right
     * `+Y`: Up (Elevation above ground plate)
     * `+Z`: Forward (Towards viewer)
   * Rotations are Euler angles in **radians** `[rx, ry, rz]`.
2. **Sheet Thickness & Material Gauge**:
   * Default nominal material thickness $T = 3.0\text{ mm}$.
   * When parts lie flat on the ground plane (XZ plane), set `assembledRot: [-Math.PI / 2, 0, 0]` and `assembledPos: [x, T / 2, z]`.
3. **Slot & Tab (Mortise and Tenon) Tolerances**:
   * **Tab Width**: e.g., $15.0\text{ mm}$ to $25.0\text{ mm}$.
   * **Tab Depth**: Exactly $T$ ($3.0\text{ mm}$) to create a flush exterior finish.
   * **Mating Slot Cutout**:
     * Slot thickness $= T + \text{clearance} = 3.0 + 0.15 = 3.15\text{ mm} \approx 3.2\text{ mm}$.
     * Slot length $= \text{Tab Width} + \text{clearance} = 20.0 + 0.1 = 20.1\text{ mm}$.
4. **Outline Geometry Polygon**:
   * Counter-clockwise (CCW) vertex winding order.
   * Minimum of 3 vertices, strictly 2D `[x, y]`.
   * Outline must be closed and non-self-intersecting.
5. **Part ID & Filenames**:
   * Part IDs must be unique strings (e.g. `P-01`, `W-NORTH`, `ROOF_L`).
   * Filename must end with `.svg` (e.g. `part_p01_wall.svg`).
6. **Assembly Step Sequence**:
   * Step `0` is always the Complete Assembly.
   * Steps `1..N` must follow a bottom-up physical construction order (Foundation $\to$ Walls $\to$ Braces $\to$ Roof).

---

## 2. Master System Prompt Template for LLMs

Use the following system prompt when asking an AI model to generate a new 3D design:

```markdown
You are an expert CAD and physical 3D puzzle design engineer.
Generate a valid, fully functioning JavaScript model for the PuzzleCore construction platform.

REQUIREMENTS:
1. Export the model using `export const MyModelData = { ... }; export default MyModelData;`.
2. All measurements in millimeters. Nominal sheet thickness is 3.0mm.
3. Every slot must have 0.15mm clearance (slot width = 3.2mm).
4. Parts must physically interlock with mortise-and-tenon tabs.
5. Provide: id, name, category, description, difficulty, overallDimensions, cameraBookmarks, assemblySteps, manufacturingSheets, and parts array.
6. Every part must include: id, fileName, name, category, step, sheet, color, width, length, assembledPos, assembledRot, geometry { outline, cutouts }, and connections.
```

---

## 3. Real Working Examples

### Example 1: Minimal 4-Part Interlocking Box
A starter 4-piece orthogonal interlocking cube demonstrating foundation slots and vertical wall tabs.

```javascript
export const MinimalBoxModel = {
  id: 'minimal-box-ai',
  name: 'Minimal Interlocking Box',
  category: 'Starter / Minimal',
  description: '4-part orthogonal interlocking starter cube.',
  difficulty: 'Level 1 — Starter (4 parts)',
  overallDimensions: { width: 60, length: 60, height: 40 },
  cameraBookmarks: [
    { name: 'Isometric View', eye: [80, 70, 90], target: [0, 15, 0], dist: 130 }
  ],
  assemblySteps: [
    { num: 0, title: 'Full Assembly', desc: 'Finished 4-part cube.' },
    { num: 1, title: 'Base Plate', desc: 'Lay down slotted base plate.', parts: ['B-01'] },
    { num: 2, title: 'Enclosing Walls', desc: 'Slot in North, South, and East walls.', parts: ['B-02', 'B-03', 'B-04'] }
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
      width: 50,
      length: 50,
      assembledPos: [0, 1.5, 0],
      assembledRot: [-Math.PI / 2, 0, 0],
      geometry: {
        outline: [[-25, -25], [25, -25], [25, 25], [-25, 25]],
        cutouts: [
          { x: 0, y: 20, w: 20, h: 3.2, tabId: 'N-SLOT' },
          { x: 0, y: -20, w: 20, h: 3.2, tabId: 'S-SLOT' },
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
      fileName: 'part_b02_north.svg',
      name: 'North Wall',
      category: 'Wall',
      step: 2,
      sheet: 1,
      color: '#d97706',
      width: 50,
      length: 30,
      assembledPos: [0, 16.5, 20],
      assembledRot: [0, 0, 0],
      geometry: {
        outline: [
          [-25, 15], [25, 15], [25, -15],
          [10, -15], [10, -18], [-10, -18], [-10, -15],
          [-25, -15]
        ],
        cutouts: []
      },
      connections: [{ partId: 'B-01', type: 'tab-slot', description: 'Tenon tab into Base' }]
    },
    {
      id: 'B-03',
      fileName: 'part_b03_south.svg',
      name: 'South Wall',
      category: 'Wall',
      step: 2,
      sheet: 1,
      color: '#d97706',
      width: 50,
      length: 30,
      assembledPos: [0, 16.5, -20],
      assembledRot: [0, 0, 0],
      geometry: {
        outline: [
          [-25, 15], [25, 15], [25, -15],
          [10, -15], [10, -18], [-10, -18], [-10, -15],
          [-25, -15]
        ],
        cutouts: []
      },
      connections: [{ partId: 'B-01', type: 'tab-slot', description: 'Tenon tab into Base' }]
    },
    {
      id: 'B-04',
      fileName: 'part_b04_east.svg',
      name: 'East Wall',
      category: 'Wall',
      step: 2,
      sheet: 1,
      color: '#059669',
      width: 40,
      length: 30,
      assembledPos: [20, 16.5, 0],
      assembledRot: [0, Math.PI / 2, 0],
      geometry: {
        outline: [
          [-20, 15], [20, 15], [20, -15],
          [10, -15], [10, -18], [-10, -18], [-10, -15],
          [-20, -15]
        ],
        cutouts: []
      },
      connections: [{ partId: 'B-01', type: 'tab-slot', description: 'Tenon tab into Base' }]
    }
  ]
};
export default MinimalBoxModel;
```

---

### Example 2: Simple Example (Level 1 — Country Gable House)
12 interlocking components including slotted foundation, window cutouts, gabled pitched roof, and chimney. Available directly in the platform under `js/models/simple-house.js`.

---

### Example 3: Medium Example (Level 2 — Gothic Cathedral Pavilion)
32 precision components featuring buttresses, cross-vaulted transept arches, and slotted spires. Available directly in `js/models/cathedral.js`.

---

### Example 4: Complex Example (Level 3 — Grand Olympic Sports Arena)
112 high-density parts including curved multi-tier grandstands, floodlight towers, pitch surface markings, and perimeter security turnstiles. Available directly in `js/models/my-model.js`.

---

## 4. Common Failure Modes & Invalid Example Analysis

Here is an example of an **INVALID** model with explanations of each violation:

```javascript
// ❌ INVALID MODEL DEFINITION (DO NOT USE)
const BadModel = {
  id: "bad model with spaces!",     // ❌ ERROR: Contains spaces and special characters
  // ❌ MISSING: 'name' property
  parts: [
    {
      id: "part-1",
      fileName: "part1.svg",
      name: "Wall",
      // ❌ ERROR: Outline has only 2 vertices (minimum 3 required to form 2D area)
      geometry: {
        outline: [[0, 0], [10, 10]], 
        cutouts: [
          { x: 5, y: 5, w: -3, h: 0 } // ❌ ERROR: Cutout width and height must be > 0
        ]
      },
      assembledPos: [0, "invalid", 0] // ❌ ERROR: Position coordinate contains non-numeric string
    },
    {
      id: "part-1",                   // ❌ ERROR: Duplicate part id "part-1"! Part IDs must be strictly unique.
      fileName: "part2.svg",
      name: "Roof",
      geometry: {
        outline: [[0, 0], [20, 0], [10, 15]]
      }
    }
  ]
};
export default BadModel;
```

### Diagnostic Summary of Errors & Fixes:
1. **Spaces in ID**: Change `bad model with spaces!` to `bad-model-fixed`.
2. **Missing Name**: Add `name: "Fixed Model 1"`.
3. **Degenerate Outline**: Expand outline from 2 points to at least 3 vertices representing a closed polygon.
4. **Negative/Zero Cutouts**: Ensure cutouts have positive width and height (e.g. `w: 3.2, h: 15.0`).
5. **Non-Numeric Coordinates**: Replace `"invalid"` with a floating point number.
6. **Duplicate Part IDs**: Rename second `part-1` to `part-2`.
