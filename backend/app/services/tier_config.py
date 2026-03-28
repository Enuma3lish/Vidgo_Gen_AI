"""
Tier Configuration - Defines plan-based limits and credit costs.

This module provides:
1. FREE_TIER / PAID_TIER configs for provider_router parameter overrides
2. get_credit_cost() - Dynamic credit cost lookup by tool + user plan
3. get_user_tier() - Determine user's tier string from their plan

Pricing Reference (from spec):
- 文生圖 (Flux) / 去背: 20 credits (default model, Basic+)
- 圖生影片 (Wan 5s) / AI 試穿: 250 credits (wan_pro, Pro+)
- AI 虛擬人物 / 唇形同步: 300 credits (gemini_pro, Pro+)
- 超高畫質影片 (Sora): 2,500 credits (premium+, future)
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
# Matches spec Section 三「AI 工具扣點對照表」
# PiAPI 漲價時只需改此表，前端月費不變。
# ─────────────────────────────────────────────────────────────────────────────

CREDIT_COSTS = {
    # Static generation — default model (Basic+)
    "text_to_image":        {"default": 20},
    "background_removal":   {"default": 20},
    "product_scene":        {"default": 20},
    "pattern_gen":          {"default": 20},
    "room_redesign":        {"default": 20},
    "i2i":                  {"default": 20},
    "style_transfer":       {"default": 20},
    "upscale":              {"default": 20},

    # Dynamic generation — wan_pro / gemini_pro (Pro+)
    "image_to_video":       {"default": 50,  "wan_pro": 250},
    "text_to_video":        {"default": 50,  "wan_pro": 250},
    "short_video":          {"default": 50,  "wan_pro": 250},
    "video_style_transfer": {"default": 50,  "wan_pro": 250},
    "ai_try_on":            {"default": 50,  "wan_pro": 250, "gemini_pro": 250},
    "interior_design":      {"default": 20,  "wan_pro": 250},
    "effect":               {"default": 20,  "wan_pro": 250},

    # Avatar / lip-sync — gemini_pro (Pro+)
    "ai_avatar":            {"gemini_pro": 300},
    "avatar":               {"default": 300, "gemini_pro": 300},
    "lip_sync":             {"gemini_pro": 300},

    # Premium — future expansion
    "ultra_hd_video":       {"sora": 2500},
}

# Map plan names → tier strings
PLAN_TIER_MAP = {
    "demo":       "free",
    "free":       "free",
    "basic":      "basic",
    "starter":    "basic",
    "pro":        "pro",
    "premium":    "pro",
    "enterprise": "pro",
}

# Allowed model types per plan tier
TIER_ALLOWED_MODELS = {
    "free":  ["default"],
    "basic": ["default"],
    "pro":   ["default", "wan_pro", "gemini_pro", "sora"],
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
        # Fallback: 20 credits for unknown tools
        return 20

    # If explicit model_type provided, use it
    if model_type and model_type in costs:
        return costs[model_type]

    # Determine user's tier and pick highest allowed model
    if user:
        tier = get_user_tier(user)
        allowed = TIER_ALLOWED_MODELS.get(tier, ["default"])

        # Pick the most expensive allowed model (user pays for their tier's capability)
        best_cost = costs.get("default", 20)
        for model in allowed:
            if model in costs:
                best_cost = max(best_cost, costs[model])
        return best_cost

    # No user context → return default cost
    return costs.get("default", list(costs.values())[0])
