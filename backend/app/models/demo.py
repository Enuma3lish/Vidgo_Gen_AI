"""
Demo Video Models for Smart Demo Engine
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Float, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class DemoCategory(Base):
    """Categories for organizing demo videos"""
    __tablename__ = "demo_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, index=True)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)  # Icon name for UI
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    demos = relationship("DemoVideo", back_populates="category")


class DemoVideo(Base):
    """Pre-generated demo videos for the Smart Demo Engine"""
    __tablename__ = "demo_videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Content metadata
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    prompt = Column(Text, nullable=False)  # Original prompt used to generate
    keywords = Column(ARRAY(String), default=[])  # Keywords for matching

    # Category
    category_id = Column(UUID(as_uuid=True), ForeignKey("demo_categories.id"), nullable=True)

    # Video files
    video_url = Column(String(500), nullable=False)  # Original video
    video_url_watermarked = Column(String(500), nullable=True)  # Watermarked version for demo
    thumbnail_url = Column(String(500), nullable=True)

    # Video metadata
    duration_seconds = Column(Float, default=5.0)
    resolution = Column(String(20), default="720p")  # 720p, 1080p, 4K
    style = Column(String(50), nullable=True)  # anime, realistic, 3d, etc.

    # Generation metadata
    source_service = Column(String(50), nullable=True)  # leonardo, runway, pollo, goenhance
    generation_params = Column(Text, nullable=True)  # JSON string of generation parameters

    # Matching scores (pre-computed for performance)
    popularity_score = Column(Integer, default=0)  # View count
    quality_score = Column(Float, default=0.0)  # Internal quality rating

    # Status
    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    category = relationship("DemoCategory", back_populates="demos")


class DemoView(Base):
    """Track demo video views for popularity scoring"""
    __tablename__ = "demo_views"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    demo_id = Column(UUID(as_uuid=True), ForeignKey("demo_videos.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Nullable for anonymous
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    viewed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    demo = relationship("DemoVideo")
