"""Abuse prevention helpers for public auth and generation endpoints."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx
import redis.asyncio as redis
from fastapi import Request

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass
class AbuseCheckResult:
    allowed: bool
    message: str = ""
    retry_after_seconds: Optional[int] = None


def get_client_ip(request: Request) -> str:
    """Resolve the original client IP behind Cloud Run/load balancers."""
    for header in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
        value = request.headers.get(header)
        if not value:
            continue
        first = value.split(",", 1)[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


class AbusePreventionService:
    """Redis-backed rate limits plus optional reCAPTCHA verification."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client

    async def _check_limit(self, key: str, max_count: int, window_seconds: int) -> AbuseCheckResult:
        if max_count <= 0 or window_seconds <= 0:
            return AbuseCheckResult(True)
        if not self.redis:
            logger.warning("Redis unavailable; allowing abuse check for %s", key)
            return AbuseCheckResult(True)

        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, window_seconds)
            ttl = await self.redis.ttl(key)
        except Exception as exc:
            logger.warning("Redis abuse check failed for %s: %s", key, exc)
            return AbuseCheckResult(True)

        if count > max_count:
            retry_after = ttl if ttl and ttl > 0 else window_seconds
            return AbuseCheckResult(
                allowed=False,
                message="Too many requests. Please try again later.",
                retry_after_seconds=retry_after,
            )
        return AbuseCheckResult(True)

    async def check_registration_ip(self, ip_address: str) -> AbuseCheckResult:
        return await self._check_limit(
            f"abuse:register:{ip_address}",
            settings.ABUSE_REGISTRATION_IP_DAILY_LIMIT,
            24 * 60 * 60,
        )

    async def check_login_ip(self, ip_address: str) -> AbuseCheckResult:
        return await self._check_limit(
            f"abuse:login:{ip_address}",
            settings.ABUSE_LOGIN_IP_HOURLY_LIMIT,
            60 * 60,
        )

    # ── Per-account lockout ──────────────────────────────────────────────
    # The IP limits above don't stop a distributed / credential-stuffing
    # attack that rotates IPs against ONE account. These three methods track
    # consecutive failures per email and lock that account for a fixed window
    # once the threshold is crossed. The counter resets on a correct password,
    # and the lock auto-expires (no extension during lockout) so a real user
    # is never permanently locked out and an attacker can't weaponize the lock
    # for indefinite DoS.
    @staticmethod
    def _account_key(email: str) -> str:
        return f"abuse:login_fail:{(email or '').strip().lower()}"

    async def check_login_account(self, email: str) -> AbuseCheckResult:
        max_failures = settings.ABUSE_LOGIN_ACCOUNT_MAX_FAILURES
        if max_failures <= 0 or not self.redis or not email:
            return AbuseCheckResult(True)
        try:
            raw = await self.redis.get(self._account_key(email))
            count = int(raw) if raw is not None else 0
            if count >= max_failures:
                ttl = await self.redis.ttl(self._account_key(email))
                retry_after = ttl if ttl and ttl > 0 else settings.ABUSE_LOGIN_ACCOUNT_LOCKOUT_SECONDS
                return AbuseCheckResult(
                    allowed=False,
                    message=(
                        "Too many failed login attempts for this account. "
                        "Please try again later or reset your password."
                    ),
                    retry_after_seconds=retry_after,
                )
        except Exception as exc:
            logger.warning("Redis account lockout check failed for %s: %s", email, exc)
        return AbuseCheckResult(True)

    async def record_login_failure(self, email: str) -> None:
        if settings.ABUSE_LOGIN_ACCOUNT_MAX_FAILURES <= 0 or not self.redis or not email:
            return
        key = self._account_key(email)
        try:
            count = await self.redis.incr(key)
            # Set the lockout window only on the first failure; do NOT extend on
            # later failures so the lock can't be held open indefinitely.
            if count == 1:
                await self.redis.expire(key, settings.ABUSE_LOGIN_ACCOUNT_LOCKOUT_SECONDS)
        except Exception as exc:
            logger.warning("Redis account failure record failed for %s: %s", email, exc)

    async def reset_login_failures(self, email: str) -> None:
        if not self.redis or not email:
            return
        try:
            await self.redis.delete(self._account_key(email))
        except Exception as exc:
            logger.warning("Redis account failure reset failed for %s: %s", email, exc)

    async def check_generation_user(self, user_id: str) -> AbuseCheckResult:
        return await self._check_limit(
            f"abuse:generation:{user_id}",
            settings.ABUSE_GENERATION_USER_PER_MINUTE_LIMIT,
            60,
        )

    async def verify_recaptcha_token(self, token: Optional[str], ip_address: Optional[str] = None) -> AbuseCheckResult:
        if not settings.RECAPTCHA_REQUIRED:
            return AbuseCheckResult(True)
        if not settings.RECAPTCHA_SECRET_KEY:
            logger.error("RECAPTCHA_REQUIRED=true but RECAPTCHA_SECRET_KEY is not configured")
            return AbuseCheckResult(False, "reCAPTCHA is not configured. Please contact support.")
        if not token:
            return AbuseCheckResult(False, "Please complete reCAPTCHA and try again.")

        payload = {
            "secret": settings.RECAPTCHA_SECRET_KEY,
            "response": token,
        }
        if ip_address and ip_address != "unknown":
            payload["remoteip"] = ip_address

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post("https://www.google.com/recaptcha/api/siteverify", data=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("reCAPTCHA verification failed: %s", exc)
            return AbuseCheckResult(False, "reCAPTCHA verification failed. Please try again.")

        if data.get("success"):
            return AbuseCheckResult(True)

        logger.warning("reCAPTCHA rejected token: %s", data.get("error-codes"))
        return AbuseCheckResult(False, "reCAPTCHA verification failed. Please try again.")
