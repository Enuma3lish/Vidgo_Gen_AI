from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime, Float, JSON, func, DECIMAL
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class Plan(Base):
    """
    Subscription plans available for users.
    """
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=True)
    plan_type = Column(String, nullable=False, default="free")  # free, basic, pro, enterprise
    description = Column(String, nullable=True)

    # Pricing (keep old price for backward compat, add new monthly/yearly)
    price = Column(DECIMAL(10, 2), nullable=True)  # Legacy field
    price_monthly = Column(Float, default=0.0)
    price_yearly = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    billing_cycle = Column(String, default="monthly")

    # Features & Limits
    credits_per_month = Column(Integer, default=10)
    max_video_length = Column(Integer, default=5)  # Seconds
    max_resolution = Column(String, default="720p")
    watermark = Column(Boolean, default=True)
    priority_queue = Column(Boolean, default=False)
    api_access = Column(Boolean, default=False)

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
