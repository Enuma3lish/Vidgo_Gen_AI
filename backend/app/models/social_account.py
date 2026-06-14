"""
Social Media Account model for storing OAuth tokens and account info.
Supports Facebook, Instagram, and TikTok integrations.
"""
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class SocialAccount(Base):
    """
    Stores connected social media accounts for users.
    Each user can connect one account per platform.
    """
    __tablename__ = "social_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Platform identifier: 'facebook', 'instagram', 'tiktok'
    platform = Column(String(32), nullable=False, index=True)

    # Platform-specific account info
    platform_user_id = Column(String(256), nullable=True)   # Platform's user/page ID
    platform_username = Column(String(256), nullable=True)  # Display name / username
    platform_avatar = Column(String(512), nullable=True)    # Profile picture URL

    # OAuth tokens (encrypted in production)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # For Instagram: page_id is needed for Graph API publishing
    page_id = Column(String(256), nullable=True)
    # For TikTok: open_id is the user identifier
    open_id = Column(String(256), nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    user = relationship("User", back_populates="social_accounts")

    class Config:
        unique_together = [("user_id", "platform")]
