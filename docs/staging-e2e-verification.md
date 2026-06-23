# Staging E2E Verification Runbook (Phase 2/3/4)

> **Why this exists.** Several flows can only be proven on a live, multi-instance
> staging environment with real sandbox credentials — they are *not* coverable by
> the unit/CI suite (which mocks DB/Redis/providers). Without a standing sandbox
> staging + seed accounts, Phase 2/3/4 verification stalls at "code reviewed,
> green in CI". This runbook is the repeatable process ticket for that.
>
> Code-level state of each item below is **PASS**; what remains is the live run.

---

## 0. One-time: stand up sandbox staging

A separate, low-cost deploy that mirrors prod but in sandbox mode and **with
Redis** (prod dropped Memorystore in the 2026-06 cost pass — but the pub/sub
cross-instance test in §4 needs it, so staging must re-enable it):

- Deploy backend to a staging Cloud Run service, **`--min-instances 2`** (so the
  cross-instance pub/sub broadcast in §4 is actually exercised).
- Env / secrets:
  - `ECPAY_ENV=sandbox` (`config.py:98`) + ECPay **test** merchant id / hash key / hash IV.
  - `PAYPAL_ENV=sandbox` + PayPal sandbox creds (optional, for the PayPal path).
  - A reachable **Redis** (Memorystore or a small VM) + `REDIS_URL` set, so the
    model-registry pub/sub subscriber starts (`main.py` lifespan) and §4 can pass.
  - `GIVEME_ENABLED` per the invoice provider you're testing.

---

## 1. Seed the four accounts

| Account | How |
|---|---|
| **Guest** | No account — just browse / hit demo endpoints unauthenticated. |
| **Free** | Register through the UI (or `backend/scripts/seed_test_user.py`), no subscription. |
| **Subscriber** | `bash gcp/seed-qa-personas.sh` → seeds `qa-pro@vidgo.local` + `qa-premium@vidgo.local` (needs a `.qa-secrets` file). |
| **Admin** | `ADMIN_ACCOUNT` / `ADMIN_PASSWORD` seeded by `gcp/deploy.sh` (Phase 3, `seed_admin`). |

---

## 2. Verification checklist (the BLOCKED items)

### A. Four seed accounts — end-to-end
For each account, exercise the gating that the unit tests only assert structurally:
- **Guest / Free** → tool generate returns the watermarked demo / `subscription_card_required`, never a real Provider charge.
- **Subscriber** → real generation, no watermark, credits deducted via the single gateway.
- **Admin** → `require_admin` (is_superuser) pages load; admin actions deduct 0 credits.

### B. ECPay sandbox checkout
- With `ECPAY_ENV=sandbox`, run a subscription checkout with an **ECPay test card**.
- Expect the order to redirect to ECPay's sandbox Cashier and return to the result page.

### C. Payment callback — `handle_payment_success`
`backend/app/services/subscription_service.py:1507`. After the sandbox payment, confirm:
1. **Order → `Paid`**.
2. **Credits granted** (currency-aware: TWD/ECPay vs USD/PayPal; yearly = 11/12 proration).
3. **`auto_issue_invoice`** fires and issues the correct type:
   - carrier / donation / **B2B** per the buyer's saved `default_invoice_mode`
     (set "公司發票＋統編" → expect `Invoice.invoice_type == "b2b"` with the tax id).

### D. Provider timeout + Redis pub/sub cross-instance broadcast
- **Provider timeout / reclaim:** trigger a long generation (avatar / try-on / Veo) and
  kill/scale the serving instance mid-poll; confirm the `pending_provider_tasks`
  reclaim worker (Cloud Scheduler → `/api/v1/tasks/*`) materialises the result or
  refunds — no silently lost credits.
- **Model-registry pub/sub:** with Redis up and ≥2 instances, change a model override
  in `/admin/models` on one instance; confirm the other instance picks up the new
  model within one pub/sub cycle (`refresh_in_process_cache`). **If staging has no
  Redis**, this degrades to restart/RESEED propagation (the prod path) — test that
  instead and note it.

---

## Notes
- Most seeding tooling already exists (above) — the standing cost is the staging
  env + sandbox credentials, not new scripts.
- Keep this as a recurring pre-release gate; CI green is necessary but not sufficient
  for Phase 2/3/4 sign-off.
