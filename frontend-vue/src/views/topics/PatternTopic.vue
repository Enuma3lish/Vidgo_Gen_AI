<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'


import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import CreditCost from '@/components/tools/CreditCost.vue'
import { generationApi } from '@/api/generation'
import { useLocalized, useDemoMode, usePromptLibrary } from '@/composables'
import { useUIStore } from '@/stores'
import { downloadAsset } from '@/utils/downloadAsset'

const { t, locale } = useI18n()
// L is the 5-language inline picker — fixes ja/ko/es fall-through (BUG-017).
const { getLocalizedField, L } = useLocalized()
const uiStore = useUIStore()
const isZh = computed(() => locale.value.startsWith('zh'))

// Demo mode
const {
  isDemoUser,
  loadDemoTemplates,
  demoTemplates,
  resolveDemoTemplateResultUrl
} = useDemoMode()

// Curated prompt library — locked dropdown for the prompt input.
const { options: patternPromptOptions, promptFor: patternPromptTextFor } = usePromptLibrary('pattern_generate')
// Locale-stable selection so EN/ZH toggle re-derives the displayed prompt.
const selectedPatternPromptId = ref('')

// Example prompts for each tool (aligned with backend PATTERN_GENERATE_MAPPING, common business use)
const toolExamplePrompts = {
  patternGenerate: [
    { en: 'Seamless premium tea packaging pattern, Alishan leaves, misty mountain lines, jade green and warm cream palette, flat vector, clean repeat, no text', zh: '高山茶包裝用無縫圖案，阿里山茶葉、薄霧山線，翡翠綠與暖奶油配色，扁平向量，乾淨可重複，不要文字' },
    { en: 'Boutique skincare pattern, white camellia petals and soft glass droplets, airy spacing, pearl white and sage green, luxury minimal repeat, no logo', zh: '保養品牌圖案，白山茶花瓣與柔和玻璃水滴，留白充足，珍珠白與鼠尾草綠，高級極簡可重複，不要 Logo' },
    { en: 'Cafe gift-wrap pattern, hand-drawn coffee beans with tiny steam doodles, warm mocha and ivory, playful but clean seamless tile', zh: '咖啡禮品包裝圖案，手繪咖啡豆與小蒸氣線稿，摩卡與象牙白，俏皮乾淨無縫平鋪' },
    { en: 'Modern bakery tissue pattern, croissant line art, sesame dots, soft butter yellow palette, balanced negative space, tileable print', zh: '烘焙品牌襯紙圖案，可頌線稿、芝麻點綴，柔和奶油黃，留白平衡，可平鋪印刷' },
    { en: 'Tech accessory retail pattern, rounded geometric modules, subtle depth, cobalt blue and graphite accents, precise seamless repeat', zh: '科技配件零售圖案，圓角幾何模組、微立體感，鈷藍與石墨灰點綴，精準無縫重複' },
    { en: 'Children product packaging pattern, soft 3D clay stars and clouds, pastel coral and sky blue, centered spacing, cheerful seamless tile', zh: '兒童商品包裝圖案，柔軟 3D 黏土星星與雲朵，粉珊瑚與天空藍，間距居中，明亮可愛無縫平鋪' }
  ],
  patternTransfer: [
    { en: 'Apply a pearl marble surface to the product, keep original shape and label readable, soft studio reflections, premium packaging look', zh: '將珍珠大理石表面套用到商品，保留原始外形與可讀標籤，柔和棚燈反射，高級包裝感' },
    { en: 'Convert the product surface to woven embroidery texture, preserve edges and proportions, visible thread detail, clean white background', zh: '將商品表面轉為刺繡織紋，保留邊緣與比例，清楚線材細節，乾淨白背景' },
    { en: 'Transfer watercolor floral artwork onto the packaging, gentle pigment bleed, brand-safe blank areas, realistic paper texture', zh: '將水彩花卉轉印到包裝上，柔和顏料暈染，保留品牌安全留白，真實紙張質感' },
    { en: 'Add metallic gold line accents to the gift box, balanced highlights, no warped text, refined seasonal campaign style', zh: '在禮盒加入金色金屬線條點綴，高光平衡，不扭曲文字，精緻節慶活動風格' }
  ],
  patternSeamless: [
    { en: 'Create a perfectly tileable 1:1 repeat for packaging and wallpaper, no visible seams, balanced margins, production-ready print', zh: '建立 1:1 完美可平鋪圖案，用於包裝與壁紙，無接縫，邊距平衡，可直接印刷' },
    { en: 'Repeatable fabric print, medium-scale motif, consistent spacing, limited four-color palette, no text or logo', zh: '可重複布料印花，中等尺寸圖形，間距一致，限制四色配色，不要文字或 Logo' },
    { en: 'Brand social backdrop pattern, subtle texture, generous negative space for product overlays, seamless and clean', zh: '品牌社群背景圖案，細緻紋理，保留足夠留白可放商品，無縫乾淨' },
    { en: 'Retail-ready seamless textile, crisp edges, realistic woven detail, stable repeat, neutral product-friendly colors', zh: '零售用無縫織品圖案，邊緣清楚，真實編織細節，穩定重複，商品友善中性色' }
  ]
}

// Tools in this topic
const tools = computed(() => [
  {
    key: 'patternGenerate',
    icon: '🎨',
    credits: 5,
    examples: toolExamplePrompts.patternGenerate,
    action: () => {
      selectedTool.value = 'patternGenerate'
      scrollToQuickGenerate()
    }
  },
  {
    key: 'patternTransfer',
    icon: '🖼️',
    credits: 8,
    examples: toolExamplePrompts.patternTransfer,
    action: () => {
      selectedTool.value = 'patternTransfer'
      scrollToQuickGenerate()
    }
  },
  {
    key: 'patternSeamless',
    icon: '🔄',
    credits: 5,
    examples: toolExamplePrompts.patternSeamless,
    action: () => {
      selectedTool.value = 'patternSeamless'
      scrollToQuickGenerate()
    }
  }
])

const selectedTool = ref('patternGenerate')
const examples = ref<any[]>([])

function scrollToQuickGenerate() {
  const el = document.getElementById('quick-generate')
  if (el) {
    el.scrollIntoView({ behavior: 'smooth' })
  }
}

// Pattern styles
const styles = [
  { key: 'seamless', icon: '🔄' },
  { key: 'floral', icon: '🌸' },
  { key: 'geometric', icon: '📐' },
  { key: 'abstract', icon: '🎭' },
  { key: 'traditional', icon: '🏮' },
  { key: '3d', icon: '🎲' },
  { key: 'interior', icon: '🏠' },
  { key: 'mockup', icon: '📦' }
]

// Map each UI style button to the prompt-library `category` band(s) it
// surfaces. The library categories are: geometric, floral, animal,
// traditional, abstract. The UI exposes 8 styles, so a few of them join
// onto the same backend category (e.g. `interior` borrows floral/botanical
// prompts; `mockup` borrows geometric clean-design prompts). `seamless`
// is the catch-all that shows the entire 40-prompt set.
const STYLE_TO_CATEGORIES: Record<string, string[] | null> = {
  seamless: null,                          // null = no filter, show all
  floral: ['floral'],
  geometric: ['geometric'],
  abstract: ['abstract', 'animal'],
  traditional: ['traditional'],
  '3d': ['geometric'],                     // closest match
  interior: ['floral'],                    // botanical wallpapers
  mockup: ['geometric'],                   // clean packaging-friendly
}

const selectedStyle = ref('seamless')
const prompt = ref('')

// 2026-05-20 revision — three-tier T2I picker, verified against live PiAPI:
//   flux     Qubico/flux1-schnell  premium / balanced default
//   qwen     Qubico/qwen-image     best for Chinese prompts (Alibaba)
//   z-image  Qubico/z-image        cheap & fast (Alibaba)
// Hunyuan / Seedance were removed — PiAPI exposes them only for video.
const selectedT2IModel = ref<'flux' | 'qwen' | 'z-image'>('flux')
const t2iModelOptions = [
  { id: 'flux' as const,    labelZh: 'Flux',          labelEn: 'Flux' },
  { id: 'qwen' as const,    labelZh: 'Qwen 通義',     labelEn: 'Qwen' },
  { id: 'z-image' as const, labelZh: 'Z-Image 極速',  labelEn: 'Z-Image' },
]

// Filter the prompt-library dropdown by the currently-selected style band.
const filteredPromptOptions = computed(() => {
  const cats = STYLE_TO_CATEGORIES[selectedStyle.value]
  const all = patternPromptOptions.value
  if (!cats || cats.length === 0) return all
  const set = new Set(cats)
  const matches = all.filter((o: any) => o.category && set.has(o.category))
  // Fall back to the full list if the band somehow has no entries — never
  // leave the user with an empty dropdown.
  return matches.length > 0 ? matches : all
})

// When the user changes style, drop the now-invalid prompt selection.
watch(selectedStyle, () => {
  if (selectedPatternPromptId.value) {
    const stillValid = filteredPromptOptions.value.some(
      (o: any) => o.id === selectedPatternPromptId.value
    )
    if (!stillValid) selectedPatternPromptId.value = ''
  }
})

watch([selectedPatternPromptId, locale], ([newId, _newLocale], [oldId, _oldLocale]) => {
  prompt.value = selectedPatternPromptId.value ? patternPromptTextFor(selectedPatternPromptId.value) : ''
  // Clear stale result when the dropdown selection actually changes —
  // skip when only the locale flipped (same prompt, different language),
  // since the existing result is still valid for the new prompt text.
  if (newId !== oldId) {
    result.value = null
  }
})
const isGenerating = ref(false)
const result = ref<string | null>(null)
const selectedDemoPromptId = ref<string | null>(null)

// Filter examples by the currently-selected style. When the user clicks
// "🌸 花卉風格" we should only surface floral pattern examples, not the
// full mixed gallery (previous behavior surfaced "3D 設計" cards under
// every style choice because there was no filter).
const filteredExamples = computed(() => {
  const all = examples.value
  if (!Array.isArray(all) || all.length === 0) return []
  const sel = selectedStyle.value
  if (!sel) return all
  const matches = all.filter(ex => (ex.style || '').toLowerCase() === sel.toLowerCase())
  return matches.length > 0 ? matches : all
})





// Hardcoded Unsplash fallback — kept around for reference only. The
// runtime now uses `libraryExamples()` (40 cards from the curated prompt
// library) as the last-resort gallery, since the 6 entries below felt
// too thin to a real user.
// @ts-expect-error TS6133 — intentionally retained but not referenced.
const fallbackExamples = [
  {
    id: 1,
    title: '花卉無縫圖案',
    title_en: 'Floral Seamless Pattern',
    prompt: '優雅的玫瑰花卉圖案，金色與深藍色配色',
    prompt_en: 'Elegant rose floral pattern with gold and navy colors',
    after: 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600&h=600&fit=crop'
  },
  {
    id: 2,
    title: '幾何抽象圖案',
    title_en: 'Geometric Abstract Pattern',
    prompt: '現代幾何圖案，三角形與圓形組合',
    prompt_en: 'Modern geometric pattern with triangles and circles',
    after: 'https://images.unsplash.com/photo-1557672172-298e090bd0f1?w=600&h=600&fit=crop'
  },
  {
    id: 3,
    title: '日式傳統紋樣',
    title_en: 'Japanese Traditional Pattern',
    prompt: '和風波浪紋樣，深藍與白色',
    prompt_en: 'Japanese wave pattern in navy and white',
    after: 'https://images.unsplash.com/photo-1553356084-58ef4a67b2a7?w=600&h=600&fit=crop'
  },
  {
    id: 4,
    title: '熱帶植物圖案',
    title_en: 'Tropical Plant Pattern',
    prompt: '熱帶棕櫚葉與龜背竹圖案',
    prompt_en: 'Tropical palm leaves and monstera pattern',
    after: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=600&h=600&fit=crop'
  },
  {
    id: 5,
    title: '大理石紋理',
    title_en: 'Marble Texture',
    prompt: '優雅白色大理石紋理配金色紋路',
    prompt_en: 'Elegant white marble texture with gold veins',
    after: 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600&h=600&fit=crop'
  },
  {
    id: 6,
    title: '水彩花卉',
    title_en: 'Watercolor Floral',
    prompt: '柔和水彩風格玫瑰花卉圖案',
    prompt_en: 'Soft watercolor style rose floral pattern',
    after: 'https://images.unsplash.com/photo-1557672172-298e090bd0f1?w=600&h=600&fit=crop'
  }
]

// Build a synthetic gallery from the curated 40-prompt library when no
// pre-rendered Material rows exist. Without this, /tools/pattern-generate
// fell back to 6 hardcoded Unsplash thumbnails, which the user (rightly)
// complained looked too thin.
//
// CSS gradient placeholders are keyed off the prompt's `category` so the
// 5 bands (geometric / floral / animal / traditional / abstract) read
// visually distinct even though we don't have rendered PNGs yet.
function libraryExamples() {
  const CATEGORY_GRADIENTS: Record<string, string> = {
    geometric:   'linear-gradient(135deg, #1e293b 0%, #475569 50%, #94a3b8 100%)',
    floral:      'linear-gradient(135deg, #f9a8d4 0%, #fde68a 50%, #86efac 100%)',
    animal:      'linear-gradient(135deg, #78350f 0%, #b45309 50%, #fde68a 100%)',
    traditional: 'linear-gradient(135deg, #1e3a8a 0%, #ffffff 50%, #1e3a8a 100%)',
    abstract:    'linear-gradient(135deg, #581c87 0%, #db2777 50%, #f59e0b 100%)',
  }
  return patternPromptOptions.value.map((opt: any, i: number) => {
    const cat: string = opt.category || 'seamless'
    return {
      id: opt.id,
      presetId: opt.id,
      title: opt.label,
      title_zh: opt.label,
      prompt: opt.full,
      prompt_zh: opt.full,
      // No `after` URL → card renders a styled placeholder block. The card
      // template falls back to a category-tinted gradient div.
      after: '',
      placeholder_gradient: CATEGORY_GRADIENTS[cat] || CATEGORY_GRADIENTS['geometric'],
      tool: 'pattern_generate',
      style: cat,
      _index: i,
    }
  })
}

async function loadExamples() {
  try {
    if (demoTemplates.value.length === 0) {
      await loadDemoTemplates('pattern_generate', undefined, locale.value, 100)
    }

    const materialExamples = demoTemplates.value
      .filter(template => {
        const anyTemplate = template as any
        const resultUrl = template.result_watermarked_url || template.result_image_url || template.thumbnail_url
        const promptText = template.prompt_zh || template.prompt || ''
        const titleText = anyTemplate.title_zh || anyTemplate.title_en || ''
        return Boolean(resultUrl) && !`${promptText} ${titleText}`.includes('VidGo readiness')
      })
      .map((template, index) => {
        const anyTemplate = template as any
        const topicLabel = t(`styles.${template.topic || 'seamless'}`)
        const titleFallback = topicLabel && !topicLabel.startsWith('styles.')
          ? `${topicLabel}${L('範例', ' Example', '例', ' 예시', ' Ejemplo')}`
          : L('圖案範例', 'Pattern Example', 'パターン例', '패턴 예시', 'Ejemplo de patrón')

        return {
          id: template.id || index + 1,
          presetId: template.id,
          title: anyTemplate.title_en || titleFallback,
          title_zh: anyTemplate.title_zh || titleFallback,
          prompt: template.prompt || template.prompt_zh || '',
          prompt_zh: template.prompt_zh || template.prompt || '',
          after: template.result_watermarked_url || template.result_image_url || template.thumbnail_url,
          tool: 'pattern_generate',
          style: template.topic || anyTemplate.input_params?.style_id || 'seamless',
        }
      })

    if (materialExamples.length > 0) {
      examples.value = materialExamples
      return
    }

    // No DB rows — try the legacy /examples API once for any seeded examples.
    let apiExamples: any[] = []
    try {
      const response = await generationApi.getExamples('pattern')
      apiExamples = response.examples || []
    } catch { apiExamples = [] }

    if (apiExamples.length > 0) {
      examples.value = apiExamples
      return
    }

    // Last resort: render the full 40-prompt curated library as cards.
    // Each card carries a category-tinted gradient placeholder so the
    // visual scan-time matches the polish of the rest of the page.
    examples.value = libraryExamples()
  } catch (error) {
    console.error('Failed to load examples:', error)
    examples.value = libraryExamples()
  }
}

function useGalleryExample(example: any) {
  prompt.value = getLocalizedField(example, 'prompt') || example.prompt || ''
  selectedDemoPromptId.value = example.presetId || null
  if (example.style) selectedStyle.value = example.style
  result.value = null
  scrollToQuickGenerate()
}

async function generatePattern() {
  if (!prompt.value.trim()) {
    uiStore.showError(L('請輸入或選擇提示詞', 'Please enter or select a prompt', 'プロンプトを入力または選択してください', '프롬프트를 입력하거나 선택해 주세요', 'Introduce o selecciona un prompt'))
    return
  }

  isGenerating.value = true
  result.value = null

  try {
    // For demo users, resolve the selected preset through backend lookup
    if (isDemoUser.value) {
      await new Promise(resolve => setTimeout(resolve, 1500))

      if (selectedDemoPromptId.value) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(selectedDemoPromptId.value)
        if (demoResultUrl) {
          result.value = demoResultUrl
          uiStore.showSuccess(L('生成成功（示範）', 'Generated successfully (Demo)', '生成成功（デモ）', '생성 성공 (데모)', 'Generado correctamente (demo)'))
          return
        }
      }

      const matchingTemplate = demoTemplates.value.find(t =>
        t.prompt === prompt.value || t.prompt_zh === prompt.value
      )

      if (matchingTemplate?.id) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(matchingTemplate.id)
        if (demoResultUrl) {
          result.value = demoResultUrl
          uiStore.showSuccess(L('生成成功（示範）', 'Generated successfully (Demo)', '生成成功（デモ）', '생성 성공 (데모)', 'Generado correctamente (demo)'))
          return
        }
      }

      uiStore.showInfo(L('此提示詞尚未生成，請訂閱以使用完整功能', 'This prompt is not pre-generated. Subscribe for full features.', 'このプロンプトはまだ生成されていません。フル機能を使うにはサブスク登録してください。', '이 프롬프트는 아직 생성되지 않았습니다. 전체 기능을 사용하려면 구독해 주세요.', 'Este prompt no está pregenerado. Suscríbete para acceso completo.'))
      return
    }

    // For subscribed users, call the API
    const response = await generationApi.generatePattern({
      prompt: prompt.value,
      prompt_id: selectedPatternPromptId.value || undefined,
      locale: String(locale.value || ''),
      style: selectedStyle.value,
      width: 1024,
      height: 1024,
      // Only forward when the user actively picked something other than
      // Flux — keeps the wire payload identical to old clients.
      ...(selectedT2IModel.value !== 'flux' ? { model: selectedT2IModel.value } : {}),
    })

    if (response.success && response.result_url) {
      result.value = response.result_url
    }
  } catch (error) {
    console.error('Generation failed:', error)
    uiStore.showError(L('生成失敗', 'Generation failed', '生成に失敗', '생성 실패', 'Falló la generación'))
  } finally {
    isGenerating.value = false
  }
}

onMounted(() => {
  loadExamples()
})
</script>

<template>
  <div class="min-h-screen pt-20" style="background: #09090b;">
    <!-- Hero Section -->
    <section class="py-16 bg-gradient-to-b from-purple-500/10 to-transparent">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center">
          <span class="text-6xl mb-6 block">🎨</span>
          <h1 class="text-4xl md:text-5xl font-bold text-white mb-4">
            {{ t('topics.pattern.name') }}
          </h1>
          <p class="text-xl text-gray-400 max-w-2xl mx-auto">
            {{ t('topics.pattern.longDesc') }}
          </p>

          <!-- Subscribe Notice for Demo Users -->
          <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
            <RouterLink to="/pricing" class="hover:underline">
              {{ L('訂閱以解鎖更多功能', 'Subscribe to unlock more features', 'サブスク登録で機能を解禁', '구독으로 더 많은 기능 잠금 해제', 'Suscríbete para desbloquear más funciones') }}
            </RouterLink>
          </div>
        </div>
      </div>
    </section>

    <!-- Tools Section -->
    <section class="py-16">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 class="section-title text-center mb-12">{{ t('sections.availableTools') }}</h2>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div
            v-for="tool in tools"
            :key="tool.key"
            class="card-gradient hover:scale-[1.02] transition-transform cursor-pointer"
            :class="selectedTool === tool.key ? 'ring-2 ring-primary-500' : ''"
            @click="tool.action()"
          >
            <div class="flex items-center gap-4 mb-4">
              <span class="text-4xl">{{ tool.icon }}</span>
              <div>
                <h3 class="text-xl font-semibold text-white">
                  {{ t(`tools.${tool.key}.name`) }}
                </h3>
                <CreditCost :cost="tool.credits" />
              </div>
            </div>
            <p class="text-gray-400 mb-4">
              {{ t(`tools.${tool.key}.desc`) }}
            </p>

            <!-- Example Prompts for this tool -->
            <div class="space-y-2">
              <p class="text-xs text-gray-500 mb-1">{{ L('範例提示詞:', 'Example prompts:', '例プロンプト：', '예시 프롬프트:', 'Prompts de ejemplo:') }}</p>
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="(ex, idx) in tool.examples.slice(0, 3)"
                  :key="idx"
                  class="text-xs px-2 py-1 bg-dark-700 text-gray-400 rounded-full"
                >
                  {{ (isZh ? ex.zh : ex.en).slice(0, 15) }}...
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Quick Generate Section -->
    <section id="quick-generate" class="py-16 bg-transparent">
      <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 class="section-title text-center mb-8">{{ t('sections.quickGenerate') }}</h2>

        <!-- Tool Selection Tabs -->
        <div class="flex justify-center mb-6">
          <div class="inline-flex bg-dark-700 rounded-xl p-1">
            <button
              v-for="tool in tools"
              :key="tool.key"
              @click="selectedTool = tool.key"
              class="px-4 py-2 rounded-lg text-sm font-medium transition-all"
              :class="selectedTool === tool.key
                ? 'bg-primary-500 text-white'
                : 'text-gray-400 hover:text-white'"
            >
              {{ tool.icon }} {{ t(`tools.${tool.key}.name`) }}
            </button>
          </div>
        </div>

        <!-- Style Selection -->
        <div class="mb-8">
          <label class="block text-sm text-gray-400 mb-3">{{ t('common.selectStyle') }}</label>
          <div class="flex flex-wrap gap-3">
            <button
              v-for="style in styles"
              :key="style.key"
              @click="selectedStyle = style.key"
              class="px-4 py-2 rounded-xl flex items-center gap-2 transition-all"
              :class="selectedStyle === style.key
                ? 'bg-primary-500 text-white'
                : 'bg-dark-700 text-gray-400 hover:text-white'"
            >
              <span>{{ style.icon }}</span>
              <span>{{ t(`styles.${style.key}`) }}</span>
            </button>
          </div>
        </div>

        <!-- AI model picker (2026-05-20 tier addition). Default Flux is the
             baseline the curated prompt library is calibrated for; Seedance /
             Hunyuan let users explore alternative renderings of the same prompt. -->
        <div class="mb-6">
          <label class="block text-sm text-gray-400 mb-2">
            {{ L('AI 模型', 'AI Model', 'AIモデル', 'AI 모델', 'Modelo IA') }}
          </label>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="m in t2iModelOptions"
              :key="m.id"
              @click="selectedT2IModel = m.id; result = null"
              class="px-4 py-2 rounded-xl text-sm font-medium transition-all"
              :class="selectedT2IModel === m.id
                ? 'bg-primary-500 text-white'
                : 'bg-dark-700 text-gray-400 hover:text-white'"
            >{{ L(m.labelZh, m.labelEn, m.labelEn, m.labelEn, m.labelEn) }}</button>
          </div>
        </div>

        <!-- Prompt Selection (locked dropdown — no free-form input) -->
        <!-- The legacy "Example Prompts" pill row was removed: it submitted
             free-form text that bypassed the curated prompt library and the
             backend prompt_id validator. The curated dropdown below is now
             the only path. -->
        <div class="mb-6">
          <label class="block text-sm text-gray-400 mb-2">{{ L('選擇提示詞', 'Select a Prompt', 'プロンプトを選択', '프롬프트 선택', 'Selecciona un prompt') }}</label>

          <div class="mb-2 p-2 bg-primary-500/10 border border-primary-500/20 rounded-lg">
            <p class="text-xs text-primary-400">
              {{ L('為確保品質與安全，提示詞由系統精選提供。', 'For quality and safety, prompts are curated by the system.', '品質と安全のため、プロンプトはシステムが厳選しています。', '품질과 안전을 위해 시스템이 프롬프트를 엄선합니다.', 'Por calidad y seguridad, los prompts están seleccionados.') }}
            </p>
          </div>

          <div class="flex gap-4">
            <select
              v-model="selectedPatternPromptId"
              class="flex-1 bg-dark-700 border border-dark-600 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-primary-500"
            >
              <option value="">{{ L('— 請選擇 —', '— Select —', '— 選択 —', '— 선택 —', '— Seleccionar —') }}</option>
              <option v-for="opt in filteredPromptOptions" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
            </select>
            <button
              @click="generatePattern"
              :disabled="isGenerating || !prompt.trim()"
              class="btn-primary px-8"
            >
              <span v-if="isGenerating" class="flex items-center gap-2">
                <svg class="animate-spin w-5 h-5" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {{ t('common.processing') }}
              </span>
              <span v-else>{{ t('common.generate') }}</span>
            </button>
          </div>
        </div>

        <!-- Credit Info -->
        <div class="flex justify-center mb-8">
          <CreditCost :cost="5" :label="t('common.estimatedCost')" />
        </div>

        <!-- Result -->
        <div v-if="result" class="card overflow-hidden">
          <img :src="result" alt="Generated pattern" class="w-full rounded-lg" />

          <!-- Watermark Notice for Demo -->
          <div v-if="isDemoUser" class="mt-4 text-center text-sm text-yellow-400">
            {{ L('示範結果帶有浮水印', 'Demo result has watermark', 'デモ結果にはウォーターマークが付いています', '데모 결과에는 워터마크가 있습니다', 'El resultado demo tiene marca de agua') }}
          </div>

          <div class="mt-4 flex justify-end gap-4">
            <RouterLink
              v-if="isDemoUser"
              to="/pricing"
              class="btn-primary"
            >
              {{ L('訂閱以下載', 'Subscribe to Download', 'サブスクでダウンロード', '구독으로 다운로드', 'Suscríbete para descargar') }}
            </RouterLink>
            <button
              v-else
              class="btn-secondary"
              @click="downloadAsset(result!, 'vidgo_pattern.png')"
            >
              {{ t('common.download') }}
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- Examples Gallery -->
    <section class="py-16">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 class="section-title text-center mb-12">{{ t('examples.title') }}</h2>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="example in filteredExamples"
            :key="example.id"
            class="card overflow-hidden cursor-pointer transition-transform hover:-translate-y-1"
            role="button"
            tabindex="0"
            @click="useGalleryExample(example)"
            @keydown.enter.prevent="useGalleryExample(example)"
          >
            <h4 class="text-lg font-semibold text-white mb-4">{{ getLocalizedField(example, 'title') }}</h4>

            <!-- Before/After or Single Result -->
            <div v-if="example.before && example.after" class="rounded-xl overflow-hidden">
              <BeforeAfterSlider
                :before-image="example.before"
                :after-image="example.after"
                :before-label="t('examples.before')"
                :after-label="t('examples.after')"
              />
            </div>
            <div v-else-if="example.after" class="rounded-xl overflow-hidden">
              <img :src="example.after" :alt="getLocalizedField(example, 'title')" class="w-full aspect-square object-cover" />
            </div>
            <!-- Library-driven cards have no rendered image; render a
                 category-tinted gradient block so the gallery still has
                 strong visual rhythm. -->
            <div
              v-else-if="(example as any).placeholder_gradient"
              class="rounded-xl overflow-hidden aspect-square flex items-center justify-center"
              :style="`background: ${(example as any).placeholder_gradient};`"
            >
              <span class="text-white/85 text-xs font-mono tracking-wider" style="text-shadow: 0 1px 8px rgba(0,0,0,0.45);">
                {{ String(example.id).toUpperCase() }}
              </span>
            </div>

            <!-- Prompt -->
            <p v-if="example.prompt" class="mt-3 text-sm text-gray-500 italic">
              "{{ getLocalizedField(example, 'prompt') }}"
            </p>

            <div class="mt-4 flex items-center justify-between gap-3">
              <span v-if="example.style" class="text-xs px-2 py-1 rounded-full bg-dark-700 text-gray-400">
                {{ t(`styles.${example.style}`) }}
              </span>
              <button
                v-if="example.presetId"
                type="button"
                class="ml-auto text-sm font-medium text-primary-500 hover:text-primary-400"
                @click.stop="useGalleryExample(example)"
              >
                {{ L('使用此範例', 'Use Example', 'この例を使用', '이 예시 사용', 'Usar ejemplo') }}
              </button>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="examples.length === 0" class="text-center py-12">
          <span class="text-6xl mb-4 block">🎨</span>
          <p class="text-gray-400">{{ t('examples.loading') }}</p>
        </div>
      </div>
    </section>

    <!-- CTA Section -->
    <section class="py-16 bg-gradient-to-b from-purple-500/10 to-transparent">
      <div class="max-w-3xl mx-auto px-4 text-center">
        <h2 class="text-3xl font-bold text-white mb-6">
          {{ t('sections.readyToStart') }}
        </h2>
        <p class="text-xl text-gray-400 mb-8">
          {{ t('sections.freeToTry') }}
        </p>
        <RouterLink to="/pricing" class="btn-primary text-lg px-10 py-4">
          {{ L('立即訂閱', 'Subscribe Now', 'いますぐサブスク', '지금 구독', 'Suscribirse ya') }}
        </RouterLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* Pattern topic page inherits the global dark theme used by other tool topics
   (ProductTopic, VideoTopic). The previous `.commerce-topic-page` light-theme
   overrides were removed so the page is consistent with the rest of the app. */
</style>
