# VidGo AI Platform - Backend Architecture

**Version:** 4.3
**Last Updated:** January 18, 2026
**Framework:** FastAPI + Python 3.12
**Database:** PostgreSQL + Redis
**Mode:** Preset-Only (Material DB Lookup, No Runtime API Calls)

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
|  |  |  | - I2V             |  | - T2V (Pollo)     |  | - Lip-sync TTS    |  |  | |
|  |  |  | - Interior        |  |                   |  |                   |  |  | |
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
│   │   └── demo_topics.py           # Demo topic configuration
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
│   ├── main_pregenerate.py          # Main pre-generation pipeline (7 tools)
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
| `/auth` | auth | User authentication (login, register, verify) |
| `/payments` | payments | Payment webhooks (ECPay, Paddle) |
| `/subscriptions` | subscriptions | Subscription management |
| `/demo` | demo | Demo/preset endpoints |
| `/plans` | plans | Subscription plan details |
| `/promotions` | promotions | Promotional codes |
| `/credits` | credits | Credit balance and transactions |
| `/effects` | effects | Video effects |
| `/generate` | generation | Content generation |
| `/landing` | landing | Landing page data |
| `/quota` | quota | Usage quota management |
| `/tools` | tools | Tool-specific operations |
| `/admin` | admin | Admin dashboard |
| `/session` | session | Session management |
| `/interior` | interior | Interior design |
| `/workflow` | workflow | Workflow management |
| `/prompts` | prompts | Prompt templates |

---

## 4. Database Models

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
    """7 Core Tools"""
    BACKGROUND_REMOVAL = "background_removal"
    PRODUCT_SCENE = "product_scene"
    TRY_ON = "try_on"
    ROOM_REDESIGN = "room_redesign"
    SHORT_VIDEO = "short_video"
    AI_AVATAR = "ai_avatar"
    PATTERN_GENERATE = "pattern_generate"  # NEW: Seamless pattern generation

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
    - tool_type: One of 6 core tools
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

---

## 5. AI Provider Integration

### 5.1 Provider Summary

| Provider | API | Purpose | Cost | Env Variable |
|----------|-----|---------|------|--------------|
| PiAPI | Wan API | T2I, I2V, Interior Design | Medium | `PIAPI_KEY` |
| Pollo AI | Pixverse, Kling, Luma | I2V, T2V | Medium | `POLLO_API_KEY` |
| A2E.ai | Lip-sync + TTS | Avatar Video | Medium | `A2E_API_KEY`, `A2E_DEFAULT_CREATOR_ID` |
| Gemini | Generative AI | Moderation, Backup Image | Low | `GEMINI_API_KEY` |

### 5.2 Provider Router

```python
# app/providers/provider_router.py

class ProviderRouter:
    """
    Smart routing between AI providers with fallback.

    Routing Strategy:
    - T2I: PiAPI Wan (primary) -> Gemini (backup)
    - I2V: Pollo AI -> PiAPI Wan
    - T2V: Pollo AI -> PiAPI Wan
    - Avatar: A2E.ai (no backup)
    - Interior: PiAPI Wan -> Gemini
    """

    ROUTING_CONFIG = {
        "text_to_image": {"primary": "piapi", "backup": "gemini"},
        "image_to_video": {"primary": "pollo", "backup": "piapi"},
        "text_to_video": {"primary": "pollo", "backup": "piapi"},
        "avatar": {"primary": "a2e", "backup": None},
        "interior": {"primary": "piapi", "backup": "gemini"},
    }
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
- `img2img` - Image-to-Image
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
|  │     ├─ Convert local files to base64 for API           │       |
|  │     ├─ Call Kling AI Virtual Try-On API                │       |
|  │     └─ Fallback to T2I if API fails                    │       |
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

## 6. Payment Integration

### 6.1 Supported Payment Providers

| Provider | Region | Features |
|----------|--------|----------|
| ECPay | Taiwan | Credit card, ATM, CVS |
| Paddle | International | Credit card, PayPal |

### 6.2 ECPay Configuration

```python
# app/core/config.py
ECPAY_MERCHANT_ID: str = ""
ECPAY_HASH_KEY: str = ""
ECPAY_HASH_IV: str = ""
ECPAY_PAYMENT_URL: str = "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"
```

### 6.3 Paddle Configuration

```python
PADDLE_API_KEY: str = ""
PADDLE_PUBLIC_KEY: str = ""
```

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

    # Payments
    ECPAY_MERCHANT_ID: str = ""
    ECPAY_HASH_KEY: str = ""
    ECPAY_HASH_IV: str = ""
    PADDLE_API_KEY: str = ""

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
|  1. Wait for Dependencies                                            |
|     - PostgreSQL ready (pg_isready)                                  |
|     - Redis ready (redis-cli ping)                                   |
|                                                                      |
|  2. Database Migrations                                              |
|     - alembic upgrade head                                           |
|                                                                      |
|  3. Pre-generation Pipeline (if not skipped)                         |
|     - Validate API keys                                              |
|     - Generate materials for each tool type                          |
|     - Store with lookup_hash for O(1) access                         |
|                                                                      |
|  4. Startup Validation                                               |
|     - Check minimum materials per tool                               |
|     - FAIL if requirements not met (unless dev mode)                 |
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

---

## 9. Material Topics Configuration

### 9.1 Tool-Specific Topics (MATERIAL_TOPICS)

```python
# app/models/material.py

MATERIAL_TOPICS = {
    ToolType.BACKGROUND_REMOVAL: [
        {"topic_id": "electronics", "name_en": "Electronics", "name_zh": "電子產品"},
        {"topic_id": "fashion", "name_en": "Fashion", "name_zh": "時尚服飾"},
        {"topic_id": "jewelry", "name_en": "Jewelry", "name_zh": "珠寶首飾"},
        {"topic_id": "food", "name_en": "Food & Beverage", "name_zh": "食品飲料"},
        {"topic_id": "cosmetics", "name_en": "Cosmetics", "name_zh": "化妝品"},
        {"topic_id": "furniture", "name_en": "Furniture", "name_zh": "家具"},
        {"topic_id": "toys", "name_en": "Toys", "name_zh": "玩具"},
        {"topic_id": "sports", "name_en": "Sports", "name_zh": "運動用品"},
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
        {"topic_id": "brand_story", "name_en": "Brand Story", "name_zh": "品牌故事"},
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
}
```

### 9.2 Landing Page Topics (LANDING_EXAMPLES)

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

**Important**: Landing materials are stored with `tool_type=SHORT_VIDEO` or `tool_type=AI_AVATAR` but use landing-specific topics (ecommerce, social, brand, app, promo, service) instead of MATERIAL_TOPICS.

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

async def check_materials_exist(session, category, min_count):
    if category == 'landing':
        # CRITICAL: Must use LANDING_TOPICS, NOT MATERIAL_TOPICS
        landing_topics = ["ecommerce", "social", "brand", "app", "promo", "service"]

        # Check SHORT_VIDEO with landing topics
        video_count = count(Material.tool_type == SHORT_VIDEO AND topic IN landing_topics)

        # Check AI_AVATAR with landing topics
        avatar_count = count(Material.tool_type == AI_AVATAR AND topic IN landing_topics)

        return video_count >= min_count AND avatar_count >= min_count
```

### 10.3 Expected Material Counts

| Category | Tool Type | Topics | Min Count | Expected Total |
|----------|-----------|--------|-----------|----------------|
| landing (video) | SHORT_VIDEO | ecommerce, social, brand, app, promo, service | 6 | 36 (6 topics × 6 examples) |
| landing (avatar) | AI_AVATAR | ecommerce, social, brand, app, promo, service | 6 | 72 (6 topics × 6 examples × 2 languages) |
| pattern | BACKGROUND_REMOVAL | electronics, fashion, jewelry, food, cosmetics, furniture, toys, sports | 10 | 80+ |
| product | PRODUCT_SCENE | studio, nature, luxury, minimal, lifestyle, urban, seasonal, holiday | 6 | 40 |
| video | SHORT_VIDEO | product_showcase, brand_story, tutorial, promo | 5 | 10 |
| avatar | AI_AVATAR | spokesperson, product_intro, customer_service, social_media | 6 | 16 |

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

---

*Document Version: 4.2*
*Last Updated: January 18, 2026*
*Mode: Preset-Only (Material DB Lookup, No Runtime API Calls)*
