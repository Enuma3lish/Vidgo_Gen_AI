<script setup lang="ts">
/**
 * ShortVideo — PiAPI-style combined playground.
 *
 * One page covers two task types (V2V removed 2026-05-31):
 *   1. Image to Video  → /api/v1/tools/short-video    (image + prompt)
 *   2. Text to Video   → /api/v1/tools/kling-video    (prompt only)
 *
 * Route mapping:
 *   /tools/short-video      → defaults to image_to_video
 *   /tools/image-to-video   → image_to_video
 *   /tools/text-to-video    → redirects to /tools/short-video
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
import { useDemoMode, useLocalized, useExamplePrefill, useGenerationTask } from '@/composables'
import { usePromptLibrary } from '@/composables/usePromptLibrary'
import { toolsApi } from '@/api'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import VideoFaithfulnessControls from '@/components/tools/VideoFaithfulnessControls.vue'
import { extractApiError } from '@/utils/apiError'
import { dataURItoBlob } from '@/utils/dataUri'
import { downloadAsset } from '@/utils/downloadAsset'
import { handleCardRequired } from '@/utils/toolGate'

const { t, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const { isDemoUser, generateOnDemand } = useDemoMode()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

// ─── Task type + model catalogs ──────────────────────────────────────
// V2V (video_style_transfer) removed 2026-05-31.
type TaskType = 'image_to_video' | 'text_to_video'

interface ModelOpt {
  id: string
  nameZh: string
  nameEn: string
  badge?: string
}
// VidGo 3.0 扣點表 — each model id maps to a fixed credit cost in tools.py
// (resolve_video_credits). Labels, ids, and the creditCost computed below all
// agree with the backend so the user never gets a sticker-shock deduction.
// 2026-06-23 menu policy: only expose models with BOTH a verified PiAPI
// primary AND a verified secondary provider (per owner directive "must have
// two providers, remove non-duplicates"). Secondary is Pollo for the
// Hailuo/Seedance/Kling family; for Veo specifically Pollo has no endpoint,
// so the secondary is Vertex AI Veo (provider_router VERTEX_VIDEO_MODEL_IDS).
// Models removed in this pass:
//   - wan      — no Pollo endpoint exists, no other backup
//   - hunyuan  — not in Pollo's catalog (404'd in prod) AND PiAPI rejects
//                Qubico/hunyuan + img2video-concat with "invalid request"
const I2V_MODELS: ModelOpt[] = [
  { id: 'hailuo',         nameZh: 'Hailuo Fast（最便宜）',      nameEn: 'Hailuo Fast (cheapest)' },
  { id: 'kling_v2',       nameZh: 'Kling V2.5（標準）',          nameEn: 'Kling V2.5 (standard)' },
  { id: 'seedance',       nameZh: 'Seedance 720p',             nameEn: 'Seedance 720p', badge: 'premium' },
  { id: 'seedance_1080p', nameZh: 'Seedance 1080p',            nameEn: 'Seedance 1080p', badge: 'premium' },
  { id: 'kling_v3_std',   nameZh: 'Kling V3.0（標準）',          nameEn: 'Kling V3.0 (standard)', badge: 'premium' },
  { id: 'kling_omni',     nameZh: 'Kling V3.0 PRO（含音訊）',    nameEn: 'Kling V3.0 PRO (with audio)', badge: 'premium' },
  { id: 'veo',            nameZh: 'Veo 3.1（含音訊）',           nameEn: 'Veo 3.1 (with audio)', badge: 'premium' },
]
// 2026-06-25 — Hailuo is the basic T2V default: cheapest (18 cr) AND the only
// model both PiAPI and Pollo serve in text-to-video, so it has a real backup
// (routes through /text-to-video → TaskType.T2V dual-provider). Seedance is the
// mid premium tier on the same path. The three Kling tiers keep /kling-video.
const T2V_MODELS: ModelOpt[] = [
  { id: 'hailuo',     nameZh: 'Hailuo Fast（最便宜）',      nameEn: 'Hailuo Fast (cheapest)' },
  { id: 'seedance',   nameZh: 'Seedance 720p',            nameEn: 'Seedance 720p', badge: 'premium' },
  { id: 'default',    nameZh: 'Kling V2.5（標準）',         nameEn: 'Kling V2.5 (standard)', badge: 'premium' },
  { id: 'flagship',   nameZh: 'Kling V3.0（標準）',         nameEn: 'Kling V3.0 (standard)', badge: 'premium' },
  { id: 'omni',       nameZh: 'Kling V3.0 PRO（含音訊）',    nameEn: 'Kling V3.0 PRO (with audio)', badge: 'premium' },
]
function modelOptionsFor(tt: TaskType): ModelOpt[] {
  return tt === 'image_to_video' ? I2V_MODELS : T2V_MODELS
}

// Default model per task type — chosen as the cheapest/most-reliable
const DEFAULT_MODEL: Record<TaskType, string> = {
  image_to_video: 'seedance',
  text_to_video:  'hailuo',
}

// ─── State ───────────────────────────────────────────────────────────
const taskType = ref<TaskType>('image_to_video')
const modelId = ref<string>(DEFAULT_MODEL.image_to_video)

const prompt = ref('')
const negativePrompt = ref('')
const motionStrength = ref<number>(5)
const aspectRatio = ref<'16:9' | '9:16' | '1:1'>('16:9')
const duration = ref<5 | 8 | 10>(5)
// 2026-06-12 — anti-hallucination controls (additive; the prompt itself
// stays verbatim). cameraMove pins an exact move; faithLock = subject_lock
// in I2V mode and strict_prompt in T2V mode. Default on.
const cameraMove = ref('')
const faithLock = ref(true)

const imageInput = ref<string | undefined>(undefined)   // data URI from ImageUploader (for I2V)

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

// P0-2: single source of truth for the in-flight task. Recovers on timeout
// (background-poll instead of erroring) and on page refresh (resume()).
const task = useGenerationTask('short_video')
function renderTaskResult(r: any) {
  if (r && r.success && (r.video_url || r.result_url)) {
    resultUrl.value = r.video_url || r.result_url
    status.value = 'done'
    statusText.value = isZh.value ? '完成' : 'Done'
    if (r.credits_used) creditsStore.deductCredits(r.credits_used)
  }
}
watch(() => task.result.value, (r) => renderTaskResult(r))
watch(() => task.phase.value, (p) => {
  if (p === 'error') {
    status.value = 'error'
    statusText.value = isZh.value ? '生成失敗' : 'Failed'
    uiStore.showError(task.error.value || (isZh.value ? '生成失敗' : 'Generation failed'))
  }
})
onMounted(() => {
  // Resume a generation left in-flight by a previous page load (refresh recovery).
  if (task.resume()) {
    status.value = 'running'
    statusText.value = isZh.value ? '正在恢復先前的生成…' : 'Resuming your previous generation…'
  }
})

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

// Editing the prompt away from the chosen preset clears the preset id, so the
// backend sees a CUSTOM prompt (subscription + bound card required) rather
// than a free example.
watch(prompt, (val) => {
  if (selectedPresetId.value && val.trim() !== presetPromptFor(selectedPresetId.value).trim()) {
    selectedPresetId.value = ''
  }
})
const usingPreset = computed(() =>
  !!selectedPresetId.value && prompt.value.trim() === presetPromptFor(selectedPresetId.value).trim()
)

// Default task type from route. /tools/video-transform was removed
// 2026-05-31 (V2V dropped); the route is gone, so we only branch I2V vs T2V.
function applyRouteToTaskType() {
  const name = String(route.name || '')
  const path = String(route.path || '')
  if (name === 'text-to-video' || path.endsWith('/text-to-video')) {
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

// Gallery "Try this example" deeplink — prefill prompt + source image. A
// carried image forces image_to_video so the picture is actually used; the
// prompt fills the textarea (marked custom, which is correct for an edited run).
useExamplePrefill({
  onPrompt: (p) => { prompt.value = p },
  onImage: (url) => {
    imageInput.value = url
    taskType.value = 'image_to_video'
    modelId.value = DEFAULT_MODEL.image_to_video
  },
  onError: () => uiStore.showError(L(
    '範例素材已過期,請改用其他範例或上傳自有圖片。',
    'This example is no longer available. Pick another or upload your own image.',
    'この例は利用できなくなりました。別の例を選ぶか、画像をアップロードしてください。',
    '이 예제는 더 이상 사용할 수 없습니다. 다른 예제를 선택하거나 이미지를 업로드하세요.',
    'Este ejemplo ya no está disponible. Elige otro o sube tu propia imagen.',
  )),
})

// ─── Validation + cost ───────────────────────────────────────────────
const disabled = computed(() => {
  // Demo/free users may ONLY preview a cached example from the dropdown — the
  // prompt box is read-only for them, so "ready" means a preset is picked.
  // (They cannot type a custom prompt; that needs a subscription.)
  if (isDemoUser.value) return !usingPreset.value
  if (taskType.value === 'image_to_video') return !imageInput.value
  return !prompt.value.trim()  // text_to_video
})

// Map the page's model dropdown to the demo model catalog (Kling 3.0 / Veo).
// Standard/cheap models return undefined → the free "default" cached example.
// Sora 2 lives on its own page (Sora2Pro.vue), not in this model list.
function demoModelId(): string | undefined {
  const m = (modelId.value || '').toLowerCase()
  if (m === 'veo') return 'veo'
  if (m.includes('kling_v3') || m === 'kling_omni' || m === 'flagship' || m === 'omni') return 'kling_v3'
  return undefined
}
const isRunning = computed(() => status.value === 'running')

const creditCost = computed(() => {
  // VidGo 3.0 扣點表 — mirror resolve_video_credits() in backend tools.py.
  if (taskType.value === 'text_to_video') {
    if (modelId.value === 'omni') return 130      // Kling V3.0 PRO (audio)
    if (modelId.value === 'flagship') return 65   // Kling V3.0 STD
    if (modelId.value === 'seedance') return 65   // Seedance 720p (dual-provider)
    if (modelId.value === 'default') return 28    // Kling V2.5 STD
    return 18                                     // Hailuo (basic, dual-provider)
  }
  const m = modelId.value || ''
  if (m === 'veo') return 80                      // Veo 3.1 (PiAPI primary, Vertex backup)
  if (m === 'seedance_1080p') return 160
  if (m === 'seedance') return 65                 // Seedance 720p
  if (m === 'kling_omni') return 130              // Kling V3.0 PRO (audio)
  if (m === 'kling_v3_std') return 65             // Kling V3.0 STD
  if (m.includes('kling')) return 28              // Kling V2.5 standard
  return 18                                       // hailuo / default
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

// handleVideoChange removed 2026-05-31 — V2V dropped.

// ─── Generate ────────────────────────────────────────────────────────
// Demo/free preview: pull the cached example for the picked (model × preset)
// from the demo cache-through endpoint and show it watermarked. No credits,
// no real generation — this is the "try a premium model for free" path.
async function generateDemoPreview() {
  status.value = 'running'
  statusText.value = isZh.value ? '載入範例中…' : 'Loading example…'
  resultUrl.value = null
  try {
    const effect = (usingPreset.value ? presetPromptFor(selectedPresetId.value) : prompt.value.trim()) || undefined
    const url = await generateOnDemand('short_video', undefined, {
      effect_prompt: effect,
      model_id: demoModelId(),
      // A library-picked (non-data:) image can key an I2V example; uploaded
      // data URIs are ignored in demo mode (the cached example has its own input).
      input_image_url: imageInput.value && !imageInput.value.startsWith('data:') ? imageInput.value : undefined,
    })
    if (url) {
      resultUrl.value = url
      status.value = 'done'
      statusText.value = isZh.value ? '範例預覽（含浮水印）' : 'Example preview (watermarked)'
    } else {
      status.value = 'error'
      statusText.value = isZh.value ? '此模型尚無快取範例' : 'No cached example for this model yet'
      uiStore.showError(isZh.value
        ? '此模型尚無快取範例，請改選其他模型或範例。'
        : 'No cached example for this model yet — try another model or preset.')
    }
  } catch (e: any) {
    status.value = 'error'
    statusText.value = isZh.value ? '載入失敗' : 'Failed'
    uiStore.showError(extractApiError(e, isZh.value ? '載入失敗' : 'Failed to load example'))
  }
}

async function generate() {
  if (disabled.value || isRunning.value) return
  // Free/visitor users get the watermarked cached preview for the picked
  // premium model — the conversion driver. Subscribers fall through to real
  // generation below.
  if (isDemoUser.value) { await generateDemoPreview(); return }
  // No client-side subscription block: the backend decides. A free account
  // using an unmodified preset gets the cached example; a custom/edited prompt
  // returns error_code 'subscription_card_required', handled below.
  status.value = 'running'
  statusText.value = isZh.value ? '生成中… 通常需要 1-3 分鐘' : 'Generating… typically 1-3 min'
  resultUrl.value = null

  // Upload the still BEFORE handing to the task wrapper (the upload must not be
  // tagged with the generation's client_task_id).
  let imageUrl: string | null = null
  if (taskType.value === 'image_to_video') {
    imageUrl = await ensureImageUrl()
    if (!imageUrl) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }
  }

  let result: any
  try {
    result = await task.run((cid) => {
      if (taskType.value === 'image_to_video') {
        return toolsApi.shortVideo(imageUrl as string, {
          motionStrength: motionStrength.value,
          modelId: modelId.value,
          prompt: prompt.value.trim() || undefined,
          promptId: usingPreset.value ? selectedPresetId.value : undefined,
          negativePrompt: negativePrompt.value.trim() || undefined,
          locale: String(locale.value || ''),
          cameraMove: cameraMove.value || undefined,
          subjectLock: faithLock.value,
        }, cid)
      }
      // text_to_video. Kling tiers (V2.5 default / V3.0 flagship / V3.0 PRO omni)
      // route to /kling-video; the cheaper Hailuo / Seedance route to the
      // dual-provider /text-to-video (PiAPI → Pollo), so the basic default has a
      // real backup. 2026-06-25.
      const klingTiers = ['default', 'flagship', 'omni']
      if (klingTiers.includes(modelId.value)) {
        const tier = (modelId.value === 'flagship' || modelId.value === 'omni')
          ? modelId.value
          : 'default'
        return toolsApi.klingVideo({
          prompt: prompt.value.trim(),
          tier: tier as 'default' | 'flagship' | 'omni',
          aspectRatio: aspectRatio.value,
          duration: duration.value as 5 | 10,
          negativePrompt: negativePrompt.value.trim() || undefined,
          cameraMove: cameraMove.value || undefined,
          strictPrompt: faithLock.value,
        }, cid)
      }
      return toolsApi.textToVideo({
        prompt: prompt.value.trim(),
        modelId: modelId.value,
        aspectRatio: aspectRatio.value,
        duration: duration.value as 5 | 10,
        negativePrompt: negativePrompt.value.trim() || undefined,
        cameraMove: cameraMove.value || undefined,
        strictPrompt: faithLock.value,
        promptId: usingPreset.value ? selectedPresetId.value : undefined,
        locale: String(locale.value || ''),
      }, cid)
    })
  } catch (e: any) {
    // Only non-recoverable errors reach here; timeouts are handled by task.run.
    status.value = 'error'
    statusText.value = isZh.value ? '錯誤' : 'Error'
    uiStore.showError(extractApiError(e, isZh.value ? '生成失敗' : 'Generation failed'))
    return
  }

  if (result === null) {
    // Timed out client-side but the backend is still running — DON'T error.
    // Keep showing progress; the result will appear here when polling resolves
    // and is also saved to 作品庫 (gallery CTA is shown via task.suggestGallery).
    status.value = 'running'
    statusText.value = isZh.value
      ? '仍在生成中，完成後會自動顯示，也會存入「我的作品」。'
      : 'Still generating — it will appear here when done, and is saved to My Works.'
    return
  }

  if (handleCardRequired(result, uiStore, router, isZh.value)) {
    status.value = 'idle'
    return
  }

  if (result?.success && (result.video_url || result.result_url)) {
    renderTaskResult(result)
    uiStore.showSuccess(t('common.success') || 'Success')
  } else {
    status.value = 'error'
    statusText.value = isZh.value ? '生成失敗' : 'Failed'
    uiStore.showError(result?.message || result?.error || (isZh.value ? '生成失敗' : 'Generation failed'))
  }
}

// ─── UI label helpers ────────────────────────────────────────────────
const pageTitle = computed(() => {
  if (taskType.value === 'text_to_video') return isZh.value ? 'AI 影片生成（文字）' : 'AI Video Generation (Text)'
  return isZh.value ? 'AI 影片生成（圖片）' : 'AI Video Generation (Image)'
})
const pageSubtitle = computed(() => {
  if (taskType.value === 'text_to_video') return isZh.value ? '輸入文字描述，AI 生成 5-10 秒影片。' : 'Describe a scene; AI generates a 5-10s video.'
  return isZh.value ? '上傳圖片，AI 加入鏡頭與動作生成影片。' : 'Upload a still; AI adds camera + motion to create video.'
})

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="240"
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="isZh ? '開始生成' : 'Generate'"
    :generate-label-running="isZh ? '生成中…' : 'Generating…'"
    :disabled="disabled"
    @generate="generate"
  >
    <template #inputs>
      <!-- P0-2: background-recovery banner. Shown when the request timed out
           client-side but the backend is still running; result appears here
           when polling resolves and is also saved to My Works. -->
      <div v-if="task.suggestGallery.value" class="rounded-lg p-3 text-xs"
           style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);">
        <p>{{ isZh ? '生成時間較長，仍在背景處理中。完成後會自動顯示，也會存入「我的作品」。' : 'This is taking a while — still processing in the background. It will appear here when done, and is saved to My Works.' }}</p>
        <button type="button" class="underline mt-1" @click="router.push({ name: 'my-works' })">
          {{ isZh ? '前往「我的作品」 →' : 'Go to My Works →' }}
        </button>
      </div>

      <!-- Task type — 3 options switch the rest of the form -->
      <div>
        <label class="pp-field-label">{{ isZh ? '任務類型 *' : 'Task Type *' }}</label>
        <select v-model="taskType" class="pp-select">
          <option value="image_to_video">{{ isZh ? '圖片轉影片 (I2V)' : 'Image to Video' }}</option>
          <option value="text_to_video">{{ isZh ? '文字生影片 (T2V)' : 'Text to Video' }}</option>
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

      <!-- V2V video upload removed 2026-05-31 -->

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
            <!-- Visitors/free users can only run a curated example, so the empty
                 "custom" choice is a disabled placeholder for them; members keep
                 it as the one-click fill / clear option. -->
            <option value="" :disabled="isDemoUser">{{ isDemoUser
              ? (isZh ? '— 請選擇範例 —' : '— Select an example —')
              : (isZh ? '— 選擇範例（一鍵填入）—' : '— Pick a preset (one-click fill) —') }}</option>
            <option v-for="opt in presetOptions" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
          </select>
        </div>

        <textarea
          v-model="prompt"
          rows="4"
          maxlength="2000"
          class="pp-textarea"
          :readonly="isDemoUser"
          :class="{ 'opacity-60 cursor-not-allowed': isDemoUser }"
          :placeholder="isDemoUser
            ? (isZh ? '請從上方下拉選單挑選範例（免費帳號僅能使用範例）' : 'Pick an example from the dropdown above (free accounts can only use examples)')
            : (isZh
              ? (taskType === 'image_to_video' ? '例：相機緩慢推近，產品微微旋轉，黃金時段陽光柔和。' : '描述你想要的影片內容…')
              : (taskType === 'image_to_video' ? 'e.g. Slow camera push-in, product slowly rotates, soft golden-hour light.' : 'Describe the video you want…'))"
        ></textarea>
        <p class="pp-field-help">{{ isDemoUser
          ? (isZh ? '免費帳號只能從下拉選單選擇範例提示詞；自訂提示詞需訂閱。' : 'Free accounts can only pick an example prompt from the dropdown; custom prompts require a subscription.')
          : (isZh ? '提示會原封不動傳給模型；越具體越好。' : 'Your prompt reaches the model verbatim. The more specific, the better.') }}</p>
      </div>

      <!-- Anti-hallucination controls: camera move + faith lock (2026-06-12).
           faithLock = subject_lock (I2V) / strict_prompt (T2V). -->
      <VideoFaithfulnessControls
        :mode="taskType === 'image_to_video' ? 'i2v' : 't2v'"
        v-model:camera-move="cameraMove"
        v-model:faith-lock="faithLock"
      />

      <!-- Negative prompt (both I2V and T2V) -->
      <div>
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
        {{ isZh
          ? '免費帳號：選一個進階模型（Kling 3.0 / Veo）＋範例，即可預覽含浮水印的成品。訂閱即可去除浮水印並用自訂提示詞生成。'
          : 'Free account: pick a premium model (Kling 3.0 / Veo) + an example to preview the watermarked result. Subscribe to remove the watermark and generate from your own prompts.' }}
        <button @click="gotoPricing" class="underline ml-1">{{ isZh ? '查看方案' : 'View Plans' }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <video :src="resultUrl" class="max-w-full max-h-[520px] rounded-lg" controls />
    </template>

    <template v-if="resultUrl" #result-actions>
      <!-- Demo preview is watermarked → drive the subscribe conversion instead
           of offering a clean download. -->
      <button
        v-if="isDemoUser"
        @click="gotoPricing"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: linear-gradient(135deg,#7c3aed,#a855f7); color: #fff; border: 0;"
      >✨ {{ isZh ? '訂閱以去除浮水印' : 'Subscribe for clean output' }} →</button>
      <button
        v-else
        @click="downloadAsset(resultUrl!, `vidgo_video_${Date.now()}.mp4`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ isZh ? '下載' : 'Download' }}</button>
      <button
        @click="generate"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >🔄 {{ isZh ? (isDemoUser ? '換一個範例' : '重新生成') : (isDemoUser ? 'Try another' : 'Regenerate') }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="short-video" />
    </template>
  </PiapiPlayground>
</template>
