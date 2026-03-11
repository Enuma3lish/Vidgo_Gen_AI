<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import AppHeader from './components/layout/AppHeader.vue'
import AppFooter from './components/layout/AppFooter.vue'
import Toast from './components/common/Toast.vue'
import { useGeoLanguage } from './composables/useGeoLanguage'
import { useAuthStore } from '@/stores'

const { initLanguage } = useGeoLanguage()
const authStore = useAuthStore()
onMounted(async () => {
  await authStore.init()
  await initLanguage()
})
</script>

<template>
  <div class="min-h-screen flex flex-col bg-white">
    <AppHeader />
    <main class="flex-1">
      <RouterView />
    </main>
    <AppFooter />
    <Toast />
  </div>
</template>
