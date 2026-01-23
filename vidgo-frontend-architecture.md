# VidGo AI Platform - Frontend Architecture

**Version:** 4.3
**Last Updated:** January 18, 2026
**Framework:** Vue 3 + Vite + TypeScript
**Mode:** Preset-Only (No Custom Input)

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
│   │   │   ├── MaterialCard.vue
│   │   │   ├── ToastNotification.vue
│   │   │   ├── UpgradePrompt.vue
│   │   │   └── index.ts
│   │   │
│   │   ├── tools/                   # Tool-specific components
│   │   │   ├── BeforeAfterSlider.vue
│   │   │   ├── CreditCost.vue
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
│   │   │   ├── Dashboard.vue
│   │   │   └── MyWorks.vue
│   │   │
│   │   ├── tools/                   # 7 Core Tool Pages
│   │   │   ├── BackgroundRemoval.vue
│   │   │   ├── ProductScene.vue
│   │   │   ├── TryOn.vue
│   │   │   ├── RoomRedesign.vue
│   │   │   ├── ShortVideo.vue
│   │   │   ├── AIAvatar.vue
│   │   │   └── PatternDesign.vue
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

  // ===== 7 Core Tools =====
  { path: '/tools/background-removal', name: 'background-removal', component: BackgroundRemoval },
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
  const presets = ref<Preset[]>([])
  const selectedPreset = ref<Preset | null>(null)
  const result = ref<DemoResult | null>(null)
  const isLoading = ref(false)

  // Load available presets from Material DB
  const loadPresets = async () => {
    const response = await demoApi.getPresets(toolType)
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

  onMounted(loadPresets)

  return {
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

## 7. Tool Pages (7 Core Tools)

### 7.1 Tool Feature Map

```
+-----------------------------------------------------------------------------+
|                           VidGo AI Tool Map                                  |
+-----------------------------------------------------------------------------+
|                                                                              |
|  Tool 1: Background Removal (一鍵白底圖)                                     |
|  ├─ Backend: PiAPI T2I + Rembg / Gemini backup                               |
|  ├─ Route: /tools/background-removal                                         |
|  ├─ Topics: electronics, fashion, jewelry, food, cosmetics, furniture...     |
|  └─ Mode: Pre-generated examples from Material DB                            |
|                                                                              |
|  Tool 2: Product Scene (產品攝影靈感)                                        |
|  ├─ Backend: PiAPI T2I (Flux model)                                          |
|  ├─ Route: /tools/product-scene                                              |
|  ├─ Topics: studio, nature, luxury, minimal, lifestyle, urban...             |
|  └─ Mode: Pre-generated gallery, watermarked output                          |
|                                                                              |
|  Tool 3: Virtual Try-On (時尚穿搭展示)                                       |
|  ├─ Backend: Kling AI Try-On via PiAPI (with T2I fallback)                   |
|  ├─ Route: /tools/try-on                                                     |
|  ├─ Topics: casual, formal, dresses, sportswear, outerwear, accessories      |
|  ├─ Model Library: AI-generated full-body models (3 female, 3 male)          |
|  └─ Mode: Pre-generated gallery, watermarked output                          |
|                                                                              |
|  Tool 4: Room Redesign (室內設計範例)                                        |
|  ├─ Backend: PiAPI T2I (Flux model)                                          |
|  ├─ Route: /tools/room-redesign                                              |
|  ├─ Topics: modern, nordic, japanese, industrial, minimalist, luxury         |
|  └─ Mode: Pre-generated gallery, watermarked output                          |
|                                                                              |
|  Tool 5: Short Video (短影片)                                                |
|  ├─ Backend: Pollo AI I2V (Pixverse v4.5 default)                            |
|  ├─ Route: /tools/short-video                                                |
|  ├─ Topics: product_showcase, brand_story, tutorial, promo                   |
|  ├─ Landing Topics: ecommerce, social, brand, app, promo, service            |
|  └─ Mode: Pre-generated videos from Material DB                              |
|                                                                              |
|  Tool 6: AI Avatar (AI數位人)                                                |
|  ├─ Backend: A2E.ai (TTS + Lip-sync)                                         |
|  ├─ Route: /tools/avatar                                                     |
|  ├─ Topics: spokesperson, product_intro, customer_service, social_media      |
|  ├─ Landing Topics: ecommerce, social, brand, app, promo, service            |
|  ├─ Languages: en, zh-TW, ja, ko                                             |
|  └─ Mode: Pre-generated avatar videos from Material DB                       |
|                                                                              |
|  Tool 7: Pattern Design (印花設計)                                           |
|  ├─ Backend: PiAPI T2I (Flux model)                                          |
|  ├─ Route: /tools/pattern-design                                             |
|  ├─ Topics: floral, geometric, abstract, traditional, modern                 |
|  └─ Mode: Pre-generated seamless patterns from Material DB                   |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### 7.2 Backend API Integration

| Tool | API Endpoint | Backend Provider | Pre-generation |
|------|--------------|------------------|----------------|
| Background Removal | `/api/v1/demo/presets/background_removal` | PiAPI T2I | Yes |
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

### 9.1 Access Control Matrix

| Feature | All Users |
|---------|-----------|
| View preset options | Yes |
| Select preset | Yes |
| Enter custom text | No |
| View watermarked result | Yes |
| View original result | No |
| Download | No |
| API calls | No (Material DB only) |

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
| floral | 花卉印花 | Floral and botanical patterns |
| geometric | 幾何圖案 | Geometric and abstract shapes |
| abstract | 抽象藝術 | Abstract artistic patterns |
| traditional | 傳統紋樣 | Traditional cultural patterns |
| modern | 現代設計 | Contemporary modern designs |

### 14.3 Backend Integration

- **Tool Type**: `pattern_generate`
- **API Endpoint**: `/api/v1/demo/presets/pattern_generate`
- **Provider**: PiAPI T2I (Flux model)
- **Output**: Seamless tileable patterns

---

*Document Version: 4.3*
*Last Updated: January 18, 2026*
*Mode: Preset-Only (No Custom Input)*
