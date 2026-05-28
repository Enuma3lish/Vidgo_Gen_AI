"""
Credit System API Endpoints

Endpoints:
- GET /credits/balance - Get current credit balance breakdown
- GET /credits/transactions - Get credit transaction history
- POST /credits/estimate - Estimate credits for a generation
- GET /credits/packages - Get available credit packages
- POST /credits/purchase - Purchase credit package
- GET /credits/pricing - Get service pricing table
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

from app.api.deps import get_db, get_current_user, get_current_active_user, get_redis
from app.services.credit_service import CreditService, OFFICIAL_CREDIT_PACKAGE_NAMES
from app.models.user import User
from app.core.config import settings
from app.services.ecpay.client import ECPayClient
from app.schemas.credit import (
    CreditBalance,
    CreditEstimate,
    CreditEstimateRequest,
    CreditPackageList,
    CreditPackageResponse,
    CreditPurchaseRequest,
    CreditPurchaseResponse,
    TransactionHistory,
    CreditTransactionResponse,
    ServicePricingList,
    ServicePricingResponse,
)

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/balance", response_model=CreditBalance)
async def get_balance(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Get current credit balance breakdown."""
    service = CreditService(db, redis)
    balance = await service.get_balance(str(current_user.id))
    return CreditBalance(**balance)


@router.post("/estimate", response_model=CreditEstimate)
async def estimate_generation_cost(
    request: CreditEstimateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Estimate credits needed for a generation."""
    service = CreditService(db)
    pricing = await service.get_service_pricing(request.service_type)

    if not pricing:
        raise HTTPException(
            status_code=404,
            detail=f"Service type '{request.service_type}' not found"
        )

    return CreditEstimate(
        service_type=request.service_type,
        credits_needed=pricing.credit_cost,
        display_name=pricing.display_name,
        resolution=pricing.resolution,
        max_duration=pricing.max_duration
    )


@router.get("/transactions", response_model=TransactionHistory)
async def get_transactions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    transaction_type: str = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get credit transaction history."""
    service = CreditService(db)
    transactions, total = await service.get_transactions(
        str(current_user.id),
        limit=limit,
        offset=offset,
        transaction_type=transaction_type
    )

    return TransactionHistory(
        transactions=[
            CreditTransactionResponse(
                id=t.id,
                user_id=t.user_id,
                amount=t.amount,
                balance_after=t.balance_after,
                transaction_type=t.transaction_type,
                service_type=t.service_type,
                generation_id=t.generation_id,
                package_id=t.package_id,
                payment_id=t.payment_id,
                description=t.description,
                created_at=t.created_at
            )
            for t in transactions
        ],
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/packages", response_model=CreditPackageList)
async def get_packages(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get available credit packages for user's plan."""
    service = CreditService(db)
    packages = await service.get_packages_for_user(str(current_user.id))

    # Get user's plan name
    user_plan = None
    if current_user.current_plan_id:
        from app.models.billing import Plan
        from sqlalchemy import select
        result = await db.execute(
            select(Plan).where(Plan.id == current_user.current_plan_id)
        )
        plan = result.scalar_one_or_none()
        if plan:
            user_plan = plan.name

    return CreditPackageList(
        packages=[
            CreditPackageResponse(
                id=pkg.id,
                name=pkg.name,
                display_name=pkg.display_name or pkg.name_en or pkg.name,
                credits=pkg.credits,
                price_twd=pkg.price_twd,
                price_usd=pkg.price_usd,
                min_plan=pkg.min_plan,
                bonus_credits=pkg.bonus_credits,
                is_popular=pkg.is_popular,
                is_best_value=pkg.is_best_value,
                is_active=pkg.is_active
            )
            for pkg in packages
        ],
        user_plan=user_plan
    )


@router.post("/purchase", response_model=CreditPurchaseResponse)
async def purchase_credits(
    purchase: CreditPurchaseRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Purchase credit package.
    Returns payment URL for ECPay or PayPal.
    """
    from sqlalchemy import select
    from app.models.billing import CreditPackage, Order
    import uuid

    # Get package
    result = await db.execute(
        select(CreditPackage).where(
            CreditPackage.id == purchase.package_id,
            CreditPackage.is_active == True,
            CreditPackage.name.in_(OFFICIAL_CREDIT_PACKAGE_NAMES),
        )
    )
    package = result.scalar_one_or_none()

    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    # Check if user's plan qualifies for this package. Return a structured
    # 403 with the required plan + the user's current plan so the frontend
    # can render an "Upgrade to <plan>" CTA instead of a generic error toast.
    service = CreditService(db)
    available_packages = await service.get_packages_for_user(str(current_user.id))
    if package not in available_packages:
        user_plan_name = None
        if current_user.current_plan_id:
            from app.models.billing import Plan
            plan_row = await db.execute(
                select(Plan).where(Plan.id == current_user.current_plan_id)
            )
            plan_obj = plan_row.scalar_one_or_none()
            if plan_obj:
                user_plan_name = plan_obj.name
        raise HTTPException(
            status_code=403,
            detail={
                "error": "plan_upgrade_required",
                "message": "Your current plan does not qualify for this package.",
                "required_plan": package.min_plan,
                "current_plan": user_plan_name or "free",
                "package_name": package.name,
            },
        )

    # Determine amount based on payment method.
    #
    # IMPORTANT: PayPal must always use ``package.price_usd`` as a hardcoded
    # value — do NOT compute it from ``price_twd`` via runtime FX conversion.
    # PayPal's ~3% processing fee plus exchange-rate margin (~8% spread vs
    # mid-market) means an auto-converted price quietly eats the margin
    # every time the rate drifts. Each pack carries its own USD column so
    # the price the customer sees is the price ops decided, period.
    if purchase.payment_method == "ecpay":
        amount = package.price_twd or package.price
        currency = "TWD"
    else:  # paypal
        amount = package.price_usd or package.price
        currency = "USD"

    # Create order. Alphanumeric-only (no hyphens) so ECPay accepts it as
    # MerchantTradeNo when the credit purchase uses the ECPay gateway.
    order = Order(
        order_number=f"CR{uuid.uuid4().hex[:12].upper()}",
        user_id=current_user.id,
        amount=amount,
        status="pending",
        payment_method=purchase.payment_method,
        payment_data={
            "package_id": str(package.id),
            "package_name": package.name,
            "credits": package.credits,
            "bonus_credits": package.bonus_credits,
            "currency": currency,
        }
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    payment_url = None
    ecpay_form = None
    if purchase.payment_method == "ecpay":
        if not settings.ECPAY_MERCHANT_ID or not settings.ECPAY_HASH_KEY or not settings.ECPAY_HASH_IV:
            raise HTTPException(status_code=500, detail="ECPay payment not configured")

        from datetime import datetime

        ecpay_client = ECPayClient(
            merchant_id=settings.ECPAY_MERCHANT_ID,
            hash_key=settings.ECPAY_HASH_KEY,
            hash_iv=settings.ECPAY_HASH_IV,
            payment_url=settings.ECPAY_PAYMENT_URL,
        )
        payment_url = settings.ECPAY_PAYMENT_URL
        ecpay_form = ecpay_client.create_payment(
            merchant_trade_no=order.order_number,
            merchant_trade_date=datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            total_amount=int(amount),
            trade_desc=f"VidGo {package.display_name or package.name} credits",
            item_name=f"VidGo {package.display_name or package.name} {package.credits} credits",
            return_url=f"{settings.BACKEND_URL}/api/v1/payments/ecpay/callback",
            order_result_url=f"{settings.BACKEND_URL}/api/v1/payments/ecpay/result-redirect?order={order.order_number}",
            client_back_url=f"{settings.FRONTEND_URL}/pricing",
            choose_payment="Credit",
        )
    elif purchase.payment_method == "paypal":
        # One-shot PayPal Orders v2 checkout for credit packs. Anyone who
        # doesn't want to subscribe should still be able to top up credits
        # via PayPal; previously this branch returned only a placeholder URL
        # and the user got a hard 503 from /payments/paypal/checkout because
        # it required a subscription paypal_plan_id. We now create the
        # PayPal order here directly with amount_usd; the existing
        # PAYMENT.CAPTURE.COMPLETED webhook already credits the user based
        # on order.payment_data.package_id.
        try:
            from app.services.paypal_service import get_paypal_service
            paypal_service = get_paypal_service()
            paypal_result = await paypal_service.create_checkout_session(
                user_id=current_user.id,
                user_email=current_user.email,
                plan_id=f"credits:{package.name}",
                price_id=f"sku_{order.order_number}",
                billing_cycle="one-time",
                success_url=f"{settings.FRONTEND_URL}/subscription/success?order={order.order_number}",
                cancel_url=f"{settings.FRONTEND_URL}/pricing",
                amount_usd=float(amount),
            )
            if not paypal_result.get("success"):
                # Roll the pending order back so the user can retry without
                # hitting a stale duplicate when they click again.
                order.status = "failed"
                await db.commit()
                raise HTTPException(
                    status_code=502,
                    detail=paypal_result.get("error") or "PayPal checkout failed",
                )
            order.payment_data["paypal_transaction_id"] = paypal_result.get("transaction_id")
            await db.commit()
            payment_url = paypal_result.get("checkout_url")
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("PayPal credit checkout failed: %s", exc, exc_info=True)
            order.status = "failed"
            await db.commit()
            raise HTTPException(status_code=502, detail="PayPal checkout is temporarily unavailable")
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported payment_method: {purchase.payment_method}",
        )

    return CreditPurchaseResponse(
        order_id=order.id,
        package_id=package.id,
        credits=package.credits,
        amount=amount,
        currency=currency,
        payment_url=payment_url,
        payment_method=purchase.payment_method,
        ecpay_form=ecpay_form,
        is_mock=False,
        status="pending"
    )


@router.get("/pricing", response_model=ServicePricingList)
async def get_pricing(
    db: AsyncSession = Depends(get_db)
):
    """Get service pricing table."""
    service = CreditService(db)
    pricing_list = await service.get_all_pricing()

    return ServicePricingList(
        pricing=[
            ServicePricingResponse(
                id=p.id,
                service_type=p.service_type,
                display_name=p.display_name,
                credit_cost=p.credit_cost,
                api_cost_usd=p.api_cost_usd,
                resolution=p.resolution,
                max_duration=p.max_duration,
                description=p.description,
                is_active=p.is_active
            )
            for p in pricing_list
        ]
    )


@router.post("/add")
async def add_credits_admin(
    user_id: str,
    amount: int,
    credit_type: str = "bonus",
    description: str = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Add credits to a user (admin only).
    For testing and admin purposes.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")

    service = CreditService(db, redis)

    try:
        new_balance = await service.add_credits(
            user_id=user_id,
            amount=amount,
            credit_type=credit_type,
            description=description or f"Admin added {amount} {credit_type} credits"
        )
        return {"success": True, "new_balance": new_balance}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
