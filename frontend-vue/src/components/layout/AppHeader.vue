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
const toolsOpen = ref(false)

function handleScroll() {
  isScrolled.value = window.scrollY > 10
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
    :style="isScrolled
      ? 'background: rgba(255,255,255,0.98); backdrop-filter: blur(12px); box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-bottom: 1px solid rgba(0,0,0,0.06);'
      : 'background: rgba(255,255,255,0.96); backdrop-filter: blur(8px); border-bottom: 1px solid rgba(0,0,0,0.04);'"
  >
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">

        <!-- Logo -->
        <RouterLink to="/" class="flex items-center gap-2 flex-shrink-0">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center font-black text-white text-sm"
            style="background: linear-gradient(135deg, #1677ff, #0958d9);">
            V
          </div>
          <span class="text-lg font-black tracking-tight" style="color: #1F1F1F;">VidGo <span style="color: #1677ff;">AI</span></span>
        </RouterLink>

        <!-- Center Nav -->
        <nav class="hidden md:flex items-center gap-1">
          <RouterLink to="/" class="nav-link rounded-md" active-class="!text-[#1677ff]">
            {{ t('nav.home') }}
          </RouterLink>

          <!-- Tools Dropdown -->
          <div class="relative" @mouseenter="toolsOpen = true" @mouseleave="toolsOpen = false">
            <button class="nav-link rounded-md flex items-center gap-1" style="color: rgba(0,0,0,0.65);">
              {{ t('nav.tools') }}
              <svg class="w-3.5 h-3.5 mt-0.5 transition-transform" :class="toolsOpen ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
              </svg>
            </button>
            <div
              v-show="toolsOpen"
              class="absolute top-full left-1/2 -translate-x-1/2 mt-1 rounded-xl overflow-hidden"
              style="background: #ffffff; border: 1px solid rgba(0,0,0,0.1); box-shadow: 0 12px 32px rgba(0,0,0,0.14); width: 580px;"
            >
              <div class="grid grid-cols-3 gap-0 p-4">
                <!-- Fashion AI Column -->
                <div>
                  <div class="px-3 py-1.5 text-xs font-bold uppercase tracking-wider" style="color: rgba(0,0,0,0.35);">{{ t('lp.categories.fashionAI') }}</div>
                  <RouterLink to="/tools/try-on" class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors hover:bg-blue-50" style="color: rgba(0,0,0,0.65);" @click="toolsOpen = false">
                    <span>👗</span><span class="font-medium" style="color: #1F1F1F;">{{ t('lp.allTools.tryOn.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/ai-model-swap" class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors hover:bg-blue-50" style="color: rgba(0,0,0,0.65);" @click="toolsOpen = false">
                    <span>🧑‍🎤</span><span class="font-medium" style="color: #1F1F1F;">{{ t('lp.allTools.aiModelSwap.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/short-video" class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors hover:bg-blue-50" style="color: rgba(0,0,0,0.65);" @click="toolsOpen = false">
                    <span>🎬</span><span class="font-medium" style="color: #1F1F1F;">{{ t('lp.allTools.fashionReels.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/avatar" class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors hover:bg-blue-50" style="color: rgba(0,0,0,0.65);" @click="toolsOpen = false">
                    <span>🎭</span><span class="font-medium" style="color: #1F1F1F;">{{ t('lp.allTools.productAvatars.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/try-on-accessories" class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors hover:bg-blue-50" style="color: rgba(0,0,0,0.65);" @click="toolsOpen = false">
                    <span>💍</span><span class="font-medium" style="color: #1F1F1F;">{{ t('lp.allTools.tryOnAccessories.name') }}</span>
                  </RouterLink>
                </div>
                <!-- E-commerce AI Column -->
                <div>
                  <div class="px-3 py-1.5 text-xs font-bold uppercase tracking-wider" style="color: rgba(0,0,0,0.35);">{{ t('lp.categories.ecommerceAI') }}</div>
                  <RouterLink to="/tools/product-scene" class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors hover:bg-blue-50" style="color: rgba(0,0,0,0.65);" @click="toolsOpen = false">
                    <span>📸</span><span class="font-medium" style="color: #1F1F1F;">{{ t('lp.allTools.productAnyshoot.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/background-removal" class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors hover:bg-blue-50" style="color: rgba(0,0,0,0.65);" @click="toolsOpen = false">
                    <span>✂️</span><span class="font-medium" style="color: #1F1F1F;">{{ t('lp.allTools.bgRemoval.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/background-removal" class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors hover:bg-blue-50" style="color: rgba(0,0,0,0.65);" @click="toolsOpen = false">
                    <span>🖼️</span><span class="font-medium" style="color: #1F1F1F;">{{ t('lp.allTools.aiBackgrounds.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/effects" class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors hover:bg-blue-50" style="color: rgba(0,0,0,0.65);" @click="toolsOpen = false">
                    <span>🌑</span><span class="font-medium" style="color: #1F1F1F;">{{ t('lp.allTools.aiShadows.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/ai-templates" class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors hover:bg-blue-50" style="color: rgba(0,0,0,0.65);" @click="toolsOpen = false">
                    <span>📐</span><span class="font-medium" style="color: #1F1F1F;">{{ t('lp.allTools.aiTemplates.name') }}</span>
                  </RouterLink>
                </div>
                <!-- Design & Content AI Column -->
                <div>
                  <div class="px-3 py-1.5 text-xs font-bold uppercase tracking-wider" style="color: rgba(0,0,0,0.35);">{{ t('lp.categories.designAI') }}</div>
                  <RouterLink to="/tools/room-redesign" class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors hover:bg-blue-50" style="color: rgba(0,0,0,0.65);" @click="toolsOpen = false">
                    <span>🏠</span><span class="font-medium" style="color: #1F1F1F;">{{ t('lp.allTools.roomRedesign.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/effects" class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors hover:bg-blue-50" style="color: rgba(0,0,0,0.65);" @click="toolsOpen = false">
                    <span>🎨</span><span class="font-medium" style="color: #1F1F1F;">{{ t('lp.allTools.styleClone.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/image-translator" class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors hover:bg-blue-50" style="color: rgba(0,0,0,0.65);" @click="toolsOpen = false">
                    <span>🌐</span><span class="font-medium" style="color: #1F1F1F;">{{ t('lp.allTools.imageTranslator.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/remove-watermark" class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors hover:bg-blue-50" style="color: rgba(0,0,0,0.65);" @click="toolsOpen = false">
                    <span>💧</span><span class="font-medium" style="color: #1F1F1F;">{{ t('lp.allTools.removeWatermark.name') }}</span>
                  </RouterLink>
                </div>
              </div>
            </div>
          </div>

          <RouterLink to="/pricing" class="nav-link rounded-md" active-class="!text-[#1677ff]">
            {{ t('nav.pricing') }}
          </RouterLink>
        </nav>

        <!-- Right Side -->
        <div class="flex items-center gap-2">
          <LanguageSelector />
          <template v-if="authStore.isAuthenticated">
            <RouterLink
              to="/dashboard"
              class="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold transition-all"
              style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
              {{ creditsStore.balance }} {{ t('nav.credits') }}
            </RouterLink>
            <RouterLink to="/dashboard" class="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.65);">
              {{ t('nav.dashboard') }}
            </RouterLink>
            <button @click="handleLogout" class="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.45);">
              {{ t('nav.logout') }}
            </button>
          </template>
          <template v-else>
            <RouterLink to="/auth/login" class="hidden md:inline-flex px-4 py-2 text-sm font-medium rounded-md transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.65);">
              {{ t('nav.login') }}
            </RouterLink>
            <RouterLink to="/auth/register" class="inline-flex items-center px-4 py-2 text-sm font-semibold text-white rounded transition-all duration-200 hover:opacity-90" style="background: #1677ff;">
              {{ t('lp.ctaPrimary') }}
            </RouterLink>
          </template>
          <!-- Mobile Menu Button -->
          <button @click="mobileMenuOpen = !mobileMenuOpen" class="md:hidden p-2 rounded-md transition-colors hover:bg-gray-100" style="color: rgba(0,0,0,0.65);">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path v-if="!mobileMenuOpen" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
              <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Mobile Menu -->
    <div v-if="mobileMenuOpen" class="md:hidden" style="background: #ffffff; border-top: 1px solid rgba(0,0,0,0.06); box-shadow: 0 4px 12px rgba(0,0,0,0.08);">
      <div class="px-4 py-4 space-y-1">
        <RouterLink to="/" class="block px-4 py-2.5 rounded-lg font-medium transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.65);" @click="mobileMenuOpen = false">{{ t('nav.home') }}</RouterLink>
        <RouterLink to="/pricing" class="block px-4 py-2.5 rounded-lg font-medium transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.65);" @click="mobileMenuOpen = false">{{ t('nav.pricing') }}</RouterLink>
        <div class="px-4 pt-2 pb-1 text-xs font-semibold uppercase tracking-wider" style="color: rgba(0,0,0,0.35);">{{ t('nav.tools') }}</div>
        <RouterLink to="/tools/try-on" class="block px-4 py-2.5 rounded-lg font-medium transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.65);" @click="mobileMenuOpen = false">👗 {{ t('lp.allTools.tryOn.name') }}</RouterLink>
        <RouterLink to="/tools/ai-model-swap" class="block px-4 py-2.5 rounded-lg font-medium transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.65);" @click="mobileMenuOpen = false">🧑‍🎤 {{ t('lp.allTools.aiModelSwap.name') }}</RouterLink>
        <RouterLink to="/tools/short-video" class="block px-4 py-2.5 rounded-lg font-medium transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.65);" @click="mobileMenuOpen = false">🎬 {{ t('lp.allTools.fashionReels.name') }}</RouterLink>
        <RouterLink to="/tools/avatar" class="block px-4 py-2.5 rounded-lg font-medium transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.65);" @click="mobileMenuOpen = false">🎭 {{ t('lp.allTools.productAvatars.name') }}</RouterLink>
        <RouterLink to="/tools/product-scene" class="block px-4 py-2.5 rounded-lg font-medium transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.65);" @click="mobileMenuOpen = false">📸 {{ t('lp.allTools.productAnyshoot.name') }}</RouterLink>
        <RouterLink to="/tools/background-removal" class="block px-4 py-2.5 rounded-lg font-medium transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.65);" @click="mobileMenuOpen = false">✂️ {{ t('lp.allTools.bgRemoval.name') }}</RouterLink>
        <RouterLink to="/tools/room-redesign" class="block px-4 py-2.5 rounded-lg font-medium transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.65);" @click="mobileMenuOpen = false">🏠 {{ t('lp.allTools.roomRedesign.name') }}</RouterLink>
        <RouterLink to="/tools/image-translator" class="block px-4 py-2.5 rounded-lg font-medium transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.65);" @click="mobileMenuOpen = false">🌐 {{ t('lp.allTools.imageTranslator.name') }}</RouterLink>
        <div v-if="!authStore.isAuthenticated" class="pt-3 space-y-2" style="border-top: 1px solid rgba(0,0,0,0.06);">
          <RouterLink to="/auth/login" class="block px-4 py-2.5 rounded-lg font-medium transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.65);" @click="mobileMenuOpen = false">{{ t('nav.login') }}</RouterLink>
          <RouterLink to="/auth/register" class="block px-4 py-2.5 rounded-lg text-white text-center font-semibold" style="background: #1677ff;" @click="mobileMenuOpen = false">{{ t('lp.ctaPrimary') }}</RouterLink>
        </div>
        <div v-else class="pt-3 space-y-2" style="border-top: 1px solid rgba(0,0,0,0.06);">
          <RouterLink to="/dashboard" class="block px-4 py-2.5 rounded-lg font-medium transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.65);" @click="mobileMenuOpen = false">{{ t('nav.dashboard') }}</RouterLink>
          <button @click="handleLogout; mobileMenuOpen = false" class="block w-full text-left px-4 py-2.5 rounded-lg font-medium transition-colors hover:bg-gray-50" style="color: rgba(0,0,0,0.45);">{{ t('nav.logout') }}</button>
        </div>
      </div>
    </div>
  </header>
</template>
