"""
Media Cleanup Service

Handles the 14-day media retention policy for user generations.

Policy:
- When a generation is created, expires_at is set to created_at + 14 days
- After 14 days, result_image_url and result_video_url are cleared (set to None)
- media_expired flag is set to True
- All other fields (tool_type, input_params, result_metadata, credits_used, etc.)
  are kept permanently for generation history

This service is called:
1. By a scheduled background task (every hour via APScheduler or cron)
2. On-demand via the admin API endpoint

Usage:
    from app.services.media_cleanup_service import run_media_cleanup
    expired_count = await run_media_cleanup(db)
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.user_generation import UserGeneration

logger = logging.getLogger(__name__)


async def run_media_cleanup(db: AsyncSession) -> dict:
    """
    Find all generations past their expires_at date and clear their media URLs.

    Returns a dict with:
    - expired_count: number of records processed
    - already_expired: records already flagged (skipped)
    """
    now = datetime.now(timezone.utc)

    # Find generations that have passed their expiry date but haven't been cleaned yet
    result = await db.execute(
        select(UserGeneration).where(
            UserGeneration.media_expired == False,  # noqa: E712
            UserGeneration.expires_at != None,       # noqa: E711
            UserGeneration.expires_at <= now,
        )
    )
    to_expire = result.scalars().all()

    expired_count = 0
    for generation in to_expire:
        # Clear media URLs but keep all other data
        generation.result_image_url = None
        generation.result_video_url = None
        generation.media_expired = True
        expired_count += 1
        logger.info(
            f"Expired media for generation {generation.id} "
            f"(user={generation.user_id}, tool={generation.tool_type}, "
            f"expired_at={generation.expires_at})"
        )

    if expired_count > 0:
        await db.commit()
        logger.info(f"Media cleanup complete: {expired_count} generations expired")
    
    return {
        "expired_count": expired_count,
        "processed_at": now.isoformat(),
    }


async def set_expiry_for_new_generation(generation: UserGeneration) -> None:
    """
    Set the expiry date for a newly created generation.
    Call this when saving a new generation to the database.
    """
    generation.set_expiry()
    logger.debug(
        f"Set expiry for generation {generation.id}: expires_at={generation.expires_at}"
    )


async def get_expiry_stats(db: AsyncSession) -> dict:
    """
    Get statistics about media expiry across all users.
    Used by admin dashboard.
    """
    from sqlalchemy import func
    now = datetime.now(timezone.utc)

    total = await db.scalar(select(func.count(UserGeneration.id))) or 0

    active = await db.scalar(
        select(func.count(UserGeneration.id)).where(
            UserGeneration.media_expired == False,  # noqa: E712
        )
    ) or 0

    expired = await db.scalar(
        select(func.count(UserGeneration.id)).where(
            UserGeneration.media_expired == True,  # noqa: E712
        )
    ) or 0

    # Expiring soon (within 3 days)
    expiring_soon = await db.scalar(
        select(func.count(UserGeneration.id)).where(
            UserGeneration.media_expired == False,  # noqa: E712
            UserGeneration.expires_at != None,       # noqa: E711
            UserGeneration.expires_at > now,
            UserGeneration.expires_at <= now.replace(day=now.day + 3)
            if now.day + 3 <= 28
            else UserGeneration.expires_at > now,
        )
    ) or 0

    return {
        "total_generations": total,
        "active_media": active,
        "expired_media": expired,
        "expiring_soon_3days": expiring_soon,
        "checked_at": now.isoformat(),
    }
