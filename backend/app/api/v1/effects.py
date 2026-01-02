"""
VidGo Effects API Endpoints.

White-labeled GoEnhance services:
- VidGo Style Effects (style transfer)
- VidGo HD Enhance (4K upscale)
- VidGo Video Pro (video enhancement)

Access: Subscribers only (Starter/Pro/Pro+)
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.services.effects_service import VidGoEffectsService, VIDGO_STYLES

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get available VidGo style effects.

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Apply style effect to an image.

    **Requires:** Starter, Pro, or Pro+ subscription
    **Credits:** 8 points per use
    """
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

    return ApplyStyleResponse(
        success=True,
        output_url=result.get("output_url"),
        style=result.get("style"),
        credits_used=result.get("credits_used")
    )


@router.post("/hd-enhance", response_model=HDEnhanceResponse)
async def hd_enhance(
    request: HDEnhanceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upscale image to 4K resolution.

    **Requires:** Starter, Pro, or Pro+ subscription
    **Credits:** 10 points per use
    """
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

    return HDEnhanceResponse(
        success=True,
        output_url=result.get("output_url"),
        resolution=result.get("resolution"),
        credits_used=result.get("credits_used")
    )


@router.post("/video-enhance", response_model=VideoEnhanceResponse)
async def video_enhance(
    request: VideoEnhanceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Enhance video quality.

    **Requires:** Pro or Pro+ subscription
    **Credits:** 12 points per use

    Enhancement types:
    - quality: General quality improvement
    - stabilize: Video stabilization
    - denoise: Noise reduction
    """
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

    return VideoEnhanceResponse(
        success=True,
        output_url=result.get("output_url"),
        enhancement=result.get("enhancement"),
        credits_used=result.get("credits_used")
    )
