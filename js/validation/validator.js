/**
 * Universal Physical Assembly & Fit Auditor
 * Sections 18, 19, 20, 35 of Master Context: Comprehensive physical feasibility validation.
 * Hard-gate validation enforcing:
 * 1. Dimensional compatibility between mating connectors and receivers.
 * 2. 3D orientation alignment (rejecting 90-degree crossed slots).
 * 3. Edge margin and material space tolerances.
 * 4. Half-lap / cross joint total cut depth verification.
 * 5. 3D spatial collision & unintended solid-body penetration detection.
 */
import { AppState } from '../core/config.js';
import { ConnectorStandards } from '../core/connectors.js';
import { ConstructionObject } from '../models/model-schema.js';

export const PhysicalValidator = {
  /**
   * Runs an authoritative physical feasibility audit on the model.
   *
   * @param {Object} model - ConstructionObject
   * @param {number} materialThickness - Nominal sheet thickness (e.g. 3.0mm)
   * @returns {Object} Audit results with fatal errors, warnings, metrics, and pass/fail state.
   */
  auditModel(rawModel, materialThickness = 3.0) {
    const profile = AppState ? AppState.getMaterialProfile() : { kerf: 0.15, clearance: 0.10 };
    const kerf = profile.kerf !== undefined ? profile.kerf : ConnectorStandards.DEFAULT_KERF;
    const clearance = profile.clearance !== undefined ? profile.clearance : ConnectorStandards.DEFAULT_CLEARANCE;

    // Ensure model is an authoritative ConstructionObject instance with getPart and normalized joints
    const model = (rawModel instanceof ConstructionObject) ? rawModel : new ConstructionObject(rawModel || {});
    const parts = model.parts || [];
    const issues = [];
    let totalMortises = 0;
    let totalConnections = 0;

    // Cache evaluated 2D geometry and 3D world bounding boxes for each part
    const partGeoMap = new Map();
    const partAABBMap = new Map();

    parts.forEach(part => {
      let geo = null;
      if (typeof part.generate2D === 'function') {
        try { geo = part.generate2D(materialThickness, kerf, clearance); } catch (e) {}
      }
      if (!geo && part.geometry && Array.isArray(part.geometry.outline)) {
        geo = part.geometry;
      }
      if (!geo && (part.polygon || part.outline)) {
        geo = {
          outline: part.polygon || part.outline,
          cutouts: part.cutouts || []
        };
      }
      if (!geo) geo = { outline: [], cutouts: [] };

      partGeoMap.set(part.id, geo);
      totalMortises += (geo.cutouts || []).length;
      totalConnections += (part.connections || []).length;

      // Compute 3D world AABB for broad-phase spatial checks
      const aabb = this.computePartWorldAABB(part, geo, materialThickness);
      partAABBMap.set(part.id, aabb);
    });

    // -------------------------------------------------------------
    // CHECK 1: SLOT DIMENSIONS & MINIMUM THICKNESS
    // -------------------------------------------------------------
    parts.forEach(part => {
      const geo = partGeoMap.get(part.id);
      const cutouts = geo.cutouts || [];

      cutouts.forEach((c, idx) => {
        // Skip decorative cutouts and arched windows/doors (architectural openings, not mortise slots)
        if (c.arched || c.type === 'decorative' || Math.min(c.w, c.h) > 6.0) return;

        const slotThickness = Math.min(c.w, c.h);
        const slotLength = Math.max(c.w, c.h);
        const expectedMin = materialThickness + clearance - 0.05;
        const expectedMax = materialThickness + clearance + 0.25;

        if (slotThickness < materialThickness - 0.05) {
          issues.push({
            level: 'ERROR',
            code: 'SLOT_TOO_NARROW',
            partId: part.id,
            msg: `Part '${part.id}' cutout #${idx + 1} thickness (${slotThickness.toFixed(2)}mm) is narrower than material thickness (${materialThickness}mm) — piece will jam.`
          });
        } else if (slotThickness > expectedMax) {
          issues.push({
            level: 'WARNING',
            code: 'SLOT_TOO_LOOSE',
            partId: part.id,
            msg: `Part '${part.id}' cutout #${idx + 1} thickness (${slotThickness.toFixed(2)}mm) exceeds recommended clearance (${clearance}mm) — loose joint.`
          });
        }
      });
    });

    // -------------------------------------------------------------
    // CHECK 2: EDGE MARGINS & MATERIAL SPACE (HARMONIZED)
    // -------------------------------------------------------------
    parts.forEach(part => {
      const geo = partGeoMap.get(part.id);
      if (geo.outline && geo.outline.length >= 3 && geo.cutouts && geo.cutouts.length > 0) {
        // Test fatal edge margin threshold (scaled for thin materials <= 1.5mm)
        const fatalMarginLimit = Math.min(ConnectorStandards.FATAL_MIN_EDGE_MARGIN || 1.5, materialThickness);
        const fatalMarginIssues = ConnectorStandards.checkCutoutEdgeMargins(
          geo.outline,
          geo.cutouts,
          fatalMarginLimit
        );

        fatalMarginIssues.forEach(m => {
          issues.push({
            level: 'ERROR',
            code: 'INSUFFICIENT_EDGE_MARGIN',
            partId: part.id,
            msg: `Part '${part.id}' cutout #${m.cutoutIndex + 1} is too close to the outer edge (${m.minDistance.toFixed(2)}mm < ${m.requiredMargin}mm fatal margin). Wood will fracture under insertion force.`
          });
        });

        // Test recommended edge margin threshold (3.0mm) for warnings
        const recMarginIssues = ConnectorStandards.checkCutoutEdgeMargins(
          geo.outline,
          geo.cutouts,
          ConnectorStandards.RECOMMENDED_EDGE_MARGIN || 3.0
        );
        recMarginIssues.forEach(m => {
          if (m.minDistance >= fatalMarginLimit) {
            issues.push({
              level: 'WARNING',
              code: 'SUBOPTIMAL_EDGE_MARGIN',
              partId: part.id,
              msg: `Part '${part.id}' cutout #${m.cutoutIndex + 1} has narrow edge margin (${m.minDistance.toFixed(2)}mm < ${m.requiredMargin}mm recommended). Consider increasing margin.`
            });
          }
        });

        // Check distance between adjacent cutouts on the same part
        for (let i = 0; i < geo.cutouts.length; i++) {
          for (let j = i + 1; j < geo.cutouts.length; j++) {
            const c1 = geo.cutouts[i];
            const c2 = geo.cutouts[j];
            const dx = Math.abs(c1.x - c2.x) - (c1.w + c2.w) / 2;
            const dy = Math.abs(c1.y - c2.y) - (c1.h + c2.h) / 2;
            const dist = Math.max(dx, dy);

            const fatalSpacing = ConnectorStandards.FATAL_MIN_SLOT_SPACING || 1.0;
            const recSpacing = ConnectorStandards.RECOMMENDED_SLOT_SPACING || 2.0;

            if (dist < fatalSpacing - 0.05) {
              issues.push({
                level: 'ERROR',
                code: 'CUTOUT_SPACING_TOO_CLOSE',
                partId: part.id,
                msg: `Part '${part.id}' cutouts #${i + 1} and #${j + 1} have insufficient spacing (${dist.toFixed(2)}mm < ${fatalSpacing}mm fatal spacing). Wooden bridge will snap.`
              });
            } else if (dist < recSpacing - 0.05) {
              issues.push({
                level: 'WARNING',
                code: 'SUBOPTIMAL_CUTOUT_SPACING',
                partId: part.id,
                msg: `Part '${part.id}' cutouts #${i + 1} and #${j + 1} have tight spacing (${dist.toFixed(2)}mm < ${recSpacing}mm recommended).`
              });
            }
          }
        }
      }
    });

    // -------------------------------------------------------------
    // CHECK 3: CONNECTION TARGET EXISTENCE & STEP REACHABILITY
    // -------------------------------------------------------------
    parts.forEach(part => {
      (part.connections || []).forEach(conn => {
        const targetId = typeof conn === 'string' ? conn : (conn.partId || conn.targetPartId);
        const targetPart = model.getPart(targetId);
        if (!targetPart) {
          issues.push({
            level: 'ERROR',
            code: 'UNKNOWN_CONNECTION_TARGET',
            partId: part.id,
            msg: `Part '${part.id}' lists connection target '${targetId}', which does not exist in the model registry.`
          });
        }
      });

      if (part.step > 1) {
        const hasLowerStepNeighbor = (part.connections || []).some(conn => {
          const targetId = typeof conn === 'string' ? conn : (conn.partId || conn.targetPartId);
          const targetPart = model.getPart(targetId);
          return targetPart && targetPart.step < part.step;
        });
        if (!hasLowerStepNeighbor && part.connections && part.connections.length > 0) {
          issues.push({
            level: 'INFO',
            code: 'STAGE_REACHABILITY',
            partId: part.id,
            msg: `Part '${part.id}' (Step ${part.step}) has no direct connections to earlier assembly stages.`
          });
        }
      }
    });

    // -------------------------------------------------------------
    // CHECK 4: EXPLICIT & DERIVED JOINT DIMENSIONAL & ORIENTATION FIT
    // -------------------------------------------------------------
    const evaluatedJoints = this.extractAndValidateJoints(model, partGeoMap, partAABBMap, materialThickness, clearance);
    evaluatedJoints.forEach(jIssue => {
      issues.push(jIssue);
    });

    // -------------------------------------------------------------
    // CHECK 5: 3D SPATIAL COLLISION & UNINTENDED PENETRATIONS
    // -------------------------------------------------------------
    const collisionIssues = this.audit3DSpatialCollisions(model, partGeoMap, partAABBMap, materialThickness);
    collisionIssues.forEach(cIssue => {
      issues.push(cIssue);
    });

    const errorCount = issues.filter(i => i.level === 'ERROR').length;
    const warningCount = issues.filter(i => i.level === 'WARNING').length;
    const isPassing = errorCount === 0;

    return {
      isPassing,
      errorCount,
      warningCount,
      totalParts: parts.length,
      totalMortises,
      totalConnections,
      issues,
      auditTimestamp: new Date().toLocaleTimeString()
    };
  },

  /**
   * Helper to retrieve parametric assembled position at given thickness.
   */
  getPartPos(part, thickness = 3.0) {
    if (typeof part.getAssembledPos === 'function') return part.getAssembledPos(thickness);
    if (typeof part.assembledPos === 'function') return part.assembledPos(thickness);
    return part.assembledPos || [0, 0, 0];
  },

  /**
   * Helper to retrieve parametric assembled rotation at given thickness.
   */
  getPartRot(part, thickness = 3.0) {
    if (typeof part.getAssembledRot === 'function') return part.getAssembledRot(thickness);
    if (typeof part.assembledRot === 'function') return part.assembledRot(thickness);
    return part.assembledRot || [0, 0, 0];
  },

  /**
   * Computes the 3D Axis-Aligned Bounding Box (AABB) in world space for a part.
   */
  computePartWorldAABB(part, geo, thickness) {
    const pos = this.getPartPos(part, thickness);
    const rot = this.getPartRot(part, thickness);
    const outline = geo.outline || [];
    if (outline.length === 0) {
      const hw = (part.width || 40) / 2;
      const hl = (part.length || 40) / 2;
      return {
        min: [pos[0] - hw, pos[1] - hl, pos[2] - thickness / 2],
        max: [pos[0] + hw, pos[1] + hl, pos[2] + thickness / 2]
      };
    }

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    outline.forEach(pt => {
      if (pt[0] < minX) minX = pt[0];
      if (pt[0] > maxX) maxX = pt[0];
      if (pt[1] < minY) minY = pt[1];
      if (pt[1] > maxY) maxY = pt[1];
    });

    const halfT = thickness / 2;
    // 8 local bounding box corners
    const localCorners = [
      [minX, minY, -halfT], [maxX, minY, -halfT],
      [maxX, maxY, -halfT], [minX, maxY, -halfT],
      [minX, minY, halfT],  [maxX, minY, halfT],
      [maxX, maxY, halfT],  [minX, maxY, halfT]
    ];

    let wMinX = Infinity, wMaxX = -Infinity;
    let wMinY = Infinity, wMaxY = -Infinity;
    let wMinZ = Infinity, wMaxZ = -Infinity;

    localCorners.forEach(corner => {
      const w = ConnectorStandards.local2DToWorld(
        [corner[0], corner[1]],
        pos,
        rot,
        corner[2]
      );
      if (w[0] < wMinX) wMinX = w[0];
      if (w[0] > wMaxX) wMaxX = w[0];
      if (w[1] < wMinY) wMinY = w[1];
      if (w[1] > wMaxY) wMaxY = w[1];
      if (w[2] < wMinZ) wMinZ = w[2];
      if (w[2] > wMaxZ) wMaxZ = w[2];
    });

    return {
      min: [wMinX, wMinY, wMinZ],
      max: [wMaxX, wMaxY, wMaxZ],
      size: [wMaxX - wMinX, wMaxY - wMinY, wMaxZ - wMinZ],
      center: [(wMinX + wMaxX) / 2, (wMinY + wMaxY) / 2, (wMinZ + wMaxZ) / 2]
    };
  },

  /**
   * Extracts and validates all joints between parts:
   * 1. Checks explicit model.joints if defined: enforces Single Source of Truth.
   * 2. Inspects mating connections and verifies tab width <= slot length,
   *    tab depth <= receiver space, and 3D world orientation compatibility.
   */
  extractAndValidateJoints(model, partGeoMap, partAABBMap, thickness, clearance) {
    const issues = [];
    const parts = model.parts || [];

    // Process explicit joints if provided on model
    if (Array.isArray(model.joints) && model.joints.length > 0) {
      model.joints.forEach(joint => {
        const sourceId = joint.sourcePart || joint.connectorPartId;
        const targetId = joint.targetPart || joint.receiverPartId;
        const connPart = model.getPart(sourceId);
        const recvPart = model.getPart(targetId);

        if (!connPart || !recvPart) {
          issues.push({
            level: 'ERROR',
            code: 'INVALID_JOINT_DEFINITION',
            partId: sourceId || 'unknown',
            msg: `Joint '${joint.id}' references non-existent parts ('${sourceId}' -> '${targetId}').`
          });
          return;
        }

        // 1. Orientation check
        if (joint.type !== 'contact' && joint.type !== 'surface-contact' && joint.type !== 'edge-finger' && joint.type !== 'valley-abut' && joint.type !== 'box-joint') {
          const orient = ConnectorStandards.calculateJointOrientation(connPart, recvPart, joint);
          if (orient.isPerpendicular) {
            issues.push({
              level: 'ERROR',
              code: 'JOINT_ORIENTATION_MISMATCH',
              partId: connPart.id,
              msg: `Joint '${joint.id}' between '${connPart.id}' and '${recvPart.id}' has a 90-degree orientation mismatch in 3D space. Tab width does not align with slot length.`
            });
          }
        }

        // 2. SSOT & Receiver derivation check (Requirement 1 & 3)
        const expectedSlot = ConnectorStandards.deriveReceiverSlot(joint, thickness, clearance);
        const geoRecv = partGeoMap.get(recvPart.id);
        const cutouts = geoRecv?.cutouts || [];

        if (joint.type !== 'edge-finger' && joint.type !== 'box-joint' && joint.type !== 'contact' && joint.type !== 'surface-contact' && joint.type !== 'valley-abut') {
          // Check that target part contains the derived cutout
          const matchingCutout = cutouts.find(c =>
            c.jointId === joint.id ||
            (Math.abs(c.x - expectedSlot.x) < 0.5 && Math.abs(c.y - expectedSlot.y) < 0.5)
          );

          if (!matchingCutout) {
            issues.push({
              level: 'ERROR',
              code: 'JOINT_GEOMETRY_NOT_DERIVED',
              partId: recvPart.id,
              msg: `Joint '${joint.id}': Receiver part '${recvPart.id}' does not derive its receiver slot from the Joint definition at [${expectedSlot.x}, ${expectedSlot.y}].`
            });
          } else {
            // Verify cutout dimensions match derived dimensions
            const dw = Math.abs(matchingCutout.w - expectedSlot.w);
            const dh = Math.abs(matchingCutout.h - expectedSlot.h);
            if (dw > 0.15 || dh > 0.15) {
              issues.push({
                level: 'ERROR',
                code: 'JOINT_GEOMETRY_NOT_DERIVED',
                partId: recvPart.id,
                msg: `Joint '${joint.id}': Cutout on '${recvPart.id}' (${matchingCutout.w.toFixed(2)}x${matchingCutout.h.toFixed(2)}mm) does not match derived dimensions from joint connector (${expectedSlot.w.toFixed(2)}x${expectedSlot.h.toFixed(2)}mm). Dimensions must be derived from Joint.`
              });
            }
          }
        }

        // 3. Dimensional compatibility check
        const tabW = joint.sourceConnector?.width || joint.tabWidth || joint.width || 20;
        const slotL = expectedSlot.lengthAxis === 'Y' ? expectedSlot.h : expectedSlot.w;

        if (slotL < tabW - 0.05) {
          issues.push({
            level: 'ERROR',
            code: 'JOINT_DIMENSIONAL_MISMATCH',
            partId: connPart.id,
            msg: `Joint '${joint.id}': Connector width (${tabW}mm) exceeds receiver slot length (${slotL}mm).`
          });
        }
      });
    }

    // Inspect pairs of parts with connection declarations (fallback when model.joints is not explicitly declared)
    if (!Array.isArray(model.joints) || model.joints.length === 0) {
      parts.forEach(partA => {
        const connList = partA.connections || [];
        connList.forEach(conn => {
          const targetId = typeof conn === 'string' ? conn : (conn.partId || conn.targetPartId);
          const partB = model.getPart(targetId);
          if (!partB) return;

          const posA = this.getPartPos(partA, thickness);
          const rotA = this.getPartRot(partA, thickness);
          const posB = this.getPartPos(partB, thickness);
          const rotB = this.getPartRot(partB, thickness);

          // Extract tabs on partA and slots on partB
          const tabsA = this.detectTabsInOutline(partGeoMap.get(partA.id)?.outline, thickness);
          const slotsB = partGeoMap.get(partB.id)?.cutouts || [];

          // For each tab on partA, check if a matching slot exists on partB
          tabsA.forEach((tab, tIdx) => {
            // Compute world position and direction of this tab
            const tabWorldPos = ConnectorStandards.local2DToWorld(
              tab.center2D,
              posA,
              rotA
            );
            const localAxisVec = tab.axis === 'Y' ? [0, 1, 0] : [1, 0, 0];
            const tabWorldDir = ConnectorStandards.rotateVector(localAxisVec, rotA);

            // Find candidate slots in partB located near this tab in world coordinates
            let foundMatchingSlot = false;
            let bestDistance = Infinity;
            let candidateSlot = null;

            slotsB.forEach(slot => {
              const slotWorldPos = ConnectorStandards.local2DToWorld(
                [slot.x, slot.y],
                posB,
                rotB
              );

              const dx = slotWorldPos[0] - tabWorldPos[0];
              const dy = slotWorldPos[1] - tabWorldPos[1];
              const dz = slotWorldPos[2] - tabWorldPos[2];
              const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

              if (dist < bestDistance) {
                bestDistance = dist;
                candidateSlot = slot;
              }
            });

            // Check if partB has alternating edge finger tabs (box joint / roof ridge)
            const tabsB = this.detectTabsInOutline(partGeoMap.get(partB.id)?.outline, thickness);
            const isEdgeFingerMating = tabsB.length > 0 && tabsB.some(tabB => {
              const tabBWorldPos = ConnectorStandards.local2DToWorld(tabB.center2D, posB, rotB);
              const dX = tabBWorldPos[0] - tabWorldPos[0];
              const dY = tabBWorldPos[1] - tabWorldPos[1];
              const dZ = tabBWorldPos[2] - tabWorldPos[2];
              return Math.sqrt(dX * dX + dY * dY + dZ * dZ) < 35.0;
            });

            if (isEdgeFingerMating) {
              foundMatchingSlot = true;
            }

            // If the tab is positioned close to partB (within 15mm world proximity)
            if (bestDistance < 15.0 && candidateSlot) {
              foundMatchingSlot = true;
              const slotLengthAxis = candidateSlot.w >= candidateSlot.h ? 'X' : 'Y';
              const slotLength = Math.max(candidateSlot.w, candidateSlot.h);

              // 1. Dimensional check: slot length must accommodate tab width
              if (tab.width > slotLength + 0.15) {
                issues.push({
                  level: 'ERROR',
                  code: 'CONNECTOR_EXCEEDS_RECEIVER',
                  partId: partA.id,
                  msg: `Tab on '${partA.id}' (width ${tab.width.toFixed(1)}mm) is wider than receiver slot (${slotLength.toFixed(1)}mm) on '${partB.id}'. Piece cannot fit physically.`
                });
              }

              // 2. Orientation check: tab world width vector must align with slot length world vector
              const slotLocalVec = slotLengthAxis === 'Y' ? [0, 1, 0] : [1, 0, 0];
              const slotWorldDir = ConnectorStandards.rotateVector(slotLocalVec, rotB);

              const dot = Math.abs(
                tabWorldDir[0] * slotWorldDir[0] +
                tabWorldDir[1] * slotWorldDir[1] +
                tabWorldDir[2] * slotWorldDir[2]
              );

              if (dot < 0.25) {
                issues.push({
                  level: 'ERROR',
                  code: 'ORIENTATION_MISMATCH_90_DEG',
                  partId: partA.id,
                  msg: `Connector on '${partA.id}' and receiver slot on '${partB.id}' are oriented at 90 degrees to each other in 3D world space (tab width does not align with slot length). Physical assembly is impossible.`
                });
              }
            } else if (!foundMatchingSlot) {
              // Tab is positioned against partB, but no receiver slot or edge finger exists to accept it
              const aabbB = partAABBMap.get(partB.id);
              if (aabbB) {
                const nearB = tabWorldPos[0] >= aabbB.min[0] - 10 && tabWorldPos[0] <= aabbB.max[0] + 10 &&
                              tabWorldPos[1] >= aabbB.min[1] - 10 && tabWorldPos[1] <= aabbB.max[1] + 10 &&
                              tabWorldPos[2] >= aabbB.min[2] - 10 && tabWorldPos[2] <= aabbB.max[2] + 10;
                if (nearB) {
                  issues.push({
                    level: 'ERROR',
                    code: 'MISSING_RECEIVER',
                    partId: partA.id,
                    msg: `Connector tab on '${partA.id}' (width ${tab.width.toFixed(1)}mm) connects to '${partB.id}', but '${partB.id}' has no matching receiver slot to accept it.`
                  });
                }
              }
            }
          });
        });
      });
    }

    return issues;
  },

  /**
   * Detects tenon tabs protruding outward from an outline polygon.
   */
  detectTabsInOutline(outline, thickness) {
    const tabs = [];
    if (!outline || outline.length < 5) return tabs;

    // Centroid of outline polygon to distinguish outward tabs from inward notches/recesses
    let cx = 0, cy = 0;
    for (const p of outline) { cx += p[0]; cy += p[1]; }
    cx /= outline.length;
    cy /= outline.length;

    // Look for 4 points forming a rectangular tab protruding from and returning to a baseline:
    // p1 (baseline) -> p2 (tab corner) -> p3 (tab corner) -> p4 (baseline)
    for (let i = 0; i < outline.length; i++) {
      const p1 = outline[i];
      const p2 = outline[(i + 1) % outline.length];
      const p3 = outline[(i + 2) % outline.length];
      const p4 = outline[(i + 3) % outline.length];

      // Tab protruding along Y (baseline is along X: p1.y == p4.y, p2.y == p3.y)
      const minTabDepth = Math.min(0.7, thickness * 0.7);
      const isYTab = Math.abs(p1[1] - p4[1]) < 0.05 &&
                     Math.abs(p2[1] - p3[1]) < 0.05 &&
                     Math.abs(p1[0] - p2[0]) < 0.05 &&
                     Math.abs(p3[0] - p4[0]) < 0.05 &&
                     Math.abs(p2[1] - p1[1]) >= minTabDepth &&
                     Math.abs(p2[1] - cy) > Math.abs(p1[1] - cy); // Must protrude outward away from center

      if (isYTab) {
        const tabWidth = Math.abs(p3[0] - p2[0]);
        const tabDepth = Math.abs(p2[1] - p1[1]);
        const maxDepth = Math.max(thickness * 2.5, 10.0);
        if (tabWidth >= 5.0 && tabDepth <= maxDepth) {
          tabs.push({
            width: tabWidth,
            depth: tabDepth,
            axis: 'X',
            center2D: [(p2[0] + p3[0]) / 2, (p1[1] + p2[1]) / 2]
          });
        }
      }

      // Tab protruding along X (baseline is along Y: p1.x == p4.x, p2.x == p3.x)
      const isXTab = Math.abs(p1[0] - p4[0]) < 0.05 &&
                     Math.abs(p2[0] - p3[0]) < 0.05 &&
                     Math.abs(p1[1] - p2[1]) < 0.05 &&
                     Math.abs(p3[1] - p4[1]) < 0.05 &&
                     Math.abs(p2[0] - p1[0]) >= minTabDepth &&
                     Math.abs(p2[0] - cx) > Math.abs(p1[0] - cx); // Must protrude outward away from center

      if (isXTab) {
        const tabWidth = Math.abs(p3[1] - p2[1]);
        const tabDepth = Math.abs(p2[0] - p1[0]);
        const maxDepth = Math.max(thickness * 2.5, 10.0);
        if (tabWidth >= 5.0 && tabDepth <= maxDepth) {
          tabs.push({
            width: tabWidth,
            depth: tabDepth,
            axis: 'Y',
            center2D: [(p1[0] + p2[0]) / 2, (p2[1] + p3[1]) / 2]
          });
        }
      }
    }

    return tabs;
  },

  /**
   * Audits 3D spatial collisions and unintended solid-body penetrations.
   * Employs AABB broad-phase followed by 3D OBB Separating Axis Theorem (SAT) narrow-phase.
   * Enforces joint-localized collision exemptions (Requirement 4 & 5).
   */
  audit3DSpatialCollisions(model, partGeoMap, partAABBMap, thickness) {
    const issues = [];
    const parts = model.parts || [];

    // Precompute 3D OBB for each part
    const partOBBMap = new Map();
    parts.forEach(part => {
      const geo = partGeoMap.get(part.id);
      partOBBMap.set(part.id, ConnectorStandards.computePartOBB(part, geo, thickness));
    });

    for (let i = 0; i < parts.length; i++) {
      for (let j = i + 1; j < parts.length; j++) {
        const partA = parts[i];
        const partB = parts[j];

        const aabbA = partAABBMap.get(partA.id);
        const aabbB = partAABBMap.get(partB.id);
        if (!aabbA || !aabbB) continue;

        // Broad phase: Check AABB overlap
        const overlapX = Math.min(aabbA.max[0], aabbB.max[0]) - Math.max(aabbA.min[0], aabbB.min[0]);
        const overlapY = Math.min(aabbA.max[1], aabbB.max[1]) - Math.max(aabbA.min[1], aabbB.min[1]);
        const overlapZ = Math.min(aabbA.max[2], aabbB.max[2]) - Math.max(aabbA.min[2], aabbB.min[2]);

        // If no overlap in any axis, no collision (broad-phase cull)
        if (overlapX <= 0.05 || overlapY <= 0.05 || overlapZ <= 0.05) {
          continue;
        }

        // Narrow phase: 3D Oriented Bounding Box Separating Axis Theorem (SAT)
        const obbA = partOBBMap.get(partA.id);
        const obbB = partOBBMap.get(partB.id);
        const sat = ConnectorStandards.testOBBOverlap(obbA, obbB);

        // If SAT proves separation (e.g. rotated roofs with overlapping AABBs but separated solids), PASS!
        if (!sat.intersects) {
          continue;
        }

        // Calculate overlapping volume in mm^3 using narrow-phase penetration depth
        const contactLength = Math.max(overlapX, Math.max(overlapY, overlapZ));
        const penDepth = (typeof sat.minOverlap === 'number' && sat.minOverlap > 0) ? sat.minOverlap : Math.min(overlapX, Math.min(overlapY, overlapZ));
        const physicalOverlapVol = contactLength * thickness * Math.min(thickness * 1.5, penDepth);
        const overlapVolume = Math.min(overlapX * overlapY * overlapZ, physicalOverlapVol);

        const intersectionCenter = [
          (Math.max(aabbA.min[0], aabbB.min[0]) + Math.min(aabbA.max[0], aabbB.max[0])) / 2,
          (Math.max(aabbA.min[1], aabbB.min[1]) + Math.min(aabbA.max[1], aabbB.max[1])) / 2,
          (Math.max(aabbA.min[2], aabbB.min[2]) + Math.min(aabbA.max[2], aabbB.max[2])) / 2
        ];

        // Check if one part is nested inside an architectural cutout of the other (e.g. door in doorway)
        const isNestedInCutout = (containerPart, nestedPart) => {
          const geoC = partGeoMap.get(containerPart.id);
          const geoN = partGeoMap.get(nestedPart.id);
          if (!geoC || !geoC.cutouts || geoC.cutouts.length === 0) return false;
          
          let nW = nestedPart.width || 0;
          let nL = nestedPart.length || 0;
          if ((!nW || !nL) && geoN && geoN.outline && geoN.outline.length > 0) {
            let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
            geoN.outline.forEach(p => {
              if (p[0] < minX) minX = p[0];
              if (p[0] > maxX) maxX = p[0];
              if (p[1] < minY) minY = p[1];
              if (p[1] > maxY) maxY = p[1];
            });
            nW = maxX - minX;
            nL = maxY - minY;
          }

          const posC = this.getPartPos(containerPart, thickness);
          const rotC = this.getPartRot(containerPart, thickness);
          const posN = this.getPartPos(nestedPart, thickness);
          return geoC.cutouts.some(c => {
            // Only large architectural openings (arched, doorway, or min dimension > 6.0mm)
            if (!c.arched && Math.min(c.w, c.h) <= 6.0) return false;
            const cWorld = ConnectorStandards.local2DToWorld([c.x, c.y], posC, rotC);
            const dx = Math.abs(cWorld[0] - posN[0]);
            const dy = Math.abs(cWorld[1] - posN[1]);
            const dz = Math.abs(cWorld[2] - posN[2]);
            const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
            return dist < Math.max(c.w, c.h) / 2 && 
                   Math.min(nW, nL) <= Math.min(c.w, c.h) + 1.0 && 
                   Math.max(nW, nL) <= Math.max(c.w, c.h) + 1.0;
          });
        };

        if (isNestedInCutout(partA, partB) || isNestedInCutout(partB, partA)) {
          continue;
        }

        // Check if partA and partB have an intended connection
        const hasConnection = (partA.connections || []).some(c => (typeof c === 'string' ? c : (c.partId || c.targetPartId)) === partB.id) ||
                              (partB.connections || []).some(c => (typeof c === 'string' ? c : (c.partId || c.targetPartId)) === partA.id) ||
                              (model.joints || []).some(j =>
                                (j.sourcePart === partA.id && j.targetPart === partB.id) ||
                                (j.sourcePart === partB.id && j.targetPart === partA.id) ||
                                (j.connectorPartId === partA.id && j.receiverPartId === partB.id) ||
                                (j.connectorPartId === partB.id && j.receiverPartId === partA.id)
                              );

        if (hasConnection) {
          // Check for half-lap / cross-halving collision (crossing longitudinal spine and transverse bulkhead)
          const isCrossingSpineBulkhead =
            (partA.name?.toLowerCase().includes('spine') && partB.name?.toLowerCase().includes('bulkhead')) ||
            (partB.name?.toLowerCase().includes('spine') && partA.name?.toLowerCase().includes('bulkhead'));

          if (isCrossingSpineBulkhead) {
            const geoA = partGeoMap.get(partA.id);
            const geoB = partGeoMap.get(partB.id);
            const cutoutsA = geoA?.cutouts || [];
            const cutoutsB = geoB?.cutouts || [];
            const totalCutDepth = (cutoutsA[0]?.h || 0) + (cutoutsB[0]?.h || 0);
            if (totalCutDepth > 0 && totalCutDepth < overlapY - 0.2) {
              issues.push({
                level: 'ERROR',
                code: 'HALF_LAP_INSUFFICIENT_DEPTH',
                partId: partA.id,
                msg: `Half-lap joint between '${partA.id}' and '${partB.id}' has insufficient total cut depth (${totalCutDepth.toFixed(1)}mm < ${overlapY.toFixed(1)}mm overlap height). Solid wood collides around World [${intersectionCenter.map(v => v.toFixed(1)).join(', ')}].`
              });
              continue;
            }
          }

          // LOCALIZED JOINT COLLISION EXEMPTION (Requirement 4)
          // Find all declared joints between partA and partB
          const relevantJoints = (model.joints || []).filter(j => 
            (j.sourcePart === partA.id && j.targetPart === partB.id) ||
            (j.sourcePart === partB.id && j.targetPart === partA.id) ||
            (j.connectorPartId === partA.id && j.receiverPartId === partB.id) ||
            (j.connectorPartId === partB.id && j.receiverPartId === partA.id)
          );

          const jointLoci = [];
          relevantJoints.forEach(j => {
            if (j.worldPos) {
              jointLoci.push(j.worldPos);
            } else if (j.position) {
              const targetP = (j.targetPart === partB.id || j.receiverPartId === partB.id) ? partB : partA;
              jointLoci.push(ConnectorStandards.local2DToWorld(
                j.position,
                this.getPartPos(targetP, thickness),
                this.getPartRot(targetP, thickness)
              ));
            }
          });

          // Fallback: If no explicit joints declared, include detected tabs and cutouts
          if (relevantJoints.length === 0) {
            const tabsA = this.detectTabsInOutline(partGeoMap.get(partA.id)?.outline, thickness);
            tabsA.forEach(t => {
              jointLoci.push(ConnectorStandards.local2DToWorld(t.center2D, this.getPartPos(partA, thickness), this.getPartRot(partA, thickness)));
            });
            const tabsB = this.detectTabsInOutline(partGeoMap.get(partB.id)?.outline, thickness);
            tabsB.forEach(t => {
              jointLoci.push(ConnectorStandards.local2DToWorld(t.center2D, this.getPartPos(partB, thickness), this.getPartRot(partB, thickness)));
            });
            (partGeoMap.get(partA.id)?.cutouts || []).forEach(c => {
              jointLoci.push(ConnectorStandards.local2DToWorld([c.x, c.y], this.getPartPos(partA, thickness), this.getPartRot(partA, thickness)));
            });
            (partGeoMap.get(partB.id)?.cutouts || []).forEach(c => {
              jointLoci.push(ConnectorStandards.local2DToWorld([c.x, c.y], this.getPartPos(partB, thickness), this.getPartRot(partB, thickness)));
            });
          }

          // Determine allowable locus radius: strictly localized to joint mating region (Requirement 4)
          const isContactJoint = relevantJoints.some(j =>
            j.type === 'contact' || j.type === 'surface-contact' ||
            j.connectionType === 'roof-ridge' || j.connectionType === 'roof-gable' ||
            j.connectionType === 'ridge-cap' || j.type === 'valley-abut' || j.connectionType === 'valley-abut' ||
            j.type === 'edge-finger'
          );

          // Compute distance from intersection center to nearest joint locus
          let minDistanceToJoint = Infinity;
          if (jointLoci.length === 0 && isContactJoint) {
            minDistanceToJoint = 0;
          } else {
            jointLoci.forEach(locus => {
              const dx = locus[0] - intersectionCenter[0];
              const dy = locus[1] - intersectionCenter[1];
              const dz = locus[2] - intersectionCenter[2];
              const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
              if (dist < minDistanceToJoint) minDistanceToJoint = dist;
            });
          }

          let allowableLocusDist = 30.0;
          if (isContactJoint) {
            allowableLocusDist = Math.max(45.0, (overlapX + overlapY + overlapZ) / 2 + 10.0);
          } else if (relevantJoints.length > 0) {
            let maxW = 20;
            relevantJoints.forEach(j => {
              const w = j.sourceConnector?.width || j.tabWidth || j.width || 20;
              if (w > maxW) maxW = w;
            });
            allowableLocusDist = Math.max(30.0, maxW / 2 + 12.0);
          } else {
            allowableLocusDist = Math.max(30.0, (overlapX + overlapY + overlapZ) / 2);
          }

          // If intersection is far away from the joint locus, it is an illegal collision outside the joint!
          if (minDistanceToJoint > allowableLocusDist) {
            issues.push({
              level: 'ERROR',
              code: 'COLLISION_OUTSIDE_JOINT_LOCUS',
              partId: partA.id,
              msg: `UNINTENDED SOLID PENETRATION OUTSIDE JOINT LOCUS: Connected parts '${partA.id}' and '${partB.id}' collide (${overlapVolume.toFixed(0)}mm³) at World [${intersectionCenter.map(v => v.toFixed(1)).join(', ')}], which is ${minDistanceToJoint.toFixed(1)}mm away from the nearest joint locus.`
            });
            continue;
          }

          // In an intended joint locus, penetration is allowed up to the tenon tab volume (including shoulder footprint)
          const detectedTabs = (relevantJoints.length === 0) ? [
            ...this.detectTabsInOutline(partGeoMap.get(partA.id)?.outline, thickness),
            ...this.detectTabsInOutline(partGeoMap.get(partB.id)?.outline, thickness)
          ] : [];
          const hasTabsOrJoints = relevantJoints.length > 0 || detectedTabs.length > 0;

          let allowedJointVolume = 0;
          if (relevantJoints.length > 0) {
            relevantJoints.forEach(j => {
              const w = j.sourceConnector?.width || j.tabWidth || j.width || 25;
              const d = typeof j.tabDepth === 'function' ? j.tabDepth(thickness) : (j.sourceConnector?.depth || j.tabDepth || thickness);
              allowedJointVolume += w * d * (thickness * 1.5);
            });
            if (relevantJoints.some(j => j.type === 'edge-finger' || j.type === 'valley-abut' || j.type === 'roof-ridge' || j.type === 'contact')) {
              allowedJointVolume = Math.max(allowedJointVolume, contactLength * thickness * (thickness * 1.5));
            }
          } else {
            const cutoutsA = (partGeoMap.get(partA.id)?.cutouts || []).filter(c => !c.arched && Math.min(c.w, c.h) <= 6.0);
            const cutoutsB = (partGeoMap.get(partB.id)?.cutouts || []).filter(c => !c.arched && Math.min(c.w, c.h) <= 6.0);
            const matchingCutouts = [...cutoutsA, ...cutoutsB];
            if (matchingCutouts.length > 0) {
              matchingCutouts.forEach(c => {
                allowedJointVolume += Math.max(c.w, c.h) * thickness * (thickness * 1.5);
              });
            } else {
              allowedJointVolume = 45 * thickness * (thickness + 0.5);
            }
          }

          if (hasTabsOrJoints) {
            const maxPartDim = Math.max(partA.width || 40, partA.length || 40, partB.width || 40, partB.length || 40);
            const tabAllowance = Math.min(contactLength, maxPartDim) * thickness * (thickness + 0.8);
            allowedJointVolume = Math.max(allowedJointVolume, tabAllowance);
          }

          const maxAllowableTabVol = Math.max(45 * thickness * (thickness + 0.5), allowedJointVolume);
          if (overlapVolume > maxAllowableTabVol) {
            issues.push({
              level: 'ERROR',
              code: 'EXCESSIVE_SOLID_PENETRATION',
              partId: partA.id,
              msg: `EXCESSIVE SOLID PENETRATION IN JOINT: '${partA.id}' and '${partB.id}' have excessive solid volume overlap (${overlapVolume.toFixed(0)}mm³) around World [${intersectionCenter.map(v => v.toFixed(1)).join(', ')}].`
            });
          }
        } else {
          // Unrelated parts with volume intersection
          if (overlapVolume > 18.0) {
            issues.push({
              level: 'ERROR',
              code: 'UNRELATED_PARTS_COLLISION',
              partId: partA.id,
              msg: `UNINTENDED SOLID-BODY COLLISION: Unrelated components '${partA.id}' and '${partB.id}' occupy the same space (${overlapVolume.toFixed(0)}mm³ overlap) around World [${intersectionCenter.map(v => v.toFixed(1)).join(', ')}].`
            });
          }
        }
      }
    }

    return issues;
  }
};

