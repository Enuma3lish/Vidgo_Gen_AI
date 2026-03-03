<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter, useRoute } from 'vue-router'
// useI18n not needed
import { useAuthStore } from '@/stores'
import { useUIStore } from '@/stores'

// const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const uiStore = useUIStore()

const email = ref('')
const password = ref('')
const isLoading = ref(false)
const showPassword = ref(false)

async function handleSubmit() {
  if (!email.value || !password.value) {
    uiStore.showError('請填寫所有欄位')
    return
  }
  isLoading.value = true
  try {
    await authStore.login({ email: email.value, password: password.value })
    const redirect = route.query.redirect as string
    router.push(redirect || '/dashboard')
  } catch (error) {
    // Error handled in store
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-24" style="background: linear-gradient(160deg, #e8ffb3 0%, #f0ffe0 40%, #fffde0 100%);">
    <div class="w-full max-w-md">
      <div class="bg-white rounded-3xl p-8 md:p-10" style="box-shadow: 0 8px 40px rgba(0,0,0,0.12);">
        <!-- Logo -->
        <div class="text-center mb-8">
          <RouterLink to="/" class="inline-flex items-center gap-2 mb-6">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center font-black text-white text-base" style="background: #111111;">V</div>
            <span class="text-xl font-black text-dark-900">VidGo AI</span>
          </RouterLink>
          <h1 class="text-2xl font-bold text-dark-900 mb-2">歡迎回來</h1>
          <p class="text-dark-500 text-sm">登入您的帳號繼續創作</p>
        </div>

        <!-- Free Credits Banner -->
        <div class="mb-6 p-3 rounded-2xl flex items-center gap-3" style="background: #d4f06b;">
          <span class="text-xl">🎁</span>
          <div>
            <div class="font-semibold text-dark-900 text-sm">新用戶免費獲得 40 點</div>
            <div class="text-dark-600 text-xs">立即體驗所有 AI 工具</div>
          </div>
        </div>

        <!-- Error -->
        <div v-if="authStore.error" class="mb-4 p-3 rounded-xl text-sm" style="background: rgba(239,68,68,0.1); color: #ef4444; border: 1px solid rgba(239,68,68,0.2);">
          {{ authStore.error }}
        </div>

        <!-- Form -->
        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label class="form-label">電子郵件</label>
            <input v-model="email" type="email" class="form-input" placeholder="you@example.com" autocomplete="email"/>
          </div>
          <div>
            <div class="flex items-center justify-between mb-1.5">
              <label class="form-label mb-0">密碼</label>
              <RouterLink to="/auth/forgot-password" class="text-xs text-dark-500 hover:text-dark-900 transition-colors">忘記密碼？</RouterLink>
            </div>
            <div class="relative">
              <input v-model="password" :type="showPassword ? 'text' : 'password'" class="form-input pr-10" placeholder="••••••••" autocomplete="current-password"/>
              <button type="button" @click="showPassword = !showPassword" class="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-dark-700">
                <svg v-if="!showPassword" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
                <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/></svg>
              </button>
            </div>
          </div>
          <button type="submit" :disabled="isLoading" class="w-full py-3.5 rounded-full font-bold text-white transition-all duration-200 flex items-center justify-center gap-2" style="background: #111111; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
            <svg v-if="isLoading" class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
            <span>{{ isLoading ? '登入中...' : '登入' }}</span>
          </button>
        </form>

        <!-- Divider -->
        <div class="flex items-center gap-3 my-6">
          <div class="flex-1 h-px" style="background: rgba(0,0,0,0.08);"></div>
          <span class="text-xs text-dark-400">還沒有帳號？</span>
          <div class="flex-1 h-px" style="background: rgba(0,0,0,0.08);"></div>
        </div>

        <RouterLink to="/auth/register" class="block w-full py-3.5 rounded-full font-semibold text-dark-900 text-center transition-all duration-200 border-2 border-dark-200 hover:border-dark-900">
          免費註冊 — 獲得 40 點
        </RouterLink>
      </div>
    </div>
  </div>
</template>
