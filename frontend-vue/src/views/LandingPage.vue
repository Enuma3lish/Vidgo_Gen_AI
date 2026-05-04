<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores'

const { t, tm, locale } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

// ── Real demo data from API ──
const demoImages = ref<Record<string, { before: string; after: string }[]>>({})
const demoLoading = ref(true)

// Fallback images — shown while real AI results load or as error fallback.
// "before" = realistic input state; "after" = compelling AI-transformed result.
const FALLBACK: Record<string, { before: string; after: string }> = {
  try_on:            { before: 'https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?w=600&q=85', after: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600&q=85' },
  background_removal:{ before: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=85', after: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=85&bg=ffffff' },
  room_redesign:     { before: 'https://images.unsplash.com/photo-1560185893-a55cbc8c57e8?w=600&q=85', after: 'https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?w=600&q=85' },
  short_video:       { before: 'https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=600&q=85', after: 'https://images.unsplash.com/photo-1611162616475-46b635cb6868?w=600&q=85' },
  product_scene:     { before: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=85', after: 'https://images.unsplash.com/photo-1491553895911-0055eca6402d?w=600&q=85' },
  ai_avatar:         { before: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=600&q=85', after: 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=600&q=85' },
}

function demo(cat: string, idx: 'before' | 'after') {
  const list = demoImages.value[cat]
  if (list && list.length > 0) return idx === 'before' ? list[0].before : list[0].after
  return FALLBACK[cat]?.[idx] || ''
}

function fallbackImg(e: Event, cat: string, type: 'before' | 'after') {
  const img = e.target as HTMLImageElement
  const fb = FALLBACK[cat]?.[type]
  if (fb && img.src !== fb) img.src = fb
}

const demoCats = ['try_on', 'background_removal', 'room_redesign', 'short_video', 'product_scene']
let pollTimer: ReturnType<typeof setInterval> | null = null

// Hero interactive demo tabs
const heroDemoTabs = [
  { key: 'product_scene',     label: 'Studio Scene' },
  { key: 'background_removal',label: 'Cutout' },
  { key: 'try_on',            label: 'Try-On' },
  { key: 'room_redesign',     label: 'Room' },
] as const
const activeDemoTab = ref<typeof heroDemoTabs[number]['key']>('product_scene')
let heroTabTimer: ReturnType<typeof setInterval> | null = null

async function loadDemos() {
  const results = await Promise.allSettled(
    demoCats.map(cat =>
      import('@/api/client').then(m => m.default.get(`/api/v1/demo/presets/${cat}?limit=2`))
    )
  )
  results.forEach((r, i) => {
    if (r.status === 'fulfilled' && r.value?.data?.presets?.length) {
      demoImages.value[demoCats[i]] = r.value.data.presets
        .filter((p: any) => p.result_watermarked_url || p.result_image_url || p.thumbnail_url)
        .map((p: any) => ({
          before: p.input_image_url || '',
          after: p.result_watermarked_url || p.result_image_url || p.thumbnail_url || '',
        }))
    }
  })
  demoLoading.value = false

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

interface LandingTool {
  id: string
  route: string
  emoji: string
  color: string
  tag: string
  nameKey?: string
  descKey?: string
}

// ── All AI Creation Tools ──
const allTools: LandingTool[] = [
  { id: 'tryOn',           route: '/tools/try-on',             emoji: '👗', color: '#eb2f96', tag: 'Hot' },
  { id: 'fashionReels',    route: '/tools/short-video',        emoji: '🎬', color: '#1677ff', tag: 'Hot' },
  { id: 'productAvatars',  route: '/tools/avatar',             emoji: '🗣️', color: '#722ed1', tag: 'New' },
  { id: 'productAnyshoot', route: '/tools/product-scene',      emoji: '📸', color: '#fa8c16', tag: '' },
  { id: 'bgRemoval',       route: '/tools/background-removal', emoji: '✂️', color: '#08979c', tag: 'Free' },
  { id: 'roomRedesign',    route: '/tools/room-redesign',      emoji: '🏠', color: '#52c41a', tag: '' },
  { id: 'hdUpscale',       route: '/tools/upscale',            emoji: '🔍', color: '#13c2c2', tag: 'New' },
  { id: 'videoTransform',  route: '/tools/video-transform',    emoji: '🎞️', color: '#2f54eb', tag: 'Pro' },
  { id: 'patternGenerate', route: '/tools/pattern-generate',   emoji: '▦', color: '#f759ab', tag: '' },
  { id: 'imageTranslator', route: '/tools/image-translator',   emoji: '文', color: '#faad14', tag: 'New' },
  {
    id: 'videoDubbing',
    route: '/tools/video-dubbing',
    emoji: '🎙️',
    color: '#13c2c2',
    tag: 'Pro',
    nameKey: 'lp.videoDubbing.title',
    descKey: 'lp.videoDubbing.desc',
  },
]

function toolName(tool: LandingTool): string {
  return t(tool.nameKey || `lp.allTools.${tool.id}.name`)
}

function toolDesc(tool: LandingTool): string {
  return t(tool.descKey || `lp.allTools.${tool.id}.desc`)
}

// ── Seasonal marketing scenarios ──
const seasons = ref([
  { id: 'spring', topics: ['spring', 'seasonal'], active: false },
  { id: 'valentines', topics: ['valentines', 'seasonal', 'holiday'], active: false },
  { id: 'blackFriday', topics: ['black_friday', 'holiday', 'seasonal'], active: false },
  { id: 'christmas', topics: ['christmas', 'holiday'], active: false },
  { id: 'newYear', topics: ['new_year', 'holiday'], active: true },
])
const activeSeason = ref('newYear')
const seasonLoading = ref(true)

// Pre-generated season showcase data from API
interface SeasonItem { url: string; input_url: string; label: string }
const seasonData = ref<Record<string, SeasonItem[]>>({})

function compactLabel(value: string): string {
  return value
    .replace(/\s*\|\s*Scene:.*/i, '')
    .replace(/\s*\|\s*場景[:：].*/g, '')
    .replace(/棚拍產品照[:：]?\s*/g, '')
    .replace(/Studio product photo of\s*/i, '')
    .replace(/，.*$/g, '')
    .replace(/,.*$/g, '')
    .trim()
}

// Map raw English product_name from the backend to a localized, professional
// display name. Falls back to the raw name if no translation exists.
function localizedProductName(rawName: string | undefined | null): string {
  if (!rawName) return ''
  const key = `lp.productNames.${rawName}`
  const translated = t(key)
  // vue-i18n returns the key itself when no translation is found
  return translated && translated !== key ? translated : rawName
}

function seasonLabel(preset: any, seasonId?: string): string {
  const params = preset.input_params || {}
  const isZh = locale.value.startsWith('zh')
  const rawName =
    (isZh ? params.product_name_zh : params.product_name_en) ||
    params.product_name ||
    ''
  const productName = localizedProductName(rawName) || (isZh
    ? preset.title_zh || preset.title_en
    : preset.title_en || preset.title_zh)
  const cleaned = compactLabel(productName || preset.prompt_en || preset.prompt || '')
  const seasonTag = seasonId ? t(`lp.seasons.${seasonId}`) : ''
  if (cleaned && seasonTag) return `${seasonTag} · ${cleaned}`
  return cleaned || seasonTag || t('lp.seasonShowcase')
}

async function loadSeasonPresets(seasonId: string) {
  const season = seasons.value.find(s => s.id === seasonId)
  if (!season || seasonData.value[seasonId]) return
  try {
    const client = (await import('@/api/client')).default
    const topicResults = await Promise.allSettled(
      season.topics.map(topic => client.get(`/api/v1/demo/presets/product_scene?topic=${topic}&limit=4`))
    )
    const seen = new Set<string>()
    const presets = topicResults.flatMap(result =>
      result.status === 'fulfilled' ? (result.value.data?.presets || []) : []
    )
    seasonData.value[seasonId] = presets
      .filter((p: any) => p.result_image_url || p.thumbnail_url)
      .filter((p: any) => {
        const key = p.id || p.result_image_url || p.thumbnail_url
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
      .slice(0, 4)
      .map((p: any) => ({
        url: p.result_watermarked_url || p.result_image_url || p.thumbnail_url || '',
        input_url: p.input_image_url || '',
        label: seasonLabel(p, seasonId),
      }))
  } catch {
    seasonData.value[seasonId] = []
  }
}

async function loadAllSeasonPresets() {
  seasonLoading.value = true
  await Promise.all(seasons.value.map(s => loadSeasonPresets(s.id)))
  const firstAvailable = seasons.value.find(season => (seasonData.value[season.id]?.length || 0) > 0)
  if (firstAvailable && !seasonData.value[activeSeason.value]?.length) {
    setActiveSeason(firstAvailable.id)
  }
  seasonLoading.value = false
}

function setActiveSeason(id: string) {
  activeSeason.value = id
  seasons.value.forEach(s => s.active = s.id === id)
  loadSeasonPresets(id)
}

const availableSeasons = computed(() => {
  return seasons.value
})

const activeSeasonItems = computed(() => {
  return seasonData.value[activeSeason.value] || []
})

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

onMounted(() => {
  loadDemos()
  loadAllSeasonPresets()
  // Auto-rotate hero demo tabs every 4s
  heroTabTimer = setInterval(() => {
    const idx = heroDemoTabs.findIndex(t => t.key === activeDemoTab.value)
    activeDemoTab.value = heroDemoTabs[(idx + 1) % heroDemoTabs.length].key
  }, 4000)
})
onUnmounted(() => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (heroTabTimer) { clearInterval(heroTabTimer); heroTabTimer = null }
})

watch(locale, () => { seasonData.value = {}; loadAllSeasonPresets() })
</script>

<template>
  <div class="commerce-page">

    <!-- ============================================================
            SECTION 1 — HERO (Demo-first SMB layout)
    ============================================================= -->
    <section class="commerce-hero relative pt-24 pb-16 md:pt-28 md:pb-20 overflow-hidden">
      <div class="hero-bg-orb hero-bg-orb-a"></div>
      <div class="hero-bg-orb hero-bg-orb-b"></div>
      <div class="hero-bg-orb hero-bg-orb-c"></div>
      <div class="hero-grid-pattern"></div>

      <div class="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="grid lg:grid-cols-12 gap-10 lg:gap-12 items-center">

          <!-- LEFT: Copy column -->
          <div class="lg:col-span-6 text-center lg:text-left">
            <div class="hero-eyebrow inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold mb-6">
              <span class="w-1.5 h-1.5 rounded-full hero-eyebrow-dot"></span>
              {{ t('lp.badge') }}
            </div>
            <h1 class="hero-headline mb-5">
              <span class="hero-brand-mark">VidGo AI</span>
              <span class="hero-headline-main">{{ t('lp.headline') }}</span>
            </h1>
            <p class="hero-sub mb-6">
              {{ t('lp.sub1') }}
            </p>
            <p class="hero-sub-accent mb-8">
              {{ t('lp.sub2') }}
            </p>
            <div class="flex flex-col sm:flex-row items-center lg:items-start justify-center lg:justify-start gap-3 mb-6">
              <button @click="handleStartCreating" class="hero-cta-primary">
                {{ t('lp.ctaPrimary') }}
                <svg class="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/></svg>
              </button>
              <RouterLink to="/pricing" class="hero-cta-secondary">
                {{ t('lp.ctaSecondary') }}
              </RouterLink>
            </div>
            <div class="flex flex-wrap items-center justify-center lg:justify-start gap-x-5 gap-y-2 text-sm hero-trust">
              <span class="flex items-center gap-1.5"><span class="hero-check">✓</span> {{ t('lp.trust1') }}</span>
              <span class="flex items-center gap-1.5"><span class="hero-check">✓</span> {{ t('lp.trust2') }}</span>
              <span class="flex items-center gap-1.5"><span class="hero-check">✓</span> {{ t('lp.trust3') }}</span>
            </div>
          </div>

          <!-- RIGHT: Interactive before/after demo -->
          <div class="lg:col-span-6">
            <div class="hero-demo-card">
              <div class="hero-demo-card-glow"></div>
              <div class="hero-demo-tabs">
                <button v-for="cat in heroDemoTabs" :key="cat.key"
                  class="hero-demo-tab" :class="{ 'is-active': activeDemoTab === cat.key }"
                  @click="activeDemoTab = cat.key">
                  {{ cat.label }}
                </button>
              </div>
              <div class="hero-demo-stage">
                <div class="hero-demo-pane">
                  <img :src="demo(activeDemoTab, 'before') || FALLBACK[activeDemoTab]?.before" alt="Before" class="hero-demo-img" @error="fallbackImg($event, activeDemoTab, 'before')" />
                  <span class="hero-demo-badge hero-demo-badge-before">BEFORE</span>
                </div>
                <div class="hero-demo-pane">
                  <img :src="demo(activeDemoTab, 'after') || FALLBACK[activeDemoTab]?.after" alt="After" class="hero-demo-img" @error="fallbackImg($event, activeDemoTab, 'after')" />
                  <span class="hero-demo-badge hero-demo-badge-after">AFTER · AI</span>
                </div>
              </div>
              <div class="hero-demo-meta">
                <div class="hero-demo-meta-left">
                  <span class="hero-demo-dot"></span>
                  Generated in seconds
                </div>
                <div class="hero-demo-meta-right">
                  Powered by VidGo AI
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 2 — TRUST BAR (Platform logos)
    ============================================================= -->
    <section class="py-10" style="border-top: 1px solid rgba(255,255,255,0.04); border-bottom: 1px solid rgba(255,255,255,0.04);">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <p class="text-center text-sm font-medium mb-6" style="color: #6b6b8a;"
          v-html="t('lp.trustBrands')"></p>
        <div class="overflow-hidden">
          <div class="flex items-center gap-12 marquee-track">
            <span v-for="(brand, i) in [...brands, ...brands]" :key="i"
              class="font-bold text-lg whitespace-nowrap flex-shrink-0"
              style="color: rgba(255,255,255,0.1);">{{ brand }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 3 — EXPLORE ALL AI CREATION TOOLS
    ============================================================= -->
    <section class="section-padding" style="background: var(--bg-section);">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-3xl md:text-4xl font-bold mb-4" style="color: #f5f5fa;">{{ t('lp.sec3Title') }}</h2>
          <p class="text-base md:text-lg max-w-2xl mx-auto" style="color: #9494b0;">{{ t('lp.sec3Sub') }}</p>
        </div>

        <div class="tool-grid">
          <RouterLink
            v-for="tool in allTools"
            :key="tool.id"
            :to="tool.route"
            class="tool-card group"
            :style="`--tool-color: ${tool.color};`"
          >
            <!-- Colored top accent bar -->
            <div class="tool-card-accent" :style="`background: linear-gradient(90deg, ${tool.color}, ${tool.color}88);`" />

            <!-- Badge -->
            <div v-if="tool.tag" class="tool-badge-wrap">
              <span v-if="tool.tag === 'Hot'"  class="badge-hot">{{ tool.tag }}</span>
              <span v-else-if="tool.tag === 'New'"  class="badge-new">{{ tool.tag }}</span>
              <span v-else-if="tool.tag === 'Free'" class="badge-free">{{ tool.tag }}</span>
              <span v-else class="badge-custom" :style="`background: ${tool.color}22; color: ${tool.color}; border: 1px solid ${tool.color}55;`">{{ tool.tag }}</span>
            </div>

            <!-- Icon -->
            <div
              class="tool-icon"
              :style="`background: ${tool.color}18; border: 1.5px solid ${tool.color}30;`"
            >
              <span class="tool-emoji">{{ tool.emoji }}</span>
            </div>

            <!-- Text -->
            <div class="tool-name">{{ toolName(tool) }}</div>
            <div class="tool-desc">{{ toolDesc(tool) }}</div>

            <!-- Arrow (appears on hover) -->
            <div class="tool-arrow">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </div>
          </RouterLink>
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 4 — GENERATE ENDLESS POSSIBILITIES (Category showcase)
    ============================================================= -->
    <section class="section-padding" style="background: var(--bg-section-alt);">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-3xl md:text-4xl font-bold mb-4" style="color: #f5f5fa;">{{ t('lp.sec4Title') }}</h2>
          <p class="text-base md:text-lg max-w-2xl mx-auto" style="color: #9494b0;">{{ t('lp.sec4Sub') }}</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <!-- Card 1: Fashion AI -->
          <div class="rounded-2xl overflow-hidden transition-all duration-300 hover:-translate-y-1"
            style="background: var(--bg-card); border: 1px solid var(--border-subtle);">
            <div class="h-48 overflow-hidden relative">
              <img :src="demo('try_on', 'after') || FALLBACK.try_on.after"
                alt="Fashion AI" class="w-full h-full object-cover" @error="fallbackImg($event, 'try_on', 'after')" />
              <div class="absolute inset-0" style="background: linear-gradient(to top, #1c1c1c 0%, transparent 60%);"></div>
              <div class="absolute bottom-4 left-4 text-white font-bold text-lg">{{ t('lp.categories.fashionAI') }}</div>
            </div>
            <div class="p-5">
              <p class="text-sm mb-4" style="color: #9494b0;">{{ t('lp.categories.fashionAIDesc') }}</p>
              <div class="space-y-2">
                <RouterLink to="/tools/try-on" class="flex items-center gap-2 text-sm font-medium transition-colors" style="color: #c4c4d8;" @mouseenter="($event.target as HTMLElement).style.color='#f59e0b'" @mouseleave="($event.target as HTMLElement).style.color='#a8a29e'">
                  <span>👗</span> {{ t('lp.allTools.tryOn.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
                <RouterLink to="/tools/short-video" class="flex items-center gap-2 text-sm font-medium transition-colors" style="color: #c4c4d8;" @mouseenter="($event.target as HTMLElement).style.color='#f59e0b'" @mouseleave="($event.target as HTMLElement).style.color='#a8a29e'">
                  <span>🎬</span> {{ t('lp.allTools.fashionReels.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
                <RouterLink to="/tools/avatar" class="flex items-center gap-2 text-sm font-medium transition-colors" style="color: #c4c4d8;" @mouseenter="($event.target as HTMLElement).style.color='#f59e0b'" @mouseleave="($event.target as HTMLElement).style.color='#a8a29e'">
                  <span>🗣️</span> {{ t('lp.allTools.productAvatars.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
              </div>
            </div>
          </div>
          <!-- Card 2: E-commerce AI -->
          <div class="rounded-2xl overflow-hidden transition-all duration-300 hover:-translate-y-1"
            style="background: var(--bg-card); border: 1px solid var(--border-subtle);">
            <div class="h-48 overflow-hidden relative">
              <img :src="demo('product_scene', 'after') || FALLBACK.product_scene.after"
                alt="E-commerce AI" class="w-full h-full object-cover" @error="fallbackImg($event, 'product_scene', 'after')" />
              <div class="absolute inset-0" style="background: linear-gradient(to top, #1c1c1c 0%, transparent 60%);"></div>
              <div class="absolute bottom-4 left-4 text-white font-bold text-lg">{{ t('lp.categories.ecommerceAI') }}</div>
            </div>
            <div class="p-5">
              <p class="text-sm mb-4" style="color: #9494b0;">{{ t('lp.categories.ecommerceAIDesc') }}</p>
              <div class="space-y-2">
                <RouterLink to="/tools/product-scene" class="flex items-center gap-2 text-sm font-medium transition-colors" style="color: #c4c4d8;" @mouseenter="($event.target as HTMLElement).style.color='#f59e0b'" @mouseleave="($event.target as HTMLElement).style.color='#a8a29e'">
                  <span>📸</span> {{ t('lp.allTools.productAnyshoot.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
                <RouterLink to="/tools/background-removal" class="flex items-center gap-2 text-sm font-medium transition-colors" style="color: #c4c4d8;" @mouseenter="($event.target as HTMLElement).style.color='#f59e0b'" @mouseleave="($event.target as HTMLElement).style.color='#a8a29e'">
                  <span>✂️</span> {{ t('lp.allTools.bgRemoval.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
                <RouterLink to="/tools/upscale" class="flex items-center gap-2 text-sm font-medium transition-colors" style="color: #c4c4d8;" @mouseenter="($event.target as HTMLElement).style.color='#f59e0b'" @mouseleave="($event.target as HTMLElement).style.color='#a8a29e'">
                  <span>🔍</span> {{ t('lp.allTools.hdUpscale.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
                <RouterLink to="/tools/pattern-generate" class="flex items-center gap-2 text-sm font-medium transition-colors" style="color: #c4c4d8;" @mouseenter="($event.target as HTMLElement).style.color='#f59e0b'" @mouseleave="($event.target as HTMLElement).style.color='#a8a29e'">
                  <span>▦</span> {{ t('lp.allTools.patternGenerate.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
              </div>
            </div>
          </div>
          <!-- Card 3: Design & Content AI -->
          <div class="rounded-2xl overflow-hidden transition-all duration-300 hover:-translate-y-1"
            style="background: var(--bg-card); border: 1px solid var(--border-subtle);">
            <div class="h-48 overflow-hidden relative">
              <img :src="demo('room_redesign', 'after') || FALLBACK.room_redesign.after"
                alt="Design AI" class="w-full h-full object-cover" @error="fallbackImg($event, 'room_redesign', 'after')" />
              <div class="absolute inset-0" style="background: linear-gradient(to top, #1c1c1c 0%, transparent 60%);"></div>
              <div class="absolute bottom-4 left-4 text-white font-bold text-lg">{{ t('lp.categories.designAI') }}</div>
            </div>
            <div class="p-5">
              <p class="text-sm mb-4" style="color: #9494b0;">{{ t('lp.categories.designAIDesc') }}</p>
              <div class="space-y-2">
                <RouterLink to="/tools/room-redesign" class="flex items-center gap-2 text-sm font-medium transition-colors" style="color: #c4c4d8;" @mouseenter="($event.target as HTMLElement).style.color='#f59e0b'" @mouseleave="($event.target as HTMLElement).style.color='#a8a29e'">
                  <span>🏠</span> {{ t('lp.allTools.roomRedesign.name') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
                <RouterLink to="/gallery" class="flex items-center gap-2 text-sm font-medium transition-colors" style="color: #c4c4d8;" @mouseenter="($event.target as HTMLElement).style.color='#f59e0b'" @mouseleave="($event.target as HTMLElement).style.color='#a8a29e'">
                  <span>🖼️</span> {{ t('gallery.title') }}
                  <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </RouterLink>
                <RouterLink to="/tools/video-transform" class="flex items-center gap-2 text-sm font-medium transition-colors" style="color: #c4c4d8;" @mouseenter="($event.target as HTMLElement).style.color='#f59e0b'" @mouseleave="($event.target as HTMLElement).style.color='#a8a29e'">
                  <span>🎞️</span> {{ t('lp.allTools.videoTransform.name') }}
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
    <section class="section-padding" style="background: var(--bg-section);">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-3xl md:text-4xl font-bold mb-4" style="color: #f5f5fa;">{{ t('lp.sec5Title') }}</h2>
          <p class="text-base md:text-lg max-w-2xl mx-auto" style="color: #9494b0;">{{ t('lp.sec5Sub') }}</p>
        </div>
        <!-- Season tabs -->
        <div class="flex flex-wrap items-center justify-center gap-3 mb-10">
          <button v-for="season in availableSeasons" :key="season.id"
            @click="setActiveSeason(season.id)"
            class="px-5 py-2.5 rounded-full text-sm font-medium transition-all duration-200"
            :style="activeSeason === season.id
              ? 'background: #f59e0b; color: #0a0a0a; font-weight: 600; box-shadow: 0 4px 16px rgba(245,158,11,0.30);'
              : 'background: var(--bg-card); color: var(--text-secondary); border: 1px solid var(--border-light);'">
            {{ t('lp.seasons.' + season.id) }}
          </button>
        </div>
        <!-- Season tagline -->
        <p class="text-center text-sm md:text-base max-w-2xl mx-auto mb-8" style="color: #b8b8d0;">
          {{ t('lp.seasonsTagline.' + activeSeason) }}
        </p>
        <!-- Season showcase grid -->
        <div v-if="seasonLoading && activeSeasonItems.length === 0" class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div v-for="idx in 4" :key="idx"
            class="rounded-xl overflow-hidden relative"
            style="aspect-ratio: 3/4; background: var(--bg-card); border: 1px solid var(--border-subtle);">
            <div class="absolute inset-0 animate-pulse" style="background: linear-gradient(90deg, transparent, rgba(255,255,255,0.06), transparent);"></div>
          </div>
        </div>
        <div v-else-if="activeSeasonItems.length > 0" class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div v-for="(item, idx) in activeSeasonItems" :key="activeSeason + '-' + idx"
            class="rounded-xl overflow-hidden relative group cursor-pointer transition-all duration-300 hover:-translate-y-1"
            style="aspect-ratio: 3/4; background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <img :src="item.url"
              :alt="item.label"
              class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
              @error="($event.target as HTMLImageElement).src = FALLBACK.product_scene.after" />
            <div class="absolute inset-0" style="background: linear-gradient(to top, rgba(0,0,0,0.7) 0%, transparent 50%);"></div>
            <div class="absolute bottom-3 left-3 right-3">
              <span class="text-white text-xs font-medium px-2.5 py-1 rounded-md" style="background: rgba(255,255,255,0.1); backdrop-filter: blur(8px);">
                {{ item.label }}
              </span>
            </div>
          </div>
        </div>
        <div v-else class="rounded-xl p-8 text-center" style="background: #141420; border: 1px solid rgba(255,255,255,0.06); color: #9494b0;">
          {{ t('lp.seasonUnavailable') }}
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 6 — BEFORE/AFTER DEEP DIVES
    ============================================================= -->
    <section class="section-padding" style="background: var(--bg-section-alt);">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-20">
        <div v-for="(feature, i) in deepDiveDefs" :key="feature.key"
          class="flex flex-col lg:flex-row items-center gap-10 md:gap-16"
          :class="i % 2 === 1 ? 'lg:flex-row-reverse' : ''">
          <!-- Before/After image pair -->
          <div class="lg:w-1/2 w-full">
            <div class="grid grid-cols-2 gap-3 rounded-2xl overflow-hidden" style="box-shadow: 0 8px 40px rgba(0,0,0,0.5);">
              <div class="relative overflow-hidden" style="aspect-ratio: 3/4;">
                <img :src="demo(feature.cat, 'before') || FALLBACK[feature.cat]?.before"
                  :alt="t('lp.deepDives.' + feature.key + '.before')" class="w-full h-full object-cover"
                  @error="fallbackImg($event, feature.cat, 'before')" />
                <div class="absolute top-3 left-3 px-2.5 py-1 rounded-md text-xs font-bold" style="background: rgba(0,0,0,0.6); backdrop-filter: blur(4px); color: #ffffff;">Before</div>
              </div>
              <div class="relative overflow-hidden" style="aspect-ratio: 3/4;">
                <img :src="demo(feature.cat, 'after') || FALLBACK[feature.cat]?.after"
                  :alt="t('lp.deepDives.' + feature.key + '.after')" class="w-full h-full object-cover"
                  @error="fallbackImg($event, feature.cat, 'after')" />
                <div class="absolute top-3 left-3 px-2.5 py-1 rounded-md text-xs font-bold" :style="'background: ' + feature.accentColor + '; color: #ffffff;'">After</div>
              </div>
            </div>
          </div>
          <!-- Text -->
          <div class="lg:w-1/2 w-full">
            <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold mb-4"
              :style="'background: ' + feature.accentColor + '15; color: ' + feature.accentColor + '; border: 1px solid ' + feature.accentColor + '30;'">
              AI Powered
            </div>
            <h3 class="text-2xl md:text-3xl font-black mb-4" style="color: #f5f5fa;">{{ t('lp.deepDives.' + feature.key + '.title') }}</h3>
            <p class="text-base leading-relaxed mb-8" style="color: #9494b0;">{{ t('lp.deepDives.' + feature.key + '.desc') }}</p>
            <RouterLink :to="feature.route"
              class="inline-flex items-center gap-2 px-6 py-3 text-white text-sm font-semibold rounded-lg transition-all duration-200 hover:opacity-90"
              :style="'background: ' + feature.accentColor + '; box-shadow: 0 4px 16px ' + feature.accentColor + '40;'">
              {{ t('lp.tryNow') }}
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/></svg>
            </RouterLink>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 8 — TESTIMONIALS
    ============================================================= -->
    <section class="section-padding" style="background: var(--bg-section-alt);">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-3xl md:text-4xl font-bold mb-4" style="color: #f5f5fa;">{{ t('lp.sec8Title') }}</h2>
          <p class="text-base md:text-lg max-w-xl mx-auto" style="color: #9494b0;">{{ t('lp.sec8Sub') }}</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          <div v-for="(t2, idx) in (tm('lp.testimonials') as any[])" :key="idx"
            class="rounded-xl p-6 flex flex-col transition-all duration-300 hover:-translate-y-1"
            style="background: var(--bg-card); border: 1px solid var(--border-subtle);">
            <div class="flex gap-0.5 mb-4">
              <span v-for="s in 5" :key="s" class="text-base" style="color: #f59e0b;">★</span>
            </div>
            <p class="text-sm leading-relaxed flex-1 mb-5" style="color: #9494b0;">&ldquo;{{ t2.text }}&rdquo;</p>
            <div class="pt-4" style="border-top: 1px solid rgba(255,255,255,0.06);">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold text-white"
                  :style="'background: ' + ['#1677ff','#6366f1','#eb2f96','#fa8c16'][idx % 4]">
                  {{ t2.name.charAt(0) }}
                </div>
                <div>
                  <div class="font-semibold text-sm" style="color: #e8e8f0;">{{ t2.name }}</div>
                  <div class="text-xs mt-0.5" style="color: #6b6b8a;">{{ t2.role }}</div>
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
    <section class="section-padding" style="background: var(--bg-section);">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-3xl md:text-4xl font-bold mb-4" style="color: #f5f5fa;">{{ t('lp.sec9Title') }}</h2>
          <p class="text-base md:text-lg max-w-xl mx-auto" style="color: #9494b0;">{{ t('lp.sec9Sub') }}</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div v-for="story in successStories" :key="story.id"
            class="group rounded-2xl overflow-hidden transition-all duration-300 hover:-translate-y-1"
            style="background: var(--bg-card); border: 1px solid var(--border-subtle);">
            <div class="p-6">
              <div class="flex items-center gap-3 mb-4">
                <span class="text-2xl">{{ story.icon }}</span>
                <div>
                  <div class="font-bold text-base" style="color: #e8e8f0;">{{ t('lp.stories.' + story.id + '.brand') }}</div>
                  <div class="text-xs" style="color: #6b6b8a;">{{ t('lp.stories.' + story.id + '.role') }}</div>
                </div>
              </div>
              <h4 class="font-bold text-lg mb-3" style="color: #f5f5fa;">{{ t('lp.stories.' + story.id + '.title') }}</h4>
              <p class="text-sm leading-relaxed mb-4" style="color: #9494b0;">{{ t('lp.stories.' + story.id + '.quote') }}</p>
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
    <section class="py-20 relative overflow-hidden">
      <div class="absolute inset-0" style="background: linear-gradient(135deg, #0f1830, #141420);"></div>
      <div class="absolute inset-0 bg-mesh"></div>
      <div class="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-2xl md:text-3xl font-bold mb-3" style="color: #f5f5fa;">{{ t('lp.sec10Title') }}</h2>
          <p class="text-base" style="color: #9494b0;">{{ t('lp.sec10Sub') }}</p>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
          <div v-for="(stat, idx) in (tm('lp.stats') as any[])" :key="idx" class="text-center">
            <div class="text-4xl md:text-5xl font-black mb-2 gradient-text">{{ stat.value }}</div>
            <div class="text-sm font-medium" style="color: #9494b0;">{{ stat.label }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         SECTION 11 — FINAL CTA
    ============================================================= -->
    <section class="py-20 relative overflow-hidden">
      <div class="absolute inset-0" style="background: radial-gradient(ellipse at center, rgba(22,119,255,0.08) 0%, #09090b 70%);"></div>
      <div class="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 class="text-3xl md:text-5xl font-black mb-5" style="color: #f5f5fa;">{{ t('lp.ctaFinalTitle') }}</h2>
        <p class="text-lg mb-10 max-w-xl mx-auto" style="color: #9494b0;">{{ t('lp.ctaFinalSub') }}</p>
        <button @click="handleStartCreating"
          class="btn-accent px-10 py-4 font-bold text-base">
          {{ t('lp.ctaFinalBtn') }}
        </button>
        <p class="text-sm mt-4" style="color: #6b6b8a;">{{ t('lp.ctaFinalNote') }}</p>
      </div>
    </section>

  </div>
</template>

<style scoped>
/* ================================================================
   VidGo AI — Premium Dark AI Landing Page
   ================================================================ */

.section-padding {
  padding-top: 5rem;
  padding-bottom: 5rem;
}

/* ── Tool Grid ──────────────────────────────────────────────────── */
.tool-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}
@media (min-width: 640px)  { .tool-grid { grid-template-columns: repeat(3, 1fr); gap: 1.25rem; } }
@media (min-width: 900px)  { .tool-grid { grid-template-columns: repeat(4, 1fr); gap: 1.5rem; } }

/* ── Tool Card ──────────────────────────────────────────────────── */
.tool-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 1.375rem 1.375rem 1.125rem;
  border-radius: 18px;
  overflow: hidden;
  background: rgba(12, 12, 22, 0.85);
  border: 1px solid rgba(100, 80, 200, 0.12);
  cursor: pointer;
  text-decoration: none;
  transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;
  min-height: 160px;
  backdrop-filter: blur(16px);
}
.tool-card::before {
  content: '';
  position: absolute; inset: 0;
  border-radius: 18px;
  background: radial-gradient(ellipse at top left, color-mix(in srgb, var(--tool-color) 8%, transparent), transparent 60%);
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
}
.tool-card:hover {
  transform: translateY(-6px);
  background: rgba(16, 16, 30, 0.95);
  border-color: color-mix(in srgb, var(--tool-color) 50%, transparent);
  box-shadow:
    0 20px 60px rgba(0,0,0,0.6),
    0 0 0 1px color-mix(in srgb, var(--tool-color) 25%, transparent),
    0 0 40px color-mix(in srgb, var(--tool-color) 10%, transparent);
}
.tool-card:hover::before { opacity: 1; }

.tool-card-accent {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  opacity: 0.9;
  border-radius: 18px 18px 0 0;
}

.tool-badge-wrap {
  position: absolute;
  top: 0.75rem; right: 0.75rem;
}
.badge-custom {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.03em;
}

.tool-icon {
  width: 52px; height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center; justify-content: center;
  margin-bottom: 0.875rem;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
  flex-shrink: 0;
}
.tool-card:hover .tool-icon {
  transform: scale(1.1);
  box-shadow: 0 0 20px color-mix(in srgb, var(--tool-color) 35%, transparent);
}
.tool-emoji { font-size: 1.5rem; line-height: 1; }

.tool-name {
  font-size: 0.9375rem;
  font-weight: 650;
  color: #e8e8f8;
  margin-bottom: 0.35rem;
  line-height: 1.3;
}
.tool-desc {
  font-size: 0.8125rem;
  color: #6868a0;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
  transition: color 0.2s ease;
}
.tool-card:hover .tool-desc { color: #a0a0c8; }

.tool-arrow {
  position: absolute;
  bottom: 0.875rem; right: 0.875rem;
  color: var(--tool-color);
  opacity: 0; transform: translateX(-6px);
  transition: opacity 0.22s ease, transform 0.22s ease;
}
.tool-card:hover .tool-arrow { opacity: 0.9; transform: translateX(0); }

/* ── Marquee ──────────────────────────────────────────────────── */
@keyframes marquee {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}
.marquee-track { animation: marquee 30s linear infinite; }

/* ================================================================
   DARK AI PREMIUM THEME
   ================================================================ */

.commerce-page {
  background: #07070f;
  color: #e8e8f8;
  --bg-page:        #07070f;
  --bg-section:     #09090f;
  --bg-section-alt: #0c0c18;
  --bg-card:        #0f0f1e;
  --bg-card-hover:  #141428;
  --bg-elevated:    #1a1a2e;
  --text-primary:   #e8e8f8;
  --text-secondary: #9898c0;
  --text-muted:     #5a5a80;
  --border-subtle:  rgba(100, 80, 220, 0.10);
  --border-light:   rgba(100, 80, 220, 0.16);
  --border-medium:  rgba(100, 80, 220, 0.24);
}

/* Reset text colors for dark theme */
.commerce-page,
.commerce-page p,
.commerce-page span,
.commerce-page li { color: inherit; }
.commerce-page h1, .commerce-page h2, .commerce-page h3,
.commerce-page h4, .commerce-page h5, .commerce-page h6 { color: #e8e8f8; }
.commerce-page a { color: inherit; }

/* Section backgrounds */
.commerce-page section { background: var(--bg-section) !important; }
.commerce-page section:nth-of-type(even) { background: var(--bg-section-alt) !important; }

/* Restore inline dark-friendly colors */
.commerce-page [style*="color: #f5f5fa"],
.commerce-page [style*="color: #e8e8f0"],
.commerce-page [style*="color: #c4c4d8"] { color: #e8e8f8 !important; }
.commerce-page [style*="color: #9494b0"],
.commerce-page [style*="color: #b8b8d0"] { color: #9898c0 !important; }
.commerce-page [style*="color: #6b6b8a"] { color: #6060a0 !important; }

/* Keep already-dark inline backgrounds as-is */
.commerce-page [style*="background: #141420"],
.commerce-page [style*="background: #0f0f17"],
.commerce-page [style*="background: #09090b"] {
  background: var(--bg-section-alt) !important;
  border-color: var(--border-subtle) !important;
}

/* Gradient text for stats & highlights */
.commerce-page :deep(.gradient-text) {
  background: linear-gradient(135deg, #f59e0b 0%, #a855f7 55%, #06b6d4 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.commerce-page :deep(.btn-secondary) {
  border-color: rgba(120,100,255,0.28);
  color: #d0d0f0;
  background: rgba(120,100,255,0.06);
}
.commerce-page :deep(.btn-secondary:hover) {
  border-color: #f59e0b;
  color: #f59e0b;
  background: rgba(245,158,11,0.06);
}

.commerce-page :deep(.bg-mesh) { display: block; }

/* ── Hero Section ─────────────────────────────────────────────── */
.commerce-hero {
  min-height: 700px;
  background: #07070f;
  border-bottom: 1px solid rgba(100, 80, 220, 0.08);
  position: relative;
  overflow: hidden;
}

/* ── Animated Aurora Orbs ─────────────────────────────────────── */
.hero-bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  pointer-events: none;
  z-index: 0;
}
.hero-bg-orb-a {
  width: 650px; height: 650px;
  top: -200px; left: -200px;
  background: radial-gradient(circle, rgba(124, 58, 237, 0.45), rgba(99, 102, 241, 0.25), transparent 65%);
  animation: orb-drift-a 14s ease-in-out infinite;
}
.hero-bg-orb-b {
  width: 600px; height: 600px;
  bottom: -200px; right: -200px;
  background: radial-gradient(circle, rgba(6, 182, 212, 0.35), rgba(16, 185, 129, 0.18), transparent 65%);
  animation: orb-drift-b 16s ease-in-out infinite;
}
.hero-bg-orb-c {
  width: 400px; height: 400px;
  top: 40%; left: 50%;
  background: radial-gradient(circle, rgba(245, 158, 11, 0.12), transparent 65%);
  animation: orb-drift-c 20s ease-in-out infinite;
}

@keyframes orb-drift-a {
  0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.55; }
  40%       { transform: translate(60px, 40px) scale(1.08); opacity: 0.65; }
  70%       { transform: translate(-30px, 70px) scale(0.93); opacity: 0.45; }
}
@keyframes orb-drift-b {
  0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.5; }
  35%       { transform: translate(-50px, -40px) scale(1.1); opacity: 0.6; }
  65%       { transform: translate(40px, -60px) scale(0.9); opacity: 0.4; }
}
@keyframes orb-drift-c {
  0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.4; }
  50%       { transform: translate(-50%, -50%) scale(1.3); opacity: 0.2; }
}

/* ── Animated dot-grid ────────────────────────────────────────── */
.hero-grid-pattern {
  position: absolute; inset: 0; z-index: 0;
  pointer-events: none;
  background-image:
    radial-gradient(circle, rgba(120, 100, 255, 0.35) 1px, transparent 1px);
  background-size: 36px 36px;
  mask-image: radial-gradient(ellipse 80% 70% at 50% 50%, black 20%, transparent 90%);
  animation: grid-fade 8s ease-in-out infinite;
}
@keyframes grid-fade {
  0%, 100% { opacity: 0.3; }
  50%       { opacity: 0.55; }
}

/* ── Hero Eyebrow Badge ───────────────────────────────────────── */
.hero-eyebrow {
  background: rgba(124, 58, 237, 0.14);
  color: #c4b5fd;
  border: 1px solid rgba(124, 58, 237, 0.30);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
.hero-eyebrow-dot {
  background: #a78bfa;
  box-shadow: 0 0 0 4px rgba(124, 58, 237, 0.22), 0 0 10px rgba(167, 139, 250, 0.5);
  animation: pulse-dot 2s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { transform: scale(1); opacity: 1; }
  50%       { transform: scale(1.5); opacity: 0.5; }
}

/* ── Hero Headline ────────────────────────────────────────────── */
.hero-headline {
  font-family: 'Syne', system-ui, sans-serif;
  font-weight: 800;
  line-height: 1.05;
  color: #f0f0fa;
  display: flex; flex-direction: column; gap: 6px;
}
.hero-headline-main {
  font-size: clamp(2.25rem, 5vw, 3.75rem);
  color: #f0f0fa;
}

.commerce-page .hero-brand-mark {
  display: inline-block;
  font-size: clamp(1.1rem, 1.6vw, 1.35rem);
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: linear-gradient(135deg, #f59e0b 0%, #a855f7 50%, #06b6d4 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
  margin-bottom: 4px;
  filter: drop-shadow(0 0 12px rgba(168, 85, 247, 0.35));
}

.hero-sub {
  font-size: 1.125rem;
  line-height: 1.65;
  color: #7878a8;
  max-width: 32rem;
}
.hero-sub-accent {
  font-size: 0.95rem;
  font-weight: 600;
  color: #c4b5fd;
  max-width: 32rem;
}

/* ── Hero CTAs ────────────────────────────────────────────────── */
.hero-cta-primary {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 14px 32px;
  font-size: 0.95rem; font-weight: 700;
  color: #ffffff;
  background: linear-gradient(135deg, #f59e0b 0%, #ea580c 100%);
  border-radius: 10px;
  border: none;
  box-shadow: 0 12px 32px rgba(245, 158, 11, 0.35), 0 0 0 1px rgba(245,158,11,0.2), inset 0 1px 0 rgba(255,255,255,0.2);
  transition: transform .18s ease, box-shadow .18s ease, filter .18s ease;
  cursor: pointer;
}
.hero-cta-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 18px 44px rgba(245, 158, 11, 0.45), 0 0 24px rgba(245,158,11,0.2);
  filter: brightness(1.08);
}

.hero-cta-secondary {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 14px 28px;
  font-size: 0.95rem; font-weight: 600;
  color: #c0c0e8;
  background: rgba(100, 80, 220, 0.10);
  border: 1.5px solid rgba(100, 80, 220, 0.28);
  border-radius: 10px;
  backdrop-filter: blur(12px);
  transition: all .18s ease;
}
.hero-cta-secondary:hover {
  border-color: rgba(167, 139, 250, 0.55);
  color: #f0f0fa;
  background: rgba(100, 80, 220, 0.18);
  box-shadow: 0 6px 24px rgba(124, 58, 237, 0.18);
}

.hero-trust { color: #5050a0; }
.hero-check {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 999px;
  background: rgba(16, 185, 129, 0.15);
  color: #10b981; font-weight: 800;
  box-shadow: 0 0 8px rgba(16,185,129,0.2);
}

/* ── Demo Card — glassmorphism ────────────────────────────────── */
.hero-demo-card {
  position: relative;
  background: rgba(10, 10, 22, 0.75);
  border: 1px solid rgba(100, 80, 220, 0.20);
  border-radius: 24px;
  box-shadow:
    0 32px 80px -20px rgba(0, 0, 0, 0.8),
    0 0 60px rgba(124, 58, 237, 0.08),
    inset 0 1px 0 rgba(255,255,255,0.06);
  padding: 18px;
  overflow: hidden;
  backdrop-filter: blur(24px);
}
.hero-demo-card::before {
  content: '';
  position: absolute; inset: -1px;
  border-radius: 24px;
  padding: 1px;
  background: linear-gradient(135deg, rgba(124,58,237,0.55) 0%, rgba(6,182,212,0.30) 50%, transparent 75%);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
          mask-composite: exclude;
  pointer-events: none;
}
.hero-demo-card-glow {
  position: absolute;
  inset: -30px;
  background: radial-gradient(ellipse at 50% 0%, rgba(124,58,237,0.15), transparent 65%);
  pointer-events: none; z-index: 0;
}

.hero-demo-tabs {
  display: flex; gap: 5px;
  padding: 4px;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid rgba(100, 80, 220, 0.12);
  border-radius: 11px;
  margin-bottom: 14px;
  overflow-x: auto;
  position: relative; z-index: 1;
}
.hero-demo-tab {
  flex: 1;
  padding: 8px 12px;
  font-size: 0.8rem; font-weight: 600;
  color: #5050a0;
  background: transparent;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all .2s ease;
  white-space: nowrap;
}
.hero-demo-tab:hover { color: #b0b0e0; background: rgba(100,80,220,0.08); }
.hero-demo-tab.is-active {
  background: rgba(124, 58, 237, 0.22);
  color: #d4c0ff;
  box-shadow: 0 2px 10px rgba(124,58,237,0.22), 0 0 0 1px rgba(124,58,237,0.28);
}

.hero-demo-stage {
  display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
  position: relative; z-index: 1;
}
.hero-demo-pane {
  position: relative;
  aspect-ratio: 1 / 1;
  border-radius: 14px;
  overflow: hidden;
  background: rgba(8, 8, 18, 0.6);
  border: 1px solid rgba(100, 80, 220, 0.14);
}
.hero-demo-img {
  width: 100%; height: 100%;
  object-fit: cover; display: block;
  transition: opacity .35s ease, transform .5s ease;
}
.hero-demo-pane:hover .hero-demo-img { transform: scale(1.04); }
.hero-demo-badge {
  position: absolute; top: 10px; left: 10px;
  padding: 4px 9px;
  font-size: 0.65rem; font-weight: 800;
  letter-spacing: 0.08em;
  border-radius: 6px;
  backdrop-filter: blur(10px);
}
.hero-demo-badge-before {
  background: rgba(0, 0, 0, 0.65);
  color: #c0c0e8;
  border: 1px solid rgba(255,255,255,0.08);
}
.hero-demo-badge-after {
  background: linear-gradient(135deg, #7c3aed, #06b6d4);
  color: #ffffff;
  box-shadow: 0 4px 14px rgba(124, 58, 237, 0.45);
}

.hero-demo-meta {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 14px; padding: 0 4px;
  font-size: 0.78rem; color: #505090;
  position: relative; z-index: 1;
}
.hero-demo-meta-left { display: inline-flex; align-items: center; gap: 8px; font-weight: 600; }
.hero-demo-meta-right { font-weight: 500; opacity: 0.6; }
.hero-demo-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.18), 0 0 10px rgba(16,185,129,0.45);
  animation: pulse-dot 1.6s ease-in-out infinite;
}

@media (max-width: 1024px) { .hero-demo-card { margin-top: 8px; } }
@media (max-width: 768px) {
  .commerce-hero { min-height: 0; }
  .hero-headline-main { font-size: 2rem; }
  .hero-demo-pane { aspect-ratio: 4 / 5; }
}
</style>
