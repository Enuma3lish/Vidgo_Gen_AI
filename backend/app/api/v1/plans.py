"""
Plans API endpoints.
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.api import deps
from app.models.user import User
from app.models.billing import Plan, Subscription, CreditPackage
from app.schemas.plan import (
    Plan as PlanSchema,
    PlanSummary,
    UserSubscription as UserSubscriptionSchema,
    PlansListResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Default subscription plans for VidGo
# Prices shown in both TWD and USD; weekly_credits = monthly / 4
# ---------------------------------------------------------------------------
DEFAULT_PLANS = [
    {
        "name": "demo",
        "display_name": "Free",
        "slug": "free",
        "plan_type": "free",
        "description": "Try VidGo with limited features",
        "price_monthly": 0.0,
        "price_yearly": 0.0,
        "price_twd": 0,
        "price_usd": 0,
        "currency": "TWD",
        "billing_cycle": "monthly",
        "monthly_credits": 0,
        "weekly_credits": 0,
        "credits_per_month": 0,
        "topup_discount_rate": 0,
        "max_video_length": 5,
        "max_resolution": "720p",
        "has_watermark": True,
        "watermark": True,
        "priority_queue": False,
        "api_access": False,
        "can_use_effects": False,
        "feature_clothing_transform": True,
        "feature_goenhance": False,
        "feature_video_gen": True,
        "feature_batch_processing": False,
        "feature_custom_styles": False,
        "is_featured": False,
    },
    {
        "name": "starter",
        "display_name": "Starter",
        "slug": "starter",
        "plan_type": "basic",
        "description": "Perfect for creators getting started",
        "price_monthly": 9.99,
        "price_yearly": 107.88,  # 12 * 8.99 (yearly discount)
        "price_twd": 299,
        "price_usd": 9.99,
        "currency": "TWD",
        "billing_cycle": "monthly",
        "monthly_credits": 200,
        "weekly_credits": 50,
        "credits_per_month": 200,
        "topup_discount_rate": 0,
        "max_video_length": 15,
        "max_resolution": "1080p",
        "has_watermark": False,
        "watermark": False,
        "priority_queue": False,
        "api_access": False,
        "can_use_effects": True,
        "feature_clothing_transform": True,
        "feature_goenhance": True,
        "feature_video_gen": True,
        "feature_batch_processing": False,
        "feature_custom_styles": False,
        "is_featured": False,
    },
    {
        "name": "pro",
        "display_name": "Pro",
        "slug": "pro",
        "plan_type": "pro",
        "description": "For professionals and power users",
        "price_monthly": 21.99,
        "price_yearly": 239.88,  # 12 * 19.99 (yearly discount)
        "price_twd": 649,
        "price_usd": 21.99,
        "currency": "TWD",
        "billing_cycle": "monthly",
        "monthly_credits": 500,
        "weekly_credits": 125,
        "credits_per_month": 500,
        "topup_discount_rate": 0.10,
        "max_video_length": 30,
        "max_resolution": "1080p",
        "has_watermark": False,
        "watermark": False,
        "priority_queue": True,
        "api_access": False,
        "can_use_effects": True,
        "feature_clothing_transform": True,
        "feature_goenhance": True,
        "feature_video_gen": True,
        "feature_batch_processing": False,
        "feature_custom_styles": True,
        "is_featured": True,
    },
    {
        "name": "pro_plus",
        "display_name": "Pro Plus",
        "slug": "pro-plus",
        "plan_type": "enterprise",
        "description": "Maximum power with API access and batch processing",
        "price_monthly": 42.99,
        "price_yearly": 467.88,  # 12 * 38.99 (yearly discount)
        "price_twd": 1299,
        "price_usd": 42.99,
        "currency": "TWD",
        "billing_cycle": "monthly",
        "monthly_credits": 2000,
        "weekly_credits": 500,
        "credits_per_month": 2000,
        "topup_discount_rate": 0.20,
        "max_video_length": 60,
        "max_resolution": "4K",
        "has_watermark": False,
        "watermark": False,
        "priority_queue": True,
        "api_access": True,
        "can_use_effects": True,
        "feature_clothing_transform": True,
        "feature_goenhance": True,
        "feature_video_gen": True,
        "feature_batch_processing": True,
        "feature_custom_styles": True,
        "is_featured": False,
    },
]


# ---------------------------------------------------------------------------
# Default credit packages for top-up purchases
# ---------------------------------------------------------------------------
DEFAULT_CREDIT_PACKAGES = [
    {
        "name": "starter_pack",
        "name_zh": "入門包",
        "name_en": "Starter Pack",
        "display_name": "Starter Pack",
        "description": "100 credits to get started",
        "credits": 100,
        "price": 3.29,
        "price_twd": 99,
        "price_usd": 3.29,
        "currency": "TWD",
        "bonus_credits": 0,
        "is_popular": True,
        "is_best_value": False,
        "sort_order": 1,
        "is_active": True,
    },
    {
        "name": "value_pack",
        "name_zh": "超值包",
        "name_en": "Value Pack",
        "display_name": "Value Pack",
        "description": "300 credits for regular creators",
        "credits": 300,
        "price": 8.29,
        "price_twd": 249,
        "price_usd": 8.29,
        "currency": "TWD",
        "bonus_credits": 0,
        "is_popular": False,
        "is_best_value": False,
        "sort_order": 2,
        "is_active": True,
    },
    {
        "name": "pro_pack",
        "name_zh": "專業包",
        "name_en": "Pro Pack",
        "display_name": "Pro Pack",
        "description": "600 credits for power users",
        "credits": 600,
        "price": 14.99,
        "price_twd": 449,
        "price_usd": 14.99,
        "currency": "TWD",
        "bonus_credits": 0,
        "is_popular": False,
        "is_best_value": True,
        "sort_order": 3,
        "is_active": True,
    },
    {
        "name": "enterprise_pack",
        "name_zh": "企業包",
        "name_en": "Enterprise Pack",
        "display_name": "Enterprise Pack",
        "description": "2000 credits for teams and heavy usage",
        "credits": 2000,
        "price": 42.99,
        "price_twd": 1299,
        "price_usd": 42.99,
        "currency": "TWD",
        "bonus_credits": 0,
        "is_popular": False,
        "is_best_value": False,
        "sort_order": 4,
        "is_active": True,
    },
]


async def ensure_default_plans(db: AsyncSession) -> None:
    """Ensure default subscription plans exist in the database."""
    result = await db.execute(select(Plan).limit(1))
    existing = result.scalars().first()

    if not existing:
        for plan_data in DEFAULT_PLANS:
            plan = Plan(**plan_data)
            db.add(plan)
        await db.commit()


async def ensure_default_credit_packages(db: AsyncSession) -> None:
    """Ensure default credit packages exist in the database."""
    result = await db.execute(select(CreditPackage).limit(1))
    existing = result.scalars().first()

    if not existing:
        for pkg_data in DEFAULT_CREDIT_PACKAGES:
            package = CreditPackage(**pkg_data)
            db.add(package)
        await db.commit()


@router.get("", response_model=List[PlanSchema])
async def get_plans(
    db: AsyncSession = Depends(deps.get_db),
    active_only: bool = True
) -> Any:
    """
    Get all available plans.
    Public endpoint - no authentication required.
    """
    # Ensure default plans exist
    await ensure_default_plans(db)

    query = select(Plan)
    if active_only:
        query = query.where(Plan.is_active == True)
    query = query.order_by(Plan.price_monthly)

    result = await db.execute(query)
    plans = result.scalars().all()

    return plans


@router.get("/credit-packages")
async def get_credit_packages(
    db: AsyncSession = Depends(deps.get_db),
    active_only: bool = True,
) -> Any:
    """
    Get all available credit packages for top-up purchase.
    Public endpoint - no authentication required.
    """
    await ensure_default_credit_packages(db)

    query = select(CreditPackage)
    if active_only:
        query = query.where(CreditPackage.is_active == True)
    query = query.order_by(CreditPackage.sort_order)

    result = await db.execute(query)
    packages = result.scalars().all()

    return packages


@router.get("/current", response_model=Optional[UserSubscriptionSchema])
async def get_current_subscription(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Get current user's subscription.
    """
    result = await db.execute(
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(Subscription.user_id == current_user.id)
        .where(Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
    )
    subscription = result.scalars().first()

    return subscription


@router.get("/with-subscription", response_model=PlansListResponse)
async def get_plans_with_subscription(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Get all plans along with the user's current subscription.
    """
    # Ensure default plans exist
    await ensure_default_plans(db)

    # Get all active plans
    plans_result = await db.execute(
        select(Plan)
        .where(Plan.is_active == True)
        .order_by(Plan.price_monthly)
    )
    plans = plans_result.scalars().all()

    # Get user's current subscription
    sub_result = await db.execute(
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(Subscription.user_id == current_user.id)
        .where(Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
    )
    subscription = sub_result.scalars().first()

    return PlansListResponse(
        plans=[PlanSchema.model_validate(p) for p in plans],
        current_subscription=UserSubscriptionSchema.model_validate(subscription) if subscription else None
    )


@router.get("/{plan_id}", response_model=PlanSchema)
async def get_plan(
    plan_id: str,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Get a specific plan by ID.
    """
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalars().first()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )

    return plan
