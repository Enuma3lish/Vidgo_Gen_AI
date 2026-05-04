<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { RouterView } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from './components/layout/AppHeader.vue'
import AppFooter from './components/layout/AppFooter.vue'
import Toast from './components/common/Toast.vue'
import { useGeoLanguage } from './composables/useGeoLanguage'
import { useSessionHeartbeat } from './composables/useSessionHeartbeat'
import { useAuthStore } from '@/stores'
import { localeToHtmlLang, persistLocale } from '@/utils/locales'

const { initLanguage } = useGeoLanguage()
const { startHeartbeat } = useSessionHeartbeat()
const { locale } = useI18n()
const authStore = useAuthStore()

watch(locale, (newLocale) => {
  const normalizedLocale = persistLocale(newLocale)
  document.documentElement.lang = localeToHtmlLang(normalizedLocale)
}, { immediate: true })

onMounted(async () => {
  await authStore.init()
  await initLanguage()
  startHeartbeat()
})
</script>

<template>
  <div class="min-h-screen flex flex-col" style="background: var(--bg-page); color: var(--text-primary);">
    <AppHeader />
    <main class="flex-1">
      <RouterView v-slot="{ Component, route: r }">
        <Transition name="page-fade" mode="out-in">
          <component :is="Component" :key="r.fullPath" />
        </Transition>
      </RouterView>
    </main>
    <AppFooter />
    <Toast />
  </div>
</template>
