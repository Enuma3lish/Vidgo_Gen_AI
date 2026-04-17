import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

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

  // Product Scene — T2I + rembg + PIL composite
  {
    path: '/tools/product-scene',
    name: 'product-scene',
    component: () => import('@/views/tools/ProductScene.vue'),
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

  // Video Style Transfer — PiAPI Wan VACE V2V
  {
    path: '/tools/video-transform',
    name: 'video-transform',
    component: () => import('@/views/tools/ShortVideo.vue'),
    meta: { requiresAuth: false }
  },

  // Text-to-Video removed — redirect to Image-to-Video
  { path: '/tools/text-to-video', redirect: '/tools/short-video' },

  // Image Upscale — PiAPI image-toolkit (NEW)
  {
    path: '/tools/upscale',
    name: 'upscale',
    component: () => import('@/views/tools/ImageUpscale.vue'),
    meta: { requiresAuth: false }
  },

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

  // ===== Redirects for removed/aliased routes =====
  { path: '/tools/remove-watermark', redirect: '/tools/effects' },
  { path: '/tools/image-translator', redirect: '/tools/effects' },
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

  // Dashboard routes
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('@/views/dashboard/Dashboard.vue'),
    meta: { requiresAuth: true }
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
    path: '/dashboard/social-accounts',
    name: 'social-accounts',
    component: () => import('@/views/dashboard/SocialAccounts.vue'),
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

  // Subscription payment results
  {
    path: '/subscription/success',
    name: 'subscription-success',
    component: () => import('@/views/subscription/SubscriptionSuccess.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/subscription/cancelled',
    name: 'subscription-cancelled',
    component: () => import('@/views/subscription/SubscriptionCancelled.vue')
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
    name: 'admin',
    component: () => import('@/views/admin/AdminDashboard.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/admin/users',
    name: 'admin-users',
    component: () => import('@/views/admin/AdminUsers.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/admin/materials',
    name: 'admin-materials',
    component: () => import('@/views/admin/AdminMaterials.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/admin/moderation',
    name: 'admin-moderation',
    component: () => import('@/views/admin/AdminModeration.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/admin/revenue',
    name: 'admin-revenue',
    component: () => import('@/views/admin/AdminRevenue.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/admin/system',
    name: 'admin-system',
    component: () => import('@/views/admin/AdminSystem.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
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
      next({ name: 'dashboard' })
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
      next({ name: 'dashboard' })
    } else {
      next()
    }
  } else {
    next()
  }
})

export default router
