/**
 * Board Studio — CAD Precision Cut & Gap Inspector (2D Blueprint & Shop Specs)
 *
 * Provides high-contrast, color-coded, non-overlapping 2D CAD cutting blueprints
 * with physical millimeter grid, animated gap zones, loupe magnifier, cut order,
 * synchronized checklist, Full Screen workshop mode, and comprehensive step-by-step
 * manual hand-cutting guides for fast, error-free physical cutting.
 */

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/**
 * Checks whether a numerical dimension is a clean integer (no non-zero decimal fraction).
 */
export function isCleanInteger(v) {
  if (v === null || v === undefined || isNaN(v)) return false;
  return Math.abs(v - Math.round(v)) < 1e-4;
}

/**
 * Format dimensions cleanly: whole numbers display as clean integers without any
 * trailing '.0' (e.g. 30, 38, 7, 12 mm), while numbers with decimal fractions display their decimals.
 */
export function fmt(v, maxDecimals = 1) {
  if (v === null || v === undefined || isNaN(v)) return '0';
  const rounded = Math.round(v * 10 ** maxDecimals) / 10 ** maxDecimals;
  if (isCleanInteger(rounded)) {
    return Math.round(rounded).toString();
  }
  return rounded.toFixed(maxDecimals);
}

export function computeBbox(pts) {
  if (!pts || !pts.length) return { x0: 0, x1: 0, y0: 0, y1: 0, width: 0, height: 0 };
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

/**
 * Creates a crisp, high-contrast rounded pill label for SVG dimensions.
 * Ensures ample width so millimeter units are never clipped or truncated.
 */
export function svgPill(x, y, text, color, bg = '#0f172a', width = null) {
  const w = width || Math.max(62, text.length * 8.6 + 22);
  return `
    <g transform="translate(${x.toFixed(1)}, ${y.toFixed(1)})">
      <rect x="${(-w / 2).toFixed(1)}" y="-11" width="${w.toFixed(1)}" height="22" rx="6"
            fill="${bg}" stroke="${color}" stroke-width="1.4" />
      <text x="0" y="4" text-anchor="middle" fill="${color}"
            font-family="'JetBrains Mono', monospace" font-size="11.5" font-weight="700">${text}</text>
    </g>
  `;
}

/**
 * Computes complete shop & drafting specifications for any component,
 * including thorough step-by-step manual hand-cutting guides.
 */
export function computeDraftingSpecs(c) {
  const pts = c.cut_outline || [];
  const n = pts.length;
  if (n < 3) return null;

  const bbox = computeBbox(pts);
  const cx = pts.reduce((s, p) => s + p[0], 0) / n;
  const cy = pts.reduce((s, p) => s + p[1], 0) / n;
  const thickness = c.thickness || 1.0;

  // 1. Analyze perimeter edges & corners
  const edges = [];
  let apexCorner = null;

  // Detect true geometric peaks (e.g. roof gables, triangular peaks, boat bow)
  // Top peak: point with max Y that is inset from left/right sides and strictly higher than its neighbors
  const topPeakPt = pts.find((p, idx) => {
    const pPrev = pts[(idx - 1 + n) % n];
    const pNext = pts[(idx + 1) % n];
    return p[1] >= bbox.y1 - 0.5 && p[0] > bbox.x0 + 1.5 && p[0] < bbox.x1 - 1.5 &&
           p[1] > pPrev[1] + 0.5 && p[1] > pNext[1] + 0.5;
  });

  // Right bow point: point with max X that is inset from top/bottom sides and strictly beyond its neighbors
  const rightBowPt = pts.find((p, idx) => {
    const pPrev = pts[(idx - 1 + n) % n];
    const pNext = pts[(idx + 1) % n];
    return p[0] >= bbox.x1 - 0.5 && p[1] > bbox.y0 + 1.5 && p[1] < bbox.y1 - 1.5 &&
           p[0] > pPrev[0] + 0.5 && p[0] > pNext[0] + 0.5;
  });

  if (topPeakPt) {
    const idx = pts.indexOf(topPeakPt);
    const pPrev = pts[(idx - 1 + n) % n];
    const pNext = pts[(idx + 1) % n];
    const v1 = [pPrev[0] - topPeakPt[0], pPrev[1] - topPeakPt[1]];
    const v2 = [pNext[0] - topPeakPt[0], pNext[1] - topPeakPt[1]];
    const dot = v1[0] * v2[0] + v1[1] * v2[1];
    const mag = Math.hypot(...v1) * Math.hypot(...v2);
    const cosA = Math.max(-1, Math.min(1, dot / (mag || 1)));
    const angle = Math.round(Math.acos(cosA) * 1800 / Math.PI) / 10;

    // Detect shoulder height (where the gable angles meet the vertical walls)
    const leftCandidates = pts.filter((p) => Math.abs(p[0] - bbox.x0) < 1.0 && p[1] < topPeakPt[1] - 0.5);
    const rightCandidates = pts.filter((p) => Math.abs(p[0] - bbox.x1) < 1.0 && p[1] < topPeakPt[1] - 0.5);
    const leftShoulderY = leftCandidates.length ? Math.max(...leftCandidates.map((p) => p[1])) : bbox.y0;
    const rightShoulderY = rightCandidates.length ? Math.max(...rightCandidates.map((p) => p[1])) : bbox.y0;
    const shoulderY = Math.round(Math.max(leftShoulderY, rightShoulderY) * 10) / 10;
    const rise = Math.round((topPeakPt[1] - shoulderY) * 10) / 10;
    const run = Math.round(Math.abs(topPeakPt[0] - bbox.x0) * 10) / 10;
    const pitch = run > 0 ? Math.round(Math.atan2(rise, run) * 1800 / Math.PI) / 10 : 45.0;
    const cutLength = Math.round(Math.hypot(run, rise) * 10) / 10;

    apexCorner = {
      pt: topPeakPt,
      angle,
      pitch,
      rise,
      run,
      cutLength,
      shoulderY,
      dir: 'top'
    };
  } else if (rightBowPt) {
    const idx = pts.indexOf(rightBowPt);
    const pPrev = pts[(idx - 1 + n) % n];
    const pNext = pts[(idx + 1) % n];
    const v1 = [pPrev[0] - rightBowPt[0], pPrev[1] - rightBowPt[1]];
    const v2 = [pNext[0] - rightBowPt[0], pNext[1] - rightBowPt[1]];
    const dot = v1[0] * v2[0] + v1[1] * v2[1];
    const mag = Math.hypot(...v1) * Math.hypot(...v2);
    const cosA = Math.max(-1, Math.min(1, dot / (mag || 1)));
    const angle = Math.round(Math.acos(cosA) * 1800 / Math.PI) / 10;

    const shoulderCandidates = pts.filter((p) => p[0] < rightBowPt[0] - 1.0 && (Math.abs(p[1] - bbox.y0) < 2.5 || Math.abs(p[1] - bbox.y1) < 2.5));
    const shoulderX = shoulderCandidates.length ? Math.max(...shoulderCandidates.map((p) => p[0])) : bbox.x0;
    const run = Math.round((rightBowPt[0] - shoulderX) * 10) / 10;
    const rise = Math.round((bbox.height / 2) * 10) / 10;
    const pitch = run > 0 ? Math.round(Math.atan2(rise, run) * 1800 / Math.PI) / 10 : 45.0;
    const cutLength = Math.round(Math.hypot(run, rise) * 10) / 10;

    apexCorner = {
      pt: rightBowPt,
      angle,
      pitch,
      run,
      rise,
      cutLength,
      shoulderX,
      dir: 'right'
    };
  }

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
    let name = 'Angled cut';
    if (rise < 0.05) {
      type = 'horizontal';
      name = (pA[1] + pB[1]) / 2 < cy ? 'Bottom edge' : 'Top edge';
    } else if (run < 0.05) {
      type = 'vertical';
      name = (pA[0] + pB[0]) / 2 < cx ? 'Left edge' : 'Right edge';
    } else {
      if ((pA[0] + pB[0]) / 2 > cx) name = 'Bow / gable angle';
      else name = 'Aft / gable angle';
    }

    // Corner / included angle at pB
    const pC = pts[(i + 2) % n];
    const v1 = [pA[0] - pB[0], pA[1] - pB[1]];
    const v2 = [pC[0] - pB[0], pC[1] - pB[1]];
    const dot = v1[0] * v2[0] + v1[1] * v2[1];
    const mag1 = Math.hypot(...v1);
    const mag2 = Math.hypot(...v2);
    const cosA = Math.max(-1, Math.min(1, dot / ((mag1 * mag2) || 1)));
    const cornerAngleDeg = Math.round(Math.acos(cosA) * 1800 / Math.PI) / 10;

    // Outward normal in CAD plane
    const mid = [(pA[0] + pB[0]) / 2, (pA[1] + pB[1]) / 2];
    let nx = length > 0 ? dy / length : 0;
    let ny = length > 0 ? -dx / length : 0;
    if ((mid[0] - cx) * nx + (mid[1] - cy) * ny < 0) {
      nx = -nx;
      ny = -ny;
    }

    edges.push({
      index: i + 1,
      pA, pB, dx, dy,
      length: Math.round(length * 10) / 10,
      run: Math.round(run * 10) / 10,
      rise: Math.round(rise * 10) / 10,
      angleDeg,
      cornerAngleDeg,
      type,
      name,
      mid,
      normal: [nx, ny]
    });
  }

  // 2. Analyze features (slots, holes, openings)
  const features = [];
  const rawFeatures = c.features || c.cutouts || c.slots || [];

  for (let idx = 0; idx < rawFeatures.length; idx++) {
    const f = rawFeatures[idx];
    const center = f.center || (f.position ? [f.position[0], f.position[1]] : [0, 0]);
    let poly = f.polygon;
    if (!poly) {
      const fcx = center[0], fcy = center[1];
      if (f.shape === 'circle') {
        const r = (f.diameter || 0) / 2;
        poly = [[fcx - r, fcy - r], [fcx + r, fcy - r], [fcx + r, fcy + r], [fcx - r, fcy + r]];
      } else {
        const hw = (f.width || 0) / 2, hh = (f.height || 0) / 2;
        const ang = ((f.angle || 0) * Math.PI) / 180;
        const cosA = Math.cos(ang), sinA = Math.sin(ang);
        const corners = [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]];
        poly = corners.map(([rx, ry]) => [
          fcx + rx * cosA - ry * sinA,
          fcy + rx * sinA + ry * cosA
        ]);
      }
    }

    const fxs = poly.map((p) => p[0]);
    const fys = poly.map((p) => p[1]);
    const minX = Math.min(...fxs), maxX = Math.max(...fxs);
    const minY = Math.min(...fys), maxY = Math.max(...fys);

    const gapBottom = Math.round((minY - bbox.y0) * 10) / 10;
    const gapTop = Math.round((bbox.y1 - maxY) * 10) / 10;
    const gapLeft = Math.round((minX - bbox.x0) * 10) / 10;
    const gapRight = Math.round((bbox.x1 - maxX) * 10) / 10;

    // Minimum solid margin to outer perimeter
    let minMargin = Infinity;
    for (const pt of poly) {
      for (let i = 0; i < n; i++) {
        const pA = pts[i], pB = pts[(i + 1) % n];
        const d = distPtSeg(pt[0], pt[1], pA[0], pA[1], pB[0], pB[1]);
        if (d < minMargin) minMargin = d;
      }
    }
    minMargin = Math.round(minMargin * 10) / 10;

    features.push({
      id: f.id,
      order: idx + 1,
      kind: f.kind,
      shape: f.shape,
      center,
      width: Math.round((f.width || 0) * 10) / 10,
      height: Math.round((f.height || 0) * 10) / 10,
      diameter: f.diameter ? Math.round(f.diameter * 10) / 10 : null,
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

  // Calculate inter-slot spacing between adjacent slots
  for (let i = 0; i < features.length; i++) {
    const f1 = features[i];
    let bestDist = Infinity;
    let nextFeat = null;
    for (let j = 0; j < features.length; j++) {
      if (i === j) continue;
      const f2 = features[j];
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

  // 3. Analyze edge tabs and slant joints (detected from outline and/or declared in c.tabs)
  function distPts(p1, p2) { return Math.hypot(p2[0] - p1[0], p2[1] - p1[1]); }
  function dotPts(p1, p2, p3, p4) { return (p2[0] - p1[0]) * (p4[0] - p3[0]) + (p2[1] - p1[1]) * (p4[1] - p3[1]); }

  const tabs = [];
  const rawDeclaredTabs = c.tabs || [];
  const usedDeclaredTabs = new Set();

  // 3a. Detect 4-point step tabs/notches directly from cut_outline
  for (let i = 0; i < n; i++) {
    const v0 = pts[i], v1 = pts[(i + 1) % n], v2 = pts[(i + 2) % n], v3 = pts[(i + 3) % n];
    const L1 = distPts(v0, v1);
    const L2 = distPts(v1, v2);
    const L3 = distPts(v2, v3);

    if (L1 >= 0.5 && L1 <= 20.0 && L3 >= 0.5 && L3 <= 20.0 && Math.abs(L1 - L3) < 1.2 && L2 >= 1.5) {
      const d12 = dotPts(v0, v1, v1, v2) / ((L1 * L2) || 1);
      const d13 = dotPts(v0, v1, v2, v3) / ((L1 * L3) || 1);
      const d23 = dotPts(v1, v2, v2, v3) / ((L2 * L3) || 1);

      if (Math.abs(d12) < 0.35 && d13 < -0.8 && Math.abs(d23) < 0.35) {
        const isSlant = Math.abs(v2[0] - v1[0]) > 0.5 && Math.abs(v2[1] - v1[1]) > 0.5;
        const midX = (v1[0] + v2[0]) / 2;
        const midY = (v1[1] + v2[1]) / 2;

        let locName = 'Edge Joint';
        let distFromStart = 0;
        let distFromEnd = 0;
        let startName = 'corner';
        let endName = 'corner';

        if (isSlant && apexCorner && apexCorner.dir === 'top') {
          if (midX >= (apexCorner.pt[0] - 1.0)) {
            locName = 'Right Roof Slant Joint';
            const rShoulder = [bbox.x1, apexCorner.shoulderY !== null ? apexCorner.shoulderY : bbox.y0];
            distFromStart = Math.round(distPts(rShoulder, v0) * 10) / 10;
            distFromEnd = Math.round(distPts(v3, apexCorner.pt) * 10) / 10;
            startName = 'right shoulder';
            endName = 'apex peak';
          } else {
            locName = 'Left Roof Slant Joint';
            const lShoulder = [bbox.x0, apexCorner.shoulderY !== null ? apexCorner.shoulderY : bbox.y0];
            distFromStart = Math.round(distPts(lShoulder, v3) * 10) / 10;
            distFromEnd = Math.round(distPts(v0, apexCorner.pt) * 10) / 10;
            startName = 'left shoulder';
            endName = 'apex peak';
          }
        } else if (Math.abs(midY - bbox.y0) < 5.0) {
          locName = 'Bottom Baseline Joint';
          distFromStart = Math.round(distPts([bbox.x0, bbox.y0], v0) * 10) / 10;
          distFromEnd = Math.round(distPts(v3, [bbox.x1, bbox.y0]) * 10) / 10;
          startName = 'bottom-left corner';
          endName = 'bottom-right corner';
        } else if (Math.abs(midY - bbox.y1) < 5.0) {
          locName = 'Top Baseline Joint';
          distFromStart = Math.round(distPts([bbox.x0, bbox.y1], v0) * 10) / 10;
          distFromEnd = Math.round(distPts(v3, [bbox.x1, bbox.y1]) * 10) / 10;
          startName = 'top-left corner';
          endName = 'top-right corner';
        } else if (Math.abs(midX - bbox.x0) < 5.0) {
          locName = 'Left Wall Edge Joint';
          distFromStart = Math.round(distPts([bbox.x0, bbox.y0], v0) * 10) / 10;
          distFromEnd = Math.round(distPts(v3, [bbox.x0, bbox.y1]) * 10) / 10;
          startName = 'bottom-left corner';
          endName = 'top-left corner';
        } else if (Math.abs(midX - bbox.x1) < 5.0) {
          locName = 'Right Wall Edge Joint';
          distFromStart = Math.round(distPts([bbox.x1, bbox.y0], v0) * 10) / 10;
          distFromEnd = Math.round(distPts(v3, [bbox.x1, bbox.y1]) * 10) / 10;
          startName = 'bottom-right corner';
          endName = 'top-right corner';
        } else {
          distFromStart = Math.round(distPts(pts[(i - 1 + n) % n], v0) * 10) / 10;
          distFromEnd = Math.round(distPts(v3, pts[(i + 4) % n]) * 10) / 10;
        }

        const declared = rawDeclaredTabs.find((dt) => {
          if (usedDeclaredTabs.has(dt)) return false;
          if (dt.width && Math.abs(dt.width - L2) < 2.0) {
            if (isSlant && dt.id) {
              const dtId = dt.id.toLowerCase();
              if (locName.includes('Right') && (dtId.includes('roofr') || dtId.includes('right') || dt.edge === 2)) return true;
              if (locName.includes('Left') && (dtId.includes('roofl') || dtId.includes('left') || dt.edge === 3)) return true;
            }
            return true;
          }
          return false;
        });
        if (declared) usedDeclaredTabs.add(declared);

        tabs.push({
          id: declared ? declared.id : `tab-${tabs.length + 1}`,
          name: declared?.name || locName,
          edge: declared ? declared.edge : null,
          locName,
          width: Math.round(L2 * 10) / 10,
          depth: Math.round(L1 * 10) / 10,
          distFromStart,
          distFromEnd,
          startName,
          endName,
          mid: [Math.round(midX * 10) / 10, Math.round(midY * 10) / 10],
          pRoot1: [Math.round(v0[0] * 10) / 10, Math.round(v0[1] * 10) / 10],
          pTip1: [Math.round(v1[0] * 10) / 10, Math.round(v1[1] * 10) / 10],
          pTip2: [Math.round(v2[0] * 10) / 10, Math.round(v2[1] * 10) / 10],
          pRoot2: [Math.round(v3[0] * 10) / 10, Math.round(v3[1] * 10) / 10],
          isSlant
        });
      }
    }
  }

  // 3b. If no geometric tabs were detected from cut_outline, fall back to c.tabs
  if (tabs.length === 0 && rawDeclaredTabs.length > 0) {
    const outlinePts = c.outline || [];
    rawDeclaredTabs.forEach((t, idx) => {
      let pRoot1 = null, pTip1 = null, pTip2 = null, pRoot2 = null;
      let isSlant = false;
      let distFromStart = Math.round(Math.max(0, (t.offset || 0) - (t.width || 0) / 2) * 10) / 10;
      let distFromEnd = 0;
      let startName = 'edge start';
      let endName = 'edge end';
      let locName = `Edge ${t.edge} Finger Tab`;

      if (outlinePts.length > t.edge) {
        const pA = outlinePts[t.edge];
        const pB = outlinePts[(t.edge + 1) % outlinePts.length];
        const edx = pB[0] - pA[0], edy = pB[1] - pA[1];
        const elen = Math.hypot(edx, edy) || 1;
        const u = [edx / elen, edy / elen];
        let nrm = [u[1], -u[0]];
        const eMid = [(pA[0] + pB[0]) / 2, (pA[1] + pB[1]) / 2];
        if ((eMid[0] - cx) * nrm[0] + (eMid[1] - cy) * nrm[1] < 0) {
          nrm = [-nrm[0], -nrm[1]];
        }
        isSlant = Math.abs(edx) > 0.5 && Math.abs(edy) > 0.5;
        const s = (t.offset || 0) - (t.width || 0) / 2;
        const e = (t.offset || 0) + (t.width || 0) / 2;
        distFromEnd = Math.round(Math.max(0, elen - e) * 10) / 10;

        pRoot1 = [Math.round((pA[0] + u[0] * s) * 10) / 10, Math.round((pA[1] + u[1] * s) * 10) / 10];
        pRoot2 = [Math.round((pA[0] + u[0] * e) * 10) / 10, Math.round((pA[1] + u[1] * e) * 10) / 10];
        pTip1 = [Math.round((pRoot1[0] + nrm[0] * (t.depth || 0)) * 10) / 10, Math.round((pRoot1[1] + nrm[1] * (t.depth || 0)) * 10) / 10];
        pTip2 = [Math.round((pRoot2[0] + nrm[0] * (t.depth || 0)) * 10) / 10, Math.round((pRoot2[1] + nrm[1] * (t.depth || 0)) * 10) / 10];

        if (isSlant && apexCorner && apexCorner.dir === 'top') {
          locName = eMid[0] > (apexCorner.pt[0] - 1.0) ? 'Right Roof Slant Joint' : 'Left Roof Slant Joint';
          startName = locName.includes('Right') ? 'right shoulder' : 'left shoulder';
          endName = 'apex peak';
        }
      }

      tabs.push({
        id: t.id || `tab-${idx + 1}`,
        name: t.name || locName,
        edge: t.edge,
        locName,
        width: Math.round((t.width || 0) * 10) / 10,
        depth: Math.round((t.depth || 0) * 10) / 10,
        distFromStart,
        distFromEnd,
        startName,
        endName,
        mid: pTip1 && pTip2 ? [Math.round(((pTip1[0] + pTip2[0]) / 2) * 10) / 10, Math.round(((pTip1[1] + pTip2[1]) / 2) * 10) / 10] : null,
        pRoot1,
        pTip1,
        pTip2,
        pRoot2,
        isSlant
      });
    });
  }

  const angledEdges = edges.filter((e) => e.type === 'angled' && e.length > thickness * 2 + 1);

  // 4. Construct unified, non-overlapping dimension checklist items with thorough manual cutting instructions
  const dimensions = [];
  let stepCounter = 1;

  // Step 1: Blank stock size
  dimensions.push({
    id: 'outer-size',
    step: stepCounter++,
    category: 'outer',
    name: 'Cut Blank Stock Sheet',
    value: `${fmt(bbox.width)} × ${fmt(bbox.height)} mm`,
    color: '#e2e8f0',
    colorName: 'white',
    badgeClass: 'cad-badge-white',
    dotClass: 'cad-dot-white',
    action: 'Cut',
    actionIcon: '✂️',
    tool: 'Steel ruler & utility knife',
    desc: `Cut rectangular blank ${fmt(bbox.width)} × ${fmt(bbox.height)} mm from ${thickness} mm sheet`,
    guide: `Using a steel ruler and utility knife, cut a clean rectangular blank measuring exactly ${fmt(bbox.width)} mm wide by ${fmt(bbox.height)} mm high from your ${thickness} mm sheet. Check squareness across diagonals before scribing internal features.`
  });

  // Steps 1b: Edge Finger Tabs & Slant Joints Checklist & Walkthrough steps
  tabs.forEach((t) => {
    const wCm = (t.width / 10).toFixed(1);
    const dCm = (t.depth / 10).toFixed(1);
    const startCm = (t.distFromStart / 10).toFixed(1);
    const endCm = (t.distFromEnd / 10).toFixed(1);
    const isSlant = t.isSlant;

    dimensions.push({
      id: `tab-${t.id}`,
      step: stepCounter++,
      category: 'outer',
      name: isSlant ? `Scribe & Cut Slant Roof Joint (${esc(t.locName)})` : `Scribe & Cut Edge Joint Tab (${esc(t.locName)})`,
      value: `W: ${fmt(t.width)} mm (${wCm} cm) × D: ${fmt(t.depth)} mm · Scribe ${fmt(t.distFromStart)} mm (${startCm} cm)`,
      color: '#38bdf8',
      colorName: 'cyan',
      badgeClass: 'cad-badge-cyan',
      dotClass: 'cad-dot-cyan',
      action: 'Cut',
      actionIcon: '🧩',
      tool: 'Steel ruler & sharp craft knife',
      desc: `Joint Width: ${fmt(t.width)} mm (${wCm} cm) · Step Depth: ${fmt(t.depth)} mm · Start: ${fmt(t.distFromStart)} mm (${startCm} cm) from ${t.startName}`,
      guide: isSlant
        ? `1. On the slanted roof edge, measure ${fmt(t.distFromStart)} mm (${startCm} cm) along the slope from the ${t.startName} to locate the joint start.\n2. Cut 90° strictly perpendicular outward by ${fmt(t.depth)} mm (joint step depth).\n3. Cut parallel to the roof slope for ${fmt(t.width)} mm (${wCm} cm) (joint width).\n4. Cut 90° strictly perpendicular inward by ${fmt(t.depth)} mm back to the slope baseline. (${fmt(t.distFromEnd)} mm / ${endCm} cm remains to ${t.endName}).`
        : `1. Measure ${fmt(t.distFromStart)} mm (${startCm} cm) along the edge from ${t.startName} to mark the tab start.\n2. Cut 90° perpendicular outward by ${fmt(t.depth)} mm.\n3. Cut parallel along edge for ${fmt(t.width)} mm (${wCm} cm).\n4. Cut 90° perpendicular inward by ${fmt(t.depth)} mm back to baseline.`
    });
  });

  // Steps 2 & 3: Horizontal Gaps (X)
  if (features.length) {
    const minLeft = Math.round((Math.min(...features.map((f) => f.bounds.minX)) - bbox.x0) * 10) / 10;
    const minRight = Math.round((bbox.x1 - Math.max(...features.map((f) => f.bounds.maxX))) * 10) / 10;

    if (Math.abs(minLeft - minRight) < 0.2) {
      dimensions.push({
        id: 'left-gap',
        step: stepCounter++,
        category: 'gaps',
        name: 'Scribe Left & Right Slot Datums',
        value: `${fmt(minLeft)} mm`,
        color: '#38bdf8',
        colorName: 'cyan',
        badgeClass: 'cad-badge-cyan',
        dotClass: 'cad-dot-cyan',
        action: 'Mark',
        actionIcon: '✏️',
        tool: 'Vernier caliper or steel ruler',
        desc: `Symmetric margin: measure ${fmt(minLeft)} mm from left & right edges`,
        guide: `Measure exactly ${fmt(minLeft)} mm inward from the left straight edge and right straight edge. Scribe faint vertical pencil datum lines across the blank. The slot ends align exactly on these lines.`
      });
    } else {
      dimensions.push({
        id: 'left-gap',
        step: stepCounter++,
        category: 'gaps',
        name: 'Scribe Left Slot Datum',
        value: `${fmt(minLeft)} mm`,
        color: '#38bdf8',
        colorName: 'cyan',
        badgeClass: 'cad-badge-cyan',
        dotClass: 'cad-dot-cyan',
        action: 'Mark',
        actionIcon: '✏️',
        tool: 'Vernier caliper or steel ruler',
        desc: `Measure ${fmt(minLeft)} mm from left edge to locate slots`,
        guide: `Measure exactly ${fmt(minLeft)} mm inward from the left straight edge. Scribe a vertical pencil line. The left ends of the slots start on this datum.`
      });
      dimensions.push({
        id: 'right-gap',
        step: stepCounter++,
        category: 'gaps',
        name: 'Scribe Right Slot Datum',
        value: `${fmt(minRight)} mm`,
        color: '#38bdf8',
        colorName: 'cyan',
        badgeClass: 'cad-badge-cyan',
        dotClass: 'cad-dot-cyan',
        action: 'Mark',
        actionIcon: '✏️',
        tool: 'Vernier caliper or steel ruler',
        desc: `Measure ${fmt(minRight)} mm from right edge to terminate slots`,
        guide: `Measure exactly ${fmt(minRight)} mm inward from the right straight edge. Scribe a vertical pencil line. The right ends of the slots terminate on this datum.`
      });
    }

    // Vertical Gaps (Y)
    const minTop = Math.round((bbox.y1 - Math.max(...features.map((f) => f.bounds.maxY))) * 10) / 10;
    const minBot = Math.round((Math.min(...features.map((f) => f.bounds.minY)) - bbox.y0) * 10) / 10;

    dimensions.push({
      id: 'bottom-gap',
      step: stepCounter++,
      category: 'gaps',
      name: 'Scribe Lower Slot Baseline',
      value: `${fmt(minBot)} mm`,
      color: '#facc15',
      colorName: 'amber',
      badgeClass: 'cad-badge-amber',
      dotClass: 'cad-dot-amber',
      action: 'Mark',
      actionIcon: '✏️',
      tool: 'Steel ruler & fine pencil',
      desc: `Measure ${fmt(minBot)} mm up from bottom edge for lower slots`,
      guide: `Measure ${fmt(minBot)} mm up from the bottom baseline edge on both sides. Scribe a horizontal line across. The bottom edge of the lower slot row sits on this line.`
    });

    // Check for vertical spacing between rows
    let rowSpacing = null;
    for (let i = 0; i < features.length; i++) {
      for (let j = 0; j < features.length; j++) {
        if (i === j) continue;
        const f1 = features[i], f2 = features[j];
        if (f2.bounds.minY >= f1.bounds.maxY - 0.1) {
          const vGap = f2.bounds.minY - f1.bounds.maxY;
          if (vGap > 1.0 && (rowSpacing === null || vGap < rowSpacing)) {
            rowSpacing = Math.round(vGap * 10) / 10;
          }
        }
      }
    }

    const hSpacings = features.map((f) => f.spacingToNext).filter((v) => v !== null);
    if (rowSpacing !== null) {
      dimensions.push({
        id: 'inner-spacing',
        step: stepCounter++,
        category: 'gaps',
        name: 'Measure Spacing to Upper Slots',
        value: `${fmt(rowSpacing)} mm`,
        color: '#34d399',
        colorName: 'emerald',
        badgeClass: 'cad-badge-emerald',
        dotClass: 'cad-dot-emerald',
        action: 'Mark',
        actionIcon: '✏️',
        tool: 'Steel ruler & fine pencil',
        desc: `Solid bridge between slot rows: ${fmt(rowSpacing)} mm`,
        guide: `Measure ${fmt(rowSpacing)} mm upward from the top of the lower slots (solid bridge). Scribe a horizontal line to locate the lower edge of the upper slot row.`
      });
    } else if (hSpacings.length) {
      dimensions.push({
        id: 'inner-spacing',
        step: stepCounter++,
        category: 'gaps',
        name: 'Check Inter-Slot Web Margin',
        value: `${fmt(hSpacings[0])} mm`,
        color: '#34d399',
        colorName: 'emerald',
        badgeClass: 'cad-badge-emerald',
        dotClass: 'cad-dot-emerald',
        action: 'Check',
        actionIcon: '🔍',
        tool: 'Vernier caliper',
        desc: `Solid wood web between cutouts: ${fmt(hSpacings[0])} mm`,
        guide: `Ensure a solid wood web of ${fmt(hSpacings[0])} mm remains between adjacent cutouts so the material maintains structural integrity and does not split.`
      });
    }

    dimensions.push({
      id: 'top-gap',
      step: stepCounter++,
      category: 'gaps',
      name: 'Verify Top / Roof Clearance',
      value: `${fmt(minTop)} mm`,
      color: '#facc15',
      colorName: 'amber',
      badgeClass: 'cad-badge-amber',
      dotClass: 'cad-dot-amber',
      action: 'Check',
      actionIcon: '🔍',
      tool: 'Steel ruler',
      desc: `Clearance to top edge: ${fmt(minTop)} mm solid wood`,
      guide: `Confirm ${fmt(minTop)} mm of solid wood remains above the upper slot to the top perimeter/peak. This provides strong interlocking support for roof or ceiling panels.`
    });

    // Slot Cut-out Size
    const slotSizes = [...new Set(features.map((f) => {
      if (f.shape === 'circle') return `Ø${fmt(f.diameter)} mm`;
      return `${fmt(Math.max(f.width, f.height))} × ${fmt(Math.min(f.width, f.height))} mm`;
    }))];

    dimensions.push({
      id: 'slot-size',
      step: stepCounter++,
      category: 'slots',
      name: 'Drill Pilot & Cut Internal Slots',
      value: slotSizes.join(', '),
      color: '#fb7185',
      colorName: 'rose',
      badgeClass: 'cad-badge-rose',
      dotClass: 'cad-dot-rose',
      action: 'Cut',
      actionIcon: '🪚',
      tool: '0.8-1.0mm drill & sharp craft blade',
      desc: `Cut ${features.length} slot(s) measuring ${slotSizes.join(', ')}`,
      guide: `For each of the ${features.length} slot(s) (${slotSizes.join(', ')}): drill small 0.8–1.0 mm pilot holes just inside opposite corners. Use a fresh craft blade held at 90° (strictly perpendicular) to cut along the scribed datum lines.`
    });
  }

  // Apex and Slant Geometry Cuts (in mm & cm)
  if (apexCorner) {
    const isTop = apexCorner.dir === 'top';
    const runCm = (apexCorner.run / 10).toFixed(1);
    const riseCm = (apexCorner.rise / 10).toFixed(1);
    const cutCm = (apexCorner.cutLength / 10).toFixed(1);
    const pitchAngle = apexCorner.pitch || (apexCorner.run > 0 ? Math.round(Math.atan2(apexCorner.rise, apexCorner.run) * 1800 / Math.PI) / 10 : 45.0);

    dimensions.push({
      id: 'apex-corner',
      step: stepCounter++,
      category: 'outer',
      name: isTop ? 'Layout & Cut Roof Apex Pitch' : 'Shape Bow Apex Point',
      value: `${isTop ? 'Apex' : 'Bow'} ∠ ${fmt(apexCorner.angle)}°${apexCorner.pitch ? ` (Pitch: ${fmt(apexCorner.pitch)}°)` : ''}`,
      color: '#f59e0b',
      colorName: 'amber',
      badgeClass: 'cad-badge-amber',
      dotClass: 'cad-dot-amber',
      action: 'Angle',
      actionIcon: '📐',
      tool: 'Steel ruler & bevel gauge',
      desc: isTop
        ? `Peak angle: ${fmt(apexCorner.angle)}° · Pitch angle: ${fmt(pitchAngle)}° · Centerline X = ${fmt(bbox.width / 2)} mm (${(bbox.width / 20).toFixed(1)} cm)`
        : `Bow angle: ${fmt(apexCorner.angle)}° · Tip at X = ${fmt(apexCorner.pt[0] - bbox.x0)} mm (${((apexCorner.pt[0] - bbox.x0)/10).toFixed(1)} cm), Y = ${fmt(apexCorner.pt[1] - bbox.y0)} mm`,
      guide: isTop
        ? `Mark top centerline at X = ${fmt(bbox.width / 2)} mm (${(bbox.width / 20).toFixed(1)} cm) on the top edge (Y = ${fmt(bbox.height)} mm). ${apexCorner.shoulderY !== null ? `Mark the gable shoulders at Y = ${fmt(apexCorner.shoulderY)} mm (${(apexCorner.shoulderY/10).toFixed(1)} cm) along left and right edges. ` : ''}Connect shoulders to the peak point (included apex angle: ${fmt(apexCorner.angle)}°, pitch: ${fmt(pitchAngle)}°) and cut along the angled slope lines.`
        : `Mark the pointed bow tip at X = ${fmt(apexCorner.pt[0] - bbox.x0)} mm (${((apexCorner.pt[0] - bbox.x0)/10).toFixed(1)} cm) and Y = ${fmt(apexCorner.pt[1] - bbox.y0)} mm. Scribe straight angled cut lines from the flat hull edges to the bow tip (included bow angle: ${fmt(apexCorner.angle)}°) and slice cleanly with a craft knife.`
    });

    dimensions.push({
      id: 'slant-dimension',
      step: stepCounter++,
      category: 'outer',
      name: isTop ? 'Slant Width, Height & Cut Length' : 'Bow Slant Dimensions',
      value: `W: ${fmt(apexCorner.run)} mm (${runCm} cm) · H: ${fmt(apexCorner.rise)} mm (${riseCm} cm) · Cut: ${fmt(apexCorner.cutLength)} mm (${cutCm} cm)`,
      color: '#f59e0b',
      colorName: 'amber',
      badgeClass: 'cad-badge-amber',
      dotClass: 'cad-dot-amber',
      action: 'Measure',
      actionIcon: '📐',
      tool: 'Steel ruler & fine mechanical pencil',
      desc: `Slant Width (Run): ${fmt(apexCorner.run)} mm (${runCm} cm) | Slant Height (Rise): ${fmt(apexCorner.rise)} mm (${riseCm} cm) | Diagonal Cut: ${fmt(apexCorner.cutLength)} mm (${cutCm} cm) | Pitch: ${fmt(pitchAngle)}°`,
      guide: isTop
        ? `1. Scribe peak centerline at Slant Width = ${fmt(apexCorner.run)} mm (${runCm} cm) inward from left & right straight edges.\n2. From gable shoulder line at Y = ${fmt(apexCorner.shoulderY)} mm (${(apexCorner.shoulderY/10).toFixed(1)} cm), measure vertical Slant Height = ${fmt(apexCorner.rise)} mm (${riseCm} cm) up to peak.\n3. Scribe a straight line between shoulder and peak (diagonal cut length: ${fmt(apexCorner.cutLength)} mm / ${cutCm} cm, angle: ${fmt(pitchAngle)}°) and cut with ruler & craft blade.`
        : `1. Mark the bow taper start at Slant Width = ${fmt(apexCorner.run)} mm (${runCm} cm) back from the tip.\n2. Measure half-beam Slant Height = ${fmt(apexCorner.rise)} mm (${riseCm} cm) from centerline to hull sides.\n3. Scribe diagonal cut lines (cut length: ${fmt(apexCorner.cutLength)} mm / ${cutCm} cm) and cut.`
    });
  }

  // Find remaining angled edges not touching apex
  const nonApexAngled = angledEdges.filter((e) => {
    if (!apexCorner) return true;
    const isAtApex = (Math.hypot(e.pA[0] - apexCorner.pt[0], e.pA[1] - apexCorner.pt[1]) < 1.0) ||
                     (Math.hypot(e.pB[0] - apexCorner.pt[0], e.pB[1] - apexCorner.pt[1]) < 1.0);
    return !isAtApex;
  });

  if (nonApexAngled.length > 0 && nonApexAngled.length <= 4) {
    const e = nonApexAngled[0];
    const isSymmetric = nonApexAngled.length >= 2 && Math.abs(nonApexAngled[0].run - nonApexAngled[1].run) < 1.0;
    const eRunCm = (e.run / 10).toFixed(1);
    const eRiseCm = (e.rise / 10).toFixed(1);
    const eLenCm = (e.length / 10).toFixed(1);
    dimensions.push({
      id: 'corner-chamfers',
      step: stepCounter++,
      category: 'outer',
      name: isSymmetric ? 'Layout & Cut Symmetric Slant Tapers' : 'Cut Angled Slant Chamfers',
      value: `W: ${fmt(e.run)} mm (${eRunCm} cm) × H: ${fmt(e.rise)} mm (${eRiseCm} cm) · Cut: ${fmt(e.length)} mm (${eLenCm} cm)`,
      color: '#f59e0b',
      colorName: 'amber',
      badgeClass: 'cad-badge-amber',
      dotClass: 'cad-dot-amber',
      action: 'Angle',
      actionIcon: '📐',
      tool: 'Steel ruler & craft knife',
      desc: `Slant Width (Run): ${fmt(e.run)} mm (${eRunCm} cm) · Slant Height (Rise): ${fmt(e.rise)} mm (${eRiseCm} cm) · Cut: ${fmt(e.length)} mm (${eLenCm} cm) (angle ${fmt(e.angleDeg)}°)`,
      guide: `From the corners, measure and mark Slant Width = ${fmt(e.run)} mm (${eRunCm} cm) horizontally and Slant Height = ${fmt(e.rise)} mm (${eRiseCm} cm) vertically. Scribe diagonal cut lines (angle: ${fmt(e.angleDeg)}°, cut length: ${fmt(e.length)} mm / ${eLenCm} cm) and cut away waste.`
    });
  }

  // 5. Audit all dimensions for non-integer floating-point values
  const floatIssues = [];
  dimensions.forEach((d) => {
    let isFloat = false;
    let rawVal = null;
    if (d.id === 'outer-size') {
      if (!isCleanInteger(bbox.width)) { isFloat = true; rawVal = bbox.width; }
      if (!isCleanInteger(bbox.height)) { isFloat = true; rawVal = bbox.height; }
    } else if (d.id === 'left-gap') {
      const minLeft = Math.round((Math.min(...features.map((f) => f.bounds.minX)) - bbox.x0) * 10) / 10;
      if (!isCleanInteger(minLeft)) { isFloat = true; rawVal = minLeft; }
    } else if (d.id === 'right-gap') {
      const minRight = Math.round((bbox.x1 - Math.max(...features.map((f) => f.bounds.maxX))) * 10) / 10;
      if (!isCleanInteger(minRight)) { isFloat = true; rawVal = minRight; }
    } else if (d.id === 'bottom-gap') {
      const minBot = Math.round((Math.min(...features.map((f) => f.bounds.minY)) - bbox.y0) * 10) / 10;
      if (!isCleanInteger(minBot)) { isFloat = true; rawVal = minBot; }
    } else if (d.id === 'top-gap') {
      const minTop = Math.round((bbox.y1 - Math.max(...features.map((f) => f.bounds.maxY))) * 10) / 10;
      if (!isCleanInteger(minTop)) { isFloat = true; rawVal = minTop; }
    } else if (d.id === 'inner-spacing') {
      const val = parseFloat(d.value);
      if (!isNaN(val) && !isCleanInteger(val)) { isFloat = true; rawVal = val; }
    } else if (d.id === 'slot-size') {
      features.forEach((f) => {
        if (!isCleanInteger(f.width)) { isFloat = true; rawVal = f.width; }
        if (!isCleanInteger(f.height)) { isFloat = true; rawVal = f.height; }
      });
    }

    if (isFloat) {
      d.isFloat = true;
      d.rawVal = rawVal;
      d.badgeClass = 'cad-badge-warn';
      d.dotClass = 'cad-dot-amber';
      d.desc += ` ⚠️ Non-integer float (${fmt(rawVal)} mm)`;
      d.guide += ` ⚠️ Non-integer float (${fmt(rawVal)} mm) — must be whole integer millimetres.`;
      floatIssues.push(d);
    }
  });

  // 6. Compute exact Cartesian graph plotting coordinates relative to bottom-left origin (0, 0)
  const graphPoints = pts.map((p, i) => {
    const xMm = Math.round((p[0] - bbox.x0) * 10) / 10;
    const yMm = Math.round((p[1] - bbox.y0) * 10) / 10;
    const xCm = Math.round(xMm) / 10;
    const yCm = Math.round(yMm) / 10;
    let desc = `Corner #${i + 1}`;
    const matchingTab = tabs.find((t) =>
      (t.pRoot1 && distPts(p, t.pRoot1) < 0.2) ||
      (t.pTip1 && distPts(p, t.pTip1) < 0.2) ||
      (t.pTip2 && distPts(p, t.pTip2) < 0.2) ||
      (t.pRoot2 && distPts(p, t.pRoot2) < 0.2)
    );
    if (matchingTab) {
      const sName = matchingTab.startName || 'corner';
      const eName = matchingTab.endName || 'corner';
      if (distPts(p, matchingTab.pRoot1) < 0.2) {
        desc = `Joint scribe root (${matchingTab.locName || matchingTab.id}) · Mark at ${fmt(matchingTab.distFromStart)} mm (${(matchingTab.distFromStart/10).toFixed(1)} cm) from ${sName} — Start 90° cut`;
      } else if (distPts(p, matchingTab.pTip1) < 0.2) {
        desc = `Joint step corner (+${fmt(matchingTab.depth)} mm perpendicular outward cut)`;
      } else if (distPts(p, matchingTab.pTip2) < 0.2) {
        desc = `Joint outer corner (tab cut width: ${fmt(matchingTab.width)} mm / ${(matchingTab.width/10).toFixed(1)} cm)`;
      } else if (distPts(p, matchingTab.pRoot2) < 0.2) {
        desc = `Joint return root back to slope (end 90° cut · ${fmt(matchingTab.distFromEnd)} mm to ${eName})`;
      }
    } else if (i === 0) desc = `Origin datum (bottom-left corner)`;
    else if (apexCorner && Math.hypot(p[0] - apexCorner.pt[0], p[1] - apexCorner.pt[1]) < 0.5) {
      desc = `${apexCorner.dir === 'top' ? 'Roof apex peak' : 'Bow tip'}`;
    } else if (Math.abs(yMm - bbox.height) < 0.2) desc = `Top perimeter edge`;
    else if (Math.abs(yMm) < 0.2) desc = `Bottom baseline edge`;
    else if (Math.abs(xMm) < 0.2) desc = `Left wall edge`;
    else if (Math.abs(xMm - bbox.width) < 0.2) desc = `Right wall edge`;
    return {
      index: i + 1,
      pt: p,
      xMm, yMm, xCm, yCm,
      desc
    };
  });

  const slotGraphPoints = features.map((f, i) => {
    const minX = Math.round((f.bounds.minX - bbox.x0) * 10) / 10;
    const maxX = Math.round((f.bounds.maxX - bbox.x0) * 10) / 10;
    const minY = Math.round((f.bounds.minY - bbox.y0) * 10) / 10;
    const maxY = Math.round((f.bounds.maxY - bbox.y0) * 10) / 10;
    const cx = Math.round((f.center[0] - bbox.x0) * 10) / 10;
    const cy = Math.round((f.center[1] - bbox.y0) * 10) / 10;
    return {
      id: f.id.replace('slot-', ''),
      order: i + 1,
      minX, maxX, minY, maxY,
      cx, cy,
      width: f.width,
      height: f.height,
      size: f.shape === 'circle' ? `Ø${fmt(f.diameter)} mm` : `${fmt(f.width)} × ${fmt(f.height)} mm`,
      desc: `X: ${fmt(minX)}–${fmt(maxX)} mm · Y: ${fmt(minY)}–${fmt(maxY)} mm`
    };
  });

  const slant = apexCorner ? {
    runMm: apexCorner.run,
    runCm: Number((apexCorner.run / 10).toFixed(1)),
    riseMm: apexCorner.rise,
    riseCm: Number((apexCorner.rise / 10).toFixed(1)),
    cutLengthMm: apexCorner.cutLength,
    cutLengthCm: Number((apexCorner.cutLength / 10).toFixed(1)),
    pitchAngle: apexCorner.pitch || (apexCorner.run > 0 ? Math.round(Math.atan2(apexCorner.rise, apexCorner.run) * 1800 / Math.PI) / 10 : 45.0),
    shoulderY: apexCorner.shoulderY !== undefined ? apexCorner.shoulderY : null,
    dir: apexCorner.dir,
    isApex: true
  } : (angledEdges.length > 0 ? {
    runMm: angledEdges[0].run,
    runCm: Number((angledEdges[0].run / 10).toFixed(1)),
    riseMm: angledEdges[0].rise,
    riseCm: Number((angledEdges[0].rise / 10).toFixed(1)),
    cutLengthMm: angledEdges[0].length,
    cutLengthCm: Number((angledEdges[0].length / 10).toFixed(1)),
    pitchAngle: angledEdges[0].angleDeg,
    shoulderY: null,
    dir: 'corner',
    isApex: false
  } : null);

  const maxDim = Math.max(bbox.width, bbox.height, 20);
  const SCALE = Math.max(2.0, Math.min(10, 260 / maxDim));
  const W = bbox.width * SCALE;
  const H = bbox.height * SCALE;

  const snapPoints = [];
  pts.forEach((p, idx) => {
    snapPoints.push({
      x: p[0],
      y: p[1],
      xMm: Math.round((p[0] - bbox.x0) * 10) / 10,
      yMm: Math.round((p[1] - bbox.y0) * 10) / 10,
      svgX: (p[0] - bbox.x0) * SCALE,
      svgY: (bbox.y1 - p[1]) * SCALE,
      label: `Corner #${idx + 1}`
    });
  });
  tabs.forEach((t) => {
    if (t.pRoot1) {
      snapPoints.push({
        x: t.pRoot1[0], y: t.pRoot1[1],
        xMm: Math.round((t.pRoot1[0] - bbox.x0) * 10) / 10,
        yMm: Math.round((t.pRoot1[1] - bbox.y0) * 10) / 10,
        svgX: (t.pRoot1[0] - bbox.x0) * SCALE,
        svgY: (bbox.y1 - t.pRoot1[1]) * SCALE,
        label: `Joint Root (${t.id})`
      });
    }
    if (t.pTip1) {
      snapPoints.push({
        x: t.pTip1[0], y: t.pTip1[1],
        xMm: Math.round((t.pTip1[0] - bbox.x0) * 10) / 10,
        yMm: Math.round((t.pTip1[1] - bbox.y0) * 10) / 10,
        svgX: (t.pTip1[0] - bbox.x0) * SCALE,
        svgY: (bbox.y1 - t.pTip1[1]) * SCALE,
        label: `Joint Step (+${t.depth}mm)`
      });
    }
    if (t.pTip2) {
      snapPoints.push({
        x: t.pTip2[0], y: t.pTip2[1],
        xMm: Math.round((t.pTip2[0] - bbox.x0) * 10) / 10,
        yMm: Math.round((t.pTip2[1] - bbox.y0) * 10) / 10,
        svgX: (t.pTip2[0] - bbox.x0) * SCALE,
        svgY: (bbox.y1 - t.pTip2[1]) * SCALE,
        label: `Joint Tip (${t.width}mm)`
      });
    }
    if (t.pRoot2) {
      snapPoints.push({
        x: t.pRoot2[0], y: t.pRoot2[1],
        xMm: Math.round((t.pRoot2[0] - bbox.x0) * 10) / 10,
        yMm: Math.round((t.pRoot2[1] - bbox.y0) * 10) / 10,
        svgX: (t.pRoot2[0] - bbox.x0) * SCALE,
        svgY: (bbox.y1 - t.pRoot2[1]) * SCALE,
        label: `Joint Return (${t.id})`
      });
    }
  });
  features.forEach((f) => {
    const minX = f.bounds.minX, maxX = f.bounds.maxX, minY = f.bounds.minY, maxY = f.bounds.maxY;
    const ptsF = [
      [minX, minY, 'Slot Corner'],
      [maxX, minY, 'Slot Corner'],
      [maxX, maxY, 'Slot Corner'],
      [minX, maxY, 'Slot Corner'],
      [f.center[0], f.center[1], 'Slot Center']
    ];
    ptsF.forEach(([px, py, desc]) => {
      snapPoints.push({
        x: px, y: py,
        xMm: Math.round((px - bbox.x0) * 10) / 10,
        yMm: Math.round((py - bbox.y0) * 10) / 10,
        svgX: (px - bbox.x0) * SCALE,
        svgY: (bbox.y1 - py) * SCALE,
        label: `${desc} (${f.id})`
      });
    });
  });

  return {
    bbox,
    edges,
    angledEdges,
    apexCorner,
    features,
    tabs,
    dimensions,
    graphPoints,
    slotGraphPoints,
    slant,
    SCALE,
    scale: SCALE,
    W,
    H,
    snapPoints,
    summary: {
      blankWidth: Math.round(bbox.width * 10) / 10,
      blankHeight: Math.round(bbox.height * 10) / 10,
      thickness,
      edgeCount: edges.length,
      angledCount: angledEdges.length,
      apexAngle: apexCorner ? apexCorner.angle : null,
      slant,
      minSolidMargin: features.length ? Math.min(...features.map((f) => f.minMargin)) : null,
      slotCount: features.filter((f) => f.kind === 'slot').length,
      outerCutOrder: features.length + 1,
      floatCount: floatIssues.length,
      floatIssues
    }
  };
}

/**
 * Renders the pixel-perfect, non-overlapping 2D Blueprint SVG.
 * Ensures clean visual hierarchy with dedicated dimension rails and zero clutter.
 */
export function renderDraftingSvg(c, options = {}) {
  const specs = computeDraftingSpecs(c);
  if (!specs) return '';

  const { bbox, edges, apexCorner, features, tabs, summary } = specs;
  const w = bbox.width;
  const h = bbox.height;
  if (w <= 0 || h <= 0) return '';

  // Adaptive scaling so drawings fit nicely
  const maxDim = Math.max(w, h, 20);
  const SCALE = Math.max(2.0, Math.min(10, 260 / maxDim));
  const W = w * SCALE;
  const H = h * SCALE;

  // Has top apex: if top apex exists, put cyan horizontal gap rail at the bottom so it NEVER collides with apex!
  const hasTopApex = Boolean(apexCorner && apexCorner.dir === 'top');

  // Dedicated rail offsets (measured in SVG units outside part)
  const leftPad = 120;
  const rightPad = 120;
  const topPad = 105;
  const botPad = hasTopApex ? 85 : 55;

  const vbX = -leftPad;
  const vbY = -topPad;
  const vbW = W + leftPad + rightPad;
  const vbH = H + topPad + botPad;

  // Coordinate transforms: CAD mm to SVG coords (SVG Y=0 is top of part, Y=H is bottom)
  const toX = (x) => (x - bbox.x0) * SCALE;
  const toY = (y) => (bbox.y1 - y) * SCALE;

  // 1. Precise Millimeter & Centimeter Graph Axis Rulers along Bottom (X) and Left (Y)
  let axisRulers = `<g id="axis-rulers" font-family="'JetBrains Mono', monospace">`;
  // X axis at bottom baseline (Y = H)
  axisRulers += `<line x1="0" y1="${H.toFixed(1)}" x2="${W.toFixed(1)}" y2="${H.toFixed(1)}" stroke="#64748b" stroke-width="1.3" />`;
  for (let mm = 0; mm <= w; mm += 1) {
    const x = mm * SCALE;
    if (mm % 10 === 0) {
      axisRulers += `<line x1="${x.toFixed(1)}" y1="${H.toFixed(1)}" x2="${x.toFixed(1)}" y2="${(H + 7).toFixed(1)}" stroke="#38bdf8" stroke-width="1.3" />`;
      const numLabel = mm % 10 === 0 && mm > 0 ? `${mm / 10}cm` : `${mm}`;
      axisRulers += `<text x="${x.toFixed(1)}" y="${(H + 18).toFixed(1)}" text-anchor="middle" fill="#38bdf8" font-size="9" font-weight="700">${numLabel}</text>`;
    } else if (mm % 5 === 0) {
      axisRulers += `<line x1="${x.toFixed(1)}" y1="${H.toFixed(1)}" x2="${x.toFixed(1)}" y2="${(H + 5).toFixed(1)}" stroke="#94a3b8" stroke-width="0.9" />`;
    } else if (SCALE >= 3.0) {
      axisRulers += `<line x1="${x.toFixed(1)}" y1="${H.toFixed(1)}" x2="${x.toFixed(1)}" y2="${(H + 3).toFixed(1)}" stroke="#475569" stroke-width="0.6" />`;
    }
  }

  // Y axis at left baseline (X = 0, going up from Y = H to Y = 0)
  axisRulers += `<line x1="0" y1="${H.toFixed(1)}" x2="0" y2="0" stroke="#64748b" stroke-width="1.3" />`;
  for (let mm = 0; mm <= h; mm += 1) {
    const y = H - mm * SCALE;
    if (mm % 10 === 0) {
      axisRulers += `<line x1="0" y1="${y.toFixed(1)}" x2="-7" y2="${y.toFixed(1)}" stroke="#38bdf8" stroke-width="1.3" />`;
      const numLabel = mm % 10 === 0 && mm > 0 ? `${mm / 10}cm` : `${mm}`;
      axisRulers += `<text x="-9" y="${(y + 3).toFixed(1)}" text-anchor="end" fill="#38bdf8" font-size="9" font-weight="700">${numLabel}</text>`;
    } else if (mm % 5 === 0) {
      axisRulers += `<line x1="0" y1="${y.toFixed(1)}" x2="-5" y2="${y.toFixed(1)}" stroke="#94a3b8" stroke-width="0.9" />`;
    } else if (SCALE >= 3.0) {
      axisRulers += `<line x1="0" y1="${y.toFixed(1)}" x2="-3" y2="${y.toFixed(1)}" stroke="#475569" stroke-width="0.6" />`;
    }
  }
  axisRulers += `</g>`;

  // 1b. Vertex Coordinate Plot Pins Layer (for Manual Graph Paper Plotting)
  let drawPointsHtml = `<g id="draw-points-layer" style="display:none;">`;
  specs.graphPoints.forEach((gp) => {
    const px = toX(gp.pt[0]);
    const py = toY(gp.pt[1]);
    const label = `(${fmt(gp.xMm)}, ${fmt(gp.yMm)})`;
    const pillW = Math.max(48, label.length * 6.5 + 14);
    const offY = py < H / 2 ? -14 : 16;
    drawPointsHtml += `
      <g class="vertex-pin" data-vertex="${gp.index}" transform="translate(${px.toFixed(1)}, ${py.toFixed(1)})">
        <circle cx="0" cy="0" r="4.5" fill="#38bdf8" stroke="#0a0e14" stroke-width="1.8" />
        <circle cx="0" cy="0" r="1.5" fill="#ffffff" />
        <rect x="${(-pillW / 2).toFixed(1)}" y="${(offY - 10).toFixed(1)}" width="${pillW.toFixed(1)}" height="16" rx="4" fill="#0f172a" stroke="#38bdf8" stroke-width="1.1" opacity="0.95" />
        <text x="0" y="${(offY + 2).toFixed(1)}" text-anchor="middle" fill="#38bdf8" font-family="'JetBrains Mono', monospace" font-size="9" font-weight="700">${label}</text>
      </g>
    `;
  });

  specs.slotGraphPoints.forEach((sp) => {
    const fx = toX(sp.cx + bbox.x0);
    const fy = toY(sp.cy + bbox.y0);
    const label = `${sp.id}: (${fmt(sp.cx)}, ${fmt(sp.cy)})`;
    const pillW = Math.max(52, label.length * 6.2 + 14);
    drawPointsHtml += `
      <g class="slot-pin" data-slot="${sp.id}" transform="translate(${fx.toFixed(1)}, ${fy.toFixed(1)})">
        <circle cx="0" cy="0" r="3.5" fill="#fb7185" stroke="#0a0e14" stroke-width="1.4" />
        <rect x="${(-pillW / 2).toFixed(1)}" y="7" width="${pillW.toFixed(1)}" height="15" rx="4" fill="#1e1017" stroke="#fb7185" stroke-width="1" opacity="0.95" />
        <text x="0" y="18" text-anchor="middle" fill="#fb7185" font-family="'JetBrains Mono', monospace" font-size="8.5" font-weight="700">${label}</text>
      </g>
    `;
  });
  drawPointsHtml += `</g>`;

  // 2. Wooden Panel Body + Outer Cut Path (Coral Red laser cut line)
  const pts = c.cut_outline || [];
  const panelPath = pts.length > 2
    ? 'M' + pts.map((p) => `${toX(p[0]).toFixed(1)},${toY(p[1]).toFixed(1)}`).join('L') + 'Z'
    : `M0,0 L${W.toFixed(1)},0 L${W.toFixed(1)},${H.toFixed(1)} L0,${H.toFixed(1)} Z`;

  let geometryHtml = `
    <g id="panel-geometry">
      <path d="${panelPath}" fill="#d9b589" fill-opacity="0.92" stroke="#ef4444" stroke-width="2.2" />
  `;

  // Render Cut-outs
  features.forEach((f) => {
    if (f.shape === 'circle') {
      const cx = toX(f.center[0]);
      const cy = toY(f.center[1]);
      const r = (f.diameter / 2) * SCALE;
      geometryHtml += `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${r.toFixed(1)}" fill="#0a0e14" stroke="#38bdf8" stroke-width="1.8" />`;
    } else if (f.poly && f.poly.length > 2) {
      const pD = 'M' + f.poly.map((p) => `${toX(p[0]).toFixed(1)},${toY(p[1]).toFixed(1)}`).join('L') + 'Z';
      geometryHtml += `<path d="${pD}" fill="#0a0e14" stroke="#38bdf8" stroke-width="1.8" />`;
    } else {
      const sx = toX(f.bounds.minX);
      const sy = toY(f.bounds.maxY);
      const sw = (f.bounds.maxX - f.bounds.minX) * SCALE;
      const sh = (f.bounds.maxY - f.bounds.minY) * SCALE;
      geometryHtml += `<rect x="${sx.toFixed(1)}" y="${sy.toFixed(1)}" width="${sw.toFixed(1)}" height="${sh.toFixed(1)}" rx="1.2" fill="#0a0e14" stroke="#38bdf8" stroke-width="1.8" />`;
    }
  });
  geometryHtml += `</g>`;

  // 3. Recommended Cut Order Badges (toggleable)
  let cutOrderHtml = `<g id="cut-order-layer" style="display:none;">`;
  features.forEach((f, idx) => {
    const cx = toX(f.center[0]);
    const cy = toY(f.center[1]);
    cutOrderHtml += `
      <circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="11" fill="#0f172a" stroke="#f59e0b" stroke-width="2" />
      <text x="${cx.toFixed(1)}" y="${(cy + 4).toFixed(1)}" text-anchor="middle" fill="#fbbf24" font-family="'JetBrains Mono', monospace" font-size="11" font-weight="700">${idx + 1}</text>
    `;
  });
  cutOrderHtml += `
    <circle cx="${W.toFixed(1)}" cy="0" r="11" fill="#0f172a" stroke="#ef4444" stroke-width="2" />
    <text x="${W.toFixed(1)}" y="4" text-anchor="middle" fill="#f87171" font-family="'JetBrains Mono', monospace" font-size="11" font-weight="700">${summary.outerCutOrder}</text>
  </g>`;

  // 4. Color-Coded Dimension Groups on Dedicated, Non-Colliding Rails
  let dimensionsHtml = '';

  // 4a. OUTER SIZE (White):
  // Top Outer Width Rail: Y = -68
  const topOuterRailY = -68;
  // Right Outer Height Rail: X = W + 60
  const rightOuterRailX = W + 60;

  dimensionsHtml += `
    <g class="dim-group" data-dim-id="outer-size" data-category="outer" style="color:#e2e8f0">
      <!-- Top width line -->
      <line x1="0" y1="-6" x2="0" y2="${(topOuterRailY - 8).toFixed(1)}" stroke="#64748b" stroke-width="1" stroke-dasharray="3 3" />
      <line x1="${W.toFixed(1)}" y1="-6" x2="${W.toFixed(1)}" y2="${(topOuterRailY - 8).toFixed(1)}" stroke="#64748b" stroke-width="1" stroke-dasharray="3 3" />
      <line x1="3" y1="${topOuterRailY.toFixed(1)}" x2="${(W - 3).toFixed(1)}" y2="${topOuterRailY.toFixed(1)}" stroke="#e2e8f0" stroke-width="1.6"
            marker-start="url(#arrow-white)" marker-end="url(#arrow-white)" />
      ${svgPill(W / 2, topOuterRailY, `${fmt(w)} mm`, '#f8fafc', '#1e293b', 72)}

      <!-- Right height line -->
      <line x1="${(W + 16).toFixed(1)}" y1="0" x2="${(rightOuterRailX + 8).toFixed(1)}" y2="0" stroke="#64748b" stroke-width="1" stroke-dasharray="3 3" />
      <line x1="${(W + 16).toFixed(1)}" y1="${H.toFixed(1)}" x2="${(rightOuterRailX + 8).toFixed(1)}" y2="${H.toFixed(1)}" stroke="#64748b" stroke-width="1" stroke-dasharray="3 3" />
      <line x1="${rightOuterRailX.toFixed(1)}" y1="3" x2="${rightOuterRailX.toFixed(1)}" y2="${(H - 3).toFixed(1)}" stroke="#e2e8f0" stroke-width="1.6"
            marker-start="url(#arrow-white)" marker-end="url(#arrow-white)" />
      <g transform="translate(${rightOuterRailX.toFixed(1)}, ${(H / 2).toFixed(1)}) rotate(90)">
        ${svgPill(0, 0, `${fmt(h)} mm`, '#f8fafc', '#1e293b', 72)}
      </g>
    </g>
  `;

  // 4b. HORIZONTAL GAPS (X, Cyan):
  // Placed on sub-rail: if top apex exists, place at BOTTOM (Y = H + 34) to avoid ANY apex collision!
  // If top is flat, place at Y = -28.
  if (features.length) {
    const horizRailY = hasTopApex ? H + 34 : -28;

    // Find leftmost feature and rightmost feature
    const leftFeat = features.reduce((p, c) => c.bounds.minX < p.bounds.minX ? c : p, features[0]);
    const rightFeat = features.reduce((p, c) => c.bounds.maxX > p.bounds.maxX ? c : p, features[0]);

    const leftGapMm = Math.round((leftFeat.bounds.minX - bbox.x0) * 10) / 10;
    const rightGapMm = Math.round((bbox.x1 - rightFeat.bounds.maxX) * 10) / 10;

    const leftStartX = toX(leftFeat.bounds.minX);
    const rightEndX = toX(rightFeat.bounds.maxX);

    // Translucent gap zones on wood (subtle by default, active on hover)
    let gapZones = '';
    features.forEach((f) => {
      const fsx = toX(f.bounds.minX);
      const fsw = (f.bounds.maxX - f.bounds.minX) * SCALE;
      const fsy = toY(f.bounds.maxY);
      const fsh = (f.bounds.maxY - f.bounds.minY) * SCALE;
      gapZones += `<rect class="gap-zone" x="0" y="${fsy.toFixed(1)}" width="${fsx.toFixed(1)}" height="${fsh.toFixed(1)}" fill="#38bdf8" />`;
      gapZones += `<rect class="gap-zone" x="${(fsx + fsw).toFixed(1)}" y="${fsy.toFixed(1)}" width="${(W - (fsx + fsw)).toFixed(1)}" height="${fsh.toFixed(1)}" fill="#38bdf8" />`;
    });

    // Extension lines to the cyan rail
    const refY = hasTopApex ? toY(leftFeat.bounds.minY) : toY(leftFeat.bounds.maxY);
    let extLines = `
      <line class="animate-dash" x1="${leftStartX.toFixed(1)}" y1="${refY.toFixed(1)}" x2="${leftStartX.toFixed(1)}" y2="${(horizRailY + (hasTopApex ? -6 : 6)).toFixed(1)}" stroke="#38bdf8" stroke-width="1.2" stroke-dasharray="4 3" />
      <line class="animate-dash" x1="${rightEndX.toFixed(1)}" y1="${refY.toFixed(1)}" x2="${rightEndX.toFixed(1)}" y2="${(horizRailY + (hasTopApex ? -6 : 6)).toFixed(1)}" stroke="#38bdf8" stroke-width="1.2" stroke-dasharray="4 3" />
    `;

    // Arrows and Pills
    let arrowsAndPills = `
      <line x1="3" y1="${horizRailY.toFixed(1)}" x2="${(leftStartX - 3).toFixed(1)}" y2="${horizRailY.toFixed(1)}" stroke="#38bdf8" stroke-width="1.8" marker-start="url(#arrow-cyan)" marker-end="url(#arrow-cyan)" />
      ${svgPill(Math.max(28, leftStartX / 2), horizRailY, `${fmt(leftGapMm)} mm`, '#38bdf8', '#0c1929', 60)}

      <line x1="${(rightEndX + 3).toFixed(1)}" y1="${horizRailY.toFixed(1)}" x2="${(W - 3).toFixed(1)}" y2="${horizRailY.toFixed(1)}" stroke="#38bdf8" stroke-width="1.8" marker-start="url(#arrow-cyan)" marker-end="url(#arrow-cyan)" />
      ${svgPill(Math.min(W - 28, rightEndX + (W - rightEndX) / 2), horizRailY, `${fmt(rightGapMm)} mm`, '#38bdf8', '#0c1929', 60)}
    `;

    dimensionsHtml += `
      <g class="dim-group" data-dim-id="left-gap" data-category="gaps" style="color:#38bdf8">
        ${gapZones}
        ${extLines}
        ${arrowsAndPills}
      </g>
    `;

    // 4c. VERTICAL GAPS (Y, Amber):
    // Left Outer Rail: X = -64
    const leftOuterRailX = -64;
    const topFeat = features.reduce((p, c) => c.bounds.maxY > p.bounds.maxY ? c : p, features[0]);
    const botFeat = features.reduce((p, c) => c.bounds.minY < p.bounds.minY ? c : p, features[0]);

    const topGapMm = Math.round((bbox.y1 - topFeat.bounds.maxY) * 10) / 10;
    const botGapMm = Math.round((botFeat.bounds.minY - bbox.y0) * 10) / 10;

    const topSlotTopY = toY(topFeat.bounds.maxY);
    const botSlotBotY = toY(botFeat.bounds.minY);

    dimensionsHtml += `
      <g class="dim-group" data-dim-id="top-gap" data-category="gaps" style="color:#facc15">
        <line class="animate-dash" x1="0" y1="0" x2="${(leftOuterRailX - 10).toFixed(1)}" y2="0" stroke="#facc15" stroke-width="1.2" stroke-dasharray="4 3" />
        <line class="animate-dash" x1="${toX(topFeat.bounds.minX).toFixed(1)}" y1="${topSlotTopY.toFixed(1)}" x2="${(leftOuterRailX - 10).toFixed(1)}" y2="${topSlotTopY.toFixed(1)}" stroke="#facc15" stroke-width="1.2" stroke-dasharray="4 3" />
        <line x1="${leftOuterRailX.toFixed(1)}" y1="3" x2="${leftOuterRailX.toFixed(1)}" y2="${(topSlotTopY - 3).toFixed(1)}" stroke="#facc15" stroke-width="1.8" marker-start="url(#arrow-amber)" marker-end="url(#arrow-amber)" />
        ${svgPill(leftOuterRailX - 32, Math.max(12, topSlotTopY / 2), `${fmt(topGapMm)} mm`, '#facc15', '#1c1910', 60)}
      </g>

      <g class="dim-group" data-dim-id="bottom-gap" data-category="gaps" style="color:#facc15">
        <line class="animate-dash" x1="${toX(botFeat.bounds.minX).toFixed(1)}" y1="${botSlotBotY.toFixed(1)}" x2="${(leftOuterRailX - 10).toFixed(1)}" y2="${botSlotBotY.toFixed(1)}" stroke="#facc15" stroke-width="1.2" stroke-dasharray="4 3" />
        <line class="animate-dash" x1="0" y1="${H.toFixed(1)}" x2="${(leftOuterRailX - 10).toFixed(1)}" y2="${H.toFixed(1)}" stroke="#facc15" stroke-width="1.2" stroke-dasharray="4 3" />
        <line x1="${leftOuterRailX.toFixed(1)}" y1="${(botSlotBotY + 3).toFixed(1)}" x2="${leftOuterRailX.toFixed(1)}" y2="${(H - 3).toFixed(1)}" stroke="#facc15" stroke-width="1.8" marker-start="url(#arrow-amber)" marker-end="url(#arrow-amber)" />
        ${svgPill(leftOuterRailX - 32, Math.min(H - 12, botSlotBotY + (H - botSlotBotY) / 2), `${fmt(botGapMm)} mm`, '#facc15', '#1c1910', 60)}
      </g>
    `;

    // 4d. SLOT CUT-OUT SIZE (Rose):
    // Placed cleanly in the open central interior space so it never overlaps edges or cut lines!
    const pFeat = features[0];
    const pW = pFeat.width;
    const pH = pFeat.height;
    const slotLabel = pFeat.shape === 'circle'
      ? `Ø${fmt(pFeat.diameter)} mm`
      : `${fmt(Math.max(pW, pH))} × ${fmt(Math.min(pW, pH))} mm`;
    const roseW = Math.max(82, slotLabel.length * 8.6 + 24);

    const centerX = W / 2;
    let centerY = H / 2;
    if (features.length >= 2 && Math.abs(features[0].center[1] - features[1].center[1]) > (H / SCALE) * 0.45) {
      centerY = toY(features[0].bounds.minY) + 26;
    }

    dimensionsHtml += `
      <g class="dim-group" data-dim-id="slot-size" data-category="slots" style="color:#fb7185">
        ${svgPill(centerX, centerY, slotLabel, '#fb7185', '#231017', roseW)}
      </g>
    `;

    // 4e. INNER SLOT SPACING (Emerald):
    // Check for row-to-row vertical spacing
    let rowSpacingMm = null;
    let rowGapY1 = null;
    let rowGapY2 = null;

    for (let i = 0; i < features.length; i++) {
      for (let j = 0; j < features.length; j++) {
        if (i === j) continue;
        const f1 = features[i], f2 = features[j];
        if (f2.bounds.minY >= f1.bounds.maxY - 0.1) {
          const vGap = f2.bounds.minY - f1.bounds.maxY;
          if (vGap > 1.0 && (rowSpacingMm === null || vGap < rowSpacingMm)) {
            rowSpacingMm = Math.round(vGap * 10) / 10;
            rowGapY1 = toY(f2.bounds.minY);
            rowGapY2 = toY(f1.bounds.maxY);
          }
        }
      }
    }

    if (rowSpacingMm !== null) {
      const leftInnerRailX = -28;
      const sy1 = Math.min(rowGapY1, rowGapY2);
      const sy2 = Math.max(rowGapY1, rowGapY2);

      dimensionsHtml += `
        <g class="dim-group" data-dim-id="inner-spacing" data-category="gaps" style="color:#34d399">
          <line class="animate-dash" x1="${leftStartX.toFixed(1)}" y1="${sy1.toFixed(1)}" x2="${(leftInnerRailX - 6).toFixed(1)}" y2="${sy1.toFixed(1)}" stroke="#34d399" stroke-width="1.1" stroke-dasharray="4 3" />
          <line class="animate-dash" x1="${leftStartX.toFixed(1)}" y1="${sy2.toFixed(1)}" x2="${(leftInnerRailX - 6).toFixed(1)}" y2="${sy2.toFixed(1)}" stroke="#34d399" stroke-width="1.1" stroke-dasharray="4 3" />
          <line x1="${leftInnerRailX.toFixed(1)}" y1="${(sy1 + 3).toFixed(1)}" x2="${leftInnerRailX.toFixed(1)}" y2="${(sy2 - 3).toFixed(1)}" stroke="#34d399" stroke-width="1.6" marker-start="url(#arrow-emerald)" marker-end="url(#arrow-emerald)" />
          ${svgPill(leftInnerRailX - 32, (sy1 + sy2) / 2, `${fmt(rowSpacingMm)} mm`, '#34d399', '#0a1f18', 64)}
        </g>
      `;
    }
  }

  // 4f. ROOF APEX & SLANT DIMENSIONS (Gold / Amber):
  // Clean, non-colliding display of Slant Width (Run), Slant Height (Rise), and Slant Cut in mm & cm!
  if (apexCorner && apexCorner.dir === 'top') {
    const ax = toX(apexCorner.pt[0]);
    const ay = toY(apexCorner.pt[1]);
    const shoulderSvgY = toY(apexCorner.shoulderY !== null ? apexCorner.shoulderY : 0);
    const runMm = apexCorner.run;
    const runCm = (runMm / 10).toFixed(1);
    const riseMm = apexCorner.rise;
    const riseCm = (riseMm / 10).toFixed(1);
    const slantCutMm = apexCorner.cutLength || Math.round(Math.hypot(runMm, riseMm) * 10) / 10;
    const slantCutCm = (slantCutMm / 10).toFixed(1);
    const pitchDeg = apexCorner.pitch || (runMm > 0 ? Math.round(Math.atan2(riseMm, runMm) * 1800 / Math.PI) / 10 : 45.0);

    // 1. Apex Angle Pill right above the peak
    const apexPillY = ay - 14;
    const apexText = `Apex ∠ ${fmt(apexCorner.angle)}° · Pitch: ${fmt(pitchDeg)}°`;

    // 2. Slant Width (Run) rail at Y = -38 (above roof, below outer width rail at Y = -68)
    const slantWidthRailY = -38;
    const swStartX = 0;
    const swEndX = ax;

    // 3. Slant Height (Rise) rail at X = W + 26 (between board X = W and outer height rail at X = W + 60)
    const slantHeightRailX = W + 26;
    const shStartY = ay;
    const shEndY = shoulderSvgY;

    // 4. Slant Cut Length (Diagonal) along right roof slope
    const dx = W - ax;
    const dy = shoulderSvgY - ay;
    const len = Math.hypot(dx, dy);
    const nx = len > 0 ? dy / len : 0;
    const ny = len > 0 ? -dx / len : 0;
    const offsetDist = 24;
    const ox1 = ax + nx * offsetDist;
    const oy1 = ay + ny * offsetDist;
    const ox2 = W + nx * offsetDist;
    const oy2 = shoulderSvgY + ny * offsetDist;
    const midCutX = (ox1 + ox2) / 2;
    const midCutY = (oy1 + oy2) / 2;

    dimensionsHtml += `
      <!-- 1. Apex Peak Included Angle Group -->
      <g class="dim-group" data-dim-id="apex-corner" data-category="outer" style="color:#f59e0b">
        <circle cx="${ax.toFixed(1)}" cy="${ay.toFixed(1)}" r="3.5" fill="#facc15" stroke="#0e1217" stroke-width="1.4" />
        <line x1="${ax.toFixed(1)}" y1="${ay.toFixed(1)}" x2="${ax.toFixed(1)}" y2="${(apexPillY + 11).toFixed(1)}" stroke="#f59e0b" stroke-width="1.2" stroke-dasharray="3 2" />
        ${svgPill(ax, apexPillY, apexText, '#facc15', '#1c1910', 160)}
      </g>

      <!-- 2. Slant Width (Run), Slant Height (Rise) & Diagonal Cut Group -->
      <g class="dim-group" data-dim-id="slant-dimension" data-category="outer" style="color:#f59e0b">
        <!-- Slant Width (Run): Horizontal arrow and pill from outer wall to peak centerline -->
        <line class="animate-dash" x1="${swStartX.toFixed(1)}" y1="${shoulderSvgY.toFixed(1)}" x2="${swStartX.toFixed(1)}" y2="${(slantWidthRailY - 6).toFixed(1)}" stroke="#f59e0b" stroke-width="1.1" stroke-dasharray="3 3" />
        <line class="animate-dash" x1="${swEndX.toFixed(1)}" y1="${ay.toFixed(1)}" x2="${swEndX.toFixed(1)}" y2="${(slantWidthRailY - 6).toFixed(1)}" stroke="#f59e0b" stroke-width="1.1" stroke-dasharray="3 3" />
        <line x1="${(swStartX + 3).toFixed(1)}" y1="${slantWidthRailY.toFixed(1)}" x2="${(swEndX - 3).toFixed(1)}" y2="${slantWidthRailY.toFixed(1)}" stroke="#facc15" stroke-width="1.6" marker-start="url(#arrow-amber)" marker-end="url(#arrow-amber)" />
        ${svgPill((swStartX + swEndX) / 2, slantWidthRailY, `Slant W: ${fmt(runMm)} mm (${runCm} cm)`, '#facc15', '#1c1910', 140)}

        <!-- Slant Height (Rise): Vertical arrow and pill from shoulder to peak -->
        <line class="animate-dash" x1="${ax.toFixed(1)}" y1="${shStartY.toFixed(1)}" x2="${(slantHeightRailX + 8).toFixed(1)}" y2="${shStartY.toFixed(1)}" stroke="#f59e0b" stroke-width="1.1" stroke-dasharray="3 3" />
        <line class="animate-dash" x1="${W.toFixed(1)}" y1="${shEndY.toFixed(1)}" x2="${(slantHeightRailX + 8).toFixed(1)}" y2="${shEndY.toFixed(1)}" stroke="#f59e0b" stroke-width="1.1" stroke-dasharray="3 3" />
        <line x1="${slantHeightRailX.toFixed(1)}" y1="${(shStartY + 3).toFixed(1)}" x2="${slantHeightRailX.toFixed(1)}" y2="${(shEndY - 3).toFixed(1)}" stroke="#facc15" stroke-width="1.6" marker-start="url(#arrow-amber)" marker-end="url(#arrow-amber)" />
        <g transform="translate(${slantHeightRailX.toFixed(1)}, ${((shStartY + shEndY) / 2).toFixed(1)}) rotate(90)">
          ${svgPill(0, 0, `Slant H: ${fmt(riseMm)} mm (${riseCm} cm)`, '#facc15', '#1c1910', 140)}
        </g>

        <!-- Slant Cut (Diagonal): Parallel arrow and pill along right roof slope -->
        <line class="animate-dash" x1="${ax.toFixed(1)}" y1="${ay.toFixed(1)}" x2="${ox1.toFixed(1)}" y2="${oy1.toFixed(1)}" stroke="#f59e0b" stroke-width="1.0" stroke-dasharray="2 2" />
        <line class="animate-dash" x1="${W.toFixed(1)}" y1="${shoulderSvgY.toFixed(1)}" x2="${ox2.toFixed(1)}" y2="${oy2.toFixed(1)}" stroke="#f59e0b" stroke-width="1.0" stroke-dasharray="2 2" />
        <line x1="${(ox1 + (dx / len) * 3).toFixed(1)}" y1="${(oy1 + (dy / len) * 3).toFixed(1)}" x2="${(ox2 - (dx / len) * 3).toFixed(1)}" y2="${(oy2 - (dy / len) * 3).toFixed(1)}" stroke="#facc15" stroke-width="1.6" marker-start="url(#arrow-amber)" marker-end="url(#arrow-amber)" />
        ${svgPill(midCutX, midCutY, `Cut: ${fmt(slantCutMm)} mm (${slantCutCm} cm)`, '#facc15', '#1c1910', 132)}
      </g>
    `;
  } else if (apexCorner && apexCorner.dir === 'right') {
    const ax = toX(apexCorner.pt[0]);
    const ay = toY(apexCorner.pt[1]);
    const shoulderSvgX = toX(apexCorner.shoulderX || (bbox.x0 + bbox.width * 0.5));
    const runMm = apexCorner.run;
    const runCm = (runMm / 10).toFixed(1);
    const riseMm = apexCorner.rise;
    const riseCm = (riseMm / 10).toFixed(1);
    const slantCutMm = apexCorner.cutLength || Math.round(Math.hypot(runMm, riseMm) * 10) / 10;
    const slantCutCm = (slantCutMm / 10).toFixed(1);

    dimensionsHtml += `
      <g class="dim-group" data-dim-id="apex-corner" data-category="outer" style="color:#f59e0b">
        <circle cx="${ax.toFixed(1)}" cy="${ay.toFixed(1)}" r="3.5" fill="#facc15" stroke="#0e1217" stroke-width="1.4" />
        <line x1="${ax.toFixed(1)}" y1="${ay.toFixed(1)}" x2="${(ax + 16).toFixed(1)}" y2="${ay.toFixed(1)}" stroke="#f59e0b" stroke-width="1.2" stroke-dasharray="3 2" />
        ${svgPill(ax + 24, ay, `Bow ∠ ${fmt(apexCorner.angle)}°`, '#facc15', '#1c1910', 92)}
      </g>

      <g class="dim-group" data-dim-id="slant-dimension" data-category="outer" style="color:#f59e0b">
        <line class="animate-dash" x1="${shoulderSvgX.toFixed(1)}" y1="0" x2="${shoulderSvgX.toFixed(1)}" y2="-30" stroke="#f59e0b" stroke-width="1.1" stroke-dasharray="3 3" />
        <line class="animate-dash" x1="${ax.toFixed(1)}" y1="${ay.toFixed(1)}" x2="${ax.toFixed(1)}" y2="-30" stroke="#f59e0b" stroke-width="1.1" stroke-dasharray="3 3" />
        <line x1="${(shoulderSvgX + 3).toFixed(1)}" y1="-26" x2="${(ax - 3).toFixed(1)}" y2="-26" stroke="#facc15" stroke-width="1.6" marker-start="url(#arrow-amber)" marker-end="url(#arrow-amber)" />
        ${svgPill((shoulderSvgX + ax) / 2, -26, `Bow W: ${fmt(runMm)} mm (${runCm} cm)`, '#facc15', '#1c1910', 134)}
        ${svgPill(ax + 24, ay + 26, `Cut: ${fmt(slantCutMm)} mm (${slantCutCm} cm)`, '#facc15', '#1c1910', 130)}
      </g>
    `;
  } else if (edges.filter((e) => e.type === 'angled' && e.length > summary.thickness * 2 + 1).length >= 1) {
    const mainAngled = edges.filter((e) => e.type === 'angled' && e.length > summary.thickness * 2 + 1);
    mainAngled.slice(0, 2).forEach((e, idx) => {
      const mx = toX(e.mid[0]);
      const my = toY(e.mid[1]);
      const lx = mx + (e.normal[0] || 0) * 30;
      const ly = my - (e.normal[1] || 0) * 30;
      const eRunCm = (e.run / 10).toFixed(1);
      const eRiseCm = (e.rise / 10).toFixed(1);
      const eLenCm = (e.length / 10).toFixed(1);
      dimensionsHtml += `
        <g class="dim-group" data-dim-id="corner-chamfers" data-category="outer" style="color:#f59e0b">
          <line x1="${mx.toFixed(1)}" y1="${my.toFixed(1)}" x2="${lx.toFixed(1)}" y2="${ly.toFixed(1)}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="2 2" />
          ${svgPill(lx, ly, `Cut: ${fmt(e.length)} mm (${eLenCm} cm) · W ${fmt(e.run)} mm (${eRunCm} cm) × H ${fmt(e.rise)} mm (${eRiseCm} cm)`, '#facc15', '#1c1910', 185)}
        </g>
      `;
    });
  }

  // 4g. EDGE FINGER TABS & SLANT JOINTS DIMENSIONS (Cyan / Sky):
  // Clean, dedicated dimension lines, translucent highlight polygon, and pills for edge finger tabs and roof slant joints!
  tabs.forEach((t) => {
    if (!t.pRoot1 || !t.pTip1 || !t.pTip2 || !t.pRoot2) return;
    const r1x = toX(t.pRoot1[0]);
    const r1y = toY(t.pRoot1[1]);
    const t1x = toX(t.pTip1[0]);
    const t1y = toY(t.pTip1[1]);
    const t2x = toX(t.pTip2[0]);
    const t2y = toY(t.pTip2[1]);
    const r2x = toX(t.pRoot2[0]);
    const r2y = toY(t.pRoot2[1]);

    const wMm = t.width;
    const wCm = (wMm / 10).toFixed(1);
    const dMm = t.depth;
    const startMm = t.distFromStart;
    const startCm = (startMm / 10).toFixed(1);

    // Tip vector & outward normal
    const tipDx = t2x - t1x;
    const tipDy = t2y - t1y;
    const tipLen = Math.hypot(tipDx, tipDy) || 1;
    const ux = tipDx / tipLen;
    const uy = tipDy / tipLen;

    const sx = t1x - r1x;
    const sy = t1y - r1y;
    const sLen = Math.hypot(sx, sy) || 1;
    const nx = sx / sLen;
    const ny = sy / sLen;

    // Dimension rail offset outward along normal from the tab tip
    const dimOffset = 15;
    const ox1 = t1x + nx * dimOffset;
    const oy1 = t1y + ny * dimOffset;
    const ox2 = t2x + nx * dimOffset;
    const oy2 = t2y + ny * dimOffset;
    const midOx = (ox1 + ox2) / 2 + nx * 8;
    const midOy = (oy1 + oy2) / 2 + ny * 8;

    const tabLabel = `Joint: ${fmt(wMm)} mm (${wCm} cm) · ${fmt(dMm)} mm`;
    const pillW = Math.max(90, tabLabel.length * 7.5 + 20);

    // Scribe marker along slope/edge from start corner to r1
    let scribeGuideHtml = '';
    if (t.distFromStart >= 4.0) {
      const sOx = r1x - ux * 16;
      const sOy = r1y - uy * 16;
      scribeGuideHtml = `
        <line class="animate-dash" x1="${r1x.toFixed(1)}" y1="${r1y.toFixed(1)}" x2="${sOx.toFixed(1)}" y2="${sOy.toFixed(1)}" stroke="#38bdf8" stroke-width="1.1" stroke-dasharray="3 2" />
        <circle cx="${r1x.toFixed(1)}" cy="${r1y.toFixed(1)}" r="2.8" fill="#38bdf8" stroke="#0e1217" stroke-width="1" />
      `;
    }

    dimensionsHtml += `
      <g class="dim-group" data-dim-id="tab-${t.id}" data-category="outer" style="color:#38bdf8">
        <!-- Translucent highlight over joint cut area -->
        <polygon class="gap-zone" points="${r1x.toFixed(1)},${r1y.toFixed(1)} ${t1x.toFixed(1)},${t1y.toFixed(1)} ${t2x.toFixed(1)},${t2y.toFixed(1)} ${r2x.toFixed(1)},${r2y.toFixed(1)}" fill="#38bdf8" fill-opacity="0.25" stroke="#38bdf8" stroke-width="1.3" stroke-dasharray="3 2" />
        
        <!-- Extension lines to outer dimension rail -->
        <line class="animate-dash" x1="${t1x.toFixed(1)}" y1="${t1y.toFixed(1)}" x2="${ox1.toFixed(1)}" y2="${oy1.toFixed(1)}" stroke="#38bdf8" stroke-width="1.0" stroke-dasharray="2 2" />
        <line class="animate-dash" x1="${t2x.toFixed(1)}" y1="${t2y.toFixed(1)}" x2="${ox2.toFixed(1)}" y2="${oy2.toFixed(1)}" stroke="#38bdf8" stroke-width="1.0" stroke-dasharray="2 2" />
        
        <!-- Dimension arrow line along tab tip -->
        <line x1="${(ox1 + ux * 2).toFixed(1)}" y1="${(oy1 + uy * 2).toFixed(1)}" x2="${(ox2 - ux * 2).toFixed(1)}" y2="${(oy2 - uy * 2).toFixed(1)}" stroke="#38bdf8" stroke-width="1.6" marker-start="url(#arrow-cyan)" marker-end="url(#arrow-cyan)" />
        
        <!-- Dimension Pill -->
        ${svgPill(midOx, midOy, tabLabel, '#38bdf8', '#0c1929', pillW)}
        ${scribeGuideHtml}
      </g>
    `;
  });

  let minor1mmLines = '';
  for (let i = 1; i < 10; i++) {
    if (i === 5) continue;
    const p = (i * SCALE).toFixed(1);
    const m10 = (10 * SCALE).toFixed(1);
    minor1mmLines += `<line x1="${p}" y1="0" x2="${p}" y2="${m10}" stroke="rgba(56, 189, 248, 0.16)" stroke-width="0.6" />`;
    minor1mmLines += `<line x1="0" y1="${p}" x2="${m10}" y2="${p}" stroke="rgba(56, 189, 248, 0.16)" stroke-width="0.6" />`;
  }

  return `
    <svg id="blueprint-svg-${c.id}" class="cad-inspector-svg" viewBox="${vbX.toFixed(1)} ${vbY.toFixed(1)} ${vbW.toFixed(1)} ${vbH.toFixed(1)}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <!-- 1mm Engineering Graph Paper Pattern (anchored at (0, H) baseline) -->
        <pattern id="pattern-grid-1mm" x="0" y="${H.toFixed(1)}" width="${(10 * SCALE).toFixed(1)}" height="${(10 * SCALE).toFixed(1)}" patternUnits="userSpaceOnUse">
          ${minor1mmLines}
          <line x1="${(5 * SCALE).toFixed(1)}" y1="0" x2="${(5 * SCALE).toFixed(1)}" y2="${(10 * SCALE).toFixed(1)}" stroke="rgba(56, 189, 248, 0.35)" stroke-width="0.85" />
          <line x1="0" y1="${(5 * SCALE).toFixed(1)}" x2="${(10 * SCALE).toFixed(1)}" y2="${(5 * SCALE).toFixed(1)}" stroke="rgba(56, 189, 248, 0.35)" stroke-width="0.85" />
          <path d="M ${(10 * SCALE).toFixed(1)} 0 L 0 0 0 ${(10 * SCALE).toFixed(1)}" fill="none" stroke="rgba(56, 189, 248, 0.65)" stroke-width="1.3" />
        </pattern>

        <!-- 1cm Centimeter Grid Pattern (anchored at (0, H) baseline) -->
        <pattern id="pattern-grid-1cm" x="0" y="${H.toFixed(1)}" width="${(10 * SCALE).toFixed(1)}" height="${(10 * SCALE).toFixed(1)}" patternUnits="userSpaceOnUse">
          <line x1="${(5 * SCALE).toFixed(1)}" y1="0" x2="${(5 * SCALE).toFixed(1)}" y2="${(10 * SCALE).toFixed(1)}" stroke="rgba(56, 189, 248, 0.2)" stroke-dasharray="3 3" stroke-width="0.75" />
          <line x1="0" y1="${(5 * SCALE).toFixed(1)}" x2="${(10 * SCALE).toFixed(1)}" y2="${(5 * SCALE).toFixed(1)}" stroke="rgba(56, 189, 248, 0.2)" stroke-dasharray="3 3" stroke-width="0.75" />
          <path d="M ${(10 * SCALE).toFixed(1)} 0 L 0 0 0 ${(10 * SCALE).toFixed(1)}" fill="none" stroke="rgba(56, 189, 248, 0.75)" stroke-width="1.4" />
        </pattern>

        <!-- Crisp Color-Coded Arrow Markers -->
        <marker id="arrow-white" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#e2e8f0" />
        </marker>
        <marker id="arrow-cyan" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#38bdf8" />
        </marker>
        <marker id="arrow-amber" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#facc15" />
        </marker>
        <marker id="arrow-rose" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#fb7185" />
        </marker>
        <marker id="arrow-emerald" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#34d399" />
        </marker>
      </defs>

      <!-- Background Graph Paper Grid Layer -->
      <rect id="grid-layer" x="${(-leftPad).toFixed(1)}" y="${(-topPad).toFixed(1)}" width="${vbW.toFixed(1)}" height="${vbH.toFixed(1)}" fill="url(#pattern-grid-1mm)" opacity="0.85" />

      <!-- Blueprint Content Group -->
      <g id="blueprint-content">
        ${axisRulers}
        ${geometryHtml}
        ${cutOrderHtml}
        ${drawPointsHtml}
        ${dimensionsHtml}
        <!-- Interactive Caliper Measure Layer -->
        <g id="measure-layer-${c.id}"></g>
      </g>
    </svg>
  `;
}

/**
 * Render the dedicated CAD Precision Cut & Gap Inspector component.
 * Includes Fullscreen mode toggle, interactive checklist, and thorough manual hand-cutting walkthrough.
 */
export function renderDraftingGuide(c, mode = 'all') {
  const specs = computeDraftingSpecs(c);
  if (!specs) return '';

  const { bbox, edges, angledEdges, apexCorner, features, tabs, dimensions, summary } = specs;
  const svgHtml = renderDraftingSvg(c, { mode });

  // Checklist rows
  const checkRowsHtml = dimensions.map((d) => `
    <button type="button"
      class="cad-check-row"
      data-dim-id="${d.id}"
      data-category="${d.category}">
      <div class="cad-check-info">
        <span class="cad-check-dot ${d.dotClass}"></span>
        <div class="truncate">
          <div class="cad-check-name"><span class="step-badge">Step ${d.step}</span> ${esc(d.name)}</div>
          <div class="cad-check-desc">${esc(d.desc)}</div>
        </div>
      </div>
      <span class="cad-check-badge ${d.badgeClass}">${esc(d.value)}</span>
    </button>
  `).join('');

  // Step-by-Step Hand-Cutting Walkthrough Items
  const walkthroughStepsHtml = dimensions.map((d) => `
    <div class="cad-walkthrough-step" data-dim-id="${d.id}">
      <div class="step-num-bubble">${d.step}</div>
      <div class="step-body">
        <div class="step-header">
          <span class="step-action-tag">${d.actionIcon} ${esc(d.action)}</span>
          <span class="step-title">${esc(d.name)}</span>
          <span class="step-val-badge ${d.badgeClass}">${esc(d.value)}</span>
        </div>
        <p class="step-instruction">${esc(d.guide)}</p>
        <div class="step-meta">
          <span class="step-tool">🔧 <b>Tool:</b> ${esc(d.tool)}</span>
        </div>
      </div>
    </div>
  `).join('');

  // Shop Specs Edge Rows
  const edgeRows = edges.map((e) => {
    const isAngled = e.type === 'angled';
    const lenCm = (e.length / 10).toFixed(1);
    const runCm = (e.run / 10).toFixed(1);
    const riseCm = (e.rise / 10).toFixed(1);
    return `
      <tr class="${isAngled ? 'row-angled' : ''}" data-edge="${e.index}">
        <td class="mono">#${e.index}</td>
        <td><b>${esc(e.name)}</b></td>
        <td class="mono font-bold">${fmt(e.length)} mm <span class="muted" style="font-size:10px;">(${lenCm} cm)</span></td>
        <td class="mono">${isAngled ? `<span class="badge-angle">∠ ${fmt(e.angleDeg)}°</span>` : fmt(e.angleDeg) + '°'}</td>
        <td class="mono">${isAngled ? `<span class="text-amber">W: ${fmt(e.run)} mm (${runCm} cm) × H: ${fmt(e.rise)} mm (${riseCm} cm)</span>` : '—'}</td>
        <td class="mono">${e.cornerAngleDeg ? `${fmt(e.cornerAngleDeg)}° ${e.isApex ? '<span class="badge-apex">Apex</span>' : ''}` : '—'}</td>
      </tr>`;
  }).join('');

  // Shop Specs Slot Rows
  const slotRows = features.map((f, i) => {
    const sizeStr = f.shape === 'circle' ? `Ø${fmt(f.diameter)} mm` : `${fmt(f.width)} × ${fmt(f.height)} mm`;
    const gapVert = f.gapBottom <= f.gapTop ? `Bottom: ${fmt(f.gapBottom)} mm` : `Top: ${fmt(f.gapTop)} mm`;
    const spacingStr = f.spacingToNext !== null ? `<span class="badge-gap">${fmt(f.spacingToNext)} mm</span>` : '—';
    return `
      <tr data-slot="${esc(f.id)}">
        <td class="mono">#${i + 1}</td>
        <td class="mono font-bold">${esc(f.id.replace('slot-', ''))}</td>
        <td class="mono">${sizeStr}</td>
        <td class="mono">${gapVert}</td>
        <td class="mono">Left: ${fmt(f.gapLeft)} mm</td>
        <td class="mono font-bold ${f.minMargin < 3.0 ? 'text-warn' : ''}">${fmt(f.minMargin)} mm</td>
        <td class="mono">${spacingStr}</td>
      </tr>`;
  }).join('');

  // Tabs table rows
  const tabRows = tabs.map((t, i) => {
    const wCm = (t.width / 10).toFixed(1);
    const startCm = (t.distFromStart / 10).toFixed(1);
    const endCm = (t.distFromEnd / 10).toFixed(1);
    const coordsStr = t.pRoot1 && t.pRoot2
      ? `(${fmt(t.pRoot1[0] - bbox.x0)}, ${fmt(t.pRoot1[1] - bbox.y0)}) → (${fmt(t.pRoot2[0] - bbox.x0)}, ${fmt(t.pRoot2[1] - bbox.y0)}) mm`
      : '—';
    return `
      <tr data-tab="${esc(t.id)}">
        <td class="mono">#${i + 1}</td>
        <td class="mono font-bold text-cyan">${esc(t.id)}<br/><span style="font-size:10px;color:#94a3b8;font-weight:normal;">${esc(t.locName || t.name)}</span></td>
        <td class="mono font-bold">${fmt(t.width)} mm (${wCm} cm) × ${fmt(t.depth)} mm</td>
        <td class="mono text-cyan">Scribe ${fmt(t.distFromStart)} mm (${startCm} cm)<br/><span style="font-size:10px;color:#94a3b8;">from ${esc(t.startName)}</span></td>
        <td class="mono">${fmt(t.distFromEnd)} mm (${endCm} cm)<br/><span style="font-size:10px;color:#94a3b8;">to ${esc(t.endName)}</span></td>
        <td class="mono text-slate-300" style="font-size:11px;">1. Scribe at ${fmt(t.distFromStart)}mm<br/>2. 90° out ${fmt(t.depth)}mm<br/>3. Cut ${fmt(t.width)}mm<br/>4. 90° in ${fmt(t.depth)}mm</td>
        <td class="mono text-slate-400" style="font-size:10px;">${coordsStr}</td>
      </tr>`;
  }).join('');

  return `
    <div class="cad-inspector-card" data-part-id="${esc(c.id)}">
      <!-- Fullscreen Header (only visible when maximized) -->
      <div class="cad-fs-header">
        <div class="cad-fs-title-box">
          <span class="cad-fs-dot"></span>
          <div>
            <div class="cad-fs-title">${esc(c.name || c.id)} <span class="cad-fs-sub">· ${esc(c.id)}</span></div>
            <div class="cad-fs-spec">${fmt(summary.blankWidth)} × ${fmt(summary.blankHeight)} mm · ${summary.thickness} mm sheet · Ready to Cut</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          <button type="button" class="cad-small-btn" data-tool="toggle-sidebar" title="Toggle Workshop Specs &amp; Walkthrough Drawer">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2"/></svg>
            Specs &amp; Guide
          </button>
          <button type="button" class="cad-exit-fs-btn" data-act="exit-fullscreen" title="Exit Full Screen (Esc)">
            <svg viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></svg>
            Exit Full Screen (Esc)
          </button>
        </div>
      </div>

      <!-- 2D Blueprint Controls Bar (Filters + Clarity Tools + Full Screen) -->
      <div class="cad-ctrl-bar">
        <div class="cad-filter-group">
          <button type="button" class="cad-filter-btn active" data-filter="all">All</button>
          <button type="button" class="cad-filter-btn" data-filter="gaps">Gaps Only</button>
          <button type="button" class="cad-filter-btn" data-filter="slots">Cut-outs</button>
          <button type="button" class="cad-filter-btn" data-filter="outer">Outer</button>
          <button type="button" class="cad-filter-btn" data-filter="graph" title="Hide dimension lines and show only the graph paper lines for manual hand drawing">Graph Only (No Lines)</button>
        </div>
        <div class="cad-tools-group">
          <div class="cad-grid-segmented" role="group" aria-label="Graph Paper Grid Scale">
            <span class="cad-grid-title">Graph:</span>
            <button type="button" class="cad-seg-btn active" data-grid-scale="1mm" title="1mm Engineering Graph Paper (1mm fine lines, 5mm mid, 10mm bold lines)">1mm</button>
            <button type="button" class="cad-seg-btn" data-grid-scale="1cm" title="1cm Centimeter Grid (10mm squares with 1cm numbering)">1cm</button>
            <button type="button" class="cad-seg-btn" data-grid-scale="off" title="Turn graph grid lines off">Off</button>
          </div>
          <button type="button" class="cad-tool-btn" data-tool="draw-points" title="Plot (X, Y) coordinates along graph lines so you can manually draw the shape">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="m18 2 4 4-12 12H6v-4L18 2z"/><path d="m15 5 4 4"/></svg>
            Draw Points
          </button>
          <button type="button" class="cad-tool-btn" data-tool="measure" title="Interactive Measure Scale Pointer (M): Click any two points or snap to corners to measure distance, width, height &amp; angle in mm &amp; cm">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12h20M7 8v8M12 9v6M17 8v8M2 9v6M22 9v6"/></svg>
            Measure Scale
          </button>
          <button type="button" class="cad-tool-btn" data-tool="ruler" title="Toggle Movable 15cm Digital Workshop Scale (R)">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="10" rx="1"/><line x1="6" y1="7" x2="6" y2="12"/><line x1="10" y1="7" x2="10" y2="10"/><line x1="14" y1="7" x2="14" y2="12"/><line x1="18" y1="7" x2="18" y2="10"/></svg>
            Movable Ruler
          </button>
          <button type="button" class="cad-tool-btn" data-tool="loupe" title="Hover over blueprint to magnify tight gaps">
            <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M11 8v6M8 11h6"/></svg>
            Loupe
          </button>
          <button type="button" class="cad-tool-btn" data-tool="order" title="Show recommended cutting sequence">Cut Order</button>
          <button type="button" class="cad-tool-btn" data-tool="toggle-sidebar" title="Toggle Workshop Specs &amp; Checklist">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2"/></svg>
            Specs
          </button>
          <button type="button" class="cad-tool-btn cad-btn-fullscreen" data-tool="fullscreen" title="Open Full Screen Mode (F)">
            <svg viewBox="0 0 24 24"><path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/></svg>
            Full Screen
          </button>
        </div>
      </div>

      ${summary.floatCount > 0 ? `
        <div class="cad-float-alert">
          <div class="cad-float-alert-text">
            <span class="cad-warn-dot"></span>
            <span><b>${summary.floatCount} non-integer dimension(s) detected:</b> Values have decimal fractions. Requirement: clean whole integer mm.</span>
          </div>
          <button type="button" class="cad-small-btn cad-btn-fix-floats" data-act="copy-float-fix" title="Copy prompt for AI to round dimensions to integers">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            Copy Prompt to Fix (${summary.floatCount})
          </button>
        </div>
      ` : ''}

      <!-- Color Legend Strip -->
      <div class="cad-legend">
        <span class="cad-legend-item"><span class="cad-legend-dot cad-dot-white"></span>Outer Size</span>
        <span class="cad-legend-item"><span class="cad-legend-dot cad-dot-cyan"></span>Horizontal Gap (X)</span>
        <span class="cad-legend-item"><span class="cad-legend-dot cad-dot-amber"></span>Vertical Gap (Y)</span>
        <span class="cad-legend-item"><span class="cad-legend-dot cad-dot-rose"></span>Cut-out Size</span>
        <span class="cad-legend-item"><span class="cad-legend-dot cad-dot-emerald"></span>Slot Spacing</span>
      </div>

      <!-- Main Layout (Blueprint expands to 100% full width and height in Fullscreen) -->
      <div class="cad-body-layout">
        <!-- Interactive 2D Cutting Blueprint Canvas -->
        <div class="cad-inspector-wrapper" id="blueprint-wrapper-${c.id}">
          <!-- Top-Left Zoom Controls -->
          <div class="cad-zoom-controls">
            <button type="button" class="cad-zoom-btn" data-zoom="in" title="Zoom In">+</button>
            <button type="button" class="cad-zoom-btn" data-zoom="out" title="Zoom Out">−</button>
            <button type="button" class="cad-zoom-btn fit" data-zoom="fit" title="Reset View">Fit</button>
            <button type="button" class="cad-zoom-btn fullscreen" data-zoom="fullscreen" title="Toggle Full Screen (F)">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/></svg>
            </button>
          </div>

          <!-- Top-Right Active Hint / Status Pill -->
          <div class="cad-status-pill" id="blueprint-status-${c.id}">
            Hover any gap to inspect · or click Measure Scale
          </div>

          <!-- The SVG Blueprint -->
          ${svgHtml}

          <!-- Interactive Magnifier Loupe Overlay -->
          <div id="loupe-lens-${c.id}" class="cad-loupe-lens hidden">
            <svg id="loupe-svg-${c.id}"></svg>
            <div class="cad-loupe-crosshair">
              <div class="ch-x"></div>
              <div class="ch-y"></div>
              <div class="ch-ring"></div>
            </div>
            <div class="cad-loupe-badge">2.8× ZOOM</div>
          </div>

          <!-- Interactive Measure Caliper HUD Card -->
          <div id="measure-card-${c.id}" class="cad-measure-card hidden">
            <div class="mc-head">
              <span>📐 Measured Distance</span>
              <button type="button" class="cad-ruler-btn" data-act="clear-measure" title="Clear measurement (Esc)">✕</button>
            </div>
            <div class="mc-dist" id="mc-dist-${c.id}">0.0 mm</div>
            <div class="mc-details" id="mc-details-${c.id}"></div>
            <div class="mc-actions">
              <button type="button" class="cad-small-btn" data-act="measure-again">Measure Again</button>
              <button type="button" class="cad-small-btn" data-act="copy-measure">Copy</button>
            </div>
          </div>

          <!-- Movable Digital Workshop Ruler (Scale) -->
          <div id="digital-ruler-${c.id}" class="cad-digital-ruler hidden">
            <div class="cad-ruler-bar">
              <span style="display:flex;align-items:center;gap:4px;">
                <span>📏</span> <b>15cm Precision Scale</b>
              </span>
              <div style="display:flex;align-items:center;gap:4px;">
                <button type="button" class="cad-ruler-btn" data-rot="0">0°</button>
                <button type="button" class="cad-ruler-btn" data-rot="90">90°</button>
                ${specs.slant ? `<button type="button" class="cad-ruler-btn" data-rot="${specs.slant.pitchAngle}">${specs.slant.pitchAngle}°</button>` : ''}
                <button type="button" class="cad-ruler-btn" data-rot="+15">+15°</button>
                <button type="button" class="cad-ruler-btn" data-act="close-ruler">✕</button>
              </div>
            </div>
            <div id="ruler-body-${c.id}" style="padding: 2px 4px 6px;"></div>
          </div>
        </div>

        <!-- Scrollable Workshop Sidebar (Slide-over in Fullscreen) -->
        <div class="cad-sidebar-scroll" id="sidebar-scroll-${c.id}">
          <!-- Step-by-Step Manual Hand-Cutting Procedure (Workshop Walkthrough) -->
          <div class="cad-walkthrough-card">
            <div class="cad-walkthrough-head">
              <div>
                <h4 class="cad-walkthrough-title">🛠️ Step-by-Step Hand-Cutting Procedure</h4>
                <p class="cad-walkthrough-sub">Follow each measurement sequentially to scribe and cut with ruler &amp; craft blade.</p>
              </div>
              <button type="button" class="cad-small-btn" data-act="copy-guide" title="Copy step-by-step cutting guide">
                <svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                Copy Steps
              </button>
            </div>
            <div class="cad-walkthrough-list">
              ${walkthroughStepsHtml}
            </div>
          </div>

          <!-- Measurements & Gaps Checklist -->
          <div class="cad-checklist-wrap">
            <div class="cad-checklist-head">
              <span class="cad-checklist-title">Measurements &amp; Gaps Checklist</span>
              <span class="cad-checklist-hint">Hover or click to zoom to gap</span>
            </div>
            <div class="cad-checklist" id="checklist-${c.id}">
              ${checkRowsHtml}
            </div>
          </div>

          <!-- Material & Summary Specs Cards -->
          <div class="cad-specs-grid">
            <div class="cad-spec-card">
              <div class="lbl">Cut Size</div>
              <div class="val">${fmt(summary.blankWidth)} × ${fmt(summary.blankHeight)} mm <span class="muted" style="font-size:10px;">(${(summary.blankWidth/10).toFixed(1)} × ${(summary.blankHeight/10).toFixed(1)} cm)</span></div>
            </div>
            <div class="cad-spec-card">
              <div class="lbl">Thickness</div>
              <div class="val">${summary.thickness.toFixed(1)} mm</div>
            </div>
            <div class="cad-spec-card">
              <div class="lbl">Net Area</div>
              <div class="val">${fmt((c.dimensions_2d?.area || (summary.blankWidth * summary.blankHeight * 0.95)) / 100, 1)} cm²</div>
            </div>
            ${specs.slant ? `
            <div class="cad-spec-card">
              <div class="lbl">Slant Width (Run)</div>
              <div class="val text-amber font-bold">${fmt(specs.slant.runMm)} mm <span style="font-size:10px;color:#cbd5e1;">(${specs.slant.runCm} cm)</span></div>
            </div>
            <div class="cad-spec-card">
              <div class="lbl">Slant Height (Rise)</div>
              <div class="val text-amber font-bold">${fmt(specs.slant.riseMm)} mm <span style="font-size:10px;color:#cbd5e1;">(${specs.slant.riseCm} cm)</span></div>
            </div>
            <div class="cad-spec-card">
              <div class="lbl">Slant Cut Length</div>
              <div class="val text-amber font-bold">${fmt(specs.slant.cutLengthMm)} mm <span style="font-size:10px;color:#cbd5e1;">(${specs.slant.cutLengthCm} cm)</span></div>
            </div>
            ` : ''}
          </div>

          <!-- Quick Action Buttons -->
          <div class="cad-action-grid">
            <button type="button" class="cad-primary-btn" data-act="zoom-critical">
              <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M11 8v6M8 11h6"/></svg>
              Zoom to Critical Gap
            </button>
            <button type="button" class="cad-secondary-btn" data-act="copy-specs">
              <svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              Copy Cut Specs
            </button>
          </div>

          <!-- Section 0: Plot on Graph Paper (Step-by-Step Coordinates) -->
          <details class="more drafting-details" open style="margin-top: 14px;">
            <summary><b>✏️ Plot on Graph Paper (${specs.graphPoints.length} vertices, ${specs.slotGraphPoints.length} slots)</b></summary>
            <p class="guide-tip" style="margin-bottom:8px;">💡 <b>How to draw on graph paper:</b> Place your pencil at <b>(0, 0) mm</b> at the bottom-left corner. Count millimeter or centimeter lines along X and Y to plot each coordinate dot, then connect the dots with a ruler.</p>
            <div class="table-wrap">
              <table class="drafting-table">
                <thead>
                  <tr><th>Point</th><th>X (mm)</th><th>Y (mm)</th><th>Graph Paper (cm)</th><th>Feature Description</th></tr>
                </thead>
                <tbody>
                  ${specs.graphPoints.map((gp) => `
                    <tr data-vertex="${gp.index}">
                      <td class="mono font-bold">#${gp.index}</td>
                      <td class="mono text-cyan">${fmt(gp.xMm)} mm</td>
                      <td class="mono text-amber">${fmt(gp.yMm)} mm</td>
                      <td class="mono font-bold text-emerald">${(gp.xMm / 10).toFixed(1)} × ${(gp.yMm / 10).toFixed(1)} cm</td>
                      <td>${esc(gp.desc)}</td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
            ${specs.slotGraphPoints.length ? `
              <div style="margin-top: 10px; font-weight: 700; font-size: 11px; color: #cbd5e1;">Internal Slot Graph Coordinates:</div>
              <div class="table-wrap" style="margin-top: 4px;">
                <table class="drafting-table">
                  <thead>
                    <tr><th>Slot</th><th>Size</th><th>X Range (mm)</th><th>Y Range (mm)</th><th>Center (X, Y)</th></tr>
                  </thead>
                  <tbody>
                    ${specs.slotGraphPoints.map((sp) => `
                      <tr data-slot="${esc(sp.id)}">
                        <td class="mono font-bold text-rose">${esc(sp.id)}</td>
                        <td class="mono">${esc(sp.size)}</td>
                        <td class="mono">${fmt(sp.minX)}–${fmt(sp.maxX)} mm</td>
                        <td class="mono">${fmt(sp.minY)}–${fmt(sp.maxY)} mm</td>
                        <td class="mono font-bold">(${fmt(sp.cx)}, ${fmt(sp.cy)}) mm</td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
              </div>
            ` : ''}
            <button type="button" class="cad-small-btn" data-act="copy-graph-points" style="margin-top: 10px;">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              Copy Graph Coordinates
            </button>
          </details>

          <!-- Section 1: Detailed Perimeter Edge Cuts -->
          <details class="more drafting-details" style="margin-top: 14px;">
            <summary><b>📐 Perimeter Cuts &amp; Angles (${edges.length} edges)</b></summary>
            <div class="table-wrap">
              <table class="drafting-table">
                <thead>
                  <tr><th>#</th><th>Cut Description</th><th>Length</th><th>Angle</th><th>Run × Rise (Marking)</th><th>Corner Angle</th></tr>
                </thead>
                <tbody>${edgeRows}</tbody>
              </table>
            </div>
            <p class="guide-tip">💡 <b>How to mark angles:</b> Scribe the <b>Run</b> along the horizontal edge and the <b>Rise</b> along the vertical edge, then draw a pencil line between marks.</p>
          </details>

          <!-- Section 2: Internal Slots & Cutouts -->
          ${features.length ? `
          <details class="more drafting-details">
            <summary><b>📏 Internal Slots &amp; Cutout Gaps (${features.length} features)</b></summary>
            <div class="table-wrap">
              <table class="drafting-table">
                <thead>
                  <tr><th>#</th><th>Slot ID</th><th>Slot Size</th><th>Gap from Bottom/Top</th><th>Gap from Left</th><th>Min Solid Margin</th><th>Spacing to Next</th></tr>
                </thead>
                <tbody>${slotRows}</tbody>
              </table>
            </div>
            <p class="guide-tip">💡 <b>Slot layout:</b> Scribe pencil lines at <b>Gap from Bottom</b> and <b>Gap from Left</b> to locate corners. Maintain at least <b>Min Solid Margin</b> along edges so wood does not split.</p>
          </details>` : ''}

          <!-- Section 3: Edge Tabs & Slant Joints (if present) -->
          ${tabs.length ? `
          <details class="more drafting-details" open>
            <summary><b>🧩 Edge Finger Tabs &amp; Slant Joints (${tabs.length} joints)</b></summary>
            <div class="table-wrap">
              <table class="drafting-table">
                <thead>
                  <tr><th>#</th><th>Joint ID &amp; Location</th><th>Joint Size (W × Depth)</th><th>Scribe Start (Distance)</th><th>Remaining to Corner/Peak</th><th>Cutting Sequence</th><th>Root Coordinates (X, Y)</th></tr>
                </thead>
                <tbody>${tabRows}</tbody>
              </table>
            </div>
            <p class="guide-tip">💡 <b>How to cut slant joints:</b> Measure the <b>Scribe Start</b> distance along the slope from the shoulder or peak. Make a strictly 90° perpendicular knife cut to the specified <b>Depth</b>, cut parallel along the slope for the <b>Width</b>, then return 90° back to the slope baseline.</p>
          </details>` : ''}
        </div>
      </div>
    </div>
  `;
}

/**
 * Format a comprehensive plain-text cutting guide suitable for clipboard copying.
 */
export function formatDraftingSpecsText(c) {
  const specs = computeDraftingSpecs(c);
  if (!specs) return '';

  const { bbox, edges, angledEdges, apexCorner, features, tabs, dimensions, summary } = specs;

  const lines = [
    `=================================================================`,
    `MANUAL HAND-CUTTING & WORKSHOP SPECIFICATIONS: ${c.id} (${c.name || 'Component'})`,
    `=================================================================`,
    `Material Sheet:       ${summary.thickness} mm Sheet Stock`,
    `Blank Stock Required: ${fmt(summary.blankWidth)} × ${fmt(summary.blankHeight)} mm (${(summary.blankWidth/10).toFixed(1)} × ${(summary.blankHeight/10).toFixed(1)} cm)`,
    specs.slant ? `Roof / Bow Slant:     Width: ${fmt(specs.slant.runMm)} mm (${specs.slant.runCm} cm) × Height: ${fmt(specs.slant.riseMm)} mm (${specs.slant.riseCm} cm) · Cut Length: ${fmt(specs.slant.cutLengthMm)} mm (${specs.slant.cutLengthCm} cm) (Pitch: ${fmt(specs.slant.pitchAngle)}°)` : null,
    `Perimeter Cuts:       ${summary.edgeCount} edges (${summary.angledCount} angled cuts)`,
    apexCorner ? `Apex Angle:           ${fmt(apexCorner.angle)}° included angle (Pitch: ${apexCorner.pitch ? fmt(apexCorner.pitch) + '°' : 'N/A'})` : null,
    summary.minSolidMargin !== null ? `Min Solid Margin:     ${fmt(summary.minSolidMargin)} mm (clearance to edge)` : null,
    ``,
    `--- 1. STEP-BY-STEP HAND-CUTTING PROCEDURE ---`
  ].filter(Boolean);

  dimensions.forEach((d) => {
    lines.push(`Step ${d.step}: [${d.action.toUpperCase()}] ${d.name} (${d.value})`);
    lines.push(`   Instruction: ${d.guide}`);
    lines.push(`   Tool:        ${d.tool}`);
    lines.push(``);
  });

  lines.push(
    `--- 2. PERIMETER CUTS & ANGLES ---`,
    `Edge  Cut Description        Length (mm & cm)      Angle    Run x Rise (Marking in mm & cm)             Corner Angle`,
    `--------------------------------------------------------------------------------------------------------------------`
  );

  edges.forEach((e) => {
    const idx = `#${e.index}`.padEnd(6);
    const desc = e.name.padEnd(23);
    const len = `${fmt(e.length)} mm (${(e.length/10).toFixed(1)} cm)`.padEnd(22);
    const ang = `${fmt(e.angleDeg)} deg`.padEnd(9);
    const runRise = (e.type === 'angled' ? `W ${fmt(e.run)} mm (${(e.run/10).toFixed(1)} cm) x H ${fmt(e.rise)} mm (${(e.rise/10).toFixed(1)} cm)` : '—').padEnd(44);
    const corner = e.cornerAngleDeg ? `${fmt(e.cornerAngleDeg)} deg${e.isApex ? ' (Apex)' : ''}` : '—';
    lines.push(`${idx}${desc}${len}${ang}${runRise}${corner}`);
  });

  if (features.length) {
    lines.push(
      ``,
      `--- 3. INTERNAL SLOTS & CUTOUT GAPS ---`,
      `Slot ID               Size (W x H)   Gap from Edge       Gap from Left   Min Margin   Spacing to Next`,
      `------------------------------------------------------------------------------------------------------`
    );
    features.forEach((f) => {
      const id = f.id.replace('slot-', '').padEnd(22);
      const size = (f.shape === 'circle' ? `Ø${fmt(f.diameter)} mm` : `${fmt(f.width)} x ${fmt(f.height)} mm`).padEnd(15);
      const gapVert = (f.gapBottom <= f.gapTop ? `Bottom: ${fmt(f.gapBottom)} mm` : `Top: ${fmt(f.gapTop)} mm`).padEnd(20);
      const gapLeft = `Left: ${fmt(f.gapLeft)} mm`.padEnd(16);
      const margin = `${fmt(f.minMargin)} mm`.padEnd(13);
      const spacing = f.spacingToNext !== null ? `Gap ${fmt(f.spacingToNext)} mm` : '—';
      lines.push(`${id}${size}${gapVert}${gapLeft}${margin}${spacing}`);
    });
  }

  if (tabs.length) {
    lines.push(
      ``,
      `--- 4. EDGE FINGER TABS & SLANT JOINTS ---`,
      `Joint ID              Location / Slope              Size (W x D in mm & cm)          Scribe Distance from Shoulder/Apex`,
      `-------------------------------------------------------------------------------------------------------------------------`
    );
    tabs.forEach((t) => {
      const wCm = (t.width / 10).toFixed(1);
      const startCm = (t.distFromStart / 10).toFixed(1);
      const id = t.id.padEnd(22);
      const loc = (t.locName || `Edge ${t.edge}`).padEnd(30);
      const size = `${fmt(t.width)} mm (${wCm} cm) x ${fmt(t.depth)} mm`.padEnd(33);
      const scribe = `Scribe ${fmt(t.distFromStart)} mm (${startCm} cm) from ${t.startName} (remains ${fmt(t.distFromEnd)} mm to ${t.endName})`;
      lines.push(`${id}${loc}${size}${scribe}`);
    });
  }

  lines.push(
    ``,
    `--- 5. PRACTICAL WORKSHOP TIPS ---`,
    `* Always scribe faint pencil lines with a 0.5mm mechanical pencil and verify with calipers.`,
    `* For slots: drill 0.8-1.0mm pilot holes at corners first to prevent blade overrun.`,
    `* Hold craft knife strictly at 90 degrees to ensure flat, perpendicular mating joint faces.`,
    `* Perform a dry-fit test before applying glue or finishing.`,
    `=================================================================`
  );

  return lines.join('\n');
}

/**
 * Format a comprehensive plain-text coordinate list for manual hand drawing on 1mm or 1cm graph paper.
 */
export function formatGraphPointsText(c) {
  const specs = computeDraftingSpecs(c);
  if (!specs) return '';

  const { bbox, summary, graphPoints, slotGraphPoints } = specs;
  const lines = [
    `=================================================================`,
    `MANUAL GRAPH PAPER DRAWING GUIDE: ${c.id} (${c.name || 'Component'})`,
    `=================================================================`,
    `Stock Blank Size: ${fmt(summary.blankWidth)} × ${fmt(summary.blankHeight)} mm (${(summary.blankWidth / 10).toFixed(1)} × ${(summary.blankHeight / 10).toFixed(1)} cm)`,
    `Material Gauge:   ${summary.thickness} mm Sheet Stock`,
    `Reference Datum:  Bottom-left corner = (0, 0) mm`,
    ``,
    `--- 1. OUTLINE VERTEX COORDINATES (Plot sequentially on 1mm or 1cm graph paper) ---`,
    `Point   X (mm)   Y (mm)   In Centimeters (cm)   Description`,
    `---------------------------------------------------------------------------------`
  ];

  graphPoints.forEach((gp) => {
    const idx = `#${gp.index}`.padEnd(8);
    const x = `${fmt(gp.xMm)} mm`.padEnd(9);
    const y = `${fmt(gp.yMm)} mm`.padEnd(9);
    const cm = `${(gp.xMm / 10).toFixed(1)} × ${(gp.yMm / 10).toFixed(1)} cm`.padEnd(22);
    lines.push(`${idx}${x}${y}${cm}${gp.desc}`);
  });

  if (slotGraphPoints.length) {
    lines.push(
      ``,
      `--- 2. INTERNAL SLOTS (Plot on graph lines) ---`,
      `Slot ID        Size           X Range (mm)        Y Range (mm)        Center (X, Y)`,
      `-----------------------------------------------------------------------------------`
    );
    slotGraphPoints.forEach((sp) => {
      const id = sp.id.padEnd(15);
      const size = sp.size.padEnd(15);
      const xR = `${fmt(sp.minX)}–${fmt(sp.maxX)} mm`.padEnd(20);
      const yR = `${fmt(sp.minY)}–${fmt(sp.maxY)} mm`.padEnd(20);
      const center = `(${fmt(sp.cx)}, ${fmt(sp.cy)}) mm`;
      lines.push(`${id}${size}${xR}${yR}${center}`);
    });
  }

  lines.push(
    ``,
    `--- 3. HOW TO DRAW ON GRAPH PAPER BY HAND ---`,
    `1. Place pencil at (0, 0) mm at the bottom-left corner of your 1mm or 1cm graph paper.`,
    `2. Count grid lines along X and Y to plot each coordinate point in sequence.`,
    `3. Connect the plotted points with a steel ruler to draw the exact cut contour.`,
    `4. Mark internal slots at their specified X and Y ranges.`,
    `=================================================================`
  );

  return lines.join('\n');
}

/**
 * Binds all interactive events (fullscreen, filters, loupe magnifier, zoom/pan,
 * checklist rows, walkthrough steps, and gap inspection) for the CAD Inspector.
 */
export function bindCadInspectorEvents(container, c) {
  const card = container.querySelector(`.cad-inspector-card[data-part-id="${c.id}"]`) || container.querySelector('.cad-inspector-card');
  const wrapper = container.querySelector(`#blueprint-wrapper-${c.id}`);
  const svg = container.querySelector(`#blueprint-svg-${c.id}`);
  if (!wrapper || !svg || !card) return;

  const statusEl = container.querySelector(`#blueprint-status-${c.id}`);
  const loupe = container.querySelector(`#loupe-lens-${c.id}`);
  const loupeSvg = container.querySelector(`#loupe-svg-${c.id}`);
  const specs = computeDraftingSpecs(c);
  if (!specs) return;

  // Initial state
  const rawVb = (svg.getAttribute('viewBox') || '').split(' ').map(Number);
  const defaultViewBox = {
    x: rawVb[0] || -100,
    y: rawVb[1] || -80,
    w: rawVb[2] || 450,
    h: rawVb[3] || 450
  };
  const state = {
    activeFilter: 'all',
    gridScale: '1mm',
    showDrawPoints: false,
    showCutOrder: false,
    loupeEnabled: false,
    isFullscreen: false,
    showSidebar: false,
    measureMode: false,
    measure: {
      pointA: null,
      pointB: null,
      locked: false,
      hoverSnap: null
    },
    rulerMode: false,
    rulerAngle: 0,
    hoveredDimId: null,
    lockedDimId: null,
    viewBox: { ...defaultViewBox }
  };

  const mLayer = svg.querySelector(`#measure-layer-${c.id}`);
  const mCard = container.querySelector(`#measure-card-${c.id}`);
  const rulerEl = container.querySelector(`#digital-ruler-${c.id}`);

  function toggleMeasureMode(force = null) {
    state.measureMode = force !== null ? force : !state.measureMode;
    wrapper.classList.toggle('is-measuring', state.measureMode);
    card.querySelectorAll('[data-tool="measure"]').forEach((b) => b.classList.toggle('active', state.measureMode));

    if (!state.measureMode) {
      clearMeasure();
    } else {
      if (statusEl) {
        statusEl.innerHTML = '<span style="color:#38bdf8;font-weight:700;">📐 Measure Scale Active: Click Point A on workpiece (or snap to corner)</span>';
      }
    }
  }

  function clearMeasure() {
    state.measure.pointA = null;
    state.measure.pointB = null;
    state.measure.locked = false;
    state.measure.hoverSnap = null;
    if (mLayer) mLayer.innerHTML = '';
    if (mCard) mCard.classList.add('hidden');
    if (state.measureMode && statusEl) {
      statusEl.innerHTML = '<span style="color:#38bdf8;font-weight:700;">📐 Click Point A (or snap to corner) to start measurement</span>';
    } else {
      applyDimensionStates();
    }
  }

  function getPointFromEvent(e) {
    try {
      const pt = svg.createSVGPoint();
      pt.x = e.clientX;
      pt.y = e.clientY;
      const ctm = svg.getScreenCTM();
      if (!ctm) return null;
      const svgPt = pt.matrixTransform(ctm.inverse());

      const SCALE = specs.SCALE || 5;
      const H = specs.H || (specs.bbox.height * SCALE);

      // Relative CAD coords from bottom-left origin (0, 0)
      const relCadX = Math.round((svgPt.x / SCALE) * 10) / 10;
      const relCadY = Math.round(((H - svgPt.y) / SCALE) * 10) / 10;

      // Magnetic snap check
      let nearestSnap = null;
      let minDist = 16; // 16px magnetic snap threshold in SVG coords
      if (specs.snapPoints && specs.snapPoints.length) {
        for (const sp of specs.snapPoints) {
          const d = Math.hypot(sp.svgX - svgPt.x, sp.svgY - svgPt.y);
          if (d < minDist) {
            minDist = d;
            nearestSnap = sp;
          }
        }
      }

      if (nearestSnap) {
        return {
          svgX: nearestSnap.svgX,
          svgY: nearestSnap.svgY,
          xMm: nearestSnap.xMm,
          yMm: nearestSnap.yMm,
          label: nearestSnap.label,
          snapped: true
        };
      }

      return {
        svgX: svgPt.x,
        svgY: svgPt.y,
        xMm: relCadX,
        yMm: relCadY,
        label: null,
        snapped: false
      };
    } catch {
      return null;
    }
  }

  function renderMeasureLayer(tempPt = null) {
    if (!mLayer) return;
    const SCALE = specs.SCALE || 5;
    const pA = state.measure.pointA;
    const pB = state.measure.pointB || tempPt;
    const snap = state.measure.hoverSnap;

    let html = '';

    // Snap Ring Marker
    if (snap && (!state.measure.locked || !state.measure.pointB)) {
      const lblW = Math.max(45, snap.label.length * 6.5 + 10);
      html += `
        <g class="cad-snap-marker">
          <circle cx="${snap.svgX.toFixed(1)}" cy="${snap.svgY.toFixed(1)}" r="7" fill="none" stroke="#38bdf8" stroke-width="2" class="cad-snap-ring" />
          <circle cx="${snap.svgX.toFixed(1)}" cy="${snap.svgY.toFixed(1)}" r="2.2" fill="#38bdf8" />
          <rect x="${(snap.svgX + 8).toFixed(1)}" y="${(snap.svgY - 14).toFixed(1)}" width="${lblW.toFixed(1)}" height="16" rx="4" fill="#0f172a" stroke="#38bdf8" stroke-width="1" opacity="0.95" />
          <text x="${(snap.svgX + 13).toFixed(1)}" y="${(snap.svgY - 3).toFixed(1)}" fill="#38bdf8" font-size="9" font-family="'JetBrains Mono', monospace" font-weight="700">${esc(snap.label)}</text>
        </g>
      `;
    }

    // Point A Anchor Pin
    if (pA) {
      html += `
        <g class="cad-measure-pA">
          <circle cx="${pA.svgX.toFixed(1)}" cy="${pA.svgY.toFixed(1)}" r="5.5" fill="#38bdf8" stroke="#ffffff" stroke-width="1.8" />
          <rect x="${(pA.svgX - 34).toFixed(1)}" y="${(pA.svgY - 24).toFixed(1)}" width="68" height="15" rx="3" fill="#0f172a" stroke="#38bdf8" stroke-width="1" opacity="0.92" />
          <text x="${pA.svgX.toFixed(1)}" y="${(pA.svgY - 13).toFixed(1)}" text-anchor="middle" fill="#38bdf8" font-size="8.5" font-family="'JetBrains Mono', monospace" font-weight="700">A (${fmt(pA.xMm)}, ${fmt(pA.yMm)})</text>
        </g>
      `;
    }

    // Dynamic Caliper Line & Graduated Millimeter Scale
    if (pA && pB) {
      const dx = pB.svgX - pA.svgX;
      const dy = pB.svgY - pA.svgY;
      const L = Math.hypot(dx, dy);

      if (L > 2) {
        const ux = dx / L, uy = dy / L;
        const nx = -uy, ny = ux;

        const dCadMm = Math.round((L / SCALE) * 10) / 10;
        const dXCadMm = Math.round(Math.abs(pB.xMm - pA.xMm) * 10) / 10;
        const dYCadMm = Math.round(Math.abs(pB.yMm - pA.yMm) * 10) / 10;
        const angleDeg = Math.round(Math.atan2(-dy, dx) * 1800 / Math.PI) / 10;

        // Jaw extensions at A and B
        const jawLen = 14;
        const jAx1 = pA.svgX + nx * jawLen, jAy1 = pA.svgY + ny * jawLen;
        const jAx2 = pA.svgX - nx * jawLen, jAy2 = pA.svgY - ny * jawLen;
        const jBx1 = pB.svgX + nx * jawLen, jBy1 = pB.svgY + ny * jawLen;
        const jBx2 = pB.svgX - nx * jawLen, jBy2 = pB.svgY - ny * jawLen;

        html += `
          <g class="cad-caliper-measure">
            <!-- Caliper Jaws -->
            <line x1="${jAx1.toFixed(1)}" y1="${jAy1.toFixed(1)}" x2="${jAx2.toFixed(1)}" y2="${jAy2.toFixed(1)}" stroke="#38bdf8" stroke-width="1.8" />
            <line x1="${jBx1.toFixed(1)}" y1="${jBy1.toFixed(1)}" x2="${jBx2.toFixed(1)}" y2="${jBy2.toFixed(1)}" stroke="#38bdf8" stroke-width="1.8" />

            <!-- Caliper Main Scale Spine Line -->
            <line x1="${pA.svgX.toFixed(1)}" y1="${pA.svgY.toFixed(1)}" x2="${pB.svgX.toFixed(1)}" y2="${pB.svgY.toFixed(1)}" stroke="#38bdf8" stroke-width="2.2" stroke-linecap="round" />
        `;

        // Graduated millimeter tick marks along the caliper line
        const maxTicks = Math.floor(dCadMm);
        for (let m = 1; m < maxTicks; m++) {
          const t = m * SCALE;
          const tx = pA.svgX + ux * t;
          const ty = pA.svgY + uy * t;
          let tickH = 3;
          let tickStroke = '#475569';
          let tickW = '0.7';

          if (m % 10 === 0) {
            tickH = 9;
            tickStroke = '#38bdf8';
            tickW = '1.4';
          } else if (m % 5 === 0) {
            tickH = 6;
            tickStroke = '#94a3b8';
            tickW = '1.0';
          }

          if (tickH > 3 || SCALE >= 2.5) {
            html += `<line x1="${tx.toFixed(1)}" y1="${ty.toFixed(1)}" x2="${(tx + nx * tickH).toFixed(1)}" y2="${(ty + ny * tickH).toFixed(1)}" stroke="${tickStroke}" stroke-width="${tickW}" />`;
            if (m % 10 === 0 && L > 45) {
              const lx = tx + nx * (tickH + 6);
              const ly = ty + ny * (tickH + 6);
              html += `<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="middle" fill="#38bdf8" font-size="8" font-family="'JetBrains Mono', monospace" font-weight="700">${m / 10}cm</text>`;
            }
          }
        }

        // Center Digital Readout Badge
        const midX = (pA.svgX + pB.svgX) / 2 + nx * 22;
        const midY = (pA.svgY + pB.svgY) / 2 + ny * 22;
        const mainText = `${fmt(dCadMm)} mm (${(dCadMm / 10).toFixed(2)} cm)`;
        const subText = `Run: ${fmt(dXCadMm)} · Rise: ${fmt(dYCadMm)} · ${fmt(Math.abs(angleDeg))}°`;
        const bW = Math.max(88, mainText.length * 7.5 + 16);

        html += `
          <g class="cad-measure-pill" transform="translate(${midX.toFixed(1)}, ${midY.toFixed(1)})">
            <rect x="${(-bW / 2).toFixed(1)}" y="-14" width="${bW.toFixed(1)}" height="28" rx="6" fill="#0b1320" stroke="#38bdf8" stroke-width="1.5" opacity="0.96" filter="drop-shadow(0 4px 10px rgba(0,0,0,0.6))" />
            <text x="0" y="-1" text-anchor="middle" fill="#ffffff" font-family="'JetBrains Mono', monospace" font-size="10.5" font-weight="700">${mainText}</text>
            <text x="0" y="10" text-anchor="middle" fill="#94a3b8" font-family="'JetBrains Mono', monospace" font-size="8">${subText}</text>
          </g>
        `;

        html += `</g>`;

        if (state.measure.locked) {
          // Point B pin
          html += `
            <g class="cad-measure-pB">
              <circle cx="${pB.svgX.toFixed(1)}" cy="${pB.svgY.toFixed(1)}" r="5.5" fill="#38bdf8" stroke="#ffffff" stroke-width="1.8" />
              <rect x="${(pB.svgX - 34).toFixed(1)}" y="${(pB.svgY - 24).toFixed(1)}" width="68" height="15" rx="3" fill="#0f172a" stroke="#38bdf8" stroke-width="1" opacity="0.92" />
              <text x="${pB.svgX.toFixed(1)}" y="${(pB.svgY - 13).toFixed(1)}" text-anchor="middle" fill="#38bdf8" font-size="8.5" font-family="'JetBrains Mono', monospace" font-weight="700">B (${fmt(pB.xMm)}, ${fmt(pB.yMm)})</text>
            </g>
          `;
        }
      }
    }

    mLayer.innerHTML = html;
  }

  function generateRulerSvg() {
    const rBody = container.querySelector(`#ruler-body-${c.id}`);
    if (!rBody) return;

    // 150mm ruler: 3px per mm = 450px wide, 46px high
    const rW = 450;
    const rH = 46;
    let ticks = '';

    for (let mm = 0; mm <= 150; mm++) {
      const x = mm * 3;
      if (mm % 10 === 0) {
        ticks += `<line x1="${x}" y1="0" x2="${x}" y2="16" stroke="#38bdf8" stroke-width="1.6" />`;
        ticks += `<text x="${x}" y="26" text-anchor="middle" fill="#ffffff" font-family="'JetBrains Mono', monospace" font-size="9.5" font-weight="700">${mm / 10}</text>`;
      } else if (mm % 5 === 0) {
        ticks += `<line x1="${x}" y1="0" x2="${x}" y2="11" stroke="#94a3b8" stroke-width="1.1" />`;
      } else {
        ticks += `<line x1="${x}" y1="0" x2="${x}" y2="6" stroke="#64748b" stroke-width="0.7" />`;
      }
    }

    // Bottom edge millimeter ticks (gauge)
    for (let mm = 0; mm <= 150; mm += 2) {
      const x = mm * 3;
      const len = mm % 10 === 0 ? 8 : (mm % 5 === 0 ? 5 : 3);
      ticks += `<line x1="${x}" y1="${rH}" x2="${x}" y2="${rH - len}" stroke="#38bdf8" stroke-width="${mm % 10 === 0 ? 1.2 : 0.6}" opacity="0.8" />`;
    }

    rBody.innerHTML = `
      <svg width="${rW}" height="${rH}" viewBox="0 0 ${rW} ${rH}" style="display:block;">
        <defs>
          <linearGradient id="ruler-grad-${c.id}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#0b1320" stop-opacity="0.95" />
            <stop offset="100%" stop-color="#152238" stop-opacity="0.95" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="${rW}" height="${rH}" rx="6" fill="url(#ruler-grad-${c.id})" stroke="#38bdf8" stroke-width="1.2" />
        ${ticks}
        <text x="430" y="25" fill="#38bdf8" font-family="'JetBrains Mono', monospace" font-size="8" font-weight="700">cm</text>
      </svg>
    `;
  }

  let rulerDragging = false;
  let rulerStart = { x: 0, y: 0 };
  let rulerPos = { x: 40, y: 50 };

  if (rulerEl) {
    generateRulerSvg();

    const onRulerMouseDown = (e) => {
      if (e.target.closest('.cad-ruler-btn')) return;
      rulerDragging = true;
      rulerStart = { x: e.clientX - rulerPos.x, y: e.clientY - rulerPos.y };
      document.addEventListener('mousemove', onRulerMouseMove);
      document.addEventListener('mouseup', onRulerMouseUp);
      e.preventDefault();
    };

    const onRulerMouseMove = (e) => {
      if (!rulerDragging) return;
      rulerPos.x = e.clientX - rulerStart.x;
      rulerPos.y = e.clientY - rulerStart.y;
      rulerEl.style.left = `${rulerPos.x}px`;
      rulerEl.style.top = `${rulerPos.y}px`;
    };

    const onRulerMouseUp = () => {
      rulerDragging = false;
      document.removeEventListener('mousemove', onRulerMouseMove);
      document.removeEventListener('mouseup', onRulerMouseUp);
    };

    rulerEl.addEventListener('mousedown', onRulerMouseDown);

    // Rotation buttons
    rulerEl.querySelectorAll('[data-rot]').forEach((btn) => {
      btn.onclick = () => {
        const val = btn.getAttribute('data-rot');
        if (val.startsWith('+')) {
          state.rulerAngle = (state.rulerAngle + parseInt(val.slice(1), 10)) % 360;
        } else {
          state.rulerAngle = parseFloat(val) || 0;
        }
        rulerEl.style.transform = `rotate(${state.rulerAngle}deg)`;
      };
    });

    const btnCloseRuler = rulerEl.querySelector('[data-act="close-ruler"]');
    if (btnCloseRuler) {
      btnCloseRuler.onclick = () => toggleRuler(false);
    }
  }

  function toggleRuler(force = null) {
    state.rulerMode = force !== null ? force : !state.rulerMode;
    if (rulerEl) {
      rulerEl.classList.toggle('hidden', !state.rulerMode);
    }
    const btn = card.querySelector('[data-tool="ruler"]');
    if (btn) btn.classList.toggle('active', state.rulerMode);
    if (statusEl && state.rulerMode) {
      statusEl.innerHTML = '<span style="color:#38bdf8;font-weight:700;">📏 15cm Digital Ruler Active · Drag to place across cuts, click angle buttons to rotate</span>';
      setTimeout(() => applyDimensionStates(), 2600);
    }
  }

  function toggleSidebar(force = null) {
    state.showSidebar = force !== null ? force : !state.showSidebar;
    card.classList.toggle('show-sidebar', state.showSidebar);
    card.querySelectorAll('[data-tool="toggle-sidebar"]').forEach((btn) => {
      btn.classList.toggle('active', state.showSidebar);
    });
    if (statusEl) {
      statusEl.innerHTML = state.showSidebar
        ? '<span style="color:#38bdf8;font-weight:700;">📋 Workshop Specs &amp; Procedure drawer opened</span>'
        : '<span style="color:#94a3b8;">Specs drawer closed</span>';
      setTimeout(() => applyDimensionStates(), 1800);
    }
  }

  function updateViewBoxSVG() {
    const vb = state.viewBox;
    svg.setAttribute('viewBox', `${vb.x.toFixed(1)} ${vb.y.toFixed(1)} ${vb.w.toFixed(1)} ${vb.h.toFixed(1)}`);
  }

  let animFrame = null;
  function animateViewBox(target) {
    if (animFrame) cancelAnimationFrame(animFrame);
    const start = { ...state.viewBox };
    const duration = 280;
    const t0 = performance.now();

    function step(now) {
      const p = Math.min(1, (now - t0) / duration);
      const ease = 1 - Math.pow(1 - p, 3);
      state.viewBox.x = start.x + (target.x - start.x) * ease;
      state.viewBox.y = start.y + (target.y - start.y) * ease;
      state.viewBox.w = start.w + (target.w - start.w) * ease;
      state.viewBox.h = start.h + (target.h - start.h) * ease;
      updateViewBoxSVG();
      if (p < 1) animFrame = requestAnimationFrame(step);
    }
    animFrame = requestAnimationFrame(step);
  }

  function applyDimensionStates() {
    const activeId = state.hoveredDimId || state.lockedDimId;
    const groups = svg.querySelectorAll('.dim-group');

    groups.forEach((g) => {
      const id = g.getAttribute('data-dim-id');
      const cat = g.getAttribute('data-category');

      // Category filter - hide dimension lines completely in 'graph' mode
      const matchesFilter = state.activeFilter !== 'graph' && (state.activeFilter === 'all' || state.activeFilter === cat);
      g.style.display = matchesFilter ? '' : 'none';

      // Hover / lock highlighting
      g.classList.remove('dim-active', 'dim-dimmed');
      if (activeId) {
        if (id === activeId) {
          g.classList.add('dim-active');
        } else {
          g.classList.add('dim-dimmed');
        }
      }
    });

    // Highlight matching checklist row
    card.querySelectorAll('.cad-check-row').forEach((btn) => {
      const rowId = btn.getAttribute('data-dim-id');
      if (activeId && rowId === activeId) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    // Highlight matching walkthrough step
    card.querySelectorAll('.cad-walkthrough-step').forEach((stepEl) => {
      const stepId = stepEl.getAttribute('data-dim-id');
      if (activeId && stepId === activeId) {
        stepEl.classList.add('active');
      } else {
        stepEl.classList.remove('active');
      }
    });

    // Update status badge
    if (statusEl) {
      if (activeId) {
        const dim = specs.dimensions.find((d) => d.id === activeId);
        if (dim) {
          statusEl.innerHTML = `<span style="color:${dim.color}" class="font-bold">${esc(dim.name)}: ${esc(dim.value)}</span>`;
        }
      } else if (state.activeFilter === 'graph') {
        statusEl.innerHTML = `<span style="color:#38bdf8;font-weight:700;">✏️ Graph Drawing Mode · Move cursor over blueprint to read (X, Y)</span>`;
      } else if (specs.summary.floatCount > 0) {
        statusEl.innerHTML = `<span style="color:#f59e0b;font-weight:700;">⚠️ ${specs.summary.floatCount} float dimension(s) · Click 'Copy Prompt to Fix'</span>`;
      } else {
        statusEl.textContent = state.loupeEnabled ? 'Loupe Active · Move over gaps' : 'Hover any gap to inspect';
      }
    }
  }

  function setHoverDim(dimId) {
    if (state.measureMode) return;
    state.hoveredDimId = dimId;
    applyDimensionStates();
  }

  function toggleLockDim(dimId) {
    if (state.measureMode) return;
    state.lockedDimId = state.lockedDimId === dimId ? null : dimId;
    applyDimensionStates();
  }

  function focusOnDimension(dimId) {
    const dim = specs.dimensions.find((d) => d.id === dimId);
    if (!dim) return;

    if (state.activeFilter !== 'all' && state.activeFilter !== dim.category) {
      setFilter('all');
    }

    state.lockedDimId = dimId;
    let targetBox = { ...defaultViewBox };
    if (dimId === 'outer-size') {
      targetBox = { ...defaultViewBox };
    } else if (dimId === 'slant-dimension' || dimId === 'apex-corner' || dimId === 'corner-chamfers') {
      const zw = defaultViewBox.w * 0.75;
      const zh = defaultViewBox.h * 0.75;
      targetBox = {
        x: defaultViewBox.x + (defaultViewBox.w - zw) / 2,
        y: defaultViewBox.y,
        w: zw,
        h: zh
      };
    } else if (dimId.includes('gap') || dimId.includes('slot') || dimId.includes('spacing')) {
      const zw = defaultViewBox.w * 0.65;
      const zh = defaultViewBox.h * 0.65;
      targetBox = {
        x: defaultViewBox.x + (defaultViewBox.w - zw) / 2,
        y: defaultViewBox.y + (defaultViewBox.h - zh) / 2,
        w: zw,
        h: zh
      };
    } else if (dimId.startsWith('tab-')) {
      const tabObj = specs.tabs.find((t) => `tab-${t.id}` === dimId);
      if (tabObj && tabObj.mid) {
        const zw = Math.max(100, defaultViewBox.w * 0.45);
        const zh = Math.max(100, defaultViewBox.h * 0.45);
        const tx = toX(tabObj.mid[0]);
        const ty = toY(tabObj.mid[1]);
        targetBox = {
          x: tx - zw / 2,
          y: ty - zh / 2,
          w: zw,
          h: zh
        };
      }
    }
    animateViewBox(targetBox);
    applyDimensionStates();
  }

  function setFilter(cat) {
    state.activeFilter = cat;
    state.lockedDimId = null;
    card.querySelectorAll('.cad-filter-btn').forEach((b) => {
      b.classList.toggle('active', b.dataset.filter === cat);
    });
    if (cat === 'graph') {
      if (state.gridScale === 'off') {
        setGridScale('1mm');
      }
      toggleDrawPoints(true);
    }
    applyDimensionStates();
  }

  function setGridScale(scale) {
    state.gridScale = scale;
    const gridLayer = svg.querySelector('#grid-layer');
    if (gridLayer) {
      if (scale === 'off') {
        gridLayer.style.display = 'none';
      } else {
        gridLayer.style.display = '';
        gridLayer.setAttribute('fill', scale === '1cm' ? 'url(#pattern-grid-1cm)' : 'url(#pattern-grid-1mm)');
      }
    }
    card.querySelectorAll('[data-grid-scale]').forEach((btn) => {
      btn.classList.toggle('active', btn.getAttribute('data-grid-scale') === scale);
    });
    if (statusEl) {
      const msg = scale === 'off' ? 'Grid turned off' : `Switched to ${scale} graph paper`;
      statusEl.innerHTML = `<span style="color:#38bdf8;font-weight:700;">${msg}</span>`;
      setTimeout(() => applyDimensionStates(), 1800);
    }
  }

  function toggleDrawPoints(force = null) {
    state.showDrawPoints = force !== null ? force : !state.showDrawPoints;
    const dpLayer = svg.querySelector('#draw-points-layer');
    if (dpLayer) dpLayer.style.display = state.showDrawPoints ? '' : 'none';
    const btn = card.querySelector('[data-tool="draw-points"]');
    if (btn) btn.classList.toggle('active', state.showDrawPoints);
    if (statusEl && force === null) {
      const msg = state.showDrawPoints ? 'Plot points enabled: (X, Y) coordinates shown at vertices' : 'Plot points hidden';
      statusEl.innerHTML = `<span style="color:#38bdf8;font-weight:700;">${msg}</span>`;
      setTimeout(() => applyDimensionStates(), 1800);
    }
  }

  function toggleCutOrder() {
    state.showCutOrder = !state.showCutOrder;
    const orderLayer = svg.querySelector('#cut-order-layer');
    if (orderLayer) orderLayer.style.display = state.showCutOrder ? '' : 'none';
    const btn = card.querySelector('[data-tool="order"]');
    if (btn) {
      btn.classList.toggle('active', state.showCutOrder);
      btn.classList.toggle('active-order', state.showCutOrder);
    }
  }

  function toggleMagnifier() {
    state.loupeEnabled = !state.loupeEnabled;
    const btn = card.querySelector('[data-tool="loupe"]');
    if (btn) btn.classList.toggle('active', state.loupeEnabled);
    if (!state.loupeEnabled && loupe) {
      loupe.classList.add('hidden');
    }
    applyDimensionStates();
  }

  function toggleFullscreen(forceState = null) {
    state.isFullscreen = forceState !== null ? forceState : !state.isFullscreen;
    card.classList.toggle('is-fullscreen', state.isFullscreen);
    document.body.classList.toggle('cad-card-fullscreen', state.isFullscreen);

    const btnFsAll = card.querySelectorAll('[data-tool="fullscreen"], [data-zoom="fullscreen"]');
    btnFsAll.forEach((b) => {
      b.classList.toggle('active', state.isFullscreen);
      b.setAttribute('title', state.isFullscreen ? 'Exit Full Screen (Esc)' : 'Open Full Screen (F)');
    });

    // Handle HTML5 Fullscreen API gracefully if available
    try {
      if (state.isFullscreen && card.requestFullscreen && !document.fullscreenElement) {
        card.requestFullscreen().catch(() => {});
      } else if (!state.isFullscreen && document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
    } catch {
      /* Ignore browser fullscreen permission errors */
    }

    setTimeout(() => {
      animateViewBox({ ...defaultViewBox });
      applyDimensionStates();
    }, 120);
  }

  // Mouse Wheel Zoom centered on cursor
  if (wrapper) {
    wrapper.addEventListener('wheel', (e) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 0.85 : 1.18;
      const vb = state.viewBox;
      const nw = Math.max(60, Math.min(defaultViewBox.w * 3, vb.w * factor));
      const nh = Math.max(60, Math.min(defaultViewBox.h * 3, vb.h * factor));

      try {
        const pt = svg.createSVGPoint();
        pt.x = e.clientX;
        pt.y = e.clientY;
        const ctm = svg.getScreenCTM();
        if (ctm) {
          const svgPt = pt.matrixTransform(ctm.inverse());
          const rx = (svgPt.x - vb.x) / vb.w;
          const ry = (svgPt.y - vb.y) / vb.h;
          state.viewBox.x = svgPt.x - rx * nw;
          state.viewBox.y = svgPt.y - ry * nh;
          state.viewBox.w = nw;
          state.viewBox.h = nh;
          updateViewBoxSVG();
          return;
        }
      } catch {
        /* Fallback to center zoom */
      }
      state.viewBox.x = vb.x + (vb.w - nw) / 2;
      state.viewBox.y = vb.y + (vb.h - nh) / 2;
      state.viewBox.w = nw;
      state.viewBox.h = nh;
      updateViewBoxSVG();
    }, { passive: false });

    wrapper.addEventListener('mousemove', (e) => {
      // 0. Interactive Measure Mode Pointer Tracking & Millimeter Scale
      if (state.measureMode) {
        const pt = getPointFromEvent(e);
        if (pt) {
          state.measure.hoverSnap = pt.snapped ? pt : null;
        }

        if (state.measure.pointA && !state.measure.locked) {
          renderMeasureLayer(pt);
          if (statusEl && pt) {
            const dMm = Math.round(Math.hypot(pt.xMm - state.measure.pointA.xMm, pt.yMm - state.measure.pointA.yMm) * 10) / 10;
            statusEl.innerHTML = `<span style="color:#38bdf8;font-weight:700;">📐 Measuring: ${fmt(dMm)} mm (${(dMm / 10).toFixed(2)} cm) · Click Point B to lock</span>`;
          }
        } else if (!state.measure.pointA) {
          renderMeasureLayer(pt);
          if (statusEl && pt) {
            if (pt.snapped) {
              statusEl.innerHTML = `<span style="color:#38bdf8;font-weight:700;">◎ Snapped to ${esc(pt.label)}: (${fmt(pt.xMm)}, ${fmt(pt.yMm)}) mm · Click to anchor Point A</span>`;
            } else {
              statusEl.innerHTML = `<span style="color:#38bdf8;">📍 Pointer: (${fmt(pt.xMm)}, ${fmt(pt.yMm)}) mm · Click to anchor Point A</span>`;
            }
          }
        }
        return;
      }

      // 1. Loupe magnifier handling
      if (state.loupeEnabled && loupe && loupeSvg) {
        const rect = wrapper.getBoundingClientRect();
        const relX = e.clientX - rect.left;
        const relY = e.clientY - rect.top;

        loupe.classList.remove('hidden');
        const size = 144;
        loupe.style.left = `${Math.max(8, Math.min(rect.width - size - 8, relX - size / 2))}px`;
        loupe.style.top = `${Math.max(8, Math.min(rect.height - size - 8, relY - size / 2))}px`;

        try {
          const pt = svg.createSVGPoint();
          pt.x = e.clientX;
          pt.y = e.clientY;
          const ctm = svg.getScreenCTM();
          if (ctm) {
            const svgPt = pt.matrixTransform(ctm.inverse());
            const zoomW = state.viewBox.w / 2.8;
            const zoomH = state.viewBox.h / 2.8;
            loupeSvg.innerHTML = svg.innerHTML;
            loupeSvg.setAttribute('viewBox', `${svgPt.x - zoomW / 2} ${svgPt.y - zoomH / 2} ${zoomW} ${zoomH}`);
          }
        } catch (err) {
          /* Ignore cursor tracking error on fast exit */
        }
      }

      // 2. Real-time CAD coordinate tracking on status pill
      if (statusEl && !state.hoveredDimId && !state.lockedDimId) {
        try {
          const pt = svg.createSVGPoint();
          pt.x = e.clientX;
          pt.y = e.clientY;
          const ctm = svg.getScreenCTM();
          if (ctm) {
            const svgPt = pt.matrixTransform(ctm.inverse());
            const cadXMm = svgPt.x / specs.scale;
            const cadYMm = (specs.H - svgPt.y) / specs.scale;

            if (cadXMm >= -5 && cadXMm <= specs.summary.blankWidth + 5 && cadYMm >= -5 && cadYMm <= specs.summary.blankHeight + 5) {
              const clampedX = Math.max(0, Math.min(specs.summary.blankWidth, cadXMm));
              const clampedY = Math.max(0, Math.min(specs.summary.blankHeight, cadYMm));
              statusEl.innerHTML = `<span style="font-family:'JetBrains Mono', monospace; font-size:11px;">📍 <b>X:</b> ${clampedX.toFixed(1)} mm <span style="color:#94a3b8">(${(clampedX/10).toFixed(2)} cm)</span> &nbsp;|&nbsp; <b>Y:</b> ${clampedY.toFixed(1)} mm <span style="color:#94a3b8">(${(clampedY/10).toFixed(2)} cm)</span></span>`;
            }
          }
        } catch (err) {
          /* Ignore matrix transform errors */
        }
      }
    });

    wrapper.addEventListener('click', (e) => {
      if (e.target.closest('.cad-zoom-controls') || e.target.closest('.cad-status-pill') || e.target.closest('.cad-digital-ruler') || e.target.closest('.cad-measure-card')) {
        return;
      }
      if (state.measureMode) {
        const pt = getPointFromEvent(e);
        if (!pt) return;

        if (!state.measure.pointA) {
          state.measure.pointA = pt;
          renderMeasureLayer();
          if (statusEl) {
            statusEl.innerHTML = `<span style="color:#38bdf8;font-weight:700;">📐 Point A anchored at (${fmt(pt.xMm)}, ${fmt(pt.yMm)}) mm. Now move pointer and click Point B.</span>`;
          }
        } else if (!state.measure.locked) {
          state.measure.pointB = pt;
          state.measure.locked = true;
          renderMeasureLayer();

          const pA = state.measure.pointA;
          const pB = state.measure.pointB;
          const dx = Math.round(Math.abs(pB.xMm - pA.xMm) * 10) / 10;
          const dy = Math.round(Math.abs(pB.yMm - pA.yMm) * 10) / 10;
          const dist = Math.round(Math.hypot(pB.xMm - pA.xMm, pB.yMm - pA.yMm) * 10) / 10;
          const angle = Math.round(Math.atan2(pB.yMm - pA.yMm, pB.xMm - pA.xMm) * 1800 / Math.PI) / 10;

          // Show measure card
          if (mCard) {
            const distEl = mCard.querySelector(`#mc-dist-${c.id}`);
            const detEl = mCard.querySelector(`#mc-details-${c.id}`);
            if (distEl) distEl.textContent = `${fmt(dist)} mm (${(dist / 10).toFixed(2)} cm)`;
            if (detEl) {
              detEl.innerHTML = `
                <div><b>Run (ΔX):</b> ${fmt(dx)} mm (${(dx / 10).toFixed(2)} cm)</div>
                <div><b>Rise (ΔY):</b> ${fmt(dy)} mm (${(dy / 10).toFixed(2)} cm)</div>
                <div><b>Slope Angle:</b> ${fmt(Math.abs(angle))}°</div>
                <div><b>Point A:</b> (${fmt(pA.xMm)}, ${fmt(pA.yMm)}) mm ${pA.label ? `<span style="color:#38bdf8">[${esc(pA.label)}]</span>` : ''}</div>
                <div><b>Point B:</b> (${fmt(pB.xMm)}, ${fmt(pB.yMm)}) mm ${pB.label ? `<span style="color:#38bdf8">[${esc(pB.label)}]</span>` : ''}</div>
              `;
            }
            mCard.classList.remove('hidden');
          }

          if (statusEl) {
            statusEl.innerHTML = `<span style="color:#34d399;font-weight:700;">✓ Locked: ${fmt(dist)} mm (${(dist / 10).toFixed(2)} cm) · Click [Measure Again] or Esc</span>`;
          }
        }
      }
    });

    wrapper.addEventListener('mouseleave', () => {
      if (loupe) loupe.classList.add('hidden');
      if (state.measureMode && !state.measure.locked) {
        state.measure.hoverSnap = null;
        renderMeasureLayer();
      } else {
        applyDimensionStates();
      }
    });
  }

  // Bind filter buttons
  card.querySelectorAll('.cad-filter-btn').forEach((b) => {
    b.onclick = () => setFilter(b.dataset.filter);
  });

  // Bind tools
  card.querySelectorAll('[data-grid-scale]').forEach((btn) => {
    btn.onclick = () => setGridScale(btn.getAttribute('data-grid-scale'));
  });

  const btnDrawPoints = card.querySelector('[data-tool="draw-points"]');
  if (btnDrawPoints) btnDrawPoints.onclick = () => toggleDrawPoints();

  const btnMeasure = card.querySelector('[data-tool="measure"]');
  if (btnMeasure) btnMeasure.onclick = () => toggleMeasureMode();

  const btnRuler = card.querySelector('[data-tool="ruler"]');
  if (btnRuler) btnRuler.onclick = () => toggleRuler();

  const btnOrder = card.querySelector('[data-tool="order"]');
  if (btnOrder) btnOrder.onclick = toggleCutOrder;

  const btnLoupe = card.querySelector('[data-tool="loupe"]');
  if (btnLoupe) btnLoupe.onclick = toggleMagnifier;

  card.querySelectorAll('[data-tool="toggle-sidebar"]').forEach((btn) => {
    btn.onclick = () => toggleSidebar();
  });

  const btnClearMeasure = card.querySelector('[data-act="clear-measure"]');
  if (btnClearMeasure) btnClearMeasure.onclick = () => clearMeasure();

  const btnMeasureAgain = card.querySelector('[data-act="measure-again"]');
  if (btnMeasureAgain) btnMeasureAgain.onclick = () => clearMeasure();

  const btnCopyMeasure = card.querySelector('[data-act="copy-measure"]');
  if (btnCopyMeasure) {
    btnCopyMeasure.onclick = () => {
      const pA = state.measure.pointA;
      const pB = state.measure.pointB;
      if (!pA || !pB) return;
      const dx = Math.round(Math.abs(pB.xMm - pA.xMm) * 10) / 10;
      const dy = Math.round(Math.abs(pB.yMm - pA.yMm) * 10) / 10;
      const dist = Math.round(Math.hypot(pB.xMm - pA.xMm, pB.yMm - pA.yMm) * 10) / 10;
      const angle = Math.round(Math.atan2(pB.yMm - pA.yMm, pB.xMm - pA.xMm) * 1800 / Math.PI) / 10;

      const txt = `MEASURED CAD DISTANCE: ${c.id} (${c.name || 'Component'})
Straight Distance: ${fmt(dist)} mm (${(dist / 10).toFixed(2)} cm)
Run (ΔX):          ${fmt(dx)} mm (${(dx / 10).toFixed(2)} cm)
Rise (ΔY):         ${fmt(dy)} mm (${(dy / 10).toFixed(2)} cm)
Angle:             ${fmt(Math.abs(angle))}°
Point A:           (${fmt(pA.xMm)}, ${fmt(pA.yMm)}) mm ${pA.label ? `[${pA.label}]` : ''}
Point B:           (${fmt(pB.xMm)}, ${fmt(pB.yMm)}) mm ${pB.label ? `[${pB.label}]` : ''}`;

      copyTextToClipboard(txt, 'Copied measurement to clipboard!');
    };
  }

  const btnToolFs = card.querySelector('[data-tool="fullscreen"]');
  if (btnToolFs) btnToolFs.onclick = () => toggleFullscreen();

  const btnExitFs = card.querySelector('[data-act="exit-fullscreen"]');
  if (btnExitFs) btnExitFs.onclick = () => toggleFullscreen(false);

  // Bind zoom buttons
  const btnZoomIn = card.querySelector('[data-zoom="in"]');
  if (btnZoomIn) btnZoomIn.onclick = () => {
    const vb = state.viewBox;
    const nw = Math.max(80, vb.w / 1.25);
    const nh = Math.max(80, vb.h / 1.25);
    animateViewBox({ x: vb.x + (vb.w - nw) / 2, y: vb.y + (vb.h - nh) / 2, w: nw, h: nh });
  };

  const btnZoomOut = card.querySelector('[data-zoom="out"]');
  if (btnZoomOut) btnZoomOut.onclick = () => {
    const vb = state.viewBox;
    const nw = Math.min(defaultViewBox.w * 2, vb.w * 1.25);
    const nh = Math.min(defaultViewBox.h * 2, vb.h * 1.25);
    animateViewBox({ x: vb.x + (vb.w - nw) / 2, y: vb.y + (vb.h - nh) / 2, w: nw, h: nh });
  };

  const btnZoomFit = card.querySelector('[data-zoom="fit"]');
  if (btnZoomFit) btnZoomFit.onclick = () => {
    state.lockedDimId = null;
    animateViewBox({ ...defaultViewBox });
    applyDimensionStates();
  };

  const btnZoomFs = card.querySelector('[data-zoom="fullscreen"]');
  if (btnZoomFs) btnZoomFs.onclick = () => toggleFullscreen();

  // Keyboard shortcut listener for 'F' (fullscreen), 'M' (measure), 'R' (ruler), 'S' (specs) and 'Esc'
  const onKeyDown = (e) => {
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
    if (e.key === 'f' || e.key === 'F') {
      if (document.body.contains(card)) {
        e.preventDefault();
        toggleFullscreen();
      }
    } else if (e.key === 'm' || e.key === 'M') {
      if (document.body.contains(card)) {
        e.preventDefault();
        toggleMeasureMode();
      }
    } else if (e.key === 'r' || e.key === 'R') {
      if (document.body.contains(card)) {
        e.preventDefault();
        toggleRuler();
      }
    } else if (e.key === 's' || e.key === 'S') {
      if (document.body.contains(card)) {
        e.preventDefault();
        toggleSidebar();
      }
    } else if (e.key === 'Escape') {
      if (state.measure.locked || state.measure.pointA) {
        e.preventDefault();
        clearMeasure();
      } else if (state.measureMode) {
        e.preventDefault();
        toggleMeasureMode(false);
      } else if (state.rulerMode) {
        e.preventDefault();
        toggleRuler(false);
      } else if (state.showSidebar) {
        e.preventDefault();
        toggleSidebar(false);
      } else if (state.isFullscreen) {
        e.preventDefault();
        toggleFullscreen(false);
      }
    }
  };
  window.addEventListener('keydown', onKeyDown);

  const onFsChange = () => {
    if (!document.fullscreenElement && state.isFullscreen) {
      toggleFullscreen(false);
    }
  };
  document.addEventListener('fullscreenchange', onFsChange);

  // Bind SVG dim-groups hover & click
  svg.querySelectorAll('.dim-group').forEach((g) => {
    const id = g.getAttribute('data-dim-id');
    g.addEventListener('mouseenter', () => setHoverDim(id));
    g.addEventListener('mouseleave', () => setHoverDim(null));
    g.addEventListener('click', () => toggleLockDim(id));
  });

  // Bind checklist rows
  card.querySelectorAll('.cad-check-row').forEach((row) => {
    const id = row.getAttribute('data-dim-id');
    row.addEventListener('mouseenter', () => setHoverDim(id));
    row.addEventListener('mouseleave', () => setHoverDim(null));
    row.addEventListener('click', () => focusOnDimension(id));
  });

  // Bind walkthrough step cards
  card.querySelectorAll('.cad-walkthrough-step').forEach((stepEl) => {
    const id = stepEl.getAttribute('data-dim-id');
    stepEl.addEventListener('mouseenter', () => setHoverDim(id));
    stepEl.addEventListener('mouseleave', () => setHoverDim(null));
    stepEl.addEventListener('click', () => focusOnDimension(id));
  });

  // Bind quick actions
  const btnZoomCritical = card.querySelector('[data-act="zoom-critical"]');
  if (btnZoomCritical) {
    btnZoomCritical.onclick = () => {
      const critDim = specs.dimensions.find((d) => d.id === 'left-gap' || d.id === 'bottom-gap' || d.id === 'top-gap') || specs.dimensions[0];
      if (critDim) focusOnDimension(critDim.id);
    };
  }

  async function copyTextToClipboard(text, successMsg) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      if (statusEl) {
        statusEl.innerHTML = `<span style="color:#34d399;font-weight:700;">✓ ${esc(successMsg)}</span>`;
        setTimeout(() => applyDimensionStates(), 2400);
      }
    } catch {
      if (statusEl) statusEl.textContent = 'Failed to copy';
    }
  }

  const btnCopySpecs = card.querySelector('[data-act="copy-specs"]');
  if (btnCopySpecs) {
    btnCopySpecs.onclick = () => copyTextToClipboard(formatDraftingSpecsText(c), 'Copied cut specs to clipboard!');
  }

  const btnCopyGuide = card.querySelector('[data-act="copy-guide"]');
  if (btnCopyGuide) {
    btnCopyGuide.onclick = () => copyTextToClipboard(formatDraftingSpecsText(c), 'Copied hand-cutting guide!');
  }

  const btnCopyGraph = card.querySelector('[data-act="copy-graph-points"]');
  if (btnCopyGraph) {
    btnCopyGraph.onclick = () => copyTextToClipboard(formatGraphPointsText(c), 'Copied graph coordinates!');
  }

  // Interactive highlighting between table rows and vertex / slot pins
  card.querySelectorAll('tr[data-vertex]').forEach((row) => {
    const idx = row.getAttribute('data-vertex');
    const pin = svg.querySelector(`.vertex-pin[data-vertex="${idx}"]`);
    row.addEventListener('mouseenter', () => {
      if (pin) pin.classList.add('pin-highlight');
      row.classList.add('row-highlight');
    });
    row.addEventListener('mouseleave', () => {
      if (pin) pin.classList.remove('pin-highlight');
      row.classList.remove('row-highlight');
    });
  });

  svg.querySelectorAll('.vertex-pin').forEach((pin) => {
    const idx = pin.getAttribute('data-vertex');
    const row = card.querySelector(`tr[data-vertex="${idx}"]`);
    pin.addEventListener('mouseenter', () => {
      pin.classList.add('pin-highlight');
      if (row) row.classList.add('row-highlight');
    });
    pin.addEventListener('mouseleave', () => {
      pin.classList.remove('pin-highlight');
      if (row) row.classList.remove('row-highlight');
    });
  });

  card.querySelectorAll('tr[data-slot]').forEach((row) => {
    const sid = row.getAttribute('data-slot');
    const pin = svg.querySelector(`.slot-pin[data-slot="${sid}"]`);
    row.addEventListener('mouseenter', () => {
      if (pin) pin.classList.add('pin-highlight');
      row.classList.add('row-highlight');
    });
    row.addEventListener('mouseleave', () => {
      if (pin) pin.classList.remove('pin-highlight');
      row.classList.remove('row-highlight');
    });
  });

  svg.querySelectorAll('.slot-pin').forEach((pin) => {
    const sid = pin.getAttribute('data-slot');
    const row = card.querySelector(`tr[data-slot="${sid}"]`);
    pin.addEventListener('mouseenter', () => {
      pin.classList.add('pin-highlight');
      if (row) row.classList.add('row-highlight');
    });
    pin.addEventListener('mouseleave', () => {
      pin.classList.remove('pin-highlight');
      if (row) row.classList.remove('row-highlight');
    });
  });

  card.querySelectorAll('tr[data-tab]').forEach((row) => {
    const tabId = row.getAttribute('data-tab');
    const dimId = `tab-${tabId}`;
    row.addEventListener('mouseenter', () => setHoverDim(dimId));
    row.addEventListener('mouseleave', () => setHoverDim(null));
    row.addEventListener('click', () => focusOnDimension(dimId));
  });

  const btnFixFloats = card.querySelector('[data-act="copy-float-fix"]');
  if (btnFixFloats) {
    btnFixFloats.onclick = () => {
      const floatDims = specs.dimensions.filter((d) => d.isFloat);
      const promptText = `The following dimensions in component '${c.id}' (${c.name || 'Component'}) do NOT meet the integer millimetre requirement because they contain floating-point numbers with decimal fractions:

${floatDims.map((d) => `- ${d.name}: current value is ${d.value} (must be a clean round integer mm, e.g. ${Math.round(parseFloat(d.value) || 0)} mm)`).join('\n')}

REQUIREMENT:
All board dimensions (width, height, thickness), coordinates (X, Y, Z), profiles, opening cutouts, tab sizes and gap margins must be clean ROUND INTEGER NUMBERS in millimetres (e.g. 7, 12, 17, 30, 38 mm). Never use fractional decimals like 6.7, 16.6, 3.9, 28.2 mm.

UPDATE INSTRUCTION:
Update the existing design ONLY for these specific dimensions to match clean integer millimetres (round each to the nearest sensible integer). Keep every other board, id, position, and connection exactly as it is.

Return the COMPLETE updated design as one \`\`\`json code block.`;

      copyTextToClipboard(promptText, `Copied prompt to fix ${floatDims.length} floating-point dimension(s)!`);
    };
  }
}
