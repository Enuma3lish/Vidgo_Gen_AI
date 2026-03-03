<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { demoApi } from '@/api'
// PRESET-ONLY MODE: UploadZone removed - all users use presets
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
  tryPrompts,
  dbEmpty
} = useDemoMode()

const uploadedImage = ref<string | undefined>(undefined)
const resultImages = ref<string[]>([])
const isProcessing = ref(false)
const selectedScene = ref('studio')
const prompt = ref('')

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
      input: template?.input_image_url || ''
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


// Pre-generated results cache: key = "product-id_scene-id", value = result URL
const preGeneratedResults = ref<Record<string, string>>({})

// Get result key for current selection
const currentResultKey = computed(() => {
  return `${selectedProductId.value}_${selectedScene.value}`
})

// Get pre-generated result for current combination
const currentPreGeneratedResult = computed(() => {
  return preGeneratedResults.value[currentResultKey.value] || null
})

// Load demo templates on mount
onMounted(async () => {
  await loadDemoTemplates('product_scene', undefined, locale.value)

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

// Load pre-generated results for ALL product×scene combinations from database
function loadAllPreGeneratedResults() {
  // Clear existing cache
  preGeneratedResults.value = {}

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

      if (template?.result_watermarked_url || template?.result_image_url) {
        preGeneratedResults.value[resultKey] = template.result_watermarked_url || template.result_image_url || ''
      }
    }
  }
}

function selectDefaultProduct(product: DemoProduct) {
  selectedProductId.value = product.id
  uploadedImage.value = product.input
  // Don't change the scene - user can select any scene independently
  resultImages.value = []
}

async function generateScenes() {
  if (!uploadedImage.value) return

  // Demo users cannot use custom scene
  if (isDemoUser.value && selectedScene.value === 'custom') {
    uiStore.showError(isZh.value ? '請訂閱以使用自訂場景' : 'Please subscribe to use custom scene')
    return
  }

  isProcessing.value = true
  try {
    // For demo users, use cached result for product×scene combination
    if (isDemoUser.value) {
      // Simulate processing delay for demo effect
      await new Promise(resolve => setTimeout(resolve, 1500))

      // Check if we have a pre-generated result for this exact product×scene combination
      const preGenResult = currentPreGeneratedResult.value
      if (preGenResult) {
        resultImages.value = [preGenResult]
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }

      // Try to find a preset that matches BOTH the selected product AND scene
      const selectedProduct = defaultProducts.value.find(p => p.id === selectedProductId.value)
      const template = demoTemplates.value.find(t => {
        const params = (t as any).input_params || {}
        const matchesProduct = params.product_id === selectedProductId.value ||
                               params.input_url === selectedProduct?.input ||
                               t.input_image_url === selectedProduct?.input
        const matchesScene = params.scene_type === selectedScene.value || t.topic === selectedScene.value
        return matchesProduct && matchesScene
      })

      if (template?.result_watermarked_url || template?.result_image_url) {
        resultImages.value = [template.result_watermarked_url || template.result_image_url || '']
        // Cache this result for future use
        preGeneratedResults.value[currentResultKey.value] = template.result_watermarked_url || template.result_image_url || ''
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }

      // No matching pre-generated result found - show info message
      uiStore.showInfo(isZh.value ? '此組合尚未生成，請訂閱以使用完整功能' : 'This combination is not pre-generated. Subscribe for full features.')
      return
    }

    const uploadResult = await demoApi.uploadImage(
      dataURItoBlob(uploadedImage.value) as File
    )

    const result = await demoApi.generate({
      tool: 'product_scene',
      image_url: uploadResult.url,
      prompt: selectedScene.value === 'custom' ? prompt.value : undefined,
      params: {
        scene_type: selectedScene.value
      }
    })

    if (result.success && result.image_url) {
      resultImages.value = [result.image_url]
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
  <div class="min-h-screen pt-24 bg-white pb-20">
    <LoadingOverlay :show="isProcessing" :message="t('common.processing')" />

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
          {{ t('tools.productScene.name') }}
        </h1>
        <p class="text-xl text-dark-500">
          {{ t('tools.productScene.longDesc') }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ isZh ? '訂閱以解鎖更多功能' : 'Subscribe to unlock more features' }}
          </RouterLink>
        </div>

        <!-- DB Empty: Show try prompts (fixed prompts for try-play) -->
        <div v-if="dbEmpty && tryPrompts.length > 0" class="mt-6 p-4 rounded-xl bg-gray-100/50 border border-gray-200">
          <p class="text-sm text-dark-600 mb-3">
            {{ isZh ? '以下為可試玩的固定提示詞，資料庫尚未有預生成結果。訂閱者可上傳自訂圖片並即時生成。' : 'Try-play prompts below. DB has no pre-generated results yet. Subscribers can upload and generate.' }}
          </p>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="p in tryPrompts.slice(0, 6)"
              :key="p.id"
              class="px-3 py-1 rounded-full text-xs bg-dark-800 text-dark-600"
            >
              {{ p.prompt }}
            </span>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Left Panel - Product Selection -->
        <div class="card">
          <h3 class="text-lg font-semibold text-dark-900 mb-4">{{ t('tools.common.productImage') }}</h3>

          <!-- PRESET-ONLY MODE: All users select from preset products -->
          <div class="mb-4">
            <p class="text-sm text-dark-500 mb-3">
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
                  : 'border-gray-200 hover:border-dark-500'"
              >
                <img
                  v-if="product.input"
                  :src="product.input"
                  alt="Product"
                  class="w-full h-full object-cover"
                />
                <div v-else class="w-full h-full bg-gray-100 flex items-center justify-center">
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
             <h4 class="text-sm font-medium text-dark-500 mb-2">{{ isZh ? '上傳您的產品' : 'Upload Your Product' }}</h4>
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
          <h3 class="text-lg font-semibold text-dark-900 mb-4">{{ t('tools.common.selectScene') }}</h3>

          <div class="grid grid-cols-2 gap-3">
            <button
              v-for="scene in sceneTemplates"
              :key="scene.id"
              @click="!scene.proOnly || canUseCustomInputs ? (selectedScene = scene.id) : uiStore.showError(isZh ? '請訂閱以使用此功能' : 'Please subscribe to use this feature')"
              class="p-4 rounded-xl border-2 transition-all text-left relative"
              :class="[
                selectedScene === scene.id
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'border-gray-200 hover:border-dark-500',
                scene.proOnly && isDemoUser ? 'opacity-60' : ''
              ]"
            >
              <span v-if="scene.proOnly && isDemoUser" class="absolute top-1 right-1 text-xs bg-primary-500 text-dark-900 px-1 rounded">Pro</span>
              <span class="text-2xl">{{ scene.icon }}</span>
              <p class="font-medium text-dark-900 mt-2">{{ scene.name }}</p>
              <p class="text-xs text-dark-400">{{ scene.desc }}</p>
            </button>
          </div>

           <!-- Custom Prompt Input (Pro Only) -->
           <div v-if="selectedScene === 'custom'" class="mt-4">
             <label class="block text-sm font-medium text-dark-500 mb-2">
               {{ isZh ? '自訂場景描述' : 'Custom Scene Prompt' }}
             </label>
             <textarea
               v-model="prompt"
               rows="3"
               class="w-full bg-dark-900 border border-gray-200 rounded-lg p-3 text-dark-900 focus:outline-none focus:border-primary-500"
               :placeholder="isZh ? '描述您想要的場景細節...' : 'Describe the scene details...'"
             ></textarea>
           </div>

          <!-- Credit Cost & Generate -->
          <div class="mt-6 pt-4 border-t border-gray-200">
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
          <h3 class="text-lg font-semibold text-dark-900 mb-4">{{ t('tools.common.generatedScenes') }}</h3>

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
