"""
Example Cache Service — Cache-through pattern for example mode.

Flow:
  1. User picks a preset (tool_type + preset_id)
  2. Build cache key: example:{tool_type}:{preset_id}
  3. Redis GET → HIT? return cached result
  4. MISS → call ProviderRouter.route() → store in Redis (forever) → return

Redis values have no TTL — once generated, a preset result lives forever.
The set of presets is finite (defined in example_presets.py), so Redis memory
is bounded and predictable.
"""
import json
import logging
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis

from app.config.example_presets import get_preset_by_id, get_presets
from app.providers.provider_router import ProviderRouter, TaskType, get_provider_router

logger = logging.getLogger(__name__)

# Map tool_type strings → TaskType enum for the ProviderRouter
TOOL_TO_TASK: Dict[str, TaskType] = {
    "background_removal": TaskType.BACKGROUND_REMOVAL,
    "product_scene": TaskType.T2I,
    "effect": TaskType.I2I,
    "room_redesign": TaskType.INTERIOR,
    "short_video": TaskType.I2V,
    "ai_avatar": TaskType.AVATAR,
    "pattern_generate": TaskType.T2I,
}


def _cache_key(tool_type: str, preset_id: str) -> str:
    """Build deterministic Redis cache key."""
    return f"example:{tool_type}:{preset_id}"


def _build_provider_params(preset: Dict[str, Any], tool_type: str) -> Dict[str, Any]:
    """
    Build the params dict that ProviderRouter.route() expects,
    from a preset record.
    """
    params: Dict[str, Any] = {}
    preset_params = preset.get("params", {})
    image_url = preset.get("image_url", "")

    if tool_type == "background_removal":
        params["image_url"] = image_url

    elif tool_type == "product_scene":
        params["prompt"] = preset_params.get("prompt", "")
        params["image_url"] = image_url
        params["size"] = "1024*1024"

    elif tool_type == "effect":
        params["prompt"] = preset_params.get("prompt", "")
        params["image_url"] = image_url

    elif tool_type == "room_redesign":
        params["prompt"] = preset_params.get("prompt", "")
        params["image_url"] = image_url
        params["style"] = preset_params.get("style", "modern")
        params["room_type"] = preset_params.get("room_type", "living_room")

    elif tool_type == "short_video":
        params["prompt"] = preset_params.get("prompt", "")
        params["image_url"] = image_url
        params["duration"] = preset_params.get("duration", 5)

    elif tool_type == "ai_avatar":
        params["image_url"] = image_url
        params["text"] = preset_params.get("text", "")
        params["prompt"] = preset_params.get("text", "")
        params["language"] = preset_params.get("language", "zh-TW")
        params["voice_id"] = preset_params.get("voice_id", "xiaoxiao")
        params["duration"] = preset_params.get("duration", 30)
        params["aspect_ratio"] = preset_params.get("aspect_ratio", "9:16")

    elif tool_type == "pattern_generate":
        params["prompt"] = preset_params.get("prompt", "")
        params["size"] = preset_params.get("size", "1024*1024")

    return params


def _extract_result_urls(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the output URLs from a ProviderRouter result."""
    output = result.get("output", {})
    data: Dict[str, Any] = {}
    if output.get("image_url"):
        data["image_url"] = output["image_url"]
    if output.get("video_url"):
        data["video_url"] = output["video_url"]
    if output.get("audio_url"):
        data["audio_url"] = output["audio_url"]
    return data


class ExampleCacheService:
    """
    Cache-through service for example mode.

    Usage:
        service = ExampleCacheService(redis)
        presets = service.list_presets("effect")
        result = await service.generate_or_cache("effect", "fx-bubbletea-anime")
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.router = get_provider_router()

    def list_presets(self, tool_type: str) -> List[Dict[str, Any]]:
        """
        Return available presets for a tool type.
        Strips internal fields (gemini_prompt, params) — only returns
        what the frontend needs to display.
        """
        presets = get_presets(tool_type)
        return [
            {
                "id": p["id"],
                "name": p["name"],
                "image_url": p.get("image_url", ""),
            }
            for p in presets
        ]

    async def generate_or_cache(
        self, tool_type: str, preset_id: str
    ) -> Dict[str, Any]:
        """
        Cache-through: return cached result or generate + cache.

        Returns:
            {
                "success": True,
                "from_cache": bool,
                "preset_id": str,
                "image_url": str (optional),
                "video_url": str (optional),
            }
        """
        # Validate preset exists
        preset = get_preset_by_id(tool_type, preset_id)
        if not preset:
            raise ValueError(f"Unknown preset: {tool_type}/{preset_id}")

        task_type = TOOL_TO_TASK.get(tool_type)
        if not task_type:
            raise ValueError(f"Unknown tool type: {tool_type}")

        key = _cache_key(tool_type, preset_id)

        # 1. Redis GET — cache hit?
        cached = await self.redis.get(key)
        if cached:
            logger.info(f"[ExampleCache] HIT: {key}")
            data = json.loads(cached)
            return {
                "success": True,
                "from_cache": True,
                "preset_id": preset_id,
                **data,
            }

        # 2. Cache miss — call provider
        logger.info(f"[ExampleCache] MISS: {key} — calling provider")
        params = _build_provider_params(preset, tool_type)

        result = await self.router.route(
            task_type=task_type,
            params=params,
            user_tier="starter",
            persist_to_gcs=True,
        )

        if not result.get("success"):
            raise Exception(
                f"Provider failed for {tool_type}/{preset_id}: "
                f"{result.get('error', 'unknown error')}"
            )

        # 3. Extract URLs and store in Redis (no TTL = forever)
        urls = _extract_result_urls(result)
        await self.redis.set(key, json.dumps(urls))
        logger.info(f"[ExampleCache] STORED: {key} → {list(urls.keys())}")

        return {
            "success": True,
            "from_cache": False,
            "preset_id": preset_id,
            **urls,
        }

    async def get_cache_status(self) -> Dict[str, Any]:
        """Get cache statistics — how many presets are cached per tool."""
        status: Dict[str, Dict[str, int]] = {}
        for tool_type in TOOL_TO_TASK:
            presets = get_presets(tool_type)
            total = len(presets)
            cached = 0
            for p in presets:
                key = _cache_key(tool_type, p["id"])
                if await self.redis.exists(key):
                    cached += 1
            status[tool_type] = {"total": total, "cached": cached}
        return status

    async def invalidate(
        self, tool_type: str, preset_id: Optional[str] = None
    ) -> int:
        """
        Invalidate cached results. Used when re-generating with a new provider.

        Args:
            tool_type: Tool to invalidate
            preset_id: Specific preset, or None for all presets in tool

        Returns:
            Number of keys deleted
        """
        if preset_id:
            key = _cache_key(tool_type, preset_id)
            return await self.redis.delete(key)

        # Delete all presets for this tool
        presets = get_presets(tool_type)
        count = 0
        for p in presets:
            key = _cache_key(tool_type, p["id"])
            count += await self.redis.delete(key)
        return count
