"""
Social Post Model - Tracks posts published to social media platforms.
Stores post metadata and engagement metrics for analytics.
"""
import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class SocialPost(Base):
    """Track posts published to social media platforms."""
    __tablename__ = "social_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    social_account_id = Column(UUID(as_uuid=True), ForeignKey("social_accounts.id", ondelete="SET NULL"), nullable=True)
    generation_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Post details
    platform = Column(String(32), nullable=False, index=True)  # facebook, instagram, tiktok, youtube
    platform_post_id = Column(String(256), nullable=True)       # Post ID from the platform
    post_url = Column(String(1024), nullable=True)
    caption = Column(Text, nullable=True)
    media_type = Column(String(32), nullable=True)               # image, video
    status = Column(String(32), default="published", nullable=False)  # published, failed, deleted

    # Engagement metrics (updated periodically)
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)
    views_count = Column(Integer, default=0)
    analytics_updated_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    social_account = relationship("SocialAccount", foreign_keys=[social_account_id])

    __table_args__ = (
        Index('idx_social_post_user_platform', 'user_id', 'platform'),
        Index('idx_social_post_published', 'published_at'),
    )
