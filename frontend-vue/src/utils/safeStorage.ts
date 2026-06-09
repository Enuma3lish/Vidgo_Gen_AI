/**
 * Safe wrappers around localStorage / sessionStorage.
 *
 * Edge ships with stricter defaults than Chrome: Tracking Prevention (Balanced
 * is the default, Strict is one click away), "Block cookies and site data", and
 * InPrivate mode can all make Web Storage throw. Critically, in these modes the
 * `localStorage` object still EXISTS — so a `typeof localStorage !== 'undefined'`
 * guard passes — but the first `.getItem()/.setItem()` call throws SecurityError.
 *
 * Because tokens, locale, and the router guard read storage during app
 * initialization, an unguarded throw blanks the entire SPA. These helpers
 * degrade gracefully instead: storage simply stops persisting (the user has to
 * log in again per session), but the app still boots and runs.
 */

function read(store: 'local' | 'session', key: string): string | null {
  try {
    const s = store === 'local' ? window.localStorage : window.sessionStorage
    return s.getItem(key)
  } catch {
    return null
  }
}

function write(store: 'local' | 'session', key: string, value: string): void {
  try {
    const s = store === 'local' ? window.localStorage : window.sessionStorage
    s.setItem(key, value)
  } catch {
    /* storage blocked (Edge tracking prevention / private mode) — non-fatal */
  }
}

function drop(store: 'local' | 'session', key: string): void {
  try {
    const s = store === 'local' ? window.localStorage : window.sessionStorage
    s.removeItem(key)
  } catch {
    /* storage blocked — non-fatal */
  }
}

export const safeLocalStorage = {
  getItem: (key: string) => read('local', key),
  setItem: (key: string, value: string) => write('local', key, value),
  removeItem: (key: string) => drop('local', key),
}

export const safeSessionStorage = {
  getItem: (key: string) => read('session', key),
  setItem: (key: string, value: string) => write('session', key, value),
  removeItem: (key: string) => drop('session', key),
}
