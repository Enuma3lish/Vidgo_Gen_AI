import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import router from './router'
import App from './App.vue'
import './assets/styles/main.css'
import { getInitialLocale, localeToHtmlLang } from './utils/locales'

// Locale bundles (2026-07-12 perf audit #4). Previously ALL 5 locales were
// statically imported into the entry chunk (~427KB raw / ~110KB gz) though
// only one is ever active. Now only the two primary locales are eager —
// en (the fallbackLocale, needed for missing-key resolution) and zh-TW (the
// primary audience) — so there's zero flash-of-fallback for ~99% of users.
// ja/ko/es load on demand via ensureLocaleMessages().
import en from './locales/en.json'
import zhTW from './locales/zh-TW.json'

// Lazy loaders for every locale (Vite emits one chunk each). Used to fetch a
// non-eager locale before we switch to it.
const localeLoaders = import.meta.glob('./locales/*.json')

const i18n = createI18n({
  legacy: false,
  locale: 'en',            // set correctly below once messages are ready
  fallbackLocale: 'en',
  messages: {
    en,
    'zh-TW': zhTW,
  },
})

/**
 * Ensure a locale's messages are loaded, then (optionally) activate it.
 * Idempotent — eager/already-loaded locales resolve instantly. Callers that
 * switch language (LanguageSelector, geo-detection) should await this BEFORE
 * setting the active locale so there's no flash of the fallback language.
 */
export async function ensureLocaleMessages(locale: string): Promise<void> {
  // Cast around vue-i18n's strict message-schema types: at runtime any of the
  // 5 locales is valid, but the type union is narrowed to the eager set.
  if ((i18n.global.availableLocales as string[]).includes(locale)) return
  const loader = localeLoaders[`./locales/${locale}.json`]
  if (!loader) return
  try {
    const mod = (await loader()) as { default: Record<string, unknown> }
    i18n.global.setLocaleMessage(locale as 'en', mod.default as never)
  } catch {
    /* keep fallbackLocale — a failed locale chunk must not break the app */
  }
}

async function bootstrap() {
  // getInitialLocale() honours a ?lang= query param so hreflang alternates
  // resolve to genuinely different content. If it resolves to a lazy locale
  // (ja/ko/es via ?lang= or stored preference), fetch it BEFORE mount so the
  // first paint is already in the right language.
  const initialLocale = getInitialLocale()
  await ensureLocaleMessages(initialLocale)
  ;(i18n.global.locale as unknown as { value: string }).value = initialLocale

  // Reflect the active locale on <html lang> immediately so the first served
  // markup matches for crawlers; router.afterEach keeps it in sync after.
  document.documentElement.setAttribute('lang', localeToHtmlLang(initialLocale))

  const app = createApp(App)
  const pinia = createPinia()
  // Pinia before the router so navigation guards can resolve auth/admin state
  // on the first page load.
  app.use(pinia)
  app.use(router)
  app.use(i18n)
  app.mount('#app')
}

void bootstrap()
