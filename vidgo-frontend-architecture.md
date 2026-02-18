# VidGo AI Platform - Frontend Architecture

**Version:** 5.0
**Last Updated:** February 18, 2026
**Framework:** Vue 3 + Vite + TypeScript
**Mode:** Hybrid (Free Trial Presets + Tier-based Generation)
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
│   │   ├── admin.ts                 # Admin API endpoints
│   │   ├── auth.ts                  # Authentication API
│   │   ├── credits.ts               # Credits API
│   │   ├── demo.ts                  # Demo/preset API
│   │   ├── effects.ts               # Effects API
│   │   ├── generation.ts            # Generation API
│   │   ├── interior.ts              # Interior design API
│   │   ├── landing.ts               # Landing page API
│   │   ├── quota.ts                 # Quota API
│   │   └── subscription.ts          # Subscription API
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
│   │   │   ├── GenerationProgress.vue  # Generation queue/progress display
│   │   │   ├── InsufficientCreditsModal.vue # "點數不足" credit lockout modal
│   │   │   ├── MaterialCard.vue
│   │   │   ├── ToastNotification.vue
│   │   │   ├── UpgradePrompt.vue
│   │   │   └── index.ts
│   │   │
│   │   ├── tools/                   # Tool-specific components
│   │   │   ├── BeforeAfterSlider.vue
│   │   │   ├── CreditCost.vue
│   │   │   ├── ThreeViewer.vue         # Three.js GLB 3D model viewer
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
│   │   ├── admin.ts                 # Admin state
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
│   │   ├── admin/                   # Admin dashboard
│   │   │   ├── AdminDashboard.vue
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
│   │   │   ├── ContactUs.vue           # Contact form
│   │   │   ├── Dashboard.vue
│   │   │   ├── GiftCodes.vue           # Gift code redemption
│   │   │   ├── Invoices.vue             # Invoice history & download
│   │   │   ├── MyWorks.vue
│   │   │   └── Profile.vue             # User profile editing
│   │   │
│   │   ├── subscription/            # Paddle redirect result pages
│   │   │   ├── SubscriptionSuccess.vue   # Payment success (order= query)
│   │   │   ├── SubscriptionCancelled.vue # User cancelled payment
│   │   │   └── SubscriptionMockCheckout.vue # Mock payment complete → redirect dashboard
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

  // ===== 8 Core Tools =====
  { path: '/tools/background-removal', name: 'background-removal', component: BackgroundRemoval },
  { path: '/tools/effects', name: 'effects', component: ImageEffects },
  { path: '/tools/product-scene', name: 'product-scene', component: ProductScene },
  { path: '/tools/try-on', name: 'try-on', component: TryOn },
  { path: '/tools/room-redesign', name: 'room-redesign', component: RoomRedesign },
  { path: '/tools/short-video', name: 'short-video', component: ShortVideo },
  { path: '/tools/avatar', name: 'avatar', component: AIAvatar },
  { path: '/tools/pattern-design', name: 'pattern-design', component: PatternDesign },

  // ===== Video Tool Aliases =====
  { path: '/tools/image-to-video', redirect: '/tools/short-video' },
  { path: '/tools/video-transform', redirect: '/tools/short-video' },
  { path: '/tools/product-video', redirect: '/tools/short-video' },

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
  { path: '/dashboard/gift-codes', name: 'gift-codes', component: GiftCodes, meta: { requiresAuth: true } },
  { path: '/dashboard/profile', name: 'profile', component: Profile, meta: { requiresAuth: true } },
  { path: '/dashboard/contact', name: 'contact-us', component: ContactUs, meta: { requiresAuth: true } },

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
export { useTrialMode } from './useTrialMode'        // Free trial + generation mode (replaces useDemoMode for generation)
export { useGenerationProgress } from './useGenerationProgress'  // Generation queue/progress tracking
```

### 4.2 useDemoMode Composable (Preset Browsing Only)

> **Note:** `useDemoMode` still exists for preset browsing (Material DB lookups). For live generation with credit checking, use the new `useTrialMode` composable instead.

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
export * from './tools'              // Tool operations (with credit check)
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
```

### 5.10 Gift Code & Promotions API (NEW)

```typescript
export const redeemGiftCode = async (code: string) => {
  return client.post('/promotions/redeem', { code })
  // Returns: { success, credits_added, message }
}
```

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
// src/stores/credits.ts (updated)

export const useCreditsStore = defineStore('credits', () => {
  const balance = ref(0)
  const bonusCredits = ref(0)
  const purchasedCredits = ref(0)
  const showInsufficientCreditsModal = ref(false)

  const fetchBalance = async () => { ... }
  const deductCredits = async (amount: number, type: string) => { ... }
  const openInsufficientModal = () => { showInsufficientCreditsModal.value = true }
  const closeInsufficientModal = () => { showInsufficientCreditsModal.value = false }

  return { balance, bonusCredits, purchasedCredits, showInsufficientCreditsModal, fetchBalance, deductCredits, openInsufficientModal, closeInsufficientModal }
})
```

### 6.4 Generation Store

```typescript
// src/stores/generation.ts (updated)

export const useGenerationStore = defineStore('generation', () => {
  const currentTask = ref<GenerationTask | null>(null)
  const isProcessing = computed(() => ['uploading', 'processing', 'polling'].includes(currentTask.value?.status))

  function startTask(toolType: string, creditCost: number): string { ... }
  function updateStatus(status: GenerationStatus) { ... }
  function startPolling(taskId: string) { ... }  // Polls /generate/status/{taskId} every 3s

  return { currentTask, isProcessing, startTask, updateStatus, startPolling }
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
|  ├─ Backend: PiAPI T2I (Flux model)                                          |
|  ├─ Route: /tools/room-redesign                                              |
|  ├─ Topics: living_room, bedroom, kitchen, bathroom                          |
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

### 7.3 Tier-based Generation Quality (NEW)

| Tool | Free Tier (720P) | Paid Tier (1080P) |
|------|------------------|-------------------|
| Background Removal | 512×512, watermarked | 1024×1024, original |
| Product Scene | 512×512, watermarked | 1024×1024, original |
| Room Redesign | 720P, style change only | 1080P, style change only |
| Short Video | 720P, 5s max | 1080P, 15s max |
| AI Avatar | 720P, 30s, no audio | 1080P, 120s, with audio |
| Effects | 512×512 | 1024×1024 |
| Try-On | 512×512 | 1024×1024 |
| Pattern Design | 512×512 | 1024×1024 |

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

## 9. Free Trial & Preset Mode (Updated)

**Hybrid flow:** Users can both browse presets AND generate new content (with credit deduction).

### 9.1 Access Control Matrix (Updated)

| Feature | Guest (No Login) | Free Trial (Logged In, No Payment) | Paid (Credits/Subscription) |
|---------|-------------------|-------------------------------------|---------------------------|
| View presets | Yes | Yes | Yes |
| Select preset | Yes | Yes | Yes |
| View watermarked result | Yes | Yes | Yes |
| Live generation | No | Yes (720P, limited) | Yes (1080P, full) |
| Download | No | No (watermarked) | Yes (original) |
| API calls | No | Yes (free tier params) | Yes (paid tier params) |
| Starting credits | — | 40 bonus points | Purchase 100 pts for NT$99 |

### 9.2 User Flow (Updated)

```
+---------------------------------------------------------------------+
|                     HYBRID USER FLOW                                 |
+---------------------------------------------------------------------+
|                                                                      |
|  GUEST (Not logged in):                                              |
|  1. Browse presets from Material DB                                   |
|  2. View watermarked results only                                    |
|  3. Prompt to register for free 40 points                            |
|                                                                      |
|  FREE TRIAL (Logged in, 40 bonus points):                           |
|  1. Browse presets + generate new content                            |
|  2. Generation: 720P, 5s video, no audio, watermarked               |
|  3. Credit deducted per generation (20-35 pts)                       |
|  4. When 0 credits → InsufficientCreditsModal → /pricing             |
|                                                                      |
|  PAID (Purchased credits or subscription):                           |
|  1. Full access: presets + premium generation                        |
|  2. Generation: 1080P, 15s video, with audio, original quality       |
|  3. Download enabled                                                  |
|  4. Priority queue                                                    |
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

## 15. New Components (Free Trial System)

### 15.1 InsufficientCreditsModal

Modal shown when user has insufficient credits for generation.
- Trigger: API returns HTTP 402 with `error: "insufficient_credits"`
- Message: "點數不足，請儲值" (Insufficient credits, please top up)
- Action: "前往儲值" button → navigates to `/pricing`
- Shows: required credits vs current balance

### 15.2 GenerationProgress

Real-time generation progress display component.
- States: 排隊中... → 生成中... 50% → 完成
- Polls `/generate/status/{task_id}` every 3 seconds
- Estimated time: 3-8 minutes
- Shows credit cost that will be deducted

### 15.3 ThreeViewer (3D Model Viewer)

Three.js-based GLB model viewer for interior design 3D outputs.
- Uses GLTFLoader to load .glb files from Trellis API
- OrbitControls for rotation, zoom, pan
- Auto-rotation on load
- Responsive container sizing
- Dependencies: `three`, `@types/three`

### 15.4 Dashboard Sidebar Navigation

Full sidebar navigation for authenticated users:
1. 儀表板 (Dashboard) → `/dashboard`
2. 我的創作 (My Works) → `/dashboard/my-works`
3. 會員帳單 (Invoices) → `/dashboard/invoices`
4. 禮品碼 (Gift Codes) → `/dashboard/gift-codes`
5. 個人資料 (Profile) → `/dashboard/profile`
6. 聯絡我們 (Contact Us) → `/dashboard/contact`

Dashboard shows: "剩餘 X 點" (remaining credits display)

---

*Document Version: 5.0*
*Last Updated: February 18, 2026*
*Mode: Hybrid (Free Trial Presets + Tier-based Generation)*
*Target: SMB (small businesses selling everyday products/services)*
