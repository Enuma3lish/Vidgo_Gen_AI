<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores'
import LanguageSelector from './LanguageSelector.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const isScrolled = ref(false)
const mobileMenuOpen = ref(false)

function handleScroll() {
  isScrolled.value = window.scrollY > 20
}

function handleLogout() {
  authStore.logout()
  router.push('/')
}

onMounted(() => {
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
        ? 'bg-dark-900/95 backdrop-blur-lg border-b border-dark-700'
        : 'bg-dark-900/80 backdrop-blur-sm'
    ]"
  >
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-14">
        <!-- Logo -->
        <RouterLink to="/" class="flex items-center gap-2">
          <span class="text-2xl">🎬</span>
          <span class="text-xl font-bold gradient-text">VidGo</span>
        </RouterLink>

        <!-- Center: Home only -->
        <nav class="hidden md:flex items-center">
          <RouterLink to="/" class="px-4 py-2 text-gray-300 hover:text-white transition-colors">
            {{ t('nav.home') }}
          </RouterLink>
        </nav>

        <!-- Right Side: Language + Auth -->
        <div class="flex items-center gap-3">
          <LanguageSelector />

          <template v-if="authStore.isAuthenticated">
            <RouterLink to="/dashboard" class="px-3 py-1.5 text-sm text-gray-300 hover:text-white transition-colors">
              {{ t('nav.dashboard') }}
            </RouterLink>
            <button @click="handleLogout" class="px-3 py-1.5 text-sm text-gray-400 hover:text-white transition-colors">
              {{ t('nav.logout') }}
            </button>
          </template>
          <template v-else>
            <RouterLink to="/auth/login" class="px-3 py-1.5 text-sm text-gray-300 hover:text-white transition-colors">
              {{ t('nav.login') }}
            </RouterLink>
            <RouterLink to="/auth/register" class="px-4 py-1.5 text-sm bg-primary-500 hover:bg-primary-600 text-white rounded-lg transition-colors">
              {{ t('nav.register') }}
            </RouterLink>
          </template>

          <!-- Mobile Menu Button -->
          <button
            @click="mobileMenuOpen = !mobileMenuOpen"
            class="md:hidden p-2 text-gray-400 hover:text-white"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                v-if="!mobileMenuOpen"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M4 6h16M4 12h16M4 18h16"
              />
              <path
                v-else
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Mobile Menu -->
    <div
      v-if="mobileMenuOpen"
      class="md:hidden bg-dark-800 border-t border-dark-700 max-h-[calc(100vh-3.5rem)] overflow-y-auto"
    >
      <div class="px-4 py-4 space-y-1">
        <!-- Home -->
        <RouterLink
          to="/"
          class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-white font-medium"
          @click="mobileMenuOpen = false"
        >
          {{ t('nav.home') }}
        </RouterLink>

        <!-- Authenticated user: dashboard links -->
        <template v-if="authStore.isAuthenticated">
          <div class="pt-3 mt-2 border-t border-dark-700">
            <p class="px-4 pb-1 text-xs font-semibold text-gray-500 uppercase tracking-wider">Account</p>
            <div class="space-y-1">
              <RouterLink
                to="/dashboard"
                class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-gray-300"
                @click="mobileMenuOpen = false"
              >
                {{ t('nav.dashboard') }}
              </RouterLink>
              <RouterLink
                to="/dashboard/my-works"
                class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-gray-300"
                @click="mobileMenuOpen = false"
              >
                {{ t('nav.myWorks') }}
              </RouterLink>
            </div>
          </div>
        </template>

        <!-- AI Image Tools -->
        <div class="pt-3 mt-2 border-t border-dark-700">
          <p class="px-4 pb-1 text-xs font-semibold text-gray-500 uppercase tracking-wider">AI Image</p>
          <div class="space-y-1">
            <RouterLink
              to="/tools/background-removal"
              class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-gray-300"
              @click="mobileMenuOpen = false"
            >
              Background Removal
            </RouterLink>
            <RouterLink
              to="/tools/product-scene"
              class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-gray-300"
              @click="mobileMenuOpen = false"
            >
              Product Scene
            </RouterLink>
            <RouterLink
              to="/tools/try-on"
              class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-gray-300"
              @click="mobileMenuOpen = false"
            >
              Virtual Try-On
            </RouterLink>
            <RouterLink
              to="/tools/effects"
              class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-gray-300"
              @click="mobileMenuOpen = false"
            >
              Style Effects
            </RouterLink>
            <RouterLink
              to="/tools/pattern-generate"
              class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-gray-300"
              @click="mobileMenuOpen = false"
            >
              Pattern Design
            </RouterLink>
          </div>
        </div>

        <!-- Video Tools -->
        <div class="pt-3 mt-2 border-t border-dark-700">
          <p class="px-4 pb-1 text-xs font-semibold text-gray-500 uppercase tracking-wider">Video</p>
          <div class="space-y-1">
            <RouterLink
              to="/tools/short-video"
              class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-gray-300"
              @click="mobileMenuOpen = false"
            >
              Short Video
            </RouterLink>
            <RouterLink
              to="/tools/image-to-video"
              class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-gray-300"
              @click="mobileMenuOpen = false"
            >
              Image to Video
            </RouterLink>
            <RouterLink
              to="/tools/avatar"
              class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-gray-300"
              @click="mobileMenuOpen = false"
            >
              AI Avatar
            </RouterLink>
          </div>
        </div>

        <!-- Interior Tools -->
        <div class="pt-3 mt-2 border-t border-dark-700">
          <p class="px-4 pb-1 text-xs font-semibold text-gray-500 uppercase tracking-wider">Interior</p>
          <div class="space-y-1">
            <RouterLink
              to="/tools/room-redesign"
              class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-gray-300"
              @click="mobileMenuOpen = false"
            >
              Room Redesign
            </RouterLink>
          </div>
        </div>

        <!-- Pricing -->
        <div class="pt-3 mt-2 border-t border-dark-700">
          <RouterLink
            to="/pricing"
            class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-white font-medium"
            @click="mobileMenuOpen = false"
          >
            Pricing
          </RouterLink>
        </div>

        <!-- Authenticated: Admin + Logout -->
        <template v-if="authStore.isAuthenticated">
          <!-- Admin link -->
          <div v-if="authStore.isAdmin" class="pt-3 mt-2 border-t border-dark-700">
            <RouterLink
              to="/admin"
              class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-orange-400 font-medium"
              @click="mobileMenuOpen = false"
            >
              Admin Panel
            </RouterLink>
          </div>

          <!-- Logout -->
          <div class="pt-3 mt-2 border-t border-dark-700">
            <button
              @click="handleLogout(); mobileMenuOpen = false"
              class="block w-full text-left px-4 py-2.5 rounded-lg hover:bg-dark-700 text-red-400"
            >
              {{ t('nav.logout') }}
            </button>
          </div>
        </template>

        <!-- Not authenticated: login/register -->
        <div v-if="!authStore.isAuthenticated" class="pt-3 mt-2 border-t border-dark-700 space-y-2 pb-2">
          <RouterLink
            to="/auth/login"
            class="block px-4 py-2.5 rounded-lg hover:bg-dark-700 text-gray-300"
            @click="mobileMenuOpen = false"
          >
            {{ t('nav.login') }}
          </RouterLink>
          <RouterLink
            to="/auth/register"
            class="block px-4 py-2.5 rounded-lg bg-primary-500 text-white text-center font-medium"
            @click="mobileMenuOpen = false"
          >
            {{ t('nav.register') }}
          </RouterLink>
        </div>
      </div>
    </div>
  </header>
</template>
