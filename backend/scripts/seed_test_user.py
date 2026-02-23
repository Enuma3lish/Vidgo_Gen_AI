#!/usr/bin/env python3
"""Seed test user for API content tests. Run: python -m scripts.seed_test_user"""
import asyncio
import sys
sys.path.insert(0, "/app")
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core import security
from app.models.user import User

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "TestPass123!"

async def seed():
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(User).where(User.email == TEST_EMAIL))
        if r.scalar_one_or_none():
            print("Test user already exists:", TEST_EMAIL)
            return
        user = User(
            email=TEST_EMAIL,
            username="testuser",
            hashed_password=security.get_password_hash(TEST_PASSWORD),
            is_active=True,
            email_verified=True,
        )
        db.add(user)
        await db.commit()
        print("Created test user:", TEST_EMAIL)

if __name__ == "__main__":
    asyncio.run(seed())
