"""
Subscription Management Service

Handles all subscription-related operations:
- Subscribe to plans (with or without payment)
- Manage subscription state
- Cancel subscriptions with refund eligibility (within 7 days)
- Credit allocation on subscription

Supports both:
1. Paddle payment integration (when keys configured)
2. Mock mode for development/testing (when keys not configured)
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession


def utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)

from app.models.user import User
from app.models.billing import Plan, Subscription, Order, CreditTransaction
from app.services.paddle_service import get_paddle_service
from app.services.ecpay.client import ECPayClient
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Refund eligibility period (7 days)
REFUND_ELIGIBILITY_DAYS = 7

# Work retention period after cancellation (7 days)
WORK_RETENTION_DAYS = 7


class SubscriptionService:
    """
    Manages user subscriptions.

    Provides:
    - Subscribe to plans (with/without payment)
    - Get subscription status
    - Cancel with refund (within 7 days)
    - Upgrade/downgrade plans
    - Credit allocation management
    """

    def __init__(self):
        self.paddle = get_paddle_service()

    # =========================================================================
    # SUBSCRIBE TO PLAN
    # =========================================================================

    async def subscribe(
        self,
        db: AsyncSession,
        user_id: UUID,
        plan_id: UUID,
        billing_cycle: str = "monthly",
        payment_method: str = "paddle",
        skip_payment: bool = False
    ) -> Dict[str, Any]:
        """
        Subscribe user to a plan with upgrade/downgrade detection.

        Upgrade (higher plan): Activate immediately, allocate new credits.
        Downgrade (lower plan): Schedule change at end of current billing period.
        Same plan: Reject.
        New subscription (no current plan): Activate normally.

        Args:
            db: Database session
            user_id: User's UUID
            plan_id: Plan's UUID
            billing_cycle: 'monthly' or 'yearly'
            payment_method: 'paddle' or 'ecpay'
            skip_payment: Skip payment and activate directly (for dev/testing)

        Returns:
            Dict with subscription info and checkout URL (if payment required)
        """
        # Get user
        user = await db.get(User, user_id)
        if not user:
            return {"success": False, "error": "User not found"}

        # Get plan
        plan = await db.get(Plan, plan_id)
        if not plan:
            return {"success": False, "error": "Plan not found"}

        # Check if already subscribed to same plan
        if user.current_plan_id == plan_id:
            current_sub = await self._get_active_subscription(db, user_id)
            if current_sub and current_sub.status == "active":
                return {
                    "success": False,
                    "error": "Already subscribed to this plan",
                    "subscription_id": str(current_sub.id)
                }

        # Detect upgrade vs downgrade vs new subscription
        change_type = await self._detect_plan_change(db, user, plan)

        if change_type == "downgrade":
            # Downgrade: schedule for end of current period
            return await self._schedule_downgrade(db, user, plan, billing_cycle)

        # For upgrade or new subscription: cancel existing and activate new
        await self._cancel_existing_subscriptions(db, user_id)

        # Determine if we should use mock mode
        use_mock = skip_payment or (self.paddle.is_mock and payment_method != 'ecpay')

        if use_mock:
            # Direct activation without payment
            return await self._activate_subscription_directly(
                db, user, plan, billing_cycle, is_upgrade=(change_type == "upgrade")
            )
        elif payment_method == 'ecpay':
            # Create ECPay checkout (Taiwan credit card)
            return await self._create_ecpay_checkout(
                db, user, plan, billing_cycle
            )
        else:
            # Create Paddle checkout
            return await self._create_payment_checkout(
                db, user, plan, billing_cycle
            )

    PLAN_LEVEL = {"demo": 0, "starter": 1, "pro": 2, "pro_plus": 3}

    async def _detect_plan_change(
        self, db: AsyncSession, user: User, new_plan: Plan
    ) -> str:
        """Detect if this is an upgrade, downgrade, or new subscription.
        Returns: 'upgrade', 'downgrade', or 'new'"""
        if not user.current_plan_id:
            return "new"

        # Only treat as upgrade/downgrade if user has an ACTIVE subscription
        active_sub = await self._get_active_subscription(db, user.id)
        if not active_sub:
            return "new"

        current_plan = await db.get(Plan, user.current_plan_id)
        if not current_plan:
            return "new"

        current_level = self.PLAN_LEVEL.get(current_plan.name, 0)
        new_level = self.PLAN_LEVEL.get(new_plan.name, 0)

        if new_level > current_level:
            return "upgrade"
        elif new_level < current_level:
            return "downgrade"
        return "new"  # Same level but different plan somehow

    async def _schedule_downgrade(
        self,
        db: AsyncSession,
        user: User,
        new_plan: Plan,
        billing_cycle: str
    ) -> Dict[str, Any]:
        """Schedule a downgrade to take effect at end of current billing period."""
        current_sub = await self._get_active_subscription(db, user.id)
        if not current_sub:
            return {"success": False, "error": "No active subscription to downgrade from"}

        current_plan = await db.get(Plan, current_sub.plan_id)
        end_date = current_sub.end_date or user.plan_expires_at

        # Store pending downgrade info
        current_sub.auto_renew = False
        # Store the scheduled downgrade plan in subscription metadata or a new field
        # For now, we create a pending subscription that activates at end_date
        pending_sub = Subscription(
            user_id=user.id,
            plan_id=new_plan.id,
            status="pending_downgrade",
            start_date=end_date,
            end_date=end_date + timedelta(days=30) if end_date else utc_now() + timedelta(days=60),
            auto_renew=True
        )
        db.add(pending_sub)
        await db.commit()

        logger.info(
            f"Downgrade scheduled: user {user.id} from {current_plan.name if current_plan else '?'} "
            f"to {new_plan.name} effective {end_date}"
        )

        return {
            "success": True,
            "subscription_id": str(pending_sub.id),
            "status": "pending_downgrade",
            "plan_name": new_plan.name,
            "effective_date": end_date.isoformat() if end_date else None,
            "is_mock": True,
            "message": (
                f"Downgrade to {new_plan.display_name or new_plan.name} scheduled. "
                f"Your current plan remains active until {end_date.strftime('%Y-%m-%d') if end_date else 'end of period'}. "
                f"New plan will activate automatically."
            )
        }

    async def _activate_subscription_directly(
        self,
        db: AsyncSession,
        user: User,
        plan: Plan,
        billing_cycle: str,
        is_upgrade: bool = False
    ) -> Dict[str, Any]:
        """
        Activate subscription without payment (mock/dev mode).

        This is used when:
        - Paddle API key is not configured
        - skip_payment=True (for testing)
        - Free plan subscription

        On upgrade: preserves purchased_credits and bonus_credits,
        sets subscription_credits to new plan level.
        """
        logger.info(f"Activating subscription directly for user {user.id} (upgrade={is_upgrade})")

        now = utc_now()

        # Calculate end date based on billing cycle
        if billing_cycle == "yearly":
            end_date = now + timedelta(days=365)
        else:
            end_date = now + timedelta(days=30)

        # Cancel any existing active subscription
        await self._cancel_existing_subscriptions(db, user.id)

        # Create new subscription
        subscription = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status="active",
            start_date=now,
            end_date=end_date,
            auto_renew=True
        )
        db.add(subscription)

        # Update user's plan reference
        user.current_plan_id = plan.id
        user.plan_started_at = now
        user.plan_expires_at = end_date

        # Clear any cancellation/retention state from previous cancel
        user.subscription_cancelled_at = None
        user.work_retention_until = None

        # Allocate subscription credits
        credits_to_add = plan.monthly_credits or plan.weekly_credits or plan.credits_per_month or 0
        old_sub_credits = user.subscription_credits or 0

        if credits_to_add > 0:
            user.subscription_credits = credits_to_add
            user.credits_reset_at = now

            # Record credit transaction
            description = f"{'Upgrade' if is_upgrade else 'Subscription'} credits for {plan.name} plan"
            if is_upgrade and old_sub_credits > 0:
                description += f" (replaced {old_sub_credits} from previous plan)"

            transaction = CreditTransaction(
                user_id=user.id,
                amount=credits_to_add,
                balance_after=user.total_credits,
                transaction_type="subscription",
                description=description,
                extra_data={
                    "plan_id": str(plan.id),
                    "plan_name": plan.name,
                    "billing_cycle": billing_cycle,
                    "is_upgrade": is_upgrade,
                    "previous_sub_credits": old_sub_credits
                }
            )
            db.add(transaction)

        await db.commit()
        await db.refresh(subscription)
        await db.refresh(user)

        logger.info(f"Subscription activated: {subscription.id}")

        msg = "Subscription activated successfully (development mode)"
        if is_upgrade:
            msg = f"Upgraded to {plan.display_name or plan.name} plan successfully (development mode)"

        return {
            "success": True,
            "subscription_id": str(subscription.id),
            "status": "active",
            "plan_name": plan.name,
            "billing_cycle": billing_cycle,
            "start_date": subscription.start_date.isoformat(),
            "end_date": subscription.end_date.isoformat(),
            "credits_allocated": credits_to_add,
            "is_mock": True,
            "is_upgrade": is_upgrade,
            "message": msg
        }

    async def _create_ecpay_checkout(
        self,
        db: AsyncSession,
        user: User,
        plan: Plan,
        billing_cycle: str
    ) -> Dict[str, Any]:
        """Create ECPay checkout form data for Taiwan credit card payment."""
        import uuid
        from datetime import datetime

        # Validate ECPay configuration
        if not settings.ECPAY_MERCHANT_ID or not settings.ECPAY_HASH_KEY or not settings.ECPAY_HASH_IV:
            logger.error("ECPay credentials not configured")
            return {"success": False, "error": "ECPay payment not configured"}

        # Get price in TWD (use price_twd if available, else convert from USD at ~32 TWD/USD)
        if billing_cycle == "yearly":
            price_usd = float(plan.price_yearly or plan.price_usd or 0)
        else:
            price_usd = float(plan.price_monthly or plan.price_usd or 0)

        # Use TWD price if available, otherwise convert
        price_twd = int(float(plan.price_twd or 0))
        if price_twd == 0:
            price_twd = max(1, int(price_usd * 32))  # Convert USD to TWD

        # Create pending subscription record
        now = utc_now()
        if billing_cycle == "yearly":
            end_date = now + timedelta(days=365)
        else:
            end_date = now + timedelta(days=30)

        subscription = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status="pending",
            start_date=now,
            end_date=end_date,
            auto_renew=True
        )
        db.add(subscription)
        await db.flush()

        # Create order record
        order_number = f"EC-{uuid.uuid4().hex[:8].upper()}"
        order = Order(
            order_number=order_number,
            user_id=user.id,
            subscription_id=subscription.id,
            amount=price_twd,
            status="pending",
            payment_method="ecpay",
            payment_data={
                "plan_id": str(plan.id),
                "plan_name": plan.name,
                "billing_cycle": billing_cycle,
                "currency": "TWD",
                "price_twd": price_twd
            }
        )
        db.add(order)
        await db.commit()

        # Create ECPay client
        ecpay_client = ECPayClient(
            merchant_id=settings.ECPAY_MERCHANT_ID,
            hash_key=settings.ECPAY_HASH_KEY,
            hash_iv=settings.ECPAY_HASH_IV,
            payment_url=settings.ECPAY_PAYMENT_URL
        )

        # Generate ECPay payment form
        trade_date = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        # Use backend URL for ReturnURL (server callback)
        return_url = f"{settings.BACKEND_URL}/api/v1/payments/ecpay/callback"
        # Use frontend URL for OrderResultURL (user-facing result page)
        order_result_url = f"{settings.FRONTEND_URL}/subscription/ecpay-result?order={order_number}"
        client_back_url = f"{settings.FRONTEND_URL}/pricing"

        payment_data = ecpay_client.create_payment(
            merchant_trade_no=order_number,
            merchant_trade_date=trade_date,
            total_amount=price_twd,
            trade_desc=f"VidGo {plan.display_name or plan.name} {billing_cycle} subscription",
            item_name=f"VidGo {plan.display_name or plan.name} Plan",
            return_url=return_url,
            order_result_url=order_result_url,
            client_back_url=client_back_url,
            choose_payment="Credit"
        )

        logger.info(f"ECPay checkout created for order: {order_number}")

        return {
            "success": True,
            "subscription_id": str(subscription.id),
            "order_number": order_number,
            "payment_method": "ecpay",
            "ecpay_form": payment_data,  # Contains action_url and params
            "status": "pending_payment",
            "is_mock": False
        }

    async def _create_payment_checkout(
        self,
        db: AsyncSession,
        user: User,
        plan: Plan,
        billing_cycle: str
    ) -> Dict[str, Any]:
        """Create Paddle checkout session for payment."""
        # Get price based on billing cycle
        if billing_cycle == "yearly":
            price = float(plan.price_yearly or plan.price_usd or 0)
        else:
            price = float(plan.price_monthly or plan.price_usd or 0)

        # Create pending subscription record
        now = utc_now()
        if billing_cycle == "yearly":
            end_date = now + timedelta(days=365)
        else:
            end_date = now + timedelta(days=30)

        subscription = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status="pending",
            start_date=now,
            end_date=end_date,
            auto_renew=True
        )
        db.add(subscription)
        await db.flush()

        # Create order record
        import uuid
        order = Order(
            order_number=f"SUB-{uuid.uuid4().hex[:8].upper()}",
            user_id=user.id,
            subscription_id=subscription.id,
            amount=price,
            status="pending",
            payment_method="paddle",
            payment_data={
                "plan_id": str(plan.id),
                "plan_name": plan.name,
                "billing_cycle": billing_cycle
            }
        )
        db.add(order)
        await db.commit()

        # Create Paddle checkout session
        # Note: In real implementation, you'd need to configure Paddle price IDs
        paddle_result = await self.paddle.create_checkout_session(
            user_id=user.id,
            user_email=user.email,
            plan_id=str(plan.id),
            price_id=f"pri_{plan.slug or plan.name}_{billing_cycle}",  # Would be real Paddle price ID
            billing_cycle=billing_cycle,
            success_url=f"{settings.FRONTEND_URL}/subscription/success?order={order.order_number}",
            cancel_url=f"{settings.FRONTEND_URL}/subscription/cancelled"
        )

        if not paddle_result.get("success"):
            # Rollback subscription and order
            subscription.status = "failed"
            order.status = "failed"
            await db.commit()
            return paddle_result

        # Store Paddle transaction ID
        order.payment_data["paddle_transaction_id"] = paddle_result.get("transaction_id")
        await db.commit()

        return {
            "success": True,
            "subscription_id": str(subscription.id),
            "order_number": order.order_number,
            "checkout_url": paddle_result.get("checkout_url"),
            "status": "pending_payment",
            "is_mock": paddle_result.get("is_mock", False)
        }

    # =========================================================================
    # GET SUBSCRIPTION STATUS
    # =========================================================================

    async def get_subscription_status(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Get user's current subscription status.

        Returns:
            Dict with subscription details and eligibility info
        """
        user = await db.get(User, user_id)
        if not user:
            return {"success": False, "error": "User not found"}

        # Get active subscription
        subscription = await self._get_active_subscription(db, user_id)

        if not subscription:
            return {
                "success": True,
                "has_subscription": False,
                "plan": None,
                "status": "none",
                "credits": {
                    "subscription": user.subscription_credits or 0,
                    "purchased": user.purchased_credits or 0,
                    "bonus": user.bonus_credits or 0,
                    "total": user.total_credits
                }
            }

        # Get plan details
        plan = await db.get(Plan, subscription.plan_id)

        # Calculate refund eligibility
        days_since_start = (utc_now() - subscription.start_date).days
        refund_eligible = days_since_start <= REFUND_ELIGIBILITY_DAYS
        refund_days_remaining = max(0, REFUND_ELIGIBILITY_DAYS - days_since_start)

        # Check for pending downgrade
        pending_downgrade = None
        pending_result = await db.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.status == "pending_downgrade"
                )
            )
            .order_by(Subscription.created_at.desc())
        )
        pending_sub = pending_result.scalars().first()
        if pending_sub:
            pending_plan = await db.get(Plan, pending_sub.plan_id)
            pending_downgrade = {
                "plan_name": pending_plan.name if pending_plan else None,
                "plan_display_name": pending_plan.display_name if pending_plan else None,
                "effective_date": pending_sub.start_date.isoformat() if pending_sub.start_date else None
            }

        return {
            "success": True,
            "has_subscription": True,
            "subscription_id": str(subscription.id),
            "status": subscription.status,
            "plan": {
                "id": str(plan.id) if plan else None,
                "name": plan.name if plan else None,
                "display_name": plan.display_name if plan else None
            },
            "start_date": subscription.start_date.isoformat() if subscription.start_date else None,
            "end_date": subscription.end_date.isoformat() if subscription.end_date else None,
            "auto_renew": subscription.auto_renew,
            "refund_eligible": refund_eligible,
            "refund_days_remaining": refund_days_remaining,
            "pending_downgrade": pending_downgrade,
            "credits": {
                "subscription": user.subscription_credits or 0,
                "purchased": user.purchased_credits or 0,
                "bonus": user.bonus_credits or 0,
                "total": user.total_credits
            }
        }

    # =========================================================================
    # CANCEL SUBSCRIPTION
    # =========================================================================

    async def cancel_subscription(
        self,
        db: AsyncSession,
        user_id: UUID,
        request_refund: bool = False
    ) -> Dict[str, Any]:
        """
        Cancel user's subscription.

        If request_refund=True and within 7 days:
            - Processes full refund via Paddle
            - Revokes subscription credits

        If request_refund=False or past 7 days:
            - Subscription remains active until end of billing period
            - No refund processed

        Args:
            db: Database session
            user_id: User's UUID
            request_refund: Whether to request a refund

        Returns:
            Dict with cancellation result
        """
        user = await db.get(User, user_id)
        if not user:
            return {"success": False, "error": "User not found"}

        # Get active subscription
        subscription = await self._get_active_subscription(db, user_id)
        if not subscription:
            return {
                "success": False,
                "error": "No active subscription found"
            }

        # Calculate refund eligibility
        days_since_start = (utc_now() - subscription.start_date).days
        refund_eligible = days_since_start <= REFUND_ELIGIBILITY_DAYS

        # Get associated order for refund
        order = await self._get_subscription_order(db, subscription.id)

        # Process refund if requested and eligible
        refund_result = None
        if request_refund:
            if not refund_eligible:
                return {
                    "success": False,
                    "error": f"Refund period expired. You can only request a refund within {REFUND_ELIGIBILITY_DAYS} days of subscription.",
                    "days_since_start": days_since_start
                }

            # Process refund
            refund_result = await self._process_refund(db, user, subscription, order)

            if refund_result.get("success"):
                # Revoke subscription credits on refund
                await self._revoke_subscription_credits(db, user)

                # Cancel immediately
                subscription.status = "cancelled"
                subscription.end_date = utc_now()

                # Clear user's plan
                user.current_plan_id = None
                user.plan_expires_at = None

                # Set 7-day work retention period
                user.subscription_cancelled_at = utc_now()
                user.work_retention_until = utc_now() + timedelta(days=WORK_RETENTION_DAYS)
        else:
            # Cancel at end of billing period (no refund)
            subscription.status = "cancelled"
            # Keep end_date as is - subscription remains active until then

            # Set work retention to 7 days after end_date
            user.subscription_cancelled_at = utc_now()
            end = subscription.end_date or utc_now()
            user.work_retention_until = end + timedelta(days=WORK_RETENTION_DAYS)

            # If using Paddle, notify them
            if order and order.payment_data.get("paddle_subscription_id"):
                await self.paddle.cancel_subscription(
                    order.payment_data["paddle_subscription_id"],
                    effective_from="next_billing_period"
                )

        subscription.auto_renew = False
        await db.commit()

        return {
            "success": True,
            "subscription_id": str(subscription.id),
            "status": subscription.status,
            "refund_processed": refund_result.get("success") if refund_result else False,
            "refund_amount": refund_result.get("amount") if refund_result else None,
            "active_until": subscription.end_date.isoformat() if subscription.end_date else None,
            "work_retention_until": user.work_retention_until.isoformat() if user.work_retention_until else None,
            "message": "Subscription cancelled successfully" + (
                " with refund" if refund_result and refund_result.get("success") else ""
            )
        }

    async def _process_refund(
        self,
        db: AsyncSession,
        user: User,
        subscription: Subscription,
        order: Optional[Order]
    ) -> Dict[str, Any]:
        """Process refund for subscription."""
        if not order:
            # No payment record - might be mock subscription
            logger.info(f"No order found for subscription {subscription.id} - mock refund")
            return {
                "success": True,
                "is_mock": True,
                "amount": 0,
                "message": "Refund processed (no payment on record)"
            }

        refund_amount = float(order.amount or 0)

        if self.paddle.is_mock:
            # Mock refund
            order.status = "refunded"
            order.payment_data["refund"] = {
                "status": "completed",
                "amount": refund_amount,
                "processed_at": utc_now().isoformat(),
                "is_mock": True
            }
            await db.commit()

            return {
                "success": True,
                "is_mock": True,
                "amount": refund_amount,
                "message": "Refund processed (mock mode)"
            }

        # Real Paddle refund
        transaction_id = order.payment_data.get("paddle_transaction_id")
        if not transaction_id:
            return {
                "success": False,
                "error": "No Paddle transaction ID found"
            }

        paddle_result = await self.paddle.create_refund(
            transaction_id=transaction_id,
            reason="customer_request",
            amount=None  # Full refund
        )

        if paddle_result.get("success"):
            order.status = "refunded"
            order.payment_data["refund"] = {
                "status": "completed",
                "paddle_refund_id": paddle_result.get("refund_id"),
                "amount": refund_amount,
                "processed_at": utc_now().isoformat()
            }
            await db.commit()

            # Record refund transaction
            transaction = CreditTransaction(
                user_id=user.id,
                amount=0,
                balance_after=user.total_credits,
                transaction_type="refund",
                description=f"Subscription refund - {refund_amount}",
                extra_data={
                    "subscription_id": str(subscription.id),
                    "order_id": str(order.id),
                    "refund_amount": refund_amount
                }
            )
            db.add(transaction)
            await db.commit()

        return {
            "success": paddle_result.get("success"),
            "amount": refund_amount if paddle_result.get("success") else 0,
            "refund_id": paddle_result.get("refund_id"),
            "error": paddle_result.get("error")
        }

    async def _revoke_subscription_credits(
        self,
        db: AsyncSession,
        user: User
    ) -> None:
        """Revoke subscription credits on refund."""
        if user.subscription_credits > 0:
            revoked = user.subscription_credits

            # Record the revocation
            transaction = CreditTransaction(
                user_id=user.id,
                amount=-revoked,
                balance_after=user.total_credits - revoked,
                transaction_type="refund",
                description="Subscription credits revoked due to refund"
            )
            db.add(transaction)

            user.subscription_credits = 0
            await db.commit()

            logger.info(f"Revoked {revoked} subscription credits from user {user.id}")

    # =========================================================================
    # WEBHOOK HANDLERS
    # =========================================================================

    async def handle_payment_success(
        self,
        db: AsyncSession,
        order_number: str,
        paddle_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle successful payment webhook from Paddle.

        Activates the subscription and allocates credits.
        """
        # Find order
        result = await db.execute(
            select(Order).where(Order.order_number == order_number)
        )
        order = result.scalar_one_or_none()

        if not order:
            logger.error(f"Order not found: {order_number}")
            return {"success": False, "error": "Order not found"}

        if order.status == "paid":
            return {"success": True, "message": "Order already processed"}

        # Update order
        order.status = "paid"
        order.paid_at = utc_now()
        order.payment_data.update(paddle_data)

        # Activate subscription
        if order.subscription_id:
            result = await db.execute(
                select(Subscription).where(Subscription.id == order.subscription_id)
            )
            subscription = result.scalar_one_or_none()

            if subscription:
                subscription.status = "active"

                # Update user
                user = await db.get(User, order.user_id)
                if user:
                    user.current_plan_id = subscription.plan_id
                    user.plan_started_at = subscription.start_date
                    user.plan_expires_at = subscription.end_date

                    # Allocate credits
                    plan = await db.get(Plan, subscription.plan_id)
                    if plan:
                        credits = plan.monthly_credits or plan.weekly_credits or 0
                        if credits > 0:
                            user.subscription_credits = credits
                            user.credits_reset_at = utc_now()

                            transaction = CreditTransaction(
                                user_id=user.id,
                                amount=credits,
                                balance_after=user.total_credits,
                                transaction_type="subscription",
                                description=f"Subscription credits for {plan.name}"
                            )
                            db.add(transaction)

        await db.commit()

        logger.info(f"Payment success processed: {order_number}")
        return {"success": True, "order_number": order_number}

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    async def _get_active_subscription(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> Optional[Subscription]:
        """Get user's active subscription (most recent active or pending)."""
        result = await db.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.status.in_(["active", "pending"])
                )
            )
            .order_by(Subscription.created_at.desc())
        )
        return result.scalars().first()

    async def _get_subscription_order(
        self,
        db: AsyncSession,
        subscription_id: UUID
    ) -> Optional[Order]:
        """Get order associated with subscription."""
        result = await db.execute(
            select(Order).where(Order.subscription_id == subscription_id)
        )
        return result.scalar_one_or_none()

    async def _cancel_existing_subscriptions(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> None:
        """Cancel all existing active/pending subscriptions for user."""
        result = await db.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.status.in_(["active", "pending"])
                )
            )
        )
        subscriptions = result.scalars().all()

        for sub in subscriptions:
            sub.status = "cancelled"
            sub.auto_renew = False

        if subscriptions:
            logger.info(f"Cancelled {len(subscriptions)} existing subscriptions for user {user_id}")


# Singleton instance
_subscription_service: Optional[SubscriptionService] = None


def get_subscription_service() -> SubscriptionService:
    """Get or create subscription service singleton."""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service
