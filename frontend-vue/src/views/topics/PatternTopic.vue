<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import UploadZone from '@/components/tools/UploadZone.vue'
import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import CreditCost from '@/components/tools/CreditCost.vue'
import { generationApi } from '@/api/generation'
import { useLocalized } from '@/composables/useLocalized'

const { t } = useI18n()
const { getLocalizedField } = useLocalized()
const router = useRouter()

// Tools in this topic
const tools = [
  {
    key: 'patternGenerate',
    icon: '🎨',
    credits: 5,
    route: '/tools/pattern-generate'
  },
  {
    key: 'patternTransfer',
    icon: '🖼️',
    credits: 8,
    route: '/tools/pattern-transfer'
  },
  {
    key: 'patternSeamless',
    icon: '🔄',
    credits: 5,
    route: '/tools/pattern-seamless'
  }
]

// Pattern styles
const styles = [
  { key: 'seamless', icon: '🔄' },
  { key: 'floral', icon: '🌸' },
  { key: 'geometric', icon: '📐' },
  { key: 'abstract', icon: '🎭' },
  { key: 'traditional', icon: '🏮' }
]

const selectedStyle = ref('seamless')
const prompt = ref('')
const isGenerating = ref(false)
const result = ref<string | null>(null)
const examples = ref<any[]>([])

async function loadExamples() {
  try {
    const response = await generationApi.getExamples('pattern')
    examples.value = response.examples || []
  } catch (error) {
    console.error('Failed to load examples:', error)
  }
}

async function generatePattern() {
  if (!prompt.value.trim()) return

  isGenerating.value = true
  result.value = null

  try {
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
  } finally {
    isGenerating.value = false
  }
}

onMounted(() => {
  loadExamples()
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
            @click="router.push(tool.route)"
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
            <p class="text-gray-400">
              {{ t(`tools.${tool.key}.desc`) }}
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- Quick Generate Section -->
    <section class="py-16 bg-dark-800/50">
      <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 class="section-title text-center mb-8">{{ t('sections.quickGenerate') }}</h2>

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

        <!-- Prompt Input -->
        <div class="mb-6">
          <label class="block text-sm text-gray-400 mb-2">{{ t('common.enterPrompt') }}</label>
          <div class="flex gap-4">
            <input
              v-model="prompt"
              type="text"
              :placeholder="t('tools.patternGenerate.desc')"
              class="flex-1 bg-dark-700 border border-dark-600 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-primary-500"
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
          <div class="mt-4 flex justify-end gap-4">
            <button class="btn-secondary">
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
        <RouterLink to="/auth/register" class="btn-primary text-lg px-10 py-4">
          {{ t('sections.startFree') }}
        </RouterLink>
      </div>
    </section>
  </div>
</template>
