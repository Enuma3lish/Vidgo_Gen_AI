<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ArrowUpTrayIcon,
  CheckCircleIcon,
  PlayCircleIcon,
  SpeakerWaveIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
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
// 5-language inline picker — fixes ja/ko/es fall-through (BUG-017).
const { L } = useLocalized()
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
    ? L('配音結果', 'Dubbed Result', '吹き替え結果', '더빙 결과', 'Resultado de doblaje')
    : L('示範輸出', 'Example Output', 'デモ出力', '데모 출력', 'Salida de demo')
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

  processingMessage.value = L('正在上傳影片...', 'Uploading video...', '動画をアップロード中...', '동영상 업로드 중...', 'Subiendo video...')
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
  processingMessage.value = L('正在準備示範結果...', 'Preparing example result...', 'デモ結果を準備中...', '데모 결과 준비 중...', 'Preparando resultado de ejemplo...')
  await new Promise((resolve) => window.setTimeout(resolve, 500))
  resultVideo.value = selectedExample.value.resultUrl
  resultScript.value = scriptMode.value === 'translated'
    ? translatedScript.value
    : selectedExample.value.translatedScript
  uiStore.showSuccess(L('示範配音已準備好', 'Example dubbing is ready', 'デモ吹き替えが準備できました', '데모 더빙이 준비되었습니다', 'El doblaje de ejemplo está listo'))
}

async function handleDubbing() {
  if (!hasScript.value) {
    uiStore.showWarning(L('請輸入字幕或配音稿', 'Please enter a transcript or dubbing script', '字幕または吹き替え原稿を入力してください', '자막 또는 더빙 대본을 입력해 주세요', 'Introduce el transcript o guion de doblaje'))
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
      uiStore.showWarning(L('請先上傳影片', 'Please upload a video first', '先に動画をアップロードしてください', '먼저 동영상을 업로드해 주세요', 'Sube primero un video'))
      return
    }

    processingMessage.value = L('正在翻譯並產生配音影片...', 'Translating and generating dubbed video...', '翻訳して吹き替え動画を生成中...', '번역 및 더빙 동영상 생성 중...', 'Traduciendo y generando video doblado...')
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
        uiStore.showSuccess(L('示範預覽已準備好', 'Demo preview is ready', 'デモプレビューが準備できました', '데모 프리뷰가 준비되었습니다', 'La vista previa demo está lista'))
      } else {
        creditsStore.fetchBalance()
        uiStore.showSuccess(L('影片翻譯配音完成', 'Video dubbing completed', '動画の翻訳吹き替えが完了しました', '동영상 더빙 완료', 'Doblaje de video completado'))
      }
    } else {
      uiStore.showError(result.message || L('影片配音失敗', 'Video dubbing failed', '動画の吹き替えに失敗', '동영상 더빙 실패', 'Falló el doblaje de video'))
    }
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.response?.data?.message || err?.message
    uiStore.showError(detail || L('影片配音失敗', 'Video dubbing failed', '動画の吹き替えに失敗', '동영상 더빙 실패', 'Falló el doblaje de video'))
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
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b; color: #f5f5fa;">
    <div class="max-w-6xl mx-auto px-4">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold mb-2" style="color: #f5f5fa;">
          {{ L('影片翻譯配音', 'Video Translation & Dubbing', '動画翻訳＆吹き替え', '동영상 번역 & 더빙', 'Traducción y doblaje de video') }}
        </h1>
        <p style="color: #9494b0;">
          {{ L('先用範例快速預覽，再替自己的影片產生正式配音。', 'Preview with a sample first, then generate dubbing for your own video.', 'まずサンプルでプレビュー、その後自分の動画で吹き替えを生成。', '먼저 샘플로 미리보기 후 본인 동영상으로 더빙 생성하세요.', 'Vista previa con una muestra, luego dobla tu propio video.') }}
        </p>
        <CreditCost :cost="30" class="mt-2" />
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ L('訂閱後可上傳自己的影片並下載結果', 'Subscribe to upload your own videos and download results', 'サブスク登録で動画アップロードと結果ダウンロードが可能', '구독하면 동영상 업로드 및 결과 다운로드 가능', 'Suscríbete para subir tu video y descargar resultados') }}
          </RouterLink>
        </div>
      </div>

      <HowToUseHint
        media-kind="video"
        :i18n-keys="[
          'howTo.video_dubbing.step1',
          'howTo.video_dubbing.step2',
          'howTo.video_dubbing.step3',
        ]"
      />

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Left column: examples + controls -->
        <div class="space-y-4">
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-3" style="color: #e8e8f0;">
              {{ L('選擇範例影片', 'Choose a sample video', 'サンプル動画を選択', '샘플 동영상 선택', 'Selecciona un video de muestra') }}
            </label>
            <div class="grid grid-cols-1 gap-2">
              <button
                v-for="example in demoExamples"
                :key="example.id"
                class="flex items-center justify-between gap-3 px-3 py-3 rounded-lg text-left transition-all"
                :style="selectedExampleId === example.id
                  ? 'background: rgba(22,119,255,0.12); border: 1px solid rgba(22,119,255,0.6); color: #f5f5fa;'
                  : 'background: #0d0d15; border: 1px solid rgba(255,255,255,0.08); color: #e8e8f0;'"
                @click="selectDemoExample(example)"
              >
                <span class="flex flex-col">
                  <strong class="text-sm">{{ exampleTitle(example) }}</strong>
                  <small style="color: #9494b0;">{{ exampleUseCase(example) }}</small>
                </span>
                <CheckCircleIcon v-if="selectedExampleId === example.id" class="w-5 h-5" style="color: #1677ff;" />
              </button>
            </div>
          </div>

          <div v-if="!isDemoUser" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-3" style="color: #e8e8f0;">
              {{ L('上傳自己的影片', 'Upload your own video', '自分の動画をアップロード', '본인 동영상 업로드', 'Sube tu propio video') }}
            </label>
            <label class="flex flex-col items-center justify-center gap-2 cursor-pointer rounded-lg py-6"
              style="border: 1px dashed rgba(255,255,255,0.18); background: #0d0d15;">
              <input type="file" accept=".mp4,.webm,.mov,video/mp4,video/webm,video/quicktime" class="sr-only" @change="handleVideoFile" />
              <ArrowUpTrayIcon class="w-7 h-7" style="color: #9494b0;" />
              <span class="text-sm font-medium" style="color: #e8e8f0;">{{ L('上傳影片', 'Upload Video', '動画をアップロード', '동영상 업로드', 'Subir video') }}</span>
              <small style="color: #6b6b8a;">MP4, WebM, MOV · 20MB</small>
            </label>
            <button v-if="hasCustomVideo" class="mt-2 inline-flex items-center gap-1 text-xs hover:underline" style="color: #9494b0;" @click="clearVideo()">
              <XMarkIcon class="w-3 h-3" />
              {{ L('改用範例', 'Use sample instead', 'サンプルを使用', '샘플 사용', 'Usar muestra') }}
            </button>
          </div>

          <div class="rounded-xl p-4 space-y-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ L('來源語言', 'Source Language', 'ソース言語', '소스 언어', 'Idioma origen') }}</label>
                <select v-model="sourceLanguage" class="control-select">
                  <option value="Auto">{{ L('自動偵測', 'Auto detect', '自動検出', '자동 감지', 'Detección automática') }}</option>
                  <option v-for="option in languageOptions" :key="option.value" :value="option.value">{{ languageLabel(option) }}</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ L('配音語言', 'Dubbing Language', '吹き替え言語', '더빙 언어', 'Idioma de doblaje') }}</label>
                <select v-model="targetLanguage" class="control-select">
                  <option v-for="option in languageOptions" :key="option.value" :value="option.value">{{ languageLabel(option) }}</option>
                </select>
              </div>
            </div>

            <div>
              <div class="flex items-center justify-between mb-2">
                <label class="block text-sm font-medium" style="color: #e8e8f0;">{{ L('配音內容', 'Dubbing Copy', '吹き替え原稿', '더빙 원고', 'Texto de doblaje') }}</label>
                <div class="inline-flex rounded-lg p-1" style="background: #0d0d15; border: 1px solid rgba(255,255,255,0.08);">
                  <button
                    type="button"
                    class="px-3 py-1 rounded-md text-xs font-medium transition-colors"
                    :style="scriptMode === 'translate' ? 'background: #1677ff; color: white;' : 'color: #9494b0;'"
                    @click="scriptMode = 'translate'"
                  >
                    {{ L('原文翻譯', 'Translate', '原文翻訳', '원문 번역', 'Traducir') }}
                  </button>
                  <button
                    type="button"
                    class="px-3 py-1 rounded-md text-xs font-medium transition-colors"
                    :style="scriptMode === 'translated' ? 'background: #1677ff; color: white;' : 'color: #9494b0;'"
                    @click="scriptMode = 'translated'"
                  >
                    {{ L('直接配音', 'Ready Copy', 'そのまま吹き替え', '바로 더빙', 'Texto listo') }}
                  </button>
                </div>
              </div>
              <textarea
                v-if="scriptMode === 'translate'"
                v-model="sourceScript"
                rows="4"
                class="control-textarea"
                :placeholder="L('貼上原文字幕或旁白稿', 'Paste the original transcript or narration copy', '原文の字幕またはナレーション原稿を貼り付け', '원문 자막 또는 내레이션 원고를 붙여넣으세요', 'Pega el transcript o narración original')"
              />
              <textarea
                v-else
                v-model="translatedScript"
                rows="4"
                class="control-textarea"
                :placeholder="L('貼上已翻譯完成、要直接配音的文字', 'Paste the translated copy to speak directly', '翻訳済みの吹き替え用テキストを貼り付け', '번역 완료된 더빙용 텍스트를 붙여넣으세요', 'Pega el texto traducido para doblar directamente')"
              />
            </div>

            <div>
              <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">
                {{ L('參考聲音 (選填)', 'Reference Voice (optional)', '参考音声（任意）', '참고 음성 (선택)', 'Voz de referencia (opcional)') }}
              </label>
              <input
                v-model="voiceReferenceUrl"
                class="control-select"
                :placeholder="L('參考聲音音檔 URL', 'Reference voice audio URL', '参考音声ファイルURL', '참고 음성 파일 URL', 'URL del audio de referencia')"
              />
            </div>
          </div>

          <button
            @click="handleDubbing"
            :disabled="!canGenerate"
            class="w-full py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-50 inline-flex items-center justify-center gap-2"
            style="background: #1677ff;"
          >
            <PlayCircleIcon class="w-5 h-5" />
            {{ isProcessing
              ? L('處理中...', 'Processing...', '処理中...', '처리 중...', 'Procesando...')
              : (hasCustomVideo
                  ? L('產生配音影片', 'Generate Dubbed Video', '吹き替え動画を生成', '더빙 동영상 생성', 'Generar video doblado')
                  : L('產生範例配音', 'Generate Example', 'デモ吹き替えを生成', '데모 더빙 생성', 'Generar ejemplo')) }}
          </button>
        </div>

        <!-- Right column: video preview + result -->
        <div class="space-y-4">
          <div class="rounded-xl p-4 relative" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <LoadingOverlay :show="isProcessing" :message="processingMessage || L('正在產生配音影片...', 'Generating dubbed video...', '吹き替え動画を生成中...', '더빙 동영상 생성 중...', 'Generando video doblado...')" />
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">
              {{ hasCustomVideo ? L('你的影片', 'Your Video', 'あなたの動画', '내 동영상', 'Tu video') : exampleTitle(selectedExample) }}
            </label>
            <video :src="activeVideoPreview" controls muted class="w-full rounded-lg" style="max-height: 300px; background: #000;" />
          </div>

          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ resultPanelTitle }}</label>
            <video
              :src="activeResultPreview"
              controls
              class="w-full rounded-lg"
              :style="resultVideo ? 'background: #000;' : 'background: #000; opacity: 0.6;'"
            />
            <div v-if="activeScriptPreview" class="mt-3 rounded-lg p-3" style="background: #0d0d15; border: 1px solid rgba(255,255,255,0.06);">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-semibold" style="color: #9494b0;">
                  {{ L('配音稿預覽', 'Dubbing Script Preview', '吹き替え原稿プレビュー', '더빙 원고 미리보기', 'Vista previa del guion') }} · {{ targetLanguage }}
                </span>
                <button
                  type="button"
                  class="inline-flex items-center gap-1 text-xs hover:underline"
                  style="color: #1677ff;"
                  @click="isSpeakingPreview ? stopVoicePreview() : playVoicePreview()"
                >
                  <SpeakerWaveIcon class="w-3 h-3" />
                  {{ isSpeakingPreview ? L('停止', 'Stop', '停止', '정지', 'Detener') : L('播放聲音', 'Voice Preview', '音声プレビュー', '음성 미리보기', 'Vista previa de voz') }}
                </button>
              </div>
              <p class="text-sm leading-relaxed" style="color: #e8e8f0;">{{ activeScriptPreview }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.control-select,
.control-textarea {
  width: 100%;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.1);
  background: #0d0d15;
  color: #f5f5fa;
  padding: 10px 12px;
  font-size: 14px;
  outline: none;
}

.control-select:focus,
.control-textarea:focus {
  border-color: rgba(22,119,255,0.65);
  box-shadow: 0 0 0 3px rgba(22,119,255,0.12);
}

.control-textarea {
  resize: vertical;
  min-height: 96px;
}
</style>
