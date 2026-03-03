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
        ? 'bg-white/95 backdrop-blur-lg shadow-sm border-b border-black/8'
        : 'bg-white/90 backdrop-blur-sm'
    ]"
  >
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <!-- Logo -->
        <RouterLink to="/" class="flex items-center gap-2 flex-shrink-0">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center font-black text-white text-sm" style="background: #111111;">
            V
          </div>
          <span class="text-lg font-black text-dark-900 tracking-tight">VidGo AI</span>
        </RouterLink>

        <!-- Center Nav -->
        <nav class="hidden md:flex items-center gap-1">
          <RouterLink to="/" class="nav-link rounded-lg hover:bg-black/5 font-medium text-dark-700">
            {{ t('nav.home') }}
          </RouterLink>
          <RouterLink to="/pricing" class="nav-link rounded-lg hover:bg-black/5 font-medium text-dark-700">
            {{ t('nav.pricing') }}
          </RouterLink>
          <div class="relative group">
            <button class="nav-link rounded-lg hover:bg-black/5 font-medium text-dark-700 flex items-center gap-1">
              工具
              <svg class="w-3.5 h-3.5 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
            </button>
            <div class="absolute top-full left-0 mt-1 w-52 bg-white rounded-2xl shadow-xl border border-black/8 overflow-hidden opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
              <RouterLink to="/tools/short-video" class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-dark-700 text-sm font-medium">
                <span class="text-lg">🎬</span> AI 短影片
              </RouterLink>
              <RouterLink to="/tools/try-on" class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-dark-700 text-sm font-medium">
                <span class="text-lg">👔</span> 虛擬試穿
              </RouterLink>
              <RouterLink to="/tools/product-scene" class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-dark-700 text-sm font-medium">
                <span class="text-lg">🛍️</span> 商品場景
              </RouterLink>
              <RouterLink to="/tools/background-removal" class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-dark-700 text-sm font-medium">
                <span class="text-lg">✂️</span> 背景去除
              </RouterLink>
              <RouterLink to="/tools/room-redesign" class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-dark-700 text-sm font-medium">
                <span class="text-lg">🏠</span> 室內設計
              </RouterLink>
              <RouterLink to="/tools/avatar" class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-dark-700 text-sm font-medium">
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
              class="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold transition-colors"
              style="background: #d4f06b; color: #111111;"
            >
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M10 2a8 8 0 100 16A8 8 0 0010 2zm0 14a6 6 0 110-12 6 6 0 010 12zm1-9H9v4l3.5 2.1.7-1.2-2.2-1.3V7z"/></svg>
              {{ creditsStore.balance }} 點
            </RouterLink>
            <RouterLink
              to="/dashboard"
              class="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-dark-700 hover:text-dark-900 transition-colors"
            >
              {{ t('nav.dashboard') }}
            </RouterLink>
            <button
              @click="handleLogout"
              class="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-dark-500 hover:text-dark-700 transition-colors"
            >
              {{ t('nav.logout') }}
            </button>
          </template>
          <template v-else>
            <RouterLink
              to="/auth/login"
              class="hidden md:inline-flex px-4 py-2 text-sm font-medium text-dark-700 hover:text-dark-900 transition-colors"
            >
              {{ t('nav.login') }}
            </RouterLink>
            <RouterLink
              to="/auth/register"
              class="inline-flex items-center px-4 py-2 text-sm font-semibold bg-dark-900 text-white rounded-full hover:bg-dark-800 transition-all duration-200"
              style="box-shadow: 0 2px 8px rgba(0,0,0,0.15);"
            >
              免費開始
            </RouterLink>
          </template>
          <!-- Mobile Menu Button -->
          <button
            @click="mobileMenuOpen = !mobileMenuOpen"
            class="md:hidden p-2 text-dark-600 hover:text-dark-900 rounded-lg hover:bg-black/5"
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
    <div v-if="mobileMenuOpen" class="md:hidden bg-white border-t border-black/8 shadow-lg">
      <div class="px-4 py-4 space-y-1">
        <RouterLink to="/" class="block px-4 py-2.5 rounded-xl text-dark-700 hover:bg-black/5 font-medium" @click="mobileMenuOpen = false">
          {{ t('nav.home') }}
        </RouterLink>
        <RouterLink to="/pricing" class="block px-4 py-2.5 rounded-xl text-dark-700 hover:bg-black/5 font-medium" @click="mobileMenuOpen = false">
          {{ t('nav.pricing') }}
        </RouterLink>
        <RouterLink to="/tools/short-video" class="block px-4 py-2.5 rounded-xl text-dark-700 hover:bg-black/5 font-medium" @click="mobileMenuOpen = false">
          AI 影片
        </RouterLink>
        <div v-if="!authStore.isAuthenticated" class="pt-3 border-t border-black/8 space-y-2">
          <RouterLink to="/auth/login" class="block px-4 py-2.5 rounded-xl text-dark-700 hover:bg-black/5 font-medium" @click="mobileMenuOpen = false">
            {{ t('nav.login') }}
          </RouterLink>
          <RouterLink to="/auth/register" class="block px-4 py-2.5 rounded-xl bg-dark-900 text-white text-center font-semibold" @click="mobileMenuOpen = false">
            免費開始
          </RouterLink>
        </div>
        <div v-else class="pt-3 border-t border-black/8 space-y-2">
          <RouterLink to="/dashboard" class="block px-4 py-2.5 rounded-xl text-dark-700 hover:bg-black/5 font-medium" @click="mobileMenuOpen = false">
            {{ t('nav.dashboard') }}
          </RouterLink>
          <button @click="handleLogout; mobileMenuOpen = false" class="block w-full text-left px-4 py-2.5 rounded-xl text-dark-500 hover:bg-black/5 font-medium">
            {{ t('nav.logout') }}
          </button>
        </div>
      </div>
    </div>
  </header>
</template>
