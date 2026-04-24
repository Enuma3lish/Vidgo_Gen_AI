#!/usr/bin/env python3
"""
VidGo — Deep subscription LIFECYCLE test.

Uses the existing superuser test account (plan=pro by default). The superuser
bypass on /subscriptions/subscribe activates plans directly without routing
through Paddle/ECPay — documented QA path (backend/app/api/v1/subscriptions.py:271-275).

Steps:
  A. Baseline: /auth/me, /credits/balance, /subscriptions/current, /credits/transactions
  B. Upgrade path: current → basic → pro → premium → enterprise → pro
     At each step verify:
       · subscribe response (success, is_mock, credits_allocated, status)
       · /subscriptions/current reflects the new plan (status, plan_id)
       · /credits/balance total changes (or is preserved) correctly
       · /credits/transactions has a new subscription-type row
       · /subscriptions/invoices updates if a real invoice is created
  C. Cancel without refund: active_until set, credits retained, auto_renew=false
     Then re-subscribe to pro to leave state good.
  D. Same-plan resubscribe rejection
  E. Lower/same plan variants / downgrade semantics
  F. Tool access gating per plan (e.g. resolution gate for upscale scale=4 requires 4k plan)
"""
import asyncio
import json
import os
import sys
from typing import Any, Optional

import httpx

BACKEND = os.environ.get("VIDGO_BACKEND", "https://vidgo-backend-38714015566.asia-east1.run.app")
EMAIL = os.environ["VIDGO_EMAIL"]
PASSWORD = os.environ["VIDGO_PASSWORD"]


class Client:
    def __init__(self):
        self.c = httpx.AsyncClient(timeout=60)
        self.token: Optional[str] = None

    async def login(self):
        r = await self.c.post(f"{BACKEND}/api/v1/auth/login",
                              json={"email": EMAIL, "password": PASSWORD})
        r.raise_for_status()
        self.token = r.json()["tokens"]["access"]

    def h(self):
        return {"Authorization": f"Bearer {self.token}"}

    async def get(self, path, **kw):
        return await self.c.get(f"{BACKEND}{path}", headers=self.h(), **kw)

    async def post(self, path, body=None, **kw):
        return await self.c.post(f"{BACKEND}{path}", json=body or {},
                                 headers=self.h(), **kw)

    async def close(self):
        await self.c.aclose()


async def snapshot(c: Client) -> dict:
    """Take a snapshot of user state."""
    me = (await c.get("/api/v1/auth/me")).json()
    bal = (await c.get("/api/v1/credits/balance")).json()
    cur_r = await c.get("/api/v1/subscriptions/current")
    current_sub = cur_r.json() if cur_r.status_code == 200 else None
    txns_r = await c.get("/api/v1/credits/transactions?limit=5")
    txns = txns_r.json().get("transactions", []) if txns_r.status_code == 200 else []
    invs_r = await c.get("/api/v1/subscriptions/invoices?limit=5")
    invoices = invs_r.json() if invs_r.status_code == 200 else []
    if isinstance(invoices, dict):
        invoices = invoices.get("invoices", invoices.get("items", []))
    return {
        "plan_type": me.get("plan_type"),
        "plan_id": me.get("current_plan_id") or me.get("plan_id"),
        "credits_total": bal.get("total"),
        "credits_sub": bal.get("subscription"),
        "credits_bonus": bal.get("bonus"),
        "credits_purchased": bal.get("purchased"),
        "monthly_used": bal.get("monthly_used"),
        "subscription": current_sub,
        "recent_txns": [
            {"type": t.get("transaction_type"),
             "amount": t.get("amount"),
             "desc": (t.get("description") or "")[:50],
             "created_at": t.get("created_at")}
            for t in txns
        ],
        "invoices_count": len(invoices),
        "latest_invoice": invoices[0] if invoices else None,
    }


def print_snapshot(label: str, s: dict):
    print(f"\n── {label} ──")
    print(f"  plan_type={s['plan_type']} plan_id={str(s['plan_id'])[:8] if s['plan_id'] else None}")
    print(f"  credits: total={s['credits_total']} (sub={s['credits_sub']} purch={s['credits_purchased']} bonus={s['credits_bonus']})")
    print(f"  monthly_used={s['monthly_used']}")
    sub = s["subscription"]
    if sub:
        print(f"  subscription: status={sub.get('status')} auto_renew={sub.get('auto_renew')} "
              f"active_until={sub.get('active_until') or sub.get('current_period_end')}")
    else:
        print("  subscription: (none)")
    print(f"  invoices: {s['invoices_count']}")
    if s["latest_invoice"]:
        inv = s["latest_invoice"]
        print(f"    latest: #{inv.get('order_number') or inv.get('invoice_number')} "
              f"{inv.get('amount')} {inv.get('currency')} status={inv.get('status')}")
    print(f"  last txns:")
    for t in s["recent_txns"][:5]:
        print(f"    {t['type']:<14} {t['amount']:>+8} | {t['desc']}")


async def subscribe(c: Client, plan_id: str, label: str) -> dict:
    print(f"\n>> SUBSCRIBE to {label} ({plan_id[:8]}…)")
    r = await c.post("/api/v1/subscriptions/subscribe", {
        "plan_id": plan_id,
        "billing_cycle": "monthly",
        "payment_method": "paddle",
    }, timeout=60)
    try:
        body = r.json()
    except Exception:
        body = {"_raw": r.text[:200]}
    print(f"   HTTP {r.status_code}  success={body.get('success')} is_mock={body.get('is_mock')} "
          f"status={body.get('status')} credits_allocated={body.get('credits_allocated')}")
    msg = body.get("message") or body.get("detail") or body.get("error")
    if msg:
        print(f"   msg: {msg[:120]}")
    return body


async def cancel(c: Client, request_refund: bool) -> dict:
    print(f"\n>> CANCEL  request_refund={request_refund}")
    r = await c.post("/api/v1/subscriptions/cancel", {"request_refund": request_refund})
    try:
        body = r.json()
    except Exception:
        body = {"_raw": r.text[:200]}
    print(f"   HTTP {r.status_code}  success={body.get('success')} refund_processed={body.get('refund_processed')} "
          f"refund_amount={body.get('refund_amount')} active_until={body.get('active_until')}")
    return body


async def main():
    c = Client()
    await c.login()

    # Load plan catalogue → id map
    plans = (await c.get("/api/v1/subscriptions/plans")).json()
    plan_by_name = {p["name"]: p["id"] for p in plans}
    print(f"Available plans: {list(plan_by_name.keys())}")

    # A. Baseline
    baseline = await snapshot(c)
    print_snapshot("A. BASELINE", baseline)
    original_plan = baseline["plan_type"]
    print(f"\n[NB] baseline plan is '{original_plan}'. Will restore to this at the end.")

    # B. Walk the upgrade path: basic → pro → premium → enterprise → back to original
    walk = ["basic", "pro", "premium", "enterprise"]
    if original_plan in walk:
        walk = [p for p in walk if p != original_plan] + [original_plan]

    for plan_name in walk:
        await subscribe(c, plan_by_name[plan_name], plan_name)
        # Give the DB a beat to settle
        await asyncio.sleep(1)
        s = await snapshot(c)
        print_snapshot(f"state after subscribe({plan_name})", s)

    # C. Same-plan resubscribe rejection test
    print("\n── C. SAME-PLAN RE-SUBSCRIBE REJECTION ──")
    current = await snapshot(c)
    same_plan = current["plan_type"] or "pro"
    body = await subscribe(c, plan_by_name[same_plan], f"{same_plan} (SAME)")
    same_plan_rejected = body.get("success") is False or "already" in (body.get("message") or body.get("error") or "").lower()
    print(f"   same-plan rejected? {same_plan_rejected}")

    # D. Cancel without refund
    print("\n── D. CANCEL (no refund) ──")
    before_cancel = await snapshot(c)
    cancel_body = await cancel(c, request_refund=False)
    await asyncio.sleep(1)
    after_cancel = await snapshot(c)
    print_snapshot("state after cancel", after_cancel)

    # Did credits survive?
    credits_delta = (after_cancel["credits_total"] or 0) - (before_cancel["credits_total"] or 0)
    print(f"\n   credits delta across cancel: {credits_delta}")
    if cancel_body.get("success"):
        print(f"   → expected: credits preserved, auto_renew=false, active_until={cancel_body.get('active_until')}")

    # Re-subscribe to restore original plan so we leave things clean
    if after_cancel["plan_type"] != original_plan and original_plan in plan_by_name:
        print(f"\n── E. RESTORE to original plan '{original_plan}' ──")
        await subscribe(c, plan_by_name[original_plan], original_plan)
        await asyncio.sleep(1)
        final = await snapshot(c)
        print_snapshot("FINAL state", final)

    # F. Quick tool-access sanity: hit a 4k-gated upscale at scale=4 and see if the
    #    plan gate enforces (expect success only on premium/enterprise)
    print("\n── F. RESOLUTION GATE (upscale scale=4) ──")
    r = await c.post("/api/v1/tools/upscale", {
        "image_url": "https://storage.googleapis.com/vidgo-media-vidgo-ai/generated/image/e5f0b67fb84e.png",
        "scale": 4,
    }, timeout=180)
    body = r.json() if r.status_code < 500 else {"_raw": r.text[:200]}
    print(f"   HTTP {r.status_code} success={body.get('success')} "
          f"message={(body.get('message') or body.get('detail') or '')[:100]}")

    await c.close()


if __name__ == "__main__":
    asyncio.run(main())
