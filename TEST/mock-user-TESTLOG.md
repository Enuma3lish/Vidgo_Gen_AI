# VidGo — Mock User Behaviour · Test Log

Reference document for all mock-user behaviour tests run during the
deep QA pass on **2026-04-24** against Cloud Run `asia-east1`.
Companion diagrams:

- [mock-user-behavior.mmd](mock-user-behavior.mmd) — full persona × action flowchart
- [mock-user-lifecycle.mmd](mock-user-lifecycle.mmd) — subscription state machine
- [mock-user-billing-sequence.mmd](mock-user-billing-sequence.mmd) — billing sequence
- [mock-user-tool-sequence.mmd](mock-user-tool-sequence.mmd) — tool-call sequence

Test runner scripts:

| Script | Scope |
|---|---|
| [TEST/deep_tool_test.py](deep_tool_test.py) | Per-tool validation (10 tools, real output sanity) |
| [TEST/deep_billing_test.py](deep_billing_test.py) | Visitor + register-shape + plans + account state |
| [TEST/deep_billing_lifecycle.py](deep_billing_lifecycle.py) | subscribe/cancel/upgrade lifecycle |
| [TEST/test_fixes_unit.py](test_fixes_unit.py) | Unit-level verification of tool fixes |
| [TEST/test_billing_fixes.py](test_billing_fixes.py) | Unit-level verification of billing fixes |
| [TEST/verify_billing_fixes.py](verify_billing_fixes.py) | End-to-end verification on deployed revision |

Deployments exercised:

| Revision | Image tag | Purpose |
|---|---|---|
| `vidgo-backend-00074-xmv` | `50b1713f-556a-4b9f-a5f9-7b9e4d3530d7` | Tool fixes (Try-On GCS, HD Enhance) |
| `vidgo-backend-00075-hmm` | `2c98bfe0-420a-48b3-abda-3af261d3a063` | Billing fixes A–H, exposed order_number collision |
| `vidgo-backend-00076-cbl` | `2dde56e4-a955-4c73-9a7c-573f25a7ab46` | **Current** — billing fixes + uuid suffix |

---

## 1 · Persona × scenario matrix

Each row is one realistic user journey simulated against the running
backend. Pass/fail counts are per-scenario assertions.

### 1.1 · Visitor (no auth)

| # | Scenario | Script | Result |
|---|---|---|---|
| 1.1.1 | `GET /subscriptions/plans` returns 4 plans with prices | deep_billing_test | ✅ basic 699 / pro 999 / premium 1 699 / enterprise 15 000 TWD |
| 1.1.2 | `GET /credits/pricing` returns 29 pricing rows | deep_billing_test | ✅ |
| 1.1.3 | `GET /auth/geo-language` returns locale | deep_billing_test | ✅ |
| 1.1.4 | `GET /tools/list` — tool catalogue | deep_billing_test | ✅ |
| 1.1.5 | Protected endpoints reject without token | deep_billing_test | ✅ `/credits/balance` → 401, `/auth/me` → 401 |
| 1.1.6 | Tool call (`/tools/remove-bg`) returns demo response | deep_billing_test | ✅ `is_demo=true` · CTA copy present |
| 1.1.7 | `/register` with bad body → 422 | deep_billing_test | ✅ |
| 1.1.8 | `/login` with wrong password → 401 | deep_billing_test | ✅ |
| 1.1.9 | `/login` with unverified email → 403 mentions "6-digit code" | verify_billing_fixes | ✅ VG-FIX-G |

### 1.2 · Registered but unverified

| # | Scenario | Script | Result |
|---|---|---|---|
| 1.2.1 | Register fresh user returns 6-digit code message | probe_visitor_unpaid | ✅ |
| 1.2.2 | Register duplicate email → 409 "already exists" | deep_billing_test | ✅ |
| 1.2.3 | Register password mismatch → 422 | deep_billing_test | ✅ |
| 1.2.4 | Register password too short → 422 | deep_billing_test | ✅ |
| 1.2.5 | `/verify-code` for unregistered email → 422 | deep_billing_test | ✅ |
| 1.2.6 | Pre-verify login blocked with helpful message | verify_billing_fixes | ✅ "Check your inbox for the 6-digit verification code" |
| 1.2.7 | `/resend-code` succeeds | probe_visitor_unpaid | ✅ rate-limited to 3/h |

### 1.3 · Free member (verified, no plan)

| # | Scenario | Expected | Result |
|---|---|---|---|
| 1.3.1 | `/auth/me` → `plan_type=null`, `current_plan_id=null` | schema has `current_plan_id` | ✅ VG-FIX-C |
| 1.3.2 | `/credits/balance` → `total = bonus_credits` | 200 OK shape | ✅ |
| 1.3.3 | `POST /tools/*` → `is_demo=true` (no deduction) | demo path | ✅ observed |
| 1.3.4 | `POST /effects/hd-enhance` → 403 "Active subscription required" | subscribers-only gate | ✅ observed |
| 1.3.5 | `POST /subscriptions/subscribe` → checkout_url | starts checkout | ✅ mock path exercised |

### 1.4 · Paid subscriber (per tier)

Tested against live backend using the superuser QA account's
`action="refresh"` path (real subscribe flow — activates DB rows, allocates credits,
creates complimentary Order). Each row is an endpoint × behaviour assertion.

#### 1.4.1 · basic (699 TWD, 7000 cr, 720p, watermark, no effects)

| # | Behaviour | Result |
|---|---|---|
| — | Policy only (no tool calls executed while on basic) | see matrix in .mmd |

#### 1.4.2 · pro (999 TWD, 10000 cr, 1080p, effects)

| # | Behaviour | Script | Result |
|---|---|---|---|
| 1.4.2.1 | `remove-bg` returns real PNG · alpha channel | deep_tool_test | ✅ 768×558 RGBA · α=0 corner · α=254 centre |
| 1.4.2.2 | `product-scene` returns 1024×1024 PNG | deep_tool_test | ✅ 1 263 392 B · 1653 unique centre colours |
| 1.4.2.3 | `room-redesign` returns 1024×768 PNG | deep_tool_test | ✅ 1597 unique centre colours |
| 1.4.2.4 | `effects/apply-style` anime returns distinct output vs image-transform | deep_tool_test | ✅ 767 non-zero diff-histogram buckets |
| 1.4.2.5 | `image-transform` watercolour returns 768×928 | deep_tool_test | ✅ 1 387 131 B |
| 1.4.2.6 | `upscale scale=2` returns 1536×1116 (exact 2×) | deep_tool_test | ✅ |
| 1.4.2.7 | `upscale scale=4` blocked by plan-resolution gate | deep_tool_test (on pro) | ✅ 400 "plan does not support 4k" |
| 1.4.2.8 | `short-video` returns ISO-BMFF MP4 | deep_tool_test | ✅ `ftypisom` magic |
| 1.4.2.9 | `avatar` returns MP4 | deep_tool_test | ✅ 1 636 344 B |
| 1.4.2.10 | `try-on` returns absolute GCS URL (not `/static/…`) | deep_tool_test pre/post fix | ✅ VG-FIX-1 · 768×1152 RGB |
| 1.4.2.11 | `hd-enhance 2k` succeeds · 2× upscale | deep_tool_test pre/post fix | ✅ VG-FIX-2 code path now reads `result.output.image_url` |
| 1.4.2.12 | `hd-enhance 4k` succeeds · 4× upscale · 3072×2232 | deep_tool_test | ✅ 3 038 978 B |

#### 1.4.3 · premium (1699 TWD, 18000 cr, 4k, priority queue)

| # | Behaviour | Script | Result |
|---|---|---|---|
| 1.4.3.1 | `hd-enhance target=4k` returns real 4k output | deep_tool_test | ✅ 3072×2232 |
| 1.4.3.2 | All pro tools work at higher resolution cap | deep_tool_test | ✅ |

#### 1.4.4 · enterprise (15000 TWD, 160000 cr, 4k, all features)

| # | Behaviour | Script | Result |
|---|---|---|---|
| 1.4.4.1 | `subscribe(enterprise)` from premium classified UPGRADE | verify_billing_fixes | ✅ VG-FIX-A · status=active · credits_allocated=160 000 |
| 1.4.4.2 | `subscribe(enterprise)` creates Order `DIRECT-…-uuid6` | verify_billing_fixes | ✅ 5 rows in `/invoices` (VG-FIX-D) |

### 1.5 · Plan change (pivotal — was the bug surface)

| # | Scenario | Before fix | After fix |
|---|---|---|---|
| 1.5.1 | pro → premium | `status=pending_downgrade` ❌ | `status=active · credits=18 000` ✅ |
| 1.5.2 | pro → enterprise | `status=pending_downgrade` ❌ | `status=active · credits=160 000` ✅ |
| 1.5.3 | premium → enterprise | `status=pending_downgrade` ❌ | `status=active · credits=160 000` ✅ |
| 1.5.4 | enterprise → basic | `status=pending_downgrade` ✅ (coincidentally right) | `status=pending_downgrade` ✅ |
| 1.5.5 | premium → premium (no action) | `status=active · +18 000 cr duplicate` ❌ | `400 "Already subscribed to this plan"` ✅ VG-FIX-B |
| 1.5.6 | premium → premium (`action="refresh"`) | same as above | `200 · credits re-granted · DIRECT audit row` ✅ |
| 1.5.7 | Subscribe with bogus UUID | `400` | `400` ✅ |
| 1.5.8 | Rapid concurrent subscribes | **500** `UniqueViolationError on ix_orders_order_number` ❌ | `200` (uuid6 suffix) ✅ |

### 1.6 · Billing views

| # | Endpoint | Result |
|---|---|---|
| 1.6.1 | `GET /subscriptions/status` | ✅ returns plan, status, dates, refund_eligible, credits, pending_downgrade |
| 1.6.2 | `GET /subscriptions/current` alias | ✅ VG-FIX-H returns identical body |
| 1.6.3 | `GET /subscriptions/invoices` includes direct orders | ✅ VG-FIX-D 5 `DIRECT-…` rows visible |
| 1.6.4 | `GET /subscriptions/history` | ✅ shows all subscriptions incl. cancelled |
| 1.6.5 | `GET /subscriptions/refund-eligibility` | ✅ eligible=true days_remaining=7 |
| 1.6.6 | `GET /subscriptions/plan-features` (no query) | ✅ returns current user's plan |
| 1.6.7 | `GET /subscriptions/plan-features?plan_id=premium` | ✅ VG-FIX-F preview=true, max_res=4k |
| 1.6.8 | `GET /subscriptions/plan-features?plan_id=enterprise` | ✅ preview=true |
| 1.6.9 | `GET /credits/balance` | ✅ subscription / purchased / bonus / total |
| 1.6.10 | `GET /credits/transactions` | ✅ 30 rows; types subscription / generation / refund |
| 1.6.11 | `GET /credits/transactions?transaction_type=refund` | ✅ filter accepted (new `refund`-typed rows from VG-FIX-E) |

### 1.7 · Cancel flow

| # | Scenario | Expected | Result |
|---|---|---|---|
| 1.7.1 | Cancel without refund | 200 · `credits retained` · `auto_renew=false` · `active_until`=end_date · `work_retention_until`=end_date+7d | ✅ |
| 1.7.2 | Cancel with refund within 7d | 200 · all credits revoked · invoice voided · work_retention_until=now+7d | ✅ code-path verified (not executed live) |
| 1.7.3 | Cancel with refund after 7d | 400 "Refund period expired" | ✅ code-path verified (REFUND_ELIGIBILITY_DAYS=7) |
| 1.7.4 | Cancel bad body | 422 | ✅ |
| 1.7.5 | Cancel without token | 401 | ✅ |
| 1.7.6 | Cancel with no active sub | 400 "No active subscription" | ✅ code-path verified |

### 1.8 · Superuser / admin

| # | Scenario | Result |
|---|---|---|
| 1.8.1 | `/auth/me` reveals `is_superuser=true`, `current_plan_id` | ✅ VG-FIX-C |
| 1.8.2 | Subscribe with `skip_payment=True` via superuser path | ✅ direct activation |
| 1.8.3 | Tool call bypasses credit deduction | ✅ (observed: credit delta = 0 across full tool run) |
| 1.8.4 | `action="refresh"` same-plan grants new credits | ✅ VG-FIX-B |
| 1.8.5 | Non-superuser cannot pass `action="refresh"` to bypass | ✅ `is_admin_refresh = skip_payment and action=="refresh"`; non-admins never get `skip_payment=True` |

### 1.9 · Webhook / payment provider

| # | Scenario | Result |
|---|---|---|
| 1.9.1 | ECPay callback with bad CheckMacValue | ✅ rejected with `0\|SignatureError` |
| 1.9.2 | ECPay callback valid signature (code path) | ✅ marks Order paid, issues Invoice |
| 1.9.3 | Paddle webhook `transaction.completed` | ✅ code path reviewed (webhook_paid) |
| 1.9.4 | No provider configured → mock activation | ✅ `use_mock=True` path active, `Order.status=complimentary` |

---

## 2 · Bugs found, filed, and fixed

All the following were found while executing scenarios above. Each has a
corresponding code change now live on `vidgo-backend-00076-cbl`.

| ID | Severity | Bug | Fix |
|---|---|---|---|
| VG-FIX-1 | 🔴 Critical | Try-On returned `/static/generated/...` relative path from Cloud Run ephemeral disk | `_download_as` now uploads to GCS via `get_gcs_storage().upload_public()` with proper content-type routing; local-disk fallback only in dev · [piapi_client.py:847](../backend/scripts/services/piapi_client.py#L847) |
| VG-FIX-2 | 🔴 Critical | HD Enhance returned "HD enhancement failed" even when provider succeeded — bug was `result.get('image_url')` instead of `result['output']['image_url']` | Now reads `result['output']['image_url']` with flat keys as fallback · [effects_service.py:317](../backend/app/services/effects_service.py#L317) |
| VG-FIX-A | 🔴 Critical | `PLAN_LEVEL = {"demo":0,"starter":1,"standard":2,"pro":3,"pro_plus":4}` did not match real DB names (basic/pro/premium/enterprise), so every upgrade from pro misclassified as downgrade | `_plan_rank()` uses `plan.price_monthly` with credit / named fallbacks · [subscription_service.py:148-188](../backend/app/services/subscription_service.py#L148-L188) |
| VG-FIX-B | 🔴 Critical | Superuser could grant themselves unlimited credits by re-posting `/subscribe` to current plan | Require explicit `action="refresh"` flag; default rejects with 400 · [subscription_service.py:61-113](../backend/app/services/subscription_service.py#L61-L113) |
| VG-FIX-C | 🟠 High | `/auth/me` did not expose `current_plan_id` | Added field to `UserWithDetails` and populated in `/me` · [schemas/user.py:52-58](../backend/app/schemas/user.py#L52-L58), [auth.py:552-555](../backend/app/api/v1/auth.py#L552-L555) |
| VG-FIX-D | 🟠 High | Direct-activated subscriptions produced zero invoice trail | Write `Order(status="complimentary", order_number="DIRECT-…-uuid6")` on activation; `/invoices` includes both paid + complimentary · [subscription_service.py:301-332](../backend/app/services/subscription_service.py#L301-L332) |
| VG-FIX-E | 🟠 High | Refund rows were mislabelled `transaction_type="subscription"` | `add_credits()` takes optional `transaction_type` override; `_refund_credits` uses `"refund"` · [credit_service.py:224-274](../backend/app/services/credit_service.py#L224-L274) |
| VG-FIX-F | 🟠 High | `/plan-features` ignored `plan_id` query (couldn't preview an upgrade candidate) | Accepts `plan_id`, returns preview with price + credits + features · [subscriptions.py:558-617](../backend/app/api/v1/subscriptions.py#L558-L617) |
| VG-FIX-G | 🟡 Low | Unverified-login error mentioned "verification link" while flow uses a 6-digit code | Updated copy · [auth.py:82](../backend/app/api/v1/auth.py#L82) |
| VG-FIX-H | 🟡 Low | `/subscriptions/current` returned 404 because route did not exist | Added alias decorator on `/status` handler · [subscriptions.py:336-337](../backend/app/api/v1/subscriptions.py#L336-L337) |
| side-fix | 🟠 High (introduced by VG-FIX-D) | Rapid direct subscribes collided on `ix_orders_order_number` unique index | Added `uuid4.hex[:6]` suffix to order number · [subscription_service.py:320](../backend/app/services/subscription_service.py#L320) |

---

## 3 · Observations / remaining watch-list

These are not bugs yet — observations worth tracking.

- **Legacy mislabelled refund rows** still exist in `CreditTransaction` with `transaction_type="subscription"` and description starting with `"Refund:"`. ~19 rows for the QA account. Consider a one-off backfill migration that reclassifies them by description prefix.
- **Plan-catalogue drift**: `DEFAULT_VIDGO_PLANS` in [subscriptions.py:121-127](../backend/app/api/v1/subscriptions.py#L121-L127) still lists `demo/starter/standard/pro/pro_plus`, which no longer match production DB (`basic/pro/premium/enterprise`). The `ensure_vidgo_plans` seeder is a no-op because rows exist, but a new environment would be seeded with the wrong names. Consider aligning.
- **QA account state**: after the destructive test sequence, `qaz0978005418@gmail.com` is on **enterprise** with a `pending_downgrade → pro` scheduled for 2026-05-23. Credits inflated to ~160 k. Account is superuser, no billing impact, and will auto-heal at period end.

---

## 4 · Reproducing the suite

All tests are credential-driven via env vars, do not hardcode secrets in
tool calls:

```bash
export VIDGO_EMAIL=qaz0978005418@gmail.com
export VIDGO_PASSWORD=<password>

# Tool output validation
backend/.venv/bin/python TEST/deep_tool_test.py

# Visitor + register-shape + plans
backend/.venv/bin/python TEST/deep_billing_test.py

# Subscription lifecycle
backend/.venv/bin/python TEST/deep_billing_lifecycle.py

# Fix verification on deployed revision
backend/.venv/bin/python TEST/verify_billing_fixes.py
```

Artefacts produced:

- `/tmp/deep_tool_report.json` — per-tool output metrics
- `/tmp/deep_billing_lifecycle.log` — full subscribe/cancel sequence
- `/tmp/verify_billing.log` + `/tmp/verify_billing2.log` + `/tmp/verify_billing3.log` — three iterative verification runs

---

## 5 · Snapshot of diagrams

The four `.mmd` files in this directory are stand-alone Mermaid sources
renderable at https://mermaid.live or via VS Code's Markdown Preview
Mermaid Support extension. They are not embedded in a parent markdown so
they can be consumed by auto-generated documentation pipelines.
