<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore, useAuthStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { demoApi } from '@/api'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const authStore = useAuthStore()
const isZh = computed(() => locale.value.startsWith('zh'))

// Check if user is subscribed (has paid plan)
const isSubscribed = computed(() => {
  return authStore.user?.plan_type && authStore.user.plan_type !== 'demo'
})

// PRESET-ONLY MODE: All users use presets, no custom input
const {
  isDemoUser,
  canUseCustomInputs,
  loadDemoTemplates,
  demoTemplates,
  isLoadingTemplates
} = useDemoMode()

const uploadedImage = ref<string | undefined>(undefined)
const resultVideo = ref<string | null>(null)
const isProcessing = ref(false)
// Settings - only for subscribed users
const selectedDuration = ref(5)
const selectedMotion = ref('auto')
const selectedModel = ref('pixverse_v4.5')

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
      motion: t.input_params?.motion || t.topic || 'auto'
    }))
})

// Load demo presets on mount
onMounted(async () => {
  await loadDemoTemplates('short_video')
})

function selectDemoImage(item: { id: string; preview?: string; video_url?: string; motion?: string }) {
  selectedDemoImageId.value = item.id
  uploadedImage.value = item.preview || item.video_url || undefined
  // Auto-show the result video for demo items
  const template = demoTemplates.value.find(t => t.id === item.id)
  if (template?.result_video_url || template?.result_watermarked_url) {
    resultVideo.value = template.result_video_url || template.result_watermarked_url || null
  } else {
    resultVideo.value = null
  }
}



async function generateVideo() {
  if (!uploadedImage.value) {
    uiStore.showError(isZh.value ? '請選擇一個範例' : 'Please select an example')
    return
  }

  isProcessing.value = true
  try {
    // For demo users with selected template, use cached result
    if (isDemoUser.value && selectedDemoImageId.value) {
      const template = demoTemplates.value.find(t => t.id === selectedDemoImageId.value)
      if (template?.result_video_url || template?.result_watermarked_url) {
        resultVideo.value = template.result_video_url || template.result_watermarked_url || null
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }
    }

    let imageUrl = null
    if (uploadedImage.value) {
      const uploadResult = await demoApi.uploadImage(
        dataURItoBlob(uploadedImage.value) as File
      )
      imageUrl = uploadResult.url
    }

    const result = await demoApi.generate({
      tool: 'short_video',
      image_url: imageUrl || undefined,
      params: {
        duration: selectedDuration.value,
        motion: selectedMotion.value,
        model: selectedModel.value
      }
    })

    if (result.success && result.video_url) {
      resultVideo.value = result.video_url
      creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success'))
    }
  } catch (error) {
    uiStore.showError(isZh.value ? '生成失敗' : 'Generation failed')
  } finally {
    isProcessing.value = false
  }
}

function dataURItoBlob(dataURI: string): Blob {
  const byteString = atob(dataURI.split(',')[1])
  const mimeString = dataURI.split(',')[0].split(':')[1].split(';')[0]
  const ab = new ArrayBuffer(byteString.length)
  const ia = new Uint8Array(ab)
  for (let i = 0; i < byteString.length; i++) {
    ia[i] = byteString.charCodeAt(i)
  }
  return new Blob([ab], { type: mimeString })
}


</script>

<template>
  <div class="min-h-screen pt-24 pb-20 bg-white">
    <LoadingOverlay :show="isProcessing" :message="isZh ? '正在生成影片... 這可能需要幾分鐘' : 'Generating video... This may take a few minutes'" />

    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Back Button -->
      <button
        @click="router.back()"
        class="mb-6 flex items-center gap-2 text-dark-500 hover:text-dark-900 transition-colors"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        {{ t('common.back') }}
      </button>

      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-dark-900 mb-4">
          {{ t('tools.shortVideo.name') }}
        </h1>
        <p class="text-xl text-dark-500">
          {{ t('tools.shortVideo.longDesc') }}
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
            <h3 class="text-lg font-semibold text-dark-900 mb-4">
              {{ isZh ? '請試試我們精彩的範例' : 'Please try our amazing examples' }}
            </h3>

            <!-- Subscriber Interface: Upload Zone -->
            <div v-if="!isDemoUser" class="mb-6">
               <h4 class="text-sm font-medium text-dark-500 mb-2">{{ isZh ? '上傳圖片 (.jpg, .png)' : 'Upload Image (.jpg, .png)' }}</h4>
               <ImageUploader 
                 v-model="uploadedImage" 
                 :label="isZh ? '點擊上傳或拖放起始圖片' : 'Drop starting image here'"
                 class="mb-4"
                 @update:model-value="selectedDemoImageId = null"
               />
            </div>

            <!-- Demo Images for all users -->
            <div v-if="demoImages.length > 0" class="mb-4">
              <p class="text-sm text-dark-500 mb-3">
                {{ isZh ? '點擊查看不同動態效果' : 'Click to see different motion effects' }}
              </p>
              <div v-if="isLoadingTemplates" class="flex justify-center py-8">
                <div class="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
              </div>
              <div v-else class="grid grid-cols-2 gap-2">
                <button
                  v-for="item in demoImages"
                  :key="item.id"
                  @click="selectDemoImage(item)"
                  class="aspect-video rounded-lg overflow-hidden border-2 transition-all relative group"
                  :class="selectedDemoImageId === item.id
                    ? 'border-primary-500'
                    : 'border-gray-200 hover:border-gray-300'"
                >
                  <!-- Video preview with poster -->
                  <video
                    v-if="item.video_url"
                    :src="item.video_url"
                    class="w-full h-full object-cover"
                    muted
                    preload="metadata"
                    @mouseenter="($event.target as HTMLVideoElement).play()"
                    @mouseleave="($event.target as HTMLVideoElement).pause(); ($event.target as HTMLVideoElement).currentTime = 0"
                  />
                  <img
                    v-else-if="item.preview"
                    :src="item.preview"
                    :alt="item.name"
                    class="w-full h-full object-cover"
                  />
                  <div v-else class="w-full h-full bg-gray-100 flex items-center justify-center">
                    <span class="text-3xl">🎬</span>
                  </div>
                  <!-- Motion type badge -->
                  <div class="absolute top-1 left-1 px-2 py-0.5 bg-primary-500/80 rounded text-xs text-dark-900">
                    {{ isZh
                      ? motionOptions.find(m => m.id === item.motion)?.nameZh || item.topic
                      : motionOptions.find(m => m.id === item.motion)?.nameEn || item.topic
                    }}
                  </div>
                  <!-- Prompt description overlay -->
                  <div class="absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-t from-black/80 to-transparent">
                    <p class="text-dark-900 text-xs line-clamp-2">
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
            <div v-if="uploadedImage" class="space-y-4 mt-4">
              <img :src="uploadedImage" alt="Source" class="w-full rounded-xl" />
              <button v-if="canUseCustomInputs" @click="uploadedImage = undefined; selectedDemoImageId = null" class="btn-ghost text-sm w-full">
                {{ isZh ? '移除圖片' : 'Remove Image' }}
              </button>
            </div>
          </div>

          <!-- Selected Video Info - shows when a preset is selected -->
          <div v-if="selectedDemoImageId" class="card">
            <h3 class="text-lg font-semibold text-dark-900 mb-4">
              {{ isZh ? '已選擇的範例' : 'Selected Example' }}
            </h3>
            <div class="p-3 bg-primary-500/10 border border-primary-500/20 rounded-lg">
              <p class="text-sm text-dark-900 mb-2">
                <span class="text-primary-400 font-medium">{{ isZh ? '動態效果：' : 'Motion Effect: ' }}</span>
                {{ isZh
                  ? motionOptions.find(m => m.id === demoImages.find(d => d.id === selectedDemoImageId)?.motion)?.nameZh || '自動'
                  : motionOptions.find(m => m.id === demoImages.find(d => d.id === selectedDemoImageId)?.motion)?.nameEn || 'Auto'
                }}
              </p>
              <p class="text-sm text-dark-600">
                <span class="text-primary-400 font-medium">{{ isZh ? '描述：' : 'Prompt: ' }}</span>
                {{ demoImages.find(d => d.id === selectedDemoImageId)?.name }}
              </p>
            </div>
          </div>

          <!-- Prompt to select - shows when nothing selected -->
          <div v-else class="card">
            <h3 class="text-lg font-semibold text-dark-900 mb-4">
              {{ isZh ? '選擇一個範例' : 'Select an Example' }}
            </h3>
            <div class="p-3 bg-gray-100/50 border border-gray-200 rounded-lg">
              <p class="text-sm text-dark-500">
                {{ isZh ? '👆 從上方範例影片中選擇一個來查看效果' : '👆 Select an example video above to see the result' }}
              </p>
            </div>
          </div>

          <!-- Video Settings - Subscriber Only -->
          <div class="card">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold text-dark-900">
                {{ isZh ? '影片設定' : 'Video Settings' }}
              </h3>
              <span v-if="!isSubscribed" class="text-xs px-2 py-1 bg-amber-500/20 text-amber-400 rounded">
                {{ isZh ? '訂閱專屬' : 'Subscribers Only' }}
              </span>
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
                    : 'border-gray-200 hover:border-gray-300'"
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
                    : 'border-gray-200 hover:border-gray-300'"
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
            <div class="mt-6 pt-4 border-t border-gray-200">
              <CreditCost service="short_video" />
              <button
                @click="generateVideo"
                :disabled="!selectedDemoImageId || isProcessing"
                class="btn-primary w-full mt-4"
              >
                {{ isZh ? '查看結果' : 'View Result' }}
              </button>
            </div>
          </div>

          <!-- AI Model Selection - Subscriber Only -->
          <div class="card">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold text-dark-900">
                {{ isZh ? 'AI 模型選擇' : 'AI Model Selection' }}
              </h3>
              <span v-if="!isSubscribed" class="text-xs px-2 py-1 bg-amber-500/20 text-amber-400 rounded">
                {{ isZh ? '訂閱專屬' : 'Subscribers Only' }}
              </span>
            </div>

            <div :class="{ 'opacity-50 pointer-events-none': !isSubscribed }">
              <p class="text-sm text-dark-500 mb-3">
                {{ isZh ? '選擇不同的 AI 模型以獲得不同的生成效果' : 'Choose different AI models for different generation effects' }}
              </p>
              <div class="space-y-2">
                <button
                  v-for="model in aiModelOptions"
                  :key="model.id"
                  @click="isSubscribed && (selectedModel = model.id)"
                  class="w-full p-3 rounded-xl border-2 transition-all text-left flex items-center justify-between"
                  :class="selectedModel === model.id
                    ? 'border-primary-500 bg-primary-500/10'
                    : 'border-gray-200 hover:border-gray-300'"
                >
                  <div>
                    <p class="text-sm font-medium text-dark-900">{{ isZh ? model.nameZh : model.nameEn }}</p>
                    <p class="text-xs text-dark-400">{{ isZh ? model.descZh : model.descEn }}</p>
                    <p class="text-xs text-dark-400 mt-1">
                      {{ isZh ? `支援長度: ${model.lengths.join('s, ')}s` : `Lengths: ${model.lengths.join('s, ')}s` }}
                    </p>
                  </div>
                  <div v-if="model.badge" class="ml-2">
                    <span v-if="model.badge === 'default'" class="text-xs px-2 py-0.5 bg-gray-500/20 text-dark-500 rounded">Default</span>
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
        </div>

        <!-- Right Panel - Result -->
        <div class="card h-fit sticky top-24">
          <h3 class="text-lg font-semibold text-dark-900 mb-4">
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

          <div v-else class="aspect-video flex items-center justify-center bg-gray-100 rounded-xl text-dark-400">
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
