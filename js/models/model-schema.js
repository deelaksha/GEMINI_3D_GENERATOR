/**
 * Universal Object Model & Schema Validator
 * Sections 4, 5, 6 of Master Context: Authoritative structured object & part definition.
 */

import { ConnectorStandards } from '../core/connectors.js';

export class ConstructionObject {
  constructor(data) {
    this.id = data.id || 'unnamed_object';
    this.name = data.name || 'Unnamed Construction Object';
    this.category = data.category || 'General';
    this.description = data.description || '';
    this.difficulty = data.difficulty || 'Level 2 - Intermediate';
    this.defaultScale = data.defaultScale || 1.0;
    this.parts = (data.parts || []).map(p => ConstructionObject.normalizePart(p));
    this.joints = data.joints || [];
    this.assemblies = data.assemblies || [];
    this.assemblySteps = data.assemblySteps || [];
    this.manufacturingSheets = data.manufacturingSheets || [];
    this.cameraBookmarks = data.cameraBookmarks || [];
  }

  /**
   * Normalizes a part definition to guarantee dual-representation:
   * both part.generate2D(t, kerf, clr) and part.geometry = { outline, cutouts }
   */
  static normalizePart(part) {
    if (!part || typeof part !== 'object') return part;

    // Clone or wrap part to avoid mutating frozen definitions
    const p = { ...part };

    // 1. If part has generate2D function, ensure geometry is also populated
    if (typeof p.generate2D === 'function') {
      try {
        const sampleGeo = p.generate2D(3.0, 0.15, 0.10);
        if (sampleGeo && Array.isArray(sampleGeo.outline)) {
          p.geometry = {
            outline: sampleGeo.outline,
            cutouts: (sampleGeo.cutouts || []).map(ConstructionObject.normalizeCutout)
          };
        }
      } catch (err) {
        console.warn(`[ConstructionObject] Error pre-evaluating generate2D for part ${p.id}:`, err);
      }
    } else if (p.geometry && Array.isArray(p.geometry.outline)) {
      // 2. If part has static geometry, synthesize generate2D
      const staticGeo = p.geometry;
      const normalizedCutouts = (staticGeo.cutouts || []).map(ConstructionObject.normalizeCutout);
      p.geometry = {
        outline: staticGeo.outline || [],
        cutouts: normalizedCutouts
      };
      p.generate2D = function(thickness = 3.0, kerf = 0.15, clearance = 0.10) {
        return {
          outline: staticGeo.outline || [],
          cutouts: normalizedCutouts
        };
      };
    } else if (p.polygon && Array.isArray(p.polygon)) {
      // 3. If part has 2D polygon outline
      const normalizedCutouts = (p.cutouts || []).map(ConstructionObject.normalizeCutout);
      p.geometry = {
        outline: p.polygon,
        cutouts: normalizedCutouts
      };
      p.generate2D = function() {
        return {
          outline: p.polygon,
          cutouts: normalizedCutouts
        };
      };
    } else {
      // 4. Fallback rectangular geometry if neither is defined
      const w = p.width || 30;
      const l = p.length || 30;
      const hw = w / 2;
      const hl = l / 2;
      const fallbackGeo = {
        outline: [[-hw, -hl], [hw, -hl], [hw, hl], [-hw, hl]],
        cutouts: []
      };
      p.geometry = fallbackGeo;
      p.generate2D = function() {
        return fallbackGeo;
      };
    }

    // Attach parametric transform evaluation methods
    p.getAssembledPos = function(thickness = 3.0) {
      if (typeof this.assembledPos === 'function') {
        return this.assembledPos(thickness);
      }
      return this.assembledPos || [0, 0, 0];
    };

    p.getAssembledRot = function(thickness = 3.0) {
      if (typeof this.assembledRot === 'function') {
        return this.assembledRot(thickness);
      }
      return this.assembledRot || [0, 0, 0];
    };

    return p;
  }

  /**
   * Normalizes a cutout representation into a standard { x, y, w, h } object.
   */
  static normalizeCutout(c) {
    if (!c) return { x: 0, y: 0, w: 10, h: 10 };
    if (Array.isArray(c)) {
      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      c.forEach(pt => {
        if (pt[0] < minX) minX = pt[0];
        if (pt[0] > maxX) maxX = pt[0];
        if (pt[1] < minY) minY = pt[1];
        if (pt[1] > maxY) maxY = pt[1];
      });
      return {
        x: (minX + maxX) / 2,
        y: (minY + maxY) / 2,
        w: maxX - minX,
        h: maxY - minY,
        points: c
      };
    }
    return c;
  }

  /**
   * Synthesizes authoritative joints from part connection declarations if not explicitly authored.
   */
  static synthesizeJointsFromParts(parts = []) {
    const joints = [];
    const partMap = new Map(parts.map(p => [p.id, p]));
    let jointCounter = 1;

    const isSlot = (c) => !c.arched && !c.decorative && Math.min(c.w, c.h) <= 6.0;

    parts.forEach(partA => {
      (partA.connections || []).forEach(conn => {
        const targetId = typeof conn === 'string' ? conn : (conn.partId || conn.targetPartId);
        const partB = partMap.get(targetId);
        if (!partB) return;

        const alreadyExists = joints.some(j =>
          (j.connectorPartId === partA.id && j.receiverPartId === targetId) ||
          (j.connectorPartId === targetId && j.receiverPartId === partA.id)
        );
        if (alreadyExists) return;

        const posA = typeof partA.getAssembledPos === 'function' ? partA.getAssembledPos(3.0) : (partA.assembledPos || [0, 0, 0]);
        const rotA = typeof partA.getAssembledRot === 'function' ? partA.getAssembledRot(3.0) : (partA.assembledRot || [0, 0, 0]);
        const posB = typeof partB.getAssembledPos === 'function' ? partB.getAssembledPos(3.0) : (partB.assembledPos || [0, 0, 0]);
        const rotB = typeof partB.getAssembledRot === 'function' ? partB.getAssembledRot(3.0) : (partB.assembledRot || [0, 0, 0]);

        const isNear = (c, hostPos, hostRot, targetPos) => {
          const w = ConnectorStandards.local2DToWorld([c.x, c.y], hostPos, hostRot);
          const dx = w[0] - targetPos[0], dy = w[1] - targetPos[1], dz = w[2] - targetPos[2];
          return Math.sqrt(dx * dx + dy * dy + dz * dz) < 45.0;
        };

        const cutoutsB = (partB.geometry?.cutouts || []).filter(c => isSlot(c) && isNear(c, posB, rotB, posA));
        const cutoutsA = (partA.geometry?.cutouts || []).filter(c => isSlot(c) && isNear(c, posA, rotA, posB));

        if (cutoutsB.length > 0) {
          cutoutsB.forEach((c, idx) => {
            joints.push({
              id: `J-${partA.id}-${partB.id}-${idx + 1}`,
              sourcePart: partA.id,
              connectorPartId: partA.id,
              targetPart: partB.id,
              receiverPartId: partB.id,
              type: 'mortise-tenon',
              connectorAxis: c.w >= c.h ? 'X' : 'Y',
              receiverAxis: c.w >= c.h ? 'X' : 'Y',
              tabWidth: Math.max(c.w, c.h),
              position: [c.x, c.y]
            });
          });
        } else if (cutoutsA.length > 0) {
          cutoutsA.forEach((c, idx) => {
            joints.push({
              id: `J-${partB.id}-${partA.id}-${idx + 1}`,
              sourcePart: partB.id,
              connectorPartId: partB.id,
              targetPart: partA.id,
              receiverPartId: partA.id,
              type: 'mortise-tenon',
              connectorAxis: c.w >= c.h ? 'X' : 'Y',
              receiverAxis: c.w >= c.h ? 'X' : 'Y',
              tabWidth: Math.max(c.w, c.h),
              position: [c.x, c.y]
            });
          });
        } else {
          joints.push({
            id: `J-${partA.id}-${partB.id}-${jointCounter++}`,
            sourcePart: partA.id,
            connectorPartId: partA.id,
            targetPart: partB.id,
            receiverPartId: partB.id,
            type: 'contact',
            connectorAxis: 'X',
            receiverAxis: 'X',
            tabWidth: 20,
            position: [0, 0]
          });
        }
      });
    });

    return joints;
  }

  getPart(partId) {
    return this.parts.find(p => p.id === partId);
  }

  getJointsForPart(partId) {
    return (this.joints || []).filter(j =>
      (j.sourcePart === partId || j.connectorPartId === partId ||
       j.targetPart === partId || j.receiverPartId === partId)
    );
  }

  getPartsForStep(stepNum) {
    if (stepNum === 0) return this.parts;
    return this.parts.filter(p => p.step <= stepNum);
  }

  getPartsForSheet(sheetNum) {
    return this.parts.filter(p => p.sheet === sheetNum);
  }

  getPartCount() {
    return this.parts.length;
  }
}
