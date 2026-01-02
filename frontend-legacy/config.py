"""
Configuration for Streamlit Frontend
VidGo - AI Video Generation Platform
"""
import os
from decouple import config

# API URLs
BACKEND_URL = config('BACKEND_URL', default='http://localhost:8000')
PAYMENT_SERVICE_URL = config('PAYMENT_SERVICE_URL', default='http://localhost:8001')

# API Endpoints - Authentication
API_AUTH_REGISTER = f"{BACKEND_URL}/api/v1/auth/register"
API_AUTH_LOGIN = f"{BACKEND_URL}/api/v1/auth/login"
API_AUTH_LOGOUT = f"{BACKEND_URL}/api/v1/auth/logout"
API_AUTH_REFRESH = f"{BACKEND_URL}/api/v1/auth/refresh"
API_AUTH_VERIFY_EMAIL = f"{BACKEND_URL}/api/v1/auth/verify-email"
API_AUTH_RESEND_VERIFICATION = f"{BACKEND_URL}/api/v1/auth/resend-verification"
API_AUTH_FORGOT_PASSWORD = f"{BACKEND_URL}/api/v1/auth/forgot-password"
API_AUTH_RESET_PASSWORD = f"{BACKEND_URL}/api/v1/auth/reset-password"

# API Endpoints - User
API_USERS_ME = f"{BACKEND_URL}/api/v1/auth/me"
API_CHANGE_PASSWORD = f"{BACKEND_URL}/api/v1/auth/me/change-password"

# API Endpoints - Plans
API_PLANS = f"{BACKEND_URL}/api/v1/plans"
API_PLANS_CURRENT = f"{BACKEND_URL}/api/v1/plans/current"
API_PLANS_WITH_SUBSCRIPTION = f"{BACKEND_URL}/api/v1/plans/with-subscription"

# API Endpoints - Billing (legacy)
API_SUBSCRIPTIONS = f"{BACKEND_URL}/api/subscriptions/"
API_ORDERS = f"{BACKEND_URL}/api/orders/"
API_INVOICES = f"{BACKEND_URL}/api/invoices/"

# API Endpoints - Demo (Smart Demo Engine)
API_DEMO_SEARCH = f"{BACKEND_URL}/api/v1/demo/search"
API_DEMO_RANDOM = f"{BACKEND_URL}/api/v1/demo/random"
API_DEMO_ANALYZE = f"{BACKEND_URL}/api/v1/demo/analyze"
API_DEMO_STYLES = f"{BACKEND_URL}/api/v1/demo/styles"
API_DEMO_CATEGORIES = f"{BACKEND_URL}/api/v1/demo/categories"
API_DEMO_MODERATE = f"{BACKEND_URL}/api/v1/demo/moderate"
API_DEMO_BLOCK_CACHE_STATS = f"{BACKEND_URL}/api/v1/demo/block-cache/stats"
API_DEMO_BLOCK_CACHE_CHECK = f"{BACKEND_URL}/api/v1/demo/block-cache/check"

# API Endpoints - Payment
API_PAYMENT_CREATE = f"{PAYMENT_SERVICE_URL}/payment/ecpay/create/"
API_PAYMENT_INVOICE = f"{PAYMENT_SERVICE_URL}/payment/invoice/"

# Session keys
SESSION_USER = 'user'
SESSION_ACCESS_TOKEN = 'access_token'
SESSION_REFRESH_TOKEN = 'refresh_token'

# Page config
PAGE_TITLE = "VidGo - AI Video Generation"
PAGE_ICON = "🎬"
LAYOUT = "wide"

# Demo page config
DEMO_FEATURES = [
    {
        "id": "clothing",
        "name": "AI Clothing Transform",
        "name_zh": "AI 換裝特效",
        "description": "Transform clothing styles with AI magic",
        "icon": "👗"
    },
    {
        "id": "goenhance",
        "name": "Special Effects",
        "name_zh": "特殊特效",
        "description": "Apply stunning video style transformations",
        "icon": "✨"
    }
]

# Supported languages for demo
SUPPORTED_LANGUAGES = {
    "en": "English",
    "zh-TW": "繁體中文",
    "ja": "日本語",
    "ko": "한국어",
    "es": "Español"
}
