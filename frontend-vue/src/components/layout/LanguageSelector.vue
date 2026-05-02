<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore, useUIStore } from '@/stores'

const { locale } = useI18n()
const uiStore = useUIStore()
const authStore = useAuthStore()
const route = useRoute()
const isOpen = ref(false)
const isAdminSurface = computed(() => authStore.isAdmin && (route.path.startsWith('/admin') || route.path === '/dashboard'))

const languages = [
  { code: 'en', name: 'English', flag: '🇺🇸' },
  { code: 'zh-TW', name: '繁體中文', flag: '🇹🇼' },
  { code: 'ja', name: '日本語', flag: '🇯🇵' },
  { code: 'ko', name: '한국어', flag: '🇰🇷' },
  { code: 'es', name: 'Español', flag: '🇪🇸' }
]

const currentLanguage = computed(() =>
  isAdminSurface.value ? languages[1] : languages.find(l => l.code === locale.value) || languages[1]
)

function selectLanguage(code: string) {
  if (isAdminSurface.value) {
    locale.value = 'zh-TW'
    uiStore.setLocale('zh-TW')
    isOpen.value = false
    return
  }
  locale.value = code
  uiStore.setLocale(code)
  isOpen.value = false
}
</script>

<template>
  <div class="relative">
    <!-- Trigger Button -->
    <button
      @click="isAdminSurface ? selectLanguage('zh-TW') : isOpen = !isOpen"
      class="flex items-center gap-1.5 px-3 py-2 rounded-lg transition-colors text-sm font-medium"
      style="color: #d6d3d1;"
      @mouseenter="($event.target as HTMLElement).style.background='rgba(255,255,255,0.08)'"
      @mouseleave="($event.target as HTMLElement).style.background='transparent'"
    >
      <span class="text-base leading-none">{{ currentLanguage.flag }}</span>
      <span class="hidden sm:inline text-sm">{{ currentLanguage.name }}</span>
      <svg
        v-if="!isAdminSurface"
        class="w-3.5 h-3.5 transition-transform duration-200"
        :class="{ 'rotate-180': isOpen }"
        style="color: #d6d3d1;"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Dropdown -->
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 scale-95 -translate-y-1"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 -translate-y-1"
    >
      <div
        v-if="isOpen && !isAdminSurface"
        class="absolute right-0 mt-2 rounded-xl py-1.5 min-w-44 z-50 origin-top-right dropdown-menu"
      >
        <button
          v-for="lang in languages"
          :key="lang.code"
          @click="selectLanguage(lang.code)"
          class="w-full flex items-center gap-3 px-4 py-2.5 transition-colors text-sm"
          :style="lang.code === locale
            ? 'background: rgba(245,158,11,0.12); color: #fbbf24; font-weight: 600;'
            : 'color: #d6d3d1;'"
        >
          <span class="text-base leading-none">{{ lang.flag }}</span>
          <span>{{ lang.name }}</span>
          <svg
            v-if="lang.code === locale"
            class="w-4 h-4 ml-auto"
            style="color: #fbbf24;"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
          </svg>
        </button>
      </div>
    </Transition>

    <!-- Backdrop -->
    <div
      v-if="isOpen"
      class="fixed inset-0 z-40"
      @click="isOpen = false"
    />
  </div>
</template>
