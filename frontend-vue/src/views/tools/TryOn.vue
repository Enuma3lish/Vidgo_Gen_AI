<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { toolsApi } from '@/api'
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
  dbEmpty,
  resolveDemoTemplateResultUrl,
  generateOnDemand
} = useDemoMode()

// State
const clothingImage = ref<string | undefined>(undefined)
const selectedClothingId = ref<string | null>(null)
const modelImage = ref<string | undefined>(undefined)
const resultImage = ref<string | null>(null)
const isProcessing = ref(false)
// True when a demo user clicked Generate but the selected tile isn't backed
// by a real Material DB preset (db_empty fallback or missing preset id).
// Surfaces a persistent in-block message instead of a silent no-op.
const demoEmptyState = ref(false)
const selectedModel = ref('female-1')

// Style templates for try-on scene/background
interface StyleTemplateItem {
  id: string
  category: string
  name_en: string
  name_zh: string
  preview_image_url?: string
  is_featured: boolean
}
const styleTemplates = ref<StyleTemplateItem[]>([])
const selectedTemplateId = ref<string | null>(null)

// Default model options (6 models matching backend generate_model_library() naming)
const modelOptions = ref([
  { id: 'female-1', name: 'Female Model 1', name_zh: '女模特 1', preview: 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/female-1.png' },
  { id: 'female-2', name: 'Female Model 2', name_zh: '女模特 2', preview: 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/female-2.png' },
  { id: 'female-3', name: 'Female Model 3', name_zh: '女模特 3', preview: 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/female-3.png' },
  { id: 'male-1', name: 'Male Model 1', name_zh: '男模特 1', preview: 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/male-1.png' },
  { id: 'male-2', name: 'Male Model 2', name_zh: '男模特 2', preview: 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/male-2.png' },
  { id: 'male-3', name: 'Male Model 3', name_zh: '男模特 3', preview: 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/male-3.png' }
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

  // Load curated style templates for try-on scenes
  try {
    const { templates } = await toolsApi.getStyleTemplates('try_on')
    styleTemplates.value = templates
  } catch (e) {
    console.warn('Failed to load try-on style templates:', e)
  }
})

// Kling AI is trained on garments. If an accessory slips into the catalog we
// still let the user click it, but surface a clear toast up-front so the
// unexpected result is explained before they hit Generate.
const ACCESSORY_KEYWORDS = [
  'hat', 'cap', 'beanie', 'sunglass', 'glasses', 'watch', 'scarf',
  'earring', 'necklace', 'bracelet', 'ring', 'bag', 'shoe', 'boot',
  '帽', '眼鏡', '太陽眼鏡', '手錶', '圍巾', '絲巾', '耳環', '項鍊',
  '手鍊', '戒指', '包', '鞋', '靴',
]

function isAccessoryItem(name: string, clothingType?: string): boolean {
  if (clothingType && clothingType !== 'general' && clothingType !== 'dress') {
    // Non-general/dress types from the backend are explicit hints
    const nonGarment = ['hat', 'glasses', 'watch', 'scarf', 'jewelry', 'bag', 'shoes', 'accessory']
    if (nonGarment.includes(clothingType)) return true
  }
  const lower = (name || '').toLowerCase()
  return ACCESSORY_KEYWORDS.some(k => lower.includes(k))
}

function selectDemoClothing(item: { id: string; name?: string; clothingType?: string; preview?: string; watermarked_result?: string }) {
  selectedClothingId.value = item.id
  clothingImage.value = item.preview || undefined
  resultImage.value = null
  demoEmptyState.value = false
  if (isAccessoryItem(item.name || '', item.clothingType)) {
    uiStore.showInfo(isZh.value
      ? '此項為配件，AI 試穿不一定能正確呈現，結果僅供參考'
      : 'This is an accessory. Virtual try-on may not render it correctly — results are indicative only.')
  }
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

  // Clear stale result so the loading overlay is the only thing visible
  // until the new try-on finishes.
  resultImage.value = null
  demoEmptyState.value = false
  isProcessing.value = true
  try {
    // For demo users, resolve the exact model+clothing preset through backend lookup
    if (isDemoUser.value && selectedClothingId.value) {
      await new Promise(resolve => setTimeout(resolve, 500))

      const template = demoTemplates.value.find(t => {
        const params = (t as any).input_params || {}
        return params.clothing_id === selectedClothingId.value && params.model_id === selectedModel.value
      })

      if (template?.id) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(template.id)
        if (demoResultUrl) {
          resultImage.value = demoResultUrl
          uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
          return
        }
      }

      // Cache-through on demand. Try-on uses PiAPI REST (no MCP path).
      // Pass model_id via product_id (API only exposes one extra param) and
      // the garment category via topic so the backend picks the right pair.
      const garmentTopic = (demoTemplates.value.find(t => (t as any).input_params?.clothing_id === selectedClothingId.value) as any)?.topic
      uiStore.showInfo(isZh.value ? '此組合尚未生成，正在為您即時生成（約 30-60 秒）...' : 'Generating in real-time (30-60s)...')
      const onDemandUrl = await generateOnDemand('try_on', garmentTopic, {
        product_id: selectedModel.value,
      })
      if (onDemandUrl) {
        resultImage.value = onDemandUrl
        uiStore.showSuccess(isZh.value ? '試穿成功' : 'Try-on successful')
        return
      }
      demoEmptyState.value = true
      uiStore.showError(isZh.value ? '試穿服務暫時無法使用，請稍後再試或訂閱解鎖完整功能' : 'Try-on service temporarily unavailable. Please try again later or subscribe.')
      return
    }

    // For subscribed users or if no cached result
    let imageUrl = clothingImage.value

    // Upload if custom image (data URI from file picker)
    if (clothingImage.value && clothingImage.value.startsWith('data:')) {
      const blob = dataURItoBlob(clothingImage.value)
      if (!blob) {
        uiStore.showError(isZh.value ? '圖片格式無效，請重新上傳' : 'Invalid image format. Please re-upload.')
        return
      }
      const uploadResult = await toolsApi.uploadImage(blob as File)
      imageUrl = uploadResult.url
    }

    let modelUrl = null
    if (selectedModel.value === 'custom' && modelImage.value) {
      if (modelImage.value.startsWith('data:')) {
        const blob = dataURItoBlob(modelImage.value)
        if (!blob) {
          uiStore.showError(isZh.value ? '模特圖片格式無效' : 'Invalid model image format.')
          return
        }
        const modelUpload = await toolsApi.uploadImage(blob as File)
        modelUrl = modelUpload.url
      } else {
        modelUrl = modelImage.value
      }
    }

    const result = await toolsApi.tryOn(imageUrl!, {
      modelImageUrl: modelUrl ?? undefined,
      modelId: selectedModel.value !== 'custom' ? selectedModel.value : undefined,
      templateId: selectedTemplateId.value || undefined,
    })

    if (result.success && (result.image_url || result.result_url)) {
      resultImage.value = result.image_url || result.result_url || null
      if (result.credits_used) {
        creditsStore.deductCredits(result.credits_used)
      }
      uiStore.showSuccess(t('common.success'))
    } else {
      const errMsg = result.message || (result as any).error || (isZh.value ? '生成失敗，請稍後再試' : 'Generation failed. Please try again.')
      uiStore.showError(errMsg)
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail || error?.response?.data?.message || error?.message || ''
    uiStore.showError(detail || (isZh.value ? '生成失敗' : 'Generation failed'))
  } finally {
    isProcessing.value = false
  }
}

function handleBack() {
  router.back()
}

function dataURItoBlob(dataURI: string): Blob | null {
  if (!dataURI || !dataURI.includes(',') || !dataURI.startsWith('data:')) {
    return null
  }
  try {
    const byteString = atob(dataURI.split(',')[1])
    const mimeString = dataURI.split(',')[0].split(':')[1].split(';')[0]
    const ab = new ArrayBuffer(byteString.length)
    const ia = new Uint8Array(ab)
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i)
    }
    return new Blob([ab], { type: mimeString })
  } catch {
    return null
  }
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b; color: #f5f5fa;">
    <LoadingOverlay :show="isProcessing" :message="t('common.processing')" />

    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Back Button -->
      <button
        @click="handleBack"
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
          {{ t('tools.tryOn.name') }}
        </h1>
        <p class="text-xl text-dark-300">
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
          <h3 class="text-lg font-semibold text-dark-50 mb-4">
            {{ isZh ? '選擇服裝' : 'Select Clothing' }}
          </h3>

          <!-- Kling AI limitation notice — try-on is trained on torso/body
               garments only. Accessories (hats, sunglasses, watches, scarves,
               jewelry, shoes) don't render correctly regardless of provider. -->
          <div class="mb-4 p-3 rounded-lg" style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.24);">
            <p class="text-xs text-amber-400 leading-relaxed">
              <span class="font-semibold">
                {{ isZh ? '⚠️ 提示：' : '⚠️ Note: ' }}
              </span>
              {{ isZh
                ? 'AI 試穿適用於完整服裝（上衣、裙裝、外套等）。配件類如帽子、眼鏡、手錶、絲巾、珠寶、鞋子可能無法正確呈現。'
                : 'Virtual try-on works best with full garments (tops, dresses, coats, etc.). Accessories like hats, sunglasses, watches, scarves, jewelry, or shoes may not render correctly.' }}
            </p>
          </div>

          <!-- Demo Clothing Items -->
          <div v-if="isDemoUser || displayClothingItems.length > 0" class="mb-4">
            <p class="text-sm text-dark-300 mb-3">
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
                  : 'hover:border-dark-500'" style="border-color: rgba(255,255,255,0.08);">
              >
                <img
                  v-if="item.preview"
                  :src="item.preview"
                  :alt="item.name"
                  class="w-full h-full object-cover"
                />
                <div v-else class="w-full h-full flex items-center justify-center" style="background: #141420;">
                  <span class="text-3xl">👔</span>
                </div>
              </button>
            </div>
          </div>

          <!-- Subscriber Interface: Upload Zone -->
          <div v-if="!isDemoUser" class="mb-4">
             <h4 class="text-sm font-medium text-dark-300 mb-2">{{ isZh ? '上傳服裝' : 'Upload Clothing' }}</h4>
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
          <h3 class="text-lg font-semibold text-dark-50 mb-4">
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
                : 'hover:border-dark-500'" style="border-color: rgba(255,255,255,0.08);">
            >
              <div class="aspect-[2/3] rounded-lg overflow-hidden mb-2">
                <img :src="model.preview" :alt="isZh ? model.name_zh : model.name" class="w-full h-full object-cover" />
              </div>
              <p class="text-xs text-center text-dark-50">{{ isZh ? model.name_zh : model.name }}</p>
            </button>

            <!-- Subscriber Interface: Custom Model Upload -->
             <div v-if="!isDemoUser" class="col-span-2 mt-2">
               <button 
                 v-if="selectedModel !== 'custom'"
                 @click="selectedModel = 'custom'" 
                 class="w-full py-2 border-2 border-dashed rounded-xl hover:border-primary-500 hover:text-primary-500 transition-colors text-dark-300 text-sm flex items-center justify-center gap-2" style="border-color: rgba(255,255,255,0.12);">
               >
                 <span>➕</span> {{ isZh ? '上傳自定義模特' : 'Upload Custom Model' }}
               </button>

               <div v-else class="space-y-2">
                 <div class="flex justify-between items-center mb-1">
                   <span class="text-sm font-medium text-dark-50">{{ isZh ? '自定義模特' : 'Custom Model' }}</span>
                   <button @click="selectedModel = 'female-1'; modelImage = undefined" class="text-xs text-dark-300 hover:text-dark-50">
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

          <!-- Style Templates (scene/background for try-on — subscribers only) -->
          <div v-if="!isDemoUser && styleTemplates.length > 0" class="mt-6">
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-sm font-semibold text-dark-200">
                {{ isZh ? '拍攝場景模版' : 'Scene Templates' }}
              </h4>
              <button
                v-if="selectedTemplateId"
                @click="selectedTemplateId = null"
                class="text-xs text-primary-400 hover:text-primary-300"
              >
                {{ isZh ? '清除' : 'Clear' }}
              </button>
            </div>
            <div class="grid grid-cols-3 gap-2">
              <button
                v-for="tmpl in styleTemplates"
                :key="tmpl.id"
                @click="selectedTemplateId = selectedTemplateId === tmpl.id ? null : tmpl.id"
                class="relative rounded-xl border-2 p-2 transition-all text-center"
                :class="selectedTemplateId === tmpl.id
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'border-transparent hover:border-dark-500'"
                style="background: #1a1a2e;"
              >
                <img
                  v-if="tmpl.preview_image_url"
                  :src="tmpl.preview_image_url"
                  :alt="isZh ? tmpl.name_zh : tmpl.name_en"
                  class="w-full h-16 object-cover rounded-lg mb-1"
                />
                <div v-else class="w-full h-16 rounded-lg mb-1 flex items-center justify-center" style="background: #141420;">
                  <span class="text-xl">🎨</span>
                </div>
                <p class="text-[10px] font-medium text-dark-50 truncate">
                  {{ isZh ? tmpl.name_zh : tmpl.name_en }}
                </p>
              </button>
            </div>
            <p class="text-xs text-dark-400 mt-2">
              {{ isZh ? '選擇場景模版，AI 將在指定背景中展示穿搭效果' : 'Select a scene for the model background' }}
            </p>
          </div>

          <!-- Credit Cost & Generate -->
          <div class="mt-6 pt-4" style="border-top: 1px solid rgba(255,255,255,0.06);">
            <CreditCost service="virtual_try_on" />

            <!-- Warning message for invalid combination -->
            <div v-if="!isValidCombination" class="mt-3 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
              <p class="text-sm text-red-400">
                {{ isZh ? '⚠️ 男性模特不能穿著裙子或洋裝' : '⚠️ Male models cannot wear dresses or skirts' }}
              </p>
            </div>

            <button
              @click="generateTryOn"
              :disabled="(!clothingImage && !selectedClothingId) || isProcessing || !isValidCombination"
              class="btn-primary w-full mt-4"
              :class="{ 'opacity-50 cursor-not-allowed': !isValidCombination }"
            >
              {{ t('common.generate') }}
            </button>
          </div>
        </div>

        <!-- Right Panel - Result -->
        <div class="card">
          <h3 class="text-lg font-semibold text-dark-50 mb-4">
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

          <div v-else-if="demoEmptyState" class="h-64 flex flex-col items-center justify-center rounded-xl text-center px-6 gap-3" style="background: #141420; border: 1px solid rgba(255,255,255,0.08);">
            <span class="text-2xl">🔒</span>
            <p class="text-sm text-dark-200">
              {{ isZh ? '此範例尚未預生成結果' : 'No pre-generated result for this example yet' }}
            </p>
            <RouterLink to="/pricing" class="btn-primary text-sm px-4 py-2">
              {{ isZh ? '訂閱以使用完整 AI 功能' : 'Subscribe to use the real AI' }}
            </RouterLink>
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
