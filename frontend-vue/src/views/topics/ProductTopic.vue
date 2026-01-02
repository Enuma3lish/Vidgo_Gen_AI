<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import UploadZone from '@/components/tools/UploadZone.vue'
import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import CreditCost from '@/components/tools/CreditCost.vue'
import { generationApi } from '@/api/generation'
import { useLocalized } from '@/composables/useLocalized'

const { t } = useI18n()
const { getLocalizedField } = useLocalized()
const router = useRouter()

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
const isProcessing = ref(false)
const result = ref<string | null>(null)
const examples = ref<any[]>([])

async function loadExamples() {
  try {
    const response = await generationApi.getExamples('product')
    examples.value = response.examples || []
  } catch (error) {
    console.error('Failed to load examples:', error)
  }
}

function handleFileSelect(files: File[]) {
  if (files.length > 0) {
    const reader = new FileReader()
    reader.onload = (e) => {
      uploadedImage.value = e.target?.result as string
    }
    reader.readAsDataURL(files[0])
  }
}

async function generateScene() {
  if (!uploadedImage.value) return

  isProcessing.value = true
  result.value = null

  try {
    const response = await generationApi.generateProductScene({
      product_image_url: uploadedImage.value,
      scene_type: selectedScene.value
    })

    if (response.success && response.result_url) {
      result.value = response.result_url
    }
  } catch (error) {
    console.error('Generation failed:', error)
  } finally {
    isProcessing.value = false
  }
}

async function removeBackground() {
  if (!uploadedImage.value) return

  isProcessing.value = true
  result.value = null

  try {
    const response = await generationApi.removeBackground({
      image_url: uploadedImage.value
    })

    if (response.success && response.result_url) {
      result.value = response.result_url
    }
  } catch (error) {
    console.error('Background removal failed:', error)
  } finally {
    isProcessing.value = false
  }
}

onMounted(() => {
  loadExamples()
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
            <UploadZone
              accept="image/*"
              @files-selected="handleFileSelect"
            />

            <!-- Preview -->
            <div v-if="uploadedImage" class="mt-4">
              <img :src="uploadedImage" alt="Uploaded" class="w-full rounded-xl" />
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
              <div class="mt-4 flex justify-end gap-4">
                <button class="btn-secondary">
                  {{ t('common.download') }}
                </button>
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
