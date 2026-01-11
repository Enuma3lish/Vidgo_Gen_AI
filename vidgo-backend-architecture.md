# VidGo AI Platform - Backend Architecture

**Version:** 4.0
**Last Updated:** January 12, 2026
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
│   ├── pregenerate.py               # Pre-generation pipeline
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
    """6 Core Tools"""
    BACKGROUND_REMOVAL = "background_removal"
    PRODUCT_SCENE = "product_scene"
    TRY_ON = "try_on"
    ROOM_REDESIGN = "room_redesign"
    SHORT_VIDEO = "short_video"
    AI_AVATAR = "ai_avatar"

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

| Provider | API | Purpose | Cost |
|----------|-----|---------|------|
| PiAPI | Wan API | T2I, I2V, Interior Design | Medium |
| Pollo AI | Pixverse, Pollo | I2V, T2V | Medium |
| A2E.ai | Lip-sync | Avatar Video with TTS | Medium |
| Gemini | Generative AI | Moderation, Backup Image | Low |

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

### 5.3 Interior Design Service (2D-to-3D)
**Objective**: Convert technical 2D files (CAD/Floor Plans) into photorealistic 3D visualizations.

**Workflow Steps**:
1.  **File Parsing**: Convert technical 2D files (CAD/Floor Plans) into high-contrast image sketches using a specialized parser.
2.  **Sketch-to-Image**: Pass the sketch to **PiAPI Trellis (Image-to-3D)** or **Wan 2.6 (Image-to-Image)** to generate photorealistic 3D visualizations.
3.  **Refinement**: Apply natural language prompts to customize furniture, lighting, and materials.

**Demo/Preset Mode Strategy**:
-   **Pre-generation**: Admin pre-generates high-quality "Result" images using this workflow and stores them in `Material DB`.
-   **Visitor Access**: Unsubscribed users can *only* browse these pre-generated examples.
-   **Restrictions**: API calls are blocked. Downloads are disabled. Watermarked results are shown by default.

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

```python
# app/models/material.py

MATERIAL_TOPICS = {
    ToolType.BACKGROUND_REMOVAL: [
        {"topic_id": "electronics", "name_en": "Electronics", "name_zh": "電子產品"},
        {"topic_id": "fashion", "name_en": "Fashion", "name_zh": "時尚服飾"},
        {"topic_id": "jewelry", "name_en": "Jewelry", "name_zh": "珠寶首飾"},
        {"topic_id": "food", "name_en": "Food & Beverage", "name_zh": "食品飲料"},
        {"topic_id": "cosmetics", "name_en": "Cosmetics", "name_zh": "化妝品"},
        # ... more topics
    ],
    ToolType.PRODUCT_SCENE: [
        {"topic_id": "studio", "name_en": "Studio Lighting", "name_zh": "攝影棚"},
        {"topic_id": "nature", "name_en": "Nature Setting", "name_zh": "自然場景"},
        {"topic_id": "luxury", "name_en": "Luxury Setting", "name_zh": "奢華場景"},
        # ... more topics
    ],
    ToolType.TRY_ON: [
        {"topic_id": "casual", "name_en": "Casual Wear", "name_zh": "休閒服飾"},
        {"topic_id": "formal", "name_en": "Formal Wear", "name_zh": "正式服飾"},
        # ... more topics
    ],
    ToolType.ROOM_REDESIGN: [
        {"topic_id": "modern", "name_en": "Modern", "name_zh": "現代風格"},
        {"topic_id": "nordic", "name_en": "Nordic", "name_zh": "北歐風格"},
        {"topic_id": "japanese", "name_en": "Japanese", "name_zh": "日式風格"},
        # ... more topics
    ],
    ToolType.SHORT_VIDEO: [
        {"topic_id": "product_showcase", "name_en": "Product Showcase", "name_zh": "產品展示"},
        {"topic_id": "brand_story", "name_en": "Brand Story", "name_zh": "品牌故事"},
        # ... more topics
    ],
    ToolType.AI_AVATAR: [
        {"topic_id": "spokesperson", "name_en": "Spokesperson", "name_zh": "品牌代言人"},
        {"topic_id": "product_intro", "name_en": "Product Introduction", "name_zh": "產品介紹"},
        {"topic_id": "customer_service", "name_en": "Customer Service", "name_zh": "客服助理"},
        {"topic_id": "social_media", "name_en": "Social Media", "name_zh": "社群媒體"},
    ],
}
```

---

## 10. Docker Services

```yaml
# docker-compose.yml services

services:
  postgres:      # PostgreSQL 15 - Primary database
  redis:         # Redis 7 - Cache & task queue
  mailpit:       # Email testing (dev only)
  backend:       # FastAPI application
  worker:        # ARQ background worker
  init-materials: # Initial pre-generation (runs once)
  frontend:      # Vue 3 frontend
```

---

*Document Version: 4.0*
*Last Updated: January 12, 2026*
*Mode: Preset-Only (Material DB Lookup, No Runtime API Calls)*
