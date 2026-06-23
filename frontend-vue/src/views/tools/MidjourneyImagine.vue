<script setup lang="ts">
/**
 * MidjourneyImagine — PiAPI-style playground (Deploy 4, 2026-05-24).
 *
 * Premium T2I tier. Backend (/api/v1/tools/midjourney-imagine) routes
 * the user's model dropdown choice via params.model:
 *   flux (default) · qwen · z-image · nano-banana · nano-banana-pro · seedream
 *
 * (Midjourney itself was permanently dropped by PiAPI in May 2026 — the
 * endpoint name is kept for backward URL compatibility but Flux is the
 * actual primary route.)
 */
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { usePromptLibrary } from '@/composables/usePromptLibrary'
import { toolsApi } from '@/api'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import { downloadAsset } from '@/utils/downloadAsset'
import { extractApiError } from '@/utils/apiError'
import { handleCardRequired } from '@/utils/toolGate'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const { isDemoUser } = useDemoMode()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

type ModelId = 'flux' | 'qwen' | 'z-image' | 'nano-banana' | 'nano-banana-pro' | 'seedream'
// All Midjourney/T2I models flow through the backend's
// `image_generation_premium` ServicePricing row, which is a flat 5 credits
// regardless of which model the user picks (z-image, flux, qwen, nano-banana,
// seedream, nano-banana-pro all priced the same on our side). Frontend
// previously displayed per-model costs (1/5/8/15) — those were aspirational
// per-model pricing that never landed in the backend, causing the UI to
// show 15 credits while the user only got charged 5. Aligning to actual.
// TODO: if/when ops adds per-model service_pricing rows, restore the cost
// field here and dispatch by model_id in the backend cost-resolution chain.
const modelOptions: Array<{ id: ModelId; nameZh: string; nameEn: string; tag?: string; cost: number }> = [
  // VidGo 3.0 扣點表 — standard models (Flux/Z-Image/Qwen/Seedream) = 2,
  // Gemini / nano-banana 1K = 8. Mirrors resolve_image_credits() in tools.py.
  { id: 'flux',             nameZh: 'Flux Schnell（預設）',        nameEn: 'Flux Schnell (default)', cost: 2 },
  { id: 'z-image',          nameZh: 'Z-Image Turbo（最便宜）',     nameEn: 'Z-Image Turbo (cheapest)', cost: 2 },
  { id: 'qwen',             nameZh: 'Qwen Image（中文擅長）',       nameEn: 'Qwen Image (Chinese-friendly)', tag: 'pro', cost: 2 },
  { id: 'nano-banana',      nameZh: 'Nano Banana 2（Gemini 1K）',  nameEn: 'Nano Banana 2 (Gemini 1K)', tag: 'pro', cost: 8 },
  { id: 'seedream',         nameZh: 'Seedream 5 Lite',             nameEn: 'Seedream 5 Lite', tag: 'pro', cost: 2 },
  { id: 'nano-banana-pro',  nameZh: 'Nano Banana Pro（最高品質）', nameEn: 'Nano Banana Pro (highest quality)', tag: 'premium', cost: 8 },
]

const modelId = ref<ModelId>('flux')
const prompt = ref('')
const aspectRatio = ref<'1:1' | '16:9' | '9:16' | '4:3' | '3:4' | '3:2' | '2:3'>('1:1')

// Curated dropdown presets (premium_image). Free visitors who pick an
// unmodified preset get the pregenerated cached demo (top-model Nano Banana
// Pro); subscribers send the same verbatim prompt for a real generation.
const { options: presetOptions, promptFor: presetPromptFor } = usePromptLibrary('premium_image')
const selectedPresetId = ref('')
function applyPreset() {
  if (!selectedPresetId.value) return
  prompt.value = presetPromptFor(selectedPresetId.value)
}
// Editing the prompt away from the preset text de-selects it (so it counts as a
// custom prompt → subscribe wall, matching the backend gate).
watch(prompt, (val) => {
  if (selectedPresetId.value && val.trim() !== presetPromptFor(selectedPresetId.value).trim()) {
    selectedPresetId.value = ''
  }
})
const usingPreset = computed(() =>
  !!selectedPresetId.value && prompt.value.trim() === presetPromptFor(selectedPresetId.value).trim()
)

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

const disabled = computed(() => !prompt.value.trim())
// Free visitors may run an unmodified preset (cached demo); a custom prompt
// needs a subscription. So a demo user is only "ready" once a preset is picked.
const generateDisabled = computed(() =>
  isDemoUser.value ? !usingPreset.value : disabled.value
)
const currentModel = computed(() => modelOptions.find(m => m.id === modelId.value) || modelOptions[0])
const creditCost = computed(() => currentModel.value.cost)

async function generate() {
  if (status.value === 'running') return
  if (isDemoUser.value && !usingPreset.value) {
    uiStore.showInfo(L(
      '選擇一個範例提示詞即可免費試用，或訂閱以使用自訂提示詞',
      'Pick a preset to try it free, or subscribe to use a custom prompt',
      'プリセットを選んで無料体験、またはサブスク登録',
      '프리셋을 선택해 무료 체험하거나 구독하세요',
      'Elige un preajuste para probar gratis o suscríbete',
    ))
    return
  }
  if (disabled.value) return
  status.value = 'running'
  statusText.value = isZh.value ? '生成中…' : 'Generating…'
  resultUrl.value = null
  try {
    const result = await toolsApi.midjourneyImagine({
      prompt: prompt.value.trim(),
      aspectRatio: aspectRatio.value,
      model: modelId.value,
      // When an unmodified preset is selected, send its id so free visitors get
      // the cached demo and the backend uses the canonical prompt text.
      promptId: usingPreset.value ? selectedPresetId.value : undefined,
      locale: String(locale.value || ''),
    })
    if (handleCardRequired(result, uiStore, router, isZh.value)) {
      status.value = 'idle'
      return
    }
    if (result.success && (result.image_url || result.result_url)) {
      resultUrl.value = result.image_url || result.result_url || null
      status.value = 'done'
      statusText.value = isZh.value ? '完成' : 'Done'
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      uiStore.showError((result as any).message || (result as any).error || (isZh.value ? '生成失敗' : 'Failed'))
    }
  } catch (e: any) {
    status.value = 'error'
    uiStore.showError(extractApiError(e, isZh.value ? '生成失敗' : 'Failed'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="60"
    :title="isZh ? 'AI 圖片生成（旗艦）' : 'Premium AI Image Generation'"
    :subtitle="isZh
      ? '6 種模型可選，從便宜的 Z-Image Turbo 到最高品質的 Nano Banana Pro。文字描述即生成。'
      : '6 models from cheap Z-Image Turbo to top-quality Nano Banana Pro. Text-to-image, prompt verbatim.'"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="isZh ? '生成圖片' : 'Generate'"
    :generate-label-running="isZh ? '生成中…' : 'Generating…'"
    :disabled="generateDisabled"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ isZh ? '模型 *' : 'Model *' }}</label>
        <select v-model="modelId" class="pp-select">
          <option v-for="m in modelOptions" :key="m.id" :value="m.id">
            {{ (isZh ? m.nameZh : m.nameEn) }} · {{ m.cost }}{{ isZh ? ' 點' : ' credits' }}{{ m.tag ? ` · ${m.tag}` : '' }}
          </option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '任務類型 *' : 'Task Type *' }}</label>
        <select class="pp-select" disabled>
          <option>txt2img</option>
        </select>
      </div>

      <div v-if="presetOptions.length > 0">
        <label class="pp-field-label">{{ isZh ? '範例提示詞（免費試用）' : 'Example prompt (free to try)' }}</label>
        <select v-model="selectedPresetId" @change="applyPreset" class="pp-select">
          <option value="">{{ isZh ? '— 自訂提示詞 —' : '— Custom prompt —' }}</option>
          <option v-for="opt in presetOptions" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '提示詞 *' : 'Prompt *' }}</label>
        <textarea v-model="prompt" rows="5" maxlength="2000" class="pp-textarea"
          :placeholder="isZh ? '描述你想要的圖片…' : 'Describe the image you want…'"></textarea>
        <p class="pp-field-help">{{ isZh ? '提示會原封不動傳給模型。' : 'Your prompt reaches the model verbatim.' }}</p>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '比例' : 'Aspect Ratio' }}</label>
        <select v-model="aspectRatio" class="pp-select">
          <option value="1:1">1:1 (square)</option>
          <option value="16:9">16:9 (landscape)</option>
          <option value="9:16">9:16 (portrait)</option>
          <option value="4:3">4:3</option>
          <option value="3:4">3:4</option>
          <option value="3:2">3:2</option>
          <option value="2:3">2:3</option>
        </select>
      </div>


      <p v-if="isDemoUser" class="pp-field-help" style="color: #fbbf24;">
        {{ isZh
          ? '選擇上方範例提示詞即可免費預覽；自訂提示詞需訂閱。'
          : 'Pick an example prompt above to preview free; custom prompts need a subscription.' }}
        <button @click="gotoPricing" class="underline ml-1">{{ isZh ? '查看方案' : 'View Plans' }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <img :src="resultUrl" alt="Result" class="max-w-full max-h-[520px] object-contain rounded-lg" />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_t2i_${modelId}_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ isZh ? '下載' : 'Download' }}</button>
      <button @click="generate" class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >🔄 {{ isZh ? '重新生成' : 'Regenerate' }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="midjourney-imagine" />
    </template>
  </PiapiPlayground>
</template>
