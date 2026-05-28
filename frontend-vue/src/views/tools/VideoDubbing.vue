<script setup lang="ts">
/**
 * VideoDubbing — PiAPI-style playground (Deploy 4, 2026-05-24).
 *
 * Upload a video, pick a target language, optionally supply a reference
 * voice clip + transcript for voice cloning. Backend extracts/translates
 * the script (when not provided) and muxes new audio onto the video.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { toolsApi, uploadsApi } from '@/api'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import { downloadAsset } from '@/utils/downloadAsset'
import { extractApiError } from '@/utils/apiError'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const { isDemoUser } = useDemoMode()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

const LANGUAGES = [
  { code: 'Traditional Chinese', labelZh: '繁體中文', labelEn: 'Traditional Chinese' },
  { code: 'Simplified Chinese',  labelZh: '簡體中文', labelEn: 'Simplified Chinese' },
  { code: 'English',             labelZh: '英文',     labelEn: 'English' },
  { code: 'Japanese',            labelZh: '日文',     labelEn: 'Japanese' },
  { code: 'Korean',              labelZh: '韓文',     labelEn: 'Korean' },
  { code: 'Spanish',             labelZh: '西班牙文', labelEn: 'Spanish' },
  { code: 'Vietnamese',          labelZh: '越南文',   labelEn: 'Vietnamese' },
  { code: 'Thai',                labelZh: '泰文',     labelEn: 'Thai' },
]

const targetLanguage = ref<string>('Traditional Chinese')
const sourceLanguage = ref<string>('')
const sourceScript = ref<string>('')
const translatedScript = ref<string>('')
const voiceReferenceUrl = ref<string>('')

const videoFile = ref<File | null>(null)
const videoPreviewUrl = ref<string | null>(null)

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

// Backend requires (a) a video AND (b) at least one of source_script /
// translated_script. Without either script the API returns 400 "Please
// provide a source script/transcript or a translated script." Match that
// gate client-side so users see the disabled state instead of a backend
// error after a 30-second wait. (Fix 2026-05-26.)
const disabled = computed(() =>
  !videoFile.value
  || (!sourceScript.value.trim() && !translatedScript.value.trim())
)
// Backend tools.py video_dubbing handler deducts 30 credits (see comment
// at line ~4585: "30 credits per tier_config.py video_dubbing default; UI
// hard-codes the same value on CreditCost so the displayed cost matches
// what we deduct"). Frontend previously showed 80 — that was stale from
// an earlier pricing draft. Aligning now so the cost badge tells the truth.
const creditCost = computed(() => 30)

function handleVideoChange(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (!f) return
  if (f.size > 100 * 1024 * 1024) {
    uiStore.showError(L('檔案超過 100 MB', 'File exceeds 100 MB', '100MB上限', '100MB 한도', 'Excede 100 MB'))
    return
  }
  videoFile.value = f
  videoPreviewUrl.value = URL.createObjectURL(f)
}

async function generate() {
  if (disabled.value || status.value === 'running') return
  if (isDemoUser.value) {
    uiStore.showInfo(L('請訂閱以使用此工具', 'Please subscribe to use this tool', 'サブスク登録してください', '구독해 주세요', 'Suscríbete'))
    return
  }
  status.value = 'running'
  statusText.value = isZh.value ? '上傳並正規化…' : 'Uploading & normalizing…'
  resultUrl.value = null
  try {
    const normalized = await uploadsApi.normalizeVideo(videoFile.value!)
    statusText.value = isZh.value ? '翻譯與配音中…' : 'Translating & dubbing…'
    const result = await toolsApi.videoDubbing({
      videoUrl: normalized.video_url,
      targetLanguage: targetLanguage.value,
      sourceLanguage: sourceLanguage.value || undefined,
      sourceScript: sourceScript.value.trim() || undefined,
      translatedScript: translatedScript.value.trim() || undefined,
      voiceReferenceUrl: voiceReferenceUrl.value.trim() || undefined,
    })
    if (result.success && (result.video_url || result.result_url)) {
      resultUrl.value = result.video_url || result.result_url || null
      status.value = 'done'
      statusText.value = isZh.value ? '完成' : 'Done'
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      uiStore.showError((result as any).message || (result as any).error || (isZh.value ? '配音失敗' : 'Dubbing failed'))
    }
  } catch (e: any) {
    status.value = 'error'
    uiStore.showError(extractApiError(e, isZh.value ? '配音失敗' : 'Dubbing failed'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="180"
    :title="isZh ? '影片翻譯配音' : 'Video Translation & Dubbing'"
    :subtitle="isZh
      ? '上傳影片 → AI 翻譯腳本、生成目標語言語音、自動混合回影片。支援聲音複製（提供 30 秒參考音檔）。'
      : 'Upload a video → AI translates the script, generates target-language voice, muxes audio back onto the video. Supports voice cloning when you provide a 30-second reference clip.'"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="isZh ? '開始配音' : 'Generate'"
    :generate-label-running="isZh ? '處理中…' : 'Processing…'"
    :disabled="disabled || isDemoUser"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ isZh ? '模型 *' : 'Model *' }}</label>
        <select class="pp-select" disabled>
          <option>Video Dubbing — Whisper + F5-TTS / OpenAI TTS</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '任務類型 *' : 'Task Type *' }}</label>
        <select class="pp-select" disabled>
          <option>translate + dub</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '影片 *' : 'Video *' }}</label>
        <input type="file" accept="video/mp4" class="pp-input" @change="handleVideoChange" />
        <p class="pp-field-help">{{ L('MP4 · 最大 100 MB', 'MP4 · max 100 MB', 'MP4 · 最大100MB', 'MP4 · 최대 100MB', 'MP4 · máx 100 MB') }}</p>
        <video v-if="videoPreviewUrl" :src="videoPreviewUrl" class="w-full mt-2 rounded-lg" controls />
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '目標語言 *' : 'Target Language *' }}</label>
        <select v-model="targetLanguage" class="pp-select">
          <option v-for="l in LANGUAGES" :key="l.code" :value="l.code">
            {{ isZh ? l.labelZh : l.labelEn }}
          </option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '原始語言（選填，自動偵測）' : 'Source Language (optional, auto-detected)' }}</label>
        <select v-model="sourceLanguage" class="pp-select">
          <option value="">{{ isZh ? '自動偵測' : 'Auto-detect' }}</option>
          <option v-for="l in LANGUAGES" :key="l.code" :value="l.code">
            {{ isZh ? l.labelZh : l.labelEn }}
          </option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '原始腳本（至少填一個腳本欄位）' : 'Source Script (at least one script field required)' }}</label>
        <textarea v-model="sourceScript" rows="3" maxlength="4000" class="pp-textarea"
          :placeholder="isZh ? '若已有逐字稿，貼在這裡可加速處理。' : 'If you have the transcript, paste it here to skip ASR.'"></textarea>
        <p class="pp-field-help">{{ isZh ? '請至少填寫「原始腳本」或下方「翻譯後腳本」其中一項；ASR 自動辨識目前不可用。' : 'Provide either Source Script OR Translated Script below; automatic ASR transcription is currently unavailable.' }}</p>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '翻譯後腳本（選填，覆蓋自動翻譯）' : 'Translated Script (optional, overrides auto-translation)' }}</label>
        <textarea v-model="translatedScript" rows="3" maxlength="4000" class="pp-textarea"
          :placeholder="isZh ? '若已自行翻譯，貼在這裡會以此為準。' : 'If pre-translated, paste here to override auto-translation.'"></textarea>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '聲音參考音檔 URL（選填，啟用聲音複製）' : 'Voice Reference URL (optional, enables voice cloning)' }}</label>
        <input v-model="voiceReferenceUrl" type="url" maxlength="1000" class="pp-input"
          placeholder="https://…" />
        <p class="pp-field-help">{{ isZh ? '30 秒以內的乾淨單人音檔。' : '30-second clean single-speaker audio clip.' }}</p>
      </div>

      <p v-if="isDemoUser" class="pp-field-help" style="color: #fbbf24;">
        {{ isZh ? '訂閱後即可使用。' : 'Subscribe to use this tool.' }}
        <button @click="gotoPricing" class="underline ml-1">{{ isZh ? '查看方案' : 'View Plans' }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <video :src="resultUrl" class="max-w-full max-h-[520px] rounded-lg" controls />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_dub_${Date.now()}.mp4`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ isZh ? '下載' : 'Download' }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="video-dubbing" />
    </template>
  </PiapiPlayground>
</template>
