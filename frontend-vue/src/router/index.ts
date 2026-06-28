import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { applySeo } from '@/composables/useSeo'
import { safeLocalStorage } from '@/utils/safeStorage'

// 2026-05-18 — subscription result pages are eagerly imported. They
// are the landing target when PayPal redirects back to vidgo.co after
// the user cancels or completes payment, and a lazy-chunk fetch over
// a slow network on top of the PayPal redirect was producing a blank
// "page keeps loading but does nothing" experience for cancellers.
import SubscriptionSuccess from '@/views/subscription/SubscriptionSuccess.vue'
import SubscriptionCancelled from '@/views/subscription/SubscriptionCancelled.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/LandingPage.vue')
  },

  // ===== Real Tools (backed by PiAPI / rembg / A2E APIs) =====

  // Background Removal — local rembg
  {
    path: '/tools/background-removal',
    name: 'background-removal',
    component: () => import('@/views/tools/BackgroundRemoval.vue'),
    meta: { requiresAuth: false }
  },

  // Style Effects & Image Transform removed — merged into Room Redesign
  { path: '/tools/effects', redirect: '/tools/room-redesign' },
  { path: '/tools/image-transform', redirect: '/tools/room-redesign' },

  // Product Scene — now the tool-hub launcher ("What do you need?").
  {
    path: '/tools/product-scene',
    name: 'product-scene',
    component: () => import('@/views/tools/ProductScene.vue'),
    meta: { requiresAuth: false }
  },

  // Legacy Product Scene generator (preset products × scenes) kept reachable
  // for users who deep-link or who still want the scene picker. Linked from
  // the hub tiles for "Flat lay" and "Product photography".
  {
    path: '/tools/product-scene-classic',
    name: 'product-scene-classic',
    component: () => import('@/views/tools/ProductSceneClassic.vue'),
    meta: { requiresAuth: false }
  },

  // AI Try-On — PiAPI Kling ai_try_on
  {
    path: '/tools/try-on',
    name: 'try-on',
    component: () => import('@/views/tools/TryOn.vue'),
    meta: { requiresAuth: false }
  },

  // Product Recolor (商品換色) — added 2026-06-12. The hub tile previously
  // deep-linked to /tools/pattern-generate (wrong tool); this is the real
  // color-change service (Kontext I2I, color-only edit).
  {
    path: '/tools/recolor',
    name: 'recolor',
    component: () => import('@/views/tools/Recolor.vue'),
    meta: { requiresAuth: false }
  },

  // Room Redesign — PiAPI Kontext (Flux advanced)
  {
    path: '/tools/room-redesign',
    name: 'room-redesign',
    component: () => import('@/views/tools/RoomRedesign.vue'),
    meta: { requiresAuth: false }
  },

  // 2026-06-11 — interior design workflow tools. The growth video folded into
  // 3D 效果圖 (/tools/render-3d), so the old floorplan-to-video route now redirects.
  {
    path: '/tools/floor-plan',
    name: 'floor-plan',
    component: () => import('@/views/tools/FloorPlan.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/tools/isometric',
    name: 'isometric',
    component: () => import('@/views/tools/Isometric.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/tools/render-3d',
    name: 'render-3d',
    component: () => import('@/views/tools/Render3D.vue'),
    meta: { requiresAuth: false }
  },
  { path: '/tools/floorplan-to-video', redirect: '/tools/render-3d' },

  // Exterior AI — building-facade render. Reuses /tools/room-redesign with
  // space_kind='exterior' (mnml.ai/app/exterior-ai parity).
  {
    path: '/tools/exterior-ai',
    name: 'exterior-ai',
    component: () => import('@/views/tools/ExteriorAI.vue'),
    meta: { requiresAuth: false }
  },

  // Commercial Space Design — split out of RoomRedesign (2026-06-03). Reuses
  // /tools/room-redesign with space_kind='commercial'.
  {
    path: '/tools/commercial-space',
    name: 'commercial-space',
    component: () => import('@/views/tools/CommercialSpace.vue'),
    meta: { requiresAuth: false }
  },

  // Landscape / Garden AI — new 2026-06-15. Reuses /tools/room-redesign with
  // space_kind='landscape' (LANDSCAPE_STYLES catalog).
  {
    path: '/tools/landscape-ai',
    name: 'landscape-ai',
    component: () => import('@/views/tools/LandscapeAI.vue'),
    meta: { requiresAuth: false }
  },

  // Sketch → photorealistic render. Reuses /tools/room-redesign image-to-image
  // (mnml.ai/app/sketch2img parity). 2026-06-12 — split into dedicated
  // interior and exterior pages (owner directive: never mix interior and
  // exterior on one page); the old combined route redirects to the exterior
  // page, which was its previous default.
  {
    path: '/tools/sketch-to-render-exterior',
    name: 'sketch-to-render-exterior',
    component: () => import('@/views/tools/SketchToRender.vue'),
    props: { spaceKind: 'exterior' },
    meta: { requiresAuth: false }
  },
  {
    path: '/tools/sketch-to-render-interior',
    name: 'sketch-to-render-interior',
    component: () => import('@/views/tools/SketchToRender.vue'),
    props: { spaceKind: 'interior' },
    meta: { requiresAuth: false }
  },
  { path: '/tools/sketch-to-render', redirect: '/tools/sketch-to-render-exterior' },

  // Render Enhancer — AI detail enhance (room-redesign magic) + upscale
  // (mnml.ai/app/render-enhancer parity).
  {
    path: '/tools/render-enhancer',
    name: 'render-enhancer',
    component: () => import('@/views/tools/RenderEnhancer.vue'),
    meta: { requiresAuth: false }
  },

  // Templates Galleries — Pippit-style browsable style cards (added
  // 2026-05-24). 2026-06-12: the in-page interior/exterior/commercial tab
  // switcher was removed (owner directive: never mix interior and exterior
  // on one page) — each space kind is its own dedicated page pinned via the
  // spaceKind prop. Clicking a card deeplinks into the matching tool page.
  {
    path: '/tools/interior-templates',
    name: 'interior-templates',
    component: () => import('@/views/tools/InteriorTemplates.vue'),
    props: { spaceKind: 'interior' },
    meta: { requiresAuth: false }
  },
  {
    path: '/tools/exterior-templates',
    name: 'exterior-templates',
    component: () => import('@/views/tools/InteriorTemplates.vue'),
    props: { spaceKind: 'exterior' },
    meta: { requiresAuth: false }
  },
  {
    path: '/tools/commercial-templates',
    name: 'commercial-templates',
    component: () => import('@/views/tools/InteriorTemplates.vue'),
    props: { spaceKind: 'commercial' },
    meta: { requiresAuth: false }
  },

  // Video Background Remove — Qubico video-toolkit (added 2026-05-24,
  // verified healthy via stability probe). Sibling Qubico video tools
  // upscale + watermark-remove dropped per same probe.
  {
    path: '/tools/video-bg-remove',
    name: 'video-bg-remove',
    component: () => import('@/views/tools/VideoBackgroundRemove.vue'),
    meta: { requiresAuth: false }
  },

  // Claymation AI — multi-mode (T2I / I2I / T2V / V2V) routed to
  // Seedream 5 Lite / Flux Kontext / Kling Omni 3.0 / Seedance 2.0 Fast.
  // Matches piapi.ai/zh-TW/claymation-ai-generator layout.
  {
    path: '/tools/claymation',
    name: 'claymation',
    component: () => import('@/views/tools/Claymation.vue'),
    meta: { requiresAuth: false }
  },

  // Image-to-Video — PiAPI Wan 2.6 I2V
  {
    path: '/tools/short-video',
    name: 'short-video',
    component: () => import('@/views/tools/ShortVideo.vue'),
    meta: { requiresAuth: false }
  },
  // /tools/image-to-video rendered the SAME ShortVideo.vue with identical
  // behaviour (applyRouteToTaskType defaults both to image_to_video), so it was
  // a duplicate indexable URL. Redirect to the canonical /tools/short-video so
  // Google consolidates them (was GSC "duplicate" on the alternate URL). Old
  // links (e.g. VideoTopic.vue) keep working via the redirect.
  { path: '/tools/image-to-video', redirect: '/tools/short-video' },

  // /tools/video-transform route removed 2026-05-31 — V2V dropped repo-wide.

  // Text-to-Video removed — redirect to Image-to-Video
  { path: '/tools/text-to-video', redirect: '/tools/short-video' },

  // Image Upscale — PiAPI image-toolkit (NEW)
  {
    path: '/tools/upscale',
    name: 'upscale',
    component: () => import('@/views/tools/ImageUpscale.vue'),
    meta: { requiresAuth: false }
  },
  { path: '/tools/image-upscale', redirect: '/tools/upscale' },

  // AI Avatar — A2E provider
  {
    path: '/tools/avatar',
    name: 'avatar',
    component: () => import('@/views/tools/AIAvatar.vue'),
    meta: { requiresAuth: false }
  },

  // Pattern Generate — PiAPI T2I (Flux)
  {
    path: '/tools/pattern-generate',
    name: 'pattern-generate',
    component: () => import('@/views/topics/PatternTopic.vue'),
    meta: { requiresAuth: false }
  },

  // ===== Premium / Flagship Models (PiAPI) =====

  // Midjourney text-to-image — image_generation_premium tier (~50 credits)
  {
    path: '/tools/midjourney-imagine',
    name: 'midjourney-imagine',
    component: () => import('@/views/tools/MidjourneyImagine.vue'),
    meta: { requiresAuth: false }
  },

  // Kling video — tier-based pricing (default 100 / flagship 500 credits)
  {
    path: '/tools/kling-video',
    name: 'kling-video',
    component: () => import('@/views/tools/KlingVideo.vue'),
    meta: { requiresAuth: false }
  },

  // Sora 2 Pro — flagship 5s 1080p with audio (80 credits / premium tier).
  // Added 2026-06-09; PiAPI primary, Pollo backup. Mirrors KlingVideo UX
  // (preset dropdown + free-form prompt + optional source frame).
  {
    path: '/tools/sora2-pro',
    name: 'sora2-pro',
    component: () => import('@/views/tools/Sora2Pro.vue'),
    meta: { requiresAuth: false }
  },

  // ===== Redirects for removed/aliased routes =====
  // 2026-05-19: Luma removed in favor of the new tier (Seedance Fast default,
  // Kling Omni premium, Hailuo Fast cheap, Hunyuan 中文, Wan specialty).
  // Redirect to /tools/short-video so old bookmarks land on the closest tool.
  { path: '/tools/luma-video', redirect: '/tools/short-video' },
  { path: '/tools/remove-watermark', redirect: '/tools/effects' },
  // 2026-06-11: Image Translator and Video Dubbing retired. Redirect old
  // bookmarks/links to the tool hub instead of 404-ing.
  { path: '/tools/image-translator', redirect: '/tools/product-scene' },
  { path: '/tools/video-dubbing', redirect: '/tools/product-scene' },
  { path: '/tools/ai-model-swap', redirect: '/tools/try-on' },
  { path: '/tools/try-on-accessories', redirect: '/tools/try-on' },
  { path: '/tools/ai-templates', redirect: '/tools/product-scene' },
  { path: '/tools/product-video', redirect: '/tools/short-video' },
  { path: '/tools/product-enhance', redirect: '/tools/upscale' },
  { path: '/tools/pattern-transfer', redirect: '/tools/pattern-generate' },
  { path: '/tools/pattern-seamless', redirect: '/tools/pattern-generate' },

  // Topic pages
  {
    path: '/topics/pattern',
    name: 'topic-pattern',
    component: () => import('@/views/topics/PatternTopic.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/topics/product',
    name: 'topic-product',
    component: () => import('@/views/topics/ProductTopic.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/topics/video',
    name: 'topic-video',
    component: () => import('@/views/topics/VideoTopic.vue'),
    meta: { requiresAuth: false }
  },

  // Auth routes
  {
    path: '/auth/login',
    name: 'login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { guestOnly: true }
  },
  {
    path: '/auth/register',
    name: 'register',
    component: () => import('@/views/auth/Register.vue'),
    meta: { guestOnly: true }
    // Accepts ?ref=CODE query param to pre-fill referral code during registration
  },
  {
    path: '/auth/verify',
    name: 'verify',
    component: () => import('@/views/auth/VerifyEmail.vue')
  },
  {
    path: '/auth/forgot-password',
    name: 'forgot-password',
    component: () => import('@/views/auth/ForgotPassword.vue'),
    meta: { guestOnly: true }
  },
  {
    path: '/auth/reset-password',
    name: 'reset-password',
    component: () => import('@/views/auth/ResetPassword.vue'),
    meta: { guestOnly: true }
  },

  // Dashboard routes
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('@/views/admin/AdminDashboard.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/dashboard/my-works',
    name: 'my-works',
    component: () => import('@/views/dashboard/MyWorks.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/dashboard/invoices',
    name: 'invoices',
    component: () => import('@/views/dashboard/Invoices.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/dashboard/referrals',
    name: 'referrals',
    component: () => import('@/views/dashboard/Referrals.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/dashboard/share-links',
    name: 'share-links',
    component: () => import('@/views/dashboard/SocialAccounts.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/dashboard/social-accounts',
    redirect: { name: 'share-links' },
    meta: { requiresAuth: true }
  },

  // Pricing
  {
    path: '/pricing',
    name: 'pricing',
    component: () => import('@/views/Pricing.vue')
  },

  {
    path: '/:slug(about|contact|blog|affiliate|terms|terms-of-service|terms-and-conditions|privacy|privacy-policy|cookies|refunds|refund|refund-policy)',
    name: 'static-info',
    component: () => import('@/views/StaticInfoPage.vue')
  },
  // /info/<slug> aliases — surface the same content at the namespaced path so
  // external links built with /info/... prefixes resolve. Final QA expects
  // /info/about, /info/contact, /info/terms, /info/privacy, /info/cookies,
  // /info/refund, /info/affiliate to all render.
  {
    path: '/info/:slug(about|contact|blog|affiliate|terms|terms-of-service|terms-and-conditions|privacy|privacy-policy|cookies|refunds|refund|refund-policy)',
    name: 'static-info-namespaced',
    component: () => import('@/views/StaticInfoPage.vue')
  },

  // Subscription payment results — eagerly imported so the browser
  // never sits on a blank "loading" frame waiting on a lazy chunk
  // after PayPal redirects back to vidgo.co. The chunks are tiny.
  {
    path: '/subscription/success',
    name: 'subscription-success',
    component: SubscriptionSuccess,
    // Intentionally NOT requiring auth here — PayPal sometimes drops
    // our access_token cookie during its OAuth roundtrip, and bouncing
    // a paying user to /login on /subscription/success is a worse UX
    // than letting them see the success message. The webhook + return
    // handler validate the order server-side.
  },
  {
    path: '/subscription/cancelled',
    name: 'subscription-cancelled',
    component: SubscriptionCancelled
  },
  {
    path: '/subscription/mock-checkout',
    name: 'subscription-mock-checkout',
    component: () => import('@/views/subscription/SubscriptionMockCheckout.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/subscription/ecpay-result',
    name: 'subscription-ecpay-result',
    component: () => import('@/views/subscription/ECPayResult.vue')
  },

  // Admin Dashboard
  {
    path: '/admin',
    component: () => import('@/views/admin/AdminLayout.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
    redirect: { name: 'admin-dashboard' },
    children: [
      { path: 'dashboard',         name: 'admin-dashboard',        component: () => import('@/views/admin/AdminDashboard.vue') },
      { path: 'users',             name: 'admin-users',            component: () => import('@/views/admin/AdminUsers.vue') },
      { path: 'promotions',        name: 'admin-promotions',       component: () => import('@/views/admin/AdminPromotions.vue') },
      { path: 'materials',         name: 'admin-materials',        component: () => import('@/views/admin/AdminMaterials.vue') },
      { path: 'moderation',        name: 'admin-moderation',       component: () => import('@/views/admin/AdminModeration.vue') },
      { path: 'revenue',           name: 'admin-revenue',          component: () => import('@/views/admin/AdminRevenue.vue') },
      { path: 'system',            name: 'admin-system',           component: () => import('@/views/admin/AdminSystem.vue') },
      { path: 'plans',             name: 'admin-plans',            component: () => import('@/views/admin/AdminPlans.vue') },
      { path: 'branding',          name: 'admin-branding',         component: () => import('@/views/admin/AdminBranding.vue') },
      { path: 'costs',             name: 'admin-costs',            component: () => import('@/views/admin/AdminCosts.vue') },
      { path: 'models',            name: 'admin-models',           component: () => import('@/views/admin/AdminModels.vue') },
      { path: 'settings/payment',  name: 'admin-settings-payment', component: () => import('@/views/admin/AdminPaymentSettings.vue') },
    ],
  },

  // 404
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFound.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    } else {
      return { top: 0 }
    }
  }
})

// ── SEO metadata per route ──
// Keyed by route.name so the catalogue is decoupled from path edits. Pages
// without an entry fall back to the site-wide default in applySeo().
type RouteSeo = { title: string; description: string }
const ROUTE_SEO: Record<string, RouteSeo> = {
  'landscape-ai': {
    title: 'AI 景觀設計渲染｜庭園/外構風格範本 - VidGo',
    description:
      '上傳庭園、綠地或外構照片，挑選風格，AI 生成多版本景觀設計提案圖。',
  },
  home: {
    title: 'VidGo AI｜AI 商品攝影、去背、短影音與室內設計工具',
    description:
      'VidGo AI 集合商品攝影、智能去背、AI 試穿、室內設計渲染、短影音與數位人，一站完成電商與品牌內容製作。',
  },
  pricing: {
    title: 'VidGo 定價方案｜AI 商品圖、影片與室內設計點數方案',
    description:
      '比較 VidGo AI 訂閱方案與點數包：4K 影音、無浮水印、優先佇列、API 存取，依用量選擇最適方案。',
  },
  'background-removal': {
    title: 'AI 智能去背工具｜商品圖透明 PNG 與換景 - VidGo',
    description:
      '上傳商品圖即可一鍵 AI 去背，輸出透明 PNG 或自動換景；保留邊緣細節，適合電商商品圖與目錄。',
  },
  recolor: {
    title: 'AI 商品換色｜一鍵更換商品顏色，材質與 Logo 不變 - VidGo',
    description:
      '上傳商品照片並選擇目標顏色，AI 只更換顏色 — 形狀、材質、Logo、背景與光影完全保留，快速產出多色系商品圖。',
  },
  'room-redesign': {
    title: 'AI 室內設計渲染｜房間照片、草圖與平面圖轉提案圖 - VidGo',
    description:
      '上傳房間照片或草圖，挑選風格範本，AI 立即生成室內設計提案圖，支援 4K 高解析輸出。',
  },
  'interior-templates': {
    title: 'AI 室內設計範本庫｜風格範本一鍵套用 - VidGo',
    description:
      '瀏覽北歐、極簡、日式侘寂、工業風等室內設計範本，挑選後上傳房間照片，AI 立即生成提案圖。',
  },
  'exterior-templates': {
    title: 'AI 建築外觀範本庫｜外觀風格一鍵套用 - VidGo',
    description:
      '瀏覽現代玻璃帷幕、北歐木屋、地中海別墅等建築外觀範本，挑選後上傳建築照片，AI 立即生成外觀提案。',
  },
  'commercial-templates': {
    title: 'AI 商業空間範本庫｜店面與餐廳風格一鍵套用 - VidGo',
    description:
      '瀏覽餐酒館、精品零售、飯店大廳等商業空間範本，挑選後上傳空間照片，AI 立即生成設計提案。',
  },
  'floor-plan': {
    title: 'AI 平面配置圖｜輸入需求或草圖生成 2D 平面圖 - VidGo',
    description:
      '輸入空間需求與尺寸，或上傳手繪草圖，AI 立即產生乾淨的 2D 平面配置圖。',
  },
  'isometric': {
    title: 'AI 立體圖｜平面圖轉 45° 等角透視 - VidGo',
    description:
      '上傳平面圖或空間照片，AI 生成 45° 等角立體圖（dollhouse 視角），快速呈現格局。',
  },
  'render-3d': {
    title: 'AI 3D 效果圖｜平面圖轉寫實渲染與成長影片 - VidGo',
    description:
      '上傳平面圖或房間照片，AI 渲染寫實 3D 效果圖，並可加購「拔地而起」成長影片與可旋轉 3D 模型。',
  },
  'exterior-ai': {
    title: 'AI 建築外觀渲染｜立面風格範本 - VidGo',
    description:
      '上傳建築外觀照片或草圖，挑選材質與風格，AI 生成多版本建築立面提案圖。',
  },
  'commercial-space': {
    title: 'AI 商業空間設計渲染｜店面、辦公室與餐廳提案 - VidGo',
    description:
      '上傳商業空間照片，AI 依照產業與品牌氣質生成店面、辦公室、咖啡廳的設計提案。',
  },
  'sketch-to-render-exterior': {
    title: 'AI 草圖轉渲染（建築外觀）｜手繪外觀草圖轉寫實渲染 - VidGo',
    description:
      '上傳建築外觀手繪草圖或線稿，挑選風格，AI 立即生成寫實建築外觀渲染圖。',
  },
  'sketch-to-render-interior': {
    title: 'AI 草圖轉渲染（室內）｜手繪室內草圖轉寫實渲染 - VidGo',
    description:
      '上傳室內空間手繪草圖或線稿，挑選風格，AI 立即生成寫實室內設計渲染圖。',
  },
  'try-on': {
    title: 'AI 模特試穿｜服飾自動套用到模特身上 - VidGo',
    description:
      '上傳平拍服飾與模特圖片，AI 自動完成試穿合成，保留布料質感與品牌一致性。',
  },
  'short-video': {
    title: 'AI 短影音生成｜圖片轉影片、社群廣告影片 - VidGo',
    description:
      '單張商品圖即可生成 8 秒短影音，適合社群廣告、商品介紹與品牌主視覺。',
  },
  avatar: {
    title: 'AI 數位人生成｜口播導購與品牌代言影片 - VidGo',
    description:
      'AI 數位人代言：自動生成口播影片，支援多語言、語速調整，適合電商導購與品牌行銷。',
  },
  upscale: {
    title: 'AI 圖片高畫質放大｜4K 高解析輸出 - VidGo',
    description:
      '上傳低解析圖片，AI 自動補細節並放大至 4K，適合商品圖、藝術作品與印刷素材。',
  },
  login: { title: '登入 VidGo AI', description: '登入 VidGo AI 帳號，繼續使用 AI 商品攝影、影音與室內設計工具。' },
  register: {
    title: '註冊 VidGo AI｜40 點免費點數',
    description: '免費註冊 VidGo AI，立即獲得 40 點免費點數，使用商品攝影、影音與室內設計工具。',
  },
}

// Canonical host is always the apex vidgo.co, NOT window.location.origin.
// The same SPA is served on both vidgo.co and www.vidgo.co (Cloud Run domain
// mappings, 2026-06-28); if canonical were derived from the live host, www
// pages would self-reference www and Google would index two copies of every
// page. Pinning the apex consolidates all SEO signal onto vidgo.co.
const CANONICAL_ORIGIN = 'https://vidgo.co'

router.afterEach((to) => {
  const origin = CANONICAL_ORIGIN
  const path = to.path || '/'
  // /info/<slug> renders the SAME StaticInfoPage as /<slug>. Keep the namespaced
  // route working (external links use it) but point its canonical at the clean
  // /<slug> form so Google indexes ONE URL per static page instead of treating
  // /info/about as a duplicate of /about.
  let canonicalPath = path
  if (to.name === 'static-info-namespaced' && to.params.slug) {
    canonicalPath = '/' + String(to.params.slug)
  }
  const canonical = origin ? origin + canonicalPath : undefined
  const name = (to.name as string) || ''
  const seo = ROUTE_SEO[name]
  const lang = typeof document !== 'undefined' ? document.documentElement.getAttribute('lang') || 'en' : 'en'
  // 2026-06-15 — single canonical URL per page. We deliberately DO NOT emit
  // per-locale ?lang= hreflang alternates: the canonical here is the param-less
  // path (origin + path), so advertising ?lang= variants as separate indexable
  // URLs contradicted the canonical and produced Google Search Console's
  // "Alternate page with proper canonical tag" exclusions. The ?lang= query
  // still works for users (getInitialLocale honours it) — it's just not
  // surfaced to search engines as a distinct URL. applySeo() clears any stale
  // hreflang on every navigation.
  applySeo({
    title: seo?.title,
    description: seo?.description,
    canonical,
    locale: lang,
    // Guest-only pages (login/register/etc.) shouldn't be indexed once logged in,
    // but as guest-discoverable pages they're fine to leave open. /admin etc. is
    // explicitly noindex.
    noindex: path.startsWith('/admin') || path.startsWith('/dashboard') || path.startsWith('/subscription'),
  })
})

// Navigation guards
router.beforeEach(async (to, _from, next) => {
  const token = safeLocalStorage.getItem('access_token')
  const isAuthenticated = !!token

  if (to.meta.requiresAuth && !isAuthenticated) {
    next({ name: 'login', query: { redirect: to.fullPath } })
  } else if (to.meta.guestOnly && isAuthenticated) {
    const { useAuthStore } = await import('@/stores/auth')
    const authStore = useAuthStore()
    if (!authStore.user) {
      try {
        await authStore.fetchUser()
      } catch {
        next()
        return
      }
    }
    if (authStore.user) {
      next({ name: authStore.isAdmin ? 'admin-dashboard' : 'my-works' })
    } else {
      next()
    }
  } else if (to.path === '/dashboard' && isAuthenticated) {
    const { useAuthStore } = await import('@/stores/auth')
    const authStore = useAuthStore()
    if (!authStore.user && token) {
      await authStore.fetchUser()
    }
    next({ name: authStore.isAdmin ? 'admin-dashboard' : 'my-works' })
  } else if (
    isAuthenticated &&
    (to.path === '/dashboard/invoices' ||
      to.path === '/dashboard/referrals')
  ) {
    // Invoices and referrals are user-billing-only; admins don't have a
    // personal billing record to view there, so we still bounce them up to
    // the admin dashboard. /dashboard/my-works, /dashboard/share-links, and
    // /dashboard/social-accounts ARE meaningful for admin accounts (own
    // generations, own share links) so we let those pass through.
    const { useAuthStore } = await import('@/stores/auth')
    const authStore = useAuthStore()
    if (!authStore.user && token) {
      try { await authStore.fetchUser() } catch { /* noop */ }
    }
    if (authStore.isAdmin) {
      next({ name: 'admin-dashboard' })
    } else {
      next()
    }
  } else if (to.meta.requiresAdmin) {
    const { useAuthStore } = await import('@/stores/auth')
    const authStore = useAuthStore()
    if (!authStore.user && token) {
      await authStore.fetchUser()
    }
    if (!authStore.isAdmin) {
      next({ name: 'home' })
    } else {
      next()
    }
  } else {
    next()
  }
})

export default router
