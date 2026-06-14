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
        "credit_cost": 10,
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
        "credit_cost": 15,
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
        "credit_cost": 30,
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
        "credit_cost": 1,
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
        "credit_cost": 1,
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
        "credit_cost": 3,
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
        "credit_cost": 3,
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
        "credit_cost": 30,
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
        "credit_cost": 30,
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
        "credit_cost": 50,
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
        "credit_cost": 30,
        "api_cost_usd": Decimal("0.50"),
        "resolution": "720p",
        "max_duration": 8,
        "subscribers_only": False,
        "min_plan": None,
        "description": "Fallback video generation via Runway (internal)"
    },
    # Model-specific pricing (for model selection feature)
    {
        "service_type": "model_pixverse_v4_5",
        "display_name": "Pixverse v4.5 (Fast)",
        "credit_cost": 10,
        "api_cost_usd": Decimal("0.10"),
        "resolution": "720p",
        "max_duration": 8,
        "subscribers_only": False,
        "min_plan": "starter",
        "description": "Fast video generation with Pixverse v4.5"
    },
    {
        "service_type": "model_pixverse_v5",
        "display_name": "Pixverse v5 (Creative)",
        "credit_cost": 15,
        "api_cost_usd": Decimal("0.15"),
        "resolution": "720p",
        "max_duration": 8,
        "subscribers_only": False,
        "min_plan": "starter",
        "description": "Creative animations with Pixverse v5"
    },
    {
        "service_type": "model_kling_v1_5",
        "display_name": "Kling v1.5 (Good Quality)",
        "credit_cost": 20,
        "api_cost_usd": Decimal("0.25"),
        "resolution": "1080p",
        "max_duration": 10,
        "subscribers_only": False,
        "min_plan": "starter",
        "description": "Good quality video with Kling v1.5"
    },
    {
        "service_type": "model_kling_v2",
        "display_name": "Kling v2.0 (High Quality)",
        "credit_cost": 30,
        "api_cost_usd": Decimal("0.40"),
        "resolution": "1080p",
        "max_duration": 10,
        "subscribers_only": False,
        "min_plan": "pro",
        "description": "High quality video with Kling v2.0"
    },
    {
        "service_type": "model_luma_ray2",
        "display_name": "Luma Ray 2.0 (Cinematic)",
        "credit_cost": 30,
        "api_cost_usd": Decimal("0.50"),
        "resolution": "1080p",
        "max_duration": 10,
        "subscribers_only": False,
        "min_plan": "pro",
        "description": "Cinematic quality video with Luma Ray 2.0"
    },
    {
        "service_type": "model_wan_t2i",
        "display_name": "Wan T2I (Standard Image)",
        "credit_cost": 1,
        "api_cost_usd": Decimal("0.02"),
        "resolution": "1024x1024",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "starter",
        "description": "Standard text-to-image generation"
    },
    {
        "service_type": "model_wan_i2v",
        "display_name": "Wan I2V (Standard Video)",
        "credit_cost": 10,
        "api_cost_usd": Decimal("0.15"),
        "resolution": "720p",
        "max_duration": 5,
        "subscribers_only": False,
        "min_plan": "starter",
        "description": "Standard image-to-video generation with Wan"
    },
    # Background removal for subscribers
    {
        "service_type": "bg_removal",
        "display_name": "Background Removal",
        "credit_cost": 1,
        "api_cost_usd": Decimal("0.02"),
        "resolution": None,
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "starter",
        "description": "AI background removal from uploaded images"
    },
    # Product scene for subscribers
    {
        "service_type": "product_scene_gen",
        "display_name": "Product Scene Generation",
        "credit_cost": 1,
        "api_cost_usd": Decimal("0.05"),
        "resolution": "1024x1024",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "starter",
        "description": "Generate product in professional scenes"
    },
    # Pattern generation for subscribers
    {
        "service_type": "pattern_gen",
        "display_name": "Pattern Generation",
        "credit_cost": 1,
        "api_cost_usd": Decimal("0.03"),
        "resolution": "1024x1024",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "starter",
        "description": "Generate seamless patterns"
    },
    # Effect / style transfer for subscribers
    {
        "service_type": "style_transfer",
        "display_name": "Style Transfer",
        "credit_cost": 2,  # v2.2 — Flux Kontext $0.04
        "api_cost_usd": Decimal("0.04"),
        "resolution": "1024x1024",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "starter",
        "description": "Apply artistic styles to images"
    },

    # ─── v2.2 (2026-06) — new PiAPI / vendor catalog rows ─────────────
    # All values match the h2b3c4d5e6f7 alembic migration + tier_config.py.
    # api_cost_usd is the 2026-Q2 vendor list price; reconcile against the
    # monthly PiAPI / A2E / Vertex invoice and update when vendors shift.
    {
        "service_type": "nano_banana_pro_t2i",
        "display_name": "Nano Banana Pro (T2I)",
        "credit_cost": 5,
        "api_cost_usd": Decimal("0.10"),
        "resolution": "1024x1024",
        "max_duration": None,
        "subscribers_only": True,
        "min_plan": "pro",
        "description": "Google Gemini Nano Banana Pro 高品質 T2I"
    },
    {
        "service_type": "seedream_5_lite_t2i",
        "display_name": "Seedream 5 Lite (T2I)",
        "credit_cost": 1,
        "api_cost_usd": Decimal("0.025"),
        "resolution": "1024x1024",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "basic",
        "description": "ByteDance Seedream 5 Lite — 中低價位 T2I"
    },
    {
        "service_type": "hailuo_fast_video",
        "display_name": "Hailuo Fast 影片",
        "credit_cost": 20,
        "api_cost_usd": Decimal("0.10"),
        "resolution": "720p",
        "max_duration": 5,
        "subscribers_only": True,
        "min_plan": "basic",
        "description": "Hailuo Fast — 平價影片預設"
    },
    {
        "service_type": "seedance_fast_video",
        "display_name": "Seedance Fast 影片",
        "credit_cost": 20,
        "api_cost_usd": Decimal("0.10"),
        "resolution": "720p",
        "max_duration": 5,
        "subscribers_only": True,
        "min_plan": "basic",
        "description": "Seedance 2 Fast — 性價比影片預設"
    },
    {
        "service_type": "kling_omni_video",
        "display_name": "Kling 3.0 Omni 影片",
        "credit_cost": 60,
        "api_cost_usd": Decimal("0.50"),
        "resolution": "1080p",
        "max_duration": 10,
        "subscribers_only": True,
        "min_plan": "pro",
        "description": "Kling 3.0 Omni — 旗艦影片"
    },
    {
        "service_type": "hunyuan_video",
        "display_name": "Hunyuan 中文影片",
        "credit_cost": 25,
        "api_cost_usd": Decimal("0.30"),
        "resolution": "720p",
        "max_duration": 5,
        "subscribers_only": True,
        "min_plan": "basic",
        "description": "Hunyuan — 中文 prompts 影片"
    },
    {
        "service_type": "veo_31_fast",
        "display_name": "Veo 3.1 Fast 影片",
        "credit_cost": 200,
        "api_cost_usd": Decimal("0.50"),
        "resolution": "1080p",
        "max_duration": 5,
        "subscribers_only": True,
        "min_plan": "premium",
        "description": "Google Veo 3.1 Fast — 旗艦短影片"
    },

    # Avatar / lip-sync — v2.2 fallback rows so the DB-driven path
    # works for ai_avatar / lip_sync / video_dubbing endpoints.
    {
        "service_type": "ai_avatar",
        "display_name": "AI Avatar",
        "credit_cost": 80,
        "api_cost_usd": Decimal("2.00"),
        "resolution": "1080p",
        "max_duration": 30,
        "subscribers_only": True,
        "min_plan": "pro",
        "description": "AI 數位人 (A2E / Kling Avatar)"
    },
    {
        "service_type": "lip_sync",
        "display_name": "Lip Sync",
        "credit_cost": 50,
        "api_cost_usd": Decimal("1.00"),
        "resolution": "1080p",
        "max_duration": 30,
        "subscribers_only": True,
        "min_plan": "pro",
        "description": "AI 對嘴 (Kling Lip Sync)"
    },
    {
        "service_type": "video_dubbing",
        "display_name": "Video Dubbing",
        "credit_cost": 60,
        "api_cost_usd": Decimal("1.50"),
        "resolution": "1080p",
        "max_duration": 30,
        "subscribers_only": True,
        "min_plan": "pro",
        "description": "AI 配音 (A2E 多語配音)"
    },
    {
        "service_type": "virtual_try_on",
        "display_name": "Virtual Try-On",
        "credit_cost": 30,
        "api_cost_usd": Decimal("0.70"),
        "resolution": "1080p",
        "max_duration": None,
        "subscribers_only": True,
        "min_plan": "basic",
        "description": "Kling Try-On — 虛擬試穿"
    },
]

# Plan data (VidGo 2.0 — monthly subscription credit system)
# 週期性配點: subscription_credits reset to monthly_credits each billing date
# 過期清空: monthly subscription credits do NOT roll over (Breakage 利潤)
# 換算單點成本 (TWD/credit): Starter 0.98, Pro 0.86, Master 0.82
PLAN_DATA = [
    {
        "name": "demo",
        "display_name": "Demo",
        "slug": "demo",
        "plan_type": "free",
        "price_twd": Decimal("0"),
        "price_usd": Decimal("0"),
        "price_monthly": 0.0,
        "price_yearly": 0.0,
        "monthly_credits": 0,
        "weekly_credits": 0,  # Demo users get 2 one-time credits on signup
        "topup_discount_rate": Decimal("0"),
        "max_resolution": "720p",
        "has_watermark": True,
        "priority_queue": False,
        "can_use_effects": False,
        "pollo_limit": 0,
        "goenhance_limit": 0,
        "description": "Free demo tier with cached results (2 one-time credits)"
    },
    {
        "name": "starter",
        "display_name": "Starter",
        "slug": "starter",
        "plan_type": "basic",
        "price_twd": Decimal("490"),
        "price_usd": Decimal("16"),
        "price_monthly": 490.0,
        "price_yearly": 4900.0,
        "monthly_credits": 500,
        "weekly_credits": 0,  # VidGo 2.0: monthly only
        "topup_discount_rate": Decimal("0"),
        "max_resolution": "1080p",
        "has_watermark": False,
        "priority_queue": False,
        "can_use_effects": True,
        "pollo_limit": 30,
        "goenhance_limit": None,
        "description": "初學者 Starter — 每月 500 點 (每點 TWD 0.98)"
    },
    {
        "name": "pro",
        "display_name": "Pro",
        "slug": "pro",
        "plan_type": "pro",
        "price_twd": Decimal("1290"),
        "price_usd": Decimal("42"),
        "price_monthly": 1290.0,
        "price_yearly": 12900.0,
        "monthly_credits": 1500,
        "weekly_credits": 0,
        "topup_discount_rate": Decimal("0.10"),
        "max_resolution": "4k",
        "has_watermark": False,
        "priority_queue": True,
        "can_use_effects": True,
        "pollo_limit": 50,
        "goenhance_limit": None,
        "description": "專業版 Pro — 每月 1,500 點 (每點 TWD 0.86)"
    },
    {
        # internal name "pro_plus" retained for foreign-key compatibility,
        # display surfaces as "Master" per VidGo 2.0 spec.
        "name": "pro_plus",
        "display_name": "Master",
        "slug": "master",
        "plan_type": "enterprise",
        "price_twd": Decimal("2890"),
        "price_usd": Decimal("93"),
        "price_monthly": 2890.0,
        "price_yearly": 28900.0,
        "monthly_credits": 3500,
        "weekly_credits": 0,
        "topup_discount_rate": Decimal("0.20"),
        "max_resolution": "4k",
        "has_watermark": False,
        "priority_queue": True,
        "can_use_effects": True,
        "pollo_limit": 100,
        "goenhance_limit": None,
        "description": "大師版 Master — 每月 3,500 點 (每點 TWD 0.82)"
    },
]

# Credit package data (VidGo 2.0 Top-up packages)
# 權限限制: subscribers-only (min_plan=starter); non-subscribers see higher prices
# 永不過期: top-up credits land in user.purchased_credits and never expire
CREDIT_PACKAGE_DATA = [
    {
        "name": "compact",
        "name_en": "Compact Pack",
        "name_zh": "精簡儲值包",
        "display_name": "Compact Pack",
        "credits": 300,
        "price": 11.0,
        "price_twd": Decimal("350"),
        "price_usd": Decimal("11"),
        "min_plan": "starter",  # subscribers only
        "bonus_credits": 0,
        "is_popular": False,
        "is_best_value": False,
        "sort_order": 1
    },
    {
        "name": "standard",
        "name_en": "Standard Pack",
        "name_zh": "標準儲值包",
        "display_name": "Standard Pack",
        "credits": 1000,
        "price": 32.0,
        "price_twd": Decimal("990"),
        "price_usd": Decimal("32"),
        "min_plan": "starter",
        "bonus_credits": 0,
        "is_popular": True,
        "is_best_value": False,
        "sort_order": 2
    },
    {
        "name": "large",
        "name_en": "Large Pack",
        "name_zh": "大容量儲值包",
        "display_name": "Large Pack",
        "credits": 2000,
        "price": 61.0,
        "price_twd": Decimal("1890"),
        "price_usd": Decimal("61"),
        "min_plan": "starter",
        "bonus_credits": 0,
        "is_popular": False,
        "is_best_value": True,
        "sort_order": 3
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
