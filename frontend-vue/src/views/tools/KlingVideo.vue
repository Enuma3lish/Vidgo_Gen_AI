<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { usePromptLibrary } from '@/composables/usePromptLibrary'
import { toolsApi } from '@/api'
import ImageUploader from '@/components/common/ImageUploader.vue'
import CreditCost from '@/components/tools/CreditCost.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import { downloadAsset } from '@/utils/downloadAsset'
import { extractApiError } from '@/utils/apiError'
import { handleCardRequired } from '@/utils/toolGate'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { isDemoUser } = useDemoMode()
const { L } = useLocalized()

const prompt = ref('')
// 2026-05-20: added "omni" tier (Kling 3.0 multimodal with audio + lip-sync).
// Backend KlingVideoRequest accepts the same three values; mode selection
// inside kling_video_generation routes "omni" to PiAPI's omni mode.
const tier = ref<'default' | 'flagship' | 'omni'>('default')
const duration = ref<5 | 10>(5)
const aspectRatio = ref<'16:9' | '9:16' | '1:1'>('16:9')
const startImage = ref<string | undefined>(undefined)
const tailImage = ref<string | undefined>(undefined)
const negativePrompt = ref('')
const resultVideo = ref<string | undefined>(undefined)
const isProcessing = ref(false)

// Wire to the curated 40-prompt `kling_video` library (kv_*) — same
// source of truth all flagship tools share. The previous hardcoded
// 8-item list was visibly too small in the dropdown.
const { options: presetOptions, promptFor: presetPromptFor } = usePromptLibrary('kling_video')

const selectedPresetId = ref('')
function applyPreset() {
  if (!selectedPresetId.value) return
  prompt.value = presetPromptFor(selectedPresetId.value)
  // Clear stale video from a previous generation so the result panel
  // doesn't read as "this video doesn't match the prompt I just picked."
  // Matches the fix applied to MidjourneyImagine for the same UX class.
  resultVideo.value = undefined
}
watch(locale, () => {
  if (selectedPresetId.value) prompt.value = presetPromptFor(selectedPresetId.value)
})

// Backend hardcoded fallback per tier (matches seeded ServicePricing).
// Admin overrides via /admin/models still affect the actual deduction
// regardless of what's displayed here.
// VidGo 3.0 扣點表 — mirror resolve_video_credits(tier=...) in backend tools.py:
// default → Kling V2.5 STD (28), flagship → Kling V3.0 STD (65),
// omni → Kling V3.0 PRO 含音 (130).
const displayCost = computed(() => {
  if (tier.value === 'omni') return 130
  if (tier.value === 'flagship') return 65
  return 28
})

async function handleGenerate() {
  if (!prompt.value.trim()) {
    uiStore.showWarning(t('klingVideo.warnings.emptyPrompt'))
    return
  }
  isProcessing.value = true
  resultVideo.value = undefined
  try {
    const result = await toolsApi.klingVideo({
      prompt: prompt.value,
      tier: tier.value,
      aspectRatio: startImage.value ? undefined : aspectRatio.value,
      duration: duration.value,
      imageUrl: startImage.value,
      imageTailUrl: tailImage.value,
      negativePrompt: negativePrompt.value || undefined,
    })
    if (handleCardRequired(result, uiStore, router, String(locale.value || '').startsWith('zh'))) {
      return
    }
    if (result.success && (result.video_url || result.result_url)) {
      resultVideo.value = result.video_url || result.result_url
      if (!isDemoUser.value) {
        creditsStore.fetchBalance()
        uiStore.showSuccess(t('klingVideo.toasts.success', { tier: t(`klingVideo.tiers.${tier.value}`) }))
      } else {
        uiStore.showSuccess(t('klingVideo.toasts.demoReady'))
      }
    } else {
      uiStore.showError(result.message || t('klingVideo.errors.generic'))
    }
  } catch (err: any) {
    uiStore.showError(extractApiError(err, t('klingVideo.errors.generic')))
  } finally {
    isProcessing.value = false
  }
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b;">
    <div class="max-w-5xl mx-auto px-4">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold mb-2" style="color: #f5f5fa;">{{ t('klingVideo.title') }}</h1>
        <p style="color: #9494b0;">{{ t('klingVideo.subtitle') }}</p>
        <CreditCost :cost="displayCost" class="mt-2" />
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ t('klingVideo.demoCta') }}
          </RouterLink>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="space-y-4">
          <!-- Tier — three options as of 2026-05-19: default (Kling 2.6, ~100c),
               flagship (Kling 2.1-master pro, ~500c), omni (Kling 3.0 multimodal
               with audio + lip-sync, ~750c). Translation fallbacks via L()
               keep us functional even before the i18n strings ship. -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('klingVideo.tierLabel') }}</label>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <button
                v-for="tk in ['default', 'flagship', 'omni'] as const"
                :key="tk"
                @click="tier = tk; resultVideo = undefined"
                class="py-3 rounded-lg text-sm font-medium transition-all text-left px-3"
                :style="tier === tk ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >
                <div class="font-semibold">
                  <template v-if="tk === 'omni'">{{ L('Kling 3.0 / Omni', 'Kling 3.0 / Omni', 'Kling 3.0 / Omni', 'Kling 3.0 / Omni', 'Kling 3.0 / Omni') }}</template>
                  <template v-else>{{ t(`klingVideo.tiers.${tk}`) }}</template>
                </div>
                <div class="text-xs opacity-75 mt-1">
                  <template v-if="tk === 'omni'">{{ L('多模態 + 音訊與口型同步（約 750 點）', 'Multimodal + audio & lip-sync (~750 credits)', 'マルチモーダル + 音声・リップシンク（約750ポイント）', '멀티모달 + 오디오·립싱크 (약 750 포인트)', 'Multimodal + audio y sincronización labial (~750 créditos)') }}</template>
                  <template v-else>{{ t(`klingVideo.tierHints.${tk}`) }}</template>
                </div>
              </button>
            </div>
          </div>

          <!-- Prompt — free-form editable. The curated library remains as
               an optional dropdown that populates the textarea, but users
               can write or edit anything. Text reaches Kling verbatim. -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">
              {{ t('klingVideo.presetLabel') }} <span style="color: #6b6b8a;">({{ L('選填', 'optional', '任意', '선택', 'opcional') }})</span>
            </label>
            <select
              v-model="selectedPresetId"
              @change="applyPreset"
              class="w-full px-3 py-2 rounded-lg text-sm mb-4"
              style="background: #0d0d15; color: #e8e8f0; border: 1px solid rgba(255,255,255,0.1);"
            >
              <option value="">{{ L('— 自行輸入提示詞 —', '— Write my own prompt —', '— 自分で入力 —', '— 직접 입력 —', '— Escribe el tuyo —') }}</option>
              <option v-for="opt in presetOptions" :key="opt.id" :value="opt.id">
                {{ opt.label }}
              </option>
            </select>

            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('klingVideo.promptLabel') }}</label>
            <textarea
              v-model="prompt"
              rows="5"
              maxlength="2500"
              class="w-full px-3 py-2 rounded-lg text-sm"
              style="background: #0d0d15; color: #e8e8f0; border: 1px solid rgba(255,255,255,0.1); resize: vertical;"
              :placeholder="t('klingVideo.promptPlaceholder')"
            ></textarea>
          </div>

          <!-- Start frame (I2V) -->
          <div v-if="!isDemoUser" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('klingVideo.startImage') }}</label>
            <p class="text-xs mb-2" style="color: #6b6b8a;">{{ t('klingVideo.startImageHint') }}</p>
            <ImageUploader tool-type="kling_video" v-model="startImage" />
          </div>

          <!-- End frame (only if start frame set) -->
          <div v-if="startImage && !isDemoUser" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('klingVideo.endImage') }}</label>
            <p class="text-xs mb-2" style="color: #6b6b8a;">{{ t('klingVideo.endImageHint') }}</p>
            <ImageUploader tool-type="kling_video_tail" v-model="tailImage" />
          </div>

          <!-- Duration -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('klingVideo.duration') }}</label>
            <div class="flex gap-2">
              <button
                v-for="d in [5, 10] as const"
                :key="d"
                @click="duration = d"
                class="flex-1 py-2 rounded-lg text-sm font-medium transition-all"
                :style="duration === d ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >{{ d }}s</button>
            </div>
          </div>

          <!-- Aspect ratio (T2V only) -->
          <div v-if="!startImage" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('klingVideo.aspectRatio') }}</label>
            <div class="grid grid-cols-3 gap-2">
              <button
                v-for="ar in ['16:9', '9:16', '1:1'] as const"
                :key="ar"
                @click="aspectRatio = ar"
                class="py-2 rounded-lg text-xs font-medium transition-all"
                :style="aspectRatio === ar ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >{{ ar }}</button>
            </div>
          </div>

          <button
            @click="handleGenerate"
            :disabled="isProcessing || !prompt.trim()"
            class="w-full py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-50"
            style="background: #1677ff;"
          >
            {{ isProcessing ? t('klingVideo.processing') : t('klingVideo.action') }}
          </button>
        </div>

        <div class="rounded-xl p-4 flex items-center justify-center min-h-[400px]" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <LoadingOverlay :show="isProcessing" :eta-seconds="180" :message="t('klingVideo.loading')" />
          <div v-if="!isProcessing && resultVideo" class="w-full">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('klingVideo.resultLabel') }}</label>
            <video :src="resultVideo" controls class="w-full rounded-lg" style="max-height: 500px;" />
            <button
              v-if="!isDemoUser"
              @click="downloadAsset(resultVideo!, 'vidgo_kling_video.mp4')"
              class="block w-full mt-3 text-center py-2 rounded-lg text-sm font-medium transition-colors"
              style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
            >{{ t('klingVideo.download') }}</button>
          </div>
          <div v-if="!isProcessing && !resultVideo" class="text-center" style="color: #6b6b8a;">
            <p class="text-sm">{{ t('klingVideo.placeholder') }}</p>
          </div>
        </div>
      </div>

      <section class="mt-12">
        <ExampleGallery tool-key="kling-video" />
      </section>
    </div>
  </div>
</template>
