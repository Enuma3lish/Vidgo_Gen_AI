#!/usr/bin/env python3
"""
Create developer staff account + clear Material DB + flush Redis.

Usage (inside container or with correct DATABASE_URL/REDIS_URL):
    python -m scripts.setup_dev_staff
"""
import asyncio
import sys
sys.path.insert(0, "/app")

from sqlalchemy import select, delete
from app.core.database import AsyncSessionLocal
from app.core import security
from app.models.user import User
from app.models.material import Material

DEV_EMAIL = "qaz0978005418@gmail.com"
DEV_PASSWORD = "qaz129946858"


async def setup():
    # ── 1. Create or update developer staff account ──
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == DEV_EMAIL))
        existing = result.scalar_one_or_none()

        if existing:
            existing.hashed_password = security.get_password_hash(DEV_PASSWORD)
            existing.is_active = True
            existing.is_superuser = True
            existing.email_verified = True
            print(f"[✓] Updated existing user to admin: {DEV_EMAIL}")
        else:
            user = User(
                email=DEV_EMAIL,
                username="dev-staff",
                full_name="Developer Staff",
                hashed_password=security.get_password_hash(DEV_PASSWORD),
                is_active=True,
                is_superuser=True,
                email_verified=True,
            )
            db.add(user)
            print(f"[✓] Created developer staff admin: {DEV_EMAIL}")

        await db.commit()

    # ── 2. Clear all materials ──
    async with AsyncSessionLocal() as db:
        result = await db.execute(delete(Material))
        count = result.rowcount
        await db.commit()
        print(f"[✓] Deleted {count} materials from database")

    # ── 3. Flush Redis ──
    try:
        import redis.asyncio as aioredis
        from app.core.config import get_settings
        settings = get_settings()
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.flushdb()
        await r.aclose()
        print("[✓] Redis flushed (all keys deleted)")
    except Exception as e:
        print(f"[!] Redis flush failed: {e}")

    print()
    print("Developer staff account:")
    print(f"  Email:    {DEV_EMAIL}")
    print(f"  Password: {DEV_PASSWORD}")
    print(f"  Role:     Administrator (is_superuser=True)")
    print()
    print("Material DB: emptied")
    print("Redis cache: flushed")


if __name__ == "__main__":
    asyncio.run(setup())
