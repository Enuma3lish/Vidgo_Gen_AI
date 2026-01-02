<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore, useCreditsStore } from '@/stores'
import { demoApi } from '@/api'
import UploadZone from '@/components/tools/UploadZone.vue'
import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'

const { t } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()

const uploadedImage = ref<string | null>(null)
const resultImage = ref<string | null>(null)
const isProcessing = ref(false)
const selectedBgType = ref<'transparent' | 'white' | 'custom'>('transparent')
const customBgColor = ref('#ffffff')

const bgOptions = [
  { value: 'transparent', label: 'Transparent', icon: '🔲' },
  { value: 'white', label: 'White', icon: '⬜' },
  { value: 'custom', label: 'Custom Color', icon: '🎨' }
]

async function handleFilesSelected(files: File[]) {
  const file = files[0]
  if (file) {
    const reader = new FileReader()
    reader.onload = (e) => {
      uploadedImage.value = e.target?.result as string
      resultImage.value = null
    }
    reader.readAsDataURL(file)
  }
}

async function processImage() {
  if (!uploadedImage.value) return

  isProcessing.value = true
  try {
    // Upload image first
    const uploadResult = await demoApi.uploadImage(
      dataURItoBlob(uploadedImage.value) as File
    )

    // Call generate API
    const result = await demoApi.generate({
      tool: 'background_removal',
      image_url: uploadResult.url,
      params: {
        bg_type: selectedBgType.value,
        bg_color: selectedBgType.value === 'custom' ? customBgColor.value : null
      }
    })

    if (result.success && result.image_url) {
      resultImage.value = result.image_url
      creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success'))
    } else {
      uiStore.showError(result.message || 'Processing failed')
    }
  } catch (error) {
    uiStore.showError('An error occurred while processing')
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

function downloadResult() {
  if (!resultImage.value) return
  const link = document.createElement('a')
  link.href = resultImage.value
  link.download = 'background-removed.png'
  link.click()
}

function reset() {
  uploadedImage.value = null
  resultImage.value = null
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20">
    <LoadingOverlay :show="isProcessing" :message="t('common.processing')" />

    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-white mb-4">
          {{ t('tools.backgroundRemoval.name') }}
        </h1>
        <p class="text-xl text-gray-400">
          {{ t('tools.backgroundRemoval.longDesc') }}
        </p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Left Panel - Upload & Settings -->
        <div class="space-y-6">
          <!-- Upload Zone -->
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-4">{{ t('common.upload') }}</h3>

            <div v-if="!uploadedImage">
              <UploadZone
                accept="image/*"
                @files="handleFilesSelected"
                @error="(msg) => uiStore.showError(msg)"
              />
            </div>

            <div v-else class="space-y-4">
              <img
                :src="uploadedImage"
                alt="Uploaded"
                class="w-full rounded-xl"
              />
              <button @click="reset" class="btn-ghost text-sm">
                Upload Different Image
              </button>
            </div>
          </div>

          <!-- Settings -->
          <div v-if="uploadedImage" class="card">
            <h3 class="text-lg font-semibold text-white mb-4">Background Type</h3>

            <div class="grid grid-cols-3 gap-3">
              <button
                v-for="option in bgOptions"
                :key="option.value"
                @click="selectedBgType = option.value as any"
                class="p-4 rounded-xl border-2 transition-all text-center"
                :class="selectedBgType === option.value
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'border-dark-600 hover:border-dark-500'"
              >
                <span class="text-2xl block mb-2">{{ option.icon }}</span>
                <span class="text-sm">{{ option.label }}</span>
              </button>
            </div>

            <!-- Custom Color Picker -->
            <div v-if="selectedBgType === 'custom'" class="mt-4">
              <label class="label">Select Color</label>
              <input
                type="color"
                v-model="customBgColor"
                class="w-full h-12 rounded-lg cursor-pointer"
              />
            </div>

            <!-- Credit Cost -->
            <div class="mt-6 pt-4 border-t border-dark-700">
              <CreditCost service="background_removal" />
            </div>

            <!-- Generate Button -->
            <button
              @click="processImage"
              :disabled="isProcessing"
              class="btn-primary w-full mt-4"
            >
              {{ t('common.generate') }}
            </button>
          </div>
        </div>

        <!-- Right Panel - Results -->
        <div>
          <div class="card h-full">
            <h3 class="text-lg font-semibold text-white mb-4">Result</h3>

            <div v-if="resultImage && uploadedImage" class="space-y-4">
              <BeforeAfterSlider
                :before-image="uploadedImage"
                :after-image="resultImage"
                before-label="Before"
                after-label="After"
              />

              <button @click="downloadResult" class="btn-primary w-full">
                {{ t('common.download') }}
              </button>
            </div>

            <div v-else class="h-64 flex items-center justify-center text-gray-500">
              <div class="text-center">
                <svg class="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <p>Upload an image to see the result</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
