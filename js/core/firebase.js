/**
 * Firebase Configuration & Initialization
 * PuzzleCore 3D Physical Construction Workbench
 *
 * Using Firebase CDN-compatible ES module imports via the compat/app bundle
 * so it works seamlessly with the existing vanilla ES module project.
 */

import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js';
import { getAnalytics, logEvent } from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-analytics.js';
import { 
  getFirestore, 
  collection, 
  doc, 
  getDoc, 
  getDocs, 
  setDoc, 
  deleteDoc, 
  query, 
  orderBy, 
  serverTimestamp 
} from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js';

// ============================================================================
// FIREBASE PROJECT CONFIGURATION
// ============================================================================
const firebaseConfig = {
  apiKey:            "AIzaSyAd3K1rM2bn82mNY4rEmu9UySNFKu6xzZA",
  authDomain:        "d-model-c2f16.firebaseapp.com",
  projectId:         "d-model-c2f16",
  storageBucket:     "d-model-c2f16.firebasestorage.app",
  messagingSenderId: "1004441719586",
  appId:             "1:1004441719586:web:ff2f3decedf0543aab4b7b",
  measurementId:     "G-3653Z1F9HE"
};

// ============================================================================
// INITIALIZATION
// ============================================================================

/** Firebase App singleton */
const firebaseApp = initializeApp(firebaseConfig);

/** Firestore Database singleton */
let db = null;
try {
  db = getFirestore(firebaseApp);
  console.log('[Firebase] Firestore initialized — project: d-model-c2f16');
} catch (err) {
  console.warn('[Firebase] Firestore initialization warning:', err.message);
}

/** Analytics instance — only active in browser contexts */
let analytics = null;
try {
  analytics = getAnalytics(firebaseApp);
  console.log('[Firebase] Analytics initialized — project: d-model-c2f16');
} catch (err) {
  console.warn('[Firebase] Analytics not available in this environment:', err.message);
}

// ============================================================================
// EXPORTED UTILITIES
// ============================================================================

/**
 * Log a custom analytics event.
 * @param {string} eventName  - The event name (snake_case recommended).
 * @param {Object} [params]   - Optional event parameters.
 */
export function trackEvent(eventName, params = {}) {
  if (analytics) {
    try {
      logEvent(analytics, eventName, params);
    } catch (e) {
      // ignore
    }
  }
}

export { 
  firebaseApp, 
  db, 
  analytics,
  collection, 
  doc, 
  getDoc, 
  getDocs, 
  setDoc, 
  deleteDoc, 
  query, 
  orderBy, 
  serverTimestamp 
};
export default firebaseApp;

