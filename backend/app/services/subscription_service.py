"""
Subscription Management Service

Handles all subscription-related operations:
- Subscribe to plans (with or without payment)
- Manage subscription state
- Cancel subscriptions with refund eligibility (within 7 days)
- Credit allocation on subscription

Supports both:
1. PayPal payment integration (when keys configured)
2. Mock mode for development/testing (when keys not configured)
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession


def utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)

from app.models.user import User
from app.models.billing import Plan, Subscription, Order, CreditTransaction, Invoice
from app.services.paypal_service import get_paypal_service
from app.services.ecpay.client import ECPayClient
from app.core.config import get_settings
from app.core.test_plans import can_access_test_pro_plan, is_test_pro_plan

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
        self.paypal = get_paypal_service()

    # =========================================================================
    # SUBSCRIBE TO PLAN
    # =========================================================================

    async def subscribe(
        self,
        db: AsyncSession,
        user_id: UUID,
        plan_id: UUID,
        billing_cycle: str = "monthly",
        payment_method: str = "paypal",
        skip_payment: bool = False,
        action: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Subscribe user to a plan with upgrade/downgrade detection.

        Upgrade (higher plan): Activate immediately, allocate new credits.
        Downgrade (lower plan): Schedule change at end of current billing period.
        Same plan: Reject unless `action="refresh"` is explicitly passed by an
            admin — this prevents accidentally re-granting monthly credits
            on duplicate POSTs (VG-BUG-B).
        New subscription (no current plan): Activate normally.

        Args:
            db: Database session
            user_id: User's UUID
            plan_id: Plan's UUID
            billing_cycle: 'monthly' or 'yearly'
            payment_method: 'paypal' or 'ecpay'
            skip_payment: Skip payment and activate directly (for dev/testing)
            action: Optional admin action flag. Set to "refresh" to explicitly
                re-grant monthly credits on an already-subscribed plan.

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

        already_assigned_test_plan = user.current_plan_id == plan_id
        if is_test_pro_plan(plan) and not (can_access_test_pro_plan(user.email) or already_assigned_test_plan):
            return {"success": False, "error": "Plan not found"}

        if is_test_pro_plan(plan):
            if skip_payment and action != "refresh":
                return {"success": False, "error": "Test plan requires payment checkout"}
            if payment_method != "ecpay" and action != "refresh":
                return {"success": False, "error": "Test plan requires ECPay checkout"}

        # Check if already subscribed to same plan. Reject every duplicate
        # unless the caller is an admin path (skip_payment=True) AND has
        # explicitly asked for a credit refresh (action="refresh"). This
        # prevents the previous behaviour where any superuser-driven
        # duplicate subscribe call minted another `plan.monthly_credits`
        # with no audit trail.
        is_admin_refresh = skip_payment and action == "refresh"
        if user.current_plan_id == plan_id and not is_admin_refresh:
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

        # BUG-014: previously we ran `_cancel_existing_subscriptions` here,
        # BEFORE the user even reached the payment provider. If they then
        # pressed Back without completing payment, the old subscription was
        # already gone — the user effectively downgraded by abandoning a
        # checkout. We now only cancel the existing subscription inside the
        # zero-payment branch (`_activate_subscription_directly`) and in
        # `handle_payment_success` after the webhook confirms the new
        # payment. For checkout paths the cancellation is deferred.

        # Determine if we should use explicit direct activation mode.
        paypal_plans_configured = bool(settings.PAYPAL_PLAN_IDS)
        use_mock = skip_payment

        if payment_method == 'paypal' and not paypal_plans_configured and not use_mock:
            logger.error("PayPal checkout requested but PAYPAL_PLAN_IDS is not configured")
            return {
                "success": False,
                "error": "Payment checkout is temporarily unavailable"
            }

        if use_mock:
            # Direct activation without payment — safe to cancel previous sub
            # immediately because there's no "back from payment" scenario.
            return await self._activate_subscription_directly(
                db, user, plan, billing_cycle, is_upgrade=(change_type == "upgrade")
            )
        elif payment_method == 'ecpay':
            # Create ECPay checkout (Taiwan credit card). Existing subscription
            # stays active until ECPay confirms payment via webhook.
            return await self._create_ecpay_checkout(
                db, user, plan, billing_cycle
            )
        else:
            # Create PayPal checkout. Existing subscription stays active
            # until PayPal webhook confirms payment.
            return await self._create_payment_checkout(
                db, user, plan, billing_cycle
            )

    # Named-plan fallback rank. Used only when two plans have equal price
    # (e.g. promotional plans) and we need a tiebreaker. The authoritative
    # comparison is `plan.price_monthly` — this dict no longer gates
    # upgrade detection, so stale entries do not cause upgrade-→-downgrade
    # misclassification (VG-BUG-A).
    PLAN_LEVEL = {
        "demo": 0, "free": 0,
        "starter": 1, "basic": 1,
        "standard": 2, "pro": 2,
        "test_pro_usd_1": 2,
        "pro_plus": 3, "premium": 3,
        "enterprise": 4,
    }

    @classmethod
    def _plan_rank(cls, plan: Plan) -> float:
        """Return a comparable rank for a plan. Higher = more expensive tier.

        Primary signal is `price_monthly`; falls back to monthly_credits, then
        to the named-plan table, then 0. Using price keeps upgrade detection
        correct when plan names are rebranded (basic/pro/premium/enterprise,
        starter/standard/pro/pro_plus, …).
        """
        if is_test_pro_plan(plan):
            return 599.0

        price = getattr(plan, "price_monthly", None) or 0
        if price:
            return float(price)
        credits = getattr(plan, "monthly_credits", None) or getattr(plan, "credits_per_month", None) or 0
        if credits:
            # Scale credits into the same rough magnitude as price so they
            # tiebreak-only against a price-less plan.
            return float(credits) / 1000.0
        return float(cls.PLAN_LEVEL.get((plan.name or "").lower(), 0))

    async def _detect_plan_change(
        self, db: AsyncSession, user: User, new_plan: Plan
    ) -> str:
        """Detect if this is an upgrade, downgrade, or new subscription.
        Returns: 'upgrade', 'downgrade', 'same', or 'new'"""
        if not user.current_plan_id:
            return "new"

        # Only treat as upgrade/downgrade if user has an ACTIVE subscription
        active_sub = await self._get_active_subscription(db, user.id)
        if not active_sub:
            return "new"

        current_plan = await db.get(Plan, user.current_plan_id)
        if not current_plan:
            return "new"

        if current_plan.id == new_plan.id:
            return "same"

        current_level = self._plan_rank(current_plan)
        new_level = self._plan_rank(new_plan)

        if new_level > current_level:
            return "upgrade"
        if new_level < current_level:
            return "downgrade"
        # Equal rank, different plan id — treat as a lateral switch, which we
        # handle like a new activation (no special prorate). Previously this
        # path returned "new" silently.
        return "new"

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
        - PayPal API credentials are not configured
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
        await db.flush()  # make subscription.id available for the audit Order

        # Audit Order row — every subscription activation leaves a trail, even
        # when the payment step is skipped (mock, superuser refresh). Without
        # this, the cancel flow can't find an order to reference and /invoices
        # stays empty forever (VG-BUG-D).
        order_amount = plan.price_yearly if billing_cycle == "yearly" else plan.price_monthly
        order = Order(
            user_id=user.id,
            subscription_id=subscription.id,
            order_number=f"DIRECT-{now.strftime('%Y%m%d%H%M%S')}-{str(user.id)[:8]}-{uuid.uuid4().hex[:6]}",
            amount=order_amount or 0,
            status="complimentary",
            payment_method="direct",
            payment_data={
                "source": "direct_activation",
                "billing_cycle": billing_cycle,
                "is_upgrade": is_upgrade,
            },
            paid_at=now,
        )
        db.add(order)

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
        await db.refresh(order)
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

        # Get price in TWD. Plans store the discounted yearly TWD price
        # directly in `plan.price_yearly` (e.g. 2990 for starter = 10 ×
        # monthly with the 2-month yearly discount baked in). The earlier
        # implementation always grabbed `plan.price_twd` (monthly only)
        # regardless of cycle, so the annual checkout page charged the
        # monthly amount (BUG-013). Use `price_yearly` for yearly billing
        # and only fall back to USD-based conversion when neither field is
        # populated.
        if billing_cycle == "yearly":
            price_yearly_twd = int(float(plan.price_yearly or 0))
            if price_yearly_twd > 0:
                price_twd = price_yearly_twd
                price_usd = price_yearly_twd / 32.0
            else:
                price_usd = float(plan.price_usd or 0)
                # No yearly TWD on the plan — fall back to monthly × 12,
                # never the bare monthly amount.
                base_monthly_twd = int(float(plan.price_twd or 0))
                if base_monthly_twd > 0:
                    price_twd = base_monthly_twd * 12
                else:
                    price_twd = max(1, int(price_usd * 32))
        else:
            price_usd = float(plan.price_monthly or plan.price_usd or 0)
            price_twd = int(float(plan.price_twd or 0))
            if price_twd == 0:
                price_twd = max(1, int(price_usd * 32))

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

        # Create order record. ECPay MerchantTradeNo only accepts letters and
        # digits (no hyphens or underscores) — see error 10200031. Keep the
        # prefix inline so the format stays readable but ECPay-compatible.
        order_number = f"EC{uuid.uuid4().hex[:12].upper()}"
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
        # ECPay may POST OrderResultURL in the user's browser. Send it to the
        # backend first so FastAPI can convert the POST into a 303 GET redirect
        # to the Vue result page instead of hitting static nginx with POST.
        order_result_url = f"{settings.BACKEND_URL}/api/v1/payments/ecpay/result-redirect?order={order_number}"
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
        """Create PayPal checkout session for payment."""
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

        # Create order record. Alphanumeric-only (no hyphens) so the same
        # order_number is safe to pass to ECPay as MerchantTradeNo later.
        import uuid
        order = Order(
            order_number=f"SUB{uuid.uuid4().hex[:12].upper()}",
            user_id=user.id,
            subscription_id=subscription.id,
            amount=price,
            status="pending",
            payment_method="paypal",
            payment_data={
                "plan_id": str(plan.id),
                "plan_name": plan.name,
                "billing_cycle": billing_cycle
            }
        )
        db.add(order)
        await db.commit()

        # Resolve PayPal Plan ID from config mapping
        import json as _json
        price_map = {}
        if settings.PAYPAL_PLAN_IDS:
            try:
                price_map = _json.loads(settings.PAYPAL_PLAN_IDS)
            except Exception:
                logger.error("Failed to parse PAYPAL_PLAN_IDS config")

        price_key = f"{plan.slug or plan.name}_{billing_cycle}"
        price_id = price_map.get(price_key)
        if not price_id:
            logger.error("No PayPal Plan ID for %s", price_key)
            order.status = "failed"
            order.payment_data["failure_reason"] = "missing_paypal_plan_id"
            await db.commit()
            return {
                "success": False,
                "error": "Payment checkout is temporarily unavailable"
            }

        paypal_result = await self.paypal.create_checkout_session(
            user_id=user.id,
            user_email=user.email,
            plan_id=str(plan.id),
            price_id=price_id,
            billing_cycle=billing_cycle,
            success_url=f"{settings.FRONTEND_URL}/subscription/success?order={order.order_number}",
            cancel_url=f"{settings.FRONTEND_URL}/subscription/cancelled",
            amount_usd=price,
        )

        if not paypal_result.get("success"):
            # Rollback subscription and order
            subscription.status = "failed"
            order.status = "failed"
            await db.commit()
            return paypal_result

        # Store PayPal transaction ID
        order.payment_data["paypal_transaction_id"] = paypal_result.get("transaction_id")
        await db.commit()

        return {
            "success": True,
            "subscription_id": str(subscription.id),
            "order_number": order.order_number,
            "checkout_url": paypal_result.get("checkout_url"),
            "status": "pending_payment",
            "is_mock": paypal_result.get("is_mock", False)
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
            - Processes full refund via PayPal
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
        invoice_voided = None
        invoice_void_required_manual = False
        if request_refund:
            if not refund_eligible:
                return {
                    "success": False,
                    "error": f"Refund period expired. You can only request a refund within {REFUND_ELIGIBILITY_DAYS} days of subscription.",
                    "days_since_start": days_since_start
                }

            # Process refund
            refund_result = await self._process_refund(db, user, subscription, order)

            if not refund_result.get("success"):
                return {
                    "success": False,
                    "error": refund_result.get("error") or "Refund processing failed"
                }

            if refund_result.get("success"):
                # Revoke only subscription credits tied to the refunded
                # subscription. Purchased and registration/bonus buckets are
                # separate balances and must not be zeroed by cancellation.
                await self._revoke_subscription_credits(db, user)

                # Void the e-invoice associated with this order (if any).
                # Must be within the current bimonthly tax period; if not,
                # log a warning for admin to handle manually.
                if order:
                    try:
                        from app.services.invoice_service import void_invoice
                        inv_result = await db.execute(
                            select(Invoice).where(
                                Invoice.order_id == order.id,
                                Invoice.status.in_(["issued", "uploaded"]),
                            )
                        )
                        invoice_to_void = inv_result.scalars().first()
                        if invoice_to_void:
                            void_result = await void_invoice(
                                db=db,
                                user_id=str(user.id),
                                invoice_id=str(invoice_to_void.id),
                                reason=f"Subscription refund — order {order.order_number}",
                            )
                            if void_result.get("success"):
                                invoice_voided = True
                            else:
                                invoice_voided = False
                                invoice_void_required_manual = True
                                logger.warning(
                                    f"Could not void invoice {invoice_to_void.id} "
                                    f"for refund order {order.order_number}: "
                                    f"{void_result.get('error')} — manual voiding required"
                                )
                        else:
                            invoice_voided = None
                    except Exception as e:
                        invoice_voided = False
                        invoice_void_required_manual = True
                        logger.error(f"Invoice voiding failed for order {order.order_number}: {e}")

                    # Persist manual action flags into order.payment_data so
                    # admin dashboards can query unresolved finance tasks.
                    payment_data = dict(order.payment_data or {})
                    refund_meta = dict(payment_data.get("refund", {}) or {})
                    refund_meta.update({
                        "invoice_voided": invoice_voided,
                        "invoice_void_required_manual": invoice_void_required_manual,
                        "invoice_void_checked_at": utc_now().isoformat(),
                    })
                    payment_data["refund"] = refund_meta
                    order.payment_data = payment_data

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

            # If using PayPal, notify them
            if order and order.payment_data.get("paypal_subscription_id"):
                await self.paypal.cancel_subscription(
                    order.payment_data["paypal_subscription_id"],
                    effective_from="next_billing_period"
                )

        subscription.auto_renew = False
        await db.commit()

        # Send refund notification email (fire-and-forget — never block the response)
        if refund_result and refund_result.get("success"):
            try:
                from app.services.email_service import email_service
                await email_service.send_refund_notification(
                    to_email=user.email,
                    order_number=order.order_number if order else "N/A",
                    refund_amount=refund_result.get("amount", 0),
                    currency="TWD" if (order and order.payment_method == "ecpay") else "USD",
                    requires_manual=refund_result.get("requires_manual", False),
                    username=user.username,
                )
            except Exception as e:
                logger.error(f"Failed to send refund notification email: {e}")

        if request_refund and refund_result:
            if refund_result.get("requires_manual"):
                message = (
                    "Refund requested and subscription cancelled. "
                    "Refund requires manual processing (3-5 business days)."
                )
            elif invoice_void_required_manual:
                message = (
                    "Refund processed and subscription cancelled. "
                    "Invoice void requires manual follow-up."
                )
            else:
                message = "Refund processed and subscription cancelled immediately."
        else:
            message = (
                "Subscription cancelled. Current plan remains active until the end of the billing period."
            )

        return {
            "success": True,
            "subscription_id": str(subscription.id),
            "status": subscription.status,
            "refund_processed": refund_result.get("success") if refund_result else False,
            "refund_amount": refund_result.get("amount") if refund_result else None,
            "refund_requires_manual": refund_result.get("requires_manual", False) if refund_result else False,
            "invoice_voided": invoice_voided,
            "invoice_void_required_manual": invoice_void_required_manual,
            "active_until": subscription.end_date.isoformat() if subscription.end_date else None,
            "work_retention_until": user.work_retention_until.isoformat() if user.work_retention_until else None,
            "message": message,
        }

    async def get_manual_action_queue(
        self,
        db: AsyncSession,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List refund/invoice cases that still require manual finance action."""
        result = await db.execute(
            select(Order)
            .where(Order.status.in_(["refund_pending", "refunded"]))
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        orders = result.scalars().all()

        items: List[Dict[str, Any]] = []
        for order in orders:
            payment_data = order.payment_data or {}
            refund_meta = payment_data.get("refund", {}) or {}

            refund_status = refund_meta.get("status")
            needs_refund_manual = refund_status == "pending_manual"
            needs_invoice_void_manual = bool(refund_meta.get("invoice_void_required_manual"))

            if not needs_refund_manual and not needs_invoice_void_manual:
                continue

            user = await db.get(User, order.user_id)
            inv_result = await db.execute(
                select(Invoice)
                .where(Invoice.order_id == order.id)
                .order_by(Invoice.issued_at.desc())
            )
            invoice = inv_result.scalars().first()

            items.append({
                "order_id": str(order.id),
                "order_number": order.order_number,
                "user_id": str(order.user_id),
                "user_email": user.email if user else None,
                "amount": float(order.amount) if order.amount is not None else 0.0,
                "payment_method": order.payment_method,
                "order_status": order.status,
                "refund_status": refund_status,
                "needs_refund_manual": needs_refund_manual,
                "needs_invoice_void_manual": needs_invoice_void_manual,
                "invoice_id": str(invoice.id) if invoice else None,
                "invoice_number": invoice.invoice_number if invoice else None,
                "invoice_status": invoice.status if invoice else None,
                "invoice_period": invoice.invoice_period if invoice else None,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "updated_at": order.paid_at.isoformat() if order.paid_at else None,
                "actions_required": [
                    action for action, needed in [
                        ("process_refund", needs_refund_manual),
                        ("void_invoice", needs_invoice_void_manual),
                    ] if needed
                ],
            })

        return {
            "success": True,
            "count": len(items),
            "items": items,
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

        if self.paypal.is_mock:
            # Mock refund
            order.status = "refunded"
            payment_data = dict(order.payment_data or {})
            payment_data["refund"] = {
                "status": "completed",
                "amount": refund_amount,
                "processed_at": utc_now().isoformat(),
                "is_mock": True
            }
            order.payment_data = payment_data
            await db.commit()

            return {
                "success": True,
                "is_mock": True,
                "amount": refund_amount,
                "message": "Refund processed (mock mode)"
            }

        # Route refund by payment method
        payment_method = order.payment_method or order.payment_data.get("payment_method", "")

        if payment_method == "ecpay":
            # ECPay refund — requires manual processing by merchant
            # ECPay does not provide an automated refund API for credit card payments.
            # Mark as pending refund so admin can process manually via ECPay merchant portal.
            order.status = "refund_pending"
            payment_data = dict(order.payment_data or {})
            payment_data["refund"] = {
                "status": "pending_manual",
                "amount": refund_amount,
                "requested_at": utc_now().isoformat(),
                "note": "ECPay refunds require manual processing via merchant portal",
                "ecpay_trade_no": payment_data.get("ecpay_trade_no"),
            }
            order.payment_data = payment_data
            await db.commit()

            # Record refund transaction
            transaction = CreditTransaction(
                user_id=user.id,
                amount=0,
                balance_after=user.total_credits,
                transaction_type="refund",
                description=f"Subscription refund requested - {refund_amount} TWD (ECPay - pending manual processing)",
                extra_data={
                    "subscription_id": str(subscription.id),
                    "order_id": str(order.id),
                    "refund_amount": refund_amount,
                    "payment_method": "ecpay",
                }
            )
            db.add(transaction)
            await db.commit()

            logger.info(f"ECPay refund requested for order {order.order_number} — requires manual processing")

            return {
                "success": True,
                "amount": refund_amount,
                "message": "Refund requested. ECPay refunds are processed within 3-5 business days.",
                "requires_manual": True,
            }

        # Real PayPal refund
        transaction_id = order.payment_data.get("paypal_transaction_id")
        if not transaction_id:
            return {
                "success": False,
                "error": "No PayPal transaction ID found"
            }

        paypal_result = await self.paypal.create_refund(
            transaction_id=transaction_id,
            reason="customer_request",
            amount=None  # Full refund
        )

        if paypal_result.get("success"):
            order.status = "refunded"
            payment_data = dict(order.payment_data or {})
            payment_data["refund"] = {
                "status": "completed",
                "paypal_refund_id": paypal_result.get("refund_id"),
                "amount": refund_amount,
                "processed_at": utc_now().isoformat()
            }
            order.payment_data = payment_data
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
            "success": paypal_result.get("success"),
            "amount": refund_amount if paypal_result.get("success") else 0,
            "refund_id": paypal_result.get("refund_id"),
            "error": paypal_result.get("error")
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
        payment_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle successful payment webhook from PayPal or ECPay.

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
        payment_data = dict(order.payment_data or {})
        payment_data.update(payment_payload)
        order.payment_data = payment_data

        # Activate subscription
        if order.subscription_id:
            result = await db.execute(
                select(Subscription).where(Subscription.id == order.subscription_id)
            )
            subscription = result.scalar_one_or_none()

            if subscription:
                # BUG-014 follow-up: cancel any OTHER active subscriptions
                # for this user now that payment is confirmed. Previously
                # the subscribe endpoint did this before checkout, so a
                # user who pressed Back lost their old plan without ever
                # paying. We now defer the cancellation until here, after
                # the webhook proves the new payment went through.
                other_subs_result = await db.execute(
                    select(Subscription)
                    .where(
                        and_(
                            Subscription.user_id == order.user_id,
                            Subscription.id != subscription.id,
                            Subscription.status.in_(["active", "pending"])
                        )
                    )
                )
                for other in other_subs_result.scalars().all():
                    other.status = "cancelled"
                    other.auto_renew = False

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
        else:
            package_id = payment_data.get("package_id")
            purchased_credits = int(payment_data.get("credits") or 0)
            bonus_credits = int(payment_data.get("bonus_credits") or 0)
            if package_id and (purchased_credits > 0 or bonus_credits > 0):
                user = await db.get(User, order.user_id)
                if user:
                    payment_id = payment_data.get("ecpay_trade_no") or payment_data.get("paypal_transaction_id")
                    if purchased_credits > 0:
                        user.purchased_credits = (user.purchased_credits or 0) + purchased_credits
                        transaction = CreditTransaction(
                            user_id=user.id,
                            amount=purchased_credits,
                            balance_after=user.total_credits,
                            transaction_type="purchase",
                            package_id=UUID(str(package_id)),
                            payment_id=payment_id,
                            description=f"Purchased {purchased_credits} credits",
                        )
                        db.add(transaction)
                    if bonus_credits > 0:
                        user.bonus_credits = (user.bonus_credits or 0) + bonus_credits
                        transaction = CreditTransaction(
                            user_id=user.id,
                            amount=bonus_credits,
                            balance_after=user.total_credits,
                            transaction_type="bonus",
                            package_id=UUID(str(package_id)),
                            payment_id=payment_id,
                            description=f"Credit package bonus {bonus_credits} credits",
                        )
                        db.add(transaction)

        await db.commit()

        # Taiwan e-invoice: auto-issue (or create pending_issue record) right
        # after payment so we stay within the tax period. Runs when Giveme
        # is enabled OR the payment was made via ECPay (Taiwan local
        # payments). International PayPal payments skip this branch.
        # Failures here MUST NOT roll back the payment — log and continue.
        from app.core.config import settings
        is_taiwan_payment = (
            settings.GIVEME_ENABLED
            or (order.payment_method or "") == "ecpay"
        )
        if is_taiwan_payment:
            try:
                from app.services.invoice_service import auto_issue_invoice
                invoice_result = await auto_issue_invoice(
                    db=db,
                    user_id=str(order.user_id),
                    order_id=str(order.id),
                )
                if not invoice_result.get("success"):
                    logger.warning(
                        f"Auto-issue invoice failed for order {order_number}: "
                        f"{invoice_result.get('error')}"
                    )
            except Exception as e:
                logger.error(
                    f"Auto-issue invoice raised for order {order_number}: {e}",
                    exc_info=True,
                )

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
        """Get user's current effective subscription.

        Includes:
        - active / pending subscriptions
        - cancelled subscriptions that are still within end_date (cancel-at-period-end)
        """
        result = await db.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.status.in_(["active", "pending", "cancelled"])
                )
            )
            .order_by(Subscription.created_at.desc())
        )
        subscriptions = result.scalars().all()
        now = utc_now()
        for sub in subscriptions:
            if sub.status in ("active", "pending"):
                return sub
            if sub.status == "cancelled" and sub.end_date and sub.end_date > now:
                return sub
        return None

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
