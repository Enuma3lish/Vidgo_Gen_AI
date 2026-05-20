"""
Tier Configuration - Defines plan-based limits and credit costs.

This module provides:
1. FREE_TIER / PAID_TIER configs for provider_router parameter overrides
2. get_credit_cost() - Dynamic credit cost lookup by tool + user plan
3. get_user_tier() - Determine user's tier string from their plan

Pricing Reference (VidGo 2.0 Credit Spec — 2026-05):
- 標準圖片 (SD/SDXL/Flux):              1  credit  (~$0.5  cost)
- 高畫質圖片 (MJ/DALL-E/Midjourney):    3  credits (~$1.5  cost, range 3-5)
- 標準影片 (5-10s, 5s/720p):            10 credits (~$5    cost)
- 專業影片 (Luma/Kling, 10s/4K):        30 credits (~$15   cost, range 30-50)
- 影片擴展/修補 (Extend):               15 credits (~$7.5  cost)
"""
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# TIER PARAMETER CONFIGS (used by provider_router._apply_tier_overrides)
# ─────────────────────────────────────────────────────────────────────────────

FREE_TIER = {
    "max_resolution": "720p",
    "max_duration": 5,
    "audio_enabled": False,
    "models": {
        "t2i": {"resolution": "512x512", "size": "512*512"},
        "i2i": {"resolution": "512x512", "size": "512*512"},
        "i2v": {"resolution": "720p", "duration": 3},
        "t2v": {"resolution": "720p", "duration": 3},
        "interior": {"resolution": "512x512", "size": "512*512"},
        "interior_3d": {},
        "avatar": {"resolution": "720p", "duration": 5},
        "bg_removal": {},
        "effect": {"resolution": "512x512", "size": "512*512"},
    },
}

# Basic plan (699 TWD, default model only)
BASIC_TIER = {
    "max_resolution": "720p",
    "max_duration": 5,
    "audio_enabled": True,
    "models": {
        "t2i": {"resolution": "1024x1024", "size": "1024*1024"},
        "i2i": {"resolution": "1024x1024", "size": "1024*1024"},
        "i2v": {"resolution": "720p", "duration": 5},
        "t2v": {"resolution": "720p", "duration": 5},
        "interior": {"resolution": "1024x1024", "size": "1024*1024"},
        "interior_3d": {},
        "avatar": {"resolution": "720p", "duration": 10},
        "bg_removal": {},
        "effect": {"resolution": "1024x1024", "size": "1024*1024"},
    },
}

# Pro / Premium / Enterprise
PAID_TIER = {
    "max_resolution": "1080p",
    "max_duration": 10,
    "audio_enabled": True,
    "models": {
        "t2i": {"resolution": "1024x1024", "size": "1024*1024"},
        "i2i": {"resolution": "1024x1024", "size": "1024*1024"},
        "i2v": {"resolution": "1080p", "duration": 10},
        "t2v": {"resolution": "1080p", "duration": 10},
        "interior": {"resolution": "1024x1024", "size": "1024*1024"},
        "interior_3d": {},
        "avatar": {"resolution": "1080p", "duration": 30},
        "bg_removal": {},
        "effect": {"resolution": "1024x1024", "size": "1024*1024"},
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# CREDIT COST TABLE (tool_type → model_type → credits)
#
# VidGo 2.0 spec (2026-05): point-based pricing aligned with internal cost.
# Standard image=1, High-quality image=3, Standard video=10, Pro video=30,
# Video extend/repair=15. PiAPI cost shifts → adjust this table only.
# ─────────────────────────────────────────────────────────────────────────────

CREDIT_COSTS = {
    # Standard image (SD/SDXL/Flux) = 1, High-quality (MJ/DALL-E) = 3
    "text_to_image":        {"default": 1,  "midjourney": 3, "wan_pro": 3},
    "background_removal":   {"default": 1},
    "product_scene":        {"default": 1,  "wan_pro": 3},
    "pattern_gen":          {"default": 1,  "wan_pro": 3},
    "pattern_generate":     {"default": 1,  "wan_pro": 3},
    "room_redesign":        {"default": 1,  "wan_pro": 3},
    "i2i":                  {"default": 1,  "wan_pro": 3},
    "style_transfer":       {"default": 1,  "wan_pro": 3},
    "upscale":              {"default": 1},
    "image_translator":     {"default": 1,  "wan_pro": 3},

    # Standard video (5-10s) = 10, Pro video (Luma/Kling 10s/4K) = 30
    "image_to_video":       {"default": 10, "wan_pro": 30},
    "text_to_video":        {"default": 10, "wan_pro": 30},
    "short_video":          {"default": 10, "wan_pro": 30},
    "video_style_transfer": {"default": 10, "wan_pro": 30},
    "ai_try_on":            {"default": 10, "wan_pro": 30, "gemini_pro": 30},
    "try_on":               {"default": 10, "wan_pro": 30, "gemini_pro": 30},
    "interior_design":      {"default": 1,  "wan_pro": 3},
    "effect":               {"default": 1,  "wan_pro": 3},

    # Avatar / lip-sync — pro video tier
    "ai_avatar":            {"default": 30, "gemini_pro": 30},
    "avatar":               {"default": 30, "gemini_pro": 30},
    "lip_sync":             {"default": 30, "gemini_pro": 30},
    "video_dubbing":        {"default": 30, "gemini_pro": 30},

    # Video extend / repair = 15
    "video_extend":         {"default": 15},
    "video_transform":      {"default": 15},

    # Premium — future expansion (e.g. Veo 3.1 / Kling Omni-tier upgrades).
}

# Map plan names → tier strings
PLAN_TIER_MAP = {
    "demo":       "free",
    "free":       "free",
    "basic":      "basic",
    "starter":    "basic",
    "pro":        "pro",
    "test_pro_usd_1": "pro",
    "premium":    "pro",
    "enterprise": "pro",
}

# Allowed model types per plan tier
TIER_ALLOWED_MODELS = {
    "free":  ["default"],
    "basic": ["default"],
    "pro":   ["default", "wan_pro", "gemini_pro", "veo"],
}


def get_tier_config(tier: str) -> dict:
    """Get the parameter config for a tier."""
    if tier == "free":
        return FREE_TIER
    elif tier == "basic":
        return BASIC_TIER
    else:
        return PAID_TIER


def get_user_tier(user) -> str:
    """
    Determine user's tier string from their model/plan.

    Args:
        user: User ORM object with current_plan_id or plan relationship

    Returns:
        Tier string: "free", "basic", or "pro"
    """
    if not user:
        return "free"

    # Check if user has a plan loaded (via relationship or cached attribute)
    plan_name = None

    if hasattr(user, "_plan_name"):
        plan_name = user._plan_name
    elif hasattr(user, "plan") and user.plan:
        plan_name = user.plan.name
    elif hasattr(user, "current_plan_id") and user.current_plan_id:
        # Plan is set but not loaded — assume at least basic
        return "basic"
    else:
        return "free"

    return PLAN_TIER_MAP.get(plan_name, "free")


def get_credit_cost(tool_type: str, user=None, model_type: Optional[str] = None) -> int:
    """
    Get the credit cost for a tool, considering model type.

    Args:
        tool_type: Tool identifier (e.g., "text_to_image", "avatar")
        user: Optional User object (used to determine allowed model)
        model_type: Optional explicit model type override

    Returns:
        Credit cost (integer)
    """
    costs = CREDIT_COSTS.get(tool_type)
    if not costs:
        # Fallback for unknown tools (VidGo 2.0: standard-video tier)
        return 10

    # If explicit model_type provided, use it
    if model_type and model_type in costs:
        return costs[model_type]

    # Determine user's tier and pick highest allowed model
    if user:
        tier = get_user_tier(user)
        allowed = TIER_ALLOWED_MODELS.get(tier, ["default"])

        # Pick the most expensive allowed model (user pays for their tier's capability)
        best_cost = costs.get("default", 10)
        for model in allowed:
            if model in costs:
                best_cost = max(best_cost, costs[model])
        return best_cost

    # No user context → return default cost
    return costs.get("default", list(costs.values())[0])
