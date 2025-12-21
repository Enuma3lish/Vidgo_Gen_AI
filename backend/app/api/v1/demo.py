"""
Demo API Endpoints
Smart Demo Engine for showcasing AI style transformation
Supports multi-language prompts (EN, ZH-TW, JA, KO, ES)

Features:
- Smart prompt matching with multi-language support
- Redis block cache for illegal content filtering
- Gemini AI-powered content moderation with learning
- GoEnhance style transformation demos
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db
from app.models.demo import ImageDemo, DemoCategory, DemoVideo
from app.services.demo_service import get_demo_service, DEMO_TOPICS
from app.services.prompt_matching import get_prompt_matching_service
from app.services.moderation import get_moderation_service
from app.services.goenhance import GOENHANCE_STYLES
from app.services.block_cache import get_block_cache

router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================

class DemoSearchRequest(BaseModel):
    """Request to search or generate demo"""
    prompt: str = Field(..., min_length=2, max_length=500, description="User prompt in any supported language")
    style: Optional[str] = Field(None, description="Preferred style slug")
    category: Optional[str] = Field(None, description="Category filter")
    generate_if_not_found: bool = Field(True, description="Generate new demo if no match found")


class ImageDemoResponse(BaseModel):
    """Response containing demo image data"""
    id: Optional[str] = None
    prompt: str
    prompt_normalized: Optional[str] = None
    language: Optional[str] = None
    image_before: Optional[str] = None
    image_after: Optional[str] = None
    style_name: Optional[str] = None
    style_slug: Optional[str] = None
    category: Optional[str] = None
    match_score: Optional[float] = None
    is_sample: bool = False

    class Config:
        from_attributes = True


class DemoSearchResponse(BaseModel):
    """Response from demo search"""
    success: bool
    found_existing: bool
    generated_new: bool = False
    match_score: Optional[float] = None
    matched_keywords: Optional[List[str]] = None
    demo: Optional[ImageDemoResponse] = None
    error: Optional[str] = None
    suggestion: Optional[str] = None


class RandomDemoRequest(BaseModel):
    """Request for random demo"""
    category: Optional[str] = None
    style: Optional[str] = None


class StyleInfo(BaseModel):
    """Style information"""
    id: int
    name: str
    slug: str
    version: Optional[str] = None


class CategoryInfo(BaseModel):
    """Category information"""
    slug: str
    name: str
    topic_count: int
    sample_topics: List[str]


class VideoInfo(BaseModel):
    """Video information for category display"""
    id: str
    title: str
    description: Optional[str] = None
    prompt: str
    video_url: str
    thumbnail_url: Optional[str] = None
    duration_seconds: float = 5.0
    style: Optional[str] = None
    category_slug: Optional[str] = None


class CategoryVideosResponse(BaseModel):
    """Response for category videos"""
    category: str
    category_name: str
    videos: List[VideoInfo]
    total_count: int


class PromptAnalysisResponse(BaseModel):
    """Response from prompt analysis"""
    original: str
    normalized: str
    language: str
    keywords: List[str]
    category: Optional[str]
    style: Optional[str]
    confidence: float


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/search", response_model=DemoSearchResponse)
async def search_or_generate_demo(
    request: DemoSearchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Search for matching demo or generate new one.

    Flow:
    1. Moderate prompt for safety
    2. Normalize prompt and extract keywords
    3. Search database for similar demos
    4. If found: return best match
    5. If not found and generate_if_not_found=True: generate new demo

    Supports prompts in: English, Traditional Chinese, Japanese, Korean, Spanish
    """
    # 1. Content moderation
    moderation_service = get_moderation_service()
    moderation_result = await moderation_service.moderate(request.prompt)

    if not moderation_result.is_safe:
        raise HTTPException(
            status_code=400,
            detail=f"Content not allowed: {moderation_result.reason}"
        )

    # 2. Get or create demo
    demo_service = get_demo_service()
    result = await demo_service.get_or_create_demo(
        db=db,
        prompt=request.prompt,
        preferred_style=request.style
    )

    if result.get("success"):
        demo_data = result.get("demo", {})
        return DemoSearchResponse(
            success=True,
            found_existing=result.get("found_existing", False),
            generated_new=result.get("generated_new", False),
            match_score=result.get("match_score"),
            matched_keywords=result.get("matched_keywords"),
            demo=ImageDemoResponse(
                id=demo_data.get("id"),
                prompt=demo_data.get("prompt_original", request.prompt),
                prompt_normalized=demo_data.get("prompt_normalized"),
                image_before=demo_data.get("image_before"),
                image_after=demo_data.get("image_after"),
                style_name=demo_data.get("style_name"),
                style_slug=demo_data.get("style_slug"),
                category=demo_data.get("category"),
                match_score=result.get("match_score"),
            )
        )
    else:
        return DemoSearchResponse(
            success=False,
            found_existing=False,
            error=result.get("error"),
            suggestion=result.get("suggestion")
        )


@router.get("/random", response_model=ImageDemoResponse)
async def get_random_demo(
    category: Optional[str] = Query(None, description="Filter by category"),
    style: Optional[str] = Query(None, description="Filter by style"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a random demo for displaying on demo page.
    If no demos exist, returns a sample prompt suggestion.
    """
    demo_service = get_demo_service()
    result = await demo_service.get_random_demo_for_display(db, category=category)

    if result:
        return ImageDemoResponse(
            id=result.get("id"),
            prompt=result.get("prompt"),
            prompt_normalized=result.get("prompt_normalized"),
            image_before=result.get("image_before"),
            image_after=result.get("image_after"),
            style_name=result.get("style_name"),
            category=result.get("category"),
            is_sample=result.get("is_sample", False)
        )

    # Fallback if service returns nothing
    import random
    all_topics = []
    for topics in DEMO_TOPICS.values():
        all_topics.extend(topics)

    return ImageDemoResponse(
        prompt=random.choice(all_topics) if all_topics else "A beautiful sunset over the ocean",
        is_sample=True
    )


@router.post("/analyze", response_model=PromptAnalysisResponse)
async def analyze_prompt(
    prompt: str = Query(..., min_length=2, max_length=500)
):
    """
    Analyze a prompt without generating a demo.
    Useful for previewing how the system will interpret a prompt.

    Returns normalized English version, detected language, keywords, etc.
    """
    matcher = get_prompt_matching_service()
    analysis = matcher.normalize_prompt(prompt)

    return PromptAnalysisResponse(
        original=analysis.original,
        normalized=analysis.normalized,
        language=analysis.language,
        keywords=analysis.keywords,
        category=analysis.category,
        style=analysis.style,
        confidence=analysis.confidence
    )


@router.get("/styles", response_model=List[StyleInfo])
async def get_available_styles():
    """
    Get all available transformation styles from GoEnhance.
    """
    return [
        StyleInfo(
            id=style_id,
            name=info["name"],
            slug=info["slug"],
            version=info.get("version")
        )
        for style_id, info in GOENHANCE_STYLES.items()
    ]


@router.get("/categories", response_model=List[CategoryInfo])
async def get_demo_categories():
    """
    Get all demo categories with sample topics.
    """
    return [
        CategoryInfo(
            slug=category,
            name=category.replace("_", " ").title(),
            topic_count=len(topics),
            sample_topics=topics[:3]
        )
        for category, topics in DEMO_TOPICS.items()
    ]


@router.get("/topics/{category}", response_model=List[str])
async def get_category_topics(
    category: str,
    limit: int = Query(10, ge=1, le=50)
):
    """
    Get sample topics for a specific category.
    """
    if category not in DEMO_TOPICS:
        raise HTTPException(status_code=404, detail=f"Category not found: {category}")

    topics = DEMO_TOPICS[category]
    return topics[:limit]


@router.get("/videos/{category}", response_model=CategoryVideosResponse)
async def get_category_videos(
    category: str,
    limit: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db)
):
    """
    Get videos for a specific category.
    Returns up to 10 demo videos related to the category.
    """
    # First try to get category from database
    cat_query = select(DemoCategory).where(DemoCategory.slug == category)
    cat_result = await db.execute(cat_query)
    db_category = cat_result.scalar_one_or_none()

    category_name = category.replace("_", " ").replace("-", " ").title()
    if db_category:
        category_name = db_category.name

    # Get videos from database
    video_query = select(DemoVideo).where(
        DemoVideo.is_active == True
    )

    # Filter by category if we have a category record
    if db_category:
        video_query = video_query.where(DemoVideo.category_id == db_category.id)

    video_query = video_query.order_by(
        DemoVideo.popularity_score.desc(),
        DemoVideo.created_at.desc()
    ).limit(limit)

    result = await db.execute(video_query)
    videos = result.scalars().all()

    # Convert to response format
    video_list = [
        VideoInfo(
            id=str(video.id),
            title=video.title,
            description=video.description,
            prompt=video.prompt,
            video_url=video.video_url,
            thumbnail_url=video.thumbnail_url,
            duration_seconds=video.duration_seconds or 5.0,
            style=video.style,
            category_slug=category
        )
        for video in videos
    ]

    return CategoryVideosResponse(
        category=category,
        category_name=category_name,
        videos=video_list,
        total_count=len(video_list)
    )


@router.post("/moderate")
async def moderate_prompt(
    prompt: str = Query(..., min_length=3, max_length=500)
):
    """
    Check if a prompt passes content moderation.
    Pre-validates prompts before generation.
    """
    moderation_service = get_moderation_service()
    result = await moderation_service.moderate(prompt)
    return {
        "is_safe": result.is_safe,
        "reason": result.reason,
        "categories": result.categories
    }


@router.get("/{demo_id}", response_model=ImageDemoResponse)
async def get_demo_by_id(
    demo_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific demo by ID.
    """
    try:
        demo_uuid = UUID(demo_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid demo ID format")

    query = select(ImageDemo).where(
        ImageDemo.id == demo_uuid,
        ImageDemo.is_active == True
    )
    result = await db.execute(query)
    demo = result.scalar_one_or_none()

    if not demo:
        raise HTTPException(status_code=404, detail="Demo not found")

    return ImageDemoResponse(
        id=str(demo.id),
        prompt=demo.prompt_original,
        prompt_normalized=demo.prompt_normalized,
        language=demo.prompt_language,
        image_before=demo.image_url_before,
        image_after=demo.image_url_after,
        style_name=demo.style_name,
        style_slug=demo.style_slug,
        category=demo.category_slug,
    )


# =============================================================================
# ADMIN ENDPOINTS (for manual regeneration)
# =============================================================================

@router.post("/admin/regenerate", include_in_schema=False)
async def trigger_regeneration(
    background_tasks: BackgroundTasks,
    count_per_category: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger demo regeneration.
    For admin use only - should be protected with auth.
    """
    demo_service = get_demo_service()

    # Run in background
    background_tasks.add_task(
        demo_service.regenerate_demos,
        db,
        count_per_category,
        2  # styles per topic
    )

    return {"status": "regeneration_started", "count_per_category": count_per_category}


@router.post("/admin/cleanup", include_in_schema=False)
async def trigger_cleanup(
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger expired demo cleanup.
    For admin use only.
    """
    demo_service = get_demo_service()
    cleaned = await demo_service.cleanup_expired_demos(db)

    return {"status": "cleanup_complete", "cleaned_count": cleaned}


# =============================================================================
# BLOCK CACHE ENDPOINTS (Content Moderation)
# =============================================================================

class BlockWordRequest(BaseModel):
    """Request to add a blocked word"""
    word: str = Field(..., min_length=2, max_length=100)
    reason: str = Field(default="custom_rule", description="Reason for blocking")


class BlockCacheStatsResponse(BaseModel):
    """Block cache statistics"""
    total_blocked_words: int
    cache_hits: int
    prompt_cache_hits: int
    blocked_by_seed: int
    blocked_by_gemini: int
    blocked_by_manual: int


@router.get("/block-cache/stats", response_model=BlockCacheStatsResponse)
async def get_block_cache_stats():
    """
    Get block cache statistics.
    Shows how many words are blocked, cache hit rates, etc.
    """
    block_cache = get_block_cache()
    stats = await block_cache.get_stats()
    return BlockCacheStatsResponse(**stats)


@router.post("/block-cache/check")
async def check_prompt_in_cache(
    prompt: str = Query(..., min_length=2, max_length=500)
):
    """
    Check if a prompt is blocked by the cache.
    Does NOT call Gemini API - only checks existing cache.
    """
    block_cache = get_block_cache()
    result = await block_cache.check_prompt(prompt)

    return {
        "is_blocked": result.is_blocked,
        "reason": result.reason,
        "blocked_words": result.blocked_words,
        "source": result.source,
        "confidence": result.confidence
    }


@router.post("/admin/block-cache/add", include_in_schema=False)
async def add_blocked_word(request: BlockWordRequest):
    """
    Manually add a word to the block cache.
    For admin use only - should be protected with auth.
    """
    block_cache = get_block_cache()
    success = await block_cache.add_blocked_word(
        word=request.word,
        reason=request.reason,
        source="manual"
    )

    if success:
        return {"status": "success", "word": request.word, "reason": request.reason}
    else:
        raise HTTPException(status_code=500, detail="Failed to add blocked word")


@router.delete("/admin/block-cache/remove", include_in_schema=False)
async def remove_blocked_word(
    word: str = Query(..., min_length=2, max_length=100)
):
    """
    Remove a word from the block cache.
    For admin use only.
    """
    block_cache = get_block_cache()
    success = await block_cache.remove_blocked_word(word)

    if success:
        return {"status": "success", "word": word, "message": "Word removed from block cache"}
    else:
        return {"status": "not_found", "word": word, "message": "Word not found in cache"}


@router.post("/admin/block-cache/clear", include_in_schema=False)
async def clear_block_cache():
    """
    Clear all block cache data.
    WARNING: This will remove all cached blocked words!
    For admin use only.
    """
    block_cache = get_block_cache()
    count = await block_cache.clear_cache()

    return {"status": "cleared", "entries_removed": count}
