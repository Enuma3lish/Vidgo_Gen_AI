<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore, useCreditsStore } from '@/stores'
import { demoApi } from '@/api'
import UploadZone from '@/components/tools/UploadZone.vue'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'

const { t } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()

const clothingImage = ref<string | null>(null)
const modelImage = ref<string | null>(null)
const resultImage = ref<string | null>(null)
const isProcessing = ref(false)
const selectedModel = ref('female-1')

const modelOptions = [
  { id: 'female-1', name: 'Female Model 1', preview: 'https://picsum.photos/seed/model1/100/150' },
  { id: 'female-2', name: 'Female Model 2', preview: 'https://picsum.photos/seed/model2/100/150' },
  { id: 'male-1', name: 'Male Model 1', preview: 'https://picsum.photos/seed/model3/100/150' },
  { id: 'male-2', name: 'Male Model 2', preview: 'https://picsum.photos/seed/model4/100/150' },
  { id: 'custom', name: 'Upload Custom', preview: null }
]

function handleClothingSelected(files: File[]) {
  const file = files[0]
  if (file) {
    const reader = new FileReader()
    reader.onload = (e) => {
      clothingImage.value = e.target?.result as string
      resultImage.value = null
    }
    reader.readAsDataURL(file)
  }
}

function handleModelSelected(files: File[]) {
  const file = files[0]
  if (file) {
    const reader = new FileReader()
    reader.onload = (e) => {
      modelImage.value = e.target?.result as string
    }
    reader.readAsDataURL(file)
  }
}

async function generateTryOn() {
  if (!clothingImage.value) return

  isProcessing.value = true
  try {
    const uploadResult = await demoApi.uploadImage(
      dataURItoBlob(clothingImage.value) as File
    )

    let modelUrl = null
    if (selectedModel.value === 'custom' && modelImage.value) {
      const modelUpload = await demoApi.uploadImage(
        dataURItoBlob(modelImage.value) as File
      )
      modelUrl = modelUpload.url
    }

    const result = await demoApi.generate({
      tool: 'virtual_try_on',
      image_url: uploadResult.url,
      params: {
        model_id: selectedModel.value,
        model_image: modelUrl
      }
    })

    if (result.success && result.image_url) {
      resultImage.value = result.image_url
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
      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-white mb-4">
          {{ t('tools.tryOn.name') }}
        </h1>
        <p class="text-xl text-gray-400">
          {{ t('tools.tryOn.longDesc') }}
        </p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Left Panel - Clothing Upload -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">Clothing Item</h3>

          <div v-if="!clothingImage">
            <UploadZone
              accept="image/*"
              @files="handleClothingSelected"
              @error="(msg) => uiStore.showError(msg)"
            />
          </div>

          <div v-else class="space-y-4">
            <img :src="clothingImage" alt="Clothing" class="w-full rounded-xl" />
            <button @click="clothingImage = null" class="btn-ghost text-sm w-full">
              Change Clothing
            </button>
          </div>
        </div>

        <!-- Middle Panel - Model Selection -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">Select Model</h3>

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
              <div v-if="model.preview" class="aspect-[2/3] rounded-lg overflow-hidden mb-2">
                <img :src="model.preview" :alt="model.name" class="w-full h-full object-cover" />
              </div>
              <div v-else class="aspect-[2/3] rounded-lg bg-dark-700 flex items-center justify-center mb-2">
                <span class="text-3xl">📤</span>
              </div>
              <p class="text-xs text-center">{{ model.name }}</p>
            </button>
          </div>

          <!-- Custom Model Upload -->
          <div v-if="selectedModel === 'custom'" class="mt-4">
            <UploadZone
              accept="image/*"
              @files="handleModelSelected"
              @error="(msg) => uiStore.showError(msg)"
            />
          </div>

          <!-- Credit Cost & Generate -->
          <div class="mt-6 pt-4 border-t border-dark-700">
            <CreditCost service="virtual_try_on" />
            <button
              @click="generateTryOn"
              :disabled="!clothingImage || isProcessing"
              class="btn-primary w-full mt-4"
            >
              {{ t('common.generate') }}
            </button>
          </div>
        </div>

        <!-- Right Panel - Result -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">Try-On Result</h3>

          <div v-if="resultImage" class="space-y-4">
            <img :src="resultImage" alt="Result" class="w-full rounded-xl" />
            <button class="btn-primary w-full">
              {{ t('common.download') }}
            </button>
          </div>

          <div v-else class="h-64 flex items-center justify-center text-gray-500">
            <div class="text-center">
              <span class="text-5xl block mb-4">👔</span>
              <p>Virtual try-on result will appear here</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
