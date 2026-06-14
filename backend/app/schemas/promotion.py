from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ============ Credit Package Schemas ============

class CreditPackageBase(BaseModel):
    name: str
    name_zh: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    credits: int
    price: float
    currency: str = "USD"
    bonus_credits: int = 0


class CreditPackageCreate(CreditPackageBase):
    is_popular: bool = False
    is_best_value: bool = False
    sort_order: int = 0


class CreditPackageUpdate(BaseModel):
    name: Optional[str] = None
    name_zh: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    credits: Optional[int] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    bonus_credits: Optional[int] = None
    is_popular: Optional[bool] = None
    is_best_value: Optional[bool] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class CreditPackageResponse(CreditPackageBase):
    id: UUID
    is_popular: bool
    is_best_value: bool
    sort_order: int
    is_active: bool
    created_at: datetime

    # Calculated fields (filled by API)
    discounted_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    promotion_badge: Optional[str] = None

    class Config:
        from_attributes = True


# ============ Promotion Schemas ============

class PromotionBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str
    name_zh: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    description_zh: Optional[str] = None
    description_en: Optional[str] = None


class PromotionCreate(PromotionBase):
    discount_type: str = "percentage"  # percentage, fixed_amount
    discount_value: float = Field(..., gt=0)
    min_purchase_amount: float = 0
    max_discount_amount: Optional[float] = None

    start_date: datetime
    end_date: datetime

    max_uses_total: Optional[int] = None
    max_uses_per_user: int = 1

    applicable_plans: List[str] = []  # List of plan IDs
    applicable_credit_packages: List[str] = []  # List of package IDs

    banner_image_url: Optional[str] = None
    badge_text: Optional[str] = None
    badge_color: str = "#ff4444"
    priority: int = 0

    is_active: bool = True
    is_featured: bool = False


class PromotionUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    name_zh: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    description_zh: Optional[str] = None
    description_en: Optional[str] = None

    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    min_purchase_amount: Optional[float] = None
    max_discount_amount: Optional[float] = None

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    max_uses_total: Optional[int] = None
    max_uses_per_user: Optional[int] = None

    applicable_plans: Optional[List[str]] = None
    applicable_credit_packages: Optional[List[str]] = None

    banner_image_url: Optional[str] = None
    badge_text: Optional[str] = None
    badge_color: Optional[str] = None
    priority: Optional[int] = None

    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None


class PromotionResponse(PromotionBase):
    id: UUID
    discount_type: str
    discount_value: float
    min_purchase_amount: float
    max_discount_amount: Optional[float]

    start_date: datetime
    end_date: datetime

    max_uses_total: Optional[int]
    max_uses_per_user: int
    current_uses: int

    applicable_plans: List[str]
    applicable_credit_packages: List[str]

    banner_image_url: Optional[str]
    badge_text: Optional[str]
    badge_color: str
    priority: int

    is_active: bool
    is_featured: bool
    created_at: datetime

    # Computed fields
    is_valid: Optional[bool] = None  # Currently within date range
    remaining_uses: Optional[int] = None  # max_uses_total - current_uses

    class Config:
        from_attributes = True


class PromotionPublicResponse(BaseModel):
    """Public promotion info (no sensitive data)"""
    id: UUID
    code: str
    name: str
    name_zh: Optional[str]
    name_en: Optional[str]
    description: Optional[str]
    description_zh: Optional[str]
    description_en: Optional[str]

    discount_type: str
    discount_value: float

    start_date: datetime
    end_date: datetime

    banner_image_url: Optional[str]
    badge_text: Optional[str]
    badge_color: str

    is_featured: bool

    class Config:
        from_attributes = True


# ============ Apply Promotion Schemas ============

class ApplyPromotionRequest(BaseModel):
    promotion_code: str
    package_id: Optional[UUID] = None
    plan_id: Optional[UUID] = None
    original_amount: float


class ApplyPromotionResponse(BaseModel):
    success: bool
    original_amount: float
    discount_amount: float
    final_amount: float
    promotion_code: str
    promotion_name: str
    message: Optional[str] = None


class ValidatePromotionRequest(BaseModel):
    promotion_code: str


class ValidatePromotionResponse(BaseModel):
    valid: bool
    promotion: Optional[PromotionPublicResponse] = None
    message: str


# ============ List Responses ============

class ActivePromotionsResponse(BaseModel):
    promotions: List[PromotionPublicResponse]
    featured_promotion: Optional[PromotionPublicResponse] = None


class CreditPackagesWithPromotionsResponse(BaseModel):
    packages: List[CreditPackageResponse]
    active_promotion: Optional[PromotionPublicResponse] = None
