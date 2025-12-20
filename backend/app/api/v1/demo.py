"""
Demo Video API Endpoints
Smart Demo Engine for showcasing AI video generation
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.demo import DemoVideo, DemoCategory
from app.schemas.demo import (
    DemoSearchRequest,
    DemoSearchResponse,
    DemoVideoResponse,
    DemoCategory as DemoCategorySchema,
)
from app.schemas.moderation import ModerationResult
from app.services.demo import get_demo_service
from app.services.moderation import get_moderation_service

router = APIRouter()


@router.post("/search", response_model=DemoSearchResponse)
async def search_demos(
    request: DemoSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Search for demo videos matching the user's prompt.
    Uses Smart Demo Engine with keyword matching and scoring.
    """
    # First, moderate the prompt
    moderation_service = get_moderation_service()
    moderation_result = await moderation_service.moderate(request.prompt)

    if not moderation_result.is_safe:
        raise HTTPException(
            status_code=400,
            detail=f"Content not allowed: {moderation_result.reason}"
        )

    # Search for matching demos
    demo_service = get_demo_service()
    results = await demo_service.search_demos(
        db=db,
        prompt=request.prompt,
        category_slug=request.category,
        style=request.style,
        limit=request.limit
    )

    return DemoSearchResponse(
        results=results,
        total_count=len(results),
        query_prompt=request.prompt
    )


@router.get("/featured", response_model=List[DemoVideoResponse])
async def get_featured_demos(
    limit: int = Query(default=6, ge=1, le=20),
    db: AsyncSession = Depends(get_db)
):
    """
    Get featured demo videos for homepage showcase.
    """
    demo_service = get_demo_service()
    demos = await demo_service.get_featured_demos(db, limit=limit)
    return demos


@router.get("/categories", response_model=List[DemoCategorySchema])
async def get_demo_categories(
    db: AsyncSession = Depends(get_db)
):
    """
    Get all demo categories.
    """
    query = (
        select(DemoCategory)
        .where(DemoCategory.is_active == True)
        .order_by(DemoCategory.sort_order)
    )
    result = await db.execute(query)
    categories = result.scalars().all()

    return [
        DemoCategorySchema(
            id=cat.id,
            name=cat.name,
            slug=cat.slug,
            description=cat.description,
            icon=cat.icon,
            sort_order=cat.sort_order,
            is_active=cat.is_active,
            created_at=cat.created_at
        )
        for cat in categories
    ]


@router.get("/category/{slug}", response_model=List[DemoVideoResponse])
async def get_demos_by_category(
    slug: str,
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get demo videos by category slug.
    """
    # Verify category exists
    cat_query = select(DemoCategory).where(
        DemoCategory.slug == slug,
        DemoCategory.is_active == True
    )
    cat_result = await db.execute(cat_query)
    category = cat_result.scalar_one_or_none()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Get demos in category
    query = (
        select(DemoVideo)
        .where(DemoVideo.category_id == category.id)
        .where(DemoVideo.is_active == True)
        .order_by(DemoVideo.popularity_score.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    demos = result.scalars().all()

    return [
        DemoVideoResponse(
            id=demo.id,
            title=demo.title,
            description=demo.description,
            prompt=demo.prompt,
            keywords=demo.keywords or [],
            resolution=demo.resolution,
            style=demo.style,
            video_url_watermarked=demo.video_url_watermarked,
            thumbnail_url=demo.thumbnail_url,
            duration_seconds=demo.duration_seconds,
            category=DemoCategorySchema(
                id=category.id,
                name=category.name,
                slug=category.slug,
                description=category.description,
                icon=category.icon,
                sort_order=category.sort_order,
                is_active=category.is_active,
                created_at=category.created_at
            ),
            is_featured=demo.is_featured,
            popularity_score=demo.popularity_score,
            created_at=demo.created_at
        )
        for demo in demos
    ]


@router.get("/{demo_id}", response_model=DemoVideoResponse)
async def get_demo_by_id(
    demo_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific demo video by ID.
    Also records the view for popularity tracking.
    """
    from uuid import UUID

    try:
        demo_uuid = UUID(demo_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid demo ID format")

    query = (
        select(DemoVideo)
        .where(DemoVideo.id == demo_uuid)
        .where(DemoVideo.is_active == True)
        .options(selectinload(DemoVideo.category))
    )
    result = await db.execute(query)
    demo = result.scalar_one_or_none()

    if not demo:
        raise HTTPException(status_code=404, detail="Demo not found")

    # Record view
    demo_service = get_demo_service()
    await demo_service.record_view(
        db=db,
        demo_id=demo_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )

    category_schema = None
    if demo.category:
        category_schema = DemoCategorySchema(
            id=demo.category.id,
            name=demo.category.name,
            slug=demo.category.slug,
            description=demo.category.description,
            icon=demo.category.icon,
            sort_order=demo.category.sort_order,
            is_active=demo.category.is_active,
            created_at=demo.category.created_at
        )

    return DemoVideoResponse(
        id=demo.id,
        title=demo.title,
        description=demo.description,
        prompt=demo.prompt,
        keywords=demo.keywords or [],
        resolution=demo.resolution,
        style=demo.style,
        video_url_watermarked=demo.video_url_watermarked,
        thumbnail_url=demo.thumbnail_url,
        duration_seconds=demo.duration_seconds,
        category=category_schema,
        is_featured=demo.is_featured,
        popularity_score=demo.popularity_score,
        created_at=demo.created_at
    )


@router.post("/moderate")
async def moderate_prompt(
    prompt: str = Query(..., min_length=3, max_length=500)
) -> ModerationResult:
    """
    Check if a prompt passes content moderation.
    Useful for pre-validating prompts before generation.
    """
    moderation_service = get_moderation_service()
    result = await moderation_service.moderate(prompt)
    return result


@router.get("/styles", response_model=List[str])
async def get_available_styles(
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of available video styles.
    """
    query = (
        select(DemoVideo.style)
        .where(DemoVideo.is_active == True)
        .where(DemoVideo.style.isnot(None))
        .distinct()
    )
    result = await db.execute(query)
    styles = [row[0] for row in result.fetchall() if row[0]]

    return styles
