"""
VidGo Effects API Endpoints.

White-labeled PiAPI services:
- VidGo Style Effects (style transfer)
- VidGo HD Enhance (4K upscale)
- VidGo Video Pro (video enhancement)

Access:
- GET /styles: Open to all users (browse available styles)
- POST endpoints: Subscribers only (Starter/Pro/Pro+)
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user, get_current_user_optional, get_redis, is_subscribed_user
from app.models.user import User
from app.models.material import Material, ToolType, MaterialSource, MaterialStatus
from app.models.user_generation import UserGeneration
from app.services.effects_service import VidGoEffectsService, VIDGO_STYLES
from app.services.demo_cache_service import DemoCacheService
from sqlalchemy import select, func
import logging
import hashlib

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/effects", tags=["effects"])


# ============ Schemas ============

class StyleInfo(BaseModel):
    id: str
    name: str
    name_zh: str
    category: str
    preview_url: str


class ApplyStyleRequest(BaseModel):
    image_url: str = Field(..., description="Publicly reachable source image URL for style transfer.")
    style_id: str = Field(..., description="Target style preset ID, for example anime, cartoon, cinematic, product, or watercolor.")
    intensity: float = Field(1.0, ge=0.0, le=1.0, description="Style strength from 0.0 to 1.0. Higher values apply a more visible effect.")


class ApplyStyleResponse(BaseModel):
    success: bool
    output_url: Optional[str] = None
    style: Optional[str] = None
    credits_used: Optional[int] = None
    error: Optional[str] = None
    # Demo before/after pair
    is_demo: bool = False
    demo_input_url: Optional[str] = None
    demo_prompt: Optional[str] = None


class HDEnhanceRequest(BaseModel):
    image_url: str = Field(..., description="Publicly reachable source image URL to upscale.")
    target_resolution: str = Field("4k", description="Requested output resolution. Supported values are 2k and 4k.")


class HDEnhanceResponse(BaseModel):
    success: bool
    output_url: Optional[str] = None
    resolution: Optional[str] = None
    credits_used: Optional[int] = None
    error: Optional[str] = None
    is_demo: bool = False
    demo_input_url: Optional[str] = None


class VideoEnhanceRequest(BaseModel):
    video_url: str = Field(..., description="Publicly reachable source video URL to enhance.")
    enhancement_type: str = Field("quality", description="Enhancement mode: quality, stabilize, or denoise.")


class VideoEnhanceResponse(BaseModel):
    success: bool
    output_url: Optional[str] = None
    enhancement: Optional[str] = None
    credits_used: Optional[int] = None
    error: Optional[str] = None
    is_demo: bool = False
    demo_input_url: Optional[str] = None


# ============ Endpoints ============

@router.get("/styles", response_model=List[StyleInfo])
async def get_available_styles(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get available VidGo style effects. Open to all users.

    Categories:
    - artistic: Anime, Ghibli, Cartoon, 3D, Clay, Pixel, Oil Painting, Watercolor, Sketch
    - modern: Cyberpunk, Vintage, Pop Art
    - professional: Cinematic, Product

    Returns array of styles directly for frontend compatibility.
    """
    effects_service = VidGoEffectsService(db)
    styles = effects_service.get_available_styles(category)

    # Return array directly (not wrapped in object) for frontend compatibility
    return [
        StyleInfo(
            id=s["id"],
            name=s["name"],
            name_zh=s["name_zh"],
            category=s["category"],
            preview_url=s["preview_url"]
        )
        for s in styles
    ]


@router.post("/apply-style", response_model=ApplyStyleResponse)
async def apply_style_effect(
    request: ApplyStyleRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Apply style effect to an image.

    - **Subscribers:** Calls real API, saves to UserGeneration, no watermark.
    - **Demo users:** Returns a pre-generated Material DB result (watermarked).

    **Credits:** 8 points per use (subscribers only)
    """
    # Demo/free user path: cache-first with on-demand generation keyed on
    # (tool, style_id, user-picked input_url). When the user passes an
    # `image_url` it flows straight through — cache miss triggers a real API
    # call against their chosen input, and the result is persisted under the
    # same lookup_hash so the next identical (input, style) request hits cache.
    if not is_subscribed_user(current_user):
        try:
            redis = await get_redis()
        except Exception:
            redis = None
        cache_service = DemoCacheService(db, redis)
        # Resolve /static/ paths to public URLs so the hash matches whatever
        # the cached material stored.
        import os as _os
        user_input_url = request.image_url
        if user_input_url and user_input_url.startswith("/static/"):
            pub = _os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
            if pub:
                user_input_url = f"{pub}{user_input_url}"
        # Resolve style_id → style_prompt so the effect_prompt goes into the
        # cache key and the real API call.
        from app.services.effects_service import get_style_prompt
        style_prompt = get_style_prompt(request.style_id) if request.style_id else None
        demo = await cache_service.get_or_generate(
            ToolType.EFFECT,
            topic=request.style_id,
            input_image_url=user_input_url,
            effect_prompt=style_prompt,
        )
        if not demo:
            raise HTTPException(status_code=503, detail="Demo generation temporarily unavailable. Please try again.")
        return ApplyStyleResponse(
            success=True,
            output_url=demo["result_url"],
            style=request.style_id,
            credits_used=0,
            is_demo=True,
            demo_input_url=demo.get("input_image_url"),
            demo_prompt=demo.get("prompt"),
        )

    # Subscriber path: call real API
    effects_service = VidGoEffectsService(db)

    # Resolve /static/ paths to public URLs for external AI APIs
    import os as _os
    resolved_url = request.image_url
    if resolved_url.startswith("/static/"):
        pub = _os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
        if pub:
            resolved_url = f"{pub}{resolved_url}"

    success, result = await effects_service.apply_style(
        user_id=str(current_user.id),
        image_url=resolved_url,
        style_id=request.style_id,
        intensity=request.intensity
    )

    if not success:
        error_msg = result.get("error", "Failed to apply style")
        # Access-related errors → 403; processing errors → 500
        if any(kw in error_msg.lower() for kw in ("subscription", "insufficient", "plan", "not found")):
            code = status.HTTP_403_FORBIDDEN
        else:
            code = status.HTTP_500_INTERNAL_SERVER_ERROR
        raise HTTPException(status_code=code, detail=error_msg)

    # Save to UserGeneration
    generation = UserGeneration(
        user_id=current_user.id,
        tool_type=ToolType.EFFECT,
        input_image_url=request.image_url,
        input_params={"style_id": request.style_id, "intensity": request.intensity},
        result_image_url=result.get("output_url"),
        credits_used=result.get("credits_used", 8),
    )
    db.add(generation)

    # Recycle for demo gallery (admin review required)
    output_url = result.get("output_url")
    if output_url:
        try:
            existing_count = await db.execute(
                select(func.count()).select_from(Material).where(
                    Material.tool_type == ToolType.EFFECT,
                    Material.topic == request.style_id,
                    Material.source == MaterialSource.USER,
                )
            )
            if (existing_count.scalar() or 0) < 10:
                lookup_content = f"effect:{request.image_url}:{request.style_id}:{generation.id}"
                lookup_hash = hashlib.sha256(lookup_content.encode()).hexdigest()[:64]
                # Check for existing hash first
                existing_mat = await db.execute(
                    select(Material.id).where(Material.lookup_hash == lookup_hash)
                )
                if not existing_mat.scalar_one_or_none():
                    material = Material(
                        lookup_hash=lookup_hash,
                        tool_type=ToolType.EFFECT,
                        topic=request.style_id,
                        prompt=f"User effect: {request.style_id}",
                        effect_prompt=request.style_id,
                        input_image_url=request.image_url,
                        result_image_url=output_url,
                        result_watermarked_url=output_url,
                        source=MaterialSource.USER,
                        status=MaterialStatus.PENDING,
                        is_active=False,
                        input_params={"style_id": request.style_id, "intensity": request.intensity},
                    )
                    db.add(material)
        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            logger.debug(f"[Recycle] Skip effect: {e}")

    await db.commit()

    return ApplyStyleResponse(
        success=True,
        output_url=result.get("output_url"),
        style=result.get("style"),
        credits_used=result.get("credits_used")
    )


@router.post("/hd-enhance", response_model=HDEnhanceResponse)
async def hd_enhance(
    request: HDEnhanceRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Upscale image to 4K resolution.

    - **Subscribers:** Calls real API, saves to UserGeneration.
    - **Demo users:** Returns 403 (no pre-generated HD enhance examples).

    **Credits:** 10 points per use (subscribers only)
    """
    if not is_subscribed_user(current_user):
        raise HTTPException(status_code=403, detail="Active subscription required for HD enhance.")

    effects_service = VidGoEffectsService(db)

    success, result = await effects_service.hd_enhance(
        user_id=str(current_user.id),
        image_url=request.image_url,
        target_resolution=request.target_resolution
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result.get("error", "Failed to enhance image")
        )

    # Save to UserGeneration
    generation = UserGeneration(
        user_id=current_user.id,
        tool_type=ToolType.EFFECT,
        input_image_url=request.image_url,
        input_params={"target_resolution": request.target_resolution, "action": "hd_enhance"},
        result_image_url=result.get("output_url"),
        credits_used=result.get("credits_used", 10),
    )
    db.add(generation)
    await db.commit()

    return HDEnhanceResponse(
        success=True,
        output_url=result.get("output_url"),
        resolution=result.get("resolution"),
        credits_used=result.get("credits_used")
    )


@router.post("/video-enhance", response_model=VideoEnhanceResponse)
async def video_enhance(
    request: VideoEnhanceRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Enhance video quality.

    - **Subscribers:** Calls real API, saves to UserGeneration.
    - **Demo users:** Returns 403 (no pre-generated video enhance examples).

    **Credits:** 12 points per use (subscribers only)

    Enhancement types:
    - quality: General quality improvement
    - stabilize: Video stabilization
    - denoise: Noise reduction
    """
    if not is_subscribed_user(current_user):
        raise HTTPException(status_code=403, detail="Active subscription required for video enhance.")

    effects_service = VidGoEffectsService(db)

    success, result = await effects_service.video_enhance(
        user_id=str(current_user.id),
        video_url=request.video_url,
        enhancement_type=request.enhancement_type
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result.get("error", "Failed to enhance video")
        )

    # Save to UserGeneration
    generation = UserGeneration(
        user_id=current_user.id,
        tool_type=ToolType.EFFECT,
        input_video_url=request.video_url,
        input_params={"enhancement_type": request.enhancement_type, "action": "video_enhance"},
        result_video_url=result.get("output_url"),
        credits_used=result.get("credits_used", 12),
    )
    db.add(generation)
    await db.commit()

    return VideoEnhanceResponse(
        success=True,
        output_url=result.get("output_url"),
        enhancement=result.get("enhancement"),
        credits_used=result.get("credits_used")
    )
