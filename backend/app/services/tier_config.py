"""
Tier Configuration - Defines plan-based limits and credit costs.

This module provides:
1. FREE_TIER / BASIC_TIER / PAID_TIER configs for provider_router overrides
2. get_credit_cost() - Dynamic credit cost lookup by tool + user plan
3. get_user_tier() - Determine user's tier string from their plan

Pricing Reference (VidGo 2.2 Credit Spec — 2026-06 margin pass).
At the cheapest pack rate (heavy_pack: 850 cr / NT$999 ≈ $0.0388/credit)
the floor revenue per credit is $0.039. The values below were chosen so
each tool's "default" credit_cost covers its CHEAPEST viable upstream at
that floor revenue, and "premium" (wan_pro / gemini_pro / veo) covers
the flagship upstream + ≥30% margin.

Real upstream costs that drive the table (PiAPI / A2E / Vertex 2026-Q2):
  Standard image (Flux schnell, Z-Image, Seedream-Lite):  $0.003-0.025
  Premium image (Nano Banana Pro, MJ, Flux Kontext):      $0.04-0.10
  Standard 5s video (Hailuo Fast, Seedance Fast):         $0.10-0.15
  Mid 5s video (Hunyuan, Wan 2.6, Kling 2.6):             $0.20-0.30
  Premium 5s video (Kling 2.1-master, Kling 3 Omni):      $0.50-0.70
  Veo 3.1 Fast 5s:                                        $0.50
  Try-on (Kling Try-On):                                  $0.50-1.00
  Avatar (A2E full pipeline, Kling Avatar):               $1.00-3.00
  Lip-sync / dubbing:                                     $0.50-2.00
  Background removal / image upscale:                     $0.02-0.20
  Video upscale / video bg-remove:                        $0.10-0.50

Spec lifecycle:
  v2.0 (2026-05-12): undercharged ~10x — every paid call lost margin.
  v2.1 (2026-05-22): repriced DB rows for image / video / pro-video /
                     upscale; missed tools.py service_type mismatches.
  v2.2 (2026-06-03): closed mismatches, raised avatar/try-on/lip-sync
                     fallbacks, rerated heavy_pack to stop arbitrage.
                     See docs/service-cost.md for the full audit.

When PiAPI / vendor costs shift, update this file AND seed an alembic
migration that mirrors the change into service_pricing. Keep the two
sources of truth aligned — the deduction firewall prefers DB values, but
the code fallback is the floor when a DB row is missing.
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
    # 2026-06 margin pass: every tool's "default" must cover the cheapest
    # viable upstream at the cheapest-pack rate ($0.033/credit). "premium"
    # (wan_pro / gemini_pro / veo) covers the flagship upstream + margin.
    # See docs/service-cost.md for the spreadsheet that drives these values.
    "text_to_image":        {"default": 1,  "midjourney": 5, "wan_pro": 5,  "gemini_pro": 5},
    "background_removal":   {"default": 3},
    "bg_removal":           {"default": 3},
    "product_scene":        {"default": 10, "wan_pro": 15},
    "product_scene_gen":    {"default": 10, "wan_pro": 15},
    "pattern_gen":          {"default": 2,  "wan_pro": 5},
    "pattern_generate":     {"default": 2,  "wan_pro": 5},
    "room_redesign":        {"default": 5,  "wan_pro": 10},
    "i2i":                  {"default": 2,  "wan_pro": 5,  "gemini_pro": 5},
    "image_transform":      {"default": 2,  "wan_pro": 5,  "gemini_pro": 5},
    "style_transfer":       {"default": 2,  "wan_pro": 5},
    "upscale":              {"default": 15},
    "image_upscale":        {"default": 15},
    "video_upscale":        {"default": 50},
    "image_translator":     {"default": 2,  "wan_pro": 5,  "gemini_pro": 5},
    "image_translation":    {"default": 2,  "wan_pro": 5,  "gemini_pro": 5},

    # Video: cheap-upstream default (Hailuo/Seedance fast ~$0.10),
    # premium covers Kling 2.1-master / Veo 3.1 (~$0.50-0.70).
    "image_to_video":       {"default": 20, "wan_pro": 60, "veo": 200},
    "text_to_video":        {"default": 20, "wan_pro": 60, "veo": 200},
    "short_video":          {"default": 20, "wan_pro": 60, "veo": 200},
    "ai_try_on":            {"default": 30, "wan_pro": 60, "gemini_pro": 60},
    "try_on":               {"default": 30, "wan_pro": 60, "gemini_pro": 60},
    "virtual_try_on":       {"default": 30, "wan_pro": 60, "gemini_pro": 60},
    "interior_design":      {"default": 2,  "wan_pro": 5},
    "effect":               {"default": 1,  "wan_pro": 5},
    "claymation":           {"default": 10, "wan_pro": 50},  # 8→10 image, 50 video

    # Avatar / lip-sync upstream is $1-3 per call — must charge accordingly.
    "ai_avatar":            {"default": 80, "gemini_pro": 80},
    "avatar":               {"default": 80, "gemini_pro": 80},
    "lip_sync":             {"default": 50, "gemini_pro": 50},
    "video_dubbing":        {"default": 60, "gemini_pro": 60},

    # Video extend / repair: ~$0.30-1.00 upstream.
    "video_extend":         {"default": 30},
    "video_transform":      {"default": 30},
    "video_background_remove": {"default": 50},

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

# Allowed model types per plan tier.
# free/basic CANNOT select flagship variants (wan_pro / gemini_pro / veo)
# because those upstreams cost $0.40-$1.40 per call and the cheapest pack
# only yields $0.033/credit. Pro and above unlock the premium tiers.
TIER_ALLOWED_MODELS = {
    "free":  ["default"],
    "basic": ["default"],
    "pro":   ["default", "wan_pro", "gemini_pro", "midjourney", "veo"],
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
