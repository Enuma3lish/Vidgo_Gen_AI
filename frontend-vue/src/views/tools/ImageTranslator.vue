<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { toolsApi } from '@/api'
import ImageUploader from '@/components/common/ImageUploader.vue'
import HowToUseHint from '@/components/common/HowToUseHint.vue'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'

const { locale } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { isDemoUser } = useDemoMode()

const isZh = computed(() => locale.value.startsWith('zh'))
// 5-language inline picker — fixes ja/ko/es fall-through (BUG-017).
const { L } = useLocalized()
const uploadedImage = ref<string | undefined>(undefined)
const resultImage = ref<string | undefined>(undefined)
const sourceLanguage = ref('Auto')
const targetLanguage = ref('Traditional Chinese')
// Curated tone presets — replaces the previous free-text textarea so the
// model gets a tightly bounded instruction (lower hallucination risk).
const TONE_PRESETS = [
  { id: 'tw_ecommerce', labelEn: 'Taiwan e-commerce tone (default)', labelZh: '台灣電商語氣（預設）',
    text: 'Use a friendly Taiwan e-commerce tone. Keep brand names, model numbers and prices unchanged. Preserve the original layout, fonts and colors of the source image as closely as possible.' },
  { id: 'formal_business', labelEn: 'Formal business', labelZh: '正式商務',
    text: 'Use a formal business tone. Keep all proper nouns, brand names and numerical values exactly. Preserve the original visual layout.' },
  { id: 'casual_social', labelEn: 'Casual social-media', labelZh: '社群口語',
    text: 'Use a casual, conversational social-media tone suitable for Instagram or TikTok. Keep brand names and prices unchanged.' },
  { id: 'tech_marketing', labelEn: 'Tech / product marketing', labelZh: '3C / 產品行銷',
    text: 'Use a clear, benefit-led product-marketing tone. Keep technical specifications, model numbers and units unchanged.' },
  { id: 'food_menu', labelEn: 'Food & beverage menu', labelZh: '餐飲菜單',
    text: 'Translate as a food & beverage menu. Keep dish names, prices and currency symbols unchanged. Use Traditional Chinese conventions for serving sizes when applicable.' },
  { id: 'literal_only', labelEn: 'Literal translation only', labelZh: '僅直譯',
    text: 'Translate the visible text literally with no localization or rewriting. Preserve all numbers, brand names and proper nouns.' },
]
const selectedToneId = ref('tw_ecommerce')
const instructions = computed(() => TONE_PRESETS.find(t => t.id === selectedToneId.value)?.text || '')
const isProcessing = ref(false)

const languageOptions = [
  { value: 'Traditional Chinese', labelEn: 'Traditional Chinese', labelZh: '繁體中文' },
  { value: 'English', labelEn: 'English', labelZh: '英文' },
  { value: 'Japanese', labelEn: 'Japanese', labelZh: '日文' },
  { value: 'Korean', labelEn: 'Korean', labelZh: '韓文' },
  { value: 'Spanish', labelEn: 'Spanish', labelZh: '西班牙文' },
]

// Curated demo images — each guaranteed to contain readable English text so
// the translator has something to actually OCR + translate. The previous
// Unsplash photos were inconsistent (lifestyle shots with little or no
// readable text), which made the translator look broken on the demo path.
const demoExamples = [
  {
    id: 'sale-card-en',
    labelEn: 'Sale card (EN → ZH)',
    labelZh: '促銷卡片（英→中）',
    url: 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/demos/image-translator/text-sale-card-en.png',
  },
  {
    id: 'menu-board-en',
    labelEn: 'Cafe menu board (EN → ZH/JA)',
    labelZh: '咖啡廳菜單（英→中／日）',
    url: 'https://placehold.co/1200x720/f8fafc/111827/png?text=Today%27s+Menu%0AAmericano+%24120%0ALatte+%24140%0AMatcha+%24150',
  },
  {
    id: 'event-poster-en',
    labelEn: 'Event poster (EN → ZH)',
    labelZh: '活動海報（英→中）',
    url: 'https://placehold.co/900x1200/c41e3a/ffffff/png?text=NEW+OPENING%0AOct+5+%E2%80%93+12%0A20%25+OFF+ALL+ITEMS',
  },
]

function languageLabel(option: { labelEn: string; labelZh: string }) {
  return isZh.value ? option.labelZh : option.labelEn
}

function selectDemoExample(example: { url: string }) {
  uploadedImage.value = example.url
  resultImage.value = undefined
}

async function handleTranslate() {
  if (!uploadedImage.value) {
    uiStore.showWarning(L('請先選擇或上傳圖片', 'Please select or upload an image first', '先に画像を選択またはアップロードしてください', '먼저 이미지를 선택하거나 업로드해 주세요', 'Selecciona o sube primero una imagen'))
    return
  }

  isProcessing.value = true
  resultImage.value = undefined
  try {
    const result = await toolsApi.imageTranslate({
      imageUrl: uploadedImage.value,
      targetLanguage: targetLanguage.value,
      sourceLanguage: sourceLanguage.value === 'Auto' ? undefined : sourceLanguage.value,
      instructions: instructions.value || undefined,
    })
    const imageUrl = result.result_url || result.image_url
    if (result.success && imageUrl) {
      resultImage.value = imageUrl
      if (isDemoUser.value) {
        uiStore.showSuccess(L('示範翻譯已完成', 'Demo translation is ready', 'デモ翻訳が完了しました', '데모 번역이 완료되었습니다', 'Traducción demo lista'))
      } else {
        creditsStore.fetchBalance()
        uiStore.showSuccess(L('圖片翻譯完成', 'Image translated successfully', '画像翻訳が完了しました', '이미지 번역 완료', 'Imagen traducida correctamente'))
      }
    } else {
      uiStore.showError(result.message || L('圖片翻譯失敗', 'Image translation failed', '画像翻訳に失敗', '이미지 번역 실패', 'Falló la traducción de imagen'))
    }
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.response?.data?.message || err?.message
    uiStore.showError(detail || L('圖片翻譯失敗', 'Image translation failed', '画像翻訳に失敗', '이미지 번역 실패', 'Falló la traducción de imagen'))
  } finally {
    isProcessing.value = false
  }
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b; color: #f5f5fa;">
    <div class="max-w-6xl mx-auto px-4">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold mb-2" style="color: #f5f5fa;">{{ L('圖片翻譯', 'Image Translation', '画像翻訳', '이미지 번역', 'Traducción de imagen') }}</h1>
        <p style="color: #9494b0;">{{ L('保留原圖排版與商品細節，將圖片中的文字翻譯成目標語言。', 'Translate visible image text while preserving layout, product details, and visual style.', '元の画像のレイアウトと商品ディテールを保ったまま、画像内のテキストを目標言語に翻訳します。', '원본 이미지의 레이아웃과 제품 디테일을 유지하면서 이미지 내 텍스트를 목표 언어로 번역합니다.', 'Traduce el texto de la imagen conservando layout, detalles del producto y estilo visual.') }}</p>
        <CreditCost :cost="20" class="mt-2" />
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ L('訂閱後可上傳自己的圖片並下載結果', 'Subscribe to upload your own images and download results', 'サブスク登録で画像アップロードと結果ダウンロードが可能', '구독하면 본인 이미지 업로드 및 결과 다운로드 가능', 'Suscríbete para subir tus imágenes y descargar resultados') }}
          </RouterLink>
        </div>
      </div>

      <HowToUseHint
        media-kind="image"
        :i18n-keys="[
          'howTo.image_translator.step1',
          'howTo.image_translator.step2',
          'howTo.image_translator.step3',
        ]"
      />

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="space-y-4">
          <!-- Examples grid (shown to all users so they can see what the tool does) -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-3" style="color: #e8e8f0;">{{ L('選擇示範圖片', 'Try a demo image', 'デモ画像を試す', '데모 이미지 사용', 'Prueba una imagen demo') }}</label>
            <div class="grid grid-cols-2 gap-2">
              <button
                v-for="example in demoExamples"
                :key="example.id"
                @click="selectDemoExample(example)"
                class="aspect-video rounded-lg overflow-hidden border-2 transition-all"
                :style="uploadedImage === example.url ? 'border-color: #1677ff;' : 'border-color: rgba(255,255,255,0.08);'"
              >
                <img :src="example.url" :alt="languageLabel(example)" class="w-full h-full object-cover" />
              </button>
            </div>
          </div>

          <!-- Upload (subscribers only) -->
          <div v-if="!isDemoUser" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-3" style="color: #e8e8f0;">{{ L('或上傳自己的圖片', 'Or upload your own image', 'または自分の画像をアップロード', '또는 본인 이미지 업로드', 'O sube tu propia imagen') }}</label>
            <ImageUploader tool-type="image_translator" v-model="uploadedImage" />
          </div>

          <div v-if="uploadedImage" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ L('原始圖片', 'Original Image', '元画像', '원본 이미지', 'Imagen original') }}</label>
            <img :src="uploadedImage" class="w-full rounded-lg" style="max-height: 320px; object-fit: contain;" />
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
                <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ L('目標語言', 'Target Language', '目標言語', '목표 언어', 'Idioma destino') }}</label>
                <select v-model="targetLanguage" class="control-select">
                  <option v-for="option in languageOptions" :key="option.value" :value="option.value">{{ languageLabel(option) }}</option>
                </select>
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ L('翻譯語氣', 'Translation Tone', '翻訳トーン', '번역 톤', 'Tono de traducción') }}</label>
              <select v-model="selectedToneId" class="control-select">
                <option v-for="t in TONE_PRESETS" :key="t.id" :value="t.id">{{ isZh ? t.labelZh : t.labelEn }}</option>
              </select>
              <p class="mt-2 text-[11px] text-dark-500">
                {{ isZh
                  ? '為確保翻譯品質與一致性，目前僅提供精選語氣預設。'
                  : 'For consistent results, only curated tone presets are available.' }}
              </p>
            </div>
          </div>

          <button
            @click="handleTranslate"
            :disabled="isProcessing || !uploadedImage"
            class="w-full py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-50"
            style="background: #1677ff;"
          >
            {{ isProcessing ? L('翻譯中...', 'Translating...', '翻訳中...', '번역 중...', 'Traduciendo...') : L('開始圖片翻譯', 'Translate Image', '画像翻訳を開始', '이미지 번역 시작', 'Traducir imagen') }}
          </button>
        </div>

        <div class="rounded-xl p-4 flex items-center justify-center min-h-[460px] relative" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <LoadingOverlay :show="isProcessing" :message="L('正在翻譯圖片文字...', 'Translating image text...', '画像内テキストを翻訳中...', '이미지 텍스트 번역 중...', 'Traduciendo texto de la imagen...')" />
          <div v-if="!isProcessing && resultImage" class="w-full">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ L('翻譯結果', 'Translated Result', '翻訳結果', '번역 결과', 'Resultado traducido') }}</label>
            <img :src="resultImage" class="w-full rounded-lg" style="max-height: 520px; object-fit: contain;" />
            <a
              v-if="!isDemoUser"
              :href="resultImage"
              target="_blank"
              download
              class="block mt-3 text-center py-2 rounded-lg text-sm font-medium transition-colors"
              style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
            >
              {{ L('下載翻譯圖片', 'Download Image', '画像をダウンロード', '이미지 다운로드', 'Descargar imagen') }}
            </a>
            <RouterLink
              v-else
              to="/pricing"
              class="block mt-3 text-center py-2 rounded-lg text-sm font-medium transition-colors"
              style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
            >
              {{ L('訂閱以下載結果', 'Subscribe to download', 'サブスクでダウンロード', '구독으로 다운로드', 'Suscríbete para descargar') }}
            </RouterLink>
          </div>
          <div v-if="!isProcessing && !resultImage" class="text-center" style="color: #6b6b8a;">
            <div class="text-5xl mb-4">文</div>
            <p class="text-sm">{{ L('選擇圖片與語言後開始翻譯', 'Choose an image and language to translate', '画像と言語を選択して翻訳を開始', '이미지와 언어를 선택하여 번역', 'Elige imagen e idioma para traducir') }}</p>
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
  min-height: 88px;
}
</style>