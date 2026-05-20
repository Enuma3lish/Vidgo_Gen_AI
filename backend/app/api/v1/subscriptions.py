"""
Subscription API Endpoints

Handles subscription management:
- Subscribe to plans (with or without payment)
- Get subscription status
- Cancel subscription (with 7-day refund window)
- Upgrade/downgrade plans

When PayPal credentials are not configured:
- Subscriptions are activated immediately without payment
- Useful for development and testing
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import logging

from app.api import deps
from app.core.config import get_settings
from app.models.user import User
from app.models.billing import Plan, Subscription, Order, Invoice
from app.services.subscription_service import get_subscription_service, REFUND_ELIGIBILITY_DAYS
from app.services.paypal_service import get_paypal_service
from app.services.payment_routing import infer_payment_route
from app.core.public_plans import can_list_public_plan, plan_monthly_price
from app.core.test_plans import TEST_PRO_PLAN_DEFAULTS, can_access_test_pro_plan, is_test_pro_plan

settings = get_settings()

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
logger = logging.getLogger(__name__)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class SubscribeRequest(BaseModel):
    """Request to subscribe to a plan."""
    plan_id: str = Field(..., description="UUID of the plan to subscribe to")
    billing_cycle: str = Field("monthly", description="'monthly' or 'yearly'")
    payment_method: str = Field("paypal", description="'paypal' or 'ecpay'")
    action: Optional[str] = Field(
        None,
        description=(
            "Optional admin action. Pass 'refresh' alongside superuser auth "
            "to re-grant monthly credits on the current plan. Omitted or "
            "non-admin callers get the default subscribe behaviour."
        ),
    )


class SubscribeResponse(BaseModel):
    """Response from subscribe endpoint."""
    success: bool
    subscription_id: Optional[str] = None
    order_number: Optional[str] = None
    status: Optional[str] = None
    checkout_url: Optional[str] = None
    payment_method: Optional[str] = None
    ecpay_form: Optional[dict] = None  # ECPay form data (action_url + params)
    is_mock: bool = False
    is_upgrade: bool = False
    effective_date: Optional[str] = None  # For scheduled downgrades
    credits_allocated: Optional[int] = None
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
    pending_downgrade: Optional[dict] = None
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
    refund_requires_manual: bool = False
    invoice_voided: Optional[bool] = None
    invoice_void_required_manual: bool = False
    active_until: Optional[str] = None
    work_retention_until: Optional[str] = None  # 7-day work download deadline
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
    currency: str = "TWD"
    is_test_only: bool = False
    monthly_credits: int
    features: dict


# =============================================================================
# ENDPOINTS
# =============================================================================

# Default production plans to ensure pricing page always has data (TWD for NT$ display).
# Keep this aligned with scripts.seed_new_pricing_tiers.NEW_PLAN_DATA.
DEFAULT_VIDGO_PLANS = [
    {"name": "basic", "display_name": "基礎進階版", "slug": "basic", "plan_type": "basic", "price_monthly": 699.0, "price_yearly": 6990.0, "price_twd": 699, "price_usd": 22, "monthly_credits": 7000, "weekly_credits": 0, "max_resolution": "720p", "has_watermark": True, "priority_queue": False, "api_access": False, "can_use_effects": False, "feature_batch_processing": False, "feature_custom_styles": False, "social_media_batch_posting": False, "enterprise_features": False, "max_concurrent_generations": 1, "allowed_models": ["default"], "pollo_limit": 0, "goenhance_limit": 0, "description": "引流款，讓用戶體驗基本圖文生成，僅限 default 模型"},
    {"name": "pro", "display_name": "專業版", "slug": "pro", "plan_type": "pro", "price_monthly": 999.0, "price_yearly": 9990.0, "price_twd": 999, "price_usd": 32, "monthly_credits": 10000, "weekly_credits": 0, "max_resolution": "1080p", "has_watermark": False, "priority_queue": False, "api_access": False, "can_use_effects": True, "feature_batch_processing": True, "feature_custom_styles": False, "social_media_batch_posting": True, "enterprise_features": False, "max_concurrent_generations": 3, "allowed_models": ["default", "wan_pro", "gemini_pro"], "pollo_limit": 50, "goenhance_limit": None, "description": "主力銷售方案，開放高級模型與社交媒體一鍵批次發布"},
    {"name": "premium", "display_name": "尊榮版", "slug": "premium", "plan_type": "premium", "price_monthly": 1699.0, "price_yearly": 16990.0, "price_twd": 1699, "price_usd": 55, "monthly_credits": 18000, "weekly_credits": 0, "max_resolution": "4k", "has_watermark": False, "priority_queue": True, "api_access": False, "can_use_effects": True, "feature_batch_processing": True, "feature_custom_styles": False, "social_media_batch_posting": True, "enterprise_features": False, "max_concurrent_generations": 5, "allowed_models": ["default", "wan_pro", "gemini_pro"], "pollo_limit": 100, "goenhance_limit": None, "description": "針對重度創作者，包含 Pro 所有功能，外加優先任務處理佇列"},
    {"name": "enterprise", "display_name": "企業旗艦版", "slug": "enterprise", "plan_type": "enterprise", "price_monthly": 15000.0, "price_yearly": 150000.0, "price_twd": 15000, "price_usd": 485, "monthly_credits": 160000, "weekly_credits": 0, "max_resolution": "4k", "has_watermark": False, "priority_queue": True, "api_access": True, "can_use_effects": True, "feature_batch_processing": True, "feature_custom_styles": True, "social_media_batch_posting": True, "enterprise_features": True, "max_concurrent_generations": 10, "allowed_models": ["default", "wan_pro", "gemini_pro", "veo"], "pollo_limit": None, "goenhance_limit": None, "description": "全功能解鎖、專屬企業素材庫、自訂浮水印"},
    TEST_PRO_PLAN_DEFAULTS,
]


async def ensure_vidgo_plans(db: AsyncSession) -> None:
    """
    Ensure every production plan in DEFAULT_VIDGO_PLANS exists and deactivate
    legacy public plans so PayPal plan mapping only needs basic/pro/premium/
    enterprise keys.
    """
    existing_result = await db.execute(select(Plan))
    existing_plans = existing_result.scalars().all()
    existing_by_name = {p.name: p for p in existing_plans}
    default_names = {data["name"] for data in DEFAULT_VIDGO_PLANS}

    added = 0
    changed = False
    for data in DEFAULT_VIDGO_PLANS:
        name = data["name"]
        if name in existing_by_name:
            existing = existing_by_name[name]
            if not existing.is_active:
                existing.is_active = True
                changed = True
            for key, value in data.items():
                if getattr(existing, key, None) != value:
                    setattr(existing, key, value)
                    changed = True
            continue
        plan = Plan(**data)
        db.add(plan)
        added += 1

    for plan in existing_plans:
        if plan.name not in default_names and plan.is_active and not is_test_pro_plan(plan):
            plan.is_active = False
            changed = True

    if added or changed:
        await db.commit()


@router.get("/payment-route")
async def get_payment_route(request: Request):
    """
    Geo-based payment routing (VidGo 2.0 spec, Section 四).

    Returns the recommended currency + payment gateway based on caller IP:
      - 台灣 (TW)   → currency=TWD, gateway=ecpay (綠界)
      - 海外 (其他) → currency=USD, gateway=paypal

    Frontend uses this to pre-select the right checkout flow before the
    user reaches the payment step.
    """
    route = infer_payment_route(request)
    return {
        "country": route.country,
        "currency": route.currency,
        "gateway": route.gateway,
    }


@router.get("/plans", response_model=List[PlanInfo])
async def list_available_plans(
    db: AsyncSession = Depends(deps.get_db),
    current_user: Optional[User] = Depends(deps.get_current_user_optional_lenient),
):
    """
    List all available subscription plans.

    Returns plans with pricing and features. Ensures default plans exist if DB is empty.
    Prices are in TWD for NT$ display on frontend.
    """
    await ensure_vidgo_plans(db)
    result = await db.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.price_monthly)
    )
    plans = result.scalars().all()
    can_view_test_plan = can_access_test_pro_plan(current_user.email if current_user else None)
    if not can_view_test_plan and current_user and current_user.current_plan_id:
        can_view_test_plan = any(
            is_test_pro_plan(plan) and plan.id == current_user.current_plan_id
            for plan in plans
        )
    plans = [plan for plan in plans if can_list_public_plan(plan, can_view_test_plan)]

    def _monthly(plan: Plan) -> float:
        return plan_monthly_price(plan)

    def _yearly(plan: Plan) -> float:
        v = plan.price_yearly
        if v is not None and float(v) > 0:
            return float(v)
        m = _monthly(plan)
        return m * 10.0 if m > 0 else 0.0

    return [
        PlanInfo(
            id=str(plan.id),
            name=plan.name,
            display_name=plan.display_name,
            description=plan.description,
            price_monthly=_monthly(plan),
            price_yearly=_yearly(plan),
            currency=plan.currency or "TWD",
            is_test_only=is_test_pro_plan(plan),
            monthly_credits=plan.monthly_credits or plan.weekly_credits or 0,
            features={
                "max_video_length": plan.max_video_length,
                "max_resolution": plan.max_resolution,
                "has_watermark": plan.has_watermark,
                "priority_queue": plan.priority_queue,
                "api_access": plan.api_access,
                "can_use_effects": plan.can_use_effects,
                "batch_processing": plan.feature_batch_processing,
                "custom_styles": plan.feature_custom_styles
            }
        )
        for plan in plans
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
    - If PayPal credentials are configured: Returns checkout URL for payment
    - If ECPay credentials are configured: Returns ECPay form data
    - If NEITHER is configured: Activates subscription immediately (mock mode)

    **Mock Mode:**
    When running without payment keys (development/GCP without keys),
    subscriptions are activated immediately with full credits allocated.
    This allows testing the full user flow without actual payments.

    **Args:**
    - plan_id: UUID of the plan to subscribe to
    - billing_cycle: 'monthly' or 'yearly'
    - payment_method: 'paypal' (international) or 'ecpay' (Taiwan)

    **Returns:**
    - For mock mode: Activated subscription details
    - For live mode: Checkout URL to complete payment
    """
    subscription_service = get_subscription_service()

    try:
        plan_uuid = UUID(request.plan_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid plan ID format")

    plan_for_policy = await db.get(Plan, plan_uuid)
    if not plan_for_policy:
        raise HTTPException(status_code=404, detail="Plan not found")

    if is_test_pro_plan(plan_for_policy) and request.payment_method != "ecpay":
        raise HTTPException(status_code=400, detail="Test plan requires ECPay checkout")

    # Check if payment providers are actually configured
    paypal = get_paypal_service()
    ecpay_configured = bool(
        settings.ECPAY_MERCHANT_ID and settings.ECPAY_HASH_KEY and settings.ECPAY_HASH_IV
    )

    # If neither payment provider is configured, force mock/direct mode
    force_skip = False
    if paypal.is_mock and not ecpay_configured:
        if not settings.PAYMENT_MOCK_COMPLETION_ENABLED:
            raise HTTPException(status_code=503, detail="Payment checkout is temporarily unavailable")
        logger.info("No payment providers configured — activating subscription in explicit mock mode")
        force_skip = True
    elif request.payment_method == 'ecpay' and not ecpay_configured:
        if not settings.PAYMENT_MOCK_COMPLETION_ENABLED:
            raise HTTPException(status_code=503, detail="ECPay checkout is temporarily unavailable")
        logger.info("ECPay not configured — falling back to explicit mock mode")
        force_skip = True

    # Note: superusers go through the same PayPal / ECPay flow as regular
    # users. The previous admin-bypass branch silently activated plans
    # without ever opening PayPal, which made admins clicking PayPal see
    # "nothing happen" (no spinner, no redirect, no error) and broke admin
    # PayPal testing. If an admin needs to grant a plan without payment,
    # the `/subscribe/direct` endpoint or admin dashboard is the right path.

    result = await subscription_service.subscribe(
        db=db,
        user_id=current_user.id,
        plan_id=plan_uuid,
        billing_cycle=request.billing_cycle,
        payment_method=request.payment_method,
        skip_payment=force_skip,  # Force skip when no payment provider available
        action=request.action,
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
    regardless of PayPal configuration.
    """
    if not getattr(current_user, "is_superuser", False) and not settings.PAYMENT_MOCK_COMPLETION_ENABLED:
        raise HTTPException(status_code=403, detail="Direct subscription activation is disabled")

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
@router.get("/current", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Get current subscription status.

    Also available as `/subscriptions/current` (alias) for frontends that
    follow REST naming conventions.

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


# =============================================================================
# INVOICES (User-facing list & PDF)
# =============================================================================

class InvoiceItem(BaseModel):
    """Single invoice/order for list."""
    order_id: str
    order_number: str
    amount: float
    currency: str
    status: str
    paid_at: Optional[str] = None
    invoice_number: Optional[str] = None
    has_pdf: bool = False


class InvoiceListResponse(BaseModel):
    success: bool
    invoices: List[InvoiceItem]


class InvoicePdfResponse(BaseModel):
    success: bool
    pdf_url: Optional[str] = None
    error: Optional[str] = None


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    List billable orders (invoices) for the current user, most recent first.

    Includes both paid orders (real payments) and complimentary orders
    (direct activations used for admin/QA flows) so the dashboard and
    cancellation flow have a consistent audit trail (VG-BUG-D).
    """
    result = await db.execute(
        select(Order)
        .where(
            Order.user_id == current_user.id,
            Order.status.in_(["paid", "complimentary"]),
        )
        .order_by(Order.paid_at.desc().nullslast(), Order.created_at.desc())
        .limit(limit)
    )
    orders = result.scalars().all()

    # Load invoices for these orders (order_id -> invoice)
    inv_result = await db.execute(
        select(Invoice).where(Invoice.order_id.in_([o.id for o in orders]))
    )
    invoices_by_order = {str(inv.order_id): inv for inv in inv_result.scalars().all()}

    items = []
    for order in orders:
        inv = invoices_by_order.get(str(order.id))
        transaction_id = (order.payment_data or {}).get("paypal_transaction_id") or (order.payment_data or {}).get("transaction_id")
        items.append(InvoiceItem(
            order_id=str(order.id),
            order_number=order.order_number or str(order.id),
            amount=float(order.amount) if order.amount else 0,
            currency=(order.payment_data or {}).get("currency_code", "USD"),
            status=order.status or "paid",
            paid_at=order.paid_at.isoformat() if order.paid_at else None,
            invoice_number=inv.invoice_number if inv else None,
            has_pdf=bool(transaction_id or (inv and inv.pdf_url))
        ))

    return InvoiceListResponse(success=True, invoices=items)


@router.get("/invoices/{order_id}/pdf", response_model=InvoicePdfResponse)
async def get_invoice_pdf(
    order_id: str,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Get a temporary PDF URL for the invoice of a paid order.

    The URL typically expires after 1 hour (PayPal). Open in new tab or download.
    """
    try:
        order_uuid = UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    result = await db.execute(
        select(Order).where(Order.id == order_uuid, Order.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "paid":
        raise HTTPException(status_code=400, detail="Invoice only available for paid orders")

    # Prefer stored pdf_url (Invoice table), then PayPal
    inv_result = await db.execute(select(Invoice).where(Invoice.order_id == order.id))
    inv = inv_result.scalar_one_or_none()
    if inv and inv.pdf_url:
        return InvoicePdfResponse(success=True, pdf_url=inv.pdf_url)

    transaction_id = (order.payment_data or {}).get("paypal_transaction_id") or (order.payment_data or {}).get("transaction_id")
    if not transaction_id:
        return InvoicePdfResponse(success=False, error="No invoice PDF available for this order")

    paypal = get_paypal_service()
    pdf_result = await paypal.get_invoice_pdf_url(str(transaction_id))
    if not pdf_result.get("success") or not pdf_result.get("pdf_url"):
        return InvoicePdfResponse(
            success=False,
            error=pdf_result.get("error", "Failed to retrieve invoice PDF")
        )
    return InvoicePdfResponse(success=True, pdf_url=pdf_result["pdf_url"])


@router.get("/plan-features")
async def get_plan_features(
    plan_id: Optional[str] = Query(
        None,
        description=(
            "UUID of a plan to preview. Omit to get the current user's "
            "active plan features."
        ),
    ),
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Return plan feature flags for frontend UI gating.

    When `plan_id` is supplied the endpoint previews THAT plan's features so
    the frontend can render comparison tables before upgrade (VG-BUG-F).
    Omitting `plan_id` returns the caller's current plan features.
    """
    # Plan preview mode — look up the requested plan directly, no subscription
    # check. Makes upgrade-compare UI possible.
    if plan_id:
        try:
            plan_uuid = UUID(plan_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid plan ID format")
        plan = await db.get(Plan, plan_uuid)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        return {
            "success": True,
            "has_plan": True,
            "preview": True,
            "plan_name": plan.name,
            "plan_type": plan.plan_type,
            "features": {
                "max_resolution": plan.max_resolution or "720p",
                "has_watermark": plan.has_watermark if plan.has_watermark is not None else True,
                "can_use_effects": plan.can_use_effects or False,
                "batch_processing": plan.feature_batch_processing or False,
                "custom_styles": plan.feature_custom_styles or False,
                "priority_queue": plan.priority_queue or False,
                "api_access": plan.api_access or False,
            },
            "monthly_credits": plan.monthly_credits or 0,
            "weekly_credits": plan.weekly_credits or 0,
            "price_monthly": float(plan.price_monthly) if plan.price_monthly else 0,
            "price_yearly": float(plan.price_yearly) if plan.price_yearly else 0,
        }

    from app.api.deps import get_user_plan_features
    features = await get_user_plan_features(current_user, db)

    if not features:
        return {
            "success": True,
            "has_plan": False,
            "plan_name": None,
            "features": {
                "max_resolution": "720p",
                "has_watermark": True,
                "can_use_effects": False,
                "batch_processing": False,
                "custom_styles": False,
                "priority_queue": False,
                "api_access": False,
            }
        }

    return {
        "success": True,
        "has_plan": True,
        "plan_name": features["plan_name"],
        "plan_type": features["plan_type"],
        "features": {
            "max_resolution": features["max_resolution"],
            "has_watermark": features["has_watermark"],
            "can_use_effects": features["can_use_effects"],
            "batch_processing": features["batch_processing"],
            "custom_styles": features["custom_styles"],
            "priority_queue": features["priority_queue"],
            "api_access": features["api_access"],
        }
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
