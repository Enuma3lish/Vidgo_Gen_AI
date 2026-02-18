"""Social media sharing endpoints."""
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.social_share import SocialShareService, SocialPlatform

router = APIRouter()


class ShareLinkRequest(BaseModel):
    generation_id: str
    platform: str
    caption: Optional[str] = None


class ShareLinkResponse(BaseModel):
    platform: str
    share_url: str
    content_url: str
    caption: str
    requires_manual: bool


@router.post("/share-link", response_model=ShareLinkResponse)
async def create_share_link(
    request: ShareLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate a social media share link for a generation result."""
    # Look up the generation result
    from app.models.user_generation import UserGeneration
    result = await db.execute(
        select(UserGeneration).where(
            UserGeneration.id == request.generation_id,
            UserGeneration.user_id == current_user.id
        )
    )
    generation = result.scalar_one_or_none()
    if not generation:
        raise HTTPException(status_code=404, detail="Generation not found")

    # Get the content URL (prefer video, fallback to image)
    content_url = generation.result_video_url or generation.result_image_url
    if not content_url:
        raise HTTPException(status_code=400, detail="No content URL available for sharing")

    # Validate platform
    try:
        platform = SocialPlatform(request.platform)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid platform. Choose from: {', '.join(p.value for p in SocialPlatform)}"
        )

    service = SocialShareService()
    share_result = service.generate_share_url(platform, content_url, request.caption)
    return share_result


@router.get("/platforms")
async def list_platforms():
    """List all available social media platforms for sharing."""
    return {
        "platforms": [
            {"id": "facebook", "name": "Facebook", "icon": "facebook", "supports_direct_share": True},
            {"id": "twitter", "name": "Twitter / X", "icon": "twitter", "supports_direct_share": True},
            {"id": "line", "name": "LINE", "icon": "line", "supports_direct_share": True},
            {"id": "tiktok", "name": "TikTok", "icon": "tiktok", "supports_direct_share": False},
            {"id": "instagram", "name": "Instagram", "icon": "instagram", "supports_direct_share": False},
        ]
    }
