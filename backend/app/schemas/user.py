from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    password_confirm: Optional[str] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class PasswordReset(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class UserInDBBase(UserBase):
    id: UUID
    is_active: bool = False
    email_verified: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class User(UserInDBBase):
    """User response schema (public info)"""
    pass


class UserWithDetails(UserInDBBase):
    """User with more details (for profile page)"""
    is_superuser: bool = False
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None


# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPair(BaseModel):
    access: str
    refresh: str


class LoginResponse(BaseModel):
    """Login response matching frontend expectations"""
    user: User
    tokens: TokenPair


class RefreshTokenRequest(BaseModel):
    refresh: str


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    type: Optional[str] = "access"  # "access" or "refresh"
    exp: Optional[int] = None


# Email Verification Schemas
class EmailVerificationRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class MessageResponse(BaseModel):
    message: str
    success: bool = True
