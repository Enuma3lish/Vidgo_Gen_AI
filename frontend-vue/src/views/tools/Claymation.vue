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
import { toolsApi } from '@/api'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import { dataURItoBlob } from '@/utils/dataUri'
import { downloadAsset } from '@/utils/downloadAsset'
import { handleCardRequired } from '@/utils/toolGate'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const { isDemoUser } = useDemoMode()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

// video_to_video mode removed 2026-05-31 (V2V dropped repo-wide).
type Mode = 'text_to_image' | 'image_to_image' | 'text_to_video'

const mode = ref<Mode>('text_to_image')
const prompt = ref('')
const aspectRatio = ref<'1:1' | '16:9' | '9:16' | '4:3' | '3:4'>('1:1')
const imageInput = ref<string | undefined>(undefined)   // data URI from ImageUploader

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)
const resultKind = ref<'image' | 'video'>('image')

const isVideoMode = computed(() => mode.value === 'text_to_video')
const needsImage = computed(() => mode.value === 'image_to_image')

const disabled = computed(() => {
  if (!prompt.value.trim()) return true
  if (needsImage.value && !imageInput.value) return true
  return false
})
// Image modes (T2I / I2I) cost 10 credits; video (T2V) costs 50.
// Mirrors backend tools.claymation_generate (CREDIT_COST = 50 if is_video else 10).
// Was hardcoded 50/50 (2026-06-23 fix) — T2I users saw 50 but were charged 10,
// then balance display "jumped back" 40 on next refresh.
const creditCost = computed(() => isVideoMode.value ? 50 : 10)

function pickMode(next: Mode) {
  mode.value = next
  resultUrl.value = null
}

// handleVideoChange removed 2026-05-31 — V2V dropped.

// 7 outfit-style style presets — these are RENDERED into the prompt
// textarea on click so the user sees + can edit the canonical text.
const presets = [
  { id: 'family',    zh: '一個快樂的家庭在公園野餐',          en: 'a happy family having a picnic in a park',                       ja: '公園でピクニックを楽しむ幸せな家族',           ko: '공원에서 피크닉을 즐기는 행복한 가족',         es: 'una familia feliz haciendo un picnic en el parque' },
  { id: 'ramen',     zh: '一碗熱騰騰的拉麵，蔥花與半熟蛋',    en: 'a steaming bowl of ramen with green onions and soft-boiled egg', ja: '湯気の立つラーメン、ねぎと半熟卵添え',         ko: '김이 모락모락 나는 라멘, 파와 반숙 계란',      es: 'un cuenco humeante de ramen con cebolleta y huevo pasado por agua' },
  { id: 'astronaut', zh: '一位太空人在月球上跳舞',            en: 'an astronaut dancing on the surface of the moon',                ja: '月面で踊る宇宙飛行士',                         ko: '달 표면에서 춤추는 우주비행사',                es: 'un astronauta bailando en la superficie de la luna' },
  { id: 'cat',       zh: '一隻戴著草帽的橘貓在曬太陽',        en: 'an orange cat wearing a straw hat sunbathing',                   ja: '麦わら帽子をかぶって日向ぼっこする茶トラ猫',   ko: '밀짚모자를 쓰고 햇볕을 쬐는 주황색 고양이',    es: 'un gato naranja con sombrero de paja tomando el sol' },
  { id: 'forest',    zh: '迷霧森林裡的小木屋，夕陽從樹梢灑下', en: 'a tiny wooden cabin in a foggy forest with sunset light',        ja: '霧の森に佇む小さな丸太小屋、夕日が木々を照らす', ko: '안개 낀 숲속의 작은 통나무집, 노을빛이 비치는', es: 'una pequeña cabaña de madera en un bosque brumoso con luz del atardecer' },
  { id: 'robot',     zh: '一個復古機器人在咖啡廳裡點咖啡',    en: 'a retro robot ordering coffee at a cafe',                        ja: 'カフェでコーヒーを注文するレトロなロボット',   ko: '카페에서 커피를 주문하는 레트로 로봇',        es: 'un robot retro pidiendo café en una cafetería' },
]
function applyPreset(p: typeof presets[number]) { prompt.value = L(p.zh, p.en, p.ja, p.ko, p.es) }

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
  statusText.value = isVideoMode.value
    ? L('生成中…通常 1-3 分鐘', 'Generating… 1-3 min', '生成中…通常 1〜3 分', '생성 중… 보통 1-3분', 'Generando… 1-3 min')
    : L('生成中…通常 15-30 秒', 'Generating… 15-30s', '生成中…通常 15〜30 秒', '생성 중… 보통 15-30초', 'Generando… 15-30 s')
  resultUrl.value = null
  try {
    let imageUrl: string | undefined
    if (needsImage.value) {
      const u = await ensureUploadedImage()
      if (!u) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像のアップロードに失敗しました', '이미지 업로드 실패', 'Error al subir la imagen')); return }
      imageUrl = u
    }
    const result = await toolsApi.claymation({
      mode: mode.value,
      prompt: prompt.value.trim(),
      imageUrl,
      aspectRatio: aspectRatio.value,
    })
    if (handleCardRequired(result, uiStore, router, isZh.value)) {
      status.value = 'idle'
      return
    }
    if (result.success && (result.image_url || result.video_url || result.result_url)) {
      const url = result.image_url || result.video_url || result.result_url || ''
      resultUrl.value = url.startsWith('http') ? url : `${window.location.origin}${url}`
      resultKind.value = isVideoMode.value ? 'video' : 'image'
      status.value = 'done'
      statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      statusText.value = L('生成失敗', 'Failed', '生成失敗', '생성 실패', 'Error')
      // Backend (result.message / result.error) returns zh/en only — ja/ko/es fall through to English (BUG-017).
      uiStore.showError((result as any).message || (result as any).error || L('生成失敗', 'Generation failed', '生成に失敗しました', '생성에 실패했습니다', 'Error al generar'))
    }
  } catch (e: any) {
    status.value = 'error'
    statusText.value = L('錯誤', 'Error', 'エラー', '오류', 'Error')
    uiStore.showError(e?.message || L('生成失敗', 'Generation failed', '生成に失敗しました', '생성에 실패했습니다', 'Error al generar'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="150"
    :title="L('黏土風生成 (Claymation AI)', 'Claymation AI Generator', 'クレイメーション生成 (Claymation AI)', '클레이메이션 생성 (Claymation AI)', 'Generador Claymation AI')"
    :subtitle="L(
      '把任何主題變成手工黏土的定格動畫感。支援文字生圖、圖生圖、文字生影片、影片轉黏土風。',
      'Turn anything into handcrafted stop-motion clay. Supports text→image, image→image, text→video, and video→video.',
      'どんなテーマも手作りクレイのストップモーション風に。テキスト→画像、画像→画像、テキスト→動画、動画→クレイ風に対応。',
      '어떤 주제든 손으로 빚은 클레이 스톱모션 느낌으로. 텍스트→이미지, 이미지→이미지, 텍스트→영상, 영상→클레이 변환 지원.',
      'Convierte cualquier tema en stop-motion de plastilina artesanal. Compatible con texto→imagen, imagen→imagen, texto→vídeo y vídeo→plastilina.'
    )"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="L('生成', 'Generate', '生成', '생성', 'Generar')"
    :generate-label-running="L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…')"
    :disabled="disabled || isDemoUser"
    @generate="generate"
  >
    <template #inputs>
      <!-- Mode dropdown -->
      <div>
        <label class="pp-field-label">{{ L('模型 *', 'Model *', 'モデル *', '모델 *', 'Modelo *') }}</label>
        <select :value="mode" @change="(e) => pickMode((e.target as HTMLSelectElement).value as Mode)" class="pp-select">
          <option value="text_to_image">{{ L('文字生圖 (Seedream 5 Lite)', 'Text to Image — Seedream 5 Lite', 'テキスト→画像 (Seedream 5 Lite)', '텍스트→이미지 (Seedream 5 Lite)', 'Texto a imagen — Seedream 5 Lite') }}</option>
          <option value="image_to_image">{{ L('圖生圖 (Flux Kontext)', 'Image to Image — Flux Kontext', '画像→画像 (Flux Kontext)', '이미지→이미지 (Flux Kontext)', 'Imagen a imagen — Flux Kontext') }}</option>
          <option value="text_to_video">{{ L('文字生影片 (Kling 3.0)', 'Text to Video — Kling 3.0', 'テキスト→動画 (Kling 3.0)', '텍스트→영상 (Kling 3.0)', 'Texto a vídeo — Kling 3.0') }}</option>
        </select>
      </div>

      <!-- Task type (locked per mode) -->
      <div>
        <label class="pp-field-label">{{ L('任務類型 *', 'Task Type *', 'タスクタイプ *', '작업 유형 *', 'Tipo de tarea *') }}</label>
        <select class="pp-select" disabled>
          <option v-if="mode === 'text_to_image'">txt2img</option>
          <option v-else-if="mode === 'image_to_image'">img2img</option>
          <option v-else>txt2video</option>
        </select>
      </div>

      <!-- Image upload (I2I) -->
      <div v-if="mode === 'image_to_image'">
        <label class="pp-field-label">{{ L('參考圖片 *', 'Reference Image *', '参考画像 *', '참고 이미지 *', 'Imagen de referencia *') }}</label>
        <ImageUploader
          tool-type="claymation"
          v-model="imageInput"
          :label="L('點擊或拖放圖片', 'Click or drag an image', '画像をクリックまたはドラッグ', '이미지를 클릭하거나 드래그', 'Haz clic o arrastra una imagen')"
        />
      </div>

      <!-- V2V video upload removed 2026-05-31 -->

      <!-- Prompt -->
      <div>
        <label class="pp-field-label">{{ L('描述 *', 'Prompt *', 'プロンプト *', '프롬프트 *', 'Descripción *') }}</label>
        <textarea
          v-model="prompt"
          rows="4"
          maxlength="2000"
          class="pp-textarea"
          :placeholder="L('描述你想要的黏土風場景…', 'Describe the claymation scene you want…', '作りたいクレイメーションのシーンを記述…', '원하는 클레이메이션 장면을 설명하세요…', 'Describe la escena de plastilina que quieres…')"
        ></textarea>
        <p class="pp-field-help">{{ L('提示會原封不動傳給 AI（前綴加上「黏土風」風格指令）。', 'Your prompt reaches the model verbatim (prefixed with a one-line "claymation style" instruction).', 'プロンプトはそのままAIに送られます（「クレイメーション風」指示が先頭に付加されます）。', '프롬프트는 그대로 AI에 전달됩니다(「클레이메이션 스타일」지시문이 앞에 추가됩니다).', 'Tu prompt llega al modelo tal cual (con una instrucción "estilo plastilina" antepuesta).') }}</p>

        <div class="mt-3">
          <p class="pp-field-label">{{ L('快速套用', 'Quick Presets', 'クイックプリセット', '빠른 프리셋', 'Preajustes rápidos') }}</p>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="p in presets"
              :key="p.id"
              type="button"
              @click="applyPreset(p)"
              class="text-[11px] px-2 py-1 rounded-full"
              style="background: rgba(124,58,237,0.15); color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
            >{{ L(p.zh.slice(0, 12), p.en.slice(0, 22), p.ja.slice(0, 14), p.ko.slice(0, 14), p.es.slice(0, 22)) }}</button>
          </div>
        </div>
      </div>

      <!-- Aspect ratio (image modes only) -->
      <div v-if="mode === 'text_to_image' || mode === 'image_to_image'">
        <label class="pp-field-label">{{ L('比例', 'Aspect Ratio', 'アスペクト比', '화면 비율', 'Relación de aspecto') }}</label>
        <select v-model="aspectRatio" class="pp-select">
          <option value="1:1">1:1 (square)</option>
          <option value="16:9">16:9 (landscape)</option>
          <option value="9:16">9:16 (portrait)</option>
          <option value="4:3">4:3</option>
          <option value="3:4">3:4</option>
        </select>
      </div>

      <p v-if="isDemoUser" class="pp-field-help" style="color: #fbbf24;">
        {{ L('訂閱後即可使用此工具。', 'Subscribe to generate your own results.', 'サブスク登録するとこのツールを使えます。', '구독하면 이 도구를 사용할 수 있습니다.', 'Suscríbete para generar tus propios resultados.') }}
        <button @click="gotoPricing" class="underline ml-1">{{ L('查看方案', 'View Plans', 'プランを見る', '요금제 보기', 'Ver planes') }} →</button>
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
      >📥 {{ L('下載', 'Download', 'ダウンロード', '다운로드', 'Descargar') }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="claymation" />
    </template>
  </PiapiPlayground>
</template>
