<script setup lang="ts">
/**
 * Claymation AI — PiAPI-style playground (NEW 2026-05-24).
 *
 * Layout matches piapi.ai/zh-TW/claymation-ai-generator: a single
 * "Mode" dropdown switches between Text-to-Image / Image-to-Image /
 * Text-to-Video / Video-to-Video, the rest of the inputs adapt to mode.
 *
 * Backend dispatches the mode to:
 *   T2I → Seedream 5 Lite
 *   I2I → Flux Kontext I2I (until PiAPI exposes Seedream-I2I separately)
 *   T2V → Kling Omni 3.0
 *   V2V → Seedance 2.0 Fast (first-frame I2V)
 *
 * The user's prompt reaches the model VERBATIM — only a one-line
 * "claymation style…" prefix is prepended server-side.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { toolsApi, uploadsApi } from '@/api'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import { dataURItoBlob } from '@/utils/dataUri'
import { downloadAsset } from '@/utils/downloadAsset'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const { isDemoUser } = useDemoMode()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

type Mode = 'text_to_image' | 'image_to_image' | 'text_to_video' | 'video_to_video'

const mode = ref<Mode>('text_to_image')
const prompt = ref('')
const aspectRatio = ref<'1:1' | '16:9' | '9:16' | '4:3' | '3:4'>('1:1')
const imageInput = ref<string | undefined>(undefined)   // data URI from ImageUploader
const videoFile = ref<File | null>(null)
const videoPreviewUrl = ref<string | null>(null)

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)
const resultKind = ref<'image' | 'video'>('image')

const isVideoMode = computed(() => mode.value === 'text_to_video' || mode.value === 'video_to_video')
const needsImage = computed(() => mode.value === 'image_to_image')
const needsVideo = computed(() => mode.value === 'video_to_video')

const disabled = computed(() => {
  if (!prompt.value.trim()) return true
  if (needsImage.value && !imageInput.value) return true
  if (needsVideo.value && !videoFile.value) return true
  return false
})
const creditCost = computed(() => isVideoMode.value ? 50 : 8)

function pickMode(next: Mode) {
  mode.value = next
  resultUrl.value = null
}

function handleVideoChange(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (!f) return
  if (f.size > 20 * 1024 * 1024) {
    uiStore.showError(L('檔案超過 20 MB 上限', 'File exceeds the 20 MB limit', '20MB上限', '20MB 한도', 'Excede 20 MB'))
    return
  }
  videoFile.value = f
  videoPreviewUrl.value = URL.createObjectURL(f)
}

// 7 outfit-style style presets — these are RENDERED into the prompt
// textarea on click so the user sees + can edit the canonical text.
const presets = [
  { id: 'family',    zh: '一個快樂的家庭在公園野餐',          en: 'a happy family having a picnic in a park' },
  { id: 'ramen',     zh: '一碗熱騰騰的拉麵，蔥花與半熟蛋',    en: 'a steaming bowl of ramen with green onions and soft-boiled egg' },
  { id: 'astronaut', zh: '一位太空人在月球上跳舞',            en: 'an astronaut dancing on the surface of the moon' },
  { id: 'cat',       zh: '一隻戴著草帽的橘貓在曬太陽',        en: 'an orange cat wearing a straw hat sunbathing' },
  { id: 'forest',    zh: '迷霧森林裡的小木屋，夕陽從樹梢灑下', en: 'a tiny wooden cabin in a foggy forest with sunset light' },
  { id: 'robot',     zh: '一個復古機器人在咖啡廳裡點咖啡',    en: 'a retro robot ordering coffee at a cafe' },
]
function applyPreset(p: typeof presets[number]) { prompt.value = isZh.value ? p.zh : p.en }

async function ensureUploadedImage(): Promise<string | null> {
  if (!imageInput.value) return null
  if (!imageInput.value.startsWith('data:')) return imageInput.value
  const blob = dataURItoBlob(imageInput.value)
  if (!blob) return null
  const upload = await toolsApi.uploadImage(blob as File)
  return upload.url
}

async function generate() {
  if (disabled.value || status.value === 'running') return
  if (isDemoUser.value) {
    uiStore.showInfo(L('請訂閱以使用此工具', 'Please subscribe to use this tool', 'サブスク登録してください', '구독해 주세요', 'Suscríbete'))
    return
  }
  status.value = 'running'
  statusText.value = isZh.value
    ? (isVideoMode.value ? '生成中…通常 1-3 分鐘' : '生成中…通常 15-30 秒')
    : (isVideoMode.value ? 'Generating… 1-3 min' : 'Generating… 15-30s')
  resultUrl.value = null
  try {
    let imageUrl: string | undefined
    let videoUrl: string | undefined
    if (needsImage.value) {
      const u = await ensureUploadedImage()
      if (!u) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }
      imageUrl = u
    }
    if (needsVideo.value) {
      statusText.value = isZh.value ? '上傳影片中…' : 'Uploading video…'
      const normalized = await uploadsApi.normalizeVideo(videoFile.value!)
      videoUrl = normalized.video_url
      statusText.value = isZh.value ? '生成中…通常 1-3 分鐘' : 'Generating… 1-3 min'
    }
    const result = await toolsApi.claymation({
      mode: mode.value,
      prompt: prompt.value.trim(),
      imageUrl,
      videoUrl,
      aspectRatio: aspectRatio.value,
    })
    if (result.success && (result.image_url || result.video_url || result.result_url)) {
      const url = result.image_url || result.video_url || result.result_url || ''
      resultUrl.value = url.startsWith('http') ? url : `${window.location.origin}${url}`
      resultKind.value = isVideoMode.value ? 'video' : 'image'
      status.value = 'done'
      statusText.value = isZh.value ? '完成' : 'Done'
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      statusText.value = isZh.value ? '生成失敗' : 'Failed'
      uiStore.showError((result as any).message || (result as any).error || (isZh.value ? '生成失敗' : 'Generation failed'))
    }
  } catch (e: any) {
    status.value = 'error'
    statusText.value = isZh.value ? '錯誤' : 'Error'
    uiStore.showError(e?.message || (isZh.value ? '生成失敗' : 'Generation failed'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="150"
    :title="isZh ? '黏土風生成 (Claymation AI)' : 'Claymation AI Generator'"
    :subtitle="isZh
      ? '把任何主題變成手工黏土的定格動畫感。支援文字生圖、圖生圖、文字生影片、影片轉黏土風。'
      : 'Turn anything into handcrafted stop-motion clay. Supports text→image, image→image, text→video, and video→video.'"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="isZh ? '生成' : 'Generate'"
    :generate-label-running="isZh ? '生成中…' : 'Generating…'"
    :disabled="disabled || isDemoUser"
    @generate="generate"
  >
    <template #inputs>
      <!-- Mode dropdown -->
      <div>
        <label class="pp-field-label">{{ isZh ? '模型 *' : 'Model *' }}</label>
        <select :value="mode" @change="(e) => pickMode((e.target as HTMLSelectElement).value as Mode)" class="pp-select">
          <option value="text_to_image">{{ isZh ? '文字生圖 (Seedream 5 Lite)' : 'Text to Image — Seedream 5 Lite' }}</option>
          <option value="image_to_image">{{ isZh ? '圖生圖 (Flux Kontext)' : 'Image to Image — Flux Kontext' }}</option>
          <option value="text_to_video">{{ isZh ? '文字生影片 (Kling 3.0)' : 'Text to Video — Kling 3.0' }}</option>
          <option value="video_to_video">{{ isZh ? '影片轉黏土 (Seedance 2.0 Fast)' : 'Video to Video — Seedance 2.0 Fast' }}</option>
        </select>
      </div>

      <!-- Task type (locked per mode) -->
      <div>
        <label class="pp-field-label">{{ isZh ? '任務類型 *' : 'Task Type *' }}</label>
        <select class="pp-select" disabled>
          <option v-if="mode === 'text_to_image'">txt2img</option>
          <option v-else-if="mode === 'image_to_image'">img2img</option>
          <option v-else-if="mode === 'text_to_video'">txt2video</option>
          <option v-else>img2video (first-frame)</option>
        </select>
      </div>

      <!-- Image upload (I2I) -->
      <div v-if="mode === 'image_to_image'">
        <label class="pp-field-label">{{ isZh ? '參考圖片 *' : 'Reference Image *' }}</label>
        <ImageUploader
          tool-type="claymation"
          v-model="imageInput"
          :label="isZh ? '點擊或拖放圖片' : 'Click or drag an image'"
        />
      </div>

      <!-- Video upload (V2V) -->
      <div v-if="mode === 'video_to_video'">
        <label class="pp-field-label">{{ isZh ? '來源影片 *' : 'Source Video *' }}</label>
        <input type="file" accept="video/mp4" class="pp-input" @change="handleVideoChange" />
        <p class="pp-field-help">{{ L('MP4 · 最大 20 MB。系統會抽出第一幀並重塑為黏土感影片。', 'MP4 · max 20 MB. We extract the first frame and re-render the clip with claymation styling.', 'MP4 · 最大20MB。', 'MP4 · 최대 20MB.', 'MP4 · máx 20 MB.') }}</p>
        <video v-if="videoPreviewUrl" :src="videoPreviewUrl" class="w-full mt-2 rounded-lg" controls />
      </div>

      <!-- Prompt -->
      <div>
        <label class="pp-field-label">{{ isZh ? '描述 *' : 'Prompt *' }}</label>
        <textarea
          v-model="prompt"
          rows="4"
          maxlength="2000"
          class="pp-textarea"
          :placeholder="isZh ? '描述你想要的黏土風場景…' : 'Describe the claymation scene you want…'"
        ></textarea>
        <p class="pp-field-help">{{ isZh ? '提示會原封不動傳給 AI（前綴加上「黏土風」風格指令）。' : 'Your prompt reaches the model verbatim (prefixed with a one-line "claymation style" instruction).' }}</p>

        <div class="mt-3">
          <p class="pp-field-label">{{ isZh ? '快速套用' : 'Quick Presets' }}</p>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="p in presets"
              :key="p.id"
              type="button"
              @click="applyPreset(p)"
              class="text-[11px] px-2 py-1 rounded-full"
              style="background: rgba(124,58,237,0.15); color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
            >{{ isZh ? p.zh.slice(0, 12) : p.en.slice(0, 22) }}</button>
          </div>
        </div>
      </div>

      <!-- Aspect ratio (image modes only) -->
      <div v-if="mode === 'text_to_image' || mode === 'image_to_image'">
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
        {{ isZh ? '訂閱後即可使用此工具。' : 'Subscribe to generate your own results.' }}
        <button @click="gotoPricing" class="underline ml-1">{{ isZh ? '查看方案' : 'View Plans' }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <img v-if="resultKind === 'image'" :src="resultUrl" alt="Result" class="max-w-full max-h-[520px] object-contain rounded-lg" />
      <video v-else :src="resultUrl" class="max-w-full max-h-[520px] rounded-lg" controls />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button
        @click="downloadAsset(resultUrl!, `vidgo_claymation_${Date.now()}.${resultKind === 'image' ? 'png' : 'mp4'}`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ isZh ? '下載' : 'Download' }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="claymation" />
    </template>
  </PiapiPlayground>
</template>
