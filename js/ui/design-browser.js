/**
 * Design Browser & Cloud Manager
 * Displays all user and cloud designs with thumbnails, metadata, search, and instant actions.
 */

import { DesignService } from '../services/firebase-designs.js';
import { ModelRegistry } from '../models/registry.js';
import { AppState } from '../core/config.js';
import { Toast } from './toast.js';

export class DesignBrowser {
  constructor({ onSelectDesign, onEditDesign, onCreateNew }) {
    this.onSelectDesign = onSelectDesign;
    this.onEditDesign = onEditDesign;
    this.onCreateNew = onCreateNew;
    this.designs = [];
    this.isOpen = false;

    this.mount();
  }

  mount() {
    if (document.getElementById('design-browser-modal')) return;

    const modal = document.createElement('div');
    modal.id = 'design-browser-modal';
    modal.className = 'fixed inset-0 bg-slate-950/85 backdrop-blur-md z-50 flex items-center justify-center hidden p-4';
    modal.innerHTML = `
      <div class="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-4xl max-h-[88vh] flex flex-col shadow-2xl overflow-hidden">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-slate-800 bg-slate-950/70 flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div class="flex items-center space-x-3">
            <div class="w-9 h-9 rounded-xl bg-sky-500/20 border border-sky-500/40 flex items-center justify-center text-sky-400 text-lg">
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
        <div class="px-6 py-3 border-b border-slate-800 bg-slate-950/40 flex flex-wrap items-center justify-between gap-3 text-xs shrink-0">
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
        <div id="browser-grid-container" class="flex-1 overflow-y-auto p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <!-- Populated dynamically -->
        </div>

        <!-- Empty State -->
        <div id="browser-empty-state" class="hidden flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400 space-y-3">
          <span class="text-4xl">📦</span>
          <p class="font-medium text-slate-200">No designs found</p>
          <p class="text-xs max-w-sm text-slate-400">No designs match your search or no designs are saved yet. Click below to start your first 3D design.</p>
          <button id="browser-empty-create" class="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded text-xs transition">Create New Design</button>
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
      card.className = `bg-slate-950/70 border ${isCurrent ? 'border-sky-500 shadow-lg shadow-sky-500/10 ring-1 ring-sky-500' : 'border-slate-800 hover:border-slate-700'} rounded-xl p-3 flex flex-col justify-between transition hover:shadow-xl`;

      const thumbHtml = d.thumbnail
        ? `<img src="${d.thumbnail}" alt="${d.name}" class="w-full h-32 object-cover rounded-lg bg-slate-900 border border-slate-800" />`
        : `<div class="w-full h-32 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-600 text-3xl">🧩</div>`;

      card.innerHTML = `
        <div class="space-y-2">
          <div class="relative">
            ${thumbHtml}
            ${isCurrent ? `<span class="absolute top-2 right-2 px-2 py-0.5 rounded-md bg-sky-500 text-slate-950 font-bold text-[10px] uppercase shadow">Active</span>` : ''}
            <span class="absolute bottom-2 left-2 px-1.5 py-0.5 rounded bg-slate-900/90 text-amber-300 font-mono text-[10px] border border-slate-700 backdrop-blur">
              ${d.partCount || '?'} Parts
            </span>
          </div>

          <div>
            <div class="flex items-center justify-between gap-1">
              <h3 class="font-bold text-slate-100 text-xs truncate max-w-[180px]">${d.name}</h3>
              <span class="text-[9px] font-mono px-1 py-0.2 rounded bg-slate-800 text-slate-400">v${d.version || 1}</span>
            </div>
            <div class="text-[10px] text-slate-400 flex items-center gap-2 mt-0.5">
              <span>${d.category || 'General'}</span>
              <span>•</span>
              <span class="font-mono text-slate-500">${this.formatDate(d.updatedAt)}</span>
            </div>
          </div>
        </div>

        <div class="mt-3 pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs">
          <div class="flex items-center space-x-1">
            <button class="btn-open-design px-2.5 py-1 bg-sky-600 hover:bg-sky-500 text-white rounded font-medium text-[11px] transition flex items-center gap-1">
              <span>▶ View</span>
            </button>
            <button class="btn-edit-design px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-[11px] transition">
              <span>✏️ Edit</span>
            </button>
          </div>

          <div class="flex items-center space-x-1 text-slate-400">
            <button class="btn-clone-design hover:text-slate-100 p-1" title="Duplicate Design">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2"/></svg>
            </button>
            <button class="btn-export-design hover:text-slate-100 p-1" title="Export .JS File">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
            </button>
            <button class="btn-delete-design hover:text-rose-400 p-1" title="Delete Design">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          </div>
        </div>
      `;

      // Bind button events
      card.querySelector('.btn-open-design').onclick = () => {
        this.close();
        if (this.onSelectDesign) this.onSelectDesign(d);
      };

      card.querySelector('.btn-edit-design').onclick = () => {
        this.close();
        if (this.onEditDesign) this.onEditDesign(d);
      };

      card.querySelector('.btn-clone-design').onclick = async () => {
        const copyName = prompt('Enter name for duplicate design:', `${d.name} (Copy)`);
        if (copyName) {
          try {
            await DesignService.duplicateDesign(d.id, copyName);
            Toast.show(`Duplicated as "${copyName}"`, '📑');
            await this.refreshDesigns();
          } catch (e) {
            Toast.show('Duplicate failed: ' + e.message, '⚠️');
          }
        }
      };

      card.querySelector('.btn-export-design').onclick = () => {
        DesignService.exportDesignAsJS(d);
        Toast.show(`Exported ${d.id}.js`, '📥');
      };

      card.querySelector('.btn-delete-design').onclick = async () => {
        if (confirm(`Are you sure you want to delete "${d.name}"?`)) {
          await DesignService.deleteDesign(d.id);
          Toast.show(`Deleted "${d.name}"`, '🗑️');
          await this.refreshDesigns();
        }
      };

      container.appendChild(card);
    });
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
