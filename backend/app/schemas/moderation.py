"""
Content Moderation Schemas
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class ModerationCategory(str, Enum):
    """Categories of content that may be flagged"""
    SAFE = "safe"
    ADULT = "adult"
    VIOLENCE = "violence"
    HATE = "hate"
    ILLEGAL = "illegal"
    HARASSMENT = "harassment"
    SELF_HARM = "self_harm"
    DANGEROUS = "dangerous"


class ModerationResult(BaseModel):
    """Result of content moderation check"""
    is_safe: bool
    categories: List[ModerationCategory] = []
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: Optional[str] = None
    flagged_keywords: List[str] = []
    needs_manual_review: bool = False
    source: str = "gemini"  # gemini, keyword_filter, manual


class ModerationRequest(BaseModel):
    """Request for content moderation"""
    prompt: str = Field(..., min_length=1, max_length=2000)
    check_image: bool = False
    image_url: Optional[str] = None
    strict_mode: bool = False  # More aggressive filtering


class ModerationStats(BaseModel):
    """Statistics for moderation (admin use)"""
    total_checks: int
    flagged_count: int
    category_breakdown: dict
    gemini_availability: float  # Percentage of time Gemini was available
