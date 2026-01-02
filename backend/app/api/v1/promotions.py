"""
Promotion API endpoints for managing promotions, credit packages, and discounts.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timezone
from uuid import UUID

from app.api.deps import get_db, get_current_user, get_current_active_user, get_current_superuser
from app.models.billing import Promotion, CreditPackage, PromotionUsage
from app.models.user import User
from app.schemas.promotion import (
    PromotionCreate, PromotionUpdate, PromotionResponse, PromotionPublicResponse,
    CreditPackageCreate, CreditPackageUpdate, CreditPackageResponse,
    ApplyPromotionRequest, ApplyPromotionResponse,
    ValidatePromotionRequest, ValidatePromotionResponse,
    ActivePromotionsResponse, CreditPackagesWithPromotionsResponse
)

router = APIRouter()


# ============ Helper Functions ============

def is_promotion_valid(promotion: Promotion) -> bool:
    """Check if promotion is currently valid (active and within date range)"""
    now = datetime.now(timezone.utc)
    return (
        promotion.is_active and
        promotion.start_date <= now <= promotion.end_date and
        (promotion.max_uses_total is None or promotion.current_uses < promotion.max_uses_total)
    )


def calculate_discount(promotion: Promotion, original_amount: float) -> float:
    """Calculate discount amount based on promotion type"""
    if original_amount < promotion.min_purchase_amount:
        return 0.0

    if promotion.discount_type == "percentage":
        discount = original_amount * (promotion.discount_value / 100)
        if promotion.max_discount_amount:
            discount = min(discount, promotion.max_discount_amount)
    else:  # fixed_amount
        discount = promotion.discount_value

    return min(discount, original_amount)  # Can't discount more than original


async def get_user_promotion_usage_count(
    db: AsyncSession, user_id: UUID, promotion_id: UUID
) -> int:
    """Get how many times a user has used a promotion"""
    result = await db.execute(
        select(PromotionUsage).where(
            and_(
                PromotionUsage.user_id == user_id,
                PromotionUsage.promotion_id == promotion_id
            )
        )
    )
    return len(result.scalars().all())


# ============ Public Endpoints ============

@router.get("/active", response_model=ActivePromotionsResponse)
async def get_active_promotions(db: AsyncSession = Depends(get_db)):
    """
    Get all currently active promotions (public endpoint).
    Returns promotions that are:
    - Active
    - Within their valid date range
    - Have remaining uses (if limited)
    """
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Promotion).where(
            and_(
                Promotion.is_active == True,
                Promotion.start_date <= now,
                Promotion.end_date >= now
            )
        ).order_by(Promotion.priority.desc(), Promotion.created_at.desc())
    )
    promotions = result.scalars().all()

    # Filter out promotions that have reached max uses
    valid_promotions = [
        p for p in promotions
        if p.max_uses_total is None or p.current_uses < p.max_uses_total
    ]

    # Find featured promotion
    featured = next((p for p in valid_promotions if p.is_featured), None)

    return ActivePromotionsResponse(
        promotions=[PromotionPublicResponse.model_validate(p) for p in valid_promotions],
        featured_promotion=PromotionPublicResponse.model_validate(featured) if featured else None
    )


@router.get("/packages", response_model=CreditPackagesWithPromotionsResponse)
async def get_credit_packages_with_promotions(db: AsyncSession = Depends(get_db)):
    """
    Get all active credit packages with current promotion pricing.
    """
    # Get active packages
    result = await db.execute(
        select(CreditPackage).where(CreditPackage.is_active == True)
        .order_by(CreditPackage.sort_order, CreditPackage.credits)
    )
    packages = result.scalars().all()

    # Get active promotions
    now = datetime.now(timezone.utc)
    promo_result = await db.execute(
        select(Promotion).where(
            and_(
                Promotion.is_active == True,
                Promotion.start_date <= now,
                Promotion.end_date >= now
            )
        ).order_by(Promotion.priority.desc()).limit(1)
    )
    active_promo = promo_result.scalar_one_or_none()

    # Calculate discounted prices
    package_responses = []
    for pkg in packages:
        pkg_response = CreditPackageResponse.model_validate(pkg)

        if active_promo and is_promotion_valid(active_promo):
            # Check if this package is applicable
            applicable = (
                not active_promo.applicable_credit_packages or
                str(pkg.id) in active_promo.applicable_credit_packages
            )

            if applicable:
                discount = calculate_discount(active_promo, pkg.price)
                pkg_response.discounted_price = round(pkg.price - discount, 2)
                pkg_response.discount_percentage = round((discount / pkg.price) * 100, 1)
                pkg_response.promotion_badge = active_promo.badge_text

        package_responses.append(pkg_response)

    return CreditPackagesWithPromotionsResponse(
        packages=package_responses,
        active_promotion=PromotionPublicResponse.model_validate(active_promo) if active_promo else None
    )


@router.post("/validate", response_model=ValidatePromotionResponse)
async def validate_promotion_code(
    request: ValidatePromotionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate a promotion code (public endpoint).
    """
    result = await db.execute(
        select(Promotion).where(Promotion.code == request.promotion_code.upper())
    )
    promotion = result.scalar_one_or_none()

    if not promotion:
        return ValidatePromotionResponse(
            valid=False,
            promotion=None,
            message="Invalid promotion code"
        )

    if not promotion.is_active:
        return ValidatePromotionResponse(
            valid=False,
            promotion=None,
            message="This promotion is no longer active"
        )

    now = datetime.now(timezone.utc)
    if now < promotion.start_date:
        return ValidatePromotionResponse(
            valid=False,
            promotion=PromotionPublicResponse.model_validate(promotion),
            message=f"This promotion starts on {promotion.start_date.strftime('%Y-%m-%d')}"
        )

    if now > promotion.end_date:
        return ValidatePromotionResponse(
            valid=False,
            promotion=None,
            message="This promotion has expired"
        )

    if promotion.max_uses_total and promotion.current_uses >= promotion.max_uses_total:
        return ValidatePromotionResponse(
            valid=False,
            promotion=None,
            message="This promotion has reached its usage limit"
        )

    return ValidatePromotionResponse(
        valid=True,
        promotion=PromotionPublicResponse.model_validate(promotion),
        message="Promotion code is valid"
    )


@router.post("/apply", response_model=ApplyPromotionResponse)
async def apply_promotion(
    request: ApplyPromotionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Apply a promotion code to calculate discount (requires authentication).
    This doesn't consume the promotion - that happens at payment.
    """
    result = await db.execute(
        select(Promotion).where(Promotion.code == request.promotion_code.upper())
    )
    promotion = result.scalar_one_or_none()

    if not promotion or not is_promotion_valid(promotion):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired promotion code"
        )

    # Check user usage limit
    user_usage = await get_user_promotion_usage_count(db, current_user.id, promotion.id)
    if user_usage >= promotion.max_uses_per_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You have already used this promotion {promotion.max_uses_per_user} time(s)"
        )

    # Check if applicable to the package/plan
    if request.package_id and promotion.applicable_credit_packages:
        if str(request.package_id) not in promotion.applicable_credit_packages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This promotion is not applicable to the selected package"
            )

    if request.plan_id and promotion.applicable_plans:
        if str(request.plan_id) not in promotion.applicable_plans:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This promotion is not applicable to the selected plan"
            )

    # Calculate discount
    discount = calculate_discount(promotion, request.original_amount)
    final_amount = request.original_amount - discount

    return ApplyPromotionResponse(
        success=True,
        original_amount=request.original_amount,
        discount_amount=round(discount, 2),
        final_amount=round(final_amount, 2),
        promotion_code=promotion.code,
        promotion_name=promotion.name,
        message=f"Promotion applied: {promotion.badge_text or f'{promotion.discount_value}% OFF'}"
    )


# ============ Admin Endpoints ============

@router.get("/admin/list", response_model=List[PromotionResponse])
async def list_all_promotions(
    skip: int = 0,
    limit: int = 50,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    List all promotions (admin only).
    """
    query = select(Promotion)
    if not include_inactive:
        query = query.where(Promotion.is_active == True)

    query = query.order_by(Promotion.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    promotions = result.scalars().all()

    response = []
    now = datetime.now(timezone.utc)
    for p in promotions:
        promo_response = PromotionResponse.model_validate(p)
        promo_response.is_valid = is_promotion_valid(p)
        if p.max_uses_total:
            promo_response.remaining_uses = p.max_uses_total - p.current_uses
        response.append(promo_response)

    return response


@router.post("/admin/create", response_model=PromotionResponse)
async def create_promotion(
    promotion_data: PromotionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Create a new promotion (admin only).
    """
    # Check if code already exists
    existing = await db.execute(
        select(Promotion).where(Promotion.code == promotion_data.code.upper())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Promotion code already exists"
        )

    promotion = Promotion(
        code=promotion_data.code.upper(),
        name=promotion_data.name,
        name_zh=promotion_data.name_zh,
        name_en=promotion_data.name_en,
        description=promotion_data.description,
        description_zh=promotion_data.description_zh,
        description_en=promotion_data.description_en,
        discount_type=promotion_data.discount_type,
        discount_value=promotion_data.discount_value,
        min_purchase_amount=promotion_data.min_purchase_amount,
        max_discount_amount=promotion_data.max_discount_amount,
        start_date=promotion_data.start_date,
        end_date=promotion_data.end_date,
        max_uses_total=promotion_data.max_uses_total,
        max_uses_per_user=promotion_data.max_uses_per_user,
        applicable_plans=promotion_data.applicable_plans,
        applicable_credit_packages=promotion_data.applicable_credit_packages,
        banner_image_url=promotion_data.banner_image_url,
        badge_text=promotion_data.badge_text,
        badge_color=promotion_data.badge_color,
        priority=promotion_data.priority,
        is_active=promotion_data.is_active,
        is_featured=promotion_data.is_featured
    )

    db.add(promotion)
    await db.commit()
    await db.refresh(promotion)

    return PromotionResponse.model_validate(promotion)


@router.put("/admin/{promotion_id}", response_model=PromotionResponse)
async def update_promotion(
    promotion_id: UUID,
    promotion_data: PromotionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Update a promotion (admin only).
    """
    result = await db.execute(
        select(Promotion).where(Promotion.id == promotion_id)
    )
    promotion = result.scalar_one_or_none()

    if not promotion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promotion not found"
        )

    # Update fields
    update_data = promotion_data.model_dump(exclude_unset=True)
    if "code" in update_data:
        update_data["code"] = update_data["code"].upper()

    for field, value in update_data.items():
        setattr(promotion, field, value)

    await db.commit()
    await db.refresh(promotion)

    return PromotionResponse.model_validate(promotion)


@router.delete("/admin/{promotion_id}")
async def delete_promotion(
    promotion_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Delete (deactivate) a promotion (admin only).
    """
    result = await db.execute(
        select(Promotion).where(Promotion.id == promotion_id)
    )
    promotion = result.scalar_one_or_none()

    if not promotion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promotion not found"
        )

    promotion.is_active = False
    await db.commit()

    return {"message": "Promotion deactivated successfully"}


# ============ Credit Package Admin Endpoints ============

@router.post("/admin/packages/create", response_model=CreditPackageResponse)
async def create_credit_package(
    package_data: CreditPackageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Create a new credit package (admin only).
    """
    package = CreditPackage(
        name=package_data.name,
        name_zh=package_data.name_zh,
        name_en=package_data.name_en,
        description=package_data.description,
        credits=package_data.credits,
        price=package_data.price,
        currency=package_data.currency,
        bonus_credits=package_data.bonus_credits,
        is_popular=package_data.is_popular,
        is_best_value=package_data.is_best_value,
        sort_order=package_data.sort_order
    )

    db.add(package)
    await db.commit()
    await db.refresh(package)

    return CreditPackageResponse.model_validate(package)


@router.put("/admin/packages/{package_id}", response_model=CreditPackageResponse)
async def update_credit_package(
    package_id: UUID,
    package_data: CreditPackageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Update a credit package (admin only).
    """
    result = await db.execute(
        select(CreditPackage).where(CreditPackage.id == package_id)
    )
    package = result.scalar_one_or_none()

    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credit package not found"
        )

    update_data = package_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(package, field, value)

    await db.commit()
    await db.refresh(package)

    return CreditPackageResponse.model_validate(package)


# ============ Usage Tracking (Internal) ============

@router.post("/internal/record-usage")
async def record_promotion_usage(
    promotion_id: UUID,
    user_id: UUID,
    order_id: Optional[UUID],
    discount_amount: float,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Record promotion usage after successful payment (internal/admin use).
    """
    # Increment promotion usage count
    result = await db.execute(
        select(Promotion).where(Promotion.id == promotion_id)
    )
    promotion = result.scalar_one_or_none()

    if not promotion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promotion not found"
        )

    promotion.current_uses += 1

    # Create usage record
    usage = PromotionUsage(
        promotion_id=promotion_id,
        user_id=user_id,
        order_id=order_id,
        discount_amount=discount_amount
    )
    db.add(usage)

    await db.commit()

    return {"message": "Usage recorded successfully"}
