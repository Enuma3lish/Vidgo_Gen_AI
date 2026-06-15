"""Helpers for restricted internal testing subscription plans."""

from typing import Any, Optional


TEST_PRO_PLAN_NAME = "test_pro_usd_1"
TEST_PRO_PLAN_SLUG = "test_pro_usd_1"
TEST_PRO_PLAN_DISPLAY_NAME = "Pro Test $1"
TEST_PRO_PLAN_CREDITS = 100
TEST_PRO_PLAN_PRICE_USD = 1
TEST_PRO_PLAN_PRICE_TWD = 32
TEST_PRO_PLAN_ALLOWED_EMAILS = {"qaz0978005418@gmail.com"}

TEST_PRO_PLAN_DEFAULTS = {
    "name": TEST_PRO_PLAN_NAME,
    "display_name": TEST_PRO_PLAN_DISPLAY_NAME,
    "slug": TEST_PRO_PLAN_SLUG,
    "plan_type": "pro",
    "price_monthly": float(TEST_PRO_PLAN_PRICE_USD),
    "price_yearly": float(TEST_PRO_PLAN_PRICE_USD * 12),
    "price_twd": TEST_PRO_PLAN_PRICE_TWD,
    "price_usd": TEST_PRO_PLAN_PRICE_USD,
    "currency": "USD",
    "monthly_credits": TEST_PRO_PLAN_CREDITS,
    "weekly_credits": TEST_PRO_PLAN_CREDITS,
    "credits_per_month": TEST_PRO_PLAN_CREDITS,
    "allowed_models": ["default"],
    "max_resolution": "1080p",
    "max_video_length": 0,
    "max_concurrent_generations": 1,
    "has_watermark": False,
    "watermark": False,
    "priority_queue": True,
    "api_access": True,
    "can_use_effects": True,
    "social_media_batch_posting": True,
    "enterprise_features": True,
    "feature_video_gen": False,
    "feature_batch_processing": True,
    "feature_custom_styles": True,
    "feature_clothing_transform": True,
    "feature_goenhance": True,
    "description": "Restricted internal Pro test plan with all tools enabled",
    "is_active": False,
}


def normalize_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()


def can_access_test_pro_plan(email: Optional[str]) -> bool:
    return normalize_email(email) in TEST_PRO_PLAN_ALLOWED_EMAILS


def is_test_pro_plan(plan: Any) -> bool:
    name = getattr(plan, "name", None)
    slug = getattr(plan, "slug", None)
    if isinstance(plan, str):
        name = plan
        slug = plan
    return name == TEST_PRO_PLAN_NAME or slug == TEST_PRO_PLAN_SLUG