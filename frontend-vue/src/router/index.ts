import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/LandingPage.vue')
  },
  // ===== 5 Core Tools (per ARCHITECTURE_FINAL.md) =====
  // Tool 1: Background Removal (一鍵白底圖)
  {
    path: '/tools/background-removal',
    name: 'background-removal',
    component: () => import('@/views/tools/BackgroundRemoval.vue'),
    meta: { requiresAuth: false }
  },
  // Tool 2: Product Scene (商品場景圖)
  {
    path: '/tools/product-scene',
    name: 'product-scene',
    component: () => import('@/views/tools/ProductScene.vue'),
    meta: { requiresAuth: false }
  },
  // Tool 3: AI Try-On (AI試穿)
  {
    path: '/tools/try-on',
    name: 'try-on',
    component: () => import('@/views/tools/TryOn.vue'),
    meta: { requiresAuth: false }
  },
  // Tool 4: Room Redesign (毛坯精裝)
  {
    path: '/tools/room-redesign',
    name: 'room-redesign',
    component: () => import('@/views/tools/RoomRedesign.vue'),
    meta: { requiresAuth: false }
  },
  // Tool 5: Short Video (短影片)
  {
    path: '/tools/short-video',
    name: 'short-video',
    component: () => import('@/views/tools/ShortVideo.vue'),
    meta: { requiresAuth: false }
  },
  // Tool: Product Enhancement (產品增強)
  {
    path: '/tools/product-enhance',
    name: 'product-enhance',
    component: () => import('@/views/tools/ProductScene.vue'),
    meta: { requiresAuth: false }
  },
  // Video tools (redirects to short-video for now)
  {
    path: '/tools/image-to-video',
    name: 'image-to-video',
    component: () => import('@/views/tools/ShortVideo.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/tools/video-transform',
    name: 'video-transform',
    component: () => import('@/views/tools/ShortVideo.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/tools/product-video',
    name: 'product-video',
    component: () => import('@/views/tools/ShortVideo.vue'),
    meta: { requiresAuth: false }
  },
  // Tool 6: AI Avatar (AI數位人)
  {
    path: '/tools/avatar',
    name: 'avatar',
    component: () => import('@/views/tools/AIAvatar.vue'),
    meta: { requiresAuth: false }
  },
  // Pattern tools
  {
    path: '/tools/pattern-generate',
    name: 'pattern-generate',
    component: () => import('@/views/topics/PatternTopic.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/tools/pattern-transfer',
    name: 'pattern-transfer',
    component: () => import('@/views/topics/PatternTopic.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/tools/pattern-seamless',
    name: 'pattern-seamless',
    component: () => import('@/views/topics/PatternTopic.vue'),
    meta: { requiresAuth: false }
  },
  // Topic pages (navigation categories)
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
  // Pricing
  {
    path: '/pricing',
    name: 'pricing',
    component: () => import('@/views/Pricing.vue')
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
    next({ name: 'dashboard' })
  } else if (to.meta.requiresAdmin) {
    // For admin routes, we need to check user's admin status
    // This requires the auth store to be initialized
    const { useAuthStore } = await import('@/stores/auth')
    const authStore = useAuthStore()

    // Fetch user if not already loaded
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
