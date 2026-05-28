# Production Browser Smoke Test — 2026-05-25

After the backend (revision `vidgo-backend-00285-792`) and frontend (revision
`vidgo-frontend-00240-85x`) deploys today, walk this checklist as the admin
account in an incognito window. **I cannot use a browser, so each visual /
interactive item below is on you.** Each step lists what to look for and what
should NOT happen.

Test URL: **https://vidgo-frontend-r2laip67ma-de.a.run.app**
Admin login: `vidgo168@gmail.com` (skip; rotate after testing — credentials
were exposed in a chat transcript)

Skip all PayPal / ECPay checkout flows per your instructions.

---

## 1. Theme & visual cohesion (the brand refresh)

| # | Step | Expect | Don't expect |
|---|---|---|---|
| 1.1 | Hard-refresh `/` (Cmd+Shift+R) | New `index-*.js` and `index-*.css` hashes load (network tab) | Cached stale bundle |
| 1.2 | Look at the page chrome | Dark navy background, no warm amber accents in the main UI | Yellow/amber buttons everywhere |
| 1.3 | Click around hero CTAs | Blue (#1677ff) and violet (#7c3aed) accents on primary actions | Amber primary buttons |

## 2. Landing page — new Interior Design featured section

| # | Step | Expect | Don't expect |
|---|---|---|---|
| 2.1 | Scroll past the hero + trust-brands strip | A NEW section: "Featured · Interior Design" chip with the title "Redesign Any Room From a Single Photo" (EN) or "重新設計整個房間" (zh-TW) | Section missing |
| 2.2 | Verify the two preview panes on the right | Two stacked image panes labelled "Before" and "AI Redesign" with a violet/blue label on the after pane | Both panes blank — the images at `/static/landing/room-before.jpg` and `room-after.jpg` aren't uploaded yet. If broken, the section still renders without the images (graceful fallback via the `@error` handler). You may want to upload these |
| 2.3 | Click "Try Room Redesign Free" | Navigates to `/tools/room-redesign` | Hangs / 404 |
| 2.4 | Click "Browse Design Templates" | Navigates to `/tools/interior-templates` | 404 |
| 2.5 | Switch i18n to zh-TW | Section copy switches to Chinese | English text leaks through |

## 3. Pricing page

| # | Step | Expect | Don't expect |
|---|---|---|---|
| 3.1 | Open `/pricing` | Page renders, no console errors | Blank page / hydration errors |
| 3.2 | Look at credit packs section | Three packs: **Light 250 / NT$299**, **Standard 416 / NT$499**, **Heavy 833 / NT$999** | Old values (3,000 / 5,500 / 12,000) — those would mean the bundled fallback is leaking |
| 3.3 | Open browser DevTools → Network, refresh, click on `/api/v1/promotions/packages` response | JSON with `credits: 250, 416, 833` and `price: 299, 499, 999` | Any other numbers → backend served wrong data |
| 3.4 | Verify monthly subscriptions | basic NT$399 (450cr/mo), pro NT$999 (1,200cr/mo), premium NT$1,699 (2,200cr/mo) | Old monthly pricing |
| 3.5 | Click a credit pack purchase button (then back-button out) | Redirects to PayPal/ECPay — back-button returns to site | Frontend crash before redirect |

## 4. Tool hub (formerly Product Scene, now `/tools/product-scene`)

| # | Step | Expect | Don't expect |
|---|---|---|---|
| 4.1 | Open `/tools/product-scene` | Tool hub renders | Old single-grid view |
| 4.2 | Look ABOVE the tile grid | NEW segmented filter bar: `All / Image / Video / Interior / Effects` with counts on each chip | No filter bar |
| 4.3 | Click "Interior" | Grid filters to ~2 tiles: Room Redesign + Interior Templates | More than 2 tiles |
| 4.4 | Click "Video" | Grid shows IG/TikTok, Kling, 3D, Video Generator, Video BG Remove | Image tools sneaking in |
| 4.5 | Click "Effects" | Grid shows Background (replace), Ironing, Claymation | Image-generation tools |
| 4.6 | Click a tile (e.g. Room Redesign) | Navigates and is added to "Recently Used" on next visit | Recently Used doesn't update |

## 5. Room Redesign tool (`/tools/room-redesign`)

| # | Step | Expect | Don't expect |
|---|---|---|---|
| 5.1 | Page loads, hero with mode tabs | "Redesign / Stage / Magic" tabs visible | Single mode only |
| 5.2 | Upload a room photo | Preview shows; style chips appear; "Generate" button enables | Upload fails / no preview |
| 5.3 | Pick an interior style, click Generate | Backend call to `/api/v1/tools/room-redesign` returns a result image within ~30-60s | "Tool temporarily unavailable" (would indicate provider issue) |
| 5.4 | Try Magic mode with a custom prompt ("add a coffee table") | Result reflects the prompt | Generic output |

## 6. Other flagship tools (smoke test — provide a sample image, click Generate)

For each, expect a result OR a graceful error message (NOT a console exception):

- `/tools/background-removal` — upload a product photo, expect transparent bg
- `/tools/try-on` — upload garment + model, expect dressed model
- `/tools/product-scene-classic` — upload product + pick scene
- `/tools/upscale` — upload low-res image, expect 2x output (premium plan can pick 4x)
- `/tools/short-video` — pick a tier and prompt
- `/tools/kling-video` — pick Kling tier (your premium plan unlocks Omni)
- `/tools/midjourney-imagine` — text prompt
- `/tools/ai-avatar` — upload photo + script
- `/tools/image-translator` — upload signage, pick target language

## 7. Refund-eligibility (the new code path)

| # | Step | Expect | Don't expect |
|---|---|---|---|
| 7.1 | Open `/account` or `/subscription` page | Your active premium subscription is shown | Stale "free" plan |
| 7.2 | Watch DevTools Network on page load | A request to `/api/v1/subscriptions/refund-eligibility` returns `code:"OK"` with `used`, `allowance`, `has_hq_export` fields | Endpoint 404/500 |
| 7.3 | If a "Cancel subscription with refund" button is shown | Don't click it — that would actually cancel | — |

## 8. Admin override endpoint (new — backend test only since there's no UI for it yet)

Run this from your terminal (the new `is_refundable` admin override):

```bash
TOKEN=$(curl -s -X POST https://vidgo-backend-r2laip67ma-de.a.run.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"vidgo168@gmail.com","password":"<your_admin_password>"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['tokens']['access'])")

# Block refund on a sub (replace SUB_ID with a real subscription UUID):
curl -X PATCH "https://vidgo-backend-r2laip67ma-de.a.run.app/api/v1/admin/subscriptions/SUB_ID/refund-eligibility?is_refundable=false&reason=ADMIN_BLOCK" \
  -H "Authorization: Bearer $TOKEN"

# Re-enable:
curl -X PATCH "https://vidgo-backend-r2laip67ma-de.a.run.app/api/v1/admin/subscriptions/SUB_ID/refund-eligibility?is_refundable=true&reason=admin_override" \
  -H "Authorization: Bearer $TOKEN"
```

Expected response shape: `{success: true, is_refundable: bool, previous: bool, reason: str, admin_id: str}`

## 9. Sanity / regression spot-checks

| # | Step | Expect |
|---|---|---|
| 9.1 | Open `/admin` (because you're a superuser) | Admin dashboard loads, no 500 |
| 9.2 | Open `/admin/plans` | Lists basic / pro / premium / enterprise with the new prices |
| 9.3 | Open browser console on each page | NO red errors. Yellow warnings about HMR or `materials_ready:false` are OK |

---

## If something fails

1. **Get the error**: Open DevTools → Network, find the failing request, copy as cURL.
2. **Get the server side**: `gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="vidgo-backend" AND severity>=ERROR' --limit 10 --freshness 5m`
3. **Rollback if critical**: `gcloud run services update-traffic vidgo-backend --to-revisions vidgo-backend-00284-lf9=100 --region asia-east1` (previous revision)
   And the same for `vidgo-frontend-00239-82d`.

## Credential rotation reminder

The `ADMIN_PASSWORD=Vidgo96003146` value in `backend/.env` AND `gcp/deploy.sh`
is now in this chat transcript. Same value is the production DB root password.
Recommend:

1. Generate a new strong password.
2. Change the admin user's password through the app.
3. Rotate the Cloud SQL password: `gcloud sql users set-password postgres --instance=prod-db --password=<NEW>` then update the Secret Manager entry the backend reads.
4. Remove the hardcoded value from `gcp/deploy.sh` and read it from `gcloud secrets versions access`.
