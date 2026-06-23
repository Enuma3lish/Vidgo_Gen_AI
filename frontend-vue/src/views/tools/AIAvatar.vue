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
import { useDemoMode, useLocalized, useExamplePrefill } from '@/composables'
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
// Backend voice-language enum is locked to en / zh-TW (see file header + server validator).
// ja/ko/es UI users default to 'en' voices — extending requires backend changes (out of scope).
const language = ref<Language>(isZh.value ? 'zh-TW' : 'en')
const script = ref('')
const voiceId = ref('')
const headshot = ref<string | undefined>(undefined)
const voices = ref<Array<{ id: string; name: string }>>([])

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)
// Demo only: both the EN and zh-TW pre-rendered videos for a script preset, so
// the visitor can watch both language versions.
const demoVideos = ref<Array<{ language: string; url: string }> | null>(null)
function langLabel(code: string): string {
  return String(code || '').toLowerCase().startsWith('zh') ? '中文 (zh-TW)' : 'English'
}

// Service availability — backend takes AI Avatar offline (GET /tools/availability)
// when its providers are down, rather than charging 300 credits for a degraded
// render. When offline we block the page: redirect away + disable generation.
const available = ref(true)
async function checkAvailability() {
  try {
    const resp = await apiClient.get('/api/v1/tools/availability')
    available.value = resp.data?.ai_avatar !== false
  } catch { available.value = true /* fail-open: don't block on a transient error */ }
  if (!available.value) {
    uiStore.showError(L(
      'AI 虛擬主播正在升級影片引擎,暫時無法使用,且不會扣點。請稍後再試。',
      'AI Avatar is temporarily unavailable while we upgrade the video engine (no credits charged). Please check back soon.',
      'AIアバターは動画エンジンのアップグレード中で一時的に利用できません(課金なし)。',
      'AI 아바타는 동영상 엔진 업그레이드로 일시적으로 사용할 수 없습니다(요금 미청구).',
      'AI Avatar no está disponible temporalmente mientras actualizamos el motor de vídeo (sin cargo).',
    ))
    router.replace('/tools')
  }
}

const disabled = computed(() => !available.value || !headshot.value || !script.value.trim() || script.value.trim().length < 5)
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

// Gallery deeplink — the avatar tool consumes a headshot image and a script,
// so map ?image → headshot and ?prompt → script when present.
useExamplePrefill({
  onImage: (url) => { headshot.value = url },
  onPrompt: (p) => { script.value = p },
  onError: () => uiStore.showError(L(
    '範例素材已過期,請改用其他範例或上傳自有圖片。',
    'This example is no longer available. Pick another or upload your own image.',
    'この例は利用できなくなりました。別の例を選ぶか、画像をアップロードしてください。',
    '이 예제는 더 이상 사용할 수 없습니다. 다른 예제를 선택하거나 이미지를 업로드하세요.',
    'Este ejemplo ya no está disponible. Elige otro o sube tu propia imagen.',
  )),
})

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
    // The endpoint returns a bare JSON array when a language is given (and a
    // {lang: [...]} dict otherwise), not {voices: [...]} — tolerate both so the
    // voice selector actually populates instead of staying permanently empty.
    const raw = resp.data
    const list = Array.isArray(raw) ? raw : (raw?.voices || raw?.[language.value] || [])
    voices.value = list.map((v: any) => ({ id: v.id, name: v.name || v.id }))
    if (!voiceId.value && voices.value[0]) voiceId.value = voices.value[0].id
  } catch (e) {
    console.warn('[avatar] voice list failed', e)
  }
}
onMounted(() => { checkAvailability(); loadVoices() })

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
  statusText.value = L('生成中…通常 2-5 分鐘', 'Generating… typically 2-5 min', '生成中…通常2〜5分', '생성 중… 보통 2-5분', 'Generando… normalmente 2-5 min')
  resultUrl.value = null
  demoVideos.value = null
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
      // Demo path returns both language videos — show them side by side.
      demoVideos.value = result.demo_videos && result.demo_videos.length > 1 ? result.demo_videos : null
      status.value = 'done'
      statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      uiStore.showError((result as any).message || (result as any).error || L('生成失敗', 'Failed', '生成に失敗しました', '생성 실패', 'Error al generar'))
    }
  } catch (e: any) {
    status.value = 'error'
    uiStore.showError(extractApiError(e, L('生成失敗', 'Failed', '生成に失敗しました', '생성 실패', 'Error al generar')))
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
    :title="L('AI 數位人 / 代言人', 'AI Avatar / Spokesperson', 'AIアバター / スポークスパーソン', 'AI 아바타 / 대변인', 'Avatar IA / Portavoz')"
    :subtitle="L(
      '上傳清晰正面照 + 撰寫腳本，AI 生成口型同步的講話影片。',
      'Upload a clear frontal headshot + write a script; AI generates a lip-synced talking video.',
      '正面の顔写真と台本をアップロードすると、AIがリップシンク動画を生成します。',
      '정면 사진과 스크립트를 업로드하면 AI가 립싱크 영상을 생성합니다.',
      'Sube una foto frontal y un guion; la IA genera un vídeo con labios sincronizados.'
    )"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="L('生成影片', 'Generate', '動画を生成', '영상 생성', 'Generar vídeo')"
    :generate-label-running="L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…')"
    :disabled="disabled"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ L('模型 *', 'Model *', 'モデル *', '모델 *', 'Modelo *') }}</label>
        <select class="pp-select" disabled>
          <option>{{ L('Vidgo 數位人模型（口型同步 + 語音合成）', 'Vidgo Avatar Model (lip-sync + voice synthesis)', 'Vidgoアバターモデル（リップシンク + 音声合成）', 'Vidgo 아바타 모델 (립싱크 + 음성합성)', 'Modelo Vidgo Avatar (sincronización labial + síntesis de voz)') }}</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ L('任務類型 *', 'Task Type *', 'タスクタイプ *', '작업 유형 *', 'Tipo de tarea *') }}</label>
        <select class="pp-select" disabled>
          <option>avatar · talking head</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ L('正面照 *', 'Frontal Headshot *', '正面写真 *', '정면 사진 *', 'Foto frontal *') }}</label>

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
            <!-- SAMPLE_HEADSHOTS labels only have .zh / .en — ja/ko/es fall through to English (data shape, out of scope). -->
            <img :src="s.url" :alt="isZh ? s.label.zh : s.label.en" />
          </button>
        </div>
        <p class="pp-field-help" style="margin-bottom: 6px;">
          {{ L('點選範例頭像或上傳你自己的照片。', 'Click a sample headshot or upload your own.', 'サンプル画像を選ぶか、ご自身の写真をアップロードしてください。', '샘플 사진을 선택하거나 직접 업로드하세요.', 'Elige una foto de muestra o sube la tuya.') }}
        </p>

        <ImageUploader
          tool-type="ai_avatar"
          v-model="headshot"
          :label="L('清晰正面照（避免側臉、戴墨鏡）', 'Clear frontal photo (avoid profile / sunglasses)', '正面写真（横顔・サングラスは避ける）', '정면 사진 (측면 / 선글라스 피하기)', 'Foto frontal nítida (sin perfil ni gafas)')"
        />
      </div>

      <div>
        <label class="pp-field-label">{{ L('語言 *', 'Language *', '言語 *', '언어 *', 'Idioma *') }}</label>
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
        <label class="pp-field-label">{{ L('聲音', 'Voice', '声', '음성', 'Voz') }}</label>
        <select v-model="voiceId" class="pp-select">
          <option v-for="v in voices" :key="v.id" :value="v.id">{{ v.name }}</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ L('腳本 *', 'Script *', '台本 *', '스크립트 *', 'Guion *') }}</label>

        <!-- Script preset picker — sources from prompt_library.json's
             `ai_avatar` topic (spokesperson / product intro / customer
             service / social media / tutorial / greeting). Same flagship
             pattern KlingVideo / ProductSceneClassic adopted. -->
        <div v-if="scriptPresetOptions.length > 0" class="mb-2">
          <select v-model="selectedScriptPresetId" @change="applyScriptPreset" class="pp-select">
            <option value="">{{ L('— 選擇腳本範例（一鍵填入）—', '— Pick a script preset (one-click fill) —', '— 台本プリセットを選択（ワンクリック入力）—', '— 스크립트 프리셋 선택 (원클릭 입력) —', '— Elige un guion predefinido (un clic) —') }}</option>
            <option v-for="opt in scriptPresetOptions" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
          </select>
        </div>

        <textarea v-model="script" rows="6" maxlength="2000" class="pp-textarea"
          :placeholder="L('例：嗨大家好！今天要為你介紹我們剛上架的新品…', 'e.g. Hi everyone! Today I want to introduce our brand-new product…', '例：こんにちは！今日は新発売の商品をご紹介します…', '예: 안녕하세요! 오늘은 새로 출시된 제품을 소개합니다…', 'Ej: ¡Hola a todos! Hoy presento nuestro nuevo producto…')"></textarea>
        <p class="pp-field-help">{{ L('最少 5 個字，最多 2000 個字。zh-TW 語言下需含中文字。', 'Min 5 chars, max 2000. When zh-TW is picked, script must contain Chinese characters.', '最少5文字、最大2000文字。zh-TW選択時は中国語の文字が必要です。', '최소 5자, 최대 2000자. zh-TW 선택 시 중국어 문자가 필요합니다.', 'Mín. 5 caracteres, máx. 2000. Con zh-TW, el guion debe incluir caracteres chinos.') }}</p>
      </div>

      <p v-if="isDemoUser" class="pp-field-help" style="color: #fbbf24;">
        {{ L(
          '免費帳號可用範例腳本下拉選單一鍵生成；自訂腳本需訂閱並綁定信用卡。',
          'Free accounts can generate from the example scripts; custom scripts require a subscription with a bound card.',
          '無料アカウントはサンプル台本から生成可能。カスタム台本はカード登録の有料プランが必要です。',
          '무료 계정은 샘플 스크립트로 생성 가능. 커스텀 스크립트는 카드 등록 구독이 필요합니다.',
          'Las cuentas gratuitas pueden generar con guiones de ejemplo; los guiones personalizados requieren suscripción con tarjeta.'
        ) }}
        <button @click="gotoPricing" class="underline ml-1">{{ L('查看方案', 'View Plans', 'プランを見る', '요금제 보기', 'Ver planes') }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <!-- Demo: both EN + zh-TW versions of the preset, side by side. -->
      <div v-if="demoVideos" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div v-for="v in demoVideos" :key="v.language">
          <div class="text-xs mb-1 text-dark-400">{{ langLabel(v.language) }}</div>
          <video :src="v.url" class="max-w-full max-h-[420px] rounded-lg" controls />
        </div>
      </div>
      <video v-else :src="resultUrl" class="max-w-full max-h-[520px] rounded-lg" controls />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_avatar_${Date.now()}.mp4`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載', 'Download', 'ダウンロード', '다운로드', 'Descargar') }}</button>
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
