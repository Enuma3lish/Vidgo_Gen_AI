"""
Email Verification Model for tracking verification history.
Primary verification uses Redis for speed, this table stores audit trail.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class EmailVerification(Base):
    """
    Track email verification attempts and history.

    Note: Primary verification uses Redis for speed (15-min TTL).
    This table provides audit trail and backup verification.
    """
    __tablename__ = "email_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)

    # Verification Code (hashed for security)
    code_hash = Column(String(255), nullable=False)

    # Attempt tracking
    attempts = Column(Integer, default=0)

    # Status: pending, verified, expired, failed
    status = Column(String(20), default="pending")

    # Timestamps
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("app.models.user.User", backref="email_verifications")
