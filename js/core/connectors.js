/**
 * Universal Connector Standards & Formulas
 * Section 8 & 9 of Master Context: Reusable connector vocabulary & parameterized dimensions.
 */

export const ConnectorStandards = {
  /**
   * Computes slot dimensions based on material thickness and clearance profile.
   */
  calculateSlotDimensions(nominalThickness, clearance = 0.10, kerf = 0.15) {
    return {
      width: nominalThickness + clearance,
      kerfCompensatedWidth: (nominalThickness + clearance) - kerf,
      clearance: clearance,
      kerf: kerf
    };
  },

  /**
   * Universal connector types enum
   */
  Types: {
    TAB: 'TAB',
    SLOT: 'SLOT',
    MORTISE_TENON: 'MORTISE_TENON',
    CROSS_HALVING: 'CROSS_HALVING',
    EDGE_FINGER: 'EDGE_FINGER',
    DOVETAIL_LOCK: 'DOVETAIL_LOCK'
  }
};
