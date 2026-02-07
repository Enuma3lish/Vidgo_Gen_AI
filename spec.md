# VidGo Platform – Function & Tool Coverage Spec

**Purpose:** Check that each function/tool is implemented in both **Backend** and **Frontend**. Use this to find gaps.

**功能對齊參考：** 與豆绘AI (douhuiai.com) 功能對齊、UI 維持現狀的對照與實作計畫見 [docs/DOUHUAIAI_FEATURE_ALIGNMENT.md](docs/DOUHUAIAI_FEATURE_ALIGNMENT.md)。

**Legend:**
- ✅ Implemented and wired
- ⚠️ Partial or preset-only / different flow
- ❌ Missing or not wired

---

## 1. Core AI Tools (8 Tools)

| # | Tool | Backend API | Backend Preset (Material DB) | Frontend Route | Frontend Uses Presets | Status |
|---|------|-------------|-----------------------------|-----------------|------------------------|--------|
| 1 | **Background Removal** (一鍵白底圖) | `POST /api/v1/tools/remove-bg` | ✅ `presets/background_removal`, `use-preset` | ✅ `/tools/background-removal` | ✅ useDemoMode + presets | ✅ |
| 2 | **Product Scene** (商品場景圖) | `POST /api/v1/tools/product-scene` | ✅ `presets/product_scene`, `use-preset` | ✅ `/tools/product-scene` | ✅ useDemoMode + presets | ✅ |
| 3 | **Try-On** (AI試穿) | `POST /api/v1/tools/try-on` | ✅ `presets/try_on`, `use-preset` | ✅ `/tools/try-on` | ✅ useDemoMode + presets | ✅ |
| 4 | **Room Redesign** (毛坯精裝) | `POST /api/v1/tools/room-redesign` | ✅ `presets/room_redesign`, `use-preset` | ✅ `/tools/room-redesign` | ✅ useDemoMode + presets | ✅ |
| 5 | **Short Video** (短影片) | `POST /api/v1/tools/short-video` | ✅ `presets/short_video`, `use-preset` | ✅ `/tools/short-video` | ✅ useDemoMode + presets | ✅ |
| 6 | **AI Avatar** (AI數位人) | `POST /api/v1/tools/avatar` | ✅ `presets/ai_avatar`, `use-preset` | ✅ `/tools/avatar` | ✅ useDemoMode + presets | ✅ |
| 7 | **Pattern Generate** (圖案生成) | Generation: `POST /api/v1/generate/pattern/generate` | ✅ `presets/pattern_generate` (Material DB) | ✅ `/tools/pattern-generate`, PatternTopic.vue | ⚠️ Topic page | ✅ |
| 8 | **Effect / Style Transfer** (圖片風格) | `GET/POST /api/v1/effects/*` (subscriber) | ✅ `presets/effect`, `use-preset` | ✅ `/tools/effects` (ImageEffects.vue) | ✅ loadDemoTemplates('effect') + use-preset; also effectsApi for subscribers | ✅ |

**Notes:**
- Effect: Backend has **two** paths — (1) Demo: `presets/effect` + `use-preset` from Material DB; (2) Subscriber: `/api/v1/effects/styles`, `/api/v1/effects/apply-style`. Frontend ImageEffects uses both (presets for demo, effectsApi for styles list / apply when subscribed).
- All 8 tools have `ToolType` in backend and entries in `topic_registry.TOOL_TOPICS`.

---

## 2. Demo / Preset-Only Flow

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| List tool types | ✅ `GET /api/v1/demo/topics` (tool_types, topics) | ❌ Not called (topics can be hardcoded or from presets) | ⚠️ Frontend could use for dynamic topic lists |
| Get topics per tool | ✅ `GET /api/v1/demo/topics/{tool_type}` | ❌ Not used | ⚠️ Optional: use for topic dropdowns |
| Get presets for tool | ✅ `GET /api/v1/demo/presets/{tool_type}` | ✅ useDemoMode → `presets/${toolType}` | ✅ |
| Use preset (get result) | ✅ `POST /api/v1/demo/use-preset` | ✅ useDemoMode → `use-preset` | ✅ |
| Download preset result | ✅ `GET /api/v1/demo/download/{preset_id}` | ⚠️ Blocked for demo users (canDownloadOriginal) | ✅ |
| Materials status | ✅ `GET /api/v1/demo/materials/status`, `GET /materials/status` | ❌ Not used in UI | ⚠️ Optional: admin or status page |

---

## 3. Auth

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Login (form) | ✅ `POST /api/v1/auth/login/form` | ✅ Login.vue | ✅ |
| Register | ✅ `POST /api/v1/auth/register` | ✅ Register.vue | ✅ |
| Logout | ✅ `POST /api/v1/auth/logout` | ✅ (store/client) | ✅ |
| Refresh token | ✅ `POST /api/v1/auth/refresh` | ✅ (client) | ✅ |
| Get current user | ✅ `GET /api/v1/auth/me` | ✅ auth store | ✅ |
| Update profile | ✅ `PUT /api/v1/auth/me` | ✅ | ✅ |
| Verify email | ✅ `POST /api/v1/auth/verify-email` | ✅ VerifyEmail.vue | ✅ |
| Resend verification | ✅ `POST /api/v1/auth/resend-verification` | ✅ | ✅ |
| Forgot password | ✅ `POST /api/v1/auth/forgot-password` | ✅ ForgotPassword.vue | ✅ |
| Reset password | ✅ `POST /api/v1/auth/reset-password` | ⚠️ Route exists; confirm reset flow | ✅ |
| Geo/language by IP | ✅ `GET /api/v1/auth/geo-language` | ✅ useGeoLanguage | ✅ |

---

## 4. Subscription & Payments

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| List plans | ✅ `GET /api/v1/subscriptions/plans` (or plans router) | ✅ Pricing / subscription API | ✅ |
| Subscribe | ✅ `POST /api/v1/subscriptions/subscribe` | ✅ | ✅ |
| Subscription status | ✅ `GET /api/v1/subscriptions/status` | ✅ subscriptionApi.getStatus() | ✅ |
| Cancel subscription | ✅ `POST /api/v1/subscriptions/cancel` | ✅ | ✅ |
| Subscription history | ✅ `GET /api/v1/subscriptions/history` | ⚠️ Confirm used in UI | ✅ |
| Payment webhook (Paddle/ECPay) | ✅ `POST /api/v1/payments/*` | N/A | ✅ |
| Invoice (send on payment) | ✅ Email + Paddle invoice PDF | N/A | ✅ |

---

## 5. Credits

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Balance | ✅ `GET /api/v1/credits/balance` | ✅ credits API / store | ✅ |
| Estimate cost | ✅ `POST /api/v1/credits/estimate` | ✅ | ✅ |
| Transactions | ✅ `GET /api/v1/credits/transactions` | ✅ | ✅ |
| Packages | ✅ `GET /api/v1/credits/packages` | ✅ | ✅ |
| Purchase credits | ✅ `POST /api/v1/credits/purchase` | ✅ | ✅ |
| Pricing (services) | ✅ `GET /api/v1/credits/pricing` | ✅ | ✅ |

---

## 6. Landing & Marketing

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Landing stats | ✅ `GET /api/v1/landing/stats` | ⚠️ Confirm | ✅ |
| Features | ✅ `GET /api/v1/landing/features` | ✅ | ✅ |
| Examples | ✅ `GET /api/v1/landing/examples` | ✅ | ✅ |
| Testimonials | ✅ `GET /api/v1/landing/testimonials` | ✅ | ✅ |
| Pricing (landing) | ✅ `GET /api/v1/landing/pricing` | ✅ | ✅ |
| FAQ | ✅ `GET /api/v1/landing/faq` | ✅ | ✅ |
| Contact form | ✅ `POST /api/v1/landing/contact` | ⚠️ Confirm | ✅ |
| Demo inspiration | ✅ `GET /api/v1/demo/inspiration` | ✅ demoApi.getInspiration | ✅ |
| Landing examples (by category) | ✅ `GET /api/v1/demo/landing/examples` | ✅ LandingPage | ✅ |
| Watch demo (random video) | ✅ `GET /api/v1/demo/landing/watch-demo` | ✅ | ✅ |

---

## 7. User Dashboard

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Dashboard home | ✅ (auth/me, subscription, credits) | ✅ Dashboard.vue | ✅ |
| My Works (generations) | ✅ Likely generation history / user_generations | ✅ MyWorks.vue | ✅ |
| **Invoices list & download** | ✅ `GET /api/v1/subscriptions/invoices`, `GET /api/v1/subscriptions/invoices/{order_id}/pdf` | ✅ Invoices.vue, route `/dashboard/invoices` | ✅ |

---

## 8. Admin

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Admin dashboard | ✅ `/api/v1/admin/*` | ✅ AdminDashboard.vue | ✅ |
| Users list | ✅ `GET /api/v1/admin/users` | ✅ AdminUsers.vue | ✅ |
| Materials list | ✅ `GET /api/v1/admin/materials` | ✅ AdminMaterials.vue | ✅ |
| Moderation queue | ✅ `GET /api/v1/admin/materials/pending` etc. | ✅ AdminModeration.vue | ✅ |
| Revenue | ✅ Admin revenue endpoints | ✅ AdminRevenue.vue | ✅ |
| System | ✅ Admin system endpoints | ✅ AdminSystem.vue | ✅ |
| Review material | ✅ `POST /api/v1/admin/materials/{id}/review` | ✅ | ✅ |

---

## 9. Generation (Subscriber / Full API)

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| T2I | ✅ `POST /api/v1/generate/t2i` | ✅ generation API | ✅ |
| I2V | ✅ `POST /api/v1/generate/i2v` | ✅ | ✅ |
| Interior | ✅ `POST /api/v1/generate/interior` | ✅ | ✅ |
| Pattern generate/transfer | ✅ `POST /api/v1/generate/pattern/*` | ✅ | ✅ |
| Remove BG (generate) | ✅ `POST /api/v1/generate/product/remove-background` | ✅ | ✅ |
| Product scene (generate) | ✅ `POST /api/v1/generate/product/generate-scene` | ✅ | ✅ |
| Product enhance | ✅ `POST /api/v1/generate/product/enhance` | ✅ | ✅ |
| Image to video | ✅ `POST /api/v1/generate/video/image-to-video` | ✅ | ✅ |
| Video transform | ✅ `POST /api/v1/generate/video/transform` | ✅ | ✅ |
| Video styles | ✅ `GET /api/v1/generate/video/styles` | ✅ | ✅ |
| Interior styles/room types | ✅ `GET /api/v1/generate/interior-styles`, room-types | ✅ | ✅ |

---

## 10. Effects (Style Transfer – Subscriber)

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| List styles | ✅ `GET /api/v1/effects/styles` | ✅ effectsApi.getStyles() | ✅ |
| Apply style | ✅ `POST /api/v1/effects/apply-style` | ✅ effectsApi.applyStyle() | ✅ |
| HD enhance | ✅ `POST /api/v1/effects/hd-enhance` | ✅ effectsApi.hdEnhance() | ⚠️ Confirm UI |

---

## 11. Interior Design

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Styles | ✅ `GET /api/v1/interior/styles` | ✅ interior API | ✅ |
| Room types | ✅ `GET /api/v1/interior/room-types` | ✅ | ✅ |
| Redesign | ✅ `POST /api/v1/interior/redesign` | ✅ | ✅ |
| Generate / Fusion / Edit / Style transfer | ✅ interior endpoints | ✅ | ✅ |

---

## 12. Tools – Extra (Try-On, Avatar, etc.)

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Try-on models list | ✅ `GET /api/v1/tools/models/list` | ⚠️ Confirm | ✅ |
| Avatar voices | ✅ `GET /api/v1/tools/avatar/voices` | ✅ | ✅ |
| Avatar characters | ✅ `GET /api/v1/tools/avatar/characters` | ✅ | ✅ |
| Scene templates | ✅ `GET /api/v1/tools/templates/scenes` | ✅ | ✅ |
| Interior styles (tools) | ✅ `GET /api/v1/tools/templates/interior-styles` | ✅ | ✅ |
| Video styles (tools) | ✅ `GET /api/v1/tools/styles` | ✅ | ✅ |

---

## 13. Session & Quota

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Heartbeat | ✅ `POST /api/v1/session/heartbeat` | ✅ | ✅ |
| Online count | ✅ `GET /api/v1/session/online-count` | ⚠️ Optional | ✅ |
| Daily quota | ✅ `GET /api/v1/quota/daily` | ✅ quota API | ✅ |
| Use quota | ✅ `POST /api/v1/quota/use` | ✅ | ✅ |

---

## 14. Prompts & Templates

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Groups / sub-topics | ✅ `GET /api/v1/prompts/groups`, `groups/{group}/sub-topics` | ⚠️ Confirm | ✅ |
| Default templates (demo) | ✅ `GET /api/v1/prompts/defaults/{group}` | ✅ | ✅ |
| Demo use template | ✅ `POST /api/v1/prompts/demo/use-template` | ✅ | ✅ |
| Subscribed generate/download | ✅ `POST/GET /api/v1/prompts/subscribed/*` | ✅ | ✅ |

---

## 15. Workflow

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| List topics/categories | ✅ `GET /api/v1/workflow/topics`, `categories` | ⚠️ Confirm | ✅ |
| Generate single/category | ✅ `POST /api/v1/workflow/generate*` | ⚠️ Confirm | ✅ |
| Preview topic | ✅ `GET /api/v1/workflow/preview/{topic_id}` | ⚠️ Confirm | ✅ |

---

## Summary: Gaps to Fix

| Area | Status |
|------|--------|
| **Dashboard Invoices** | ✅ **Done.** Backend: `GET /api/v1/subscriptions/invoices`, `GET /api/v1/subscriptions/invoices/{order_id}/pdf`. Frontend: `Invoices.vue`, route `/dashboard/invoices`, subscriptionApi.getInvoices/getInvoicePdf. |
| **Frontend (optional)** | Use `GET /api/v1/demo/topics` and `GET /api/v1/demo/topics/{tool_type}` for dynamic topic lists instead of hardcoding. |
| **Frontend (optional)** | Expose materials status (e.g. admin or status page) via `GET /api/v1/demo/materials/status` or `GET /materials/status`. |

---

## Quick Reference – Backend API Prefixes

| Prefix | Purpose |
|--------|---------|
| `/api/v1/auth` | Login, register, me, verify, password |
| `/api/v1/demo` | Presets, use-preset, topics, materials, inspiration, landing, upload |
| `/api/v1/tools` | remove-bg, product-scene, try-on, room-redesign, short-video, avatar, templates, models, voices, styles |
| `/api/v1/effects` | styles, apply-style, hd-enhance |
| `/api/v1/generate` | t2i, i2v, interior, pattern, product/*, video/* |
| `/api/v1/interior` | styles, room-types, redesign, generate, fusion, edit |
| `/api/v1/subscriptions` | plans, subscribe, status, cancel, history |
| `/api/v1/credits` | balance, estimate, transactions, packages, purchase, pricing |
| `/api/v1/landing` | stats, features, examples, testimonials, pricing, faq, contact |
| `/api/v1/admin` | users, materials, moderation, revenue, system |
| `/api/v1/prompts` | groups, defaults, demo/use-template, subscribed/* |
| `/api/v1/session` | heartbeat, online-count |
| `/api/v1/quota` | daily, user, use |
| `/api/v1/workflow` | topics, categories, generate, preview |
| `/api/v1/payments` | Webhooks (no user-facing list) |

---

## Quick Reference – Frontend Routes

| Route | View | Notes |
|-------|------|--------|
| `/` | LandingPage | ✅ |
| `/pricing` | Pricing | ✅ |
| `/tools/background-removal` | BackgroundRemoval.vue | ✅ |
| `/tools/effects` | ImageEffects.vue | ✅ |
| `/tools/product-scene` | ProductScene.vue | ✅ |
| `/tools/try-on` | TryOn.vue | ✅ |
| `/tools/room-redesign` | RoomRedesign.vue | ✅ |
| `/tools/short-video` | ShortVideo.vue | ✅ |
| `/tools/avatar` | AIAvatar.vue | ✅ |
| `/tools/pattern-generate`, etc. | PatternTopic.vue | ✅ |
| `/topics/pattern`, product, video | PatternTopic, ProductTopic, VideoTopic | ✅ |
| `/auth/login`, register, verify, forgot-password | Auth views | ✅ |
| `/dashboard` | Dashboard.vue | ✅ |
| `/dashboard/my-works` | MyWorks.vue | ✅ |
| `/dashboard/invoices` | Invoices.vue | ✅ |
| `/admin/*` | Admin views | ✅ |
| `/:pathMatch(.*)*` | NotFound | ✅ |
