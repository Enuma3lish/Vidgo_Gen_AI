"""
Quota API - Free quota management for daily limits and per-user limits
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
import redis.asyncio as redis
from app.core.config import settings

router = APIRouter()


# ============== Schemas ==============

class DailyQuotaResponse(BaseModel):
    remaining: int
    total: int
    reset_at: str


class UserQuotaResponse(BaseModel):
    remaining: int
    total: int
    is_exhausted: bool


class PromoQuotaResponse(BaseModel):
    remaining: int
    plan: str
    discount: str
    expires_at: Optional[str]


class UseQuotaResponse(BaseModel):
    success: bool
    remaining: int
    message: str


# ============== Constants ==============

DAILY_FREE_QUOTA = 100  # 全站每日免費額度
USER_FREE_TRIALS = 5    # 每人免費試用次數
PROMO_REMAINING = 88    # 促銷剩餘名額 (動態顯示)


# ============== Redis Keys ==============

def get_daily_quota_key() -> str:
    """Get Redis key for today's quota"""
    today = date.today().isoformat()
    return f"quota:daily:{today}"


def get_user_quota_key(identifier: str) -> str:
    """Get Redis key for user quota (by user_id or IP)"""
    return f"quota:user:{identifier}"


def get_promo_quota_key() -> str:
    """Get Redis key for promotional quota"""
    return "quota:promo:current"


# ============== Helper Functions ==============

async def get_redis_client():
    """Get Redis client connection"""
    return redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )


def get_client_identifier(request: Request, user_id: Optional[str] = None) -> str:
    """Get unique identifier for client (user_id or IP)"""
    if user_id:
        return f"user:{user_id}"
    # Use IP for anonymous users
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    return f"ip:{ip}"


# ============== Endpoints ==============

@router.get("/daily", response_model=DailyQuotaResponse)
async def get_daily_quota():
    """
    Get today's remaining free quota for the whole site
    全站每日免費額度：100 次
    """
    try:
        r = await get_redis_client()
        key = get_daily_quota_key()

        # Get current count
        used = await r.get(key)
        used = int(used) if used else 0
        remaining = max(0, DAILY_FREE_QUOTA - used)

        # Calculate reset time (next midnight)
        now = datetime.now()
        tomorrow = datetime(now.year, now.month, now.day) + timedelta(days=1)
        reset_at = tomorrow.isoformat()

        await r.aclose()

        return DailyQuotaResponse(
            remaining=remaining,
            total=DAILY_FREE_QUOTA,
            reset_at=reset_at
        )
    except Exception as e:
        # Return default on error
        return DailyQuotaResponse(
            remaining=DAILY_FREE_QUOTA,
            total=DAILY_FREE_QUOTA,
            reset_at=datetime.now().isoformat()
        )


@router.get("/user", response_model=UserQuotaResponse)
async def get_user_quota(request: Request, user_id: Optional[str] = None):
    """
    Get user's remaining free trials
    每人免費試用：5 次（未登入用 IP 識別）
    """
    try:
        r = await get_redis_client()
        identifier = get_client_identifier(request, user_id)
        key = get_user_quota_key(identifier)

        # Get used count
        used = await r.get(key)
        used = int(used) if used else 0
        remaining = max(0, USER_FREE_TRIALS - used)

        await r.aclose()

        return UserQuotaResponse(
            remaining=remaining,
            total=USER_FREE_TRIALS,
            is_exhausted=remaining <= 0
        )
    except Exception as e:
        return UserQuotaResponse(
            remaining=USER_FREE_TRIALS,
            total=USER_FREE_TRIALS,
            is_exhausted=False
        )


@router.post("/use", response_model=UseQuotaResponse)
async def use_quota(request: Request, user_id: Optional[str] = None):
    """
    Use one free quota (for demo generation)
    Checks both daily limit and per-user limit
    """
    try:
        r = await get_redis_client()

        # Check daily quota
        daily_key = get_daily_quota_key()
        daily_used = await r.get(daily_key)
        daily_used = int(daily_used) if daily_used else 0

        if daily_used >= DAILY_FREE_QUOTA:
            await r.aclose()
            return UseQuotaResponse(
                success=False,
                remaining=0,
                message="今日免費額度已用完，請明天再試或升級方案"
            )

        # Check user quota
        identifier = get_client_identifier(request, user_id)
        user_key = get_user_quota_key(identifier)
        user_used = await r.get(user_key)
        user_used = int(user_used) if user_used else 0

        if user_used >= USER_FREE_TRIALS:
            await r.aclose()
            return UseQuotaResponse(
                success=False,
                remaining=0,
                message="您的免費試用次數已用完，請註冊或升級方案"
            )

        # Increment both counters
        await r.incr(daily_key)
        await r.expire(daily_key, 86400)  # 24 hours TTL

        await r.incr(user_key)
        # User quota never expires (lifetime limit)

        new_remaining = USER_FREE_TRIALS - user_used - 1

        await r.aclose()

        return UseQuotaResponse(
            success=True,
            remaining=new_remaining,
            message=f"剩餘免費次數：{new_remaining}"
        )
    except Exception as e:
        return UseQuotaResponse(
            success=False,
            remaining=0,
            message="系統錯誤，請稍後再試"
        )


@router.get("/promo", response_model=PromoQuotaResponse)
async def get_promo_quota():
    """
    Get promotional remaining slots
    本月優惠剩餘名額：動態顯示
    """
    try:
        r = await get_redis_client()
        key = get_promo_quota_key()

        remaining = await r.get(key)
        if remaining is None:
            # Initialize promo quota
            remaining = PROMO_REMAINING
            await r.set(key, remaining)
        else:
            remaining = int(remaining)

        await r.aclose()

        # Calculate end of month
        now = datetime.now()
        if now.month == 12:
            expires_at = datetime(now.year + 1, 1, 1).isoformat()
        else:
            expires_at = datetime(now.year, now.month + 1, 1).isoformat()

        return PromoQuotaResponse(
            remaining=remaining,
            plan="Pro",
            discount="50%",
            expires_at=expires_at
        )
    except Exception:
        return PromoQuotaResponse(
            remaining=PROMO_REMAINING,
            plan="Pro",
            discount="50%",
            expires_at=None
        )


# Import timedelta
from datetime import timedelta
