# VidGo Gen AI Platform

**AI-Powered Visual Content Generation for E-commerce, Interior & Architecture**

VidGo is a comprehensive AI platform for creating professional visual content — product photography, short video ads, virtual try-on, interior/exterior design renders, and digital spokespersons. The platform operates with a **two-tier model**: free users browse pre-generated examples (PRESET mode), while paid subscribers access real-time AI generation with full-quality output.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Core Features](#core-features)
- [User Role Matrix](#user-role-matrix)
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
+----------------+  +----------------+  +------------------+
                             |
              +------ AI Providers (REST) ------+
              |                |                |
     +----------------+ +-------------+ +----------------+
     |  PiAPI (REST)  | | Vertex AI   | |  Pollo (REST)  |
     |  PRIMARY       | | Gemini 2.5  | |  video backup  |
     |  Flux/Kontext  | | Flash Image | |  Kling/Sora    |
     |  Kling 2.5-3.0 | | (ADC auth)  | +----------------+
     |  Sora 2 Pro    | | interior +  |
     |  Veo/Seedance  | | image backup|
     |  Try-On/3D     | +-------------+
     +----------------+
```

> The MCP subprocess architecture was removed on 2026-05-26 — all providers
> are called through their REST APIs via `provider_router.py`, which maps
> each `TaskType` to a primary / backup / tertiary provider chain with
> circuit-breaking and transient-retry.

### Dual-Mode Architecture

| Mode | Who | Experience |
|------|-----|------------|
| **PRESET-ONLY** | Free / trial users | Browse pre-generated watermarked gallery; instant results, no API costs |
| **REAL-API** | Subscribers | Upload own materials, call live AI APIs, choose AI model, download without watermark |

All demo tools share a **cache-through flow**: a visitor picks a preset combo,
the backend serves the pre-generated Material DB row, and on a cache miss the
pipeline runs once with frozen GCS inputs and persists the result for the next
visitor. See [docs/example-mode-cache-system.md](./docs/example-mode-cache-system.md).

### Prompt-Fidelity Principle

User prompts reach the generation models **verbatim** — no AI rewriting
(owner directive 2026-05-23). Hallucination is reduced with *additive,
user-selected* controls instead: camera-move catalogs, subject-lock /
strict-prompt toggles, atmosphere knobs (lighting / color temperature /
material), structure-preservation clauses, and baseline negative prompts.

---

## Core Features

The tool hub (`/tools/product-scene`) lists **32 tiles in 5 categories**.
Interior and exterior are strictly separated — each tool is its own page.

### 廣告宣傳 (Advertising)
| Tool | Description | Engine |
|------|-------------|--------|
| Virtual Try-On | Built-in AI models or own photo; garment image or text outfit | PiAPI Kling Try-On / Flux Kontext |
| Product Staging / Photography / Flat-lay | Composite products into AI scenes | PiAPI Flux + rembg |
| AI Video (image / text) | I2V + T2V short videos | Hailuo, Wan, Hunyuan, Seedance 720p/1080p, Kling 2.5/3.0/Omni, Veo 3.1 |
| Kling Video | Premium T2V/I2V with tiers (V2.5 STD / V3.0 STD / V3.0 PRO + audio) | PiAPI Kling, Pollo backup |
| Sora 2 Pro | Flagship 4–12 s 1080p video with synchronized audio | PiAPI Sora 2 Pro, Pollo backup |
| AI Avatar / Spokesperson | Talking head with lip-sync TTS | PiAPI Kling Avatar |
| IG / TikTok Reel | Social-format short video | Shared video pipeline |

### 室內設計 (Interior Design) — one page per tool
| Tool | Page |
|------|------|
| 室內設計改造 Room Redesign | `/tools/room-redesign` (redesign / stage / magic modes, 34 styles) |
| 室內設計範本 Interior Templates | `/tools/interior-templates` |
| 平面配置圖 Floor Plan | `/tools/floor-plan` (text or sketch → clean 2D plan; vision pass reads furniture/labels from the image) |
| 立體圖 Isometric View | `/tools/isometric` (45° dollhouse; lighting / color-temp / material knobs) |
| 3D 效果圖 3D Render | `/tools/render-3d` (保留結構 ControlNet-depth lock or 自由改造; optional growth video + GLB model) |
| 商業空間設計 Commercial Space | `/tools/commercial-space` |
| 草圖轉渲染（室內）Sketch → Render | `/tools/sketch-to-render-interior` |
| 渲染圖優化放大 Render Enhancer | `/tools/render-enhancer` |

### 室外設計 (Exterior Design) — one page per tool
| Tool | Page |
|------|------|
| 建築外觀 AI 設計 Exterior AI | `/tools/exterior-ai` (12 facade styles) |
| 草圖轉渲染（建築外觀）Sketch → Render | `/tools/sketch-to-render-exterior` |
| 建築外觀範本 Exterior Templates | `/tools/exterior-templates` |

### 品牌設計 (Branding)
Logo, marketing hero image, packaging pattern, recolor — PiAPI T2I
(Flux / Qwen / Z-Image / Nano Banana / Seedream).

### 其他 (Other)
Background cutout / replace, upscale (2x/4x), ghost mannequin, wrinkle
removal, video background remove, claymation playground.

### Inspiration Gallery

`/gallery` showcases pre-generated examples with search, industry/tool
filters, and "Try this example" deep links that pre-fill the matching tool.

---

## User Role Matrix

| Feature | Visitor (Guest) | Free Registered | Paid Subscriber | Admin |
|---------|----------------|-----------------|-----------------|-------|
| Browse landing page | ✅ | ✅ | ✅ | ✅ |
| Demo tools (preset, DB results) | ✅ (limit 2) | ✅ (limit 2) | ✅ | ✅ |
| Watermarked results | ✅ | ✅ | ❌ (clean) | N/A |
| Download results | ❌ | ❌ | ✅ | ✅ |
| Upload own materials | ❌ | ❌ | ✅ | ❌ |
| Real AI API generation / custom prompts | ❌ | ❌ | ✅ (bound card required) | ✅ |
| Premium models (Kling 3.0 / Sora 2 / Veo) | ❌ | ❌ | ✅ (plan-tier gated) | ✅ |
| Promotion code (own) | ❌ | ❌ | ✅ (auto-issued) | Can create special ones |
| Private work library (14-day media retention) | ❌ | ❌ | ✅ | N/A |
| Taiwan e-invoice + 發票設定 | ❌ | ❌ | ✅ | N/A |
| Admin dashboard / model registry | ❌ | ❌ | ❌ | ✅ |

## Subscriber Features

- **Custom uploads** — JPEG/PNG/WebP (HEIC auto-normalized), max 20 MB; clean, downloadable results.
- **Model selection** — per-tool model picker; better models cost more credits (see `backend/app/services/tier_config.py`).
- **Referral program** — referrer earns 50 credits per signup; new users get 40 welcome credits; leaderboard at `/dashboard/referrals`.
- **Work library retention** — generated media stays 14 days from creation; records remain until account deletion.
- **Taiwan e-invoice (電子發票)** — auto-issued after every payment. Users choose the mode once in 發票設定 (dashboard → Invoices → Invoice Settings): 個人發票＋載具 (mobile barcode / citizen cert / email), 公司發票＋統一編號 (B2B), or 捐贈發票 (love code). Issued via **Giveme** (primary), ECPay (fallback), or PayPal Invoicing v2 for PayPal orders; voiding supported within the bimonthly tax period.

## Admin Features

The local admin account is seeded from `FIRST_SUPERUSER_EMAIL` /
`FIRST_SUPERUSER_PASSWORD` in `backend/.env` (set your own values — never
commit them). Production credentials live in Secret Manager:

```bash
gcloud secrets versions access latest --secret=FIRST_SUPERUSER_PASSWORD --project=vidgo-ai
```

Capabilities: API cost breakdown, popular-tools and active-account stats,
live online-user count, credit grants, special promo codes, user ban/unban,
model-registry overrides (Redis pub/sub propagates flips to all instances
without redeploy), runtime PayPal config.

---

## Technology Stack

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| Vue 3 | 3.4+ | UI framework (`<script setup>`, defineModel) |
| TypeScript | 5.x | Type safety |
| Pinia / Vue Router / Vue I18n | — | State / routing / i18n (en, zh-TW, ja, ko, es) |
| Tailwind CSS | 3.x | Styling |
| Vite | 5.x | Build (`Dockerfile.prod` does the production build) |

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12+ | Runtime |
| FastAPI | 0.109+ | API framework (27 routers under `/api/v1`) |
| SQLAlchemy 2 + asyncpg | — | Async ORM |
| Alembic | — | Migrations (multi-head history; applied manually with idempotent SQL) |
| Cloud Scheduler | — | Background tasks (`POST /api/v1/tasks/*`); replaced the always-on ARQ worker in prod |
| httpx | — | Provider REST calls |

### AI Providers (all REST — MCP removed 2026-05-26)
| Provider | Role | Services |
|----------|------|----------|
| **PiAPI** | Primary | Flux T2I/I2I, Flux Kontext, Kling video 2.5/2.6/3.0/Omni, Sora 2 Pro, Veo 3.1, Seedance, Hailuo, Hunyuan, Wan, Kling Try-On & Avatar, Trellis 3D, ControlNet, upscale, rembg |
| **Vertex AI (Gemini 2.5 Flash Image)** | Interior design primary + image backup | Uses **ADC** (`VERTEX_AI_PROJECT`); the legacy `GEMINI_API_KEY` was revoked |
| **Pollo.ai** | Video backup | Kling / Sora fallback lane |
| **GCS** | Storage | Provider CDN URLs expire in ~14 days → results persisted to `vidgo-media-vidgo-ai` |

### Payment & Billing
| Provider | Region | Status |
|----------|--------|--------|
| PayPal | International (USD) | Subscriptions + Invoicing v2; runtime-configurable from the admin UI ([docs/PAYPAL_SETUP.md](./docs/PAYPAL_SETUP.md)) |
| ECPay | Taiwan (TWD) | Card checkout |
| Giveme → ECPay | Taiwan | E-invoice issuance (B2C 載具/捐贈, B2B 統編) + void |

Plans: Basic / Pro / Premium / Enterprise subscriptions + credit packs; see
[docs/service-cost.md](./docs/service-cost.md) for the live credit/cost table.

---

## Project Structure

```
Vidgo_Gen_AI/
├── backend/
│   ├── app/
│   │   ├── api/v1/             # 27 routers (tools, interior, einvoices, payments, …)
│   │   ├── core/               # Config, database, security, upload validation
│   │   ├── models/             # SQLAlchemy models
│   │   ├── providers/          # provider_router + PiAPI / Vertex / Pollo REST clients
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── services/           # Business logic (interior, invoice, tier_config, …)
│   │   └── main.py             # FastAPI app
│   ├── alembic/                # Migrations
│   ├── scripts/                # Seeders + brand-asset generation
│   └── Dockerfile
├── frontend-vue/
│   ├── src/
│   │   ├── api/                # API clients
│   │   ├── components/         # Shared components (tools/, invoice/, layout/…)
│   │   ├── data/toolHub.ts     # Tool-hub tile catalog (single source of truth)
│   │   ├── locales/            # i18n (en, zh-TW, ja, ko, es)
│   │   ├── views/tools/        # One page per tool
│   │   ├── views/dashboard/    # MyWorks, Invoices (+發票設定), Referrals
│   │   └── router/
│   ├── Dockerfile.prod         # Production build (used by deploys)
│   └── Dockerfile              # Dev
├── cloudbuild.yaml             # Full CI pipeline (build + push + deploy)
├── docker-compose.yml          # Local stack
├── docs/                       # Architecture & ops docs (see Documentation)
└── README.md
```

---

## Getting Started

### Prerequisites

- Docker 24+ and Docker Compose 2.0+
- API keys: PiAPI (required), Pollo (video backup); GCP ADC for Vertex AI

### Quick Start

```bash
git clone https://github.com/Enuma3lish/Vidgo_Gen_AI.git
cd Vidgo_Gen_AI
cp backend/.env.example backend/.env   # add your API keys
docker compose up -d
```

---

## Accessing the Application

### Docker environment (local)

| Surface | URL | Purpose |
|---|---|---|
| Frontend (Vue app) | http://localhost:8501 | Landing, pricing, tools, dashboard |
| Backend API | http://localhost:8001 | FastAPI server |
| Swagger docs | http://localhost:8001/docs | Interactive API reference |
| Mailpit | http://localhost:8025 | Outbound email — verification codes land here |
| Postgres / Redis | `localhost:5433` / `localhost:6380` | DB `vidgo`, user `postgres` |

**Local admin:** seeded from `FIRST_SUPERUSER_EMAIL` / `FIRST_SUPERUSER_PASSWORD` in `backend/.env`.
**Reset everything:** `docker compose down -v` (⚠ wipes Postgres + materials).

### GCP environment (production)

Backend on **GCP project `vidgo-ai`** (region `asia-east1`); frontend on
**Firebase Hosting** (project `vidgo-gen-ai-prod`):

| Service | URL |
|---|---|
| Frontend | https://vidgo.co (Firebase Hosting, global CDN) |
| Backend API | https://vidgo-backend-38714015566.asia-east1.run.app |
| Background tasks | Cloud Scheduler → `POST /api/v1/tasks/*` (no public UI, no worker service) |

```bash
# Health checks
curl -s https://vidgo-backend-38714015566.asia-east1.run.app/health
curl -I https://vidgo.co

# Logs
gcloud run services logs tail vidgo-backend --project vidgo-ai --region asia-east1
```

⚠ **Production actions burn real credits and can charge real users.**

**Deploying:** see [docs/DEPLOYMENT_GUIDE.md](./docs/DEPLOYMENT_GUIDE.md) —
backend via Cloud Build (`cloudbuild.yaml`) or local build → Artifact Registry →
`gcloud run services update`; frontend via `firebase deploy --only hosting`.
Full bring-up: [`gcp/deploy.sh`](./gcp/deploy.sh). Apply DB migrations **before**
deploying a backend that contains them.

---

## Configuration

```env
# backend/.env (excerpt — see .env.example for the full list)

# AI Providers
PIAPI_KEY=your_piapi_key                # Primary provider (REST)
POLLO_API_KEY=your_pollo_key            # Video backup lane
VERTEX_AI_PROJECT=vidgo-ai              # Vertex AI via ADC (GEMINI_API_KEY is retired)
VERTEX_AI_GENAI_LOCATION=us-central1    # gemini-2.5-flash-image region

# Provider recovery
PROVIDER_CIRCUIT_BREAKER_FAILURES=3
PROVIDER_CIRCUIT_BREAKER_COOLDOWN_SECONDS=180

# Storage
GCS_BUCKET=vidgo-media-vidgo-ai

# Payments — Taiwan
ECPAY_ENV=production
ECPAY_MERCHANT_ID=...
ECPAY_HASH_KEY=...
ECPAY_HASH_IV=...
# E-invoice via Giveme (primary when enabled; ECPay e-invoice is the fallback)
GIVEME_ENABLED=true
GIVEME_IDNO=...

# Payments — International (PayPal is runtime-configurable from the admin UI;
# see docs/PAYPAL_SETUP.md)

# Security / email
SECRET_KEY=...
SMTP_HOST=mailpit          # dev; Gmail App Password on production
SMTP_PORT=1025
```

### Pre-generation Control

| Variable | Default | Description |
|----------|---------|-------------|
| `SKIP_PREGENERATION` | `false` | Skip AI API calls on startup (production sets `true`) |
| `PREGENERATION_LIMIT` | `10` | Materials per tool |

### Referral & Upload Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `REGISTRATION_BONUS_CREDITS` | `40` | Credits granted on signup |
| `REFERRAL_BONUS_CREDITS` | `50` | Credits for referrer per successful signup |
| `MAX_UPLOAD_SIZE_MB` | `20` | Max subscriber upload size |

---

## Docker Services

```yaml
services:
  postgres:        # PostgreSQL 15
  redis:           # Redis 7 — local cache (prod uses in-process cache, no Memorystore)
  mailpit:         # Email testing (dev only)
  backend:         # FastAPI (host port 8001)
  init-materials:  # One-time pre-generation (profile: init)
  frontend:        # Vue 3 (host port 8501)
```

```bash
docker compose up -d                          # start
docker compose logs -f backend                # logs
docker compose --profile init up init-materials   # first-time pregen
SKIP_PREGENERATION=true docker compose up -d  # skip pregen
```

---

## Development

### Local Development (Without Docker)

```bash
# Backend
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend-vue && npm install && npm run dev
```

### API Routers (`/api/v1`)

| Prefix | Description |
|--------|-------------|
| `/auth`, `/session` | Authentication, email verification, session tracking |
| `/tools` | All generation tools (try-on, short-video, kling-video, sora2-pro, room-redesign, upscale, …) |
| `/interior` | Interior suite: floorplan, isometric, floorplan-to-video (3D 效果圖), 3D models, redesign |
| `/demo`, `/example`, `/hero`, `/landing` | Preset/demo content + landing data |
| `/generation`, `/uploads`, `/downloads`, `/user-works` | Subscriber generation + work library |
| `/credits`, `/plans`, `/subscriptions`, `/payments`, `/promotions`, `/quota` | Billing, plans, promo codes, quotas |
| `/einvoices` | Taiwan e-invoice: issue B2C/B2B, void, list, **preferences (發票設定)** |
| `/referrals`, `/social-media`, `/share-proxy` | Referrals + social publishing |
| `/admin`, `/admin-models` | Admin dashboard + model registry overrides |
| `/prompts`, `/effects`, `/workflow` | Prompt library, style effects, workflows |

---

## Security & Anti-Abuse

| Mechanism | Implementation |
|-----------|---------------|
| Rate limiting | Per-IP and per-email limits on registration and generation (Redis-backed when present; Postgres/in-process fallback in prod) |
| CAPTCHA | Google reCAPTCHA v2 on registration |
| Watermarking | All demo outputs watermarked; subscribers get clean output |
| Credit gating | Generation endpoints check balance before processing; deduct-then-refund on failure (deduction firewall, `ServicePricing` overrides) |
| Custom-prompt gate | Custom prompts / premium models require active subscription + bound card |
| Pending-task recovery | Long video jobs recorded in `PendingProviderTask` before polling so Cloud Run restarts don't lose paid generations |

---

## Documentation

| Doc | Content |
|---|---|
| [docs/vidgo-backend-architecture.md](./docs/vidgo-backend-architecture.md) | Backend architecture: routers, providers, services, billing |
| [docs/vidgo-frontend-architecture.md](./docs/vidgo-frontend-architecture.md) | Frontend architecture: routes, tool hub, components |
| [docs/vidgo-infra-architecture.md](./docs/vidgo-infra-architecture.md) | GCP infrastructure: Cloud Run, Cloud SQL, networking, CI |
| [docs/DEPLOYMENT_GUIDE.md](./docs/DEPLOYMENT_GUIDE.md) | How to build, migrate, and deploy |
| [docs/setup_guide.md](./docs/setup_guide.md) | First-time production bring-up (DNS, SSL, payments) |
| [docs/dns-and-ecpay-setup.md](./docs/dns-and-ecpay-setup.md) | GoDaddy DNS + ECPay merchant setup |
| [docs/PAYPAL_SETUP.md](./docs/PAYPAL_SETUP.md) | PayPal sandbox→production runtime config |
| [docs/service-cost.md](./docs/service-cost.md) | Credit pricing vs API cost / margin analysis |
| [docs/example-mode-cache-system.md](./docs/example-mode-cache-system.md) | Demo cache-through system |
| [docs/vidgo-project-supplement.md](./docs/vidgo-project-supplement.md) | Business value & strategy notes |

---

## Supported Languages

`en` English · `zh-TW` Traditional Chinese · `ja` Japanese · `ko` Korean · `es` Spanish

---

*Last Updated: June 12, 2026*
