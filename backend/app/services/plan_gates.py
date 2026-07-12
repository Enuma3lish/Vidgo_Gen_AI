"""
Plan-tier gate for premium AI models.

Frontend pickers expose multiple model choices per tool (e.g. ShortVideo lets
the user pick Seedance / Kling Omni / Hailuo / Hunyuan / Wan). Without a
backend check, a tech-savvy user on the basic plan can hit the API directly
with ``model_id=kling_omni`` and consume Kling 3.0 even though their plan
only paid for the cheap default tier.

This module enforces the tier→model floor server-side. Endpoints call
``require_model_access(db, user, model_id)`` BEFORE deducting credits or
calling the provider. A user below the floor gets a 403 with an explicit
``required_plan`` hint so the frontend can prompt an upgrade.

Mapping (owner-approved 2026-05-20, conservative variant):
    basic     → flux, seedance (default), z-image
    pro       → + qwen, kling default (1.6), hailuo, hunyuan, wan
    premium   → + kling flagship (2.5), kling omni (3.0), veo 3.1
    enterprise→ + sora
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Plan
from app.models.user import User


# Plan precedence — index = tier rank. Anything not in this list defaults to 0.
PLAN_ORDER = ["basic", "pro", "premium", "enterprise"]

# Aliases for legacy / alternate plan names that should map to the same rank.
_PLAN_NAME_ALIASES = {
    "starter": "basic",
    "demo": "basic",
    "free": "basic",
    "pro_plus": "premium",
    "test_pro_usd_1": "premium",  # historical test SKU treated as premium
}


# Model-id substrings → required plan floor. Longest matching key wins
# (so "kling_omni" beats "kling"). All keys are lowercase; the lookup
# normalises the incoming model_id to lowercase before matching.
#
# IMPORTANT: keep the more-specific kling tiers ABOVE the generic "kling"
# entry so they take precedence during the longest-match scan.
_PLAN_FLOOR_FOR_MODEL: dict[str, str] = {
    # ── Premium video tiers ──
    "kling_omni":     "premium",
    "kling-omni":     "premium",
    "kling_v3":       "premium",
    "kling3":         "premium",
    "kling-3":        "premium",
    "kling_flagship": "premium",
    "kling-flagship": "premium",
    "flagship":       "premium",   # KlingVideo passes raw tier string "flagship"
    "omni":           "premium",   # KlingVideo passes raw tier string "omni"
    "2.1-master":     "premium",
    "veo":            "premium",
    "veo3":           "premium",
    "veo-3":          "premium",
    "veo3.1":         "premium",   # 2026-05-23 new model
    "veo-3-1":        "premium",
    "veo_31":         "premium",
    # Nano Banana Pro — Google Gemini's premium image tier (~$0.105/img)
    "nano-banana-pro": "premium",
    "nano_banana_pro": "premium",
    "nanobananapro":   "premium",

    # ── Pro-tier video / images ──
    "kling":          "pro",       # generic Kling (defaults to 1.6)
    "qwen":           "pro",
    "hailuo":         "pro",
    "minimax":        "pro",       # backend alias for hailuo
    "hunyuan":        "pro",
    "tencent":        "pro",       # backend alias for hunyuan
    "wan":            "pro",
    # Nano Banana 2 (~$0.03/img) + Seedream 5 Lite (~$0.05/img) — pro tier
    "nano-banana":    "pro",
    "nano_banana":    "pro",
    "nanobanana":     "pro",
    "nano-banana-2":  "pro",
    "seedream":       "pro",
    "seedream-5":     "pro",
    "seedream_5":     "pro",

    # ── Basic-tier (cheap default) ──
    "flux":           "basic",
    "seedance":       "basic",
    "doubao":         "basic",     # backend alias for seedance
    "z-image":        "basic",
    "z_image":        "basic",
    "zimage":         "basic",

    # ── Sora 2 Pro (premium tier as of 2026-06-09) ──
    # Sora 2 Pro is now exposed via PiAPI (primary) and Pollo (backup) at the
    # same billing row as Veo 3.1 (80 credits / $1.20 / 5s 1080p). It belongs
    # in the premium plan, not enterprise — keep these BEFORE the generic
    # "sora" entry so the longest-match scan wins. The bare "sora" key below
    # stays at enterprise as a safety net for the legacy OpenAI-direct alias
    # that was removed 2026-05-20.
    "sora2_pro":      "premium",
    "sora-2-pro":     "premium",
    "sora2-pro":      "premium",
    "sora_2_pro":     "premium",
    # Sora 2 STD (2026-07-12 SKU split) — $0.40 upstream / 30 credits. Sits at
    # the pro floor because subscribers pass through anyway (credits-only
    # policy) and it's still a video generation surface we don't want to
    # expose to free/demo. Keep BEFORE the generic "sora2" entry so the
    # longest-match scan picks std over the pro row.
    "sora2_std":      "pro",
    "sora-2-std":     "pro",
    "sora2-std":      "pro",
    "sora_2_std":     "pro",
    "sora2":          "premium",
    "sora-2":         "premium",
    "sora_2":         "premium",

    # ── Enterprise-only ──
    "sora":           "enterprise",
}


def _normalise_plan_name(name: Optional[str]) -> str:
    """Map raw plan.name into the canonical PLAN_ORDER vocabulary."""
    if not name:
        return "basic"
    n = name.strip().lower()
    return _PLAN_NAME_ALIASES.get(n, n)


def _required_floor(model_id: Optional[str]) -> Optional[str]:
    """Return required min plan name, or None if model_id is empty / unknown."""
    if not model_id:
        return None
    m = model_id.strip().lower()
    if not m:
        return None
    # Longest substring match wins so kling_omni → premium beats kling → pro.
    best_key: Optional[str] = None
    for key in _PLAN_FLOOR_FOR_MODEL:
        if key in m and (best_key is None or len(key) > len(best_key)):
            best_key = key
    if best_key is None:
        return None
    return _PLAN_FLOOR_FOR_MODEL[best_key]


async def require_model_access(
    db: AsyncSession,
    user: Optional[User],
    model_id: Optional[str],
) -> None:
    """
    Raise HTTPException(403) if ``user``'s plan tier is below the floor for
    ``model_id``. Empty / unknown ``model_id`` is allowed through.

    2026-07 policy change: EVERY active plan (basic/pro/premium/enterprise)
    may use EVERY model — per-model credit pricing already covers the
    upstream cost, so credits are the only gate for subscribers. Plans
    differentiate on monthly credits, concurrency, and queue priority
    (load_governor), not on model access. The floor table above is kept
    only to block users with NO plan (free tier) from premium upstreams.

    Call this BEFORE ``_check_and_deduct_credits`` so a rejected request
    never debits the wallet.

    Args:
        db:       Async session — used to load the user's Plan row.
        user:     Resolved User. ``None`` is permitted (no subscriber) but
                  callers normally gate on ``is_subscribed_user`` first.
        model_id: The model / tier string the client sent. May be a raw
                  frontend id ("seedance"), a tier label ("flagship"), or a
                  backend canonical id ("Doubao/seedance"). Substring match.
    """
    floor = _required_floor(model_id)
    if floor is None:
        return  # unknown / unspecified — nothing to gate

    # Superusers bypass for QA + ops dashboard testing.
    if user is not None and getattr(user, "is_superuser", False):
        return

    user_plan_name = "basic"
    if user is not None and user.current_plan_id:
        result = await db.execute(
            select(Plan).where(Plan.id == user.current_plan_id)
        )
        plan = result.scalar_one_or_none()
        if plan is not None:
            plan_name = (plan.name or "").strip().lower()
            if plan_name not in ("free", "demo"):
                # Any real subscription unlocks every model — credits gate.
                return
            user_plan_name = _normalise_plan_name(plan.name)

    floor = _normalise_plan_name(floor)

    try:
        user_idx = PLAN_ORDER.index(user_plan_name)
    except ValueError:
        user_idx = 0
    try:
        floor_idx = PLAN_ORDER.index(floor)
    except ValueError:
        floor_idx = 0

    if user_idx < floor_idx:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PLAN_TIER_REQUIRED",
                "message": (
                    f"Your '{user_plan_name}' plan does not include this model. "
                    f"Please upgrade to '{floor}' or higher."
                ),
                "user_plan": user_plan_name,
                "required_plan": floor,
                "model": model_id,
            },
        )
