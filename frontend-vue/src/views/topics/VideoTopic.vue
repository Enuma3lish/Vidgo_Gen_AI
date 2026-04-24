<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import UploadZone from '@/components/tools/UploadZone.vue'

import CreditCost from '@/components/tools/CreditCost.vue'
import { generationApi } from '@/api/generation'
import { useLocalized, useDemoMode } from '@/composables'
import { useUIStore } from '@/stores'

const { t, locale } = useI18n()
const isZh = computed(() => locale.value.startsWith('zh'))
const { getLocalizedField } = useLocalized()
const router = useRouter()
const uiStore = useUIStore()

// Demo mode
const {
  isDemoUser,
  canUseCustomInputs,
  loadDemoTemplates,
  demoTemplates,
  isLoadingTemplates,
  resolveDemoTemplateResultUrl
} = useDemoMode()

// Tools in this topic
const tools = [
  {
    key: 'imageToVideo',
    icon: '🎬',
    credits: 25,
    route: '/tools/image-to-video'
  }
]

// Video styles
const videoStyles = ref<any[]>([])
const selectedStyle = ref('anime_v5')
const uploadedImage = ref<string | null>(null)
const isProcessing = ref(false)
const result = ref<string | null>(null)
const examples = ref<any[]>([])

// Default fallback styles with preview URLs
const defaultStyles = [
  { id: 'anime', name: 'Anime Style', name_zh: '動漫風格', preview_url: 'https://images.unsplash.com/photo-1578632767115-351597cf2477?w=400&h=300&fit=crop' },
  { id: 'ghibli', name: 'Ghibli Style', name_zh: '吉卜力風格', preview_url: 'https://images.unsplash.com/photo-1533628635777-112b2239b1c7?w=400&h=300&fit=crop' },
  { id: 'clay', name: 'Clay Animation', name_zh: '黏土動畫', preview_url: 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&h=300&fit=crop' },
  { id: 'watercolor', name: 'Watercolor', name_zh: '水彩風格', preview_url: 'https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?w=400&h=300&fit=crop' },
  { id: 'cyberpunk', name: 'Cyberpunk', name_zh: '賽博朋克', preview_url: 'https://images.unsplash.com/photo-1515705576963-95cad62945b6?w=400&h=300&fit=crop' }
]

// Fallback examples for video topic
const fallbackExamples = [
  {
    id: 1,
    title: '動漫風格轉換',
    title_en: 'Anime Style Transform',
    after: 'https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600&h=400&fit=crop',
    style: 'anime'
  },
  {
    id: 2,
    title: '水彩藝術效果',
    title_en: 'Watercolor Art Effect',
    after: 'https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?w=600&h=400&fit=crop',
    style: 'watercolor'
  },
  {
    id: 3,
    title: '賽博朋克風格',
    title_en: 'Cyberpunk Style',
    after: 'https://images.unsplash.com/photo-1515705576963-95cad62945b6?w=600&h=400&fit=crop',
    style: 'cyberpunk'
  }
]

async function loadStyles() {
  try {
    const response = await generationApi.getVideoStyles()
    // API returns array directly
    const styles = Array.isArray(response) ? response : ((response as any).styles || [])
    // Ensure all styles have preview_url
    videoStyles.value = styles.length > 0 ? styles.map((s: any) => ({
      ...s,
      preview_url: s.preview_url || `https://images.unsplash.com/photo-1578632767115-351597cf2477?w=400&h=300&fit=crop`
    })) : defaultStyles
  } catch (error) {
    console.error('Failed to load styles:', error)
    videoStyles.value = defaultStyles
  }
}

async function loadExamples() {
  try {
    const response = await generationApi.getExamples('video')
    examples.value = response.examples?.length > 0 ? response.examples : fallbackExamples
  } catch (error) {
    console.error('Failed to load examples:', error)
    examples.value = fallbackExamples
  }
}

// Demo images for demo users
const selectedDemoImageId = ref<string | null>(null)

const demoImages = computed(() => {
  return demoTemplates.value
    .filter(t => t.input_image_url && (t.result_video_url || t.result_watermarked_url))
    .map(t => ({
      id: t.id,
      name: isZh.value ? (t.prompt_zh || t.prompt) : t.prompt,
      preview: t.input_image_url,
      watermarked_result: t.result_watermarked_url || t.result_video_url
    }))
})

function selectDemoImage(item: { id: string; preview?: string }) {
  selectedDemoImageId.value = item.id
  uploadedImage.value = item.preview || null
  result.value = null
}

function handleImageSelect(files: File[]) {
  if (!canUseCustomInputs.value) {
    uiStore.showError(isZh.value ? '請訂閱以上傳自訂圖片' : 'Please subscribe to upload custom images')
    return
  }

  if (files.length > 0) {
    const reader = new FileReader()
    reader.onload = (e) => {
      uploadedImage.value = e.target?.result as string
      selectedDemoImageId.value = null
    }
    reader.readAsDataURL(files[0])
  }
}

async function generateVideo() {
  if (!uploadedImage.value) return

  isProcessing.value = true
  result.value = null

  try {
    // For demo users, resolve the selected preset through backend lookup
    if (isDemoUser.value && selectedDemoImageId.value) {
      const demoResultUrl = await resolveDemoTemplateResultUrl(selectedDemoImageId.value)
      if (demoResultUrl) {
        result.value = demoResultUrl
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }

      uiStore.showInfo(isZh.value ? '此影片範例尚未生成，請訂閱以使用完整功能' : 'This video example is not pre-generated. Subscribe for full features.')
      return
    }

    const response = await generationApi.imageToVideo({
      image_url: uploadedImage.value!,
      motion_strength: 5,
      style: selectedStyle.value
    })

    if (response.success && response.result_url) {
      result.value = response.result_url
    }
  } catch (error) {
    console.error('Video generation failed:', error)
  } finally {
    isProcessing.value = false
  }
}

onMounted(() => {
  loadStyles()
  loadExamples()
  loadDemoTemplates('short_video')
})
</script>

<template>
  <div class="min-h-screen pt-20" style="background: #09090b;">
    <!-- Hero Section -->
    <section class="py-16 bg-gradient-to-b from-green-500/10 to-transparent">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center">
          <span class="text-6xl mb-6 block">🎬</span>
          <h1 class="text-4xl md:text-5xl font-bold text-white mb-4">
            {{ t('topics.video.name') }}
          </h1>
          <p class="text-xl text-gray-400 max-w-2xl mx-auto">
            {{ t('topics.video.longDesc') }}
          </p>
        </div>
      </div>
    </section>

    <!-- Tools Section -->
    <section class="py-16">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 class="section-title text-center mb-12">{{ t('sections.availableTools') }}</h2>

        <div class="grid grid-cols-1 md:grid-cols-1 gap-6 max-w-3xl mx-auto">
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
    <section class="py-16 bg-transparent">
      <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 class="section-title text-center mb-8">{{ t('sections.quickGenerate') }}</h2>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="flex justify-center mb-6">
          <div class="inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
            <RouterLink to="/pricing" class="hover:underline">
              {{ isZh ? '訂閱以解鎖更多功能' : 'Subscribe to unlock more features' }}
            </RouterLink>
          </div>
        </div>

        <div class="flex justify-center gap-4 mb-8">
          <div class="px-6 py-3 rounded-xl font-medium bg-primary-500 text-white">
            🖼️ {{ t('topics.video.imageToVideo') }}
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <!-- Upload Section -->
          <div>
            <h3 class="text-lg font-semibold text-white mb-4">
              {{ t('common.uploadImage') }}
            </h3>

            <div>
              <!-- Demo Images for demo users -->
              <div v-if="isDemoUser || demoImages.length > 0" class="mb-4">
                <p class="text-sm text-gray-400 mb-3">
                  {{ isZh ? '預設圖片（示範）' : 'Preset Images (Demo)' }}
                </p>
                <div v-if="isLoadingTemplates" class="flex justify-center py-8">
                  <div class="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
                </div>
                <div v-else class="grid grid-cols-2 gap-2">
                  <button
                    v-for="item in demoImages"
                    :key="item.id"
                    @click="selectDemoImage(item)"
                    class="aspect-video rounded-lg overflow-hidden border-2 transition-all"
                    :class="selectedDemoImageId === item.id
                      ? 'border-primary-500'
                      : 'border-dark-600 hover:border-dark-500'"
                  >
                    <img
                      v-if="item.preview"
                      :src="item.preview"
                      :alt="item.name"
                      class="w-full h-full object-cover"
                    />
                    <div v-else class="w-full h-full bg-dark-700 flex items-center justify-center">
                      <span class="text-3xl">🎬</span>
                    </div>
                  </button>
                </div>
              </div>

              <!-- Custom Upload (Subscribed Users Only) -->
              <div v-if="canUseCustomInputs">
                <p v-if="demoImages.length > 0" class="text-sm text-gray-400 mb-3">
                  {{ isZh ? '或上傳自訂圖片' : 'Or upload custom image' }}
                </p>
                <UploadZone
                  accept="image/*"
                  @files-selected="handleImageSelect"
                />
              </div>

              <div v-if="uploadedImage" class="mt-4">
                <img :src="uploadedImage" alt="Uploaded" class="w-full rounded-xl" />
              </div>
            </div>

          </div>

          <!-- Style Selection & Actions -->
          <div>
            <h3 class="text-lg font-semibold text-white mb-4">{{ t('common.selectStyle') }}</h3>

            <!-- Style Grid -->
            <div class="grid grid-cols-2 gap-3 mb-6 max-h-64 overflow-y-auto">
              <button
                v-for="style in videoStyles"
                :key="style.id"
                @click="selectedStyle = style.id"
                class="p-3 rounded-xl text-left transition-all"
                :class="selectedStyle === style.id
                  ? 'bg-primary-500/20 border-2 border-primary-500'
                  : 'bg-dark-700 border-2 border-transparent hover:border-dark-600'"
              >
                <span class="text-white font-medium block">{{ style.name }}</span>
                <span class="text-gray-500 text-xs">{{ style.version }}</span>
              </button>
            </div>

            <!-- Generate Button -->
            <button
              @click="generateVideo"
              :disabled="!uploadedImage || isProcessing"
              class="btn-primary w-full py-4"
            >
              <span v-if="isProcessing" class="flex items-center justify-center gap-2">
                <svg class="animate-spin w-5 h-5" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {{ t('common.processing') }}
              </span>
              <span v-else class="flex items-center justify-center gap-2">
                {{ t('common.generate') }}
                <CreditCost :cost="25" />
              </span>
            </button>

            <!-- Result -->
            <div v-if="result" class="mt-6 card overflow-hidden">
              <h4 class="text-white font-semibold mb-3">{{ t('common.result') }}</h4>
              <video :src="result" controls class="w-full rounded-lg" />
              <div class="mt-4 flex justify-end gap-4">
                <button class="btn-secondary">
                  {{ t('common.download') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Style Showcase -->
    <section class="py-16">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 class="section-title text-center mb-4">{{ t('sections.popularStyles') }}</h2>
        <p class="text-center text-gray-400 mb-12">{{ t('topics.video.stylesDesc') }}</p>

        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          <div
            v-for="style in videoStyles.slice(0, 10)"
            :key="style.id"
            class="card overflow-hidden cursor-pointer hover:scale-[1.02] transition-transform"
            @click="selectedStyle = style.id"
          >
            <div class="aspect-video rounded-lg overflow-hidden mb-3">
              <img
                :src="style.preview_url"
                :alt="style.name"
                class="w-full h-full object-cover"
              />
            </div>
            <span class="text-white font-medium text-sm block text-center">{{ isZh ? (style.name_zh || style.name) : style.name }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Examples Gallery -->
    <section class="py-16 bg-transparent">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 class="section-title text-center mb-12">{{ t('examples.title') }}</h2>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="example in examples"
            :key="example.id"
            class="card overflow-hidden"
          >
            <h4 class="text-lg font-semibold text-white mb-4">{{ getLocalizedField(example, 'title') }}</h4>

            <!-- Video comparison or result -->
            <div class="rounded-xl overflow-hidden bg-dark-700 aspect-video flex items-center justify-center">
              <video
                v-if="example.after?.endsWith('.mp4')"
                :src="example.after"
                controls
                class="w-full"
              />
              <img
                v-else-if="example.after"
                :src="example.after"
                :alt="getLocalizedField(example, 'title')"
                class="w-full"
              />
              <span v-else class="text-gray-500">{{ t('common.previewComingSoon') }}</span>
            </div>

            <!-- Style badge -->
            <div v-if="example.style" class="mt-3">
              <span class="inline-block px-3 py-1 bg-primary-500/20 text-primary-400 rounded-full text-sm">
                {{ t(`styles.${example.style}`) }}
              </span>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="examples.length === 0" class="text-center py-12">
          <span class="text-6xl mb-4 block">🎬</span>
          <p class="text-gray-400">{{ t('examples.loading') }}</p>
        </div>
      </div>
    </section>

    <!-- CTA Section -->
    <section class="py-16 bg-gradient-to-b from-green-500/10 to-transparent">
      <div class="max-w-3xl mx-auto px-4 text-center">
        <h2 class="text-3xl font-bold text-white mb-6">
          {{ t('topics.video.ctaTitle') }}
        </h2>
        <p class="text-xl text-gray-400 mb-8">
          {{ t('topics.video.ctaDesc') }}
        </p>
        <RouterLink to="/auth/register" class="btn-primary text-lg px-10 py-4">
          {{ t('common.startFree') }}
        </RouterLink>
      </div>
    </section>
  </div>
</template>
