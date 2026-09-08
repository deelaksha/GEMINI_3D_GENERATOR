/**
 * Universal Navigation Bar Component
 * Unified header rendered across all pages with model switcher, page links, and thickness gauge.
 */
import { AppState, MATERIAL_PROFILES } from '../core/config.js';
import { ModelRegistry } from '../models/registry.js';
import { Toast } from './toast.js';
import { aiPromptModal } from './ai-prompt-modal.js';

export const WorkbenchNav = {
  render(activePageId) {
    const navPlaceholder = document.getElementById('workbench-navbar-mount');
    if (!navPlaceholder) return;

    const state = AppState.getState();
    const activeModel = ModelRegistry.getActiveModel();
    const allModels = ModelRegistry.getAllModels();

    const pages = [
      { id: 'assembly', href: 'index.html', label: '3D Assembly', icon: 'M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21l-2-1m2 1l2-1m-2 1v-2.5M6 18l-2-1v-2.5M18 18l2-1v-2.5' },
      { id: 'inspector', href: 'inspector.html', label: 'Part File Inspector', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
      { id: 'manufacturing', href: 'manufacturing.html', label: '2D Cut Sheets', icon: 'M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z' },
      { id: 'validation', href: 'validation.html', label: 'Fit Audit & Graph', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z' },
      { id: 'guide', href: 'guide.html', label: 'Construction Guide', icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253' }
    ];

    const modelOptions = allModels.map(m => `
      <option value="${m.id}" ${m.id === activeModel.id ? 'selected' : ''} class="bg-slate-900 text-slate-100">
        ${m.name} (${m.getPartCount()} parts)
      </option>
    `).join('');

    const thicknessOptions = Object.entries(MATERIAL_PROFILES).map(([key, prof]) => `
      <option value="${key}" ${state.materialThickness.toFixed(1) === key ? 'selected' : ''} class="bg-slate-900 text-slate-100">
        ${prof.name}
      </option>
    `).join('');

    navPlaceholder.innerHTML = `
      <header class="bg-slate-900/95 border-b border-slate-800 px-4 py-2 flex flex-wrap items-center justify-between gap-3 shrink-0 z-30 backdrop-blur">
        <!-- Logo & Model Switcher -->
        <div class="flex items-center space-x-3">
          <div class="w-9 h-9 rounded-lg bg-gradient-to-tr from-amber-600 via-amber-500 to-yellow-300 flex items-center justify-center shadow-lg shadow-amber-500/20 text-slate-950 font-black text-lg">
            🧩
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <h1 class="font-bold text-sm tracking-wide text-slate-100 uppercase">PUZZLECORE</h1>
              <span class="text-[10px] px-1.5 py-0.2 rounded bg-sky-950 text-sky-400 border border-sky-800 font-mono font-bold">GENERIC V2.0</span>
            </div>
            <div class="flex items-center space-x-1.5 text-xs">
              <span class="text-slate-400 text-[11px]">Active Object:</span>
              <select id="global-model-selector" class="bg-slate-800/80 text-amber-300 font-semibold px-2 py-0.5 rounded border border-slate-700 text-xs focus:outline-none cursor-pointer">
                ${modelOptions}
              </select>
              <button id="btn-navbar-new" class="bg-sky-600 hover:bg-sky-500 text-white font-bold px-2.5 py-0.5 rounded text-xs transition flex items-center gap-1 shadow shadow-sky-600/30" title="Create New 3D Model">
                <span class="text-sm font-black leading-none">+</span>
                <span>New</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Page Navigation Tabs -->
        <nav class="flex bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-medium space-x-0.5">
          ${pages.map(p => {
            const isActive = p.id === activePageId;
            const activeClass = isActive 
              ? 'bg-sky-600 text-white shadow' 
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900';
            return `
              <a href="${p.href}?model=${activeModel.id}&thickness=${state.materialThickness.toFixed(1)}${state.selectedPartId ? `&part=${state.selectedPartId}` : ''}" 
                 class="px-3 py-1.5 rounded-md transition flex items-center gap-1.5 ${activeClass}">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${p.icon}"/>
                </svg>
                <span>${p.label}</span>
              </a>
            `;
          }).join('')}
        </nav>

        <!-- Right Side Parameter Config & Studio Buttons -->
        <div class="flex items-center space-x-2 text-xs">
          <button id="btn-navbar-new-alt" class="bg-sky-600 hover:bg-sky-500 text-white font-bold px-2.5 py-1.5 rounded transition flex items-center gap-1 shadow shadow-sky-600/30" title="Create New 3D Model">
            <span class="text-sm font-black leading-none">+</span>
            <span>New</span>
          </button>

          <button id="btn-open-cloud-designs" class="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-medium px-2.5 py-1.5 rounded transition flex items-center gap-1.5 shadow">
            <span class="text-sky-400">☁️</span>
            <span>My Designs</span>
          </button>

          <button id="btn-open-ai-prompt" class="bg-gradient-to-r from-purple-700 to-indigo-600 hover:from-purple-600 hover:to-indigo-500 text-white font-semibold px-2.5 py-1.5 rounded transition flex items-center gap-1.5 shadow shadow-purple-600/30" title="View & Copy AI Prompt (ai-prompt.txt)">
            <span>🤖</span>
            <span>AI Prompt</span>
          </button>

          <button id="btn-open-code-studio" class="bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-slate-950 font-bold px-3 py-1.5 rounded transition flex items-center gap-1.5 shadow shadow-amber-500/20">
            <span>⚡</span>
            <span>Design Studio</span>
          </button>

          <div class="flex items-center space-x-1.5 bg-slate-800/80 px-2.5 py-1 rounded border border-slate-700">
            <span class="text-slate-400 font-mono">Gauge:</span>
            <select id="global-thickness-selector" class="bg-transparent text-amber-300 font-mono font-bold focus:outline-none cursor-pointer">
              ${thicknessOptions}
            </select>
          </div>

          <button id="btn-export-manifest" class="bg-slate-800 hover:bg-slate-700 text-sky-300 border border-slate-700 font-medium px-2.5 py-1.5 rounded transition flex items-center gap-1">
            <span>📦</span><span class="hidden xl:inline">Export Manifest</span>
          </button>
        </div>
      </header>
    `;

    // Bind event listeners
    const modelSel = document.getElementById('global-model-selector');
    if (modelSel) {
      modelSel.addEventListener('change', (e) => {
        const newModelId = e.target.value;
        const newModel = ModelRegistry.getModel(newModelId);
        const firstPart = newModel?.parts[0]?.id || null;
        AppState.setState({ activeModelId: newModelId, selectedPartId: firstPart, activeStep: 0 });
        Toast.show(`Switched active model to: ${newModel.name}`, '🔄');
        // Reload current page with updated model param
        const url = new URL(window.location.href);
        url.searchParams.set('model', newModelId);
        if (firstPart) {
          url.searchParams.set('part', firstPart);
        } else {
          url.searchParams.delete('part');
        }
        window.location.href = url.toString();
      });
    }

    const isIndexPage = window.location.pathname.endsWith('index.html') || window.location.pathname.endsWith('/') || window.location.pathname === '';

    const triggerNewModel = () => {
      if (isIndexPage) {
        window.dispatchEvent(new CustomEvent('puzzlecore:new-model'));
      } else {
        window.location.href = `index.html?action=new`;
      }
    };

    const btnNew = document.getElementById('btn-navbar-new');
    if (btnNew) btnNew.addEventListener('click', triggerNewModel);

    const btnNewAlt = document.getElementById('btn-navbar-new-alt');
    if (btnNewAlt) btnNewAlt.addEventListener('click', triggerNewModel);

    const btnStudio = document.getElementById('btn-open-code-studio');
    if (btnStudio) {
      btnStudio.addEventListener('click', () => {
        if (isIndexPage) {
          window.dispatchEvent(new CustomEvent('puzzlecore:open-studio'));
        } else {
          window.location.href = `index.html?open=studio&model=${AppState.getState().activeModelId}`;
        }
      });
    }

    const btnCloud = document.getElementById('btn-open-cloud-designs');
    if (btnCloud) {
      btnCloud.addEventListener('click', () => {
        if (isIndexPage) {
          window.dispatchEvent(new CustomEvent('puzzlecore:open-browser'));
        } else {
          window.location.href = `index.html?open=browser&model=${AppState.getState().activeModelId}`;
        }
      });
    }

    const btnAiPrompt = document.getElementById('btn-open-ai-prompt');
    if (btnAiPrompt) {
      btnAiPrompt.addEventListener('click', () => {
        aiPromptModal.open();
      });
    }

    const thickSel = document.getElementById('global-thickness-selector');
    if (thickSel) {
      thickSel.addEventListener('change', (e) => {
        const t = parseFloat(e.target.value);
        AppState.setState({ materialThickness: t });
        Toast.show(`Material gauge set to: ${t.toFixed(1)} mm`, '📏');
      });

      AppState.subscribe((state) => {
        const val = state.materialThickness.toFixed(1);
        if (thickSel.value !== val) {
          thickSel.value = val;
        }
      });
    }

    const btnManifest = document.getElementById('btn-export-manifest');
    if (btnManifest) {
      btnManifest.addEventListener('click', () => {
        const model = ModelRegistry.getActiveModel();
        const currentThick = AppState.getState().materialThickness;
        const manifest = {
          format: "PUZZLECORE_AUTHORITATIVE_CONSTRUCTION_SPEC",
          version: "2.0.0",
          modelId: model.id,
          modelName: model.name,
          category: model.category,
          difficulty: model.difficulty,
          materialThickness: currentThick,
          totalParts: model.getPartCount(),
          parts: model.parts.map(p => ({
            id: p.id,
            fileName: p.fileName,
            name: p.name,
            category: p.category,
            step: p.step,
            sheet: p.sheet,
            dimensions: `${p.width}x${p.length}mm`,
            matingPartCount: (p.connections || []).length
          }))
        };

        const jsonStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(manifest, null, 2));
        const link = document.createElement("a");
        link.href = jsonStr;
        link.download = `${model.id}_manifest.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        Toast.show('Project Manifest JSON exported!', '📥');
      });
    }
  }
};
