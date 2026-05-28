<script setup lang="ts">
/**
 * TryOn — PiAPI playground refactor (2026-05-24).
 *
 * Layout matches piapi.ai/zh-TW/flux-kontext exactly:
 *   Left column  → Model + Task Type + Prompt + Image + params + Generate
 *   Right column → Status + Result preview + Download/Regenerate
 *   Below        → Examples gallery + FAQ
 *
 * Two task types backed by the same /api/v1/tools/try-on endpoint:
 *   - "Garment Try-On"  → mode=garment (image+image via Kling AI Try-On)
 *   - "Prompt Outfit"   → mode=prompt  (image+text via Flux Kontext I2I)
 *
 * Owner directive: ui colors stay (#0a0a0f bg, violet gradient buttons),
 * only UX shape changes.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { toolsApi } from '@/api'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import { downloadAsset } from '@/utils/downloadAsset'
import { dataURItoBlob } from '@/utils/dataUri'
import { extractApiError } from '@/utils/apiError'

// If the user just uploaded an image via ImageUploader, modelValue is a
// data: URI. Backend cannot fetch a data URI — Kontext / Kling reject it
// outright. Upload to GCS first and swap for the resulting public URL.
async function ensurePublicUrl(value: string | undefined): Promise<string | null> {
  if (!value) return null
  if (!value.startsWith('data:')) return value
  const blob = dataURItoBlob(value)
  if (!blob) return null
  const upload = await toolsApi.uploadImage(blob as File)
  return upload.url
}

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))
const { L } = useLocalized()
const { isDemoUser, loadInputLibrary, inputLibrary } = useDemoMode()

// ─── Models (the "model" picker in piapi.ai style) ────────────────────
type TryOnModelId = 'kling_try_on' | 'flux_kontext'
const modelOptions: Array<{ id: TryOnModelId; nameEn: string; nameZh: string; desc_en: string; desc_zh: string }> = [
  {
    id: 'kling_try_on',
    nameEn: 'Kling AI Try-On',
    nameZh: 'Kling AI 試穿',
    desc_en: 'Image-to-image: drop a garment photo onto a model photo.',
    desc_zh: '圖對圖：把服裝照片穿到模特照片上。',
  },
  {
    id: 'flux_kontext',
    nameEn: 'Flux Kontext (prompt mode)',
    nameZh: 'Flux Kontext（文字描述）',
    desc_en: 'Image-to-image edit: keep the person, describe the outfit in text.',
    desc_zh: '圖像編輯：保留人物，用文字描述新服裝。',
  },
]
const selectedModel = ref<TryOnModelId>('kling_try_on')
function pickModel(id: TryOnModelId) {
  selectedModel.value = id
  resultUrl.value = null
}

// ─── Task type (per-model — locked to one task each for try-on) ───────
const taskTypeOptions = computed(() => {
  return selectedModel.value === 'kling_try_on'
    ? [{ id: 'ai_try_on', label: L('虛擬試衣', 'Virtual Try-On', 'バーチャル試着', '가상 시착', 'Prueba Virtual') }]
    : [{ id: 'kontext_outfit', label: L('Kontext 改服裝', 'Kontext Change Outfit', 'Kontext 服装変更', 'Kontext 의상 변경', 'Kontext Cambio de Atuendo') }]
})
const selectedTaskType = computed(() => taskTypeOptions.value[0]?.id || '')

// ─── Inputs ───────────────────────────────────────────────────────────
const modelImageUrl = ref<string | undefined>(undefined)  // person photo
const garmentImageUrl = ref<string | undefined>(undefined) // clothing photo (Kling only)
const promptText = ref('')                                  // outfit description (Kontext only)
const garmentCategory = ref<'upper_body' | 'lower_body' | 'dress' | 'full_body'>('dress')

// Outfit presets for Kontext mode — Kling 3.0 style instruction prompts.
const outfitPresets = [
  { id: 'business',    label_zh: '高階商務',   label_en: 'Premium Business',  prompt: "Keep the person's identity, pose, and background exactly the same. Change the outfit into a tailored navy blue slim-fit wool suit with crisp white shirt and minimalist silk tie. Realistic fabric texture, natural wrinkles." },
  { id: 'streetwear',  label_zh: '街頭潮流',   label_en: 'Streetwear',        prompt: "Keep the person's identity, pose, and background exactly the same. Change the outfit into an oversized beige graphic hoodie, black cargo pants, retro chunky sneakers." },
  { id: 'couture',     label_zh: '高級高訂',   label_en: 'High Couture',      prompt: "Keep the person's identity, pose, and background exactly the same. Change the outfit into a flowing silk slip dress with delicate lace details." },
  { id: 'evening',     label_zh: '晚禮服',     label_en: 'Evening Gown',      prompt: "Keep the person's identity, pose, and background exactly the same. Change the outfit into a luxurious emerald velvet evening gown with realistic fabric drape." },
  { id: 'summer',      label_zh: '夏日休閒',   label_en: 'Summer Casual',     prompt: "Keep the person's identity, pose, and background exactly the same. Change the outfit into a relaxed linen white shirt and beige chinos." },
  { id: 'athletic',    label_zh: '機能運動',   label_en: 'Athletic',          prompt: "Keep the person's identity, pose, and background exactly the same. Change the outfit into a fitted black performance tee, technical jogger pants, athletic sneakers." },
]
function applyPreset(p: (typeof outfitPresets)[number]) { promptText.value = p.prompt }

// ─── State ────────────────────────────────────────────────────────────
const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

// Disable Generate when required inputs are missing.
const disabled = computed(() => {
  if (selectedModel.value === 'kling_try_on') {
    return !modelImageUrl.value || !garmentImageUrl.value
  }
  return !modelImageUrl.value || !promptText.value.trim()
})

const creditCost = computed(() => 15)

// ─── Generate ─────────────────────────────────────────────────────────
async function generate() {
  if (disabled.value || status.value === 'running') return
  status.value = 'running'
  statusText.value = isZh.value ? '生成中…通常需要 30-60 秒' : 'Generating… typically 30-60s'
  resultUrl.value = null
  try {
    // Promote any local data: URIs to public URLs (Kontext / Kling cannot
    // fetch a data URI). Done concurrently — they're independent uploads.
    const [personUrl, garmentUrl] = await Promise.all([
      ensurePublicUrl(modelImageUrl.value),
      selectedModel.value === 'kling_try_on' ? ensurePublicUrl(garmentImageUrl.value) : Promise.resolve(null),
    ])
    if (!personUrl) {
      status.value = 'error'
      uiStore.showError(isZh.value ? '人物照片上傳失敗' : 'Person photo upload failed')
      return
    }
    if (selectedModel.value === 'kling_try_on' && !garmentUrl) {
      status.value = 'error'
      uiStore.showError(isZh.value ? '服裝照片上傳失敗' : 'Garment photo upload failed')
      return
    }

    const apiPayload: Parameters<typeof toolsApi.tryOn>[1] = {
      modelImageUrl: personUrl,
    }
    let result
    if (selectedModel.value === 'kling_try_on') {
      apiPayload.mode = 'garment'
      apiPayload.category = garmentCategory.value
      result = await toolsApi.tryOn(garmentUrl!, apiPayload)
    } else {
      apiPayload.mode = 'prompt'
      apiPayload.prompt = promptText.value.trim()
      result = await toolsApi.tryOn('', apiPayload)
    }
    if (result.success && (result.image_url || result.result_url)) {
      resultUrl.value = result.image_url || result.result_url || null
      status.value = 'done'
      statusText.value = isZh.value ? '完成' : 'Done'
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success'))
    } else {
      status.value = 'error'
      statusText.value = isZh.value ? '生成失敗' : 'Failed'
      uiStore.showError((result as any).message || (result as any).error || (isZh.value ? '生成失敗，請稍後再試' : 'Generation failed, please retry.'))
    }
  } catch (e: any) {
    status.value = 'error'
    statusText.value = isZh.value ? '錯誤' : 'Error'
    uiStore.showError(extractApiError(e, isZh.value ? '生成失敗' : 'Generation failed'))
  }
}

// ─── Examples (clickable cards) ──────────────────────────────────────
interface ExampleCard { id: string; title_zh: string; title_en: string; image: string; modelHint: TryOnModelId; promptHint?: string }
const examples = ref<ExampleCard[]>([])
onMounted(async () => {
  await loadInputLibrary('try_on')
  examples.value = (inputLibrary.value || [])
    .filter((it: any) => it.result_image_url || it.input_image_url)
    .slice(0, 6)
    .map((it: any, i: number) => ({
      id: it.id || `ex-${i}`,
      title_zh: it.prompt_zh || it.prompt || '示範',
      title_en: it.prompt || it.topic || 'Example',
      image: it.result_image_url || it.input_image_url,
      modelHint: 'kling_try_on',
    }))
})

function applyExample(ex: ExampleCard) {
  selectedModel.value = ex.modelHint
  if (ex.promptHint) promptText.value = ex.promptHint
  uiStore.showInfo(isZh.value ? '已套用範例設定' : 'Example applied — adjust inputs and click Generate.')
}

const subtitle = computed(() => isZh.value
  ? '上傳一張人物照，再選一張服裝或用文字描述新服裝。模型保留人物與姿勢，只改變身上穿的。'
  : 'Upload a person photo, then drop in a garment image OR describe the new outfit in text. The model keeps the person and pose, swapping only the clothing.')

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="60"
    :title="isZh ? 'AI 換裝 / 試衣' : 'AI Try-On'"
    :subtitle="subtitle"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="isZh ? '生成' : 'Generate'"
    :generate-label-running="isZh ? '生成中…' : 'Generating…'"
    :disabled="disabled || isDemoUser"
    @generate="generate"
  >
    <!-- ─── INPUT COLUMN ─── -->
    <template #inputs>
      <!-- Model dropdown (piapi-style 'Model *') -->
      <div>
        <label class="pp-field-label">{{ isZh ? '模型 *' : 'Model *' }}</label>
        <select class="pp-select" :value="selectedModel" @change="(e) => pickModel(((e.target as HTMLSelectElement).value as TryOnModelId))">
          <option v-for="m in modelOptions" :key="m.id" :value="m.id">
            {{ (isZh ? m.nameZh : m.nameEn) }} — {{ (isZh ? m.desc_zh : m.desc_en) }}
          </option>
        </select>
      </div>

      <!-- Task Type dropdown -->
      <div>
        <label class="pp-field-label">{{ isZh ? '任務類型 *' : 'Task Type *' }}</label>
        <select class="pp-select" :value="selectedTaskType" disabled>
          <option v-for="opt in taskTypeOptions" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
        </select>
      </div>

      <!-- Model image upload -->
      <div>
        <label class="pp-field-label">{{ isZh ? '人物照片 *' : 'Person Photo *' }}</label>
        <ImageUploader
          tool-type="try_on_model"
          v-model="modelImageUrl"
          :label="isZh ? '點擊或拖放人物照片' : 'Click or drag a person photo'"
        />
        <p class="pp-field-help mt-1.5">
          {{ isZh
            ? '建議全身直立照，比例約 2:3 或 3:4（手機直拍）。正方形或橫拍會被拒絕。'
            : 'Use a full-body portrait, roughly 2:3 or 3:4 (phone-portrait). Square or landscape photos will be rejected.' }}
        </p>
      </div>

      <!-- Garment image (only for Kling mode) -->
      <div v-if="selectedModel === 'kling_try_on'">
        <label class="pp-field-label">{{ isZh ? '服裝照片 *' : 'Garment Photo *' }}</label>
        <ImageUploader
          tool-type="try_on"
          v-model="garmentImageUrl"
          :label="isZh ? '點擊或拖放服裝照片' : 'Click or drag a garment photo'"
        />
        <div class="mt-2">
          <p class="pp-field-help">{{ isZh ? '服裝類型（決定 Kling 的輸入欄位）' : 'Garment category (drives Kling input slot)' }}</p>
          <div class="grid grid-cols-2 gap-2 mt-1">
            <button
              v-for="opt in [
                { id: 'dress' as const,       label: isZh ? '連身/洋裝' : 'Dress' },
                { id: 'upper_body' as const,  label: isZh ? '上身' : 'Upper' },
                { id: 'lower_body' as const,  label: isZh ? '下身' : 'Lower' },
                { id: 'full_body' as const,   label: isZh ? '整套' : 'Full Body' },
              ]"
              :key="opt.id"
              type="button"
              @click="garmentCategory = opt.id"
              class="text-xs py-2 rounded transition-colors"
              :style="garmentCategory === opt.id
                ? 'background: rgba(124,58,237,0.25); color: #c4b5fd; border: 1px solid rgba(124,58,237,0.4);'
                : 'background: #0a0a0f; color: #94949f; border: 1px solid rgba(255,255,255,0.08);'"
            >{{ opt.label }}</button>
          </div>
        </div>
      </div>

      <!-- Prompt + presets (only for Kontext mode) -->
      <div v-if="selectedModel === 'flux_kontext'">
        <label class="pp-field-label">{{ isZh ? '服裝描述 *' : 'Outfit Prompt *' }}</label>
        <textarea
          v-model="promptText"
          class="pp-textarea"
          rows="4"
          maxlength="2000"
          :placeholder="isZh
            ? '例：保留人物與姿勢，把服裝換成深藍色羊毛西裝，自然布料質感'
            : 'e.g. Keep the person and pose, change the outfit to a tailored navy wool suit, realistic fabric texture'"
        ></textarea>
        <p class="pp-field-help">{{ isZh
          ? '提示：以「保留人物、把服裝換成…」開頭效果最佳。'
          : 'Tip: prompts starting with "Keep the person, change the outfit to…" work best.' }}</p>

        <div class="mt-3">
          <p class="pp-field-label">{{ isZh ? '快速套用' : 'Quick Presets' }}</p>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="p in outfitPresets"
              :key="p.id"
              type="button"
              @click="applyPreset(p)"
              class="text-[11px] px-2 py-1 rounded-full"
              style="background: rgba(124,58,237,0.15); color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
            >{{ isZh ? p.label_zh : p.label_en }}</button>
          </div>
        </div>
      </div>

      <p v-if="isDemoUser" class="pp-field-help" style="color: #fbbf24;">
        {{ isZh ? '訂閱後即可使用此工具生成你的圖片。' : 'Subscribe to generate your own results.' }}
        <button @click="gotoPricing" class="underline ml-1">{{ isZh ? '查看方案' : 'View Plans' }} →</button>
      </p>
    </template>

    <!-- ─── RESULT COLUMN ─── -->
    <template v-if="resultUrl" #result>
      <img :src="resultUrl" alt="Result" class="max-w-full max-h-[520px] object-contain rounded-lg" />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button
        @click="downloadAsset(resultUrl!, `vidgo_tryon_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ isZh ? '下載' : 'Download' }}</button>
      <button
        @click="generate"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >🔄 {{ isZh ? '重新生成' : 'Regenerate' }}</button>
    </template>

    <!-- ─── EXAMPLES ─── -->
    <template v-if="examples.length > 0" #examples-title>
      {{ isZh ? '範例靈感' : 'Example Inspirations' }}
    </template>
    <template v-if="examples.length > 0" #examples>
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        <button
          v-for="ex in examples"
          :key="ex.id"
          @click="applyExample(ex)"
          class="rounded-xl overflow-hidden text-left group"
          style="background: #141420; border: 1px solid rgba(255,255,255,0.06);"
        >
          <div class="aspect-[3/4] overflow-hidden" style="background: #0a0a0f;">
            <img v-if="ex.image" :src="ex.image" :alt="(isZh ? ex.title_zh : ex.title_en)" class="w-full h-full object-cover transition-transform group-hover:scale-105" loading="lazy" />
          </div>
          <p class="text-xs p-2 line-clamp-2" style="color: #f5f5fa;">{{ isZh ? ex.title_zh : ex.title_en }}</p>
        </button>
      </div>
    </template>
  </PiapiPlayground>
</template>
