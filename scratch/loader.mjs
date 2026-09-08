const mockStorage = new Map();
if (!globalThis.localStorage) {
  globalThis.localStorage = {
    getItem: (key) => mockStorage.get(key) || null,
    setItem: (key, val) => mockStorage.set(key, String(val)),
    removeItem: (key) => mockStorage.delete(key),
    clear: () => mockStorage.clear()
  };
}
if (!globalThis.window) {
  globalThis.window = {
    location: { search: '', href: 'http://localhost:8080/index.html' },
    history: { replaceState: () => {} },
    addEventListener: () => {},
    dispatchEvent: () => {}
  };
}

export async function load(url, context, nextLoad) {
  if (url.startsWith('https:')) {
    return {
      format: 'module',
      shortCircuit: true,
      source: `
        export function initializeApp() { return {}; }
        export function getFirestore() { return null; }
        export function getAnalytics() { return null; }
        export function logEvent() {}
        export function collection() {}
        export function doc() {}
        export function getDoc() { return Promise.resolve({ exists: () => false }); }
        export function getDocs() { return Promise.resolve([]); }
        export function setDoc() { return Promise.resolve(); }
        export function deleteDoc() { return Promise.resolve(); }
        export function query() {}
        export function orderBy() {}
        export function serverTimestamp() { return new Date(); }
      `
    };
  }
  return nextLoad(url, context);
}
