"""
ARQ Worker for Background Tasks
Handles scheduled demo regeneration and cleanup.

Usage:
    arq app.worker.WorkerSettings
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.services.demo_service import get_demo_service

logger = logging.getLogger(__name__)
settings = get_settings()


# Database session for worker
async def get_db_session() -> AsyncSession:
    """Create database session for worker tasks"""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


# =============================================================================
# SCHEDULED TASKS
# =============================================================================

async def regenerate_demos_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Daily task to regenerate demo images.
    Runs every 24 hours to refresh demos with new styles.
    """
    logger.info("Starting daily demo regeneration task")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as db:
            demo_service = get_demo_service()

            # First cleanup expired demos
            cleaned = await demo_service.cleanup_expired_demos(db)
            logger.info(f"Cleaned up {cleaned} expired demos")

            # Regenerate new demos
            results = await demo_service.regenerate_demos(
                db=db,
                count_per_category=15,  # 15 topics per category
                styles_per_topic=2      # 2 different styles per topic
            )

            return {
                "status": "completed",
                "cleaned_up": cleaned,
                "regeneration": results
            }

    except Exception as e:
        logger.error(f"Demo regeneration failed: {e}")
        return {"status": "failed", "error": str(e)}

    finally:
        await engine.dispose()


async def cleanup_expired_demos_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hourly task to cleanup expired demos.
    More frequent than regeneration to keep DB clean.
    """
    logger.info("Starting demo cleanup task")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as db:
            demo_service = get_demo_service()
            cleaned = await demo_service.cleanup_expired_demos(db)

            return {"status": "completed", "cleaned_up": cleaned}

    except Exception as e:
        logger.error(f"Demo cleanup failed: {e}")
        return {"status": "failed", "error": str(e)}

    finally:
        await engine.dispose()


async def health_check_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Simple health check task"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


# =============================================================================
# ON-DEMAND TASKS (called via API)
# =============================================================================

async def generate_single_demo_task(
    ctx: Dict[str, Any],
    prompt: str,
    style: str = None
) -> Dict[str, Any]:
    """
    Generate a single demo on demand.
    Called when user prompt doesn't match any existing demo.
    """
    logger.info(f"Generating on-demand demo: {prompt[:50]}...")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as db:
            demo_service = get_demo_service()
            result = await demo_service.get_or_create_demo(
                db=db,
                prompt=prompt,
                preferred_style=style
            )
            return result

    except Exception as e:
        logger.error(f"On-demand demo generation failed: {e}")
        return {"status": "failed", "error": str(e)}

    finally:
        await engine.dispose()


# =============================================================================
# WORKER SETTINGS
# =============================================================================

class WorkerSettings:
    """ARQ Worker configuration"""

    # Redis connection
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    # Available functions
    functions = [
        regenerate_demos_task,
        cleanup_expired_demos_task,
        health_check_task,
        generate_single_demo_task,
    ]

    # Cron jobs (scheduled tasks)
    cron_jobs = [
        # Daily demo regeneration at 3:00 AM UTC
        cron(
            regenerate_demos_task,
            hour=3,
            minute=0,
            run_at_startup=False
        ),
        # Hourly cleanup of expired demos
        cron(
            cleanup_expired_demos_task,
            minute=30,  # Run at :30 every hour
            run_at_startup=True  # Run once on startup
        ),
        # Health check every 5 minutes
        cron(
            health_check_task,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            run_at_startup=True
        ),
    ]

    # Worker settings
    max_jobs = 3
    job_timeout = 600  # 10 minutes max per job
    keep_result = 3600  # Keep results for 1 hour
    health_check_interval = 30

    # Logging
    @staticmethod
    async def on_startup(ctx: Dict[str, Any]) -> None:
        logger.info("ARQ Worker started")

    @staticmethod
    async def on_shutdown(ctx: Dict[str, Any]) -> None:
        logger.info("ARQ Worker shutting down")
