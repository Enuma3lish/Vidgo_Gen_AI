<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, usePromptLibrary, useLocalized } from '@/composables'
import { toolsApi, effectsApi, uploadsApi } from '@/api'
import type { Style } from '@/api/effects'
import type { UploadStatusResponse } from '@/api/uploads'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import HowToUseHint from '@/components/common/HowToUseHint.vue'
import { validateVideoFile } from '@/utils/mediaValidation'

const { t, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const isZh = computed(() => locale.value.startsWith('zh'))
// 5-language inline picker — fixes BUG-017 (ja/ko/es users were falling
// into the English branch of the legacy `isZh ? zh : en` ternary).
const { L } = useLocalized()
// `route.name === 'video-transform'` covers /tools/video-transform. The QA
// plan also expects /tools/short-video?mode=transform to land on the same
// workflow, so we honor the query-string variant too.
const isVideoTransformMode = computed(() =>
  route.name === 'video-transform' || String(route.query.mode || '') === 'transform'
)
const pageTitle = computed(() => isVideoTransformMode.value
  ? L('影片風格轉換', 'Video Style Transform', '動画スタイル変換', '비디오 스타일 변환', 'Transformación de estilo de video')
  : t('tools.shortVideo.name'))
const pageDescription = computed(() => isVideoTransformMode.value
  ? L('上傳自己的影片，套用 AI 風格轉換效果。', 'Upload your own video and apply an AI video style transform.', '動画をアップロードし、AIスタイル変換を適用します。', '동영상을 업로드하고 AI 스타일 변환 효과를 적용하세요.', 'Sube tu video y aplica un efecto AI de transformación de estilo.')
  : t('tools.shortVideo.longDesc'))

// PRESET-ONLY MODE: All users use presets, no custom input
const {
  isDemoUser,
  canUseCustomInputs,
  loadDemoTemplates,
  demoTemplates,
  isLoadingTemplates,
  resolveDemoTemplateResultUrl,
  generateOnDemand,
  loadInputLibrary,
  inputLibrary,
  loadEffectCatalog,
  effectCatalog,
} = useDemoMode()

// Curated prompt library — dropdown options for the video transform prompt.
const { options: videoPromptOptions, promptFor: videoPromptTextFor } = usePromptLibrary('short_video')
const selectedVideoPromptId = ref('')

const isSubscribed = computed(() => !isDemoUser.value)

const uploadedImage = ref<string | undefined>(undefined)
const uploadedVideoFile = ref<File | null>(null)
const uploadedVideoPreview = ref<string | null>(null)
const transformPrompt = ref('')
// Re-derive transform prompt when the user picks a new option OR switches
// locale so the displayed prompt always matches the active language.
watch([selectedVideoPromptId, locale], () => {
  if (selectedVideoPromptId.value) {
    transformPrompt.value = videoPromptTextFor(selectedVideoPromptId.value)
  } else {
    transformPrompt.value = ''
  }
})
const resultVideo = ref<string | null>(null)
const isProcessing = ref(false)
const uploadProgress = ref(0)
const processingStage = ref<string | null>(null)
const currentUploadId = ref<string | null>(null)
// True when a demo user clicked Generate but the selected tile isn't backed
// by a real Material DB preset (db_empty fallback or missing preset id).
// Surfaces a persistent in-block message instead of a silent no-op.
const demoEmptyState = ref(false)
// Settings - only for subscribed users
const selectedDuration = ref(5)
const selectedMotion = ref('auto')
const selectedModel = ref('pixverse_v4.5')
const selectedStyle = ref<string | null>(null)
const videoStyles = ref<Style[]>([])

const motionStrengthById: Record<string, number> = {
  auto: 5,
  'zoom-in': 4,
  'zoom-out': 4,
  'pan-left': 6,
  'pan-right': 6,
  rotate: 7,
}

function normalizeMotionId(motion?: string | null): string {
  return (motion || 'auto').replace(/_/g, '-')
}

// Duration options vary by model
const durationOptions = computed(() => {
  const modelInfo = aiModelOptions.find(m => m.id === selectedModel.value)
  return modelInfo?.lengths || [5, 8]
})

// Motion types — bilingual labels extended with ja/ko/es so non-Chinese
// locales no longer fall back to English (BUG-017).
const motionOptions = [
  { id: 'auto',      nameEn: 'Auto',       nameZh: '自動', nameJa: '自動',     nameKo: '자동',     nameEs: 'Auto',         descEn: 'AI decides motion',         descZh: 'AI 自動選擇動態', descJa: 'AIが動きを決定',         descKo: 'AI가 동작 결정',        descEs: 'La IA decide el movimiento' },
  { id: 'zoom-in',   nameEn: 'Zoom In',    nameZh: '放大', nameJa: 'ズームイン', nameKo: '확대',    nameEs: 'Acercar',      descEn: 'Gradual zoom effect',       descZh: '逐漸放大效果',   descJa: '徐々にズーム',           descKo: '서서히 확대',           descEs: 'Efecto de zoom gradual' },
  { id: 'zoom-out',  nameEn: 'Zoom Out',   nameZh: '縮小', nameJa: 'ズームアウト', nameKo: '축소',  nameEs: 'Alejar',       descEn: 'Pull back effect',          descZh: '拉遠效果',       descJa: '引いてズームアウト',     descKo: '뒤로 빠지는 효과',      descEs: 'Efecto de alejamiento' },
  { id: 'pan-left',  nameEn: 'Pan Left',   nameZh: '左移', nameJa: '左にパン',   nameKo: '왼쪽 이동', nameEs: 'Pan izquierda', descEn: 'Horizontal movement left',  descZh: '向左平移',       descJa: '水平に左へ移動',         descKo: '수평으로 왼쪽 이동',    descEs: 'Movimiento horizontal a la izquierda' },
  { id: 'pan-right', nameEn: 'Pan Right',  nameZh: '右移', nameJa: '右にパン',   nameKo: '오른쪽 이동', nameEs: 'Pan derecha', descEn: 'Horizontal movement right', descZh: '向右平移',       descJa: '水平に右へ移動',         descKo: '수평으로 오른쪽 이동',  descEs: 'Movimiento horizontal a la derecha' },
  { id: 'rotate',    nameEn: 'Rotate',     nameZh: '旋轉', nameJa: '回転',     nameKo: '회전',     nameEs: 'Rotar',        descEn: 'Circular motion',           descZh: '旋轉動態',       descJa: '円運動',               descKo: '원형 운동',             descEs: 'Movimiento circular' }
]

// AI Model options from Pollo AI - subscriber only feature
const aiModelOptions = [
  {
    id: 'pixverse_v4.5',
    nameEn: 'Pixverse 4.5',
    nameZh: 'Pixverse 4.5',
    descEn: 'Fast & Affordable - Good quality',
    descZh: '快速實惠 - 品質優良',
    descJa: '高速・低コスト・良好な品質',
    descKo: '빠르고 저렴 - 좋은 품질',
    descEs: 'Rápido y económico - Buena calidad',
    lengths: [5, 8],
    badge: 'default'
  },
  {
    id: 'pixverse_v5',
    nameEn: 'Pixverse 5.0',
    nameZh: 'Pixverse 5.0',
    descEn: 'Creative animations',
    descZh: '創意動畫風格',
    descJa: 'クリエイティブなアニメーション',
    descKo: '창의적인 애니메이션',
    descEs: 'Animaciones creativas',
    lengths: [5, 8],
    badge: 'new'
  },
  {
    id: 'kling_v2',
    nameEn: 'Kling AI 2.0',
    nameZh: 'Kling AI 2.0',
    descEn: 'High quality, lifelike movements',
    descZh: '高品質，逼真動態',
    descJa: '高品質、リアルな動き',
    descKo: '고품질, 사실적인 움직임',
    descEs: 'Alta calidad, movimientos realistas',
    lengths: [5, 10],
    badge: 'pro'
  },
  {
    id: 'kling_v1.5',
    nameEn: 'Kling AI 1.5',
    nameZh: 'Kling AI 1.5',
    descEn: 'Fast generation, good quality',
    descZh: '快速生成，品質好',
    descJa: '高速生成、良好な品質',
    descKo: '빠른 생성, 좋은 품질',
    descEs: 'Generación rápida, buena calidad',
    lengths: [5, 10],
    badge: null
  },
  {
    id: 'luma_ray2',
    nameEn: 'Luma Ray 2.0',
    nameZh: 'Luma Ray 2.0',
    descEn: 'Cinematic quality',
    descZh: '電影級品質',
    descJa: '映画レベルの品質',
    descKo: '영화 수준의 품질',
    descEs: 'Calidad cinematográfica',
    lengths: [5, 10],
    badge: 'premium'
  }
]

// Demo images for demo users
const selectedDemoImageId = ref<string | null>(null)

const demoImages = computed(() => {
  return demoTemplates.value
    .filter(t => t.result_video_url || t.result_watermarked_url)
    .map(t => ({
      id: t.id,
      // Always show prompt in user's current language
      name: isZh.value ? (t.prompt_zh || t.prompt) : t.prompt,
      // Use thumbnail, input_image, or generate from video URL
      preview: t.thumbnail_url || t.input_image_url || undefined,
      video_url: t.result_video_url || t.result_watermarked_url,
      watermarked_result: t.result_watermarked_url,
      topic: t.topic,
      // Extract motion type from input_params (API returns metadata in input_params)
      motion: normalizeMotionId(t.input_params?.motion || t.topic || 'auto')
    }))
})


// Static fallback examples for ShortVideo (shown when backend DB is empty)
const STATIC_VIDEO_EXAMPLES = [
  {
    id: 'static-sv-1',
    name: 'Cherry blossom petals falling in slow motion, cinematic',
    nameZh: '櫻花花瓣以慢動作飄落，電影感畫面',
    preview: 'https://images.unsplash.com/photo-1522383225653-ed111181a951?w=600&fit=crop',
    video_url: undefined,
    watermarked_result: undefined,
    topic: 'nature',
    motion: 'zoom_in'
  },
  {
    id: 'static-sv-2',
    name: 'Skincare product rotating on marble surface, studio lighting',
    nameZh: '保養品在大理石檯面旋轉，棚拍燈光',
    preview: 'https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=600&fit=crop',
    video_url: undefined,
    watermarked_result: undefined,
    topic: 'product',
    motion: 'rotate'
  },
  {
    id: 'static-sv-3',
    name: 'Coffee being poured into a glass cup, overhead view',
    nameZh: '咖啡倒入玻璃杯，俯拍視角',
    preview: 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600&fit=crop',
    video_url: undefined,
    watermarked_result: undefined,
    topic: 'food',
    motion: 'pan_right'
  },
  {
    id: 'static-sv-4',
    name: 'Fashion model walking on city street, golden hour',
    nameZh: '時尚模特在城市街道行走，金色時刻',
    preview: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600&fit=crop',
    video_url: undefined,
    watermarked_result: undefined,
    topic: 'fashion',
    motion: 'pan_left'
  },
  {
    id: 'static-sv-5',
    name: 'Mountain landscape with clouds moving, time lapse',
    nameZh: '山景雲霧流動，縮時攝影感',
    preview: 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=600&fit=crop',
    video_url: undefined,
    watermarked_result: undefined,
    topic: 'landscape',
    motion: 'zoom_out'
  },
  {
    id: 'static-sv-6',
    name: 'Bubble tea shop interior, warm lighting, cozy atmosphere',
    nameZh: '手搖飲店內景，溫暖燈光與舒適氛圍',
    preview: 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600&fit=crop',
    video_url: undefined,
    watermarked_result: undefined,
    topic: 'food',
    motion: 'auto'
  }
]
const effectiveDemoImages = computed(() =>
  demoImages.value.length > 0
    ? demoImages.value
    : STATIC_VIDEO_EXAMPLES.map(example => ({
        ...example,
        name: isZh.value ? example.nameZh : example.name,
      }))
)
const processingMessage = computed(() => {
  if (!isVideoTransformMode.value) {
    return L('正在生成影片... 這可能需要幾分鐘', 'Generating video... This may take a few minutes', '動画を生成中...数分かかる場合があります', '동영상 생성 중... 몇 분 소요될 수 있습니다', 'Generando video... puede tardar unos minutos')
  }

  if (uploadProgress.value > 0 && uploadProgress.value < 100) {
    return isZh.value
      ? `正在上傳影片... ${uploadProgress.value}%`
      : `Uploading video... ${uploadProgress.value}%`
  }

  if (processingStage.value) {
    return processingStage.value
  }

  return L('正在處理影片轉換... 這可能需要幾分鐘', 'Processing video transform... This may take a few minutes', '動画変換を処理中...数分かかる場合があります', '동영상 변환 처리 중... 몇 분 소요될 수 있습니다', 'Procesando transformación... puede tardar unos minutos')
})
const pendingTitle = computed(() => isVideoTransformMode.value
  ? L('我正在產生所需的影片，這可能需要幾分鐘，請稍後再回來查看是否已完成。', 'I am creating the requested video. This may take a few minutes, so please check back shortly.', 'リクエストされた動画を作成中です。数分かかる場合があるので、少ししてから再確認してください。', '요청하신 동영상을 생성 중입니다. 몇 분 소요될 수 있으니 잠시 후 다시 확인해 주세요.', 'Estamos creando el video solicitado. Puede tardar unos minutos; vuelve en un momento.')
  : L('我正在產生所需的影片，這可能需要幾分鐘，請稍後再回來查看是否已完成。', 'I am generating the requested video. This may take a few minutes, so please check back shortly.', 'リクエストされた動画を生成中です。数分かかる場合があるので、少ししてから再確認してください。', '요청하신 동영상을 생성 중입니다. 몇 분 소요될 수 있으니 잠시 후 다시 확인해 주세요.', 'Estamos generando el video solicitado. Puede tardar unos minutos; vuelve en un momento.'))
const pendingDetail = computed(() => isVideoTransformMode.value
  ? L('正在轉換影片...', 'Transforming video...', '動画を変換中...', '동영상 변환 중...', 'Transformando video...')
  : L('正在生成影片...', 'Generating video...', '動画を生成中...', '동영상 생성 중...', 'Generando video...'))
const pendingDuration = computed(() => isVideoTransformMode.value
  ? L('需要 2 至 5 分鐘', 'Usually takes 2 to 5 minutes', '通常2〜5分かかります', '보통 2-5분 소요', 'Suele tardar 2-5 minutos')
  : L('需要 1 至 2 分鐘', 'Usually takes 1 to 2 minutes', '通常1〜2分かかります', '보통 1-2분 소요', 'Suele tardar 1-2 minutos'))

// Load demo presets on mount
onMounted(async () => {
  await Promise.all([
    loadDemoTemplates('short_video'),
    // Pregenerated Vertex Veo T2V inputs as startable source frames/clips,
    // plus the motion-flavor catalog whose `prompt` is cache-keyed alongside
    // the picked input.
    loadInputLibrary('short_video'),
    loadEffectCatalog('short_video', locale.value),
  ])
  try {
    const styles = await effectsApi.getStyles('professional')
    videoStyles.value = styles.slice(0, 6)
  } catch {
    videoStyles.value = [
      { id: 'cinematic', name: 'VidGo Cinematic', name_zh: '電影質感', category: 'professional', preview_url: '' },
      { id: 'realistic', name: 'VidGo Realistic', name_zh: '寫實風格', category: 'modern', preview_url: '' },
      { id: 'anime', name: 'VidGo Anime', name_zh: '動漫風格', category: 'artistic', preview_url: '' },
      { id: 'watercolor', name: 'VidGo Watercolor', name_zh: '水彩風格', category: 'artistic', preview_url: '' },
    ]
  }
})

onBeforeUnmount(() => {
  if (uploadedVideoPreview.value) {
    URL.revokeObjectURL(uploadedVideoPreview.value)
  }
})

watch(locale, () => loadEffectCatalog('short_video', locale.value))

function selectDemoImage(item: { id: string; preview?: string; video_url?: string; motion?: string }) {
  selectedDemoImageId.value = item.id
  uploadedImage.value = item.preview || item.video_url || undefined
  resultVideo.value = null
  demoEmptyState.value = false
}



async function generateVideo() {
  if (isVideoTransformMode.value) {
    await generateVideoTransform()
    return
  }

  if (!uploadedImage.value) {
    uiStore.showError(L('請選擇一個範例', 'Please select an example', '例を選択してください', '예시를 선택해 주세요', 'Selecciona un ejemplo'))
    return
  }

  // Clear stale result so loading overlay is the only thing visible.
  resultVideo.value = null
  demoEmptyState.value = false
  isProcessing.value = true
  try {
    // For demo users, resolve the selected preset through backend lookup
    if (isDemoUser.value && selectedDemoImageId.value) {
      const demoResultUrl = await resolveDemoTemplateResultUrl(selectedDemoImageId.value)
      if (demoResultUrl) {
        resultVideo.value = demoResultUrl
        uiStore.showSuccess(L('生成成功（示範）', 'Generated successfully (Demo)', '生成成功（デモ）', '생성 성공 (데모)', 'Generado correctamente (demo)'))
        return
      }

      // VG-BUG-010 fix: cache-through on demand (Pollo MCP video generation
      // takes 2-5 min — the longer client-side timeout in generateOnDemand
      // accommodates this).
      uiStore.showInfo(L('此影片尚未生成，正在為您即時生成（約 2-5 分鐘）...', 'Generating in real-time (2-5 min)...', 'リアルタイム生成中（約2〜5分）...', '실시간으로 생성 중 (약 2-5분)...', 'Generando en tiempo real (2-5 min)...'))
      // Prefer the pregenerated Vertex input frame when the user picked one
      // from the library; otherwise fall back to the finished-example input
      // or the user-uploaded image.
      const pickedFromLibrary = (inputLibrary.value.find((item: any) => item.id === selectedDemoImageId.value) as any)?.input_image_url
      const pickedFromTemplate = (demoTemplates.value.find((t: any) => t.id === selectedDemoImageId.value) as any)?.input_image_url
      const pickedFrame = pickedFromLibrary || pickedFromTemplate || uploadedImage.value || undefined
      // Map the motion radio to a real effect prompt from the catalog so the
      // cache key differentiates between "gentle" / "dramatic" / etc.
      const motionId = normalizeMotionId(selectedMotion.value)
      const motionPrompt = effectCatalog.value.find((e: any) =>
        e.id === motionId
        || e.id === (selectedStyle.value || '')
      )?.prompt || selectedStyle.value || undefined
      const onDemandUrl = await generateOnDemand('short_video', undefined, {
        input_image_url: pickedFrame,
        effect_prompt: motionPrompt,
      })
      if (onDemandUrl) {
        resultVideo.value = onDemandUrl
        uiStore.showSuccess(L('生成成功', 'Generated successfully', '生成成功', '생성 성공', 'Generado correctamente'))
        return
      }
      demoEmptyState.value = true
      uiStore.showError(L('生成服務暫時無法使用，請稍後再試或訂閱解鎖完整功能', 'Generation service temporarily unavailable. Please try again later or subscribe.', '生成サービスは一時的に利用できません。後ほど再試行するか、サブスクで全機能を解禁してください。', '생성 서비스를 일시적으로 사용할 수 없습니다. 나중에 다시 시도하거나 구독해 주세요.', 'Servicio temporalmente no disponible. Inténtalo más tarde o suscríbete.'))
      return
    }

    let imageUrl: string | null = null
    if (uploadedImage.value) {
      if (uploadedImage.value.startsWith('data:')) {
        const blob = dataURItoBlob(uploadedImage.value)
        if (!blob) {
          uiStore.showError(L('圖片格式無效，請重新上傳', 'Invalid image format. Please re-upload.', '画像形式が無効です。再アップロードしてください。', '이미지 형식이 올바르지 않습니다. 다시 업로드해 주세요.', 'Formato de imagen inválido. Súbela de nuevo.'))
          return
        }
        const uploadResult = await toolsApi.uploadImage(blob as File)
        imageUrl = uploadResult.url
      } else {
        imageUrl = uploadedImage.value
      }
    }

    const result = await toolsApi.shortVideo(imageUrl!, {
      motionStrength: motionStrengthById[normalizeMotionId(selectedMotion.value)] ?? 5,
      modelId: selectedModel.value !== 'default' ? selectedModel.value : undefined,
      style: selectedStyle.value || undefined,
      promptId: selectedVideoPromptId.value || undefined,
      locale: String(locale.value || ''),
    })

    if (result.success && (result.video_url || result.result_url)) {
      resultVideo.value = result.video_url || result.result_url || null
      creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success'))
    } else {
      uiStore.showError(result.message || (result as any).error || L('影片生成失敗，請稍後再試', 'Video generation failed. Please try again.', '動画生成に失敗しました。後ほど再試行してください。', '동영상 생성에 실패했습니다. 나중에 다시 시도해 주세요.', 'Falló la generación de video. Inténtalo de nuevo.'))
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail || error?.response?.data?.message || error?.message || ''
    uiStore.showError(detail || L('生成失敗', 'Generation failed', '生成に失敗', '생성 실패', 'Falló la generación'))
  } finally {
    isProcessing.value = false
  }
}

function handleVideoUpload(event: Event) {
  const input = event.target as HTMLInputElement | null
  const file = input?.files?.[0]
  if (!file) return

  const validationError = validateVideoFile(file, isZh.value, { maxSizeMb: 20 })
  if (validationError) {
    uiStore.showError(validationError)
    if (input) input.value = ''
    return
  }

  if (uploadedVideoPreview.value) {
    URL.revokeObjectURL(uploadedVideoPreview.value)
  }

  uploadedVideoFile.value = file
  uploadedVideoPreview.value = URL.createObjectURL(file)
  resultVideo.value = null
  demoEmptyState.value = false
}

function clearUploadedVideo() {
  uploadedVideoFile.value = null
  resultVideo.value = null
  uploadProgress.value = 0
  processingStage.value = null
  currentUploadId.value = null
  if (uploadedVideoPreview.value) {
    URL.revokeObjectURL(uploadedVideoPreview.value)
    uploadedVideoPreview.value = null
  }
}

function playPreviewVideo(event: Event) {
  const video = event.target as HTMLVideoElement | null
  video?.play()
}

function resetPreviewVideo(event: Event) {
  const video = event.target as HTMLVideoElement | null
  if (!video) return
  video.pause()
  video.currentTime = 0
}

async function pollUploadStatus(uploadId: string): Promise<UploadStatusResponse> {
  const maxAttempts = 120
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const status = await uploadsApi.getUploadStatus(uploadId)
    if (status.status === 'completed' || status.status === 'failed') {
      return status
    }
    processingStage.value = isZh.value
      ? `伺服器正在處理中...（${status.status}）`
      : `Server is processing... (${status.status})`
    await new Promise(resolve => window.setTimeout(resolve, 3000))
  }
  throw new Error(L('影片轉換逾時，請稍後到作品紀錄查看', 'Video transform timed out. Please check My Works later.', '動画変換がタイムアウトしました。後ほど作品一覧で確認してください。', '동영상 변환 시간이 초과되었습니다. 나중에 작품에서 확인해 주세요.', 'Tiempo de espera agotado. Revisa Mis Obras más tarde.'))
}

async function generateVideoTransform() {
  if (!isSubscribed.value) {
    uiStore.showError(L('請先訂閱以使用影片上傳', 'Please subscribe to upload your own video', '動画アップロードを使うにはサブスク登録してください', '동영상 업로드를 사용하려면 먼저 구독해 주세요', 'Suscríbete para subir tu propio video'))
    return
  }

  if (!uploadedVideoFile.value) {
    uiStore.showError(L('請先上傳影片', 'Please upload a video first', '先に動画をアップロードしてください', '먼저 동영상을 업로드해 주세요', 'Sube primero un video'))
    return
  }

  if (!transformPrompt.value.trim()) {
    uiStore.showError(L('請輸入影片風格描述', 'Please enter a video style prompt', '動画スタイルの説明を入力してください', '동영상 스타일 설명을 입력해 주세요', 'Introduce un prompt de estilo'))
    return
  }

  resultVideo.value = null
  isProcessing.value = true
  uploadProgress.value = 0
  currentUploadId.value = null
  processingStage.value = L('準備上傳影片...', 'Preparing upload...', 'アップロード準備中...', '업로드 준비 중...', 'Preparando subida...')
  try {
    const prompt = selectedStyle.value
      ? `${transformPrompt.value.trim()}\nStyle preset: ${selectedStyle.value}`
      : transformPrompt.value.trim()
    const upload = await uploadsApi.uploadAndGenerate(
      'video_transform',
      uploadedVideoFile.value,
      'default',
      prompt,
      (pct) => {
        uploadProgress.value = pct
        processingStage.value = isZh.value
          ? `正在上傳影片... ${pct}%`
          : `Uploading video... ${pct}%`
      },
    )
    currentUploadId.value = upload.upload_id
    uploadProgress.value = 100
    processingStage.value = L('上傳完成，正在排入轉換...', 'Upload complete, queuing transform...', 'アップロード完了、変換キューに追加中...', '업로드 완료, 변환 대기 중...', 'Subida completa, encolando transformación...')
    const status = await pollUploadStatus(upload.upload_id)

    if (status.status === 'completed' && status.result_video_url) {
      resultVideo.value = status.result_video_url
      creditsStore.deductCredits(status.credits_used)
      processingStage.value = L('影片轉換完成', 'Video transform completed', '動画変換が完了しました', '동영상 변환 완료', 'Transformación de video completa')
      uiStore.showSuccess(L('影片轉換完成', 'Video transform completed', '動画変換が完了しました', '동영상 변환 완료', 'Transformación de video completa'))
      return
    }

    uiStore.showError(status.error_message || L('影片轉換失敗', 'Video transform failed', '動画変換に失敗', '동영상 변환 실패', 'Falló la transformación de video'))
  } catch (error: any) {
    const detail = error?.response?.data?.detail || error?.message || ''
    uiStore.showError(detail || L('影片轉換失敗', 'Video transform failed', '動画変換に失敗', '동영상 변환 실패', 'Falló la transformación de video'))
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
      icon="🎬"
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
          {{ pageTitle }}
        </h1>
        <p class="text-xl text-dark-300">
          {{ pageDescription }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ L('訂閱以解鎖進階設定與 AI 模型選擇', 'Subscribe to unlock advanced settings & AI model selection', 'サブスク登録で詳細設定とAIモデル選択を解禁', '구독으로 고급 설정과 AI 모델 선택 잠금 해제', 'Suscríbete para desbloquear ajustes avanzados y modelos AI') }}
          </RouterLink>
        </div>
      </div>

      <HowToUseHint
        tool-type="short_video"
        :media-kind="isVideoTransformMode ? 'video' : 'image'"
        :i18n-keys="isVideoTransformMode
          ? [
              'howTo.short_video.v2v.step1',
              'howTo.short_video.v2v.step2',
              'howTo.short_video.v2v.step3',
            ]
          : [
              'howTo.short_video.i2v.step1',
              'howTo.short_video.i2v.step2',
              'howTo.short_video.i2v.step3',
            ]"
      />

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Left Panel - Input -->
        <div class="space-y-6">
          <!-- Example Selection -->
          <div class="card">
            <h3 class="text-lg font-semibold text-dark-50 mb-4">
              {{ isVideoTransformMode
                ? L('上傳你的影片', 'Upload Your Video', '動画をアップロード', '동영상 업로드', 'Sube tu video')
                : L('請試試我們精彩的範例', 'Please try our amazing examples', '素晴らしい例をお試しください', '멋진 예시를 사용해 보세요', 'Prueba nuestros ejemplos') }}
            </h3>

            <!-- Subscriber Interface: Upload Zone -->
            <div v-if="!isDemoUser && !isVideoTransformMode" class="mb-6">
               <h4 class="text-sm font-medium text-dark-300 mb-2">{{ L('上傳圖片 (.jpg, .png)', 'Upload Image (.jpg, .png)', '画像をアップロード (.jpg, .png)', '이미지 업로드 (.jpg, .png)', 'Subir imagen (.jpg, .png)') }}</h4>
               <ImageUploader
                 tool-type="short_video"
                 v-model="uploadedImage"
                 :label="L('點擊上傳或拖放起始圖片', 'Drop starting image here', 'クリックまたは開始画像をドロップ', '클릭 또는 시작 이미지 드롭', 'Sube o arrastra una imagen inicial')"
                 class="mb-4"
                 @update:model-value="selectedDemoImageId = null"
               />
            </div>

            <div v-if="isSubscribed && isVideoTransformMode" class="space-y-4 mb-6">
              <div>
                <label class="label">{{ L('上傳影片', 'Upload Video', '動画をアップロード', '동영상 업로드', 'Subir video') }}</label>
                <label class="block rounded-xl border-2 border-dashed p-6 cursor-pointer transition-colors" style="border-color: rgba(255,255,255,0.08); background: #141420;">
                  <input type="file" accept=".mp4,.webm,.mov,video/mp4,video/webm,video/quicktime" class="hidden" @change="handleVideoUpload" />
                  <div class="text-center">
                    <p class="text-dark-50 text-sm font-medium">{{ L('點擊或拖放 MP4 / WEBM / MOV', 'Click or drop MP4 / WEBM / MOV', 'クリックまたはMP4 / WEBM / MOVをドロップ', '클릭 또는 MP4 / WEBM / MOV 드롭', 'Toca o arrastra MP4 / WEBM / MOV') }}</p>
                    <p class="text-dark-400 text-xs mt-1">{{ L('付費用戶可上傳自己的影片做風格轉換', 'Paid users can upload their own videos for style transfer', '有料ユーザーは自分の動画をスタイル変換できます', '유료 사용자는 본인 동영상으로 스타일 변환 가능', 'Los usuarios premium pueden subir su propio video') }}</p>
                  </div>
                </label>
              </div>

              <div v-if="uploadedVideoPreview" class="space-y-3">
                <video :src="uploadedVideoPreview" controls playsinline preload="metadata" class="w-full rounded-xl" />
                <button @click="clearUploadedVideo" class="btn-ghost text-sm w-full">
                  {{ L('移除影片', 'Remove Video', '動画を削除', '동영상 제거', 'Quitar video') }}
                </button>
              </div>

              <div>
                <label class="label">{{ L('轉換描述', 'Transform Prompt', '変換プロンプト', '변환 프롬프트', 'Prompt de transformación') }}</label>
                <select
                  v-model="selectedVideoPromptId"
                  class="w-full rounded-xl px-4 py-3 text-dark-50"
                  style="background: #141420; border: 1px solid rgba(255,255,255,0.08);"
                >
                  <option value="">{{ L('— 請選擇影片動效 —', '— Select a motion effect —', '— モーション効果を選択 —', '— 모션 효과 선택 —', '— Selecciona un efecto —') }}</option>
                  <option v-for="opt in videoPromptOptions" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
                </select>
              </div>

              <div v-if="isProcessing || currentUploadId || uploadProgress > 0" class="rounded-2xl p-4 border" style="background: linear-gradient(135deg, rgba(16,24,40,0.92), rgba(19,49,58,0.78)); border-color: rgba(93, 188, 210, 0.28);">
                <div class="flex items-start justify-between gap-4 mb-3">
                  <div>
                    <p class="text-xs uppercase text-cyan-300/80">
                      {{ L('轉換狀態', 'Transform Status', '変換ステータス', '변환 상태', 'Estado de transformación') }}
                    </p>
                    <p class="text-sm text-dark-50 mt-1">{{ processingMessage }}</p>
                  </div>
                  <div class="shrink-0 text-right">
                    <p class="text-2xl font-semibold text-cyan-200">{{ uploadProgress }}%</p>
                    <p class="text-[11px] text-dark-400">{{ L('上傳進度', 'Upload Progress', 'アップロード進捗', '업로드 진행률', 'Progreso de subida') }}</p>
                  </div>
                </div>

                <div class="h-2 rounded-full overflow-hidden mb-3" style="background: rgba(255,255,255,0.08);">
                  <div class="h-full rounded-full transition-all duration-300" :style="{ width: `${uploadProgress}%`, background: 'linear-gradient(90deg, #5dbcd2, #b4f0ff)' }" />
                </div>

                <div class="flex items-center justify-between text-xs text-dark-300 gap-3">
                  <span>{{ L('大型影片通常需要數分鐘', 'Longer clips can take several minutes', '長いクリップは数分かかる場合があります', '긴 클립은 몇 분이 소요될 수 있습니다', 'Los clips largos pueden tardar varios minutos') }}</span>
                  <span v-if="currentUploadId" class="font-mono text-cyan-200">#{{ currentUploadId.slice(0, 8) }}</span>
                </div>
              </div>
            </div>

            <div v-else-if="isVideoTransformMode" class="p-4 rounded-xl mb-6" style="background: #141420; border: 1px solid rgba(255,255,255,0.08);">
              <p class="text-sm text-dark-300">{{ L('訂閱後即可上傳自己的影片並進行風格轉換。', 'Subscribe to upload your own video and run style transfer.', 'サブスク登録で動画アップロードとスタイル変換が可能になります。', '구독하면 본인 동영상을 업로드해 스타일 변환을 할 수 있습니다.', 'Suscríbete para subir tu video y aplicar transferencia de estilo.') }}</p>
            </div>

            <!-- Demo Images for all users -->
            <div v-if="!isVideoTransformMode && effectiveDemoImages.length > 0" class="mb-4">
              <p class="text-sm text-dark-300 mb-3">
                {{ L('點擊查看不同動態效果', 'Click to see different motion effects', 'クリックして異なるモーション効果を確認', '클릭하여 다양한 모션 효과 확인', 'Toca para ver diferentes efectos') }}
              </p>
              <div v-if="isLoadingTemplates" class="flex justify-center py-8">
                <div class="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
              </div>
              <div v-else class="grid grid-cols-2 gap-2">
                <button
                  v-for="item in effectiveDemoImages"
                  :key="item.id"
                  @click="selectDemoImage(item)"
                  class="aspect-video rounded-lg overflow-hidden border-2 transition-all relative group"
                  :class="selectedDemoImageId === item.id
                    ? 'border-primary-500'
                    : ''" style="border-color: rgba(255,255,255,0.08);">
                >
                  <!-- Video preview with poster image. The poster attribute
                       makes mobile browsers (especially iOS Safari) show the
                       still thumbnail even when they refuse to preload video
                       metadata over a metered network (BUG-016). The <img>
                       fallback below covers browsers that ignore both. -->
                  <video
                    v-if="item.video_url"
                    :src="item.video_url"
                    :poster="item.preview || undefined"
                    class="w-full h-full object-cover"
                    muted
                    playsinline
                    preload="metadata"
                    @mouseenter="playPreviewVideo"
                    @mouseleave="resetPreviewVideo"
                  />
                  <img
                    v-else-if="item.preview"
                    :src="item.preview"
                    :alt="item.name"
                    class="w-full h-full object-cover"
                    loading="lazy"
                  />
                  <div v-else class="w-full h-full flex items-center justify-center" style="background: #141420;">
                    <span class="text-3xl">🎬</span>
                  </div>
                  <!-- BUG-002: the top-left badge and bottom-name caption
                       leaked internal motion/topic identifiers into the
                       publicly-shareable preview. Removed both so the tile
                       shows only the actual content. Hover state below
                       still tells users it's clickable. -->
                  <!-- Play icon overlay -->
                  <div class="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    <span class="text-4xl">▶️</span>
                  </div>
                </button>
              </div>
            </div>

            <!-- Selected Image Preview -->
            <div v-if="!isVideoTransformMode && uploadedImage" class="space-y-4 mt-4">
              <img :src="uploadedImage" alt="Source" class="w-full rounded-xl" />
              <button v-if="canUseCustomInputs" @click="uploadedImage = undefined; selectedDemoImageId = null" class="btn-ghost text-sm w-full">
                {{ L('移除圖片', 'Remove Image', '画像を削除', '이미지 제거', 'Quitar imagen') }}
              </button>
            </div>
          </div>

          <!-- Selected Video Info - shows when a preset is selected -->
          <div v-if="!isVideoTransformMode && selectedDemoImageId" class="card">
            <h3 class="text-lg font-semibold text-dark-50 mb-4">
              {{ L('已選擇的範例', 'Selected Example', '選択した例', '선택한 예시', 'Ejemplo seleccionado') }}
            </h3>
            <div class="p-3 bg-primary-500/10 border border-primary-500/20 rounded-lg">
              <p class="text-sm text-dark-50 mb-2">
                <span class="text-primary-400 font-medium">{{ L('動態效果：', 'Motion Effect: ', 'モーション効果：', '모션 효과: ', 'Efecto de movimiento: ') }}</span>
                {{ isZh
                  ? motionOptions.find(m => m.id === demoImages.find(d => d.id === selectedDemoImageId)?.motion)?.nameZh || '自動'
                  : motionOptions.find(m => m.id === demoImages.find(d => d.id === selectedDemoImageId)?.motion)?.nameEn || 'Auto'
                }}
              </p>
              <p class="text-sm text-dark-200">
                <span class="text-primary-400 font-medium">{{ L('描述：', 'Prompt: ', 'プロンプト：', '프롬프트: ', 'Prompt: ') }}</span>
                {{ demoImages.find(d => d.id === selectedDemoImageId)?.name }}
              </p>
            </div>
            <!-- Visitor/demo user: direct "View Result" button, no gated settings noise -->
            <div v-if="!isSubscribed" class="mt-4">
              <button
                @click="generateVideo"
                :disabled="isProcessing"
                class="btn-primary w-full"
              >
                {{ L('查看結果', 'View Result', '結果を見る', '결과 보기', 'Ver resultado') }}
              </button>
            </div>
          </div>

          <!-- Prompt to select - shows when nothing selected -->
          <div v-else-if="!isVideoTransformMode" class="card">
            <h3 class="text-lg font-semibold text-dark-50 mb-4">
              {{ L('選擇一個範例', 'Select an Example', '例を選択', '예시 선택', 'Selecciona un ejemplo') }}
            </h3>
            <div class="p-3 rounded-lg" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
              <p class="text-sm text-dark-300">
                {{ L('👆 從上方範例影片中選擇一個來查看效果', '👆 Select an example video above to see the result', '👆 上の例から動画を選択して結果を確認', '👆 위 예시 동영상에서 선택하여 결과 확인', '👆 Selecciona uno de los ejemplos para ver el resultado') }}
              </p>
            </div>
          </div>

          <!-- Video Settings / Transform CTA - Subscriber Only (hidden entirely for visitors) -->
          <div v-if="isSubscribed" class="card">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold text-dark-50">
                {{ isVideoTransformMode ? L('轉換設定', 'Transform Settings', '変換設定', '변환 설정', 'Ajustes de transformación') : L('影片設定', 'Video Settings', '動画設定', '동영상 설정', 'Ajustes de video') }}
              </h3>
            </div>

            <!-- Duration - Subscriber only -->
            <div v-if="!isVideoTransformMode" class="mb-6" :class="{ 'opacity-50 pointer-events-none': !isSubscribed }">
              <label class="label">{{ L('影片長度', 'Duration', '長さ', '재생 시간', 'Duración') }}</label>
              <div class="flex gap-3">
                <button
                  v-for="dur in durationOptions"
                  :key="dur"
                  @click="isSubscribed && (selectedDuration = dur)"
                  class="flex-1 py-3 rounded-xl border-2 transition-all"
                  :class="selectedDuration === dur
                    ? 'border-primary-500 bg-primary-500/10'
                    : ''" style="border-color: rgba(255,255,255,0.08);">
                >
                  {{ dur }}s
                </button>
              </div>
              <p v-if="!isSubscribed" class="text-xs text-dark-400 mt-2">
                {{ L('訂閱後可自訂影片長度', 'Subscribe to customize video duration', 'サブスク登録で動画の長さをカスタマイズ可能', '구독하면 동영상 길이 사용자 설정 가능', 'Suscríbete para personalizar la duración') }}
              </p>
            </div>

            <!-- Motion Type - Subscriber only -->
            <div v-if="!isVideoTransformMode" :class="{ 'opacity-50 pointer-events-none': !isSubscribed }">
              <label class="label">{{ L('動態類型', 'Motion Type', 'モーションタイプ', '모션 유형', 'Tipo de movimiento') }}</label>
              <div class="grid grid-cols-3 gap-2">
                <button
                  v-for="motion in motionOptions"
                  :key="motion.id"
                  @click="isSubscribed && (selectedMotion = motion.id)"
                  class="p-3 rounded-xl border-2 transition-all text-center"
                  :class="selectedMotion === motion.id
                    ? 'border-primary-500 bg-primary-500/10'
                    : ''" style="border-color: rgba(255,255,255,0.08);">
                >
                  <p class="text-sm font-medium">{{ L(motion.nameZh, motion.nameEn, motion.nameJa, motion.nameKo, motion.nameEs) }}</p>
                  <p class="text-xs text-dark-400 mt-1">{{ L(motion.descZh, motion.descEn, motion.descJa, motion.descKo, motion.descEs) }}</p>
                </button>
              </div>
              <p v-if="!isSubscribed" class="text-xs text-dark-400 mt-2">
                {{ L('訂閱後可選擇動態效果', 'Subscribe to choose motion effects', 'サブスク登録でモーション効果を選択可能', '구독하면 모션 효과 선택 가능', 'Suscríbete para elegir efectos de movimiento') }}
              </p>
            </div>

            <!-- Not subscribed notice -->
            <div v-if="!isSubscribed" class="mt-4 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
              <p class="text-sm text-amber-400">
                {{ L('🔒 升級訂閱以使用自訂設定', '🔒 Upgrade to use custom settings', '🔒 アップグレードでカスタム設定を使用', '🔒 업그레이드로 사용자 설정 사용', '🔒 Actualiza para ajustes personalizados') }}
              </p>
              <RouterLink to="/pricing" class="text-sm text-primary-400 hover:underline mt-1 inline-block">
                {{ L('查看方案 →', 'View Plans →', 'プランを見る →', '플랜 보기 →', 'Ver planes →') }}
              </RouterLink>
            </div>

            <!-- Credit Cost & Generate -->
            <div class="mt-6 pt-4" style="border-top: 1px solid rgba(255,255,255,0.06);">
              <CreditCost :service="isVideoTransformMode ? undefined : 'short_video'" :cost="isVideoTransformMode ? 35 : undefined" />
              <button
                @click="generateVideo"
                :disabled="isVideoTransformMode ? (!uploadedVideoFile || !transformPrompt.trim() || isProcessing) : (!(selectedDemoImageId || uploadedImage) || isProcessing)"
                class="btn-primary w-full mt-4"
              >
                {{ isVideoTransformMode
                  ? L('開始轉換', 'Start Transform', '変換を開始', '변환 시작', 'Iniciar transformación')
                  : (isSubscribed ? L('確認生成', 'Confirm Generate', '生成を確定', '생성 확인', 'Confirmar generación') : L('查看結果', 'View Result', '結果を見る', '결과 보기', 'Ver resultado')) }}
              </button>
            </div>
          </div>

          <!-- AI Model Selection - Subscriber Only (hidden entirely for visitors) -->
          <div v-if="isSubscribed && !isVideoTransformMode" class="card">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold text-dark-50">
                {{ L('AI 模型選擇', 'AI Model Selection', 'AIモデル選択', 'AI 모델 선택', 'Selección de modelo AI') }}
              </h3>
            </div>

            <div v-if="isSubscribed">
              <p class="text-sm text-dark-300 mb-3">
                {{ L('選擇不同的 AI 模型以獲得不同的生成效果', 'Choose different AI models for different generation effects', '異なるAIモデルで異なる生成効果', '다양한 AI 모델로 다양한 생성 효과', 'Elige diferentes modelos AI para distintos efectos') }}
              </p>
              <div class="space-y-2">
                <button
                  v-for="model in aiModelOptions"
                  :key="model.id"
                  @click="selectedModel = model.id"
                  class="w-full p-3 rounded-xl border-2 transition-all text-left flex items-center justify-between"
                  :class="selectedModel === model.id
                    ? 'border-primary-500 bg-primary-500/10'
                    : ''" style="border-color: rgba(255,255,255,0.08);">
                >
                  <div>
                    <p class="text-sm font-medium text-dark-50">{{ L(model.nameZh, model.nameEn, model.nameZh, model.nameZh, model.nameZh) }}</p>
                    <p class="text-xs text-dark-400">{{ L(model.descZh, model.descEn, model.descJa, model.descKo, model.descEs) }}</p>
                    <p class="text-xs text-dark-400 mt-1">
                      {{ L(`支援長度: ${model.lengths.join('s, ')}s`, `Lengths: ${model.lengths.join('s, ')}s`, `対応長さ: ${model.lengths.join('s, ')}s`, `지원 길이: ${model.lengths.join('s, ')}s`, `Duraciones: ${model.lengths.join('s, ')}s`) }}
                    </p>
                  </div>
                  <div v-if="model.badge" class="ml-2">
                    <span v-if="model.badge === 'default'" class="text-xs px-2 py-0.5 bg-gray-500/20 text-dark-300 rounded">Default</span>
                    <span v-else-if="model.badge === 'new'" class="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded">New</span>
                    <span v-else-if="model.badge === 'pro'" class="text-xs px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded">Pro</span>
                    <span v-else-if="model.badge === 'premium'" class="text-xs px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded">Premium</span>
                  </div>
                </button>
              </div>
            </div>

            <!-- Not subscribed notice -->
            <div v-if="!isSubscribed" class="mt-4 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
              <p class="text-sm text-amber-400">
                {{ L('🔒 升級訂閱以選擇不同 AI 模型', '🔒 Upgrade to choose different AI models', '🔒 アップグレードで異なるAIモデルを選択', '🔒 업그레이드로 다른 AI 모델 선택', '🔒 Actualiza para elegir distintos modelos') }}
              </p>
              <RouterLink to="/pricing" class="text-sm text-primary-400 hover:underline mt-1 inline-block">
                {{ L('查看方案 →', 'View Plans →', 'プランを見る →', '플랜 보기 →', 'Ver planes →') }}
              </RouterLink>
            </div>
          </div>

          <!-- Video Style Effects - Subscriber Only -->
          <div v-if="isSubscribed" class="card">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold text-dark-50">
                {{ isVideoTransformMode
                  ? L('影片轉換風格', 'Video Transform Style', '動画変換スタイル', '동영상 변환 스타일', 'Estilo de transformación')
                  : L('影片風格效果', 'Video Style Effects', '動画スタイル効果', '동영상 스타일 효과', 'Efectos de estilo') }}
              </h3>
              <button
                v-if="selectedStyle"
                @click="selectedStyle = null"
                class="text-xs text-primary-400 hover:text-primary-300 transition-colors"
              >
                {{ L('清除效果', 'Clear Effect', '効果をクリア', '효과 제거', 'Quitar efecto') }}
              </button>
            </div>

            <p class="text-sm text-dark-300 mb-3">
              {{ isVideoTransformMode
                ? L('可選擇一個風格預設，會附加到你的影片轉換描述中。', 'Optionally choose a style preset to append to your video transform prompt.', 'スタイルプリセットを選択して変換プロンプトに追加できます。', '스타일 프리셋을 선택하여 변환 프롬프트에 추가할 수 있습니다.', 'Elige un preset de estilo para añadir al prompt de transformación.')
                : L('可選擇性套用第二段影片風格轉換。未選擇時只會進行一般圖片轉影片。', 'Optionally apply a second-pass video style transform. Leave empty to use standard image-to-video only.', 'オプションでセカンドパスのスタイル変換を適用できます。未選択の場合は通常の画像→動画のみ。', '선택적으로 2차 스타일 변환을 적용할 수 있습니다. 미선택 시 일반 이미지→동영상만 진행됩니다.', 'Aplica opcionalmente una segunda pasada. Si lo dejas vacío, solo imagen-a-video.') }}
            </p>

            <div class="grid grid-cols-2 gap-2">
              <button
                v-for="style in videoStyles"
                :key="style.id"
                @click="selectedStyle = selectedStyle === style.id ? null : style.id"
                class="p-3 rounded-xl border-2 transition-all text-left"
                :class="selectedStyle === style.id ? 'border-primary-500 bg-primary-500/10' : ''"
                style="border-color: rgba(255,255,255,0.08);"
              >
                <p class="text-sm font-medium text-dark-50">
                  {{ L(style.name_zh, style.name, style.name_zh, style.name_zh, style.name) }}
                </p>
                <p class="text-xs text-dark-400 mt-1">{{ style.id }}</p>
              </button>
            </div>
          </div>
        </div>

        <!-- Right Panel - Result -->
        <div class="card h-fit sticky top-24">
          <h3 class="text-lg font-semibold text-dark-50 mb-4">
            {{ L('生成的影片', 'Generated Video', '生成された動画', '생성된 동영상', 'Video generado') }}
          </h3>

          <div v-if="resultVideo" class="space-y-4">
            <video
              :src="resultVideo"
              controls
              class="w-full rounded-xl"
              autoplay
              loop
            />
            <!-- Watermark badge -->
            <div class="text-center text-xs text-dark-400">vidgo.ai</div>
            <!-- Download / Action Buttons -->
            <div class="flex gap-3">
               <a
                 v-if="!isDemoUser"
                 :href="resultVideo"
                 download="vidgo_short_video.mp4"
                 class="btn-primary flex-1 text-center py-3 flex items-center justify-center"
               >
                 <span class="mr-2">📥</span> {{ t('common.download') }}
               </a>

               <RouterLink v-else to="/pricing" class="btn-primary w-full text-center block">
                 {{ L('訂閱以獲得完整功能', 'Subscribe for Full Access', 'サブスクで全機能を解禁', '구독으로 전체 액세스', 'Suscríbete para acceso completo') }}
               </RouterLink>
            </div>
          </div>

          <div v-else-if="demoEmptyState" class="aspect-video flex flex-col items-center justify-center rounded-xl text-center px-6 gap-3" style="background: #141420; border: 1px solid rgba(255,255,255,0.08);">
            <span class="text-2xl">🔒</span>
            <p class="text-sm text-dark-200">
              {{ L('此範例尚未預生成結果', 'No pre-generated result for this example yet', 'この例はまだ事前生成されていません', '이 예시는 아직 사전 생성되지 않았습니다', 'Aún no hay resultado pregenerado') }}
            </p>
            <RouterLink to="/pricing" class="btn-primary text-sm px-4 py-2">
              {{ L('訂閱以使用完整 AI 功能', 'Subscribe to use the real AI', 'サブスクで実AI機能を解禁', '구독으로 실제 AI 사용', 'Suscríbete para usar la IA real') }}
            </RouterLink>
          </div>

          <div v-else class="aspect-video flex items-center justify-center rounded-xl text-dark-400" style="background: #141420;">
            <div class="text-center">
              <span class="text-5xl block mb-4">🎬</span>
              <p>{{ L('生成的影片將顯示在這裡', 'Generated video will appear here', '生成された動画はここに表示されます', '생성된 동영상이 여기에 표시됩니다', 'El video generado aparecerá aquí') }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
