import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import router from './router'
import App from './App.vue'
import './assets/styles/main.css'
import { getInitialLocale, localeToHtmlLang } from './utils/locales'

// Import locale messages
import en from './locales/en.json'
import zhTW from './locales/zh-TW.json'
import ja from './locales/ja.json'
import ko from './locales/ko.json'
import es from './locales/es.json'

// Create i18n instance. getInitialLocale() honours a ?lang= query param so the
// hreflang alternates we emit for SEO resolve to genuinely different content.
const initialLocale = getInitialLocale()
const i18n = createI18n({
  legacy: false,
  locale: initialLocale,
  fallbackLocale: 'en',
  messages: {
    en,
    'zh-TW': zhTW,
    ja,
    ko,
    es
  }
})

// Reflect the active locale on <html lang> immediately so the first served
// markup matches the chosen language for crawlers; router.afterEach keeps it in
// sync on subsequent navigations.
document.documentElement.setAttribute('lang', localeToHtmlLang(initialLocale))

// Create app
const app = createApp(App)
const pinia = createPinia()

// Use plugins
// Pinia must be installed before the router so navigation guards can safely
// resolve auth/admin state on the first page load.
app.use(pinia)
app.use(router)
app.use(i18n)

// Mount app
app.mount('#app')
