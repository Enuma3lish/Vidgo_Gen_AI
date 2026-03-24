# VidGo Gen AI Platform

**AI-Powered Visual Content Generation for E-commerce**

VidGo is a comprehensive AI platform that enables e-commerce businesses to create professional visual content using cutting-edge generative AI technology. The platform operates with a **two-tier model**: free users browse pre-generated examples (PRESET mode), while paid subscribers access real-time AI generation with full-quality output.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Core Features](#core-features)
- [Subscriber Features](#subscriber-features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Docker Services](#docker-services)
- [Development](#development)
- [Security & Anti-Abuse](#security--anti-abuse)
- [Documentation](#documentation)

---

## Architecture Overview

```
                    +------------------+
                    |    Frontend      |
                    |    (Vue 3)       |
                    |   Port: 8501     |
                    +--------+---------+
                             |
                             | HTTP/WebSocket
                             v
                    +------------------+
                    |    Backend       |
                    |   (FastAPI)      |
                    |   Port: 8001     |
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                   |                   |
         v                   v                   v
+----------------+  +----------------+  +----------------+
|   PostgreSQL   |  |     Redis      |  |  AI Services   |
|  (Database)    |  |  (Cache/Queue) |  |  (External)    |
|  Port: 5432    |  |  Port: 6379    |  |                |
+----------------+  +----------------+  +----------------+
                                               |
                    +--------------------------+
                    |          |               |
         +-------------+  +---------------+
         |    PiAPI     |  | Google Gemini  |
         | ALL generation|  | - Backup for    |
         | T2I,I2I,I2V  |  |   image tasks   |
         | T2V,V2V,Avatar|  | - Moderation    |
         | Try-On,BG Rem |  | - Pre-gen input |
         | 3D, Effects   |  |   materials     |
         | (primary)     |  +---------------+
         +-------------+
```

### Dual-Mode Architecture

VidGo supports two modes depending on user tier:

| Mode | Who | Experience |
|------|-----|------------|
| **PRESET-ONLY** | Free / trial users | Browse pre-generated watermarked gallery; instant results, no API costs |
| **REAL-API** | Subscribers | Upload own materials, call live AI APIs, choose AI model, download without watermark |

### PRESET-ONLY Mode (Free Users)
1. **No Runtime API Calls**: All demo content is pre-generated before service starts
2. **Instant Experience**: Users see results immediately without waiting
3. **Watermarked Results**: All demo outputs have watermarks; downloads require subscription

### REAL-API Mode (Subscribers)
1. **Custom Upload**: Upload own images for processing
2. **Model Selection**: Choose from multiple AI models (better models cost more credits)
3. **No Watermarks**: Full-quality results available for download
4. **Credit System**: Credits deducted per generation; better models cost more

### Paid Tier (Real-Time Generation)

Subscribers receive real-time AI generation with:

1. **Full Resolution**: 1080P output (vs 720P for free tier)
2. **No Watermarks**: Clean output with full download access
3. **Credit System**: Free tier 20-35 pts vs Paid tier 80-120 pts per generation
4. **Registration Bonus**: 40 credits (30-day expiry) for new users to trial paid features
5. **Custom Uploads**: Upload and process custom images across all tools

---

## Core Features

### 10 Core AI Tools

| Tool | Description | Engine |
|------|-------------|--------|
| **Background Removal** | Remove backgrounds from product images | AI Engine |
| **Product Scene** | Product Photography Inspiration Gallery | AI Image Engine |
| **Virtual Try-On** | Fashion Model Showcase | AI Try-On Engine |
| **Room Redesign** | Interior Design Example Gallery | AI Image Engine |
| **Short Video** | Image-to-video, Text-to-video | AI Video Engine |
| **AI Avatar** | Talking avatar with lip-sync TTS | AI Avatar Engine |
| **Image Effects** | Artistic style transfer | AI Style Engine |
| **Pattern Design** | Seamless pattern generation | AI Image Engine |
| **I2I Transform** | Image-to-image style transfer | AI Style Engine |
| **Room 3D Model** | Generate 3D models from room images | AI 3D Engine |

### Inspiration Gallery

The **Inspiration Gallery** (`/gallery`) provides a comprehensive showcase of AI-generated examples from real businesses, following the piapi.ai style while maintaining VidGo's design language:

- **Search & Filter**: Search by keywords, filter by industry (Food & Beverage, Fashion, E-commerce, etc.) and tool type
- **Freemium Access**: Free users can browse and try pre-generated examples; subscribers can upload custom materials
- **Industry Targeting**: Specifically designed for small businesses and personal companies
- **Instant Results**: All examples are pre-generated from the Material DB for instant viewing
- **Try This Example**: Click any example to navigate to the corresponding tool with the preset selected

---

## User Role Matrix

VidGo supports **3-tier user system** with distinct capabilities:

| Feature | Visitor (Guest) | Free Registered | Paid Subscriber | Admin |
|---------|----------------|-----------------|-----------------|-------|
| Browse landing page | ✅ | ✅ | ✅ | ✅ |
| Demo tools (preset, DB results) | ✅ (limit 2) | ✅ (limit 2) | ✅ | ✅ |
| Watermarked results | ✅ | ✅ | ❌ (clean) | N/A |
| Download results | ❌ | ❌ | ✅ | ✅ |
| Share to social media | ❌ | ❌ | ✅ | ❌ |
| Upload own materials | ❌ | ❌ | ✅ | ❌ |
| Real AI API generation | ❌ | ❌ | ✅ | ❌ |
| Promotion code (own) | ❌ | ❌ | ✅ (auto-issued) | Can create special ones |
| Use others' promo codes | ❌ | ✅ | ✅ | N/A |
| Work repo (7-day retention) | ❌ | ❌ | ✅ | N/A |
| View API analytics | ❌ | ❌ | ❌ | ✅ |
| Manage users/credits | ❌ | ❌ | ❌ | ✅ |
| Create special promo codes | ❌ | ❌ | ❌ | ✅ |

## Subscriber Features

### Custom Material Upload
Subscribers can upload their own product images and trigger real AI API calls:
- Supported tools: All 10 tools
- Supported formats: JPEG, PNG, WebP (max 20 MB)
- Results returned without watermarks
- Results downloadable via `/api/v1/uploads/{id}/download`

### AI Model Selection
Paid users can choose from multiple AI models per tool:

| Model | Credit Multiplier | Best For |
|-------|-------------------|----------|
| Standard (default) | 1× | Quick, everyday use |
| Pixverse v5 | 1.5× | Creative video animations |
| Kling v2 | 2× | High-quality video / try-on |
| Wan Pro | 2× | High-quality image generation |
| Luma Ray2 | 3× | Cinematic video quality |

### Personal Promotion Code System
Every **paid subscriber** automatically receives a unique promotion code:
- Share your code: Earn **50 credits** when someone registers using your code
- New users get **20 welcome credits** for using a referral code
- Admin can create special promotion codes for specific users
- Free users can use others' codes but cannot create their own

### 7-Day Work Retention
When a subscriber cancels their subscription:
- All generated works are retained for **7 days**
- Can download existing works during retention period
- Cannot generate new works after cancellation
- Account deletion: All works deleted immediately (no retention)

### Referral Program
Invite friends and earn credits:
- Referrer earns **50 credits** per successful registration
- New user earns **20 welcome credits** for using a referral code
- Referral leaderboard at `/dashboard/referrals`
- Share via LINE, X/Twitter, Facebook, or direct link

**Free vs Paid Features**

| Capability | Free (Demo) | Paid (Subscriber) |
|---|---|---|
| Browse AI galleries | Pre-generated, watermarked | Full-quality, downloadable |
| Upload custom images | -- | All tools |
| I2I Transformations | Demo result | Real-time AI Engine |
| Room Redesign + 3D | Gallery only | Real-time redesign + GLB export |
| Product Scene Compositing | Gallery only | 3-step pipeline (rembg + AI Engine + composite) |
| Virtual Try-On | Gallery only | Real-time AI Try-On Engine |
| Style Effects | Browse styles | Real-time AI Engine |
| Credits on signup | 40 pts (30-day expiry) | Purchase packages (Starter / Standard / Premium) |
| Personal promotion code | ❌ | ✅ (auto-generated) |
| 7-day work retention | ❌ | ✅ (post-cancellation) |
| Social media publishing | ❌ | ✅ (FB, IG, TikTok, YouTube) |

## Admin Features
Fixed admin account configured in `.env`:
- `FIRST_SUPERUSER_EMAIL=admin@vidgo.ai`
- `FIRST_SUPERUSER_PASSWORD=admin123`

**Admin capabilities:**
- View API cost breakdown
- Monitor most popular APIs/tools usage
- Track most active accounts
- Real-time online user count via WebSocket
- Send credits to specific users
- Create special promotion codes for targeted users
- Ban/unban users

## Core Features

### 10 Core AI Tools

| Tool | Description | Engine |
|------|-------------|--------|
| **Background Removal** | Remove backgrounds from product images | AI Engine |
| **Product Scene** | Composite products into professional scenes (3-step I2I) | AI Image Engine |
| **Virtual Try-On** | Place garments on AI models | AI Try-On Engine |
| **Room Redesign** | AI interior design with 10 styles + iterative editing | AI Image Engine |
| **3D Model Generation** | Convert 2D designs to interactive GLB models | AI 3D Engine |
| **Short Video** | Image-to-video, Text-to-video | AI Video Engine |
| **AI Avatar** | Talking avatar with lip-sync TTS | AI Avatar Engine |
| **Image Effects** | Style transfer (anime, ghibli, 3D, etc.) + HD upscale | AI Style Engine |
| **I2I Transform** | Image-to-image transformation with prompt control | AI Style Engine |
| **Pattern Design** | Seamless pattern generation | AI Image Engine |

---

## Technology Stack

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| Vue 3 | 3.4+ | UI Framework |
| TypeScript | 5.0+ | Type Safety |
| Pinia | 2.0+ | State Management |
| Vue Router | 4.0+ | Routing |
| Tailwind CSS | 3.0+ | Styling |
| Vue I18n | 9.0+ | Internationalization |

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12+ | Runtime |
| FastAPI | 0.109+ | API Framework |
| SQLAlchemy | 2.0+ | ORM |
| Alembic | 1.13+ | Database Migrations |
| ARQ | 0.26+ | Background Tasks |
| httpx | 0.27+ | HTTP Client |

### Infrastructure
| Technology | Version | Purpose |
|------------|---------|---------|
| PostgreSQL | 15+ | Primary Database |
| Redis | 7+ | Cache & Task Queue |
| Docker | 24+ | Containerization |
| Docker Compose | 2.0+ | Orchestration |

### AI Providers
| Provider | Services | Details |
|----------|----------|---------|
| PiAPI | **Primary** for ALL generation: T2I, I2I, I2V, T2V, V2V, Avatar, Interior, BG Removal, Try-On, Effects, 3D | Flux (image); Wan (video); Kling (try-on); Trellis (3D). When PiAPI has no credits, image tasks fall back to Gemini |
| Google Gemini | **Backup** for image tasks + Content moderation + Pre-generation | Backup for T2I, I2I, Interior, BG Removal, Upscale, Effects. Also handles content moderation and pre-generating demo materials |

### Payment & Billing
| Provider | Region | Status |
|----------|--------|--------|
| Paddle | International | **Primary** - credit card, PayPal |
| ECPay | Taiwan | Legacy (optional, still in codebase) |
| ECPay E-Invoice | Taiwan | B2C/B2B e-invoice issue + void |

**Credit Packages**: Starter / Standard / Premium tiers. Gift codes and promotional discounts supported.

---

## Project Structure

```
Vidgo_Gen_AI/
├── backend/
│   ├── app/
│   │   ├── api/v1/             # API endpoints (20 routers)
│   │   ├── core/               # Config, database, security
│   │   ├── models/             # SQLAlchemy models
│   │   ├── providers/          # AI provider integrations
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── services/           # Business logic
│   │   └── main.py             # FastAPI app
│   ├── alembic/                # Database migrations
│   ├── scripts/                # Startup & pre-generation scripts
│   ├── static/                 # Generated files storage
│   └── Dockerfile
│
├── frontend-vue/
│   ├── src/
│   │   ├── api/                # API clients
│   │   ├── components/         # Vue components
│   │   ├── composables/        # Composition API hooks
│   │   ├── locales/            # i18n (en, zh-TW, ja, ko, es)
│   │   ├── stores/             # Pinia stores
│   │   ├── views/              # Page components
│   │   │   ├── tools/          # 8 tool pages
│   │   │   ├── dashboard/      # Dashboard + MyWorks + Invoices + Referrals
│   │   │   ├── admin/          # Admin dashboard
│   │   │   └── auth/           # Auth pages
│   │   └── router/             # Vue Router
│   └── Dockerfile
│
├── docker-compose.yml
├── vidgo-backend-architecture.md
├── vidgo-frontend-architecture.md
└── README.md
```

---

## Getting Started

### Prerequisites

- Docker 24+ and Docker Compose 2.0+
- API Keys for: PiAPI, Google Gemini

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/vidgo-gen-ai.git
   cd vidgo-gen-ai
   ```

2. **Configure environment variables**
   ```bash
   cp backend/.env.example backend/.env
   # Edit .env and add your API keys
   ```

3. **Start the services**
   ```bash
   # Standard startup (includes pre-generation)
   docker-compose up -d

   # First-time bulk generation (30 materials per tool)
   docker-compose --profile init up init-materials
   ```

4. **Access the application**
   - Frontend: http://localhost:8501
   - Backend API: http://localhost:8001
   - API Docs: http://localhost:8001/docs
   - Email Testing: http://localhost:8025 (Mailpit)

---

## Configuration

### Required API Keys

```env
# backend/.env

# AI Providers
PIAPI_KEY=your_piapi_key
GEMINI_API_KEY=your_gemini_key

# Payment - Primary (International)
PADDLE_API_KEY=
PADDLE_PUBLIC_KEY=

# Payment - Legacy (Taiwan, optional)
# ECPAY_MERCHANT_ID=
# ECPAY_HASH_KEY=
# ECPAY_HASH_IV=

# Security
SECRET_KEY=your-secret-key-here
RECAPTCHA_SECRET_KEY=your_recaptcha_v2_secret
RECAPTCHA_SITE_KEY=your_recaptcha_v2_site_key

# Email (dev uses Mailpit)
SMTP_HOST=mailpit
SMTP_PORT=1025
```

### Pre-generation Control

| Variable | Default | Description |
|----------|---------|-------------|
| `SKIP_PREGENERATION` | `false` | Skip AI API calls on startup |
| `PREGENERATION_LIMIT` | `10` | Materials per tool |
| `SKIP_AVATAR` | - | Skip avatar generation |
| `SKIP_VIDEO` | - | Skip video generation |

### Referral & Upload Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `REFERRAL_BONUS_CREDITS` | `50` | Credits for referrer per successful signup |
| `REFERRAL_WELCOME_CREDITS` | `20` | Welcome credits for new user via referral |
| `MAX_UPLOAD_SIZE_MB` | `20` | Max subscriber upload size in MB |
| `UPLOAD_ALLOWED_TYPES` | `image/jpeg,...` | Allowed upload MIME types |

---

## Docker Services

```yaml
services:
  postgres:        # PostgreSQL 15 - Primary database
  redis:           # Redis 7 - Cache & task queue
  mailpit:         # Email testing (dev only)
  backend:         # FastAPI application (port 8001)
  worker:          # ARQ background worker
  init-materials:  # Initial pre-generation (runs once)
  frontend:        # Vue 3 frontend (port 8501)
```

### Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Run pre-generation
docker-compose --profile init up init-materials

# Skip pre-generation (use cached materials)
SKIP_PREGENERATION=true docker-compose up -d

# Skip expensive operations
SKIP_VIDEO=true SKIP_AVATAR=true docker-compose up -d
```

---

## Development

### Local Development (Without Docker)

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend-vue
npm install
npm run dev
```

### API Endpoints

| Prefix | Description |
|--------|-------------|
| `/api/v1/auth` | Authentication + Email verification |
| `/api/v1/demo` | Demo/preset endpoints (preset-only mode) |
| `/api/v1/generate` | Content generation (subscribers) |
| `/api/v1/uploads` | Subscriber material upload + real-API generation |
| `/api/v1/referrals` | Referral code management + stats |
| `/api/v1/tools` | Tool operations (BG removal, try-on, I2I, etc.) |
| `/api/v1/credits` | Credit management |
| `/api/v1/subscriptions` | Subscription plans + Paddle checkout |
| `/api/v1/admin` | Admin dashboard (stats, costs, active users) |
| `/api/v1/einvoices` | Taiwan e-invoice (issue, void) |
| `/api/v1/interior` | Interior design & 3D models |
| `/api/v1/workflow` | Workflow management |
| `/api/v1/effects` | Style effects & HD enhance |
| `/api/v1/promotions` | Promotions & gift codes |
| `/api/v1/plans` | Subscription plans & pricing |
| `/api/v1/payments` | Payment processing (Paddle) |
| `/api/v1/landing` | Landing page data |
| `/api/v1/quota` | Usage quotas |
| `/api/v1/session` | Session tracking |
| `/api/v1/prompts` | Prompt templates |
| `/api/v1/user` | User works & generations |
| `/api/v1/social` | Social sharing |
| `/api/v1/models` | AI model registry |

---

## Security & Anti-Abuse

| Mechanism | Implementation |
|-----------|---------------|
| Rate Limiting | Redis-based; per-IP and per-email limits on registration and generation |
| CAPTCHA | Google reCAPTCHA v2 on registration |
| Watermarking | All demo outputs watermarked; subscribers get clean output |
| Credit Gating | All generation endpoints check credit balance before processing (HTTP 402) |

See [backend architecture doc](./vidgo-backend-architecture.md) for full security details.

---

## Documentation

- **Backend Architecture**: [vidgo-backend-architecture.md](./vidgo-backend-architecture.md)
- **Frontend Architecture**: [vidgo-frontend-architecture.md](./vidgo-frontend-architecture.md)
- **Infrastructure**: [vidgo-infra-architecture.md](./vidgo-infra-architecture.md)
- **API Documentation**: http://localhost:8001/docs (when running)

---

## ⚠️ Docker Startup Notes

### Material Pre-generation
The `docker-compose.yml` **backend** service bypasses `docker_entrypoint.sh` (it sets `entrypoint: []`) for fast development iteration. To pre-generate materials, run:

```bash
# First-time setup: generate all materials
docker compose --profile init up init-materials

# Or skip pre-generation for dev (uses empty Material DB)
SKIP_PREGENERATION=true ALLOW_EMPTY_MATERIALS=true docker compose up -d
```

The Dockerfile's `ENTRYPOINT` (the full startup sequence with migration + material check) is used in production builds.

---

## Supported Languages

| Code | Language |
|------|----------|
| `en` | English |
| `zh-TW` | Traditional Chinese |
| `ja` | Japanese |
| `ko` | Korean |
| `es` | Spanish |

---

*Last Updated: March 23, 2026*

