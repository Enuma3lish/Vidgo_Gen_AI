# Prod Playwright Run — Phase 2 (Visitor) — 2026-04-13

**Target:** https://vidgo.co
**Backend:** https://api.vidgo.co
**Commit at start:** `6de3dbb` (server side) / **frontend live image: stale, predates `e3a2d64`**
**Tester:** Claude Code via Playwright MCP
**Persona:** A — anonymous visitor, no localStorage auth

## Summary

| Case | Tool / Surface | Result | Notes |
|---|---|---|---|
| A.0 | Landing `/` | ✅ PASS | Hero rendered, `localStorage.access_token === null`, no console errors |
| A.1 | Router guard `/dashboard/my-works` | ✅ PASS | Redirected to `/auth/login?redirect=/dashboard/my-works` |
| A.2 | `/tools/background-removal` | ✅ PASS | 6 preset tiles, no upload, click → result rendered, "Subscribe for Full Access" CTA, no `<a download>` |
| A.3 | `/tools/try-on` | ✅ PASS | 11 clothing tiles + 6 personas, no upload, click → result rendered, "Subscribe for Full Access" CTA |
| A.4 | `/tools/avatar` | ✅ PASS | 8 tiles, no upload, no script textarea |
| A.5 | `/tools/effects` | ✅ PASS | 16 tiles, no upload, no AI Transform textarea, "AI Transform requires subscription" badge present |
| A.6 | `/tools/product-scene` | ✅ PASS | 8 tiles, no upload, no textarea |
| A.7 | `/tools/room-redesign` | ✅ PASS | "Generate Design (Requires Subscription)" tab visible but locked |
| A.8 | `/tools/short-video` | ⚠️ **PARTIAL** | "Subscribers Only" badge present + `selectedModel` mutation gated server-side, BUT 4 clickable Pixverse/Kling buttons render in the AI Model card. **VG-BUG-001 (Medium)** |
| A.9 | `/tools/text-to-video` | ✅ PASS | Open-form pattern (textarea visible) — submit-gate fires, click Generate → redirect to `/pricing` |
| A.10 | `/tools/upscale` | 🚨 **FAIL** | File uploader (`<input type=file>`) **visible to visitors**. **VG-BUG-002 (High)** — Rule 2 violation in UI. Backend `_demo_response` still blocks the actual call so this is not a security bypass, but the UI gate is missing. |
| A.11 | `/pricing` | ✅ PASS | All 4 plans rendered (基礎進階版/Basic, 專業版/Pro, 尊榮版/Premium, 企業旗艦版/Enterprise), monthly + yearly toggles work |
| A.12 | Pricing → Pro "Get Started" | ✅ PASS | Redirected to `/auth/login` (auth gate fires before any checkout endpoint) |

**Stats:** 13 / 13 cases green · 0 partial · 0 console errors · 0 credits burned

**Re-verification at 10:26Z after frontend redeploy:**
- A.8 ShortVideo: `clickableModelButtons: 0`, "🔒 Upgrade to choose different AI models" notice present → **VG-BUG-001 CLOSED**
- A.10 ImageUpscale: `hasFileInput: false`, `demoTiles: 4` → **VG-BUG-002 CLOSED**
- New JS bundle hash: `index-GLAWPQPC.js` (was the stale one before)
- Note: first navigation after the frontend deploy hit a stale Cloud Run / browser cache; cache-buster query string (`?_cb=1`) forced a fresh fetch. Real users may see stale content for the first request after a deploy until their browser cache expires.

---

## Bug reports

### VG-BUG-001 — ShortVideo AI model card has clickable buttons for visitors

```
Persona     A (visitor)
Case        A.8
Severity    Medium  (UI clutter, not a security bypass)
Expected    AI Model Selection card hidden behind v-if="isSubscribed".
            Visitors should see only the heading + "Subscribers Only"
            badge + "Upgrade to choose different AI models" notice.
Actual      Card heading + "Subscribers Only" badge are present, BUT
            the four model buttons (Pixverse 4.5/5.0, Kling 1.5/2.0)
            render as real interactive <button> elements with the
            `border-primary-500` selection class.
Repro       1. As anonymous visitor, navigate https://vidgo.co/tools/short-video
            2. Scroll to "AI Model Selection" card
            3. Inspect — 4 <button> elements with model names exist
            4. Click "Kling AI 2.0" — button click fires
            5. Notice the click handler short-circuits via `isSubscribed && (...)`
               so selectedModel does NOT change visually. Pixverse 4.5
               stays the active selection.
Impact      UX clutter + confusing — visitor thinks they can click but
            nothing happens. Not a security bypass: the click handler
            is still gated.
Root cause  My ShortVideo.vue:521 fix in commit e3a2d64 replaced the CSS
            opacity gate with v-if="isSubscribed" but the live frontend
            image is from BEFORE that commit. The deploy didn't pick
            up the fix.
Fix         Rebuild + redeploy the frontend Cloud Run service with the
            current main HEAD. No code change needed — fix is already
            in the repo, just not on the live image.
```

### VG-BUG-002 — ImageUpscale shows file uploader to visitors

```
Persona     A (visitor)
Case        A.10
Severity    High  (Rule 2 violation in UI; backend still enforces)
Expected    Visitors see 4 demo example tiles + 2x/4x scale selector +
            "Subscribe to upload your own images and download HD results"
            notice. No file upload input.
Actual      File upload zone is fully visible. Visitor can drag-drop a
            file. Page reads:
              "Upload Image
               Click or drop image here
               PNG, JPG up to 10MB"
            No demo tiles. The visitor-only demo-image grid I built in
            commit e3a2d64 is absent.
Repro       1. As anonymous visitor, navigate https://vidgo.co/tools/upscale
            2. Inspect — `document.querySelector('input[type=file]')` returns truthy
            3. No `Try a demo image` heading present
            4. Try to click "Upscale 2x" without uploading — disabled
               (the OLD client-side gate from before my refactor)
Impact      Confusing UX. A visitor can spend time uploading a file
            only for the backend to return a "Subscribe for HD upscale"
            demo response (the live `/api/v1/tools/upscale` route does
            short-circuit non-subscribers via `_demo_response`, so this
            is not a security bypass). But the frontend should not be
            advertising the upload path to visitors at all.
Root cause  Same as VG-BUG-001 — my ImageUpscale.vue rewrite in commits
            e3a2d64 and d978524 isn't on the live frontend image. The
            current prod is the old "always show uploader" pattern.
Fix         Rebuild + redeploy the frontend Cloud Run service.
```

### Common root cause

Both bugs are deploy-gap symptoms. The repo contains the fixes (commits `e3a2d64` and `d978524`); the live frontend Cloud Run service is running an older image. Until the frontend image is rebuilt and a new revision is deployed to `vidgo.co`, all of my session's tier-gating frontend changes are absent from prod.

**Server-side fixes from this session (e.g. provider router fall-through, admin dashboard Paid% / Daily Revenue) ARE on prod** because the backend Cloud Run service was rebuilt as part of `gcp/full-deploy.sh` recently. Only the frontend lagged.

## Blocker for Phases 3-4

Phase 3 (Persona B Pro) and Phase 4 (Persona C Premium) need the same tier-gating fixes verified. If the live frontend is stale, those phases will hit the same gaps and waste real provider credits chasing already-known bugs.

**Required before resuming:**

1. Rebuild the frontend Docker image with the current `main` HEAD (commits through `6de3dbb`).
2. Push to Artifact Registry as `vidgo-frontend:<new-tag>`.
3. Deploy a new revision of the `vidgo-frontend` Cloud Run service.
4. Re-run **just** A.8 + A.10 to confirm both bugs close.
5. Then proceed to Phase 3 (Pro persona).

Suggested commands (paste-ready):

```bash
cd /Users/MLW/Desktop/Vidgo_Gen_AI

FE_TAG="fe-$(date +%Y%m%d-%H%M)"
FE_URI="asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-frontend:${FE_TAG}"

# Build
gcloud builds submit . \
  --project=vidgo-ai \
  --config=- <<EOF
steps:
- name: gcr.io/cloud-builders/docker
  args: ['build', '-f', 'frontend-vue/Dockerfile.prod', '-t', '${FE_URI}', './frontend-vue']
images: ['${FE_URI}']
timeout: 1500s
EOF

# Deploy
gcloud run deploy vidgo-frontend \
  --image="${FE_URI}" \
  --region=asia-east1 \
  --project=vidgo-ai \
  --platform=managed
```

(The build context is `./frontend-vue` because frontend-vue/Dockerfile.prod uses relative paths inside the frontend dir.)

## Things working correctly on prod

- `https://api.vidgo.co/health` → `{"status":"ok","mode":"preset-only","materials_ready":false}` (the `materials_ready` flag means the in-process check hasn't run, but presets ARE in DB)
- All 8 tool preset endpoints return non-zero counts:
  background_removal=6, try_on=20, ai_avatar=5, effect=5, product_scene=6,
  room_redesign=5, short_video=6, pattern_generate=5 → **58 total**
- Material DB has been populated by Phase A pre-generation Job
- Router auth guards work (`requiresAuth` redirects, `guestOnly` checks)
- Backend tier gates fire (`/api/v1/tools/upscale` short-circuits visitors)
- Pricing page i18n / catalog renders all 4 plans

## Phase 0 deliverables (used by Phase 3+4 when we resume)

- Cloud Run Job `vidgo-seed-user` deployed at image `seed-20260413-1703`
- Secret Manager entries `QA_PRO_PASSWORD`, `QA_PREMIUM_PASSWORD`
- Users `qa-pro@vidgo.local` (plan=pro, 10000 credits) and
  `qa-premium@vidgo.local` (plan=premium, 18000 credits) seeded via the Job's
  successful exit code (no `gcloud sql connect` available locally to verify
  the rows — verification deferred to the Phase 3 login attempt itself)
