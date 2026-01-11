<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore } from '@/stores'
import { useDemoMode } from '@/composables'
import UploadZone from '@/components/tools/UploadZone.vue'
import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import CreditCost from '@/components/tools/CreditCost.vue'
import { generationApi } from '@/api/generation'
import { demoApi } from '@/api/demo'
import { useLocalized } from '@/composables/useLocalized'

const { t, locale } = useI18n()
const { getLocalizedField } = useLocalized()
const router = useRouter()
const uiStore = useUIStore()
const isZh = computed(() => locale.value.startsWith('zh'))

// Demo mode
const {
  isDemoUser,
  canUseCustomInputs,
  canDownloadOriginal,
  loadDemoTemplates,
  demoTemplates,
  isLoadingTemplates
} = useDemoMode()

// Tools in this topic
const tools = [
  {
    key: 'removeBackground',
    icon: '✂️',
    credits: 3,
    route: '/tools/background-removal'
  },
  {
    key: 'productScene',
    icon: '🏞️',
    credits: 10,
    route: '/tools/product-scene'
  },
  {
    key: 'productEnhance',
    icon: '✨',
    credits: 5,
    route: '/tools/product-enhance'
  }
]

// Scene types - descriptions use i18n keys from tools.scenes
const sceneTypes = [
  { key: 'studio', icon: '📷' },
  { key: 'nature', icon: '🌿' },
  { key: 'luxury', icon: '💎' },
  { key: 'minimal', icon: '⬜' },
  { key: 'lifestyle', icon: '🏠' }
]

const selectedScene = ref('studio')
const uploadedImage = ref<string | null>(null)
const uploadedFile = ref<File | null>(null)
const isProcessing = ref(false)
const result = ref<string | null>(null)
const examples = ref<any[]>([])
const selectedDemoImageId = ref<string | null>(null)

// Demo images from database
const demoImages = computed(() => {
  return demoTemplates.value
    .filter(t => t.group === 'product_scene' || t.group === 'background_removal')
    .map(t => ({
      id: t.id,
      name: isZh.value ? (t.prompt_zh || t.prompt) : t.prompt,
      preview: t.input_image_url,
      result_image_url: t.result_image_url,
      result_watermarked_url: t.result_watermarked_url
    }))
})

// Fallback examples if API returns empty
const fallbackExamples = [
  {
    id: 1,
    title: '產品去背',
    title_en: 'Product Background Removal',
    before: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&h=400&fit=crop',
    after: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&h=400&fit=crop',
    scene: 'studio'
  },
  {
    id: 2,
    title: '奢華場景',
    title_en: 'Luxury Scene',
    before: 'https://images.unsplash.com/photo-1585386959984-a4155224a1ad?w=600&h=400&fit=crop',
    after: 'https://images.unsplash.com/photo-1560343090-f0409e92791a?w=600&h=400&fit=crop',
    scene: 'luxury'
  },
  {
    id: 3,
    title: '自然背景',
    title_en: 'Nature Background',
    before: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&h=400&fit=crop',
    after: 'https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=600&h=400&fit=crop',
    scene: 'nature'
  }
]

async function loadExamples() {
  try {
    const response = await generationApi.getExamples('product')
    examples.value = response.examples?.length > 0 ? response.examples : fallbackExamples
  } catch (error) {
    console.error('Failed to load examples:', error)
    examples.value = fallbackExamples
  }
}

function selectDemoImage(item: { id: string; preview?: string; result_image_url?: string; result_watermarked_url?: string }) {
  selectedDemoImageId.value = item.id
  uploadedImage.value = item.preview || null
  uploadedFile.value = null
  result.value = null
}

function handleFileSelect(files: File[]) {
  // Demo users cannot upload custom images
  if (!canUseCustomInputs.value) {
    uiStore.showError(isZh.value ? '請訂閱以上傳自訂圖片' : 'Please subscribe to upload custom images')
    return
  }

  if (files.length > 0) {
    uploadedFile.value = files[0]
    selectedDemoImageId.value = null
    const reader = new FileReader()
    reader.onload = (e) => {
      uploadedImage.value = e.target?.result as string
    }
    reader.readAsDataURL(files[0])
  }
}

async function uploadImageFirst(): Promise<string | null> {
  if (!uploadedFile.value) return null
  try {
    const uploadResult = await demoApi.uploadImage(uploadedFile.value)
    return uploadResult.url
  } catch (error) {
    console.error('Image upload failed:', error)
    return null
  }
}

async function generateScene() {
  if (!uploadedImage.value) return

  isProcessing.value = true
  result.value = null

  try {
    // For demo users with selected template, use cached result
    if (isDemoUser.value && selectedDemoImageId.value) {
      const template = demoTemplates.value.find(t => t.id === selectedDemoImageId.value)
      if (template?.result_watermarked_url || template?.result_image_url) {
        result.value = template.result_watermarked_url || template.result_image_url || null
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }
    }

    // First upload the image to get an HTTP URL
    const imageUrl = await uploadImageFirst()
    if (!imageUrl) {
      uiStore.showError(isZh.value ? '圖片上傳失敗' : 'Failed to upload image')
      return
    }

    const response = await generationApi.generateProductScene({
      product_image_url: imageUrl,
      scene_type: selectedScene.value
    })

    if (response.success && response.result_url) {
      result.value = response.result_url
      uiStore.showSuccess(t('common.success'))
    }
  } catch (error) {
    console.error('Generation failed:', error)
    uiStore.showError(isZh.value ? '生成失敗' : 'Generation failed')
  } finally {
    isProcessing.value = false
  }
}

async function removeBackground() {
  if (!uploadedImage.value) return

  isProcessing.value = true
  result.value = null

  try {
    // For demo users with selected template, use cached result
    if (isDemoUser.value && selectedDemoImageId.value) {
      const template = demoTemplates.value.find(t => t.id === selectedDemoImageId.value)
      if (template?.result_watermarked_url || template?.result_image_url) {
        result.value = template.result_watermarked_url || template.result_image_url || null
        uiStore.showSuccess(isZh.value ? '去背成功（示範）' : 'Background removed (Demo)')
        return
      }
    }

    // First upload the image to get an HTTP URL
    const imageUrl = await uploadImageFirst()
    if (!imageUrl) {
      uiStore.showError(isZh.value ? '圖片上傳失敗' : 'Failed to upload image')
      return
    }

    const response = await generationApi.removeBackground({
      image_url: imageUrl
    })

    if (response.success && response.result_url) {
      result.value = response.result_url
      uiStore.showSuccess(t('common.success'))
    }
  } catch (error) {
    console.error('Background removal failed:', error)
    uiStore.showError(isZh.value ? '去背失敗' : 'Background removal failed')
  } finally {
    isProcessing.value = false
  }
}

onMounted(async () => {
  loadExamples()
  await loadDemoTemplates('product_scene')
})
</script>

<template>
  <div class="min-h-screen pt-20">
    <!-- Hero Section -->
    <section class="py-16 bg-gradient-to-b from-blue-500/10 to-transparent">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center">
          <span class="text-6xl mb-6 block">🛍️</span>
          <h1 class="text-4xl md:text-5xl font-bold text-white mb-4">
            {{ t('topics.product.name') }}
          </h1>
          <p class="text-xl text-gray-400 max-w-2xl mx-auto">
            {{ t('topics.product.longDesc') }}
          </p>

          <!-- Subscribe Notice for Demo Users -->
          <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
            <RouterLink to="/pricing" class="hover:underline">
              {{ isZh ? '訂閱以解鎖更多功能' : 'Subscribe to unlock more features' }}
            </RouterLink>
          </div>
        </div>
      </div>
    </section>

    <!-- Tools Section -->
    <section class="py-16">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 class="section-title text-center mb-12">{{ t('sections.availableTools') }}</h2>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div
            v-for="tool in tools"
            :key="tool.key"
            class="card-gradient hover:scale-[1.02] transition-transform cursor-pointer"
            @click="router.push(tool.route)"
          >
            <div class="flex items-center gap-4 mb-4">
              <span class="text-4xl">{{ tool.icon }}</span>
              <div>
                <h3 class="text-xl font-semibold text-white">
                  {{ t(`tools.${tool.key}.name`) }}
                </h3>
                <CreditCost :cost="tool.credits" />
              </div>
            </div>
            <p class="text-gray-400">
              {{ t(`tools.${tool.key}.desc`) }}
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- Quick Process Section -->
    <section class="py-16 bg-dark-800/50">
      <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 class="section-title text-center mb-8">{{ t('sections.quickProcess') }}</h2>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <!-- Upload Section -->
          <div>
            <h3 class="text-lg font-semibold text-white mb-4">{{ t('tools.common.productImage') }}</h3>

            <!-- Demo Images (for demo users) -->
            <div v-if="isDemoUser || demoImages.length > 0" class="mb-4">
              <p class="text-sm text-gray-400 mb-2">
                {{ isZh ? '選擇產品圖片' : 'Select Product Image' }}
              </p>
              <div v-if="isLoadingTemplates" class="flex justify-center py-4">
                <div class="animate-spin w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full"></div>
              </div>
              <div v-else class="grid grid-cols-3 gap-2">
                <button
                  v-for="item in demoImages.slice(0, 6)"
                  :key="item.id"
                  @click="selectDemoImage(item)"
                  class="aspect-square rounded-lg overflow-hidden border-2 transition-all"
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
                    <span class="text-2xl">📦</span>
                  </div>
                </button>
              </div>
            </div>

            <!-- Custom Upload (Subscribed Users Only) -->
            <div v-if="canUseCustomInputs">
              <p class="text-sm text-gray-400 mb-2">{{ isZh ? '或上傳自訂圖片' : 'Or upload custom image' }}</p>
              <UploadZone
                accept="image/*"
                @files-selected="handleFileSelect"
              />
            </div>

            <!-- Preview -->
            <div v-if="uploadedImage" class="mt-4">
              <img :src="uploadedImage" alt="Uploaded" class="w-full rounded-xl" />
              <button
                v-if="canUseCustomInputs"
                @click="uploadedImage = null; uploadedFile = null; selectedDemoImageId = null"
                class="btn-ghost text-sm w-full mt-2"
              >
                {{ isZh ? '更換圖片' : 'Change Image' }}
              </button>
            </div>
          </div>

          <!-- Options & Actions -->
          <div>
            <!-- Scene Selection -->
            <h3 class="text-lg font-semibold text-white mb-4">{{ t('tools.common.selectScene') }}</h3>
            <div class="grid grid-cols-2 gap-3 mb-6">
              <button
                v-for="scene in sceneTypes"
                :key="scene.key"
                @click="selectedScene = scene.key"
                class="p-4 rounded-xl text-left transition-all"
                :class="selectedScene === scene.key
                  ? 'bg-primary-500/20 border-2 border-primary-500'
                  : 'bg-dark-700 border-2 border-transparent hover:border-dark-600'"
              >
                <span class="text-2xl block mb-2">{{ scene.icon }}</span>
                <span class="text-white font-medium">{{ t(`tools.scenes.${scene.key}.name`) }}</span>
                <span class="text-gray-500 text-sm block">{{ t(`tools.scenes.${scene.key}.desc`) }}</span>
              </button>
            </div>

            <!-- Action Buttons -->
            <div class="space-y-3">
              <button
                @click="removeBackground"
                :disabled="!uploadedImage || isProcessing"
                class="btn-secondary w-full flex items-center justify-center gap-2"
              >
                <span>✂️</span>
                <span>{{ t('tools.removeBackground.name') }}</span>
                <CreditCost :cost="3" class="ml-auto" />
              </button>

              <button
                @click="generateScene"
                :disabled="!uploadedImage || isProcessing"
                class="btn-primary w-full flex items-center justify-center gap-2"
              >
                <span v-if="isProcessing" class="flex items-center gap-2">
                  <svg class="animate-spin w-5 h-5" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  {{ t('common.processing') }}
                </span>
                <template v-else>
                  <span>🏞️</span>
                  <span>{{ t('tools.productScene.name') }}</span>
                  <CreditCost :cost="10" class="ml-auto" />
                </template>
              </button>
            </div>

            <!-- Result -->
            <div v-if="result" class="mt-6 card overflow-hidden">
              <h4 class="text-white font-semibold mb-3">{{ t('common.result') }}</h4>
              <img :src="result" alt="Result" class="w-full rounded-lg" />

              <!-- Watermark Notice for Demo -->
              <div v-if="isDemoUser" class="mt-3 text-center text-sm text-yellow-400">
                {{ isZh ? '示範結果帶有浮水印' : 'Demo result has watermark' }}
              </div>

              <div class="mt-4 flex justify-end gap-4">
                <button
                  v-if="canDownloadOriginal"
                  class="btn-secondary"
                >
                  {{ t('common.download') }}
                </button>
                <RouterLink
                  v-else
                  to="/pricing"
                  class="btn-primary"
                >
                  {{ isZh ? '訂閱以下載' : 'Subscribe to Download' }}
                </RouterLink>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Examples Gallery -->
    <section class="py-16">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 class="section-title text-center mb-12">{{ t('examples.title') }}</h2>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="example in examples"
            :key="example.id"
            class="card overflow-hidden"
          >
            <h4 class="text-lg font-semibold text-white mb-4">{{ getLocalizedField(example, 'title') }}</h4>

            <!-- Before/After Slider -->
            <div v-if="example.before && example.after" class="rounded-xl overflow-hidden">
              <BeforeAfterSlider
                :before-image="example.before"
                :after-image="example.after"
                :before-label="t('examples.before')"
                :after-label="t('examples.after')"
              />
            </div>

            <!-- Scene badge -->
            <div v-if="example.scene" class="mt-3">
              <span class="inline-block px-3 py-1 bg-primary-500/20 text-primary-400 rounded-full text-sm">
                {{ t(`styles.${example.scene}`) }}
              </span>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="examples.length === 0" class="text-center py-12">
          <span class="text-6xl mb-4 block">🛍️</span>
          <p class="text-gray-400">{{ t('examples.loading') }}</p>
        </div>
      </div>
    </section>

    <!-- CTA Section -->
    <section class="py-16 bg-gradient-to-b from-blue-500/10 to-transparent">
      <div class="max-w-3xl mx-auto px-4 text-center">
        <h2 class="text-3xl font-bold text-white mb-6">
          {{ t('topics.product.ctaTitle') }}
        </h2>
        <p class="text-xl text-gray-400 mb-8">
          {{ t('topics.product.ctaDesc') }}
        </p>
        <RouterLink to="/auth/register" class="btn-primary text-lg px-10 py-4">
          {{ t('common.startFree') }}
        </RouterLink>
      </div>
    </section>
  </div>
</template>
