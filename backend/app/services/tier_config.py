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
import math
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
    "text_to_image":        {"default": 2,  "premium": 3, "nano_banana": 8, "nano_banana_4k": 12},
    "background_removal":   {"default": 2},
    "bg_removal":           {"default": 2},
    "product_scene":        {"default": 10, "wan_pro": 15},
    "product_scene_gen":    {"default": 10, "wan_pro": 15},
    "pattern_gen":          {"default": 2,  "wan_pro": 5},
    "pattern_generate":     {"default": 2,  "wan_pro": 5},
    "room_redesign":        {"default": 5,  "wan_pro": 10},
    "i2i":                  {"default": 2,  "wan_pro": 5,  "gemini_pro": 5},
    "image_transform":      {"default": 2,  "wan_pro": 5,  "gemini_pro": 5},
    "style_transfer":       {"default": 2,  "wan_pro": 5},
    "upscale":              {"default": 3},
    "image_upscale":        {"default": 3},
    "video_upscale":        {"default": 50},
    "image_translator":     {"default": 2,  "wan_pro": 5,  "gemini_pro": 5},
    "image_translation":    {"default": 2,  "wan_pro": 5,  "gemini_pro": 5},

    # Video: cheap-upstream default (Hailuo/Seedance fast ~$0.10),
    # premium covers Kling 2.1-master / Veo 3.1 (~$0.50-0.70).
    # Video defaults are the legacy fallback only — the live charge comes from
    # VIDEO_CREDIT_COSTS via resolve_video_credits() (per model + resolution).
    "image_to_video":       {"default": 18, "wan_pro": 65, "veo": 80},
    "text_to_video":        {"default": 18, "wan_pro": 65, "veo": 80},
    "short_video":          {"default": 18, "wan_pro": 65, "veo": 80},
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


# ─────────────────────────────────────────────────────────────────────────────
# VidGo 3.0 PER-MODEL CREDIT TABLE — "扣點表 + 方案金額" spec (2026-06)
#
# Iron rule: credits = ceil( PiAPI_cost_USD / 0.04 * 2.5 ). Every task sells for
# ≥2.5× upstream cost at 1 credit = US$0.04. Video MUST charge per
# model + resolution + duration — never a single fixed value — so the deduction
# path resolves (model_id, resolution, tier) → (service_type, credits) via the
# tables below before charging. When upstream PiAPI costs move, update ONLY
# these tables AND the mirroring alembic migration (keep service_pricing aligned).
# ─────────────────────────────────────────────────────────────────────────────

CREDIT_USD_PRICE = 0.04   # 1 credit = US$0.04 (point-pack unit price; do NOT change)
MARGIN_MULTIPLIER = 2.5   # gross-margin multiple over upstream cost


def credits_for_cost(api_cost_usd: float) -> int:
    """Iron-rule price for an arbitrary upstream cost: ceil(usd / 0.04 * 2.5)."""
    return max(1, math.ceil(api_cost_usd / CREDIT_USD_PRICE * MARGIN_MULTIPLIER))


# Normalized model key → its billing row. `credits` are the doc-fixed values
# (rounded up from the formula). `usd` is the 2026-Q2 PiAPI upstream estimate.
VIDEO_CREDIT_COSTS = {
    "hailuo":          {"service_type": "video_hailuo",         "credits": 18,  "usd": 0.26, "label": "Hailuo Fast 10s 768p"},
    "wan":             {"service_type": "video_wan",            "credits": 20,  "usd": 0.28, "label": "Wan 480p"},
    "hunyuan":         {"service_type": "video_hunyuan",        "credits": 20,  "usd": 0.28, "label": "Hunyuan"},
    "kling_std":       {"service_type": "video_kling_std",      "credits": 28,  "usd": 0.40, "label": "Kling V2.5 STD 10s"},
    "seedance_720p":   {"service_type": "video_seedance_720p",  "credits": 65,  "usd": 1.00, "label": "Seedance 720p 5s"},
    "seedance_1080p":  {"service_type": "video_seedance_1080p", "credits": 160, "usd": 2.50, "label": "Seedance 1080p 5s"},
    "kling_v3_std":    {"service_type": "video_kling_v3_std",   "credits": 65,  "usd": 1.00, "label": "Kling V3.0 STD 10s"},
    "kling_v3_pro":    {"service_type": "video_kling_v3_pro",   "credits": 130, "usd": 2.00, "label": "Kling V3.0 PRO 10s 含音"},
    "veo":             {"service_type": "video_veo",            "credits": 80,  "usd": 1.20, "label": "Veo 3.1 5s 含音"},
    "sora2":           {"service_type": "video_sora2",          "credits": 80,  "usd": 1.20, "label": "Sora2 Pro 5s"},
}

IMAGE_CREDIT_COSTS = {
    "standard":        {"service_type": "text_to_image",            "credits": 2,  "usd": 0.015, "label": "Standard AI image (Z-Image/Qwen)"},
    "premium":         {"service_type": "image_generation_premium", "credits": 3,  "usd": 0.025, "label": "Premium image (Flux dev / Qwen edit)"},
    "nano_banana":     {"service_type": "nano_banana_t2i",          "credits": 8,  "usd": 0.105, "label": "Gemini / nano-banana 1K"},
    "nano_banana_4k":  {"service_type": "nano_banana_4k_t2i",       "credits": 12, "usd": 0.18,  "label": "nano-banana 4K"},
    "upscale":         {"service_type": "image_upscale",            "credits": 3,  "usd": 0.005, "label": "Upscale"},
    "bg_removal":      {"service_type": "bg_removal",               "credits": 2,  "usd": 0.001, "label": "Background Removal"},
}


def _norm(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def resolve_video_credits(
    model_id: Optional[str],
    resolution: Optional[str] = None,
    tier: Optional[str] = None,
) -> dict:
    """Map an incoming video (model_id, resolution, tier) to its billing row.

    Resolution disambiguates Seedance 720p vs 1080p; model/tier disambiguates
    Kling V2.5 STD vs V3.0 STD vs V3.0 PRO. Unknown models fall back to the
    Hailuo (cheapest) row so we never charge zero.
    """
    m, r, t = _norm(model_id), _norm(resolution), _norm(tier)

    # Exact canonical key (the frontend may send e.g. "seedance_1080p" directly).
    if m in VIDEO_CREDIT_COSTS:
        return VIDEO_CREDIT_COSTS[m]

    # The Kling-video endpoint sends a bare tier (default/flagship/omni) with no
    # model_id. Map those three onto the doc's three Kling tiers (28/65/130).
    if not m and t in ("default", "flagship", "omni"):
        return VIDEO_CREDIT_COSTS[
            {"default": "kling_std", "flagship": "kling_v3_std", "omni": "kling_v3_pro"}[t]
        ]

    if "veo" in m:
        return VIDEO_CREDIT_COSTS["veo"]
    if "sora" in m:
        return VIDEO_CREDIT_COSTS["sora2"]
    if "seedance" in m or "doubao" in m:
        if "1080" in m or "1080" in r:
            return VIDEO_CREDIT_COSTS["seedance_1080p"]
        return VIDEO_CREDIT_COSTS["seedance_720p"]
    if "kling" in m or "kling" in t:
        is_v3 = any(k in m for k in ("omni", "_v3", "v3", "kling3", "kling-3")) or t == "omni"
        if is_v3:
            # omni / audio / pro → the audio-enabled PRO tier; else V3.0 STD.
            if "pro" in m or "pro" in t or "audio" in m or "omni" in m:
                return VIDEO_CREDIT_COSTS["kling_v3_pro"]
            return VIDEO_CREDIT_COSTS["kling_v3_std"]
        if "flagship" in m or "master" in m or "2.1" in m or t == "flagship":
            return VIDEO_CREDIT_COSTS["kling_v3_std"]  # legacy 2.1-master → V3.0 STD tier
        return VIDEO_CREDIT_COSTS["kling_std"]  # Kling 2.5 / 2.6 standard
    if "hunyuan" in m or "tencent" in m:
        return VIDEO_CREDIT_COSTS["hunyuan"]
    if "wan" in m:
        return VIDEO_CREDIT_COSTS["wan"]
    return VIDEO_CREDIT_COSTS["hailuo"]


def resolve_image_credits(model_id: Optional[str], resolution: Optional[str] = None) -> dict:
    """Map an incoming image (model_id, resolution) to its billing row."""
    m, r = _norm(model_id), _norm(resolution)
    if "nano-banana" in m or "nano_banana" in m:
        if "4k" in m or "4k" in r or "2048" in r or "4096" in r:
            return IMAGE_CREDIT_COSTS["nano_banana_4k"]
        return IMAGE_CREDIT_COSTS["nano_banana"]
    if "gemini" in m:
        return IMAGE_CREDIT_COSTS["nano_banana"]
    if any(k in m for k in ("flux-dev", "flux_dev", "qwen-edit", "qwen_edit", "kontext", "edit")):
        return IMAGE_CREDIT_COSTS["premium"]
    return IMAGE_CREDIT_COSTS["standard"]  # flux schnell / z-image / qwen / seedream / sdxl


# Flat catalog used by seeds + the alembic migration to upsert service_pricing
# rows for every per-model entry above (keeps DB ⇄ code in lockstep).
def all_model_pricing_rows() -> list:
    """Return [(service_type, credits, usd, label, kind), ...] for every row."""
    rows = []
    for entry in IMAGE_CREDIT_COSTS.values():
        rows.append((entry["service_type"], entry["credits"], entry["usd"], entry["label"], "image"))
    for entry in VIDEO_CREDIT_COSTS.values():
        rows.append((entry["service_type"], entry["credits"], entry["usd"], entry["label"], "video"))
    return rows
