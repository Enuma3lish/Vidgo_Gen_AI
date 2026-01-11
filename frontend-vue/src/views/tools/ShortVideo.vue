<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { demoApi } from '@/api'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const isZh = computed(() => locale.value.startsWith('zh'))

// PRESET-ONLY MODE: All users use presets, no custom input
const {
  isDemoUser,
  canUseCustomInputs,
  loadDemoTemplates,
  demoTemplates,
  isLoadingTemplates
} = useDemoMode()

const uploadedImage = ref<string | null>(null)
const resultVideo = ref<string | null>(null)
const isProcessing = ref(false)
// prompt is readonly in preset-only mode - users select from presets
const selectedDuration = ref(5)
const selectedMotion = ref('auto')

const durationOptions = [3, 5, 10]

const motionOptions = [
  { id: 'auto', name: 'Auto', desc: 'AI decides motion' },
  { id: 'zoom-in', name: 'Zoom In', desc: 'Gradual zoom effect' },
  { id: 'zoom-out', name: 'Zoom Out', desc: 'Pull back effect' },
  { id: 'pan-left', name: 'Pan Left', desc: 'Horizontal movement' },
  { id: 'pan-right', name: 'Pan Right', desc: 'Horizontal movement' },
  { id: 'rotate', name: 'Rotate', desc: 'Circular motion' }
]

// Demo images for demo users
const selectedDemoImageId = ref<string | null>(null)

const demoImages = computed(() => {
  return demoTemplates.value
    .filter(t => t.input_image_url)
    .map(t => ({
      id: t.id,
      name: isZh.value ? (t.prompt_zh || t.prompt) : t.prompt,
      preview: t.input_image_url,
      watermarked_result: t.result_watermarked_url
    }))
})

// Load demo presets on mount
onMounted(async () => {
  await loadDemoTemplates('short_video')
})

function selectDemoImage(item: { id: string; preview?: string }) {
  selectedDemoImageId.value = item.id
  uploadedImage.value = item.preview || null
  resultVideo.value = null
}



async function generateVideo() {
  if (!uploadedImage.value) {
    uiStore.showError('Please upload an image')
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
        motion: selectedMotion.value
      }
    })

    if (result.success && result.video_url) {
      resultVideo.value = result.video_url
      creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success'))
    }
  } catch (error) {
    uiStore.showError('Generation failed')
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
  <div class="min-h-screen pt-24 pb-20">
    <LoadingOverlay :show="isProcessing" :message="'Generating video... This may take a few minutes'" />

    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Back Button -->
      <button
        @click="router.back()"
        class="mb-6 flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        {{ t('common.back') }}
      </button>

      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-white mb-4">
          {{ t('tools.shortVideo.name') }}
        </h1>
        <p class="text-xl text-gray-400">
          {{ t('tools.shortVideo.longDesc') }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ isZh ? '訂閱以解鎖更多功能' : 'Subscribe to unlock more features' }}
          </RouterLink>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Left Panel - Input -->
        <div class="space-y-6">
          <!-- Source Selection -->
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-4">Source Image (Optional)</h3>

            <!-- Demo Images for demo users -->
            <div v-if="isDemoUser || demoImages.length > 0" class="mb-4">
              <p class="text-sm text-gray-400 mb-3">
                {{ isZh ? '預設圖片（示範）' : 'Preset Images (Demo)' }}
              </p>
              <div v-if="isLoadingTemplates" class="flex justify-center py-8">
                <div class="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
              </div>
              <div v-else class="grid grid-cols-2 gap-2">
                <button
                  v-for="item in demoImages"
                  :key="item.id"
                  @click="selectDemoImage(item)"
                  class="aspect-video rounded-lg overflow-hidden border-2 transition-all"
                  :class="selectedDemoImageId === item.id
                    ? 'border-primary-500'
                    : 'border-dark-600 hover:border-dark-500'"
                >
                  <img
                    v-if="item.preview"
                    :src="item.preview"
                    :alt="item.name"
                    class="w-full h-full object-cover"
                  />
                  <div v-else class="w-full h-full bg-dark-700 flex items-center justify-center">
                    <span class="text-3xl">🎬</span>
                  </div>
                </button>
              </div>
            </div>

            <!-- PRESET-ONLY MODE: Custom upload REMOVED - all users use presets -->

            <!-- Selected Image Preview -->
            <div v-if="uploadedImage" class="space-y-4 mt-4">
              <img :src="uploadedImage" alt="Source" class="w-full rounded-xl" />
              <button v-if="canUseCustomInputs" @click="uploadedImage = null; selectedDemoImageId = null" class="btn-ghost text-sm w-full">
                {{ isZh ? '移除圖片' : 'Remove Image' }}
              </button>
            </div>
          </div>

          <!-- PRESET-ONLY MODE: No custom prompt input -->
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-4">
              {{ isZh ? '選擇預設風格' : 'Select Preset Style' }}
            </h3>

            <!-- PRESET-ONLY Notice -->
            <div class="mb-4 p-3 bg-primary-500/10 border border-primary-500/20 rounded-lg">
              <p class="text-sm text-primary-400">
                {{ isZh ? '從上方預設圖片中選擇一個來查看效果' : 'Select a preset image above to see the result' }}
              </p>
            </div>

            <!-- Custom prompt input REMOVED in preset-only mode -->
          </div>

          <!-- Settings -->
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-4">Video Settings</h3>

            <!-- Duration -->
            <div class="mb-6">
              <label class="label">Duration</label>
              <div class="flex gap-3">
                <button
                  v-for="dur in durationOptions"
                  :key="dur"
                  @click="selectedDuration = dur"
                  class="flex-1 py-3 rounded-xl border-2 transition-all"
                  :class="selectedDuration === dur
                    ? 'border-primary-500 bg-primary-500/10'
                    : 'border-dark-600 hover:border-dark-500'"
                >
                  {{ dur }}s
                </button>
              </div>
            </div>

            <!-- Motion Type -->
            <div>
              <label class="label">Motion Type</label>
              <div class="grid grid-cols-3 gap-2">
                <button
                  v-for="motion in motionOptions"
                  :key="motion.id"
                  @click="selectedMotion = motion.id"
                  class="p-3 rounded-xl border-2 transition-all text-center"
                  :class="selectedMotion === motion.id
                    ? 'border-primary-500 bg-primary-500/10'
                    : 'border-dark-600 hover:border-dark-500'"
                >
                  <p class="text-sm font-medium">{{ motion.name }}</p>
                </button>
              </div>
            </div>

            <!-- Credit Cost & Generate -->
            <div class="mt-6 pt-4 border-t border-dark-700">
              <CreditCost service="short_video" />
              <button
                @click="generateVideo"
                :disabled="!uploadedImage || isProcessing"
                class="btn-primary w-full mt-4"
              >
                {{ t('common.generate') }}
              </button>
            </div>
          </div>
        </div>

        <!-- Right Panel - Result -->
        <div class="card h-fit sticky top-24">
          <h3 class="text-lg font-semibold text-white mb-4">Generated Video</h3>

          <div v-if="resultVideo" class="space-y-4">
            <video
              :src="resultVideo"
              controls
              class="w-full rounded-xl"
              autoplay
              loop
            />
            <!-- Watermark badge -->
            <div class="text-center text-xs text-gray-500">vidgo.ai</div>
            <!-- PRESET-ONLY: Download blocked - show subscribe CTA -->
            <RouterLink to="/pricing" class="btn-primary w-full text-center block">
              {{ isZh ? '訂閱以獲得完整功能' : 'Subscribe for Full Access' }}
            </RouterLink>
          </div>

          <div v-else class="aspect-video flex items-center justify-center bg-dark-700 rounded-xl text-gray-500">
            <div class="text-center">
              <span class="text-5xl block mb-4">🎬</span>
              <p>Generated video will appear here</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
