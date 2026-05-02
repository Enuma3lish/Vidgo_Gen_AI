<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'


import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import CreditCost from '@/components/tools/CreditCost.vue'
import { generationApi } from '@/api/generation'
import { useLocalized, useDemoMode } from '@/composables'
import { useUIStore } from '@/stores'

const { t, locale } = useI18n()
const { getLocalizedField } = useLocalized()
const uiStore = useUIStore()
const isZh = computed(() => locale.value.startsWith('zh'))

// Demo mode
const {
  isDemoUser,
  loadDemoTemplates,
  demoTemplates,
  resolveDemoTemplateResultUrl
} = useDemoMode()

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

function scrollToQuickGenerate() {
  const el = document.getElementById('quick-generate')
  if (el) {
    el.scrollIntoView({ behavior: 'smooth' })
  }
}

// Current tool's example prompts
const currentToolExamples = computed(() => {
  const tool = tools.value.find(t => t.key === selectedTool.value)
  return tool?.examples || []
})

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

const selectedStyle = ref('seamless')
const prompt = ref('')
const isGenerating = ref(false)
const result = ref<string | null>(null)
const examples = ref<any[]>([])
const selectedDemoPromptId = ref<string | null>(null)





// Fallback examples if API returns empty
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

async function loadExamples() {
  try {
    const response = await generationApi.getExamples('pattern')
    examples.value = response.examples?.length > 0 ? response.examples : fallbackExamples
  } catch (error) {
    console.error('Failed to load examples:', error)
    examples.value = fallbackExamples
  }
}

function useExamplePrompt(example: { en: string; zh: string }) {
  prompt.value = isZh.value ? example.zh : example.en
  selectedDemoPromptId.value = null
}

async function generatePattern() {
  if (!prompt.value.trim()) {
    uiStore.showError(isZh.value ? '請輸入或選擇提示詞' : 'Please enter or select a prompt')
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
          uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
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
          uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
          return
        }
      }

      uiStore.showInfo(isZh.value ? '此提示詞尚未生成，請訂閱以使用完整功能' : 'This prompt is not pre-generated. Subscribe for full features.')
      return
    }

    // For subscribed users, call the API
    const response = await generationApi.generatePattern({
      prompt: prompt.value,
      style: selectedStyle.value,
      width: 1024,
      height: 1024
    })

    if (response.success && response.result_url) {
      result.value = response.result_url
    }
  } catch (error) {
    console.error('Generation failed:', error)
    uiStore.showError(isZh.value ? '生成失敗' : 'Generation failed')
  } finally {
    isGenerating.value = false
  }
}

onMounted(() => {
  loadExamples()
  loadDemoTemplates('pattern_generate')
})
</script>

<template>
  <div class="commerce-topic-page min-h-screen pt-20" style="background: #f8fafc;">
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
              {{ isZh ? '訂閱以解鎖更多功能' : 'Subscribe to unlock more features' }}
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
              <p class="text-xs text-gray-500 mb-1">{{ isZh ? '範例提示詞:' : 'Example prompts:' }}</p>
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

        <!-- Example Prompts (Always visible) -->
        <div class="mb-6">
          <label class="block text-sm text-gray-400 mb-3">
            {{ isZh ? '選擇範例提示詞' : 'Select Example Prompt' }}
          </label>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="(ex, idx) in currentToolExamples"
              :key="idx"
              @click="useExamplePrompt(ex)"
              class="px-3 py-2 rounded-lg text-sm transition-all"
              :class="prompt === (isZh ? ex.zh : ex.en)
                ? 'bg-primary-500 text-white'
                : 'bg-dark-700 text-gray-400 hover:bg-dark-600 hover:text-white'"
            >
              {{ (isZh ? ex.zh : ex.en).slice(0, 25) }}{{ (isZh ? ex.zh : ex.en).length > 25 ? '...' : '' }}
            </button>
          </div>
        </div>

        <!-- Prompt Input -->
        <div class="mb-6">
          <label class="block text-sm text-gray-400 mb-2">{{ t('common.enterPrompt') }}</label>

          <!-- Demo user notice -->
          <div v-if="isDemoUser" class="mb-2 p-2 bg-primary-500/10 border border-primary-500/20 rounded-lg">
            <p class="text-xs text-primary-400">
              {{ isZh ? '請從上方選擇範例提示詞，或訂閱以自訂提示詞' : 'Select from example prompts above, or subscribe to use custom prompts' }}
            </p>
          </div>

          <div class="flex gap-4">
            <input
              v-model="prompt"
              type="text"
              :disabled="isDemoUser && !prompt"
              :placeholder="t('tools.patternGenerate.desc')"
              class="flex-1 bg-dark-700 border border-dark-600 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 disabled:opacity-50"
              :class="isDemoUser ? 'cursor-default' : ''"
              :readonly="isDemoUser"
            />
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
            {{ isZh ? '示範結果帶有浮水印' : 'Demo result has watermark' }}
          </div>

          <div class="mt-4 flex justify-end gap-4">
            <RouterLink
              v-if="isDemoUser"
              to="/pricing"
              class="btn-primary"
            >
              {{ isZh ? '訂閱以下載' : 'Subscribe to Download' }}
            </RouterLink>
            <button v-else class="btn-secondary">
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
            v-for="example in examples"
            :key="example.id"
            class="card overflow-hidden"
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
              <img :src="example.after" :alt="getLocalizedField(example, 'title')" class="w-full" />
            </div>

            <!-- Prompt -->
            <p v-if="example.prompt" class="mt-3 text-sm text-gray-500 italic">
              "{{ getLocalizedField(example, 'prompt') }}"
            </p>
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
          {{ isZh ? '立即訂閱' : 'Subscribe Now' }}
        </RouterLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
.commerce-topic-page {
  color: #0f172a;
}

.commerce-topic-page section {
  background: #f8fafc !important;
}

.commerce-topic-page section:nth-of-type(even) {
  background: #ffffff !important;
}

.commerce-topic-page :deep(.section-title),
.commerce-topic-page :deep(.text-dark-50),
.commerce-topic-page :deep(h1.text-white),
.commerce-topic-page :deep(h2.text-white),
.commerce-topic-page :deep(h3.text-white),
.commerce-topic-page :deep(h4.text-white) {
  color: #0f172a !important;
}

.commerce-topic-page :deep(.text-gray-400),
.commerce-topic-page :deep(.text-gray-500),
.commerce-topic-page :deep(.text-dark-300),
.commerce-topic-page :deep(.text-dark-400) {
  color: #64748b !important;
}

.commerce-topic-page :deep(.card),
.commerce-topic-page :deep(.card-gradient) {
  background: #ffffff !important;
  border: 1px solid rgba(15, 23, 42, 0.08) !important;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
  border-radius: 16px;
}

.commerce-topic-page :deep(.bg-dark-700),
.commerce-topic-page :deep(.bg-dark-600) {
  background: #f1f5f9 !important;
  border-color: rgba(15, 23, 42, 0.1) !important;
}

.commerce-topic-page input {
  background: #ffffff !important;
  color: #0f172a !important;
  border-color: rgba(15, 23, 42, 0.14) !important;
}

.commerce-topic-page input::placeholder {
  color: #94a3b8;
}
</style>
