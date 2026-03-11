"""
ECPay E-Invoice Client

Handles Taiwan e-invoice (電子發票) operations:
- B2C invoice issuance (一般消費者)
- B2B invoice issuance (有統編)
- Invoice voiding (作廢)

Uses the same CheckMacValue generation as the payment client.
Reference: https://developers.ecpay.com.tw/?p=7809
"""
import hashlib
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import quote_plus
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)


class ECPayEInvoiceClient:
    """ECPay E-Invoice API Client for Taiwan electronic invoices."""

    def __init__(
        self,
        merchant_id: str,
        hash_key: str,
        hash_iv: str,
        b2c_issue_url: str,
        b2b_issue_url: str,
        b2c_void_url: str,
        b2b_void_url: str,
    ):
        self.merchant_id = merchant_id
        self.hash_key = hash_key
        self.hash_iv = hash_iv
        self.b2c_issue_url = b2c_issue_url
        self.b2b_issue_url = b2b_issue_url
        self.b2c_void_url = b2c_void_url
        self.b2b_void_url = b2b_void_url

    def generate_check_mac_value(self, params: Dict[str, Any]) -> str:
        """
        Generate CheckMacValue for ECPay e-invoice API.
        Same algorithm as payment API: URL-encode → lowercase → SHA256 → uppercase.
        """
        params_copy = {k: str(v) for k, v in params.items() if k != "CheckMacValue"}
        sorted_params = sorted(params_copy.items(), key=lambda x: x[0])
        param_str = "&".join(f"{k}={v}" for k, v in sorted_params)
        raw_str = f"HashKey={self.hash_key}&{param_str}&HashIV={self.hash_iv}"

        encoded_str = quote_plus(raw_str).lower()
        # ECPay-specific character replacements
        for old, new in [("%2d", "-"), ("%5f", "_"), ("%2e", "."),
                         ("%21", "!"), ("%2a", "*"), ("%28", "("), ("%29", ")")]:
            encoded_str = encoded_str.replace(old, new)

        return hashlib.sha256(encoded_str.encode("utf-8")).hexdigest().upper()

    @staticmethod
    def generate_relate_number() -> str:
        """Generate a unique RelateNumber for ECPay (max 30 chars)."""
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        uid = uuid4().hex[:16]
        return f"{ts}{uid}"[:30]

    @staticmethod
    def get_current_tax_period() -> str:
        """
        Get the current bimonthly tax period string.
        Taiwan tax periods: 1-2月, 3-4月, 5-6月, 7-8月, 9-10月, 11-12月
        Returns format: "YYYYMM" where MM is the first month of the period.
        """
        now = datetime.now()
        # Map month to period start: 1→01, 2→01, 3→03, 4→03, etc.
        period_month = ((now.month - 1) // 2) * 2 + 1
        return f"{now.year}{period_month:02d}"

    @staticmethod
    def is_same_tax_period(invoice_period: str) -> bool:
        """Check if an invoice period matches the current tax period."""
        return invoice_period == ECPayEInvoiceClient.get_current_tax_period()

    async def _make_request(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make async POST request to ECPay e-invoice API."""
        check_mac = self.generate_check_mac_value(params)
        params["CheckMacValue"] = check_mac

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=params)
            response.raise_for_status()

            try:
                result = response.json()
            except Exception:
                # ECPay sometimes returns form-encoded responses
                result = {}
                for item in response.text.split("&"):
                    if "=" in item:
                        key, value = item.split("=", 1)
                        result[key] = value

            logger.info(f"ECPay e-invoice response: RtnCode={result.get('RtnCode')}")
            return result

    async def issue_b2c_invoice(
        self,
        relate_number: str,
        customer_email: str,
        sales_amount: int,
        tax_type: str,
        items: List[Dict[str, Any]],
        inv_type: str = "07",
        carrier_type: Optional[str] = None,
        carrier_num: Optional[str] = None,
        donation: bool = False,
        love_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Issue a B2C e-invoice via ECPay.

        Args:
            relate_number: Unique identifier for this invoice request
            customer_email: Buyer's email
            sales_amount: Total amount (integer, TWD)
            tax_type: 1=taxable, 2=zero_tax, 3=tax_free, 9=mixed
            items: List of item dicts with name, count, unit, price, amount, tax_type
            inv_type: 07=general, 08=special
            carrier_type: 1=ECPay member, 2=citizen cert, 3=mobile barcode
            carrier_num: Carrier number
            donation: Whether to donate the invoice
            love_code: Charity donation code (3-7 digits)

        Returns:
            ECPay API response dict
        """
        tax_type_map = {"taxable": "1", "zero_tax": "2", "tax_free": "3", "mixed": "9"}
        carrier_type_map = {"ecpay_member": "1", "citizen_cert": "2", "mobile_barcode": "3"}

        # Build item strings (pipe-separated)
        item_names = "|".join(item["name"] for item in items)
        item_counts = "|".join(str(item["count"]) for item in items)
        item_units = "|".join(item.get("unit", "式") for item in items)
        item_prices = "|".join(str(item["price"]) for item in items)
        item_amounts = "|".join(str(item["amount"]) for item in items)

        params: Dict[str, Any] = {
            "MerchantID": self.merchant_id,
            "RelateNumber": relate_number,
            "CustomerEmail": customer_email or "",
            "CustomerPhone": "",
            "CustomerName": "",
            "CustomerAddr": "",
            "CustomerIdentifier": "",  # Empty for B2C
            "TaxType": tax_type_map.get(tax_type, "1"),
            "SalesAmount": sales_amount,
            "InvType": inv_type,
            "vat": "1",
            "ItemName": item_names,
            "ItemCount": item_counts,
            "ItemWord": item_units,
            "ItemPrice": item_prices,
            "ItemAmount": item_amounts,
            "TimeStamp": str(int(time.time())),
        }

        # Carrier info
        if carrier_type and carrier_num:
            params["CarrierType"] = carrier_type_map.get(carrier_type, "")
            params["CarrierNum"] = carrier_num
            params["Print"] = "0"  # Don't print if carrier is used
        else:
            params["CarrierType"] = ""
            params["CarrierNum"] = ""
            params["Print"] = "1"  # Print if no carrier

        # Donation
        if donation and love_code:
            params["Donation"] = "1"
            params["LoveCode"] = love_code
            params["Print"] = "0"
            params["CarrierType"] = ""
            params["CarrierNum"] = ""
        else:
            params["Donation"] = "0"
            params["LoveCode"] = ""

        # Mixed tax item types
        if tax_type == "mixed":
            item_tax_types = "|".join(
                tax_type_map.get(item.get("tax_type", "taxable"), "1") for item in items
            )
            params["ItemTaxType"] = item_tax_types

        return await self._make_request(self.b2c_issue_url, params)

    async def issue_b2b_invoice(
        self,
        relate_number: str,
        customer_identifier: str,
        customer_name: str,
        customer_email: str,
        sales_amount: int,
        tax_type: str,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Issue a B2B e-invoice via ECPay.

        Args:
            relate_number: Unique identifier
            customer_identifier: Buyer tax ID (統一編號, 8 digits)
            customer_name: Buyer company name
            customer_email: Buyer email
            sales_amount: Total amount
            tax_type: Tax type string
            items: List of item dicts
        """
        tax_type_map = {"taxable": "1", "zero_tax": "2", "tax_free": "3", "mixed": "9"}

        item_names = "|".join(item["name"] for item in items)
        item_counts = "|".join(str(item["count"]) for item in items)
        item_units = "|".join(item.get("unit", "式") for item in items)
        item_prices = "|".join(str(item["price"]) for item in items)
        item_amounts = "|".join(str(item["amount"]) for item in items)

        params: Dict[str, Any] = {
            "MerchantID": self.merchant_id,
            "RelateNumber": relate_number,
            "CustomerIdentifier": customer_identifier,
            "CustomerName": customer_name,
            "CustomerEmail": customer_email or "",
            "CustomerPhone": "",
            "CustomerAddr": "",
            "TaxType": tax_type_map.get(tax_type, "1"),
            "SalesAmount": sales_amount,
            "InvType": "07",
            "vat": "1",
            "ItemName": item_names,
            "ItemCount": item_counts,
            "ItemWord": item_units,
            "ItemPrice": item_prices,
            "ItemAmount": item_amounts,
            "Print": "1",  # B2B always prints
            "Donation": "0",
            "LoveCode": "",
            "CarrierType": "",
            "CarrierNum": "",
            "TimeStamp": str(int(time.time())),
        }

        return await self._make_request(self.b2b_issue_url, params)

    async def void_invoice(
        self,
        invoice_no: str,
        invoice_date: str,
        reason: str,
        is_b2b: bool = False,
    ) -> Dict[str, Any]:
        """
        Void an e-invoice.

        Args:
            invoice_no: Invoice number to void (e.g., AB12345678)
            invoice_date: Original issue date (YYYY-MM-DD)
            reason: Void reason
            is_b2b: Whether this is a B2B invoice
        """
        params = {
            "MerchantID": self.merchant_id,
            "InvoiceNo": invoice_no,
            "InvoiceDate": invoice_date,
            "Reason": reason,
            "TimeStamp": str(int(time.time())),
        }

        url = self.b2b_void_url if is_b2b else self.b2c_void_url
        return await self._make_request(url, params)


def get_einvoice_client() -> ECPayEInvoiceClient:
    """Factory function to create ECPayEInvoiceClient from settings."""
    from app.core.config import get_settings
    settings = get_settings()
    return ECPayEInvoiceClient(
        merchant_id=settings.ECPAY_EINVOICE_MERCHANT_ID,
        hash_key=settings.ECPAY_EINVOICE_HASH_KEY,
        hash_iv=settings.ECPAY_EINVOICE_HASH_IV,
        b2c_issue_url=settings.ECPAY_EINVOICE_URL,
        b2b_issue_url=settings.ECPAY_EINVOICE_B2B_URL,
        b2c_void_url=settings.ECPAY_EINVOICE_VOID_URL,
        b2b_void_url=settings.ECPAY_EINVOICE_B2B_VOID_URL,
    )
