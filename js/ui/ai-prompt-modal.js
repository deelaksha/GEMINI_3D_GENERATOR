/**
 * AI Prompt & Contest Context Modal Component
 * Loads and renders the copyable content of ai-prompt.txt in the top right corner.
 */

import { Toast } from './toast.js';

export class AIPromptModal {
  constructor() {
    this.modalId = 'ai-prompt-modal';
    this.promptText = '';
    this.mount();
  }

  mount() {
    if (document.getElementById(this.modalId)) return;

    const modal = document.createElement('div');
    modal.id = this.modalId;
    modal.className = 'fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center hidden p-4';
    modal.innerHTML = `
      <div class="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-3xl max-h-[88vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
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

        <!-- Prompt Content Area -->
        <div class="flex-1 overflow-y-auto p-6 flex flex-col space-y-3 bg-slate-950/40">
          <div class="flex items-center justify-between text-xs text-slate-400">
            <span id="ai-prompt-stats" class="font-mono text-[11px]">0 characters • 0 words</span>
            <span class="text-[11px] text-slate-500 font-mono">Ready to copy</span>
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
          <div class="flex-1 min-h-[260px] relative rounded-xl border border-slate-700 bg-slate-950 overflow-hidden flex flex-col focus-within:border-purple-500 transition-colors">
            <textarea id="ai-prompt-textarea" 
                      placeholder="Paste or write your AI prompt here, or save it in ai-prompt.txt..."
                      class="w-full flex-1 p-4 bg-transparent text-slate-100 font-mono text-xs leading-relaxed resize-none focus:outline-none placeholder-slate-600 select-text overflow-y-auto"></textarea>
          </div>
        </div>

        <!-- Footer Actions -->
        <div class="px-6 py-3 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between shrink-0">
          <div class="text-[11px] text-slate-400 flex items-center gap-1.5">
            <span>💡</span>
            <span>Clicking "Copy Prompt" copies the entire text to your clipboard.</span>
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
    this.bindEvents();
    this.loadPromptFile();
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

    this.promptText = content;

    const textarea = document.getElementById('ai-prompt-textarea');
    const emptyNotice = document.getElementById('ai-prompt-empty-notice');

    if (textarea) {
      textarea.value = this.promptText;
    }

    if (emptyNotice) {
      if (!this.promptText) {
        emptyNotice.classList.remove('hidden');
      } else {
        emptyNotice.classList.add('hidden');
      }
    }

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
    const textToCopy = textarea ? textarea.value : this.promptText;

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
    await this.loadPromptFile();
  }

  close() {
    const modal = document.getElementById(this.modalId);
    if (modal) {
      modal.classList.add('hidden');
    }
  }
}

export const aiPromptModal = new AIPromptModal();
