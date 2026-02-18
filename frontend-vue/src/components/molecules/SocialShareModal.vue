<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  visible: boolean
  contentUrl: string
  contentType?: 'image' | 'video'
}>()

const emit = defineEmits<{
  close: []
}>()

const copied = ref(false)

interface Platform {
  id: string
  name: string
  icon: string
  color: string
}

const platforms: Platform[] = [
  { id: 'facebook', name: 'Facebook', icon: 'f', color: '#1877F2' },
  { id: 'twitter', name: 'X / Twitter', icon: '𝕏', color: '#000000' },
  { id: 'line', name: 'LINE', icon: 'L', color: '#06C755' },
  { id: 'tiktok', name: 'TikTok', icon: '♪', color: '#000000' },
  { id: 'instagram', name: 'Instagram', icon: '📷', color: '#E4405F' },
]

const shareTemplates: Record<string, string | null> = {
  facebook: 'https://www.facebook.com/sharer/sharer.php?u={url}',
  twitter: 'https://twitter.com/intent/tweet?url={url}&text={text}',
  line: 'https://social-plugins.line.me/lineit/share?url={url}',
  tiktok: 'https://www.tiktok.com/upload?url={url}',
  instagram: null,
}

function shareTo(platformId: string) {
  const template = shareTemplates[platformId]
  const encodedUrl = encodeURIComponent(props.contentUrl)
  const encodedText = encodeURIComponent('Check out what I created with VidGo AI!')

  if (!template) {
    // Instagram doesn't support web share - copy link
    copyLink()
    return
  }

  const shareUrl = template
    .replace('{url}', encodedUrl)
    .replace('{text}', encodedText)

  window.open(shareUrl, '_blank', 'width=600,height=400')
}

async function copyLink() {
  try {
    await navigator.clipboard.writeText(props.contentUrl)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // Fallback for older browsers
    const input = document.createElement('input')
    input.value = props.contentUrl
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    document.body.removeChild(input)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
      @click.self="emit('close')"
    >
      <div class="absolute inset-0 bg-dark-900/80 backdrop-blur-sm" @click="emit('close')" />

      <div class="relative bg-dark-800 rounded-2xl max-w-sm w-full p-6">
        <!-- Close -->
        <button
          @click="emit('close')"
          class="absolute top-4 right-4 w-8 h-8 flex items-center justify-center text-gray-400 hover:text-white rounded-full hover:bg-dark-700"
        >
          ✕
        </button>

        <!-- Title -->
        <h3 class="text-lg font-semibold text-white mb-1">Share to Social Media</h3>
        <p class="text-sm text-gray-400 mb-6">Share your creation with the world</p>

        <!-- Platform Grid -->
        <div class="grid grid-cols-5 gap-3 mb-6">
          <button
            v-for="platform in platforms"
            :key="platform.id"
            @click="shareTo(platform.id)"
            class="flex flex-col items-center gap-1.5 p-3 rounded-xl hover:bg-dark-700 transition-colors group"
          >
            <div
              class="w-10 h-10 rounded-full flex items-center justify-center text-white text-lg font-bold"
              :style="{ backgroundColor: platform.color }"
            >
              {{ platform.icon }}
            </div>
            <span class="text-xs text-gray-400 group-hover:text-white transition-colors">
              {{ platform.name }}
            </span>
          </button>
        </div>

        <!-- Copy Link -->
        <button
          @click="copyLink"
          class="w-full flex items-center justify-center gap-2 px-4 py-3 bg-dark-700 hover:bg-dark-600 text-white rounded-xl transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
          </svg>
          {{ copied ? 'Copied!' : 'Copy Link' }}
        </button>
      </div>
    </div>
  </Teleport>
</template>
