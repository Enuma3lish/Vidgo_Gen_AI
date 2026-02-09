"""
VidGo Effects API Endpoints.

White-labeled GoEnhance services:
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

from app.api.deps import get_db, get_current_user, get_current_user_optional, is_subscribed_user
from app.models.user import User
from app.models.material import Material, ToolType
from app.models.user_generation import UserGeneration
from app.services.effects_service import VidGoEffectsService, VIDGO_STYLES
from sqlalchemy import select, func

router = APIRouter(prefix="/effects", tags=["effects"])


# ============ Schemas ============

class StyleInfo(BaseModel):
    id: str
    name: str
    name_zh: str
    category: str
    preview_url: str


class ApplyStyleRequest(BaseModel):
    image_url: str = Field(..., description="URL of the input image")
    style_id: str = Field(..., description="Style effect ID (anime, cartoon, 3d, etc.)")
    intensity: float = Field(1.0, ge=0.0, le=1.0, description="Effect intensity")


class ApplyStyleResponse(BaseModel):
    success: bool
    output_url: Optional[str] = None
    style: Optional[str] = None
    credits_used: Optional[int] = None
    error: Optional[str] = None


class HDEnhanceRequest(BaseModel):
    image_url: str = Field(..., description="URL of the input image")
    target_resolution: str = Field("4k", description="Target resolution (2k or 4k)")


class HDEnhanceResponse(BaseModel):
    success: bool
    output_url: Optional[str] = None
    resolution: Optional[str] = None
    credits_used: Optional[int] = None
    error: Optional[str] = None


class VideoEnhanceRequest(BaseModel):
    video_url: str = Field(..., description="URL of the input video")
    enhancement_type: str = Field("quality", description="Enhancement type: quality, stabilize, denoise")


class VideoEnhanceResponse(BaseModel):
    success: bool
    output_url: Optional[str] = None
    enhancement: Optional[str] = None
    credits_used: Optional[int] = None
    error: Optional[str] = None


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
    # Demo path: return pre-generated material
    if not is_subscribed_user(current_user):
        result = await db.execute(
            select(Material)
            .where(
                Material.tool_type == ToolType.EFFECT,
                Material.topic == request.style_id,
                Material.is_active == True,
            )
            .order_by(func.random())
            .limit(1)
        )
        material = result.scalar_one_or_none()
        if material:
            return ApplyStyleResponse(
                success=True,
                output_url=material.result_watermarked_url or material.result_image_url,
                style=request.style_id,
                credits_used=0,
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required. No demo examples available for this style.",
        )

    # Subscriber path: call real API
    effects_service = VidGoEffectsService(db)

    success, result = await effects_service.apply_style(
        user_id=str(current_user.id),
        image_url=request.image_url,
        style_id=request.style_id,
        intensity=request.intensity
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result.get("error", "Failed to apply style")
        )

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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required for HD enhance.",
        )

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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required for video enhance.",
        )

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
