"""
Payment API Endpoints

Paddle is the ONLY payment provider for this platform.
Supports:
- Subscription checkout
- Webhook handling
- Invoice PDF retrieval
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from typing import Optional
import logging

from app.api import deps
from app.core.config import get_settings
from app.models.billing import Order
from app.models.user import User
from app.services.paddle_service import get_paddle_service

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
    invoice_number = data.get("invoice_number", transaction_id)

    if not user_id:
        logger.warning(f"Transaction without user_id: {transaction_id}")
        return

    # Find order by transaction ID
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
