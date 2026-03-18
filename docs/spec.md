# VidGo Platform – Function & Tool Coverage Spec

**Purpose:** Check that each function/tool is implemented in both **Backend** and **Frontend**. Use this to find gaps.
**Last Updated:** March 18, 2026

**Legend:**
- ✅ Implemented and wired
- ⚠️ Partial or preset-only / different flow
- ❌ Missing or not wired

---

## 1. Core AI Tools (8 Tools)

| # | Tool | Backend API | Backend Preset (Material DB) | Frontend Route | Status |
|---|------|-------------|-----------------------------|-----------------|--------|
| 1 | **Background Removal** (一鍵白底圖) | `POST /tools/remove-bg`, `POST /tools/remove-bg/batch` | ✅ `presets/background_removal` | ✅ `/tools/background-removal` | ✅ |
| 2 | **Product Scene** (商品場景圖) | `POST /tools/product-scene` | ✅ `presets/product_scene` | ✅ `/tools/product-scene`, `/tools/product-enhance` | ✅ |
| 3 | **Try-On** (AI試穿) | `POST /tools/try-on` | ✅ `presets/try_on` | ✅ `/tools/try-on` | ✅ |
| 4 | **Room Redesign** (毛坯精裝) | `POST /tools/room-redesign` | ✅ `presets/room_redesign` | ✅ `/tools/room-redesign` | ✅ |
| 5 | **Short Video** (短影片) | `POST /tools/short-video` | ✅ `presets/short_video` | ✅ `/tools/short-video`, `/tools/image-to-video`, `/tools/video-transform`, `/tools/product-video` | ✅ |
| 6 | **AI Avatar** (AI數位人) | `POST /tools/avatar` | ✅ `presets/ai_avatar` | ✅ `/tools/avatar` | ✅ |
| 7 | **Pattern Generate** (圖案生成) | `POST /generate/pattern/generate`, `POST /generate/pattern/transfer` | ✅ `presets/pattern_generate` | ✅ `/tools/pattern-generate`, `/tools/pattern-transfer`, `/tools/pattern-seamless` | ✅ |
| 8 | **Effect / Style Transfer** (圖片風格) | `GET/POST /effects/*`, `POST /tools/image-transform` | ✅ `presets/effect` | ✅ `/tools/effects`, `/tools/image-transform` | ✅ |

---

## 2. Demo / Preset-Only Flow

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| List tool types | ✅ `GET /demo/topics` | ✅ | ✅ |
| Get topics per tool | ✅ `GET /demo/topics/{tool_type}` | ✅ | ✅ |
| Get presets for tool | ✅ `GET /demo/presets/{tool_type}` | ✅ useDemoMode | ✅ |
| Use preset (get result) | ✅ `POST /demo/use-preset` | ✅ useDemoMode | ✅ |
| Download preset result | ✅ `GET /demo/download/{preset_id}` | ✅ (subscriber only) | ✅ |
| Inspiration gallery | ✅ `GET /demo/inspiration` | ✅ | ✅ |
| Tool showcases | ✅ `GET /demo/tool-showcases/{category}` | ✅ | ✅ |
| Search demos | ✅ `POST /demo/search` | ✅ | ✅ |

---

## 3. Auth

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Login | ✅ `POST /auth/login` | ✅ Login.vue | ✅ |
| Login (form) | ✅ `POST /auth/login/form` | ✅ | ✅ |
| Register | ✅ `POST /auth/register` | ✅ Register.vue (supports `?ref=CODE`) | ✅ |
| Logout | ✅ `POST /auth/logout` | ✅ | ✅ |
| Refresh token | ✅ `POST /auth/refresh` | ✅ client interceptor | ✅ |
| Get current user | ✅ `GET /auth/me` | ✅ auth store | ✅ |
| Update profile | ✅ `PUT /auth/me` | ✅ | ✅ |
| Change password | ✅ `POST /auth/me/change-password` | ✅ | ✅ |
| Verify email | ✅ `POST /auth/verify-email` | ✅ VerifyEmail.vue | ✅ |
| Verify code | ✅ `POST /auth/verify-code` | ✅ | ✅ |
| Resend verification | ✅ `POST /auth/resend-verification` | ✅ | ✅ |
| Forgot password | ✅ `POST /auth/forgot-password` | ✅ ForgotPassword.vue | ✅ |
| Reset password | ✅ `POST /auth/reset-password` | ✅ | ✅ |
| Delete account | ✅ `DELETE /auth/me` | ✅ (7-day work retention) | ✅ |
| Geo/language detect | ✅ `GET /auth/geo-language` | ✅ useGeoLanguage | ✅ |

---

## 4. Subscription & Payments

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| List plans | ✅ `GET /subscriptions/plans` | ✅ Pricing.vue | ✅ |

### Per-Plan Feature Restrictions

| Feature Flag | Description |
|-------------|-------------|
| `feature_clothing_transform` | Try-on / clothing transform access |
| `feature_goenhance` | GoEnhance style effects access |
| `feature_video_gen` | Video generation access |
| `feature_batch_processing` | Batch operations access |
| `feature_custom_styles` | Custom style creation |
| `pollo_limit` | Monthly Pollo AI generation limit |
| `goenhance_limit` | Monthly GoEnhance generation limit |

### Subscription Endpoints
| Subscribe (Paddle) | ✅ `POST /subscriptions/subscribe` | ✅ | ✅ |
| Subscribe (ECPay) | ✅ `POST /subscriptions/subscribe/direct` | ✅ | ✅ |
| Subscription status | ✅ `GET /subscriptions/status` | ✅ | ✅ |
| Cancel subscription | ✅ `POST /subscriptions/cancel` | ✅ | ✅ |
| Subscription history | ✅ `GET /subscriptions/history` | ✅ | ✅ |
| Invoices list | ✅ `GET /subscriptions/invoices` | ✅ Invoices.vue | ✅ |
| Invoice PDF | ✅ `GET /subscriptions/invoices/{id}/pdf` | ✅ | ✅ |
| Refund eligibility | ✅ `GET /subscriptions/refund-eligibility` | ✅ | ✅ |
| Paddle webhook | ✅ `POST /payments/paddle/webhook` | N/A | ✅ |
| ECPay callback | ✅ `POST /payments/ecpay/callback` | N/A | ✅ |
| ECPay result | ✅ `GET /payments/ecpay/result` | ✅ ECPayResult.vue | ✅ |
| Payment success | N/A | ✅ SubscriptionSuccess.vue | ✅ |
| Payment cancelled | N/A | ✅ SubscriptionCancelled.vue | ✅ |

---

## 5. Credits

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Balance | ✅ `GET /credits/balance` | ✅ credits store | ✅ |
| Estimate cost | ✅ `POST /credits/estimate` | ✅ | ✅ |
| Transactions | ✅ `GET /credits/transactions` | ✅ | ✅ |
| Packages | ✅ `GET /credits/packages` | ✅ | ✅ |
| Purchase credits | ✅ `POST /credits/purchase` | ✅ | ✅ |
| Pricing (services) | ✅ `GET /credits/pricing` | ✅ | ✅ |

### Credit Types

| Type | Reset | Expiry |
|------|-------|--------|
| `subscription_credits` | Weekly (Monday) via `credits_reset_at` | Resets each week |
| `purchased_credits` | Never | Never expire |
| `bonus_credits` | Never | Expire on `bonus_credits_expiry` |

### Demo Usage Limits
- Free users: limited to `demo_usage_limit` (default **2**) demo generations
- Tracked via `demo_usage_count` on User model

---

## 6. Landing & Marketing

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Landing stats | ✅ `GET /landing/stats` | ✅ LandingPage.vue | ✅ |
| Features | ✅ `GET /landing/features` | ✅ | ✅ |
| Examples | ✅ `GET /landing/examples` | ✅ | ✅ |
| Testimonials | ✅ `GET /landing/testimonials` | ✅ | ✅ |
| Pricing (landing) | ✅ `GET /landing/pricing` | ✅ | ✅ |
| FAQ | ✅ `GET /landing/faq` | ✅ | ✅ |
| Contact form | ✅ `POST /landing/contact` | ✅ | ✅ |
| Demo generate | ✅ `POST /landing/demo-generate` | ✅ | ✅ |

---

## 7. User Dashboard

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Dashboard home | ✅ auth/me, subscription, credits | ✅ Dashboard.vue | ✅ |
| My Works (generations) | ✅ `GET /user/generations` | ✅ MyWorks.vue | ✅ |
| Generation detail | ✅ `GET /user/generations/{id}` | ✅ | ✅ |
| Download generation | ✅ `GET /user/generations/{id}/download` | ✅ | ✅ |
| Delete generation | ✅ `DELETE /user/generations/{id}` | ✅ | ✅ |
| User stats | ✅ `GET /user/stats` | ✅ | ✅ |
| Invoices | ✅ `GET /subscriptions/invoices` | ✅ Invoices.vue | ✅ |
| Referrals | ✅ `GET /referrals/*` | ✅ Referrals.vue | ✅ |
| Social Accounts | ✅ `GET /social/accounts` | ✅ SocialAccounts.vue | ✅ |

---

## 8. Referral System

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Get referral code | ✅ `GET /referrals/code` | ✅ Referrals.vue | ✅ |
| Referral stats | ✅ `GET /referrals/stats` | ✅ | ✅ |
| Apply referral code | ✅ `POST /referrals/apply` | ✅ | ✅ |
| Leaderboard | ✅ `GET /referrals/leaderboard` | ✅ | ✅ |

---

## 9. Social Media Publishing

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| List connected accounts | ✅ `GET /social/accounts` | ✅ SocialAccounts.vue | ✅ |
| Disconnect account | ✅ `DELETE /social/accounts/{platform}` | ✅ | ✅ |
| OAuth flow | ✅ `GET /social/oauth/{platform}` | ✅ | ✅ |
| Facebook callback | ✅ `GET /social/oauth/facebook/callback` | N/A | ✅ |
| Instagram callback | ✅ `GET /social/oauth/instagram/callback` | N/A | ✅ |
| TikTok callback | ✅ `GET /social/oauth/tiktok/callback` | N/A | ✅ |
| YouTube callback | ✅ `GET /social/oauth/youtube/callback` | N/A | ✅ |
| Publish to platforms | ✅ `POST /social/publish/{generation_id}` | ✅ ShareToSocialModal.vue | ✅ |
| Post history | ✅ `GET /social/posts` | ✅ socialMediaApi | ✅ |
| Post analytics | ✅ `GET /social/posts/analytics` | ✅ socialMediaApi | ✅ |
| Token auto-refresh | ✅ token_refresh_service.py | N/A | ✅ |

---

## 10. Subscriber Uploads

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Available models | ✅ `GET /uploads/models/{tool_type}` | ✅ SubscriberUploadPanel | ✅ |
| Upload material | ✅ `POST /uploads/material` | ✅ | ✅ |
| My uploads | ✅ `GET /uploads/my-uploads` | ✅ | ✅ |
| Upload status | ✅ `GET /uploads/{upload_id}` | ✅ (polling) | ✅ |
| Download result | ✅ `GET /uploads/{upload_id}/download` | ✅ | ✅ |

---

## 11. Admin

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Dashboard stats | ✅ `GET /admin/stats/*` | ✅ AdminDashboard.vue | ✅ |
| Charts (generations, revenue, growth, tool usage, credits by tool, users by plan) | ✅ `GET /admin/charts/*` | ✅ Chart.js (vue-chartjs) LineChart, BarChart, DoughnutChart | ✅ |
| Date range selector | N/A | ✅ DateRangeSelector.vue (7D, 30D, 90D, 1Y, Custom) | ✅ |
| CSV export (API Cost, Tool Usage) | N/A | ✅ exportCsv.ts utility | ✅ |
| Manual refresh with timestamp | N/A | ✅ AdminDashboard.vue + admin store refreshAll() | ✅ |
| Error banner | N/A | ✅ AdminDashboard.vue (shows adminStore.error) | ✅ |
| Users list | ✅ `GET /admin/users` | ✅ AdminUsers.vue | ✅ |
| User detail | ✅ `GET /admin/users/{id}` | ✅ | ✅ |
| Ban/Unban user | ✅ `POST /admin/users/{id}/ban|unban` | ✅ | ✅ |
| Adjust credits | ✅ `POST /admin/users/{id}/credits` | ✅ | ✅ |
| Materials list | ✅ `GET /admin/materials` | ✅ AdminMaterials.vue | ✅ |
| Review material | ✅ `POST /admin/materials/{id}/review` | ✅ | ✅ |
| Moderation queue | ✅ `GET /admin/moderation/queue` | ✅ AdminModeration.vue | ✅ |
| System health | ✅ `GET /admin/health` | ✅ AdminSystem.vue | ✅ |
| AI services | ✅ `GET /admin/ai-services` | ✅ | ✅ |
| All generations | ✅ `GET /admin/generations` | ✅ | ✅ |
| Tool usage stats | ✅ `GET /admin/stats/tool-usage` | ✅ AdminDashboard.vue | ✅ |
| Earnings stats | ✅ `GET /admin/stats/earnings` | ✅ AdminDashboard.vue | ✅ |
| API cost breakdown | ✅ `GET /admin/stats/api-costs` | ✅ AdminDashboard.vue | ✅ |
| Active users/generations | ✅ `GET /admin/stats/active-users` | ✅ AdminDashboard.vue | ✅ |
| Real-time WebSocket | ✅ `WS /admin/ws/realtime` | ✅ AdminDashboard.vue | ✅ |

---

## 12. E-Invoice (Taiwan)

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Issue B2C invoice | ✅ `POST /einvoices/b2c` | ✅ InvoiceCreateForm.vue | ✅ |
| Issue B2B invoice | ✅ `POST /einvoices/b2b` | ✅ InvoiceCreateForm.vue | ✅ |
| Void invoice | ✅ `POST /einvoices/void` | ✅ InvoiceVoidDialog.vue | ✅ |
| List invoices | ✅ `GET /einvoices/` | ✅ Invoices.vue | ✅ |
| Invoice detail | ✅ `GET /einvoices/{id}` | ✅ Invoices.vue | ✅ |
| Invoice preferences | ✅ `PUT /einvoices/preferences` | ✅ Invoices.vue | ✅ |

---

## 13. Effects (Subscriber)

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| List styles | ✅ `GET /effects/styles` | ✅ effectsApi | ✅ |
| Apply style | ✅ `POST /effects/apply-style` | ✅ | ✅ |
| HD enhance | ✅ `POST /effects/hd-enhance` | ✅ | ✅ |
| Video enhance | ✅ `POST /effects/video-enhance` | ✅ | ✅ |

---

## 14. Interior Design

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Styles | ✅ `GET /interior/styles` | ✅ RoomRedesign.vue | ✅ |
| Room types | ✅ `GET /interior/room-types` | ✅ | ✅ |
| Redesign | ✅ `POST /interior/redesign` | ✅ | ✅ |
| Generate | ✅ `POST /interior/generate` | ✅ | ✅ |
| Fusion | ✅ `POST /interior/fusion` | ✅ | ✅ |
| Iterative edit | ✅ `POST /interior/edit` | ✅ | ✅ |
| Style transfer | ✅ `POST /interior/style-transfer` | ✅ | ✅ |
| Demo redesign | ✅ `POST /interior/demo/redesign` | ✅ | ✅ |
| Demo generate | ✅ `POST /interior/demo/generate` | ✅ | ✅ |

---

## 15. Generation API (Advanced)

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| T2I | ✅ `POST /generate/t2i` | ✅ | ✅ |
| I2V | ✅ `POST /generate/i2v` | ✅ | ✅ |
| Pattern generate/transfer | ✅ `POST /generate/pattern/*` | ✅ | ✅ |
| Product (remove-bg, scene, enhance) | ✅ `POST /generate/product/*` | ✅ | ✅ |
| Video (i2v, transform) | ✅ `POST /generate/video/*` | ✅ | ✅ |
| Models list | ✅ `GET /generate/models` | ✅ | ✅ |
| Service status | ✅ `GET /generate/service-status` | ✅ | ✅ |

---

## 16. Promotions

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Active promotions | ✅ `GET /promotions/active` | ✅ | ✅ |
| Packages with promos | ✅ `GET /promotions/packages` | ✅ | ✅ |
| Validate promo | ✅ `POST /promotions/validate` | ✅ | ✅ |
| Apply promo | ✅ `POST /promotions/apply` | ✅ | ✅ |
| Admin CRUD | ✅ `GET/POST/PUT/DELETE /promotions/admin/*` | ✅ | ✅ |

---

## 17. Session & Quota

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Heartbeat | ✅ `POST /session/heartbeat` | ✅ | ✅ |
| Online count | ✅ `GET /session/online-count` | ✅ | ✅ |
| Daily quota | ✅ `GET /quota/daily` | ✅ | ✅ |
| User quota | ✅ `GET /quota/user` | ✅ | ✅ |
| Use quota | ✅ `POST /quota/use` | ✅ | ✅ |
| Promo quota | ✅ `GET /quota/promo` | ✅ | ✅ |

---

## 18. Prompts & Templates

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Groups | ✅ `GET /prompts/groups` | ✅ | ✅ |
| Sub-topics | ✅ `GET /prompts/groups/{group}/sub-topics` | ✅ | ✅ |
| Generate prompt | ✅ `POST /prompts/generate` | ✅ | ✅ |
| Default templates | ✅ `GET /prompts/defaults/{group}` | ✅ | ✅ |
| Demo use template | ✅ `POST /prompts/demo/use-template` | ✅ | ✅ |
| Subscriber generate | ✅ `POST /prompts/subscribed/generate` | ✅ | ✅ |

---

## 19. Workflow

| Function | Backend | Frontend | Status |
|----------|---------|----------|--------|
| Topics list | ✅ `GET /workflow/topics` | ✅ | ✅ |
| Topic detail | ✅ `GET /workflow/topics/{id}` | ✅ | ✅ |
| Categories | ✅ `GET /workflow/categories` | ✅ | ✅ |
| Generate | ✅ `POST /workflow/generate` | ✅ | ✅ |
| Batch generate | ✅ `POST /workflow/generate/category/{cat}` | ✅ | ✅ |
| Preview | ✅ `GET /workflow/preview/{topic_id}` | ✅ | ✅ |

---

## Quick Reference – All Backend API Prefixes

| Prefix | Purpose |
|--------|---------|
| `/api/v1/auth` | Login, register, verify, password, profile |
| `/api/v1/demo` | Presets, use-preset, topics, showcases, inspiration, search |
| `/api/v1/tools` | 8 core tools + templates, models, voices, styles |
| `/api/v1/effects` | Style transfer, HD enhance, video enhance |
| `/api/v1/generate` | T2I, I2V, interior, pattern, product, video |
| `/api/v1/interior` | Interior design (redesign, generate, fusion, edit, style-transfer) |
| `/api/v1/subscriptions` | Plans, subscribe, status, cancel, invoices |
| `/api/v1/credits` | Balance, estimate, transactions, packages, pricing |
| `/api/v1/payments` | Paddle webhook, ECPay callback |
| `/api/v1/plans` | Plan listing |
| `/api/v1/promotions` | Promo codes, packages |
| `/api/v1/landing` | Stats, features, examples, testimonials, pricing, FAQ |
| `/api/v1/admin` | Dashboard stats, users, materials, moderation, API costs, active users |
| `/api/v1/einvoices` | Taiwan e-invoice (B2C/B2B issue, void, preferences) |
| `/api/v1/prompts` | Groups, templates, demo/subscriber generation |
| `/api/v1/session` | Heartbeat, online count |
| `/api/v1/quota` | Daily, user, promo quota |
| `/api/v1/workflow` | Topics, categories, generation |
| `/api/v1/user` | User generation history, stats |
| `/api/v1/uploads` | Subscriber uploads, models, download |
| `/api/v1/referrals` | Referral code, stats, apply, leaderboard |
| `/api/v1/social` | Social media OAuth (FB, IG, TikTok, YouTube), accounts, publish, post history, analytics |

---

## Quick Reference – All Frontend Routes

| Route | View | Auth |
|-------|------|------|
| `/` | LandingPage | - |
| `/pricing` | Pricing | - |
| `/tools/background-removal` | BackgroundRemoval | - |
| `/tools/product-scene` | ProductScene | - |
| `/tools/product-enhance` | ProductScene | - |
| `/tools/try-on` | TryOn | - |
| `/tools/room-redesign` | RoomRedesign | - |
| `/tools/short-video` | ShortVideo | - |
| `/tools/image-to-video` | ShortVideo | - |
| `/tools/video-transform` | ShortVideo | - |
| `/tools/product-video` | ShortVideo | - |
| `/tools/avatar` | AIAvatar | - |
| `/tools/effects` | ImageEffects | - |
| `/tools/image-transform` | ImageEffects | - |
| `/tools/pattern-generate` | PatternTopic | - |
| `/tools/pattern-transfer` | PatternTopic | - |
| `/tools/pattern-seamless` | PatternTopic | - |
| `/topics/pattern` | PatternTopic | - |
| `/topics/product` | ProductTopic | - |
| `/topics/video` | VideoTopic | - |
| `/auth/login` | Login | guest |
| `/auth/register` | Register | guest |
| `/auth/verify` | VerifyEmail | - |
| `/auth/forgot-password` | ForgotPassword | guest |
| `/dashboard` | Dashboard | auth |
| `/dashboard/my-works` | MyWorks | auth |
| `/dashboard/invoices` | Invoices | auth |
| `/dashboard/referrals` | Referrals | auth |
| `/dashboard/social-accounts` | SocialAccounts | auth |
| `/subscription/success` | SubscriptionSuccess | auth |
| `/subscription/cancelled` | SubscriptionCancelled | - |
| `/subscription/mock-checkout` | SubscriptionMockCheckout | auth |
| `/subscription/ecpay-result` | ECPayResult | - |
| `/admin` | AdminDashboard | admin |
| `/admin/users` | AdminUsers | admin |
| `/admin/materials` | AdminMaterials | admin |
| `/admin/moderation` | AdminModeration | admin |
| `/admin/revenue` | AdminRevenue | admin |
| `/admin/system` | AdminSystem | admin |
