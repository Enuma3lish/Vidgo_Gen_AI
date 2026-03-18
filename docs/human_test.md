# VidGo AI Platform — Manual Browser Test Cases

**Last Updated:** March 18, 2026
**Frontend URL:** `http://localhost:8501`
**Backend API:** `http://localhost:8001`
**Swagger Docs:** `http://localhost:8001/docs`
**Mailpit (dev email):** `http://localhost:8025`

---

## Prerequisites

Before testing, ensure all services are running:

```bash
docker compose up -d
# Verify:
curl http://localhost:8001/health          # Backend health
curl http://localhost:8001/materials/status # Material DB ready
open http://localhost:8501                  # Frontend loads
open http://localhost:8025                  # Mailpit (email testing)
```

---

## Test Legend

- **Priority:** P0 (Critical) / P1 (High) / P2 (Medium) / P3 (Low)
- **Role:** Guest = not logged in, User = registered user, Subscriber = paid user, Admin = superuser
- Pass: ✅ | Fail: ❌ | Blocked: ⛔ | Skipped: ⏭️

---

## 1. Landing Page (P0) — Role: Guest

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 1.1 | Landing page loads | Navigate to `/` | Page loads with hero section, feature highlights, examples, testimonials, pricing, FAQ | |
| 1.2 | Platform stats display | Check stats section on landing | Shows total generations, users, tools count (from `GET /landing/stats`) | |
| 1.3 | Feature highlights | Scroll to features section | All 10 AI tools listed with descriptions and icons | |
| 1.4 | Example gallery | Scroll to examples section | Before/after examples render correctly with images | |
| 1.5 | Testimonials carousel | Scroll to testimonials | Testimonials display with names and quotes | |
| 1.6 | Pricing section | Scroll to pricing | Plans displayed with prices, credits, features | |
| 1.7 | FAQ section | Scroll to FAQ | Questions expand/collapse on click | |
| 1.8 | Contact form | Fill out and submit contact form | Success message shown, email received in Mailpit | |
| 1.9 | Navigation links | Click each nav item (Tools, Topics, Pricing) | Navigates to correct page | |
| 1.10 | Language selector | Switch language (e.g., EN → 繁中 → 日本語 → 한국어 → ES) | All visible text translates correctly | |
| 1.11 | Responsive layout | Resize browser to mobile width (375px) | Layout adapts, hamburger menu appears | |
| 1.12 | CTA buttons | Click "Get Started" / "Try Free" | Redirects to register page or tool page | |

---

## 2. Authentication (P0) — Role: Guest → User

### 2.1 Registration

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 2.1.1 | Register with valid email | Go to `/auth/register`, fill email + password + confirm | Account created, verification email sent, redirect to verify page | |
| 2.1.2 | Password validation | Enter weak password (< 8 chars) | Error: password too short | |
| 2.1.3 | Password mismatch | Enter different passwords | Error: passwords don't match | |
| 2.1.4 | Duplicate email | Register with existing email | Error: email already registered | |
| 2.1.5 | Referral code registration | Go to `/auth/register?ref=TESTCODE` | Referral code field pre-filled; after registration, both users receive bonus credits | |
| 2.1.6 | Empty fields | Submit with empty fields | Validation errors for all required fields | |

### 2.2 Email Verification

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 2.2.1 | Verify with correct code | Check Mailpit for 6-digit code, enter on verify page | Email verified, can now login | |
| 2.2.2 | Verify with wrong code | Enter incorrect code | Error: invalid verification code | |
| 2.2.3 | Resend verification | Click "Resend Code" | New email sent, old code invalidated | |
| 2.2.4 | Expired code | Wait 24h (or modify Redis TTL in test) | Error: code expired | |

### 2.3 Login

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 2.3.1 | Login with valid credentials | Go to `/auth/login`, enter email + password | Logged in, redirected to dashboard, JWT stored | |
| 2.3.2 | Login with wrong password | Enter incorrect password | Error: invalid credentials | |
| 2.3.3 | Login with unverified email | Try login before verifying | Error: email not verified | |
| 2.3.4 | Login with banned account | Try login as banned user | Error: account suspended | |
| 2.3.5 | Token refresh | Wait 30 min (access token expiry), then perform action | Token auto-refreshed, action succeeds | |
| 2.3.6 | Logout | Click logout button | Redirected to landing, JWT cleared | |

### 2.4 Password Recovery

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 2.4.1 | Forgot password | Go to `/auth/forgot-password`, enter email | Reset email sent to Mailpit | |
| 2.4.2 | Reset password | Click link in email, enter new password | Password updated, can login with new password | |
| 2.4.3 | Reset with invalid token | Modify reset token URL | Error: invalid or expired token | |

### 2.5 Profile & Account

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 2.5.1 | View profile | Go to dashboard, check profile section | Shows email, plan, credits, member since | |
| 2.5.2 | Update profile | Change display name | Profile updated successfully | |
| 2.5.3 | Change password | Enter old + new password | Password changed, can login with new | |
| 2.5.4 | Delete account | Click "Delete Account" → confirm | Account deleted, works retained for 7 days, logged out | |

---

## 3. Demo/Preset Mode — AI Tools (P0) — Role: Guest

> Test each tool in demo mode (no login required). Demo results should be **watermarked** and **download blocked**.

### 3.1 Background Removal

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 3.1.1 | Load preset gallery | Navigate to `/tools/background-removal` | Pre-generated examples load with before/after images | |
| 3.1.2 | Select topic | Click different topics (drinks, snacks, meals, etc.) | Gallery filters by selected topic | |
| 3.1.3 | Apply preset | Click "Apply" on a preset | Watermarked result displayed (no API call, instant) | |
| 3.1.4 | Download blocked | Click "Download" | Blocked with upgrade prompt / subscription CTA | |
| 3.1.5 | Before/after slider | Drag the before/after slider | Smoothly reveals original vs. result | |

### 3.2 Product Scene

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 3.2.1 | Load preset gallery | Navigate to `/tools/product-scene` | Scene examples load (studio, nature, luxury, etc.) | |
| 3.2.2 | Select scene type | Click different scene types | Gallery filters correctly | |
| 3.2.3 | Apply preset | Select preset and apply | Watermarked product-in-scene result shown | |
| 3.2.4 | Multiple scenes | Apply different scenes for same product | Different background scenes shown | |

### 3.3 Virtual Try-On

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 3.3.1 | Load presets | Navigate to `/tools/try-on` | Model + garment presets load | |
| 3.3.2 | Select model gender | Toggle male/female | Model presets change accordingly | |
| 3.3.3 | Apply try-on | Select model + garment, click apply | Watermarked try-on result shown | |
| 3.3.4 | Different garments | Try multiple garments on same model | Each shows different result | |

### 3.4 Room Redesign

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 3.4.1 | Load room presets | Navigate to `/tools/room-redesign` | Default room images load | |
| 3.4.2 | Select style | Choose style (modern, nordic, japanese, industrial, etc.) | Style option highlighted | |
| 3.4.3 | Select room type | Choose room type (living room, bedroom, kitchen) | Room type selected | |
| 3.4.4 | Apply redesign | Click apply with room + style selection | Watermarked redesigned room shown | |
| 3.4.5 | Style comparison | Apply different styles to same room | Visually different results per style | |

### 3.5 Short Video

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 3.5.1 | Load video presets | Navigate to `/tools/short-video` | Video presets load with thumbnails | |
| 3.5.2 | Play preview | Click on a video preset | Video plays in browser (watermarked) | |
| 3.5.3 | Different topics | Switch between product_showcase, brand_intro, tutorial, promo | Different video examples shown | |

### 3.6 AI Avatar

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 3.6.1 | Load avatar presets | Navigate to `/tools/avatar` | Avatar video presets load | |
| 3.6.2 | Preview avatar | Click on preset | Avatar video plays with lip-sync audio | |
| 3.6.3 | Language options | Check available languages (EN, 中文, 日本語, 한국어) | Language options visible | |

### 3.7 Pattern Design

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 3.7.1 | Load pattern presets | Navigate to `/tools/pattern-generate` | Pattern examples load (seamless, floral, geometric, etc.) | |
| 3.7.2 | Apply pattern | Select and apply a pattern preset | Watermarked pattern result shown | |
| 3.7.3 | Pattern transfer | Navigate to `/tools/pattern-transfer` | Pattern transfer presets available | |

### 3.8 Image Effects / Style Transfer

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 3.8.1 | Load effects presets | Navigate to `/tools/effects` | Effect examples load (anime, ghibli, cartoon, oil painting, etc.) | |
| 3.8.2 | Apply effect | Select a style effect | Watermarked styled result shown | |
| 3.8.3 | Image transform | Navigate to `/tools/image-transform` | Image-to-image transform presets available | |

### 3.9 Cross-Tool Demo Checks

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 3.9.1 | Demo usage limit | As guest, use 2+ demo presets | After demo_usage_limit (default 2), prompted to register | |
| 3.9.2 | Watermark on all results | Check every tool's demo result | ALL demo results have visible watermark | |
| 3.9.3 | No API calls in demo | Open browser DevTools > Network | No calls to external AI providers (PiAPI, Pollo, A2E) | |
| 3.9.4 | Inspiration gallery | Navigate to inspiration section | Mixed gallery of all tool results loads | |

---

## 4. Subscriber Tool Generation (P0) — Role: Subscriber

> Test each tool with actual AI generation (requires active subscription + credits).

### 4.1 Background Removal (Subscriber)

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 4.1.1 | Upload image | Click upload zone, select product image (JPEG/PNG, < 20MB) | Image uploaded and previewed | |
| 4.1.2 | Remove background | Click "Remove Background" | Spinner shown → transparent PNG result (no watermark) | |
| 4.1.3 | Download result | Click "Download" | Full-quality PNG downloaded without watermark | |
| 4.1.4 | Credits deducted | Check credit balance after generation | 3 credits deducted | |
| 4.1.5 | Batch removal | Upload multiple images, click batch process | All images processed, credits = 3 × count | |
| 4.1.6 | Invalid file type | Upload a .pdf or .gif | Error: unsupported file format | |
| 4.1.7 | File too large | Upload image > 20MB | Error: file size exceeds limit | |

### 4.2 Product Scene (Subscriber)

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 4.2.1 | Upload product image | Upload product photo | Image shown in upload zone | |
| 4.2.2 | Select scene type | Choose from: studio, nature, luxury, minimal, lifestyle, beach, urban, garden | Scene type selected | |
| 4.2.3 | Generate scene | Click generate | Product composited into scene (BG removed → scene generated → composited) | |
| 4.2.4 | Download | Download result | Full-quality scene image, no watermark | |
| 4.2.5 | Credits | Check balance | 10 credits deducted | |

### 4.3 Virtual Try-On (Subscriber)

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 4.3.1 | Upload garment | Upload garment image | Garment image shown | |
| 4.3.2 | Select model | Choose preset model (male/female) or upload model image | Model selected | |
| 4.3.3 | Generate try-on | Click generate | Garment placed on model realistically | |
| 4.3.4 | Credits | Check balance | 15 credits deducted | |

### 4.4 Room Redesign (Subscriber)

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 4.4.1 | Upload room photo | Upload room image | Room shown in upload zone | |
| 4.4.2 | Select style + room type | Choose style (modern, nordic, etc.) + room type (living, bedroom, etc.) | Options selected | |
| 4.4.3 | Generate redesign | Click generate | Redesigned room with selected style | |
| 4.4.4 | Iterative edit | After first result, type edit instructions (e.g., "make walls lighter") | Updated room based on edit | |
| 4.4.5 | Credits | Check balance | 20 credits deducted per generation | |

### 4.5 Short Video (Subscriber)

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 4.5.1 | Image-to-video | Upload image + set motion strength | Video generated from image | |
| 4.5.2 | Text-to-video | Enter text prompt | Video generated from text | |
| 4.5.3 | Model selection | Choose different models (Standard, Pixverse v5, Kling v2, Wan Pro, Luma Ray2) | Higher-quality models produce better results, cost more credits | |
| 4.5.4 | Video playback | Play generated video | Video plays smoothly in browser | |
| 4.5.5 | Download video | Download result | Video file downloads (MP4) | |
| 4.5.6 | Credits by model | Check credits per model | Standard: 25, Pixverse v5: 37, Kling v2: 50, Wan Pro: 50, Luma Ray2: 75 | |

### 4.6 AI Avatar (Subscriber)

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 4.6.1 | Upload avatar image | Upload face/person image | Image previewed | |
| 4.6.2 | Enter script | Type script text | Script accepted | |
| 4.6.3 | Select language | Choose from EN, 中文, 日本語, 한국어 | Language selected | |
| 4.6.4 | Select voice | Choose voice from voice list | Voice selected | |
| 4.6.5 | Generate avatar | Click generate | Avatar video with lip-sync TTS generated | |
| 4.6.6 | Play result | Play avatar video | Audio synced with lip movements | |
| 4.6.7 | Credits | Check balance | 30 credits deducted | |

### 4.7 Model Selection (Subscriber)

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 4.7.1 | Default model | Generate with default model | Base credit cost (1× multiplier) | |
| 4.7.2 | Pixverse v5 | Select Pixverse v5 for short video | Credits = base × 1.5 | |
| 4.7.3 | Kling v2 | Select Kling v2 for try-on | Credits = base × 2 | |
| 4.7.4 | Wan Pro | Select Wan Pro for product scene | Credits = base × 2 | |
| 4.7.5 | Luma Ray2 | Select Luma Ray2 for short video | Credits = base × 3 | |
| 4.7.6 | Cost estimate | Before generating, check estimated cost | Estimate matches actual deduction | |

### 4.8 Insufficient Credits

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 4.8.1 | Insufficient credits | Try to generate with 0 credits | Error: insufficient credits (HTTP 402), upgrade prompt shown | |
| 4.8.2 | Credit estimate warning | Before generation, show estimated cost | Warning if balance < estimated cost | |

---

## 5. Subscription & Billing (P0) — Role: User → Subscriber

### 5.1 Plans & Pricing

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 5.1.1 | View pricing page | Navigate to `/pricing` | All plans displayed with features, credits, pricing | |
| 5.1.2 | Monthly vs yearly toggle | Toggle billing cycle | Prices update (yearly shows discount) | |
| 5.1.3 | Plan comparison | Compare plan features | Feature differences clearly shown | |
| 5.1.4 | Plan feature flags | Check which tools available per plan | Restricted tools show lock/upgrade icon | |

### 5.2 Subscribe Flow

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 5.2.1 | Subscribe (Paddle) | Click subscribe → Paddle checkout | Paddle checkout page opens | |
| 5.2.2 | Mock payment (dev) | Go to `/subscription/mock-checkout`, complete mock | Subscription activated, credits added | |
| 5.2.3 | Success page | After payment | Redirected to `/subscription/success` with confirmation | |
| 5.2.4 | Credits added | Check balance after subscribing | Monthly credits added to balance | |
| 5.2.5 | Subscription status | Check dashboard | Shows active plan name, expiry date, credits remaining | |

### 5.3 Cancel & Refund

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 5.3.1 | Cancel subscription | Go to dashboard → cancel subscription | Confirmation dialog, then subscription marked cancelled | |
| 5.3.2 | Cancelled page | After cancellation | Redirected to `/subscription/cancelled` | |
| 5.3.3 | Refund eligibility | Check within 7 days of purchase | Eligible for refund shown | |
| 5.3.4 | After 7 days | Check refund after 7 days | Not eligible | |
| 5.3.5 | Access after cancel | Try tools after cancellation | Can use until current period ends | |

### 5.4 Invoices

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 5.4.1 | View invoices | Go to `/dashboard/invoices` | List of invoices shown | |
| 5.4.2 | Download PDF | Click PDF download on invoice | PDF downloads with correct details | |
| 5.4.3 | Invoice details | Click on invoice | Shows amount, date, plan, status | |

---

## 6. Credits System (P1) — Role: Subscriber

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 6.1 | View balance | Check credit badge in header | Current balance displayed | |
| 6.2 | Transaction history | Go to credits page → transactions | Shows all credit changes with reason | |
| 6.3 | Purchase extra credits | Buy credit package (Starter/Standard/Premium) | Credits added, payment processed | |
| 6.4 | Credit packages | View available packages | Shows packages with prices and credit amounts | |
| 6.5 | Weekly reset | Wait for Monday reset (or simulate) | `subscription_credits` reset to plan allocation | |
| 6.6 | Purchased credits persist | After weekly reset | `purchased_credits` unchanged | |
| 6.7 | Bonus credits expiry | Check bonus credits with set expiry | Expired bonus credits become unavailable | |
| 6.8 | Credit cost estimate | Before each tool generation | Estimated cost matches tool + model multiplier | |

---

## 7. Promotions & Referrals (P1) — Role: User / Subscriber

### 7.1 Promotions

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 7.1.1 | View active promotions | Check promotions section | Active promos displayed with codes | |
| 7.1.2 | Validate promo code | Enter valid promo code | Shows discount/credits to be applied | |
| 7.1.3 | Apply promo code | Apply valid code | Credits/discount applied successfully | |
| 7.1.4 | Invalid promo code | Enter expired/invalid code | Error: invalid or expired promo code | |
| 7.1.5 | Already used code | Reuse same code | Error: code already used | |

### 7.2 Referrals

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 7.2.1 | View referral code | Go to `/dashboard/referrals` | Personal referral code displayed | |
| 7.2.2 | Copy referral link | Click copy button | Link copied to clipboard (includes `?ref=CODE`) | |
| 7.2.3 | Referral stats | View referral page | Shows total referrals, credits earned | |
| 7.2.4 | Referral leaderboard | View leaderboard | Top referrers displayed | |
| 7.2.5 | New user uses referral | Register via referral link | New user gets +20 credits, referrer gets +50 credits | |

---

## 8. User Dashboard (P1) — Role: Subscriber

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 8.1 | Dashboard overview | Navigate to `/dashboard` | Shows plan info, credit balance, recent generations, quick stats | |
| 8.2 | My Works gallery | Navigate to `/dashboard/my-works` | All user generations displayed in grid | |
| 8.3 | Generation detail | Click on a generation | Shows input, result, tool type, credits used, timestamp | |
| 8.4 | Download generation | Click download on a generation | Full-quality file downloads | |
| 8.5 | Delete generation | Click delete on a generation | Confirmation dialog → generation removed | |
| 8.6 | User stats | Check stats section | Shows total generations, credits used, favorite tool | |
| 8.7 | 14-day retention notice | Check generation older than 14 days | Media URLs cleared, message indicates expiry | |
| 8.8 | Pagination | If > 20 generations, check pagination | Pages load correctly | |

---

## 9. Social Media Publishing (P1) — Role: Subscriber

### 9.1 Connect Accounts

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 9.1.1 | Social accounts page | Navigate to `/dashboard/social-accounts` | Shows available platforms (FB, IG, TikTok, YouTube) | |
| 9.1.2 | Connect Facebook | Click Connect Facebook → OAuth flow | Facebook account linked, shown in connected list | |
| 9.1.3 | Connect Instagram | Click Connect Instagram → OAuth flow | Instagram account linked | |
| 9.1.4 | Connect TikTok | Click Connect TikTok → OAuth flow | TikTok account linked | |
| 9.1.5 | Connect YouTube | Click Connect YouTube → Google OAuth | YouTube account linked | |
| 9.1.6 | Mock connect (dev) | Use mock connect for testing | Account connected without real OAuth | |
| 9.1.7 | Disconnect account | Click disconnect on connected account | Account removed from list | |

### 9.2 Publish Content

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 9.2.1 | Share modal | From My Works, click share on a generation | ShareToSocialModal opens with platform checkboxes | |
| 9.2.2 | Select platforms | Check one or more platforms | Platforms highlighted | |
| 9.2.3 | Publish to Facebook | Select FB → publish | Post published, success message shown | |
| 9.2.4 | Publish to Instagram | Select IG → publish | Post published | |
| 9.2.5 | Publish to TikTok | Select TikTok → publish (video only) | Video published | |
| 9.2.6 | Publish to YouTube | Select YouTube → publish (video only) | Video uploaded via resumable upload API | |
| 9.2.7 | Multi-platform publish | Select all platforms → publish | Published to all selected platforms | |

### 9.3 Post History & Analytics

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 9.3.1 | Post history | Check post history section | Shows all published posts with platform, date, status | |
| 9.3.2 | Post analytics | Check analytics | Shows views, likes, shares per post | |
| 9.3.3 | Token refresh | (Dev) Set token to expire soon, then publish | Token auto-refreshed before publish succeeds | |

---

## 10. E-Invoice — Taiwan (P2) — Role: Subscriber

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 10.1 | Issue B2C invoice | After purchase, issue B2C invoice | Invoice created with carrier type (mobile barcode/citizen cert/email) | |
| 10.2 | Issue B2B invoice | Enter 8-digit tax ID (統一編號) | B2B invoice created with company info | |
| 10.3 | Donation invoice | Select donation code (愛心碼) | Invoice donated to charity organization | |
| 10.4 | Void invoice | Void an invoice (same bimonthly period) | Invoice voided successfully | |
| 10.5 | Invoice list | View invoice list | All e-invoices shown with details | |
| 10.6 | Invoice preferences | Set default carrier type | Preference saved, auto-applied on next invoice | |
| 10.7 | Invalid tax ID | Enter non-8-digit tax ID | Error: invalid tax ID format | |

---

## 11. Admin Dashboard (P1) — Role: Admin

### 11.1 Dashboard Overview

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 11.1.1 | Access admin | Navigate to `/admin` | Admin dashboard loads (superuser only) | |
| 11.1.2 | Non-admin access | Login as regular user, navigate to `/admin` | Redirected or 403 forbidden | |
| 11.1.3 | Online users stat | Check real-time card | Shows current online user count | |
| 11.1.4 | Users by tier | Check tier breakdown | Shows free / starter / pro / enterprise user counts | |
| 11.1.5 | Dashboard stats | Check overview cards | Total users, generations, revenue, active subscriptions | |
| 11.1.6 | Real-time updates | Keep dashboard open | WebSocket updates stats in real-time (no page refresh) | |

### 11.2 Charts & Analytics

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 11.2.1 | Generation chart | View generation trend chart | Line chart shows daily generation counts | |
| 11.2.2 | Revenue chart | View revenue chart | Line chart shows revenue over time | |
| 11.2.3 | User growth chart | View growth chart | Shows cumulative user registrations | |
| 11.2.4 | Tool usage chart | View tool usage | Bar/doughnut chart shows usage per tool | |
| 11.2.5 | Date range selector | Change range: 7D → 30D → 90D → 1Y → Custom | Charts update with selected date range | |
| 11.2.6 | Custom date range | Set custom start/end dates | Charts filter to exact date range | |
| 11.2.7 | Manual refresh | Click refresh button | Charts re-fetch data, timestamp updates | |
| 11.2.8 | CSV export | Click export on API Cost / Tool Usage | CSV file downloads with correct data | |

### 11.3 User Management

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 11.3.1 | Users list | Navigate to `/admin/users` | Paginated list of all users | |
| 11.3.2 | Search user | Search by email | Matching users shown | |
| 11.3.3 | View user detail | Click on user | Shows profile, plan, credits, generations | |
| 11.3.4 | Ban user | Click ban on a user → confirm | User banned, cannot login | |
| 11.3.5 | Unban user | Click unban on banned user | User unbanned, can login again | |
| 11.3.6 | Adjust credits | Add/remove credits for a user | Balance updated, transaction created | |

### 11.4 Material & Moderation

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 11.4.1 | Materials list | Navigate to `/admin/materials` | All pre-generated materials listed | |
| 11.4.2 | Review material | Approve/reject a material | Status updated | |
| 11.4.3 | Moderation queue | Navigate to `/admin/moderation` | Flagged content shown for review | |

### 11.5 System Health

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 11.5.1 | System health | Navigate to `/admin/system` | Shows DB, Redis, AI service status | |
| 11.5.2 | AI services status | Check AI provider statuses | PiAPI, Pollo, A2E, Gemini status shown | |
| 11.5.3 | API cost breakdown | Check cost stats | Per-provider cost shown (weekly/monthly) | |
| 11.5.4 | Revenue stats | Navigate to `/admin/revenue` | Revenue analytics with breakdown | |

---

## 12. Internationalization (i18n) (P2) — Role: Guest

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 12.1 | English (default) | Set language to EN | All text in English | |
| 12.2 | Traditional Chinese | Switch to 繁體中文 | All text in Traditional Chinese | |
| 12.3 | Japanese | Switch to 日本語 | All text in Japanese | |
| 12.4 | Korean | Switch to 한국어 | All text in Korean | |
| 12.5 | Spanish | Switch to Español | All text in Spanish | |
| 12.6 | Language persistence | Switch language, reload page | Language setting preserved | |
| 12.7 | Geo-language auto-detect | First visit (no cookie) | Language auto-detected based on browser/geo | |
| 12.8 | Tool names translated | Check tool names in each language | All tool names properly translated | |
| 12.9 | Error messages translated | Trigger an error in non-EN language | Error message in selected language | |

---

## 13. Responsive Design (P2) — Role: Guest

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 13.1 | Desktop (1920px) | Test on full desktop | Full layout, sidebar if applicable | |
| 13.2 | Laptop (1280px) | Resize to laptop width | Layout adjusts, no horizontal scroll | |
| 13.3 | Tablet (768px) | Resize to tablet | Layout stacks, touch-friendly buttons | |
| 13.4 | Mobile (375px) | Resize to mobile | Single-column layout, hamburger menu | |
| 13.5 | Tool pages mobile | Open any tool page on mobile | Upload zone, presets all accessible | |
| 13.6 | Admin on tablet | Open admin dashboard on tablet | Charts and tables readable | |

---

## 14. Topic Pages (P2) — Role: Guest

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 14.1 | Pattern topic hub | Navigate to `/topics/pattern` | Pattern-related tools and presets displayed | |
| 14.2 | Product topic hub | Navigate to `/topics/product` | Product tools (BG removal, scene, enhance) shown | |
| 14.3 | Video topic hub | Navigate to `/topics/video` | Video tools (short video, I2V, transform) shown | |
| 14.4 | Topic navigation | Click through topic presets | Each links to correct tool page | |

---

## 15. Prompt Templates (P2) — Role: Guest / Subscriber

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 15.1 | View prompt groups | Access prompt template section | Groups listed (by tool type) | |
| 15.2 | View sub-topics | Click a group | Sub-topics expand | |
| 15.3 | Demo use template | As guest, use a template | Watermarked result from cached template | |
| 15.4 | Subscriber generate | As subscriber, use template with custom params | Real-time generation, credits deducted | |

---

## 16. Effects & Enhancement (P2) — Role: Subscriber

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 16.1 | List styles | View available style effects | All styles shown (anime, ghibli, cartoon, oil painting, watercolor, etc.) | |
| 16.2 | Apply style transfer | Upload image → select style → apply | Styled image returned (8 credits) | |
| 16.3 | HD enhance | Upload image → HD enhance | High-resolution version returned (12 credits) | |
| 16.4 | Video enhance | Upload video → enhance | Enhanced video returned (15 credits) | |

---

## 17. Session & Quota (P3) — Role: Guest / User

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 17.1 | Session heartbeat | Open site, check network for heartbeat | Periodic `POST /session/heartbeat` calls | |
| 17.2 | Online count | Check online users count | Reasonable number displayed | |
| 17.3 | Daily quota (demo) | As guest, check remaining quota | Shows remaining / total / reset time | |
| 17.4 | Quota exhausted | Use all daily quota | Message: quota exhausted, shows reset time | |

---

## 18. Error Handling & Edge Cases (P1)

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 18.1 | 404 page | Navigate to non-existent route (e.g., `/nonexistent`) | Custom 404 page or redirect | |
| 18.2 | API timeout | (Dev) Kill backend while using tool | Graceful error message, retry option | |
| 18.3 | Network disconnect | Disable network while generating | Error message with retry | |
| 18.4 | Concurrent generations | Start 2+ generations simultaneously | All handled properly, credits deducted correctly | |
| 18.5 | Session expiry | Let token expire, then act | Auto-refresh or redirect to login | |
| 18.6 | Content moderation | Upload inappropriate content | Blocked by Gemini moderation, error message | |
| 18.7 | Provider failover | (Dev) Disable primary provider | Backup provider used, result still returned | |
| 18.8 | Credit refund on failure | Generation fails after credit deduction | Credits refunded automatically | |

---

## 19. Security (P1)

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 19.1 | Protected routes | Navigate to `/dashboard` without login | Redirected to login | |
| 19.2 | Admin guard | Navigate to `/admin` as regular user | Redirected or 403 | |
| 19.3 | JWT in storage | After login, check localStorage/cookie | JWT stored securely | |
| 19.4 | XSS in inputs | Enter `<script>alert(1)</script>` in any text field | Input sanitized, no script execution | |
| 19.5 | File upload validation | Upload non-image file renamed to .jpg | Server rejects with error | |
| 19.6 | Rate limiting | Send 50+ rapid requests | Rate limit response (429) after threshold | |
| 19.7 | CORS check | Make API request from different origin | CORS headers properly configured | |
| 19.8 | Download authorization | Try downloading another user's generation | 403 Forbidden | |

---

## 20. Performance (P3)

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 20.1 | Landing page load | Measure load time on first visit | < 3 seconds to interactive | |
| 20.2 | Demo preset load | Load tool page with presets | Presets load within 1 second | |
| 20.3 | Image upload | Upload 10MB image | Upload completes in < 5 seconds (local) | |
| 20.4 | Chart rendering | Load admin dashboard with charts | Charts render within 2 seconds | |
| 20.5 | Language switch | Switch language | Text updates instantly (no page reload) | |

---

## 21. Workflow System (P3) — Role: Subscriber

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 21.1 | View workflow topics | Access workflow section | Topic list with categories shown | |
| 21.2 | Topic detail | Click on a workflow topic | Shows steps, tools involved, expected output | |
| 21.3 | Generate from workflow | Select topic → generate | Multi-step generation executes | |
| 21.4 | Batch by category | Generate all topics in a category | Multiple generations queued and completed | |
| 21.5 | Preview topic | Preview before generating | Shows expected output without using credits | |

---

## Test Execution Tracking

| Section | Total Tests | Passed | Failed | Blocked | Notes |
|---------|------------|--------|--------|---------|-------|
| 1. Landing Page | 12 | | | | |
| 2. Authentication | 19 | | | | |
| 3. Demo/Preset Tools | 30 | | | | |
| 4. Subscriber Tools | 34 | | | | |
| 5. Subscription & Billing | 14 | | | | |
| 6. Credits System | 8 | | | | |
| 7. Promotions & Referrals | 10 | | | | |
| 8. User Dashboard | 8 | | | | |
| 9. Social Media | 13 | | | | |
| 10. E-Invoice | 7 | | | | |
| 11. Admin Dashboard | 18 | | | | |
| 12. Internationalization | 9 | | | | |
| 13. Responsive Design | 6 | | | | |
| 14. Topic Pages | 4 | | | | |
| 15. Prompt Templates | 4 | | | | |
| 16. Effects & Enhancement | 4 | | | | |
| 17. Session & Quota | 4 | | | | |
| 18. Error Handling | 8 | | | | |
| 19. Security | 8 | | | | |
| 20. Performance | 5 | | | | |
| 21. Workflow | 5 | | | | |
| **TOTAL** | **230** | | | | |

---

*Document Version: 1.0*
*Last Updated: March 18, 2026*
*Platform: VidGo Gen AI*
