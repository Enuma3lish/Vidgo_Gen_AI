"""
Redis-based rate limiting service for anti-abuse protection.

Protects against:
- Rapid registration from same IP (max 3/hour)
- Rapid generation requests (max 10/minute per user)
- Email enumeration attacks
"""
import logging
from typing import Optional
import redis.asyncio as aioredis

from fastapi import HTTPException

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis-based rate limiter."""

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def check_registration_rate(self, ip: str, email: str) -> None:
        """
        Check if registration is rate-limited.

        Limits:
        - Max 3 registrations per IP per hour
        - Max 5 attempts per email per day

        Raises HTTPException(429) if rate limited.
        """
        # Check IP rate
        ip_key = f"ratelimit:register:ip:{ip}"
        ip_count = await self.redis.incr(ip_key)
        if ip_count == 1:
            await self.redis.expire(ip_key, 3600)  # 1 hour window
        if ip_count > 3:
            logger.warning(f"Registration rate limit: IP {ip} exceeded 3/hour")
            raise HTTPException(
                status_code=429,
                detail="Too many registration attempts from this IP. Please try again later."
            )

        # Check email rate
        email_key = f"ratelimit:register:email:{email}"
        email_count = await self.redis.incr(email_key)
        if email_count == 1:
            await self.redis.expire(email_key, 86400)  # 24 hour window
        if email_count > 5:
            logger.warning(f"Registration rate limit: email {email} exceeded 5/day")
            raise HTTPException(
                status_code=429,
                detail="Too many registration attempts with this email. Please try again later."
            )

    async def check_generation_rate(self, user_id: str) -> None:
        """
        Check if generation is rate-limited.

        Limit: Max 10 generations per minute per user.

        Raises HTTPException(429) if rate limited.
        """
        key = f"ratelimit:generate:user:{user_id}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 60)  # 1 minute window
        if count > 10:
            logger.warning(f"Generation rate limit: user {user_id} exceeded 10/minute")
            raise HTTPException(
                status_code=429,
                detail="Too many generation requests. Please wait a moment."
            )

    async def check_login_rate(self, ip: str) -> None:
        """
        Check if login attempts are rate-limited.

        Limit: Max 10 login attempts per IP per 15 minutes.
        """
        key = f"ratelimit:login:ip:{ip}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 900)  # 15 minute window
        if count > 10:
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts. Please try again in 15 minutes."
            )


def get_rate_limiter(redis: aioredis.Redis) -> RateLimiter:
    """Factory function for rate limiter."""
    return RateLimiter(redis)
