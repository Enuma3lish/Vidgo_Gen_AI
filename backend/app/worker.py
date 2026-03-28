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
from app.services.credit_service import CreditService

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


async def auto_renew_subscriptions_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Daily task to auto-renew expired subscriptions.

    Checks for active subscriptions where:
    - auto_renew = True
    - plan_expires_at <= now

    For each, re-allocates monthly credits and extends the subscription period.
    """
    logger.info("Starting auto-renewal check")

    from sqlalchemy import select, and_
    from app.models.user import User
    from app.models.billing import Plan, Subscription, CreditTransaction

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    renewed_count = 0
    error_count = 0

    try:
        async with async_session() as db:
            # Find expired subscriptions with auto_renew=True
            result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.status == "active",
                        Subscription.auto_renew == True,
                        Subscription.end_date <= datetime.utcnow(),
                    )
                )
            )
            subscriptions = result.scalars().all()

            for sub in subscriptions:
                try:
                    user = await db.get(User, sub.user_id)
                    plan = await db.get(Plan, sub.plan_id)

                    if not user or not plan:
                        continue

                    # Extend subscription by 1 month
                    old_end = sub.end_date
                    new_end = old_end + timedelta(days=30)
                    sub.start_date = old_end
                    sub.end_date = new_end

                    # Update user plan dates
                    user.plan_started_at = old_end
                    user.plan_expires_at = new_end

                    # Allocate new monthly credits (old ones expired)
                    credits = plan.monthly_credits or 0
                    if credits > 0:
                        # Expire remaining old subscription credits
                        old_credits = user.subscription_credits or 0
                        if old_credits > 0:
                            expiry_tx = CreditTransaction(
                                user_id=user.id,
                                amount=-old_credits,
                                balance_after=(user.purchased_credits or 0) + (user.bonus_credits or 0) + credits,
                                transaction_type="expiry",
                                description=f"Monthly subscription credits expired — {old_credits} unused",
                            )
                            db.add(expiry_tx)

                        # Allocate fresh credits
                        user.subscription_credits = credits
                        user.credits_reset_at = datetime.utcnow()

                        alloc_tx = CreditTransaction(
                            user_id=user.id,
                            amount=credits,
                            balance_after=(user.purchased_credits or 0) + (user.bonus_credits or 0) + credits,
                            transaction_type="subscription",
                            description=f"Auto-renewal credit allocation — {plan.display_name or plan.name} ({credits} credits)",
                        )
                        db.add(alloc_tx)

                    renewed_count += 1
                    logger.info(f"Auto-renewed subscription for user {user.id}: {plan.name} until {new_end}")

                except Exception as e:
                    logger.error(f"Failed to auto-renew subscription {sub.id}: {e}")
                    error_count += 1

            await db.commit()

        return {
            "status": "completed",
            "renewed": renewed_count,
            "errors": error_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Auto-renewal task failed: {e}")
        return {"status": "failed", "error": str(e)}

    finally:
        await engine.dispose()


# =============================================================================
# CREDIT MANAGEMENT TASKS
# =============================================================================

async def monthly_credit_reset_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Monthly task to reset subscription credits for all active subscribers.
    Runs on the 1st of each month at 00:05 UTC.

    Subscription credits DO NOT carry over — they reset to the plan's monthly_credits.
    Purchased credits and bonus credits are NOT affected.
    """
    logger.info("Starting monthly credit reset task")

    from sqlalchemy import select, and_
    from app.models.user import User
    from app.models.billing import Plan, CreditTransaction

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    reset_count = 0
    error_count = 0

    try:
        async with async_session() as db:
            # Get all active users with a plan
            result = await db.execute(
                select(User).where(
                    and_(
                        User.current_plan_id != None,
                        User.is_active == True,
                    )
                )
            )
            users = result.scalars().all()

            for user in users:
                try:
                    # Get user's plan
                    plan_result = await db.execute(
                        select(Plan).where(Plan.id == user.current_plan_id)
                    )
                    plan = plan_result.scalar_one_or_none()

                    if not plan or not plan.monthly_credits:
                        continue

                    old_credits = user.subscription_credits or 0
                    new_credits = plan.monthly_credits

                    # Reset subscription credits to plan amount
                    user.subscription_credits = new_credits
                    user.credits_reset_at = datetime.utcnow()

                    # Record the reset as a transaction
                    # First record expiry of old credits if any
                    if old_credits > 0:
                        expiry_tx = CreditTransaction(
                            user_id=user.id,
                            amount=-old_credits,
                            balance_after=(user.purchased_credits or 0) + (user.bonus_credits or 0) + new_credits,
                            transaction_type="expiry",
                            description=f"Monthly subscription credit reset — {old_credits} unused credits expired",
                        )
                        db.add(expiry_tx)

                    # Then record the new allocation
                    alloc_tx = CreditTransaction(
                        user_id=user.id,
                        amount=new_credits,
                        balance_after=(user.purchased_credits or 0) + (user.bonus_credits or 0) + new_credits,
                        transaction_type="subscription",
                        description=f"Monthly credit allocation — {plan.display_name or plan.name} plan ({new_credits} credits)",
                    )
                    db.add(alloc_tx)

                    reset_count += 1

                except Exception as e:
                    logger.error(f"Failed to reset credits for user {user.id}: {e}")
                    error_count += 1

            await db.commit()
            logger.info(f"Monthly credit reset completed: {reset_count} users reset, {error_count} errors")

        return {
            "status": "completed",
            "users_reset": reset_count,
            "errors": error_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Monthly credit reset task failed: {e}")
        return {"status": "failed", "error": str(e)}

    finally:
        await engine.dispose()


async def cleanup_expired_bonus_credits_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Daily task to clean up expired bonus credits.
    Zeroes out bonus_credits where bonus_credits_expiry has passed.
    """
    logger.info("Starting expired bonus credits cleanup")

    from sqlalchemy import select, and_
    from app.models.user import User
    from app.models.billing import CreditTransaction

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    cleaned_count = 0

    try:
        async with async_session() as db:
            result = await db.execute(
                select(User).where(
                    and_(
                        User.bonus_credits > 0,
                        User.bonus_credits_expiry != None,
                        User.bonus_credits_expiry < datetime.utcnow(),
                    )
                )
            )
            users = result.scalars().all()

            for user in users:
                expired_amount = user.bonus_credits
                user.bonus_credits = 0
                user.bonus_credits_expiry = None

                tx = CreditTransaction(
                    user_id=user.id,
                    amount=-expired_amount,
                    balance_after=(user.subscription_credits or 0) + (user.purchased_credits or 0),
                    transaction_type="expiry",
                    description=f"Bonus credits expired ({expired_amount} credits)",
                )
                db.add(tx)
                cleaned_count += 1

            await db.commit()
            logger.info(f"Cleaned up bonus credits for {cleaned_count} users")

        return {"status": "completed", "users_cleaned": cleaned_count}

    except Exception as e:
        logger.error(f"Bonus credit cleanup failed: {e}")
        return {"status": "failed", "error": str(e)}

    finally:
        await engine.dispose()


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
        monthly_credit_reset_task,
        cleanup_expired_bonus_credits_task,
        auto_renew_subscriptions_task,
    ]

    # Cron jobs (scheduled tasks)
    cron_jobs = [
        # Daily demo regeneration DISABLED — pre-generated content is permanent.
        # Use main_pregenerate.py for one-time generation instead of wasting
        # API credits on daily regeneration that nobody specifically requested.
        # To re-enable: uncomment the cron below.
        # cron(
        #     regenerate_demos_task,
        #     hour=3,
        #     minute=0,
        #     run_at_startup=False
        # ),
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
        # Monthly credit reset — 1st of each month at 00:05 UTC
        cron(
            monthly_credit_reset_task,
            month=None,  # Every month
            day=1,
            hour=0,
            minute=5,
            run_at_startup=False
        ),
        # Daily expired bonus credit cleanup — 2:00 AM UTC
        cron(
            cleanup_expired_bonus_credits_task,
            hour=2,
            minute=0,
            run_at_startup=False
        ),
        # Daily auto-renewal check — 1:00 AM UTC
        # Renews expired subscriptions with auto_renew=True and allocates new credits
        cron(
            auto_renew_subscriptions_task,
            hour=1,
            minute=0,
            run_at_startup=False
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
