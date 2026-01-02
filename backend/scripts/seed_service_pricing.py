"""
Seed script for Service Pricing.

This script seeds the service_pricing table with default pricing for all services.
Run with: python -m scripts.seed_service_pricing
"""
import asyncio
import sys
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, "/app")

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.billing import ServicePricing, Plan, CreditPackage


# Service pricing data (with white-labeled VidGo names)
SERVICE_PRICING_DATA = [
    # Leonardo Services (All Tiers)
    {
        "service_type": "leonardo_video_720p",
        "display_name": "VidGo Video 720p",
        "credit_cost": 5,
        "api_cost_usd": Decimal("0.05"),
        "resolution": "720p",
        "max_duration": 8,
        "subscribers_only": False,
        "min_plan": None,
        "description": "Standard quality video generation"
    },
    {
        "service_type": "leonardo_video_1080p",
        "display_name": "VidGo Video 1080p",
        "credit_cost": 8,
        "api_cost_usd": Decimal("0.08"),
        "resolution": "1080p",
        "max_duration": 8,
        "subscribers_only": False,
        "min_plan": "starter",
        "description": "High quality video generation"
    },
    {
        "service_type": "leonardo_video_4k",
        "display_name": "VidGo Video 4K",
        "credit_cost": 12,
        "api_cost_usd": Decimal("0.12"),
        "resolution": "4k",
        "max_duration": 8,
        "subscribers_only": False,
        "min_plan": "pro",
        "description": "4K video generation"
    },
    {
        "service_type": "leonardo_image_512",
        "display_name": "VidGo Image 512px",
        "credit_cost": 2,
        "api_cost_usd": Decimal("0.015"),
        "resolution": "512x512",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": None,
        "description": "Small image generation"
    },
    {
        "service_type": "leonardo_image_1024",
        "display_name": "VidGo Image 1024px",
        "credit_cost": 3,
        "api_cost_usd": Decimal("0.025"),
        "resolution": "1024x1024",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": None,
        "description": "Large image generation"
    },
    # VidGo Effects (GoEnhance - Subscribers Only)
    {
        "service_type": "vidgo_style",
        "display_name": "VidGo Style Effects",
        "credit_cost": 8,
        "api_cost_usd": Decimal("0.15"),
        "resolution": None,
        "max_duration": None,
        "subscribers_only": True,
        "min_plan": "starter",
        "description": "AI style transformation (subscribers only)"
    },
    {
        "service_type": "vidgo_hd_enhance",
        "display_name": "VidGo HD Enhance",
        "credit_cost": 10,
        "api_cost_usd": Decimal("0.20"),
        "resolution": "4k",
        "max_duration": None,
        "subscribers_only": True,
        "min_plan": "starter",
        "description": "4K upscaling (subscribers only)"
    },
    {
        "service_type": "vidgo_video_pro",
        "display_name": "VidGo Video Pro",
        "credit_cost": 12,
        "api_cost_usd": Decimal("0.25"),
        "resolution": None,
        "max_duration": None,
        "subscribers_only": True,
        "min_plan": "pro",
        "description": "Video enhancement (Pro/Pro+ only)"
    },
    # Pollo Services (Future)
    {
        "service_type": "pollo_basic",
        "display_name": "VidGo Advanced Basic",
        "credit_cost": 20,
        "api_cost_usd": Decimal("0.60"),
        "resolution": "720p",
        "max_duration": 5,
        "subscribers_only": False,
        "min_plan": "starter",
        "description": "Advanced AI video generation (future)"
    },
    {
        "service_type": "pollo_premium",
        "display_name": "VidGo Advanced Premium",
        "credit_cost": 30,
        "api_cost_usd": Decimal("0.80"),
        "resolution": "1080p",
        "max_duration": 10,
        "subscribers_only": False,
        "min_plan": "pro",
        "description": "Premium advanced video generation (future)"
    },
    # Runway (Fallback - Internal Use)
    {
        "service_type": "runway_720p",
        "display_name": "Runway Fallback 720p",
        "credit_cost": 15,
        "api_cost_usd": Decimal("0.50"),
        "resolution": "720p",
        "max_duration": 8,
        "subscribers_only": False,
        "min_plan": None,
        "description": "Fallback video generation via Runway (internal)"
    },
]

# Plan data (Weekly Credit System)
PLAN_DATA = [
    {
        "name": "demo",
        "display_name": "Demo",
        "slug": "demo",
        "plan_type": "free",
        "price_twd": Decimal("0"),
        "price_usd": Decimal("0"),
        "monthly_credits": 0,
        "weekly_credits": 0,  # Demo users get 2 one-time credits on signup
        "topup_discount_rate": Decimal("0"),
        "max_resolution": "720p",
        "has_watermark": True,
        "priority_queue": False,
        "can_use_effects": False,  # No VidGo Effects access
        "pollo_limit": 0,
        "goenhance_limit": 0,
        "description": "Free demo tier with cached results (2 one-time credits)"
    },
    {
        "name": "starter",
        "display_name": "Starter",
        "slug": "starter",
        "plan_type": "basic",
        "price_twd": Decimal("299"),
        "price_usd": Decimal("10"),
        "monthly_credits": 100,
        "weekly_credits": 25,  # 25 credits per week
        "topup_discount_rate": Decimal("0"),
        "max_resolution": "1080p",
        "has_watermark": False,
        "priority_queue": False,
        "can_use_effects": True,  # VidGo Effects access
        "pollo_limit": 30,
        "goenhance_limit": None,
        "description": "Great for getting started (25 credits/week)"
    },
    {
        "name": "pro",
        "display_name": "Pro",
        "slug": "pro",
        "plan_type": "pro",
        "price_twd": Decimal("599"),
        "price_usd": Decimal("20"),
        "monthly_credits": 250,
        "weekly_credits": 60,  # 60 credits per week
        "topup_discount_rate": Decimal("0.10"),
        "max_resolution": "4k",
        "has_watermark": False,
        "priority_queue": True,
        "can_use_effects": True,  # VidGo Effects access
        "pollo_limit": 50,
        "goenhance_limit": None,
        "description": "For professionals and power users (60 credits/week)"
    },
    {
        "name": "pro_plus",
        "display_name": "Pro+",
        "slug": "pro_plus",
        "plan_type": "enterprise",
        "price_twd": Decimal("999"),
        "price_usd": Decimal("33"),
        "monthly_credits": 500,
        "weekly_credits": 125,  # 125 credits per week
        "topup_discount_rate": Decimal("0.20"),
        "max_resolution": "4k",
        "has_watermark": False,
        "priority_queue": True,
        "can_use_effects": True,  # VidGo Effects access
        "pollo_limit": 100,
        "goenhance_limit": None,
        "description": "Unlimited potential for enterprises (125 credits/week)"
    },
]

# Credit package data
CREDIT_PACKAGE_DATA = [
    {
        "name": "small",
        "name_en": "Small Pack",
        "name_zh": "小包",
        "display_name": "Small Pack",
        "credits": 50,
        "price": 5.0,
        "price_twd": Decimal("150"),
        "price_usd": Decimal("5"),
        "min_plan": None,
        "bonus_credits": 0,
        "is_popular": False,
        "is_best_value": False,
        "sort_order": 1
    },
    {
        "name": "medium",
        "name_en": "Medium Pack",
        "name_zh": "中包",
        "display_name": "Medium Pack",
        "credits": 100,
        "price": 8.0,
        "price_twd": Decimal("250"),
        "price_usd": Decimal("8"),
        "min_plan": "starter",
        "bonus_credits": 10,
        "is_popular": True,
        "is_best_value": False,
        "sort_order": 2
    },
    {
        "name": "large",
        "name_en": "Large Pack",
        "name_zh": "大包",
        "display_name": "Large Pack",
        "credits": 200,
        "price": 13.0,
        "price_twd": Decimal("400"),
        "price_usd": Decimal("13"),
        "min_plan": "pro",
        "bonus_credits": 30,
        "is_popular": False,
        "is_best_value": True,
        "sort_order": 3
    },
    {
        "name": "enterprise",
        "name_en": "Enterprise Pack",
        "name_zh": "企業包",
        "display_name": "Enterprise Pack",
        "credits": 500,
        "price": 26.0,
        "price_twd": Decimal("800"),
        "price_usd": Decimal("26"),
        "min_plan": "pro_plus",
        "bonus_credits": 100,
        "is_popular": False,
        "is_best_value": False,
        "sort_order": 4
    },
]


async def seed_service_pricing():
    """Seed service pricing data."""
    async with AsyncSessionLocal() as session:
        print("Seeding service pricing...")

        for data in SERVICE_PRICING_DATA:
            # Check if already exists
            result = await session.execute(
                select(ServicePricing).where(
                    ServicePricing.service_type == data["service_type"]
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  Updating {data['service_type']}...")
                for key, value in data.items():
                    setattr(existing, key, value)
            else:
                print(f"  Creating {data['service_type']}...")
                pricing = ServicePricing(**data)
                session.add(pricing)

        await session.commit()
        print(f"Seeded {len(SERVICE_PRICING_DATA)} service pricing entries.")


async def seed_plans():
    """Seed plan data."""
    async with AsyncSessionLocal() as session:
        print("\nSeeding plans...")

        for data in PLAN_DATA:
            # Check if already exists by name or slug
            result = await session.execute(
                select(Plan).where(
                    (Plan.name == data["name"]) | (Plan.slug == data["slug"])
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  Updating plan {data['name']}...")
                for key, value in data.items():
                    if key != 'slug':  # Don't update slug to avoid conflicts
                        setattr(existing, key, value)
            else:
                print(f"  Creating plan {data['name']}...")
                plan = Plan(**data)
                session.add(plan)

            # Commit after each plan to avoid conflicts
            try:
                await session.commit()
            except Exception as e:
                await session.rollback()
                print(f"  Warning: Could not save plan {data['name']}: {e}")

        print(f"Seeded {len(PLAN_DATA)} plans.")


async def seed_credit_packages():
    """Seed credit package data."""
    async with AsyncSessionLocal() as session:
        print("\nSeeding credit packages...")

        for data in CREDIT_PACKAGE_DATA:
            # Check if already exists
            result = await session.execute(
                select(CreditPackage).where(CreditPackage.name == data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  Updating package {data['name']}...")
                for key, value in data.items():
                    setattr(existing, key, value)
            else:
                print(f"  Creating package {data['name']}...")
                package = CreditPackage(**data)
                session.add(package)

            # Commit after each package to avoid conflicts
            try:
                await session.commit()
            except Exception as e:
                await session.rollback()
                print(f"  Warning: Could not save package {data['name']}: {e}")

        print(f"Seeded {len(CREDIT_PACKAGE_DATA)} credit packages.")


async def main():
    """Main function to seed all data."""
    print("=" * 60)
    print("VidGo Service Pricing Seed Script")
    print("=" * 60)

    await seed_service_pricing()
    await seed_plans()
    await seed_credit_packages()

    print("\n" + "=" * 60)
    print("Seeding completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
