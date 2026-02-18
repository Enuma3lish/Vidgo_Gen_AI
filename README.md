# VidGo Gen AI Platform

**AI-Powered Visual Content Generation for E-commerce**

VidGo is a comprehensive AI platform that enables e-commerce businesses to create professional visual content using cutting-edge generative AI technology. The platform operates with a **two-tier model**: free users browse pre-generated examples (PRESET mode), while paid subscribers access real-time AI generation with full-quality output.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Core Features](#core-features)
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
         +-------------+  +----------+  +--------------+
         |    PiAPI     |  | Pollo AI |  |    A2E.ai    |
         | - T2I / I2I  |  | - I2V    |  | - Avatar     |
         | - I2V / T2V  |  | - T2V    |  | - Lip-sync   |
         | - Try-On     |  | - V2V    |  +--------------+
         | - 3D(Trellis)|  +----------+
         +-------------+         +---------------+
                                 | Google Gemini  |
                                 | - Moderation   |
                                 | - Interior(bkp)|
                                 +---------------+
```

### Demo / Free Tier (PRESET Mode)

Free users experience **PRESET mode**:

1. **No Runtime API Calls**: All demo content is pre-generated before service starts
2. **Instant Experience**: Users see results immediately without waiting for AI processing
3. **Cost Control**: Zero API costs for demo usage - only pre-generation costs
4. **Watermarked Results**: All demo outputs have watermarks; full downloads require subscription
5. **Conversion-Focused**: Demo experience drives users toward paid subscriptions

### Paid Tier (Real-Time Generation)

Subscribers receive real-time AI generation with:

1. **Full Resolution**: 1080P output (vs 720P for free tier)
2. **No Watermarks**: Clean output with full download access
3. **Credit System**: Free tier 20-35 pts vs Paid tier 80-120 pts per generation
4. **Registration Bonus**: 40 credits (30-day expiry) for new users to trial paid features
5. **Custom Uploads**: Upload and process custom images across all tools

---

**Free vs Paid Features**

| Capability | Free (Demo) | Paid (Subscriber) |
|---|---|---|
| Browse AI galleries | Pre-generated, watermarked | Full-quality, downloadable |
| Upload custom images | -- | All tools |
| I2I Transformations | Demo result | Real-time via PiAPI Flux |
| Room Redesign + 3D | Gallery only | Real-time redesign + GLB export |
| Product Scene Compositing | Gallery only | 3-step pipeline (rembg + T2I + composite) |
| Virtual Try-On | Gallery only | Real-time via Kling AI (PiAPI) |
| Style Effects | Browse styles | Real-time via GoEnhance |
| Credits on signup | 40 pts (30-day expiry) | Purchase packages (Starter / Standard / Premium) |

## Core Features

### 9 Core AI Tools

| Tool | Description | API Provider |
|------|-------------|--------------|
| **Background Removal** | Remove backgrounds from product images | PiAPI (Flux) |
| **Product Scene** | Composite products into professional scenes (3-step I2I) | PiAPI T2I + PIL |
| **Virtual Try-On** | Place garments on AI models | Kling AI via PiAPI |
| **Room Redesign** | AI interior design with 10 styles + iterative editing | Gemini 2.5 Flash |
| **3D Model Generation** | Convert 2D designs to interactive GLB models | PiAPI Trellis (Qubico) |
| **Short Video** | Image-to-video, Text-to-video | PiAPI Wan / Pollo AI |
| **AI Avatar** | Talking avatar with lip-sync TTS | A2E.ai |
| **Image Effects** | Style transfer (anime, ghibli, 3D, etc.) + HD upscale | GoEnhance |
| **I2I Transform** | Image-to-image transformation with prompt control | PiAPI Flux (img2img) |

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
| PiAPI | T2I, I2I, I2V, T2V, Interior, BG Removal, 3D | Flux1-schnell (free) / Flux (paid); Wan for video; Trellis for 3D |
| PiAPI (Kling) | Virtual Try-On | Kling AI accessed through PiAPI |
| Pollo AI | I2V, T2V, V2V | Backup for video; keyframes, effects, multi-model |
| A2E.ai | Avatar + Lip-sync TTS | Photo-to-avatar; Asian-focused; gender-voice matching |
| Google Gemini | Moderation, Interior (backup) | Content moderation; emergency fallback for interior design |
| GoEnhance | Style Effects, HD Enhance | White-labeled as VidGo Effects |

### Payment & Billing
| Provider | Region | Status |
|----------|--------|--------|
| Paddle | International | **Primary** - credit card, PayPal |
| ECPay | Taiwan | Legacy (optional, still in codebase) |

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
│   │   │   ├── tools/          # 6 tool pages
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
- API Keys for: PiAPI, Pollo AI, A2E.ai
- (Optional) Gemini API key for backup

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
POLLO_API_KEY=your_pollo_key
A2E_API_KEY=your_a2e_key
A2E_API_ID=your_a2e_api_id
A2E_DEFAULT_CREATOR_ID=your_creator_id
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
| `SKIP_AVATAR` | - | Skip A2E avatar generation |
| `SKIP_VIDEO` | - | Skip Pollo video generation |

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
| `/api/v1/auth` | Authentication & registration |
| `/api/v1/demo` | Demo/preset endpoints |
| `/api/v1/generate` | Content generation |
| `/api/v1/tools` | Tool operations (BG removal, try-on, I2I, etc.) |
| `/api/v1/credits` | Credit balance & transactions |
| `/api/v1/admin` | Admin dashboard |
| `/api/v1/interior` | Interior design & 3D models |
| `/api/v1/workflow` | Workflow management |
| `/api/v1/subscriptions` | Subscription management |
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
- **API Documentation**: http://localhost:8001/docs (when running)

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

*Last Updated: February 18, 2026*

