# VidGo API Workflow

> Current system architecture and API flow documentation.
> Generated: 2026-02-06

---

## System Overview

VidGo operates in **PRESET-ONLY MODE**:
- Demo/free users get **watermarked** pre-generated results from Material DB
- Subscribers get **real-time** AI generation via external APIs
- No custom text input for demo users
- Downloads blocked for demo users

### Stack

| Component | Tech | Port |
|-----------|------|------|
| Frontend | Vue 3 + TypeScript | 8501 |
| Backend API | FastAPI + SQLAlchemy | 8001 |
| Database | PostgreSQL 15 | 5432 |
| Cache/Queue | Redis 7 | 6379 |
| Worker | ARQ (async task queue) | — |
| Mail | Mailpit (dev) | 8025 |

---

## 1. Authentication Flow

### Register → Verify → Login

```
POST /api/v1/auth/register
  {email, password, password_confirm}
      ↓
  Create user (email_verified=false)
  Generate 6-digit code → send email
  Save code to Redis (24h TTL)
      ↓
POST /api/v1/auth/verify-email
  {email, verification_code}
      ↓
  Validate code from Redis
  Set email_verified=true
      ↓
POST /api/v1/auth/login
  {email, password}
      ↓
  Check: email_verified? is_active?
  Generate JWT token pair:
    - access_token (30 min)
    - refresh_token (7 days)
      ↓
  Return: {user, tokens: {access, refresh}}
```

### Token Refresh

```
POST /api/v1/auth/refresh
  {refresh_token}
      ↓
  Decode & validate refresh token
  Generate new token pair (both rotated)
      ↓
  Return: {access_token, refresh_token}
```

### Auth Dependency Chain

```
get_current_user_optional()     → User | None  (for tools - demo-ready)
  └─ get_current_user()         → User         (required login)
       └─ get_current_active_user() → User     (active check)
            └─ get_current_superuser() → User  (admin only)
```

---

## 2. Demo/Preset Flow (Anonymous Users)

All demo endpoints: **no auth required**, results **watermarked**.

```
User visits tool page (e.g. /tools/effects)
      ↓
GET /api/v1/demo/presets/{tool_type}
  → Returns pre-generated examples from Material DB
  → Each preset has: input_image, result_image, watermarked_url
      ↓
User clicks "Apply" / selects a preset
      ↓
POST /api/v1/demo/use-preset
  {preset_id, params}
      ↓
  Lookup Material DB by tool_type + topic
  Return watermarked result (NO external API calls)
      ↓
User sees watermarked result
  → Download blocked (403)
  → CTA: "Subscribe for Full Access"
```

### Demo Endpoints

| Endpoint | Returns |
|----------|---------|
| `GET /demo/topics` | All 8 tool types with their topics |
| `GET /demo/topics/{tool_type}` | Topics for specific tool |
| `GET /demo/presets/{tool_type}` | Pre-generated examples (watermarked) |
| `GET /demo/try-prompts/{tool_type}` | Selectable prompt options |
| `POST /demo/use-preset` | Apply preset → watermarked result |
| `GET /demo/download/{preset_id}` | **ALWAYS 403** (blocked for all) |

---

## 3. Tool Generation Flows (Subscribers)

### Two-Tier Logic (All Tools)

```
POST /api/v1/tools/{tool}
      ↓
  Auth: get_current_user_optional()
      ↓
  is_subscribed_user(user)?
      ↓                    ↓
    YES (subscriber)     NO (demo user)
      ↓                    ↓
  Check credits        Lookup Material DB
  Call external API    Return watermarked result
  Save to UserGen      Return {credits_used: 0}
  Deduct credits
  Return result
```

### Tool 1: Background Removal

```
POST /api/v1/tools/remove-bg
  {image_url}
      ↓
  Credits: 3
  API: PiAPI (GoEnhance background removal)
      ↓
  Result: Transparent PNG
```

### Tool 2: Product Scene

```
POST /api/v1/tools/product-scene
  {image_url, scene_type}
      ↓
  Credits: 10
  3-step pipeline:
    Step 1: Remove background (PiAPI)
    Step 2: Generate scene background (PiAPI T2I)
    Step 3: Composite product onto scene (PIL local)
      ↓
  Scene types: studio, nature, luxury, minimal, lifestyle, beach, urban, garden
```

### Tool 3: AI Try-On

```
POST /api/v1/tools/try-on
  {model_image_url | model_id, garment_image_url}
      ↓
  Credits: 15
  API: PiAPI (specialized try-on endpoint)
      ↓
  Models: 6 preset (3F + 3M)
  Result: Model wearing garment
```

### Tool 4: Room Redesign

```
POST /api/v1/tools/room-redesign
  {image_url, style_id, room_type}
      ↓
  Credits: 20
  API: PiAPI (Wan Doodle) → Gemini fallback
      ↓
  Styles: modern, nordic, japanese, industrial, minimalist, luxury, bohemian, coastal
  Room types: living_room, bedroom, kitchen, bathroom, office, dining, studio
```

### Tool 5: Short Video (I2V)

```
POST /api/v1/tools/short-video
  {image_url, motion_strength: 1-10, style?, script?, voice_id?}
      ↓
  Credits: 25 base (+5 for style, +5 for voice)
  API: PiAPI I2V (Wan model) → Pollo backup
    Optional: V2V enhancement (+5 credits)
    Optional: TTS audio (+5 credits)
      ↓
  Result: MP4 video (8 seconds default)
```

### Tool 6: AI Avatar

```
POST /api/v1/tools/avatar
  {image_url, script, language, voice_id, aspect_ratio, resolution}
      ↓
  Credits: 30
  API: A2E.ai (NO fallback)
    Step 1: TTS (text-to-speech)
    Step 2: Video generation (lipsync)
    Step 3: Poll for result (up to 300s)
      ↓
  Languages: en, zh-TW, ja, ko
  Aspect ratios: 9:16, 16:9, 1:1
  Result: MP4 video with talking avatar
```

### Tool 7: Image Effects (Style Transfer)

```
GET /api/v1/effects/styles         ← OPEN (no auth)
POST /api/v1/effects/apply-style   ← AUTH REQUIRED
  {image_url, style_id, intensity: 0.0-1.0}
      ↓
  Credits: 8
  API: GoEnhance (style transfer)
      ↓
  11 styles across 3 categories:
    Artistic: anime, ghibli, cartoon, clay, cute_anime, oil_painting, watercolor
    Modern: cyberpunk, vintage, pop_art
    Professional: cinematic, product

POST /api/v1/effects/hd-enhance    ← AUTH REQUIRED
  {image_url, target_resolution: "2k"|"4k"}
  Credits: 12

POST /api/v1/effects/video-enhance ← AUTH REQUIRED
  {video_url, enhancement_type: "quality"|"stabilize"|"denoise"}
  Credits: 15
```

### Tool 8: Pattern Generate

```
POST /api/v1/tools/pattern-generate (via /generate/pattern/*)
  {prompt, product_type}
      ↓
  Credits: varies
  API: PiAPI T2I
      ↓
  Topics: ingredients, equipment, meals, drinks, packaging, desserts, signage, snacks
```

---

## 4. Provider Routing

External AI services with failover:

| Task | Primary | Backup | Model |
|------|---------|--------|-------|
| Text-to-Image (T2I) | PiAPI | Pollo | flux1-schnell |
| Image-to-Video (I2V) | PiAPI | Pollo | wan2.6-i2v |
| Text-to-Video (T2V) | PiAPI | Pollo | wan2.6-t2v |
| Video Style (V2V) | PiAPI | Pollo | wan2.1-vace |
| Interior Design | PiAPI | Gemini | wan2.1-doodle |
| Avatar | A2E.ai | NONE | — |
| Background Removal | PiAPI | NONE | GoEnhance |
| Effects / Style | GoEnhance | NONE | — |
| Content Moderation | Gemini | NONE | — |

### Failover Logic

```
Try primary provider
  ↓ success → return result
  ↓ failure
Try backup provider (if configured)
  ↓ success → return result (used_backup=true)
  ↓ failure
Raise error: "All providers failed"
```

---

## 5. Credit & Quota System

### Credit Costs Per Tool

| Tool | Credits |
|------|---------|
| Background Removal | 3 |
| Product Scene | 10 |
| AI Try-On | 15 |
| Room Redesign | 20 |
| Short Video | 25-35 |
| AI Avatar | 30 |
| Apply Style Effect | 8 |
| HD Enhance | 12 |
| Video Enhance | 15 |

### Credit Flow (Subscribers)

```
POST /tools/{tool}
      ↓
  Check: remaining_credits >= cost?
    NO → Error: "Insufficient credits"
    YES ↓
  Execute tool (call provider API)
      ↓ success
  Create CreditTransaction (negative amount)
  Update user balance
      ↓
  Return: {result, credits_used}
```

### Free Quota (Demo Users)

```
DAILY_FREE_QUOTA = 100 (site-wide per day)
USER_FREE_TRIALS = 5  (per IP, lifetime)

GET /api/v1/quota/daily   → {remaining, total, reset_at}
GET /api/v1/quota/user    → {remaining, total, is_exhausted}
POST /api/v1/quota/use    → decrement both counters
```

---

## 6. Subscription Flow

### Subscribe

```
POST /api/v1/subscriptions/subscribe
  {plan_id, billing_cycle: "monthly"|"yearly", payment_method: "paddle"|"ecpay"}
      ↓
  Create Order
  Generate payment checkout URL (Paddle or ECPay)
      ↓
  Return: {subscription_id, checkout_url}
      ↓
  User completes payment
      ↓
  Webhook confirms → activate plan
  Set user.current_plan_id, plan_expires_at
  Add monthly_credits to balance
```

### Plan Tiers

| Plan | Monthly Credits | Price |
|------|----------------|-------|
| Demo | 0 | Free |
| Starter | 100 | — |
| Pro | 250 | — |
| Pro+ | 500 | — |

### Check Status

```
GET /api/v1/subscriptions/status (auth required)
  → {has_subscription, plan, credits, start/end dates, refund_eligible}

GET /api/v1/credits/balance (auth required)
  → {monthly_credits, used, remaining, bonus_credits}
```

---

## 7. Material DB (Pre-generation)

### Current Status

| Tool | Status | Count | Topics |
|------|--------|-------|--------|
| pattern | ✅ Ready | 59 | 8 topics |
| product | ✅ Ready | 35 | 8 scenes |
| avatar | ✅ Ready | 22 | 4 categories (8 avatars × 11 scripts) |
| effect | ✅ Ready | 20 | 5 styles × 3 sources |
| background_removal | ✅ Ready | — | 5 topics |
| room_redesign | ✅ Ready | — | 8 styles |
| video | ❌ | 2 | missing tutorial, promo |
| landing | ❌ | 4 | missing most categories |
| try_on | — | 0 | optional, not seeded |

### Pre-generation Pipeline

```
Script: python -m scripts.main_pregenerate --tool {tool} --per-topic-limit N

For each source × style combination:
  Step 1: Generate source image (T2I)
  Step 2: Apply transformation (I2I, I2V, A2E, etc.)
  Step 3: Add watermark
  Step 4: Store to Material DB
```

### Seed on Startup

```
Docker entrypoint:
  1. Wait for postgres + redis
  2. Run migrations
  3. Seed pricing plans
  4. CLEAN_MATERIALS={tool} → delete + re-seed (optional)
  5. Check material status (required tools block startup)
  6. Seed if empty
  7. Start uvicorn
```

---

## 8. Frontend Routes

### Public Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | LandingPage | Marketing page |
| `/tools/background-removal` | BackgroundRemoval | Remove backgrounds |
| `/tools/product-scene` | ProductScene | Product scene generation |
| `/tools/try-on` | TryOn | Virtual try-on |
| `/tools/room-redesign` | RoomRedesign | Room redesign |
| `/tools/short-video` | ShortVideo | Image-to-video |
| `/tools/avatar` | AIAvatar | AI avatar videos |
| `/tools/effects` | ImageEffects | Style transfer |
| `/topics/pattern` | PatternTopic | Pattern generation |
| `/topics/product` | ProductTopic | Product examples |
| `/topics/video` | VideoTopic | Video examples |

### Auth Pages

| Route | Page |
|-------|------|
| `/auth/login` | Login |
| `/auth/register` | Register |
| `/auth/verify` | Email verification |
| `/auth/forgot-password` | Password reset |

### Dashboard (Auth Required)

| Route | Page |
|-------|------|
| `/dashboard` | Dashboard |
| `/dashboard/my-works` | My generations |
| `/dashboard/invoices` | Billing history |

### Admin (Superuser Only)

| Route | Page |
|-------|------|
| `/admin` | Admin dashboard |
| `/admin/users` | User management |
| `/admin/materials` | Material management |

---

## 9. Complete Request Examples

### Example A: Anonymous User Tries Effects

```
1. Visit /tools/effects
2. GET /api/v1/effects/styles          → 11 styles (open, no auth)
3. GET /api/v1/demo/presets/effect     → 20 examples (watermarked)
4. User selects anime style + bubble tea example
5. Click "Apply Style"
6. Frontend shows watermarked result from preset
7. Download button → "Subscribe for Full Access"
```

### Example B: Subscriber Generates AI Avatar

```
1. POST /api/v1/auth/login             → {tokens}
2. GET /api/v1/credits/balance          → {remaining: 220}
3. POST /api/v1/tools/avatar
     {image_url, script: "...", language: "zh-TW", voice_id: "zh_female_1"}
4. Backend: is_subscribed_user? YES
5. Backend: remaining_credits (220) >= 30? YES
6. A2E.ai: TTS → video generate → poll result
7. Save to UserGeneration, deduct 30 credits
8. Return: {success, result_url, credits_used: 30}
9. User can download non-watermarked video
```

### Example C: Demo User Browses Product Scenes

```
1. Visit /tools/product-scene
2. GET /api/v1/demo/presets/product_scene → 35 examples
3. User selects studio scene
4. Click "Generate"
5. Backend: is_subscribed_user? NO
6. Return watermarked Material DB result
7. No API calls, no credits
8. Download blocked → pricing CTA
```

---

## 10. API Service Status

Check all external services:

```
GET /api/v1/generate/service-status
  → {
      piapi: "ok",       # T2I, I2V, I2I, bg removal
      pollo: "ok",       # Backup provider
      goenhance: "ok",   # Effects, enhancement
      a2e: "ok",         # AI Avatar
      gemini: "ok"       # Moderation, interior backup
    }
```
