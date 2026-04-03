"""
User Works API Endpoints.

Allows authenticated users to:
- List their generated works (paginated, filterable by tool_type)
- View individual work details (including expiry status)
- Download works (subscribers only, no watermark, within 14-day window)
- Delete works
- View dashboard stats (total works, credits used, by tool type)

Media Retention Policy:
- Media files (result_image_url, result_video_url) are available for 14 days
- After 14 days, media URLs are cleared but the generation record is kept forever
- The record retains: tool_type, input_params, credits_used, created_at, result_metadata
- This lets users see their creation history even after media has expired
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, update
from datetime import datetime, timezone, timedelta

from app.api.deps import get_db, get_current_user, is_subscribed_user
from app.models.user import User
from app.models.user_generation import UserGeneration, MEDIA_RETENTION_DAYS

router = APIRouter()


# ============ Schemas ============

class GenerationItem(BaseModel):
    id: str
    tool_type: str
    input_image_url: Optional[str] = None
    input_text: Optional[str] = None
    result_image_url: Optional[str] = None
    result_video_url: Optional[str] = None
    credits_used: int = 0
    created_at: datetime
    # Expiry fields
    expires_at: Optional[datetime] = None
    media_expired: bool = False
    days_until_expiry: Optional[int] = None
    hours_until_expiry: Optional[int] = None

    class Config:
        from_attributes = True


class GenerationDetail(GenerationItem):
    input_video_url: Optional[str] = None
    input_params: Optional[dict] = None
    result_metadata: Optional[dict] = None


class GenerationListResponse(BaseModel):
    items: List[GenerationItem]
    total: int
    page: int
    per_page: int


class UserStatsResponse(BaseModel):
    total_works: int
    total_credits_used: int
    by_tool_type: dict
    active_works: int       # works with media still available
    expired_works: int      # works where media has expired (record kept)


# ============ Helper ============

def _build_item(g: UserGeneration) -> GenerationItem:
    """Build GenerationItem from ORM object, masking expired media URLs."""
    is_expired = g.is_media_expired
    return GenerationItem(
        id=str(g.id),
        tool_type=g.tool_type.value if hasattr(g.tool_type, 'value') else g.tool_type,
        input_image_url=g.input_image_url,
        input_text=g.input_text,
        # Return None for media URLs if expired (record kept but files gone)
        result_image_url=None if is_expired else g.result_image_url,
        result_video_url=None if is_expired else g.result_video_url,
        credits_used=g.credits_used or 0,
        created_at=g.created_at,
        expires_at=g.expires_at,
        media_expired=is_expired,
        days_until_expiry=g.days_until_expiry,
        hours_until_expiry=g.hours_until_expiry,
    )


def _build_detail(g: UserGeneration) -> GenerationDetail:
    """Build GenerationDetail from ORM object, masking expired media URLs."""
    is_expired = g.is_media_expired
    return GenerationDetail(
        id=str(g.id),
        tool_type=g.tool_type.value if hasattr(g.tool_type, 'value') else g.tool_type,
        input_image_url=g.input_image_url,
        input_video_url=g.input_video_url,
        input_text=g.input_text,
        input_params=g.input_params,          # Always kept
        result_image_url=None if is_expired else g.result_image_url,
        result_video_url=None if is_expired else g.result_video_url,
        result_metadata=g.result_metadata,    # Always kept
        credits_used=g.credits_used or 0,
        created_at=g.created_at,
        expires_at=g.expires_at,
        media_expired=is_expired,
        days_until_expiry=g.days_until_expiry,
        hours_until_expiry=g.hours_until_expiry,
    )


# ============ Endpoints ============

@router.get("/generations", response_model=GenerationListResponse)
async def list_user_generations(
    page: int = 1,
    per_page: int = 20,
    tool_type: Optional[str] = None,
    show_expired: bool = True,   # include expired records (history view)
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List current user's generated works with pagination and optional tool_type filter.

    All records are returned by default (including expired ones for history).
    Set show_expired=false to only show works with active media.

    Expired works have media_expired=true and null result URLs,
    but retain all other metadata (tool_type, input_params, etc.).
    """
    query = select(UserGeneration).where(UserGeneration.user_id == current_user.id)
    count_query = select(func.count(UserGeneration.id)).where(
        UserGeneration.user_id == current_user.id
    )

    if tool_type:
        query = query.where(UserGeneration.tool_type == tool_type)
        count_query = count_query.where(UserGeneration.tool_type == tool_type)

    if not show_expired:
        # Only show works where media is still available
        now = datetime.now(timezone.utc)
        query = query.where(
            (UserGeneration.media_expired == False) &  # noqa: E712
            ((UserGeneration.expires_at == None) | (UserGeneration.expires_at > now))  # noqa: E711
        )
        count_query = count_query.where(
            (UserGeneration.media_expired == False) &  # noqa: E712
            ((UserGeneration.expires_at == None) | (UserGeneration.expires_at > now))  # noqa: E711
        )

    total = await db.scalar(count_query) or 0

    offset = (page - 1) * per_page
    query = query.order_by(desc(UserGeneration.created_at)).offset(offset).limit(per_page)

    result = await db.execute(query)
    generations = result.scalars().all()

    return GenerationListResponse(
        items=[_build_item(g) for g in generations],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/generations/{generation_id}", response_model=GenerationDetail)
async def get_generation_detail(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get details for a single generation belonging to the current user.

    Expired works still return the full record with input_params and result_metadata,
    but result_image_url and result_video_url will be null.
    """
    result = await db.execute(
        select(UserGeneration).where(
            UserGeneration.id == generation_id,
            UserGeneration.user_id == current_user.id,
        )
    )
    generation = result.scalar_one_or_none()

    if not generation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work not found")

    return _build_detail(generation)


@router.get("/generations/{generation_id}/download")
async def download_generation(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download a generation result.

    Requirements:
    - Active subscription (paid member only)
    - Media must not be expired (within 14-day window)

    After 14 days, the media is no longer available for download,
    but the generation record is kept for history purposes.
    """
    if not is_subscribed_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required to download",
        )

    result = await db.execute(
        select(UserGeneration).where(
            UserGeneration.id == generation_id,
            UserGeneration.user_id == current_user.id,
        )
    )
    generation = result.scalar_one_or_none()

    if not generation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work not found")

    # Check media expiry
    if generation.is_media_expired:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "This work's media has expired (14-day retention period). "
                "The generation record is kept for your history, "
                "but the media file is no longer available for download."
            ),
        )

    download_url = generation.result_video_url or generation.result_image_url
    if not download_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No result file available")

    return RedirectResponse(url=download_url)


@router.delete("/generations/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_generation(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a generation record belonging to the current user.
    This permanently removes the record (including history).
    """
    result = await db.execute(
        select(UserGeneration).where(
            UserGeneration.id == generation_id,
            UserGeneration.user_id == current_user.id,
        )
    )
    generation = result.scalar_one_or_none()

    if not generation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work not found")

    await db.delete(generation)
    await db.commit()


@router.get("/dashboard", response_model=UserStatsResponse)
@router.get("/stats", response_model=UserStatsResponse)
async def get_user_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get dashboard stats for the current user:
    - total works (all time)
    - active works (media still available)
    - expired works (record kept, media gone)
    - total credits used
    - breakdown by tool_type
    """
    now = datetime.now(timezone.utc)

    total_works = await db.scalar(
        select(func.count(UserGeneration.id)).where(
            UserGeneration.user_id == current_user.id
        )
    ) or 0

    total_credits = await db.scalar(
        select(func.coalesce(func.sum(UserGeneration.credits_used), 0)).where(
            UserGeneration.user_id == current_user.id
        )
    ) or 0

    # Active works: media_expired=False AND (expires_at is null OR expires_at > now)
    active_works = await db.scalar(
        select(func.count(UserGeneration.id)).where(
            UserGeneration.user_id == current_user.id,
            UserGeneration.media_expired == False,  # noqa: E712
        )
    ) or 0

    expired_works = total_works - active_works

    # Breakdown by tool_type
    breakdown_result = await db.execute(
        select(
            UserGeneration.tool_type,
            func.count(UserGeneration.id).label("count"),
        )
        .where(UserGeneration.user_id == current_user.id)
        .group_by(UserGeneration.tool_type)
    )
    by_tool_type = {
        (row.tool_type.value if hasattr(row.tool_type, 'value') else row.tool_type): row.count
        for row in breakdown_result.all()
    }

    return UserStatsResponse(
        total_works=total_works,
        total_credits_used=total_credits,
        by_tool_type=by_tool_type,
        active_works=active_works,
        expired_works=expired_works,
    )
