<script setup lang="ts">
// vue imports removed - not needed
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores'

const router = useRouter()
const authStore = useAuthStore()

const toolCards = [
  { id: 'short-video', name: 'AI 短影片', desc: '文字一鍵生成專業短影片', route: '/tools/short-video', bg: '#d4f06b', emoji: '🎬', tag: 'Hot' },
  { id: 'avatar', name: 'AI 數位人', desc: '照片轉會說話的數位人', route: '/tools/avatar', bg: '#e8d5ff', emoji: '🎭', tag: 'New' },
  { id: 'try-on', name: '虛擬試穿', desc: '服裝 AI 模特展示效果', route: '/tools/try-on', bg: '#ffd4b3', emoji: '👗', tag: '' },
  { id: 'product-scene', name: '產品場景', desc: '商品圖智能場景生成', route: '/tools/product-scene', bg: '#d0e8ff', emoji: '📸', tag: '' },
  { id: 'background-removal', name: '智能去背', desc: '一鍵去除圖片背景', route: '/tools/background-removal', bg: '#ffd0e8', emoji: '✂️', tag: '' },
  { id: 'room-redesign', name: '空間設計', desc: 'AI 室內空間改造', route: '/tools/room-redesign', bg: '#d4f06b', emoji: '🏠', tag: '' },
]

const featureGroups = [
  {
    category: 'AI 影片創作', bg: '#d4f06b', emoji: '🎬',
    tools: [
      { name: 'AI 短影片生成', desc: '文字描述一鍵生成 2-30 秒專業短影片', route: '/tools/short-video', preview: '🎥' },
      { name: 'AI 數位人', desc: '照片轉會說話的數位人，自然唇形同步', route: '/tools/avatar', preview: '🎭' },
    ]
  },
  {
    category: '電商視覺', bg: '#e8d5ff', emoji: '🛒',
    tools: [
      { name: '虛擬試穿', desc: '服裝 AI 模特展示，提升購買轉化率', route: '/tools/try-on', preview: '👗' },
      { name: '產品場景生成', desc: '商品圖智能場景合成，電商級品質', route: '/tools/product-scene', preview: '📸' },
      { name: '智能去背', desc: '一鍵去除圖片背景，精準邊緣處理', route: '/tools/background-removal', preview: '✂️' },
    ]
  },
  {
    category: '空間設計', bg: '#ffd4b3', emoji: '🏠',
    tools: [
      { name: '室內空間改造', desc: 'AI 重新設計任何房間，多種風格選擇', route: '/tools/room-redesign', preview: '🛋️' },
    ]
  },
]

const stats = [
  { value: '1M+', label: '活躍用戶' },
  { value: '50M+', label: '生成作品' },
  { value: '8', label: 'AI 模型' },
  { value: '99.9%', label: '服務可用性' },
]

const brands = ['TikTok', 'Shopify', 'Amazon', 'Instagram', 'Etsy', 'eBay', 'WooCommerce', 'Walmart']

const pricingPreview = [
  { name: '免費體驗', price: '0', credits: '40', desc: '新用戶專屬，立即體驗 AI 生成', featured: false },
  { name: 'Starter', price: '99', credits: '100', desc: '適合個人創作者與小型電商', featured: false },
  { name: 'Pro', price: '649', credits: '無限制', desc: '專業團隊首選，最高畫質輸出', featured: true },
]

const modelInfo = [
  { name: 'Wan 2.2', type: '免費', desc: '快速生成，適合預覽', color: '#d4f06b' },
  { name: 'Kling v2', type: '付費', desc: '高畫質，8-30 秒', color: '#e8d5ff' },
  { name: 'Wan 2.5 Pro', type: '付費', desc: '專業級，1080p', color: '#ffd4b3' },
  { name: 'Hunyuan', type: '免費', desc: '多風格支援', color: '#d0e8ff' },
  { name: 'AnimateDiff', type: '免費', desc: '動畫風格生成', color: '#ffd0e8' },
  { name: 'Veo 3', type: '付費', desc: '最高品質輸出', color: '#d4f06b' },
]

function handleStartCreating() {
  if (authStore.isAuthenticated) {
    router.push('/tools/short-video')
  } else {
    router.push('/auth/register')
  }
}
</script>

<template>
  <div class="bg-white">

    <!-- HERO SECTION -->
    <section class="hero-section pt-24 pb-16 md:pt-32 md:pb-24">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div class="text-center max-w-4xl mx-auto">
          <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold mb-6" style="background: rgba(0,0,0,0.08); color: #111111;">
            <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
            8 個 AI 模型，智慧路由切換
          </div>
          <h1 class="text-5xl md:text-6xl lg:text-7xl font-black text-dark-900 leading-tight mb-6">
            AI 時代的<br>
            <span class="relative inline-block">
              影片創作平台
              <svg class="absolute -bottom-2 left-0 w-full" height="8" viewBox="0 0 300 8" fill="none">
                <path d="M2 6 C50 2, 150 2, 298 6" stroke="#d4f06b" stroke-width="4" stroke-linecap="round" fill="none"/>
              </svg>
            </span>
          </h1>
          <p class="text-lg md:text-xl text-dark-500 max-w-2xl mx-auto mb-10 leading-relaxed">
            文字描述一鍵生成專業影片。智慧模型路由，免費用戶自動使用開源模型，付費用戶解鎖 Kling、Wan Pro 等頂級模型。
          </p>
          <div class="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button @click="handleStartCreating" class="inline-flex items-center gap-2 px-8 py-4 bg-dark-900 text-white text-base font-bold rounded-full transition-all duration-200 hover:bg-dark-800" style="box-shadow: 0 4px 20px rgba(0,0,0,0.2);">
              <span>✦</span> 免費開始創作
            </button>
            <RouterLink to="/pricing" class="inline-flex items-center gap-2 px-8 py-4 bg-white text-dark-900 text-base font-semibold rounded-full border-2 border-dark-200 hover:border-dark-900 transition-all duration-200">
              查看定價方案
            </RouterLink>
          </div>
          <div class="flex items-center justify-center gap-6 mt-8 text-sm text-dark-400">
            <span class="flex items-center gap-1.5">✓ 免費 40 點起步</span>
            <span class="flex items-center gap-1.5">✓ 無需信用卡</span>
            <span class="flex items-center gap-1.5">✓ 台灣電子發票</span>
          </div>
        </div>
        <!-- Hero Demo Cards -->
        <div class="mt-16 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto">
          <div v-for="tool in toolCards.slice(0, 4)" :key="tool.id" class="rounded-2xl p-4 cursor-pointer transition-all duration-300 hover:scale-105" :style="{ background: tool.bg }" @click="router.push(tool.route)">
            <div class="text-3xl mb-2">{{ tool.emoji }}</div>
            <div class="font-bold text-dark-900 text-sm">{{ tool.name }}</div>
            <div class="text-dark-600 text-xs mt-0.5">{{ tool.desc }}</div>
            <div v-if="tool.tag" class="mt-2"><span class="badge-new text-xs">{{ tool.tag }}</span></div>
          </div>
        </div>
      </div>
    </section>

    <!-- BRAND LOGOS -->
    <section class="py-10 bg-white border-y border-black/6">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <p class="text-center text-sm text-dark-400 font-medium mb-6">受到全球 1,000,000+ 品牌與電商信賴</p>
        <div class="overflow-hidden">
          <div class="flex items-center gap-12 marquee-track">
            <span v-for="(brand, i) in [...brands, ...brands]" :key="i" class="text-dark-300 font-bold text-lg whitespace-nowrap flex-shrink-0">{{ brand }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- EXPLORE ALL TOOLS -->
    <section class="section-padding bg-white">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="section-title mb-4">探索所有 AI 創作工具</h2>
          <p class="section-subtitle">涵蓋影片生成、電商視覺、空間設計的完整 AI 工具集</p>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <RouterLink v-for="tool in toolCards" :key="tool.id" :to="tool.route" class="tool-card aspect-square flex flex-col items-center justify-center p-4 text-center" :style="{ background: tool.bg }">
            <div class="text-4xl mb-3 float-anim">{{ tool.emoji }}</div>
            <div class="font-bold text-dark-900 text-sm leading-tight">{{ tool.name }}</div>
            <div v-if="tool.tag" class="mt-2"><span class="badge-new text-xs">{{ tool.tag }}</span></div>
          </RouterLink>
        </div>
      </div>
    </section>

    <!-- GENERATE ENDLESS POSSIBILITIES -->
    <section class="section-padding" style="background: #f8f8f8;">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="section-title mb-4">一鍵生成無限可能</h2>
          <p class="section-subtitle">透過智慧整合的 AI 能力，大幅提升創作效率與競爭力</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div v-for="group in featureGroups" :key="group.category" class="rounded-3xl overflow-hidden" :style="{ background: group.bg }">
            <div class="p-6 pb-4">
              <div class="text-3xl mb-2">{{ group.emoji }}</div>
              <h3 class="text-xl font-black text-dark-900">{{ group.category }}</h3>
            </div>
            <div class="px-4 pb-4 space-y-3">
              <RouterLink v-for="tool in group.tools" :key="tool.name" :to="tool.route" class="block bg-white/70 backdrop-blur-sm rounded-2xl p-4 hover:bg-white/90 transition-all duration-200 group">
                <div class="flex items-center gap-3">
                  <span class="text-2xl">{{ tool.preview }}</span>
                  <div class="flex-1 min-w-0">
                    <div class="font-semibold text-dark-900 text-sm">{{ tool.name }}</div>
                    <div class="text-dark-500 text-xs mt-0.5 truncate">{{ tool.desc }}</div>
                  </div>
                  <svg class="w-4 h-4 text-dark-400 group-hover:text-dark-900 transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </div>
              </RouterLink>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- MODEL ROUTING -->
    <section class="section-padding bg-white">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="section-title mb-4">智慧模型路由</h2>
          <p class="section-subtitle">系統自動根據您的點數餘額，選擇最適合的 AI 模型</p>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-10">
          <div v-for="model in modelInfo" :key="model.name" class="rounded-2xl p-4 text-center" :style="{ background: model.color }">
            <div class="font-bold text-dark-900 text-sm mb-1">{{ model.name }}</div>
            <div class="text-xs text-dark-600 mb-2">{{ model.desc }}</div>
            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold" :class="model.type === '免費' ? 'bg-white/80 text-dark-700' : 'bg-dark-900 text-white'">{{ model.type }}</span>
          </div>
        </div>
        <div class="max-w-2xl mx-auto">
          <div class="rounded-3xl p-8" style="background: #111111; color: white;">
            <h3 class="text-lg font-bold mb-6 text-center">路由邏輯</h3>
            <div class="space-y-4">
              <div class="flex items-center gap-4 p-4 rounded-2xl" style="background: rgba(212,240,107,0.15); border: 1px solid rgba(212,240,107,0.3);">
                <div class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style="background: #d4f06b;"><span class="text-dark-900 font-bold text-sm">40</span></div>
                <div>
                  <div class="font-semibold text-sm" style="color: #d4f06b;">免費層（40 點內）</div>
                  <div class="text-xs text-gray-400 mt-0.5">自動使用 Hugging Face / AnimateDiff / Hunyuan / Wan 2.2 / Veo 3</div>
                </div>
              </div>
              <div class="flex items-center justify-center"><svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg></div>
              <div class="flex items-center gap-4 p-4 rounded-2xl" style="background: rgba(196,168,255,0.15); border: 1px solid rgba(196,168,255,0.3);">
                <div class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style="background: #c4a8ff;"><span class="text-dark-900 font-bold text-sm">Pro</span></div>
                <div>
                  <div class="font-semibold text-sm" style="color: #c4a8ff;">付費層（儲值後）</div>
                  <div class="text-xs text-gray-400 mt-0.5">解鎖 Wan 2.5 / Kling v2 / 萬興天幕，1080p 高畫質有聲</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- STATS -->
    <section class="section-padding" style="background: #d4f06b;">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div v-for="stat in stats" :key="stat.label" class="text-center">
            <div class="text-4xl md:text-5xl font-black text-dark-900 mb-2">{{ stat.value }}</div>
            <div class="text-dark-600 font-medium">{{ stat.label }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- PRICING PREVIEW -->
    <section class="section-padding bg-white">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="section-title mb-4">簡單透明的定價</h2>
          <p class="section-subtitle">從免費開始，按需升級。台灣電子發票，合法報帳。</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto">
          <div v-for="plan in pricingPreview" :key="plan.name" class="pricing-card" :class="{ featured: plan.featured }">
            <div v-if="plan.featured" class="badge-new mb-4 inline-block">最受歡迎</div>
            <h3 class="text-xl font-bold mb-2" :class="plan.featured ? 'text-white' : 'text-dark-900'">{{ plan.name }}</h3>
            <div class="flex items-baseline gap-1 mb-4">
              <span class="text-4xl font-black" :class="plan.featured ? 'text-white' : 'text-dark-900'">NT${{ plan.price }}</span>
              <span class="text-sm" :class="plan.featured ? 'text-gray-400' : 'text-dark-400'">/月</span>
            </div>
            <div class="mb-4"><span class="text-sm font-semibold" :class="plan.featured ? 'text-gray-300' : 'text-dark-500'">{{ plan.credits }} 點數</span></div>
            <p class="text-sm mb-6" :class="plan.featured ? 'text-gray-400' : 'text-dark-500'">{{ plan.desc }}</p>
            <RouterLink to="/pricing" class="block text-center py-3 rounded-full font-semibold text-sm transition-all duration-200" :class="plan.featured ? 'bg-primary-300 text-dark-900 hover:bg-primary-200' : 'bg-dark-900 text-white hover:bg-dark-800'">
              {{ plan.price === '0' ? '立即免費開始' : '選擇此方案' }}
            </RouterLink>
          </div>
        </div>
        <div class="text-center mt-8">
          <RouterLink to="/pricing" class="inline-flex items-center gap-2 text-dark-600 hover:text-dark-900 font-medium transition-colors">
            查看完整定價與功能對比
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
          </RouterLink>
        </div>
      </div>
    </section>

    <!-- HOW IT WORKS -->
    <section class="section-padding" style="background: #f0e8ff;">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="section-title mb-4">三步驟開始創作</h2>
          <p class="section-subtitle">從註冊到生成第一個影片，只需幾分鐘</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-3xl mx-auto">
          <div class="text-center">
            <div class="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl mx-auto mb-4 font-black text-dark-900" style="background: #d4f06b;">1</div>
            <h3 class="font-bold text-dark-900 mb-2">免費註冊</h3>
            <p class="text-dark-500 text-sm">填寫 Email 即可完成，立即獲得 40 點免費點數</p>
          </div>
          <div class="text-center">
            <div class="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl mx-auto mb-4 font-black text-dark-900" style="background: #c4a8ff;">2</div>
            <h3 class="font-bold text-dark-900 mb-2">輸入描述</h3>
            <p class="text-dark-500 text-sm">用中文或英文描述您想要的影片內容</p>
          </div>
          <div class="text-center">
            <div class="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl mx-auto mb-4 font-black text-dark-900" style="background: #ffd4b3;">3</div>
            <h3 class="font-bold text-dark-900 mb-2">下載使用</h3>
            <p class="text-dark-500 text-sm">3-8 分鐘生成完成，直接下載高畫質影片</p>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA SECTION -->
    <section class="section-padding" style="background: #111111;">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 class="text-4xl md:text-5xl font-black text-white mb-6">立即開始免費創作</h2>
        <p class="text-gray-400 text-lg mb-10 max-w-xl mx-auto">加入超過 100 萬個品牌與創作者，用 AI 讓您的創意無限延伸</p>
        <button @click="handleStartCreating" class="inline-flex items-center gap-2 px-10 py-4 font-bold text-dark-900 rounded-full text-lg transition-all duration-200 hover:scale-105" style="background: #d4f06b; box-shadow: 0 4px 30px rgba(212,240,107,0.4);">
          <span>✦</span> 免費開始 — 獲得 40 點
        </button>
        <p class="text-gray-500 text-sm mt-4">無需信用卡 · 立即可用 · 隨時取消</p>
      </div>
    </section>

  </div>
</template>
