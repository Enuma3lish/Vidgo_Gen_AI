#!/usr/bin/env python3
"""Seed test user + admin user for API content tests. Run: python -m scripts.seed_test_user"""
import asyncio
import sys
sys.path.insert(0, "/app")
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core import security
from app.models.user import User

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "TestPass123!"
ADMIN_EMAIL = "admin@vidgo.ai"
ADMIN_PASSWORD = "Admin1234!"

async def seed():
    async with AsyncSessionLocal() as db:
        # Create test user
        r = await db.execute(select(User).where(User.email == TEST_EMAIL))
        if r.scalar_one_or_none():
            print("Test user already exists:", TEST_EMAIL)
        else:
            user = User(
                email=TEST_EMAIL,
                username="testuser",
                hashed_password=security.get_password_hash(TEST_PASSWORD),
                is_active=True,
                email_verified=True,
            )
            db.add(user)
            print("Created test user:", TEST_EMAIL)

        # Create admin user
        r = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        if r.scalar_one_or_none():
            print("Admin user already exists:", ADMIN_EMAIL)
        else:
            admin = User(
                email=ADMIN_EMAIL,
                username="admin",
                full_name="Admin",
                hashed_password=security.get_password_hash(ADMIN_PASSWORD),
                is_active=True,
                is_superuser=True,
                email_verified=True,
            )
            db.add(admin)
            print("Created admin user:", ADMIN_EMAIL)

        await db.commit()

    print()
    print("Test accounts:")
    print(f"  User:  {TEST_EMAIL} / {TEST_PASSWORD}")
    print(f"  Admin: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")

if __name__ == "__main__":
    asyncio.run(seed())
