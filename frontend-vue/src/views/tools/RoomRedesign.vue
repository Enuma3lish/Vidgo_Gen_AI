<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore } from '@/stores'
import { useDemoMode, usePromptLibrary, useLocalized } from '@/composables'
import { interiorApi, effectsApi, demoApi } from '@/api'
import type { DesignStyle, RoomType } from '@/api'
import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import ThreeViewer from '@/components/tools/ThreeViewer.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import HowToUseHint from '@/components/common/HowToUseHint.vue'

// FastAPI returns 422 / 415 validation errors as `detail: [{msg, loc, ...}]`.
// A bare `error.response.data.detail` then renders as "[object Object]" in
// the toast (or no toast at all), which is what makes failed uploads look
// like a silent "404". This helper flattens the array into a readable
// single line so the user actually sees the reason.
function explainBackendError(error: any, fallback: string): string {
  const detail = error?.response?.data?.detail
  if (!detail) return error?.message || fallback
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const lines = detail
      .map((d: any) => (typeof d === 'string' ? d : d?.msg || d?.message))
      .filter(Boolean)
    if (lines.length) return lines.join('; ')
  }
  if (typeof detail === 'object') {
    if (typeof detail.message === 'string') return detail.message
    if (typeof detail.error === 'string') return detail.error
  }
  return fallback
}

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const isZh = computed(() => locale.value.startsWith('zh'))
// L(zh, en, ja?, ko?, es?) — 5-language inline string picker. Replaces
// the legacy `isZh ? zh : en` ternary that always fell back to English
// for ja/ko/es users (BUG-017).
const { L } = useLocalized()

// Demo mode
const {
  isDemoUser,
  loadDemoTemplates,
  demoTemplates,
  resolveDemoTemplateResultUrl,
  checkSubscription,
  subscriptionChecked,
  loadInputLibrary,
  inputLibrary,
} = useDemoMode()

// Curated prompt library — dropdown options for both Custom Prompt and
// Transform Description (no free-form text in MVP).
const { options: roomPromptOptions, promptFor: roomPromptTextFor } = usePromptLibrary('room_redesign')
// Two independent selects (Redesign tab + AI Transform tab) each bind to
// their own prompt-id ref so we can re-derive text on locale switch.
const selectedRoomPromptId = ref('')
const selectedTransformPromptId = ref('')

// Data
const styles = ref<DesignStyle[]>([])
const roomTypes = ref<RoomType[]>([])

// State
const activeTab = ref<'redesign' | 'generate' | 'styleTransfer' | '3dModel' | 'transform'>('redesign')
// Tab list: subscriber-only tabs (generate, 3dModel, transform) are hidden for visitors
// so they never see locked chrome or error toasts.
const visibleTabs = computed(() => {
  const all = [
    { id: 'redesign' as const,      icon: '🔄', label: t('interior.tabs.redesign'),      subOnly: false },
    { id: 'generate' as const,      icon: '✨', label: t('interior.tabs.generate'),      subOnly: true },
    { id: 'styleTransfer' as const, icon: '🎨', label: t('interior.tabs.styleTransfer'), subOnly: false },
    { id: 'transform' as const,     icon: '🪄', label: L('AI 自由變換', 'AI Transform', 'AI 自由変換', 'AI 자유 변환', 'AI Transformación'), subOnly: true },
    { id: '3dModel' as const,       icon: '🧊', label: L('3D 模型', '3D Model', '3Dモデル', '3D 모델', 'Modelo 3D'), subOnly: true },
  ]
  return all.filter(tab => !(tab.subOnly && isDemoUser.value))
})

const studioCapabilities = computed(() => [
  {
    icon: '📷',
    title: L('照片 / 空屋改造', 'Photo / Empty-room Redesign', '写真 / 空室リデザイン', '사진 / 빈 방 리디자인', 'Foto / Rediseño de sala vacía'),
    text: L('從現況照、空屋照或家具空間開始，保留房型比例並生成可比較的改造視覺。', 'Start from room photos, empty spaces, or furniture contexts and create comparable redesign visuals while preserving spatial proportion.', '現況写真、空室写真、家具のある空間から開始し、間取り比率を保ったまま比較可能なリデザインビジュアルを生成します。', '실제 사진, 빈 방 사진 또는 가구가 있는 공간에서 시작하여 공간 비율을 유지하면서 비교 가능한 리디자인 비주얼을 생성합니다.', 'Empieza con fotos de habitaciones, espacios vacíos o ambientes amueblados y crea visuales de rediseño comparables conservando las proporciones del espacio.'),
    proof: L('房仲刊登、出租物件、裝修前後對照', 'Listings, rental visuals, before/after renovation', '不動産掲載、賃貸ビジュアル、リフォーム前後比較', '부동산 등록, 임대 비주얼, 리노베이션 전후 비교', 'Anuncios inmobiliarios, alquileres, antes/después de reforma'),
  },
  {
    icon: '✏️',
    title: L('草圖到提案圖', 'Sketch to Proposal', 'スケッチから提案図へ', '스케치에서 제안서까지', 'De boceto a propuesta'),
    text: L('把手繪概念、參考圖與設計描述整理成客戶看得懂的視覺方向。', 'Turn sketches, references, and design notes into client-readable visual directions.', '手描きコンセプト、参考画像、設計メモを顧客が理解できるビジュアル方向にまとめます。', '손으로 그린 컨셉, 참고 이미지, 디자인 메모를 클라이언트가 이해할 수 있는 비주얼 방향으로 정리합니다.', 'Convierte bocetos, referencias y notas de diseño en direcciones visuales que el cliente pueda entender.'),
    proof: L('初步簡報、風格溝通、提案比稿', 'Pitch decks, style alignment, concept options', 'プレゼン資料、スタイル合意、コンセプト比較', '제안 자료, 스타일 합의, 컨셉 비교', 'Presentaciones, alineación de estilo, comparativa de conceptos'),
  },
  {
    icon: '📐',
    title: L('平面圖到渲染', 'Plan to Render', '平面図からレンダーへ', '평면도에서 렌더링까지', 'De plano a render'),
    text: L('先鎖定空間類型、採光與材質語言，再建立寫實室內視角並延伸 3D 流程。', 'Lock room type, daylight, and material language before creating realistic interior views and extending into 3D.', '部屋タイプ、採光、素材言語をまず固めてから、写実的な室内ビューを作成し、3Dフローへと展開します。', '먼저 공간 유형, 채광, 자재 언어를 정한 다음 사실적인 인테리어 뷰를 생성하고 3D 워크플로우로 확장합니다.', 'Fija el tipo de habitación, la iluminación y los materiales antes de crear vistas interiores realistas y extenderlas a 3D.'),
    proof: L('建案簡報、空間配置、3D 展示素材', 'Architecture decks, layouts, 3D presentation assets', '建築プレゼン、レイアウト、3D提示素材', '건축 프레젠테이션, 레이아웃, 3D 시연 자료', 'Presentaciones de arquitectura, distribuciones, recursos 3D'),
  },
  {
    icon: '✨',
    title: L('提案級輸出', 'Proposal-grade Output', '提案グレードの出力', '제안서 수준의 출력', 'Salida apta para propuesta'),
    text: L('以材質、燈光、鏡頭、比例與品牌調性檢查結果，降低粗糙 AI 感。', 'Review material realism, lighting, camera language, proportion, and brand tone to reduce the AI look.', '素材のリアリティ、ライティング、カメラ言語、比率、ブランドトーンを確認し、AIっぽさを抑えます。', '자재 사실감, 조명, 카메라 언어, 비율, 브랜드 톤을 검토하여 AI 느낌을 줄입니다.', 'Revisa el realismo de materiales, iluminación, lenguaje de cámara, proporciones y tono de marca para reducir el aspecto AI.'),
    proof: L('設計提案、家具情境圖、社群素材', 'Design proposals, furniture scenes, social content', '設計提案、家具シーン、SNS素材', '디자인 제안, 가구 씬, SNS 콘텐츠', 'Propuestas de diseño, escenas de mobiliario, contenido social'),
  },
])

const proposalWorkflow = computed(() => [
  {
    step: '01',
    title: L('輸入空間', 'Bring a Space', '空間を入力', '공간 입력', 'Aporta un espacio'),
    text: L('照片、空屋、草圖或平面圖都能作為起點。', 'Start from a photo, empty room, sketch, or floor plan.', '写真、空室、スケッチ、平面図のいずれもスタート地点になります。', '사진, 빈 방, 스케치, 평면도 모두 시작점이 될 수 있습니다.', 'Empieza con una foto, una habitación vacía, un boceto o un plano.'),
  },
  {
    step: '02',
    title: L('鎖定風格', 'Lock the Direction', '方向性を固める', '방향 정하기', 'Define la dirección'),
    text: L('選擇空間類型、設計風格與材質/燈光描述。', 'Choose room type, design style, materials, and lighting notes.', '部屋タイプ、デザインスタイル、素材／ライティングの説明を選びます。', '공간 유형, 디자인 스타일, 자재/조명 설명을 선택합니다.', 'Elige tipo de habitación, estilo de diseño, materiales y notas de iluminación.'),
  },
  {
    step: '03',
    title: L('生成提案圖', 'Generate Proposal Visuals', '提案ビジュアルを生成', '제안 비주얼 생성', 'Genera la propuesta'),
    text: L('輸出可放進簡報、刊登頁或客戶溝通的寫實視覺。', 'Create realistic visuals for decks, listings, and client alignment.', 'プレゼン、掲載ページ、顧客とのすり合わせに使える写実的ビジュアルを出力します。', '프레젠테이션, 등록 페이지, 클라이언트 협의에 사용할 사실적인 비주얼을 출력합니다.', 'Crea visuales realistas para presentaciones, anuncios y alineación con el cliente.'),
  },
  {
    step: '04',
    title: L('延伸 3D', 'Extend to 3D', '3Dへ展開', '3D로 확장', 'Llévalo a 3D'),
    text: L('訂閱用戶可把完成圖延伸為 GLB 3D 展示素材。', 'Subscribers can turn approved renders into GLB presentation assets.', 'サブスク会員は完成画像をGLB 3D提示素材へ展開できます。', '구독자는 완성된 이미지를 GLB 3D 시연 자료로 확장할 수 있습니다.', 'Los suscriptores pueden convertir los renders en activos GLB 3D para presentación.'),
  },
])

const deliverableStandards = computed(() => [
  L('保留主要房型、窗戶位置與空間比例', 'Preserve core layout, windows, and spatial proportion', '主要な間取り、窓の位置、空間比率を保持', '주요 간추, 창문 위치, 공간 비율 유지', 'Conserva la distribución, las ventanas y las proporciones'),
  L('強化材質細節、自然光、陰影與鏡頭透視', 'Improve material detail, natural light, shadow, and camera perspective', '素材の細部、自然光、影、カメラパースを強化', '자재 디테일, 자연광, 그림자, 카메라 원근을 강화', 'Mejora detalle de materiales, luz natural, sombra y perspectiva'),
  L('適合房仲刊登、室內設計提案與家具情境圖', 'Useful for real estate listings, design proposals, and furniture scenes', '不動産掲載、インテリア提案、家具シーンに最適', '부동산 등록, 인테리어 제안, 가구 씬에 적합', 'Ideal para anuncios, propuestas de diseño y escenas de mobiliario'),
  L('可搭配 3D 模型與批次素材製作流程', 'Works with 3D model and batch content workflows', '3Dモデルおよびバッチ素材制作フローに対応', '3D 모델 및 배치 콘텐츠 제작 워크플로우 지원', 'Compatible con flujos de modelo 3D y producción por lotes'),
])

const roomCreditPackages = computed(() => [
  { name: L('輕量包', 'Light Pack', 'ライトパック', '라이트 팩', 'Pack ligero'), price: 'NT$299', credits: L('3,000 點', '3,000 credits', '3,000ポイント', '3,000 포인트', '3,000 créditos'), note: L('小量測試', 'Light testing', '少量テスト', '소량 테스트', 'Prueba ligera') },
  { name: L('標準包', 'Standard Pack', 'スタンダードパック', '스탠다드 팩', 'Pack estándar'), price: 'NT$499', credits: L('5,500 點', '5,500 credits', '5,500ポイント', '5,500 포인트', '5,500 créditos'), note: L('多送 10%', '10% bonus', '10%ボーナス', '10% 보너스', '10% extra') },
  { name: L('重度包', 'Heavy Pack', 'ヘビーパック', '헤비 팩', 'Pack intensivo'), price: 'NT$999', credits: L('12,000 點', '12,000 credits', '12,000ポイント', '12,000 포인트', '12,000 créditos'), note: L('多送 20%', '20% bonus', '20%ボーナス', '20% 보너스', '20% extra') },
])
const uploadedImage = ref<string | undefined>(undefined)
// True when a demo user clicked Generate but the selected tile isn't backed
// by a real Material DB preset (db_empty fallback or missing preset id).
// Surfaces a persistent in-block message instead of a silent no-op.
const demoEmptyState = ref(false)
const uploadedFile = ref<File | null>(null)
const resultImage = ref<string | null>(null)
const resultDescription = ref<string>('')
const isProcessing = ref(false)
const selectedStyle = ref<string>('')
const selectedRoomType = ref<string>('living_room')
const prompt = ref<string>('')

// Conversation for iterative editing
const conversationId = ref<string | null>(null)
const editHistory = ref<Array<{ prompt: string; image: string }>>([])

// 3D Model state
const modelUrl = ref<string | null>(null)
const is3DProcessing = ref(false)
const textureSize = ref(1024)
const meshSimplify = ref(0.95)
const modelQuality = ref<'v1' | 'v2'>('v2') // v2 = Trellis2 (HD)
const isFloorPlan = ref(false)               // when true, use Floor Plan -> 3D pipeline
const floorplanRoomType = ref<string>('living_room')

// AI Transform state (merged from ImageEffects)
const transformPrompt = ref('')
// Keep `prompt` and `transformPrompt` in sync with the active locale whenever
// the user picks a new preset OR toggles EN/ZH.
watch([selectedRoomPromptId, locale], () => {
  prompt.value = selectedRoomPromptId.value ? roomPromptTextFor(selectedRoomPromptId.value) : ''
})
watch([selectedTransformPromptId, locale], () => {
  transformPrompt.value = selectedTransformPromptId.value ? roomPromptTextFor(selectedTransformPromptId.value) : ''
})
const transformStrength = ref(0.75)

// Style icons mapping
const styleIcons: Record<string, string> = {
  modern_minimalist: '🏢',
  scandinavian: '🌲',
  japanese: '🎋',
  industrial: '🏭',
  bohemian: '🎨',
  mediterranean: '🌊',
  art_deco: '✨',
  mid_century_modern: '🪑',
  coastal: '🏖️',
  farmhouse: '🏡'
}

// Room type icons
const roomTypeIcons: Record<string, string> = {
  living_room: '🛋️',
  bedroom: '🛏️',
  kitchen: '🍳',
  bathroom: '🚿',
  dining_room: '🍽️',
  home_office: '💻',
  balcony: '🌿'
}

// Default room images for demo users
// Rooms and styles are independent - any room can be combined with any style
interface DemoRoom {
  id: string
  type_id: string
  input: string
  name: string
  nameZh: string
}

// Static fallback room images — the previous kitchen photo
// (1556909114-f6e7ad7d3136) had people working in the foreground and the
// AI was echoing them into the redesign output. Swapped to a well-known
// empty modern kitchen Unsplash photo. Other rooms retained — user only
// flagged the kitchen and the others have rendered cleanly in past runs.
const STATIC_ROOM_FALLBACKS: Record<string, string> = {
  living_room: 'https://images.unsplash.com/photo-1554995207-c18c203602cb?w=800',
  bedroom: 'https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=800',
  kitchen: 'https://images.unsplash.com/photo-1556911220-bff31c812dba?w=800',
  bathroom: 'https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800',
  dining_room: 'https://images.unsplash.com/photo-1617806118233-18e1de247200?w=800',
  home_office: 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800',
  balcony: 'https://images.unsplash.com/photo-1595526114035-0d45ed16cfbf?w=800',
}

const STATIC_ROOM_DEFS: Array<{ id: string; type_id: string; name: string; nameZh: string }> = [
  { id: 'room-1', type_id: 'living_room', name: 'Living Room', nameZh: '客廳' },
  { id: 'room-2', type_id: 'bedroom',     name: 'Bedroom',     nameZh: '臥室' },
  { id: 'room-3', type_id: 'kitchen',     name: 'Kitchen',     nameZh: '廚房' },
  { id: 'room-4', type_id: 'bathroom',    name: 'Bathroom',    nameZh: '浴室' },
  { id: 'room-5', type_id: 'dining_room', name: 'Dining Room', nameZh: '餐廳' },
  { id: 'room-6', type_id: 'home_office', name: 'Home Office', nameZh: '書房' },
  { id: 'room-7', type_id: 'balcony',     name: 'Balcony',     nameZh: '陽台' },
]

// Room picker list — the pregenerated Vertex input library wins when rows
// exist for the given type_id; otherwise we use the static Unsplash fallback
// so the view always renders something.
const defaultRooms = computed<DemoRoom[]>(() => {
  return STATIC_ROOM_DEFS.map(def => {
    const libRow = inputLibrary.value.find(
      (item: any) => item.topic === def.type_id,
    )
    return {
      ...def,
      input: (libRow?.input_image_url as string) || STATIC_ROOM_FALLBACKS[def.type_id] || '',
    }
  })
})

// Demo design styles - only relevant interior design styles for demo users
// These are the style IDs that make sense for interior design transformation
const allowedDemoStyleIds = [
  'modern_minimalist',
  'scandinavian',
  'japanese',
  'industrial',
  'mediterranean',
  'mid_century_modern'
]

// Filtered styles for display - in demo mode, only show relevant styles
const displayStyles = computed(() => {
  if (isDemoUser.value) {
    return styles.value.filter(s => allowedDemoStyleIds.includes(s.id))
  }
  return styles.value
})

// Track which demo room is selected
const selectedDemoRoomId = ref<string | null>('room-1')

// Pre-generated preset cache: key = "room-id_roomType_style", value = preset ID
const preGeneratedTemplateIds = ref<Record<string, string>>({})
// Get result key for current selection
const currentResultKey = computed(() => {
  return `${selectedDemoRoomId.value}_${selectedRoomType.value}_${selectedStyle.value}`
})

// Get pre-generated preset ID for current combination
const currentPreGeneratedTemplateId = computed(() => {
  return preGeneratedTemplateIds.value[currentResultKey.value] || null
})

// Computed
const styleName = computed(() => {
  return (style: DesignStyle) => locale.value === 'zh-TW' ? style.name_zh : style.name
})

const roomTypeName = computed(() => {
  return (room: RoomType) => locale.value === 'zh-TW' ? room.name_zh : room.name
})

const selectedRoomLabel = computed(() => {
  const room = roomTypes.value.find(r => r.id === selectedRoomType.value)
  if (room) return roomTypeName.value(room)
  const fallback = defaultRooms.value.find(r => r.type_id === selectedRoomType.value)
  return isZh.value
    ? (fallback?.nameZh || '空間')
    : L('空間', fallback?.name || 'Space', '空間', '공간', 'Espacio')
})

const proposalExamples = computed(() => {
  return allowedDemoStyleIds.map(styleId => {
    const style = styles.value.find(s => s.id === styleId)
    const template = demoTemplates.value.find(t => {
      const params = (t as any).input_params || {}
      const templateRoomType = params.room_type || t.topic
      return templateRoomType === selectedRoomType.value && params.style_id === styleId
    })
    const fallbackRoom = defaultRooms.value.find(r => r.type_id === selectedRoomType.value)
    const image = template?.thumbnail_url
      || template?.result_watermarked_url
      || template?.result_image_url
      || fallbackRoom?.input
      || ''

    return {
      styleId,
      templateId: template?.id || null,
      image,
      styleName: style ? styleName.value(style) : styleId.replace(/_/g, ' '),
      ready: Boolean(template?.id),
    }
  })
})

const showCustomPrompt = computed(() => !isDemoUser.value && ['redesign', 'generate', 'styleTransfer'].includes(activeTab.value))

const customPromptLabel = computed(() => {
  if (activeTab.value === 'generate') return t('interior.prompt')
  if (activeTab.value === 'styleTransfer') return L('補充描述（可選）', 'Additional Notes (Optional)', '追加メモ（任意）', '추가 메모 (선택)', 'Notas adicionales (opcional)')
  return L('自訂描述（可選）', 'Custom Prompt (Optional)', 'カスタムプロンプト（任意）', '커스텀 프롬프트 (선택)', 'Prompt personalizado (opcional)')
})

const pendingTitle = computed(() => isZh.value
  ? '我正在為您重新設計空間，這可能需要幾分鐘，請稍後再回來查看是否已完成。'
  : 'Redesigning your space — this may take a minute, please check back shortly.')
const pendingDetail = computed(() => L('正在生成室內設計圖...', 'Generating interior design...', 'インテリアデザインを生成中...', '인테리어 디자인 생성 중...', 'Generando diseño de interior...'))
const pendingDuration = computed(() => L('需要 1 至 2 分鐘', 'Usually takes 1 to 2 minutes', '通常1〜2分かかります', '보통 1~2분 소요', 'Suele tardar 1-2 minutos'))

function buildInteriorPrompt(): string {
  const styleInfo = styles.value.find(s => s.id === selectedStyle.value)
  const roomInfo = roomTypes.value.find(r => r.id === selectedRoomType.value)
  const styleLabel = styleInfo?.name || selectedStyle.value.replace(/_/g, ' ') || 'selected'
  const roomLabel = roomInfo?.name || selectedRoomType.value.replace(/_/g, ' ') || 'room'

  // Common constraints attached to every interior request so the output
  // always reads as a real-estate / staging photo and not an aspirational
  // lifestyle scene. Without these the model frequently invented people,
  // pets, or open floor plans that didn't match the uploaded room — which
  // is what users were reporting for the kitchen demo.
  const CONSTRAINTS = (
    'No people, no humans, no faces, no hands, no pets. '
    + 'Preserve the original walls, windows, doors, ceiling height, and overall room footprint. '
    + 'Empty interior staged only with furniture, decor, and lighting. '
    + 'Photorealistic real-estate interior photography, sharp focus, balanced exposure.'
  )

  const trimmedPrompt = prompt.value.trim()
  if (trimmedPrompt) {
    return `${trimmedPrompt}. ${CONSTRAINTS}`
  }

  return (
    `Redesign this ${roomLabel} in ${styleLabel} style while preserving the main room layout. `
    + CONSTRAINTS
  )
}

function clearGeneratedResult() {
  resultImage.value = null
  resultDescription.value = ''
  conversationId.value = null
  editHistory.value = []
  modelUrl.value = null
  demoEmptyState.value = false
}

function handleRoomFileSelected(file: File) {
  // The Generate button's :disabled binding reads `uploadedImage` (the
  // display-URL ref), so we MUST set it here when a subscriber uploads a
  // real file. Without this the button stayed disabled after upload and
  // clicks were silently dropped — which is why the e2e bot logged
  // "no_api_observed" on Room Redesign cases (see bug.md FT-010).
  if (uploadedImage.value && uploadedImage.value.startsWith('blob:')) {
    URL.revokeObjectURL(uploadedImage.value)
  }
  uploadedFile.value = file
  uploadedImage.value = URL.createObjectURL(file)
  clearGeneratedResult()
}

// Load styles and room types


onMounted(async () => {
  try {
    if (!subscriptionChecked.value) {
      await checkSubscription()
    }

    const [stylesData, roomTypesData] = await Promise.all([
      interiorApi.getStyles(),
      interiorApi.getRoomTypes()
    ])
    styles.value = stylesData
    roomTypes.value = roomTypesData

    // Load demo templates for demo users plus the Vertex-pregenerated room
    // input library. Demo clicks resolve real Material presets only.
    await Promise.all([
      loadDemoTemplates('room_redesign'),
      loadInputLibrary('room_redesign'),
    ])

    // For demo users, auto-select first default room
    if (isDemoUser.value && defaultRooms.value.length > 0) {
      const firstRoom = defaultRooms.value[0]
      selectedRoomType.value = firstRoom.type_id
      selectedDemoRoomId.value = firstRoom.id
      uploadedImage.value = firstRoom.input
      selectedStyle.value = 'modern_minimalist'  // Default style

      // Load all pre-generated results for room×roomType×style combinations
      loadAllPreGeneratedResults()
    } else if (stylesData.length > 0) {
      selectedStyle.value = stylesData[0].id
    }
  } catch (error) {
    console.error('Failed to load interior design data:', error)
  }
})

// Load pre-generated preset IDs for ALL room×roomType×style combinations from database
function loadAllPreGeneratedResults() {
  preGeneratedTemplateIds.value = {}

  // For demo, we'll check templates that match room input + room type + style
  for (const room of defaultRooms.value) {
    for (const roomType of roomTypes.value) {
      for (const style of displayStyles.value) {
        const resultKey = `${room.id}_${roomType.id}_${style.id}`

        // Find matching preset in database
        const template = demoTemplates.value.find(t =>
          ((t as any).input_params?.room_id === room.id ||
           (t as any).input_params?.input_url === room.input ||
           t.input_image_url === room.input) &&
          ((t as any).input_params?.room_type === roomType.id ||
           t.topic === roomType.id) &&
          (t as any).input_params?.style_id === style.id
        )

        if (template?.id) {
          preGeneratedTemplateIds.value[resultKey] = template.id
        }
      }
    }
  }
}

// Handlers
async function handleRedesign() {
  // For demo users, resolve the exact room×roomType×style preset through backend lookup
  if (isDemoUser.value) {
    isProcessing.value = true
    try {
      await new Promise(resolve => setTimeout(resolve, 1500))

      const preGeneratedTemplateId = currentPreGeneratedTemplateId.value
      if (preGeneratedTemplateId) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(preGeneratedTemplateId)
        if (demoResultUrl) {
          resultImage.value = demoResultUrl
          resultDescription.value = ''
          uiStore.showSuccess(L('生成成功（示範）', 'Generated successfully (Demo)', '生成成功（デモ）', '생성 성공 (데모)', 'Generado correctamente (demo)'))
          return
        }
      }

      const selectedRoom = defaultRooms.value.find(r => r.id === selectedDemoRoomId.value)
      const template = demoTemplates.value.find(t => {
        const params = (t as any).input_params || {}
        const matchesRoom = params.room_id === selectedDemoRoomId.value ||
                            params.input_url === selectedRoom?.input ||
                            t.input_image_url === selectedRoom?.input
        const matchesRoomType = params.room_type === selectedRoomType.value || t.topic === selectedRoomType.value
        const matchesStyle = params.style_id === selectedStyle.value
        return matchesRoom && matchesRoomType && matchesStyle
      })

      if (template?.id) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(template.id)
        if (demoResultUrl) {
          resultImage.value = demoResultUrl
          resultDescription.value = (template as any).result_description || ''
          preGeneratedTemplateIds.value[currentResultKey.value] = template.id
          uiStore.showSuccess(L('生成成功（示範）', 'Generated successfully (Demo)', '生成成功（デモ）', '생성 성공 (데모)', 'Generado correctamente (demo)'))
          return
        }
      }

      demoEmptyState.value = true
      uiStore.showError(L('此組合尚未預生成，請先選擇有範例的空間與風格。', 'This combination is not pre-generated yet. Please pick an available room and style example.', 'この組み合わせはまだ事前生成されていません。利用可能な部屋とスタイルの例を選んでください。', '이 조합은 아직 사전 생성되지 않았습니다. 사용 가능한 공간과 스타일 예시를 선택해 주세요.', 'Esta combinación aún no está pregenerada. Elige un ejemplo de habitación y estilo disponible.'))
    } finally {
      isProcessing.value = false
    }
    return
  }

  if (!uploadedFile.value) {
    uiStore.showError(t('interior.errors.imageRequired'))
    return
  }

  isProcessing.value = true
  try {
    const effectivePrompt = buildInteriorPrompt()
    const result = await interiorApi.demoRedesign(
      uploadedFile.value,
      effectivePrompt,
      selectedStyle.value,
      selectedRoomType.value
    )

    if (result.success && result.image_url) {
      resultImage.value = result.image_url.startsWith('http')
        ? result.image_url
        : `${window.location.origin}${result.image_url}`
      resultDescription.value = result.description || ''
      conversationId.value = result.conversation_id || null

      // Add to history
      editHistory.value.push({
        prompt: effectivePrompt,
        image: resultImage.value
      })

      uiStore.showSuccess(t('interior.success.redesigned'))
    } else {
      uiStore.showError(result.error || t('interior.errors.failed'))
    }
  } catch (error: any) {
    console.error('Redesign failed:', error)
    uiStore.showError(explainBackendError(error, t('interior.errors.failed')))
  } finally {
    isProcessing.value = false
  }
}

async function handleGenerate() {
  // Demo users cannot use Generate tab
  if (isDemoUser.value) {
    uiStore.showError(L('請訂閱以使用文字生成功能', 'Please subscribe to use text generation', 'テキスト生成機能を使うにはサブスク登録してください', '텍스트 생성 기능을 사용하려면 구독해 주세요', 'Suscríbete para usar la generación de texto'))
    return
  }

  if (!prompt.value.trim()) {
    uiStore.showError(t('interior.errors.promptRequired'))
    return
  }

  isProcessing.value = true
  try {
    const result = await interiorApi.demoGenerate({
      prompt: prompt.value,
      style_id: selectedStyle.value,
      room_type: selectedRoomType.value
    })

    if (result.success && result.image_url) {
      resultImage.value = result.image_url.startsWith('http')
        ? result.image_url
        : `${window.location.origin}${result.image_url}`
      resultDescription.value = result.description || ''
      uiStore.showSuccess(t('interior.success.generated'))
    } else {
      uiStore.showError(result.error || t('interior.errors.failed'))
    }
  } catch (error: any) {
    console.error('Generate failed:', error)
    uiStore.showError(explainBackendError(error, t('interior.errors.failed')))
  } finally {
    isProcessing.value = false
  }
}

async function handleStyleTransfer() {
  // For demo users, resolve the exact room×roomType×style preset through backend lookup
  if (isDemoUser.value) {
    isProcessing.value = true
    try {
      await new Promise(resolve => setTimeout(resolve, 1500))

      const preGeneratedTemplateId = currentPreGeneratedTemplateId.value
      if (preGeneratedTemplateId) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(preGeneratedTemplateId)
        if (demoResultUrl) {
          resultImage.value = demoResultUrl
          resultDescription.value = ''
          uiStore.showSuccess(L('風格轉換成功（示範）', 'Style applied successfully (Demo)', 'スタイル適用に成功（デモ）', '스타일 적용 성공 (데모)', 'Estilo aplicado correctamente (demo)'))
          return
        }
      }

      const selectedRoom = defaultRooms.value.find(r => r.id === selectedDemoRoomId.value)
      const template = demoTemplates.value.find(t => {
        const params = (t as any).input_params || {}
        const matchesRoom = params.room_id === selectedDemoRoomId.value ||
                            params.input_url === selectedRoom?.input ||
                            t.input_image_url === selectedRoom?.input
        const matchesStyle = params.style_id === selectedStyle.value
        return matchesRoom && matchesStyle
      })

      if (template?.id) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(template.id)
        if (demoResultUrl) {
          resultImage.value = demoResultUrl
          resultDescription.value = (template as any).result_description || ''
          preGeneratedTemplateIds.value[currentResultKey.value] = template.id
          uiStore.showSuccess(L('風格轉換成功（示範）', 'Style applied successfully (Demo)', 'スタイル適用に成功（デモ）', '스타일 적용 성공 (데모)', 'Estilo aplicado correctamente (demo)'))
          return
        }
      }

      demoEmptyState.value = true
      uiStore.showError(L('此組合尚未預生成，請先選擇有範例的空間與風格。', 'This combination is not pre-generated yet. Please pick an available room and style example.', 'この組み合わせはまだ事前生成されていません。利用可能な部屋とスタイルの例を選んでください。', '이 조합은 아직 사전 생성되지 않았습니다. 사용 가능한 공간과 스타일 예시를 선택해 주세요.', 'Esta combinación aún no está pregenerada. Elige un ejemplo de habitación y estilo disponible.'))
    } finally {
      isProcessing.value = false
    }
    return
  }

  if (!uploadedFile.value) {
    uiStore.showError(t('interior.errors.imageRequired'))
    return
  }

  if (!selectedStyle.value) {
    uiStore.showError(t('interior.errors.styleRequired'))
    return
  }

  isProcessing.value = true
  try {
    // For style transfer, use the redesign endpoint with style-focused prompt
    const styleInfo = styles.value.find(s => s.id === selectedStyle.value)
    const extraPrompt = prompt.value.trim()
    const stylePrompt = `Apply ${styleInfo?.name || selectedStyle.value} style to this room. ${styleInfo?.description || ''}${extraPrompt ? ` ${extraPrompt}` : ''}`

    const result = await interiorApi.demoRedesign(
      uploadedFile.value,
      stylePrompt,
      selectedStyle.value,
      selectedRoomType.value
    )

    if (result.success && result.image_url) {
      resultImage.value = result.image_url.startsWith('http')
        ? result.image_url
        : `${window.location.origin}${result.image_url}`
      resultDescription.value = result.description || ''
      uiStore.showSuccess(t('interior.success.styleApplied'))
    } else {
      uiStore.showError(result.error || t('interior.errors.failed'))
    }
  } catch (error: any) {
    console.error('Style transfer failed:', error)
    uiStore.showError(explainBackendError(error, t('interior.errors.failed')))
  } finally {
    isProcessing.value = false
  }
}

async function handle3DGenerate() {
  if (isDemoUser.value) {
    uiStore.showInfo(L('請訂閱以使用 3D 模型生成', 'Subscribe to use 3D model generation', '3Dモデル生成を使うにはサブスク登録してください', '3D 모델 생성을 사용하려면 구독해 주세요', 'Suscríbete para usar la generación de modelos 3D'))
    return
  }

  // Use the generated 2D result or the uploaded image as source
  let sourceUrl = resultImage.value || uploadedImage.value
  if (!sourceUrl) {
    uiStore.showError(L('請先上傳房間圖片或生成 2D 設計', 'Please upload a room image or generate a 2D design first', '先に部屋の画像をアップロードするか、2Dデザインを生成してください', '먼저 방 이미지를 업로드하거나 2D 디자인을 생성해 주세요', 'Sube primero una imagen de la habitación o genera un diseño 2D'))
    return
  }

  is3DProcessing.value = true
  isProcessing.value = true
  try {
    if (sourceUrl.startsWith('data:')) {
      const blob = await fetch(sourceUrl).then(response => response.blob())
      const uploadFile = new File([blob], 'vidgo-3d-source.png', { type: blob.type || 'image/png' })
      const uploaded = await demoApi.uploadImage(uploadFile)
      sourceUrl = uploaded.url
    }

    const result = isFloorPlan.value
      ? await interiorApi.generate3DFromFloorplan({
          image_url: sourceUrl,
          style_id: selectedStyle.value || undefined,
          room_type: floorplanRoomType.value,
          prompt: prompt.value || undefined,
          model_version: modelQuality.value
        })
      : await interiorApi.generate3DModel({
          image_url: sourceUrl,
          texture_size: textureSize.value,
          mesh_simplify: meshSimplify.value,
          model_version: modelQuality.value
        })

    if (result.success && result.model_url) {
      modelUrl.value = result.model_url
      if (isFloorPlan.value && result.preview_image_url) {
        resultImage.value = result.preview_image_url
      }
      uiStore.showSuccess(L('3D 模型生成成功', '3D model generated successfully', '3Dモデル生成に成功', '3D 모델 생성 성공', 'Modelo 3D generado correctamente'))
    } else {
      uiStore.showError(result.error || L('3D 模型生成失敗', '3D model generation failed', '3Dモデル生成に失敗', '3D 모델 생성 실패', 'Falló la generación del modelo 3D'))
    }
  } catch (error: any) {
    console.error('3D generation failed:', error)
    const detail = error.response?.data?.detail
    if (typeof detail === 'object' && detail?.error === 'insufficient_credits') {
      uiStore.showError(L('點數不足，請儲值', 'Insufficient credits', 'ポイント不足です。チャージしてください', '포인트가 부족합니다. 충전해 주세요', 'Créditos insuficientes. Recarga'))
    } else {
      uiStore.showError(typeof detail === 'string' ? detail : L('生成過程中發生錯誤', 'An error occurred', '生成中にエラーが発生しました', '생성 중 오류가 발생했습니다', 'Ocurrió un error durante la generación'))
    }
  } finally {
    is3DProcessing.value = false
    isProcessing.value = false
  }
}

async function handleTransform() {
  if (isDemoUser.value) {
    uiStore.showError(L('請訂閱以使用 AI 自由變換', 'Please subscribe to use AI Transform', 'AI自由変換を使うにはサブスク登録してください', 'AI 자유 변환을 사용하려면 구독해 주세요', 'Suscríbete para usar AI Transformación'))
    return
  }
  if (!uploadedImage.value) {
    uiStore.showError(L('請先上傳圖片', 'Please upload an image first', '先に画像をアップロードしてください', '먼저 이미지를 업로드해 주세요', 'Sube primero una imagen'))
    return
  }
  if (!transformPrompt.value.trim()) {
    uiStore.showError(L('請輸入變換描述', 'Please enter a transform description', '変換の説明を入力してください', '변환 설명을 입력해 주세요', 'Introduce una descripción de transformación'))
    return
  }

  isProcessing.value = true
  try {
    let transformUrl = uploadedImage.value
    if (uploadedImage.value.startsWith('data:')) {
      const blob = await fetch(uploadedImage.value).then(r => r.blob())
      const uploaded = await demoApi.uploadImage(blob as File)
      transformUrl = uploaded.url
    }

    const response = await effectsApi.imageTransform({
      image_url: transformUrl,
      prompt: transformPrompt.value,
      strength: transformStrength.value
    })

    if (response.success && response.result_url) {
      resultImage.value = response.result_url
      uiStore.showSuccess(L('變換成功', 'Transform applied successfully', '変換に成功', '변환 성공', 'Transformación aplicada correctamente'))
    } else {
      uiStore.showError(L('變換失敗', 'Transform failed', '変換に失敗', '변환 실패', 'Falló la transformación'))
    }
  } catch (error: any) {
    console.error('Image transform failed:', error)
    const detail = error.response?.data?.detail
    if (typeof detail === 'object' && detail?.error === 'insufficient_credits') {
      uiStore.showError(L('點數不足，請儲值', 'Insufficient credits', 'ポイント不足です。チャージしてください', '포인트가 부족합니다. 충전해 주세요', 'Créditos insuficientes. Recarga'))
    } else {
      uiStore.showError(L('處理過程中發生錯誤', 'An error occurred while processing', '処理中にエラーが発生しました', '처리 중 오류가 발생했습니다', 'Ocurrió un error durante el procesamiento'))
    }
  } finally {
    isProcessing.value = false
  }
}

function handleSubmit() {
  switch (activeTab.value) {
    case 'redesign':
      handleRedesign()
      break
    case 'generate':
      handleGenerate()
      break
    case 'styleTransfer':
      handleStyleTransfer()
      break
    case 'transform':
      handleTransform()
      break
    case '3dModel':
      handle3DGenerate()
      break
  }
}

async function selectProposalExample(example: { styleId: string; templateId: string | null }) {
  selectedStyle.value = example.styleId
  clearGeneratedResult()

  if (!example.templateId) return

  isProcessing.value = true
  try {
    const demoResultUrl = await resolveDemoTemplateResultUrl(example.templateId)
    if (demoResultUrl) {
      resultImage.value = demoResultUrl
      uiStore.showSuccess(L('已套用示範範例', 'Example applied', 'デモ例を適用しました', '데모 예시 적용됨', 'Ejemplo aplicado'))
    }
  } finally {
    isProcessing.value = false
  }
}

function reset() {
  uploadedImage.value = undefined
  uploadedFile.value = null
  resultImage.value = null
  resultDescription.value = ''
  prompt.value = ''
  conversationId.value = null
  editHistory.value = []
  modelUrl.value = null

  // For demo users, re-select first default room
  if (isDemoUser.value && defaultRooms.value.length > 0) {
    const firstRoom = defaultRooms.value[0]
    selectedDemoRoomId.value = firstRoom.id
    uploadedImage.value = firstRoom.input
    selectedRoomType.value = 'living_room'  // Reset to default
    selectedStyle.value = 'modern_minimalist'  // Reset to default
  }
}



// Update demo room pattern when room type changes
watch(selectedRoomType, (newType) => {
  if (isDemoUser.value) {
    const matchingRoom = defaultRooms.value.find(r => r.type_id === newType)
    if (matchingRoom) {
      selectedDemoRoomId.value = matchingRoom.id
      uploadedImage.value = matchingRoom.input
    } else {
      selectedDemoRoomId.value = null
      uploadedImage.value = undefined
    }
    resultImage.value = null
    resultDescription.value = ''
    demoEmptyState.value = false
  }
})

// Demo-user tab guarding is now handled by `visibleTabs` above — locked
// tabs are hidden entirely, so there's no need for a watch + error toast.
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b; color: #f5f5fa;">
    <LoadingOverlay
      :show="isProcessing"
      icon="🏠"
      :title="pendingTitle"
      :detail="pendingDetail"
      :duration="pendingDuration"
    />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
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
        <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary-500/10 border border-primary-500/20 mb-4">
          <span class="text-2xl">🏠</span>
          <span class="text-primary-400 font-medium">{{ t('interior.badge') }}</span>
        </div>
        <h1 class="text-4xl md:text-5xl font-bold text-dark-50 mb-4">
          {{ t('interior.title') }}
        </h1>
        <p class="text-xl text-dark-300 max-w-2xl mx-auto">
          {{ t('interior.subtitle') }}
        </p>
        <p class="mt-3 text-sm md:text-base text-dark-400 max-w-3xl mx-auto">
          {{ isZh
            ? '把房間照片、空屋、草圖與平面圖轉成可交付的寫實渲染，適合室內設計提案、房仲刊登、家具品牌情境圖與 3D 展示素材。'
            : 'Turn room photos, empty spaces, sketches, and floor plans into deliverable photorealistic renders for interior proposals, real estate listings, furniture scenes, and 3D presentation assets.' }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ L('訂閱以解鎖更多功能', 'Subscribe to unlock more features', 'サブスク登録で機能を解禁', '구독으로 더 많은 기능 잠금 해제', 'Suscríbete para desbloquear más funciones') }}
          </RouterLink>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div
          v-for="item in studioCapabilities"
          :key="item.title"
          class="rounded-xl p-4"
          style="background: #141420; border: 1px solid rgba(255,255,255,0.06);"
        >
          <div class="flex items-center gap-2 mb-2">
            <span class="text-xl">{{ item.icon }}</span>
            <div class="text-sm font-semibold text-dark-50">{{ item.title }}</div>
          </div>
          <p class="text-xs leading-relaxed text-dark-300 mb-3">{{ item.text }}</p>
          <p class="text-[11px] leading-relaxed text-dark-500">{{ item.proof }}</p>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-8">
        <section class="rounded-2xl p-5" style="background: #11111b; border: 1px solid rgba(82,196,26,0.18);">
          <div class="flex items-center justify-between gap-3 mb-4">
            <div>
              <p class="text-xs font-semibold uppercase tracking-wide" style="color: #95de64;">
                {{ L('專業提案流程', 'Professional Proposal Flow', 'プロ提案フロー', '전문 제안 프로세스', 'Flujo de propuesta profesional') }}
              </p>
              <h2 class="text-xl font-bold text-dark-50 mt-1">
                {{ L('像室內設計團隊一樣交付視覺方向', 'Deliver visual direction like an interior team', 'インテリアチームのようにビジュアル方向を提供', '인테리어 팀처럼 비주얼 방향 전달', 'Ofrece dirección visual como un equipo de interiorismo') }}
              </h2>
            </div>
            <RouterLink to="/tools/room-redesign" class="hidden sm:inline-flex text-xs font-semibold px-3 py-2 rounded-lg" style="background: rgba(82,196,26,0.1); color: #95de64; border: 1px solid rgba(82,196,26,0.22);">
              {{ L('開始試用', 'Start', '試してみる', '시작하기', 'Empezar') }}
            </RouterLink>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div v-for="step in proposalWorkflow" :key="step.step" class="rounded-xl p-3" style="background: rgba(255,255,255,0.035); border: 1px solid rgba(255,255,255,0.06);">
              <div class="text-xs font-bold mb-2" style="color: #95de64;">{{ step.step }}</div>
              <div class="text-sm font-semibold text-dark-50 mb-1">{{ step.title }}</div>
              <p class="text-xs leading-relaxed text-dark-400">{{ step.text }}</p>
            </div>
          </div>
        </section>

        <section class="rounded-2xl p-5" style="background: #11111b; border: 1px solid rgba(22,119,255,0.18);">
          <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-4">
            <div>
              <p class="text-xs font-semibold uppercase tracking-wide" style="color: #69b1ff;">
                {{ L('單買點數收費', 'One-time Credit Pricing', '都度ポイント購入', '단건 포인트 결제', 'Compra de créditos puntual') }}
              </p>
              <h2 class="text-xl font-bold text-dark-50 mt-1">
                {{ L('不用訂閱，也能為專案補點數', 'Top up credits for project work', 'サブスクなしでプロジェクト向けにポイント追加', '구독 없이 프로젝트용 포인트 충전', 'Recarga créditos para proyectos sin suscripción') }}
              </h2>
              <p class="text-xs leading-relaxed text-dark-400 mt-2">
                {{ L('點數包適合臨時室內提案、批次渲染、房仲素材與家具情境圖補量。', 'Credit packs are ideal for ad hoc proposals, batch renders, listing visuals, and furniture scene production.', 'ポイントパックは臨時のインテリア提案、バッチレンダリング、不動産素材、家具シーン補充に最適です。', '포인트 팩은 임시 인테리어 제안, 일괄 렌더링, 부동산 자료, 가구 씬 추가에 적합합니다.', 'Los paquetes de créditos son ideales para propuestas puntuales, renders por lotes, anuncios y escenas de mobiliario.') }}
              </p>
            </div>
            <RouterLink to="/pricing#credit-packs" class="inline-flex justify-center text-xs font-semibold px-3 py-2 rounded-lg" style="background: #1677ff; color: white;">
              {{ L('查看與購買', 'View Packs', 'パックを見る', '팩 보기', 'Ver paquetes') }}
            </RouterLink>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div v-for="pkg in roomCreditPackages" :key="pkg.name" class="rounded-xl p-3" style="background: rgba(255,255,255,0.035); border: 1px solid rgba(255,255,255,0.06);">
              <div class="text-sm font-semibold text-dark-50">{{ pkg.name }}</div>
              <div class="text-xl font-bold mt-1" style="color: #f5f5fa;">{{ pkg.price }}</div>
              <div class="text-xs text-dark-300 mt-1">{{ pkg.credits }}</div>
              <div class="text-[11px] text-dark-500 mt-2">{{ pkg.note }}</div>
            </div>
          </div>
        </section>
      </div>

      <HowToUseHint
        tool-type="room_redesign"
        media-kind="image"
        :i18n-keys="[
          'howTo.room_redesign.step1',
          'howTo.room_redesign.step2',
          'howTo.room_redesign.step3',
        ]"
      />
      <div class="flex justify-center mb-8">
        <div class="inline-flex rounded-xl p-1" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <button
            v-for="tab in visibleTabs"
            :key="tab.id"
            @click="activeTab = tab.id"
            class="px-6 py-3 rounded-lg font-medium transition-all"
            :class="activeTab === tab.id
              ? 'bg-primary-500 text-dark-50'
              : 'text-dark-300 hover:text-dark-50'"
          >
            <span class="mr-2">{{ tab.icon }}</span>
            {{ tab.label }}
          </button>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Left Panel - Input -->
        <div class="space-y-6">
          <!-- 1. Room Type Selection -->
          <div class="card" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-lg font-semibold text-dark-50 mb-4 flex items-center gap-2">
              <span>🏠</span>
              {{ t('interior.roomType') }}
            </h3>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <button
                v-for="room in roomTypes"
                :key="room.id"
                @click="selectedRoomType = room.id"
                class="p-3 rounded-xl border-2 transition-all text-center"
                :class="selectedRoomType === room.id
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'hover:border-dark-500'"
                style="border-color: rgba(255,255,255,0.08);"
              >
                <span class="text-2xl block">{{ roomTypeIcons[room.id] || '🏠' }}</span>
                <p class="text-xs text-dark-300 mt-1 truncate">{{ roomTypeName(room) }}</p>
              </button>
            </div>
          </div>

          <!-- 2. Room Image -->
          <div v-if="activeTab !== 'generate'" class="card" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-lg font-semibold text-dark-50 mb-4 flex items-center gap-2">
              <span>📷</span>
              {{ L('房間圖片', 'Room Image', '部屋の画像', '방 이미지', 'Imagen de la habitación') }}
            </h3>

            <!-- For Demo users: automatically show the image based on selected room type -->
            <div v-if="isDemoUser" class="mb-4">
              <div v-if="selectedDemoRoomId && uploadedImage" class="relative aspect-[4/3] rounded-lg overflow-hidden border-2 border-primary-500">
                <img :src="uploadedImage" alt="Room" class="w-full h-full object-cover" />
                <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-2">
                  <span class="text-xs text-white">
                    {{ isZh ? defaultRooms.find(r => r.id === selectedDemoRoomId)?.nameZh : defaultRooms.find(r => r.id === selectedDemoRoomId)?.name }}
                  </span>
                </div>
              </div>
              <div v-else class="flex flex-col items-center justify-center p-8 rounded-lg text-dark-400" style="background: #141420;">
                <span class="text-4xl mb-2">📷</span>
                <p class="text-sm text-center">
                  {{ L('目前所選擇的空間類型尚未有示範圖片，請切換至其他空間類型。', 'No demo image available for this space type. Please select another room type.', '現在選択中の部屋タイプにはデモ画像がありません。別のタイプを選択してください。', '현재 선택한 공간 유형에 데모 이미지가 없습니다. 다른 유형을 선택해 주세요.', 'No hay imagen demo para este tipo de espacio. Selecciona otro tipo.') }}
                </p>
              </div>
            </div>

            <!-- For Paid Users: Upload Zone -->
            <div v-else class="mb-6">
               <h4 class="text-sm font-medium text-dark-300 mb-2">{{ L('上傳房間照片', 'Upload Room Photo', '部屋の写真をアップロード', '방 사진 업로드', 'Subir foto de la habitación') }}</h4>
               <ImageUploader 
                 tool-type="room_redesign"
                 v-model="uploadedImage" 
                 :label="L('點擊上傳或拖放房間照片', 'Drop room photo here', 'クリックまたは部屋の写真をドロップ', '클릭 또는 방 사진을 드롭', 'Sube o arrastra una foto de la habitación')"
                 class="mb-4"
                 @file-selected="handleRoomFileSelected"
               />
               <div v-if="uploadedImage" class="mt-4 space-y-2">
                 <img :src="uploadedImage" alt="Selected Room" class="w-full rounded-xl" />
               </div>
            </div>
          </div>

          <!-- Style Selection -->
          <div class="card" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-lg font-semibold text-dark-50 mb-4 flex items-center gap-2">
              <span>🎨</span>
              {{ t('interior.designStyle') }}
            </h3>
            <div class="grid grid-cols-2 gap-3">
              <button
                v-for="style in displayStyles"
                :key="style.id"
                @click="selectedStyle = style.id"
                class="p-4 rounded-xl border-2 transition-all text-left"
                :class="selectedStyle === style.id
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'hover:border-dark-500'"
                style="border-color: rgba(255,255,255,0.08);"
              >
                <span class="text-2xl">{{ styleIcons[style.id] || '🏠' }}</span>
                <p class="font-medium text-dark-50 mt-2">{{ styleName(style) }}</p>
                <p class="text-xs text-dark-400 line-clamp-2">{{ style.description }}</p>
              </button>
            </div>
          </div>

          <div class="card" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <div class="flex items-start justify-between gap-3 mb-4">
              <div>
                <h3 class="text-lg font-semibold text-dark-50 flex items-center gap-2">
                  <span>🧩</span>
                  {{ isZh ? `${selectedRoomLabel}示範提案` : `${selectedRoomLabel} Proposal Examples` }}
                </h3>
                <p class="text-xs text-dark-400 mt-1">
                  {{ L('每個空間類型提供 6 種常用室內風格，方便比較方向。', 'Each room type includes 6 common interior style examples for quick direction comparison.', '各部屋タイプに6つの代表的なインテリアスタイル例を用意し、方向性を比較しやすくしています。', '각 공간 유형마다 대표적인 인테리어 스타일 6가지를 제공하여 방향성을 비교하기 쉽습니다.', 'Cada tipo de habitación incluye 6 ejemplos de estilo comunes para comparar direcciones rápidamente.') }}
                </p>
              </div>
              <span class="text-xs font-semibold px-2 py-1 rounded-lg" style="background: rgba(82,196,26,0.12); color: #95de64;">
                {{ proposalExamples.filter(item => item.ready).length }}/6
              </span>
            </div>

            <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
              <button
                v-for="example in proposalExamples"
                :key="example.styleId"
                type="button"
                @click="selectProposalExample(example)"
                class="text-left rounded-xl overflow-hidden border transition-all"
                :class="selectedStyle === example.styleId ? 'border-primary-500 bg-primary-500/10' : 'hover:border-dark-500'"
                style="border-color: rgba(255,255,255,0.08);"
              >
                <div class="aspect-[4/3] bg-dark-900 overflow-hidden">
                  <img v-if="example.image" :src="example.image" :alt="example.styleName" class="w-full h-full object-cover" />
                </div>
                <div class="p-2">
                  <p class="text-xs font-semibold text-dark-50 truncate">{{ example.styleName }}</p>
                  <p class="text-[11px] mt-0.5" :class="example.ready ? 'text-primary-400' : 'text-dark-500'">
                    {{ example.ready ? L('可預覽範例', 'Ready example', 'プレビュー可', '미리보기 가능', 'Ejemplo listo') : L('預生成中', 'Preparing', '事前生成中', '사전 생성 중', 'Preparando') }}
                  </p>
                </div>
              </button>
            </div>
          </div>

          <!-- Curated Prompt Dropdown (replaces free-text in MVP) -->
          <div v-if="showCustomPrompt" class="card" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
             <h3 class="text-lg font-semibold text-dark-50 mb-4 flex items-center gap-2">
               <span>✏️</span>
               {{ customPromptLabel }}
             </h3>
             <select
               v-model="selectedRoomPromptId"
               class="w-full rounded-lg p-3 focus:outline-none focus:border-primary-500"
               style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #f5f5fa;"
             >
               <option value="">{{ L('— 請選擇設計風格 —', '— Select a design style —', '— デザインスタイルを選択 —', '— 디자인 스타일 선택 —', '— Selecciona un estilo —') }}</option>
               <option v-for="opt in roomPromptOptions" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
             </select>
          </div>

          <!-- 3D Model Settings -->
          <div v-if="activeTab === '3dModel' && !isDemoUser" class="card" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-lg font-semibold text-dark-50 mb-4 flex items-center gap-2">
              <span>🧊</span>
              {{ L('3D 模型設定', '3D Model Settings', '3Dモデル設定', '3D 모델 설정', 'Ajustes del modelo 3D') }}
            </h3>

            <!-- Input requirements notice (helps users avoid the floor-plan pitfall) -->
            <div v-if="!isFloorPlan" class="notice mb-4">
              <span class="notice-icon">i</span>
              <div class="space-y-1.5">
                <p class="font-semibold" style="color: var(--text-primary);">
                  {{ L('什麼樣的圖片適合？', 'What kind of image works?', 'どんな画像が適切？', '어떤 이미지가 적합한가요?', '¿Qué tipo de imagen funciona?') }}
                </p>
                <p style="color: var(--text-secondary);">
                  {{ isZh
                    ? '請上傳真實「房間照片」或「立體物件照片」（有光影、深度）。系統會用 AI 重建為可旋轉的 3D 模型。'
                    : 'Upload a real photo of a room or a 3D object (with lighting and depth). Our AI will reconstruct it into a rotatable 3D model.' }}
                </p>
              </div>
            </div>
            <div v-if="!isFloorPlan" class="notice notice-warn mb-4">
              <span class="notice-icon">!</span>
              <div class="space-y-1.5">
                <p class="font-semibold" style="color: var(--text-primary);">
                  {{ L('上傳的是平面圖 / 設計圖？', 'Uploaded a floor plan / blueprint?', 'アップロードしたのは平面図／設計図？', '평면도 / 도면을 업로드하셨나요?', '¿Subiste un plano / blueprint?') }}
                </p>
                <p style="color: var(--text-secondary);">
                  {{ isZh
                    ? '純線稿平面圖沒有立體資訊。開啟「平面圖模式」後，系統會先用 AI 渲染成寫實室內視角，再生成 3D 模型。'
                    : 'Flat line drawings have no depth. Turn on Floor Plan Mode and we will first render a photorealistic interior, then build the 3D mesh.' }}
                </p>
                <button
                  type="button"
                  class="text-xs font-semibold mt-1"
                  style="color: #fbbf24;"
                  @click="isFloorPlan = true"
                >
                  {{ L('→ 開啟平面圖 → 3D 模式', '→ Enable Floor Plan → 3D mode', '→ 平面図→3Dモードを有効化', '→ 평면도→3D 모드 활성화', '→ Activar modo plano → 3D') }}
                </button>
              </div>
            </div>

            <!-- Floor Plan mode active notice -->
            <div v-if="isFloorPlan" class="notice mb-4" style="border-color: rgba(168, 85, 247, 0.45); background: rgba(168, 85, 247, 0.08);">
              <span class="notice-icon" style="background: var(--color-accent); color: #fff;">⌂</span>
              <div class="space-y-1.5 flex-1">
                <p class="font-semibold" style="color: var(--text-primary);">
                  {{ L('平面圖 → 3D 模式已啟用', 'Floor Plan → 3D Mode Active', '平面図→3Dモードを有効化済み', '평면도→3D 모드 활성화됨', 'Modo plano → 3D activo') }}
                </p>
                <p style="color: var(--text-secondary);">
                  {{ isZh
                    ? '兩階段流程：① Gemini 將平面圖渲染成寫實等角室內視覺圖；② Trellis2 重建為高品質 GLB 模型（約 3-7 分鐘）。'
                    : 'Two-stage pipeline: (1) Gemini renders the floor plan as a photorealistic isometric interior; (2) Trellis2 reconstructs it into a high-quality GLB mesh (~3-7 min).' }}
                </p>
                <button
                  type="button"
                  class="text-xs font-semibold mt-1"
                  style="color: var(--text-muted);"
                  @click="isFloorPlan = false"
                >
                  {{ L('× 關閉，使用一般房間照片', '× Disable, use a normal room photo', '× 無効化、通常の部屋の写真を使用', '× 비활성화, 일반 방 사진 사용', '× Desactivar, usar foto normal') }}
                </button>
              </div>
            </div>

            <div class="space-y-4">
              <div>
                <p class="text-sm text-dark-200 mb-2">
                  {{ isFloorPlan
                    ? L('已選的平面圖將先渲染為寫實室內，再生成 3D 模型。', 'The selected floor plan will be rendered to a photorealistic interior, then turned into a 3D model.', '選択した平面図はまず写実的なインテリアにレンダリングされ、その後3Dモデルに変換されます。', '선택한 평면도는 먼저 사실적인 인테리어로 렌더링된 후 3D 모델로 변환됩니다.', 'El plano seleccionado se renderiza primero como interior fotorrealista y luego se convierte en modelo 3D.')
                    : L('將 2D 圖片轉換為可互動的 3D 模型（GLB 格式）。', 'Convert a 2D image into an interactive 3D model (GLB format).', '2D画像をインタラクティブな3Dモデル（GLB形式）に変換します。', '2D 이미지를 인터랙티브한 3D 모델(GLB 형식)로 변환합니다.', 'Convierte una imagen 2D en un modelo 3D interactivo (formato GLB).') }}
                </p>
                <p v-if="resultImage && !isFloorPlan" class="text-xs text-primary-400">
                  {{ L('將使用上方的 2D 設計結果作為來源', 'Will use the 2D design result above as source', '上記の2Dデザイン結果をソースとして使用します', '위의 2D 디자인 결과를 소스로 사용합니다', 'Se usará el resultado 2D anterior como origen') }}
                </p>
                <p v-else class="text-xs text-dark-400">
                  {{ L('將使用已選擇的圖片作為來源', 'Will use the selected image as source', '選択した画像をソースとして使用します', '선택한 이미지를 소스로 사용합니다', 'Se usará la imagen seleccionada como origen') }}
                </p>
              </div>

              <!-- Model Quality (Trellis v1 vs v2) -->
              <div>
                <label class="text-sm font-medium text-dark-200 mb-1 block">
                  {{ L('模型品質', 'Model Quality', 'モデル品質', '모델 품질', 'Calidad del modelo') }}
                </label>
                <div class="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    @click="modelQuality = 'v1'"
                    class="p-3 rounded-lg border-2 text-left transition-all"
                    :class="modelQuality === 'v1' ? 'border-primary-500 bg-primary-500/10' : 'hover:border-dark-500'"
                    style="border-color: rgba(255,255,255,0.08);"
                  >
                    <p class="text-sm font-semibold" style="color: var(--text-primary);">{{ L('標準', 'Standard', '標準', '표준', 'Estándar') }}</p>
                    <p class="text-xs" style="color: var(--text-muted);">Trellis · {{ L('快速', 'Fast', '高速', '빠름', 'Rápido') }}</p>
                  </button>
                  <button
                    type="button"
                    @click="modelQuality = 'v2'"
                    class="p-3 rounded-lg border-2 text-left transition-all"
                    :class="modelQuality === 'v2' ? 'border-primary-500 bg-primary-500/10' : 'hover:border-dark-500'"
                    style="border-color: rgba(255,255,255,0.08);"
                  >
                    <p class="text-sm font-semibold" style="color: var(--text-primary);">{{ L('高品質 HD', 'High Quality', '高品質 HD', '고품질 HD', 'Alta calidad') }}</p>
                    <p class="text-xs" style="color: var(--text-muted);">Trellis2 · {{ L('精細網格', 'Finer mesh', '精細メッシュ', '정밀 메시', 'Malla refinada') }}</p>
                  </button>
                </div>
              </div>

              <!-- Floor-plan extras: room type hint -->
              <div v-if="isFloorPlan">
                <label class="text-sm font-medium text-dark-200 mb-1 block">
                  {{ L('房間類型（提示）', 'Room Type (hint)', '部屋タイプ（ヒント）', '공간 유형 (힌트)', 'Tipo de habitación (pista)') }}
                </label>
                <select
                  v-model="floorplanRoomType"
                  class="w-full rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
                  style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #f5f5fa;"
                >
                  <option value="living_room">{{ L('客廳', 'Living Room', 'リビング', '거실', 'Sala') }}</option>
                  <option value="bedroom">{{ L('臥室', 'Bedroom', '寝室', '침실', 'Dormitorio') }}</option>
                  <option value="kitchen">{{ L('廚房', 'Kitchen', 'キッチン', '주방', 'Cocina') }}</option>
                  <option value="bathroom">{{ L('浴室', 'Bathroom', 'バスルーム', '욕실', 'Baño') }}</option>
                  <option value="office">{{ L('辦公室', 'Office', 'オフィス', '사무실', 'Oficina') }}</option>
                  <option value="dining_room">{{ L('餐廳', 'Dining Room', 'ダイニング', '다이닝', 'Comedor') }}</option>
                </select>
              </div>

              <!-- Texture quality (only relevant for non-floorplan path; Trellis2 ignores) -->
              <div v-if="!isFloorPlan && modelQuality === 'v1'">
                <label class="text-sm font-medium text-dark-200 mb-1 block">
                  {{ L('貼圖品質', 'Texture Quality', 'テクスチャ品質', '텍스처 품질', 'Calidad de textura') }}
                </label>
                <select
                  v-model.number="textureSize"
                  class="w-full rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
                  style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #f5f5fa;"
                >
                  <option :value="512">512px ({{ L('較快', 'Faster', '高速', '빠름', 'Más rápido') }})</option>
                  <option :value="1024">1024px ({{ L('高品質', 'High Quality', '高品質', '고품질', 'Alta calidad') }})</option>
                </select>
              </div>

              <div v-if="!isFloorPlan && modelQuality === 'v1'">
                <div class="flex justify-between items-center mb-1">
                  <label class="text-sm font-medium text-dark-200">
                    {{ L('網格精細度', 'Mesh Detail', 'メッシュ精細度', '메시 정밀도', 'Detalle de malla') }}
                  </label>
                  <span class="text-xs text-dark-300">{{ Math.round(meshSimplify * 100) }}%</span>
                </div>
                <input
                  v-model.number="meshSimplify"
                  type="range"
                  min="0.5"
                  max="1"
                  step="0.05"
                  class="w-full h-2 rounded-lg appearance-none cursor-pointer accent-primary-500" style="background: #1e1e32;">
                />
              </div>

              <p class="text-xs text-dark-400">
                {{ isFloorPlan
                  ? L('平面圖 → 3D 約需 3-7 分鐘', 'Floor Plan → 3D takes about 3-7 minutes', '平面図→3Dは約3〜7分かかります', '평면도→3D는 약 3-7분 소요됩니다', 'El plano → 3D tarda unos 3-7 minutos')
                  : L('3D 模型生成可能需要 2-5 分鐘', '3D model generation may take 2-5 minutes', '3Dモデル生成には2〜5分かかる場合があります', '3D 모델 생성은 2-5분 소요될 수 있습니다', 'La generación 3D puede tardar 2-5 minutos') }}
              </p>
            </div>
          </div>

          <!-- AI Transform Settings (merged from ImageEffects) -->
          <div v-if="activeTab === 'transform' && !isDemoUser" class="card" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-lg font-semibold text-dark-50 mb-4 flex items-center gap-2">
              <span>🪄</span>
              {{ L('AI 自由變換設定', 'AI Transform Settings', 'AI自由変換設定', 'AI 자유 변환 설정', 'Ajustes de AI Transformación') }}
            </h3>
            <div class="space-y-4">
              <div>
                <label class="text-sm font-medium text-dark-200 mb-1 block">
                  {{ L('變換描述', 'Transform Description', '変換の説明', '변환 설명', 'Descripción de transformación') }}
                </label>
                <select
                  v-model="selectedTransformPromptId"
                  class="w-full rounded-lg p-3 focus:outline-none focus:border-primary-500"
                  style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #f5f5fa;"
                >
                  <option value="">{{ L('— 請選擇 —', '— Select —', '— 選択 —', '— 선택 —', '— Seleccionar —') }}</option>
                  <option v-for="opt in roomPromptOptions" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
                </select>
              </div>

              <div>
                <div class="flex justify-between items-center mb-1">
                  <label class="text-sm font-medium text-dark-200">
                    {{ L('變換強度', 'Transform Strength', '変換強度', '변환 강도', 'Intensidad de transformación') }}
                  </label>
                  <span class="text-xs text-dark-300">{{ Math.round(transformStrength * 100) }}%</span>
                </div>
                <input
                  v-model.number="transformStrength"
                  type="range"
                  min="0.1"
                  max="1"
                  step="0.05"
                  class="w-full h-2 rounded-lg appearance-none cursor-pointer accent-primary-500"
                  style="background: #1e1e32;"
                />
                <div class="flex justify-between text-xs text-dark-400 mt-1">
                  <span>{{ L('微調', 'Subtle', '微調整', '미세 조정', 'Sutil') }}</span>
                  <span>{{ L('大幅變換', 'Strong', '大幅な変換', '큰 변환', 'Fuerte') }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Generate Button -->
          <div class="card" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <button
              @click="handleSubmit"
              :disabled="isProcessing || (activeTab !== 'generate' && !uploadedImage)"
              class="btn-primary cta-glow w-full py-4 text-lg font-semibold"
            >
              <span v-if="isProcessing" class="flex items-center justify-center gap-2">
                <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {{ t('interior.processing') }}
              </span>
              <span v-else class="flex items-center justify-center gap-2">
                <span>✨</span>
                {{ activeTab === 'redesign' ? t('interior.actions.redesign') :
                   activeTab === 'generate' ? t('interior.actions.generate') :
                   activeTab === '3dModel' ? L('生成 3D 模型', 'Generate 3D Model', '3Dモデルを生成', '3D 모델 생성', 'Generar modelo 3D') :
                   activeTab === 'transform' ? L('AI 變換', 'AI Transform', 'AI変換', 'AI 변환', 'AI Transformación') :
                   t('interior.actions.applyStyle') }}
              </span>
            </button>
          </div>
        </div>

        <!-- Right Panel - Results -->
        <div class="space-y-6">
          <div class="card backdrop-blur h-fit sticky top-24" style="background: #0f0f17; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-lg font-semibold text-dark-50 mb-4 flex items-center gap-2">
              <span>🖼️</span>
              {{ t('interior.result') }}
            </h3>

            <div v-if="resultImage && uploadedImage && activeTab !== 'generate'" class="space-y-4">
              <BeforeAfterSlider
                :before-image="uploadedImage"
                :after-image="resultImage"
                :before-label="t('interior.before')"
                :after-label="t('interior.after')"
              />

              <p v-if="resultDescription" class="text-sm text-dark-300 italic">
                {{ resultDescription }}
              </p>

              <!-- Watermark badge -->
              <div class="text-center text-xs text-dark-400">vidgo.ai</div>

              <!-- Download / Action Buttons -->
              <div class="flex gap-3">
                 <a
                   v-if="!isDemoUser"
                   :href="resultImage"
                   download="vidgo_room_design.png"
                   class="btn-primary flex-1 text-center py-3 flex items-center justify-center"
                 >
                   <span class="mr-2">📥</span> {{ t('common.download') }}
                 </a>

                 <RouterLink
                   v-else
                   to="/pricing"
                   class="btn-primary flex-1 text-center"
                 >
                   {{ L('訂閱以獲得完整功能', 'Subscribe for Full Access', 'サブスクで全機能を解禁', '구독으로 전체 액세스', 'Suscríbete para acceso completo') }}
                 </RouterLink>

                 <button @click="reset" class="btn-ghost flex-1">
                   <span class="mr-2">🔄</span>
                   {{ t('interior.tryAnother') }}
                 </button>
              </div>
            </div>

            <div v-else-if="resultImage && activeTab === 'generate'" class="space-y-4">
              <div class="rounded-xl overflow-hidden">
                <img :src="resultImage" alt="Generated Design" class="w-full" />
              </div>

              <p v-if="resultDescription" class="text-sm text-dark-300 italic">
                {{ resultDescription }}
              </p>

              <!-- Watermark badge -->
              <div class="text-center text-xs text-dark-400">vidgo.ai</div>

              <!-- Download / Action Buttons -->
              <div class="flex gap-3">
                 <a
                   v-if="!isDemoUser"
                   :href="resultImage"
                   download="vidgo_room_design.png"
                   class="btn-primary flex-1 text-center py-3 flex items-center justify-center"
                 >
                   <span class="mr-2">📥</span> {{ t('common.download') }}
                 </a>

                 <RouterLink
                   v-else
                   to="/pricing"
                   class="btn-primary flex-1 text-center"
                 >
                   {{ L('訂閱以獲得完整功能', 'Subscribe for Full Access', 'サブスクで全機能を解禁', '구독으로 전체 액세스', 'Suscríbete para acceso completo') }}
                 </RouterLink>

                 <button @click="reset" class="btn-ghost flex-1">
                   <span class="mr-2">🔄</span>
                   {{ t('interior.tryAnother') }}
                 </button>
              </div>
            </div>

            <!-- 3D Model Result -->
            <div v-else-if="modelUrl && activeTab === '3dModel'" class="space-y-4">
              <ThreeViewer
                :model-url="modelUrl"
                :width="560"
                :height="400"
              />
              <p class="text-sm text-dark-300 text-center">
                {{ L('拖曳旋轉 / 滾輪縮放', 'Drag to rotate / Scroll to zoom', 'ドラッグで回転 / スクロールでズーム', '드래그로 회전 / 스크롤로 확대', 'Arrastra para rotar / Rueda para zoom') }}
              </p>

              <div class="flex gap-3">
                <a
                  :href="modelUrl"
                  download="vidgo_3d_model.glb"
                  class="btn-primary flex-1 text-center py-3 flex items-center justify-center"
                >
                  <span class="mr-2">📥</span> {{ L('下載 GLB 模型', 'Download GLB Model', 'GLBモデルをダウンロード', 'GLB 모델 다운로드', 'Descargar modelo GLB') }}
                </a>
                <button @click="reset" class="btn-ghost flex-1">
                  <span class="mr-2">🔄</span>
                  {{ t('interior.tryAnother') }}
                </button>
              </div>
            </div>

            <div v-else-if="demoEmptyState" class="h-80 flex flex-col items-center justify-center rounded-xl text-center px-6 gap-3" style="background: #141420; border: 1px solid rgba(255,255,255,0.08);">
              <span class="text-2xl">🔒</span>
              <p class="text-sm text-dark-200">
                {{ L('此範例尚未預生成結果', 'No pre-generated result for this example yet', 'この例はまだ事前生成されていません', '이 예시는 아직 사전 생성되지 않았습니다', 'Aún no hay resultado pregenerado') }}
              </p>
              <RouterLink to="/pricing" class="btn-primary text-sm px-4 py-2">
                {{ L('訂閱以使用完整 AI 功能', 'Subscribe to use the real AI', 'サブスクで実AI機能を解禁', '구독으로 실제 AI 사용', 'Suscríbete para usar la IA real') }}
              </RouterLink>
            </div>

            <div v-else class="h-80 flex items-center justify-center">
              <div class="text-center">
                <span class="text-6xl block mb-4">🏠</span>
                <p class="text-dark-400">{{ t('interior.resultPlaceholder') }}</p>
                <p class="text-dark-400 text-sm mt-2">{{ t('interior.resultHint') }}</p>
              </div>
            </div>
          </div>

          <!-- Features Info -->
          <div class="card bg-gradient-to-br from-primary-500/10 to-purple-500/10 border border-primary-500/20">
            <h4 class="font-semibold text-dark-50 mb-3 flex items-center gap-2">
              <span>✓</span>
              {{ L('提案級輸出標準', 'Proposal-grade output standards', '提案グレードの出力基準', '제안서 수준의 출력 기준', 'Estándares de salida para propuestas') }}
            </h4>
            <ul class="space-y-2 text-sm text-dark-300">
              <li v-for="item in deliverableStandards" :key="item" class="flex items-start gap-2">
                <span class="text-primary-400">✓</span>
                {{ item }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  @apply p-6 rounded-2xl;
  background: #141420;
  border: 1px solid rgba(255,255,255,0.06);
}

.btn-primary {
  @apply px-6 py-3 bg-gradient-to-r from-primary-500 to-primary-600 text-dark-50 font-medium rounded-xl
         hover:from-primary-600 hover:to-primary-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed;
}

.btn-ghost {
  @apply px-6 py-3 text-dark-200 font-medium rounded-xl
         hover:text-dark-50 transition-all;
  background: #1e1e32;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
