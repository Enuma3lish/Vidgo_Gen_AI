<script setup lang="ts">
import { ref, computed } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore, useUIStore } from '@/stores'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const uiStore = useUIStore()

const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const isLoading = ref(false)

const passwordMatch = computed(() => password.value === confirmPassword.value)
const passwordStrong = computed(() => password.value.length >= 8)

async function handleSubmit() {
  if (!email.value || !password.value || !confirmPassword.value) {
    uiStore.showError('Please fill in all fields')
    return
  }

  if (!passwordMatch.value) {
    uiStore.showError('Passwords do not match')
    return
  }

  if (!passwordStrong.value) {
    uiStore.showError('Password must be at least 8 characters')
    return
  }

  isLoading.value = true
  try {
    await authStore.register({
      email: email.value,
      password: password.value
    })

    uiStore.showSuccess('Registration successful! Please verify your email.')
    router.push('/auth/verify')
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
          <h1 class="text-2xl font-bold text-white mb-2">{{ t('auth.registerTitle') }}</h1>
          <p class="text-gray-400">{{ t('auth.registerSubtitle') }}</p>
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
              autocomplete="new-password"
            />
            <p
              class="mt-1 text-xs"
              :class="passwordStrong ? 'text-green-400' : 'text-gray-500'"
            >
              Minimum 8 characters
            </p>
          </div>

          <div>
            <label class="label">{{ t('auth.confirmPassword') }}</label>
            <input
              v-model="confirmPassword"
              type="password"
              class="input-field"
              placeholder="••••••••"
              autocomplete="new-password"
            />
            <p
              v-if="confirmPassword && !passwordMatch"
              class="mt-1 text-xs text-red-400"
            >
              Passwords do not match
            </p>
          </div>

          <button
            type="submit"
            :disabled="isLoading || !passwordMatch || !passwordStrong"
            class="btn-primary w-full"
          >
            <span v-if="isLoading" class="flex items-center justify-center gap-2">
              <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              {{ t('common.loading') }}
            </span>
            <span v-else>{{ t('auth.signUp') }}</span>
          </button>
        </form>

        <!-- Footer -->
        <p class="mt-6 text-center text-gray-400 text-sm">
          {{ t('auth.hasAccount') }}
          <RouterLink to="/auth/login" class="text-primary-400 hover:text-primary-300 font-medium">
            {{ t('auth.signIn') }}
          </RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>
