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
