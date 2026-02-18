<script setup lang="ts">
import { ref, onMounted } from 'vue'
import apiClient from '@/api/client'

interface Announcement {
  model_id: string
  model_name: string
  model_name_zh: string
  message: string
  message_zh: string
  tier: string
  announced_at: string
}

const announcements = ref<Announcement[]>([])
const dismissed = ref(false)
const isZh = ref(document.documentElement.lang?.startsWith('zh') || false)

onMounted(async () => {
  // Check if user already dismissed recent announcements
  const lastDismissed = localStorage.getItem('vidgo_model_banner_dismissed')
  if (lastDismissed) {
    const dismissedAt = new Date(lastDismissed)
    const hoursSince = (Date.now() - dismissedAt.getTime()) / (1000 * 60 * 60)
    if (hoursSince < 24) {
      dismissed.value = true
      return
    }
  }

  try {
    const { data } = await apiClient.get('/api/v1/models/new?days=7')
    announcements.value = data.announcements || []
  } catch {
    // Silently fail - banner is non-critical
  }
})

function dismiss() {
  dismissed.value = true
  localStorage.setItem('vidgo_model_banner_dismissed', new Date().toISOString())
}
</script>

<template>
  <div
    v-if="announcements.length > 0 && !dismissed"
    class="bg-gradient-to-r from-primary-600 to-purple-600 text-white py-2 px-4"
  >
    <div class="max-w-7xl mx-auto flex items-center justify-between gap-4">
      <div class="flex items-center gap-2 text-sm">
        <span class="font-bold whitespace-nowrap">NEW</span>
        <span>
          {{ isZh ? announcements[0].message_zh : announcements[0].message }}
        </span>
        <span
          v-if="announcements[0].tier === 'paid'"
          class="bg-white/20 px-2 py-0.5 rounded text-xs"
        >
          {{ isZh ? 'Pro 專屬' : 'Pro Only' }}
        </span>
      </div>
      <button
        @click="dismiss"
        class="text-white/80 hover:text-white shrink-0"
        aria-label="Dismiss"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  </div>
</template>
