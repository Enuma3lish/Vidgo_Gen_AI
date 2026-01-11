<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import AppHeader from './components/layout/AppHeader.vue'
import AppFooter from './components/layout/AppFooter.vue'
import Toast from './components/common/Toast.vue'
import { useGeoLanguage } from './composables/useGeoLanguage'

// Initialize geo-based language detection
const { initLanguage } = useGeoLanguage()

onMounted(async () => {
  // Detect and set language based on user's IP location
  // Only runs once per device, result is cached in localStorage
  await initLanguage()
})
</script>

<template>
  <div class="min-h-screen flex flex-col bg-gradient-dark">
    <AppHeader />
    <main class="flex-1">
      <RouterView />
    </main>
    <AppFooter />
    <Toast />
  </div>
</template>
