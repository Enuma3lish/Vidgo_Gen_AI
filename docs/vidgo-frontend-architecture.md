# VidGo AI Platform - Frontend Architecture

> Last updated: 2026-06-12

**Version:** 8.0
**Last Updated:** June 12, 2026
**Framework:** Vue 3 + Vite + TypeScript
**Mode:** Real-API tools (PiAPI / rembg / A2E / Vertex) with demo gating + credit-based billing
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
|  |  | Logo | | Home | Tools (mega-dropdown) | Pricing    | | Lang | Login || |
|  |  +------+ +-------------------------------------------+ +--------------+| |
|  |  Tools dropdown renders the shared toolHub catalog (data/toolHub.ts):   | |
|  |  5 category groups + a localStorage-backed "Recently Used" row.         | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  |                         Main Content Area                               | |
|  |                                                                          | |
|  |  Most tool pages use the shared PiapiPlayground layout                   | |
|  |  (components/tools/PiapiPlayground.vue):                                 | |
|  |                                                                          | |
|  |  +------------------------+  +----------------------------------+       | |
|  |  | Left: Configuration    |  | Right: Result + Status           |       | |
|  |  | - Model / task type    |  | - Status pill (idle/running/...) |       | |
|  |  | - Prompt / params      |  | - Result preview                 |       | |
|  |  | - Image upload         |  | - Download / Regenerate          |       | |
|  |  | - Generate (credits)   |  |                                  |       | |
|  |  +------------------------+  +----------------------------------+       | |
|  |  Below: Examples gallery | Pricing block | FAQ                           | |
|  |                                                                          | |
|  |  Exceptions: ProductScene.vue is the tool-hub launcher page,             | |
|  |  RoomRedesign.vue uses a ReRoom.ai-style "inspire first" layout, and     | |
|  |  InteriorTemplates.vue uses a Pippit-style template gallery.             | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  |                         Footer (AppFooter)                              | |
|  +------------------------------------------------------------------------+ |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### 1.2 Color Scheme

The tool pages share a fixed dark palette (owner directive: "ui color like
before but change ux like piapi" — palette stays even when layouts change):

```scss
// VidGo Tool-UI Palette
$bg-page: #0a0a0f;            // Page background
$bg-panel: #141420;           // Panels / cards
$accent-from: #7c3aed;        // Violet gradient start (buttons, accents)
$accent-to: #a78bfa;          // Violet gradient end

// Text Colors
$text-primary: #f5f5fa;
$text-secondary: #94949f;     // (also #9494b0 in dashboard tabs)
$text-muted: #6b6b7a;

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
│   │   ├── client.ts                # Axios client (15-min timeout, token refresh)
│   │   ├── admin.ts                 # Admin API (stats, costs, active users) + admin WS
│   │   ├── auth.ts                  # Authentication API
│   │   ├── credits.ts               # Credits API
│   │   ├── demo.ts                  # Demo/inspiration/showcase API
│   │   ├── effects.ts               # Effects API
│   │   ├── einvoice.ts              # Taiwan e-invoice (B2C/B2B issue, void, preferences)
│   │   ├── generation.ts            # Generation API
│   │   ├── interior.ts              # Interior design API (redesign, floorplan, isometric, 3D, growth video)
│   │   ├── landing.ts               # Landing page API
│   │   ├── quota.ts                 # Quota API
│   │   ├── referrals.ts             # Referral code/stats/apply
│   │   ├── socialMedia.ts           # Social media OAuth + publishing
│   │   ├── subscription.ts          # Subscription API (PayPal / ECPay)
│   │   ├── tools.ts                 # Real tool endpoints (/api/v1/tools/*)
│   │   ├── uploads.ts               # Subscriber upload + real-API generation
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
│   │   │   ├── AppHeader.vue        # Top navigation + Tools mega-dropdown (toolHub catalog)
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
│   │   ├── admin/                   # Admin dashboard components
│   │   │   ├── DateRangeSelector.vue    # Date range filter (7D, 30D, 90D, 1Y, Custom)
│   │   │   └── charts/                  # Chart.js chart components (vue-chartjs)
│   │   │       ├── LineChart.vue
│   │   │       ├── BarChart.vue
│   │   │       └── DoughnutChart.vue
│   │   │
│   │   ├── social/                  # Social media components
│   │   │   └── ShareToSocialModal.vue   # Publish to FB/IG/TikTok/YouTube
│   │   │
│   │   ├── invoice/                 # E-invoice components
│   │   │   ├── InvoiceCreateForm.vue    # B2C/B2B e-invoice creation form
│   │   │   ├── InvoicePrefsForm.vue     # 發票設定 — carrier / 統編 / donation prefs (NEW 2026-06-12)
│   │   │   └── InvoiceVoidDialog.vue    # Invoice void confirmation dialog
│   │   │
│   │   ├── tools/                   # Tool-specific components
│   │   │   ├── AtmosphereControls.vue       # Lighting / Kelvin / material knobs (NEW 2026-06-12)
│   │   │   ├── BeforeAfterSlider.vue
│   │   │   ├── CreditCost.vue
│   │   │   ├── ExampleGallery.vue           # Example cards under tool pages
│   │   │   ├── PiapiPlayground.vue          # Shared two-column tool layout (pp-* styles)
│   │   │   ├── ProToolHero.vue
│   │   │   ├── SubscriberUploadPanel.vue    # Subscriber upload + model selection
│   │   │   ├── ThreeViewer.vue              # 3D model viewer (Three.js)
│   │   │   ├── UploadZone.vue
│   │   │   ├── VideoFaithfulnessControls.vue # Camera-move + subject-lock (NEW 2026-06-12)
│   │   │   └── VisionFusionInfo.vue
│   │   │
│   │   └── index.ts                 # Component exports
│   │
│   ├── composables/                 # Vue Composition API Hooks
│   │   ├── index.ts                 # Composable exports
│   │   ├── useCredits.ts            # Credit management
│   │   ├── useDemoMode.ts           # Demo-user gating + input library + effect catalog
│   │   ├── useExamplePrefill.ts     # Click-an-example → pre-fill tool form
│   │   ├── useGeoLanguage.ts        # Geo-based language detection (server-side)
│   │   ├── useLocalized.ts          # Localization helpers (5-language L() picker)
│   │   ├── usePromptLibrary.ts      # Curated prompt library (data/prompt_library.json)
│   │   ├── useRecaptcha.ts          # reCAPTCHA integration
│   │   ├── useResponsive.ts         # Responsive breakpoints
│   │   ├── useSeo.ts                # applySeo / hreflang alternates (used by router)
│   │   ├── useSessionHeartbeat.ts   # Session heartbeat
│   │   ├── useToast.ts              # Toast notifications
│   │   ├── useUpload.ts             # File upload logic
│   │   └── useWebSocket.ts          # WebSocket connection
│   │
│   ├── data/                        # Static catalogs
│   │   ├── prompt_library.json      # Curated prompts per tool (usePromptLibrary)
│   │   ├── toolExamples.ts          # Example cards per tool
│   │   └── toolHub.ts               # Shared tool-hub catalog (31 tiles, 5 categories)
│   │
│   ├── locales/                     # Internationalization
│   │   ├── en.json                  # English
│   │   ├── zh-TW.json               # Traditional Chinese
│   │   ├── ja.json                  # Japanese
│   │   ├── ko.json                  # Korean
│   │   └── es.json                  # Spanish
│   │
│   ├── router/
│   │   └── index.ts                 # Vue Router configuration + ROUTE_SEO catalog
│   │
│   ├── stores/                      # Pinia State Management
│   │   ├── index.ts                 # Store exports
│   │   ├── admin.ts                 # Admin state (stats, API costs, active users, refreshAll)
│   │   ├── auth.ts                  # Authentication state
│   │   ├── branding.ts              # Branding state (admin-managed brand assets)
│   │   ├── credits.ts               # Credits state
│   │   ├── generation.ts            # Generation state
│   │   └── ui.ts                    # UI state (modals, toasts)
│   │
│   ├── views/
│   │   ├── LandingPage.vue          # Home page
│   │   ├── Pricing.vue              # Pricing page
│   │   ├── InspirationGallery.vue   # Inspiration Gallery
│   │   ├── StaticInfoPage.vue       # about/contact/terms/privacy/... static pages
│   │   ├── NotFound.vue             # 404 page
│   │   │
│   │   ├── admin/                   # Admin dashboard (nested under AdminLayout)
│   │   │   ├── AdminLayout.vue      # Shell with nested children routes
│   │   │   ├── AdminDashboard.vue   # Overview: Chart.js charts, date range, CSV export
│   │   │   ├── AdminUsers.vue
│   │   │   ├── AdminMaterials.vue
│   │   │   ├── AdminModeration.vue
│   │   │   ├── AdminRevenue.vue
│   │   │   ├── AdminSystem.vue
│   │   │   ├── AdminPlans.vue
│   │   │   ├── AdminBranding.vue
│   │   │   ├── AdminCosts.vue
│   │   │   ├── AdminModels.vue      # Per-model ServicePricing overrides
│   │   │   └── AdminPaymentSettings.vue
│   │   │
│   │   ├── auth/                    # Authentication pages
│   │   │   ├── Login.vue
│   │   │   ├── Register.vue         # Accepts ?ref=CODE referral pre-fill
│   │   │   ├── VerifyEmail.vue
│   │   │   ├── ForgotPassword.vue
│   │   │   └── ResetPassword.vue
│   │   │
│   │   ├── dashboard/               # User dashboard
│   │   │   ├── Dashboard.vue        # (legacy — no longer routed; /dashboard redirects)
│   │   │   ├── MyWorks.vue
│   │   │   ├── Invoices.vue         # 3 tabs: history / create / 發票設定 (NEW)
│   │   │   ├── Referrals.vue        # Referral program, stats, leaderboard
│   │   │   └── SocialAccounts.vue   # Share links / connected accounts (/dashboard/share-links)
│   │   │
│   │   ├── subscription/            # Payment result pages
│   │   │   ├── ECPayResult.vue           # ECPay payment result
│   │   │   ├── SubscriptionSuccess.vue   # Payment success (eagerly imported)
│   │   │   ├── SubscriptionCancelled.vue # User cancelled payment (eagerly imported)
│   │   │   └── SubscriptionMockCheckout.vue # Mock payment (dev)
│   │   │
│   │   ├── tools/                   # 22 Tool Pages
│   │   │   ├── AIAvatar.vue
│   │   │   ├── BackgroundRemoval.vue
│   │   │   ├── Claymation.vue
│   │   │   ├── ComingSoonTool.vue
│   │   │   ├── CommercialSpace.vue
│   │   │   ├── ExteriorAI.vue
│   │   │   ├── FloorPlan.vue
│   │   │   ├── ImageUpscale.vue
│   │   │   ├── InteriorTemplates.vue    # 1 component, 3 routes via spaceKind prop
│   │   │   ├── Isometric.vue
│   │   │   ├── KlingVideo.vue
│   │   │   ├── MidjourneyImagine.vue
│   │   │   ├── ProductScene.vue         # Tool-hub launcher ("What do you need?")
│   │   │   ├── ProductSceneClassic.vue  # Legacy preset products × scenes generator
│   │   │   ├── Render3D.vue
│   │   │   ├── RenderEnhancer.vue
│   │   │   ├── RoomRedesign.vue
│   │   │   ├── ShortVideo.vue
│   │   │   ├── SketchToRender.vue       # 1 component, 2 routes via spaceKind prop
│   │   │   ├── Sora2Pro.vue             # NEW 2026-06-09
│   │   │   ├── TryOn.vue                # Overhauled 2026-06-12
│   │   │   └── VideoBackgroundRemove.vue
│   │   │
│   │   └── topics/                  # Topic category pages
│   │       ├── PatternTopic.vue
│   │       ├── ProductTopic.vue
│   │       └── VideoTopic.vue
│   │
│   ├── utils/
│   │   ├── apiError.ts              # extractApiError helper
│   │   ├── checkout.ts              # PaymentMethod ('paypal' | 'ecpay') checkout helpers
│   │   ├── dataUri.ts               # dataURItoBlob
│   │   ├── downloadAsset.ts
│   │   ├── exportCsv.ts             # CSV export utility for admin tables
│   │   ├── locales.ts               # SUPPORTED_LOCALES / normalizeLocale
│   │   ├── mediaValidation.ts
│   │   ├── safeStorage.ts           # safeLocalStorage (private-mode safe)
│   │   └── toolGate.ts              # handleCardRequired gating helper
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

All tool routes are public (`requiresAuth: false`) — generation itself is
gated by credits/demo logic, not by routing.

```typescript
// src/router/index.ts (condensed — see file for full definitions)

// ===== Public =====
'/'            → LandingPage
'/pricing'     → Pricing
'/gallery'     → InspirationGallery
'/:slug(about|contact|blog|affiliate|terms|privacy|cookies|refunds|…)' → StaticInfoPage
'/info/:slug(…)'                                                       → StaticInfoPage (alias)

// ===== Tools — advertising / general =====
'/tools/background-removal'    → BackgroundRemoval      // local rembg
'/tools/product-scene'         → ProductScene           // tool-hub launcher
'/tools/product-scene-classic' → ProductSceneClassic    // legacy generator
'/tools/try-on'                → TryOn                  // PiAPI Kling ai_try_on + Kontext
'/tools/short-video'           → ShortVideo             // I2V + T2V
'/tools/image-to-video'        → ShortVideo             // alias
'/tools/avatar'                → AIAvatar               // A2E provider
'/tools/upscale'               → ImageUpscale           // PiAPI image-toolkit
'/tools/video-bg-remove'       → VideoBackgroundRemove  // Qubico video-toolkit
'/tools/claymation'            → Claymation             // multi-mode T2I / I2I / T2V
'/tools/pattern-generate'      → PatternTopic           // PiAPI T2I (Flux)
'/tools/midjourney-imagine'    → MidjourneyImagine      // multi-model T2I
'/tools/kling-video'           → KlingVideo             // tier-based Kling
'/tools/sora2-pro'             → Sora2Pro               // NEW 2026-06-09

// ===== Tools — interior design (室內設計) =====
'/tools/room-redesign'             → RoomRedesign       // interior-only
'/tools/floor-plan'                → FloorPlan          // 平面配置圖
'/tools/isometric'                 → Isometric          // 立體圖 (45° dollhouse)
'/tools/render-3d'                 → Render3D           // 3D 效果圖 (+growth video, +3D model)
'/tools/commercial-space'          → CommercialSpace    // space_kind='commercial'
'/tools/sketch-to-render-interior' → SketchToRender     // props: { spaceKind: 'interior' }
'/tools/render-enhancer'           → RenderEnhancer     // AI detail enhance + upscale
'/tools/interior-templates'        → InteriorTemplates  // props: { spaceKind: 'interior' }
'/tools/commercial-templates'      → InteriorTemplates  // props: { spaceKind: 'commercial' }

// ===== Tools — exterior design (室外設計) =====
'/tools/exterior-ai'               → ExteriorAI         // space_kind='exterior'
'/tools/sketch-to-render-exterior' → SketchToRender     // props: { spaceKind: 'exterior' }
'/tools/exterior-templates'        → InteriorTemplates  // props: { spaceKind: 'exterior' }

// ===== Topic Pages =====
'/topics/pattern' → PatternTopic
'/topics/product' → ProductTopic
'/topics/video'   → VideoTopic

// ===== Auth =====
'/auth/login'           → Login          (guestOnly)
'/auth/register'        → Register       (guestOnly, accepts ?ref=CODE)
'/auth/verify'          → VerifyEmail
'/auth/forgot-password' → ForgotPassword (guestOnly)
'/auth/reset-password'  → ResetPassword  (guestOnly)

// ===== Dashboard (Auth Required) =====
'/dashboard'                 → guard redirects: admin → admin-dashboard, user → my-works
'/dashboard/my-works'        → MyWorks
'/dashboard/invoices'        → Invoices    (admins bounced to admin-dashboard)
'/dashboard/referrals'       → Referrals   (admins bounced to admin-dashboard)
'/dashboard/share-links'     → SocialAccounts
'/dashboard/social-accounts' → redirect → share-links

// ===== Subscription Result Pages =====
// SubscriptionSuccess + SubscriptionCancelled are EAGERLY imported — they are
// the PayPal redirect targets and a lazy-chunk fetch over a slow network
// produced a blank page for cancellers (2026-05-18 fix).
'/subscription/success'       → SubscriptionSuccess     // intentionally NOT auth-gated
'/subscription/cancelled'     → SubscriptionCancelled
'/subscription/mock-checkout' → SubscriptionMockCheckout (requiresAuth)
'/subscription/ecpay-result'  → ECPayResult

// ===== Admin (nested children under AdminLayout, requiresAdmin) =====
'/admin' → AdminLayout, redirect → admin-dashboard
  children: dashboard, users, materials, moderation, revenue, system,
            plans, branding, costs, models, settings/payment

// ===== 404 =====
'/:pathMatch(.*)*' → NotFound
```

### 3.2 Redirects for Removed / Aliased Routes

| Old path | Redirects to | Reason |
|----------|--------------|--------|
| `/tools/effects`, `/tools/image-transform` | `/tools/room-redesign` | Style Effects merged into Room Redesign |
| `/tools/sketch-to-render` | `/tools/sketch-to-render-exterior` | Split into interior/exterior pages 2026-06-12 |
| `/tools/floorplan-to-video` | `/tools/render-3d` | Growth video folded into 3D 效果圖 2026-06-11 |
| `/tools/text-to-video` | `/tools/short-video` | T2V merged into ShortVideo |
| `/tools/luma-video` | `/tools/short-video` | Luma removed 2026-05-19 |
| `/tools/image-upscale` | `/tools/upscale` | alias |
| `/tools/remove-watermark` | `/tools/effects` (→ room-redesign) | tool dropped |
| `/tools/image-translator`, `/tools/video-dubbing` | `/tools/product-scene` | retired 2026-06-11 |
| `/tools/ai-model-swap`, `/tools/try-on-accessories` | `/tools/try-on` | merged |
| `/tools/ai-templates` | `/tools/product-scene` | merged |
| `/tools/product-video` | `/tools/short-video` | merged |
| `/tools/product-enhance` | `/tools/upscale` | merged |
| `/tools/pattern-transfer`, `/tools/pattern-seamless` | `/tools/pattern-generate` | merged |

`/tools/video-transform` (V2V) was **removed repo-wide 2026-05-31** — the route
no longer exists (404s).

### 3.3 SEO Hook

`router.afterEach` applies per-route SEO via `useSeo.applySeo()`:
- `ROUTE_SEO` catalog keyed by route **name** (zh-TW titles/descriptions for
  home, pricing, gallery, and every major tool page).
- Canonical URL, per-locale `hreflang` alternates (`?lang=` URLs), and
  `noindex` for `/admin`, `/dashboard`, `/subscription` paths.

### 3.4 Navigation Guards

```typescript
router.beforeEach(async (to, _from, next) => {
  const token = safeLocalStorage.getItem('access_token')
  const isAuthenticated = !!token

  // 1. requiresAuth + not logged in   → login with ?redirect=
  // 2. guestOnly + logged in          → admin → admin-dashboard, user → my-works
  // 3. '/dashboard' + logged in       → admin → admin-dashboard, user → my-works
  // 4. '/dashboard/invoices' or '/dashboard/referrals' + admin
  //                                   → admin-dashboard (billing pages are
  //                                     user-only; my-works/share-links DO
  //                                     pass through for admins)
  // 5. requiresAdmin + not admin      → home
})
```

---

## 4. Composables

### 4.1 Available Composables

```typescript
// src/composables/index.ts
export { useLocalized } from './useLocalized'          // i18n helpers (5-language L() picker)
export { useToast } from './useToast'                  // Toast notifications
export { useCredits } from './useCredits'              // Credit management
export { useUpload } from './useUpload'                // File upload
export { useWebSocket } from './useWebSocket'          // WebSocket connection
export { useResponsive } from './useResponsive'        // Responsive breakpoints
export { useGeoLanguage } from './useGeoLanguage'      // Geo-based language
export { useDemoMode } from './useDemoMode'            // Demo gating logic
export { usePromptLibrary } from './usePromptLibrary'  // Curated prompt catalogs
export { useExamplePrefill } from './useExamplePrefill' // Example → form pre-fill
// Not re-exported (imported directly): useRecaptcha, useSeo, useSessionHeartbeat
```

### 4.2 useDemoMode Composable (Demo Gating)

`useDemoMode()` no longer loads topics/presets per tool — it is the shared
**gating** composable used by tool pages:

```typescript
// src/composables/useDemoMode.ts
export function useDemoMode() {
  // isDemoUser: true when no user, OR no paid plan AND no confirmed active
  // subscription. Admins/superusers are never demo (so QA can exercise the
  // real generation pipeline). Cached user state is NOT trusted until the
  // session is validated (subscriptionChecked) — optional-auth endpoints
  // silently downgrade invalid tokens to demo, so optimistic paid gating
  // would cause UI/API mismatch.
  const isDemoUser = computed(() => { ... })
  const isPaid = computed(() => !isDemoUser.value)

  const canUseCustomInputs = computed(() => !isDemoUser.value)
  const canDownloadOriginal = computed(() => !isDemoUser.value)

  // Demo content helpers:
  //  - demoTemplates / tryPrompts / dbEmpty  (finished example rows)
  //  - inputLibrary + loadInputLibrary(toolType, topic?)  (pre-generated
  //    inputs for the input × effect picker flow)
  //  - effectCatalog (per-tool effect list)
  //  - checkSubscription() → subscriptionApi.getStatus()
}
```

### 4.3 usePromptLibrary

Curated prompt catalogs (`data/prompt_library.json`) shared by the flagship
tools — e.g. KlingVideo wires `usePromptLibrary('kling_video')` to a 40-prompt
preset dropdown, re-localized on locale change.

---

## 5. API Layer

### 5.1 API Client Configuration

```typescript
// src/api/client.ts
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 900000, // 15 minutes — subscriber-tier generation endpoints are
                   // synchronous and providers (Kling Avatar, Pollo I2V,
                   // Vertex Veo) regularly take 2-8 min, peaking ~10 min.
  headers: { 'Content-Type': 'application/json' }
})

// Request interceptor: Bearer token (safeLocalStorage) + Accept-Language
// (from 'locale' / 'vidgo-locale' / navigator.language).

// Response interceptor:
//  - Guards against nginx returning index.html instead of JSON.
//  - Flattens structured backend errors { detail: { error_code, message } }
//    so UI code reading data.detail still gets a string.
//  - 401 → single in-flight token refresh (concurrent 401s share one
//    /auth/refresh call; refresh-token rotation would otherwise log the
//    user out). Refresh failure → clear tokens, redirect to /auth/login.
```

### 5.2 API Modules

```typescript
// src/api/index.ts
export { default as apiClient } from './client'
export { authApi } from './auth'
export { uploadsApi } from './uploads'
export { referralsApi } from './referrals'
export { demoApi } from './demo'
export { toolsApi } from './tools'        // real tool endpoints
export { creditsApi } from './credits'
export { effectsApi } from './effects'
export { generationApi } from './generation'
export { default as landingApi } from './landing'
export { default as quotaApi } from './quota'
export { adminApi, createAdminWebSocket } from './admin'
export { interiorApi } from './interior'
export { subscriptionApi } from './subscription'
export { userApi } from './user'
// (einvoiceApi is imported directly from './einvoice')
```

### 5.3 Tools API (Real Generation)

All tool pages call `/api/v1/tools/*` through `toolsApi`:

```typescript
// src/api/tools.ts
toolsApi.removeBackground(...) / removeBackgroundBatch(...)
toolsApi.productScene(...)
toolsApi.tryOn(...)                 // garment mode + prompt mode (model_id presets)
toolsApi.roomRedesign(...)          // also used by Exterior/Commercial via spaceKind
toolsApi.shortVideo(...)            // I2V, per-model
toolsApi.avatar(...)                // A2E
toolsApi.claymation(...)            // T2I / I2I / T2V
toolsApi.videoBackgroundRemove(videoUrl, opts?)
toolsApi.upscale(imageUrl, scale)
toolsApi.midjourneyImagine(...)     // multi-model T2I
toolsApi.klingVideo(...)            // T2V/I2V tiers (also ShortVideo's T2V path)
toolsApi.sora2Pro(...)
toolsApi.uploadImage(file) / uploadFile(file)   // data-URI → public GCS URL
toolsApi.getStyleTemplates(toolType, opts?)     // template galleries
```

### 5.4 Demo API

The old topic-registry/preset endpoints were retired. `demoApi` now exposes:

```typescript
// src/api/demo.ts
demoApi.getInspiration(category?)      // Inspiration gallery items
demoApi.generate(data)                 // demo generation
demoApi.getToolShowcases(category)     // tool showcase rows
demoApi.uploadImage(file)
```

(Landing-page seasonal sections still read `/api/v1/demo/presets/{tool}` rows
directly via `apiClient` for curated example imagery.)

### 5.5 Landing Page Data Sources

The homepage (`LandingPage.vue`) loads data from:

| Section | Endpoint | Description |
|---------|----------|-------------|
| Hero before/after pairs | `GET /api/v1/hero/pairs` | Curated, admin-managed pairs (primary source) |
| Category examples | `GET /api/v1/demo/presets/{category}?limit=2` | Per-tool example rows |
| Seasonal product scenes | `GET /api/v1/demo/presets/product_scene?topic=…&limit=4` | Seasonal topic strips |
| Feature/stats/FAQ/etc. | `GET /api/v1/landing/{stats,features,examples,testimonials,pricing,faq}` | Static landing content (`landingApi`) |

### 5.6 Auth & Email Verification

- **Register** (`auth/Register.vue`): `authApi.register()`; store sets `pendingEmail` and redirects to `/auth/verify`. Accepts `?ref=CODE` to pre-fill a referral code.
- **Verify** (`auth/VerifyEmail.vue`): 6-digit code → `authApi.verifyCode({ email, code })`. Backend returns **AuthResponse**; the store accepts both `tokens.access/refresh` and flat `access_token/refresh_token`, logging the user in without a separate login.
- **Resend:** `authApi.resendCode(email)`.
- **Password reset:** `/auth/forgot-password` → email link → `/auth/reset-password` (`ResetPassword.vue`).

### 5.7 Pricing & Payments (PayPal / ECPay)

- **Plans:** `subscriptionApi.getPlans()` → `GET /api/v1/subscriptions/plans`. `Pricing.vue` displays `NT$` prices and plan features.
- **Subscribe:** `subscriptionApi.subscribe({ plan_id, billing_cycle, payment_method })` with `payment_method: 'paypal' | 'ecpay'` (see `utils/checkout.ts`). PayPal responses include `checkout_url` (frontend redirects); ECPay responses include an `ecpay_form` payload (auto-posted form). Mock flow activates immediately.
- **Result routes:** `/subscription/success?order=…`, `/subscription/cancelled`, `/subscription/mock-checkout?txn=…`, `/subscription/ecpay-result`. Success/cancelled are eagerly imported and success is deliberately not auth-gated (PayPal can drop the token cookie during its roundtrip; the webhook validates server-side).
- **Cancel & Refund:** `subscriptionApi.cancel({ request_refund })` — with refund (within the 7-day `refund_eligible` window: full refund, immediate revoke) or without (active until period end). Eligibility comes from `subscriptionApi.getStatus()` (`refund_eligible`, `refund_days_remaining`).

### 5.8 E-Invoice API (Taiwan)

```typescript
// src/api/einvoice.ts
einvoiceApi.issueB2C(request) / issueB2B(request)   // POST /api/v1/einvoices/b2c | /b2b
einvoiceApi.void(request)                           // POST /api/v1/einvoices/void
einvoiceApi.list(params) / get(invoiceId)           // GET  /api/v1/einvoices[/{id}]
einvoiceApi.getPreferences()                        // GET  /api/v1/einvoices/preferences  (NEW)
einvoiceApi.updatePreferences(prefs)                // PUT  /api/v1/einvoices/preferences  (NEW)
// InvoicePrefs: mode 'carrier' | 'donation' | 'b2b' + carrier/統編/donation fields
```

### 5.9 Interior API

```typescript
// src/api/interior.ts
interiorApi.getStyles() / getRoomTypes()
interiorApi.redesign(request)                  // + demoRedesign / demoGenerate
interiorApi.floorplan(request)                 // 平面配置圖
interiorApi.isometric(request)                 // 立體圖
interiorApi.generate(request) / fusion(request) / edit(request) / styleTransfer(request)
interiorApi.generate3DModel(request)           // Trellis 3D (.glb), 300s timeout
interiorApi.generate3DFromFloorplan(request)
interiorApi.getFloorplanOptions()
interiorApi.floorplanToVideo(request)          // 3D 效果圖 backend — result_tier:
                                               // 'render' | 'video' | 'video_3d'
// Shared types: InteriorLightingTone, InteriorMaterialAccent, GrowthTier
```

---

## 6. State Management (Pinia)

### 6.1 Store Modules

```typescript
// src/stores/index.ts
export { useAuthStore } from './auth'
export { useBrandingStore } from './branding'   // admin-managed brand assets
export { useCreditsStore } from './credits'
export { useUIStore } from './ui'
export { useGenerationStore } from './generation'
export { useAdminStore } from './admin'
```

### 6.2 Auth Store

```typescript
// src/stores/auth.ts
export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const accessToken = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)

  const isAuthenticated = computed(() => !!accessToken.value)
  const isAdmin = computed(() => user.value?.is_admin ?? false)

  // login / register / logout / fetchUser ...
})
```

### 6.3 Credits Store

```typescript
// src/stores/credits.ts
// remainingCredits shown in the AppHeader badge; tool pages call
// creditsStore.deductCredits(result.credits_used) after a successful run
// (the backend reports ACTUAL credits used, which may differ from the
// displayed constant when admin ServicePricing overrides apply) and
// fetchBalance() to re-sync.
```

---

## 7. Tool Pages

### 7.1 Tool Hub (data/toolHub.ts)

`ProductScene.vue` (`/tools/product-scene`) is the **tool-hub launcher** and
`AppHeader.vue`'s Tools mega-dropdown renders the same catalog —
**one source of truth**: `src/data/toolHub.ts`.

- **31 tiles** in **5 categories** (`TOOL_HUB_CATEGORIES` order):

| Category | zh name | Contents |
|----------|---------|----------|
| `advertising` | 廣告宣傳 | virtual-model, product-staging, flat-lay, instagram-story, product-photography, three-d-illustration, video-generator, ai-avatar, sora2-pro |
| `interior` | 室內設計 | room-redesign, interior-templates, floor-plan, isometric, render-3d, commercial-space, sketch-to-render-interior, render-enhancer |
| `exterior` | 室外設計 (**NEW 2026-06-12**) | exterior-ai, sketch-to-render-exterior, exterior-templates |
| `branding` | 品牌設計 | recolor, edit-with-ai, logo, create-any-image, product-packaging |
| `other` | 其他酷炫的AI功能 | product-beautifier, ghost-mannequin, ironing, background, video-bg-remove, claymation |

- Every tile has a **dedicated GCS thumbnail** (filename = tile id):
  `https://storage.googleapis.com/vidgo-media-vidgo-ai/static/hub/{id}.png`,
  generated via `backend/scripts/generate_brand_assets.py`.
- "Recently Used" (max 4) is localStorage-backed (`vidgo.toolHub.recent`,
  `getRecentTiles()` / `pushRecentTool()`), shared by the hub page and header.
- **Owner directive (2026-06-12): interior and exterior NEVER mix on one
  page.** The former combined 室內室外設計 bucket was split; commercial-space
  stays in `interior` (it designs interiors of commercial venues) and
  render-enhancer stays in `interior` as the generic render utility.

### 7.2 Tool Feature Map

```
+-----------------------------------------------------------------------------+
|                           VidGo AI Tool Map                                  |
+-----------------------------------------------------------------------------+
|                                                                              |
|  ── Advertising / General ──                                                 |
|  Background Removal (一鍵白底圖)  /tools/background-removal  local rembg     |
|  Product Scene Hub                /tools/product-scene       tool launcher   |
|  Product Scene Classic            /tools/product-scene-classic               |
|  Virtual Try-On (時尚穿搭展示)    /tools/try-on              Kling + Kontext |
|  Short Video (短影音)             /tools/short-video         I2V + T2V       |
|  Kling Video                      /tools/kling-video         tiered T2V/I2V  |
|  Sora 2 Pro (NEW 2026-06-09)      /tools/sora2-pro           PiAPI / Pollo   |
|  AI Avatar (AI數位人)             /tools/avatar               A2E             |
|  Midjourney Imagine               /tools/midjourney-imagine  multi-model T2I |
|  Image Upscale                    /tools/upscale             image-toolkit   |
|  Video BG Remove                  /tools/video-bg-remove     Qubico          |
|  Claymation                       /tools/claymation          T2I/I2I/T2V     |
|  Pattern Generate (印花設計)      /tools/pattern-generate    Flux T2I        |
|                                                                              |
|  ── Interior Design (室內設計) — interior-only pages ──                      |
|  Room Redesign                    /tools/room-redesign                       |
|    modes: redesign / stage / magic (+ hidden: generate / 3D /                |
|    styleTransfer / transform). ReRoom.ai-style layout.                       |
|  Floor Plan (平面配置圖)          /tools/floor-plan                          |
|  Isometric (立體圖)               /tools/isometric          + Atmosphere     |
|  Render 3D (3D 效果圖)            /tools/render-3d          + Atmosphere     |
|    tiers: render | video (Kling growth) | video_3d (Trellis .glb);          |
|    render mode 保留結構 (preserve, ControlNet depth) / 自由改造 (free)        |
|  Commercial Space                 /tools/commercial-space   space_kind=      |
|                                                             'commercial'     |
|  Sketch→Render (interior)         /tools/sketch-to-render-interior           |
|  Render Enhancer                  /tools/render-enhancer                     |
|  Templates: interior/commercial   /tools/interior-templates,                 |
|                                   /tools/commercial-templates                |
|                                                                              |
|  ── Exterior Design (室外設計) — exterior-only pages (NEW group) ──          |
|  Exterior AI                      /tools/exterior-ai        space_kind=      |
|                                                             'exterior'       |
|  Sketch→Render (exterior)         /tools/sketch-to-render-exterior           |
|  Templates: exterior              /tools/exterior-templates                  |
|                                                                              |
+-----------------------------------------------------------------------------+
```

**Single-component, multi-route pages (spaceKind prop):**
- `SketchToRender.vue` — `/tools/sketch-to-render-interior` (`spaceKind='interior'`, INTERIOR_STYLES) and `/tools/sketch-to-render-exterior` (`spaceKind='exterior'`, EXTERIOR_STYLES). Styles loaded from `/api/v1/tools/templates/interior-styles?space_kind=…`.
- `InteriorTemplates.vue` — `/tools/interior-templates`, `/tools/exterior-templates`, `/tools/commercial-templates`. The old in-page tab switcher was **removed 2026-06-12** (owner directive); each space kind is its own page. Clicking a card deeplinks into the matching tool page with `?style=`.

### 7.3 Video Models & Credits

`ShortVideo.vue` supports two task types:
- **image_to_video** (default) — per-model via `toolsApi.shortVideo`:

| Model id | Display | Credits |
|----------|---------|---------|
| `hailuo` | Hailuo Fast（最便宜） | 18 |
| `wan` | Wan 480p | 20 |
| `hunyuan` | Hunyuan（中文擅長） | 20 |
| `kling_v2` | Kling V2.5（標準） | 28 |
| `seedance` | Seedance 720p | 65 |
| `seedance_1080p` | Seedance 1080p | 160 |
| `kling_v3_std` | Kling V3.0（標準） | 65 |
| `kling_omni` | Kling V3.0 PRO（含音訊） | 130 |
| `veo` | Veo 3.1（含音訊） | 80 |

- **text_to_video** — routed through `toolsApi.klingVideo` with a tier.

`KlingVideo.vue` tiers: default → Kling V2.5 STD (28), flagship → Kling V3.0
STD (65), omni → Kling V3.0 PRO with audio (130). `Sora2Pro.vue`: flagship 5s
clip, 720p/1080p both billed flat **80 credits** (`video_sora2` row); preset
dropdown + free-form prompt + optional source frame, mirroring KlingVideo UX.
`MidjourneyImagine.vue` models: Flux Schnell / Z-Image Turbo / Qwen /
Seedream 5 Lite = 2 credits; Nano Banana 2 / Nano Banana Pro (Gemini) = 8.

Displayed costs mirror the backend's seeded ServicePricing; admin overrides
via `/admin/models` change the actual deduction, and pages reconcile using
`result.credits_used`.

### 7.4 Shared Tool Components (NEW 2026-06-12)

- **AtmosphereControls.vue** — lighting tone (daylight / warm_evening /
  golden_hour / overcast_soft / dramatic_spotlight / night), color temperature
  Kelvin slider (0 = auto), and material accent (wood / marble / concrete /
  linen / brass / leather / terrazzo). Maps 1:1 to the backend's additive
  atmosphere clauses — light/surfaces only, geometry protected by the
  anti-hallucination invariants. Used by **Isometric** + **Render3D**.
- **VideoFaithfulnessControls.vue** — anti-hallucination controls for the
  video tools (**ShortVideo, KlingVideo, Sora2Pro**). Camera-move catalog
  (static / dolly_in / dolly_out / orbit / pan / tilt_up / crane_up /
  handheld — ids match backend `VIDEO_CAMERA_MOVES`) plus one faithfulness
  toggle whose meaning adapts to mode: i2v → `subject_lock`, t2v →
  `strict_prompt`. Default ON. Exists because the platform never rewrites the
  user's prompt (owner directive 2026-05-23: verbatim prompt fidelity).
- **PiapiPlayground.vue** — the shared two-column tool-page layout (left
  config / right result + status pill, examples/pricing/FAQ below) with
  slots `inputs`, `result`, `result-actions`, `examples`, `faq` and `pp-*`
  scoped styles. Used by 17 of the 22 tool pages.

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
// Runs once per session/device. Order:
//   1. Saved preference (LOCALE_STORAGE_KEY via safeLocalStorage)
//   2. Server-side geo lookup: GET /api/v1/auth/geo-language
//      (Taiwan/HK/Macau → zh-TW, Japan → ja, Korea → ko,
//       Spain & Latin America → es)
//   3. Fallback: 'en'
// Result normalized against SUPPORTED_LOCALES (utils/locales.ts) and
// persisted; detection flag stored so it never re-runs.
```

In-component copy for the tool pages largely uses `useLocalized().L(zh, en,
ja, ko, es)` inline pickers alongside vue-i18n JSON catalogs.

---

## 9. 3-Tier User System

VidGo supports a **3-tier user system** with distinct capabilities:

### 9.1 User Role Matrix

| Feature | Visitor (Guest) | Free Registered | Paid Subscriber | Admin |
|---------|----------------|-----------------|-----------------|-------|
| Browse landing page | ✅ | ✅ | ✅ | ✅ |
| Demo tools (limited, watermarked) | ✅ | ✅ | ✅ | ✅ |
| Watermarked results | ✅ | ✅ | ❌ (clean) | N/A |
| Download results | ❌ | ❌ | ✅ | ✅ |
| Share to social media | ❌ | ❌ | ✅ | ❌ |
| Upload own materials | ❌ | ❌ | ✅ | ✅ (QA) |
| Real AI API generation (credits) | ❌ | ❌ | ✅ | ✅ (QA) |
| Promotion code (own) | ❌ | ❌ | ✅ (auto-issued) | Can create special ones |
| Use others' promo codes | ❌ | ✅ | ✅ | N/A |
| Private work library (14-day media retention) | ❌ | ❌ | ✅ | N/A |
| View API analytics | ❌ | ❌ | ❌ | ✅ |
| Manage users/credits | ❌ | ❌ | ❌ | ✅ |

Gating is implemented client-side by `useDemoMode().isDemoUser` (see §4.2)
and enforced server-side by the optional-auth tool endpoints (invalid tokens
silently downgrade to demo). Admins/superusers always get the full subscriber
flow for QA. New registrations receive 40 free credits (see register SEO copy).

### 9.2 Promotion Code System

**Personal Promotion Codes:**
- **Paid subscribers**: Automatically receive unique promotion code upon subscription
- **Free users**: Cannot create promotion codes, but can use others' codes
- **Admin**: Can create special promotion codes with custom credits/discounts
- **Code usage**: When someone uses a promotion code, code owner earns credits

**Promotion Code Types:**
| Type | Who Can Create | Credits Awarded | Expiry |
|------|---------------|-----------------|--------|
| Personal referral code | Auto-generated for paid subscribers | Referrer: +50, New user: +40 | Never |
| Special admin code | Admin only | Custom (e.g., 100 credits) | Custom date |
| Public promo code | Admin only | Discount or credits | Fixed expiry |

### 9.3 Work Library Retention

**Active subscribers**: All works stored indefinitely
**Cancelled subscribers**: Generation records remain in the private work library
**During retention**: Can download existing works, cannot generate new works
**Account deletion**: All works deleted immediately (no retention)
**Media expiry**: Generated media remains available for 14 days from creation

### 9.4 User Flow (Real-API Tools)

```
+---------------------------------------------------------------------+
|                        TOOL-PAGE USER FLOW                           |
+---------------------------------------------------------------------+
|                                                                      |
|  1. User visits a tool page (e.g., /tools/try-on) — public route     |
|                                                                      |
|  2. Page loads examples (data/toolExamples.ts + demo input library)  |
|     and shows credit cost on the Generate button                     |
|                                                                      |
|  3. Demo user: limited inputs, watermarked output, no download;      |
|     clicking an example pre-fills the form (useExamplePrefill)       |
|                                                                      |
|  4. Subscriber: uploads own image (data-URI → toolsApi.uploadImage   |
|     → public GCS URL), picks model/params, clicks Generate           |
|                                                                      |
|  5. Frontend calls /api/v1/tools/{tool} (synchronous; up to 15 min)  |
|     └── On success: creditsStore.deductCredits(result.credits_used)  |
|     └── On card-required: handleCardRequired() routes to pricing     |
|                                                                      |
|  6. Result displayed with Download / Regenerate actions              |
|                                                                      |
+---------------------------------------------------------------------+
```

---

## 10. Environment Configuration

### 10.1 Development

```bash
# .env.development
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_TITLE=VidGo
VITE_RECAPTCHA_SITE_KEY=
```

### 10.2 Production

```bash
# .env.production
VITE_API_BASE_URL=          # same-origin (served behind nginx)
VITE_APP_TITLE=VidGo
VITE_RECAPTCHA_SITE_KEY=
```

---

## 11. Build & Deploy

```bash
# Install dependencies
npm install

# Development server
npm run dev

# Production build (vue-tsc && vite build)
npm run build

# Preview production build
npm run preview

# Type check
npm run type-check
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

### 12.2 Test Flow

```
+----------------------------------------------------------+
|                   FULL STACK TEST FLOW                    |
+----------------------------------------------------------+
|                                                          |
|  1. START SERVICES                                       |
|     docker-compose up -d                                 |
|                                                          |
|  2. VERIFY BACKEND                                       |
|     curl http://localhost:8000/health                    |
|                                                          |
|  3. VERIFY FRONTEND                                      |
|     npm run dev → landing page loads with hero pairs     |
|                                                          |
|  4. TEST TOOL PAGES                                      |
|     /tools/product-scene → hub tiles render (31 tiles)   |
|     /tools/try-on → pick preset model → generate         |
|     /tools/room-redesign → upload → redesign             |
|     /tools/short-video → pick I2V model → generate       |
|                                                          |
|  5. TEST API ENDPOINTS                                   |
|     GET /api/v1/hero/pairs                               |
|     GET /api/v1/tools/templates/interior-styles          |
|                                                          |
+----------------------------------------------------------+
```

### 12.3 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Frontend blank | Backend not ready | Wait for backend health check |
| API 401 | Missing auth token | Check localStorage for access_token |
| "non-JSON response" errors | nginx proxy misconfigured | client.ts guard fires; check proxy |
| Stuck "處理中..." | client timeout shorter than provider | timeout is 15 min by design |
| Videos not playing | CORS or URL issues | Check browser console for errors |

---

## 13. Virtual Try-On (Overhauled 2026-06-12)

### 13.1 Overview

`TryOn.vue` was rebuilt as **two plain-task modes** backed by the same
`/api/v1/tools/try-on` endpoint — the engine choice is an implementation
detail (owner request: make try-on easier to use; no model-name dropdowns):

| Mode | Input | Engine |
|------|-------|--------|
| `garment` (default) | Upload a garment photo | Kling AI Try-On (image+image) |
| `prompt` | Describe the outfit in text | Flux Kontext I2I |

**Credit cost: 30** (mirrors backend `tools.py ai_try_on CREDIT_COST`).

### 13.2 Built-in AI Model Picker

The person photo comes from either a **preset model grid** (default — one
click, no upload, never rejected by the aspect-ratio validator) or the user's
own upload (full-body 2:3 / 3:4 portrait). The **11 presets** map to backend
`TRYON_MODELS` by `model_id`; thumbnails live at
`…/static/tryon/models/{id}.png`:

| model_id | zh name | model_id | zh name |
|----------|---------|----------|---------|
| `avery` | 怡君 | `julia` | 佩珊 |
| `kendall` | 曉雨 | `sam` | 志偉 |
| `alex` | 佳穎 | `taylor` | 俊豪 |
| `maya` | 雅婷 | `jordan` | 冠宇 |
| `lena` | 美玲 | `casey` | 宗翰 |
| | | `reece` | 昊然 |

The first model is preselected so the form starts nearly ready. Prompt mode
ships six outfit presets (business / streetwear / couture / evening / summer /
athletic) using identity-preserving Kontext instruction prompts. Local
data-URI uploads are converted to public URLs via `toolsApi.uploadImage`
before generation (Kling/Kontext cannot fetch data URIs).

---

## 14. Pattern Design Feature

- **Route:** `/tools/pattern-generate` → `views/topics/PatternTopic.vue`
  (PiAPI Flux T2I). `/tools/pattern-transfer` and `/tools/pattern-seamless`
  now redirect here.
- The hub exposes it via the `recolor` and `product-packaging` tiles
  (category `branding`).

---

## 15. Key Components

### 15.1 PiapiPlayground

The shared tool-page layout (see §7.4) — two columns, status pill, credit-cost
badge in the Generate button, `pp-*` scoped styles. Owner directive
2026-05-24: every tool page looks like piapi.ai's /flux-kontext playground,
except the Interior pages which use the Pippit templates-gallery style.

### 15.2 ThreeViewer (3D Model Viewer)

Three.js-based GLB model viewer.
- Location: `src/components/tools/ThreeViewer.vue`
- Used by: `Render3D.vue` (`video_3d` tier — Trellis2 interactive .glb)
- GLTFLoader, OrbitControls, auto-rotation
- Dependency: `three`

### 15.3 ShareToSocialModal

Modal for publishing generations to connected social media accounts.
- Location: `src/components/social/ShareToSocialModal.vue`
- Platforms: Facebook, Instagram, TikTok, YouTube

### 15.4 Referrals Dashboard

Route: `/dashboard/referrals` — `views/dashboard/Referrals.vue`
- Stats cards (invited count, credits earned)
- Shareable referral link (LINE, X, Facebook)
- Apply referral code form
- Top 10 leaderboard
- (Admins are bounced to the admin dashboard by the router guard.)

### 15.5 Share Links / Social Accounts Dashboard

Route: `/dashboard/share-links` — `views/dashboard/SocialAccounts.vue`
(`/dashboard/social-accounts` redirects here)
- Connect/disconnect social media accounts
- OAuth flow for Facebook, Instagram, TikTok, YouTube (Google OAuth 2.0)

### 15.6 Invoices Dashboard (3 tabs)

Route: `/dashboard/invoices` — `views/dashboard/Invoices.vue`
- **list** — invoice history with void action
- **create** — B2C/B2B e-invoice creation (`InvoiceCreateForm.vue`)
- **settings (發票設定, NEW 2026-06-12)** — `InvoicePrefsForm.vue`: carrier
  (載具) / company tax ID (統編) / donation preference, persisted via
  `/api/v1/einvoices/preferences`

### 15.7 API Clients

```typescript
// src/api/uploads.ts
uploadsApi.getToolModels(toolType)
uploadsApi.uploadAndGenerate(...)
uploadsApi.getUploadStatus(uploadId)
uploadsApi.getDownloadUrl(uploadId)

// src/api/referrals.ts
referralsApi.getCode() / getStats() / applyCode(code) / getLeaderboard()

// src/api/socialMedia.ts
socialMediaApi.getAccounts() / disconnectAccount(platform)
socialMediaApi.getOAuthUrl(platform)
socialMediaApi.publish(generationId, platforms)
socialMediaApi.getPostHistory(params) / getPostAnalytics()

// src/api/user.ts
userApi.getGenerations(params) / getGenerationDetail(id)
userApi.downloadGeneration(id) / deleteGeneration(id) / getStats()
```

---

*Document Version: 8.0*
*Last Updated: June 12, 2026*
*Mode: Real-API tools (PiAPI / rembg / A2E / Vertex) with demo gating + credit-based billing*
*Target: SMB (small businesses selling everyday products/services)*
