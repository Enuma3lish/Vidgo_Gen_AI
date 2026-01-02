"""
Credit Service - Manages user credits for the VidGo platform.

Credit Deduction Priority:
1. Bonus Credits (expiring soonest first)
2. Subscription Credits (expire at month end)
3. Purchased Credits (never expire)
"""
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime
from uuid import UUID
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.config import get_settings
from app.models.user import User
from app.models.billing import CreditTransaction, ServicePricing, CreditPackage, Generation

settings = get_settings()


class CreditService:
    """Service for managing user credits with distributed locking."""

    def __init__(self, db: AsyncSession, redis_client: Optional[redis.Redis] = None):
        self.db = db
        self.redis = redis_client

    async def get_balance(self, user_id: str) -> Dict[str, Any]:
        """Get user's credit balance breakdown."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            return {
                "subscription": 0,
                "purchased": 0,
                "bonus": 0,
                "bonus_expiry": None,
                "total": 0
            }

        subscription = user.subscription_credits or 0
        purchased = user.purchased_credits or 0
        bonus = user.bonus_credits or 0

        # Check if bonus credits have expired
        if user.bonus_credits_expiry and user.bonus_credits_expiry < datetime.utcnow():
            bonus = 0

        return {
            "subscription": subscription,
            "purchased": purchased,
            "bonus": bonus,
            "bonus_expiry": user.bonus_credits_expiry,
            "total": subscription + purchased + bonus
        }

    async def check_sufficient(self, user_id: str, amount: int) -> bool:
        """Check if user has sufficient credits."""
        balance = await self.get_balance(user_id)
        return balance["total"] >= amount

    async def deduct_credits(
        self,
        user_id: str,
        amount: int,
        service_type: str,
        generation_id: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Deduct credits with distributed lock.
        Priority: bonus -> subscription -> purchased

        Returns:
            Tuple of (success, new_balance_or_error)
        """
        lock_key = f"credit_lock:{user_id}"

        try:
            # Use Redis lock if available
            if self.redis:
                async with self.redis.lock(lock_key, timeout=10):
                    return await self._do_deduct(
                        user_id, amount, service_type,
                        generation_id, description, metadata
                    )
            else:
                # Fallback without lock (for testing/dev)
                return await self._do_deduct(
                    user_id, amount, service_type,
                    generation_id, description, metadata
                )
        except Exception as e:
            return False, {"error": str(e)}

    async def _do_deduct(
        self,
        user_id: str,
        amount: int,
        service_type: str,
        generation_id: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Internal method to perform credit deduction."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            return False, {"error": "User not found"}

        balance = await self.get_balance(user_id)

        if balance["total"] < amount:
            return False, {"error": "Insufficient credits", "balance": balance}

        remaining = amount

        # 1. Deduct from bonus first (expiring soonest)
        if user.bonus_credits and user.bonus_credits > 0 and remaining > 0:
            # Check if bonus not expired
            if not user.bonus_credits_expiry or user.bonus_credits_expiry >= datetime.utcnow():
                deduct = min(user.bonus_credits, remaining)
                user.bonus_credits -= deduct
                remaining -= deduct

        # 2. Deduct from subscription
        if user.subscription_credits and user.subscription_credits > 0 and remaining > 0:
            deduct = min(user.subscription_credits, remaining)
            user.subscription_credits -= deduct
            remaining -= deduct

        # 3. Deduct from purchased
        if user.purchased_credits and user.purchased_credits > 0 and remaining > 0:
            deduct = min(user.purchased_credits, remaining)
            user.purchased_credits -= deduct
            remaining -= deduct

        # Get new balance
        new_balance = await self.get_balance(user_id)

        # Record transaction
        transaction = CreditTransaction(
            user_id=user_id,
            amount=-amount,
            balance_after=new_balance["total"],
            transaction_type="generation",
            service_type=service_type,
            generation_id=UUID(generation_id) if generation_id else None,
            description=description or f"Generation using {service_type}",
            extra_data=metadata
        )
        self.db.add(transaction)
        await self.db.commit()

        return True, new_balance

    async def add_credits(
        self,
        user_id: str,
        amount: int,
        credit_type: str,  # subscription, purchased, bonus
        package_id: Optional[str] = None,
        payment_id: Optional[str] = None,
        description: Optional[str] = None,
        expiry: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Add credits to user account."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        if credit_type == "subscription":
            user.subscription_credits = (user.subscription_credits or 0) + amount
        elif credit_type == "purchased":
            user.purchased_credits = (user.purchased_credits or 0) + amount
        elif credit_type == "bonus":
            user.bonus_credits = (user.bonus_credits or 0) + amount
            if expiry:
                user.bonus_credits_expiry = expiry
        else:
            raise ValueError(f"Invalid credit type: {credit_type}")

        new_balance = await self.get_balance(user_id)

        # Record transaction
        transaction = CreditTransaction(
            user_id=user_id,
            amount=amount,
            balance_after=new_balance["total"],
            transaction_type=credit_type,
            package_id=UUID(package_id) if package_id else None,
            payment_id=payment_id,
            description=description or f"Added {amount} {credit_type} credits",
            extra_data=metadata
        )
        self.db.add(transaction)
        await self.db.commit()

        return new_balance

    async def get_service_pricing(self, service_type: str) -> Optional[ServicePricing]:
        """Get pricing for a specific service type."""
        result = await self.db.execute(
            select(ServicePricing).where(
                ServicePricing.service_type == service_type,
                ServicePricing.is_active == True
            )
        )
        return result.scalar_one_or_none()

    async def estimate_cost(self, service_type: str) -> int:
        """Get credit cost for a service."""
        pricing = await self.get_service_pricing(service_type)
        return pricing.credit_cost if pricing else 0

    async def get_all_pricing(self) -> List[ServicePricing]:
        """Get all active service pricing."""
        result = await self.db.execute(
            select(ServicePricing).where(ServicePricing.is_active == True)
        )
        return result.scalars().all()

    async def get_transactions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        transaction_type: Optional[str] = None
    ) -> Tuple[List[CreditTransaction], int]:
        """Get user's credit transaction history."""
        query = select(CreditTransaction).where(
            CreditTransaction.user_id == user_id
        )

        if transaction_type:
            query = query.where(CreditTransaction.transaction_type == transaction_type)

        # Count total
        from sqlalchemy import func
        count_query = select(func.count()).select_from(
            query.subquery()
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        query = query.order_by(desc(CreditTransaction.created_at))
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        transactions = result.scalars().all()

        return transactions, total

    async def get_packages_for_user(self, user_id: str) -> List[CreditPackage]:
        """Get available credit packages for a user based on their plan."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        # Get user's current plan name
        user_plan = None
        if user and user.current_plan_id:
            from app.models.billing import Plan
            plan_result = await self.db.execute(
                select(Plan).where(Plan.id == user.current_plan_id)
            )
            plan = plan_result.scalar_one_or_none()
            if plan:
                user_plan = plan.name

        # Get all active packages
        query = select(CreditPackage).where(CreditPackage.is_active == True)
        result = await self.db.execute(query)
        all_packages = result.scalars().all()

        # Filter packages based on user's plan
        plan_order = {"demo": 0, "starter": 1, "pro": 2, "pro_plus": 3}
        user_plan_level = plan_order.get(user_plan, 0)

        available_packages = []
        for pkg in all_packages:
            if pkg.min_plan is None:
                available_packages.append(pkg)
            else:
                required_level = plan_order.get(pkg.min_plan, 0)
                if user_plan_level >= required_level:
                    available_packages.append(pkg)

        return available_packages

    async def reset_subscription_credits(self, user_id: str, credits: int) -> Dict[str, Any]:
        """Reset subscription credits (called on billing cycle)."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        old_credits = user.subscription_credits or 0
        user.subscription_credits = credits

        new_balance = await self.get_balance(user_id)

        # Record transaction for expired credits
        if old_credits > 0:
            transaction = CreditTransaction(
                user_id=user_id,
                amount=-old_credits,
                balance_after=new_balance["total"] - credits + old_credits,
                transaction_type="expiry",
                description="Monthly subscription credits expired"
            )
            self.db.add(transaction)

        # Record new credits
        transaction = CreditTransaction(
            user_id=user_id,
            amount=credits,
            balance_after=new_balance["total"],
            transaction_type="subscription",
            description="Monthly subscription credits added"
        )
        self.db.add(transaction)
        await self.db.commit()

        return new_balance

    async def expire_bonus_credits(self, user_id: str) -> Dict[str, Any]:
        """Expire bonus credits that are past their expiry date."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        if user.bonus_credits and user.bonus_credits > 0:
            if user.bonus_credits_expiry and user.bonus_credits_expiry < datetime.utcnow():
                expired_credits = user.bonus_credits
                user.bonus_credits = 0
                user.bonus_credits_expiry = None

                new_balance = await self.get_balance(user_id)

                # Record expiry transaction
                transaction = CreditTransaction(
                    user_id=user_id,
                    amount=-expired_credits,
                    balance_after=new_balance["total"],
                    transaction_type="expiry",
                    description="Bonus credits expired"
                )
                self.db.add(transaction)
                await self.db.commit()

                return new_balance

        return await self.get_balance(user_id)
