"""
Plan and Subscription schemas.
"""
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from enum import Enum


class PlanType(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class BillingCycle(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"
    LIFETIME = "lifetime"


class PlanFeatures(BaseModel):
    """Plan feature flags."""
    clothing_transform: bool = True
    goenhance: bool = True
    video_gen: bool = False
    batch_processing: bool = False
    custom_styles: bool = False


class PlanBase(BaseModel):
    """Base plan schema."""
    name: str
    plan_type: str = "free"  # free, basic, pro, enterprise
    description: Optional[str] = None
    price_monthly: float = 0.0
    price_yearly: float = 0.0
    currency: str = "USD"
    credits_per_month: int = 10
    max_video_length: int = 5
    max_resolution: str = "720p"
    watermark: bool = True
    priority_queue: bool = False
    api_access: bool = False


class PlanCreate(PlanBase):
    """Create plan schema."""
    feature_clothing_transform: bool = True
    feature_goenhance: bool = True
    feature_video_gen: bool = False
    feature_batch_processing: bool = False
    feature_custom_styles: bool = False


class Plan(PlanBase):
    """Plan response schema."""
    id: UUID
    is_active: bool = True
    is_featured: bool = False
    feature_clothing_transform: bool = True
    feature_goenhance: bool = True
    feature_video_gen: bool = False
    feature_batch_processing: bool = False
    feature_custom_styles: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PlanSummary(BaseModel):
    """Simplified plan for listing."""
    id: UUID
    name: str
    plan_type: str = "free"
    description: Optional[str] = None
    price_monthly: float = 0.0
    price_yearly: float = 0.0
    currency: str = "USD"
    credits_per_month: int = 10
    is_featured: bool = False

    class Config:
        from_attributes = True


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAST_DUE = "past_due"


class UserSubscriptionBase(BaseModel):
    """Base subscription schema."""
    plan_id: UUID
    billing_cycle: BillingCycle = BillingCycle.MONTHLY


class UserSubscriptionCreate(UserSubscriptionBase):
    """Create subscription schema."""
    pass


class UserSubscription(BaseModel):
    """User subscription response (compatible with billing.Subscription model)."""
    id: UUID
    user_id: UUID
    plan_id: UUID
    plan: Optional[PlanSummary] = None
    status: str = "active"
    auto_renew: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubscriptionWithPlan(BaseModel):
    """Subscription with full plan details."""
    subscription: UserSubscription
    plan: Plan


class PlansListResponse(BaseModel):
    """Response for listing all plans."""
    plans: List[Plan]
    current_subscription: Optional[UserSubscription] = None
