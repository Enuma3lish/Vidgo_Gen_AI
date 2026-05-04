<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ArrowUpTrayIcon,
  CheckCircleIcon,
  DocumentTextIcon,
  LanguageIcon,
  PlayCircleIcon,
  SpeakerWaveIcon,
  SparklesIcon,
  VideoCameraIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { toolsApi } from '@/api'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import HowToUseHint from '@/components/common/HowToUseHint.vue'
import { validateVideoFile } from '@/utils/mediaValidation'

interface DubbingExample {
  id: string
  titleEn: string
  titleZh: string
  useCaseEn: string
  useCaseZh: string
  sourceUrl: string
  resultUrl: string
  sourceLanguage: string
  targetLanguage: string
  sourceScript: string
  translatedScript: string
}

const demoExamples: DubbingExample[] = [
  {
    id: 'florist-launch',
    titleEn: 'Retail Product Launch',
    titleZh: '零售新品短片',
    useCaseEn: 'Product intro',
    useCaseZh: '商品介紹',
    sourceUrl: 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
    resultUrl: 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
    sourceLanguage: 'English',
    targetLanguage: 'Traditional Chinese',
    sourceScript: 'Meet our new seasonal bouquet. Fresh color, soft texture, and a natural look for every special moment.',
    translatedScript: '認識我們全新的季節花束。清新的色彩、柔和的質感，為每個特別時刻帶來自然優雅的氛圍。',
  },
  {
    id: 'travel-promo',
    titleEn: 'Travel Promo',
    titleZh: '旅遊宣傳短片',
    useCaseEn: 'Campaign voiceover',
    useCaseZh: '活動旁白',
    sourceUrl: 'https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4',
    resultUrl: 'https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4',
    sourceLanguage: 'English',
    targetLanguage: 'Traditional Chinese',
    sourceScript: 'Plan a short escape with a smoother itinerary, local experiences, and everything arranged before you arrive.',
    translatedScript: '安排一趟輕鬆小旅行，行程更順暢、體驗更在地，抵達前一切都已為你準備好。',
  },
  {
    id: 'brand-update',
    titleEn: 'Brand Update',
    titleZh: '品牌更新短片',
    useCaseEn: 'Social clip',
    useCaseZh: '社群短片',
    sourceUrl: 'https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4',
    resultUrl: 'https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4',
    sourceLanguage: 'English',
    targetLanguage: 'Traditional Chinese',
    sourceScript: 'A new update is here. Faster setup, cleaner visuals, and a more polished customer experience from start to finish.',
    translatedScript: '全新版本已經上線。設定更快速、畫面更清楚，從開始到完成都能提供更精緻的顧客體驗。',
  },
]

const languageOptions = [
  { value: 'Traditional Chinese', labelEn: 'Traditional Chinese', labelZh: '繁體中文' },
  { value: 'English', labelEn: 'English', labelZh: '英文' },
  { value: 'Japanese', labelEn: 'Japanese', labelZh: '日文' },
  { value: 'Korean', labelEn: 'Korean', labelZh: '韓文' },
  { value: 'Spanish', labelEn: 'Spanish', labelZh: '西班牙文' },
]

const { locale } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { isDemoUser } = useDemoMode()

const isZh = computed(() => locale.value.startsWith('zh'))
const selectedExampleId = ref(demoExamples[0].id)
const uploadedVideoFile = ref<File | null>(null)
const uploadedVideoPreview = ref<string | null>(null)
const uploadedVideoUrl = ref<string | null>(null)
const resultVideo = ref<string | null>(null)
const resultScript = ref<string | null>(null)
const isProcessing = ref(false)
const isSpeakingPreview = ref(false)
const processingMessage = ref('')
const targetLanguage = ref(demoExamples[0].targetLanguage)
const sourceLanguage = ref(demoExamples[0].sourceLanguage)
const scriptMode = ref<'translate' | 'translated'>('translate')
const sourceScript = ref(demoExamples[0].sourceScript)
const translatedScript = ref(demoExamples[0].translatedScript)
const voiceReferenceUrl = ref('')

const selectedExample = computed(() => (
  demoExamples.find((example) => example.id === selectedExampleId.value) || demoExamples[0]
))
const hasCustomVideo = computed(() => Boolean(uploadedVideoFile.value || uploadedVideoUrl.value))
const activeVideoPreview = computed(() => uploadedVideoPreview.value || selectedExample.value.sourceUrl)
const activeResultPreview = computed(() => resultVideo.value || selectedExample.value.resultUrl)
const hasScript = computed(() => (
  scriptMode.value === 'translated'
    ? translatedScript.value.trim().length > 0
    : sourceScript.value.trim().length > 0
))
const canGenerate = computed(() => !isProcessing.value && hasScript.value)
const resultPanelTitle = computed(() => (
  resultVideo.value
    ? (isZh.value ? '配音結果' : 'Dubbed Result')
    : (isZh.value ? '示範輸出' : 'Example Output')
))
const activeScriptPreview = computed(() => resultScript.value || translatedScript.value || selectedExample.value.translatedScript)

function languageLabel(option: { labelEn: string; labelZh: string }) {
  return isZh.value ? option.labelZh : option.labelEn
}

function exampleTitle(example: DubbingExample) {
  return isZh.value ? example.titleZh : example.titleEn
}

function exampleUseCase(example: DubbingExample) {
  return isZh.value ? example.useCaseZh : example.useCaseEn
}

function selectDemoExample(example: DubbingExample) {
  selectedExampleId.value = example.id
  sourceLanguage.value = example.sourceLanguage
  targetLanguage.value = example.targetLanguage
  sourceScript.value = example.sourceScript
  translatedScript.value = example.translatedScript
  resultVideo.value = null
  resultScript.value = null
  clearVideo(false)
}

function handleVideoFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const validationError = validateVideoFile(file, isZh.value, { maxSizeMb: 20 })
  if (validationError) {
    uiStore.showError(validationError)
    input.value = ''
    return
  }
  if (uploadedVideoPreview.value) {
    URL.revokeObjectURL(uploadedVideoPreview.value)
  }
  uploadedVideoFile.value = file
  uploadedVideoPreview.value = URL.createObjectURL(file)
  uploadedVideoUrl.value = null
  resultVideo.value = null
  resultScript.value = null
}

function clearVideo(resetResult = true) {
  uploadedVideoFile.value = null
  uploadedVideoUrl.value = null
  if (resetResult) {
    resultVideo.value = null
    resultScript.value = null
  }
  if (uploadedVideoPreview.value) {
    URL.revokeObjectURL(uploadedVideoPreview.value)
    uploadedVideoPreview.value = null
  }
}

async function resolveVideoUrl() {
  if (!hasCustomVideo.value) return selectedExample.value.sourceUrl
  if (uploadedVideoUrl.value) return uploadedVideoUrl.value
  if (!uploadedVideoFile.value) return null

  processingMessage.value = isZh.value ? '正在上傳影片...' : 'Uploading video...'
  const uploaded = await toolsApi.uploadFile(uploadedVideoFile.value)
  uploadedVideoUrl.value = uploaded.url
  return uploaded.url
}

function speechLanguage() {
  if (targetLanguage.value === 'Traditional Chinese') return 'zh-TW'
  if (targetLanguage.value === 'Japanese') return 'ja-JP'
  if (targetLanguage.value === 'Korean') return 'ko-KR'
  if (targetLanguage.value === 'Spanish') return 'es-ES'
  return 'en-US'
}

function playVoicePreview() {
  const text = activeScriptPreview.value.trim()
  if (!text || !('speechSynthesis' in window)) return

  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = speechLanguage()
  utterance.rate = 0.95
  utterance.onend = () => {
    isSpeakingPreview.value = false
  }
  utterance.onerror = () => {
    isSpeakingPreview.value = false
  }
  isSpeakingPreview.value = true
  window.speechSynthesis.speak(utterance)
}

function stopVoicePreview() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel()
  }
  isSpeakingPreview.value = false
}

async function showExampleResult() {
  processingMessage.value = isZh.value ? '正在準備示範結果...' : 'Preparing example result...'
  await new Promise((resolve) => window.setTimeout(resolve, 500))
  resultVideo.value = selectedExample.value.resultUrl
  resultScript.value = scriptMode.value === 'translated'
    ? translatedScript.value
    : selectedExample.value.translatedScript
  uiStore.showSuccess(isZh.value ? '示範配音已準備好' : 'Example dubbing is ready')
}

async function handleDubbing() {
  if (!hasScript.value) {
    uiStore.showWarning(isZh.value ? '請輸入字幕或配音稿' : 'Please enter a transcript or dubbing script')
    return
  }

  isProcessing.value = true
  resultVideo.value = null
  resultScript.value = null
  stopVoicePreview()
  try {
    if (!hasCustomVideo.value) {
      await showExampleResult()
      return
    }

    const videoUrl = await resolveVideoUrl()
    if (!videoUrl) {
      uiStore.showWarning(isZh.value ? '請先上傳影片' : 'Please upload a video first')
      return
    }

    processingMessage.value = isZh.value ? '正在翻譯並產生配音影片...' : 'Translating and generating dubbed video...'
    const result = await toolsApi.videoDubbing({
      videoUrl,
      targetLanguage: targetLanguage.value,
      sourceLanguage: sourceLanguage.value === 'Auto' ? undefined : sourceLanguage.value,
      sourceScript: scriptMode.value === 'translate' ? sourceScript.value : undefined,
      translatedScript: scriptMode.value === 'translated' ? translatedScript.value : undefined,
      voiceReferenceUrl: voiceReferenceUrl.value || undefined,
    })

    const video = result.result_url || result.video_url
    if (result.success && video) {
      resultVideo.value = video
      resultScript.value = result.translated_script || null
      if (isDemoUser.value) {
        uiStore.showSuccess(isZh.value ? '示範預覽已準備好' : 'Demo preview is ready')
      } else {
        creditsStore.fetchBalance()
        uiStore.showSuccess(isZh.value ? '影片翻譯配音完成' : 'Video dubbing completed')
      }
    } else {
      uiStore.showError(result.message || (isZh.value ? '影片配音失敗' : 'Video dubbing failed'))
    }
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.response?.data?.message || err?.message
    uiStore.showError(detail || (isZh.value ? '影片配音失敗' : 'Video dubbing failed'))
  } finally {
    isProcessing.value = false
    processingMessage.value = ''
  }
}

onBeforeUnmount(() => {
  stopVoicePreview()
  if (uploadedVideoPreview.value) {
    URL.revokeObjectURL(uploadedVideoPreview.value)
  }
})
</script>

<template>
  <div class="video-dubbing-page">
    <div class="tool-shell">
      <section class="tool-header">
        <div>
          <div class="eyebrow">
            <SparklesIcon class="icon-sm" />
            <span>{{ isZh ? 'AI 影片在地化' : 'AI Video Localization' }}</span>
          </div>
          <h1>{{ isZh ? '影片翻譯配音' : 'Video Translation & Dubbing' }}</h1>
          <p>{{ isZh ? '先用範例快速預覽，再替自己的影片產生正式配音。' : 'Preview with a sample first, then generate dubbing for your own video.' }}</p>
        </div>
        <div class="header-actions">
          <CreditCost :cost="35" />
          <RouterLink v-if="isDemoUser" to="/pricing" class="soft-link">
            {{ isZh ? '升級使用自己的影片' : 'Upgrade for your videos' }}
          </RouterLink>
        </div>
      </section>

      <HowToUseHint
        media-kind="video"
        :steps="[
          { en: 'Pick a sample video to preview the dubbing flow.', zh: '選示範影片以快速預覽配音流程。' },
          { en: 'Subscribers can upload their own MP4 / WebM / MOV.', zh: '訂閱用戶可上傳自己的 MP4 / WebM / MOV 影片。' },
          { en: 'Choose source / target language and click Generate Dubbing.', zh: '選擇來源 / 目標語言並點擊生成配音。' },
        ]"
      />

      <div class="workspace-grid">
        <aside class="left-rail">
          <section class="panel">
            <div class="panel-heading">
              <VideoCameraIcon class="icon-md" />
              <h2>{{ isZh ? '選擇範例' : 'Choose Example' }}</h2>
            </div>
            <div class="example-list">
              <button
                v-for="example in demoExamples"
                :key="example.id"
                class="example-option"
                :class="selectedExampleId === example.id ? 'example-option-active' : ''"
                @click="selectDemoExample(example)"
              >
                <span>
                  <strong>{{ exampleTitle(example) }}</strong>
                  <small>{{ exampleUseCase(example) }}</small>
                </span>
                <CheckCircleIcon v-if="selectedExampleId === example.id" class="icon-md" />
              </button>
            </div>
          </section>

          <section class="panel" :class="isDemoUser ? 'panel-muted' : ''">
            <div class="panel-heading">
              <ArrowUpTrayIcon class="icon-md" />
              <h2>{{ isZh ? '影片來源' : 'Video Source' }}</h2>
            </div>
            <div v-if="isDemoUser" class="subscription-note">
              {{ isZh ? '目前會使用上方範例影片。訂閱後可上傳自己的 MP4、WebM 或 MOV。' : 'This preview uses the selected sample. Subscribe to upload MP4, WebM, or MOV files.' }}
            </div>
            <div v-else class="upload-block">
              <label class="upload-zone">
                <input type="file" accept=".mp4,.webm,.mov,video/mp4,video/webm,video/quicktime" class="sr-only" @change="handleVideoFile" />
                <ArrowUpTrayIcon class="icon-lg" />
                <span>{{ isZh ? '上傳影片' : 'Upload Video' }}</span>
                <small>MP4, WebM, MOV · 20MB</small>
              </label>
              <button v-if="hasCustomVideo" class="text-button" @click="clearVideo()">
                <XMarkIcon class="icon-sm" />
                {{ isZh ? '改用範例' : 'Use sample instead' }}
              </button>
            </div>
          </section>

          <section class="panel">
            <div class="panel-heading">
              <LanguageIcon class="icon-md" />
              <h2>{{ isZh ? '語言' : 'Languages' }}</h2>
            </div>
            <div class="control-grid">
              <label>
                <span>{{ isZh ? '來源' : 'Source' }}</span>
                <select v-model="sourceLanguage" class="field-control">
                  <option value="Auto">{{ isZh ? '自動偵測' : 'Auto detect' }}</option>
                  <option v-for="option in languageOptions" :key="option.value" :value="option.value">
                    {{ languageLabel(option) }}
                  </option>
                </select>
              </label>
              <label>
                <span>{{ isZh ? '配音' : 'Dubbing' }}</span>
                <select v-model="targetLanguage" class="field-control">
                  <option v-for="option in languageOptions" :key="option.value" :value="option.value">
                    {{ languageLabel(option) }}
                  </option>
                </select>
              </label>
            </div>
          </section>
        </aside>

        <main class="main-stage">
          <section class="video-panel">
            <LoadingOverlay :show="isProcessing" :message="processingMessage || (isZh ? '正在產生配音影片...' : 'Generating dubbed video...')" />
            <div class="video-column">
              <div class="video-card">
                <div class="video-card-header">
                  <span>{{ hasCustomVideo ? (isZh ? '你的影片' : 'Your Video') : exampleTitle(selectedExample) }}</span>
                  <small>{{ hasCustomVideo ? (uploadedVideoFile?.name || '') : exampleUseCase(selectedExample) }}</small>
                </div>
                <video :src="activeVideoPreview" controls muted class="preview-video" />
              </div>
              <div class="video-card result-card">
                <div class="video-card-header">
                  <span>{{ resultPanelTitle }}</span>
                  <small>{{ resultVideo ? (isZh ? '已完成' : 'Ready') : (isZh ? '點擊產生後顯示' : 'Shown after generate') }}</small>
                </div>
                <video :src="activeResultPreview" controls class="preview-video" :class="resultVideo ? '' : 'soft-preview'" />
              </div>
            </div>

            <div v-if="activeScriptPreview" class="script-preview">
              <div class="script-preview-header">
                <div>
                  <span>{{ isZh ? '配音稿預覽' : 'Dubbing Script Preview' }}</span>
                  <small>{{ targetLanguage }}</small>
                </div>
                <button class="voice-button" type="button" @click="isSpeakingPreview ? stopVoicePreview() : playVoicePreview()">
                  <SpeakerWaveIcon class="icon-sm" />
                  {{ isSpeakingPreview ? (isZh ? '停止' : 'Stop') : (isZh ? '播放聲音' : 'Voice Preview') }}
                </button>
              </div>
              <p>{{ activeScriptPreview }}</p>
            </div>
          </section>

          <section class="script-panel">
            <div class="script-panel-header">
              <div class="panel-heading compact">
                <DocumentTextIcon class="icon-md" />
                <h2>{{ isZh ? '配音內容' : 'Dubbing Copy' }}</h2>
              </div>
              <div class="mode-tabs" role="tablist">
                <button
                  type="button"
                  :class="scriptMode === 'translate' ? 'mode-tab-active' : ''"
                  @click="scriptMode = 'translate'"
                >
                  {{ isZh ? '原文翻譯' : 'Translate' }}
                </button>
                <button
                  type="button"
                  :class="scriptMode === 'translated' ? 'mode-tab-active' : ''"
                  @click="scriptMode = 'translated'"
                >
                  {{ isZh ? '直接配音' : 'Ready Copy' }}
                </button>
              </div>
            </div>

            <textarea
              v-if="scriptMode === 'translate'"
              v-model="sourceScript"
              rows="5"
              class="script-textarea"
              :placeholder="isZh ? '貼上原文字幕或旁白稿' : 'Paste the original transcript or narration copy'"
            />
            <textarea
              v-else
              v-model="translatedScript"
              rows="5"
              class="script-textarea"
              :placeholder="isZh ? '貼上已翻譯完成、要直接配音的文字' : 'Paste the translated copy to speak directly'"
            />

            <div class="script-footer">
              <input
                v-model="voiceReferenceUrl"
                class="field-control voice-field"
                :placeholder="isZh ? '選填：參考聲音音檔 URL' : 'Optional reference voice audio URL'"
              />
              <button class="generate-button" type="button" :disabled="!canGenerate" @click="handleDubbing">
                <PlayCircleIcon class="icon-md" />
                {{ isProcessing ? (isZh ? '處理中' : 'Processing') : (hasCustomVideo ? (isZh ? '產生正式配音' : 'Generate Dubbed Video') : (isZh ? '產生範例' : 'Generate Example')) }}
              </button>
            </div>

            <RouterLink v-if="isDemoUser" to="/pricing" class="upgrade-strip">
              {{ isZh ? '訂閱後可上傳自己的影片、產生完整配音並下載結果。' : 'Subscribe to upload your own video, generate full dubbing, and download the result.' }}
            </RouterLink>
          </section>
        </main>
      </div>
    </div>
  </div>
</template>

<style scoped>
.video-dubbing-page {
  min-height: 100vh;
  padding: 96px 0 72px;
  background: #f6f7fb;
  color: #111827;
}

.tool-shell {
  width: min(1280px, calc(100% - 32px));
  margin: 0 auto;
}

.tool-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.tool-header h1 {
  margin: 10px 0 8px;
  color: #111827;
  font-size: clamp(32px, 4vw, 48px);
  letter-spacing: 0;
}

.tool-header p {
  max-width: 640px;
  color: #5b6475;
  font-size: 16px;
}

.eyebrow,
.soft-link,
.voice-button,
.text-button,
.upgrade-strip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.eyebrow {
  width: fit-content;
  border-radius: 999px;
  border: 1px solid #cfe0ff;
  background: #edf5ff;
  color: #1557b0;
  padding: 7px 12px;
  font-size: 13px;
  font-weight: 700;
}

.header-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.soft-link {
  min-height: 38px;
  border-radius: 8px;
  border: 1px solid #bfd6ff;
  background: #ffffff;
  color: #1557b0;
  padding: 8px 12px;
  font-size: 14px;
  font-weight: 700;
}

.workspace-grid {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.left-rail,
.main-stage {
  display: grid;
  gap: 16px;
}

.panel,
.video-panel,
.script-panel {
  border: 1px solid #dfe4ee;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
}

.panel {
  padding: 16px;
}

.panel-muted {
  background: #fbfcff;
}

.panel-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  color: #111827;
}

.panel-heading.compact {
  margin-bottom: 0;
}

.panel-heading h2 {
  color: #111827;
  font-size: 15px;
  font-weight: 800;
}

.example-list {
  display: grid;
  gap: 8px;
}

.example-option {
  display: flex;
  min-height: 70px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  padding: 12px;
  color: #111827;
  text-align: left;
  transition: border-color 0.18s ease, background 0.18s ease, box-shadow 0.18s ease;
}

.example-option strong,
.example-option small {
  display: block;
}

.example-option strong {
  font-size: 14px;
}

.example-option small,
.video-card-header small,
.script-preview-header small,
.upload-zone small {
  color: #6b7280;
  font-size: 12px;
}

.example-option:hover,
.example-option-active {
  border-color: #3b82f6;
  background: #f5f9ff;
  box-shadow: 0 8px 20px rgba(59, 130, 246, 0.12);
}

.subscription-note {
  border-radius: 8px;
  background: #f1f5f9;
  color: #475569;
  padding: 12px;
  font-size: 14px;
  line-height: 1.55;
}

.upload-block {
  display: grid;
  gap: 10px;
}

.upload-zone {
  display: flex;
  min-height: 126px;
  cursor: pointer;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px dashed #b8c4d8;
  border-radius: 8px;
  background: #f8fafc;
  color: #111827;
  transition: border-color 0.18s ease, background 0.18s ease;
}

.upload-zone:hover {
  border-color: #2563eb;
  background: #eff6ff;
}

.control-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.control-grid label {
  display: grid;
  gap: 6px;
  color: #475569;
  font-size: 13px;
  font-weight: 700;
}

.field-control,
.script-textarea {
  width: 100%;
  border: 1px solid #cfd8e6;
  border-radius: 8px;
  background: #ffffff;
  color: #111827;
  outline: none;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.field-control {
  min-height: 42px;
  padding: 9px 11px;
  font-size: 14px;
}

.script-textarea {
  min-height: 136px;
  resize: vertical;
  padding: 12px;
  font-size: 14px;
  line-height: 1.65;
}

.field-control:focus,
.script-textarea:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.video-panel {
  position: relative;
  padding: 16px;
}

.video-column {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 14px;
}

.video-card {
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #0f172a;
}

.video-card-header {
  display: flex;
  min-height: 52px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  background: #ffffff;
  padding: 10px 12px;
}

.video-card-header span {
  color: #111827;
  font-size: 14px;
  font-weight: 800;
}

.preview-video {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #0f172a;
  object-fit: contain;
}

.soft-preview {
  opacity: 0.72;
}

.script-preview {
  margin-top: 14px;
  border: 1px solid #dbe7d7;
  border-radius: 8px;
  background: #f6fbf4;
  padding: 14px;
}

.script-preview-header,
.script-panel-header,
.script-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.script-preview-header span {
  display: block;
  color: #14351f;
  font-size: 14px;
  font-weight: 800;
}

.script-preview p {
  margin-top: 10px;
  color: #1f2937;
  font-size: 14px;
  line-height: 1.7;
}

.voice-button,
.text-button {
  border: 0;
  border-radius: 8px;
  background: #ffffff;
  color: #166534;
  font-size: 13px;
  font-weight: 800;
}

.voice-button {
  min-height: 36px;
  padding: 8px 10px;
  border: 1px solid #bbd7bf;
}

.text-button {
  justify-content: center;
  color: #475569;
  padding: 8px;
}

.script-panel {
  padding: 16px;
}

.script-panel-header {
  margin-bottom: 12px;
}

.mode-tabs {
  display: inline-grid;
  grid-template-columns: 1fr 1fr;
  min-width: 240px;
  border: 1px solid #d7deea;
  border-radius: 8px;
  background: #f8fafc;
  padding: 3px;
}

.mode-tabs button {
  min-height: 34px;
  border-radius: 6px;
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
}

.mode-tab-active {
  background: #111827;
  color: #ffffff !important;
}

.script-footer {
  margin-top: 12px;
}

.voice-field {
  flex: 1;
}

.generate-button {
  display: inline-flex;
  min-height: 44px;
  min-width: 190px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: 8px;
  background: #2563eb;
  color: #ffffff;
  padding: 10px 16px;
  font-weight: 800;
  transition: background 0.18s ease, opacity 0.18s ease, transform 0.18s ease;
}

.generate-button:hover:not(:disabled) {
  background: #1d4ed8;
  transform: translateY(-1px);
}

.generate-button:disabled {
  cursor: not-allowed;
  opacity: 0.52;
}

.upgrade-strip {
  justify-content: center;
  width: 100%;
  margin-top: 12px;
  border: 1px solid #fed7aa;
  border-radius: 8px;
  background: #fff7ed;
  color: #9a3412;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 800;
  text-align: center;
}

.icon-sm {
  width: 16px;
  height: 16px;
  flex: 0 0 auto;
}

.icon-md {
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
}

.icon-lg {
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
}

@media (max-width: 1080px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .left-rail {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 820px) {
  .video-dubbing-page {
    padding-top: 84px;
  }

  .tool-header,
  .script-panel-header,
  .script-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .header-actions {
    align-items: flex-start;
  }

  .left-rail,
  .video-column,
  .control-grid {
    grid-template-columns: 1fr;
  }

  .mode-tabs,
  .generate-button {
    width: 100%;
  }
}
</style>