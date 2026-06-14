"""
Style Template Model for VidGo Platform

Pre-configured scene/style templates with hidden prompt engineering.
Users select a template by thumbnail; the backend resolves the full
English prompt (including lighting, focal length, material settings)
and sends it to PiAPI.
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from app.core.database import Base


class StyleTemplate(Base):
    """
    A curated style template for ProductScene or TryOn tools.

    Users see: thumbnail + localized name.
    Backend uses: prompt_en (detailed English prompt with cinematic parameters).
    """
    __tablename__ = "style_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Which tool this template applies to: "product_scene" or "try_on"
    tool_type = Column(String(50), nullable=False, index=True)

    # Grouping category (e.g. "mediterranean", "minimalist", "street")
    category = Column(String(100), nullable=False, index=True)

    # Localized display names
    name_en = Column(String(200), nullable=False)
    name_zh = Column(String(200), nullable=False)
    name_ja = Column(String(200), nullable=True)
    name_ko = Column(String(200), nullable=True)
    name_es = Column(String(200), nullable=True)

    # Preview image shown to user in template grid
    preview_image_url = Column(String(1000), nullable=True)

    # The detailed English prompt — NEVER exposed to users.
    # Includes: lighting, focal length, material, mood, camera angle, etc.
    prompt_en = Column(Text, nullable=False)

    # Structured metadata for prompt composition
    prompt_metadata = Column(JSONB, nullable=True, default=dict)
    # Expected keys: lighting, focal_length, material, mood, camera_angle, color_grading

    # Ordering & visibility
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    is_featured = Column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
