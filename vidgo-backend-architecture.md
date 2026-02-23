# VidGo AI Platform - Backend Architecture

**Version:** 5.1
**Last Updated:** February 23, 2026
**Framework:** FastAPI + Python 3.12
**Database:** PostgreSQL + Redis
**Mode:** Dual-Mode — Preset-Only (free) + Real-API (subscribers)
**Target Audience:** Small businesses (SMB) selling everyday products/services—not luxury.

---

## 0. User Tiers & Access Control

### 0.1 Free/Demo Users (Preset-Only)
**User experience:** Visitors and non-subscribers try default AI functions by selecting pre-generated presets. No runtime API calls—all results are pre-computed and stored in Material DB.

**Flow:**
1. **Pre-generation (startup/CLI):** Prompts → AI APIs (T2I, I2V, I2I, etc.) → results stored in `materials` table
2. **User trial:** Frontend loads presets from `/api/v1/demo/presets/{tool_type}` → user selects preset → backend returns watermarked result via O(1) Material DB lookup
3. **Download blocked.** All demo results carry a watermark; download requires subscription.

### 0.2 Subscribers (Real-API Mode)
**User experience:** Subscribers upload their own images and trigger live AI API calls. Results are returned without watermarks and can be downloaded.

**Flow:**
1. **Upload:** `POST /api/v1/uploads/material` (multipart form: file + tool_type + model_id + prompt)
2. **Credit deduction:** Credits deducted based on `tool_type` base cost × model multiplier
3. **Generation:** Backend calls AI provider (PiAPI / Pollo / A2E) in real time
4. **Result:** `result_url` / `result_video_url` stored without watermark; `GET /api/v1/uploads/{id}/download`

### 0.3 Preset Download (Subscribers)
Subscribers can also download full-quality (no watermark) versions of preset gallery results:
- `POST /api/v1/demo/use-preset` returns `result_url` (full quality) when authenticated as subscriber
- `GET /api/v1/demo/download/{material_id}` redirects to full-quality result URL

**Tier config keys** (`app/services/tier_config.py`):
Each tool maps to a tier_config key that defines per-tier credit cost and quality parameters. The `i2i` key is configured as:
- **Free:** 20 pts, strength 0.65
- **Paid:** 80 pts, strength 0.70

**Credit cost table:**

| Tool | Free Tier | Paid Tier |
|------|-----------|-----------|
| T2I | 20 pts | 80 pts |
| I2V | 25 pts | 100 pts |
| T2V | 30 pts | 120 pts |
| Avatar | 35 pts | 100 pts |
| Interior | 25 pts | 90 pts |
| Interior 3D | 30 pts | 100 pts |
| Background Removal | 20 pts | 80 pts |
| Effect/Style | 20 pts | 80 pts |
| I2I (Image-to-Image) | 20 pts | 80 pts |

### 0.4 Model Selection
Paid users can select AI models for upload-based generation. Better models cost more credits:

| Model | Multiplier | Tools |
|-------|------------|-------|
| default | 1× | All tools |
| pixverse_v5 | 1.5× | short_video |
| kling_v2 | 2× | try_on, short_video |
| wan_pro | 2× | product_scene, room_redesign, pattern_generate, effect |
| luma_ray2 | 3× | short_video |

### 0.5 Referral System
Users earn bonus credits by inviting others:
- Referrer: **+50 credits** per successful registration via their code
- New user: **+20 credits** when registering with a referral code
- Endpoints: `GET /referrals/code`, `GET /referrals/stats`, `POST /referrals/apply`, `GET /referrals/leaderboard`

**Target audience:** Small companies selling everyday products (drinks, snacks, apparel, services)—not luxury brands.

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
|  |  +-----------------------------------------------------------------------+  | |
|  |                                                                             | |
|  |  +-----------------------------------------------------------------------+  | |
|  |  |                          Service Layer                                |  | |
|  |  |                                                                       |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  |  | Material      | | Demo          | | Credit        | | Generation | |  | |
|  |  |  | Lookup        | | Service       | | Service       | | Service    | |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  |                                                                       |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  |  | A2E Avatar    | | Interior      | | Subscription  | | Payment    | |  | |
|  |  |  | Service       | | Service       | | Service       | | Service    | |  | |
|  |  |  +---------------+ +---------------+ +---------------+ +------------+ |  | |
|  |  +-----------------------------------------------------------------------+  | |
|  |                                                                             | |
|  |  +-----------------------------------------------------------------------+  | |
|  |  |                       AI Provider Layer                               |  | |
|  |  |                                                                       |  | |
|  |  |  +-------------------+  +-------------------+  +-------------------+  |  | |
|  |  |  |   PiAPI (Wan)     |  |   Pollo AI API    |  |    A2E.ai API     |  |  | |
|  |  |  | - T2I             |  | - I2V (Pixverse)  |  | - Avatar Video    |  |  | |
|  |  |  | - I2I (Style)     |  | - T2V (Pollo)     |  | - Lip-sync TTS    |  |  | |
|  |  |  | - I2V, Interior   |  |                   |  |                   |  |  | |
|  |  |  +-------------------+  +-------------------+  +-------------------+  |  | |
|  |  |                                                                       |  | |
|  |  |  +-------------------+                                               |  | |
|  |  |  |   Gemini API      |                                               |  | |
|  |  |  | - Moderation      |                                               |  | |
|  |  |  | - Backup Image    |                                               |  | |
|  |  |  +-------------------+                                               |  | |
|  |  +-----------------------------------------------------------------------+  | |
|  +-----------------------------------------------------------------------------+ |
|                                                                                   |
|  +-----------------------------------------------------------------------------+ |
|  |                              Data Layer                                      | |
|  |  +---------------+ +---------------+ +---------------+ +----------------+   | |
|  |  |  PostgreSQL   | |    Redis      | | Local Storage | |  Material DB   |   | |
|  |  |  (Main DB)    | | (Cache/Queue) | | (Media Files) | | (Pre-generated)|   | |
|  |  +---------------+ +---------------+ +---------------+ +----------------+   | |
|  +-----------------------------------------------------------------------------+ |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

---

## 2. Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI application entry
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── api.py                   # Main router (combines all v1 routes)
│   │   ├── deps.py                  # Dependencies (auth, db session)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── auth.py              # Authentication endpoints
│   │       ├── admin.py             # Admin dashboard endpoints
│   │       ├── credits.py           # Credit management
│   │       ├── demo.py              # Demo/preset endpoints
│   │       ├── effects.py           # Video effects
│   │       ├── generation.py        # Content generation
│   │       ├── interior.py          # Interior design endpoints
│   │       ├── landing.py           # Landing page data
│   │       ├── payments.py          # Payment webhooks
│   │       ├── plans.py             # Subscription plans
│   │       ├── promotions.py        # Promotional codes
│   │       ├── prompts.py           # Prompt templates API
│   │       ├── quota.py             # Usage quota management
│   │       ├── session.py           # Session management
│   │       ├── subscriptions.py     # Subscription management
│   │       ├── tools.py             # Tool-specific endpoints
│   │       └── workflow.py          # Workflow management
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── demo_topics.py           # Demo topic configuration (legacy)
│   │   └── topic_registry.py       # Topic registry (single source of truth)
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Settings & environment variables
│   │   ├── database.py              # Database connection
│   │   └── security.py              # JWT & password hashing
│   │
│   ├── models/
│   │   ├── __init__.py              # Model exports
│   │   ├── billing.py               # Plan, Subscription, Order, Invoice
│   │   ├── demo.py                  # DemoCategory, DemoVideo, ToolShowcase
│   │   ├── material.py              # Material, MaterialView, MaterialTopic
│   │   ├── prompt_template.py       # PromptTemplate, PromptTemplateUsage
│   │   ├── user.py                  # User model
│   │   └── verification.py          # EmailVerification
│   │
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py                  # Base provider interface
│   │   ├── a2e_provider.py          # A2E.ai Avatar provider
│   │   ├── gemini_provider.py       # Google Gemini provider
│   │   ├── piapi_provider.py        # PiAPI (Wan) provider - Primary
│   │   ├── pollo_provider.py        # Pollo AI provider
│   │   └── provider_router.py       # Smart routing between providers
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── credit.py
│   │   ├── demo.py
│   │   ├── moderation.py
│   │   ├── payment.py
│   │   ├── plan.py
│   │   ├── promotion.py
│   │   └── user.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── a2e_service.py           # A2E Avatar service
│   │   ├── admin_dashboard.py       # Admin dashboard service
│   │   ├── block_cache.py           # Block-level caching
│   │   ├── credit_service.py        # Credit management
│   │   ├── demo.py                  # Demo data service
│   │   ├── demo_service.py          # Demo generation service
│   │   ├── effects_service.py       # Video effects service
│   │   ├── email_service.py         # Email sending
│   │   ├── email_verify.py          # Email verification
│   │   ├── gemini_service.py        # Gemini AI service
│   │   ├── image_generator.py       # Image generation service
│   │   ├── interior_design_service.py # Interior design service
│   │   ├── leonardo_service.py      # Leonardo AI (legacy)
│   │   ├── material_generator.py    # Material generation
│   │   ├── material_lookup.py       # O(1) material lookup
│   │   ├── moderation.py            # Content moderation
│   │   ├── paddle_service.py        # Paddle payment service
│   │   ├── pollo_ai.py              # Pollo AI client
│   │   ├── prompt_generator.py      # Prompt generation & caching
│   │   ├── rescue_service.py        # Error recovery service
│   │   ├── subscription_service.py  # Subscription management
│   │   ├── workflow_generator.py    # Workflow generation
│   │   ├── workflow_service.py      # Workflow execution
│   │   │
│   │   ├── base/
│   │   │   ├── __init__.py
│   │   │   ├── generation.py        # Base generation service
│   │   │   └── material.py          # Base material service
│   │   │
│   │   ├── ecpay/
│   │   │   ├── __init__.py
│   │   │   └── client.py            # ECPay payment client
│   │   │
│   │   ├── generation/
│   │   │   ├── __init__.py
│   │   │   ├── factory.py           # Generation service factory
│   │   │   └── pollo_service.py     # Pollo AI generation
│   │   │
│   │   └── material/
│   │       ├── __init__.py
│   │       ├── collector.py         # Material collection
│   │       ├── generator.py         # Material generation
│   │       ├── library.py           # Material library
│   │       └── requirements.py      # Material requirements
│   │
│   └── worker.py                    # ARQ background worker
│
├── alembic/
│   ├── alembic.ini
│   ├── env.py
│   └── versions/                    # Database migrations
│
├── scripts/
│   ├── docker_entrypoint.sh         # Docker startup script
│   ├── main_pregenerate.py          # Main pre-generation pipeline (8 tools)
│   ├── startup_check.py             # Startup validation
│   ├── test_api_keys.py             # API key validation
│   └── services/                    # Service-specific scripts
│
├── static/
│   ├── generated/                   # Generated images/videos
│   │   ├── demos/                   # Demo materials
│   │   └── interior/                # Interior design results
│   └── materials/                   # Avatar and source materials
│
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## 3. API Endpoints

### 3.1 Main Router Configuration

```python
# app/api/api.py
from fastapi import APIRouter
from app.api.v1 import (
    auth, payments, demo, plans, promotions, credits,
    effects, generation, landing, quota, tools, admin,
    session, interior, workflow, subscriptions, prompts
)

api_router = APIRouter()
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
```

### 3.2 Endpoint Summary

| Prefix | Tag | Description |
|--------|-----|-------------|
| `/auth` | auth | User authentication (login, register, 6-digit verify; verify-code returns tokens) |
| `/payments` | payments | Payment webhooks (Paddle) |
| `/subscriptions` | subscriptions | Subscription management (plans seed defaults; subscribe returns checkout_url) |
| `/demo` | demo | Demo/preset endpoints; `use-preset` returns full URL for subscribers, watermarked for free users |
| `/plans` | plans | Subscription plan details (ensure_default_plans) |
| `/promotions` | promotions | Promotional codes |
| `/credits` | credits | Credit balance and transactions |
| `/effects` | effects | Video effects |
| `/generate` | generation | Content generation (subscribers) |
| `/uploads` | uploads | **NEW** Subscriber material upload + real-API generation + download (no watermark) |
| `/referrals` | referrals | **NEW** Referral code, stats, apply, leaderboard |
| `/landing` | landing | Landing page data |
| `/quota` | quota | Usage quota management |
| `/tools` | tools | Tool-specific operations |
| `/admin` | admin | Admin dashboard |
| `/session` | session | Session management |
| `/interior` | interior | Interior design |
| `/workflow` | workflow | Workflow management |
| `/prompts` | prompts | Prompt templates |
| `/user` | user | User works history |

### 3.3 Detailed Endpoint Documentation

#### `POST /api/v1/tools/image-transform` — Image-to-Image Transformation (NEW)

True Image-to-Image transformation via PiAPI Flux (model: `flux1-schnell`).

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `image_url` | HttpUrl | Yes | — | Source image URL to transform |
| `prompt` | str | Yes | — | Transformation prompt describing desired output |
| `strength` | float | No | 0.75 | Transformation strength (0.0-1.0). Lower preserves more of the original. |
| `negative_prompt` | str | No | None | Negative prompt to exclude unwanted elements |

**Response:** Standard `ToolResponse`

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the operation succeeded |
| `result_url` | str | URL of the transformed image |
| `credits_used` | int | Credits consumed |
| `message` | str | Status message |
| `cached` | bool | Whether the result was served from cache |

**Behavior by user type:**

- **Demo users (no credits):** Returns a pre-generated result from the Material DB (matched via `ToolType.EFFECT`). No AI generation is performed.
- **Subscribers (with credits):** Real-time I2I generation via PiAPI Flux `img2img`. Result is saved to `UserGeneration` table.

**Credits:** 20 (free tier) / 80 (paid tier)

---

#### `POST /api/v1/interior/3d-model` — 3D Model from Interior Design Image (NEW)

Generate a 3D model (GLB format) from a 2D interior design image via PiAPI Trellis (`Qubico/trellis`).

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `image_url` | str | Yes | — | URL of the 2D interior design image |
| `texture_size` | int | No | 1024 | Texture resolution: `512` (free) or `1024` (paid) |
| `mesh_simplify` | float | No | 0.95 | Mesh simplification ratio (0.0-1.0) |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether the operation succeeded |
| `model_url` | str | URL of the generated GLB 3D model file |
| `task_id` | str | PiAPI task ID for reference |

**Auth:** Requires authentication and credit check (HTTP 402 if insufficient).

**Credits:** 30 (free tier, 512px texture) / 100 (paid tier, 1024px texture)

---

## 4. Database Models

### 4.0 New Models (v5.0)

```python
# app/models/user_upload.py  — subscriber material uploads
class UserUpload(Base):
    """
    File uploaded by a subscriber for use with a real AI generation call.
    Tracks upload, generation status, result URL (no watermark), and credits used.
    """
    tool_type: str               # e.g. "background_removal"
    file_url: str                # stored path
    selected_model: str          # model chosen by user
    status: UploadStatus         # pending → processing → completed / failed
    result_url: str              # result image (no watermark)
    result_video_url: str        # result video (no watermark)
    credits_used: int            # credits deducted for this generation

# app/models/user.py — referral fields added
class User(Base):
    referral_code: str           # unique 8-char code (auto-generated)
    referred_by_id: UUID         # FK → users.id of referrer
    referral_count: int          # number of successful referrals
```

### 4.1 Core Models

```python
# app/models/__init__.py

# User Management
from app.models.user import User

# Billing & Subscriptions
from app.models.billing import (
    Plan, Subscription, Order, Invoice, Promotion,
    CreditPackage, PromotionUsage, CreditTransaction,
    ServicePricing, Generation
)

# Demo & Showcase
from app.models.demo import (
    DemoCategory, DemoVideo, DemoView, ImageDemo,
    PromptCache, DemoExample, ToolShowcase
)

# Materials (Core for Preset-Only Mode)
from app.models.material import (
    Material, MaterialView, MaterialTopic,
    ToolType, MaterialSource, MaterialStatus
)

# Verification
from app.models.verification import EmailVerification

# Prompt Templates
from app.models.prompt_template import (
    PromptTemplate, PromptTemplateUsage,
    PromptGroup, PromptSubTopic
)
```

### 4.2 Material Model (Preset-Only Mode)

```python
class ToolType(str, enum.Enum):
    """8 Core Tools"""
    BACKGROUND_REMOVAL = "background_removal"
    PRODUCT_SCENE = "product_scene"
    TRY_ON = "try_on"
    ROOM_REDESIGN = "room_redesign"
    SHORT_VIDEO = "short_video"
    AI_AVATAR = "ai_avatar"
    PATTERN_GENERATE = "pattern_generate"
    EFFECT = "effect"  # Style transfer / artistic effects

class MaterialSource(str, enum.Enum):
    SEED = "seed"      # Pre-generated
    USER = "user"      # User-generated
    ADMIN = "admin"    # Admin-curated

class MaterialStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FEATURED = "featured"

class Material(Base):
    """
    Unified Material model for pre-generated examples.

    Key Fields:
    - lookup_hash: SHA256 for O(1) preset lookup
    - tool_type: One of 8 core tools
    - prompt/prompt_zh: Multi-language prompts
    - result_image_url/result_video_url: Generated outputs
    - result_watermarked_url: Watermarked version for demo
    """
    __tablename__ = "materials"

    id = Column(UUID, primary_key=True)
    lookup_hash = Column(String(64), unique=True, index=True)
    tool_type = Column(Enum(ToolType), nullable=False, index=True)
    topic = Column(String(100), nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    prompt_zh = Column(Text, nullable=True)
    result_image_url = Column(String(500), nullable=True)
    result_video_url = Column(String(500), nullable=True)
    result_watermarked_url = Column(String(500), nullable=True)
    # ... additional fields
```

### 4.3 Material Pre-generation and Watermark Data Flow

The following diagram shows how materials are pre-generated with watermarks for the preset-only mode:

```mermaid
flowchart LR
    subgraph Pre-generation["Pre-generation Script"]
        A[Prompt] --> B[T2I/API]
        B --> C[result_image_url]
        C --> D["Apply Watermark (Vidgo AI)"]
        D --> E[result_watermarked_url]
    end
    
    subgraph Database["Material DB"]
        E --> F[(materials table)]
        C --> G[input_image_url]
        G --> F
    end
    
    subgraph Frontend["Frontend Display"]
        F --> H["Before: input_image_url"]
        F --> I["After: result_watermarked_url"]
    end
```

**Key Points:**
- `input_image_url`: The original/before image (e.g., product, room, person)
- `result_image_url` or `result_video_url`: The raw generated result
- `result_watermarked_url`: The watermarked version displayed to demo users
- All demo users see watermarked results only; download is blocked

---

## 5. AI Provider Integration

### 5.1 Provider Summary

| Provider | API | Purpose | Cost | Env Variable |
|----------|-----|---------|------|--------------|
| PiAPI | Wan API | T2I, I2I (Style Transfer), I2V, Interior Design | Medium | `PIAPI_KEY` |
| Pollo AI | Pixverse, Kling, Luma | I2V, T2V | Medium | `POLLO_API_KEY` |
| A2E.ai | Lip-sync + TTS | Avatar Video | Medium | `A2E_API_KEY`, `A2E_DEFAULT_CREATOR_ID` |
| Gemini | Generative AI | Moderation, Backup Image | Low | `GEMINI_API_KEY` |

### 5.2 Provider Router

```python
<<<<<<< HEAD
# app/providers/provider_router.py
=======
class TaskType(str, Enum):
    T2I = "text_to_image"
    I2V = "image_to_video"
    T2V = "text_to_video"
    V2V = "video_style_transfer"
    INTERIOR = "interior_design"
    INTERIOR_3D = "interior_3d"
    AVATAR = "avatar"
    UPSCALE = "upscale"
    KEYFRAMES = "keyframes"
    EFFECTS = "effects"
    MULTI_MODEL = "multi_model"
    MODERATION = "moderation"
    BACKGROUND_REMOVAL = "background_removal"
    I2I = "image_to_image"
>>>>>>> origin/claude/add-free-trial-mode-B21Bl

class ProviderRouter:
    """
    Smart routing between AI providers with fallback.

    Routing Strategy:
    - T2I: PiAPI Wan (primary) -> Gemini (backup)
    - I2V: Pollo AI -> PiAPI Wan
    - T2V: Pollo AI -> PiAPI Wan
    - Avatar: A2E.ai (no backup)
<<<<<<< HEAD
    - Interior: PiAPI Wan -> Gemini
    """

    ROUTING_CONFIG = {
        "text_to_image": {"primary": "piapi", "backup": "gemini"},
        "image_to_image": {"primary": "piapi", "backup": None},  # Style transfer
        "image_to_video": {"primary": "pollo", "backup": "piapi"},
        "text_to_video": {"primary": "pollo", "backup": "piapi"},
        "avatar": {"primary": "a2e", "backup": None},
        "interior": {"primary": "piapi", "backup": "gemini"},
    }
=======
    - Background Removal: PiAPI (no backup)
    - I2I: PiAPI (primary, model: flux1-schnell), no backup
    - Keyframes/Effects/MultiModel: Pollo only
    - Moderation: Gemini only
    """

    async def route(self, task_type, params, user_tier="free", user=None):
        # Auto-detect tier from user object
        if user is not None:
            user_tier = get_user_tier(user)
        # Apply tier-based parameter overrides
        params = self._apply_tier_overrides(task_type, params, user_tier)
        # Route to provider with failover
        ...

    # Tier key mapping (TaskType -> tier_config key):
    #   T2I -> "t2i", I2V -> "i2v", T2V -> "t2v", AVATAR -> "avatar",
    #   INTERIOR -> "interior", INTERIOR_3D -> "interior_3d",
    #   BACKGROUND_REMOVAL -> "background_removal", EFFECTS -> "effect",
    #   I2I -> "i2i"
>>>>>>> origin/claude/add-free-trial-mode-B21Bl
```

### 5.3 A2E.ai Avatar Service (Verified Workflow)

**Base URL:** `https://video.a2e.ai` (NOT `api.a2e.ai` - that's just docs)

**Authentication:** Bearer token in Authorization header

**Workflow:**
```
+----------------------------------------------------------+
|                 A2E AVATAR GENERATION FLOW                |
+----------------------------------------------------------+
|                                                          |
|  Step 1: GENERATE TTS AUDIO                              |
|  ├─ Endpoint: POST /api/v1/video/send_tts                |
|  ├─ Headers: Authorization: Bearer {A2E_API_KEY}         |
|  ├─ Body: {                                              |
|  │     "msg": "Text to speak",                           |
|  │     "tts_id": "6625ebd4613f49985c349f95",  // Voice ID|
|  │     "speechRate": 1.0                                 |
|  │   }                                                   |
|  └─ Response: {"code": 0, "data": "https://...audio.mp3"}|
|                                                          |
|  Step 2: GENERATE VIDEO                                  |
|  ├─ Endpoint: POST /api/v1/video/generate                |
|  ├─ Body: {                                              |
|  │     "anchor_id": "{A2E_DEFAULT_CREATOR_ID}",          |
|  │     "audioSrc": "https://...audio.mp3",               |
|  │     "anchor_type": 0   // 0 = public anchor           |
|  │   }                                                   |
|  └─ Response: {"code": 0, "data": {"_id": "task_id"}}    |
|                                                          |
|  Step 3: CHECK STATUS (POLL)                             |
|  ├─ Endpoint: POST /api/v1/video/awsResult               |
|  ├─ Body: {"_id": "task_id"}   // MUST use POST, not GET |
|  ├─ Response: {"code": 0, "data": [{                     |
|  │     "status": "success",                              |
|  │     "result": "https://...video.mp4"                  |
|  │   }]}                                                 |
|  └─ Status values: init, process, success, failed        |
|                                                          |
+----------------------------------------------------------+
```

**Configuration Variables:**
```
A2E_API_KEY=sk_xxxxx          # Bearer token (from dashboard)
A2E_API_ID=xxxxx              # Account ID (from JWT payload)
A2E_DEFAULT_CREATOR_ID=xxxxx  # Anchor ID (from character_list)
```

**Get Available Anchors:**
```bash
GET /api/v1/anchor/character_list
# Returns list of available avatars/anchors
```

**AI Avatar Pre-generation Rules:**
- **Gender-name consistency:** Male character name must match male face; female name on female face. Characters are partitioned by detected gender; male voice uses male character, female voice uses female character.
- **Chinese priority:** Most AI Avatars are zh-TW (VidGo targets Taiwan/SMB market). Language order: zh-TW first, then en.
- **Product/service focus:** Scripts must clearly sell a product or service (e.g., "買我們的珍珠奶茶！" / "Buy our bubble tea now!"). Not generic brand fluff—explicit promotion.

### 5.4 Pollo AI Service (Verified Workflow)

**Base URL:** `https://pollo.ai/api/platform`

**Authentication:** x-api-key header

**Available Models:**

| Model | Endpoint | Lengths | Description |
|-------|----------|---------|-------------|
| pixverse_v4.5 | /generation/pixverse/pixverse-v4-5 | 5s, 8s | Fast, affordable |
| pixverse_v5 | /generation/pixverse/pixverse-v5 | 5s, 8s | Creative animations |
| kling_v2 | /generation/kling-ai/kling-v2 | 5s, 10s | High quality |
| kling_v1.5 | /generation/kling-ai/kling-v1-5 | 5s, 10s | Fast, good quality |
| luma_ray2 | /generation/luma/luma-ray-2-0 | 5s, 10s | Cinematic quality |

**Workflow:**
```
+----------------------------------------------------------+
|                POLLO I2V GENERATION FLOW                  |
+----------------------------------------------------------+
|                                                          |
|  Step 1: CREATE TASK                                     |
|  ├─ Endpoint: POST /generation/pixverse/pixverse-v4-5    |
|  ├─ Headers: x-api-key: {POLLO_API_KEY}                  |
|  ├─ Body: {                                              |
|  │     "input": {                                        |
|  │       "image": "https://...image.jpg",                |
|  │       "prompt": "animation description",              |
|  │       "negativePrompt": "blurry, distorted",          |
|  │       "length": 5                                     |
|  │     }                                                 |
|  │   }                                                   |
|  └─ Response: {"code": "SUCCESS", "data": {"taskId":...}}|
|                                                          |
|  Step 2: CHECK STATUS (POLL)                             |
|  ├─ Endpoint: GET /generation/{taskId}/status            |
|  ├─ Response: {"data": {"generations": [{                |
|  │     "status": "succeed",                              |
|  │     "url": "https://...video.mp4"                     |
|  │   }]}}                                                |
|  └─ Status values: pending, processing, succeed, failed  |
|                                                          |
+----------------------------------------------------------+
```

### 5.5 PiAPI Service (Verified Workflow)

**Base URL:** `https://api.piapi.ai/api/v1`

**Authentication:** X-API-Key header

**Supported Task Types:**
- `txt2img` - Text-to-Image (Flux model)
- `img2img` - Image-to-Image / Style Transfer (Flux, with `strength` param)
- `ai_try_on` - Virtual Try-On (Kling AI)
- `background-remove` - Background Removal
- `wan26-img2video` - Image-to-Video
- `wan26-txt2video` - Text-to-Video
- `kontext` - Context-aware editing

**Workflow:**
```
+----------------------------------------------------------+
|                  PIAPI GENERATION FLOW                    |
+----------------------------------------------------------+
|                                                          |
|  Step 1: CREATE TASK                                     |
|  ├─ Endpoint: POST /task                                 |
|  ├─ Headers: X-API-Key: {PIAPI_KEY}                      |
|  ├─ Body: {                                              |
|  │     "task_type": "txt2img",                           |
|  │     "input": {...}                                    |
|  │   }                                                   |
|  └─ Response: {"task_id": "xxx", "status": "pending"}    |
|                                                          |
|  Step 2: CHECK STATUS (POLL)                             |
|  ├─ Endpoint: GET /task/{task_id}                        |
|  └─ Response: {"status": "completed", "output": {...}}   |
|                                                          |
+----------------------------------------------------------+
```

### 5.6 Interior Design Service

**Current Implementation (Free Users - Example Gallery Mode)**:
-   Free users browse pre-generated interior design examples
-   Examples created via Text-to-Image (T2I) generation
-   No actual processing of user-uploaded images
-   Watermarked results, no downloads

**Future Implementation (Paid Users - True I2I Mode)**:
-   **Objective**: Convert user-uploaded floor plans into photorealistic 3D visualizations
-   **Workflow**:
    1. Parse CAD/Floor Plan files into high-contrast sketches
    2. Use **PiAPI I2I/ControlNet** to generate 3D renders from sketches
    3. Apply style refinements via natural language prompts
-   **Benefits**: True transformation vs example browsing

### 5.7 Virtual Try-On with Model Library (NEW)

**Architecture:**
The Virtual Try-On feature uses AI-generated full-body model photos to ensure compatibility with Kling AI's requirements.

```
+------------------------------------------------------------------+
|                    VIRTUAL TRY-ON ARCHITECTURE                    |
+------------------------------------------------------------------+
|                                                                    |
|  MODEL LIBRARY (/static/models/)                                   |
|  ├── female/                                                       |
|  │   ├── female-fullbody-1.png  (AI-generated full-body model)    |
|  │   ├── female-fullbody-2.png                                    |
|  │   └── female-fullbody-3.png                                    |
|  └── male/                                                         |
|      ├── male-fullbody-1.png                                      |
|      ├── male-fullbody-2.png                                      |
|      └── male-fullbody-3.png                                      |
|                                                                    |
|  GENERATION FLOW:                                                  |
|  ┌────────────────────────────────────────────────────────┐       |
|  │  1. generate_model_library()                            │       |
|  │     ├─ Use PiAPI T2I to generate full-body model photos │       |
|  │     ├─ Prompts optimized for Kling AI requirements      │       |
|  │     └─ Store in /static/models/{gender}/                │       |
|  └────────────────────────────────────────────────────────┘       |
|                          │                                         |
|                          ▼                                         |
|  ┌────────────────────────────────────────────────────────┐       |
|  │  2. generate_try_on()                                   │       |
|  │     ├─ Load models from library                         │       |
|  │     ├─ Apply gender restrictions (male skips female)    │       |
|  │     ├─ Convert local files to base64 for API           │       |
|  │     ├─ Call Kling AI Virtual Try-On API                │       |
|  │     └─ Skip on API failure (no T2I fallback)           │       |
|  └────────────────────────────────────────────────────────┘       |
|                                                                    |
+------------------------------------------------------------------+
```

**Model Requirements for Kling AI:**

- Full body shot (head to at least waist visible)
- Clear visibility of upper body/torso
- Neutral pose with arms at sides
- Plain or minimal background
- Simple base clothing (t-shirt or tank top)

**Gender Restrictions:**
- Male models can only wear male/unisex clothing (skip female-only items)
- Female models can wear all clothing (male, female, unisex)
- Each clothing item has a `gender_restriction` field: `"male"`, `"female"`, or `None` (unisex)
- On API failure, the try-on is **skipped** (no T2I fallback to preserve person identity)

**Local File to API Support:**

The PiAPI client automatically converts local files to base64 data URLs:

```python
# piapi_client.py
def _resolve_image_input(self, image_input: str) -> str:
    """Convert local paths to base64 data URLs for PiAPI"""
    if image_input.startswith("/static/") or image_input.startswith("/app/"):
        return self._to_base64_data_url(local_path)
    return image_input  # Remote URL, pass through
```

**CLI Commands:**
```bash
# Generate model library (6 models)
python -m scripts.main_pregenerate --tool model_library --limit 6

# Generate try-on materials (auto-generates models if needed)
python -m scripts.main_pregenerate --tool try_on --limit 20
```

---

### 5.8 Effect / Style Transfer (NEW)

**Architecture:**
The Effect tool applies artistic styles to product images using a two-step pipeline (T2I → I2I) while preserving product identity.

**CRITICAL—Example Correspondence:** We do *not* use a second prompt to generate a "corresponding" image. The example IS the transformation of the SAME image:
1. T2I generates source image from product prompt
2. Effect API (I2I) receives that **existing** image and applies style
3. Result is stored in Material DB with `input_image_url` = T2I output, `result_image_url` = I2I output

The before/after relationship is: same product, different style—linked by the same source.

```
+------------------------------------------------------------------+
|                  EFFECT / STYLE TRANSFER FLOW                     |
+------------------------------------------------------------------+
|                                                                    |
|  Step 1: GENERATE SOURCE IMAGE (PiAPI T2I)                        |
|  ├─ Input: Product prompt (e.g., "bubble milk tea, studio light") |
|  ├─ API: PiAPI Flux txt2img                                       |
|  └─ Output: source_image_url (original product photo)             |
|                                                                    |
|  Step 2: APPLY STYLE (PiAPI I2I) ← uses EXISTING image, not new   |
|  ├─ Input: source_image_url (from Step 1) + style prompt          |
|  ├─ Strength: 0.60-0.70 (preserves product identity)             |
|  ├─ API: PiAPI Flux img2img                                       |
|  └─ Output: styled_image_url (same product, different art style)  |
|                                                                    |
|  IMPORTANT CONSTRAINTS:                                            |
|  ├─ Style prompt ONLY describes art style, NOT the product        |
|  ├─ Strength must stay 0.6-0.7 (>0.8 changes the product)       |
|  └─ Input product = Output product (identity preserved)           |
|                                                                    |
+------------------------------------------------------------------+
```

**Source Images (multi-category):**
- Bubble Tea (珍珠奶茶) — topic: drinks
- Fried Chicken (炸雞排) — topic: snacks
- Fruit Tea (水果茶) — topic: drinks
- Running Sneakers (跑步運動鞋) — topic: apparel
- Smartphone (智慧型手機) — topic: tech
- Skincare Serum (保養精華液) — topic: cosmetics
- Wireless Headphones (無線耳機) — topic: tech
- Modern Sofa (現代沙發) — topic: home

**Available Styles:**

| Style ID | Name | Strength | Description |
|----------|------|----------|-------------|
| anime | Anime (動漫風格) | 0.65 | Anime illustration style |
| ghibli | Ghibli (吉卜力風格) | 0.65 | Studio Ghibli / Miyazaki style |
| cartoon | Cartoon (卡通風格) | 0.60 | Pixar 3D cartoon style |
| oil_painting | Oil Painting (油畫風格) | 0.70 | Van Gogh oil painting style |
| watercolor | Watercolor (水彩風格) | 0.65 | Soft watercolor painting style |

**CLI Commands:**
```bash
# Generate effect/style transfer materials
python -m scripts.main_pregenerate --tool effect --limit 15
```

---

## 6. Payment & Invoice System

### 6.1 Supported Payment Providers

| Provider | Status | Features |
|----------|--------|----------|
| **Paddle** | ✅ Active | Global payments, Tax compliance, Invoicing |
| ECPay | ❌ Removed | Legacy Taiwan-only provider |

### 6.2 Paddle Configuration

```python
# app/core/config.py
PADDLE_API_KEY: str = "your_api_key"
PADDLE_PUBLIC_KEY: str = "your_public_key"
PADDLE_WEBHOOK_SECRET: str = "your_webhook_secret"
```

### 6.3 Paddle Checkout, Cancel & Refund

- **Subscribe:** `POST /subscriptions/subscribe` (plan_id, billing_cycle, payment_method=paddle). When Paddle is configured, returns `checkout_url`; frontend redirects user to Paddle to pay. When Paddle is not configured (mock), subscription is activated immediately.
- **Webhook:** `POST /payments/paddle/webhook` handles `transaction_completed`; activates subscription and allocates credits.
- **Cancel subscription:** `POST /subscriptions/cancel` with body `{ "request_refund": true | false }`.
  - **With refund** (`request_refund: true`): Allowed only within 7 days of subscription start. Backend calls `PaddleService.create_refund()`, marks order as refunded, revokes subscription credits, and sets subscription to cancelled immediately.
  - **Without refund** (`request_refund: false`): Subscription is set to cancelled; access continues until end of billing period, then no renewal. If the order has a Paddle subscription ID, backend notifies Paddle to cancel at next billing period.
- **Refund eligibility:** `GET /subscriptions/status` returns `refund_eligible` (boolean) and `refund_days_remaining` (int). `GET /subscriptions/refund-eligibility` returns `eligible`, `days_remaining`, and optional `reason` for use by the frontend (e.g. to show "Cancel with Refund" only when eligible).

### 6.4 Invoice System flow

1. **Trigger**: `transaction_completed` webhook from Paddle.
2. **Processing**:
    - Webhook handler validates signature.
    - Extracts transaction details.
    - Calls `PaddleService.get_invoice_pdf_url(transaction_id)`.
3. **Delivery**:
    - `EmailService.send_invoice_email()` sends PDF link to user.
    - User downloads PDF via temporary URL (1h expiry).

### 6.5 Plans & pricing display

- `GET /subscriptions/plans` lists active plans with `price_monthly`, `price_yearly`, and features. It ensures default plans exist (e.g. via `ensure_vidgo_plans(db)` or `ensure_default_plans(db)` depending on codebase) so that if the DB has no plans, default plans with prices and credits are seeded before returning.

### 6.6 Email verification (auth)

- **Register:** `POST /auth/register` creates user (is_active=false), sends 6-digit code via email.
- **Verify:** `POST /auth/verify-code` (email, code) validates the code, activates the user, then returns **AuthResponse** (user, access_token, refresh_token, token_type) so the frontend can set the session without a separate login call.


---

## 7. Configuration

### 7.1 Environment Variables

```python
# app/core/config.py

class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "VidGo Gen AI"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/vidgo"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "YOUR_SECRET_KEY_HERE"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # AI Providers
    PIAPI_KEY: str = ""           # PiAPI for Wan API (Primary)
    POLLO_API_KEY: str = ""       # Pollo AI
    A2E_API_KEY: str = ""         # A2E.ai Avatar
    GEMINI_API_KEY: str = ""      # Google Gemini (Backup)

    # Payments (Paddle Only)
    PADDLE_API_KEY: str = ""
    PADDLE_PUBLIC_KEY: str = ""
    PADDLE_WEBHOOK_SECRET: str = ""
    # ECPay (Legacy - Removed)

    # Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # Watermark
    WATERMARK_TEXT: str = "VidGo Demo"
```

---

## 8. Pre-generation Pipeline

### 8.1 Startup Sequence

```
+---------------------------------------------------------------------+
|                        STARTUP SEQUENCE                              |
+---------------------------------------------------------------------+
|                                                                      |
|  ⚠️  NOTE: docker-compose.yml backend service sets entrypoint: []   |
|  to bypass docker_entrypoint.sh for fast dev iteration.             |
|  Use `docker compose --profile init up init-materials` for          |
|  first-time material pre-generation, or set                         |
|  ALLOW_EMPTY_MATERIALS=true SKIP_PREGENERATION=true for dev.        |
|                                                                      |
|  PRODUCTION (Dockerfile ENTRYPOINT — docker_entrypoint.sh):         |
|  1. Wait for Dependencies                                            |
|     - PostgreSQL ready (pg_isready)                                  |
|     - Redis ready (redis-cli ping)                                   |
|                                                                      |
|  2. Database Migrations                                              |
|     - alembic upgrade head                                           |
|                                                                      |
|  3. Seed Service Pricing                                             |
|     - python -m scripts.seed_service_pricing                         |
|                                                                      |
|  4. Material DB Check + Pre-generation (if empty)                    |
|     - python -m scripts.check_material_status                        |
|     - python -m scripts.seed_materials_if_empty --force (if needed) |
|     - Waits up to MATERIAL_CHECK_TIMEOUT (default 10800s / 3h)      |
|                                                                      |
|  5. Start uvicorn                                                    |
|                                                                      |
+---------------------------------------------------------------------+
```

### 8.2 Pre-generation Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SKIP_PREGENERATION` | `false` | Skip AI API calls on startup |
| `PREGENERATION_LIMIT` | `10` | Materials per tool |
| `SKIP_AVATAR` | - | Skip A2E avatar generation |
| `SKIP_VIDEO` | - | Skip Pollo video generation |
| `ALLOW_EMPTY_MATERIALS` | `false` | Allow startup without materials |
| `MIN_TEMPLATES` | `1` | Minimum templates per group |
| `STARTUP_TIMEOUT` | `300` | Validation timeout (seconds) |

**Prompt-Driven Guarantee:**  
All pre-generated examples are created from explicit prompts (product + scene/style prompts), not from static placeholder URLs.

---

## 9. Material Topics Configuration

### 9.1 Topic Registry Overview

**IMPORTANT**: There are two topic systems in the codebase:

| System | File | Status | Description |
|--------|------|--------|-------------|
| **MAPPING System** | `scripts/main_pregenerate.py` | ✅ **ACTIVE** | Used for actual pre-generation, stored in Material.topic |
| Topic Definition System | `app/config/demo_topics.py` | ⚠️ **LEGACY** | Old design, NOT used by pre-generation pipeline |

The **MAPPING System** in `main_pregenerate.py` defines the actual topics stored in the Material DB:
- `SCRIPT_MAPPING` → AI Avatar topics (scripts must clearly sell product/service)
- `BACKGROUND_REMOVAL_MAPPING` → Background Removal topics (food/drink focused)
- `ROOM_REDESIGN_MAPPING` → Room Redesign styles (stored as topic)
- `SHORT_VIDEO_MAPPING` → Short Video topics; **SMB-focused** (bubble tea, fried chicken, small shop, everyday products—not luxury)
- `TRYON_MAPPING` → Try-On clothing categories (with gender restrictions)
- `PATTERN_GENERATE_MAPPING` → Pattern Generate styles
- `EFFECT_MAPPING` → Effect/Style Transfer (source images × art styles)

### 9.2 Tool-Specific Topics (Active Mappings)

```python
# scripts/main_pregenerate.py - ACTUALLY USED

MATERIAL_TOPICS = {
    ToolType.BACKGROUND_REMOVAL: [
        {"topic_id": "drinks", "name_en": "Drinks", "name_zh": "飲料"},
        {"topic_id": "snacks", "name_en": "Snacks", "name_zh": "小吃"},
        {"topic_id": "desserts", "name_en": "Desserts", "name_zh": "甜點"},
        {"topic_id": "meals", "name_en": "Meals", "name_zh": "正餐便當"},
        {"topic_id": "packaging", "name_en": "Packaging", "name_zh": "包裝外帶"},
        {"topic_id": "equipment", "name_en": "Equipment", "name_zh": "設備器材"},
        {"topic_id": "signage", "name_en": "Signage", "name_zh": "招牌菜單"},
        {"topic_id": "ingredients", "name_en": "Ingredients", "name_zh": "食材原料"},
    ],
    ToolType.PRODUCT_SCENE: [
        {"topic_id": "studio", "name_en": "Studio Lighting", "name_zh": "攝影棚"},
        {"topic_id": "nature", "name_en": "Nature Setting", "name_zh": "自然場景"},
        {"topic_id": "luxury", "name_en": "Luxury Setting", "name_zh": "奢華場景"},
        {"topic_id": "minimal", "name_en": "Minimal", "name_zh": "極簡風格"},
        {"topic_id": "lifestyle", "name_en": "Lifestyle", "name_zh": "生活風格"},
        {"topic_id": "urban", "name_en": "Urban", "name_zh": "都市風格"},
        {"topic_id": "seasonal", "name_en": "Seasonal", "name_zh": "季節性"},
        {"topic_id": "holiday", "name_en": "Holiday", "name_zh": "節日"},
    ],
    ToolType.TRY_ON: [
        {"topic_id": "casual", "name_en": "Casual Wear", "name_zh": "休閒服飾"},
        {"topic_id": "formal", "name_en": "Formal Wear", "name_zh": "正式服飾"},
        {"topic_id": "dresses", "name_en": "Dresses", "name_zh": "洋裝"},
        {"topic_id": "sportswear", "name_en": "Sportswear", "name_zh": "運動服"},
        {"topic_id": "outerwear", "name_en": "Outerwear", "name_zh": "外套"},
        {"topic_id": "accessories", "name_en": "Accessories", "name_zh": "配件"},
    ],
    ToolType.ROOM_REDESIGN: [
        {"topic_id": "modern", "name_en": "Modern", "name_zh": "現代風格"},
        {"topic_id": "nordic", "name_en": "Nordic", "name_zh": "北歐風格"},
        {"topic_id": "japanese", "name_en": "Japanese", "name_zh": "日式風格"},
        {"topic_id": "industrial", "name_en": "Industrial", "name_zh": "工業風格"},
        {"topic_id": "minimalist", "name_en": "Minimalist", "name_zh": "極簡風格"},
        {"topic_id": "luxury", "name_en": "Luxury", "name_zh": "奢華風格"},
    ],
    ToolType.SHORT_VIDEO: [
        {"topic_id": "product_showcase", "name_en": "Product Showcase", "name_zh": "產品展示"},
        {"topic_id": "brand_intro", "name_en": "Brand Introduction", "name_zh": "品牌介紹"},
        {"topic_id": "tutorial", "name_en": "Tutorial", "name_zh": "教學"},
        {"topic_id": "promo", "name_en": "Promotion", "name_zh": "促銷"},
    ],
    ToolType.AI_AVATAR: [
        {"topic_id": "spokesperson", "name_en": "Spokesperson", "name_zh": "品牌代言人"},
        {"topic_id": "product_intro", "name_en": "Product Introduction", "name_zh": "產品介紹"},
        {"topic_id": "customer_service", "name_en": "Customer Service", "name_zh": "客服助理"},
        {"topic_id": "social_media", "name_en": "Social Media", "name_zh": "社群媒體"},
    ],
    ToolType.PATTERN_GENERATE: [
        {"topic_id": "seamless", "name_en": "Seamless Pattern", "name_zh": "無縫圖案"},
        {"topic_id": "floral", "name_en": "Floral Pattern", "name_zh": "花卉圖案"},
        {"topic_id": "geometric", "name_en": "Geometric Pattern", "name_zh": "幾何圖案"},
        {"topic_id": "abstract", "name_en": "Abstract Pattern", "name_zh": "抽象圖案"},
        {"topic_id": "traditional", "name_en": "Traditional Pattern", "name_zh": "傳統紋樣"},
    ],
    ToolType.EFFECT: [
        {"topic_id": "anime", "name_en": "Anime", "name_zh": "動漫風格"},
        {"topic_id": "ghibli", "name_en": "Ghibli", "name_zh": "吉卜力風格"},
        {"topic_id": "cartoon", "name_en": "Cartoon", "name_zh": "卡通風格"},
        {"topic_id": "oil_painting", "name_en": "Oil Painting", "name_zh": "油畫風格"},
        {"topic_id": "watercolor", "name_en": "Watercolor", "name_zh": "水彩風格"},
    ],
}
```

### 9.3 Topic Registry API Endpoint

```python
# app/api/v1/demo.py

@router.get("/topics/{tool_type}")
async def get_tool_topics(tool_type: str):
    """
    Get valid topics for a specific tool type.
    
    Returns:
        {
            "success": true,
            "tool_type": "ai_avatar",
            "topics": [
                {"id": "spokesperson", "name_en": "Spokesperson", "name_zh": "品牌代言人"},
                ...
            ]
        }
    """
    topics = get_topics_for_tool(tool_type)
    return {"success": True, "tool_type": tool_type, "topics": topics}
```

### 9.4 Landing Page Topics (LANDING_EXAMPLES)

Landing page materials use **separate topics** from MATERIAL_TOPICS, stored in `material_generator.py`:

```python
# app/services/material_generator.py

LANDING_TOPICS = ["ecommerce", "social", "brand", "app", "promo", "service"]

LANDING_EXAMPLES = {
    "ecommerce": {
        "name_en": "E-commerce",
        "name_zh": "電商廣告",
        "examples": [...]  # 6 examples with prompt_en, prompt_zh, avatar_en, avatar_zh
    },
    "social": {
        "name_en": "Social Media",
        "name_zh": "社群媒體",
        "examples": [...]
    },
    "brand": {
        "name_en": "Brand Promotion",
        "name_zh": "品牌推廣",
        "examples": [...]
    },
    "app": {
        "name_en": "App Promotion",
        "name_zh": "應用推廣",
        "examples": [...]
    },
    "promo": {
        "name_en": "Promotional",
        "name_zh": "活動促銷",
        "examples": [...]
    },
    "service": {
        "name_en": "Service Introduction",
        "name_zh": "服務介紹",
        "examples": [...]
    }
}
```

**Important**: Landing materials are stored with `tool_type=SHORT_VIDEO` or `tool_type=AI_AVATAR` but use landing-specific topics (ecommerce, social, brand, app, promo, service) instead of `TOOL_TOPICS` in `topic_registry.py`.

### 9.5 Legacy Topic System (demo_topics.py)

⚠️ **WARNING**: The `app/config/demo_topics.py` file contains a legacy topic system that is **NOT** used by the pre-generation pipeline.

```python
# app/config/demo_topics.py - LEGACY, DO NOT USE

class TopicCategory(str, Enum):
    PRODUCT_VIDEO = "product_video"      # NOT USED
    INTERIOR_DESIGN = "interior_design"  # NOT USED
    STYLE_TRANSFER = "style_transfer"    # NOT USED
    AVATAR = "avatar"                    # NOT USED
    T2I_SHOWCASE = "t2i_showcase"        # NOT USED

# These topics are NOT stored in Material DB:
# - luxury_watch, perfume_bottle, sneaker_product (legacy)
# - modern_living, anime_landscape (legacy)
# - ecommerce_pitch_en, product_demo_zh (legacy)
```

If you see topics like `luxury_watch` or `ecommerce_pitch_en` in the frontend, they will NOT match any materials in the database.

---

## 10. Landing Material Generation Flow

### 10.1 Generation Pipeline

```
+-----------------------------------------------------------------------------+
|                    LANDING MATERIAL GENERATION FLOW                          |
+-----------------------------------------------------------------------------+
|                                                                              |
|  For each topic in LANDING_EXAMPLES (ecommerce, social, brand, app, promo,  |
|  service):                                                                   |
|                                                                              |
|    For each example (6 per topic):                                          |
|                                                                              |
|      1. GENERATE SOURCE IMAGE (PiAPI T2I)                                   |
|         ├─ Input: prompt_zh (Chinese prompt for product image)              |
|         ├─ API: PiAPI Flux model                                            |
|         └─ Output: source_image_url                                         |
|                                                                              |
|      2. GENERATE VIDEO (Pollo AI I2V)                                       |
|         ├─ Input: source_image_url + prompt_zh                              |
|         ├─ API: Pollo Pixverse v4.5                                         |
|         ├─ Length: `SHORT_VIDEO_LENGTH` (default 8s)                        |
|         ├─ Output: video_url                                                |
|         └─ Store as: Material(tool_type=SHORT_VIDEO, topic=<landing_topic>) |
|                                                                              |
|      3. GENERATE AVATAR - English (A2E.ai)                                  |
|         ├─ Input: avatar_image_url + avatar_en script                       |
|         ├─ API: A2E.ai Lip-sync                                             |
|         ├─ Output: avatar_video_url                                         |
|         └─ Store as: Material(tool_type=AI_AVATAR, topic=<landing_topic>,   |
|                               language="en")                                 |
|                                                                              |
|      4. GENERATE AVATAR - Chinese (A2E.ai)                                  |
|         ├─ Input: avatar_image_url + avatar_zh script                       |
|         ├─ API: A2E.ai Lip-sync                                             |
|         ├─ Output: avatar_video_url                                         |
|         └─ Store as: Material(tool_type=AI_AVATAR, topic=<landing_topic>,   |
|                               language="zh-TW")                              |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### 10.2 Material Check Logic

```python
# app/services/material_generator.py

async def check_all_materials(session):
    # Landing topics from registry
    landing_topics = get_landing_topic_ids()

    # Per-topic counts (not just totals)
    video_counts = count_by_topic(SHORT_VIDEO, landing_topics)
    avatar_counts = count_by_topic(AI_AVATAR, landing_topics)

    # Prompt validation
    prompt_missing = count_missing_prompts(SHORT_VIDEO, landing_topics) + count_missing_prompts(AI_AVATAR, landing_topics)
    prompt_zh_missing = count_missing_prompt_zh(AI_AVATAR, landing_topics)

    ready = (
        all(c >= 6 for c in video_counts.values()) and
        all(c >= 12 for c in avatar_counts.values()) and
        prompt_missing == 0 and
        prompt_zh_missing == 0
    )
```

### 10.3 Expected Material Counts

| Category | Tool Type | Topics | Min Count | Expected Total |
|----------|-----------|--------|-----------|----------------|
| landing (video) | SHORT_VIDEO | ecommerce, social, brand, app, promo, service | 6 | 36 (6 topics × 6 examples) |
| landing (avatar) | AI_AVATAR | ecommerce, social, brand, app, promo, service | 6 | 72 (6 topics × 6 examples × 2 languages) |
| bg_removal | BACKGROUND_REMOVAL | drinks, snacks, desserts, meals, packaging, equipment, signage, ingredients | 10 | 80+ |
| product | PRODUCT_SCENE | studio, nature, luxury, minimal, lifestyle, urban, seasonal, holiday | 6 | 40 |
| video | SHORT_VIDEO | product_showcase, brand_intro, tutorial, promo | 5 | 10 |
| avatar | AI_AVATAR | spokesperson, product_intro, customer_service, social_media | 6 | 16 |
| effect | EFFECT | anime, ghibli, cartoon, oil_painting, watercolor | 5 | 15 (3 sources × 5 styles) |

### 10.4 Generation Command

```bash
# Generate landing materials only
docker-compose exec backend python -c "
import asyncio
from app.services.material_generator import get_material_generator
from app.core.database import AsyncSessionLocal

async def generate():
    generator = get_material_generator()
    async with AsyncSessionLocal() as session:
        await generator._generate_landing_materials(session)

asyncio.run(generate())
"

# Or use the main pregenerate script
python -m scripts.main_pregenerate --tool short_video --limit 36
python -m scripts.main_pregenerate --tool ai_avatar --limit 72
```

---

## 11. Docker Services

```yaml
# docker-compose.yml services

services:
  postgres:      # PostgreSQL 15 - Primary database
  redis:         # Redis 7 - Cache & task queue
  mailpit:       # Email testing (dev only)
  backend:       # FastAPI application (port 8001)
  worker:        # ARQ background worker
  init-materials: # Initial pre-generation (runs once)
  frontend:      # Vue 3 frontend (port 8501)
```

---

## 12. API Testing Commands

### 12.1 Test Individual Providers

```bash
# Test PiAPI connection
docker-compose exec backend python -c "
import asyncio
from app.providers.piapi_provider import PiAPIProvider

async def test():
    p = PiAPIProvider()
    print(f'API Key set: {bool(p.api_key)}')
    result = await p.health_check()
    print(f'Health check: {result}')

asyncio.run(test())
"

# Test Pollo AI connection
docker-compose exec backend python -c "
from app.services.pollo_ai import get_pollo_client

p = get_pollo_client()
print(f'API Key set: {bool(p.api_key)}')
"

# Test A2E.ai connection
docker-compose exec backend python -c "
import asyncio
from app.services.a2e_service import get_a2e_service

async def test():
    a = get_a2e_service()
    result = await a.test_connection()
    print(result)

asyncio.run(test())
"
```

### 12.2 Test Material Generation

```bash
# Check existing materials
docker-compose exec backend python -c "
import asyncio
from app.core.database import AsyncSessionLocal
from app.services.material_generator import get_material_generator

async def check():
    gen = get_material_generator()
    async with AsyncSessionLocal() as session:
        result = await gen.check_all_materials(session)
        print(result)

asyncio.run(check())
"

# Generate missing materials (dry run)
docker-compose exec backend python -m scripts.main_pregenerate --dry-run

# Generate specific tool materials
docker-compose exec backend python -m scripts.main_pregenerate --tool ai_avatar --limit 1
```

### 12.3 Full Stack Test Endpoints

```bash
# Backend health check
curl http://localhost:8001/health

# API docs
open http://localhost:8001/docs

# Frontend
open http://localhost:8501

# Landing page materials API
curl http://localhost:8001/api/v1/landing/materials

# Demo presets API
curl http://localhost:8001/api/v1/demo/presets/short_video
```

### 12.4 Homepage Tool Hub (Frontend Integration)

The landing page (`frontend-vue/src/views/LandingPage.vue`) is built as a **tool hub** layout (sidebar categories + hero prompt + tool grid + showcases) inspired by Douhui AI, but **only surfaces features backed by existing APIs**:

- **Featured tools**: background_removal, product_scene, try_on, room_redesign, short_video, ai_avatar, pattern_generate, effect
- **Data source**: `/api/v1/landing/features` → capability highlights (tool-aligned)
- **Data source**: `/api/v1/demo/landing/works` → works gallery (product_scene, effect, background_removal, short_video, ai_avatar) with `video_url` field for video items
- **Data source**: `/api/v1/demo/landing/examples` → short-video landing examples (fallback to `/api/v1/landing/examples`)
- **Data source**: `/api/v1/demo/presets/ai_avatar` → avatar showcase presets (9 items, 3×3 grid)

### 12.5 Landing Works Gallery (`/demo/landing/works`)

The works gallery endpoint returns a mix of image and video materials for the homepage:

**Tool types included:** `product_scene`, `effect`, `background_removal`, `short_video`, `ai_avatar`

**Response fields per item:**
| Field | Description |
|-------|-------------|
| `id` | Material UUID |
| `tool_type` | One of the 5 tool types above |
| `tool_name` | Localized tool display name |
| `route` | Frontend route for the tool page |
| `thumb` | Thumbnail image URL (result_watermarked_url or input_image_url) |
| `video_url` | Video URL (only for short_video and ai_avatar items, null otherwise) |
| `input_image_url` | Original input image (for effect before/after) |
| `result_image_url` | Result image URL |
| `prompt` | Truncated prompt text |
| `topic` | Material topic |

**Frontend rendering:**
- Image items (product_scene, effect, background_removal): display as `<img>` with hover effects
- Video items (short_video, ai_avatar): display with play icon overlay, `<video>` hover-to-play

---

<<<<<<< HEAD
---

## 13. New Features (v5.0)

### 13.1 Subscriber Upload & Real-API Generation

```
POST /api/v1/uploads/material
  ├─ Auth: Bearer (subscriber required)
  ├─ Body: multipart/form-data
  │   ├─ tool_type: str
  │   ├─ model_id: str (default = "default")
  │   ├─ prompt: str (optional)
  │   └─ file: binary (JPEG/PNG/WebP, max 20 MB)
  ├─ Credits deducted: TOOL_BASE_CREDITS[tool_type] × model_multiplier
  └─ Response: { upload_id, status, credits_used }

GET /api/v1/uploads/{upload_id}
  └─ Returns status + result_url / result_video_url (no watermark)

GET /api/v1/uploads/{upload_id}/download
  └─ Streaming download of result file (no watermark, subscribers only)

GET /api/v1/uploads/models/{tool_type}
  └─ List available models with credit costs for a tool
```

### 13.2 Referral System

```
GET  /api/v1/referrals/code        → { referral_code, referral_url }
GET  /api/v1/referrals/stats       → { referral_count, credits_earned, referred_by }
POST /api/v1/referrals/apply       → Apply a code; earn welcome credits
GET  /api/v1/referrals/leaderboard → Top 10 referrers (public)
```

**Credit awards:**
- Referrer: `REFERRAL_BONUS_CREDITS` (default 50) per successful referral
- New user: `REFERRAL_WELCOME_CREDITS` (default 20) when registering via referral

### 13.3 Subscriber Download from Preset Gallery

`POST /api/v1/demo/use-preset` now accepts optional Bearer token:
- **Subscriber:** returns `result_url` (full quality) + `can_download=true`
- **Free user / anonymous:** returns `result_watermarked_url` + `can_download=false`

`GET /api/v1/demo/download/{material_id}` redirects to full-quality URL (subscribers only).

---

*Document Version: 5.0*
*Last Updated: February 21, 2026*
*Mode: Dual-Mode — Preset-Only (free) + Real-API (subscribers)*
=======
## 13. Paid User Feature Readiness

| Feature | Status | Endpoint | Provider | Notes |
|---------|--------|----------|----------|-------|
| Text-to-Image (T2I) | Implemented | `POST /api/v1/tools/generate-image` | PiAPI Flux | — |
| Image-to-Video (I2V) | Implemented | `POST /api/v1/tools/generate-video` | PiAPI Wan / Pollo | — |
| Text-to-Video (T2V) | Implemented | `POST /api/v1/generate/text-to-video` | PiAPI Wan / Pollo | — |
| AI Avatar | Implemented | `POST /api/v1/tools/avatar` | A2E.ai | — |
| Interior Redesign | Implemented | `POST /api/v1/interior/redesign` | PiAPI Wan Doodle | — |
| Background Removal | Implemented | `POST /api/v1/tools/remove-background` | PiAPI | — |
| Effect/Style Transfer | Implemented | `POST /api/v1/tools/effect` | PiAPI Flux I2I | — |
| **I2I Transformations** | **Implemented** | `POST /api/v1/tools/image-transform` | PiAPI Flux (flux1-schnell) | New: true image-to-image |
| **Room Redesign 3D** | **Implemented** | `POST /api/v1/interior/3d-model` | PiAPI Trellis | New: GLB 3D model from 2D image |
| Virtual Try-On | Implemented | `POST /api/v1/tools/try-on` | PiAPI (Kling AI) | — |
| Pattern Generate | Implemented | `POST /api/v1/tools/pattern` | PiAPI Flux | — |

---

*Document Version: 5.1*
*Last Updated: February 18, 2026*
*Mode: Hybrid (Free Trial + Paid Generation)*
>>>>>>> origin/claude/add-free-trial-mode-B21Bl
*Target: SMB (small businesses selling everyday products/services)*
