/**
 * AI Design Canvas.
 *
 * 1 Describe -> 2 project-aware prompt (server-built from the engine's real constants) -> external AI ->
 * 3 paste JSON into the editor -> Compile (server: parse, validate, existing generator, joins, validation,
 * nesting) -> 4 preview with the studio's own 3D / 2D engines. The pasted text is only ever sent to the
 * compiler as data; nothing is evaluated in the page.
 */
/* global CodeMirror */
import { Api, ApiError } from '../studio/api.js';
import { Viewport3D } from '../studio/viewport3d.js';
import { Sheet2D } from '../studio/sheet2d.js';
import { bindFullscreen } from '../studio/fullscreen.js';
import { CompileLoader } from './compile-loader.js?v=2.15';
import { AssemblyPreview } from './assembly-preview.js?v=2.15';
import { renderDraftingSvg, renderDraftingGuide, formatDraftingSpecsText, bindCadInspectorEvents } from '../studio/drafting.js?v=2.5';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = (v, n = 1) => (Math.round(v * 10 ** n) / 10 ** n).toString();
const narrow = matchMedia('(max-width: 1100px)');
const DRAFT_KEY = 'board-canvas-draft';

const S = { spec: null, result: null, compiledSource: '', selected: null, savedId: null, compiling: false, marks: [], draftingMode: 'all' };

// ---------------------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------------------
function toast(msg, err = false, ms = err ? 6500 : 2800) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = `toast show${err ? ' err' : ''}`;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.className = 'toast'), ms);
}
function reportError(e) {
  console.error(e);
  const first = e instanceof ApiError ? (e.issues.find((i) => i.severity === 'error') || e.issues[0]) : null;
  toast(`${e.message}${first?.message ? ' — ' + first.message : ''}`, true);
}

// ---------------------------------------------------------------------------
// Editor (CodeMirror 5, same library the legacy workbench uses)
// ---------------------------------------------------------------------------
const cm = CodeMirror($('#editor'), {
  mode: { name: 'javascript', json: true }, lineNumbers: true, matchBrackets: true, autoCloseBrackets: true,
  styleActiveLine: true, tabSize: 2, indentUnit: 2, lineWrapping: false, gutters: ['cv-marks', 'CodeMirror-linenumbers'],
  extraKeys: {
    'Ctrl-Enter': () => compile(true), 'Cmd-Enter': () => compile(true),
    'Shift-Alt-F': () => formatCode(), 'Ctrl-S': () => save(!!S.savedId), 'Cmd-S': () => save(!!S.savedId)
  },
  placeholder: 'Paste the JSON the AI returned here…'
});
try { const d = localStorage.getItem(DRAFT_KEY); if (d) cm.setValue(d); } catch (e) { /* storage unavailable */ }

function stripForParse(text) {
  // mirror of the server's tolerance for AI replies: fenced block, comments, trailing commas
  const m = text.match(/```(?:json|jsonc|json5)?[ \t]*\n([\s\S]*?)```/i);
  let s = m ? m[1] : text;
  const first = s.indexOf('{'), last = s.lastIndexOf('}');
  if (first > 0 && last > first && s.slice(0, first).trim()) s = s.slice(first, last + 1);
  let out = '', inStr = false;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (inStr) { out += c; if (c === '\\') { out += s[++i] ?? ''; } else if (c === '"') inStr = false; continue; }
    if (c === '"') { inStr = true; out += c; continue; }
    if (c === '/' && s[i + 1] === '/') { while (i < s.length && s[i] !== '\n') i++; out += '\n'; continue; }
    if (c === '/' && s[i + 1] === '*') { i += 2; while (i < s.length && !(s[i] === '*' && s[i + 1] === '/')) i++; i++; continue; }
    out += c;
  }
  return out.replace(/,(\s*[}\]])/g, '$1');
}

function parseCode() {
  return JSON.parse(stripForParse(cm.getValue()));
}

/** 2-space JSON with number-only arrays kept on one line ([x, y, z] stays readable; strings untouched). */
function pretty(data) {
  return JSON.stringify(data, null, 2).replace(/\[\s*(-?[\d.eE+]+(?:\s*,\s*-?[\d.eE+]+)*)\s*\]/g,
    (_m, inner) => `[${inner.split(/\s*,\s*/).join(', ')}]`);
}

function formatCode() {
  try {
    cm.setValue(pretty(parseCode()));
    toast('Formatted');
  } catch (e) { toast(`Cannot format: ${e.message}`, true); }
}

/** Character range {from, to} of the JSON object that defines `id` (scans braces, skipping strings). */
function objectRange(text, id) {
  const re = new RegExp(`"id"\\s*:\\s*"${id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"`);
  const m = re.exec(text);
  if (!m) return null;
  let depth = 0, start = -1;
  for (let i = m.index; i >= 0; i--) {
    const c = text[i];
    if (c === '}') depth++;
    else if (c === '{') { if (depth === 0) { start = i; break; } depth--; }
  }
  if (start < 0) return null;
  let inStr = false;
  depth = 0;
  for (let i = start; i < text.length; i++) {
    const c = text[i];
    if (inStr) { if (c === '\\') i++; else if (c === '"') inStr = false; continue; }
    if (c === '"') inStr = true;
    else if (c === '{') depth++;
    else if (c === '}' && --depth === 0) return { from: start, to: i + 1 };
  }
  return null;
}

let boardMark = null;
function highlightBoard(id, scroll = true) {
  boardMark?.clear();
  boardMark = null;
  if (!id) return;
  const r = objectRange(cm.getValue(), id);
  if (!r) return;
  const from = cm.posFromIndex(r.from), to = cm.posFromIndex(r.to);
  boardMark = cm.markText(from, to, { className: 'cm-board-sel' });
  if (scroll) cm.scrollIntoView({ from, to }, 60);
}

function boardAtCursor() {
  if (!S.result?.model3d) return null;
  const text = cm.getValue(), idx = cm.indexFromPos(cm.getCursor());
  for (const c of S.result.model3d.components) {
    const r = objectRange(text, c.id);
    if (r && idx >= r.from && idx <= r.to) return c.id;
  }
  return null;
}

cm.on('cursorActivity', () => {
  clearTimeout(cm._cursorT);
  cm._cursorT = setTimeout(() => {
    const id = boardAtCursor();
    if (id && id !== S.selected) select(id, 'code');
  }, 250);
});
cm.on('change', () => {
  try { localStorage.setItem(DRAFT_KEY, cm.getValue()); } catch (e) { /* ignore */ }
  setStatus('dirty');
});

// ---------------------------------------------------------------------------
// Prompt
// ---------------------------------------------------------------------------
function fillThickness() {
  const ts = S.spec.materials.plywood.thicknesses;     // the default material's stock thicknesses
  $('#in-thickness').innerHTML = ts.map((t) => `<option ${t === 18 ? 'selected' : ''}>${t}</option>`).join('');
}

async function generatePrompt() {
  const title = $('#in-title').value.trim();
  if (!title) { $('#in-title').focus(); return toast('Enter a product title first', true); }
  try {
    const r = await Api.canvasPrompt({ title, requirements: $('#in-req').value,
      thickness: parseFloat($('#in-thickness').value), joinery: 'interlocking' });   // always glue-free
    $('#out-prompt').value = r.prompt;
    $('#btn-copy-prompt').disabled = false;
    $('#prompt-meta').innerHTML = `${r.prompt.length.toLocaleString()} characters · self-contained, works in any AI chat. Paste the AI’s JSON reply into the editor and click <b>Compile</b>.`;
    if (narrow.matches) setPane('prompt');
    toast('Prompt ready — copy it into your AI');
  } catch (e) { reportError(e); }
}

function showPrompt(prompt, meta) {
  $('#out-prompt').value = prompt;
  $('#btn-copy-prompt').disabled = false;
  $('#prompt-meta').innerHTML = meta;
  if (narrow.matches) setPane('prompt');
}

async function repairPrompt() {
  const source = cm.getValue();
  if (!source.trim()) return toast('Paste the AI’s code into the editor first', true);
  const btn = $('#btn-repair-prompt');
  const btnBanner = $('#btn-banner-copy-repair');
  if (btn) btn.disabled = true;
  if (btnBanner) btnBanner.disabled = true;
  try {
    const r = await Api.canvasRepairPrompt(source);
    showPrompt(r.prompt, `Follow-up prompt with ${r.problems} problem(s). Paste it into the same AI chat, then paste its reply into the editor and click <b>Compile</b>.`);
    if (r.problems > 0 || r.prompt) {
      await copyText(r.prompt, 'Fix prompt');
      toast(`Copied follow-up fix prompt (${r.problems} issue${r.problems === 1 ? '' : 's'}) to clipboard! Paste it into your AI chat.`);
    } else {
      toast('No problems to fix — all checks passed!');
    }
  } catch (e) {
    reportError(e);
  } finally {
    if (btn) btn.disabled = false;
    if (btnBanner) btnBanner.disabled = false;
  }
}

async function integerFixPrompt() {
  const source = cm.getValue();
  if (!source.trim()) return toast('Paste the AI’s code into the editor first', true);
  try {
    const r = await Api.canvasIntegerFixPrompt(source);
    if (r.count > 0 || r.prompt) {
      showPrompt(r.prompt, `Follow-up prompt to fix ${r.count} floating-point dimension(s). Paste it into your AI chat to round all dimensions to clean integers.`);
      await copyText(r.prompt, 'Integer fix prompt');
      toast(`Copied prompt to fix ${r.count} floating-point dimension(s)! Paste into your AI chat.`);
    } else {
      toast('All dimensions in this design are already clean integers!');
    }
  } catch (e) {
    reportError(e);
  }
}

async function changePrompt() {
  const source = cm.getValue();
  const change = $('#in-req').value.trim();
  if (!source.trim()) return toast('Paste or open the current design in the editor first', true);
  if (!change) { $('#in-req').focus(); return toast('Describe the change in the requirements box', true); }
  const btn = $('#btn-change-prompt');
  if (btn) btn.disabled = true;
  try {
    const r = await Api.canvasUpdatePrompt(source, change);
    showPrompt(r.prompt, 'Change prompt: the AI is asked to modify only the affected boards and keep the rest. Paste its reply into the editor and click <b>Compile</b>.');
    await copyText(r.prompt, 'Update prompt');
    toast('Copied update prompt to clipboard! Paste into your AI chat.');
  } catch (e) {
    reportError(e);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function copyText(text, what) {
  try { await navigator.clipboard.writeText(text); toast(`${what} copied`); }
  catch (e) {
    const ta = Object.assign(document.createElement('textarea'), { value: text });
    document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove();
    toast(`${what} copied`);
  }
}

// ---------------------------------------------------------------------------
// Compile
// ---------------------------------------------------------------------------
// while compiling, the view shows the live assembly: picking would hit the (hidden) previous model
const view3d = new Viewport3D($('#canvas3d'), { onSelect: (id) => !loader.active && select(id, 'view'),
  onHover: (id, e) => tip($('#tip-3d'), loader.active ? null : id, e) });
const sheet2d = new Sheet2D($('#svg2d'), { onSelect: (id) => select(id, 'view'), onHover: (id, e) => tip($('#tip-2d'), id, e), scalebar: $('#scalebar-2d') });

function tip(el, id, e) {
  const c = id && S.result?.model3d?.components.find((x) => x.id === id);
  if (!c || !e) { el.style.display = 'none'; return; }
  const r = el.parentElement.getBoundingClientRect();
  const b = c.world_bounds;
  el.innerHTML = `<b class="mono">${esc(id)}</b> · ${esc(c.name)}<br><span class="muted">${[0, 1, 2].map((i) => fmt(b.max[i] - b.min[i])).join(' × ')} mm</span>`;
  el.style.display = 'block';
  el.style.left = `${Math.max(8, Math.min(e.clientX - r.left + 14, r.width - 200))}px`;
  el.style.top = `${e.clientY - r.top + 14}px`;
}

function setStatus(kind, text) {
  const pill = $('#compile-status');
  const map = { dirty: ['', 'Edited — not compiled'], busy: ['cut', 'Compiling…'], ok: ['ok', text], warn: ['warn', text], err: ['err', text] };
  const [cls, t] = map[kind] || ['', text];
  if (kind === 'dirty' && !S.result) { pill.innerHTML = '<span class="dot"></span><span class="txt">Not compiled</span>'; return; }
  pill.innerHTML = `<span class="dot ${cls}"></span><span class="txt">${esc(t)}</span>`;
}

function showStatus(r) {
  const s = r.summary;
  if (!r.model3d) setStatus('err', `${r.diagnostics.filter((d) => d.severity === 'error').length} error(s) — not compiled`);
  else if (r.compiled) setStatus(s.warnings ? 'warn' : 'ok', s.warnings ? `Compiled · ${s.warnings} warning(s)` : `Compiled · ${s.boards} boards · ${s.joined}/${s.joints} joints`);
  else setStatus('err', `${s.errors} error(s)`);
}

const nextFrame = () => new Promise((r) => requestAnimationFrame(() => r()));
const preview = new AssemblyPreview(view3d);
const loader = new CompileLoader($('.view-3d'), { onCancel: () => cancelCompile(), onHide: () => preview.end() });
let compileJob = null;

/** First compile phase, streamed: a Web Worker runs the request and parses the reply, posting the compiler's
 *  real stage events as they arrive, and the preview geometry built from them. Resolves with the same result as
 *  Api.canvasCompile(source, false). */
function compileStream(source, onProgress, onPreview) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL('./compile-worker.js?v=2.15', import.meta.url), { type: 'module' });
    const end = () => { worker.terminate(); compileJob = null; };
    let settled = false;
    compileJob = { cancel: () => { end(); reject(Object.assign(new Error('Compilation cancelled'), { cancelled: true })); } };
    worker.onmessage = ({ data }) => {
      if (data.type === 'progress') return onProgress(data);
      if (data.type === 'preview') return onPreview(data);
      if (data.type === 'preview-done') return settled && worker.terminate();
      if (data.type === 'result' && !data.result.model3d && data.previewPending) {
        // a failed compile can finish before its preview is built: let the worker deliver it (the partial
        // design, errors in red, behind the failure panel); the result is not held back for it
        settled = true;
        compileJob = null;
        setTimeout(() => worker.terminate(), 10000);
        return resolve(data.result);
      }
      end();
      if (data.type === 'result') resolve(data.result);
      else reject(new ApiError(data.status, { error: { message: data.message } }));
    };
    worker.onerror = (e) => { e.preventDefault(); end(); reject(new ApiError(0, { error: { message: 'The compile worker could not start.' } })); };
    worker.postMessage({ source, production: false, timeout: 120000 });
  });
}

function cancelCompile() {
  if (!compileJob || !loader.busy) return;
  S.pending = S.recompile = false;
  compileJob.cancel();
}

/** Why a compile produced no model, as the loader's failure panel shows it. */
function compileFailure(r) {
  const errs = r.diagnostics.filter((d) => d.severity === 'error');
  const first = errs[0] || r.diagnostics[0];
  const title = first?.code === 'COMPILE_TIMEOUT' ? 'Compilation timed out'
    : first?.code === 'JSON_SYNTAX' ? 'The code is not valid JSON'
      : `${errs.length} error${errs.length === 1 ? '' : 's'} stopped the compile`;
  return { title, message: first ? `${first.line ? `Line ${first.line}: ` : ''}${first.message}` : '' };
}

/** Two short requests instead of one long one: geometry + validation first (3D and problems appear right
 *  away), then the cut sheets / cut list. A slow or failed second phase never hides the first result.
 *  An explicit compile (production) shows the compile loader over the preview; background recompiles (auto-fix) only use the status pill. */
/** Replace the editor text with a repaired version (one undoable change) and flash the lines that changed. */
function applySyntaxRepair(fix) {
  cm.replaceRange(fix.source, cm.posFromIndex(0), cm.posFromIndex(cm.getValue().length));
  const lines = [...new Set(fix.changes.map((c) => c.line - 1))].filter((l) => l < cm.lineCount());
  const marks = lines.map((l) => cm.addLineClass(l, 'background', 'cm-fixed-line'));
  setTimeout(() => marks.forEach((h) => cm.removeLineClass(h, 'background', 'cm-fixed-line')), 4000);
  toast(`Fixed the JSON syntax automatically — ${fix.summary}. Press Ctrl+Z to undo.`, false, 7000);
}

async function compile(production = true) {
  let source = cm.getValue();
  if (!source.trim()) return toast('Paste the AI’s code into the editor first', true);
  if (S.compiling) {
    if (source === S.compilingSource) return;    // this exact code is already compiling: never send it twice
    S.recompile = production || S.recompile || false; S.pending = true; return;   // run again when done
  }
  S.compiling = true;
  S.compilingSource = source;
  setStatus('busy');
  $('#btn-compile').disabled = true;
  const show = production;
  const close = () => { loader.hide(); if (narrow.matches && !S.result?.model3d) setPane('code'); };
  if (show) {
    loader.start();
    preview.begin();             // the design assembles in the 3D view as the compiler works through it
    if (narrow.matches) setPane('preview');
    setPreview('3d');
    // full screen for the assembly when the user started the compile (browsers allow it only after a click / key)
    if (navigator.userActivation?.isActive ?? true) fs3d.enter();
  }
  try {
    let serverT = 0, first, repaired = false;
    while (true) {
      first = await compileStream(source,
        (ev) => { serverT = ev.t; if (show) { preview.event(ev); loader.progress(ev, preview.detail(ev)); } },
        (p) => { if (show && loader.active) { preview.show(p); loader.assembling(p.ids.length); } });
      // a JSON syntax error the compiler can repair is fixed in the editor and compiled again, once
      const fix = !first.model3d && !repaired && first.diagnostics[0]?.code === 'JSON_SYNTAX' &&
        first.diagnostics[0].fixes?.find((f) => f.kind === 'repair_json');
      if (!fix || cm.getValue() !== source) break;
      repaired = true;
      applySyntaxRepair(fix);
      source = S.compilingSource = cm.getValue();
    }
    if (show && first.model3d) {
      loader.rendering(serverT);
      await nextFrame();         // let "Rendering" paint before the WebGL build blocks the main thread
    }
    const sameDesign = S.result?.model3d && first.model3d &&
      S.result.model3d.components.map((c) => c.id).join() === first.model3d.components.map((c) => c.id).join();
    S.result = first;
    S.compiledSource = source;
    render(sameDesign || preview.shown);     // the camera the live assembly settled on carries over
    if (first.model3d) preview.end();         // swapped in the same frame as the final model appears
    if (cm.getValue() === source) showStatus(first); else setStatus('dirty');
    if (show) {
      if (first.model3d) {
        await nextFrame();       // the model has been drawn once: reveal it
        const s = first.summary;
        loader.complete(s.errors ? `Compiled with ${s.errors} error${s.errors === 1 ? '' : 's'}` : `Compiled · ${s.boards} boards · ${s.joined}/${s.joints} joints`);
      } else {
        preview.markErrors(first.diagnostics.filter((d) => d.severity === 'error' && d.board).map((d) => d.board));
        loader.fail({ ...compileFailure(first), actions: [['close', 'Close', false, close],
          ['problems', 'Show problems', true, () => { loader.hide(); fs3d.exit(); setPane('code'); $('#diag-list .dg[data-i="0"]')?.click(); }]] });
      }
    }
    if (production && first.model3d && narrow.matches) setPane('preview');
    if (production && first.model3d) {
      setStatus(first.compiled ? 'ok' : 'err', `${$('#compile-status').innerText} · preparing cut sheets…`);
      try {
        const full = await Api.canvasCompile(source, true);
        if (cm.getValue() === source) { S.result = full; render(true); showStatus(full); }
      } catch (e) {
        showStatus(first);
        toast(`3D and checks are ready, but the cut sheets could not be prepared: ${e.message}`, true);
      }
    }
  } catch (e) {
    if (e.cancelled) {
      loader.hide();
      if (S.result && cm.getValue() === S.compiledSource) showStatus(S.result); else setStatus('dirty');
      toast('Compilation cancelled');
    } else {
      setStatus('err', 'Compile failed');
      if (show) {
        console.error(e);
        loader.fail({ title: e.status === 408 ? 'Compilation timed out' : 'Compilation failed', message: e.message,
          actions: [['close', 'Close', false, close], ['retry', 'Retry', true, () => { loader.hide(); compile(true); }]] });
      } else reportError(e);
    }
  } finally {
    S.compiling = false;
    S.compilingSource = null;
    $('#btn-compile').disabled = false;
    if (S.pending) {            // the text changed while compiling: compile the latest version
      const prod = S.recompile;
      S.pending = S.recompile = false;
      compile(prod);
    }
  }
}

function render(keepCamera = false) {
  const r = S.result;
  renderDiagnostics();
  markEditor();
  $('#btn-save').disabled = !r?.model3d;
  $('#btn-import').disabled = !r?.model3d;
  $('#pv-empty').hidden = !!r?.model3d;
  if (r?.model3d) {
    if (!keepCamera) view3d._framed = false;
    view3d.load(r.model3d);
    const s = r.summary;
    $('#pv-summary').textContent = `${s.boards} boards · ${s.joined}/${s.joints} joints${r.layout ? ` · ${r.layout.nesting.sheet_count} sheet(s)` : ''}`;
  }
  if (r?.layout) { sheet2d._fitted = false; sheet2d.load(r.layout, { mode: 'production', states: Object.fromEntries(r.model3d.components.map((c) => [c.id, c.state])) }); }
  if (S.selected && !r?.model3d?.components.some((c) => c.id === S.selected)) S.selected = null;
  select(S.selected, 'render');
}

function renderDiagnostics() {
  const r = S.result;
  const list = $('#diag-list');
  const ds = (r?.diagnostics || []).slice().sort((a, b) => (a.severity === b.severity ? 0 : a.severity === 'error' ? -1 : 1));
  $('#diag-count').textContent = ds.length;
  $('#diag-count').className = `badge ${ds.some((d) => d.severity === 'error') ? 'err' : ds.length ? 'warn' : ''}`;
  const safe = ds.flatMap((d) => (d.fixes || []).filter((f) => f.safe));
  $('#btn-autofix').disabled = !safe.length;
  $('#btn-autofix').innerHTML = `<svg><use href="#i-wand"/></svg>Auto-fix safe issues${safe.length ? ` (${safe.length})` : ''}`;

  const errCount = ds.filter((d) => d.severity === 'error').length;
  const btnRepair = $('#btn-repair-prompt');
  if (btnRepair) {
    btnRepair.disabled = !ds.length;
    btnRepair.classList.toggle('primary', errCount > 0);
    btnRepair.innerHTML = `<svg><use href="#i-copy"/></svg><span>Copy fix prompt${ds.length ? ` (${ds.length})` : ''}</span>`;
  }

  if (!ds.length) {
    list.innerHTML = r?.model3d ? `<div class="dg ok"><span class="dot ok"></span><div><div class="msg">No problems: every board, connection, gap and overlap check passed${r.layout?.ready_for_production ? ', and the design is ready for production' : ''}.</div></div></div>`
      : '<div class="empty">Paste the AI’s code above and click Compile.</div>';
    return;
  }

  const floatIssues = ds.filter((d) => d.code === 'NON_INTEGER_DIMENSION');
  const btnIntegerPrompt = $('#btn-integer-prompt');
  if (btnIntegerPrompt) {
    btnIntegerPrompt.hidden = !floatIssues.length;
    btnIntegerPrompt.innerHTML = `<svg><use href="#i-copy"/></svg><span>Fix floats (${floatIssues.length})</span>`;
  }

  const floatBanner = floatIssues.length ? `
    <div class="diag-banner warn" style="margin-bottom: 8px; border-color: rgba(245, 158, 11, 0.5); background: rgba(245, 158, 11, 0.1);">
      <div class="diag-banner-text">
        <span class="dot warn" style="background:#f59e0b; box-shadow:0 0 6px #f59e0b;"></span>
        <span><b>${floatIssues.length} Non-Integer Dimension(s) Detected:</b> Requirement: dimensions must be clean whole integers in millimetres.</span>
      </div>
      <button class="btn small" id="btn-banner-copy-integer-fix" style="background:#f59e0b; color:#0f172a; font-weight:700; border:none; white-space:nowrap;">
        <svg><use href="#i-copy"/></svg>Copy Prompt to Fix Floats
      </button>
    </div>` : '';

  const banner = floatBanner + `
    <div class="diag-banner ${errCount ? 'err' : 'warn'}">
      <div class="diag-banner-text">
        <span class="dot ${errCount ? 'err' : 'warn'}"></span>
        <span><b>${errCount || ds.length} ${errCount ? 'error(s)' : 'issue(s)'} detected:</b> Copy a follow-up fix prompt containing these error diagnostics to send back to your AI.</span>
      </div>
      <button class="btn small primary" id="btn-banner-copy-repair"><svg><use href="#i-copy"/></svg>Copy Fix Prompt for AI</button>
    </div>`;

  list.innerHTML = banner + ds.map((d, i) => `<div class="dg" data-i="${i}">
    <span class="dot ${d.severity === 'error' ? 'err' : d.severity === 'warning' ? 'warn' : ''}"></span>
    <div><div class="meta">${esc(d.code)}${d.board ? ' · ' + esc(d.board) : ''}${d.line ? ' · line ' + d.line : ''}</div>
      <div class="msg">${esc(d.message)}</div>
      ${d.fixes?.length ? `<div class="fixes">${d.fixes.map((f, k) => `<button class="btn ${f.safe ? 'safe' : ''}" data-fix="${i}:${k}" title="${f.safe ? 'Unambiguous correction' : 'Changes the design — you will be asked to confirm'}">${f.safe ? '✓ ' : ''}${esc(f.title)}</button>`).join('')}</div>` : ''}
    </div></div>`).join('');

  const btnBanner = $('#btn-banner-copy-repair', list);
  if (btnBanner) btnBanner.onclick = repairPrompt;

  const btnFloatFixBanner = $('#btn-banner-copy-integer-fix', list);
  if (btnFloatFixBanner) btnFloatFixBanner.onclick = integerFixPrompt;

  $$('.dg', list).forEach((el) => (el.onclick = (ev) => {
    if (ev.target.closest('[data-fix]') || ev.target.closest('#btn-banner-copy-repair')) return;
    const d = ds[+el.dataset.i];
    if (!d) return;
    if (d.line) { cm.focus(); cm.setCursor({ line: d.line - 1, ch: 0 }); cm.scrollIntoView({ line: d.line - 1, ch: 0 }, 80); }
    if (d.board) select(d.board, 'diag');
    if (d.location) view3d.focusPoint(d.location);
  }));
  $$('[data-fix]', list).forEach((b) => (b.onclick = () => {
    const [i, k] = b.dataset.fix.split(':').map(Number);
    const fix = ds[i].fixes[k];
    fix.safe ? applyFix(fix) : confirmFix(fix, ds[i]);
  }));
}

function markEditor() {
  S.marks.forEach((h) => cm.removeLineClass(h, 'background'));
  S.marks = [];
  cm.clearGutter('cv-marks');
  for (const d of S.result?.diagnostics || []) {
    if (!d.line || d.line > cm.lineCount() || !['error', 'warning'].includes(d.severity)) continue;
    const h = cm.addLineClass(d.line - 1, 'background', d.severity === 'error' ? 'cm-err-line' : 'cm-warn-line');
    S.marks.push(h);
    const m = document.createElement('div');
    m.className = `cm-gutter-mark ${d.severity}`;
    m.title = d.message;
    cm.setGutterMarker(d.line - 1, 'cv-marks', m);
  }
}

// ---------------------------------------------------------------------------
// Corrections (code-level: the code stays the single source of truth)
// ---------------------------------------------------------------------------
function describeEdits(fix) {
  let data = null;
  try { data = parseCode(); } catch (e) { /* ignore */ }
  return fix.edits.map((e) => {
    const b = e.board ? (data?.boards || []).find((x) => x.id === e.board) : data;
    const before = b ? JSON.stringify(b[e.field]) : '?';
    return `${e.board ? e.board + '.' : ''}${e.field}: ${before}  →  ${JSON.stringify(e.value)}`;
  }).join('\n');
}

function confirmFix(fix, d) {
  const dlg = $('#dlg-fix');
  $('#fix-title').textContent = 'This correction changes the design';
  $('#fix-body').innerHTML = `<p class="lead">${esc(d.message)}</p><div class="fix-diff">${esc(describeEdits(fix))}</div>
    <p class="lead">The code will be updated and recompiled. Choose a different correction if this is not what you intended.</p>
    <div class="row-actions"><button class="btn" id="fix-cancel">Cancel</button><button class="btn primary" id="fix-ok">${esc(fix.title)}</button></div>`;
  dlg.showModal();
  $('#fix-cancel').onclick = () => dlg.close();
  $('#fix-ok').onclick = async () => { dlg.close(); await applyFix(fix); };
}

async function applyFix(fix, recompile = true) {
  try {
    const r = await Api.canvasFix(cm.getValue(), fix);
    cm.setValue(r.source);
    toast(`Applied: ${fix.title}`);
    if (recompile) await compile(true);
  } catch (e) { reportError(e); }
}

async function autoFixSafe() {
  for (let round = 0; round < 10; round++) {
    const fix = (S.result?.diagnostics || []).flatMap((d) => (d.fixes || []).filter((f) => f.safe))[0];
    if (!fix) break;
    await applyFix(fix, false);
    await compile(false);
  }
  await compile(true);
}

// ---------------------------------------------------------------------------
// Selection + board inspector (edits go back into the code)
// ---------------------------------------------------------------------------
function select(id, source) {
  S.selected = id || null;
  view3d.setSelected(S.selected);
  sheet2d.setSelected(S.selected);
  if (source !== 'code') highlightBoard(S.selected, source !== 'render');
  else highlightBoard(S.selected, false);
  if (S.selected && source === 'view') view3d.focus(S.selected);
  renderBoard();
}

function renderBoard() {
  const panel = $('#board-panel');
  const r = S.result;
  const c = S.selected && r?.model3d?.components.find((x) => x.id === S.selected);
  if (!c) { panel.innerHTML = '<div class="empty">Click a board in 3D (or put the cursor inside its definition) to inspect it.</div>'; return; }
  let raw = null;
  try { raw = (parseCode().boards || []).find((b) => b.id === c.id); } catch (e) { /* code being edited */ }
  const joints = r.model3d.joints.filter((j) => j.a === c.id || j.b === c.id);
  const diags = r.diagnostics.filter((d) => d.board === c.id || (d.components || []).includes(c.id));
  const cut = (r.cut_list?.boards || []).find((p) => p.id === c.id);
  const b = c.world_bounds;
  panel.innerHTML = `
    <div class="section"><div class="title-row"><span class="id">${esc(c.id)}</span><span class="chip ${c.state}">${c.state === 'cut' ? 'not joined' : c.state}</span></div>
      <div class="muted" style="margin-top:2px">${esc(c.name)} · ${esc(c.group)}</div>
      ${renderDraftingGuide(c, S.draftingMode || 'all')}
    </div>
    ${raw ? `<div class="section"><h4>Edit in code</h4>
      <div class="edit-grid"><span></span><span class="ax">X</span><span class="ax">Y</span><span class="ax">Z</span></div>
      <div class="edit-grid"><label>Position</label>${raw.position.map((v, i) => `<input data-f="position" data-i="${i}" value="${v}" inputmode="decimal" />`).join('')}</div>
      <div class="edit-grid"><label>Size</label>${raw.size.map((v, i) => `<input data-f="size" data-i="${i}" value="${v}" inputmode="decimal" />`).join('')}</div>
      <div class="row-actions"><button class="btn small" id="be-reset">Reset</button><button class="btn small primary" id="be-apply">Update code &amp; compile</button></div></div>` : ''}
    <div class="section"><h4>Connections <span class="badge">${joints.length}</span></h4>
      ${joints.map((j) => `<div class="line"><span class="dot ${j.status === 'joined' ? 'joined' : 'error'}"></span><span class="grow mono">${esc(j.id)}</span>
        <span class="muted">${esc(j.type.replace('_', ' '))} ${j.a === c.id ? '→ ' + esc(j.b) : '← ' + esc(j.a)}</span></div>`).join('') || '<p class="lead">No connections.</p>'}</div>
    ${diags.length ? `<div class="section"><h4>Problems <span class="badge ${diags.some((d) => d.severity === 'error') ? 'err' : 'warn'}">${diags.length}</span></h4>
      ${diags.map((d) => `<div class="line" style="align-items:flex-start"><span class="dot ${d.severity === 'error' ? 'err' : 'warn'}" style="margin-top:5px"></span><span>${esc(d.message)}</span></div>`).join('')}</div>` : ''}`;

  // Drafting view mode toggles
  $$('[data-draft]', panel).forEach((b) => (b.onclick = () => {
    S.draftingMode = b.dataset.draft;
    const svg = panel.querySelector('.drafting-svg');
    if (svg) svg.className.baseVal = `profile drafting-svg mode-${S.draftingMode}`;
    $$('[data-draft]', panel).forEach((btn) => btn.classList.toggle('on', btn.dataset.draft === S.draftingMode));
  }));

  // Copy manual cutting specs
  const btnCopy = $('#btn-copy-specs', panel);
  if (btnCopy) btnCopy.onclick = async () => {
    try {
      await navigator.clipboard.writeText(formatDraftingSpecsText(c));
      toast('Copied manual cutting specs to clipboard!');
    } catch {
      toast('Failed to copy to clipboard', true);
    }
  };

  // Interactive hover highlights between drafting tables and SVG
  $$('.drafting-table tr[data-edge]', panel).forEach((tr) => {
    const edgeId = tr.dataset.edge;
    tr.onmouseenter = () => panel.querySelectorAll(`.drafting-svg [data-edge="${edgeId}"]`).forEach((el) => el.classList.add('highlight'));
    tr.onmouseleave = () => panel.querySelectorAll(`.drafting-svg [data-edge="${edgeId}"]`).forEach((el) => el.classList.remove('highlight'));
  });
  $$('.drafting-table tr[data-slot]', panel).forEach((tr) => {
    const slotId = tr.dataset.slot;
    tr.onmouseenter = () => panel.querySelectorAll(`.drafting-svg [data-slot="${slotId}"]`).forEach((el) => el.classList.add('highlight'));
    tr.onmouseleave = () => panel.querySelectorAll(`.drafting-svg [data-slot="${slotId}"]`).forEach((el) => el.classList.remove('highlight'));
  });
  bindCadInspectorEvents(panel, c);
  if (raw) {
    $('#be-reset').onclick = renderBoard;
    $('#be-apply').onclick = async () => {
      try {
        const data = parseCode();
        const bd = data.boards.find((x) => x.id === c.id);
        for (const inp of $$('[data-f]', panel)) {
          const v = parseFloat(inp.value);
          if (!Number.isFinite(v)) throw new Error(`${inp.dataset.f} must be numbers`);
          bd[inp.dataset.f][+inp.dataset.i] = v;
        }
        cm.setValue(pretty(data));
        await compile(true);
        select(c.id, 'render');
      } catch (e) { toast(e.message, true); }
    };
  }
}

// ---------------------------------------------------------------------------
// Save / open / import
// ---------------------------------------------------------------------------
async function save(update = false) {
  if (!S.result?.model3d) return toast('Compile the design first', true);
  try {
    const r = await Api.canvasSave(cm.getValue(), undefined, update ? S.savedId : undefined);
    S.savedId = r.design_id;
    $('#btn-open-studio').disabled = false;
    $('#btn-update').hidden = false;
    history.replaceState(null, '', `?design=${encodeURIComponent(r.design_id)}`);
    toast(update ? 'Project updated' : `Saved as new project “${r.design_id}”`);
  } catch (e) { reportError(e); }
}

async function openImport() {
  const dlg = $('#dlg-import');
  const { designs } = await Api.designs();
  const ids = S.result.model3d.components.map((c) => c.id);
  $('#import-body').innerHTML = `
    <p class="lead">Boards (and the connections between them) are added through the normal validated operations; ids that already exist get an <code>AI-</code> prefix.</p>
    <label class="form" style="display:block">Target project<select class="input" id="imp-target" style="width:100%;margin-top:6px">${designs.map((d) => `<option value="${esc(d.id)}">${esc(d.name)} (${d.components} parts)</option>`).join('')}</select></label>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:6px">${ids.map((id) => `<label class="check"><input type="checkbox" value="${esc(id)}" ${!S.selected || id === S.selected ? 'checked' : ''}/> ${esc(id)}</label>`).join('')}</div>
    <div class="row-actions"><button class="btn" onclick="this.closest('dialog').close()">Cancel</button><button class="btn primary" id="imp-go">Import</button></div>`;
  dlg.showModal();
  $('#imp-go').onclick = async () => {
    const boards = $$('#import-body input[type=checkbox]:checked').map((i) => i.value);
    if (!boards.length) return toast('Select at least one board', true);
    try {
      const target = $('#imp-target').value;
      await Api.canvasImport(cm.getValue(), target, boards);
      dlg.close();
      toast(`Imported ${boards.length} board(s) into ${target}`);
    } catch (e) { reportError(e); }
  };
}

// ---------------------------------------------------------------------------
// Panes (narrow screens show one at a time)
// ---------------------------------------------------------------------------
function setPane(p) {
  document.body.dataset.pane = p;
  $$('.canvas-steps button, .canvas-tabbar button').forEach((b) => b.classList.toggle('on', b.dataset.pane === p));
  if (!narrow.matches) {
    const target = { describe: '#in-title', prompt: '#out-prompt', code: null, preview: null }[p];
    if (target) $(target).focus();
    if (p === 'code') cm.focus();
  }
  requestAnimationFrame(() => { cm.refresh(); view3d.resize(); sheet2d._apply(); });
}

function setPreview(pv) {
  $$('#pv-seg button').forEach((b) => b.classList.toggle('on', b.dataset.pv === pv));
  $$('.cv-preview .pv').forEach((el) => (el.hidden = el.dataset.pvId !== pv));
  requestAnimationFrame(() => { view3d.resize(); sheet2d._apply(); if (pv === '2d') sheet2d.fit(); });
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------
$$('.canvas-steps button, .canvas-tabbar button').forEach((b) => (b.onclick = () => setPane(b.dataset.pane)));
$$('#pv-seg button').forEach((b) => (b.onclick = () => setPreview(b.dataset.pv)));
$$('[data-cam]').forEach((b) => (b.onclick = () => view3d.view(b.dataset.cam)));
$('#btn-fit-3d').onclick = () => view3d.view('iso');
$('#btn-fit-2d').onclick = () => sheet2d.fit();
const fs3d = bindFullscreen($('.view-3d'), $('#btn-full-3d'), () => requestAnimationFrame(() => view3d.resize()));
bindFullscreen($('.view-2d'), $('#btn-full-2d'), () => requestAnimationFrame(() => { sheet2d._apply(); sheet2d.fit(); }));
$('#explode').oninput = (e) => view3d.setExplode(e.target.value / 100);
$('#btn-gen-prompt').onclick = generatePrompt;
$('#btn-change-prompt').onclick = changePrompt;
$('#btn-repair-prompt').onclick = repairPrompt;
if ($('#btn-integer-prompt')) $('#btn-integer-prompt').onclick = integerFixPrompt;
$('#btn-copy-prompt').onclick = () => copyText($('#out-prompt').value, 'Prompt');
$('#btn-compile').onclick = () => compile(true);
$('#btn-format').onclick = formatCode;
$('#btn-undo').onclick = () => cm.undo();
$('#btn-redo').onclick = () => cm.redo();
$('#btn-copy-code').onclick = () => copyText(cm.getValue(), 'Code');
$('#btn-export').onclick = () => {
  let name = 'design';
  try { name = (parseCode().product?.name || name).toLowerCase().replace(/[^a-z0-9]+/g, '-'); } catch (e) { /* ignore */ }
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(new Blob([cm.getValue()], { type: 'application/json' })), download: `${name}.json` });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 3000);
};
$('#btn-reset').onclick = () => { if (S.compiledSource) { cm.setValue(S.compiledSource); toast('Back to the last compiled code'); } };
$('#btn-clear').onclick = () => { if (!cm.getValue().trim() || confirm('Clear the editor?')) { cm.setValue(''); cm.focus(); } };
$('#btn-autofix').onclick = autoFixSafe;
$('#btn-save').onclick = () => save(false);
$('#btn-update').onclick = () => save(true);
$('#btn-open-studio').onclick = () => { if (S.savedId) location.href = `/?design=${encodeURIComponent(S.savedId)}`; };
$('#btn-import').onclick = () => openImport().catch(reportError);
$('#sel-example').onchange = (e) => {
  const src = S.spec && { spec: S.spec.example_source, complex: S.spec.complex_example_source,
    structures: S.spec.structures_example_source }[e.target.value];
  if (src && (!cm.getValue().trim() || confirm('Replace the editor contents with the example?'))) cm.setValue(src);
  e.target.value = '';
};
narrow.addEventListener('change', () => setPane(document.body.dataset.pane));
// Esc cancels a compile; in full screen the first Esc only leaves full screen
window.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape' || !loader.busy || document.querySelector('dialog[open]')) return;
  e.preventDefault();
  if (fs3d.isOn()) fs3d.exit(); else cancelCompile();
}, true);

(async () => {
  try {
    S.spec = await Api.canvasSpec();
    fillThickness();
    const q = new URLSearchParams(location.search);
    if (q.get('design')) {
      const { design } = await Api.design(q.get('design'));
      if (design.source?.code) {
        cm.setValue(design.source.code);
        S.savedId = design.id;
        $('#btn-open-studio').disabled = false;
        $('#btn-update').hidden = false;
      } else toast('That project was not created in the AI canvas; its code is not available here.', true);
    }
    if (q.get('example') === '1') cm.setValue(S.spec.example_source);
    if (q.get('title')) { $('#in-title').value = q.get('title'); }
    setPane(q.get('pane') || 'code');
    if (cm.getValue().trim() && q.get('compile') !== '0') await compile(true);
    if (q.get('select')) select(q.get('select'), 'view');
    if (q.get('pv')) setPreview(q.get('pv'));
    window.__canvasReady = true;
  } catch (e) { reportError(e); window.__canvasReady = true; }
})();
