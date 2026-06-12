<script setup lang="ts">
/**
 * TryOn — PiAPI playground refactor (2026-05-24), UX overhaul 2026-06-12.
 *
 * Layout: PiapiPlayground (left config / right result / examples below).
 *
 * Two modes backed by the same /api/v1/tools/try-on endpoint:
 *   - "garment" → upload a garment photo (Kling AI Try-On, image+image)
 *   - "prompt"  → describe the outfit in text (Flux Kontext I2I)
 * The engine choice is an implementation detail — the UI shows plain-task
 * buttons instead of model-name dropdowns (2026-06-12 owner request:
 * make try-on easier to use).
 *
 * Person photo comes from either:
 *   - a built-in AI model picker (backend TRYON_MODELS presets — one click,
 *     no upload, never rejected by the aspect-ratio validator), or
 *   - the user's own upload (full-body 2:3 / 3:4 portrait).
 *
 * Owner directive: ui colors stay (#0a0a0f bg, violet gradient buttons),
 * only UX shape changes.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized, useExamplePrefill } from '@/composables'
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

// ─── Mode — plain-task buttons, engine is an implementation detail ────
// 'garment' → Kling AI Try-On (image+image); 'prompt' → Flux Kontext I2I.
type TryOnMode = 'garment' | 'prompt'
const mode = ref<TryOnMode>('garment')
function pickMode(m: TryOnMode) {
  mode.value = m
  resultUrl.value = null
}

// ─── Person source — built-in AI models OR the user's own photo ───────
// The backend has always accepted model_id → TRYON_MODELS (11 presets with
// brand-generated photos on GCS), but the UI never exposed them, forcing
// every user to find a strict 2:3 full-body portrait first. The preset grid
// makes the tool one-click usable: pick a model, add a garment, generate.
type PersonSource = 'preset' | 'upload'
const personSource = ref<PersonSource>('preset')
const PRESET_MODEL_BASE = 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models'
interface PresetModel { id: string; nameZh: string; nameEn: string }
// Ids must match backend TRYON_MODELS in app/api/v1/tools.py; display names
// follow the brand-asset catalog (generate_brand_assets.py model_catalog).
const presetModels: PresetModel[] = [
  { id: 'avery',   nameZh: '怡君', nameEn: 'Yi-Jun' },
  { id: 'kendall', nameZh: '曉雨', nameEn: 'Xiao-Yu' },
  { id: 'alex',    nameZh: '佳穎', nameEn: 'Jia-Ying' },
  { id: 'maya',    nameZh: '雅婷', nameEn: 'Ya-Ting' },
  { id: 'lena',    nameZh: '美玲', nameEn: 'Mei-Ling' },
  { id: 'julia',   nameZh: '佩珊', nameEn: 'Pei-Shan' },
  { id: 'sam',     nameZh: '志偉', nameEn: 'Zhi-Wei' },
  { id: 'taylor',  nameZh: '俊豪', nameEn: 'Jun-Hao' },
  { id: 'jordan',  nameZh: '冠宇', nameEn: 'Guan-Yu' },
  { id: 'casey',   nameZh: '宗翰', nameEn: 'Zong-Han' },
  { id: 'reece',   nameZh: '昊然', nameEn: 'Hao-Ran' },
]
// Preselect the first model so the form starts nearly ready — the user only
// adds a garment (or outfit text) and clicks Generate.
const selectedPresetModelId = ref<string>('avery')
const presetThumb = (id: string) => `${PRESET_MODEL_BASE}/${id}.png`

// ─── Inputs ───────────────────────────────────────────────────────────
const modelImageUrl = ref<string | undefined>(undefined)  // person photo (upload source)
const garmentImageUrl = ref<string | undefined>(undefined) // clothing photo (garment mode)
const promptText = ref('')                                  // outfit description (prompt mode)
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
const personReady = computed(() =>
  personSource.value === 'preset' ? !!selectedPresetModelId.value : !!modelImageUrl.value)
const disabled = computed(() => {
  if (!personReady.value) return true
  if (mode.value === 'garment') return !garmentImageUrl.value
  return !promptText.value.trim()
})

// Must mirror the backend deduction (tools.py ai_try_on CREDIT_COST = 30).
// Was displayed as 15 while the backend charged 30 — sticker-shock bug
// fixed 2026-06-12.
const creditCost = computed(() => 30)

// ─── Generate ─────────────────────────────────────────────────────────
async function generate() {
  if (disabled.value || status.value === 'running') return
  status.value = 'running'
  statusText.value = L('生成中…通常需要 30-60 秒', 'Generating… typically 30-60s', '生成中…通常 30〜60 秒かかります', '생성 중… 보통 30-60초 소요', 'Generando… normalmente 30-60 s')
  resultUrl.value = null
  try {
    // Promote any local data: URIs to public URLs (Kontext / Kling cannot
    // fetch a data URI). Done concurrently — they're independent uploads.
    // Preset models skip the person upload entirely: the backend resolves
    // model_id → TRYON_MODELS URL itself.
    const usePreset = personSource.value === 'preset'
    const [personUrl, garmentUrl] = await Promise.all([
      usePreset ? Promise.resolve(null) : ensurePublicUrl(modelImageUrl.value),
      mode.value === 'garment' ? ensurePublicUrl(garmentImageUrl.value) : Promise.resolve(null),
    ])
    if (!usePreset && !personUrl) {
      status.value = 'error'
      uiStore.showError(L('人物照片上傳失敗', 'Person photo upload failed', '人物写真のアップロードに失敗しました', '인물 사진 업로드 실패', 'Error al subir la foto de la persona'))
      return
    }
    if (mode.value === 'garment' && !garmentUrl) {
      status.value = 'error'
      uiStore.showError(L('服裝照片上傳失敗', 'Garment photo upload failed', '衣服の写真のアップロードに失敗しました', '의상 사진 업로드 실패', 'Error al subir la foto de la prenda'))
      return
    }

    const apiPayload: Parameters<typeof toolsApi.tryOn>[1] = usePreset
      ? { modelId: selectedPresetModelId.value }
      : { modelImageUrl: personUrl! }
    let result
    if (mode.value === 'garment') {
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
      statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success'))
    } else {
      status.value = 'error'
      statusText.value = L('生成失敗', 'Failed', '生成失敗', '생성 실패', 'Falló')
      uiStore.showError((result as any).message || (result as any).error || L('生成失敗，請稍後再試', 'Generation failed, please retry.', '生成に失敗しました。再試行してください。', '생성에 실패했습니다. 다시 시도해 주세요.', 'Falló la generación. Inténtalo de nuevo.'))
    }
  } catch (e: any) {
    status.value = 'error'
    statusText.value = L('錯誤', 'Error', 'エラー', '오류', 'Error')
    uiStore.showError(extractApiError(e, L('生成失敗', 'Generation failed', '生成に失敗しました', '생성에 실패했습니다', 'Falló la generación')))
  }
}

// ─── Examples (clickable cards) ──────────────────────────────────────
interface ExampleCard { id: string; title_zh: string; title_en: string; image: string; modeHint: TryOnMode; promptHint?: string }
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
      modeHint: 'garment',
    }))
})

function applyExample(ex: ExampleCard) {
  mode.value = ex.modeHint
  if (ex.promptHint) promptText.value = ex.promptHint
  uiStore.showInfo(isZh.value ? '已套用範例設定' : 'Example applied — adjust inputs and click Generate.')
}

// Gallery "Try this example" deeplink — prefill outfit prompt + person image.
// A prompt-only example switches to prompt mode (person photo + text outfit)
// so the carried prompt is actually consumed.
useExamplePrefill({
  onPrompt: (p) => {
    promptText.value = p
    mode.value = 'prompt'
  },
  onImage: (url) => {
    modelImageUrl.value = url
    personSource.value = 'upload'
  },
  onError: () => uiStore.showError(L(
    '範例素材已過期,請改用其他範例或上傳自有圖片。',
    'This example is no longer available. Pick another or upload your own image.',
    'この例は利用できなくなりました。別の例を選ぶか、画像をアップロードしてください。',
    '이 예제는 더 이상 사용할 수 없습니다. 다른 예제를 선택하거나 이미지를 업로드하세요.',
    'Este ejemplo ya no está disponible. Elige otro o sube tu propia imagen.',
  )),
})

const subtitle = computed(() => isZh.value
  ? '選一位 AI 模特（或上傳自己的照片），再上傳服裝照片或用文字描述新服裝。AI 保留人物與姿勢，只改變身上穿的。'
  : 'Pick a built-in AI model (or upload your own photo), then add a garment photo OR describe the outfit in text. The AI keeps the person and pose, swapping only the clothing.')

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
    :generate-label="L('生成', 'Generate', '生成', '생성', 'Generar')"
    :generate-label-running="L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…')"
    :disabled="disabled || isDemoUser"
    @generate="generate"
  >
    <!-- ─── INPUT COLUMN ─── -->
    <template #inputs>
      <!-- Mode — two plain-task buttons (engine is an implementation detail) -->
      <div>
        <label class="pp-field-label">{{ L('換裝方式 *', 'How do you want to dress them? *', '着せ替え方法 *', '체인지 방식 *', 'Método *') }}</label>
        <div class="grid grid-cols-2 gap-2">
          <button v-for="opt in [
              { id: 'garment' as const, t: L('上傳服裝照片', 'Garment Photo', '服の写真', '의상 사진', 'Foto de prenda'), d: L('把服裝照片穿到模特身上', 'Put a garment photo onto the model', '服の写真をモデルに着せる', '의상 사진을 모델에게 입히기', 'Pone la prenda en la modelo') },
              { id: 'prompt' as const,  t: L('文字描述服裝', 'Describe Outfit', 'テキストで指定', '텍스트로 설명', 'Describir atuendo'), d: L('用一句話描述想要的新服裝', 'Describe the new outfit in a sentence', '欲しい服装を一文で説明', '원하는 의상을 한 문장으로', 'Describe el atuendo en una frase') },
            ]" :key="opt.id" type="button" @click="pickMode(opt.id)"
            class="p-3 rounded-lg text-left transition-colors"
            :style="mode === opt.id
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'
              : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'"
          >
            <div class="text-[13px] font-semibold mb-1">{{ mode === opt.id ? '✓ ' : '' }}{{ opt.t }}</div>
            <div class="text-[11px] leading-snug opacity-80">{{ opt.d }}</div>
          </button>
        </div>
      </div>

      <!-- Person — built-in AI model picker OR own photo upload -->
      <div>
        <label class="pp-field-label">{{ L('模特 *', 'Model *', 'モデル *', '모델 *', 'Modelo *') }}</label>
        <div class="grid grid-cols-2 gap-1.5 mb-2">
          <button v-for="opt in [
              { id: 'preset' as const, label: L('選擇 AI 模特', 'Built-in AI models', 'AIモデルを選ぶ', 'AI 모델 선택', 'Modelos integrados') },
              { id: 'upload' as const, label: L('上傳自己的照片', 'Upload your own', '自分の写真', '직접 업로드', 'Sube la tuya') },
            ]" :key="opt.id" type="button" @click="personSource = opt.id"
            class="py-2 rounded-lg text-xs font-medium transition-colors"
            :style="personSource === opt.id
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'
              : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'"
          >{{ opt.label }}</button>
        </div>

        <!-- Preset model grid: one click, no upload, never rejected -->
        <template v-if="personSource === 'preset'">
          <div class="grid grid-cols-4 gap-2">
            <button
              v-for="m in presetModels"
              :key="m.id"
              type="button"
              @click="selectedPresetModelId = m.id"
              class="rounded-lg overflow-hidden text-center transition-all"
              :style="selectedPresetModelId === m.id
                ? 'border: 2px solid #a78bfa; box-shadow: 0 0 0 2px rgba(124,58,237,0.35);'
                : 'border: 1px solid rgba(255,255,255,0.08);'"
            >
              <div class="aspect-[2/3] overflow-hidden" style="background:#0a0a0f;">
                <img :src="presetThumb(m.id)" :alt="isZh ? m.nameZh : m.nameEn" class="w-full h-full object-cover" loading="lazy" />
              </div>
              <p class="text-[10px] py-1" :style="selectedPresetModelId === m.id ? 'color:#c4b5fd;' : 'color:#94949f;'">
                {{ isZh ? m.nameZh : m.nameEn }}
              </p>
            </button>
          </div>
          <p class="pp-field-help mt-1.5">{{ L('點選一位內建模特即可開始，不需要上傳人物照片。', 'Pick a built-in model and you\'re ready — no person photo needed.', '内蔵モデルを選ぶだけでOK。人物写真は不要です。', '내장 모델을 선택하면 바로 시작 — 인물 사진이 필요 없습니다.', 'Elige un modelo integrado y listo, sin subir fotos.') }}</p>
        </template>

        <!-- Own photo upload -->
        <template v-else>
          <ImageUploader
            tool-type="try_on_model"
            v-model="modelImageUrl"
            :label="L('點擊或拖放人物照片', 'Click or drag a person photo', '人物写真をクリックまたはドラッグ', '인물 사진을 클릭하거나 끌어다 놓기', 'Haz clic o arrastra una foto de la persona')"
          />
          <p class="pp-field-help mt-1.5">
            {{ L(
              '建議全身直立照，比例約 2:3 或 3:4（手機直拍）。正方形或橫拍會被拒絕。',
              'Use a full-body portrait, roughly 2:3 or 3:4 (phone-portrait). Square or landscape photos will be rejected.',
              '全身の縦長ポートレートを推奨（おおむね 2:3 または 3:4 / スマホ縦撮り）。正方形や横向きは弾かれます。',
              '전신 세로 사진을 권장합니다(약 2:3 또는 3:4, 휴대폰 세로 촬영). 정사각형이나 가로 사진은 거부됩니다.',
              'Usa un retrato de cuerpo entero, aprox. 2:3 o 3:4 (vertical). Las fotos cuadradas u horizontales serán rechazadas.',
            ) }}
          </p>
        </template>
      </div>

      <!-- Garment image (garment mode) -->
      <div v-if="mode === 'garment'">
        <label class="pp-field-label">{{ L('服裝照片 *', 'Garment Photo *', '衣服の写真 *', '의상 사진 *', 'Foto de la prenda *') }}</label>
        <ImageUploader
          tool-type="try_on"
          v-model="garmentImageUrl"
          :label="L('點擊或拖放服裝照片', 'Click or drag a garment photo', '衣服の写真をクリックまたはドラッグ', '의상 사진을 클릭하거나 끌어다 놓기', 'Haz clic o arrastra una foto de la prenda')"
        />
        <div class="mt-2">
          <p class="pp-field-help">{{ L('服裝類型（決定 Kling 的輸入欄位）', 'Garment category (drives Kling input slot)', '衣服のカテゴリ（Kling の入力スロットを決定）', '의상 카테고리 (Kling 입력 슬롯 결정)', 'Categoría de prenda (define la entrada de Kling)') }}</p>
          <div class="grid grid-cols-2 gap-2 mt-1">
            <button
              v-for="opt in [
                { id: 'dress' as const,       label: L('連身/洋裝', 'Dress', 'ワンピース', '드레스', 'Vestido') },
                { id: 'upper_body' as const,  label: L('上身', 'Upper', '上半身', '상의', 'Parte superior') },
                { id: 'lower_body' as const,  label: L('下身', 'Lower', '下半身', '하의', 'Parte inferior') },
                { id: 'full_body' as const,   label: L('整套', 'Full Body', '全身', '풀바디', 'Cuerpo entero') },
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

      <!-- Prompt + presets (prompt mode) -->
      <div v-if="mode === 'prompt'">
        <label class="pp-field-label">{{ L('服裝描述 *', 'Outfit Prompt *', '服装の説明 *', '의상 설명 *', 'Prompt del atuendo *') }}</label>
        <textarea
          v-model="promptText"
          class="pp-textarea"
          rows="4"
          maxlength="2000"
          :placeholder="L(
            '例：保留人物與姿勢，把服裝換成深藍色羊毛西裝，自然布料質感',
            'e.g. Keep the person and pose, change the outfit to a tailored navy wool suit, realistic fabric texture',
            '例：人物とポーズは保ち、服装を仕立てたネイビーのウールスーツに変更（自然な質感）',
            '예: 인물과 자세는 그대로 두고, 의상을 맞춤 네이비 울 슈트로 변경(자연스러운 질감)',
            'p. ej. Mantén la persona y la pose, cambia el atuendo por un traje de lana azul marino, textura realista',
          )"
        ></textarea>
        <p class="pp-field-help">{{ L(
          '提示：以「保留人物、把服裝換成…」開頭效果最佳。',
          'Tip: prompts starting with "Keep the person, change the outfit to…" work best.',
          'ヒント：「人物はそのままに、服装を…に変更」で始めると効果的です。',
          '팁: "인물은 유지하고, 의상을 …로 변경"으로 시작하면 가장 효과적입니다.',
          'Consejo: empieza con "Conserva a la persona, cambia el atuendo a…"',
        ) }}</p>

        <div class="mt-3">
          <p class="pp-field-label">{{ L('快速套用', 'Quick Presets', 'クイックプリセット', '빠른 프리셋', 'Preajustes rápidos') }}</p>
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
        {{ L('訂閱後即可使用此工具生成你的圖片。', 'Subscribe to generate your own results.', '購読すると、このツールで自分の画像を生成できます。', '구독하면 이 도구로 직접 결과물을 생성할 수 있습니다.', 'Suscríbete para generar tus propios resultados.') }}
        <button @click="gotoPricing" class="underline ml-1">{{ L('查看方案', 'View Plans', 'プランを見る', '플랜 보기', 'Ver planes') }} →</button>
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
      >📥 {{ L('下載', 'Download', 'ダウンロード', '다운로드', 'Descargar') }}</button>
      <button
        @click="generate"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >🔄 {{ L('重新生成', 'Regenerate', '再生成', '재생성', 'Regenerar') }}</button>
    </template>

    <!-- ─── EXAMPLES ─── -->
    <template v-if="examples.length > 0" #examples-title>
      {{ L('範例靈感', 'Example Inspirations', '例とインスピレーション', '예시 영감', 'Ejemplos e inspiración') }}
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
