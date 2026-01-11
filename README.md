# VidGo Gen AI Platform

**AI-Powered Visual Content Generation for E-commerce**

VidGo is a comprehensive AI platform that enables e-commerce businesses to create professional visual content using cutting-edge generative AI technology. The platform operates in **PRESET-ONLY mode**, providing instant access to pre-generated high-quality examples while driving conversions to paid subscriptions.

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

### PRESET-ONLY Mode

VidGo operates in **PRESET-ONLY mode** for demo users:

1. **No Runtime API Calls**: All demo content is pre-generated before service starts
2. **Instant Experience**: Users see results immediately without waiting for AI processing
3. **Cost Control**: Zero API costs for demo usage - only pre-generation costs
4. **Watermarked Results**: All demo outputs have watermarks; full downloads require subscription
5. **Conversion-Focused**: Demo experience drives users toward paid subscriptions

---

## Core Features

### 6 Core AI Tools

| Tool | Description | API Provider |
|------|-------------|--------------|
| **Background Removal** | Remove backgrounds from product images | PiAPI Wan / Gemini |
| **Product Scene** | Place products in professional settings | PiAPI Wan T2I |
| **Virtual Try-On** | Virtual clothing try-on for fashion | Pollo AI |
| **Room Redesign** | 2D-to-3D Visualization (Plan to Render) | PiAPI Wan / Trellis |
| **Short Video** | Image-to-video, Text-to-video | Pollo AI |
| **AI Avatar** | Talking avatar with lip-sync TTS | A2E.ai |

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
| ECPay | Taiwan | Credit card, ATM, CVS |
| Paddle | International | Credit card, PayPal |

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
| `ALLOW_EMPTY_MATERIALS` | `false` | Allow startup without materials |

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

# Development mode (allow empty materials)
ALLOW_EMPTY_MATERIALS=true docker-compose up -d

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
| `/api/v1/auth` | Authentication |
| `/api/v1/demo` | Demo/preset endpoints |
| `/api/v1/generate` | Content generation |
| `/api/v1/tools` | Tool operations |
| `/api/v1/credits` | Credit management |
| `/api/v1/admin` | Admin dashboard |
| `/api/v1/interior` | Interior design |
| `/api/v1/workflow` | Workflow management |

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

*Last Updated: January 12, 2026*

