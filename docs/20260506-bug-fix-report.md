# VidGo Bug Fix Report - 2026-05-06

## Source Documents

- `docs/bugs/20260506 vidgo網站驗收清單.docx`
- `docs/bugs/vidgo程式碼全面修復清單2.docx`

This report summarizes the code fixes completed for the two bug-checklist documents. Items that depend on real third-party credentials, provider account permissions, or production payment callbacks are listed separately under "External validation still required".

## Fixed Items

### P0 Payment And Credits

| Bug / risk | How it was fixed | Main files |
| --- | --- | --- |
| International payment could direct-activate plans when Paddle was missing or misconfigured. | Normal users now fail closed when Paddle price IDs or payment provider settings are missing. Direct activation is restricted to explicit mock/admin/dev-safe flows. | `backend/app/services/subscription_service.py`, `backend/app/api/v1/subscriptions.py`, `backend/app/api/v1/payments.py` |
| Paddle checkout compatibility and fake price fallback risk. | Added `/api/v1/payments/paddle/checkout/{order_number}` compatibility and removed the fake `pri_{order_number}` fallback outside mock mode. | `backend/app/api/v1/payments.py` |
| Credit packages did not grant bonus credits after successful payment. | Payment success now grants package `bonus_credits` in addition to purchased credits and records the correct transaction metadata. | `backend/app/services/subscription_service.py` |
| Subscription refund/cancel could remove unrelated purchased or promotional credits. | Refund logic now revokes subscription credits for subscription refunds while preserving unrelated purchased and bonus credit buckets. Tool refunds restore the original bucket deducted from. | `backend/app/services/subscription_service.py`, `backend/app/services/credit_service.py`, `backend/app/api/v1/tools.py` |
| Product Scene / demo 0-credit tools could be blocked by stale min-plan metadata. | `check_model_permission()` now skips min-plan gating for 0-credit tools, so free/demo tools remain usable when cost is zero. | `backend/app/services/credit_service.py` |

### AI Tool Error Handling And Abuse Prevention

| Bug / risk | How it was fixed | Main files |
| --- | --- | --- |
| Provider `success=false` responses could expose raw upstream errors to users. | Added a shared provider-failure response helper that logs the internal error, emails admin, and returns a generic tool-unavailable message to the user. Applied it to background removal, room redesign, short video, video transform, upscale, image translation, and video dubbing. | `backend/app/api/v1/tools.py` |
| Generation endpoints needed basic abuse prevention. | Added a lightweight Redis-backed abuse-prevention service and wired user generation rate checks into credit deduction. | `backend/app/services/abuse_prevention_service.py`, `backend/app/api/v1/tools.py`, `backend/app/core/config.py` |
| Public auth endpoints needed throttling / anti-abuse hooks. | Added IP-based register/login checks and optional reCAPTCHA request fields/config. | `backend/app/services/abuse_prevention_service.py`, `backend/app/api/v1/auth.py`, `backend/app/schemas/user.py`, `backend/app/core/config.py`, `frontend-vue/src/api/auth.ts` |

### Auth, Email, And Language

| Bug / risk | How it was fixed | Main files |
| --- | --- | --- |
| Password reset email linked to a root query instead of a real frontend reset page. | Reset emails now link to `/auth/reset-password?token=...`, and the frontend route/page was added. | `backend/app/services/email_service.py`, `frontend-vue/src/views/auth/ResetPassword.vue`, `frontend-vue/src/router/index.ts` |
| Auth emails were English-only. | Verification, password reset, and welcome emails now support English and Chinese content selected from request language. | `backend/app/services/email_service.py`, `backend/app/services/email_verify.py`, `backend/app/api/v1/auth.py` |
| API requests did not consistently send the selected UI language. | Axios now sends `Accept-Language`, and the UI store has a synced language-change helper. | `frontend-vue/src/api/client.ts`, `frontend-vue/src/stores/ui.ts` |

### Dashboard, Downloads, Footer, And Mobile UX

| Bug / risk | How it was fixed | Main files |
| --- | --- | --- |
| Documented download endpoint `/api/v1/downloads/{id}` was missing. | Added the endpoint with auth, subscription, ownership, and 14-day expiry checks. Expired media returns `410 Gone`. | `backend/app/api/v1/downloads.py`, `backend/app/api/api.py` |
| My Works downloads bypassed backend checks by opening direct media URLs. | Dashboard downloads now open the backend download endpoint so retention, ownership, and subscription rules are enforced. | `frontend-vue/src/api/user.ts`, `frontend-vue/src/views/dashboard/MyWorks.vue` |
| Footer company/legal links used placeholder `#` routes. | Added real static routes and a shared static info page for company/legal/footer links. | `frontend-vue/src/components/layout/AppFooter.vue`, `frontend-vue/src/views/StaticInfoPage.vue`, `frontend-vue/src/router/index.ts` |
| Short Video subscribed image-to-video action used result-style wording. | Button text now says "Confirm Generate" / "確認生成" for subscribed generation flow. | `frontend-vue/src/views/tools/ShortVideo.vue` |
| Mobile video preview behavior needed improvement. | Uploaded video preview now uses mobile-friendly video attributes such as inline playback and metadata preload. | `frontend-vue/src/views/tools/ShortVideo.vue` |

## Earlier Fixes Already Completed In This Work Session

- Admin can assign the `$1 USD` test plan with `10000` credits.
- Admin pages no longer show the admin user's personal credits/gallery testing work.
- Upload validation blocks unsupported size, format, and dimensions and prompts the user to choose media again.
- Provider routing/fallback was adjusted and verified earlier:
  - Avatar: `piapi -> a2e`
  - Image/video tools: `piapi_mcp` / `piapi`, then `pollo` / `pollo_mcp`, then `vertex_ai` / Gemini where applicable.
- Admin Rescue Mechanism display was corrected and browser-verified on the deployed site before this document-driven patch set.

## Verification Completed

| Check | Result |
| --- | --- |
| Backend Python syntax compile | Passed with the configured Python 3.12 interpreter. |
| VS Code diagnostics on touched backend/frontend files | Passed: no errors reported. |
| `git diff --check` | Passed after normalizing CRLF line endings and removing trailing whitespace. |
| Local `npm` availability | Not available in this machine environment, so frontend build/type-check could not be run locally. |
| Local pytest with configured Python | Blocked because the configured Python environment only has `pip` and no `pytest`. |
| `uv run pytest ...` | Blocked while building `llvmlite==0.46.0`, from `rembg -> pymatting -> numba -> llvmlite`, with `TypeError: spawn() got an unexpected keyword argument 'dry_run'`. |

## External Validation Still Required

These items cannot be fully proven by local code changes alone:

- Real Paddle checkout and webhook completion with production price IDs.
- Real ECPay callback/signature flow in the production merchant account.
- Real Giveme invoice auto-issue flow with production credentials.
- A2E provider permission/authentication if upstream still returns `403`.
- Final provider output quality and commercial realism, because that depends on upstream model/account behavior and generated assets.
- Frontend production build or type-check in a container/Cloud Build environment because local `npm` is unavailable.
- Full backend pytest suite in an environment where the `llvmlite` dependency can build or where the dependency stack is already installed.

## Recommended Next Steps

1. Run frontend build/type-check in Cloud Build or a Node-enabled container.
2. Run backend tests in the project container or a prepared Python environment with the dependency stack installed.
3. Deploy the patched backend/frontend to GCP staging or production.
4. Browser-test the high-risk flows: registration, password reset, paid checkout, credit package payment, My Works download, Product Scene 0-credit generation, and provider-error fallback.