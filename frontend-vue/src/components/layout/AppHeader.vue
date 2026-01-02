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

// 3 Main Topics
const topics = [
  { key: 'pattern', icon: '🎨', route: '/topics/pattern' },
  { key: 'product', icon: '🛍️', route: '/topics/product' },
  { key: 'video', icon: '🎬', route: '/topics/video' }
]

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
        : 'bg-transparent'
    ]"
  >
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <!-- Logo -->
        <RouterLink to="/" class="flex items-center gap-2">
          <span class="text-2xl">🎨</span>
          <span class="text-xl font-bold gradient-text">{{ t('app.name') }}</span>
        </RouterLink>

        <!-- Desktop Navigation -->
        <nav class="hidden md:flex items-center gap-6">
          <RouterLink to="/" class="btn-ghost">{{ t('nav.home') }}</RouterLink>

          <!-- Topics Dropdown -->
          <div class="relative group">
            <button class="btn-ghost flex items-center gap-1">
              {{ t('categories.aiCreate') }}
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            <div class="absolute top-full left-0 pt-2 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200">
              <div class="bg-dark-800 border border-dark-700 rounded-xl py-2 min-w-56 shadow-xl">
                <RouterLink
                  v-for="topic in topics"
                  :key="topic.key"
                  :to="topic.route"
                  class="flex items-center gap-3 px-4 py-3 hover:bg-dark-700 transition-colors"
                >
                  <span class="text-xl">{{ topic.icon }}</span>
                  <div>
                    <div class="text-white font-medium">{{ t(`topics.${topic.key}.name`) }}</div>
                    <div class="text-xs text-gray-500">{{ t(`topics.${topic.key}.desc`) }}</div>
                  </div>
                </RouterLink>
              </div>
            </div>
          </div>

          <RouterLink to="/pricing" class="btn-ghost">{{ t('nav.pricing') }}</RouterLink>
        </nav>

        <!-- Right Side -->
        <div class="flex items-center gap-4">
          <LanguageSelector />

          <template v-if="authStore.isAuthenticated">
            <RouterLink to="/dashboard" class="btn-ghost hidden md:flex">
              {{ t('nav.dashboard') }}
            </RouterLink>
            <button @click="handleLogout" class="btn-secondary">
              {{ t('nav.logout') }}
            </button>
          </template>
          <template v-else>
            <RouterLink to="/auth/login" class="btn-ghost hidden md:flex">
              {{ t('nav.login') }}
            </RouterLink>
            <RouterLink to="/auth/register" class="btn-primary">
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
          class="block px-4 py-2 rounded-lg hover:bg-dark-700"
          @click="mobileMenuOpen = false"
        >
          {{ t('nav.home') }}
        </RouterLink>

        <!-- Topic Links -->
        <div class="pt-2 border-t border-dark-700">
          <div class="px-4 py-2 text-xs text-gray-500 uppercase tracking-wider">
            {{ t('categories.aiCreate') }}
          </div>
          <RouterLink
            v-for="topic in topics"
            :key="topic.key"
            :to="topic.route"
            class="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-dark-700"
            @click="mobileMenuOpen = false"
          >
            <span class="text-xl">{{ topic.icon }}</span>
            <span class="text-white">{{ t(`topics.${topic.key}.name`) }}</span>
          </RouterLink>
        </div>

        <RouterLink
          to="/pricing"
          class="block px-4 py-2 rounded-lg hover:bg-dark-700"
          @click="mobileMenuOpen = false"
        >
          {{ t('nav.pricing') }}
        </RouterLink>

        <!-- Auth links for mobile -->
        <div v-if="!authStore.isAuthenticated" class="pt-2 border-t border-dark-700">
          <RouterLink
            to="/auth/login"
            class="block px-4 py-2 rounded-lg hover:bg-dark-700"
            @click="mobileMenuOpen = false"
          >
            {{ t('nav.login') }}
          </RouterLink>
        </div>
      </div>
    </div>
  </header>
</template>
