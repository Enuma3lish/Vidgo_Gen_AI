"""
Authentication API endpoints with email verification support.
"""
from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, EmailStr

from app.api import deps
from app.core import security
from app.core.config import get_settings
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    User as UserSchema,
    UserWithDetails,
    LoginResponse,
    TokenPair,
    RefreshTokenRequest,
    EmailVerificationRequest,
    ResendVerificationRequest,
    MessageResponse,
    PasswordChange,
    PasswordReset,
)
from app.services.email_service import email_service
from app.services.email_verify import EmailVerificationService
import redis.asyncio as redis

settings = get_settings()
router = APIRouter()


# Redis client for verification service
async def get_redis_client():
    """Get Redis client for verification service."""
    try:
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return client
    except Exception:
        return None


# ============== Login / Logout ==============

class LoginRequest(BaseModel):
    """Login request body."""
    email: EmailStr
    password: str


@router.post("/login", response_model=LoginResponse)
async def login(
    db: AsyncSession = Depends(deps.get_db),
    login_data: LoginRequest = Body(...)
) -> Any:
    """
    Login with email and password.
    Returns user info and token pair (access + refresh).
    """
    # Find user by email
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalars().first()

    # Verify credentials
    if not user or not security.verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Check if email is verified
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in. Check your inbox for the verification link."
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact support."
        )

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    # Generate token pair
    access_token, refresh_token = security.create_token_pair(str(user.id))

    return LoginResponse(
        user=UserSchema.model_validate(user),
        tokens=TokenPair(access=access_token, refresh=refresh_token)
    )


@router.post("/login/form", response_model=LoginResponse)
async def login_form(
    db: AsyncSession = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible login (form data).
    Username field accepts email.
    """
    login_request = LoginRequest(email=form_data.username, password=form_data.password)
    return await login(db=db, login_data=login_request)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Logout current user.
    In a stateless JWT setup, client should discard tokens.
    For added security, implement token blacklisting with Redis.
    """
    # TODO: Implement token blacklisting with Redis for enhanced security
    return MessageResponse(message="Successfully logged out")


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(
    db: AsyncSession = Depends(deps.get_db),
    token_data: RefreshTokenRequest = Body(...)
) -> Any:
    """
    Refresh access token using refresh token.
    """
    # Decode and validate refresh token
    payload = security.decode_token(token_data.refresh)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Check token type
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )

    # Get user
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Generate new token pair
    access_token, new_refresh_token = security.create_token_pair(str(user.id))

    return TokenPair(access=access_token, refresh=new_refresh_token)


# ============== Registration ==============

@router.post("/register", response_model=MessageResponse)
async def register(
    db: AsyncSession = Depends(deps.get_db),
    user_in: UserCreate = Body(...)
) -> Any:
    """
    Register a new user.
    Sends verification email - user must verify before logging in.
    """
    # Check password confirmation if provided
    if user_in.password_confirm and user_in.password != user_in.password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_in.email))
    existing_user = result.scalars().first()

    if existing_user:
        if existing_user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists"
            )
        else:
            # Resend verification email for unverified account
            verification_token = security.generate_verification_token()
            existing_user.email_verification_token = verification_token
            existing_user.email_verification_sent_at = datetime.now(timezone.utc)
            await db.commit()

            await email_service.send_verification_email(
                to_email=existing_user.email,
                token=verification_token,
                username=existing_user.username
            )

            return MessageResponse(
                message="A verification email has been sent. Please check your inbox."
            )

    # Generate verification token
    verification_token = security.generate_verification_token()

    # Create new user
    user = User(
        email=user_in.email,
        username=user_in.username,
        full_name=user_in.full_name,
        hashed_password=security.get_password_hash(user_in.password),
        is_active=False,  # Will be activated after email verification
        email_verified=False,
        email_verification_token=verification_token,
        email_verification_sent_at=datetime.now(timezone.utc)
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Send verification email
    await email_service.send_verification_email(
        to_email=user.email,
        token=verification_token,
        username=user.username
    )

    return MessageResponse(
        message="Registration successful! Please check your email to verify your account."
    )


# ============== Email Verification ==============

@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    db: AsyncSession = Depends(deps.get_db),
    verification: EmailVerificationRequest = Body(...)
) -> Any:
    """
    Verify email address using token from email link.
    """
    # Find user with this verification token
    result = await db.execute(
        select(User).where(User.email_verification_token == verification.token)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token"
        )

    # Check if token is expired
    if user.email_verification_sent_at:
        expiry_time = user.email_verification_sent_at + timedelta(
            hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS
        )
        if datetime.now(timezone.utc) > expiry_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has expired. Please request a new one."
            )

    # Verify the user
    user.email_verified = True
    user.is_active = True
    user.email_verification_token = None
    user.email_verification_sent_at = None

    await db.commit()

    # Send welcome email
    await email_service.send_welcome_email(
        to_email=user.email,
        username=user.username
    )

    return MessageResponse(message="Email verified successfully! You can now log in.")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    db: AsyncSession = Depends(deps.get_db),
    request: ResendVerificationRequest = Body(...)
) -> Any:
    """
    Resend verification email.
    """
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalars().first()

    if not user:
        # Don't reveal if email exists
        return MessageResponse(
            message="If an account with this email exists, a verification email will be sent."
        )

    if user.email_verified:
        return MessageResponse(message="This email is already verified. You can log in.")

    # Rate limiting: check if email was sent recently (e.g., within 2 minutes)
    if user.email_verification_sent_at:
        time_since_last = datetime.now(timezone.utc) - user.email_verification_sent_at
        if time_since_last < timedelta(minutes=2):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait before requesting another verification email."
            )

    # Generate new token
    verification_token = security.generate_verification_token()
    user.email_verification_token = verification_token
    user.email_verification_sent_at = datetime.now(timezone.utc)

    await db.commit()

    await email_service.send_verification_email(
        to_email=user.email,
        token=verification_token,
        username=user.username
    )

    return MessageResponse(
        message="If an account with this email exists, a verification email will be sent."
    )


# ============== Password Reset ==============

class PasswordResetRequest(BaseModel):
    email: EmailStr


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    db: AsyncSession = Depends(deps.get_db),
    request: PasswordResetRequest = Body(...)
) -> Any:
    """
    Request password reset email.
    """
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalars().first()

    if not user:
        # Don't reveal if email exists
        return MessageResponse(
            message="If an account with this email exists, a password reset link will be sent."
        )

    # Rate limiting
    if user.password_reset_sent_at:
        time_since_last = datetime.now(timezone.utc) - user.password_reset_sent_at
        if time_since_last < timedelta(minutes=2):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait before requesting another password reset."
            )

    # Generate reset token
    reset_token = security.generate_password_reset_token()
    user.password_reset_token = reset_token
    user.password_reset_sent_at = datetime.now(timezone.utc)

    await db.commit()

    await email_service.send_password_reset_email(
        to_email=user.email,
        token=reset_token,
        username=user.username
    )

    return MessageResponse(
        message="If an account with this email exists, a password reset link will be sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    db: AsyncSession = Depends(deps.get_db),
    reset_data: PasswordReset = Body(...)
) -> Any:
    """
    Reset password using token from email.
    """
    result = await db.execute(
        select(User).where(User.password_reset_token == reset_data.token)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token"
        )

    # Check if token is expired (1 hour)
    if user.password_reset_sent_at:
        expiry_time = user.password_reset_sent_at + timedelta(hours=1)
        if datetime.now(timezone.utc) > expiry_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired. Please request a new one."
            )

    # Update password
    user.hashed_password = security.get_password_hash(reset_data.new_password)
    user.password_reset_token = None
    user.password_reset_sent_at = None

    await db.commit()

    return MessageResponse(message="Password reset successfully! You can now log in.")


# ============== User Profile ==============

@router.get("/me", response_model=UserWithDetails)
async def get_current_user_profile(
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Get current user's profile.
    """
    return current_user


@router.put("/me", response_model=UserWithDetails)
async def update_current_user_profile(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    username: str = Body(None),
    full_name: str = Body(None)
) -> Any:
    """
    Update current user's profile.
    """
    if username is not None:
        current_user.username = username
    if full_name is not None:
        current_user.full_name = full_name

    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)

    return current_user


@router.post("/me/change-password", response_model=MessageResponse)
async def change_password(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    password_data: PasswordChange = Body(...)
) -> Any:
    """
    Change current user's password.
    """
    # Verify current password
    if not security.verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Update password
    current_user.hashed_password = security.get_password_hash(password_data.new_password)
    current_user.updated_at = datetime.now(timezone.utc)

    await db.commit()

    return MessageResponse(message="Password changed successfully")


# ============== 6-Digit Code Verification (New System) ==============

class VerifyCodeRequest(BaseModel):
    """Request body for 6-digit code verification."""
    email: EmailStr
    code: str


class ResendCodeRequest(BaseModel):
    """Request body for resending verification code."""
    email: EmailStr


@router.post("/verify-code", response_model=MessageResponse)
async def verify_email_code(
    db: AsyncSession = Depends(deps.get_db),
    request: VerifyCodeRequest = Body(...)
) -> Any:
    """
    Verify email using 6-digit code.

    This is the new verification system using 6-digit codes instead of links.
    - Code expires in 15 minutes
    - Maximum 3 attempts per code
    """
    redis_client = await get_redis_client()
    verify_service = EmailVerificationService(db, redis_client, email_service)

    success, message = await verify_service.verify_code(request.email, request.code)

    if redis_client:
        await redis_client.close()

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return MessageResponse(message=message)


@router.post("/resend-code", response_model=MessageResponse)
async def resend_verification_code(
    db: AsyncSession = Depends(deps.get_db),
    request: ResendCodeRequest = Body(...)
) -> Any:
    """
    Resend 6-digit verification code.

    Rate limited to 5 requests per hour.
    """
    redis_client = await get_redis_client()
    verify_service = EmailVerificationService(db, redis_client, email_service)

    success, message = await verify_service.resend_code(request.email)

    if redis_client:
        await redis_client.close()

    if not success:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS if "Too many" in message else status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return MessageResponse(message=message)
