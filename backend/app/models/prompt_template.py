"""
Prompt Template Model for VidGo Platform
Stores pre-generated prompts with before/after results for demo users.

Key Features:
- Primary key: prompt (unique constraint with group)
- Group: topic category (e.g., "product_effect", "background_removal")
- Before/after results stored in PostgreSQL
- Non-subscribed users can only use default prompts to reduce API calls
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Float, ForeignKey, Index, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import relationship
import uuid
import enum
from app.core.database import Base


class PromptGroup(str, enum.Enum):
    """Main topic groups for prompt categorization"""
    # Product & E-commerce
    PRODUCT_EFFECT = "product_effect"
    BACKGROUND_REMOVAL = "background_removal"
    BACKGROUND_CHANGE = "background_change"
    PRODUCT_SCENE = "product_scene"

    # Video Generation
    IMAGE_TO_VIDEO = "image_to_video"
    TEXT_TO_VIDEO = "text_to_video"
    VIDEO_EFFECT = "video_effect"

    # Style & Design
    STYLE_TRANSFER = "style_transfer"
    ROOM_REDESIGN = "room_redesign"
    INTERIOR_DESIGN = "interior_design"

    # Fashion
    VIRTUAL_TRY_ON = "virtual_try_on"
    FASHION_MODEL = "fashion_model"

    # Avatar
    AI_AVATAR = "ai_avatar"
    TALKING_HEAD = "talking_head"

    # Enhancement
    UPSCALE = "upscale"
    WATERMARK_REMOVAL = "watermark_removal"

    # Pattern & Creative
    PATTERN_GENERATE = "pattern_generate"
    CREATIVE_DESIGN = "creative_design"


class PromptSubTopic(str, enum.Enum):
    """Sub-topics within each group for finer categorization"""
    # Product Effects
    COLOR_CHANGE = "color_change"
    MATERIAL_CHANGE = "material_change"
    LIGHTING_CHANGE = "lighting_change"
    ANGLE_CHANGE = "angle_change"

    # Background
    TRANSPARENT = "transparent"
    WHITE_BACKGROUND = "white_background"
    STUDIO_BACKGROUND = "studio_background"
    NATURE_BACKGROUND = "nature_background"
    LUXURY_BACKGROUND = "luxury_background"

    # Room Styles
    MODERN_STYLE = "modern_style"
    NORDIC_STYLE = "nordic_style"
    JAPANESE_STYLE = "japanese_style"
    INDUSTRIAL_STYLE = "industrial_style"
    MINIMALIST_STYLE = "minimalist_style"

    # Video Effects
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    ROTATE = "rotate"
    CINEMATIC = "cinematic"

    # General
    DEFAULT = "default"
    CUSTOM = "custom"


class PromptTemplate(Base):
    """
    Pre-generated prompt templates with cached results.

    Purpose:
    - Store default prompts that demo/non-subscribed users can use
    - Cache API results to reduce redundant API calls
    - Provide before/after examples for each tool

    Primary Key Strategy:
    - Composite unique constraint on (prompt_hash + group + sub_topic)
    - This ensures the same prompt can exist in different contexts
    """
    __tablename__ = "prompt_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # === Prompt Identity (Unique Constraint) ===
    prompt_hash = Column(String(64), nullable=False, index=True)  # SHA256 of normalized prompt
    prompt = Column(Text, nullable=False)  # The actual prompt text
    prompt_normalized = Column(Text, nullable=False)  # Cleaned/normalized version

    # === Multi-language Support ===
    prompt_en = Column(Text, nullable=True)  # English version
    prompt_zh = Column(Text, nullable=True)  # Traditional Chinese version
    prompt_ja = Column(Text, nullable=True)  # Japanese version
    prompt_ko = Column(Text, nullable=True)  # Korean version
    prompt_es = Column(Text, nullable=True)  # Spanish version
    original_language = Column(String(10), default="en")  # Original prompt language

    # === Categorization ===
    group = Column(
        SQLEnum(PromptGroup, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True
    )
    sub_topic = Column(
        SQLEnum(PromptSubTopic, values_callable=lambda x: [e.value for e in x]),
        default=PromptSubTopic.DEFAULT,
        index=True
    )

    # Display names for UI
    group_display_en = Column(String(100), nullable=True)  # e.g., "Product Effects"
    group_display_zh = Column(String(100), nullable=True)  # e.g., "產品特效"
    sub_topic_display_en = Column(String(100), nullable=True)
    sub_topic_display_zh = Column(String(100), nullable=True)

    # Tags for search and filtering
    tags = Column(ARRAY(String), default=[])
    keywords = Column(ARRAY(String), default=[])  # Extracted keywords for matching

    # === Input Data (Before) ===
    input_description = Column(Text, nullable=True)  # Description of input
    input_image_url = Column(String(500), nullable=True)  # Source image (before)
    input_video_url = Column(String(500), nullable=True)  # Source video (before)
    input_params = Column(JSONB, default={})  # Parameters used for generation

    # === Output Data (After) ===
    result_description = Column(Text, nullable=True)  # Description of result
    result_image_url = Column(String(500), nullable=True)  # Generated image (after)
    result_video_url = Column(String(500), nullable=True)  # Generated video (after)
    result_thumbnail_url = Column(String(500), nullable=True)
    result_watermarked_url = Column(String(500), nullable=True)  # For demo users
    result_params = Column(JSONB, default={})  # Generation result metadata

    # === API Information ===
    api_endpoint = Column(String(100), nullable=True)  # Which API to call
    api_provider = Column(String(50), nullable=True)  # piapi, pollo, goenhance, etc.
    api_model = Column(String(100), nullable=True)  # Specific model used
    generation_steps = Column(JSONB, default=[])  # Multi-step generation tracking

    # === Usage Statistics ===
    usage_count = Column(Integer, default=0)  # How many times this template was used
    success_count = Column(Integer, default=0)  # Successful generations
    failure_count = Column(Integer, default=0)  # Failed generations
    avg_generation_time_ms = Column(Integer, default=0)  # Average generation time
    total_cost_usd = Column(Float, default=0.0)  # Total API cost for this template

    # === Quality & Ranking ===
    quality_score = Column(Float, default=0.8)  # 0-1 quality rating
    popularity_score = Column(Integer, default=0)  # Based on usage
    sort_order = Column(Integer, default=0)  # Manual sorting

    # === Access Control ===
    is_default = Column(Boolean, default=True)  # Available for non-subscribed users
    is_premium = Column(Boolean, default=False)  # Only for paid users
    min_subscription_tier = Column(String(20), default="free")  # free, starter, pro, pro_plus
    credits_required = Column(Integer, default=0)  # Credits needed (0 for demo)

    # === Display Settings ===
    title_en = Column(String(255), nullable=True)
    title_zh = Column(String(255), nullable=True)
    description_en = Column(Text, nullable=True)
    description_zh = Column(Text, nullable=True)

    # === Flags ===
    is_featured = Column(Boolean, default=False)  # Show in featured section
    is_active = Column(Boolean, default=True)  # Available for use
    is_cached = Column(Boolean, default=False)  # Has cached result
    cache_expires_at = Column(DateTime(timezone=True), nullable=True)  # Cache expiration

    # === Timestamps ===
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # === Relationships ===
    usages = relationship("PromptTemplateUsage", back_populates="template", cascade="all, delete-orphan")

    # === Indexes for Performance ===
    __table_args__ = (
        # Unique constraint on prompt + group + sub_topic
        Index('idx_prompt_template_unique', 'prompt_hash', 'group', 'sub_topic', unique=True),
        # Fast lookup by group
        Index('idx_prompt_template_group', 'group', 'is_active', 'is_default'),
        # Fast lookup by sub_topic
        Index('idx_prompt_template_sub_topic', 'sub_topic', 'is_active'),
        # Search by keywords
        Index('idx_prompt_template_keywords', 'keywords', postgresql_using='gin'),
        Index('idx_prompt_template_tags', 'tags', postgresql_using='gin'),
        # Featured and popular
        Index('idx_prompt_template_featured', 'is_featured', 'is_active'),
        Index('idx_prompt_template_popular', 'popularity_score', 'is_active'),
        # Cache management
        Index('idx_prompt_template_cached', 'is_cached', 'cache_expires_at'),
    )


class PromptTemplateUsage(Base):
    """
    Track usage of prompt templates by users.
    Helps with analytics and personalization.
    """
    __tablename__ = "prompt_template_usages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("prompt_templates.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(64), nullable=True)  # For anonymous users

    # Usage context
    source_page = Column(String(50), nullable=True)  # landing, tool_page, inspiration
    user_tier = Column(String(20), default="free")  # User's subscription tier
    used_cached = Column(Boolean, default=True)  # Whether cached result was used

    # Result tracking
    was_successful = Column(Boolean, default=True)
    generation_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Custom input (if user modified the prompt)
    custom_prompt = Column(Text, nullable=True)
    custom_params = Column(JSONB, default={})

    # Timestamps
    used_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    template = relationship("PromptTemplate", back_populates="usages")

    # Indexes
    __table_args__ = (
        Index('idx_template_usage_user', 'user_id', 'used_at'),
        Index('idx_template_usage_template', 'template_id', 'used_at'),
    )


# === Group Display Names Configuration ===
GROUP_DISPLAY_NAMES = {
    PromptGroup.PRODUCT_EFFECT: {
        "en": "Product Effects",
        "zh": "產品特效",
    },
    PromptGroup.BACKGROUND_REMOVAL: {
        "en": "Background Removal",
        "zh": "背景移除",
    },
    PromptGroup.BACKGROUND_CHANGE: {
        "en": "Background Change",
        "zh": "背景更換",
    },
    PromptGroup.PRODUCT_SCENE: {
        "en": "Product Scene",
        "zh": "產品場景",
    },
    PromptGroup.IMAGE_TO_VIDEO: {
        "en": "Image to Video",
        "zh": "圖生視頻",
    },
    PromptGroup.TEXT_TO_VIDEO: {
        "en": "Text to Video",
        "zh": "文生視頻",
    },
    PromptGroup.VIDEO_EFFECT: {
        "en": "Video Effects",
        "zh": "視頻特效",
    },
    PromptGroup.STYLE_TRANSFER: {
        "en": "Style Transfer",
        "zh": "風格轉換",
    },
    PromptGroup.ROOM_REDESIGN: {
        "en": "Room Redesign",
        "zh": "房間重設計",
    },
    PromptGroup.INTERIOR_DESIGN: {
        "en": "Interior Design",
        "zh": "室內設計",
    },
    PromptGroup.VIRTUAL_TRY_ON: {
        "en": "Virtual Try-On",
        "zh": "虛擬試穿",
    },
    PromptGroup.FASHION_MODEL: {
        "en": "Fashion Model",
        "zh": "時尚模特",
    },
    PromptGroup.AI_AVATAR: {
        "en": "AI Avatar",
        "zh": "AI數位人",
    },
    PromptGroup.TALKING_HEAD: {
        "en": "Talking Head",
        "zh": "口播視頻",
    },
    PromptGroup.UPSCALE: {
        "en": "HD Upscale",
        "zh": "高清放大",
    },
    PromptGroup.WATERMARK_REMOVAL: {
        "en": "Watermark Removal",
        "zh": "去水印",
    },
    PromptGroup.PATTERN_GENERATE: {
        "en": "Pattern Generation",
        "zh": "圖案生成",
    },
    PromptGroup.CREATIVE_DESIGN: {
        "en": "Creative Design",
        "zh": "創意設計",
    },
}


# === Sub-Topic Display Names Configuration ===
SUB_TOPIC_DISPLAY_NAMES = {
    PromptSubTopic.COLOR_CHANGE: {"en": "Color Change", "zh": "顏色更換"},
    PromptSubTopic.MATERIAL_CHANGE: {"en": "Material Change", "zh": "材質更換"},
    PromptSubTopic.LIGHTING_CHANGE: {"en": "Lighting Change", "zh": "光線調整"},
    PromptSubTopic.ANGLE_CHANGE: {"en": "Angle Change", "zh": "角度調整"},
    PromptSubTopic.TRANSPARENT: {"en": "Transparent", "zh": "透明背景"},
    PromptSubTopic.WHITE_BACKGROUND: {"en": "White Background", "zh": "白色背景"},
    PromptSubTopic.STUDIO_BACKGROUND: {"en": "Studio Background", "zh": "攝影棚背景"},
    PromptSubTopic.NATURE_BACKGROUND: {"en": "Nature Background", "zh": "自然背景"},
    PromptSubTopic.LUXURY_BACKGROUND: {"en": "Luxury Background", "zh": "奢華背景"},
    PromptSubTopic.MODERN_STYLE: {"en": "Modern Style", "zh": "現代風格"},
    PromptSubTopic.NORDIC_STYLE: {"en": "Nordic Style", "zh": "北歐風格"},
    PromptSubTopic.JAPANESE_STYLE: {"en": "Japanese Style", "zh": "日式風格"},
    PromptSubTopic.INDUSTRIAL_STYLE: {"en": "Industrial Style", "zh": "工業風格"},
    PromptSubTopic.MINIMALIST_STYLE: {"en": "Minimalist Style", "zh": "極簡風格"},
    PromptSubTopic.ZOOM_IN: {"en": "Zoom In", "zh": "放大"},
    PromptSubTopic.ZOOM_OUT: {"en": "Zoom Out", "zh": "縮小"},
    PromptSubTopic.PAN_LEFT: {"en": "Pan Left", "zh": "左移"},
    PromptSubTopic.PAN_RIGHT: {"en": "Pan Right", "zh": "右移"},
    PromptSubTopic.ROTATE: {"en": "Rotate", "zh": "旋轉"},
    PromptSubTopic.CINEMATIC: {"en": "Cinematic", "zh": "電影感"},
    PromptSubTopic.DEFAULT: {"en": "Default", "zh": "預設"},
    PromptSubTopic.CUSTOM: {"en": "Custom", "zh": "自訂"},
}
