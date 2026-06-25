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
- PiAPI style transformation demos
"""
from typing import Optional, List, Dict, Any
import logging
import uuid
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Query, BackgroundTasks, UploadFile, File
import shutil
import os
from pathlib import Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.api.deps import get_db, get_current_user_optional, is_subscribed_user
from app.models.demo import ImageDemo, DemoCategory, DemoVideo, DemoExample, PromptCache, ToolShowcase
from app.services.demo_service import get_demo_service, DEMO_TOPICS, DEMO_STYLES
from app.services.prompt_matching import get_prompt_matching_service
from app.services.moderation import get_moderation_service
from app.services.block_cache import get_block_cache
from app.services.gemini_service import get_gemini_service
from app.services.gcs_storage_service import get_gcs_storage
from app.services.similarity import get_similarity_service
from app.services.rescue_service import get_rescue_service
from app.core.config import get_settings
from app.core.upload_validation import (
    COMMON_IMAGE_DIMENSION_RULES,
    extension_for_content_type,
    validate_uploaded_content,
)

settings = get_settings()
logger = logging.getLogger(__name__)
SHORT_VIDEO_LENGTH = int(getattr(settings, "SHORT_VIDEO_LENGTH", 8))


def _runtime_demo_generation_disabled() -> None:
    """Raise a clean 410 for the retired legacy runtime example-generation
    endpoints (generate-paid, search-or-generate, generate-image,
    generate-realtime). On-demand demo generation was replaced by
    developer-managed pre-generated presets. These endpoints stay mounted for
    backwards compatibility but must return a clear "gone" — previously this
    helper was REFERENCED but never DEFINED, so each call raised NameError → 500.
    """
    raise HTTPException(
        status_code=410,
        detail={
            "error": "runtime_demo_generation_disabled",
            "message": (
                "Runtime demo generation is disabled. Use /api/v1/demo/presets "
                "for pre-generated examples, or the tool endpoints under "
                "/api/v1/tools to generate your own."
            ),
        },
    )
from app.services.material import MaterialLibraryService, UserContentCollector, MATERIAL_REQUIREMENTS
from app.config.topic_registry import (
    get_topics_for_tool,
    get_topic_ids_for_tool,
    is_valid_topic,
    get_all_tool_types,
    get_landing_topics,
    TOOL_TOPICS,
)

router = APIRouter()


def _public_material_filters(Material):
    return [
        or_(Material.input_params["readiness_seed"].astext.is_(None), Material.input_params["readiness_seed"].astext != "true"),
        or_(Material.input_params["reused_generated_media"].astext.is_(None), Material.input_params["reused_generated_media"].astext != "true"),
        or_(
            Material.prompt.is_(None),
            and_(
                ~Material.prompt.ilike("VidGo readiness%"),
                ~Material.prompt.ilike("VidGo landing%"),
            ),
        ),
        or_(
            Material.prompt_zh.is_(None),
            and_(
                ~Material.prompt_zh.ilike("VidGo readiness%"),
                ~Material.prompt_zh.ilike("VidGo landing%"),
            ),
        ),
    ]


def _landing_work_copy(material, tool_type: str, language: str, fallback_name: str):
    is_zh = language.startswith("zh")
    params = material.input_params or {}

    def _clean_label(value: str | None) -> str:
        return (value or "").replace("_", " ").replace("-", " ").strip()

    if tool_type == "product_scene":
        product = params.get("product_name_zh" if is_zh else "product_name")
        scene = params.get("scene_name_zh" if is_zh else "scene_name")
        if product and scene:
            if is_zh:
                return (
                    f"{product} × {scene}",
                    f"以{scene}打造{product}的商業情境圖，適合電商主圖、活動頁與社群廣告。",
                )
            return (
                f"{product} x {scene}",
                f"A polished {scene} campaign scene for {product}, ready for e-commerce listings, landing pages, and social ads.",
            )

        raw_prompt = (material.prompt_zh if is_zh else material.prompt_en) or material.prompt or ""
        product_candidate = raw_prompt.split(" | ", 1)[0] if " | " in raw_prompt else ""
        generic_titles = {"", "商品場景", "Product Scene", "product scene"}
        title_candidate = (material.title_zh if is_zh else material.title_en) or ""
        product_label = _clean_label(product_candidate or ("" if title_candidate in generic_titles else title_candidate))
        scene_labels = {
            "nature": ("自然生活風格", "natural lifestyle"),
            "lifestyle": ("日常生活情境", "lifestyle"),
            "luxury": ("精品質感棚拍", "premium studio"),
            "studio": ("商業棚拍", "commercial studio"),
            "holiday": ("節慶活動", "holiday campaign"),
            "black_friday": ("黑色星期五", "Black Friday"),
            "valentines": ("情人節", "Valentine's Day"),
            "christmas": ("聖誕節", "Christmas"),
            "new_year": ("農曆新年", "Lunar New Year"),
            "spring_sale": ("春季特賣", "spring sale"),
        }
        zh_scene, en_scene = scene_labels.get(material.topic or "", ("品牌情境", "brand campaign"))
        if is_zh:
            product_label = product_label or "商品"
            return (
                f"{product_label} × {zh_scene}",
                f"以{zh_scene}呈現{product_label}的商業情境圖，適合商品頁、活動頁、廣告素材與社群貼文。",
            )
        product_label = product_label or "product"
        return (
            f"{product_label} x {en_scene}",
            f"A polished {en_scene} scene for {product_label}, ready for product pages, campaign creatives, ads, and social posts.",
        )

    if tool_type == "ai_avatar":
        topic_labels = {
            "spokesperson": ("Brand Story Presenter", "品牌故事數位人"),
            "product_intro": ("Product Demo Presenter", "產品開箱數位人"),
            "customer_service": ("Customer Service Presenter", "客服說明數位人"),
            "social_media": ("Social Commerce Presenter", "社群導購數位人"),
        }
        en_label, zh_label = topic_labels.get(material.topic or "", ("AI Avatar Presenter", "AI 數位人導購"))
        title = zh_label if is_zh else en_label
        prompt = (material.prompt_zh if is_zh else material.prompt_en) or material.prompt or ""
        if prompt:
            return title, prompt[:120] + "..." if len(prompt) > 120 else prompt

    if tool_type == "room_redesign":
        room_type = params.get("room_type") or (material.topic if material.topic in {
            "living_room", "bedroom", "kitchen", "bathroom", "dining_room", "home_office", "balcony"
        } else None)
        style_id = params.get("style_id") or (material.topic if material.topic in {
            "modern_minimalist", "scandinavian", "japanese", "industrial", "mediterranean", "mid_century_modern", "bohemian", "coastal", "farmhouse", "art_deco"
        } else None)

        room_labels = {
            "living_room": ("Living Room", "客廳"),
            "bedroom": ("Bedroom", "臥室"),
            "kitchen": ("Kitchen", "廚房"),
            "bathroom": ("Bathroom", "浴室"),
            "dining_room": ("Dining Room", "餐廳"),
            "home_office": ("Home Office", "書房"),
            "balcony": ("Balcony", "陽台"),
        }
        style_labels = {
            "modern_minimalist": ("Modern Minimalist", "現代極簡"),
            "scandinavian": ("Scandinavian", "北歐風格"),
            "japanese": ("Japanese Zen", "日式禪風"),
            "industrial": ("Industrial", "工業風"),
            "mediterranean": ("Mediterranean", "地中海風格"),
            "mid_century_modern": ("Mid-Century Modern", "中世紀現代"),
            "bohemian": ("Bohemian", "波西米亞"),
            "coastal": ("Coastal", "海岸風格"),
            "farmhouse": ("Farmhouse", "農舍風格"),
            "art_deco": ("Art Deco", "裝飾藝術"),
        }
        en_room, zh_room = room_labels.get(room_type or "", ("Interior Space", "室內空間"))
        en_style, zh_style = style_labels.get(style_id or "", ("Proposal Render", "提案渲染"))
        if is_zh:
            return (
                f"{zh_room} × {zh_style}提案",
                f"將{zh_room}現況照轉成{zh_style}方向的寫實室內渲染，保留主要格局、採光與空間比例，適合設計提案、房仲刊登與家具情境圖。",
            )
        return (
            f"{en_room} x {en_style} Proposal",
            f"A photorealistic {en_style} redesign for a {en_room.lower()}, preserving the core layout, daylight, and spatial proportion for proposals, listings, and furniture scenes.",
        )

    if tool_type == "effect":
        raw_text = " ".join(
            str(value or "")
            for value in (
                params.get("style_id"),
                params.get("style"),
                params.get("effect_id"),
                material.effect_prompt,
                material.effect_prompt_zh,
                material.prompt,
                material.prompt_en,
                material.prompt_zh,
                material.topic,
            )
        ).lower()
        effect_labels = {
            "upscale_2x": (
                "HD Image Enhancement",
                "高解析圖片增強",
                "An HD-enhanced source image with cleaner detail, sharper edges, and production-ready clarity.",
                "提升原始圖片的清晰度、細節與銳利度，適合商品頁、廣告素材與社群內容。",
            ),
            "realistic": (
                "Realistic Photo Polish",
                "寫實照片優化",
                "A realistic photo refinement with cleaner lighting, richer texture, and commercial-grade detail.",
                "以寫實質感優化光線、紋理與細節，讓圖片更適合商業展示。",
            ),
            "cinematic": (
                "Cinematic Image Effect",
                "電影質感圖片特效",
                "A cinematic visual treatment with refined color, dramatic contrast, and campaign-ready mood.",
                "以電影感色調與對比強化畫面氛圍，適合活動頁與廣告素材。",
            ),
            "anime": (
                "Anime Style Conversion",
                "動漫風格轉換",
                "An anime-style transformation that keeps the subject recognizable while adding bold illustrated character.",
                "將原圖轉換為動漫風格，同時保留主體辨識度與畫面重點。",
            ),
        }
        for marker, (en_title, zh_title, en_prompt, zh_prompt) in effect_labels.items():
            if marker in raw_text:
                return (zh_title, zh_prompt) if is_zh else (en_title, en_prompt)
        return (
            ("圖片風格優化", "以專業圖片特效提升原圖質感，適合商品頁、活動頁與社群素材。")
            if is_zh else
            ("Professional Image Effect", "A polished image effect that turns the source visual into a cleaner, campaign-ready creative asset.")
        )

    title = (material.title_zh if is_zh else material.title_en) or fallback_name
    prompt = (material.prompt_zh if is_zh else material.prompt_en) or material.prompt or ""
    return title, prompt[:120] + "..." if len(prompt) > 120 else prompt


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
    style: Optional[str] = Field(None, description="Style slug (no longer applied — V2V removed 2026-05-31).")
    # skip_v2v field removed 2026-05-31 — V2V is gone repo-wide; we always skip.


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
    id: str  # style key e.g. anime, realistic
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
    """Response from using a preset.
    Subscribers receive the full-quality URL; free users receive the watermarked URL."""
    success: bool
    preset_id: str
    result_url: Optional[str] = None              # Full-quality result (subscribers only)
    result_watermarked_url: Optional[str] = None   # Watermarked result (free users / fallback)
    result_thumbnail_url: Optional[str] = None
    input_image_url: Optional[str] = None          # For before/after display (Effect, Try-on, etc.)
    prompt: Optional[str] = None
    prompt_zh: Optional[str] = None
    can_download: bool = False                      # True for subscribers
    is_subscribed: bool = False
    message: str = "Subscribe for full access"
    error: Optional[str] = None


@router.post("/use-preset", response_model=PresetResultResponse)
async def use_preset(
    request: UsePresetRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """
    Use a preset template - Material DB lookup only.

    - Free/anonymous users receive watermarked results; downloads blocked.
    - Subscribers receive full-quality results and may download.
    - NO external API calls in either case.
    """
    from app.services.material_lookup import get_material_lookup_service

    lookup_service = get_material_lookup_service(db)
    subscribed = is_subscribed_user(current_user)

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

    # Permanent public URLs (no signing, no TTL). These preset rows are the
    # SHARED demo cache every visitor loads — the objects are uploaded public
    # (make_public), so their bare URL works forever and is CDN/browser-
    # cacheable. Re-signing them on every click was pure overhead (~200ms) and
    # bought no access control (the blob path is in the signed URL anyway).
    from app.services.gcs_storage_service import get_gcs_storage
    gcs = get_gcs_storage()

    full_result_url = gcs.public_url(material.result_video_url or material.result_image_url)
    watermarked_url = gcs.public_url(material.result_watermarked_url) or full_result_url

    if subscribed:
        return PresetResultResponse(
            success=True,
            preset_id=request.preset_id,
            result_url=full_result_url,
            result_watermarked_url=watermarked_url,
            result_thumbnail_url=gcs.public_url(getattr(material, "result_thumbnail_url", None)),
            input_image_url=gcs.public_url(material.input_image_url),
            prompt=material.prompt,
            prompt_zh=material.prompt_zh,
            can_download=True,
            is_subscribed=True,
            message="Full access",
        )

    return PresetResultResponse(
        success=True,
        preset_id=request.preset_id,
        result_url=None,
        result_watermarked_url=watermarked_url,
        result_thumbnail_url=gcs.public_url(getattr(material, "result_thumbnail_url", None)),
        input_image_url=gcs.public_url(material.input_image_url),
        prompt=material.prompt,
        prompt_zh=material.prompt_zh,
        can_download=False,
        is_subscribed=False,
        message="Subscribe for full access",
    )


@router.get("/download/{material_id}")
async def download_preset_result(
    material_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """
    Download the full-quality result for a preset (subscribers only).
    Returns a redirect to the result URL.
    """
    from fastapi.responses import RedirectResponse
    from app.services.material_lookup import get_material_lookup_service

    if not is_subscribed_user(current_user):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "download_blocked",
                "message": "A subscription is required to download results.",
            }
        )

    lookup_service = get_material_lookup_service(db)
    material = await lookup_service.lookup_by_id(material_id)

    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    download_url = material.result_video_url or material.result_image_url
    if not download_url:
        raise HTTPException(status_code=404, detail="No result available for download")

    from app.services.gcs_storage_service import get_gcs_storage
    # Subscriber gate already enforced above; the object is public, so a
    # permanent public URL (no signing/TTL) is the right redirect target.
    download_url = get_gcs_storage().public_url(download_url) or download_url

    return RedirectResponse(url=download_url)


# =============================================================================
# TOPIC REGISTRY ENDPOINTS
# =============================================================================

@router.get("/topics")
async def get_all_topics():
    """
    Get all available topics grouped by tool type.
    
    Returns the complete topic registry for frontend initialization.
    """
    return {
        "success": True,
        "tool_types": get_all_tool_types(),
        "topics": TOOL_TOPICS,
        "landing_topics": get_landing_topics()
    }


@router.get("/topics/{tool_type}")
async def get_tool_topics(tool_type: str):
    """
    Get valid topics for a specific tool type.
    
    IMPORTANT: Use this API to get the correct topic list.
    Do NOT hardcode topic values in frontend.
    
    Args:
        tool_type: Tool type (e.g., 'ai_avatar', 'background_removal')
        
    Returns:
        List of valid topics with id, name_en, name_zh
    """
    topics = get_topics_for_tool(tool_type)
    
    if not topics:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "invalid_tool_type",
                "message": f"Unknown tool type: {tool_type}",
                "valid_tool_types": get_all_tool_types()
            }
        )
    
    return {
        "success": True,
        "tool_type": tool_type,
        "topics": topics,
        "count": len(topics)
    }


@router.get("/inputs/{tool_type}")
async def get_input_library(
    tool_type: str,
    topic: Optional[str] = Query(None, description="Topic filter"),
    limit: int = Query(48, ge=1, le=200, description="Maximum number of inputs"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the pregenerated INPUT library for a tool.

    These are the assets the visitor picks from as their "input" — images
    from Vertex Imagen (T2I) or videos from Vertex Veo (T2V), all uploaded
    to GCS. Rows are written by scripts/pregenerate_inputs.py and tagged
    with `input_params.is_input_library = true` and have NULL result URLs.

    The runtime path then combines the picked input with a user-chosen
    effect_prompt and either serves a cached result or calls the real
    provider API on miss (see DemoCacheService.get_or_generate).
    """
    from app.models.material import Material, MaterialStatus

    # Tools without a curated input library (paid-only operations or aliases)
    # return an empty list so old SPA bundles don't 404.
    _NO_INPUT_LIBRARY = {
        "upscale", "image_upscale", "video_upscale",
        "image_translate", "image_translation", "video_dubbing",
    }
    if tool_type in _NO_INPUT_LIBRARY:
        return {"success": True, "tool_type": tool_type, "topic": topic, "inputs": [], "count": 0}

    valid_tool_types = get_all_tool_types()
    if tool_type not in valid_tool_types:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "invalid_tool_type",
                "message": f"Unknown tool type: {tool_type}",
                "valid_tool_types": valid_tool_types,
            },
        )

    query = select(Material).where(
        Material.tool_type == tool_type,
        Material.is_active == True,
        Material.status.in_([MaterialStatus.APPROVED, MaterialStatus.FEATURED]),
        Material.input_params["is_input_library"].astext == "true",
    )
    if topic:
        query = query.where(Material.topic == topic)
    query = query.order_by(Material.created_at.desc()).limit(limit)

    result = await db.execute(query)
    rows = result.scalars().all()

    return {
        "success": True,
        "tool_type": tool_type,
        "topic": topic,
        "inputs": [
            {
                "id": str(r.id),
                "topic": r.topic,
                "prompt": r.prompt,
                "input_image_url": r.input_image_url,
                "input_video_url": r.input_video_url,
                "input_params": r.input_params or {},
            }
            for r in rows
        ],
        "count": len(rows),
    }


# Demo model dropdown — lets free/visitor users "try" a PREMIUM model without
# a prompt: they pick a cached example generated by that model. The premium
# examples are pregenerated into the Material cache tagged with
# input_params.model_id, then served watermarked (subscribe to remove). Tools
# not listed here only expose the free "default" model.
_DEMO_DEFAULT_MODEL = {"id": "default", "name": "Standard", "name_zh": "標準", "premium": False}
_DEMO_PREMIUM_VIDEO = [
    {"id": "kling_v3", "name": "Kling 3.0", "name_zh": "Kling 3.0", "premium": True},
    {"id": "sora2", "name": "Sora 2", "name_zh": "Sora 2", "premium": True},
    {"id": "veo", "name": "Veo 3.1", "name_zh": "Veo 3.1", "premium": True},
]
_DEMO_MODEL_CATALOG: Dict[str, List[Dict[str, Any]]] = {
    "short_video": [_DEMO_DEFAULT_MODEL, *_DEMO_PREMIUM_VIDEO],
    "image_transform": [_DEMO_DEFAULT_MODEL, *_DEMO_PREMIUM_VIDEO],
    "video_transform": [_DEMO_DEFAULT_MODEL, *_DEMO_PREMIUM_VIDEO],
    "ai_avatar": [_DEMO_DEFAULT_MODEL,
                  {"id": "kling_v3", "name": "Kling 3.0", "name_zh": "Kling 3.0", "premium": True}],
}


@router.get("/models/{tool_type}")
async def get_demo_model_catalog(tool_type: str):
    """Models the free-tier demo dropdown offers for a tool.

    Each entry: { id, name, name_zh, premium }. `premium: true` items are the
    "try a premium model for free" options (Kling 3.0 / Sora 2 / Veo) — the
    frontend marks them and shows a subscribe CTA on the watermarked result.
    """
    valid_tool_types = get_all_tool_types()
    if tool_type not in valid_tool_types:
        raise HTTPException(status_code=404, detail={"error": "invalid_tool_type"})
    return {
        "tool_type": tool_type,
        "models": _DEMO_MODEL_CATALOG.get(tool_type, [_DEMO_DEFAULT_MODEL]),
    }


@router.get("/effects/{tool_type}")
async def get_effect_catalog(
    tool_type: str,
    language: str = Query("en", description="Language code (en, zh-TW)"),
):
    """
    Return the per-tool effect-prompt catalog the user chooses from.

    Pairs with /inputs/{tool_type} to form the two halves of every demo
    request: (picked input) × (picked effect). Sent through to the
    runtime cache-through endpoint, which keys on that exact pair.

    Each entry: { id, name, name_zh, prompt } — the `prompt` is what
    ultimately flows into `effect_prompt` on the tool request.
    """
    valid_tool_types = get_all_tool_types()
    if tool_type not in valid_tool_types:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "invalid_tool_type",
                "valid_tool_types": valid_tool_types,
            },
        )

    effects: List[Dict[str, Any]] = []

    if tool_type == "effect":
        from app.services.effects_service import VIDGO_STYLES, get_style_prompt
        for s in VIDGO_STYLES:
            effects.append({
                "id": s["id"],
                "name": s["name"],
                "name_zh": s.get("name_zh"),
                "prompt": get_style_prompt(s["id"]),
                "category": s.get("category"),
            })

    elif tool_type == "product_scene":
        from app.api.v1.tools import SCENE_TEMPLATES
        for s in SCENE_TEMPLATES:
            effects.append({
                "id": s["id"],
                "name": s["name"],
                "name_zh": s.get("name_zh"),
                "prompt": s["prompt"],
            })

    elif tool_type == "room_redesign":
        from app.api.v1.tools import INTERIOR_STYLES
        for s in INTERIOR_STYLES:
            effects.append({
                "id": s["id"],
                "name": s["name"],
                "name_zh": s.get("name_zh"),
                "prompt": s["prompt"],
            })

    elif tool_type == "short_video":
        # Motion prompts — user picks the camera/motion flavor; the cache
        # key differentiates between them so they don't collide.
        motions = [
            ("subtle", "Subtle Motion", "細微動態",
             "subtle cinematic motion, barely-perceptible parallax drift, steady locked exposure"),
            ("gentle", "Gentle Motion", "輕柔動態",
             "gentle cinematic orbit, smooth stabilized camera, elegant slow-motion feel"),
            ("dynamic", "Dynamic Motion", "動感動態",
             "confident cinematic tracking shot, moderate parallax, dynamic lighting transition"),
            ("dramatic", "Dramatic Motion", "戲劇動態",
             "dramatic cinematic push-in with rack focus, bold sweeping camera arc, high-energy commercial feel"),
        ]
        for mid, en, zh, prompt in motions:
            effects.append({"id": mid, "name": en, "name_zh": zh, "prompt": prompt})

    elif tool_type == "try_on":
        # For try-on the "effect" is which garment category to render.
        # Garment url comes from the input library (input_params.garment_id).
        for topic in get_topics_for_tool(tool_type):
            effects.append({
                "id": topic["id"],
                "name": topic.get("name_en", topic["id"]),
                "name_zh": topic.get("name_zh"),
                "prompt": topic["id"],  # topic doubles as the cache key for try-on
            })

    elif tool_type == "ai_avatar":
        # Scripts per category; language-aware default is chosen by the
        # runtime when the user doesn't write a custom line.
        base_scripts = {
            "spokesperson": {
                "zh-TW": "歡迎認識我們的品牌故事，我們用心做好每一件產品。",
                "en":    "Welcome to our brand story. Every product is made with care.",
            },
            "product_intro": {
                "zh-TW": "讓我介紹這款產品，品質優良、價格實惠，限時特惠中。",
                "en":    "Let me introduce this product. Great quality, great price, on sale now.",
            },
            "customer_service": {
                "zh-TW": "有任何問題都可以聯絡我們，我們會在兩小時內回覆您。",
                "en":    "Contact us anytime with questions. We reply within two hours.",
            },
            "social_media": {
                "zh-TW": "記得按讚訂閱追蹤，更多精彩內容即將推出，不要錯過！",
                "en":    "Like, subscribe, and follow for more. You do not want to miss this!",
            },
        }
        lang_key = "zh-TW" if language.startswith("zh") else "en"
        for topic_id, by_lang in base_scripts.items():
            effects.append({
                "id": topic_id,
                "name": topic_id.replace("_", " ").title(),
                "name_zh": topic_id,
                "prompt": by_lang[lang_key],
            })

    elif tool_type == "pattern_generate":
        # Pattern tool is T2I-only — each "topic" IS the effect prompt.
        seeds = {
            "seamless": "elegant floral pattern for packaging, rose and navy, seamless tile",
            "floral": "cherry blossom pattern for cafe branding, soft pink and white",
            "geometric": "modern geometric pattern, triangles black and gold, professional",
            "abstract": "marble texture pattern for cosmetics packaging, gold veins",
            "traditional": "Chinese cloud pattern, red and gold, auspicious design",
        }
        for topic in get_topics_for_tool(tool_type):
            prompt = seeds.get(topic["id"], topic.get("name_en", topic["id"]))
            effects.append({
                "id": topic["id"],
                "name": topic.get("name_en", topic["id"]),
                "name_zh": topic.get("name_zh"),
                "prompt": prompt,
            })

    elif tool_type == "background_removal":
        # Background removal has no user-facing effect choice — the output
        # format is a single canonical operation. Return one entry so the
        # frontend still gets a stable shape.
        effects.append({
            "id": "transparent_png",
            "name": "Remove Background",
            "name_zh": "去除背景",
            "prompt": None,
        })

    return {
        "success": True,
        "tool_type": tool_type,
        "effects": effects,
        "count": len(effects),
    }


@router.get("/presets/{tool_type}")
async def get_presets(
    tool_type: str,
    topic: Optional[str] = Query(None, description="Topic filter"),
    product_id: Optional[str] = Query(None, description="Product ID filter (input_params.product_id)"),
    platform: Optional[str] = Query(None, max_length=40, description="Filter by Material.platform tag (e.g. 'instagram', 'tiktok', 'shopify')"),
    role: Optional[str] = Query(None, max_length=40, description="Filter by Material.role tag (e.g. 'creator', 'seller', 'designer')"),
    limit: int = Query(100, ge=1, le=200, description="Maximum number of presets"),
    language: str = Query("en", description="Language for try_prompts when db_empty"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get available presets for a tool.

    Returns list of preset templates with thumbnails.
    Users can only select from these presets - no custom input allowed.
    
    Topic validation: If topic is provided, it must be a valid topic from Topic Registry.
    """
    from app.services.material_lookup import get_material_lookup_service

    # Normalize legacy / stale-client tool_type aliases so old SPA bundles
    # cached in browsers do not 404 against the new ToolType enum names.
    # Logged as a deprecation warning so we can track which clients still
    # send the old names.
    _LEGACY_TOOL_TYPE_ALIASES = {
        "avatar": "ai_avatar",
        "digital_human": "ai_avatar",
    }
    # Tool types that exist as features but have no Material presets in the
    # DB. Return an empty preset list so the client renders gracefully.
    #
    # 2026-05-26: removed upscale + image_translate/image_translation from
    # this list — those tools now have seeded demo presets, so they should
    # query the DB like any other tool. video_upscale + video_dubbing remain
    # blocked because we have not seeded examples for them yet (video gen
    # cost too high for demo gallery).
    _NO_PRESET_TOOL_TYPES = {
        "video_upscale",
        "video_dubbing",
    }

    if tool_type in _LEGACY_TOOL_TYPE_ALIASES:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "demo.presets: legacy tool_type alias '%s' -> '%s' (update client)",
            tool_type, _LEGACY_TOOL_TYPE_ALIASES[tool_type],
        )
        tool_type = _LEGACY_TOOL_TYPE_ALIASES[tool_type]

    if tool_type in _NO_PRESET_TOOL_TYPES:
        return {
            "success": True,
            "presets": [],
            "count": 0,
            "db_empty": True,
            "try_prompts": [],
            "message": f"Tool '{tool_type}' has no demo presets.",
        }

    # Validate tool_type
    valid_tool_types = get_all_tool_types()
    if tool_type not in valid_tool_types:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "invalid_tool_type",
                "message": f"Unknown tool type: {tool_type}",
                "valid_tool_types": valid_tool_types
            }
        )
    
    # Validate topic if provided
    if topic and not is_valid_topic(tool_type, topic):
        valid_topics = get_topic_ids_for_tool(tool_type)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_topic",
                "message": f"Invalid topic '{topic}' for tool '{tool_type}'",
                "valid_topics": valid_topics
            }
        )

    lookup_service = get_material_lookup_service(db)
    # Over-fetch: the GCS-existence post-filter below can drop rows whose
    # signed-URL blobs were rotated/expired since the last cache refresh.
    # If we asked the DB for exactly `limit` rows, and all of them happen to
    # be stale, the endpoint returns 0 even though more matching rows exist.
    # Pull a generous superset so the post-filter has material to work with.
    fetch_limit = max(limit * 5, 50)
    presets = await lookup_service.get_presets_for_tool(tool_type, topic, fetch_limit, product_id=product_id, platform=platform, role=role)

    from app.services.gcs_storage_service import get_gcs_storage
    gcs = get_gcs_storage()

    # Drop Material rows whose primary result blob no longer exists in GCS.
    # Stale rows (deleted by lifecycle, failed pregenerate uploads, etc.) sign
    # successfully but the URL 404s on the browser, which makes the LandingPage
    # hero fall back to placeholder images. We use a 5-minute cached blob
    # listing so hot read paths stay fast.
    if gcs.enabled and presets:
        # Combine blob listings for the four prefixes our outputs land under:
        #   • generated/      — pregen / runtime AI outputs (most pregen rows)
        #   • examples/       — curated bg/fx/ps/room/avatar pairs that the
        #                       reseed_background_removal_inputs script remaps
        #                       bg_removal rows onto.
        #   • users/          — runtime tool outputs are stored per-user under
        #                       users/<user_id>/<tool>/<file>. Without this
        #                       prefix every short_video / ai_avatar /
        #                       live-generated seed row gets dropped.
        #   • static/         — admin-curated demo pairs (e.g. room_redesign
        #                       Scandinavian / Industrial / Japandi rendered
        #                       from static/examples/_inputs/room-empty.jpg).
        #                       Without this prefix the curated seeds were
        #                       silently filtered out (audit 2026-05-26).
        # 900s + stale-while-revalidate (see list_blob_names_cached): only the
        # first gallery load per instance pays the GCS LIST cost; later loads
        # return instantly and refresh in the background.
        existing_gen = gcs.list_blob_names_cached("generated/", ttl_seconds=900)
        existing_examples = gcs.list_blob_names_cached("examples/", ttl_seconds=900)
        existing_users = gcs.list_blob_names_cached("users/", ttl_seconds=900)
        existing_static = gcs.list_blob_names_cached("static/", ttl_seconds=900)
        existing = (
            (existing_gen or set())
            | (existing_examples or set())
            | (existing_users or set())
            | (existing_static or set())
        )
        if existing:
            def _row_has_live_blob(p) -> bool:
                # A row is keepable if at least one of its result URLs either
                # points outside our bucket (external CDN) or references a
                # blob we just listed.
                for url_attr in ("result_image_url", "result_watermarked_url", "result_video_url"):
                    u = getattr(p, url_attr, None)
                    if not u:
                        continue
                    blob_name = gcs.extract_blob_name(u, gcs.bucket_name)
                    if blob_name is None:
                        # External URL — assume reachable.
                        return True
                    if blob_name in existing:
                        return True
                return False
            before = len(presets)
            presets = [p for p in presets if _row_has_live_blob(p)]
            dropped = before - len(presets)
            if dropped:
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "[presets/%s] Dropped %d/%d Material rows with missing GCS blobs (topic=%s).",
                    tool_type, dropped, before, topic,
                )

    # Apply the user-requested limit AFTER GCS filtering so a stale-blob
    # streak in the first N DB rows can't starve the response.
    presets = presets[:limit]

    def _r(u):
        # Permanent public URL (no signing, no TTL) — these preset rows are the
        # shared demo cache every visitor loads; the objects are public.
        return gcs.public_url(u) if u else u

    def _safe_thumb(p):
        """Return a still-image thumbnail URL or None.

        Falling back to result_watermarked_url leaked .mp4 URLs into
        thumbnail_url for video tools (short_video, ai_avatar). The frontend
        uses thumbnail_url as an <img> src and as the I2V source, which
        triggered net::ERR_ABORTED on previews and HTTP 415
        invalid_upload errors when the user clicked "Generate".
        """
        candidates = [
            getattr(p, "result_thumbnail_url", None),
            getattr(p, "result_image_url", None),
            getattr(p, "input_image_url", None),
            getattr(p, "result_watermarked_url", None),
        ]
        for c in candidates:
            if not c:
                continue
            lower = str(c).split("?", 1)[0].lower()
            if lower.endswith((".mp4", ".webm", ".mov", ".m4v")):
                continue
            return c
        return None

    payload = {
        "success": True,
        "tool_type": tool_type,
        "topic": topic,
        "presets": [
            {
                "id": str(p.id),
                    "prompt": getattr(p, "prompt", ""),
                    "prompt_zh": getattr(p, "prompt_zh", None),
                    "prompt_en": getattr(p, "prompt_en", None) or getattr(p, "prompt", ""),
                    "title_zh": getattr(p, "title_zh", None),
                    "title_en": getattr(p, "title_en", None),
                    "input_image_url": _r(getattr(p, "input_image_url", None)),
                    "input_video_url": _r(getattr(p, "input_video_url", None)),
                    "result_image_url": _r(getattr(p, "result_image_url", None)),
                    "result_video_url": _r(getattr(p, "result_video_url", None)),
                    "result_watermarked_url": _r(getattr(p, "result_watermarked_url", None)),
                    "thumbnail_url": _r(_safe_thumb(p)),
                    "topic": getattr(p, "topic", None),
                    "input_params": getattr(p, "input_params", None) or {},
                    "style_tags": getattr(p, "tags", None) or []
            }
            for p in presets
        ],
        "count": len(presets)
    }

    # When no materials, include fixed try_prompts so frontend can show selectable options
    if len(presets) == 0:
        from app.config.try_prompts import get_try_prompts as _get_try_prompts
        payload["try_prompts"] = _get_try_prompts(tool_type, language)
        payload["db_empty"] = True
    else:
        payload["db_empty"] = False

    return payload


@router.get("/try-prompts/{tool_type}")
async def get_try_prompts(
    tool_type: str,
    language: str = Query("en", description="Language code (en, zh-TW, zh)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get fixed prompts for try-play mode.

    When Material DB is empty, frontend uses these prompts to show selectable options.
    When user selects a prompt, they query Material DB (via presets or use-preset).
    Run scripts/seed_materials_if_empty.py to populate DB with results for these prompts.

    Supported tools: all registered tool types
    """
    from app.config.try_prompts import get_try_prompts as get_prompts

    valid_tools = tuple(get_all_tool_types())
    if tool_type not in valid_tools:
        raise HTTPException(
            status_code=404,
            detail={"error": "invalid_tool_type", "valid_tools": list(valid_tools)}
        )

    prompts = get_prompts(tool_type, language)
    return {
        "success": True,
        "tool_type": tool_type,
        "prompts": prompts,
        "count": len(prompts),
        "message": "Run seed_materials_if_empty.py to populate Material DB with results."
    }


# =============================================================================
# NEW ENDPOINTS - Demo Tier with Leonardo AI
# =============================================================================

@router.get("/inspiration", response_model=InspirationResponse)
async def get_inspiration_examples(
    topic: Optional[str] = Query(None, description="Filter by topic"),
    count: int = Query(10, ge=1, le=50, description="Number of examples to return"),
    language: str = Query("en", description="Language code (en, zh-TW)"),
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
    else:
        # 2026-05-18 — historical seeded rows for room-redesign topics
        # (living_room / bedroom / kitchen / bathroom / dining_room /
        # home_office / balcony) have unreliable image_url ↔ caption
        # pairing (e.g. a bubble-tea image labeled "interior proposal").
        # The frontend ships vetted curated fallbacks for room_redesign,
        # so drop the broken DB rows here rather than render them.
        _UNRELIABLE_ROOM_TOPICS = (
            "living_room", "bedroom", "kitchen", "bathroom",
            "dining_room", "home_office", "balcony", "room_redesign",
        )
        query = query.where(~DemoExample.topic.in_(_UNRELIABLE_ROOM_TOPICS))

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
    is_zh = language.startswith("zh")

    def contains_cjk(value: Optional[str]) -> bool:
        return bool(value) and any("\u4e00" <= char <= "\u9fff" for char in value)

    example_list = []
    for ex in examples:
        topic_display = (
            ex.topic_zh if is_zh else ex.topic_en
        ) or ex.topic.replace("_", " ").title()
        raw_title = ex.title or ""
        title = (ex.title_zh if is_zh else ex.title_en) or (
            raw_title if contains_cjk(raw_title) == is_zh else topic_display
        )
        raw_prompt = ex.prompt or ""
        prompt = raw_prompt if contains_cjk(raw_prompt) == is_zh else title

        example_list.append(InspirationExample(
            id=str(ex.id),
            topic=ex.topic,
            topic_display=topic_display,
            prompt=prompt,
            image_url=ex.image_url,
            video_url=ex.video_url,
            thumbnail_url=ex.thumbnail_url,
            title=title,
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
    Demo generation endpoint — cache-first with on-demand fallback.

    1. Check Material DB / Redis cache for existing result
    2. If found → return cached result instantly
    3. If not found → generate on-the-fly via AI API → cache → return

    Everyone can use this endpoint. Results are cached for future requests.
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
            length=SHORT_VIDEO_LENGTH
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
# TOOL-SPECIFIC DEMO GENERATION (cache-first with on-demand fallback)
# =============================================================================

@router.post("/generate/{tool_type}")
async def generate_demo_for_tool(
    tool_type: str,
    topic: Optional[str] = Query(None, description="Topic / scene / style filter"),
    product_id: Optional[str] = Query(None, description="Product/avatar/model ID filter"),
    language: Optional[str] = Query(None, description="Language for avatar script (zh-TW, en)"),
    input_image_url: Optional[str] = Query(None, description="Pregenerated input image URL the user picked"),
    input_video_url: Optional[str] = Query(None, description="Pregenerated input video URL the user picked"),
    effect_prompt: Optional[str] = Query(None, description="Effect/style/motion prompt the user picked"),
    model_id: Optional[str] = Query(None, description="Demo model id (e.g. default, kling_v3, sora2, veo) — picks the premium-model cached example"),
    room_id: Optional[str] = Query(None, description="Room redesign demo room id"),
    room_type: Optional[str] = Query(None, description="Room redesign room type"),
    style_id: Optional[str] = Query(None, description="Room redesign style id"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """
    Demo generation for a specific tool type — everyone can use this.

    1. Check Material DB by lookup_hash(tool, effect_or_topic, input_url) for
       an exact-pair cache hit when the user picked a specific input + effect.
    2. Otherwise check by (topic, product_id) for back-compat.
    3. On cache miss → generate on-demand via real AI API using the user's
       chosen input + effect → persist under the same lookup_hash → return.
    """
    from app.services.material_lookup import get_material_lookup_service
    from app.services.demo_cache_service import DemoCacheService
    from app.api.deps import get_redis

    valid_tool_types = get_all_tool_types()
    if tool_type not in valid_tool_types:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "invalid_tool_type",
                "message": f"Unknown tool type: {tool_type}",
                "valid_tool_types": valid_tool_types,
            },
        )

    # Defense-in-depth (2026-06-25): the supported visitor/free flow is "pick a
    # dropdown preset, unchanged" — never a typed prompt. So a non-subscriber's
    # inbound free-form `effect_prompt` is ignored ENTIRELY here, independent of
    # the global DEMO_PRESET_ONLY flag, so it can never seed a cache-miss
    # generation. The example is still resolved from the curated dropdown levers
    # (topic / model_id). This mirrors the custom-prompt gate on the real tool
    # endpoints. Subscribers don't use this demo path (they hit the real tool
    # endpoint), so their generation is unaffected.
    if effect_prompt and not is_subscribed_user(current_user):
        logger.info(
            "[demo] ignoring free-form effect_prompt from non-subscriber for tool=%s "
            "(preset-only visitor flow)",
            tool_type,
        )
        effect_prompt = None

    # When the caller provided a specific (input_url, effect_prompt), skip the
    # generic preset list and route straight through the cache service so the
    # lookup_hash path runs first.
    skip_generic_presets = bool(input_image_url or input_video_url or effect_prompt)

    if skip_generic_presets:
        presets = []
    else:
        lookup_service = get_material_lookup_service(db)
        presets = await lookup_service.get_presets_for_tool(
            tool_type, topic, limit=20, product_id=product_id
        )

    # If no presets match the requested (topic, product_id), generate one on-demand
    if not presets:
        try:
            redis = await get_redis()
        except Exception:
            redis = None

        cache_service = DemoCacheService(db, redis)
        request_input_params = {}
        if tool_type == "room_redesign":
            request_input_params = {
                key: value
                for key, value in {
                    "room_id": room_id,
                    "room_type": room_type,
                    "style_id": style_id,
                }.items()
                if value
            }
        # Thread the picked model through so a premium-model cached example
        # (pregenerated with input_params.model_id) is matched/recorded. Only a
        # real premium pick is tagged — "default"/empty stays untagged so it
        # keeps hitting the standard free examples.
        if model_id and model_id != "default":
            request_input_params["model_id"] = model_id
        request_input_params = request_input_params or None

        generated = await cache_service.get_or_generate(
            tool_type,
            topic,
            product_id=product_id,
            language=language,
            input_image_url=input_image_url,
            input_video_url=input_video_url,
            effect_prompt=effect_prompt,
            input_params=request_input_params,
        )

        if generated:
            subscribed = is_subscribed_user(current_user)
            clean_url = generated.get("result_url")
            # Prefer a watermarked variant for non-subscribers; the cache
            # service returns one when it persisted a watermarked copy. Fall
            # back to the clean URL only when no watermark exists yet.
            wm_url = generated.get("watermarked_url") or generated.get("result_watermarked_url")
            return {
                "success": True,
                "tool_type": tool_type,
                "generated_on_demand": True,
                "presets": [
                    {
                        "id": generated.get("id", "temp"),
                        "prompt": generated.get("prompt"),
                        "prompt_zh": None,
                        "thumbnail_url": wm_url or clean_url,
                        "result_watermarked_url": wm_url or clean_url,
                        "input_image_url": generated.get("input_image_url"),
                        "result_url": clean_url if subscribed else (wm_url or clean_url),
                        "can_download": subscribed,
                    }
                ],
                "count": 1,
            }

        return {
            "success": True,
            "tool_type": tool_type,
            "message": "Generation in progress. Please try again shortly.",
            "presets": [],
            "count": 0,
        }

    subscribed = is_subscribed_user(current_user)
    return {
        "success": True,
        "tool_type": tool_type,
        "presets": [
            {
                "id": str(p.id),
                "prompt": p.prompt,
                "prompt_zh": p.prompt_zh,
                "thumbnail_url": p.result_thumbnail_url or p.result_watermarked_url or p.result_image_url,
                "result_watermarked_url": p.result_watermarked_url,
                "input_image_url": p.input_image_url,
                "result_url": (p.result_video_url or p.result_image_url) if subscribed else p.result_watermarked_url,
                "can_download": subscribed,
            }
            for p in presets
        ],
        "count": len(presets),
    }


# =============================================================================
# PAID TIER GENERATION (with image upload & Material DB storage)
# =============================================================================

@router.post("/generate/paid", response_model=PaidGenerationResponse)
async def generate_paid_tier(
    request: PaidGenerationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Legacy paid runtime example-generation endpoint.

    Subscriber generation should use the tool-specific endpoints under /api/v1/tools
    or /api/v1/uploads. Demo examples are developer-managed only.
    """
    _runtime_demo_generation_disabled()

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
            # Video generation with PiAPI via provider router
            from app.providers.provider_router import get_provider_router, TaskType as ProvTaskType
            router = get_provider_router()

            result = await router.route(
                ProvTaskType.I2V,
                {
                    "image_url": input_image_url,
                    "prompt": enhanced_prompt,
                    "duration": SHORT_VIDEO_LENGTH
                }
            )

            if result.get("success"):
                vid_output = result.get("output", {})
                result_video_url = vid_output.get("video_url") or result.get("video_url")
                total_cost += 0.10

                generation_steps.append({
                    "step": len(generation_steps) + 1,
                    "api": "piapi",
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
                    length=SHORT_VIDEO_LENGTH
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
    Legacy search endpoint from the old runtime-demo system.

    Runtime generation is disabled. Use /api/v1/demo/presets and the inspiration
    gallery to browse pre-generated examples.
    """
    _runtime_demo_generation_disabled()


@router.post("/generate-image", response_model=GenerateImageResponse)
async def generate_demo_image(
    request: GenerateImageRequest,
):
    """
    Legacy runtime demo-image generation endpoint.

    Runtime generation is disabled. Use a pre-generated demo preset instead.
    """
    _runtime_demo_generation_disabled()


@router.post("/generate-realtime", response_model=RealtimeDemoResponse)
async def generate_demo_realtime(
    request: RealtimeDemoRequest,
):
    """
    Legacy runtime demo-video generation endpoint.

    Runtime generation is disabled. Use pre-generated demo video examples instead.
    """
    _runtime_demo_generation_disabled()


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
    from app.models.material import Material, ToolType, MaterialStatus
    from app.config.topic_registry import get_topics_for_tool
    from sqlalchemy import func

    # Get topic definitions
    avatar_topics = get_topics_for_tool(ToolType.AI_AVATAR.value)

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
        topic_id = topic["id"]
        count = topic_counts.get(topic_id, 0)

        if language == "zh-TW":
            name = topic.get("name_zh") or topic.get("name_en", "")
        else:
            name = topic.get("name_en") or topic.get("name_zh", "")

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
# INSPIRATION GALLERY - 24 Categories (must be before /{demo_id})
# =============================================================================

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

    topic_keywords = GALLERY_CATEGORY_MAP.get(category, [category])
    conditions = []
    for keyword in topic_keywords:
        conditions.append(Material.topic.ilike(f"%{keyword}%"))
        conditions.append(Material.tags.contains([keyword]))
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
    items = []
    for m in materials:
        if language.startswith("zh"):
            title = m.title_zh or m.title_en or f"{category} #{len(items) + 1}"
        elif language.startswith("ja"):
            title = m.title_en or f"{category} #{len(items) + 1}"
        elif language.startswith("ko"):
            title = m.title_en or f"{category} #{len(items) + 1}"
        elif language.startswith("es"):
            title = m.title_en or f"{category} #{len(items) + 1}"
        else:
            title = m.title_en or f"{category} #{len(items) + 1}"
        prompt = m.prompt or m.prompt_enhanced or ""
        thumb = m.result_image_url or m.input_image_url or m.result_thumbnail_url
        if thumb:
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
# LANDING PAGE EXAMPLES
# =============================================================================

# Map material topics to landing page categories
TOPIC_TO_CATEGORY = {
    "ecommerce": "ecommerce",
    "social": "social",
    "brand": "brand",
    "app": "app",
    "promo": "promo",
    "service": "service"
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

    # Landing page categories must match landing topics registry
    from app.config.topic_registry import get_landing_topic_ids
    landing_topics = get_landing_topic_ids()

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

        # Topic display names for UI
        topic_names = {
            "ecommerce": {"en": "E-commerce", "zh": "電商廣告"},
            "social": {"en": "Social Media", "zh": "社群媒體"},
            "brand": {"en": "Brand Promotion", "zh": "品牌推廣"},
            "app": {"en": "App Promotion", "zh": "應用推廣"},
            "promo": {"en": "Promotional", "zh": "活動促銷"},
            "service": {"en": "Service Introduction", "zh": "服務介紹"}
        }
        topic_display = topic_names.get(topic, {"en": topic.replace("_", " ").title(), "zh": topic})

        # Use prompt as description, create title from topic
        title_en = video.title_en or topic_display["en"]
        title_zh = video.title_zh or topic_display["zh"]

        # For thumb: use video URL as poster (browser will extract first frame)
        # Or use a topic-specific Unsplash image
        topic_images = {
            "ecommerce": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600",
            "social": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=600",
            "brand": "https://images.unsplash.com/photo-1552664730-d307ca884978?w=600",
            "app": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=600",
            "promo": "https://images.unsplash.com/photo-1607083206869-4c7672e72a8a?w=600",
            "service": "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=600"
        }

        all_examples.append({
            "id": str(video.id),
            "category": topic,
            "title": title_zh if language.startswith("zh") else title_en,
            "title_zh": title_zh,
            "title_en": title_en,
            "prompt": video.prompt[:100] if video.prompt else "",
            "thumb": video.input_image_url or topic_images.get(topic, "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600"),
            "video": video.result_video_url,
            "avatar_video": avatar_video,
            "duration": f"{SHORT_VIDEO_LENGTH}s",
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


@router.get("/landing/works")
async def get_landing_works(
    language: str = Query("en", description="Language code"),
    limit: int = Query(24, ge=8, le=48, description="Number of works to return"),
    tool_type: Optional[str] = Query(None, description="Filter by tool: product_scene, effect, background_removal, room_redesign, short_video, ai_avatar"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get works gallery for homepage - 產品增強 (product enhancement) & 廣告特效 (ad effects).
    Returns materials from product_scene, effect, background_removal for dense gallery display.
    Similar to douhuiai.com homepage works showcase.
    """
    from sqlalchemy import func
    from app.models.material import Material, ToolType

    # Tool types for product visuals, interiors, image effects, and video content
    valid_tool_types = ("product_scene", "effect", "background_removal", "room_redesign", "short_video", "ai_avatar")
    # 2026-05-18 — drop ROOM_REDESIGN from the default pool. Historical seed
    # rows pair captions and images unreliably (e.g. balcony caption on a
    # bedroom image, or people present in renders the user asked to keep
    # unpopulated). The frontend curated fallback covers this category.
    # An explicit ?tool_type=room_redesign request still works.
    works_tool_types = [
        ToolType.PRODUCT_SCENE,
        ToolType.EFFECT,
        ToolType.BACKGROUND_REMOVAL,
        ToolType.SHORT_VIDEO,
        ToolType.AI_AVATAR,
    ]
    if tool_type and tool_type in valid_tool_types:
        works_tool_types = [ToolType(tool_type)]

    # Query materials with images or videos
    result = await db.execute(
        select(Material)
        .where(
            Material.tool_type.in_(works_tool_types),
            Material.is_active == True,
            (
                Material.result_image_url.isnot(None)
                | Material.result_watermarked_url.isnot(None)
                | Material.result_video_url.isnot(None)
            ),
            *_public_material_filters(Material),
        )
        .order_by(func.random())
        .limit(limit)
    )
    materials = result.scalars().all()

    # Tool display names and routes
    tool_info = {
        "product_scene": {"name_en": "Product Scene", "name_zh": "商品場景", "route": "/tools/product-scene"},
        "effect": {"name_en": "Image Effects", "name_zh": "圖片風格", "route": "/tools/effects"},
        "background_removal": {"name_en": "Background Removal", "name_zh": "一鍵白底", "route": "/tools/background-removal"},
        "room_redesign": {"name_en": "Interior Proposal Render", "name_zh": "室內設計渲染", "route": "/tools/room-redesign"},
        "short_video": {"name_en": "Short Video", "name_zh": "短影片", "route": "/tools/short-video"},
        "ai_avatar": {"name_en": "AI Avatar", "name_zh": "AI 數位人", "route": "/tools/avatar"},
    }

    items = []
    for m in materials:
        tt = m.tool_type.value if hasattr(m.tool_type, "value") else str(m.tool_type)
        info = tool_info.get(tt, {"name_en": tt, "name_zh": tt, "route": "/"})
        # For video tools, use video thumbnail or input image; for image tools, use result
        video_url = m.result_video_url if tt in ("short_video", "ai_avatar") else None
        thumb = m.result_watermarked_url or m.result_image_url or m.result_thumbnail_url or m.input_image_url
        if not thumb and not video_url:
            continue
        title, prompt = _landing_work_copy(
            m,
            tt,
            language,
            info["name_zh"] if language.startswith("zh") else info["name_en"],
        )
        items.append({
            "id": str(m.id),
            "tool_type": tt,
            "tool_name": info["name_zh"] if language.startswith("zh") else info["name_en"],
            "route": info["route"],
            "title": title,
            "prompt": prompt,
            "thumb": thumb,
            "video_url": video_url,
            "input_image_url": m.input_image_url,  # For effect before/after
            "result_image_url": m.result_watermarked_url or m.result_image_url,
            "topic": m.topic,
            "input_params": m.input_params or {},
        })

    return {
        "success": True,
        "items": items,
        "total": len(items),
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
    from app.config.topic_registry import get_landing_topic_ids
    landing_topics = get_landing_topic_ids()

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

# ============================================================================
# Utility Endpoints
# ============================================================================

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), request: Request = None):
    """
    General file upload endpoint for demo tools.

    Auto-normalizes the upload: any decodable image format (JPG, PNG,
    WebP, HEIC/HEIF, BMP, TIFF, GIF) is re-encoded to PNG (or JPEG when
    we have to compress to fit the size budget) and resized/cropped to
    fit the common dimension rule. Users no longer get a 422 because
    their iPhone photo is HEIC or their panorama is 4:1 — we just fix
    it server-side.
    """
    try:
        content = await file.read()

        # Try the normaliser first. If it can decode the bytes as ANY
        # image format, we accept and re-encode to a clean PNG. Falls
        # through to the strict validator for non-image uploads (rare;
        # this endpoint is image-only in practice).
        from app.services.image_normalize_service import normalize_uploaded_image

        try:
            normalized = normalize_uploaded_image(
                content,
                rules=COMMON_IMAGE_DIMENSION_RULES,
                max_bytes=20 * 1024 * 1024,
            )
            content = normalized.bytes
            content_type = normalized.content_type
        except HTTPException:
            # Fall back to the strict validator so callers who genuinely
            # uploaded a non-image (mistakenly) still see the original
            # "Unsupported file content" 415 message.
            content_type = validate_uploaded_content(
                content=content,
                declared_content_type=file.content_type,
                expected_kind=None,
                max_bytes=20 * 1024 * 1024,
                dimension_rules=COMMON_IMAGE_DIMENSION_RULES,
            )

        filename = f"{uuid.uuid4()}{extension_for_content_type(content_type)}"

        static_path = f"/static/uploads/{filename}"
        public_url = static_path

        gcs = get_gcs_storage()
        uploaded_to_gcs = False
        if gcs.enabled:
            try:
                public_url = gcs.upload_public(
                    data=content,
                    blob_name=f"uploads/demo/{filename}",
                    content_type=content_type,
                )
                uploaded_to_gcs = True
            except Exception as exc:
                logger.warning("GCS demo upload failed; falling back to local storage: %s", exc)

        if not uploaded_to_gcs:
            # Local dev fallback when GCS is not wired.
            upload_dir = Path("/app/static/uploads")
            upload_dir.mkdir(parents=True, exist_ok=True)
            filepath = upload_dir / filename
            with open(filepath, "wb") as buffer:
                buffer.write(content)

            public_base = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
            public_url = f"{public_base}{static_path}" if public_base else static_path

        return {"url": public_url, "static_path": static_path}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Demo upload failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "upload_failed",
                "message": "Upload could not be completed. Please try again.",
            },
        )
