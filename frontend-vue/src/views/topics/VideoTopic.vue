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
    key: 'imageToVideo',
    icon: '🎬',
    credits: 25,
    route: '/tools/image-to-video'
  },
  {
    key: 'videoTransform',
    icon: '🎨',
    credits: 30,
    route: '/tools/video-transform'
  },
  {
    key: 'productVideo',
    icon: '📦',
    credits: 35,
    route: '/tools/product-video'
  }
]

// Video styles
const videoStyles = ref<any[]>([])
const selectedStyle = ref('anime_v5')
const uploadedImage = ref<string | null>(null)
const uploadedVideo = ref<string | null>(null)
const isProcessing = ref(false)
const result = ref<string | null>(null)
const examples = ref<any[]>([])
const activeTab = ref<'image' | 'video'>('image')

async function loadStyles() {
  try {
    const response = await generationApi.getVideoStyles()
    videoStyles.value = response.styles || []
  } catch (error) {
    console.error('Failed to load styles:', error)
    // Fallback styles
    videoStyles.value = [
      { id: 'anime_v5', name: 'Anime Style', version: 'v5' },
      { id: 'ghibli', name: 'Ghibli Style', version: 'v5' },
      { id: 'clay', name: 'Clay Animation', version: 'v5' },
      { id: 'pixar_v5', name: 'Pixar Style', version: 'v5' },
      { id: 'watercolor', name: 'Watercolor', version: 'v4' }
    ]
  }
}

async function loadExamples() {
  try {
    const response = await generationApi.getExamples('video')
    examples.value = response.examples || []
  } catch (error) {
    console.error('Failed to load examples:', error)
  }
}

function handleImageSelect(files: File[]) {
  if (files.length > 0) {
    const reader = new FileReader()
    reader.onload = (e) => {
      uploadedImage.value = e.target?.result as string
    }
    reader.readAsDataURL(files[0])
  }
}

function handleVideoSelect(files: File[]) {
  if (files.length > 0) {
    uploadedVideo.value = URL.createObjectURL(files[0])
  }
}

async function generateVideo() {
  if (activeTab.value === 'image' && !uploadedImage.value) return
  if (activeTab.value === 'video' && !uploadedVideo.value) return

  isProcessing.value = true
  result.value = null

  try {
    if (activeTab.value === 'image') {
      const response = await generationApi.imageToVideo({
        image_url: uploadedImage.value!,
        motion_strength: 5,
        style: selectedStyle.value
      })

      if (response.success && response.result_url) {
        result.value = response.result_url
      }
    } else {
      const response = await generationApi.transformVideo({
        video_url: uploadedVideo.value!,
        style: selectedStyle.value
      })

      if (response.success && response.result_url) {
        result.value = response.result_url
      }
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
})
</script>

<template>
  <div class="min-h-screen pt-20">
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
      <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 class="section-title text-center mb-8">{{ t('sections.quickGenerate') }}</h2>

        <!-- Tab Switch -->
        <div class="flex justify-center gap-4 mb-8">
          <button
            @click="activeTab = 'image'"
            class="px-6 py-3 rounded-xl font-medium transition-all"
            :class="activeTab === 'image'
              ? 'bg-primary-500 text-white'
              : 'bg-dark-700 text-gray-400 hover:text-white'"
          >
            🖼️ {{ t('topics.video.imageToVideo') }}
          </button>
          <button
            @click="activeTab = 'video'"
            class="px-6 py-3 rounded-xl font-medium transition-all"
            :class="activeTab === 'video'
              ? 'bg-primary-500 text-white'
              : 'bg-dark-700 text-gray-400 hover:text-white'"
          >
            🎨 {{ t('topics.video.styleTransform') }}
          </button>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <!-- Upload Section -->
          <div>
            <h3 class="text-lg font-semibold text-white mb-4">
              {{ activeTab === 'image' ? t('common.uploadImage') : t('common.uploadVideo') }}
            </h3>

            <!-- Image Upload -->
            <div v-if="activeTab === 'image'">
              <UploadZone
                accept="image/*"
                @files-selected="handleImageSelect"
              />
              <div v-if="uploadedImage" class="mt-4">
                <img :src="uploadedImage" alt="Uploaded" class="w-full rounded-xl" />
              </div>
            </div>

            <!-- Video Upload -->
            <div v-else>
              <UploadZone
                accept="video/*"
                :hint="t('common.supportedVideoFormats')"
                @files-selected="handleVideoSelect"
              />
              <div v-if="uploadedVideo" class="mt-4">
                <video :src="uploadedVideo" controls class="w-full rounded-xl" />
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
              :disabled="(activeTab === 'image' && !uploadedImage) || (activeTab === 'video' && !uploadedVideo) || isProcessing"
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
                <CreditCost :cost="activeTab === 'image' ? 25 : 30" />
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
            v-for="style in ['anime', 'ghibli', 'pixar', 'clay', 'watercolor']"
            :key="style"
            class="card text-center p-4"
          >
            <div class="w-16 h-16 rounded-xl bg-gradient-to-br from-primary-500/20 to-purple-500/20 flex items-center justify-center mx-auto mb-3">
              <span class="text-2xl">
                {{ style === 'anime' ? '🎌' :
                   style === 'ghibli' ? '🏯' :
                   style === 'pixar' ? '🎪' :
                   style === 'clay' ? '🎭' : '🎨' }}
              </span>
            </div>
            <span class="text-white font-medium">{{ t(`styles.${style}`) }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Examples Gallery -->
    <section class="py-16 bg-dark-800/50">
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
