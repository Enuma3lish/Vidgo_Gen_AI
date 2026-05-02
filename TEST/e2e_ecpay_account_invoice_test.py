#!/usr/bin/env python3
"""Deployed account + ECPay + invoice refund lifecycle test.

This test intentionally uses a fresh QA account and a signed simulated ECPay
callback so we can verify backend state changes without entering card details.
It still exercises the production callback signature path and invoice service.
"""
from __future__ import annotations

import asyncio
import base64
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Any

import asyncpg
import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.ecpay.client import ECPayClient  # noqa: E402


BACKEND = os.getenv("VIDGO_BACKEND_URL", os.getenv("VIDGO_BACKEND", "https://vidgo-backend-r2laip67ma-de.a.run.app")).rstrip("/")
PROJECT_ID = os.getenv("PROJECT_ID", "vidgo-ai")
REGION = os.getenv("REGION", "asia-east1")
PASSWORD = os.getenv("VIDGO_E2E_PASSWORD", "QaPayTest1234!")
ACTIVATION_JOB = os.getenv("VIDGO_QA_ACTIVATION_JOB", "vidgo-qa-activate-user")


class CheckFailed(RuntimeError):
    pass


def ok(label: str, detail: str = "") -> None:
    print(f"OK  {label}" + (f" — {detail}" if detail else ""))


def fail(label: str, detail: str = "") -> None:
    raise CheckFailed(f"{label}: {detail}" if detail else label)


def require(condition: bool, label: str, detail: str = "") -> None:
    if not condition:
        fail(label, detail)
    ok(label, detail)


def secret(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    result = subprocess.run(
        ["gcloud", "secrets", "versions", "access", "latest", f"--secret={name}", f"--project={PROJECT_ID}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def database_dsn() -> str:
    return secret("DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://", 1)


async def activate_registered_user(email: str) -> str:
    dsn = database_dsn()
    try:
        return await activate_registered_user_direct(email, dsn)
    except (OSError, TimeoutError, asyncpg.PostgresError) as exc:
        ok("Direct DB activation unavailable, using Cloud Run job", exc.__class__.__name__)
        activate_registered_user_via_job(email)
        return "activated-via-cloud-run-job"


async def activate_registered_user_direct(email: str, dsn: str) -> str:
    conn = await asyncpg.connect(dsn, timeout=5)
    try:
        user_id = await conn.fetchval(
            """
            UPDATE users
               SET is_active = true,
                   email_verified = true,
                   email_verification_token = NULL,
                   email_verification_sent_at = NULL
             WHERE email = $1
             RETURNING id::text
            """,
            email,
        )
        if not user_id:
            fail("Activate registered account", "user row not found")
        return user_id
    finally:
        await conn.close()


def backend_image() -> str:
    result = subprocess.run(
        [
            "gcloud", "run", "services", "describe", "vidgo-backend",
            f"--project={PROJECT_ID}", f"--region={REGION}",
            "--format=value(spec.template.spec.containers[0].image)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    image = result.stdout.strip()
    if not image:
        fail("Find backend image", "Cloud Run service did not report an image")
    return image


def ensure_activation_job(image: str) -> None:
    runner = "import base64;import os;exec(base64.b64decode(os.environ['QA_CODE_B64']).decode())"
    describe = subprocess.run(
        ["gcloud", "run", "jobs", "describe", ACTIVATION_JOB, f"--project={PROJECT_ID}", f"--region={REGION}"],
        capture_output=True,
        text=True,
    )
    base_args = [
        "--image", image,
        "--service-account", f"vidgo-backend@{PROJECT_ID}.iam.gserviceaccount.com",
        "--vpc-connector", f"projects/{PROJECT_ID}/locations/{REGION}/connectors/vidgo-connector",
        "--vpc-egress", "private-ranges-only",
        "--set-secrets", "DATABASE_URL=DATABASE_URL:latest",
        "--command", "python",
        "--args", f"-c,{runner}",
        "--tasks", "1",
        "--task-timeout", "300s",
        "--memory", "512Mi",
    ]
    if describe.returncode == 0:
        subprocess.run(
            ["gcloud", "run", "jobs", "update", ACTIVATION_JOB, f"--project={PROJECT_ID}", f"--region={REGION}", *base_args],
            check=True,
            capture_output=True,
            text=True,
        )
        return

    subprocess.run(
        ["gcloud", "run", "jobs", "create", ACTIVATION_JOB, f"--project={PROJECT_ID}", f"--region={REGION}", *base_args],
        check=True,
        capture_output=True,
        text=True,
    )


def activate_registered_user_via_job(email: str) -> None:
    code = """
import asyncio
import os
import asyncpg

async def main():
    dsn = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://', 1)
    conn = await asyncpg.connect(dsn)
    try:
        user_id = await conn.fetchval('''
            UPDATE users
               SET is_active = true,
                   email_verified = true,
                   email_verification_token = NULL,
                   email_verification_sent_at = NULL
             WHERE email = $1
             RETURNING id::text
        ''', os.environ['QA_EMAIL'])
        if not user_id:
            raise SystemExit('registered user not found')
        print('activated', user_id)
    finally:
        await conn.close()

asyncio.run(main())
"""
    encoded = base64.b64encode(code.encode()).decode()
    image = backend_image()
    ensure_activation_job(image)
    subprocess.run(
        [
            "gcloud", "run", "jobs", "execute", ACTIVATION_JOB,
            f"--project={PROJECT_ID}", f"--region={REGION}",
            "--wait",
            "--update-env-vars", f"QA_EMAIL={email},QA_CODE_B64={encoded}",
        ],
        check=True,
    )


async def json_or_text(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text


async def main() -> int:
    timestamp = int(time.time())
    email = os.getenv("VIDGO_E2E_EMAIL", f"vidgo.qa.paytest+{timestamp}@vidgo.ai")
    username = f"qa_pay_{timestamp}"

    ecpay_client = ECPayClient(
        merchant_id=secret("ECPAY_MERCHANT_ID"),
        hash_key=secret("ECPAY_HASH_KEY"),
        hash_iv=secret("ECPAY_HASH_IV"),
        payment_url="",
    )

    async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
        register_payload = {
            "email": email,
            "username": username,
            "full_name": "VidGo QA Payment Test",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        }
        register = await client.post(f"{BACKEND}/api/v1/auth/register", json=register_payload)
        register_body = await json_or_text(register)
        require(register.status_code in (200, 409), "Create account endpoint responds", f"HTTP {register.status_code}")
        if register.status_code == 409:
            fail("Create account uses fresh email", str(register_body)[:160])

        blocked_login = await client.post(f"{BACKEND}/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        require(blocked_login.status_code == 403, "Unverified account cannot login", f"HTTP {blocked_login.status_code}")

        user_id = await activate_registered_user(email)
        ok("Registered account verified for QA", user_id)

        login = await client.post(f"{BACKEND}/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        login_body = login.json()
        require(login.status_code == 200 and "tokens" in login_body, "Verified account can login", f"HTTP {login.status_code}")
        token = login_body["tokens"]["access"]
        headers = {"Authorization": f"Bearer {token}"}

        plans = (await client.get(f"{BACKEND}/api/v1/subscriptions/plans")).json()
        paid_plans = [plan for plan in plans if float(plan.get("price_monthly") or 0) > 0]
        require(bool(paid_plans), "Paid plans are available")
        plan = next((p for p in paid_plans if p.get("name") == "starter"), paid_plans[0])
        expected_credits = int(plan.get("monthly_credits") or 0)

        subscribe = await client.post(
            f"{BACKEND}/api/v1/subscriptions/subscribe",
            json={"plan_id": plan["id"], "billing_cycle": "monthly", "payment_method": "ecpay"},
            headers=headers,
        )
        subscribe_body = subscribe.json()
        require(subscribe.status_code == 200 and subscribe_body.get("success"), "ECPay checkout created", f"HTTP {subscribe.status_code}")
        require(subscribe_body.get("payment_method") == "ecpay" and subscribe_body.get("ecpay_form"), "ECPay form returned")

        form = subscribe_body["ecpay_form"]
        params = form["params"]
        order_number = subscribe_body["order_number"]
        require(order_number and order_number.isalnum() and len(order_number) <= 20, "ECPay order number valid", order_number)
        require(params.get("CheckMacValue"), "ECPay checkout CheckMacValue present")
        require(str(params.get("ReturnURL", "")).endswith("/api/v1/payments/ecpay/callback"), "ECPay ReturnURL points to callback")

        bad_callback = {"MerchantID": params["MerchantID"], "MerchantTradeNo": order_number, "RtnCode": "1"}
        bad = await client.post(f"{BACKEND}/api/v1/payments/ecpay/callback", data=bad_callback)
        require(bad.text == "0|SignatureError", "Unsigned ECPay callback rejected", bad.text)

        callback = {
            "MerchantID": params["MerchantID"],
            "MerchantTradeNo": order_number,
            "RtnCode": "1",
            "RtnMsg": "Succeeded",
            "TradeNo": f"QA{timestamp}",
            "TradeAmt": str(params["TotalAmount"]),
            "PaymentDate": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            "PaymentType": "Credit_CreditCard",
            "PaymentTypeChargeFee": "0",
            "TradeDate": str(params["MerchantTradeDate"]),
            "SimulatePaid": "0",
        }
        callback["CheckMacValue"] = ecpay_client.generate_check_mac_value(callback)
        paid = await client.post(f"{BACKEND}/api/v1/payments/ecpay/callback", data=callback)
        require(paid.text == "1|OK", "Signed ECPay success callback accepted", paid.text)

        await asyncio.sleep(3)

        status = (await client.get(f"{BACKEND}/api/v1/subscriptions/status", headers=headers)).json()
        require(status.get("has_subscription") and status.get("status") == "active", "Payment activates subscription", str(status.get("status")))

        balance = (await client.get(f"{BACKEND}/api/v1/credits/balance", headers=headers)).json()
        require(int(balance.get("subscription") or 0) == expected_credits, "Payment allocates plan credits", f"subscription={balance.get('subscription')}")

        einvoices = (await client.get(f"{BACKEND}/api/v1/einvoices", headers=headers)).json()
        invoices = einvoices.get("invoices", [])
        require(bool(invoices), "Invoice service created an invoice", f"count={len(invoices)}")
        invoice = invoices[0]
        require(invoice.get("status") in ("issued", "uploaded"), "Invoice is active after payment", str(invoice.get("status")))
        invoice_id = invoice["id"]

        cancel = await client.post(
            f"{BACKEND}/api/v1/subscriptions/cancel",
            json={"request_refund": True},
            headers=headers,
        )
        cancel_body = cancel.json()
        require(cancel.status_code == 200 and cancel_body.get("success"), "Cancel with refund succeeds", f"HTTP {cancel.status_code}")
        require(cancel_body.get("refund_processed") is True, "Refund path processed")
        require(cancel_body.get("invoice_voided") is True, "Invoice voided on refund cancel", str(cancel_body))

        post_cancel_balance = (await client.get(f"{BACKEND}/api/v1/credits/balance", headers=headers)).json()
        require(int(post_cancel_balance.get("total") or 0) == 0, "Credits reset to zero after refund cancel", str(post_cancel_balance))

        invoice_detail = (await client.get(f"{BACKEND}/api/v1/einvoices/{invoice_id}", headers=headers)).json()
        require(invoice_detail.get("invoice", {}).get("status") == "voided", "Invoice status is voided after cancel")

    print("\nECPay/account/invoice lifecycle passed")
    print(f"Test account: {email}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except CheckFailed as exc:
        print(f"FAIL {exc}")
        raise SystemExit(1)