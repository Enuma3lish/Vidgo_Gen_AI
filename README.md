# Vidgo_Gen_AI
# VidGo Final - Complete Architecture

Smart Demo AI Image/Video Generation Platform  
**Leonardo + Runway Unlimited | Pollo + GoEnhance Credits | Auto Recovery | Security**

---

## 🎯 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              VidGo vFinal Architecture                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                        🌐 User Interface Layer                            │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐    │  │
│  │  │ Frontend│ │ Speech  │ │ Social  │ │ Admin   │ │ 🎨 Style Gallery│    │  │
│  │  │Streamlit│ │ to Text │ │ Upload  │ │ Panel   │ │ (Upgrade CTA)   │    │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────────────┘    │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │              🛡️ Security Layer (JWT + Rate Limit + HTTPS)                │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │              🔍 Content Moderation (Gemini API + Keyword Filter)         │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                     🔓 UNLIMITED SERVICES                                 │  │
│  │                  Leonardo AI  ←──────→  Runway                           │  │
│  │                      (Primary)    (Auto Failover)                        │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                     🎫 CREDITS SERVICES                                   │  │
│  │                   Pollo AI  |  GoEnhance AI (🌟 Core Selling Point)      │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │              💰 Dual Payment (ECPay Taiwan | Paddle Global)              │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Service Tiers

| Tier | Price | Unlimited Services | Credits Services | Max Resolution |
|------|-------|-------------------|------------------|----------------|
| **Demo** | $0 | Smart Demo Only | — | 720p + Watermark |
| **Starter** | NT$299 | Leonardo 720p + Runway | 1080p credits + Pollo Basic | 1080p |
| **Pro** | NT$599 | Leonardo 720p/1080p + Runway | Full Pollo + GoEnhance | 4K |
| **Unlimited** | NT$999 | Leonardo 720p/1080p + Runway + Priority | More Pollo + GoEnhance | 4K 60fps |

### Service Classification

| Type | Platforms | Billing | Role |
|------|-----------|---------|------|
| 🔓 **Unlimited** | Leonardo AI | Subscription | Core generation |
| 🔓 **Unlimited** | Runway *(scale-up)* | Subscription | Failover (add when users >50) |
| 🎫 **Credits** | Pollo AI, GoEnhance | Per-use | Advanced features (🌟 upgrade incentive) |

---

## 🎨 UI Design - Upgrade Incentive Zone

### Style Showcase Gallery

| Position | Content | Purpose |
|----------|---------|---------|
| Homepage Top | GoEnhance style carousel | First impression |
| Generation Page | "Unlock More Styles" preview | Show possibilities |
| Profile Center | Weekly popular styles | Social proof |
| Sidebar | "Upgrade Now" floating button | Constant reminder |

### GoEnhance Style Examples

| Category | Style Name | Use Case |
|----------|------------|----------|
| 🎌 Anime | Japanese Anime, Makoto Shinkai | Personal, Social |
| 🎬 3D Animation | Pixar, Disney | Kids content, Ads |
| 🏺 Claymation | Stop-motion | Creative ads, Art |
| 🎨 Artistic | Oil painting, Watercolor | Art display, Branding |
| 📺 Retro | 80s, VHS effect | Nostalgia, Music MV |
| 🎮 Gaming | Pixel art, Cyberpunk | Game promo, Tech |

---

## 🎫 Credits System

### Credits Consumption

| Platform | Feature | Resolution | Credits | Tier |
|----------|---------|------------|---------|------|
| Leonardo | Image | 1080p | 2 | Starter+ |
| Leonardo | Video | 1080p | 10 | Starter+ |
| Pollo | Basic effect | 1080p | 5 | Starter+ |
| Pollo | 4K video | 4K | 15 | Pro+ |
| GoEnhance | Style transfer | 1080p | 10 | Pro+ |
| GoEnhance | Style transfer | 4K | 25 | Pro+ |
| GoEnhance | 4K upscaling | → 4K | 15 | Pro+ |
| GoEnhance | AI face swap | Any | 20 | Pro+ |

### Credits Purchase

| Package | Price | Credits | Tier |
|---------|-------|---------|------|
| Small | NT$99 / $2.99 | 50 | Starter+ |
| Medium | NT$249 / $7.99 | 150 | Starter+ |
| Large | NT$699 / $22.99 | 500 | Pro+ |
| **Value** | NT$559 / $18.39 | 500 (20% off) | **Unlimited Only** |

---

## 🔄 Auto Recovery System

### Initial Phase (Leonardo Only)

| Leonardo | System Behavior |
|----------|-----------------|
| ✅ Online | Use Leonardo (primary) |
| ❌ Down | Auto-switch to Credits Services (Pollo/GoEnhance) |

### Scale-up Phase (Add Runway when users > 50)

| Leonardo | Runway | System Behavior |
|----------|--------|-----------------|
| ✅ Online | ✅ Online | Use Leonardo (primary) |
| ❌ Down | ✅ Online | Auto-switch to Runway |
| ✅ Online | ❌ Down | Continue with Leonardo |
| ❌ Down | ❌ Down | Enable Credits Services |

### Complete Recovery Table

| Service | Primary | Fallback | Final |
|---------|---------|----------|-------|
| Content Moderation | Gemini API | Keyword Filter | Pass + Manual |
| Demo Engine | DB Match | Leonardo 720p | Static Demo |
| Unlimited Generation | Leonardo | Credits (→Runway later) | Queue |
| Credits Services | Pollo/GoEnhance | Cross-backup | Refund |
| Payment | ECPay/Paddle | Cross-backup | Manual |

---

## 🛡️ Security

### Authentication & Authorization

| Mechanism | Technology | Details |
|-----------|------------|---------|
| JWT Token | Access + Refresh | Access: 15min / Refresh: 7days |
| Password | bcrypt + salt | 12 rounds hashing |
| API Key | HMAC-SHA256 | External API auth |

### API Security

| Protection | Setting | Purpose |
|------------|---------|---------|
| Rate Limiting | 100 req/min per IP | Prevent brute force |
| CORS | Whitelist domains | Cross-origin control |
| HTTPS | TLS 1.3 required | Encrypted transport |
| Input Validation | Pydantic | Strict validation |
| SQL Injection | ORM | Parameterized queries |
| XSS | CSP headers | Script injection prevention |

### Content & Payment Security

- **Gemini API**: 18+ / Violence / Illegal content detection
- **IP Ban System**: Auto-ban repeat violators
- **PCI DSS**: Card data handled by ECPay/Paddle
- **Webhook Signature**: Verify callback signatures
- **Database Encryption**: AES-256 at rest + Daily backup

---

## 💰 Cost Analysis (Initial 1-3 Months Optimized)

### Strategy
Low-cost operation initially, scale services as users grow.

### Monthly Fixed Costs

| Item | Original | Optimized | Strategy |
|------|----------|-----------|----------|
| Leonardo AI | $60 | **$60** | Essential, keep |
| Runway | $76 | **$0** | Skip initially, use credits as fallback |
| Infrastructure | $80 | **$45** | Low-spec VPS (Hetzner/Linode) |
| Gemini API | $20 | **$8** | Use free tier + keyword filter |
| Pollo AI | $40 | **$15** | Low initial usage |
| GoEnhance | $60 | **$25** | Mainly for showcase |
| Whisper API | $30 | **$5** | Defer or use local OSS |
| Others | $20 | **$10** | Free tools (Sentry, Cloudflare) |
| **Total** | **$386** | **$168** | **Save 56%** |

### Revenue & Profit (Optimized)

| Metric | Value |
|--------|-------|
| Monthly Revenue | NT$37,927 (~USD $1,185) |
| Monthly Cost (Initial) | NT$5,376 (~USD $168) |
| Monthly Profit | NT$32,551 (~USD $1,017) |
| **Profit Margin** | **85.8%** |
| **Break-even** | **10-15 paying users** |

### Scale-up Triggers

| Service | When to Add |
|---------|-------------|
| Runway | Paying users > 50 or Leonardo downtime increases |
| Upgrade Infrastructure | DAU > 100 |
| Whisper API | Clear voice feature demand |

---

## 💳 Dual Payment Gateway

| Feature | ECPay | Paddle |
|---------|-------|--------|
| Region | Taiwan only | Global |
| Fee | 2.5-2.75% | 5% + $0.50 |
| Methods | Credit Card, ATM, CVS, LINE Pay | Credit Card, PayPal, Apple Pay |

---

## 🌍 Internationalization (i18n)

| Language | Code | Regions |
|----------|------|---------|
| English | `en` | US, UK, AU (default) |
| 日本語 | `ja` | JP |
| 繁體中文 | `zh-TW` | TW, HK |
| 한국어 | `ko` | KR |
| Español | `es` | ES, MX, AR |

---

## 📅 Development Timeline

| # | Phase | Hours |
|---|-------|-------|
| 1 | Core Infrastructure (FastAPI, PostgreSQL, Redis, Auth) | 4h |
| 2 | Smart Demo Engine + Gemini Moderation | 15h |
| 3 | Leonardo + Runway Unlimited + Auto Switch | 18h |
| 4 | Pollo + GoEnhance Credits System | 12h |
| 5 | Upgrade Incentive Zone + UI/UX (Streamlit) | 10h |
| 6 | Dual Payment (ECPay + Paddle) | 20h |
| 7 | i18n (EN/JA/ZH-TW/KO/ES) | 6h |
| 8 | Admin Dashboard + Monitoring | 8h |
| 9 | Security Hardening + Testing + Deployment | 12h |
| **Total** | | **105h (~13 days)** |

**Target Launch: December 28, 2024**

---

## 📈 KPI Targets

| Metric | Target |
|--------|--------|
| Demo → Starter Conversion | 5-8% |
| System Availability | 99.9% |
| Refund Rate | < 3% |
| Monthly Revenue | NT$37,927+ |
| Profit Margin | 85%+ |
| Break-even | 10-15 paying users |

---

## 🔧 Environment Variables

```env
# Django/FastAPI
SECRET_KEY=xxx
DEBUG=false

# Database
DATABASE_URL=postgres://user:pass@host:5432/vidgo
REDIS_URL=redis://host:6379/0

# Security
JWT_SECRET_KEY=xxx
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15

# Content Moderation
GEMINI_API_KEY=xxx

# Unlimited Services
LEONARDO_API_KEY=xxx
RUNWAY_API_KEY=xxx

# Credits Services
POLLO_API_KEY=xxx
GOENHANCE_API_KEY=xxx

# Payment - ECPay (Taiwan)
ECPAY_MERCHANT_ID=xxx
ECPAY_HASH_KEY=xxx
ECPAY_HASH_IV=xxx

# Payment - Paddle (Global)
PADDLE_VENDOR_ID=xxx
PADDLE_API_KEY=xxx
PADDLE_WEBHOOK_SECRET=xxx

# i18n
DEFAULT_LANGUAGE=en
SUPPORTED_LANGUAGES=en,ja,zh-TW,ko,es
```

---

## License

MIT License
