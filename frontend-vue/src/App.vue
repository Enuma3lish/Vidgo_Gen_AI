<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from './components/layout/AppHeader.vue'
import AppFooter from './components/layout/AppFooter.vue'
import Toast from './components/common/Toast.vue'
import { useGeoLanguage } from './composables/useGeoLanguage'
import { useSessionHeartbeat } from './composables/useSessionHeartbeat'
import { useAuthStore, useUIStore } from '@/stores'

const { initLanguage } = useGeoLanguage()
const { startHeartbeat } = useSessionHeartbeat()
const { locale } = useI18n()
const authStore = useAuthStore()
const uiStore = useUIStore()
const route = useRoute()
const isAdminSurface = computed(() => route.path.startsWith('/admin') || route.path.startsWith('/dashboard'))

function enforceAdminLocale() {
  if (authStore.isAdmin && isAdminSurface.value) {
    locale.value = 'zh-TW'
    uiStore.setLocale('zh-TW')
  }
}

watch(() => authStore.isAdmin, enforceAdminLocale)
watch(() => route.path, enforceAdminLocale)

onMounted(async () => {
  await authStore.init()
  await initLanguage()
  enforceAdminLocale()
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
