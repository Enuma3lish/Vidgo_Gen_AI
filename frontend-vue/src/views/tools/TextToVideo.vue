<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { toolsApi } from '@/api'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'

const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()

const { isDemoUser } = useDemoMode()

const prompt = ref('')
const duration = ref(5)
const resolution = ref('1080P')
const aspectRatio = ref('16:9')
const resultVideo = ref<string | undefined>(undefined)
const isProcessing = ref(false)

const quickPrompts = [
  { label: 'Ocean Waves', prompt: 'Calm ocean waves crashing on a sandy beach at sunset, cinematic, 4K' },
  { label: 'City Night', prompt: 'Bustling city street at night with neon lights and rain reflections' },
  { label: 'Nature', prompt: 'A serene forest with sunlight filtering through tall trees, gentle breeze' },
  { label: 'Product Showcase', prompt: 'Elegant product rotating on a marble surface with soft studio lighting' },
  { label: 'Food', prompt: 'Steaming hot coffee being poured into a ceramic cup, close-up, warm lighting' },
  { label: 'Fashion', prompt: 'Model walking on a runway with dramatic lighting and slow motion' },
]

function selectQuickPrompt(p: string) {
  prompt.value = p
}

async function handleGenerate() {
  if (!prompt.value.trim()) {
    uiStore.showWarning('Please enter a prompt')
    return
  }

  if (isDemoUser.value) {
    uiStore.showInfo('Subscribe to generate custom videos from text.')
    router.push('/pricing')
    return
  }

  isProcessing.value = true
  resultVideo.value = undefined
  try {
    const result = await toolsApi.textToVideo(prompt.value, {
      duration: duration.value,
      resolution: resolution.value,
      aspectRatio: aspectRatio.value,
    })
    if (result.success && result.result_url) {
      resultVideo.value = result.result_url
      creditsStore.fetchBalance()
      uiStore.showSuccess('Video generated successfully!')
    } else {
      uiStore.showError(result.message || 'Generation failed')
    }
  } catch (err: any) {
    uiStore.showError(err.response?.data?.detail || 'Generation failed')
  } finally {
    isProcessing.value = false
  }
}
</script>

<template>
  <div class="min-h-screen pt-20 pb-20" style="background: #09090b;">
    <div class="max-w-4xl mx-auto px-4">
      <!-- Header -->
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold mb-2" style="color: #f5f5fa;">Text to Video</h1>
        <p style="color: #9494b0;">Generate videos from text descriptions using AI</p>
        <CreditCost :cost="30" class="mt-2" />
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Left: Input -->
        <div class="space-y-4">
          <!-- Prompt -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">Prompt</label>
            <textarea
              v-model="prompt"
              rows="4"
              class="w-full rounded-lg p-3 text-sm resize-none"
              style="background: #0d0d15; color: #f5f5fa; border: 1px solid rgba(255,255,255,0.1);"
              placeholder="Describe the video you want to create..."
            />
          </div>

          <!-- Quick Prompts -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">Quick Prompts</label>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="qp in quickPrompts"
                :key="qp.label"
                @click="selectQuickPrompt(qp.prompt)"
                class="px-3 py-1.5 rounded-lg text-xs transition-colors"
                style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
              >
                {{ qp.label }}
              </button>
            </div>
          </div>

          <!-- Options -->
          <div class="rounded-xl p-4 space-y-3" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <div>
              <label class="block text-xs mb-1" style="color: #9494b0;">Duration</label>
              <select v-model="duration" class="w-full rounded-lg p-2 text-sm" style="background: #0d0d15; color: #f5f5fa; border: 1px solid rgba(255,255,255,0.1);">
                <option :value="5">5 seconds</option>
                <option :value="10">10 seconds</option>
                <option :value="15">15 seconds</option>
              </select>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs mb-1" style="color: #9494b0;">Resolution</label>
                <select v-model="resolution" class="w-full rounded-lg p-2 text-sm" style="background: #0d0d15; color: #f5f5fa; border: 1px solid rgba(255,255,255,0.1);">
                  <option value="720P">720P</option>
                  <option value="1080P">1080P</option>
                </select>
              </div>
              <div>
                <label class="block text-xs mb-1" style="color: #9494b0;">Aspect Ratio</label>
                <select v-model="aspectRatio" class="w-full rounded-lg p-2 text-sm" style="background: #0d0d15; color: #f5f5fa; border: 1px solid rgba(255,255,255,0.1);">
                  <option value="16:9">16:9 Landscape</option>
                  <option value="9:16">9:16 Portrait</option>
                  <option value="1:1">1:1 Square</option>
                </select>
              </div>
            </div>
          </div>

          <!-- Generate Button -->
          <button
            @click="handleGenerate"
            :disabled="isProcessing || !prompt.trim()"
            class="w-full py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-50"
            style="background: #1677ff;"
          >
            {{ isProcessing ? 'Generating...' : 'Generate Video' }}
          </button>
        </div>

        <!-- Right: Result -->
        <div class="rounded-xl p-4 flex items-center justify-center min-h-[400px]" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <LoadingOverlay :show="isProcessing" message="Generating video... This may take 30-60 seconds." />
          <video
            v-if="!isProcessing && resultVideo"
            :src="resultVideo"
            controls
            autoplay
            loop
            class="w-full rounded-lg"
            style="max-height: 500px;"
          />
          <div v-if="!isProcessing && !resultVideo" class="text-center" style="color: #6b6b8a;">
            <svg class="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <p class="text-sm">Enter a prompt and click Generate</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
