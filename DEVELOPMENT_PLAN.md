# VidGo Development Plan

## Project Summary

| Item | Details |
|------|---------|
| **Project** | VidGo - AI Video Generation SaaS |
| **Target Launch** | December 28, 2024 |
| **Total Hours** | 105 hours (~13 working days) |
| **Initial Monthly Cost** | $150-200 USD (optimized) |
| **Break-even Point** | 10-15 paid users |

---

## Development Timeline

```
Dec 14-15  │ Phase 1: Core Infrastructure ✅ COMPLETE (4h)
           │
Dec 16-20  │ Phase 2: Smart Demo + Gemini ✅ COMPLETE (15h)
           │
Dec 21-23  │ Phase 3: Leonardo + Runway (18h)
           │
Dec 22-23  │ Phase 4: Pollo + GoEnhance (12h)
           │
Dec 24     │ Phase 5: UI/UX Streamlit (10h)
           │
Dec 25-26  │ Phase 6: Payment Integration (20h)
           │
Dec 27     │ Phase 7-8: i18n + Admin (14h)
           │
Dec 28     │ Phase 9: Security + Deploy (12h)
           │
           ▼
        🚀 LAUNCH
```

---

## Phase Checklist

### Phase 1: Core Infrastructure (4h) ✅ COMPLETE

#### Backend Foundation
- [x] FastAPI project setup with async support
- [x] PostgreSQL database with async SQLAlchemy
- [x] Redis configuration for caching
- [x] Project structure (app/api, app/core, app/models, app/services, app/schemas)

#### Authentication System
- [x] JWT authentication with access + refresh tokens
- [x] Token type validation (access vs refresh)
- [x] Password hashing with bcrypt
- [x] OAuth2 compatible login endpoints

#### User Management
- [x] User model with email verification fields
- [x] User registration with email verification flow
- [x] Email verification token generation
- [x] Password reset flow (forgot/reset)
- [x] User profile endpoints (GET/PUT /me)

#### Email Service
- [x] SMTP email service with HTML templates
- [x] Verification email sending
- [x] Password reset email sending
- [x] Welcome email after verification
- [x] Debug mode logging (when SMTP not configured)

#### API Endpoints
- [x] POST `/api/v1/auth/register` - User registration
- [x] POST `/api/v1/auth/login` - Login with email/password
- [x] POST `/api/v1/auth/logout` - Logout
- [x] POST `/api/v1/auth/refresh` - Refresh access token
- [x] POST `/api/v1/auth/verify-email` - Email verification
- [x] POST `/api/v1/auth/resend-verification` - Resend verification
- [x] POST `/api/v1/auth/forgot-password` - Request password reset
- [x] POST `/api/v1/auth/reset-password` - Reset password
- [x] GET `/api/v1/auth/me` - Get current user
- [x] PUT `/api/v1/auth/me` - Update profile
- [x] POST `/api/v1/auth/me/change-password` - Change password

#### Plans System
- [x] Plan model with feature flags and pricing
- [x] Default plans seeding (Free, Basic, Pro, Enterprise)
- [x] GET `/api/v1/plans` - List all plans (public)
- [x] GET `/api/v1/plans/current` - Get current subscription
- [x] GET `/api/v1/plans/with-subscription` - Plans with user subscription

---

### Phase 2: Smart Demo + Content Moderation (15h) ✅ COMPLETE

#### Demo System
- [x] Demo database schema (DemoCategory, DemoVideo, DemoView)
- [x] Prompt matching algorithm with multi-language support
- [x] Demo video serving endpoints
- [x] Random demo selection
- [x] Style and category filtering

#### Content Moderation - Gemini Integration
- [x] Google Gemini API integration for content analysis
- [x] Structured prompt analysis (intent, style, safety)
- [x] Self-learning moderation from Gemini feedback
- [x] Fallback to keyword filter when Gemini unavailable

#### Content Moderation - Block Cache (Redis)
- [x] Redis-based block cache for illegal words
- [x] Multi-language support (EN, ZH-TW, JA, KO, ES)
- [x] 200+ seed blocked words across 6 categories:
  - Adult content
  - Violence
  - Hate speech
  - Illegal activities
  - Self-harm
  - Dangerous content
- [x] Self-learning cache updates from Gemini analysis
- [x] Block cache management endpoints

#### Content Moderation - Keyword Filter
- [x] Pattern-based content filtering
- [x] Multi-language keyword detection
- [x] Category-based blocking reasons
- [x] Fallback when other systems unavailable

#### Demo API Endpoints
- [x] POST `/api/v1/demo/search` - Search/generate demos
- [x] GET `/api/v1/demo/random` - Get random demo
- [x] GET `/api/v1/demo/analyze` - Analyze prompt
- [x] GET `/api/v1/demo/styles` - List available styles
- [x] GET `/api/v1/demo/categories` - List categories
- [x] POST `/api/v1/demo/moderate` - Check content moderation
- [x] GET `/api/v1/demo/block-cache/stats` - Block cache statistics
- [x] POST `/api/v1/demo/block-cache/check` - Check prompt against cache

#### GoEnhance Integration
- [x] GoEnhance API client
- [x] Style transformation effects
- [x] Video enhancement capabilities

#### Frontend - Demo Page
- [x] Streamlit demo page with AI Clothing Transform showcase
- [x] GoEnhance Effects showcase
- [x] Multi-language prompt support
- [x] Style gallery display
- [x] Category browsing
- [x] Content moderation feedback UI
- [x] Dark mode styling

#### Frontend - Authentication
- [x] Landing page with Demo/Plans/Login/Register navigation
- [x] Login form with email verification message handling
- [x] Registration form with terms acceptance
- [x] Forgot password flow
- [x] Password reset form (from email link)
- [x] Email verification handling (from email link)
- [x] Session management with access/refresh tokens

#### Frontend - Plans Display
- [x] Public plans page (non-authenticated)
- [x] Authenticated plans page with current subscription
- [x] Plan feature display (credits, video length, resolution, etc.)
- [x] Featured/recommended plan highlighting

---

### Phase 3: Leonardo + Runway (18h) ⏳ PENDING
- [ ] Leonardo API wrapper
- [ ] 720p/1080p generation
- [ ] Runway API wrapper
- [ ] Health check service
- [ ] Auto-failover logic
- [ ] Status monitoring
- [ ] Integration tests

### Phase 4: Pollo + GoEnhance (12h) ✅ COMPLETE

#### GoEnhance Nano Banana (Text-to-Image)
- [x] GoEnhance API client with Nano Banana support
- [x] Text-to-Image generation endpoint (`/nano-banana`)
- [x] Async polling for image completion
- [x] Image result retrieval (`/jobs/detail`)
- [x] Style parameter support

#### Pollo AI (Image-to-Video)
- [x] Pollo AI API client with multiple model support
- [x] Pixverse v4.5 integration (cheapest model)
- [x] Image-to-Video generation (`/generation/pixverse/pixverse-v4-5`)
- [x] Status polling (`/generation/{taskId}/status`)
- [x] Video URL extraction from `generations[0].url`
- [x] Length validation (5 or 8 seconds only)

#### GoEnhance V2V (Video Enhancement)
- [x] Video-to-Video style transformation
- [x] 12+ style options (Anime, Pixar, Cyberpunk, etc.)
- [x] Resolution support (540p, 720p)
- [x] Video enhancement pipeline

#### Demo Pipeline ("See It In Action")
- [x] Full pipeline implementation:
  ```
  User Prompt
      ↓
  [Step 1] GoEnhance Nano Banana → Image (~30-60s)
      ↓
  [Step 2] Pollo AI Pixverse → Video (~1-3min)
      ↓
  [Step 3] GoEnhance V2V → Enhanced Video (~2-5min)
      ↓
  Final Demo Result
  ```
- [x] Real-time demo generation API endpoint
- [x] Skip V2V option for faster results
- [x] Frontend integration with progress display

#### Demo API Endpoints (New)
- [x] POST `/api/v1/demo/generate-realtime` - Real-time pipeline generation

#### Point System (Pending)
- [ ] Point balance system
- [ ] Monthly reset logic
- [ ] Point deduction logic

### Phase 5: UI/UX (10h) ⏳ PENDING
- [x] Streamlit main app structure
- [x] Demo interface
- [x] User authentication UI
- [ ] Full generation interface
- [ ] User dashboard improvements
- [ ] Style gallery carousel
- [ ] Upgrade prompts

### Phase 6: Payment Integration (20h) ⏳ PENDING
- [ ] ECPay credit card
- [ ] ECPay ATM/convenience store
- [ ] ECPay LINE Pay
- [ ] Paddle international
- [ ] Webhook handlers
- [ ] Receipt generation

### Phase 7: i18n (6h) ⏳ PENDING
- [x] English (en) - Content moderation
- [x] Japanese (ja) - Content moderation
- [x] Traditional Chinese (zh-TW) - Content moderation
- [x] Korean (ko) - Content moderation
- [x] Spanish (es) - Content moderation
- [ ] Full UI translation
- [ ] Language detection

### Phase 8: Admin Dashboard (8h) ⏳ PENDING
- [ ] User management
- [ ] Generation stats
- [ ] Revenue reports
- [ ] Moderation queue
- [ ] System health

### Phase 9: Security + Deploy (12h) ⏳ PENDING
- [x] Input validation (Pydantic schemas)
- [x] Password hashing - Server (bcrypt 12 rounds)
- [x] Password hashing - Client (SHA-256 with salt)
- [x] JWT token security (access + refresh with type validation)
- [x] Email verification (token-based, 24h expiry)
- [x] Password reset flow (secure token, 1h expiry)
- [ ] Rate limiting
- [ ] CORS whitelist
- [ ] SQL injection prevention (using ORM)
- [ ] XSS protection
- [ ] Docker setup
- [ ] CI/CD pipeline
- [ ] Production deploy
- [ ] Monitoring setup

#### Security Implementation Details

**Defense in Depth (Password Security):**
```
User enters password
        ↓
[Layer 1] Client-side SHA-256 hash with salt (frontend)
        ↓
[Layer 2] HTTPS/TLS encryption in transit
        ↓
[Layer 3] Server-side bcrypt hash (12 rounds)
        ↓
Stored securely in PostgreSQL
```

**Email Verification Flow:**
```
1. User registers → Account created (is_active=False)
                  → Verification token generated
                  → Email sent with verification link

2. User clicks link → Token validated (24h expiry)
                    → Account activated (is_active=True)
                    → Welcome email sent

3. User can login → Access token (15-30min) + Refresh token (7 days)
```

**Token Security:**
- Access tokens: Short-lived (15-30 min), used for API calls
- Refresh tokens: Long-lived (7 days), used only to get new access tokens
- Token type validation: Prevents using refresh token for API calls
- Tokens include: user_id, type, expiry

---
 **Test Services Running:**

  - Frontend: http://localhost:8501
  - Backend: http://localhost:8000

## Current Project Structure

```
vidgo/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry
│   │   ├── api/
│   │   │   ├── api.py                 # Router aggregation
│   │   │   ├── deps.py                # Dependencies (auth, db, token validation)
│   │   │   └── v1/
│   │   │       ├── auth.py            # Auth endpoints (login, register, verify, reset)
│   │   │       ├── demo.py            # Demo endpoints (incl. real-time generation)
│   │   │       ├── plans.py           # Plans endpoints
│   │   │       └── payments.py        # Payment endpoints
│   │   ├── core/
│   │   │   ├── config.py              # Settings (incl. SMTP, token expiry)
│   │   │   ├── database.py            # Database connection
│   │   │   └── security.py            # JWT (access+refresh), bcrypt, token generation
│   │   ├── models/
│   │   │   ├── user.py                # User model (email verification fields)
│   │   │   ├── billing.py             # Plan, Subscription, Order
│   │   │   └── demo.py                # Demo models (ImageDemo, DemoCategory, DemoVideo)
│   │   ├── schemas/
│   │   │   ├── user.py                # User schemas (LoginResponse, TokenPair)
│   │   │   └── plan.py                # Plan schemas
│   │   └── services/
│   │       ├── moderation.py          # Content moderation (Gemini + keywords)
│   │       ├── block_cache.py         # Redis block cache (multi-language)
│   │       ├── prompt_matching.py     # Prompt matching
│   │       ├── goenhance.py           # GoEnhance API (Nano Banana + V2V)
│   │       ├── pollo_ai.py            # Pollo AI API (Image-to-Video)
│   │       ├── email_service.py       # Email sending (verification, reset, welcome)
│   │       └── demo_service.py        # Demo service (full pipeline orchestration)
│   └── requirements.txt
├── frontend/
│   ├── app.py                         # Streamlit main (auth flows, plans)
│   ├── config.py                      # Frontend config (API endpoints)
│   ├── utils/
│   │   ├── api_client.py              # API client (incl. real-time demo generation)
│   │   └── auth.py                    # Auth utilities
│   ├── components/
│   │   └── demo.py                    # Demo component (See It In Action)
│   └── pages/
│       └── demo.py                    # Demo page
├── docker-compose.yml
├── pyproject.toml
├── README.md
├── README.zh-TW.md
├── DEVELOPMENT_PLAN.md                # This file
└── ARCHITECTURE.md                    # System architecture
```

---

## Cost Optimization Strategy

### Initial Phase (Month 1-3)

| Service | Action | Monthly Savings |
|---------|--------|-----------------|
| Runway | Delay subscription, use Leonardo only | $76 |
| Infrastructure | Use Hetzner/Linode low-tier VPS | $30-40 |
| Gemini API | Rely on free tier + keyword filter | $10-15 |
| Pollo AI | Minimal usage (few Pro users) | $25 |
| GoEnhance | Minimal usage (showcase demos) | $35 |
| Whisper API | Delay feature or use open-source | $20-30 |
| Monitoring | Use free tiers (Sentry, Cloudflare) | $10 |

**Total Savings: $186-236/month**

### Scale-up Triggers

| Milestone | Action |
|-----------|--------|
| 50+ paid users | Add Runway subscription |
| 100+ paid users | Upgrade infrastructure |
| 200+ paid users | Premium monitoring |

---

## Critical Path Items

### Must-Have for Launch
1. ✅ User authentication (JWT + email verification)
2. ✅ Content moderation (Gemini + Block Cache + Keywords)
3. ✅ Demo showcase system
4. ✅ Plans display
5. ⏳ Leonardo video generation
6. ⏳ Basic payment (ECPay)
7. ⏳ Point system

### Nice-to-Have (Can Defer)
- Runway backup (use points as fallback)
- Paddle international payments
- Full i18n UI (content moderation already multi-language)
- Admin dashboard (use DB directly)

---

## Launch Checklist

### Pre-Launch (Dec 27)
- [ ] All P0 features complete
- [ ] Security audit passed
- [ ] Payment flow tested
- [ ] Load testing done
- [ ] Backup system verified

### Launch Day (Dec 28)
- [ ] DNS configured
- [ ] SSL certificate active
- [ ] Monitoring enabled
- [ ] Error alerts configured
- [ ] Support channel ready

### Post-Launch (Dec 29+)
- [ ] Monitor error rates
- [ ] Track user signups
- [ ] Gather feedback
- [ ] Fix critical bugs
- [ ] Plan Phase 2 features

---

## API Keys Needed

| Service | Where to Get | Priority | Status |
|---------|--------------|----------|--------|
| Gemini | ai.google.dev | P0 | ✅ Integrated |
| GoEnhance | goenhance.ai | P0 | ✅ Integrated (Nano Banana + V2V) |
| Pollo AI | pollo.ai | P0 | ✅ Integrated (Pixverse I2V) |
| Leonardo AI | leonardo.ai | P1 | ⏳ Pending |
| ECPay | ecpay.com.tw | P0 | ⏳ Pending |
| Paddle | paddle.com | P2 | ⏳ Pending |
| Runway | runway.ml | P2 | ⏳ Pending |

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
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# AI Services
GEMINI_API_KEY=your-gemini-key
GOENHANCE_API_KEY=your-goenhance-key
LEONARDO_API_KEY=your-leonardo-key
POLLO_API_KEY=your-pollo-key

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@vidgo.ai
EMAIL_VERIFICATION_EXPIRE_HOURS=24

# Frontend
FRONTEND_URL=http://localhost:8501
```

---

*Last Updated: December 23, 2024*
