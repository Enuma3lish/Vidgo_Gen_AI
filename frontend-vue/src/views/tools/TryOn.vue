<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { demoApi } from '@/api'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'

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
  isLoadingTemplates,
  tryPrompts,
  dbEmpty
} = useDemoMode()

// State
const clothingImage = ref<string | undefined>(undefined)
const selectedClothingId = ref<string | null>(null)
const modelImage = ref<string | undefined>(undefined)
const resultImage = ref<string | null>(null)
const isProcessing = ref(false)
const selectedModel = ref('female-1')

// Default model options (6 models matching backend generate_model_library() naming)
const modelOptions = ref([
  { id: 'female-1', name: 'Female Model 1', name_zh: '女模特 1', preview: 'https://images.unsplash.com/photo-1615262239828-5a7d7b6e5e0a?w=200&h=300&fit=crop&crop=faces' },
  { id: 'female-2', name: 'Female Model 2', name_zh: '女模特 2', preview: 'https://images.unsplash.com/photo-1566589430181-7a3e3d6d4e8b?w=200&h=300&fit=crop&crop=faces' },
  { id: 'female-3', name: 'Female Model 3', name_zh: '女模特 3', preview: 'https://images.unsplash.com/photo-1614387256720-e00e2a5a7e0a?w=200&h=300&fit=crop&crop=faces' },
  { id: 'male-1', name: 'Male Model 1', name_zh: '男模特 1', preview: 'https://images.unsplash.com/photo-1643990081716-e0c8a7c3c4b1?w=200&h=300&fit=crop&crop=faces' },
  { id: 'male-2', name: 'Male Model 2', name_zh: '男模特 2', preview: 'https://images.unsplash.com/photo-1634843824979-e0b7c4e3e0a1?w=200&h=300&fit=crop&crop=faces' },
  { id: 'male-3', name: 'Male Model 3', name_zh: '男模特 3', preview: 'https://images.unsplash.com/photo-1560250097-0b93528c311a?w=200&h=300&fit=crop&crop=faces' }
])

// Clothing types that are restricted for male models
const femaleOnlyClothingTypes = ['dress', 'skirt', 'short_skirt', 'mini_skirt']

// Check if selected model is male
const isMaleModel = computed(() => selectedModel.value.startsWith('male'))

// Get unique clothing items from database (grouped by clothing_id)
// Each clothing item may have multiple results for different models
const demoClothingItems = computed(() => {
  // Group templates by clothing_id to get unique clothing items
  const clothingMap = new Map<string, {
    id: string
    name: string
    preview: string
    clothingType: string
    genderRestriction: string | null
  }>()

  demoTemplates.value
    .filter(t => t.input_image_url)
    .forEach(t => {
      const params = (t as any).input_params || {}
      const clothingId = params.clothing_id || t.id

      // Only add if not already in map (to avoid duplicates)
      if (!clothingMap.has(clothingId)) {
        // Get clothing type from input_params (set by backend) or detect from prompt
        let clothingType = params.clothing_type || 'general'
        if (clothingType === 'general') {
          // Fallback: detect from prompt/style_tags
          const prompt = (t.prompt || '').toLowerCase()
          const promptZh = (t.prompt_zh || '').toLowerCase()
          const styleTags = (t.style_tags || []).map((tag: string) => tag.toLowerCase())

          if (prompt.includes('dress') || promptZh.includes('裙') || promptZh.includes('洋裝') ||
              styleTags.some((tag: string) => tag.includes('dress'))) {
            clothingType = 'dress'
          } else if (prompt.includes('skirt') || promptZh.includes('短裙') || promptZh.includes('裙子') ||
              styleTags.some((tag: string) => tag.includes('skirt'))) {
            clothingType = 'skirt'
          }
        }

        clothingMap.set(clothingId, {
          id: clothingId,
          name: isZh.value ? (t.prompt_zh || t.prompt) : t.prompt,
          preview: t.input_image_url || '',
          clothingType,
          genderRestriction: params.gender_restriction || null
        })
      }
    })

  return Array.from(clothingMap.values())
})

// Fallback clothing items from try_prompts (when DB is empty)
const fallbackClothingItems = computed(() => {
  if (!dbEmpty.value || tryPrompts.value.length === 0) return []
  return tryPrompts.value.map((p: any) => ({
    id: p.id,
    name: p.prompt,
    preview: p.image_url || '',
    clothingType: p.clothing_type || 'general',
    genderRestriction: null
  }))
})

// Display items: use DB items if available, otherwise fallback from try_prompts, then STATIC_CLOTHING
const displayClothingItems = computed(() => {
  if (demoClothingItems.value.length > 0) return demoClothingItems.value
  if (fallbackClothingItems.value.length > 0) return fallbackClothingItems.value
  // Last resort: static clothing images
  return STATIC_CLOTHING.map(c => ({
    id: c.id,
    name: c.label,
    preview: c.url,
    clothingType: 'general',
    genderRestriction: null
  }))
})

// Get selected clothing type
const selectedClothingType = computed(() => {
  if (!selectedClothingId.value) return null
  const item = displayClothingItems.value.find(c => c.id === selectedClothingId.value)
  return item?.clothingType || 'general'
})

// Check if current combination is valid (male + dress/skirt = invalid)
const isValidCombination = computed(() => {
  if (!selectedClothingType.value) return true
  if (isMaleModel.value && femaleOnlyClothingTypes.includes(selectedClothingType.value)) {
    return false
  }
  return true
})


// Static clothing fallback images (shown when backend DB is empty)
const STATIC_CLOTHING = [
  { id: 'c1', url: 'https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=400&fit=crop', label: 'White Blouse' },
  { id: 'c2', url: 'https://images.unsplash.com/photo-1594938298603-c8148c4b4357?w=400&fit=crop', label: 'Blue Dress' },
  { id: 'c3', url: 'https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=400&fit=crop', label: 'Denim Jacket' },
  { id: 'c4', url: 'https://images.unsplash.com/photo-1578587018452-892bacefd3f2?w=400&fit=crop', label: 'Floral Dress' },
  { id: 'c5', url: 'https://images.unsplash.com/photo-1542272604-787c3835535d?w=400&fit=crop', label: 'Jeans' },
  { id: 'c6', url: 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400&fit=crop', label: 'White T-Shirt' }
]

// Load demo presets on mount
onMounted(async () => {
  await loadDemoTemplates('try_on')
})

function selectDemoClothing(item: { id: string; preview?: string; watermarked_result?: string }) {
  selectedClothingId.value = item.id
  clothingImage.value = item.preview || undefined
  resultImage.value = null
}

async function generateTryOn() {
  if (!clothingImage.value && !selectedClothingId.value) return

  // Validate: Male models cannot wear dresses/skirts
  if (!isValidCombination.value) {
    uiStore.showError(isZh.value
      ? '男性模特不能穿著裙子或洋裝，請選擇其他服裝或女性模特'
      : 'Male models cannot wear dresses or skirts. Please select different clothing or a female model.')
    return
  }

  isProcessing.value = true
  try {
    // For demo users, find the result matching BOTH model AND clothing
    if (isDemoUser.value && selectedClothingId.value) {
      // Simulate processing delay for demo effect
      await new Promise(resolve => setTimeout(resolve, 1500))

      // Find template matching the selected model AND clothing combination
      const template = demoTemplates.value.find(t => {
        const params = (t as any).input_params || {}
        const matchesClothing = params.clothing_id === selectedClothingId.value
        const matchesModel = params.model_id === selectedModel.value
        return matchesClothing && matchesModel && (t.result_watermarked_url || t.result_image_url)
      })

      if (template?.result_watermarked_url || template?.result_image_url) {
        resultImage.value = template.result_watermarked_url || template.result_image_url || null
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }

      // Fallback: Find any template with this clothing (different model is OK for demo)
      const fallbackTemplate = demoTemplates.value.find(t => {
        const params = (t as any).input_params || {}
        return params.clothing_id === selectedClothingId.value && (t.result_watermarked_url || t.result_image_url)
      })

      if (fallbackTemplate?.result_watermarked_url || fallbackTemplate?.result_image_url) {
        resultImage.value = fallbackTemplate.result_watermarked_url || fallbackTemplate.result_image_url || null
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }

      // No pre-generated result available
      if (dbEmpty.value) {
        uiStore.showInfo(isZh.value ? '預覽模式：此服裝尚未生成試穿結果，訂閱以使用完整功能' : 'Preview mode: Try-on results not yet generated. Subscribe for full features.')
      } else {
        uiStore.showInfo(isZh.value ? '此組合尚未生成，請訂閱以使用完整功能' : 'This combination is not pre-generated. Subscribe for full features.')
      }
      return
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
  <div class="min-h-screen pt-24 bg-white pb-20">
    <LoadingOverlay :show="isProcessing" :message="t('common.processing')" />

    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Back Button -->
      <button
        @click="handleBack"
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
          {{ t('tools.tryOn.name') }}
        </h1>
        <p class="text-xl text-dark-500">
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
          <h3 class="text-lg font-semibold text-dark-900 mb-4">
            {{ isZh ? '選擇服裝' : 'Select Clothing' }}
          </h3>

          <!-- DB Empty Info Banner (prominent preview mode notice) -->
          <div v-if="dbEmpty" class="mb-4 p-4 bg-amber-500/15 border border-amber-500/40 rounded-lg">
            <div class="flex items-start gap-3">
              <span class="text-amber-400 text-lg mt-0.5">&#x1F441;</span>
              <div>
                <p class="text-sm font-medium text-amber-300 mb-1">
                  {{ isZh ? '預覽模式' : 'Preview Mode' }}
                </p>
                <p class="text-xs text-amber-400/80 mb-2">
                  {{ isZh ? '目前僅供瀏覽服裝款式，訂閱後即可使用完整虛擬試穿功能' : 'Currently for browsing only. Subscribe to unlock full virtual try-on.' }}
                </p>
                <RouterLink to="/pricing" class="inline-flex items-center gap-1 text-xs font-medium text-primary-400 hover:text-primary-300 transition-colors">
                  {{ isZh ? '立即訂閱' : 'Subscribe Now' }}
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                  </svg>
                </RouterLink>
              </div>
            </div>
          </div>

          <!-- Demo Clothing Items -->
          <div v-if="isDemoUser || displayClothingItems.length > 0" class="mb-4">
            <p class="text-sm text-dark-500 mb-3">
              {{ isZh ? '預設服裝（示範）' : 'Preset Clothing (Demo)' }}
            </p>
            <div v-if="isLoadingTemplates" class="flex justify-center py-8">
              <div class="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
            </div>
            <div v-else class="grid grid-cols-2 gap-2">
              <button
                v-for="item in displayClothingItems"
                :key="item.id"
                @click="selectDemoClothing(item)"
                class="aspect-[3/4] rounded-lg overflow-hidden border-2 transition-all"
                :class="selectedClothingId === item.id
                  ? 'border-primary-500'
                  : 'border-gray-200 hover:border-dark-500'"
              >
                <img
                  v-if="item.preview"
                  :src="item.preview"
                  :alt="item.name"
                  class="w-full h-full object-cover"
                />
                <div v-else class="w-full h-full bg-gray-100 flex items-center justify-center">
                  <span class="text-3xl">👔</span>
                </div>
              </button>
            </div>
          </div>

          <!-- Subscriber Interface: Upload Zone -->
          <div v-if="!isDemoUser" class="mb-4">
             <h4 class="text-sm font-medium text-dark-500 mb-2">{{ isZh ? '上傳服裝' : 'Upload Clothing' }}</h4>
             <ImageUploader 
               v-model="clothingImage" 
               :label="isZh ? '點擊上傳或拖放服裝圖片' : 'Drop clothing image here'"
               class="mb-4"
             />
          </div>

          <!-- Selected Clothing Preview -->
          <div v-if="clothingImage" class="mt-4 space-y-2">
            <img :src="clothingImage" alt="Clothing" class="w-full rounded-xl" />
            <button
               v-if="canUseCustomInputs"
               @click="clothingImage = undefined; selectedClothingId = null"
               class="btn-ghost text-sm w-full"
            >
              {{ isZh ? '更換服裝' : 'Change Clothing' }}
            </button>
          </div>
        </div>

        <!-- Middle Panel - Model Selection -->
        <div class="card">
          <h3 class="text-lg font-semibold text-dark-900 mb-4">
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
                : 'border-gray-200 hover:border-dark-500'"
            >
              <div class="aspect-[2/3] rounded-lg overflow-hidden mb-2">
                <img :src="model.preview" :alt="isZh ? model.name_zh : model.name" class="w-full h-full object-cover" />
              </div>
              <p class="text-xs text-center text-dark-900">{{ isZh ? model.name_zh : model.name }}</p>
            </button>

            <!-- Subscriber Interface: Custom Model Upload -->
             <div v-if="!isDemoUser" class="col-span-2 mt-2">
               <button 
                 v-if="selectedModel !== 'custom'"
                 @click="selectedModel = 'custom'" 
                 class="w-full py-2 border-2 border-dashed border-gray-600 rounded-xl hover:border-primary-500 hover:text-primary-500 transition-colors text-dark-500 text-sm flex items-center justify-center gap-2"
               >
                 <span>➕</span> {{ isZh ? '上傳自定義模特' : 'Upload Custom Model' }}
               </button>

               <div v-else class="space-y-2">
                 <div class="flex justify-between items-center mb-1">
                   <span class="text-sm font-medium text-dark-900">{{ isZh ? '自定義模特' : 'Custom Model' }}</span>
                   <button @click="selectedModel = 'female-1'; modelImage = undefined" class="text-xs text-dark-500 hover:text-dark-900">
                     {{ isZh ? '取消' : 'Cancel' }}
                   </button>
                 </div>
                 <ImageUploader 
                   v-model="modelImage" 
                   :label="isZh ? '上傳全身模特照片' : 'Upload full-body model photo'"
                   height="h-48"
                 />
               </div>
             </div>
          </div>

          <!-- Credit Cost & Generate -->
          <div class="mt-6 pt-4 border-t border-gray-200">
            <CreditCost service="virtual_try_on" />

            <!-- Warning message for invalid combination -->
            <div v-if="!isValidCombination" class="mt-3 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
              <p class="text-sm text-red-400">
                {{ isZh ? '⚠️ 男性模特不能穿著裙子或洋裝' : '⚠️ Male models cannot wear dresses or skirts' }}
              </p>
            </div>

            <button
              @click="generateTryOn"
              :disabled="(!clothingImage && !selectedClothingId) || isProcessing || !isValidCombination || dbEmpty"
              class="btn-primary w-full mt-4"
              :class="{ 'opacity-50 cursor-not-allowed': !isValidCombination || dbEmpty }"
            >
              {{ dbEmpty ? (isZh ? '預覽模式' : 'Preview Mode') : t('common.generate') }}
            </button>
            <p v-if="dbEmpty" class="text-xs text-dark-400 text-center mt-2">
              {{ isZh ? '訂閱後即可生成試穿結果' : 'Subscribe to generate try-on results' }}
            </p>
          </div>
        </div>

        <!-- Right Panel - Result -->
        <div class="card">
          <h3 class="text-lg font-semibold text-dark-900 mb-4">
            {{ isZh ? '試穿結果' : 'Try-On Result' }}
          </h3>

          <div v-if="resultImage" class="space-y-4">
            <img :src="resultImage" alt="Result" class="w-full rounded-xl" />

            <!-- Watermark badge -->
            <div class="text-center text-xs text-dark-400">vidgo.ai</div>

            <!-- Download / Action Buttons -->
            <div class="flex gap-2">
               <a
                 v-if="!isDemoUser"
                 :href="resultImage"
                 download="vidgo_tryon_result.png"
                 class="btn-primary flex-1 text-center py-2"
               >
                 {{ t('common.download') }}
               </a>

               <RouterLink v-else to="/pricing" class="btn-primary w-full text-center block">
                 {{ isZh ? '訂閱以獲得完整功能' : 'Subscribe for Full Access' }}
               </RouterLink>
            </div>
          </div>

          <div v-else class="h-64 flex items-center justify-center text-dark-400">
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
