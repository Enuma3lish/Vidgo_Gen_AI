"""
Pydantic schemas for Taiwan E-Invoice API endpoints.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from enum import Enum


class TaxType(str, Enum):
    taxable = "taxable"
    zero_tax = "zero_tax"
    tax_free = "tax_free"
    mixed = "mixed"


class CarrierType(str, Enum):
    mobile_barcode = "mobile_barcode"
    citizen_cert = "citizen_cert"
    email = "email"


class InvoiceItemInput(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=255)
    item_count: int = Field(default=1, ge=1)
    item_unit: str = Field(default="式", max_length=10)
    item_price: float = Field(..., gt=0)
    item_amount: Optional[float] = None  # Auto-calculated if not provided
    item_tax_type: Optional[TaxType] = TaxType.taxable  # For mixed-tax invoices


class B2CInvoiceCreateRequest(BaseModel):
    order_id: str
    buyer_email: Optional[str] = None
    tax_type: TaxType = TaxType.taxable
    carrier_type: Optional[CarrierType] = None
    carrier_number: Optional[str] = None
    is_donation: bool = False
    love_code: Optional[str] = None
    items: List[InvoiceItemInput] = Field(..., min_length=1)

    @field_validator("love_code")
    @classmethod
    def validate_love_code(cls, v):
        if v and (len(v) < 3 or len(v) > 7 or not v.isdigit()):
            raise ValueError("Love code must be 3-7 digits")
        return v

    @field_validator("carrier_number")
    @classmethod
    def validate_carrier_number(cls, v, info):
        if v and not v.strip():
            raise ValueError("Carrier number cannot be empty when provided")
        return v


class B2BInvoiceCreateRequest(BaseModel):
    order_id: str
    buyer_company_name: str = Field(..., min_length=1, max_length=100)
    buyer_tax_id: str = Field(..., min_length=8, max_length=8)
    buyer_email: Optional[str] = None
    tax_type: TaxType = TaxType.taxable
    items: List[InvoiceItemInput] = Field(..., min_length=1)

    @field_validator("buyer_tax_id")
    @classmethod
    def validate_tax_id(cls, v):
        if not v.isdigit():
            raise ValueError("Tax ID (統一編號) must be exactly 8 digits")
        return v


class InvoiceVoidRequest(BaseModel):
    invoice_id: str
    reason: str = Field(..., min_length=1, max_length=255)


class InvoicePrefsUpdateRequest(BaseModel):
    """Update user's default invoice preferences for auto-issue."""
    default_carrier_type: Optional[CarrierType] = None
    default_carrier_number: Optional[str] = None
    default_love_code: Optional[str] = None

    @field_validator("default_love_code")
    @classmethod
    def validate_love_code(cls, v):
        if v and (len(v) < 3 or len(v) > 7 or not v.isdigit()):
            raise ValueError("Love code must be 3-7 digits")
        return v


class EInvoiceResponse(BaseModel):
    success: bool
    invoice_id: Optional[str] = None
    invoice_number: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    status: Optional[str] = None


class InvoiceListResponse(BaseModel):
    success: bool
    invoices: List[dict] = []
    total: int = 0
    limit: int = 20
    offset: int = 0


class InvoiceDetailResponse(BaseModel):
    success: bool
    invoice: Optional[dict] = None
    error: Optional[str] = None
