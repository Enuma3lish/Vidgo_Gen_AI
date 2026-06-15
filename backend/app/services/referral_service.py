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
from sqlalchemy import func, select
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

# 2026-06-15 (Plan D): description tags for the split signup / conversion /
# first-generation bonuses. Kept distinct so the admin dashboard, idempotency
# checks, and the 30-day cap query can each filter on the exact event without
# matching the others. The legacy "Referral reward: %" prefix from the
# pre-Plan-D code path still appears in historical rows; admin /promotions
# uses `LIKE 'Referral reward%'` which catches both old and new.
REFERRAL_SIGNUP_TAG     = "Referral reward (signup):"
REFERRAL_CONVERSION_TAG = "Referral reward (paid conversion):"
REFERRAL_FIRSTGEN_TAG   = "Welcome bonus (first generation):"


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

        # 2026-06-15 (Plan D): 30-day rolling cap on promoter signup bonuses.
        # Past the cap we still record the referral link so the conversion
        # bonus can fire later, but we skip the promoter signup credit — this
        # is the abuse-cap that stops mass-signup credit farming.
        signup_count = await self._signup_bonuses_awarded_recently(str(referrer.id))
        cap = int(settings.REFERRAL_SIGNUP_MONTHLY_CAP)
        promoter_signup_credits = 0
        capped = signup_count >= cap > 0
        if not capped:
            promoter_signup_credits = self.referrer_reward_credits
            await credit_svc.add_credits(
                user_id=str(referrer.id),
                amount=promoter_signup_credits,
                credit_type="bonus",
                description=f"{REFERRAL_SIGNUP_TAG} {new_user.email} signed up with your code",
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
                reward_credits=promoter_signup_credits,
            )
        except Exception as exc:
            logger.warning(
                "Failed to send promotion-code notification to %s for referred user %s: %s",
                referrer.email,
                new_user.email,
                exc,
            )

        cap_note = f" (signup bonus skipped — promoter hit {cap}/30d cap)" if capped else ""
        logger.info(
            f"Referral applied: {new_user.email} referred by {referrer.email} "
            f"(+{promoter_signup_credits} to referrer, +{self.referee_welcome_credits} to new user){cap_note}"
        )
        return True, "Referral code applied successfully"

    async def _signup_bonuses_awarded_recently(self, promoter_id: str, days: int = 30) -> int:
        """Count CreditTransactions tagged as Plan-D signup bonus for this
        promoter within the rolling window. Used to enforce the per-promoter
        monthly cap so a single account can't farm signup credits indefinitely.
        Only counts the new tag (REFERRAL_SIGNUP_TAG); legacy "Referral reward:"
        rows from the pre-Plan-D code never re-trigger and shouldn't count
        against the new cap.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(
            select(func.count(CreditTransaction.id)).where(
                CreditTransaction.user_id == promoter_id,
                CreditTransaction.transaction_type == "bonus",
                CreditTransaction.description.like(f"{REFERRAL_SIGNUP_TAG}%"),
                CreditTransaction.created_at >= since,
            )
        )
        return int(result.scalar() or 0)

    async def _conversion_bonus_already_awarded(self, referred_user_id: str) -> bool:
        """Idempotency check for the paid-conversion bonus. The referred
        user's id is embedded in the description (avoids JSON-operator
        portability concerns vs. extra_data lookup) so a plain LIKE works
        on any backend."""
        result = await self.db.execute(
            select(CreditTransaction.id).where(
                CreditTransaction.transaction_type == "bonus",
                CreditTransaction.description.like(f"{REFERRAL_CONVERSION_TAG}%[user:{referred_user_id}]%"),
            )
        )
        return result.scalars().first() is not None

    async def _firstgen_bonus_already_awarded(self, referred_user_id: str) -> bool:
        result = await self.db.execute(
            select(CreditTransaction.id).where(
                CreditTransaction.user_id == referred_user_id,
                CreditTransaction.transaction_type == "bonus",
                CreditTransaction.description.like(f"{REFERRAL_FIRSTGEN_TAG}%"),
            )
        )
        return result.scalars().first() is not None

    async def award_paid_conversion(
        self,
        referred_user_id: str,
        plan_name: Optional[str] = None,
        redis_client=None,
    ) -> Tuple[bool, str]:
        """Plan D: when a referred user activates their FIRST paid plan, pay
        the promoter the conversion bonus. Idempotent — second activations
        (renewals, upgrades) don't double-pay.

        Caller MUST skip if `plan_name` is the $1 test plan or any free
        plan; this method assumes the caller already filtered.
        """
        result = await self.db.execute(select(User).where(User.id == referred_user_id))
        referred_user = result.scalar_one_or_none()
        if not referred_user or not referred_user.referred_by_id:
            return False, "User has no referrer"
        if await self._conversion_bonus_already_awarded(str(referred_user.id)):
            return False, "Conversion bonus already awarded"

        referrer = await self.db.get(User, referred_user.referred_by_id)
        if not referrer:
            return False, "Referrer not found"

        amount = int(settings.REFERRAL_PAID_CONVERSION_PROMOTER_CREDITS)
        if amount <= 0:
            return False, "Conversion bonus disabled (amount=0)"

        credit_svc = CreditService(self.db, redis_client)
        expiry = datetime.now(timezone.utc) + timedelta(days=BONUS_EXPIRY_DAYS)
        # Embed [user:<id>] in the description so _conversion_bonus_already_awarded
        # can do a portable LIKE lookup without leaning on JSON operators.
        await credit_svc.add_credits(
            user_id=str(referrer.id),
            amount=amount,
            credit_type="bonus",
            description=(
                f"{REFERRAL_CONVERSION_TAG} {referred_user.email} subscribed to "
                f"{plan_name or 'a paid plan'} [user:{referred_user.id}]"
            ),
            expiry=expiry,
            metadata={
                "referred_user_id": str(referred_user.id),
                "plan_name": plan_name,
            },
        )
        await self.db.commit()
        logger.info(
            f"Conversion bonus awarded: +{amount} to {referrer.email} (referred {referred_user.email} → {plan_name})"
        )
        return True, "Conversion bonus awarded"

    async def award_first_generation(
        self,
        referred_user_id: str,
        redis_client=None,
    ) -> Tuple[bool, str]:
        """Plan D: when a referred user makes their first credit-deducted
        generation, give the REFEREE the engagement bonus. The promoter side
        is already handled by award_paid_conversion. Idempotent."""
        result = await self.db.execute(select(User).where(User.id == referred_user_id))
        user = result.scalar_one_or_none()
        if not user or not user.referred_by_id:
            return False, "User has no referrer"
        if await self._firstgen_bonus_already_awarded(str(user.id)):
            return False, "First-generation bonus already awarded"

        amount = int(settings.REFERRAL_FIRST_GENERATION_REFEREE_CREDITS)
        if amount <= 0:
            return False, "First-generation bonus disabled (amount=0)"

        credit_svc = CreditService(self.db, redis_client)
        expiry = datetime.now(timezone.utc) + timedelta(days=BONUS_EXPIRY_DAYS)
        await credit_svc.add_credits(
            user_id=str(user.id),
            amount=amount,
            credit_type="bonus",
            description=f"{REFERRAL_FIRSTGEN_TAG} thanks for your first generation",
            expiry=expiry,
            metadata={"referrer_id": str(user.referred_by_id)},
        )
        await self.db.commit()
        logger.info(f"First-generation bonus awarded: +{amount} to {user.email}")
        return True, "First-generation bonus awarded"

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
        """Get referral statistics for a user.

        2026-06-15 (Plan D): total_credits_earned now SUMs actual
        CreditTransaction rows (signup + conversion bonuses, including legacy
        "Referral reward:" rows from before Plan D). Pre-Plan-D code used
        (referral_count × referrer_reward_credits) which now under-counts
        historical earnings since the per-signup rate dropped 50 → 10.
        """
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

        earned_result = await self.db.execute(
            select(func.coalesce(func.sum(CreditTransaction.amount), 0)).where(
                CreditTransaction.user_id == user_id,
                CreditTransaction.transaction_type == "bonus",
                CreditTransaction.description.like("Referral reward%"),
            )
        )
        total_credits_earned = int(earned_result.scalar() or 0)

        return {
            "referral_code": user.referral_code,
            "referral_count": user.referral_count or 0,
            "total_credits_earned": total_credits_earned,
            "referred_users": [
                {
                    "email": u.email[:3] + "***" + u.email[u.email.index("@"):],
                    "joined_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in referred_users
            ],
            # Forward-looking rates (Plan D split: small signup + big conversion + first-gen).
            "reward_per_signup": self.referrer_reward_credits,
            "reward_per_paid_conversion": int(settings.REFERRAL_PAID_CONVERSION_PROMOTER_CREDITS),
            "referee_welcome_bonus": self.referee_welcome_credits,
            "referee_first_generation_bonus": int(settings.REFERRAL_FIRST_GENERATION_REFEREE_CREDITS),
            "monthly_signup_cap": int(settings.REFERRAL_SIGNUP_MONTHLY_CAP),
        }
