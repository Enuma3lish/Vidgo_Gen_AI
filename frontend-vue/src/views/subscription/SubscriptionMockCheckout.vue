<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const router = useRouter()

onMounted(() => {
  // In mock mode, subscription is already activated by backend; redirect after short delay
  const timer = setTimeout(() => {
    router.replace('/dashboard')
  }, 2500)
  return () => clearTimeout(timer)
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-24 bg-dark-900">
    <div class="max-w-md w-full text-center card p-8">
      <div class="w-16 h-16 bg-primary-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
        <svg class="w-8 h-8 text-primary-400 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
      <h1 class="text-2xl font-bold text-white mb-2">
        {{ t('subscription.mockComplete', 'Demo payment complete') }}
      </h1>
      <p class="text-gray-400 mb-6">
        {{ t('subscription.redirecting', 'Redirecting to dashboard...') }}
      </p>
      <button
        type="button"
        class="text-primary-400 hover:text-primary-300 text-sm"
        @click="router.replace('/dashboard')"
      >
        {{ t('subscription.goNow', 'Go now') }}
      </button>
    </div>
  </div>
</template>
