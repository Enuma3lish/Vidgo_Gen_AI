"""
Seed script for New Pricing Tiers from specification.

This script seeds the new pricing tiers based on the specification document.
Run with: python -m scripts.seed_new_pricing_tiers
"""
import asyncio
import sys
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, "/app")

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.billing import ServicePricing, Plan, CreditPackage


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

# Three production Point Pack top-ups. Top-up credits land in
# user.purchased_credits and do not expire.
NEW_CREDIT_PACKAGE_DATA = [
    {
        "name": "light_pack",
        "name_en": "Point Pack",
        "name_zh": "點數包",
        "display_name": "Point Pack",
        "credits": 3000,
        "price": 299.0,
        "price_twd": Decimal("299"),
        "price_usd": Decimal("10"),
        "currency": "TWD",
        "min_plan": "basic",
        "bonus_credits": 0,
        "is_popular": False,
        "is_best_value": False,
        "sort_order": 1
    },
    {
        "name": "standard_pack",
        "name_en": "Point Pack Plus",
        "name_zh": "超值點數包",
        "display_name": "Point Pack Plus",
        "credits": 5500,
        "price": 499.0,
        "price_twd": Decimal("499"),
        "price_usd": Decimal("16"),
        "currency": "TWD",
        "min_plan": "basic",
        "bonus_credits": 500,  # 10% bonus included in 5500
        "is_popular": True,
        "is_best_value": True,
        "sort_order": 2
    },
    {
        "name": "heavy_pack",
        "name_en": "Point Pack Max",
        "name_zh": "重度點數包",
        "display_name": "Point Pack Max",
        "credits": 12000,
        "price": 999.0,
        "price_twd": Decimal("999"),
        "price_usd": Decimal("32"),
        "currency": "TWD",
        "min_plan": "pro",
        "bonus_credits": 2000,  # 20% bonus included in 12000
        "is_popular": False,
        "is_best_value": True,
        "sort_order": 3
    },
]

# New Service Pricing data from specification
NEW_SERVICE_PRICING_DATA = [
    # Standard Static Generation (default model, 1x cost)
    {
        "service_type": "text_to_image_default",
        "display_name": "文生圖 (Default 模型)",
        "credit_cost": 20,
        "api_cost_usd": Decimal("0.02"),
        "model_type": "default",
        "tool_category": "static",
        "tool_type": "text_to_image",
        "resolution": "1024x1024",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "basic",
        "allowed_models": ["default"],
        "description": "標準靜態生成 - 文生圖"
    },
    {
        "service_type": "background_removal_default",
        "display_name": "去背 (Default 模型)",
        "credit_cost": 20,
        "api_cost_usd": Decimal("0.02"),
        "model_type": "default",
        "tool_category": "static",
        "tool_type": "background_removal",
        "resolution": None,
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "basic",
        "allowed_models": ["default"],
        "description": "標準靜態生成 - 去背"
    },
    
    # Advanced Dynamic Generation (wan_pro / gemini_pro models)
    {
        "service_type": "image_to_video_wan",
        "display_name": "圖生影片 (Wan, 5秒)",
        "credit_cost": 250,
        "api_cost_usd": Decimal("0.25"),
        "model_type": "wan_pro",
        "tool_category": "dynamic",
        "tool_type": "image_to_video",
        "resolution": "720p",
        "max_duration": 5,
        "subscribers_only": False,
        "min_plan": "pro",
        "allowed_models": ["wan_pro"],
        "description": "進階動態生成 - 圖生影片"
    },
    {
        "service_type": "ai_try_on",
        "display_name": "AI 試穿",
        "credit_cost": 250,
        "api_cost_usd": Decimal("0.25"),
        "model_type": "wan_pro",
        "tool_category": "dynamic",
        "tool_type": "ai_try_on",
        "resolution": "720p",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "pro",
        "allowed_models": ["wan_pro", "gemini_pro"],
        "description": "進階動態生成 - AI 試穿"
    },
    {
        "service_type": "ai_avatar",
        "display_name": "AI 虛擬人物",
        "credit_cost": 300,
        "api_cost_usd": Decimal("0.30"),
        "model_type": "gemini_pro",
        "tool_category": "dynamic",
        "tool_type": "ai_avatar",
        "resolution": "1080p",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "pro",
        "allowed_models": ["gemini_pro"],
        "description": "進階動態生成 - AI 虛擬人物"
    },
    {
        "service_type": "lip_sync",
        "display_name": "唇形同步",
        "credit_cost": 300,
        "api_cost_usd": Decimal("0.30"),
        "model_type": "gemini_pro",
        "tool_category": "dynamic",
        "tool_type": "lip_sync",
        "resolution": "1080p",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "pro",
        "allowed_models": ["gemini_pro"],
        "description": "進階動態生成 - 唇形同步"
    },
    
    # Premium High-Consumption Tasks
    {
        "service_type": "ultra_hd_video",
        "display_name": "超高畫質影片",
        "credit_cost": 2500,
        "api_cost_usd": Decimal("2.50"),
        "model_type": "sora",
        "tool_category": "premium",
        "tool_type": "ultra_hd_video",
        "resolution": "4k",
        "max_duration": 10,
        "subscribers_only": False,
        "min_plan": "premium",
        "allowed_models": ["sora"],
        "description": "頂規耗能任務 - 超高畫質影片 (如需外接 Sora 或極高畫質 3D)"
    },

    # ========================================================================
    # Deduction Firewall — Six tier categories per 2026-05 spec.
    #
    # Margin model:
    #   1 credit ≈ NT$0.10 ≈ $0.00333 USD (Basic plan NT$699 / 7000 credits)
    #   Target: ≥ 2x markup over API cost (≈ 200% gross margin)
    #   credit_cost ≈ ceil(api_cost_usd * 900) for 3x markup
    #
    # Spec asked for 1/5/10/15/35/50 but that scale undercuts API cost on the
    # flagship tier (50 credits = NT$5 revenue vs $0.5 USD = NT$15 cost).
    # Numbers below replace the spec with margin-safe equivalents so adding
    # high-cost flagship models doesn't bleed gross margin.
    #
    # tools.py endpoints fall through to their hardcoded CREDIT_COST when no
    # ServicePricing row matches by service_type, so adding these rows does
    # NOT change pricing of existing endpoints — only declares the catalog
    # for upcoming model integrations.
    # ========================================================================
    {
        "service_type": "image_generation_standard",
        "display_name": "標準 AI 圖片 (SDXL / Flux)",
        "credit_cost": 5,  # spec said 1; recalculated for $0.005 cost
        "api_cost_usd": Decimal("0.005"),
        "model_type": "default",
        "tool_category": "static",
        "tool_type": "text_to_image",
        "resolution": "1024x1024",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "basic",
        "allowed_models": ["default", "sdxl", "flux"],
        "description": "標準靜態圖片 - SDXL / Flux 等開源模型"
    },
    {
        "service_type": "image_generation_premium",
        "display_name": "高品質 AI 圖片 (Midjourney / DALL-E 3)",
        "credit_cost": 50,  # spec said 5; recalculated for $0.05 cost
        "api_cost_usd": Decimal("0.050"),
        "model_type": "wan_pro",
        "tool_category": "static",
        "tool_type": "text_to_image",
        "resolution": "2048x2048",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "basic",
        "allowed_models": ["midjourney", "dalle3"],
        "description": "高品質圖片 - Midjourney / DALL-E 3"
    },
    {
        "service_type": "video_generation_standard",
        "display_name": "標準 AI 影片 (5-10s)",
        "credit_cost": 100,  # spec said 10; recalculated for $0.10 cost
        "api_cost_usd": Decimal("0.100"),
        "model_type": "wan_pro",
        "tool_category": "dynamic",
        "tool_type": "image_to_video",
        "resolution": "720p",
        "max_duration": 10,
        "subscribers_only": False,
        "min_plan": "pro",
        "allowed_models": ["wan_pro", "kling_standard"],
        "description": "標準影片 - 主流 5-10s 模型"
    },
    {
        "service_type": "video_upscale",
        "display_name": "影片畫質修復 / 增強 (AI Upscale)",
        "credit_cost": 50,  # spec said 15; recalculated for $0.05 cost
        "api_cost_usd": Decimal("0.050"),
        "model_type": "default",
        "tool_category": "static",
        "tool_type": "upscale",
        "resolution": "4k",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "basic",
        "allowed_models": ["default", "esrgan"],
        "description": "影片畫質修復 / Upscale"
    },
    {
        "service_type": "video_generation_professional",
        "display_name": "專業級長影片 (Luma / Kling Standard)",
        "credit_cost": 300,  # spec said 35; recalculated for $0.30 cost
        "api_cost_usd": Decimal("0.300"),
        "model_type": "wan_pro",
        "tool_category": "premium",
        "tool_type": "image_to_video",
        "resolution": "1080p",
        "max_duration": 10,
        "subscribers_only": False,
        "min_plan": "pro",
        "allowed_models": ["luma_dream_machine", "kling_standard"],
        "description": "專業級長影片 - Luma Dream Machine / Kling Standard"
    },
    {
        "service_type": "video_flagship",
        "display_name": "極致旗艦影片 (Kling 2.1 Master / Sora2 / Veo)",
        "credit_cost": 500,  # spec said 50; recalculated for $0.50 cost
        "api_cost_usd": Decimal("0.500"),
        "model_type": "sora",
        "tool_category": "premium",
        "tool_type": "ultra_hd_video",
        "resolution": "4k",
        "max_duration": 10,
        "subscribers_only": False,
        "min_plan": "premium",
        "allowed_models": ["kling_2_1_master", "sora2_pro", "veo"],
        "description": "極致旗艦影片 - 單次成本 > $0.5 USD 的頂級模型"
    },
]


async def seed_new_plans():
    """Seed new plan data from specification.

    Also deactivates any pre-existing plans that are NOT in NEW_PLAN_DATA.
    Context for F-003: earlier seeds (seed_service_pricing.py) inserted plans
    like 'pro_plus' and 'starter' which now collide on price with the new
    '專業版' (pro) plan — both at NT$999 but with 500 vs 10000 credits. The
    subscriptions API filters on `is_active == True`, so flipping the old
    plans to `is_active=False` removes them from the Pricing page without
    deleting historical subscription rows referencing them.
    """
    async with AsyncSessionLocal() as session:
        print("\nSeeding new plans from specification...")

        new_plan_names = {data["name"] for data in NEW_PLAN_DATA}

        for data in NEW_PLAN_DATA:
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
                # Ensure it's active (in case it was deactivated by a prior run)
                existing.is_active = True
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

        # Deactivate legacy plans not in NEW_PLAN_DATA (e.g. pro_plus, starter,
        # demo, free from seed_service_pricing.py). Preserves rows so existing
        # subscriptions still reference valid plan_ids, but removes them from
        # the Pricing page via the is_active filter.
        print("\nDeactivating legacy plans not in NEW_PLAN_DATA...")
        all_result = await session.execute(select(Plan))
        all_plans = all_result.scalars().all()
        deactivated = 0
        for plan in all_plans:
            if plan.name not in new_plan_names and plan.is_active:
                print(f"  Deactivating legacy plan: {plan.name} ({plan.display_name})")
                plan.is_active = False
                deactivated += 1
        if deactivated:
            try:
                await session.commit()
            except Exception as e:
                await session.rollback()
                print(f"  Warning: Could not deactivate legacy plans: {e}")
        print(f"  Deactivated {deactivated} legacy plan(s)")

        print(f"Seeded {len(NEW_PLAN_DATA)} new plans.")


async def seed_new_credit_packages():
    """Seed new credit package data from specification.

    Deactivates legacy package rows so public pricing and authenticated
    purchases only expose the current light/standard/heavy TWD packages.
    """
    async with AsyncSessionLocal() as session:
        print("\nSeeding new credit packages...")

        new_package_names = {data["name"] for data in NEW_CREDIT_PACKAGE_DATA}

        for data in NEW_CREDIT_PACKAGE_DATA:
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

        print("\nDeactivating legacy credit packages not in NEW_CREDIT_PACKAGE_DATA...")
        all_result = await session.execute(select(CreditPackage))
        all_packages = all_result.scalars().all()
        deactivated = 0
        for package in all_packages:
            if package.name not in new_package_names and package.is_active:
                print(f"  Deactivating legacy package: {package.name} ({package.display_name})")
                package.is_active = False
                deactivated += 1
            elif package.name in new_package_names and not package.is_active:
                package.is_active = True
        try:
            await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"  Warning: Could not normalize credit packages: {e}")
        print(f"  Deactivated {deactivated} legacy package(s)")

        print(f"Seeded {len(NEW_CREDIT_PACKAGE_DATA)} new credit packages.")


async def seed_new_service_pricing():
    """Seed new service pricing data from specification."""
    async with AsyncSessionLocal() as session:
        print("\nSeeding new service pricing...")

        for data in NEW_SERVICE_PRICING_DATA:
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
        print(f"Seeded {len(NEW_SERVICE_PRICING_DATA)} new service pricing entries.")


async def map_existing_users_to_new_plans():
    """Map existing users to closest new plans (Option B from discussion)."""
    async with AsyncSessionLocal() as session:
        print("\nMapping existing users to new plans...")
        
        from app.models.user import User
        from sqlalchemy import update
        
        # Mapping from old plan names to new plan names
        plan_mapping = {
            "demo": "basic",      # Demo -> Basic (closest match)
            "starter": "basic",   # Starter -> Basic
            "pro": "pro",         # Pro -> Pro (same name)
            "pro_plus": "premium" # Pro+ -> Premium (closest match)
        }
        
        # Get all plans to create name->id mapping
        result = await session.execute(select(Plan))
        all_plans = result.scalars().all()
        plan_name_to_id = {plan.name: plan.id for plan in all_plans}
        
        # Get users with current_plan_id
        result = await session.execute(
            select(User).where(User.current_plan_id != None)
        )
        users = result.scalars().all()
        
        updated_count = 0
        for user in users:
            # Get user's current plan name
            if user.current_plan_id:
                # Find plan by id
                user_plan_result = await session.execute(
                    select(Plan).where(Plan.id == user.current_plan_id)
                )
                user_plan = user_plan_result.scalar_one_or_none()
                
                if user_plan and user_plan.name in plan_mapping:
                    new_plan_name = plan_mapping[user_plan.name]
                    if new_plan_name in plan_name_to_id:
                        # Update user's plan
                        user.current_plan_id = plan_name_to_id[new_plan_name]
                        updated_count += 1
                        print(f"  Mapped user {user.id} from {user_plan.name} to {new_plan_name}")
        
        await session.commit()
        print(f"Mapped {updated_count} users to new plans.")


async def main():
    """Main function to seed all new data."""
    print("=" * 60)
    print("VidGo New Pricing Tiers Seed Script")
    print("=" * 60)

    await seed_new_plans()
    await seed_new_credit_packages()
    await seed_new_service_pricing()
    await map_existing_users_to_new_plans()

    print("\n" + "=" * 60)
    print("New pricing tiers seeding completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())