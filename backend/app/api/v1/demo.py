"""
Demo API Endpoints - PRESET-ONLY MODE
Smart Demo Engine for showcasing AI style transformation
Supports multi-language prompts (EN, ZH-TW, JA, KO, ES)

PRESET-ONLY MODE:
- ALL users (subscribed and non-subscribed) have the SAME experience
- Users can ONLY select from pre-defined prompts/presets
- NO custom text input allowed (no script, no description)
- ALL results come from Material DB (pre-generated)
- ALL results are watermarked
- Downloads are BLOCKED for everyone
- NO external API calls during user sessions

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
from app.models.demo import ImageDemo, DemoCategory, DemoVideo, DemoExample, PromptCache, ToolShowcase
from app.services.demo_service import get_demo_service, DEMO_TOPICS, DEMO_STYLES
from app.services.prompt_matching import get_prompt_matching_service
from app.services.moderation import get_moderation_service
from app.services.block_cache import get_block_cache
from app.services.gemini_service import get_gemini_service
from app.services.similarity import get_similarity_service
from app.services.rescue_service import get_rescue_service
from app.services.material import MaterialLibraryService, UserContentCollector, MATERIAL_REQUIREMENTS

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
# NEW SCHEMAS - Demo Tier with Leonardo AI
# =============================================================================

class InspirationExample(BaseModel):
    """A single inspiration example"""
    id: str
    topic: str
    topic_display: str
    prompt: str
    image_url: str
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    title: Optional[str] = None
    style_tags: List[str] = []

    class Config:
        from_attributes = True


class InspirationResponse(BaseModel):
    """Response for inspiration gallery"""
    success: bool
    examples: List[InspirationExample]
    topics: List[str]
    total_count: int


class ProductVideoRequest(BaseModel):
    """Request for product ads video generation (Demo Tier)"""
    prompt: str = Field(..., min_length=2, max_length=500, description="Product description prompt")
    category: str = Field(default="product", description="Topic category")
    style: Optional[str] = Field(None, description="Style preference")
    user_id: Optional[str] = Field(None, description="User ID for demo usage tracking")


class PaidGenerationRequest(BaseModel):
    """Request for paid tier generation with image upload support.

    Paid users can:
    1. Upload their own images (base64 or URL)
    2. Call generation APIs directly
    3. Results stored to Material DB with Gemini description as key
    """
    prompt: str = Field(..., min_length=2, max_length=500, description="Generation prompt")
    tool: str = Field(default="background_removal", description="Tool to use")
    category: str = Field(default="product", description="Topic category")
    style: Optional[str] = Field(None, description="Style preference")
    image_url: Optional[str] = Field(None, description="Source image URL")
    image_base64: Optional[str] = Field(None, description="Source image as base64")
    user_id: str = Field(..., description="Paid user ID (required)")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional parameters")


class PaidGenerationResponse(BaseModel):
    """Response from paid tier generation"""
    success: bool
    original_prompt: str
    enhanced_prompt: Optional[str] = None
    image_description: Optional[str] = None  # Gemini description of uploaded image
    image_tags: Optional[List[str]] = None
    input_image_url: Optional[str] = None
    result_image_url: Optional[str] = None
    result_video_url: Optional[str] = None
    material_id: Optional[str] = None  # ID in Material DB
    generation_steps: Optional[List[Dict[str, Any]]] = None
    credits_used: int = 0
    error: Optional[str] = None
    blocked_reason: Optional[str] = None


class ProductVideoResponse(BaseModel):
    """Response from product ads video generation"""
    success: bool
    from_cache: bool = False
    similarity_score: Optional[float] = None
    original_prompt: str
    enhanced_prompt: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    video_url_watermarked: Optional[str] = None
    credits_used: int = 0
    demo_uses_remaining: Optional[int] = None
    error: Optional[str] = None
    blocked_reason: Optional[str] = None


# =============================================================================
# TOOL SHOWCASE SCHEMAS
# =============================================================================

class ToolShowcaseItem(BaseModel):
    """A single tool showcase example"""
    id: str
    tool_category: str
    tool_id: str
    tool_name: str
    tool_name_zh: Optional[str] = None
    source_image_url: str
    prompt: str
    prompt_zh: Optional[str] = None
    result_image_url: Optional[str] = None
    result_video_url: Optional[str] = None
    title: Optional[str] = None
    title_zh: Optional[str] = None
    description: Optional[str] = None
    description_zh: Optional[str] = None
    duration_seconds: float = 5.0
    style_tags: List[str] = []
    is_featured: bool = False

    class Config:
        from_attributes = True


class ToolShowcaseResponse(BaseModel):
    """Response for tool showcase gallery"""
    success: bool
    showcases: List[ToolShowcaseItem]
    tool_category: str
    tool_id: Optional[str] = None
    total_count: int


class SaveShowcaseRequest(BaseModel):
    """Request to save user-generated showcase"""
    tool_category: str = Field(..., description="Tool category (edit_tools, ecommerce, etc.)")
    tool_id: str = Field(..., description="Specific tool ID")
    source_image_url: str = Field(..., description="Source image URL")
    prompt: str = Field(..., description="Prompt used for generation")
    result_image_url: Optional[str] = Field(None, description="Result image URL")
    result_video_url: Optional[str] = Field(None, description="Result video URL")


# =============================================================================
# ENDPOINTS
# =============================================================================

# =============================================================================
# PRESET-ONLY MODE ENDPOINTS (NEW)
# =============================================================================

class UsePresetRequest(BaseModel):
    """Request to use a preset template"""
    preset_id: str = Field(..., description="Preset template ID or material ID")
    tool_type: Optional[str] = Field(None, description="Tool type for filtering")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")


class PresetResultResponse(BaseModel):
    """Response from using a preset - always watermarked"""
    success: bool
    preset_id: str
    result_watermarked_url: Optional[str] = None
    result_thumbnail_url: Optional[str] = None
    can_download: bool = False  # ALWAYS false in preset-only mode
    message: str = "Subscribe for full access"
    error: Optional[str] = None


@router.post("/use-preset", response_model=PresetResultResponse)
async def use_preset(
    request: UsePresetRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Use a preset template - Material DB lookup only.

    PRESET-ONLY MODE:
    - ALL users use this endpoint (no distinction)
    - Returns watermarked results from Material DB
    - NO external API calls
    - NO custom prompts allowed
    """
    from app.services.material_lookup import get_material_lookup_service

    lookup_service = get_material_lookup_service(db)

    # Look up material by ID
    material = await lookup_service.lookup_by_id(request.preset_id)

    if not material:
        return PresetResultResponse(
            success=False,
            preset_id=request.preset_id,
            error="Preset result not found"
        )

    # Increment use count
    await lookup_service.increment_use_count(str(material.id))

    # Return watermarked result only
    return PresetResultResponse(
        success=True,
        preset_id=request.preset_id,
        result_watermarked_url=material.result_watermarked_url or material.result_video_url or material.result_image_url,
        result_thumbnail_url=material.result_thumbnail_url,
        can_download=False,  # ALWAYS false
        message="Subscribe for full access"
    )


@router.get("/presets/{tool_type}")
async def get_presets(
    tool_type: str,
    topic: Optional[str] = Query(None, description="Topic filter"),
    limit: int = Query(20, ge=1, le=50, description="Maximum number of presets"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get available presets for a tool.

    Returns list of preset templates with thumbnails.
    Users can only select from these presets - no custom input allowed.
    """
    from app.services.material_lookup import get_material_lookup_service

    lookup_service = get_material_lookup_service(db)
    presets = await lookup_service.get_presets_for_tool(tool_type, topic, limit)

    return {
        "success": True,
        "tool_type": tool_type,
        "topic": topic,
        "presets": [
            {
                "id": str(p.id),
                "prompt": p.prompt,
                "prompt_zh": p.prompt_zh,
                "input_image_url": p.input_image_url,
                "input_video_url": p.input_video_url,
                "result_image_url": p.result_image_url,
                "result_video_url": p.result_video_url,
                "result_watermarked_url": p.result_watermarked_url,
                "thumbnail_url": p.result_thumbnail_url or p.result_watermarked_url or p.result_image_url,
                "topic": p.topic,
                "input_params": p.input_params or {},
                "style_tags": p.tags or []
            }
            for p in presets
        ],
        "count": len(presets)
    }


@router.get("/download/{preset_id}")
async def download_result(preset_id: str):
    """
    Download is BLOCKED for ALL users in preset-only mode.
    """
    raise HTTPException(
        status_code=403,
        detail={
            "error": "download_blocked",
            "message": "Downloads are not available. Subscribe for full access.",
            "redirect": "/pricing"
        }
    )


# =============================================================================
# NEW ENDPOINTS - Demo Tier with Leonardo AI
# =============================================================================

@router.get("/inspiration", response_model=InspirationResponse)
async def get_inspiration_examples(
    topic: Optional[str] = Query(None, description="Filter by topic"),
    count: int = Query(10, ge=1, le=20, description="Number of examples to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get random inspiration examples for the AI Creation gallery.

    Returns up to 10 random pre-generated examples from the database.
    Examples include product images and videos for inspiration.
    """
    import random
    from sqlalchemy import func

    # Build query
    query = select(DemoExample).where(DemoExample.is_active == True)

    if topic:
        query = query.where(DemoExample.topic == topic)

    # Get random examples using SQL RANDOM()
    query = query.order_by(func.random()).limit(count)

    result = await db.execute(query)
    examples = result.scalars().all()

    # Get all available topics
    topics_result = await db.execute(
        select(DemoExample.topic).where(DemoExample.is_active == True).distinct()
    )
    available_topics = [row[0] for row in topics_result.fetchall()]

    # Convert to response format
    example_list = []
    for ex in examples:
        # Determine display name for topic
        topic_display = ex.topic_zh or ex.topic.replace("_", " ").title()

        example_list.append(InspirationExample(
            id=str(ex.id),
            topic=ex.topic,
            topic_display=topic_display,
            prompt=ex.prompt,
            image_url=ex.image_url,
            video_url=ex.video_url,
            thumbnail_url=ex.thumbnail_url,
            title=ex.title,
            style_tags=ex.style_tags or []
        ))

    return InspirationResponse(
        success=True,
        examples=example_list,
        topics=available_topics,
        total_count=len(example_list)
    )


@router.post("/generate", response_model=ProductVideoResponse)
async def generate_product_video(
    request: ProductVideoRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate product ads video from prompt (Demo Tier).

    Flow:
    1. Check demo usage limit (2 uses per user)
    2. Content moderation (reject illegal/18+ content)
    3. Enhance prompt with Gemini AI
    4. Check for similar cached prompts (>85% similarity)
    5. If similar found: return cached result (saves credits)
    6. If not found: generate new image & video with Leonardo AI
    7. Cache result for future similarity matching
    8. Increment demo usage count

    Demo tier limitations:
    - 720p resolution
    - Watermark on video
    - 2 uses per user (resets weekly)
    """
    from app.models.user import User
    from datetime import datetime, timedelta
    from uuid import UUID

    gemini = get_gemini_service()
    similarity = get_similarity_service()
    rescue_service = get_rescue_service()

    # Step 0: Check demo usage limit if user_id provided
    user = None
    if request.user_id:
        try:
            user_result = await db.execute(
                select(User).where(User.id == UUID(request.user_id))
            )
            user = user_result.scalar_one_or_none()

            if user and not user.can_use_demo:
                return ProductVideoResponse(
                    success=False,
                    from_cache=False,
                    original_prompt=request.prompt,
                    demo_uses_remaining=0,
                    error="Demo usage limit reached (2 uses). Please upgrade to continue.",
                    credits_used=0
                )
        except Exception:
            pass  # Continue without user tracking if ID is invalid

    # Step 1: Content moderation
    moderation = await gemini.moderate_content(request.prompt)
    if not moderation.get("is_safe", True):
        return ProductVideoResponse(
            success=False,
            from_cache=False,
            original_prompt=request.prompt,
            blocked_reason=moderation.get("reason", "Content violates usage policy"),
            credits_used=0
        )

    # Step 2: Enhance prompt and get embedding
    processed = await gemini.process_user_prompt(
        prompt=request.prompt,
        category=request.category,
        style=request.style
    )

    if not processed.get("success"):
        return ProductVideoResponse(
            success=False,
            from_cache=False,
            original_prompt=request.prompt,
            blocked_reason=processed.get("blocked_reason"),
            credits_used=0
        )

    enhanced_prompt = processed.get("enhanced_prompt", request.prompt)
    embedding = processed.get("embedding", [])

    # Step 3: Check for similar cached prompts
    similar = await similarity.find_similar_prompt(
        prompt=request.prompt,
        db=db,
        embedding=embedding
    )

    if similar and similar.get("found"):
        # Return cached result - no credits used!
        return ProductVideoResponse(
            success=True,
            from_cache=True,
            similarity_score=similar.get("similarity"),
            original_prompt=request.prompt,
            enhanced_prompt=similar.get("prompt_enhanced"),
            image_url=similar.get("image_url"),
            video_url=similar.get("video_url"),
            video_url_watermarked=similar.get("video_url_watermarked"),
            credits_used=0
        )

    # Step 4: Generate new content with rescue service (Wan primary, fal.ai rescue)
    try:
        # First generate image
        image_result = await rescue_service.generate_image(
            prompt=enhanced_prompt,
            width=1024,
            height=1024
        )

        if not image_result.get("success"):
            return ProductVideoResponse(
                success=False,
                from_cache=False,
                original_prompt=request.prompt,
                enhanced_prompt=enhanced_prompt,
                error=image_result.get("error", "Image generation failed"),
                credits_used=1  # Still costs credit even if failed
            )

        image_url = image_result.get("image_url")

        # Then generate video from image
        video_result = await rescue_service.generate_video(
            image_url=image_url,
            prompt=enhanced_prompt,
            length=5
        )

        video_url = video_result.get("video_url") if video_result.get("success") else None

        # Step 5: Cache result for future similarity matching
        await similarity.cache_generation_result(
            prompt=request.prompt,
            enhanced_prompt=enhanced_prompt,
            embedding=embedding,
            image_url=image_url,
            video_url=video_url,
            video_url_watermarked=video_url,  # Add watermark service later
            db=db
        )

        # Step 6: Increment demo usage count
        demo_uses_remaining = None
        if user:
            user.demo_usage_count = (user.demo_usage_count or 0) + 1
            await db.commit()
            demo_uses_remaining = user.demo_uses_remaining

        # Step 7: Collect user generation to material library for future use
        try:
            from app.services.material.collector import UserContentCollector
            from app.services.base import GenerationResult, GenerationType
            import uuid

            collector = UserContentCollector(db)
            gen_result = GenerationResult(
                success=True,
                task_id=str(uuid.uuid4()),
                service_name="wan",  # Using Wan as primary service
                generation_type=GenerationType.TEXT_TO_IMAGE,
                prompt=request.prompt,
                source_image_url=image_url,  # Source is the generated image
                image_url=image_url,
                video_url=video_url
            )
            await collector.on_generation_complete(
                generation_id=str(uuid.uuid4()),
                result=gen_result,
                user_id=request.user_id or "anonymous",
                category_hint=request.category
            )
        except Exception as collect_error:
            # Don't fail the request if collection fails
            pass

        return ProductVideoResponse(
            success=True,
            from_cache=False,
            original_prompt=request.prompt,
            enhanced_prompt=enhanced_prompt,
            image_url=image_url,
            video_url=video_url,
            video_url_watermarked=video_url,  # Add watermark service later
            credits_used=2,  # 1 for image + 1 for video
            demo_uses_remaining=demo_uses_remaining
        )

    except Exception as e:
        return ProductVideoResponse(
            success=False,
            from_cache=False,
            original_prompt=request.prompt,
            enhanced_prompt=enhanced_prompt,
            error=str(e),
            credits_used=0
        )


# =============================================================================
# PAID TIER GENERATION (with image upload & Material DB storage)
# =============================================================================

@router.post("/generate/paid", response_model=PaidGenerationResponse)
async def generate_paid_tier(
    request: PaidGenerationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Paid tier generation with image upload support.

    Flow:
    1. Verify user is paid tier (not demo)
    2. If image provided: moderate and describe with Gemini
    3. Enhance prompt with Gemini
    4. Call generation API (Leonardo/GoEnhance/Pollo)
    5. Store result to Material DB with Gemini description as primary key
    6. Result becomes example for demo users

    Key differences from demo tier:
    - Can upload custom images
    - Always calls APIs (never reads from Material DB)
    - Results stored as examples for others
    """
    from app.models.user import User
    from app.models.material import Material, ToolType, MaterialSource, MaterialStatus
    from uuid import UUID
    import time

    gemini = get_gemini_service()
    rescue_service = get_rescue_service()

    generation_steps = []
    total_cost = 0.0

    # Step 1: Verify paid user
    try:
        user_result = await db.execute(
            select(User).where(User.id == UUID(request.user_id))
        )
        user = user_result.scalar_one_or_none()

        if not user:
            return PaidGenerationResponse(
                success=False,
                original_prompt=request.prompt,
                error="User not found"
            )

        # Check if user is paid tier
        if user.plan_id in [None, "demo", "free"]:
            return PaidGenerationResponse(
                success=False,
                original_prompt=request.prompt,
                error="Paid tier required. Demo users should use /generate endpoint."
            )
    except Exception as e:
        return PaidGenerationResponse(
            success=False,
            original_prompt=request.prompt,
            error=f"User verification failed: {str(e)}"
        )

    # Step 2: Process uploaded image (if provided)
    image_description = None
    image_tags = []
    input_image_url = request.image_url

    if request.image_url or request.image_base64:
        # Moderate image content
        mod_result = await gemini.moderate_image(
            image_url=request.image_url,
            image_base64=request.image_base64
        )

        if not mod_result.get("is_safe", True):
            return PaidGenerationResponse(
                success=False,
                original_prompt=request.prompt,
                blocked_reason=f"Image content violates policy: {mod_result.get('reason', 'Inappropriate content')}"
            )

        # Describe image (becomes primary key in Material DB)
        desc_result = await gemini.describe_image(
            image_url=request.image_url,
            image_base64=request.image_base64
        )

        if desc_result.get("success"):
            image_description = desc_result.get("description", "")
            image_tags = desc_result.get("tags", [])

            generation_steps.append({
                "step": 1,
                "api": "gemini",
                "action": "image_analysis",
                "input": {"image_provided": True},
                "output": {
                    "description": image_description,
                    "category": desc_result.get("category"),
                    "tags": image_tags
                }
            })

    # Step 3: Content moderation and prompt enhancement
    moderation = await gemini.moderate_content(request.prompt)
    if not moderation.get("is_safe", True):
        return PaidGenerationResponse(
            success=False,
            original_prompt=request.prompt,
            blocked_reason=moderation.get("reason", "Content violates usage policy")
        )

    processed = await gemini.process_user_prompt(
        prompt=request.prompt,
        category=request.category,
        style=request.style
    )
    enhanced_prompt = processed.get("enhanced_prompt", request.prompt)

    generation_steps.append({
        "step": len(generation_steps) + 1,
        "api": "gemini",
        "action": "enhance_prompt",
        "input": {"prompt": request.prompt},
        "output": {"enhanced_prompt": enhanced_prompt}
    })

    # Step 4: Generate based on tool type
    result_image_url = None
    result_video_url = None

    try:
        tool = request.tool.lower()
        start_time = time.time()

        if tool == "short_video":
            # Video generation with Pollo AI
            from app.services.pollo_service import get_pollo_client
            pollo = get_pollo_client()

            result = await pollo.generate_video(
                prompt=enhanced_prompt,
                source_image_url=input_image_url
            )

            if result.get("success"):
                result_video_url = result.get("video_url")
                total_cost += 0.10

                generation_steps.append({
                    "step": len(generation_steps) + 1,
                    "api": "pollo",
                    "action": "text_to_video",
                    "input": {"prompt": enhanced_prompt, "image_url": input_image_url},
                    "result_url": result_video_url,
                    "cost": 0.10,
                    "duration_ms": int((time.time() - start_time) * 1000)
                })
        else:
            # Image generation with rescue service (Wan primary, fal.ai rescue)
            image_result = await rescue_service.generate_image(
                prompt=enhanced_prompt,
                width=1024,
                height=1024
            )

            if image_result.get("success"):
                result_image_url = image_result.get("image_url")
                total_cost += 0.01

                # Generate video from image
                video_result = await rescue_service.generate_video(
                    image_url=result_image_url,
                    prompt=enhanced_prompt,
                    length=5
                )
                result_video_url = video_result.get("video_url") if video_result.get("success") else None
                if result_video_url:
                    total_cost += 0.01

                generation_steps.append({
                    "step": len(generation_steps) + 1,
                    "api": "wan",
                    "action": "generate",
                    "input": {"prompt": enhanced_prompt},
                    "result_image_url": result_image_url,
                    "result_video_url": result_video_url,
                    "cost": 0.02,
                    "duration_ms": int((time.time() - start_time) * 1000)
                })

        if not result_image_url and not result_video_url:
            return PaidGenerationResponse(
                success=False,
                original_prompt=request.prompt,
                enhanced_prompt=enhanced_prompt,
                error="Generation failed"
            )

    except Exception as e:
        return PaidGenerationResponse(
            success=False,
            original_prompt=request.prompt,
            enhanced_prompt=enhanced_prompt,
            error=f"Generation error: {str(e)}"
        )

    # Step 5: Store to Material DB (becomes example for demo users)
    try:
        # Map tool string to ToolType enum
        tool_type_map = {
            "background_removal": ToolType.BACKGROUND_REMOVAL,
            "product_scene": ToolType.PRODUCT_SCENE,
            "try_on": ToolType.TRY_ON,
            "room_redesign": ToolType.ROOM_REDESIGN,
            "short_video": ToolType.SHORT_VIDEO
        }
        tool_type = tool_type_map.get(request.tool, ToolType.BACKGROUND_REMOVAL)

        # Primary key is Gemini description (or prompt if no image)
        primary_description = image_description or request.prompt

        material = Material(
            tool_type=tool_type,
            topic=request.category,
            tags=image_tags or [request.category],
            source=MaterialSource.USER,
            source_user_id=user.id,
            status=MaterialStatus.PENDING,  # Needs admin review
            prompt=request.prompt,
            prompt_enhanced=enhanced_prompt,
            input_image_url=input_image_url,
            input_params=request.params,
            generation_steps=generation_steps,
            result_image_url=result_image_url,
            result_video_url=result_video_url,
            generation_cost_usd=total_cost,
            quality_score=0.7,  # Default, can be updated by admin
            title_en=primary_description[:255] if len(primary_description) > 255 else primary_description,
            is_active=True
        )

        db.add(material)
        await db.commit()
        await db.refresh(material)

        material_id = str(material.id)

    except Exception as e:
        # Don't fail the request if material storage fails
        material_id = None

    return PaidGenerationResponse(
        success=True,
        original_prompt=request.prompt,
        enhanced_prompt=enhanced_prompt,
        image_description=image_description,
        image_tags=image_tags,
        input_image_url=input_image_url,
        result_image_url=result_image_url,
        result_video_url=result_video_url,
        material_id=material_id,
        generation_steps=generation_steps,
        credits_used=int(total_cost * 100)  # Convert to credits
    )


@router.get("/topics")
async def get_available_topics(
    db: AsyncSession = Depends(get_db)
):
    """
    Get all available topics with example counts.
    Used for topic filter in inspiration gallery.
    """
    from sqlalchemy import func

    # Get topic counts
    result = await db.execute(
        select(
            DemoExample.topic,
            DemoExample.topic_zh,
            DemoExample.topic_en,
            func.count(DemoExample.id).label("count")
        )
        .where(DemoExample.is_active == True)
        .group_by(DemoExample.topic, DemoExample.topic_zh, DemoExample.topic_en)
    )
    rows = result.fetchall()

    topics = []
    for row in rows:
        topics.append({
            "slug": row[0],
            "name_zh": row[1] or row[0].replace("_", " ").title(),
            "name_en": row[2] or row[0].replace("_", " ").title(),
            "count": row[3]
        })

    return {
        "topics": topics,
        "total": len(topics)
    }


# =============================================================================
# TOOL SHOWCASE ENDPOINTS
# =============================================================================

@router.get("/tool-showcases/{tool_category}", response_model=ToolShowcaseResponse)
async def get_tool_showcases(
    tool_category: str,
    tool_id: Optional[str] = Query(None, description="Filter by specific tool ID"),
    limit: int = Query(10, ge=1, le=50, description="Number of showcases to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get tool showcases for a specific tool category.

    Categories:
    - edit_tools: Style Transfer, AI Enhance, Background Remove, etc.
    - ecommerce: Product Ads Video, Product Background, Model Try-on, etc.
    - architecture: Interior Design, Exterior Rendering, Space Planning, etc.
    - portrait: Portrait Enhancement, Style Portrait, Background Change, etc.

    Returns showcases with source image, prompt, and result (image/video).
    """
    from sqlalchemy import func

    # Build query
    query = select(ToolShowcase).where(
        ToolShowcase.tool_category == tool_category,
        ToolShowcase.is_active == True
    )

    if tool_id:
        query = query.where(ToolShowcase.tool_id == tool_id)

    # Order by featured first, then sort_order
    query = query.order_by(
        ToolShowcase.is_featured.desc(),
        ToolShowcase.sort_order.asc(),
        func.random()
    ).limit(limit)

    result = await db.execute(query)
    showcases = result.scalars().all()

    # Convert to response format
    showcase_list = []
    for sc in showcases:
        showcase_list.append(ToolShowcaseItem(
            id=str(sc.id),
            tool_category=sc.tool_category,
            tool_id=sc.tool_id,
            tool_name=sc.tool_name,
            tool_name_zh=sc.tool_name_zh,
            source_image_url=sc.source_image_url,
            prompt=sc.prompt,
            prompt_zh=sc.prompt_zh,
            result_image_url=sc.result_image_url,
            result_video_url=sc.result_video_url,
            title=sc.title,
            title_zh=sc.title_zh,
            description=sc.description,
            description_zh=sc.description_zh,
            duration_seconds=sc.duration_seconds or 5.0,
            style_tags=sc.style_tags or [],
            is_featured=sc.is_featured
        ))

    return ToolShowcaseResponse(
        success=True,
        showcases=showcase_list,
        tool_category=tool_category,
        tool_id=tool_id,
        total_count=len(showcase_list)
    )


@router.get("/tool-showcases/{tool_category}/{tool_id}", response_model=ToolShowcaseResponse)
async def get_tool_showcases_by_id(
    tool_category: str,
    tool_id: str,
    limit: int = Query(10, ge=1, le=50, description="Number of showcases to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get showcases for a specific tool.
    Shorthand for /tool-showcases/{category}?tool_id={id}
    """
    return await get_tool_showcases(tool_category, tool_id, limit, db)


@router.post("/tool-showcases/save")
async def save_user_showcase(
    request: SaveShowcaseRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Save a user-generated result as a showcase example.
    This allows user creations to appear in the example gallery.

    User-generated showcases are marked with is_user_generated=True.
    """
    import uuid

    # Create new showcase
    showcase = ToolShowcase(
        id=uuid.uuid4(),
        tool_category=request.tool_category,
        tool_id=request.tool_id,
        tool_name=request.tool_id.replace("_", " ").title(),
        source_image_url=request.source_image_url,
        prompt=request.prompt,
        result_image_url=request.result_image_url,
        result_video_url=request.result_video_url,
        is_user_generated=True,
        is_active=True,
        sort_order=100  # User-generated appear after featured
    )

    db.add(showcase)
    await db.commit()
    await db.refresh(showcase)

    return {
        "success": True,
        "id": str(showcase.id),
        "message": "Showcase saved successfully"
    }


@router.get("/tool-categories")
async def get_tool_categories(
    db: AsyncSession = Depends(get_db)
):
    """
    Get all tool categories with their tools and showcase counts.
    """
    from sqlalchemy import func

    # Get showcase counts by category and tool
    result = await db.execute(
        select(
            ToolShowcase.tool_category,
            ToolShowcase.tool_id,
            ToolShowcase.tool_name,
            ToolShowcase.tool_name_zh,
            func.count(ToolShowcase.id).label("count")
        )
        .where(ToolShowcase.is_active == True)
        .group_by(
            ToolShowcase.tool_category,
            ToolShowcase.tool_id,
            ToolShowcase.tool_name,
            ToolShowcase.tool_name_zh
        )
    )
    rows = result.fetchall()

    # Organize by category
    categories = {}
    for row in rows:
        cat = row[0]
        if cat not in categories:
            categories[cat] = {
                "category": cat,
                "category_name": cat.replace("_", " ").title(),
                "tools": []
            }
        categories[cat]["tools"].append({
            "tool_id": row[1],
            "tool_name": row[2],
            "tool_name_zh": row[3],
            "showcase_count": row[4]
        })

    return {
        "categories": list(categories.values()),
        "total_categories": len(categories)
    }


# =============================================================================
# LEGACY ENDPOINTS
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
    Get all available transformation styles.
    """
    return [
        StyleInfo(
            id=style_id,
            name=info["name"],
            slug=info["slug"],
            version=info.get("version")
        )
        for style_id, info in DEMO_STYLES.items()
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

    demo_service = get_demo_service()
    results = {}

    # Available styles for variety
    style_slugs = [info["slug"] for info in DEMO_STYLES.values()]

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


# =============================================================================
# AI AVATAR ENDPOINTS (Language-Based) - Must be before /{demo_id} catch-all
# =============================================================================

@router.get("/avatars")
async def get_avatar_materials(
    language: str = Query("en", description="Language code: 'en' or 'zh-TW'"),
    topic: Optional[str] = Query(None, description="Avatar topic filter"),
    limit: int = Query(10, description="Maximum number of avatars to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI Avatar examples based on user's language preference.

    When user visits zh-TW page, shows zh-TW avatar examples.
    When user visits en page, shows en avatar examples.
    Default is English.

    Supported languages: 'en', 'zh-TW'
    """
    from app.models.material import Material, ToolType, MaterialStatus
    from sqlalchemy import func

    # Validate language
    if language not in ["en", "zh-TW"]:
        language = "en"

    # Build query for avatar materials
    query = select(Material).where(
        Material.tool_type == ToolType.AI_AVATAR,
        Material.language == language,
        Material.status == MaterialStatus.APPROVED,
        Material.is_active == True,
        Material.result_video_url.isnot(None)
    )

    # Filter by topic if specified
    if topic:
        query = query.where(Material.topic == topic)

    # Order by quality score and randomize
    query = query.order_by(func.random()).limit(limit)

    result = await db.execute(query)
    materials = result.scalars().all()

    # Format response
    avatars = []
    for m in materials:
        avatars.append({
            "id": str(m.id),
            "topic": m.topic,
            "language": m.language,
            "script": m.prompt,
            "video_url": m.result_video_url,
            "thumbnail_url": m.result_thumbnail_url,
            "title": m.title_en if language == "en" else (m.title_zh or m.title_en),
            "view_count": m.view_count,
            "quality_score": m.quality_score
        })

    return {
        "success": True,
        "language": language,
        "count": len(avatars),
        "avatars": avatars
    }


@router.get("/avatars/topics")
async def get_avatar_topics(
    language: str = Query("en", description="Language code: 'en' or 'zh-TW'"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get available avatar topics for a language.

    Returns topics that have at least one avatar material available.
    """
    from app.models.material import Material, ToolType, MaterialStatus, MATERIAL_TOPICS
    from sqlalchemy import func

    # Get topic definitions
    avatar_topics = MATERIAL_TOPICS.get(ToolType.AI_AVATAR, [])

    # Count materials per topic for this language
    query = select(
        Material.topic,
        func.count(Material.id).label("count")
    ).where(
        Material.tool_type == ToolType.AI_AVATAR,
        Material.language == language,
        Material.status == MaterialStatus.APPROVED,
        Material.is_active == True
    ).group_by(Material.topic)

    result = await db.execute(query)
    topic_counts = {row.topic: row.count for row in result}

    # Format topics with counts
    topics = []
    for topic in avatar_topics:
        topic_id = topic["topic_id"]
        count = topic_counts.get(topic_id, 0)

        if language == "zh-TW":
            name = topic.get("name_zh", topic["name_en"])
        else:
            name = topic["name_en"]

        topics.append({
            "topic_id": topic_id,
            "name": name,
            "count": count,
            "has_materials": count > 0
        })

    return {
        "language": language,
        "topics": topics
    }


# =============================================================================
# DEMO BY ID - Catch-all route (must be last)
# =============================================================================

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


# =============================================================================
# MATERIAL LIBRARY ENDPOINTS
# =============================================================================

@router.get("/materials/status")
async def get_material_status(
    db: AsyncSession = Depends(get_db)
):
    """
    Get material library status and sufficiency check.
    Shows what materials are available and what's missing.
    """
    library = MaterialLibraryService(db)

    # Get all requirements with current status
    requirements = await library.get_all_requirements()

    # Get missing materials
    missing = await library.get_missing_materials()

    # Calculate totals
    total_required = sum(r.min_count for r in requirements)
    total_current = sum(r.current_count for r in requirements)
    total_missing = sum(r.missing_count for r in requirements)

    sufficiency_pct = (total_current / total_required * 100) if total_required > 0 else 100

    # Format requirements for response
    requirements_data = []
    for req in requirements:
        requirements_data.append({
            "category": req.category,
            "tool_id": req.tool_id,
            "min_count": req.min_count,
            "current_count": req.current_count,
            "missing_count": req.missing_count,
            "is_sufficient": req.is_sufficient
        })

    return {
        "total_required": total_required,
        "total_current": total_current,
        "total_missing": total_missing,
        "sufficiency_percentage": round(sufficiency_pct, 1),
        "is_sufficient": total_missing == 0,
        "requirements": requirements_data,
        "missing": missing
    }


@router.get("/materials/categories")
async def get_material_categories():
    """
    Get all material categories and their tool requirements.
    Used for understanding what tools need showcases.
    """
    categories = []

    for category_id, category in MATERIAL_REQUIREMENTS.items():
        tools = []
        for tool in category.tools:
            tools.append({
                "tool_id": tool.tool_id,
                "tool_name": tool.tool_name,
                "tool_name_zh": tool.tool_name_zh,
                "min_showcases": tool.min_showcases,
                "generation_type": tool.generation_type,
                "requires_source_image": tool.requires_source_image
            })

        categories.append({
            "category_id": category_id,
            "category_name": category.category_name,
            "category_name_zh": category.category_name_zh,
            "tools": tools,
            "total_tools": len(tools)
        })

    return {
        "categories": categories,
        "total_categories": len(categories)
    }


@router.get("/materials/collection-stats")
async def get_collection_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    Get statistics about user content collection.
    Shows how many user-generated materials have been collected and promoted.
    """
    collector = UserContentCollector(db)
    stats = await collector.get_collection_stats()

    return stats


@router.post("/materials/collect", include_in_schema=False)
async def collect_user_material(
    source_image_url: str,
    result_image_url: Optional[str] = None,
    result_video_url: Optional[str] = None,
    prompt: str = "",
    user_id: str = "",
    generation_id: str = "",
    service_name: str = "unknown",
    db: AsyncSession = Depends(get_db)
):
    """
    Manually collect a user generation as material.
    This is typically called automatically after generation.
    For admin/testing use.
    """
    library = MaterialLibraryService(db)

    material_id = await library.collect_user_content(
        source_image_url=source_image_url,
        result_image_url=result_image_url,
        result_video_url=result_video_url,
        prompt=prompt,
        user_id=user_id,
        generation_id=generation_id,
        service_name=service_name
    )

    if material_id:
        return {"success": True, "material_id": material_id}
    else:
        return {"success": False, "message": "Material not collected (quality threshold not met)"}


@router.post("/materials/promote/{material_id}", include_in_schema=False)
async def promote_material_to_showcase(
    material_id: str,
    tool_category: str,
    tool_id: str,
    review_notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Promote a user-generated material to an official showcase.
    For admin use only.
    """
    library = MaterialLibraryService(db)

    success = await library.promote_to_showcase(
        material_id=material_id,
        tool_category=tool_category,
        tool_id=tool_id,
        review_notes=review_notes
    )

    if success:
        return {"success": True, "message": "Material promoted to showcase"}
    else:
        return {"success": False, "message": "Failed to promote material"}


# =============================================================================
# INSPIRATION GALLERY - 24 Categories
# =============================================================================

# Map gallery categories to material topics
GALLERY_CATEGORY_MAP = {
    "video": ["short_video", "video"],
    "recommended": ["product", "ecommerce", "brand"],
    "portrait": ["portrait", "people", "human"],
    "photography": ["photography", "realistic"],
    "animation": ["animation", "cartoon", "animated"],
    "poster": ["poster", "illustration", "design"],
    "anime": ["anime", "manga", "2d"],
    "ecommerceDesign": ["ecommerce", "product", "shopping"],
    "chinese": ["chinese", "oriental", "asian"],
    "female": ["female", "woman", "girl"],
    "male": ["male", "man", "boy"],
    "interior": ["interior", "room", "home"],
    "architectureLandscape": ["architecture", "landscape", "building"],
    "toys": ["toys", "figures", "collectibles"],
    "art": ["art", "painting", "artistic"],
    "productDesign": ["product", "industrial", "design"],
    "gameCG": ["game", "cg", "gaming"],
    "nature": ["nature", "natural", "landscape"],
    "threeD": ["3d", "render", "dimensional"],
    "logoUI": ["logo", "ui", "branding"],
    "character": ["character", "ip", "mascot"],
    "animals": ["animals", "pets", "wildlife"],
    "fantasy": ["fantasy", "magical", "mythical"],
    "scifi": ["scifi", "futuristic", "tech"]
}


@router.get("/inspirations")
async def get_inspirations(
    category: str = Query("recommended", description="Gallery category"),
    language: str = Query("en", description="Language code for prompts"),
    limit: int = Query(8, ge=4, le=20, description="Number of items to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get inspiration gallery items for the homepage.

    Returns images with prompts organized by category.
    Clicking an item shows the generation prompt in the user's language.

    Categories:
    - video, recommended, portrait, photography, animation, poster
    - anime, ecommerceDesign, chinese, female, male, interior
    - architectureLandscape, toys, art, productDesign, gameCG, nature
    - threeD, logoUI, character, animals, fantasy, scifi
    """
    from sqlalchemy import func, or_
    from app.models.material import Material, MaterialStatus

    # Get topic keywords for this category
    topic_keywords = GALLERY_CATEGORY_MAP.get(category, [category])

    # Build query to find materials matching any of the topic keywords
    conditions = []
    for keyword in topic_keywords:
        conditions.append(Material.topic.ilike(f"%{keyword}%"))
        conditions.append(Material.tags.contains([keyword]))

    # Query materials with images
    result = await db.execute(
        select(Material)
        .where(
            or_(*conditions) if conditions else True,
            Material.is_active == True,
            or_(
                Material.result_image_url.isnot(None),
                Material.input_image_url.isnot(None)
            )
        )
        .order_by(func.random())
        .limit(limit)
    )
    materials = result.scalars().all()

    # Format response based on language
    items = []
    for m in materials:
        # Determine title based on language
        if language.startswith("zh"):
            title = m.title_zh or m.title_en or f"{category} #{len(items) + 1}"
        elif language.startswith("ja"):
            title = m.title_en or f"{category} #{len(items) + 1}"  # TODO: Add ja titles
        elif language.startswith("ko"):
            title = m.title_en or f"{category} #{len(items) + 1}"  # TODO: Add ko titles
        elif language.startswith("es"):
            title = m.title_en or f"{category} #{len(items) + 1}"  # TODO: Add es titles
        else:
            title = m.title_en or f"{category} #{len(items) + 1}"

        # Get the prompt (prefer localized if available)
        prompt = m.prompt or m.prompt_enhanced or ""

        # Get best available image
        thumb = m.result_image_url or m.input_image_url or m.result_thumbnail_url

        if thumb:  # Only include items with images
            items.append({
                "id": str(m.id),
                "title": title,
                "thumb": thumb,
                "prompt": prompt,
                "category": category
            })

    return {
        "success": True,
        "items": items,
        "category": category,
        "language": language,
        "total": len(items)
    }


# =============================================================================
# LANDING PAGE EXAMPLES
# =============================================================================

# Map material topics to landing page categories
TOPIC_TO_CATEGORY = {
    "spokesperson": "brand",
    "product_intro": "ecommerce",
    "customer_service": "service",
    "social_media": "social",
    "education": "app",
    "marketing": "promo",
    "tutorial": "app",
    "announcement": "promo"
}


@router.get("/landing/examples")
async def get_landing_examples(
    language: str = Query("en", description="Language code"),
    page: int = Query(1, description="Page number (1-based)"),
    per_page: int = Query(6, description="Examples per page"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get examples for landing page gallery organized by category.
    Returns materials from DB with both product videos and avatars per category.
    Avatar MUST match the same topic as product video for coherent content.
    Supports pagination for View More functionality.
    """
    from sqlalchemy import func, or_
    from app.models.material import Material, MaterialStatus, ToolType

    # Determine avatar language based on user's language
    avatar_lang = "zh-TW" if language.startswith("zh") else "en"

    # Landing page categories we want
    landing_topics = ["ecommerce", "social", "brand", "app", "promo", "service"]

    # Query ALL avatars for the user's language, grouped by topic
    avatars_result = await db.execute(
        select(Material)
        .where(
            Material.tool_type == ToolType.AI_AVATAR,
            Material.language == avatar_lang,
            Material.result_video_url.isnot(None),
            Material.is_active == True,
            Material.topic.in_(landing_topics)
        )
    )
    avatars = avatars_result.scalars().all()

    # Create lookup of avatars by topic (list to support multiple per topic)
    avatar_by_topic = {}
    for a in avatars:
        if a.topic not in avatar_by_topic:
            avatar_by_topic[a.topic] = []
        avatar_by_topic[a.topic].append(a)

    # Query ALL product videos for landing topics
    videos_result = await db.execute(
        select(Material)
        .where(
            Material.tool_type == ToolType.SHORT_VIDEO,
            Material.result_video_url.isnot(None),
            Material.is_active == True,
            Material.topic.in_(landing_topics)
        )
        .order_by(Material.created_at.desc())
    )
    videos = videos_result.scalars().all()

    # Track which avatars we've used per topic for matching
    avatar_index_by_topic = {topic: 0 for topic in landing_topics}

    # Build examples list with matched avatars
    all_examples = []
    for video in videos:
        topic = video.topic

        # Get next avatar for this topic (rotating through available avatars)
        topic_avatars = avatar_by_topic.get(topic, [])
        avatar = None
        if topic_avatars:
            idx = avatar_index_by_topic[topic] % len(topic_avatars)
            avatar = topic_avatars[idx]
            avatar_index_by_topic[topic] += 1

        avatar_video = avatar.result_video_url if avatar else None

        all_examples.append({
            "id": str(video.id),
            "category": topic,
            "title": video.title_zh if language.startswith("zh") else (video.title_en or topic.replace("_", " ").title()),
            "title_zh": video.title_zh,
            "title_en": video.title_en or topic.replace("_", " ").title(),
            "prompt": video.prompt[:100] if video.prompt else "",
            "thumb": video.input_image_url or f"https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600",
            "video": video.result_video_url,
            "avatar_video": avatar_video,
            "duration": "8s",
            "topic": topic
        })

    # Paginate
    total = len(all_examples)
    start = (page - 1) * per_page
    end = start + per_page
    examples = all_examples[start:end]

    return {
        "success": True,
        "examples": examples,
        "avatar_language": avatar_lang,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 1,
            "has_more": end < total
        }
    }


@router.get("/landing/watch-demo")
async def get_watch_demo(
    language: str = Query("en", description="Language code"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a random ad video for Watch Demo button.
    Returns a random material with video from the DB.
    """
    from sqlalchemy import func
    from app.models.material import Material

    # Query random material with video
    result = await db.execute(
        select(Material)
        .where(
            Material.result_video_url.isnot(None),
            Material.is_active == True,
            Material.language == language if language else True
        )
        .order_by(func.random())
        .limit(1)
    )
    material = result.scalar_one_or_none()

    if material:
        return {
            "success": True,
            "video": {
                "id": str(material.id),
                "title": material.title_zh if language.startswith("zh") else (material.title_en or "AI Generated Video"),
                "video_url": material.result_video_url,
                "thumb": material.input_image_url,
                "prompt": material.prompt,
                "topic": material.topic
            }
        }

    # Fallback if no materials
    return {
        "success": False,
        "error": "No demo videos available"
    }


@router.get("/landing/view-more")
async def get_view_more_examples(
    language: str = Query("en", description="Language code"),
    category: str = Query(None, description="Filter by category (optional)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get 6 random short videos with AI Avatar for "View More Examples" modal.
    Each video is paired with an AI Avatar from the same topic.
    """
    from sqlalchemy import func
    from app.models.material import Material, ToolType

    # Determine avatar language
    avatar_lang = "zh-TW" if language.startswith("zh") else "en"

    # Landing page categories
    landing_topics = ["ecommerce", "social", "brand", "app", "promo", "service"]

    # Filter by category if provided
    if category and category != "all" and category in landing_topics:
        topics_to_query = [category]
    else:
        topics_to_query = landing_topics

    # Get random product videos
    videos_result = await db.execute(
        select(Material)
        .where(
            Material.tool_type == ToolType.SHORT_VIDEO,
            Material.result_video_url.isnot(None),
            Material.is_active == True,
            Material.topic.in_(topics_to_query)
        )
        .order_by(func.random())
        .limit(6)
    )
    videos = videos_result.scalars().all()

    # Get all avatars for the language
    avatars_result = await db.execute(
        select(Material)
        .where(
            Material.tool_type == ToolType.AI_AVATAR,
            Material.language == avatar_lang,
            Material.result_video_url.isnot(None),
            Material.is_active == True,
            Material.topic.in_(landing_topics)
        )
    )
    avatars = avatars_result.scalars().all()

    # Create lookup by topic
    avatar_by_topic = {}
    for a in avatars:
        if a.topic not in avatar_by_topic:
            avatar_by_topic[a.topic] = []
        avatar_by_topic[a.topic].append(a)

    # Build response with video + matching avatar
    import random
    examples = []
    for video in videos:
        # Get random avatar from same topic
        topic_avatars = avatar_by_topic.get(video.topic, [])
        avatar = random.choice(topic_avatars) if topic_avatars else None
        avatar_video = avatar.result_video_url if avatar else None

        examples.append({
            "id": str(video.id),
            "category": video.topic,
            "title": video.title_zh if language.startswith("zh") else (video.title_en or video.topic.replace("_", " ").title()),
            "prompt": video.prompt[:100] if video.prompt else "",
            "thumb": video.input_image_url,
            "video": video.result_video_url,
            "avatar_video": avatar_video,
            "duration": "8s"
        })

    return {
        "success": True,
        "examples": examples,
        "total": len(examples),
        "avatar_language": avatar_lang
    }
