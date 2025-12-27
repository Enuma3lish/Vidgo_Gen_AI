"""
Demo Models for Smart Demo Engine
Supports multi-language prompt matching with before/after image transformation
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Float, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class DemoCategory(Base):
    """Categories for organizing demos"""
    __tablename__ = "demo_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, index=True)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    demos = relationship("ImageDemo", back_populates="category")
    video_demos = relationship("DemoVideo", back_populates="category")


class ImageDemo(Base):
    """
    Pre-generated image demos for the Smart Demo Engine.
    Shows before/after style transformation effects.
    Supports multi-language prompt matching.
    """
    __tablename__ = "image_demos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Prompt data (multi-language support)
    prompt_original = Column(Text, nullable=False)  # User's original prompt (any language)
    prompt_normalized = Column(Text, nullable=False, index=True)  # Normalized English version
    prompt_language = Column(String(10), default="en")  # en, zh-TW, ja, ko, es

    # Matching keywords (extracted from normalized prompt)
    keywords = Column(ARRAY(String), default=[], index=True)
    keywords_json = Column(JSONB, default={})  # {"animals": ["cat", "dog"], "style": ["anime"]}

    # Category
    category_id = Column(UUID(as_uuid=True), ForeignKey("demo_categories.id"), nullable=True)
    category_slug = Column(String(50), index=True)  # Denormalized for fast queries

    # Image URLs
    image_url_before = Column(String(500), nullable=False)  # Original source image
    image_url_after = Column(String(500), nullable=True)  # Transformed image
    thumbnail_url = Column(String(500), nullable=True)

    # Style information
    style_id = Column(Integer, nullable=True)  # GoEnhance model ID
    style_name = Column(String(100), nullable=True)
    style_slug = Column(String(50), index=True)

    # Generation metadata
    source_service = Column(String(50), default="goenhance")
    task_id = Column(String(100), nullable=True)  # External API task ID
    generation_params = Column(JSONB, default={})
    generation_cost = Column(Float, default=0.0)  # Credits used

    # Matching & ranking
    popularity_score = Column(Integer, default=0)  # View count
    quality_score = Column(Float, default=0.8)  # Internal quality rating 0-1
    match_boost = Column(Float, default=1.0)  # Manual boost for matching priority

    # Status
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # For daily regeneration

    # Relationships
    category = relationship("DemoCategory", back_populates="demos")

    # Indexes for fast searching
    __table_args__ = (
        Index('idx_image_demo_keywords', 'keywords', postgresql_using='gin'),
        Index('idx_image_demo_search', 'prompt_normalized', 'category_slug', 'style_slug'),
        Index('idx_image_demo_active', 'is_active', 'status'),
    )


class DemoVideo(Base):
    """Pre-generated demo videos for Explore Categories feature"""
    __tablename__ = "demo_videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    prompt = Column(Text, nullable=False)
    keywords = Column(ARRAY(String), default=[])

    category_id = Column(UUID(as_uuid=True), ForeignKey("demo_categories.id"), nullable=True)
    category_slug = Column(String(50), index=True)  # Denormalized for fast queries

    # Image and Video URLs
    image_url = Column(String(500), nullable=True)  # Source image
    video_url = Column(String(500), nullable=False)
    video_url_watermarked = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)

    duration_seconds = Column(Float, default=5.0)
    resolution = Column(String(20), default="720p")
    style = Column(String(50), nullable=True)
    style_slug = Column(String(50), nullable=True)

    source_service = Column(String(50), default="pollo_ai")
    generation_params = Column(JSONB, default={})

    popularity_score = Column(Integer, default=0)
    quality_score = Column(Float, default=0.0)

    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    category = relationship("DemoCategory", back_populates="video_demos")

    # Indexes for fast queries
    __table_args__ = (
        Index('idx_demo_video_category', 'category_slug', 'is_active'),
    )


class DemoView(Base):
    """Track demo views for popularity scoring"""
    __tablename__ = "demo_views"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    demo_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    demo_type = Column(String(20), default="image")  # image, video
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    search_prompt = Column(Text, nullable=True)  # What the user searched for
    viewed_at = Column(DateTime(timezone=True), server_default=func.now())


class PromptCache(Base):
    """
    Cache for prompt translations and keyword extractions.
    Speeds up multi-language prompt processing.
    """
    __tablename__ = "prompt_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_hash = Column(String(64), unique=True, index=True)  # SHA256 of original prompt
    prompt_original = Column(Text, nullable=False)
    prompt_normalized = Column(Text, nullable=False)
    detected_language = Column(String(10), nullable=True)
    keywords = Column(ARRAY(String), default=[])
    category_hints = Column(ARRAY(String), default=[])
    style_hints = Column(ARRAY(String), default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    hit_count = Column(Integer, default=0)
