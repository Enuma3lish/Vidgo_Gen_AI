<script setup lang="ts">
import { ref } from 'vue'
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
const selectedStyle = ref('modern')

const styleOptions = [
  { id: 'modern', name: 'Modern', icon: '🏢', desc: 'Clean contemporary design' },
  { id: 'minimalist', name: 'Minimalist', icon: '⬜', desc: 'Simple and clutter-free' },
  { id: 'scandinavian', name: 'Scandinavian', icon: '🌲', desc: 'Light woods and neutral tones' },
  { id: 'industrial', name: 'Industrial', icon: '🏭', desc: 'Raw materials and exposed elements' },
  { id: 'bohemian', name: 'Bohemian', icon: '🎨', desc: 'Eclectic and colorful' },
  { id: 'traditional', name: 'Traditional', icon: '🏛️', desc: 'Classic and elegant' }
]

function handleFilesSelected(files: File[]) {
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

async function generateRedesign() {
  if (!uploadedImage.value) return

  isProcessing.value = true
  try {
    const uploadResult = await demoApi.uploadImage(
      dataURItoBlob(uploadedImage.value) as File
    )

    const result = await demoApi.generate({
      tool: 'room_redesign',
      image_url: uploadResult.url,
      params: {
        style: selectedStyle.value
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
          {{ t('tools.roomRedesign.name') }}
        </h1>
        <p class="text-xl text-gray-400">
          {{ t('tools.roomRedesign.longDesc') }}
        </p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Left Panel - Upload & Settings -->
        <div class="space-y-6">
          <!-- Upload Zone -->
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-4">Room Photo</h3>

            <div v-if="!uploadedImage">
              <UploadZone
                accept="image/*"
                @files="handleFilesSelected"
                @error="(msg) => uiStore.showError(msg)"
              />
            </div>

            <div v-else class="space-y-4">
              <img :src="uploadedImage" alt="Room" class="w-full rounded-xl" />
              <button @click="reset" class="btn-ghost text-sm w-full">
                Upload Different Room
              </button>
            </div>
          </div>

          <!-- Style Selection -->
          <div v-if="uploadedImage" class="card">
            <h3 class="text-lg font-semibold text-white mb-4">Design Style</h3>

            <div class="grid grid-cols-2 gap-3">
              <button
                v-for="style in styleOptions"
                :key="style.id"
                @click="selectedStyle = style.id"
                class="p-4 rounded-xl border-2 transition-all text-left"
                :class="selectedStyle === style.id
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'border-dark-600 hover:border-dark-500'"
              >
                <span class="text-2xl">{{ style.icon }}</span>
                <p class="font-medium text-white mt-2">{{ style.name }}</p>
                <p class="text-xs text-gray-500">{{ style.desc }}</p>
              </button>
            </div>

            <!-- Credit Cost & Generate -->
            <div class="mt-6 pt-4 border-t border-dark-700">
              <CreditCost service="room_redesign" />
              <button
                @click="generateRedesign"
                :disabled="!uploadedImage || isProcessing"
                class="btn-primary w-full mt-4"
              >
                {{ t('common.generate') }}
              </button>
            </div>
          </div>
        </div>

        <!-- Right Panel - Results -->
        <div class="card h-fit">
          <h3 class="text-lg font-semibold text-white mb-4">Redesigned Room</h3>

          <div v-if="resultImage && uploadedImage" class="space-y-4">
            <BeforeAfterSlider
              :before-image="uploadedImage"
              :after-image="resultImage"
              before-label="Original"
              after-label="Redesigned"
            />
            <button class="btn-primary w-full">
              {{ t('common.download') }}
            </button>
          </div>

          <div v-else class="h-64 flex items-center justify-center text-gray-500">
            <div class="text-center">
              <span class="text-5xl block mb-4">🏠</span>
              <p>Redesigned room will appear here</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
