# VidGo AI Platform - Frontend Architecture

**Version:** 6.0
**Last Updated:** March 5, 2026
**Framework:** Vue 3 + Vite + TypeScript
**Mode:** Dual-Mode — Preset-Only (free) + Real-API with model selection (subscribers)
**Target Audience:** Small businesses (SMB) selling everyday products/services

---

## 1. Design Overview

### 1.1 Layout Structure

```
+-----------------------------------------------------------------------------+
|                         VidGo AI Platform Layout                             |
+-----------------------------------------------------------------------------+
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  |                         Top Navigation Bar (AppHeader)                  | |
|  |  +------+ +-------------------------------------------+ +--------------+| |
|  |  | Logo | | Home | Tools | Topics | Pricing           | | Lang | Login || |
|  |  +------+ +-------------------------------------------+ +--------------+| |
|  +------------------------------------------------------------------------+ |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  |                                                                          | |
|  |                         Main Content Area                               | |
|  |                                                                          | |
|  |  +------------------------------------------------------------------+  | |
|  |  |                    Landing Page / Tool Pages                       |  | |
|  |  |                                                                    |  | |
|  |  |  +------------------------+  +----------------------------------+  |  | |
|  |  |  |   Tool Navigation      |  |       Result Display             |  |  | |
|  |  |  |   - Background Removal |  |       - Before/After             |  |  | |
|  |  |  |   - Product Scene      |  |       - Watermarked Output       |  |  | |
|  |  |  |   - Try On             |  |       - Subscribe CTA            |  |  | |
|  |  |  |   - Room Redesign      |  |                                  |  |  | |
|  |  |  |   - Short Video        |  |                                  |  |  | |
|  |  |  |   - AI Avatar          |  |                                  |  |  | |
|  |  |  |   - Pattern Design     |  |                                  |  |  | |
|  |  |  +------------------------+  +----------------------------------+  |  | |
|  |  |                                                                    |  | |
|  |  +------------------------------------------------------------------+  | |
|  |                                                                          | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  |                         Footer (AppFooter)                              | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### 1.2 Color Scheme

```scss
// VidGo Brand Colors (Tailwind CSS)
$primary-color: #6366F1;      // Indigo - Primary
$primary-light: #818CF8;      // Indigo Light
$primary-dark: #4F46E5;       // Indigo Dark

$secondary-color: #EC4899;    // Pink - Secondary
$accent-color: #10B981;       // Emerald - Accent

// Background Colors (Dark Theme)
$bg-dark: #0F172A;            // Slate 900
$bg-card: #1E293B;            // Slate 800
$bg-hover: #334155;           // Slate 700

// Text Colors
$text-primary: #F8FAFC;       // Slate 50
$text-secondary: #94A3B8;     // Slate 400
$text-muted: #64748B;         // Slate 500

// Status Colors
$success: #22C55E;
$warning: #F59E0B;
$error: #EF4444;
$info: #3B82F6;
```

---

## 2. Project Structure

```
frontend-vue/
├── public/
│   ├── favicon.ico
│   └── logo.svg
│
├── src/
│   ├── api/                         # API Client Layer
│   │   ├── index.ts                 # API exports
│   │   ├── client.ts                # Axios client configuration
│   │   ├── admin.ts                 # Admin API endpoints (stats, costs, active users)
│   │   ├── einvoice.ts              # Taiwan e-invoice API (B2C/B2B issue, void)
│   │   ├── auth.ts                  # Authentication API
│   │   ├── credits.ts               # Credits API
│   │   ├── demo.ts                  # Demo/preset API
│   │   ├── effects.ts               # Effects API
│   │   ├── generation.ts            # Generation API
│   │   ├── interior.ts              # Interior design API
│   │   ├── landing.ts               # Landing page API
│   │   ├── quota.ts                 # Quota API
│   │   ├── subscription.ts          # Subscription API
│   │   ├── uploads.ts               # Subscriber upload + real-API generation
│   │   ├── referrals.ts             # Referral code/stats/apply
│   │   ├── socialMedia.ts           # Social media OAuth + publishing
│   │   └── user.ts                  # User generation history/stats
│   │
│   ├── components/
│   │   ├── atoms/                   # Basic UI components
│   │   │   ├── BaseBadge.vue
│   │   │   ├── BaseButton.vue
│   │   │   ├── BaseInput.vue
│   │   │   ├── BaseSpinner.vue
│   │   │   ├── GlassCard.vue
│   │   │   └── index.ts
│   │   │
│   │   ├── common/                  # Shared components
│   │   │   ├── ImageUploader.vue
│   │   │   ├── LoadingOverlay.vue
│   │   │   └── Toast.vue
│   │   │
│   │   ├── layout/                  # Layout components
│   │   │   ├── AppHeader.vue        # Top navigation
│   │   │   ├── AppFooter.vue        # Footer
│   │   │   └── LanguageSelector.vue # Language switcher
│   │   │
│   │   ├── molecules/               # Composite components
│   │   │   ├── ConfirmModal.vue
│   │   │   ├── CreditBadge.vue
│   │   │   ├── MaterialCard.vue
│   │   │   ├── ToastNotification.vue
│   │   │   ├── UpgradePrompt.vue
│   │   │   └── index.ts
│   │   │
│   │   ├── social/                  # Social media components
│   │   │   └── ShareToSocialModal.vue  # Publish to FB/IG/TikTok
│   │   │
│   │   ├── invoice/                 # E-invoice components
│   │   │   ├── InvoiceCreateForm.vue    # B2C/B2B e-invoice creation form
│   │   │   └── InvoiceVoidDialog.vue    # Invoice void confirmation dialog
│   │   │
│   │   ├── tools/                   # Tool-specific components
│   │   │   ├── BeforeAfterSlider.vue
│   │   │   ├── CreditCost.vue
│   │   │   ├── SubscriberUploadPanel.vue  # Subscriber upload + model selection
│   │   │   ├── ThreeViewer.vue            # 3D model viewer (Three.js)
│   │   │   └── UploadZone.vue
│   │   │
│   │   └── index.ts                 # Component exports
│   │
│   ├── composables/                 # Vue Composition API Hooks
│   │   ├── index.ts                 # Composable exports
│   │   ├── useCredits.ts            # Credit management
│   │   ├── useDemoMode.ts           # Demo mode logic
│   │   ├── useGeoLanguage.ts        # Geo-based language detection
│   │   ├── useLocalized.ts          # Localization helpers
│   │   ├── useResponsive.ts         # Responsive breakpoints
│   │   ├── useToast.ts              # Toast notifications
│   │   ├── useUpload.ts             # File upload logic
│   │   └── useWebSocket.ts          # WebSocket connection
│   │
│   ├── locales/                     # Internationalization
│   │   ├── en.json                  # English
│   │   ├── zh-TW.json               # Traditional Chinese
│   │   ├── ja.json                  # Japanese
│   │   ├── ko.json                  # Korean
│   │   └── es.json                  # Spanish
│   │
│   ├── router/
│   │   └── index.ts                 # Vue Router configuration
│   │
│   ├── stores/                      # Pinia State Management
│   │   ├── index.ts                 # Store exports
│   │   ├── admin.ts                 # Admin state (stats, API costs, active users)
│   │   ├── auth.ts                  # Authentication state
│   │   ├── credits.ts               # Credits state
│   │   ├── generation.ts            # Generation state
│   │   └── ui.ts                    # UI state (modals, toasts)
│   │
│   ├── views/
│   │   ├── LandingPage.vue          # Home page
│   │   ├── Pricing.vue              # Pricing page
│   │   ├── NotFound.vue             # 404 page
│   │   │
│   │   ├── admin/                   # Admin dashboard (stats, costs, profit, active users)
│   │   │   ├── AdminDashboard.vue   # Overview: stats, profit, API costs, sessions
│   │   │   ├── AdminUsers.vue
│   │   │   ├── AdminMaterials.vue
│   │   │   ├── AdminModeration.vue
│   │   │   ├── AdminRevenue.vue
│   │   │   └── AdminSystem.vue
│   │   │
│   │   ├── auth/                    # Authentication pages
│   │   │   ├── Login.vue
│   │   │   ├── Register.vue
│   │   │   ├── VerifyEmail.vue
│   │   │   └── ForgotPassword.vue
│   │   │
│   │   ├── dashboard/               # User dashboard
│   │   │   ├── Dashboard.vue
│   │   │   ├── MyWorks.vue
│   │   │   ├── Invoices.vue             # Invoice history, e-invoice issue/void
│   │   │   ├── Referrals.vue            # Referral program, stats, leaderboard
│   │   │   └── SocialAccounts.vue       # Connected social media accounts
│   │   │
│   │   ├── subscription/            # Payment result pages
│   │   │   ├── ECPayResult.vue           # ECPay payment result
│   │   │   ├── SubscriptionSuccess.vue   # Payment success (order= query)
│   │   │   ├── SubscriptionCancelled.vue # User cancelled payment
│   │   │   └── SubscriptionMockCheckout.vue # Mock payment (dev)
│   │   │
│   │   ├── tools/                   # 8 Core Tool Pages
│   │   │   ├── BackgroundRemoval.vue
│   │   │   ├── ProductScene.vue
│   │   │   ├── TryOn.vue
│   │   │   ├── RoomRedesign.vue
│   │   │   ├── ShortVideo.vue
│   │   │   ├── AIAvatar.vue
│   │   │   ├── PatternDesign.vue
│   │   │   └── ImageEffects.vue
│   │   │
│   │   └── topics/                  # Topic category pages
│   │       ├── PatternTopic.vue
│   │       ├── ProductTopic.vue
│   │       └── VideoTopic.vue
│   │
│   ├── App.vue                      # Root component
│   ├── main.ts                      # Application entry
│   └── vite-env.d.ts                # TypeScript declarations
│
├── .env.development
├── .env.production
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

---

## 3. Route Configuration

### 3.1 Routes Overview

```typescript
// src/router/index.ts

const routes: RouteRecordRaw[] = [
  // ===== Public Routes =====
  { path: '/', name: 'home', component: LandingPage },
  { path: '/pricing', name: 'pricing', component: Pricing },

  // ===== Subscription payment result (Paddle redirects here) =====
  { path: '/subscription/success', name: 'subscription-success', component: SubscriptionSuccess, meta: { requiresAuth: true } },
  { path: '/subscription/cancelled', name: 'subscription-cancelled', component: SubscriptionCancelled },
  { path: '/subscription/mock-checkout', name: 'subscription-mock-checkout', component: SubscriptionMockCheckout, meta: { requiresAuth: true } },

  // ===== Core Tools =====
  { path: '/tools/background-removal', name: 'background-removal', component: BackgroundRemoval },
  { path: '/tools/effects', name: 'effects', component: ImageEffects },
  { path: '/tools/image-transform', name: 'image-transform', component: ImageEffects },
  { path: '/tools/product-scene', name: 'product-scene', component: ProductScene },
  { path: '/tools/product-enhance', name: 'product-enhance', component: ProductScene },
  { path: '/tools/try-on', name: 'try-on', component: TryOn },
  { path: '/tools/room-redesign', name: 'room-redesign', component: RoomRedesign },
  { path: '/tools/short-video', name: 'short-video', component: ShortVideo },
  { path: '/tools/image-to-video', name: 'image-to-video', component: ShortVideo },
  { path: '/tools/video-transform', name: 'video-transform', component: ShortVideo },
  { path: '/tools/product-video', name: 'product-video', component: ShortVideo },
  { path: '/tools/avatar', name: 'avatar', component: AIAvatar },

  // ===== Pattern Tools =====
  { path: '/tools/pattern-generate', name: 'pattern-generate', component: PatternTopic },
  { path: '/tools/pattern-transfer', name: 'pattern-transfer', component: PatternTopic },
  { path: '/tools/pattern-seamless', name: 'pattern-seamless', component: PatternTopic },

  // ===== Topic Pages =====
  { path: '/topics/pattern', name: 'topic-pattern', component: PatternTopic },
  { path: '/topics/product', name: 'topic-product', component: ProductTopic },
  { path: '/topics/video', name: 'topic-video', component: VideoTopic },

  // ===== Auth Routes =====
  { path: '/auth/login', name: 'login', component: Login, meta: { guestOnly: true } },
  { path: '/auth/register', name: 'register', component: Register, meta: { guestOnly: true } },
  { path: '/auth/verify', name: 'verify', component: VerifyEmail },
  { path: '/auth/forgot-password', name: 'forgot-password', component: ForgotPassword },

  // ===== Dashboard Routes (Auth Required) =====
  { path: '/dashboard', name: 'dashboard', component: Dashboard, meta: { requiresAuth: true } },
  { path: '/dashboard/my-works', name: 'my-works', component: MyWorks, meta: { requiresAuth: true } },
  { path: '/dashboard/invoices', name: 'invoices', component: Invoices, meta: { requiresAuth: true } },
  { path: '/dashboard/referrals', name: 'referrals', component: Referrals, meta: { requiresAuth: true } },
  { path: '/dashboard/social-accounts', name: 'social-accounts', component: SocialAccounts, meta: { requiresAuth: true } },

  // ===== Subscription Result Pages =====
  { path: '/subscription/success', name: 'subscription-success', component: SubscriptionSuccess, meta: { requiresAuth: true } },
  { path: '/subscription/cancelled', name: 'subscription-cancelled', component: SubscriptionCancelled },
  { path: '/subscription/mock-checkout', name: 'subscription-mock-checkout', component: SubscriptionMockCheckout, meta: { requiresAuth: true } },
  { path: '/subscription/ecpay-result', name: 'subscription-ecpay-result', component: ECPayResult },

  // ===== Admin Routes (Admin Only) =====
  { path: '/admin', name: 'admin', component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/admin/users', name: 'admin-users', component: AdminUsers, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/admin/materials', name: 'admin-materials', component: AdminMaterials, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/admin/moderation', name: 'admin-moderation', component: AdminModeration, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/admin/revenue', name: 'admin-revenue', component: AdminRevenue, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/admin/system', name: 'admin-system', component: AdminSystem, meta: { requiresAuth: true, requiresAdmin: true } },

  // ===== 404 =====
  { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFound }
]
```

### 3.2 Navigation Guards

```typescript
router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('access_token')
  const isAuthenticated = !!token

  // Auth required routes
  if (to.meta.requiresAuth && !isAuthenticated) {
    next({ name: 'login', query: { redirect: to.fullPath } })
  }
  // Guest only routes
  else if (to.meta.guestOnly && isAuthenticated) {
    next({ name: 'dashboard' })
  }
  // Admin routes
  else if (to.meta.requiresAdmin) {
    const authStore = useAuthStore()
    if (!authStore.isAdmin) {
      next({ name: 'dashboard' })
    } else {
      next()
    }
  }
  else {
    next()
  }
})
```

---

## 4. Composables

### 4.1 Available Composables

```typescript
// src/composables/index.ts

export { useLocalized } from './useLocalized'      // i18n helpers
export { useToast } from './useToast'              // Toast notifications
export { useCredits } from './useCredits'          // Credit management
export { useUpload } from './useUpload'            // File upload
export { useWebSocket } from './useWebSocket'      // WebSocket connection
export { useResponsive } from './useResponsive'    // Responsive breakpoints
export { useGeoLanguage } from './useGeoLanguage'  // Geo-based language
export { useDemoMode } from './useDemoMode'        // Demo mode logic
```

### 4.2 useDemoMode Composable (Preset-Only Mode)

```typescript
// src/composables/useDemoMode.ts

export function useDemoMode(toolType: string) {
  const topics = ref<Topic[]>([])        // Valid topics from API
  const selectedTopic = ref<string>('')  // Current topic filter
  const presets = ref<Preset[]>([])
  const selectedPreset = ref<Preset | null>(null)
  const result = ref<DemoResult | null>(null)
  const isLoading = ref(false)

  // Load valid topics from Topic Registry API
  const loadTopics = async () => {
    const response = await demoApi.getToolTopics(toolType)
    topics.value = response.data.topics
    if (topics.value.length > 0) {
      selectedTopic.value = topics.value[0].id
    }
  }

  // Load available presets from Material DB (filtered by topic)
  const loadPresets = async (topic?: string) => {
    const response = await demoApi.getPresets(toolType, topic || selectedTopic.value)
    presets.value = response.data
    if (presets.value.length > 0) {
      selectedPreset.value = presets.value[0]
    }
  }

  // Use preset - O(1) lookup from Material DB
  const usePreset = async (presetId: string) => {
    isLoading.value = true
    try {
      result.value = await demoApi.usePreset(toolType, presetId)
    } finally {
      isLoading.value = false
    }
  }

  // Download blocked for all users
  const canDownload = computed(() => false)

  // Watch topic change and reload presets
  watch(selectedTopic, (newTopic) => {
    loadPresets(newTopic)
  })

  onMounted(async () => {
    await loadTopics()
    await loadPresets()
  })

  return {
    topics,
    selectedTopic,
    presets,
    selectedPreset,
    result,
    isLoading,
    canDownload,
    usePreset,
  }
}
```

---

## 5. API Layer

### 5.1 API Client Configuration

```typescript
// src/api/client.ts

import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Add auth token to requests
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default client
```

### 5.2 API Modules

```typescript
// src/api/index.ts

export * from './auth'
export * from './demo'
export * from './generation'
export * from './credits'
export * from './admin'
export * from './landing'
export * from './interior'
export * from './subscription'
export * from './quota'
export * from './effects'
```

### 5.3 Demo API (Topic Registry)

```typescript
// src/api/demo.ts

/**
 * Get valid topics for a specific tool type.
 * IMPORTANT: Use this API to get the correct topic list,
 * do NOT hardcode topic values in frontend.
 */
export const getToolTopics = async (toolType: string) => {
  return client.get(`/demo/topics/${toolType}`)
  // Returns: { success: true, tool_type: "ai_avatar", topics: [...] }
}

export const getPresets = async (toolType: string, topic?: string) => {
  const params = topic ? { topic } : {}
  return client.get(`/demo/presets/${toolType}`, { params })
}

export const usePreset = async (toolType: string, presetId: string) => {
  return client.post(`/demo/use-preset`, { tool_type: toolType, preset_id: presetId })
}
```

### 5.4 Topic System Overview

⚠️ **IMPORTANT**: Topics must match what's stored in the Material DB.

| Tool Type | Valid Topics (from API) |
|-----------|-------------------------|
| `background_removal` | drinks, snacks, desserts, meals, packaging, equipment, signage, ingredients |
| `effect` | anime, ghibli, cartoon, oil_painting, watercolor |
| `product_scene` | studio, nature, luxury, minimal, lifestyle, urban, seasonal, holiday |
| `try_on` | casual, formal, sportswear, outerwear, accessories, dresses |
| `room_redesign` | living_room, bedroom, kitchen, bathroom |
| `short_video` | product_showcase, brand_intro, tutorial, promo |
| `ai_avatar` | spokesperson, product_intro, customer_service, social_media |
| `pattern_generate` | seamless, floral, geometric, abstract, traditional |

**Landing Page Topics** (separate system):
- ecommerce, social, brand, app, promo, service

### 5.5 Landing Page Data Sources

The homepage (`LandingPage.vue`) loads data from multiple endpoints:

| Section | Endpoint | Description |
|---------|----------|-------------|
| Works Gallery | `GET /api/v1/demo/landing/works` | Mixed gallery of image + video items from 5 tool types (product_scene, effect, background_removal, short_video, ai_avatar). Video items include `video_url` field and render with hover-to-play. |
| Video Examples | `GET /api/v1/demo/landing/examples` | Short video landing examples |
| Avatar Showcase | `GET /api/v1/demo/presets/ai_avatar` | AI Avatar presets displayed in 3×3 grid (9 items) with hover video preview |
| Feature Highlights | `GET /api/v1/landing/features` | Tool capability highlights |

**Works Gallery video rendering:**
- Items with `video_url` display a play icon overlay and auto-play `<video>` on hover
- Items without `video_url` display as static `<img>` (with before/after for effect tool)

### 5.6 Auth & Email Verification

- **Register** (`auth/Register.vue`): Calls `authApi.register()`; store sets `pendingEmail` and redirects to `/auth/verify`.
- **Verify** (`auth/VerifyEmail.vue`): User enters 6-digit code; `authApi.verifyCode({ email: pendingEmail, code })` is called. Backend returns **AuthResponse** (user, access_token, refresh_token); auth store accepts both `tokens.access`/`tokens.refresh` and flat `access_token`/`refresh_token`, then sets tokens and user so the user is logged in without a separate login.
- **Resend:** `authApi.resendCode(email)` for resending the verification code.

### 5.7 Pricing & Paddle

- **Plans:** `subscriptionApi.getPlans()` → `GET /api/v1/subscriptions/plans`. Backend seeds default plans with `price_monthly`, `price_yearly`, and credits when DB is empty. `Pricing.vue` displays `NT${{ getPrice(plan) }}` and plan features.
- **Subscribe:** `subscriptionApi.subscribe({ plan_id, billing_cycle, payment_method: 'paddle' })` → `POST /subscriptions/subscribe`. When not mock, response includes `checkout_url`; frontend redirects with `window.location.href = result.checkout_url`. When mock, subscription is activated and status is refreshed.
- **Subscription result routes:** After Paddle payment (or mock), user is sent to:
  - `/subscription/success?order=...` — success message and links to Dashboard / Pricing.
  - `/subscription/cancelled` — user cancelled payment; link back to Pricing.
  - `/subscription/mock-checkout?txn=...` — mock flow; auto-redirect to Dashboard.
- **Cancel & Refund:** On Pricing, when user has an active subscription, two actions are shown (with `ConfirmModal` before submitting):
  - **Cancel with Refund** (only when `refund_eligible`, i.e. within 7 days): `subscriptionApi.cancel({ request_refund: true })` — full refund, subscription and credits revoked immediately.
  - **Cancel subscription** (no refund): `subscriptionApi.cancel({ request_refund: false })` — subscription stays active until period end, then no renewal.
  Status and refund eligibility come from `subscriptionApi.getStatus()` (`refund_eligible`, `refund_days_remaining`). Dashboard plan card links to `/pricing` with label "Manage or upgrade plan" so users can cancel or refund from there.

### 5.8 Generation Status API (NEW)

```typescript
// Generation status polling
export const getGenerationStatus = async (taskId: string) => {
  return client.get(`/generate/status/${taskId}`)
  // Returns: { task_id, status: "queued"|"processing"|"completed"|"failed", progress, output }
}
```

### 5.9 Interior 3D API (NEW)

```typescript
// Trellis 3D model generation
export const generate3DModel = async (imageUrl: string) => {
  return client.post('/interior/3d-model', { image_url: imageUrl })
  // Returns: { task_id, model_url: "https://...file.glb" }
}

// Room-type constraints
export const getRoomConstraints = async () => {
  return client.get('/interior/room-constraints')
  // Returns: { constraints: { bathroom: ["bathroom"], kitchen: ["kitchen"], ... } }
}

// Full 3D model generation with parameters (used by RoomRedesign "3D Model" tab)
// interiorApi.generate3DModel(request) — 5-minute timeout
export const generate3DModelFull = async (request: Generate3DRequest) => {
  return client.post('/interior/3d-model', request, { timeout: 300000 })
  // Sends: { image_url, texture_size, mesh_simplify }
  // Returns: Generate3DResponse { model_url }
}

interface Generate3DRequest {
  image_url: string
  texture_size?: number
  mesh_simplify?: number
}

interface Generate3DResponse {
  model_url: string
}
```

### 5.9.1 Effects API — Image Transform (NEW)

```typescript
// effectsApi.imageTransform(data) — Free-form I2I transformation
// Used by ImageEffects "AI Transform" tab
export const imageTransform = async (data: ImageTransformRequest) => {
  return client.post('/tools/image-transform', data)
  // Returns: ApplyStyleResponse
}

interface ImageTransformRequest {
  image_url: string
  prompt: string
  strength: number
  negative_prompt?: string
}
```

### 5.10 Gift Code & Promotions API (NEW)

```typescript
export const redeemGiftCode = async (code: string) => {
  return client.post('/promotions/redeem', { code })
  // Returns: { success, credits_added, message }
}
```

>>>>>>> origin/claude/add-free-trial-mode-B21Bl
---

## 6. State Management (Pinia)

### 6.1 Store Modules

```typescript
// src/stores/index.ts

export { useAuthStore } from './auth'
export { useCreditsStore } from './credits'
export { useGenerationStore } from './generation'
export { useAdminStore } from './admin'
export { useUIStore } from './ui'
```

### 6.2 Auth Store

```typescript
// src/stores/auth.ts

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)

  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.is_admin ?? false)

  const login = async (email: string, password: string) => { ... }
  const register = async (data: RegisterData) => { ... }
  const logout = () => { ... }
  const fetchUser = async () => { ... }

  return { user, token, isAuthenticated, isAdmin, login, register, logout, fetchUser }
})
```

### 6.3 Credits Store

```typescript
// src/stores/credits.ts

export const useCreditsStore = defineStore('credits', () => {
  const balance = ref(0)
  const weeklyCredits = ref(0)
  const paidCredits = ref(0)

  const fetchBalance = async () => { ... }
  const deductCredits = async (amount: number, type: string) => { ... }

  return { balance, weeklyCredits, paidCredits, fetchBalance, deductCredits }
})
```

---

## 7. Tool Pages (8 Core Tools)

### 7.1 Tool Feature Map

```
+-----------------------------------------------------------------------------+
|                           VidGo AI Tool Map                                  |
+-----------------------------------------------------------------------------+
|                                                                              |
|  Tool 1: Background Removal (一鍵白底圖)                                     |
|  ├─ Backend: PiAPI T2I + Rembg / Gemini backup                               |
|  ├─ Route: /tools/background-removal                                         |
|  ├─ Topics: drinks, snacks, desserts, meals, packaging, equipment...         |
|  └─ Mode: Pre-generated examples from Material DB                            |
|                                                                              |
|  Tool 2: Image Effects (圖片風格 / 風格轉換)                                 |
|  ├─ Backend: PiAPI I2I (Flux model, strength 0.60-0.70)                      |
|  ├─ Route: /tools/effects                                                    |
|  ├─ Topics: anime, ghibli, cartoon, oil_painting, watercolor                 |
|  ├─ Tabs:                                                                    |
|  │   ├─ "Style Presets" — Existing preset-based style transfer (default)     |
|  │   └─ "AI Transform" — Free-form I2I transformation with custom prompt     |
|  │       + strength slider. Requires subscription; demo users blocked.       |
|  └─ Mode: Pre-generated before/after gallery, watermarked output             |
|                                                                              |
|  Tool 3: Product Scene (產品攝影靈感)                                        |
|  ├─ Backend: PiAPI T2I (Flux model)                                          |
|  ├─ Route: /tools/product-scene                                              |
|  ├─ Topics: studio, nature, luxury, minimal, lifestyle, urban...             |
|  └─ Mode: Pre-generated gallery, watermarked output                          |
|                                                                              |
|  Tool 4: Virtual Try-On (時尚穿搭展示)                                       |
|  ├─ Backend: Kling AI Try-On via PiAPI (with T2I fallback)                   |
|  ├─ Route: /tools/try-on                                                     |
|  ├─ Topics: casual, formal, dresses, sportswear, outerwear, accessories      |
|  ├─ Model Library: AI-generated full-body models (3 female, 3 male)          |
|  ├─ Preview Mode: When DB has 0 try_on materials, shows clothing             |
|  │   thumbnails from try_prompts; Generate button disabled ("預覽模式")       |
|  └─ Mode: Pre-generated gallery, watermarked output                          |
|                                                                              |
|  Tool 5: Room Redesign (室內設計範例)                                        |
|  ├─ Backend: PiAPI T2I (Flux model) + PiAPI Trellis (3D)                     |
|  ├─ Route: /tools/room-redesign                                              |
|  ├─ Topics: living_room, bedroom, kitchen, bathroom                          |
|  ├─ Tabs:                                                                    |
|  │   ├─ "Redesign" — Existing room redesign (default)                        |
|  │   ├─ "Generate" — Room image generation                                   |
|  │   ├─ "Style Transfer" — Room style transfer                               |
|  │   └─ "3D Model" — Converts 2D room image/design into interactive 3D GLB  |
|  │       model via PiAPI Trellis. Renders with ThreeViewer.vue.              |
|  │       Requires subscription; demo users blocked.                          |
|  └─ Mode: Pre-generated gallery, watermarked output                          |
|                                                                              |
|  Tool 6: Short Video (短影片)                                                |
|  ├─ Backend: Pollo AI I2V (Pixverse v4.5 default)                            |
|  ├─ Route: /tools/short-video                                                |
|  ├─ Topics: product_showcase, brand_intro, tutorial, promo                   |
|  ├─ SMB focus: Everyday products (bubble tea, fried chicken, small shop)     |
|  ├─ Landing Topics: ecommerce, social, brand, app, promo, service            |
|  └─ Mode: Pre-generated videos from Material DB                              |
|                                                                              |
|  Tool 7: AI Avatar (AI數位人)                                                |
|  ├─ Backend: A2E.ai (TTS + Lip-sync)                                         |
|  ├─ Route: /tools/avatar                                                     |
|  ├─ Topics: spokesperson, product_intro, customer_service, social_media      |
|  ├─ Landing Topics: ecommerce, social, brand, app, promo, service            |
|  ├─ Languages: zh-TW (primary), en; scripts clearly sell product/service     |
|  ├─ Gender: Male name on male face, female on female (character-voice match) |
|  └─ Mode: Pre-generated avatar videos from Material DB                       |
|                                                                              |
|  Tool 8: Pattern Design (印花設計)                                           |
|  ├─ Backend: PiAPI T2I (Flux model)                                          |
|  ├─ Route: /tools/pattern-design                                             |
|  ├─ Topics: seamless, floral, geometric, abstract, traditional               |
|  └─ Mode: Pre-generated seamless patterns from Material DB                   |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### 7.2 Backend API Integration

| Tool | API Endpoint | Backend Provider | Pre-generation |
|------|--------------|------------------|----------------|
| Background Removal | `/api/v1/demo/presets/background_removal` | PiAPI T2I | Yes |
| Image Effects | `/api/v1/demo/presets/effect` | PiAPI I2I (style transfer) | Yes |
| Product Scene | `/api/v1/demo/presets/product_scene` | PiAPI T2I | Yes |
| Try-On | `/api/v1/demo/presets/try_on` | Kling AI + T2I fallback | Yes |
| Room Redesign | `/api/v1/demo/presets/room_redesign` | PiAPI T2I | Yes |
| Short Video | `/api/v1/demo/presets/short_video` | Pollo AI I2V | Yes |
| AI Avatar | `/api/v1/demo/presets/ai_avatar` | A2E.ai TTS+Lipsync | Yes |
| Pattern Design | `/api/v1/demo/presets/pattern_generate` | PiAPI T2I | Yes |

### 7.2 Tool Page Template (Preset-Only Mode)

```vue
<!-- Example: src/views/tools/BackgroundRemoval.vue -->
<template>
  <div class="tool-page">
    <h1>{{ $t('tools.backgroundRemoval.title') }}</h1>

    <!-- Preset Selection -->
    <div class="preset-grid">
      <div
        v-for="preset in presets"
        :key="preset.id"
        class="preset-card"
        :class="{ selected: selectedPreset?.id === preset.id }"
        @click="selectPreset(preset)"
      >
        <img :src="preset.thumbnail_url" :alt="preset.topic" />
        <span>{{ preset.topic_zh || preset.topic }}</span>
      </div>
    </div>

    <!-- Generate Button -->
    <button
      class="btn-generate"
      :disabled="isLoading || !selectedPreset"
      @click="generate"
    >
      {{ isLoading ? $t('common.loading') : $t('common.viewResult') }}
    </button>

    <!-- Result Display -->
    <div v-if="result" class="result-section">
      <div class="before-after">
        <img :src="result.input_url" alt="Before" />
        <img :src="result.result_watermarked_url" alt="After (Watermarked)" />
      </div>

      <!-- Download Blocked -->
      <div class="download-blocked">
        <button disabled>{{ $t('common.subscribeToDownload') }}</button>
        <router-link to="/pricing">{{ $t('common.viewPlans') }}</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useDemoMode } from '@/composables/useDemoMode'

const {
  presets,
  selectedPreset,
  result,
  isLoading,
  usePreset,
} = useDemoMode('background_removal')

const selectPreset = (preset: Preset) => {
  selectedPreset.value = preset
}

const generate = async () => {
  if (selectedPreset.value) {
    await usePreset(selectedPreset.value.id)
  }
}
</script>
```

---

## 8. Internationalization (i18n)

### 8.1 Supported Languages

| Code | Language | File |
|------|----------|------|
| `en` | English | `en.json` |
| `zh-TW` | Traditional Chinese | `zh-TW.json` |
| `ja` | Japanese | `ja.json` |
| `ko` | Korean | `ko.json` |
| `es` | Spanish | `es.json` |

### 8.2 Language Detection

```typescript
// src/composables/useGeoLanguage.ts

export function useGeoLanguage() {
  const detectLanguage = async () => {
    // 1. Check saved preference
    const saved = localStorage.getItem('language')
    if (saved) return saved

    // 2. Check browser language
    const browserLang = navigator.language
    if (browserLang.startsWith('zh')) return 'zh-TW'
    if (browserLang.startsWith('ja')) return 'ja'
    if (browserLang.startsWith('ko')) return 'ko'
    if (browserLang.startsWith('es')) return 'es'

    return 'en'
  }

  return { detectLanguage }
}
```

---

## 9. Preset-Only Mode

**Demo/Trial flow:** Users try default AI functions by selecting presets. Backend returns pre-generated results from Material DB—no runtime AI API calls. Examples are correctly linked (e.g., Effect tool: before = T2I image, after = I2I transform of that same image).

### 9.1 Access Control Matrix

| Feature | Free / Anonymous | Subscriber |
|---------|-----------------|------------|
| View preset options | Yes | Yes |
| Select preset | Yes | Yes |
| Enter custom text | No | No (preset mode) |
| View watermarked result | Yes | Yes (+ full-quality) |
| Download preset result | No | Yes (no watermark) |
| Upload own material | No | Yes |
| Select AI model | No | Yes |
| Real-API generation | No | Yes (credits deducted) |
| Referral program | Earn credits | Earn credits |

### 9.2 User Flow

```
+---------------------------------------------------------------------+
|                     PRESET-ONLY USER FLOW                            |
+---------------------------------------------------------------------+
|                                                                      |
|  1. User visits tool page (e.g., /tools/background-removal)          |
|                                                                      |
|  2. Frontend loads presets from /api/v1/demo/presets/{tool_type}     |
|     └── Returns list of pre-generated materials                      |
|                                                                      |
|  3. User selects a preset (clicks on thumbnail)                      |
|                                                                      |
|  4. User clicks "View Result" button                                 |
|                                                                      |
|  5. Frontend calls /api/v1/demo/use-preset                           |
|     └── O(1) lookup by material ID                                   |
|     └── NO external API calls                                        |
|                                                                      |
|  6. Result displayed with watermark                                  |
|     └── Download button disabled                                     |
|     └── "Subscribe for full access" CTA shown                        |
|                                                                      |
+---------------------------------------------------------------------+
```

---

## 10. Environment Configuration

### 10.1 Development

```bash
# .env.development
VITE_API_BASE_URL=
VITE_WS_URL=ws://localhost:8001/ws
```

### 10.2 Production

```bash
# .env.production
VITE_API_BASE_URL=https://api.vidgo.ai
VITE_WS_URL=wss://api.vidgo.ai/ws
VITE_GA_ID=G-XXXXXXXXXX
```

---

## 11. Build & Deploy

```bash
# Install dependencies
npm install

# Development server
npm run dev

# Production build
npm run build

# Preview production build
npm run preview

# Type check
npm run type-check

# Lint
npm run lint
```

---

## 12. Full Stack Testing

### 12.1 Development Setup

```bash
# Start all services
docker-compose up -d

# Check service health
docker-compose ps

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 12.2 Access URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:8501 | Vue 3 application |
| Backend API | http://localhost:8001 | FastAPI server |
| API Docs | http://localhost:8001/docs | Swagger UI |
| Mailpit | http://localhost:8025 | Email testing UI |

### 12.3 Test Flow

```
+----------------------------------------------------------+
|                   FULL STACK TEST FLOW                    |
+----------------------------------------------------------+
|                                                          |
|  1. START SERVICES                                       |
|     docker-compose up -d                                 |
|                                                          |
|  2. VERIFY BACKEND                                       |
|     curl http://localhost:8001/health                    |
|     # Expected: {"status": "healthy"}                    |
|                                                          |
|  3. VERIFY FRONTEND                                      |
|     open http://localhost:8501                           |
|     # Expected: Landing page loads with videos/avatars   |
|                                                          |
|  4. TEST TOOL PAGES                                      |
|     /tools/background-removal → Select preset → View     |
|     /tools/product-scene → Select topic → View           |
|     /tools/short-video → Select video → Play             |
|     /tools/avatar → Select avatar → Play                 |
|                                                          |
|  5. TEST API ENDPOINTS                                   |
|     GET /api/v1/demo/presets/short_video                 |
|     GET /api/v1/landing/materials                        |
|                                                          |
+----------------------------------------------------------+
```

### 12.4 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Frontend blank | Backend not ready | Wait for backend health check |
| No materials | Pre-generation skipped | Run `python -m scripts.main_pregenerate` |
| API 401 | Missing auth token | Check localStorage for access_token |
| Videos not playing | CORS or URL issues | Check browser console for errors |

---

## 13. Virtual Try-On with Model Library

### 13.1 Model Library Overview

The Virtual Try-On feature uses an AI-generated Model Library to provide full-body models that meet Kling AI API requirements.

```
+---------------------------------------------------------------------+
|                     MODEL LIBRARY ARCHITECTURE                       |
+---------------------------------------------------------------------+
|                                                                      |
|  PRE-GENERATION PHASE (Backend)                                      |
|  ├─ Generate 6 full-body models (3 female, 3 male)                   |
|  ├─ Store in /static/models/{gender}/                                |
|  └─ Requirements: Full-body, visible torso, neutral background       |
|                                                                      |
|  TRY-ON GENERATION                                                   |
|  ├─ Load model from Model Library                                    |
|  ├─ Attempt Kling AI Virtual Try-On API                              |
|  │   └─ If fails: Fallback to T2I with model+garment prompt          |
|  └─ Store result in Material DB                                      |
|                                                                      |
|  FRONTEND DISPLAY                                                    |
|  ├─ Show pre-generated try-on results                                |
|  ├─ Before/After comparison                                          |
|  └─ Watermarked output                                               |
|                                                                      |
+---------------------------------------------------------------------+
```

### 13.2 Model Types

| ID | Gender | Description |
| --- | --- | --- |
| female-fullbody-1 | Female | Young Asian woman - casual white tank top |
| female-fullbody-2 | Female | European woman - business casual |
| female-fullbody-3 | Female | Multi-ethnic woman - athleisure |
| male-fullbody-1 | Male | Asian man - casual polo shirt |
| male-fullbody-2 | Male | European man - smart casual |
| male-fullbody-3 | Male | Multi-ethnic man - urban streetwear |

### 13.3 API Flow

```
Frontend                    Backend                     External APIs
   │                           │                             │
   │ GET /presets/try_on       │                             │
   │──────────────────────────>│                             │
   │                           │                             │
   │   [Material DB Lookup]    │                             │
   │                           │                             │
   │<─────────────────────────-│                             │
   │   Pre-generated results   │                             │
   │   (watermarked)           │                             │
   │                           │                             │
   │   Display in gallery      │                             │
   │   with model + garment    │                             │
```

---

## 14. Pattern Design Feature

### 14.1 Overview

Pattern Design generates seamless textile patterns for fashion and interior design applications.

### 14.2 Topics

| Topic ID | Chinese Name | Description |
| --- | --- | --- |
| seamless | 無縫圖案 | Seamless repeating patterns |
| floral | 花卉印花 | Floral and botanical patterns |
| geometric | 幾何圖案 | Geometric and abstract shapes |
| abstract | 抽象藝術 | Abstract artistic patterns |
| traditional | 傳統紋樣 | Traditional cultural patterns |

### 14.3 Backend Integration

- **Tool Type**: `pattern_generate`
- **API Endpoint**: `/api/v1/demo/presets/pattern_generate`
- **Topics API**: `/api/v1/demo/topics/pattern_generate`
- **Provider**: PiAPI T2I (Flux model)
- **Output**: Seamless tileable patterns

---

---

## 15. Key Components

### 15.1 SubscriberUploadPanel

Reusable drop-in component added to all tool pages. Shows a "Subscribe to unlock" gate for free users.

```vue
<SubscriberUploadPanel
  :tool-type="'background_removal'"
  :is-subscribed="isSubscribed"
  :show-prompt="true"
  @result="handleResult"
/>
```

Features: Model selector, drag-and-drop upload, progress bar, status polling, download button.

### 15.2 ThreeViewer (3D Model Viewer)

Three.js-based GLB model viewer for interior design 3D outputs.
- Location: `src/components/tools/ThreeViewer.vue`
- Used by: `RoomRedesign.vue` (3D Model tab)
- GLTFLoader, OrbitControls, auto-rotation
- Dependencies: `three`, `@types/three`

### 15.3 ShareToSocialModal

Modal for publishing generations to connected social media accounts.
- Location: `src/components/social/ShareToSocialModal.vue`
- Platforms: Facebook, Instagram, TikTok
- Shows connected accounts, allows multi-platform publishing

### 15.4 Referrals Dashboard

Route: `/dashboard/referrals` — `views/dashboard/Referrals.vue`
- Stats cards (invited count, credits earned)
- Shareable referral link (LINE, X, Facebook)
- Apply referral code form
- Top 10 leaderboard

### 15.5 Social Accounts Dashboard

Route: `/dashboard/social-accounts` — `views/dashboard/SocialAccounts.vue`
- Connect/disconnect social media accounts
- OAuth flow for Facebook, Instagram, TikTok

### 15.6 API Clients

```typescript
// src/api/uploads.ts
uploadsApi.getToolModels(toolType)
uploadsApi.uploadAndGenerate(...)
uploadsApi.getUploadStatus(uploadId)
uploadsApi.getDownloadUrl(uploadId)

// src/api/referrals.ts
referralsApi.getCode()
referralsApi.getStats()
referralsApi.applyCode(code)
referralsApi.getLeaderboard()

// src/api/socialMedia.ts
socialMediaApi.getAccounts()
socialMediaApi.disconnectAccount(platform)
socialMediaApi.getOAuthUrl(platform)
socialMediaApi.publish(generationId, platforms)

// src/api/user.ts
userApi.getGenerations(params)
userApi.getGenerationDetail(id)
userApi.downloadGeneration(id)
userApi.deleteGeneration(id)
userApi.getStats()
```

---

*Document Version: 6.0*
*Last Updated: March 5, 2026*
*Mode: Dual-Mode — Preset-Only (free) + Real-API with model selection (subscribers)*
*Target: SMB (small businesses selling everyday products/services)*
