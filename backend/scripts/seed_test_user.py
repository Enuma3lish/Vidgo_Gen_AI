#!/usr/bin/env python3
"""
Seed the test + admin users used by API content tests and the admin console.

Idempotent — existing rows are left alone (only missing users are created).

Reads credentials from env vars so real passwords never live in the repo:

  ADMIN_ACCOUNT     (fallback: ADMIN_EMAIL; default: "admin@example.invalid")
  ADMIN_PASSWORD    (no default — refuses to create admin if unset in non-dev)
  TEST_EMAIL        (default: "test@example.com")
  TEST_PASSWORD     (default: "TestPass123!")
  ALLOW_DEFAULT_ADMIN_PASSWORD  (set to "true" to allow the placeholder
                                 password below — dev only)

On GCP this script is run as a one-shot Cloud Run Job with
ADMIN_ACCOUNT / ADMIN_PASSWORD wired in from Secret Manager by
gcp/full-deploy.sh.

Run locally: `python -m scripts.seed_test_user`
"""
import asyncio
import os
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core import security
from app.models.user import User

TEST_EMAIL = os.environ.get("TEST_EMAIL", "test@example.com")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "TestPass123!")

ADMIN_EMAIL = (
    os.environ.get("ADMIN_ACCOUNT")
    or os.environ.get("ADMIN_EMAIL")
    or "admin@example.invalid"
)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
ALLOW_DEFAULT = os.environ.get("ALLOW_DEFAULT_ADMIN_PASSWORD", "").lower() == "true"

# Obvious placeholder — never match a real password. Only used if the caller
# explicitly opts in via ALLOW_DEFAULT_ADMIN_PASSWORD=true (dev only).
DEFAULT_DEV_PASSWORD = "ChangeMe_local_dev_only!"


async def seed() -> int:
    async with AsyncSessionLocal() as db:
        # ── Test user ────────────────────────────────────────────────────
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

        # ── Admin user ───────────────────────────────────────────────────
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
                await db.commit()  # still commit the test user if it was new
                return 2

        r = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        if r.scalar_one_or_none():
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

        await db.commit()

    print()
    print("Test accounts:")
    print(f"  User:  {TEST_EMAIL} / {TEST_PASSWORD}")
    print(f"  Admin: {ADMIN_EMAIL} / <password from env>")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(seed()))
