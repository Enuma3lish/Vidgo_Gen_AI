from pydantic_settings import BaseSettings
from typing import Optional, List
from functools import lru_cache


class Settings(BaseSettings):
    PROJECT_NAME: str = "VidGo Gen AI"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/vidgo"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "YOUR_SECRET_KEY_HERE_CHANGE_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8501"]

    # AI Services - Provider Configuration
    # Primary: PiAPI (Wan API access)
    PIAPI_KEY: str = ""  # PiAPI for Wan T2I, I2V, T2V, Interior

    # Backup: Pollo.ai (Advanced features + backup)
    POLLO_API_KEY: str = ""  # Pollo for keyframes, effects, multi-model

    # Specialized Providers
    A2E_API_KEY: str = ""  # A2E.ai for Avatar/Digital Human
    A2E_DEFAULT_ANCHOR_ID: str = ""  # A2E anchor ID (create at video.a2e.ai)
    GEMINI_API_KEY: str = ""  # Gemini for moderation + emergency backup

    # Legacy (deprecated)
    WAN_API_KEY: str = ""  # Deprecated - use PIAPI_API_KEY instead
    RUNWAY_API_KEY: str = ""  # Not used

    # Taiwanese TTS (台語/閩南語 TTS)
    # Option 1: Taigi TTS API (https://learn-language.tokyo/en/taiwanese-taigi-tts-api)
    TAIGI_TTS_API_KEY: str = ""
    # Option 2: Self-hosted tai5-uan5 (https://github.com/i3thuan5/tai5-uan5_gian5-gi2_hok8-bu7)
    TAI5UAN5_BASE_URL: str = ""

    # Payment - ECPay (Taiwan)
    ECPAY_MERCHANT_ID: str = ""
    ECPAY_HASH_KEY: str = ""
    ECPAY_HASH_IV: str = ""
    ECPAY_PAYMENT_URL: str = "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"

    # Payment - Paddle (International)
    PADDLE_API_KEY: str = ""
    PADDLE_PUBLIC_KEY: str = ""

    # Storage
    S3_BUCKET: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_ENDPOINT: str = ""

    # Watermark
    WATERMARK_TEXT: str = "VidGo Demo"
    WATERMARK_IMAGE_PATH: Optional[str] = None

    # Material Generation
    AUTO_GENERATE_MATERIALS: bool = True  # Auto-generate showcase materials on startup

    # Email Configuration (for email verification)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@vidgo.ai"
    SMTP_FROM_NAME: str = "VidGo"
    SMTP_TLS: bool = True

    # Email Verification
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24
    FRONTEND_URL: str = "http://localhost:8501"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings():
    return Settings()


# Create settings instance for easy import
settings = get_settings()
