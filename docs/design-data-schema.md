# PuzzleCore Design Data Schema Specification

This document provides the exhaustive specification for JavaScript design objects in PuzzleCore.

---

## 1. Top-Level Construction Object

A valid design object conforms to the following schema:

```typescript
interface ConstructionObjectModel {
  id: string;                     // Unique identifier (slug, e.g. "modern-villa-1")
  name: string;                   // Human-friendly title (e.g. "Modern Villa 1")
  category?: string;              // "Architecture", "Starter", "Vehicle", etc.
  description?: string;           // Detailed notes, assembly advice
  difficulty?: string;            // e.g. "Level 1 — Beginner (4 parts)"
  overallDimensions?: {
    width: number;                // Dimension along X-axis (mm)
    length: number;               // Dimension along Z-axis (mm)
    height: number;               // Dimension along Y-axis (mm)
  };
  cameraBookmarks?: CameraBookmark[];
  assemblySteps?: AssemblyStep[];
  manufacturingSheets?: ManufacturingSheet[];
  parts: PartDefinition[];        // Array of physical parts (at least 1)
}
```

---

## 2. Part Definition Entity

Each part represents an individual planar sheet component that will be manufactured (laser cut / CNC milled / stamped) and assembled in 3D space:

```typescript
interface PartDefinition {
  id: string;                     // Unique part ID (e.g. "P-01", "BASE_PLATE")
  fileName: string;               // Virtual cut file (e.g. "part_p01_base.svg")
  name: string;                   // Human-readable part name (e.g. "Ground Foundation Floor")
  category: string;               // "Foundation", "Wall", "Roof", "Brace", etc.
  step: number;                   // Stage number in assembly sequence (1-based)
  sheet: number;                  // Assigned nesting sheet index (1-based)
  color: string;                  // Hex or CSS color string (e.g. "#0284c7")
  thickness?: number;             // Default material thickness (usually 3.0mm)
  width: number;                  // Bounding width in mm
  length: number;                 // Bounding length in mm
  assembledPos: [number, number, number]; // [X, Y, Z] world position in assembly
  assembledRot: [number, number, number]; // [EulerX, EulerY, EulerZ] in radians
  geometry: PartGeometry;         // 2D outline and interior cutout definitions
  connections?: PartConnection[]; // Mating relationships with other parts
}
```

---

## 3. Geometry: 2D Outline & Cutouts

The geometry object represents the physical flat cut shape before extrusion:

```typescript
interface PartGeometry {
  outline: [number, number][];    // Closed polygon coordinates in mm: [[x1, y1], [x2, y2], ...]
  cutouts?: CutoutDefinition[];   // Internal holes, mortise slots, or engravings
}

interface CutoutDefinition {
  x: number;                      // Center X coordinate relative to part origin (mm)
  y: number;                      // Center Y coordinate relative to part origin (mm)
  w: number;                      // Cutout width (mm)
  h: number;                      // Cutout height (mm)
  tabId?: string;                 // Identifier of the mating tenon or partner slot
  type?: 'slot' | 'hole' | 'decorative';
}
```

### Outline Rules:
1. Vertices must be defined in **counter-clockwise (CCW)** order for proper outward-facing normals.
2. The polygon must contain at least 3 vertices and must be non-self-intersecting.
3. Coordinates are specified in local part space in millimeters.

---

## 4. Connections & Assembly Steps

### 4.1. Mating Connection Pair

```typescript
interface PartConnection {
  partId: string;                 // ID of the mating part
  type: 'slot-tab' | 'tab-slot' | 'butt-joint' | 'cross-lap' | 'hinge';
  description: string;            // Descriptive note (e.g. "Base Slot #2 into Wall Tab")
}
```

### 4.2. Assembly Step

```typescript
interface AssemblyStep {
  num: number;                    // Step number (0 is reserved for Full Assembly)
  title: string;                  // Short step summary
  desc: string;                   // Detailed instructional text
  parts?: string[];               // Array of part IDs introduced in this step
}
```

### 4.3. Camera Sightline Bookmark

```typescript
interface CameraBookmark {
  name: string;                   // Bookmark label (e.g. "Front Porch View")
  eye?: [number, number, number]; // Camera eye position
  target: [number, number, number]; // Target point lookAt vector
  dist: number;                   // Distance to target
  select?: string;                // Optional part ID to automatically highlight
}
```
