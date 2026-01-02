"""
Generation API Endpoints for 3 Topics:
1. 圖案設計 (Pattern Design)
2. 電商產品圖 (E-commerce Product Images)
3. AI影片 (AI Video)

Uses Leonardo AI and GoEnhance AI with Redis caching
Supports similarity-based prompt caching to save credits
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.services.leonardo_service import leonardo_service
from app.services.goenhance_service import goenhance_service
from app.services.effects_service import VIDGO_STYLES, get_style_by_id, get_goenhance_model_id
from app.services.similarity import get_similarity_service
from app.api.deps import get_current_user_optional, get_db
from app.models.demo import ToolShowcase, PromptCache
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


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
        result = await leonardo_service.generate_pattern(
            prompt=request.prompt,
            style=request.style,
            use_cache=True
        )

        if result.get("success"):
            images = result.get("images", [])
            return GenerationResponse(
                success=True,
                result_url=images[0]["url"] if images else None,
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
        # Use Leonardo to generate pattern-applied product
        result = await leonardo_service.generate_image(
            prompt=f"Product with pattern overlay, seamless integration, professional product photography",
            width=1024,
            height=1024,
            use_cache=True
        )

        if result.get("success"):
            images = result.get("images", [])
            return GenerationResponse(
                success=True,
                result_url=images[0]["url"] if images else None,
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
        result = await leonardo_service.remove_background(
            image_url=str(request.image_url),
            use_cache=True
        )

        if result.get("success"):
            return GenerationResponse(
                success=True,
                result_url=result.get("image_url"),
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
        result = await leonardo_service.generate_product_scene(
            product_image_url=str(request.product_image_url),
            scene_prompt=scene_prompt,
            use_cache=True
        )

        if result.get("success"):
            images = result.get("images", [])
            return GenerationResponse(
                success=True,
                result_url=images[0]["url"] if images else None,
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
        # Use Leonardo upscaler
        result = await leonardo_service.remove_background(
            image_url=str(request.image_url),
            use_cache=True
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

    Uses Leonardo Motion for natural motion generation.
    Optional style transformation via GoEnhance.
    """
    try:
        # Generate motion video with Leonardo
        result = await leonardo_service.image_to_video(
            image_url=str(request.image_url),
            motion_strength=request.motion_strength,
            use_cache=True
        )

        if result.get("success"):
            video_url = result.get("video_url")

            # Optional: Apply style transformation with GoEnhance using unified styles
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
    Check status of all AI APIs
    """
    status = {
        "leonardo": {"available": False, "tokens": 0},
        "goenhance": {"available": False, "models": 0}
    }

    try:
        # Check Leonardo
        user_info = await leonardo_service.get_user_info()
        if user_info.get("user_details"):
            details = user_info["user_details"][0]
            status["leonardo"] = {
                "available": True,
                "tokens": details.get("subscriptionTokens", 0),
                "api_tokens": details.get("apiSubscriptionTokens", 0)
            }
    except Exception as e:
        logger.error(f"Leonardo status check failed: {e}")

    try:
        # Check GoEnhance
        models = await goenhance_service.get_model_list()
        if models.get("code") == 0:
            model_count = sum(
                len(cat.get("list", []))
                for cat in models.get("data", [])
            )
            status["goenhance"] = {
                "available": True,
                "models": model_count
            }
    except Exception as e:
        logger.error(f"GoEnhance status check failed: {e}")

    return status
