"""
Referral System API

Endpoints:
- GET  /referrals/code          - Get or create own referral code
- GET  /referrals/stats         - Referral stats (count, credits earned)
- POST /referrals/apply         - Apply a referral code (called during/after registration)
- GET  /referrals/leaderboard   - Top referrers (public)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func as sql_func

from app.api.deps import get_db, get_current_active_user
from app.models.user import User, generate_referral_code
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/referrals", tags=["referrals"])


# ─────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────

class ReferralCodeResponse(BaseModel):
    referral_code: str
    referral_url: str


class ReferralStatsResponse(BaseModel):
    referral_code: str
    referral_url: str
    referral_count: int
    credits_earned: int
    referred_by: Optional[str] = None    # email of who referred this user (masked)


class ApplyReferralRequest(BaseModel):
    referral_code: str


class ApplyReferralResponse(BaseModel):
    success: bool
    message: str
    bonus_credits: int


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    referral_count: int


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _mask_email(email: str) -> str:
    """Mask email for display: john@example.com → j***@example.com"""
    parts = email.split('@')
    if len(parts) != 2:
        return "***"
    name = parts[0]
    masked = name[0] + '***' if name else '***'
    return f"{masked}@{parts[1]}"


async def _ensure_referral_code(user: User, db: AsyncSession) -> str:
    """Ensure user has a referral code, generating one if absent."""
    if user.referral_code:
        return user.referral_code

    # Generate unique code
    for _ in range(10):
        code = generate_referral_code()
        existing = await db.execute(select(User).where(User.referral_code == code))
        if not existing.scalars().first():
            user.referral_code = code
            await db.commit()
            await db.refresh(user)
            return code

    raise HTTPException(status_code=500, detail="Could not generate unique referral code")


# ─────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────

@router.get("/code", response_model=ReferralCodeResponse)
async def get_referral_code(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get (or create) the current user's referral code."""
    code = await _ensure_referral_code(current_user, db)
    url = f"{settings.FRONTEND_URL}/auth/register?ref={code}"
    return ReferralCodeResponse(referral_code=code, referral_url=url)


@router.get("/stats", response_model=ReferralStatsResponse)
async def get_referral_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get referral statistics for the current user."""
    code = await _ensure_referral_code(current_user, db)

    # Count how many users were referred by this user
    result = await db.execute(
        select(sql_func.count(User.id)).where(User.referred_by_id == current_user.id)
    )
    referral_count = result.scalar() or 0

    credits_earned = referral_count * settings.REFERRAL_BONUS_CREDITS

    # Who referred this user?
    referred_by_email = None
    if current_user.referred_by_id:
        ref_result = await db.execute(
            select(User.email).where(User.id == current_user.referred_by_id)
        )
        ref_email = ref_result.scalar()
        if ref_email:
            referred_by_email = _mask_email(ref_email)

    url = f"{settings.FRONTEND_URL}/auth/register?ref={code}"
    return ReferralStatsResponse(
        referral_code=code,
        referral_url=url,
        referral_count=referral_count,
        credits_earned=credits_earned,
        referred_by=referred_by_email,
    )


@router.post("/apply", response_model=ApplyReferralResponse)
async def apply_referral_code(
    request: ApplyReferralRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Apply a referral code to the current user's account.

    Rules:
    - Can only be applied once (if referred_by_id is already set, reject)
    - Cannot apply own referral code
    - Referrer receives REFERRAL_BONUS_CREDITS
    - New user receives REFERRAL_WELCOME_CREDITS
    """
    if current_user.referred_by_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already used a referral code."
        )

    code = request.referral_code.strip().upper()

    # Find referrer
    result = await db.execute(select(User).where(User.referral_code == code))
    referrer = result.scalars().first()

    if not referrer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid referral code."
        )

    if referrer.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot use your own referral code."
        )

    # Apply referral
    current_user.referred_by_id = referrer.id
    current_user.bonus_credits = (current_user.bonus_credits or 0) + settings.REFERRAL_WELCOME_CREDITS

    # Reward referrer
    referrer.bonus_credits = (referrer.bonus_credits or 0) + settings.REFERRAL_BONUS_CREDITS
    referrer.referral_count = (referrer.referral_count or 0) + 1

    await db.commit()

    return ApplyReferralResponse(
        success=True,
        message=f"Referral applied! You received {settings.REFERRAL_WELCOME_CREDITS} bonus credits.",
        bonus_credits=settings.REFERRAL_WELCOME_CREDITS,
    )


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    db: AsyncSession = Depends(get_db),
):
    """Top 10 referrers leaderboard (public)."""
    result = await db.execute(
        select(User.username, User.referral_count)
        .where(User.referral_count > 0)
        .order_by(User.referral_count.desc())
        .limit(10)
    )
    rows = result.all()
    return [
        LeaderboardEntry(
            rank=idx + 1,
            username=row.username or "Anonymous",
            referral_count=row.referral_count or 0,
        )
        for idx, row in enumerate(rows)
    ]
