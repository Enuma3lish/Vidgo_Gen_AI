"""
Referral Service - Manages user referral program.

When a new user registers with a promotion/referral code:
1. The new user is linked to the referrer
2. The referrer receives bonus credits
3. The new user also receives a welcome bonus

Credit rewards are configured in app settings.
"""
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.core.config import get_settings
from app.models.billing import CreditTransaction
from app.models.user import User
from app.services.credit_service import CreditService
from app.services.email_service import email_service

logger = logging.getLogger(__name__)

settings = get_settings()
BONUS_EXPIRY_DAYS = 90
WELCOME_BONUS_DESCRIPTIONS = (
    "Welcome bonus for using a referral code",
    "Welcome bonus for using a promotion code",
)


class ReferralService:
    """Service for managing user referrals."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @property
    def referrer_reward_credits(self) -> int:
        return settings.REFERRAL_BONUS_CREDITS

    @property
    def referee_welcome_credits(self) -> int:
        return settings.REFERRAL_WELCOME_CREDITS

    async def _welcome_bonus_already_awarded(self, user_id: str) -> bool:
        result = await self.db.execute(
            select(CreditTransaction).where(
                CreditTransaction.user_id == user_id,
                CreditTransaction.transaction_type == "bonus",
                CreditTransaction.description.in_(WELCOME_BONUS_DESCRIPTIONS),
            )
        )
        return result.scalars().first() is not None

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
        if await self._welcome_bonus_already_awarded(new_user_id):
            return False, "Referral bonus already applied"

        referrer.referral_count = (referrer.referral_count or 0) + 1

        credit_svc = CreditService(self.db, redis_client)
        expiry = datetime.now(timezone.utc) + timedelta(days=BONUS_EXPIRY_DAYS)

        await credit_svc.add_credits(
            user_id=str(referrer.id),
            amount=self.referrer_reward_credits,
            credit_type="bonus",
            description=f"Referral reward: {new_user.email} signed up with your code",
            expiry=expiry,
            metadata={"referral_user_id": str(new_user_id)},
        )

        await credit_svc.add_credits(
            user_id=str(new_user_id),
            amount=self.referee_welcome_credits,
            credit_type="bonus",
            description="Welcome bonus for using a promotion code",
            expiry=expiry,
            metadata={"referrer_id": str(referrer.id)},
        )

        await self.db.commit()

        try:
            await email_service.send_promotion_code_used_email(
                to_email=referrer.email,
                username=referrer.username or referrer.full_name,
                new_user_email=new_user.email,
                promotion_code=referrer.referral_code or "",
                reward_credits=self.referrer_reward_credits,
            )
        except Exception as exc:
            logger.warning(
                "Failed to send promotion-code notification to %s for referred user %s: %s",
                referrer.email,
                new_user.email,
                exc,
            )

        logger.info(
            f"Referral applied: {new_user.email} referred by {referrer.email} "
            f"(+{self.referrer_reward_credits} to referrer, +{self.referee_welcome_credits} to new user)"
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

        if await self._welcome_bonus_already_awarded(str(new_user.id)):
            return False, "Referral bonus already awarded"

        referrer.referral_count = (referrer.referral_count or 0) + 1

        credit_svc = CreditService(self.db, redis_client)
        expiry = datetime.now(timezone.utc) + timedelta(days=BONUS_EXPIRY_DAYS)

        await credit_svc.add_credits(
            user_id=str(referrer.id),
            amount=self.referrer_reward_credits,
            credit_type="bonus",
            description=f"Referral reward: {new_user.email} verified their account",
            expiry=expiry,
            metadata={"referral_user_id": str(new_user.id)},
        )

        await credit_svc.add_credits(
            user_id=str(new_user.id),
            amount=self.referee_welcome_credits,
            credit_type="bonus",
            description="Welcome bonus for using a promotion code",
            expiry=expiry,
            metadata={"referrer_id": str(referrer.id)},
        )

        await self.db.commit()

        try:
            await email_service.send_promotion_code_used_email(
                to_email=referrer.email,
                username=referrer.username or referrer.full_name,
                new_user_email=new_user.email,
                promotion_code=referrer.referral_code or "",
                reward_credits=self.referrer_reward_credits,
            )
        except Exception as exc:
            logger.warning(
                "Failed to send promotion-code notification to %s for referred user %s: %s",
                referrer.email,
                new_user.email,
                exc,
            )

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
            "total_credits_earned": (user.referral_count or 0) * self.referrer_reward_credits,
            "referred_users": [
                {
                    "email": u.email[:3] + "***" + u.email[u.email.index("@"):],
                    "joined_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in referred_users
            ],
            "reward_per_referral": self.referrer_reward_credits,
            "referee_bonus": self.referee_welcome_credits,
        }
