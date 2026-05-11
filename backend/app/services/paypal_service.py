"""
PayPal Payment Service

Handles PayPal REST API integration for:
- Subscription / order checkout (Orders v2)
- Payment verification
- Subscription management (cancel, suspend, activate)
- Refund processing (Payments v2)

When PAYPAL_CLIENT_ID is not configured, provides mock functionality
for development and testing.

API Docs: https://developer.paypal.com/api/rest/
"""
import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID
import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PayPalService:
    """
    PayPal Payment Service.

    Supports both live PayPal API calls and mock mode for development.
    When PAYPAL_CLIENT_ID is empty, operates in mock mode.
    """

    SANDBOX_URL = "https://api-m.sandbox.paypal.com"
    PRODUCTION_URL = "https://api-m.paypal.com"

    def __init__(self):
        self.client_id = getattr(settings, 'PAYPAL_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'PAYPAL_CLIENT_SECRET', '')
        self.webhook_id = getattr(settings, 'PAYPAL_WEBHOOK_ID', '')
        self.webhook_secret = getattr(settings, 'PAYPAL_WEBHOOK_SECRET', '')
        self.is_mock = not (self.client_id and self.client_secret)

        env = (getattr(settings, 'PAYPAL_ENV', 'sandbox') or 'sandbox').lower()
        self.is_sandbox = env != 'production'
        self.base_url = self.SANDBOX_URL if self.is_sandbox else self.PRODUCTION_URL

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        if self.is_mock:
            logger.warning("PayPal credentials not configured - running in MOCK mode")
        else:
            logger.info(f"PayPal service initialized (sandbox={self.is_sandbox}, url={self.base_url})")

    # =========================================================================
    # AUTH
    # =========================================================================

    async def _get_access_token(self) -> str:
        """Fetch / cache an OAuth2 access token."""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        creds = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/oauth2/token",
                headers={
                    "Authorization": f"Basic {creds}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data="grant_type=client_credentials",
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data["access_token"]
            self._token_expires_at = time.time() + int(data.get("expires_in", 3000))
            return self._access_token

    async def _auth_headers(self) -> Dict[str, str]:
        token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # =========================================================================
    # SUBSCRIPTION CHECKOUT (PayPal Orders v2)
    # =========================================================================

    async def create_checkout_session(
        self,
        user_id: UUID,
        user_email: str,
        plan_id: str,
        price_id: str,
        billing_cycle: str = "monthly",
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        amount_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Create a PayPal order. ``price_id`` here represents either a PayPal
        Plan ID (for subscriptions) or an opaque SKU; ``amount_usd`` is used
        as the order total when subscription plans aren't pre-provisioned.

        Returns ``checkout_url`` (the approve link) and ``transaction_id``
        (the PayPal order id).
        """
        if self.is_mock:
            return self._mock_checkout_session(user_id, user_email, plan_id, billing_cycle)

        try:
            value = f"{amount_usd:.2f}" if amount_usd else "0.00"
            payload = {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": str(user_id),
                        "custom_id": json.dumps({
                            "user_id": str(user_id),
                            "plan_id": plan_id,
                            "billing_cycle": billing_cycle,
                            "price_id": price_id,
                        }),
                        "amount": {"currency_code": "USD", "value": value},
                    }
                ],
                "payment_source": {
                    "paypal": {
                        "experience_context": {
                            "return_url": success_url or f"{settings.FRONTEND_URL}/subscription/success",
                            "cancel_url": cancel_url or f"{settings.FRONTEND_URL}/subscription/cancelled",
                            "user_action": "PAY_NOW",
                        }
                    }
                },
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v2/checkout/orders",
                    headers=await self._auth_headers(),
                    json=payload,
                )
                if response.status_code in (200, 201):
                    data = response.json()
                    approve = next(
                        (link["href"] for link in data.get("links", []) if link.get("rel") == "payer-action"),
                        None,
                    ) or next(
                        (link["href"] for link in data.get("links", []) if link.get("rel") == "approve"),
                        None,
                    )
                    return {
                        "success": True,
                        "checkout_url": approve,
                        "transaction_id": data.get("id"),
                        "paypal_response": data,
                    }
                logger.error(f"PayPal checkout failed: {response.text}")
                return {"success": False, "error": f"PayPal API error: {response.status_code}"}
        except Exception as exc:
            logger.error(f"PayPal checkout error: {exc}")
            return {"success": False, "error": str(exc)}

    def _mock_checkout_session(
        self, user_id: UUID, user_email: str, plan_id: str, billing_cycle: str
    ) -> Dict[str, Any]:
        import uuid
        mock_txn_id = f"PAYID_MOCK_{uuid.uuid4().hex[:12].upper()}"
        return {
            "success": True,
            "is_mock": True,
            "checkout_url": f"{settings.FRONTEND_URL}/subscription/mock-checkout?txn={mock_txn_id}",
            "transaction_id": mock_txn_id,
            "message": "Mock mode - no actual payment required",
        }

    # =========================================================================
    # SUBSCRIPTION MANAGEMENT (PayPal Subscriptions v1)
    # =========================================================================

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Get subscription details from PayPal."""
        if self.is_mock:
            return self._mock_subscription(subscription_id)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/billing/subscriptions/{subscription_id}",
                    headers=await self._auth_headers(),
                )
                if response.status_code == 200:
                    return {"success": True, "subscription": response.json()}
                return {"success": False, "error": f"Subscription not found: {response.status_code}"}
        except Exception as exc:
            logger.error(f"Get PayPal subscription error: {exc}")
            return {"success": False, "error": str(exc)}

    def _mock_subscription(self, subscription_id: str) -> Dict[str, Any]:
        return {
            "success": True,
            "is_mock": True,
            "subscription": {
                "id": subscription_id,
                "status": "ACTIVE",
                "billing_info": {
                    "next_billing_time": (datetime.utcnow() + timedelta(days=30)).isoformat()
                },
            },
        }

    async def cancel_subscription(
        self, subscription_id: str, effective_from: str = "next_billing_period"
    ) -> Dict[str, Any]:
        """Cancel a PayPal subscription."""
        if self.is_mock:
            return {
                "success": True,
                "is_mock": True,
                "message": "Subscription cancelled (mock mode)",
                "effective_from": effective_from,
            }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/billing/subscriptions/{subscription_id}/cancel",
                    headers=await self._auth_headers(),
                    json={"reason": "User requested cancellation"},
                )
                if response.status_code in (200, 204):
                    return {"success": True, "effective_from": effective_from}
                logger.error(f"PayPal cancel failed: {response.text}")
                return {"success": False, "error": f"Cancel failed: {response.status_code}"}
        except Exception as exc:
            logger.error(f"PayPal cancel error: {exc}")
            return {"success": False, "error": str(exc)}

    async def pause_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Suspend a PayPal subscription."""
        if self.is_mock:
            return {"success": True, "is_mock": True, "message": "Subscription suspended (mock mode)"}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/billing/subscriptions/{subscription_id}/suspend",
                    headers=await self._auth_headers(),
                    json={"reason": "User requested pause"},
                )
                if response.status_code in (200, 204):
                    return {"success": True}
                return {"success": False, "error": f"Suspend failed: {response.status_code}"}
        except Exception as exc:
            logger.error(f"PayPal suspend error: {exc}")
            return {"success": False, "error": str(exc)}

    async def resume_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Activate a suspended PayPal subscription."""
        if self.is_mock:
            return {"success": True, "is_mock": True, "message": "Subscription resumed (mock mode)"}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/billing/subscriptions/{subscription_id}/activate",
                    headers=await self._auth_headers(),
                    json={"reason": "User requested resume"},
                )
                if response.status_code in (200, 204):
                    return {"success": True}
                return {"success": False, "error": f"Resume failed: {response.status_code}"}
        except Exception as exc:
            logger.error(f"PayPal resume error: {exc}")
            return {"success": False, "error": str(exc)}

    # =========================================================================
    # REFUND PROCESSING (Payments v2)
    # =========================================================================

    async def create_refund(
        self,
        transaction_id: str,
        reason: str = "customer_request",
        amount: Optional[float] = None,
        currency: str = "USD",
    ) -> Dict[str, Any]:
        """Refund a captured PayPal payment. ``transaction_id`` is the capture id."""
        if self.is_mock:
            return {
                "success": True,
                "is_mock": True,
                "refund_id": f"REF_MOCK_{transaction_id[:8]}",
                "message": "Refund processed (mock mode)",
                "amount_refunded": amount,
            }
        try:
            payload: Dict[str, Any] = {"note_to_payer": reason}
            if amount:
                payload["amount"] = {"value": f"{amount:.2f}", "currency_code": currency}
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v2/payments/captures/{transaction_id}/refund",
                    headers=await self._auth_headers(),
                    json=payload,
                )
                if response.status_code in (200, 201):
                    data = response.json()
                    return {"success": True, "refund": data, "refund_id": data.get("id")}
                logger.error(f"PayPal refund failed: {response.text}")
                return {"success": False, "error": f"Refund failed: {response.status_code}"}
        except Exception as exc:
            logger.error(f"PayPal refund error: {exc}")
            return {"success": False, "error": str(exc)}

    # =========================================================================
    # WEBHOOK VERIFICATION
    # =========================================================================

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Best-effort PayPal webhook signature verification.

        For full PCI compliance, replace this with the
        ``/v1/notifications/verify-webhook-signature`` API call. Here we accept
        either a configured shared HMAC secret (``PAYPAL_WEBHOOK_SECRET``) or
        skip verification when none is configured.
        """
        if self.is_mock:
            return True
        if not self.webhook_secret:
            logger.warning("PayPal webhook secret not configured — skipping verification")
            return True
        try:
            expected = hmac.new(
                self.webhook_secret.encode(), payload, hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature or "")
        except Exception as exc:
            logger.error(f"PayPal webhook verification error: {exc}")
            return False

    # =========================================================================
    # CUSTOMER MANAGEMENT (no concept of stored customers — return mock)
    # =========================================================================

    async def get_or_create_customer(
        self, email: str, name: Optional[str] = None
    ) -> Dict[str, Any]:
        """PayPal does not maintain a separate customer object; map by email."""
        import uuid
        return {
            "success": True,
            "is_mock": self.is_mock,
            "customer_id": f"PPC_{uuid.uuid5(uuid.NAMESPACE_URL, email).hex[:12]}",
            "email": email,
        }

    async def get_customer_portal_url(self, customer_id: str) -> Dict[str, Any]:
        """PayPal billing is managed inside paypal.com; return that URL."""
        url = (
            "https://www.sandbox.paypal.com/myaccount/autopay/"
            if self.is_sandbox
            else "https://www.paypal.com/myaccount/autopay/"
        )
        return {"success": True, "is_mock": self.is_mock, "portal_url": url}

    # =========================================================================
    # INVOICE
    # =========================================================================

    async def get_invoice_pdf_url(
        self, transaction_id: str, disposition: str = "inline"
    ) -> Dict[str, Any]:
        """PayPal exposes captures, not invoices. Return the activity URL."""
        if self.is_mock:
            return {
                "success": True,
                "is_mock": True,
                "pdf_url": f"{settings.FRONTEND_URL}/mock-invoice-{transaction_id}.pdf",
            }
        host = "www.sandbox.paypal.com" if self.is_sandbox else "www.paypal.com"
        return {
            "success": True,
            "pdf_url": f"https://{host}/activity/payment/{transaction_id}",
        }


# Singleton instance
_paypal_service: Optional[PayPalService] = None


def get_paypal_service() -> PayPalService:
    """Get or create PayPal service singleton."""
    global _paypal_service
    if _paypal_service is None:
        _paypal_service = PayPalService()
    return _paypal_service
