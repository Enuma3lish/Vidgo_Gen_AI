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

const uploadedImage = ref<string | null>(null)
const resultVideo = ref<string | null>(null)
const isProcessing = ref(false)
const prompt = ref('')
const selectedDuration = ref(5)
const selectedMotion = ref('auto')

const durationOptions = [3, 5, 10]

const motionOptions = [
  { id: 'auto', name: 'Auto', desc: 'AI decides motion' },
  { id: 'zoom-in', name: 'Zoom In', desc: 'Gradual zoom effect' },
  { id: 'zoom-out', name: 'Zoom Out', desc: 'Pull back effect' },
  { id: 'pan-left', name: 'Pan Left', desc: 'Horizontal movement' },
  { id: 'pan-right', name: 'Pan Right', desc: 'Horizontal movement' },
  { id: 'rotate', name: 'Rotate', desc: 'Circular motion' }
]

function handleFilesSelected(files: File[]) {
  const file = files[0]
  if (file) {
    const reader = new FileReader()
    reader.onload = (e) => {
      uploadedImage.value = e.target?.result as string
      resultVideo.value = null
    }
    reader.readAsDataURL(file)
  }
}

async function generateVideo() {
  if (!uploadedImage.value && !prompt.value) {
    uiStore.showError('Please upload an image or enter a prompt')
    return
  }

  isProcessing.value = true
  try {
    let imageUrl = null
    if (uploadedImage.value) {
      const uploadResult = await demoApi.uploadImage(
        dataURItoBlob(uploadedImage.value) as File
      )
      imageUrl = uploadResult.url
    }

    const result = await demoApi.generate({
      tool: 'short_video',
      image_url: imageUrl || undefined,
      prompt: prompt.value || undefined,
      params: {
        duration: selectedDuration.value,
        motion: selectedMotion.value
      }
    })

    if (result.success && result.video_url) {
      resultVideo.value = result.video_url
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
  resultVideo.value = null
  prompt.value = ''
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20">
    <LoadingOverlay :show="isProcessing" :message="'Generating video... This may take a few minutes'" />

    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-white mb-4">
          {{ t('tools.shortVideo.name') }}
        </h1>
        <p class="text-xl text-gray-400">
          {{ t('tools.shortVideo.longDesc') }}
        </p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Left Panel - Input -->
        <div class="space-y-6">
          <!-- Source Selection -->
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-4">Source Image (Optional)</h3>

            <div v-if="!uploadedImage">
              <UploadZone
                accept="image/*"
                @files="handleFilesSelected"
                @error="(msg) => uiStore.showError(msg)"
              />
            </div>

            <div v-else class="space-y-4">
              <img :src="uploadedImage" alt="Source" class="w-full rounded-xl" />
              <button @click="uploadedImage = null" class="btn-ghost text-sm w-full">
                Remove Image
              </button>
            </div>
          </div>

          <!-- Prompt -->
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-4">Video Description</h3>
            <textarea
              v-model="prompt"
              class="input-field resize-none"
              rows="4"
              placeholder="Describe the video you want to create..."
            />
          </div>

          <!-- Settings -->
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-4">Video Settings</h3>

            <!-- Duration -->
            <div class="mb-6">
              <label class="label">Duration</label>
              <div class="flex gap-3">
                <button
                  v-for="dur in durationOptions"
                  :key="dur"
                  @click="selectedDuration = dur"
                  class="flex-1 py-3 rounded-xl border-2 transition-all"
                  :class="selectedDuration === dur
                    ? 'border-primary-500 bg-primary-500/10'
                    : 'border-dark-600 hover:border-dark-500'"
                >
                  {{ dur }}s
                </button>
              </div>
            </div>

            <!-- Motion Type -->
            <div>
              <label class="label">Motion Type</label>
              <div class="grid grid-cols-3 gap-2">
                <button
                  v-for="motion in motionOptions"
                  :key="motion.id"
                  @click="selectedMotion = motion.id"
                  class="p-3 rounded-xl border-2 transition-all text-center"
                  :class="selectedMotion === motion.id
                    ? 'border-primary-500 bg-primary-500/10'
                    : 'border-dark-600 hover:border-dark-500'"
                >
                  <p class="text-sm font-medium">{{ motion.name }}</p>
                </button>
              </div>
            </div>

            <!-- Credit Cost & Generate -->
            <div class="mt-6 pt-4 border-t border-dark-700">
              <CreditCost service="short_video" />
              <button
                @click="generateVideo"
                :disabled="(!uploadedImage && !prompt) || isProcessing"
                class="btn-primary w-full mt-4"
              >
                {{ t('common.generate') }}
              </button>
            </div>
          </div>
        </div>

        <!-- Right Panel - Result -->
        <div class="card h-fit sticky top-24">
          <h3 class="text-lg font-semibold text-white mb-4">Generated Video</h3>

          <div v-if="resultVideo" class="space-y-4">
            <video
              :src="resultVideo"
              controls
              class="w-full rounded-xl"
              autoplay
              loop
            />
            <button class="btn-primary w-full">
              {{ t('common.download') }}
            </button>
          </div>

          <div v-else class="aspect-video flex items-center justify-center bg-dark-700 rounded-xl text-gray-500">
            <div class="text-center">
              <span class="text-5xl block mb-4">🎬</span>
              <p>Generated video will appear here</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
