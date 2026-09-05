/**
 * Universal Configuration & State Manager
 * Centralizes material properties, kerf, clearance, and active application state.
 */

export const MATERIAL_PROFILES = {
  '2.0': { name: '2.0 mm (Heavy Cardstock)', thickness: 2.0, kerf: 0.12, clearance: 0.08, color: '#f59e0b' },
  '3.0': { name: '3.0 mm (MDF / Laser Plywood)', thickness: 3.0, kerf: 0.15, clearance: 0.10, color: '#d97706' },
  '4.0': { name: '4.0 mm (Corrugated Board)', thickness: 4.0, kerf: 0.18, clearance: 0.15, color: '#b45309' }
};

class AppStateManager {
  constructor() {
    this.listeners = new Set();
    
    // Parse URL params or fallback
    const urlParams = new URLSearchParams(window.location.search);
    const savedModel = localStorage.getItem('PUZZLE_ACTIVE_MODEL') || 'football-stadium';
    const savedThickness = localStorage.getItem('PUZZLE_THICKNESS') || '3.0';

    this.state = {
      activeModelId: urlParams.get('model') || savedModel,
      selectedPartId: urlParams.get('part') || null,
      materialThickness: parseFloat(urlParams.get('thickness') || savedThickness),
      explodeFactor: parseFloat(urlParams.get('explode') || '0.0'),
      activeStep: parseInt(urlParams.get('step') || '0', 10),
      showWireframe: true,
      activeLaserSheet: 1,
      currentFileSubView: 'preview' // 'preview' or 'code'
    };

    if (!MATERIAL_PROFILES[this.state.materialThickness.toFixed(1)]) {
      this.state.materialThickness = 3.0;
    }
  }

  getState() {
    return { ...this.state };
  }

  getMaterialProfile() {
    const key = this.state.materialThickness.toFixed(1);
    return MATERIAL_PROFILES[key] || MATERIAL_PROFILES['3.0'];
  }

  setState(updates, persist = true) {
    this.state = { ...this.state, ...updates };

    if (persist) {
      if (updates.activeModelId) localStorage.setItem('PUZZLE_ACTIVE_MODEL', updates.activeModelId);
      if (updates.materialThickness) localStorage.setItem('PUZZLE_THICKNESS', updates.materialThickness.toString());
      this.updateUrlQuery();
    }

    this.notify();
  }

  updateUrlQuery() {
    const url = new URL(window.location.href);
    url.searchParams.set('model', this.state.activeModelId);
    if (this.state.selectedPartId) {
      url.searchParams.set('part', this.state.selectedPartId);
    } else {
      url.searchParams.delete('part');
    }
    url.searchParams.set('thickness', this.state.materialThickness.toFixed(1));
    window.history.replaceState({}, '', url.toString());
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify() {
    for (const listener of this.listeners) {
      listener(this.getState());
    }
  }
}

export const AppState = new AppStateManager();
