<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { toolsApi, effectsApi, uploadsApi } from '@/api'
import type { Style } from '@/api/effects'
import type { UploadStatusResponse } from '@/api/uploads'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'

const { t, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const isZh = computed(() => locale.value.startsWith('zh'))
const isVideoTransformMode = computed(() => route.name === 'video-transform')
const pageTitle = computed(() => isVideoTransformMode.value
  ? (isZh.value ? '影片風格轉換' : 'Video Style Transform')
  : t('tools.shortVideo.name'))
const pageDescription = computed(() => isVideoTransformMode.value
  ? (isZh.value ? '上傳自己的影片，套用 AI 風格轉換效果。' : 'Upload your own video and apply an AI video style transform.')
  : t('tools.shortVideo.longDesc'))

// PRESET-ONLY MODE: All users use presets, no custom input
const {
  isDemoUser,
  canUseCustomInputs,
  loadDemoTemplates,
  demoTemplates,
  isLoadingTemplates,
  resolveDemoTemplateResultUrl,
  generateOnDemand,
  loadInputLibrary,
  inputLibrary,
  loadEffectCatalog,
  effectCatalog,
} = useDemoMode()

const isSubscribed = computed(() => !isDemoUser.value)

const uploadedImage = ref<string | undefined>(undefined)
const uploadedVideoFile = ref<File | null>(null)
const uploadedVideoPreview = ref<string | null>(null)
const transformPrompt = ref('')
const resultVideo = ref<string | null>(null)
const isProcessing = ref(false)
const uploadProgress = ref(0)
const processingStage = ref<string | null>(null)
const currentUploadId = ref<string | null>(null)
// True when a demo user clicked Generate but the selected tile isn't backed
// by a real Material DB preset (db_empty fallback or missing preset id).
// Surfaces a persistent in-block message instead of a silent no-op.
const demoEmptyState = ref(false)
// Settings - only for subscribed users
const selectedDuration = ref(5)
const selectedMotion = ref('auto')
const selectedModel = ref('pixverse_v4.5')
const selectedStyle = ref<string | null>(null)
const videoStyles = ref<Style[]>([])

const motionStrengthById: Record<string, number> = {
  auto: 5,
  'zoom-in': 4,
  'zoom-out': 4,
  'pan-left': 6,
  'pan-right': 6,
  rotate: 7,
}

function normalizeMotionId(motion?: string | null): string {
  return (motion || 'auto').replace(/_/g, '-')
}

// Duration options vary by model
const durationOptions = computed(() => {
  const modelInfo = aiModelOptions.find(m => m.id === selectedModel.value)
  return modelInfo?.lengths || [5, 8]
})

// Motion types - all motion options available in examples
const motionOptions = [
  { id: 'auto', nameEn: 'Auto', nameZh: '自動', descEn: 'AI decides motion', descZh: 'AI 自動選擇動態' },
  { id: 'zoom-in', nameEn: 'Zoom In', nameZh: '放大', descEn: 'Gradual zoom effect', descZh: '逐漸放大效果' },
  { id: 'zoom-out', nameEn: 'Zoom Out', nameZh: '縮小', descEn: 'Pull back effect', descZh: '拉遠效果' },
  { id: 'pan-left', nameEn: 'Pan Left', nameZh: '左移', descEn: 'Horizontal movement left', descZh: '向左平移' },
  { id: 'pan-right', nameEn: 'Pan Right', nameZh: '右移', descEn: 'Horizontal movement right', descZh: '向右平移' },
  { id: 'rotate', nameEn: 'Rotate', nameZh: '旋轉', descEn: 'Circular motion', descZh: '旋轉動態' }
]

// AI Model options from Pollo AI - subscriber only feature
const aiModelOptions = [
  {
    id: 'pixverse_v4.5',
    nameEn: 'Pixverse 4.5',
    nameZh: 'Pixverse 4.5',
    descEn: 'Fast & Affordable - Good quality',
    descZh: '快速實惠 - 品質優良',
    lengths: [5, 8],
    badge: 'default'
  },
  {
    id: 'pixverse_v5',
    nameEn: 'Pixverse 5.0',
    nameZh: 'Pixverse 5.0',
    descEn: 'Creative animations',
    descZh: '創意動畫風格',
    lengths: [5, 8],
    badge: 'new'
  },
  {
    id: 'kling_v2',
    nameEn: 'Kling AI 2.0',
    nameZh: 'Kling AI 2.0',
    descEn: 'High quality, lifelike movements',
    descZh: '高品質，逼真動態',
    lengths: [5, 10],
    badge: 'pro'
  },
  {
    id: 'kling_v1.5',
    nameEn: 'Kling AI 1.5',
    nameZh: 'Kling AI 1.5',
    descEn: 'Fast generation, good quality',
    descZh: '快速生成，品質好',
    lengths: [5, 10],
    badge: null
  },
  {
    id: 'luma_ray2',
    nameEn: 'Luma Ray 2.0',
    nameZh: 'Luma Ray 2.0',
    descEn: 'Cinematic quality',
    descZh: '電影級品質',
    lengths: [5, 10],
    badge: 'premium'
  }
]

// Demo images for demo users
const selectedDemoImageId = ref<string | null>(null)

const demoImages = computed(() => {
  return demoTemplates.value
    .filter(t => t.result_video_url || t.result_watermarked_url)
    .map(t => ({
      id: t.id,
      // Always show prompt in user's current language
      name: isZh.value ? (t.prompt_zh || t.prompt) : t.prompt,
      // Use thumbnail, input_image, or generate from video URL
      preview: t.thumbnail_url || t.input_image_url || undefined,
      video_url: t.result_video_url || t.result_watermarked_url,
      watermarked_result: t.result_watermarked_url,
      topic: t.topic,
      // Extract motion type from input_params (API returns metadata in input_params)
      motion: normalizeMotionId(t.input_params?.motion || t.topic || 'auto')
    }))
})


// Static fallback examples for ShortVideo (shown when backend DB is empty)
const STATIC_VIDEO_EXAMPLES = [
  {
    id: 'static-sv-1',
    name: 'Cherry blossom petals falling in slow motion, cinematic',
    preview: 'https://images.unsplash.com/photo-1522383225653-ed111181a951?w=600&fit=crop',
    video_url: undefined,
    watermarked_result: undefined,
    topic: 'nature',
    motion: 'zoom_in'
  },
  {
    id: 'static-sv-2',
    name: 'Skincare product rotating on marble surface, studio lighting',
    preview: 'https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=600&fit=crop',
    video_url: undefined,
    watermarked_result: undefined,
    topic: 'product',
    motion: 'rotate'
  },
  {
    id: 'static-sv-3',
    name: 'Coffee being poured into a glass cup, overhead view',
    preview: 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600&fit=crop',
    video_url: undefined,
    watermarked_result: undefined,
    topic: 'food',
    motion: 'pan_right'
  },
  {
    id: 'static-sv-4',
    name: 'Fashion model walking on city street, golden hour',
    preview: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600&fit=crop',
    video_url: undefined,
    watermarked_result: undefined,
    topic: 'fashion',
    motion: 'pan_left'
  },
  {
    id: 'static-sv-5',
    name: 'Mountain landscape with clouds moving, time lapse',
    preview: 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=600&fit=crop',
    video_url: undefined,
    watermarked_result: undefined,
    topic: 'landscape',
    motion: 'zoom_out'
  },
  {
    id: 'static-sv-6',
    name: 'Bubble tea shop interior, warm lighting, cozy atmosphere',
    preview: 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600&fit=crop',
    video_url: undefined,
    watermarked_result: undefined,
    topic: 'food',
    motion: 'auto'
  }
]
const effectiveDemoImages = computed(() =>
  demoImages.value.length > 0 ? demoImages.value : STATIC_VIDEO_EXAMPLES
)
const processingMessage = computed(() => {
  if (!isVideoTransformMode.value) {
    return isZh.value ? '正在生成影片... 這可能需要幾分鐘' : 'Generating video... This may take a few minutes'
  }

  if (uploadProgress.value > 0 && uploadProgress.value < 100) {
    return isZh.value
      ? `正在上傳影片... ${uploadProgress.value}%`
      : `Uploading video... ${uploadProgress.value}%`
  }

  if (processingStage.value) {
    return processingStage.value
  }

  return isZh.value ? '正在處理影片轉換... 這可能需要幾分鐘' : 'Processing video transform... This may take a few minutes'
})

// Load demo presets on mount
onMounted(async () => {
  await Promise.all([
    loadDemoTemplates('short_video'),
    // Pregenerated Vertex Veo T2V inputs as startable source frames/clips,
    // plus the motion-flavor catalog whose `prompt` is cache-keyed alongside
    // the picked input.
    loadInputLibrary('short_video'),
    loadEffectCatalog('short_video', locale.value),
  ])
  try {
    const styles = await effectsApi.getStyles('professional')
    videoStyles.value = styles.slice(0, 6)
  } catch {
    videoStyles.value = [
      { id: 'cinematic', name: 'VidGo Cinematic', name_zh: '電影質感', category: 'professional', preview_url: '' },
      { id: 'realistic', name: 'VidGo Realistic', name_zh: '寫實風格', category: 'modern', preview_url: '' },
      { id: 'anime', name: 'VidGo Anime', name_zh: '動漫風格', category: 'artistic', preview_url: '' },
      { id: 'watercolor', name: 'VidGo Watercolor', name_zh: '水彩風格', category: 'artistic', preview_url: '' },
    ]
  }
})

onBeforeUnmount(() => {
  if (uploadedVideoPreview.value) {
    URL.revokeObjectURL(uploadedVideoPreview.value)
  }
})

function selectDemoImage(item: { id: string; preview?: string; video_url?: string; motion?: string }) {
  selectedDemoImageId.value = item.id
  uploadedImage.value = item.preview || item.video_url || undefined
  resultVideo.value = null
  demoEmptyState.value = false
}



async function generateVideo() {
  if (isVideoTransformMode.value) {
    await generateVideoTransform()
    return
  }

  if (!uploadedImage.value) {
    uiStore.showError(isZh.value ? '請選擇一個範例' : 'Please select an example')
    return
  }

  // Clear stale result so loading overlay is the only thing visible.
  resultVideo.value = null
  demoEmptyState.value = false
  isProcessing.value = true
  try {
    // For demo users, resolve the selected preset through backend lookup
    if (isDemoUser.value && selectedDemoImageId.value) {
      const demoResultUrl = await resolveDemoTemplateResultUrl(selectedDemoImageId.value)
      if (demoResultUrl) {
        resultVideo.value = demoResultUrl
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }

      // VG-BUG-010 fix: cache-through on demand (Pollo MCP video generation
      // takes 2-5 min — the longer client-side timeout in generateOnDemand
      // accommodates this).
      uiStore.showInfo(isZh.value ? '此影片尚未生成，正在為您即時生成（約 2-5 分鐘）...' : 'Generating in real-time (2-5 min)...')
      // Prefer the pregenerated Vertex input frame when the user picked one
      // from the library; otherwise fall back to the finished-example input
      // or the user-uploaded image.
      const pickedFromLibrary = (inputLibrary.value.find((item: any) => item.id === selectedDemoImageId.value) as any)?.input_image_url
      const pickedFromTemplate = (demoTemplates.value.find((t: any) => t.id === selectedDemoImageId.value) as any)?.input_image_url
      const pickedFrame = pickedFromLibrary || pickedFromTemplate || uploadedImage.value || undefined
      // Map the motion radio to a real effect prompt from the catalog so the
      // cache key differentiates between "gentle" / "dramatic" / etc.
      const motionId = normalizeMotionId(selectedMotion.value)
      const motionPrompt = effectCatalog.value.find((e: any) =>
        e.id === motionId
        || e.id === (selectedStyle.value || '')
      )?.prompt || selectedStyle.value || undefined
      const onDemandUrl = await generateOnDemand('short_video', undefined, {
        input_image_url: pickedFrame,
        effect_prompt: motionPrompt,
      })
      if (onDemandUrl) {
        resultVideo.value = onDemandUrl
        uiStore.showSuccess(isZh.value ? '生成成功' : 'Generated successfully')
        return
      }
      demoEmptyState.value = true
      uiStore.showError(isZh.value ? '生成服務暫時無法使用，請稍後再試或訂閱解鎖完整功能' : 'Generation service temporarily unavailable. Please try again later or subscribe.')
      return
    }

    let imageUrl: string | null = null
    if (uploadedImage.value) {
      if (uploadedImage.value.startsWith('data:')) {
        const blob = dataURItoBlob(uploadedImage.value)
        if (!blob) {
          uiStore.showError(isZh.value ? '圖片格式無效，請重新上傳' : 'Invalid image format. Please re-upload.')
          return
        }
        const uploadResult = await toolsApi.uploadImage(blob as File)
        imageUrl = uploadResult.url
      } else {
        imageUrl = uploadedImage.value
      }
    }

    const result = await toolsApi.shortVideo(imageUrl!, {
      motionStrength: motionStrengthById[normalizeMotionId(selectedMotion.value)] ?? 5,
      modelId: selectedModel.value !== 'default' ? selectedModel.value : undefined,
      style: selectedStyle.value || undefined,
    })

    if (result.success && (result.video_url || result.result_url)) {
      resultVideo.value = result.video_url || result.result_url || null
      creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success'))
    } else {
      uiStore.showError(result.message || (result as any).error || (isZh.value ? '影片生成失敗，請稍後再試' : 'Video generation failed. Please try again.'))
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail || error?.response?.data?.message || error?.message || ''
    uiStore.showError(detail || (isZh.value ? '生成失敗' : 'Generation failed'))
  } finally {
    isProcessing.value = false
  }
}

function handleVideoUpload(event: Event) {
  const input = event.target as HTMLInputElement | null
  const file = input?.files?.[0]
  if (!file) return

  if (!file.type.startsWith('video/')) {
    uiStore.showError(isZh.value ? '請上傳影片檔案' : 'Please upload a video file')
    return
  }

  if (uploadedVideoPreview.value) {
    URL.revokeObjectURL(uploadedVideoPreview.value)
  }

  uploadedVideoFile.value = file
  uploadedVideoPreview.value = URL.createObjectURL(file)
  resultVideo.value = null
  demoEmptyState.value = false
}

function clearUploadedVideo() {
  uploadedVideoFile.value = null
  resultVideo.value = null
  uploadProgress.value = 0
  processingStage.value = null
  currentUploadId.value = null
  if (uploadedVideoPreview.value) {
    URL.revokeObjectURL(uploadedVideoPreview.value)
    uploadedVideoPreview.value = null
  }
}

function playPreviewVideo(event: Event) {
  const video = event.target as HTMLVideoElement | null
  video?.play()
}

function resetPreviewVideo(event: Event) {
  const video = event.target as HTMLVideoElement | null
  if (!video) return
  video.pause()
  video.currentTime = 0
}

async function pollUploadStatus(uploadId: string): Promise<UploadStatusResponse> {
  const maxAttempts = 120
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const status = await uploadsApi.getUploadStatus(uploadId)
    if (status.status === 'completed' || status.status === 'failed') {
      return status
    }
    processingStage.value = isZh.value
      ? `伺服器正在處理中...（${status.status}）`
      : `Server is processing... (${status.status})`
    await new Promise(resolve => window.setTimeout(resolve, 3000))
  }
  throw new Error(isZh.value ? '影片轉換逾時，請稍後到作品紀錄查看' : 'Video transform timed out. Please check My Works later.')
}

async function generateVideoTransform() {
  if (!isSubscribed.value) {
    uiStore.showError(isZh.value ? '請先訂閱以使用影片上傳' : 'Please subscribe to upload your own video')
    return
  }

  if (!uploadedVideoFile.value) {
    uiStore.showError(isZh.value ? '請先上傳影片' : 'Please upload a video first')
    return
  }

  if (!transformPrompt.value.trim()) {
    uiStore.showError(isZh.value ? '請輸入影片風格描述' : 'Please enter a video style prompt')
    return
  }

  resultVideo.value = null
  isProcessing.value = true
  uploadProgress.value = 0
  currentUploadId.value = null
  processingStage.value = isZh.value ? '準備上傳影片...' : 'Preparing upload...'
  try {
    const prompt = selectedStyle.value
      ? `${transformPrompt.value.trim()}\nStyle preset: ${selectedStyle.value}`
      : transformPrompt.value.trim()
    const upload = await uploadsApi.uploadAndGenerate(
      'video_transform',
      uploadedVideoFile.value,
      'default',
      prompt,
      (pct) => {
        uploadProgress.value = pct
        processingStage.value = isZh.value
          ? `正在上傳影片... ${pct}%`
          : `Uploading video... ${pct}%`
      },
    )
    currentUploadId.value = upload.upload_id
    uploadProgress.value = 100
    processingStage.value = isZh.value ? '上傳完成，正在排入轉換...' : 'Upload complete, queuing transform...'
    const status = await pollUploadStatus(upload.upload_id)

    if (status.status === 'completed' && status.result_video_url) {
      resultVideo.value = status.result_video_url
      creditsStore.deductCredits(status.credits_used)
      processingStage.value = isZh.value ? '影片轉換完成' : 'Video transform completed'
      uiStore.showSuccess(isZh.value ? '影片轉換完成' : 'Video transform completed')
      return
    }

    uiStore.showError(status.error_message || (isZh.value ? '影片轉換失敗' : 'Video transform failed'))
  } catch (error: any) {
    const detail = error?.response?.data?.detail || error?.message || ''
    uiStore.showError(detail || (isZh.value ? '影片轉換失敗' : 'Video transform failed'))
  } finally {
    isProcessing.value = false
  }
}

function dataURItoBlob(dataURI: string): Blob | null {
  if (!dataURI || !dataURI.includes(',') || !dataURI.startsWith('data:')) return null
  try {
    const byteString = atob(dataURI.split(',')[1])
    const mimeString = dataURI.split(',')[0].split(':')[1].split(';')[0]
    const ab = new ArrayBuffer(byteString.length)
    const ia = new Uint8Array(ab)
    for (let i = 0; i < byteString.length; i++) { ia[i] = byteString.charCodeAt(i) }
    return new Blob([ab], { type: mimeString })
  } catch { return null }
}


</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b; color: #f5f5fa;">
    <LoadingOverlay :show="isProcessing" :message="processingMessage" />

    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Back Button -->
      <button
        @click="router.back()"
        class="mb-6 flex items-center gap-2 text-dark-300 hover:text-dark-50 transition-colors"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        {{ t('common.back') }}
      </button>

      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-dark-50 mb-4">
          {{ pageTitle }}
        </h1>
        <p class="text-xl text-dark-300">
          {{ pageDescription }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ isZh ? '訂閱以解鎖進階設定與 AI 模型選擇' : 'Subscribe to unlock advanced settings & AI model selection' }}
          </RouterLink>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Left Panel - Input -->
        <div class="space-y-6">
          <!-- Example Selection -->
          <div class="card">
            <h3 class="text-lg font-semibold text-dark-50 mb-4">
              {{ isVideoTransformMode
                ? (isZh ? '上傳你的影片' : 'Upload Your Video')
                : (isZh ? '請試試我們精彩的範例' : 'Please try our amazing examples') }}
            </h3>

            <!-- Subscriber Interface: Upload Zone -->
            <div v-if="!isDemoUser && !isVideoTransformMode" class="mb-6">
               <h4 class="text-sm font-medium text-dark-300 mb-2">{{ isZh ? '上傳圖片 (.jpg, .png)' : 'Upload Image (.jpg, .png)' }}</h4>
               <ImageUploader 
                 v-model="uploadedImage" 
                 :label="isZh ? '點擊上傳或拖放起始圖片' : 'Drop starting image here'"
                 class="mb-4"
                 @update:model-value="selectedDemoImageId = null"
               />
            </div>

            <div v-if="isSubscribed && isVideoTransformMode" class="space-y-4 mb-6">
              <div>
                <label class="label">{{ isZh ? '上傳影片' : 'Upload Video' }}</label>
                <label class="block rounded-xl border-2 border-dashed p-6 cursor-pointer transition-colors" style="border-color: rgba(255,255,255,0.08); background: #141420;">
                  <input type="file" accept="video/mp4,video/webm,video/quicktime" class="hidden" @change="handleVideoUpload" />
                  <div class="text-center">
                    <p class="text-dark-50 text-sm font-medium">{{ isZh ? '點擊或拖放 MP4 / WEBM / MOV' : 'Click or drop MP4 / WEBM / MOV' }}</p>
                    <p class="text-dark-400 text-xs mt-1">{{ isZh ? '付費用戶可上傳自己的影片做風格轉換' : 'Paid users can upload their own videos for style transfer' }}</p>
                  </div>
                </label>
              </div>

              <div v-if="uploadedVideoPreview" class="space-y-3">
                <video :src="uploadedVideoPreview" controls class="w-full rounded-xl" />
                <button @click="clearUploadedVideo" class="btn-ghost text-sm w-full">
                  {{ isZh ? '移除影片' : 'Remove Video' }}
                </button>
              </div>

              <div>
                <label class="label">{{ isZh ? '轉換描述' : 'Transform Prompt' }}</label>
                <textarea
                  v-model="transformPrompt"
                  rows="4"
                  class="w-full rounded-xl px-4 py-3 text-dark-50"
                  style="background: #141420; border: 1px solid rgba(255,255,255,0.08);"
                  :placeholder="isZh ? '例如：把這支商品展示影片變成更電影感、燈光更柔和、適合小品牌廣告。' : 'Example: Make this product clip more cinematic with softer lighting for a small business ad.'"
                />
              </div>

              <div v-if="isProcessing || currentUploadId || uploadProgress > 0" class="rounded-2xl p-4 border" style="background: linear-gradient(135deg, rgba(16,24,40,0.92), rgba(19,49,58,0.78)); border-color: rgba(93, 188, 210, 0.28);">
                <div class="flex items-start justify-between gap-4 mb-3">
                  <div>
                    <p class="text-xs uppercase tracking-[0.24em] text-cyan-300/80">
                      {{ isZh ? '轉換狀態' : 'Transform Status' }}
                    </p>
                    <p class="text-sm text-dark-50 mt-1">{{ processingMessage }}</p>
                  </div>
                  <div class="shrink-0 text-right">
                    <p class="text-2xl font-semibold text-cyan-200">{{ uploadProgress }}%</p>
                    <p class="text-[11px] text-dark-400">{{ isZh ? '上傳進度' : 'Upload Progress' }}</p>
                  </div>
                </div>

                <div class="h-2 rounded-full overflow-hidden mb-3" style="background: rgba(255,255,255,0.08);">
                  <div class="h-full rounded-full transition-all duration-300" :style="{ width: `${uploadProgress}%`, background: 'linear-gradient(90deg, #5dbcd2, #b4f0ff)' }" />
                </div>

                <div class="flex items-center justify-between text-xs text-dark-300 gap-3">
                  <span>{{ isZh ? '大型影片通常需要數分鐘' : 'Longer clips can take several minutes' }}</span>
                  <span v-if="currentUploadId" class="font-mono text-cyan-200">#{{ currentUploadId.slice(0, 8) }}</span>
                </div>
              </div>
            </div>

            <div v-else-if="isVideoTransformMode" class="p-4 rounded-xl mb-6" style="background: #141420; border: 1px solid rgba(255,255,255,0.08);">
              <p class="text-sm text-dark-300">{{ isZh ? '訂閱後即可上傳自己的影片並進行風格轉換。' : 'Subscribe to upload your own video and run style transfer.' }}</p>
            </div>

            <!-- Demo Images for all users -->
            <div v-if="!isVideoTransformMode && effectiveDemoImages.length > 0" class="mb-4">
              <p class="text-sm text-dark-300 mb-3">
                {{ isZh ? '點擊查看不同動態效果' : 'Click to see different motion effects' }}
              </p>
              <div v-if="isLoadingTemplates" class="flex justify-center py-8">
                <div class="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
              </div>
              <div v-else class="grid grid-cols-2 gap-2">
                <button
                  v-for="item in effectiveDemoImages"
                  :key="item.id"
                  @click="selectDemoImage(item)"
                  class="aspect-video rounded-lg overflow-hidden border-2 transition-all relative group"
                  :class="selectedDemoImageId === item.id
                    ? 'border-primary-500'
                    : ''" style="border-color: rgba(255,255,255,0.08);">
                >
                  <!-- Video preview with poster -->
                  <video
                    v-if="item.video_url"
                    :src="item.video_url"
                    class="w-full h-full object-cover"
                    muted
                    preload="metadata"
                    @mouseenter="playPreviewVideo"
                    @mouseleave="resetPreviewVideo"
                  />
                  <img
                    v-else-if="item.preview"
                    :src="item.preview"
                    :alt="item.name"
                    class="w-full h-full object-cover"
                  />
                  <div v-else class="w-full h-full flex items-center justify-center" style="background: #141420;">
                    <span class="text-3xl">🎬</span>
                  </div>
                  <!-- Motion type badge -->
                  <div class="absolute top-1 left-1 px-2 py-0.5 bg-primary-500/80 rounded text-xs text-dark-50">
                    {{ isZh
                      ? motionOptions.find(m => m.id === item.motion)?.nameZh || item.topic
                      : motionOptions.find(m => m.id === item.motion)?.nameEn || item.topic
                    }}
                  </div>
                  <!-- Prompt description overlay -->
                  <div class="absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-t from-black/80 to-transparent">
                    <p class="text-dark-50 text-xs line-clamp-2">
                      {{ item.name }}
                    </p>
                  </div>
                  <!-- Play icon overlay -->
                  <div class="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    <span class="text-4xl">▶️</span>
                  </div>
                </button>
              </div>
            </div>

            <!-- Selected Image Preview -->
            <div v-if="!isVideoTransformMode && uploadedImage" class="space-y-4 mt-4">
              <img :src="uploadedImage" alt="Source" class="w-full rounded-xl" />
              <button v-if="canUseCustomInputs" @click="uploadedImage = undefined; selectedDemoImageId = null" class="btn-ghost text-sm w-full">
                {{ isZh ? '移除圖片' : 'Remove Image' }}
              </button>
            </div>
          </div>

          <!-- Selected Video Info - shows when a preset is selected -->
          <div v-if="!isVideoTransformMode && selectedDemoImageId" class="card">
            <h3 class="text-lg font-semibold text-dark-50 mb-4">
              {{ isZh ? '已選擇的範例' : 'Selected Example' }}
            </h3>
            <div class="p-3 bg-primary-500/10 border border-primary-500/20 rounded-lg">
              <p class="text-sm text-dark-50 mb-2">
                <span class="text-primary-400 font-medium">{{ isZh ? '動態效果：' : 'Motion Effect: ' }}</span>
                {{ isZh
                  ? motionOptions.find(m => m.id === demoImages.find(d => d.id === selectedDemoImageId)?.motion)?.nameZh || '自動'
                  : motionOptions.find(m => m.id === demoImages.find(d => d.id === selectedDemoImageId)?.motion)?.nameEn || 'Auto'
                }}
              </p>
              <p class="text-sm text-dark-200">
                <span class="text-primary-400 font-medium">{{ isZh ? '描述：' : 'Prompt: ' }}</span>
                {{ demoImages.find(d => d.id === selectedDemoImageId)?.name }}
              </p>
            </div>
            <!-- Visitor/demo user: direct "View Result" button, no gated settings noise -->
            <div v-if="!isSubscribed" class="mt-4">
              <button
                @click="generateVideo"
                :disabled="isProcessing"
                class="btn-primary w-full"
              >
                {{ isZh ? '查看結果' : 'View Result' }}
              </button>
            </div>
          </div>

          <!-- Prompt to select - shows when nothing selected -->
          <div v-else-if="!isVideoTransformMode" class="card">
            <h3 class="text-lg font-semibold text-dark-50 mb-4">
              {{ isZh ? '選擇一個範例' : 'Select an Example' }}
            </h3>
            <div class="p-3 rounded-lg" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
              <p class="text-sm text-dark-300">
                {{ isZh ? '👆 從上方範例影片中選擇一個來查看效果' : '👆 Select an example video above to see the result' }}
              </p>
            </div>
          </div>

          <!-- Video Settings - Subscriber Only (hidden entirely for visitors) -->
          <div v-if="isSubscribed && !isVideoTransformMode" class="card">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold text-dark-50">
                {{ isZh ? '影片設定' : 'Video Settings' }}
              </h3>
            </div>

            <!-- Duration - Subscriber only -->
            <div class="mb-6" :class="{ 'opacity-50 pointer-events-none': !isSubscribed }">
              <label class="label">{{ isZh ? '影片長度' : 'Duration' }}</label>
              <div class="flex gap-3">
                <button
                  v-for="dur in durationOptions"
                  :key="dur"
                  @click="isSubscribed && (selectedDuration = dur)"
                  class="flex-1 py-3 rounded-xl border-2 transition-all"
                  :class="selectedDuration === dur
                    ? 'border-primary-500 bg-primary-500/10'
                    : ''" style="border-color: rgba(255,255,255,0.08);">
                >
                  {{ dur }}s
                </button>
              </div>
              <p v-if="!isSubscribed" class="text-xs text-dark-400 mt-2">
                {{ isZh ? '訂閱後可自訂影片長度' : 'Subscribe to customize video duration' }}
              </p>
            </div>

            <!-- Motion Type - Subscriber only -->
            <div :class="{ 'opacity-50 pointer-events-none': !isSubscribed }">
              <label class="label">{{ isZh ? '動態類型' : 'Motion Type' }}</label>
              <div class="grid grid-cols-3 gap-2">
                <button
                  v-for="motion in motionOptions"
                  :key="motion.id"
                  @click="isSubscribed && (selectedMotion = motion.id)"
                  class="p-3 rounded-xl border-2 transition-all text-center"
                  :class="selectedMotion === motion.id
                    ? 'border-primary-500 bg-primary-500/10'
                    : ''" style="border-color: rgba(255,255,255,0.08);">
                >
                  <p class="text-sm font-medium">{{ isZh ? motion.nameZh : motion.nameEn }}</p>
                  <p class="text-xs text-dark-400 mt-1">{{ isZh ? motion.descZh : motion.descEn }}</p>
                </button>
              </div>
              <p v-if="!isSubscribed" class="text-xs text-dark-400 mt-2">
                {{ isZh ? '訂閱後可選擇動態效果' : 'Subscribe to choose motion effects' }}
              </p>
            </div>

            <!-- Not subscribed notice -->
            <div v-if="!isSubscribed" class="mt-4 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
              <p class="text-sm text-amber-400">
                {{ isZh ? '🔒 升級訂閱以使用自訂設定' : '🔒 Upgrade to use custom settings' }}
              </p>
              <RouterLink to="/pricing" class="text-sm text-primary-400 hover:underline mt-1 inline-block">
                {{ isZh ? '查看方案 →' : 'View Plans →' }}
              </RouterLink>
            </div>

            <!-- Credit Cost & Generate -->
            <div class="mt-6 pt-4" style="border-top: 1px solid rgba(255,255,255,0.06);">
              <CreditCost :service="isVideoTransformMode ? undefined : 'short_video'" :cost="isVideoTransformMode ? 35 : undefined" />
              <button
                @click="generateVideo"
                :disabled="isVideoTransformMode ? (!uploadedVideoFile || !transformPrompt.trim() || isProcessing) : (!(selectedDemoImageId || uploadedImage) || isProcessing)"
                class="btn-primary w-full mt-4"
              >
                {{ isVideoTransformMode
                  ? (isZh ? '開始轉換' : 'Start Transform')
                  : (isZh ? '查看結果' : 'View Result') }}
              </button>
            </div>
          </div>

          <!-- AI Model Selection - Subscriber Only (hidden entirely for visitors) -->
          <div v-if="isSubscribed && !isVideoTransformMode" class="card">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold text-dark-50">
                {{ isZh ? 'AI 模型選擇' : 'AI Model Selection' }}
              </h3>
            </div>

            <div v-if="isSubscribed">
              <p class="text-sm text-dark-300 mb-3">
                {{ isZh ? '選擇不同的 AI 模型以獲得不同的生成效果' : 'Choose different AI models for different generation effects' }}
              </p>
              <div class="space-y-2">
                <button
                  v-for="model in aiModelOptions"
                  :key="model.id"
                  @click="selectedModel = model.id"
                  class="w-full p-3 rounded-xl border-2 transition-all text-left flex items-center justify-between"
                  :class="selectedModel === model.id
                    ? 'border-primary-500 bg-primary-500/10'
                    : ''" style="border-color: rgba(255,255,255,0.08);">
                >
                  <div>
                    <p class="text-sm font-medium text-dark-50">{{ isZh ? model.nameZh : model.nameEn }}</p>
                    <p class="text-xs text-dark-400">{{ isZh ? model.descZh : model.descEn }}</p>
                    <p class="text-xs text-dark-400 mt-1">
                      {{ isZh ? `支援長度: ${model.lengths.join('s, ')}s` : `Lengths: ${model.lengths.join('s, ')}s` }}
                    </p>
                  </div>
                  <div v-if="model.badge" class="ml-2">
                    <span v-if="model.badge === 'default'" class="text-xs px-2 py-0.5 bg-gray-500/20 text-dark-300 rounded">Default</span>
                    <span v-else-if="model.badge === 'new'" class="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded">New</span>
                    <span v-else-if="model.badge === 'pro'" class="text-xs px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded">Pro</span>
                    <span v-else-if="model.badge === 'premium'" class="text-xs px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded">Premium</span>
                  </div>
                </button>
              </div>
            </div>

            <!-- Not subscribed notice -->
            <div v-if="!isSubscribed" class="mt-4 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
              <p class="text-sm text-amber-400">
                {{ isZh ? '🔒 升級訂閱以選擇不同 AI 模型' : '🔒 Upgrade to choose different AI models' }}
              </p>
              <RouterLink to="/pricing" class="text-sm text-primary-400 hover:underline mt-1 inline-block">
                {{ isZh ? '查看方案 →' : 'View Plans →' }}
              </RouterLink>
            </div>
          </div>

          <!-- Video Style Effects - Subscriber Only -->
          <div v-if="isSubscribed" class="card">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold text-dark-50">
                {{ isVideoTransformMode
                  ? (isZh ? '影片轉換風格' : 'Video Transform Style')
                  : (isZh ? '影片風格效果' : 'Video Style Effects') }}
              </h3>
              <button
                v-if="selectedStyle"
                @click="selectedStyle = null"
                class="text-xs text-primary-400 hover:text-primary-300 transition-colors"
              >
                {{ isZh ? '清除效果' : 'Clear Effect' }}
              </button>
            </div>

            <p class="text-sm text-dark-300 mb-3">
              {{ isVideoTransformMode
                ? (isZh ? '可選擇一個風格預設，會附加到你的影片轉換描述中。' : 'Optionally choose a style preset to append to your video transform prompt.')
                : (isZh ? '可選擇性套用第二段影片風格轉換。未選擇時只會進行一般圖片轉影片。' : 'Optionally apply a second-pass video style transform. Leave empty to use standard image-to-video only.') }}
            </p>

            <div class="grid grid-cols-2 gap-2">
              <button
                v-for="style in videoStyles"
                :key="style.id"
                @click="selectedStyle = selectedStyle === style.id ? null : style.id"
                class="p-3 rounded-xl border-2 transition-all text-left"
                :class="selectedStyle === style.id ? 'border-primary-500 bg-primary-500/10' : ''"
                style="border-color: rgba(255,255,255,0.08);"
              >
                <p class="text-sm font-medium text-dark-50">
                  {{ isZh ? style.name_zh : style.name }}
                </p>
                <p class="text-xs text-dark-400 mt-1">{{ style.id }}</p>
              </button>
            </div>
          </div>
        </div>

        <!-- Right Panel - Result -->
        <div class="card h-fit sticky top-24">
          <h3 class="text-lg font-semibold text-dark-50 mb-4">
            {{ isZh ? '生成的影片' : 'Generated Video' }}
          </h3>

          <div v-if="resultVideo" class="space-y-4">
            <video
              :src="resultVideo"
              controls
              class="w-full rounded-xl"
              autoplay
              loop
            />
            <!-- Watermark badge -->
            <div class="text-center text-xs text-dark-400">vidgo.ai</div>
            <!-- Download / Action Buttons -->
            <div class="flex gap-3">
               <a
                 v-if="!isDemoUser"
                 :href="resultVideo"
                 download="vidgo_short_video.mp4"
                 class="btn-primary flex-1 text-center py-3 flex items-center justify-center"
               >
                 <span class="mr-2">📥</span> {{ t('common.download') }}
               </a>

               <RouterLink v-else to="/pricing" class="btn-primary w-full text-center block">
                 {{ isZh ? '訂閱以獲得完整功能' : 'Subscribe for Full Access' }}
               </RouterLink>
            </div>
          </div>

          <div v-else-if="demoEmptyState" class="aspect-video flex flex-col items-center justify-center rounded-xl text-center px-6 gap-3" style="background: #141420; border: 1px solid rgba(255,255,255,0.08);">
            <span class="text-2xl">🔒</span>
            <p class="text-sm text-dark-200">
              {{ isZh ? '此範例尚未預生成結果' : 'No pre-generated result for this example yet' }}
            </p>
            <RouterLink to="/pricing" class="btn-primary text-sm px-4 py-2">
              {{ isZh ? '訂閱以使用完整 AI 功能' : 'Subscribe to use the real AI' }}
            </RouterLink>
          </div>

          <div v-else class="aspect-video flex items-center justify-center rounded-xl text-dark-400" style="background: #141420;">
            <div class="text-center">
              <span class="text-5xl block mb-4">🎬</span>
              <p>{{ isZh ? '生成的影片將顯示在這裡' : 'Generated video will appear here' }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
