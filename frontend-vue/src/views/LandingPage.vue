<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import apiClient from '@/api/client'
import landingApi from '@/api/landing'
import type { FeatureItem } from '@/api/landing'

const { locale } = useI18n()
const router = useRouter()

const isZh = computed(() => locale.value.startsWith('zh'))

// ============================================
// SIDEBAR CATEGORIES - Inspired by douhuiai.com
// ============================================
interface Tool {
  key: string
  icon: string
  route: string
  name: string
  nameZh: string
}

interface Category {
  key: string
  icon: string
  name: string
  nameZh: string
  desc: string
  descZh: string
  color: string
  tools: Tool[]
}

const categories = ref<Category[]>([
  {
    key: 'aiImage',
    icon: '🖼️',
    name: 'AI Image',
    nameZh: 'AI 圖像創作',
    desc: 'Product scenes, styles, and smart edits',
    descZh: '產品場景、風格效果與智慧修圖',
    color: 'purple',
    tools: [
      { key: 'productScene', icon: '🏞️', route: '/tools/product-scene', name: 'Product Scene', nameZh: '產品場景' },
      { key: 'bgRemoval', icon: '✂️', route: '/tools/background-removal', name: 'Remove Background', nameZh: '智能去背' },
      { key: 'patternGen', icon: '🔲', route: '/tools/pattern-generate', name: 'Pattern Design', nameZh: '圖案設計' },
      { key: 'effects', icon: '🎨', route: '/tools/effects', name: 'Image Effects', nameZh: '圖片風格' }
    ]
  },
  {
    key: 'aiVideo',
    icon: '🎬',
    name: 'AI Video',
    nameZh: 'AI 影片創作',
    desc: 'Short videos and digital humans',
    descZh: '短影片與 AI 數位人',
    color: 'cyan',
    tools: [
      { key: 'shortVideo', icon: '📱', route: '/tools/short-video', name: 'Short Video', nameZh: '短影片生成' },
      { key: 'avatar', icon: '🎭', route: '/tools/avatar', name: 'AI Avatar', nameZh: 'AI 數位人' }
    ]
  },
  {
    key: 'ecommerce',
    icon: '🛒',
    name: 'E-commerce',
    nameZh: '電商視覺',
    desc: 'Catalog ready product assets',
    descZh: '電商商品圖與素材',
    color: 'orange',
    tools: [
      { key: 'tryOn', icon: '👗', route: '/tools/try-on', name: 'Virtual Try-On', nameZh: '虛擬試穿' },
      { key: 'productScene', icon: '🏞️', route: '/tools/product-scene', name: 'Product Photo', nameZh: '產品場景' },
      { key: 'bgRemoval', icon: '✂️', route: '/tools/background-removal', name: 'Background Remove', nameZh: '背景移除' }
    ]
  },
  {
    key: 'interior',
    icon: '🏠',
    name: 'Interior Design',
    nameZh: '空間設計',
    desc: 'Room redesign and style transfer',
    descZh: '空間重設計與風格改造',
    color: 'green',
    tools: [
      { key: 'roomRedesign', icon: '🛋️', route: '/tools/room-redesign', name: 'Room Redesign', nameZh: '空間重設計' }
    ]
  },
  {
    key: 'design',
    icon: '✨',
    name: 'Design Tools',
    nameZh: '設計工具集',
    desc: 'Patterns and artistic effects',
    descZh: '圖案生成與藝術風格',
    color: 'pink',
    tools: [
      { key: 'patternGen', icon: '🔲', route: '/tools/pattern-generate', name: 'Pattern Design', nameZh: '圖案設計' },
      { key: 'effects', icon: '🎨', route: '/tools/effects', name: 'Image Effects', nameZh: '圖片風格' }
    ]
  }
])

// Hover state for sidebar categories
const hoveredCategory = ref<string | null>(null)
const sidebarExpanded = ref(false)

function onCategoryHover(key: string) {
  hoveredCategory.value = key
  sidebarExpanded.value = true
}

function onCategoryLeave() {
  // Delay to allow moving to expanded panel
  setTimeout(() => {
    if (!sidebarExpanded.value) {
      hoveredCategory.value = null
    }
  }, 100)
}

function onExpandedPanelLeave() {
  sidebarExpanded.value = false
  hoveredCategory.value = null
}

function goToTool(route: string) {
  router.push(route)
}

// ============================================
// HERO CONTENT
// ============================================
const heroPrompt = ref('')

const promptSuggestions = computed(() => [
  {
    key: 'prompt-1',
    label: isZh.value ? '電商產品場景' : 'E-commerce product scene',
    value: isZh.value ? '為高級香水設計極簡棚拍場景' : 'Minimal studio scene for luxury perfume'
  },
  {
    key: 'prompt-2',
    label: isZh.value ? '短影片腳本' : 'Short video script',
    value: isZh.value ? '品牌新品 8 秒介紹影片' : '8-second brand intro for new product'
  },
  {
    key: 'prompt-3',
    label: isZh.value ? '空間改造' : 'Room redesign',
    value: isZh.value ? '北歐風客廳改造' : 'Nordic living room redesign'
  }
])

const quickActions = computed(() => [
  { key: 'shortVideo', label: isZh.value ? '短影片' : 'Short Video', route: '/tools/short-video' },
  { key: 'productScene', label: isZh.value ? '產品場景' : 'Product Scene', route: '/tools/product-scene' },
  { key: 'bgRemoval', label: isZh.value ? '智能去背' : 'Remove BG', route: '/tools/background-removal' },
  { key: 'roomRedesign', label: isZh.value ? '空間設計' : 'Room Design', route: '/tools/room-redesign' },
  { key: 'tryOn', label: isZh.value ? '虛擬試穿' : 'Virtual Try-On', route: '/tools/try-on' },
  { key: 'effects', label: isZh.value ? '圖片風格' : 'Image Effects', route: '/tools/effects' }
])

const landingBadges = computed(() => [
  { key: 'ecommerce', label: isZh.value ? '電商' : 'E-commerce' },
  { key: 'social', label: isZh.value ? '社群' : 'Social' },
  { key: 'brand', label: isZh.value ? '品牌' : 'Brand' },
  { key: 'app', label: isZh.value ? '應用' : 'App' },
  { key: 'promo', label: isZh.value ? '促銷' : 'Promo' },
  { key: 'service', label: isZh.value ? '服務' : 'Service' }
])

function applySuggestion(value: string) {
  heroPrompt.value = value
}

function startWithPrompt() {
  goToTool('/tools/product-scene')
}

// ============================================
// TOOL GRID
// ============================================
const toolCatalog = computed(() => [
  {
    key: 'shortVideo',
    icon: '📱',
    route: '/tools/short-video',
    name: isZh.value ? '短影片生成' : 'Short Video',
    desc: isZh.value ? '8 秒品牌與產品短片' : '8-second branded videos',
    color: 'from-purple-500 to-pink-500',
    hot: true
  },
  {
    key: 'avatar',
    icon: '🎭',
    route: '/tools/avatar',
    name: isZh.value ? 'AI 數位人' : 'AI Avatar',
    desc: isZh.value ? '數位人口播影片' : 'Digital spokesperson videos',
    color: 'from-cyan-500 to-blue-500',
    hot: true
  },
  {
    key: 'productScene',
    icon: '🏞️',
    route: '/tools/product-scene',
    name: isZh.value ? '產品場景' : 'Product Scene',
    desc: isZh.value ? '商品棚拍與情境圖' : 'Product photography scenes',
    color: 'from-orange-500 to-red-500',
    new: true
  },
  {
    key: 'bgRemoval',
    icon: '✂️',
    route: '/tools/background-removal',
    name: isZh.value ? '智能去背' : 'Remove Background',
    desc: isZh.value ? '一鍵移除背景' : 'One-click cutout',
    color: 'from-green-500 to-teal-500'
  },
  {
    key: 'roomRedesign',
    icon: '🏠',
    route: '/tools/room-redesign',
    name: isZh.value ? '空間設計' : 'Room Redesign',
    desc: isZh.value ? '室內空間改造' : 'Interior redesign',
    color: 'from-blue-500 to-indigo-500'
  },
  {
    key: 'tryOn',
    icon: '👗',
    route: '/tools/try-on',
    name: isZh.value ? '虛擬試穿' : 'Virtual Try-On',
    desc: isZh.value ? 'AI 模特試穿' : 'AI model fitting',
    color: 'from-pink-500 to-rose-500'
  },
  {
    key: 'patternGen',
    icon: '🔲',
    route: '/tools/pattern-generate',
    name: isZh.value ? '圖案設計' : 'Pattern Design',
    desc: isZh.value ? '無縫圖案生成' : 'Seamless patterns',
    color: 'from-indigo-500 to-purple-500'
  },
  {
    key: 'effects',
    icon: '🎨',
    route: '/tools/effects',
    name: isZh.value ? '圖片風格' : 'Image Effects',
    desc: isZh.value ? '藝術風格轉換' : 'Artistic style transfer',
    color: 'from-yellow-500 to-orange-500'
  }
])

// ============================================
// FEATURE HIGHLIGHTS (Landing API)
// ============================================
const featureHighlights = ref<FeatureItem[]>([])
const isLoadingFeatures = ref(false)

async function loadFeatureHighlights() {
  isLoadingFeatures.value = true
  try {
    featureHighlights.value = await landingApi.getFeatures()
  } catch (error) {
    console.error('Failed to load features:', error)
    featureHighlights.value = []
  } finally {
    isLoadingFeatures.value = false
  }
}

// ============================================
// WORKS GALLERY (產品增強 + 廣告特效 - like douhuiai)
// ============================================
interface WorkItem {
  id: string
  tool_type: string
  tool_name: string
  route: string
  title: string
  prompt: string
  thumb: string
  video_url?: string | null
  input_image_url?: string
  result_image_url?: string
  topic?: string
}

const worksGallery = ref<WorkItem[]>([])
const isLoadingWorks = ref(false)

async function loadWorksGallery() {
  isLoadingWorks.value = true
  try {
    const langCode = locale.value.startsWith('zh') ? 'zh-TW' : 'en'
    const response = await apiClient.get(`/api/v1/demo/landing/works?language=${langCode}&limit=24`)
    if (response.data.success && response.data.items?.length > 0) {
      worksGallery.value = response.data.items
    }
  } catch (error) {
    console.error('Failed to load works gallery:', error)
    worksGallery.value = []
  } finally {
    isLoadingWorks.value = false
  }
}

// ============================================
// VIDEO EXAMPLES
// ============================================
const videoExamples = ref<any[]>([])
const avatarExamples = ref<any[]>([])
const isLoadingVideos = ref(false)
const isLoadingAvatars = ref(false)
const selectedVideo = ref<any>(null)
const showVideoModal = ref(false)
const hoveredAvatar = ref<number | null>(null)

async function loadVideoExamples() {
  isLoadingVideos.value = true
  try {
    const langCode = locale.value.startsWith('zh') ? 'zh-TW' : 'en'
    const response = await apiClient.get(`/api/v1/demo/landing/examples?language=${langCode}`)
    if (response.data.success && response.data.examples?.length > 0) {
      videoExamples.value = response.data.examples
    }
    // No fallback to /api/v1/landing/examples - that endpoint returns static data
    // without video_url fields, which would produce empty video players
  } catch (error) {
    console.error('Failed to load video examples:', error)
    videoExamples.value = []
  } finally {
    isLoadingVideos.value = false
  }
}

async function loadAvatarExamples() {
  isLoadingAvatars.value = true
  try {
    const langCode = locale.value.startsWith('zh') ? 'zh-TW' : 'en'
    const response = await apiClient.get(`/api/v1/demo/presets/ai_avatar?language=${langCode}`)
    if (response.data.success && response.data.presets?.length > 0) {
      avatarExamples.value = response.data.presets.slice(0, 9)
    }
  } catch (error) {
    console.error('Failed to load avatar examples:', error)
  } finally {
    isLoadingAvatars.value = false
  }
}

function playVideo(video: any) {
  // If video has a video URL (API returns 'video' field), show modal and play
  const videoUrl = video.video || video.video_url || video.result_video_url
  if (videoUrl) {
    selectedVideo.value = { ...video, video_url: videoUrl }
    showVideoModal.value = true
  } else {
    // No video URL available, navigate to tool
    goToTool('/tools/short-video')
  }
}

function closeVideoModal() {
  showVideoModal.value = false
  selectedVideo.value = null
}

// ============================================
// INITIALIZE
// ============================================
onMounted(() => {
  loadWorksGallery()
  loadFeatureHighlights()
  loadVideoExamples()
  loadAvatarExamples()
})

watch(locale, () => {
  loadWorksGallery()
  loadVideoExamples()
  loadAvatarExamples()
})
</script>

<template>
  <div class="min-h-screen pt-14 flex">
    <!-- ============================================
         LEFT SIDEBAR - Category Navigation
         ============================================ -->
    <aside class="hidden lg:block w-16 hover:w-16 fixed left-0 top-14 bottom-0 bg-dark-800/50 border-r border-dark-700 z-40">
      <div class="py-4">
        <!-- Category Icons -->
        <div
          v-for="cat in categories"
          :key="cat.key"
          @mouseenter="onCategoryHover(cat.key)"
          @mouseleave="onCategoryLeave"
          class="relative"
        >
          <div
            class="w-full py-3 flex flex-col items-center gap-1 cursor-pointer transition-all duration-200"
            :class="[
              hoveredCategory === cat.key
                ? 'bg-primary-500/20 text-white'
                : 'text-gray-400 hover:text-white hover:bg-dark-700/50'
            ]"
          >
            <span class="text-xl">{{ cat.icon }}</span>
            <span class="text-[10px] leading-tight text-center px-1">
              {{ isZh ? cat.nameZh.slice(0, 4) : cat.name.slice(0, 6) }}
            </span>
          </div>
        </div>
      </div>

      <!-- Expanded Panel - Shows tools on hover -->
      <Transition name="slide">
        <div
          v-if="hoveredCategory"
          @mouseenter="sidebarExpanded = true"
          @mouseleave="onExpandedPanelLeave"
          class="absolute left-16 top-0 bottom-0 w-60 bg-dark-800 border-r border-dark-700 shadow-xl overflow-y-auto"
        >
          <!-- Category Header -->
          <div class="sticky top-0 bg-dark-800 border-b border-dark-700 p-4">
            <div class="flex items-center gap-2">
              <span class="text-xl">{{ categories.find(c => c.key === hoveredCategory)?.icon }}</span>
              <div>
                <span class="font-medium text-white block">
                  {{ isZh
                    ? categories.find(c => c.key === hoveredCategory)?.nameZh
                    : categories.find(c => c.key === hoveredCategory)?.name
                  }}
                </span>
                <span class="text-xs text-gray-400">
                  {{ isZh
                    ? categories.find(c => c.key === hoveredCategory)?.descZh
                    : categories.find(c => c.key === hoveredCategory)?.desc
                  }}
                </span>
              </div>
            </div>
          </div>

          <!-- Tools List -->
          <div class="p-2">
            <button
              v-for="tool in categories.find(c => c.key === hoveredCategory)?.tools"
              :key="tool.key"
              @click="goToTool(tool.route)"
              class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-dark-700 transition-colors text-left"
            >
              <span class="text-lg">{{ tool.icon }}</span>
              <span class="text-sm text-gray-300 hover:text-white">
                {{ isZh ? tool.nameZh : tool.name }}
              </span>
            </button>
          </div>
        </div>
      </Transition>
    </aside>

    <!-- ============================================
         MAIN CONTENT AREA
         ============================================ -->
    <main class="flex-1 lg:ml-16">
      <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <!-- ============================================
             HERO SECTION
             ============================================ -->
        <section class="mb-12">
          <div class="relative overflow-hidden rounded-3xl border border-dark-700 bg-gradient-to-br from-dark-800/80 via-dark-900/90 to-black/80">
            <div class="absolute -top-24 right-0 w-72 h-72 bg-primary-500/10 blur-3xl"></div>
            <div class="absolute -bottom-24 left-0 w-72 h-72 bg-cyan-500/10 blur-3xl"></div>
            <div class="relative grid lg:grid-cols-12 gap-8 p-6 md:p-10">
              <div class="lg:col-span-7">
                <p class="text-xs uppercase tracking-widest text-primary-300 mb-3">
                  {{ isZh ? '全方位 AI 視覺平台' : 'All-in-one AI Visual Studio' }}
                </p>
                <h1 class="text-3xl md:text-4xl font-bold text-white mb-4">
                  {{ isZh
                    ? '用一句話完成電商、品牌與空間設計素材'
                    : 'Create commerce, brand, and interior visuals in minutes'
                  }}
                </h1>
                <p class="text-gray-300 leading-relaxed mb-6">
                  {{ isZh
                    ? '靈感、素材、短影片與數位人一次完成。所有展示功能都對應 VidGo 已提供的 API。'
                    : 'From product scenes to short videos and digital humans, every showcase here maps to VidGo APIs you already have.'
                  }}
                </p>

                <div class="flex flex-wrap gap-3">
                  <button
                    class="btn-primary"
                    @click="goToTool('/tools/product-scene')"
                  >
                    {{ isZh ? '開始生成產品場景' : 'Start with Product Scene' }}
                  </button>
                  <button
                    class="px-5 py-2.5 rounded-xl border border-dark-600 text-gray-200 hover:text-white hover:border-primary-400 transition-colors"
                    @click="goToTool('/tools/short-video')"
                  >
                    {{ isZh ? '試做短影片' : 'Try Short Video' }}
                  </button>
                </div>

                <div class="mt-6">
                  <div class="flex items-center gap-2 text-xs text-gray-400 mb-2">
                    <span class="uppercase tracking-widest">Prompt</span>
                    <span>{{ isZh ? '快速靈感' : 'Quick ideas' }}</span>
                  </div>
                  <div class="flex flex-col sm:flex-row gap-3">
                    <input
                      v-model="heroPrompt"
                      type="text"
                      class="flex-1 bg-dark-900 border border-dark-600 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-primary-500"
                      :placeholder="isZh ? '輸入一句話描述你想要的畫面…' : 'Describe what you want to create…'"
                    />
                    <button
                      class="btn-primary px-6"
                      @click="startWithPrompt"
                    >
                      {{ isZh ? '開始創作' : 'Start' }}
                    </button>
                  </div>
                  <div class="mt-3 flex flex-wrap gap-2">
                    <button
                      v-for="suggestion in promptSuggestions"
                      :key="suggestion.key"
                      class="px-3 py-1 rounded-full text-xs border border-dark-600 text-gray-300 hover:text-white hover:border-primary-400 transition-colors"
                      @click="applySuggestion(suggestion.value)"
                    >
                      {{ suggestion.label }}
                    </button>
                  </div>
                  <div class="mt-4 flex flex-wrap gap-2">
                    <button
                      v-for="action in quickActions"
                      :key="action.key"
                      class="px-3 py-1 rounded-full text-xs bg-dark-800 text-gray-300 hover:text-white hover:bg-dark-700 transition-colors"
                      @click="goToTool(action.route)"
                    >
                      {{ action.label }}
                    </button>
                  </div>
                </div>
              </div>

              <div class="lg:col-span-5">
                <div class="grid gap-4">
                  <div class="p-5 rounded-2xl bg-dark-800/70 border border-dark-700">
                    <div class="flex items-center justify-between">
                      <h3 class="text-sm font-semibold text-white">
                        {{ isZh ? '工具庫' : 'Tool Library' }}
                      </h3>
                      <span class="text-xs text-primary-300">{{ toolCatalog.length }} {{ isZh ? '項' : 'tools' }}</span>
                    </div>
                    <div class="mt-4 grid grid-cols-2 gap-2 text-xs text-gray-300">
                      <div v-for="tool in toolCatalog.slice(0, 4)" :key="tool.key" class="flex items-center gap-2">
                        <span>{{ tool.icon }}</span>
                        <span>{{ tool.name }}</span>
                      </div>
                    </div>
                    <button
                      class="mt-4 w-full text-xs text-primary-300 hover:text-primary-200"
                      @click="goToTool('/tools/product-scene')"
                    >
                      {{ isZh ? '立即開始生成' : 'Start generating now' }}
                    </button>
                  </div>

                  <div class="p-5 rounded-2xl bg-dark-800/70 border border-dark-700">
                    <h3 class="text-sm font-semibold text-white">
                      {{ isZh ? '適用場景' : 'Use Cases' }}
                    </h3>
                    <p class="text-xs text-gray-400 mt-2">
                      {{ isZh ? '支援電商、社群、品牌、App、促銷與服務型影片素材' : 'Optimized for ecommerce, social, brand, app, promo, and service creatives.' }}
                    </p>
                    <div class="mt-4 flex flex-wrap gap-2">
                      <span
                        v-for="badge in landingBadges"
                        :key="badge.key"
                        class="px-3 py-1 rounded-full text-xs bg-dark-700 text-gray-300"
                      >
                        {{ badge.label }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- ============================================
             WORKS GALLERY - 產品增強與廣告特效 (like douhuiai)
             ============================================ -->
        <section v-if="worksGallery.length > 0" class="mb-12">
          <div class="flex items-center justify-between mb-6">
            <h2 class="text-lg font-semibold text-white flex items-center gap-2">
              <span>🎨</span>
              {{ isZh ? '產品增強與廣告特效' : 'Product Enhancement & Ad Effects' }}
            </h2>
            <span class="text-sm text-gray-400">
              {{ isZh ? '精選作品靈感' : 'Featured work inspiration' }}
            </span>
          </div>

          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <div
              v-for="work in worksGallery"
              :key="work.id"
              class="group relative aspect-square rounded-xl overflow-hidden bg-dark-700 cursor-pointer border border-dark-600 hover:border-primary-500/50 transition-all duration-300"
              @click="goToTool(work.route)"
            >
              <!-- Video item (short_video / ai_avatar) -->
              <template v-if="work.video_url">
                <!-- Video poster/thumbnail (default) -->
                <img
                  v-if="work.thumb"
                  :src="work.thumb"
                  :alt="work.title"
                  class="absolute inset-0 w-full h-full object-cover transition-opacity duration-300 group-hover:opacity-0"
                />
                <!-- Video (plays on hover) -->
                <video
                  :src="work.video_url"
                  class="absolute inset-0 w-full h-full object-cover transition-opacity duration-300"
                  :class="work.thumb ? 'opacity-0 group-hover:opacity-100' : ''"
                  muted
                  loop
                  playsinline
                  @mouseenter="($event.target as HTMLVideoElement).play()"
                  @mouseleave="($event.target as HTMLVideoElement).pause(); ($event.target as HTMLVideoElement).currentTime = 0"
                />
                <!-- Play icon overlay -->
                <div class="absolute inset-0 flex items-center justify-center pointer-events-none group-hover:opacity-0 transition-opacity duration-300">
                  <div class="w-10 h-10 bg-white/80 rounded-full flex items-center justify-center shadow-lg">
                    <svg class="w-5 h-5 text-primary-600 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z" />
                    </svg>
                  </div>
                </div>
              </template>

              <!-- Image item (product_scene, effect, background_removal) -->
              <template v-else>
                <!-- Main thumbnail (result) -->
                <img
                  :src="work.thumb"
                  :alt="work.title"
                  class="absolute inset-0 w-full h-full object-cover transition-opacity duration-300"
                  :class="{ 'group-hover:opacity-0': work.input_image_url && work.tool_type === 'effect' }"
                />
                <!-- Before image (for effects - show on hover) -->
                <img
                  v-if="work.input_image_url && work.tool_type === 'effect'"
                  :src="work.input_image_url"
                  :alt="work.title"
                  class="absolute inset-0 w-full h-full object-cover opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                />
              </template>

              <!-- Tool badge -->
              <div class="absolute top-1.5 left-1.5 px-2 py-0.5 bg-black/70 text-white text-[10px] rounded-full">
                {{ work.tool_name }}
              </div>

              <!-- Gradient overlay with prompt on hover -->
              <div class="absolute inset-0 bg-gradient-to-t from-black/90 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex flex-col justify-end p-2">
                <p class="text-white text-[10px] line-clamp-2">
                  {{ work.prompt }}
                </p>
              </div>

              <!-- Arrow hint -->
              <div class="absolute bottom-1.5 right-1.5 w-5 h-5 rounded-full bg-primary-500/90 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                </svg>
              </div>
            </div>
          </div>
        </section>

        <!-- Loading state for Works Gallery -->
        <section v-else-if="isLoadingWorks" class="mb-12">
          <div class="flex items-center justify-between mb-6">
            <h2 class="text-lg font-semibold text-white flex items-center gap-2">
              <span>🎨</span>
              {{ isZh ? '產品增強與廣告特效' : 'Product Enhancement & Ad Effects' }}
            </h2>
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <div v-for="i in 12" :key="i" class="aspect-square rounded-xl bg-dark-700/50 animate-pulse" />
          </div>
        </section>

        <!-- ============================================
             CATEGORY CARDS
             ============================================ -->
        <section class="mb-12">
          <div class="flex items-center justify-between mb-6">
            <h2 class="text-lg font-semibold text-white flex items-center gap-2">
              <span>📚</span>
              {{ isZh ? '工具分類' : 'Tool Categories' }}
            </h2>
            <span class="text-sm text-gray-400">
              {{ isZh ? '所有功能皆對應現有 API' : 'All features map to existing APIs' }}
            </span>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div
              v-for="cat in categories"
              :key="cat.key"
              class="group relative rounded-2xl border border-dark-600 bg-dark-700/40 p-5 hover:border-primary-500/40 transition-colors"
            >
              <div class="flex items-center justify-between">
                <span class="text-2xl">{{ cat.icon }}</span>
                <span class="text-xs text-gray-400">{{ cat.tools.length }} {{ isZh ? '工具' : 'tools' }}</span>
              </div>
              <h3 class="text-base font-semibold text-white mt-3">
                {{ isZh ? cat.nameZh : cat.name }}
              </h3>
              <p class="text-xs text-gray-400 mt-1">
                {{ isZh ? cat.descZh : cat.desc }}
              </p>
              <div class="mt-4 flex flex-wrap gap-2">
                <span
                  v-for="tool in cat.tools"
                  :key="tool.key"
                  class="px-2.5 py-1 rounded-full text-xs bg-dark-800 text-gray-300"
                >
                  {{ isZh ? tool.nameZh : tool.name }}
                </span>
              </div>
              <button
                class="mt-4 text-xs text-primary-300 hover:text-primary-200"
                @click="goToTool(cat.tools[0]?.route || '/')"
              >
                {{ isZh ? '立即查看' : 'Explore' }}
              </button>
            </div>
          </div>
        </section>

        <!-- ============================================
             FEATURED TOOLS GRID
             ============================================ -->
        <section class="mb-12">
          <div class="flex items-center justify-between mb-6">
            <h2 class="text-lg font-semibold text-white flex items-center gap-2">
              <span>⚡</span>
              {{ isZh ? '熱門功能' : 'Featured Tools' }}
            </h2>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            <button
              v-for="tool in toolCatalog"
              :key="tool.key"
              @click="goToTool(tool.route)"
              class="group relative bg-dark-700/50 hover:bg-dark-700 border border-dark-600 hover:border-primary-500/50 rounded-xl p-4 text-left transition-all duration-300"
            >
              <!-- Hot/New Badge -->
              <div v-if="tool.hot" class="absolute -top-2 -right-2 px-2 py-0.5 bg-red-500 text-white text-xs rounded-full">
                HOT
              </div>
              <div v-if="tool.new" class="absolute -top-2 -right-2 px-2 py-0.5 bg-green-500 text-white text-xs rounded-full">
                NEW
              </div>

              <!-- Icon -->
              <div
                class="w-12 h-12 rounded-xl flex items-center justify-center text-2xl mb-3 bg-gradient-to-br"
                :class="tool.color"
              >
                {{ tool.icon }}
              </div>

              <!-- Name -->
              <h3 class="font-medium text-white group-hover:text-primary-300 transition-colors mb-1">
                {{ tool.name }}
              </h3>

              <!-- Description -->
              <p class="text-xs text-gray-400 line-clamp-2">
                {{ tool.desc }}
              </p>

              <!-- Arrow -->
              <div class="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                <svg class="w-5 h-5 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                </svg>
              </div>
            </button>
          </div>
        </section>

        <!-- ============================================
             FEATURE HIGHLIGHTS
             ============================================ -->
        <section v-if="featureHighlights.length > 0" class="mb-12">
          <div class="flex items-center justify-between mb-6">
            <h2 class="text-lg font-semibold text-white flex items-center gap-2">
              <span>✨</span>
              {{ isZh ? '能力亮點' : 'Capability Highlights' }}
            </h2>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div
              v-for="feature in featureHighlights"
              :key="feature.id"
              class="p-5 rounded-2xl border border-dark-600 bg-dark-700/40"
            >
              <div class="w-12 h-12 rounded-xl bg-dark-800 flex items-center justify-center text-2xl">
                {{ feature.icon }}
              </div>
              <h3 class="text-base font-semibold text-white mt-4">
                {{ isZh ? feature.title_zh : feature.title }}
              </h3>
              <p class="text-xs text-gray-400 mt-2">
                {{ isZh ? feature.description_zh : feature.description }}
              </p>
            </div>
          </div>
        </section>

        <section v-else-if="isLoadingFeatures" class="mb-12">
          <div class="flex items-center gap-3 text-gray-400">
            <svg class="animate-spin w-5 h-5" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span>{{ isZh ? '載入功能亮點...' : 'Loading highlights...' }}</span>
          </div>
        </section>

        <!-- ============================================
             VIDEO SHOWCASE
             ============================================ -->
        <section v-if="videoExamples.length > 0" class="mb-12">
          <div class="flex items-center justify-between mb-6">
            <h2 class="text-lg font-semibold text-white flex items-center gap-2">
              <span>🎬</span>
              {{ isZh ? '短影片精選案例' : 'Short Video Showcase' }}
            </h2>
            <RouterLink to="/tools/short-video" class="text-sm text-primary-400 hover:text-primary-300 flex items-center gap-1">
              {{ isZh ? '查看更多' : 'View More' }}
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
            </RouterLink>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div
              v-for="(video, idx) in videoExamples.slice(0, 6)"
              :key="video.id || idx"
              class="group relative aspect-video rounded-xl overflow-hidden bg-dark-700 cursor-pointer"
              @click="playVideo(video)"
            >
              <!-- Video preview with hover-to-play -->
              <video
                v-if="video.video"
                :src="video.video"
                class="w-full h-full object-cover"
                muted
                preload="metadata"
                @mouseenter="($event.target as HTMLVideoElement).play()"
                @mouseleave="($event.target as HTMLVideoElement).pause(); ($event.target as HTMLVideoElement).currentTime = 0"
              />
              <!-- Fallback to image thumbnail -->
              <img
                v-else
                :src="video.thumb || video.image_url || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400'"
                :alt="video.title"
                class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
              />

              <!-- Play Overlay -->
              <div class="absolute inset-0 bg-black/30 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                <div class="w-12 h-12 bg-white/90 rounded-full flex items-center justify-center">
                  <svg class="w-6 h-6 text-primary-600 ml-1" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </div>
              </div>

              <!-- Topic Badge -->
              <div class="absolute top-2 left-2 px-2 py-1 bg-black/70 text-white text-xs rounded-full">
                {{ video.title || video.topic }}
              </div>

              <!-- Title Overlay with prompt -->
              <div class="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-black/80 to-transparent">
                <p class="text-white text-xs line-clamp-2">
                  {{ video.prompt || (isZh ? '精選案例' : 'Featured Example') }}
                </p>
              </div>
            </div>
          </div>
        </section>

        <!-- Loading State for Videos -->
        <section v-else-if="isLoadingVideos" class="mb-12">
          <div class="flex items-center gap-3 text-gray-400">
            <svg class="animate-spin w-5 h-5" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span>{{ isZh ? '載入精選案例...' : 'Loading examples...' }}</span>
          </div>
        </section>

        <!-- ============================================
             AI AVATAR SHOWCASE
             ============================================ -->
        <section v-if="avatarExamples.length > 0" class="mb-12">
          <div class="flex items-center justify-between mb-6">
            <h2 class="text-lg font-semibold text-white flex items-center gap-2">
              <span>🧑‍💼</span>
              {{ isZh ? 'AI 數位人 精選案例' : 'AI Avatar Showcase' }}
            </h2>
            <RouterLink to="/tools/avatar" class="text-sm text-primary-400 hover:text-primary-300 flex items-center gap-1">
              {{ isZh ? '立即體驗' : 'Try Now' }}
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
            </RouterLink>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div
              v-for="(avatar, idx) in avatarExamples"
              :key="avatar.id || idx"
              class="group relative rounded-xl overflow-hidden bg-dark-700 cursor-pointer"
              @click="playVideo({ video: avatar.result_video_url, title: isZh ? 'AI 數位人' : 'AI Avatar', prompt: avatar.prompt })"
            >
              <!-- Avatar Photo with Video Hover Preview -->
              <div class="aspect-[9/16] relative">
                <!-- Static Photo (default) -->
                <img
                  :src="avatar.input_image_url || avatar.thumbnail_url || 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=400'"
                  :alt="isZh ? 'AI 數位人' : 'AI Avatar'"
                  class="w-full h-full object-cover transition-opacity duration-300"
                  :class="{ 'opacity-0': hoveredAvatar === idx }"
                />
                <!-- Video Preview (on hover) -->
                <video
                  v-if="avatar.result_video_url"
                  :src="avatar.result_video_url"
                  class="absolute inset-0 w-full h-full object-cover transition-opacity duration-300"
                  :class="{ 'opacity-100': hoveredAvatar === idx, 'opacity-0': hoveredAvatar !== idx }"
                  muted
                  loop
                  playsinline
                  @mouseenter="hoveredAvatar = idx; ($event.target as HTMLVideoElement).play()"
                  @mouseleave="hoveredAvatar = null; ($event.target as HTMLVideoElement).pause()"
                />
              </div>

              <!-- Play Overlay -->
              <div class="absolute inset-0 bg-black/20 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                <div class="w-14 h-14 bg-white/90 rounded-full flex items-center justify-center shadow-lg">
                  <svg class="w-7 h-7 text-primary-600 ml-1" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </div>
              </div>

              <!-- Avatar Badge -->
              <div class="absolute top-2 left-2 px-2 py-1 bg-gradient-to-r from-purple-600 to-pink-500 text-white text-xs rounded-full font-medium">
                {{ isZh ? 'AI 數位人' : 'AI Avatar' }}
              </div>

              <!-- Script Preview -->
              <div class="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-black/90 to-transparent">
                <p class="text-white text-xs line-clamp-2">
                  {{ (isZh ? avatar.prompt_zh : avatar.prompt) || (isZh ? '專業數位代言人' : 'Professional Digital Presenter') }}
                </p>
              </div>
            </div>
          </div>
        </section>

        <!-- Loading State for Avatars -->
        <section v-else-if="isLoadingAvatars" class="mb-12">
          <div class="flex items-center gap-3 text-gray-400">
            <svg class="animate-spin w-5 h-5" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span>{{ isZh ? '載入 AI 數位人...' : 'Loading AI Avatars...' }}</span>
          </div>
        </section>

        <!-- ============================================
             QUICK ACCESS CATEGORIES - Mobile visible (horizontal scroll)
             ============================================ -->
        <section class="lg:hidden mb-12">
          <h2 class="text-lg font-semibold text-white mb-4">
            {{ isZh ? '功能分類' : 'Categories' }}
          </h2>
          <div class="flex gap-3 overflow-x-auto pb-2 scrollbar-hide -mx-4 px-4">
            <button
              v-for="cat in categories"
              :key="cat.key"
              @click="goToTool(cat.tools[0]?.route || '/')"
              class="flex items-center gap-2 px-4 py-3 bg-dark-700/50 hover:bg-dark-700 border border-dark-600 rounded-xl transition-colors whitespace-nowrap flex-shrink-0"
            >
              <span class="text-xl">{{ cat.icon }}</span>
              <span class="text-sm text-white">{{ isZh ? cat.nameZh : cat.name }}</span>
            </button>
          </div>
        </section>

        <!-- ============================================
             CTA SECTION
             ============================================ -->
        <section class="bg-gradient-to-r from-primary-500/20 to-cyan-500/20 rounded-2xl p-8 text-center">
          <h2 class="text-xl md:text-2xl font-bold text-white mb-3">
            {{ isZh ? '開始你的 AI 創作之旅' : 'Start Your AI Creation Journey' }}
          </h2>
          <p class="text-gray-400 mb-6">
            {{ isZh ? '免費試用，無需信用卡' : 'Free trial, no credit card required' }}
          </p>
          <RouterLink to="/auth/register" class="inline-flex items-center gap-2 px-6 py-3 bg-primary-500 hover:bg-primary-600 text-white rounded-xl transition-colors">
            <span>✨</span>
            {{ isZh ? '免費開始' : 'Start Free' }}
          </RouterLink>
        </section>

      </div>
    </main>

    <!-- ============================================
         MOBILE BOTTOM NAV - Category quick access
         ============================================ -->
    <nav class="lg:hidden fixed bottom-0 left-0 right-0 bg-dark-800/95 backdrop-blur-lg border-t border-dark-700 z-40">
      <div class="flex justify-around py-2">
        <button
          v-for="cat in categories.slice(0, 5)"
          :key="cat.key"
          @click="goToTool(cat.tools[0]?.route || '/')"
          class="flex flex-col items-center gap-1 py-2 px-3 text-gray-400 hover:text-white transition-colors"
        >
          <span class="text-xl">{{ cat.icon }}</span>
          <span class="text-[10px]">{{ isZh ? cat.nameZh.slice(0, 4) : cat.name.slice(0, 6) }}</span>
        </button>
      </div>
    </nav>
    <!-- Video Modal -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="showVideoModal && selectedVideo"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          @click.self="closeVideoModal"
        >
          <div class="relative w-full max-w-4xl mx-4">
            <!-- Close Button -->
            <button
              @click="closeVideoModal"
              class="absolute -top-12 right-0 text-white/80 hover:text-white transition-colors"
            >
              <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            <!-- Video Player -->
            <div class="bg-dark-800 rounded-xl overflow-hidden">
              <video
                :src="selectedVideo.video_url || selectedVideo.result_video_url"
                class="w-full"
                controls
                autoplay
              />
              <div class="p-4">
                <h3 class="text-lg font-semibold text-white">
                  {{ selectedVideo.title || (isZh ? '精選案例' : 'Featured Example') }}
                </h3>
                <p v-if="selectedVideo.description" class="text-gray-400 mt-2 text-sm">
                  {{ selectedVideo.description }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(-10px);
  opacity: 0;
}

/* Fade transition for modal */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Add padding for mobile bottom nav */
@media (max-width: 1023px) {
  main {
    padding-bottom: 80px;
  }
}

/* Hide scrollbar for horizontal scroll containers */
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
</style>
