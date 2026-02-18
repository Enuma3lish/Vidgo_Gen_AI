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
      class="md:hidden bg-dark-800 border-t border-dark-700"
    >
      <div class="px-4 py-4 space-y-2">
        <RouterLink
          to="/"
          class="block px-4 py-2 rounded-lg hover:bg-dark-700 text-white"
          @click="mobileMenuOpen = false"
        >
          {{ t('nav.home') }}
        </RouterLink>

        <!-- Auth links for mobile -->
        <div v-if="!authStore.isAuthenticated" class="pt-2 border-t border-dark-700 space-y-2">
          <RouterLink
            to="/auth/login"
            class="block px-4 py-2 rounded-lg hover:bg-dark-700 text-gray-300"
            @click="mobileMenuOpen = false"
          >
            {{ t('nav.login') }}
          </RouterLink>
          <RouterLink
            to="/auth/register"
            class="block px-4 py-2 rounded-lg bg-primary-500 text-white text-center"
            @click="mobileMenuOpen = false"
          >
            {{ t('nav.register') }}
          </RouterLink>
        </div>
      </div>
    </div>
  </header>
</template>
