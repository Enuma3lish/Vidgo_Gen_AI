# VidGo.co Final QA Test Plan

**Date**: 2026-05-12
**Source**: `bug_list/VidGo.co_網站測試驗收清單_(UAT_Checklist)0511.pdf`
**Scope**: Admin-account full-feature validation across every tool. Payment / subscription is **explicitly out of scope** per request — we only confirm that pricing **pages exist with no bugs**. New scope additions: real API generation, download, dashboard gallery presence, and Web Share API social distribution.

**Environment**
- Production: `https://vidgo.co` (frontend) + `https://api.vidgo.co` (backend)
- Admin test account: `vidgo168@gmail.com` (already provisioned, has unlimited credits)
- Browsers: Chrome (desktop) + Safari iOS (mobile share API)

**Pass criteria**: every item below returns ✅. Any ❌ blocks release; any ⚠ becomes a follow-up issue but does not block.

---

## Section 0 · Environment Smoke Test

| ID | Step | Expected | Pass/Fail | Notes |
|---|---|---|---|---|
| ENV-01 | `curl https://api.vidgo.co/health` | HTTP 200, JSON `{"status":"ok",...}` | | |
| ENV-02 | `curl https://api.vidgo.co/api/v1/admin/branding/public` | HTTP 200, JSON with `settings.{}` schema | | Confirms migration `z1a2b3c4d5e6` ran. |
| ENV-03 | `curl -I https://vidgo.co/` | HTTP 200, `content-type: text/html` | | |
| ENV-04 | Open https://vidgo.co in Chrome incognito | Landing page renders without console errors | | |
| ENV-05 | DevTools → Network panel, refresh | Vite bundle hash differs from previous deploy | | Cache-busting working. |

---

## Section 1 · Account & Permissions

> Same scope as UA-01 through UA-04, plus admin-redirect check.

| ID | Test | Steps | Expected | Pass/Fail | Notes |
|---|---|---|---|---|---|
| UA-01 | New user registration | 1. Homepage → "Sign Up". 2. Use throw-away email `qa+$(date)@vidgo.co`. 3. Submit. 4. Click verification link in email. | Account created; 40 free credits granted; redirect to `/dashboard/my-works`. | | Use a real mailbox for the verification click. |
| UA-02 | Login | 1. Logout. 2. Login with admin `vidgo168@gmail.com`. | Lands on `/admin/dashboard` (admin auto-redirect). | | |
| UA-03 | Password reset | 1. Logout. 2. Click "Forgot password". 3. Enter test email. 4. Open reset link from email. 5. Set new password. 6. Login. | Reset email arrives within 60s, link valid, login succeeds. | | |
| UA-04 | Logout | 1. Click avatar → Logout. | Returned to landing page; `/dashboard/*` redirects to `/auth/login`. | | |
| UA-05 | Admin nav | 1. Login as admin. 2. Click each quick-link: Users, Materials, Revenue, Costs, Plans, Branding, System. | All 7 admin pages render with no console errors and no 5xx. | | New pages: Costs, Plans, Branding. |

---

## Section 2 · Landing & Topic Pages

Confirm structural existence; do not test generation here.

| ID | Page | What to verify | Pass/Fail |
|---|---|---|---|
| TOPIC-01 | `/` Landing | Hero, tool grid, seasonal showcase, pricing CTA all render. | |
| TOPIC-02 | `/topics/pattern` | Pattern showcase + prompt examples visible. | |
| TOPIC-03 | `/topics/product` | Product Scene showcase + product image grid visible. | |
| TOPIC-04 | `/topics/video` | Video / motion examples visible. | |
| TOPIC-05 | `/gallery` Inspiration | At least 12 sample tiles render; clicking opens detail. | |
| TOPIC-06 | `/pricing` (no checkout) | All 4 plan cards render with localized text. **Do not click subscribe.** | |
| TOPIC-07 | Static info pages | `/info/about`, `/info/contact`, `/info/terms`, `/info/privacy`, `/info/cookies`, `/info/refund`, `/info/affiliate` all render. | |

---

## Section 3 · Tool Full-Function Tests (Admin Account)

For **every tool**, the admin account must complete all six steps:

```
A. Upload user input (real file from local disk)
B. Generate (real API — verify backend logs show provider call)
C. Result visible on the SAME page (no need to leave for dashboard)
D. Download the result (file lands on disk, opens correctly)
E. Open Dashboard → My Works → result appears with a thumbnail
F. Open Share-to-Social modal → verify Web Share API + at least one platform
```

Fixtures live in `TEST/Test_material/assets/`. Admin should use those for repeatability.

### 3.1 AI Model Try-On (`/tools/try-on`)

| Step | Action | Expected |
|---|---|---|
| A | Upload `assets/try-on/garment-dress-only.png` to garment slot | Preview appears within 2 s; no console error |
| A.1 | Pick model "Female 1" from preset grid OR upload `assets/try-on/model-female-1.png` | Selection highlighted |
| A.2 | Pick scene preset (e.g. "Studio white") | Scene tile highlighted |
| B | Click "Generate" | Loading overlay appears; backend logs (`gcloud run services logs read vidgo-backend --limit=20`) show `Kling` or `PiAPI` try-on task |
| C | Wait up to 2 min | Result image appears in right panel of same page |
| D | Click "Download" | File saves as `vidgo-try_on-*.png`; opens in image viewer |
| E | Open `/dashboard/my-works`, filter "Try-On" | Generation appears with valid thumbnail |
| F | Click "Publish" → modal opens → click "System Share" (mobile) or "Facebook" (desktop) | Web Share sheet (mobile) or Facebook share page (desktop) opens with caption + URL |

### 3.2 AI Product Scene Studio (`/tools/product-scene`)

| Step | Action | Expected |
|---|---|---|
| A | Upload `assets/product-scene/product-coffee-beans-packshot.png` | Preview rendered |
| A.1 | Choose scene "Nature" or "Custom Prompt" → type `"on a marble countertop with morning light"` | Scene selected; prompt counter shows ≤300 chars |
| B | Click "Generate" | Backend logs show `Kontext I2I` call (primary) or `rembg + T2I + composite` (fallback) |
| C | Result image renders on the same page within 90 s | Product preserved; background reflects the prompt |
| D | "Download" → file `vidgo_product_scene_*.png` saved | |
| E | Dashboard → My Works filter `product_scene` | Thumbnail visible |
| F | Share modal → click "Threads" | Threads composer opens in new tab with caption + URL |

### 3.3 Smart Background Removal (`/tools/background-removal`)

| Step | Action | Expected |
|---|---|---|
| A | Upload any image with complex background (hair, fur, transparent edges) | Preview rendered |
| A.1 | Try **black** background mode | Black solid composite visible after generate |
| A.2 | Try **white** background mode | White solid composite visible |
| A.3 | Try **replace image** → upload another image (NOT URL paste) | File picker accepts upload; preview of replacement appears |
| A.4 | On a mobile device or DevTools mobile viewport, re-test the upload control | Upload works — no hidden input issue (BUG-009 regression check) |
| B | Generate | Backend logs show `PiAPI MCP` or `Vertex` background-removal task |
| C | Result image renders on the same page | Edges clean, no halo |
| D | Download — confirm correct format (PNG for transparent, JPG for solid) | |
| E | Dashboard My Works filter `background_removal` | Thumbnail visible |
| F | Share modal → "LINE" | LINE share opens with link |

### 3.4 Sketch Instant Render / Room Redesign (`/tools/room-redesign`)

| Step | Action | Expected |
|---|---|---|
| A | Upload `assets/room-redesign/room-bedroom-2d-sketch.png` | Preview visible |
| A.1 | Pick room type "Bedroom", style "Scandinavian" | Selections highlighted |
| B | Click "Generate" on the Redesign tab | API returns 200 (BUG-011 regression: no 404 on `/api/v1/interior/redesign`); backend logs show Vertex AI / PiAPI call |
| C | Realistic interior render appears on same page within 2 min | Aspect ratio preserved |
| D | Download GLB or JPG depending on tab | |
| E | Dashboard My Works filter `room_redesign` | Thumbnail visible |
| F | Share modal → "Facebook" | Facebook share opens |
| EXTRA | Floor-plan → 3D tab: upload `assets/room-redesign/room-floor-plan-2d.png` → enable "Floor Plan → 3D mode" → Generate | GLB renders in Three.js viewer; "Download GLB Model" works |

### 3.5 Product Dynamic Video / Short Video (`/tools/short-video`)

| Step | Action | Expected |
|---|---|---|
| A | Pick a starting image (preset OR upload `assets/short-video/short-video-storyboard-product.png`) | Preview visible |
| A.1 | Pick motion type (Auto / Zoom-in / Pan-left) and Pixverse 4.5 model | Selections highlighted |
| B | Click "Generate" | Backend logs show Pollo MCP call; loading overlay shows time estimate |
| C | Video plays inline on right panel within 5 min | No leaked metadata in top-left corner (BUG-002 regression) |
| D | Click "Download" → `.mp4` saves | |
| E | Dashboard My Works filter `short_video` | **Video thumbnail uses `<video poster>` and shows the first frame** (BUG-001 / BUG-016 regression) |
| F | Share modal → "TikTok" (copy_first mode) | Caption copied + image auto-downloaded + TikTok upload page opens |

### 3.6 AI Digital Human / Avatar (`/tools/avatar`)

| Step | Action | Expected |
|---|---|---|
| A | Choose female-1 avatar from grid; or upload `assets/avatar/avatar-female-headshot.png` | Avatar tile highlighted |
| A.1 | **Type a custom script** in the textarea (BUG-003 regression — verify free-text editing works) | Character counter updates; max 500 chars enforced |
| A.2 | Choose language: zh-TW | Voice auto-mapped |
| B | Click "Generate" | Backend logs show Kling Avatar task via PiAPI |
| C | **Result video appears on the same page** (BUG-004 regression — should NOT require navigating to dashboard); scroll-into-view triggers on mobile | Video element renders inline |
| C.1 | Play video — **no unexpected text overlay** (BUG-005 regression: negative-prompt should suppress captions/subtitles) | Plain talking-head |
| D | Download `.mp4` | |
| E | Dashboard My Works filter `ai_avatar` | Thumbnail with play badge |
| F | Share modal → "Threads" | Threads opens with caption |

### 3.7 Commercial HD Upscale (`/tools/image-upscale`)

| Step | Action | Expected |
|---|---|---|
| A | Upload a low-res image (≤512 px wide) | Preview visible |
| A.1 | Choose 2× or 4× | |
| B | Generate | Backend logs show PiAPI upscale task |
| C | Higher-res result on same page within 60 s | |
| D | Download — verify dimensions match scale factor | |
| E | Dashboard My Works filter `effect` (upscale is part of effects) | Thumbnail visible |
| F | Share modal → "WhatsApp" | WhatsApp share opens |

### 3.8 Image Translator (`/tools/image-translator`)

| Step | Action | Expected |
|---|---|---|
| A | Pick demo image "Sale card (EN → ZH)" | Preview visible |
| A.1 | Set target language: Traditional Chinese | |
| A.2 | Set tone: "Taiwan e-commerce" | |
| B | Click "Translate Image" (BUG-012 regression: must actually run) | Backend logs show `/api/v1/tools/image-translate` → I2I provider call |
| C | Translated image renders on the same page within 90 s | English text replaced by Chinese; layout preserved |
| D | Download — verify file has translated text | |
| E | Dashboard My Works filter `effect` | Thumbnail visible |
| F | Share modal → "X" | X composer opens |

### 3.9 Pattern Generation (`/topics/pattern`)

| Step | Action | Expected |
|---|---|---|
| A | Select a prompt from dropdown (no free-text) | Selection updates preview area |
| B | Click "Generate Pattern" | Backend logs show Vertex Imagen / PiAPI T2I task |
| C | Pattern renders on same page within 60 s | Seamless tile pattern |
| D | Download `.png` | |
| E | Dashboard My Works filter `pattern_generate` | Thumbnail visible |
| F | Share modal → mobile native share (if on iOS Safari/Android Chrome) | OS share sheet appears with file attached |

### 3.10 Video Transform (`/tools/short-video?mode=transform`)

| Step | Action | Expected |
|---|---|---|
| A | Upload `assets/short-video/<any-short-mp4>` (≤20 MB) | Upload progress bar reaches 100% |
| A.1 | Pick a transform-style preset | |
| B | Click "Start Transform" | Backend logs show video-style-transfer task |
| C | Transformed video plays inline within 5 min | |
| D | Download `.mp4` | |
| E | Dashboard My Works | Generation row exists |
| F | Share modal → Web Share API on mobile | OS share sheet with video file |

### 3.11 Video Dubbing (`/tools/video-dubbing`)

| Step | Action | Expected |
|---|---|---|
| A | Pick a sample video OR upload your own | Preview visible |
| A.1 | Source language: Auto detect; target: Japanese | |
| A.2 | Mode: "Translate" with a sample transcript | |
| B | Click "Generate Dubbed Video" | Backend logs show dubbing task |
| C | Dubbed video plays inline | |
| D | Download | |
| E | Dashboard My Works | Row exists |
| F | Share modal → "LINE" | |

---

## Section 4 · Dashboard / My Works Gallery

| ID | Test | Expected | Pass/Fail |
|---|---|---|---|
| GAL-01 | Open `/dashboard/my-works` | All generations from Section 3 appear, sorted newest first | |
| GAL-02 | Filter chips (All / try_on / product_scene / short_video / room_redesign / ai_avatar / pattern_generate / effect) | Filter narrows the grid correctly | |
| GAL-03 | Video thumbnails | Each video tile renders the first frame via `<video poster>` (not a broken `<img>`) | |
| GAL-04 | Image thumbnails | Each image tile shows the result_image_url | |
| GAL-05 | Click a tile → detail modal | Modal opens with full preview + Download + Share buttons | |
| GAL-06 | Expiry badge | Items older than 12 days show "expires in N days"; items past 14 days show "expired record" placeholder | |
| GAL-07 | Download from modal | Downloads same file as from the tool's result panel | |
| GAL-08 | Delete a test generation | Confirmation prompt → after confirm, item disappears from grid | |

---

## Section 5 · Web Share API Social Sharing

Per spec: mobile `navigator.share()`, share caption + image file, support Instagram / Facebook / TikTok / LINE / Threads, fallbacks (copy caption + auto download + open social app/web), **no** official-API integration, **no** OAuth.

### 5.1 Desktop (Chrome)

| ID | Action | Expected | Pass/Fail |
|---|---|---|---|
| WS-D-01 | Open share modal on any generated image | Modal shows: link, caption editor, "System Share" button (or "Copy for Any App" if `navigator.share` unsupported), per-platform buttons | |
| WS-D-02 | Click "Copy Link" | Link copied; ✓ toast appears | |
| WS-D-03 | Click "Copy Caption" | Caption copied; toast appears | |
| WS-D-04 | Click "Facebook" | New tab opens at `https://www.facebook.com/sharer/sharer.php?u=...&quote=...` with link + caption populated | |
| WS-D-05 | Click "LINE" | New tab opens at `https://social-plugins.line.me/lineit/share?...` with link | |
| WS-D-06 | Click "Threads" | New tab opens at `https://www.threads.net/intent/post?text=...` with caption + URL | |
| WS-D-07 | Click "Instagram" (copy-first) | (a) Caption copied (b) Image auto-downloaded as `vidgo-<tool>-<id>.{png/mp4}` (c) Instagram opens in new tab | |
| WS-D-08 | Click "TikTok" (copy-first, video only) | Same three-step fallback for video; for image-only generations the button is disabled with reason text | |
| WS-D-09 | Click big "Copy for Any App" (when `navigator.share` not present) | Caption text copied + media auto-downloaded; toast confirms | |

### 5.2 Mobile (iOS Safari / Android Chrome)

| ID | Action | Expected | Pass/Fail |
|---|---|---|---|
| WS-M-01 | Open share modal on a generated **image** | "System Share with image" button shown (because `navigator.canShare({files:[file]})` is true) | |
| WS-M-02 | Click "System Share with image" | OS share sheet opens with the image attached + caption as text + page URL | |
| WS-M-03 | From the sheet, choose Instagram (Stories) | Instagram opens with the image; user posts. (We do not control the in-app flow.) | |
| WS-M-04 | From the sheet, choose Messages / LINE | App opens with caption text + URL + image attachment | |
| WS-M-05 | Open share modal on a generated **video** (`short_video` or `ai_avatar`) | "System Share with image" button shown (the helper code re-uses video file path) | |
| WS-M-06 | Click "System Share with image" with video | OS sheet attaches the `.mp4` and offers apps that accept video (Messages, LINE, etc.) | |
| WS-M-07 | Web Share API rejected (older device) | Falls through to fallback: caption copied + file auto-downloaded; toast says "Caption copied and file downloaded — paste into your app" | |

### 5.3 Failure-mode coverage

| ID | Scenario | Expected | Pass/Fail |
|---|---|---|---|
| WS-F-01 | Media URL returns CORS error on direct fetch | Backend proxy `/api/v1/share/share-media?url=...` is hit; share still works | |
| WS-F-02 | Both fetch routes fail | Toast surfaces "Could not prepare media — copy the link instead"; copy-link button still works | |
| WS-F-03 | Pop-up blocker on (Chrome → block all pop-ups) | Toast says "Pop-up blocked — please allow pop-ups for vidgo.co" | |
| WS-F-04 | User cancels iOS share sheet | No error toast (AbortError swallowed silently) | |
| WS-F-05 | Caption > 280 chars | No backend rejection (we are not posting to X via API) but X composer truncates at 280 — verify the visible warning under the textarea | |

### 5.4 Locale coverage of share modal

Switch language top-right, repeat smoke-test in each:

| ID | Locale | Expected | Pass/Fail |
|---|---|---|---|
| WS-L-01 | zh-TW | All modal strings in Traditional Chinese | |
| WS-L-02 | en | English | |
| WS-L-03 | ja | Japanese | |
| WS-L-04 | ko | Korean | |
| WS-L-05 | es | Spanish | |

---

## Section 6 · UI / UX / Compatibility

| ID | Test | Expected | Pass/Fail |
|---|---|---|---|
| UX-01 | Mobile responsive (Chrome DevTools iPhone 14 emulation) | All tool pages render without overflow; buttons reachable with thumb | |
| UX-02 | Multi-language switch | Top-right language picker → choose zh-TW / en / ja / ko / es. Operation panels in EVERY tool reflect the locale (BUG-017 regression — no English fallback in ja/ko/es) | |
| UX-03 | Bad file format upload | Upload a `.pdf` to any image tool | Friendly inline error, no crash | |
| UX-04 | Cold-load speed | DevTools throttle "Fast 3G", clear cache, load `/` | First contentful paint < 3 s | |
| UX-05 | Console error scan | Open DevTools → Console. Navigate to every page in Section 1, 2, 3. | No red errors (yellow warnings OK) | |
| UX-06 | Network 4xx/5xx scan | DevTools → Network. During the Section 3 tool flow, log every non-2xx | Only the deliberate 401s (admin endpoints when not logged in) appear; no 5xx | |

---

## Section 7 · Admin-Only New Features

Verify the admin pages added in commit `bdce07c` (Plans / Branding / Costs).

| ID | Page | Action | Expected | Pass/Fail |
|---|---|---|---|---|
| ADM-01 | `/admin/plans` | List loads with all subscription plans | Plans shown in `display_order` then `price_monthly` ascending; each row shows price, credits, active/inactive | |
| ADM-02 | `/admin/plans` | Click "Edit" on Pro plan → change `features_text_zh` → Save | PATCH `/admin/plans/{id}` returns 200; list refreshes with new copy | |
| ADM-03 | `/admin/plans` | Click "New Plan" → fill min fields → Save | New row appears | |
| ADM-04 | `/admin/plans` | Click "Deactivate" on a test plan | Soft-delete (is_active → false); row stays but greyed | |
| ADM-05 | `/admin/branding` | Upload a logo image | URL persists to `site_settings.logo_url`; preview updates | |
| ADM-06 | `/admin/branding` | Edit pricing-page intro `pricing_intro_body_zh` → Save | PATCH `/admin/branding` returns 200; public endpoint `/admin/branding/public` shows the new body | |
| ADM-07 | `/admin/costs` | Page loads | Top cards show grand total, GCP, AI providers; provider bucket cards (PiAPI / Pollo / A2E / Other) populated with current-month data | |
| ADM-08 | `/admin/costs` | Refresh button | New API call; numbers update | |

---

## Section 8 · Pricing Page (existence only, NO checkout)

> Payment / subscription / unsubscribe is explicitly out of scope. Verify the page renders and the admin can READ the data, but do not click "Subscribe", "Pay", "Cancel".

| ID | Test | Expected | Pass/Fail |
|---|---|---|---|
| PAY-EXISTS-01 | Open `/pricing` | 4 plan cards render with prices, credits, feature lists | |
| PAY-EXISTS-02 | Toggle Monthly ↔ Yearly | Prices update (monthly amount displayed when on yearly, with annual total below) | |
| PAY-EXISTS-03 | Each card has a "Subscribe" button | Button is visible but **not** clicked in this test | |
| PAY-EXISTS-04 | Pricing intro copy from `site_settings.pricing_intro_body_*` | If admin set intro, it appears above the grid | |
| PAY-EXISTS-05 | Switch language → zh-TW / ja / ko / es | Plan names, credits text, "Subscribe" button text are localized | |

---

## Section 9 · Cross-cutting Backend Reliability

| ID | Test | Expected | Pass/Fail |
|---|---|---|---|
| REL-01 | After every generation in Section 3, check `gcloud run services logs read vidgo-backend --limit=50` | No `ERROR` lines for the just-completed task; `_notify_admin_of_tool_failure` not triggered | |
| REL-02 | Generate the same tool twice rapidly | Second call queues correctly; no double-charge of credits | |
| REL-03 | Insufficient credits scenario (admin temporarily downgrades a test sub-user to free) | Tool returns friendly "Insufficient credits" toast; credits screen unchanged | |
| REL-04 | Generation timeout (kill backend mid-flight via Cloud Run revision rollback) | Frontend shows timeout error; credit refund triggered (`_refund_credits` log) | |

---

## Sign-off

| Field | Value |
|---|---|
| Tester | |
| Date | |
| Overall result | ☐ Pass / ☐ Conditional / ☐ Fail |
| Blockers found | |
| Follow-up tickets | |

---

## Appendix · Useful Commands

```bash
# Tail backend logs while testing
gcloud run services logs read vidgo-backend \
  --project=vidgo-ai --region=asia-east1 --limit=50 --format=json \
  | jq -r '.[] | "\(.timestamp) [\(.severity)] \(.textPayload // .jsonPayload.message)"'

# Re-run alembic migration (if needed)
gcloud run jobs execute alembic-migrate --project=vidgo-ai --region=asia-east1 --wait

# Smoke-test admin endpoints (use bearer token from frontend localStorage)
TOKEN=...; curl -H "Authorization: Bearer $TOKEN" https://api.vidgo.co/api/v1/admin/plans
```
