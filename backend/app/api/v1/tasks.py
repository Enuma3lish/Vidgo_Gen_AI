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

@router.post("/reclaim-pending", response_model=TaskResponse)
async def trigger_reclaim_pending(secret: str = Depends(verify_tasks_secret)):
    """Runs every 2 minutes via Cloud Scheduler"""
    asyncio.create_task(reclaim_pending_provider_tasks_task({}))
    return TaskResponse(status="ok")

@router.post("/cleanup-demos", response_model=TaskResponse)
async def trigger_cleanup_demos(secret: str = Depends(verify_tasks_secret)):
    """Runs hourly via Cloud Scheduler"""
    asyncio.create_task(cleanup_expired_demos_task({}))
    return TaskResponse(status="ok")

@router.post("/regenerate-demos", response_model=TaskResponse)
async def trigger_regenerate_demos(secret: str = Depends(verify_tasks_secret)):
    """Runs daily via Cloud Scheduler"""
    asyncio.create_task(regenerate_demos_task({}))
    return TaskResponse(status="ok")

@router.post("/monthly-credit-reset", response_model=TaskResponse)
async def trigger_monthly_credit_reset(secret: str = Depends(verify_tasks_secret)):
    """Runs monthly via Cloud Scheduler"""
    asyncio.create_task(monthly_credit_reset_task({}))
    return TaskResponse(status="ok")

@router.post("/cleanup-bonus-credits", response_model=TaskResponse)
async def trigger_cleanup_bonus_credits(secret: str = Depends(verify_tasks_secret)):
    """Runs daily via Cloud Scheduler"""
    asyncio.create_task(cleanup_expired_bonus_credits_task({}))
    return TaskResponse(status="ok")

@router.post("/auto-renew-subscriptions", response_model=TaskResponse)
async def trigger_auto_renew_subscriptions(secret: str = Depends(verify_tasks_secret)):
    """Runs daily via Cloud Scheduler"""
    asyncio.create_task(auto_renew_subscriptions_task({}))
    return TaskResponse(status="ok")
