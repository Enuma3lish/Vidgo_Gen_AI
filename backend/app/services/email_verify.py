"""
Email Verification Service with 6-digit code.

Features:
- Generate 6-digit numeric codes
- Store in Redis with 15-min TTL
- Max 3 verification attempts per code
- Max 5 resend requests per hour
- Hash codes for security
"""
import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import Tuple, Optional
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.models.user import User
from app.models.verification import EmailVerification

settings = get_settings()


class EmailVerificationService:
    """Service for email verification with 6-digit codes."""

    CODE_LENGTH = 6
    CODE_EXPIRY_MINUTES = 15
    MAX_ATTEMPTS = 3
    MAX_RESEND_PER_HOUR = 5

    def __init__(self, db: AsyncSession, redis_client: Optional[redis.Redis] = None, email_service=None):
        self.db = db
        self.redis = redis_client
        self.email_service = email_service

    def _generate_code(self) -> str:
        """Generate 6-digit numeric code."""
        return ''.join([str(secrets.randbelow(10)) for _ in range(self.CODE_LENGTH)])

    def _hash_code(self, code: str) -> str:
        """Hash code for storage."""
        return hashlib.sha256(code.encode()).hexdigest()

    async def send_verification_code(self, email: str, user_id: str) -> Tuple[bool, str]:
        """
        Send verification code to email.

        Returns:
            Tuple of (success, message)
        """
        if not self.redis:
            # Fallback without Redis - generate code without rate limiting
            code = self._generate_code()
            if self.email_service:
                await self.email_service.send_verification_email(email, code)
            return True, "Verification code sent"

        # Check resend limit
        resend_key = f"email_resend_count:{email}"
        resend_count = await self.redis.get(resend_key)

        if resend_count and int(resend_count) >= self.MAX_RESEND_PER_HOUR:
            return False, "Too many resend requests. Please wait 1 hour."

        # Generate code
        code = self._generate_code()

        # Store in Redis
        verify_key = f"email_verify:{email}"
        verify_data = {
            "code_hash": self._hash_code(code),
            "attempts": 0,
            "user_id": str(user_id),
            "created_at": datetime.utcnow().isoformat()
        }
        await self.redis.setex(
            verify_key,
            self.CODE_EXPIRY_MINUTES * 60,
            json.dumps(verify_data)
        )

        # Increment resend counter
        await self.redis.incr(resend_key)
        await self.redis.expire(resend_key, 3600)  # 1 hour TTL

        # Store in database for audit
        verification = EmailVerification(
            user_id=user_id,
            email=email,
            code_hash=self._hash_code(code),
            expires_at=datetime.utcnow() + timedelta(minutes=self.CODE_EXPIRY_MINUTES)
        )
        self.db.add(verification)
        await self.db.commit()

        # Send email with 6-digit code
        if self.email_service:
            await self.email_service.send_verification_code_email(email, code)

        return True, "Verification code sent"

    async def verify_code(self, email: str, code: str) -> Tuple[bool, str]:
        """
        Verify the submitted code.

        Returns:
            Tuple of (success, message)
        """
        if not self.redis:
            return False, "Verification service unavailable"

        verify_key = f"email_verify:{email}"
        data = await self.redis.get(verify_key)

        if not data:
            return False, "Verification code expired. Please request a new one."

        verify_data = json.loads(data)

        # Check attempts
        if verify_data["attempts"] >= self.MAX_ATTEMPTS:
            await self.redis.delete(verify_key)
            return False, "Too many failed attempts. Please request a new code."

        # Verify code
        if self._hash_code(code) == verify_data["code_hash"]:
            # Success - delete Redis key
            await self.redis.delete(verify_key)

            # Activate user account
            user_id = verify_data.get("user_id")
            if user_id:
                result = await self.db.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    user.email_verified = True
                    user.is_active = True
                    await self.db.commit()

            # Update verification record in database
            result = await self.db.execute(
                select(EmailVerification).where(
                    EmailVerification.email == email,
                    EmailVerification.status == "pending"
                ).order_by(EmailVerification.created_at.desc())
            )
            verification = result.scalar_one_or_none()
            if verification:
                verification.status = "verified"
                verification.verified_at = datetime.utcnow()
                await self.db.commit()

            return True, "Email verified successfully"

        # Increment attempts
        verify_data["attempts"] += 1
        remaining = self.MAX_ATTEMPTS - verify_data["attempts"]

        # Update Redis with new attempts count
        ttl = await self.redis.ttl(verify_key)
        if ttl > 0:
            await self.redis.setex(
                verify_key,
                ttl,
                json.dumps(verify_data)
            )

        if remaining <= 0:
            await self.redis.delete(verify_key)
            return False, "Too many failed attempts. Please request a new code."

        return False, f"Invalid code. {remaining} attempts remaining."

    async def resend_code(self, email: str) -> Tuple[bool, str]:
        """
        Resend verification code.

        Returns:
            Tuple of (success, message)
        """
        # Find user by email
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            return False, "User not found"

        if user.email_verified:
            return False, "Email already verified"

        return await self.send_verification_code(email, str(user.id))

    async def is_email_verified(self, email: str) -> bool:
        """Check if email is verified."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        return user.email_verified if user else False
