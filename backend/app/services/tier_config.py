"""
Tier-based generation configuration.

Two tiers:
- FREE: Users with only bonus credits (40-point registration bonus).
        Uses existing APIs with reduced quality (720P, short duration, no audio).
        Credit cost: 20-35 points per generation.

- PAID: Users who have purchased credits or have an active subscription.
        Uses existing APIs with full quality (1080P, longer duration, with audio).
        Credit cost: 80-120 points per generation.
"""
from typing import Dict, Any, Optional
from app.models.user import User


# ---------------------------------------------------------------------------
# Tier parameter configurations
# ---------------------------------------------------------------------------

FREE_TIER: Dict[str, Any] = {
    "name": "free",
    "max_resolution": "720P",
    "max_duration": 5,          # seconds for video
    "max_video_length": 10,     # seconds
    "audio_enabled": False,
    "image_size": "512*512",
    "credit_cost": {
        "t2i": 20,
        "i2v": 25,
        "t2v": 30,
        "i2i": 20,
        "avatar": 35,
        "interior": 25,
        "try_on": 25,
        "bg_removal": 20,
        "effect": 20,
        "pattern": 20,
        "interior_3d": 30,
    },
    "models": {
        "t2i": {"model": "Qubico/flux1-schnell", "size": "512*512"},
        "i2v": {"model": "Wan", "task_type": "wan26-img2video", "resolution": "720P", "duration": 5},
        "t2v": {"model": "Wan", "task_type": "wan26-txt2video", "resolution": "720P", "duration": 5},
        "i2i": {"model": "Qubico/flux1-schnell", "strength": 0.65},
        "avatar": {"resolution": "720p", "duration": 30, "audio_enabled": False},
        "interior": {"model": "Qubico/flux1-schnell", "size": "512*512"},
        "try_on": {"model": "kling", "batch_size": 1},
        "bg_removal": {"model": "Qubico/flux1-schnell"},
        "effect": {"model": "Qubico/flux1-schnell", "strength": 0.65},
        "pattern": {"model": "Qubico/flux1-schnell", "size": "512*512"},
        "interior_3d": {"model": "Qubico/trellis", "texture_size": 512},
    },
}

PAID_TIER: Dict[str, Any] = {
    "name": "paid",
    "max_resolution": "1080P",
    "max_duration": 15,         # seconds for video
    "max_video_length": 30,     # seconds
    "audio_enabled": True,
    "image_size": "1024*1024",
    "credit_cost": {
        "t2i": 80,
        "i2v": 100,
        "t2v": 120,
        "i2i": 80,
        "avatar": 100,
        "interior": 90,
        "try_on": 90,
        "bg_removal": 80,
        "effect": 80,
        "pattern": 80,
        "interior_3d": 100,
    },
    "models": {
        "t2i": {"model": "Qubico/flux1-schnell", "size": "1024*1024"},
        "i2v": {"model": "Wan", "task_type": "wan26-img2video", "resolution": "1080P", "duration": 15},
        "t2v": {"model": "Wan", "task_type": "wan26-txt2video", "resolution": "1080P", "duration": 15},
        "i2i": {"model": "Qubico/flux1-schnell", "strength": 0.70},
        "avatar": {"resolution": "1080p", "duration": 120, "audio_enabled": True},
        "interior": {"model": "Qubico/flux1-schnell", "size": "1024*1024"},
        "try_on": {"model": "kling", "batch_size": 2},
        "bg_removal": {"model": "Qubico/flux1-schnell"},
        "effect": {"model": "Qubico/flux1-schnell", "strength": 0.70},
        "pattern": {"model": "Qubico/flux1-schnell", "size": "1024*1024"},
        "interior_3d": {"model": "Qubico/trellis", "texture_size": 1024},
    },
}


def get_user_tier(user: User) -> str:
    """
    Determine user's tier based on credit/subscription state.

    Returns 'paid' if user has purchased credits or has an active plan.
    Returns 'free' otherwise (only bonus credits from registration).
    """
    if (user.purchased_credits or 0) > 0:
        return "paid"
    if user.current_plan_id is not None:
        return "paid"
    return "free"


def get_tier_config(user: User) -> Dict[str, Any]:
    """Get the full tier configuration for a user."""
    tier = get_user_tier(user)
    return PAID_TIER if tier == "paid" else FREE_TIER


def get_credit_cost(tool_type: str, user: User) -> int:
    """
    Get credit cost for a specific tool type based on user's tier.

    Args:
        tool_type: The tool type key (t2i, i2v, t2v, avatar, etc.)
        user: The User model instance

    Returns:
        Credit cost as integer
    """
    config = get_tier_config(user)
    return config["credit_cost"].get(tool_type, 30)  # Default 30 if unknown


def get_model_params(tool_type: str, user: User) -> Dict[str, Any]:
    """
    Get model parameters for a specific tool type based on user's tier.

    Args:
        tool_type: The tool type key
        user: The User model instance

    Returns:
        Dict of model parameters to pass to the provider
    """
    config = get_tier_config(user)
    return config["models"].get(tool_type, {})
