<script setup lang="ts">
/**
 * ShortVideo — PiAPI-style combined playground (Deploy 3c, 2026-05-24).
 *
 * One page covers THREE task types:
 *   1. Image to Video  → /api/v1/tools/short-video    (image + prompt)
 *   2. Text to Video   → /api/v1/tools/kling-video    (prompt only)
 *   3. Video Style Transfer → /api/v1/tools/video-transform (video + prompt)
 *
 * Route mapping kept the same so existing bookmarks work:
 *   /tools/short-video      → defaults to image_to_video
 *   /tools/image-to-video   → image_to_video
 *   /tools/text-to-video    → redirects to /tools/short-video
 *   /tools/video-transform  → video_style_transfer (URL-driven)
 *
 * Layout: PiapiPlayground component (left config / right result / status
 * pill / examples row below). Colors preserved (#0a0a0f bg, violet
 * gradient buttons, #94949f text).
 *
 * Notable behavior:
 *   - User's prompt reaches the model VERBATIM. No Gemini rewrite.
 *   - Model dropdown filters by task type. Switching task type resets
 *     selected model to the default for that type.
 *   - motion_strength applies only to I2V (varies the auto-generated
 *     motion description; user prompt still overrides when present).
 *   - Demo users see a CTA to /pricing instead of a generate button.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { usePromptLibrary } from '@/composables/usePromptLibrary'
import { toolsApi, uploadsApi } from '@/api'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import { extractApiError } from '@/utils/apiError'
import { dataURItoBlob } from '@/utils/dataUri'
import { downloadAsset } from '@/utils/downloadAsset'

const { t, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const { isDemoUser } = useDemoMode()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

// ─── Task type + model catalogs ──────────────────────────────────────
type TaskType = 'image_to_video' | 'text_to_video' | 'video_style_transfer'

interface ModelOpt {
  id: string
  nameZh: string
  nameEn: string
  badge?: string
}
const I2V_MODELS: ModelOpt[] = [
  { id: 'seedance',   nameZh: 'Seedance 2.0 Fast',         nameEn: 'Seedance 2.0 Fast',         badge: 'default' },
  { id: 'kling_omni', nameZh: 'Kling 3.0 / Omni（含音訊）', nameEn: 'Kling 3.0 / Omni (with audio)', badge: 'premium' },
  // id MUST stay 'kling_v2' (not 'kling_v3'): the backend cost/tier resolver
  // routes any id containing "_v3"/"omni" to Kling 3.0/Omni at 750 credits.
  // 'kling_v2' lands on the standard 2.6 tier (60 credits) so the label,
  // the routed model, and the charged cost all agree.
  { id: 'kling_v2',   nameZh: 'Kling 2.6（標準）',           nameEn: 'Kling 2.6 (standard)' },
  { id: 'veo',        nameZh: 'Veo 3.1 Fast（Google 旗艦）', nameEn: 'Veo 3.1 Fast (Google flagship)', badge: 'premium' },
  { id: 'hailuo',     nameZh: 'Hailuo（最便宜）',           nameEn: 'Hailuo (cheapest)' },
  { id: 'hunyuan',    nameZh: 'Hunyuan（中文擅長）',         nameEn: 'Hunyuan (Chinese-friendly)' },
  { id: 'wan',        nameZh: 'Wan 2.6',                   nameEn: 'Wan 2.6' },
]
const T2V_MODELS: ModelOpt[] = [
  { id: 'default',    nameZh: 'Kling 2.6 (預設)',          nameEn: 'Kling 2.6 (default)' },
  { id: 'flagship',   nameZh: 'Kling 2.1-master (旗艦)',   nameEn: 'Kling 2.1-master (flagship)', badge: 'premium' },
  { id: 'omni',       nameZh: 'Kling 3.0 / Omni (含音訊)',  nameEn: 'Kling 3.0 / Omni (with audio)', badge: 'premium' },
]
const V2V_MODELS: ModelOpt[] = [
  // V2V runs Seedance first-frame I2V server-side (Wan 2.1 VACE was pulled
  // from PiAPI's catalog). Label it for what actually runs so the dropdown
  // isn't promising a model we no longer call.
  { id: 'seedance',   nameZh: 'Seedance 2.0 Fast（首幀風格轉換）', nameEn: 'Seedance 2.0 Fast (first-frame style)' },
]
function modelOptionsFor(tt: TaskType): ModelOpt[] {
  return tt === 'image_to_video' ? I2V_MODELS
       : tt === 'text_to_video'  ? T2V_MODELS
       : V2V_MODELS
}

// Default model per task type — chosen as the cheapest/most-reliable
const DEFAULT_MODEL: Record<TaskType, string> = {
  image_to_video: 'seedance',
  text_to_video:  'default',
  video_style_transfer: 'seedance',
}

// ─── State ───────────────────────────────────────────────────────────
const taskType = ref<TaskType>('image_to_video')
const modelId = ref<string>(DEFAULT_MODEL.image_to_video)

const prompt = ref('')
const negativePrompt = ref('')
const motionStrength = ref<number>(5)
const aspectRatio = ref<'16:9' | '9:16' | '1:1'>('16:9')
const duration = ref<5 | 8 | 10>(5)

const imageInput = ref<string | undefined>(undefined)   // data URI from ImageUploader (for I2V)
const videoFile = ref<File | null>(null)                // raw File (for V2V)
const videoPreviewUrl = ref<string | null>(null)

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

// Curated prompt library (kv_*-style entries under `short_video` in
// prompt_library.json). Same source the flagship video / image tools
// already use — gives cold users a one-click way to populate the prompt
// instead of staring at an empty textarea. (KlingVideo wired this 2026-05-23;
// ShortVideo was left out and shipped as prompt-only — fixed 2026-05-25.)
const { options: presetOptions, promptFor: presetPromptFor } = usePromptLibrary('short_video')
const selectedPresetId = ref('')
function applyPreset() {
  if (!selectedPresetId.value) return
  prompt.value = presetPromptFor(selectedPresetId.value)
  // Clear any stale result so the right pane doesn't read as the new prompt.
  resultUrl.value = null
}
// Re-fetch the localized prompt text when the UI locale changes so the
// textarea swaps zh ↔ en in step with the chrome.
watch(locale, () => {
  if (selectedPresetId.value) prompt.value = presetPromptFor(selectedPresetId.value)
})

// Default task type from route
function applyRouteToTaskType() {
  const name = String(route.name || '')
  const path = String(route.path || '')
  if (name === 'video-transform' || path.endsWith('/video-transform')) {
    taskType.value = 'video_style_transfer'
  } else if (name === 'text-to-video' || path.endsWith('/text-to-video')) {
    taskType.value = 'text_to_video'
  } else {
    taskType.value = 'image_to_video'
  }
  modelId.value = DEFAULT_MODEL[taskType.value]
}

watch(taskType, (next, prev) => {
  if (next !== prev) {
    modelId.value = DEFAULT_MODEL[next]
    resultUrl.value = null
  }
})

onMounted(() => applyRouteToTaskType())

// ─── Validation + cost ───────────────────────────────────────────────
const disabled = computed(() => {
  if (taskType.value === 'image_to_video') return !imageInput.value
  if (taskType.value === 'text_to_video')  return !prompt.value.trim()
  return !videoFile.value || !prompt.value.trim()  // V2V
})
const isRunning = computed(() => status.value === 'running')

const creditCost = computed(() => {
  if (taskType.value === 'video_style_transfer') return 35
  if (taskType.value === 'text_to_video') {
    if (modelId.value === 'omni') return 750
    if (modelId.value === 'flagship') return 500
    return 60
  }
  // I2V — must mirror the backend cost-resolution chain in tools.py
  // (2026-05-26 sync). The previous mapping under-displayed Kling tiers,
  // causing the UI to show 200 credits while the backend deducted 750 for
  // kling_omni — a sticker-shock surprise on the user's balance.
  const m = modelId.value || ''
  if (m === 'veo') return 200
  if (m === 'kling_omni' || m.includes('_v3') || m.includes('kling-3') || m.includes('kling3')) return 750
  if (m.includes('kling') && (m.includes('flagship') || m.includes('master') || m.includes('2.1'))) return 500
  if (m.includes('kling')) return 60                                 // generic Kling 2.6
  if (m === 'seedance' || m === 'wan' || m === 'hunyuan') return 40
  return 20  // hailuo / default fallback
})

// ─── Helpers ─────────────────────────────────────────────────────────
async function ensureImageUrl(): Promise<string | null> {
  if (!imageInput.value) return null
  if (!imageInput.value.startsWith('data:')) return imageInput.value
  const blob = dataURItoBlob(imageInput.value)
  if (!blob) return null
  const up = await toolsApi.uploadImage(blob as File)
  return up.url
}

function handleVideoChange(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (!f) return
  if (f.size > 100 * 1024 * 1024) {
    uiStore.showError(L('檔案超過 100 MB 上限', 'File exceeds the 100 MB limit', '100MB上限', '100MB 한도', 'Excede 100 MB'))
    return
  }
  videoFile.value = f
  videoPreviewUrl.value = URL.createObjectURL(f)
}

// ─── Generate ────────────────────────────────────────────────────────
async function generate() {
  if (disabled.value || isRunning.value) return
  if (isDemoUser.value) {
    uiStore.showInfo(L('請訂閱以使用此工具', 'Please subscribe to use this tool', 'サブスク登録してください', '구독해 주세요', 'Suscríbete'))
    return
  }
  status.value = 'running'
  statusText.value = isZh.value ? '生成中… 通常需要 1-3 分鐘' : 'Generating… typically 1-3 min'
  resultUrl.value = null

  try {
    let result: any
    if (taskType.value === 'image_to_video') {
      const imageUrl = await ensureImageUrl()
      if (!imageUrl) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }
      result = await toolsApi.shortVideo(imageUrl, {
        motionStrength: motionStrength.value,
        modelId: modelId.value,
        prompt: prompt.value.trim() || undefined,
        negativePrompt: negativePrompt.value.trim() || undefined,
        locale: String(locale.value || ''),
      })
    } else if (taskType.value === 'text_to_video') {
      // /api/v1/tools/kling-video accepts T2V when image_url is omitted.
      // tier maps directly from modelId for T2V (default/flagship/omni).
      // 2026-05-26: was raw fetch('/api/v1/tools/kling-video') — relative URL
      // hit the wrong origin in prod and `credentials: 'include'` ignored the
      // Bearer token the app actually uses for auth, so the text-to-video
      // task silently failed for every logged-in user. Routed through
      // toolsApi.klingVideo so it uses the configured apiClient base URL +
      // Authorization header like every other tool call.
      const tier = (modelId.value === 'flagship' || modelId.value === 'omni')
        ? modelId.value
        : 'default'
      result = await toolsApi.klingVideo({
        prompt: prompt.value.trim(),
        tier,
        aspectRatio: aspectRatio.value,
        duration: duration.value as 5 | 10,
        negativePrompt: negativePrompt.value.trim() || undefined,
      })
    } else {
      // V2V
      statusText.value = isZh.value ? '上傳影片中…' : 'Uploading video…'
      const normalized = await uploadsApi.normalizeVideo(videoFile.value!)
      statusText.value = isZh.value ? '套用風格中…' : 'Applying style…'
      result = await toolsApi.videoTransform(normalized.video_url, prompt.value.trim())
    }

    if (result?.success && (result.video_url || result.result_url)) {
      resultUrl.value = result.video_url || result.result_url
      status.value = 'done'
      statusText.value = isZh.value ? '完成' : 'Done'
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      statusText.value = isZh.value ? '生成失敗' : 'Failed'
      uiStore.showError(result?.message || result?.error || (isZh.value ? '生成失敗' : 'Generation failed'))
    }
  } catch (e: any) {
    status.value = 'error'
    statusText.value = isZh.value ? '錯誤' : 'Error'
    uiStore.showError(extractApiError(e, isZh.value ? '生成失敗' : 'Generation failed'))
  }
}

// ─── UI label helpers ────────────────────────────────────────────────
const pageTitle = computed(() => {
  switch (taskType.value) {
    case 'text_to_video':       return isZh.value ? 'AI 影片生成（文字）' : 'AI Video Generation (Text)'
    case 'video_style_transfer': return isZh.value ? '影片風格轉換' : 'Video Style Transfer'
    default:                    return isZh.value ? 'AI 影片生成（圖片）' : 'AI Video Generation (Image)'
  }
})
const pageSubtitle = computed(() => {
  switch (taskType.value) {
    case 'text_to_video':       return isZh.value ? '輸入文字描述，AI 生成 5-10 秒影片。' : 'Describe a scene; AI generates a 5-10s video.'
    case 'video_style_transfer': return isZh.value ? '上傳影片，AI 套用新風格（如水彩、像素、賽博龐克）。' : 'Upload a video; AI applies a new style (watercolor, pixel, cyberpunk…).'
    default:                    return isZh.value ? '上傳圖片，AI 加入鏡頭與動作生成影片。' : 'Upload a still; AI adds camera + motion to create video.'
  }
})

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="150"
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="isZh ? '開始生成' : 'Generate'"
    :generate-label-running="isZh ? '生成中…' : 'Generating…'"
    :disabled="disabled || isDemoUser"
    @generate="generate"
  >
    <template #inputs>
      <!-- Task type — 3 options switch the rest of the form -->
      <div>
        <label class="pp-field-label">{{ isZh ? '任務類型 *' : 'Task Type *' }}</label>
        <select v-model="taskType" class="pp-select">
          <option value="image_to_video">{{ isZh ? '圖片轉影片 (I2V)' : 'Image to Video' }}</option>
          <option value="text_to_video">{{ isZh ? '文字生影片 (T2V)' : 'Text to Video' }}</option>
          <option value="video_style_transfer">{{ isZh ? '影片風格轉換 (V2V)' : 'Video Style Transfer' }}</option>
        </select>
      </div>

      <!-- Model dropdown — content depends on task type -->
      <div>
        <label class="pp-field-label">{{ isZh ? '模型 *' : 'Model *' }}</label>
        <select v-model="modelId" class="pp-select">
          <option v-for="m in modelOptionsFor(taskType)" :key="m.id" :value="m.id">
            {{ (isZh ? m.nameZh : m.nameEn) }}{{ m.badge ? ` · ${m.badge}` : '' }}
          </option>
        </select>
      </div>

      <!-- Image upload (I2V only) -->
      <div v-if="taskType === 'image_to_video'">
        <label class="pp-field-label">{{ isZh ? '起始圖片 *' : 'Starting Frame *' }}</label>
        <ImageUploader
          tool-type="short_video"
          v-model="imageInput"
          :label="isZh ? '點擊或拖放圖片' : 'Click or drag an image'"
        />
      </div>

      <!-- Video upload (V2V only) -->
      <div v-if="taskType === 'video_style_transfer'">
        <label class="pp-field-label">{{ isZh ? '來源影片 *' : 'Source Video *' }}</label>
        <input type="file" accept="video/mp4" class="pp-input" @change="handleVideoChange" />
        <p class="pp-field-help">{{ L('MP4 · 最大 100 MB · 系統會先正規化再轉換', 'MP4 · max 100 MB · normalized server-side first', 'MP4 · 最大100MB · サーバー側で正規化', 'MP4 · 최대 100MB · 서버에서 정규화', 'MP4 · máx 100 MB · normalizado en servidor') }}</p>
        <video v-if="videoPreviewUrl" :src="videoPreviewUrl" class="w-full mt-2 rounded-lg" controls />
      </div>

      <!-- Prompt -->
      <div>
        <label class="pp-field-label">
          {{ taskType === 'image_to_video' ? (isZh ? '動作描述（選填）' : 'Motion Prompt (optional)')
             : (isZh ? '描述 *' : 'Prompt *') }}
        </label>

        <!-- Preset picker — added 2026-05-25 to mirror KlingVideo's
             curated dropdown. Lets cold visitors start with a working
             one-click prompt instead of an empty textarea. -->
        <div v-if="presetOptions.length > 0" class="mb-2">
          <select v-model="selectedPresetId" @change="applyPreset" class="pp-select">
            <option value="">{{ isZh ? '— 選擇範例（一鍵填入）—' : '— Pick a preset (one-click fill) —' }}</option>
            <option v-for="opt in presetOptions" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
          </select>
        </div>

        <textarea
          v-model="prompt"
          rows="4"
          maxlength="2000"
          class="pp-textarea"
          :placeholder="isZh
            ? (taskType === 'image_to_video' ? '例：相機緩慢推近，產品微微旋轉，黃金時段陽光柔和。' : '描述你想要的影片內容…')
            : (taskType === 'image_to_video' ? 'e.g. Slow camera push-in, product slowly rotates, soft golden-hour light.' : 'Describe the video you want…')"
        ></textarea>
        <p class="pp-field-help">{{ isZh ? '提示會原封不動傳給模型；越具體越好。' : 'Your prompt reaches the model verbatim. The more specific, the better.' }}</p>
      </div>

      <!-- Negative prompt (I2V + T2V) -->
      <div v-if="taskType !== 'video_style_transfer'">
        <label class="pp-field-label">{{ isZh ? '負面提示（選填）' : 'Negative Prompt (optional)' }}</label>
        <input v-model="negativePrompt" type="text" maxlength="500" class="pp-input"
               :placeholder="isZh ? '例：模糊、變形、低品質' : 'e.g. blurry, distorted, low quality'" />
      </div>

      <!-- Motion strength slider (I2V only) -->
      <div v-if="taskType === 'image_to_video'">
        <label class="pp-field-label">{{ isZh ? '動態強度' : 'Motion Strength' }}
          <span class="ml-2" style="color: #a78bfa;">{{ motionStrength }}/10</span>
        </label>
        <input type="range" min="1" max="10" step="1" v-model.number="motionStrength" class="w-full" style="accent-color: #a78bfa;" />
        <div class="flex justify-between text-[10px] mt-0.5" style="color: #6b6b7a;">
          <span>{{ isZh ? '微微動' : 'Subtle' }}</span>
          <span>{{ isZh ? '大幅動' : 'Dramatic' }}</span>
        </div>
      </div>

      <!-- Aspect ratio (T2V only) -->
      <div v-if="taskType === 'text_to_video'">
        <label class="pp-field-label">{{ isZh ? '比例' : 'Aspect Ratio' }}</label>
        <select v-model="aspectRatio" class="pp-select">
          <option value="16:9">16:9 (landscape)</option>
          <option value="9:16">9:16 (portrait)</option>
          <option value="1:1">1:1 (square)</option>
        </select>
      </div>

      <!-- Duration (T2V only, V2V uses source video length) -->
      <div v-if="taskType === 'text_to_video'">
        <label class="pp-field-label">{{ isZh ? '影片長度（秒）' : 'Duration (seconds)' }}</label>
        <select v-model.number="duration" class="pp-select">
          <option :value="5">5s</option>
          <option :value="8">8s</option>
          <option :value="10">10s</option>
        </select>
      </div>

      <p v-if="isDemoUser" class="pp-field-help" style="color: #fbbf24;">
        {{ isZh ? '訂閱後即可使用此工具。' : 'Subscribe to generate your own videos.' }}
        <button @click="gotoPricing" class="underline ml-1">{{ isZh ? '查看方案' : 'View Plans' }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <video :src="resultUrl" class="max-w-full max-h-[520px] rounded-lg" controls />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button
        @click="downloadAsset(resultUrl!, `vidgo_video_${Date.now()}.mp4`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ isZh ? '下載' : 'Download' }}</button>
      <button
        @click="generate"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >🔄 {{ isZh ? '重新生成' : 'Regenerate' }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="short-video" />
    </template>
  </PiapiPlayground>
</template>
