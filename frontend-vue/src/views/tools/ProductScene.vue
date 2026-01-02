<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore, useCreditsStore } from '@/stores'
import { demoApi } from '@/api'
import UploadZone from '@/components/tools/UploadZone.vue'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'

const { t } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()

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
  { id: 'custom', icon: '🎨', name: t('tools.scenes.custom.name'), desc: t('tools.scenes.custom.desc') }
])

async function handleFilesSelected(files: File[]) {
  const file = files[0]
  if (file) {
    const reader = new FileReader()
    reader.onload = (e) => {
      uploadedImage.value = e.target?.result as string
      resultImages.value = []
    }
    reader.readAsDataURL(file)
  }
}

async function generateScenes() {
  if (!uploadedImage.value) return

  isProcessing.value = true
  try {
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

function reset() {
  uploadedImage.value = null
  resultImages.value = []
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20">
    <LoadingOverlay :show="isProcessing" :message="t('common.processing')" />

    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-white mb-4">
          {{ t('tools.productScene.name') }}
        </h1>
        <p class="text-xl text-gray-400">
          {{ t('tools.productScene.longDesc') }}
        </p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Left Panel - Upload -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">{{ t('tools.common.productImage') }}</h3>

          <div v-if="!uploadedImage">
            <UploadZone
              accept="image/*"
              @files="handleFilesSelected"
              @error="(msg) => uiStore.showError(msg)"
            />
          </div>

          <div v-else class="space-y-4">
            <img :src="uploadedImage" alt="Product" class="w-full rounded-xl" />
            <button @click="reset" class="btn-ghost text-sm w-full">
              {{ t('tools.common.changeImage') }}
            </button>
          </div>
        </div>

        <!-- Middle Panel - Scene Selection -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">{{ t('tools.common.selectScene') }}</h3>

          <div class="grid grid-cols-2 gap-3">
            <button
              v-for="scene in sceneTemplates"
              :key="scene.id"
              @click="selectedScene = scene.id"
              class="p-4 rounded-xl border-2 transition-all text-left"
              :class="selectedScene === scene.id
                ? 'border-primary-500 bg-primary-500/10'
                : 'border-dark-600 hover:border-dark-500'"
            >
              <span class="text-2xl">{{ scene.icon }}</span>
              <p class="font-medium text-white mt-2">{{ scene.name }}</p>
              <p class="text-xs text-gray-500">{{ scene.desc }}</p>
            </button>
          </div>

          <!-- Custom Prompt -->
          <div v-if="selectedScene === 'custom'" class="mt-4">
            <label class="label">{{ t('tools.common.describeScene') }}</label>
            <textarea
              v-model="prompt"
              class="input-field resize-none"
              rows="3"
              :placeholder="t('tools.common.scenePlaceholder')"
            />
          </div>

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
            <button class="btn-primary w-full">
              {{ t('common.download') }}
            </button>
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
