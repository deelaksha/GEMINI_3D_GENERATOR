/**
 * Universal 2D Sheet Nesting & Manufacturing Layout Engine
 * Sections 26, 28, 29 of Master Context: Multi-sheet nesting and vector manufacturing outputs.
 */
import { AppState } from '../core/config.js';

export const SheetNester = {
  /**
   * Generates SVG XML for a complete nested manufacturing sheet.
   */
  generateSheetSVG(model, sheetNum, thickness) {
    const { kerf, clearance } = AppState.getMaterialProfile();
    const sheetDef = (model.manufacturingSheets || []).find(s => s.sheetNum === sheetNum) || {
      sheetW: 400,
      sheetH: 300,
      name: `sheet_0${sheetNum}.svg`,
      layout: {}
    };

    const sheetW = sheetDef.sheetW || 400;
    const sheetH = sheetDef.sheetH || 300;
    const layout = sheetDef.layout || {};

    let sheetParts = model.getPartsForSheet(sheetNum);
    if ((!sheetParts || sheetParts.length === 0) && sheetNum === 1) {
      sheetParts = model.parts || [];
    }
    let partsSvg = '';

    let autoX = 45;
    let autoY = 55;
    let rowH = 0;

    sheetParts.forEach(part => {
      let placement = layout[part.id];
      if (!placement) {
        const pw = Math.max(part.width || 40, 30);
        const pl = Math.max(part.length || 40, 30);
        if (autoX + pw > sheetW - 30) {
          autoX = 45;
          autoY += rowH + 18;
          rowH = 0;
        }
        if (autoY + pl > sheetH - 30) {
          autoY = 55;
        }
        placement = { x: Math.round(autoX + pw / 2), y: Math.round(autoY + pl / 2), r: 0 };
        autoX += pw + 18;
        if (pl > rowH) rowH = pl;
      }
      let geo = null;
      if (typeof part.generate2D === 'function') {
        try { geo = part.generate2D(thickness, kerf, clearance); } catch (e) {}
      }
      if (!geo && part.geometry && Array.isArray(part.geometry.outline)) {
        geo = part.geometry;
      }
      if (!geo || !Array.isArray(geo.outline) || geo.outline.length === 0) {
        geo = { outline: [[-20, -20], [20, -20], [20, 20], [-20, 20]], cutouts: [] };
      }

      let d = '';
      geo.outline.forEach((pt, idx) => {
        d += (idx === 0 ? 'M' : 'L') + `${pt[0]},${pt[1]} `;
      });
      d += 'Z';

      let cutsSvg = '';
      (geo.cutouts || []).forEach(c => {
        const hw = c.w / 2;
        const hh = c.h / 2;
        if (c.arched) {
          cutsSvg += `<path d="M${c.x - hw},${c.y - hh} L${c.x + hw},${c.y - hh} L${c.x + hw},${c.y + hh * 0.4} Q${c.x},${c.y + hh * 1.3} ${c.x - hw},${c.y + hh * 0.4} Z" fill="none" stroke="#ef4444" stroke-width="0.3"/>`;
        } else {
          cutsSvg += `<rect x="${c.x - hw}" y="${c.y - hh}" width="${c.w}" height="${c.h}" fill="none" stroke="#ef4444" stroke-width="0.3"/>`;
        }
      });

      let engraveSvg = '';
      (geo.engravings || []).forEach(e => {
        if (e.type === 'circle') engraveSvg += `<circle cx="${e.x}" cy="${e.y}" r="${e.r}" fill="none" stroke="#38bdf8" stroke-width="0.3"/>`;
        else if (e.type === 'line') engraveSvg += `<line x1="${e.x1}" y1="${e.y1}" x2="${e.x2}" y2="${e.y2}" stroke="#38bdf8" stroke-width="0.3"/>`;
        else if (e.type === 'rect') engraveSvg += `<rect x="${e.x}" y="${e.y}" width="${e.w}" height="${e.h}" fill="none" stroke="#38bdf8" stroke-width="0.3"/>`;
        else if (e.type === 'cross') {
          const s = e.size;
          engraveSvg += `<line x1="${e.x - s / 2}" y1="${e.y}" x2="${e.x + s / 2}" y2="${e.y}" stroke="#38bdf8" stroke-width="0.3"/>`;
          engraveSvg += `<line x1="${e.x}" y1="${e.y - s / 2}" x2="${e.x}" y2="${e.y + s / 2}" stroke="#38bdf8" stroke-width="0.3"/>`;
        }
      });

      partsSvg += `
        <g id="part-${part.id}" transform="translate(${placement.x}, ${placement.y}) rotate(${placement.r})">
          <!-- Cut Outline -->
          <path d="${d}" fill="#1e293b" stroke="#ef4444" stroke-width="0.4"/>
          <!-- Mortises -->
          ${cutsSvg}
          <!-- Engraving -->
          ${engraveSvg}
          <text x="0" y="2" font-family="monospace" font-size="3" fill="#cbd5e1" text-anchor="middle" font-weight="bold">${part.id}</text>
        </g>
      `;
    });

    const fullSource = `<?xml version="1.0" encoding="UTF-8"?>
<!-- PUZZLECORE MANUFACTURING SHEET: ${sheetDef.name} -->
<!-- Material Gauge: ${thickness.toFixed(1)}mm | Laser Kerf: ${kerf.toFixed(2)}mm -->
<svg id="master-laser-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${sheetW} ${sheetH}" width="100%" class="max-w-[820px] border border-slate-700 bg-slate-950 rounded shadow-2xl">
  <!-- Stock Boundary Cut Line -->
  <rect x="0" y="0" width="${sheetW}" height="${sheetH}" fill="#0f172a" stroke="#475569" stroke-width="0.8" stroke-dasharray="3,3"/>
  <text x="12" y="16" font-family="monospace" font-size="6" fill="#64748b" font-weight="bold">${sheetDef.name} [${sheetW}x${sheetH}mm]</text>
  ${partsSvg}
</svg>`;

    return {
      source: fullSource,
      sheetDef,
      partsCount: sheetParts.length
    };
  },

  downloadSheetSVG(model, sheetNum, thickness) {
    const { source } = this.generateSheetSVG(model, sheetNum, thickness);
    const url = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(source);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${model.id}_sheet_0${sheetNum}_${thickness.toFixed(1)}mm.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
};
