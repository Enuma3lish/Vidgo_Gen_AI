#!/usr/bin/env python3
"""
Script to seed GCP Cloud SQL database with new pricing tiers.
Run this locally to update the GCP database.
"""

import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from decimal import Decimal

# GCP Cloud SQL connection details
DB_USER = "postgres"
DB_PASSWORD = "Vidgo96003146"
DB_HOST = "10.70.0.3"
DB_PORT = "5432"
DB_NAME = "vidgo-new"

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# New Plan data from specification (Monthly Credit System)
NEW_PLAN_DATA = [
    {
        "name": "basic",
        "display_name": "基礎進階版",
        "slug": "basic",
        "plan_type": "basic",
        "price_twd": Decimal("699"),
        "price_usd": Decimal("22"),
        "price_monthly": 699.0,
        "price_yearly": 6990.0,
        "monthly_credits": 7000,
        "weekly_credits": 0,
        "topup_discount_rate": Decimal("0"),
        "max_resolution": "720p",
        "has_watermark": True,
        "priority_queue": False,
        "can_use_effects": False,
        "social_media_batch_posting": False,
        "enterprise_features": False,
        "max_concurrent_generations": 1,
        "allowed_models": ["default"],
        "pollo_limit": 0,
        "goenhance_limit": 0,
        "description": "引流款，讓用戶體驗基本圖文生成，僅限 default 模型"
    },
    {
        "name": "pro",
        "display_name": "專業版",
        "slug": "pro",
        "plan_type": "pro",
        "price_twd": Decimal("999"),
        "price_usd": Decimal("32"),
        "price_monthly": 999.0,
        "price_yearly": 9990.0,
        "monthly_credits": 10000,
        "weekly_credits": 0,
        "topup_discount_rate": Decimal("0.10"),
        "max_resolution": "1080p",
        "has_watermark": False,
        "priority_queue": False,
        "can_use_effects": True,
        "social_media_batch_posting": True,
        "enterprise_features": False,
        "max_concurrent_generations": 3,
        "allowed_models": ["default", "wan_pro", "gemini_pro"],
        "pollo_limit": 50,
        "goenhance_limit": None,
        "description": "主力銷售方案，開放高級模型與社交媒體一鍵批次發布"
    },
    {
        "name": "premium",
        "display_name": "尊榮版",
        "slug": "premium",
        "plan_type": "premium",
        "price_twd": Decimal("1699"),
        "price_usd": Decimal("55"),
        "price_monthly": 1699.0,
        "price_yearly": 16990.0,
        "monthly_credits": 18000,
        "weekly_credits": 0,
        "topup_discount_rate": Decimal("0.15"),
        "max_resolution": "4k",
        "has_watermark": False,
        "priority_queue": True,
        "can_use_effects": True,
        "social_media_batch_posting": True,
        "enterprise_features": False,
        "max_concurrent_generations": 5,
        "allowed_models": ["default", "wan_pro", "gemini_pro"],
        "pollo_limit": 100,
        "goenhance_limit": None,
        "description": "針對重度創作者，包含 Pro 所有功能，外加優先任務處理佇列"
    },
    {
        "name": "enterprise",
        "display_name": "企業旗艦版",
        "slug": "enterprise",
        "plan_type": "enterprise",
        "price_twd": Decimal("15000"),
        "price_usd": Decimal("485"),
        "price_monthly": 15000.0,
        "price_yearly": 150000.0,
        "monthly_credits": 160000,
        "weekly_credits": 0,
        "topup_discount_rate": Decimal("0.20"),
        "max_resolution": "4k",
        "has_watermark": False,
        "priority_queue": True,
        "can_use_effects": True,
        "social_media_batch_posting": True,
        "enterprise_features": True,
        "max_concurrent_generations": 10,
        "allowed_models": ["default", "wan_pro", "gemini_pro", "sora"],
        "pollo_limit": None,
        "goenhance_limit": None,
        "description": "全功能解鎖、專屬企業素材庫、自訂浮水印"
    },
]

async def seed_database():
    """Seed the database with new pricing data."""
    print(f"Connecting to database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    
    # Create engine
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        print("Connected to database successfully!")
        
        # Check if plans table exists
        from sqlalchemy import text
        result = await session.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'plans')"))
        table_exists = result.scalar()
        
        if not table_exists:
            print("ERROR: Plans table doesn't exist. Run migrations first!")
            return
        
        # Clear existing plans
        print("Clearing existing plans...")
        await session.execute(text("DELETE FROM plans"))
        
        # Insert new plans
        print(f"Inserting {len(NEW_PLAN_DATA)} new plans...")
        for plan_data in NEW_PLAN_DATA:
            # Convert Decimal to string for SQL
            plan_data_str = {k: str(v) if isinstance(v, Decimal) else v for k, v in plan_data.items()}
            
            # Build INSERT statement
            columns = ', '.join(plan_data_str.keys())
            placeholders = ', '.join([f':{k}' for k in plan_data_str.keys()])
            query = text(f"INSERT INTO plans ({columns}) VALUES ({placeholders})")
            
            await session.execute(query, plan_data_str)
            print(f"  Inserted plan: {plan_data['name']}")
        
        await session.commit()
        print("Database seeded successfully!")
        
        # Verify
        result = await session.execute(text("SELECT COUNT(*) FROM plans"))
        count = result.scalar()
        print(f"Total plans in database: {count}")

async def main():
    """Main function."""
    print("=" * 60)
    print("GCP Cloud SQL Database Seeding Script")
    print("=" * 60)
    
    try:
        await seed_database()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 60)
    print("Seeding completed!")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)