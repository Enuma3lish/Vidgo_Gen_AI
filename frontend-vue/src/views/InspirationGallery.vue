<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { demoApi } from '@/api/demo'

const { t } = useI18n()
const router = useRouter()

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
const galleryItems = ref<any[]>([])
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
async function loadGalleryData() {
  isLoading.value = true
  try {
    const [inspirationRes, worksRes] = await Promise.allSettled([
      fetch('/api/v1/demo/inspiration?count=50').then(r => r.json()),
      fetch('/api/v1/demo/landing/works?limit=50').then(r => r.json())
    ])

    const items: any[] = []

    if (inspirationRes.status === 'fulfilled' && inspirationRes.value.success) {
      const examples = inspirationRes.value.examples || []
      examples.forEach((ex: any) => {
        items.push({
          id: ex.id,
          title: ex.title || ex.topic_display,
          prompt: ex.prompt,
          image_url: ex.image_url,
          video_url: ex.video_url,
          thumbnail_url: ex.thumbnail_url,
          tool_type: 'inspiration',
          topic: ex.topic,
          tags: ex.style_tags || [],
          type: ex.video_url ? 'video' : 'image'
        })
      })
    }

    if (worksRes.status === 'fulfilled' && worksRes.value.success) {
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

    galleryItems.value = items

    categories.value.forEach((cat: { id: string; count: number }) => {
      if (cat.id === 'all') {
        cat.count = items.length
      } else {
        cat.count = items.filter(item => item.tool_type === cat.id).length
      }
    })

  } catch (error) {
    console.error('Failed to load gallery data:', error)
  } finally {
    isLoading.value = false
  }
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
                @focus="($event.target as HTMLInputElement).style.borderColor = '#1677ff'"
                @blur="($event.target as HTMLInputElement).style.borderColor = 'rgba(255,255,255,0.08)'"
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
            @mouseenter="($event.currentTarget as HTMLElement).style.borderColor = 'rgba(22,119,255,0.3)'; ($event.currentTarget as HTMLElement).style.boxShadow = '0 12px 40px rgba(0,0,0,0.5)'"
            @mouseleave="($event.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.06)'; ($event.currentTarget as HTMLElement).style.boxShadow = 'none'"
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
                  {{ categories.find((c: any) => c.id === item.tool_type)?.name || item.tool_type }}
                </span>
              </div>

              <!-- Image -->
              <img
                v-if="item.type === 'image'"
                :src="item.image_url || item.thumbnail_url"
                :alt="item.title"
                class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
              />

              <!-- Video poster -->
              <div v-else-if="item.type === 'video'" class="relative w-full h-full">
                <img
                  :src="item.image_url || item.thumbnail_url"
                  :alt="item.title"
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
              <h3 class="font-semibold mb-2 line-clamp-1" style="color: #e8e8f0;">{{ item.title }}</h3>
              <p class="text-sm mb-3 line-clamp-2" style="color: #6b6b8a;">{{ item.prompt }}</p>

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
