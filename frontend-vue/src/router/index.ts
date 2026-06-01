import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

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

  // Room Redesign — PiAPI Kontext (Flux advanced)
  {
    path: '/tools/room-redesign',
    name: 'room-redesign',
    component: () => import('@/views/tools/RoomRedesign.vue'),
    meta: { requiresAuth: false }
  },

  // Interior Templates Gallery — Pippit-style browsable style cards
  // (added 2026-05-24). Clicking a card deeplinks to /tools/room-redesign
  // with style + space_kind preselected via query params.
  {
    path: '/tools/interior-templates',
    name: 'interior-templates',
    component: () => import('@/views/tools/InteriorTemplates.vue'),
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
  {
    path: '/tools/image-to-video',
    name: 'image-to-video',
    component: () => import('@/views/tools/ShortVideo.vue'),
    meta: { requiresAuth: false }
  },

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

  // ===== Redirects for removed/aliased routes =====
  // 2026-05-19: Luma removed in favor of the new tier (Seedance Fast default,
  // Kling Omni premium, Hailuo Fast cheap, Hunyuan 中文, Wan specialty).
  // Redirect to /tools/short-video so old bookmarks land on the closest tool.
  { path: '/tools/luma-video', redirect: '/tools/short-video' },
  { path: '/tools/remove-watermark', redirect: '/tools/effects' },
  {
    path: '/tools/image-translator',
    name: 'image-translator',
    component: () => import('@/views/tools/ImageTranslator.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/tools/video-dubbing',
    name: 'video-dubbing',
    component: () => import('@/views/tools/VideoDubbing.vue'),
    meta: { requiresAuth: false }
  },
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

  // Inspiration Gallery
  {
    path: '/gallery',
    name: 'gallery',
    component: () => import('@/views/InspirationGallery.vue')
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

// Navigation guards
router.beforeEach(async (to, _from, next) => {
  const token = localStorage.getItem('access_token')
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
