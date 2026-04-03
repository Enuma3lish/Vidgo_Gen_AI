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
    CORS_ALLOW_ALL: bool = True  # Allow all origins (safe for GCP Cloud Run where URLs are dynamic)
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8501", "http://localhost:4173", "https://vidgo.co", "https://www.vidgo.co"]

    # AI Services - Provider Configuration (MCP-based)
    # Primary video: Pollo.ai MCP — I2V, T2V (50+ models)
    POLLO_API_KEY: str = ""

    # Supplement + backup: PiAPI MCP — T2I, I2I, Try-On, Interior, Avatar, TTS, Upscale, 3D
    PIAPI_KEY: str = ""

    # PiAPI MCP server path (built from piapi-mcp-server repo)
    PIAPI_MCP_PATH: str = "/app/mcp-servers/piapi-mcp-server/dist/index.js"

    # Backup for image tasks + Moderation + Material generation
    GEMINI_API_KEY: str = ""

    # GCS Storage (persist generated media beyond provider CDN expiry)
    GCS_BUCKET: str = ""  # e.g. "vidgo-media-vidgo-ai"

    # Legacy (deprecated — kept for fallback)
    WAN_API_KEY: str = ""
    RUNWAY_API_KEY: str = ""

    # Taiwanese TTS (台語/閩南語 TTS)
    # Option 1: Taigi TTS API (https://learn-language.tokyo/en/taiwanese-taigi-tts-api)
    TAIGI_TTS_API_KEY: str = ""
    # Option 2: Self-hosted tai5-uan5 (https://github.com/i3thuan5/tai5-uan5_gian5-gi2_hok8-bu7)
    TAI5UAN5_BASE_URL: str = ""

    # ECPay (Taiwan) - Shared credentials for payment & e-invoice
    ECPAY_ENV: str = "production"  # "sandbox" or "production"
    ECPAY_MERCHANT_ID: str = "3422044"
    ECPAY_HASH_KEY: str = ""
    ECPAY_HASH_IV: str = ""
    ECPAY_PAYMENT_URL: str = "https://payment.ecpay.com.tw/Cashier/AioCheckOut/V2"
    ECPAY_INVOICE_URL: str = "https://einvoice.ecpay.com.tw"  # Base URL, paths appended by client

    # Giveme E-Invoice (Taiwan 電子發票)
    GIVEME_ENABLED: bool = False
    GIVEME_BASE_URL: str = "https://www.giveme.com.tw/invoice.do"
    GIVEME_UNCODE: str = "96003146"       # Company 統一編號 (e.g. "96003146")
    GIVEME_IDNO: str = "qaz0978005418"         # API account (from Giveme 系統設定→員工設定)
    GIVEME_PASSWORD: str = "qaz129946858"     # API password

    # Payment - Paddle (International)
    PADDLE_API_KEY: str = ""
    PADDLE_PUBLIC_KEY: str = ""
    PADDLE_WEBHOOK_SECRET: str = ""
    PADDLE_ENV: str = "sandbox"  # "sandbox" or "production"
    # Map plan_name+billing_cycle to Paddle price IDs (JSON string)
    # Example: '{"starter_monthly":"pri_abc","starter_yearly":"pri_def"}'
    # When empty, subscription flow activates directly without Paddle checkout.
    PADDLE_PRICE_IDS: str = ""

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
    SHORT_VIDEO_LENGTH: int = 8  # Default short video length in seconds

    # Email Configuration (for email verification)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@vidgo.co"
    SMTP_FROM_NAME: str = "VidGo"
    SMTP_TLS: bool = True

    # Email Verification
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"  # Backend URL for ECPay callbacks (must be publicly accessible)

    # Social Media Integration
    # Facebook / Instagram (Meta Graph API)
    # Create app at: https://developers.facebook.com/
    FACEBOOK_APP_ID: str = ""           # Meta App ID
    FACEBOOK_APP_SECRET: str = ""       # Meta App Secret
    INSTAGRAM_APP_ID: str = ""          # Same as FACEBOOK_APP_ID if using same Meta app
    INSTAGRAM_APP_SECRET: str = ""      # Same as FACEBOOK_APP_SECRET if using same Meta app
    # TikTok Content Posting API
    # Create app at: https://developers.tiktok.com/
    TIKTOK_CLIENT_KEY: str = ""         # TikTok Client Key
    TIKTOK_CLIENT_SECRET: str = ""      # TikTok Client Secret
    # YouTube (Google OAuth 2.0 + YouTube Data API v3)
    # Create project at: https://console.cloud.google.com/
    YOUTUBE_CLIENT_ID: str = ""         # Google OAuth Client ID
    YOUTUBE_CLIENT_SECRET: str = ""     # Google OAuth Client Secret

    # Registration System
    REGISTRATION_BONUS_CREDITS: int = 40   # Credits awarded to new user upon registration
    REGISTRATION_BONUS_DAYS: int = 30      # Days until registration bonus credits expire

    # Referral System
    REFERRAL_BONUS_CREDITS: int = 50       # Credits awarded to referrer per successful referral
    REFERRAL_WELCOME_CREDITS: int = 20     # Credits awarded to new user who used a referral code

    # Upload settings (subscriber material upload)
    MAX_UPLOAD_SIZE_MB: int = 20           # Max file size for subscriber uploads
    UPLOAD_ALLOWED_TYPES: str = "image/jpeg,image/png,image/webp,image/gif"

    # Model credit multipliers (model_id → credit cost per generation)
    # Base cost is defined in ServicePricing; these are multipliers
    # Format: JSON string parsed at runtime
    MODEL_CREDIT_MULTIPLIERS: str = '{"default":1,"wan_pro":2,"gemini_pro":2}'

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # allow env vars used by scripts (SKIP_PREGENERATION, DEMO_VIDEO_*, etc.) without crashing


@lru_cache()
def get_settings():
    return Settings()


# Create settings instance for easy import
settings = get_settings()
