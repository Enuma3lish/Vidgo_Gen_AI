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
  demoTemplates,
  tryPrompts,
  dbEmpty
} = useDemoMode()

const uploadedImage = ref<string | null>(null)
const resultImage = ref<string | null>(null)
const isProcessing = ref(false)
const selectedBgType = ref<'transparent' | 'white' | 'custom'>('transparent')
const customBgColor = ref('#ffffff')

// Demo images from database only (no hardcoded fallbacks)
const selectedDemoIndex = ref<number>(0)
const isLoadingTemplates = ref(true)

const demoImages = computed(() => {
  return demoTemplates.value
    .filter(t => t.input_image_url)
    .map(t => ({
      id: t.id,
      input: t.input_image_url,
      result: t.result_watermarked_url || t.result_image_url
    }))
})

// Load demo templates on mount
onMounted(async () => {
  isLoadingTemplates.value = true
  await loadDemoTemplates('background_removal', undefined, locale.value)
  isLoadingTemplates.value = false

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
      // Simulate processing delay for demo effect
      await new Promise(resolve => setTimeout(resolve, 1500))

      // First check if we have result for the selected example
      const selectedExample = demoImages.value[selectedDemoIndex.value]

      // Check if the selected example has a pre-paired result
      if (selectedExample?.result) {
        resultImage.value = selectedExample.result
        uiStore.showSuccess(isZh.value ? '處理成功（示範）' : 'Processed successfully (Demo)')
        return
      }

      // Try to find matching template from loaded templates by ID first (exact match)
      const matchingTemplate = demoTemplates.value.find(t =>
        t.id === selectedExample?.id
      )

      if (matchingTemplate?.result_watermarked_url || matchingTemplate?.result_image_url) {
        resultImage.value = matchingTemplate.result_watermarked_url || matchingTemplate.result_image_url || null
        uiStore.showSuccess(isZh.value ? '處理成功（示範）' : 'Processed successfully (Demo)')
        return
      }

      // Then try to match by input_image_url (exact match only)
      const matchByInput = demoTemplates.value.find(t =>
        t.input_image_url === selectedExample?.input
      )

      if (matchByInput?.result_watermarked_url || matchByInput?.result_image_url) {
        resultImage.value = matchByInput.result_watermarked_url || matchByInput.result_image_url || null
        uiStore.showSuccess(isZh.value ? '處理成功（示範）' : 'Processed successfully (Demo)')
        return
      }

      // No pre-generated result available - show info message (NOT the input image as fake result)
      uiStore.showInfo(isZh.value ? '此圖片尚未生成結果，請訂閱以使用完整功能' : 'This image is not pre-generated. Subscribe for full features.')
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

        <!-- DB Empty: Show try prompts -->
        <div v-if="dbEmpty && tryPrompts.length > 0" class="mt-6 p-4 rounded-xl bg-dark-700/50 border border-dark-600">
          <p class="text-sm text-gray-300 mb-2">{{ isZh ? '可試玩提示詞（資料庫尚無預生成）' : 'Try prompts (no pre-generated results yet)' }}</p>
          <div class="flex flex-wrap gap-2">
            <span v-for="p in tryPrompts.slice(0, 5)" :key="p.id" class="px-2 py-1 rounded text-xs bg-dark-800 text-gray-300">{{ p.prompt }}</span>
          </div>
        </div>
      </div>

      <!-- PRESET-ONLY MODE: All users see the same preset-based layout -->
      <div class="space-y-8">
        <!-- Example Selection -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">
            {{ isZh ? '選擇範例圖片' : 'Select Example Image' }}
          </h3>
          <div v-if="isLoadingTemplates" class="flex justify-center py-8">
            <div class="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
          </div>
          <div v-else-if="demoImages.length === 0" class="text-center py-8 text-gray-500">
            <span class="text-3xl block mb-2">📷</span>
            <p class="text-sm">{{ isZh ? '範例圖片準備中，請稍後再試' : 'Example images loading, please try again later' }}</p>
          </div>
          <div v-else class="grid grid-cols-5 gap-3">
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
