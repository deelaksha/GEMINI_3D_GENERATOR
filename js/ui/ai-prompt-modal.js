/**
 * AI Prompt & Contest Context Modal Component
 * Loads, dynamically adapts, and renders the copyable content of ai-prompt.txt.
 * Supports real-time adaptation for 1.0mm, 2.0mm, 3.0mm, 4.0mm, and 5.0mm material gauges.
 */

import { Toast } from './toast.js';
import { AppState, MATERIAL_PROFILES } from '../core/config.js';

export class AIPromptModal {
  constructor() {
    this.modalId = 'ai-prompt-modal';
    this.rawPromptText = '';
    this.currentPromptText = '';
    this.mount();
  }

  mount() {
    if (typeof document === 'undefined') return;
    if (document.getElementById(this.modalId)) return;

    const modal = document.createElement('div');
    modal.id = this.modalId;
    modal.className = 'fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center hidden p-4';
    modal.innerHTML = `
      <div class="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-slate-800 bg-slate-950/70 flex items-center justify-between shrink-0">
          <div class="flex items-center space-x-3">
            <div class="w-9 h-9 rounded-xl bg-purple-500/20 border border-purple-500/40 flex items-center justify-center text-purple-400 text-lg shadow">
              🤖
            </div>
            <div>
              <div class="flex items-center space-x-2">
                <h2 class="font-bold text-base text-slate-100 uppercase tracking-wide">AI Prompt & Contest Context</h2>
                <span class="text-[10px] px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800 font-mono font-bold">ai-prompt.txt</span>
              </div>
              <p class="text-xs text-slate-400">Copyable prompt contents loaded directly from <code class="text-amber-300 font-mono text-[11px]">ai-prompt.txt</code></p>
            </div>
          </div>

          <div class="flex items-center space-x-2">
            <button id="ai-prompt-btn-reload" class="p-1.5 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-800 transition text-xs flex items-center gap-1" title="Reload from ai-prompt.txt">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
              <span class="text-[11px]">Reload</span>
            </button>
            <button id="ai-prompt-btn-close" class="p-1.5 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-800 transition">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
          </div>
        </div>

        <!-- Thickness Gauge Selector Bar -->
        <div class="px-6 py-2.5 bg-slate-950/90 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2 shrink-0">
          <div class="flex items-center space-x-2">
            <span class="text-xs font-semibold text-slate-300 flex items-center gap-1">
              <span>📏</span> Target Gauge:
            </span>
            <div id="ai-prompt-thickness-buttons" class="inline-flex rounded-lg bg-slate-900 p-0.5 border border-slate-700">
              <!-- Buttons rendered dynamically -->
            </div>
          </div>
          <div id="ai-prompt-gauge-badge" class="text-[11px] font-mono text-amber-300/90 bg-amber-950/40 border border-amber-800/40 px-2.5 py-1 rounded-md">
            Active: 3.0 mm (MDF / Laser Plywood)
          </div>
        </div>

        <!-- Prompt Content Area -->
        <div class="flex-1 overflow-y-auto p-6 flex flex-col space-y-3 bg-slate-950/40">
          <div class="flex items-center justify-between text-xs text-slate-400">
            <span id="ai-prompt-stats" class="font-mono text-[11px]">0 characters • 0 words</span>
            <span id="ai-prompt-sync-indicator" class="text-[11px] text-emerald-400 font-mono flex items-center gap-1">
              <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              Synchronized with active gauge
            </span>
          </div>

          <!-- Blank State Notice (shown if file is empty) -->
          <div id="ai-prompt-empty-notice" class="hidden p-4 rounded-xl bg-amber-950/20 border border-amber-500/30 text-amber-200 text-xs flex items-start space-x-3">
            <span class="text-lg">ℹ️</span>
            <div class="space-y-1">
              <p class="font-semibold text-amber-300">File <code class="bg-amber-950/60 px-1 py-0.5 rounded font-mono">ai-prompt.txt</code> is currently empty</p>
              <p class="text-slate-400 text-[11px]">You can paste your AI contest prompt directly into the box below or write into <code class="text-slate-300 font-mono">ai-prompt.txt</code> in your project directory and click "Reload".</p>
            </div>
          </div>

          <!-- Text Container / Textarea -->
          <div class="flex-1 min-h-[260px] relative rounded-xl border border-slate-700 bg-slate-950 overflow-hidden flex flex-col focus-within:border-purple-500 transition-colors shadow-inner">
            <textarea id="ai-prompt-textarea" 
                      placeholder="Paste or write your AI prompt here, or save it in ai-prompt.txt..."
                      class="w-full flex-1 p-4 bg-transparent text-slate-100 font-mono text-xs leading-relaxed resize-none focus:outline-none placeholder-slate-600 select-text overflow-y-auto"></textarea>
          </div>
        </div>

        <!-- Footer Actions -->
        <div class="px-6 py-3 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between shrink-0">
          <div class="text-[11px] text-slate-400 flex items-center gap-1.5">
            <span>💡</span>
            <span>Switching gauges updates the prompt directive and joinery formulas instantly.</span>
          </div>

          <div class="flex items-center space-x-2">
            <button id="ai-prompt-btn-copy" class="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shadow-lg shadow-purple-600/30 active:scale-95">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"/></svg>
              <span id="ai-prompt-copy-text">Copy Prompt to Clipboard</span>
            </button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(modal);
    this.renderThicknessButtons();
    this.bindEvents();
    this.loadPromptFile();
  }

  renderThicknessButtons() {
    const container = document.getElementById('ai-prompt-thickness-buttons');
    if (!container) return;

    const currentThickness = AppState.getState().materialThickness;
    const thicknesses = [1.0, 2.0, 3.0, 4.0, 5.0];

    container.innerHTML = thicknesses.map(t => {
      const key = t.toFixed(1);
      const isActive = Math.abs(currentThickness - t) < 0.05;
      const activeClasses = 'bg-amber-500 text-slate-950 font-bold shadow shadow-amber-500/30';
      const inactiveClasses = 'text-slate-400 hover:text-slate-200 hover:bg-slate-800 font-medium';
      
      return `
        <button type="button" 
                data-thickness="${key}"
                class="ai-prompt-gauge-btn px-2.5 py-1 rounded text-xs font-mono transition-all duration-150 ${isActive ? activeClasses : inactiveClasses}">
          ${key} mm
        </button>
      `;
    }).join('');

    // Rebind button click events
    container.querySelectorAll('.ai-prompt-gauge-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const t = parseFloat(e.currentTarget.getAttribute('data-thickness'));
        AppState.setState({ materialThickness: t });
        Toast.show(`AI Prompt updated for ${t.toFixed(1)} mm material! 📏`, '⚡');
      });
    });

    this.updateGaugeBadge(currentThickness);
  }

  updateGaugeBadge(thickness) {
    const badge = document.getElementById('ai-prompt-gauge-badge');
    if (!badge) return;
    const prof = MATERIAL_PROFILES[thickness.toFixed(1)] || MATERIAL_PROFILES['3.0'];
    badge.innerHTML = `
      <span class="font-semibold text-amber-300">Gauge: ${thickness.toFixed(1)} mm</span> 
      <span class="text-slate-400">(${prof.name.split('(')[1]?.replace(')', '') || 'Custom'})</span>
      <span class="text-sky-400">Kerf: ${prof.kerf.toFixed(2)}mm</span> • 
      <span class="text-emerald-400">Fit: +${prof.clearance.toFixed(2)}mm</span>
    `;
  }

  bindEvents() {
    const modal = document.getElementById(this.modalId);
    document.getElementById('ai-prompt-btn-close')?.addEventListener('click', () => this.close());
    modal?.addEventListener('click', (e) => {
      if (e.target === modal) this.close();
    });

    document.getElementById('ai-prompt-btn-reload')?.addEventListener('click', () => {
      this.loadPromptFile();
      Toast.show('Reloaded ai-prompt.txt', '🔄');
    });

    const textarea = document.getElementById('ai-prompt-textarea');
    textarea?.addEventListener('input', () => {
      this.updateStats();
    });

    document.getElementById('ai-prompt-btn-copy')?.addEventListener('click', () => this.copyToClipboard());

    // Subscribe to AppState changes (e.g. from navbar thickness selector or modal buttons)
    AppState.subscribe((state) => {
      this.onThicknessChanged(state.materialThickness);
    });
  }

  onThicknessChanged(thickness) {
    this.renderThicknessButtons();
    this.updateGaugeBadge(thickness);

    if (this.rawPromptText) {
      const updatedPrompt = this.transformPromptForThickness(this.rawPromptText, thickness);
      this.currentPromptText = updatedPrompt;

      const textarea = document.getElementById('ai-prompt-textarea');
      if (textarea) {
        textarea.value = updatedPrompt;
      }
      this.updateStats();
    }
  }

  transformPromptForThickness(rawText, thickness) {
    if (!rawText) return '';

    const prof = MATERIAL_PROFILES[thickness.toFixed(1)] || MATERIAL_PROFILES['3.0'];
    const tVal = prof.thickness.toFixed(1);
    const kerfVal = prof.kerf.toFixed(2);
    const clrVal = prof.clearance.toFixed(2);
    const slotFitVal = (prof.thickness + prof.clearance).toFixed(2);

    const banner = 
`# ==============================================================================
# 🎯 ACTIVE TARGET SPECIFICATION (SELECTED MATERIAL GAUGE: ${tVal} mm)
# ==============================================================================
# • TARGET SHEET THICKNESS : ${tVal} mm
# • MATERIAL PROFILE       : ${prof.name}
# • LASER KERF COMPENSATION: ${kerfVal} mm
# • SLOT CLEARANCE TOLERANCE: ${clrVal} mm
# • PARAMETRIC MORTISE FIT : (t || ${tVal}) + (clr || ${clrVal}) => ${slotFitVal} mm slot opening
# • MATCHING TENON TAB     : Width = Slot Length | Depth = ${tVal} mm (or t + 0.2 mm)
# • INTEGER DIMENSIONS ONLY: Millimeters are small units; all board widths, lengths, heights,
#                            and [X, Y, Z] positions MUST be ROUND INTEGER NUMBERS (e.g. 30, 38, 150),
#                            NEVER floating decimals (avoid 30.27, 38.41). Only sheet thickness has decimals.
#
# 👉 DIRECTIVE FOR AI GENERATION:
# Please optimize this model's default geometry specifically for ${tVal} mm sheet thickness!
# Ensure all generate2D functions default to generate2D(t = ${tVal}, kerf = ${kerfVal}, clr = ${clrVal}).
# All slots must accommodate ${tVal} mm material while remaining fully parametric.
# ==============================================================================
`;

    // Strip any previously injected target specification banner
    let updated = rawText.replace(/# ={70,}\r?\n# 🎯 ACTIVE TARGET SPECIFICATION[\s\S]*?# ={70,}\r?\n/g, '');

    // Inject banner cleanly right before Section 1
    const anchor = '## 1. MANDATORY MODULE EXPORT STRUCTURE';
    const splitIdx = updated.indexOf(anchor);
    if (splitIdx !== -1) {
      updated = updated.slice(0, splitIdx) + banner + '\n' + updated.slice(splitIdx);
    } else {
      updated = banner + '\n' + updated;
    }

    // Adapt default function signatures and parametric slot fallbacks
    updated = updated.replace(/generate2D:\s*\(\s*t\s*=\s*[\d.]+\s*,\s*kerf\s*=\s*[\d.]+\s*,\s*clr\s*=\s*[\d.]+\s*\)/g,
      `generate2D: (t = ${tVal}, kerf = ${kerfVal}, clr = ${clrVal})`);

    updated = updated.replace(/generate2D:\s*\(\s*thickness\s*=\s*[\d.]+\s*,\s*kerf\s*=\s*[\d.]+\s*,\s*clearance\s*=\s*[\d.]+\s*\)/g,
      `generate2D: (thickness = ${tVal}, kerf = ${kerfVal}, clearance = ${clrVal})`);

    updated = updated.replace(/\(t\s*\|\|\s*[\d.]+\)\s*\+\s*\(clr\s*\|\|\s*[\d.]+\)/g,
      `(t || ${tVal}) + (clr || ${clrVal})`);

    updated = updated.replace(/desc:\s*'Main cutting sheet \([\d.]+mm[^)]*\)\.'/g,
      `desc: 'Main cutting sheet (${tVal}mm ${prof.name.split('(')[1]?.replace(')', '') || 'sheet'}).'`);

    return updated;
  }

  async loadPromptFile() {
    let content = '';
    const candidates = [
      '/ai-prompt.txt',
      '/ai-promtp.txt',
      'ai-prompt.txt',
      'ai-promtp.txt',
      '/api/prompt'
    ];

    for (const url of candidates) {
      try {
        const resp = await fetch(`${url}?_t=${Date.now()}`);
        if (resp.ok) {
          if (url.includes('/api/prompt')) {
            const data = await resp.json();
            if (data?.content && data.content.trim()) {
              content = data.content.trim();
              break;
            }
          } else {
            const text = await resp.text();
            if (text && !text.includes('<!DOCTYPE html>') && !text.includes('404 — Page Not Found')) {
              content = text.trim();
              break;
            }
          }
        }
      } catch (e) {
        // try next candidate
      }
    }

    this.rawPromptText = content;
    const currentThickness = AppState.getState().materialThickness;
    this.currentPromptText = this.transformPromptForThickness(this.rawPromptText, currentThickness);

    const textarea = document.getElementById('ai-prompt-textarea');
    const emptyNotice = document.getElementById('ai-prompt-empty-notice');

    if (textarea) {
      textarea.value = this.currentPromptText;
    }

    if (emptyNotice) {
      if (!this.rawPromptText) {
        emptyNotice.classList.remove('hidden');
      } else {
        emptyNotice.classList.add('hidden');
      }
    }

    this.renderThicknessButtons();
    this.updateStats();
  }

  updateStats() {
    const textarea = document.getElementById('ai-prompt-textarea');
    const stats = document.getElementById('ai-prompt-stats');
    if (!textarea || !stats) return;

    const val = textarea.value.trim();
    const chars = val.length;
    const words = val ? val.split(/\s+/).length : 0;
    stats.innerText = `${chars.toLocaleString()} characters • ${words.toLocaleString()} words`;
  }

  async copyToClipboard() {
    const textarea = document.getElementById('ai-prompt-textarea');
    const textToCopy = textarea ? textarea.value : this.currentPromptText;

    if (!textToCopy || !textToCopy.trim()) {
      Toast.show('No prompt content to copy yet. Paste or write your prompt in ai-prompt.txt!', '⚠️');
      return;
    }

    try {
      await navigator.clipboard.writeText(textToCopy);
      const copyBtnText = document.getElementById('ai-prompt-copy-text');
      if (copyBtnText) {
        copyBtnText.innerText = '✓ Copied to Clipboard!';
        setTimeout(() => {
          copyBtnText.innerText = 'Copy Prompt to Clipboard';
        }, 2200);
      }
      Toast.show('AI prompt copied to clipboard! ✨', '📋');
    } catch (e) {
      // Fallback
      if (textarea) {
        textarea.select();
        document.execCommand('copy');
        Toast.show('AI prompt copied to clipboard! ✨', '📋');
      }
    }
  }

  async open() {
    const modal = document.getElementById(this.modalId);
    if (modal) {
      modal.classList.remove('hidden');
    }
    const currentThickness = AppState.getState().materialThickness;
    if (!this.rawPromptText) {
      await this.loadPromptFile();
    } else {
      this.onThicknessChanged(currentThickness);
    }
  }

  close() {
    const modal = document.getElementById(this.modalId);
    if (modal) {
      modal.classList.add('hidden');
    }
  }
}

export const aiPromptModal = new AIPromptModal();
