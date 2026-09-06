/**
 * Interactive In-Browser Code Editor Panel
 * Allows users to write, paste, live preview, and persist 3D JavaScript models directly in the WebUI.
 */

import { DesignParser } from '../services/design-parser.js';
import { DesignService } from '../services/firebase-designs.js';
import { ModelRegistry } from '../models/registry.js';
import { AppState } from '../core/config.js';
import { Toast } from './toast.js';
import { TEMPLATES } from '../models/templates.js';
import { ThumbnailGenerator } from '../services/thumbnail-generator.js';

export class CodeEditorPanel {
  constructor(engine, onModelUpdated) {
    this.engine = engine;
    this.onModelUpdated = onModelUpdated;
    this.editor = null;
    this.isOpen = false;
    this.currentDesignId = null;
    this.currentDesignName = 'Untitled Design';
    this.hasUnsavedChanges = false;

    this.mount();
  }

  mount() {
    // Check if already mounted
    if (document.getElementById('code-editor-drawer')) return;

    const drawer = document.createElement('div');
    drawer.id = 'code-editor-drawer';
    drawer.className = 'fixed top-0 right-0 bottom-0 w-full md:w-[620px] bg-slate-900/98 border-l border-slate-800 shadow-2xl z-50 flex flex-col transform translate-x-full transition-transform duration-300 ease-in-out backdrop-blur';
    drawer.innerHTML = `
      <!-- Panel Header -->
      <div class="px-4 py-3 border-b border-slate-800 bg-slate-950/80 flex items-center justify-between gap-2 shrink-0">
        <div class="flex items-center space-x-2">
          <span class="text-base">⚡</span>
          <div class="flex flex-col">
            <div class="flex items-center gap-2">
              <span class="font-bold text-xs text-slate-300 uppercase tracking-wide">Model:</span>
              <input type="text" id="editor-model-name-input" placeholder="Model Name" 
                     class="bg-slate-900 border border-slate-700 hover:border-slate-600 focus:border-sky-500 rounded px-2 py-0.5 text-xs text-amber-300 font-bold focus:outline-none w-44 transition" />
            </div>
            <span id="editor-model-id-label" class="text-[10px] text-slate-500 font-mono mt-0.5">ID: untitled</span>
          </div>
        </div>

        <div class="flex items-center space-x-1.5 text-xs">
          <!-- New Model Button in Studio -->
          <button id="editor-btn-new-model" class="bg-sky-600 hover:bg-sky-500 text-white font-bold px-2 py-1 rounded text-xs transition flex items-center gap-1 shadow shadow-sky-600/30" title="Create New Model">
            <span class="font-black">+</span><span>New</span>
          </button>

          <!-- Template Selector -->
          <select id="editor-template-picker" class="bg-slate-800 text-slate-300 px-2 py-1 rounded border border-slate-700 text-xs focus:outline-none cursor-pointer">
            <option value="">Load Template...</option>
            <option value="minimal-box">Minimal Box (4 Parts)</option>
            <option value="simple-house">Country House (12 Parts)</option>
            <option value="cathedral">Gothic Cathedral (32 Parts)</option>
          </select>

          <!-- Close Panel -->
          <button id="editor-btn-close" class="p-1 text-slate-400 hover:text-slate-100 rounded hover:bg-slate-800 transition" title="Close Editor">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
      </div>

      <!-- Action Toolbar -->
      <div class="px-4 py-2 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between gap-2 text-xs shrink-0">
        <div class="flex items-center space-x-2">
          <button id="editor-btn-preview" class="bg-emerald-600 hover:bg-emerald-500 text-white font-medium px-3 py-1.5 rounded transition flex items-center gap-1.5 shadow shadow-emerald-600/30">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            <span>Live Preview</span>
            <span class="text-[10px] opacity-75 font-mono">(Ctrl+Enter)</span>
          </button>

          <button id="editor-btn-save" class="bg-sky-600 hover:bg-sky-500 text-white font-medium px-3 py-1.5 rounded transition flex items-center gap-1.5 shadow shadow-sky-600/30">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"/></svg>
            <span>Save</span>
          </button>

          <button id="editor-btn-save-as" class="bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 font-medium px-2.5 py-1.5 rounded transition flex items-center gap-1">
            <span>Save As...</span>
          </button>
        </div>

        <div class="flex items-center space-x-2 text-slate-400">
          <button id="editor-btn-download" class="hover:text-slate-200 p-1" title="Download JavaScript File">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
          </button>
        </div>
      </div>

      <!-- CodeMirror Mount Area -->
      <div id="codemirror-wrapper" class="flex-1 relative overflow-hidden bg-[#1e1e2e]">
        <textarea id="model-code-textarea" class="w-full h-full p-3 font-mono text-xs text-slate-100 bg-transparent border-0 resize-none focus:outline-none"></textarea>
      </div>

      <!-- Diagnostic Error / Warning Banner -->
      <div id="editor-error-panel" class="hidden p-3 bg-rose-950/95 border-t border-rose-800/80 text-rose-200 text-xs shrink-0 max-h-40 overflow-y-auto">
        <div class="flex items-start justify-between gap-2">
          <div class="flex items-start space-x-2">
            <span class="text-rose-400 font-bold">⚠️</span>
            <div>
              <div class="font-bold text-rose-300 flex items-center gap-2">
                <span>Validation Error</span>
                <span id="err-line-badge" class="px-1.5 py-0.2 bg-rose-900 text-rose-100 rounded font-mono text-[10px] cursor-pointer hover:underline">Line --</span>
              </div>
              <p id="err-message" class="text-rose-200 mt-0.5 font-mono text-[11px]"></p>
              <div id="err-suggestion-box" class="mt-1.5 bg-rose-900/40 p-2 rounded border border-rose-800/50 text-[11px]">
                <span class="text-amber-300 font-semibold">💡 Suggested Fix: </span>
                <span id="err-suggestion" class="text-rose-100"></span>
              </div>
            </div>
          </div>
          <button id="btn-dismiss-err" class="text-rose-400 hover:text-rose-100 p-1">&times;</button>
        </div>
      </div>

      <!-- Footer Info -->
      <div class="px-4 py-2 border-t border-slate-800 bg-slate-950/80 text-[11px] text-slate-400 flex items-center justify-between shrink-0 font-mono">
        <div class="flex items-center space-x-3">
          <span id="editor-status-text">Ready</span>
        </div>
        <div class="flex items-center space-x-2">
          <span id="editor-cursor-pos">Ln 1, Col 1</span>
        </div>
      </div>
    `;

    document.body.appendChild(drawer);

    this.mountSaveModal();
    this.mountNewModelModal();
    this.initCodeMirror();
    this.bindEvents();
  }

  mountNewModelModal() {
    if (document.getElementById('new-model-modal')) return;

    const modal = document.createElement('div');
    modal.id = 'new-model-modal';
    modal.className = 'fixed inset-0 bg-slate-950/85 backdrop-blur-sm z-50 flex items-center justify-center hidden p-4';
    modal.innerHTML = `
      <div class="bg-slate-900 border border-slate-700 rounded-2xl p-6 w-full max-w-md shadow-2xl text-slate-100 space-y-4">
        <div class="flex justify-between items-center border-b border-slate-800 pb-3">
          <h3 class="font-bold text-sm uppercase tracking-wide flex items-center gap-2">
            <span class="text-amber-400 text-lg">✨</span>
            <span>Create New Blank Design</span>
          </h3>
          <button id="new-modal-close" class="text-slate-400 hover:text-slate-100 text-lg leading-none">&times;</button>
        </div>

        <div class="space-y-3.5 text-xs">
          <div>
            <label class="block text-slate-300 mb-1.5 font-semibold">Design Name</label>
            <input type="text" id="new-model-name-input" placeholder="e.g. My New Design" 
                   class="w-full bg-slate-950 border border-slate-700 focus:border-sky-500 rounded-lg px-3 py-2 text-slate-100 focus:outline-none font-medium text-sm transition" />
            <p class="text-[11px] text-slate-500 mt-1">Creates a clean blank editor canvas ready for your custom or AI-generated model code.</p>
          </div>
        </div>

        <div class="flex justify-end items-center space-x-2 pt-3 border-t border-slate-800 text-xs">
          <button id="new-modal-cancel" class="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition font-medium">Cancel</button>
          <button id="new-modal-confirm" class="px-4 py-2 rounded-lg bg-gradient-to-r from-sky-500 to-sky-600 hover:from-sky-400 hover:to-sky-500 text-white font-bold transition flex items-center gap-1.5 shadow-lg shadow-sky-500/25">
            <span>⚡</span>
            <span>Create Blank Design</span>
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  mountSaveModal() {
    if (document.getElementById('save-design-modal')) return;

    const modal = document.createElement('div');
    modal.id = 'save-design-modal';
    modal.className = 'fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center hidden';
    modal.innerHTML = `
      <div class="bg-slate-900 border border-slate-700 rounded-xl p-5 w-full max-w-md shadow-2xl text-slate-100 space-y-4">
        <div class="flex justify-between items-center border-b border-slate-800 pb-3">
          <h3 class="font-bold text-sm uppercase tracking-wide flex items-center gap-2">
            <span>💾</span>
            <span id="save-modal-title">Save 3D Design</span>
          </h3>
          <button id="save-modal-close" class="text-slate-400 hover:text-slate-100">&times;</button>
        </div>

        <div class="space-y-3 text-xs">
          <div>
            <label class="block text-slate-400 mb-1 font-medium">Design Name <span class="text-rose-400">*</span></label>
            <input type="text" id="save-input-name" placeholder="e.g. Modern Country Villa 1" 
                   class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-slate-100 focus:outline-none focus:border-sky-500 font-medium" />
          </div>

          <div>
            <label class="block text-slate-400 mb-1 font-medium">Description</label>
            <textarea id="save-input-desc" rows="2" placeholder="Brief notes about part count, interlocking scheme, or version..." 
                      class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-slate-100 focus:outline-none focus:border-sky-500 resize-none"></textarea>
          </div>
        </div>

        <div class="flex justify-end items-center space-x-2 pt-2 border-t border-slate-800 text-xs">
          <button id="save-modal-cancel" class="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition">Cancel</button>
          <button id="save-modal-confirm" class="px-4 py-1.5 rounded bg-sky-600 hover:bg-sky-500 text-white font-medium transition flex items-center gap-1.5 shadow">
            <span>Save to Cloud & Storage</span>
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  initCodeMirror() {
    const textarea = document.getElementById('model-code-textarea');
    if (window.CodeMirror) {
      this.editor = window.CodeMirror.fromTextArea(textarea, {
        mode: 'javascript',
        theme: 'dracula',
        lineNumbers: true,
        matchBrackets: true,
        autoCloseBrackets: true,
        indentUnit: 2,
        tabSize: 2,
        lineWrapping: true
      });

      this.editor.on('cursorActivity', () => {
        const pos = this.editor.getCursor();
        const el = document.getElementById('editor-cursor-pos');
        if (el) el.innerText = `Ln ${pos.line + 1}, Col ${pos.ch + 1}`;
      });

      this.editor.on('change', () => {
        this.hasUnsavedChanges = true;
        const status = document.getElementById('editor-status-text');
        if (status) status.innerText = 'Unsaved changes';
      });

      // Keyboard shortcut: Ctrl+Enter to preview
      this.editor.addKeyMap({
        'Ctrl-Enter': () => this.triggerLivePreview(),
        'Cmd-Enter': () => this.triggerLivePreview(),
        'Ctrl-S': () => this.promptSave(),
        'Cmd-S': () => this.promptSave()
      });
    }
  }

  bindEvents() {
    // Open/Close
    document.getElementById('editor-btn-close')?.addEventListener('click', () => this.close());
    document.getElementById('btn-dismiss-err')?.addEventListener('click', () => this.hideError());

    // Error Line click jumps to editor line
    document.getElementById('err-line-badge')?.addEventListener('click', (e) => {
      const lineText = e.target.innerText.match(/\d+/);
      if (lineText && this.editor) {
        const line = parseInt(lineText[0], 10) - 1;
        this.editor.setCursor(line, 0);
        this.editor.focus();
      }
    });

    // Preview
    document.getElementById('editor-btn-preview')?.addEventListener('click', () => this.triggerLivePreview());

    // Save
    document.getElementById('editor-btn-save')?.addEventListener('click', () => {
      if (this.currentDesignId) {
        this.saveCurrentDesign();
      } else {
        this.promptSave();
      }
    });

    document.getElementById('editor-btn-save-as')?.addEventListener('click', () => this.promptSave(true));

    // Download JS
    document.getElementById('editor-btn-download')?.addEventListener('click', () => {
      const code = this.getCode();
      const blob = new Blob([code], { type: 'text/javascript' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${this.currentDesignId || 'design'}.js`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      Toast.show('Downloaded JavaScript file', '📥');
    });

    // Template picker
    document.getElementById('editor-template-picker')?.addEventListener('change', (e) => {
      const val = e.target.value;
      if (!val) return;
      this.loadTemplate(val);
      e.target.value = '';
    });

    // Model name header input in studio
    const editorNameInput = document.getElementById('editor-model-name-input');
    if (editorNameInput) {
      editorNameInput.addEventListener('input', (e) => {
        this.currentDesignName = e.target.value.trim();
        this.hasUnsavedChanges = true;
      });
    }

    // New Model button in studio header
    document.getElementById('editor-btn-new-model')?.addEventListener('click', () => this.promptNewModel());

    // New Model Modal events
    document.getElementById('new-modal-close')?.addEventListener('click', () => this.closeNewModelModal());
    document.getElementById('new-modal-cancel')?.addEventListener('click', () => this.closeNewModelModal());
    document.getElementById('new-modal-confirm')?.addEventListener('click', () => this.confirmNewModel());
    document.getElementById('new-model-name-input')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        this.confirmNewModel();
      }
    });

    // Save Modal events
    document.getElementById('save-modal-close')?.addEventListener('click', () => this.closeSaveModal());
    document.getElementById('save-modal-cancel')?.addEventListener('click', () => this.closeSaveModal());
    document.getElementById('save-modal-confirm')?.addEventListener('click', () => this.confirmSaveModal());
  }

  open(code = null, designMeta = null) {
    const drawer = document.getElementById('code-editor-drawer');
    if (drawer) {
      drawer.classList.remove('translate-x-full');
      this.isOpen = true;
    }
    this.hideError();

    if (designMeta) {
      this.currentDesignId = designMeta.id;
      this.currentDesignName = designMeta.name;
    }

    if (code !== null && code !== undefined) {
      this.setCode(code);
      this.updateDesignBadge();
      if (this.editor) {
        setTimeout(() => {
          this.editor.refresh();
          this.editor.focus();
        }, 200);
      }
    } else if (!designMeta?.isBlank && (!this.getCode() || !this.getCode().trim())) {
      // Empty editor: dynamically resolve source code for active model
      const currentModel = ModelRegistry.getActiveModel();
      const targetId = (designMeta && designMeta.id) || (currentModel ? currentModel.id : null);
      if (targetId) {
        this.fetchModelSource(targetId).then(src => {
          if (src) {
            this.setCode(src);
            if (!this.currentDesignId) this.currentDesignId = targetId;
            if (!this.currentDesignName && currentModel) this.currentDesignName = currentModel.name;
            this.updateDesignBadge();
          }
          if (this.editor) setTimeout(() => this.editor.refresh(), 200);
        });
      }
    } else {
      this.updateDesignBadge();
      if (this.editor) {
        setTimeout(() => this.editor.refresh(), 200);
      }
    }
  }

  async fetchModelSource(modelId) {
    if (!modelId) return null;

    // 1. Check if design exists in DesignService
    try {
      const d = await DesignService.getDesign(modelId);
      if (d && d.jsCode && d.jsCode.trim()) return d.jsCode;
    } catch (e) {}

    // 2. Fetch known static model source files
    const fileMap = {
      'classic-sports-coupe': 'js/models/my-model.js',
      'car-j4ir': 'js/models/my-model.js',
      'football-stadium': 'js/models/my-model.js',
      'cathedral': 'js/models/cathedral.js',
      'simple-house': 'js/models/simple-house.js'
    };

    if (fileMap[modelId]) {
      try {
        const resp = await fetch(fileMap[modelId]);
        if (resp.ok) {
          return await resp.text();
        }
      } catch (e) {
        console.warn(`[CodeEditor] Could not fetch static file for ${modelId}:`, e);
      }
    }

    // 3. Fallback to TEMPLATES definition
    if (TEMPLATES[modelId]) {
      return TEMPLATES[modelId].code;
    }

    return null;
  }

  close() {
    const drawer = document.getElementById('code-editor-drawer');
    if (drawer) {
      drawer.classList.add('translate-x-full');
      this.isOpen = false;
    }
  }

  toggle() {
    if (this.isOpen) this.close();
    else this.open();
  }

  getCode() {
    if (this.editor) return this.editor.getValue();
    const ta = document.getElementById('model-code-textarea');
    return ta ? ta.value : '';
  }

  setCode(code) {
    if (this.editor) {
      this.editor.setValue(code);
    } else {
      const ta = document.getElementById('model-code-textarea');
      if (ta) ta.value = code;
    }
    this.hasUnsavedChanges = false;
    const status = document.getElementById('editor-status-text');
    if (status) status.innerText = 'Ready';
  }

  updateDesignBadge() {
    const nameInput = document.getElementById('editor-model-name-input');
    if (nameInput) {
      nameInput.value = this.currentDesignName || '';
    }
    const idLabel = document.getElementById('editor-model-id-label');
    if (idLabel) {
      idLabel.innerText = `ID: ${this.currentDesignId || 'untitled'}`;
    }
  }

  promptNewModel() {
    const modal = document.getElementById('new-model-modal');
    if (!modal) return;
    const input = document.getElementById('new-model-name-input');
    if (input) {
      input.value = `Custom Model ${Math.floor(Math.random() * 900 + 100)}`;
    }
    modal.classList.remove('hidden');
    setTimeout(() => {
      input?.focus();
      input?.select();
    }, 80);
  }

  closeNewModelModal() {
    const modal = document.getElementById('new-model-modal');
    if (modal) modal.classList.add('hidden');
  }

  async confirmNewModel() {
    const input = document.getElementById('new-model-name-input');
    const name = (input?.value || '').trim() || `Design ${Math.floor(Math.random() * 900 + 100)}`;
    const slug = DesignService.generateSlug(name);

    // Completely blank editor canvas — no starter templates, no dummy parts, no categorization
    const code = `/**
 * ${name}
 * Paste your 3D Construction Puzzle Model code below:
 */

`;

    this.closeNewModelModal();
    this.open(code, { id: slug, name, isBlank: true });

    // Set clean status
    const status = document.getElementById('editor-status-text');
    if (status) status.innerText = 'Blank canvas ready — paste model code';
    this.hideError();

    Toast.show(`✨ Blank canvas opened for "${name}"! Ready to paste code.`, '📝');
  }

  async loadTemplate(key) {
    if (TEMPLATES[key]) {
      this.setCode(TEMPLATES[key].code);
      this.currentDesignId = TEMPLATES[key].id;
      this.currentDesignName = TEMPLATES[key].name;
      this.updateDesignBadge();
      Toast.show(`Loaded template: ${TEMPLATES[key].name}`, '📋');
      await this.triggerLivePreview();
      return;
    }

    // Dynamic fetch for other templates
    if (key === 'simple-house' || key === 'cathedral') {
      try {
        const resp = await fetch(`js/models/${key}.js`);
        if (resp.ok) {
          const code = await resp.text();
          this.setCode(code);
          this.currentDesignId = key;
          this.currentDesignName = key === 'cathedral' ? 'Gothic Cathedral' : 'Country Gable House';
          this.updateDesignBadge();
          Toast.show(`Loaded template: ${this.currentDesignName}`, '📋');
          await this.triggerLivePreview();
          return;
        }
      } catch (e) {
        Toast.show('Error loading template: ' + e.message, '⚠️');
      }
    }
  }

  async triggerLivePreview() {
    const code = this.getCode();
    this.hideError();

    const status = document.getElementById('editor-status-text');

    if (!code || !code.trim()) {
      if (status) status.innerText = 'Editor is empty';
      Toast.show('Editor is empty. Load a template or write code to preview.', 'ℹ️');
      return null;
    }

    if (status) status.innerText = 'Parsing & validating...';

    const result = await DesignParser.parseAndValidate(code);
    if (!result.success) {
      this.showError(result.error);
      if (status) status.innerText = 'Syntax / Schema error';
      return null;
    }

    try {
      const modelData = result.modelData;
      // Register into ModelRegistry
      const registered = await ModelRegistry.registerDynamicDesign({
        id: modelData.id,
        name: modelData.name,
        modelData
      });

      // Update active model in AppState without page refresh
      AppState.setState({ 
        activeModelId: modelData.id, 
        selectedPartId: modelData.parts[0]?.id || null,
        activeStep: 0 
      });

      if (this.onModelUpdated) {
        this.onModelUpdated(registered || modelData);
      }

      if (status) status.innerText = `Preview Active (${modelData.parts.length} parts)`;
      Toast.show(`Rendered: ${modelData.name} (${modelData.parts.length} parts)`, '✨');
      return modelData;
    } catch (err) {
      console.error('[CodeEditor] Render error:', err);
      this.showError({
        message: 'Runtime render failed: ' + err.message,
        line: 1,
        suggestion: 'Verify that all geometry points and cutouts are valid finite numbers.'
      });
      return null;
    }
  }

  showError(err) {
    const panel = document.getElementById('editor-error-panel');
    if (!panel) return;

    document.getElementById('err-line-badge').innerText = `Line ${err.line || 1}${err.column ? `:${err.column}` : ''}`;
    document.getElementById('err-message').innerText = err.message;
    document.getElementById('err-suggestion').innerText = err.suggestion || 'Review model specifications.';
    panel.classList.remove('hidden');

    if (this.editor && err.line) {
      this.editor.setCursor(err.line - 1, (err.column || 1) - 1);
    }
  }

  hideError() {
    const panel = document.getElementById('editor-error-panel');
    if (panel) panel.classList.add('hidden');
  }

  promptSave(isSaveAs = false) {
    const modal = document.getElementById('save-design-modal');
    if (!modal) return;

    const nameInput = document.getElementById('save-input-name');
    const title = document.getElementById('save-modal-title');

    title.innerText = isSaveAs ? 'Save Design Copy As...' : 'Save Design';
    nameInput.value = isSaveAs ? `${this.currentDesignName} (Copy)` : (this.currentDesignName !== 'Untitled Design' ? this.currentDesignName : '');
    
    modal.classList.remove('hidden');
    nameInput.focus();
    this.isSaveAsMode = isSaveAs;
  }

  closeSaveModal() {
    const modal = document.getElementById('save-design-modal');
    if (modal) modal.classList.add('hidden');
  }

  async captureThumbnail(modelData = null) {
    try {
      if (this.engine?.renderer && this.engine?.scene && this.engine?.camera) {
        // Ensure the scene is synchronously rendered to the WebGL canvas before reading
        this.engine.renderer.render(this.engine.scene, this.engine.camera);
        const dataUrl = this.engine.renderer.domElement.toDataURL('image/jpeg', 0.85);
        const isBlack = await ThumbnailGenerator.isBlackOrEmpty(dataUrl);
        if (!isBlack) {
          return dataUrl;
        }
      }
    } catch (e) {
      console.warn('[CodeEditor] Canvas capture failed, trying ThumbnailGenerator:', e);
    }

    if (modelData) {
      try {
        const genRes = await ThumbnailGenerator.generateThumbnail(modelData);
        if (genRes?.thumbnail) return genRes.thumbnail;
      } catch (err) {
        console.warn('[CodeEditor] ThumbnailGenerator fallback error:', err);
      }
    }
    return null;
  }

  async confirmSaveModal() {
    const name = document.getElementById('save-input-name').value.trim();
    const category = document.getElementById('save-input-cat').value.trim();
    const desc = document.getElementById('save-input-desc').value.trim();

    if (!name) {
      Toast.show('Please enter a design name.', '⚠️');
      return;
    }

    const previewModel = await this.triggerLivePreview();
    if (!previewModel) {
      Toast.show('Fix errors before saving.', '⚠️');
      return;
    }

    const designId = (this.isSaveAsMode || !this.currentDesignId) ? DesignService.generateSlug(name) : this.currentDesignId;
    const thumbnail = await this.captureThumbnail(previewModel);

    try {
      const saved = await DesignService.saveDesign({
        id: designId,
        name,
        category: category || previewModel.category || 'General',
        description: desc || previewModel.description || '',
        jsCode: this.getCode(),
        modelData: previewModel,
        thumbnail
      });

      this.currentDesignId = saved.id;
      this.currentDesignName = saved.name;
      this.hasUnsavedChanges = false;
      this.updateDesignBadge();
      this.closeSaveModal();

      Toast.show(`Design "${saved.name}" saved successfully!`, '☁️');
    } catch (err) {
      Toast.show('Failed to save design: ' + err.message, '⚠️');
    }
  }

  async saveCurrentDesign() {
    const previewModel = await this.triggerLivePreview();
    if (!previewModel) return;

    const thumbnail = await this.captureThumbnail(previewModel);
    try {
      const saved = await DesignService.saveDesign({
        id: this.currentDesignId,
        name: this.currentDesignName,
        category: previewModel.category || 'General',
        description: previewModel.description || '',
        jsCode: this.getCode(),
        modelData: previewModel,
        thumbnail
      });

      this.hasUnsavedChanges = false;
      const status = document.getElementById('editor-status-text');
      if (status) status.innerText = `Saved (v${saved.version})`;
      Toast.show(`Saved "${saved.name}" (v${saved.version})`, '💾');
    } catch (err) {
      Toast.show('Save failed: ' + err.message, '⚠️');
    }
  }
}
