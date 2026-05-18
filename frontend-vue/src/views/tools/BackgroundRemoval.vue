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
import ProToolHero from '@/components/tools/ProToolHero.vue'
import { downloadAsset } from '@/utils/downloadAsset'

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
type BgMode = 'transparent' | 'white' | 'black' | 'color' | 'image' | 'ai'
const selectedBgMode = ref<BgMode>('transparent')
const BG_MODE_OPTIONS: { id: BgMode; icon: string; labelEn: string; labelZh: string }[] = [
  { id: 'transparent', icon: '◇', labelEn: 'Transparent PNG', labelZh: '透明 PNG' },
  { id: 'white',       icon: '□', labelEn: 'White',           labelZh: '純白底' },
  { id: 'black',       icon: '■', labelEn: 'Black',           labelZh: '純黑底' },
  { id: 'color',       icon: '●', labelEn: 'Solid color',     labelZh: '純色背景' },
  { id: 'image',       icon: '🖼', labelEn: 'Replace image',   labelZh: '替換圖片' },
  { id: 'ai',          icon: '✨', labelEn: 'AI scene',        labelZh: 'AI 場景' },
]

const aiBackgroundPrompt = ref<string>('')
const AI_BG_PROMPT_PRESETS: { id: string; labelZh: string; labelEn: string; prompt: string }[] = [
  { id: 'beachWood',  labelZh: '熱帶海灘木台',     labelEn: 'Tropical beach pedestal',  prompt: 'sunlit tropical beach with white sand and a soft turquoise ocean horizon, blurred background, soft daylight' },
  { id: 'marble',     labelZh: '大理石檯面',       labelEn: 'White marble counter',     prompt: 'soft white marble counter with gentle natural shadow, minimalist studio background' },
  { id: 'studioPink', labelZh: '柔粉攝影棚',       labelEn: 'Soft pink studio',         prompt: 'soft pastel pink seamless studio backdrop with subtle gradient, premium e-commerce lighting' },
  { id: 'autumnLeaves', labelZh: '秋葉自然',       labelEn: 'Warm autumn leaves',       prompt: 'warm autumn leaves on a wooden table, soft natural light, shallow depth of field' },
  { id: 'concreteCity', labelZh: '極簡水泥牆',     labelEn: 'Minimalist concrete wall', prompt: 'minimalist polished concrete wall with soft directional shadow, urban editorial vibe' },
  { id: 'holiday',    labelZh: '節日聖誕情境',     labelEn: 'Holiday scene',            prompt: 'warm festive holiday scene with subtle bokeh string lights and pine branches, cinematic warm light' },
]
const selectedAiPresetId = ref<string>('')
function applyAiPreset() {
  const p = AI_BG_PROMPT_PRESETS.find(x => x.id === selectedAiPresetId.value)
  if (p) aiBackgroundPrompt.value = p.prompt
}

// Platform auto-resize — applied client-side to the final result image
// via a hidden <canvas>. Crop modes mirror the recommended specs each
// platform publishes for product cards / hero images.
type PlatformSize = '' | 'amazon_1to1' | 'shopify_1to1' | 'ig_square' | 'ig_story' | 'tiktok_video'
const selectedPlatformSize = ref<PlatformSize>('')
const PLATFORM_SIZE_OPTIONS: { id: PlatformSize; labelEn: string; labelZh: string; w: number; h: number }[] = [
  { id: '',            labelEn: 'Original size',           labelZh: '原始尺寸',                w: 0,    h: 0 },
  { id: 'amazon_1to1', labelEn: 'Amazon 2000×2000 (1:1)',  labelZh: 'Amazon 2000×2000 (1:1)', w: 2000, h: 2000 },
  { id: 'shopify_1to1',labelEn: 'Shopify 2048×2048 (1:1)', labelZh: 'Shopify 2048×2048 (1:1)',w: 2048, h: 2048 },
  { id: 'ig_square',   labelEn: 'Instagram 1080×1080',     labelZh: 'Instagram 1080×1080',     w: 1080, h: 1080 },
  { id: 'ig_story',    labelEn: 'IG Story 1080×1920 (9:16)', labelZh: 'IG 限動 1080×1920 (9:16)', w: 1080, h: 1920 },
  { id: 'tiktok_video',labelEn: 'TikTok 1080×1920 (9:16)', labelZh: 'TikTok 1080×1920 (9:16)', w: 1080, h: 1920 },
]

async function downloadResized(srcUrl: string) {
  const spec = PLATFORM_SIZE_OPTIONS.find(o => o.id === selectedPlatformSize.value)
  if (!spec || !spec.w || !spec.h) {
    // Original size — route through the shared blob-based downloader so the
    // browser actually downloads instead of opening the GCS-hosted file in
    // a new tab (cross-origin `<a download>` is ignored by all browsers).
    await downloadAsset(srcUrl, `vidgo-bg-removed.${selectedBgMode.value === 'transparent' ? 'png' : 'jpg'}`)
    return
  }
  try {
    isProcessing.value = true
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.src = srcUrl
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error('image load failed'))
    })
    const canvas = document.createElement('canvas')
    canvas.width = spec.w
    canvas.height = spec.h
    const ctx = canvas.getContext('2d')!
    // Fill background — transparent for PNG mode, white otherwise so the
    // canvas doesn't introduce a black border on JPEG.
    if (selectedBgMode.value !== 'transparent') {
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, spec.w, spec.h)
    }
    // Letterbox the cutout so the full subject is always visible (no
    // automatic center-crop that could clip the product).
    const ratio = Math.min(spec.w / img.width, spec.h / img.height)
    const drawW = img.width * ratio
    const drawH = img.height * ratio
    ctx.drawImage(img, (spec.w - drawW) / 2, (spec.h - drawH) / 2, drawW, drawH)
    const mime = selectedBgMode.value === 'transparent' ? 'image/png' : 'image/jpeg'
    const ext  = selectedBgMode.value === 'transparent' ? 'png' : 'jpg'
    canvas.toBlob((blob) => {
      if (!blob) return
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `vidgo-${spec.id}-${Date.now()}.${ext}`
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 500)
    }, mime, 0.95)
  } catch (e) {
    console.error('resize failed', e)
    uiStore.showError(L('調整尺寸失敗，使用原始圖片', 'Resize failed, downloading original instead', 'リサイズに失敗。元画像をダウンロード', '리사이즈 실패. 원본 다운로드', 'No se pudo redimensionar, descargando original'))
    const a = document.createElement('a')
    a.href = srcUrl
    a.download = `vidgo-bg-removed.${selectedBgMode.value === 'transparent' ? 'png' : 'jpg'}`
    a.click()
  } finally {
    isProcessing.value = false
  }
}

// Batch state — accepts up to 10 images, each gets the same background
// mode / color / image / AI prompt. Backend (/remove-bg/batch) enforces
// the same plan check + 10-image ceiling.
interface BatchItem { id: string; file: File; url?: string; resultUrl?: string; status: 'queued' | 'uploaded' | 'done' | 'error'; error?: string }
const batchItems = ref<BatchItem[]>([])
const isBatchProcessing = ref(false)
const BATCH_MAX = 10

function onBatchPicked(e: Event) {
  const target = e.target as HTMLInputElement
  const files = Array.from(target.files || [])
  for (const f of files) {
    if (batchItems.value.length >= BATCH_MAX) break
    batchItems.value.push({ id: Math.random().toString(36).slice(2), file: f, status: 'queued' })
  }
  target.value = ''
}

function removeBatchItem(id: string) {
  batchItems.value = batchItems.value.filter(i => i.id !== id)
}

async function runBatch() {
  if (!batchItems.value.length) return
  isBatchProcessing.value = true
  try {
    // 1. Upload everything first so we have public URLs to pass to the
    //    batch endpoint. Errors short-circuit per-file but don't block
    //    the rest of the queue.
    for (const item of batchItems.value) {
      if (item.url) continue
      try {
        const r = await toolsApi.uploadImage(item.file)
        item.url = r.url
        item.status = 'uploaded'
      } catch (err: any) {
        item.status = 'error'
        item.error = err?.message || 'upload failed'
      }
    }
    const urls = batchItems.value.filter(i => i.url).map(i => i.url as string)
    if (!urls.length) {
      uiStore.showError(L('沒有可處理的圖片', 'No images to process', '処理可能な画像なし', '처리할 이미지 없음', 'Sin imágenes que procesar'))
      return
    }
    const fmt: 'png' | 'white' | 'black' = selectedBgMode.value === 'white' ? 'white' : selectedBgMode.value === 'black' ? 'black' : 'png'
    const opts: { backgroundColor?: string; backgroundImageUrl?: string; aiBackgroundPrompt?: string } = {}
    if (selectedBgMode.value === 'color') opts.backgroundColor = selectedColorHex.value
    if (selectedBgMode.value === 'image') opts.backgroundImageUrl = customBackgroundImageUrl.value
    if (selectedBgMode.value === 'ai')    opts.aiBackgroundPrompt = aiBackgroundPrompt.value
    const resp = await toolsApi.removeBackgroundBatch(urls, fmt, opts)
    const results = resp.results || []
    // Map results back to batchItems by index of the upload-ordered urls
    let i = 0
    for (const item of batchItems.value) {
      if (!item.url) continue
      const r = results[i++]
      if (r && r.success) {
        item.resultUrl = (r as any).result_url || (r as any).image_url
        item.status = 'done'
      } else {
        item.status = 'error'
        item.error = (r as any)?.error || 'failed'
      }
    }
    creditsStore.fetchBalance()
    uiStore.showSuccess(L('批次處理完成', 'Batch processing complete', 'バッチ処理完了', '일괄 처리 완료', 'Procesamiento por lotes completo'))
  } catch (err: any) {
    uiStore.showError(err?.response?.data?.detail || err?.message || L('批次處理失敗', 'Batch processing failed', 'バッチ処理失敗', '일괄 처리 실패', 'Falló el procesamiento'))
  } finally {
    isBatchProcessing.value = false
  }
}

async function downloadAllBatchResults() {
  for (const item of batchItems.value) {
    if (!item.resultUrl) continue
    const a = document.createElement('a')
    a.href = item.resultUrl
    a.download = `vidgo-batch-${item.id}.${selectedBgMode.value === 'transparent' ? 'png' : 'jpg'}`
    a.click()
    // Stagger so the browser doesn't suppress sequential downloads.
    await new Promise((r) => setTimeout(r, 250))
  }
}

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
    const opts: { backgroundColor?: string; backgroundImageUrl?: string; aiBackgroundPrompt?: string } = {}
    if (mode === 'color') opts.backgroundColor = selectedColorHex.value
    if (mode === 'image') opts.backgroundImageUrl = customBackgroundImageUrl.value
    if (mode === 'ai')    opts.aiBackgroundPrompt = aiBackgroundPrompt.value
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

      <!-- Pro hero (Photoroom-inspired) — outcome headline + KPI strip
           + how-it-works. Same dark theme, just denser and more
           commercial. Keeps the subscribe-notice + dbEmpty try-prompts
           hint below for demo users. -->
      <ProToolHero
        :badge="L('AI 商品攝影', 'AI Product Photography', 'AI 商品撮影', 'AI 제품 촬영', 'Fotografía AI')"
        :title="L('一鍵去背，打造工作室級商品圖', 'One-click background removal, studio-grade product photos', 'ワンクリック背景除去でスタジオ品質の商品画像へ', '한 번의 클릭으로 스튜디오급 제품 이미지', 'Recorte con un clic, fotos profesionales al instante')"
        :subtitle="L('業界最精準的 AI 去背（連透明商品都行）。把成本砍 90%，畫質分毫不減，無 AI 感。', 'Industry-leading AI cutout (yes, even transparent products). Cut photo costs 90% while keeping studio-grade quality — no AI look.', '業界トップクラスのAI切り抜き（透明商品も対応）。撮影コストを90%削減し、AIっぽさのないスタジオ品質。', '업계 최정밀 AI 누끼 따기(투명 제품도 지원). 촬영 비용 90% 절감, 스튜디오 품질 유지.', 'Recorte AI líder (incluso productos transparentes). Reduce 90% el coste sin perder calidad.')"
        :rating="{ score: '4.9', label: L('受 1,000+ 商家信賴', 'Trusted by 1,000+ sellers', '1,000+ 出店者に信頼', '1,000+ 셀러 신뢰', 'La confianza de 1,000+ vendedores') }"
        :trust-line="L('Amazon · Shopify · TikTok 規格一鍵匯出', 'One-click export to Amazon · Shopify · TikTok specs', 'Amazon · Shopify · TikTok 規格を一発エクスポート', 'Amazon · Shopify · TikTok 사양 한 번에 출력', 'Exporta a Amazon · Shopify · TikTok')"
        :stats="[
          { value: '-90%', label: L('拍攝成本', 'Photo cost', '撮影コスト', '촬영 비용', 'Coste fotográfico') },
          { value: '<5s', label: L('每張平均處理時間', 'Average time per image', '1枚あたり平均処理時間', '이미지당 평균 처리 시간', 'Tiempo medio por imagen') },
          { value: '+72%', label: L('刊登點擊率提升', 'Listing CTR uplift', '掲載クリック率向上', '리스팅 CTR 상승', 'Aumento de CTR') },
        ]"
        :steps="[
          { icon: '⬆️', title: L('上傳商品照片', 'Upload product photo', '商品写真をアップロード', '제품 사진 업로드', 'Sube la foto del producto'), body: L('支援 JPG / PNG / WebP，毛邊與透明商品都能處理', 'JPG / PNG / WebP — even fuzzy edges and transparent products', 'JPG/PNG/WebP対応 — 透明商品にも対応', 'JPG/PNG/WebP 지원, 투명 제품도 OK', 'JPG/PNG/WebP, incluso productos transparentes') },
          { icon: '✂️', title: L('AI 自動精準去背', 'AI cleanly removes the background', 'AIが背景を自動で精密除去', 'AI가 자동으로 정밀하게 누끼', 'IA recorta con precisión'), body: L('保留邊緣細節，免手動修圖', 'Edge detail preserved — no manual retouching', '輪郭ディテールを保持、手動修正不要', '엣지 디테일 유지, 수동 보정 불필요', 'Detalle de bordes preservado, sin retoque manual') },
          { icon: '⚡', title: L('替換背景 / 一鍵下載', 'Replace background or download', '背景差し替え or ダウンロード', '배경 변경 또는 다운로드', 'Cambia el fondo o descarga'), body: L('純白、品牌色、AI 場景隨意切換', 'Switch white, brand-colored, or AI scene backgrounds', '白背景・ブランドカラー・AIシーンを自由に切替', '흰색·브랜드 색·AI 씬 자유 전환', 'Cambia entre blanco, color o escena AI') },
        ]"
      />

      <!-- Subscribe Notice for Demo Users -->
      <div v-if="isDemoUser" class="text-center mb-8">
        <RouterLink to="/pricing" class="inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm hover:underline">
          {{ L('訂閱以解鎖完整功能', 'Subscribe to unlock full features', 'サブスク登録で全機能を解禁', '구독으로 전체 기능 해제', 'Suscríbete para desbloquear todo') }}
        </RouterLink>
      </div>

      <!-- DB Empty: Show try prompts -->
      <div v-if="dbEmpty && tryPrompts.length > 0" class="mb-8 p-4 rounded-xl" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
        <p class="text-sm text-dark-200 mb-2">{{ L('可試玩提示詞（資料庫尚無預生成）', 'Try prompts (no pre-generated results yet)', 'プロンプトを試す（まだ事前生成なし）', '프롬프트 시도 (사전 생성 없음)', 'Prueba prompts (sin pregenerados)') }}</p>
        <div class="flex flex-wrap gap-2">
          <span v-for="p in tryPrompts.slice(0, 5)" :key="p.id" class="px-2 py-1 rounded text-xs bg-dark-800 text-dark-200">{{ p.prompt }}</span>
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

              <!-- Paid users: Platform-aware Download -->
              <div v-if="!isDemoUser && resultImage" class="space-y-2">
                <label class="block text-xs text-dark-400">
                  {{ L('輸出尺寸 / 平台', 'Export size / platform', '出力サイズ / プラットフォーム', '출력 크기 / 플랫폼', 'Tamaño / plataforma') }}
                </label>
                <select
                  v-model="selectedPlatformSize"
                  class="w-full px-3 py-2 rounded-md text-sm"
                  style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #e8e8f0;"
                >
                  <option v-for="opt in PLATFORM_SIZE_OPTIONS" :key="opt.id || 'original'" :value="opt.id">
                    {{ isZh ? opt.labelZh : opt.labelEn }}
                  </option>
                </select>
                <button
                  type="button"
                  @click="downloadResized(resultImage)"
                  class="btn-primary w-full text-center block"
                >
                  {{ L('下載結果', 'Download Result', '結果をダウンロード', '결과 다운로드', 'Descargar resultado') }}
                </button>
              </div>
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

          <!-- AI text-to-background — generate a fresh scene from a
               natural-language prompt and composite the cutout on it.
               Same Flux T2I path used by the rest of the site. -->
          <div v-if="selectedBgMode === 'ai'" class="mb-3">
            <label class="block text-xs text-dark-400 mb-2">
              {{ L('AI 背景情境（中／英皆可）', 'AI background prompt (Chinese or English)', 'AI 背景プロンプト（中英対応）', 'AI 배경 프롬프트 (중·영)', 'Prompt de fondo AI (zh/en)') }}
            </label>
            <select
              v-model="selectedAiPresetId"
              @change="applyAiPreset"
              class="w-full mb-2 px-3 py-2 rounded-md text-sm"
              style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #e8e8f0;"
            >
              <option value="">{{ L('— 範例情境 —', '— Preset scenes —', '— プリセット —', '— 프리셋 —', '— Escenas —') }}</option>
              <option v-for="p in AI_BG_PROMPT_PRESETS" :key="p.id" :value="p.id">
                {{ isZh ? p.labelZh : p.labelEn }}
              </option>
            </select>
            <textarea
              v-model="aiBackgroundPrompt"
              rows="3"
              maxlength="500"
              :placeholder="L('例如：陽光灑落的熱帶海灘，柔和散景', 'e.g. sun-drenched tropical beach with soft bokeh', '例：陽光あふれる熱帯ビーチ、柔らかいボケ', '예: 햇살 가득한 열대 해변, 부드러운 보케', 'ej: playa tropical soleada con bokeh suave')"
              class="w-full px-3 py-2 rounded-md text-sm"
              style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #e8e8f0;"
            ></textarea>
            <p class="text-[11px] text-dark-500 mt-2">
              {{ L('AI 會即時生成背景場景，再把去背的商品合成在上面。約多花 5–10 秒。', 'The AI renders a scene and composites your cutout on top. Adds ~5–10s to the run.', 'AIがシーンを生成し、切り抜きを合成します。5〜10秒追加。', 'AI가 씬을 생성한 뒤 누끼와 합성합니다. 5–10초 추가.', 'La IA crea la escena y compone el recorte. +5–10s.') }}
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
              : selectedBgMode === 'ai'
              ? L('AI 會生成背景場景，再合成商品。', 'AI generates a scene and composites the cutout on top.', 'AIがシーンを生成し、合成します。', 'AI가 씬을 생성하고 합성합니다.', 'La IA genera la escena y compone el recorte.')
              : L('商品會合成在你提供的背景圖片上。', 'Composites the cutout onto your replacement image.', '提供した背景画像に合成します。', '제공한 배경 이미지에 합성됩니다.', 'Compone el recorte sobre tu imagen de reemplazo.') }}
          </p>
        </div>

        <!-- Remove Button and Credit Cost -->
        <div class="flex flex-col items-center gap-4 mt-4 pt-4" style="border-top: 1px solid rgba(255,255,255,0.06);">
          <CreditCost service="background_removal" />
          <button
            @click="removeBackground"
            :disabled="!uploadedImage || isProcessing || (selectedBgMode === 'image' && !customBackgroundImageUrl) || (selectedBgMode === 'ai' && !aiBackgroundPrompt.trim())"
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

      <!-- Batch mode — collapsible. Subscribers can drop up to 10
           images and the backend `/remove-bg/batch` endpoint applies
           the same background mode (color / image / AI prompt) chosen
           above. Demo users see a Subscribe CTA instead. -->
      <details v-if="!isDemoUser" class="mt-8 rounded-xl" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
        <summary class="cursor-pointer px-6 py-4 text-sm font-semibold flex items-center justify-between" style="color: #f5f5fa;">
          <span class="flex items-center gap-2">
            📦 {{ L('批次處理（最多 10 張）', 'Batch processing (up to 10)', 'バッチ処理（最大10枚）', '일괄 처리(최대 10장)', 'Lote (hasta 10)') }}
          </span>
          <span class="text-xs text-dark-400">{{ batchItems.length }}/{{ BATCH_MAX }}</span>
        </summary>

        <div class="px-6 pb-6 pt-2 space-y-4">
          <label class="block w-full px-4 py-6 rounded-md text-sm text-center cursor-pointer transition-colors"
                 style="background: #0f0f17; border: 1px dashed rgba(255,255,255,0.18); color: #c4c4d8;">
            {{ L('點此或拖曳選擇圖片（JPG / PNG / WebP）', 'Tap or drag to add images (JPG / PNG / WebP)', 'タップ／ドラッグで画像を追加', '탭 또는 드래그로 이미지 추가', 'Toca o arrastra para añadir') }}
            <input type="file" accept="image/jpeg,image/png,image/webp" multiple class="hidden" @change="onBatchPicked" />
          </label>

          <div v-if="batchItems.length" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
            <div v-for="item in batchItems" :key="item.id" class="relative rounded-lg overflow-hidden" style="background: #0f0f17; border: 1px solid rgba(255,255,255,0.06);">
              <div class="aspect-square">
                <img v-if="item.resultUrl" :src="item.resultUrl" class="w-full h-full object-cover" />
                <img v-else-if="item.url"   :src="item.url" class="w-full h-full object-cover opacity-60" />
                <div v-else class="w-full h-full flex items-center justify-center text-dark-400 text-xs px-2">
                  {{ item.file.name.slice(0, 24) }}
                </div>
              </div>
              <div class="absolute top-1 right-1 flex gap-1">
                <button @click="removeBatchItem(item.id)" class="w-5 h-5 rounded-full flex items-center justify-center text-xs"
                        style="background: rgba(0,0,0,0.6); color: #f5f5fa;">×</button>
              </div>
              <div class="absolute bottom-0 left-0 right-0 px-2 py-1 text-[10px] text-center"
                   :style="{
                     background: 'rgba(0,0,0,0.65)',
                     color: item.status === 'done' ? '#95de64' : item.status === 'error' ? '#ff7875' : '#d6d3d1',
                   }">
                {{ item.status === 'done' ? L('完成', 'Done', '完了', '완료', 'Listo')
                  : item.status === 'error' ? L('失敗', 'Failed', '失敗', '실패', 'Falló')
                  : item.status === 'uploaded' ? L('已上傳', 'Uploaded', 'アップロード済み', '업로드됨', 'Subido')
                  : L('等待中', 'Queued', '待機中', '대기 중', 'En cola') }}
              </div>
            </div>
          </div>

          <div class="flex flex-wrap gap-3">
            <button @click="runBatch"
                    :disabled="!batchItems.length || isBatchProcessing"
                    class="btn-primary px-6 py-2.5 text-sm font-semibold disabled:opacity-50">
              <span v-if="isBatchProcessing">{{ t('common.processing') }}</span>
              <span v-else>{{ L('開始批次處理', 'Run batch', 'バッチ開始', '일괄 시작', 'Iniciar lote') }}</span>
            </button>
            <button v-if="batchItems.some(i => i.resultUrl)"
                    @click="downloadAllBatchResults"
                    class="btn-secondary px-4 py-2.5 text-sm">
              {{ L('全部下載', 'Download all', '全てダウンロード', '모두 다운로드', 'Descargar todos') }}
            </button>
            <button v-if="batchItems.length"
                    @click="batchItems = []"
                    class="text-xs text-dark-400 hover:text-dark-50 self-center">
              {{ L('清空', 'Clear', 'クリア', '비우기', 'Limpiar') }}
            </button>
          </div>

          <p class="text-[11px] text-dark-500">
            {{ L('批次會套用上方所選的背景模式。AI 場景模式會生成一張共用背景，套用在全部結果上以維持視覺一致。', 'Batch applies the background mode chosen above. AI scene mode renders one shared background for the whole set so the results stay visually consistent.', '上で選択した背景モードがバッチに適用されます。AIシーンは1枚の共有背景を生成し、全結果に適用します。', '위에서 선택한 배경 모드가 일괄에 적용됩니다. AI 씬 모드는 공유 배경 1장을 생성해 전체에 적용.', 'Aplica el modo elegido. El modo IA crea un único fondo compartido.') }}
          </p>
        </div>
      </details>
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
