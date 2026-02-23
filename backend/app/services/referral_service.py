"""
Referral Service - Manages user referral program.

When a new user registers with a referral code:
1. The new user is linked to the referrer
2. The referrer receives bonus credits
3. The new user also receives a welcome bonus

Credit rewards:
- Referrer: 10 bonus credits per successful referral
- New user: 5 bonus credits for using a referral code
"""
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.models.user import User
from app.services.credit_service import CreditService

logger = logging.getLogger(__name__)

REFERRER_REWARD_CREDITS = 10
REFEREE_WELCOME_CREDITS = 5
BONUS_EXPIRY_DAYS = 90


class ReferralService:
    """Service for managing user referrals."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_referrer(self, referral_code: str) -> Optional[User]:
        """Find the user who owns a referral code."""
        if not referral_code:
            return None

        result = await self.db.execute(
            select(User).where(
                User.referral_code == referral_code.strip().upper(),
                User.is_active == True,
                User.email_verified == True,
            )
        )
        return result.scalar_one_or_none()

    async def apply_referral(
        self,
        new_user_id: str,
        referral_code: str,
        redis_client=None,
    ) -> Tuple[bool, str]:
        """
        Apply a referral code to a newly registered user.

        Returns (success, message).
        """
        referrer = await self.find_referrer(referral_code)
        if not referrer:
            return False, "Invalid or expired referral code"

        if str(referrer.id) == str(new_user_id):
            return False, "Cannot use your own referral code"

        result = await self.db.execute(
            select(User).where(User.id == new_user_id)
        )
        new_user = result.scalar_one_or_none()
        if not new_user:
            return False, "User not found"

        if new_user.referred_by_id:
            return False, "Referral code already applied"

        new_user.referred_by_id = referrer.id
        referrer.referral_count = (referrer.referral_count or 0) + 1

        credit_svc = CreditService(self.db, redis_client)
        expiry = datetime.now(timezone.utc) + timedelta(days=BONUS_EXPIRY_DAYS)

        await credit_svc.add_credits(
            user_id=str(referrer.id),
            amount=REFERRER_REWARD_CREDITS,
            credit_type="bonus",
            description=f"Referral reward: {new_user.email} signed up with your code",
            expiry=expiry,
            metadata={"referral_user_id": str(new_user_id)},
        )

        await credit_svc.add_credits(
            user_id=str(new_user_id),
            amount=REFEREE_WELCOME_CREDITS,
            credit_type="bonus",
            description="Welcome bonus for using a referral code",
            expiry=expiry,
            metadata={"referrer_id": str(referrer.id)},
        )

        await self.db.commit()
        logger.info(
            f"Referral applied: {new_user.email} referred by {referrer.email} "
            f"(+{REFERRER_REWARD_CREDITS} to referrer, +{REFEREE_WELCOME_CREDITS} to new user)"
        )
        return True, "Referral code applied successfully"

    async def award_referral_bonus(
        self,
        new_user: User,
        redis_client=None,
    ) -> Tuple[bool, str]:
        """
        Award referral bonuses after a new user verifies their email.
        The new_user must already have referred_by set.
        """
        if not new_user.referred_by_id:
            return False, "User has no referrer"

        result = await self.db.execute(
            select(User).where(User.id == new_user.referred_by_id)
        )
        referrer = result.scalar_one_or_none()
        if not referrer:
            return False, "Referrer not found"

        referrer.referral_count = (referrer.referral_count or 0) + 1

        credit_svc = CreditService(self.db, redis_client)
        expiry = datetime.now(timezone.utc) + timedelta(days=BONUS_EXPIRY_DAYS)

        await credit_svc.add_credits(
            user_id=str(referrer.id),
            amount=REFERRER_REWARD_CREDITS,
            credit_type="bonus",
            description=f"Referral reward: {new_user.email} verified their account",
            expiry=expiry,
            metadata={"referral_user_id": str(new_user.id)},
        )

        await credit_svc.add_credits(
            user_id=str(new_user.id),
            amount=REFEREE_WELCOME_CREDITS,
            credit_type="bonus",
            description="Welcome bonus for using a referral code",
            expiry=expiry,
            metadata={"referrer_id": str(referrer.id)},
        )

        await self.db.commit()
        logger.info(
            f"Referral bonus awarded: {new_user.email} referred by {referrer.email}"
        )
        return True, "Referral bonus awarded"

    async def get_referral_stats(self, user_id: str) -> Dict[str, Any]:
        """Get referral statistics for a user."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return {"error": "User not found"}

        referred_result = await self.db.execute(
            select(User).where(User.referred_by_id == user_id)
        )
        referred_users = referred_result.scalars().all()

        return {
            "referral_code": user.referral_code,
            "referral_count": user.referral_count or 0,
            "total_credits_earned": (user.referral_count or 0) * REFERRER_REWARD_CREDITS,
            "referred_users": [
                {
                    "email": u.email[:3] + "***" + u.email[u.email.index("@"):],
                    "joined_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in referred_users
            ],
            "reward_per_referral": REFERRER_REWARD_CREDITS,
            "referee_bonus": REFEREE_WELCOME_CREDITS,
        }
