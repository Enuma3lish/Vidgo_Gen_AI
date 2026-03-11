"""
Invoice Service - Taiwan E-Invoice Business Logic

Handles:
- B2C invoice creation (general consumers)
- B2B invoice creation (with tax ID / 統一編號)
- Invoice voiding (within current bimonthly period)
- Auto-issue on payment with saved user preferences
- Invoice listing with pagination
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import uuid4

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.billing import Invoice, InvoiceItem, Order
from app.models.user import User
from app.services.ecpay.einvoice_client import ECPayEInvoiceClient, get_einvoice_client

logger = logging.getLogger(__name__)


def get_current_tax_period() -> str:
    """
    Get the current bimonthly tax period.
    Taiwan periods: 1-2月, 3-4月, 5-6月, 7-8月, 9-10月, 11-12月
    Returns: "YYYYMM" where MM is the first month of the period.
    """
    now = datetime.now()
    period_month = ((now.month - 1) // 2) * 2 + 1
    return f"{now.year}{period_month:02d}"


def is_same_tax_period(invoice_period: str) -> bool:
    """Check if invoice period matches current bimonthly period."""
    return invoice_period == get_current_tax_period()


def calculate_tax(total_amount: Decimal, tax_type: str) -> tuple[Decimal, Decimal]:
    """
    Calculate tax and sales amount from total.
    Taiwan standard: 5% tax included in total amount.
    Returns: (sales_amount, tax_amount)
    """
    if tax_type in ("tax_free", "zero_tax"):
        return total_amount, Decimal("0")

    # Tax-included calculation: sales = total / 1.05, tax = total - sales
    tax_rate = Decimal("1.05")
    sales_amount = (total_amount / tax_rate).quantize(Decimal("1"))
    tax_amount = total_amount - sales_amount
    return sales_amount, tax_amount


async def create_b2c_invoice(
    db: AsyncSession,
    user_id: str,
    order_id: str,
    buyer_email: Optional[str],
    tax_type: str,
    carrier_type: Optional[str],
    carrier_number: Optional[str],
    is_donation: bool,
    love_code: Optional[str],
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Create a B2C e-invoice (general consumer)."""

    # Validate order
    order = await db.get(Order, order_id)
    if not order:
        return {"success": False, "error": "Order not found"}
    if str(order.user_id) != str(user_id):
        return {"success": False, "error": "Order does not belong to user"}

    # Check no invoice exists for this order
    existing = await db.execute(
        select(Invoice).where(Invoice.order_id == order_id, Invoice.status != "failed")
    )
    if existing.scalar_one_or_none():
        return {"success": False, "error": "Invoice already exists for this order"}

    # Validate mutual exclusion: carrier vs donation
    if is_donation and carrier_type:
        return {"success": False, "error": "Cannot use carrier with donation"}
    if is_donation and not love_code:
        return {"success": False, "error": "Love code required for donation"}

    # Calculate tax
    total_amount = order.amount
    sales_amount, tax_amount = calculate_tax(Decimal(str(total_amount)), tax_type)

    # Call ECPay
    client = get_einvoice_client()
    relate_number = client.generate_relate_number()

    ecpay_items = [
        {
            "name": item["item_name"],
            "count": item.get("item_count", 1),
            "unit": item.get("item_unit", "式"),
            "price": item["item_price"],
            "amount": item.get("item_amount", item["item_price"] * item.get("item_count", 1)),
            "tax_type": item.get("item_tax_type", "taxable"),
        }
        for item in items
    ]

    try:
        response = await client.issue_b2c_invoice(
            relate_number=relate_number,
            customer_email=buyer_email or "",
            sales_amount=int(total_amount),
            tax_type=tax_type,
            items=ecpay_items,
            carrier_type=carrier_type,
            carrier_num=carrier_number,
            donation=is_donation,
            love_code=love_code,
        )
    except Exception as e:
        logger.error(f"ECPay B2C invoice error: {e}")
        return {"success": False, "error": f"ECPay API error: {str(e)}"}

    # Check response
    rtn_code = response.get("RtnCode")
    if str(rtn_code) != "1":
        # Create failed invoice record for tracking
        invoice = Invoice(
            id=uuid4(),
            order_id=order_id,
            user_id=user_id,
            invoice_type="b2c",
            amount=total_amount,
            status="failed",
            ecpay_relate_number=relate_number,
            ecpay_response_data=response,
            invoice_period=get_current_tax_period(),
        )
        db.add(invoice)
        await db.commit()
        return {"success": False, "error": response.get("RtnMsg", "Invoice creation failed")}

    # Create successful invoice record
    invoice_number = response.get("InvoiceNo", "")
    invoice = Invoice(
        id=uuid4(),
        order_id=order_id,
        user_id=user_id,
        invoice_type="b2c",
        invoice_number=invoice_number,
        amount=total_amount,
        sales_amount=sales_amount,
        tax_amount=tax_amount,
        tax_type=tax_type,
        buyer_email=buyer_email,
        carrier_type=carrier_type,
        carrier_number=carrier_number,
        is_donation=is_donation,
        love_code=love_code,
        status="issued",
        ecpay_invoice_no=response.get("InvoiceNo"),
        ecpay_relate_number=relate_number,
        ecpay_response_data=response,
        invoice_period=get_current_tax_period(),
    )
    db.add(invoice)

    # Create invoice items
    for item in items:
        db.add(InvoiceItem(
            id=uuid4(),
            invoice_id=invoice.id,
            item_name=item["item_name"],
            item_count=item.get("item_count", 1),
            item_unit=item.get("item_unit", "式"),
            item_price=item["item_price"],
            item_amount=item.get("item_amount", item["item_price"] * item.get("item_count", 1)),
            item_tax_type=item.get("item_tax_type", "taxable"),
        ))

    await db.commit()

    return {
        "success": True,
        "invoice_id": str(invoice.id),
        "invoice_number": invoice_number,
        "message": "B2C invoice created successfully",
    }


async def create_b2b_invoice(
    db: AsyncSession,
    user_id: str,
    order_id: str,
    buyer_company_name: str,
    buyer_tax_id: str,
    buyer_email: Optional[str],
    tax_type: str,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Create a B2B e-invoice (with tax ID / 統一編號)."""

    # Validate tax ID: must be exactly 8 digits
    if not buyer_tax_id or len(buyer_tax_id) != 8 or not buyer_tax_id.isdigit():
        return {"success": False, "error": "Tax ID must be exactly 8 digits"}

    # Validate order
    order = await db.get(Order, order_id)
    if not order:
        return {"success": False, "error": "Order not found"}
    if str(order.user_id) != str(user_id):
        return {"success": False, "error": "Order does not belong to user"}

    # Check no invoice exists
    existing = await db.execute(
        select(Invoice).where(Invoice.order_id == order_id, Invoice.status != "failed")
    )
    if existing.scalar_one_or_none():
        return {"success": False, "error": "Invoice already exists for this order"}

    total_amount = order.amount
    sales_amount, tax_amount = calculate_tax(Decimal(str(total_amount)), tax_type)

    client = get_einvoice_client()
    relate_number = client.generate_relate_number()

    ecpay_items = [
        {
            "name": item["item_name"],
            "count": item.get("item_count", 1),
            "unit": item.get("item_unit", "式"),
            "price": item["item_price"],
            "amount": item.get("item_amount", item["item_price"] * item.get("item_count", 1)),
        }
        for item in items
    ]

    try:
        response = await client.issue_b2b_invoice(
            relate_number=relate_number,
            customer_identifier=buyer_tax_id,
            customer_name=buyer_company_name,
            customer_email=buyer_email or "",
            sales_amount=int(total_amount),
            tax_type=tax_type,
            items=ecpay_items,
        )
    except Exception as e:
        logger.error(f"ECPay B2B invoice error: {e}")
        return {"success": False, "error": f"ECPay API error: {str(e)}"}

    rtn_code = response.get("RtnCode")
    if str(rtn_code) != "1":
        invoice = Invoice(
            id=uuid4(),
            order_id=order_id,
            user_id=user_id,
            invoice_type="b2b",
            amount=total_amount,
            status="failed",
            ecpay_relate_number=relate_number,
            ecpay_response_data=response,
            invoice_period=get_current_tax_period(),
        )
        db.add(invoice)
        await db.commit()
        return {"success": False, "error": response.get("RtnMsg", "Invoice creation failed")}

    invoice_number = response.get("InvoiceNo", "")
    invoice = Invoice(
        id=uuid4(),
        order_id=order_id,
        user_id=user_id,
        invoice_type="b2b",
        invoice_number=invoice_number,
        amount=total_amount,
        sales_amount=sales_amount,
        tax_amount=tax_amount,
        tax_type=tax_type,
        buyer_company_name=buyer_company_name,
        buyer_tax_id=buyer_tax_id,
        buyer_email=buyer_email,
        status="issued",
        ecpay_invoice_no=response.get("InvoiceNo"),
        ecpay_relate_number=relate_number,
        ecpay_response_data=response,
        invoice_period=get_current_tax_period(),
    )
    db.add(invoice)

    for item in items:
        db.add(InvoiceItem(
            id=uuid4(),
            invoice_id=invoice.id,
            item_name=item["item_name"],
            item_count=item.get("item_count", 1),
            item_unit=item.get("item_unit", "式"),
            item_price=item["item_price"],
            item_amount=item.get("item_amount", item["item_price"] * item.get("item_count", 1)),
            item_tax_type=item.get("item_tax_type", "taxable"),
        ))

    await db.commit()

    return {
        "success": True,
        "invoice_id": str(invoice.id),
        "invoice_number": invoice_number,
        "message": "B2B invoice created successfully",
    }


async def void_invoice(
    db: AsyncSession,
    user_id: str,
    invoice_id: str,
    reason: str,
) -> Dict[str, Any]:
    """Void an e-invoice (within current bimonthly period only)."""

    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        return {"success": False, "error": "Invoice not found"}
    if str(invoice.user_id) != str(user_id):
        return {"success": False, "error": "Invoice does not belong to user"}
    if invoice.status != "issued":
        return {"success": False, "error": "Only issued invoices can be voided"}
    if not invoice.invoice_period or not is_same_tax_period(invoice.invoice_period):
        return {"success": False, "error": "Can only void invoices within current tax period (當期)"}
    if not invoice.invoice_number:
        return {"success": False, "error": "Invoice has no invoice number"}

    client = get_einvoice_client()
    invoice_date = invoice.issued_at.strftime("%Y-%m-%d") if invoice.issued_at else ""
    is_b2b = invoice.invoice_type == "b2b"

    try:
        response = await client.void_invoice(
            invoice_no=invoice.invoice_number,
            invoice_date=invoice_date,
            reason=reason,
            is_b2b=is_b2b,
        )
    except Exception as e:
        logger.error(f"ECPay void invoice error: {e}")
        return {"success": False, "error": f"ECPay API error: {str(e)}"}

    rtn_code = response.get("RtnCode")
    if str(rtn_code) != "1":
        return {"success": False, "error": response.get("RtnMsg", "Invoice void failed")}

    invoice.status = "voided"
    invoice.voided_at = datetime.utcnow()
    invoice.void_reason = reason
    invoice.void_response_data = response
    await db.commit()

    return {
        "success": True,
        "invoice_id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "message": "Invoice voided successfully",
    }


async def list_invoices(
    db: AsyncSession,
    user_id: str,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """List user's e-invoices with pagination."""

    # Count total
    count_result = await db.execute(
        select(func.count()).select_from(Invoice).where(Invoice.user_id == user_id)
    )
    total = count_result.scalar() or 0

    # Fetch invoices
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(Invoice.user_id == user_id)
        .order_by(Invoice.issued_at.desc())
        .limit(limit)
        .offset(offset)
    )
    invoices = result.scalars().all()

    current_period = get_current_tax_period()

    invoice_list = []
    for inv in invoices:
        invoice_list.append({
            "id": str(inv.id),
            "order_id": str(inv.order_id) if inv.order_id else None,
            "invoice_number": inv.invoice_number,
            "invoice_type": inv.invoice_type,
            "amount": float(inv.amount) if inv.amount else 0,
            "sales_amount": float(inv.sales_amount) if inv.sales_amount else None,
            "tax_amount": float(inv.tax_amount) if inv.tax_amount else None,
            "tax_type": inv.tax_type,
            "status": inv.status,
            "buyer_company_name": inv.buyer_company_name,
            "buyer_tax_id": inv.buyer_tax_id,
            "buyer_email": inv.buyer_email,
            "carrier_type": inv.carrier_type,
            "is_donation": inv.is_donation,
            "love_code": inv.love_code,
            "issued_at": inv.issued_at.isoformat() if inv.issued_at else None,
            "voided_at": inv.voided_at.isoformat() if inv.voided_at else None,
            "void_reason": inv.void_reason,
            "can_void": inv.status == "issued" and inv.invoice_period == current_period,
            "items": [
                {
                    "item_name": item.item_name,
                    "item_count": item.item_count,
                    "item_unit": item.item_unit,
                    "item_price": float(item.item_price),
                    "item_amount": float(item.item_amount),
                }
                for item in (inv.items or [])
            ],
        })

    return {
        "success": True,
        "invoices": invoice_list,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def get_invoice(
    db: AsyncSession,
    user_id: str,
    invoice_id: str,
) -> Dict[str, Any]:
    """Get a single invoice detail."""
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        return {"success": False, "error": "Invoice not found"}
    if str(inv.user_id) != str(user_id):
        return {"success": False, "error": "Invoice does not belong to user"}

    current_period = get_current_tax_period()

    return {
        "success": True,
        "invoice": {
            "id": str(inv.id),
            "order_id": str(inv.order_id) if inv.order_id else None,
            "invoice_number": inv.invoice_number,
            "invoice_type": inv.invoice_type,
            "amount": float(inv.amount) if inv.amount else 0,
            "sales_amount": float(inv.sales_amount) if inv.sales_amount else None,
            "tax_amount": float(inv.tax_amount) if inv.tax_amount else None,
            "tax_type": inv.tax_type,
            "status": inv.status,
            "buyer_company_name": inv.buyer_company_name,
            "buyer_tax_id": inv.buyer_tax_id,
            "buyer_email": inv.buyer_email,
            "carrier_type": inv.carrier_type,
            "carrier_number": inv.carrier_number,
            "is_donation": inv.is_donation,
            "love_code": inv.love_code,
            "issued_at": inv.issued_at.isoformat() if inv.issued_at else None,
            "voided_at": inv.voided_at.isoformat() if inv.voided_at else None,
            "void_reason": inv.void_reason,
            "can_void": inv.status == "issued" and inv.invoice_period == current_period,
            "items": [
                {
                    "item_name": item.item_name,
                    "item_count": item.item_count,
                    "item_unit": item.item_unit,
                    "item_price": float(item.item_price),
                    "item_amount": float(item.item_amount),
                }
                for item in (inv.items or [])
            ],
        },
    }


async def auto_issue_invoice(
    db: AsyncSession,
    user_id: str,
    order_id: str,
) -> Dict[str, Any]:
    """
    Auto-issue invoice after payment using user's saved carrier/donation preferences.
    If user has no saved preferences, creates a pending_issue record.
    """
    user = await db.get(User, user_id)
    if not user:
        return {"success": False, "error": "User not found"}

    order = await db.get(Order, order_id)
    if not order:
        return {"success": False, "error": "Order not found"}

    # If user has saved carrier preferences, auto-issue B2C
    if user.default_carrier_type and user.default_carrier_number:
        items = [{
            "item_name": f"VidGo Service - Order {order.order_number}",
            "item_count": 1,
            "item_unit": "式",
            "item_price": float(order.amount),
            "item_amount": float(order.amount),
        }]
        return await create_b2c_invoice(
            db=db,
            user_id=str(user_id),
            order_id=str(order_id),
            buyer_email=user.email,
            tax_type="taxable",
            carrier_type=user.default_carrier_type,
            carrier_number=user.default_carrier_number,
            is_donation=False,
            love_code=None,
            items=items,
        )

    # If user has love code preference, auto-donate
    if user.default_love_code:
        items = [{
            "item_name": f"VidGo Service - Order {order.order_number}",
            "item_count": 1,
            "item_unit": "式",
            "item_price": float(order.amount),
            "item_amount": float(order.amount),
        }]
        return await create_b2c_invoice(
            db=db,
            user_id=str(user_id),
            order_id=str(order_id),
            buyer_email=user.email,
            tax_type="taxable",
            carrier_type=None,
            carrier_number=None,
            is_donation=True,
            love_code=user.default_love_code,
            items=items,
        )

    # No saved preferences - create pending_issue record
    invoice = Invoice(
        id=uuid4(),
        order_id=order_id,
        user_id=user_id,
        invoice_type="b2c",
        amount=order.amount,
        status="pending_issue",
        invoice_period=get_current_tax_period(),
    )
    db.add(invoice)
    await db.commit()

    return {
        "success": True,
        "invoice_id": str(invoice.id),
        "status": "pending_issue",
        "message": "Invoice pending - user needs to set carrier/donation preferences",
    }
