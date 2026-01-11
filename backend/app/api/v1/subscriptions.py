"""
Subscription API Endpoints

Handles subscription management:
- Subscribe to plans (with or without payment)
- Get subscription status
- Cancel subscription (with 7-day refund window)
- Upgrade/downgrade plans

When Paddle API key is not configured:
- Subscriptions are activated immediately without payment
- Useful for development and testing
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import logging

from app.api import deps
from app.models.user import User
from app.models.billing import Plan, Subscription
from app.services.subscription_service import get_subscription_service, REFUND_ELIGIBILITY_DAYS

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
logger = logging.getLogger(__name__)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class SubscribeRequest(BaseModel):
    """Request to subscribe to a plan."""
    plan_id: str = Field(..., description="UUID of the plan to subscribe to")
    billing_cycle: str = Field("monthly", description="'monthly' or 'yearly'")
    payment_method: str = Field("paddle", description="'paddle' or 'ecpay'")


class SubscribeResponse(BaseModel):
    """Response from subscribe endpoint."""
    success: bool
    subscription_id: Optional[str] = None
    status: Optional[str] = None
    checkout_url: Optional[str] = None
    is_mock: bool = False
    message: Optional[str] = None
    error: Optional[str] = None


class SubscriptionStatusResponse(BaseModel):
    """Current subscription status."""
    success: bool
    has_subscription: bool
    subscription_id: Optional[str] = None
    status: Optional[str] = None
    plan: Optional[dict] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    auto_renew: bool = False
    refund_eligible: bool = False
    refund_days_remaining: int = 0
    credits: dict = {}


class CancelRequest(BaseModel):
    """Request to cancel subscription."""
    request_refund: bool = Field(
        False,
        description=f"Request refund (only within {REFUND_ELIGIBILITY_DAYS} days)"
    )


class CancelResponse(BaseModel):
    """Response from cancel endpoint."""
    success: bool
    subscription_id: Optional[str] = None
    status: Optional[str] = None
    refund_processed: bool = False
    refund_amount: Optional[float] = None
    active_until: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


class PlanInfo(BaseModel):
    """Plan information for listing."""
    id: str
    name: str
    display_name: Optional[str]
    description: Optional[str]
    price_monthly: float
    price_yearly: float
    monthly_credits: int
    features: dict


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/plans", response_model=List[PlanInfo])
async def list_available_plans(
    db: AsyncSession = Depends(deps.get_db)
):
    """
    List all available subscription plans.

    Returns plans with pricing and features.
    """
    result = await db.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.price_monthly)
    )
    plans = result.scalars().all()

    return [
        PlanInfo(
            id=str(p.id),
            name=p.name,
            display_name=p.display_name,
            description=p.description,
            price_monthly=float(p.price_monthly or 0),
            price_yearly=float(p.price_yearly or 0),
            monthly_credits=p.monthly_credits or p.weekly_credits or 0,
            features={
                "max_video_length": p.max_video_length,
                "max_resolution": p.max_resolution,
                "has_watermark": p.has_watermark,
                "priority_queue": p.priority_queue,
                "api_access": p.api_access,
                "can_use_effects": p.can_use_effects,
                "batch_processing": p.feature_batch_processing,
                "custom_styles": p.feature_custom_styles
            }
        )
        for p in plans
    ]


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe_to_plan(
    request: SubscribeRequest,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Subscribe to a plan.

    **Behavior:**
    - If Paddle API key is configured: Returns checkout URL for payment
    - If Paddle API key is NOT configured: Activates subscription immediately (mock mode)

    **Mock Mode:**
    When running without Paddle keys (development), subscriptions are activated
    immediately with full credits allocated. This allows testing the full user
    flow without actual payments.

    **Args:**
    - plan_id: UUID of the plan to subscribe to
    - billing_cycle: 'monthly' or 'yearly'
    - payment_method: 'paddle' (international) or 'ecpay' (Taiwan)

    **Returns:**
    - For mock mode: Activated subscription details
    - For live mode: Checkout URL to complete payment
    """
    subscription_service = get_subscription_service()

    try:
        plan_uuid = UUID(request.plan_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid plan ID format")

    result = await subscription_service.subscribe(
        db=db,
        user_id=current_user.id,
        plan_id=plan_uuid,
        billing_cycle=request.billing_cycle,
        payment_method=request.payment_method,
        skip_payment=False  # Let the service decide based on mock mode
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Subscription failed")
        )

    return SubscribeResponse(**result)


@router.post("/subscribe/direct", response_model=SubscribeResponse)
async def subscribe_directly(
    request: SubscribeRequest,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Subscribe to a plan directly without payment.

    **Use Case:**
    For development, testing, or special promotions where payment
    should be skipped.

    This endpoint always activates the subscription immediately
    regardless of Paddle configuration.
    """
    subscription_service = get_subscription_service()

    try:
        plan_uuid = UUID(request.plan_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid plan ID format")

    result = await subscription_service.subscribe(
        db=db,
        user_id=current_user.id,
        plan_id=plan_uuid,
        billing_cycle=request.billing_cycle,
        payment_method=request.payment_method,
        skip_payment=True  # Force skip payment
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Subscription failed")
        )

    return SubscribeResponse(**result)


@router.get("/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Get current subscription status.

    Returns:
    - Subscription details (plan, dates, status)
    - Credit balances
    - Refund eligibility (within 7 days of subscription)
    """
    subscription_service = get_subscription_service()

    result = await subscription_service.get_subscription_status(
        db=db,
        user_id=current_user.id
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Failed to get status")
        )

    return SubscriptionStatusResponse(**result)


@router.post("/cancel", response_model=CancelResponse)
async def cancel_subscription(
    request: CancelRequest,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Cancel current subscription.

    **Refund Policy:**
    - Refund available within 7 days of subscription start
    - Full refund is processed
    - Subscription credits are revoked on refund

    **Without Refund:**
    - Subscription remains active until end of billing period
    - Auto-renewal is disabled
    - Credits are retained until period ends

    **Args:**
    - request_refund: Set to true to request full refund (within 7 days only)
    """
    subscription_service = get_subscription_service()

    result = await subscription_service.cancel_subscription(
        db=db,
        user_id=current_user.id,
        request_refund=request.request_refund
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Cancellation failed")
        )

    return CancelResponse(**result)


@router.get("/history")
async def get_subscription_history(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Get subscription history for the user.

    Returns past and current subscriptions with details.
    """
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .order_by(Subscription.created_at.desc())
        .limit(limit)
    )
    subscriptions = result.scalars().all()

    history = []
    for sub in subscriptions:
        plan = await db.get(Plan, sub.plan_id)
        history.append({
            "id": str(sub.id),
            "plan_name": plan.name if plan else "Unknown",
            "status": sub.status,
            "start_date": sub.start_date.isoformat() if sub.start_date else None,
            "end_date": sub.end_date.isoformat() if sub.end_date else None,
            "auto_renew": sub.auto_renew,
            "created_at": sub.created_at.isoformat() if sub.created_at else None
        })

    return {
        "success": True,
        "subscriptions": history
    }


@router.get("/refund-eligibility")
async def check_refund_eligibility(
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Check if current subscription is eligible for refund.

    **Refund Policy:**
    - Refunds are available within 7 days of subscription start
    - After 7 days, cancellation is still possible but no refund

    Returns:
    - eligible: Whether refund is possible
    - days_remaining: Days left in refund window
    - reason: Explanation if not eligible
    """
    subscription_service = get_subscription_service()

    status = await subscription_service.get_subscription_status(
        db=db,
        user_id=current_user.id
    )

    if not status.get("has_subscription"):
        return {
            "eligible": False,
            "reason": "No active subscription",
            "days_remaining": 0
        }

    return {
        "eligible": status.get("refund_eligible", False),
        "days_remaining": status.get("refund_days_remaining", 0),
        "reason": None if status.get("refund_eligible") else f"Refund window ({REFUND_ELIGIBILITY_DAYS} days) has expired",
        "subscription_id": status.get("subscription_id")
    }
