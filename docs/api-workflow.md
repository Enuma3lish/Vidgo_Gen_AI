# VidGo API Workflow

> Current system architecture and API flow documentation.
> Last Updated: 2026-03-29

---

## System Overview

VidGo operates in **Dual Mode**:
- **Demo/free users:** developer/admin pre-generated results only. Serving is read-only from Material DB and Redis cache. No public runtime demo generation.
- **Subscribers:** real-time AI generation via external APIs, full-quality downloads
- 14-day media retention policy with automatic cleanup

### Demo Example Serving Contract

- Demo examples are generated manually by developers/admins via `scripts.main_pregenerate` or `POST /api/v1/admin/generate-demo`
- Developers must call the real provider APIs for every default example, verify the result is correct, and then place that finished example into Redis for serving
- Material DB is the durable source of truth for examples
- Redis is a non-expiring read cache warmed from Material DB
- User expectation: default examples are cache-backed examples only; user clicks must never trigger real provider generation for demo content
- Normal backend startup validates materials non-blockingly; it does not pregenerate examples automatically

### Stack

| Component | Tech | Port |
|-----------|------|------|
| Frontend | Vue 3 + Vite + TypeScript | 8501 |
| Backend API | FastAPI + SQLAlchemy (async) | 8001 |
| Database | PostgreSQL 15 | 5432 |
| Cache/Queue | Redis 7 | 6379 |
| Worker | ARQ (async task queue) | — |
| Mail | Mailpit (dev) | 8025 |

---

## 1. Authentication Flow

### Register → Verify → Login

```
POST /api/v1/auth/register
  {email, password, password_confirm}
      ↓
  Create user (email_verified=false)
  Generate 6-digit code → send email
  Save code to Redis (24h TTL)
      ↓
POST /api/v1/auth/verify-email
  {email, verification_code}
      ↓
  Validate code from Redis
  Set email_verified=true
      ↓
POST /api/v1/auth/login
  {email, password}
      ↓
  Check: email_verified? is_active?
  Generate JWT token pair:
    - access_token (30 min)
    - refresh_token (7 days)
      ↓
  Return: {user, tokens: {access, refresh}}
```

### All Auth Endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| `POST /auth/login` | - | Email + password login |
| `POST /auth/login/form` | - | Form-based login |
| `POST /auth/logout` | yes | Logout |
| `POST /auth/refresh` | - | Rotate token pair |
| `POST /auth/register` | - | Create account |
| `POST /auth/verify-email` | - | Verify email code |
| `POST /auth/resend-verification` | - | Resend verification email |
| `POST /auth/forgot-password` | - | Request password reset |
| `POST /auth/reset-password` | - | Reset password with token |
| `GET /auth/me` | yes | Get current user |
| `PUT /auth/me` | yes | Update profile |
| `POST /auth/me/change-password` | yes | Change password |
| `POST /auth/verify-code` | - | Verify auth code |
| `POST /auth/resend-code` | - | Resend auth code |
| `DELETE /auth/me` | yes | Delete account (7-day work retention) |
| `GET /auth/geo-language` | - | Detect user region/language |

### Auth Dependency Chain

```
get_current_user_optional()     → User | None  (for tools - demo-ready)
  └─ get_current_user()         → User         (required login)
       └─ get_current_active_user() → User     (active check)
            └─ get_current_superuser() → User  (admin only)
```

---

## 2. Demo/Preset Flow (Anonymous Users)

All primary demo endpoints are **no auth required**, and the visible results are **pre-generated** and **watermarked for free users**.

```
Developer/admin generates example
  → Call real provider API for the default prompt/input/effect combination
  → Verify the returned result is the intended example
  → CLI: python -m scripts.main_pregenerate --tool <tool>
    or Admin API: POST /api/v1/admin/generate-demo
  → Store approved Material row in DB
  → Put the finished example into Redis demo cache

User visits tool page (e.g. /tools/effects)
  ↓
GET /api/v1/demo/presets/{tool_type}
  → Returns pre-generated examples from Redis/Material-backed cache data
  → Each preset includes input media, result media, topic, and metadata
  ↓
User clicks a preset/example
  ↓
POST /api/v1/demo/use-preset
  {preset_id, session_id}
  ↓
  Lookup Material DB by preset/material ID
  Increment use_count
  Return watermarked URL for free users or full-quality URL for subscribers
  ↓
No external API generation occurs during the click flow
```

### Demo Example Lifecycle

```
Developer/admin trigger
  ↓
Mapping-based generation
  - scripts.main_pregenerate (PiAPI / Pollo / A2E clients by tool)
  - /api/v1/admin/generate-demo (single example generation)
  ↓
Material DB (APPROVED / FEATURED rows)
  ↓
Redis demo cache (read cache, no TTL)
  ↓
Frontend preset listing and demo retrieval
  ↓
Subscriber-only download or subscriber real-time generation via /tools/*
```

### User And Developer Expectations

- Developers own the correctness of every default example by generating it with the real API before release.
- Redis must already contain the finished example before any demo user tries that default case.
- Demo users only query existing cached examples; they do not create new demo outputs.

### Demo Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /demo/topics` | All tool types with their topics |
| `GET /demo/topics/{tool_type}` | Topics for specific tool |
| `GET /demo/presets/{tool_type}` | Pre-generated examples (watermarked) |
| `GET /demo/try-prompts/{tool_type}` | Selectable prompt options |
| `POST /demo/use-preset` | Lookup preset by Material ID, increment use count, return watermarked/full result |
| `GET /demo/download/{material_id}` | Subscriber-only redirect to the full-quality preset result |
| `GET /demo/inspiration` | Inspiration gallery |
| `POST /demo/generate` | Legacy runtime generation endpoint, now disabled (`410`) |
| `POST /demo/generate/paid` | Legacy runtime generation endpoint, now disabled (`410`) |
| `GET /demo/tool-showcases/{category}` | Tool showcase examples |
| `GET /demo/tool-showcases/{category}/{tool_id}` | Specific tool showcase |
| `POST /demo/tool-showcases/save` | Save showcase |
| `GET /demo/tool-categories` | Tool category list |
| `POST /demo/search` | Legacy runtime demo search/generate endpoint, now disabled (`410`) |
| `POST /demo/generate-image` | Legacy runtime image-generation endpoint, now disabled (`410`) |
| `POST /demo/generate-realtime` | Legacy runtime video-generation endpoint, now disabled (`410`) |
| `GET /demo/random` | Legacy random ImageDemo suggestion endpoint |
| `POST /demo/analyze` | Prompt analysis |

---

## 3. Tool Generation Flows (Subscribers)

### Two-Tier Logic (All Tools)

```
POST /api/v1/tools/{tool}
      ↓
  Auth: get_current_user_optional()
      ↓
  is_subscribed_user(user)?
      ↓                    ↓
    YES (subscriber)     NO (demo user)
      ↓                    ↓
  Check credits        Read pre-generated demo from Redis or Material DB
  Call external API    Return watermarked result
  Save to UserGen      Return {credits_used: 0}
  Deduct credits
  Return result
```

Notes:
- Backend demo helpers under `/tools/*`, `/effects/*`, and `/generate/*` now read pre-generated demos only.
- Vue demo actions now resolve the selected default example through `/demo/use-preset` instead of using local result URLs.

### Tool Endpoints

| Endpoint | Tool | Credits |
|----------|------|---------|
| `POST /tools/remove-bg` | Background Removal | 3 |
| `POST /tools/remove-bg/batch` | Batch Background Removal | 3 × count |
| `POST /tools/product-scene` | Product Scene | 10 |
| `POST /tools/try-on` | AI Try-On | 15 |
| `POST /tools/room-redesign` | Room Redesign | 20 |
| `POST /tools/short-video` | Short Video (I2V) | 25-35 |
| `POST /tools/avatar` | AI Avatar | 30 |
| `POST /tools/image-transform` | Image Transform | varies |
| `GET /tools/avatar/voices` | List avatar voices | - |
| `GET /tools/avatar/characters` | List avatar characters | - |
| `GET /tools/templates/scenes` | Scene templates | - |
| `GET /tools/templates/interior-styles` | Interior style templates | - |
| `GET /tools/models/list` | Available AI models | - |
| `GET /tools/voices/list` | Available voices | - |
| `GET /tools/styles` | Available styles | - |

### Tool Details

**Background Removal** — `POST /tools/remove-bg`
- Input: `{image_url}`
- API: PiAPI
- Result: Transparent PNG
- Batch: `POST /tools/remove-bg/batch` for multiple images

**Product Scene** — `POST /tools/product-scene`
- Input: `{image_url, scene_type}`
- Pipeline: Remove BG → Generate scene (T2I) → Composite (PIL)
- Scene types: studio, nature, luxury, minimal, lifestyle, beach, urban, garden

**AI Try-On** — `POST /tools/try-on`
- Input: `{model_image_url | model_id, garment_image_url}`
- API: PiAPI (specialized try-on)
- Models: preset models (male + female)

**Room Redesign** — `POST /tools/room-redesign`
- Input: `{image_url, style_id, room_type}`
- API: PiAPI (Wan Doodle) — no fallback

**Short Video** — `POST /tools/short-video`
- Input: `{image_url, motion_strength, style?, script?, voice_id?}`
- API: PiAPI I2V — no fallback

**AI Avatar** — `POST /tools/avatar`
- Input: `{image_url, script, language, voice_id, aspect_ratio, resolution}`
- API: PiAPI
- Languages: en, zh-TW, ja, ko

---

## 4. Effects (Style Transfer)

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /effects/styles` | no | List all styles |
| `POST /effects/apply-style` | yes | Apply style transfer (8 credits) |
| `POST /effects/hd-enhance` | yes | HD upscale (12 credits) |
| `POST /effects/video-enhance` | yes | Video enhance (15 credits) |

---

## 5. Generation API (Advanced)

| Endpoint | Description |
|----------|-------------|
| `POST /generate/t2i` | Text-to-Image |
| `POST /generate/i2v` | Image-to-Video |
| `POST /generate/interior` | Interior generation |
| `GET /generate/service-status` | External API status |
| `GET /generate/interior-styles` | Interior style list |
| `GET /generate/room-types` | Room type list |
| `POST /generate/pattern/generate` | Pattern generation |
| `POST /generate/pattern/transfer` | Pattern transfer |
| `POST /generate/product/remove-background` | Product BG removal |
| `POST /generate/product/generate-scene` | Product scene gen |
| `POST /generate/product/enhance` | Product enhancement |
| `POST /generate/video/image-to-video` | I2V generation |
| `POST /generate/video/transform` | Video transform |
| `GET /generate/video/styles` | Video style list |
| `GET /generate/examples/{topic}` | Topic examples |
| `GET /generate/models` | Available models |
| `POST /generate/upload` | Upload for generation |
| `GET /generate/api-status` | API health check |

---

## 6. Interior Design

| Endpoint | Description |
|----------|-------------|
| `GET /interior/styles` | Design style list |
| `GET /interior/room-types` | Room type list |
| `POST /interior/redesign` | Room redesign (subscriber) |
| `POST /interior/generate` | Room generate from scratch |
| `POST /interior/fusion` | Style fusion |
| `POST /interior/edit` | Iterative edit (conversation) |
| `DELETE /interior/edit/{conversation_id}` | End edit session |
| `POST /interior/style-transfer` | Style transfer |
| `POST /interior/demo/redesign` | Demo redesign (preset) |
| `POST /interior/demo/generate` | Demo generate (preset) |

---

## 7. Prompt Templates

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /prompts/groups` | no | Prompt groups |
| `GET /prompts/groups/{group}/sub-topics` | no | Sub-topics for group |
| `POST /prompts/generate` | no | Generate prompt |
| `GET /prompts/defaults/{group}` | no | Default templates |
| `GET /prompts/cached` | no | Cached prompts |
| `GET /prompts/templates/{group}` | no | Templates by group |
| `GET /prompts/similar` | no | Similar prompts |
| `POST /prompts/usage` | no | Record usage |
| `POST /prompts/demo/use-template` | no | Use demo template |
| `GET /prompts/demo/download/{id}` | no | Download demo result |
| `POST /prompts/subscribed/generate` | yes | Subscriber generate |
| `GET /prompts/subscribed/download/{id}` | yes | Subscriber download |
| `GET /prompts/check-access` | optional | Check access level |
| `POST /prompts/admin/templates` | admin | Manage templates |
| `POST /prompts/admin/cache-result` | admin | Cache a result |
| `POST /prompts/admin/seed` | admin | Seed templates |

---

## 8. Subscriber Uploads

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /uploads/models/{tool_type}` | yes | Available models per tool |
| `POST /uploads/material` | yes | Upload material for generation |
| `GET /uploads/my-uploads` | yes | List my uploads |
| `GET /uploads/{upload_id}` | yes | Get upload status |
| `GET /uploads/{upload_id}/download` | yes | Download result |

---

## 9. User Works (My Gallery)

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /user/generations` | yes | List user's generations (paginated) |
| `GET /user/generations/{id}` | yes | Generation detail |
| `GET /user/generations/{id}/download` | yes | Download generation |
| `DELETE /user/generations/{id}` | yes | Delete generation |
| `GET /user/stats` | yes | User usage statistics |

---

## 10. Provider Routing

External AI services (no failover):

| Task | Provider | Backup | Note |
|------|----------|--------|------|
| Runtime subscriber generation (T2I, I2I, I2V, T2V, V2V, Interior, Avatar, BG Removal, Effects, 3D, Try-On, Upscale) | PiAPI-based provider router | NONE | If down → generation endpoints fail gracefully |
| Content Moderation | Gemini | NONE | Detect illegal/inappropriate uploads |
| Developer/admin example generation | `scripts.main_pregenerate` and `/api/v1/admin/generate-demo` | NONE | Uses PiAPI, Pollo, and A2E clients depending on tool |

### TaskType Enum
```python
class TaskType(str, Enum):
    T2I = "text_to_image"
    I2V = "image_to_video"
    T2V = "text_to_video"
    V2V = "video_style_transfer"
    INTERIOR = "interior_design"
    INTERIOR_3D = "interior_3d"
    AVATAR = "avatar"
    UPSCALE = "upscale"
    EFFECTS = "effects"
    MODERATION = "moderation"
    BACKGROUND_REMOVAL = "background_removal"
    I2I = "image_to_image"
    MATERIAL_GENERATION = "material_generation"
```

### Provider Configuration
- **PiAPI**: Base URL `https://api.piapi.ai/api/v1`, X-API-Key header
- **Pollo**: Used by pregeneration flows for video generation where applicable
- **A2E**: Used by pregeneration flows for AI avatar generation
- **Gemini**: Used for moderation and some legacy/demo support paths
- **No failover in the demo serving path**: pre-generated demo retrieval does not call external providers at request time
- **Provider names never exposed** to end users

---

## 11. Credit & Quota System

### Credit Costs Per Tool

| Tool | Credits |
|------|---------|
| Background Removal | 3 |
| Product Scene | 10 |
| AI Try-On | 15 |
| Room Redesign | 20 |
| Short Video | 25-35 |
| AI Avatar | 30 |
| Apply Style Effect | 8 |
| HD Enhance | 12 |
| Video Enhance | 15 |

### Credit Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /credits/balance` | Current balance |
| `POST /credits/estimate` | Estimate cost before action |
| `GET /credits/transactions` | Transaction history |
| `GET /credits/packages` | Available credit packages |
| `POST /credits/purchase` | Purchase credits |
| `GET /credits/pricing` | Service pricing list |
| `POST /credits/add` | Admin: add credits |

### Credit Types

| Type | Reset | Expiry |
|------|-------|--------|
| `subscription_credits` | Weekly (Monday) via `credits_reset_at` | Resets each week |
| `purchased_credits` | Never | Never expire |
| `bonus_credits` | Never | Expire on `bonus_credits_expiry` |

### Model Selection & Multipliers
Paid users can select AI models for upload-based generation. Better models cost more credits:

| Model | Multiplier | Tools |
|-------|------------|-------|
| default | 1× | All tools |
| wan_pro | 2× | product_scene, room_redesign, pattern_generate, effect, short_video |
| gemini_pro | 2× | ai_avatar, try_on |

### Promotion Code Ownership
- **Paid subscribers**: Automatically receive unique promotion code upon subscription
- **Free users**: Cannot create promotion codes, but can use others' codes
- **Admin**: Can create special promotion codes with custom credits/discounts
- **Code usage**: When someone uses a promotion code, code owner earns credits

### 7-Day Work Retention
- **Active subscribers**: All works stored indefinitely
- **Cancelled subscribers**: Works retained for 7 days post-cancellation
- **During retention**: Can download existing works, cannot generate new works
- **Account deletion**: All works deleted immediately (no retention)
- **Media expiry**: Works older than 14 days have media URLs cleared

### Free Quota (Demo Users)

- Demo usage limited to `demo_usage_limit` (default **2**) generations per user

```
GET /api/v1/quota/daily   → {remaining, total, reset_at}
GET /api/v1/quota/user    → {remaining, total, is_exhausted}
POST /api/v1/quota/use    → decrement both counters
GET /api/v1/quota/promo   → promotional quota info
```

---

## 12. Subscription & Payment Flow

### Subscribe

```
POST /api/v1/subscriptions/subscribe
  {plan_id, billing_cycle: "monthly"|"yearly", payment_method: "paddle"|"ecpay"}
      ↓
  Create Order
  Generate payment checkout URL (Paddle or ECPay)
      ↓
  Return: {subscription_id, checkout_url}
      ↓
  User completes payment
      ↓
  Webhook confirms → activate plan
  Set user.current_plan_id, plan_expires_at
  Add monthly_credits to balance
```

### Subscription Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /subscriptions/plans` | Available plans |
| `POST /subscriptions/subscribe` | Start subscription (Paddle) |
| `POST /subscriptions/subscribe/direct` | Direct subscription (ECPay) |
| `GET /subscriptions/status` | Current subscription status |
| `POST /subscriptions/cancel` | Cancel subscription |
| `GET /subscriptions/history` | Subscription history |
| `GET /subscriptions/invoices` | Invoice list |
| `GET /subscriptions/invoices/{id}/pdf` | Download invoice PDF |
| `GET /subscriptions/refund-eligibility` | Check refund eligibility |

### Payment Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /payments/paddle/checkout` | Create Paddle checkout |
| `POST /payments/paddle/webhook` | Paddle webhook handler |
| `GET /payments/paddle/customer-portal` | Paddle customer portal |
| `POST /payments/ecpay/callback` | ECPay server callback |
| `GET /payments/ecpay/result` | ECPay result page redirect |
| `GET /payments/order/{order_number}` | Order status |
| `POST /payments/mock/complete/{order_number}` | Mock payment (dev) |

### Plan Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /plans` | All plans |
| `GET /plans/comparison` | Detailed plan comparison table |
| `GET /plans/current` | Current user's subscription |
| `POST /plans/upgrade` | Upgrade to a higher plan |
| `POST /plans/downgrade` | Downgrade plan |
| `GET /plans/check-permission` | Check if a plan/user can use a service |
| `GET /plans/check-concurrent` | Check concurrent generation limit |

---

## 13. Referral System

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /referrals/code` | yes | Get my referral code |
| `GET /referrals/stats` | yes | Referral statistics |
| `POST /referrals/apply` | yes | Apply a referral code |
| `GET /referrals/leaderboard` | no | Top referrers |

Flow: User shares `?ref=CODE` link → new user registers → both get bonus credits.

---

## 14. Social Media Publishing

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /social/accounts` | yes | List connected accounts |
| `DELETE /social/accounts/{platform}` | yes | Disconnect account |
| `GET /social/oauth/{platform}` | yes | Start OAuth flow |
| `GET /social/oauth/facebook/callback` | - | Facebook OAuth callback |
| `GET /social/oauth/instagram/callback` | - | Instagram OAuth callback |
| `GET /social/oauth/tiktok/callback` | - | TikTok OAuth callback |
| `GET /social/oauth/youtube/callback` | - | YouTube OAuth callback (Google OAuth 2.0) |
| `POST /social/oauth/mock-connect` | yes | Mock connect (dev) |
| `POST /social/publish/{generation_id}` | yes | Publish to connected platforms (auto-refreshes tokens before publish) |
| `GET /social/posts` | yes | Paginated post history |
| `GET /social/posts/analytics` | yes | Aggregated post analytics |

Supported platforms: Facebook (Graph API v21.0), Instagram (Graph API v21.0), TikTok, YouTube (Data API v3 resumable upload).

### Token Refresh Flow

```
Before each publish attempt:
      |
  Token refresh service checks token expiry
      |
  Token expires within 24 hours?
      |                    |
    YES                   NO
      |                    |
  Refresh token        Proceed with publish
  (platform-specific)
      |
  Facebook: Exchange for long-lived token via Graph API
  TikTok: Refresh via TikTok OAuth refresh endpoint
  YouTube: Refresh via Google OAuth 2.0 refresh token
      |
  Update stored token + expires_at
      |
  Proceed with publish
```

### YouTube OAuth Flow

```
GET /api/v1/social/oauth/youtube
      |
  Generate Google OAuth 2.0 authorization URL
  Scopes: youtube.upload, youtube.readonly
      |
  User authorizes on Google consent screen
      |
  Callback: GET /api/v1/social/oauth/youtube/callback
      |
  Exchange code for access_token + refresh_token
  Store token with expires_at
      |
  Publishing: Resumable upload via YouTube Data API v3
```

---

## 15. Promotions

| Endpoint | Description |
|----------|-------------|
| `GET /promotions/active` | Active promotions |
| `GET /promotions/packages` | Credit packages with promotions |
| `POST /promotions/validate` | Validate promo code |
| `POST /promotions/apply` | Apply promo code |
| `GET /promotions/admin/list` | Admin: list all promotions |
| `POST /promotions/admin/create` | Admin: create promotion |
| `PUT /promotions/admin/{id}` | Admin: update promotion |
| `DELETE /promotions/admin/{id}` | Admin: delete promotion |
| `POST /promotions/admin/packages/create` | Admin: create credit package |
| `PUT /promotions/admin/packages/{id}` | Admin: update credit package |

---

## 16. Workflow System

| Endpoint | Description |
|----------|-------------|
| `GET /workflow/topics` | Workflow topic list |
| `GET /workflow/topics/{id}` | Topic details |
| `GET /workflow/categories` | Category list |
| `POST /workflow/generate` | Generate from workflow |
| `POST /workflow/generate/category/{cat}` | Batch generate by category |
| `GET /workflow/preview/{topic_id}` | Preview topic |

---

## 17. Session & Landing

### Session

| Endpoint | Description |
|----------|-------------|
| `POST /session/heartbeat` | Session heartbeat (online tracking) |
| `GET /session/online-count` | Current online user count |

### Landing Page Data

| Endpoint | Description |
|----------|-------------|
| `GET /landing/stats` | Platform statistics |
| `GET /landing/features` | Feature highlights |
| `GET /landing/examples` | Example gallery |
| `GET /landing/testimonials` | User testimonials |
| `GET /landing/pricing` | Pricing display |
| `GET /landing/faq` | FAQ items |
| `POST /landing/contact` | Contact form |
| `POST /landing/demo-generate` | Landing page demo |

---

## 18. Admin Dashboard

All admin routes require superuser authentication.

| Endpoint | Description |
|----------|-------------|
| `GET /admin/stats/online` | Online user count |
| `GET /admin/stats/users-by-tier` | Users grouped by tier |
| `GET /admin/stats/dashboard` | Dashboard overview stats |
| `GET /admin/charts/generations` | Generation chart data |
| `GET /admin/charts/revenue` | Revenue chart data |
| `GET /admin/charts/users-growth` | User growth chart |
| `GET /admin/users` | User list |
| `GET /admin/users/{id}` | User detail |
| `POST /admin/users/{id}/ban` | Ban user |
| `POST /admin/users/{id}/unban` | Unban user |
| `POST /admin/users/{id}/credits` | Adjust credits |
| `GET /admin/materials` | Material list |
| `POST /admin/materials/{id}/review` | Review material |
| `GET /admin/moderation/queue` | Content moderation queue |
| `GET /admin/health` | System health |
| `GET /admin/ai-services` | AI service status |
| `GET /admin/generations` | All generations |
| `GET /admin/stats/tool-usage` | Tool usage by frequency and credits |
| `GET /admin/stats/earnings` | Weekly/monthly earnings |
| `GET /admin/stats/api-costs` | Per-service API cost breakdown (week/month) |
| `GET /admin/stats/active-users` | Active generations + online sessions |
| `WS /admin/ws/realtime` | Real-time stats (online users, active generations) |

---

## 19. E-Invoice (Taiwan)

All e-invoice routes require authentication. Integrates with ECPay staging/production API.

| Endpoint | Description |
|----------|-------------|
| `POST /einvoices/b2c` | Issue B2C invoice (consumer, with carrier/donation support) |
| `POST /einvoices/b2b` | Issue B2B invoice (business, requires 8-digit tax ID) |
| `POST /einvoices/void` | Void invoice (same bimonthly tax period only) |
| `GET /einvoices/` | List user's invoices |
| `GET /einvoices/{id}` | Get invoice detail |
| `PUT /einvoices/preferences` | Update default carrier/donation preferences |

---

## 20. Media Cleanup (14-Day Retention)

```
Startup:
  → Run initial cleanup (clear already-expired media)
  → Start hourly background task

Every hour:
  → Scan user_generations table
  → Find entries older than 14 days
  → Clear media URLs (result_url, result_video_url)
  → Log expired count
```

---

## 21. Frontend Routes

### Public Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | LandingPage | Marketing page |
| `/tools/background-removal` | BackgroundRemoval | Remove backgrounds |
| `/tools/product-scene` | ProductScene | Product scene generation |
| `/tools/product-enhance` | ProductScene | Product enhancement |
| `/tools/try-on` | TryOn | Virtual try-on |
| `/tools/room-redesign` | RoomRedesign | Room redesign |
| `/tools/short-video` | ShortVideo | Image-to-video |
| `/tools/image-to-video` | ShortVideo | I2V alias |
| `/tools/video-transform` | ShortVideo | Video transform alias |
| `/tools/product-video` | ShortVideo | Product video alias |
| `/tools/avatar` | AIAvatar | AI avatar videos |
| `/tools/effects` | ImageEffects | Style transfer |
| `/tools/image-transform` | ImageEffects | Image transform |
| `/tools/pattern-generate` | PatternTopic | Pattern generation |
| `/tools/pattern-transfer` | PatternTopic | Pattern transfer |
| `/tools/pattern-seamless` | PatternTopic | Seamless pattern |
| `/topics/pattern` | PatternTopic | Pattern topic hub |
| `/topics/product` | ProductTopic | Product topic hub |
| `/topics/video` | VideoTopic | Video topic hub |
| `/pricing` | Pricing | Pricing page |

### Auth Pages

| Route | Page |
|-------|------|
| `/auth/login` | Login |
| `/auth/register` | Register (supports `?ref=CODE`) |
| `/auth/verify` | Email verification |
| `/auth/forgot-password` | Password reset |

### Dashboard (Auth Required)

| Route | Page |
|-------|------|
| `/dashboard` | Dashboard overview |
| `/dashboard/my-works` | My generations gallery |
| `/dashboard/invoices` | Billing & invoices |
| `/dashboard/referrals` | Referral program |
| `/dashboard/social-accounts` | Connected social accounts |

### Subscription

| Route | Page |
|-------|------|
| `/subscription/success` | Payment success |
| `/subscription/cancelled` | Payment cancelled |
| `/subscription/mock-checkout` | Mock checkout (dev) |
| `/subscription/ecpay-result` | ECPay result |

### Admin (Superuser Only)

| Route | Page |
|-------|------|
| `/admin` | Admin dashboard |
| `/admin/users` | User management |
| `/admin/materials` | Material management |
| `/admin/moderation` | Content moderation |
| `/admin/revenue` | Revenue analytics |
| `/admin/system` | System health |

---

## 22. Root-Level Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check + non-blocking material validation status |
| `GET /materials/status` | Material DB coverage/status report |
| `POST /materials/generate` | Manual material generation trigger for the legacy material-generator service |

### Operational Notes

- Normal backend runtime does not auto-pregenerate demo examples.
- Developer/operator workflows may still run `scripts.main_pregenerate`, `scripts.seed_materials_if_empty`, or the `init-materials` Docker profile manually.
- The backend Docker entrypoint script is present, but the default `docker-compose.yml` backend service currently overrides the entrypoint and starts `uvicorn` directly.
