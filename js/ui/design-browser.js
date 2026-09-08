/**
 * Design Browser & Cloud Manager
 * Displays all user and cloud designs with 3D thumbnails, metadata, search,
 * direct click-to-open, automatic thumbnail repair, and an interactive in-modal 3D viewer.
 */

import { DesignService } from '../services/firebase-designs.js';
import { ModelRegistry } from '../models/registry.js';
import { AppState } from '../core/config.js';
import { Toast } from './toast.js';
import { ThumbnailGenerator } from '../services/thumbnail-generator.js';
import { ExplodeEngine } from '../assembly/explode.js';

export class DesignBrowser {
  constructor({ onSelectDesign, onEditDesign, onCreateNew }) {
    this.onSelectDesign = onSelectDesign;
    this.onEditDesign = onEditDesign;
    this.onCreateNew = onCreateNew;
    this.designs = [];
    this.isOpen = false;

    // Quick 3D Viewer state
    this.quickViewer = {
      active: false,
      renderer: null,
      scene: null,
      camera: null,
      meshMap: new Map(),
      parts: [],
      animId: null,
      autoRotate: true,
      cameraAngleX: 0.55,
      cameraAngleY: -0.75,
      cameraDistance: 250,
      cameraTarget: null,
      isMouseDown: false,
      mouseX: 0,
      mouseY: 0
    };

    this.mount();
  }

  mount() {
    if (document.getElementById('design-browser-modal')) return;

    const modal = document.createElement('div');
    modal.id = 'design-browser-modal';
    modal.className = 'fixed inset-0 bg-slate-950/85 backdrop-blur-md z-50 flex items-center justify-center hidden p-4';
    modal.innerHTML = `
      <div class="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden relative">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-slate-800 bg-slate-950/70 flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div class="flex items-center space-x-3">
            <div class="w-9 h-9 rounded-xl bg-sky-500/20 border border-sky-500/40 flex items-center justify-center text-sky-400 text-lg shadow-inner">
              ☁️
            </div>
            <div>
              <h2 class="font-bold text-base text-slate-100 uppercase tracking-wide flex items-center gap-2">
                <span>Cloud & Local Designs</span>
                <span id="browser-count-badge" class="text-xs px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800 font-mono font-bold">0 Designs</span>
              </h2>
              <p class="text-xs text-slate-400">Manage, inspect, switch, and duplicate stored 3D models</p>
            </div>
          </div>

          <div class="flex items-center space-x-2">
            <button id="browser-btn-new" class="bg-gradient-to-r from-sky-500 to-sky-600 hover:from-sky-400 hover:to-sky-500 text-white text-xs font-semibold px-3 py-2 rounded-lg transition flex items-center gap-1.5 shadow shadow-sky-500/30">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
              <span>New Design</span>
            </button>
            <button id="browser-btn-close" class="p-1.5 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-800 transition">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
          </div>
        </div>

        <!-- Filter & Search Bar -->
        <div id="browser-filter-bar" class="px-6 py-3 border-b border-slate-800 bg-slate-950/40 flex flex-wrap items-center justify-between gap-3 text-xs shrink-0">
          <div class="flex-1 min-w-[200px] relative">
            <input type="text" id="browser-search-input" placeholder="Search by design name, category, or id..." 
                   class="w-full bg-slate-950 border border-slate-700 rounded-lg pl-8 pr-3 py-1.5 text-slate-200 focus:outline-none focus:border-sky-500 text-xs" />
            <svg class="w-4 h-4 text-slate-500 absolute left-2.5 top-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
          </div>

          <div class="flex items-center space-x-2">
            <span class="text-slate-400 font-mono text-[11px]">Filter:</span>
            <select id="browser-filter-cat" class="bg-slate-800 text-slate-200 px-2 py-1 rounded border border-slate-700 text-xs focus:outline-none cursor-pointer">
              <option value="all">All Categories</option>
            </select>
          </div>
        </div>

        <!-- Designs Grid Body -->
        <div id="browser-grid-container" class="flex-1 overflow-y-auto p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          <!-- Populated dynamically -->
        </div>

        <!-- Empty State -->
        <div id="browser-empty-state" class="hidden flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400 space-y-3">
          <span class="text-4xl">📦</span>
          <p class="font-medium text-slate-200">No designs found</p>
          <p class="text-xs max-w-sm text-slate-400">No designs match your search or no designs are saved yet. Click below to start your first 3D design.</p>
          <button id="browser-empty-create" class="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded text-xs transition">Create New Design</button>
        </div>

        <!-- In-Modal 3D Interactive Quick Viewer Overlay -->
        <div id="browser-quick-viewer-panel" class="hidden absolute inset-0 bg-slate-950/95 z-20 flex flex-col backdrop-blur-md">
          <!-- Viewer Header -->
          <div class="px-6 py-3 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between shrink-0">
            <div class="flex items-center space-x-3">
              <span class="px-2 py-0.5 rounded bg-sky-500/20 text-sky-400 border border-sky-500/30 font-mono text-[11px] font-bold">3D Quick View</span>
              <h3 id="quick-viewer-title" class="font-bold text-slate-100 text-sm truncate max-w-[280px]">Model Preview</h3>
              <span id="quick-viewer-part-badge" class="text-amber-300 font-mono text-xs bg-slate-800 px-2 py-0.5 rounded border border-slate-700">-- Parts</span>
            </div>
            <button id="quick-viewer-btn-back" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium transition flex items-center gap-1.5">
              <span>✕ Back to Grid</span>
            </button>
          </div>

          <!-- 3D Canvas Area -->
          <div class="flex-1 relative overflow-hidden bg-gradient-to-b from-slate-950 to-slate-900 flex items-center justify-center">
            <div id="quick-viewer-canvas-mount" class="w-full h-full cursor-grab active:cursor-grabbing"></div>

            <!-- Viewer Floating Controls -->
            <div class="absolute top-3 left-4 flex items-center space-x-2 bg-slate-900/80 backdrop-blur border border-slate-700/80 rounded-lg p-1.5 text-xs text-slate-300">
              <button id="quick-viewer-btn-autorotate" class="px-2.5 py-1 rounded bg-sky-600/30 text-sky-300 border border-sky-500/40 hover:bg-sky-600/50 transition flex items-center gap-1 font-medium text-[11px]">
                <span>🔄</span> Turntable: ON
              </button>
              <button id="quick-viewer-btn-reset" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition text-[11px]">
                🎯 Reset View
              </button>
              <div class="flex items-center space-x-1.5 pl-2 border-l border-slate-700 text-[11px]">
                <span>💥 Explode:</span>
                <input type="range" id="quick-viewer-explode-slider" min="0" max="1" step="0.01" value="0" class="w-20 accent-sky-500 cursor-pointer" />
              </div>
            </div>

            <!-- Help hint -->
            <div class="absolute bottom-3 right-4 px-2.5 py-1 rounded bg-slate-900/80 text-slate-400 font-mono text-[10px] border border-slate-800 pointer-events-none">
              Drag to Orbit • Scroll to Zoom
            </div>
          </div>

          <!-- Viewer Footer Actions -->
          <div class="px-6 py-3 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between shrink-0">
            <div id="quick-viewer-meta" class="text-xs text-slate-400 flex items-center gap-3">
              <span id="quick-viewer-dim">--</span>
              <span>•</span>
              <span id="quick-viewer-cat">--</span>
            </div>
            <div class="flex items-center space-x-2">
              <button id="quick-viewer-btn-edit" class="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium transition flex items-center gap-1.5">
                <span>✏️ Edit in Code Studio</span>
              </button>
              <button id="quick-viewer-btn-open" class="px-4 py-1.5 bg-gradient-to-r from-sky-500 to-sky-600 hover:from-sky-400 hover:to-sky-500 text-white rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shadow shadow-sky-500/30">
                <span>▶ Open in Workbench</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(modal);
    this.bindEvents();
  }

  bindEvents() {
    document.getElementById('browser-btn-close')?.addEventListener('click', () => this.close());
    document.getElementById('browser-btn-new')?.addEventListener('click', () => {
      this.close();
      if (this.onCreateNew) this.onCreateNew();
    });
    document.getElementById('browser-empty-create')?.addEventListener('click', () => {
      this.close();
      if (this.onCreateNew) this.onCreateNew();
    });

    const searchInput = document.getElementById('browser-search-input');
    searchInput?.addEventListener('input', () => this.renderGrid());

    const catSelect = document.getElementById('browser-filter-cat');
    catSelect?.addEventListener('change', () => this.renderGrid());

    // Quick Viewer Controls
    document.getElementById('quick-viewer-btn-back')?.addEventListener('click', () => this.closeQuick3DView());
    document.getElementById('quick-viewer-btn-autorotate')?.addEventListener('click', () => {
      this.quickViewer.autoRotate = !this.quickViewer.autoRotate;
      const btn = document.getElementById('quick-viewer-btn-autorotate');
      if (btn) {
        btn.innerHTML = `<span>🔄</span> Turntable: ${this.quickViewer.autoRotate ? 'ON' : 'OFF'}`;
        if (this.quickViewer.autoRotate) {
          btn.className = 'px-2.5 py-1 rounded bg-sky-600/30 text-sky-300 border border-sky-500/40 hover:bg-sky-600/50 transition flex items-center gap-1 font-medium text-[11px]';
        } else {
          btn.className = 'px-2.5 py-1 rounded bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700 transition flex items-center gap-1 font-medium text-[11px]';
        }
      }
    });

    document.getElementById('quick-viewer-btn-reset')?.addEventListener('click', () => {
      this.quickViewer.cameraAngleX = 0.55;
      this.quickViewer.cameraAngleY = -0.75;
      this.updateQuickCamera();
    });

    const explodeSlider = document.getElementById('quick-viewer-explode-slider');
    explodeSlider?.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value) || 0;
      ExplodeEngine.applyExplode(this.quickViewer.meshMap, this.quickViewer.parts, val);
    });
  }

  async open() {
    const modal = document.getElementById('design-browser-modal');
    if (modal) {
      modal.classList.remove('hidden');
      this.isOpen = true;
    }

    await this.refreshDesigns();
  }

  close() {
    this.closeQuick3DView();
    const modal = document.getElementById('design-browser-modal');
    if (modal) {
      modal.classList.add('hidden');
      this.isOpen = false;
    }
  }

  async refreshDesigns() {
    this.designs = await DesignService.listDesigns();
    this.updateCategoryOptions();
    this.renderGrid();
    // In background, auto-repair any missing or all-black thumbnails
    this.autoRepairMissingThumbnails();
  }

  /**
   * Scans all designs and automatically generates 3D thumbnails and accurate part counts
   * for any models with missing, empty, or black thumbnails.
   */
  async autoRepairMissingThumbnails() {
    for (const d of this.designs) {
      const isBlank = d.isBlank || (d.modelData && Array.isArray(d.modelData.parts) && d.modelData.parts.length === 0) || (d.partCount === 0);
      if (isBlank) continue;

      const isBlackOrMissing = await ThumbnailGenerator.isBlackOrEmpty(d.thumbnail);
      const needsParts = d.partCount === undefined || d.partCount === null || d.partCount === '?';

      if (isBlackOrMissing || needsParts) {
        try {
          const genRes = await ThumbnailGenerator.generateThumbnail(d);
          if (genRes && genRes.thumbnail) {
            d.thumbnail = genRes.thumbnail;
            d.partCount = genRes.partCount;
            if (genRes.dimensions) d.dimensions = genRes.dimensions;
            if (genRes.difficulty) d.difficulty = genRes.difficulty;

            // Live-update card image and badge in DOM without jarring re-render
            const imgEl = document.getElementById(`thumb-img-${d.id}`);
            if (imgEl) {
              imgEl.src = d.thumbnail;
            } else {
              const holder = document.getElementById(`thumb-holder-${d.id}`);
              if (holder) {
                holder.innerHTML = `<img id="thumb-img-${d.id}" src="${d.thumbnail}" alt="${d.name}" class="w-full h-36 object-cover rounded-lg bg-slate-900 border border-slate-800 transition-transform duration-300 group-hover:scale-105" />`;
              }
            }

            const badgeEl = document.getElementById(`part-badge-${d.id}`);
            if (badgeEl) {
              badgeEl.innerText = `${d.partCount} Parts`;
            }

            // Persist updated thumbnail and metadata to storage
            await DesignService.saveDesign({
              id: d.id,
              name: d.name,
              category: d.category,
              description: d.description,
              jsCode: d.jsCode,
              modelData: genRes.modelData,
              thumbnail: d.thumbnail
            });
          }
        } catch (err) {
          console.warn('[DesignBrowser] Auto-repair thumbnail error for:', d.id, err);
        }
      }
    }
  }

  updateCategoryOptions() {
    const catSelect = document.getElementById('browser-filter-cat');
    if (!catSelect) return;

    const cats = new Set(['all']);
    this.designs.forEach(d => {
      if (d.category) cats.add(d.category);
    });

    catSelect.innerHTML = Array.from(cats).map(c => `
      <option value="${c}">${c === 'all' ? 'All Categories' : c}</option>
    `).join('');
  }

  renderGrid() {
    const container = document.getElementById('browser-grid-container');
    const emptyState = document.getElementById('browser-empty-state');
    const countBadge = document.getElementById('browser-count-badge');
    const searchVal = (document.getElementById('browser-search-input')?.value || '').toLowerCase();
    const catVal = document.getElementById('browser-filter-cat')?.value || 'all';

    if (!container) return;

    const filtered = this.designs.filter(d => {
      const matchSearch = !searchVal || 
        d.name.toLowerCase().includes(searchVal) || 
        (d.category && d.category.toLowerCase().includes(searchVal)) ||
        d.id.toLowerCase().includes(searchVal);
      const matchCat = catVal === 'all' || d.category === catVal;
      return matchSearch && matchCat;
    });

    if (countBadge) {
      countBadge.innerText = `${filtered.length} Design${filtered.length === 1 ? '' : 's'}`;
    }

    if (filtered.length === 0) {
      container.classList.add('hidden');
      emptyState?.classList.remove('hidden');
      return;
    }

    container.classList.remove('hidden');
    emptyState?.classList.add('hidden');
    container.innerHTML = '';

    const currentModelId = AppState.getState().activeModelId;

    filtered.forEach(d => {
      const isCurrent = d.id === currentModelId;
      const card = document.createElement('div');
      card.className = `group bg-slate-950/80 border ${isCurrent ? 'border-sky-500 shadow-lg shadow-sky-500/15 ring-1 ring-sky-500' : 'border-slate-800 hover:border-sky-500/50'} rounded-xl p-3 flex flex-col justify-between transition-all duration-200 hover:-translate-y-1 hover:shadow-2xl cursor-pointer relative`;

      const thumbHtml = d.thumbnail
        ? `<img id="thumb-img-${d.id}" src="${d.thumbnail}" alt="${d.name}" class="w-full h-36 object-cover rounded-lg bg-slate-900 border border-slate-800 transition-transform duration-300 group-hover:scale-105" />`
        : `<div id="thumb-holder-${d.id}" class="w-full h-36 rounded-lg bg-slate-900 border border-slate-800 flex flex-col items-center justify-center text-slate-500 text-3xl gap-1">
             <span>🧩</span>
             <span class="text-[10px] font-mono text-slate-500">Generating 3D preview...</span>
           </div>`;

      card.innerHTML = `
        <div class="space-y-2.5">
          <!-- Thumbnail Container with Direct Click & Quick View Overlay -->
          <div class="relative rounded-lg overflow-hidden group/thumb bg-slate-900">
            ${thumbHtml}
            
            ${isCurrent ? `<span class="absolute top-2 right-2 px-2 py-0.5 rounded-md bg-sky-500 text-slate-950 font-bold text-[10px] uppercase shadow z-10">Active</span>` : ''}
            
            <span id="part-badge-${d.id}" class="absolute bottom-2 left-2 px-2 py-0.5 rounded bg-slate-950/90 text-amber-300 font-mono text-[11px] font-bold border border-slate-700 backdrop-blur z-10 shadow">
              ${d.partCount ? `${d.partCount} Parts` : 'Loading...'}
            </span>

            <!-- Hover Overlay -->
            <div class="absolute inset-0 bg-slate-950/65 opacity-0 group-hover/thumb:opacity-100 transition-opacity duration-200 flex flex-col items-center justify-center gap-2 backdrop-blur-[2px] z-10">
              <span class="px-3 py-1.5 rounded-lg bg-sky-500 text-slate-950 font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-sky-500/40 transform -translate-y-1 group-hover/thumb:translate-y-0 transition-transform">
                <span>▶</span> Click to Open & Assemble
              </span>
              <button class="btn-card-quick-3d px-2.5 py-1 rounded bg-slate-800/90 hover:bg-slate-700 text-sky-300 text-[11px] border border-slate-700 backdrop-blur flex items-center gap-1 transition">
                <span>👁️ Quick 3D View</span>
              </button>
            </div>
          </div>

          <!-- Metadata -->
          <div>
            <div class="flex items-center justify-between gap-1">
              <h3 class="font-bold text-slate-100 text-xs truncate max-w-[190px] group-hover:text-sky-400 transition-colors">${d.name}</h3>
              <span class="text-[9px] font-mono px-1 py-0.2 rounded bg-slate-800 text-slate-400">v${d.version || 1}</span>
            </div>
            <div class="text-[10px] text-slate-400 flex items-center gap-2 mt-0.5">
              <span class="truncate max-w-[120px]">${d.category || 'General'}</span>
              <span>•</span>
              <span class="font-mono text-slate-500">${this.formatDate(d.updatedAt)}</span>
            </div>
          </div>
        </div>

        <!-- Action Toolbar -->
        <div class="mt-3 pt-2.5 border-t border-slate-800/80 flex items-center justify-between text-xs">
          <div class="flex items-center space-x-1.5">
            <button class="btn-open-design px-2.5 py-1 bg-sky-600 hover:bg-sky-500 text-white rounded font-medium text-[11px] transition flex items-center gap-1 shadow shadow-sky-600/20">
              <span>▶ View</span>
            </button>
            <button class="btn-quick-3d px-2 py-1 bg-slate-800 hover:bg-slate-700 text-sky-400 rounded text-[11px] transition flex items-center gap-1 border border-slate-700" title="Inspect model in 3D right here">
              <span>👁️ 3D</span>
            </button>
            <button class="btn-edit-design px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-[11px] transition">
              <span>✏️ Edit</span>
            </button>
          </div>

          <div class="flex items-center space-x-1 text-slate-400">
            <button class="btn-clone-design hover:text-slate-100 p-1 rounded hover:bg-slate-800 transition" title="Duplicate Design">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2"/></svg>
            </button>
            <button class="btn-export-design hover:text-slate-100 p-1 rounded hover:bg-slate-800 transition" title="Export .JS File">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
            </button>
            <button class="btn-delete-design hover:text-rose-400 p-1 rounded hover:bg-slate-800 transition" title="Delete Design">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          </div>
        </div>
      `;

      // Direct Card Click: Immediately loads design into workbench
      card.onclick = (e) => {
        // If user clicked an action button, let the button handler manage it
        if (e.target.closest('button')) return;
        this.close();
        if (this.onSelectDesign) this.onSelectDesign(d);
      };

      // Button: Open / View
      card.querySelector('.btn-open-design').onclick = (e) => {
        e.stopPropagation();
        this.close();
        if (this.onSelectDesign) this.onSelectDesign(d);
      };

      // Button: Quick 3D View (Both in toolbar and thumbnail hover)
      card.querySelector('.btn-quick-3d')?.addEventListener('click', (e) => {
        e.stopPropagation();
        this.openQuick3DView(d);
      });
      card.querySelector('.btn-card-quick-3d')?.addEventListener('click', (e) => {
        e.stopPropagation();
        this.openQuick3DView(d);
      });

      // Button: Edit in Studio
      card.querySelector('.btn-edit-design').onclick = (e) => {
        e.stopPropagation();
        this.close();
        if (this.onEditDesign) this.onEditDesign(d);
      };

      // Button: Duplicate
      card.querySelector('.btn-clone-design').onclick = async (e) => {
        e.stopPropagation();
        const copyName = prompt('Enter name for duplicate design:', `${d.name} (Copy)`);
        if (copyName) {
          try {
            await DesignService.duplicateDesign(d.id, copyName);
            Toast.show(`Duplicated as "${copyName}"`, '📑');
            await this.refreshDesigns();
          } catch (err) {
            Toast.show('Duplicate failed: ' + err.message, '⚠️');
          }
        }
      };

      // Button: Export JS
      card.querySelector('.btn-export-design').onclick = (e) => {
        e.stopPropagation();
        DesignService.exportDesignAsJS(d);
        Toast.show(`Exported ${d.id}.js`, '📥');
      };

      // Button: Delete
      card.querySelector('.btn-delete-design').onclick = async (e) => {
        e.stopPropagation();
        if (confirm(`Are you sure you want to delete "${d.name}"?`)) {
          await DesignService.deleteDesign(d.id);
          Toast.show(`Deleted "${d.name}"`, '🗑️');
          await this.refreshDesigns();
        }
      };

      container.appendChild(card);
    });
  }

  /**
   * Opens the in-modal interactive 3D Quick Viewer for a design
   */
  async openQuick3DView(design) {
    const panel = document.getElementById('browser-quick-viewer-panel');
    const mount = document.getElementById('quick-viewer-canvas-mount');
    if (!panel || !mount) return;

    panel.classList.remove('hidden');

    // Populate metadata
    document.getElementById('quick-viewer-title').innerText = design.name;
    document.getElementById('quick-viewer-part-badge').innerText = `${design.partCount || '?'} Parts`;
    document.getElementById('quick-viewer-cat').innerText = design.category || 'General';
    document.getElementById('quick-viewer-dim').innerText = design.dimensions || '';

    // Bind primary actions
    const btnOpen = document.getElementById('quick-viewer-btn-open');
    if (btnOpen) {
      btnOpen.onclick = () => {
        this.closeQuick3DView();
        this.close();
        if (this.onSelectDesign) this.onSelectDesign(design);
      };
    }

    const btnEdit = document.getElementById('quick-viewer-btn-edit');
    if (btnEdit) {
      btnEdit.onclick = () => {
        this.closeQuick3DView();
        this.close();
        if (this.onEditDesign) this.onEditDesign(design);
      };
    }

    // Initialize interactive 3D scene inside mount
    await this.initQuickViewerScene(mount, design);
  }

  async initQuickViewerScene(container, design) {
    if (typeof THREE === 'undefined') return;

    this.disposeQuickViewer();

    const width = container.clientWidth || 700;
    const height = container.clientHeight || 450;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x080d19);

    const camera = new THREE.PerspectiveCamera(38, width / height, 1, 3000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;

    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // Studio Lighting
    const ambientLight = new THREE.AmbientLight(0xfff7ed, 0.9);
    scene.add(ambientLight);

    const sunLight = new THREE.DirectionalLight(0xffedd5, 1.25);
    sunLight.position.set(220, 350, 240);
    scene.add(sunLight);

    const rimLight = new THREE.DirectionalLight(0x38bdf8, 0.65);
    rimLight.position.set(-220, 180, -220);
    scene.add(rimLight);

    // Resolve modelData
    const modelData = await ThumbnailGenerator.resolveModelData(design);
    if (!modelData || !Array.isArray(modelData.parts)) {
      container.innerHTML = `<div class="text-rose-400 p-8 text-center text-xs">Could not load 3D parts for this design.</div>`;
      return;
    }

    if (modelData.parts.length === 0) {
      container.innerHTML = `<div class="text-slate-400 p-8 text-center text-xs space-y-2"><span>📦</span><div class="font-medium text-slate-300">This design is currently blank (0 parts).</div><div class="text-[11px] text-slate-500">Click "Edit in Code Studio" to add parts.</div></div>`;
      return;
    }

    this.quickViewer.parts = modelData.parts;
    this.quickViewer.meshMap.clear();

    const rootGroup = new THREE.Group();
    modelData.parts.forEach(part => {
      const pMesh = ThumbnailGenerator.buildPartMesh(part);
      if (pMesh) {
        rootGroup.add(pMesh);
        this.quickViewer.meshMap.set(part.id, pMesh);
      }
    });

    scene.add(rootGroup);

    // Center model at origin
    const box = new THREE.Box3().setFromObject(rootGroup);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    rootGroup.position.sub(center);

    const maxDim = Math.max(size.x, size.y, size.z, 30);
    const gridHelper = new THREE.GridHelper(maxDim * 1.8, 20, 0x1e293b, 0x0f172a);
    gridHelper.position.y = -(size.y / 2) - 1;
    scene.add(gridHelper);

    this.quickViewer.renderer = renderer;
    this.quickViewer.scene = scene;
    this.quickViewer.camera = camera;
    this.quickViewer.cameraDistance = maxDim * 1.75;
    this.quickViewer.cameraTarget = new THREE.Vector3(0, 0, 0);
    this.quickViewer.cameraAngleX = 0.55;
    this.quickViewer.cameraAngleY = -0.75;
    this.quickViewer.autoRotate = true;

    // Reset explode slider
    const explodeSlider = document.getElementById('quick-viewer-explode-slider');
    if (explodeSlider) explodeSlider.value = 0;

    this.updateQuickCamera();

    // Bind canvas interactions (orbit & zoom)
    const domEl = renderer.domElement;

    domEl.onmousedown = (e) => {
      this.quickViewer.isMouseDown = true;
      this.quickViewer.mouseX = e.clientX;
      this.quickViewer.mouseY = e.clientY;
    };

    window.onmousemove = (e) => {
      if (!this.quickViewer.isMouseDown) return;
      const dx = e.clientX - this.quickViewer.mouseX;
      const dy = e.clientY - this.quickViewer.mouseY;
      this.quickViewer.mouseX = e.clientX;
      this.quickViewer.mouseY = e.clientY;

      this.quickViewer.cameraAngleY -= dx * 0.008;
      this.quickViewer.cameraAngleX += dy * 0.008;
      this.quickViewer.cameraAngleX = Math.max(-Math.PI / 2.2, Math.min(Math.PI / 2.2, this.quickViewer.cameraAngleX));
      this.updateQuickCamera();
    };

    window.onmouseup = () => {
      this.quickViewer.isMouseDown = false;
    };

    domEl.onwheel = (e) => {
      e.preventDefault();
      this.quickViewer.cameraDistance += e.deltaY * 0.25;
      this.quickViewer.cameraDistance = Math.max(30, Math.min(1200, this.quickViewer.cameraDistance));
      this.updateQuickCamera();
    };

    // Render loop
    const animateQuick = () => {
      if (!this.quickViewer.renderer) return;
      this.quickViewer.animId = requestAnimationFrame(animateQuick);

      if (this.quickViewer.autoRotate && !this.quickViewer.isMouseDown) {
        this.quickViewer.cameraAngleY -= 0.004;
        this.updateQuickCamera();
      }

      this.quickViewer.renderer.render(this.quickViewer.scene, this.quickViewer.camera);
    };
    animateQuick();
  }

  updateQuickCamera() {
    const q = this.quickViewer;
    if (!q.camera || !q.cameraTarget) return;

    const x = q.cameraTarget.x + q.cameraDistance * Math.cos(q.cameraAngleX) * Math.sin(q.cameraAngleY);
    const y = q.cameraTarget.y + q.cameraDistance * Math.sin(q.cameraAngleX);
    const z = q.cameraTarget.z + q.cameraDistance * Math.cos(q.cameraAngleX) * Math.cos(q.cameraAngleY);

    q.camera.position.set(x, y, z);
    q.camera.lookAt(q.cameraTarget);
  }

  closeQuick3DView() {
    const panel = document.getElementById('browser-quick-viewer-panel');
    if (panel) panel.classList.add('hidden');
    this.disposeQuickViewer();
  }

  disposeQuickViewer() {
    if (this.quickViewer.animId) {
      cancelAnimationFrame(this.quickViewer.animId);
      this.quickViewer.animId = null;
    }
    if (this.quickViewer.renderer) {
      this.quickViewer.renderer.dispose();
      this.quickViewer.renderer = null;
    }
    this.quickViewer.scene = null;
    this.quickViewer.camera = null;
    this.quickViewer.meshMap.clear();
    this.quickViewer.parts = [];
  }

  formatDate(isoStr) {
    if (!isoStr) return '';
    try {
      const date = new Date(isoStr);
      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch (e) {
      return '';
    }
  }
}
