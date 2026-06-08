// All five locale files are at parity with en.json (1016 keys each as of
// 2026-05-11). The 246 ja/ko/es keys that previously fell back to English
// were patched via /tmp/patch_locales.py. If a future en-only key is added
// without a matching ja/ko/es value, vue-i18n's missingHandler will fall
// back to en — but that should be the exception, not the steady state.
export const SUPPORTED_LOCALES = ['en', 'zh-TW', 'ja', 'ko', 'es'] as const

export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number]

export const DEFAULT_LOCALE: SupportedLocale = 'zh-TW'
export const LOCALE_STORAGE_KEY = 'locale'

export function normalizeLocale(value?: string | null): SupportedLocale {
  const locale = (value || '').trim().replace('_', '-')
  const lowerLocale = locale.toLowerCase()

  if (lowerLocale.startsWith('zh')) return 'zh-TW'
  if (lowerLocale.startsWith('en')) return 'en'
  if (lowerLocale.startsWith('ja')) return 'ja'
  if (lowerLocale.startsWith('ko')) return 'ko'
  if (lowerLocale.startsWith('es')) return 'es'

  return DEFAULT_LOCALE
}

export function getStoredLocale(): SupportedLocale {
  if (typeof localStorage === 'undefined') return DEFAULT_LOCALE
  return normalizeLocale(localStorage.getItem(LOCALE_STORAGE_KEY))
}

/**
 * Locale to boot the app with. A `?lang=` query param wins (and is persisted)
 * so the hreflang alternates emitted for SEO — `…?lang=ja`, `…?lang=ko`, etc. —
 * resolve to genuinely different content for crawlers and shared links. Falls
 * back to the user's stored choice, then DEFAULT_LOCALE. Unknown `lang` values
 * are ignored rather than forced to the default, so a stray param can't wipe a
 * returning user's saved language.
 */
export function getInitialLocale(): SupportedLocale {
  if (typeof window !== 'undefined') {
    const param = (new URLSearchParams(window.location.search).get('lang') || '').trim().toLowerCase()
    if (param && SUPPORTED_LOCALES.some((code) => param.startsWith(code.split('-')[0]))) {
      return persistLocale(param)
    }
  }
  return getStoredLocale()
}

export function persistLocale(locale: string): SupportedLocale {
  const normalizedLocale = normalizeLocale(locale)
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(LOCALE_STORAGE_KEY, normalizedLocale)
  }
  return normalizedLocale
}

export function localeToHtmlLang(locale: string): string {
  const normalizedLocale = normalizeLocale(locale)
  return normalizedLocale === 'zh-TW' ? 'zh-Hant-TW' : normalizedLocale
}