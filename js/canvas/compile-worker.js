/**
 * Compile worker: runs the streaming compile request and all response parsing off the main thread, so the
 * loading animation and the editor stay responsive however large the design (and its result JSON) is.
 *
 * in:  {source, production, timeout}
 * out: {type:'progress', stage, done, total, t} ... then {type:'result', result, bytes} | {type:'error', status, message}
 * Cancel by terminating the worker: that aborts the request, and the server stops compiling when it notices.
 */
self.onmessage = async ({ data: { source, production, timeout } }) => {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeout);
  const fail = (status, message) => self.postMessage({ type: 'error', status, message });
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
        if (ev.type === 'progress') self.postMessage(ev);
        else if (ev.type === 'result') { self.postMessage({ type: 'result', result: ev.result, bytes, t: ev.t }); done = true; }
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
