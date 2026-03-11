"""
Payment API Endpoints

Supports:
- Paddle: Subscription checkout, webhook handling, invoice PDF retrieval
- ECPay: Taiwan credit card payment, callback handling
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from typing import Optional
import logging

from fastapi.responses import HTMLResponse
from app.api import deps
from app.core.config import get_settings
from app.models.billing import Order, Subscription
from app.models.user import User
from app.services.paddle_service import get_paddle_service
from app.services.ecpay.client import ECPayClient

settings = get_settings()
router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Paddle service
paddle_service = get_paddle_service()


# =============================================================================
# PADDLE ENDPOINTS
# =============================================================================

@router.post("/paddle/checkout")
async def create_paddle_checkout(
    order_number: str,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Create Paddle checkout session for an order.

    This is called when user clicks "Pay" for a pending order.
    Returns checkout URL to redirect user to Paddle payment page.
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

    # Create Paddle checkout
    paddle_result = await paddle_service.create_checkout_session(
        user_id=current_user.id,
        user_email=current_user.email,
        plan_id=str(order.payment_data.get("plan_id", "")),
        price_id=f"pri_{order.order_number}",  # Would be real Paddle price ID
        billing_cycle=order.payment_data.get("billing_cycle", "monthly"),
        success_url=f"{settings.FRONTEND_URL}/payment/success?order={order.order_number}",
        cancel_url=f"{settings.FRONTEND_URL}/payment/cancelled"
    )

    if not paddle_result.get("success"):
        raise HTTPException(status_code=500, detail=paddle_result.get("error"))

    # Update order with Paddle transaction ID
    order.payment_data["paddle_transaction_id"] = paddle_result.get("transaction_id")
    await db.commit()

    return {
        "success": True,
        "checkout_url": paddle_result.get("checkout_url"),
        "is_mock": paddle_result.get("is_mock", False)
    }


@router.post("/paddle/webhook")
async def paddle_webhook(
    request: Request,
    paddle_signature: Optional[str] = Header(None, alias="Paddle-Signature"),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Handle Paddle webhooks.

    Paddle sends webhooks for:
    - transaction.completed - Payment successful
    - subscription.created - Subscription created
    - subscription.updated - Subscription changed
    - subscription.canceled - Subscription cancelled
    """
    body = await request.body()

    # Verify webhook signature (skip in mock mode)
    if not paddle_service.is_mock and not paddle_service.verify_webhook(body, paddle_signature or ""):
        logger.warning("Invalid Paddle webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        data = await request.json()
        event_type = data.get("event_type", "")
        event_data = data.get("data", {})

        logger.info(f"Paddle webhook received: {event_type}")

        if event_type == "transaction.completed":
            await handle_transaction_completed(db, event_data)
        elif event_type == "subscription.created":
            await handle_subscription_created(db, event_data)
        elif event_type == "subscription.updated":
            await handle_subscription_updated(db, event_data)
        elif event_type == "subscription.canceled":
            await handle_subscription_canceled(db, event_data)

        return {"success": True}

    except Exception as e:
        logger.error(f"Paddle webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def handle_transaction_completed(db: AsyncSession, data: dict):
    """Handle successful payment transaction and send invoice email."""
    custom_data = data.get("custom_data", {})
    user_id = custom_data.get("user_id")
    transaction_id = data.get("id")
    if transaction_id is not None:
        transaction_id = str(transaction_id).strip('"')
    invoice_number = data.get("invoice_number", transaction_id)

    if not user_id:
        logger.warning(f"Transaction without user_id: {transaction_id}")
        return
    if not transaction_id:
        logger.warning("Transaction completed webhook missing id")
        return

    # Find order by transaction ID (normalize to string for JSONB comparison)
    result = await db.execute(
        select(Order).where(
            Order.payment_data["paddle_transaction_id"].astext == transaction_id
        )
    )
    order = result.scalars().first()

    if order:
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
            # Get invoice PDF URL from Paddle
            invoice_result = await paddle_service.get_invoice_pdf_url(transaction_id)
            pdf_url = invoice_result.get("pdf_url", "")

            # Extract amount info
            totals = data.get("details", {}).get("totals", {})
            amount = float(totals.get("grand_total", 0)) / 100  # Paddle uses cents
            currency = data.get("currency_code", "USD")
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


async def handle_subscription_created(db: AsyncSession, data: dict):
    """Handle subscription created event."""
    subscription_id = data.get("id")
    logger.info(f"Subscription created: {subscription_id}")


async def handle_subscription_updated(db: AsyncSession, data: dict):
    """Handle subscription updated event."""
    subscription_id = data.get("id")
    logger.info(f"Subscription updated: {subscription_id}")


async def handle_subscription_canceled(db: AsyncSession, data: dict):
    """Handle subscription cancelled event."""
    subscription_id = data.get("id")
    logger.info(f"Subscription canceled: {subscription_id}")


@router.get("/paddle/customer-portal")
async def get_paddle_customer_portal(
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    Get Paddle customer portal URL for self-service billing management.

    The portal allows users to:
    - View billing history
    - Update payment method
    - Download invoices
    """
    # Get or create Paddle customer
    customer_result = await paddle_service.get_or_create_customer(
        email=current_user.email,
        name=current_user.full_name
    )

    if not customer_result.get("success"):
        raise HTTPException(status_code=500, detail=customer_result.get("error"))

    # Get portal URL
    portal_result = await paddle_service.get_customer_portal_url(
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

        # Verify signature
        if not ecpay_client.verify_callback(callback_data.copy()):
            logger.error(f"ECPay callback signature verification failed for order: {callback_data.get('MerchantTradeNo')}")
            return HTMLResponse(content="0|SignatureError", status_code=200)

        # Check payment status (RtnCode=1 means success)
        rtn_code = callback_data.get("RtnCode", "0")
        order_number = callback_data.get("MerchantTradeNo", "")

        if rtn_code == "1" and order_number:
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

    Only works when Paddle is in mock mode (no API key configured).
    """
    if not paddle_service.is_mock:
        raise HTTPException(
            status_code=400,
            detail="Mock payment only available in development mode"
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
