from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class CreditBalance(BaseModel):
    """Credit balance breakdown."""
    subscription: int = Field(default=0, description="Monthly subscription credits")
    purchased: int = Field(default=0, description="Purchased credits (never expire)")
    bonus: int = Field(default=0, description="Bonus/promotional credits")
    bonus_expiry: Optional[datetime] = Field(default=None, description="When bonus credits expire")
    total: int = Field(default=0, description="Total available credits")

    class Config:
        from_attributes = True


class CreditEstimateRequest(BaseModel):
    """Request to estimate credits for a service."""
    service_type: str = Field(..., description="Service type (e.g., leonardo_video_720p)")


class CreditEstimate(BaseModel):
    """Estimated credits for a service."""
    service_type: str
    credits_needed: int
    display_name: Optional[str] = None
    resolution: Optional[str] = None
    max_duration: Optional[int] = None


class CreditTransactionBase(BaseModel):
    """Base credit transaction schema."""
    amount: int = Field(..., description="Credits added (positive) or deducted (negative)")
    transaction_type: str = Field(..., description="Type: generation, purchase, subscription, refund, bonus, expiry")
    service_type: Optional[str] = None
    description: Optional[str] = None


class CreditTransactionCreate(CreditTransactionBase):
    """Create a credit transaction."""
    pass


class CreditTransactionResponse(CreditTransactionBase):
    """Credit transaction response."""
    id: UUID
    user_id: UUID
    balance_after: int
    generation_id: Optional[UUID] = None
    package_id: Optional[UUID] = None
    payment_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionHistory(BaseModel):
    """Paginated transaction history."""
    transactions: List[CreditTransactionResponse]
    total: int
    limit: int
    offset: int


class CreditPackageBase(BaseModel):
    """Base credit package schema."""
    name: str
    display_name: Optional[str] = None
    credits: int
    price_twd: Optional[Decimal] = None
    price_usd: Optional[Decimal] = None
    min_plan: Optional[str] = None
    bonus_credits: int = 0


class CreditPackageResponse(CreditPackageBase):
    """Credit package response."""
    id: UUID
    is_popular: bool = False
    is_best_value: bool = False
    is_active: bool = True

    class Config:
        from_attributes = True


class CreditPackageList(BaseModel):
    """List of available credit packages."""
    packages: List[CreditPackageResponse]
    user_plan: Optional[str] = None


class CreditPurchaseRequest(BaseModel):
    """Request to purchase credits."""
    package_id: UUID
    payment_method: str = Field(default="ecpay", description="Payment method: ecpay, paddle")


class CreditPurchaseResponse(BaseModel):
    """Response after initiating credit purchase."""
    order_id: UUID
    package_id: UUID
    credits: int
    amount: Decimal
    currency: str
    payment_url: Optional[str] = None
    status: str = "pending"


class ServicePricingBase(BaseModel):
    """Base service pricing schema."""
    service_type: str
    display_name: str
    credit_cost: int
    api_cost_usd: Decimal
    resolution: Optional[str] = None
    max_duration: Optional[int] = None
    description: Optional[str] = None


class ServicePricingResponse(ServicePricingBase):
    """Service pricing response."""
    id: UUID
    is_active: bool = True

    class Config:
        from_attributes = True


class ServicePricingList(BaseModel):
    """List of service pricing."""
    pricing: List[ServicePricingResponse]


class GenerationBase(BaseModel):
    """Base generation schema."""
    prompt_original: str
    input_image_url: Optional[str] = None
    service_type: str = "leonardo_video_720p"


class GenerationCreate(GenerationBase):
    """Create a generation request."""
    pass


class GenerationResponse(GenerationBase):
    """Generation response."""
    id: UUID
    user_id: UUID
    prompt_enhanced: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    credits_used: int = 0
    cache_hit: bool = False
    status: str = "pending"
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
