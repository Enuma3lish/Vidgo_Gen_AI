from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any, Tuple
from jose import jwt
from passlib.context import CryptContext
import secrets
import hashlib
import base64
from app.core.config import get_settings

settings = get_settings()

# Use bcrypt with SHA256 pre-hashing to handle passwords > 72 bytes
# This is more secure than truncation for long passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _prehash_password(password: str) -> str:
    """
    Pre-hash password with SHA256 before bcrypt.
    This handles bcrypt's 72-byte limit securely.
    """
    # SHA256 hash the password and base64 encode it
    # This produces a consistent 44-character string
    sha256_hash = hashlib.sha256(password.encode('utf-8')).digest()
    return base64.b64encode(sha256_hash).decode('ascii')


def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create an access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access"
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a refresh token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh"
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_token_pair(subject: Union[str, Any]) -> Tuple[str, str]:
    """Create both access and refresh tokens."""
    access_token = create_access_token(subject)
    refresh_token = create_refresh_token(subject)
    return access_token, refresh_token


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except jwt.JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    # Pre-hash with SHA256 to handle bcrypt's 72-byte limit
    prehashed = _prehash_password(plain_password)
    return pwd_context.verify(prehashed, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    # Pre-hash with SHA256 to handle bcrypt's 72-byte limit
    prehashed = _prehash_password(password)
    return pwd_context.hash(prehashed)


def generate_verification_token() -> str:
    """Generate a secure random token for email verification."""
    return secrets.token_urlsafe(32)


def generate_password_reset_token() -> str:
    """Generate a secure random token for password reset."""
    return secrets.token_urlsafe(32)
