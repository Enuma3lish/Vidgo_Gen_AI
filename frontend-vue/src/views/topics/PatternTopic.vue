<script setup lang="ts">
/**
 * PatternTopic / Pattern Generate — PiAPI-style playground (Deploy 4).
 *
 * Backed by /api/v1/generate/pattern/generate (PatternGenerateRequest).
 * Style picker + curated-prompt dropdown + free-form prompt + product_name
 * (QA #6 added 2026-05-24). User text reaches Flux/Qwen/Z-Image verbatim.
 */
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, usePromptLibrary, useExamplePrefill } from '@/composables'
import { generationApi } from '@/api/generation'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import { downloadAsset } from '@/utils/downloadAsset'
import { handleCardRequired } from '@/utils/toolGate'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { isDemoUser } = useDemoMode()
const { options: patternPromptOptions, promptFor: patternPromptTextFor } = usePromptLibrary('pattern_generate')
const isZh = computed(() => locale.value.startsWith('zh'))

type ModelId = 'flux' | 'qwen' | 'z-image'
// Displayed credit cost comes ENTIRELY from the backend ServicePricing API
// (GET /credits/pricing) — never hardcoded here — so the picker can never
// drift from the actual deduction (P0-1). Flux schnell / Z-Image / Qwen all
// resolve to the backend "standard" image tier (resolve_image_credits →
// service_type=text_to_image); kept as a fn so a future premium model can map
// to its own service_type. The numeric 2 is only a pre-fetch fallback.
const modelOptions: Array<{ id: ModelId; nameZh: string; nameEn: string }> = [
  { id: 'flux',    nameZh: 'Flux Schnell（預設）',    nameEn: 'Flux Schnell (default)' },
  { id: 'z-image', nameZh: 'Z-Image Turbo（最便宜）', nameEn: 'Z-Image Turbo (cheapest)' },
  { id: 'qwen',    nameZh: 'Qwen Image（中文擅長）',   nameEn: 'Qwen Image (zh-friendly)' },
]
const modelId = ref<ModelId>('flux')
function serviceTypeFor(_id: ModelId): string { return 'text_to_image' }
function costFor(id: ModelId): number { return creditsStore.getServiceCost(serviceTypeFor(id), 2) }
onMounted(() => { creditsStore.ensurePricing() })

const styleOptions = [
  { id: 'seamless',     labelZh: '無縫拼接',       labelEn: 'Seamless' },
  { id: 'floral',       labelZh: '花卉植物',       labelEn: 'Floral' },
  { id: 'geometric',    labelZh: '幾何抽象',       labelEn: 'Geometric' },
  { id: 'abstract',     labelZh: '抽象藝術',       labelEn: 'Abstract' },
  { id: 'traditional',  labelZh: '傳統文化',       labelEn: 'Traditional' },
  { id: '3d',           labelZh: '3D 浮雕',         labelEn: '3D Embossed' },
  { id: 'interior',     labelZh: '居家壁紙',       labelEn: 'Interior / Wallpaper' },
  { id: 'mockup',       labelZh: '產品包裝',       labelEn: 'Packaging Mockup' },
]
const style = ref<string>('seamless')

const selectedPromptId = ref('')
const prompt = ref('')
const productName = ref('')
const aspectRatio = ref<'1:1' | '16:9' | '9:16' | '4:3' | '3:4'>('1:1')

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

const disabled = computed(() => !prompt.value.trim())
const creditCost = computed(() => costFor(modelId.value))

watch([selectedPromptId, locale], () => {
  if (selectedPromptId.value) prompt.value = patternPromptTextFor(selectedPromptId.value)
})
// Editing away from the chosen preset clears the preset id, so the backend
// sees a CUSTOM prompt (subscription + bound card required) instead of a
// free example.
watch(prompt, (val) => {
  if (selectedPromptId.value && val.trim() !== patternPromptTextFor(selectedPromptId.value).trim()) {
    selectedPromptId.value = ''
  }
})

// Gallery deeplink → fill the prompt textarea. Pattern generate is T2I so
// no image is consumed; example image is ignored.
useExamplePrefill({
  onPrompt: (p) => { prompt.value = p },
})

function sizeForRatio(ratio: string): { width: number; height: number } {
  switch (ratio) {
    case '16:9': return { width: 1280, height: 720 }
    case '9:16': return { width: 720, height: 1280 }
    case '4:3':  return { width: 1152, height: 896 }
    case '3:4':  return { width: 896, height: 1152 }
    default:     return { width: 1024, height: 1024 }
  }
}

async function generate() {
  if (disabled.value || status.value === 'running') return
  // Backend governs access: a free account gets the cached example for an
  // unmodified preset; a custom prompt returns 'subscription_card_required',
  // handled below.
  status.value = 'running'
  statusText.value = isZh.value ? '生成中…' : 'Generating…'
  resultUrl.value = null
  try {
    const { width, height } = sizeForRatio(aspectRatio.value)
    const response = await generationApi.generatePattern({
      prompt: prompt.value.trim(),
      prompt_id: selectedPromptId.value || undefined,
      locale: String(locale.value || ''),
      style: style.value,
      width,
      height,
      ...(modelId.value !== 'flux' ? { model: modelId.value } : {}),
      ...(productName.value.trim() ? { product_name: productName.value.trim() } : {}),
    })
    if (handleCardRequired(response, uiStore, router, isZh.value)) {
      status.value = 'idle'
      return
    }
    if (response.success && response.result_url) {
      resultUrl.value = response.result_url
      status.value = 'done'
      statusText.value = isZh.value ? '完成' : 'Done'
      if ((response as any).credits_used) creditsStore.deductCredits((response as any).credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      uiStore.showError((response as any).message || (response as any).error || (isZh.value ? '生成失敗' : 'Failed'))
    }
  } catch (e: any) {
    status.value = 'error'
    uiStore.showError(e?.response?.data?.detail || e?.message || (isZh.value ? '生成失敗' : 'Failed'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="40"
    :title="isZh ? '花紋 / 圖案設計' : 'Pattern Design Generator'"
    :subtitle="isZh
      ? '為包裝、布料、磁磚、桌布等產品生成無縫拼接圖案。填寫產品名稱可讓 AI 針對該產品優化材質與留白。'
      : 'Generate seamless patterns for packaging, fabric, tiles, wallpaper, and more. Fill in the product name and AI tunes material / margins for that target.'"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="isZh ? '生成圖案' : 'Generate'"
    :generate-label-running="isZh ? '生成中…' : 'Generating…'"
    :disabled="disabled"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ isZh ? '模型 *' : 'Model *' }}</label>
        <select v-model="modelId" class="pp-select">
          <option v-for="m in modelOptions" :key="m.id" :value="m.id">
            {{ (isZh ? m.nameZh : m.nameEn) }} · {{ costFor(m.id) }}
          </option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '任務類型 *' : 'Task Type *' }}</label>
        <select class="pp-select" disabled>
          <option>txt2img · pattern</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '風格 *' : 'Style *' }}</label>
        <select v-model="style" class="pp-select">
          <option v-for="s in styleOptions" :key="s.id" :value="s.id">
            {{ isZh ? s.labelZh : s.labelEn }}
          </option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '產品名稱（選填）' : 'Product Name (optional)' }}</label>
        <input v-model="productName" type="text" maxlength="120" class="pp-input"
          :placeholder="isZh ? '例：咖啡袋、絲巾、磁磚、抱枕' : 'e.g. coffee bag, silk scarf, tile, throw pillow'" />
        <p class="pp-field-help">{{ isZh ? '填寫後，AI 會為此產品設計合適的圖案。' : 'When filled, AI tailors the pattern to that product.' }}</p>
      </div>

      <div v-if="patternPromptOptions.length > 0">
        <label class="pp-field-label">{{ isZh ? '精選提示詞（選填）' : 'Curated Prompts (optional)' }}</label>
        <select v-model="selectedPromptId" class="pp-select">
          <option value="">{{ isZh ? '— 自行輸入 —' : '— Write my own —' }}</option>
          <option v-for="opt in patternPromptOptions" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '提示詞 *' : 'Prompt *' }}</label>
        <textarea v-model="prompt" rows="4" class="pp-textarea"
          :placeholder="isZh ? '描述圖案的內容、顏色、風格…' : 'Describe the pattern subject, colors, style…'"></textarea>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '比例' : 'Aspect Ratio' }}</label>
        <select v-model="aspectRatio" class="pp-select">
          <option value="1:1">1:1 (square)</option>
          <option value="16:9">16:9 (landscape)</option>
          <option value="9:16">9:16 (portrait)</option>
          <option value="4:3">4:3</option>
          <option value="3:4">3:4</option>
        </select>
      </div>

      <p v-if="isDemoUser" class="pp-field-help" style="color: #fbbf24;">
        {{ isZh
          ? '免費帳號可用範例下拉選單一鍵生成；自訂提示詞需訂閱並綁定信用卡。'
          : 'Free accounts can generate from the example presets; custom prompts require a subscription with a bound card.' }}
        <button @click="gotoPricing" class="underline ml-1">{{ isZh ? '查看方案' : 'View Plans' }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <img :src="resultUrl" alt="Pattern" class="max-w-full max-h-[520px] object-contain rounded-lg" />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_pattern_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ isZh ? '下載' : 'Download' }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="pattern-generate" />
    </template>
  </PiapiPlayground>
</template>
