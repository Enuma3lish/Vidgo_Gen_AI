<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { demoApi, effectsApi } from '@/api'
import type { Style } from '@/api'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'

const { locale, t } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const isZh = computed(() => locale.value.startsWith('zh'))

const {
  isDemoUser,
  canUseCustomInputs,
  loadDemoTemplates,
  demoTemplates,
  tryPrompts,
  dbEmpty
} = useDemoMode()

// Tab state
const activeTab = ref<'styles' | 'transform'>('styles')

const uploadedImage = ref<string | undefined>(undefined)
const resultImage = ref<string | null>(null)
const isProcessing = ref(false)

const styles = ref<Style[]>([])
const selectedStyle = ref<string>('anime')

// AI Transform state
const transformPrompt = ref('')
const transformStrength = ref(0.75)

const defaultStyles: Style[] = [
  { id: 'anime', name: 'Anime', name_zh: '動漫風格', preview_url: 'https://images.unsplash.com/photo-1578632767115-351597cf2477?w=400&h=300&fit=crop', category: 'artistic' },
  { id: 'ghibli', name: 'Ghibli', name_zh: '吉卜力風格', preview_url: 'https://images.unsplash.com/photo-1533628635777-112b2239b1c7?w=400&h=300&fit=crop', category: 'artistic' },
  { id: 'cartoon', name: 'Cartoon', name_zh: '卡通風格', preview_url: 'https://images.unsplash.com/photo-1526498460520-4c246339dccb?w=400&h=300&fit=crop', category: 'artistic' },
  { id: 'oil_painting', name: 'Oil Painting', name_zh: '油畫風格', preview_url: 'https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?w=400&h=300&fit=crop', category: 'artistic' },
  { id: 'watercolor', name: 'Watercolor', name_zh: '水彩風格', preview_url: 'https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?w=400&h=300&fit=crop', category: 'artistic' }
]

interface DemoExample {
  id: string
  input: string
  result?: string | null
  topic?: string
  prompt?: string
  promptZh?: string
}

const selectedDemoIndex = ref(0)
const isLoadingDemoImages = ref(true)

// Demo images from database only (no hardcoded fallbacks)
const demoImages = computed<DemoExample[]>(() => {
  return demoTemplates.value
    .filter(t => t.input_image_url)
    .map(t => ({
      id: t.id,
      input: t.input_image_url!,
      result: t.result_watermarked_url || t.result_image_url,
      topic: t.topic,
      prompt: t.prompt,
      promptZh: t.prompt_zh
    }))
})

function selectDemoExample(index: number) {
  selectedDemoIndex.value = index
  const example = demoImages.value[index]
  if (example) {
    uploadedImage.value = example.input
    resultImage.value = null
    if (example.topic) {
      selectedStyle.value = example.topic
    }
  }
}

async function loadStyles() {
  try {
    const response = await effectsApi.getStyles()
    styles.value = response.length > 0 ? response : defaultStyles
  } catch (error) {
    console.error('Failed to load styles:', error)
    styles.value = defaultStyles
  }
}

function dataURItoBlob(dataURI: string): Blob {
  const byteString = atob(dataURI.split(',')[1])
  const mimeString = dataURI.split(',')[0].split(':')[1].split(';')[0]
  const ab = new ArrayBuffer(byteString.length)
  const ia = new Uint8Array(ab)
  for (let i = 0; i < byteString.length; i++) {
    ia[i] = byteString.charCodeAt(i)
  }
  return new Blob([ab], { type: mimeString })
}

async function applyStyle() {
  if (!uploadedImage.value) return

  isProcessing.value = true
  try {
    if (isDemoUser.value) {
      const selectedExample = demoImages.value[selectedDemoIndex.value]
      if (selectedExample?.result) {
        resultImage.value = selectedExample.result
        uiStore.showSuccess(isZh.value ? '處理成功（示範）' : 'Processed successfully (Demo)')
        return
      }

      const matchingTemplate = demoTemplates.value.find(t => t.id === selectedExample?.id)
      if (matchingTemplate?.result_watermarked_url || matchingTemplate?.result_image_url) {
        resultImage.value = matchingTemplate.result_watermarked_url || matchingTemplate.result_image_url || null
        uiStore.showSuccess(isZh.value ? '處理成功（示範）' : 'Processed successfully (Demo)')
        return
      }

      uiStore.showInfo(isZh.value ? '此圖片尚未生成結果，請訂閱以使用完整功能' : 'This image is not pre-generated. Subscribe for full features.')
      return
    }

    if (!canUseCustomInputs.value) {
      uiStore.showError(isZh.value ? '請訂閱以上傳自訂圖片' : 'Please subscribe to upload custom images')
      return
    }

    const uploadResult = await demoApi.uploadImage(
      dataURItoBlob(uploadedImage.value) as File
    )

    const response = await effectsApi.applyStyle({
      image_url: uploadResult.url,
      style_id: selectedStyle.value,
      strength: 0.8
    })

    if (response.success && response.result_url) {
      resultImage.value = response.result_url
      creditsStore.deductCredits(response.credits_used)
      uiStore.showSuccess(isZh.value ? '處理成功' : 'Processed successfully')
    } else {
      uiStore.showError(isZh.value ? '處理失敗' : 'Processing failed')
    }
  } catch (error) {
    console.error('Effect generation failed:', error)
    uiStore.showError(isZh.value ? '處理過程中發生錯誤' : 'An error occurred while processing')
  } finally {
    isProcessing.value = false
  }
}

async function applyTransform() {
  if (!uploadedImage.value || !transformPrompt.value.trim()) return

  if (isDemoUser.value) {
    uiStore.showInfo(isZh.value ? '請訂閱以使用 AI 自由變換功能' : 'Subscribe to use AI Transform')
    return
  }

  if (!canUseCustomInputs.value) {
    uiStore.showError(isZh.value ? '請訂閱以上傳自訂圖片' : 'Please subscribe to upload custom images')
    return
  }

  isProcessing.value = true
  try {
    const uploadResult = await demoApi.uploadImage(
      dataURItoBlob(uploadedImage.value) as File
    )

    const response = await effectsApi.imageTransform({
      image_url: uploadResult.url,
      prompt: transformPrompt.value,
      strength: transformStrength.value
    })

    if (response.success && response.result_url) {
      resultImage.value = response.result_url
      creditsStore.deductCredits(response.credits_used)
      uiStore.showSuccess(isZh.value ? '變換成功' : 'Transform applied successfully')
    } else {
      uiStore.showError(isZh.value ? '變換失敗' : 'Transform failed')
    }
  } catch (error: any) {
    console.error('Image transform failed:', error)
    const detail = error.response?.data?.detail
    if (detail?.error === 'insufficient_credits') {
      uiStore.showError(isZh.value ? '點數不足，請儲值' : 'Insufficient credits')
    } else {
      uiStore.showError(isZh.value ? '處理過程中發生錯誤' : 'An error occurred while processing')
    }
  } finally {
    isProcessing.value = false
  }
}

function handleSubmit() {
  if (activeTab.value === 'transform') {
    applyTransform()
  } else {
    applyStyle()
  }
}

// Block demo users from AI Transform tab
watch(activeTab, (newTab) => {
  if (isDemoUser.value && newTab === 'transform') {
    uiStore.showInfo(isZh.value ? '請訂閱以使用 AI 自由變換' : 'Subscribe to use AI Transform')
    activeTab.value = 'styles'
  }
})

const strengthLabel = computed(() => {
  if (transformStrength.value < 0.3) return isZh.value ? '微調' : 'Subtle'
  if (transformStrength.value < 0.7) return isZh.value ? '中等' : 'Moderate'
  return isZh.value ? '強烈' : 'Dramatic'
})

onMounted(async () => {
  isLoadingDemoImages.value = true
  await loadDemoTemplates('effect', undefined, locale.value)
  isLoadingDemoImages.value = false
  await loadStyles()

  if (demoImages.value.length > 0) {
    selectDemoExample(0)
  }
})
</script>

<template>
  <div class="min-h-screen pt-20" style="background: #09090b; color: #f5f5fa;">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
      <div class="mb-8">
        <h1 class="text-2xl md:text-3xl font-bold text-dark-50 mb-2">
          {{ isZh ? '圖片風格轉換' : 'Image Style Effects' }}
        </h1>
        <p class="text-dark-300">
          {{ isZh ? '將照片快速轉換成不同的藝術風格，或使用 AI 自由描述變換效果。' : 'Transform photos into artistic styles or use AI to freely describe transformations.' }}
        </p>
        <div v-if="dbEmpty && tryPrompts.length > 0" class="mt-4 p-4 rounded-xl" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <p class="text-sm text-dark-200 mb-2">{{ isZh ? '可試玩提示詞（資料庫尚無預生成）' : 'Try prompts (no pre-generated results yet)' }}</p>
          <div class="flex flex-wrap gap-2">
            <span v-for="p in tryPrompts.slice(0, 5)" :key="p.id" class="px-2 py-1 rounded text-xs bg-dark-800 text-dark-200">{{ p.prompt }}</span>
          </div>
        </div>
      </div>

      <!-- Tab Switcher -->
      <div class="flex gap-2 mb-6">
        <button
          v-for="tab in [
            { id: 'styles', label: isZh ? '風格預設' : 'Style Presets' },
            { id: 'transform', label: isZh ? 'AI 自由變換' : 'AI Transform' }
          ]"
          :key="tab.id"
          @click="activeTab = tab.id as any"
          class="px-6 py-3 rounded-lg font-medium transition-all"
          :class="activeTab === tab.id
            ? 'bg-primary-500 text-dark-50'
            : 'bg-dark-800 text-dark-300 hover:text-dark-50'"
        >
          {{ tab.label }}
        </button>
        <span v-if="isDemoUser" class="self-center ml-2 text-xs text-yellow-400">
          {{ isZh ? 'AI 變換需訂閱' : 'AI Transform requires subscription' }}
        </span>
      </div>

      <div class="grid lg:grid-cols-3 gap-6">
        <!-- Input Panel -->
        <div class="card">
          <h3 class="text-lg font-semibold text-dark-50 mb-4">
            {{ isZh ? '選擇圖片' : 'Select Image' }}
          </h3>

          <div v-if="isDemoUser" class="space-y-4">
            <p class="text-xs text-dark-300">
              {{ isZh ? '示範圖片（可切換）' : 'Demo images (switch to preview)' }}
            </p>
            <div v-if="isLoadingDemoImages" class="flex justify-center py-6">
              <div class="animate-spin w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full"></div>
            </div>
            <div v-else-if="demoImages.length === 0" class="text-center py-6 text-dark-400">
              <span class="text-2xl block mb-1">🎨</span>
              <p class="text-xs">{{ isZh ? '範例圖片準備中' : 'Loading examples...' }}</p>
            </div>
            <div v-else class="grid grid-cols-2 gap-3">
              <button
                v-for="(example, idx) in demoImages"
                :key="example.id"
                class="relative rounded-xl overflow-hidden border transition-colors"
                :class="selectedDemoIndex === idx ? 'border-primary-500' : 'hover:border-dark-500'"
                @click="selectDemoExample(idx)"
              >
                <img :src="example.input" :alt="example.prompt" class="w-full h-24 object-cover" />
                <div class="absolute inset-0 bg-black/30 opacity-0 hover:opacity-100 transition-opacity"></div>
              </button>
            </div>
          </div>

          <div v-else class="space-y-4">
            <ImageUploader
              v-model="uploadedImage"
              :label="isZh ? '點擊上傳或拖放圖片' : 'Drop image here'"
            />
          </div>

          <div v-if="uploadedImage" class="mt-4">
            <img :src="uploadedImage" alt="Input" class="w-full rounded-xl" />
          </div>
        </div>

        <!-- Style Selection / Transform Controls -->
        <div class="card">
          <!-- Style Presets Mode -->
          <template v-if="activeTab === 'styles'">
            <h3 class="text-lg font-semibold text-dark-50 mb-4">
              {{ isZh ? '選擇風格' : 'Choose Style' }}
            </h3>

            <div class="grid grid-cols-2 gap-3">
              <button
                v-for="style in styles"
                :key="style.id"
                @click="selectedStyle = style.id"
                class="rounded-xl border-2 overflow-hidden text-left transition-all"
                :class="selectedStyle === style.id ? 'border-primary-500 bg-primary-500/10' : 'hover:border-dark-500'"
              >
                <img :src="style.preview_url" :alt="style.name" class="w-full h-20 object-cover" />
                <div class="p-2">
                  <p class="text-xs text-dark-50 font-medium">
                    {{ isZh ? style.name_zh : style.name }}
                  </p>
                </div>
              </button>
            </div>
          </template>

          <!-- AI Transform Mode -->
          <template v-else>
            <h3 class="text-lg font-semibold text-dark-50 mb-4">
              {{ isZh ? 'AI 變換設定' : 'Transform Settings' }}
            </h3>

            <div class="space-y-5">
              <!-- Prompt -->
              <div>
                <label class="block text-sm font-medium text-dark-200 mb-2">
                  {{ isZh ? '描述你想要的變換效果' : 'Describe the transformation' }}
                </label>
                <textarea
                  v-model="transformPrompt"
                  rows="4"
                  class="w-full rounded-xl px-4 py-3 placeholder-gray-500 focus:outline-none focus:border-primary-500 resize-none" style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #f5f5fa;">
                  :placeholder="isZh ? '例如：轉換成水彩畫風格、添加日落氛圍、改為冬天雪景...' : 'e.g. watercolor painting style, add sunset mood, change to winter snow scene...'"
                ></textarea>
              </div>

              <!-- Strength Slider -->
              <div>
                <div class="flex justify-between items-center mb-2">
                  <label class="text-sm font-medium text-dark-200">
                    {{ isZh ? '變換強度' : 'Transform Strength' }}
                  </label>
                  <span class="text-xs text-primary-400 font-medium">
                    {{ Math.round(transformStrength * 100) }}% — {{ strengthLabel }}
                  </span>
                </div>
                <input
                  v-model.number="transformStrength"
                  type="range"
                  min="0.05"
                  max="1"
                  step="0.05"
                  class="w-full h-2 rounded-lg appearance-none cursor-pointer accent-primary-500" style="background: #1e1e32;">
                />
                <div class="flex justify-between text-xs text-dark-400 mt-1">
                  <span>{{ isZh ? '微調' : 'Subtle' }}</span>
                  <span>{{ isZh ? '強烈' : 'Dramatic' }}</span>
                </div>
              </div>

              <!-- Quick prompts -->
              <div>
                <p class="text-xs text-dark-300 mb-2">{{ isZh ? '快速選擇：' : 'Quick picks:' }}</p>
                <div class="flex flex-wrap gap-2">
                  <button
                    v-for="qp in [
                      { en: 'Watercolor painting', zh: '水彩畫風格' },
                      { en: 'Oil painting', zh: '油畫效果' },
                      { en: 'Cyberpunk neon style', zh: '賽博朋克霓虹' },
                      { en: 'Vintage film photo', zh: '復古底片風格' },
                      { en: 'Pencil sketch', zh: '鉛筆素描' },
                    ]"
                    :key="qp.en"
                    @click="transformPrompt = isZh ? qp.zh : qp.en"
                    class="px-3 py-1.5 text-xs rounded-lg hover:text-dark-50 transition-colors" style="background: #1e1e32; color: #9494b0;">
                  >
                    {{ isZh ? qp.zh : qp.en }}
                  </button>
                </div>
              </div>
            </div>
          </template>

          <div class="mt-6 pt-4" style="border-top: 1px solid rgba(255,255,255,0.06);">
            <button
              class="btn-primary w-full"
              :disabled="!uploadedImage || isProcessing || (activeTab === 'transform' && !transformPrompt.trim())"
              @click="handleSubmit"
            >
              {{ activeTab === 'transform'
                ? (isZh ? 'AI 變換' : 'Transform')
                : (isZh ? '開始轉換' : 'Apply Style') }}
            </button>
            <p class="mt-2 text-xs text-dark-400">
              {{ activeTab === 'transform'
                ? (isZh ? '使用 PiAPI Flux I2I 即時變換' : 'Real-time I2I via PiAPI Flux')
                : (isZh ? '示範模式會使用預先生成結果' : 'Demo mode uses pre-generated results') }}
            </p>
          </div>
        </div>

        <!-- Result Panel -->
        <div class="card">
          <h3 class="text-lg font-semibold text-dark-50 mb-4">
            {{ isZh ? '生成結果' : 'Result' }}
          </h3>

          <div v-if="resultImage" class="space-y-4">
            <img :src="resultImage" alt="Result" class="w-full rounded-xl" />
            <a
              v-if="!isDemoUser"
              :href="resultImage"
              download="vidgo_effect.png"
              class="btn-primary w-full text-center py-2 block"
            >
              {{ isZh ? '下載結果' : 'Download' }}
            </a>
            <RouterLink
              v-if="isDemoUser"
              to="/pricing"
              class="btn-primary w-full text-center block"
            >
              {{ isZh ? '訂閱以獲得完整功能' : 'Subscribe for Full Access' }}
            </RouterLink>
          </div>

          <div v-else class="text-sm text-dark-400">
            {{ isZh ? '生成結果將顯示於此' : 'Your result will appear here' }}
          </div>
        </div>
      </div>
    </div>

    <LoadingOverlay :show="isProcessing" :message="t('common.processing')" />
  </div>
</template>
