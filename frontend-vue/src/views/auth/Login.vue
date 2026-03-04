<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores'
import { useUIStore } from '@/stores'

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
  <div class="min-h-screen flex items-center justify-center px-4 py-24"
    style="background: linear-gradient(160deg, #020817 0%, #0a1628 50%, #0f1f3d 100%);">
    <!-- Background glow -->
    <div style="position: fixed; top: 30%; left: 50%; transform: translate(-50%,-50%); width: 500px; height: 300px; background: radial-gradient(ellipse, rgba(0,184,230,0.08) 0%, transparent 70%); pointer-events: none; z-index: 0;"></div>
    <div class="w-full max-w-md relative z-10">
      <div class="rounded-3xl p-8 md:p-10"
        style="background: #0f1f3d; border: 1px solid rgba(0,184,230,0.2); box-shadow: 0 8px 40px rgba(0,0,0,0.4), 0 0 80px rgba(0,184,230,0.05);">
        <!-- Logo -->
        <div class="text-center mb-8">
          <RouterLink to="/" class="inline-flex items-center gap-2 mb-6">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center font-black text-white text-base"
              style="background: linear-gradient(135deg, #00b8e6, #0077a8); box-shadow: 0 0 15px rgba(0,184,230,0.4);">V</div>
            <span class="text-xl font-black" style="color: #e8f4ff;">VidGo <span style="color: #00b8e6;">AI</span></span>
          </RouterLink>
          <h1 class="text-2xl font-bold mb-2" style="color: #e8f4ff;">歡迎回來</h1>
          <p class="text-sm" style="color: #6b9ab8;">登入您的帳號繼續創作</p>
        </div>

        <!-- Free Credits Banner -->
        <div class="mb-6 p-3 rounded-2xl flex items-center gap-3"
          style="background: rgba(0,184,230,0.1); border: 1px solid rgba(0,184,230,0.25);">
          <span class="text-xl">🎁</span>
          <div>
            <div class="font-semibold text-sm" style="color: #00b8e6;">新用戶免費獲得 40 點</div>
            <div class="text-xs" style="color: #6b9ab8;">立即體驗所有 AI 工具</div>
          </div>
        </div>

        <!-- Error -->
        <div v-if="authStore.error" class="mb-4 p-3 rounded-xl text-sm"
          style="background: rgba(239,68,68,0.1); color: #ef4444; border: 1px solid rgba(239,68,68,0.2);">
          {{ authStore.error }}
        </div>

        <!-- Form -->
        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label class="block text-sm font-medium mb-1.5" style="color: #a8c8e8;">電子郵件</label>
            <input v-model="email" type="email"
              class="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
              style="background: rgba(0,184,230,0.05); border: 1px solid rgba(0,184,230,0.2); color: #e8f4ff;"
              placeholder="you@example.com" autocomplete="email"
              onfocus="this.style.borderColor='rgba(0,184,230,0.6)';this.style.boxShadow='0 0 0 3px rgba(0,184,230,0.1)'"
              onblur="this.style.borderColor='rgba(0,184,230,0.2)';this.style.boxShadow=''"/>
          </div>
          <div>
            <div class="flex items-center justify-between mb-1.5">
              <label class="block text-sm font-medium" style="color: #a8c8e8;">密碼</label>
              <RouterLink to="/auth/forgot-password" class="text-xs transition-colors" style="color: #6b9ab8;"
                onmouseover="this.style.color='#00b8e6'" onmouseout="this.style.color='#6b9ab8'">忘記密碼？</RouterLink>
            </div>
            <div class="relative">
              <input v-model="password" :type="showPassword ? 'text' : 'password'"
                class="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all pr-10"
                style="background: rgba(0,184,230,0.05); border: 1px solid rgba(0,184,230,0.2); color: #e8f4ff;"
                placeholder="••••••••" autocomplete="current-password"
                onfocus="this.style.borderColor='rgba(0,184,230,0.6)';this.style.boxShadow='0 0 0 3px rgba(0,184,230,0.1)'"
                onblur="this.style.borderColor='rgba(0,184,230,0.2)';this.style.boxShadow=''"/>
              <button type="button" @click="showPassword = !showPassword"
                class="absolute right-3 top-1/2 -translate-y-1/2 transition-colors" style="color: #6b9ab8;">
                <svg v-if="!showPassword" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
                <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/></svg>
              </button>
            </div>
          </div>
          <button type="submit" :disabled="isLoading"
            class="w-full py-3.5 rounded-full font-bold text-white transition-all duration-200 flex items-center justify-center gap-2"
            style="background: linear-gradient(135deg, #00b8e6, #0077a8); box-shadow: 0 4px 20px rgba(0,184,230,0.35);">
            <svg v-if="isLoading" class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
            <span>{{ isLoading ? '登入中...' : '登入' }}</span>
          </button>
        </form>

        <!-- Divider -->
        <div class="flex items-center gap-3 my-6">
          <div class="flex-1 h-px" style="background: rgba(0,184,230,0.15);"></div>
          <span class="text-xs" style="color: #4a7bb5;">還沒有帳號？</span>
          <div class="flex-1 h-px" style="background: rgba(0,184,230,0.15);"></div>
        </div>

        <RouterLink to="/auth/register"
          class="block w-full py-3.5 rounded-full font-semibold text-center transition-all duration-200"
          style="color: #00b8e6; border: 2px solid rgba(0,184,230,0.35); background: transparent;"
          onmouseover="this.style.background='rgba(0,184,230,0.08)';this.style.borderColor='rgba(0,184,230,0.7)'"
          onmouseout="this.style.background='transparent';this.style.borderColor='rgba(0,184,230,0.35)'">
          免費註冊 — 獲得 40 點
        </RouterLink>
      </div>
    </div>
  </div>
</template>
