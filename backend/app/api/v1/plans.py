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
from app.models.billing import Plan, Subscription
from app.schemas.plan import (
    Plan as PlanSchema,
    PlanSummary,
    UserSubscription as UserSubscriptionSchema,
    PlansListResponse,
)

router = APIRouter()


# Default plans to seed if none exist
DEFAULT_PLANS = [
    {
        "name": "Free",
        "slug": "free",
        "plan_type": "free",
        "description": "Get started with AI video generation",
        "price_monthly": 0,
        "price_yearly": 0,
        "credits_per_month": 10,
        "max_video_length": 3,
        "max_resolution": "480p",
        "watermark": True,
        "priority_queue": False,
        "api_access": False,
        "feature_clothing_transform": True,
        "feature_goenhance": True,
        "feature_video_gen": False,
        "feature_batch_processing": False,
        "feature_custom_styles": False,
        "is_featured": False,
    },
    {
        "name": "Basic",
        "slug": "basic",
        "plan_type": "basic",
        "description": "Perfect for creators getting started",
        "price_monthly": 9.99,
        "price_yearly": 99.99,
        "credits_per_month": 100,
        "max_video_length": 10,
        "max_resolution": "720p",
        "watermark": False,
        "priority_queue": False,
        "api_access": False,
        "feature_clothing_transform": True,
        "feature_goenhance": True,
        "feature_video_gen": True,
        "feature_batch_processing": False,
        "feature_custom_styles": False,
        "is_featured": False,
    },
    {
        "name": "Pro",
        "slug": "pro",
        "plan_type": "pro",
        "description": "For professionals and power users",
        "price_monthly": 29.99,
        "price_yearly": 299.99,
        "credits_per_month": 500,
        "max_video_length": 30,
        "max_resolution": "1080p",
        "watermark": False,
        "priority_queue": True,
        "api_access": True,
        "feature_clothing_transform": True,
        "feature_goenhance": True,
        "feature_video_gen": True,
        "feature_batch_processing": True,
        "feature_custom_styles": True,
        "is_featured": True,
    },
    {
        "name": "Enterprise",
        "slug": "enterprise",
        "plan_type": "enterprise",
        "description": "Custom solutions for teams and businesses",
        "price_monthly": 99.99,
        "price_yearly": 999.99,
        "credits_per_month": 2000,
        "max_video_length": 60,
        "max_resolution": "4K",
        "watermark": False,
        "priority_queue": True,
        "api_access": True,
        "feature_clothing_transform": True,
        "feature_goenhance": True,
        "feature_video_gen": True,
        "feature_batch_processing": True,
        "feature_custom_styles": True,
        "is_featured": False,
    },
]


async def ensure_default_plans(db: AsyncSession) -> None:
    """Ensure default plans exist in the database."""
    result = await db.execute(select(Plan).limit(1))
    existing = result.scalars().first()

    if not existing:
        for plan_data in DEFAULT_PLANS:
            plan = Plan(**plan_data)
            db.add(plan)
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
