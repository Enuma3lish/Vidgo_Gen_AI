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
from sqlalchemy import cast, String
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import BaseModel
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

    # Update order with PayPal transaction ID (dual-write: JSON for back-compat
    # + the indexed column the webhook lookup uses — perf audit #7).
    order.payment_data["paypal_transaction_id"] = paypal_result.get("transaction_id")
    order.paypal_transaction_id = paypal_result.get("transaction_id")
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

    # 2026-07-10 — cross-gateway currency guard. PayPal orders store USD
    # amounts (19.99 / 239.88); ECPay charges the raw number as NT$. Routing
    # a USD order through this endpoint charged NT$19 for a US$19.99 plan
    # (~32× underpayment) and the signed callback then provisioned the full
    # plan. ECPay checkout is only valid for orders created for TWD/ECPay.
    _pd = order.payment_data or {}
    if (order.payment_method or "").lower() == "paypal" or any(
        str(k).startswith("paypal") for k in _pd.keys()
    ):
        raise HTTPException(
            status_code=400,
            detail="This order was created for PayPal (USD). Please start a new checkout to pay with ECPay.",
        )
    if order.amount is None or order.amount != int(order.amount):
        # NT$ amounts are whole numbers; a fractional amount means the order
        # was priced in a foreign currency.
        raise HTTPException(status_code=400, detail="Order amount is not a valid TWD amount for ECPay.")

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

    # Pick up admin-editable DB credential overrides BEFORE the is_mock gate
    # (2026-07-10). is_mock is derived from env at import time; in a
    # deployment whose PayPal creds live only in the payment_settings row,
    # the old order left the webhook permanently "mock" — signature
    # verification skipped while checkout (which does refresh) worked, so
    # anyone could post forged PAYMENT.CAPTURE.COMPLETED events. Best-effort:
    # a DB hiccup must not drop a legitimate webhook when env creds exist.
    try:
        await paypal_service.refresh_from_db(db)
    except Exception as exc:
        logger.warning("PayPal webhook: refresh_from_db failed (using env creds): %s", exc)

    # Verify webhook via PayPal's verify-webhook-signature API (RSA + cert chain).
    # The HMAC fallback was insecure — PayPal does NOT sign webhooks with HMAC.
    if not paypal_service.is_mock:
        verified = await paypal_service.verify_webhook_signature(body, dict(request.headers))
        if not verified:
            logger.warning("PayPal webhook signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")

    dedup_key = None
    redis_client = None
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

            # Durable dedup belt (perf audit #7/#10): if Redis was unavailable
            # above, a unique INSERT on the event id still stops a reprocess.
            # Best-effort + own transaction so it never blocks a legitimate
            # event; a conflict means we already handled this id.
            try:
                from app.models.billing import ProcessedWebhookEvent
                from sqlalchemy.dialects.postgresql import insert as _pg_insert
                stmt = _pg_insert(ProcessedWebhookEvent).values(
                    event_id=str(event_id), provider="paypal",
                ).on_conflict_do_nothing(index_elements=["event_id"])
                res = await db.execute(stmt)
                await db.commit()
                if (res.rowcount or 0) == 0:
                    logger.info(f"PayPal webhook duplicate (DB belt) ignored: {event_type} id={event_id}")
                    return {"success": True, "duplicate": True}
            except Exception as exc:
                await db.rollback()
                logger.warning(f"PayPal webhook DB dedup skipped (continuing): {exc}")

        logger.info(f"PayPal webhook received: {event_type} id={event_id}")

        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            await handle_transaction_completed(db, event_data)
        elif event_type == "CHECKOUT.ORDER.APPROVED":
            # Approval moves NO money — the merchant must capture. Routing
            # this into the "completed" handler (as the old code did) would
            # grant credits without ever charging the buyer.
            await handle_order_approved(db, event_data)
        elif event_type == "PAYMENT.SALE.COMPLETED":
            # Recurring billing capture for an active subscription.
            await handle_subscription_renewal(db, event_data)
        elif event_type == "PAYMENT.CAPTURE.REFUNDED":
            # One-time capture (credit pack) refunded at PayPal — claw back
            # the granted credits. Was log-only until 2026-07-10: a console
            # refund returned the money while the user kept the credits.
            await handle_capture_refunded(db, event_data)
        elif event_type == "PAYMENT.SALE.REFUNDED":
            # Subscription billing refunded — cancel the local subscription
            # and strip this cycle's credits. Was log-only until 2026-07-10.
            await handle_sale_refunded(db, event_data)
        elif event_type == "BILLING.SUBSCRIPTION.CREATED":
            await handle_subscription_created(db, event_data)
        elif event_type in ("BILLING.SUBSCRIPTION.ACTIVATED", "BILLING.SUBSCRIPTION.UPDATED"):
            await handle_subscription_updated(db, event_data)
        elif event_type == "BILLING.SUBSCRIPTION.PAYMENT.FAILED":
            # 2026-07-10: a single failed billing attempt is RETRYABLE — PayPal
            # retries on its own schedule and sends SUSPENDED/CANCELLED if it
            # finally gives up. The old code cancelled the local subscription
            # immediately, so when PayPal's retry then succeeded, the SALE
            # webhook found a cancelled sub and skipped the renewal — the user
            # was charged and received nothing.
            logger.warning(
                "PayPal billing attempt failed for %s — awaiting PayPal retry / final status",
                event_data.get("billing_agreement_id") or event_data.get("id"),
            )
        elif event_type in (
            "BILLING.SUBSCRIPTION.CANCELLED",
            "BILLING.SUBSCRIPTION.EXPIRED",
            "BILLING.SUBSCRIPTION.SUSPENDED",
        ):
            await handle_subscription_canceled(db, event_data)
        elif event_type.startswith("BILLING.PLAN.") or event_type.startswith("CATALOG.PRODUCT."):
            # A plan's price / product definition changed in PayPal — drop the
            # cached USD prices so /pricing reflects the new price immediately
            # rather than after the TTL. Best-effort accelerator; the price
            # cache TTL remains the guaranteed path (PayPal does not always
            # emit these events for a pricing-scheme update).
            from app.services.paypal_pricing import invalidate_cache as invalidate_paypal_price_cache
            invalidate_paypal_price_cache()
            logger.info("PayPal plan/catalog event %s — invalidated USD price cache", event_type)
        else:
            logger.info(f"PayPal webhook event ignored (not handled): {event_type}")

        return {"success": True}

    except Exception as e:
        logger.error(f"PayPal webhook error: {e}", exc_info=True)
        # 2026-07-10: release the dedup claim and return 500 so PayPal RETRIES.
        # The old behavior (claim first, ack 200 on error) permanently dropped
        # a paid event on any transient DB hiccup — user charged, never
        # provisioned (the admin reprovision tool existed to patch exactly
        # this). Signature-verified garbage still gets acked above via the
        # normal branches; only processing failures reach here.
        if dedup_key and redis_client is not None:
            try:
                await redis_client.delete(dedup_key)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="Webhook processing failed; please retry")


async def _send_paypal_invoice_email(
    db: AsyncSession,
    user_id,
    transaction_id: Optional[str],
    invoice_number: Optional[str],
    amount: float,
    currency: str,
    plan_name: str,
) -> None:
    """Best-effort invoice email after a PayPal payment. Never raises."""
    try:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalars().first()
        if not user:
            return

        invoice_result = await paypal_service.get_invoice_pdf_url(transaction_id)
        pdf_url = invoice_result.get("pdf_url", "")

        from app.services.email_service import email_service
        await email_service.send_invoice_email(
            to_email=user.email,
            invoice_number=invoice_number or transaction_id or "",
            amount=amount,
            currency=currency,
            plan_name=plan_name,
            pdf_url=pdf_url,
            username=user.full_name or user.email.split('@')[0]
        )
        logger.info(f"Invoice email sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send invoice email: {e}")


def _paypal_amount_from(data: dict) -> tuple:
    """(amount, currency) from an Orders-v2 order or capture resource.

    PayPal returns the amount as a decimal string (e.g. "19.99"), NOT cents.
    """
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
    return amount, currency


async def handle_transaction_completed(db: AsyncSession, data: dict) -> dict:
    """Handle PAYMENT.CAPTURE.COMPLETED — a one-time Orders-v2 capture.

    The webhook resource here is the CAPTURE, not the order: ``data["id"]``
    is the capture id, while the order id our checkout stored as
    ``paypal_transaction_id`` arrives in ``supplementary_data.related_ids
    .order_id``; buyer metadata arrives as a ``custom_id`` JSON string.
    The old reads (``data["custom_data"]`` — a field PayPal never sends —
    and matching orders on the capture id) matched nothing, so this handler
    never completed a purchase end-to-end (2026-07-10 audit).
    """
    custom_data = _extract_paypal_custom_data(data)
    capture_id = data.get("id")
    if capture_id is not None:
        capture_id = str(capture_id).strip('"')
    related_ids = (data.get("supplementary_data") or {}).get("related_ids") or {}
    # Capture events carry the order id in related_ids; fall back to the
    # resource id itself so order-shaped payloads (mock mode, manual replays)
    # still resolve.
    order_lookup_id = str(related_ids.get("order_id") or capture_id or "")

    if not order_lookup_id:
        logger.warning("PAYMENT.CAPTURE.COMPLETED webhook missing capture/order id")
        return {"success": False, "error": "no transaction_id"}

    order = await _find_order_by_paypal_transaction(db, order_lookup_id)
    if not order:
        logger.warning(f"No order found for PayPal transaction: {order_lookup_id}")
        return {"success": False, "error": "order not found"}

    # Idempotency: skip if already paid (duplicate webhook, or the APPROVED
    # webhook / return-leg capture endpoint already completed it)
    if order.status == "paid":
        logger.info(f"Order {order.order_number} already paid — ignoring duplicate webhook")
        return {"success": True, "already_processed": True}

    # The resource id on a CAPTURE.COMPLETED event IS the capture id — index it
    # so a later REFUNDED webhook resolves this order directly (perf audit #7).
    if capture_id:
        order.paypal_capture_id = capture_id
    from app.services.subscription_service import get_subscription_service
    await get_subscription_service().handle_payment_success(
        db, order.order_number, data
    )

    amount, currency = _paypal_amount_from(data)
    await _send_paypal_invoice_email(
        db,
        custom_data.get("user_id") or order.user_id,
        capture_id,
        data.get("invoice_number", capture_id),
        amount,
        currency,
        custom_data.get("plan_name")
        or (order.payment_data or {}).get("package_name")
        or "VidGo Purchase",
    )

    logger.info(f"Transaction completed: {order_lookup_id}")
    return {"success": True}


async def handle_order_approved(db: AsyncSession, data: dict) -> dict:
    """Handle CHECKOUT.ORDER.APPROVED — buyer approved a one-time order.

    Approval only authorizes; the money moves when WE capture. This is the
    webhook-driven capture path, so a credit-pack purchase completes even
    when the buyer closes the tab instead of returning to our success page.
    The return-leg endpoint (/paypal/capture) does the same for the fast
    path — both are idempotent (capture_order normalizes
    ORDER_ALREADY_CAPTURED; handle_payment_success is FOR-UPDATE +
    already-paid guarded).
    """
    order_id = data.get("id")
    if order_id is not None:
        order_id = str(order_id).strip('"')
    if not order_id:
        return {"success": False, "error": "no order id"}

    order = await _find_order_by_paypal_transaction(db, order_id)
    if not order:
        # Not one of our one-time orders (e.g. a subscription approval
        # travels through BILLING.SUBSCRIPTION.* instead) — acknowledge.
        logger.info(f"CHECKOUT.ORDER.APPROVED for unknown PayPal order {order_id} — ignored")
        return {"success": True, "ignored": True}
    if order.status == "paid":
        return {"success": True, "already_processed": True}

    capture = await paypal_service.capture_order(order_id)
    if not capture.get("success") or capture.get("status") != "COMPLETED":
        # Raise → the webhook handler releases the dedup key and returns 500,
        # so PayPal redelivers the approval and the capture is re-attempted.
        raise RuntimeError(
            f"PayPal capture failed for order {order.order_number}: "
            f"{capture.get('error') or capture.get('status')}"
        )

    order_data = capture.get("order") or {}
    pu = (order_data.get("purchase_units") or [{}])[0]
    cap = ((pu.get("payments") or {}).get("captures") or [{}])[0]
    # Record the indexed capture id so a later REFUNDED webhook resolves this
    # order without the LIKE scan (perf audit #7). Set before handle_payment_
    # success commits.
    if cap.get("id"):
        order.paypal_capture_id = str(cap["id"])
    from app.services.subscription_service import get_subscription_service
    await get_subscription_service().handle_payment_success(
        db, order.order_number, order_data
    )

    amount, currency = _paypal_amount_from(order_data)
    await _send_paypal_invoice_email(
        db,
        order.user_id,
        cap.get("id") or order_id,
        cap.get("id") or order_id,
        amount,
        currency,
        (order.payment_data or {}).get("package_name") or "VidGo Purchase",
    )

    logger.info(f"PayPal order captured via APPROVED webhook: {order.order_number}")
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
    # Indexed lookup first (perf audit #7) — was a full seq scan casting the
    # payment_data JSON on every PayPal webhook. Fall back to the JSON scan
    # only for rows created before the column backfill (rare, transitional).
    result = await db.execute(
        select(Order).where(Order.paypal_transaction_id == transaction_id).limit(1)
    )
    order = result.scalars().first()
    if order:
        return order
    result = await db.execute(
        select(Order).where(
            cast(Order.payment_data, JSONB)["paypal_transaction_id"].astext == transaction_id
        ).limit(1)
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
    from app.services.subscription_service import utc_now
    credits = subscription_period_credits(plan, order.payment_method, billing_cycle)
    if credits > 0:
        # Subscription credits are a *replacement* allotment, not additive,
        # to mirror what handle_payment_success does on the first activation.
        user.subscription_credits = credits
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

    # 2026-07-10: extend the LOCAL paid-through date on every real billing
    # capture. Previously nothing moved subscription.end_date on renewal, so
    # the local period lapsed one cycle after activation and the daily worker
    # blind-extended it (now it only extends what PayPal confirms). Anchor on
    # the later of (current end_date, now) so late captures don't leave the
    # period already expired.
    period = timedelta(days=365 if billing_cycle == "yearly" else 30)
    _now = utc_now()
    anchor = subscription.end_date or _now
    if anchor < _now:
        anchor = _now
    # PayPal fires SALE.COMPLETED for the INITIAL payment too (2026-07-10
    # round 5): activation already set end_date = start + period, so blindly
    # extending here left the local paid-through date one full cycle ahead
    # forever. If end_date already covers (now + period − 3d slack) this SALE
    # is the initial capture or a duplicate — the credit grant above is a
    # replacement (harmless to repeat) but the period must NOT extend again.
    if subscription.end_date and subscription.end_date >= _now + period - timedelta(days=3):
        logger.info(
            "Renewal %s: end_date %s already covers this period — initial-payment "
            "SALE, extension skipped", paypal_sub_id, subscription.end_date,
        )
    else:
        subscription.end_date = anchor + period
        user.plan_expires_at = subscription.end_date

    await db.commit()
    logger.info(f"Subscription renewal processed: sub={paypal_sub_id} user={user.id} +{credits} credits")
    return {"success": True}


async def handle_subscription_canceled(db: AsyncSession, data: dict):
    """Handle subscription cancelled / expired / suspended events.

    2026-07-10 rewrite: act on THE subscription the webhook is about, resolved
    via the order that stored this PayPal agreement id — NOT on "the user's
    newest active subscription". The old code cancelled by user_id, so after a
    plan upgrade a late CANCELLED event for the OLD agreement cancelled the
    NEW plan locally, and its no-refund path then called PayPal to cancel the
    NEW agreement too — actively terminating the plan the user was paying for.
    Remote paypal.cancel is never needed here: PayPal itself sent the event.
    """
    from app.models.billing import Subscription, CreditTransaction

    paypal_sub_id = str(data.get("id") or "").strip('"')
    if not paypal_sub_id:
        logger.warning("Subscription-cancelled webhook without a subscription id; ignoring")
        return

    order = await _find_order_by_paypal_transaction(db, paypal_sub_id)
    if not order or not order.subscription_id:
        logger.warning(f"Subscription canceled but no local subscription found for {paypal_sub_id}")
        return

    sub = await db.get(Subscription, order.subscription_id)
    if not sub or sub.status not in ("active", "pending"):
        # Already terminal (e.g. superseded by an upgrade) — nothing to do.
        logger.info(f"Cancel webhook for {paypal_sub_id}: local sub already {getattr(sub, 'status', 'missing')}")
        return

    sub.status = "cancelled"
    sub.auto_renew = False

    # Only touch the user's plan/credits if the cancelled sub was their
    # CURRENT entitlement (no other active subscription remains).
    user = await db.get(User, sub.user_id)
    if user:
        other_active = (await db.execute(
            select(Subscription.id).where(
                Subscription.user_id == user.id,
                Subscription.id != sub.id,
                Subscription.status == "active",
            ).limit(1)
        )).scalar_one_or_none()
        if other_active is None and user.current_plan_id == sub.plan_id:
            user.current_plan_id = None
            old_credits = user.subscription_credits or 0
            if old_credits > 0:
                user.subscription_credits = 0
                db.add(CreditTransaction(
                    user_id=user.id,
                    amount=-old_credits,
                    balance_after=(user.purchased_credits or 0) + (user.bonus_credits or 0),
                    transaction_type="expiry",
                    description="Subscription cancelled at PayPal — unused subscription credits removed",
                ))

    await db.commit()
    logger.info(f"Subscription canceled via webhook: {paypal_sub_id} sub={sub.id} user={sub.user_id}")


async def _revoke_order_grants(
    db: AsyncSession,
    order: Order,
    *,
    reason: str,
    refund_amount: Optional[float] = None,
    actor: str = "webhook",
) -> dict:
    """Reverse what a PAID order granted, after the money went back.

    Credit packs (no subscription_id): claw back the purchased + bonus
    credits recorded on the order — pro-rata when `refund_amount` covers only
    part of `order.amount`, and always clamped at what the user still holds
    (spent credits are not driven negative). Subscription orders: cancel the
    subscription and strip the plan/credits with the same only-if-current
    rules as the CANCELLED webhook. Idempotent via order.status ==
    "refunded". Shared by the PayPal refund webhooks and the admin
    mark-refunded endpoint (the ECPay parity path — ECPay sends no refund
    notification, so its clawback is admin-triggered after the portal
    refund). Caller does NOT need to commit; this commits.
    """
    if order.status == "refunded":
        return {"success": True, "already_processed": True}

    from app.models.billing import Subscription, CreditTransaction

    pdata = dict(order.payment_data or {})
    user = await db.get(User, order.user_id)
    revoked_purchased = revoked_bonus = revoked_subscription = 0

    if order.subscription_id:
        sub = await db.get(Subscription, order.subscription_id)
        if sub and sub.status in ("active", "pending"):
            sub.status = "cancelled"
            sub.auto_renew = False
            if user:
                other_active = (await db.execute(
                    select(Subscription.id).where(
                        Subscription.user_id == user.id,
                        Subscription.id != sub.id,
                        Subscription.status == "active",
                    ).limit(1)
                )).scalar_one_or_none()
                if other_active is None and user.current_plan_id == sub.plan_id:
                    user.current_plan_id = None
                    revoked_subscription = int(user.subscription_credits or 0)
                    if revoked_subscription > 0:
                        user.subscription_credits = 0
                        db.add(CreditTransaction(
                            user_id=user.id,
                            amount=-revoked_subscription,
                            balance_after=(user.purchased_credits or 0) + (user.bonus_credits or 0),
                            transaction_type="refund",
                            description=f"Refund clawback: {reason}",
                        ))
    else:
        granted_purchased = int(pdata.get("credits") or 0)
        granted_bonus = int(pdata.get("bonus_credits") or 0)
        ratio = 1.0
        try:
            if refund_amount is not None and float(order.amount or 0) > 0:
                ratio = max(0.0, min(1.0, float(refund_amount) / float(order.amount)))
        except Exception:
            ratio = 1.0
        if user:
            take_p = int(round(granted_purchased * ratio))
            take_b = int(round(granted_bonus * ratio))
            revoked_purchased = min(take_p, int(user.purchased_credits or 0))
            revoked_bonus = min(take_b, int(user.bonus_credits or 0))
            if revoked_purchased > 0:
                user.purchased_credits = int(user.purchased_credits or 0) - revoked_purchased
            if revoked_bonus > 0:
                user.bonus_credits = int(user.bonus_credits or 0) - revoked_bonus
            if revoked_purchased or revoked_bonus:
                from uuid import UUID as _UUID
                _pkg = None
                try:
                    _pkg = _UUID(str(pdata.get("package_id"))) if pdata.get("package_id") else None
                except Exception:
                    _pkg = None
                db.add(CreditTransaction(
                    user_id=user.id,
                    amount=-(revoked_purchased + revoked_bonus),
                    balance_after=user.total_credits,
                    transaction_type="refund",
                    package_id=_pkg,
                    description=f"Refund clawback: {reason}",
                ))

    order.status = "refunded"
    pdata.update({
        "refund_reason": reason,
        "refund_actor": actor,
        "refunded_at": datetime.now(timezone.utc).isoformat(),
    })
    order.payment_data = pdata
    await db.commit()

    logger.info(
        "Order %s refund clawback (%s): purchased=-%d bonus=-%d subscription=-%d",
        order.order_number, actor, revoked_purchased, revoked_bonus, revoked_subscription,
    )
    return {
        "success": True,
        "order_number": order.order_number,
        "revoked_purchased": revoked_purchased,
        "revoked_bonus": revoked_bonus,
        "revoked_subscription": revoked_subscription,
    }


async def handle_capture_refunded(db: AsyncSession, data: dict) -> dict:
    """PAYMENT.CAPTURE.REFUNDED — a one-time capture (credit pack) was
    refunded at PayPal. Resolve the order and claw back the credits.

    The resource is the REFUND object: the order id we stored lives in
    supplementary_data.related_ids.order_id when present; otherwise the
    parent capture id is in the rel="up" link, and that capture id exists
    inside order.payment_data (merged there by handle_payment_success)."""
    refund_amount = None
    try:
        v = (data.get("amount") or {}).get("value")
        refund_amount = float(v) if v is not None else None
    except Exception:
        refund_amount = None

    order = None
    related = (data.get("supplementary_data") or {}).get("related_ids") or {}
    if related.get("order_id"):
        order = await _find_order_by_paypal_transaction(db, str(related["order_id"]))
    if not order:
        capture_id = None
        for link in data.get("links") or []:
            href = str(link.get("href") or "")
            if link.get("rel") == "up" and "/captures/" in href:
                capture_id = href.rstrip("/").split("/")[-1]
                break
        if capture_id:
            # Indexed capture-id lookup first (perf audit #7); the LIKE scan is
            # kept only as a transitional fallback for rows predating the
            # paypal_capture_id backfill.
            res = await db.execute(
                select(Order).where(Order.paypal_capture_id == capture_id).limit(1)
            )
            order = res.scalars().first()
            if not order:
                res = await db.execute(
                    select(Order).where(cast(Order.payment_data, String).like(f"%{capture_id}%")).limit(1)
                )
                order = res.scalars().first()
    if not order:
        logger.warning(f"PAYMENT.CAPTURE.REFUNDED: no local order found (refund {data.get('id')})")
        return {"success": False, "error": "order not found"}

    return await _revoke_order_grants(
        db, order,
        reason=f"PayPal capture refund {data.get('id')}",
        refund_amount=refund_amount,
    )


async def handle_sale_refunded(db: AsyncSession, data: dict) -> dict:
    """PAYMENT.SALE.REFUNDED — a subscription billing was refunded at PayPal.
    Cancel the local subscription and strip the current cycle's credits."""
    paypal_sub_id = data.get("billing_agreement_id")
    if not paypal_sub_id:
        logger.warning(f"PAYMENT.SALE.REFUNDED without billing_agreement_id (refund {data.get('id')})")
        return {"success": False, "error": "no billing_agreement_id"}

    order = await _find_order_by_paypal_transaction(db, str(paypal_sub_id).strip('"'))
    if not order:
        logger.warning(f"PAYMENT.SALE.REFUNDED: no local order for agreement {paypal_sub_id}")
        return {"success": False, "error": "order not found"}

    return await _revoke_order_grants(
        db, order,
        reason=f"PayPal sale refund {data.get('id')} (agreement {paypal_sub_id})",
    )


class PayPalCaptureRequest(BaseModel):
    # The PayPal Orders-v2 order id — appended by PayPal to the return URL as
    # ?token=... after the buyer approves. Same value we stored at checkout
    # as payment_data.paypal_transaction_id.
    token: str
    # Our order_number from the success URL's ?order=... — optional
    # cross-check only.
    order: Optional[str] = None


@router.post("/paypal/capture")
async def paypal_capture_order(
    body: PayPalCaptureRequest,
    request: Request,
    db: AsyncSession = Depends(deps.get_db),
):
    """Return-leg capture for one-time PayPal orders (credit packs).

    The success page calls this with the ?token= PayPal appended to the
    return URL. Deliberately unauthenticated, mirroring the success route:
    PayPal's OAuth roundtrip can drop our access token, and the only thing
    this can do is complete the payment of the order the token belongs to
    (the token is the unguessable PayPal order id; amounts/credits come from
    OUR stored order row, not the request). The CHECKOUT.ORDER.APPROVED
    webhook performs the same capture for buyers who never come back — both
    paths are idempotent.
    """
    # Per-IP throttle (2026-07-10 round 5): unauthenticated endpoint doing a
    # DB order scan + a PayPal API call per hit — a legitimate buyer needs at
    # most a couple of attempts. Fail-open on Redis trouble.
    try:
        from app.services.abuse_prevention_service import AbusePreventionService, get_client_ip
        _rate = await AbusePreventionService(await deps.get_redis()).check_paypal_capture_ip(
            get_client_ip(request)
        )
        if not _rate.allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many attempts. Please try again later.",
                headers={"Retry-After": str(_rate.retry_after_seconds or 600)},
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("paypal capture rate check skipped: %s", exc)

    token = (body.token or "").strip()
    # Subscription approvals redirect with a BA-/I- token that is not an
    # Orders-v2 id; they are activated by the BILLING.SUBSCRIPTION webhooks.
    if not token or len(token) > 64:
        raise HTTPException(status_code=400, detail="Invalid token")

    order = await _find_order_by_paypal_transaction(db, token)
    if not order or order.payment_method != "paypal":
        raise HTTPException(status_code=404, detail="Order not found")
    if body.order and body.order != order.order_number:
        raise HTTPException(status_code=404, detail="Order not found")
    # Only one-time credit orders are captured here; subscription orders have
    # no Orders-v2 order behind them.
    if order.subscription_id:
        raise HTTPException(status_code=400, detail="Not a one-time order")

    if order.status == "paid":
        return {"success": True, "order_number": order.order_number, "already_processed": True}
    if order.status != "pending":
        raise HTTPException(status_code=409, detail=f"Order is {order.status}")

    capture = await paypal_service.capture_order(token)
    if not capture.get("success") or capture.get("status") != "COMPLETED":
        # Buyer may have bailed before approving (ORDER_NOT_APPROVED) or the
        # webhook race already handled it. Report "not completed yet" without
        # failing the order — the webhook path can still finish the job.
        return {
            "success": False,
            "order_number": order.order_number,
            "status": capture.get("status") or "pending",
            "message": "Payment not confirmed yet. Credits will be added once PayPal confirms.",
        }

    _cap_order = capture.get("order") or {}
    _cap = ((( _cap_order.get("purchase_units") or [{}])[0].get("payments") or {}).get("captures") or [{}])[0]
    if _cap.get("id"):
        order.paypal_capture_id = str(_cap["id"])  # indexed for refund lookup (perf audit #7)
    from app.services.subscription_service import get_subscription_service
    await get_subscription_service().handle_payment_success(
        db, order.order_number, _cap_order
    )
    logger.info(f"PayPal order captured via return leg: {order.order_number}")
    return {"success": True, "order_number": order.order_number}


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
                # 2026-07-10 guard: never flip an already-paid order (and its
                # live subscription) to "failed" — a replayed/late failure
                # callback for an order that subsequently succeeded was
                # corrupting paid state. Mirrors the already-paid guard on the
                # success branch.
                if failed_order and failed_order.status == "paid":
                    logger.info(f"ECPay failure callback ignored — order {order_number} already paid")
                    return HTMLResponse(content="1|OK", status_code=200)
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
