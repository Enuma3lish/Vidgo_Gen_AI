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

// Demo mode
const {
  isDemoUser,
  canUseCustomInputs,
  loadDemoTemplates,
  demoTemplates,
  isLoadingTemplates
} = useDemoMode()

// State
const clothingImage = ref<string | null>(null)
const selectedClothingId = ref<string | null>(null)
const modelImage = ref<string | null>(null)
const resultImage = ref<string | null>(null)
const isProcessing = ref(false)
const selectedModel = ref('female-1')

// Default model options (5 models for demo users)
const modelOptions = ref([
  { id: 'female-1', name: 'Female Model 1', name_zh: '女模特 1', preview: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&h=225&fit=crop' },
  { id: 'female-2', name: 'Female Model 2', name_zh: '女模特 2', preview: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150&h=225&fit=crop' },
  { id: 'female-3', name: 'Female Model 3', name_zh: '女模特 3', preview: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=150&h=225&fit=crop' },
  { id: 'male-1', name: 'Male Model 1', name_zh: '男模特 1', preview: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=225&fit=crop' },
  { id: 'male-2', name: 'Male Model 2', name_zh: '男模特 2', preview: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&h=225&fit=crop' }
])

// Default clothing items for demo users (from presets)
const demoClothingItems = computed(() => {
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
  await loadDemoTemplates('try_on')
})

function selectDemoClothing(item: { id: string; preview?: string; watermarked_result?: string }) {
  selectedClothingId.value = item.id
  clothingImage.value = item.preview || null
  resultImage.value = null
}

async function generateTryOn() {
  if (!clothingImage.value && !selectedClothingId.value) return

  isProcessing.value = true
  try {
    // For demo users with selected template, use cached result
    if (isDemoUser.value && selectedClothingId.value) {
      const template = demoTemplates.value.find(t => t.id === selectedClothingId.value)
      if (template?.result_watermarked_url) {
        resultImage.value = template.result_watermarked_url
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }
    }

    // For subscribed users or if no cached result
    let imageUrl = clothingImage.value

    // Upload if custom image
    if (clothingImage.value && !clothingImage.value.startsWith('http')) {
      const uploadResult = await demoApi.uploadImage(
        dataURItoBlob(clothingImage.value) as File
      )
      imageUrl = uploadResult.url
    }

    let modelUrl = null
    if (selectedModel.value === 'custom' && modelImage.value) {
      const modelUpload = await demoApi.uploadImage(
        dataURItoBlob(modelImage.value) as File
      )
      modelUrl = modelUpload.url
    }

    const result = await demoApi.generate({
      tool: 'virtual_try_on',
      image_url: imageUrl!,
      params: {
        model_id: selectedModel.value,
        model_image: modelUrl
      }
    })

    if (result.success && result.image_url) {
      resultImage.value = result.image_url
      if (result.credits_used) {
        creditsStore.deductCredits(result.credits_used)
      }
      uiStore.showSuccess(t('common.success'))
    }
  } catch (error) {
    uiStore.showError(isZh.value ? '生成失敗' : 'Generation failed')
  } finally {
    isProcessing.value = false
  }
}

function handleBack() {
  router.back()
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
        @click="handleBack"
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
          {{ t('tools.tryOn.name') }}
        </h1>
        <p class="text-xl text-gray-400">
          {{ t('tools.tryOn.longDesc') }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ isZh ? '訂閱以解鎖更多功能' : 'Subscribe to unlock more features' }}
          </RouterLink>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Left Panel - Clothing Selection -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">
            {{ isZh ? '選擇服裝' : 'Select Clothing' }}
          </h3>

          <!-- Demo Clothing Items -->
          <div v-if="isDemoUser || demoClothingItems.length > 0" class="mb-4">
            <p class="text-sm text-gray-400 mb-3">
              {{ isZh ? '預設服裝（示範）' : 'Preset Clothing (Demo)' }}
            </p>
            <div v-if="isLoadingTemplates" class="flex justify-center py-8">
              <div class="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
            </div>
            <div v-else class="grid grid-cols-2 gap-2">
              <button
                v-for="item in demoClothingItems"
                :key="item.id"
                @click="selectDemoClothing(item)"
                class="aspect-[3/4] rounded-lg overflow-hidden border-2 transition-all"
                :class="selectedClothingId === item.id
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
                  <span class="text-3xl">👔</span>
                </div>
              </button>
            </div>
          </div>

          <!-- PRESET-ONLY MODE: Custom upload REMOVED - all users use presets -->

          <!-- Selected Clothing Preview -->
          <div v-if="clothingImage" class="mt-4 space-y-2">
            <img :src="clothingImage" alt="Clothing" class="w-full rounded-xl" />
            <button
              v-if="canUseCustomInputs"
              @click="clothingImage = null; selectedClothingId = null"
              class="btn-ghost text-sm w-full"
            >
              {{ isZh ? '更換服裝' : 'Change Clothing' }}
            </button>
          </div>
        </div>

        <!-- Middle Panel - Model Selection -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">
            {{ isZh ? '選擇模特' : 'Select Model' }}
          </h3>

          <div class="grid grid-cols-2 gap-3">
            <button
              v-for="model in modelOptions"
              :key="model.id"
              @click="selectedModel = model.id"
              class="p-2 rounded-xl border-2 transition-all"
              :class="selectedModel === model.id
                ? 'border-primary-500 bg-primary-500/10'
                : 'border-dark-600 hover:border-dark-500'"
            >
              <div class="aspect-[2/3] rounded-lg overflow-hidden mb-2">
                <img :src="model.preview" :alt="isZh ? model.name_zh : model.name" class="w-full h-full object-cover" />
              </div>
              <p class="text-xs text-center text-white">{{ isZh ? model.name_zh : model.name }}</p>
            </button>

            <!-- PRESET-ONLY MODE: Custom model upload REMOVED -->
          </div>

          <!-- Credit Cost & Generate -->
          <div class="mt-6 pt-4 border-t border-dark-700">
            <CreditCost service="virtual_try_on" />
            <button
              @click="generateTryOn"
              :disabled="(!clothingImage && !selectedClothingId) || isProcessing"
              class="btn-primary w-full mt-4"
            >
              {{ t('common.generate') }}
            </button>
          </div>
        </div>

        <!-- Right Panel - Result -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">
            {{ isZh ? '試穿結果' : 'Try-On Result' }}
          </h3>

          <div v-if="resultImage" class="space-y-4">
            <img :src="resultImage" alt="Result" class="w-full rounded-xl" />

            <!-- Watermark badge -->
            <div class="text-center text-xs text-gray-500">vidgo.ai</div>

            <!-- PRESET-ONLY: Download blocked - show subscribe CTA -->
            <RouterLink to="/pricing" class="btn-primary w-full text-center block">
              {{ isZh ? '訂閱以獲得完整功能' : 'Subscribe for Full Access' }}
            </RouterLink>
          </div>

          <div v-else class="h-64 flex items-center justify-center text-gray-500">
            <div class="text-center">
              <span class="text-5xl block mb-4">👔</span>
              <p>{{ isZh ? '試穿結果將在此顯示' : 'Try-on result will appear here' }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
