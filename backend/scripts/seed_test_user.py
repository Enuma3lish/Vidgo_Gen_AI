#!/usr/bin/env python3
"""
Seed users for tests and the admin console.

Two modes:

1) **Default mode** — creates the built-in test user + admin user (idempotent).
   Reads credentials from env vars so real passwords never live in the repo:

     ADMIN_ACCOUNT     (fallback: ADMIN_EMAIL; default: "admin@example.invalid")
     ADMIN_PASSWORD    (no default — refuses to create admin if unset)
     TEST_EMAIL        (default: "test@example.com")
     TEST_PASSWORD     (default: "TestPass123!")
     ALLOW_DEFAULT_ADMIN_PASSWORD  (set to "true" to allow placeholder — dev only)

   Run: `python -m scripts.seed_test_user`

2) **Provision mode** — creates (or updates) a single QA persona with a specific
   paid plan assigned. Mirrors `subscription_service._activate_subscription_directly`
   so we're on the same code path a real mock-checkout would take, just without
   the HTTP round trip. Used by the Phase 0 Playwright test prep.

   Run: `python -m scripts.seed_test_user --plan pro \\
                                          --email qa-pro@vidgo.local \\
                                          --password "$QA_PRO_PASSWORD"`

   Supported --plan values: basic, pro, premium, enterprise (must exist in
   the plans table — run scripts.seed_new_pricing_tiers first).

   On re-run with the same --email, the script UPDATES the existing user's
   plan + credits instead of failing, so it's safe to run repeatedly.
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core import security
from app.models.user import User
from app.models.billing import Plan

# ─── Default-mode env defaults ──────────────────────────────────────────────
TEST_EMAIL = os.environ.get("TEST_EMAIL", "test@example.com")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "TestPass123!")

ADMIN_EMAIL = (
    os.environ.get("ADMIN_ACCOUNT")
    or os.environ.get("ADMIN_EMAIL")
    or "admin@example.invalid"
)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
# Additional admin accounts: comma-separated "email:password" pairs
ADMIN_EXTRA_ACCOUNTS = os.environ.get("ADMIN_EXTRA_ACCOUNTS", "")
ALLOW_DEFAULT = os.environ.get("ALLOW_DEFAULT_ADMIN_PASSWORD", "").lower() == "true"
DEFAULT_DEV_PASSWORD = "ChangeMe_local_dev_only!"


def _parse_extra_admins() -> list[tuple[str, str]]:
    """Parse ADMIN_EXTRA_ACCOUNTS env var into list of (email, password) tuples."""
    if not ADMIN_EXTRA_ACCOUNTS:
        return []
    pairs = []
    for entry in ADMIN_EXTRA_ACCOUNTS.split(","):
        entry = entry.strip()
        if ":" not in entry:
            continue
        email, password = entry.split(":", 1)
        email, password = email.strip(), password.strip()
        if email and password:
            pairs.append((email, password))
    return pairs

VALID_PLAN_TYPES = {"basic", "pro", "premium", "enterprise"}


async def _seed_default_users() -> int:
    """Legacy default-mode: create test + admin users."""
    async with AsyncSessionLocal() as db:
        # Test user
        r = await db.execute(select(User).where(User.email == TEST_EMAIL))
        if r.scalar_one_or_none():
            print(f"Test user already exists: {TEST_EMAIL}")
        else:
            user = User(
                email=TEST_EMAIL,
                username="testuser",
                hashed_password=security.get_password_hash(TEST_PASSWORD),
                is_active=True,
                email_verified=True,
            )
            db.add(user)
            print(f"Created test user: {TEST_EMAIL}")

        # Admin user
        admin_password = ADMIN_PASSWORD
        if not admin_password:
            if ALLOW_DEFAULT:
                admin_password = DEFAULT_DEV_PASSWORD
                print(
                    "WARN: ADMIN_PASSWORD not set — using DEFAULT_DEV_PASSWORD "
                    "(dev only). Set ADMIN_PASSWORD env var for real deploys."
                )
            else:
                print(
                    "ERROR: ADMIN_PASSWORD env var is empty. Refusing to create "
                    "admin with a default password. Either set ADMIN_PASSWORD or "
                    "pass ALLOW_DEFAULT_ADMIN_PASSWORD=true (dev only).",
                    file=sys.stderr,
                )
                await db.commit()
                return 2

        r = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        existing_admin = r.scalar_one_or_none()
        if existing_admin:
            # Ensure is_superuser is set (may have been cleared)
            if not existing_admin.is_superuser:
                existing_admin.is_superuser = True
                existing_admin.is_active = True
                existing_admin.email_verified = True
                print(f"Admin user updated (is_superuser=True): {ADMIN_EMAIL}")
            else:
                print(f"Admin user already exists: {ADMIN_EMAIL}")
        else:
            admin = User(
                email=ADMIN_EMAIL,
                username="admin",
                full_name="Admin",
                hashed_password=security.get_password_hash(admin_password),
                is_active=True,
                is_superuser=True,
                email_verified=True,
            )
            db.add(admin)
            print(f"Created admin user: {ADMIN_EMAIL}")

        # Extra admin accounts (from ADMIN_EXTRA_ACCOUNTS env var)
        extra_admins = _parse_extra_admins()
        for idx, (extra_email, extra_password) in enumerate(extra_admins, start=2):
            r = await db.execute(select(User).where(User.email == extra_email))
            existing = r.scalar_one_or_none()
            if existing:
                if not existing.is_superuser:
                    existing.is_superuser = True
                    existing.is_active = True
                    existing.email_verified = True
                    existing.hashed_password = security.get_password_hash(extra_password)
                    print(f"Extra admin updated (is_superuser=True): {extra_email}")
                else:
                    print(f"Extra admin already exists: {extra_email}")
            else:
                extra_admin = User(
                    email=extra_email,
                    username=f"admin-{idx}",
                    full_name=f"Admin {idx}",
                    hashed_password=security.get_password_hash(extra_password),
                    is_active=True,
                    is_superuser=True,
                    email_verified=True,
                )
                db.add(extra_admin)
                print(f"Created extra admin user: {extra_email}")

        await db.commit()

    print()
    print("Test accounts:")
    print(f"  User:  {TEST_EMAIL} / {TEST_PASSWORD}")
    print(f"  Admin: {ADMIN_EMAIL} / <password from env>")
    for extra_email, _ in extra_admins:
        print(f"  Admin: {extra_email} / <password from env>")
    return 0


async def _provision_persona(
    email: str,
    password: str,
    plan_type: str,
    username: str | None = None,
) -> int:
    """
    Provision a single QA persona with an assigned paid plan.

    Mirrors subscription_service._activate_subscription_directly:
      - user.current_plan_id = plan.id
      - user.plan_started_at = NOW()
      - user.plan_expires_at = NOW() + 30d
      - user.subscription_credits = plan.monthly_credits
      - is_active=True, email_verified=True (skips signup email loop)

    Idempotent: re-running with the same email updates the user instead of
    creating a duplicate, which makes Phase 0 re-runnable after partial failures.
    """
    if plan_type not in VALID_PLAN_TYPES:
        print(
            f"ERROR: --plan must be one of {sorted(VALID_PLAN_TYPES)}, got '{plan_type}'",
            file=sys.stderr,
        )
        return 2
    if not password:
        print("ERROR: --password is required in --plan mode", file=sys.stderr)
        return 2

    async with AsyncSessionLocal() as db:
        # Look up the target plan
        result = await db.execute(
            select(Plan).where(Plan.plan_type == plan_type).limit(1)
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            print(
                f"ERROR: no Plan row found with plan_type='{plan_type}'. "
                f"Run scripts.seed_new_pricing_tiers first.",
                file=sys.stderr,
            )
            return 3

        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=30)

        # Find or create the user
        r = await db.execute(select(User).where(User.email == email))
        user = r.scalar_one_or_none()

        if user is None:
            user = User(
                email=email,
                username=username or email.split("@", 1)[0],
                full_name=f"QA {plan_type.title()}",
                hashed_password=security.get_password_hash(password),
                is_active=True,
                email_verified=True,
                is_superuser=False,
                current_plan_id=plan.id,
                plan_started_at=now,
                plan_expires_at=expires,
                subscription_credits=plan.monthly_credits or 0,
            )
            db.add(user)
            action = "Created"
        else:
            # Idempotent update: refresh password + plan + credits
            user.hashed_password = security.get_password_hash(password)
            user.is_active = True
            user.email_verified = True
            user.current_plan_id = plan.id
            user.plan_started_at = now
            user.plan_expires_at = expires
            user.subscription_credits = plan.monthly_credits or 0
            action = "Updated"

        await db.commit()
        await db.refresh(user)

        print(
            f"{action} persona: email={email} plan={plan_type} "
            f"credits={plan.monthly_credits} expires={expires.date()}"
        )
        print(f"  user_id={user.id}")
        print(f"  plan_id={plan.id} ({plan.name} · {plan.max_resolution})")
        return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="seed_test_user",
        description="Seed test/admin users or provision a QA persona with a paid plan.",
    )
    parser.add_argument(
        "--plan",
        choices=sorted(VALID_PLAN_TYPES),
        help="Provision mode: assign this plan_type to the user at --email.",
    )
    parser.add_argument(
        "--email",
        help="Email for --plan mode. Required if --plan is set.",
    )
    parser.add_argument(
        "--password",
        help="Password for --plan mode (falls back to $QA_PASSWORD env).",
    )
    parser.add_argument(
        "--username",
        help="Username override (default: derived from --email).",
    )
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()

    if args.plan is None:
        return await _seed_default_users()

    if not args.email:
        print("ERROR: --plan requires --email", file=sys.stderr)
        return 2
    password = args.password or os.environ.get("QA_PASSWORD", "")
    return await _provision_persona(
        email=args.email,
        password=password,
        plan_type=args.plan,
        username=args.username,
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
