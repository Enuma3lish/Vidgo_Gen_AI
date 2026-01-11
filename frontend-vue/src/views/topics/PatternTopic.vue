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
  demoTemplates
} = useDemoMode()

// Example prompts for each tool
const toolExamplePrompts = {
  patternGenerate: [
    { en: 'Elegant rose floral pattern with gold and navy colors', zh: '優雅的玫瑰花卉圖案，金色與深藍色配色' },
    { en: 'Modern geometric pattern with triangles', zh: '現代幾何圖案搭配三角形' },
    { en: 'Japanese wave pattern in navy and white', zh: '日式波浪紋樣，深藍與白色' },
    { en: 'Tropical palm leaves seamless pattern', zh: '熱帶棕櫚葉無縫圖案' },
    { en: 'Art deco golden lines pattern', zh: '裝飾藝術風格金線圖案' },
    { en: 'Watercolor cherry blossom pattern', zh: '水彩櫻花圖案' }
  ],
  patternTransfer: [
    { en: 'Apply marble texture to this pattern', zh: '將大理石紋理應用到此圖案' },
    { en: 'Convert to embroidery style', zh: '轉換為刺繡風格' },
    { en: 'Make it look like watercolor painting', zh: '使其看起來像水彩畫' },
    { en: 'Add metallic gold finish', zh: '添加金屬金色效果' }
  ],
  patternSeamless: [
    { en: 'Create seamless tile from this pattern', zh: '從此圖案創建無縫磁磚' },
    { en: 'Make edges blend perfectly', zh: '使邊緣完美融合' },
    { en: 'Generate repeatable wallpaper pattern', zh: '生成可重複的壁紙圖案' },
    { en: 'Create fabric-ready seamless design', zh: '創建織物可用的無縫設計' }
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
    // For demo users with selected template, use cached result
    if (isDemoUser.value && selectedDemoPromptId.value) {
      const template = demoTemplates.value.find(t => t.id === selectedDemoPromptId.value)
      if (template?.result_watermarked_url || template?.result_image_url) {
        result.value = template.result_watermarked_url || template.result_image_url || null
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }
    }

    // For demo users without cached result
    if (isDemoUser.value) {
      // Find any cached result
      const anyTemplate = demoTemplates.value.find(t =>
        t.group === 'pattern_generate' &&
        (t.result_watermarked_url || t.result_image_url)
      )

      if (anyTemplate) {
        result.value = anyTemplate.result_watermarked_url || anyTemplate.result_image_url || null
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
      } else {
        uiStore.showInfo(isZh.value ? '訂閱後可使用完整功能' : 'Subscribe to use full features')
      }
      return
    }

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
  <div class="min-h-screen pt-20">
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
    <section id="quick-generate" class="py-16 bg-dark-800/50">
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
