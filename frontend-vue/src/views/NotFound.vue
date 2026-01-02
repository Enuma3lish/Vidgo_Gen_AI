<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4">
    <div class="text-center">
      <h1 class="text-8xl font-bold gradient-text mb-4">404</h1>
      <h2 class="text-2xl font-semibold text-white mb-4">Page Not Found</h2>
      <p class="text-gray-400 mb-8">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <RouterLink to="/" class="btn-primary">
        Go Home
      </RouterLink>
    </div>
  </div>
</template>
