"""
E-Invoice API Endpoints - Taiwan Electronic Invoice (電子發票)

Endpoints:
- POST /einvoices/b2c - Create B2C invoice (general consumer)
- POST /einvoices/b2b - Create B2B invoice (with tax ID)
- POST /einvoices/void - Void an invoice
- GET  /einvoices - List user's e-invoices
- GET  /einvoices/{invoice_id} - Get invoice detail
- PUT  /einvoices/preferences - Update user's invoice preferences
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.einvoice import (
    B2CInvoiceCreateRequest,
    B2BInvoiceCreateRequest,
    InvoiceVoidRequest,
    InvoicePrefsUpdateRequest,
    EInvoiceResponse,
    InvoiceListResponse,
    InvoiceDetailResponse,
)
from app.services import invoice_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/b2c", response_model=EInvoiceResponse)
async def create_b2c_invoice(
    request: B2CInvoiceCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a B2C e-invoice for a general consumer (no tax ID)."""
    # Validate carrier + donation mutual exclusion
    if request.is_donation and request.carrier_type:
        raise HTTPException(
            status_code=400,
            detail="Cannot use carrier with donation (載具與捐贈互斥)"
        )
    if request.carrier_type and not request.carrier_number:
        raise HTTPException(
            status_code=400,
            detail="Carrier number required when carrier type is specified"
        )

    items = [
        {
            "item_name": item.item_name,
            "item_count": item.item_count,
            "item_unit": item.item_unit,
            "item_price": item.item_price,
            "item_amount": item.item_amount or (item.item_price * item.item_count),
            "item_tax_type": item.item_tax_type.value if item.item_tax_type else "taxable",
        }
        for item in request.items
    ]

    result = await invoice_service.create_b2c_invoice(
        db=db,
        user_id=str(current_user.id),
        order_id=request.order_id,
        buyer_email=request.buyer_email,
        tax_type=request.tax_type.value,
        carrier_type=request.carrier_type.value if request.carrier_type else None,
        carrier_number=request.carrier_number,
        is_donation=request.is_donation,
        love_code=request.love_code,
        items=items,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/b2b", response_model=EInvoiceResponse)
async def create_b2b_invoice(
    request: B2BInvoiceCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a B2B e-invoice with a buyer tax ID (統一編號)."""
    items = [
        {
            "item_name": item.item_name,
            "item_count": item.item_count,
            "item_unit": item.item_unit,
            "item_price": item.item_price,
            "item_amount": item.item_amount or (item.item_price * item.item_count),
            "item_tax_type": item.item_tax_type.value if item.item_tax_type else "taxable",
        }
        for item in request.items
    ]

    result = await invoice_service.create_b2b_invoice(
        db=db,
        user_id=str(current_user.id),
        order_id=request.order_id,
        buyer_company_name=request.buyer_company_name,
        buyer_tax_id=request.buyer_tax_id,
        buyer_email=request.buyer_email,
        tax_type=request.tax_type.value,
        items=items,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/void", response_model=EInvoiceResponse)
async def void_invoice(
    request: InvoiceVoidRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Void an e-invoice (only within the current bimonthly tax period)."""
    result = await invoice_service.void_invoice(
        db=db,
        user_id=str(current_user.id),
        invoice_id=request.invoice_id,
        reason=request.reason,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's e-invoices with pagination."""
    return await invoice_service.list_invoices(
        db=db,
        user_id=str(current_user.id),
        limit=limit,
        offset=offset,
    )


# NOTE: must be declared BEFORE GET /{invoice_id}, otherwise "preferences"
# would be captured as an invoice_id path param.
@router.get("/preferences")
async def get_invoice_preferences(
    current_user: User = Depends(get_current_user),
):
    """Get the user's saved invoice preferences (發票設定) for auto-issue."""
    return {
        "success": True,
        "preferences": {
            "default_invoice_mode": current_user.default_invoice_mode,
            "default_carrier_type": current_user.default_carrier_type,
            "default_carrier_number": current_user.default_carrier_number,
            "default_love_code": current_user.default_love_code,
            "default_buyer_tax_id": current_user.default_buyer_tax_id,
            "default_buyer_company_name": current_user.default_buyer_company_name,
        },
    }


@router.get("/{invoice_id}", response_model=InvoiceDetailResponse)
async def get_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single e-invoice detail."""
    result = await invoice_service.get_invoice(
        db=db,
        user_id=str(current_user.id),
        invoice_id=invoice_id,
    )

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.put("/preferences")
async def update_invoice_preferences(
    request: InvoicePrefsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update user's default invoice preferences for auto-issue on payment.

    2026-06-12 — mode-aware (發票設定): the buyer picks how every future
    payment issues its invoice — 個人發票+載具 (carrier), 捐贈 (donation),
    or 公司發票+統編 (b2b). Each mode requires its own fields and the other
    modes' fields are cleared so auto_issue_invoice never sees a conflicting
    combination. Legacy callers that send only carrier/love-code fields
    (no mode) keep the old behavior.
    """
    mode = request.default_invoice_mode.value if request.default_invoice_mode else None

    if mode == "carrier":
        if not request.default_carrier_type or not (request.default_carrier_number or "").strip():
            raise HTTPException(
                status_code=400,
                detail="Carrier mode requires carrier type and number (載具模式需要載具類別與號碼)",
            )
    elif mode == "donation":
        if not request.default_love_code:
            raise HTTPException(
                status_code=400,
                detail="Donation mode requires a love code (捐贈模式需要愛心碼)",
            )
    elif mode == "b2b":
        # Company name is always required. The tax ID is required for TW 統編
        # invoices but OPTIONAL for overseas PayPal buyers (free-format VAT/EIN),
        # so it is validated per-channel at issue time, not here.
        if not (request.default_buyer_company_name or "").strip():
            raise HTTPException(
                status_code=400,
                detail="B2B mode requires a company name (公司發票需要公司抬頭)",
            )
    else:
        # Legacy (no mode): keep the original carrier-vs-donation exclusion.
        if request.default_carrier_type and request.default_love_code:
            raise HTTPException(
                status_code=400,
                detail="Cannot set both carrier and love code (載具與捐贈互斥)"
            )

    current_user.default_invoice_mode = mode
    # Persist only the active mode's fields; clear the rest so a later mode
    # switch can't leave stale combinations behind.
    use_carrier = mode == "carrier" or (mode is None and request.default_carrier_type)
    use_donation = mode == "donation" or (mode is None and request.default_love_code)
    current_user.default_carrier_type = (
        request.default_carrier_type.value if (use_carrier and request.default_carrier_type) else None
    )
    current_user.default_carrier_number = request.default_carrier_number if use_carrier else None
    current_user.default_love_code = request.default_love_code if use_donation else None
    current_user.default_buyer_tax_id = request.default_buyer_tax_id if mode == "b2b" else None
    current_user.default_buyer_company_name = (
        (request.default_buyer_company_name or "").strip() if mode == "b2b" else None
    )
    await db.commit()

    return {
        "success": True,
        "message": "Invoice preferences updated",
        "preferences": {
            "default_invoice_mode": current_user.default_invoice_mode,
            "default_carrier_type": current_user.default_carrier_type,
            "default_carrier_number": current_user.default_carrier_number,
            "default_love_code": current_user.default_love_code,
            "default_buyer_tax_id": current_user.default_buyer_tax_id,
            "default_buyer_company_name": current_user.default_buyer_company_name,
        },
    }
