# VidGo - Architecture Documentation

## System Overview

VidGo is a 4-tier AI video generation SaaS platform (Demo / Starter / Pro / Unlimited) built with **Leonardo AI + Runway** as unlimited core services, complemented by **Pollo AI + GoEnhance** point-based premium features. The platform features intelligent failover, multi-tier subscriptions, and style transformation capabilities.

### Core Design Principles

| Principle | Implementation |
|-----------|----------------|
| 4-Tier Service | Demo → Starter → Pro → Unlimited |
| Unlimited Services | Leonardo + Runway (mutual failover) |
| Point Services | Pollo + GoEnhance (monthly allocation + purchasable) |
| Smart Failover | Auto-detect failures, dual-down triggers point services |
| Upgrade Incentive | GoEnhance style showcase attracts upgrades |
| Content Moderation | Gemini API (18+ / illegal content) |
| Multi-language | EN / JA / ZH-TW / KO / ES |
| Dual Payment | ECPay (Taiwan) + Paddle (International) |

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
│  │  │ Demo Showcase│  │  Generation  │  │    User      │             │    │
│  │  │              │  │      UI      │  │  Dashboard   │             │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │    │
│  │                                                                     │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │    │
│  │  │Style Gallery │  │ Subscription │  │   Payment    │             │    │
│  │  │  (GoEnhance) │  │  Management  │  │   Checkout   │             │    │
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
│  │  │    Auth     │  │ Generation  │  │   Points    │  │  Payments   │  │ │
│  │  │   Service   │  │   Service   │  │ Management  │  │  (ECPay/    │  │ │
│  │  │   (JWT)     │  │ (Failover)  │  │             │  │   Paddle)   │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │ │
│  │                                                                        │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │ │
│  │  │   Content   │  │   Smart     │  │    User     │  │    Admin    │  │ │
│  │  │ Moderation  │  │    Demo     │  │   Profile   │  │   (Future)  │  │ │
│  │  │  (Gemini)   │  │   Engine    │  │             │  │             │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────────┐
│                           AI SERVICES LAYER                                  │
│                                    │                                         │
│      ┌─────────────────────────────┴─────────────────────────────────┐     │
│      │                   Smart Failover Controller                    │     │
│      │                                                                │     │
│      │   Leonardo ✓ + Runway ✓ → Use Leonardo (primary)              │     │
│      │   Leonardo ✗ + Runway ✓ → Auto-switch to Runway               │     │
│      │   Leonardo ✓ + Runway ✗ → Continue with Leonardo              │     │
│      │   Leonardo ✗ + Runway ✗ → Activate point services             │     │
│      └────────────────────────────────────────────────────────────────┘     │
│                                    │                                         │
│              ┌─────────────────────┴─────────────────────┐                  │
│              │                                           │                  │
│   ┌──────────┴──────────┐                   ┌───────────┴───────────┐      │
│   │  UNLIMITED SERVICES │                   │    POINT SERVICES     │      │
│   │                     │                   │                       │      │
│   │  ┌───────────────┐  │                   │  ┌─────────────────┐  │      │
│   │  │  Leonardo AI  │◄─┼─── Failover ──────┼─►│    Pollo AI     │  │      │
│   │  │   (Primary)   │  │                   │  │  (High Quality) │  │      │
│   │  │  720p/1080p   │  │                   │  │    4K Video     │  │      │
│   │  └───────────────┘  │                   │  └─────────────────┘  │      │
│   │         ↕           │                   │                       │      │
│   │  ┌───────────────┐  │                   │  ┌─────────────────┐  │      │
│   │  │    Runway     │  │                   │  │   GoEnhance     │  │      │
│   │  │   (Backup)    │  │                   │  │Style Transform  │  │      │
│   │  │  720p/1080p   │  │                   │  │  4K Upscale     │  │      │
│   │  └───────────────┘  │                   │  └─────────────────┘  │      │
│   └─────────────────────┘                   └───────────────────────┘      │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                         Gemini API                                   │  │
│   │                    (Content Moderation)                              │  │
│   │           18+ Detection | Violence Filter | Illegal Content         │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         TASK PROCESSING LAYER                                │
│                                                                              │
│   ┌───────────────────────────────┐     ┌───────────────────────────────┐  │
│   │        Celery Worker          │     │       Celery Beat             │  │
│   │                               │     │       (Scheduler)             │  │
│   │  - Video Processing           │     │                               │  │
│   │  - Email Notifications        │     │  - Subscription Renewal       │  │
│   │  - Point Deduction            │     │  - Monthly Point Reset        │  │
│   │  - Invoice Generation         │     │  - Health Checks              │  │
│   │  - Webhook Processing         │     │  - Cleanup Tasks              │  │
│   └───────────────────────────────┘     └───────────────────────────────┘  │
│                         │                             │                     │
└─────────────────────────┼─────────────────────────────┼─────────────────────┘
                          │                             │
┌─────────────────────────┼─────────────────────────────┼─────────────────────┐
│                         DATA LAYER                    │                      │
│                         │                             │                      │
│           ┌─────────────┴─────────────┬───────────────┴─────────────┐       │
│           │                           │                             │       │
│           ▼                           ▼                             ▼       │
│  ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────┐   │
│  │   PostgreSQL 15     │   │      Redis 7        │   │  Object Storage │   │
│  │   (Port 5432)       │   │   (Port 6379)       │   │   (S3/Minio)    │   │
│  │                     │   │                     │   │                 │   │
│  │  - Users            │   │  - Session Cache    │   │  - Videos       │   │
│  │  - Plans            │   │  - Rate Limiting    │   │  - Thumbnails   │   │
│  │  - Subscriptions    │   │  - Celery Broker    │   │  - User Uploads │   │
│  │  - Orders           │   │  - API Responses    │   │                 │   │
│  │  - Invoices         │   │  - Point Balances   │   │                 │   │
│  │  - Generations      │   │  - Health Status    │   │                 │   │
│  │  - Point Txns       │   │                     │   │                 │   │
│  └─────────────────────┘   └─────────────────────┘   └─────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SERVICES                                    │
│                                                                              │
│  ┌─────────────────────────────┐   ┌─────────────────────────────┐         │
│  │          ECPay              │   │          Paddle             │         │
│  │    (Taiwan Payments)        │   │  (International Payments)   │         │
│  │                             │   │                             │         │
│  │  - Credit Card              │   │  - Credit Card              │         │
│  │  - ATM Transfer             │   │  - PayPal                   │         │
│  │  - CVS Payment              │   │  - Apple Pay                │         │
│  │  - LINE Pay                 │   │  - Google Pay               │         │
│  └─────────────────────────────┘   └─────────────────────────────┘         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

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

### Frontend (Streamlit)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | Streamlit 1.30.0 | Rapid UI development |
| Navigation | streamlit-option-menu | Enhanced navigation |
| Session | extra-streamlit-components | Session management |
| HTTP | requests 2.31.0 | API communication |
| Styling | Custom CSS | Brand consistency |

### Task Queue

| Component | Technology | Purpose |
|-----------|------------|---------|
| Queue | Celery 5.3.6 | Distributed task processing |
| Broker | Redis 5.0.1 | Message broker |
| Scheduler | Celery Beat | Periodic tasks |

### Infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| Database | PostgreSQL 15 | Primary data storage |
| Cache | Redis 7 | Cache + queue + rate limiting |
| Storage | S3-compatible | Video file storage |
| Hosting | Hetzner/Linode | Cost-effective VPS |
| CDN | Cloudflare | Asset delivery + DDoS protection |
| SSL | Let's Encrypt | HTTPS certificates |
| Monitoring | Sentry (Free) | Error tracking |

### External AI Services

| Service | Purpose | Billing Model | Status |
|---------|---------|---------------|--------|
| GoEnhance | Nano Banana (T2I) + V2V Style Transform | Pay-per-use | ✅ Integrated |
| Pollo AI | Image-to-Video (Pixverse) | Pay-per-use | ✅ Integrated |
| Leonardo AI | Primary video generation | Subscription ($60/mo) | ⏳ Pending |
| Runway | Backup video generation | On-demand | ⏳ Pending |
| Gemini API | Content moderation | Pay-per-use | ✅ Integrated |

### Demo Pipeline ("See It In Action")

```
User Prompt
    ↓
[Step 1] GoEnhance Nano Banana → Image (~30-60 seconds)
    ↓
[Step 2] Pollo AI Pixverse → Video (~1-3 minutes)
    ↓
[Step 3] GoEnhance V2V → Enhanced Video (~2-5 minutes)
    ↓
Final Demo Result
```

| Step | Service | Input | Output | Time |
|------|---------|-------|--------|------|
| 1 | GoEnhance Nano Banana | Text Prompt | Image URL | 30-60s |
| 2 | Pollo AI Pixverse v4.5 | Image URL | Video URL (5s) | 1-3min |
| 3 | GoEnhance V2V | Video URL | Enhanced Video URL | 2-5min |

## Project Structure

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
│   │   │       ├── auth.py         # Authentication endpoints
│   │   │       ├── demo.py         # Demo endpoints (incl. real-time generation)
│   │   │       ├── plans.py        # Plan endpoints
│   │   │       └── payments.py     # Payment endpoints
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py           # Settings management
│   │   │   ├── database.py         # Async database setup
│   │   │   ├── security.py         # JWT + password utilities
│   │   │   └── rate_limit.py       # Rate limiting
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py             # User model
│   │   │   ├── billing.py          # Plan, Subscription, Order, Invoice
│   │   │   └── demo.py             # Demo models (ImageDemo, DemoCategory)
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── user.py             # User Pydantic schemas
│   │   │   └── plan.py             # Plan schemas
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── goenhance.py        # GoEnhance (Nano Banana + V2V)
│   │   │   ├── pollo_ai.py         # Pollo AI (Image-to-Video)
│   │   │   ├── moderation.py       # Gemini content moderation
│   │   │   ├── block_cache.py      # Redis block cache
│   │   │   ├── prompt_matching.py  # Prompt matching service
│   │   │   ├── demo_service.py     # Demo pipeline orchestration
│   │   │   └── email_service.py    # Email notifications
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── helpers.py          # Utility functions
│   ├── alembic/
│   │   ├── env.py                  # Alembic configuration
│   │   └── versions/               # Migration files
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/
│   ├── app.py                      # Streamlit main app
│   ├── config.py                   # Frontend configuration
│   ├── pages/                      # Streamlit pages
│   ├── components/
│   │   └── demo.py                 # Demo component (See It In Action)
│   └── utils/
│       ├── auth.py                 # Auth utilities
│       └── api_client.py           # Backend API client
├── docker-compose.yml
├── pyproject.toml
├── DEVELOPMENT_PLAN.md             # Development timeline
├── ARCHITECTURE.md                 # This file
└── README.md
```

## Data Flow

### Video Generation Flow (with Failover)

```
1. User submits prompt (Streamlit)
   ↓
2. POST /api/v1/generation/create (FastAPI)
   ↓
3. Content Moderation (Gemini API)
   │  - Check for 18+ content
   │  - Check for violence/illegal content
   │  - Keyword fallback filter
   ↓
4. If flagged → Return rejection with reason
   ↓
5. Check user tier & points
   │  - Validate subscription status
   │  - Check resolution permissions
   ↓
6. Smart Failover Logic
   │
   ├─► Leonardo Healthy?
   │   YES → Generate with Leonardo
   │   │     └─► Success → Return video
   │   │     └─► Failure → Try Runway
   │   │
   │   NO → Check Runway
   │
   ├─► Runway Healthy?
   │   YES → Generate with Runway
   │   │     └─► Success → Return video
   │   │     └─► Failure → Check Points
   │   │
   │   NO → Both Down
   │
   └─► User has points?
       YES → Deduct points → Use Pollo/GoEnhance
       NO  → Return ServiceUnavailableError
   ↓
7. Store video in Object Storage
   ↓
8. Create Generation record in DB
   ↓
9. Return video URL to user
```

### Payment Flow (ECPay)

```
1. User selects subscription plan (Streamlit)
   ↓
2. POST /api/v1/payments/create (FastAPI)
   ↓
3. Verify user authentication
   ↓
4. Create Order (status: pending)
   ↓
5. Generate ECPay payment parameters
   │  - MerchantTradeNo (unique)
   │  - CheckMacValue (SHA256)
   │  - Return/Callback URLs
   ↓
6. Return payment form data
   ↓
7. Submit form to ECPay (Client-side redirect)
   ↓
8. User completes payment on ECPay
   ↓
9. ECPay POST /api/v1/payments/callback (webhook)
   ↓
10. Verify CheckMacValue signature
    ↓
11. Update Order status to 'paid'
    ↓
12. Activate/Extend Subscription
    ↓
13. Allocate monthly points
    ↓
14. Send confirmation email
    ↓
15. ECPay redirects user to success page
```

### Point Consumption Flow

```
1. User requests premium feature (e.g., 4K upscale)
   ↓
2. Check feature availability for tier
   ↓
3. Calculate point cost
   │  - GoEnhance Style Transform 1080p: 10 pts
   │  - GoEnhance Style Transform 4K: 25 pts
   │  - GoEnhance 4K Upscale: 15 pts
   ↓
4. Check point balance
   │  - Monthly points first
   │  - Then purchased points
   ↓
5. Deduct points
   ↓
6. Execute premium feature
   ↓
7. Record transaction
   ↓
8. Return result to user
```

## Database Schema

### User Model

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(150),
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
```

### Plan Model

```sql
CREATE TABLE plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'TWD',
    billing_cycle VARCHAR(20) DEFAULT 'monthly',
    features JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Features JSON structure:
-- {
--   "unlimited_720p": true,
--   "unlimited_1080p": false,
--   "monthly_pollo_points": 30,
--   "monthly_goenhance_points": 0,
--   "max_resolution": "1080p",
--   "priority_queue": false,
--   "point_discount": 0
-- }
```

### Subscription Model

```sql
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    plan_id UUID NOT NULL REFERENCES plans(id),
    status VARCHAR(20) DEFAULT 'pending',
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    auto_renew BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX idx_subscriptions_user ON subscriptions(user_id, status);
CREATE INDEX idx_subscriptions_end ON subscriptions(status, end_date);
```

### Order Model

```sql
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number VARCHAR(50) UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    subscription_id UUID REFERENCES subscriptions(id),
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    payment_method VARCHAR(20),
    payment_data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    paid_at TIMESTAMPTZ
);

CREATE INDEX idx_orders_user ON orders(user_id, status);
CREATE INDEX idx_orders_number ON orders(order_number);
```

### Invoice Model

```sql
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID UNIQUE NOT NULL REFERENCES orders(id),
    user_id UUID NOT NULL REFERENCES users(id),
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    pdf_url VARCHAR(255),
    issued_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Point Balance Model (Future)

```sql
CREATE TABLE point_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id),
    monthly_pollo_points INTEGER DEFAULT 0,
    monthly_goenhance_points INTEGER DEFAULT 0,
    purchased_points INTEGER DEFAULT 0,
    last_reset_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Point Transaction Model (Future)

```sql
CREATE TABLE point_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    type VARCHAR(20) NOT NULL,  -- 'deduct', 'allocate', 'purchase', 'refund'
    points INTEGER NOT NULL,
    source VARCHAR(20),  -- 'monthly', 'purchased'
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_point_txns_user ON point_transactions(user_id, created_at);
```

### Generation History Model (Future)

```sql
CREATE TABLE generations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    prompt TEXT NOT NULL,
    service VARCHAR(20) NOT NULL,  -- 'leonardo', 'runway', 'pollo', 'goenhance'
    resolution VARCHAR(10),
    style VARCHAR(50),
    video_url VARCHAR(500),
    thumbnail_url VARCHAR(500),
    status VARCHAR(20) DEFAULT 'pending',
    points_used INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_generations_user ON generations(user_id, created_at);
```

## API Endpoints

### Authentication

```
POST   /api/v1/auth/login          Login (returns JWT tokens)
POST   /api/v1/auth/register       Register new user
POST   /api/v1/auth/refresh        Refresh JWT token
GET    /api/v1/auth/me             Get current user info
```

### Video Generation (Phase 2-3)

```
POST   /api/v1/generation/create   Create new video generation
GET    /api/v1/generation/         List user's generations
GET    /api/v1/generation/{id}     Get generation details
GET    /api/v1/generation/status   Check AI service health status
```

### Points (Phase 4)

```
GET    /api/v1/points/balance      Get user point balance
GET    /api/v1/points/history      Get point transaction history
POST   /api/v1/points/purchase     Purchase point package
```

### Payments

```
POST   /api/v1/payments/create     Create ECPay payment
POST   /api/v1/payments/callback   ECPay callback (webhook)
GET    /api/v1/payments/history    Get payment history
```

### Subscriptions (Phase 6)

```
GET    /api/v1/subscriptions/      List user subscriptions
POST   /api/v1/subscriptions/      Create subscription
GET    /api/v1/subscriptions/{id}  Get subscription details
POST   /api/v1/subscriptions/cancel Cancel subscription
```

### Admin (Phase 8)

```
GET    /api/v1/admin/users         List all users
GET    /api/v1/admin/stats         System statistics
GET    /api/v1/admin/moderation    Content moderation queue
```

## Security Features

### Authentication & Authorization

| Mechanism | Technology | Details |
|-----------|------------|---------|
| JWT Token | Access + Refresh | Access: 30min, Refresh: 7 days |
| Password | bcrypt + salt | Secure password hashing |
| API Key | HMAC-SHA256 | External API verification |

### API Security

| Protection | Setting | Purpose |
|------------|---------|---------|
| Rate Limiting | 100 req/min/IP | Prevent brute force |
| CORS | Whitelist domains | Cross-origin restriction |
| HTTPS | TLS 1.3 only | Encrypted transmission |
| Input Validation | Pydantic | Strict schema validation |
| SQL Injection | SQLAlchemy ORM | Parameterized queries |

### Content Security

| Feature | Implementation |
|---------|----------------|
| Gemini Moderation | 18+ / violence / illegal content detection |
| Keyword Filter | Fallback when Gemini unavailable |
| IP Banning | Auto-ban after violations |
| Webhook Signature | Verify ECPay/Paddle callbacks |

## Service Tiers

| Tier | Price | Unlimited Services | Point Services | Max Resolution |
|------|-------|-------------------|----------------|----------------|
| **Demo** | $0 | Smart Demo Only | — | 720p + Watermark |
| **Starter** | NT$299/mo | Leonardo 720p + Runway | 50 + 30 pts | 1080p |
| **Pro** | NT$599/mo | Leonardo 720p/1080p + Runway | 100 + 50 pts | 4K |
| **Unlimited** | NT$999/mo | Pro + Priority Queue | 300 + 150 pts + 20% off | 4K 60fps |

## Point System

### Consumption Table

| Platform | Feature | Resolution | Points |
|----------|---------|------------|--------|
| Leonardo AI | Image Gen | 1080p | 2 |
| Leonardo AI | Video Gen | 1080p | 10 |
| Pollo AI | Basic Effects | 1080p | 5 |
| Pollo AI | 4K Video | 4K | 15 |
| GoEnhance | Style Transform | 1080p | 10 |
| GoEnhance | Style Transform | 4K | 25 |
| GoEnhance | 4K Upscale | → 4K | 15 |

### Point Rules

- **Monthly allocation**: Resets on 1st of each month
- **Purchased points**: Never expire
- **Consumption order**: Monthly points first, then purchased

## Development Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Core Infrastructure (FastAPI, PostgreSQL, JWT) | ✅ Complete |
| 2 | Smart Demo + Gemini Moderation | ✅ Complete |
| 3 | Leonardo + Runway + Auto-switch | ⏳ Pending |
| 4 | Pollo + GoEnhance Demo Pipeline | ✅ Complete |
| 5 | Upgrade UI + Streamlit | 🔄 In Progress |
| 6 | Dual Payment (ECPay + Paddle) | ⏳ Pending |
| 7 | i18n (5 languages) | ⏳ Pending |
| 8 | Admin Dashboard | ⏳ Pending |
| 9 | Security + Testing + Deploy | ⏳ Pending |

## Deployment

### Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/vidgo

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# AI Services
LEONARDO_API_KEY=your-leonardo-key
RUNWAY_API_KEY=your-runway-key
POLLO_API_KEY=your-pollo-key
GOENHANCE_API_KEY=your-goenhance-key
GEMINI_API_KEY=your-gemini-key

# Payments
ECPAY_MERCHANT_ID=your-merchant-id
ECPAY_HASH_KEY=your-hash-key
ECPAY_HASH_IV=your-hash-iv
PADDLE_API_KEY=your-paddle-key

# App
APP_ENV=development
DEBUG=true
```

### Docker Deployment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Local Development

```bash
# Install dependencies
uv sync

# Run backend
cd backend && uv run uvicorn app.main:app --reload

# Run frontend
cd frontend && uv run streamlit run app.py
```

## Future Enhancements

- [ ] WebSocket for real-time generation progress
- [ ] Multi-region deployment
- [ ] Usage analytics dashboard
- [ ] Webhook support for third-party integrations
- [ ] Mobile app (React Native)
- [ ] Advanced video editing features
- [ ] Team/Organization accounts
- [ ] API access for developers
