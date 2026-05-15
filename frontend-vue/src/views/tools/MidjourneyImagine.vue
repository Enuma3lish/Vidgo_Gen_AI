<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { toolsApi } from '@/api'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'

const { t } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { isDemoUser } = useDemoMode()

const prompt = ref('')
const aspectRatio = ref<'1:1' | '16:9' | '9:16' | '4:3' | '3:4'>('1:1')
const processMode = ref<'relax' | 'fast' | 'turbo'>('fast')
const resultImage = ref<string | undefined>(undefined)
const isProcessing = ref(false)

// Curated prompts that are known to produce strong Midjourney results.
// Prompt text stays English (the model's native input); label is i18n'd.
// Each one is a complete, ready-to-generate payload — picking → click
// Generate produces a result with no further input required.
const PROMPT_PRESETS = [
  { id: 'cityDusk',       prompt: 'cinematic city skyline at dusk, golden hour, ultra-wide, dramatic clouds, photorealistic, 8k --ar 16:9' },
  { id: 'minimalProduct', prompt: 'minimalist product photograph on white seamless background, soft three-point studio lighting, sharp focus, commercial e-commerce style --ar 1:1' },
  { id: 'forestFog',      prompt: 'ethereal forest with morning fog and god rays streaming through tall pine trees, soft volumetric light, photorealistic landscape --ar 16:9' },
  { id: 'cyberpunkStreet',prompt: 'futuristic neon-lit street, rainy night, cyberpunk style, reflective puddles, blade-runner inspired color palette --ar 16:9' },
  { id: 'abstractMetal',  prompt: 'abstract liquid metal sculpture, chrome surface with subtle iridescence, studio lighting, soft shadows, gallery exhibition --ar 1:1' },
  { id: 'minimalKitchen', prompt: 'Japanese minimalist kitchen interior, warm afternoon light, natural wood and white plaster, calm atmosphere, architectural photography --ar 16:9' },
  { id: 'fashionPortrait',prompt: 'editorial fashion portrait, dramatic Rembrandt lighting, neutral linen backdrop, sharp focus on face, high-end magazine quality --ar 3:4' },
  { id: 'foodHero',       prompt: 'hero shot of a steaming ceramic bowl of ramen on dark wood table, overhead 45-degree angle, moody warm lighting, professional food photography --ar 1:1' },
]
const selectedPresetId = ref('')
function applyPreset() {
  const preset = PROMPT_PRESETS.find(p => p.id === selectedPresetId.value)
  if (preset) prompt.value = preset.prompt
}

async function handleGenerate() {
  if (!prompt.value.trim()) {
    uiStore.showWarning(t('midjourney.warnings.emptyPrompt'))
    return
  }
  isProcessing.value = true
  resultImage.value = undefined
  try {
    const result = await toolsApi.midjourneyImagine({
      prompt: prompt.value,
      aspectRatio: aspectRatio.value,
      processMode: processMode.value,
    })
    if (result.success && (result.image_url || result.result_url)) {
      resultImage.value = result.image_url || result.result_url
      if (!isDemoUser.value) {
        creditsStore.fetchBalance()
        uiStore.showSuccess(t('midjourney.toasts.success'))
      } else {
        uiStore.showSuccess(t('midjourney.toasts.demoReady'))
      }
    } else {
      uiStore.showError(result.message || t('midjourney.errors.generic'))
    }
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.message || t('midjourney.errors.generic')
    uiStore.showError(detail)
  } finally {
    isProcessing.value = false
  }
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b;">
    <div class="max-w-5xl mx-auto px-4">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold mb-2" style="color: #f5f5fa;">{{ t('midjourney.title') }}</h1>
        <p style="color: #9494b0;">{{ t('midjourney.subtitle') }}</p>
        <!-- Backend tools.py CREDIT_COST = 50; ServicePricing override (admin
             can dial via /admin/models) takes effect on deduction even if
             the displayed value here stays at the hardcoded baseline. -->
        <CreditCost :cost="50" class="mt-2" />
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ t('midjourney.demoCta') }}
          </RouterLink>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="space-y-4">
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('midjourney.presetLabel') }}</label>
            <select
              v-model="selectedPresetId"
              @change="applyPreset"
              class="w-full px-3 py-2 rounded-lg text-sm mb-3"
              style="background: #0d0d15; color: #e8e8f0; border: 1px solid rgba(255,255,255,0.1);"
            >
              <option value="">{{ t('midjourney.presetCustom') }}</option>
              <option v-for="p in PROMPT_PRESETS" :key="p.id" :value="p.id">
                {{ t(`midjourney.presets.${p.id}`) }}
              </option>
            </select>

            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('midjourney.promptLabel') }}</label>
            <textarea
              v-model="prompt"
              rows="4"
              :placeholder="t('midjourney.promptPlaceholder')"
              class="w-full px-3 py-2 rounded-lg text-sm"
              style="background: #0d0d15; color: #e8e8f0; border: 1px solid rgba(255,255,255,0.1);"
              maxlength="2000"
            />
          </div>

          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('midjourney.aspectRatio') }}</label>
            <div class="grid grid-cols-5 gap-2">
              <button
                v-for="ar in ['1:1', '16:9', '9:16', '4:3', '3:4'] as const"
                :key="ar"
                @click="aspectRatio = ar"
                class="py-2 rounded-lg text-xs font-medium transition-all"
                :style="aspectRatio === ar ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >{{ ar }}</button>
            </div>
          </div>

          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('midjourney.processMode') }}</label>
            <div class="grid grid-cols-3 gap-2">
              <button
                v-for="pm in ['relax', 'fast', 'turbo'] as const"
                :key="pm"
                @click="processMode = pm"
                class="py-2 rounded-lg text-xs font-medium transition-all"
                :style="processMode === pm ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >{{ t(`midjourney.processModes.${pm}`) }}</button>
            </div>
          </div>

          <button
            @click="handleGenerate"
            :disabled="isProcessing || !prompt.trim()"
            class="w-full py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-50"
            style="background: #1677ff;"
          >
            {{ isProcessing ? t('midjourney.processing') : t('midjourney.action') }}
          </button>
        </div>

        <div class="rounded-xl p-4 flex items-center justify-center min-h-[400px]" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <LoadingOverlay :show="isProcessing" :message="t('midjourney.loading')" />
          <div v-if="!isProcessing && resultImage" class="w-full">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('midjourney.resultLabel') }}</label>
            <img :src="resultImage" class="w-full rounded-lg" style="max-height: 500px; object-fit: contain;" />
            <a
              v-if="!isDemoUser"
              :href="resultImage"
              target="_blank"
              download
              class="block mt-3 text-center py-2 rounded-lg text-sm font-medium transition-colors"
              style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
            >{{ t('midjourney.download') }}</a>
          </div>
          <div v-if="!isProcessing && !resultImage" class="text-center" style="color: #6b6b8a;">
            <p class="text-sm">{{ t('midjourney.placeholder') }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
