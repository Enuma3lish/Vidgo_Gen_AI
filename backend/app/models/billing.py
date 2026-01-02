from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime, Float, JSON, Text, func, DECIMAL
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class Plan(Base):
    """
    Subscription plans available for users.
    Updated to support credit-based billing system.
    """
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(50), nullable=False)  # demo, starter, pro, pro_plus
    slug = Column(String, unique=True, index=True, nullable=True)
    display_name = Column(String(100), nullable=True)  # Display name (i18n key)
    plan_type = Column(String, nullable=False, default="free")  # free, basic, pro, enterprise
    description = Column(String, nullable=True)

    # Pricing
    price = Column(DECIMAL(10, 2), nullable=True)  # Legacy field
    price_twd = Column(DECIMAL(10, 2), default=0)  # Price in TWD
    price_usd = Column(DECIMAL(10, 2), default=0)  # Price in USD
    price_monthly = Column(Float, default=0.0)
    price_yearly = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    billing_cycle = Column(String, default="monthly")

    # Credit Allocation
    monthly_credits = Column(Integer, default=0)  # Credits per month (legacy)
    weekly_credits = Column(Integer, default=0)  # Credits per week (new weekly system)
    credits_per_month = Column(Integer, default=10)  # Legacy field

    # Discounts
    topup_discount_rate = Column(DECIMAL(3, 2), default=0)  # 0.00 = no discount, 0.20 = 20% off

    # VidGo Effects Access
    can_use_effects = Column(Boolean, default=False)  # Can access VidGo Effects (GoEnhance)

    # Features & Limits
    max_video_length = Column(Integer, default=5)  # Seconds
    max_resolution = Column(String(20), default="720p")  # 720p, 1080p, 4k
    has_watermark = Column(Boolean, default=True)
    watermark = Column(Boolean, default=True)  # Legacy field
    priority_queue = Column(Boolean, default=False)
    api_access = Column(Boolean, default=False)

    # Service Limits (per month)
    pollo_limit = Column(Integer, nullable=True)  # NULL = no limit
    goenhance_limit = Column(Integer, nullable=True)

    # Feature flags
    feature_clothing_transform = Column(Boolean, default=True)
    feature_goenhance = Column(Boolean, default=True)
    feature_video_gen = Column(Boolean, default=False)
    feature_batch_processing = Column(Boolean, default=False)
    feature_custom_styles = Column(Boolean, default=False)

    # Legacy features JSON (for backward compat)
    features = Column(JSON, default={})

    # Status
    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    
    status = Column(String, default="pending") # active, pending, cancelled, expired
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    auto_renew = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("app.models.user.User", backref="subscriptions")
    plan = relationship("Plan")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number = Column(String, unique=True, index=True) # Generated ID for Humans/Payment Providers
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True)
    
    amount = Column(DECIMAL(10, 2), nullable=False)
    status = Column(String, default="pending") # pending, paid, failed
    payment_method = Column(String, nullable=True)
    payment_data = Column(JSON, default={}) # Store ECPay/Paddle return data
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    
    user = relationship("app.models.user.User", backref="orders")

class Invoice(Base):
    __tablename__ = "invoices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), unique=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    invoice_number = Column(String, unique=True)
    amount = Column(DECIMAL(10, 2))
    pdf_url = Column(String, nullable=True)
    
    issued_at = Column(DateTime(timezone=True), server_default=func.now())
    
    order = relationship("Order", backref="invoice")


class Promotion(Base):
    """
    Promotions for special events like 11/11, 12/12, Black Friday, etc.
    Controls discount rates and validity periods for credit packages.
    """
    __tablename__ = "promotions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Basic Info
    code = Column(String, unique=True, index=True, nullable=False)  # e.g., "1111_SALE", "1212_DEAL"
    name = Column(String, nullable=False)  # Display name
    name_zh = Column(String, nullable=True)  # Chinese name
    name_en = Column(String, nullable=True)  # English name
    description = Column(String, nullable=True)
    description_zh = Column(String, nullable=True)
    description_en = Column(String, nullable=True)

    # Discount Configuration
    discount_type = Column(String, default="percentage")  # percentage, fixed_amount
    discount_value = Column(Float, nullable=False)  # e.g., 50 for 50% off, or 10 for $10 off
    min_purchase_amount = Column(Float, default=0)  # Minimum order amount to apply
    max_discount_amount = Column(Float, nullable=True)  # Cap on discount (for percentage type)

    # Validity Period
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)

    # Usage Limits
    max_uses_total = Column(Integer, nullable=True)  # Total uses allowed (null = unlimited)
    max_uses_per_user = Column(Integer, default=1)  # Uses per user
    current_uses = Column(Integer, default=0)  # Track current usage count

    # Applicable To
    applicable_plans = Column(JSON, default=[])  # List of plan_ids, empty = all plans
    applicable_credit_packages = Column(JSON, default=[])  # List of package_ids, empty = all

    # Display
    banner_image_url = Column(String, nullable=True)  # Promotion banner
    badge_text = Column(String, nullable=True)  # e.g., "50% OFF", "限時優惠"
    badge_color = Column(String, default="#ff4444")  # Badge background color
    priority = Column(Integer, default=0)  # Higher = shown first

    # Status
    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)  # Show on homepage

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CreditPackage(Base):
    """
    Credit packages available for purchase.
    Can be affected by promotions.
    """
    __tablename__ = "credit_packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Package Info
    name = Column(String(100), nullable=False)  # small, medium, large, enterprise
    name_zh = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    display_name = Column(String(100), nullable=True)
    description = Column(String, nullable=True)

    # Credits & Pricing
    credits = Column(Integer, nullable=False)  # Amount of credits
    price = Column(Float, nullable=False)  # Original price (legacy)
    price_twd = Column(DECIMAL(10, 2), nullable=True)
    price_usd = Column(DECIMAL(10, 2), nullable=True)
    currency = Column(String, default="USD")

    # Restrictions
    min_plan = Column(String(50), nullable=True)  # Minimum plan required (NULL = all plans)

    # Bonus
    bonus_credits = Column(Integer, default=0)  # Extra credits (e.g., buy 100 get 10 free)

    # Display
    is_popular = Column(Boolean, default=False)  # Show "Popular" badge
    is_best_value = Column(Boolean, default=False)  # Show "Best Value" badge
    sort_order = Column(Integer, default=0)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PromotionUsage(Base):
    """
    Track promotion usage per user.
    """
    __tablename__ = "promotion_usages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    promotion_id = Column(UUID(as_uuid=True), ForeignKey("promotions.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)

    discount_amount = Column(Float, nullable=False)  # Actual discount applied

    used_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    promotion = relationship("Promotion", backref="usages")
    user = relationship("app.models.user.User", backref="promotion_usages")


class CreditTransaction(Base):
    """
    Track all credit transactions (credits added or deducted).
    """
    __tablename__ = "credit_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Transaction Details
    amount = Column(Integer, nullable=False)  # Positive = credit, Negative = debit
    balance_after = Column(Integer, nullable=False)  # Balance after transaction

    # Transaction Type
    transaction_type = Column(String(50), nullable=False)  # generation, purchase, subscription, refund, bonus, expiry

    # For generation transactions
    service_type = Column(String(50), nullable=True)  # leonardo_video, pollo_video, goenhance, runway
    generation_id = Column(UUID(as_uuid=True), nullable=True)  # Reference to generation record

    # For purchase transactions
    package_id = Column(UUID(as_uuid=True), ForeignKey("credit_packages.id"), nullable=True)
    payment_id = Column(String(255), nullable=True)  # External payment reference

    # Metadata
    description = Column(Text, nullable=True)
    extra_data = Column(JSONB, nullable=True)  # Additional data (resolution, duration, etc.)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("app.models.user.User", backref="credit_transactions")
    package = relationship("CreditPackage", backref="transactions")


class ServicePricing(Base):
    """
    Service pricing table for credit-based billing.
    Defines how many credits each service costs.
    """
    __tablename__ = "service_pricing"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    service_type = Column(String(50), unique=True, nullable=False)  # leonardo_720p, leonardo_1080p, pollo_basic, etc.
    display_name = Column(String(100), nullable=False)

    # Credit Cost
    credit_cost = Column(Integer, nullable=False)  # Credits per use

    # API Cost (for internal tracking)
    api_cost_usd = Column(DECIMAL(10, 4), nullable=False)  # Actual API cost in USD

    # Access Control
    min_plan = Column(String(50), nullable=True)  # Minimum plan required (NULL = all)
    subscribers_only = Column(Boolean, default=False)  # Requires paid subscription (VidGo Effects)

    # Metadata
    description = Column(Text, nullable=True)
    resolution = Column(String(20), nullable=True)
    max_duration = Column(Integer, nullable=True)  # Max duration in seconds

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Generation(Base):
    """
    Track all generation requests and their status.
    """
    __tablename__ = "generations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Input
    prompt_original = Column(Text, nullable=False)
    prompt_enhanced = Column(Text, nullable=True)
    input_image_url = Column(String(500), nullable=True)

    # Output
    image_url = Column(String(500), nullable=True)
    video_url = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)

    # Service Info
    service_type = Column(String(50), nullable=False)  # leonardo_video_720p, pollo_basic, etc.
    credits_used = Column(Integer, nullable=False, default=0)
    cache_hit = Column(Boolean, default=False)

    # Status
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("app.models.user.User", backref="generations")
