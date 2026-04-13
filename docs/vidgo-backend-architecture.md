# VidGo AI Platform - Backend Architecture

**Version:** 7.1
**Last Updated:** March 18, 2026
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
2. Credit deduction: Credits deducted based on `tool_type` base cost × model multiplier
3. Generation: Backend calls AI provider in real time
4. Result: `result_url` / `result_video_url` stored without watermark; `GET /api/v1/uploads/{id}/download`

### 0.3 Preset Download (Subscribers)
Subscribers can download full-quality (no watermark) versions of preset gallery results:
- `POST /api/v1/demo/use-preset` returns `result_url` (full quality) when authenticated as subscriber
- `GET /api/v1/demo/download/{material_id}` redirects to full-quality result URL

### 0.4 Model Selection
Paid users can select AI models for upload-based generation. Better models cost more credits:

| Model | Multiplier | Tools |
|-------|------------|-------|
| default | 1× | All tools |
| wan_pro | 2× | product_scene, room_redesign, pattern_generate, effect, short_video |
| gemini_pro | 2× | ai_avatar, try_on |

### 0.5 Referral System
Users earn bonus credits by inviting others:
- Referrer: **+50 credits** per successful registration via their code
- New user: **+20 credits** when registering with a referral code
- Endpoints: `GET /referrals/code`, `GET /referrals/stats`, `POST /referrals/apply`, `GET /referrals/leaderboard`

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

### 0.9 Credit Types & Weekly Reset
Credits are split into three types:
| Type | Reset | Expiry |
|------|-------|--------|
| `subscription_credits` | Weekly (Monday) via `credits_reset_at` | Resets each week |
| `purchased_credits` | Never | Never expire |
| `bonus_credits` | Never | Expire on `bonus_credits_expiry` |

### 0.10 Per-Plan Feature Restrictions
Plans can restrict tool access via feature flags:
- `feature_clothing_transform`, `feature_video_gen`
- `feature_batch_processing`, `feature_custom_styles`

### 0.11 Media Retention Policy
14-day media retention with automatic cleanup:
- Hourly background task scans `user_generations` table
- Entries older than 14 days have media URLs cleared
- Initial cleanup runs on startup

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
|  |  |  | Interior | | Uploads  | | Referral | |  Social  | |   Prompts   | |  | |
|  |  |  | Endpoints| | Endpoints| | Endpoints| | Endpoints| |  Endpoints  | |  | |
|  |  |  +----------+ +----------+ +----------+ +----------+ +-------------+ |  | |
|  |  +-----------------------------------------------------------------------+  | |
|  |                                                                             | |
|  |  +-----------------------------------------------------------------------+  | |
|  |  |                          Service Layer                                |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  |  | Material      | | Demo          | | Credit        | | Generation | |  | |
|  |  |  | Lookup        | | Service       | | Service       | | Service    | |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  |  | Interior      | | Subscription  | | Payment       | | Referral   | |  | |
|  |  |  | Service       | | Service       | | Service       | | Service    | |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  |  | Referral      | | Social Media  | | Media Cleanup | | Moderation | |  | |
|  |  |  | Service       | | Service       | | Service       | | Service    | |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  +-----------------------------------------------------------------------+  | |
|  |                                                                             | |
|  |  +-----------------------------------------------------------------------+  | |
|  |  |                       AI Provider Layer                               |  | |
|  |  |  +---------------+ +---------------+ +-------------------+          |  | |
|  |  |  | PiAPI MCP     | | Pollo.ai MCP  | | Vertex AI (GCP)   |          |  | |
|  |  |  | PRIMARY:      | | BACKUP:       | | - Gemini: image   |          |  | |
|  |  |  | T2I,I2I,I2V,  | | I2V, T2V, V2V | |   backup+moderat. |          |  | |
|  |  |  | T2V,V2V,Avatar| | (50+ models)  | | - Veo: 3rd video  |          |  | |
|  |  |  | Interior,3D,  | |               | |   backup          |          |  | |
|  |  |  | BG Rem,Effects| |               | | - Material gen    |          |  | |
|  |  |  +---------------+ +---------------+ +-------------------+          |  | |
|  |  +-----------------------------------------------------------------------+  | |
|  +-----------------------------------------------------------------------------+ |
|                                                                                   |
|  +-----------------------------------------------------------------------------+ |
|  |                              Data Layer                                      | |
|  |  +---------------+ +---------------+ +---------------+ +----------------+   | |
|  |  |  PostgreSQL   | |    Redis      | | Docker Volume | |  Material DB   |   | |
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
│   ├── worker.py                    # ARQ background worker
│   │
│   ├── api/
│   │   ├── api.py                   # Main router (combines all v1 routes)
│   │   ├── deps.py                  # Dependencies (auth, db session)
│   │   └── v1/
│   │       ├── admin.py             # Admin dashboard endpoints
│   │       ├── auth.py              # Authentication endpoints
│   │       ├── credits.py           # Credit management
│   │       ├── demo.py              # Demo/preset endpoints
│   │       ├── effects.py           # Style transfer & enhancement
│   │       ├── einvoices.py         # Taiwan e-invoice (B2C/B2B issue, void)
│   │       ├── generation.py        # Content generation (T2I, I2V, patterns)
│   │       ├── interior.py          # Interior design endpoints
│   │       ├── landing.py           # Landing page data
│   │       ├── payments.py          # Payment webhooks (Paddle + ECPay)
│   │       ├── plans.py             # Subscription plans
│   │       ├── promotions.py        # Promotional codes
│   │       ├── prompts.py           # Prompt templates API
│   │       ├── quota.py             # Usage quota management
│   │       ├── referrals.py         # Referral system
│   │       ├── session.py           # Session heartbeat & online tracking
│   │       ├── social_media.py      # Social media OAuth & publishing
│   │       ├── subscriptions.py     # Subscription management
│   │       ├── tools.py             # Tool-specific endpoints (8 tools)
│   │       ├── uploads.py           # Subscriber material uploads
│   │       ├── user_works.py        # User generation history
│   │       └── workflow.py          # Workflow management
│   │
│   ├── config/
│   │   ├── demo_topics.py           # Demo topic configuration (legacy)
│   │   ├── topic_registry.py        # Topic registry (single source of truth)
│   │   └── try_prompts.py           # Try prompt configuration
│   │
│   ├── core/
│   │   ├── config.py                # Settings & environment variables
│   │   ├── database.py              # Database connection (async)
│   │   └── security.py              # JWT & password hashing
│   │
│   ├── models/
│   │   ├── billing.py               # Plan, Subscription, Order, Invoice, CreditTransaction, etc.
│   │   ├── demo.py                  # DemoCategory, DemoVideo, ToolShowcase, etc.
│   │   ├── material.py              # Material, MaterialView, MaterialTopic, ToolType
│   │   ├── prompt_template.py       # PromptTemplate, PromptTemplateUsage
│   │   ├── social_account.py        # SocialAccount (OAuth connections)
│   │   ├── social_post.py          # SocialPost (published post tracking)
│   │   ├── user.py                  # User model
│   │   ├── user_generation.py       # UserGeneration (subscriber results)
│   │   ├── user_upload.py           # UserUpload (subscriber uploads)
│   │   └── verification.py          # EmailVerification
│   │
│   ├── providers/
│   │   ├── base.py                  # Base provider interface
│   │   ├── piapi_mcp_provider.py    # PiAPI via MCP (primary: video + image)
│   │   ├── pollo_mcp_provider.py    # Pollo.ai via MCP (backup: video)
│   │   ├── vertex_ai_provider.py    # Vertex AI Gemini + Veo (image backup, 3rd video, moderation)
│   │   ├── piapi_provider.py        # PiAPI REST (legacy fallback)
│   │   ├── pollo_provider.py        # Pollo REST (legacy fallback)
│   │   ├── a2e_provider.py          # A2E (avatar backup)
│   │   └── provider_router.py       # Routes tasks → providers
│   │
│   ├── schemas/
│   │   ├── credit.py                # Credit-related schemas
│   │   ├── demo.py                  # Demo schemas
│   │   ├── moderation.py            # Moderation schemas
│   │   ├── payment.py               # Payment schemas
│   │   ├── plan.py                  # Plan schemas
│   │   ├── promotion.py             # Promotion schemas
│   │   ├── einvoice.py              # Taiwan e-invoice schemas
│   │   └── user.py                  # User schemas
│   │
│   ├── services/
│   │   ├── gemini_service.py        # Gemini AI service (prompt enhancement, moderation, embeddings)
│   │   ├── mcp_client.py           # MCP client manager (subprocess lifecycle)
│   │   ├── gcs_storage_service.py  # CDN → GCS persistence
│   │   ├── admin_dashboard.py       # Admin dashboard service (stats, API costs, active users)
│   │   ├── invoice_service.py      # Taiwan e-invoice business logic
│   │   ├── block_cache.py           # Block-level caching
│   │   ├── credit_service.py        # Credit management
│   │   ├── demo.py                  # Demo data service
│   │   ├── demo_service.py          # Demo generation service
│   │   ├── effects_service.py       # Style transfer service
│   │   ├── email_service.py         # Email sending
│   │   ├── email_verify.py          # Email verification
│   │   ├── image_generator.py       # Image generation service
│   │   ├── interior_design_service.py # Interior design service
│   │   ├── leonardo_service.py      # Leonardo AI (legacy)
│   │   ├── material_generator.py    # Material pre-generation
│   │   ├── material_lookup.py       # O(1) material lookup
│   │   ├── media_cleanup_service.py # 14-day media cleanup
│   │   ├── moderation.py            # Content moderation (Gemini)
│   │   ├── paddle_service.py        # Paddle payment service
│   │   ├── piapi_client.py           # PiAPI client
│   │   ├── prompt_generator.py      # Prompt generation & caching
│   │   ├── prompt_matching.py       # Prompt similarity matching
│   │   ├── referral_service.py      # Referral system
│   │   ├── rescue_service.py        # Error recovery service
│   │   ├── session_tracker.py       # Session/online tracking
│   │   ├── similarity.py            # Similarity computation
│   │   ├── social_media_service.py  # Social media OAuth & publishing (FB, IG, TikTok, YouTube)
│   │   ├── token_refresh_service.py # Auto-refresh expiring OAuth tokens (FB, TikTok, YouTube)
│   │   ├── subscription_service.py  # Subscription management
│   │   ├── taigi_tts.py             # Taiwanese TTS service
│   │   ├── watermark.py             # Watermark application
│   │   ├── workflow_generator.py    # Workflow generation
│   │   ├── workflow_service.py      # Workflow execution
│   │   ├── base/
│   │   │   ├── generation.py        # Base generation service
│   │   │   └── material.py          # Base material service
│   │   ├── generation/
│   │   │   ├── factory.py           # Generation service factory
│   │   │   └── piapi_service.py     # PiAPI generation
│   │   └── material/
│   │       ├── collector.py         # Material collection
│   │       ├── generator.py         # Material generation
│   │       ├── library.py           # Material library
│   │       └── requirements.py      # Material requirements
│   │
├── alembic/                         # Database migrations
├── scripts/                         # CLI scripts (pregenerate, seed, etc.)
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
api_router.include_router(plans.router, prefix="/plans", tags=["plans"])
api_router.include_router(promotions.router, prefix="/promotions", tags=["promotions"])
api_router.include_router(credits.router, tags=["credits"])
api_router.include_router(effects.router, tags=["effects"])
api_router.include_router(generation.router, prefix="/generate", tags=["generation"])
api_router.include_router(landing.router, prefix="/landing", tags=["landing"])
api_router.include_router(quota.router, prefix="/quota", tags=["quota"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(session.router, prefix="/session", tags=["session"])
api_router.include_router(interior.router, tags=["interior"])
api_router.include_router(workflow.router, tags=["workflow"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
api_router.include_router(user_works.router, prefix="/user", tags=["user"])
api_router.include_router(uploads.router, tags=["uploads"])
api_router.include_router(referrals.router, tags=["referrals"])
api_router.include_router(social_media.router, tags=["social"])
api_router.include_router(einvoices.router, prefix="/einvoices", tags=["einvoices"])
```

### Endpoint Summary

| Prefix | Tag | Description |
|--------|-----|-------------|
| `/auth` | auth | Authentication (login, register, verify, password reset, geo-language) |
| `/payments` | payments | Payment webhooks (Paddle + ECPay) |
| `/subscriptions` | subscriptions | Subscription CRUD, invoices, refund |
| `/demo` | demo | Demo presets, showcases, inspiration, search |
| `/plans` | plans | Plan listing and details |
| `/promotions` | promotions | Promo codes, credit packages (user + admin) |
| `/credits` | credits | Credit balance, transactions, pricing |
| `/effects` | effects | Style transfer, HD enhance, video enhance |
| `/generate` | generation | T2I, I2V, pattern, product, video generation |
| `/landing` | landing | Landing page data (stats, features, examples, FAQ) |
| `/quota` | quota | Daily/user/promo quota management |
| `/tools` | tools | 8 core AI tools (remove-bg, product-scene, try-on, etc.) |
| `/admin` | admin | Admin dashboard, user/material management, moderation, API costs, active users |
| `/einvoices` | einvoices | Taiwan e-invoice (B2C/B2B issue, void, preferences) |
| `/session` | session | Session heartbeat, online count |
| `/interior` | interior | Interior design (redesign, generate, fusion, edit, style-transfer) |
| `/workflow` | workflow | Workflow topics, categories, generation |
| `/prompts` | prompts | Prompt templates, groups, demo/subscriber generation |
| `/user` | user | User generation history, stats, downloads |
| `/uploads` | uploads | Subscriber material upload + real-API generation |
| `/referrals` | referrals | Referral code, stats, apply, leaderboard |
| `/social` | social | Social media OAuth + publishing (FB, IG, TikTok, YouTube), post history, analytics |

---

## 4. Database Models

### 4.1 Core Models

```python
# User Management
User                    # User account (email, password, plan, referral fields)

# Billing & Subscriptions
Plan                    # Subscription plan definitions
Subscription            # Active subscriptions
Order                   # Payment orders
Invoice                 # Invoice records (Taiwan e-invoice fields: carrier, donation, ECPay tracking)
InvoiceItem             # Invoice line items (required by ECPay API)
Promotion               # Promotional campaigns
CreditPackage           # Purchasable credit packs
PromotionUsage          # Promo code usage tracking
CreditTransaction       # Credit ledger entries
ServicePricing          # Per-service pricing
Generation              # Generation records (billing context)

# Demo & Showcase
DemoCategory            # Demo categories
ImageDemo               # Image demo entries
DemoVideo               # Video demo entries
DemoView                # View tracking
PromptCache             # Cached prompt results
DemoExample             # Demo examples
ToolShowcase            # Tool showcase entries

# Materials (Preset-Only Mode)
Material                # Pre-generated examples (core model)
MaterialView            # Material view tracking
MaterialTopic           # Material topic definitions
ToolType (enum)         # 8 core tools
MaterialSource (enum)   # seed / user / admin
MaterialStatus (enum)   # pending / approved / rejected / featured

# Prompt Templates
PromptTemplate          # Reusable prompt templates
PromptTemplateUsage     # Template usage tracking
PromptGroup (enum)      # Template groups
PromptSubTopic (enum)   # Template sub-topics

# Social
SocialAccount           # OAuth-connected social accounts (FB, IG, TikTok, YouTube)
SocialPost              # Published post tracking (platform, status, analytics)

# User Content
UserGeneration          # Subscriber generation results (14-day retention)
UserUpload              # Subscriber uploaded materials

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

| Provider | Interface | Purpose | Env Variable |
|----------|-----------|---------|--------------|
| PiAPI | MCP (stdio) | **Primary** for video + image + specialized: T2I, I2I, I2V, T2V, V2V, Interior, Avatar, BG Removal, Effects, 3D | `PIAPI_KEY` |
| Pollo.ai | MCP (stdio) | **Backup** for video tasks (50+ models): I2V, T2V, V2V | `POLLO_API_KEY` |
| Vertex AI | GCP SDK | **Backup** for image tasks (Gemini), **3rd backup** for video (Veo), **Primary** for moderation + material gen | `VERTEX_AI_PROJECT` |
| A2E | REST | **Backup** for avatar generation | `A2E_API_KEY` |

**Failover Strategy:**
- **Video tasks** (I2V, T2V, V2V): PiAPI MCP → Pollo MCP → Vertex AI Veo → PiAPI REST
- **Image tasks** (T2I, I2I, Interior, BG Removal, Upscale, Effects): PiAPI MCP → Vertex AI Gemini → PiAPI REST
- **Avatar**: PiAPI MCP → A2E → PiAPI REST
- **Moderation & Material generation**: Vertex AI Gemini only
- Provider names are never exposed to end users

### 5.2 Provider Router

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

# Routing configuration:
# Video (I2V, T2V, V2V) → PiAPI MCP primary, Pollo MCP backup, Vertex AI Veo 3rd
# Image (T2I, I2I, Interior, BG Removal, Upscale, Effects) → PiAPI MCP primary, Vertex AI Gemini backup
# Avatar → PiAPI MCP primary, A2E backup
# Moderation & Material pre-generation → Vertex AI Gemini only
```

### 5.3 PiAPI Service

**Base URL:** `https://api.piapi.ai/api/v1`
**Auth:** X-API-Key header

Task types: `txt2img`, `img2img`, `ai_try_on`, `background-remove`, `wan26-img2video`, `wan26-txt2video`, `kontext`

```
Step 1: POST /task                       → Create task
Step 2: GET /task/{task_id}              → Poll for result
```

### 5.4 Interior Design Service

- **Free users:** Browse pre-generated examples (watermarked)
- **Subscribers:** Real-time generation with multiple modes:
  - Redesign: Transform room photos with style
  - Generate: Create room from scratch
  - Fusion: Blend two styles
  - Edit: Iterative conversation-based editing
  - Style Transfer: Apply style from reference image

---

## 6. Payment System

### 6.1 Supported Payment Providers

| Provider | Region | Status |
|----------|--------|--------|
| Paddle | International | Active |
| ECPay | Taiwan | Active |

### 6.2 Configuration

```python
# Paddle
PADDLE_API_KEY: str = ""
PADDLE_PUBLIC_KEY: str = ""

# ECPay (Taiwan)
ECPAY_MERCHANT_ID: str = ""
ECPAY_HASH_KEY: str = ""
ECPAY_HASH_IV: str = ""
ECPAY_PAYMENT_URL: str = "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"
```

### 6.3 Subscription Flow

- Subscribe: `POST /subscriptions/subscribe` → returns `checkout_url`
- Paddle webhook: `POST /payments/paddle/webhook` → activates subscription
- ECPay callback: `POST /payments/ecpay/callback` → activates subscription
- Cancel: `POST /subscriptions/cancel` (optional refund within 7 days)
- Invoices: `GET /subscriptions/invoices` → list, `GET /subscriptions/invoices/{id}/pdf` → PDF

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
    VERTEX_AI_PROJECT: str = ""          # GCP project ID
    VERTEX_AI_LOCATION: str = "us-central1"
    GEMINI_API_KEY: str = ""             # Legacy fallback

    # YouTube (Google OAuth 2.0 for YouTube Data API v3)
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""

    # Taiwanese TTS
    TAIGI_TTS_API_KEY: str = ""
    TAI5UAN5_BASE_URL: str = ""

    # Payments
    ECPAY_MERCHANT_ID: str = ""
    ECPAY_HASH_KEY: str = ""
    ECPAY_HASH_IV: str = ""
    PADDLE_API_KEY: str = ""
    PADDLE_PUBLIC_KEY: str = ""

    # Storage
    S3_BUCKET: str = ""
```

---

## 8. Pre-generation Pipeline

### 8.1 Startup Sequence

```
1. Wait for PostgreSQL + Redis
2. Run database migrations (alembic upgrade head)
3. Seed service pricing
4. Validate pre-generated materials (blocking)
5. Run initial media cleanup (14-day retention)
6. Start hourly cleanup background task
7. Start uvicorn
```

### 8.2 Material Topics

| Tool | Topics |
|------|--------|
| background_removal | drinks, snacks, desserts, meals, packaging, equipment, signage, ingredients |
| product_scene | studio, nature, luxury, minimal, lifestyle, urban, seasonal, holiday |
| try_on | casual, formal, dresses, sportswear, outerwear, accessories |
| room_redesign | modern, nordic, japanese, industrial, minimalist, luxury |
| short_video | product_showcase, brand_intro, tutorial, promo |
| ai_avatar | spokesperson, product_intro, customer_service, social_media |
| pattern_generate | seamless, floral, geometric, abstract, traditional |
| effect | anime, ghibli, cartoon, oil_painting, watercolor |

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
  postgres:       # PostgreSQL 15 - Primary database (port 5432)
  redis:          # Redis 7 - Cache & task queue (port 6379)
  mailpit:        # Email testing - dev only (port 8025)
  backend:        # FastAPI application (port 8001)
  worker:         # ARQ background worker
  init-materials: # Initial pre-generation (runs once)
  frontend:       # Vue 3 frontend (port 8501)

volumes:
  postgres_data:         # Persist PostgreSQL data
  redis_data:            # Persist Redis data
  vidgo_generated:       # Persist generated images/videos (Docker volume)
  vidgo_materials:       # Persist pre-generated materials (Docker volume)
  vidgo_tryon_garments:  # Persist cached Virtual Try-On garment images
```

**Storage:** Pre-generated materials and user-generated content are stored in **Docker named volumes** (`vidgo_materials`, `vidgo_generated`), NOT on the local filesystem. This ensures data persists across container restarts and rebuilds.

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

*Document Version: 7.0*
*Last Updated: March 17, 2026*
*Mode: Dual-Mode — Preset-Only (free) + Real-API (subscribers)*
*Target: SMB (small businesses selling everyday products/services)*
