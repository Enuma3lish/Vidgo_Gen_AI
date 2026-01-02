<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUIStore } from '@/stores'

const { t } = useI18n()
const uiStore = useUIStore()

const email = ref('')
const isLoading = ref(false)
const isSubmitted = ref(false)

async function handleSubmit() {
  if (!email.value) {
    uiStore.showError('Please enter your email')
    return
  }

  isLoading.value = true
  try {
    // API call would go here
    await new Promise(resolve => setTimeout(resolve, 1000))
    isSubmitted.value = true
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-24">
    <div class="w-full max-w-md">
      <!-- Card -->
      <div class="card-gradient">
        <!-- Success State -->
        <div v-if="isSubmitted" class="text-center">
          <div class="w-16 h-16 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg class="w-8 h-8 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h1 class="text-2xl font-bold text-white mb-2">Check Your Email</h1>
          <p class="text-gray-400 mb-6">
            We've sent password reset instructions to<br />
            <span class="text-white font-medium">{{ email }}</span>
          </p>
          <RouterLink to="/auth/login" class="btn-primary inline-block">
            Back to Login
          </RouterLink>
        </div>

        <!-- Form State -->
        <template v-else>
          <!-- Header -->
          <div class="text-center mb-8">
            <div class="w-16 h-16 bg-primary-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg class="w-8 h-8 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
              </svg>
            </div>
            <h1 class="text-2xl font-bold text-white mb-2">{{ t('auth.forgotPassword') }}</h1>
            <p class="text-gray-400">
              Enter your email address and we'll send you instructions to reset your password.
            </p>
          </div>

          <!-- Form -->
          <form @submit.prevent="handleSubmit" class="space-y-6">
            <div>
              <label class="label">{{ t('auth.email') }}</label>
              <input
                v-model="email"
                type="email"
                class="input-field"
                placeholder="you@example.com"
                autocomplete="email"
              />
            </div>

            <button
              type="submit"
              :disabled="isLoading"
              class="btn-primary w-full"
            >
              <span v-if="isLoading" class="flex items-center justify-center gap-2">
                <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {{ t('common.loading') }}
              </span>
              <span v-else>Send Reset Instructions</span>
            </button>
          </form>

          <!-- Back to Login -->
          <p class="mt-6 text-center">
            <RouterLink to="/auth/login" class="text-gray-400 hover:text-white text-sm">
              ← Back to login
            </RouterLink>
          </p>
        </template>
      </div>
    </div>
  </div>
</template>
