<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from './components/layout/AppHeader.vue'
import AppFooter from './components/layout/AppFooter.vue'
import Toast from './components/common/Toast.vue'
import { useGeoLanguage } from './composables/useGeoLanguage'
import { useSessionHeartbeat } from './composables/useSessionHeartbeat'
import { useAuthStore, useBrandingStore } from '@/stores'
import { localeToHtmlLang, persistLocale } from '@/utils/locales'

const { initLanguage } = useGeoLanguage()
const { startHeartbeat } = useSessionHeartbeat()
const { locale } = useI18n()
const authStore = useAuthStore()
const brandingStore = useBrandingStore()
const route = useRoute()

// /admin/* uses its own persistent shell (AdminLayout with sidebar +
// status strip), so we hide the consumer AppHeader / AppFooter there to
// avoid stacking two top bars on admin pages.
const isAdminRoute = computed(() => route.path.startsWith('/admin'))

watch(locale, (newLocale) => {
  const normalizedLocale = persistLocale(newLocale)
  document.documentElement.lang = localeToHtmlLang(normalizedLocale)
  // Safety net (perf audit #4): if some other code path switched to a lazy
  // locale without pre-loading it, fetch its messages now. Worst case is a
  // brief flash of the fallback before this resolves — the primary switch
  // paths (LanguageSelector, geo-init) already await the load, so this only
  // covers rare edge routes.
  void import('@/main').then((m) => m.ensureLocaleMessages(normalizedLocale))
}, { immediate: true })

onMounted(() => {
  // Parallelize independent boot work (perf audit #6). initLanguage (geo/
  // locale) and branding.fetch (header logo) don't depend on auth, so they no
  // longer wait behind auth.init()'s getMe → getBalance chain. All three
  // tolerate failure independently.
  void initLanguage()
  brandingStore.fetch().catch(() => undefined)
  void authStore.init()
  startHeartbeat()
})
</script>

<template>
  <div class="min-h-screen flex flex-col" style="background: var(--bg-page); color: var(--text-primary);">
    <AppHeader v-if="!isAdminRoute" />
    <main class="flex-1">
      <RouterView v-slot="{ Component, route: r }">
        <Transition name="page-fade" mode="out-in">
          <component :is="Component" :key="r.fullPath" />
        </Transition>
      </RouterView>
    </main>
    <AppFooter v-if="!isAdminRoute" />
    <Toast />
  </div>
</template>
