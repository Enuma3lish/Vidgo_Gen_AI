"""
VidGo Tools API - Unified API for 6 Core Tools
Based on ARCHITECTURE_FINAL.md specification

Tools:
1. Background Removal - /tools/remove-bg
2. Product Scene - /tools/product-scene
3. AI Try-On - /tools/try-on
4. Room Redesign - /tools/room-redesign
5. Short Video - /tools/short-video
6. AI Avatar - /tools/avatar (NEW: Photo-to-Avatar with lip sync)
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.effects_service import VIDGO_STYLES, get_style_by_id, get_style_prompt
from app.services.a2e_service import get_a2e_service, A2E_VOICES
from app.services.rescue_service import get_rescue_service
from app.providers.provider_router import get_provider_router, TaskType
from app.api.deps import get_current_user_optional, get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class RemoveBackgroundRequest(BaseModel):
    """Remove background from image"""
    image_url: HttpUrl
    output_format: str = "png"  # png (transparent) or white


class RemoveBackgroundBatchRequest(BaseModel):
    """Batch remove background"""
    image_urls: List[HttpUrl]
    output_format: str = "png"


class ProductSceneRequest(BaseModel):
    """Generate product in new scene"""
    product_image_url: HttpUrl
    scene_type: str = "studio"  # studio, nature, luxury, minimal, lifestyle
    custom_prompt: Optional[str] = None


class TryOnRequest(BaseModel):
    """AI Try-On - virtual clothing try-on"""
    garment_image_url: HttpUrl
    model_image_url: Optional[HttpUrl] = None  # Use preset model if None
    model_id: Optional[str] = None  # Preset model ID
    angle: str = "front"  # front, side, back
    background: str = "white"  # white, transparent, studio


class RoomRedesignRequest(BaseModel):
    """Room Redesign - transform room style"""
    room_image_url: HttpUrl
    style: str = "modern"  # modern, nordic, japanese, industrial, minimalist, luxury
    custom_prompt: Optional[str] = None
    preserve_structure: bool = True


class ShortVideoRequest(BaseModel):
    """Short Video - image to video with optional TTS"""
    image_url: HttpUrl
    motion_strength: int = 5  # 1-10
    style: Optional[str] = None  # Optional style transformation
    script: Optional[str] = None  # Optional TTS script
    voice_id: Optional[str] = None  # TTS voice ID


class AvatarRequest(BaseModel):
    """AI Avatar - Photo-to-Avatar with lip sync"""
    image_url: HttpUrl  # Clear headshot photo
    script: str  # Text for the avatar to speak
    language: str = "en"  # Language code: 'en' or 'zh-TW'
    voice_id: Optional[str] = None  # Voice ID (defaults to first voice for language)
    duration: int = 30  # Target duration in seconds (max 120)
    aspect_ratio: str = "9:16"  # Video aspect ratio: '9:16', '16:9', '1:1'
    resolution: str = "720p"  # Resolution: '720p' or '1080p'


class ToolResponse(BaseModel):
    """Standard tool response"""
    success: bool
    result_url: Optional[str] = None
    results: Optional[List[Dict]] = None
    credits_used: int = 0
    message: Optional[str] = None
    cached: bool = False


# ============================================================================
# Scene Templates
# ============================================================================

SCENE_TEMPLATES = [
    {"id": "studio", "name": "Studio", "name_zh": "攝影棚", "preview_url": "/static/scenes/studio.jpg",
     "prompt": "professional studio lighting, white background, soft shadows, commercial photography"},
    {"id": "nature", "name": "Nature", "name_zh": "自然風景", "preview_url": "/static/scenes/nature.jpg",
     "prompt": "natural outdoor setting, soft sunlight, greenery, organic environment"},
    {"id": "luxury", "name": "Luxury", "name_zh": "奢華風格", "preview_url": "/static/scenes/luxury.jpg",
     "prompt": "luxury marble surface, gold accents, premium elegant setting, high-end"},
    {"id": "minimal", "name": "Minimal", "name_zh": "極簡風格", "preview_url": "/static/scenes/minimal.jpg",
     "prompt": "clean minimal white backdrop, simple composition, modern aesthetic"},
    {"id": "lifestyle", "name": "Lifestyle", "name_zh": "生活情境", "preview_url": "/static/scenes/lifestyle.jpg",
     "prompt": "cozy home environment, lifestyle context, warm lighting, lived-in feel"},
    {"id": "beach", "name": "Beach", "name_zh": "海灘", "preview_url": "/static/scenes/beach.jpg",
     "prompt": "beach seaside setting, ocean waves, sandy shore, summer vibes"},
    {"id": "urban", "name": "Urban", "name_zh": "都市街景", "preview_url": "/static/scenes/urban.jpg",
     "prompt": "urban city street, modern architecture, stylish metropolitan backdrop"},
    {"id": "garden", "name": "Garden", "name_zh": "花園", "preview_url": "/static/scenes/garden.jpg",
     "prompt": "beautiful garden setting, flowers blooming, natural green environment"},
]

# Interior design styles for Room Redesign
INTERIOR_STYLES = [
    {"id": "modern", "name": "Modern", "name_zh": "現代風格", "preview_url": "/static/interior/modern.jpg",
     "prompt": "modern interior design, clean lines, contemporary furniture, neutral colors"},
    {"id": "nordic", "name": "Nordic", "name_zh": "北歐風格", "preview_url": "/static/interior/nordic.jpg",
     "prompt": "scandinavian nordic interior, light wood, white walls, minimalist cozy"},
    {"id": "japanese", "name": "Japanese", "name_zh": "日式風格", "preview_url": "/static/interior/japanese.jpg",
     "prompt": "japanese zen interior, tatami, natural materials, minimal elegant"},
    {"id": "industrial", "name": "Industrial", "name_zh": "工業風", "preview_url": "/static/interior/industrial.jpg",
     "prompt": "industrial loft style, exposed brick, metal pipes, concrete floors"},
    {"id": "minimalist", "name": "Minimalist", "name_zh": "極簡主義", "preview_url": "/static/interior/minimalist.jpg",
     "prompt": "minimalist interior, white space, essential furniture only, clean design"},
    {"id": "luxury", "name": "Luxury", "name_zh": "奢華風格", "preview_url": "/static/interior/luxury.jpg",
     "prompt": "luxury interior design, premium materials, gold accents, elegant sophisticated"},
    {"id": "bohemian", "name": "Bohemian", "name_zh": "波希米亞", "preview_url": "/static/interior/bohemian.jpg",
     "prompt": "bohemian boho interior, colorful textiles, plants, eclectic warm"},
    {"id": "coastal", "name": "Coastal", "name_zh": "海岸風格", "preview_url": "/static/interior/coastal.jpg",
     "prompt": "coastal beach house interior, white blue colors, nautical elements, breezy"},
]

# Preset models for Try-On
TRYON_MODELS = [
    {"id": "female_01", "name": "Female Model 1", "name_zh": "女模特 1",
     "preview_url": "/static/models/female_01.jpg", "gender": "female", "body_type": "slim"},
    {"id": "female_02", "name": "Female Model 2", "name_zh": "女模特 2",
     "preview_url": "/static/models/female_02.jpg", "gender": "female", "body_type": "average"},
    {"id": "female_03", "name": "Female Model 3", "name_zh": "女模特 3",
     "preview_url": "/static/models/female_03.jpg", "gender": "female", "body_type": "plus"},
    {"id": "male_01", "name": "Male Model 1", "name_zh": "男模特 1",
     "preview_url": "/static/models/male_01.jpg", "gender": "male", "body_type": "slim"},
    {"id": "male_02", "name": "Male Model 2", "name_zh": "男模特 2",
     "preview_url": "/static/models/male_02.jpg", "gender": "male", "body_type": "average"},
    {"id": "male_03", "name": "Male Model 3", "name_zh": "男模特 3",
     "preview_url": "/static/models/male_03.jpg", "gender": "male", "body_type": "athletic"},
]

# TTS Voices
TTS_VOICES = [
    {"id": "female_zh", "name": "Chinese Female", "name_zh": "中文女聲", "language": "zh-TW", "gender": "female"},
    {"id": "male_zh", "name": "Chinese Male", "name_zh": "中文男聲", "language": "zh-TW", "gender": "male"},
    {"id": "female_en", "name": "English Female", "name_zh": "英文女聲", "language": "en-US", "gender": "female"},
    {"id": "male_en", "name": "English Male", "name_zh": "英文男聲", "language": "en-US", "gender": "male"},
    {"id": "taigi", "name": "Taiwanese", "name_zh": "台語", "language": "nan-TW", "gender": "neutral"},
]


# ============================================================================
# Tool 1: Background Removal
# ============================================================================

@router.post("/remove-bg", response_model=ToolResponse)
async def remove_background(
    request: RemoveBackgroundRequest,
    current_user=Depends(get_current_user_optional)
):
    """
    Remove background from product image.
    Returns transparent PNG or white background.

    Credits: 3 per image
    """
    try:
        # Use provider router for background removal (GoEnhance)
        provider_router = get_provider_router()
        result = await provider_router.route(
            TaskType.BACKGROUND_REMOVAL,
            {"image_url": str(request.image_url)}
        )

        if result.get("success"):
            output = result.get("output", {})
            return ToolResponse(
                success=True,
                result_url=output.get("image_url"),
                credits_used=3,
                message="Background removed successfully"
            )
        else:
            return ToolResponse(
                success=False,
                message=result.get("error", "Background removal failed")
            )
    except Exception as e:
        logger.error(f"Background removal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/remove-bg/batch", response_model=ToolResponse)
async def remove_background_batch(
    request: RemoveBackgroundBatchRequest,
    current_user=Depends(get_current_user_optional)
):
    """
    Batch remove background from multiple images.
    Maximum 10 images per request.

    Credits: 3 per image
    """
    if len(request.image_urls) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 images per batch")

    results = []
    credits_used = 0
    provider_router = get_provider_router()

    for image_url in request.image_urls:
        try:
            # Use provider router for background removal (GoEnhance)
            result = await provider_router.route(
                TaskType.BACKGROUND_REMOVAL,
                {"image_url": str(image_url)}
            )
            if result.get("success"):
                output = result.get("output", {})
                results.append({
                    "input_url": str(image_url),
                    "result_url": output.get("image_url"),
                    "success": True
                })
                credits_used += 3
            else:
                results.append({
                    "input_url": str(image_url),
                    "success": False,
                    "error": result.get("error", "Failed")
                })
        except Exception as e:
            results.append({
                "input_url": str(image_url),
                "success": False,
                "error": str(e)
            })

    return ToolResponse(
        success=True,
        results=results,
        credits_used=credits_used,
        message=f"Processed {len(results)} images"
    )


# ============================================================================
# Tool 2: Product Scene
# ============================================================================

@router.post("/product-scene", response_model=ToolResponse)
async def generate_product_scene(
    request: ProductSceneRequest,
    current_user=Depends(get_current_user_optional)
):
    """
    Generate product in a professional scene/background.

    Scene types: studio, nature, luxury, minimal, lifestyle, beach, urban, garden
    Credits: 10 per generation
    """
    # Get scene prompt from templates
    scene = next((s for s in SCENE_TEMPLATES if s["id"] == request.scene_type), None)
    if not scene:
        scene = SCENE_TEMPLATES[0]  # Default to studio

    scene_prompt = request.custom_prompt or scene["prompt"]

    try:
        # Use rescue service for T2I generation (Wan primary, fal.ai rescue)
        rescue_service = get_rescue_service()
        full_prompt = f"Product photography, {scene_prompt}, professional quality"
        result = await rescue_service.generate_image(
            prompt=full_prompt,
            width=1024,
            height=1024
        )

        if result.get("success"):
            image_url = result.get("image_url")
            images = result.get("images", [])
            return ToolResponse(
                success=True,
                result_url=image_url or (images[0]["url"] if images else None),
                results=images,
                credits_used=10,
                message="Product scene generated successfully"
            )
        else:
            return ToolResponse(
                success=False,
                message=result.get("error", "Scene generation failed")
            )
    except Exception as e:
        logger.error(f"Product scene error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Tool 3: AI Try-On
# ============================================================================

@router.post("/try-on", response_model=ToolResponse)
async def ai_try_on(
    request: TryOnRequest,
    current_user=Depends(get_current_user_optional)
):
    """
    Virtual try-on - place garment on model.
    Uses face/body swap technology.

    Credits: 15 per generation
    """
    try:
        # Get model image URL
        if request.model_image_url:
            model_url = str(request.model_image_url)
        elif request.model_id:
            model = next((m for m in TRYON_MODELS if m["id"] == request.model_id), None)
            if not model:
                raise HTTPException(status_code=400, detail=f"Invalid model_id: {request.model_id}")
            model_url = model["preview_url"]
        else:
            # Use default female model
            model_url = TRYON_MODELS[0]["preview_url"]

        # Use ProviderRouter for try-on effect
        router = get_provider_router()
        result = await router.route(
            TaskType.T2I,
            {
                "prompt": f"Virtual try-on of garment on model",
                "image_url": str(request.garment_image_url),
                "reference_url": model_url
            }
        )

        output_url = result.get("image_url") or result.get("output_url")
        if output_url:
            return ToolResponse(
                success=True,
                result_url=output_url,
                credits_used=15,
                message="Try-on generated successfully"
            )
        else:
            return ToolResponse(
                success=False,
                message=result.get("error", "Try-on generation failed")
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Try-on error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Tool 4: Room Redesign
# ============================================================================

@router.post("/room-redesign", response_model=ToolResponse)
async def room_redesign(
    request: RoomRedesignRequest,
    current_user=Depends(get_current_user_optional)
):
    """
    Transform room interior style.
    Converts empty/bare rooms to furnished designs.

    Styles: modern, nordic, japanese, industrial, minimalist, luxury, bohemian, coastal
    Credits: 20 per generation
    """
    # Get interior style
    interior = next((s for s in INTERIOR_STYLES if s["id"] == request.style), None)
    if not interior:
        interior = INTERIOR_STYLES[0]  # Default to modern

    style_prompt = request.custom_prompt or interior["prompt"]

    try:
        # Use ProviderRouter for interior design
        router = get_provider_router()
        result = await router.route(
            TaskType.INTERIOR,
            {
                "image_url": str(request.room_image_url),
                "prompt": style_prompt,
                "style": request.style
            }
        )

        output_url = result.get("image_url") or result.get("output_url")
        if output_url:
            return ToolResponse(
                success=True,
                result_url=output_url,
                credits_used=20,
                message=f"Room redesigned to {interior['name']} style"
            )
        else:
            return ToolResponse(
                success=False,
                message=result.get("error", "Room redesign failed")
            )
    except Exception as e:
        logger.error(f"Room redesign error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Tool 5: Short Video
# ============================================================================

@router.post("/short-video", response_model=ToolResponse)
async def generate_short_video(
    request: ShortVideoRequest,
    current_user=Depends(get_current_user_optional)
):
    """
    Generate short video from image.
    Optionally apply style and add TTS narration.

    Credits: 25-35 (varies by features used)
    """
    try:
        credits_used = 25

        # Generate motion video with rescue service (Wan primary, fal.ai rescue)
        rescue_service = get_rescue_service()
        result = await rescue_service.generate_video(
            image_url=str(request.image_url),
            prompt="Natural camera motion, smooth animation",
            length=5
        )

        if not result.get("success"):
            return ToolResponse(
                success=False,
                message=result.get("error", "Video generation failed")
            )

        video_url = result.get("video_url")

        # Optional: Apply style transformation with ProviderRouter V2V
        if request.style:
            style_prompt = get_style_prompt(request.style)
            if style_prompt:
                router = get_provider_router()
                style_result = await router.route(
                    TaskType.V2V,
                    {
                        "video_url": video_url,
                        "prompt": style_prompt
                    }
                )
                output_url = style_result.get("video_url") or style_result.get("output_url")
                if output_url:
                    video_url = output_url
                    credits_used += 5

        # TODO: Add TTS if script is provided
        # if request.script and request.voice_id:
        #     tts_result = await tts_service.generate(request.script, request.voice_id)
        #     # Merge audio with video
        #     credits_used += 5

        return ToolResponse(
            success=True,
            result_url=video_url,
            credits_used=credits_used,
            message="Short video generated successfully"
        )

    except Exception as e:
        logger.error(f"Short video error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Tool 6: AI Avatar
# ============================================================================

@router.post("/avatar", response_model=ToolResponse)
async def generate_avatar_video(
    request: AvatarRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional)
):
    """
    Generate AI Avatar video from photo with lip sync.
    Transforms a headshot into a talking avatar video.

    Uses A2E.ai API for avatar generation with native lip-sync.
    After generation, the result is saved to material DB for demo examples.

    Supported languages: 'en' (English), 'zh-TW' (Traditional Chinese)
    Credits: 30 per generation
    """
    from app.models.material import Material, ToolType, MaterialSource, MaterialStatus

    try:
        # Validate language
        if request.language not in ["en", "zh-TW", "ja", "ko"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language: {request.language}. Supported: en, zh-TW, ja, ko"
            )

        # Validate duration
        if request.duration < 5 or request.duration > 120:
            raise HTTPException(
                status_code=400,
                detail="Duration must be between 5 and 120 seconds"
            )

        avatar_service = get_a2e_service()

        # Call A2E.ai API to generate avatar
        logger.info(f"Calling A2E.ai Avatar API for user request: {request.script[:50]}...")

        result = await avatar_service.generate_and_wait(
            image_url=str(request.image_url),
            script=request.script,
            language=request.language,
            voice_id=request.voice_id,
            duration=request.duration,
            timeout=300,
            save_locally=True
        )

        if result.get("success"):
            video_url = result.get("video_url")

            # Save to material DB for demo examples
            try:
                # Determine topic based on script content (simple heuristic)
                topic = "social_media"  # Default
                script_lower = request.script.lower()
                if any(word in script_lower for word in ["brand", "product", "company", "品牌", "公司"]):
                    topic = "spokesperson"
                elif any(word in script_lower for word in ["feature", "design", "功能", "設計", "產品"]):
                    topic = "product_intro"
                elif any(word in script_lower for word in ["help", "support", "question", "幫助", "服務", "問題"]):
                    topic = "customer_service"

                material = Material(
                    tool_type=ToolType.AI_AVATAR,
                    topic=topic,
                    language=request.language,
                    tags=[topic, "ai_avatar", request.language, "user"],
                    source=MaterialSource.USER,
                    status=MaterialStatus.PENDING,  # User content needs review
                    prompt=request.script,
                    prompt_enhanced=request.script,
                    input_image_url=str(request.image_url),
                    generation_steps=[{
                        "step": 1,
                        "api": "a2e-avatar",
                        "action": "photo_to_avatar",
                        "language": request.language,
                        "input": {"script": request.script, "image": str(request.image_url)},
                        "result_url": video_url,
                        "cost": 0.10
                    }],
                    result_video_url=video_url,
                    generation_cost_usd=0.10,
                    quality_score=0.8,
                    is_active=True
                )

                # Set language-specific title
                if request.language == "zh-TW":
                    material.title_zh = request.script[:100]
                    material.title_en = f"User Avatar: {topic}"
                else:
                    material.title_en = request.script[:100]

                db.add(material)
                await db.commit()

                logger.info(f"User avatar saved to material DB: {material.id}")

            except Exception as db_error:
                logger.error(f"Failed to save avatar to DB: {db_error}")
                # Don't fail the request if DB save fails

            return ToolResponse(
                success=True,
                result_url=video_url,
                credits_used=30,
                message=f"Avatar video generated successfully in {request.language}"
            )
        else:
            return ToolResponse(
                success=False,
                message=result.get("error", "Avatar generation failed")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Avatar generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/avatar/voices")
async def get_avatar_voices(
    language: Optional[str] = None
):
    """
    Get available avatar voices.
    Filter by language: 'en', 'zh-TW', 'ja', 'ko'
    """
    if language and language in A2E_VOICES:
        return A2E_VOICES[language]
    return A2E_VOICES


# ============================================================================
# Template & Resource Endpoints
# ============================================================================

@router.get("/templates/scenes")
async def get_scene_templates():
    """Get available scene templates for Product Scene tool"""
    return SCENE_TEMPLATES


@router.get("/templates/interior-styles")
async def get_interior_styles():
    """Get available interior styles for Room Redesign tool"""
    return INTERIOR_STYLES


@router.get("/models/list")
async def get_tryon_models(
    gender: Optional[str] = None,
    body_type: Optional[str] = None
):
    """Get available models for AI Try-On tool"""
    models = TRYON_MODELS
    if gender:
        models = [m for m in models if m["gender"] == gender]
    if body_type:
        models = [m for m in models if m["body_type"] == body_type]
    return models


@router.get("/voices/list")
async def get_tts_voices(
    language: Optional[str] = None,
    gender: Optional[str] = None
):
    """Get available TTS voices for Short Video tool"""
    voices = TTS_VOICES
    if language:
        voices = [v for v in voices if v["language"].startswith(language)]
    if gender:
        voices = [v for v in voices if v["gender"] == gender]
    return voices


@router.get("/styles")
async def get_video_styles():
    """Get available video styles (unified with effects API)"""
    return VIDGO_STYLES
