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


class GenerateImageRequest(BaseModel):
    """Request for image-only generation (Generate Demo)"""
    prompt: str = Field(..., min_length=2, max_length=500, description="User prompt for image")
    style: Optional[str] = Field(None, description="Style slug for image generation")


class GenerateImageResponse(BaseModel):
    """Response from image generation"""
    success: bool
    prompt: str
    image_url: Optional[str] = None  # Watermarked image (for display)
    original_url: Optional[str] = None  # Original image (for video generation)
    style_name: Optional[str] = None
    error: Optional[str] = None


class RealtimeDemoRequest(BaseModel):
    """Request for real-time demo generation (See It In Action)"""
    prompt: str = Field(..., min_length=2, max_length=500, description="User prompt for demo")
    image_url: Optional[str] = Field(None, description="Pre-generated image URL to use for video")
    style: Optional[str] = Field(None, description="Style slug for V2V enhancement")
    skip_v2v: bool = Field(True, description="Skip V2V enhancement step (default True for current version)")


class PipelineStep(BaseModel):
    """A step in the demo pipeline"""
    step: int
    name: str
    status: str  # "in_progress", "completed", "failed", "skipped"


class RealtimeDemoResponse(BaseModel):
    """Response from real-time demo generation"""
    success: bool
    prompt: str
    style_name: Optional[str] = None
    style_slug: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    enhanced_video_url: Optional[str] = None
    steps: List[PipelineStep] = []
    partial: bool = False  # True if only some steps completed
    error: Optional[str] = None


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


@router.post("/generate-image", response_model=GenerateImageResponse)
async def generate_demo_image(
    request: GenerateImageRequest,
):
    """
    Generate a demo image only (with watermark).
    This is the "Generate Demo" feature - Step 1.

    Uses GoEnhance Nano Banana for text-to-image generation.
    Image includes watermark for demo purposes.

    Processing time: ~30-60 seconds
    """
    # 1. Content moderation
    moderation_service = get_moderation_service()
    moderation_result = await moderation_service.moderate(request.prompt)

    if not moderation_result.is_safe:
        raise HTTPException(
            status_code=400,
            detail=f"Content not allowed: {moderation_result.reason}"
        )

    # 2. Generate image only
    demo_service = get_demo_service()
    result = await demo_service.generate_image_only(
        prompt=request.prompt,
        style_slug=request.style
    )

    return GenerateImageResponse(
        success=result.get("success", False),
        prompt=request.prompt,
        image_url=result.get("image_url"),
        original_url=result.get("original_url"),  # For video generation
        style_name=result.get("style_name"),
        error=result.get("error")
    )


@router.post("/generate-realtime", response_model=RealtimeDemoResponse)
async def generate_demo_realtime(
    request: RealtimeDemoRequest,
):
    """
    Generate video from an existing image.
    This is the "See It In Action" feature - Step 2.

    If image_url is provided, uses that image directly.
    Otherwise generates a new image first.

    Uses Pollo AI Pixverse for image-to-video generation.
    V2V enhancement is disabled in current version.

    Processing time: ~1-3 minutes
    """
    # 1. Content moderation
    moderation_service = get_moderation_service()
    moderation_result = await moderation_service.moderate(request.prompt)

    if not moderation_result.is_safe:
        raise HTTPException(
            status_code=400,
            detail=f"Content not allowed: {moderation_result.reason}"
        )

    # 2. Generate video (and image if not provided)
    demo_service = get_demo_service()
    result = await demo_service.generate_video_from_image(
        prompt=request.prompt,
        image_url=request.image_url,
        style_slug=request.style,
        skip_v2v=request.skip_v2v
    )

    return RealtimeDemoResponse(
        success=result.get("success", False),
        prompt=result.get("prompt", request.prompt),
        style_name=result.get("style_name"),
        style_slug=result.get("style_slug"),
        image_url=result.get("image_url"),
        video_url=result.get("video_url"),
        enhanced_video_url=result.get("enhanced_video_url"),
        steps=[
            PipelineStep(
                step=s.get("step", 0),
                name=s.get("name", ""),
                status=s.get("status", "")
            )
            for s in result.get("steps", [])
        ],
        partial=result.get("partial", False),
        error=result.get("error")
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
    category_name = category.replace("_", " ").replace("-", " ").title()

    # Use demo service to get videos
    demo_service = get_demo_service()
    videos = await demo_service.get_random_category_videos(db, category, limit)

    # Convert to response format
    video_list = [
        VideoInfo(
            id=v["id"],
            title=v.get("title", ""),
            description=None,
            prompt=v.get("prompt", ""),
            video_url=v["video_url"],
            thumbnail_url=v.get("thumbnail_url"),
            duration_seconds=v.get("duration", 5.0),
            style=v.get("style"),
            category_slug=category
        )
        for v in videos
    ]

    return CategoryVideosResponse(
        category=category,
        category_name=category_name,
        videos=video_list,
        total_count=len(video_list)
    )


@router.get("/videos/{category}/random")
async def get_random_category_videos(
    category: str,
    count: int = Query(3, ge=1, le=10),
    db: AsyncSession = Depends(get_db)
):
    """
    Get random videos for a category (for Explore Categories display).
    Returns specified number of random videos for auto-play carousel.
    """
    demo_service = get_demo_service()

    # Get video count
    total = await demo_service.get_category_video_count(db, category)

    # Get random videos
    videos = await demo_service.get_random_category_videos(db, category, count)

    return {
        "category": category,
        "videos": videos,
        "total_available": total,
        "has_enough": total >= 30  # Has enough videos for full carousel
    }


@router.get("/videos/{category}/count")
async def get_category_video_count(
    category: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get count of videos for a category.
    Used to check if pre-generation is needed.
    """
    demo_service = get_demo_service()
    count = await demo_service.get_category_video_count(db, category)

    return {
        "category": category,
        "count": count,
        "target": 30,
        "needs_generation": count < 30
    }


@router.post("/videos/{category}/generate")
async def generate_category_videos(
    category: str,
    count: int = Query(3, ge=1, le=10, description="Number of videos to generate"),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate new videos for a category.
    This is an admin endpoint for pre-populating category videos.

    Each category needs ~30 videos for the Explore Categories feature.
    This generates videos from the predefined prompts in DEMO_TOPICS.
    """
    if category not in DEMO_TOPICS:
        raise HTTPException(status_code=404, detail=f"Category not found: {category}")

    # Get prompts for this category
    prompts = DEMO_TOPICS[category]

    # Shuffle and take requested count
    import random
    selected_prompts = random.sample(prompts, min(count, len(prompts)))

    demo_service = get_demo_service()
    result = await demo_service.generate_category_videos_batch(
        db=db,
        category_slug=category,
        prompts=selected_prompts,
        target_count=30
    )

    return result


@router.post("/videos/generate-all")
async def generate_all_category_videos(
    background_tasks: BackgroundTasks,
    videos_per_category: int = Query(30, ge=1, le=50, description="Number of videos per category"),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate videos for ALL categories (background task).
    This is an admin endpoint for bulk pre-populating all category videos.

    Will generate up to videos_per_category videos for each category.
    Categories: animals, nature, urban, people, fantasy, sci-fi, food
    """
    import random
    from app.services.goenhance import GOENHANCE_STYLES

    demo_service = get_demo_service()
    results = {}

    # Available styles for variety
    style_slugs = [info["slug"] for info in GOENHANCE_STYLES.values()]

    for category, base_prompts in DEMO_TOPICS.items():
        current_count = await demo_service.get_category_video_count(db, category)

        if current_count >= videos_per_category:
            results[category] = {
                "status": "skipped",
                "message": f"Already has {current_count} videos",
                "count": current_count
            }
            continue

        to_generate = videos_per_category - current_count

        # Generate prompts with style variations
        prompts_with_styles = []
        for prompt in base_prompts:
            for style in style_slugs[:3]:  # Use 3 different styles per prompt
                prompts_with_styles.append({
                    "prompt": prompt,
                    "style": style
                })

        # Shuffle and select
        random.shuffle(prompts_with_styles)
        selected = prompts_with_styles[:to_generate]

        generated = 0
        failed = 0

        for item in selected:
            try:
                result = await demo_service.generate_category_video(
                    db=db,
                    prompt=item["prompt"],
                    category_slug=category,
                    style_slug=item["style"]
                )
                if result.get("success"):
                    generated += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1

            # Rate limiting
            import asyncio
            await asyncio.sleep(3)

        final_count = await demo_service.get_category_video_count(db, category)
        results[category] = {
            "status": "completed",
            "generated": generated,
            "failed": failed,
            "total": final_count
        }

    return {
        "status": "completed",
        "categories": results
    }


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
