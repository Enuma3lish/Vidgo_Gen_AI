<script setup lang="ts">
/**
 * AIAvatar — PiAPI-style playground (Deploy 4, 2026-05-24).
 *
 * Upload a clear frontal headshot + a script. Server generates a
 * lip-synced talking-head video via PiAPI Kling Avatar (with F5-TTS or
 * tts-1 fallback). Language locked to en / zh-TW (server-side validator).
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { usePromptLibrary } from '@/composables/usePromptLibrary'
import { toolsApi } from '@/api'
import apiClient from '@/api/client'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import { dataURItoBlob } from '@/utils/dataUri'
import { downloadAsset } from '@/utils/downloadAsset'
import { handleCardRequired } from '@/utils/toolGate'
import { extractApiError } from '@/utils/apiError'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const { isDemoUser } = useDemoMode()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

type Language = 'en' | 'zh-TW'
const language = ref<Language>(isZh.value ? 'zh-TW' : 'en')
const script = ref('')
const voiceId = ref('')
const headshot = ref<string | undefined>(undefined)
const voices = ref<Array<{ id: string; name: string }>>([])

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

const disabled = computed(() => !headshot.value || !script.value.trim() || script.value.trim().length < 5)
const creditCost = computed(() => 300)

// Sample headshot picker — added 2026-05-25. Cold users without a clean
// frontal portrait can't get past the upload gate; clicking one of these
// short-circuits to a known-good test image hosted in GCS
// (gs://vidgo-media-vidgo-ai/static/avatars/{female,male}-{1,2,3}.png).
// The URL is set directly on `headshot.value`, which `ensureImageUrl()`
// passes through unchanged when it isn't a data: URI.
const SAMPLE_HEADSHOTS = [
  { id: 'female-1', url: 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/avatars/female-1.png', label: { zh: '女性 A', en: 'Female A' } },
  { id: 'female-2', url: 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/avatars/female-2.png', label: { zh: '女性 B', en: 'Female B' } },
  { id: 'female-3', url: 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/avatars/female-3.png', label: { zh: '女性 C', en: 'Female C' } },
  { id: 'male-1',   url: 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/avatars/male-1.png',   label: { zh: '男性 A', en: 'Male A' } },
  { id: 'male-2',   url: 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/avatars/male-2.png',   label: { zh: '男性 B', en: 'Male B' } },
  { id: 'male-3',   url: 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/avatars/male-3.png',   label: { zh: '男性 C', en: 'Male C' } },
]
function pickSampleHeadshot(url: string) { headshot.value = url }

// Curated script library (`ai_avatar` topic in prompt_library.json).
// Same flagship-tool pattern KlingVideo / ProductSceneClassic use.
// Each preset auto-fills the script textarea on selection so cold users
// don't stare at an empty box.
const { options: scriptPresetOptions, promptFor: scriptPresetPromptFor } = usePromptLibrary('ai_avatar')
const selectedScriptPresetId = ref('')
function applyScriptPreset() {
  if (!selectedScriptPresetId.value) return
  script.value = scriptPresetPromptFor(selectedScriptPresetId.value)
}
// Locale switch re-fetches the preset in the user's display language
// so they don't see a stale zh/en mismatch in the textarea.
watch(locale, () => {
  if (selectedScriptPresetId.value) script.value = scriptPresetPromptFor(selectedScriptPresetId.value)
})

// Editing the script away from the chosen preset clears the preset id, so a
// custom script is gated (subscription + bound card) while an unmodified
// preset stays free.
watch(script, (val) => {
  if (selectedScriptPresetId.value && val.trim() !== scriptPresetPromptFor(selectedScriptPresetId.value).trim()) {
    selectedScriptPresetId.value = ''
  }
})
const usingScriptPreset = computed(() =>
  !!selectedScriptPresetId.value && script.value.trim() === scriptPresetPromptFor(selectedScriptPresetId.value).trim()
)

async function loadVoices() {
  try {
    const resp = await apiClient.get(`/api/v1/tools/avatar/voices?language=${language.value}`)
    voices.value = (resp.data?.voices || []).map((v: any) => ({ id: v.id, name: v.name || v.id }))
    if (!voiceId.value && voices.value[0]) voiceId.value = voices.value[0].id
  } catch (e) {
    console.warn('[avatar] voice list failed', e)
  }
}
onMounted(loadVoices)

async function ensureImageUrl(): Promise<string | null> {
  if (!headshot.value) return null
  if (!headshot.value.startsWith('data:')) return headshot.value
  const blob = dataURItoBlob(headshot.value)
  if (!blob) return null
  const up = await toolsApi.uploadImage(blob as File)
  return up.url
}

async function generate() {
  if (disabled.value || status.value === 'running') return
  // Backend governs access: a free account using an unmodified preset script
  // gets the cached example; a custom script returns
  // 'subscription_card_required', handled below.
  status.value = 'running'
  statusText.value = isZh.value ? '生成中…通常 2-5 分鐘' : 'Generating… typically 2-5 min'
  resultUrl.value = null
  try {
    const url = await ensureImageUrl()
    if (!url) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }
    const result = await toolsApi.avatar({
      image_url: url,
      script: script.value.trim(),
      voice_id: voiceId.value || undefined,
      language: language.value,
      prompt_id: usingScriptPreset.value ? selectedScriptPresetId.value : undefined,
      locale: String(locale.value || ''),
    })
    if (handleCardRequired(result, uiStore, router, isZh.value)) {
      status.value = 'idle'
      return
    }
    if (result.success && (result.video_url || result.result_url)) {
      resultUrl.value = result.video_url || result.result_url || null
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

function pickLanguage(next: Language) {
  language.value = next
  voiceId.value = ''
  loadVoices()
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="300"
    :title="isZh ? 'AI 數位人 / 代言人' : 'AI Avatar / Spokesperson'"
    :subtitle="isZh
      ? '上傳清晰正面照 + 撰寫腳本，AI 生成口型同步的講話影片（PiAPI Kling Avatar）。'
      : 'Upload a clear frontal headshot + write a script; AI generates a lip-synced talking video (PiAPI Kling Avatar).'"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="isZh ? '生成影片' : 'Generate'"
    :generate-label-running="isZh ? '生成中…' : 'Generating…'"
    :disabled="disabled"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ isZh ? '模型 *' : 'Model *' }}</label>
        <select class="pp-select" disabled>
          <option>PiAPI Kling Avatar (lip-sync + F5-TTS)</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '任務類型 *' : 'Task Type *' }}</label>
        <select class="pp-select" disabled>
          <option>avatar · talking head</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '正面照 *' : 'Frontal Headshot *' }}</label>

        <!-- Sample headshot grid — added 2026-05-25. Visitors without a
             portrait can click one to instantly populate the input.
             The selected sample's URL replaces any earlier upload.
             Clicking the cleared state (ImageUploader's X button) resets
             headshot.value to undefined and these tiles become the only
             way to fill the field without an upload. -->
        <div class="grid grid-cols-6 gap-1.5 mb-2">
          <button
            v-for="s in SAMPLE_HEADSHOTS"
            :key="s.id"
            type="button"
            @click="pickSampleHeadshot(s.url)"
            class="headshot-tile"
            :class="{ 'is-active': headshot === s.url }"
            :title="isZh ? s.label.zh : s.label.en"
          >
            <img :src="s.url" :alt="isZh ? s.label.zh : s.label.en" />
          </button>
        </div>
        <p class="pp-field-help" style="margin-bottom: 6px;">
          {{ isZh ? '點選範例頭像或上傳你自己的照片。' : 'Click a sample headshot or upload your own.' }}
        </p>

        <ImageUploader
          tool-type="ai_avatar"
          v-model="headshot"
          :label="isZh ? '清晰正面照（避免側臉、戴墨鏡）' : 'Clear frontal photo (avoid profile / sunglasses)'"
        />
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '語言 *' : 'Language *' }}</label>
        <div class="grid grid-cols-2 gap-1.5">
          <button v-for="opt in [
            { id: 'zh-TW' as const, label: '繁體中文' },
            { id: 'en' as const,    label: 'English' },
          ]" :key="opt.id" type="button" @click="pickLanguage(opt.id)"
            class="py-2 rounded text-xs font-medium"
            :style="language === opt.id
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color: #fff;'
              : 'background: #0a0a0f; color: #94949f; border: 1px solid rgba(255,255,255,0.08);'"
          >{{ opt.label }}</button>
        </div>
      </div>

      <div v-if="voices.length > 0">
        <label class="pp-field-label">{{ isZh ? '聲音' : 'Voice' }}</label>
        <select v-model="voiceId" class="pp-select">
          <option v-for="v in voices" :key="v.id" :value="v.id">{{ v.name }}</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '腳本 *' : 'Script *' }}</label>

        <!-- Script preset picker — sources from prompt_library.json's
             `ai_avatar` topic (spokesperson / product intro / customer
             service / social media / tutorial / greeting). Same flagship
             pattern KlingVideo / ProductSceneClassic adopted. -->
        <div v-if="scriptPresetOptions.length > 0" class="mb-2">
          <select v-model="selectedScriptPresetId" @change="applyScriptPreset" class="pp-select">
            <option value="">{{ isZh ? '— 選擇腳本範例（一鍵填入）—' : '— Pick a script preset (one-click fill) —' }}</option>
            <option v-for="opt in scriptPresetOptions" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
          </select>
        </div>

        <textarea v-model="script" rows="6" maxlength="2000" class="pp-textarea"
          :placeholder="isZh ? '例：嗨大家好！今天要為你介紹我們剛上架的新品…' : 'e.g. Hi everyone! Today I want to introduce our brand-new product…'"></textarea>
        <p class="pp-field-help">{{ isZh ? '最少 5 個字，最多 2000 個字。zh-TW 語言下需含中文字。' : 'Min 5 chars, max 2000. When zh-TW is picked, script must contain Chinese characters.' }}</p>
      </div>

      <p v-if="isDemoUser" class="pp-field-help" style="color: #fbbf24;">
        {{ isZh
          ? '免費帳號可用範例腳本下拉選單一鍵生成；自訂腳本需訂閱並綁定信用卡。'
          : 'Free accounts can generate from the example scripts; custom scripts require a subscription with a bound card.' }}
        <button @click="gotoPricing" class="underline ml-1">{{ isZh ? '查看方案' : 'View Plans' }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <video :src="resultUrl" class="max-w-full max-h-[520px] rounded-lg" controls />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_avatar_${Date.now()}.mp4`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ isZh ? '下載' : 'Download' }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="ai-avatar" />
    </template>
  </PiapiPlayground>
</template>

<style scoped>
/* Sample-headshot picker tiles. Square thumbnails in a 6-column grid;
   active tile gets the violet brand glow that matches the rest of the
   playground accents. */
.headshot-tile {
  position: relative;
  aspect-ratio: 1 / 1;
  border-radius: 8px;
  overflow: hidden;
  border: 1.5px solid rgba(255, 255, 255, 0.08);
  background: #0a0a0f;
  transition: border-color 0.15s ease, transform 0.15s ease;
  padding: 0;
  cursor: pointer;
}
.headshot-tile:hover {
  border-color: rgba(167, 139, 250, 0.55);
  transform: translateY(-1px);
}
.headshot-tile.is-active {
  border-color: #a78bfa;
  box-shadow: 0 0 0 2px rgba(167, 139, 250, 0.30);
}
.headshot-tile img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
</style>
