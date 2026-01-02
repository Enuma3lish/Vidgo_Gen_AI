from sqlalchemy import Boolean, Column, String, DateTime, Integer, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class User(Base):
    """
    User model with email verification and credit system support.

    Email Verification Flow:
    1. User registers -> is_active=False, email_verified=False
    2. Verification email sent with token
    3. User clicks link -> email_verified=True, is_active=True

    Credit System:
    - subscription_credits: Monthly credits (reset each billing cycle)
    - purchased_credits: Top-up credits (never expire)
    - bonus_credits: Promotional credits (expire on bonus_credits_expiry)
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=False, nullable=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)

    # Account status
    is_active = Column(Boolean, default=False)  # Activated after email verification
    is_superuser = Column(Boolean, default=False)

    # Credit System Fields
    subscription_credits = Column(Integer, default=0)  # Weekly credits (reset each Monday 00:00 UTC)
    purchased_credits = Column(Integer, default=0)  # Top-up credits (never expire)
    bonus_credits = Column(Integer, default=0)  # Promotional credits
    bonus_credits_expiry = Column(DateTime(timezone=True), nullable=True)  # When bonus credits expire
    credits_reset_at = Column(DateTime(timezone=True), nullable=True)  # Last weekly reset timestamp

    # Plan Info
    current_plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=True, index=True)
    plan_started_at = Column(DateTime(timezone=True), nullable=True)
    plan_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Email verification
    email_verified = Column(Boolean, default=False)
    email_verification_token = Column(String, nullable=True, index=True)
    email_verification_sent_at = Column(DateTime(timezone=True), nullable=True)

    # Password reset
    password_reset_token = Column(String, nullable=True, index=True)
    password_reset_sent_at = Column(DateTime(timezone=True), nullable=True)

    # Demo Tier Usage Tracking
    demo_usage_count = Column(Integer, default=0)  # Number of demo generations used
    demo_usage_reset_at = Column(DateTime(timezone=True), nullable=True)  # Last reset timestamp
    demo_usage_limit = Column(Integer, default=2)  # Max demo uses (default 2)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    current_plan = relationship("app.models.billing.Plan", foreign_keys=[current_plan_id])

    @property
    def total_credits(self) -> int:
        """Get total available credits."""
        return (self.subscription_credits or 0) + (self.purchased_credits or 0) + (self.bonus_credits or 0)

    @property
    def can_use_demo(self) -> bool:
        """Check if user can still use demo tier (hasn't exceeded 2-use limit)."""
        return (self.demo_usage_count or 0) < (self.demo_usage_limit or 2)

    @property
    def demo_uses_remaining(self) -> int:
        """Get remaining demo uses."""
        limit = self.demo_usage_limit or 2
        used = self.demo_usage_count or 0
        return max(0, limit - used)
