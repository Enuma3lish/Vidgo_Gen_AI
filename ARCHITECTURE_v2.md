# VidGo - Architecture Documentation

## System Overview

VidGo is a 4-tier **AI Product Ads Video Generation Platform** (Demo / Starter / Pro / Pro+) that helps users create professional product advertising videos from text prompts or product images. Built with **Leonardo AI** as the primary generation service, featuring **Gemini AI** for intelligent prompt enhancement and content moderation, and **prompt similarity caching** to optimize costs.

### Core Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Product Focus** | Create product ads videos from text or images |
| 4-Tier Service | Demo → Starter → Pro → Pro+ |
| Primary Generation | Leonardo AI (image + video generation) |
| Enhancement Effects | VidGo Effects (powered by GoEnhance, subscribers only) |
| Future Multi-Model | VidGo Advanced Models (via Pollo API aggregator) |
| Prompt Enhancement | Gemini AI improves user prompts |
| Content Moderation | Gemini AI (18+ / illegal content detection) |
| Similarity Caching | 85% similar prompts reuse cached results |
| **Weekly Credit System** | All services consume credits, refresh weekly |
| Multi-language | EN / JA / ZH-TW / KO / ES |
| Dual Payment | ECPay (Taiwan) + Paddle (International) |
| **Email Verification** | 6-digit code verification to activate account |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                      Streamlit Frontend                             │    │
│  │                         (Port 8501)                                 │    │
│  │                                                                     │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │    │
│  │  │Product Ads   │  │ Inspiration  │  │    User      │             │    │
│  │  │Video Creator │  │   Gallery    │  │  Dashboard   │             │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │    │
│  │                                                                     │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │    │
│  │  │ 5-Language   │  │ Subscription │  │VidGo Effects │             │    │
│  │  │   Support    │  │  Management  │  │(Subscribers) │             │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                                     │ HTTP/REST (JSON)
                                     │
┌────────────────────────────────────┼────────────────────────────────────────┐
│                          APPLICATION LAYER                                   │
│                                    │                                         │
│  ┌─────────────────────────────────┴─────────────────────────────────────┐ │
│  │                     FastAPI Backend (Port 8000)                        │ │
│  │                                                                        │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │ │
│  │  │    Auth     │  │ Generation  │  │   Credit    │  │  Payments   │  │ │
│  │  │   Service   │  │   Service   │  │   Service   │  │  (ECPay/    │  │ │
│  │  │(JWT+Email)  │  │ (Leonardo)  │  │  (Weekly)   │  │   Paddle)   │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │ │
│  │                                                                        │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │ │
│  │  │   Content   │  │  Prompt     │  │ Similarity  │  │VidGo Effects│  │ │
│  │  │ Moderation  │  │Enhancement  │  │   Cache     │  │  Service    │  │ │
│  │  │  (Gemini)   │  │  (Gemini)   │  │  Service    │  │ (GoEnhance) │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────────┐
│                           AI SERVICES LAYER                                  │
│                                    │                                         │
│      ┌─────────────────────────────┴─────────────────────────────────┐     │
│      │                   Credit-Based Generation Flow                 │     │
│      │                                                                │     │
│      │   1. Check Weekly Credit Balance                               │     │
│      │   2. Content Moderation (Gemini) - Block unsafe content       │     │
│      │   3. Prompt Enhancement (Gemini) - Improve for better results │     │
│      │   4. Similarity Check - Find cached results (>85% match)      │     │
│      │   5. Generate New (Leonardo) - If no cache hit               │     │
│      │   6. Deduct Credits - Record transaction                      │     │
│      │   7. Cache Result - Store for future matching                 │     │
│      └────────────────────────────────────────────────────────────────┘     │
│                                    │                                         │
│              ┌─────────────────────┴─────────────────────┐                  │
│              │                                           │                  │
│   ┌──────────┴──────────┐                   ┌───────────┴───────────┐      │
│   │  GENERATION SERVICES│                   │   ENHANCEMENT SERVICES │      │
│   │  (All Tiers)        │                   │   (Subscribers Only)   │      │
│   │                     │                   │                        │      │
│   │  ┌───────────────┐  │                   │  ┌─────────────────┐   │      │
│   │  │  Leonardo AI  │  │                   │  │   Gemini AI     │   │      │
│   │  │   (Primary)   │  │                   │  │ - Enhancement   │   │      │
│   │  │  Image+Video  │  │                   │  │ - Moderation    │   │      │
│   │  │  Phoenix+SVD  │  │                   │  │ - Embeddings    │   │      │
│   │  └───────────────┘  │                   │  └─────────────────┘   │      │
│   │                     │                   │                        │      │
│   │  ┌───────────────┐  │                   │  ┌─────────────────┐   │      │
│   │  │   Runway      │  │                   │  │  VidGo Effects  │   │      │
│   │  │  (Fallback)   │  │                   │  │ (GoEnhance API) │   │      │
│   │  └───────────────┘  │                   │  │ - Style Transfer│   │      │
│   │                     │                   │  │ - 4K Upscale    │   │      │
│   └─────────────────────┘                   │  │ - Video Enhance │   │      │
│                                             │  └─────────────────┘   │      │
│   ┌─────────────────────┐                   │                        │      │
│   │ VidGo Advanced      │                   └────────────────────────┘      │
│   │ Models (Pollo API)  │                                                   │
│   │ (Pro/Pro+ Only)     │                                                   │
│   │ - Wan 2.2           │                                                   │
│   │ - Veo 3.1           │                                                   │
│   │ - Kling (Pro+ only) │                                                   │
│   │ - Runway Gen-3      │                                                   │
│   └─────────────────────┘                                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│                                                                              │
│           ┌─────────────────────┬───────────────────────┐                   │
│           │                     │                       │                   │
│           ▼                     ▼                       ▼                   │
│  ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────┐   │
│  │   PostgreSQL 15     │   │      Redis 7        │   │  Object Storage │   │
│  │   (Port 5432)       │   │   (Port 6379)       │   │   (CDN URLs)    │   │
│  │                     │   │                     │   │                 │   │
│  │  - Users            │   │  - Session Cache    │   │  - Images       │   │
│  │  - EmailVerification│   │  - Block Cache      │   │  - Videos       │   │
│  │  - Plans            │   │  - Rate Limiting    │   │  - Thumbnails   │   │
│  │  - Subscriptions    │   │  - Credit Lock      │   │                 │   │
│  │  - CreditTransactions│  │  - Weekly Reset Job │   │                 │   │
│  │  - CreditPackages   │   │  - Online Users     │   │                 │   │
│  │  - ServicePricing   │   │                     │   │                 │   │
│  │  - PromptCache      │   │                     │   │                 │   │
│  └─────────────────────┘   └─────────────────────┘   └─────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## White-Label Service Mapping

> **Important**: All external APIs are white-labeled as VidGo's own features to users.

| User-Facing Name | Internal Service | API Provider |
|------------------|------------------|--------------|
| **VidGo Video** | Primary video generation | Leonardo AI |
| **VidGo Image** | Primary image generation | Leonardo AI |
| **VidGo Style Effects** | Style transformation | GoEnhance API |
| **VidGo HD Enhance** | 4K upscale | GoEnhance API |
| **VidGo Video Pro** | Video enhancement | GoEnhance API |
| **VidGo Advanced Models** | Multi-model hub (Pro/Pro+ only) | Pollo API |
| **VidGo 台語配音** | Taiwanese TTS | ATEN AI Voice |
| **VidGo 數位人** | AI Avatar video | Leonardo AI + TTS |
| **VidGo 台語代言人** | Taiwanese Avatar video | ATEN + Leonardo |

---

## Technology Stack

### Backend (FastAPI)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | FastAPI 0.109.0 | High-performance async API |
| Server | Uvicorn 0.27.0 | ASGI server |
| Database | SQLAlchemy 2.0.25 (async) | ORM with async support |
| Migration | Alembic 1.13.1 | Database migrations |
| DB Driver | asyncpg 0.29.0 | Async PostgreSQL driver |
| Validation | Pydantic 2.5.3 | Request/response validation |
| Auth | python-jose + passlib | JWT tokens + password hashing |
| HTTP Client | httpx 0.26.0 | Async HTTP for external APIs |
| Task Queue | Celery + Redis | Weekly credit reset job |

### Frontend (Streamlit)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | Streamlit 1.30.0 | Rapid UI development |
| Main App | front_app.py | Product Ads Video creator |
| i18n | Built-in translations | 5-language support |
| Styling | Custom CSS | Light theme, brand consistency |

### Infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| Database | PostgreSQL 15 | Primary data storage |
| Cache | Redis 7 | Cache + queue + rate limiting + credit locks |
| Containers | Docker + docker-compose | Service orchestration |
| Hosting | Hetzner/Linode | Cost-effective VPS |
| CDN | Leonardo AI CDN | Image/video delivery |
| Scheduler | Celery Beat | Weekly credit reset |

### External AI Services

| Service | Purpose | User-Facing Name | Status |
|---------|---------|------------------|--------|
| Leonardo AI | Primary image & video generation | VidGo Video/Image | ✅ Integrated |
| Gemini API | Prompt enhancement, moderation, embeddings | (Internal) | ✅ Integrated |
| GoEnhance | Style transfer, 4K upscale, video enhance | VidGo Effects | ✅ Integrated |
| Runway | Fallback video generation + Avatar backup | (Fallback) | ✅ Integrated |
| Pollo AI | Multi-model hub (Pro/Pro+) | VidGo Advanced Models | ✅ Integrated |

---

## Weekly Credit System Architecture

### Credit Refresh Schedule

```
Every Monday 00:00 UTC:
┌─────────────────────────────────────────────────────────┐
│                  WEEKLY CREDIT RESET JOB                 │
│                                                          │
│  1. Query all active subscribers                        │
│  2. Reset subscription_credits to plan's weekly_credits │
│  3. Record reset in credit_transactions                 │
│  4. Send email notification (optional)                  │
│                                                          │
│  Starter: Reset to 25 pts                               │
│  Pro:     Reset to 60 pts                               │
│  Pro+:    Reset to 125 pts                              │
│  Demo:    No reset (one-time 2 free uses)               │
└─────────────────────────────────────────────────────────┘
```

### Credit Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      CREDIT ACQUISITION                          │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Subscription │  │   Top-up     │  │    Bonus     │          │
│  │   Credits    │  │   Credits    │  │   Credits    │          │
│  │ (Weekly)     │  │ (Permanent)  │  │ (90 days)    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         └─────────────────┼─────────────────┘                   │
│                           ▼                                     │
│                  ┌─────────────────┐                           │
│                  │  Credit Wallet  │                           │
│                  │ (Total Balance) │                           │
│                  └────────┬────────┘                           │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────┼─────────────────────────────────────┐
│                      CREDIT CONSUMPTION                          │
│                            │                                     │
│         ┌──────────────────┼──────────────────┐                 │
│         ▼                  ▼                  ▼                 │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐           │
│  │  Leonardo   │   │VidGo Effects│   │   Runway    │           │
│  │ 5-8 pts/vid │   │ 8-12 pts    │   │  (Fallback) │           │
│  │ (All users) │   │(Subscribers)│   │  15 pts     │           │
│  └─────────────┘   └─────────────┘   └─────────────┘           │
│                                                                  │
│  Deduction Priority: Bonus → Subscription → Purchased           │
└──────────────────────────────────────────────────────────────────┘
```

### Service Access Control

| Service | Demo | Starter | Pro | Pro+ |
|---------|------|---------|-----|------|
| Leonardo Video 720p | ✅ (cached only) | ✅ | ✅ | ✅ |
| Leonardo Video 1080p | ❌ | ✅ | ✅ | ✅ |
| Leonardo Video 4K | ❌ | ❌ | ✅ | ✅ |
| Priority Queue | ❌ | ❌ | ✅ | ✅ |

#### GoEnhance Services (All Tiers)

| Service | Demo | Starter | Pro | Pro+ |
|---------|------|---------|-----|------|
| VidGo Style Effects (Basic) | ✅ (3 pts) | ✅ (3 pts) | ✅ (3 pts) | ✅ (2 pts) |
| VidGo Style Effects (Pro) | ❌ | ✅ (6 pts) | ✅ (5 pts) | ✅ (4 pts) |
| VidGo HD Enhance | ❌ | ✅ (8 pts) | ✅ (7 pts) | ✅ (5 pts) |
| VidGo Video Pro | ❌ | ✅ (10 pts) | ✅ (8 pts) | ✅ (6 pts) |

#### Pollo AI Services (Pro/Pro+ Only)

| Service | Demo | Starter | Pro | Pro+ |
|---------|------|---------|-----|------|
| VidGo Wan 2.2 | ❌ | ❌ | ✅ (8 pts) | ✅ (6 pts) |
| VidGo Veo 3.1 | ❌ | ❌ | ✅ (15 pts) | ✅ (12 pts) |
| VidGo Kling | ❌ | ❌ | ❌ | ✅ (18 pts) |
| VidGo Runway Gen-3 | ❌ | ❌ | ✅ (12 pts) | ✅ (10 pts) |

---

## Email Verification System

### Verification Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                    EMAIL VERIFICATION FLOW                        │
│                                                                   │
│  ┌─────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │  User   │───▶│  Register   │───▶│  Generate   │              │
│  │ Submit  │    │   (POST)    │    │ 6-digit Code│              │
│  └─────────┘    └─────────────┘    └──────┬──────┘              │
│                                           │                      │
│                                           ▼                      │
│                                    ┌─────────────┐              │
│                                    │ Store Code  │              │
│                                    │ in Redis    │              │
│                                    │ (15 min TTL)│              │
│                                    └──────┬──────┘              │
│                                           │                      │
│                                           ▼                      │
│                                    ┌─────────────┐              │
│                                    │ Send Email  │              │
│                                    │ with Code   │              │
│                                    └──────┬──────┘              │
│                                           │                      │
│                                           ▼                      │
│  ┌─────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │  User   │───▶│  Verify     │───▶│  Activate   │              │
│  │Input Code│   │  (POST)     │    │   Account   │              │
│  └─────────┘    └─────────────┘    └─────────────┘              │
│                                                                   │
│  Security:                                                        │
│  - 6-digit numeric code                                          │
│  - 15 minute expiration                                          │
│  - Max 3 attempts per code                                       │
│  - Max 5 resend requests per hour                                │
│  - Account locked until verified                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Verification Code Storage (Redis)

```
Key:    email_verify:{email}
Value:  {
          "code": "123456",
          "attempts": 0,
          "created_at": "2024-12-28T10:00:00Z"
        }
TTL:    900 seconds (15 minutes)

Key:    email_resend_count:{email}
Value:  3
TTL:    3600 seconds (1 hour)
```

---

## Database Schema

### User Model (Updated)

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,           -- Must verify email to use
    
    -- Credit System Fields (Weekly)
    subscription_credits INTEGER DEFAULT 0,      -- Weekly credits (reset each week)
    purchased_credits INTEGER DEFAULT 0,         -- Top-up credits (never expire)
    bonus_credits INTEGER DEFAULT 0,             -- Promotional credits
    bonus_credits_expiry TIMESTAMPTZ,            -- When bonus credits expire
    credits_reset_at TIMESTAMPTZ,                -- Last weekly reset timestamp
    
    -- Plan Info
    current_plan_id UUID REFERENCES plans(id),
    plan_started_at TIMESTAMPTZ,
    plan_expires_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_plan ON users(current_plan_id);
CREATE INDEX idx_users_verified ON users(is_verified);
```

### Email Verification Model (New)

```sql
-- Note: Primary verification uses Redis for speed
-- This table stores verification history for audit

CREATE TABLE email_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    code_hash VARCHAR(255) NOT NULL,             -- Hashed 6-digit code
    attempts INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',        -- pending, verified, expired, failed
    expires_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_email_verify_user ON email_verifications(user_id, created_at DESC);
CREATE INDEX idx_email_verify_status ON email_verifications(status, expires_at);
```

### Plan Model (Updated for Weekly Credits)

```sql
CREATE TABLE plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL,                    -- demo, starter, pro, pro_plus
    display_name VARCHAR(100) NOT NULL,           -- Display name (i18n key)
    price_twd DECIMAL(10,2) DEFAULT 0,            -- Monthly price in TWD
    price_usd DECIMAL(10,2) DEFAULT 0,            -- Monthly price in USD
    
    -- Credit Allocation (WEEKLY)
    weekly_credits INTEGER DEFAULT 0,             -- Credits per week
    
    -- Discounts
    topup_discount_rate DECIMAL(3,2) DEFAULT 0,   -- 0.00 = no discount, 0.20 = 20% off
    
    -- Features
    max_resolution VARCHAR(20) DEFAULT '720p',    -- 720p, 1080p, 4k
    has_watermark BOOLEAN DEFAULT TRUE,
    priority_queue BOOLEAN DEFAULT FALSE,
    can_use_effects BOOLEAN DEFAULT FALSE,        -- VidGo Effects (GoEnhance) access
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed Plans (Weekly Credits)
INSERT INTO plans (name, display_name, price_twd, weekly_credits, topup_discount_rate, max_resolution, has_watermark, priority_queue, can_use_effects) VALUES
('demo', 'Demo', 0, 0, 0, '720p', true, false, false),
('starter', 'Starter', 299, 25, 0, '1080p', false, false, true),
('pro', 'Pro', 599, 60, 0.10, '4k', false, true, true),
('pro_plus', 'Pro+', 999, 125, 0.20, '4k', false, true, true);
```

### Credit Transaction Model

```sql
CREATE TABLE credit_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Transaction Details
    amount INTEGER NOT NULL,                      -- Positive = credit, Negative = debit
    balance_after INTEGER NOT NULL,               -- Balance after transaction
    
    -- Transaction Type
    transaction_type VARCHAR(50) NOT NULL,        -- generation, purchase, weekly_reset, refund, bonus, expiry
    
    -- For generation transactions
    service_type VARCHAR(50),                     -- leonardo_video, vidgo_style, runway
    generation_id UUID,                           -- Reference to generation record
    
    -- For purchase transactions
    package_id UUID REFERENCES credit_packages(id),
    payment_id VARCHAR(255),                      -- External payment reference
    
    -- Metadata
    description TEXT,
    metadata JSONB,                               -- Additional data (resolution, duration, etc.)
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_credit_tx_user ON credit_transactions(user_id, created_at DESC);
CREATE INDEX idx_credit_tx_type ON credit_transactions(transaction_type, created_at DESC);
```

### Service Pricing Model (Updated)

```sql
CREATE TABLE service_pricing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_type VARCHAR(50) NOT NULL UNIQUE,     -- leonardo_720p, vidgo_style, etc.
    display_name VARCHAR(100) NOT NULL,           -- User-facing name
    
    -- Credit Cost
    credit_cost INTEGER NOT NULL,                 -- Credits per use
    
    -- API Cost (for internal tracking)
    api_cost_usd DECIMAL(10,4) NOT NULL,          -- Actual API cost in USD
    
    -- Access Control
    min_plan VARCHAR(50),                         -- Minimum plan required (NULL = all)
    subscribers_only BOOLEAN DEFAULT FALSE,       -- Requires paid subscription
    
    -- Metadata
    description TEXT,
    resolution VARCHAR(20),
    max_duration INTEGER,                         -- Max duration in seconds
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Seed Service Pricing (White-labeled names)
INSERT INTO service_pricing (service_type, display_name, credit_cost, api_cost_usd, resolution, max_duration, subscribers_only) VALUES
-- Leonardo Services (All tiers)
('leonardo_video_720p', 'VidGo Video 720p', 5, 0.05, '720p', 8, false),
('leonardo_video_1080p', 'VidGo Video 1080p', 8, 0.08, '1080p', 8, false),
('leonardo_video_4k', 'VidGo Video 4K', 12, 0.12, '4k', 8, false),
('leonardo_image_512', 'VidGo Image 512px', 2, 0.015, '512x512', NULL, false),
('leonardo_image_1024', 'VidGo Image 1024px', 3, 0.025, '1024x1024', NULL, false),

-- VidGo Effects (GoEnhance - Subscribers Only)
('vidgo_style', 'VidGo Style Effects', 8, 0.15, NULL, NULL, true),
('vidgo_hd_enhance', 'VidGo HD Enhance', 10, 0.20, '4k', NULL, true),
('vidgo_video_pro', 'VidGo Video Pro', 12, 0.25, NULL, NULL, true),

-- Runway (Fallback - internal use)
('runway_720p', 'Runway Fallback 720p', 15, 0.50, '720p', 8, false),

-- GoEnhance Services (All Tiers - different credit costs per tier)
('goenhance_style_basic', 'VidGo Style Effects (Basic)', 3, 0.10, NULL, NULL, false),
('goenhance_style_pro', 'VidGo Style Effects (Pro)', 6, 0.15, NULL, NULL, true),
('goenhance_4k', 'VidGo HD Enhance', 8, 0.20, '4k', NULL, true),
('goenhance_video', 'VidGo Video Pro', 10, 0.25, NULL, NULL, true),

-- Pollo AI Services (Pro/Pro+ Only)
('pollo_wan', 'VidGo Wan 2.2', 8, 0.10, '720p', 4, true),
('pollo_veo', 'VidGo Veo 3.1', 15, 0.20, '1080p', 6, true),
('pollo_kling', 'VidGo Kling', 18, 0.30, '1080p', 8, true),
('pollo_runway', 'VidGo Runway Gen-3', 12, 0.25, '1080p', 6, true);
```

---

## API Endpoints

### Authentication (Updated)

```
POST   /api/v1/auth/register            Register new user (sends verification code)
POST   /api/v1/auth/verify-email        Verify email with 6-digit code
POST   /api/v1/auth/resend-code         Resend verification code
POST   /api/v1/auth/login               Login (requires verified email)
POST   /api/v1/auth/refresh             Refresh access token
GET    /api/v1/auth/me                  Get current user info
POST   /api/v1/auth/forgot-password     Request password reset
POST   /api/v1/auth/reset-password      Reset password with token
```

### Credit System Endpoints

```
GET    /api/v1/credits/balance          Get current credit balance breakdown
GET    /api/v1/credits/transactions     Get credit transaction history
POST   /api/v1/credits/estimate         Estimate credits for a generation
GET    /api/v1/credits/packages         Get available credit packages
POST   /api/v1/credits/purchase         Purchase credit package
GET    /api/v1/credits/pricing          Get service pricing table
GET    /api/v1/credits/reset-schedule   Get next weekly reset time
```

### Demo & Generation

```
GET    /api/v1/demo/inspiration         Get random examples for gallery
POST   /api/v1/demo/generate            Generate product ads video
GET    /api/v1/demo/topics              Get available topics with counts
```

### VidGo Effects / GoEnhance (All Tiers)

```
GET    /api/v1/effects/styles           Get available style effects
POST   /api/v1/effects/apply-style      Apply style to image/video
POST   /api/v1/effects/hd-enhance       Upscale to 4K
POST   /api/v1/effects/video-enhance    Enhance video quality
GET    /api/v1/effects/status/{id}      Check processing status
```

### Admin Dashboard (Admin Only)

```
GET    /api/v1/admin/stats/online       Get current online users count
GET    /api/v1/admin/stats/users-by-tier Get user breakdown by subscription tier
GET    /api/v1/admin/stats/dashboard    Get combined dashboard statistics
WS     /api/v1/admin/ws/realtime        WebSocket for real-time updates
```

### VidGo Advanced Models / Pollo AI (Pro/Pro+ Only)

```
GET    /api/v1/models                   List available AI models
GET    /api/v1/models/{model}/info      Get model details and pricing
POST   /api/v1/models/generate          Generate video with selected model
GET    /api/v1/models/status/{id}       Check generation status
GET    /api/v1/models/download/{id}     Download generated video
```

### Plans & Subscriptions

```
GET    /api/v1/plans                    List all plans (public)
GET    /api/v1/plans/current            Get current subscription
POST   /api/v1/plans/subscribe          Subscribe to a plan
POST   /api/v1/plans/cancel             Cancel subscription
```

---

## Service Tiers (Updated - Weekly Credits)

| Tier | Price (Monthly) | Credits/Week | Top-up Discount | Max Resolution | GoEnhance | Pollo AI |
|------|-----------------|--------------|-----------------|----------------|-----------|----------|
| **Demo** | $0 | 2 (one-time) | — | 720p + Watermark | ✅ Basic | ❌ |
| **Starter** | NT$299 | 25 pts | Standard | 1080p | ✅ Full | ❌ |
| **Pro** | NT$599 | 60 pts | 10% off | 4K | ✅ Full | ✅ Basic |
| **Pro+** | NT$999 | 125 pts | 20% off | 4K 60fps | ✅ Full | ✅ Full |

### Service Credit Costs

| Service | User-Facing Name | Credits | API Cost | Access |
|---------|------------------|---------|----------|--------|
| Leonardo Video 720p | VidGo Video 720p | 5 pts | ~$0.05 | All |
| Leonardo Video 1080p | VidGo Video 1080p | 8 pts | ~$0.08 | Starter+ |
| Leonardo Video 4K | VidGo Video 4K | 12 pts | ~$0.12 | Pro+ |
| Leonardo Image 512px | VidGo Image | 2 pts | ~$0.015 | All |
| Leonardo Image 1024px | VidGo Image HD | 3 pts | ~$0.025 | All |
| Runway Fallback | (Internal) | 15 pts | ~$0.50 | Fallback |

#### GoEnhance Services (All Tiers - Tiered Pricing)

| Service | User-Facing Name | Demo | Starter | Pro | Pro+ | API Cost |
|---------|------------------|------|---------|-----|------|----------|
| Style Basic | VidGo Style Effects (Basic) | 3 pts | 3 pts | 3 pts | 2 pts | ~$0.10 |
| Style Pro | VidGo Style Effects (Pro) | ❌ | 6 pts | 5 pts | 4 pts | ~$0.15 |
| 4K Upscale | VidGo HD Enhance | ❌ | 8 pts | 7 pts | 5 pts | ~$0.20 |
| Video Enhance | VidGo Video Pro | ❌ | 10 pts | 8 pts | 6 pts | ~$0.25 |

#### Pollo AI Services (Pro/Pro+ Only - Tiered Pricing)

| Service | User-Facing Name | Demo | Starter | Pro | Pro+ | API Cost |
|---------|------------------|------|---------|-----|------|----------|
| Wan 2.2 | VidGo Wan 2.2 | ❌ | ❌ | 8 pts | 6 pts | ~$0.10 |
| Veo 3.1 | VidGo Veo 3.1 | ❌ | ❌ | 15 pts | 12 pts | ~$0.20 |
| Kling | VidGo Kling | ❌ | ❌ | ❌ | 18 pts | ~$0.30 |
| Runway Gen-3 | VidGo Runway Gen-3 | ❌ | ❌ | 12 pts | 10 pts | ~$0.25 |

---

## Implementation Code

### Email Verification Service

```python
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
import redis.asyncio as redis

class EmailVerificationService:
    CODE_LENGTH = 6
    CODE_EXPIRY_MINUTES = 15
    MAX_ATTEMPTS = 3
    MAX_RESEND_PER_HOUR = 5
    
    def __init__(self, redis_client: redis.Redis, email_service):
        self.redis = redis_client
        self.email_service = email_service
    
    def _generate_code(self) -> str:
        """Generate 6-digit numeric code."""
        return ''.join([str(secrets.randbelow(10)) for _ in range(self.CODE_LENGTH)])
    
    def _hash_code(self, code: str) -> str:
        """Hash code for storage."""
        return hashlib.sha256(code.encode()).hexdigest()
    
    async def send_verification_code(self, email: str) -> Tuple[bool, str]:
        """Send verification code to email."""
        # Check resend limit
        resend_key = f"email_resend_count:{email}"
        resend_count = await self.redis.get(resend_key)
        
        if resend_count and int(resend_count) >= self.MAX_RESEND_PER_HOUR:
            return False, "Too many resend requests. Please wait 1 hour."
        
        # Generate code
        code = self._generate_code()
        
        # Store in Redis
        verify_key = f"email_verify:{email}"
        await self.redis.setex(
            verify_key,
            self.CODE_EXPIRY_MINUTES * 60,
            json.dumps({
                "code_hash": self._hash_code(code),
                "attempts": 0,
                "created_at": datetime.utcnow().isoformat()
            })
        )
        
        # Increment resend counter
        await self.redis.incr(resend_key)
        await self.redis.expire(resend_key, 3600)  # 1 hour TTL
        
        # Send email
        await self.email_service.send_verification_email(email, code)
        
        return True, "Verification code sent"
    
    async def verify_code(self, email: str, code: str) -> Tuple[bool, str]:
        """Verify the submitted code."""
        verify_key = f"email_verify:{email}"
        data = await self.redis.get(verify_key)
        
        if not data:
            return False, "Verification code expired. Please request a new one."
        
        verify_data = json.loads(data)
        
        # Check attempts
        if verify_data["attempts"] >= self.MAX_ATTEMPTS:
            await self.redis.delete(verify_key)
            return False, "Too many failed attempts. Please request a new code."
        
        # Verify code
        if self._hash_code(code) == verify_data["code_hash"]:
            await self.redis.delete(verify_key)
            return True, "Email verified successfully"
        
        # Increment attempts
        verify_data["attempts"] += 1
        await self.redis.setex(
            verify_key,
            self.CODE_EXPIRY_MINUTES * 60,
            json.dumps(verify_data)
        )
        
        remaining = self.MAX_ATTEMPTS - verify_data["attempts"]
        return False, f"Invalid code. {remaining} attempts remaining."
```

### Weekly Credit Reset Service

```python
from celery import Celery
from celery.schedules import crontab
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime

celery_app = Celery('vidgo')

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Weekly credit reset - Every Monday at 00:00 UTC
    sender.add_periodic_task(
        crontab(hour=0, minute=0, day_of_week=1),
        weekly_credit_reset.s(),
        name='weekly-credit-reset'
    )

@celery_app.task
async def weekly_credit_reset():
    """Reset subscription credits for all active subscribers."""
    async with get_db_session() as db:
        # Get all active subscribers with their plans
        query = """
            UPDATE users u
            SET 
                subscription_credits = p.weekly_credits,
                credits_reset_at = NOW()
            FROM plans p
            WHERE u.current_plan_id = p.id
            AND u.is_active = true
            AND u.is_verified = true
            AND p.name != 'demo'
            RETURNING u.id, u.email, p.weekly_credits
        """
        
        result = await db.execute(text(query))
        reset_users = result.fetchall()
        
        # Record transactions
        for user_id, email, weekly_credits in reset_users:
            transaction = CreditTransaction(
                user_id=user_id,
                amount=weekly_credits,
                balance_after=weekly_credits,  # Note: purchased credits not included here
                transaction_type="weekly_reset",
                description=f"Weekly credit reset: {weekly_credits} pts"
            )
            db.add(transaction)
        
        await db.commit()
        
        return f"Reset credits for {len(reset_users)} users"
```

### Credit Service (Updated for Weekly)

```python
class CreditService:
    def __init__(self, db: AsyncSession, redis_client: redis.Redis):
        self.db = db
        self.redis = redis_client
    
    async def get_balance(self, user_id: str) -> dict:
        """Get user's credit balance breakdown."""
        user = await self.db.get(User, user_id)
        return {
            "subscription": user.subscription_credits,
            "purchased": user.purchased_credits,
            "bonus": user.bonus_credits,
            "total": user.subscription_credits + user.purchased_credits + user.bonus_credits,
            "next_reset": self._get_next_monday()
        }
    
    def _get_next_monday(self) -> datetime:
        """Get next Monday 00:00 UTC."""
        today = datetime.utcnow()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0 and today.hour >= 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)
        return next_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    async def check_service_access(self, user_id: str, service_type: str) -> Tuple[bool, str]:
        """Check if user can access a service."""
        user = await self.db.get(User, user_id)
        plan = await self.db.get(Plan, user.current_plan_id) if user.current_plan_id else None
        
        # Get service pricing
        result = await self.db.execute(
            select(ServicePricing).where(ServicePricing.service_type == service_type)
        )
        pricing = result.scalar_one_or_none()
        
        if not pricing:
            return False, "Service not found"
        
        # Check if service requires subscription
        if pricing.subscribers_only:
            if not plan or plan.name == 'demo':
                return False, "This feature requires a paid subscription"
            if not plan.can_use_effects:
                return False, "Your plan does not include VidGo Effects"
        
        # Check credit balance
        balance = await self.get_balance(user_id)
        if balance["total"] < pricing.credit_cost:
            return False, f"Insufficient credits. Need {pricing.credit_cost}, have {balance['total']}"
        
        return True, "OK"
```

---

## Project Structure (Updated)

```
vidgo/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application entry
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── api.py              # API router aggregation
│   │   │   ├── deps.py             # Dependency injection
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py         # Auth + Email verification
│   │   │       ├── credits.py      # Credit system endpoints
│   │   │       ├── demo.py         # Demo + Generation endpoints
│   │   │       ├── effects.py      # VidGo Effects (GoEnhance) - NEW
│   │   │       ├── plans.py        # Plan endpoints
│   │   │       ├── payments.py     # Payment endpoints
│   │   │       └── promotions.py   # Promotion endpoints
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py           # Settings management
│   │   │   ├── database.py         # Async database setup
│   │   │   └── security.py         # JWT + password utilities
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py             # User model (weekly credits)
│   │   │   ├── billing.py          # Plan, Subscription, CreditTransaction
│   │   │   ├── verification.py     # EmailVerification model - NEW
│   │   │   └── demo.py             # DemoExample, PromptCache, Generation
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── user.py             # User Pydantic schemas
│   │   │   ├── auth.py             # Auth schemas (verification) - NEW
│   │   │   ├── credit.py           # Credit schemas
│   │   │   ├── effects.py          # Effects schemas - NEW
│   │   │   ├── plan.py             # Plan schemas
│   │   │   └── promotion.py        # Promotion schemas
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── credit_service.py   # Credit management (weekly)
│   │       ├── email_verify.py     # Email verification service - NEW
│   │       ├── leonardo.py         # Leonardo AI (Image + Video)
│   │       ├── gemini_service.py   # Gemini (Enhancement + Moderation)
│   │       ├── similarity.py       # Prompt similarity matching
│   │       ├── effects_service.py  # VidGo Effects (GoEnhance wrapper) - NEW
│   │       ├── goenhance.py        # GoEnhance API client
│   │       ├── pollo_ai.py         # Pollo AI multi-model hub (Pro/Pro+)
│   │       ├── runway.py           # Runway (Fallback + Avatar backup)
│   │       ├── aten_tts.py         # ATEN AI Voice (Taiwanese TTS)
│   │       ├── avatar_service.py   # AI Avatar (Leonardo + TTS)
│   │       ├── admin_dashboard.py  # Admin Dashboard service - NEW
│   │       ├── moderation.py       # Content moderation
│   │       ├── block_cache.py      # Redis block cache
│   │       └── email_service.py    # Email sending
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py           # Celery configuration - NEW
│   │   └── credit_reset.py         # Weekly credit reset task - NEW
│   ├── scripts/
│   │   ├── seed_demo_examples.py   # Seed demo examples
│   │   └── seed_service_pricing.py # Seed service pricing
│   ├── alembic/
│   │   ├── env.py                  # Alembic configuration
│   │   └── versions/               # Migration files
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/
│   ├── front_app.py                # Streamlit main app
│   ├── components/
│   │   ├── demo.py                 # Demo component
│   │   ├── effects.py              # VidGo Effects component - NEW
│   │   └── admin_dashboard.py      # Admin Dashboard component - NEW
│   ├── translations/               # i18n files
│   └── .streamlit/
│       └── config.toml             # Theme configuration
├── docker-compose.yml
├── DEVELOPMENT_PLAN.md             # Development timeline
├── ARCHITECTURE.md                 # This file
├── CREDIT_CONSUMPTION_SPEC.md      # Credit system specification
├── BREAK_EVEN_ANALYSIS.md          # Financial analysis
├── CHANGELOG.md                    # Modification history
└── README.md
```

---

## Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/vidgo

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key
ALGORITHM=HS256

# AI Services
LEONARDO_API_KEY=your-leonardo-key
GEMINI_API_KEY=your-gemini-key
GOENHANCE_API_KEY=your-goenhance-key
POLLO_API_KEY=your-pollo-key
RUNWAY_API_KEY=your-runway-key

# Taiwanese TTS
ATEN_API_KEY=your-aten-api-key
ATEN_API_URL=https://api.aivoice.com.tw

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@vidgo.ai

# Payments
ECPAY_MERCHANT_ID=your-merchant-id
ECPAY_HASH_KEY=your-hash-key
ECPAY_HASH_IV=your-hash-iv
PADDLE_VENDOR_ID=your-vendor-id
PADDLE_API_KEY=your-paddle-key

# Celery (for scheduled tasks)
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

---

## Admin Dashboard Architecture

### Real-Time Online Users Tracking

The admin dashboard uses Redis to track online users in real-time with session-based tracking.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ADMIN DASHBOARD SYSTEM                               │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                      Real-Time User Tracking                        │    │
│  │                                                                     │    │
│  │  User Login/Activity                                                │    │
│  │        ↓                                                            │    │
│  │  ┌─────────────────┐    ┌─────────────────┐                        │    │
│  │  │  Update Redis   │───▶│  Online Users   │                        │    │
│  │  │  Session Key    │    │  Sorted Set     │                        │    │
│  │  └─────────────────┘    └─────────────────┘                        │    │
│  │        ↓                        │                                   │    │
│  │  Heartbeat (every 30s)          │                                   │    │
│  │        ↓                        ▼                                   │    │
│  │  ┌─────────────────┐    ┌─────────────────┐                        │    │
│  │  │  Expire Inactive│───▶│  Admin Dashboard│                        │    │
│  │  │  (5 min timeout)│    │  Real-time View │                        │    │
│  │  └─────────────────┘    └─────────────────┘                        │    │
│  │                                                                     │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                      Dashboard Components                           │    │
│  │                                                                     │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │    │
│  │  │   Online     │  │ Users by     │  │   Active     │             │    │
│  │  │   Users      │  │   Tier       │  │  Sessions    │             │    │
│  │  │   Counter    │  │  Breakdown   │  │   List       │             │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │    │
│  │                                                                     │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │    │
│  │  │  Generation  │  │   Revenue    │  │   Credit     │             │    │
│  │  │   Stats      │  │   Overview   │  │   Usage      │             │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │    │
│  │                                                                     │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Redis Keys for Online Tracking

```
Key:    online_users
Type:   Sorted Set (ZSET)
Score:  Unix timestamp of last activity
Value:  user_id

Key:    user_session:{user_id}
Type:   Hash
Value:  {
          "plan": "pro",
          "email": "user@example.com",
          "last_activity": "2024-12-29T10:00:00Z",
          "ip_address": "192.168.1.1",
          "user_agent": "Mozilla/5.0..."
        }
TTL:    300 seconds (5 minutes)

Key:    online_count_by_tier
Type:   Hash
Value:  {
          "demo": 15,
          "starter": 42,
          "pro": 28,
          "pro_plus": 12
        }
```

### Admin Dashboard Database Schema

```sql
-- Admin users table (separate from regular users)
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'admin',          -- admin, super_admin
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- User activity log for analytics
CREATE TABLE user_activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    activity_type VARCHAR(50) NOT NULL,        -- login, generation, payment, etc.
    plan_at_time VARCHAR(50),                  -- User's plan during activity
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_activity_user ON user_activity_log(user_id, created_at DESC);
CREATE INDEX idx_activity_type ON user_activity_log(activity_type, created_at DESC);
CREATE INDEX idx_activity_plan ON user_activity_log(plan_at_time, created_at DESC);
```

### Admin Dashboard Service Implementation

```python
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

class AdminDashboardService:
    ONLINE_TIMEOUT_SECONDS = 300  # 5 minutes
    HEARTBEAT_INTERVAL = 30  # 30 seconds

    def __init__(self, redis_client: redis.Redis, db: AsyncSession):
        self.redis = redis_client
        self.db = db

    async def update_user_activity(self, user_id: str, plan: str, email: str,
                                    ip_address: str = None, user_agent: str = None):
        """Update user's online status and session info."""
        now = datetime.utcnow()
        timestamp = now.timestamp()

        # Update sorted set for online users
        await self.redis.zadd("online_users", {user_id: timestamp})

        # Update session info
        session_key = f"user_session:{user_id}"
        await self.redis.hset(session_key, mapping={
            "plan": plan,
            "email": email,
            "last_activity": now.isoformat(),
            "ip_address": ip_address or "",
            "user_agent": user_agent or ""
        })
        await self.redis.expire(session_key, self.ONLINE_TIMEOUT_SECONDS)

        # Update tier count cache
        await self._update_tier_counts()

    async def _update_tier_counts(self):
        """Recalculate online users by tier."""
        cutoff = datetime.utcnow().timestamp() - self.ONLINE_TIMEOUT_SECONDS

        # Get all online user IDs
        online_users = await self.redis.zrangebyscore(
            "online_users", cutoff, "+inf"
        )

        # Count by tier
        tier_counts = {"demo": 0, "starter": 0, "pro": 0, "pro_plus": 0}

        for user_id in online_users:
            session_key = f"user_session:{user_id.decode()}"
            plan = await self.redis.hget(session_key, "plan")
            if plan:
                plan_name = plan.decode()
                if plan_name in tier_counts:
                    tier_counts[plan_name] += 1

        # Store counts
        await self.redis.hset("online_count_by_tier", mapping=tier_counts)

    async def get_online_users_count(self) -> int:
        """Get total number of online users."""
        cutoff = datetime.utcnow().timestamp() - self.ONLINE_TIMEOUT_SECONDS
        return await self.redis.zcount("online_users", cutoff, "+inf")

    async def get_users_by_tier(self) -> Dict[str, int]:
        """Get online user count breakdown by subscription tier."""
        counts = await self.redis.hgetall("online_count_by_tier")
        return {
            "demo": int(counts.get(b"demo", 0)),
            "starter": int(counts.get(b"starter", 0)),
            "pro": int(counts.get(b"pro", 0)),
            "pro_plus": int(counts.get(b"pro_plus", 0)),
            "total": await self.get_online_users_count()
        }

    async def get_online_users_list(self, limit: int = 50) -> List[Dict]:
        """Get list of currently online users with details."""
        cutoff = datetime.utcnow().timestamp() - self.ONLINE_TIMEOUT_SECONDS

        # Get online user IDs (most recent first)
        online_users = await self.redis.zrevrangebyscore(
            "online_users", "+inf", cutoff, start=0, num=limit
        )

        users = []
        for user_id in online_users:
            session_key = f"user_session:{user_id.decode()}"
            session = await self.redis.hgetall(session_key)
            if session:
                users.append({
                    "user_id": user_id.decode(),
                    "email": session.get(b"email", b"").decode(),
                    "plan": session.get(b"plan", b"").decode(),
                    "last_activity": session.get(b"last_activity", b"").decode()
                })

        return users

    async def get_dashboard_stats(self) -> Dict:
        """Get combined dashboard statistics."""
        # Get online stats
        online_by_tier = await self.get_users_by_tier()

        # Get total registered users by tier from database
        query = select(
            Plan.name,
            func.count(User.id)
        ).join(User, User.current_plan_id == Plan.id).group_by(Plan.name)

        result = await self.db.execute(query)
        total_by_tier = {row[0]: row[1] for row in result.fetchall()}

        # Get today's stats
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)

        return {
            "online": online_by_tier,
            "total_users": total_by_tier,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def cleanup_inactive_users(self):
        """Remove expired sessions from online users set."""
        cutoff = datetime.utcnow().timestamp() - self.ONLINE_TIMEOUT_SECONDS
        await self.redis.zremrangebyscore("online_users", "-inf", cutoff)
```

### Admin Dashboard API Endpoints

```python
from fastapi import APIRouter, Depends, HTTPException, WebSocket
from fastapi.websockets import WebSocketDisconnect
import asyncio

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

@router.get("/stats/online")
async def get_online_users(
    admin: AdminUser = Depends(get_current_admin),
    dashboard: AdminDashboardService = Depends(get_dashboard_service)
):
    """Get current online users count."""
    count = await dashboard.get_online_users_count()
    return {"online_users": count, "timestamp": datetime.utcnow().isoformat()}

@router.get("/stats/users-by-tier")
async def get_users_by_tier(
    admin: AdminUser = Depends(get_current_admin),
    dashboard: AdminDashboardService = Depends(get_dashboard_service)
):
    """Get online user breakdown by subscription tier."""
    return await dashboard.get_users_by_tier()

@router.get("/stats/dashboard")
async def get_dashboard(
    admin: AdminUser = Depends(get_current_admin),
    dashboard: AdminDashboardService = Depends(get_dashboard_service)
):
    """Get combined dashboard statistics."""
    return await dashboard.get_dashboard_stats()

@router.get("/stats/online-users-list")
async def get_online_users_list(
    limit: int = 50,
    admin: AdminUser = Depends(get_current_admin),
    dashboard: AdminDashboardService = Depends(get_dashboard_service)
):
    """Get list of currently online users."""
    return await dashboard.get_online_users_list(limit=limit)

@router.websocket("/ws/realtime")
async def realtime_stats(
    websocket: WebSocket,
    dashboard: AdminDashboardService = Depends(get_dashboard_service)
):
    """WebSocket for real-time dashboard updates."""
    await websocket.accept()

    try:
        while True:
            stats = await dashboard.get_dashboard_stats()
            await websocket.send_json(stats)
            await asyncio.sleep(5)  # Update every 5 seconds
    except WebSocketDisconnect:
        pass
```

### Frontend Admin Dashboard Component

```python
# frontend/components/admin_dashboard.py
import streamlit as st
import requests
import time

def render_admin_dashboard():
    st.title("🎛️ VidGo Admin Dashboard")

    # Auto-refresh toggle
    auto_refresh = st.sidebar.checkbox("Auto-refresh (5s)", value=True)

    # Online Users Section
    col1, col2, col3, col4, col5 = st.columns(5)

    stats = fetch_dashboard_stats()

    with col1:
        st.metric("👥 Total Online", stats["online"]["total"])

    with col2:
        st.metric("🆓 Demo", stats["online"]["demo"])

    with col3:
        st.metric("⭐ Starter", stats["online"]["starter"])

    with col4:
        st.metric("🚀 Pro", stats["online"]["pro"])

    with col5:
        st.metric("💎 Pro+", stats["online"]["pro_plus"])

    # Tier Breakdown Chart
    st.subheader("📊 Online Users by Tier")
    tier_data = {
        "Tier": ["Demo", "Starter", "Pro", "Pro+"],
        "Count": [
            stats["online"]["demo"],
            stats["online"]["starter"],
            stats["online"]["pro"],
            stats["online"]["pro_plus"]
        ]
    }
    st.bar_chart(tier_data, x="Tier", y="Count")

    # Online Users List
    st.subheader("👤 Currently Online Users")
    users = fetch_online_users_list()
    st.dataframe(users, use_container_width=True)

    if auto_refresh:
        time.sleep(5)
        st.rerun()
```

---

## Development Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Core Infrastructure (FastAPI, PostgreSQL, JWT) | ✅ Complete |
| 2 | Content Moderation + Prompt Enhancement | ✅ Complete |
| 3 | Leonardo AI + Similarity Caching | ✅ Complete |
| 4 | GoEnhance Integration (VidGo Effects - All Tiers) | ✅ Complete |
| 5 | UI/UX (Product Ads Video, 5 Languages) | ✅ Complete |
| 6 | **Weekly Credit System** | 🔄 Updated |
| 7 | **Email Verification (6-digit code)** | 🔄 Updated |
| 8 | **Pollo AI Integration (Pro/Pro+ Only)** | ✅ Complete |
| 9 | Payment Integration | ⏳ Pending |
| 10 | i18n Completion | ✅ Complete |
| 11 | Admin Dashboard (Online Users + Tier Breakdown) | 🔄 Updated |
| 12 | Security + Production Deploy | ⏳ Pending |

---

*Last Updated: December 29, 2024*
