from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import os
import logging
import asyncio

# Import the actual task logic
from app.worker import (
    regenerate_demos_task,
    cleanup_expired_demos_task,
    health_check_task,
    monthly_credit_reset_task,
    cleanup_expired_bonus_credits_task,
    auto_renew_subscriptions_task,
    reclaim_pending_provider_tasks_task,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Cloud Scheduler or Cloud Tasks should send this header
TASKS_SECRET_HEADER = APIKeyHeader(name="X-Tasks-Secret")

def verify_tasks_secret(api_key: str = Security(TASKS_SECRET_HEADER)):
    expected_secret = os.getenv("TASKS_SECRET_KEY")
    # If no secret is configured, deny access by default for safety
    if not expected_secret or api_key != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid tasks secret")
    return api_key

class TaskResponse(BaseModel):
    status: str
    message: str = "Task started in background"


# Strong references so fire-and-forget tasks can't be garbage-collected
# mid-run (asyncio only keeps weak refs to tasks — an unreferenced
# create_task() is legal GC prey, silently killing a half-done financial
# job). 2026-07-10.
_BACKGROUND_TASKS: set = set()


def _spawn(coro, name: str):
    task = asyncio.create_task(coro, name=name)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


async def _spawn_locked(coro_factory, name: str, ttl_seconds: int) -> bool:
    """Run a task only if no other instance/run currently holds its Redis
    lock. Cloud Scheduler fires every N minutes regardless of whether the
    previous run finished; on CPU-throttled Cloud Run a slow run overlaps the
    next one and both process the same rows (double refunds in the reclaim
    task). Fail-open when Redis is down — a rare double-run beats never
    running. Lock auto-expires; we do NOT release early so a fast run still
    shields the remainder of its window."""
    try:
        from app.api import deps
        redis_client = await deps.get_redis()
        acquired = await redis_client.set(f"tasks:lock:{name}", "1", nx=True, ex=ttl_seconds)
        if not acquired:
            logger.info("tasks: %s already running elsewhere — skipped", name)
            return False
    except Exception as exc:
        logger.warning("tasks: Redis lock unavailable for %s (%s) — running unlocked", name, exc)
    _spawn(coro_factory(), name)
    return True


@router.post("/reclaim-pending", response_model=TaskResponse)
async def trigger_reclaim_pending(secret: str = Depends(verify_tasks_secret)):
    """Runs every 2 minutes via Cloud Scheduler"""
    started = await _spawn_locked(lambda: reclaim_pending_provider_tasks_task({}), "reclaim-pending", 110)
    return TaskResponse(status="ok" if started else "skipped")

@router.post("/cleanup-demos", response_model=TaskResponse)
async def trigger_cleanup_demos(secret: str = Depends(verify_tasks_secret)):
    """Runs hourly via Cloud Scheduler"""
    _spawn(cleanup_expired_demos_task({}), "cleanup-demos")
    return TaskResponse(status="ok")

@router.post("/regenerate-demos", response_model=TaskResponse)
async def trigger_regenerate_demos(secret: str = Depends(verify_tasks_secret)):
    """Daily demo regeneration — DISABLED unless DEMO_REGEN_ENABLED=true.

    2026-07-10: one run is ~80+ premium pipelines (nano-banana-pro T2I +
    Veo I2V) producing demos that self-expire in 7 days; the ARQ cron for
    this task was deliberately disabled as credit waste, but this endpoint
    quietly re-enabled it for Cloud Scheduler. Opt back in via env when the
    spend is intended.
    """
    if os.getenv("DEMO_REGEN_ENABLED", "").lower() not in ("1", "true", "yes"):
        raise HTTPException(
            status_code=403,
            detail="Demo regeneration is disabled (set DEMO_REGEN_ENABLED=true to allow; ~80 premium generations per run)",
        )
    _spawn(regenerate_demos_task({}), "regenerate-demos")
    return TaskResponse(status="ok")

@router.post("/monthly-credit-reset", response_model=TaskResponse)
async def trigger_monthly_credit_reset(secret: str = Depends(verify_tasks_secret)):
    """Runs monthly via Cloud Scheduler"""
    started = await _spawn_locked(lambda: monthly_credit_reset_task({}), "monthly-credit-reset", 3600)
    return TaskResponse(status="ok" if started else "skipped")

@router.post("/cleanup-bonus-credits", response_model=TaskResponse)
async def trigger_cleanup_bonus_credits(secret: str = Depends(verify_tasks_secret)):
    """Runs daily via Cloud Scheduler"""
    _spawn(cleanup_expired_bonus_credits_task({}), "cleanup-bonus-credits")
    return TaskResponse(status="ok")

@router.post("/auto-renew-subscriptions", response_model=TaskResponse)
async def trigger_auto_renew_subscriptions(secret: str = Depends(verify_tasks_secret)):
    """Runs daily via Cloud Scheduler"""
    started = await _spawn_locked(lambda: auto_renew_subscriptions_task({}), "auto-renew-subscriptions", 3600)
    return TaskResponse(status="ok" if started else "skipped")
