"""Social media sharing endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.social_share import build_share_url, get_all_share_urls, SUPPORTED_PLATFORMS

router = APIRouter()


class ShareRequest(BaseModel):
    content_url: str
    platform: Optional[str] = None
    caption: Optional[str] = None


class ShareResponse(BaseModel):
    platform: str
    share_url: Optional[str]
    content_url: str
    action: str
    message: Optional[str] = None


@router.post("/share", response_model=ShareResponse)
async def create_share_link(
    request: ShareRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate a share link for a specific platform."""
    if not request.platform:
        raise HTTPException(400, "Platform is required")

    result = build_share_url(request.platform, request.content_url, request.caption)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/share/all")
async def get_all_share_links(
    request: ShareRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate share links for all supported platforms."""
    return {
        "platforms": get_all_share_urls(request.content_url, request.caption),
        "supported_platforms": SUPPORTED_PLATFORMS
    }


@router.get("/platforms")
async def list_platforms():
    """List all supported social media platforms."""
    return {"platforms": SUPPORTED_PLATFORMS}
