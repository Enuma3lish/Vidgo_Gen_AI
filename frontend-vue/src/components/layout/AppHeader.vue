<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore, useBrandingStore, useCreditsStore } from '@/stores'
import LanguageSelector from './LanguageSelector.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const creditsStore = useCreditsStore()
const brandingStore = useBrandingStore()
// Admin-uploaded logo overrides the built-in SVG mark when set. The
// store fetches /admin/branding/public on first mount and persists the
// result, so subsequent navigations re-use the same URL without
// re-hitting the API.
const logoUrl = computed(() => brandingStore.settings.logo_url || '')
const brandName = computed(() => brandingStore.settings.brand_name || 'VidgoAI')
const isScrolled = ref(false)
const mobileMenuOpen = ref(false)
const toolsOpen = ref(false)
const showCreditBadge = computed(() => authStore.isAuthenticated && !authStore.isAdmin)
const showPublicGalleryLinks = computed(() => !authStore.isAdmin)

interface ToolEntry { to: string; emoji: string; key: string }
interface ToolGroup { titleKey: string; items: ToolEntry[] }

const toolGroups: ToolGroup[] = [
  {
    titleKey: 'lp.categories.fashionAI',
    items: [
      { to: '/tools/try-on',      emoji: '👗', key: 'lp.allTools.tryOn.name' },
      { to: '/tools/short-video', emoji: '🎬', key: 'lp.allTools.fashionReels.name' },
      { to: '/tools/avatar',      emoji: '🗣️', key: 'lp.allTools.productAvatars.name' },
    ],
  },
  {
    titleKey: 'lp.categories.ecommerceAI',
    items: [
      { to: '/tools/product-scene',      emoji: '📸', key: 'lp.allTools.productAnyshoot.name' },
      { to: '/tools/background-removal', emoji: '✂️', key: 'lp.allTools.bgRemoval.name' },
      { to: '/tools/upscale',            emoji: '🔍', key: 'lp.allTools.hdUpscale.name' },
      { to: '/tools/pattern-generate',   emoji: '▦',  key: 'lp.allTools.patternGenerate.name' },
    ],
  },
  {
    titleKey: 'lp.categories.designAI',
    items: [
      { to: '/tools/room-redesign',  emoji: '🏠',  key: 'lp.allTools.roomRedesign.name' },
      { to: '/tools/video-transform', emoji: '🎞️', key: 'lp.allTools.videoTransform.name' },
      { to: '/gallery',               emoji: '🖼️', key: 'gallery.title' },
    ],
  },
  {
    titleKey: 'lp.imageTranslation.title',
    items: [
      { to: '/tools/image-translator', emoji: '文',  key: 'lp.allTools.imageTranslator.name' },
      { to: '/tools/video-dubbing',    emoji: '🎙️', key: 'lp.videoDubbing.title' },
    ],
  },
  {
    titleKey: 'lp.categories.proAi',
    items: [
      { to: '/tools/midjourney-imagine', emoji: '🎨', key: 'lp.allTools.midjourney.name' },
      { to: '/tools/kling-video',        emoji: '🎥', key: 'lp.allTools.klingVideo.name' },
      { to: '/tools/luma-video',         emoji: '✨', key: 'lp.allTools.lumaVideo.name' },
    ],
  },
]

const visibleToolGroups = computed(() =>
  toolGroups.map(group => ({
    ...group,
    items: showPublicGalleryLinks.value
      ? group.items
      : group.items.filter(item => item.to !== '/gallery'),
  })).filter(group => group.items.length > 0)
)

function handleScroll() {
  isScrolled.value = window.scrollY > 8
}
function handleLogout() {
  authStore.logout()
  router.push('/')
}
function closeMobile() { mobileMenuOpen.value = false }

onMounted(async () => {
  if (authStore.isAuthenticated && !authStore.isAdmin) {
    try { await creditsStore.fetchBalance() } catch { /* noop */ }
  }
  window.addEventListener('scroll', handleScroll, { passive: true })
  handleScroll()
})
onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<template>
  <header
    class="app-header fixed top-0 left-0 right-0 z-50"
    :class="{ scrolled: isScrolled }"
  >
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">

        <!-- Logo — admin-uploaded image (from site_settings.logo_url)
             wins, falls back to the built-in SVG mark when unset. -->
        <RouterLink to="/" class="flex items-center gap-2.5 flex-shrink-0 group" :aria-label="`${brandName} Home`">
          <template v-if="logoUrl">
            <img
              :src="logoUrl"
              :alt="brandName"
              class="flex-shrink-0 transition-all duration-300 group-hover:scale-105"
              style="height: 32px; width: auto; max-width: 160px; object-fit: contain; border-radius: 6px;"
            />
          </template>
          <template v-else>
            <div class="relative w-8 h-8 flex-shrink-0 transition-all duration-300 group-hover:scale-105 group-hover:shadow-[0_0_18px_rgba(245,158,11,0.45)]" style="border-radius: 9px; background: #f59e0b;">
              <svg class="absolute inset-0 w-full h-full" viewBox="0 0 32 32" fill="none">
                <path d="M9 10.5 L16 21 L23 10.5" stroke="#0a0a0a" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <span class="text-[15px] font-bold leading-none" style="font-family: 'Syne', sans-serif; color: var(--text-primary); letter-spacing: 0;">
              Vidgo<span style="color: #f59e0b;">AI</span>
            </span>
          </template>
        </RouterLink>

        <!-- Center Nav -->
        <nav class="hidden md:flex items-center gap-1">
          <RouterLink to="/" class="nav-link">{{ t('nav.home') }}</RouterLink>
          <RouterLink v-if="showPublicGalleryLinks" to="/gallery" class="nav-link">{{ t('gallery.title') }}</RouterLink>

          <!-- Tools Dropdown -->
          <div class="relative" @mouseenter="toolsOpen = true" @mouseleave="toolsOpen = false">
            <button class="nav-link flex items-center gap-1" :aria-expanded="toolsOpen" aria-haspopup="true">
              {{ t('nav.tools') }}
              <svg class="w-3.5 h-3.5 transition-transform duration-200" :class="toolsOpen ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
              </svg>
            </button>
            <Transition
              enter-active-class="transition duration-150 ease-out"
              enter-from-class="opacity-0 -translate-y-1"
              enter-to-class="opacity-100 translate-y-0"
              leave-active-class="transition duration-100 ease-in"
              leave-from-class="opacity-100"
              leave-to-class="opacity-0"
            >
              <div
                v-show="toolsOpen"
                class="absolute top-full left-1/2 -translate-x-1/2 pt-3 w-[calc(100vw-2rem)] md:w-[820px]"
              >
                <div class="dropdown-menu overflow-hidden">
                  <div class="grid grid-cols-4 gap-1 p-4">
                    <div v-for="group in visibleToolGroups" :key="group.titleKey">
                      <div class="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-muted">
                        {{ t(group.titleKey) }}
                      </div>
                      <RouterLink
                        v-for="item in group.items"
                        :key="item.to"
                        :to="item.to"
                        class="dropdown-item"
                        @click="toolsOpen = false"
                      >
                        <span class="text-base leading-none">{{ item.emoji }}</span>
                        <span>{{ t(item.key) }}</span>
                      </RouterLink>
                    </div>
                  </div>
                  <div class="px-4 py-3 flex items-center justify-between" style="background: rgba(245,158,11,0.05); border-top: 1px solid var(--border-subtle);">
                    <span class="text-xs text-secondary">{{ t('nav.tools') }} · {{ t('lp.sec3Sub') }}</span>
                    <RouterLink to="/" class="text-xs font-semibold" style="color: var(--color-primary);" @click="toolsOpen = false">
                      {{ t('lp.ctaSecondary') }} →
                    </RouterLink>
                  </div>
                </div>
              </div>
            </Transition>
          </div>

          <RouterLink to="/pricing" class="nav-link">{{ t('nav.pricing') }}</RouterLink>
        </nav>

        <!-- Right Side -->
        <div class="flex items-center gap-1.5">
          <LanguageSelector />
          <template v-if="authStore.isAuthenticated">
            <RouterLink
              v-if="showCreditBadge"
              to="/dashboard/my-works"
              class="hidden md:inline-flex credit-badge transition-all hover:scale-[1.02]"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
              {{ creditsStore.remainingCredits.toLocaleString() }} {{ t('nav.credits') }}
            </RouterLink>
            <RouterLink v-if="!authStore.isAdmin" to="/dashboard/my-works" class="hidden md:inline-flex nav-link">
              {{ t('nav.dashboard') }}
            </RouterLink>
            <RouterLink
              v-else
              to="/admin/dashboard"
              class="hidden md:inline-flex items-center justify-center w-9 h-9 rounded-lg transition-all duration-200"
              style="color: #d6d3d1; border: 1px solid rgba(255,255,255,0.14);"
              :aria-label="t('nav.adminDashboard')"
              :title="t('nav.adminDashboard')"
              @mouseenter="($event.currentTarget as HTMLElement).style.color='#fff'; ($event.currentTarget as HTMLElement).style.background='rgba(22,119,255,0.10)'; ($event.currentTarget as HTMLElement).style.borderColor='rgba(22,119,255,0.35)'"
              @mouseleave="($event.currentTarget as HTMLElement).style.color='#d6d3d1'; ($event.currentTarget as HTMLElement).style.background='transparent'; ($event.currentTarget as HTMLElement).style.borderColor='rgba(255,255,255,0.14)'"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 15.5A3.5 3.5 0 1 0 12 8a3.5 3.5 0 0 0 0 7.5Z" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 1 1-4 0v-.08a1.7 1.7 0 0 0-1.03-1.56 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.56-1.03H3a2 2 0 1 1 0-4h.08A1.7 1.7 0 0 0 4.64 8.94a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H9A1.7 1.7 0 0 0 10 3.08V3a2 2 0 1 1 4 0v.08a1.7 1.7 0 0 0 1.03 1.56 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87V9a1.7 1.7 0 0 0 1.56 1H21a2 2 0 1 1 0 4h-.08A1.7 1.7 0 0 0 19.4 15Z" />
              </svg>
            </RouterLink>
            <button @click="handleLogout" class="hidden md:inline-flex btn-ghost text-sm">
              {{ t('nav.logout') }}
            </button>
          </template>
          <template v-else>
            <RouterLink to="/auth/login" class="hidden md:inline-flex btn-ghost text-sm">
              {{ t('nav.login') }}
            </RouterLink>
            <RouterLink to="/auth/register" class="hidden md:inline-flex btn-primary py-2 px-4 text-sm">
              {{ t('lp.ctaPrimary') }}
            </RouterLink>
          </template>

          <!-- Mobile Menu Button -->
          <button
            @click="mobileMenuOpen = !mobileMenuOpen"
            class="md:hidden p-2 rounded-lg transition-colors"
            style="color: #d6d3d1;"
            :aria-expanded="mobileMenuOpen"
            :aria-label="t('nav.toggleMenu')"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path v-if="!mobileMenuOpen" stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
              <path v-else stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Mobile Menu -->
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="mobileMenuOpen"
        class="md:hidden border-t"
        style="background: rgba(9,9,11,0.96); backdrop-filter: blur(20px); border-color: rgba(255,255,255,0.06);"
      >
        <div class="px-4 py-4 space-y-1 max-h-[80vh] overflow-y-auto">
          <RouterLink to="/" class="dropdown-item w-full" @click="closeMobile">{{ t('nav.home') }}</RouterLink>
          <RouterLink v-if="showPublicGalleryLinks" to="/gallery" class="dropdown-item w-full" @click="closeMobile">{{ t('gallery.title') }}</RouterLink>
          <RouterLink to="/pricing" class="dropdown-item w-full" @click="closeMobile">{{ t('nav.pricing') }}</RouterLink>

          <template v-for="group in visibleToolGroups" :key="group.titleKey">
            <div class="px-3 pt-3 pb-1 text-[11px] font-bold uppercase tracking-wider text-muted">{{ t(group.titleKey) }}</div>
            <RouterLink
              v-for="item in group.items"
              :key="item.to"
              :to="item.to"
              class="dropdown-item w-full"
              @click="closeMobile"
            >
              <span>{{ item.emoji }}</span>
              <span>{{ t(item.key) }}</span>
            </RouterLink>
          </template>

          <div class="pt-3 mt-2 space-y-2 border-t" style="border-color: rgba(255,255,255,0.06);">
            <template v-if="!authStore.isAuthenticated">
              <RouterLink to="/auth/login" class="btn-secondary w-full" @click="closeMobile">{{ t('nav.login') }}</RouterLink>
              <RouterLink to="/auth/register" class="btn-primary w-full" @click="closeMobile">{{ t('lp.ctaPrimary') }}</RouterLink>
            </template>
            <template v-else>
              <RouterLink v-if="!authStore.isAdmin" to="/dashboard/my-works" class="btn-secondary w-full" @click="closeMobile">{{ t('nav.dashboard') }}</RouterLink>
              <RouterLink v-else to="/admin/dashboard" class="btn-secondary w-full" @click="closeMobile">⚙ {{ t('nav.adminDashboard') }}</RouterLink>
              <button @click="handleLogout(); closeMobile()" class="btn-ghost w-full justify-center">{{ t('nav.logout') }}</button>
            </template>
          </div>
        </div>
      </div>
    </Transition>
  </header>
</template>
