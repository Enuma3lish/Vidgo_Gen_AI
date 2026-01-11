"""
Prompt Template API Endpoints

Provides endpoints for:
- Getting default prompts for demo/non-subscribed users
- Generating context-aware prompts
- Managing prompt templates (admin)
- Caching and retrieving results

IMPORTANT ACCESS RULES:
- Non-subscribed/demo users: Can ONLY use default prompts with cached results
- Non-subscribed/demo users: CANNOT download original quality results (watermarked only)
- Subscribed users: Can use custom prompts and call APIs
- Subscribed users: Can download original quality results
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import httpx

from app.core.database import get_db
from app.services.prompt_generator import (
    PromptGeneratorService,
    get_prompt_generator_service,
)
from app.models.prompt_template import PromptGroup, PromptSubTopic

router = APIRouter()


# === Request/Response Models ===

class PromptGenerateRequest(BaseModel):
    """Request model for prompt generation."""
    group: str = Field(..., description="Prompt group (e.g., background_removal, product_effect)")
    sub_topic: Optional[str] = Field(None, description="Sub-topic within the group")
    language: str = Field("en", description="Language code (en, zh-TW, ja, ko, es)")
    context: Optional[dict] = Field(None, description="Additional context for prompt generation")


class PromptTemplateResponse(BaseModel):
    """Response model for a prompt template."""
    id: str
    prompt: str
    prompt_zh: Optional[str] = None
    group: str
    sub_topic: str
    input_image_url: Optional[str] = None
    result_image_url: Optional[str] = None
    result_video_url: Optional[str] = None
    result_thumbnail_url: Optional[str] = None
    result_watermarked_url: Optional[str] = None
    title_en: Optional[str] = None
    title_zh: Optional[str] = None


class PromptGenerateResponse(BaseModel):
    """Response model for generated prompt."""
    prompt: str
    prompt_localized: Optional[str] = None
    group: str
    sub_topic: str
    template_id: Optional[str] = None
    has_cached_result: bool = False
    cached_result: Optional[dict] = None


class CacheResultRequest(BaseModel):
    """Request model for caching a result."""
    template_id: str
    input_data: dict = Field(..., description="Input/before data")
    result_data: dict = Field(..., description="Generated result data")
    generation_time_ms: int = 0
    cost_usd: float = 0.0


class CreateTemplateRequest(BaseModel):
    """Request model for creating a template."""
    prompt: str
    group: str
    sub_topic: str = "default"
    prompt_translations: Optional[dict] = None
    input_data: Optional[dict] = None
    result_data: Optional[dict] = None
    api_info: Optional[dict] = None
    is_default: bool = True
    keywords: List[str] = []
    tags: List[str] = []


class RecordUsageRequest(BaseModel):
    """Request model for recording template usage."""
    template_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    source_page: str = "tool_page"
    user_tier: str = "free"
    used_cached: bool = True
    was_successful: bool = True
    generation_time_ms: Optional[int] = None
    custom_prompt: Optional[str] = None
    custom_params: Optional[dict] = None


class GroupInfo(BaseModel):
    """Response model for group information."""
    group: str
    display_en: str
    display_zh: str
    template_count: int


class SubTopicInfo(BaseModel):
    """Response model for sub-topic information."""
    sub_topic: str
    display_en: str
    display_zh: str
    template_count: int


# === Endpoints ===

@router.get("/groups", response_model=List[GroupInfo])
async def get_all_groups(
    db: AsyncSession = Depends(get_db),
):
    """
    Get all available prompt groups with their display names.
    """
    service = get_prompt_generator_service(db)
    groups = await service.get_all_groups()
    return groups


@router.get("/groups/{group}/sub-topics", response_model=List[SubTopicInfo])
async def get_sub_topics(
    group: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all sub-topics available for a specific group.
    """
    try:
        prompt_group = PromptGroup(group)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid group: {group}")

    service = get_prompt_generator_service(db)
    sub_topics = await service.get_sub_topics_for_group(prompt_group)
    return sub_topics


@router.post("/generate", response_model=PromptGenerateResponse)
async def generate_prompt(
    request: PromptGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a context-aware prompt based on group and sub_topic.

    This endpoint helps users by suggesting relevant prompts
    based on the tool/feature they're using.
    """
    try:
        prompt_group = PromptGroup(request.group)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid group: {request.group}")

    sub_topic = None
    if request.sub_topic:
        try:
            sub_topic = PromptSubTopic(request.sub_topic)
        except ValueError:
            sub_topic = PromptSubTopic.DEFAULT

    service = get_prompt_generator_service(db)
    result = await service.generate_prompt(
        group=prompt_group,
        sub_topic=sub_topic,
        language=request.language,
        context=request.context,
    )

    return PromptGenerateResponse(**result)


@router.get("/defaults/{group}", response_model=List[PromptTemplateResponse])
async def get_default_templates(
    group: str,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """
    Get default templates with cached results for demo/non-subscribed users.

    This endpoint is crucial for reducing API calls - demo users
    can only use these pre-generated results.
    """
    try:
        prompt_group = PromptGroup(group)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid group: {group}")

    service = get_prompt_generator_service(db)
    templates = await service.get_default_templates_for_demo(
        group=prompt_group,
        limit=limit,
    )

    return [PromptTemplateResponse(**t) for t in templates]


@router.get("/cached")
async def get_cached_result(
    group: str,
    prompt: str,
    sub_topic: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Check if a cached result exists for a prompt.

    Returns the cached result if available, reducing API calls.
    """
    try:
        prompt_group = PromptGroup(group)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid group: {group}")

    sub_topic_enum = None
    if sub_topic:
        try:
            sub_topic_enum = PromptSubTopic(sub_topic)
        except ValueError:
            pass

    service = get_prompt_generator_service(db)
    result = await service.get_cached_result(
        group=prompt_group,
        prompt=prompt,
        sub_topic=sub_topic_enum,
    )

    if result:
        return {"cached": True, **result}
    return {"cached": False}


@router.get("/templates/{group}", response_model=List[PromptTemplateResponse])
async def get_templates_by_group(
    group: str,
    sub_topic: Optional[str] = None,
    language: str = "en",
    limit: int = Query(10, ge=1, le=50),
    include_premium: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    Get templates filtered by group and optionally sub_topic.
    """
    try:
        prompt_group = PromptGroup(group)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid group: {group}")

    sub_topic_enum = None
    if sub_topic:
        try:
            sub_topic_enum = PromptSubTopic(sub_topic)
        except ValueError:
            pass

    service = get_prompt_generator_service(db)
    templates = await service.get_templates_by_group(
        group=prompt_group,
        sub_topic=sub_topic_enum,
        language=language,
        limit=limit,
        include_premium=include_premium,
    )

    return [
        PromptTemplateResponse(
            id=str(t.id),
            prompt=t.prompt,
            prompt_zh=t.prompt_zh,
            group=t.group.value,
            sub_topic=t.sub_topic.value,
            input_image_url=t.input_image_url,
            result_image_url=t.result_image_url,
            result_video_url=t.result_video_url,
            result_thumbnail_url=t.result_thumbnail_url,
            result_watermarked_url=t.result_watermarked_url,
            title_en=t.title_en,
            title_zh=t.title_zh,
        )
        for t in templates
    ]


@router.get("/similar")
async def find_similar_template(
    group: str,
    prompt: str,
    threshold: float = Query(0.7, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """
    Find a similar cached template using keyword matching.

    Useful for suggesting existing results when user enters a custom prompt.
    """
    try:
        prompt_group = PromptGroup(group)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid group: {group}")

    service = get_prompt_generator_service(db)
    template = await service.find_similar_template(
        prompt=prompt,
        group=prompt_group,
        threshold=threshold,
    )

    if template:
        return {
            "found": True,
            "template": PromptTemplateResponse(
                id=str(template.id),
                prompt=template.prompt,
                prompt_zh=template.prompt_zh,
                group=template.group.value,
                sub_topic=template.sub_topic.value,
                input_image_url=template.input_image_url,
                result_image_url=template.result_image_url,
                result_video_url=template.result_video_url,
                result_thumbnail_url=template.result_thumbnail_url,
                result_watermarked_url=template.result_watermarked_url,
                title_en=template.title_en,
                title_zh=template.title_zh,
            ),
        }

    return {"found": False}


@router.post("/usage")
async def record_usage(
    request: RecordUsageRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Record usage of a prompt template.

    Helps with analytics and improving recommendations.
    """
    service = get_prompt_generator_service(db)

    usage = await service.record_usage(
        template_id=request.template_id,
        user_id=request.user_id,
        session_id=request.session_id,
        source_page=request.source_page,
        user_tier=request.user_tier,
        used_cached=request.used_cached,
        was_successful=request.was_successful,
        generation_time_ms=request.generation_time_ms,
        custom_prompt=request.custom_prompt,
        custom_params=request.custom_params,
    )

    return {"success": True, "usage_id": str(usage.id)}


# === Admin Endpoints ===

@router.post("/admin/templates", tags=["Admin"])
async def create_template(
    request: CreateTemplateRequest,
    db: AsyncSession = Depends(get_db),
    # current_user = Depends(get_admin_user),  # Add auth
):
    """
    Create a new prompt template (Admin only).
    """
    try:
        prompt_group = PromptGroup(request.group)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid group: {request.group}")

    try:
        sub_topic = PromptSubTopic(request.sub_topic)
    except ValueError:
        sub_topic = PromptSubTopic.DEFAULT

    service = get_prompt_generator_service(db)

    template = await service.create_template(
        prompt=request.prompt,
        group=prompt_group,
        sub_topic=sub_topic,
        prompt_translations=request.prompt_translations,
        input_data=request.input_data,
        result_data=request.result_data,
        api_info=request.api_info,
        is_default=request.is_default,
        keywords=request.keywords,
        tags=request.tags,
    )

    return {
        "success": True,
        "template_id": str(template.id),
    }


@router.post("/admin/cache-result", tags=["Admin"])
async def cache_result(
    request: CacheResultRequest,
    db: AsyncSession = Depends(get_db),
    # current_user = Depends(get_admin_user),  # Add auth
):
    """
    Cache a generation result for a template (Admin only).
    """
    service = get_prompt_generator_service(db)

    template = await service.cache_result(
        template_id=request.template_id,
        input_data=request.input_data,
        result_data=request.result_data,
        generation_time_ms=request.generation_time_ms,
        cost_usd=request.cost_usd,
    )

    return {
        "success": True,
        "template_id": str(template.id),
        "is_cached": template.is_cached,
    }


@router.post("/admin/seed", tags=["Admin"])
async def seed_default_prompts(
    db: AsyncSession = Depends(get_db),
    # current_user = Depends(get_admin_user),  # Add auth
):
    """
    Seed the database with default prompts (Admin only).
    """
    service = get_prompt_generator_service(db)
    counts = await service.seed_default_prompts()

    return {
        "success": True,
        "seeded_counts": counts,
    }


# === Demo User Endpoints (Non-Subscribed) ===

class DemoUserRequest(BaseModel):
    """Request model for demo user operations."""
    group: str
    template_id: Optional[str] = None
    session_id: Optional[str] = None


class DemoResultResponse(BaseModel):
    """Response for demo users - watermarked results only."""
    template_id: str
    prompt: str
    prompt_zh: Optional[str] = None
    group: str
    sub_topic: str
    input_image_url: Optional[str] = None
    result_watermarked_url: Optional[str] = None  # Only watermarked for demo
    result_thumbnail_url: Optional[str] = None
    can_download: bool = False  # Always False for demo users
    message: str = "Subscribe to download original quality results"


@router.post("/demo/use-template", response_model=DemoResultResponse)
async def use_template_demo(
    request: DemoUserRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Use a default template for demo/non-subscribed users.

    RESTRICTIONS:
    - MUST specify template_id - results are BOUND to specific templates (NO random selection)
    - Can only use default templates with cached results
    - Returns watermarked results only
    - Cannot download original quality
    - Does not call external APIs (saves costs)
    """
    try:
        prompt_group = PromptGroup(request.group)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid group: {request.group}")

    service = get_prompt_generator_service(db)

    # IMPORTANT: template_id is REQUIRED - results are bound to specific templates
    if not request.template_id:
        raise HTTPException(
            status_code=400,
            detail="template_id is required. Results are bound to specific templates, not randomly selected."
        )

    # Get the specific template by ID - result is BOUND to this template
    template = await service.get_template_by_id(request.template_id)

    if not template:
        raise HTTPException(
            status_code=404,
            detail="Template not found."
        )

    # Verify template is available for demo users
    if not template.is_default or not template.is_active:
        raise HTTPException(
            status_code=403,
            detail="This template is not available for demo users. Please subscribe."
        )

    # Verify template has cached result - MUST have pre-generated result
    if not template.is_cached:
        raise HTTPException(
            status_code=503,
            detail="This template result is not ready yet. Please try again later."
        )

    # Verify template belongs to the requested group
    if template.group != prompt_group:
        raise HTTPException(
            status_code=400,
            detail=f"Template does not belong to group: {request.group}"
        )

    # Record usage with specific template binding
    await service.record_usage(
        template_id=str(template.id),
        session_id=request.session_id,
        source_page="demo",
        user_tier="free",
        used_cached=True,
    )

    # Return the BOUND result for this specific template
    return DemoResultResponse(
        template_id=str(template.id),
        prompt=template.prompt,
        prompt_zh=template.prompt_zh,
        group=template.group.value,
        sub_topic=template.sub_topic.value,
        input_image_url=template.input_image_url,
        result_watermarked_url=template.result_watermarked_url,
        result_thumbnail_url=template.result_thumbnail_url,
        can_download=False,
        message="Subscribe to download original quality results and use custom prompts",
    )


@router.get("/demo/download/{template_id}")
async def download_demo_result(
    template_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Attempt to download result - blocked for demo users.

    Demo users cannot download original quality results.
    They can only view watermarked versions.
    """
    raise HTTPException(
        status_code=403,
        detail={
            "error": "download_blocked",
            "message": "Download is not available for demo users. Please subscribe to download original quality results.",
            "action": "subscribe",
            "redirect": "/pricing",
        }
    )


# === Subscribed User Endpoints ===

class SubscribedUserRequest(BaseModel):
    """Request for subscribed users."""
    group: str
    prompt: str
    sub_topic: Optional[str] = None
    use_custom: bool = True
    input_data: Optional[dict] = None


class SubscribedResultResponse(BaseModel):
    """Response for subscribed users - full quality results."""
    template_id: Optional[str] = None
    prompt: str
    group: str
    sub_topic: str
    input_image_url: Optional[str] = None
    result_image_url: Optional[str] = None  # Original quality
    result_video_url: Optional[str] = None  # Original quality
    result_thumbnail_url: Optional[str] = None
    can_download: bool = True  # Always True for subscribed users
    download_url: Optional[str] = None
    credits_used: int = 0


@router.post("/subscribed/generate", response_model=SubscribedResultResponse)
async def generate_for_subscribed(
    request: SubscribedUserRequest,
    db: AsyncSession = Depends(get_db),
    # current_user = Depends(get_subscribed_user),  # Add subscription check
):
    """
    Generate result for subscribed users.

    PRIVILEGES:
    - Can use custom prompts
    - Can download original quality
    - Calls external APIs for generation
    - Credits will be deducted
    """
    try:
        prompt_group = PromptGroup(request.group)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid group: {request.group}")

    sub_topic = PromptSubTopic.DEFAULT
    if request.sub_topic:
        try:
            sub_topic = PromptSubTopic(request.sub_topic)
        except ValueError:
            pass

    service = get_prompt_generator_service(db)

    # Check for cached result first
    cached = await service.get_cached_result(
        group=prompt_group,
        prompt=request.prompt,
        sub_topic=sub_topic,
    )

    if cached:
        # Return cached result
        return SubscribedResultResponse(
            template_id=cached.get("template_id"),
            prompt=request.prompt,
            group=request.group,
            sub_topic=sub_topic.value,
            input_image_url=cached.get("input_image_url"),
            result_image_url=cached.get("result_image_url"),
            result_video_url=cached.get("result_video_url"),
            result_thumbnail_url=cached.get("result_thumbnail_url"),
            can_download=True,
            download_url=cached.get("result_image_url") or cached.get("result_video_url"),
            credits_used=0,  # No credits for cached
        )

    # For custom prompts, need to call API (implement generation logic)
    # This would integrate with the generation service
    return SubscribedResultResponse(
        prompt=request.prompt,
        group=request.group,
        sub_topic=sub_topic.value,
        can_download=True,
        credits_used=1,  # Default credit cost
    )


@router.get("/subscribed/download/{template_id}")
async def download_subscribed_result(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    # current_user = Depends(get_subscribed_user),  # Add subscription check
):
    """
    Download original quality result for subscribed users.

    Subscribed users can download original quality without watermark.
    """
    service = get_prompt_generator_service(db)
    template = await service.get_template_by_id(template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Get the original quality URL
    download_url = template.result_image_url or template.result_video_url

    if not download_url:
        raise HTTPException(status_code=404, detail="No result available for download")

    return {
        "download_url": download_url,
        "filename": f"vidgo_{template_id[:8]}.{'mp4' if template.result_video_url else 'png'}",
        "can_download": True,
    }


# === Access Check Endpoint ===

@router.get("/check-access")
async def check_user_access(
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Check user access level and available features.

    Returns what the user can and cannot do based on subscription status.
    """
    # This would integrate with the subscription service
    # For now, return demo access by default
    is_subscribed = False  # Would check from subscription service

    if is_subscribed:
        return {
            "access_level": "subscribed",
            "can_use_custom_prompts": True,
            "can_download_original": True,
            "can_call_api": True,
            "watermark_results": False,
            "message": "Full access - enjoy all features!",
        }
    else:
        return {
            "access_level": "demo",
            "can_use_custom_prompts": False,
            "can_download_original": False,
            "can_call_api": False,
            "watermark_results": True,
            "message": "Demo access - subscribe for full features",
            "upgrade_url": "/pricing",
        }
