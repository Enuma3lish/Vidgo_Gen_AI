<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { toolsApi } from '@/api'
import ImageUploader from '@/components/common/ImageUploader.vue'
import CreditCost from '@/components/tools/CreditCost.vue'

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
  dbEmpty,
  resolveDemoTemplateResultUrl,
  generateOnDemand
} = useDemoMode()

const uploadedImage = ref<string | undefined>(undefined)
const resultImage = ref<string | null>(null)
const isProcessing = ref(false)
// True when a demo user clicked Generate but the selected tile isn't backed
// by a real Material DB preset (db_empty fallback or missing preset id).
// Surfaces a persistent in-block message instead of a silent no-op.
const demoEmptyState = ref(false)
const selectedBgType = ref<'transparent' | 'white' | 'custom'>('transparent')

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


// Static fallback examples (shown when backend DB is empty)
const STATIC_BG_EXAMPLES = [
  {
    id: 'static-bg-1',
    input: 'https://images.unsplash.com/photo-1585386959984-a4155224a1ad?w=600&fit=crop',
    result: 'https://images.unsplash.com/photo-1585386959984-a4155224a1ad?w=600&fit=crop&bg=transparent',
    label: 'Skincare Bottle'
  },
  {
    id: 'static-bg-2',
    input: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&fit=crop',
    result: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&fit=crop',
    label: 'Watch'
  },
  {
    id: 'static-bg-3',
    input: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&fit=crop',
    result: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&fit=crop',
    label: 'Sneakers'
  },
  {
    id: 'static-bg-4',
    input: 'https://images.unsplash.com/photo-1491553895911-0055eca6402d?w=600&fit=crop',
    result: 'https://images.unsplash.com/photo-1491553895911-0055eca6402d?w=600&fit=crop',
    label: 'Running Shoes'
  },
  {
    id: 'static-bg-5',
    input: 'https://images.unsplash.com/photo-1560343090-f0409e92791a?w=600&fit=crop',
    result: 'https://images.unsplash.com/photo-1560343090-f0409e92791a?w=600&fit=crop',
    label: 'Sneaker Pair'
  },
  {
    id: 'static-bg-6',
    input: 'https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=600&fit=crop',
    result: 'https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=600&fit=crop',
    label: 'Camera'
  }
]

const effectiveDemoImages = computed(() =>
  demoImages.value.length > 0 ? demoImages.value : STATIC_BG_EXAMPLES
)

// Load demo templates on mount
onMounted(async () => {
  isLoadingTemplates.value = true
  await loadDemoTemplates('background_removal', undefined, locale.value)
  isLoadingTemplates.value = false

  // For demo users, auto-select first example
  const effective = demoImages.value.length > 0 ? demoImages.value : STATIC_BG_EXAMPLES
  if (isDemoUser.value && effective.length > 0) {
    uploadedImage.value = effective[0].input || undefined
  }
})

function selectDemoExample(index: number) {
  selectedDemoIndex.value = index
  const effective2 = demoImages.value.length > 0 ? demoImages.value : STATIC_BG_EXAMPLES
  const example = effective2[index]
  if (example) {
    uploadedImage.value = example.input || undefined
    resultImage.value = null
    demoEmptyState.value = false
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
    // For demo users, resolve the selected preset through backend lookup
    if (isDemoUser.value) {
      await new Promise(resolve => setTimeout(resolve, 1500))

      const selectedTemplateId = demoImages.value[selectedDemoIndex.value]?.id
      if (selectedTemplateId) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(selectedTemplateId)
        if (demoResultUrl) {
          resultImage.value = demoResultUrl
          uiStore.showSuccess(isZh.value ? '處理成功（示範）' : 'Processed successfully (Demo)')
          return
        }
      }

      // VG-BUG-010 fix: no cached result — call cache-through endpoint.
      uiStore.showInfo(isZh.value ? '此圖片尚未生成結果，正在為您即時處理...' : 'Generating in real-time...')
      const onDemandUrl = await generateOnDemand('background_removal')
      if (onDemandUrl) {
        resultImage.value = onDemandUrl
        uiStore.showSuccess(isZh.value ? '處理成功' : 'Processed successfully')
        return
      }
      demoEmptyState.value = true
      uiStore.showError(isZh.value ? '生成服務暫時無法使用，請稍後再試或訂閱解鎖完整功能' : 'Generation service temporarily unavailable. Please try again later or subscribe.')
      return
    }

    // Upload image first
    let uploadUrl = uploadedImage.value
    if (uploadedImage.value.startsWith('data:')) {
      const blob = dataURItoBlob(uploadedImage.value)
      if (!blob) {
        uiStore.showError(isZh.value ? '圖片格式無效，請重新上傳' : 'Invalid image format. Please re-upload.')
        return
      }
      const uploadResult = await toolsApi.uploadImage(blob as File)
      uploadUrl = uploadResult.url
    }
    const uploadResult = { url: uploadUrl }

    // Call tools API for background removal
    const result = await toolsApi.removeBackground(uploadResult.url, 'png')

    if (result.success && (result.image_url || result.result_url)) {
      resultImage.value = result.image_url || result.result_url || null
      creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success'))
    } else {
      uiStore.showError(result.message || 'Processing failed')
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail || error?.response?.data?.message || error?.message || ''
    uiStore.showError(detail || (isZh.value ? '處理失敗，請稍後再試' : 'Processing failed. Please try again.'))
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
    <LoadingOverlay :show="isProcessing" :message="t('common.processing')" />

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
          {{ t('tools.backgroundRemoval.name') }}
        </h1>
        <p class="text-xl text-dark-300">
          {{ t('tools.backgroundRemoval.longDesc') }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ isZh ? '訂閱以解鎖更多功能' : 'Subscribe to unlock more features' }}
          </RouterLink>
        </div>

        <!-- DB Empty: Show try prompts -->
        <div v-if="dbEmpty && tryPrompts.length > 0" class="mt-6 p-4 rounded-xl" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <p class="text-sm text-dark-200 mb-2">{{ isZh ? '可試玩提示詞（資料庫尚無預生成）' : 'Try prompts (no pre-generated results yet)' }}</p>
          <div class="flex flex-wrap gap-2">
            <span v-for="p in tryPrompts.slice(0, 5)" :key="p.id" class="px-2 py-1 rounded text-xs bg-dark-800 text-dark-200">{{ p.prompt }}</span>
          </div>
        </div>
      </div>

      <!-- PRESET-ONLY MODE: All users see the same preset-based layout -->
      <div class="space-y-8">
        <!-- Example Selection (Demo Users) -->
        <div v-if="isDemoUser || effectiveDemoImages.length > 0" class="card">
          <h3 class="text-lg font-semibold text-dark-50 mb-4">
            {{ isZh ? '選擇範例圖片' : 'Select Example Image' }}
          </h3>
          <div v-if="isLoadingTemplates" class="flex justify-center py-8">
            <div class="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
          </div>
          <div v-else-if="effectiveDemoImages.length === 0" class="text-center py-8 text-dark-400">
            <span class="text-3xl block mb-2">📷</span>
            <p class="text-sm">{{ isZh ? '範例圖片準備中，請稍後再試' : 'Example images loading, please try again later' }}</p>
          </div>
          <div v-else class="grid grid-cols-5 gap-3">
            <button
              v-for="(example, idx) in effectiveDemoImages"
              :key="example.id || idx"
              @click="selectDemoExample(idx)"
              class="aspect-square rounded-lg overflow-hidden border-2 transition-all"
              :class="selectedDemoIndex === idx && uploadedImage === example.input
                ? 'border-primary-500 ring-2 ring-primary-500/50'
                : 'hover:border-dark-500'" style="border-color: rgba(255,255,255,0.08);">
            >
              <img
                :src="example.input"
                alt="Example"
                class="w-full h-full object-cover"
              />
            </button>
          </div>
        </div>

        <!-- Custom Upload (Paid Users) -->
        <div v-if="!isDemoUser" class="card mt-4">
          <h3 class="text-lg font-semibold text-dark-50 mb-4">
            {{ isZh ? '上傳圖片' : 'Upload Image' }}
          </h3>
          <ImageUploader 
            v-model="uploadedImage" 
            :label="isZh ? '點擊上傳或拖放圖片' : 'Drop image here'"
          />
        </div>

        <!-- Input and Result Side by Side -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mt-4">
          <!-- Input -->
          <div class="card">
            <h3 class="text-lg font-semibold text-dark-50 mb-4">
              {{ isZh ? '原始圖片' : 'Original Image' }}
            </h3>
            <div v-if="uploadedImage" class="rounded-xl overflow-hidden">
              <img :src="uploadedImage" alt="Original" class="w-full" />
            </div>
            <div v-else class="h-64 flex items-center justify-center rounded-xl" style="background: #141420;">
              <span class="text-dark-400">{{ isZh ? '請選擇圖片' : 'Select an image' }}</span>
            </div>
          </div>

          <!-- Result -->
          <div class="card">
            <h3 class="text-lg font-semibold text-dark-50 mb-4">
              {{ isZh ? '去背結果' : 'Result' }}
            </h3>
            <div v-if="resultImage" class="space-y-4">
              <div class="rounded-xl overflow-hidden bg-checkered relative">
                <img :src="resultImage" alt="Result" class="w-full" />
              </div>

              <!-- Watermark badge -->
              <div class="text-center text-xs text-dark-400">vidgo.ai</div>

              <!-- Paid users: Download button -->
              <a
                v-if="!isDemoUser && resultImage"
                :href="resultImage"
                download="vidgo-bg-removed.png"
                class="btn-primary w-full text-center block"
              >
                {{ isZh ? '下載結果' : 'Download Result' }}
              </a>
              <!-- Demo users: Subscribe CTA -->
              <RouterLink
                v-else
                to="/pricing"
                class="btn-primary w-full text-center block"
              >
                {{ isZh ? '訂閱以獲得完整功能' : 'Subscribe for Full Access' }}
              </RouterLink>
            </div>
            <div v-else-if="demoEmptyState" class="h-64 flex flex-col items-center justify-center rounded-xl text-center px-6 gap-3" style="background: #141420; border: 1px solid rgba(255,255,255,0.08);">
              <span class="text-2xl">🔒</span>
              <p class="text-sm text-dark-200">
                {{ isZh ? '此範例尚未預生成結果' : 'No pre-generated result for this example yet' }}
              </p>
              <RouterLink to="/pricing" class="btn-primary text-sm px-4 py-2">
                {{ isZh ? '訂閱以使用完整 AI 功能' : 'Subscribe to use the real AI' }}
              </RouterLink>
            </div>
            <div v-else class="h-64 flex items-center justify-center rounded-xl" style="background: #141420;">
              <span class="text-dark-400">{{ isZh ? '點擊下方按鈕去除背景' : 'Click button below to remove background' }}</span>
            </div>
          </div>
        </div>

        <!-- Remove Button and Credit Cost -->
        <div class="flex flex-col items-center gap-4 mt-6 pt-6" style="border-top: 1px solid rgba(255,255,255,0.06);">
          <CreditCost service="background_removal" />
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
