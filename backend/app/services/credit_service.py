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
from sqlalchemy import select, desc, func, and_, update


from app.core.config import get_settings
from app.models.user import User
from app.models.billing import CreditTransaction, ServicePricing, CreditPackage, Plan

settings = get_settings()

OFFICIAL_CREDIT_PACKAGE_NAMES = ("light_pack", "standard_pack", "heavy_pack")

# In-process ServicePricing cache — service_type -> (expires_monotonic, snapshot).
# 30s TTL: price retunes tolerate a sub-minute propagation delay, and this
# removes the highest-frequency DB query in the app (one per generation).
# Per-process by design (no invalidation hook needed — nothing writes
# ServicePricing at runtime today). See get_service_pricing().
_PRICING_CACHE: Dict[str, tuple] = {}
_PRICING_CACHE_TTL_SEC = 30.0


def settle_expired_bonus(db_session, user) -> int:
    """Settle an already-expired bonus batch BEFORE adding new bonus credits.

    A stale (past) bonus_credits_expiry makes the whole bonus bucket dead:
    get_balance() displays it as 0, deduct() skips it, and the daily cleanup
    task wipes it wholesale — so any grant landing on top of it is invisible
    to the member. Zeroes the expired batch, clears the expiry, and adds the
    offsetting "expiry" ledger row (mirroring cleanup_expired_bonus_credits_task).
    Returns the expired amount (0 when nothing to settle). Caller commits.
    """
    if not (user.bonus_credits_expiry and user.bonus_credits_expiry < datetime.now(timezone.utc)):
        return 0
    expired_amount = user.bonus_credits or 0
    user.bonus_credits = 0
    user.bonus_credits_expiry = None
    if expired_amount > 0:
        db_session.add(CreditTransaction(
            user_id=user.id,
            amount=-expired_amount,
            balance_after=(user.subscription_credits or 0) + (user.purchased_credits or 0),
            transaction_type="expiry",
            description=f"Bonus credits expired ({expired_amount} credits)",
        ))
    return expired_amount


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
                # No Redis → the per-user deduct serialization lock is GONE
                # (2026-07-12 cache audit #9). Acceptable in dev, but in prod
                # this silently drops the only guard against two concurrent
                # generations double-spending the same balance. The DB path
                # (_do_deduct) still runs its own SELECT ... FOR UPDATE row
                # lock, so a true double-spend is unlikely, but log LOUDLY so
                # a prod Redis outage on the money path is never invisible.
                logger.error(
                    "credit deduct running WITHOUT Redis lock (Redis unavailable) "
                    "for user=%s service=%s amount=%s — relying on DB row lock only",
                    user_id, service_type, amount,
                )
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
        """Internal method to perform credit deduction.

        Acquires a PostgreSQL row-level lock on the user row via
        ``SELECT ... FOR UPDATE`` so concurrent deduct calls serialize at the
        DB level even if Redis is unavailable or its lock TTL expired. This is
        defense-in-depth: the Redis lock above is still the primary mutex.

        Concurrency guarantee: the balance check below runs *inside* the
        row lock, so two simultaneous /tools/short-video requests for the
        same user cannot both succeed when only one wallet has funds. The
        second caller acquires the lock after the first commits, reads the
        post-deduction balance, sees it's insufficient, and returns the
        ``Insufficient credits`` error. The balance is provably never
        driven negative. (Risk reported by ops 2026-05-20 — verified safe.)
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        user = result.scalar_one_or_none()

        if not user:
            return False, {"error": "User not found"}

        balance = await self.get_balance(user_id)

        if balance["total"] < amount:
            return False, {"error": "Insufficient credits", "balance": balance}

        remaining = amount
        deducted = {"bonus": 0, "subscription": 0, "purchased": 0}

        # 1. Deduct from bonus first (expiring soonest)
        if user.bonus_credits and user.bonus_credits > 0 and remaining > 0:
            # Check if bonus not expired
            if not user.bonus_credits_expiry or user.bonus_credits_expiry >= datetime.now(timezone.utc):
                deduct = min(user.bonus_credits, remaining)
                user.bonus_credits -= deduct
                deducted["bonus"] += deduct
                remaining -= deduct

        # 2. Deduct from subscription
        if user.subscription_credits and user.subscription_credits > 0 and remaining > 0:
            deduct = min(user.subscription_credits, remaining)
            user.subscription_credits -= deduct
            deducted["subscription"] += deduct
            remaining -= deduct

        # 3. Deduct from purchased
        if user.purchased_credits and user.purchased_credits > 0 and remaining > 0:
            deduct = min(user.purchased_credits, remaining)
            user.purchased_credits -= deduct
            deducted["purchased"] += deduct
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
            extra_data={**(metadata or {}), "deducted": deducted}
        )
        self.db.add(transaction)
        await self.db.commit()

        # Eager refund-eligibility lock: if this single generation crossed
        # the HQ-export threshold, flip the active subscription's
        # ``is_refundable`` flag to FALSE *before* the user can race to
        # /subscription/cancel?refund=true. The lazy check inside the
        # refund endpoint also runs, but doing it here closes the window
        # between "HQ render delivered" and "refund requested". Cheap:
        # one UPDATE on a single subscription row, only on HQ spend.
        try:
            from app.services.subscription_service import REFUND_HQ_EXPORT_THRESHOLD
            if amount >= REFUND_HQ_EXPORT_THRESHOLD:
                from app.models.billing import Subscription
                # NOTE: do NOT re-import datetime/timezone here. They are already
                # imported at module level (line 16). A local `from datetime
                # import datetime` rebinds `datetime` as a function-local for the
                # WHOLE of _do_deduct, so the earlier `datetime.now(...)` bonus-
                # expiry check raised UnboundLocalError ("cannot access local
                # variable 'datetime'...") and crashed every credit-deducting
                # render for users holding bonus credits.
                await self.db.execute(
                    update(Subscription)
                    .where(
                        Subscription.user_id == user_id,
                        Subscription.status.in_(["active", "pending"]),
                        Subscription.is_refundable.is_(True),
                    )
                    .values(
                        is_refundable=False,
                        refund_blocked_at=datetime.now(timezone.utc),
                        refund_blocked_reason="HQ_EXPORT_PRODUCED",
                    )
                )
                await self.db.commit()
        except Exception as exc:
            # Refund-flag write is best-effort. The lazy check at refund
            # time will catch any miss, so a failure here must NOT raise
            # back to the caller (it would block a successful generation).
            try:
                await self.db.rollback()
            except Exception:
                pass
            # Use module logger if available; fall back to print.
            try:
                import logging
                logging.getLogger(__name__).warning(
                    f"is_refundable eager-flip failed for user {user_id}: {exc}"
                )
            except Exception:
                pass

        return True, {**new_balance, "deducted": deducted}

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
            # Settle an already-expired bonus batch before adding, otherwise
            # the new credits land in a bucket that get_balance()/deduct()
            # treat as 0 and the daily cleanup task wipes wholesale.
            settle_expired_bonus(self.db, user)
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

    async def get_service_pricing(self, service_type: str):
        """Get pricing for a specific service type.

        Cached in-process for 30s (2026-07-12 cache audit #1): this runs on
        EVERY deduct via tools._check_and_deduct_credits — one DB round-trip
        per generation for a ~40-row table that only changes when ops retune
        prices (seed script / SQL; no admin write endpoint exists). Misses
        (unseeded service_types) are cached too — they are the common case
        for endpoints whose hardcoded fallback price is in use. Returns a
        detached column snapshot (SimpleNamespace), NOT a live ORM row, so a
        cached object can never raise on attribute access after its source
        session closes; callers only read columns.
        """
        import time as _time
        now = _time.monotonic()
        hit = _PRICING_CACHE.get(service_type)
        if hit is not None and hit[0] > now:
            return hit[1]

        result = await self.db.execute(
            select(ServicePricing).where(
                ServicePricing.service_type == service_type,
                ServicePricing.is_active == True
            )
        )
        row = result.scalar_one_or_none()
        snapshot = None
        if row is not None:
            from types import SimpleNamespace
            snapshot = SimpleNamespace(**{
                c.key: getattr(row, c.key) for c in ServicePricing.__table__.columns
            })
        _PRICING_CACHE[service_type] = (now + _PRICING_CACHE_TTL_SEC, snapshot)
        return snapshot

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

        # Get the official top-up packages only. Older small/medium/large rows
        # may still exist in production DBs from previous seeds, but they should
        # not be purchasable or displayed.
        query = select(CreditPackage).where(
            CreditPackage.is_active == True,
            CreditPackage.name.in_(OFFICIAL_CREDIT_PACKAGE_NAMES),
        ).order_by(CreditPackage.sort_order, CreditPackage.credits)
        result = await self.db.execute(query)
        all_packages = result.scalars().all()

        # Filter packages based on user's plan
        plan_order = {
            "demo": 0,
            "free": 0,
            "basic": 1,
            "starter": 1,
            "standard": 1,
            "pro": 2,
            "premium": 3,
            "pro_plus": 3,
            "enterprise": 4,
        }
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

        2026-07 policy: any ACTIVE plan (basic/pro/premium/enterprise) may use
        every model/service — per-model credit pricing already covers the
        upstream cost, so credits are the only gate for subscribers. Only
        free/demo plan holders are still held to min_plan / allowed_models.
        (Mirrors plan_gates.require_model_access, the enforcement-path gate.)
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

        if (plan.name or "").strip().lower() not in ("free", "demo"):
            # Any real subscription unlocks every model — credits gate.
            return True, ""

        # Free/demo plan: keep the legacy min_plan + allowed_models floors.
        # Free/zero-credit services must remain available when their credit
        # price is 0.
        if pricing.min_plan and (pricing.credit_cost or 0) > 0:
            plan_order = {
                "free": 0,
                "basic": 1,
                "starter": 1,
                "pro": 2,
                "pro_plus": 3,
                "test_pro_usd_1": 3,
                "premium": 3,
                "enterprise": 4,
            }
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

        Counts ``pending_provider_tasks`` rows in an active status
        ("submitting"/"polling"). The old implementation counted the legacy
        ``generations`` table, which no code path writes — the limit was a
        platform-wide no-op (2026-07-10 audit). Pending rows are written by
        every long-running tool (short_video / kling_video / ai_avatar /
        try_on / claymation / upscale / recolor / interior growth) right
        after deduction, which is exactly the set worth limiting; sub-minute
        image jobs don't create rows and stay unthrottled by design.

        The count window is bounded to the reclaim worker's abandon horizon
        (worker.RECLAIM_MAX_AGE_HOURS = 6h): if the worker is down and rows
        rot in "submitting", they stop blocking the user after 6h.
        """
        # LEFT-join the plan: users with no current_plan_id (free registrants,
        # lapsed subscriptions holding purchased credits) must NOT be hard-
        # rejected here — the old inner join returned "User or plan not found"
        # for them. They get the default limit of 1 instead.
        result = await self.db.execute(
            select(User, Plan)
            .outerjoin(Plan, User.current_plan_id == Plan.id)
            .where(User.id == user_id)
        )
        row = result.first()

        if not row:
            return False, "User not found"

        user, plan = row

        max_concurrent = (plan.max_concurrent_generations if plan else None) or 1

        from app.models.pending_provider_task import PendingProviderTask

        window_start = datetime.now(timezone.utc) - timedelta(hours=6)
        count_result = await self.db.execute(
            select(func.count()).select_from(PendingProviderTask).where(
                PendingProviderTask.user_id == user.id,
                PendingProviderTask.status.in_(["submitting", "polling"]),
                PendingProviderTask.created_at >= window_start,
            )
        )
        current_count = count_result.scalar() or 0

        if current_count >= max_concurrent:
            return False, (
                f"Concurrent generation limit reached ({current_count}/{max_concurrent}). "
                "Please wait for current generations to complete."
            )

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

        2026-06 margin pass:
        - Yearly subscribers get a prorated monthly grant (11/12 of full)
          because price_yearly is 10 × price_monthly (2 free months). Without
          this proration a yearly subscriber paying $322 receives 14,400
          credits (12 × 1,200) → $0.0224/credit, undercutting heavy_pack
          ($0.033/credit) and every subscription tier.
        - For yearly subscribers do NOT overwrite plan_expires_at — the
          old logic clamped it to next_month, silently truncating yearly
          plans into monthly rentals.
        """
        from app.models.billing import Subscription

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

                # Determine billing cycle from the most recent active subscription.
                sub_res = await self.db.execute(
                    select(Subscription)
                    .where(
                        Subscription.user_id == user.id,
                        Subscription.status == "active",
                    )
                    .order_by(desc(Subscription.start_date))
                    .limit(1)
                )
                sub = sub_res.scalar_one_or_none()
                billing_cycle = (getattr(sub, "billing_cycle", None) if sub else "monthly") or "monthly"
                is_yearly = billing_cycle == "yearly"

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

                    # Add new credits. Currency-aware: ECPay (TWD) subscribers
                    # get the smaller TWD allowance (anti-arbitrage); yearly
                    # stays 11/12-prorated. See subscription_period_credits.
                    from app.models.billing import Order as _Order
                    from app.services.subscription_service import (
                        subscription_period_credits as _period_credits,
                    )
                    _ord = None
                    if sub is not None:
                        _ord = (await self.db.execute(
                            select(_Order)
                            .where(_Order.subscription_id == sub.id)
                            .order_by(_Order.created_at.desc())
                        )).scalars().first()
                    new_credits = _period_credits(
                        plan, _ord.payment_method if _ord else None, billing_cycle
                    )
                    if new_credits > 0:
                        user.subscription_credits = new_credits
                        stats["credits_added"] += new_credits

                        # Record new credits transaction
                        transaction = CreditTransaction(
                            user_id=user.id,
                            amount=new_credits,
                            balance_after=(user.purchased_credits or 0) + (user.bonus_credits or 0) + new_credits,
                            transaction_type="subscription",
                            description=(
                                "Yearly subscription monthly top-up (11/12 prorated)"
                                if is_yearly
                                else "Monthly subscription credits added"
                            )
                        )
                        self.db.add(transaction)

                    # Only roll plan_expires_at forward for monthly subs.
                    # Yearly subs already have a year-out expiry from
                    # subscription activation; clamping to next_month here
                    # turned annual contracts into rolling monthly ones.
                    if not is_yearly:
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
