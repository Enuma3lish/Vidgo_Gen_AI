<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { demoApi } from '@/api'
// PRESET-ONLY MODE: UploadZone removed - all users use presets

import LoadingOverlay from '@/components/common/LoadingOverlay.vue'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const isZh = computed(() => locale.value.startsWith('zh'))

// Demo mode
const {
  isDemoUser,
  loadDemoTemplates,
  demoTemplates
} = useDemoMode()

const uploadedImage = ref<string | null>(null)
const resultImage = ref<string | null>(null)
const isProcessing = ref(false)
const selectedBgType = ref<'transparent' | 'white' | 'custom'>('transparent')
const customBgColor = ref('#ffffff')

// Default images for demo users (5 examples) - with paired input/result URLs
// These should be pre-generated and stored in the static folder
const demoExamples = [
  {
    id: 'demo-1',
    input: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800',
    prompt: 'Remove the background from this product image',
    promptZh: '移除這張產品圖片的背景',
    result: null as string | null
  },
  {
    id: 'demo-2',
    input: 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800',
    prompt: 'Remove background and create transparent PNG',
    promptZh: '移除背景並創建透明PNG圖片',
    result: null as string | null
  },
  {
    id: 'demo-3',
    input: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800',
    prompt: 'Remove background from shoes image',
    promptZh: '移除鞋子圖片的背景',
    result: null as string | null
  },
  {
    id: 'demo-4',
    input: 'https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=800',
    prompt: 'Create clean product cutout with transparent background',
    promptZh: '創建乾淨的產品剪影，透明背景',
    result: null as string | null
  },
  {
    id: 'demo-5',
    input: 'https://images.unsplash.com/photo-1541643600914-78b084683601?w=800',
    prompt: 'Extract product from background for e-commerce',
    promptZh: '為電商提取產品，移除背景',
    result: null as string | null
  }
]

// Demo images from database
const selectedDemoIndex = ref<number>(0)

const demoImages = computed(() => {
  const templates = demoTemplates.value
    .filter(t => t.input_image_url)
    .map(t => ({
      id: t.id,
      input: t.input_image_url,
      result: t.result_watermarked_url || t.result_image_url
    }))
  return templates.length > 0 ? templates : demoExamples
})

// Load demo templates on mount
onMounted(async () => {
  await loadDemoTemplates('background_removal')

  // For demo users, auto-select first example
  if (isDemoUser.value && demoImages.value.length > 0) {
    uploadedImage.value = demoImages.value[0].input || null
  }
})

function selectDemoExample(index: number) {
  selectedDemoIndex.value = index
  const example = demoImages.value[index]
  if (example) {
    uploadedImage.value = example.input || null
    resultImage.value = null
  }
}



async function removeBackground() {
  if (!uploadedImage.value) return

  // Demo users cannot use custom background
  if (isDemoUser.value && selectedBgType.value === 'custom') {
    uiStore.showError(isZh.value ? '請訂閱以使用自訂背景' : 'Please subscribe to use custom background')
    return
  }

  isProcessing.value = true
  try {
    // For demo users, use cached result from database templates
    if (isDemoUser.value) {
      // First check if we have templates from database
      const selectedExample = demoImages.value[selectedDemoIndex.value]

      // Check for result_watermarked_url or result from database template
      if (selectedExample?.result) {
        // Simulate processing delay for demo effect
        await new Promise(resolve => setTimeout(resolve, 1500))
        resultImage.value = selectedExample.result
        uiStore.showSuccess(isZh.value ? '處理成功（示範）' : 'Processed successfully (Demo)')
        return
      }

      // Try to find matching template from loaded templates
      const matchingTemplate = demoTemplates.value.find(t =>
        t.id === selectedExample?.id ||
        t.input_image_url === uploadedImage.value
      )

      if (matchingTemplate?.result_watermarked_url || matchingTemplate?.result_image_url) {
        await new Promise(resolve => setTimeout(resolve, 1500))
        resultImage.value = matchingTemplate.result_watermarked_url || matchingTemplate.result_image_url || null
        uiStore.showSuccess(isZh.value ? '處理成功（示範）' : 'Processed successfully (Demo)')
        return
      }

      // No pre-generated result available - show demo preview
      // Use the input image as a preview with demo overlay message
      await new Promise(resolve => setTimeout(resolve, 1500))
      resultImage.value = uploadedImage.value
      uiStore.showInfo(isZh.value ? '這是示範預覽，訂閱後可使用完整去背功能' : 'This is a demo preview. Subscribe for full background removal.')
      return
    }

    // Upload image first
    const uploadResult = await demoApi.uploadImage(
      dataURItoBlob(uploadedImage.value) as File
    )

    // Call generate API
    const result = await demoApi.generate({
      tool: 'background_removal',
      image_url: uploadResult.url,
      params: {
        bg_type: selectedBgType.value,
        bg_color: selectedBgType.value === 'custom' ? customBgColor.value : null
      }
    })

    if (result.success && result.image_url) {
      resultImage.value = result.image_url
      creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success'))
    } else {
      uiStore.showError(result.message || 'Processing failed')
    }
  } catch (error) {
    uiStore.showError('An error occurred while processing')
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
    <LoadingOverlay :show="isProcessing" :message="t('common.processing')" />

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
          {{ t('tools.backgroundRemoval.name') }}
        </h1>
        <p class="text-xl text-gray-400">
          {{ t('tools.backgroundRemoval.longDesc') }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ isZh ? '訂閱以解鎖更多功能' : 'Subscribe to unlock more features' }}
          </RouterLink>
        </div>
      </div>

      <!-- PRESET-ONLY MODE: All users see the same preset-based layout -->
      <div class="space-y-8">
        <!-- Example Selection -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">
            {{ isZh ? '選擇範例圖片' : 'Select Example Image' }}
          </h3>
          <div class="grid grid-cols-5 gap-3">
            <button
              v-for="(example, idx) in demoImages"
              :key="example.id || idx"
              @click="selectDemoExample(idx)"
              class="aspect-square rounded-lg overflow-hidden border-2 transition-all"
              :class="selectedDemoIndex === idx
                ? 'border-primary-500 ring-2 ring-primary-500/50'
                : 'border-dark-600 hover:border-dark-500'"
            >
              <img
                :src="example.input"
                alt="Example"
                class="w-full h-full object-cover"
              />
            </button>
          </div>
        </div>

        <!-- Input and Result Side by Side -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
          <!-- Input -->
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-4">
              {{ isZh ? '原始圖片' : 'Original Image' }}
            </h3>
            <div v-if="uploadedImage" class="rounded-xl overflow-hidden">
              <img :src="uploadedImage" alt="Original" class="w-full" />
            </div>
            <div v-else class="h-64 flex items-center justify-center bg-dark-700 rounded-xl">
              <span class="text-gray-500">{{ isZh ? '請選擇圖片' : 'Select an image' }}</span>
            </div>
          </div>

          <!-- Result -->
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-4">
              {{ isZh ? '去背結果' : 'Result' }}
            </h3>
            <div v-if="resultImage" class="space-y-4">
              <div class="rounded-xl overflow-hidden bg-checkered relative">
                <img :src="resultImage" alt="Result" class="w-full" />
              </div>

              <!-- Watermark badge -->
              <div class="text-center text-xs text-gray-500">vidgo.ai</div>

              <!-- PRESET-ONLY: Download blocked - show subscribe CTA -->
              <RouterLink
                to="/pricing"
                class="btn-primary w-full text-center block"
              >
                {{ isZh ? '訂閱以獲得完整功能' : 'Subscribe for Full Access' }}
              </RouterLink>
            </div>
            <div v-else class="h-64 flex items-center justify-center bg-dark-700 rounded-xl">
              <span class="text-gray-500">{{ isZh ? '點擊下方按鈕去除背景' : 'Click button below to remove background' }}</span>
            </div>
          </div>
        </div>

        <!-- Remove Button -->
        <div class="flex justify-center">
          <button
            @click="removeBackground"
            :disabled="!uploadedImage || isProcessing"
            class="btn-primary px-12 py-4 text-lg font-semibold"
          >
            <span v-if="isProcessing" class="flex items-center gap-2">
              <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              {{ t('common.processing') }}
            </span>
            <span v-else class="flex items-center gap-2">
              <span>✨</span>
              {{ isZh ? '去除背景' : 'Remove Background' }}
            </span>
          </button>
        </div>
      </div>
      <!-- PRESET-ONLY MODE: Subscribed user layout REMOVED - all users use presets -->
    </div>
  </div>
</template>

<style scoped>
.bg-checkered {
  background-image: linear-gradient(45deg, #374151 25%, transparent 25%),
    linear-gradient(-45deg, #374151 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #374151 75%),
    linear-gradient(-45deg, transparent 75%, #374151 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
  background-color: #1f2937;
}
</style>
