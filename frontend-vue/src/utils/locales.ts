// NOTE: ja / ko / es locale files are currently incomplete (256 keys missing
// vs en.json) which makes the UI render in mixed languages — keys that exist
// only in en fall back to English mid-sentence. Until those locales are fully
// translated we restrict the picker to the two complete locales (en, zh-TW)
// so users never see a half-translated screen. Add the locale back here once
// its messages reach parity with en.json.
export const SUPPORTED_LOCALES = ['en', 'zh-TW'] as const

export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number]

export const DEFAULT_LOCALE: SupportedLocale = 'zh-TW'
export const LOCALE_STORAGE_KEY = 'locale'

export function normalizeLocale(value?: string | null): SupportedLocale {
  const locale = (value || '').trim().replace('_', '-')
  const lowerLocale = locale.toLowerCase()

  if (lowerLocale.startsWith('zh')) return 'zh-TW'
  if (lowerLocale.startsWith('en')) return 'en'
  // ja / ko / es fall back to the default until those locale files are
  // fully translated; see SUPPORTED_LOCALES note above.

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