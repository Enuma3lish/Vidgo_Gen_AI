"""
Example Mode API — Endpoints for the preset-only example experience.

Users in example mode cannot type prompts. They can only:
  1. Browse available presets (GET /examples/{tool_type})
  2. Click to generate (POST /examples/{tool_type}/generate)

Results are cached in Redis forever. First request calls the AI provider;
subsequent requests for the same preset return instantly from cache.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import redis.asyncio as aioredis

from app.api.deps import get_redis
from app.config.example_presets import get_all_tool_types
from app.services.example_cache_service import ExampleCacheService

logger = logging.getLogger(__name__)
router = APIRouter()


class GenerateRequest(BaseModel):
    preset_id: str


@router.get("/{tool_type}")
async def list_presets(
    tool_type: str,
    language: Optional[str] = "en",
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """
    List available example presets for a tool.

    Returns preset id, name (localized), and thumbnail image URL.
    """
    valid_tools = get_all_tool_types()
    if tool_type not in valid_tools:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown tool type: {tool_type}. Valid: {valid_tools}",
        )

    service = ExampleCacheService(redis_client)
    presets = service.list_presets(tool_type)

    # Localize names
    for p in presets:
        name = p.get("name", {})
        if isinstance(name, dict):
            p["name"] = name.get("zh" if language and language.startswith("zh") else "en", "")

    return {"tool_type": tool_type, "presets": presets, "count": len(presets)}


@router.post("/{tool_type}/generate")
async def generate_example(
    tool_type: str,
    body: GenerateRequest,
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """
    Generate (or return cached) result for a preset.

    Cache-through:
      - Redis HIT → return instantly
      - Redis MISS → call AI provider → store in Redis forever → return
    """
    valid_tools = get_all_tool_types()
    if tool_type not in valid_tools:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown tool type: {tool_type}",
        )

    service = ExampleCacheService(redis_client)

    try:
        result = await service.generate_or_cache(tool_type, body.preset_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Example] Generation failed: {tool_type}/{body.preset_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail="Generation service is temporarily unavailable. Please try again.",
        )


@router.get("/status/cache")
async def cache_status(
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """
    Get cache status — how many presets are cached per tool.
    Useful for monitoring cache warm-up progress.
    """
    service = ExampleCacheService(redis_client)
    status = await service.get_cache_status()
    return {"cache": status}
