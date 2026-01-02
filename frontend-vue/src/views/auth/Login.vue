<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore, useUIStore } from '@/stores'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const uiStore = useUIStore()

const email = ref('')
const password = ref('')
const isLoading = ref(false)

async function handleSubmit() {
  if (!email.value || !password.value) {
    uiStore.showError('Please fill in all fields')
    return
  }

  isLoading.value = true
  try {
    await authStore.login({
      email: email.value,
      password: password.value
    })

    uiStore.showSuccess('Login successful!')

    // Redirect to intended page or dashboard
    const redirect = route.query.redirect as string
    router.push(redirect || '/dashboard')
  } catch (error) {
    // Error is already set in store
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
        <!-- Header -->
        <div class="text-center mb-8">
          <RouterLink to="/" class="inline-flex items-center gap-2 mb-6">
            <span class="text-3xl">🎨</span>
            <span class="text-2xl font-bold gradient-text">{{ t('app.name') }}</span>
          </RouterLink>
          <h1 class="text-2xl font-bold text-white mb-2">{{ t('auth.loginTitle') }}</h1>
          <p class="text-gray-400">{{ t('auth.loginSubtitle') }}</p>
        </div>

        <!-- Error Message -->
        <div
          v-if="authStore.error"
          class="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm"
        >
          {{ authStore.error }}
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

          <div>
            <label class="label">{{ t('auth.password') }}</label>
            <input
              v-model="password"
              type="password"
              class="input-field"
              placeholder="••••••••"
              autocomplete="current-password"
            />
          </div>

          <div class="flex items-center justify-between text-sm">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" class="rounded border-dark-600" />
              <span class="text-gray-400">Remember me</span>
            </label>
            <RouterLink to="/auth/forgot-password" class="text-primary-400 hover:text-primary-300">
              {{ t('auth.forgotPassword') }}
            </RouterLink>
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
            <span v-else>{{ t('auth.signIn') }}</span>
          </button>
        </form>

        <!-- Footer -->
        <p class="mt-6 text-center text-gray-400 text-sm">
          {{ t('auth.noAccount') }}
          <RouterLink to="/auth/register" class="text-primary-400 hover:text-primary-300 font-medium">
            {{ t('auth.signUp') }}
          </RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>
