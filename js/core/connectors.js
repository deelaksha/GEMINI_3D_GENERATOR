/**
 * Universal Connector & Joint Standards
 * Single Source of Truth for Mechanical Joints, Clearances, and 3D Orientations.
 */

export const ConnectorStandards = {
  // Centralized Clearance & Tolerance Policies
  DEFAULT_CLEARANCE: 0.10, // mm (for friction-fit zero glue joinery)
  DEFAULT_KERF: 0.15,      // mm (laser beam kerf compensation)
  MIN_EDGE_MARGIN: 1.5,    // mm (minimum solid wood distance from enclosed slot to boundary)
  MIN_SLOT_SPACING: 1.0,   // mm (minimum solid wood between adjacent cutouts)

  Types: {
    TAB: 'TAB',
    SLOT: 'SLOT',
    MORTISE_TENON: 'MORTISE_TENON',
    CROSS_HALVING: 'CROSS_HALVING',
    CORNER_RABBET: 'CORNER_RABBET',
    EDGE_FINGER: 'EDGE_FINGER',
    DOVETAIL_LOCK: 'DOVETAIL_LOCK'
  },

  /**
   * Computes slot dimensions based on material thickness and clearance profile.
   */
  calculateSlotDimensions(nominalThickness, clearance = 0.10, kerf = 0.15) {
    const clr = clearance !== undefined ? clearance : this.DEFAULT_CLEARANCE;
    const kf = kerf !== undefined ? kerf : this.DEFAULT_KERF;
    return {
      width: nominalThickness + clr,
      kerfCompensatedWidth: (nominalThickness + clr) - kf,
      clearance: clr,
      kerf: kf
    };
  },

  /**
   * Transforms a 3D vector by Euler XYZ radians. Standalone math (no Three.js dependency needed).
   * Matches THREE.Euler order 'XYZ' (matrix R = Rx * Ry * Rz, so Rz is applied to the vector first),
   * which is how Engine3D renders part.assembledRot.
   */
  rotateVector(vec, eulerRot) {
    if (!eulerRot || eulerRot.length < 3) return [...vec];
    const [rx, ry, rz] = eulerRot;
    const [x, y, z] = vec;

    // Rz
    const cz = Math.cos(rz), sz = Math.sin(rz);
    const x1 = x * cz - y * sz;
    const y1 = x * sz + y * cz;
    const z1 = z;

    // Ry
    const cy = Math.cos(ry), sy = Math.sin(ry);
    const x2 = x1 * cy + z1 * sy;
    const y2 = y1;
    const z2 = -x1 * sy + z1 * cy;

    // Rx
    const cx = Math.cos(rx), sx = Math.sin(rx);
    const x3 = x2;
    const y3 = y2 * cx - z2 * sx;
    const z3 = y2 * sx + z2 * cx;

    return [x3, y3, z3];
  },

  /**
   * Transforms a local 2D point [x, y] to 3D world space using assembledPos and assembledRot.
   */
  local2DToWorld(local2D, assembledPos, assembledRot, localZ = 0) {
    const localVec = [local2D[0], local2D[1], localZ];
    const rotated = this.rotateVector(localVec, assembledRot || [0, 0, 0]);
    const pos = assembledPos || [0, 0, 0];
    return [
      rotated[0] + pos[0],
      rotated[1] + pos[1],
      rotated[2] + pos[2]
    ];
  },

  /**
   * Derives receiver slot dimensions { w, h } directly from the connector tab
   * and the receiver's local orientation, acting as the Single Source of Truth.
   *
   * @param {Object} joint - Unified Joint definition
   * @param {number} thickness - Material thickness (mm)
   * @param {number} clearance - Clearance (mm)
   * @returns {{ w: number, h: number, lengthAxis: string, thicknessAxis: string }}
   */
  deriveReceiverSlot(joint, thickness = 3.0, clearance = 0.10) {
    const clr = clearance !== undefined ? clearance : this.DEFAULT_CLEARANCE;
    const tabWidth = joint.sourceConnector?.width || joint.tabWidth || joint.width || 20;
    const slotThickness = thickness + clr;
    const slotLength = tabWidth + (joint.lengthClearance !== undefined ? joint.lengthClearance : clr);
    const axis = joint.receiverAxis || (joint.axis === 'Y' ? 'Y' : 'X');
    const pos = joint.position || joint.receiverPosition || [0, 0];

    if (axis === 'Y') {
      // Slot length runs along local Y, thickness runs along local X
      return {
        id: joint.id,
        jointId: joint.id,
        x: pos[0],
        y: pos[1],
        w: slotThickness,
        h: slotLength,
        width: slotLength,
        thickness: slotThickness,
        lengthAxis: 'Y',
        thicknessAxis: 'X'
      };
    } else {
      // Slot length runs along local X, thickness runs along local Y
      return {
        id: joint.id,
        jointId: joint.id,
        x: pos[0],
        y: pos[1],
        w: slotLength,
        h: slotThickness,
        width: slotLength,
        thickness: slotThickness,
        lengthAxis: 'X',
        thicknessAxis: 'Y'
      };
    }
  },

  /**
   * Derives all receiver cutouts for a given part from an authoritative joint array.
   */
  deriveCutoutsForPart(partId, joints = [], thickness = 3.0, clearance = 0.10) {
    const receivingJoints = (joints || []).filter(j =>
      (j.targetPart === partId || j.receiverPartId === partId) &&
      j.type !== 'edge-finger' && j.type !== 'box-joint' &&
      j.type !== 'contact' && j.type !== 'surface-contact' && j.type !== 'valley-abut'
    );
    return receivingJoints.map(j => this.deriveReceiverSlot(j, thickness, clearance));
  },

  /**
   * Derives all connector tabs for a given part from an authoritative joint array.
   */
  deriveConnectorsForPart(partId, joints = [], thickness = 3.0) {
    const sendingJoints = (joints || []).filter(j =>
      (j.sourcePart === partId || j.connectorPartId === partId) &&
      j.type !== 'contact' && j.type !== 'surface-contact' && j.type !== 'valley-abut'
    );
    return sendingJoints.map(j => {
      const tabW = j.sourceConnector?.width || j.tabWidth || j.width || 20;
      const tabD = typeof j.tabDepth === 'function' ? j.tabDepth(thickness) : (j.sourceConnector?.depth || j.tabDepth || thickness);
      const pos = j.connectorPosition || j.position || [0, 0];
      const axis = j.connectorAxis || 'X';
      return {
        id: j.id,
        jointId: j.id,
        width: tabW,
        depth: tabD,
        position: pos,
        axis
      };
    });
  },

  /**
   * Calculates world-space vectors for connector width and receiver length
   * to determine whether they are aligned (parallel) or mismatched (crossed at 90 deg).
   */
  calculateJointOrientation(connectorPart, receiverPart, joint) {
    const rotConn = connectorPart.assembledRot || [0, 0, 0];
    const rotRecv = receiverPart.assembledRot || [0, 0, 0];

    // Local 2D axis along which tab width spans
    const localConnVec = joint.connectorAxis === 'Y' ? [0, 1, 0] : [1, 0, 0];
    // Local 2D axis along which slot length spans
    const localRecvVec = joint.receiverAxis === 'Y' ? [0, 1, 0] : [1, 0, 0];

    const worldConnWidth = this.rotateVector(localConnVec, rotConn);
    const worldRecvLength = this.rotateVector(localRecvVec, rotRecv);

    // Dot product of the two unit length directions
    const dot = Math.abs(
      worldConnWidth[0] * worldRecvLength[0] +
      worldConnWidth[1] * worldRecvLength[1] +
      worldConnWidth[2] * worldRecvLength[2]
    );

    // Parallel in world space if dot product is close to 1.0 (threshold 0.92)
    const isAligned = dot >= 0.92;
    const isPerpendicular = dot <= 0.15;

    return {
      dot: Math.round(dot * 1000) / 1000,
      isAligned,
      isPerpendicular,
      worldConnWidth,
      worldRecvLength
    };
  },

  /**
   * Checks whether a point or rectangular cutout has sufficient edge margin
   * from the closed outer polygon outline.
   */
  computeDistanceToPolygon(point, polygon) {
    if (!polygon || polygon.length < 3) return Infinity;
    let minSq = Infinity;
    const px = point[0], py = point[1];

    for (let i = 0; i < polygon.length; i++) {
      const a = polygon[i];
      const b = polygon[(i + 1) % polygon.length];

      const dx = b[0] - a[0];
      const dy = b[1] - a[1];
      const lenSq = dx * dx + dy * dy;

      let t = 0;
      if (lenSq > 0.00001) {
        t = Math.max(0, Math.min(1, ((px - a[0]) * dx + (py - a[1]) * dy) / lenSq));
      }

      const projX = a[0] + t * dx;
      const projY = a[1] + t * dy;
      const distSq = (px - projX) * (px - projX) + (py - projY) * (py - projY);
      if (distSq < minSq) minSq = distSq;
    }

    return Math.sqrt(minSq);
  },

  /**
   * Validates edge margins for all cutouts of a part.
   * Returns issues if any cutout is closer than minMargin to the boundary.
   */
  checkCutoutEdgeMargins(outline, cutouts, minMargin = 4.0) {
    const issues = [];
    if (!outline || outline.length < 3 || !cutouts) return issues;

    cutouts.forEach((c, idx) => {
      const hw = (c.w || 10) / 2;
      const hh = (c.h || 10) / 2;
      const cx = c.x || 0;
      const cy = c.y || 0;

      // Test 4 corners and 4 edge centers of the cutout rectangle
      const testPoints = [
        [cx - hw, cy - hh], [cx + hw, cy - hh],
        [cx + hw, cy + hh], [cx - hw, cy + hh],
        [cx, cy - hh], [cx, cy + hh],
        [cx - hw, cy], [cx + hw, cy]
      ];

      let minDistance = Infinity;
      for (const pt of testPoints) {
        const d = this.computeDistanceToPolygon(pt, outline);
        if (d < minDistance) minDistance = d;
      }

      // If minDistance is near 0 (< 0.25mm), the cutout touches or extends past the outer edge (open edge slot).
      // If minDistance is between 0.25mm and minMargin, it leaves a paper-thin fragile sliver of wood.
      if (minDistance >= 0.25 && minDistance < minMargin - 0.05) {
        issues.push({
          cutoutIndex: idx,
          minDistance: Math.round(minDistance * 100) / 100,
          requiredMargin: minMargin,
          cutout: c
        });
      }
    });

    return issues;
  },

  // Harmonized Manufacturing Limits (§9 Master Directive)
  FATAL_MIN_EDGE_MARGIN: 1.5,       // mm (below this, wood grain shears under insertion pressure)
  RECOMMENDED_EDGE_MARGIN: 3.0,     // mm (recommended structural margin = 1.0 x thickness)
  FATAL_MIN_SLOT_SPACING: 1.0,      // mm (minimum solid bridge between adjacent cutouts)
  RECOMMENDED_SLOT_SPACING: 2.0,    // mm (recommended bridge spacing)

  /**
   * Computes the 3D Oriented Bounding Box (OBB) for an extruded part.
   */
  computePartOBB(part, geo, thickness) {
    const outline = (geo && geo.outline) ? geo.outline : [];
    let minX = -15, maxX = 15, minY = -15, maxY = 15;
    if (outline.length >= 3) {
      minX = Infinity; maxX = -Infinity; minY = Infinity; maxY = -Infinity;
      outline.forEach(pt => {
        if (pt[0] < minX) minX = pt[0];
        if (pt[0] > maxX) maxX = pt[0];
        if (pt[1] < minY) minY = pt[1];
        if (pt[1] > maxY) maxY = pt[1];
      });
    }

    const hx = (maxX - minX) / 2;
    const hy = (maxY - minY) / 2;
    const hz = thickness / 2;
    const localCenter = [(minX + maxX) / 2, (minY + maxY) / 2, 0];

    const pos = typeof part.getAssembledPos === 'function' ? part.getAssembledPos(thickness) :
                (typeof part.assembledPos === 'function' ? part.assembledPos(thickness) : (part.assembledPos || [0, 0, 0]));
    const rot = typeof part.getAssembledRot === 'function' ? part.getAssembledRot(thickness) :
                (typeof part.assembledRot === 'function' ? part.assembledRot(thickness) : (part.assembledRot || [0, 0, 0]));
    const worldCenter = this.local2DToWorld([localCenter[0], localCenter[1]], pos, rot, localCenter[2]);

    const u0 = this.rotateVector([1, 0, 0], rot);
    const u1 = this.rotateVector([0, 1, 0], rot);
    const u2 = this.rotateVector([0, 0, 1], rot);

    return {
      center: worldCenter,
      halfSize: [hx, hy, hz],
      axes: [u0, u1, u2]
    };
  },

  /**
   * Exact 3D Separating Axis Theorem (SAT) for Oriented Bounding Boxes (Narrow-Phase).
   * Tests all 15 potential separating axes.
   * Returns { intersects: boolean, minOverlap: number }
   */
  testOBBOverlap(obbA, obbB) {
    const cA = obbA.center;
    const cB = obbB.center;
    const aA = obbA.axes;
    const aB = obbB.axes;
    const eA = obbA.halfSize;
    const eB = obbB.halfSize;

    // Translation vector from A to B in world coordinates
    const vD = [cB[0] - cA[0], cB[1] - cA[1], cB[2] - cA[2]];

    // Rotation matrix expressing B in A's coordinate frame
    // R[i][j] = dot(aA[i], aB[j])
    const R = [
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0]
    ];
    const AbsR = [
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0]
    ];

    for (let i = 0; i < 3; i++) {
      for (let j = 0; j < 3; j++) {
        const dot = aA[i][0] * aB[j][0] + aA[i][1] * aB[j][1] + aA[i][2] * aB[j][2];
        R[i][j] = dot;
        AbsR[i][j] = Math.abs(dot) + 1e-6; // prevent zero-length cross products
      }
    }

    // Translation vector expressed in A's frame
    const tA = [
      vD[0] * aA[0][0] + vD[1] * aA[0][1] + vD[2] * aA[0][2],
      vD[0] * aA[1][0] + vD[1] * aA[1][1] + vD[2] * aA[1][2],
      vD[0] * aA[2][0] + vD[1] * aA[2][1] + vD[2] * aA[2][2]
    ];

    let minOverlap = Infinity;

    // 1. Test A's 3 face normals: L = aA[0], aA[1], aA[2]
    for (let i = 0; i < 3; i++) {
      const ra = eA[i];
      const rb = eB[0] * AbsR[i][0] + eB[1] * AbsR[i][1] + eB[2] * AbsR[i][2];
      const dist = Math.abs(tA[i]);
      if (dist > ra + rb + 0.05) return { intersects: false, minOverlap: 0 };
      const overlap = (ra + rb) - dist;
      if (overlap < minOverlap) minOverlap = overlap;
    }

    // 2. Test B's 3 face normals: L = aB[0], aB[1], aB[2]
    for (let j = 0; j < 3; j++) {
      const ra = eA[0] * AbsR[0][j] + eA[1] * AbsR[1][j] + eA[2] * AbsR[2][j];
      const rb = eB[j];
      const dist = Math.abs(tA[0] * R[0][j] + tA[1] * R[1][j] + tA[2] * R[2][j]);
      if (dist > ra + rb + 0.05) return { intersects: false, minOverlap: 0 };
      const overlap = (ra + rb) - dist;
      if (overlap < minOverlap) minOverlap = overlap;
    }

    // 3. Test 9 edge cross-products: L = aA[i] x aB[j]
    // Skip nearly parallel axes where cross product is zero/degenerate
    // Axis: aA[0] x aB[0]
    if (AbsR[0][0] < 0.999) {
      const ra = eA[1] * AbsR[2][0] + eA[2] * AbsR[1][0];
      const rb = eB[1] * AbsR[0][2] + eB[2] * AbsR[0][1];
      const dist = Math.abs(tA[2] * R[1][0] - tA[1] * R[2][0]);
      if (dist > ra + rb + 0.05) return { intersects: false, minOverlap: 0 };
    }
    // Axis: aA[0] x aB[1]
    if (AbsR[0][1] < 0.999) {
      const ra = eA[1] * AbsR[2][1] + eA[2] * AbsR[1][1];
      const rb = eB[0] * AbsR[0][2] + eB[2] * AbsR[0][0];
      const dist = Math.abs(tA[2] * R[1][1] - tA[1] * R[2][1]);
      if (dist > ra + rb + 0.05) return { intersects: false, minOverlap: 0 };
    }
    // Axis: aA[0] x aB[2]
    if (AbsR[0][2] < 0.999) {
      const ra = eA[1] * AbsR[2][2] + eA[2] * AbsR[1][2];
      const rb = eB[0] * AbsR[0][1] + eB[1] * AbsR[0][0];
      const dist = Math.abs(tA[2] * R[1][2] - tA[1] * R[2][2]);
      if (dist > ra + rb + 0.05) return { intersects: false, minOverlap: 0 };
    }

    // Axis: aA[1] x aB[0]
    if (AbsR[1][0] < 0.999) {
      const ra = eA[0] * AbsR[2][0] + eA[2] * AbsR[0][0];
      const rb = eB[1] * AbsR[1][2] + eB[2] * AbsR[1][1];
      const dist = Math.abs(tA[0] * R[2][0] - tA[2] * R[0][0]);
      if (dist > ra + rb + 0.05) return { intersects: false, minOverlap: 0 };
    }
    // Axis: aA[1] x aB[1]
    if (AbsR[1][1] < 0.999) {
      const ra = eA[0] * AbsR[2][1] + eA[2] * AbsR[0][1];
      const rb = eB[0] * AbsR[1][2] + eB[2] * AbsR[1][0];
      const dist = Math.abs(tA[0] * R[2][1] - tA[2] * R[0][1]);
      if (dist > ra + rb + 0.05) return { intersects: false, minOverlap: 0 };
    }
    // Axis: aA[1] x aB[2]
    if (AbsR[1][2] < 0.999) {
      const ra = eA[0] * AbsR[2][2] + eA[2] * AbsR[0][2];
      const rb = eB[0] * AbsR[1][1] + eB[1] * AbsR[1][0];
      const dist = Math.abs(tA[0] * R[2][2] - tA[2] * R[0][2]);
      if (dist > ra + rb + 0.05) return { intersects: false, minOverlap: 0 };
    }

    // Axis: aA[2] x aB[0]
    if (AbsR[2][0] < 0.999) {
      const ra = eA[0] * AbsR[1][0] + eA[1] * AbsR[0][0];
      const rb = eB[1] * AbsR[2][2] + eB[2] * AbsR[2][1];
      const dist = Math.abs(tA[1] * R[0][0] - tA[0] * R[1][0]);
      if (dist > ra + rb + 0.05) return { intersects: false, minOverlap: 0 };
    }
    // Axis: aA[2] x aB[1]
    if (AbsR[2][1] < 0.999) {
      const ra = eA[0] * AbsR[1][1] + eA[1] * AbsR[0][1];
      const rb = eB[0] * AbsR[2][2] + eB[2] * AbsR[2][0];
      const dist = Math.abs(tA[1] * R[0][1] - tA[0] * R[1][1]);
      if (dist > ra + rb + 0.05) return { intersects: false, minOverlap: 0 };
    }
    // Axis: aA[2] x aB[2]
    if (AbsR[2][2] < 0.999) {
      const ra = eA[0] * AbsR[1][2] + eA[1] * AbsR[0][2];
      const rb = eB[0] * AbsR[2][1] + eB[1] * AbsR[2][0];
      const dist = Math.abs(tA[1] * R[0][2] - tA[0] * R[1][2]);
      if (dist > ra + rb + 0.05) return { intersects: false, minOverlap: 0 };
    }

    return { intersects: true, minOverlap };
  }
};

export const ConnectorRegistry = ConnectorStandards;
