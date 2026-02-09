"""
User Works API Endpoints.

Allows authenticated users to:
- List their generated works (paginated, filterable by tool_type)
- View individual work details
- Download works (subscribers only, no watermark)
- Delete works
- View dashboard stats (total works, credits used, by tool type)
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime

from app.api.deps import get_db, get_current_user, is_subscribed_user
from app.models.user import User
from app.models.user_generation import UserGeneration
from app.models.material import ToolType

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


# ============ Endpoints ============

@router.get("/generations", response_model=GenerationListResponse)
async def list_user_generations(
    page: int = 1,
    per_page: int = 20,
    tool_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List current user's generated works with pagination and optional tool_type filter.
    """
    query = select(UserGeneration).where(UserGeneration.user_id == current_user.id)
    count_query = select(func.count(UserGeneration.id)).where(
        UserGeneration.user_id == current_user.id
    )

    if tool_type:
        query = query.where(UserGeneration.tool_type == tool_type)
        count_query = count_query.where(UserGeneration.tool_type == tool_type)

    total = await db.scalar(count_query) or 0

    offset = (page - 1) * per_page
    query = query.order_by(desc(UserGeneration.created_at)).offset(offset).limit(per_page)

    result = await db.execute(query)
    generations = result.scalars().all()

    return GenerationListResponse(
        items=[
            GenerationItem(
                id=str(g.id),
                tool_type=g.tool_type.value if hasattr(g.tool_type, 'value') else g.tool_type,
                input_image_url=g.input_image_url,
                input_text=g.input_text,
                result_image_url=g.result_image_url,
                result_video_url=g.result_video_url,
                credits_used=g.credits_used or 0,
                created_at=g.created_at,
            )
            for g in generations
        ],
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

    return GenerationDetail(
        id=str(generation.id),
        tool_type=generation.tool_type.value if hasattr(generation.tool_type, 'value') else generation.tool_type,
        input_image_url=generation.input_image_url,
        input_video_url=generation.input_video_url,
        input_text=generation.input_text,
        input_params=generation.input_params,
        result_image_url=generation.result_image_url,
        result_video_url=generation.result_video_url,
        result_metadata=generation.result_metadata,
        credits_used=generation.credits_used or 0,
        created_at=generation.created_at,
    )


@router.get("/generations/{generation_id}/download")
async def download_generation(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download a generation result. Subscribers only (no watermark).
    """
    if not is_subscribed_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required to download without watermark",
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
    Delete a generation belonging to the current user.
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


@router.get("/stats", response_model=UserStatsResponse)
async def get_user_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get dashboard stats for the current user: total works, total credits used, breakdown by tool_type.
    """
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
    )
