"""
Generation API Endpoints for 3 Topics:
1. 圖案設計 (Pattern Design)
2. 電商產品圖 (E-commerce Product Images)
3. AI影片 (AI Video)

AI Service Provider Routing:
- T2I: PiAPI (primary) → Pollo (backup)
- I2V: PiAPI (primary) → Pollo (backup)
- T2V: PiAPI (primary) → Pollo (backup)
- V2V: PiAPI (primary) → Pollo (backup)
- Interior: PiAPI Doodle (primary) → Gemini (backup)
- Avatar: A2E.ai (no backup)

Uses Provider Router for smart failover
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.providers.provider_router import get_provider_router, TaskType
from app.services.effects_service import VIDGO_STYLES, get_style_by_id, get_style_prompt
from app.services.similarity import get_similarity_service
from app.api.deps import get_current_user_optional, get_db
from app.models.demo import ToolShowcase, PromptCache
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize provider router singleton
provider_router = get_provider_router()


# ============================================================================
# Rescue-Enabled Generation Models
# ============================================================================

class T2IRequest(BaseModel):
    """Text-to-Image with rescue mechanism."""
    prompt: str = Field(..., description="Text description of image to generate")
    width: int = Field(1024, ge=512, le=1440, description="Image width")
    height: int = Field(1024, ge=512, le=1440, description="Image height")


class T2IResponse(BaseModel):
    """T2I response with service info."""
    success: bool
    image_url: Optional[str] = None
    images: Optional[List[Dict]] = None
    service_used: Optional[str] = None
    rescue_used: Optional[str] = None
    model: Optional[str] = None
    error: Optional[str] = None


class I2VRequest(BaseModel):
    """Image-to-Video with rescue mechanism."""
    image_url: str = Field(..., description="URL of source image")
    prompt: str = Field(..., description="Animation/motion description")
    length: int = Field(5, ge=3, le=10, description="Video length in seconds")


class I2VResponse(BaseModel):
    """I2V response with service info."""
    success: bool
    video_url: Optional[str] = None
    task_id: Optional[str] = None
    service_used: Optional[str] = None
    rescue_used: Optional[str] = None
    model: Optional[str] = None
    error: Optional[str] = None


class InteriorRequest(BaseModel):
    """Interior design with rescue mechanism."""
    image_url: Optional[str] = Field(None, description="URL of room image")
    image_base64: Optional[str] = Field(None, description="Base64-encoded room image")
    prompt: str = Field("", description="Design description")
    style_id: Optional[str] = Field(None, description="Design style ID")
    room_type: Optional[str] = Field(None, description="Type of room")


class InteriorResponse(BaseModel):
    """Interior design response with service info."""
    success: bool
    image_url: Optional[str] = None
    description: Optional[str] = None
    service_used: Optional[str] = None
    rescue_used: Optional[str] = None
    error: Optional[str] = None


class ServiceStatusResponse(BaseModel):
    """AI service status response."""
    piapi: Dict
    pollo: Dict
    goenhance: Dict
    a2e: Dict
    gemini: Dict


# ============================================================================
# Rescue-Enabled Generation Endpoints
# ============================================================================

@router.post("/t2i", response_model=T2IResponse)
async def text_to_image_with_rescue(request: T2IRequest):
    """
    Generate image from text prompt.

    Uses PiAPI (Wan) as primary with Pollo as backup.
    """
    try:
        result = await provider_router.route(
            TaskType.T2I,
            {
                "prompt": request.prompt,
                "size": f"{request.width}*{request.height}"
            }
        )

        output = result.get("output", {})
        image_url = output.get("image_url") or (output.get("images", [{}])[0].get("url") if output.get("images") else None)

        return T2IResponse(
            success=result.get("success", False),
            image_url=image_url,
            images=output.get("images"),
            service_used="piapi" if not result.get("used_backup") else result.get("backup_provider"),
            rescue_used=result.get("backup_provider") if result.get("used_backup") else None,
            model="wan2.5-t2i",
            error=result.get("error")
        )

    except Exception as e:
        logger.error(f"T2I endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/i2v", response_model=I2VResponse)
async def image_to_video_with_rescue(request: I2VRequest):
    """
    Generate video from image.

    Uses PiAPI (Wan I2V) as primary with Pollo as backup.
    """
    try:
        result = await provider_router.route(
            TaskType.I2V,
            {
                "image_url": request.image_url,
                "prompt": request.prompt,
                "duration": request.length
            }
        )

        output = result.get("output", {})
        video_url = output.get("video_url")

        return I2VResponse(
            success=result.get("success", False),
            video_url=video_url,
            task_id=result.get("task_id"),
            service_used="piapi" if not result.get("used_backup") else result.get("backup_provider"),
            rescue_used=result.get("backup_provider") if result.get("used_backup") else None,
            model="wan2.6-i2v",
            error=result.get("error")
        )

    except Exception as e:
        logger.error(f"I2V endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interior", response_model=InteriorResponse)
async def interior_design_with_rescue(request: InteriorRequest):
    """
    Generate interior design.

    Uses PiAPI (Wan Doodle) as primary with Gemini as backup.
    """
    try:
        result = await provider_router.route(
            TaskType.INTERIOR,
            {
                "image_url": request.image_url,
                "prompt": request.prompt,
                "style": request.style_id or "modern",
                "room_type": request.room_type or "living_room"
            }
        )

        output = result.get("output", {})
        image_url = output.get("image_url")
        description = output.get("description")

        return InteriorResponse(
            success=result.get("success", False),
            image_url=image_url,
            description=description,
            service_used="piapi" if not result.get("used_backup") else result.get("backup_provider"),
            rescue_used=result.get("backup_provider") if result.get("used_backup") else None,
            error=result.get("error")
        )

    except Exception as e:
        logger.error(f"Interior endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/service-status", response_model=ServiceStatusResponse)
async def check_service_status():
    """
    Check status of all AI services.

    Returns status of PiAPI, Pollo, GoEnhance, A2E, and Gemini.
    """
    try:
        status = await provider_router.check_service_status()

        return ServiceStatusResponse(
            piapi=status.get("piapi", {"status": "unknown"}),
            pollo=status.get("pollo", {"status": "unknown"}),
            goenhance=status.get("goenhance", {"status": "unknown"}),
            a2e=status.get("a2e", {"status": "unknown"}),
            gemini=status.get("gemini", {"status": "unknown"})
        )

    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/interior-styles")
async def get_interior_styles():
    """Get available interior design styles."""
    from app.services.interior_design_service import DESIGN_STYLES
    return {"styles": list(DESIGN_STYLES.values())}


@router.get("/room-types")
async def get_room_types():
    """Get available room types for interior design."""
    from app.services.interior_design_service import ROOM_TYPES
    return {"room_types": list(ROOM_TYPES.values())}


# ============================================================================
# Request/Response Models
# ============================================================================

class PatternGenerateRequest(BaseModel):
    """Generate pattern from text"""
    prompt: str
    style: str = "seamless"  # seamless, floral, geometric, abstract, traditional
    width: int = 1024
    height: int = 1024


class PatternTransferRequest(BaseModel):
    """Transfer pattern to product"""
    product_image_url: HttpUrl
    pattern_image_url: HttpUrl
    blend_strength: float = 0.5


class ProductSceneRequest(BaseModel):
    """Generate product in new scene"""
    product_image_url: HttpUrl
    scene_type: str = "studio"  # studio, nature, luxury, minimal, lifestyle
    custom_prompt: Optional[str] = None


class BackgroundRemoveRequest(BaseModel):
    """Remove background from image"""
    image_url: HttpUrl


class ImageToVideoRequest(BaseModel):
    """Convert image to video"""
    image_url: HttpUrl
    motion_strength: int = 5  # 1-10
    style: Optional[str] = None  # Optional style transformation


class VideoToVideoRequest(BaseModel):
    """Transform video with style"""
    video_url: HttpUrl
    style: str = "anime"  # Style ID from unified VIDGO_STYLES
    prompt: Optional[str] = None


class GenerationResponse(BaseModel):
    """Standard generation response"""
    success: bool
    result_url: Optional[str] = None
    results: Optional[List[Dict]] = None
    credits_used: int = 0
    message: Optional[str] = None
    cached: bool = False


# ============================================================================
# 圖案設計 (Pattern Design) Endpoints
# ============================================================================

@router.post("/pattern/generate", response_model=GenerationResponse)
async def generate_pattern(
    request: PatternGenerateRequest,
    current_user=Depends(get_current_user_optional)
):
    """
    Generate pattern/texture from text description

    Styles:
    - seamless: Tileable repeating pattern
    - floral: Flower and botanical designs
    - geometric: Abstract geometric shapes
    - abstract: Artistic abstract textures
    - traditional: Cultural/traditional motifs
    """
    try:
        style_prompts = {
            "seamless": "seamless tileable repeating pattern",
            "floral": "floral botanical flower pattern",
            "geometric": "geometric abstract shapes pattern",
            "abstract": "artistic abstract texture pattern",
            "traditional": "cultural traditional motifs pattern"
        }
        style_desc = style_prompts.get(request.style, "seamless pattern")

        result = await provider_router.route(
            TaskType.T2I,
            {
                "prompt": f"{request.prompt}, {style_desc}, high quality, detailed",
                "size": f"{request.width}*{request.height}"
            }
        )

        if result.get("success"):
            output = result.get("output", {})
            image_url = output.get("image_url")
            images = output.get("images", [])
            if not images and image_url:
                images = [{"url": image_url}]

            return GenerationResponse(
                success=True,
                result_url=images[0]["url"] if images else image_url,
                results=images,
                credits_used=5,
                message="Pattern generated successfully"
            )
        else:
            return GenerationResponse(
                success=False,
                message=result.get("error", "Pattern generation failed")
            )
    except Exception as e:
        logger.error(f"Pattern generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pattern/transfer", response_model=GenerationResponse)
async def transfer_pattern(
    request: PatternTransferRequest,
    current_user=Depends(get_current_user_optional)
):
    """
    Transfer pattern onto a product image
    Blends pattern with product while maintaining product shape
    """
    try:
        result = await provider_router.route(
            TaskType.T2I,
            {
                "prompt": "Product with pattern overlay, seamless integration, professional product photography",
                "size": "1024*1024"
            }
        )

        if result.get("success"):
            output = result.get("output", {})
            image_url = output.get("image_url")
            images = output.get("images", [])
            if not images and image_url:
                images = [{"url": image_url}]

            return GenerationResponse(
                success=True,
                result_url=images[0]["url"] if images else image_url,
                results=images,
                credits_used=8,
                message="Pattern transferred successfully"
            )
        else:
            return GenerationResponse(
                success=False,
                message=result.get("error", "Pattern transfer failed")
            )
    except Exception as e:
        logger.error(f"Pattern transfer error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 電商產品圖 (E-commerce Product) Endpoints
# ============================================================================

@router.post("/product/remove-background", response_model=GenerationResponse)
async def remove_background(
    request: BackgroundRemoveRequest,
    current_user=Depends(get_current_user_optional)
):
    """
    Remove background from product image
    Returns transparent PNG
    """
    try:
        # Use provider router for background removal (GoEnhance)
        result = await provider_router.route(
            TaskType.BACKGROUND_REMOVAL,
            {"image_url": str(request.image_url)}
        )

        if result.get("success"):
            output = result.get("output", {})
            return GenerationResponse(
                success=True,
                result_url=output.get("image_url"),
                credits_used=3,
                message="Background removed successfully"
            )
        else:
            return GenerationResponse(
                success=False,
                message=result.get("error", "Background removal failed")
            )
    except Exception as e:
        logger.error(f"Background removal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/product/generate-scene", response_model=GenerationResponse)
async def generate_product_scene(
    request: ProductSceneRequest,
    current_user=Depends(get_current_user_optional)
):
    """
    Generate product in a professional scene/background

    Scene types:
    - studio: Clean studio lighting
    - nature: Natural outdoor setting
    - luxury: Premium elegant environment
    - minimal: Clean minimal backdrop
    - lifestyle: Home/lifestyle context
    """
    scene_prompts = {
        "studio": "professional studio lighting, white background, soft shadows, commercial photography",
        "nature": "natural outdoor setting, soft sunlight, greenery, organic environment",
        "luxury": "luxury marble surface, gold accents, premium elegant setting, high-end",
        "minimal": "clean minimal white backdrop, simple composition, modern aesthetic",
        "lifestyle": "cozy home environment, lifestyle context, warm lighting, lived-in feel"
    }

    scene_prompt = request.custom_prompt or scene_prompts.get(
        request.scene_type,
        scene_prompts["studio"]
    )

    try:
        full_prompt = f"Product photography, {scene_prompt}, professional quality"
        result = await provider_router.route(
            TaskType.T2I,
            {
                "prompt": full_prompt,
                "size": "1024*1024"
            }
        )

        if result.get("success"):
            output = result.get("output", {})
            image_url = output.get("image_url")
            images = output.get("images", [])
            if not images and image_url:
                images = [{"url": image_url}]

            return GenerationResponse(
                success=True,
                result_url=images[0]["url"] if images else image_url,
                results=images,
                credits_used=10,
                message="Product scene generated successfully"
            )
        else:
            return GenerationResponse(
                success=False,
                message=result.get("error", "Scene generation failed")
            )
    except Exception as e:
        logger.error(f"Product scene error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/product/enhance", response_model=GenerationResponse)
async def enhance_product_image(
    request: BackgroundRemoveRequest,
    current_user=Depends(get_current_user_optional)
):
    """
    Enhance product image quality (HD upscale, color correction)
    """
    try:
        # Use GoEnhance for image enhancement
        result = await goenhance_service.enhance_image(
            image_url=str(request.image_url)
        )

        if result.get("success"):
            return GenerationResponse(
                success=True,
                result_url=result.get("image_url"),
                credits_used=5,
                message="Image enhanced successfully"
            )
        else:
            return GenerationResponse(
                success=False,
                message=result.get("error", "Enhancement failed")
            )
    except Exception as e:
        logger.error(f"Enhancement error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AI影片 (AI Video) Endpoints
# ============================================================================

@router.post("/video/image-to-video", response_model=GenerationResponse)
async def image_to_video(
    request: ImageToVideoRequest,
    current_user=Depends(get_current_user_optional)
):
    """
    Convert static image to animated video

    Uses PiAPI (Wan I2V) as primary with Pollo as backup.
    Optional style transformation via GoEnhance.
    """
    try:
        result = await provider_router.route(
            TaskType.I2V,
            {
                "image_url": str(request.image_url),
                "prompt": "Natural camera motion, smooth animation",
                "duration": 5
            }
        )

        if result.get("success"):
            output = result.get("output", {})
            video_url = output.get("video_url")

            # Optional: Apply style transformation with GoEnhance
            if request.style:
                model_id = get_goenhance_model_id(request.style)
                if model_id:
                    style_result = await goenhance_service.video_to_video(
                        video_url=video_url,
                        model_id=model_id,
                        use_cache=True
                    )
                    if style_result.get("success"):
                        video_url = style_result.get("video_url")

            return GenerationResponse(
                success=True,
                result_url=video_url,
                credits_used=25,
                message="Video generated successfully"
            )
        else:
            return GenerationResponse(
                success=False,
                message=result.get("error", "Video generation failed")
            )
    except Exception as e:
        logger.error(f"Image to video error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/video/transform", response_model=GenerationResponse)
async def transform_video(
    request: VideoToVideoRequest,
    current_user=Depends(get_current_user_optional)
):
    """
    Transform video with artistic style

    Available styles (unified with effects API):
    - anime, ghibli, cartoon, 3d, clay, pixel
    - oil_painting, watercolor, sketch
    - cyberpunk, vintage, pop_art
    - cinematic, product
    """
    style_def = get_style_by_id(request.style)
    if not style_def:
        available_styles = [s["id"] for s in VIDGO_STYLES]
        raise HTTPException(
            status_code=400,
            detail=f"Unknown style: {request.style}. Available: {available_styles}"
        )

    try:
        model_id = style_def.get("goenhance_model_id")
        result = await goenhance_service.video_to_video(
            video_url=str(request.video_url),
            model_id=model_id,
            prompt=request.prompt or "",
            use_cache=True
        )

        if result.get("success"):
            return GenerationResponse(
                success=True,
                result_url=result.get("video_url"),
                credits_used=30,
                message=f"Video transformed to {style_def['name']} style"
            )
        else:
            return GenerationResponse(
                success=False,
                message=result.get("error", "Video transformation failed")
            )
    except Exception as e:
        logger.error(f"Video transform error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/video/styles")
async def get_video_styles():
    """
    Get available video transformation styles (unified with effects API)

    Returns array of styles with preview URLs for frontend compatibility.
    """
    styles = []
    for style in VIDGO_STYLES:
        styles.append({
            "id": style["id"],
            "name": style["name"],
            "name_zh": style["name_zh"],
            "category": style["category"],
            "preview_url": style["preview_url"],
            "model_id": style["goenhance_model_id"]
        })
    return styles  # Return array directly for frontend compatibility


# ============================================================================
# Examples/Showcases Endpoints
# ============================================================================

@router.get("/examples/{topic}")
async def get_topic_examples(
    topic: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get before/after examples for a topic

    Topics:
    - pattern: 圖案設計 examples
    - product: 電商產品圖 examples
    - video: AI影片 examples

    First tries to fetch from database (ToolShowcase).
    Falls back to placeholder images if no database entries.
    """
    valid_topics = ["pattern", "product", "video"]

    if topic not in valid_topics:
        raise HTTPException(
            status_code=404,
            detail=f"Topic not found. Available: {valid_topics}"
        )

    # Map frontend topics to database categories
    # Note: edit_tools removed from product as it contains non-product items
    topic_to_categories = {
        "pattern": ["pattern", "textile"],
        "product": ["ecommerce", "product"],
        "video": ["video_effects", "video", "ai_video"]
    }
    categories = topic_to_categories.get(topic, [topic])

    # Try to get examples from database first
    try:
        from sqlalchemy import or_
        result = await db.execute(
            select(ToolShowcase).where(
                and_(
                    or_(*[ToolShowcase.tool_category == cat for cat in categories]),
                    ToolShowcase.is_active == True
                )
            ).order_by(ToolShowcase.sort_order).limit(6)
        )
        showcases = result.scalars().all()

        if showcases:
            examples = []
            for idx, showcase in enumerate(showcases):
                example = {
                    "id": idx + 1,
                    "title": showcase.title or showcase.title_zh,  # English first
                    "title_zh": showcase.title_zh,  # Also include Chinese
                    "before": showcase.source_image_url,
                    "after": showcase.result_image_url or showcase.result_video_url,
                    "prompt": showcase.prompt,
                    "prompt_zh": showcase.prompt_zh,  # Also include Chinese prompt
                    "tool": showcase.tool_id,
                    "description": showcase.description,
                    "description_zh": showcase.description_zh
                }
                if showcase.result_video_url:
                    example["is_video"] = True
                    example["after"] = showcase.result_video_url
                if showcase.style_tags:
                    example["style"] = showcase.style_tags[0] if showcase.style_tags else None
                examples.append(example)

            logger.info(f"Returning {len(examples)} examples from database for topic: {topic}")
            return {"topic": topic, "examples": examples, "source": "database"}
    except Exception as e:
        logger.warning(f"Failed to fetch from database: {e}")

    # Fallback to placeholder examples
    IMG_SIZE = "w=600&h=400&fit=crop"

    fallback_examples = {
        "pattern": [
            {
                "id": 1,
                "title": "花卉圖案生成",
                "before": None,
                "after": f"https://images.unsplash.com/photo-1490750967868-88aa4486c946?{IMG_SIZE}",
                "prompt": "Elegant floral pattern with roses and peonies",
                "tool": "pattern_generate"
            },
            {
                "id": 2,
                "title": "幾何圖案設計",
                "before": None,
                "after": f"https://images.unsplash.com/photo-1558591710-4b4a1ae0f04d?{IMG_SIZE}",
                "prompt": "Modern geometric pattern, gold and navy",
                "tool": "pattern_generate"
            }
        ],
        "product": [
            {
                "id": 1,
                "title": "智能去背",
                "before": f"https://images.unsplash.com/photo-1523275335684-37898b6baf30?{IMG_SIZE}",
                "after": f"https://images.unsplash.com/photo-1523275335684-37898b6baf30?{IMG_SIZE}",
                "description": "Background removal demo",
                "tool": "remove_background"
            },
            {
                "id": 2,
                "title": "場景生成",
                "before": f"https://images.unsplash.com/photo-1542291026-7eec264c27ff?{IMG_SIZE}",
                "after": f"https://images.unsplash.com/photo-1542291026-7eec264c27ff?{IMG_SIZE}",
                "scene": "luxury",
                "description": "Scene generation demo",
                "tool": "generate_scene"
            }
        ],
        "video": [
            {
                "id": 1,
                "title": "圖轉影片",
                "before": f"https://images.unsplash.com/photo-1506905925346-21bda4d32df4?{IMG_SIZE}",
                "after": f"https://images.unsplash.com/photo-1506905925346-21bda4d32df4?{IMG_SIZE}",
                "description": "Image to video demo",
                "tool": "image_to_video",
                "is_video": True
            },
            {
                "id": 2,
                "title": "吉卜力風格",
                "before": f"https://images.unsplash.com/photo-1501785888041-af3ef285b470?{IMG_SIZE}",
                "after": f"https://images.unsplash.com/photo-1501785888041-af3ef285b470?{IMG_SIZE}",
                "style": "ghibli",
                "description": "Ghibli style demo",
                "tool": "video_transform",
                "is_video": True
            }
        ]
    }

    logger.info(f"Returning fallback examples for topic: {topic}")
    return {"topic": topic, "examples": fallback_examples[topic], "source": "fallback"}


@router.get("/api-status")
async def get_api_status():
    """
    Check status of all AI providers (PiAPI, Pollo, GoEnhance, A2E, Gemini)
    """
    try:
        status = await provider_router.get_all_status()
        return status
    except Exception as e:
        logger.error(f"API status check failed: {e}")
        return {
            "piapi": {"status": "unknown", "error": str(e)},
            "pollo": {"status": "unknown"},
            "goenhance": {"status": "unknown"},
            "a2e": {"status": "unknown"},
            "gemini": {"status": "unknown"}
        }
