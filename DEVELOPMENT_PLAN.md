# VidGo Development Plan

## 🎯 Project Summary

| Item | Details |
|------|---------|
| **Project** | VidGo - AI Video Generation SaaS |
| **Target Launch** | December 28, 2024 |
| **Total Hours** | 105 hours (~13 working days) |
| **Initial Monthly Cost** | $150-200 USD (optimized) |
| **Break-even Point** | 10-15 paid users |

---

## 📅 Development Timeline

```
Dec 14-15  │ Phase 1: Core Infrastructure ✅ (4h)
           │
Dec 16-20  │ Phase 2: Smart Demo + Gemini ✅ (15h)
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

## ✅ Phase Checklist

### Phase 1: Core Infrastructure (4h) ✅ COMPLETE
- [x] FastAPI project setup
- [x] PostgreSQL database
- [x] Redis configuration
- [x] JWT authentication
- [x] Basic API routes

### Phase 2: Smart Demo + Content Moderation (15h) ✅ COMPLETE
- [x] Demo database schema
- [x] Prompt matching algorithm
- [x] Demo video serving
- [x] Watermark overlay
- [x] Gemini API integration
- [x] Keyword fallback filter
- [x] Unit tests

### Phase 3: Leonardo + Runway (18h) ⏳ PENDING
- [ ] Leonardo API wrapper
- [ ] 720p/1080p generation
- [ ] Runway API wrapper
- [ ] Health check service
- [ ] Auto-failover logic
- [ ] Status monitoring
- [ ] Integration tests

### Phase 4: Pollo + GoEnhance (12h) ⏳ PENDING
- [ ] Point balance system
- [ ] Monthly reset logic
- [ ] Pollo API integration
- [ ] GoEnhance API integration
- [ ] Style transformation
- [ ] Point deduction logic

### Phase 5: UI/UX (10h) ⏳ PENDING
- [ ] Streamlit main app
- [ ] Generation interface
- [ ] User dashboard
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
- [ ] English (en)
- [ ] Japanese (ja)
- [ ] Traditional Chinese (zh-TW)
- [ ] Korean (ko)
- [ ] Spanish (es)
- [ ] Language detection

### Phase 8: Admin Dashboard (8h) ⏳ PENDING
- [ ] User management
- [ ] Generation stats
- [ ] Revenue reports
- [ ] Moderation queue
- [ ] System health

### Phase 9: Security + Deploy (12h) ⏳ PENDING
- [ ] Rate limiting
- [ ] CORS whitelist
- [ ] Input validation
- [ ] SQL injection prevention
- [ ] XSS protection
- [ ] Docker setup
- [ ] CI/CD pipeline
- [ ] Production deploy
- [ ] Monitoring setup

---

## 💰 Cost Optimization Strategy

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

## 🔑 Critical Path Items

### Must-Have for Launch
1. ✅ User authentication (JWT)
2. ✅ Content moderation (Gemini)
3. ⏳ Leonardo video generation
4. ⏳ Basic payment (ECPay)
5. ⏳ Point system
6. ⏳ Streamlit UI

### Nice-to-Have (Can Defer)
- Runway backup (use points as fallback)
- Paddle international payments
- Full i18n (start with EN + ZH-TW)
- Admin dashboard (use DB directly)

---

## 📁 Key Files to Create

```
vidgo/
├── app/
│   ├── main.py                 # FastAPI entry
│   ├── config.py               # Settings
│   ├── api/
│   │   ├── auth.py             # Login/register
│   │   ├── generation.py       # Video generation
│   │   ├── points.py           # Point management
│   │   └── payments.py         # ECPay/Paddle
│   ├── services/
│   │   ├── leonardo.py         # Leonardo API
│   │   ├── runway.py           # Runway API (Phase 2)
│   │   ├── pollo.py            # Pollo API
│   │   ├── goenhance.py        # GoEnhance API
│   │   └── moderation.py       # Gemini moderation
│   └── core/
│       ├── security.py         # JWT, hashing
│       └── failover.py         # Auto-switch logic
├── frontend/
│   ├── app.py                  # Streamlit main
│   └── pages/
│       ├── generate.py         # Generation page
│       ├── gallery.py          # Style gallery
│       └── account.py          # User settings
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 🚀 Launch Checklist

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

## 📞 API Keys Needed

| Service | Where to Get | Priority |
|---------|--------------|----------|
| Leonardo AI | leonardo.ai | P0 |
| Gemini | ai.google.dev | P0 |
| ECPay | ecpay.com.tw | P0 |
| Pollo AI | pollo.ai | P1 |
| GoEnhance | goenhance.ai | P1 |
| Paddle | paddle.com | P2 |
| Runway | runway.ml | P2 |

---

*Last Updated: December 2024*
