<script setup lang="ts">
import { ref, computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { generationApi } from '@/api/generation'

const { t, locale } = useI18n()

// Helper for localized content
const isZh = computed(() => locale.value.startsWith('zh'))

// ============================================
// SECTION 1: HERO - Stats with i18n
// ============================================
const stats = computed(() => [
  { value: '10K+', label: t('landing.stats.users'), color: 'purple' },
  { value: '80%', label: t('landing.stats.timeSaved'), color: 'cyan' },
  { value: '3x', label: t('landing.stats.conversion'), color: 'pink' }
])

// ============================================
// SECTION 2: FEATURES with i18n
// ============================================
const features = computed(() => [
  { id: 'ai', icon: '✨', gradient: 'blue', title: t('landing.features.ai.title'), desc: t('landing.features.ai.desc') },
  { id: 'fast', icon: '⚡', gradient: 'orange', title: t('landing.features.fast.title'), desc: t('landing.features.fast.desc') },
  { id: 'target', icon: '🎯', gradient: 'green', title: t('landing.features.target.title'), desc: t('landing.features.target.desc') },
  { id: 'data', icon: '📈', gradient: 'pink', title: t('landing.features.data.title'), desc: t('landing.features.data.desc') },
  { id: 'lang', icon: '🌐', gradient: 'cyan', title: t('landing.features.lang.title'), desc: t('landing.features.lang.desc') },
  { id: 'team', icon: '👥', gradient: 'red', title: t('landing.features.team.title'), desc: t('landing.features.team.desc') }
])

// ============================================
// SECTION 3: HOW IT WORKS with i18n
// ============================================
const steps = computed(() => [
  { num: '01', title: t('landing.howItWorks.step1.title'), desc: t('landing.howItWorks.step1.desc'), color: 'cyan' },
  { num: '02', title: t('landing.howItWorks.step2.title'), desc: t('landing.howItWorks.step2.desc'), color: 'purple' },
  { num: '03', title: t('landing.howItWorks.step3.title'), desc: t('landing.howItWorks.step3.desc'), color: 'purple' },
  { num: '04', title: t('landing.howItWorks.step4.title'), desc: t('landing.howItWorks.step4.desc'), color: 'pink' }
])

// ============================================
// SECTION 4: EXAMPLES with i18n
// ============================================
const categories = computed(() => [
  { key: 'all', label: t('landing.examples.categories.all') },
  { key: 'ecommerce', label: t('landing.examples.categories.ecommerce') },
  { key: 'social', label: t('landing.examples.categories.social') },
  { key: 'brand', label: t('landing.examples.categories.brand') },
  { key: 'app', label: t('landing.examples.categories.app') },
  { key: 'promo', label: t('landing.examples.categories.promo') },
  { key: 'service', label: t('landing.examples.categories.service') }
])
const activeCategory = ref('all')

// Video modal state
const showVideoModal = ref(false)
const currentVideo = ref<{ title: string; video: string } | null>(null)

function openVideo(example: { title: string; video?: string }) {
  if (example.video) {
    currentVideo.value = { title: example.title, video: example.video }
    showVideoModal.value = true
  }
}

function closeVideo() {
  showVideoModal.value = false
  currentVideo.value = null
}

// Examples loaded from API
const examples = ref<any[]>([])
const isLoadingExamples = ref(false)

// Fallback examples if API fails
const fallbackExamples = computed(() => [
  { id: 'ex1', category: 'ecommerce', label: t('landing.examples.categories.ecommerce'), duration: isZh.value ? '15 秒' : '15s', title: isZh.value ? '電商產品廣告' : 'E-commerce Product Ad', desc: isZh.value ? '適合電商平台的產品展示影片' : 'Product showcase videos for e-commerce platforms', thumb: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&h=400&fit=crop', video: 'https://videos.pexels.com/video-files/5585432/5585432-sd_640_360_30fps.mp4' },
  { id: 'ex2', category: 'social', label: t('landing.examples.categories.social'), duration: isZh.value ? '10 秒' : '10s', title: isZh.value ? '社群媒體短影片' : 'Social Media Short Video', desc: isZh.value ? 'Instagram、TikTok 專用的吸睛短片' : 'Eye-catching shorts for Instagram & TikTok', thumb: 'https://images.unsplash.com/photo-1611162616305-c69b3fa7fbe0?w=600&h=400&fit=crop', video: 'https://videos.pexels.com/video-files/4571295/4571295-sd_640_360_25fps.mp4' },
  { id: 'ex3', category: 'brand', label: t('landing.examples.categories.brand'), duration: isZh.value ? '30 秒' : '30s', title: isZh.value ? '品牌形象影片' : 'Brand Image Video', desc: isZh.value ? '展現企業價值與品牌故事' : 'Showcase company values and brand story', thumb: 'https://images.unsplash.com/photo-1552664730-d307ca884978?w=600&h=400&fit=crop', video: 'https://videos.pexels.com/video-files/3129671/3129671-sd_640_360_30fps.mp4' },
  { id: 'ex4', category: 'app', label: t('landing.examples.categories.app'), duration: isZh.value ? '20 秒' : '20s', title: isZh.value ? 'App 推廣影片' : 'App Promo Video', desc: isZh.value ? '突顯應用程式核心功能' : 'Highlight app core features', thumb: 'https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?w=600&h=400&fit=crop', video: 'https://videos.pexels.com/video-files/5752729/5752729-sd_640_360_30fps.mp4' },
  { id: 'ex5', category: 'promo', label: t('landing.examples.categories.promo'), duration: isZh.value ? '12 秒' : '12s', title: isZh.value ? '促銷活動影片' : 'Promotional Video', desc: isZh.value ? '限時優惠與促銷活動宣傳' : 'Limited-time offers and promotions', thumb: 'https://images.unsplash.com/photo-1607083206869-4c7672e72a8a?w=600&h=400&fit=crop', video: 'https://videos.pexels.com/video-files/6774226/6774226-sd_640_360_30fps.mp4' },
  { id: 'ex6', category: 'service', label: t('landing.examples.categories.service'), duration: isZh.value ? '25 秒' : '25s', title: isZh.value ? '服務介紹影片' : 'Service Introduction', desc: isZh.value ? '專業服務展示與說明' : 'Professional service showcase', thumb: 'https://images.unsplash.com/photo-1556761175-5973dc0f32e7?w=600&h=400&fit=crop', video: 'https://videos.pexels.com/video-files/3209828/3209828-sd_640_360_25fps.mp4' }
])

// Load examples from API
async function loadExamples() {
  isLoadingExamples.value = true
  try {
    const response = await generationApi.getExamples('video')
    if (response.examples && response.examples.length > 0) {
      // Transform API examples to landing page format
      examples.value = response.examples.map((ex: any, idx: number) => {
        // Map to categories based on style or index
        const categoryMap: Record<string, string> = {
          'anime': 'social',
          'ghibli': 'brand',
          'clay': 'app',
          'pixar': 'promo',
          'watercolor': 'service',
          'nature': 'ecommerce'
        }
        const category = categoryMap[ex.style] || ['ecommerce', 'social', 'brand', 'app', 'promo', 'service'][idx % 6]
        const categoryLabels: Record<string, string> = {
          'ecommerce': t('landing.examples.categories.ecommerce'),
          'social': t('landing.examples.categories.social'),
          'brand': t('landing.examples.categories.brand'),
          'app': t('landing.examples.categories.app'),
          'promo': t('landing.examples.categories.promo'),
          'service': t('landing.examples.categories.service')
        }

        return {
          id: ex.id || `ex${idx}`,
          category,
          label: categoryLabels[category],
          duration: isZh.value ? '5 秒' : '5s',
          title: isZh.value ? (ex.title_zh || ex.title) : (ex.title || ex.title_zh),
          desc: isZh.value ? (ex.prompt_zh || ex.prompt || '') : (ex.prompt || ex.prompt_zh || ''),
          thumb: ex.thumbnail_url || ex.before || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&h=400&fit=crop',
          video: ex.after || ex.video_url
        }
      })
    } else {
      examples.value = fallbackExamples.value
    }
  } catch (error) {
    console.error('Failed to load examples:', error)
    examples.value = fallbackExamples.value
  } finally {
    isLoadingExamples.value = false
  }
}

// Examples are initialized via the locale watch with { immediate: true }

const filteredExamples = computed(() => {
  if (activeCategory.value === 'all') return examples.value
  return examples.value.filter(e => e.category === activeCategory.value)
})

// ============================================
// SECTION 5: COMPARISON with i18n
// ============================================
const traditionalItems = computed(() => isZh.value
  ? ['需要專業團隊', '製作週期 2-4 週', '成本高昂 $5000+', '修改困難且耗時', '需要專業設備', '人力成本高']
  : ['Requires professional team', '2-4 weeks production', 'High cost $5000+', 'Difficult revisions', 'Professional equipment needed', 'High labor costs']
)

const vidgoAiItems = computed(() => isZh.value
  ? ['無需專業技能', '3 分鐘快速完成', '月費 $49 起', '隨時調整優化', '線上即可操作', 'AI 自動化處理']
  : ['No professional skills needed', 'Complete in 3 minutes', 'Starting at $49/month', 'Adjust anytime', 'Online operation', 'AI automation']
)

// ============================================
// SECTION 6: TESTIMONIALS with i18n
// ============================================
const testimonials = computed(() => isZh.value ? [
  { name: '陳建華', title: '行銷總監', company: '數位行銷公司', quote: 'VIDGO 大幅提升了我們的廣告製作效率。原本需要數週的工作，現在只需幾分鐘就能完成。' },
  { name: '林雅婷', title: '創意總監', company: '品牌策略公司', quote: 'AI 生成的影片質量超出預期，客戶都對我們的效率和創意讚不絕口。' },
  { name: '王大明', title: '執行長', company: '電商平台', quote: '使用 VIDGO 後，我們的廣告轉換率提升了 3 倍。這真的是革命性的工具。' },
  { name: '張美玲', title: '社群經理', company: '新創公司', quote: '作為小團隊，我們沒有預算請專業團隊製作影片。VIDGO 解決了這個問題。' },
  { name: '李俊傑', title: '數位行銷專員', company: '廣告代理商', quote: '多語言支援功能非常實用，我們現在能夠服務全球客戶。' },
  { name: '黃淑芬', title: '產品經理', company: 'SaaS 公司', quote: '數據分析功能幫助我們持續優化廣告策略，可以即時看到什麼效果好。' }
] : [
  { name: 'John Chen', title: 'Marketing Director', company: 'Digital Marketing Co.', quote: 'VIDGO has dramatically improved our ad production efficiency. Work that used to take weeks now completes in minutes.' },
  { name: 'Lisa Lin', title: 'Creative Director', company: 'Brand Strategy Firm', quote: 'The AI-generated video quality exceeded expectations. Clients are impressed by our efficiency and creativity.' },
  { name: 'David Wang', title: 'CEO', company: 'E-commerce Platform', quote: 'After using VIDGO, our ad conversion rate increased 3x. This is truly a revolutionary tool.' },
  { name: 'Mary Chang', title: 'Social Media Manager', company: 'Startup', quote: 'As a small team, we didn\'t have budget for professional video production. VIDGO solved this problem.' },
  { name: 'Jack Lee', title: 'Digital Marketing Specialist', company: 'Ad Agency', quote: 'The multi-language support feature is incredibly useful. We can now serve global clients.' },
  { name: 'Sophie Huang', title: 'Product Manager', company: 'SaaS Company', quote: 'The analytics feature helps us continuously optimize ad strategies with real-time insights.' }
])

// ============================================
// SECTION 7: PRICING with i18n
// ============================================
const plans = computed(() => isZh.value ? [
  { id: 'starter', name: '入門版', price: 165, original: 329, features: ['每月 10 個影片', '720p 高清畫質', '基礎 AI 模板', '免費音樂庫', '社群媒體格式', '電子郵件支援'], featured: false },
  { id: 'pro', name: '專業版', price: 325, original: 649, features: ['每月 50 個影片', '1080p 全高清畫質', '進階 AI 模板', '完整音樂庫', '所有平台格式', '優先客服支援', '品牌客製化', '團隊協作 (5人)'], featured: true, badge: t('landing.pricing.mostPopular') },
  { id: 'enterprise', name: '企業版', price: 550, original: 1099, features: ['無限制影片', '4K 超高清畫質', '自訂 AI 模型', '版權音樂庫', '多品牌管理', '專屬客戶經理', 'API 整合', '無限團隊成員'], featured: false }
] : [
  { id: 'starter', name: 'Starter', price: 165, original: 329, features: ['10 videos/month', '720p HD quality', 'Basic AI templates', 'Free music library', 'Social media formats', 'Email support'], featured: false },
  { id: 'pro', name: 'Pro', price: 325, original: 649, features: ['50 videos/month', '1080p Full HD', 'Advanced AI templates', 'Full music library', 'All platform formats', 'Priority support', 'Brand customization', 'Team (5 members)'], featured: true, badge: t('landing.pricing.mostPopular') },
  { id: 'enterprise', name: 'Enterprise', price: 550, original: 1099, features: ['Unlimited videos', '4K Ultra HD', 'Custom AI models', 'Licensed music', 'Multi-brand management', 'Dedicated manager', 'API integration', 'Unlimited team'], featured: false }
])

// ============================================
// SECTION 8: FAQ with i18n
// ============================================
const faqs = ref([] as { q: string; a: string; open: boolean }[])

// Initialize FAQs based on locale
const initFaqs = () => {
  faqs.value = isZh.value ? [
    { q: 'VIDGO 是如何運作的？', a: 'VIDGO 使用先進的 AI 技術自動分析您上傳的素材和需求，然後生成專業的影片廣告。只需上傳您的產品圖片或影片，選擇風格模板，AI 就會完成其餘工作。', open: false },
    { q: '我需要具備影片製作經驗嗎？', a: '不需要任何經驗！VIDGO 專為所有人設計。我們直觀的介面和 AI 工具讓影片製作像上傳照片和點擊按鈕一樣簡單。', open: false },
    { q: '生成一個影片需要多長時間？', a: '大多數影片在 1-5 分鐘內生成，取決於複雜度和長度。短社群媒體片段通常約 1 分鐘，較長的品牌影片可能需要 5 分鐘。', open: false },
    { q: '我可以自訂影片的風格和內容嗎？', a: '當然可以！您可以自訂模板、顏色、字體、音樂和文字。付費用戶還可以使用自訂提示詞獲得更個性化的結果。', open: false },
    { q: '支援哪些影片格式和尺寸？', a: '我們支援所有主流格式，包括 MP4、MOV 和 WebM。尺寸包括 16:9 (YouTube)、9:16 (TikTok/Reels)、1:1 (Instagram) 和 4:5 (Facebook)。', open: false },
    { q: '免費試用包含哪些功能？', a: '免費試用包含 5 次帶浮水印的影片生成，可存取基礎模板和 720p 輸出品質。這是訂閱前體驗我們 AI 能力的好方法。', open: false },
    { q: '如何收費？可以隨時取消嗎？', a: '我們提供月訂閱方案，無長期合約。您可以隨時升級、降級或取消。首月享半價優惠，並提供 7 天全額退款保證。', open: false },
    { q: '我的數據和影片內容安全嗎？', a: '是的，安全是我們的首要任務。所有數據都經過加密，安全儲存，絕不與第三方共享。您保留內容的完全所有權。', open: false }
  ] : [
    { q: 'How does VIDGO work?', a: 'VIDGO uses advanced AI technology to automatically analyze your uploaded materials and requirements, then generates professional video ads. Simply upload your product images or videos, select a style template, and AI does the rest.', open: false },
    { q: 'Do I need video production experience?', a: 'No experience needed! VIDGO is designed for everyone. Our intuitive interface and AI tools make video creation as simple as uploading photos and clicking buttons.', open: false },
    { q: 'How long does it take to generate a video?', a: 'Most videos are generated within 1-5 minutes, depending on complexity and length. Short social media clips take about 1 minute, while longer brand videos may take 5 minutes.', open: false },
    { q: 'Can I customize the video style and content?', a: 'Absolutely! You can customize templates, colors, fonts, music, and text. Paid users can also use custom prompts for more personalized results.', open: false },
    { q: 'What video formats and sizes are supported?', a: 'We support all major formats including MP4, MOV, and WebM. Sizes include 16:9 (YouTube), 9:16 (TikTok/Reels), 1:1 (Instagram), and 4:5 (Facebook).', open: false },
    { q: 'What\'s included in the free trial?', a: 'The free trial includes 5 watermarked video generations, access to basic templates, and 720p output quality. It\'s a great way to experience our AI capabilities before subscribing.', open: false },
    { q: 'How does billing work? Can I cancel anytime?', a: 'We offer monthly subscriptions with no long-term contracts. You can upgrade, downgrade, or cancel anytime. First month is 50% off with a 7-day full refund guarantee.', open: false },
    { q: 'Is my data and video content safe?', a: 'Yes, security is our top priority. All data is encrypted, stored securely, and never shared with third parties. You retain full ownership of your content.', open: false }
  ]
}

// Watch for locale changes
import { watch } from 'vue'
watch(locale, () => {
  initFaqs()
  loadExamples() // Reload examples with correct localization
}, { immediate: true })

function toggleFaq(index: number) {
  faqs.value[index].open = !faqs.value[index].open
}
</script>

<template>
  <div class="min-h-screen">
    <!-- ============================================
         SECTION 1: HERO
         ============================================ -->
    <section class="relative pt-32 pb-24 overflow-hidden">
      <!-- Background effects -->
      <div class="absolute inset-0 bg-gradient-to-b from-primary-500/10 to-transparent" />
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary-500/5 rounded-full blur-3xl" />

      <div class="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <!-- Badge -->
        <div class="badge mb-6 mx-auto w-fit">
          <span class="text-lg">✨</span>
          <span>{{ t('landing.badge') }}</span>
          <span class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
        </div>

        <!-- Headline -->
        <h1 class="text-4xl md:text-6xl lg:text-7xl font-bold mb-6">
          <span class="gradient-text">{{ t('landing.headline1') }}</span><br>
          <span class="text-white">{{ t('landing.headline2') }}</span>
        </h1>

        <!-- Subtitle -->
        <p class="text-xl text-gray-400 mb-4 max-w-2xl mx-auto">
          {{ t('landing.subtitle') }}
        </p>

        <!-- Highlight -->
        <p class="text-lg mb-8">
          <span class="gradient-text-highlight font-semibold">{{ t('landing.highlight') }}</span>
        </p>

        <!-- CTAs -->
        <div class="flex flex-wrap justify-center gap-4 mb-12">
          <RouterLink to="/auth/register" class="btn-primary text-lg px-8 py-4">
            <span class="mr-2">✨</span>
            {{ t('landing.tryFree') }}
          </RouterLink>
          <button class="btn-secondary text-lg px-8 py-4">
            <span class="mr-2">▶</span>
            {{ t('landing.watchDemo') }}
          </button>
        </div>

        <!-- Stats -->
        <div class="flex justify-center gap-8 md:gap-16">
          <div v-for="stat in stats" :key="stat.label" class="card-glass px-6 py-4">
            <div class="stat-value" :class="stat.color">{{ stat.value }}</div>
            <div class="text-sm text-gray-400">{{ stat.label }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================
         SECTION 2: FEATURES
         ============================================ -->
    <section class="py-20">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <!-- Section Header -->
        <div class="text-center mb-12">
          <div class="badge mb-4 mx-auto w-fit">
            <span class="w-2 h-2 bg-primary-500 rounded-full"></span>
            <span>{{ isZh ? '功能特色' : 'Features' }}</span>
          </div>
          <h2 class="section-title">
            {{ t('landing.features.title') }}<span class="gradient-text">{{ t('landing.features.titleHighlight') }}</span>
          </h2>
          <p class="section-subtitle mx-auto">
            {{ t('landing.features.subtitle') }}
          </p>
        </div>

        <!-- Feature Cards Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div v-for="feature in features" :key="feature.id" class="card-feature group transition-all duration-300">
            <!-- Gradient Bar -->
            <div class="gradient-bar" :class="feature.gradient"></div>

            <!-- Icon -->
            <div class="icon-circle mb-4" :class="feature.gradient">
              <span>{{ feature.icon }}</span>
            </div>

            <!-- Content -->
            <h3 class="text-xl font-semibold text-white mb-2">{{ feature.title }}</h3>
            <p class="text-gray-400">{{ feature.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================
         SECTION 3: HOW IT WORKS
         ============================================ -->
    <section class="py-20 bg-dark-800/50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <!-- Section Header -->
        <div class="text-center mb-16">
          <div class="badge mb-4 mx-auto w-fit">
            <span>✨</span>
            <span>{{ t('landing.howItWorks.badge') }}</span>
          </div>
          <h2 class="section-title">
            {{ t('landing.howItWorks.title') }}<span class="gradient-text">{{ t('landing.howItWorks.titleHighlight') }}</span>
          </h2>
          <p class="section-subtitle mx-auto">
            {{ t('landing.howItWorks.subtitle') }}
          </p>
        </div>

        <!-- Timeline -->
        <div class="max-w-3xl mx-auto">
          <div v-for="(step, idx) in steps" :key="step.num" class="flex items-start gap-8 mb-8">
            <!-- Circle -->
            <div class="flex flex-col items-center">
              <div
                class="timeline-circle"
                :style="{
                  background: step.color === 'cyan' ? 'linear-gradient(135deg, #06b6d4, #0891b2)' :
                              step.color === 'purple' ? 'linear-gradient(135deg, #8b5cf6, #7c3aed)' :
                              'linear-gradient(135deg, #ec4899, #db2777)'
                }"
              >
                {{ step.num }}
              </div>
              <div v-if="idx < steps.length - 1" class="timeline-line"></div>
            </div>

            <!-- Content -->
            <div class="flex-1 pt-3">
              <h3 class="text-xl font-semibold text-white mb-2">{{ step.title }}</h3>
              <p class="text-gray-400">{{ step.desc }}</p>
            </div>
          </div>
        </div>

        <!-- CTA -->
        <div class="text-center mt-12">
          <RouterLink to="/auth/register" class="btn-primary text-lg px-8 py-4">
            {{ t('landing.tryFree') }} →
          </RouterLink>
        </div>
      </div>
    </section>

    <!-- ============================================
         SECTION 4: EXAMPLES GALLERY
         ============================================ -->
    <section class="py-20">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <!-- Section Header -->
        <div class="text-center mb-12">
          <div class="badge mb-4 mx-auto w-fit">
            <span>{{ t('landing.examples.badge') }}</span>
          </div>
          <h2 class="section-title">{{ t('landing.examples.title') }}</h2>
          <p class="section-subtitle mx-auto">
            {{ t('landing.examples.subtitle') }}
          </p>
        </div>

        <!-- Category Tabs -->
        <div class="flex flex-wrap justify-center gap-3 mb-8">
          <button
            v-for="cat in categories"
            :key="cat.key"
            @click="activeCategory = cat.key"
            class="category-tab"
            :class="{ 'active': activeCategory === cat.key }"
          >
            {{ cat.label }}
          </button>
        </div>

        <!-- Examples Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="example in filteredExamples"
            :key="example.id"
            class="card overflow-hidden group cursor-pointer hover:scale-[1.02] transition-transform"
            @click="openVideo(example)"
          >
            <!-- Thumbnail -->
            <div class="relative aspect-video overflow-hidden rounded-xl mb-4">
              <img :src="example.thumb" :alt="example.title" class="w-full h-full object-cover" />
              <!-- Category Badge -->
              <span class="absolute top-3 left-3 px-3 py-1 bg-blue-500/90 text-white text-xs rounded-full">
                ✨ {{ example.label }}
              </span>
              <!-- Duration Badge -->
              <span class="absolute top-3 right-3 px-2 py-1 bg-black/60 text-white text-xs rounded">
                {{ example.duration }}
              </span>
              <!-- Play Overlay -->
              <div class="absolute inset-0 bg-black/30 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                <div class="w-12 h-12 bg-white/90 rounded-full flex items-center justify-center">
                  <span class="text-dark-900 text-xl ml-1">▶</span>
                </div>
              </div>
            </div>
            <!-- Content -->
            <h3 class="text-lg font-semibold text-white mb-1">{{ example.title }}</h3>
            <p class="text-gray-400 text-sm">{{ example.desc }}</p>
          </div>
        </div>

        <!-- View More -->
        <div class="text-center mt-8">
          <button class="btn-outline">{{ t('landing.examples.viewMore') }}</button>
        </div>
      </div>
    </section>

    <!-- ============================================
         SECTION 5: COMPARISON
         ============================================ -->
    <section class="py-20 bg-dark-800/50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <!-- Section Header -->
        <div class="text-center mb-12">
          <div class="badge mb-4 mx-auto w-fit">
            <span>{{ t('landing.comparison.badge') }}</span>
          </div>
          <h2 class="section-title">
            {{ t('landing.comparison.title') }}<span class="gradient-text">{{ t('landing.comparison.titleHighlight') }}</span>
          </h2>
          <p class="section-subtitle mx-auto">
            {{ t('landing.comparison.subtitle') }}
          </p>
        </div>

        <!-- Comparison Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto mb-12">
          <!-- Traditional -->
          <div class="card bg-dark-800/80">
            <h3 class="text-xl font-semibold text-white mb-6">{{ t('landing.comparison.traditional') }}</h3>
            <ul class="space-y-3">
              <li v-for="item in traditionalItems" :key="item" class="flex items-center gap-3 text-gray-400">
                <span class="text-red-400">❌</span>
                {{ item }}
              </li>
            </ul>
          </div>

          <!-- VIDGO AI -->
          <div class="pricing-card featured relative">
            <span class="absolute -top-3 right-4 badge-featured px-3 py-1 text-sm rounded-full">{{ t('landing.comparison.recommend') }}</span>
            <h3 class="text-xl font-semibold text-white mb-6">{{ t('landing.comparison.aiWay') }}</h3>
            <ul class="space-y-3">
              <li v-for="item in vidgoAiItems" :key="item" class="flex items-center gap-3 text-gray-300">
                <span class="text-green-400">✅</span>
                {{ item }}
              </li>
            </ul>
          </div>
        </div>

        <!-- Stats -->
        <div class="flex justify-center gap-8 md:gap-16">
          <div class="text-center">
            <div class="stat-value purple">95%</div>
            <div class="text-sm text-gray-400">{{ t('landing.comparison.statTimeSaved') }}</div>
          </div>
          <div class="text-center">
            <div class="stat-value cyan">90%</div>
            <div class="text-sm text-gray-400">{{ t('landing.comparison.statCostReduced') }}</div>
          </div>
          <div class="text-center">
            <div class="stat-value pink">3x</div>
            <div class="text-sm text-gray-400">{{ t('landing.comparison.statEfficiency') }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================
         SECTION 6: TESTIMONIALS
         ============================================ -->
    <section class="py-20">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <!-- Section Header -->
        <div class="text-center mb-12">
          <div class="badge mb-4 mx-auto w-fit">
            <span>{{ t('landing.testimonials.badge') }}</span>
          </div>
          <h2 class="section-title">
            {{ t('landing.testimonials.title') }}<span class="gradient-text">{{ t('landing.testimonials.titleHighlight') }}</span>{{ t('landing.testimonials.titleEnd') }}
          </h2>
          <p class="section-subtitle mx-auto">
            {{ t('landing.testimonials.subtitle') }}
          </p>
        </div>

        <!-- Testimonial Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
          <div v-for="testimonial in testimonials" :key="testimonial.name" class="card">
            <!-- Quote Icon -->
            <div class="text-3xl text-primary-500/30 mb-4">"</div>
            <!-- Stars -->
            <div class="flex gap-1 mb-3">
              <span v-for="i in 5" :key="i" class="text-yellow-400">⭐</span>
            </div>
            <!-- Quote -->
            <p class="text-gray-300 mb-4">{{ testimonial.quote }}</p>
            <!-- Author -->
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-primary-500/20 rounded-full flex items-center justify-center text-primary-400 font-bold">
                {{ testimonial.name[0] }}
              </div>
              <div>
                <div class="font-medium text-white">{{ testimonial.name }}</div>
                <div class="text-sm text-gray-400">{{ testimonial.title }} · {{ testimonial.company }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Stats -->
        <div class="flex flex-wrap justify-center gap-8 md:gap-16">
          <div class="text-center">
            <div class="stat-value white">4.9/5</div>
            <div class="text-sm text-gray-400">{{ t('landing.testimonials.avgRating') }}</div>
          </div>
          <div class="text-center">
            <div class="stat-value purple">10K+</div>
            <div class="text-sm text-gray-400">{{ t('landing.testimonials.activeUsers') }}</div>
          </div>
          <div class="text-center">
            <div class="stat-value cyan">500K+</div>
            <div class="text-sm text-gray-400">{{ t('landing.testimonials.generatedVideos') }}</div>
          </div>
          <div class="text-center">
            <div class="stat-value pink">98%</div>
            <div class="text-sm text-gray-400">{{ t('landing.testimonials.satisfaction') }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================
         SECTION 7: PRICING
         ============================================ -->
    <section class="py-20 bg-dark-800/50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <!-- Section Header -->
        <div class="text-center mb-12">
          <div class="badge mb-4 mx-auto w-fit">
            <span>⭐</span>
            <span>{{ t('landing.pricing.badge') }}</span>
          </div>
          <h2 class="section-title">
            {{ t('landing.pricing.title') }}<span class="gradient-text">{{ t('landing.pricing.titleHighlight') }}</span>
          </h2>
          <p class="section-subtitle mx-auto">
            {{ t('landing.pricing.subtitle') }}
          </p>
        </div>

        <!-- Pricing Cards -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          <div
            v-for="plan in plans"
            :key="plan.id"
            class="pricing-card"
            :class="{ 'featured': plan.featured }"
          >
            <!-- Badge -->
            <div v-if="plan.badge" class="badge-featured px-3 py-1 text-sm rounded-full mb-4 inline-block">
              {{ plan.badge }}
            </div>

            <!-- Name -->
            <h3 class="text-xl font-semibold text-white mb-2">{{ plan.name }}</h3>

            <!-- Price -->
            <div class="mb-6">
              <span class="pricing-price">NT${{ plan.price }}</span>
              <span class="text-gray-400">{{ t('landing.pricing.perMonth') }}</span>
              <div class="text-sm text-gray-500 line-through">{{ t('landing.pricing.originalPrice') }} NT${{ plan.original }}</div>
            </div>

            <!-- Features -->
            <ul class="space-y-3 mb-8">
              <li v-for="f in plan.features" :key="f" class="flex items-center gap-2 text-gray-300">
                <span class="text-cyan-400">✓</span>
                {{ f }}
              </li>
            </ul>

            <!-- CTA -->
            <RouterLink
              :to="plan.featured ? '/auth/register' : '/pricing'"
              :class="plan.featured ? 'btn-primary w-full' : 'btn-secondary w-full'"
            >
              {{ plan.featured ? t('landing.pricing.startNow') : t('landing.pricing.learnMore') }}
            </RouterLink>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================
         SECTION 8: FAQ
         ============================================ -->
    <section class="py-20">
      <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <!-- Section Header -->
        <div class="text-center mb-12">
          <div class="badge mb-4 mx-auto w-fit">
            <span>⊙</span>
            <span>{{ t('landing.faq.badge') }}</span>
          </div>
          <h2 class="section-title">
            {{ t('landing.faq.title') }}<span class="gradient-text">{{ t('landing.faq.titleHighlight') }}</span>
          </h2>
          <p class="section-subtitle mx-auto">
            {{ t('landing.faq.subtitle') }}
          </p>
        </div>

        <!-- FAQ Accordion -->
        <div class="space-y-2">
          <div v-for="(faq, idx) in faqs" :key="idx" class="faq-item">
            <div class="faq-question" @click="toggleFaq(idx)">
              <span class="font-medium text-white">{{ faq.q }}</span>
              <span class="text-gray-400 transition-transform" :class="{ 'rotate-180': faq.open }">▼</span>
            </div>
            <div v-show="faq.open" class="faq-answer">
              {{ faq.a }}
            </div>
          </div>
        </div>

        <!-- Support CTA -->
        <div class="mt-8 p-6 card-glass text-center">
          <p class="text-white mb-4">{{ t('landing.faq.moreQuestions') }}</p>
          <button class="btn-secondary">{{ t('landing.faq.contactSupport') }}</button>
        </div>
      </div>
    </section>

    <!-- ============================================
         SECTION 9: FINAL CTA
         ============================================ -->
    <section class="py-20 bg-gradient-to-b from-primary-500/10 to-transparent">
      <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <!-- Icon -->
        <div class="w-20 h-20 mx-auto mb-6 rounded-full flex items-center justify-center" style="background: linear-gradient(135deg, #8b5cf6, #ec4899)">
          <span class="text-4xl">✨</span>
        </div>

        <h2 class="text-3xl md:text-4xl font-bold text-white mb-4">
          {{ t('landing.cta.title') }}
        </h2>
        <p class="text-xl text-gray-400 mb-4">
          {{ t('landing.cta.subtitle') }}
        </p>
        <p class="text-cyan-400 mb-8">
          {{ t('landing.cta.highlight') }}
        </p>

        <!-- Trust Badges -->
        <div class="flex justify-center gap-6 mb-8 text-gray-400 text-sm">
          <span>✓ {{ t('landing.cta.noCreditCard') }}</span>
          <span>✓ {{ t('landing.cta.freeTrial') }}</span>
          <span>✓ {{ t('landing.cta.cancelAnytime') }}</span>
        </div>

        <!-- CTAs -->
        <div class="flex flex-wrap justify-center gap-4 mb-8">
          <RouterLink to="/auth/register" class="btn-primary text-lg px-8 py-4">
            {{ t('landing.cta.tryNow') }} →
          </RouterLink>
          <button class="btn-secondary text-lg px-8 py-4">
            {{ t('landing.cta.contactSales') }}
          </button>
        </div>

        <!-- Social Proof -->
        <div class="flex items-center justify-center gap-2 text-gray-400">
          <span class="text-xl">🚀</span>
          <span>{{ t('landing.cta.socialProof') }}</span>
        </div>
      </div>
    </section>

    <!-- Video Modal -->
    <Teleport to="body">
      <div
        v-if="showVideoModal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @click.self="closeVideo"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm"></div>

        <!-- Modal Content -->
        <div class="relative w-full max-w-4xl bg-dark-800 rounded-2xl overflow-hidden shadow-2xl">
          <!-- Close Button -->
          <button
            @click="closeVideo"
            class="absolute top-4 right-4 z-10 w-10 h-10 bg-black/50 hover:bg-black/70 rounded-full flex items-center justify-center text-white transition-colors"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          <!-- Video Player -->
          <div class="aspect-video bg-black">
            <video
              v-if="currentVideo"
              :src="currentVideo.video"
              class="w-full h-full"
              controls
              autoplay
            >
              Your browser does not support the video tag.
            </video>
          </div>

          <!-- Title -->
          <div class="p-4 border-t border-dark-700">
            <h3 class="text-lg font-semibold text-white">{{ currentVideo?.title }}</h3>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
