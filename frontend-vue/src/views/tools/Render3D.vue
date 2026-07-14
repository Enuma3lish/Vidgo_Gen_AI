<script setup lang="ts">
/**
 * Render3D (3D 效果圖 / 細化) — photorealistic interior render of an uploaded
 * floor plan, isometric, or room photo.
 *
 * UX rebuilt 2026-06-14 (owner spec): default to 細化模式 — the uploaded
 * image's STYLE and FURNITURE LAYOUT are locked, the user only tunes
 * lighting + per-surface texture (floor / ceiling / wall) with sensible
 * defaults. Magic mode unlocks a free-prompt textarea (layout still locked).
 *
 *   render      → photorealistic image only
 *   simulation  → 4 light×material variants of the same locked space
 *   video       → render + Kling 3.0/Omni growth animation
 *   video_3d    → + Trellis2 interactive .glb model
 *
 * Backend: POST /api/v1/interior/floorplan-to-video
 */
import { ref, computed, onMounted, watch, defineAsyncComponent } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore, useCreditsStore } from '@/stores'
import { useLocalized, useGenerationTask } from '@/composables'
import { toolsApi } from '@/api'
import {
  interiorApi,
  type FloorplanTier,
  type GrowthTier,
  type InteriorLightingTone,
  type SurfaceFloor,
  type SurfaceCeiling,
  type SurfaceWall,
  type SimulationVariant,
  type BatchRenderGroup,
} from '@/api/interior'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
// three.js (~150KB gz) lives inside ThreeViewer. Load it ONLY when an
// interactive .glb model actually needs rendering (the paid video_3d tier) —
// otherwise every visitor to this page downloaded three.js for nothing
// (perf audit #5). The template guards <ThreeViewer> behind `modelUrl`.
const ThreeViewer = defineAsyncComponent(() => import('@/components/tools/ThreeViewer.vue'))
import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import { extractApiError } from '@/utils/apiError'
import { dataURItoBlob } from '@/utils/dataUri'
import { downloadAsset } from '@/utils/downloadAsset'

const { t, locale } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

// ─── State ───────────────────────────────────────────────────────────
const imageInput = ref<string | undefined>(undefined)
const resultTier = ref<GrowthTier>('render')

// Mode: 細化 (detail, default) = layout & style locked, only surfaces + light.
//       魔法 (magic)            = free-prompt unlocked, layout still locked.
const magicMode = ref(false)

// Per-surface texture presets (細化 mode). Defaults applied so a first-time
// user can hit Generate without picking anything.
const surfaceFloor = ref<SurfaceFloor>('oak')
const surfaceCeiling = ref<SurfaceCeiling>('white')
const surfaceWall = ref<SurfaceWall>('white')

// Lighting preset (both modes).
const lightingTone = ref<InteriorLightingTone>('daylight')

// Magic-mode free prompt.
const magicPrompt = ref('')

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const renderImageUrl = ref<string | null>(null)
const videoUrl = ref<string | null>(null)
const modelUrl = ref<string | null>(null)
const simulationVariants = ref<SimulationVariant[]>([])
const expandedSimUrl = ref<string | null>(null)

// ─── 全屋批次 (whole-house batch, 2026-07-10 owner request) ───────────
// Upload one overall plan + per-room plans, apply ONE shared effect to all,
// 1-4 variants each; finished renders can be assembled into a tour video.
const batchMode = ref(false)
interface BatchItem {
  id: number
  file: File
  previewUrl: string
  label: string
  // Preflight classification state — the row shows a spinner while Gemini
  // decides, and switches to a "auto-detected" chip once the dropdown
  // has been pre-filled. Purely UX (no bearing on the server-side
  // classifier which still runs at Generate time).
  classifying?: boolean
  autoDetected?: boolean
}
const batchItems = ref<BatchItem[]>([])
let _batchIdSeq = 1
const batchFileInput = ref<HTMLInputElement | null>(null)
const variationCount = ref(1)
const batchGroups = ref<BatchRenderGroup[]>([])
const tourVideoUrl = ref<string | null>(null)
const tourGenerating = ref(false)
const BATCH_MAX_IMAGES = 8
const BATCH_MAX_TOTAL = 16

const roomLabelOptions = computed(() => [
  // 2026-07-14: 'auto' is the default. Backend classifies the image with Gemini
  // Vision so a bathroom / kitchen / bedroom plan renders as the right room
  // without the user having to change the dropdown per upload.
  { value: 'auto',           label: L('🪄 自動偵測房型', '🪄 Auto-detect room', '🪄 自動判定', '🪄 자동 감지', '🪄 Detección automática') },
  { value: 'overall',        label: L('整體平面圖', 'Overall plan', '全体間取り図', '전체 평면도', 'Plano general') },
  { value: 'living_room',    label: L('客廳', 'Living room', 'リビング', '거실', 'Salón') },
  { value: 'dining_room',    label: L('餐廳', 'Dining room', 'ダイニング', '다이닝룸', 'Comedor') },
  { value: 'kitchen',        label: L('廚房', 'Kitchen', 'キッチン', '주방', 'Cocina') },
  { value: 'master_bedroom', label: L('主臥', 'Master bedroom', '主寝室', '안방', 'Dorm. principal') },
  { value: 'bedroom',        label: L('臥室', 'Bedroom', '寝室', '침실', 'Dormitorio') },
  { value: 'bathroom',       label: L('浴室 / 廁所', 'Bathroom / Toilet', 'バスルーム / トイレ', '욕실 / 화장실', 'Baño / Aseo') },
  { value: 'home_office',    label: L('書房', 'Study / Home office', '書斎', '서재', 'Estudio') },
  { value: 'balcony',        label: L('陽台', 'Balcony', 'バルコニー', '발코니', 'Balcón') },
  { value: 'other',          label: L('其他', 'Other', 'その他', '기타', 'Otro') },
])
function roomLabelText(v?: string | null): string {
  return roomLabelOptions.value.find(o => o.value === v)?.label
    || v
    || L('房間', 'Room', '部屋', '방', 'Sala')
}

async function _fileToBase64(f: File): Promise<string | null> {
  try {
    return await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const s = String(reader.result || '')
        const comma = s.indexOf(',')
        resolve(comma >= 0 ? s.slice(comma + 1) : s)
      }
      reader.onerror = () => reject(reader.error)
      reader.readAsDataURL(f)
    })
  } catch {
    return null
  }
}

// Preflight-classify a single upload so the dropdown pre-fills with what
// Gemini sees (bathroom → "bathroom"), not the placeholder "auto". Runs in
// the background — a failure just leaves the label at 'auto', which the
// server will re-classify at Generate time (same behaviour as before).
async function _preflightClassify(item: BatchItem): Promise<void> {
  if (item.label !== 'auto') return
  item.classifying = true
  try {
    const b64 = await _fileToBase64(item.file)
    if (!b64) return
    const res = await interiorApi.classifyRoom({ image_base64: b64 })
    const detected = (res?.room_type || '').trim()
    // The batch dropdown accepts a fixed set of values — only apply the
    // detection when it maps to one; otherwise leave the label at 'auto'
    // and the server-side pass gets another shot.
    const allowed = new Set(roomLabelOptions.value.map(o => o.value))
    if (detected && allowed.has(detected)) {
      item.label = detected
      item.autoDetected = true
    }
  } catch { /* fail-open — server-side classify still runs at Generate */ }
  finally {
    item.classifying = false
  }
}

function onBatchFilesSelected(e: Event) {
  const files = Array.from((e.target as HTMLInputElement).files || [])
  const newlyAdded: BatchItem[] = []
  for (const f of files) {
    if (batchItems.value.length >= BATCH_MAX_IMAGES) break
    if (!f.type.startsWith('image/')) continue
    const item: BatchItem = {
      id: _batchIdSeq++,
      file: f,
      previewUrl: URL.createObjectURL(f),
      // First plan defaults to the overall layout; every subsequent one to
      // 'auto' so we can pre-classify below. Prior default 'living_room'
      // silently rendered bathrooms/kitchens/etc as living rooms whenever
      // users didn't touch the dropdown.
      label: batchItems.value.length === 0 && newlyAdded.length === 0 ? 'overall' : 'auto',
    }
    batchItems.value.push(item)
    newlyAdded.push(item)
  }
  ;(e.target as HTMLInputElement).value = ''
  // Fire-and-forget preflight classification per new item. Bounded
  // concurrency avoids opening 8 Gemini calls simultaneously.
  ;(async () => {
    const workers = 3
    let idx = 0
    async function next() {
      while (idx < newlyAdded.length) {
        const i = idx++
        await _preflightClassify(newlyAdded[i])
      }
    }
    await Promise.all(Array.from({ length: workers }, () => next()))
  })()
}
function removeBatchItem(id: number) {
  const it = batchItems.value.find(b => b.id === id)
  if (it) { try { URL.revokeObjectURL(it.previewUrl) } catch { /* noop */ } }
  batchItems.value = batchItems.value.filter(b => b.id !== id)
}

const renderUnitCost = computed(() => {
  const tier = tiers.value.find(tt => tt.id === 'render')
  return tier ? tier.credits : 40
})
const batchCreditCost = computed(() =>
  renderUnitCost.value * Math.max(1, batchItems.value.length) * variationCount.value
)
const batchOverCap = computed(() => batchItems.value.length * variationCount.value > BATCH_MAX_TOTAL)
const batchDisabled = computed(() => {
  if (!batchItems.value.length || batchOverCap.value) return true
  if (magicMode.value) return !magicPrompt.value.trim()
  return false
})

async function generateBatch() {
  if (batchDisabled.value || isRunning.value) return
  status.value = 'running'
  statusText.value = L(
    `批次生成中（${batchItems.value.length} 張 × ${variationCount.value}）… 並行處理,約 1-8 分鐘`,
    `Batch rendering (${batchItems.value.length} plans × ${variationCount.value})… ~1-8 min`,
    `一括生成中（${batchItems.value.length}枚 × ${variationCount.value}）… 約1〜8分`,
    `일괄 생성 중 (${batchItems.value.length}장 × ${variationCount.value})… 약 1~8분`,
    `Generando lote (${batchItems.value.length} × ${variationCount.value})… ~1-8 min`,
  )
  batchGroups.value = []
  tourVideoUrl.value = null
  try {
    const images: { image_url: string; room_label?: string }[] = []
    for (const it of batchItems.value) {
      const up = await toolsApi.uploadImage(it.file)
      images.push({ image_url: up.url, room_label: it.label })
    }
    const res = await interiorApi.floorplanBatchRender({
      images,
      variation_count: variationCount.value,
      magic_mode: magicMode.value,
      prompt: magicMode.value ? (magicPrompt.value.trim() || undefined) : undefined,
      surface_floor: surfaceFloor.value,
      surface_ceiling: surfaceCeiling.value,
      surface_wall: surfaceWall.value,
      lighting_tone: lightingTone.value,
      language: isZh.value ? 'zh' : 'en',
    })
    if (res.success && res.groups?.length) {
      batchGroups.value = res.groups
      status.value = 'done'
      statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
      if (res.credits_used) creditsStore.deductCredits(res.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      statusText.value = L('生成失敗', 'Failed', '生成失敗', '생성 실패', 'Fallo')
      uiStore.showError(res.error || L('批次生成失敗', 'Batch rendering failed', '一括生成に失敗', '일괄 생성 실패', 'Fallo del lote'))
    }
  } catch (e: any) {
    status.value = 'error'
    statusText.value = L('錯誤', 'Error', 'エラー', '오류', 'Error')
    uiStore.showError(extractApiError(e, L('批次生成失敗', 'Batch rendering failed', '一括生成に失敗', '일괄 생성 실패', 'Fallo del lote')))
  }
}

// 全屋影片: assemble EVERY successful render (all groups × all variants)
// into one tour video. Earlier revs only used g.results[0], so users who
// picked variation_count > 1 saw only one camera per room even though they
// paid for 2-4. Labels are parallel to the flattened URLs so the backend
// can burn each room's caption onto the matching clip.
type TourClip = { url: string; label: string }
const tourClips = computed<TourClip[]>(() =>
  batchGroups.value.flatMap(g =>
    g.results.map(url => ({ url, label: g.room_label || 'room' }))
  ),
)
const tourFailedCount = computed(() =>
  batchGroups.value.filter(g => g.results.length === 0).length,
)
const tourReady = computed(() => tourClips.value.length >= 2)
async function generateTourVideo() {
  if (!tourReady.value || tourGenerating.value) return
  tourGenerating.value = true
  try {
    const res = await interiorApi.houseTourVideo(
      tourClips.value.map(c => c.url),
      tourClips.value.map(c => c.label),
    )
    if (res.success && res.video_url) {
      tourVideoUrl.value = res.video_url
      if (res.credits_used) creditsStore.deductCredits(res.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      uiStore.showError(res.error || L('影片合成失敗', 'Video assembly failed', '動画合成に失敗', '영상 합성 실패', 'Fallo del vídeo'))
    }
  } catch (e: any) {
    uiStore.showError(extractApiError(e, L('影片合成失敗', 'Video assembly failed', '動画合成に失敗', '영상 합성 실패', 'Fallo del vídeo')))
  } finally {
    tourGenerating.value = false
  }
}

// ─── Catalog (tiers) from the backend ────────────────────────────────
const tiers = ref<FloorplanTier[]>([])
// P0-2: single source of truth for the in-flight task — recovers on timeout
// (background poll) and on page refresh (resume()). These long render/video
// jobs (8–25 min) routinely exceed the client timeout, so recovery matters.
// Recovery can only restore the primary image/video (the gallery row); the
// 3D model + simulation variants still appear in 作品庫.
const task = useGenerationTask('render3d')
function renderTaskResult(r: any) {
  if (r && r.success && (r.video_url || r.image_url || r.result_url)) {
    if (r.video_url) videoUrl.value = r.video_url
    if (r.image_url) renderImageUrl.value = r.image_url
    status.value = 'done'
    statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
    if (r.credits_used) creditsStore.deductCredits(r.credits_used)
  }
}
watch(() => task.result.value, (r) => renderTaskResult(r))
watch(() => task.phase.value, (p) => {
  if (p === 'error') {
    status.value = 'error'
    statusText.value = L('生成失敗', 'Failed', '生成失敗', '생성 실패', 'Generación fallida')
    uiStore.showError(task.error.value || L('生成失敗', 'Generation failed', '生成に失敗しました', '생성에 실패했습니다', 'La generación falló'))
  }
})

onMounted(async () => {
  if (task.resume()) {
    status.value = 'running'
    statusText.value = L('正在恢復先前的生成…', 'Resuming your previous generation…', '前回の生成を復元中…', '이전 생성을 복구하는 중…', 'Reanudando tu generación…')
  }
  try {
    const opts = await interiorApi.getFloorplanOptions()
    tiers.value = opts.tiers || []
  } catch {
    tiers.value = []
  }
})

// ─── Validation + cost ───────────────────────────────────────────────
const disabled = computed(() => !imageInput.value)
const isRunning = computed(() => status.value === 'running')
const isVideoTier = computed(() => resultTier.value === 'video' || resultTier.value === 'video_3d')
const isSimulationTier = computed(() => resultTier.value === 'simulation')

const creditCost = computed(() => {
  // Backend-published cost wins; the fallbacks below mirror the constants in
  // backend/app/api/v1/interior.py so the UI never shows a stale price.
  const tier = tiers.value.find(tt => tt.id === resultTier.value)
  if (tier) return tier.credits
  switch (resultTier.value) {
    case 'video_3d':  return 750
    case 'video':     return 600
    case 'simulation': return 140
    default:           return 40
  }
})

async function ensureImageUrl(): Promise<string | null> {
  if (!imageInput.value) return null
  if (!imageInput.value.startsWith('data:')) return imageInput.value
  const blob = dataURItoBlob(imageInput.value)
  if (!blob) return null
  const up = await toolsApi.uploadImage(blob as File)
  return up.url
}

async function generate() {
  if (batchMode.value) return generateBatch()
  if (disabled.value || isRunning.value) return
  status.value = 'running'
  statusText.value =
    resultTier.value === 'render'
      ? L('生成中… 約 30–90 秒', 'Generating… ~30–90s', '生成中… 約30〜90秒', '생성 중… 약 30~90초', 'Generando… ~30–90 s')
      : resultTier.value === 'simulation'
        ? L('同時生成 4 種光線+材質變體… 約 60–150 秒', 'Rendering 4 light×material variants… ~60–150s', '4種類のバリエーションを生成中… 約60〜150秒', '4가지 변형 동시 생성 중… 약 60~150초', 'Renderizando 4 variantes… ~60–150 s')
        : resultTier.value === 'video_3d'
          ? L('生成中… 影片 + 3D 模型約需 10-25 分鐘', 'Generating… video + 3D model, ~10-25 min', '生成中… 動画 + 3Dモデル、約10〜25分', '생성 중… 영상 + 3D 모델, 약 10~25분', 'Generando… vídeo + modelo 3D, ~10-25 min')
          : L('生成中… Kling 3.0 影片約需 8-20 分鐘', 'Generating… Kling 3.0 video, ~8-20 min', '生成中… Kling 3.0 動画、約8〜20分', '생성 중… Kling 3.0 영상, 약 8~20분', 'Generando… vídeo Kling 3.0, ~8-20 min')
  renderImageUrl.value = null
  videoUrl.value = null
  modelUrl.value = null
  simulationVariants.value = []

  // Upload BEFORE the task wrapper (the upload must not carry the client id).
  const imageUrl = await ensureImageUrl()
  if (!imageUrl) {
    status.value = 'error'
    uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida'))
    return
  }

  let result: any
  try {
    result = await task.run((cid) => interiorApi.floorplanToVideo({
      image_url: imageUrl,
      result_tier: resultTier.value,
      // Layout is ALWAYS locked under the new UX — preserve_original=true
      // applies to detail mode AND magic mode (magic only loosens style/materials).
      preserve_original: true,
      magic_mode: magicMode.value,
      surface_floor: surfaceFloor.value,
      surface_ceiling: surfaceCeiling.value,
      surface_wall: surfaceWall.value,
      lighting_tone: lightingTone.value,
      prompt: magicMode.value ? (magicPrompt.value.trim() || undefined) : undefined,
      language: isZh.value ? 'zh' : 'en',
    }, cid))
  } catch (e: any) {
    status.value = 'error'
    statusText.value = L('錯誤', 'Error', 'エラー', '오류', 'Error')
    uiStore.showError(extractApiError(e, L('生成失敗', 'Generation failed', '生成に失敗しました', '생성에 실패했습니다', 'La generación falló')))
    return
  }

  if (result === null) {
    // Timed out client-side but the backend is still running — DON'T error.
    status.value = 'running'
    statusText.value = L('仍在生成中，完成後會存入「我的作品」。', 'Still generating — it will be saved to My Works when done.', '生成中です。完了後「マイ作品」に保存されます。', '생성 중입니다. 완료되면 내 작품에 저장됩니다.', 'Generando; se guardará en Mis Trabajos.')
    return
  }
  if (task.suggestGallery.value) {
    // Recovered via background polling — renderTaskResult already applied the
    // primary image/video (the full multi-tier result is in 作品庫).
    return
  }

  // Direct happy path — full multi-tier result handling (unchanged).
  {
    const okSimulation = isSimulationTier.value && (result?.simulation_variants?.length || 0) > 0
    const okVideo = isVideoTier.value && !!result.video_url
    const okRender = !isSimulationTier.value && !isVideoTier.value && !!result.render_image_url
    const ok = result?.success && (okSimulation || okVideo || okRender)
    if (ok) {
      renderImageUrl.value = result.render_image_url || null
      videoUrl.value = result.video_url || null
      modelUrl.value = result.model_url || null
      simulationVariants.value = result.simulation_variants || []
      status.value = 'done'
      statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      if (resultTier.value === 'video_3d' && !result.model_url) {
        uiStore.showError(L(
          '影片已生成,但 3D 模型建立失敗,已退回 3D 部分點數。',
          'Video generated, but the 3D model failed — the 3D portion was refunded.',
          '動画は生成されましたが、3Dモデルの作成に失敗しました。3D分のクレジットは返却済みです。',
          '영상은 생성되었지만 3D 모델 생성에 실패하여 3D 부분 크레딧을 환불했습니다.',
          'Vídeo generado, pero el modelo 3D falló — se reembolsó la parte 3D.',
        ))
      } else {
        uiStore.showSuccess(t('common.success') || 'Success')
      }
    } else {
      status.value = 'error'
      statusText.value = L('生成失敗', 'Failed', '生成失敗', '생성 실패', 'Generación fallida')
      uiStore.showError(result?.error || L('生成失敗', 'Generation failed', '生成に失敗しました', '생성에 실패했습니다', 'La generación falló'))
    }
  }
}

const pageTitle = computed(() => L('3D 效果圖（細化）', '3D Render (Refine)', '3D 効果図（詳細化）', '3D 효과도 (디테일)', 'Render 3D (refinado)'))
const pageSubtitle = computed(() => L(
  '上傳平面配置圖、立體圖或房間照片 — AI 會鎖定原始配置與家具,只依您挑的光線與牆/地/天花板材質進行寫實渲染;切換到魔法模式可自由 prompt。',
  'Upload a floor plan, isometric, or room photo — AI locks the original layout and furniture and only restyles light + floor/ceiling/wall textures. Switch to magic mode for free prompting.',
  '間取り図やレンダリングをアップロード — AIが元のレイアウトと家具を固定し、光と床/天井/壁の素材だけを再スタイル化。マジックモードで自由プロンプトも可能。',
  '평면도나 방 사진을 올리면 AI가 원래 배치와 가구를 잠그고 조명·바닥/천장/벽 재질만 다시 스타일링합니다. 매직 모드에서 자유 프롬프트도 가능합니다.',
  'Sube un plano o foto; la IA bloquea la distribución y muebles, y solo reestiliza luz + texturas. Modo mágico para escribir libremente.',
))
const hasResult = computed(() => {
  if (batchMode.value) return batchGroups.value.length > 0
  // Tier-specific checks first, but ALWAYS fall through to "anything we
  // hold" (D8, 2026-07-10): resultTier isn't persisted across a refresh, so
  // recovery of a video/video_3d job landed videoUrl while resultTier was
  // back at its 'render' default — the strict tier check returned false and
  // the result pane stayed empty even though the video was recovered.
  if (isSimulationTier.value && simulationVariants.value.length > 0) return true
  if (isVideoTier.value && videoUrl.value) return true
  return !!(renderImageUrl.value || videoUrl.value || simulationVariants.value.length > 0)
})
</script>

<template>
  <PiapiPlayground
    :eta-seconds="batchMode ? 240 : resultTier === 'render' ? 60 : resultTier === 'simulation' ? 120 : resultTier === 'video_3d' ? 1200 : 720"
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :status="status"
    :status-text="statusText"
    :credit-cost="batchMode ? batchCreditCost : creditCost"
    :generate-label="L('開始生成', 'Generate', '生成開始', '생성 시작', 'Generar')"
    :generate-label-running="L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…')"
    :disabled="batchMode ? batchDisabled : disabled"
    @generate="generate"
  >
    <template #inputs>
      <!-- What this page supports (owner request 2026-06-16): make the four
           output tiers explicit so users know the page does more than a still. -->
      <div class="rounded-lg px-3 py-2.5 text-[11px] leading-relaxed"
        style="background: rgba(124,58,237,0.08); border:1px solid rgba(124,58,237,0.2); color:#c4b5fd;">
        <div class="font-semibold mb-1" style="color:#ddd6fe;">{{ L('本頁支援', 'This page supports', 'このページの機能', '이 페이지가 지원', 'Esta página admite') }}</div>
        <ul class="space-y-0.5" style="list-style:none; padding:0; margin:0;">
          <li>🖼️ {{ L('3D 效果圖（細化）— 鎖定原配置,只調光線與材質的寫實渲染', '3D render (refine) — photorealistic, layout locked, light + materials only', '3D効果図(詳細化)— レイアウト固定で光と素材のみ', '3D 효과도(디테일) — 배치 고정, 조명·재질만', 'Render 3D (refinado) — distribución bloqueada') }}</li>
          <li>🎚️ {{ L('4 種光線 × 材質模擬,一次比較', '4 lighting × material simulations to compare', '4種のライト×素材シミュレーション', '4가지 조명×재질 시뮬레이션', '4 simulaciones de luz × material') }}</li>
          <li>🎬 {{ L('成長影片 — 由平面「長出」3D 房間（Kling 3.0/Omni）', 'Growth video — the plan “grows” into the 3D room (Kling 3.0/Omni)', '成長動画 — 平面が3D空間へ(Kling 3.0/Omni)', '성장 영상 — 평면이 3D로(Kling 3.0/Omni)', 'Vídeo de crecimiento (Kling 3.0/Omni)') }}</li>
          <li>🧊 {{ L('可旋轉 3D 模型（Trellis2 .glb,360° 檢視）', 'Rotatable 3D model (Trellis2 .glb, 360° view)', '回転可能な3Dモデル(Trellis2 .glb)', '회전 가능한 3D 모델(Trellis2 .glb)', 'Modelo 3D giratorio (Trellis2 .glb)') }}</li>
        </ul>
      </div>

      <!-- 單張 / 全屋批次 mode toggle (2026-07-10 owner request) -->
      <div>
        <label class="pp-field-label">{{ L('生成模式', 'Generation mode', '生成モード', '생성 모드', 'Modo') }}</label>
        <div class="grid grid-cols-2 gap-2">
          <button type="button" @click="batchMode = false"
            class="p-3 rounded-lg text-left transition-colors"
            :style="!batchMode
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'
              : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'"
          >
            <div class="text-[13px] font-semibold mb-1">{{ !batchMode ? '✓ ' : '' }}{{ L('單張', 'Single', '1枚', '단일', 'Única') }}</div>
            <div class="text-[11px] leading-snug opacity-80">{{ L('一張圖 → 效果圖 / 模擬 / 影片 / 3D 模型。', 'One image → render / simulation / video / 3D model.', '1枚 → 効果図/シミュレーション/動画/3Dモデル。', '한 장 → 효과도/시뮬레이션/영상/3D 모델.', 'Una imagen → render / simulación / vídeo / 3D.') }}</div>
          </button>
          <button type="button" @click="batchMode = true"
            class="p-3 rounded-lg text-left transition-colors"
            :style="batchMode
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'
              : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'"
          >
            <div class="text-[13px] font-semibold mb-1">{{ batchMode ? '✓ ' : '' }}{{ L('全屋批次', 'Whole house', '全戸一括', '전체 일괄', 'Casa completa') }}</div>
            <div class="text-[11px] leading-snug opacity-80">{{ L('整體 + 各房間平面圖,同一效果一次生成,可合成全屋影片。', 'Overall + per-room plans, one shared effect, plus a whole-house tour video.', '全体+各部屋の間取り図を同一効果で一括生成、全戸動画も。', '전체+각 방 평면도를 동일 효과로 일괄 생성, 투어 영상까지.', 'Plano general + habitaciones, un solo efecto, y vídeo de la casa.') }}</div>
          </button>
        </div>
      </div>

      <template v-if="!batchMode">
        <div>
          <label class="pp-field-label">{{ L('平面圖 / 房間照片 *', 'Floor plan / room photo *', '間取り図・部屋写真 *', '평면도 / 방 사진 *', 'Plano / foto *') }}</label>
          <ImageUploader
            tool-type="room_redesign"
            v-model="imageInput"
            :label="L('點擊或拖放圖片', 'Click or drag an image', 'クリックまたはドラッグ', '클릭 또는 드래그', 'Haz clic o arrastra')"
          />
        </div>
      </template>

      <template v-else>
        <div>
          <label class="pp-field-label">{{ L('平面配置圖（可多張）*', 'Floor plans (multiple) *', '間取り図（複数可）*', '평면도 (여러 장) *', 'Planos (varios) *') }}</label>
          <input type="file" accept="image/*" multiple class="hidden" ref="batchFileInput" @change="onBatchFilesSelected" />
          <button type="button" @click="batchFileInput?.click()"
            class="w-full p-4 rounded-lg text-[13px] transition-colors"
            style="background:#0a0a0f; border:1px dashed rgba(124,58,237,0.5); color:#c4b5fd;"
            :disabled="batchItems.length >= BATCH_MAX_IMAGES"
          >
            + {{ L(`加入平面圖（可多選,最多 ${BATCH_MAX_IMAGES} 張）`, `Add floor plans (multi-select, up to ${BATCH_MAX_IMAGES})`, `間取り図を追加（最大${BATCH_MAX_IMAGES}枚）`, `평면도 추가 (최대 ${BATCH_MAX_IMAGES}장)`, `Añadir planos (hasta ${BATCH_MAX_IMAGES})`) }}
          </button>
          <div v-if="batchItems.length" class="mt-2 space-y-2">
            <div v-for="it in batchItems" :key="it.id"
              class="flex items-center gap-2 p-2 rounded-lg"
              style="background:#0a0a0f; border:1px solid rgba(255,255,255,0.08);">
              <img :src="it.previewUrl" class="w-14 h-14 object-cover rounded flex-shrink-0" />
              <div class="flex-1 min-w-0 flex flex-col gap-1">
                <select v-model="it.label" @change="it.autoDetected = false" class="pp-select w-full">
                  <option v-for="o in roomLabelOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
                </select>
                <!-- Preflight status: spinner while Gemini looks, then a
                     chip once the dropdown was pre-filled. Cleared as soon
                     as the user overrides the choice. -->
                <span v-if="it.classifying" class="text-[10px]" style="color:#94949f;">
                  🔍 {{ L('AI 判斷中…', 'Detecting…', '判定中…', '감지 중…', 'Detectando…') }}
                </span>
                <span v-else-if="it.autoDetected" class="text-[10px]" style="color:#a78bfa;">
                  ✨ {{ L('AI 自動偵測 — 若不正確請手動選擇', 'Auto-detected — override if wrong', 'AIが自動判定 — 誤りは手動で変更', 'AI 자동 감지 — 틀리면 수동 선택', 'Autodetectado — corrige si es erróneo') }}
                </span>
              </div>
              <button type="button" @click="removeBatchItem(it.id)" class="px-2 text-lg flex-shrink-0" style="color:#f87171;">✕</button>
            </div>
          </div>
          <p class="pp-field-help">{{ L('建議:1 張整體平面圖 + 各房間平面圖(客廳、餐廳、廚房、浴室…)。房型預設為「自動偵測」— 系統會判斷每張圖是哪種空間;所有圖片會套用下方同一組效果,確保整屋風格一致。', 'Tip: one overall plan + per-room plans (living, dining, kitchen, bathroom…). Room type defaults to Auto — the server classifies each image. Every plan uses the SAME effect below, so the whole house stays consistent.', 'ヒント:全体図1枚+各部屋の図。房型はデフォルトで自動判定、全て下の同一効果を適用し、家全体の統一感を保証。', '팁: 전체도 1장 + 각 방 평면도. 방 유형은 자동 감지가 기본이며 모두 아래 동일 효과가 적용되어 집 전체 스타일이 일치합니다.', 'Consejo: un plano general + planos por habitación. El tipo de sala se detecta automáticamente. Todos usan el MISMO efecto de abajo.') }}</p>
        </div>

        <div>
          <label class="pp-field-label">{{ L('每張圖生成數量（1-4）', 'Results per plan (1-4)', '1枚あたりの生成数（1-4）', '장당 생성 수 (1-4)', 'Resultados por plano (1-4)') }}</label>
          <div class="grid grid-cols-4 gap-2">
            <button v-for="n in 4" :key="n" type="button" @click="variationCount = n"
              class="py-2 rounded-lg text-[13px] font-semibold transition-colors"
              :style="variationCount === n
                ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'
                : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'"
            >{{ n }}</button>
          </div>
          <p v-if="batchOverCap" class="pp-field-help" style="color:#f87171;">
            {{ L(`張數 × 生成數不可超過 ${BATCH_MAX_TOTAL},請減少張數或生成數。`, `plans × results must be ≤ ${BATCH_MAX_TOTAL} — reduce one of them.`, `枚数×生成数は${BATCH_MAX_TOTAL}以下にしてください。`, `장수×생성수는 ${BATCH_MAX_TOTAL} 이하여야 합니다.`, `planos × resultados debe ser ≤ ${BATCH_MAX_TOTAL}.`) }}
          </p>
          <p v-else class="pp-field-help">
            {{ L(`共 ${batchItems.length || 0} 張 × ${variationCount} = ${(batchItems.length || 0) * variationCount} 個渲染`, `Total: ${batchItems.length || 0} × ${variationCount} = ${(batchItems.length || 0) * variationCount} renders`, `合計 ${(batchItems.length || 0) * variationCount} レンダー`, `총 ${(batchItems.length || 0) * variationCount}개 렌더`, `Total: ${(batchItems.length || 0) * variationCount} renders`) }}
          </p>
        </div>
      </template>

      <div v-if="!batchMode">
        <label class="pp-field-label">{{ L('想要的結果 *', 'What result do you want? *', '希望する結果 *', '원하는 결과 *', '¿Qué resultado quieres? *') }}</label>
        <select v-model="resultTier" class="pp-select">
          <option value="render">{{ L('3D 效果圖（單張）', '3D render (single image)', '3D効果図（1枚）', '3D 효과도 (단일)', 'Render 3D (única)') }}</option>
          <option value="simulation">{{ L('模擬演示 / 試色（一次 4 張變體）', 'Simulation / Try colors (4 variants in one call)', 'シミュレーション（4種類のバリエーション）', '시뮬레이션 / 시험 (4가지 변형)', 'Simulación / Prueba (4 variantes)') }}</option>
          <option value="video">{{ L('效果圖 + 成長動畫影片', 'Render + growth video', '効果図 + 成長アニメ動画', '효과도 + 성장 영상', 'Render + vídeo de crecimiento') }}</option>
          <option value="video_3d">{{ L('效果圖 + 影片 + 可旋轉 3D 模型', 'Render + video + rotatable 3D model', '効果図 + 動画 + 回転可能3Dモデル', '효과도 + 영상 + 회전 3D 모델', 'Render + vídeo + modelo 3D giratorio') }}</option>
        </select>
        <p class="pp-field-help">
          {{
            resultTier === 'render'      ? L('單張寫實 3D 渲染,速度最快、點數最省。', 'A single photoreal render — fastest and cheapest.', '1枚のフォトリアル3Dレンダー。最速・最安。', '단일 사실적 렌더 — 가장 빠르고 저렴.', 'Un único render fotorrealista: lo más rápido y económico.')
          : resultTier === 'simulation'  ? L('同一空間 4 種光線+材質組合,一次比對「早晨」「黃昏」「陰天」「金色時刻」。', 'Four light×material combos of the SAME space side-by-side: morning, evening, overcast, golden hour.', '同じ空間を「朝」「夕方」「曇天」「ゴールデンアワー」の4パターンで生成。', '동일 공간을 아침/저녁/흐림/골든아워 4가지로 동시 생성.', '4 combinaciones luz×material del mismo espacio: mañana, tarde, nublado, hora dorada.')
          : resultTier === 'video_3d'    ? L('效果圖 + 影片 + Trellis2 .glb 模型,可 360° 旋轉。', 'Render + video + a Trellis2 .glb model you can rotate 360°.', '効果図 + 動画 + 360°回転できる Trellis2 .glb モデル。', '효과도 + 영상 + 360° 회전 가능한 Trellis2 .glb 모델.', 'Render + vídeo + modelo .glb Trellis2 girable 360°.')
                                         : L('效果圖 + Kling 3.0 含音訊的成長動畫影片。', 'Render + Kling 3.0 growth animation with audio.', '効果図 + 音声付き Kling 3.0 成長アニメ。', '효과도 + 오디오 포함 Kling 3.0 성장 애니메이션.', 'Render + animación de crecimiento Kling 3.0 con audio.')
          }}
        </p>
      </div>

      <!-- 細化 / 魔法 mode toggle -->
      <div>
        <label class="pp-field-label">{{ L('編輯模式', 'Edit Mode', '編集モード', '편집 모드', 'Modo de edición') }}</label>
        <div class="grid grid-cols-2 gap-2">
          <button type="button" @click="magicMode = false"
            class="p-3 rounded-lg text-left transition-colors"
            :style="!magicMode
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'
              : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'"
          >
            <div class="text-[13px] font-semibold mb-1">{{ !magicMode ? '✓ ' : '' }}{{ L('細化模式', 'Refine', '詳細モード', '디테일', 'Detalle') }}</div>
            <div class="text-[11px] leading-snug opacity-80">{{ L('鎖定家具配置與風格,只調光與牆/地/天花板材質。', 'Lock layout & style; only tweak light + floor/ceiling/wall textures.', 'レイアウトとスタイルを固定、光と床/天井/壁の素材だけ調整。', '레이아웃·스타일 잠금, 조명·바닥/천장/벽 재질만 조정.', 'Bloquea distribución y estilo; ajusta solo luz y texturas.') }}</div>
          </button>
          <button type="button" @click="magicMode = true"
            class="p-3 rounded-lg text-left transition-colors"
            :style="magicMode
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'
              : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'"
          >
            <div class="text-[13px] font-semibold mb-1">{{ magicMode ? '✓ ' : '' }}{{ L('魔法模式', 'Magic Mode', 'マジックモード', '매직 모드', 'Modo mágico') }}</div>
            <div class="text-[11px] leading-snug opacity-80">{{ L('自由 prompt 重新風格化;家具配置仍鎖定,不會憑空長出。', 'Free prompt restyling; furniture layout still locked, never invented.', '自由プロンプトで再スタイル化。家具配置は固定で創作しない。', '자유 프롬프트로 재스타일링. 가구 배치는 고정.', 'Re-estilizado con prompt libre; los muebles siguen bloqueados.') }}</div>
          </button>
        </div>
      </div>

      <!-- Lighting preset (both modes) -->
      <div>
        <label class="pp-field-label">{{ L('光線氛圍', 'Lighting', '照明', '조명', 'Iluminación') }}</label>
        <select v-model="lightingTone" class="pp-select">
          <option value="daylight">{{ L('自然日光', 'Natural daylight', '自然光', '자연광', 'Luz natural') }}</option>
          <option value="warm_evening">{{ L('暖色傍晚', 'Warm evening', '暖色夕方', '따뜻한 저녁', 'Atardecer cálido') }}</option>
          <option value="golden_hour">{{ L('金色時刻', 'Golden hour', 'ゴールデンアワー', '골든아워', 'Hora dorada') }}</option>
          <option value="overcast_soft">{{ L('陰天柔光', 'Overcast soft', '曇り柔光', '흐린 부드러움', 'Nublado suave') }}</option>
          <option value="dramatic_spotlight">{{ L('戲劇聚光', 'Dramatic spotlight', 'ドラマチック', '드라마틱', 'Foco dramático') }}</option>
          <option value="night">{{ L('夜景', 'Night', '夜景', '야간', 'Nocturno') }}</option>
        </select>
        <!-- Batch mode: one lighting choice is applied to every image in the
             batch — surface presets (below) are the same story. This note
             makes the "shared effect" contract visible instead of implicit. -->
        <p v-if="batchMode" class="pp-field-help" style="color:#c4b5fd;">
          🏠 {{ L(
            '本組光線氛圍將套用到全屋所有圖片(同一組地板、天花板、牆面材質也是如此)。',
            'This lighting is applied to every image in the batch (the floor / ceiling / wall presets below are also shared).',
            'この照明は全画像に共通適用(下の床/天井/壁の設定も同様)。',
            '이 조명은 배치의 모든 이미지에 동일 적용됩니다 (아래 바닥/천장/벽 설정도 동일).',
            'Esta iluminación se aplica a cada imagen del lote (los ajustes de suelo/techo/paredes también son compartidos).',
          ) }}
        </p>
      </div>

      <!-- Surface presets (細化 mode only) -->
      <template v-if="!magicMode">
        <div>
          <label class="pp-field-label">{{ L('地板材質', 'Floor texture', '床素材', '바닥 재질', 'Suelo') }}</label>
          <select v-model="surfaceFloor" class="pp-select">
            <option value="oak">{{ L('暖色橡木地板', 'Warm oak hardwood', '暖色オーク', '웜 오크', 'Roble cálido') }}</option>
            <option value="walnut">{{ L('深色胡桃木地板', 'Dark walnut hardwood', 'ダークウォルナット', '다크 월넛', 'Nogal oscuro') }}</option>
            <option value="marble">{{ L('白色大理石', 'White marble', '白大理石', '화이트 마블', 'Mármol blanco') }}</option>
            <option value="concrete">{{ L('拋光水泥', 'Polished concrete', '磨きコンクリート', '폴리시드 콘크리트', 'Hormigón pulido') }}</option>
            <option value="terrazzo">{{ L('磨石子（Terrazzo）', 'Terrazzo', 'テラゾー', '테라조', 'Terrazo') }}</option>
            <option value="tile">{{ L('啞光瓷磚', 'Matte porcelain tile', 'マット磁器タイル', '매트 포세린 타일', 'Porcelánico mate') }}</option>
          </select>
        </div>
        <div>
          <label class="pp-field-label">{{ L('天花板', 'Ceiling', '天井', '천장', 'Techo') }}</label>
          <select v-model="surfaceCeiling" class="pp-select">
            <option value="white">{{ L('純白', 'White', '白', '화이트', 'Blanco') }}</option>
            <option value="warm_white">{{ L('暖白', 'Warm white', '暖白', '웜 화이트', 'Blanco cálido') }}</option>
            <option value="exposed_beam">{{ L('裸露木樑', 'Exposed wood beams', '露出木梁', '노출 목재 빔', 'Vigas de madera') }}</option>
            <option value="industrial">{{ L('工業裸頂', 'Industrial exposed', '工業むき出し', '인더스트리얼', 'Industrial') }}</option>
          </select>
        </div>
        <div>
          <label class="pp-field-label">{{ L('牆面', 'Walls', '壁', '벽', 'Paredes') }}</label>
          <select v-model="surfaceWall" class="pp-select">
            <option value="white">{{ L('純白漆', 'White paint', '白塗装', '화이트 페인트', 'Pintura blanca') }}</option>
            <option value="warm_grey">{{ L('暖灰石灰漆', 'Warm grey limewash', 'ウォームグレーライムウォッシュ', '웜 그레이 라임워시', 'Cal gris cálido') }}</option>
            <option value="feature_brick">{{ L('磚牆主牆', 'Feature brick wall', 'レンガアクセント', '벽돌 포인트벽', 'Muro de ladrillo') }}</option>
            <option value="wood_panel">{{ L('木板主牆', 'Wood-panel feature wall', '木パネル', '우드 패널', 'Panel de madera') }}</option>
          </select>
        </div>
      </template>

      <!-- Magic mode free prompt -->
      <template v-else>
        <div>
          <label class="pp-field-label">{{ L('Prompt（魔法模式）', 'Prompt (magic mode)', 'プロンプト（マジック）', '프롬프트 (매직)', 'Prompt (mágico)') }}</label>
          <textarea v-model="magicPrompt" rows="4" maxlength="1000" class="pp-textarea"
            :placeholder="L('描述您想要的風格、材質、氛圍。例：日式侘寂、米色亞麻、藤編家具、紙燈籠。家具配置會自動保留。', 'Describe the style, materials, mood you want. e.g.: Japandi wabi-sabi, beige linen, rattan, paper lanterns. Layout stays locked automatically.', 'スタイル・素材・雰囲気を自由に。例：和モダン、麻、籐、和紙照明。レイアウトは固定されます。', '원하는 스타일·재질·분위기. 예: 와비사비, 베이지 린넨, 라탄, 종이 등. 배치는 자동 잠금.', 'Describe estilo, materiales, atmósfera. p. ej.: japandi, lino beige, ratán, faroles. La distribución queda bloqueada.')"></textarea>
          <p class="pp-field-help">{{ L('魔法模式仍然鎖定家具與牆面配置 — 不會憑空長出新門窗或家具,只會重新風格化現有空間。', 'Magic mode still locks walls and furniture — no invented doors, windows, or pieces; only restyles what is already there.', 'マジックモードでも壁と家具は固定。新たな扉・窓・家具は生成されず、既存空間の再スタイル化のみ。', '매직 모드도 벽·가구를 잠급니다. 새 문/창/가구 생성 없이 기존 공간만 재스타일링.', 'El modo mágico bloquea muros y muebles: no inventa, solo re-estiliza lo existente.') }}</p>
          <!-- Batch + magic: reassure the user that the ONE prompt they typed
               is what every room sees. The backend now wraps it in an
               explicit "apply this SAME directive to every room" clause. -->
          <p v-if="batchMode" class="pp-field-help" style="color:#c4b5fd;">
            ✨ {{ L(
              '此 prompt 會以同一段文字套用到全屋每一張圖 — 光線、地板、天花板、牆面材質等,將整批一致。',
              'This prompt is applied uniformly to every image in the batch — same lighting, floor, ceiling, and wall treatment across the whole house.',
              'このプロンプトは全ての画像に同一の指示として適用されます — 照明・床・天井・壁の質感は全戸で統一。',
              '이 프롬프트는 모든 이미지에 동일하게 적용됩니다 — 조명·바닥·천장·벽 재질이 전체적으로 통일됩니다.',
              'Este prompt se aplica idénticamente a cada imagen — misma iluminación, suelo, techo y paredes en toda la casa.',
            ) }}
          </p>
        </div>
      </template>
    </template>

    <template v-if="hasResult" #result>
      <!-- 全屋批次 results: per-room groups + whole-house tour video -->
      <template v-if="batchMode && batchGroups.length">
        <div class="w-full max-w-[720px] space-y-4">
          <div v-for="(g, gi) in batchGroups" :key="gi" class="space-y-1.5">
            <div class="text-[12px] font-semibold" style="color:#ddd6fe;">
              {{ roomLabelText(g.room_label) }}
              <span v-if="!g.results.length" style="color:#f87171;">
                — {{ L('生成失敗（該部分已退點）', 'failed (that portion was refunded)', '生成失敗（該当分は返却済み）', '생성 실패 (해당 부분 환불됨)', 'falló (esa parte fue reembolsada)') }}
              </span>
            </div>
            <div v-if="g.results.length" class="grid grid-cols-2 gap-2">
              <img v-for="u in g.results" :key="u" :src="u" loading="lazy"
                class="w-full rounded-lg" style="border:1px solid rgba(124,58,237,0.25);" />
            </div>
          </div>

          <div class="pt-3 flex flex-col items-center gap-3" style="border-top:1px solid rgba(255,255,255,0.08);">
            <!-- Partial-failure warning: without this the tour would silently
                 skip failed rooms and the user would think "the video is
                 missing my inputs". Now they see the mismatch upfront. -->
            <div v-if="tourFailedCount > 0 && tourReady"
              class="w-full rounded-lg px-3 py-2 text-[11px] leading-relaxed"
              style="background: rgba(248,113,113,0.10); border:1px solid rgba(248,113,113,0.35); color:#fecaca;">
              ⚠ {{ L(
                `${tourFailedCount} 個房間渲染失敗,影片將只包含 ${tourClips.length} 段成功的畫面。失敗部分已退點。`,
                `${tourFailedCount} room(s) failed to render — the tour will only include the ${tourClips.length} successful clips. Failed portion was refunded.`,
                `${tourFailedCount}部屋の生成に失敗しました。動画は成功した${tourClips.length}カットのみを含みます。失敗分は返金済み。`,
                `${tourFailedCount}개 방 렌더링 실패 — 영상은 성공한 ${tourClips.length}개만 포함됩니다. 실패분 환불 완료.`,
                `${tourFailedCount} habitación(es) fallaron — el vídeo solo incluirá los ${tourClips.length} clips correctos. Se reembolsó la parte fallida.`
              ) }}
            </div>
            <button type="button" @click="generateTourVideo"
              :disabled="!tourReady || tourGenerating"
              class="px-6 py-2.5 rounded-xl text-[13px] font-semibold transition-colors"
              :style="(!tourReady || tourGenerating)
                ? 'background:#141420; color:#94949f; border:1px solid rgba(255,255,255,0.06); opacity:0.6;'
                : 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'"
            >
              {{ tourGenerating
                ? L('全屋影片合成中…', 'Assembling tour video…', '全戸動画を合成中…', '투어 영상 합성 중…', 'Montando el vídeo…')
                : L(`🎬 生成全屋導覽影片(${tourClips.length} 段,20 點)`, `🎬 Generate whole-house tour video (${tourClips.length} clips, 20 cr)`, `🎬 全戸ツアー動画(${tourClips.length}カット、20pt)`, `🎬 전체 투어 영상 (${tourClips.length}개, 20크레딧)`, `🎬 Generar vídeo (${tourClips.length} clips, 20 cr)`) }}
            </button>
            <p v-if="!tourReady" class="text-[11px]" style="color:#94949f;">
              {{ L('至少需要 2 個房間的成功渲染才能合成影片。', 'Needs successful renders for at least 2 rooms.', '2部屋以上の成功レンダーが必要です。', '최소 2개 방의 성공 렌더가 필요합니다.', 'Se necesitan al menos 2 habitaciones renderizadas.') }}
            </p>
            <video v-if="tourVideoUrl" :src="tourVideoUrl" controls autoplay loop
              class="max-w-full rounded-lg" style="max-height: 400px;" />
            <button v-if="tourVideoUrl" type="button"
              @click="downloadAsset(tourVideoUrl!, `vidgo_house_tour_${Date.now()}.mp4`)"
              class="text-[12px]" style="color:#a78bfa;">
              ⬇ {{ L('下載全屋影片', 'Download tour video', 'ツアー動画をダウンロード', '투어 영상 다운로드', 'Descargar vídeo') }}
            </button>
          </div>
        </div>
      </template>

      <!-- Simulation tier: 4-up grid -->
      <template v-else-if="isSimulationTier && simulationVariants.length">
        <div class="grid grid-cols-2 gap-2 w-full max-w-[640px]">
          <div v-for="v in simulationVariants" :key="v.image_url" class="flex flex-col items-center">
            <img :src="v.image_url" :alt="v.label" loading="lazy"
              @click="expandedSimUrl = v.image_url"
              class="w-full h-auto object-cover rounded-md cursor-zoom-in"
              style="border:1px solid rgba(124,58,237,0.25);" />
            <span class="text-[11px] mt-1" style="color:#94949f;">{{ v.label }}</span>
          </div>
        </div>
        <div v-if="expandedSimUrl" @click="expandedSimUrl = null"
          class="fixed inset-0 z-50 flex items-center justify-center cursor-zoom-out"
          style="background:rgba(0,0,0,0.85);">
          <img :src="expandedSimUrl" class="max-w-[92vw] max-h-[92vh] object-contain" />
        </div>
      </template>
      <!-- Render-only tier: before/after comparison (or plain image) -->
      <template v-else-if="!isVideoTier && renderImageUrl">
        <BeforeAfterSlider
          v-if="imageInput"
          :before-image="imageInput"
          :after-image="renderImageUrl"
          :before-label="L('原始圖片', 'Before', '元画像', '원본', 'Antes')"
          :after-label="L('渲染結果', 'After', 'レンダー', '렌더', 'Después')"
        />
        <img v-else :src="renderImageUrl" alt="3D render"
          class="max-w-full max-h-[520px] object-contain rounded-lg" />
      </template>
      <!-- Video tiers: video + render + optional 3D model -->
      <div v-else class="flex flex-col gap-3 w-full items-center">
        <video v-if="videoUrl" :src="videoUrl" class="max-w-full max-h-[420px] rounded-lg" controls autoplay loop muted />
        <div class="flex flex-wrap gap-3 justify-center w-full">
          <div v-if="renderImageUrl" class="flex flex-col items-center">
            <span class="text-[11px] mb-1" style="color:#94949f;">{{ L('3D 效果圖', '3D render', '3D効果図', '3D 효과도', 'Render 3D') }}</span>
            <img :src="renderImageUrl" class="max-h-[200px] rounded-md" style="border:1px solid rgba(124,58,237,0.25);" />
          </div>
          <div v-if="modelUrl" class="flex flex-col items-center">
            <span class="text-[11px] mb-1" style="color:#94949f;">{{ L('可旋轉 3D 模型', 'Rotatable 3D model', '回転可能な3Dモデル', '회전 가능한 3D 모델', 'Modelo 3D giratorio') }}</span>
            <ThreeViewer :model-url="modelUrl" :auto-rotate="true" :width="320" :height="220" />
          </div>
        </div>
      </div>
    </template>

    <template v-if="hasResult" #result-actions>
      <template v-if="isSimulationTier && simulationVariants.length">
        <button v-for="(v, idx) in simulationVariants" :key="v.image_url"
          @click="downloadAsset(v.image_url, `vidgo_simulation_${idx+1}_${Date.now()}.png`)"
          class="px-2 py-1.5 rounded text-xs font-medium"
          style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
        >📥 {{ idx + 1 }}</button>
      </template>
      <button v-if="!isSimulationTier && !isVideoTier && renderImageUrl"
        @click="downloadAsset(renderImageUrl!, `vidgo_render3d_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載', 'Download', 'ダウンロード', '다운로드', 'Descargar') }}</button>
      <button v-if="videoUrl"
        @click="downloadAsset(videoUrl!, `vidgo_render3d_${Date.now()}.mp4`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載影片', 'Download video', '動画をダウンロード', '영상 다운로드', 'Descargar vídeo') }}</button>
      <button v-if="modelUrl"
        @click="downloadAsset(modelUrl!, `vidgo_model_${Date.now()}.glb`)"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📦 {{ L('下載 3D (.glb)', 'Download 3D (.glb)', '3Dをダウンロード (.glb)', '3D 다운로드 (.glb)', 'Descargar 3D (.glb)') }}</button>
      <button @click="generate"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >🔄 {{ L('重新生成', 'Regenerate', '再生成', '다시 생성', 'Regenerar') }}</button>
    </template>
  </PiapiPlayground>
</template>
