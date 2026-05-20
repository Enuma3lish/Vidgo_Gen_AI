<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { usePromptLibrary } from '@/composables/usePromptLibrary'
import { toolsApi } from '@/api'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import { downloadAsset } from '@/utils/downloadAsset'

const { t, locale } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { isDemoUser } = useDemoMode()
const { L } = useLocalized()

const prompt = ref('')
const aspectRatio = ref<'1:1' | '16:9' | '9:16' | '4:3' | '3:4'>('1:1')
const processMode = ref<'relax' | 'fast' | 'turbo'>('fast')
const resultImage = ref<string | undefined>(undefined)
const isProcessing = ref(false)

// 2026-05-20 revision — three-tier T2I picker, all verified against
// PiAPI's live /api/v1/task catalog (probed and confirmed working):
//   flux     Qubico/flux1-schnell  ($0.025/img)  premium / balanced default
//   qwen     Qubico/qwen-image     ($0.015/img)  Alibaba — best Chinese prompts
//   z-image  Qubico/z-image        ($0.004/img)  Alibaba — cheap & fast
// Prior Hunyuan/Seedance options were removed because those models are
// VIDEO-only on PiAPI — they returned unrelated default-model output.
const selectedT2IModel = ref<'flux' | 'qwen' | 'z-image'>('flux')
const t2iModelOptions = [
  { id: 'flux' as const,    nameZh: 'Flux',          nameEn: 'Flux',          descZh: '高品質均衡 · 通用首選', descEn: 'Premium · balanced default' },
  { id: 'qwen' as const,    nameZh: 'Qwen Image',    nameEn: 'Qwen Image',    descZh: '中文 prompt 最強 · 阿里通義', descEn: 'Best for Chinese prompts · Alibaba' },
  { id: 'z-image' as const, nameZh: 'Z-Image Turbo', nameEn: 'Z-Image Turbo', descZh: '省錢快速 · 適合大量草稿',   descEn: 'Cheap & fast · great for drafts' },
]

// Use the curated 40-prompt `premium_image` library (pi_*) — same source
// of truth as every other flagship tool. The previous 8-item hardcoded
// preset list was too small for users to browse meaningful variety.
const { options: presetOptions, promptFor: presetPromptFor } = usePromptLibrary('premium_image')

const selectedPresetId = ref('')
function applyPreset() {
  if (!selectedPresetId.value) return
  prompt.value = presetPromptFor(selectedPresetId.value)
  // Clear any stale result from a previous generation. Without this, the
  // result panel kept showing the *old* image after the user switched to a
  // new preset, which read as "the result doesn't match the prompt I just
  // picked" — see user report 2026-05-18 (Iceland aurora preset shown next
  // to a Chinese-mountain image from an earlier generation).
  resultImage.value = undefined
}
// Re-resolve prompt text when locale flips (zh ↔ en variant per library).
watch(locale, () => {
  if (selectedPresetId.value) prompt.value = presetPromptFor(selectedPresetId.value)
})

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
      // Flux is the documented default on the backend — only forward
      // an explicit model when the user picked something else, so the
      // existing schema stays backward-compatible for old clients.
      ...(selectedT2IModel.value !== 'flux' ? { model: selectedT2IModel.value } : {}),
    })
    if (result.success && (result.image_url || result.result_url)) {
      resultImage.value = result.image_url || result.result_url
      // Backend short-circuits non-subscribers (incl. logged-out users) to a
      // static pre-rendered demo PNG (_PREMIUM_DEMO_FALLBACKS in tools.py).
      // The prompt is NOT actually run against Flux in that case. Tell the
      // user honestly that the image they're seeing is a placeholder AND
      // overwrite the displayed prompt with the demo's actual prompt — the
      // user's picked prompt has not been generated, so leaving it on-screen
      // alongside a city-skyline placeholder reads as "result is wrong."
      if (result.is_demo || result.cached) {
        if ((result as any).demo_prompt) {
          prompt.value = (result as any).demo_prompt
          selectedPresetId.value = ''
        }
        uiStore.showWarning(
          result.message ||
          t('midjourney.toasts.demoPlaceholder', '此為示範圖（非依您提示詞生成）— 登入並訂閱後即可用您的提示詞實際生成。'),
        )
      } else if (!isDemoUser.value) {
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
          <!-- Curated prompt picker — locked, no free-form input. The
               premium_image library carries 40 hand-validated prompts.
               Same enforcement pattern as /tools/pattern-generate and
               /tools/kling-video. -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('midjourney.presetLabel') }}</label>
            <div class="mb-2 p-2 rounded-lg" style="background: rgba(245,158,11,0.08); border: 1px solid rgba(245,158,11,0.18);">
              <p class="text-[11px]" style="color: #fbbf24;">
                {{ t('common.curatedNotice') }}
              </p>
            </div>
            <select
              v-model="selectedPresetId"
              @change="applyPreset"
              size="8"
              class="w-full px-3 py-2 rounded-lg text-sm mb-3"
              style="background: #0d0d15; color: #e8e8f0; border: 1px solid rgba(255,255,255,0.1);"
            >
              <option v-for="opt in presetOptions" :key="opt.id" :value="opt.id">
                {{ opt.label }}
              </option>
            </select>

            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('midjourney.promptLabel') }}</label>
            <div
              class="w-full px-3 py-2 rounded-lg text-xs whitespace-pre-wrap"
              style="background: #0d0d15; color: #b4b4cf; border: 1px solid rgba(255,255,255,0.08); min-height: 80px;"
            >
              {{ prompt || t('common.curatedPickToPreview') }}
            </div>
          </div>

          <!-- AI model picker (2026-05-20 tier addition). -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">
              {{ L('AI 模型', 'AI Model', 'AIモデル', 'AI 모델', 'Modelo IA') }}
            </label>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <button
                v-for="m in t2iModelOptions"
                :key="m.id"
                @click="selectedT2IModel = m.id; resultImage = undefined"
                class="text-left p-3 rounded-lg transition-all"
                :style="selectedT2IModel === m.id
                  ? 'background: #1677ff; color: white; border: 1px solid #1677ff;'
                  : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >
                <div class="text-sm font-semibold">{{ L(m.nameZh, m.nameEn, m.nameEn, m.nameEn, m.nameEn) }}</div>
                <div class="text-[11px] opacity-80 mt-1">{{ L(m.descZh, m.descEn, m.descEn, m.descEn, m.descEn) }}</div>
              </button>
            </div>
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
            <button
              v-if="!isDemoUser"
              @click="downloadAsset(resultImage, 'vidgo_premium_image.png')"
              class="block w-full mt-3 text-center py-2 rounded-lg text-sm font-medium transition-colors"
              style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
            >{{ t('midjourney.download') }}</button>
          </div>
          <div v-if="!isProcessing && !resultImage" class="text-center" style="color: #6b6b8a;">
            <p class="text-sm">{{ t('midjourney.placeholder') }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
