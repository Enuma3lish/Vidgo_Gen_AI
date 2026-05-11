<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { toolsApi } from '@/api'
import ImageUploader from '@/components/common/ImageUploader.vue'
import HowToUseHint from '@/components/common/HowToUseHint.vue'
import CreditCost from '@/components/tools/CreditCost.vue'

import LoadingOverlay from '@/components/common/LoadingOverlay.vue'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const isZh = computed(() => locale.value.startsWith('zh'))
// 5-language inline picker — fixes ja/ko/es fall-through (BUG-017).
const { L } = useLocalized()

// Demo mode
const {
  isDemoUser,
  loadDemoTemplates,
  demoTemplates,
  tryPrompts,
  dbEmpty,
  resolveDemoTemplateResultUrl,
  generateOnDemand,
  loadInputLibrary,
  inputLibrary,
} = useDemoMode()

const uploadedImage = ref<string | undefined>(undefined)
const resultImage = ref<string | null>(null)
const isProcessing = ref(false)

const pendingTitle = computed(() => isZh.value
  ? '我正在為您移除背景，請稍後再回來查看是否已完成。'
  : 'Removing the background for you — please check back in a moment.')
const pendingDetail = computed(() => L('正在移除圖片背景...', 'Removing image background...', '背景を削除中...', '배경 제거 중...', 'Eliminando fondo...'))
const pendingDuration = computed(() => L('通常需要 30 秒', 'Usually takes about 30 seconds', '通常30秒程度', '보통 30초 정도', 'Suele tardar unos 30 segundos'))

// True when a demo user clicked Generate but the selected tile isn't backed
// by a real Material DB preset (db_empty fallback or missing preset id).
// Surfaces a persistent in-block message instead of a silent no-op.
const demoEmptyState = ref(false)
// Background mode picker. `transparent` = original behavior (PNG with alpha).
// `white` / `black` flatten the cutout onto a solid canvas. `color` shows a
// preset palette so the user can pick a brand-friendly tone (beige, navy,
// sage, etc.). `image` lets the user upload or paste a URL for a fully
// custom replacement scene.
type BgMode = 'transparent' | 'white' | 'black' | 'color' | 'image'
const selectedBgMode = ref<BgMode>('transparent')
const BG_MODE_OPTIONS: { id: BgMode; icon: string; labelEn: string; labelZh: string }[] = [
  { id: 'transparent', icon: '◇', labelEn: 'Transparent PNG', labelZh: '透明 PNG' },
  { id: 'white',       icon: '□', labelEn: 'White',           labelZh: '純白底' },
  { id: 'black',       icon: '■', labelEn: 'Black',           labelZh: '純黑底' },
  { id: 'color',       icon: '●', labelEn: 'Solid color',     labelZh: '純色背景' },
  { id: 'image',       icon: '🖼', labelEn: 'Replace image',   labelZh: '替換圖片' },
]

// Curated palette — six tones that look natural behind a product cutout.
const PRESET_COLORS = [
  { id: 'cream',   name: 'Cream',   hex: '#F5EFE6' },
  { id: 'beige',   name: 'Beige',   hex: '#E5DCC9' },
  { id: 'sage',    name: 'Sage',    hex: '#9CAF88' },
  { id: 'navy',    name: 'Navy',    hex: '#1F2A44' },
  { id: 'rose',    name: 'Rose',    hex: '#E0A6A6' },
  { id: 'charcoal',name: 'Charcoal',hex: '#2C2C2C' },
] as const
const selectedColorHex = ref<string>('#F5EFE6')
const customBackgroundImageUrl = ref<string | undefined>(undefined)
const replacementBgFileName = ref<string>('')

async function onReplacementBgPicked(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  replacementBgFileName.value = file.name
  // Upload directly to our /demo/upload (subscriber path also gates) and
  // keep the returned URL as the replacement background source. Works
  // identically on mobile because we render a <label><input type=file></label>
  // and don't rely on any custom click forwarding.
  try {
    isProcessing.value = true
    const uploaded = await toolsApi.uploadImage(file)
    customBackgroundImageUrl.value = uploaded.url
    uiStore.showSuccess(L('替換背景圖片已上傳', 'Replacement background uploaded', '置換背景画像をアップロードしました', '교체 배경 이미지 업로드됨', 'Fondo de reemplazo subido'))
  } catch (err) {
    console.error('replacement bg upload failed', err)
    uiStore.showError(L('替換背景圖片上傳失敗，請稍後再試', 'Failed to upload replacement background. Please try again.', '置換背景画像のアップロードに失敗しました。後ほど再試行してください。', '교체 배경 이미지 업로드 실패. 나중에 다시 시도해 주세요.', 'Falló la subida del fondo de reemplazo. Inténtalo de nuevo.'))
    replacementBgFileName.value = ''
  } finally {
    isProcessing.value = false
  }
}

// Demo images from database only (no hardcoded fallbacks)
const selectedDemoIndex = ref<number>(0)
const isLoadingTemplates = ref(true)

const demoImages = computed(() => {
  // Prefer the pregenerated INPUT library (Vertex Imagen → GCS) when present.
  // These rows have null result URLs by design — background removal runs
  // live per click via the cache-through path, so `result` is left null and
  // resolved at generate-time.
  if (inputLibrary.value.length > 0) {
    return inputLibrary.value
      .filter(item => item.input_image_url)
      .map(item => ({
        id: item.id,
        input: item.input_image_url as string,
        result: null as string | null,
      }))
  }
  return demoTemplates.value
    .filter(t => t.input_image_url)
    .map(t => ({
      id: t.id,
      input: t.input_image_url as string,
      result: (t.result_watermarked_url || t.result_image_url) as string | null
    }))
})


// Static fallback examples (shown when backend DB is empty)
const STATIC_BG_EXAMPLES = [
  {
    id: 'static-bg-1',
    input: 'https://images.unsplash.com/photo-1585386959984-a4155224a1ad?w=600&fit=crop',
    result: 'https://images.unsplash.com/photo-1585386959984-a4155224a1ad?w=600&fit=crop&bg=transparent',
    label: 'Skincare Bottle'
  },
  {
    id: 'static-bg-2',
    input: 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600&fit=crop',
    result: 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600&fit=crop',
    label: 'Coffee Bag'
  },
  {
    id: 'static-bg-3',
    input: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&fit=crop',
    result: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&fit=crop',
    label: 'Sneakers'
  },
  {
    id: 'static-bg-4',
    input: 'https://images.unsplash.com/photo-1491553895911-0055eca6402d?w=600&fit=crop',
    result: 'https://images.unsplash.com/photo-1491553895911-0055eca6402d?w=600&fit=crop',
    label: 'Running Shoes'
  },
  {
    id: 'static-bg-5',
    input: 'https://images.unsplash.com/photo-1560343090-f0409e92791a?w=600&fit=crop',
    result: 'https://images.unsplash.com/photo-1560343090-f0409e92791a?w=600&fit=crop',
    label: 'Sneaker Pair'
  },
  {
    id: 'static-bg-6',
    input: 'https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=600&fit=crop',
    result: 'https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=600&fit=crop',
    label: 'Camera'
  }
]

const effectiveDemoImages = computed(() =>
  demoImages.value.length > 0 ? demoImages.value : STATIC_BG_EXAMPLES
)

// Load demo templates on mount
onMounted(async () => {
  isLoadingTemplates.value = true
  await Promise.all([
    loadDemoTemplates('background_removal', undefined, locale.value),
    // Pregenerated Vertex AI input library — rows with null result URLs that
    // the user picks from. Runtime generates the cutout on first click per
    // input and caches under the same lookup_hash for subsequent hits.
    loadInputLibrary('background_removal'),
  ])
  isLoadingTemplates.value = false

  // For demo users, auto-select first example
  const effective = demoImages.value.length > 0 ? demoImages.value : STATIC_BG_EXAMPLES
  if (isDemoUser.value && effective.length > 0) {
    uploadedImage.value = effective[0].input || undefined
  }
})

watch(locale, () => loadDemoTemplates('background_removal', undefined, locale.value))

function selectDemoExample(index: number) {
  selectedDemoIndex.value = index
  const effective2 = demoImages.value.length > 0 ? demoImages.value : STATIC_BG_EXAMPLES
  const example = effective2[index]
  if (example) {
    uploadedImage.value = example.input || undefined
    resultImage.value = null
    demoEmptyState.value = false
  }
}



// Composite a transparent-PNG cutout onto a solid background colour client-
// side. Used for the demo path where the backend always returns the cached
// transparent PNG regardless of the selected Output Background mode — we
// flatten it here so White/Black/Color modes produce visibly different
// results without burning a real provider call.
async function compositeCutoutOnColor(cutoutUrl: string, fillStyle: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = img.naturalWidth
      canvas.height = img.naturalHeight
      const ctx = canvas.getContext('2d')
      if (!ctx) { reject(new Error('canvas 2d unavailable')); return }
      ctx.fillStyle = fillStyle
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(img, 0, 0)
      canvas.toBlob(blob => {
        if (!blob) { reject(new Error('canvas toBlob failed')); return }
        resolve(URL.createObjectURL(blob))
      }, 'image/jpeg', 0.9)
    }
    img.onerror = () => reject(new Error('cutout image failed to load'))
    img.src = cutoutUrl
  })
}

async function removeBackground() {
  if (!uploadedImage.value) return

  // Replacement-image mode needs the user to provide a custom background URL
  // (or upload one) — that's a real generation only subscribers can do.
  if (selectedBgMode.value === 'image' && isDemoUser.value) {
    uiStore.showError(L('請訂閱以使用自訂替換圖片背景', 'Please subscribe to use a replacement background image', '置換背景画像を使うにはサブスク登録してください', '교체 배경 이미지를 사용하려면 구독해 주세요', 'Suscríbete para usar una imagen de fondo personalizada'))
    return
  }
  if (selectedBgMode.value === 'image' && !customBackgroundImageUrl.value) {
    uiStore.showError(L('請先選擇或上傳替換背景圖片', 'Please pick or upload a replacement background image first', '先に置換背景画像を選択またはアップロードしてください', '먼저 교체 배경 이미지를 선택하거나 업로드해 주세요', 'Selecciona o sube primero una imagen de fondo'))
    return
  }

  // Clear stale result so loading overlay is the only thing visible.
  resultImage.value = null
  isProcessing.value = true
  try {
    // For demo users, resolve the selected preset through backend lookup
    if (isDemoUser.value) {
      await new Promise(resolve => setTimeout(resolve, 1500))

      // Helper: take the cached transparent cutout and apply the user's
      // chosen Output Background locally so White/Black/Color modes produce
      // visibly different results in demo mode.
      async function applyDemoOutputBg(transparentUrl: string): Promise<string> {
        const mode = selectedBgMode.value
        if (mode === 'white')  return await compositeCutoutOnColor(transparentUrl, '#ffffff')
        if (mode === 'black')  return await compositeCutoutOnColor(transparentUrl, '#000000')
        if (mode === 'color')  return await compositeCutoutOnColor(transparentUrl, selectedColorHex.value || '#F5EFE6')
        return transparentUrl
      }

      const selectedTemplateId = demoImages.value[selectedDemoIndex.value]?.id
      if (selectedTemplateId) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(selectedTemplateId)
        if (demoResultUrl) {
          try {
            resultImage.value = await applyDemoOutputBg(demoResultUrl)
          } catch {
            resultImage.value = demoResultUrl
          }
          uiStore.showSuccess(L('處理成功（示範）', 'Processed successfully (Demo)', '処理成功（デモ）', '처리 성공 (데모)', 'Procesado correctamente (demo)'))
          return
        }
      }

      // VG-BUG-010 fix: no cached result — call cache-through endpoint.
      uiStore.showInfo(L('此圖片尚未生成結果，正在為您即時處理...', 'Generating in real-time...', 'リアルタイムで処理中...', '실시간으로 처리 중...', 'Procesando en tiempo real...'))
      // `demoImages` items expose the source URL as `input` (see the computed
      // above — flattened from library/template rows), not `input_image_url`.
      const pickedInput = demoImages.value[selectedDemoIndex.value]?.input || uploadedImage.value || undefined
      const onDemandUrl = await generateOnDemand('background_removal', undefined, {
        input_image_url: pickedInput,
      })
      if (onDemandUrl) {
        try {
          resultImage.value = await applyDemoOutputBg(onDemandUrl)
        } catch {
          resultImage.value = onDemandUrl
        }
        uiStore.showSuccess(L('處理成功', 'Processed successfully', '処理成功', '처리 성공', 'Procesado correctamente'))
        return
      }
      demoEmptyState.value = true
      uiStore.showError(L('生成服務暫時無法使用，請稍後再試或訂閱解鎖完整功能', 'Generation service temporarily unavailable. Please try again later or subscribe.', '生成サービスは一時的に利用できません。後ほど再試行するか、サブスクで全機能を解禁してください。', '생성 서비스를 일시적으로 사용할 수 없습니다. 나중에 다시 시도하거나 구독해 주세요.', 'Servicio temporalmente no disponible. Inténtalo más tarde o suscríbete.'))
      return
    }

    // Upload image first
    let uploadUrl = uploadedImage.value
    if (uploadedImage.value.startsWith('data:')) {
      const blob = dataURItoBlob(uploadedImage.value)
      if (!blob) {
        uiStore.showError(L('圖片格式無效，請重新上傳', 'Invalid image format. Please re-upload.', '画像形式が無効です。再アップロードしてください。', '이미지 형식이 올바르지 않습니다. 다시 업로드해 주세요.', 'Formato de imagen inválido. Súbela de nuevo.'))
        return
      }
      const uploadResult = await toolsApi.uploadImage(blob as File)
      uploadUrl = uploadResult.url
    }
    const uploadResult = { url: uploadUrl }

    // Call tools API. Map UI mode → backend params:
    //   transparent → output_format=png, no replacement
    //   white/black → output_format=white|black
    //   color       → background_color=#hex (overrides output_format)
    //   image       → background_image_url=... (overrides everything)
    const mode = selectedBgMode.value
    const outputFormat = mode === 'white' ? 'white' : mode === 'black' ? 'black' : 'png'
    const opts: { backgroundColor?: string; backgroundImageUrl?: string } = {}
    if (mode === 'color') opts.backgroundColor = selectedColorHex.value
    if (mode === 'image') opts.backgroundImageUrl = customBackgroundImageUrl.value
    const result = await toolsApi.removeBackground(uploadResult.url, outputFormat, opts)

    if (result.success && (result.image_url || result.result_url)) {
      resultImage.value = result.image_url || result.result_url || null
      creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success'))
    } else {
      uiStore.showError(result.message || 'Processing failed')
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail || error?.response?.data?.message || error?.message || ''
    uiStore.showError(detail || L('處理失敗，請稍後再試', 'Processing failed. Please try again.', '処理に失敗しました。後ほど再試行してください。', '처리에 실패했습니다. 나중에 다시 시도해 주세요.', 'Falló el procesamiento. Inténtalo de nuevo.'))
  } finally {
    isProcessing.value = false
  }
}

function dataURItoBlob(dataURI: string): Blob | null {
  if (!dataURI || !dataURI.includes(',') || !dataURI.startsWith('data:')) return null
  try {
    const byteString = atob(dataURI.split(',')[1])
    const mimeString = dataURI.split(',')[0].split(':')[1].split(';')[0]
    const ab = new ArrayBuffer(byteString.length)
    const ia = new Uint8Array(ab)
    for (let i = 0; i < byteString.length; i++) { ia[i] = byteString.charCodeAt(i) }
    return new Blob([ab], { type: mimeString })
  } catch { return null }
}


</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b; color: #f5f5fa;">
    <LoadingOverlay
      :show="isProcessing"
      icon="✂️"
      :title="pendingTitle"
      :detail="pendingDetail"
      :duration="pendingDuration"
    />

    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Back Button -->
      <button
        @click="router.back()"
        class="mb-6 flex items-center gap-2 text-dark-300 hover:text-dark-50 transition-colors"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        {{ t('common.back') }}
      </button>

      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-dark-50 mb-4">
          {{ t('tools.backgroundRemoval.name') }}
        </h1>
        <p class="text-xl text-dark-300">
          {{ t('tools.backgroundRemoval.longDesc') }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ L('訂閱以解鎖更多功能', 'Subscribe to unlock more features', 'サブスク登録で機能を解禁', '구독으로 더 많은 기능 잠금 해제', 'Suscríbete para desbloquear más funciones') }}
          </RouterLink>
        </div>

        <!-- DB Empty: Show try prompts -->
        <div v-if="dbEmpty && tryPrompts.length > 0" class="mt-6 p-4 rounded-xl" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <p class="text-sm text-dark-200 mb-2">{{ L('可試玩提示詞（資料庫尚無預生成）', 'Try prompts (no pre-generated results yet)', 'プロンプトを試す（まだ事前生成なし）', '프롬프트 시도 (사전 생성 없음)', 'Prueba prompts (sin pregenerados)') }}</p>
          <div class="flex flex-wrap gap-2">
            <span v-for="p in tryPrompts.slice(0, 5)" :key="p.id" class="px-2 py-1 rounded text-xs bg-dark-800 text-dark-200">{{ p.prompt }}</span>
          </div>
        </div>
      </div>

      <HowToUseHint
        tool-type="background_removal"
        media-kind="image"
        :i18n-keys="[
          'howTo.background_removal.step1',
          'howTo.background_removal.step2',
          'howTo.background_removal.step3',
        ]"
      />

      <!-- PRESET-ONLY MODE: All users see the same preset-based layout -->
      <div class="space-y-8">
        <!-- Example Selection (Demo Users) -->
        <div v-if="isDemoUser || effectiveDemoImages.length > 0" class="card">
          <h3 class="text-lg font-semibold text-dark-50 mb-4">
            {{ L('選擇範例圖片', 'Select Example Image', '例の画像を選択', '예시 이미지 선택', 'Selecciona imagen ejemplo') }}
          </h3>
          <div v-if="isLoadingTemplates" class="flex justify-center py-8">
            <div class="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
          </div>
          <div v-else-if="effectiveDemoImages.length === 0" class="text-center py-8 text-dark-400">
            <span class="text-3xl block mb-2">📷</span>
            <p class="text-sm">{{ L('範例圖片準備中，請稍後再試', 'Example images loading, please try again later', '例の画像を読み込み中。後ほど再試行してください。', '예시 이미지 로딩 중. 나중에 다시 시도해 주세요.', 'Cargando imágenes de ejemplo. Inténtalo más tarde.') }}</p>
          </div>
          <div v-else class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
            <button
              v-for="(example, idx) in effectiveDemoImages"
              :key="example.id || idx"
              @click="selectDemoExample(idx)"
              class="aspect-square rounded-lg overflow-hidden border-2 transition-all"
              :class="selectedDemoIndex === idx && uploadedImage === example.input
                ? 'border-primary-500 ring-2 ring-primary-500/50'
                : 'hover:border-dark-500'" style="border-color: rgba(255,255,255,0.08);">
            >
              <img
                :src="example.input"
                alt="Example"
                class="w-full h-full object-cover"
              />
            </button>
          </div>
        </div>

        <!-- Custom Upload (Paid Users) -->
        <div v-if="!isDemoUser" class="card mt-4">
          <h3 class="text-lg font-semibold text-dark-50 mb-4">
            {{ L('上傳圖片', 'Upload Image', '画像をアップロード', '이미지 업로드', 'Subir imagen') }}
          </h3>
          <ImageUploader 
            tool-type="background_removal"
            v-model="uploadedImage" 
            :label="L('點擊上傳或拖放圖片', 'Drop image here', 'クリックまたは画像をドロップ', '클릭 또는 이미지 드롭', 'Sube o arrastra una imagen')"
          />
        </div>

        <!-- Input and Result Side by Side -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mt-4">
          <!-- Input -->
          <div class="card">
            <h3 class="text-lg font-semibold text-dark-50 mb-4">
              {{ L('原始圖片', 'Original Image', '元画像', '원본 이미지', 'Imagen original') }}
            </h3>
            <div v-if="uploadedImage" class="rounded-xl overflow-hidden">
              <img :src="uploadedImage" alt="Original" class="w-full" />
            </div>
            <div v-else class="h-64 flex items-center justify-center rounded-xl" style="background: #141420;">
              <span class="text-dark-400">{{ L('請選擇圖片', 'Select an image', '画像を選択', '이미지를 선택해 주세요', 'Selecciona una imagen') }}</span>
            </div>
          </div>

          <!-- Result -->
          <div class="card">
            <h3 class="text-lg font-semibold text-dark-50 mb-4">
              {{ L('去背結果', 'Result', '結果', '결과', 'Resultado') }}
            </h3>
            <div v-if="resultImage" class="space-y-4">
              <div class="rounded-xl overflow-hidden bg-checkered relative">
                <img :src="resultImage" alt="Result" class="w-full" />
              </div>

              <!-- Watermark badge -->
              <div class="text-center text-xs text-dark-400">vidgo.ai</div>

              <!-- Paid users: Download button -->
              <a
                v-if="!isDemoUser && resultImage"
                :href="resultImage"
                :download="`vidgo-bg-removed.${selectedBgMode === 'transparent' ? 'png' : 'jpg'}`"
                class="btn-primary w-full text-center block"
              >
                {{ L('下載結果', 'Download Result', '結果をダウンロード', '결과 다운로드', 'Descargar resultado') }}
              </a>
              <!-- Demo users: Subscribe CTA -->
              <RouterLink
                v-else
                to="/pricing"
                class="btn-primary w-full text-center block"
              >
                {{ L('訂閱以獲得完整功能', 'Subscribe for Full Access', 'サブスクで全機能を解禁', '구독으로 전체 액세스', 'Suscríbete para acceso completo') }}
              </RouterLink>
            </div>
            <div v-else-if="demoEmptyState" class="h-64 flex flex-col items-center justify-center rounded-xl text-center px-6 gap-3" style="background: #141420; border: 1px solid rgba(255,255,255,0.08);">
              <span class="text-2xl">🔒</span>
              <p class="text-sm text-dark-200">
                {{ L('此範例尚未預生成結果', 'No pre-generated result for this example yet', 'この例はまだ事前生成されていません', '이 예시는 아직 사전 생성되지 않았습니다', 'Aún no hay resultado pregenerado') }}
              </p>
              <RouterLink to="/pricing" class="btn-primary text-sm px-4 py-2">
                {{ L('訂閱以使用完整 AI 功能', 'Subscribe to use the real AI', 'サブスクで実AI機能を解禁', '구독으로 실제 AI 사용', 'Suscríbete para usar la IA real') }}
              </RouterLink>
            </div>
            <div v-else class="h-64 flex items-center justify-center rounded-xl" style="background: #141420;">
              <span class="text-dark-400">{{ L('點擊下方按鈕去除背景', 'Click button below to remove background', '下のボタンをクリックして背景を削除', '아래 버튼을 클릭하여 배경 제거', 'Toca el botón para eliminar fondo') }}</span>
            </div>
          </div>
        </div>

        <!-- Background Mode Picker -->
        <div class="mt-6 pt-6" style="border-top: 1px solid rgba(255,255,255,0.06);">
          <label class="block text-sm font-medium text-dark-200 mb-3">
            {{ L('輸出背景', 'Output Background', '出力背景', '출력 배경', 'Fondo de salida') }}
          </label>
          <div class="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-3">
            <button
              v-for="m in BG_MODE_OPTIONS"
              :key="m.id"
              type="button"
              @click="selectedBgMode = m.id"
              class="px-3 py-2 rounded-lg text-xs font-medium transition-all border"
              :style="selectedBgMode === m.id
                ? 'background: rgba(22,119,255,0.15); border-color: rgba(22,119,255,0.5); color: #6cb1ff;'
                : 'background: #141420; border-color: rgba(255,255,255,0.08); color: #c4c4d8;'"
            >
              <span class="block text-base mb-1">{{ m.icon }}</span>
              {{ isZh ? m.labelZh : m.labelEn }}
            </button>
          </div>

          <!-- Color palette -->
          <div v-if="selectedBgMode === 'color'" class="mb-3">
            <p class="text-xs text-dark-400 mb-2">
              {{ L('選擇純色背景：', 'Pick a solid color:', '単色背景を選択：', '단색 배경 선택:', 'Selecciona un color sólido:') }}
            </p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="c in PRESET_COLORS"
                :key="c.id"
                type="button"
                @click="selectedColorHex = c.hex"
                class="flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-all border"
                :style="selectedColorHex === c.hex
                  ? `background: ${c.hex}22; border-color: ${c.hex};`
                  : 'background: #141420; border-color: rgba(255,255,255,0.08);'"
              >
                <span class="inline-block w-4 h-4 rounded-full border" :style="`background: ${c.hex}; border-color: rgba(255,255,255,0.15);`" />
                <span style="color: #c4c4d8;">{{ c.name }}</span>
              </button>
            </div>
            <div class="mt-3 flex items-center gap-2">
              <span class="text-xs text-dark-400">{{ L('或自訂：', 'Or custom:', 'またはカスタム：', '또는 사용자 지정:', 'O personalizado:') }}</span>
              <input
                v-model="selectedColorHex"
                type="color"
                class="w-8 h-8 rounded border-0 cursor-pointer"
                style="background: transparent;"
              />
              <input
                v-model="selectedColorHex"
                type="text"
                placeholder="#RRGGBB"
                maxlength="9"
                class="flex-1 max-w-[140px] px-2 py-1 rounded-md text-xs"
                style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #e8e8f0;"
              />
            </div>
          </div>

          <!-- Replacement image — upload from device (works on mobile too) -->
          <div v-if="selectedBgMode === 'image'" class="mb-3">
            <p class="text-xs text-dark-400 mb-2">
              {{ L('上傳替換背景圖片（JPG / PNG / WebP）：', 'Upload a replacement background image (JPG / PNG / WebP):', '置換背景画像（JPG / PNG / WebP）をアップロード：', '교체 배경 이미지 업로드 (JPG / PNG / WebP):', 'Sube imagen de fondo (JPG / PNG / WebP):') }}
            </p>
            <label
              class="block w-full px-4 py-3 rounded-md text-sm text-center cursor-pointer transition-colors"
              style="background: #141420; border: 1px dashed rgba(255,255,255,0.18); color: #c4c4d8;"
              @mouseenter="($event.currentTarget as HTMLElement).style.borderColor = 'rgba(22,119,255,0.5)'"
              @mouseleave="($event.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.18)'"
            >
              {{ replacementBgFileName
                ? (isZh ? `已選擇：${replacementBgFileName}` : `Selected: ${replacementBgFileName}`)
                : L('點此選擇或拍攝照片', 'Tap to choose or take a photo', 'タップして選択または撮影', '탭하여 선택 또는 촬영', 'Toca para elegir o tomar foto') }}
              <!-- accept="image/*" + omitting `capture` lets the OS choose:
                   mobile shows camera + library, desktop shows file dialog. -->
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                class="hidden"
                @change="onReplacementBgPicked"
              />
            </label>
            <details class="mt-2">
              <summary class="text-[11px] text-dark-500 cursor-pointer">
                {{ L('或貼上圖片網址', 'Or paste an image URL', 'または画像URLを貼り付け', '또는 이미지 URL 붙여넣기', 'O pega una URL de imagen') }}
              </summary>
              <input
                v-model="customBackgroundImageUrl"
                type="url"
                placeholder="https://..."
                class="w-full mt-2 px-3 py-2 rounded-md text-sm"
                style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #e8e8f0;"
              />
            </details>
            <p class="text-[11px] text-dark-500 mt-2">
              {{ isZh
                ? '圖片會自動裁切貼合主體比例。建議使用 1024×1024 以上的高解析度背景。'
                : 'The image is auto-cropped to the cutout aspect. Use ≥1024×1024 for best results.' }}
            </p>
          </div>

          <p class="text-[11px] text-dark-500">
            {{ selectedBgMode === 'transparent'
              ? L('輸出透明背景 PNG，方便後製。', 'Outputs a transparent-background PNG for further compositing.', '透過背景PNGを出力します。後加工に便利。', '투명 배경 PNG로 출력. 후가공에 편리.', 'Devuelve un PNG con fondo transparente para composición.')
              : selectedBgMode === 'white'
              ? L('輸出白底圖片，適合電商主圖。', 'Outputs a white-background image, ideal for e-commerce listings.', '白背景の画像を出力。EC掲載に最適。', '흰색 배경 이미지를 출력. 이커머스 메인에 적합.', 'Devuelve una imagen con fondo blanco, ideal para e-commerce.')
              : selectedBgMode === 'black'
              ? L('輸出黑底圖片，適合精品 / 科技類品牌。', 'Outputs a black-background image for premium / tech brands.', '黒背景の画像を出力。プレミアム／テック系ブランド向け。', '검은 배경 이미지를 출력. 프리미엄/테크 브랜드에 적합.', 'Devuelve una imagen con fondo negro, ideal para marcas premium/tech.')
              : selectedBgMode === 'color'
              ? L('商品會合成在你選的純色背景上。', 'Composites the cutout onto your selected solid color.', '選択した単色背景に合成します。', '선택한 단색 배경에 합성됩니다.', 'Compone el recorte sobre el color sólido elegido.')
              : L('商品會合成在你提供的背景圖片上。', 'Composites the cutout onto your replacement image.', '提供した背景画像に合成します。', '제공한 배경 이미지에 합성됩니다.', 'Compone el recorte sobre tu imagen de reemplazo.') }}
          </p>
        </div>

        <!-- Remove Button and Credit Cost -->
        <div class="flex flex-col items-center gap-4 mt-4 pt-4" style="border-top: 1px solid rgba(255,255,255,0.06);">
          <CreditCost service="background_removal" />
          <button
            @click="removeBackground"
            :disabled="!uploadedImage || isProcessing || (selectedBgMode === 'image' && !customBackgroundImageUrl)"
            class="btn-primary px-12 py-4 text-lg font-semibold"
          >
            <span v-if="isProcessing" class="flex items-center gap-2">
              <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              {{ t('common.processing') }}
            </span>
            <span v-else class="flex items-center gap-2">
              <span>✨</span>
              {{ selectedBgMode === 'transparent' || selectedBgMode === 'white' || selectedBgMode === 'black'
                ? L('去除背景', 'Remove Background', '背景を削除', '배경 제거', 'Eliminar fondo')
                : L('替換背景', 'Replace Background', '背景を置換', '배경 교체', 'Reemplazar fondo') }}
            </span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bg-checkered {
  background-image: linear-gradient(45deg, #374151 25%, transparent 25%),
    linear-gradient(-45deg, #374151 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #374151 75%),
    linear-gradient(-45deg, transparent 75%, #374151 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
  background-color: #1f2937;
}
</style>
