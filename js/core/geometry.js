/**
 * Universal Geometry Engine
 * Bridges 2D vector profiles with 3D Three.js extrusions and SVG manufacturing code.
 */

export const GeometryEngine = {
  /**
   * Generates a Three.js ExtrudeGeometry for a given part 2D definition.
   */
  createThreeExtrude(geoData, thickness) {
    if (typeof THREE === 'undefined') return null;

    const shape = new THREE.Shape();
    if (!geoData.outline || geoData.outline.length === 0) return null;

    geoData.outline.forEach((pt, idx) => {
      if (idx === 0) shape.moveTo(pt[0], pt[1]);
      else shape.lineTo(pt[0], pt[1]);
    });
    shape.closePath();

    // Internal cutouts / mortises
    if (geoData.cutouts && geoData.cutouts.length > 0) {
      geoData.cutouts.forEach(c => {
        const holePath = new THREE.Path();
        const hw = c.w / 2;
        const hh = c.h / 2;
        if (c.arched) {
          holePath.moveTo(c.x - hw, c.y - hh);
          holePath.lineTo(c.x + hw, c.y - hh);
          holePath.lineTo(c.x + hw, c.y + hh * 0.4);
          holePath.quadraticCurveTo(c.x, c.y + hh * 1.3, c.x - hw, c.y + hh * 0.4);
          holePath.closePath();
        } else {
          holePath.moveTo(c.x - hw, c.y - hh);
          holePath.lineTo(c.x + hw, c.y - hh);
          holePath.lineTo(c.x + hw, c.y + hh);
          holePath.lineTo(c.x - hw, c.y + hh);
          holePath.closePath();
        }
        shape.holes.push(holePath);
      });
    }

    const extrudeSettings = {
      depth: thickness,
      bevelEnabled: true,
      bevelSegments: 1,
      steps: 1,
      bevelSize: 0.18,
      bevelThickness: 0.18
    };

    const geometry = new THREE.ExtrudeGeometry(shape, extrudeSettings);
    geometry.center();
    return geometry;
  },

  /**
   * Computes 2D bounding box
   */
  computeBoundingBox(points) {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    points.forEach(p => {
      if (p[0] < minX) minX = p[0];
      if (p[0] > maxX) maxX = p[0];
      if (p[1] < minY) minY = p[1];
      if (p[1] > maxY) maxY = p[1];
    });
    return { minX, maxX, minY, maxY, width: maxX - minX, height: maxY - minY };
  },

  /**
   * Generates standalone valid SVG XML for an individual part.
   */
  generateStandalonePartSVG(part, thickness, kerf = 0.15, clearance = 0.10) {
    const geo = part.generate2D(thickness, kerf, clearance);
    const bounds = this.computeBoundingBox(geo.outline);
    const pad = 12;
    const w = bounds.width + pad * 2;
    const h = bounds.height + pad * 2;

    let pathD = '';
    geo.outline.forEach((pt, i) => {
      pathD += (i === 0 ? 'M' : 'L') + `${pt[0]},${pt[1]} `;
    });
    pathD += 'Z';

    let cutsSvg = '';
    (geo.cutouts || []).forEach(c => {
      const hw = c.w / 2;
      const hh = c.h / 2;
      if (c.arched) {
        cutsSvg += `\n    <path d="M${c.x - hw},${c.y - hh} L${c.x + hw},${c.y - hh} L${c.x + hw},${c.y + hh * 0.4} Q${c.x},${c.y + hh * 1.3} ${c.x - hw},${c.y + hh * 0.4} Z" fill="none" stroke="#ef4444" stroke-width="0.3" data-cut="true"/>`;
      } else {
        cutsSvg += `\n    <rect x="${c.x - hw}" y="${c.y - hh}" width="${c.w}" height="${c.h}" fill="none" stroke="#ef4444" stroke-width="0.3" data-cut="true"/>`;
      }
    });

    let engraveSvg = '';
    (geo.engravings || []).forEach(e => {
      if (e.type === 'circle') engraveSvg += `\n    <circle cx="${e.x}" cy="${e.y}" r="${e.r}" fill="none" stroke="#38bdf8" stroke-width="0.3" data-engrave="true"/>`;
      else if (e.type === 'cross') {
        const s = e.size;
        engraveSvg += `\n    <line x1="${e.x - s / 2}" y1="${e.y}" x2="${e.x + s / 2}" y2="${e.y}" stroke="#38bdf8" stroke-width="0.3" data-engrave="true"/>`;
        engraveSvg += `\n    <line x1="${e.x}" y1="${e.y - s / 2}" x2="${e.x}" y2="${e.y + s / 2}" stroke="#38bdf8" stroke-width="0.3" data-engrave="true"/>`;
      } else if (e.type === 'line') engraveSvg += `\n    <line x1="${e.x1}" y1="${e.y1}" x2="${e.x2}" y2="${e.y2}" stroke="#38bdf8" stroke-width="0.3" data-engrave="true"/>`;
      else if (e.type === 'rect') engraveSvg += `\n    <rect x="${e.x}" y="${e.y}" width="${e.w}" height="${e.h}" fill="none" stroke="#38bdf8" stroke-width="0.3" data-engrave="true"/>`;
    });

    const fullSource = `<?xml version="1.0" encoding="UTF-8"?>
<!-- PUZZLECORE PHYSICAL PART FILE: ${part.fileName} -->
<!-- Model Part ID: ${part.id} | Part Name: ${part.name} -->
<!-- Material Gauge: ${thickness.toFixed(1)}mm | Clearance: ${clearance.toFixed(2)}mm | Kerf: ${kerf.toFixed(2)}mm -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="${bounds.minX - pad} ${bounds.minY - pad} ${w} ${h}" width="${w}mm" height="${h}mm">
  <g id="${part.id}">
    <!-- Laser Cut Perimeter (Red: 0.1mm) -->
    <path d="${pathD}" fill="#1e293b" stroke="#ef4444" stroke-width="0.4" data-cut="true"/>
    <!-- Mortise / Slot Cuts (Red: 0.1mm) -->${cutsSvg}
    <!-- Vector Engraving Lines (Sky Blue: 0.2mm) -->${engraveSvg}
    <!-- Engraved Identification Badge -->
    <text x="0" y="2" font-family="monospace" font-size="3.2" fill="#e2e8f0" text-anchor="middle" font-weight="bold">${part.id}</text>
  </g>
</svg>`;

    return {
      source: fullSource,
      viewBox: `${bounds.minX - pad} ${bounds.minY - pad} ${w} ${h}`,
      widthMm: w,
      heightMm: h,
      pathD,
      cutsSvg,
      engraveSvg
    };
  }
};
