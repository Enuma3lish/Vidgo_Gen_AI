"""
Demo Cache Service — Lazy Generation Architecture

Flow:
  1. Visitor hits tool page → check Redis cache
  2. Cache HIT  → return instantly
  3. Cache MISS → call real PiAPI API with default prompt → store in Redis (7-day TTL) → return
  4. Background task (hourly) → persist expiring Redis entries to Material DB

Cache key:  demo:{tool_type}:{topic}  → JSON list of demo results
"""
import json
import logging
import random
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.material import Material, ToolType, MaterialSource, MaterialStatus

logger = logging.getLogger(__name__)

CACHE_PREFIX = "demo"
CACHE_TTL = 7 * 24 * 3600  # 7 days

# Default prompts per tool — used when generating the first demo on cache miss
# Taiwan SMB focus: food, drinks, daily products — NOT luxury/tech
DEFAULT_DEMO_CONFIG: Dict[str, Dict[str, Any]] = {
    "background_removal": {
        "prompt": "A bubble tea cup with tapioca pearls on clean white background, product photography, studio lighting",
        "topic": "drinks",
    },
    "product_scene": {
        "prompt": "A handmade soap bar on white background, natural product photography",
        "topic": "studio",
        "scene_prompt": "professional studio lighting, clean background, commercial photography",
    },
    "try_on": {
        "prompt": "A white casual cotton t-shirt, flat lay on clean background, fashion photography",
        "topic": "casual",
    },
    "room_redesign": {
        "prompt": "A modern living room with white sofa and wooden floor, natural light from large windows",
        "topic": "modern_minimalist",
        "style_id": "modern_minimalist",
        "effect_prompt": "modern minimalist interior design, clean lines, neutral color palette, natural light",
    },
    "short_video": {
        "prompt": "A steaming cup of coffee on a wooden table, warm morning light, cozy cafe atmosphere",
        "topic": "product_showcase",
        "effect_prompt": "smooth natural camera motion, cinematic animation",
    },
    "ai_avatar": {
        "prompt": "Professional headshot of a young Asian woman smiling, studio lighting, clean background",
        "topic": "professional",
    },
    "pattern_generate": {
        "prompt": "Seamless bubble tea pattern with tapioca pearls and cups, packaging design, tileable",
        "topic": "seamless",
    },
    "effect": {
        "prompt": "A bubble tea cup with tapioca pearls, product photography, clean background",
        "topic": "anime",
        "effect_prompt": "anime style, vibrant colors, social media ad, Studio Ghibli inspired",
    },
}


def _cache_key(tool_type: str, topic: str = "_all") -> str:
    return f"{CACHE_PREFIX}:{tool_type}:{topic}"


class DemoCacheService:
    """
    Lazy-generation demo service.

    Lookup order:
      1. Redis cache (fast, 7-day TTL)
      2. Material DB (persistent, populated by TTL persistence job)
      3. Generate via real API → cache → return
    """

    def __init__(self, db: AsyncSession, redis=None):
        self.db = db
        self.redis = redis

    # ------------------------------------------------------------------
    # PUBLIC: get_or_generate — the main entry point
    # ------------------------------------------------------------------

    async def get_or_generate(
        self,
        tool_type: str,
        topic: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a demo result. If none cached, generate one via real API.

        Returns dict: {result_url, input_image_url, prompt, tool_type, topic}
        """
        # 1. Redis cache
        if self.redis:
            cached = await self._get_from_cache(tool_type, topic)
            if cached:
                return cached

        # 2. Material DB
        demo = await self._get_from_db(tool_type, topic)
        if demo:
            if self.redis:
                await self._warm_cache(tool_type, topic)
            return demo

        # 3. Cache miss everywhere — generate via real API
        logger.info(f"[DemoCache] Cache miss for {tool_type}:{topic}, generating via API...")
        generated = await self._generate_demo(tool_type, topic)
        return generated

    async def get_demos(
        self,
        tool_type: str,
        topic: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get multiple demos (for gallery/list views)."""
        if self.redis:
            key = _cache_key(tool_type, topic or "_all")
            raw = await self.redis.get(key)
            if raw:
                return json.loads(raw)[:limit]

        return await self._get_many_from_db(tool_type, topic, limit)

    # ------------------------------------------------------------------
    # GENERATE — call real PiAPI API on cache miss
    # ------------------------------------------------------------------

    # Expensive tools should NOT be lazy-generated on cache miss.
    # Only serve pre-generated content for these tools to avoid wasting API credits.
    EXPENSIVE_TOOLS = {"try_on", "ai_avatar", "short_video"}

    async def _generate_demo(
        self,
        tool_type: str,
        topic: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a demo via real API, store in Redis cache only.

        IMPORTANT: Each tool uses the correct workflow with input image + tool transformation.
        Expensive tools (try_on, ai_avatar, short_video) are NOT lazy-generated —
        they must be pre-generated via main_pregenerate.py to control costs.
        """
        from app.providers.provider_router import get_provider_router, TaskType

        # Block lazy generation for expensive tools — only serve pre-generated content
        if tool_type in self.EXPENSIVE_TOOLS:
            logger.info(f"[DemoCache] {tool_type} is expensive — skipping lazy generation, use main_pregenerate.py instead")
            return None

        config = DEFAULT_DEMO_CONFIG.get(tool_type)
        if not config:
            logger.warning(f"[DemoCache] No default config for tool_type={tool_type}")
            return None

        provider = get_provider_router()
        prompt = config["prompt"]
        used_topic = topic or config.get("topic", "_all")

        try:
            # Step 1: Generate input image via T2I (for tools that need one)
            input_url = None
            if tool_type != "pattern_generate":  # pattern is single-step
                t2i_result = await provider.route(
                    TaskType.T2I,
                    {"prompt": prompt, "size": "1024*1024"}
                )
                if not t2i_result.get("success"):
                    logger.error(f"[DemoCache] T2I failed for {tool_type}: {t2i_result.get('error')}")
                    return None
                output = t2i_result.get("output", {})
                input_url = (
                    output.get("image_url")
                    or (output.get("images", [{}])[0].get("url") if output.get("images") else None)
                )
                if not input_url:
                    logger.error(f"[DemoCache] T2I returned no image for {tool_type}")
                    return None

            # Step 2: Run tool-specific transformation using input image
            result_url = None
            video_url = None

            if tool_type == "pattern_generate":
                # Single-step: T2I result IS the pattern
                t2i_result = await provider.route(
                    TaskType.T2I,
                    {"prompt": prompt, "size": "1024*1024"}
                )
                if t2i_result.get("success"):
                    output = t2i_result.get("output", {})
                    result_url = output.get("image_url") or (output.get("images", [{}])[0].get("url") if output.get("images") else None)

            elif tool_type == "background_removal":
                # Input image → Remove BG API
                r = await provider.route(TaskType.BACKGROUND_REMOVAL, {"image_url": input_url})
                if r.get("success"):
                    result_url = r.get("output", {}).get("image_url")

            elif tool_type == "product_scene":
                # Input image → Remove BG → Generate scene → Composite
                # Step 2a: Remove background from product
                r = await provider.route(TaskType.BACKGROUND_REMOVAL, {"image_url": input_url})
                if not r.get("success"):
                    logger.error(f"[DemoCache] RemBG failed for product_scene")
                    return None
                product_no_bg = r.get("output", {}).get("image_url")

                # Step 2b: Generate scene background
                scene_prompt = config.get("scene_prompt", "professional studio lighting, clean background")
                scene_result = await provider.route(
                    TaskType.T2I,
                    {"prompt": scene_prompt, "size": "1024*1024"}
                )
                if scene_result.get("success"):
                    scene_output = scene_result.get("output", {})
                    result_url = scene_output.get("image_url") or (
                        scene_output.get("images", [{}])[0].get("url") if scene_output.get("images") else None
                    )
                # Note: PIL composite step is only in main_pregenerate.py,
                # here we use the scene as result for simplicity

            elif tool_type == "room_redesign":
                # Input room image → I2I with style prompt (preserves room structure)
                r = await provider.route(TaskType.I2I, {
                    "image_url": input_url,
                    "prompt": config.get("effect_prompt", "modern minimalist interior design"),
                    "strength": 0.65,
                })
                if r.get("success"):
                    result_url = r.get("output", {}).get("image_url")

            elif tool_type == "effect":
                # Input product image → I2I style transfer (same image, different style)
                r = await provider.route(TaskType.I2I, {
                    "image_url": input_url,
                    "prompt": config.get("effect_prompt", "anime style"),
                    "strength": 0.65,
                })
                if r.get("success"):
                    result_url = r.get("output", {}).get("image_url")

            if not result_url:
                logger.error(f"[DemoCache] Step 2 failed for {tool_type}")
                return None

            # Store in Redis cache (DB persistence happens via background task)
            demo_data = {
                "tool_type": tool_type,
                "topic": used_topic,
                "prompt": prompt,
                "input_image_url": input_url,
                "result_url": result_url,
                "result_image_url": result_url if not video_url else None,
                "result_video_url": video_url,
            }

            if self.redis:
                key = _cache_key(tool_type, used_topic)
                existing_raw = await self.redis.get(key)
                items = json.loads(existing_raw) if existing_raw else []
                items.append(demo_data)
                await self.redis.setex(key, CACHE_TTL, json.dumps(items))
                logger.info(f"[DemoCache] Generated and cached: {tool_type}:{used_topic}")

            return demo_data

        except Exception as e:
            logger.error(f"[DemoCache] Generation error for {tool_type}: {e}")
            return None

    # ------------------------------------------------------------------
    # PERSIST — move expiring Redis entries to Material DB
    # ------------------------------------------------------------------

    async def persist_expiring_to_db(self):
        """
        Scan Redis for demo:* keys with TTL < 1 day.
        Persist those entries to Material DB so they survive Redis expiry.
        Called by a background task (hourly).
        """
        if not self.redis:
            return 0

        ONE_DAY = 24 * 3600
        persisted = 0

        # Scan all demo keys
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(cursor, match=f"{CACHE_PREFIX}:*", count=100)
            for key in keys:
                ttl = await self.redis.ttl(key)
                if 0 < ttl < ONE_DAY:
                    raw = await self.redis.get(key)
                    if not raw:
                        continue
                    items = json.loads(raw)
                    for item in items:
                        # Check if already in DB
                        existing = await self.db.execute(
                            select(Material).where(
                                Material.tool_type == item.get("tool_type"),
                                Material.prompt == item.get("prompt"),
                                Material.is_active == True,
                            ).limit(1)
                        )
                        if existing.scalars().first():
                            continue

                        material = Material(
                            tool_type=item.get("tool_type"),
                            topic=item.get("topic", "_all"),
                            prompt=item.get("prompt", ""),
                            input_image_url=item.get("input_image_url"),
                            result_image_url=item.get("result_image_url"),
                            result_video_url=item.get("result_video_url"),
                            result_watermarked_url=item.get("result_url"),
                            source=MaterialSource.SEED,
                            status=MaterialStatus.APPROVED,
                            is_active=True,
                        )
                        self.db.add(material)
                        persisted += 1

            if cursor == 0:
                break

        if persisted > 0:
            await self.db.commit()
            logger.info(f"[DemoCache] Persisted {persisted} expiring demos to Material DB")

        return persisted

    # ------------------------------------------------------------------
    # WRITE — manual store (used by admin endpoint)
    # ------------------------------------------------------------------

    async def store_demo(
        self,
        tool_type: str,
        topic: str,
        prompt: str,
        result_url: str,
        input_image_url: Optional[str] = None,
        result_video_url: Optional[str] = None,
        watermarked_url: Optional[str] = None,
        extra_params: Optional[Dict] = None,
    ) -> Material:
        """Store a demo in both Redis and DB (for admin manual generation)."""
        material = Material(
            tool_type=tool_type,
            topic=topic,
            prompt=prompt,
            input_image_url=input_image_url,
            result_image_url=result_url,
            result_video_url=result_video_url,
            result_watermarked_url=watermarked_url or result_url,
            input_params=extra_params or {},
            source=MaterialSource.ADMIN,
            status=MaterialStatus.APPROVED,
            is_active=True,
        )
        self.db.add(material)
        await self.db.commit()
        await self.db.refresh(material)

        if self.redis:
            await self._warm_cache(tool_type, topic)

        return material

    # ------------------------------------------------------------------
    # CACHE helpers
    # ------------------------------------------------------------------

    async def _get_from_cache(self, tool_type: str, topic: Optional[str]) -> Optional[Dict[str, Any]]:
        key = _cache_key(tool_type, topic or "_all")
        raw = await self.redis.get(key)
        if not raw:
            return None
        items = json.loads(raw)
        return random.choice(items) if items else None

    async def _warm_cache(self, tool_type: str, topic: Optional[str] = None):
        items = await self._get_many_from_db(tool_type, topic, limit=50)
        if not items:
            return
        key = _cache_key(tool_type, topic or "_all")
        await self.redis.setex(key, CACHE_TTL, json.dumps(items))

    async def invalidate_cache(self, tool_type: str, topic: Optional[str] = None):
        if not self.redis:
            return
        await self.redis.delete(_cache_key(tool_type, topic or "_all"))

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    async def _get_from_db(self, tool_type: str, topic: Optional[str]) -> Optional[Dict[str, Any]]:
        query = select(Material).where(Material.tool_type == tool_type, Material.is_active == True)
        if topic:
            query = query.where(Material.topic == topic)
        query = query.order_by(func.random()).limit(1)
        result = await self.db.execute(query)
        m = result.scalars().first()
        return self._material_to_dict(m) if m else None

    async def _get_many_from_db(self, tool_type: str, topic: Optional[str], limit: int = 50) -> List[Dict[str, Any]]:
        query = select(Material).where(Material.tool_type == tool_type, Material.is_active == True)
        if topic:
            query = query.where(Material.topic == topic)
        query = query.order_by(Material.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return [self._material_to_dict(m) for m in result.scalars().all()]

    @staticmethod
    def _material_to_dict(m: Material) -> Dict[str, Any]:
        return {
            "id": str(m.id),
            "tool_type": m.tool_type.value if hasattr(m.tool_type, 'value') else m.tool_type,
            "topic": m.topic,
            "prompt": m.prompt,
            "input_image_url": m.input_image_url,
            "result_url": m.result_watermarked_url or m.result_image_url or m.result_video_url,
            "result_image_url": m.result_image_url,
            "result_video_url": m.result_video_url,
        }
