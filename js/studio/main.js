/**
 * Board Studio controller. All state lives on the server; every edit is an API call that
 * runs through the same validation pipeline AI agents use. After each change the studio
 * re-reads the 3D model, the 2D layout and the validation report.
 */
import { Api, ApiError } from './api.js';
import { Viewport3D } from './viewport3d.js';
import { Sheet2D } from './sheet2d.js';

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = (v, n = 1) => (Math.round(v * 10 ** n) / 10 ** n).toString();

const S = {
  designId: null, model: null, validation: null, layout: null, selected: null, mode: 'design',
  prod: { preset: 'A3', width: 600, height: 400, margin: 10, spacing: 5, rotation: 'orthogonal', kerf: true, paper: 'A4' }
};
try { Object.assign(S.prod, JSON.parse(localStorage.getItem('board-studio-prod') || '{}')); } catch (e) { /* storage unavailable */ }

function toast(msg, err = false) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = `toast show${err ? ' err' : ''}`;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.className = 'toast'), err ? 6000 : 2600);
}

function reportError(e) {
  console.error(e);
  if (e instanceof ApiError) {
    const first = e.issues.find((i) => i.severity === 'error') || e.issues[0];
    toast(`${e.message}${first ? ' — ' + first.message : ''}`, true);
  } else toast(String(e.message || e), true);
}

// ---------------------------------------------------------------------------
// Viewports
// ---------------------------------------------------------------------------
const tip2 = $('#tip-2d'), tip3 = $('#tip-3d');
function showTip(tipEl, id, e) {
  if (!id || !e) { tipEl.style.display = 'none'; return; }
  const c = S.model?.components.find((x) => x.id === id);
  if (!c) return;
  const r = tipEl.parentElement.getBoundingClientRect();
  tipEl.innerHTML = `<b class="mono">${esc(id)}</b> · ${esc(c.name)}<br><span class="muted">${fmt(c.dimensions_2d.width)} × ${fmt(c.dimensions_2d.height)} × ${c.thickness} mm · ${c.state}</span>`;
  tipEl.style.display = 'block';
  tipEl.style.left = `${e.clientX - r.left + 14}px`;
  tipEl.style.top = `${e.clientY - r.top + 14}px`;
}

const view3d = new Viewport3D($('#canvas3d'), { onSelect: (id) => select(id, 'view3d'), onHover: (id, e) => showTip(tip3, id, e) });
const sheet2d = new Sheet2D($('#svg2d'), {
  onSelect: (id) => select(id, 'view2d'), onHover: (id, e) => showTip(tip2, id, e), scalebar: $('#scalebar-2d'),
  onCursor: (txt) => ($('#cursor-pos').textContent = txt)
});

function select(id, source) {
  S.selected = id;
  view3d.setSelected(id);
  sheet2d.setSelected(id);
  if (id && source !== 'view3d' && source !== 'issue') view3d.focus(id);
  if (id && source === 'tree') sheet2d.focus(id);
  renderTree();
  renderInspector();
  if (id) setTab('inspector');
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------
function layoutOpts() {
  const p = S.prod;
  const base = { margin: p.margin, spacing: p.spacing, rotation: p.rotation, kerf: p.kerf ? 1 : 0 };
  if (S.mode === 'design') return { preset: 'board-800x600', margin: 10, spacing: 8, rotation: 'orthogonal' };
  return p.preset === 'custom' ? { ...base, width: p.width, height: p.height } : { ...base, preset: p.preset };
}

async function refresh() {
  if (!S.designId) return;
  const [model, val] = await Promise.all([Api.model3d(S.designId), Api.validate(S.designId)]);
  S.model = model;
  S.validation = val.validation;
  view3d.load(model);
  await refreshLayout();
  if (S.selected && !model.components.some((c) => c.id === S.selected)) S.selected = null;
  renderAll();
}

async function refreshLayout() {
  try {
    S.layout = await Api.layout2d(S.designId, layoutOpts());
    const states = Object.fromEntries(S.model.components.map((c) => [c.id, c.state]));
    sheet2d.load(S.layout, { mode: S.mode, states });
    $('#label-2d').textContent = S.mode === 'production' ? 'Production cutting sheets' : '2D parts (flat cut profiles)';
  } catch (e) {
    S.layout = null;
    reportError(e);
  }
}

function renderAll() {
  renderStatus();
  renderTree();
  renderJoints();
  renderInspector();
  renderValidation();
  renderProduction();
  view3d.setSelected(S.selected);
  sheet2d.setSelected(S.selected);
}

function renderStatus() {
  const v = S.validation, m = S.model;
  const pill = $('#status-pill');
  const cls = !v ? '' : v.valid ? (v.complete ? 'ok' : 'warn') : 'err';
  const text = !v ? '—' : v.valid ? (v.complete ? 'Valid · fully joined' : `Valid · ${v.summary.warnings} warnings`) : `${v.summary.errors} errors`;
  pill.innerHTML = `<span class="dot ${cls}"></span><span>${text}</span>`;
  $('#issue-count').textContent = v ? v.summary.errors + v.summary.warnings : 0;
  $('#issue-count').className = `badge ${v?.summary.errors ? 'err' : v?.summary.warnings ? 'warn' : ''}`;
  $('#sb-material').textContent = m ? `${m.material.name} · t ${m.material.thickness} mm · kerf ${m.material.kerf} · clearance ${m.material.clearance}` : '';
  $('#sb-revision').textContent = m ? `Revision ${m.revision}` : '';
}

function renderTree() {
  const tree = $('#tree');
  if (!S.model) { tree.innerHTML = ''; return; }
  const groups = {};
  S.model.components.forEach((c) => (groups[c.group] ||= []).push(c));
  $('#comp-count').textContent = S.model.components.length;
  tree.innerHTML = Object.entries(groups).map(([g, cs]) => `
    <div class="tree-group">
      <div class="tree-group-title"><span>${esc(g)}</span><span>${cs.length}</span></div>
      ${cs.map((c) => `<div class="tree-item${c.id === S.selected ? ' sel' : ''}" data-id="${esc(c.id)}" title="${esc(c.name)}">
        <span class="dot ${c.state}"></span><span class="name">${esc(c.id)}</span>
        <span class="meta">${fmt(c.dimensions_2d.width, 0)}×${fmt(c.dimensions_2d.height, 0)}</span></div>`).join('')}
    </div>`).join('');
  tree.querySelectorAll('.tree-item').forEach((n) => (n.onclick = () => select(n.dataset.id, 'tree')));
}

function jointBroken(jid) {
  return (S.validation?.issues || []).some((i) => i.joint === jid && i.severity === 'error');
}

function renderJoints() {
  const list = $('#joint-list');
  const joints = S.model?.joints || [];
  $('#joint-count').textContent = joints.length;
  list.innerHTML = joints.map((j) => {
    const cls = j.status !== 'joined' ? 'cut' : jointBroken(j.id) ? 'error' : 'joined';
    return `<div class="joint-item" data-a="${esc(j.a)}" title="${esc(j.status)}"><span class="dot ${cls}"></span>
      <span class="mono" style="font-size:11.5px;overflow:hidden;text-overflow:ellipsis">${esc(j.id)}</span>
      <span class="jt">${esc(j.type.replace('_', ' '))}</span></div>`;
  }).join('') || '<div class="muted" style="padding:10px 12px">No joints yet.</div>';
  list.querySelectorAll('.joint-item').forEach((n) => (n.onclick = () => select(n.dataset.a, 'tree')));
}

// ---------------------------------------------------------------------------
// Inspector
// ---------------------------------------------------------------------------
function profileSvg(c) {
  const pts = c.cut_outline;
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const w = x1 - x0, h = y1 - y0, pad = Math.max(w, h) * 0.14;
  const d = 'M' + pts.map((p) => `${p[0]},${-p[1]}`).join('L') + 'Z';
  const feats = c.features.map((f) => {
    const col = { slot: 'var(--slot)', opening: 'var(--opening)', hole: 'var(--hole)' }[f.kind];
    const dash = f.kind === 'opening' ? `stroke-dasharray="${w / 80} ${w / 160}"` : '';
    if (f.shape === 'circle') return `<circle cx="${f.center[0]}" cy="${-f.center[1]}" r="${f.diameter / 2}" fill="#10141a" stroke="${col}" ${dash} vector-effect="non-scaling-stroke"/>`;
    return `<rect x="${f.center[0] - f.width / 2}" y="${-f.center[1] - f.height / 2}" width="${f.width}" height="${f.height}"
      transform="rotate(${-(f.angle || 0)} ${f.center[0]} ${-f.center[1]})" fill="#10141a" stroke="${col}" ${dash} vector-effect="non-scaling-stroke"/>`;
  }).join('');
  const fs = Math.max(w, h) * 0.055;
  return `<svg class="profile" viewBox="${x0 - pad} ${-y1 - pad} ${w + 2 * pad} ${h + 2 * pad}" preserveAspectRatio="xMidYMid meet">
    <path d="${d}" fill="#d6b483" stroke="var(--cut)" vector-effect="non-scaling-stroke" stroke-width="1.2"/>${feats}
    <text x="${(x0 + x1) / 2}" y="${-y0 + pad * 0.75}" font-size="${fs}" fill="#8b96a6" text-anchor="middle">${fmt(w)} mm</text>
    <text x="${x1 + pad * 0.5}" y="${-(y0 + y1) / 2}" font-size="${fs}" fill="#8b96a6" text-anchor="middle"
      transform="rotate(-90 ${x1 + pad * 0.5} ${-(y0 + y1) / 2})">${fmt(h)} mm</text></svg>`;
}

function renderInspector() {
  const box = $('#tab-inspector');
  const c = S.model?.components.find((x) => x.id === S.selected);
  if (!c) {
    const m = S.model;
    box.innerHTML = m ? `<div class="section"><h4>Design</h4><div class="title-row"><span class="id">${esc(m.name)}</span></div>
      <dl class="kv" style="margin-top:10px">
        <dt>Components</dt><dd>${m.components.length}</dd><dt>Joints</dt><dd>${m.joints.length}</dd>
        <dt>Assembled size</dt><dd>${['x', 'y', 'z'].map((_, i) => fmt(m.bounds.max[i] - m.bounds.min[i], 0)).join(' × ')} mm</dd>
        <dt>Material</dt><dd>${esc(m.material.name)}</dd></dl></div>
      <div class="banner ${S.validation?.valid ? 'ok' : 'err'}">${S.validation?.valid ? 'Geometry validated — no errors.' : 'This design has validation errors. See the Validation tab.'}</div>
      <div class="section muted">Select a component in the tree, the 2D sheet or the 3D view to inspect and edit it.</div>` : '';
    return;
  }
  const joints = S.model.joints.filter((j) => j.a === c.id || j.b === c.id);
  const issues = (S.validation?.issues || []).filter((i) => (i.components || []).includes(c.id));
  const pos = c.placement.position, rot = c.placement.rotation;
  box.innerHTML = `
    <div class="section">
      <div class="title-row"><span class="id">${esc(c.id)}</span><span class="state-chip ${c.state}">${c.state === 'cut' ? 'cut · not joined' : c.state}</span></div>
      <div class="muted" style="margin-top:2px">${esc(c.name)} · ${esc(c.group)}</div>
      <div style="margin-top:10px">${profileSvg(c)}</div>
    </div>
    <div class="section"><h4>Dimensions</h4><dl class="kv">
      <dt>Cut profile</dt><dd>${fmt(c.dimensions_2d.width, 2)} × ${fmt(c.dimensions_2d.height, 2)} mm</dd>
      <dt>Thickness</dt><dd>${c.thickness} mm</dd><dt>Net area</dt><dd>${fmt(c.dimensions_2d.area / 100, 1)} cm²</dd>
      <dt>World bounds</dt><dd>${c.world_bounds.min.map((v) => fmt(v, 0)).join(', ')} → ${c.world_bounds.max.map((v) => fmt(v, 0)).join(', ')}</dd>
    </dl></div>
    <div class="section"><h4>Placement <span class="muted" style="text-transform:none;letter-spacing:0">validated on apply</span></h4>
      <div class="xyz"><label>Position</label>${pos.map((v, i) => `<input data-k="p${i}" value="${fmt(v, 3)}" />`).join('')}</div>
      <div class="xyz"><label>Rotation°</label>${rot.map((v, i) => `<input data-k="r${i}" value="${fmt(v, 3)}" />`).join('')}</div>
      <label class="check"><input type="checkbox" id="chk-detach" /> Detach joints this change breaks</label>
      <div class="row-actions"><button class="btn small" id="btn-reset-place">Reset</button><button class="btn small primary" id="btn-apply-place">Apply</button></div>
    </div>
    <div class="section"><h4>Features <span class="badge">${c.features.length}</span></h4>
      ${c.features.map((f) => `<div class="list-item"><span class="chip ${f.kind}">${f.kind}</span><span class="grow mono">${esc(f.id)}</span>
        <span class="muted mono">${f.shape === 'circle' ? 'Ø' + fmt(f.diameter, 2) : fmt(f.width, 2) + '×' + fmt(f.height, 2)}</span></div>`).join('') || '<div class="muted">No interior cuts.</div>'}
      ${c.tabs.map((t) => `<div class="list-item"><span class="chip tab">tab</span><span class="grow mono">${esc(t.id)} · edge ${t.edge}</span>
        <span class="muted mono">${fmt(t.width, 1)}×${fmt(t.depth, 1)}</span></div>`).join('')}
    </div>
    <div class="section"><h4>Joints <span class="badge">${joints.length}</span></h4>
      ${joints.map((j) => `<div class="list-item"><span class="dot ${j.status !== 'joined' ? 'cut' : jointBroken(j.id) ? 'error' : 'joined'}"></span>
        <span class="grow mono" title="${esc(j.type)}">${esc(j.id)}</span>
        <span class="muted">${esc(j.a === c.id ? '→ ' + j.b : '← ' + j.a)}</span>
        <button class="btn small ghost" data-check="${esc(j.id)}" title="Dry-run validation">Check</button>
        ${j.status !== 'joined' ? `<button class="btn small" data-rejoin="${esc(j.id)}">Re-join</button>` : ''}</div>`).join('') || '<div class="muted">Not joined to anything.</div>'}
    </div>
    ${issues.length ? `<div class="section"><h4>Issues <span class="badge ${issues.some((i) => i.severity === 'error') ? 'err' : 'warn'}">${issues.length}</span></h4>
      ${issues.map((i) => `<div class="list-item" style="align-items:flex-start"><span class="dot ${i.severity === 'error' ? 'err' : 'warn'}" style="margin-top:5px"></span><span>${esc(i.message)}</span></div>`).join('')}</div>` : ''}`;

  $('#btn-reset-place').onclick = renderInspector;
  $('#btn-apply-place').onclick = async () => {
    const v = (k) => parseFloat(box.querySelector(`[data-k="${k}"]`).value);
    const placement = { position: [v('p0'), v('p1'), v('p2')], rotation: [v('r0'), v('r1'), v('r2')] };
    if ([...placement.position, ...placement.rotation].some((x) => !Number.isFinite(x))) return toast('Enter numeric values', true);
    try {
      const r = await Api.updateComponent(S.designId, c.id, { placement }, { detach_broken_joints: $('#chk-detach').checked });
      const det = r.result.detached_joints || [];
      toast(det.length ? `Placement applied; detached ${det.join(', ')}` : 'Placement applied and validated');
      await refresh();
    } catch (e) { reportError(e); }
  };
  box.querySelectorAll('[data-check]').forEach((b) => (b.onclick = async () => {
    const j = S.model.joints.find((x) => x.id === b.dataset.check);
    try {
      const r = await Api.checkJoint(S.designId, { ...j, id: j.id + '-check' });
      const errs = r.issues.filter((i) => i.severity === 'error');
      toast(errs.length ? `${j.id}: ${errs[0].code} — ${errs[0].message}` : `${j.id}: geometry fits (dry run)`, !!errs.length);
    } catch (e) { reportError(e); }
  }));
  box.querySelectorAll('[data-rejoin]').forEach((b) => (b.onclick = async () => {
    const j = S.model.joints.find((x) => x.id === b.dataset.rejoin);
    const spec = { id: j.id, type: j.type, a: j.a, b: j.b, tab: j.tab, a_edge: j.a_edge, b_edge: j.b_edge };
    Object.keys(spec).forEach((k) => spec[k] === undefined && delete spec[k]);
    try {
      await Api.unjoin(S.designId, j.id);
      await Api.join(S.designId, spec, true);
      toast(`${j.id} re-joined`);
    } catch (e) { reportError(e); }
    await refresh();
  }));
}

// ---------------------------------------------------------------------------
// Validation panel
// ---------------------------------------------------------------------------
function renderValidation() {
  const box = $('#tab-validation');
  const v = S.validation;
  if (!v) { box.innerHTML = ''; return; }
  const issues = [...v.issues].sort((a, b) => (a.severity === b.severity ? 0 : a.severity === 'error' ? -1 : 1));
  box.innerHTML = `
    <div class="section"><div class="summary-grid">
      <div class="stat"><b style="color:${v.summary.errors ? 'var(--err)' : 'var(--ok)'}">${v.summary.errors}</b><span>Errors</span></div>
      <div class="stat"><b style="color:${v.summary.warnings ? 'var(--warn)' : 'inherit'}">${v.summary.warnings}</b><span>Warnings</span></div>
      <div class="stat"><b>${v.summary.joined}/${v.summary.joints}</b><span>Joined</span></div></div></div>
    ${v.valid && v.complete ? '<div class="banner ok">All 2D, joint and 3D interference checks pass. Every component is joined into one assembly.</div>' : ''}
    ${issues.map((i, k) => `<div class="issue" data-k="${k}"><span class="dot ${i.severity === 'error' ? 'err' : i.severity === 'warning' ? 'warn' : ''}"></span>
      <div><div class="code">${esc(i.code)} · ${esc(i.category)}${i.components?.length ? ' · ' + esc(i.components.join(', ')) : ''}</div>
      <div class="msg">${esc(i.message)}</div>${i.suggestion ? `<div class="code" style="margin-top:3px">suggestion: ${esc(i.suggestion.action)} ${esc(i.suggestion.component)} by [${i.suggestion.delta.join(', ')}]</div>` : ''}</div></div>`).join('')}`;
  box.querySelectorAll('.issue').forEach((n) => (n.onclick = () => {
    const i = issues[+n.dataset.k];
    if (i.components?.[0]) select(i.components[0], 'issue');
    if (i.location) view3d.focusPoint(i.location);
    else if (i.components?.[0]) view3d.focus(i.components[0]);
  }));
}

// ---------------------------------------------------------------------------
// Production
// ---------------------------------------------------------------------------
function saveProd() {
  try { localStorage.setItem('board-studio-prod', JSON.stringify(S.prod)); } catch (e) { /* ignore */ }
}

function renderProduction() {
  const box = $('#tab-production');
  const p = S.prod, L = S.layout;
  const presets = ['A4', 'A3', 'A2', 'Letter', 'board-600x400', 'board-800x600', 'board-1220x610', 'custom'];
  const st = L?.nesting.stats;
  const prodLayout = S.mode === 'production';
  box.innerHTML = `
    <div class="section"><h4>Sheet & material</h4><div class="form-grid">
      <label class="full">Sheet size<select class="input" id="pp-preset">${presets.map((x) => `<option ${x === p.preset ? 'selected' : ''}>${x}</option>`).join('')}</select></label>
      ${p.preset === 'custom' ? `<label>Width (mm)<input class="input" id="pp-width" type="number" value="${p.width}" /></label>
        <label>Height (mm)<input class="input" id="pp-height" type="number" value="${p.height}" /></label>` : ''}
      <label>Margin (mm)<input class="input" id="pp-margin" type="number" min="0" value="${p.margin}" /></label>
      <label>Spacing (mm)<input class="input" id="pp-spacing" type="number" min="0" value="${p.spacing}" /></label>
      <label>Rotation<select class="input" id="pp-rotation"><option value="orthogonal" ${p.rotation === 'orthogonal' ? 'selected' : ''}>0° / 90°</option>
        <option value="none" ${p.rotation === 'none' ? 'selected' : ''}>None</option></select></label>
      <label>Booklet paper<select class="input" id="pp-paper">${['A4', 'A3', 'Letter'].map((x) => `<option ${x === p.paper ? 'selected' : ''}>${x}</option>`).join('')}</select></label>
      <label class="check full"><input type="checkbox" id="pp-kerf" ${p.kerf ? 'checked' : ''} /> Kerf compensation (${S.model?.material.kerf ?? '—'} mm)</label>
    </div>
    <div class="row-actions">${prodLayout ? '' : '<button class="btn small" id="pp-show">Show sheets</button>'}<button class="btn small primary" id="pp-apply">Re-nest</button></div></div>
    ${prodLayout && L ? `
    <div class="section"><h4>Nesting result</h4><div class="summary-grid">
      <div class="stat"><b>${L.nesting.sheet_count}</b><span>Sheets</span></div>
      <div class="stat"><b>${fmt(st.efficiency_percent)}%</b><span>Efficiency</span></div>
      <div class="stat"><b>${fmt(st.waste_percent)}%</b><span>Waste</span></div></div>
      <dl class="kv" style="margin-top:10px"><dt>Total material</dt><dd>${fmt(st.total_material_area / 100)} cm²</dd>
      <dt>Used by parts</dt><dd>${fmt(st.used_area / 100)} cm²</dd><dt>Waste</dt><dd>${fmt(st.waste_area / 100)} cm²</dd>
      <dt>Cut paths</dt><dd>${L.cut.counts.outer} outer · ${L.cut.counts.inner} inner</dd></dl></div>
    <div class="banner ${L.ready_for_production ? 'ok' : 'err'}">${L.ready_for_production ? 'Ready for production: geometry valid, every part nested, cut paths verified.'
      : `Not ready: ${L.blocking_issues.length} blocking issue(s).<br>${L.blocking_issues.slice(0, 4).map((i) => '• ' + esc(i.message)).join('<br>')}`}</div>
    <div class="section"><h4>Export</h4><div class="export-grid">
      <button class="btn" id="ex-pdf" style="grid-column:1/-1">PDF production booklet</button>
      ${L.cut.sheets.map((s, i) => `<button class="btn small" data-ex="svg" data-sheet="${i + 1}">SVG · sheet ${i + 1}</button>
        <button class="btn small" data-ex="dxf" data-sheet="${i + 1}">DXF · sheet ${i + 1}</button>
        <button class="btn small" data-ex="png" data-sheet="${i + 1}" style="grid-column:1/-1">PNG preview · sheet ${i + 1}</button>`).join('')}
    </div>${L.ready_for_production ? '' : '<label class="check" style="margin-top:8px"><input type="checkbox" id="ex-force" /> Export anyway as marked draft</label>'}</div>` : ''}`;

  const num = (id, def) => { const n = parseFloat($(id)?.value); return Number.isFinite(n) ? n : def; };
  $('#pp-preset').onchange = (e) => { p.preset = e.target.value; saveProd(); renderProduction(); };
  $('#pp-apply').onclick = async () => {
    Object.assign(p, { margin: num('#pp-margin', 10), spacing: num('#pp-spacing', 5), rotation: $('#pp-rotation').value,
      paper: $('#pp-paper').value, kerf: $('#pp-kerf').checked });
    if (p.preset === 'custom') Object.assign(p, { width: num('#pp-width', 600), height: num('#pp-height', 400) });
    saveProd();
    sheet2d._fitted = false;
    await refreshLayout();
    renderProduction();
  };
  if ($('#pp-show')) $('#pp-show').onclick = () => setMode('production');
  const exportOpts = (extra = {}) => ({ ...layoutOpts(), paper: p.paper, force: $('#ex-force')?.checked ? 1 : '', ...extra });
  if ($('#ex-pdf')) $('#ex-pdf').onclick = () => download('pdf', exportOpts(), `${S.designId}-booklet.pdf`);
  box.querySelectorAll('[data-ex]').forEach((b) => (b.onclick = () => {
    const { ex, sheet } = b.dataset;
    if (ex === 'png') return pngPreview(+sheet, exportOpts({ sheet }));
    download(ex, exportOpts({ sheet }), `${S.designId}-sheet${sheet}.${ex}`);
  }));
}

async function download(fmtName, opts, name) {
  try {
    const blob = await Api.download(S.designId, fmtName, opts);
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: name });
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
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
// Chrome: tabs, modes, layout, designs
// ---------------------------------------------------------------------------
function setTab(tab) {
  document.querySelectorAll('#right-tabs button').forEach((b) => b.classList.toggle('on', b.dataset.tab === tab));
  ['inspector', 'validation', 'production'].forEach((t) => ($(`#tab-${t}`).hidden = t !== tab));
}

async function setMode(mode) {
  S.mode = mode;
  document.querySelectorAll('#mode-seg button').forEach((b) => b.classList.toggle('on', b.dataset.mode === mode));
  $('#legend-2d').style.display = '';
  sheet2d._fitted = false;
  if (mode === 'production') { setTab('production'); setLayout('only-2d'); } else setLayout('split');
  await refreshLayout();
  renderProduction();
}

function setLayout(layout) {
  $('#views').className = `views ${layout === 'split' ? '' : layout}`;
  document.querySelectorAll('#layout-seg button').forEach((b) => b.classList.toggle('on', b.dataset.layout === layout));
  requestAnimationFrame(() => { view3d.resize(); sheet2d._apply(); });
}

async function loadDesigns(preferred) {
  const { designs } = await Api.designs();
  const sel = $('#design-select');
  sel.innerHTML = designs.map((d) => `<option value="${esc(d.id)}">${esc(d.name)} (${d.components} parts)</option>`).join('');
  const url = new URLSearchParams(location.search).get('design');
  S.designId = [preferred, url, 'boat'].find((x) => x && designs.some((d) => d.id === x)) || designs[0]?.id || null;
  sel.value = S.designId || '';
}

document.querySelectorAll('#right-tabs button').forEach((b) => (b.onclick = () => setTab(b.dataset.tab)));
document.querySelectorAll('#mode-seg button').forEach((b) => (b.onclick = () => setMode(b.dataset.mode)));
document.querySelectorAll('#layout-seg button').forEach((b) => (b.onclick = () => setLayout(b.dataset.layout)));
document.querySelectorAll('[data-cam]').forEach((b) => (b.onclick = () => view3d.view(b.dataset.cam)));
$('#btn-fit-3d').onclick = () => view3d.view('iso');
$('#btn-fit-2d').onclick = () => sheet2d.fit();
$('#btn-edges').onclick = (e) => { view3d.setEdges(!view3d.showEdges); e.currentTarget.classList.toggle('on', view3d.showEdges); };
$('#btn-labels-2d').onclick = (e) => { sheet2d.setLabels(!sheet2d.labels); e.currentTarget.classList.toggle('on', sheet2d.labels); };
$('#explode').oninput = (e) => view3d.setExplode(e.target.value / 100);
$('#design-select').onchange = async (e) => {
  S.designId = e.target.value;
  S.selected = null;
  view3d._framed = false;
  sheet2d._fitted = false;
  await refresh().catch(reportError);
};
$('#btn-validate').onclick = async () => {
  await refresh().catch(reportError);
  setTab('validation');
  toast(S.validation?.valid ? 'Validation passed' : `${S.validation?.summary.errors} validation errors`, !S.validation?.valid);
};
$('#btn-reset-boat').onclick = async () => {
  if (!confirm('Rebuild the example boat? This replaces the current "boat" design with a freshly validated build.')) return;
  try {
    const r = await Api.rebuildBoat('boat');
    toast(`Boat rebuilt: ${r.validation.summary.joined} joints validated, ${r.join_failures.length} rejected`);
    await loadDesigns('boat');
    await refresh();
  } catch (e) { reportError(e); }
};
window.addEventListener('keydown', (e) => {
  if (e.target.matches('input, select, textarea')) return;
  if (e.key === 'Escape') select(null);
  if (e.key === 'f') { sheet2d.fit(); view3d.view('iso'); }
  if (e.key === 'v') $('#btn-validate').click();
});

(async () => {
  try {
    await loadDesigns();
    if (!S.designId) { toast('No designs yet — click "Rebuild example" to create the boat.'); return; }
    await refresh();
    // Deep links: ?design=boat&select=MAST&mode=production&explode=40&tab=validation
    const q = new URLSearchParams(location.search);
    if (q.get('mode') === 'production') await setMode('production');
    if (q.get('explode')) { $('#explode').value = q.get('explode'); view3d.setExplode(+q.get('explode') / 100); }
    if (q.get('select')) select(q.get('select'), 'tree');
    if (q.get('tab')) setTab(q.get('tab'));
    window.__studioReady = true;
  } catch (e) { reportError(e); }
})();
