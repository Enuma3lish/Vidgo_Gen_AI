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
        # Eager init from env / Secret Manager — gives a sensible default
        # when there is no DB session (e.g. health checks, scripts). The
        # `refresh_from_db()` method below is called by every endpoint
        # that takes an admin-editable DB override into account.
        self._apply_values(
            client_id=getattr(settings, 'PAYPAL_CLIENT_ID', '') or '',
            client_secret=getattr(settings, 'PAYPAL_CLIENT_SECRET', '') or '',
            webhook_id=getattr(settings, 'PAYPAL_WEBHOOK_ID', '') or '',
            env=(getattr(settings, 'PAYPAL_ENV', 'sandbox') or 'sandbox'),
        )
        self.webhook_secret = getattr(settings, 'PAYPAL_WEBHOOK_SECRET', '')

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        if self.is_mock:
            logger.warning("PayPal credentials not configured - running in MOCK mode")
        else:
            logger.info(f"PayPal service initialized (sandbox={self.is_sandbox}, url={self.base_url})")

    def _apply_values(self, *, client_id: str, client_secret: str, webhook_id: str, env: str) -> None:
        """Set the cred fields and recompute is_mock / base_url."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.webhook_id = webhook_id
        self.is_mock = not (self.client_id and self.client_secret)
        normalized_env = (env or 'sandbox').lower()
        self.is_sandbox = normalized_env != 'production'
        self.base_url = self.SANDBOX_URL if self.is_sandbox else self.PRODUCTION_URL

    async def refresh_from_db(self, db) -> None:
        """Pick up admin-editable overrides from the payment_settings row.

        Called by subscription / webhook flows before any PayPal API call.
        If the DB row has values they win; otherwise we keep the env-derived
        defaults set in __init__. Cheap: PaymentSettingsService caches the
        resolved values for 60s in-process.
        """
        from app.services.payment_settings_service import get_resolved_settings
        r = await get_resolved_settings(db)
        new_cid = r.paypal_client_id
        new_secret = r.paypal_client_secret
        if (new_cid != self.client_id) or (new_secret != self.client_secret):
            # Token cached against old creds is now invalid — drop it so the
            # next request fetches a fresh OAuth token against the new pair.
            self._access_token = None
            self._token_expires_at = 0.0
        self._apply_values(
            client_id=new_cid,
            client_secret=new_secret,
            webhook_id=r.paypal_webhook_id,
            env=r.paypal_env,
        )

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
    # CHECKOUT (PayPal Subscriptions v1 or Orders v2)
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
        Create a PayPal checkout. ``price_id`` represents either a PayPal Plan
        ID (``P-*`` for subscriptions) or an opaque SKU for one-time orders.

        Returns ``checkout_url`` (the approve link) and ``transaction_id``
        (the PayPal subscription id or order id).
        """
        if self.is_mock:
            return self._mock_checkout_session(user_id, user_email, plan_id, billing_cycle)

        # PayPal-Request-Id is PayPal's idempotency key. Bind it to the
        # logical (user, plan, cycle, price) tuple so retries from our
        # frontend do not create duplicate subscriptions/orders.
        import uuid as _uuid
        request_id = _uuid.uuid5(
            _uuid.NAMESPACE_URL,
            f"vidgo:checkout:{user_id}:{plan_id}:{billing_cycle}:{price_id}",
        ).hex

        try:
            if billing_cycle != "one-time" and price_id.startswith("P-"):
                custom_id = json.dumps(
                    {"u": str(user_id), "p": plan_id, "c": billing_cycle[:1]},
                    separators=(",", ":"),
                )
                payload = {
                    "plan_id": price_id,
                    "custom_id": custom_id,
                    "subscriber": {"email_address": user_email},
                    "application_context": {
                        "brand_name": "VidGo",
                        "locale": "zh-TW",
                        "shipping_preference": "NO_SHIPPING",
                        "user_action": "SUBSCRIBE_NOW",
                        "return_url": success_url or f"{settings.FRONTEND_URL}/subscription/success",
                        "cancel_url": cancel_url or f"{settings.FRONTEND_URL}/subscription/cancelled",
                    },
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    headers = await self._auth_headers()
                    headers["PayPal-Request-Id"] = request_id
                    response = await client.post(
                        f"{self.base_url}/v1/billing/subscriptions",
                        headers=headers,
                        json=payload,
                    )
                    if response.status_code in (200, 201):
                        data = response.json()
                        approve = next(
                            (link["href"] for link in data.get("links", []) if link.get("rel") == "approve"),
                            None,
                        )
                        return {
                            "success": True,
                            "checkout_url": approve,
                            "transaction_id": data.get("id"),
                            "paypal_response": data,
                        }
                    logger.error(f"PayPal subscription checkout failed: {response.text}")
                    return {"success": False, "error": f"PayPal API error: {response.status_code}"}

            if amount_usd is None or amount_usd <= 0:
                return {"success": False, "error": "amount_usd must be positive for one-time orders"}
            value = f"{amount_usd:.2f}"
            payload = {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": str(user_id),
                        # Keep custom_id short — PayPal limits to 127 chars.
                        "custom_id": json.dumps(
                            {"u": str(user_id), "p": plan_id, "c": billing_cycle[:1]},
                            separators=(",", ":"),
                        ),
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
                headers = await self._auth_headers()
                headers["PayPal-Request-Id"] = request_id
                response = await client.post(
                    f"{self.base_url}/v2/checkout/orders",
                    headers=headers,
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
    # ONE-TIME ORDERS (PayPal Orders v2) — credit packs
    # =========================================================================

    async def get_order(self, order_id: str) -> Dict[str, Any]:
        """Get an Orders-v2 order (status / purchase_units / captures)."""
        if self.is_mock:
            return {
                "success": True,
                "is_mock": True,
                "order": {"id": order_id, "status": "COMPLETED"},
            }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v2/checkout/orders/{order_id}",
                    headers=await self._auth_headers(),
                )
                if response.status_code == 200:
                    return {"success": True, "order": response.json()}
                return {"success": False, "error": f"Order lookup failed: {response.status_code}"}
        except Exception as exc:
            logger.error(f"Get PayPal order error for {order_id}: {exc}")
            return {"success": False, "error": str(exc)}

    async def capture_order(self, order_id: str) -> Dict[str, Any]:
        """Capture an APPROVED Orders-v2 order — the step that actually moves
        the money. ``create_checkout_session`` only CREATES the order and the
        buyer's approval only AUTHORIZES it; without this call PayPal never
        charges and PAYMENT.CAPTURE.COMPLETED never fires (the credit-pack
        flow was dormant until 2026-07-10 because nobody called it).

        Safe to call twice (approval webhook + return-leg endpoint can race):
        PayPal-Request-Id is bound to the order id, and the
        ORDER_ALREADY_CAPTURED error is normalized to success by re-reading
        the order.
        """
        if self.is_mock:
            return {
                "success": True,
                "is_mock": True,
                "status": "COMPLETED",
                "order": {"id": order_id, "status": "COMPLETED"},
            }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = await self._auth_headers()
                headers["PayPal-Request-Id"] = f"capture-{order_id}"
                response = await client.post(
                    f"{self.base_url}/v2/checkout/orders/{order_id}/capture",
                    headers=headers,
                    json={},
                )
                if response.status_code in (200, 201):
                    data = response.json()
                    return {"success": True, "status": data.get("status"), "order": data}
                if response.status_code == 422 and "ORDER_ALREADY_CAPTURED" in response.text:
                    current = await self.get_order(order_id)
                    order = current.get("order") or {}
                    return {
                        "success": bool(current.get("success")) and order.get("status") == "COMPLETED",
                        "status": order.get("status"),
                        "order": order,
                        "already_captured": True,
                    }
                logger.error(f"PayPal capture failed for {order_id}: {response.status_code} {response.text}")
                return {"success": False, "error": f"PayPal capture error: {response.status_code}"}
        except Exception as exc:
            logger.error(f"PayPal capture error for {order_id}: {exc}")
            return {"success": False, "error": str(exc)}

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

    async def get_subscription_transactions(
        self,
        subscription_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List PayPal subscription transactions (captures) for a subscription."""
        if self.is_mock:
            return {"success": True, "is_mock": True, "transactions": []}
        if not start_time:
            start_time = (datetime.utcnow() - timedelta(days=370)).strftime("%Y-%m-%dT%H:%M:%SZ")
        if not end_time:
            end_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            params = {"start_time": start_time, "end_time": end_time}
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/billing/subscriptions/{subscription_id}/transactions",
                    headers=await self._auth_headers(),
                    params=params,
                )
                if response.status_code == 200:
                    data = response.json() or {}
                    return {"success": True, "transactions": data.get("transactions", [])}
                logger.error(f"PayPal subscription transactions failed: {response.text}")
                return {"success": False, "error": f"List failed: {response.status_code}"}
        except Exception as exc:
            logger.error(f"PayPal subscription transactions error: {exc}")
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
            import uuid as _uuid
            request_id = _uuid.uuid5(_uuid.NAMESPACE_URL, f"vidgo:refund:{transaction_id}:{amount or 'full'}").hex
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = await self._auth_headers()
                headers["PayPal-Request-Id"] = request_id
                response = await client.post(
                    f"{self.base_url}/v2/payments/captures/{transaction_id}/refund",
                    headers=headers,
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
    # WEBHOOK VERIFICATION (PayPal /v1/notifications/verify-webhook-signature)
    # =========================================================================

    async def verify_webhook_signature(
        self,
        body: bytes,
        headers: Dict[str, str],
    ) -> bool:
        """
        Verify a PayPal webhook by calling PayPal's verify-webhook-signature API.

        PayPal signs webhooks with RSA + a rotating cert chain — there is no
        local-only verification. We must POST the raw event back to PayPal
        along with the transmission headers and our configured webhook id.

        Returns True only when PayPal answers SUCCESS. In mock mode (no creds),
        verification is skipped (returns True). When PAYPAL_WEBHOOK_ID is not
        configured, returns False — webhook MUST be rejected so production
        cannot accept unsigned payloads.
        """
        if self.is_mock:
            return True
        if not self.webhook_id:
            logger.error("PAYPAL_WEBHOOK_ID is not configured — rejecting webhook")
            return False

        def _h(name: str) -> str:
            return headers.get(name) or headers.get(name.lower()) or headers.get(name.upper()) or ""

        try:
            event_body = json.loads(body.decode("utf-8") or "{}")
        except Exception as exc:
            logger.warning(f"PayPal webhook body is not valid JSON: {exc}")
            return False

        verification_payload = {
            "auth_algo": _h("Paypal-Auth-Algo"),
            "cert_url": _h("Paypal-Cert-Url"),
            "transmission_id": _h("Paypal-Transmission-Id"),
            "transmission_sig": _h("Paypal-Transmission-Sig"),
            "transmission_time": _h("Paypal-Transmission-Time"),
            "webhook_id": self.webhook_id,
            "webhook_event": event_body,
        }
        # Required fields must be present.
        for key in ("auth_algo", "cert_url", "transmission_id", "transmission_sig", "transmission_time"):
            if not verification_payload[key]:
                logger.warning(f"PayPal webhook missing header: {key}")
                return False

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/notifications/verify-webhook-signature",
                    headers=await self._auth_headers(),
                    json=verification_payload,
                )
                if response.status_code != 200:
                    logger.warning(f"PayPal webhook verify HTTP {response.status_code}: {response.text}")
                    return False
                status = (response.json() or {}).get("verification_status", "")
                ok = status == "SUCCESS"
                if not ok:
                    logger.warning(f"PayPal webhook verify_status={status}")
                return ok
        except Exception as exc:
            logger.error(f"PayPal webhook verification error: {exc}")
            return False

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """
        DEPRECATED: legacy HMAC fallback retained for backwards compatibility.

        Real PayPal webhooks must be verified with `verify_webhook_signature`
        (which calls PayPal's verify API). This method is unsafe for production
        and is only kept so existing import sites do not break — it now logs an
        error and returns False unless we are in mock mode.
        """
        if self.is_mock:
            return True
        logger.error("paypal.verify_webhook (HMAC) is deprecated — use verify_webhook_signature instead")
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

    # =========================================================================
    # INVOICING v2 (PayPal-hosted invoices alongside Giveme/ECPay)
    # Docs: https://developer.paypal.com/docs/api/invoicing/v2/
    # =========================================================================

    async def generate_invoice_number(self) -> Dict[str, Any]:
        """POST /v2/invoicing/generate-next-invoice-number"""
        if self.is_mock:
            import uuid as _uuid
            return {"success": True, "is_mock": True, "invoice_number": f"MOCK-{_uuid.uuid4().hex[:8].upper()}"}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v2/invoicing/generate-next-invoice-number",
                    headers=await self._auth_headers(),
                )
                if response.status_code in (200, 201):
                    data = response.json() or {}
                    return {"success": True, "invoice_number": data.get("invoice_number")}
                logger.error(f"PayPal generate-invoice-number failed: {response.text}")
                return {"success": False, "error": f"Generate failed: {response.status_code}"}
        except Exception as exc:
            logger.error(f"PayPal generate-invoice-number error: {exc}")
            return {"success": False, "error": str(exc)}

    async def create_invoice(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST /v2/invoicing/invoices — create draft invoice."""
        if self.is_mock:
            import uuid as _uuid
            mock_id = f"INV2-MOCK-{_uuid.uuid4().hex[:10].upper()}"
            return {"success": True, "is_mock": True, "invoice_id": mock_id, "invoice": {"id": mock_id}}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v2/invoicing/invoices",
                    headers=await self._auth_headers(),
                    json=payload,
                )
                if response.status_code in (200, 201, 202):
                    data = response.json() or {}
                    invoice_id = data.get("id")
                    if not invoice_id:
                        # PayPal returns 202 with Location header pointing at the new invoice.
                        location = response.headers.get("Location") or ""
                        if location:
                            invoice_id = location.rstrip("/").rsplit("/", 1)[-1]
                    return {"success": True, "invoice_id": invoice_id, "invoice": data}
                logger.error(f"PayPal create-invoice failed: {response.text}")
                return {"success": False, "error": f"Create failed: {response.status_code}"}
        except Exception as exc:
            logger.error(f"PayPal create-invoice error: {exc}")
            return {"success": False, "error": str(exc)}

    async def send_invoice(
        self, invoice_id: str, send_to_recipient: bool = True
    ) -> Dict[str, Any]:
        """POST /v2/invoicing/invoices/{id}/send — send invoice to recipient."""
        if self.is_mock:
            return {"success": True, "is_mock": True}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v2/invoicing/invoices/{invoice_id}/send",
                    headers=await self._auth_headers(),
                    json={"send_to_recipient": send_to_recipient},
                )
                if response.status_code in (200, 202):
                    return {"success": True}
                logger.error(f"PayPal send-invoice failed: {response.text}")
                return {"success": False, "error": f"Send failed: {response.status_code}"}
        except Exception as exc:
            logger.error(f"PayPal send-invoice error: {exc}")
            return {"success": False, "error": str(exc)}

    async def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """GET /v2/invoicing/invoices/{id}"""
        if self.is_mock:
            return {"success": True, "is_mock": True, "invoice": {"id": invoice_id}}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v2/invoicing/invoices/{invoice_id}",
                    headers=await self._auth_headers(),
                )
                if response.status_code == 200:
                    return {"success": True, "invoice": response.json()}
                return {"success": False, "error": f"Get failed: {response.status_code}"}
        except Exception as exc:
            logger.error(f"PayPal get-invoice error: {exc}")
            return {"success": False, "error": str(exc)}

    async def cancel_invoice(
        self,
        invoice_id: str,
        subject: str = "Invoice cancelled",
        note: str = "Subscription refunded — invoice cancelled.",
        send_to_recipient: bool = True,
        send_to_invoicer: bool = True,
    ) -> Dict[str, Any]:
        """POST /v2/invoicing/invoices/{id}/cancel — cancel a sent invoice."""
        if self.is_mock:
            return {"success": True, "is_mock": True}
        payload = {
            "subject": subject,
            "note": note,
            "send_to_recipient": send_to_recipient,
            "send_to_invoicer": send_to_invoicer,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v2/invoicing/invoices/{invoice_id}/cancel",
                    headers=await self._auth_headers(),
                    json=payload,
                )
                if response.status_code in (200, 204):
                    return {"success": True}
                logger.error(f"PayPal cancel-invoice failed: {response.text}")
                return {"success": False, "error": f"Cancel failed: {response.status_code}"}
        except Exception as exc:
            logger.error(f"PayPal cancel-invoice error: {exc}")
            return {"success": False, "error": str(exc)}


# Singleton instance
_paypal_service: Optional[PayPalService] = None


def get_paypal_service() -> PayPalService:
    """Get or create PayPal service singleton."""
    global _paypal_service
    if _paypal_service is None:
        _paypal_service = PayPalService()
    return _paypal_service
