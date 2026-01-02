<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppHeader from './components/layout/AppHeader.vue'
import AppFooter from './components/layout/AppFooter.vue'
import Toast from './components/common/Toast.vue'
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
