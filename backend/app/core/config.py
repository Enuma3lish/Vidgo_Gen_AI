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

    # AI Services
    GEMINI_API_KEY: str = ""
    LEONARDO_API_KEY: str = ""
    RUNWAY_API_KEY: str = ""
    POLLO_API_KEY: str = ""
    GOENHANCE_API_KEY: str = ""

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

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings():
    return Settings()
