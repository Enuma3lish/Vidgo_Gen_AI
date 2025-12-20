# VidGo - Smart Demo AI Video Generation Platform

> AI-powered video generation SaaS platform with intelligent failover, multi-tier subscriptions, and style transformation features.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-green.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-teal.svg)](https://fastapi.tiangolo.com)

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Service Tiers](#service-tiers)
- [Point System](#point-system)
- [Development Plan](#development-plan)
- [Cost Analysis](#cost-analysis)
- [Getting Started](#getting-started)
- [API Integrations](#api-integrations)
- [Security](#security)
- [Internationalization](#internationalization)
- [Contributing](#contributing)

---

## Overview

VidGo is a 4-tier AI video generation platform (Demo / Starter / Pro / Unlimited) built with **Leonardo AI + Runway** as unlimited core services, complemented by **Pollo AI + GoEnhance** point-based premium features. GoEnhance's unique style transformation serves as the primary upgrade incentive.

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

---

## Key Features

### 🎬 Video Generation
- **Leonardo AI** - Primary generation platform (720p/1080p unlimited)
- **Runway** - Automatic backup for Leonardo
- **Pollo AI** - Advanced models and high-quality output (point-based)
- **GoEnhance AI** - Unique style transformation (core selling point)

### 🎨 Style Transformation (GoEnhance)
| Style Category | Styles | Use Cases |
|----------------|--------|-----------|
| Anime | Japanese Anime, Makoto Shinkai | Personal creation, Social media |
| 3D Animation | Pixar, Disney | Children's content, Advertising |
| Claymation | Stop-motion, Claymation | Creative ads, Art projects |
| Artistic | Oil painting, Watercolor, Sketch | Art display, Brand image |
| Retro | 80s, VHS effects | Nostalgic content, Music videos |
| Gaming | Pixel art, Cyberpunk | Game promotion, Tech content |

### 🛡️ Smart Failover System
```
Leonardo ✓ + Runway ✓ → Use Leonardo (primary)
Leonardo ✗ + Runway ✓ → Auto-switch to Runway
Leonardo ✓ + Runway ✗ → Continue with Leonardo
Leonardo ✗ + Runway ✗ → Activate point services (Pollo/GoEnhance)
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         VidGo Platform                          │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (Streamlit)                                           │
│  ├── Demo Showcase                                              │
│  ├── Video Generation UI                                        │
│  ├── Style Gallery                                              │
│  └── User Dashboard                                             │
├─────────────────────────────────────────────────────────────────┤
│  Backend (FastAPI)                                              │
│  ├── Auth Service (JWT)                                         │
│  ├── Generation Service                                         │
│  ├── Point Management                                           │
│  ├── Payment Processing                                         │
│  └── Content Moderation                                         │
├─────────────────────────────────────────────────────────────────┤
│  AI Services Layer                                              │
│  ├── Leonardo AI (Primary)     ←→ Runway (Backup)              │
│  ├── Pollo AI (Points)         ←→ GoEnhance (Points)           │
│  └── Gemini API (Moderation)                                    │
├─────────────────────────────────────────────────────────────────┤
│  Data Layer                                                     │
│  ├── PostgreSQL (Primary DB)                                    │
│  ├── Redis (Cache + Queue)                                      │
│  └── Object Storage (Videos)                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Backend
| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | FastAPI | High-performance async API |
| Database | PostgreSQL | Primary data storage |
| Cache | Redis | Session, queue, rate limiting |
| Task Queue | Celery + Redis | Async video processing |
| ORM | SQLAlchemy | Database operations |
| Validation | Pydantic | Request/response validation |

### Frontend
| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | Streamlit | Rapid UI development |
| Styling | Custom CSS | Brand consistency |
| i18n | streamlit-i18n | Multi-language support |

### Infrastructure
| Component | Technology | Purpose |
|-----------|------------|---------|
| Hosting | Hetzner/Linode | Cost-effective VPS |
| CDN | Cloudflare | Asset delivery + DDoS protection |
| Storage | S3-compatible | Video file storage |
| Monitoring | Sentry (Free) | Error tracking |
| SSL | Let's Encrypt | HTTPS certificates |

### External APIs
| Service | Purpose | Billing |
|---------|---------|---------|
| Leonardo AI | Primary video generation | Subscription ($60/mo) |
| Runway | Backup generation | On-demand (Phase 2) |
| Pollo AI | Premium features | Pay-per-use |
| GoEnhance | Style transformation | Pay-per-use |
| Gemini API | Content moderation | Pay-per-use |
| ECPay | Taiwan payments | Transaction fee |
| Paddle | International payments | Transaction fee |

---

## Service Tiers

### Tier Comparison

| Tier | Monthly | Unlimited Services | Point Services | Max Resolution |
|------|---------|-------------------|----------------|----------------|
| **Demo** | $0 | Smart Demo Only | — | 720p + Watermark |
| **Starter** | NT$299 | Leonardo 720p + Runway | Leonardo 1080p 50pts + Pollo Basic 30pts | 1080p |
| **Pro** | NT$599 | Leonardo 720p/1080p + Runway | Pollo Full 100pts + GoEnhance 50pts | 4K |
| **Unlimited** | NT$999 | Same as Pro + Priority | Pollo 300pts + GoEnhance 150pts + 20% discount | 4K 60fps |

### Tier Details

#### Demo (Free)
- Smart Demo engine with pre-generated samples
- 720p output with watermark
- Limited daily generations
- GoEnhance style preview (upgrade teaser)

#### Starter (NT$299/month)
- Unlimited Leonardo 720p generation
- Runway 720p backup
- 50 points for Leonardo 1080p upgrades
- 30 points for Pollo Basic features

#### Pro (NT$599/month)
- Unlimited Leonardo 720p/1080p (selectable)
- Full Runway backup
- 100 Pollo points (all features)
- 50 GoEnhance points (style transformation)
- 4K output capability

#### Unlimited (NT$999/month)
- Everything in Pro
- Priority processing queue
- 300 Pollo points
- 150 GoEnhance points
- 20% discount on point purchases

---

## Point System

### Point Consumption Table

| Platform | Feature | Resolution | Points | Available From |
|----------|---------|------------|--------|----------------|
| Leonardo AI | Image Generation | 1080p | 2 | Starter |
| Leonardo AI | Video Generation | 1080p | 10 | Starter |
| Pollo AI | Basic Effects | 1080p | 5 | Starter |
| Pollo AI | 4K Video | 4K | 15 | Pro |
| GoEnhance | Style Transform | 1080p | 10 | Pro |
| GoEnhance | Style Transform | 4K | 25 | Pro |
| GoEnhance | 4K Upscale | → 4K | 15 | Pro |
| GoEnhance | AI Face Swap | Any | 20 | Pro |

### Point Packages

| Package | Price (TWD/USD) | Points | Available To |
|---------|-----------------|--------|--------------|
| Small | NT$99 / $2.99 | 50 | Starter+ |
| Medium | NT$249 / $7.99 | 150 | Starter+ |
| Large | NT$699 / $22.99 | 500 | Pro+ |
| Value | NT$559 / $18.39 | 500 (20% off) | Unlimited only |

### Point Rules
- **Monthly allocation**: Resets on 1st of each month, unused points do not carry over
- **Purchased points**: Never expire
- **Consumption order**: Monthly points first, then purchased points

---

## Development Plan

### Phase Overview

| # | Phase | Hours | Status | Priority |
|---|-------|-------|--------|----------|
| 1 | Core Infrastructure | 4h | ✅ Complete | P0 |
| 2 | Smart Demo + Gemini Moderation | 15h | 🔄 In Progress | P0 |
| 3 | Leonardo + Runway + Auto-switch | 18h | ⏳ Pending | P0 |
| 4 | Pollo + GoEnhance Points | 12h | ⏳ Pending | P1 |
| 5 | Upgrade UI + Streamlit | 10h | ⏳ Pending | P1 |
| 6 | Dual Payment (ECPay + Paddle) | 20h | ⏳ Pending | P1 |
| 7 | i18n (5 languages) | 6h | ⏳ Pending | P2 |
| 8 | Admin Dashboard | 8h | ⏳ Pending | P2 |
| 9 | Security + Testing + Deploy | 12h | ⏳ Pending | P0 |

**Total: 105 hours (~13 working days)**  
**Target Launch: December 28, 2024**

---

### Phase 1: Core Infrastructure (4h) ✅

**Completed Components:**
- FastAPI project structure
- PostgreSQL database setup
- Redis configuration
- JWT authentication system
- Basic API endpoints

**Directory Structure:**
```
vidgo/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── generation.py
│   │   ├── points.py
│   │   └── payments.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── generation.py
│   │   └── transaction.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── leonardo.py
│   │   ├── runway.py
│   │   ├── pollo.py
│   │   ├── goenhance.py
│   │   └── moderation.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py
│   │   ├── failover.py
│   │   └── rate_limit.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── frontend/
│   ├── app.py
│   ├── pages/
│   └── components/
├── tests/
├── alembic/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

### Phase 2: Smart Demo + Content Moderation (15h) 🔄

**Tasks:**
1. **Smart Demo Engine** (8h)
   - Pre-generated demo database
   - Prompt matching algorithm
   - Demo video serving
   - Watermark overlay system

2. **Gemini Content Moderation** (5h)
   - API integration
   - 18+ content detection
   - Violence/illegal content filtering
   - Keyword fallback filter

3. **Testing & Integration** (2h)
   - Unit tests
   - Integration tests
   - Edge case handling

**Implementation Priority:**
```python
# Moderation flow
async def moderate_content(prompt: str) -> ModerationResult:
    # 1. Try Gemini API
    try:
        result = await gemini_moderate(prompt)
        return result
    except GeminiError:
        # 2. Fallback to keyword filter
        result = keyword_filter(prompt)
        if result.flagged:
            return result
        # 3. Pass through for manual review
        return ModerationResult(passed=True, needs_review=True)
```

---

### Phase 3: Leonardo + Runway Integration (18h)

**Tasks:**
1. **Leonardo AI Integration** (8h)
   - API wrapper
   - 720p/1080p generation
   - Queue management
   - Error handling

2. **Runway Integration** (6h)
   - API wrapper
   - Failover trigger logic
   - Same resolution matching

3. **Auto-switch System** (4h)
   - Health check service
   - Automatic failover
   - Status monitoring
   - Alert system

**Failover Logic:**
```python
class GenerationService:
    async def generate(self, request: GenerationRequest) -> Video:
        # Check Leonardo health
        if await self.leonardo.is_healthy():
            try:
                return await self.leonardo.generate(request)
            except LeonardoError:
                pass
        
        # Fallback to Runway
        if await self.runway.is_healthy():
            return await self.runway.generate(request)
        
        # Both down - use point services
        if request.user.has_points():
            return await self.point_service.generate(request)
        
        raise ServiceUnavailableError()
```

---

### Phase 4: Pollo + GoEnhance Points (12h)

**Tasks:**
1. **Point System Backend** (4h)
   - Point balance tracking
   - Monthly reset logic
   - Consumption recording
   - Package purchases

2. **Pollo AI Integration** (4h)
   - API wrapper
   - Feature mapping
   - Point deduction

3. **GoEnhance Integration** (4h)
   - Style transformation API
   - 4K upscaling
   - Face swap feature
   - Point deduction

---

### Phase 5: UI/UX with Streamlit (10h)

**Tasks:**
1. **Main Pages** (6h)
   - Home with style showcase
   - Generation interface
   - User dashboard
   - Subscription management

2. **Upgrade Incentive Areas** (4h)
   - GoEnhance style carousel (homepage)
   - "Unlock More Styles" preview
   - Weekly popular styles
   - Floating upgrade button

---

### Phase 6: Dual Payment System (20h)

**Tasks:**
1. **ECPay Integration** (10h)
   - Credit card
   - ATM transfer
   - Convenience store
   - LINE Pay
   - Webhook handling

2. **Paddle Integration** (8h)
   - International credit cards
   - PayPal
   - Apple Pay
   - Webhook handling

3. **Payment Logic** (2h)
   - Region detection
   - Currency conversion
   - Receipt generation

---

### Phase 7: Internationalization (6h)

**Supported Languages:**
| Language | Code | Priority | Auto-detect Region |
|----------|------|----------|-------------------|
| English | en | Primary | US, UK, AU, Default |
| Japanese | ja | High | JP |
| Traditional Chinese | zh-TW | High | TW, HK |
| Korean | ko | Medium | KR |
| Spanish | es | Medium | ES, MX, AR |

---

### Phase 8: Admin Dashboard (8h)

**Features:**
- User management
- Generation statistics
- Revenue reports
- Content moderation queue
- System health monitoring

---

### Phase 9: Security + Testing + Deploy (12h)

**Security Checklist:**
- [ ] JWT token rotation
- [ ] Rate limiting (100 req/min/IP)
- [ ] CORS whitelist
- [ ] HTTPS enforcement (TLS 1.3)
- [ ] Input validation (Pydantic)
- [ ] SQL injection prevention (ORM)
- [ ] XSS protection (CSP headers)
- [ ] Webhook signature verification
- [ ] Database encryption (AES-256)

**Deployment:**
- Docker containerization
- CI/CD pipeline
- Monitoring setup
- Backup automation

---

## Cost Analysis

### Optimized Monthly Costs (Initial Phase)

| Item | Original | Optimized | Savings |
|------|----------|-----------|---------|
| Leonardo AI | $60 | $60 | $0 |
| Runway | $76 | $0 (Phase 2) | $76 |
| Infrastructure | $80 | $40-50 | $30-40 |
| Gemini API | $20 | $5-10 | $10-15 |
| Pollo AI | $40 | $15 | $25 |
| GoEnhance | $60 | $25 | $35 |
| Whisper API | $30 | $0-10 | $20-30 |
| Other | $20 | $10 | $10 |
| **Total** | **$386** | **$150-200** | **$186-236** |

### Revenue Projection

| Tier | Users | Subscription | Add-ons | Total Revenue |
|------|-------|--------------|---------|---------------|
| Free | 200 | $0 | $0 | $0 |
| Starter | 50 | NT$14,950 | NT$2,500 | NT$17,450 |
| Pro | 15 | NT$8,985 | NT$2,000 | NT$10,985 |
| Unlimited | 8 | NT$7,992 | NT$1,500 | NT$9,492 |
| **Total** | **273** | **NT$31,927** | **NT$6,000** | **NT$37,927** |

### Profit Analysis (Optimized)

| Metric | Value |
|--------|-------|
| Monthly Revenue | NT$37,927 (~$1,185) |
| Monthly Cost | NT$4,800-6,400 (~$150-200) |
| Monthly Profit | NT$31,527-33,127 (~$985-1,035) |
| Profit Margin | **83-87%** |
| Break-even Users | **10-15 paid users** |

---

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (recommended)

### Quick Start

```bash
# Clone repository
git clone https://github.com/yourusername/vidgo.git
cd vidgo

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload
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

### Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/vidgo

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

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
PADDLE_PUBLIC_KEY=your-public-key

# App
APP_ENV=development
DEBUG=true
```

---

## API Integrations

### Leonardo AI
```python
from app.services.leonardo import LeonardoService

leonardo = LeonardoService(api_key=settings.LEONARDO_API_KEY)

# Generate video
result = await leonardo.generate(
    prompt="A cat playing piano",
    resolution="720p",
    duration=5
)
```

### Runway
```python
from app.services.runway import RunwayService

runway = RunwayService(api_key=settings.RUNWAY_API_KEY)

# Generate as backup
result = await runway.generate(
    prompt="A cat playing piano",
    resolution="720p"
)
```

### GoEnhance
```python
from app.services.goenhance import GoEnhanceService

goenhance = GoEnhanceService(api_key=settings.GOENHANCE_API_KEY)

# Style transformation
result = await goenhance.transform(
    video_url="https://...",
    style="anime_shinkai",
    resolution="4K"
)
```

---

## Security

### Authentication & Authorization
| Mechanism | Technology | Details |
|-----------|------------|---------|
| JWT Token | Access + Refresh | Access: 15min, Refresh: 7 days |
| Password | bcrypt + salt | 12 rounds hashing |
| API Key | HMAC-SHA256 | External API verification |
| OAuth 2.0 | Google/Facebook | Social login (optional) |

### API Security
| Protection | Setting | Purpose |
|------------|---------|---------|
| Rate Limiting | 100 req/min/IP | Prevent brute force |
| CORS | Whitelist domains | Cross-origin restriction |
| HTTPS | TLS 1.3 only | Encrypted transmission |
| Input Validation | Pydantic/Zod | Strict validation |
| SQL Injection | ORM + Parameterized | Prevent injection |
| XSS | CSP Headers | Prevent script attacks |

### Content & Payment Security
- **Gemini API**: All prompts screened for 18+/violence/illegal content
- **IP Ban**: Automatic ban after multiple violations
- **PCI DSS**: Card numbers handled by ECPay/Paddle only
- **Webhook Signature**: Verify payment callback signatures
- **Database Encryption**: AES-256 at rest + daily backups

---

## Internationalization

### Implementation
```python
# i18n structure
locales/
├── en.json
├── ja.json
├── zh-TW.json
├── ko.json
└── es.json
```

### Auto-detection Logic
```python
def detect_language(request):
    # 1. User preference (if logged in)
    if user.language_preference:
        return user.language_preference
    
    # 2. Browser/Accept-Language header
    accept_lang = request.headers.get('Accept-Language')
    
    # 3. IP geolocation
    country = geolocate(request.ip)
    
    # 4. Default to English
    return 'en'
```

---

## Contributing

### Development Workflow

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Code Style

- Follow PEP 8 for Python
- Use type hints
- Write docstrings for public methods
- Add tests for new features

### Commit Convention

```
feat: Add new feature
fix: Bug fix
docs: Documentation update
style: Code style (no logic change)
refactor: Code refactoring
test: Add tests
chore: Build/config changes
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Contact

- **Project**: VidGo AI Video Generation Platform
- **Target Launch**: December 28, 2024
- **Total Development**: 105 hours

---

*Built with ❤️ for creators worldwide*
