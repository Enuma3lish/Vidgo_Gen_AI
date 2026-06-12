# VidGo AI Platform - Backend Architecture

> Last updated: 2026-06-12

**Version:** 8.0
**Last Updated:** June 12, 2026
**Framework:** FastAPI + Python 3.12
**Database:** PostgreSQL + Redis
**Mode:** Dual-Mode — Preset-Only (free) + Real-API (subscribers)
**Target Audience:** Small businesses (SMB) selling everyday products/services

---

## 0. User Tiers & Access Control

### 0.1 Free/Demo Users (Preset-Only)
Visitors try AI tools by selecting pre-generated presets. No runtime API calls — all results are pre-computed and stored in Material DB.

**Flow:**
1. Pre-generation (startup/CLI): Prompts → AI APIs → results stored in `materials` table
2. User trial: Frontend loads presets from `/api/v1/demo/presets/{tool_type}` → user selects → backend returns watermarked result via O(1) Material DB lookup
3. Download blocked. All demo results carry a watermark; download requires subscription.

### 0.2 Subscribers (Real-API Mode)
Subscribers upload their own images and trigger live AI API calls. Results are returned without watermarks and can be downloaded.

**Flow:**
1. Upload: `POST /api/v1/uploads/material` (multipart form: file + tool_type + model_id + prompt)
2. Credit deduction: Credits deducted per tool via the deduction firewall — `ServicePricing` DB rows override the code fallback constants
3. Generation: Backend calls AI provider in real time
4. Result: `result_url` / `result_video_url` stored without watermark; `GET /api/v1/uploads/{id}/download`

### 0.3 Preset Download (Subscribers)
Subscribers can download full-quality (no watermark) versions of preset gallery results:
- `POST /api/v1/demo/use-preset` returns `result_url` (full quality) when authenticated as subscriber
- `GET /api/v1/demo/download/{material_id}` redirects to full-quality result URL

### 0.4 Model Selection & Plan-Tier Gating
Paid users can select AI models for generation. Premium model variants are gated by plan tier (`tier_config.TIER_ALLOWED_MODELS`):

| Tier | Allowed model types |
|------|---------------------|
| free / basic | `default` only |
| pro+ | `default`, `wan_pro`, `gemini_pro`, `midjourney`, `veo` |

Legacy upload-path multipliers (`MODEL_CREDIT_MULTIPLIERS` env): `default` 1×, `wan_pro` 2×, `gemini_pro` 2×. The live per-model charge for video/image endpoints comes from the VidGo 3.0 credit tables (see §5.5). `require_model_access` rejects premium `model_id`s (e.g. `kling_omni`, `sora2_pro`, `veo`) before billing when the user's plan doesn't include them.

### 0.5 Referral System
Users earn bonus credits by inviting others:
- Referrer: **+50 credits** (`REFERRAL_BONUS_CREDITS`) per successful registration via their code
- New user: **+40 credits** (`REFERRAL_WELCOME_CREDITS`) when registering with a referral code
- Registration bonus (no code needed): **+40 credits** expiring in 30 days (`REGISTRATION_BONUS_CREDITS` / `REGISTRATION_BONUS_DAYS`)
- Endpoints: `GET /referrals`, `GET /referrals/code`, `GET /referrals/stats`, `POST /referrals/apply`, `GET /referrals/leaderboard`

### 0.6 Social Media Publishing
Users can connect social accounts and publish generations directly:
- Supported platforms: Facebook, Instagram, TikTok, YouTube
- OAuth flow: `GET /social/oauth/{platform}` → callback → account linked
- YouTube uses Google OAuth 2.0 with resumable upload to YouTube Data API v3
- Meta Graph API version: v21.0
- Publish: `POST /social/publish/{generation_id}` → publish to selected platforms
- Token refresh: Automatic refresh of tokens expiring within 24 hours (Facebook, TikTok, YouTube)
- Post tracking: SocialPost model records each published post with status and analytics
- Post history: `GET /social/posts` (paginated), `GET /social/posts/analytics` (aggregated)

### 0.7 Account Deletion & Work Retention
- `DELETE /auth/me` — soft-deletes user account
- User model fields: `subscription_cancelled_at`, `work_retention_until`
- Works retained for **7 days** after deletion/cancellation before purge

### 0.8 Demo Usage Limits
- Free users limited to `demo_usage_limit` (default **2**) demo generations
- Tracked via `demo_usage_count` on User model

### 0.9 Credit Types & Reset
Credits are split into three types:
| Type | Reset | Expiry |
|------|-------|--------|
| `subscription_credits` | Per billing cycle — ARQ `monthly_credit_reset_task` (1st of month 00:05 UTC) + daily `auto_renew_subscriptions_task`; tracked via `credits_reset_at` | Reset each cycle |
| `purchased_credits` | Never | Never expire |
| `bonus_credits` | Never | Expire on `bonus_credits_expiry` (daily cleanup task at 02:00 UTC) |

### 0.10 Per-Plan Feature Restrictions
Plans can restrict tool access via feature flags:
- `feature_clothing_transform`, `feature_goenhance`, `feature_video_gen`
- `feature_batch_processing`, `feature_custom_styles`

### 0.11 Media Retention Policy
14-day media retention with automatic cleanup:
- Hourly background task scans `user_generations` table
- Entries older than 14 days have media URLs cleared
- Initial cleanup runs on startup

### 0.12 Custom-Prompt Access Gate
Free accounts may run unmodified presets (served from the demo cache); a typed or edited prompt requires an **active subscription with a bound credit card** (`app/services/access_gate.py`, shared by tools + generation routers). Blocked requests return `error_code="subscription_card_required"` so the frontend can pop a subscribe + add-payment CTA. Admins and internal test accounts bypass the gate.

---

## 1. System Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                          VidGo AI Backend Architecture                             |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  +-----------------------------------------------------------------------------+ |
|  |                         Load Balancer (Docker/Cloud Run)                     | |
|  +------------------------------------+----------------------------------------+ |
|                                       |                                          |
|  +------------------------------------+----------------------------------------+ |
|  |                           FastAPI Application                                | |
|  |  +-----------------------------------------------------------------------+  | |
|  |  |                          API Gateway Layer                            |  | |
|  |  |  +----------+ +----------+ +----------+ +----------+ +-------------+ |  | |
|  |  |  |   Auth   | |  Demo    | |  Tools   | | Credits  | |   Admin     | |  | |
|  |  |  | Endpoints| | Endpoints| | Endpoints| | Endpoints| |  Endpoints  | |  | |
|  |  |  +----------+ +----------+ +----------+ +----------+ +-------------+ |  | |
|  |  |  +----------+ +----------+ +----------+ +----------+ +-------------+ |  | |
|  |  |  | Interior | | Uploads  | | Referral | |  Social  | |  E-Invoice  | |  | |
|  |  |  | Endpoints| | Endpoints| | Endpoints| | Endpoints| |  Endpoints  | |  | |
|  |  |  +----------+ +----------+ +----------+ +----------+ +-------------+ |  | |
|  |  +-----------------------------------------------------------------------+  | |
|  |                                                                             | |
|  |  +-----------------------------------------------------------------------+  | |
|  |  |                          Service Layer                                |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  |  | Material      | | Demo          | | Credit        | | Tier/Plan  | |  | |
|  |  |  | Lookup        | | Service       | | Service       | | Gates      | |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  |  | Interior      | | Subscription  | | Invoice       | | Referral   | |  | |
|  |  |  | Design/Growth | | Service       | | (Giveme/ECPay | | Service    | |  | |
|  |  |  | Service       | |               | |  /PayPal)     | |            | |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  |  | PayPal        | | Social Media  | | Media Cleanup | | Moderation | |  | |
|  |  |  | Service       | | Service       | | Service       | | Service    | |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  +-----------------------------------------------------------------------+  | |
|  |                                                                             | |
|  |  +-----------------------------------------------------------------------+  | |
|  |  |             AI Provider Layer (all REST — MCP removed 2026-05-26)    |  | |
|  |  |  +---------------+ +---------------+ +-------------------+ +-------+ |  | |
|  |  |  | PiAPI REST    | | Pollo.ai REST | | Vertex AI (GCP)   | | A2E   | |  | |
|  |  |  | PRIMARY:      | | BACKUP:       | | - Gemini (ADC):   | | Avatar| |  | |
|  |  |  | T2I,I2I,I2V,  | | I2V only      | |   image backup,   | | backup| |  | |
|  |  |  | T2V,Avatar,   | | (Kling/Pix-   | |   moderation,     | |       | |  | |
|  |  |  | Interior,     | |  verse/Hailuo | |   material gen    | |       | |  | |
|  |  |  | BG Rem,Effects| |  /Wan models) | | - Veo: video      | |       | |  | |
|  |  |  | Trellis 3D,   | |               | |   backup          | |       | |  | |
|  |  |  | ControlNet    | |               | |                   | |       | |  | |
|  |  |  +---------------+ +---------------+ +-------------------+ +-------+ |  | |
|  |  +-----------------------------------------------------------------------+  | |
|  +-----------------------------------------------------------------------------+ |
|                                                                                   |
|  +-----------------------------------------------------------------------------+ |
|  |                              Data Layer                                      | |
|  |  +---------------+ +---------------+ +---------------+ +----------------+   | |
|  |  |  PostgreSQL   | |    Redis      | |  GCS Bucket   | |  Material DB   |   | |
|  |  |  (Main DB)    | | (Cache/Queue) | | (Media Files) | | (Pre-generated)|   | |
|  |  +---------------+ +---------------+ +---------------+ +----------------+   | |
|  +-----------------------------------------------------------------------------+ |
+-----------------------------------------------------------------------------------+
```

---

## 2. Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI application entry + lifespan
│   ├── worker.py                    # ARQ background worker (crons + reclaim job)
│   │
│   ├── api/
│   │   ├── api.py                   # Main router (combines all v1 routes)
│   │   ├── deps.py                  # Dependencies (auth, db session, redis)
│   │   └── v1/
│   │       ├── admin.py             # Admin dashboard endpoints
│   │       ├── admin_models.py      # Admin model-registry overrides
│   │       ├── auth.py              # Authentication endpoints
│   │       ├── credits.py           # Credit management
│   │       ├── demo.py              # Demo/preset endpoints
│   │       ├── downloads.py         # Download endpoints
│   │       ├── effects.py           # Style transfer & enhancement
│   │       ├── einvoices.py         # Taiwan e-invoice (B2C/B2B issue, void, preferences)
│   │       ├── example.py           # Example gallery endpoints
│   │       ├── generation.py        # Content generation (T2I, I2V, patterns)
│   │       ├── hero.py              # Landing hero demo pairs
│   │       ├── interior.py          # Interior design suite (see §5.6)
│   │       ├── landing.py           # Landing page data
│   │       ├── payments.py          # Payments (PayPal + ECPay checkout/webhooks)
│   │       ├── plans.py             # Subscription plans
│   │       ├── promotions.py        # Promotional codes
│   │       ├── prompts.py           # Prompt templates API
│   │       ├── quota.py             # Usage quota management
│   │       ├── referrals.py         # Referral system
│   │       ├── session.py           # Session heartbeat & online tracking
│   │       ├── share_proxy.py       # Social share proxy
│   │       ├── social_media.py      # Social media OAuth & publishing
│   │       ├── subscriptions.py     # Subscription management
│   │       ├── tools.py             # Tool endpoints (remove-bg … sora2-pro)
│   │       ├── uploads.py           # Subscriber material uploads
│   │       ├── user_works.py        # User generation history
│   │       └── workflow.py          # Workflow management
│   │
│   ├── config/
│   │   ├── demo_topics.py           # Demo topic configuration (legacy)
│   │   ├── example_presets.py       # Example preset definitions
│   │   ├── topic_registry.py        # Topic registry (single source of truth)
│   │   └── try_prompts.py           # Try prompt configuration
│   │
│   ├── core/
│   │   ├── config.py                # Settings & environment variables
│   │   ├── database.py              # Database connection (async)
│   │   ├── model_registry.py        # PIAPI_MODELS registry (env/DB/Redis overridable)
│   │   ├── public_plans.py          # Public plan catalog
│   │   ├── security.py              # JWT & password hashing
│   │   └── upload_validation.py     # Upload size/dimension validation
│   │
│   ├── models/
│   │   ├── billing.py               # Plan, Subscription, Order, Invoice, CreditTransaction, ServicePricing, etc.
│   │   ├── demo.py                  # DemoCategory, DemoVideo, ToolShowcase, etc.
│   │   ├── hero_demo_pair.py        # HeroDemoPair (landing hero before/after)
│   │   ├── material.py              # Material, MaterialView, MaterialTopic, ToolType
│   │   ├── model_registry.py        # ModelRegistryOverride, ModelRegistryAudit, GenerationMetric
│   │   ├── payment_settings.py      # PaymentSettings (admin-tunable payment routing)
│   │   ├── pending_provider_task.py # PendingProviderTask (long-task recovery, see §5.5)
│   │   ├── prompt_template.py       # PromptTemplate, PromptTemplateUsage
│   │   ├── site_settings.py         # SiteSettings (admin branding/copy)
│   │   ├── social_account.py        # SocialAccount (OAuth connections)
│   │   ├── social_post.py           # SocialPost (published post tracking)
│   │   ├── style_template.py        # StyleTemplate
│   │   ├── user.py                  # User model (credits, invoice prefs, retention)
│   │   ├── user_generation.py       # UserGeneration (subscriber results)
│   │   ├── user_upload.py           # UserUpload (subscriber uploads)
│   │   └── verification.py          # EmailVerification
│   │
│   ├── providers/                   # All REST — MCP providers deleted 2026-05-26
│   │   ├── base.py                  # Base provider interface
│   │   ├── piapi_provider.py        # PiAPI REST (primary for nearly all tasks)
│   │   ├── pollo_provider.py        # Pollo REST (narrow I2V backup)
│   │   ├── vertex_ai_provider.py    # Vertex AI Gemini + Veo (image/video backup, moderation)
│   │   ├── a2e_provider.py          # A2E (avatar backup)
│   │   └── provider_router.py       # TaskType routing table + circuit breaker
│   │
│   ├── schemas/
│   │   ├── credit.py                # Credit-related schemas
│   │   ├── demo.py                  # Demo schemas
│   │   ├── einvoice.py              # Taiwan e-invoice schemas
│   │   ├── moderation.py            # Moderation schemas
│   │   ├── payment.py               # Payment schemas
│   │   ├── plan.py                  # Plan schemas
│   │   ├── promotion.py             # Promotion schemas
│   │   └── user.py                  # User schemas
│   │
│   ├── services/
│   │   ├── a2e_service.py           # A2E avatar pipeline helpers
│   │   ├── abuse_prevention_service.py # reCAPTCHA + IP/login rate limits
│   │   ├── access_gate.py           # Custom-prompt gate (subscription + bound card)
│   │   ├── admin_dashboard.py       # Admin dashboard service (stats, API costs, active users)
│   │   ├── credit_service.py        # Credit management (balance, deduct, refund)
│   │   ├── demo.py / demo_service.py / demo_cache_service.py  # Demo data + cache
│   │   ├── ecpay/                   # ECPay payment + e-invoice clients
│   │   ├── effects_service.py       # Style transfer service
│   │   ├── email_service.py / email_verify.py
│   │   ├── example_cache_service.py # Example gallery cache
│   │   ├── gcs_storage_service.py   # CDN → GCS persistence (safe_persist_url)
│   │   ├── gemini_service.py        # Gemini LLM (Vertex AI ADC first, API-key fallback)
│   │   ├── giveme/                  # Giveme e-invoice client (primary when enabled)
│   │   ├── image_normalize_service.py / image_translator_service.py
│   │   ├── image_understanding_service.py # Vision passes (fusion disabled; additive structure pass)
│   │   ├── interior_design_service.py # Interior design (Gemini via Vertex ADC)
│   │   ├── interior_growth_service.py # Floor-plan → growth-video pipeline
│   │   ├── invoice_service.py       # E-invoice business logic (Giveme/ECPay/PayPal)
│   │   ├── material_generator.py / material_lookup.py / material/  # Material pipeline
│   │   ├── media_cleanup_service.py # 14-day media cleanup
│   │   ├── model_registry_service.py / model_registry_pubsub.py # Live model overrides
│   │   ├── moderation.py            # Content moderation (Gemini)
│   │   ├── payment_routing.py / payment_settings_service.py # Region → provider routing
│   │   ├── paypal_service.py        # PayPal Orders/Subscriptions/Invoicing v2
│   │   ├── plan_gates.py            # Plan-tier model floors (require_model_access)
│   │   ├── pollo_ai.py              # Pollo REST client helpers
│   │   ├── prompt_generator.py / prompt_library.py / prompt_matching.py
│   │   ├── referral_service.py      # Referral system
│   │   ├── rescue_service.py        # Error recovery service
│   │   ├── session_tracker.py       # Session/online tracking
│   │   ├── social_media_service.py  # Social OAuth & publishing (FB, IG, TikTok, YouTube)
│   │   ├── subscription_service.py  # Subscription management
│   │   ├── template_prompt_service.py
│   │   ├── tier_config.py           # Credit cost tables (VIDEO/IMAGE_CREDIT_COSTS, tiers)
│   │   ├── token_refresh_service.py # Auto-refresh expiring OAuth tokens
│   │   ├── watermark.py             # Watermark application
│   │   ├── workflow_generator.py    # Workflow generation
│   │   ├── base/                    # Base generation/material services
│   │   └── generation/              # Generation factory + Pollo service
│   │
├── alembic/                         # Database migrations
├── scripts/                         # CLI scripts (pregenerate, seed, backfill, entrypoint)
├── tests/                           # Test suite
├── Dockerfile
├── requirements.txt
└── pytest.ini
```

---

## 3. API Router Configuration

```python
# app/api/api.py — all v1 routes
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(subscriptions.router, tags=["subscriptions"])
api_router.include_router(demo.router, prefix="/demo", tags=["demo"])
api_router.include_router(plans.router, tags=["plans"])
api_router.include_router(promotions.router, prefix="/promotions", tags=["promotions"])
api_router.include_router(credits.router, tags=["credits"])
api_router.include_router(effects.router, tags=["effects"])
api_router.include_router(generation.router, prefix="/generate", tags=["generation"])
api_router.include_router(landing.router, prefix="/landing", tags=["landing"])
api_router.include_router(quota.router, prefix="/quota", tags=["quota"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_models.router, prefix="/admin", tags=["admin-models"])
api_router.include_router(session.router, prefix="/session", tags=["session"])
api_router.include_router(interior.router, tags=["interior"])
api_router.include_router(workflow.router, tags=["workflow"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
api_router.include_router(user_works.router, prefix="/user", tags=["user"])
api_router.include_router(downloads.router, prefix="/downloads", tags=["downloads"])
api_router.include_router(uploads.router, tags=["uploads"])
api_router.include_router(referrals.router, tags=["referrals"])
api_router.include_router(social_media.router, tags=["social"])
api_router.include_router(einvoices.router, prefix="/einvoices", tags=["einvoices"])
api_router.include_router(example.router, prefix="/examples", tags=["examples"])
api_router.include_router(share_proxy.router, prefix="/share", tags=["share"])
api_router.include_router(hero.router, tags=["hero"])
```

### Endpoint Summary

| Prefix | Tag | Description |
|--------|-----|-------------|
| `/auth` | auth | Authentication (login, register, verify, password reset, account deletion) |
| `/payments` | payments | PayPal + ECPay checkout, webhooks/callbacks, order status |
| `/subscriptions` | subscriptions | Subscription CRUD, payment-route, invoices, refund eligibility |
| `/demo` | demo | Demo presets, showcases, inspiration, search |
| `/plans` | plans | Plan listing and details |
| `/promotions` | promotions | Promo codes, credit packages (user + admin) |
| `/credits` | credits | Credit balance, transactions, pricing |
| `/effects` | effects | Style transfer, HD enhance, video enhance |
| `/generate` | generation | T2I, I2V, pattern, product, video generation |
| `/landing` | landing | Landing page data (stats, features, examples, FAQ) |
| `/quota` | quota | Daily/user/promo quota management |
| `/tools` | tools | Core AI tools (remove-bg, product-scene, try-on, short-video, kling-video, sora2-pro, avatar, claymation, upscale, image-transform, midjourney-imagine, …) |
| `/admin` | admin | Admin dashboard, user/material management, moderation, API costs, model-registry overrides |
| `/einvoices` | einvoices | Taiwan e-invoice (B2C/B2B issue, void, list, **user preferences**) |
| `/session` | session | Session heartbeat, online count |
| `/interior` | interior | Interior design suite (redesign, generate, fusion, edit, style-transfer, floorplan, isometric, floorplan-to-video, 3D) |
| `/workflow` | workflow | Workflow topics, categories, generation |
| `/prompts` | prompts | Prompt templates, groups, demo/subscriber generation |
| `/user` | user | User generation history, stats, downloads |
| `/downloads` | downloads | Download endpoints |
| `/uploads` | uploads | Subscriber material upload + real-API generation |
| `/referrals` | referrals | Referral code, stats, apply, leaderboard |
| `/social` | social | Social media OAuth + publishing (FB, IG, TikTok, YouTube), post history, analytics |
| `/examples` | examples | Example gallery |
| `/share` | share | Social share proxy |
| `/hero` | hero | Landing hero demo pairs |

---

## 4. Database Models

### 4.1 Core Models

```python
# User Management
User                    # User account (email, password, plan, referral fields,
                        # invoice preferences: default_invoice_mode (carrier|donation|b2b),
                        # default_buyer_tax_id, default_buyer_company_name,
                        # default_carrier_type/number, default_love_code)

# Billing & Subscriptions
Plan                    # Subscription plan definitions (incl. feature flags)
Subscription            # Active subscriptions
Order                   # Payment orders
Invoice                 # Invoice records (Taiwan e-invoice fields: carrier, donation, provider tracking)
InvoiceItem             # Invoice line items (required by e-invoice APIs)
Promotion               # Promotional campaigns
CreditPackage           # Purchasable credit packs
PromotionUsage          # Promo code usage tracking
CreditTransaction       # Credit ledger entries
ServicePricing          # Per-service pricing (DB override of code fallback costs)
Generation              # Generation records (billing context)

# Demo & Showcase
DemoCategory, ImageDemo, DemoVideo, DemoView, PromptCache, DemoExample, ToolShowcase
HeroDemoPair            # Landing hero before/after pairs

# Materials (Preset-Only Mode)
Material                # Pre-generated examples (core model)
MaterialView            # Material view tracking
MaterialTopic           # Material topic definitions
ToolType (enum)         # 13 tools (see 4.2)
MaterialSource (enum)   # seed / user / admin
MaterialStatus (enum)   # pending / approved / rejected / featured

# Prompt Templates
PromptTemplate, PromptTemplateUsage, PromptGroup (enum), PromptSubTopic (enum)

# Social
SocialAccount           # OAuth-connected social accounts (FB, IG, TikTok, YouTube)
SocialPost              # Published post tracking (platform, status, analytics)

# User Content
UserGeneration          # Subscriber generation results (14-day retention)
UserUpload              # Subscriber uploaded materials

# Operations
PendingProviderTask     # Long-running provider task recovery (see §5.5)
ModelRegistryOverride   # Admin model-id overrides (+ ModelRegistryAudit, GenerationMetric)
PaymentSettings         # Admin-tunable payment routing
SiteSettings            # Admin branding/copy
StyleTemplate           # Style template entries

# Verification
EmailVerification       # Email verification codes
```

### 4.2 ToolType Enum

```python
class ToolType(str, enum.Enum):
    BACKGROUND_REMOVAL = "background_removal"
    PRODUCT_SCENE = "product_scene"
    TRY_ON = "try_on"
    ROOM_REDESIGN = "room_redesign"
    SHORT_VIDEO = "short_video"
    AI_AVATAR = "ai_avatar"
    PATTERN_GENERATE = "pattern_generate"
    EFFECT = "effect"
    # 2026-05-26 demo-coverage additions
    CLAYMATION = "claymation"
    KLING_VIDEO = "kling_video"
    UPSCALE = "upscale"
    IMAGE_TRANSLATOR = "image_translator"
    MIDJOURNEY_IMAGINE = "midjourney_imagine"
```

### 4.3 Material Model

```python
class Material(Base):
    __tablename__ = "materials"

    id = Column(UUID, primary_key=True)
    lookup_hash = Column(String(64), unique=True, index=True)  # O(1) lookup
    tool_type = Column(Enum(ToolType), nullable=False, index=True)
    topic = Column(String(100), nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    prompt_zh = Column(Text, nullable=True)
    input_image_url = Column(String(500))       # Before image
    result_image_url = Column(String(500))       # Full-quality result
    result_video_url = Column(String(500))       # Video result
    result_watermarked_url = Column(String(500)) # Watermarked for demo
    input_params = Column(JSON)                  # Tool-specific params
    # ...
```

---

## 5. AI Provider Integration

### 5.1 Provider Summary

> **MCP removed (2026-05-26, owner directive):** Both the PiAPI MCP and Pollo MCP providers were deleted. PiAPI MCP had been disabled in prod (`PIAPI_MCP_ENABLED=false`) for weeks while REST was already serving every task; Pollo MCP's tool catalog had drifted (404s on every `seedance` call). All providers are now plain REST. Re-enabling would require restoring `app/providers/piapi_mcp_provider.py`, `app/services/mcp_client.py`, and the MCP server build step from git history.

| Provider | Interface | Purpose | Env Variable |
|----------|-----------|---------|--------------|
| PiAPI | REST | **Primary** for nearly all tasks: T2I, I2I, I2V, T2V, avatar, interior, BG removal, effects, upscale, Kling/Sora2 premium video, Trellis 3D, ControlNet | `PIAPI_KEY` |
| Pollo.ai | REST | Narrow **backup** for I2V only (Kling v1.5/v2, Pixverse, Hailuo/Minimax, Wan, pollo-v1-6); promoted to primary when one of those `model_id`s is explicitly requested | `POLLO_API_KEY` |
| Vertex AI | GCP SDK / REST + ADC | **Backup** for image and video tasks (Gemini / Veo), **primary** for moderation + material generation. Auth via Application Default Credentials — no API key | `VERTEX_AI_PROJECT` |
| A2E | REST | **Backup** for avatar generation | `A2E_API_KEY` |

> **Gemini auth note:** the original `GEMINI_API_KEY` was reported leaked by Google and revoked. Gemini calls now authenticate via **Vertex AI ADC** (service account on Cloud Run, `gcloud` locally) against `VERTEX_AI_PROJECT`; the image model is `gemini-2.5-flash-image` (us-central1). The API-key path survives only as a local-dev fallback and is never preferred when a project is configured.

**Failover Strategy** (`ROUTING_CONFIG`, primary → backup → tertiary):
- **I2V**: PiAPI → Vertex AI (Veo) → Pollo (last-chance tertiary, added 2026-05-26)
- **T2V**: PiAPI → Vertex AI (Pollo REST has no T2V endpoint)
- **Explicit Pollo video model choices** (`POLLO_VIDEO_MODEL_IDS`): Pollo promoted to primary
- **Image tasks** (T2I, I2I, Effects, Upscale, BG Removal, Interior): PiAPI → Vertex AI Gemini
- **Interior 3D** (Trellis): PiAPI only
- **Avatar**: PiAPI → A2E
- **Moderation & Material generation**: Vertex AI Gemini only
- **Premium tiers** (deliberately no cheap substitute): `MIDJOURNEY_T2I` → PiAPI only; `KLING_VIDEO` → PiAPI → Pollo (I2V mode only); `SORA2_VIDEO` → PiAPI → Pollo (I2V mode only)
- V2V (video style transfer) task type removed 2026-05-31; Luma video removed 2026-05-19
- Provider names are never exposed to end users

**Provider Health & Recovery:**
- Health checks are cached by `PROVIDER_HEALTH_CACHE_SECONDS` (default 60s).
- Repeated runtime failures open an in-memory provider circuit after `PROVIDER_CIRCUIT_BREAKER_FAILURES` (default 3) failures.
- Open circuits are skipped for `PROVIDER_CIRCUIT_BREAKER_COOLDOWN_SECONDS` (default 180s) when another fallback is available.
- If all circuits in a route are open, the primary provider is probed so recovery can be detected.
- Successful health checks reset failure counts and close the provider circuit.

### 5.2 Provider Router

```python
class TaskType(str, Enum):
    T2I = "text_to_image"
    I2V = "image_to_video"
    T2V = "text_to_video"
    INTERIOR = "interior_design"
    AVATAR = "avatar"
    UPSCALE = "upscale"
    EFFECTS = "effects"
    MODERATION = "moderation"
    BACKGROUND_REMOVAL = "background_removal"
    INTERIOR_3D = "interior_3d"
    I2I = "image_to_image"
    MATERIAL_GENERATION = "material_generation"
    # Premium / flagship tiers — PiAPI-first, model identity baked into the task type
    MIDJOURNEY_T2I = "midjourney_imagine"
    KLING_VIDEO    = "kling_video_generation"
    SORA2_VIDEO    = "sora2_video_generation"   # added 2026-06-09
```

```python
# ROUTING_CONFIG (provider_router.py) — per-task primary/backup/tertiary:
TaskType.I2V:  {"primary": "piapi", "backup": "vertex_ai", "tertiary": "pollo"}
TaskType.T2V:  {"primary": "piapi", "backup": "vertex_ai"}
TaskType.T2I / I2I / EFFECTS / UPSCALE / BACKGROUND_REMOVAL / INTERIOR:
               {"primary": "piapi", "backup": "vertex_ai"}
TaskType.INTERIOR_3D:    {"primary": "piapi"}
TaskType.AVATAR:         {"primary": "piapi", "backup": "a2e"}
TaskType.MODERATION / MATERIAL_GENERATION: {"primary": "vertex_ai"}
TaskType.MIDJOURNEY_T2I: {"primary": "piapi"}
TaskType.KLING_VIDEO:    {"primary": "piapi", "backup": "pollo"}
TaskType.SORA2_VIDEO:    {"primary": "piapi", "backup": "pollo"}
```

### 5.3 PiAPI Service

**Base URL:** `https://api.piapi.ai/api/v1`
**Auth:** X-API-Key header

Task types in use: `txt2img`, `img2img`, `kontext` (Flux Kontext I2I), `imagine`, `lip_sync`, `image-to-3d` (Trellis v1/v2), ControlNet depth render, Wan/Kling/Hailuo/Seedance/Hunyuan video tasks, Sora 2 Pro proxy, nano-banana (Gemini image) tasks. Model IDs live in `app/core/model_registry.py` (`PIAPI_MODELS`) and can be overridden live by admins via DB + Redis pub/sub without a redeploy.

```
Step 1: POST /task                       → Create task
Step 2: GET /task/{task_id}              → Poll for result
```

Provider CDN URLs are persisted to GCS (`gcs_storage_service.safe_persist_url`) so results survive the upstream's 14-day expiry.

### 5.4 Prompt Fidelity (Verbatim) Policy

Owner directive 2026-05-23/24 — **user prompts reach the model verbatim**, matching PiAPI's own behavior:

- `tools._refine_generation_prompt` is a **no-op pass-through**. The old Gemini rewriter ("a red apple" → "a single ripe red apple, 50mm lens, …") was deleted; the helper signature survives so its call sites are untouched.
- `image_understanding_service.describe_and_fuse` is **disabled** — it returns the user prompt unchanged instead of letting Gemini Vision drop/rewrite "misaligned" text.
- The replacement is `extract_structure_constraints` (2026-06-03): a read-only vision pass that returns an *additive* structure-preservation clause to append; the user's wording is never touched.

Anti-hallucination is therefore **additive and user-chosen** (`app/api/v1/tools.py`):
- `VIDEO_CAMERA_MOVES` — deterministic camera-move clauses (`static`, `dolly_in`, `dolly_out`, `orbit`, `pan`, `tilt_up`, `crane_up`, `handheld`) appended as `Camera: …`
- `VIDEO_SUBJECT_LOCK_CLAUSE` — I2V subject-preservation clause (default ON, user can disable)
- `VIDEO_PROMPT_ADHERENCE_CLAUSE` — T2V strict-adherence clause
- `VIDEO_BASELINE_NEGATIVE` — baseline negative prompt shared by every video endpoint (user negatives are appended, never replaced)
- `interior_design_service.build_atmosphere_clause` — composes the interior atmosphere knobs (lighting tone / color temperature / material accent) into an additive clause

### 5.5 Video Generation Endpoints & Billing

**Endpoints:**
- `POST /tools/short-video` — I2V from an uploaded image. `model_id` aliases: `seedance` (default tier), `kling_omni` / `kling_v3` (premium, audio), `hailuo` / `minimax` (cheapest), `hunyuan` (中文 prompts), `wan`, plus raw `pixverse_v4.5` / `pixverse_v5` / `kling_v1.5` / `kling_v2` strings. Optional free-form motion `prompt` (verbatim), `camera_move`, `subject_lock`, `negative_prompt`, TTS `script`/`voice_id`.
- `POST /tools/kling-video` — premium Kling tiers: `default` (Kling 2.5/2.6 STD), `flagship` (Kling V3.0 STD), `omni` (Kling 3.0 / Omni PRO, multimodal + audio + lip-sync).
- `POST /tools/sora2-pro` — added 2026-06-09. OpenAI Sora 2 Pro via PiAPI (Pollo I2V backup). 4–12 s (default 5 s), 720p/1080p, synchronized audio by default. 80 credits (`video_sora2` row).
- `POST /tools/avatar` — Kling Avatar with A2E fallback (300 credits, `ai_avatar`).

**Credit table** (`tier_config.VIDEO_CREDIT_COSTS` — iron rule `credits = ceil(usd / 0.04 × 2.5)`; resolved per model + resolution + tier via `resolve_video_credits`, with `ServicePricing` DB overrides):

| Model key | service_type | Credits | Label |
|-----------|--------------|---------|-------|
| `hailuo` | video_hailuo | 18 | Hailuo Fast 10s 768p |
| `wan` | video_wan | 20 | Wan 480p |
| `hunyuan` | video_hunyuan | 20 | Hunyuan |
| `kling_std` | video_kling_std | 28 | Kling V2.5 STD 10s |
| `seedance_720p` | video_seedance_720p | 65 | Seedance 720p 5s |
| `seedance_1080p` | video_seedance_1080p | 160 | Seedance 1080p 5s |
| `kling_v3_std` | video_kling_v3_std | 65 | Kling V3.0 STD 10s |
| `kling_v3_pro` | video_kling_v3_pro | 130 | Kling V3.0 PRO 10s 含音 |
| `veo` | video_veo | 80 | Veo 3.1 5s 含音 |
| `sora2` | video_sora2 | 80 | Sora2 Pro 5s |

Image billing is per model too (`IMAGE_CREDIT_COSTS`): standard 2, premium (Flux dev / Qwen edit / Kontext) 3, nano-banana (Gemini 1K) 8, nano-banana 4K 12, upscale 3, BG removal 2. Other fixed fallbacks: product-scene 10, room-redesign 20, try-on 30, claymation 10 image / 50 video, video-background-remove 50, avatar 300. The endpoint reports `credits_used` as the amount actually charged (ServicePricing-override aware; 0 for admins), and over-charges are partially refunded.

**Streaming heartbeat:** long-running endpoints (`short-video`, `kling-video`, `sora2-pro`, `room-redesign`, `floorplan-to-video`, …) are wrapped in `_stream_with_heartbeat`, a chunked `StreamingResponse` that emits one space every 25 s so Cloudflare/GCLB/corp proxies don't cut idle connections during 5–15 min renders. Errors inside the stream are returned as graceful `{"success": false, …}` JSON bodies (headers are already flushed as 200).

**Long-task recovery (`PendingProviderTask`):** before polling, the endpoint inserts a `pending_provider_tasks` row (user, tool/service type, credits charged, input params, provider task id once submitted). If Cloud Run kills the request mid-poll, the ARQ worker's `reclaim_pending_provider_tasks_task` (every 2 minutes) re-polls the upstream provider, materialises the result into `UserGeneration`, or refunds the credits when the task is orphaned/over-age.

### 5.6 Interior Design Suite (`/interior`, `app/api/v1/interior.py`)

Gemini calls use **Vertex AI ADC** (`VERTEX_AI_PROJECT`, model `gemini-2.5-flash-image`); image generation routes through PiAPI with Vertex fallback.

- **Classic modes** (subscribers; free users browse watermarked presets): `POST /redesign`, `/generate`, `/fusion`, `/edit` (+ `DELETE /edit/{conversation_id}`), `/style-transfer`; catalogs via `GET /styles`, `GET /room-types`; no-auth demos at `POST /demo/redesign`, `/demo/generate`.
- **`POST /floorplan` (平面配置圖, 15 credits)** — clean 2D floor-plan layout from typed requirements/dimensions OR an uploaded hand sketch. Uses a read-then-draw vision inventory pass so the drawn plan matches the stated rooms.
- **`POST /isometric` (立體圖, 25 credits)** — 45° isometric "dollhouse" render from an uploaded plan/room image, with additive atmosphere knobs `lighting_tone` / `color_temperature` / `material_accent` (`build_atmosphere_clause`).
- **`POST /floorplan-to-video` (3D 效果圖 / growth pipeline)** — streamed with heartbeat; tiers from `GET /floorplan-options`:
  - `render` (40 credits, `interior_render`) — photorealistic 3D render only
  - `video` (600 credits, `interior_growth_video`) — Gemini analysis → render → Kling 3.0/Omni first→last-frame "plan grows into room" MP4
  - `video_3d` (750 credits, `interior_growth_video_3d`) — adds a Trellis2 interactive `.glb`; the 150-credit 3D delta is refunded if the model can't be built
  - `preserve_original=true` (保留結構) — primary path is a **Flux ControlNet (depth) render** that hard-locks output geometry to the uploaded design (`structural_fidelity` → `control_strength` 0.4–0.85, `style_strength` drives restyling), with the Gemini structure-preserve render as fallback.
- **3D models**: `POST /3d-model` (PiAPI Trellis v1/v2 from an image), `POST /3d-from-floorplan` (Gemini render → Trellis2 GLB).
- **`POST /tools/room-redesign` (20 credits)** — supports `space_kind` = `interior` (default) / `exterior` / `commercial`, selecting from the separate `INTERIOR_STYLES` / `EXTERIOR_STYLES` / `COMMERCIAL_STYLES` catalogs in tools.py (also exposed via `GET /tools/templates/interior-styles?space_kind=…`, `/templates/exterior-styles`, `/templates/commercial-styles`).

### 5.7 Virtual Try-On (`POST /tools/try-on`, 30 credits)

Two modes (`CREDIT_COST = 30`, `virtual_try_on`):
- **`garment`** (default) — PiAPI Kling Try-On places an uploaded garment image on a model photo or a `TRYON_MODELS` preset model.
- **`prompt`** (added 2026-05-24) — Kling Try-On has no prompt field, so this mode routes the model photo + the user's verbatim outfit prompt through **Flux Kontext I2I**, preserving the person's identity and re-painting only the outfit. Descriptive prompts without an edit verb are wrapped in a minimal "keep the person … change the outfit to:" instruction.

`TRYON_MODELS` is the preset model-photo catalog (model_id → GCS URL).

---

## 6. Payment System

### 6.1 Supported Payment Providers

| Provider | Region | Status |
|----------|--------|--------|
| PayPal | International | Active (Orders + Subscriptions; checkout via `POST /payments/paypal/checkout`, webhook `POST /payments/paypal/webhook`) |
| ECPay | Taiwan | Active (checkout via `POST /payments/ecpay/checkout`, callback `POST /payments/ecpay/callback`) |

Region → provider routing is admin-tunable via `PaymentSettings` / `payment_routing.py`; `GET /payments/methods` and `GET /subscriptions/payment-route` expose the resolved route. (Paddle was removed.)

### 6.2 Configuration

```python
# PayPal (International)
PAYPAL_CLIENT_ID: str = ""
PAYPAL_CLIENT_SECRET: str = ""
PAYPAL_WEBHOOK_ID: str = ""
PAYPAL_ENV: str = "sandbox"          # "sandbox" or "production"
PAYPAL_PLAN_IDS: str = ""            # plan_name+cycle → PayPal Plan ID (JSON)

# ECPay (Taiwan)
ECPAY_ENV: str = "production"
ECPAY_MERCHANT_ID: str = ""
ECPAY_HASH_KEY: str = ""
ECPAY_HASH_IV: str = ""
ECPAY_PAYMENT_URL: str = "https://payment.ecpay.com.tw/Cashier/AioCheckOut/V2"
```

### 6.3 Subscription Flow

- Subscribe: `POST /subscriptions/subscribe` → returns `checkout_url` (PayPal or ECPay per route)
- PayPal webhook: `POST /payments/paypal/webhook` → activates subscription
- ECPay callback: `POST /payments/ecpay/callback` → activates subscription
- Cancel: `POST /subscriptions/cancel` (refund eligibility via `GET /subscriptions/refund-eligibility`)
- Invoices: `GET /subscriptions/invoices` → list, `GET /subscriptions/invoices/{order_id}/pdf` → PDF

### 6.4 E-Invoice (Taiwan 電子發票 + PayPal)

`app/services/invoice_service.py` routes invoice issuance by provider:
- **Giveme** (`app/services/giveme/`) is the **primary** e-invoice provider when `GIVEME_ENABLED=true` (+ `GIVEME_UNCODE` / `GIVEME_IDNO` / `GIVEME_PASSWORD`)
- **ECPay e-invoice** (`app/services/ecpay/einvoice_client.py`) is the fallback when Giveme is disabled
- **PayPal Invoicing v2** is used for PayPal-paid orders (detected via payment method / `paypal_subscription_id`), issuing in the order's currency

**User invoice preferences (added 2026-06-12):**
- `users.default_invoice_mode` — `carrier` | `donation` | `b2b` — plus `default_buyer_tax_id` (統一編號) and `default_buyer_company_name` (公司抬頭) for B2B
- `GET /einvoices/preferences` / `PUT /einvoices/preferences` read/update them
- `auto_issue_invoice` (called after payment) honors the B2B 統編 preference first, then saved carrier, then love-code donation, finally falling back to an email carrier so an invoice is always issued
- Migration: `alembic/versions/e2f3g4h5i6j7_add_invoice_mode_prefs.py`

Other endpoints: `POST /einvoices/b2c`, `POST /einvoices/b2b`, `POST /einvoices/void`, `GET /einvoices`, `GET /einvoices/{invoice_id}`.

---

## 7. Configuration

### 7.1 Environment Variables

```python
class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "VidGo Gen AI"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://..."
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "..."
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AI Providers
    PIAPI_KEY: str = ""
    POLLO_API_KEY: str = ""
    VERTEX_AI_PROJECT: str = ""          # GCP project ID — Gemini/Imagen/Veo via ADC
    VERTEX_AI_LOCATION: str = "us-central1"
    VEO_MODEL: str = "veo-3.0-generate-preview"
    GEMINI_MODEL: str = "gemini-2.5-pro"
    GEMINI_IMAGE_MODEL: str = "gemini-2.5-flash-image"
    GEMINI_API_KEY: str = ""             # Local-dev fallback ONLY — prod key was
                                         # leaked & revoked; ADC is preferred
    A2E_API_KEY: str = ""                # Avatar backup

    # Provider health / circuit breaker
    PROVIDER_HEALTH_CACHE_SECONDS: int = 60
    PROVIDER_CIRCUIT_BREAKER_FAILURES: int = 3
    PROVIDER_CIRCUIT_BREAKER_COOLDOWN_SECONDS: int = 180

    # Storage
    GCS_BUCKET: str = ""                 # Persist generated media beyond CDN expiry

    # Social media (FB/IG/TikTok/YouTube OAuth)
    FACEBOOK_APP_ID / FACEBOOK_APP_SECRET / TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""

    # Payments
    ECPAY_MERCHANT_ID / ECPAY_HASH_KEY / ECPAY_HASH_IV / ECPAY_ENV
    PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET / PAYPAL_WEBHOOK_ID / PAYPAL_ENV / PAYPAL_PLAN_IDS

    # E-invoice
    GIVEME_ENABLED: bool = False
    GIVEME_UNCODE / GIVEME_IDNO / GIVEME_PASSWORD

    # Bonuses & abuse prevention
    REGISTRATION_BONUS_CREDITS: int = 40
    REFERRAL_BONUS_CREDITS: int = 50
    REFERRAL_WELCOME_CREDITS: int = 40
    RECAPTCHA_SECRET_KEY / ABUSE_* rate limits

    # Model credit multipliers (legacy upload path)
    MODEL_CREDIT_MULTIPLIERS: str = '{"default":1,"wan_pro":2,"gemini_pro":2}'
```

---

## 8. Pre-generation Pipeline

### 8.1 Startup Sequence

**Container entrypoint** (`scripts/docker_entrypoint.sh`, blocking gates):
```
1. Run database migrations (alembic upgrade head)
2. Seed pricing tiers (idempotent)
3. Ensure example INPUT images exist in GCS (idempotent)
4. Backfill broken Material DB URLs to GCS (idempotent)
5. VERIFY gate: refuse to start if APPROVED materials still hold broken URLs
   (escape hatches: STRICT_MATERIAL_CHECK=false, SKIP_STARTUP_GATE=true)
6. exec uvicorn
```

**App lifespan** (`app/main.py`, non-blocking so the Cloud Run health check passes fast):
```
1. Start serving immediately; validate materials in a background task (30 s timeout)
2. Run initial media cleanup (14-day retention), then hourly cleanup loop
3. Start model-registry Redis pub/sub subscriber (live PIAPI_MODELS overrides)
```

Heavy first-boot seeding (`main_pregenerate.py`, 30–90 min of real provider calls) runs as a separate job, never in the entrypoint.

**ARQ worker crons** (`app/worker.py`): hourly expired-demo cleanup, 5-min health check, monthly credit reset (1st 00:05 UTC), daily bonus-credit cleanup (02:00 UTC), daily auto-renewal (01:00 UTC), and the 2-minute `reclaim_pending_provider_tasks_task` recovery job.

### 8.2 Material Topics

| Tool | Topics |
|------|--------|
| background_removal | drinks, snacks, desserts, meals, packaging, equipment, signage, ingredients |
| product_scene | studio, nature, elegant, minimal, lifestyle, urban, seasonal, holiday, spring, valentines, black_friday, christmas, new_year |
| try_on | casual, formal, sportswear, outerwear, accessories, dresses |
| room_redesign | living_room, bedroom, kitchen, bathroom, dining_room, home_office, balcony |
| short_video | product_showcase, brand_intro, tutorial, promo |
| ai_avatar | spokesperson, product_intro, customer_service, social_media |
| pattern_generate | seamless, floral, geometric, abstract, traditional, 3d, interior, mockup |
| effect | anime, ghibli, cartoon, oil_painting, watercolor |
| claymation | product, character, scene |
| kling_video | cinematic, product_motion, atmosphere |
| upscale | product, portrait, scenery |
| image_translator | menu, signage, poster |
| midjourney_imagine | logo, marketing, illustration |

### 8.3 CLI Commands

```bash
# Check material status
python -m scripts.main_pregenerate --dry-run

# Generate specific tool materials
python -m scripts.main_pregenerate --tool ai_avatar --limit 10

# Generate all tools
python -m scripts.main_pregenerate --all
```

---

## 9. Docker Services

```yaml
services:
  postgres:       # PostgreSQL 15 - Primary database (host port 5433 → 5432)
  redis:          # Redis 7 - Cache & task queue (host port 6380 → 6379)
  mailpit:        # Email testing - dev only (port 8025)
  backend:        # FastAPI application (host port 8001 → 8000)
  worker:         # ARQ background worker
  init-materials: # Initial pre-generation (profile: init, runs once)
  pregenerate:    # Manual pre-generation (profile: tools)
  frontend:       # Vue 3 frontend (host port 8501 → 5173)

volumes:
  postgres_data:         # Persist PostgreSQL data
  redis_data:            # Persist Redis data
  vidgo_generated:       # Persist generated images/videos (Docker volume)
  vidgo_materials:       # Persist pre-generated materials (Docker volume)
  vidgo_tryon_garments:  # Persist cached Virtual Try-On garment images
```

**Storage:** Locally, pre-generated materials and user-generated content live in **Docker named volumes** (`vidgo_materials`, `vidgo_generated`), NOT on the local filesystem. In production, generated media is persisted to the **GCS bucket** (`GCS_BUCKET`) so it survives provider CDN expiry and container restarts.

---

## 10. API Testing

```bash
# Health check
curl http://localhost:8001/health

# Material status
curl http://localhost:8001/materials/status

# API docs (Swagger)
open http://localhost:8001/docs

# Demo presets
curl http://localhost:8001/api/v1/demo/presets/short_video

# Frontend
open http://localhost:8501
```

---

*Document Version: 8.0*
*Last Updated: June 12, 2026*
*Mode: Dual-Mode — Preset-Only (free) + Real-API (subscribers)*
*Target: SMB (small businesses selling everyday products/services)*
