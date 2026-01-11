"""
Paddle Payment Service

Handles Paddle API integration for:
- Subscription checkout
- Payment verification
- Subscription management (cancel, pause, resume)
- Refund processing

When PADDLE_API_KEY is not configured, provides mock functionality
for development and testing.

API Docs: https://developer.paddle.com/
"""
import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PaddleService:
    """
    Paddle Payment Service.

    Supports both live Paddle API calls and mock mode for development.
    When PADDLE_API_KEY is empty, operates in mock mode.
    """

    # Paddle API endpoints
    SANDBOX_URL = "https://sandbox-api.paddle.com"
    PRODUCTION_URL = "https://api.paddle.com"

    def __init__(self):
        self.api_key = getattr(settings, 'PADDLE_API_KEY', '')
        self.public_key = getattr(settings, 'PADDLE_PUBLIC_KEY', '')
        self.is_mock = not bool(self.api_key)

        # Use sandbox in development
        self.base_url = self.SANDBOX_URL if settings.DEBUG else self.PRODUCTION_URL

        if self.is_mock:
            logger.warning("Paddle API key not configured - running in MOCK mode")
        else:
            logger.info(f"Paddle service initialized (sandbox={settings.DEBUG})")

    def _get_headers(self) -> Dict[str, str]:
        """Get API headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    # =========================================================================
    # SUBSCRIPTION CHECKOUT
    # =========================================================================

    async def create_checkout_session(
        self,
        user_id: UUID,
        user_email: str,
        plan_id: str,
        price_id: str,
        billing_cycle: str = "monthly",
        success_url: str = None,
        cancel_url: str = None
    ) -> Dict[str, Any]:
        """
        Create a Paddle checkout session for subscription.

        Args:
            user_id: User's UUID
            user_email: User's email
            plan_id: Internal plan ID
            price_id: Paddle price ID
            billing_cycle: 'monthly' or 'yearly'
            success_url: URL to redirect after success
            cancel_url: URL to redirect after cancel

        Returns:
            Dict with checkout_url and session_id
        """
        if self.is_mock:
            return self._mock_checkout_session(
                user_id, user_email, plan_id, billing_cycle
            )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/transactions",
                    headers=self._get_headers(),
                    json={
                        "items": [
                            {
                                "price_id": price_id,
                                "quantity": 1
                            }
                        ],
                        "customer": {
                            "email": user_email
                        },
                        "custom_data": {
                            "user_id": str(user_id),
                            "plan_id": plan_id,
                            "billing_cycle": billing_cycle
                        },
                        "checkout": {
                            "url": success_url or f"{settings.FRONTEND_URL}/subscription/success"
                        }
                    }
                )

                if response.status_code in [200, 201]:
                    data = response.json()
                    return {
                        "success": True,
                        "checkout_url": data.get("data", {}).get("checkout", {}).get("url"),
                        "transaction_id": data.get("data", {}).get("id"),
                        "paddle_response": data
                    }
                else:
                    logger.error(f"Paddle checkout failed: {response.text}")
                    return {
                        "success": False,
                        "error": f"Paddle API error: {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Paddle checkout error: {e}")
            return {"success": False, "error": str(e)}

    def _mock_checkout_session(
        self,
        user_id: UUID,
        user_email: str,
        plan_id: str,
        billing_cycle: str
    ) -> Dict[str, Any]:
        """Mock checkout session for development."""
        import uuid
        mock_txn_id = f"txn_mock_{uuid.uuid4().hex[:12]}"

        return {
            "success": True,
            "is_mock": True,
            "checkout_url": f"{settings.FRONTEND_URL}/subscription/mock-checkout?txn={mock_txn_id}",
            "transaction_id": mock_txn_id,
            "message": "Mock mode - no actual payment required"
        }

    # =========================================================================
    # SUBSCRIPTION MANAGEMENT
    # =========================================================================

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Get subscription details from Paddle.

        Args:
            subscription_id: Paddle subscription ID

        Returns:
            Subscription details
        """
        if self.is_mock:
            return self._mock_subscription(subscription_id)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/subscriptions/{subscription_id}",
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "subscription": data.get("data", {})
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Subscription not found: {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Get subscription error: {e}")
            return {"success": False, "error": str(e)}

    def _mock_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Mock subscription for development."""
        return {
            "success": True,
            "is_mock": True,
            "subscription": {
                "id": subscription_id,
                "status": "active",
                "current_billing_period": {
                    "starts_at": datetime.utcnow().isoformat(),
                    "ends_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
                },
                "next_billed_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
            }
        }

    async def cancel_subscription(
        self,
        subscription_id: str,
        effective_from: str = "next_billing_period"
    ) -> Dict[str, Any]:
        """
        Cancel a Paddle subscription.

        Args:
            subscription_id: Paddle subscription ID
            effective_from: 'immediately' or 'next_billing_period'

        Returns:
            Cancellation result
        """
        if self.is_mock:
            return {
                "success": True,
                "is_mock": True,
                "message": "Subscription cancelled (mock mode)",
                "effective_from": effective_from
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/subscriptions/{subscription_id}/cancel",
                    headers=self._get_headers(),
                    json={
                        "effective_from": effective_from
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "subscription": data.get("data", {}),
                        "effective_from": effective_from
                    }
                else:
                    logger.error(f"Cancel subscription failed: {response.text}")
                    return {
                        "success": False,
                        "error": f"Cancel failed: {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Cancel subscription error: {e}")
            return {"success": False, "error": str(e)}

    async def pause_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Pause a subscription."""
        if self.is_mock:
            return {
                "success": True,
                "is_mock": True,
                "message": "Subscription paused (mock mode)"
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/subscriptions/{subscription_id}/pause",
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    return {"success": True, "subscription": response.json().get("data", {})}
                else:
                    return {"success": False, "error": f"Pause failed: {response.status_code}"}

        except Exception as e:
            logger.error(f"Pause subscription error: {e}")
            return {"success": False, "error": str(e)}

    async def resume_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Resume a paused subscription."""
        if self.is_mock:
            return {
                "success": True,
                "is_mock": True,
                "message": "Subscription resumed (mock mode)"
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/subscriptions/{subscription_id}/resume",
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    return {"success": True, "subscription": response.json().get("data", {})}
                else:
                    return {"success": False, "error": f"Resume failed: {response.status_code}"}

        except Exception as e:
            logger.error(f"Resume subscription error: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # REFUND PROCESSING
    # =========================================================================

    async def create_refund(
        self,
        transaction_id: str,
        reason: str = "customer_request",
        amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create a refund for a transaction.

        Args:
            transaction_id: Paddle transaction ID
            reason: Refund reason
            amount: Partial refund amount (None = full refund)

        Returns:
            Refund result
        """
        if self.is_mock:
            return {
                "success": True,
                "is_mock": True,
                "refund_id": f"ref_mock_{transaction_id[:8]}",
                "message": "Refund processed (mock mode)",
                "amount_refunded": amount
            }

        try:
            payload = {
                "transaction_id": transaction_id,
                "reason": reason
            }

            if amount:
                payload["amount"] = str(amount)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/adjustments",
                    headers=self._get_headers(),
                    json=payload
                )

                if response.status_code in [200, 201]:
                    data = response.json()
                    return {
                        "success": True,
                        "refund": data.get("data", {}),
                        "refund_id": data.get("data", {}).get("id")
                    }
                else:
                    logger.error(f"Refund failed: {response.text}")
                    return {
                        "success": False,
                        "error": f"Refund failed: {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Refund error: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # WEBHOOK VERIFICATION
    # =========================================================================

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Verify Paddle webhook signature.

        Args:
            payload: Raw request body
            signature: Paddle-Signature header

        Returns:
            True if valid, False otherwise
        """
        if self.is_mock:
            return True

        if not self.public_key:
            logger.warning("Paddle public key not configured")
            return False

        try:
            # Parse the signature header
            # Format: ts=timestamp;h1=signature
            parts = dict(p.split("=", 1) for p in signature.split(";"))
            ts = parts.get("ts", "")
            h1 = parts.get("h1", "")

            # Compute expected signature
            signed_payload = f"{ts}:{payload.decode()}"
            expected = hmac.new(
                self.public_key.encode(),
                signed_payload.encode(),
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(expected, h1)

        except Exception as e:
            logger.error(f"Webhook verification error: {e}")
            return False

    # =========================================================================
    # CUSTOMER MANAGEMENT
    # =========================================================================

    async def get_or_create_customer(
        self,
        email: str,
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get or create a Paddle customer."""
        if self.is_mock:
            import uuid
            return {
                "success": True,
                "is_mock": True,
                "customer_id": f"ctm_mock_{uuid.uuid4().hex[:12]}",
                "email": email
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # First try to find existing customer
                response = await client.get(
                    f"{self.base_url}/customers",
                    headers=self._get_headers(),
                    params={"email": email}
                )

                if response.status_code == 200:
                    data = response.json()
                    customers = data.get("data", [])
                    if customers:
                        return {
                            "success": True,
                            "customer_id": customers[0]["id"],
                            "customer": customers[0]
                        }

                # Create new customer
                create_response = await client.post(
                    f"{self.base_url}/customers",
                    headers=self._get_headers(),
                    json={
                        "email": email,
                        "name": name
                    }
                )

                if create_response.status_code in [200, 201]:
                    data = create_response.json()
                    return {
                        "success": True,
                        "customer_id": data.get("data", {}).get("id"),
                        "customer": data.get("data", {})
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Customer creation failed: {create_response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Customer management error: {e}")
            return {"success": False, "error": str(e)}

    async def get_customer_portal_url(
        self,
        customer_id: str
    ) -> Dict[str, Any]:
        """Get Paddle customer portal URL for self-service."""
        if self.is_mock:
            return {
                "success": True,
                "is_mock": True,
                "portal_url": f"{settings.FRONTEND_URL}/account/billing",
                "message": "Mock portal URL"
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/customers/{customer_id}/portal-sessions",
                    headers=self._get_headers()
                )

                if response.status_code in [200, 201]:
                    data = response.json()
                    return {
                        "success": True,
                        "portal_url": data.get("data", {}).get("urls", {}).get("general")
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Portal session failed: {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Portal session error: {e}")
            return {"success": False, "error": str(e)}


# Singleton instance
_paddle_service: Optional[PaddleService] = None


def get_paddle_service() -> PaddleService:
    """Get or create Paddle service singleton."""
    global _paddle_service
    if _paddle_service is None:
        _paddle_service = PaddleService()
    return _paddle_service
