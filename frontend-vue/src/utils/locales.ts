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