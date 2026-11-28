/**
 * Board API client for the studio. Uses the HttpOnly session cookie issued with the page
 * plus the X-Board-Client header required for cookie-authenticated requests (CSRF guard).
 */
export class ApiError extends Error {
  constructor(status, body) {
    super(body?.error?.message || `HTTP ${status}`);
    this.status = status;
    this.body = body;
    this.issues = body?.error?.issues || [];
  }
}

const failure = (status, message) => new ApiError(status, { error: { message } });

// Every request gives up eventually (the UI must never wait forever); the server's own time budget (90 s) answers first.
async function request(method, path, payload, { timeout = 150000 } = {}) {
  const ctl = timeout ? new AbortController() : null;
  const timer = ctl && setTimeout(() => ctl.abort(), timeout);
  let res;
  try {
    res = await fetch(`/api/v1${path}`, {
      method,
      credentials: 'same-origin',
      headers: { 'X-Board-Client': 'studio', ...(payload ? { 'Content-Type': 'application/json' } : {}) },
      body: payload ? JSON.stringify(payload) : undefined,
      signal: ctl?.signal
    });
  } catch (e) {
    if (e.name === 'AbortError') throw failure(408, `The server did not answer within ${Math.round(timeout / 1000)} s. Please try again.`);
    throw failure(0, 'Cannot reach the server — check your connection.');
  } finally {
    clearTimeout(timer);
  }
  const type = res.headers.get('Content-Type') || '';
  if (!type.includes('application/json')) {
    if ([502, 503, 504].includes(res.status)) throw failure(res.status, 'The server timed out or is restarting (HTTP ' + res.status + '). Please try again in a moment.');
    if (!res.ok) throw new ApiError(res.status, null);
    return res;
  }
  const body = await res.json();
  if (!res.ok || body.ok === false) throw new ApiError(res.status, body);
  return body;
}

const enc = encodeURIComponent;
const qs = (o) => Object.entries(o).filter(([, v]) => v !== '' && v !== undefined && v !== null)
  .map(([k, v]) => `${enc(k)}=${enc(v)}`).join('&');

export const Api = {
  designs: () => request('GET', '/designs'),
  design: (id) => request('GET', `/designs/${enc(id)}`),
  model3d: (id) => request('GET', `/designs/${enc(id)}/model3d`),
  validate: (id) => request('POST', `/designs/${enc(id)}/validate`),
  layout2d: (id, opts = {}) => request('GET', `/designs/${enc(id)}/layout2d?${qs(opts)}`),
  updateComponent: (id, cid, patch, extra = {}) =>
    request('PATCH', `/designs/${enc(id)}/components/${enc(cid)}`, { patch, ...extra }),
  checkJoint: (id, joint) => request('POST', `/designs/${enc(id)}/joints/check`, { joint }),
  join: (id, joint, autoRepair) => request('POST', `/designs/${enc(id)}/joints`, { joint, auto_repair: autoRepair }),
  unjoin: (id, jid) => request('DELETE', `/designs/${enc(id)}/joints/${enc(jid)}`),
  operations: (id, ops, extra = {}) => request('POST', `/designs/${enc(id)}/operations`, { operations: ops, ...extra }),
  applyFix: (id, fixId) => request('POST', `/designs/${enc(id)}/fixes/apply`, { fix_id: fixId }),
  autoFix: (id) => request('POST', `/designs/${enc(id)}/fixes/auto`, {}),
  rebuildBoat: (id) => request('POST', '/designs/examples/boat', { id, overwrite: true }),
  storage: () => request('GET', '/storage'),
  canvasSpec: () => request('GET', '/canvas/spec'),
  canvasPrompt: (opts) => request('POST', '/canvas/prompt', opts),
  canvasExample: (name) => request('GET', `/canvas/examples/${encodeURIComponent(name)}`),
  // large designs take minutes (the server scales its own budget with the number of boards)
  canvasCompile: (source, production = true, extra = {}) => request('POST', '/canvas/compile', { source, production, ...extra }, { timeout: 900000 }),
  canvasFix: (source, fix) => request('POST', '/canvas/fix', { source, fix }),
  canvasRepairPrompt: (source, machine) => request('POST', '/canvas/repair-prompt', { source, machine }, { timeout: 900000 }),
  canvasIntegerFixPrompt: (source) => request('POST', '/canvas/integer-fix-prompt', { source }, { timeout: 120000 }),
  canvasUpdatePrompt: (source, change, extra = {}) => request('POST', '/canvas/update-prompt', { source, change, ...extra }, { timeout: 900000 }),
  canvasAiStatus: () => request('GET', '/canvas/ai-status'),
  canvasAiGenerate: (opts) => request('POST', '/canvas/ai-generate', opts, { timeout: 330000 }),
  canvasAiFix: (source, machine, requirements) => request('POST', '/canvas/ai-fix', { source, machine, requirements }, { timeout: 330000 }),
  canvasResize: (source, size) => request('POST', '/canvas/resize', { source, ...size }),
  canvasTestFit: (thickness, machine, format = 'svg') => request('POST', '/canvas/test-fit', { thickness, machine, format }).then((r) => r.blob()),
  canvasExport: (source, force = false, extra = {}) => request('POST', '/canvas/export', { source, force, ...extra }, { timeout: 900000 }).then((r) => r.blob()),
  canvasSave: (source, name, designId, machine) => request('POST', '/canvas/save', { source, name, design_id: designId || undefined, machine }),
  canvasImport: (source, target, boards) => request('POST', '/canvas/import', { source, target, boards }, { timeout: 900000 }),
  createBoat: (id, name, params) => request('POST', '/designs/examples/boat', { id, params }).then(async (r) => {
    if (name) await request('PATCH', `/designs/${enc(id)}`, { name });
    return r;
  }),
  createBlank: (id, name) => request('POST', '/designs', { id, name }),
  renameDesign: (id, name) => request('PATCH', `/designs/${enc(id)}`, { name }),
  duplicateDesign: (id, newId, name) => request('POST', `/designs/${enc(id)}/duplicate`, { id: newId, name }),
  deleteDesign: (id) => request('DELETE', `/designs/${enc(id)}`),
  exportUrl: (id, fmt, opts) => `/api/v1/designs/${enc(id)}/export/${fmt}?${qs(opts)}`,
  async download(id, fmt, opts) {
    const res = await request('GET', `/designs/${enc(id)}/export/${fmt}?${qs(opts)}`);
    return res.blob();
  },
  async exportText(id, fmt, opts) {
    const res = await request('GET', `/designs/${enc(id)}/export/${fmt}?${qs(opts)}`);
    return res.text();
  }
};
