import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import router from './router'
import App from './App.vue'
import './assets/styles/main.css'
import { getStoredLocale } from './utils/locales'

// Import locale messages
import en from './locales/en.json'
import zhTW from './locales/zh-TW.json'
import ja from './locales/ja.json'
import ko from './locales/ko.json'
import es from './locales/es.json'

// Create i18n instance
const i18n = createI18n({
  legacy: false,
  locale: getStoredLocale(),
  fallbackLocale: 'en',
  messages: {
    en,
    'zh-TW': zhTW,
    ja,
    ko,
    es
  }
})

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
