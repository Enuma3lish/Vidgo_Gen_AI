<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores'

const { t, tm } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

// ── Real demo data from API ──
const demoImages = ref<Record<string, { before: string; after: string }[]>>({})
const demoLoading = ref(true)

// SMB-focused fallback images (food, products, stores - not luxury items)
const FALLBACK: Record<string, { before: string; after: string }> = {
  try_on:            { before: 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600&q=80', after: 'https://images.unsplash.com/photo-1618354691373-d851c5c3a990?w=600&q=80' },
  background_removal:{ before: 'https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=600&q=80', after: 'https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=600&q=80' },
  room_redesign:     { before: 'https://images.unsplash.com/photo-1554118811-1e0d58224f24?w=600&q=80', after: 'https://images.unsplash.com/photo-1559329007-40df8a9345d8?w=600&q=80' },
  short_video:       { before: 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=600&q=80', after: 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&q=80' },
  product_scene:     { before: 'https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600&q=80', after: 'https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=600&q=80' },
  ai_avatar:         { before: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=600&q=80', after: 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=600&q=80' },
}

function demo(cat: string, idx: 'before' | 'after') {
  const list = demoImages.value[cat]
  if (list && list.length > 0) return idx === 'before' ? list[0].before : list[0].after
  return FALLBACK[cat]?.[idx] || ''
}

const demoCats = ['try_on', 'background_removal', 'room_redesign', 'short_video', 'product_scene']
let pollTimer: ReturnType<typeof setInterval> | null = null

async function loadDemos() {
  const results = await Promise.allSettled(
    demoCats.map(cat =>
      import('@/api/client').then(m => m.default.get(`/api/v1/demo/presets/${cat}?limit=2`))
    )
  )
  results.forEach((r, i) => {
    if (r.status === 'fulfilled' && r.value?.data?.presets?.length) {
      demoImages.value[demoCats[i]] = r.value.data.presets
        .filter((p: any) => p.input_image_url && p.result_image_url)
        .map((p: any) => ({ before: p.input_image_url, after: p.result_image_url }))
    }
  })
  demoLoading.value = false

  // Progressive polling: if some categories are still empty, poll every 60s
  const sparse = demoCats.filter(c => (demoImages.value[c]?.length || 0) < 2)
  if (sparse.length > 0 && !pollTimer) {
    pollTimer = setInterval(async () => {
      await loadDemos()
      const stillSparse = demoCats.filter(c => (demoImages.value[c]?.length || 0) < 2)
      if (stillSparse.length === 0 && pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    }, 60000)
  }
}

// ── All AI Creation Tools (PicCopilot-style grid) ──
const allTools = [
  { id: 'tryOn',           route: '/tools/try-on',             emoji: '👗', color: '#eb2f96', tag: 'Hot' },
  { id: 'aiModelSwap',     route: '/tools/ai-model-swap',      emoji: '🧑‍🎤', color: '#722ed1', tag: 'New' },
  { id: 'fashionReels',    route: '/tools/short-video',        emoji: '🎬', color: '#1677ff', tag: 'Hot' },
  { id: 'productAvatars',  route: '/tools/avatar',             emoji: '🎭', color: '#531dab', tag: '' },
  { id: 'productAnyshoot', route: '/tools/product-scene',      emoji: '📸', color: '#fa8c16', tag: '' },
  { id: 'tryOnAccessories',route: '/tools/try-on-accessories',  emoji: '💍', color: '#c41d7f', tag: 'New' },
  { id: 'aiBackgrounds',   route: '/tools/background-removal', emoji: '🖼️', color: '#13c2c2', tag: '' },
  { id: 'styleClone',      route: '/tools/effects',            emoji: '🎨', color: '#9254de', tag: '' },
  { id: 'removeWatermark', route: '/tools/remove-watermark',   emoji: '💧', color: '#597ef7', tag: '' },
  { id: 'aiTemplates',     route: '/tools/ai-templates',       emoji: '📐', color: '#f5222d', tag: '' },
  { id: 'imageTranslator', route: '/tools/image-translator',   emoji: '🌐', color: '#13c2c2', tag: '' },
  { id: 'aiShadows',       route: '/tools/effects',            emoji: '🌑', color: '#434343', tag: '' },
  { id: 'roomRedesign',    route: '/tools/room-redesign',      emoji: '🏠', color: '#52c41a', tag: '' },
  { id: 'bgRemoval',       route: '/tools/background-removal', emoji: '✂️', color: '#08979c', tag: 'Free' },
]

// Category sections are hardcoded in the template for layout flexibility

// ── Seasonal marketing scenarios ──
const seasons = ref([
  { id: 'spring', active: false },
  { id: 'valentines', active: false },
  { id: 'blackFriday', active: false },
  { id: 'christmas', active: false },
  { id: 'newYear', active: true },
])
const activeSeason = ref('newYear')

function setActiveSeason(id: string) {
  activeSeason.value = id
  seasons.value.forEach(s => s.active = s.id === id)
}

// ── Before/After deep dives ──
const deepDiveDefs = [
  { key: 'tryOn',      route: '/tools/try-on',            cat: 'try_on',            accentColor: '#eb2f96' },
  { key: 'bgRemoval',  route: '/tools/background-removal', cat: 'background_removal', accentColor: '#13c2c2' },
  { key: 'room',       route: '/tools/room-redesign',      cat: 'room_redesign',     accentColor: '#52c41a' },
]

// ── Trust brands ──
const brands = ['WooCommerce', 'Amazon', 'Instagram', 'TikTok', 'Etsy', 'Walmart', 'Shopify', 'eBay']

// ── Success stories ──
const successStories = [
  { id: 'fashionBrand', icon: '👗' },
  { id: 'furnitureBrand', icon: '🛋️' },
  { id: 'techBrand', icon: '💻' },
  { id: 'ebikeBrand', icon: '🚲' },
]

function handleStartCreating() {
  router.push(authStore.isAuthenticated ? '/tools/try-on' : '/auth/register')
}

onMounted(() => { loadDemos() })
onUnmounted(() => { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } })
</script>

<template>
  <div style="background: #ffffff; color: #1F1F1F;">

    <!-- ============================================================
         SECTION 1 — HERO (PicCopilot style)
    ============================================================= -->
    <section class="pt-24 pb-16 md:pt-32 md:pb-24"
      style="background: linear-gradient(180deg, #f0f5ff 0%, #ffffff 100%);">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <div class="max-w-4xl mx-auto">
          <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium mb-6"
            style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);">
            <span class="w-2 h-2 rounded-full animate-pulse" style="background: #1677ff;"></span>
            {{ t('lp.badge') }}
          </div>
          <h1 class="text-4xl md:text-5xl lg:text-6xl font-black leading-tight mb-5" style="color: #1F1F1F;">
            VidGo AI<br>
            <span style="background: linear-gradient(135deg, #1677ff 0%, #722ed1 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
              {{ t('lp.headline') }}
            </span>
          </h1>
          <p class="text-lg md:text-xl max-w-2xl mx-auto mb-4 leading-relaxed" style="color: rgba(0,0,0,0.65);">
            {{ t('lp.sub1') }}
          </p>
          <p class="text-base max-w-xl mx-auto mb-10 font-semibold" style="color: #fa541c;">
            {{ t('lp.sub2') }}
          </p>
          <div class="flex flex-col sm:flex-row items-center justify-center gap-3 mb-8">
            <button @click="handleStartCreating"
              class="inline-flex items-center gap-2 px-8 py-3.5 text-white text-base font-semibold rounded-lg transition-all duration-200 hover:opacity-90 hover:shadow-lg"
              style="background: linear-gradient(135deg, #1677ff, #0958d9); box-shadow: 0 4px 14px rgba(22,119,255,0.4);">
              ⭐ {{ t('lp.ctaPrimary') }}
            </button>
            <RouterLink to="/pricing"
              class="inline-flex items-center gap-2 px-8 py-3.5 text-base font-semibold rounded-lg transition-all duration-200 hover:bg-gray-50"
              style="color: rgba(0,0,0,0.65); border: 1px solid rgba(0,0,0,0.15); background: #ffffff;">
              {{ t('lp.ctaSecondary') }}
            </RouterLink>
          </div>
          <div class="flex flex-wrap items-center justify-center gap-6 text-sm" style="color: rgba(0,0,0,0.45);">
            <span class="flex items-center gap-1.5"><span style="color: #52c41a;">✓</span> {{ t('lp.trust1') }}</span>
            <span class="flex items-center gap-1.5"><span style="color: #52c41a;">✓</span> {{ t('lp.trust2') }}</span>
            <span class="flex items-center gap-1.5"><span style="color: #52c41a;">✓</span> {{ t('lp.trust3') }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 2 — TRUST BAR (Platform logos)
    ============================================================= -->
    <section class="py-10" style="background: #ffffff; border-top: 1px solid rgba(0,0,0,0.06); border-bottom: 1px solid rgba(0,0,0,0.06);">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <p class="text-center text-sm font-medium mb-6" style="color: rgba(0,0,0,0.45);"
          v-html="t('lp.trustBrands')"></p>
        <div class="overflow-hidden">
          <div class="flex items-center gap-12 marquee-track">
            <span v-for="(brand, i) in [...brands, ...brands]" :key="i"
              class="font-bold text-lg whitespace-nowrap flex-shrink-0"
              style="color: rgba(0,0,0,0.2);">{{ brand }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 3 — EXPLORE ALL AI CREATION TOOLS (PicCopilot tool grid)
    ============================================================= -->
    <section class="section-padding" style="background: #ffffff;">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-3xl md:text-4xl font-bold mb-4" style="color: #1F1F1F;">{{ t('lp.sec3Title') }}</h2>
          <p class="text-base md:text-lg max-w-2xl mx-auto" style="color: rgba(0,0,0,0.55);">{{ t('lp.sec3Sub') }}</p>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          <RouterLink v-for="tool in allTools" :key="tool.id" :to="tool.route"
            class="group relative bg-white rounded-2xl overflow-hidden cursor-pointer transition-all duration-300 hover:-translate-y-1 hover:shadow-lg p-5 text-center"
            style="border: 1px solid rgba(0,0,0,0.08);">
            <div v-if="tool.tag" class="absolute top-2 right-2">
              <span class="px-2 py-0.5 rounded text-[10px] font-bold text-white" :style="'background: ' + tool.color">{{ tool.tag }}</span>
            </div>
            <div class="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl mx-auto mb-3 transition-transform duration-300 group-hover:scale-110"
              :style="'background: ' + tool.color + '12;'">
              {{ tool.emoji }}
            </div>
            <div class="font-semibold text-sm mb-1" style="color: #1F1F1F;">{{ t('lp.allTools.' + tool.id + '.name') }}</div>
            <div class="text-xs" style="color: rgba(0,0,0,0.45);">{{ t('lp.allTools.' + tool.id + '.desc') }}</div>
          </RouterLink>
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 4 — GENERATE ENDLESS POSSIBILITIES (Category showcase)
    ============================================================= -->
    <section class="section-padding" style="background: #f7f8fa;">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-3xl md:text-4xl font-bold mb-4" style="color: #1F1F1F;">{{ t('lp.sec4Title') }}</h2>
          <p class="text-base md:text-lg max-w-2xl mx-auto" style="color: rgba(0,0,0,0.55);">{{ t('lp.sec4Sub') }}</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <!-- Card 1: Fashion AI -->
          <div class="rounded-2xl overflow-hidden bg-white transition-all duration-300 hover:-translate-y-1 hover:shadow-lg"
            style="border: 1px solid rgba(0,0,0,0.08);">
            <div class="h-48 overflow-hidden relative">
              <img :src="demo('try_on', 'after') || FALLBACK.try_on.after"
                alt="Fashion AI" class="w-full h-full object-cover" />
              <div class="absolute inset-0" style="background: linear-gradient(to top, rgba(0,0,0,0.5), transparent);"></div>
              <div class="absolute bottom-4 left-4 text-white font-bold text-lg">{{ t('lp.categories.fashionAI') }}</div>
            </div>
            <div class="p-5">
              <p class="text-sm mb-4" style="color: rgba(0,0,0,0.55);">{{ t('lp.categories.fashionAIDesc') }}</p>
              <div class="space-y-2">
                <RouterLink to="/tools/try-on" class="flex items-center gap-2 text-sm font-medium hover:text-blue-600 transition-colors" style="color: rgba(0,0,0,0.65);">
                  <span>👗</span> {{ t('lp.allTools.tryOn.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
                <RouterLink to="/tools/short-video" class="flex items-center gap-2 text-sm font-medium hover:text-blue-600 transition-colors" style="color: rgba(0,0,0,0.65);">
                  <span>🎬</span> {{ t('lp.allTools.fashionReels.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
                <RouterLink to="/tools/avatar" class="flex items-center gap-2 text-sm font-medium hover:text-blue-600 transition-colors" style="color: rgba(0,0,0,0.65);">
                  <span>🎭</span> {{ t('lp.allTools.productAvatars.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
              </div>
            </div>
          </div>
          <!-- Card 2: E-commerce AI -->
          <div class="rounded-2xl overflow-hidden bg-white transition-all duration-300 hover:-translate-y-1 hover:shadow-lg"
            style="border: 1px solid rgba(0,0,0,0.08);">
            <div class="h-48 overflow-hidden relative">
              <img :src="demo('product_scene', 'after') || FALLBACK.product_scene.after"
                alt="E-commerce AI" class="w-full h-full object-cover" />
              <div class="absolute inset-0" style="background: linear-gradient(to top, rgba(0,0,0,0.5), transparent);"></div>
              <div class="absolute bottom-4 left-4 text-white font-bold text-lg">{{ t('lp.categories.ecommerceAI') }}</div>
            </div>
            <div class="p-5">
              <p class="text-sm mb-4" style="color: rgba(0,0,0,0.55);">{{ t('lp.categories.ecommerceAIDesc') }}</p>
              <div class="space-y-2">
                <RouterLink to="/tools/product-scene" class="flex items-center gap-2 text-sm font-medium hover:text-blue-600 transition-colors" style="color: rgba(0,0,0,0.65);">
                  <span>📸</span> {{ t('lp.allTools.productAnyshoot.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
                <RouterLink to="/tools/background-removal" class="flex items-center gap-2 text-sm font-medium hover:text-blue-600 transition-colors" style="color: rgba(0,0,0,0.65);">
                  <span>✂️</span> {{ t('lp.allTools.bgRemoval.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
                <RouterLink to="/tools/effects" class="flex items-center gap-2 text-sm font-medium hover:text-blue-600 transition-colors" style="color: rgba(0,0,0,0.65);">
                  <span>🌑</span> {{ t('lp.allTools.aiShadows.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
              </div>
            </div>
          </div>
          <!-- Card 3: Design & Content AI -->
          <div class="rounded-2xl overflow-hidden bg-white transition-all duration-300 hover:-translate-y-1 hover:shadow-lg"
            style="border: 1px solid rgba(0,0,0,0.08);">
            <div class="h-48 overflow-hidden relative">
              <img :src="demo('room_redesign', 'after') || FALLBACK.room_redesign.after"
                alt="Design AI" class="w-full h-full object-cover" />
              <div class="absolute inset-0" style="background: linear-gradient(to top, rgba(0,0,0,0.5), transparent);"></div>
              <div class="absolute bottom-4 left-4 text-white font-bold text-lg">{{ t('lp.categories.designAI') }}</div>
            </div>
            <div class="p-5">
              <p class="text-sm mb-4" style="color: rgba(0,0,0,0.55);">{{ t('lp.categories.designAIDesc') }}</p>
              <div class="space-y-2">
                <RouterLink to="/tools/room-redesign" class="flex items-center gap-2 text-sm font-medium hover:text-blue-600 transition-colors" style="color: rgba(0,0,0,0.65);">
                  <span>🏠</span> {{ t('lp.allTools.roomRedesign.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
                <RouterLink to="/tools/effects" class="flex items-center gap-2 text-sm font-medium hover:text-blue-600 transition-colors" style="color: rgba(0,0,0,0.65);">
                  <span>🎨</span> {{ t('lp.allTools.styleClone.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
                <RouterLink to="/tools/image-translator" class="flex items-center gap-2 text-sm font-medium hover:text-blue-600 transition-colors" style="color: rgba(0,0,0,0.65);">
                  <span>🌐</span> {{ t('lp.allTools.imageTranslator.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 5 — THE FIRST AI THAT TRULY UNDERSTANDS MARKETING
    ============================================================= -->
    <section class="section-padding" style="background: #ffffff;">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-3xl md:text-4xl font-bold mb-4" style="color: #1F1F1F;">{{ t('lp.sec5Title') }}</h2>
          <p class="text-base md:text-lg max-w-2xl mx-auto" style="color: rgba(0,0,0,0.55);">{{ t('lp.sec5Sub') }}</p>
        </div>
        <!-- Season tabs -->
        <div class="flex flex-wrap items-center justify-center gap-3 mb-10">
          <button v-for="season in seasons" :key="season.id"
            @click="setActiveSeason(season.id)"
            class="px-5 py-2.5 rounded-full text-sm font-medium transition-all duration-200"
            :style="activeSeason === season.id
              ? 'background: #1677ff; color: #ffffff; box-shadow: 0 2px 8px rgba(22,119,255,0.3);'
              : 'background: #f5f5f5; color: rgba(0,0,0,0.65); border: 1px solid rgba(0,0,0,0.08);'">
            {{ t('lp.seasons.' + season.id) }}
          </button>
        </div>
        <!-- Season showcase grid -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div v-for="i in 4" :key="i"
            class="rounded-xl overflow-hidden relative group cursor-pointer transition-all duration-300 hover:shadow-lg"
            style="aspect-ratio: 3/4; background: #f5f5f5;">
            <img :src="demo('product_scene', 'after') || FALLBACK.product_scene.after"
              :alt="'Season showcase ' + i"
              class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
            <div class="absolute inset-0" style="background: linear-gradient(to top, rgba(0,0,0,0.5) 0%, transparent 50%);"></div>
            <div class="absolute bottom-3 left-3 right-3">
              <span class="text-white text-xs font-medium px-2 py-1 rounded" style="background: rgba(0,0,0,0.4); backdrop-filter: blur(4px);">
                {{ t('lp.seasonShowcase') }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 6 — BEFORE/AFTER DEEP DIVES
    ============================================================= -->
    <section class="section-padding" style="background: #f7f8fa;">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-20">
        <div v-for="(feature, i) in deepDiveDefs" :key="feature.key"
          class="flex flex-col lg:flex-row items-center gap-10 md:gap-16"
          :class="i % 2 === 1 ? 'lg:flex-row-reverse' : ''">
          <!-- Before/After image pair -->
          <div class="lg:w-1/2 w-full">
            <div class="grid grid-cols-2 gap-3 rounded-2xl overflow-hidden" style="box-shadow: 0 8px 32px rgba(0,0,0,0.1);">
              <div class="relative overflow-hidden" style="aspect-ratio: 3/4;">
                <img :src="demo(feature.cat, 'before') || FALLBACK[feature.cat]?.before"
                  :alt="t('lp.deepDives.' + feature.key + '.before')" class="w-full h-full object-cover" />
                <div class="absolute top-3 left-3 px-2.5 py-1 rounded text-xs font-bold" style="background: rgba(0,0,0,0.6); color: #ffffff;">Before</div>
              </div>
              <div class="relative overflow-hidden" style="aspect-ratio: 3/4;">
                <img :src="demo(feature.cat, 'after') || FALLBACK[feature.cat]?.after"
                  :alt="t('lp.deepDives.' + feature.key + '.after')" class="w-full h-full object-cover" />
                <div class="absolute top-3 left-3 px-2.5 py-1 rounded text-xs font-bold" :style="'background: ' + feature.accentColor + '; color: #ffffff;'">After</div>
              </div>
            </div>
          </div>
          <!-- Text -->
          <div class="lg:w-1/2 w-full">
            <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold mb-4"
              :style="'background: ' + feature.accentColor + '18; color: ' + feature.accentColor + '; border: 1px solid ' + feature.accentColor + '30;'">
              AI Powered
            </div>
            <h3 class="text-2xl md:text-3xl font-black mb-4" style="color: #1F1F1F;">{{ t('lp.deepDives.' + feature.key + '.title') }}</h3>
            <p class="text-base leading-relaxed mb-8" style="color: rgba(0,0,0,0.65);">{{ t('lp.deepDives.' + feature.key + '.desc') }}</p>
            <RouterLink :to="feature.route"
              class="inline-flex items-center gap-2 px-6 py-3 text-white text-sm font-semibold rounded-lg transition-all duration-200 hover:opacity-90"
              :style="'background: ' + feature.accentColor + ';'">
              {{ t('lp.tryNow') }}
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/></svg>
            </RouterLink>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 7 — IMAGE TRANSLATION & VIDEO DUBBING
    ============================================================= -->
    <section class="section-padding" style="background: #ffffff;">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <!-- Image Translation -->
          <div class="rounded-2xl p-8" style="background: linear-gradient(135deg, #f0f5ff, #e6f7ff); border: 1px solid rgba(22,119,255,0.1);">
            <div class="w-12 h-12 rounded-xl flex items-center justify-center text-2xl mb-4" style="background: rgba(22,119,255,0.1);">🌐</div>
            <h3 class="text-2xl font-bold mb-3" style="color: #1F1F1F;">{{ t('lp.imageTranslation.title') }}</h3>
            <p class="text-sm leading-relaxed mb-6" style="color: rgba(0,0,0,0.65);">{{ t('lp.imageTranslation.desc') }}</p>
            <RouterLink to="/tools/image-translator"
              class="inline-flex items-center gap-2 px-5 py-2.5 text-white text-sm font-semibold rounded-lg transition-all hover:opacity-90"
              style="background: #1677ff;">
              ⭐ {{ t('lp.tryNow') }}
            </RouterLink>
          </div>
          <!-- Video Translation & Dubbing -->
          <div class="rounded-2xl p-8" style="background: linear-gradient(135deg, #f9f0ff, #efdbff); border: 1px solid rgba(114,46,209,0.1);">
            <div class="w-12 h-12 rounded-xl flex items-center justify-center text-2xl mb-4" style="background: rgba(114,46,209,0.1);">📺</div>
            <h3 class="text-2xl font-bold mb-3" style="color: #1F1F1F;">{{ t('lp.videoDubbing.title') }}</h3>
            <p class="text-sm leading-relaxed mb-6" style="color: rgba(0,0,0,0.65);">{{ t('lp.videoDubbing.desc') }}</p>
            <RouterLink to="/tools/short-video"
              class="inline-flex items-center gap-2 px-5 py-2.5 text-white text-sm font-semibold rounded-lg transition-all hover:opacity-90"
              style="background: #722ed1;">
              ⭐ {{ t('lp.tryNow') }}
            </RouterLink>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 8 — TESTIMONIALS (They all use VidGo AI)
    ============================================================= -->
    <section class="section-padding" style="background: #f7f8fa;">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-3xl md:text-4xl font-bold mb-4" style="color: #1F1F1F;">{{ t('lp.sec8Title') }}</h2>
          <p class="text-base md:text-lg max-w-xl mx-auto" style="color: rgba(0,0,0,0.55);">{{ t('lp.sec8Sub') }}</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          <div v-for="(t2, idx) in (tm('lp.testimonials') as any[])" :key="idx"
            class="bg-white rounded-xl p-6 flex flex-col transition-all duration-300 hover:-translate-y-1 hover:shadow-md"
            style="border: 1px solid rgba(0,0,0,0.08);">
            <div class="flex gap-0.5 mb-4">
              <span v-for="s in 5" :key="s" class="text-base" style="color: #faad14;">★</span>
            </div>
            <p class="text-sm leading-relaxed flex-1 mb-5" style="color: rgba(0,0,0,0.65);">&ldquo;{{ t2.text }}&rdquo;</p>
            <div class="pt-4" style="border-top: 1px solid rgba(0,0,0,0.06);">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold text-white"
                  :style="'background: ' + ['#1677ff','#722ed1','#eb2f96','#fa8c16'][idx % 4]">
                  {{ t2.name.charAt(0) }}
                </div>
                <div>
                  <div class="font-semibold text-sm" style="color: #1F1F1F;">{{ t2.name }}</div>
                  <div class="text-xs mt-0.5" style="color: rgba(0,0,0,0.45);">{{ t2.role }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 9 — CUSTOMER SUCCESS STORIES
    ============================================================= -->
    <section class="section-padding" style="background: #ffffff;">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-3xl md:text-4xl font-bold mb-4" style="color: #1F1F1F;">{{ t('lp.sec9Title') }}</h2>
          <p class="text-base md:text-lg max-w-xl mx-auto" style="color: rgba(0,0,0,0.55);">{{ t('lp.sec9Sub') }}</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div v-for="story in successStories" :key="story.id"
            class="group rounded-2xl overflow-hidden bg-white transition-all duration-300 hover:shadow-lg"
            style="border: 1px solid rgba(0,0,0,0.08);">
            <div class="p-6">
              <div class="flex items-center gap-3 mb-4">
                <span class="text-2xl">{{ story.icon }}</span>
                <div>
                  <div class="font-bold text-base" style="color: #1F1F1F;">{{ t('lp.stories.' + story.id + '.brand') }}</div>
                  <div class="text-xs" style="color: rgba(0,0,0,0.45);">{{ t('lp.stories.' + story.id + '.role') }}</div>
                </div>
              </div>
              <h4 class="font-bold text-lg mb-3" style="color: #1F1F1F;">{{ t('lp.stories.' + story.id + '.title') }}</h4>
              <p class="text-sm leading-relaxed mb-4" style="color: rgba(0,0,0,0.55);">{{ t('lp.stories.' + story.id + '.quote') }}</p>
              <button class="inline-flex items-center gap-1 text-sm font-semibold transition-colors hover:opacity-80" style="color: #1677ff;">
                {{ t('lp.readStory') }}
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 10 — STATS (Why Choose VidGo AI)
    ============================================================= -->
    <section class="py-20" style="background: linear-gradient(135deg, #1677ff, #0958d9);">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-2xl md:text-3xl font-bold mb-3" style="color: #ffffff;">{{ t('lp.sec10Title') }}</h2>
          <p class="text-base" style="color: rgba(255,255,255,0.8);">{{ t('lp.sec10Sub') }}</p>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
          <div v-for="(stat, idx) in (tm('lp.stats') as any[])" :key="idx" class="text-center">
            <div class="text-4xl md:text-5xl font-black mb-2" style="color: #ffffff;">{{ stat.value }}</div>
            <div class="text-sm font-medium" style="color: rgba(255,255,255,0.8);">{{ stat.label }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 11 — FINAL CTA
    ============================================================= -->
    <section class="py-20" style="background: linear-gradient(180deg, #f0f5ff 0%, #ffffff 100%);">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 class="text-3xl md:text-5xl font-black mb-5" style="color: #1F1F1F;">{{ t('lp.ctaFinalTitle') }}</h2>
        <p class="text-lg mb-10 max-w-xl mx-auto" style="color: rgba(0,0,0,0.55);">{{ t('lp.ctaFinalSub') }}</p>
        <button @click="handleStartCreating"
          class="inline-flex items-center gap-2 px-10 py-4 font-bold text-white rounded-lg text-base transition-all duration-200 hover:opacity-90"
          style="background: linear-gradient(135deg, #1677ff, #0958d9); box-shadow: 0 4px 16px rgba(22,119,255,0.4);">
          ⭐ {{ t('lp.ctaFinalBtn') }}
        </button>
        <p class="text-sm mt-4" style="color: rgba(0,0,0,0.35);">{{ t('lp.ctaFinalNote') }}</p>
      </div>
    </section>

  </div>
</template>

<style scoped>
.section-padding {
  padding-top: 5rem;
  padding-bottom: 5rem;
}

@keyframes marquee {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

.marquee-track {
  animation: marquee 30s linear infinite;
}
</style>
