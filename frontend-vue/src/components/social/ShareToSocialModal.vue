<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  buildSocialShareUrl,
  socialSharePlatforms,
  type SocialSharePlatform,
} from '@/api/socialMedia'

interface Props {
  generationId: string
  toolType: string
  isVideo: boolean
  mediaUrl?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n()

const caption = ref('')
const feedback = ref<{ type: 'success' | 'error'; message: string } | null>(null)
const nativeShareSupported = ref(false)
const nativeFileShareSupported = ref(false)
const lastOpenedPlatform = ref<string | null>(null)

// Spec requires Instagram / Facebook / TikTok / LINE / Threads to be visible
// and reachable from this modal. Pin them to the top of the platform grid so
// they're always above the fold; everything else follows in original order.
const PRIORITY_PLATFORM_IDS = ['instagram', 'facebook', 'tiktok', 'line', 'threads']
function platformSortKey(id: string): number {
  const idx = PRIORITY_PLATFORM_IDS.indexOf(id)
  return idx === -1 ? 99 : idx
}
const directSharePlatforms = computed(() =>
  socialSharePlatforms
    .filter(platform => platform.mode === 'direct_share')
    .slice()
    .sort((a, b) => platformSortKey(a.id) - platformSortKey(b.id))
)
const copyFirstPlatforms = computed(() =>
  socialSharePlatforms
    .filter(platform => platform.mode === 'copy_first')
    .slice()
    .sort((a, b) => platformSortKey(a.id) - platformSortKey(b.id))
)

// Mobile detection — used to make the OS share sheet the hero CTA. We treat
// "small viewport OR touch-primary" as mobile rather than UA sniffing, so
// it stays accurate when the user resizes a desktop window.
const isMobileViewport = ref(false)
function updateViewportFlag() {
  if (typeof window === 'undefined') return
  isMobileViewport.value =
    window.matchMedia('(max-width: 640px), (pointer: coarse)').matches
}

const workShareLink = computed(() => {
  if (props.mediaUrl) return props.mediaUrl
  if (typeof window === 'undefined') return ''
  const url = new URL('/dashboard/my-works', window.location.origin)
  url.searchParams.set('work', props.generationId)
  return url.toString()
})

function platformSupportsMedia(platform: SocialSharePlatform): boolean {
  return props.isVideo ? platform.supportsVideo : platform.supportsImage
}

function getDefaultCaption(): string {
  const toolName = props.toolType.replace(/_/g, ' ')
  return t('socialShare.defaultCaptionTool', { tool: toolName })
}

function showFeedback(type: 'success' | 'error', message: string) {
  feedback.value = { type, message }
  window.setTimeout(() => {
    feedback.value = null
  }, 3000)
}

async function copyText(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value)
    return true
  } catch {
    try {
      const textarea = document.createElement('textarea')
      textarea.value = value
      textarea.setAttribute('readonly', '')
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      return true
    } catch {
      return false
    }
  }
}

async function copyShareLink(showNotice = true): Promise<boolean> {
  const ok = await copyText(workShareLink.value)
  if (showNotice) showFeedback(ok ? 'success' : 'error', t(ok ? 'socialShare.copied' : 'socialShare.copyFailed'))
  return ok
}

async function copyCaption(showNotice = true): Promise<boolean> {
  const text = caption.value.trim() || getDefaultCaption()
  const ok = await copyText(text)
  if (showNotice) showFeedback(ok ? 'success' : 'error', t(ok ? 'socialShare.captionCopied' : 'socialShare.copyFailed'))
  return ok
}

// Fetch the work media (image/video) as a File so we can hand it to the
// Web Share API Level 2 (navigator.share({files})) on mobile, or trigger an
// auto-download as a fallback for platforms (Instagram/TikTok) that need the
// asset on the device before the user uploads it.
//
// Two-stage strategy:
//   1. Direct CORS fetch from the media URL (works for our GCS bucket which
//      sets Access-Control-Allow-Origin: *).
//   2. If that fails (provider CDN with no ACAO), fall back to our backend
//      `/api/v1/share/share-media?url=...` proxy that re-emits with CORS=*.
async function fetchMediaAsFile(): Promise<File | null> {
  if (!props.mediaUrl) return null
  const tryFetch = async (url: string): Promise<Blob | null> => {
    try {
      const resp = await fetch(url, { mode: 'cors', credentials: 'omit' })
      if (!resp.ok) return null
      return await resp.blob()
    } catch {
      return null
    }
  }
  let blob = await tryFetch(props.mediaUrl)
  if (!blob) {
    // Backend proxy fallback (handles PiAPI/Pollo/Kling CDNs without ACAO).
    const proxied = `/api/v1/share/share-media?url=${encodeURIComponent(props.mediaUrl)}`
    blob = await tryFetch(proxied)
  }
  if (!blob) return null
  const guessedExt = props.isVideo
    ? (blob.type.includes('webm') ? 'webm' : 'mp4')
    : (blob.type.includes('png') ? 'png' : blob.type.includes('webp') ? 'webp' : 'jpg')
  const filename = `vidgo-${props.toolType}-${props.generationId}.${guessedExt}`
  const mime = blob.type || (props.isVideo ? 'video/mp4' : 'image/jpeg')
  return new File([blob], filename, { type: mime })
}

function triggerDownload(file: File) {
  const url = URL.createObjectURL(file)
  const a = document.createElement('a')
  a.href = url
  a.download = file.name
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  // Revoke after a tick so the browser has time to start the download.
  window.setTimeout(() => URL.revokeObjectURL(url), 4000)
}

async function autoDownloadMedia(): Promise<boolean> {
  const file = await fetchMediaAsFile()
  if (!file) return false
  triggerDownload(file)
  return true
}

async function openPlatform(platform: SocialSharePlatform) {
  if (!platformSupportsMedia(platform)) return

  if (!caption.value.trim()) {
    caption.value = getDefaultCaption()
  }

  // copy_first (Instagram, TikTok, YouTube): these platforms cannot accept a
  // pre-filled URL/text via web intent, so the MVP fallback is to (a) copy
  // the caption to the clipboard, (b) auto-download the media to the device,
  // (c) open the platform's upload page in a new tab. The user pastes the
  // caption and uploads the just-downloaded asset.
  let copiedCaption = true
  let downloaded = false
  if (platform.mode === 'copy_first') {
    copiedCaption = await copyText(caption.value.trim() || getDefaultCaption())
    downloaded = await autoDownloadMedia()
  }

  const targetUrl = buildSocialShareUrl(platform, workShareLink.value, caption.value.trim() || getDefaultCaption())
  const opened = window.open(targetUrl, '_blank', 'noopener,noreferrer')

  if (platform.mode === 'copy_first') {
    if (downloaded && copiedCaption) {
      showFeedback('success', t('socialShare.captionAndMediaReady', { platform: platform.name }))
    } else if (copiedCaption) {
      showFeedback('success', t('socialShare.copyBeforeOpen', { platform: platform.name }))
    } else {
      showFeedback('error', t('socialShare.copyFailed'))
    }
  }

  if (!opened) {
    showFeedback('error', t('socialShare.popupBlocked'))
    return
  }
  lastOpenedPlatform.value = platform.id
}

// Used to disable the hero button while we're fetching the media blob, so
// the user doesn't double-tap and trigger two OS share sheets.
const isPreparingShare = ref(false)

// Hero CTA. Tries the share strategies in this exact order:
//   1. navigator.share({files,text,url})  — OS share sheet with the image
//      attached. iOS/Android. Lets user pick Instagram/Threads/LINE/Messages.
//   2. navigator.share({text,url})        — same sheet but URL-only.
//   3. copy caption + auto-download file  — works on any browser.
// We never throw on AbortError (the user closed the sheet voluntarily).
async function shareWithSystemDialog() {
  if (!caption.value.trim()) {
    caption.value = getDefaultCaption()
  }

  const text = caption.value.trim()
  const url = workShareLink.value
  isPreparingShare.value = true

  try {
    // Level 2: caption + file (what the spec asks for).
    if (navigator.share && navigator.canShare && props.mediaUrl) {
      const file = await fetchMediaAsFile()
      if (file) {
        try {
          const payload: ShareData = { title: 'VidGo AI', text, url, files: [file] }
          if (navigator.canShare(payload)) {
            await navigator.share(payload)
            return
          }
        } catch (error: any) {
          if (error?.name === 'AbortError') return
          // canShare returned true but share() rejected → fall through
        }
      }
    }

    // Level 1: URL + caption only (no file).
    if (navigator.share) {
      try {
        await navigator.share({ title: 'VidGo AI', text, url })
        return
      } catch (error: any) {
        if (error?.name === 'AbortError') return
      }
    }

    // Fallback: copy caption + auto-download file. Works everywhere.
    const captionCopied = await copyText(text || url)
    const downloaded = await autoDownloadMedia()
    if (downloaded && captionCopied) {
      showFeedback('success', t('socialShare.fallbackCaptionAndDownload'))
    } else if (captionCopied) {
      showFeedback('success', t('socialShare.nativeFallbackCopied'))
    } else {
      showFeedback('error', t('socialShare.copyFailed'))
    }
  } finally {
    isPreparingShare.value = false
  }
}

onMounted(() => {
  nativeShareSupported.value = typeof navigator !== 'undefined' && !!navigator.share
  // canShare({files: [...]}) requires at least one File to evaluate; treat
  // the presence of both APIs as best-effort capability.
  nativeFileShareSupported.value = nativeShareSupported.value && typeof navigator.canShare === 'function'
  updateViewportFlag()
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', updateViewportFlag)
  }
  caption.value = getDefaultCaption()
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', updateViewportFlag)
  }
})
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
      style="background: rgba(0,0,0,0.8);"
      @click.self="emit('close')"
    >
      <div
        class="w-full max-w-2xl rounded-2xl overflow-hidden max-h-[90vh] overflow-y-auto"
        style="background: #141420; border: 1px solid rgba(22,119,255,0.15);"
      >
        <div
          class="flex items-center justify-between p-6 border-b"
          style="border-color: rgba(0,184,230,0.15);"
        >
          <div>
            <div class="flex items-center gap-3 mb-1">
              <span class="text-2xl">↗</span>
              <h2 class="text-xl font-bold" style="color: #e8f4ff;">{{ t('socialShare.title') }}</h2>
            </div>
            <p class="text-sm" style="color: #6b9ab8;">{{ t('socialShare.subtitle') }}</p>
          </div>
          <button
            @click="emit('close')"
            class="w-8 h-8 rounded-full flex items-center justify-center transition-colors"
            style="color: #6b9ab8;"
            @mouseover="($event.target as HTMLElement).style.background = 'rgba(255,255,255,0.1)'"
            @mouseleave="($event.target as HTMLElement).style.background = 'transparent'"
          >
            ×
          </button>
        </div>

        <div class="p-6 space-y-6">
          <transition name="fade">
            <div
              v-if="feedback"
              class="rounded-xl p-3 border flex items-center gap-3"
              :style="{
                background: feedback.type === 'success' ? 'rgba(0,200,100,0.1)' : 'rgba(255,50,50,0.1)',
                borderColor: feedback.type === 'success' ? 'rgba(0,200,100,0.3)' : 'rgba(255,50,50,0.3)',
              }"
            >
              <span>{{ feedback.type === 'success' ? '✓' : '!' }}</span>
              <p
                class="text-sm font-medium"
                :style="{ color: feedback.type === 'success' ? '#00c864' : '#ff6b6b' }"
              >
                {{ feedback.message }}
              </p>
            </div>
          </transition>

          <div>
            <label class="block text-sm font-medium mb-2" style="color: #a8c8e8;">
              {{ t('socialShare.workLink') }}
            </label>
            <div class="flex gap-2">
              <input
                :value="workShareLink"
                readonly
                class="flex-1 min-w-0 rounded-xl px-4 py-3 text-sm outline-none"
                style="background: rgba(255,255,255,0.05); border: 1px solid rgba(22,119,255,0.15); color: #e8f4ff;"
              />
              <button
                type="button"
                @click="copyShareLink()"
                class="px-4 py-3 rounded-xl text-sm font-medium whitespace-nowrap"
                style="background: rgba(0,184,230,0.1); color: #00b8e6; border: 1px solid rgba(0,184,230,0.3);"
              >
                {{ t('socialShare.copyLink') }}
              </button>
            </div>
          </div>

          <div>
            <div class="flex items-center justify-between mb-2">
              <label class="block text-sm font-medium" style="color: #a8c8e8;">
                {{ t('socialShare.caption') }}
              </label>
              <button
                type="button"
                @click="copyCaption()"
                class="text-xs px-2 py-1 rounded-md"
                style="background: rgba(0,184,230,0.1); color: #00b8e6; border: 1px solid rgba(0,184,230,0.3);"
              >
                {{ t('socialShare.copyCaption') }}
              </button>
            </div>
            <textarea
              v-model="caption"
              rows="3"
              :placeholder="t('socialShare.captionPlaceholder')"
              class="w-full rounded-xl px-4 py-3 text-sm resize-none outline-none transition-all"
              style="background: rgba(255,255,255,0.05); border: 1px solid rgba(22,119,255,0.15); color: #e8f4ff;"
              @focus="($event.target as HTMLElement).style.borderColor = 'rgba(0,184,230,0.5)'"
              @blur="($event.target as HTMLElement).style.borderColor = 'rgba(0,184,230,0.2)'"
            ></textarea>
            <p class="text-xs mt-1 text-right" style="color: #4a7bb5;">
              {{ t('socialShare.charCount', { count: caption.length }) }}
            </p>
          </div>

          <!-- Hero CTA. On mobile, this is the OS share sheet (Web Share API
               Level 2) which lets the user pick Instagram / Threads / LINE /
               Messages with the actual media file attached. On desktop or
               unsupported browsers, it copies the caption and auto-downloads
               the file. Spec: navigator.share() preferred → fallback chain. -->
          <button
            type="button"
            @click="shareWithSystemDialog"
            :disabled="isPreparingShare"
            class="w-full py-4 rounded-xl font-bold text-sm sm:text-base transition-all disabled:opacity-50 disabled:cursor-wait flex items-center justify-center gap-2"
            style="background: linear-gradient(135deg, #00b8e6, #0066cc); color: white; box-shadow: 0 4px 18px rgba(0,184,230,0.25);"
          >
            <span v-if="isPreparingShare" class="inline-block w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin"></span>
            <span v-else>{{ nativeFileShareSupported && props.mediaUrl
              ? t('socialShare.nativeShareWithImage')
              : nativeShareSupported
                ? t('socialShare.nativeShare')
                : t('socialShare.copyForAnyApp') }}</span>
          </button>
          <p v-if="isMobileViewport && nativeFileShareSupported" class="text-[11px] -mt-3" style="color: #6b9ab8;">
            {{ t('socialShare.mobileShareHint') }}
          </p>
          <p v-else-if="!nativeShareSupported" class="text-[11px] -mt-3" style="color: #6b9ab8;">
            {{ t('socialShare.desktopFallbackHint') }}
          </p>

          <!-- Secondary "just download" button — useful when the user wants
               the file on disk without engaging the share sheet. -->
          <button
            v-if="props.mediaUrl"
            type="button"
            @click="autoDownloadMedia().then(ok => showFeedback(ok ? 'success' : 'error', t(ok ? 'socialShare.mediaDownloaded' : 'socialShare.copyFailed')))"
            class="w-full py-2.5 rounded-xl font-medium text-sm transition-all"
            style="background: rgba(255,255,255,0.06); color: #e8f4ff; border: 1px solid rgba(255,255,255,0.12);"
          >
            ⬇ {{ props.isVideo ? t('socialShare.downloadVideo') : t('socialShare.downloadImage') }}
          </button>

          <div>
            <h3 class="text-sm font-semibold mb-3" style="color: #a8c8e8;">
              {{ t('socialShare.directPlatforms') }}
            </h3>
            <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <button
                v-for="platform in directSharePlatforms"
                :key="platform.id"
                type="button"
                @click="openPlatform(platform)"
                class="rounded-xl p-3 text-left border transition-all"
                :style="{
                  background: lastOpenedPlatform === platform.id ? 'rgba(0,184,230,0.12)' : 'rgba(255,255,255,0.03)',
                  borderColor: lastOpenedPlatform === platform.id ? 'rgba(0,184,230,0.45)' : 'rgba(255,255,255,0.08)',
                }"
              >
                <span
                  class="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold mb-2"
                  :style="{ background: `${platform.color}22`, color: platform.color }"
                >
                  {{ platform.icon }}
                </span>
                <span class="block text-sm font-medium" style="color: #e8f4ff;">{{ platform.name }}</span>
                <span class="text-xs" style="color: #6b9ab8;">{{ t('socialShare.openShare') }}</span>
              </button>
            </div>
          </div>

          <div>
            <h3 class="text-sm font-semibold mb-3" style="color: #a8c8e8;">
              {{ t('socialShare.copyFirstPlatforms') }}
            </h3>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <button
                v-for="platform in copyFirstPlatforms"
                :key="platform.id"
                type="button"
                @click="openPlatform(platform)"
                :disabled="!platformSupportsMedia(platform)"
                class="rounded-xl p-3 text-left border transition-all disabled:opacity-45 disabled:cursor-not-allowed"
                :style="{
                  background: lastOpenedPlatform === platform.id ? 'rgba(0,184,230,0.12)' : 'rgba(255,255,255,0.03)',
                  borderColor: lastOpenedPlatform === platform.id ? 'rgba(0,184,230,0.45)' : 'rgba(255,255,255,0.08)',
                }"
              >
                <span
                  class="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold mb-2"
                  :style="{ background: `${platform.color}22`, color: platform.color }"
                >
                  {{ platform.icon }}
                </span>
                <span class="block text-sm font-medium" style="color: #e8f4ff;">{{ platform.name }}</span>
                <span v-if="platformSupportsMedia(platform)" class="text-xs" style="color: #6b9ab8;">
                  {{ t('socialShare.openPlatform') }}
                </span>
                <span v-else class="text-xs" style="color: #ff8c80;">
                  {{ props.isVideo ? t('socialShare.videoUnsupported') : t('socialShare.imageUnsupported') }}
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
