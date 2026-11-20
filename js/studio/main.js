/**
 * Board Studio controller.
 *
 * The UI is organised as a 3-step workflow — Design → Check → Produce — and every step shows
 * only what it needs. All state lives on the server (file store or Firebase Firestore); every
 * edit is an API call through the same validation pipeline AI agents use, and the studio then
 * re-reads the model, the layout and the validation report.
 */
import { Api, ApiError } from './api.js';
import { Viewport3D } from './viewport3d.js';
import { Sheet2D } from './sheet2d.js';
import { bindFullscreen } from './fullscreen.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = (v, n = 1) => (Math.round(v * 10 ** n) / 10 ** n).toString();
const icon = (id) => `<svg><use href="#i-${id}"/></svg>`;
const mqSide = matchMedia('(max-width: 1200px)');
const mqSheet = matchMedia('(max-width: 900px)');

const STEPS = {
  design: { n: 1, title: 'Design', fab: 'Details', view: () => (mqSheet.matches ? '3d' : 'split') },
  check: { n: 2, title: 'Check & fix', fab: 'Issues', view: () => '3d' },
  produce: { n: 3, title: 'Produce', fab: 'Export', view: () => '2d' }
};

const S = {
  designId: null, designs: [], storage: null, model: null, validation: null, layout: null,
  selected: null, step: 'design', views: {}, sideTab: 'parts', filter: '', collapsed: new Set(),
  lastAutoFix: null, saving: false,
  prod: { preset: 'A3', width: 600, height: 400, margin: 10, spacing: 5, rotation: 'orthogonal', kerf: true, paper: 'A4' }
};
try { Object.assign(S.prod, JSON.parse(localStorage.getItem('board-studio-prod') || '{}')); } catch (e) { /* storage unavailable */ }

// ---------------------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------------------
function toast(msg, err = false) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = `toast show${err ? ' err' : ''}`;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.className = 'toast'), err ? 6500 : 2800);
}

function reportError(e) {
  console.error(e);
  if (e instanceof ApiError) {
    const first = e.issues.find((i) => i.severity === 'error') || e.issues[0];
    toast(`${e.message}${first?.message ? ' — ' + first.message : ''}`, true);
  } else toast(String(e?.message || e), true);
}

/** Run a server mutation with a visible "Saving…" state; refresh afterwards. */
async function save(fn, { refreshAfter = true } = {}) {
  S.saving = true;
  renderSaveState();
  try {
    const r = await fn();
    if (refreshAfter) await refresh();
    return r;
  } finally {
    S.saving = false;
    renderSaveState();
  }
}

// ---------------------------------------------------------------------------
// Viewports
// ---------------------------------------------------------------------------
const stateLabel = (s) => ({ joined: 'joined', cut: 'not joined', error: 'has errors' }[s] || s);

function showTip(tipEl, id, e) {
  if (!id || !e || mqSheet.matches) { tipEl.style.display = 'none'; return; }
  const c = S.model?.components.find((x) => x.id === id);
  if (!c) return;
  const r = tipEl.parentElement.getBoundingClientRect();
  tipEl.innerHTML = `<b class="mono">${esc(id)}</b> · ${esc(c.name)}<br><span class="muted">${fmt(c.cut_size.length)} × ${fmt(c.cut_size.width)} × ${c.thickness} mm · ${stateLabel(c.state)}</span>`;
  tipEl.style.display = 'block';
  tipEl.style.left = `${Math.max(8, Math.min(e.clientX - r.left + 14, r.width - 230))}px`;
  tipEl.style.top = `${e.clientY - r.top + 14}px`;
}

const view3d = new Viewport3D($('#canvas3d'), { onSelect: (id) => select(id, 'view'), onHover: (id, e) => showTip($('#tip-3d'), id, e) });
const sheet2d = new Sheet2D($('#svg2d'), {
  onSelect: (id) => select(id, 'view'), onHover: (id, e) => showTip($('#tip-2d'), id, e), scalebar: $('#scalebar-2d'),
  onCursor: (txt) => ($('#cursor-pos').textContent = txt)
});

function select(id, source) {
  S.selected = id;
  view3d.setSelected(id);
  sheet2d.setSelected(id);
  if (id && source === 'tree') { view3d.focus(id); sheet2d.focus(id); }
  renderSidebar();
  renderPanel();
  if (mqSide.matches && source === 'tree') closeDrawers();
  if (id && mqSheet.matches && (source === 'tree' || source === 'view') && S.step === 'design') openPanel();
}

// ---------------------------------------------------------------------------
// Drawers (tablet / phone)
// ---------------------------------------------------------------------------
const openSide = () => { document.body.classList.add('side-open'); document.body.classList.remove('panel-open'); };
const openPanel = () => { document.body.classList.add('panel-open'); document.body.classList.remove('side-open'); };
const closeDrawers = () => document.body.classList.remove('side-open', 'panel-open');

// ---------------------------------------------------------------------------
// Steps & views
// ---------------------------------------------------------------------------
async function setStep(step, { keepPanel = false } = {}) {
  const prev = S.step;
  S.step = step;
  document.body.dataset.step = step;
  $$('#steps button, #tabbar button').forEach((b) => b.classList.toggle('on', b.dataset.step === step));
  $('#fab-label').textContent = STEPS[step].fab;
  setView(S.views[step] || STEPS[step].view(), false);
  if (!keepPanel) closeDrawers();
  renderPanel();
  if ((prev === 'produce') !== (step === 'produce') && S.designId) {
    sheet2d._fitted = false;
    await refreshLayout();
    renderPanel();
  }
  renderStageTitle();
}

function setView(view, remember = true) {
  if (view === 'split' && mqSheet.matches) view = '3d';
  if (remember) S.views[S.step] = view;
  document.body.dataset.view = view;
  $$('#view-seg button').forEach((b) => b.classList.toggle('on', b.dataset.view === view));
  requestAnimationFrame(() => { view3d.resize(); sheet2d._apply(); if (view !== '3d') sheet2d.fit(); });
}

function renderStageTitle() {
  const L = S.layout;
  const t = { design: '2D: flat cut parts  ·  3D: assembled product', check: 'Click an issue to locate it in 3D',
    produce: L ? `${L.nesting.sheet_count} cutting sheet(s) · ${L.nesting.sheet.name} ${L.nesting.sheet.width} × ${L.nesting.sheet.height} mm` : '' };
  $('#stage-title').textContent = S.model ? t[S.step] : '';
}

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------
function layoutOpts() {
  const p = S.prod;
  // flat-parts view: nest on the design's own sheet (furniture from the AI canvas uses full-size boards)
  if (S.step !== 'produce') return { margin: 10, spacing: 8, rotation: 'orthogonal' };
  const base = { margin: p.margin, spacing: p.spacing, rotation: p.rotation, kerf: p.kerf ? 1 : 0 };
  return p.preset === 'custom' ? { ...base, width: p.width, height: p.height } : { ...base, preset: p.preset };
}

async function refresh() {
  if (!S.designId) return;
  const [model, val] = await Promise.all([Api.model3d(S.designId), Api.validate(S.designId)]);
  S.model = model;
  S.validation = val.validation;
  if (S.selected && !model.components.some((c) => c.id === S.selected)) S.selected = null;
  view3d.load(model);
  await refreshLayout();
  renderAll();
}

async function refreshLayout() {
  if (!S.model?.components.length) { S.layout = null; sheet2d.svg.innerHTML = ''; renderStageTitle(); return; }
  try {
    S.layout = await Api.layout2d(S.designId, layoutOpts());
    const states = Object.fromEntries(S.model.components.map((c) => [c.id, c.state]));
    sheet2d.load(S.layout, { mode: S.step === 'produce' ? 'production' : 'design', states });
  } catch (e) {
    S.layout = null;
    reportError(e);
  }
  renderStageTitle();
}

async function loadDesigns(preferred) {
  const { designs } = await Api.designs();
  S.designs = designs;
  const url = new URLSearchParams(location.search).get('design');
  let saved = null;
  try { saved = localStorage.getItem('board-studio-design'); } catch (e) { /* ignore */ }
  S.designId = [preferred, url, saved, 'boat'].find((x) => x && designs.some((d) => d.id === x)) || designs[0]?.id || null;
  rememberDesign();
}

function rememberDesign() {
  try { if (S.designId) localStorage.setItem('board-studio-design', S.designId); } catch (e) { /* ignore */ }
}

async function openDesign(id) {
  S.designId = id;
  S.selected = null;
  S.lastAutoFix = null;
  view3d._framed = false;
  sheet2d._fitted = false;
  rememberDesign();
  renderHeader();
  await refresh();
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function renderAll() {
  renderHeader();
  renderSidebar();
  renderPanel();
  renderStageTitle();
  view3d.setSelected(S.selected);
  sheet2d.setSelected(S.selected);
}

function renderSaveState() {
  const el = $('#save-state');
  const st = S.storage;
  let cls = '', txt = '', title = '';
  if (S.saving) { cls = 'saving'; txt = 'Saving…'; title = 'Saving your change'; }
  else if (!st) { txt = ''; }
  else if (st.config_error) { cls = 'warn'; txt = 'Firebase not connected'; title = st.config_error; }
  else if (st.backend === 'firestore') { txt = 'Saved to Firebase'; title = `Every change is saved to Firestore (${st.project})`; }
  else if (st.persistent) { txt = 'Saved'; title = 'Every change is saved on the server'; }
  else { cls = 'warn'; txt = 'Not saved permanently'; title = 'No database is connected — designs are lost when the server restarts. Open “My designs” for setup.'; }
  el.className = `save-state ${cls}`;
  el.title = title;
  const dot = cls === 'warn' ? 'warn' : cls === 'saving' ? 'cut' : st ? 'ok' : '';
  el.innerHTML = `<span class="dot ${dot}"></span><span class="txt">${txt}</span>`;
}

function renderHeader() {
  const d = S.designs.find((x) => x.id === S.designId);
  $('#design-name').textContent = S.model?.name || d?.name || (S.designId || 'No design — create one');
  $('#design-sub').textContent = S.model ? `${S.model.components.length} parts · rev ${S.model.revision}` : '';
  const v = S.validation;
  const cls = !v ? '' : v.valid ? (v.complete ? 'ok' : 'warn') : 'err';
  const txt = !v ? '—' : v.valid ? (v.complete ? 'Valid · fully joined' : `Valid · ${v.summary.warnings} warning${v.summary.warnings === 1 ? '' : 's'}`)
    : `${v.summary.errors} error${v.summary.errors === 1 ? '' : 's'}`;
  $('#status-pill').innerHTML = `<span class="dot ${cls}"></span><span class="txt">${txt}</span>`;
  const n = v ? v.summary.errors : 0;
  for (const id of ['#check-badge', '#check-badge-m']) {
    const b = $(id);
    b.hidden = !v || (!v.summary.errors && !v.summary.warnings);
    b.textContent = n || v?.summary.warnings || '';
    b.className = `badge ${n ? 'err' : 'warn'}`;
  }
  renderSaveState();
}

const jointBroken = (jid) => (S.validation?.issues || []).some((i) => i.joint === jid && i.severity === 'error');

function renderSidebar() {
  const m = S.model;
  $('#comp-count').textContent = m?.components.length ?? 0;
  $('#joint-count').textContent = m?.joints.length ?? 0;
  $$('#side-seg button').forEach((b) => b.classList.toggle('on', b.dataset.side === S.sideTab));
  $('#tree').hidden = S.sideTab !== 'parts';
  $('#joint-list').hidden = S.sideTab !== 'joints';
  const q = S.filter.trim().toLowerCase();
  if (!m) { $('#tree').innerHTML = $('#joint-list').innerHTML = '<div class="empty">No design open.</div>'; return; }

  if (S.sideTab === 'parts') {
    const groups = {};
    m.components.filter((c) => !q || c.id.toLowerCase().includes(q) || (c.name || '').toLowerCase().includes(q))
      .forEach((c) => (groups[c.group] ||= []).push(c));
    $('#tree').innerHTML = Object.entries(groups).map(([g, cs]) => `
      <div class="group${S.collapsed.has(g) && !q ? ' collapsed' : ''}" data-group="${esc(g)}">
        <button class="group-title">${icon('chev')}${esc(g)}<span class="n">${cs.length}</span></button>
        <div class="group-items">${cs.map((c) => `
          <div class="item${c.id === S.selected ? ' sel' : ''}" data-id="${esc(c.id)}" title="${esc(c.name)}">
            <span class="dot ${c.state}"></span><span class="name">${esc(c.id)}</span>
            <span class="meta">${fmt(c.cut_size.length, 0)}×${fmt(c.cut_size.width, 0)}</span></div>`).join('')}</div>
      </div>`).join('') || `<div class="empty">${m.components.length ? 'No parts match.' : 'This design has no parts yet.'}</div>`;
    $$('#tree .item').forEach((n) => (n.onclick = () => select(n.dataset.id, 'tree')));
    $$('#tree .group-title').forEach((b) => (b.onclick = () => {
      const g = b.parentElement.dataset.group;
      S.collapsed.has(g) ? S.collapsed.delete(g) : S.collapsed.add(g);
      b.parentElement.classList.toggle('collapsed');
    }));
  } else {
    const js = m.joints.filter((j) => !q || [j.id, j.a, j.b, j.type].some((x) => String(x).toLowerCase().includes(q)));
    $('#joint-list').innerHTML = js.map((j) => {
      const cls = j.status !== 'joined' ? 'cut' : jointBroken(j.id) ? 'error' : 'joined';
      return `<div class="item" data-a="${esc(j.a)}" title="${esc(j.a)} → ${esc(j.b)} (${esc(j.status || 'not joined')})">
        <span class="dot ${cls}"></span><span class="name mono" style="font-size:12px">${esc(j.id)}</span>
        <span class="meta">${esc(j.type.replace('_', ' '))}</span></div>`;
    }).join('') || `<div class="empty">${m.joints.length ? 'No joints match.' : 'No joints yet.'}</div>`;
    $$('#joint-list .item').forEach((n) => (n.onclick = () => select(n.dataset.a, 'tree')));
  }
}

function renderPanel() {
  const st = STEPS[S.step];
  $('#panel-kicker').textContent = `Step ${st.n} of 3`;
  $('#panel-title').textContent = S.step === 'design' && S.selected ? 'Part details' : st.title;
  const body = $('#panel-body');
  const top = body.scrollTop;
  if (!S.model || !S.validation) {
    body.innerHTML = `<div class="section"><p class="lead">No design is open.</p>
      <div class="row-actions" style="justify-content:flex-start"><button class="btn primary" id="btn-open-designs">Open or create a design</button></div></div>`;
    $('#btn-open-designs').onclick = openDesignsDialog;
    return;
  }
  if (S.step === 'design') S.selected ? renderInspector(body) : renderOverview(body);
  else if (S.step === 'check') renderCheck(body);
  else renderProduce(body);
  body.scrollTop = top;
}

// ---------- Step 1: Design ----------
function renderOverview(body) {
  const m = S.model, v = S.validation;
  const size = m.components.length ? ['x', 'y', 'z'].map((_, i) => fmt(m.bounds.max[i] - m.bounds.min[i], 0)).join(' × ') + ' mm' : '—';
  body.innerHTML = `
    <div class="section">
      <div class="title-row"><span style="font-weight:650;font-size:15px">${esc(m.name)}</span></div>
      <div class="stats" style="margin-top:12px">
        <div class="stat"><b>${m.components.length}</b><span>Parts</span></div>
        <div class="stat"><b>${v.summary.joined}/${v.summary.joints}</b><span>Joined</span></div>
        <div class="stat"><b style="color:${v.summary.errors ? 'var(--err)' : 'var(--ok)'}">${v.summary.errors}</b><span>Errors</span></div>
      </div>
      <dl class="kv" style="margin-top:12px"><dt>Assembled size</dt><dd>${size}</dd>
        <dt>Material</dt><dd>${esc(m.material.name)}</dd><dt>Thickness</dt><dd>${m.material.thickness} mm</dd>
        <dt>Joinery</dt><dd>${m.joinery === 'glue_allowed' ? 'Glue allowed' : 'Glue-free · tab &amp; slot'}</dd></dl>
    </div>
    ${!m.components.length ? '<div class="callout info">This design is empty. Parts are added through the API (an AI agent or script), or create a parametric boat from <b>My designs</b>.</div>'
      : v.valid ? (v.complete ? '<div class="callout ok">Geometry validated — every part fits and is joined.</div>'
      : '<div class="callout warn">Valid, but some parts are not fully joined. Open <b>Check</b> to see what is left.</div>')
      : `<div class="callout err">${v.summary.errors} problem(s) found. Open <b>Check</b> to see and auto-fix them.</div>`}
    <div class="section"><h4>How it works</h4>
      <ol class="steps-guide">
        <li data-go="design"><span class="n">1</span><div><b>Design</b><span>Click a part in the list, 2D or 3D view to see its dimensions and adjust its position.</span></div></li>
        <li data-go="check"><span class="n">2</span><div><b>Check &amp; fix</b><span>Every slot, gap and collision is validated. Apply fixes one by one or auto-fix all.</span></div></li>
        <li data-go="produce"><span class="n">3</span><div><b>Produce</b><span>Nest parts on A4 / A3 / board sheets and export the PDF booklet, SVG, DXF or PNG.</span></div></li>
      </ol></div>
    <div class="section"><h4>Controls</h4><p class="lead">Drag to rotate · right-drag to pan · scroll to zoom. Use <b>Explode</b> to look inside. Press <kbd>?</kbd> for shortcuts.</p></div>`;
  $$('[data-go]', body).forEach((li) => (li.onclick = () => setStep(li.dataset.go, { keepPanel: true })));
}

function profileSvg(c) {
  const pts = c.cut_outline;
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const w = x1 - x0, h = y1 - y0, pad = Math.max(w, h) * 0.16;
  const d = 'M' + pts.map((p) => `${p[0]},${-p[1]}`).join('L') + 'Z';
  const feats = c.features.map((f) => {
    const col = { slot: 'var(--slot)', opening: 'var(--opening)', hole: 'var(--hole)' }[f.kind];
    const dash = f.kind === 'opening' ? 'stroke-dasharray="3 2"' : '';
    if (f.shape === 'circle') return `<circle cx="${f.center[0]}" cy="${-f.center[1]}" r="${f.diameter / 2}" fill="#0e1217" stroke="${col}" ${dash} vector-effect="non-scaling-stroke"/>`;
    if (f.polygon) return `<path d="M${f.polygon.map((p) => `${p[0]},${-p[1]}`).join('L')}Z" fill="#0e1217" stroke="${col}" ${dash} vector-effect="non-scaling-stroke"/>`;
    return `<rect x="${f.center[0] - f.width / 2}" y="${-f.center[1] - f.height / 2}" width="${f.width}" height="${f.height}"
      transform="rotate(${-(f.angle || 0)} ${f.center[0]} ${-f.center[1]})" fill="#0e1217" stroke="${col}" ${dash} vector-effect="non-scaling-stroke"/>`;
  }).join('') + (c.marks || []).map((m) => `<path d="M${m.points.map((p) => `${p[0]},${-p[1]}`).join('L')}${m.closed ? 'Z' : ''}"
      fill="none" stroke="${m.kind === 'pocket' ? '#15803d' : '#1d4ed8'}" stroke-dasharray="2 1.5" vector-effect="non-scaling-stroke"/>`).join('');
  const fs = Math.max(w, h) * 0.055;
  return `<svg class="profile" viewBox="${x0 - pad} ${-y1 - pad} ${w + 2 * pad} ${h + 2 * pad}" preserveAspectRatio="xMidYMid meet">
    <path d="${d}" fill="#d6b483" stroke="var(--cut)" vector-effect="non-scaling-stroke" stroke-width="1.2"/>${feats}
    <text x="${(x0 + x1) / 2}" y="${-y0 + pad * 0.72}" font-size="${fs}" fill="#8d98a8" text-anchor="middle">${fmt(w)} mm</text>
    <text x="${x1 + pad * 0.5}" y="${-(y0 + y1) / 2}" font-size="${fs}" fill="#8d98a8" text-anchor="middle"
      transform="rotate(-90 ${x1 + pad * 0.5} ${-(y0 + y1) / 2})">${fmt(h)} mm</text></svg>`;
}

function jointSpec(j) {
  const spec = { id: j.id, type: j.type, a: j.a, b: j.b, tab: j.tab, a_edge: j.a_edge, b_edge: j.b_edge };
  Object.keys(spec).forEach((k) => spec[k] === undefined && delete spec[k]);
  return spec;
}

function renderInspector(body) {
  const c = S.model.components.find((x) => x.id === S.selected);
  if (!c) { S.selected = null; renderOverview(body); return; }
  const joints = S.model.joints.filter((j) => j.a === c.id || j.b === c.id);
  const errs = (S.validation?.issues || []).filter((i) => (i.components || []).includes(c.id) && i.severity === 'error').length;
  const pos = c.placement.position, rot = c.placement.rotation;
  body.innerHTML = `
    <div class="section">
      <div class="title-row"><span class="id">${esc(c.id)}</span><span class="chip ${c.state}">${stateLabel(c.state)}</span>
        <span class="spacer"></span><button class="icon-btn" id="btn-deselect" title="Back to overview (Esc)" aria-label="Back to overview">${icon('close')}</button></div>
      <div class="muted" style="margin:2px 0 12px">${esc(c.name)} · ${esc(c.group)}</div>
      ${profileSvg(c)}
      <dl class="kv" style="margin-top:12px">
        <dt>Cut size</dt><dd>${fmt(c.cut_size.length, 2)} × ${fmt(c.cut_size.width, 2)} mm</dd>
        <dt>Thickness</dt><dd>${c.thickness} mm</dd><dt>Net area</dt><dd>${fmt(c.dimensions_2d.area / 100, 1)} cm²</dd></dl>
    </div>
    ${errs ? `<div class="callout err">${errs} error(s) on this part. <a href="#" id="go-check">Show in Check</a></div>` : ''}
    <div class="section"><h4>Position in assembly</h4>
      <div class="axis-labels"><span></span><span>X</span><span>Y</span><span>Z</span></div>
      <div class="xyz"><label>Move (mm)</label>${pos.map((v, i) => `<input inputmode="decimal" data-k="p${i}" value="${fmt(v, 3)}" aria-label="Position ${'XYZ'[i]}" />`).join('')}</div>
      <div class="xyz"><label>Rotate (°)</label>${rot.map((v, i) => `<input inputmode="decimal" data-k="r${i}" value="${fmt(v, 3)}" aria-label="Rotation ${'XYZ'[i]}" />`).join('')}</div>
      <label class="check"><input type="checkbox" id="chk-detach" /> Allow detaching joints this breaks</label>
      <div class="row-actions"><button class="btn small" id="btn-reset-place">Reset</button><button class="btn small primary" id="btn-apply-place">Apply &amp; validate</button></div>
    </div>
    <div class="section"><h4>Joints <span class="badge">${joints.length}</span></h4>
      ${joints.map((j) => `<div class="line"><span class="dot ${j.status !== 'joined' ? 'cut' : jointBroken(j.id) ? 'error' : 'joined'}"></span>
        <span class="grow mono" title="${esc(j.type)}">${esc(j.id)}</span>
        <span class="muted" style="white-space:nowrap">${esc(j.a === c.id ? '→ ' + j.b : '← ' + j.a)}</span>
        <button class="btn small ghost" data-check="${esc(j.id)}" title="Dry-run validation">Check</button>
        ${j.status !== 'joined' ? `<button class="btn small" data-rejoin="${esc(j.id)}">Re-join</button>` : ''}</div>`).join('') || '<p class="lead">Not joined to anything.</p>'}
    </div>
    <div class="section"><details class="more"><summary>${icon('chev')}Cut features (${c.features.length}) &amp; tabs (${c.tabs.length})${c.marks?.length ? ` · engravings (${c.marks.length})` : ''}</summary>
      ${c.features.map((f) => `<div class="line"><span class="chip ${f.kind}">${f.kind}</span><span class="grow mono">${esc(f.id)}</span>
        <span class="muted mono">${f.shape === 'circle' ? 'Ø' + fmt(f.diameter, 2) : f.shape === 'polygon' ? 'shape' : fmt(f.width, 2) + '×' + fmt(f.height, 2)}</span></div>`).join('')}
      ${c.tabs.map((t) => `<div class="line"><span class="chip tab">tab</span><span class="grow mono">${esc(t.id)} · edge ${t.edge}</span>
        <span class="muted mono">${fmt(t.width, 1)}×${fmt(t.depth, 1)}</span></div>`).join('')}
      ${(c.marks || []).map((m) => `<div class="line"><span class="chip">${m.kind}</span><span class="grow mono">${esc(m.id)}</span>
        <span class="muted mono">${fmt(m.depth, 1)} mm deep</span></div>`).join('')}
      ${!c.features.length && !c.tabs.length && !(c.marks || []).length ? '<p class="lead">None.</p>' : ''}</details></div>`;

  $('#btn-deselect').onclick = () => select(null);
  if ($('#go-check')) $('#go-check').onclick = (e) => { e.preventDefault(); setStep('check', { keepPanel: true }); };
  $('#btn-reset-place').onclick = () => renderPanel();
  $('#btn-apply-place').onclick = async (ev) => {
    const v = (k) => parseFloat(body.querySelector(`[data-k="${k}"]`).value);
    const placement = { position: [v('p0'), v('p1'), v('p2')], rotation: [v('r0'), v('r1'), v('r2')] };
    if ([...placement.position, ...placement.rotation].some((x) => !Number.isFinite(x))) return toast('Enter numbers only', true);
    ev.currentTarget.disabled = true;
    try {
      const r = await save(() => Api.updateComponent(S.designId, c.id, { placement }, { detach_broken_joints: $('#chk-detach').checked }));
      const det = r.result.detached_joints || [];
      toast(det.length ? `Moved; detached ${det.join(', ')} — open Check to fix` : 'Position applied and validated');
    } catch (e) { reportError(e); renderPanel(); }
  };
  $$('[data-check]', body).forEach((b) => (b.onclick = async () => {
    const j = S.model.joints.find((x) => x.id === b.dataset.check);
    try {
      const r = await Api.checkJoint(S.designId, { ...jointSpec(j), id: j.id + '-check' });
      const e2 = r.issues.filter((i) => i.severity === 'error');
      toast(r.fits && !e2.length ? `${j.id}: fits` : `${j.id}: ${e2[0]?.code} — ${e2[0]?.message}`, !r.fits);
    } catch (e) { reportError(e); }
  }));
  $$('[data-rejoin]', body).forEach((b) => (b.onclick = async () => {
    const j = S.model.joints.find((x) => x.id === b.dataset.rejoin);
    b.disabled = true;
    try {
      await save(async () => { await Api.unjoin(S.designId, j.id); await Api.join(S.designId, jointSpec(j), true); });
      toast(`${j.id} re-joined`);
    } catch (e) { reportError(e); await refresh(); }
  }));
}

// ---------- Step 2: Check ----------
function issueHtml(i, k, fixById) {
  const fx = i.fix_id && fixById[i.fix_id];
  return `<div class="issue" data-k="${k}"><span class="dot ${i.severity === 'error' ? 'err' : i.severity === 'warning' ? 'warn' : ''}"></span>
    <div><div class="code">${esc(i.code)}${i.components?.length ? ' · ' + esc(i.components.join(', ')) : ''}</div>
    <div class="msg">${esc(i.message)}</div>
    ${fx ? `<div class="fix-row"><span class="desc">${esc(fx.description)}</span><button class="btn small primary" data-fix="${esc(fx.id)}">Apply fix</button></div>` : ''}</div></div>`;
}

function renderCheck(body) {
  const v = S.validation;
  const fixes = v.fixes || [], unfixable = v.unfixable || [];
  const fixById = Object.fromEntries(fixes.map((f) => [f.id, f]));
  let issues = v.issues;
  if (S.selected) issues = issues.filter((i) => (i.components || []).includes(S.selected));
  const errors = issues.filter((i) => i.severity === 'error'), warnings = issues.filter((i) => i.severity !== 'error');
  const all = [...errors, ...warnings];
  const last = S.lastAutoFix;
  body.innerHTML = `
    <div class="section">
      <div class="stats">
        <div class="stat"><b style="color:${v.summary.errors ? 'var(--err)' : 'var(--ok)'}">${v.summary.errors}</b><span>Errors</span></div>
        <div class="stat"><b style="color:${v.summary.warnings ? 'var(--warn)' : 'inherit'}">${v.summary.warnings}</b><span>Warnings</span></div>
        <div class="stat"><b>${v.summary.joined}/${v.summary.joints}</b><span>Joined</span></div></div>
      <button class="btn primary block" id="btn-autofix" style="margin-top:12px" ${fixes.length ? '' : 'disabled'}>${icon('wand')}
        ${fixes.length ? `Auto-fix all (${fixes.length})` : 'Nothing to auto-fix'}</button>
      <p class="lead" style="font-size:12px;margin-top:8px">Fixes move parts by the exact computed amount or regenerate slots. Each one is re-validated and kept only if it doesn't add problems.</p>
    </div>
    ${last ? `<div class="callout ${last.valid ? 'ok' : 'warn'}"><b>Auto-fix applied ${last.steps.length} step(s).</b>${last.steps.length
      ? '<br>' + last.steps.map((s) => '• ' + esc(s.description)).join('<br>') : ''}</div>` : ''}
    ${v.valid && v.complete ? '<div class="callout ok">All checks pass: every slot fits, nothing collides and all parts are joined.</div>' : ''}
    ${unfixable.length ? `<div class="callout warn"><b>${unfixable.length} need your decision</b> (no safe automatic fix):<br>${unfixable
      .map((u) => `• <b>${esc(u.joint)}</b> — ${esc(u.code)}`).join('<br>')}</div>` : ''}
    ${S.selected ? `<span class="filter-chip">Issues for <b>${esc(S.selected)}</b><button id="btn-clear-filter" aria-label="Show all">${icon('close')}</button></span>` : ''}
    ${errors.length ? `<div class="issue-group-title"><span>Errors</span><span>${errors.length}</span></div>${errors.map((i, k) => issueHtml(i, k, fixById)).join('')}` : ''}
    ${warnings.length ? `<details class="more" ${errors.length ? '' : 'open'}><summary class="issue-group-title">${icon('chev')} Warnings · ${warnings.length}</summary>
      ${warnings.map((i, k) => issueHtml(i, k + errors.length, fixById)).join('')}</details>` : ''}
    ${!all.length && !(v.valid && v.complete) ? '<div class="empty">No issues for this selection.</div>' : ''}`;

  if ($('#btn-clear-filter')) $('#btn-clear-filter').onclick = () => select(null);
  $$('.issue', body).forEach((n) => (n.onclick = (ev) => {
    if (ev.target.closest('[data-fix]')) return;
    const i = all[+n.dataset.k];
    const part = i.components?.[0] || null;
    if (i.location) view3d.focusPoint(i.location); else if (part) view3d.focus(part);
    view3d.setSelected(part);
    sheet2d.setSelected(part);
    if (mqSheet.matches) closeDrawers();
  }));
  $$('[data-fix]', body).forEach((b) => (b.onclick = async () => {
    b.disabled = true;
    try {
      const r = await save(() => Api.applyFix(S.designId, b.dataset.fix));
      S.lastAutoFix = null;
      toast(`Fixed: ${r.result.fix.description}`);
      renderPanel();
    } catch (e) { reportError(e); b.disabled = false; }
  }));
  const af = $('#btn-autofix');
  af.onclick = async () => {
    af.disabled = true;
    af.innerHTML = `${icon('wand')} Fixing…`;
    try {
      const r = await save(() => Api.autoFix(S.designId));
      S.lastAutoFix = r.result;
      toast(r.result.valid ? `Auto-fix: ${r.result.steps.length} step(s) — design is valid` : `Auto-fix: ${r.result.steps.length} step(s); some problems need your decision`, !r.result.valid);
      renderPanel();
    } catch (e) { reportError(e); renderPanel(); }
  };
}

// ---------- Step 3: Produce ----------
function saveProd() {
  try { localStorage.setItem('board-studio-prod', JSON.stringify(S.prod)); } catch (e) { /* ignore */ }
}

function renderProduce(body) {
  const p = S.prod, L = S.layout;
  const presets = [['A4', 'A4 paper (297 × 210)'], ['A3', 'A3 paper (420 × 297)'], ['A2', 'A2 paper (594 × 420)'], ['Letter', 'US Letter'],
    ['board-600x400', 'Board 600 × 400'], ['board-800x600', 'Board 800 × 600'], ['board-1220x610', 'Board 1220 × 610'], ['custom', 'Custom size…']];
  const st = L?.nesting.stats;
  body.innerHTML = `
    ${!S.model.components.length ? '<div class="callout info">Add parts to this design before producing it.</div>' : ''}
    ${L ? `<div class="callout ${L.ready_for_production ? 'ok' : 'err'}">${L.ready_for_production
      ? '<b>Ready for production.</b> Geometry valid, every part nested, cut paths verified.'
      : `<b>Not ready:</b> ${L.blocking_issues.length} blocking issue(s).<br>${L.blocking_issues.slice(0, 3).map((i) => '• ' + esc(i.message)).join('<br>')}`}</div>` : ''}
    <div class="section"><h4>Sheet &amp; cutting</h4><div class="form">
      <label class="full">Sheet size<select class="input" id="pp-preset">${presets.map(([k, t]) => `<option value="${k}" ${k === p.preset ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
      ${p.preset === 'custom' ? `<label>Width (mm)<input class="input" id="pp-width" type="number" min="20" value="${p.width}" /></label>
        <label>Height (mm)<input class="input" id="pp-height" type="number" min="20" value="${p.height}" /></label>` : ''}
      <label>Margin (mm)<input class="input" id="pp-margin" type="number" min="0" value="${p.margin}" /></label>
      <label>Gap between parts<input class="input" id="pp-spacing" type="number" min="0" value="${p.spacing}" /></label>
      <label>Rotate parts<select class="input" id="pp-rotation"><option value="orthogonal" ${p.rotation === 'orthogonal' ? 'selected' : ''}>Allow 90°</option>
        <option value="none" ${p.rotation === 'none' ? 'selected' : ''}>Never</option></select></label>
      <label>Booklet paper<select class="input" id="pp-paper">${['A4', 'A3', 'Letter'].map((x) => `<option ${x === p.paper ? 'selected' : ''}>${x}</option>`).join('')}</select></label>
      <label class="check full"><input type="checkbox" id="pp-kerf" ${p.kerf ? 'checked' : ''} /> Kerf compensation (${S.model.material.kerf} mm laser width)</label>
    </div><div class="row-actions"><button class="btn primary" id="pp-apply">Update layout</button></div></div>
    ${L ? `<div class="section"><h4>Material usage</h4><div class="stats">
      <div class="stat"><b>${L.nesting.sheet_count}</b><span>Sheets</span></div>
      <div class="stat"><b>${fmt(st.efficiency_percent)}%</b><span>Used</span></div>
      <div class="stat"><b>${fmt(st.waste_percent)}%</b><span>Waste</span></div></div>
      <dl class="kv" style="margin-top:12px"><dt>Total material</dt><dd>${fmt(st.total_material_area / 100)} cm²</dd>
      <dt>Parts</dt><dd>${fmt(st.used_area / 100)} cm²</dd><dt>Cut paths</dt><dd>${L.cut.counts.outer} outer · ${L.cut.counts.inner} inner</dd></dl></div>
    <div class="section"><h4>Export</h4>
      <button class="btn primary block" id="ex-pdf">${icon('download')} PDF production booklet</button>
      <p class="lead" style="font-size:12px;margin:8px 0 12px">Cover, 1:1 cutting templates, dimensioned part drawings and assembly sequence.</p>
      <div class="export-list">${L.cut.sheets.map((s, i) => `<div class="export-sheet"><span class="grow">Sheet ${i + 1}</span>
        <button class="btn small" data-ex="svg" data-sheet="${i + 1}" title="Laser cutter vector file">SVG</button>
        <button class="btn small" data-ex="dxf" data-sheet="${i + 1}" title="CNC / CAD file">DXF</button>
        <button class="btn small" data-ex="png" data-sheet="${i + 1}" title="Image preview">PNG</button></div>`).join('')}</div>
      ${L.ready_for_production ? '' : '<label class="check" style="margin-top:12px"><input type="checkbox" id="ex-force" /> Export anyway as a marked draft</label>'}
    </div>` : ''}`;

  const num = (id, def) => { const n = parseFloat($(id)?.value); return Number.isFinite(n) ? n : def; };
  $('#pp-preset').onchange = (e) => { p.preset = e.target.value; saveProd(); renderPanel(); };
  $('#pp-apply').onclick = async (ev) => {
    Object.assign(p, { margin: num('#pp-margin', 10), spacing: num('#pp-spacing', 5), rotation: $('#pp-rotation').value,
      paper: $('#pp-paper').value, kerf: $('#pp-kerf').checked });
    if (p.preset === 'custom') Object.assign(p, { width: num('#pp-width', 600), height: num('#pp-height', 400) });
    saveProd();
    ev.currentTarget.disabled = true;
    sheet2d._fitted = false;
    await refreshLayout();
    renderPanel();
    toast('Layout updated');
  };
  const exportOpts = (extra = {}) => ({ ...layoutOpts(), paper: p.paper, force: $('#ex-force')?.checked ? 1 : '', ...extra });
  if ($('#ex-pdf')) $('#ex-pdf').onclick = () => download('pdf', exportOpts(), `${S.designId}-booklet.pdf`);
  $$('[data-ex]', body).forEach((b) => (b.onclick = () => {
    const { ex, sheet } = b.dataset;
    if (ex === 'png') return pngPreview(+sheet, exportOpts({ sheet }));
    download(ex, exportOpts({ sheet }), `${S.designId}-sheet${sheet}.${ex}`);
  }));
}

async function download(fmtName, opts, name) {
  try {
    toast('Preparing download…');
    const blob = await Api.download(S.designId, fmtName, opts);
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: name });
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    toast(`Downloaded ${name}`);
  } catch (e) { reportError(e); }
}

async function pngPreview(sheet, opts) {
  try {
    const svg = await Api.exportText(S.designId, 'svg', opts);
    const { width, height } = S.layout.nesting.sheet;
    const pxPerMm = 6;
    const img = new Image();
    img.src = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
    await img.decode();
    const c = Object.assign(document.createElement('canvas'), { width: Math.round(width * pxPerMm), height: Math.round(height * pxPerMm) });
    const g = c.getContext('2d');
    g.fillStyle = '#ffffff';
    g.fillRect(0, 0, c.width, c.height);
    g.drawImage(img, 0, 0, c.width, c.height);
    URL.revokeObjectURL(img.src);
    c.toBlob((b) => {
      const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(b), download: `${S.designId}-sheet${sheet}.png` });
      a.click();
    }, 'image/png');
  } catch (e) { reportError(e); }
}

// ---------------------------------------------------------------------------
// Designs manager (open / create / duplicate / rename / delete)
// ---------------------------------------------------------------------------
const slug = (name) => (name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40) || 'design')
  + '-' + Math.random().toString(36).slice(2, 6);

function storageCallout() {
  const st = S.storage;
  if (!st) return '';
  if (st.config_error) return `<div class="callout err" style="margin:0"><b>Firebase is not connected:</b> ${esc(st.config_error)}</div>`;
  if (st.backend === 'firestore') return `<div class="callout ok" style="margin:0">Designs are saved to <b>Firebase</b> (${esc(st.project)}) after every change and can be opened from any device.</div>`;
  if (st.persistent) return '<div class="callout info" style="margin:0">Designs are saved on this server after every change.</div>';
  return `<div class="callout warn" style="margin:0"><b>Not saved permanently.</b> This server has no database connected, so designs are lost when it restarts.
    To keep them, connect Firebase by setting <code>FIREBASE_SERVICE_ACCOUNT</code> on the server (see the <a href="/docs/board-api.md" target="_blank">setup guide</a>).</div>`;
}

async function openDesignsDialog() {
  const dlg = $('#dlg-designs');
  closeDrawers();
  try { S.designs = (await Api.designs()).designs; } catch (e) { reportError(e); }
  const body = $('#designs-body');
  body.innerHTML = `
    ${storageCallout()}
    <h4>Your designs (${S.designs.length})</h4>
    <div class="design-list">${S.designs.map((d) => `
      <div class="design-card${d.id === S.designId ? ' current' : ''}">
        <div style="min-width:0"><div class="t">${esc(d.name || d.id)}</div>
          <div class="s">${d.components} parts · ${d.joints} joints · rev ${d.revision}${d.updated ? ' · ' + esc(d.updated.replace('T', ' ').replace('Z', ' UTC')) : ''}</div></div>
        <div class="acts">
          ${d.id === S.designId ? '<span class="chip joined" style="align-self:center">Open now</span>' : `<button class="btn small primary" data-open="${esc(d.id)}">Open</button>`}
          <button class="btn small" data-dup="${esc(d.id)}">Duplicate</button>
          <button class="btn small" data-ren="${esc(d.id)}">Rename</button>
          <button class="btn small danger" data-del="${esc(d.id)}">Delete</button>
        </div></div>`).join('') || '<div class="empty">No designs yet — create one below.</div>'}</div>
    <h4>Create a new design</h4>
    <div class="new-grid">
      <form class="new-card" id="new-boat">
        <h5>Sailing boat (parametric)</h5><p>A complete, validated boat built from your dimensions — slots are generated automatically.</p>
        <div class="form">
          <label class="full">Name<input class="input" name="name" value="My boat" required maxlength="80" /></label>
          <label>Length (mm)<input class="input" name="length" type="number" value="300" min="200" max="800" required /></label>
          <label>Width (mm)<input class="input" name="beam" type="number" value="80" min="50" max="300" required /></label>
          <label>Hull depth (mm)<input class="input" name="depth" type="number" value="50" min="30" max="150" required /></label>
          <label>Mast height (mm)<input class="input" name="mast_height" type="number" value="200" min="60" max="600" required /></label>
          <label class="full">Board thickness<select class="input" name="thickness"><option value="3">3 mm</option><option value="4">4 mm</option><option value="6">6 mm</option></select></label>
        </div><button class="btn primary" type="submit">Create boat</button></form>
      <form class="new-card" id="new-blank">
        <h5>Blank design</h5><p>An empty design for an AI agent or script to fill through the API (<code>/api/v1</code>).</p>
        <div class="form"><label class="full">Name<input class="input" name="name" value="New design" required maxlength="80" /></label></div>
        <button class="btn" type="submit">Create blank design</button></form>
    </div>`;
  if (!dlg.open) dlg.showModal();

  $$('[data-open]', body).forEach((b) => (b.onclick = async () => { dlg.close(); await openDesign(b.dataset.open).catch(reportError); }));
  $$('[data-dup]', body).forEach((b) => (b.onclick = async () => {
    const src = S.designs.find((d) => d.id === b.dataset.dup);
    const name = prompt('Name for the copy:', `${src.name} (copy)`);
    if (!name?.trim()) return;
    try { await Api.duplicateDesign(src.id, slug(name), name.trim()); toast(`Created “${name.trim()}”`); await openDesignsDialog(); } catch (e) { reportError(e); }
  }));
  $$('[data-ren]', body).forEach((b) => (b.onclick = async () => {
    const d = S.designs.find((x) => x.id === b.dataset.ren);
    const name = prompt('New name:', d.name);
    if (!name?.trim() || name.trim() === d.name) return;
    try {
      await Api.renameDesign(d.id, name.trim());
      toast('Renamed');
      if (d.id === S.designId) await refresh();
      await openDesignsDialog();
    } catch (e) { reportError(e); }
  }));
  $$('[data-del]', body).forEach((b) => (b.onclick = async () => {
    const d = S.designs.find((x) => x.id === b.dataset.del);
    if (!confirm(`Delete “${d.name}” permanently? This cannot be undone.`)) return;
    try {
      await Api.deleteDesign(d.id);
      toast(`Deleted “${d.name}”`);
      if (d.id === S.designId) {
        S.model = S.validation = S.layout = null;
        S.designId = null;
        await loadDesigns();
        if (S.designId) await openDesign(S.designId); else renderAll();
      }
      await openDesignsDialog();
    } catch (e) { reportError(e); }
  }));
  $('#new-boat').onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const name = f.get('name').trim();
    const params = {};
    for (const k of ['length', 'beam', 'depth', 'mast_height', 'thickness']) params[k] = parseFloat(f.get(k));
    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true;
    btn.textContent = 'Building & validating…';
    try {
      const id = slug(name);
      const r = await Api.createBoat(id, name, params);
      const fails = r.join_failures.length;
      toast(fails ? `Created “${name}” — ${fails} joint(s) need attention in Check` : `Created “${name}” — fully validated`, !!fails);
      dlg.close();
      await loadDesigns(id);
      await openDesign(id);
    } catch (err) { reportError(err); btn.disabled = false; btn.textContent = 'Create boat'; }
  };
  $('#new-blank').onsubmit = async (e) => {
    e.preventDefault();
    const name = new FormData(e.target).get('name').trim();
    try {
      const id = slug(name);
      await Api.createBlank(id, name);
      toast(`Created “${name}”`);
      dlg.close();
      await loadDesigns(id);
      await openDesign(id);
    } catch (err) { reportError(err); }
  };
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------
$$('#steps button, #tabbar button').forEach((b) => (b.onclick = () => setStep(b.dataset.step)));
$$('#view-seg button').forEach((b) => (b.onclick = () => setView(b.dataset.view)));
$$('#side-seg button').forEach((b) => (b.onclick = () => { S.sideTab = b.dataset.side; renderSidebar(); }));
$$('[data-cam]').forEach((b) => (b.onclick = () => view3d.view(b.dataset.cam)));
$$('[data-close]').forEach((b) => (b.onclick = closeDrawers));
$('#search').oninput = (e) => { S.filter = e.target.value; renderSidebar(); };
$('#btn-sidebar').onclick = () => (document.body.classList.contains('side-open') ? closeDrawers() : openSide());
$('#btn-panel').onclick = openPanel;
$('#scrim').onclick = closeDrawers;
$('#design-btn').onclick = openDesignsDialog;
$('#status-pill').onclick = async () => { await setStep('check', { keepPanel: true }); if (mqSheet.matches) openPanel(); };
$('#btn-fit-3d').onclick = () => view3d.view('iso');
$('#btn-fit-2d').onclick = () => sheet2d.fit();
bindFullscreen($('.view-3d'), $('#btn-full-3d'), () => requestAnimationFrame(() => view3d.resize()));
bindFullscreen($('.view-2d'), $('#btn-full-2d'), () => requestAnimationFrame(() => { sheet2d._apply(); sheet2d.fit(); }));
$('#btn-edges').onclick = (e) => { view3d.setEdges(!view3d.showEdges); e.currentTarget.classList.toggle('on', view3d.showEdges); };
$('#btn-labels-2d').onclick = (e) => { sheet2d.setLabels(!sheet2d.labels); e.currentTarget.classList.toggle('on', sheet2d.labels); };
$('#explode').oninput = (e) => view3d.setExplode(e.target.value / 100);

const menu = $('#menu');
$('#btn-menu').onclick = (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; };
document.addEventListener('click', (e) => { if (!menu.hidden && !e.target.closest('.menu-wrap')) menu.hidden = true; });
menu.onclick = async (e) => {
  const act = e.target.closest('[data-act]')?.dataset.act;
  if (!act) return;
  menu.hidden = true;
  if (act === 'designs') openDesignsDialog();
  if (act === 'shortcuts') $('#dlg-shortcuts').showModal();
  if (act === 'validate') {
    await refresh().catch(reportError);
    toast(S.validation?.valid ? 'Validation passed' : `${S.validation?.summary.errors} error(s) found`, !S.validation?.valid);
  }
};

mqSheet.addEventListener('change', () => { closeDrawers(); setView(S.views[S.step] || STEPS[S.step].view(), false); });
mqSide.addEventListener('change', closeDrawers);

window.addEventListener('keydown', (e) => {
  if (e.target.matches('input, select, textarea') || document.querySelector('dialog[open]')) return;
  if (e.key === 'Escape') { closeDrawers(); if (S.selected) select(null); }
  if (e.key === '1') setStep('design');
  if (e.key === '2') setStep('check');
  if (e.key === '3') setStep('produce');
  if (e.key === 'f') { sheet2d.fit(); view3d.view('iso'); }
  if (e.key === 'v') menu.querySelector('[data-act=validate]').click();
  if (e.key === '?') $('#dlg-shortcuts').showModal();
});

(async () => {
  try {
    const q = new URLSearchParams(location.search);
    const step = { production: 'produce', produce: 'produce', check: 'check' }[q.get('mode') || q.get('step')] || 'design';
    S.step = step;
    document.body.dataset.step = step;
    $$('#steps button, #tabbar button').forEach((b) => b.classList.toggle('on', b.dataset.step === step));
    $('#fab-label').textContent = STEPS[step].fab;
    setView(q.get('view') || STEPS[step].view(), false);
    Api.storage().then((st) => { S.storage = st; renderSaveState(); }).catch(() => {});
    await loadDesigns();
    if (!S.designId) { renderAll(); await openDesignsDialog(); window.__studioReady = true; return; }
    await refresh();
    if (q.get('explode')) { $('#explode').value = q.get('explode'); view3d.setExplode(+q.get('explode') / 100); }
    if (q.get('select')) select(q.get('select'), 'tree');
    if (q.get('panel') === 'open') openPanel();
    if (q.get('side') === 'open') openSide();
    if (q.get('dialog') === 'designs') await openDesignsDialog();
    window.__studioReady = true;
  } catch (e) { reportError(e); }
})();
