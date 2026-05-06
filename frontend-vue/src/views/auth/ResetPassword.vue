<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUIStore } from '@/stores'
import apiClient from '@/api/client'

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()
const uiStore = useUIStore()

const password = ref('')
const passwordConfirm = ref('')
const isLoading = ref(false)
const isComplete = ref(false)
const token = computed(() => String(route.query.token || route.query.reset_password || ''))
const isZh = computed(() => locale.value.startsWith('zh'))

async function handleSubmit() {
  if (!token.value) {
    uiStore.showError(isZh.value ? '重設連結無效或已過期' : 'Reset link is invalid or expired')
    return
  }
  if (password.value.length < 8) {
    uiStore.showError(isZh.value ? '密碼至少需要 8 個字元' : 'Password must be at least 8 characters')
    return
  }
  if (password.value !== passwordConfirm.value) {
    uiStore.showError(isZh.value ? '兩次輸入的密碼不一致' : 'Passwords do not match')
    return
  }

  isLoading.value = true
  try {
    await apiClient.post('/api/v1/auth/reset-password', {
      token: token.value,
      new_password: password.value,
    })
    isComplete.value = true
    setTimeout(() => router.replace('/auth/login'), 1200)
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } }
    uiStore.showError(e.response?.data?.detail || (isZh.value ? '重設密碼失敗' : 'Failed to reset password'))
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-24" style="background: #09090b;">
    <div class="w-full max-w-md">
      <div class="card-gradient">
        <div v-if="isComplete" class="text-center">
          <div class="w-16 h-16 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg class="w-8 h-8 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h1 class="text-2xl font-bold text-white mb-2">{{ isZh ? '密碼已更新' : 'Password Updated' }}</h1>
          <p class="text-gray-400 mb-6">{{ isZh ? '請使用新密碼登入。' : 'You can now sign in with your new password.' }}</p>
          <RouterLink to="/auth/login" class="btn-primary inline-block">{{ t('auth.login') }}</RouterLink>
        </div>

        <template v-else>
          <div class="text-center mb-8">
            <div class="w-16 h-16 bg-primary-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg class="w-8 h-8 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 10-8 0v4h8z" />
              </svg>
            </div>
            <h1 class="text-2xl font-bold text-white mb-2">{{ isZh ? '重設密碼' : 'Reset Password' }}</h1>
            <p class="text-gray-400">{{ isZh ? '請輸入新的帳戶密碼。' : 'Enter a new password for your account.' }}</p>
          </div>

          <form @submit.prevent="handleSubmit" class="space-y-6">
            <div>
              <label class="label">{{ isZh ? '新密碼' : 'New password' }}</label>
              <input v-model="password" type="password" class="input-field" autocomplete="new-password" />
            </div>
            <div>
              <label class="label">{{ isZh ? '確認新密碼' : 'Confirm new password' }}</label>
              <input v-model="passwordConfirm" type="password" class="input-field" autocomplete="new-password" />
            </div>

            <button type="submit" :disabled="isLoading" class="btn-primary w-full">
              <span v-if="isLoading" class="flex items-center justify-center gap-2">
                <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {{ t('common.loading') }}
              </span>
              <span v-else>{{ isZh ? '更新密碼' : 'Update Password' }}</span>
            </button>
          </form>

          <p class="mt-6 text-center">
            <RouterLink to="/auth/login" class="text-gray-400 hover:text-white text-sm">
              {{ isZh ? '返回登入' : 'Back to login' }}
            </RouterLink>
          </p>
        </template>
      </div>
    </div>
  </div>
</template>
