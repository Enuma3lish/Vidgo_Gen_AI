"""
Demo Video Schemas
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class DemoCategoryBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int = 0


class DemoCategoryCreate(DemoCategoryBase):
    pass


class DemoCategory(DemoCategoryBase):
    id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DemoVideoBase(BaseModel):
    title: str
    description: Optional[str] = None
    prompt: str
    keywords: List[str] = []
    resolution: str = "720p"
    style: Optional[str] = None


class DemoVideoCreate(DemoVideoBase):
    category_id: Optional[UUID] = None
    video_url: str
    video_url_watermarked: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: float = 5.0
    source_service: Optional[str] = None


class DemoVideoResponse(DemoVideoBase):
    id: UUID
    video_url_watermarked: Optional[str] = None  # Show watermarked for demo users
    thumbnail_url: Optional[str] = None
    duration_seconds: float
    category: Optional[DemoCategory] = None
    is_featured: bool
    popularity_score: int
    created_at: datetime

    class Config:
        from_attributes = True


class DemoVideoDetail(DemoVideoResponse):
    """Full demo video details (for admin)"""
    video_url: str
    source_service: Optional[str] = None
    quality_score: float
    is_active: bool


class DemoSearchRequest(BaseModel):
    """Request for searching demo videos"""
    prompt: str = Field(..., min_length=3, max_length=500)
    category: Optional[str] = None
    style: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=20)


class DemoSearchResult(BaseModel):
    """Search result with matching score"""
    demo: DemoVideoResponse
    match_score: float = Field(..., ge=0.0, le=1.0)
    match_reasons: List[str] = []  # Why this demo matched


class DemoSearchResponse(BaseModel):
    """Response for demo search"""
    results: List[DemoSearchResult]
    total_count: int
    query_prompt: str
