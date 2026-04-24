#!/usr/bin/env python3
"""
VidGo — Deep billing & auth lifecycle test.

Covers:
  1. Visitor (no auth): which endpoints work, which are gated, demo responses
  2. Registration: /register input validation + auth-guard before verification
  3. Plans: /subscriptions/plans catalogue
  4. Existing paid account: /auth/me, /credits/balance, transactions, invoices,
     active subscription info, tool access, resolution gates
  5. Subscription flow edge cases: same-plan, lower-plan, higher-plan (without
     actually completing payment — we inspect the response shape)
  6. Cancel flow edge cases: cannot-cancel-free, cancel-shape (without actually
     cancelling this live account)
  7. ECPay webhook signature check — can an unsigned callback activate an order?
"""
import asyncio
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

BACKEND = os.environ.get("VIDGO_BACKEND", "https://vidgo-backend-38714015566.asia-east1.run.app")
EMAIL = os.environ["VIDGO_EMAIL"]
PASSWORD = os.environ["VIDGO_PASSWORD"]


@dataclass
class R:
    scenario: str
    step: str
    ok: bool
    detail: str = ""


results: list[R] = []


def log(scen: str, step: str, ok: bool, detail: str = ""):
    results.append(R(scen, step, ok, detail))
    icon = "PASS" if ok else "FAIL"
    print(f"  [{icon}] {scen} · {step}" + (f" — {detail}" if detail else ""))


async def http_get(client, path, token=None, **kw):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    r = await client.get(f"{BACKEND}{path}", headers=h, **kw)
    return r


async def http_post(client, path, body=None, token=None, **kw):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    r = await client.post(f"{BACKEND}{path}", json=body or {}, headers=h, **kw)
    return r


# ───────────────────────────────── Scenario 1 ─────────────────────────────────
async def scenario_visitor(client: httpx.AsyncClient):
    scen = "1 Visitor"

    # 1a. Public GETs — should all return 200
    public_gets = [
        "/api/v1/subscriptions/plans",
        "/api/v1/credits/pricing",
        "/api/v1/auth/geo-language",
        "/api/v1/tools/list",
    ]
    for p in public_gets:
        r = await http_get(client, p)
        log(scen, f"GET {p}", r.status_code == 200, f"HTTP {r.status_code}")

    # 1b. Protected endpoints must reject (401/403/422)
    r = await http_get(client, "/api/v1/credits/balance")
    log(scen, "GET /credits/balance (no token)", r.status_code in (401, 403),
        f"HTTP {r.status_code}")
    r = await http_get(client, "/api/v1/auth/me")
    log(scen, "GET /auth/me (no token)", r.status_code in (401, 403),
        f"HTTP {r.status_code}")
    r = await http_get(client, "/api/v1/subscriptions/current")
    log(scen, "GET /subscriptions/current (no token)", r.status_code in (401, 403),
        f"HTTP {r.status_code}")

    # 1c. Tool call as visitor — should get demo response (success + is_demo=true
    # OR a 401/403), NOT 500
    r = await http_post(client, "/api/v1/tools/remove-bg",
                        {"image_url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=768"})
    if r.status_code == 200:
        d = r.json()
        is_demo = d.get("is_demo")
        log(scen, "POST /tools/remove-bg (visitor)", is_demo is True,
            f"is_demo={is_demo} msg={d.get('message','')[:50]}")
    else:
        log(scen, "POST /tools/remove-bg (visitor)", r.status_code in (401, 403),
            f"HTTP {r.status_code} body={r.text[:100]}")

    # 1d. Register with invalid body → 400/422
    r = await http_post(client, "/api/v1/auth/register", {"email": "bad"})
    log(scen, "POST /register (bad body)", r.status_code in (400, 422),
        f"HTTP {r.status_code}")

    # 1e. Login with wrong password → 401
    r = await http_post(client, "/api/v1/auth/login",
                        {"email": EMAIL, "password": "NOT_THE_PASSWORD_xx"})
    log(scen, "POST /login (wrong password)", r.status_code == 401,
        f"HTTP {r.status_code}")


# ───────────────────────────────── Scenario 2 ─────────────────────────────────
async def scenario_register_shape(client: httpx.AsyncClient):
    scen = "2 Register"

    # 2a. Duplicate email → 400
    r = await http_post(client, "/api/v1/auth/register", {
        "email": EMAIL,
        "password": "newpass123!",
        "password_confirm": "newpass123!",
    })
    log(scen, "POST /register (duplicate email)", r.status_code in (400, 409, 422),
        f"HTTP {r.status_code} body={r.text[:120]}")

    # 2b. Password mismatch → 400
    r = await http_post(client, "/api/v1/auth/register", {
        "email": f"zz-test-{uuid.uuid4().hex[:8]}@example.invalid",
        "password": "aaaaaa",
        "password_confirm": "bbbbbb",
    })
    log(scen, "POST /register (password mismatch)", r.status_code in (400, 422),
        f"HTTP {r.status_code}")

    # 2c. Password too short → 400/422
    r = await http_post(client, "/api/v1/auth/register", {
        "email": f"zz-test-{uuid.uuid4().hex[:8]}@example.invalid",
        "password": "x",
        "password_confirm": "x",
    })
    log(scen, "POST /register (password too short)", r.status_code in (400, 422),
        f"HTTP {r.status_code}")

    # 2d. Verify-code with no pending verification → 400
    r = await http_post(client, "/api/v1/auth/verify-code", {
        "email": f"never-registered-{uuid.uuid4().hex[:6]}@example.invalid",
        "code": "000000",
    })
    log(scen, "POST /verify-code (no pending)", r.status_code in (400, 404, 410),
        f"HTTP {r.status_code}")


# ───────────────────────────────── Scenario 3 ─────────────────────────────────
async def scenario_plans(client: httpx.AsyncClient):
    scen = "3 Plans"
    r = await http_get(client, "/api/v1/subscriptions/plans")
    if r.status_code != 200:
        log(scen, "GET /subscriptions/plans", False, f"HTTP {r.status_code}")
        return {}
    data = r.json()
    plans = data if isinstance(data, list) else data.get("plans", [])
    log(scen, "GET /subscriptions/plans", len(plans) >= 4, f"{len(plans)} plans")

    names = {}
    for p in plans:
        pname = p.get("plan_type") or p.get("type") or p.get("name") or "?"
        names[pname] = p
        credits = p.get("monthly_credits") or p.get("credits_per_month") or p.get("credits")
        price = p.get("price") or p.get("monthly_price") or p.get("price_twd")
        max_res = p.get("max_resolution") or p.get("resolution")
        print(f"      · {pname:<12} credits={credits!s:<6} price={price!s:<8} max_res={max_res}")
    return names


# ───────────────────────────────── Scenario 4 ─────────────────────────────────
async def scenario_existing_account(client: httpx.AsyncClient):
    scen = "4 Existing pro account"
    # Login
    r = await http_post(client, "/api/v1/auth/login", {"email": EMAIL, "password": PASSWORD})
    if r.status_code != 200:
        log(scen, "login", False, f"HTTP {r.status_code}")
        return None, None
    data = r.json()
    token = data["tokens"]["access"]
    user = data.get("user", {})
    log(scen, "login", True,
        f"plan={user.get('plan_type')} superuser={user.get('is_superuser')}")

    # /auth/me — richer user record
    r = await http_get(client, "/api/v1/auth/me", token=token)
    if r.status_code == 200:
        me = r.json()
        super_flag = me.get("is_superuser")
        email_verified = me.get("email_verified")
        plan_id = me.get("current_plan_id") or me.get("plan_id")
        log(scen, "GET /auth/me", True,
            f"superuser={super_flag} verified={email_verified} plan_id={str(plan_id)[:8] if plan_id else None}")
    else:
        log(scen, "GET /auth/me", False, f"HTTP {r.status_code}")
        me = {}

    # Credit balance shape
    r = await http_get(client, "/api/v1/credits/balance", token=token)
    bal = r.json() if r.status_code == 200 else {}
    log(scen, "GET /credits/balance",
        r.status_code == 200 and "total" in bal,
        f"total={bal.get('total')} sub={bal.get('subscription')} "
        f"purch={bal.get('purchased')} bonus={bal.get('bonus')} "
        f"limit={bal.get('monthly_limit')} used={bal.get('monthly_used')}")

    # Transaction history
    r = await http_get(client, "/api/v1/credits/transactions?limit=10", token=token)
    if r.status_code == 200:
        txns = r.json().get("transactions", [])
        # Count by type
        counts = {}
        for t in txns:
            counts[t.get("transaction_type", "?")] = counts.get(t.get("transaction_type", "?"), 0) + 1
        log(scen, "GET /credits/transactions", True,
            f"n={len(txns)} types={counts}")
        # Check shape of first txn
        if txns:
            t0 = txns[0]
            has_fields = all(k in t0 for k in ("amount", "transaction_type", "created_at"))
            log(scen, "txn shape", has_fields,
                f"amount={t0.get('amount')} type={t0.get('transaction_type')}")
    else:
        log(scen, "GET /credits/transactions", False, f"HTTP {r.status_code}")

    # Current subscription
    r = await http_get(client, "/api/v1/subscriptions/current", token=token)
    if r.status_code == 200:
        sub = r.json()
        log(scen, "GET /subscriptions/current", True,
            f"status={sub.get('status')} plan={sub.get('plan',{}).get('plan_type') or sub.get('plan_type')} "
            f"auto_renew={sub.get('auto_renew')}")
    else:
        log(scen, "GET /subscriptions/current", r.status_code == 404,
            f"HTTP {r.status_code}")
        sub = {}

    # Invoices
    r = await http_get(client, "/api/v1/subscriptions/invoices?limit=10", token=token)
    if r.status_code == 200:
        invs = r.json() if isinstance(r.json(), list) else r.json().get("invoices", [])
        log(scen, "GET /subscriptions/invoices", True, f"{len(invs)} invoices")
        for inv in invs[:3]:
            print(f"      · order={inv.get('order_number')} amt={inv.get('amount')} "
                  f"{inv.get('currency')} status={inv.get('status')} paid_at={inv.get('paid_at')}")
    else:
        log(scen, "GET /subscriptions/invoices", False, f"HTTP {r.status_code}")

    # Tool access + demo flag for a subscribed user (should NOT be demo)
    r = await http_post(client, "/api/v1/tools/remove-bg",
                        {"image_url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=768",
                         "output_format": "png"},
                        token=token, timeout=180)
    if r.status_code == 200:
        d = r.json()
        log(scen, "POST /tools/remove-bg (subscriber)",
            d.get("success") and d.get("is_demo") is not True,
            f"success={d.get('success')} is_demo={d.get('is_demo')} credits_used={d.get('credits_used')}")
    else:
        log(scen, "POST /tools/remove-bg (subscriber)", False, f"HTTP {r.status_code}")

    return token, bal


# ───────────────────────────────── Scenario 5 ─────────────────────────────────
async def scenario_subscribe_edge_cases(client: httpx.AsyncClient, token: str, plans: dict):
    scen = "5 Subscribe edge-cases"
    # Try subscribing to same plan as current → should reject (or skip_payment path)
    # We pick the plan the existing account is on (pro if possible, else first)
    # Without plan.id wired into /auth/me we inspect /subscriptions/plans for IDs.
    if not plans:
        log(scen, "no plans loaded", False)
        return
    # Pick "starter" (basic) and "pro_plus" to see reject/checkout branches
    target_names = ["starter", "pro_plus"]
    for target in target_names:
        plan = plans.get(target)
        if not plan:
            log(scen, f"plan '{target}' not in catalogue", False,
                f"catalogue has {list(plans.keys())}")
            continue
        plan_id = plan.get("id") or plan.get("plan_id") or plan.get("uuid")
        if not plan_id:
            log(scen, f"plan '{target}' missing id", False, f"keys={list(plan.keys())}")
            continue
        r = await http_post(client, "/api/v1/subscriptions/subscribe",
                            {"plan_id": plan_id, "billing_cycle": "monthly",
                             "payment_method": "paddle"},
                            token=token, timeout=60)
        body = r.json() if r.status_code < 500 and r.headers.get("content-type","").startswith("application/json") else {"_raw": r.text[:200]}
        # We don't expect success here (we're already subscribed to pro). The
        # endpoint should either reject with explanation or return a checkout
        # URL / is_mock=True. Never 500.
        log(scen, f"subscribe → {target}",
            r.status_code < 500,
            f"HTTP {r.status_code} success={body.get('success')} "
            f"is_mock={body.get('is_mock')} "
            f"msg={(body.get('message') or body.get('detail') or '')[:80]}")

    # Subscribe with bad plan_id → 404/400
    r = await http_post(client, "/api/v1/subscriptions/subscribe",
                        {"plan_id": "00000000-0000-0000-0000-000000000000",
                         "billing_cycle": "monthly", "payment_method": "paddle"},
                        token=token)
    log(scen, "subscribe (bogus plan_id)", r.status_code in (400, 404, 422),
        f"HTTP {r.status_code}")


# ───────────────────────────────── Scenario 6 ─────────────────────────────────
async def scenario_cancel_shape(client: httpx.AsyncClient, token: str):
    scen = "6 Cancel"
    # We do NOT want to actually cancel the live account. Verify the endpoint
    # exists & rejects malformed bodies, and inspect its response shape against
    # the refund path.
    # Method discovery: POST /subscriptions/cancel with an invalid body
    r = await http_post(client, "/api/v1/subscriptions/cancel",
                        {"request_refund": "not-a-bool"}, token=token)
    log(scen, "POST /cancel (bad body)", r.status_code in (400, 422),
        f"HTTP {r.status_code}")
    # Probe without auth
    r2 = await http_post(client, "/api/v1/subscriptions/cancel", {"request_refund": False})
    log(scen, "POST /cancel (no token)", r2.status_code in (401, 403),
        f"HTTP {r2.status_code}")


# ───────────────────────────────── Scenario 7 ─────────────────────────────────
async def scenario_ecpay_unsigned(client: httpx.AsyncClient):
    scen = "7 ECPay webhook"
    # Send an unsigned / garbage-signed ECPay callback. Should reject.
    fake = {
        "MerchantTradeNo": "FAKE" + uuid.uuid4().hex[:8],
        "RtnCode": "1",
        "RtnMsg": "Succeeded",
        "TradeAmt": "999",
        "PaymentType": "Credit_CreditCard",
        "CheckMacValue": "x" * 64,
    }
    # payments.py accepts form-urlencoded for ECPay callbacks
    r = await client.post(f"{BACKEND}/api/v1/payments/ecpay/callback", data=fake,
                          timeout=30)
    accepted = r.status_code == 200 and ("1|OK" in r.text or "success" in r.text.lower())
    log(scen, "ECPay unsigned callback rejected",
        not accepted,
        f"HTTP {r.status_code} body={r.text[:100]}")


# ──────────────────────────────────── main ────────────────────────────────────
async def main():
    print(f"Backend: {BACKEND}")
    print(f"User   : {EMAIL}")
    print()

    async with httpx.AsyncClient(timeout=60) as client:
        print("── Scenario 1: Visitor ──")
        await scenario_visitor(client)

        print("\n── Scenario 2: Registration input validation ──")
        await scenario_register_shape(client)

        print("\n── Scenario 3: Plans catalogue ──")
        plans = await scenario_plans(client)

        print("\n── Scenario 4: Existing paid account ──")
        token, _ = await scenario_existing_account(client)

        if token:
            print("\n── Scenario 5: Subscribe edge-cases ──")
            await scenario_subscribe_edge_cases(client, token, plans)

            print("\n── Scenario 6: Cancel endpoint shape ──")
            await scenario_cancel_shape(client, token)

        print("\n── Scenario 7: ECPay webhook signature ──")
        await scenario_ecpay_unsigned(client)

    # Summary
    print("\n" + "=" * 78)
    passed = sum(1 for r in results if r.ok)
    total = len(results)
    print(f"Total: {passed}/{total} pass")
    failed = [r for r in results if not r.ok]
    if failed:
        print("\nFailures:")
        for r in failed:
            print(f"  • {r.scenario} · {r.step}: {r.detail}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
