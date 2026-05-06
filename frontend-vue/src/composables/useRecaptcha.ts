/**
 * Google reCAPTCHA v3 composable.
 *
 * Backend (`abuse_prevention_service.verify_recaptcha_token`) accepts the token
 * via the `recaptcha_token` field on auth/generation requests. This composable
 * loads the v3 script once, then `execute(action)` returns a fresh token.
 *
 * If `VITE_RECAPTCHA_SITE_KEY` is unset (local dev), `execute` resolves to ''
 * — the backend treats the missing token as "not provided" and only blocks
 * when `RECAPTCHA_REQUIRED=true`.
 */

declare global {
  interface Window {
    grecaptcha?: {
      ready: (cb: () => void) => void
      execute: (siteKey: string, opts: { action: string }) => Promise<string>
    }
  }
}

const SITE_KEY = (import.meta.env.VITE_RECAPTCHA_SITE_KEY || '').trim()

let loaderPromise: Promise<void> | null = null

function loadScript(): Promise<void> {
  if (!SITE_KEY) return Promise.resolve()
  if (loaderPromise) return loaderPromise
  loaderPromise = new Promise<void>((resolve, reject) => {
    if (window.grecaptcha) {
      resolve()
      return
    }
    const script = document.createElement('script')
    script.src = `https://www.google.com/recaptcha/api.js?render=${encodeURIComponent(SITE_KEY)}`
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = () => {
      loaderPromise = null
      reject(new Error('Failed to load reCAPTCHA script'))
    }
    document.head.appendChild(script)
  })
  return loaderPromise
}

export function useRecaptcha() {
  const enabled = !!SITE_KEY

  async function execute(action: string): Promise<string> {
    if (!enabled) return ''
    try {
      await loadScript()
      if (!window.grecaptcha) return ''
      await new Promise<void>((resolve) => window.grecaptcha!.ready(resolve))
      return await window.grecaptcha.execute(SITE_KEY, { action })
    } catch (err) {
      console.warn('[useRecaptcha] execute failed:', err)
      return ''
    }
  }

  return { enabled, execute }
}
