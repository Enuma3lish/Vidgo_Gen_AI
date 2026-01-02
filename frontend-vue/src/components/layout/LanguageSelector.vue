<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore } from '@/stores'

const { locale } = useI18n()
const uiStore = useUIStore()

const isOpen = ref(false)

const languages = [
  { code: 'en', name: 'English', flag: '🇺🇸' },
  { code: 'zh-TW', name: '繁體中文', flag: '🇹🇼' },
  { code: 'ja', name: '日本語', flag: '🇯🇵' },
  { code: 'ko', name: '한국어', flag: '🇰🇷' },
  { code: 'es', name: 'Español', flag: '🇪🇸' }
]

const currentLanguage = () => languages.find(l => l.code === locale.value) || languages[1]

function selectLanguage(code: string) {
  locale.value = code
  uiStore.setLocale(code)
  isOpen.value = false
}
</script>

<template>
  <div class="relative">
    <button
      @click="isOpen = !isOpen"
      class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-dark-700 transition-colors"
    >
      <span class="text-lg">{{ currentLanguage().flag }}</span>
      <span class="hidden sm:inline text-sm text-gray-300">{{ currentLanguage().name }}</span>
      <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Dropdown -->
    <div
      v-if="isOpen"
      class="absolute right-0 mt-2 bg-dark-800 border border-dark-700 rounded-xl py-2 min-w-40 shadow-xl z-50"
    >
      <button
        v-for="lang in languages"
        :key="lang.code"
        @click="selectLanguage(lang.code)"
        class="w-full flex items-center gap-3 px-4 py-2 hover:bg-dark-700 transition-colors"
        :class="{ 'bg-dark-700': lang.code === locale }"
      >
        <span class="text-lg">{{ lang.flag }}</span>
        <span class="text-sm">{{ lang.name }}</span>
      </button>
    </div>

    <!-- Backdrop -->
    <div
      v-if="isOpen"
      class="fixed inset-0 z-40"
      @click="isOpen = false"
    />
  </div>
</template>
