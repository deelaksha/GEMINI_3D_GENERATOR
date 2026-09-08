const mockStorage = new Map();
globalThis.localStorage = {
  getItem: (key) => mockStorage.get(key) || null,
  setItem: (key, val) => mockStorage.set(key, String(val)),
  removeItem: (key) => mockStorage.delete(key),
  clear: () => mockStorage.clear()
};
globalThis.window = {
  location: { search: '', href: 'http://localhost:8080/index.html' },
  history: { replaceState: () => {} },
  addEventListener: () => {},
  dispatchEvent: () => {}
};
