<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t, locale } = useI18n()
const router = useRouter()

type GalleryItem = {
  id: string
  // Display strings — either bilingual pair (set by curated fallbacks) or a
  // single string (set by /demo/inspiration API, which is already localized).
  // The template picks by locale at render time.
  title: string
  prompt: string
  title_zh?: string
  prompt_zh?: string
  image_url?: string
  video_url?: string
  thumbnail_url?: string
  tool_type: string
  topic?: string
  tags: string[]
  type: 'image' | 'video'
}

const isZh = computed(() => locale.value.startsWith('zh'))
function displayTitle(item: GalleryItem): string {
  if (isZh.value && item.title_zh) return item.title_zh
  return item.title
}
function displayPrompt(item: GalleryItem): string {
  if (isZh.value && item.prompt_zh) return item.prompt_zh
  return item.prompt
}

type SettledResult<T> = {
  ok: boolean
  value?: T
}

// Bilingual fallback rows — the EN string is primary (used when
// locale !== zh), and `title_zh`/`prompt_zh` surface only on the zh-TW page.
const CURATED_FALLBACK_ITEMS: GalleryItem[] = [
  {
    id: 'fallback-product-1',
    title: 'Handmade soap brand hero shot',
    title_zh: '手工皂品牌展示圖',
    prompt: 'Handmade soap with kraft paper packaging on a wooden table, soft daylight — ideal for boutique e-commerce.',
    prompt_zh: '手工皂與牛皮紙包裝置於木質桌面，柔和日光，適合小品牌電商展示。',
    image_url: 'https://images.unsplash.com/photo-1607006483225-50cf5d3a88f5?auto=format&fit=crop&w=900&q=80',
    tool_type: 'product_scene',
    topic: 'product_scene',
    tags: ['product', 'ecommerce', 'small_business'],
    type: 'image',
  },
  {
    id: 'fallback-product-2',
    title: 'Coffee packaging e-commerce hero',
    title_zh: '咖啡包裝電商主圖',
    prompt: 'Bag of coffee beans on a wooden table, warm ambient light — suited for an e-commerce hero banner.',
    prompt_zh: '咖啡豆包裝在木質桌面，暖光氛圍，適合電商首頁展示。',
    image_url: 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=900&q=80',
    tool_type: 'product_scene',
    topic: 'product_scene',
    tags: ['food', 'beverage', 'product'],
    type: 'image',
  },
  {
    id: 'fallback-bg-1',
    title: 'Clean background removal',
    title_zh: '透明背景商品去背',
    prompt: 'Preserve product edge detail while cutting the background to a clean white backdrop.',
    prompt_zh: '保留商品邊緣細節，自動去除背景並輸出乾淨白底圖。',
    image_url: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=80',
    tool_type: 'background_removal',
    topic: 'background_removal',
    tags: ['ecommerce', 'catalog', 'clean'],
    type: 'image',
  },
  {
    id: 'fallback-tryon-1',
    title: 'AI model try-on: sport jacket',
    title_zh: '運動外套 AI 模特試穿',
    prompt: 'Apply a flat-laid jacket to a natural standing model while keeping fabric texture and fit intact.',
    prompt_zh: '將平拍外套套用到自然站姿模特，保留布料質感與版型。',
    image_url: 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=900&q=80',
    tool_type: 'try_on',
    topic: 'try_on',
    tags: ['fashion', 'clothing', 'model'],
    type: 'image',
  },
  {
    id: 'fallback-room-1',
    title: 'Scandinavian living-room redesign',
    title_zh: '北歐風客廳改造',
    prompt: 'Redesign the room in Nordic style with wooden furniture, natural light, and a crisp warm palette.',
    prompt_zh: '將空間改為北歐風，木質家具與自然採光，清爽暖色調。',
    image_url: 'https://images.unsplash.com/photo-1484101403633-562f891dc89a?auto=format&fit=crop&w=900&q=80',
    tool_type: 'room_redesign',
    topic: 'room_redesign',
    tags: ['interior', 'living_room', 'design'],
    type: 'image',
  },
  {
    id: 'fallback-video-1',
    title: 'Product rotation short video',
    title_zh: '產品旋轉短影音',
    prompt: 'Turn a single product image into an 8-second smooth rotation clip — tuned for social ads.',
    prompt_zh: '單張商品主圖生成 8 秒平滑旋轉展示影片，適合社群廣告。',
    image_url: 'https://images.unsplash.com/photo-1512496015851-a90fb38ba796?auto=format&fit=crop&w=900&q=80',
    tool_type: 'short_video',
    topic: 'short_video',
    tags: ['marketing', 'social', 'video'],
    type: 'video',
  },
  {
    id: 'fallback-avatar-1',
    title: 'Beauty brand AI presenter',
    title_zh: '美妝品牌 AI 導購',
    prompt: 'AI digital presenter introduces a new product — fluent delivery and tight pacing.',
    prompt_zh: 'AI 數位人介紹新品賣點，口播流暢、節奏精準。',
    image_url: 'https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=900&q=80',
    tool_type: 'ai_avatar',
    topic: 'ai_avatar',
    tags: ['marketing', 'brand', 'presenter'],
    type: 'video',
  },
  {
    id: 'fallback-effect-1',
    title: 'Comic-style product visual',
    title_zh: '漫畫風商品視覺',
    prompt: 'Convert the product shot into a comic-book style visual while keeping the subject recognizable and bumping contrast.',
    prompt_zh: '商品圖轉換為漫畫風視覺，保留主體辨識度並強化色彩對比。',
    image_url: 'https://images.unsplash.com/photo-1523381210434-271e8be1f52b?auto=format&fit=crop&w=900&q=80',
    tool_type: 'effect',
    topic: 'effect',
    tags: ['style', 'creative', 'ad'],
    type: 'image',
  },
  {
    id: 'fallback-pattern-1',
    title: 'Geometric packaging pattern',
    title_zh: '包裝用幾何圖案',
    prompt: 'Generate a tileable geometric pattern usable for brand packaging and e-commerce backdrops.',
    prompt_zh: '生成可平鋪幾何圖案，適用於品牌包裝與電商背景素材。',
    image_url: 'https://images.unsplash.com/photo-1456324504439-367cee3b3c32?auto=format&fit=crop&w=900&q=80',
    tool_type: 'pattern_generate',
    topic: 'pattern_generate',
    tags: ['pattern', 'design', 'branding'],
    type: 'image',
  },
]

// Gallery categories (matching piapi.ai style)
const categories = ref([
  { id: 'all', name: t('gallery.categories.all'), icon: '🌟', count: 0 },
  { id: 'product_scene', name: t('gallery.categories.product_scene'), icon: '📸', count: 0 },
  { id: 'background_removal', name: t('gallery.categories.background_removal'), icon: '✂️', count: 0 },
  { id: 'try_on', name: t('gallery.categories.try_on'), icon: '👗', count: 0 },
  { id: 'room_redesign', name: t('gallery.categories.room_redesign'), icon: '🏠', count: 0 },
  { id: 'short_video', name: t('gallery.categories.short_video'), icon: '🎬', count: 0 },
  { id: 'ai_avatar', name: t('gallery.categories.ai_avatar'), icon: '🎭', count: 0 },
  { id: 'effect', name: t('gallery.categories.effect'), icon: '🎨', count: 0 },
  { id: 'pattern_generate', name: t('gallery.categories.pattern_generate'), icon: '🔲', count: 0 },
])

// Industry filters (for SMB targeting)
const industries = ref([
  { id: 'all', name: t('gallery.industries.all'), icon: '🏢' },
  { id: 'food_beverage', name: t('gallery.industries.food_beverage'), icon: '🍔' },
  { id: 'fashion', name: t('gallery.industries.fashion'), icon: '👕' },
  { id: 'ecommerce', name: t('gallery.industries.ecommerce'), icon: '🛒' },
  { id: 'interior_design', name: t('gallery.industries.interior_design'), icon: '🛋️' },
  { id: 'marketing', name: t('gallery.industries.marketing'), icon: '📢' },
  { id: 'small_business', name: t('gallery.industries.small_business'), icon: '🏪' },
])

// Gallery items
const galleryItems = ref<GalleryItem[]>([])
const isLoading = ref(true)
const selectedCategory = ref('all')
const selectedIndustry = ref('all')
const searchQuery = ref('')

// Filtered items
const filteredItems = computed(() => {
  let items = galleryItems.value

  if (selectedCategory.value !== 'all') {
    items = items.filter(item => item.tool_type === selectedCategory.value)
  }

  if (selectedIndustry.value !== 'all') {
    const industryMap: Record<string, string[]> = {
      food_beverage: ['drinks', 'snacks', 'desserts', 'meals', 'food', 'beverage', 'restaurant'],
      fashion: ['casual', 'formal', 'sportswear', 'outerwear', 'accessories', 'dresses', 'clothing'],
      ecommerce: ['product', 'ecommerce', 'shopping', 'online', 'store'],
      interior_design: ['living_room', 'bedroom', 'kitchen', 'bathroom', 'interior', 'design'],
      marketing: ['promo', 'brand', 'ad', 'marketing', 'social'],
      small_business: ['small', 'business', 'local', 'shop', 'store']
    }

    const industryKeywords = industryMap[selectedIndustry.value] || []
    items = items.filter(item => {
      const tags = item.tags || []
      const topic = item.topic || ''
      const prompt = item.prompt || ''

      return industryKeywords.some(keyword =>
        tags.includes(keyword) ||
        topic.includes(keyword) ||
        prompt.toLowerCase().includes(keyword)
      )
    })
  }

  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    items = items.filter(item => {
      const prompt = item.prompt?.toLowerCase() || ''
      const topic = item.topic?.toLowerCase() || ''
      const tags = (item.tags || []).join(' ').toLowerCase()

      return prompt.includes(query) || topic.includes(query) || tags.includes(query)
    })
  }

  return items
})

// Load gallery data
function inferToolTypeFromExample(source: {
  topic?: string
  title?: string
  prompt?: string
  style_tags?: string[]
}): string {
  const text = `${source.topic || ''} ${source.title || ''} ${source.prompt || ''} ${(source.style_tags || []).join(' ')}`.toLowerCase()

  if (text.includes('avatar') || text.includes('digital human') || text.includes('數位人')) return 'ai_avatar'
  if (text.includes('video') || text.includes('影片') || text.includes('短影音')) return 'short_video'
  if (text.includes('try on') || text.includes('試穿') || text.includes('model')) return 'try_on'
  if (text.includes('room') || text.includes('interior') || text.includes('室內') || text.includes('空間')) return 'room_redesign'
  if (text.includes('remove background') || text.includes('去背') || text.includes('白底')) return 'background_removal'
  if (text.includes('pattern') || text.includes('圖案')) return 'pattern_generate'
  if (text.includes('effect') || text.includes('style') || text.includes('風格')) return 'effect'

  return 'product_scene'
}

function withFallbackItems(items: GalleryItem[]): GalleryItem[] {
  if (items.length >= 18) return items

  const existingIds = new Set(items.map(i => i.id))
  const nextItems = [...items]

  CURATED_FALLBACK_ITEMS.forEach((fallback) => {
    if (!existingIds.has(fallback.id)) {
      nextItems.push(fallback)
    }
  })

  return nextItems
}

async function loadGalleryData() {
  isLoading.value = true
  try {
    const safeJson = async <T>(url: string): Promise<SettledResult<T>> => {
      try {
        const response = await fetch(url)
        const value = await response.json()
        return { ok: true, value }
      } catch {
        return { ok: false }
      }
    }

    const [inspirationRes, worksRes] = await Promise.all([
      safeJson<any>('/api/v1/demo/inspiration?count=50'),
      safeJson<any>('/api/v1/demo/landing/works?limit=50')
    ])

    const items: GalleryItem[] = []

    if (inspirationRes.ok && inspirationRes.value?.success) {
      const examples = inspirationRes.value.examples || []
      examples.forEach((ex: any) => {
        const inferredToolType = inferToolTypeFromExample(ex)
        items.push({
          id: ex.id,
          title: ex.title || ex.topic_display,
          prompt: ex.prompt,
          image_url: ex.image_url,
          video_url: ex.video_url,
          thumbnail_url: ex.thumbnail_url,
          tool_type: inferredToolType,
          topic: ex.topic,
          tags: ex.style_tags || [inferredToolType],
          type: ex.video_url ? 'video' : 'image'
        })
      })
    }

    if (worksRes.ok && worksRes.value?.success) {
      const works = worksRes.value.items || []
      works.forEach((work: any) => {
        items.push({
          id: work.id,
          title: work.title,
          prompt: work.prompt,
          image_url: work.thumb || work.result_image_url,
          video_url: work.video_url,
          tool_type: work.tool_type,
          topic: work.topic,
          tags: [work.tool_type, work.topic],
          type: work.video_url ? 'video' : 'image'
        })
      })
    }

    galleryItems.value = withFallbackItems(items)

    categories.value.forEach((cat: { id: string; count: number }) => {
      if (cat.id === 'all') {
        cat.count = galleryItems.value.length
      } else {
        cat.count = galleryItems.value.filter(item => item.tool_type === cat.id).length
      }
    })

  } catch (error) {
    console.error('Failed to load gallery data:', error)
  } finally {
    isLoading.value = false
  }
}

function categoryLabelByTool(toolType: string): string {
  const category = categories.value.find(c => c.id === toolType)
  return category?.name || toolType
}

function setInputFocusStyle(event: FocusEvent) {
  const target = event.target as HTMLInputElement | null
  if (target) target.style.borderColor = '#1677ff'
}

function setInputBlurStyle(event: FocusEvent) {
  const target = event.target as HTMLInputElement | null
  if (target) target.style.borderColor = 'rgba(255,255,255,0.08)'
}

function setCardHoverStyle(event: MouseEvent) {
  const target = event.currentTarget as HTMLElement | null
  if (!target) return
  target.style.borderColor = 'rgba(22,119,255,0.3)'
  target.style.boxShadow = '0 12px 40px rgba(0,0,0,0.5)'
}

function resetCardHoverStyle(event: MouseEvent) {
  const target = event.currentTarget as HTMLElement | null
  if (!target) return
  target.style.borderColor = 'rgba(255,255,255,0.06)'
  target.style.boxShadow = 'none'
}

function tryExample(item: any) {
  const routeMap: Record<string, string> = {
    product_scene: '/tools/product-scene',
    background_removal: '/tools/background-removal',
    try_on: '/tools/try-on',
    room_redesign: '/tools/room-redesign',
    short_video: '/tools/short-video',
    ai_avatar: '/tools/avatar',
    effect: '/tools/effects',
    pattern_generate: '/tools/pattern-generate',
    inspiration: '/tools/product-scene'
  }
  const route = routeMap[item.tool_type] || '/tools/product-scene'
  router.push(route)
}

onMounted(() => {
  loadGalleryData()
})
</script>

<template>
  <div style="background: #09090b; min-height: 100vh;">
    <!-- Hero Section -->
    <section class="relative pt-28 pb-12 px-4 sm:px-6 lg:px-8 overflow-hidden">
      <div class="absolute inset-0 bg-mesh"></div>
      <div class="relative max-w-7xl mx-auto">
        <div class="text-center mb-12">
          <h1 class="text-4xl md:text-5xl font-bold mb-4" style="color: #f5f5fa;">
            {{ t('gallery.title') }}
          </h1>
          <p class="text-lg md:text-xl max-w-3xl mx-auto mb-8" style="color: #9494b0;">
            {{ t('gallery.subtitle') }}
          </p>

          <!-- Search Bar -->
          <div class="max-w-2xl mx-auto mb-8">
            <div class="relative">
              <input
                v-model="searchQuery"
                type="text"
                :placeholder="t('gallery.searchPlaceholder')"
                class="w-full px-6 py-4 pl-12 text-lg rounded-xl transition-all"
                style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #f5f5fa; outline: none;"
                @focus="setInputFocusStyle"
                @blur="setInputBlurStyle"
              />
              <div class="absolute left-4 top-1/2 transform -translate-y-1/2" style="color: #6b6b8a;">
                🔍
              </div>
            </div>
          </div>
        </div>

        <!-- Industry Filters -->
        <div class="mb-8">
          <h3 class="text-lg font-semibold mb-4" style="color: #c4c4d8;">{{ t('gallery.filterByIndustry') }}</h3>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="industry in industries"
              :key="industry.id"
              @click="selectedIndustry = industry.id"
              class="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all"
              :style="selectedIndustry === industry.id
                ? 'background: #1677ff; color: #ffffff; box-shadow: 0 4px 16px rgba(22,119,255,0.35);'
                : 'background: #141420; color: #9494b0; border: 1px solid rgba(255,255,255,0.08);'"
            >
              <span>{{ industry.icon }}</span>
              {{ industry.name }}
            </button>
          </div>
        </div>

        <!-- Category Filters -->
        <div class="mb-12">
          <h3 class="text-lg font-semibold mb-4" style="color: #c4c4d8;">{{ t('gallery.filterByTool') }}</h3>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="category in categories"
              :key="category.id"
              @click="selectedCategory = category.id"
              class="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all"
              :style="selectedCategory === category.id
                ? 'background: #1677ff; color: #ffffff; box-shadow: 0 4px 16px rgba(22,119,255,0.35);'
                : 'background: #141420; color: #9494b0; border: 1px solid rgba(255,255,255,0.08);'"
            >
              <span>{{ category.icon }}</span>
              {{ category.name }}
              <span class="ml-1 px-1.5 py-0.5 text-xs rounded-full" style="background: rgba(255,255,255,0.06); color: #6b6b8a;">
                {{ category.count }}
              </span>
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- Gallery Grid -->
    <section class="pb-20 px-4 sm:px-6 lg:px-8">
      <div class="max-w-7xl mx-auto">
        <!-- Results Count -->
        <div class="mb-6 flex justify-between items-center">
          <p style="color: #9494b0;">
            {{ t('gallery.showingResults', { count: filteredItems.length, total: galleryItems.length }) }}
          </p>
          <div v-if="selectedCategory !== 'all' || selectedIndustry !== 'all' || searchQuery">
            <button
              @click="selectedCategory = 'all'; selectedIndustry = 'all'; searchQuery = ''"
              class="text-sm font-medium" style="color: #1677ff;"
            >
              {{ t('gallery.clearFilters') }}
            </button>
          </div>
        </div>

        <!-- Loading State -->
        <div v-if="isLoading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          <div v-for="i in 8" :key="i" class="animate-pulse">
            <div class="rounded-2xl aspect-square mb-3" style="background: #141420;"></div>
            <div class="h-4 rounded mb-2" style="background: #141420;"></div>
            <div class="h-3 rounded w-3/4" style="background: #141420;"></div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else-if="filteredItems.length === 0" class="text-center py-16">
          <div class="text-6xl mb-4">🎨</div>
          <h3 class="text-xl font-semibold mb-2" style="color: #e8e8f0;">{{ t('gallery.noResults') }}</h3>
          <p class="mb-6" style="color: #6b6b8a;">{{ t('gallery.noResultsHint') }}</p>
          <button
            @click="selectedCategory = 'all'; selectedIndustry = 'all'; searchQuery = ''"
            class="btn-primary"
          >
            {{ t('gallery.viewAllExamples') }}
          </button>
        </div>

        <!-- Gallery Grid -->
        <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          <div
            v-for="item in filteredItems"
            :key="item.id"
            class="group rounded-2xl overflow-hidden transition-all duration-300 hover:-translate-y-1 cursor-pointer"
            style="background: #141420; border: 1px solid rgba(255,255,255,0.06);"
            @click="tryExample(item)"
            @mouseenter="setCardHoverStyle"
            @mouseleave="resetCardHoverStyle"
          >
            <!-- Media Container -->
            <div class="relative aspect-square overflow-hidden" style="background: #0f0f17;">
              <!-- Video Indicator -->
              <div v-if="item.type === 'video'" class="absolute top-3 right-3 z-10">
                <span class="px-2 py-1 text-xs font-medium rounded-full flex items-center gap-1" style="background: rgba(0,0,0,0.7); color: white; backdrop-filter: blur(4px);">
                  <span>▶️</span>
                  <span>{{ t('gallery.video') }}</span>
                </span>
              </div>

              <!-- Tool Type Badge -->
              <div class="absolute top-3 left-3 z-10">
                <span class="px-2 py-1 text-xs font-medium rounded-full" style="background: rgba(255,255,255,0.1); color: #c4c4d8; backdrop-filter: blur(4px);">
                  {{ categoryLabelByTool(item.tool_type) }}
                </span>
              </div>

              <!-- Image -->
              <img
                v-if="item.type === 'image'"
                :src="item.image_url || item.thumbnail_url"
                :alt="displayTitle(item)"
                class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
              />

              <!-- Video poster -->
              <div v-else-if="item.type === 'video'" class="relative w-full h-full">
                <img
                  :src="item.image_url || item.thumbnail_url"
                  :alt="displayTitle(item)"
                  class="w-full h-full object-cover"
                />
                <div class="absolute inset-0 flex items-center justify-center" style="background: rgba(0,0,0,0.2);">
                  <div class="w-16 h-16 rounded-full flex items-center justify-center text-2xl" style="background: rgba(255,255,255,0.15); backdrop-filter: blur(8px);">
                    ▶️
                  </div>
                </div>
              </div>

              <!-- Try This Overlay -->
              <div class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-end" style="background: linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 50%);">
                <div class="p-4 w-full">
                  <button class="w-full py-3 font-semibold rounded-lg transition-colors" style="background: #1677ff; color: white;">
                    {{ t('gallery.tryThis') }}
                  </button>
                </div>
              </div>
            </div>

            <!-- Content -->
            <div class="p-4">
              <h3 class="font-semibold mb-2 line-clamp-1" style="color: #e8e8f0;">{{ displayTitle(item) }}</h3>
              <p class="text-sm mb-3 line-clamp-2" style="color: #6b6b8a;">{{ displayPrompt(item) }}</p>

              <!-- Tags -->
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="tag in item.tags.slice(0, 3)"
                  :key="tag"
                  class="px-2 py-1 text-xs rounded"
                  style="background: rgba(255,255,255,0.04); color: #6b6b8a;"
                >
                  {{ tag }}
                </span>
                <span v-if="item.tags.length > 3" class="px-2 py-1 text-xs" style="color: #3a3a55;">
                  +{{ item.tags.length - 3 }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- CTA Section -->
        <div v-if="!isLoading && filteredItems.length > 0" class="mt-16 text-center">
          <div class="rounded-2xl p-8 md:p-12 relative overflow-hidden" style="background: #0f1830; border: 1px solid rgba(22,119,255,0.15);">
            <div class="absolute inset-0 bg-mesh"></div>
            <div class="relative">
              <h2 class="text-2xl md:text-3xl font-bold mb-4" style="color: #f5f5fa;">
                {{ t('gallery.ctaTitle') }}
              </h2>
              <p class="mb-8 max-w-2xl mx-auto" style="color: #9494b0;">
                {{ t('gallery.ctaSubtitle') }}
              </p>
              <div class="flex flex-col sm:flex-row gap-4 justify-center">
                <button
                  @click="router.push('/auth/register')"
                  class="btn-accent px-8 py-3"
                >
                  {{ t('gallery.ctaButtonPrimary') }}
                </button>
                <button
                  @click="router.push('/pricing')"
                  class="btn-secondary px-8 py-3"
                >
                  {{ t('gallery.ctaButtonSecondary') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.line-clamp-1 {
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
}

.line-clamp-2 {
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
</style>
