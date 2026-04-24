"""
Credit Service - Manages user credits for the VidGo platform with new pricing tiers.

Credit Deduction Priority:
1. Bonus Credits (expiring soonest first)
2. Subscription Credits (expire at month end) - DO NOT CARRY OVER TO NEXT MONTH
3. Purchased Credits (never expire)

New Features:
- Model permission checking
- Concurrent generation limits
- Monthly credit expiration (no carryover)
- Plan upgrade/downgrade logic
"""
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime, timezone, timedelta
from uuid import UUID
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_
                        

from app.core.config import get_settings
from app.models.user import User
from app.models.billing import CreditTransaction, ServicePricing, CreditPackage, Generation, Plan

settings = get_settings()


class CreditService:
    """Service for managing user credits with distributed locking and new features."""

    def __init__(self, db: AsyncSession, redis_client: Optional[redis.Redis] = None):
        self.db = db
        self.redis = redis_client

    async def get_balance(self, user_id: str) -> Dict[str, Any]:
        """Get user's credit balance breakdown with monthly expiration info."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            return {
                "subscription": 0,
                "purchased": 0,
                "bonus": 0,
                "bonus_expiry": None,
                "total": 0,
                "monthly_limit": 0,
                "monthly_used": 0,
                "subscription_expires_at": None,
            }

        subscription = user.subscription_credits or 0
        purchased = user.purchased_credits or 0
        bonus = user.bonus_credits or 0

        # Check if bonus credits have expired
        if user.bonus_credits_expiry and user.bonus_credits_expiry < datetime.now(timezone.utc):
            bonus = 0

        # Get monthly limit from user's plan
        monthly_limit = 0
        subscription_expires_at = None
        if user.current_plan_id:
            plan_result = await self.db.execute(
                select(Plan).where(Plan.id == user.current_plan_id)
            )
            plan = plan_result.scalar_one_or_none()
            if plan:
                monthly_limit = plan.monthly_credits or 0
                # Calculate when subscription credits expire (end of current month)
                if user.plan_expires_at:
                    subscription_expires_at = user.plan_expires_at
                else:
                    # Default to end of current month if not set
                    now = datetime.now(timezone.utc)
                    if now.month == 12:
                        next_month = now.replace(year=now.year + 1, month=1, day=1)
                    else:
                        next_month = now.replace(month=now.month + 1, day=1)
                    subscription_expires_at = next_month - timedelta(days=1)

        # Calculate monthly usage from transactions this month
        monthly_used = 0
        try:
            # Start of current month
            now = datetime.now(timezone.utc)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_result = await self.db.execute(
                select(func.coalesce(func.sum(CreditTransaction.amount), 0))
                .where(
                    CreditTransaction.user_id == user_id,
                    CreditTransaction.amount < 0,  # Only deductions
                    CreditTransaction.created_at >= month_start,
                    CreditTransaction.transaction_type == "generation"
                )
            )
            monthly_used = abs(monthly_result.scalar_one() or 0)
        except Exception:
            # CreditTransaction may not exist yet, ignore
            pass

        return {
            "subscription": subscription,
            "purchased": purchased,
            "bonus": bonus,
            "bonus_expiry": user.bonus_credits_expiry,
            "total": subscription + purchased + bonus,
            "monthly_limit": monthly_limit,
            "monthly_used": monthly_used,
            "subscription_expires_at": subscription_expires_at,
        }

    async def check_sufficient(self, user_id: str, amount: int) -> bool:
        """Check if user has sufficient credits and weekly limit."""
        balance = await self.get_balance(user_id)
        if balance["total"] < amount:
            return False
        # Enforce weekly limit
        weekly_limit = balance.get("weekly_limit", 0)
        weekly_used = balance.get("weekly_used", 0)
        if weekly_limit > 0 and (weekly_used + amount) > weekly_limit:
            return False
        return True

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
            if not user.bonus_credits_expiry or user.bonus_credits_expiry >= datetime.now(timezone.utc):
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
        metadata: Optional[Dict] = None,
        transaction_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add credits to user account.

        Args:
            credit_type: which bucket to credit (subscription/purchased/bonus)
            transaction_type: override for the ledger row's `transaction_type`.
                Defaults to `credit_type` when omitted. Callers that are
                restoring credits after a failed operation should pass
                `transaction_type="refund"` so analytics distinguishes a
                bonafide subscription grant from a refund-in-kind (VG-BUG-E).
        """
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
            transaction_type=transaction_type or credit_type,
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
            if user.bonus_credits_expiry and user.bonus_credits_expiry < datetime.now(timezone.utc):
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

    # ===== NEW METHODS FOR PRICING TIERS =====

    async def check_model_permission(self, user_id: str, service_type: str) -> Tuple[bool, str]:
        """
        Check if user has permission to use the model for a specific service.
        Returns: (has_permission, error_message)
        """
        # Get service pricing
        pricing = await self.get_service_pricing(service_type)
        if not pricing:
            return False, f"Service type '{service_type}' not found"

        # Get user's plan
        result = await self.db.execute(
            select(User, Plan).join(Plan, User.current_plan_id == Plan.id).where(User.id == user_id)
        )
        row = result.first()
        
        if not row:
            return False, "User or plan not found"
        
        user, plan = row

        # Check if service requires specific plan
        if pricing.min_plan:
            plan_order = {"basic": 1, "pro": 2, "premium": 3, "enterprise": 4}
            user_plan_level = plan_order.get(plan.name, 0)
            required_level = plan_order.get(pricing.min_plan, 0)
            if user_plan_level < required_level:
                return False, f"Plan '{plan.name}' does not have access to this service. Requires '{pricing.min_plan}' or higher."

        # Check model permission
        if pricing.allowed_models and plan.allowed_models:
            # Check if any of the plan's allowed models matches the service's allowed models
            has_model_access = any(
                model in plan.allowed_models for model in pricing.allowed_models
            )
            if not has_model_access:
                return False, f"Plan '{plan.name}' does not have access to models: {pricing.allowed_models}. Allowed models: {plan.allowed_models}"

        return True, ""

    async def check_concurrent_limit(self, user_id: str) -> Tuple[bool, str]:
        """
        Check if user has reached concurrent generation limit.
        Returns: (within_limit, error_message)
        """
        # Get user's plan
        result = await self.db.execute(
            select(User, Plan).join(Plan, User.current_plan_id == Plan.id).where(User.id == user_id)
        )
        row = result.first()
        
        if not row:
            return False, "User or plan not found"
        
        user, plan = row

        max_concurrent = plan.max_concurrent_generations or 1

        # Count currently processing generations
        count_result = await self.db.execute(
            select(func.count()).select_from(Generation).where(
                Generation.user_id == user_id,
                Generation.status.in_(["pending", "processing"])
            )
        )
        current_count = count_result.scalar() or 0

        if current_count >= max_concurrent:
            return False, f"Concurrent generation limit reached ({current_count}/{max_concurrent}). Please wait for current generations to complete."

        return True, ""

    async def expire_monthly_subscription_credits(self, user_id: str) -> Dict[str, Any]:
        """
        Expire monthly subscription credits (called at end of month).
        This ensures credits don't carry over to next month.
        """
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        expired_credits = user.subscription_credits or 0
        
        if expired_credits > 0:
            user.subscription_credits = 0
            
            new_balance = await self.get_balance(user_id)

            # Record expiry transaction
            transaction = CreditTransaction(
                user_id=user_id,
                amount=-expired_credits,
                balance_after=new_balance["total"],
                transaction_type="expiry",
                description="Monthly subscription credits expired (no carryover)"
            )
            self.db.add(transaction)
            await self.db.commit()

            return new_balance

        return await self.get_balance(user_id)

    async def reset_monthly_credits_for_all_users(self) -> Dict[str, Any]:
        """
        Reset monthly credits for all users with active subscriptions.
        This should be called on the 1st of each month.
        """
        # Get all users with active subscriptions
        result = await self.db.execute(
            select(User).where(
                User.current_plan_id != None,
                User.plan_expires_at >= datetime.now(timezone.utc)
            )
        )
        users = result.scalars().all()

        stats = {
            "total_users": len(users),
            "credits_expired": 0,
            "credits_added": 0,
            "errors": []
        }

        for user in users:
            try:
                # Get user's plan to know how many credits to add
                plan_result = await self.db.execute(
                    select(Plan).where(Plan.id == user.current_plan_id)
                )
                plan = plan_result.scalar_one_or_none()

                if plan:
                    # First, expire old credits
                    old_credits = user.subscription_credits or 0
                    if old_credits > 0:
                        user.subscription_credits = 0
                        stats["credits_expired"] += old_credits

                        # Record expiry transaction
                        transaction = CreditTransaction(
                            user_id=user.id,
                            amount=-old_credits,
                            balance_after=(user.purchased_credits or 0) + (user.bonus_credits or 0),
                            transaction_type="expiry",
                            description="Monthly subscription credits expired (no carryover)"
                        )
                        self.db.add(transaction)

                    # Add new monthly credits
                    new_credits = plan.monthly_credits or 0
                    if new_credits > 0:
                        user.subscription_credits = new_credits
                        stats["credits_added"] += new_credits

                        # Record new credits transaction
                        transaction = CreditTransaction(
                            user_id=user.id,
                            amount=new_credits,
                            balance_after=(user.purchased_credits or 0) + (user.bonus_credits or 0) + new_credits,
                            transaction_type="subscription",
                            description="Monthly subscription credits added"
                        )
                        self.db.add(transaction)

                    # Update plan expiration date (next month)
                    now = datetime.now(timezone.utc)
                    if now.month == 12:
                        next_month = now.replace(year=now.year + 1, month=1, day=1)
                    else:
                        next_month = now.replace(month=now.month + 1, day=1)
                    user.plan_expires_at = next_month

            except Exception as e:
                stats["errors"].append(f"User {user.id}: {str(e)}")

        await self.db.commit()
        return stats

    async def handle_plan_change(self, user_id: str, new_plan_id: str, is_upgrade: bool) -> Dict[str, Any]:
        """
        Handle plan change (upgrade or downgrade).
        - Upgrade: Add difference in credits
        - Downgrade: Keep current credits (no change until next cycle)
        """
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # Get old and new plans
        old_plan_result = await self.db.execute(
            select(Plan).where(Plan.id == user.current_plan_id)
        )
        old_plan = old_plan_result.scalar_one_or_none()

        new_plan_result = await self.db.execute(
            select(Plan).where(Plan.id == new_plan_id)
        )
        new_plan = new_plan_result.scalar_one_or_none()

        if not new_plan:
            raise ValueError("New plan not found")

        old_credits = old_plan.monthly_credits if old_plan else 0
        new_credits = new_plan.monthly_credits

        if is_upgrade:
            # Add difference in credits
            credit_diff = new_credits - old_credits
            if credit_diff > 0:
                user.subscription_credits = (user.subscription_credits or 0) + credit_diff

                # Record transaction
                transaction = CreditTransaction(
                    user_id=user_id,
                    amount=credit_diff,
                    balance_after=await self.get_balance(user_id)["total"],
                    transaction_type="subscription",
                    description=f"Plan upgrade credits added (+{credit_diff})"
                )
                self.db.add(transaction)
        # Downgrade: keep current credits (no action)

        # Update user's plan
        user.current_plan_id = new_plan_id
        user.plan_started_at = datetime.now(timezone.utc)
        
        # Set expiration to end of current month
        now = datetime.now(timezone.utc)
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        user.plan_expires_at = next_month

        await self.db.commit()
        return await self.get_balance(user_id)

    async def get_plan_comparison(self) -> List[Dict[str, Any]]:
        """Get comparison of all active plans for display."""
        result = await self.db.execute(
            select(Plan).where(Plan.is_active == True).order_by(Plan.price_twd)
        )
        plans = result.scalars().all()

        comparison = []
        for plan in plans:
            comparison.append({
                "id": plan.id,
                "name": plan.name,
                "display_name": plan.display_name,
                "price_twd": plan.price_twd,
                "monthly_credits": plan.monthly_credits,
                "allowed_models": plan.allowed_models or [],
                "max_concurrent_generations": plan.max_concurrent_generations or 1,
                "social_media_batch_posting": plan.social_media_batch_posting,
                "priority_queue": plan.priority_queue,
                "enterprise_features": plan.enterprise_features,
                "has_watermark": plan.has_watermark,
                "max_resolution": plan.max_resolution,
                "description": plan.description
            })

        return comparison
