import assert from 'node:assert/strict';

export function computeBbox(pts) {
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y0 = Math.min(...ys), y1 = Math.max(...ys);
  return { x0, x1, y0, y1, width: x1 - x0, height: y1 - y0 };
}

export function distPtSeg(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1, dy = y2 - y1;
  const L2 = dx * dx + dy * dy;
  if (L2 < 1e-9) return Math.hypot(px - x1, py - y1);
  const t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / L2));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

export function analyzeEdges(pts) {
  const n = pts.length;
  const edges = [];
  const cx = pts.reduce((s, p) => s + p[0], 0) / n;
  const cy = pts.reduce((s, p) => s + p[1], 0) / n;

  for (let i = 0; i < n; i++) {
    const pA = pts[i];
    const pB = pts[(i + 1) % n];
    const dx = pB[0] - pA[0];
    const dy = pB[1] - pA[1];
    const length = Math.hypot(dx, dy);
    const run = Math.abs(dx);
    const rise = Math.abs(dy);
    const angleDeg = Math.abs(dx) < 1e-5 ? 90.0 : Math.round(Math.atan2(rise, run) * 1800 / Math.PI) / 10;
    
    let type = 'angled';
    if (rise < 0.05) type = 'horizontal';
    else if (run < 0.05) type = 'vertical';

    // Included corner angle at pB
    const pC = pts[(i + 2) % n];
    const v1 = [pA[0] - pB[0], pA[1] - pB[1]];
    const v2 = [pC[0] - pB[0], pC[1] - pB[1]];
    const dot = v1[0] * v2[0] + v1[1] * v2[1];
    const mag1 = Math.hypot(...v1);
    const mag2 = Math.hypot(...v2);
    const cosA = Math.max(-1, Math.min(1, dot / (mag1 * mag2)));
    const cornerAngleDeg = Math.round(Math.acos(cosA) * 1800 / Math.PI) / 10;

    const mid = [(pA[0] + pB[0]) / 2, (pA[1] + pB[1]) / 2];
    let nx = length > 0 ? dy / length : 0;
    let ny = length > 0 ? -dx / length : 0;
    if ((mid[0] - cx) * nx + (mid[1] - cy) * ny < 0) {
      nx = -nx;
      ny = -ny;
    }

    edges.push({
      index: i + 1,
      pA, pB, dx, dy, length: Math.round(length * 100) / 100,
      run: Math.round(run * 100) / 100,
      rise: Math.round(rise * 100) / 100,
      angleDeg,
      cornerAngleDeg,
      isApex: cornerAngleDeg < 85,
      type,
      mid,
      normal: [nx, ny]
    });
  }
  return edges;
}

export function analyzeFeatures(features, outlinePts, bbox) {
  const n = outlinePts.length;
  const analyzed = [];

  for (let idx = 0; idx < features.length; idx++) {
    const f = features[idx];
    let poly = f.polygon;
    if (!poly) {
      const cx = f.center[0], cy = f.center[1];
      const hw = (f.width || 0) / 2, hh = (f.height || 0) / 2;
      const ang = ((f.angle || 0) * Math.PI) / 180;
      const cosA = Math.cos(ang), sinA = Math.sin(ang);
      const corners = [
        [-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]
      ];
      poly = corners.map(([rx, ry]) => [
        cx + rx * cosA - ry * sinA,
        cy + rx * sinA + ry * cosA
      ]);
    }

    const fxs = poly.map((p) => p[0]);
    const fys = poly.map((p) => p[1]);
    const minX = Math.min(...fxs), maxX = Math.max(...fxs);
    const minY = Math.min(...fys), maxY = Math.max(...fys);

    // Gaps to component outer bounding box
    const gapBottom = Math.round((minY - bbox.y0) * 10) / 10;
    const gapTop = Math.round((bbox.y1 - maxY) * 10) / 10;
    const gapLeft = Math.round((minX - bbox.x0) * 10) / 10;
    const gapRight = Math.round((bbox.x1 - maxX) * 10) / 10;

    // Minimum solid margin to actual perimeter polygon
    let minMargin = Infinity;
    for (const pt of poly) {
      for (let i = 0; i < n; i++) {
        const pA = outlinePts[i], pB = outlinePts[(i + 1) % n];
        const d = distPtSeg(pt[0], pt[1], pA[0], pA[1], pB[0], pB[1]);
        if (d < minMargin) minMargin = d;
      }
    }
    minMargin = Math.round(minMargin * 10) / 10;

    analyzed.push({
      id: f.id,
      kind: f.kind,
      shape: f.shape,
      center: f.center,
      width: Math.round((f.width || 0) * 10) / 10,
      height: Math.round((f.height || 0) * 10) / 10,
      angle: f.angle || 0,
      poly,
      bounds: { minX, maxX, minY, maxY },
      gapBottom,
      gapTop,
      gapLeft,
      gapRight,
      minMargin,
      spacingToNext: null,
      nextId: null
    });
  }

  // Find neighbor spacing along horizontal and vertical axes
  for (let i = 0; i < analyzed.length; i++) {
    const f1 = analyzed[i];
    let bestDist = Infinity;
    let nextFeat = null;
    for (let j = 0; j < analyzed.length; j++) {
      if (i === j) continue;
      const f2 = analyzed[j];
      // Check horizontal alignment (similar Y)
      if (Math.abs(f1.center[1] - f2.center[1]) < 3.0) {
        if (f2.bounds.minX >= f1.bounds.maxX - 0.1) {
          const gap = f2.bounds.minX - f1.bounds.maxX;
          if (gap < bestDist) {
            bestDist = gap;
            nextFeat = f2;
          }
        }
      }
    }
    if (nextFeat && Number.isFinite(bestDist)) {
      f1.spacingToNext = Math.round(bestDist * 10) / 10;
      f1.nextId = nextFeat.id;
    }
  }

  return analyzed;
}

// Test with clean-interlocking-sailboat-e403 bottom part
const testOutline = [
  [-78.0, -22.0],
  [-38.0, -28.0],
  [38.0, -28.0],
  [78.0, 0.0],
  [38.0, 28.0],
  [-38.0, 28.0],
  [-78.0, 22.0]
];

const testFeatures = [
  {
    angle: 0.0,
    center: [-47.0, 19.5],
    height: 1.1,
    id: "slot-HULLL-BOT-t1",
    kind: "slot",
    polygon: [[-61.05, 18.95], [-32.95, 18.95], [-32.95, 20.05], [-61.05, 20.05]],
    shape: "rect",
    width: 28.1
  },
  {
    angle: 0.0,
    center: [9.0, 19.5],
    height: 1.1,
    id: "slot-HULLL-BOT-t2",
    kind: "slot",
    polygon: [[-5.05, 18.95], [23.05, 18.95], [23.05, 20.05], [-5.05, 20.05]],
    shape: "rect",
    width: 28.1
  }
];

const bbox = computeBbox(testOutline);
const analyzedFeats = analyzeFeatures(testFeatures, testOutline, bbox);

assert.equal(analyzedFeats[0].gapTop, 8.0);
assert.equal(analyzedFeats[0].gapLeft, 17.0);
assert.equal(analyzedFeats[0].minMargin, 4.4);
assert.equal(analyzedFeats[0].spacingToNext, 27.9);
assert.equal(analyzedFeats[0].nextId, "slot-HULLL-BOT-t2");

console.log('✓ Feature gaps and spacing tests passed!');
