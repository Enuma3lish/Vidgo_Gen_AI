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
  demoTemplates
} = useDemoMode()

const uploadedImage = ref<string | null>(null)
const resultImages = ref<string[]>([])
const isProcessing = ref(false)
const selectedScene = ref('studio')
const prompt = ref('')

const sceneTemplates = computed(() => [
  { id: 'studio', icon: '📷', name: t('tools.scenes.studio.name'), desc: t('tools.scenes.studio.desc') },
  { id: 'nature', icon: '🌿', name: t('tools.scenes.nature.name'), desc: t('tools.scenes.nature.desc') },
  { id: 'luxury', icon: '✨', name: t('tools.scenes.luxury.name'), desc: t('tools.scenes.luxury.desc') },
  { id: 'minimal', icon: '⬜', name: t('tools.scenes.minimal.name'), desc: t('tools.scenes.minimal.desc') },
  { id: 'lifestyle', icon: '🏠', name: t('tools.scenes.lifestyle.name'), desc: t('tools.scenes.lifestyle.desc') },
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

const defaultProducts: DemoProduct[] = [
  {
    id: 'product-1',
    input: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800',
    name: 'Watch',
    nameZh: '手錶'
  },
  {
    id: 'product-2',
    input: 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800',
    name: 'Headphones',
    nameZh: '耳機'
  },
  {
    id: 'product-3',
    input: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800',
    name: 'Sneaker',
    nameZh: '運動鞋'
  },
  {
    id: 'product-4',
    input: 'https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=800',
    name: 'Camera',
    nameZh: '相機'
  },
  {
    id: 'product-5',
    input: 'https://images.unsplash.com/photo-1541643600914-78b084683601?w=800',
    name: 'Perfume',
    nameZh: '香水'
  }
]

// Scene types available for demo (excluding custom which is pro-only)
const demoSceneTypes = [
  { id: 'studio', name: 'Studio', nameZh: '攝影棚' },
  { id: 'nature', name: 'Nature', nameZh: '自然場景' },
  { id: 'luxury', name: 'Luxury', nameZh: '奢華場景' },
  { id: 'minimal', name: 'Minimal', nameZh: '極簡風格' },
  { id: 'lifestyle', name: 'Lifestyle', nameZh: '生活情境' }
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
  await loadDemoTemplates('product_scene')

  // For demo users, auto-select first default product
  if (isDemoUser.value && defaultProducts.length > 0) {
    const firstProduct = defaultProducts[0]
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
  for (const product of defaultProducts) {
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

      // Fallback: try to find any preset matching the scene
      const template = demoTemplates.value.find(t =>
        ((t as any).input_params?.scene_type === selectedScene.value ||
         t.topic === selectedScene.value)
      )

      if (template?.result_watermarked_url || template?.result_image_url) {
        resultImages.value = [template.result_watermarked_url || template.result_image_url || '']
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }

      // No pre-generated result - show the input image as demo preview
      resultImages.value = [uploadedImage.value!]
      uiStore.showInfo(isZh.value ? '這是示範預覽，訂閱後可生成實際場景' : 'This is a demo preview. Subscribe to generate actual scenes.')
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
          {{ t('tools.productScene.name') }}
        </h1>
        <p class="text-xl text-gray-400">
          {{ t('tools.productScene.longDesc') }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ isZh ? '訂閱以解鎖更多功能' : 'Subscribe to unlock more features' }}
          </RouterLink>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Left Panel - Product Selection -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">{{ t('tools.common.productImage') }}</h3>

          <!-- PRESET-ONLY MODE: All users select from preset products -->
          <div class="mb-4">
            <p class="text-sm text-gray-400 mb-3">
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
                  : 'border-dark-600 hover:border-dark-500'"
              >
                <img
                  :src="product.input"
                  alt="Product"
                  class="w-full h-full object-cover"
                />
                <!-- Product name badge -->
                <div class="absolute bottom-0 left-0 right-0 bg-black/70 px-2 py-1 text-xs text-center">
                  {{ isZh ? product.nameZh : product.name }}
                </div>
              </button>
            </div>
            <p class="text-xs text-gray-500 mt-2">
              {{ isZh ? '5個產品 × 5個場景 = 25種組合' : '5 products × 5 scenes = 25 combinations' }}
            </p>
          </div>

          <!-- PRESET-ONLY MODE: Custom upload REMOVED - all users use presets -->

          <!-- Selected Image Preview -->
          <div v-if="uploadedImage" class="space-y-4 mt-4">
            <img :src="uploadedImage" alt="Product" class="w-full rounded-xl" />
          </div>
        </div>

        <!-- Middle Panel - Scene Selection -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">{{ t('tools.common.selectScene') }}</h3>

          <div class="grid grid-cols-2 gap-3">
            <button
              v-for="scene in sceneTemplates"
              :key="scene.id"
              @click="!scene.proOnly || canUseCustomInputs ? (selectedScene = scene.id) : uiStore.showError(isZh ? '請訂閱以使用此功能' : 'Please subscribe to use this feature')"
              class="p-4 rounded-xl border-2 transition-all text-left relative"
              :class="[
                selectedScene === scene.id
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'border-dark-600 hover:border-dark-500',
                scene.proOnly && isDemoUser ? 'opacity-60' : ''
              ]"
            >
              <span v-if="scene.proOnly && isDemoUser" class="absolute top-1 right-1 text-xs bg-primary-500 text-white px-1 rounded">Pro</span>
              <span class="text-2xl">{{ scene.icon }}</span>
              <p class="font-medium text-white mt-2">{{ scene.name }}</p>
              <p class="text-xs text-gray-500">{{ scene.desc }}</p>
            </button>
          </div>

          <!-- PRESET-ONLY MODE: Custom prompt REMOVED - all users use preset scenes -->

          <!-- Credit Cost & Generate -->
          <div class="mt-6 pt-4 border-t border-dark-700">
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
          <h3 class="text-lg font-semibold text-white mb-4">{{ t('tools.common.generatedScenes') }}</h3>

          <div v-if="resultImages.length > 0" class="space-y-4">
            <img
              v-for="(img, index) in resultImages"
              :key="index"
              :src="img"
              alt="Result"
              class="w-full rounded-xl"
            />

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

          <div v-else class="h-64 flex items-center justify-center text-gray-500">
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
