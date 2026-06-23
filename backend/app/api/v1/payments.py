"""
Payment API Endpoints

Supports:
- PayPal: International subscription checkout, webhook handling, invoice retrieval
- ECPay: Taiwan credit card payment, callback handling
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from typing import Optional
import logging
import json
import urllib.parse

from fastapi.responses import HTMLResponse
from app.api import deps
from app.core.config import get_settings
from app.models.billing import Order, Subscription
from app.models.user import User
from app.services.paypal_service import get_paypal_service
from app.services.ecpay.client import ECPayClient

settings = get_settings()
router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize PayPal service
paypal_service = get_paypal_service()


async def _ecpay_query_confirms_paid(ecpay_client: ECPayClient, order_number: str) -> bool:
    """Confirm payment with ECPay when the callback signature cannot be trusted."""
    if not order_number:
        return False

    query_result = await ecpay_client.query_payment_async(
        order_number,
        settings.ECPAY_QUERY_URL,
    )
    trade_status = str(query_result.get("TradeStatus", ""))
    merchant_trade_no = str(query_result.get("MerchantTradeNo", ""))
    rtn_code = str(query_result.get("RtnCode", ""))
    confirmed = merchant_trade_no == order_number and (trade_status == "1" or rtn_code == "1")
    if confirmed:
        logger.info(f"ECPay query confirmed paid order after callback signature failure: {order_number}")
    else:
        logger.error(
            "ECPay query did not confirm paid order after callback signature failure: "
            f"order={order_number} TradeStatus={trade_status} RtnCode={rtn_code}"
        )
    return confirmed


# =============================================================================
# PUBLIC FEATURE FLAGS — let the SPA hide payment buttons that aren't wired up
# =============================================================================

@router.get("/methods")
async def get_payment_methods(db: AsyncSession = Depends(deps.get_db)):
    """
    Return which payment methods are actually configured in production.
    The frontend calls this on /pricing render to decide whether to show the
    PayPal button — when no credentials are configured, the button is hidden
    so users don't click it and get a mock-mode 200 with no real checkout URL.

    Resolves PayPal config through PaymentSettingsService so an admin who
    rotates credentials in /admin/settings/payment sees the change reflect
    here within ~60s without a redeploy.
    """
    from app.services.payment_settings_service import get_resolved_settings
    r = await get_resolved_settings(db)
    return {
        "paypal": {
            "enabled": bool(r.paypal_client_id) and bool(r.paypal_client_secret),
            "is_sandbox": (r.paypal_env or "sandbox").lower() != "production",
        },
        "ecpay": {
            "enabled": bool(getattr(settings, "ECPAY_MERCHANT_ID", "")) and bool(
                getattr(settings, "ECPAY_HASH_KEY", "")
            ),
            "is_sandbox": (getattr(settings, "ECPAY_ENV", "production") or "production").lower() != "production",
        },
    }


# =============================================================================
# PAYPAL ENDPOINTS
# =============================================================================

@router.post("/paypal/checkout/{order_number}")
@router.post("/paypal/checkout")
async def create_paypal_checkout(
    order_number: str,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Create PayPal checkout session for an order.

    Called when the user clicks "Pay" for a pending order.
    Returns checkout URL to redirect user to the PayPal approval page.
    """
    # Find order
    result = await db.execute(
        select(Order).where(Order.order_number == order_number)
    )
    order = result.scalars().first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if order.status == "paid":
        raise HTTPException(status_code=400, detail="Order already paid")

    price_id = order.payment_data.get("paypal_plan_id")
    if not paypal_service.is_mock and not price_id:
        logger.error("PayPal checkout requested for %s without paypal_plan_id", order.order_number)
        raise HTTPException(status_code=503, detail="Payment checkout is temporarily unavailable")

    # Create PayPal checkout
    paypal_result = await paypal_service.create_checkout_session(
        user_id=current_user.id,
        user_email=current_user.email,
        plan_id=str(order.payment_data.get("plan_id", "")),
        price_id=price_id or f"sku_{order.order_number}",
        billing_cycle=order.payment_data.get("billing_cycle", "monthly"),
        success_url=f"{settings.FRONTEND_URL}/payment/success?order={order.order_number}",
        cancel_url=f"{settings.FRONTEND_URL}/payment/cancelled",
        amount_usd=float(order.amount or 0),
    )

    if not paypal_result.get("success"):
        raise HTTPException(status_code=500, detail=paypal_result.get("error"))

    # Update order with PayPal transaction ID
    order.payment_data["paypal_transaction_id"] = paypal_result.get("transaction_id")
    await db.commit()

    return {
        "success": True,
        "checkout_url": paypal_result.get("checkout_url"),
        "is_mock": paypal_result.get("is_mock", False)
    }


# =============================================================================
# ECPAY CHECKOUT ENDPOINTS
# =============================================================================

@router.post("/ecpay/checkout/{order_number}")
@router.post("/ecpay/checkout")
async def create_ecpay_checkout(
    order_number: str,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """Create or recreate the ECPay payment form for a pending order."""
    result = await db.execute(select(Order).where(Order.order_number == order_number))
    order = result.scalars().first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if order.status == "paid":
        raise HTTPException(status_code=400, detail="Order already paid")
    if order.status not in {"pending", "failed"}:
        raise HTTPException(status_code=400, detail=f"Order cannot be paid from status '{order.status}'")

    if not (settings.ECPAY_MERCHANT_ID and settings.ECPAY_HASH_KEY and settings.ECPAY_HASH_IV):
        raise HTTPException(status_code=503, detail="ECPay checkout is temporarily unavailable")

    ecpay_client = ECPayClient(
        merchant_id=settings.ECPAY_MERCHANT_ID,
        hash_key=settings.ECPAY_HASH_KEY,
        hash_iv=settings.ECPAY_HASH_IV,
        payment_url=settings.ECPAY_PAYMENT_URL,
    )
    trade_date = (order.created_at or datetime.now()).strftime("%Y/%m/%d %H:%M:%S")
    frontend_result_url = f"{settings.FRONTEND_URL}/subscription/ecpay-result?order={order.order_number}"
    form = ecpay_client.create_payment(
        merchant_trade_no=order.order_number,
        merchant_trade_date=trade_date,
        total_amount=int(order.amount),
        trade_desc="VidGo credit purchase" if not order.subscription_id else "VidGo subscription",
        item_name=order.payment_data.get("item_name") or order.payment_data.get("package_name") or "VidGo order",
        return_url=f"{settings.BACKEND_URL}/api/v1/payments/ecpay/callback",
        order_result_url=f"{settings.BACKEND_URL}/api/v1/payments/ecpay/result-redirect",
        client_back_url=frontend_result_url,
    )
    order.payment_method = "ecpay"
    order.payment_data["ecpay_form_generated_at"] = datetime.now().isoformat()
    await db.commit()

    return {
        "success": True,
        "order_number": order.order_number,
        "ecpay_form": form,
    }


@router.post("/paypal/webhook")
async def paypal_webhook(
    request: Request,
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Handle PayPal webhooks.

    PayPal sends webhooks for:
    - PAYMENT.CAPTURE.COMPLETED      - One-time order captured
    - PAYMENT.SALE.COMPLETED         - Recurring subscription billed (renewal)
    - PAYMENT.CAPTURE.REFUNDED       - Capture refunded
    - PAYMENT.SALE.REFUNDED          - Subscription billing refunded
    - BILLING.SUBSCRIPTION.CREATED   - Subscription created
    - BILLING.SUBSCRIPTION.ACTIVATED - Subscription activated (first payment)
    - BILLING.SUBSCRIPTION.UPDATED   - Subscription changed
    - BILLING.SUBSCRIPTION.CANCELLED - Subscription cancelled
    - BILLING.SUBSCRIPTION.EXPIRED   - Subscription expired
    - BILLING.SUBSCRIPTION.PAYMENT.FAILED - Renewal payment failed
    """
    body = await request.body()

    # Verify webhook via PayPal's verify-webhook-signature API (RSA + cert chain).
    # The HMAC fallback was insecure — PayPal does NOT sign webhooks with HMAC.
    if not paypal_service.is_mock:
        verified = await paypal_service.verify_webhook_signature(body, dict(request.headers))
        if not verified:
            logger.warning("PayPal webhook signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        data = await request.json()
        event_type = data.get("event_type", "")
        event_id = data.get("id") or ""
        event_data = data.get("resource", {}) or data.get("data", {})

        # Idempotency: dedup by PayPal event id (PayPal retries up to 25x).
        # Without this, renewal events can double-credit users.
        if event_id:
            try:
                redis_client = await deps.get_redis()
                dedup_key = f"paypal:webhook:event:{event_id}"
                # SETNX with 7-day TTL (PayPal retries up to 3 days).
                claimed = await redis_client.set(dedup_key, "1", nx=True, ex=7 * 24 * 3600)
                if not claimed:
                    logger.info(f"PayPal webhook duplicate event ignored: {event_type} id={event_id}")
                    return {"success": True, "duplicate": True}
            except Exception as exc:
                # Redis down: log but do NOT block payment processing.
                logger.warning(f"PayPal webhook Redis dedup failed (continuing): {exc}")

        logger.info(f"PayPal webhook received: {event_type} id={event_id}")

        if event_type in ("PAYMENT.CAPTURE.COMPLETED", "CHECKOUT.ORDER.APPROVED"):
            await handle_transaction_completed(db, event_data)
        elif event_type == "PAYMENT.SALE.COMPLETED":
            # Recurring billing capture for an active subscription.
            await handle_subscription_renewal(db, event_data)
        elif event_type in ("PAYMENT.CAPTURE.REFUNDED", "PAYMENT.SALE.REFUNDED"):
            logger.info(f"PayPal refund webhook acknowledged: {event_id}")
        elif event_type == "BILLING.SUBSCRIPTION.CREATED":
            await handle_subscription_created(db, event_data)
        elif event_type in ("BILLING.SUBSCRIPTION.ACTIVATED", "BILLING.SUBSCRIPTION.UPDATED"):
            await handle_subscription_updated(db, event_data)
        elif event_type in (
            "BILLING.SUBSCRIPTION.CANCELLED",
            "BILLING.SUBSCRIPTION.EXPIRED",
            "BILLING.SUBSCRIPTION.PAYMENT.FAILED",
        ):
            await handle_subscription_canceled(db, event_data)
        else:
            logger.info(f"PayPal webhook event ignored (not handled): {event_type}")

        return {"success": True}

    except Exception as e:
        logger.error(f"PayPal webhook error: {e}", exc_info=True)
        # Return 200 to prevent PayPal from retrying indefinitely on app errors
        return {"success": False, "error": str(e)}


async def handle_transaction_completed(db: AsyncSession, data: dict) -> dict:
    """Handle successful payment transaction and send invoice email."""
    custom_data = data.get("custom_data", {})
    user_id = custom_data.get("user_id")
    transaction_id = data.get("id")
    if transaction_id is not None:
        transaction_id = str(transaction_id).strip('"')
    invoice_number = data.get("invoice_number", transaction_id)

    if not user_id:
        logger.warning(f"Transaction without user_id: {transaction_id}")
        return {"success": False, "error": "no user_id"}
    if not transaction_id:
        logger.warning("Transaction completed webhook missing id")
        return {"success": False, "error": "no transaction_id"}

    # Find order by transaction ID (normalize to string for JSONB comparison)
    result = await db.execute(
        select(Order).where(
            Order.payment_data["paypal_transaction_id"].astext == transaction_id
        )
    )
    order = result.scalars().first()

    if not order:
        logger.warning(f"No order found for PayPal transaction: {transaction_id}")
        return {"success": False, "error": "order not found"}

    # Idempotency: skip if already paid (duplicate webhook)
    if order.status == "paid":
        logger.info(f"Order {order.order_number} already paid — ignoring duplicate webhook")
        return {"success": True, "already_processed": True}

    from app.services.subscription_service import get_subscription_service
    subscription_service = get_subscription_service()
    await subscription_service.handle_payment_success(
        db, order.order_number, data
    )

    # --- Send Invoice Email ---
    try:
        # Get user info
        from app.models.user import User
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalars().first()

        if user:
            # Get invoice PDF URL from PayPal
            invoice_result = await paypal_service.get_invoice_pdf_url(transaction_id)
            pdf_url = invoice_result.get("pdf_url", "")

            # PayPal Orders v2 returns amount as a decimal string (e.g. "19.99"),
            # NOT cents. Read it from purchase_units[0].amount or top-level amount.
            amount = 0.0
            currency = "USD"
            try:
                amt_obj = (
                    (data.get("purchase_units") or [{}])[0].get("amount")
                    or data.get("amount")
                    or {}
                )
                amount = float(amt_obj.get("value", 0) or 0)
                currency = amt_obj.get("currency_code", "USD") or "USD"
            except Exception:
                pass
            plan_name = custom_data.get("plan_name", "VidGo Subscription")

            # Send email
            from app.services.email_service import email_service
            await email_service.send_invoice_email(
                to_email=user.email,
                invoice_number=invoice_number,
                amount=amount,
                currency=currency,
                plan_name=plan_name,
                pdf_url=pdf_url,
                username=user.full_name or user.email.split('@')[0]
            )
            logger.info(f"Invoice email sent to {user.email}")

    except Exception as e:
        logger.error(f"Failed to send invoice email: {e}")
        # Don't fail the webhook for email errors

    logger.info(f"Transaction completed: {transaction_id}")
    return {"success": True}


def _extract_paypal_custom_data(data: dict) -> dict:
    """Normalize PayPal custom metadata from custom_data or custom_id."""
    custom_data = data.get("custom_data") if isinstance(data.get("custom_data"), dict) else {}
    custom_id = data.get("custom_id")
    if isinstance(custom_id, str) and custom_id:
        try:
            parsed = json.loads(custom_id)
            if isinstance(parsed, dict):
                custom_data = {**parsed, **custom_data}
        except json.JSONDecodeError:
            pass
    if "user_id" not in custom_data and custom_data.get("u"):
        custom_data["user_id"] = custom_data["u"]
    if "plan_id" not in custom_data and custom_data.get("p"):
        custom_data["plan_id"] = custom_data["p"]
    return custom_data


async def _find_order_by_paypal_transaction(db: AsyncSession, transaction_id: str) -> Optional[Order]:
    result = await db.execute(
        select(Order).where(
            Order.payment_data["paypal_transaction_id"].astext == transaction_id
        )
    )
    return result.scalars().first()


async def _activate_paypal_subscription_order(db: AsyncSession, data: dict) -> dict:
    paypal_sub_id = data.get("id")
    if paypal_sub_id is not None:
        paypal_sub_id = str(paypal_sub_id).strip('"')
    if not paypal_sub_id:
        logger.warning("PayPal subscription webhook missing id")
        return {"success": False, "error": "no subscription id"}

    status = str(data.get("status") or "").upper()
    if status != "ACTIVE":
        logger.info(f"PayPal subscription {paypal_sub_id} status={status or 'unknown'}; waiting for ACTIVE")
        return {"success": True, "pending": True}

    order = await _find_order_by_paypal_transaction(db, paypal_sub_id)
    if not order:
        logger.warning(f"No order found for PayPal subscription: {paypal_sub_id}")
        return {"success": False, "error": "order not found"}
    if order.status == "paid":
        logger.info(f"Order {order.order_number} already paid - ignoring duplicate subscription webhook")
        return {"success": True, "already_processed": True}

    from app.services.subscription_service import get_subscription_service
    subscription_service = get_subscription_service()
    payment_payload = dict(data)
    payment_payload["paypal_subscription_id"] = paypal_sub_id
    payment_payload["custom_data"] = _extract_paypal_custom_data(data)
    await subscription_service.handle_payment_success(db, order.order_number, payment_payload)
    logger.info(f"Activated subscription order {order.order_number} from PayPal subscription {paypal_sub_id}")
    return {"success": True}


async def handle_subscription_created(db: AsyncSession, data: dict):
    """Handle subscription created event from PayPal."""
    paypal_sub_id = data.get("id")
    custom_data = _extract_paypal_custom_data(data)
    user_id = custom_data.get("user_id")
    logger.info(f"Subscription created: {paypal_sub_id} for user {user_id}")
    await _activate_paypal_subscription_order(db, data)


async def handle_subscription_updated(db: AsyncSession, data: dict):
    """Handle subscription updated event from PayPal (plan change, billing update)."""
    paypal_sub_id = data.get("id")
    status = data.get("status")
    custom_data = _extract_paypal_custom_data(data)
    user_id = custom_data.get("user_id")
    logger.info(f"Subscription updated: {paypal_sub_id} status={status} user={user_id}")
    await _activate_paypal_subscription_order(db, data)


async def handle_subscription_renewal(db: AsyncSession, data: dict):
    """
    Handle PAYMENT.SALE.COMPLETED — a recurring subscription billing capture.

    PayPal sends this every billing cycle (month/year) for an active
    subscription. The resource includes ``billing_agreement_id`` which is
    the PayPal subscription id (``I-...``) we stored on the original order.

    We refresh the user's monthly credit allotment and record a
    CreditTransaction. Idempotency is provided upstream by the webhook
    event-id Redis dedup, so this can safely be called once per renewal.
    """
    paypal_sub_id = data.get("billing_agreement_id") or data.get("billing_agreement", {}).get("id")
    if not paypal_sub_id:
        logger.warning(f"PAYMENT.SALE.COMPLETED missing billing_agreement_id: {data.get('id')}")
        return {"success": False, "error": "no billing_agreement_id"}

    paypal_sub_id = str(paypal_sub_id).strip('"')
    order = await _find_order_by_paypal_transaction(db, paypal_sub_id)
    if not order or not order.subscription_id:
        logger.warning(f"No subscription order found for renewal: {paypal_sub_id}")
        return {"success": False, "error": "subscription order not found"}

    # Load subscription + plan + user
    from app.models.billing import Subscription, Plan, CreditTransaction
    sub_result = await db.execute(select(Subscription).where(Subscription.id == order.subscription_id))
    subscription = sub_result.scalar_one_or_none()
    if not subscription or subscription.status != "active":
        logger.info(f"Renewal received for non-active subscription {paypal_sub_id}; ignoring")
        return {"success": True, "skipped": True}

    plan = await db.get(Plan, subscription.plan_id)
    user = await db.get(User, order.user_id)
    if not plan or not user:
        logger.warning(f"Renewal: missing plan/user for {paypal_sub_id}")
        return {"success": False, "error": "missing plan or user"}

    # Use the cycle-aware grant so yearly subscribers get the 11/12 prorated
    # allotment on renewal (mirrors handle_payment_success), instead of the full
    # monthly_credits every cycle.
    from app.services.subscription_service import subscription_period_credits
    billing_cycle = (
        getattr(subscription, "billing_cycle", None)
        or (order.payment_data or {}).get("billing_cycle")
        or "monthly"
    )
    credits = subscription_period_credits(plan, order.payment_method, billing_cycle)
    if credits > 0:
        # Subscription credits are a *replacement* allotment, not additive,
        # to mirror what handle_payment_success does on the first activation.
        user.subscription_credits = credits
        from app.services.subscription_service import utc_now
        user.credits_reset_at = utc_now()

        txn = CreditTransaction(
            user_id=user.id,
            amount=credits,
            balance_after=user.total_credits,
            transaction_type="subscription",
            description=f"Subscription renewal credits for {plan.name}",
            payment_id=str(data.get("id") or paypal_sub_id),
        )
        db.add(txn)

    await db.commit()
    logger.info(f"Subscription renewal processed: sub={paypal_sub_id} user={user.id} +{credits} credits")
    return {"success": True}


async def handle_subscription_canceled(db: AsyncSession, data: dict):
    """Handle subscription cancelled / expired / payment-failed events."""
    paypal_sub_id = data.get("id")
    custom_data = _extract_paypal_custom_data(data)
    user_id = custom_data.get("user_id")
    if not user_id and paypal_sub_id:
        order = await _find_order_by_paypal_transaction(db, str(paypal_sub_id).strip('"'))
        if order:
            user_id = str(order.user_id)

    if user_id:
        try:
            from app.services.subscription_service import get_subscription_service
            subscription_service = get_subscription_service()
            from uuid import UUID
            result = await subscription_service.cancel_subscription(
                db=db,
                user_id=UUID(user_id),
                request_refund=False
            )
            logger.info(f"Subscription canceled via webhook: {paypal_sub_id} user={user_id} result={result.get('success')}")
        except Exception as e:
            logger.error(f"Failed to cancel subscription via webhook: {e}")
    else:
        logger.warning(f"Subscription canceled but no user_id in custom_data: {paypal_sub_id}")


@router.get("/paypal/customer-portal")
async def get_paypal_customer_portal(
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    Get PayPal customer portal URL for self-service billing management.

    The portal allows users to:
    - View billing history
    - Update payment method
    - Download invoices
    """
    # Get or create PayPal customer
    customer_result = await paypal_service.get_or_create_customer(
        email=current_user.email,
        name=current_user.full_name
    )

    if not customer_result.get("success"):
        raise HTTPException(status_code=500, detail=customer_result.get("error"))

    # Get portal URL
    portal_result = await paypal_service.get_customer_portal_url(
        customer_id=customer_result.get("customer_id")
    )

    if not portal_result.get("success"):
        raise HTTPException(status_code=500, detail=portal_result.get("error"))

    return {
        "success": True,
        "portal_url": portal_result.get("portal_url"),
        "is_mock": portal_result.get("is_mock", False)
    }


# =============================================================================
# ECPAY ENDPOINTS
# =============================================================================

@router.post("/ecpay/callback")
async def ecpay_payment_callback(
    request: Request,
    db: AsyncSession = Depends(deps.get_db)
):
    """
    ECPay payment result callback (ReturnURL - server-side notification).

    ECPay POSTs payment result to this URL after payment is processed.
    Must return '1|OK' to acknowledge receipt.
    """
    try:
        form_data = await request.form()
        callback_data = dict(form_data)

        logger.info(f"ECPay callback received for order: {callback_data.get('MerchantTradeNo')}")
        logger.debug(f"ECPay callback data: {callback_data}")

        # Verify CheckMacValue
        if not settings.ECPAY_MERCHANT_ID or not settings.ECPAY_HASH_KEY or not settings.ECPAY_HASH_IV:
            logger.error("ECPay credentials not configured for callback verification")
            return HTMLResponse(content="0|Error", status_code=200)

        ecpay_client = ECPayClient(
            merchant_id=settings.ECPAY_MERCHANT_ID,
            hash_key=settings.ECPAY_HASH_KEY,
            hash_iv=settings.ECPAY_HASH_IV,
            payment_url=settings.ECPAY_PAYMENT_URL
        )

        # Check payment status (RtnCode=1 means success)
        rtn_code = callback_data.get("RtnCode", "0")
        order_number = callback_data.get("MerchantTradeNo", "")

        # Verify signature. If verification fails on a success callback, query
        # ECPay directly before activating; this keeps the callback secure while
        # recovering from provider encoding variants in the returned form data.
        if not ecpay_client.verify_callback(callback_data.copy()):
            logger.error(f"ECPay callback signature verification failed for order: {order_number}")
            if rtn_code != "1" or not await _ecpay_query_confirms_paid(ecpay_client, order_number):
                return HTMLResponse(content="0|SignatureError", status_code=200)

        if rtn_code == "1" and order_number:
            # Idempotency: check if order already paid (duplicate callback)
            existing_order = await db.execute(
                select(Order).where(Order.order_number == order_number)
            )
            existing = existing_order.scalars().first()
            if existing and existing.status == "paid":
                logger.info(f"ECPay callback duplicate ignored — order {order_number} already paid")
                return HTMLResponse(content="1|OK", status_code=200)

            # Payment successful - activate subscription
            from app.services.subscription_service import get_subscription_service
            subscription_service = get_subscription_service()

            result = await subscription_service.handle_payment_success(
                db,
                order_number,
                {
                    "payment_method": "ecpay",
                    "ecpay_trade_no": callback_data.get("TradeNo"),
                    "ecpay_rtn_code": rtn_code,
                    "ecpay_rtn_msg": callback_data.get("RtnMsg"),
                    "payment_type": callback_data.get("PaymentType"),
                    "payment_date": callback_data.get("PaymentDate"),
                    "trade_amt": callback_data.get("TradeAmt"),
                    "completed_at": datetime.utcnow().isoformat()
                }
            )

            if result.get("success"):
                logger.info(f"ECPay payment processed successfully: {order_number}")
            else:
                logger.error(f"ECPay payment processing failed: {result.get('error')}")
        else:
            logger.warning(f"ECPay payment failed for order {order_number}: RtnCode={rtn_code}, Msg={callback_data.get('RtnMsg')}")
            # Mark subscription and order as failed so user can retry
            if order_number:
                order_result = await db.execute(
                    select(Order).where(Order.order_number == order_number)
                )
                failed_order = order_result.scalars().first()
                if failed_order:
                    failed_order.status = "failed"
                    if failed_order.subscription_id:
                        sub_result = await db.execute(
                            select(Subscription).where(Subscription.id == failed_order.subscription_id)
                        )
                        failed_sub = sub_result.scalars().first()
                        if failed_sub:
                            failed_sub.status = "failed"
                    await db.commit()
                    logger.info(f"Marked order {order_number} and subscription as failed")

        # Must return '1|OK' to ECPay to acknowledge receipt
        return HTMLResponse(content="1|OK", status_code=200)

    except Exception as e:
        logger.error(f"ECPay callback error: {e}")
        return HTMLResponse(content="0|Error", status_code=200)


@router.api_route("/ecpay/result-redirect", methods=["GET", "POST"])
async def ecpay_payment_result_redirect(request: Request):
    """
    Browser-facing ECPay OrderResultURL target.

    ECPay can submit this URL with POST. Static frontend hosting cannot serve a
    Vue history route for POST, so this endpoint converts either GET or POST
    into a 303 redirect to the SPA result page.
    """
    order_number = request.query_params.get("order", "")
    if not order_number and request.method == "POST":
        form_data = await request.form()
        order_number = str(form_data.get("MerchantTradeNo") or form_data.get("order") or "")

    target = f"{settings.FRONTEND_URL}/subscription/ecpay-result"
    if order_number:
        target = f"{target}?order={urllib.parse.quote(order_number)}"
    return RedirectResponse(url=target, status_code=303)


@router.get("/ecpay/result")
async def ecpay_payment_result(
    order: str = "",
    db: AsyncSession = Depends(deps.get_db)
):
    """
    ECPay payment result query endpoint.

    Frontend polls this to check if ECPay payment was processed.
    Returns order status for the frontend to display.
    """
    if not order:
        return {"success": False, "error": "Order number required"}

    result = await db.execute(
        select(Order).where(Order.order_number == order)
    )
    order_obj = result.scalars().first()

    if not order_obj:
        return {"success": False, "error": "Order not found"}

    return {
        "success": True,
        "order_number": order_obj.order_number,
        "status": order_obj.status,
        "payment_method": order_obj.payment_method,
        "amount": float(order_obj.amount or 0),
        "paid_at": order_obj.paid_at.isoformat() if order_obj.paid_at else None
    }


# =============================================================================
# ORDER STATUS
# =============================================================================

@router.get("/order/{order_number}")
async def get_order_status(
    order_number: str,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """Get order status and details."""
    result = await db.execute(
        select(Order).where(Order.order_number == order_number)
    )
    order = result.scalars().first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return {
        "order_number": order.order_number,
        "status": order.status,
        "amount": float(order.amount or 0),
        "payment_method": order.payment_method,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None
    }


# =============================================================================
# MOCK PAYMENT COMPLETION (for development)
# =============================================================================

@router.post("/mock/complete/{order_number}")
async def mock_complete_payment(
    order_number: str,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Mock payment completion for development/testing.

    Only works when PayPal is in mock mode and mock completion has been
    explicitly enabled.
    """
    if not paypal_service.is_mock or not settings.PAYMENT_MOCK_COMPLETION_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Mock payment completion is disabled"
        )

    result = await db.execute(
        select(Order).where(Order.order_number == order_number)
    )
    order = result.scalars().first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if order.status == "paid":
        raise HTTPException(status_code=400, detail="Order already paid")

    # Process as if payment completed
    from app.services.subscription_service import get_subscription_service
    subscription_service = get_subscription_service()

    result = await subscription_service.handle_payment_success(
        db,
        order_number,
        {
            "status": "completed",
            "is_mock": True,
            "completed_at": datetime.utcnow().isoformat()
        }
    )

    return {
        "success": True,
        "message": "Mock payment completed",
        "order_number": order_number
    }
