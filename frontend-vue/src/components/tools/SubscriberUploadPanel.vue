<!--
  SubscriberUploadPanel
  ─────────────────────
  Drop-in panel for subscriber custom upload + real-API generation.
  Shows a "Subscribe to unlock" gate when user is not a subscriber.

  Props:
    toolType    – e.g. "background_removal", "short_video"
    isSubscribed – computed from auth store

  Emits:
    result({ result_url, result_video_url, upload_id }) when generation completes
-->
<template>
  <div>
    <!-- Subscriber gate -->
    <div
      v-if="!isSubscribed"
      class="relative rounded-2xl border border-dashed border-indigo-600/40 bg-slate-800/50 p-8 text-center select-none overflow-hidden"
    >
      <!-- blurred placeholder -->
      <div class="absolute inset-0 pointer-events-none opacity-20 bg-gradient-to-br from-indigo-900 to-purple-900 rounded-2xl" />
      <div class="relative z-10 space-y-3">
        <div class="text-5xl">🔒</div>
        <h3 class="text-lg font-semibold text-white">{{ $t('upload.gate.title') }}</h3>
        <p class="text-slate-400 text-sm max-w-xs mx-auto">{{ $t('upload.gate.description') }}</p>
        <router-link
          to="/pricing"
          class="inline-block mt-2 px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          {{ $t('upload.gate.cta') }}
        </router-link>
      </div>
    </div>

    <!-- Subscriber upload UI -->
    <div v-else class="space-y-4">
      <LoadingOverlay
        :show="isLoading && !resultUrl && !resultVideoUrl"
        :message="statusMessage || pendingDetail"
        :title="pendingTitle"
        :detail="pendingDetail"
        :duration="pendingDuration"
      />

      <!-- Model selector -->
      <div v-if="models.length > 1">
        <label class="block text-sm text-slate-400 mb-1">{{ $t('upload.selectModel') }}</label>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <button
            v-for="m in models"
            :key="m.id"
            @click="selectedModel = m.id"
            class="flex items-center justify-between px-4 py-3 rounded-xl border text-left transition-all"
            :class="selectedModel === m.id
              ? 'border-indigo-500 bg-indigo-900/40 text-white'
              : 'border-slate-700 bg-slate-800 text-slate-300 hover:border-slate-500'"
          >
            <div>
              <p class="font-medium text-sm">{{ locale === 'zh-TW' ? m.name_zh : m.name }}</p>
            </div>
            <span class="text-xs font-mono text-indigo-400 shrink-0 ml-3">
              {{ m.credit_cost }} {{ $t('upload.credits') }}
            </span>
          </button>
        </div>
      </div>

      <!-- Drop zone -->
      <div
        class="relative rounded-2xl border-2 border-dashed transition-colors cursor-pointer"
        :class="isDragging ? 'border-indigo-400 bg-indigo-900/20' : 'border-slate-600 hover:border-slate-400 bg-slate-800/50'"
        @dragover.prevent="isDragging = true"
        @dragleave="isDragging = false"
        @drop.prevent="handleDrop"
        @click="fileInput?.click()"
      >
        <input
          ref="fileInput"
          type="file"
          :accept="uploadAccept"
          class="hidden"
          @change="handleFileChange"
        />

        <div v-if="!selectedFile" class="p-10 text-center">
          <div class="text-4xl mb-3">📁</div>
          <p class="text-slate-300 font-medium">{{ $t('upload.dropzone.title') }}</p>
          <p class="text-slate-500 text-sm mt-1">{{ $t('upload.dropzone.hint') }}</p>
        </div>

        <div v-else class="p-6 flex items-center gap-4">
          <!-- Preview -->
          <img
            v-if="previewUrl"
            :src="previewUrl"
            alt="Preview"
            class="w-20 h-20 object-cover rounded-lg shrink-0"
          />
          <div class="flex-1 min-w-0">
            <p class="text-slate-200 font-medium truncate">{{ selectedFile.name }}</p>
            <p class="text-slate-500 text-xs mt-0.5">{{ formatBytes(selectedFile.size) }}</p>
          </div>
          <button
            @click.stop="clearFile"
            class="text-slate-500 hover:text-red-400 transition-colors"
          >✕</button>
        </div>
      </div>

      <!-- Prompt input (optional for applicable tools) -->
      <div v-if="showPrompt">
        <label class="block text-sm text-slate-400 mb-1">{{ $t('upload.promptLabel') }}</label>
        <textarea
          v-model="promptText"
          :placeholder="$t('upload.promptPlaceholder')"
          rows="2"
          class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none"
        />
      </div>

      <!-- Upload progress -->
      <div v-if="uploadProgress > 0 && uploadProgress < 100" class="space-y-1">
        <p class="text-xs text-slate-400">{{ $t('upload.uploading') }} {{ uploadProgress }}%</p>
        <div class="h-1.5 bg-slate-700 rounded-full overflow-hidden">
          <div
            class="h-full bg-indigo-500 transition-all duration-300"
            :style="{ width: uploadProgress + '%' }"
          />
        </div>
      </div>

      <!-- Status message -->
      <div v-if="statusMessage" class="text-sm px-3 py-2 rounded-lg" :class="statusClass">
        {{ statusMessage }}
      </div>

      <!-- Result display -->
      <div v-if="resultUrl || resultVideoUrl" class="rounded-xl overflow-hidden border border-emerald-700/40">
        <div class="bg-emerald-900/20 px-4 py-2 flex items-center justify-between">
          <span class="text-emerald-400 text-sm font-medium">✓ {{ $t('upload.resultReady') }}</span>
          <button
            type="button"
            @click="downloadResult"
            :disabled="isDownloading"
            class="text-sm text-white bg-emerald-600 hover:bg-emerald-500 px-3 py-1 rounded-lg transition-colors"
          >
            {{ isDownloading ? $t('upload.downloading') : $t('upload.download') }}
          </button>
        </div>
        <video
          v-if="resultVideoUrl"
          :src="resultVideoUrl"
          controls
          class="w-full max-h-80 bg-black"
        />
        <img
          v-else-if="resultUrl"
          :src="resultUrl"
          alt="Result"
          class="w-full max-h-80 object-contain bg-slate-900"
        />
      </div>

      <!-- Generate button -->
      <button
        v-if="!resultUrl && !resultVideoUrl"
        @click="generate"
        :disabled="!selectedFile || isLoading"
        class="w-full py-3 rounded-xl font-semibold text-white transition-all"
        :class="!selectedFile || isLoading
          ? 'bg-slate-700 cursor-not-allowed opacity-60'
          : 'bg-indigo-600 hover:bg-indigo-500 active:scale-[0.98]'"
      >
        <span v-if="isLoading" class="flex items-center justify-center gap-2">
          <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
          </svg>
          {{ $t('upload.generating') }}
        </span>
        <span v-else>
          {{ $t('upload.generate') }} · {{ currentCreditCost }} {{ $t('upload.credits') }}
        </span>
      </button>

      <!-- Start over button -->
      <button
        v-if="resultUrl || resultVideoUrl"
        @click="reset"
        class="w-full py-2 rounded-xl text-sm text-slate-400 hover:text-white border border-slate-700 hover:border-slate-500 transition-colors"
      >
        {{ $t('upload.startOver') }}
      </button>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { uploadsApi } from '@/api/uploads'
import type { ModelInfo, UploadStatusResponse } from '@/api/uploads'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import { imageDimensionRuleForTool, validateImageFileDimensions } from '@/utils/mediaValidation'

// ─── Props ──────────────────────────────────────────────────────────────────
const props = defineProps<{
  toolType: string
  isSubscribed: boolean
  showPrompt?: boolean
  accept?: string
}>()

const emit = defineEmits<{
  result: [{ result_url: string | null; result_video_url: string | null; upload_id: string }]
}>()

// ─── State ──────────────────────────────────────────────────────────────────
const { locale } = useI18n()
const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const previewUrl = ref<string | null>(null)
const isDragging = ref(false)
const promptText = ref('')
const models = ref<ModelInfo[]>([])
const selectedModel = ref('default')
const isLoading = ref(false)
const uploadProgress = ref(0)
const statusMessage = ref('')
const statusClass = ref('')
const resultUrl = ref<string | null>(null)
const resultVideoUrl = ref<string | null>(null)
const currentUploadId = ref<string | null>(null)
const isDownloading = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

// ─── Computed ────────────────────────────────────────────────────────────────
const currentCreditCost = computed(() => {
  const m = models.value.find(m => m.id === selectedModel.value)
  return m?.credit_cost ?? 0
})
const isZh = computed(() => locale.value.startsWith('zh'))
const isVideoTool = computed(() => props.toolType.includes('video') || props.toolType.includes('avatar'))
const uploadAccept = computed(() => props.accept || (
  props.toolType === 'video_transform'
    ? '.mp4,.webm,.mov,video/mp4,video/webm,video/quicktime'
    : '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'
))
const pendingTitle = computed(() => isVideoTool.value
  ? (isZh.value ? '我正在產生所需的影片，這可能需要幾分鐘，請稍後再回來查看是否已完成。' : 'I am creating the requested video. This may take a few minutes, so please check back shortly.')
  : (isZh.value ? '我正在產生所需的圖片，這可能需要一些時間，請稍後再回來查看是否已完成。' : 'I am generating the requested image. This may take a little time, so please check back shortly.'))
const pendingDetail = computed(() => isVideoTool.value
  ? (isZh.value ? '正在生成影片...' : 'Generating video...')
  : (isZh.value ? '正在生成圖片...' : 'Generating image...'))
const pendingDuration = computed(() => isVideoTool.value
  ? (isZh.value ? '需要 1 至 5 分鐘' : 'Usually takes 1 to 5 minutes')
  : (isZh.value ? '需要 1 至 2 分鐘' : 'Usually takes 1 to 2 minutes'))

function localized(zh: string, en: string): string {
  return isZh.value ? zh : en
}

// ─── Watchers ────────────────────────────────────────────────────────────────
watch(() => props.isSubscribed, async (val) => {
  if (val) await loadModels()
})

// ─── Lifecycle ───────────────────────────────────────────────────────────────
onMounted(async () => {
  if (props.isSubscribed) await loadModels()
})

// ─── Methods ─────────────────────────────────────────────────────────────────
async function loadModels() {
  try {
    const res = await uploadsApi.getToolModels(props.toolType)
    models.value = res.models
    selectedModel.value = res.models[0]?.id ?? 'default'
  } catch {
    // silently handle
  }
}

async function handleDrop(e: DragEvent) {
  isDragging.value = false
  const file = e.dataTransfer?.files[0]
  if (file) await setFile(file)
}

async function handleFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (file && !(await setFile(file))) {
    input.value = ''
  }
}

async function setFile(file: File): Promise<boolean> {
  const expectsVideo = props.toolType === 'video_transform'
  const allowedTypes = expectsVideo
    ? ['video/mp4', 'video/webm', 'video/quicktime']
    : ['image/jpeg', 'image/png', 'image/webp']
  if (!allowedTypes.includes(file.type)) {
    setStatus(
      'error',
      expectsVideo
        ? (isZh.value ? '僅支援 MP4、WebM、MOV 影片，請重新選擇' : 'Only MP4, WebM, or MOV videos are supported. Please choose again.')
        : (isZh.value ? '僅支援 JPG、PNG、WebP 圖片，請重新選擇' : 'Only JPG, PNG, or WebP images are supported. Please choose again.'),
    )
    return false
  }
  if (file.size > 20 * 1024 * 1024) {
    setStatus('error', isZh.value ? '檔案需小於 20MB，請重新選擇' : 'File must be under 20MB. Please choose a smaller file.')
    return false
  }
  if (file.type.startsWith('image/')) {
    try {
      const dimensionError = await validateImageFileDimensions(file, imageDimensionRuleForTool(props.toolType), isZh.value)
      if (dimensionError) {
        setStatus('error', dimensionError)
        return false
      }
    } catch {
      setStatus('error', isZh.value ? '無法讀取圖片尺寸，請重新選擇圖片' : 'Image dimensions could not be read. Please choose a different image.')
      return false
    }
  }
  selectedFile.value = file
  if (file.type.startsWith('image/')) {
    previewUrl.value = URL.createObjectURL(file)
  } else {
    previewUrl.value = null
  }
  statusMessage.value = ''
  resultUrl.value = null
  resultVideoUrl.value = null
  return true
}

function clearFile() {
  selectedFile.value = null
  previewUrl.value = null
  if (fileInput.value) fileInput.value.value = ''
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function extensionFromType(contentType: string): string {
  if (contentType.includes('video')) return 'mp4'
  if (contentType.includes('png')) return 'png'
  if (contentType.includes('webp')) return 'webp'
  return 'jpg'
}

async function downloadResult() {
  if (!currentUploadId.value || isDownloading.value) return
  isDownloading.value = true
  try {
    const blob = await uploadsApi.downloadResult(currentUploadId.value)
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = `vidgo_result_${currentUploadId.value.slice(0, 8)}.${extensionFromType(blob.type)}`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(objectUrl)
  } catch (err: any) {
    const msg = err?.response?.data?.detail ?? localized('下載失敗，請再試一次。', 'Download failed. Please try again.')
    setStatus('error', msg)
  } finally {
    isDownloading.value = false
  }
}

async function generate() {
  if (!selectedFile.value || isLoading.value) return
  isLoading.value = true
  statusMessage.value = ''
  uploadProgress.value = 0

  try {
    const resp = await uploadsApi.uploadAndGenerate(
      props.toolType,
      selectedFile.value,
      selectedModel.value,
      promptText.value || undefined,
      (pct) => { uploadProgress.value = pct },
    )
    currentUploadId.value = resp.upload_id
    setStatus('info', localized('生成已開始...', 'Generation started...'))
    startPolling(resp.upload_id)
  } catch (err: any) {
    isLoading.value = false
    const msg = err?.response?.data?.detail ?? localized('上傳失敗，請再試一次。', 'Upload failed. Please try again.')
    setStatus('error', msg)
  }
}

function startPolling(uploadId: string) {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const status: UploadStatusResponse = await uploadsApi.getUploadStatus(uploadId)
      if (status.status === 'completed') {
        stopPolling()
        isLoading.value = false
        resultUrl.value = status.result_url
        resultVideoUrl.value = status.result_video_url
        setStatus('success', localized('生成完成！', 'Generation complete!'))
        emit('result', {
          result_url: status.result_url,
          result_video_url: status.result_video_url,
          upload_id: uploadId,
        })
      } else if (status.status === 'failed') {
        stopPolling()
        isLoading.value = false
        setStatus('error', status.error_message ?? localized('生成失敗。', 'Generation failed.'))
      } else {
        setStatus('info', localized(`處理中...（${status.status}）`, `Processing... (${status.status})`))
      }
    } catch {
      // keep polling
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function setStatus(type: 'info' | 'success' | 'error', msg: string) {
  statusMessage.value = msg
  statusClass.value = {
    info: 'bg-slate-700/60 text-slate-300',
    success: 'bg-emerald-900/40 text-emerald-300',
    error: 'bg-red-900/40 text-red-300',
  }[type]
}

function reset() {
  stopPolling()
  clearFile()
  promptText.value = ''
  resultUrl.value = null
  resultVideoUrl.value = null
  currentUploadId.value = null
  statusMessage.value = ''
  uploadProgress.value = 0
  isLoading.value = false
}
</script>
