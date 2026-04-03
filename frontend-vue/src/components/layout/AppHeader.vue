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
      ? 'background: rgba(9,9,11,0.95); backdrop-filter: blur(16px); box-shadow: 0 1px 0 rgba(255,255,255,0.06);'
      : 'background: rgba(9,9,11,0.8); backdrop-filter: blur(8px);'"
  >
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">

        <!-- Logo -->
        <RouterLink to="/" class="flex items-center gap-2.5 flex-shrink-0">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center font-black text-white text-sm"
            style="background: linear-gradient(135deg, #1677ff, #0958d9);">
            V
          </div>
          <span class="text-lg font-black tracking-tight" style="color: #f5f5fa;">VidGo <span style="color: #1677ff;">AI</span></span>
        </RouterLink>

        <!-- Center Nav -->
        <nav class="hidden md:flex items-center gap-1">
          <RouterLink to="/" class="nav-link rounded-lg" active-class="!text-white">
            {{ t('nav.home') }}
          </RouterLink>

          <RouterLink to="/gallery" class="nav-link rounded-lg" active-class="!text-white">
            {{ t('gallery.title') }}
          </RouterLink>

          <!-- Tools Dropdown -->
          <div class="relative" @mouseenter="toolsOpen = true" @mouseleave="toolsOpen = false">
            <button class="nav-link rounded-lg flex items-center gap-1">
              {{ t('nav.tools') }}
              <svg class="w-3.5 h-3.5 mt-0.5 transition-transform" :class="toolsOpen ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
              </svg>
            </button>
            <div
              v-show="toolsOpen"
              class="absolute top-full left-1/2 -translate-x-1/2 mt-2 rounded-xl overflow-hidden dropdown-menu"
              style="width: 600px;"
            >
              <div class="grid grid-cols-3 gap-0 p-4">
                <!-- Fashion & Video Column -->
                <div>
                  <div class="px-3 py-1.5 text-xs font-bold uppercase tracking-wider" style="color: #6b6b8a;">{{ t('lp.categories.fashionAI') }}</div>
                  <RouterLink to="/tools/try-on" class="dropdown-item" @click="toolsOpen = false">
                    <span>👗</span><span class="font-medium" style="color: #e8e8f0;">{{ t('lp.allTools.tryOn.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/short-video" class="dropdown-item" @click="toolsOpen = false">
                    <span>🎬</span><span class="font-medium" style="color: #e8e8f0;">{{ t('lp.allTools.fashionReels.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/text-to-video" class="dropdown-item" @click="toolsOpen = false">
                    <span>🎥</span><span class="font-medium" style="color: #e8e8f0;">Text to Video</span>
                  </RouterLink>
                  <RouterLink to="/tools/avatar" class="dropdown-item" @click="toolsOpen = false">
                    <span>🎭</span><span class="font-medium" style="color: #e8e8f0;">{{ t('lp.allTools.productAvatars.name') }}</span>
                  </RouterLink>
                </div>
                <!-- E-commerce AI Column -->
                <div>
                  <div class="px-3 py-1.5 text-xs font-bold uppercase tracking-wider" style="color: #6b6b8a;">{{ t('lp.categories.ecommerceAI') }}</div>
                  <RouterLink to="/tools/product-scene" class="dropdown-item" @click="toolsOpen = false">
                    <span>📸</span><span class="font-medium" style="color: #e8e8f0;">{{ t('lp.allTools.productAnyshoot.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/background-removal" class="dropdown-item" @click="toolsOpen = false">
                    <span>✂️</span><span class="font-medium" style="color: #e8e8f0;">{{ t('lp.allTools.bgRemoval.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/upscale" class="dropdown-item" @click="toolsOpen = false">
                    <span>🔍</span><span class="font-medium" style="color: #e8e8f0;">HD Upscale</span>
                  </RouterLink>
                  <RouterLink to="/tools/pattern-generate" class="dropdown-item" @click="toolsOpen = false">
                    <span>🎨</span><span class="font-medium" style="color: #e8e8f0;">Pattern Design</span>
                  </RouterLink>
                </div>
                <!-- Design & Effects Column -->
                <div>
                  <div class="px-3 py-1.5 text-xs font-bold uppercase tracking-wider" style="color: #6b6b8a;">{{ t('lp.categories.designAI') }}</div>
                  <RouterLink to="/tools/room-redesign" class="dropdown-item" @click="toolsOpen = false">
                    <span>🏠</span><span class="font-medium" style="color: #e8e8f0;">{{ t('lp.allTools.roomRedesign.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/effects" class="dropdown-item" @click="toolsOpen = false">
                    <span>🎨</span><span class="font-medium" style="color: #e8e8f0;">{{ t('lp.allTools.styleClone.name') }}</span>
                  </RouterLink>
                  <RouterLink to="/tools/image-transform" class="dropdown-item" @click="toolsOpen = false">
                    <span>🔄</span><span class="font-medium" style="color: #e8e8f0;">Image Transform</span>
                  </RouterLink>
                  <RouterLink to="/tools/video-transform" class="dropdown-item" @click="toolsOpen = false">
                    <span>🎞️</span><span class="font-medium" style="color: #e8e8f0;">Video Style Transfer</span>
                  </RouterLink>
                </div>
              </div>
            </div>
          </div>

          <RouterLink to="/pricing" class="nav-link rounded-lg" active-class="!text-white">
            {{ t('nav.pricing') }}
          </RouterLink>
        </nav>

        <!-- Right Side -->
        <div class="flex items-center gap-2">
          <LanguageSelector />
          <template v-if="authStore.isAuthenticated">
            <RouterLink
              to="/dashboard"
              class="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold transition-all credit-badge"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
              {{ creditsStore.remainingCredits.toLocaleString() }} {{ t('nav.credits') }}
            </RouterLink>
            <RouterLink to="/dashboard" class="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors" style="color: #9494b0;" @mouseenter="($event.target as HTMLElement).style.color='#f5f5fa'" @mouseleave="($event.target as HTMLElement).style.color='#9494b0'">
              {{ t('nav.dashboard') }}
            </RouterLink>
            <button @click="handleLogout" class="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors" style="color: #6b6b8a;" @mouseenter="($event.target as HTMLElement).style.color='#9494b0'" @mouseleave="($event.target as HTMLElement).style.color='#6b6b8a'">
              {{ t('nav.logout') }}
            </button>
          </template>
          <template v-else>
            <RouterLink to="/auth/login" class="hidden md:inline-flex px-4 py-2 text-sm font-medium rounded-lg transition-colors" style="color: #9494b0;" @mouseenter="($event.target as HTMLElement).style.color='#f5f5fa'" @mouseleave="($event.target as HTMLElement).style.color='#9494b0'">
              {{ t('nav.login') }}
            </RouterLink>
            <RouterLink to="/auth/register" class="hidden md:inline-flex items-center px-5 py-2 text-sm font-semibold text-white rounded-lg transition-all duration-200" style="background: #1677ff;" @mouseenter="($event.target as HTMLElement).style.boxShadow='0 4px 20px rgba(22,119,255,0.4)'" @mouseleave="($event.target as HTMLElement).style.boxShadow='none'">
              {{ t('lp.ctaPrimary') }}
            </RouterLink>
          </template>
          <!-- Mobile Menu Button -->
          <button @click="mobileMenuOpen = !mobileMenuOpen" class="md:hidden p-2 rounded-lg transition-colors" style="color: #9494b0;" @mouseenter="($event.target as HTMLElement).style.background='rgba(255,255,255,0.06)'" @mouseleave="($event.target as HTMLElement).style.background='transparent'">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path v-if="!mobileMenuOpen" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
              <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Mobile Menu -->
    <div v-if="mobileMenuOpen" class="md:hidden" style="background: #0f0f17; border-top: 1px solid rgba(255,255,255,0.06);">
      <div class="px-4 py-4 space-y-1">
        <RouterLink to="/" class="block px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #9494b0;" @click="mobileMenuOpen = false">{{ t('nav.home') }}</RouterLink>
        <RouterLink to="/gallery" class="block px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #9494b0;" @click="mobileMenuOpen = false">{{ t('gallery.title') }}</RouterLink>
        <RouterLink to="/pricing" class="block px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #9494b0;" @click="mobileMenuOpen = false">{{ t('nav.pricing') }}</RouterLink>
        <div class="px-4 pt-2 pb-1 text-xs font-semibold uppercase tracking-wider" style="color: #6b6b8a;">{{ t('nav.tools') }}</div>
        <RouterLink to="/tools/try-on" class="block px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #9494b0;" @click="mobileMenuOpen = false">👗 {{ t('lp.allTools.tryOn.name') }}</RouterLink>
        <RouterLink to="/tools/short-video" class="block px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #9494b0;" @click="mobileMenuOpen = false">🎬 {{ t('lp.allTools.fashionReels.name') }}</RouterLink>
        <RouterLink to="/tools/text-to-video" class="block px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #9494b0;" @click="mobileMenuOpen = false">🎥 Text to Video</RouterLink>
        <RouterLink to="/tools/avatar" class="block px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #9494b0;" @click="mobileMenuOpen = false">🎭 {{ t('lp.allTools.productAvatars.name') }}</RouterLink>
        <RouterLink to="/tools/product-scene" class="block px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #9494b0;" @click="mobileMenuOpen = false">📸 {{ t('lp.allTools.productAnyshoot.name') }}</RouterLink>
        <RouterLink to="/tools/background-removal" class="block px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #9494b0;" @click="mobileMenuOpen = false">✂️ {{ t('lp.allTools.bgRemoval.name') }}</RouterLink>
        <RouterLink to="/tools/upscale" class="block px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #9494b0;" @click="mobileMenuOpen = false">🔍 HD Upscale</RouterLink>
        <RouterLink to="/tools/room-redesign" class="block px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #9494b0;" @click="mobileMenuOpen = false">🏠 {{ t('lp.allTools.roomRedesign.name') }}</RouterLink>
        <RouterLink to="/tools/effects" class="block px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #9494b0;" @click="mobileMenuOpen = false">🎨 {{ t('lp.allTools.styleClone.name') }}</RouterLink>
        <div v-if="!authStore.isAuthenticated" class="pt-3 space-y-2" style="border-top: 1px solid rgba(255,255,255,0.06);">
          <RouterLink to="/auth/login" class="block px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #9494b0;" @click="mobileMenuOpen = false">{{ t('nav.login') }}</RouterLink>
          <RouterLink to="/auth/register" class="block px-4 py-2.5 rounded-lg text-white text-center font-semibold" style="background: #1677ff;" @click="mobileMenuOpen = false">{{ t('lp.ctaPrimary') }}</RouterLink>
        </div>
        <div v-else class="pt-3 space-y-2" style="border-top: 1px solid rgba(255,255,255,0.06);">
          <RouterLink to="/dashboard" class="block px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #9494b0;" @click="mobileMenuOpen = false">{{ t('nav.dashboard') }}</RouterLink>
          <button @click="handleLogout; mobileMenuOpen = false" class="block w-full text-left px-4 py-2.5 rounded-lg font-medium transition-colors" style="color: #6b6b8a;">{{ t('nav.logout') }}</button>
        </div>
      </div>
    </div>
  </header>
</template>
