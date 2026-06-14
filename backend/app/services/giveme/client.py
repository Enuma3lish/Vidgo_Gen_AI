"""
Giveme E-Invoice Client — Taiwan Electronic Invoice (電子發票)

Provider: Giveme 電子發票加值中心 (https://www.giveme.com.tw)
API Docs: See docs/payment_and_infra.md

Supported operations:
- B2C invoice issuance (一般消費者發票)
- B2B invoice issuance (有統編的發票)
- Invoice voiding (發票作廢)
- Invoice query (發票查詢)
- Invoice print/image (發票列印)

Authentication: sign = MD5(timeStamp + idno + password).toUpperCase()
IP whitelist required on Giveme backend.
"""
import hashlib
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class GivemeClient:
    """Giveme E-Invoice API Client."""

    BASE_URL = "https://www.giveme.com.tw/invoice.do"

    def __init__(
        self,
        uncode: str,
        idno: str,
        password: str,
        base_url: Optional[str] = None,
    ):
        """
        Args:
            uncode: Company unified business number (統一編號)
            idno: API account ID (from Giveme backend 系統設定→員工設定)
            password: API account password
            base_url: Override base URL (for testing)
        """
        self.uncode = uncode
        self.idno = idno
        self.password = password
        self.base_url = base_url or self.BASE_URL

    # ─────────────────────────────────────────────────────────────────────
    # AUTH
    # ─────────────────────────────────────────────────────────────────────

    def _timestamp(self) -> str:
        """Current time in milliseconds (五分鐘內有效)."""
        return str(int(time.time() * 1000))

    def _sign(self, timestamp: str) -> str:
        """Generate sign = MD5(timeStamp + idno + password).toUpperCase()."""
        raw = f"{timestamp}{self.idno}{self.password}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()

    def _base_params(self) -> Dict[str, str]:
        """Common auth parameters for all requests."""
        ts = self._timestamp()
        return {
            "timeStamp": ts,
            "uncode": self.uncode,
            "idno": self.idno,
            "sign": self._sign(ts),
        }

    # ─────────────────────────────────────────────────────────────────────
    # B2C INVOICE (1.1.1)
    # ─────────────────────────────────────────────────────────────────────

    async def create_b2c_invoice(
        self,
        *,
        total_fee: int,
        content: str,
        items: List[Dict[str, Any]],
        invoice_date: Optional[str] = None,
        customer_name: Optional[str] = None,
        phone: Optional[str] = None,
        order_code: Optional[str] = None,
        email: Optional[str] = None,
        is_donation: bool = False,
        donation_code: Optional[str] = None,
        tax_type: int = 0,
    ) -> Dict[str, Any]:
        """
        Create B2C invoice (一般消費者).

        Args:
            total_fee: Total amount (must be >= 1)
            content: General remark (shown on invoice)
            items: List of {"name": str, "money": int, "number": int}
            invoice_date: "yyyy-MM-dd" (defaults to today)
            customer_name: Internal note (not printed on invoice)
            phone: Mobile barcode carrier (e.g. "/1234567")
            order_code: Custom carrier/order number
            email: Customer email
            is_donation: Whether to donate invoice
            donation_code: Charity love code (required if is_donation=True)
            tax_type: 0=taxable, 1=zero-tax, 2=tax-free, 3=special, 4=mixed

        Returns:
            {"success": True/False, "code": "AB12345678", "msg": "...", ...}
        """
        if not invoice_date:
            invoice_date = datetime.now().strftime("%Y-%m-%d")

        payload = {
            **self._base_params(),
            "datetime": invoice_date,
            "state": "1" if is_donation else "0",
            "totalFee": str(total_fee),
            "content": content,
            "items": items,
        }

        if customer_name:
            payload["customerName"] = customer_name
        if phone:
            payload["phone"] = phone
        if order_code:
            payload["orderCode"] = order_code
        if email:
            payload["email"] = email
        if is_donation and donation_code:
            payload["donationCode"] = donation_code
        if tax_type != 0:
            payload["taxType"] = tax_type

        return await self._post("addB2C", payload)

    # ─────────────────────────────────────────────────────────────────────
    # B2B INVOICE (1.1.2)
    # ─────────────────────────────────────────────────────────────────────

    async def create_b2b_invoice(
        self,
        *,
        buyer_tax_id: str,
        total_fee: int,
        content: str,
        items: List[Dict[str, Any]],
        invoice_date: Optional[str] = None,
        customer_name: Optional[str] = None,
        email: Optional[str] = None,
        tax_state: str = "0",
        tax_type: int = 0,
    ) -> Dict[str, Any]:
        """
        Create B2B invoice (有統編的發票).

        Args:
            buyer_tax_id: Buyer's unified business number (8 digits)
            total_fee: Total amount (tax included if tax_state=0)
            content: General remark
            items: List of {"name": str, "money": int/float, "number": int}
            tax_state: "0"=tax included (default), "1"=tax excluded
        """
        if not invoice_date:
            invoice_date = datetime.now().strftime("%Y-%m-%d")

        # Calculate tax amounts (5% VAT for Taiwan)
        if tax_state == "0":
            sales = int(total_fee / 1.05)
            amount = total_fee - sales
        else:
            sales = total_fee
            amount = int(total_fee * 0.05)

        payload = {
            **self._base_params(),
            "phone": buyer_tax_id,  # B2B uses "phone" field for buyer tax ID
            "datetime": invoice_date,
            "taxState": tax_state,
            "totalFee": str(total_fee),
            "amount": str(amount),
            "sales": str(sales),
            "content": content,
            "items": items,
        }

        if customer_name:
            payload["customerName"] = customer_name
        if email:
            payload["email"] = email
        if tax_type != 0:
            payload["taxType"] = tax_type

        return await self._post("addB2B", payload)

    # ─────────────────────────────────────────────────────────────────────
    # VOID INVOICE (1.1.3)
    # ─────────────────────────────────────────────────────────────────────

    async def void_invoice(
        self,
        invoice_code: str,
        reason: str = "Customer refund",
    ) -> Dict[str, Any]:
        """
        Void an invoice (作廢發票).

        Args:
            invoice_code: Invoice number (e.g. "AB12345678")
            reason: Void reason
        """
        payload = {
            **self._base_params(),
            "code": invoice_code,
            "remark": reason,
        }
        return await self._post("cancelInvoice", payload)

    # ─────────────────────────────────────────────────────────────────────
    # QUERY INVOICE (2.1)
    # ─────────────────────────────────────────────────────────────────────

    async def query_invoice(self, invoice_code: str) -> Dict[str, Any]:
        """
        Query invoice details (查詢發票).

        Returns invoice status, items, amounts, carrier info.
        """
        payload = {
            **self._base_params(),
            "code": invoice_code,
        }
        return await self._post("query", payload)

    # ─────────────────────────────────────────────────────────────────────
    # PRINT INVOICE (1.1.4 / 1.1.5)
    # ─────────────────────────────────────────────────────────────────────

    async def get_invoice_print_url(self, invoice_code: str) -> str:
        """Get invoice print URL (web mode)."""
        return (
            f"{self.base_url}?action=invoicePrint"
            f"&code={invoice_code}&uncode={self.uncode}"
        )

    async def get_invoice_image(
        self,
        invoice_code: str,
        image_type: str = "1",
    ) -> Dict[str, Any]:
        """
        Get invoice as image (圖片列印).

        Args:
            invoice_code: Invoice number
            image_type: "1"=full (proof+detail), "2"=proof only, "3"=detail only
        """
        payload = {
            **self._base_params(),
            "code": invoice_code,
            "type": image_type,
        }
        return await self._post("picture", payload, raw_response=True)

    # ─────────────────────────────────────────────────────────────────────
    # HTTP
    # ─────────────────────────────────────────────────────────────────────

    async def _post(
        self,
        action: str,
        payload: Dict[str, Any],
        raw_response: bool = False,
    ) -> Dict[str, Any]:
        """Send POST request to Giveme API."""
        url = f"{self.base_url}?action={action}"

        logger.info(f"[Giveme] {action}: totalFee={payload.get('totalFee', '?')}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if raw_response:
                    # For image endpoints that return binary stream
                    if resp.headers.get("content-type", "").startswith("image"):
                        return {"success": True, "data": resp.content}
                    # Fallback to JSON
                    try:
                        return resp.json()
                    except Exception:
                        return {"success": False, "msg": resp.text[:200]}

                data = resp.json()
                success = str(data.get("success", "")).lower() == "true"

                if success:
                    logger.info(
                        f"[Giveme] {action} OK: invoice={data.get('code', '?')}"
                    )
                else:
                    logger.warning(
                        f"[Giveme] {action} FAILED: {data.get('msg', '?')}"
                    )

                return {
                    "success": success,
                    "code": data.get("code"),
                    "msg": data.get("msg"),
                    "totalFee": data.get("totalFee"),
                    "orderCode": data.get("orderCode"),
                    "phone": data.get("phone"),
                    # Query response extras
                    "type": data.get("type"),
                    "tranno": data.get("tranno"),
                    "email": data.get("email"),
                    "randomCode": data.get("randomCode"),
                    "datetime": data.get("datetime"),
                    "status": data.get("status"),
                    "details": data.get("details"),
                    "raw": data,
                }

        except httpx.TimeoutException:
            logger.error(f"[Giveme] {action} timeout")
            return {"success": False, "msg": "Giveme API timeout"}
        except Exception as e:
            logger.error(f"[Giveme] {action} error: {e}")
            return {"success": False, "msg": str(e)}


# ─────────────────────────────────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────────────────────────────────

_giveme_client: Optional[GivemeClient] = None


def get_giveme_client() -> Optional[GivemeClient]:
    """Get or create Giveme client singleton. Returns None if not configured."""
    global _giveme_client
    if _giveme_client:
        return _giveme_client

    from app.core.config import get_settings
    settings = get_settings()

    uncode = getattr(settings, "GIVEME_UNCODE", "")
    idno = getattr(settings, "GIVEME_IDNO", "")
    password = getattr(settings, "GIVEME_PASSWORD", "")

    if not all([uncode, idno, password]):
        logger.info("[Giveme] Not configured (missing GIVEME_UNCODE/IDNO/PASSWORD)")
        return None

    base_url = getattr(settings, "GIVEME_BASE_URL", GivemeClient.BASE_URL)
    _giveme_client = GivemeClient(
        uncode=uncode,
        idno=idno,
        password=password,
        base_url=base_url,
    )
    logger.info(f"[Giveme] Client initialized for 統一編號={uncode}")
    return _giveme_client
