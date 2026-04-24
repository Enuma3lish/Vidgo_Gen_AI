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
- [Accessing the Application](#accessing-the-application)
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
+----------------+  +----------------+  +------------------+
|   PostgreSQL   |  |     Redis      |  |   GCS Bucket     |
|  (Database)    |  |  (Cache/Queue) |  |  (Media Storage) |
|  Port: 5432    |  |  Port: 6379    |  |                  |
+----------------+  +----------------+  +------------------+
                                               |
                    +------------ MCP Protocol -----------+
                    |                                     |
         +------------------+              +------------------+
         |  Pollo.ai MCP    |              |  PiAPI MCP       |
         |  (PRIMARY video) |              |  (SUPPLEMENT +   |
         |  - T2V (50+ mod) |              |   VIDEO BACKUP)  |
         |  - I2V           |              |  - T2I, I2I      |
         |  pollo-mcp (npm) |              |  - Try-On, Avatar|
         +------------------+              |  - Interior, 3D  |
                                           |  - TTS, Upscale  |
                                           |  piapi-mcp-server|
                                           +------------------+
                                                    |
                                           +------------------+
                                           | Google Gemini    |
                                           | - Image backup   |
                                           | - Moderation     |
                                           | - Material gen   |
                                           +------------------+
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

### 8 Core AI Tools

| Tool | Description | Engine / Backend |
|------|-------------|------------------|
| **Background Removal** | Remove backgrounds from product images | PiAPI rembg |
| **Product Scene** | Composite frozen product photos into AI-generated scenes (rembg → scene T2I → PIL composite) | PiAPI Flux + rembg |
| **Virtual Try-On** | Place curated garments on curated full-body models | PiAPI Kling virtual try-on |
| **Room Redesign** | AI interior design with 10 styles + iterative editing | PiAPI Flux interior |
| **Short Video** | Image-to-video, Text-to-video | Pollo MCP (primary) / PiAPI (backup) |
| **AI Avatar** | Talking head with lip-sync TTS (curated head-and-shoulders portraits) | PiAPI Kling Avatar |
| **Image Effects** | Artistic style transfer on frozen product photos | PiAPI I2I |
| **Pattern Generate** | Seamless pattern generation | PiAPI Flux |

All tools share a **cache-through demo flow**:
1. Visitor picks a preset combo (e.g. product × scene, model × garment).
2. Backend looks up a pre-generated row in the Material DB keyed by the exact combo.
3. On cache miss, the on-demand path runs the pipeline using frozen GCS inputs (never random T2I-generated assets) and persists the result for the next visitor.

See [docs/example-mode-cache-system.md](./docs/example-mode-cache-system.md) for the full demo pipeline and curated asset catalog.

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
Default admin account (seeded by `backend/scripts/seed_demo_data.py`):
- Email: `admin@vidgo.ai`
- Password: `Admin1234!`

Override locally via `.env`; in production these are seeded once into the database, not via env vars. Change the password after first login.

**Admin capabilities:**
- View API cost breakdown
- Monitor most popular APIs/tools usage
- Track most active accounts
- Real-time online user count via WebSocket
- Send credits to specific users
- Create special promotion codes for targeted users
- Ban/unban users

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

### AI Providers (MCP-based Architecture)
| Provider | Role | Services | Details |
|----------|------|----------|---------|
| Pollo.ai MCP | **Primary** (video) | I2V, T2V, V2V | 50+ models (Kling, Wan, Runway, Sora, Seedance, etc.) via `pollo-mcp` npm package |
| PiAPI MCP | **Supplement** + video backup | T2I, I2I, Try-On, Interior, Avatar, TTS, Upscale, 3D, V2V | Flux (image); Wan (video); Kling (try-on/avatar); Trellis (3D) via `piapi-mcp-server` |
| Google Gemini | **Backup** (image) + moderation | T2I, I2I, Interior, BG Removal, Upscale | Backup when PiAPI MCP fails; content moderation; material pre-generation |
| A2E | **Backup** (avatar) | Avatar | Digital human video backup when PiAPI MCP fails |
| GCS | **Storage** | Media persistence | Downloads CDN URLs → persists in GCS bucket (providers have 14-day CDN expiry) |

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
- Node.js 16+ (for MCP servers)
- API Keys for: Pollo.ai, PiAPI, Google Gemini

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

4. **Access the application** — see the [Accessing the Application](#accessing-the-application) section below.

---

## Accessing the Application

VidGo runs in two environments: your **local Docker stack** for development, and the **GCP Cloud Run** deployment in the `vidgo-ai` project for production. Use the relevant section below.

### Docker environment (local)

After `docker compose up -d` completes and `docker compose ps` shows every service `healthy`, open these URLs in a browser:

| Surface | URL | Purpose |
|---|---|---|
| Frontend (Vue app) | http://localhost:8501 | The site itself — landing, pricing, tools, dashboard |
| Backend API | http://localhost:8001 | Raw FastAPI server (for direct API calls) |
| Swagger / OpenAPI docs | http://localhost:8001/docs | Interactive API reference |
| ReDoc | http://localhost:8001/redoc | Alternative API reference |
| Mailpit (inbox) | http://localhost:8025 | All outbound email — **email verification codes land here** during local signup |
| Postgres (psql) | `localhost:5433` | DB user `postgres`, DB name `vidgo` |
| Redis | `localhost:6380` | Cache + ARQ queue |

**Internal container ports** (referenced in `docker-compose.yml`, not reachable from host):
backend `:8000`, frontend `:5173`, postgres `:5432`, redis `:6379`.

**Sign in as admin locally:**
```
Email:    admin@vidgo.ai
Password: admin123
```
Override via `FIRST_SUPERUSER_EMAIL` / `FIRST_SUPERUSER_PASSWORD` in `backend/.env`.

**Sign up a fresh user locally:** register at http://localhost:8501/auth/register, then open http://localhost:8025 (Mailpit) to read the verification code — no real inbox needed.

**Common issues:**
- `localhost:8501` hangs or 502s → frontend container not healthy yet; run `docker compose logs -f frontend`.
- `localhost:8001/docs` returns 500 on first hit → backend is still running migrations / material pregen; watch `docker compose logs -f backend` until it prints `Uvicorn running on …`.
- Port already in use → another service is bound to 8501/8001/5433/6380/8025; stop it or remap in `docker-compose.yml`.
- Reset everything: `docker compose down -v` (⚠ wipes volumes including Postgres data and pre-generated materials).

### GCP environment (production — Cloud Run)

The production deployment lives in GCP project **`vidgo-ai`**, region **`asia-east1`** (Taiwan). Each service is an independent Cloud Run revision behind the default `*.run.app` URL.

| Service | URL |
|---|---|
| Frontend (Vue app) | https://vidgo-frontend-38714015566.asia-east1.run.app |
| Backend API | https://vidgo-backend-38714015566.asia-east1.run.app |
| Worker (background jobs, no public UI) | https://vidgo-worker-38714015566.asia-east1.run.app |

The `38714015566` segment is the Cloud Run service number for project `vidgo-ai`. If Cloud Run re-issues URLs or you map a custom domain, re-fetch them with:

```bash
gcloud run services list --project vidgo-ai --region asia-east1
```

**Health check without a browser:**
```bash
curl -I https://vidgo-frontend-38714015566.asia-east1.run.app
curl -s https://vidgo-backend-38714015566.asia-east1.run.app/api/v1/health
```

**Swagger docs:** `/docs` on the backend URL is typically disabled in production for security. Use the local Docker stack or the staging env for interactive API exploration, not production.

**Admin access on production:** the same credentials pattern applies (`FIRST_SUPERUSER_EMAIL` / `FIRST_SUPERUSER_PASSWORD`), but they are stored in Secret Manager, not `.env`. Retrieve them with:
```bash
gcloud secrets versions access latest --secret=FIRST_SUPERUSER_PASSWORD --project=vidgo-ai
```
⚠ **Production actions burn real credits and can charge real users.** Never run generation endpoints, checkout flows, or rate-limit tests against these URLs without explicit authorization.

**Viewing production logs:**
```bash
# Tail the backend
gcloud run services logs tail vidgo-backend --project vidgo-ai --region asia-east1

# Grep recent worker errors
gcloud run services logs read vidgo-worker --project vidgo-ai --region asia-east1 --limit 200 | grep -i error
```

**Deploying a new revision:** see [`gcp/deploy.sh`](./gcp/deploy.sh) and [`gcp/deploy-production.sh`](./gcp/deploy-production.sh). Initial infrastructure bring-up is in `deploy-production.sh`; routine rebuilds go through Cloud Build (`cloudbuild.yaml`).

---

## Configuration

### Required API Keys

```env
# backend/.env

# AI Providers (MCP-based)
POLLO_API_KEY=your_pollo_key            # Primary video (pollo.ai)
PIAPI_KEY=your_piapi_key                # Supplement + video backup (piapi.ai)
GEMINI_API_KEY=your_gemini_key          # Image backup + moderation

# MCP Server Path (PiAPI)
PIAPI_MCP_PATH=/app/mcp-servers/piapi-mcp-server/dist/index.js

# GCS Storage (persist media beyond CDN expiry)
GCS_BUCKET=vidgo-media-vidgo-ai

# Payment - ECPay (Taiwan)
ECPAY_ENV=production
ECPAY_MERCHANT_ID=your_merchant_id
ECPAY_HASH_KEY=your_hash_key
ECPAY_HASH_IV=your_hash_iv

# Payment - Paddle (International)
PADDLE_API_KEY=
PADDLE_PUBLIC_KEY=

# Security
SECRET_KEY=your-secret-key-here

# Email (dev uses Mailpit)
SMTP_HOST=mailpit
SMTP_PORT=1025

# Gmail SMTP on GCP Cloud Run
# Use a Gmail App Password, not your normal account password.
# For STARTTLS on port 587:
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your-account@gmail.com
# SMTP_PASSWORD=your-16-char-app-password
# SMTP_TLS=true
# SMTP_SSL=false
# SMTP_FROM_EMAIL=your-account@gmail.com   # or a verified Gmail alias
# SMTP_FROM_NAME=VidGo
# SMTP_TIMEOUT_SECONDS=15
#
# For implicit SSL on port 465 instead:
# SMTP_PORT=465
# SMTP_TLS=false
# SMTP_SSL=true
```

### MCP Server Setup

Both AI providers run as MCP (Model Context Protocol) servers:

```bash
# Install Pollo MCP server (global npm package)
npm install -g pollo-mcp

# Build PiAPI MCP server (from source)
git clone https://github.com/PiAPI-1/piapi-mcp-server.git mcp-servers/piapi-mcp-server
cd mcp-servers/piapi-mcp-server && npm install && npm run build
```

The backend automatically starts both MCP servers as subprocesses on startup.
If MCP servers are unavailable, the system falls back to direct REST API calls.

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
- **MCP Provider Architecture**: [docs/mcp-provider-architecture.md](./docs/mcp-provider-architecture.md)
- **DNS & ECPay Setup**: [docs/dns-and-ecpay-setup.md](./docs/dns-and-ecpay-setup.md)
- **Payment & Invoice**: [docs/payment_and_infra.md](./docs/payment_and_infra.md)
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

*Last Updated: April 15, 2026*

