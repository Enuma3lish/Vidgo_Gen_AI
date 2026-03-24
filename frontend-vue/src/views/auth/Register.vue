<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores'
import { useUIStore } from '@/stores'

const { t } = useI18n()
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
    uiStore.showError(t('auth.fillAllFields'))
    return
  }
  isLoading.value = true
  try {
    const referralCode = (route.query.ref as string) || undefined
    await authStore.register({ email: email.value, password: password.value, referral_code: referralCode })
    router.push({ path: '/auth/verify', query: { email: email.value } })
  } catch (error) {
    // Error handled in store
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex" style="background: #09090b;">
    <!-- Left: Branding panel (hidden on mobile) -->
    <div class="hidden lg:flex lg:w-5/12 xl:w-1/2 flex-col justify-center px-12 xl:px-20 relative overflow-hidden"
      style="background: linear-gradient(160deg, rgba(22,119,255,0.15) 0%, rgba(114,46,209,0.15) 100%), #0f0f17;">
      <div class="relative z-10">
        <RouterLink to="/" class="inline-flex items-center gap-2 mb-12">
          <div class="w-9 h-9 rounded-lg flex items-center justify-center font-black text-white text-sm"
            style="background: linear-gradient(135deg, #1677ff, #0958d9);">V</div>
          <span class="text-xl font-black" style="color: #f5f5fa;">VidGo <span style="color: #1677ff;">AI</span></span>
        </RouterLink>

        <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold mb-6"
          style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);">
          🎁 {{ t('auth.freeCreditsTitle') }}
        </div>

        <h2 class="text-3xl xl:text-4xl font-black mb-4 leading-tight" style="color: #f5f5fa;">
          {{ t('auth.registerBrandingTitle') }}
        </h2>
        <p class="text-base mb-10 leading-relaxed" style="color: #9494b0;">
          {{ t('auth.registerBrandingDesc') }}
        </p>

        <div class="space-y-3">
          <div class="flex items-center gap-2.5">
            <div class="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0" style="background: rgba(16,185,129,0.15);">
              <svg class="w-3 h-3" style="color: #10b981;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>
            </div>
            <span class="text-sm" style="color: #9494b0;">{{ t('auth.perk1') }}</span>
          </div>
          <div class="flex items-center gap-2.5">
            <div class="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0" style="background: rgba(16,185,129,0.15);">
              <svg class="w-3 h-3" style="color: #10b981;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>
            </div>
            <span class="text-sm" style="color: #9494b0;">{{ t('auth.perk2') }}</span>
          </div>
          <div class="flex items-center gap-2.5">
            <div class="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0" style="background: rgba(16,185,129,0.15);">
              <svg class="w-3 h-3" style="color: #10b981;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>
            </div>
            <span class="text-sm" style="color: #9494b0;">{{ t('auth.perk3') }}</span>
          </div>
          <div class="flex items-center gap-2.5">
            <div class="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0" style="background: rgba(16,185,129,0.15);">
              <svg class="w-3 h-3" style="color: #10b981;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>
            </div>
            <span class="text-sm" style="color: #9494b0;">{{ t('auth.perk4') }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Right: Form -->
    <div class="flex-1 flex items-center justify-center px-4 py-16 sm:px-8">
      <div class="w-full max-w-md">
        <!-- Mobile logo -->
        <div class="lg:hidden text-center mb-8">
          <RouterLink to="/" class="inline-flex items-center gap-2">
            <div class="w-9 h-9 rounded-lg flex items-center justify-center font-black text-white text-sm"
              style="background: linear-gradient(135deg, #1677ff, #0958d9);">V</div>
            <span class="text-xl font-black" style="color: #f5f5fa;">VidGo <span style="color: #1677ff;">AI</span></span>
          </RouterLink>
        </div>

        <div class="rounded-2xl p-8 md:p-10" style="background: #141420; box-shadow: 0 4px 24px rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.06);">
          <h1 class="text-2xl font-bold mb-1" style="color: #f5f5fa;">{{ t('auth.registerTitle') }}</h1>
          <p class="text-sm mb-6" style="color: #6b6b8a;">{{ t('auth.registerSubtitle2') }}</p>

          <!-- Error -->
          <div v-if="authStore.error" class="mb-4 p-3 rounded-lg text-sm"
            style="background: rgba(255,77,79,0.06); color: #ff4d4f; border: 1px solid rgba(255,77,79,0.2);">
            {{ authStore.error }}
          </div>

          <!-- Form -->
          <form @submit.prevent="handleSubmit" class="space-y-4">
            <div>
              <label class="block text-sm font-medium mb-1.5" style="color: #f5f5fa;">{{ t('auth.email') }}</label>
              <input v-model="email" type="email"
                class="w-full px-4 py-3 rounded-lg text-sm outline-none transition-all"
                style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #f5f5fa;"
                placeholder="you@example.com" autocomplete="email"
                onfocus="this.style.borderColor='#1677ff';this.style.boxShadow='0 0 0 3px rgba(22,119,255,0.1)'"
                onblur="this.style.borderColor='rgba(255,255,255,0.08)';this.style.boxShadow=''"/>
            </div>
            <div>
              <label class="block text-sm font-medium mb-1.5" style="color: #f5f5fa;">{{ t('auth.setPassword') }}</label>
              <div class="relative">
                <input v-model="password" :type="showPassword ? 'text' : 'password'"
                  class="w-full px-4 py-3 rounded-lg text-sm outline-none transition-all pr-10"
                  style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #f5f5fa;"
                  placeholder="••••••••" autocomplete="new-password"
                  onfocus="this.style.borderColor='#1677ff';this.style.boxShadow='0 0 0 3px rgba(22,119,255,0.1)'"
                  onblur="this.style.borderColor='rgba(255,255,255,0.08)';this.style.boxShadow=''"/>
                <button type="button" @click="showPassword = !showPassword"
                  class="absolute right-3 top-1/2 -translate-y-1/2 transition-colors" style="color: rgba(255,255,255,0.35);">
                  <svg v-if="!showPassword" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
                  <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/></svg>
                </button>
              </div>
            </div>
            <button type="submit" :disabled="isLoading"
              class="w-full py-3.5 rounded font-bold text-white transition-all duration-200 flex items-center justify-center gap-2"
              style="background: #1677ff; box-shadow: 0 2px 0 rgba(5,145,255,0.1);"
              onmouseover="if(!this.disabled)this.style.opacity='0.9'"
              onmouseout="this.style.opacity='1'">
              <svg v-if="isLoading" class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
              <span>{{ isLoading ? t('auth.signingUp') : t('auth.registerBtn') }}</span>
            </button>
          </form>

          <p class="text-xs text-center mt-4" style="color: rgba(255,255,255,0.35);">
            {{ t('auth.termsAgree') }}
          </p>

          <!-- Divider -->
          <div class="flex items-center gap-3 my-6">
            <div class="flex-1 h-px" style="background: rgba(255,255,255,0.06);"></div>
            <span class="text-xs" style="color: rgba(255,255,255,0.35);">{{ t('auth.hasAccount') }}</span>
            <div class="flex-1 h-px" style="background: rgba(255,255,255,0.06);"></div>
          </div>

          <RouterLink to="/auth/login"
            class="block w-full py-3.5 rounded font-semibold text-center transition-all duration-200"
            style="color: #1677ff; border: 1px solid rgba(22,119,255,0.3); background: transparent;"
            onmouseover="this.style.background='rgba(22,119,255,0.04)'"
            onmouseout="this.style.background='transparent'">
            {{ t('auth.signIn') }}
          </RouterLink>
        </div>
      </div>
    </div>
  </div>
</template>
