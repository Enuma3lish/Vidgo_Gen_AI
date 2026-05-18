<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { toolsApi } from '@/api'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import HowToUseHint from '@/components/common/HowToUseHint.vue'
import { downloadAsset } from '@/utils/downloadAsset'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const isZh = computed(() => locale.value.startsWith('zh'))
// 5-language inline picker — fixes ja/ko/es fall-through (BUG-017).
const { L } = useLocalized()

// Demo mode. `inputLibrary` backs the garment picker via
// `inputLibraryClothingItems` below. `loadEffectCatalog` is called in mount
// to warm the composable state; its catalog ref is not consumed in this
// view, so we don't bind it here (vue-tsc flags unused binds as errors).
const {
  isDemoUser,
  canUseCustomInputs,
  loadDemoTemplates,
  demoTemplates,
  isLoadingTemplates,
  tryPrompts,
  dbEmpty,
  resolveDemoTemplateResultUrl,
  generateOnDemand,
  loadInputLibrary,
  inputLibrary,
  loadEffectCatalog,
} = useDemoMode()

// State
const clothingImage = ref<string | undefined>(undefined)
const selectedClothingId = ref<string | null>(null)
const modelImage = ref<string | undefined>(undefined)
const resultImage = ref<string | null>(null)
const isProcessing = ref(false)
// Sidebar settings introduced with the redesigned layout. Pose / quality
// / background / size are cosmetic until the backend accepts them, but
// they're interactive so the UI matches the mockup.
// Note: pose was removed — PiAPI Kling try-on has no pose parameter
// and prompt-based pose hints didn't reliably alter the rendered pose.
// The model image itself controls the pose; pick a different model
// to change the body posture.
const quality = ref('standard')
const background = ref('random')
const sizePreset = ref('portrait')
const applyBrandStyle = ref(false)
const promptDescription = ref('')
type SidebarMenu = 'quality' | 'background' | 'size' | null
const openMenu = ref<SidebarMenu>(null)

interface PickerOption { id: string; label: string; suffix?: string }
const qualityOptions = computed<PickerOption[]>(() => [
  { id: 'standard', label: t('tools.tryOnLayout.qualityStandard') },
  { id: 'pro',      label: t('tools.tryOnLayout.qualityPro'), suffix: 'Pro' },
])
const backgroundOptions = computed<PickerOption[]>(() => [
  { id: 'random',  label: t('tools.tryOnLayout.backgroundRandom') },
  { id: 'studio',  label: t('tools.tryOnLayout.backgroundStudio') },
  { id: 'outdoor', label: t('tools.tryOnLayout.backgroundOutdoor') },
  { id: 'white',   label: t('tools.tryOnLayout.backgroundWhite') },
])
const sizeOptions = computed<PickerOption[]>(() => [
  { id: 'portrait',  label: t('tools.tryOnLayout.sizePortrait') },
  { id: 'square',   label: t('tools.tryOnLayout.sizeSquare') },
  { id: 'landscape', label: t('tools.tryOnLayout.sizeLandscape') },
])

function toggleMenu(menu: Exclude<SidebarMenu, null>) {
  openMenu.value = openMenu.value === menu ? null : menu
}
function pickQuality(id: string)    { quality.value = id; openMenu.value = null }
function pickBackground(id: string) { background.value = id; openMenu.value = null }
function pickSize(id: string)       { sizePreset.value = id; openMenu.value = null }

// Close any open popover when the user clicks outside the sidebar.
function closeMenusOnOutsideClick(event: MouseEvent) {
  if (openMenu.value === null) return
  const target = event.target as HTMLElement | null
  if (!target) return
  if (!target.closest('.settings-row, .settings-card--clickable, .popover-menu')) {
    openMenu.value = null
  }
}
onMounted(() => document.addEventListener('click', closeMenusOnOutsideClick))
onUnmounted(() => document.removeEventListener('click', closeMenusOnOutsideClick))

const qualityLabel    = computed(() => qualityOptions.value.find(o => o.id === quality.value)?.label || '')
const backgroundLabel = computed(() => backgroundOptions.value.find(o => o.id === background.value)?.label || '')
const sizeLabel       = computed(() => sizeOptions.value.find(o => o.id === sizePreset.value)?.label || '')
// True when a demo user clicked Generate but the selected tile isn't backed
// by a real Material DB preset (db_empty fallback or missing preset id).
// Surfaces a persistent in-block message instead of a silent no-op.
const demoEmptyState = ref(false)
const selectedModel = ref('avery')

// Garment category for user uploads. Drives which Kling input slot the
// image goes into (upper_input / lower_input / dress_input).
//
// Default WAS 'upper_body' which caused a second bug on 2026-05-18: users
// uploading pants who didn't notice the radio shipped the image to the
// upper_input slot → Kling failed to render. Default is now null so the
// Generate button stays disabled until the user explicitly picks. Same
// pattern as a required form field — the choice IS the load-bearing UX.
type GarmentCategory = 'upper_body' | 'lower_body' | 'dress' | 'full_body'
const uploadedGarmentCategory = ref<GarmentCategory | null>(null)

// Style templates for try-on scene/background
interface StyleTemplateItem {
  id: string
  category: string
  name_en: string
  name_zh: string
  preview_image_url?: string
  is_featured: boolean
}
const styleTemplates = ref<StyleTemplateItem[]>([])
const selectedTemplateId = ref<string | null>(null)

// Model library. Names match the new full-body PNGs generated via
// backend/scripts/generate_brand_assets.py (set=models) and uploaded
// to gs://vidgo-media-vidgo-ai/static/tryon/models/<id>.png.
//
// The `id` is the new asset id (avery, sam, taylor, …) — backward
// compatibility with the legacy `female-1..3 / male-1..3` IDs lives
// in backend `generate_model_library()` (TODO: also recognise the new
// names there, or update it to consume this list directly).
const M = 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models'
// Display names refreshed to Taiwanese / Chinese identities to match the
// regenerated Asian model imagery (see backend/scripts/generate_brand_assets.py
// model_catalog). Asset IDs are unchanged so existing TRYON_MODELS aliases
// and user-generation rows continue to resolve.
const modelOptions = ref([
  { id: 'avery',   name: 'Yi-Jun',  name_zh: '怡君',   preview: `${M}/avery.png` },
  { id: 'sam',     name: 'Zhi-Wei', name_zh: '志偉',   preview: `${M}/sam.png` },
  { id: 'taylor',  name: 'Jun-Hao', name_zh: '俊豪',   preview: `${M}/taylor.png` },
  { id: 'kendall', name: 'Xiao-Yu', name_zh: '曉雨',   preview: `${M}/kendall.png` },
  { id: 'jordan',  name: 'Guan-Yu', name_zh: '冠宇',   preview: `${M}/jordan.png` },
  { id: 'casey',   name: 'Zong-Han',name_zh: '宗翰',   preview: `${M}/casey.png` },
  { id: 'alex',    name: 'Jia-Ying',name_zh: '佳穎',   preview: `${M}/alex.png` },
  { id: 'maya',    name: 'Ya-Ting', name_zh: '雅婷',   preview: `${M}/maya.png` },
  { id: 'reece',   name: 'Hao-Ran', name_zh: '昊然',   preview: `${M}/reece.png` },
  { id: 'lena',    name: 'Mei-Ling',name_zh: '美玲',   preview: `${M}/lena.png` },
  { id: 'julia',   name: 'Pei-Shan',name_zh: '佩珊',   preview: `${M}/julia.png` },
])

// Clothing types that are restricted for male models
const femaleOnlyClothingTypes = ['dress', 'skirt', 'short_skirt', 'mini_skirt']

// Check if selected model is male
// Male model lookup — used to block obvious mismatches like a male model
// in a dress. The new asset IDs aren't gender-prefixed, so we map by id.
const MALE_MODEL_IDS = new Set(['sam', 'taylor', 'jordan', 'casey', 'reece'])
const isMaleModel = computed(() => MALE_MODEL_IDS.has(selectedModel.value))

// Resolved preview + display name for the currently-selected model. Drives
// the "Model" card in the sidebar. Returns custom-upload values when the
// user has chosen the upload tile.
const selectedModelPreview = computed(() => {
  if (selectedModel.value === 'custom') return modelImage.value || ''
  return modelOptions.value.find(m => m.id === selectedModel.value)?.preview || ''
})
const selectedModelName = computed(() => {
  if (selectedModel.value === 'custom') return L('自訂', 'Custom', 'カスタム', '커스텀', 'Personalizado')
  const model = modelOptions.value.find(m => m.id === selectedModel.value)
  return model ? (isZh.value ? model.name_zh : model.name) : ''
})

const pendingTitle = computed(() => isZh.value
  ? '我正在為您生成試穿效果，這可能需要幾分鐘，請稍後再回來查看是否已完成。'
  : 'Generating your virtual try-on. This may take a minute — please check back shortly.')
const pendingDetail = computed(() => L('正在生成試穿圖片...', 'Generating try-on image...', '試着画像を生成中...', '시착 이미지 생성 중...', 'Generando imagen de prueba...'))
const pendingDuration = computed(() => L('需要 1 至 2 分鐘', 'Usually takes 1 to 2 minutes', '通常1〜2分かかります', '보통 1-2분 소요', 'Suele tardar 1-2 minutos'))

// Get unique clothing items from database (grouped by clothing_id)
// Each clothing item may have multiple results for different models
const demoClothingItems = computed(() => {
  // Group templates by clothing_id to get unique clothing items
  const clothingMap = new Map<string, {
    id: string
    name: string
    preview: string
    clothingType: string
    genderRestriction: string | null
  }>()

  demoTemplates.value
    .filter(t => t.input_image_url)
    .forEach(t => {
      const params = (t as any).input_params || {}
      const clothingId = params.clothing_id || t.id

      // Only add if not already in map (to avoid duplicates)
      if (!clothingMap.has(clothingId)) {
        // Get clothing type from input_params (set by backend) or detect from prompt
        let clothingType = params.clothing_type || 'general'
        if (clothingType === 'general') {
          // Fallback: detect from prompt/style_tags
          const prompt = (t.prompt || '').toLowerCase()
          const promptZh = (t.prompt_zh || '').toLowerCase()
          const styleTags = (t.style_tags || []).map((tag: string) => tag.toLowerCase())

          if (prompt.includes('dress') || promptZh.includes('裙') || promptZh.includes('洋裝') ||
              styleTags.some((tag: string) => tag.includes('dress'))) {
            clothingType = 'dress'
          } else if (prompt.includes('skirt') || promptZh.includes('短裙') || promptZh.includes('裙子') ||
              styleTags.some((tag: string) => tag.includes('skirt'))) {
            clothingType = 'skirt'
          }
        }

        clothingMap.set(clothingId, {
          id: clothingId,
          name: isZh.value ? (t.prompt_zh || t.prompt) : t.prompt,
          preview: t.input_image_url || '',
          clothingType,
          genderRestriction: params.gender_restriction || null
        })
      }
    })

  return Array.from(clothingMap.values())
})

// Fallback clothing items from try_prompts (when DB is empty)
const fallbackClothingItems = computed(() => {
  if (!dbEmpty.value || tryPrompts.value.length === 0) return []
  return tryPrompts.value.map((p: any) => ({
    id: p.id,
    name: p.prompt,
    preview: p.image_url || '',
    clothingType: p.clothing_type || 'general',
    genderRestriction: null
  }))
})

// Pregenerated garment library (Vertex Imagen → GCS). Rows are input-only
// (null result URLs); the try-on result is resolved per click via cache-
// through against the picked (garment, model) pair.
const inputLibraryClothingItems = computed(() => {
  return inputLibrary.value
    .filter((item: any) => item.input_image_url)
    .map((item: any) => {
      const params = item.input_params || {}
      return {
        id: item.id,
        name: isZh.value ? (item.prompt || item.topic) : (item.prompt || item.topic),
        preview: item.input_image_url as string,
        clothingType: item.topic || params.clothing_type || 'general',
        genderRestriction: params.gender_restriction || null,
      }
    })
})

// Display items: Vertex input library first, then DB finished-example
// inputs, then try_prompts fallback, then static Unsplash.
//
// We *always* append SUPPLEMENTAL_MENS_CLOTHING to whichever primary
// source wins. Without this, production users only see the 2 female
// Material rows in the input library and have no men's example to
// click — which is exactly the bug reported on 2026-05-17.
const displayClothingItems = computed(() => {
  let primary: any[] = []
  if (inputLibraryClothingItems.value.length > 0) {
    primary = inputLibraryClothingItems.value
  } else if (demoClothingItems.value.length > 0) {
    primary = demoClothingItems.value
  } else if (fallbackClothingItems.value.length > 0) {
    primary = fallbackClothingItems.value
  } else {
    primary = STATIC_CLOTHING.map(c => ({
      id: c.id,
      name: c.label,
      preview: c.url,
      clothingType: c.clothingType || 'general',
      genderRestriction: null,
    }))
    return primary  // STATIC already has men's items baked in
  }
  // Backend wins → append men's supplements so the picker is never all-female.
  const supplements = SUPPLEMENTAL_MENS_CLOTHING.map(c => ({
    id: c.id,
    name: c.label,
    preview: c.url,
    clothingType: c.clothingType,
    genderRestriction: null,
  }))
  return [...primary, ...supplements]
})

// Get selected clothing type
const selectedClothingType = computed(() => {
  if (!selectedClothingId.value) return null
  const item = displayClothingItems.value.find(c => c.id === selectedClothingId.value)
  return item?.clothingType || 'general'
})

// Check if current combination is valid (male + dress/skirt = invalid)
const isValidCombination = computed(() => {
  if (!selectedClothingType.value) return true
  if (isMaleModel.value && femaleOnlyClothingTypes.includes(selectedClothingType.value)) {
    return false
  }
  return true
})


// Static clothing fallback images (shown when backend DB is empty).
// Balanced 6 men's + 4 women's + unisex so the picker grid never lands
// in a women-only state for users on production where the Material
// table currently only has 2 female-model entries.
const STATIC_CLOTHING = [
  // Men's
  { id: 'c_m1', url: 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400&fit=crop', label: 'White T-Shirt', clothingType: 'upper_body' },
  { id: 'c_m2', url: 'https://images.unsplash.com/photo-1542272604-787c3835535d?w=400&fit=crop', label: 'Mens Jeans', clothingType: 'lower_body' },
  { id: 'c_m3', url: 'https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=400&fit=crop', label: 'Denim Jacket', clothingType: 'upper_body' },
  { id: 'c_m4', url: 'https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?w=400&fit=crop', label: 'Black Hoodie', clothingType: 'upper_body' },
  { id: 'c_m5', url: 'https://images.unsplash.com/photo-1564584217132-2271feaeb3c5?w=400&fit=crop', label: 'Polo Shirt', clothingType: 'upper_body' },
  { id: 'c_m6', url: 'https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=400&fit=crop', label: 'Chino Trousers', clothingType: 'lower_body' },
  // Women's
  { id: 'c_w1', url: 'https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=400&fit=crop', label: 'White Blouse', clothingType: 'upper_body' },
  { id: 'c_w2', url: 'https://images.unsplash.com/photo-1594938298603-c8148c4b4357?w=400&fit=crop', label: 'Blue Dress', clothingType: 'dress' },
  { id: 'c_w3', url: 'https://images.unsplash.com/photo-1578587018452-892bacefd3f2?w=400&fit=crop', label: 'Floral Dress', clothingType: 'dress' },
  { id: 'c_w4', url: 'https://images.unsplash.com/photo-1551803091-e20673f15770?w=400&fit=crop', label: 'Pleated Skirt', clothingType: 'lower_body' },
]

// Hand-curated supplemental items always merged into the picker, regardless
// of what the backend returns. Without this, production users see only the
// 2 female Material rows the input library currently has — no men's
// examples at all. These render after the backend rows.
const SUPPLEMENTAL_MENS_CLOTHING = [
  { id: 'sup_m1', url: 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400&fit=crop', label: 'White T-Shirt', clothingType: 'upper_body' },
  { id: 'sup_m2', url: 'https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=400&fit=crop', label: 'Denim Jacket', clothingType: 'upper_body' },
  { id: 'sup_m3', url: 'https://images.unsplash.com/photo-1542272604-787c3835535d?w=400&fit=crop', label: 'Mens Jeans', clothingType: 'lower_body' },
  { id: 'sup_m4', url: 'https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?w=400&fit=crop', label: 'Black Hoodie', clothingType: 'upper_body' },
]

// Load demo presets on mount
onMounted(async () => {
  await Promise.all([
    loadDemoTemplates('try_on'),
    // Pregenerated garment inputs (Vertex Imagen → GCS) and garment-category
    // effect catalog so the picker's (input × effect) pair matches the
    // backend's lookup_hash key.
    loadInputLibrary('try_on'),
    loadEffectCatalog('try_on', locale.value),
  ])

  // Load curated style templates for try-on scenes
  try {
    const { templates } = await toolsApi.getStyleTemplates('try_on')
    styleTemplates.value = templates
  } catch (e) {
    console.warn('Failed to load try-on style templates:', e)
  }
})

watch(locale, () => loadEffectCatalog('try_on', locale.value))

// Kling AI is trained on garments. If an accessory slips into the catalog we
// still let the user click it, but surface a clear toast up-front so the
// unexpected result is explained before they hit Generate.
const ACCESSORY_KEYWORDS = [
  'hat', 'cap', 'beanie', 'sunglass', 'glasses', 'watch', 'scarf',
  'earring', 'necklace', 'bracelet', 'ring', 'bag', 'shoe', 'boot',
  '帽', '眼鏡', '太陽眼鏡', '手錶', '圍巾', '絲巾', '耳環', '項鍊',
  '手鍊', '戒指', '包', '鞋', '靴',
]

function isAccessoryItem(name: string, clothingType?: string): boolean {
  if (clothingType && clothingType !== 'general' && clothingType !== 'dress') {
    // Non-general/dress types from the backend are explicit hints
    const nonGarment = ['hat', 'glasses', 'watch', 'scarf', 'jewelry', 'bag', 'shoes', 'accessory']
    if (nonGarment.includes(clothingType)) return true
  }
  const lower = (name || '').toLowerCase()
  return ACCESSORY_KEYWORDS.some(k => lower.includes(k))
}

function selectDemoClothing(item: { id: string; name?: string; clothingType?: string; preview?: string; watermarked_result?: string }) {
  selectedClothingId.value = item.id
  clothingImage.value = item.preview || undefined
  resultImage.value = null
  demoEmptyState.value = false
  if (isAccessoryItem(item.name || '', item.clothingType)) {
    uiStore.showInfo(isZh.value
      ? '此項為配件，AI 試穿不一定能正確呈現，結果僅供參考'
      : 'This is an accessory. Virtual try-on may not render it correctly — results are indicative only.')
  }
}

async function generateTryOn() {
  if (!clothingImage.value && !selectedClothingId.value) return

  // Validate: Male models cannot wear dresses/skirts
  if (!isValidCombination.value) {
    uiStore.showError(isZh.value
      ? '男性模特不能穿著裙子或洋裝，請選擇其他服裝或女性模特'
      : 'Male models cannot wear dresses or skirts. Please select different clothing or a female model.')
    return
  }

  // Clear stale result so the loading overlay is the only thing visible
  // until the new try-on finishes.
  resultImage.value = null
  demoEmptyState.value = false
  isProcessing.value = true
  try {
    // For demo users, resolve the exact model+clothing preset through backend lookup
    if (isDemoUser.value && selectedClothingId.value) {
      await new Promise(resolve => setTimeout(resolve, 500))

      const template = demoTemplates.value.find(t => {
        const params = (t as any).input_params || {}
        return params.clothing_id === selectedClothingId.value && params.model_id === selectedModel.value
      })

      if (template?.id) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(template.id)
        if (demoResultUrl) {
          resultImage.value = demoResultUrl
          uiStore.showSuccess(L('生成成功（示範）', 'Generated successfully (Demo)', '生成成功（デモ）', '생성 성공 (데모)', 'Generado correctamente (demo)'))
          return
        }
      }

      // Cache-through on demand. Try-on uses PiAPI REST (no MCP path).
      // Pass model_id via product_id (API only exposes one extra param) and
      // the garment category via topic so the backend picks the right pair.
      const garmentTopic = (demoTemplates.value.find(t => (t as any).input_params?.clothing_id === selectedClothingId.value) as any)?.topic
      uiStore.showInfo(L('此組合尚未生成，正在為您即時生成（約 30-60 秒）...', 'Generating in real-time (30-60s)...', 'リアルタイム生成中（約30〜60秒）...', '실시간으로 생성 중 (약 30-60초)...', 'Generando en tiempo real (30-60s)...'))
      const pickedGarment = (demoTemplates.value.find((t: any) => t.input_params?.clothing_id === selectedClothingId.value) as any)?.input_image_url
      const onDemandUrl = await generateOnDemand('try_on', garmentTopic, {
        product_id: selectedModel.value,
        input_image_url: pickedGarment || clothingImage.value,
      })
      if (onDemandUrl) {
        resultImage.value = onDemandUrl
        uiStore.showSuccess(L('試穿成功', 'Try-on successful', '試着成功', '시착 성공', 'Prueba exitosa'))
        return
      }
      demoEmptyState.value = true
      uiStore.showError(L('試穿服務暫時無法使用，請稍後再試或訂閱解鎖完整功能', 'Try-on service temporarily unavailable. Please try again later or subscribe.', '試着サービスは一時的に利用できません。後ほど再試行するか、サブスク登録してください。', '시착 서비스를 일시적으로 사용할 수 없습니다. 나중에 다시 시도하거나 구독해 주세요.', 'Servicio temporalmente no disponible. Inténtalo más tarde o suscríbete.'))
      return
    }

    // For subscribed users or if no cached result
    let imageUrl = clothingImage.value

    // Upload if custom image (data URI from file picker)
    if (clothingImage.value && clothingImage.value.startsWith('data:')) {
      const blob = dataURItoBlob(clothingImage.value)
      if (!blob) {
        uiStore.showError(L('圖片格式無效，請重新上傳', 'Invalid image format. Please re-upload.', '画像形式が無効です。再アップロードしてください。', '이미지 형식이 올바르지 않습니다. 다시 업로드해 주세요.', 'Formato de imagen inválido. Súbela de nuevo.'))
        return
      }
      const uploadResult = await toolsApi.uploadImage(blob as File)
      imageUrl = uploadResult.url
    }

    let modelUrl = null
    if (selectedModel.value === 'custom' && modelImage.value) {
      if (modelImage.value.startsWith('data:')) {
        const blob = dataURItoBlob(modelImage.value)
        if (!blob) {
          uiStore.showError(L('模特圖片格式無效', 'Invalid model image format.', 'モデル画像の形式が無効です。', '모델 이미지 형식이 올바르지 않습니다.', 'Formato de imagen del modelo inválido.'))
          return
        }
        const modelUpload = await toolsApi.uploadImage(blob as File)
        modelUrl = modelUpload.url
      } else {
        modelUrl = modelImage.value
      }
    }

    // Resolve the garment category. For a preset tile we already know the
    // clothingType — map skirts/dresses to 'dress' (Kling's dress_input
    // slot), 'general' to 'dress' too. For a custom upload, use whatever
    // the user picked in the upper/lower/dress radio (required — the
    // Generate button is disabled until they pick).
    let category: GarmentCategory
    if (selectedClothingId.value) {
      const ct = (selectedClothingType.value || '').toLowerCase()
      if (ct === 'upper_body') category = 'upper_body'
      else if (ct === 'lower_body' || ct === 'skirt') category = 'lower_body'
      else if (ct === 'full_body') category = 'full_body'
      else category = 'dress'
    } else if (uploadedGarmentCategory.value) {
      category = uploadedGarmentCategory.value
    } else {
      // Defensive: should be unreachable thanks to the button-disable, but
      // if the form is submitted some other way we refuse rather than send
      // the wrong slot.
      uiStore.showError(L('請先選擇服裝類型', 'Please pick the garment type first', '服のタイプを選択してください', '의상 타입을 먼저 선택해 주세요', 'Selecciona el tipo de prenda primero'))
      isProcessing.value = false
      return
    }

    const result = await toolsApi.tryOn(imageUrl!, {
      modelImageUrl: modelUrl ?? undefined,
      modelId: selectedModel.value !== 'custom' ? selectedModel.value : undefined,
      templateId: selectedTemplateId.value || undefined,
      angle: 'front',
      category,
    })

    if (result.success && (result.image_url || result.result_url)) {
      resultImage.value = result.image_url || result.result_url || null
      if (result.credits_used) {
        creditsStore.deductCredits(result.credits_used)
      }
      uiStore.showSuccess(t('common.success'))
    } else {
      const errMsg = result.message || (result as any).error || L('生成失敗，請稍後再試', 'Generation failed. Please try again.', '生成に失敗しました。後ほど再試行してください。', '생성에 실패했습니다. 나중에 다시 시도해 주세요.', 'Falló la generación. Inténtalo de nuevo.')
      uiStore.showError(errMsg)
    }
  } catch (error: any) {
    const detail = error?.response?.data?.detail || error?.response?.data?.message || error?.message || ''
    uiStore.showError(detail || L('生成失敗', 'Generation failed', '生成に失敗', '생성 실패', 'Falló la generación'))
  } finally {
    isProcessing.value = false
  }
}

function handleBack() {
  router.back()
}

function dataURItoBlob(dataURI: string): Blob | null {
  if (!dataURI || !dataURI.includes(',') || !dataURI.startsWith('data:')) {
    return null
  }
  try {
    const byteString = atob(dataURI.split(',')[1])
    const mimeString = dataURI.split(',')[0].split(':')[1].split(';')[0]
    const ab = new ArrayBuffer(byteString.length)
    const ia = new Uint8Array(ab)
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i)
    }
    return new Blob([ab], { type: mimeString })
  } catch {
    return null
  }
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b; color: #f5f5fa;">
    <LoadingOverlay
      :show="isProcessing"
      icon="👗"
      :title="pendingTitle"
      :detail="pendingDetail"
      :duration="pendingDuration"
    />

    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Back Button -->
      <button
        @click="handleBack"
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
          {{ t('tools.tryOn.name') }}
        </h1>
        <p class="text-xl text-dark-300">
          {{ t('tools.tryOn.longDesc') }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ L('訂閱以解鎖更多功能', 'Subscribe to unlock more features', 'サブスク登録で機能を解禁', '구독으로 더 많은 기능 잠금 해제', 'Suscríbete para desbloquear más funciones') }}
          </RouterLink>
        </div>
      </div>

      <HowToUseHint
        tool-type="try_on"
        media-kind="image"
        :i18n-keys="[
          'howTo.try_on.step1',
          'howTo.try_on.step2',
          'howTo.try_on.step3',
        ]"
      />

      <div class="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-6">
        <!-- LEFT SIDEBAR — generation settings -->
        <aside class="card space-y-5">
          <div class="flex items-center justify-between">
            <h2 class="text-base font-semibold text-dark-50 flex items-center gap-2">
              {{ t('tools.tryOn.name') }}
              <svg class="w-4 h-4 text-dark-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
              </svg>
            </h2>
          </div>

          <!-- Kling AI limitation notice -->
          <div class="p-3 rounded-lg" style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.24);">
            <p class="text-[11px] text-amber-400 leading-relaxed">
              <span class="font-semibold">{{ L('⚠️ 提示：', '⚠️ Note: ', '⚠️ 注意：', '⚠️ 참고: ', '⚠️ Nota: ') }}</span>
              {{ isZh
                ? 'AI 試穿適用於完整服裝。配件類可能無法正確呈現。'
                : 'Virtual try-on works best with full garments. Accessories may not render correctly.' }}
            </p>
          </div>

          <!-- Clothing upload + preview -->
          <div>
            <ImageUploader
              tool-type="try_on"
              v-model="clothingImage"
              :label="L('拖曳檔案或選擇圖片', 'Drag a file or choose an image', 'ファイルをドラッグまたは選択', '파일을 드래그하거나 선택', 'Arrastra un archivo o elige una imagen')"
              class="mb-3"
            />
            <div v-if="clothingImage" class="space-y-2">
              <img :src="clothingImage" alt="Clothing" class="w-full rounded-lg" />

              <!-- Garment category picker for custom uploads. Without
                   this, Kling's try-on defaults to dress_input and
                   improvises a full outfit, producing the jacket+pants
                   hybrid bug when users upload jeans alone. -->
              <div v-if="!selectedClothingId" class="rounded-lg p-3" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
                <p class="text-xs font-medium mb-2" style="color: #d1d1e0;">
                  {{ L('服裝類型', 'Garment Type', '服のタイプ', '의상 타입', 'Tipo de prenda') }}
                </p>
                <div class="grid grid-cols-3 gap-2">
                  <button
                    v-for="opt in [
                      { id: 'upper_body', label: L('上身', 'Upper', 'トップス', '상의', 'Sup.') },
                      { id: 'lower_body', label: L('下身', 'Lower', 'ボトムス', '하의', 'Inf.') },
                      { id: 'dress',      label: L('連身', 'Full', 'ワンピース', '원피스', 'Vestido') },
                    ]"
                    :key="opt.id"
                    @click="uploadedGarmentCategory = opt.id as GarmentCategory"
                    class="py-2 rounded text-xs font-medium transition-colors"
                    :style="uploadedGarmentCategory === opt.id
                      ? 'background: #f59e0b; color: #0a0a0a;'
                      : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.08);'"
                  >
                    {{ opt.label }}
                  </button>
                </div>
                <p class="text-[10px] mt-2 leading-tight" style="color: #6b6b8a;">
                  {{ L('上傳的圖只有一件上半身或下半身時，請選對應類型，避免 AI 自動補上不該有的衣物。', 'When your upload shows only an upper or lower garment, pick the matching type so the AI does not invent missing pieces.', 'アップロードがトップス・ボトムス単体の場合は、対応するタイプを選んでください。', '업로드가 상의 또는 하의 단품일 때 해당 타입을 선택하세요.', 'Si tu imagen muestra solo una prenda superior o inferior, elige el tipo correspondiente.') }}
                </p>
              </div>

              <button
                v-if="canUseCustomInputs"
                @click="clothingImage = undefined; selectedClothingId = null; uploadedGarmentCategory = null"
                class="btn-ghost text-xs w-full"
              >
                {{ L('更換服裝', 'Change Clothing', '服を変更', '의상 변경', 'Cambiar ropa') }}
              </button>
            </div>
          </div>

          <!-- Model row — pose card removed because the underlying
               try-on API doesn't accept a pose parameter and prompt
               hints didn't reliably alter the rendered pose. Users
               pick a different model in the right-hand grid to change
               the body posture. -->
          <div class="settings-card">
            <div class="settings-card-thumb">
              <img v-if="selectedModelPreview" :src="selectedModelPreview" alt="Model" />
              <span v-else class="text-xl">👤</span>
            </div>
            <div>
              <p class="settings-card-label">{{ t('tools.tryOnLayout.selectModel') }}</p>
              <p class="settings-card-value">{{ selectedModelName }}</p>
            </div>
          </div>

          <!-- Quality / Background / Size / Brand style rows -->
          <div>
            <button type="button" @click="toggleMenu('quality')" class="settings-row relative w-full">
              <span class="settings-row-label">{{ t('tools.tryOnLayout.quality') }}</span>
              <!-- Mockup shows "Standard" with a "Pro" pill next to it —
                   the pill is an upsell hint when the user is on Standard,
                   not the active selection. -->
              <span class="settings-row-value">
                {{ qualityLabel }}
                <span v-if="quality === 'standard'" class="pro-pill">Pro</span>
              </span>
              <div v-if="openMenu === 'quality'" class="popover-menu" @click.stop>
                <button v-for="opt in qualityOptions" :key="opt.id" @click="pickQuality(opt.id)" class="popover-item" :class="{ 'popover-item--active': opt.id === quality }">
                  <span>{{ opt.label }}</span>
                  <span v-if="opt.suffix" class="pro-pill">{{ opt.suffix }}</span>
                </button>
              </div>
            </button>
            <button type="button" @click="toggleMenu('background')" class="settings-row relative w-full">
              <span class="settings-row-label">{{ t('tools.tryOnLayout.background') }}</span>
              <span class="settings-row-value">{{ backgroundLabel }} 🎨</span>
              <div v-if="openMenu === 'background'" class="popover-menu" @click.stop>
                <button v-for="opt in backgroundOptions" :key="opt.id" @click="pickBackground(opt.id)" class="popover-item" :class="{ 'popover-item--active': opt.id === background }">
                  {{ opt.label }}
                </button>
              </div>
            </button>
            <button type="button" @click="toggleMenu('size')" class="settings-row relative w-full">
              <span class="settings-row-label">{{ t('tools.tryOnLayout.size') }}</span>
              <span class="settings-row-value">{{ sizeLabel }}</span>
              <div v-if="openMenu === 'size'" class="popover-menu" @click.stop>
                <button v-for="opt in sizeOptions" :key="opt.id" @click="pickSize(opt.id)" class="popover-item" :class="{ 'popover-item--active': opt.id === sizePreset }">
                  {{ opt.label }}
                </button>
              </div>
            </button>
            <div class="settings-row">
              <span class="settings-row-label">{{ t('tools.tryOnLayout.applyBrandStyle') }}</span>
              <label class="toggle-switch" :class="{ 'toggle-switch--on': applyBrandStyle }">
                <input type="checkbox" v-model="applyBrandStyle" class="sr-only" />
                <span class="toggle-switch-thumb"></span>
              </label>
            </div>
          </div>

          <textarea
            v-model="promptDescription"
            rows="3"
            :placeholder="t('tools.tryOnLayout.describePrompt')"
            class="w-full rounded-lg p-3 text-sm focus:outline-none focus:border-primary-500"
            style="background: #0f0f17; border: 1px solid rgba(255,255,255,0.08); color: #f5f5fa;"
          ></textarea>

          <div>
            <CreditCost service="virtual_try_on" />
            <div v-if="!isValidCombination" class="mt-3 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
              <p class="text-sm text-red-400">
                {{ L('⚠️ 男性模特不能穿著裙子或洋裝', '⚠️ Male models cannot wear dresses or skirts', '⚠️ 男性モデルはスカートやドレスを着用できません', '⚠️ 남성 모델은 스커트나 드레스를 입을 수 없습니다', '⚠️ Los modelos masculinos no pueden llevar vestidos o faldas') }}
              </p>
            </div>
            <!-- For custom uploads the category radio must be picked
                 first — otherwise pants land in the upper_input slot and
                 Kling fails. Preset tiles carry their own clothingType
                 so they never need the radio. -->
            <button
              @click="generateTryOn"
              :disabled="(!clothingImage && !selectedClothingId) || isProcessing || !isValidCombination || (!!clothingImage && !selectedClothingId && !uploadedGarmentCategory)"
              class="btn-primary w-full mt-3"
              style="background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%);"
              :class="{ 'opacity-50 cursor-not-allowed': !isValidCombination || (!!clothingImage && !selectedClothingId && !uploadedGarmentCategory) }"
            >
              {{ t('tools.tryOnLayout.generateOne') }}
            </button>
            <p
              v-if="!!clothingImage && !selectedClothingId && !uploadedGarmentCategory"
              class="text-[11px] mt-2"
              style="color: #fbbf24;"
            >
              {{ L('請先在上方選擇上身 / 下身 / 連身', 'Pick Upper / Lower / Full above first', '上で上身・下身・全身を選択してください', '먼저 위에서 상의 / 하의 / 원피스 선택', 'Selecciona arriba: superior / inferior / vestido') }}
            </p>
          </div>
        </aside>

        <!-- RIGHT MAIN — model grid, clothing presets, result -->
        <main class="space-y-8">
          <!-- Preset clothing (demo + curated) -->
          <section v-if="isDemoUser || displayClothingItems.length > 0" class="card">
            <h3 class="text-base font-semibold text-dark-50 mb-3">
              {{ L('預設服裝（示範）', 'Preset Clothing (Demo)', 'プリセット服（デモ）', '프리셋 의상 (데모)', 'Ropa preestablecida (demo)') }}
            </h3>
            <div v-if="isLoadingTemplates" class="flex justify-center py-8">
              <div class="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
            </div>
            <div v-else class="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-3">
              <button
                v-for="item in displayClothingItems"
                :key="item.id"
                @click="selectDemoClothing(item)"
                class="aspect-[3/4] rounded-lg overflow-hidden border-2 transition-all"
                :class="selectedClothingId === item.id ? 'border-primary-500' : 'hover:border-dark-500'"
                style="border-color: rgba(255,255,255,0.08);"
              >
                <img v-if="item.preview" :src="item.preview" :alt="item.name" class="w-full h-full object-cover" />
                <div v-else class="w-full h-full flex items-center justify-center" style="background: #141420;">
                  <span class="text-2xl">👔</span>
                </div>
              </button>
            </div>
          </section>

          <!-- Model selection grid -->
          <section class="card">
            <h3 class="text-base font-semibold text-dark-50 mb-4">
              {{ L('選擇模特', 'Select Model', 'モデルを選択', '모델 선택', 'Selecciona modelo') }}
            </h3>
            <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
              <!-- Upload tile (subscribers only). Mockup shows a clean
                   white card with just a "+" — no label below — so the
                   "Upload your own" name only appears as a tooltip. -->
              <button
                v-if="!isDemoUser"
                @click="selectedModel = 'custom'"
                class="model-tile"
                :class="selectedModel === 'custom' ? 'model-tile--active' : ''"
                :title="t('tools.tryOnLayout.uploadOwn')"
                :aria-label="t('tools.tryOnLayout.uploadOwn')"
              >
                <div class="aspect-[3/4] w-full rounded-lg flex items-center justify-center" style="background: #f5f5fa; color: #6b6b8a;">
                  <svg class="w-9 h-9" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
                </div>
              </button>

              <button
                v-for="model in modelOptions"
                :key="model.id"
                @click="selectedModel = model.id"
                class="model-tile"
                :class="selectedModel === model.id ? 'model-tile--active' : ''"
              >
                <div class="aspect-[3/4] w-full rounded-lg overflow-hidden relative">
                  <img :src="model.preview" :alt="model.name" class="w-full h-full object-cover" />
                  <div
                    v-if="selectedModel === model.id"
                    class="absolute top-2 right-2 w-6 h-6 rounded-full flex items-center justify-center"
                    style="background: #7c3aed;"
                  >
                    <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
                  </div>
                </div>
                <p class="model-tile-name mt-2">{{ isZh ? model.name_zh : model.name }}</p>
              </button>
            </div>

            <!-- Custom model upload zone (when user picked the upload tile) -->
            <div v-if="!isDemoUser && selectedModel === 'custom'" class="mt-5 space-y-2">
              <div class="flex justify-between items-center mb-1">
                <span class="text-sm font-medium text-dark-50">{{ L('自定義模特', 'Custom Model', 'カスタムモデル', '커스텀 모델', 'Modelo personalizado') }}</span>
                <button @click="selectedModel = 'avery'; modelImage = undefined" class="text-xs text-dark-300 hover:text-dark-50">
                  {{ L('取消', 'Cancel', 'キャンセル', '취소', 'Cancelar') }}
                </button>
              </div>
              <ImageUploader
                tool-type="try_on"
                v-model="modelImage"
                :label="L('上傳全身模特照片', 'Upload full-body model photo', '全身モデル写真をアップロード', '전신 모델 사진 업로드', 'Sube foto de cuerpo entero')"
                height="h-48"
              />
            </div>

            <!-- Style scene templates (subscribers) -->
            <div v-if="!isDemoUser && styleTemplates.length > 0" class="mt-6">
              <div class="flex items-center justify-between mb-3">
                <h4 class="text-sm font-semibold text-dark-200">
                  {{ L('拍攝場景模版', 'Scene Templates', 'シーンテンプレート', '씬 템플릿', 'Plantillas de escena') }}
                </h4>
                <button
                  v-if="selectedTemplateId"
                  @click="selectedTemplateId = null"
                  class="text-xs text-primary-400 hover:text-primary-300"
                >
                  {{ L('清除', 'Clear', 'クリア', '제거', 'Limpiar') }}
                </button>
              </div>
              <div class="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-2">
                <button
                  v-for="tmpl in styleTemplates"
                  :key="tmpl.id"
                  @click="selectedTemplateId = selectedTemplateId === tmpl.id ? null : tmpl.id"
                  class="relative rounded-xl border-2 p-2 transition-all text-center"
                  :class="selectedTemplateId === tmpl.id ? 'border-primary-500 bg-primary-500/10' : 'border-transparent hover:border-dark-500'"
                  style="background: #1a1a2e;"
                >
                  <img
                    v-if="tmpl.preview_image_url"
                    :src="tmpl.preview_image_url"
                    :alt="isZh ? tmpl.name_zh : tmpl.name_en"
                    class="w-full h-16 object-cover rounded-lg mb-1"
                  />
                  <div v-else class="w-full h-16 rounded-lg mb-1 flex items-center justify-center" style="background: #141420;">
                    <span class="text-xl">🎨</span>
                  </div>
                  <p class="text-[10px] font-medium text-dark-50 truncate">
                    {{ isZh ? tmpl.name_zh : tmpl.name_en }}
                  </p>
                </button>
              </div>
            </div>
          </section>

          <!-- Result -->
          <section v-if="resultImage || demoEmptyState" class="card">
            <h3 class="text-base font-semibold text-dark-50 mb-4">
              {{ L('試穿結果', 'Try-On Result', '試着結果', '시착 결과', 'Resultado de la prueba') }}
            </h3>
            <div v-if="resultImage" class="space-y-3">
              <img :src="resultImage" alt="Result" class="w-full max-w-md mx-auto rounded-xl" />
              <div class="text-center text-xs text-dark-400">vidgo.ai</div>
              <div class="flex gap-2 max-w-md mx-auto">
                <button
                  v-if="!isDemoUser"
                  @click="downloadAsset(resultImage!, 'vidgo_tryon_result.png')"
                  class="btn-primary flex-1 text-center py-2"
                >
                  {{ t('common.download') }}
                </button>
                <RouterLink v-else to="/pricing" class="btn-primary w-full text-center block">
                  {{ L('訂閱以獲得完整功能', 'Subscribe for Full Access', 'サブスクで全機能を解禁', '구독으로 전체 액세스', 'Suscríbete para acceso completo') }}
                </RouterLink>
              </div>
            </div>
            <div v-else-if="demoEmptyState" class="h-48 flex flex-col items-center justify-center rounded-xl text-center px-6 gap-3" style="background: #141420; border: 1px solid rgba(255,255,255,0.08);">
              <span class="text-2xl">🔒</span>
              <p class="text-sm text-dark-200">
                {{ L('此範例尚未預生成結果', 'No pre-generated result for this example yet', 'この例はまだ事前生成されていません', '이 예시는 아직 사전 생성되지 않았습니다', 'Aún no hay resultado pregenerado') }}
              </p>
              <RouterLink to="/pricing" class="btn-primary text-sm px-4 py-2">
                {{ L('訂閱以使用完整 AI 功能', 'Subscribe to use the real AI', 'サブスクで実AI機能を解禁', '구독으로 실제 AI 사용', 'Suscríbete para usar la IA real') }}
              </RouterLink>
            </div>
          </section>
        </main>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 12px;
  background: #0f0f17;
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.settings-card-thumb {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: #1a1a2e;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}
.settings-card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.settings-card-label {
  font-size: 10px;
  color: #6b6b8a;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  line-height: 1;
  margin-bottom: 2px;
}
.settings-card-value {
  font-size: 13px;
  color: #f5f5fa;
  font-weight: 600;
  line-height: 1.1;
}

.settings-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 2px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.settings-row:last-child { border-bottom: none; }
.settings-row-label {
  font-size: 13px;
  color: #b4b4cf;
}
.settings-row-value {
  font-size: 13px;
  color: #f5f5fa;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.pro-pill {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(124, 58, 237, 0.18);
  color: #c4b5fd;
}

.settings-card--clickable {
  cursor: pointer;
  transition: border-color 0.15s ease;
}
.settings-card--clickable:hover { border-color: rgba(124, 58, 237, 0.4); }

.popover-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  left: 0;
  z-index: 30;
  background: #1a1a2e;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 6px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.popover-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 13px;
  color: #b4b4cf;
  text-align: left;
  width: 100%;
  transition: background 0.12s ease, color 0.12s ease;
}
.popover-item:hover { background: rgba(255, 255, 255, 0.04); color: #f5f5fa; }
.popover-item--active {
  background: rgba(124, 58, 237, 0.18);
  color: #f5f5fa;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  cursor: pointer;
  transition: background 0.18s ease;
  flex-shrink: 0;
}
.toggle-switch-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 999px;
  background: #f5f5fa;
  transition: transform 0.18s ease;
}
.toggle-switch--on { background: #7c3aed; }
.toggle-switch--on .toggle-switch-thumb { transform: translateX(16px); }
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}

.model-tile {
  padding: 8px;
  border-radius: 12px;
  border: 2px solid rgba(255, 255, 255, 0.06);
  background: #141420;
  transition: border-color 0.18s ease, transform 0.18s ease;
  text-align: center;
}
.model-tile:hover { transform: translateY(-1px); }
.model-tile--active {
  border-color: #7c3aed;
  box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.18);
}
.model-tile-name {
  font-size: 12px;
  color: #b4b4cf;
  font-weight: 500;
}
.model-tile--active .model-tile-name { color: #f5f5fa; }
</style>
