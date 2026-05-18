# PayPal Setup & Sandbox→Production Switch

VidGo's PayPal integration is **runtime-configurable**. You can flip
between sandbox and production, rotate the client secret, or update the
plan-ID mapping from the admin dashboard **without a redeploy**.

This document covers:

1. [How config is resolved at runtime](#how-config-is-resolved-at-runtime)
2. [First-time PayPal setup (sandbox)](#first-time-paypal-setup-sandbox)
3. [Sandbox testing checklist](#sandbox-testing-checklist)
4. [Switch to production from the admin UI](#switch-to-production-from-the-admin-ui)
5. [Emergency CLI override via Secret Manager](#emergency-cli-override-via-secret-manager)
6. [Troubleshooting](#troubleshooting)

---

## How config is resolved at runtime

PayPal credentials live in **three places**, in priority order:

| Priority | Source | Where it's edited | Persistence |
|---|---|---|---|
| 1 (highest) | `payment_settings` DB row | `/admin/settings/payment` UI | Postgres, encrypted (client_secret only) |
| 2 | Cloud Run env vars from Secret Manager | `gcloud run services update --update-secrets` | Secret Manager, mounted on container startup |
| 3 (lowest) | `Settings` class defaults | `backend/app/core/config.py` | Code; effectively empty for prod |

`PaymentSettingsService.get_resolved_settings(db)` returns the effective
value per field. If the DB row column is `NULL`, the env value is used.
That's why "clear DB override" buttons in the admin UI exist — they wipe
the column so the env fallback wins again.

The PayPal service refreshes from the DB on **every checkout / webhook
call**, with a 60-second in-process cache. So a config change in the UI
becomes live within ~60s, no redeploy.

`paypal_client_secret` is encrypted at rest with Fernet, keyed off
`SECRET_KEY` (same secret JWT signing uses). Rotating `SECRET_KEY`
invalidates stored ciphertexts — you'll need to re-enter the PayPal
secret in the UI.

---

## First-time PayPal setup (sandbox)

You only do this once per environment.

### 1. Create a PayPal sandbox app

1. Go to <https://developer.paypal.com/dashboard/applications/sandbox>.
2. Log in with the PayPal account that owns the **VidGo merchant**.
3. **Create App** → pick **Merchant** type. Give it a name like
   `VidGo Backend (Sandbox)`.
4. Note the **Client ID** and **Secret**. These are sandbox values —
   they only work against `api-m.sandbox.paypal.com`.

### 2. Create sandbox subscription plans

The frontend maps internal plan slugs (`basic_monthly`, `pro_yearly`,
…) to PayPal Plan IDs. You must create one PayPal plan per cell of the
matrix.

1. In Sandbox dashboard → **My Apps & Credentials → Sandbox accounts**,
   make sure you have a **Business** account.
2. Switch to that account → **Catalog & Pricing → Subscription Plans**.
3. For each VidGo plan (basic, pro, premium) and each cycle (monthly,
   yearly), create a plan. Use USD amounts that match
   `frontend-vue/src/views/Pricing.vue:OVERSEAS_USD_MONTHLY`:
   - basic: $19.99/mo, $239.88/yr
   - pro: $49.99/mo, $599.88/yr
   - premium: $99.99/mo, $1199.88/yr
4. Note each plan's ID — they all start with `P-`.

You should end up with at least 6 PayPal Plan IDs. (Enterprise is
typically priced by sales and not exposed in the public PayPal flow.)

### 3. Create a sandbox webhook

1. In the same Sandbox app → **Webhooks → Add Webhook**.
2. URL: `https://vidgo.co/api/v1/payments/paypal/webhook`
3. Event types you must subscribe to:
   - `BILLING.SUBSCRIPTION.ACTIVATED`
   - `BILLING.SUBSCRIPTION.CANCELLED`
   - `BILLING.SUBSCRIPTION.SUSPENDED`
   - `BILLING.SUBSCRIPTION.PAYMENT.FAILED`
   - `PAYMENT.SALE.COMPLETED`
   - `PAYMENT.SALE.REFUNDED`
4. Save and note the **Webhook ID** (format: `WH-...` or `Numeric-X`).

### 4. Store sandbox creds in the admin UI

1. Open <https://vidgo.co/admin/settings/payment> as a superuser.
2. Set **PAYPAL_ENV → `sandbox`**.
3. Paste:
   - **PAYPAL_CLIENT_ID** from step 1
   - **PAYPAL_CLIENT_SECRET** from step 1
   - **PAYPAL_WEBHOOK_ID** from step 3
   - **PAYPAL_PLAN_IDS** as JSON:
     ```json
     {
       "basic_monthly": "P-XXXXX",
       "basic_yearly":  "P-XXXXX",
       "pro_monthly":   "P-XXXXX",
       "pro_yearly":    "P-XXXXX",
       "premium_monthly":"P-XXXXX",
       "premium_yearly": "P-XXXXX"
     }
     ```
4. **Save Changes**.
5. Click **Test Connection** — must show ✓ `OAuth ok. env=sandbox`.

---

## Sandbox testing checklist

Once sandbox config is saved, run through these flows. Each one
exercises a different PayPal endpoint.

1. **Subscribe (happy path)**
   - Log in as a non-admin user with no active sub.
   - Go to `/pricing`. PayPal button should be visible (non-zh locale).
   - Click it → redirect to `sandbox.paypal.com` → log in with a sandbox
     Personal/Buyer account → approve.
   - Returns to `/subscription/success?order=SUB...`.
   - User row in DB has `status=active`, `plan_id=basic`, monthly credits
     allocated.

2. **Webhook delivery**
   - In PayPal Sandbox dashboard → Webhooks → your webhook → **Webhook
     simulator**.
   - Send a `BILLING.SUBSCRIPTION.ACTIVATED` event.
   - Cloud Run logs should show
     `[PayPal] webhook received event=BILLING.SUBSCRIPTION.ACTIVATED`.

3. **Cancel + refund**
   - Subscribed user clicks Cancel in `/dashboard/subscription`.
   - Within refund window (7 days) → backend issues partial refund via
     `paypal.create_refund()`.
   - Sandbox dashboard → Transactions → confirm REFUNDED status.

4. **Negative paths**
   - User abandons sandbox checkout → `pending_payment` order remains;
     no double-allocation on retry.
   - Webhook signature mismatch → 400, logged, no DB write.

---

## Switch to production from the admin UI

After sandbox is green, swap to live in **one place**:

1. Create a **production** PayPal app at
   <https://developer.paypal.com/dashboard/applications/live>.
2. Create production subscription plans (same six cells as sandbox, with
   the same USD prices). Get the new `P-...` IDs.
3. Create the production webhook (same URL, same event types). Get the
   new webhook ID.
4. Open `/admin/settings/payment`:
   - Flip **PAYPAL_ENV → `production`** (the toggle turns red — a real-
     money warning).
   - Replace **PAYPAL_CLIENT_ID** with the live one.
   - Replace **PAYPAL_CLIENT_SECRET** with the live one.
   - Replace **PAYPAL_WEBHOOK_ID** with the live one.
   - Replace **PAYPAL_PLAN_IDS** with the live JSON map.
5. **Save Changes**. Per-field source badge should now show `DB override`
   for everything you replaced.
6. Click **Test Connection** — must show ✓ `env=production` with a
   token prefix starting with `A21AAM...` (live tokens differ from
   sandbox; if you see `A21AAL...` you're still on sandbox).
7. Smoke-test by paying the smallest plan with your own card (and
   refunding right after via PayPal Activity).

**Rollback**: flip `PAYPAL_ENV` back to `sandbox` and click Save. The
sandbox creds are still in their DB columns; the env switch alone
re-routes to `api-m.sandbox.paypal.com`. Customer-facing checkout
buttons hide automatically (`/api/v1/payments/methods` reports
`is_sandbox: true`).

---

## Emergency CLI override via Secret Manager

If the admin UI is down or the DB is unreachable, you can update PayPal
config directly via `gcloud`:

```bash
# Rotate ONE secret (e.g. the secret leaked publicly):
printf "%s" "NEW_PAYPAL_CLIENT_SECRET_HERE" | \
  gcloud --project vidgo-ai secrets versions add PAYPAL_CLIENT_SECRET \
    --data-file=-

# Get the new version number:
gcloud --project vidgo-ai secrets versions list PAYPAL_CLIENT_SECRET --limit=1

# Pin Cloud Run to it (this creates a new revision and rolls 100%):
gcloud --project vidgo-ai run services update vidgo-backend \
  --region asia-east1 \
  --update-secrets="PAYPAL_CLIENT_SECRET=PAYPAL_CLIENT_SECRET:3"
```

**Important:** if a value is set in the `payment_settings` DB row, it
takes priority over Secret Manager. Either clear the DB override first
(admin UI → blank the field → Save) or update the DB row directly:

```sql
UPDATE payment_settings SET paypal_client_secret_encrypted = NULL WHERE id = 1;
```

After the next 60-second cache window the runtime will pick up the
Secret-Manager value.

### Switching env via CLI (no UI)

```bash
# Flip to production without touching the UI:
gcloud --project vidgo-ai run services update vidgo-backend \
  --region asia-east1 \
  --update-env-vars="PAYPAL_ENV=production"
```

This only matters when no DB override is set. If the admin UI has set
`paypal_env=sandbox`, the env var is ignored.

### Always-true rule

> `payment_settings` DB row > Cloud Run env / Secret Manager > built-in defaults

To confirm what's actually live, hit:

```bash
curl -s https://vidgo.co/api/v1/payments/methods
# → {"paypal":{"enabled":true,"is_sandbox":false}, ...}
```

`is_sandbox` reflects the **effective** value the backend will use.

---

## Troubleshooting

### "Payment checkout is temporarily unavailable" (HTTP 400)

The plan map can't resolve `{slug}_{cycle}` to a `P-...` ID. Either:
- `PAYPAL_PLAN_IDS` JSON is missing the cell.
- `PAYPAL_PLAN_IDS` JSON has a syntax error.
- The plan's `slug`/`name` in DB differs from the JSON key (plan slug
  takes priority over name when building the lookup key).

Fix in admin UI → paste corrected JSON → Save.

### "PayPal API error: 401" in Cloud Run logs

Your client_id / secret pair doesn't authenticate. Most common causes:

- Trailing newline in the secret value (was a real bug in our initial
  Secret Manager rollout). `printf "%s"` instead of `echo`. The admin UI
  strips this automatically.
- Sandbox credentials used while `PAYPAL_ENV=production` (or vice
  versa). Each environment has separate credentials at PayPal.
- Wrong PayPal account. `app_id` from `Test Connection` should match
  the merchant.

### "PayPal button doesn't appear on /pricing"

`/api/v1/payments/methods` returns `paypal.enabled: false`. That means
no `paypal_client_id` AND no `paypal_client_secret` is resolvable.
Check:
1. Admin UI → does it show the values?
2. If both come from "Env / Secret Manager" but enabled=false, the
   secret on Cloud Run might be empty. Either the binding got removed
   or the secret version mounted is empty.

### "checkout_url is null, is_mock: true"

Backend is in mock mode. Usually means credentials couldn't be loaded
from either source. Triggers the warning log
`PayPal credentials not configured - running in MOCK mode` at startup.

### Encryption error: "Failed to decrypt payment secret"

`SECRET_KEY` was rotated. Stored client_secret can't be decrypted.
Re-enter it via admin UI; the new value gets encrypted with the new
key.

---

## Files

Backend:

- `backend/app/models/payment_settings.py` — DB model
- `backend/app/services/payment_settings_service.py` — read-through cache + Fernet
- `backend/app/services/paypal_service.py` — `refresh_from_db()` integrates the override
- `backend/app/api/v1/admin.py` — `/admin/settings/payment` endpoints
- `backend/app/api/v1/payments.py:get_payment_methods` — reflects runtime override
- `backend/alembic/versions/e7f8a9b0c1d2_add_payment_settings.py` — table migration

Frontend:

- `frontend-vue/src/views/admin/AdminPaymentSettings.vue` — admin UI
- `frontend-vue/src/router/index.ts` — `/admin/settings/payment` route

Secret Manager (gcp project `vidgo-ai`):

- `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`, `PAYPAL_PLAN_IDS`
