<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { toolsApi } from '@/api'
import ImageUploader from '@/components/common/ImageUploader.vue'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'

const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()

const { isDemoUser } = useDemoMode()

const uploadedImage = ref<string | undefined>(undefined)
const resultImage = ref<string | undefined>(undefined)
const isProcessing = ref(false)
const scale = ref(2)

const demoExamples = [
  { id: 'upscale-1', url: 'https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=600&q=80', label: 'Landscape' },
  { id: 'upscale-2', url: 'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=600&q=80', label: 'Forest' },
  { id: 'upscale-3', url: 'https://images.unsplash.com/photo-1494526585095-c41746248156?w=600&q=80', label: 'Interior' },
  { id: 'upscale-4', url: 'https://images.unsplash.com/photo-1518837695005-2083093ee35b?w=600&q=80', label: 'Ocean' }
]

function selectDemoExample(example: { id: string; url: string }) {
  uploadedImage.value = example.url
  resultImage.value = undefined
}

async function handleUpscale() {
  if (!uploadedImage.value) {
    uiStore.showWarning('Please select or upload an image first')
    return
  }

  isProcessing.value = true
  resultImage.value = undefined

  if (isDemoUser.value) {
    await new Promise(r => setTimeout(r, 1200))
    resultImage.value = uploadedImage.value
    uiStore.showSuccess(`Preview ready. Subscribe to download the real ${scale.value}x HD version.`)
    isProcessing.value = false
    return
  }

  try {
    const result = await toolsApi.upscale(uploadedImage.value, scale.value)
    if (result.success && result.result_url) {
      resultImage.value = result.result_url
      creditsStore.fetchBalance()
      uiStore.showSuccess(`Image upscaled ${scale.value}x successfully!`)
    } else {
      uiStore.showError(result.message || 'Upscale failed')
    }
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.message || 'Upscale failed'
    uiStore.showError(detail)
  } finally {
    isProcessing.value = false
  }
}

function onImageUploaded(url: string) {
  uploadedImage.value = url
  resultImage.value = undefined
}
</script>

<template>
  <div class="min-h-screen pt-20 pb-20" style="background: #09090b;">
    <div class="max-w-5xl mx-auto px-4">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold mb-2" style="color: #f5f5fa;">HD Image Upscale</h1>
        <p style="color: #9494b0;">Upscale images to 2x or 4x resolution with AI</p>
        <CreditCost :cost="10" class="mt-2" />
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            Subscribe to upload your own images and download HD results
          </RouterLink>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="space-y-4">
          <!-- Demo: preset examples grid -->
          <div v-if="isDemoUser" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-3" style="color: #e8e8f0;">Try a demo image</label>
            <div class="grid grid-cols-2 gap-2">
              <button
                v-for="example in demoExamples"
                :key="example.id"
                @click="selectDemoExample(example)"
                class="aspect-video rounded-lg overflow-hidden border-2 transition-all"
                :class="uploadedImage === example.url ? 'border-primary-500' : 'hover:border-dark-500'"
                style="border-color: rgba(255,255,255,0.08);"
              >
                <img :src="example.url" :alt="example.label" class="w-full h-full object-cover" />
              </button>
            </div>
          </div>

          <!-- Paid: upload zone -->
          <div v-else class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-3" style="color: #e8e8f0;">Upload Image</label>
            <ImageUploader @uploaded="onImageUploaded" />
          </div>

          <div v-if="uploadedImage" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">Original</label>
            <img :src="uploadedImage" class="w-full rounded-lg" style="max-height: 300px; object-fit: contain;" />
          </div>

          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">Upscale Factor</label>
            <div class="flex gap-3">
              <button
                @click="scale = 2"
                class="flex-1 py-2 rounded-lg text-sm font-medium transition-all"
                :style="scale === 2 ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >
                2x
              </button>
              <button
                @click="scale = 4"
                class="flex-1 py-2 rounded-lg text-sm font-medium transition-all"
                :style="scale === 4 ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >
                4x
              </button>
            </div>
          </div>

          <button
            @click="handleUpscale"
            :disabled="isProcessing || !uploadedImage"
            class="w-full py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-50"
            style="background: #1677ff;"
          >
            {{ isProcessing ? 'Upscaling...' : `Upscale ${scale}x` }}
          </button>
        </div>

        <div class="rounded-xl p-4 flex items-center justify-center min-h-[400px]" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <LoadingOverlay :show="isProcessing" message="Upscaling image..." />
          <div v-if="!isProcessing && resultImage" class="w-full">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">Upscaled Result ({{ scale }}x)</label>
            <img :src="resultImage" class="w-full rounded-lg" style="max-height: 500px; object-fit: contain;" />
            <a
              v-if="!isDemoUser"
              :href="resultImage"
              target="_blank"
              download
              class="block mt-3 text-center py-2 rounded-lg text-sm font-medium transition-colors"
              style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
            >
              Download HD Image
            </a>
            <RouterLink
              v-else
              to="/pricing"
              class="block mt-3 text-center py-2 rounded-lg text-sm font-medium transition-colors"
              style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
            >
              Subscribe to download HD
            </RouterLink>
          </div>
          <div v-if="!isProcessing && !resultImage" class="text-center" style="color: #6b6b8a;">
            <svg class="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <p class="text-sm">{{ isDemoUser ? 'Pick a demo image and click Upscale' : 'Upload an image to upscale' }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
