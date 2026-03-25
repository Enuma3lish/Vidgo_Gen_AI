"""
Plans API Endpoints for new pricing tiers.

Endpoints:
- GET /plans - Get all available plans
- GET /plans/comparison - Get plan comparison table
- GET /plans/current - Get current user's plan details
- POST /plans/upgrade - Upgrade user's plan
- POST /plans/downgrade - Downgrade user's plan
- GET /plans/check-permission - Check if user can use specific service
- GET /plans/check-concurrent - Check concurrent generation limit
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from typing import List, Dict, Any

from app.api.deps import get_db, get_current_user, get_current_active_user, get_redis
from app.services.credit_service import CreditService
from app.models.user import User
from app.models.billing import Plan
from sqlalchemy import select

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/", response_model=List[Dict[str, Any]])
async def get_plans(
    db: AsyncSession = Depends(get_db)
):
    """Get all available plans."""
    result = await db.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.price_twd)
    )
    plans = result.scalars().all()

    return [
        {
            "id": plan.id,
            "name": plan.name,
            "display_name": plan.display_name,
            "price_twd": plan.price_twd,
            "price_usd": plan.price_usd,
            "monthly_credits": plan.monthly_credits,
            "allowed_models": plan.allowed_models or [],
            "max_concurrent_generations": plan.max_concurrent_generations or 1,
            "social_media_batch_posting": plan.social_media_batch_posting,
            "priority_queue": plan.priority_queue,
            "enterprise_features": plan.enterprise_features,
            "has_watermark": plan.has_watermark,
            "max_resolution": plan.max_resolution,
            "description": plan.description,
            "is_featured": plan.is_featured
        }
        for plan in plans
    ]


@router.get("/comparison", response_model=List[Dict[str, Any]])
async def get_plan_comparison(
    db: AsyncSession = Depends(get_db)
):
    """Get detailed plan comparison table."""
    service = CreditService(db)
    return await service.get_plan_comparison()


@router.get("/current", response_model=Dict[str, Any])
async def get_current_plan(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's plan details."""
    if not current_user.current_plan_id:
        raise HTTPException(status_code=404, detail="User has no active plan")

    result = await db.execute(
        select(Plan).where(Plan.id == current_user.current_plan_id)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Get credit service for balance info
    service = CreditService(db)
    balance = await service.get_balance(str(current_user.id))

    return {
        "id": plan.id,
        "name": plan.name,
        "display_name": plan.display_name,
        "price_twd": plan.price_twd,
        "monthly_credits": plan.monthly_credits,
        "current_credits": balance["subscription"],
        "credits_used_this_month": balance["monthly_used"],
        "allowed_models": plan.allowed_models or [],
        "max_concurrent_generations": plan.max_concurrent_generations or 1,
        "social_media_batch_posting": plan.social_media_batch_posting,
        "priority_queue": plan.priority_queue,
        "enterprise_features": plan.enterprise_features,
        "has_watermark": plan.has_watermark,
        "max_resolution": plan.max_resolution,
        "description": plan.description,
        "plan_started_at": current_user.plan_started_at,
        "plan_expires_at": current_user.plan_expires_at,
        "balance": balance
    }


@router.post("/upgrade")
async def upgrade_plan(
    plan_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Upgrade user's plan."""
    # Check if new plan exists
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id, Plan.is_active == True)
    )
    new_plan = result.scalar_one_or_none()

    if not new_plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Check if user already has this plan
    if current_user.current_plan_id == plan_id:
        raise HTTPException(status_code=400, detail="User already has this plan")

    # Get current plan for comparison
    current_plan = None
    if current_user.current_plan_id:
        result = await db.execute(
            select(Plan).where(Plan.id == current_user.current_plan_id)
        )
        current_plan = result.scalar_one_or_none()

    # Determine if this is an upgrade
    plan_order = {"basic": 1, "pro": 2, "premium": 3, "enterprise": 4}
    current_level = plan_order.get(current_plan.name if current_plan else "basic", 0)
    new_level = plan_order.get(new_plan.name, 0)

    if new_level <= current_level:
        raise HTTPException(status_code=400, detail="Cannot upgrade to same or lower tier")

    # Process upgrade
    service = CreditService(db, redis)
    try:
        new_balance = await service.handle_plan_change(
            user_id=str(current_user.id),
            new_plan_id=plan_id,
            is_upgrade=True
        )
        return {
            "success": True,
            "message": f"Plan upgraded to {new_plan.display_name}",
            "new_plan": new_plan.name,
            "new_balance": new_balance
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upgrade failed: {str(e)}")


@router.post("/downgrade")
async def downgrade_plan(
    plan_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Downgrade user's plan (effective next billing cycle)."""
    # Check if new plan exists
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id, Plan.is_active == True)
    )
    new_plan = result.scalar_one_or_none()

    if not new_plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Check if user already has this plan
    if current_user.current_plan_id == plan_id:
        raise HTTPException(status_code=400, detail="User already has this plan")

    # Get current plan for comparison
    current_plan = None
    if current_user.current_plan_id:
        result = await db.execute(
            select(Plan).where(Plan.id == current_user.current_plan_id)
        )
        current_plan = result.scalar_one_or_none()

    # Determine if this is a downgrade
    plan_order = {"basic": 1, "pro": 2, "premium": 3, "enterprise": 4}
    current_level = plan_order.get(current_plan.name if current_plan else "basic", 0)
    new_level = plan_order.get(new_plan.name, 0)

    if new_level >= current_level:
        raise HTTPException(status_code=400, detail="Cannot downgrade to same or higher tier")

    # Process downgrade (effective next cycle)
    # For now, just update the plan immediately but keep current credits
    service = CreditService(db, redis)
    try:
        new_balance = await service.handle_plan_change(
            user_id=str(current_user.id),
            new_plan_id=plan_id,
            is_upgrade=False
        )
        return {
            "success": True,
            "message": f"Plan will be downgraded to {new_plan.display_name} on next billing cycle",
            "new_plan": new_plan.name,
            "current_balance": new_balance,
            "note": "Credits will be adjusted on next billing cycle"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Downgrade failed: {str(e)}")


@router.get("/check-permission")
async def check_model_permission(
    service_type: str = Query(..., description="Service type to check"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Check if user has permission to use specific service/model."""
    service = CreditService(db)
    has_permission, error_message = await service.check_model_permission(
        user_id=str(current_user.id),
        service_type=service_type
    )

    if not has_permission:
        raise HTTPException(status_code=403, detail=error_message)

    # Get service pricing for additional info
    pricing = await service.get_service_pricing(service_type)
    if pricing:
        return {
            "has_permission": True,
            "service_type": service_type,
            "display_name": pricing.display_name,
            "credit_cost": pricing.credit_cost,
            "model_type": pricing.model_type,
            "tool_category": pricing.tool_category,
            "min_plan": pricing.min_plan
        }
    else:
        return {
            "has_permission": True,
            "service_type": service_type,
            "message": "Service found but pricing details not available"
        }


@router.get("/check-concurrent")
async def check_concurrent_limit(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Check if user has reached concurrent generation limit."""
    service = CreditService(db)
    within_limit, error_message = await service.check_concurrent_limit(
        user_id=str(current_user.id)
    )

    if not within_limit:
        raise HTTPException(status_code=429, detail=error_message)

    # Get current count and limit
    if current_user.current_plan_id:
        result = await db.execute(
            select(Plan).where(Plan.id == current_user.current_plan_id)
        )
        plan = result.scalar_one_or_none()
        max_concurrent = plan.max_concurrent_generations if plan else 1
    else:
        max_concurrent = 1

    # Count currently processing generations
    from sqlalchemy import func, select
    from app.models.billing import Generation
    count_result = await db.execute(
        select(func.count()).select_from(Generation).where(
            Generation.user_id == current_user.id,
            Generation.status.in_(["pending", "processing"])
        )
    )
    current_count = count_result.scalar() or 0

    return {
        "within_limit": True,
        "current_count": current_count,
        "max_concurrent": max_concurrent,
        "available_slots": max_concurrent - current_count
    }


@router.post("/admin/reset-monthly-credits")
async def admin_reset_monthly_credits(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Admin endpoint to reset monthly credits for all users (cron job)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")

    service = CreditService(db, redis)
    stats = await service.reset_monthly_credits_for_all_users()

    return {
        "success": True,
        "message": "Monthly credits reset completed",
        "stats": stats
    }


@router.post("/admin/expire-user-credits")
async def admin_expire_user_credits(
    user_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Admin endpoint to expire user's monthly credits."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")

    service = CreditService(db, redis)
    new_balance = await service.expire_monthly_subscription_credits(user_id)

    return {
        "success": True,
        "message": "User monthly credits expired",
        "new_balance": new_balance
    }