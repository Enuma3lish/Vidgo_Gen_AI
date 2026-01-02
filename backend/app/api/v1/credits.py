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
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.api.deps import get_db, get_current_user, get_current_active_user, get_redis
from app.services.credit_service import CreditService
from app.models.user import User
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
    Returns payment URL for ECPay or Paddle.
    """
    from sqlalchemy import select
    from app.models.billing import CreditPackage, Order
    import uuid

    # Get package
    result = await db.execute(
        select(CreditPackage).where(
            CreditPackage.id == purchase.package_id,
            CreditPackage.is_active == True
        )
    )
    package = result.scalar_one_or_none()

    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    # Check if user's plan qualifies for this package
    service = CreditService(db)
    available_packages = await service.get_packages_for_user(str(current_user.id))
    if package not in available_packages:
        raise HTTPException(
            status_code=403,
            detail="Your current plan does not qualify for this package"
        )

    # Determine amount based on payment method
    if purchase.payment_method == "ecpay":
        amount = package.price_twd or package.price
        currency = "TWD"
    else:  # paddle
        amount = package.price_usd or package.price
        currency = "USD"

    # Create order
    order = Order(
        order_number=f"CR-{uuid.uuid4().hex[:8].upper()}",
        user_id=current_user.id,
        amount=amount,
        status="pending",
        payment_method=purchase.payment_method,
        payment_data={
            "package_id": str(package.id),
            "credits": package.credits,
            "bonus_credits": package.bonus_credits
        }
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    # Generate payment URL based on method
    payment_url = None
    if purchase.payment_method == "ecpay":
        # ECPay integration would generate payment URL here
        # For now, return a placeholder
        payment_url = f"/api/v1/payments/ecpay/checkout/{order.order_number}"
    else:
        # Paddle integration would generate payment URL here
        payment_url = f"/api/v1/payments/paddle/checkout/{order.order_number}"

    return CreditPurchaseResponse(
        order_id=order.id,
        package_id=package.id,
        credits=package.credits + package.bonus_credits,
        amount=amount,
        currency=currency,
        payment_url=payment_url,
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
