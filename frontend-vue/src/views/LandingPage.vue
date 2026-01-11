<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import apiClient from '@/api/client'

const { locale } = useI18n()
const router = useRouter()

const isZh = computed(() => locale.value.startsWith('zh'))

// ============================================
// TIME-BASED GREETING
// ============================================
const greeting = computed(() => {
  const hour = new Date().getHours()
  if (isZh.value) {
    if (hour < 6) return '凌晨好'
    if (hour < 12) return '早上好'
    if (hour < 14) return '中午好'
    if (hour < 18) return '下午好'
    return '晚上好'
  } else {
    if (hour < 6) return 'Good night'
    if (hour < 12) return 'Good morning'
    if (hour < 14) return 'Good afternoon'
    if (hour < 18) return 'Good afternoon'
    return 'Good evening'
  }
})

// ============================================
// SIDEBAR CATEGORIES - Like douhuiai.com
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
  color: string
  tools: Tool[]
}

const categories = ref<Category[]>([
  {
    key: 'aiImage',
    icon: '🎨',
    name: 'AI Image',
    nameZh: 'AI 圖像創作',
    color: 'purple',
    tools: [
      { key: 'productScene', icon: '🏞️', route: '/tools/product-scene', name: 'Product Scene', nameZh: '產品場景' },
      { key: 'bgRemoval', icon: '✂️', route: '/tools/background-removal', name: 'Remove Background', nameZh: '智能去背' },
      { key: 'patternGen', icon: '🔲', route: '/tools/pattern-generate', name: 'Pattern Design', nameZh: '圖案設計' },
      { key: 'imageEnhance', icon: '✨', route: '/tools/product-scene', name: 'Image Enhance', nameZh: '圖片增強' }
    ]
  },
  {
    key: 'aiVideo',
    icon: '🎬',
    name: 'AI Video',
    nameZh: 'AI 影片創作',
    color: 'cyan',
    tools: [
      { key: 'shortVideo', icon: '📱', route: '/tools/short-video', name: 'Short Video', nameZh: '短影片生成' },
      { key: 'imageToVideo', icon: '🎥', route: '/tools/image-to-video', name: 'Image to Video', nameZh: '圖片轉影片' },
      { key: 'videoTransform', icon: '🔄', route: '/tools/video-transform', name: 'Style Transfer', nameZh: '風格轉換' },
      { key: 'productVideo', icon: '🛍️', route: '/tools/product-video', name: 'Product Video', nameZh: '產品影片' }
    ]
  },
  {
    key: 'aiAvatar',
    icon: '🎭',
    name: 'AI Avatar',
    nameZh: 'AI 數位人',
    color: 'pink',
    tools: [
      { key: 'avatar', icon: '🎤', route: '/tools/avatar', name: 'Digital Human', nameZh: '數位人影片' },
      { key: 'lipSync', icon: '👄', route: '/tools/avatar', name: 'Lip Sync', nameZh: '口型同步' },
      { key: 'voiceClone', icon: '🗣️', route: '/tools/avatar', name: 'Voice Clone', nameZh: '聲音克隆' }
    ]
  },
  {
    key: 'ecommerce',
    icon: '🛒',
    name: 'E-commerce',
    nameZh: '電商工具',
    color: 'orange',
    tools: [
      { key: 'tryOn', icon: '👗', route: '/tools/try-on', name: 'Virtual Try-On', nameZh: '虛擬試穿' },
      { key: 'productScene', icon: '🏞️', route: '/tools/product-scene', name: 'Product Photo', nameZh: '產品照片' },
      { key: 'bgRemoval', icon: '✂️', route: '/tools/background-removal', name: 'Background Remove', nameZh: '背景移除' }
    ]
  },
  {
    key: 'interior',
    icon: '🏠',
    name: 'Interior Design',
    nameZh: '室內設計',
    color: 'green',
    tools: [
      { key: 'roomRedesign', icon: '🛋️', route: '/tools/room-redesign', name: 'Room Redesign', nameZh: '空間重設計' },
      { key: 'floorPlan', icon: '📐', route: '/tools/room-redesign', name: 'Floor Plan', nameZh: '平面圖設計' },
      { key: 'styleChange', icon: '🎨', route: '/tools/room-redesign', name: 'Style Change', nameZh: '風格轉換' }
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
// FEATURED TOOLS - Main content area
// ============================================
const featuredTools = computed(() => [
  { key: 'shortVideo', icon: '📱', route: '/tools/short-video', name: isZh.value ? '短影片生成' : 'Short Video', desc: isZh.value ? '一鍵生成爆款短影片' : 'Create viral short videos', color: 'from-purple-500 to-pink-500', hot: true },
  { key: 'avatar', icon: '🎭', route: '/tools/avatar', name: isZh.value ? 'AI 數位人' : 'AI Avatar', desc: isZh.value ? '數位人口播影片' : 'Digital human videos', color: 'from-cyan-500 to-blue-500', hot: true },
  { key: 'productScene', icon: '🏞️', route: '/tools/product-scene', name: isZh.value ? '產品場景' : 'Product Scene', desc: isZh.value ? 'AI 生成產品場景' : 'AI product backgrounds', color: 'from-orange-500 to-red-500', new: true },
  { key: 'bgRemoval', icon: '✂️', route: '/tools/background-removal', name: isZh.value ? '智能去背' : 'Remove BG', desc: isZh.value ? '一鍵移除背景' : 'One-click background removal', color: 'from-green-500 to-teal-500' },
  { key: 'roomRedesign', icon: '🏠', route: '/tools/room-redesign', name: isZh.value ? '室內設計' : 'Room Design', desc: isZh.value ? 'AI 室內設計渲染' : 'AI interior rendering', color: 'from-blue-500 to-indigo-500' },
  { key: 'tryOn', icon: '👗', route: '/tools/try-on', name: isZh.value ? '虛擬試穿' : 'Virtual Try-On', desc: isZh.value ? 'AI 模特換裝' : 'AI model fitting', color: 'from-pink-500 to-rose-500' },
  { key: 'videoTransform', icon: '🔄', route: '/tools/video-transform', name: isZh.value ? '影片風格轉換' : 'Video Style', desc: isZh.value ? '影片風格化處理' : 'Video style transfer', color: 'from-yellow-500 to-orange-500' },
  { key: 'patternGen', icon: '🔲', route: '/tools/pattern-generate', name: isZh.value ? '圖案設計' : 'Pattern Design', desc: isZh.value ? 'AI 無縫圖案生成' : 'AI seamless patterns', color: 'from-indigo-500 to-purple-500' }
])

// ============================================
// VIDEO EXAMPLES
// ============================================
const videoExamples = ref<any[]>([])
const isLoadingVideos = ref(false)
const selectedVideo = ref<any>(null)
const showVideoModal = ref(false)

async function loadVideoExamples() {
  isLoadingVideos.value = true
  try {
    const langCode = locale.value.startsWith('zh') ? 'zh-TW' : 'en'
    const response = await apiClient.get(`/api/v1/demo/landing/examples?language=${langCode}`)
    if (response.data.success && response.data.examples?.length > 0) {
      videoExamples.value = response.data.examples
    }
  } catch (error) {
    console.error('Failed to load video examples:', error)
  } finally {
    isLoadingVideos.value = false
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
  loadVideoExamples()
})

watch(locale, () => {
  loadVideoExamples()
})
</script>

<template>
  <div class="min-h-screen pt-14 flex">
    <!-- ============================================
         LEFT SIDEBAR - Category Navigation (Like douhuiai.com)
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
          class="absolute left-16 top-0 bottom-0 w-56 bg-dark-800 border-r border-dark-700 shadow-xl overflow-y-auto"
        >
          <!-- Category Header -->
          <div class="sticky top-0 bg-dark-800 border-b border-dark-700 p-4">
            <div class="flex items-center gap-2">
              <span class="text-xl">{{ categories.find(c => c.key === hoveredCategory)?.icon }}</span>
              <span class="font-medium text-white">
                {{ isZh
                  ? categories.find(c => c.key === hoveredCategory)?.nameZh
                  : categories.find(c => c.key === hoveredCategory)?.name
                }}
              </span>
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

        <!-- Greeting Section -->
        <div class="mb-8">
          <h1 class="text-2xl md:text-3xl font-bold text-white mb-2">
            {{ greeting }}{{ isZh ? '，歡迎使用 VidGo' : ', Welcome to VidGo' }}
          </h1>
          <p class="text-gray-400">
            {{ isZh ? '選擇下方功能開始你的 AI 創作之旅' : 'Choose a tool below to start your AI creation journey' }}
          </p>
        </div>

        <!-- ============================================
             FEATURED TOOLS GRID - Like douhuiai.com
             ============================================ -->
        <section class="mb-12">
          <div class="flex items-center justify-between mb-6">
            <h2 class="text-lg font-semibold text-white flex items-center gap-2">
              <span>⚡</span>
              {{ isZh ? '功能推薦' : 'Featured Tools' }}
            </h2>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            <button
              v-for="tool in featuredTools"
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
             VIDEO SHOWCASE - AI影片 精選案例
             ============================================ -->
        <section v-if="videoExamples.length > 0" class="mb-12">
          <div class="flex items-center justify-between mb-6">
            <h2 class="text-lg font-semibold text-white flex items-center gap-2">
              <span>🎬</span>
              {{ isZh ? 'AI影片 精選案例' : 'AI Video Showcase' }}
            </h2>
            <RouterLink to="/topics/video" class="text-sm text-primary-400 hover:text-primary-300 flex items-center gap-1">
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
              <!-- Thumbnail -->
              <img
                :src="video.thumb || video.image_url || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400'"
                :alt="video.title"
                class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
              />

              <!-- Play Overlay -->
              <div class="absolute inset-0 bg-black/30 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                <div class="w-12 h-12 bg-white/90 rounded-full flex items-center justify-center">
                  <svg class="w-6 h-6 text-primary-600 ml-1" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </div>
              </div>

              <!-- Video Badge (shows if video is available) -->
              <div v-if="video.video_url || video.result_video_url" class="absolute top-2 right-2 px-2 py-1 bg-primary-500 text-white text-xs rounded-full">
                {{ isZh ? '影片' : 'Video' }}
              </div>

              <!-- Title Overlay -->
              <div class="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-black/80 to-transparent">
                <p class="text-white text-sm font-medium truncate">
                  {{ video.title || (isZh ? '精選案例' : 'Featured Example') }}
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
             QUICK ACCESS CATEGORIES - Mobile visible
             ============================================ -->
        <section class="lg:hidden mb-12">
          <h2 class="text-lg font-semibold text-white mb-4">
            {{ isZh ? '功能分類' : 'Categories' }}
          </h2>
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <button
              v-for="cat in categories"
              :key="cat.key"
              @click="goToTool(cat.tools[0]?.route || '/')"
              class="flex items-center gap-3 p-4 bg-dark-700/50 hover:bg-dark-700 border border-dark-600 rounded-xl transition-colors"
            >
              <span class="text-2xl">{{ cat.icon }}</span>
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
</style>
