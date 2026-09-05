/**
 * Universal Assembly Step Sequencer
 * Sections 16 & 17 of Master Context: Filters active physical pieces based on progressive build steps.
 */
import { AppState } from '../core/config.js';

export const AssemblySequencer = {
  applyStepFilter(meshMap, parts, activeStep) {
    parts.forEach(part => {
      const group = meshMap.get(part.id);
      if (!group) return;
      group.visible = activeStep === 0 ? true : (part.step <= activeStep);
    });
  },

  nextStep(totalSteps) {
    const { activeStep } = AppState.getState();
    const next = (activeStep + 1) % totalSteps;
    AppState.setState({ activeStep: next });
    return next;
  },

  prevStep(totalSteps) {
    const { activeStep } = AppState.getState();
    const prev = (activeStep - 1 + totalSteps) % totalSteps;
    AppState.setState({ activeStep: prev });
    return prev;
  }
};
