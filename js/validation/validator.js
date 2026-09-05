/**
 * Universal Physical Assembly & Fit Auditor
 * Sections 18, 19, 20, 35 of Master Context: Comprehensive physical feasibility validation.
 */
import { AppState } from '../core/config.js';

export const PhysicalValidator = {
  /**
   * Runs an audit on the given model with the active material configuration.
   */
  auditModel(model, materialThickness) {
    const { kerf, clearance } = AppState.getMaterialProfile();
    const parts = model.parts || [];
    const issues = [];
    let totalMortises = 0;
    let totalConnections = 0;

    parts.forEach(part => {
      const geo = part.generate2D(materialThickness, kerf, clearance);
      const cutouts = geo.cutouts || [];
      totalMortises += cutouts.length;
      totalConnections += (part.connections || []).length;

      // 1. Slot width check
      cutouts.forEach((c, idx) => {
        const slotThickness = Math.min(c.w, c.h);
        const expectedMin = materialThickness;
        const expectedMax = materialThickness + clearance + 0.15;
        if (slotThickness < expectedMin - 0.05) {
          issues.push({
            level: 'ERROR',
            partId: part.id,
            msg: `Mortise slot #${idx + 1} (${slotThickness.toFixed(2)}mm) is narrower than material thickness (${materialThickness}mm) — piece will jam.`
          });
        } else if (slotThickness > expectedMax) {
          issues.push({
            level: 'WARNING',
            partId: part.id,
            msg: `Mortise slot #${idx + 1} (${slotThickness.toFixed(2)}mm) exceeds recommended clearance (${clearance}mm) — loose joint.`
          });
        }
      });

      // 2. Connector target existence check
      (part.connections || []).forEach(targetId => {
        const targetPart = model.getPart(targetId);
        if (!targetPart) {
          issues.push({
            level: 'ERROR',
            partId: part.id,
            msg: `Connection target '${targetId}' does not exist in model parts registry.`
          });
        }
      });

      // 3. Assembly step dependency check
      if (part.step > 1) {
        const hasLowerStepNeighbor = (part.connections || []).some(targetId => {
          const targetPart = model.getPart(targetId);
          return targetPart && targetPart.step < part.step;
        });
        if (!hasLowerStepNeighbor && part.connections && part.connections.length > 0) {
          issues.push({
            level: 'INFO',
            partId: part.id,
            msg: `Part '${part.id}' (Step ${part.step}) has no direct connections to earlier assembly stages.`
          });
        }
      }
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
  }
};
