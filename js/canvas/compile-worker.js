/**
 * Compile worker (module): runs the streaming compile request and all response parsing off the main thread, and
 * turns the compiler's geometry preview into ready-to-draw buffers for the live assembly animation, so the page
 * stays responsive however large the design (and its result JSON) is.
 *
 * in:  {source, production, timeout}
 * out: {type:'progress', stage, done, total, t, ...info} ... {type:'preview', ...buffers}
 *      then {type:'result', result, bytes, previewPending} | {type:'error', status, message}
 *      ({type:'preview-done'} once a preview that was still being built when the result came has been posted)
 * Cancel by terminating the worker: that aborts the request, and the server stops compiling when it notices.
 */
const THREE_URL = 'https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.module.js';   // same release as the page

// Loaded alongside the request (never in its way); the viewport's own shape builder keeps preview and final model identical.
let geometryLib = null;
const loadGeometry = () => (geometryLib ??= import(THREE_URL).then(async (THREE) => {
  globalThis.THREE = THREE;
  const { shapeFromComponent } = await import('../studio/viewport3d.js');
  return { THREE, shapeFromComponent };
}));

/** Merged, world-space buffers for every board (2 draw calls on the page, whatever the board count). */
async function buildPreview(boards) {
  const { THREE, shapeFromComponent } = await loadGeometry();
  const curveSegments = boards.length > 300 ? 4 : boards.length > 80 ? 8 : 16;   // lighter curves for big assemblies
  const parts = [];
  for (const b of boards) {
    try {
      const geo = new THREE.ExtrudeGeometry(shapeFromComponent(b), { depth: b.thickness, bevelEnabled: false, curveSegments });
      geo.translate(0, 0, -b.thickness / 2);
      geo.applyMatrix4(new THREE.Matrix4().fromArray(b.matrix_world));
      const edges = new THREE.EdgesGeometry(geo, 25);
      geo.computeBoundingBox();
      parts.push({ id: b.id, pos: geo.attributes.position.array, nrm: geo.attributes.normal.array,
        line: edges.attributes.position.array, box: geo.boundingBox });
    } catch (e) { /* invalid outline: the board is left out of the preview; the compiler reports the problem */ }
  }
  if (!parts.length) return null;
  const box = new THREE.Box3();
  parts.forEach((p) => box.union(p.box));
  const center = box.getCenter(new THREE.Vector3());
  const radius = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 1);
  const nS = parts.reduce((n, p) => n + p.pos.length / 3, 0), nL = parts.reduce((n, p) => n + p.line.length / 3, 0);
  const out = { pos: new Float32Array(nS * 3), nrm: new Float32Array(nS * 3), dir: new Float32Array(nS * 3),
    lpos: new Float32Array(nL * 3), ldir: new Float32Array(nL * 3), ids: [], solid: [], lines: [] };
  let s = 0, l = 0;
  const d = new THREE.Vector3();
  for (const p of parts) {
    // each board flies in along the line from the assembly centre through its own centre
    p.box.getCenter(d).sub(center);
    if (d.lengthSq() < 1e-6) d.set(0, 1, 0);
    d.normalize().multiplyScalar(radius * 0.55);
    const ns = p.pos.length / 3, nl = p.line.length / 3;
    out.pos.set(p.pos, s * 3); out.nrm.set(p.nrm, s * 3);
    out.lpos.set(p.line, l * 3);
    for (let i = s * 3; i < (s + ns) * 3; i += 3) { out.dir[i] = d.x; out.dir[i + 1] = d.y; out.dir[i + 2] = d.z; }
    for (let i = l * 3; i < (l + nl) * 3; i += 3) { out.ldir[i] = d.x; out.ldir[i + 1] = d.y; out.ldir[i + 2] = d.z; }
    out.ids.push(p.id); out.solid.push([s, ns]); out.lines.push([l, nl]);
    s += ns; l += nl;
  }
  out.bounds = { min: box.min.toArray(), max: box.max.toArray(), center: center.toArray() };
  return out;
}

self.onmessage = async ({ data: { source, production, timeout } }) => {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeout);
  const fail = (status, message) => self.postMessage({ type: 'error', status, message });
  let building = 0;
  loadGeometry().catch(() => { /* no preview without three.js; the compile itself is unaffected */ });
  try {
    const res = await fetch('/api/v1/canvas/compile-stream', {
      method: 'POST', credentials: 'same-origin', signal: ctl.signal,
      headers: { 'X-Board-Client': 'studio', 'Content-Type': 'application/json' },
      body: JSON.stringify({ source, production })
    });
    if (!res.ok) {
      let message = `The compiler answered HTTP ${res.status}.`;
      try { message = (await res.json()).error?.message || message; } catch (e) { /* not JSON */ }
      if ([502, 503, 504].includes(res.status)) message = `The server timed out or is restarting (HTTP ${res.status}). Please try again in a moment.`;
      return fail(res.status, message);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '', bytes = 0, done = false;
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      bytes += chunk.value.length;
      buf += decoder.decode(chunk.value, { stream: true });
      let nl;
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl);
        buf = buf.slice(nl + 1);
        if (!line) continue;
        const ev = JSON.parse(line);
        if (ev.type === 'progress') {
          if (ev.preview) {
            // built in the background: the stream (and so the compile result) never waits for the animation
            building++;
            buildPreview(ev.preview).then((p) => p && self.postMessage({ type: 'preview', ...p },
              [p.pos.buffer, p.nrm.buffer, p.dir.buffer, p.lpos.buffer, p.ldir.buffer])).catch(() => {})
              .finally(() => { if (!--building) self.postMessage({ type: 'preview-done' }); });
            delete ev.preview;
          }
          self.postMessage(ev);
        } else if (ev.type === 'result') {
          self.postMessage({ type: 'result', result: ev.result, bytes, t: ev.t, previewPending: building > 0 });
          done = true;
        }
        else if (ev.type === 'error') return fail(500, ev.message);
      }
    }
    if (!done) fail(0, 'The connection to the compiler was lost before it finished. Please try again.');
  } catch (e) {
    if (e.name === 'AbortError') fail(408, `The compiler did not finish within ${Math.round(timeout / 1000)} s. Please try again.`);
    else if (e instanceof SyntaxError) fail(0, 'The compiler sent an unreadable reply. Please try again.');
    else fail(0, 'Cannot reach the server — check your connection.');
  } finally {
    clearTimeout(timer);
  }
};
