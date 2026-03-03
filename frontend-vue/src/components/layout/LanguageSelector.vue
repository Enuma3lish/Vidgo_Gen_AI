<script setup lang="ts">
import { ref, computed } from 'vue'
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

const currentLanguage = computed(() =>
  languages.find(l => l.code === locale.value) || languages[1]
)

function selectLanguage(code: string) {
  locale.value = code
  uiStore.setLocale(code)
  isOpen.value = false
}
</script>

<template>
  <div class="relative">
    <!-- Trigger Button - Light theme -->
    <button
      @click="isOpen = !isOpen"
      class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-dark-700 hover:bg-black/5 transition-colors text-sm font-medium"
    >
      <span class="text-base leading-none">{{ currentLanguage.flag }}</span>
      <span class="hidden sm:inline text-sm text-dark-600">{{ currentLanguage.name }}</span>
      <svg
        class="w-3.5 h-3.5 text-dark-400 transition-transform duration-200"
        :class="{ 'rotate-180': isOpen }"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Dropdown - Light theme -->
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 scale-95 -translate-y-1"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 -translate-y-1"
    >
      <div
        v-if="isOpen"
        class="absolute right-0 mt-2 bg-white border border-black/8 rounded-2xl py-1.5 min-w-44 shadow-xl z-50 origin-top-right"
      >
        <button
          v-for="lang in languages"
          :key="lang.code"
          @click="selectLanguage(lang.code)"
          class="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 transition-colors text-dark-700"
          :class="lang.code === locale ? 'bg-lime-50 text-dark-900 font-semibold' : ''"
        >
          <span class="text-base leading-none">{{ lang.flag }}</span>
          <span class="text-sm">{{ lang.name }}</span>
          <svg
            v-if="lang.code === locale"
            class="w-4 h-4 ml-auto text-lime-600"
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
