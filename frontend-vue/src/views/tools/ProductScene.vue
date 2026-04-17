<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { toolsApi } from '@/api'
// PRESET-ONLY MODE: UploadZone removed - all users use presets
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()

// Static product image URLs for fallback display (keyed by product-id)
const STATIC_PRODUCT_IMAGES: Record<string, string> = {
  'product-1': 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&fit=crop',
  'product-2': 'https://images.unsplash.com/photo-1544816155-12df9643f363?w=400&fit=crop',
  'product-3': 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=400&fit=crop',
  'product-4': 'https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=400&fit=crop',
  'product-5': 'https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=400&fit=crop',
  'product-6': 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=400&fit=crop',
  'product-7': 'https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=400&fit=crop',
  'product-8': 'https://images.unsplash.com/photo-1549465220-1a8b9238cd48?w=400&fit=crop'
}

const isZh = computed(() => locale.value.startsWith('zh'))

// Demo mode
const {
  isDemoUser,
  canUseCustomInputs,
  loadDemoTemplates,
  demoTemplates,
  tryPrompts,
  dbEmpty,
  resolveDemoTemplateResultUrl,
  generateOnDemand
} = useDemoMode()

const uploadedImage = ref<string | undefined>(undefined)
const resultImages = ref<string[]>([])
const isProcessing = ref(false)
// True when a demo user clicked Generate but the selected tile isn't backed
// by a real Material DB preset (db_empty fallback or missing preset id).
// Surfaces a persistent in-block message instead of a silent no-op.
const demoEmptyState = ref(false)
const selectedScene = ref('studio')
const prompt = ref('')

// Style templates (curated prompts hidden from user)
interface StyleTemplateItem {
  id: string
  category: string
  name_en: string
  name_zh: string
  name_ja?: string
  name_ko?: string
  name_es?: string
  preview_image_url?: string
  is_featured: boolean
}
const styleTemplates = ref<StyleTemplateItem[]>([])
const selectedTemplateId = ref<string | null>(null)
const useTemplateMode = ref(false)

const sceneTemplates = computed(() => [
  { id: 'studio', icon: '📷', name: t('tools.scenes.studio.name'), desc: t('tools.scenes.studio.desc') },
  { id: 'nature', icon: '🌿', name: t('tools.scenes.nature.name'), desc: t('tools.scenes.nature.desc') },
  { id: 'elegant', icon: '✨', name: t('tools.scenes.elegant.name'), desc: t('tools.scenes.elegant.desc') },
  { id: 'minimal', icon: '⬜', name: t('tools.scenes.minimal.name'), desc: t('tools.scenes.minimal.desc') },
  { id: 'lifestyle', icon: '🏠', name: t('tools.scenes.lifestyle.name'), desc: t('tools.scenes.lifestyle.desc') },
  { id: 'urban', icon: '🏙️', name: isZh.value ? '都市' : 'Urban', desc: isZh.value ? '現代都市背景' : 'Modern city backdrop' },
  { id: 'seasonal', icon: '🍂', name: isZh.value ? '季節' : 'Seasonal', desc: isZh.value ? '季節性背景' : 'Seasonal backgrounds' },
  { id: 'holiday', icon: '🎄', name: isZh.value ? '節日' : 'Holiday', desc: isZh.value ? '節日慶典氛圍' : 'Festive celebration' },
  { id: 'custom', icon: '🎨', name: t('tools.scenes.custom.name'), desc: t('tools.scenes.custom.desc'), proOnly: true }
])

// Default product images for demo users
// Products and scenes are independent - any product can be combined with any scene
interface DemoProduct {
  id: string
  input: string
  name: string
  nameZh: string
}

// Product definitions matching backend PRODUCT_SCENE_MAPPING (8 products)
// input URLs are populated from demoTemplates API (T2I-generated images)
const defaultProducts = computed<DemoProduct[]>(() => {
  const productDefs = [
    { id: 'product-1', name: 'Bubble Tea', nameZh: '珍珠奶茶' },
    { id: 'product-2', name: 'Canvas Tote Bag', nameZh: '帆布托特包' },
    { id: 'product-3', name: 'Handmade Jewelry', nameZh: '手工飾品' },
    { id: 'product-4', name: 'Skincare Serum', nameZh: '保養精華液' },
    { id: 'product-5', name: 'Coffee Beans', nameZh: '咖啡豆' },
    { id: 'product-6', name: 'Espresso Machine', nameZh: '義式咖啡機' },
    { id: 'product-7', name: 'Handmade Candle', nameZh: '手工蠟燭' },
    { id: 'product-8', name: 'Gift Box Set', nameZh: '禮盒組合' },
  ]

  return productDefs.map(p => {
    // Find input image from pre-generated templates
    const template = demoTemplates.value.find(t => {
      const params = (t as any).input_params || {}
      return params.product_id === p.id
    })
    return {
      ...p,
      input: template?.input_image_url || STATIC_PRODUCT_IMAGES[p.id] || ''
    }
  })
})

// Scene types available for demo (excluding custom which is pro-only)
const demoSceneTypes = [
  { id: 'studio', name: 'Studio', nameZh: '攝影棚' },
  { id: 'nature', name: 'Nature', nameZh: '自然場景' },
  { id: 'elegant', name: 'Elegant', nameZh: '質感場景' },
  { id: 'minimal', name: 'Minimal', nameZh: '極簡風格' },
  { id: 'lifestyle', name: 'Lifestyle', nameZh: '生活情境' },
  { id: 'urban', name: 'Urban', nameZh: '都市' },
  { id: 'seasonal', name: 'Seasonal', nameZh: '季節' },
  { id: 'holiday', name: 'Holiday', nameZh: '節日' }
]

// Track which demo product is selected
const selectedProductId = ref<string>('product-1')


// Pre-generated preset cache: key = "product-id_scene-id", value = preset ID
const preGeneratedTemplateIds = ref<Record<string, string>>({})

// Get result key for current selection
const currentResultKey = computed(() => {
  return `${selectedProductId.value}_${selectedScene.value}`
})

// Get pre-generated preset ID for current combination
const currentPreGeneratedTemplateId = computed(() => {
  return preGeneratedTemplateIds.value[currentResultKey.value] || null
})

// Load demo templates on mount
onMounted(async () => {
  await loadDemoTemplates('product_scene', undefined, locale.value)

  // Load curated style templates for subscribers
  try {
    const { templates } = await toolsApi.getStyleTemplates('product_scene')
    styleTemplates.value = templates
  } catch (e) {
    console.warn('Failed to load style templates:', e)
  }

  // For demo users, auto-select first default product
  if (isDemoUser.value && defaultProducts.value.length > 0) {
    const firstProduct = defaultProducts.value[0]
    selectedProductId.value = firstProduct.id
    uploadedImage.value = firstProduct.input
    selectedScene.value = 'studio'  // Default scene

    // Load all pre-generated results for product×scene combinations
    loadAllPreGeneratedResults()
  }
})

// Load pre-generated preset IDs for ALL product×scene combinations from database
function loadAllPreGeneratedResults() {
  preGeneratedTemplateIds.value = {}

  // Look for templates matching each product×scene combination
  for (const product of defaultProducts.value) {
    for (const scene of demoSceneTypes) {
      const resultKey = `${product.id}_${scene.id}`

      // Find matching preset in database
      const template = demoTemplates.value.find(t =>
        ((t as any).input_params?.product_id === product.id ||
         (t as any).input_params?.input_url === product.input ||
         t.input_image_url === product.input) &&
        ((t as any).input_params?.scene_type === scene.id ||
         t.topic === scene.id)
      )

      if (template?.id) {
        preGeneratedTemplateIds.value[resultKey] = template.id
      }
    }
  }
}

function selectDefaultProduct(product: DemoProduct) {
  selectedProductId.value = product.id
  uploadedImage.value = product.input
  // Don't change the scene - user can select any scene independently
  resultImages.value = []
  demoEmptyState.value = false
}

async function generateScenes() {
  if (!uploadedImage.value) return

  // Demo users cannot use custom scene
  if (isDemoUser.value && selectedScene.value === 'custom') {
    uiStore.showError(isZh.value ? '請訂閱以使用自訂場景' : 'Please subscribe to use custom scene')
    return
  }

  // Clear stale result so the loading overlay is the only thing visible
  // until the new generation finishes.
  resultImages.value = []
  demoEmptyState.value = false
  isProcessing.value = true
  try {
    // For demo users, resolve the exact product×scene preset through backend lookup
    if (isDemoUser.value) {
      await new Promise(resolve => setTimeout(resolve, 500))

      const preGeneratedTemplateId = currentPreGeneratedTemplateId.value
      if (preGeneratedTemplateId) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(preGeneratedTemplateId)
        if (demoResultUrl) {
          resultImages.value = [demoResultUrl]
          uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
          return
        }
      }

      const selectedProduct = defaultProducts.value.find(p => p.id === selectedProductId.value)
      const template = demoTemplates.value.find(t => {
        const params = (t as any).input_params || {}
        const matchesProduct = params.product_id === selectedProductId.value ||
                               params.input_url === selectedProduct?.input ||
                               t.input_image_url === selectedProduct?.input
        const matchesScene = params.scene_type === selectedScene.value || t.topic === selectedScene.value
        return matchesProduct && matchesScene
      })

      if (template?.id) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(template.id)
        if (demoResultUrl) {
          resultImages.value = [demoResultUrl]
          preGeneratedTemplateIds.value[currentResultKey.value] = template.id
          uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
          return
        }
      }

      // VG-BUG-010 fix: no cached preset for this combo — call the backend
      // cache-through endpoint to generate one on demand via real provider.
      // The result is persisted to Material DB so the next click hits cache.
      uiStore.showInfo(isZh.value ? '此組合尚未生成，正在為您即時生成...' : 'Generating in real-time...')
      const onDemandUrl = await generateOnDemand('product_scene', selectedScene.value, {
        product_id: selectedProductId.value,
      })
      if (onDemandUrl) {
        resultImages.value = [onDemandUrl]
        uiStore.showSuccess(isZh.value ? '生成成功' : 'Generated successfully')
        return
      }

      // True last-resort fallback if even the on-demand path fails (e.g.,
      // backend cache-through doesn't support this tool yet, or all
      // providers are down).
      demoEmptyState.value = true
      uiStore.showError(isZh.value ? '生成服務暫時無法使用，請稍後再試或訂閱解鎖完整功能' : 'Generation service temporarily unavailable. Please try again later or subscribe.')
      return
    }

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

    const result = await toolsApi.productScene(
      uploadUrl,
      selectedScene.value,
      selectedScene.value === 'custom' ? prompt.value : undefined,
      selectedProductId.value || undefined,
      selectedTemplateId.value || undefined,
    )

    if (result.success && (result.image_url || result.result_url)) {
      resultImages.value = [result.image_url || result.result_url || '']
      creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success'))
    } else {
      uiStore.showError(result.message || (result as any).error || (isZh.value ? '場景生成失敗，請稍後再試' : 'Scene generation failed. Please try again.'))
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail || error?.response?.data?.message || error?.message || ''
    uiStore.showError(detail || (isZh.value ? '生成失敗' : 'Generation failed'))
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
          {{ t('tools.productScene.name') }}
        </h1>
        <p class="text-xl text-dark-300">
          {{ t('tools.productScene.longDesc') }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ isZh ? '訂閱以解鎖更多功能' : 'Subscribe to unlock more features' }}
          </RouterLink>
        </div>

        <!-- DB Empty: Show try prompts (fixed prompts for try-play) -->
        <div v-if="dbEmpty && tryPrompts.length > 0" class="mt-6 p-4 rounded-xl" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <p class="text-sm text-dark-200 mb-3">
            {{ isZh ? '以下為可試玩的固定提示詞，資料庫尚未有預生成結果。訂閱者可上傳自訂圖片並即時生成。' : 'Try-play prompts below. DB has no pre-generated results yet. Subscribers can upload and generate.' }}
          </p>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="p in tryPrompts.slice(0, 6)"
              :key="p.id"
              class="px-3 py-1 rounded-full text-xs bg-dark-800 text-dark-200"
            >
              {{ p.prompt }}
            </span>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Left Panel - Product Selection -->
        <div class="card">
          <h3 class="text-lg font-semibold text-dark-50 mb-4">{{ t('tools.common.productImage') }}</h3>

          <!-- PRESET-ONLY MODE: All users select from preset products -->
          <div class="mb-4">
            <p class="text-sm text-dark-300 mb-3">
              {{ isZh ? '選擇產品圖片' : 'Select Product Image' }}
            </p>
            <div class="grid grid-cols-2 gap-2">
              <button
                v-for="product in defaultProducts"
                :key="product.id"
                @click="selectDefaultProduct(product)"
                class="relative aspect-square rounded-lg overflow-hidden border-2 transition-all"
                :class="selectedProductId === product.id
                  ? 'border-primary-500 ring-2 ring-primary-500/50'
                  : 'hover:border-dark-500'" style="border-color: rgba(255,255,255,0.08);">
              >
                <img
                  v-if="product.input"
                  :src="product.input"
                  alt="Product"
                  class="w-full h-full object-cover"
                />
                <div v-else class="w-full h-full flex items-center justify-center" style="background: #141420;">
                  <span class="text-2xl">📦</span>
                </div>
                <!-- Product name badge -->
                <div class="absolute bottom-0 left-0 right-0 bg-black/70 px-2 py-1 text-xs text-center">
                  {{ isZh ? product.nameZh : product.name }}
                </div>
              </button>
            </div>
            <p class="text-xs text-dark-400 mt-2">
              {{ isZh ? '8個產品 × 8個場景 = 64種組合' : '8 products × 8 scenes = 64 combinations' }}
            </p>
          </div>

          <!-- Subscriber Interface: Upload Zone -->
          <div v-if="!isDemoUser" class="mb-6">
             <h4 class="text-sm font-medium text-dark-300 mb-2">{{ isZh ? '上傳您的產品' : 'Upload Your Product' }}</h4>
             <ImageUploader 
               v-model="uploadedImage" 
               :label="isZh ? '點擊上傳或拖放產品圖片' : 'Drop product image here'"
               class="mb-4"
             />
          </div>

          <!-- PRESET-ONLY: Custom upload hidden? No, we just added it above. -->

          <!-- Selected Image Preview -->
          <div v-if="uploadedImage" class="space-y-4 mt-4">
            <img :src="uploadedImage" alt="Product" class="w-full rounded-xl" />
          </div>
        </div>

        <!-- Middle Panel - Scene Selection -->
        <div class="card">
          <h3 class="text-lg font-semibold text-dark-50 mb-4">{{ t('tools.common.selectScene') }}</h3>

          <div class="grid grid-cols-2 gap-3">
            <button
              v-for="scene in sceneTemplates"
              :key="scene.id"
              @click="!scene.proOnly || canUseCustomInputs ? (selectedScene = scene.id) : uiStore.showError(isZh ? '請訂閱以使用此功能' : 'Please subscribe to use this feature')"
              class="p-4 rounded-xl border-2 transition-all text-left relative"
              :class="[
                selectedScene === scene.id
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'hover:border-dark-500',
                scene.proOnly && isDemoUser ? 'opacity-60' : ''
              ]"
            >
              <span v-if="scene.proOnly && isDemoUser" class="absolute top-1 right-1 text-xs bg-primary-500 text-dark-50 px-1 rounded">Pro</span>
              <span class="text-2xl">{{ scene.icon }}</span>
              <p class="font-medium text-dark-50 mt-2">{{ scene.name }}</p>
              <p class="text-xs text-dark-400">{{ scene.desc }}</p>
            </button>
          </div>

          <!-- Style Templates (curated prompts — subscribers only) -->
          <div v-if="!isDemoUser && styleTemplates.length > 0" class="mt-6">
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-sm font-semibold text-dark-200">
                {{ isZh ? '精選風格模版' : 'Curated Style Templates' }}
              </h4>
              <button
                v-if="selectedTemplateId"
                @click="selectedTemplateId = null"
                class="text-xs text-primary-400 hover:text-primary-300"
              >
                {{ isZh ? '清除選擇' : 'Clear' }}
              </button>
            </div>
            <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
              <button
                v-for="tmpl in styleTemplates"
                :key="tmpl.id"
                @click="selectedTemplateId = tmpl.id; selectedScene = 'custom'"
                class="relative rounded-xl border-2 p-3 transition-all text-left"
                :class="selectedTemplateId === tmpl.id
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'border-transparent hover:border-dark-500'"
                style="background: #1a1a2e;"
              >
                <img
                  v-if="tmpl.preview_image_url"
                  :src="tmpl.preview_image_url"
                  :alt="isZh ? tmpl.name_zh : tmpl.name_en"
                  class="w-full h-20 object-cover rounded-lg mb-2"
                />
                <div v-else class="w-full h-20 rounded-lg mb-2 flex items-center justify-center" style="background: #141420;">
                  <span class="text-2xl">🎨</span>
                </div>
                <p class="text-xs font-medium text-dark-50 truncate">
                  {{ isZh ? tmpl.name_zh : tmpl.name_en }}
                </p>
                <span v-if="tmpl.is_featured" class="absolute top-1 right-1 text-[10px] bg-yellow-500/20 text-yellow-400 px-1.5 py-0.5 rounded-full">★</span>
              </button>
            </div>
            <p class="text-xs text-dark-400 mt-2">
              {{ isZh ? '選擇模版後，AI 將自動套用專業攝影參數（光影、焦距、材質）' : 'Templates apply professional photography parameters automatically' }}
            </p>
          </div>

           <!-- Custom Prompt Input (Pro Only) -->
           <div v-if="selectedScene === 'custom' && !selectedTemplateId" class="mt-4">
             <label class="block text-sm font-medium text-dark-300 mb-2">
               {{ isZh ? '自訂場景描述' : 'Custom Scene Prompt' }}
             </label>
             <textarea
               v-model="prompt"
               rows="3"
               class="w-full rounded-lg p-3 focus:outline-none focus:border-primary-500" style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #f5f5fa;">
               :placeholder="isZh ? '描述您想要的場景細節...' : 'Describe the scene details...'"
             ></textarea>
           </div>

          <!-- Credit Cost & Generate -->
          <div class="mt-6 pt-4" style="border-top: 1px solid rgba(255,255,255,0.06);">
            <CreditCost service="product_scene" />
            <button
              @click="generateScenes"
              :disabled="!uploadedImage || isProcessing"
              class="btn-primary w-full mt-4"
            >
              {{ t('common.generate') }}
            </button>
          </div>
        </div>

        <!-- Right Panel - Results -->
        <div class="card">
          <h3 class="text-lg font-semibold text-dark-50 mb-4">{{ t('tools.common.generatedScenes') }}</h3>

          <div v-if="resultImages.length > 0" class="space-y-4">
            <div v-for="(img, index) in resultImages" :key="index" class="space-y-2">
              <img
                :src="img"
                alt="Result"
                class="w-full rounded-xl"
              />
              
              <!-- Download Button -->
               <a
                  v-if="!isDemoUser"
                  :href="img"
                  download="vidgo_product_scene.png"
                  class="btn-primary w-full text-center py-2 block"
               >
                 {{ t('common.download') }}
               </a>
            </div>
              
              <!-- Subscribe CTA for Demo Users -->
              <RouterLink
                v-if="isDemoUser"
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
          <div v-else class="h-64 flex items-center justify-center text-dark-400">
            <div class="text-center">
              <span class="text-5xl block mb-4">🛍️</span>
              <p>{{ t('tools.common.generatedScenes') }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
