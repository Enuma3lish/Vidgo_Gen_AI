#!/usr/bin/env python3
"""Production promotion-code smoke test.

This script is intended to run inside the backend Cloud Run image as a QA job.
It exercises the public API for registration and verification while using direct
Postgres/Redis access only to activate the promoter account and set a known
verification code for the referred account.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any

import asyncpg
import httpx
import redis.asyncio as redis


class CheckFailed(RuntimeError):
    pass


def require(condition: bool, label: str, detail: str = "") -> None:
    if not condition:
        raise CheckFailed(f"{label}: {detail}" if detail else label)
    print(f"OK  {label}" + (f" -- {detail}" if detail else ""), flush=True)


def access_token(payload: dict[str, Any]) -> str | None:
    tokens = payload.get("tokens") or {}
    return tokens.get("access") or payload.get("access_token")


def postgres_dsn() -> str:
    return os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def json_or_text(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text


async def main() -> int:
    backend = os.getenv("BACKEND_URL", "https://api.vidgo.co").rstrip("/")
    admin_email = os.environ["ADMIN_ACCOUNT"]
    admin_password = os.environ["ADMIN_PASSWORD"]

    timestamp = int(time.time())
    suffix = str(timestamp)[-8:]
    promo_code = f"QAP{suffix}"
    password = "QaPromoTest1234!"
    promoter_email = f"vidgo.qa.promo.promoter+{suffix}@vidgo.ai"
    member_email = f"vidgo.qa.promo.member+{suffix}@vidgo.ai"
    invalid_email = f"vidgo.qa.promo.invalid+{suffix}@vidgo.ai"
    known_code = "135790"

    conn = await asyncpg.connect(postgres_dsn(), timeout=20)
    redis_client = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

    try:
        async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
            health = await client.get(f"{backend}/health")
            require(
                health.status_code == 200 and health.json().get("status") == "ok",
                "Production health endpoint",
                f"HTTP {health.status_code}",
            )

            login = await client.post(
                f"{backend}/api/v1/auth/login",
                json={"email": admin_email, "password": admin_password},
            )
            login_body = await json_or_text(login)
            require(login.status_code == 200, "Admin login succeeds", f"HTTP {login.status_code}")
            admin_token = access_token(login_body)
            require(bool(admin_token), "Admin access token returned")
            admin_headers = {"Authorization": f"Bearer {admin_token}"}

            dashboard_before_response = await client.get(
                f"{backend}/api/v1/admin/stats/dashboard",
                headers=admin_headers,
            )
            dashboard_before = await json_or_text(dashboard_before_response)
            require(
                dashboard_before_response.status_code == 200,
                "Admin dashboard responds",
                f"HTTP {dashboard_before_response.status_code}",
            )
            promotions_before = dashboard_before.get("promotions") or {}
            require(
                {"accounts", "registrations", "referred_users"}.issubset(promotions_before.keys()),
                "Dashboard exposes promotion stats",
                str(promotions_before),
            )
            before_accounts = int(promotions_before.get("accounts") or 0)
            before_registrations = int(promotions_before.get("registrations") or 0)

            users_response = await client.get(
                f"{backend}/api/v1/admin/users",
                params={"page": 1, "per_page": 1},
                headers=admin_headers,
            )
            users_payload = await json_or_text(users_response)
            require(users_response.status_code == 200, "Admin users list responds", f"HTTP {users_response.status_code}")
            users = users_payload.get("users") or []
            require(bool(users), "Admin users list has rows")
            require(
                {"referral_code", "referral_count", "is_promotion_account"}.issubset(users[0].keys()),
                "Admin users expose promotion columns",
            )

            invalid_register = await client.post(
                f"{backend}/api/v1/auth/register",
                json={
                    "email": invalid_email,
                    "username": f"qa_invalid_{suffix}",
                    "full_name": "QA Invalid Promotion",
                    "password": password,
                    "password_confirm": password,
                    "referral_code": f"NO{suffix}",
                },
            )
            invalid_body = await json_or_text(invalid_register)
            require(
                invalid_register.status_code == 400 and invalid_body.get("detail") == "Invalid promotion code",
                "Invalid promotion code is rejected",
                f"HTTP {invalid_register.status_code}",
            )

            promoter_register = await client.post(
                f"{backend}/api/v1/auth/register",
                json={
                    "email": promoter_email,
                    "username": f"qa_promoter_{suffix}",
                    "full_name": "QA Promotion Owner",
                    "password": password,
                    "password_confirm": password,
                },
            )
            require(promoter_register.status_code == 200, "Create promoter account", f"HTTP {promoter_register.status_code}")

            promoter_row = await conn.fetchrow(
                """
                UPDATE users
                   SET is_active = true,
                       email_verified = true,
                       email_verification_token = NULL,
                       email_verification_sent_at = NULL
                 WHERE email = $1
                 RETURNING id::text, referral_count
                """,
                promoter_email,
            )
            require(promoter_row is not None, "Promoter activated for QA")
            promoter_id = promoter_row["id"]
            promoter_count_before = int(promoter_row["referral_count"] or 0)

            assign = await client.post(
                f"{backend}/api/v1/admin/users/{promoter_id}/promotion-code",
                json={"promotion_code": promo_code.lower()},
                headers=admin_headers,
            )
            assign_body = await json_or_text(assign)
            require(
                assign.status_code == 200 and assign_body.get("promotion_code") == promo_code,
                "Admin assigns promotion code",
                f"HTTP {assign.status_code}",
            )

            promoter_detail = await client.get(
                f"{backend}/api/v1/admin/users/{promoter_id}",
                headers=admin_headers,
            )
            promoter_detail_body = await json_or_text(promoter_detail)
            require(
                promoter_detail.status_code == 200,
                "Admin can view promotion account detail",
                f"HTTP {promoter_detail.status_code}",
            )
            promoter_user = promoter_detail_body.get("user") or {}
            require(
                promoter_user.get("referral_code") == promo_code and promoter_user.get("is_promotion_account") is True,
                "Admin detail shows assigned code",
            )

            member_register = await client.post(
                f"{backend}/api/v1/auth/register",
                json={
                    "email": member_email,
                    "username": f"qa_member_{suffix}",
                    "full_name": "QA Promotion Member",
                    "password": password,
                    "password_confirm": password,
                    "referral_code": promo_code.lower(),
                },
            )
            require(member_register.status_code == 200, "Register user with promotion code", f"HTTP {member_register.status_code}")

            member_row = await conn.fetchrow(
                """
                SELECT id::text,
                       bonus_credits,
                       referred_by_id::text AS referred_by_id,
                       email_verified,
                       is_active
                  FROM users
                 WHERE email = $1
                """,
                member_email,
            )
            require(member_row is not None, "Promoted member row exists")
            member_id = member_row["id"]
            require(member_row["referred_by_id"] == promoter_id, "Member linked to promoter before verification")
            require(int(member_row["bonus_credits"] or 0) == 40, "Member starts with base 40 credits")

            await redis_client.setex(
                f"email_verify:{member_email}",
                15 * 60,
                json.dumps(
                    {
                        "code_hash": hash_code(known_code),
                        "attempts": 0,
                        "user_id": member_id,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                ),
            )

            verify = await client.post(
                f"{backend}/api/v1/auth/verify-code",
                json={"email": member_email, "code": known_code},
            )
            verify_body = await json_or_text(verify)
            require(
                verify.status_code == 200 and bool(access_token(verify_body)),
                "Verify promoted user through public API",
                f"HTTP {verify.status_code}",
            )
            member_headers = {"Authorization": f"Bearer {access_token(verify_body)}"}

            balance_response = await client.get(
                f"{backend}/api/v1/credits/balance",
                headers=member_headers,
            )
            balance = await json_or_text(balance_response)
            require(balance_response.status_code == 200, "Promoted user credit balance responds", f"HTTP {balance_response.status_code}")
            require(
                int(balance.get("bonus") or 0) == 80 and int(balance.get("total") or 0) == 80,
                "Promoted user receives 40 + 40 credits",
                str(balance),
            )

            member_after = await conn.fetchrow(
                """
                SELECT bonus_credits,
                       subscription_credits,
                       purchased_credits,
                       email_verified,
                       is_active,
                       referred_by_id::text AS referred_by_id
                  FROM users
                 WHERE id = $1::uuid
                """,
                member_id,
            )
            promoter_after = await conn.fetchrow(
                "SELECT referral_code, referral_count, bonus_credits FROM users WHERE id = $1::uuid",
                promoter_id,
            )
            welcome_tx_count = await conn.fetchval(
                """
                SELECT count(*)
                  FROM credit_transactions
                 WHERE user_id = $1::uuid
                   AND transaction_type = 'bonus'
                   AND description = 'Welcome bonus for using a promotion code'
                """,
                member_id,
            )
            require(member_after["email_verified"] and member_after["is_active"], "Promoted user is active and verified")
            require(int(member_after["bonus_credits"] or 0) == 80, "Database stores 80 bonus credits")
            require(
                int(promoter_after["referral_count"] or 0) == promoter_count_before + 1,
                "Promotion account counter increments by 1",
                f"{promoter_count_before} -> {promoter_after['referral_count']}",
            )
            require(int(welcome_tx_count or 0) == 1, "Welcome promotion transaction recorded")

            dashboard_after_response = await client.get(
                f"{backend}/api/v1/admin/stats/dashboard",
                headers=admin_headers,
            )
            dashboard_after = await json_or_text(dashboard_after_response)
            require(dashboard_after_response.status_code == 200, "Admin dashboard still responds after signup")
            promotions_after = dashboard_after.get("promotions") or {}
            require(
                int(promotions_after.get("accounts") or 0) >= before_accounts + 1,
                "Dashboard promotion accounts count includes assigned account",
                f"{before_accounts} -> {promotions_after.get('accounts')}",
            )
            require(
                int(promotions_after.get("registrations") or 0) >= before_registrations + 1,
                "Dashboard promotion registrations count increments",
                f"{before_registrations} -> {promotions_after.get('registrations')}",
            )

            promoter_detail_after = await client.get(
                f"{backend}/api/v1/admin/users/{promoter_id}",
                headers=admin_headers,
            )
            promoter_detail_after_body = await json_or_text(promoter_detail_after)
            require(promoter_detail_after.status_code == 200, "Admin can view promoter after referral")
            require(
                int((promoter_detail_after_body.get("user") or {}).get("referral_count") or 0)
                == promoter_count_before + 1,
                "Admin detail shows updated promotion uses",
            )

            print(
                "SUMMARY "
                + json.dumps(
                    {
                        "dashboard_promotions": promotions_after,
                        "member_total_credits": balance.get("total"),
                        "promotion_code": promo_code,
                        "promoter_id": promoter_id,
                        "promoter_referral_count": promoter_after["referral_count"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    finally:
        await redis_client.aclose()
        await conn.close()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except CheckFailed as exc:
        print(f"FAIL {exc}", flush=True)
        raise SystemExit(1)
