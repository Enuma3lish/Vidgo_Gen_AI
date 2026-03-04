<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore, useCreditsStore } from '@/stores'
import LanguageSelector from './LanguageSelector.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const creditsStore = useCreditsStore()
const isScrolled = ref(false)
const mobileMenuOpen = ref(false)

function handleScroll() {
  isScrolled.value = window.scrollY > 20
}
function handleLogout() {
  authStore.logout()
  router.push('/')
}
onMounted(async () => {
  if (authStore.isAuthenticated) {
    try { await creditsStore.fetchBalance() } catch {}
  }
  window.addEventListener('scroll', handleScroll)
  handleScroll()
})
onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<template>
  <header
    class="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
    :class="[
      isScrolled
        ? 'bg-dark-900/95 backdrop-blur-lg shadow-lg'
        : 'bg-dark-900/80 backdrop-blur-sm'
    ]"
    style="border-bottom: 1px solid rgba(0,184,230,0.15);"
  >
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <!-- Logo -->
        <RouterLink to="/" class="flex items-center gap-2 flex-shrink-0">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center font-black text-white text-sm"
            style="background: linear-gradient(135deg, #00b8e6, #0077a8); box-shadow: 0 0 12px rgba(0,184,230,0.4);">
            V
          </div>
          <span class="text-lg font-black tracking-tight" style="color: #e8f4ff;">VidGo <span style="color: #00b8e6;">AI</span></span>
        </RouterLink>

        <!-- Center Nav -->
        <nav class="hidden md:flex items-center gap-1">
          <RouterLink to="/" class="nav-link rounded-lg font-medium" style="color: #a8c8e8;" active-class="!text-[#00b8e6]">
            {{ t('nav.home') }}
          </RouterLink>
          <RouterLink to="/pricing" class="nav-link rounded-lg font-medium" style="color: #a8c8e8;" active-class="!text-[#00b8e6]">
            {{ t('nav.pricing') }}
          </RouterLink>
          <div class="relative group">
            <button class="nav-link rounded-lg font-medium flex items-center gap-1" style="color: #a8c8e8;">
              {{ t('nav.tools') }}
              <svg class="w-3.5 h-3.5 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
            </button>
            <div class="absolute top-full left-0 mt-1 w-52 rounded-2xl shadow-xl overflow-hidden opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50"
              style="background: #0f1f3d; border: 1px solid rgba(0,184,230,0.2);">
              <RouterLink to="/tools/short-video" class="flex items-center gap-3 px-4 py-3 text-sm font-medium transition-colors" style="color: #a8c8e8;" onmouseover="this.style.background='rgba(0,184,230,0.08)';this.style.color='#00b8e6'" onmouseout="this.style.background='';this.style.color='#a8c8e8'">
                <span class="text-lg">🎬</span> AI 短影片
              </RouterLink>
              <RouterLink to="/tools/try-on" class="flex items-center gap-3 px-4 py-3 text-sm font-medium transition-colors" style="color: #a8c8e8;" onmouseover="this.style.background='rgba(0,184,230,0.08)';this.style.color='#00b8e6'" onmouseout="this.style.background='';this.style.color='#a8c8e8'">
                <span class="text-lg">👔</span> 虛擬試穿
              </RouterLink>
              <RouterLink to="/tools/product-scene" class="flex items-center gap-3 px-4 py-3 text-sm font-medium transition-colors" style="color: #a8c8e8;" onmouseover="this.style.background='rgba(0,184,230,0.08)';this.style.color='#00b8e6'" onmouseout="this.style.background='';this.style.color='#a8c8e8'">
                <span class="text-lg">🛍️</span> 商品場景
              </RouterLink>
              <RouterLink to="/tools/background-removal" class="flex items-center gap-3 px-4 py-3 text-sm font-medium transition-colors" style="color: #a8c8e8;" onmouseover="this.style.background='rgba(0,184,230,0.08)';this.style.color='#00b8e6'" onmouseout="this.style.background='';this.style.color='#a8c8e8'">
                <span class="text-lg">✂️</span> 背景去除
              </RouterLink>
              <RouterLink to="/tools/room-redesign" class="flex items-center gap-3 px-4 py-3 text-sm font-medium transition-colors" style="color: #a8c8e8;" onmouseover="this.style.background='rgba(0,184,230,0.08)';this.style.color='#00b8e6'" onmouseout="this.style.background='';this.style.color='#a8c8e8'">
                <span class="text-lg">🏠</span> 室內設計
              </RouterLink>
              <RouterLink to="/tools/avatar" class="flex items-center gap-3 px-4 py-3 text-sm font-medium transition-colors" style="color: #a8c8e8;" onmouseover="this.style.background='rgba(0,184,230,0.08)';this.style.color='#00b8e6'" onmouseout="this.style.background='';this.style.color='#a8c8e8'">
                <span class="text-lg">🤖</span> AI 頭像
              </RouterLink>
            </div>
          </div>
        </nav>

        <!-- Right Side -->
        <div class="flex items-center gap-2">
          <LanguageSelector />
          <template v-if="authStore.isAuthenticated">
            <RouterLink
              to="/dashboard"
              class="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold transition-all"
              style="background: rgba(0,184,230,0.15); color: #00b8e6; border: 1px solid rgba(0,184,230,0.3);"
            >
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M10 2a8 8 0 100 16A8 8 0 0010 2zm0 14a6 6 0 110-12 6 6 0 010 12zm1-9H9v4l3.5 2.1.7-1.2-2.2-1.3V7z"/></svg>
              {{ creditsStore.balance }} 點
            </RouterLink>
            <RouterLink
              to="/dashboard"
              class="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium transition-colors"
              style="color: #a8c8e8;"
            >
              {{ t('nav.dashboard') }}
            </RouterLink>
            <RouterLink
              to="/dashboard/social-accounts"
              class="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium transition-colors"
              style="color: #a8c8e8;"
              title="社交媒體帳號"
            >
              📡 社交發布
            </RouterLink>
            <button
              @click="handleLogout"
              class="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium transition-colors"
              style="color: #6b9ab8;"
            >
              {{ t('nav.logout') }}
            </button>
          </template>
          <template v-else>
            <RouterLink
              to="/auth/login"
              class="hidden md:inline-flex px-4 py-2 text-sm font-medium transition-colors"
              style="color: #a8c8e8;"
            >
              {{ t('nav.login') }}
            </RouterLink>
            <RouterLink
              to="/auth/register"
              class="inline-flex items-center px-4 py-2 text-sm font-semibold rounded-full transition-all duration-200"
              style="background: linear-gradient(135deg, #00b8e6, #0077a8); color: white; box-shadow: 0 2px 12px rgba(0,184,230,0.35);"
            >
              免費開始
            </RouterLink>
          </template>
          <!-- Mobile Menu Button -->
          <button
            @click="mobileMenuOpen = !mobileMenuOpen"
            class="md:hidden p-2 rounded-lg transition-colors"
            style="color: #a8c8e8;"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path v-if="!mobileMenuOpen" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
              <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Mobile Menu -->
    <div v-if="mobileMenuOpen" class="md:hidden shadow-lg" style="background: #0f1f3d; border-top: 1px solid rgba(0,184,230,0.15);">
      <div class="px-4 py-4 space-y-1">
        <RouterLink to="/" class="block px-4 py-2.5 rounded-xl font-medium transition-colors" style="color: #a8c8e8;" @click="mobileMenuOpen = false">
          {{ t('nav.home') }}
        </RouterLink>
        <RouterLink to="/pricing" class="block px-4 py-2.5 rounded-xl font-medium transition-colors" style="color: #a8c8e8;" @click="mobileMenuOpen = false">
          {{ t('nav.pricing') }}
        </RouterLink>
        <RouterLink to="/tools/short-video" class="block px-4 py-2.5 rounded-xl font-medium transition-colors" style="color: #a8c8e8;" @click="mobileMenuOpen = false">
          AI 影片
        </RouterLink>
        <div v-if="!authStore.isAuthenticated" class="pt-3 space-y-2" style="border-top: 1px solid rgba(0,184,230,0.15);">
          <RouterLink to="/auth/login" class="block px-4 py-2.5 rounded-xl font-medium transition-colors" style="color: #a8c8e8;" @click="mobileMenuOpen = false">
            {{ t('nav.login') }}
          </RouterLink>
          <RouterLink to="/auth/register" class="block px-4 py-2.5 rounded-xl text-white text-center font-semibold" style="background: linear-gradient(135deg, #00b8e6, #0077a8);" @click="mobileMenuOpen = false">
            免費開始
          </RouterLink>
        </div>
        <div v-else class="pt-3 space-y-2" style="border-top: 1px solid rgba(0,184,230,0.15);">
          <RouterLink to="/dashboard" class="block px-4 py-2.5 rounded-xl font-medium transition-colors" style="color: #a8c8e8;" @click="mobileMenuOpen = false">
            {{ t('nav.dashboard') }}
          </RouterLink>
          <RouterLink to="/dashboard/social-accounts" class="block px-4 py-2.5 rounded-xl font-medium transition-colors" style="color: #a8c8e8;" @click="mobileMenuOpen = false">
            📡 社交媒體帳號
          </RouterLink>
          <button @click="handleLogout; mobileMenuOpen = false" class="block w-full text-left px-4 py-2.5 rounded-xl font-medium transition-colors" style="color: #6b9ab8;">
            {{ t('nav.logout') }}
          </button>
        </div>
      </div>
    </div>
  </header>
</template>
