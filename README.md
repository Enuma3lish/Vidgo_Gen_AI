# VidGo Gen AI Platform

**AI-Powered Visual Content Generation for E-commerce**

VidGo is a comprehensive AI platform that enables e-commerce businesses to create professional visual content using cutting-edge generative AI technology. The platform provides instant access to pre-generated high-quality examples for trial users, and full real-API generation with model selection for subscribers.

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
         +----------+--+  +----+-----+  +------+-------+
         |  PiAPI/Wan  |  | Pollo AI |  |    A2E.ai    |
         | - T2I       |  | - I2V    |  | - Avatar     |
         | - I2V       |  | - T2V    |  | - Lip-sync   |
         +-------------+  +----------+  +--------------+
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

---

## Core Features

### 8 Core AI Tools

| Tool | Description | API Provider |
|------|-------------|--------------|
| **Background Removal** | Remove backgrounds from product images | PiAPI Wan / Gemini |
| **Product Scene** | Product Photography Inspiration Gallery | PiAPI Wan T2I |
| **Virtual Try-On** | Fashion Model Showcase | Kling AI via PiAPI |
| **Room Redesign** | Interior Design Example Gallery | PiAPI Wan T2I |
| **Short Video** | Image-to-video, Text-to-video | Pollo AI |
| **AI Avatar** | Talking avatar with lip-sync TTS | A2E.ai |
| **Image Effects** | Artistic style transfer | PiAPI I2I (Flux) |
| **Pattern Design** | Seamless pattern generation | PiAPI Wan T2I |

---

## Subscriber Features

### Custom Material Upload
Subscribers can upload their own product images and trigger real AI API calls:
- Supported tools: All 8 tools
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

### Referral Program
Invite friends and earn credits:
- Referrer earns **50 credits** per successful registration
- New user earns **20 welcome credits** for using a referral code
- Referral leaderboard at `/dashboard/referrals`
- Share via LINE, X/Twitter, Facebook, or direct link

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
| Provider | API | Purpose |
|----------|-----|---------|
| PiAPI | Wan API | Text-to-Image, Image-to-Video, Interior Design |
| Pollo AI | Pixverse, Pollo | Image-to-Video, Text-to-Video |
| A2E.ai | Lip-sync API | Avatar Video with TTS |
| Google Gemini | Generative AI | Moderation, Backup Image |

### Payment Providers
| Provider | Region | Features |
|----------|--------|----------|
| Paddle | International | Credit card, PayPal, Tax compliance |

---

## Project Structure

```
Vidgo_Gen_AI/
├── backend/
│   ├── app/
│   │   ├── api/v1/             # API endpoints (17 routers)
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
GEMINI_API_KEY=your_gemini_key

# Payment - Taiwan
ECPAY_MERCHANT_ID=
ECPAY_HASH_KEY=
ECPAY_HASH_IV=

# Payment - International
PADDLE_API_KEY=
PADDLE_PUBLIC_KEY=

# Security
SECRET_KEY=your-secret-key-here

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
| `/api/v1/tools` | Tool operations |
| `/api/v1/credits` | Credit management |
| `/api/v1/subscriptions` | Subscription plans + Paddle checkout |
| `/api/v1/admin` | Admin dashboard |
| `/api/v1/interior` | Interior design |
| `/api/v1/workflow` | Workflow management |

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

*Last Updated: February 21, 2026*

