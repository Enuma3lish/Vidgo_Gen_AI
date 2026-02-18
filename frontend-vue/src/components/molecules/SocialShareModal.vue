<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  visible: boolean
  contentUrl: string
  contentType?: 'image' | 'video'
}

const props = withDefaults(defineProps<Props>(), {
  contentType: 'image'
})

const emit = defineEmits<{
  close: []
}>()

const copied = ref(false)

interface PlatformInfo {
  id: string
  name: string
  color: string
  action: 'open_url' | 'copy_link'
  buildUrl: (url: string) => string | null
}

const platforms: PlatformInfo[] = [
  {
    id: 'facebook',
    name: 'Facebook',
    color: '#1877F2',
    action: 'open_url',
    buildUrl: (url: string) =>
      `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`
  },
  {
    id: 'twitter',
    name: 'X / Twitter',
    color: '#000000',
    action: 'open_url',
    buildUrl: (url: string) =>
      `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent('Check out what I created with VidGo AI!')}`
  },
  {
    id: 'line',
    name: 'LINE',
    color: '#06C755',
    action: 'open_url',
    buildUrl: (url: string) =>
      `https://social-plugins.line.me/lineit/share?url=${encodeURIComponent(url)}`
  },
  {
    id: 'tiktok',
    name: 'TikTok',
    color: '#000000',
    action: 'open_url',
    buildUrl: (url: string) =>
      `https://www.tiktok.com/upload?url=${encodeURIComponent(url)}`
  },
  {
    id: 'instagram',
    name: 'Instagram',
    color: '#E4405F',
    action: 'copy_link',
    buildUrl: () => null
  }
]

function handlePlatformClick(platform: PlatformInfo) {
  if (platform.action === 'copy_link') {
    copyToClipboard()
    return
  }
  const shareUrl = platform.buildUrl(props.contentUrl)
  if (shareUrl) {
    window.open(shareUrl, '_blank', 'noopener,noreferrer')
  }
}

async function copyToClipboard() {
  try {
    await navigator.clipboard.writeText(props.contentUrl)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    // Fallback for older browsers
    const textarea = document.createElement('textarea')
    textarea.value = props.contentUrl
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="visible"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @click.self="$emit('close')"
      >
        <!-- Backdrop -->
        <div
          class="absolute inset-0 bg-dark-900/80 backdrop-blur-sm"
          @click="$emit('close')"
        />

        <!-- Modal -->
        <div class="relative bg-dark-800 rounded-2xl max-w-sm w-full p-6 shadow-glow-sm">
          <!-- Close button -->
          <button
            class="absolute top-4 right-4 text-text-muted hover:text-white transition-colors"
            @click="$emit('close')"
          >
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>

          <!-- Header -->
          <h3 class="text-lg font-semibold text-white mb-1">Share to Social Media</h3>
          <p class="text-sm text-text-secondary mb-6">
            Share your {{ contentType === 'video' ? 'video' : 'image' }} to your favorite platform
          </p>

          <!-- Platform grid -->
          <div class="grid grid-cols-5 gap-3 mb-6">
            <button
              v-for="platform in platforms"
              :key="platform.id"
              class="flex flex-col items-center gap-1.5 group"
              @click="handlePlatformClick(platform)"
            >
              <!-- Icon circle -->
              <div
                class="w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200 group-hover:scale-110 group-hover:shadow-lg"
                :style="{ backgroundColor: platform.color }"
              >
                <!-- Facebook -->
                <svg v-if="platform.id === 'facebook'" class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                </svg>
                <!-- Twitter/X -->
                <svg v-else-if="platform.id === 'twitter'" class="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                </svg>
                <!-- LINE -->
                <svg v-else-if="platform.id === 'line'" class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19.365 9.863c.349 0 .63.285.63.631 0 .345-.281.63-.63.63H17.61v1.125h1.755c.349 0 .63.283.63.63 0 .344-.281.629-.63.629h-2.386c-.345 0-.627-.285-.627-.629V8.108c0-.345.282-.63.63-.63h2.386c.346 0 .627.285.627.63 0 .349-.281.63-.63.63H17.61v1.125h1.755zm-3.855 3.016c0 .27-.174.51-.432.596-.064.021-.133.031-.199.031-.211 0-.391-.09-.51-.25l-2.443-3.317v2.94c0 .344-.279.629-.631.629-.346 0-.626-.285-.626-.629V8.108c0-.27.173-.51.43-.595.06-.023.136-.033.194-.033.195 0 .375.104.495.254l2.462 3.33V8.108c0-.345.282-.63.63-.63.345 0 .63.285.63.63v4.771zm-5.741 0c0 .344-.282.629-.631.629-.345 0-.627-.285-.627-.629V8.108c0-.345.282-.63.63-.63.346 0 .628.285.628.63v4.771zm-2.466.629H4.917c-.345 0-.63-.285-.63-.629V8.108c0-.345.285-.63.63-.63.348 0 .63.285.63.63v4.141h1.756c.348 0 .629.283.629.63 0 .344-.282.629-.629.629M24 10.314C24 4.943 18.615.572 12 .572S0 4.943 0 10.314c0 4.811 4.27 8.842 10.035 9.608.391.082.923.258 1.058.59.12.301.079.766.038 1.08l-.164 1.02c-.045.301-.24 1.186 1.049.645 1.291-.539 6.916-4.078 9.436-6.975C23.176 14.393 24 12.458 24 10.314"/>
                </svg>
                <!-- TikTok -->
                <svg v-else-if="platform.id === 'tiktok'" class="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/>
                </svg>
                <!-- Instagram -->
                <svg v-else-if="platform.id === 'instagram'" class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>
                </svg>
              </div>
              <!-- Label -->
              <span class="text-xs text-text-secondary group-hover:text-white transition-colors text-center leading-tight">
                {{ platform.name }}
              </span>
            </button>
          </div>

          <!-- Divider -->
          <div class="border-t border-dark-700 mb-4" />

          <!-- Copy link section -->
          <div class="flex items-center gap-2">
            <div class="flex-1 bg-dark-950 rounded-lg px-3 py-2 text-sm text-text-secondary truncate">
              {{ contentUrl }}
            </div>
            <button
              class="shrink-0 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200"
              :class="copied
                ? 'bg-accent-green text-white'
                : 'bg-primary-600 hover:bg-primary-500 text-white'"
              @click="copyToClipboard"
            >
              {{ copied ? 'Copied!' : 'Copy Link' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: all 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .relative,
.modal-leave-to .relative {
  transform: scale(0.95) translateY(10px);
}
</style>
