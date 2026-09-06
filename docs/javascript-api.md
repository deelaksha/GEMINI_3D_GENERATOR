# PuzzleCore JavaScript Design API & Authoring Guide

This guide describes how to author dynamic 3D construction models using standard JavaScript (ES Modules) in the PuzzleCore WebUI.

---

## 1. Export Conventions

The client-side parser identifies your model definition through multiple standard export patterns:

### Pattern A: Default Export (Recommended)
```javascript
const MyDesign = {
  id: 'modern-pavilion-1',
  name: 'Modern Pavilion 1',
  parts: [ /* ... */ ]
};

export default MyDesign;
```

### Pattern B: Named Export
```javascript
export const MyModelData = {
  id: 'sports-arena-2',
  name: 'Sports Arena 2',
  parts: [ /* ... */ ]
};
```

Both patterns allow you to use standard ES6 syntax, math functions, loops, and modular procedural generation.

---

## 2. Parametric & Procedural Generation

Because designs are authored in full JavaScript, you can use loops and formulas to generate complex assemblies parametrically.

### Example: Procedural Column Array
```javascript
const COLUMNS_COUNT = 8;
const RADIUS = 60;
const columnParts = [];

for (let i = 0; i < COLUMNS_COUNT; i++) {
  const angle = (i / COLUMNS_COUNT) * Math.PI * 2;
  const x = Math.cos(angle) * RADIUS;
  const z = Math.sin(angle) * RADIUS;

  columnParts.push({
    id: `COL-${i + 1}`,
    fileName: `part_col_${i + 1}.svg`,
    name: `Fluted Column #${i + 1}`,
    category: 'Colonnade',
    step: 2,
    sheet: 1,
    color: '#38bdf8',
    width: 12,
    length: 50,
    assembledPos: [x, 25, z],
    assembledRot: [0, -angle, 0],
    geometry: {
      outline: [
        [-6, -25], [6, -25], [6, 25], [-6, 25]
      ],
      cutouts: []
    }
  });
}
```

---

## 3. Mathematical Coordinate System & Units

* **Unit of Measure**: **Millimeters (mm)** across all coordinates, cutouts, widths, and lengths.
* **3D Coordinate Space**: Standard Three.js **Right-Handed, Y-Up**:
  * `+X`: Right
  * `+Y`: Up (Elevation above ground floor)
  * `+Z`: Towards the camera / Forward
* **Rotations**: Euler angles in **radians** `[rx, ry, rz]`.
  * Laying a sheet flat on the ground plane (XZ plane): `assembledRot: [-Math.PI / 2, 0, 0]`
  * Facing North/South (XY plane): `assembledRot: [0, 0, 0]`
  * Facing East/West (ZY plane): `assembledRot: [0, Math.PI / 2, 0]`

---

## 4. Standard Slot & Tab Tolerances

For a nominal sheet gauge $T$ (e.g. $3.0\text{ mm}$):
* **Tab Width**: e.g. $20.0\text{ mm}$
* **Tab Depth**: Exactly equal to or slightly exceeding $T$ ($3.0\text{ mm}$)
* **Mating Slot Length**: $20.0\text{ mm} + \text{clearance}$ (nominal: $20.1\text{ mm}$)
* **Mating Slot Thickness**: $T + \text{clearance}$ (nominal: $3.1\text{ mm} \sim 3.2\text{ mm}$)
* **Kerf Compensation**: Handled dynamically by the runtime engine (default: $0.15\text{ mm}$ laser beam radius).
