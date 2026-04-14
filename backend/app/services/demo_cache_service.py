"""
Demo Cache Service — Cache-First Demo Retrieval with On-Demand Generation

Flow:
    1. User requests a demo for (tool_type, topic/style)
    2. Check Redis cache → Material DB for existing result
    3. If found → return cached result (fast path)
    4. If NOT found → generate on-the-fly via provider_router → cache → return
    5. Everyone can trigger generation (not just developers)

Cache key: demo:{tool_type}:{topic} -> JSON list of demo results

On-Demand Generation:
    - Uses provider_router to call appropriate AI API
    - Results are watermarked and stored in Material DB
    - Cached in Redis for subsequent requests
    - No credits consumed for demo generation (limited per session)
"""
import hashlib
import json
import logging
import random
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.material import Material, ToolType, MaterialSource, MaterialStatus

logger = logging.getLogger(__name__)

CACHE_PREFIX = "demo"
def _cache_key(tool_type: str, topic: str = "_all") -> str:
    return f"{CACHE_PREFIX}:{tool_type}:{topic}"


# Tool type string → ToolType enum mapping
_TOOL_TYPE_MAP = {
    "background_removal": ToolType.BACKGROUND_REMOVAL,
    "product_scene": ToolType.PRODUCT_SCENE,
    "try_on": ToolType.TRY_ON,
    "room_redesign": ToolType.ROOM_REDESIGN,
    "short_video": ToolType.SHORT_VIDEO,
    "ai_avatar": ToolType.AI_AVATAR,
    "pattern_generate": ToolType.PATTERN_GENERATE,
    "effect": ToolType.EFFECT,
}


def _generate_lookup_hash(tool_type: str, prompt: str, effect_prompt: str = None, input_image_url: str = None) -> str:
    content = f"{tool_type}:{prompt}:{effect_prompt or ''}:{input_image_url or ''}"
    return hashlib.sha256(content.encode()).hexdigest()[:64]


class DemoCacheService:
    """
    Cache-first demo service with on-demand generation.

    Lookup order:
        1. Redis cache (fast, non-expiring)
        2. Material DB (persistent)
        3. On-demand generation via provider_router (if cache miss)

    Generated results are cached in both Material DB and Redis
    so subsequent requests are served instantly.
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
        Get a demo result — from cache if available, otherwise generate on-demand.

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

        # 3. On-demand generation
        logger.info(
            "[DemoCache] Cache miss for %s:%s — attempting on-demand generation.",
            tool_type, topic,
        )
        generated = await self._generate_on_demand(tool_type, topic)
        if generated:
            return generated

        logger.warning(
            "[DemoCache] On-demand generation failed for %s:%s.",
            tool_type, topic,
        )
        return None

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

    async def persist_expiring_to_db(self):
        """
        Deprecated no-op kept for compatibility.

        Demo cache entries are now written directly to Material DB and stored in
        Redis without TTL, so there is nothing to persist in the background.
        """
        return 0

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
    # ON-DEMAND GENERATION
    # ------------------------------------------------------------------

    async def _generate_on_demand(
        self,
        tool_type: str,
        topic: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a demo example on-the-fly using provider_router.

        The result is stored in Material DB and cached in Redis.
        This allows any user to trigger generation — not just developers.
        """
        try:
            from app.providers.provider_router import get_provider_router, TaskType
        except ImportError:
            logger.error("[DemoCache] Cannot import provider_router for on-demand generation")
            return None

        provider = get_provider_router()
        result = None
        input_image_url = None
        prompt = ""
        effect_prompt = None

        try:
            if tool_type in ("effect", ToolType.EFFECT.value if hasattr(ToolType.EFFECT, 'value') else "effect"):
                result = await self._generate_effect(provider, TaskType, topic)
            elif tool_type in ("background_removal", "BACKGROUND_REMOVAL"):
                result = await self._generate_background_removal(provider, TaskType, topic)
            elif tool_type in ("product_scene", "PRODUCT_SCENE"):
                result = await self._generate_product_scene(provider, TaskType, topic)
            elif tool_type in ("room_redesign", "ROOM_REDESIGN"):
                result = await self._generate_room_redesign(provider, TaskType, topic)
            elif tool_type in ("short_video", "SHORT_VIDEO"):
                result = await self._generate_short_video(provider, TaskType, topic)
            elif tool_type in ("pattern_generate", "PATTERN_GENERATE"):
                result = await self._generate_pattern(provider, TaskType, topic)
            elif tool_type in ("try_on", "TRY_ON"):
                result = await self._generate_try_on(provider, TaskType, topic)
            elif tool_type in ("ai_avatar", "AI_AVATAR"):
                result = await self._generate_ai_avatar(provider, TaskType, topic)
            else:
                logger.info(f"[DemoCache] No on-demand generator for tool_type={tool_type}")
                return None

            if not result or not result.get("success"):
                logger.warning(f"[DemoCache] On-demand generation failed for {tool_type}: {result}")
                return None

            # Store in Material DB
            material_dict = await self._store_generated_result(
                tool_type=tool_type,
                topic=topic or result.get("topic", "_all"),
                prompt=result.get("prompt", ""),
                effect_prompt=result.get("effect_prompt"),
                input_image_url=result.get("input_image_url"),
                result_image_url=result.get("result_image_url"),
                result_video_url=result.get("result_video_url"),
                input_params=result.get("input_params", {}),
            )

            if material_dict:
                # Warm cache
                if self.redis:
                    await self._warm_cache(tool_type, topic)
                return material_dict

        except Exception as e:
            logger.error(f"[DemoCache] On-demand generation error for {tool_type}: {e}", exc_info=True)

        return None

    async def _generate_effect(self, provider, TaskType, topic: Optional[str]) -> Optional[Dict]:
        """Generate an effect (style transfer) example on-demand."""
        from app.services.effects_service import VIDGO_STYLES, get_style_by_id, get_style_prompt

        # Pick a style based on topic or random
        style_id = topic
        if not style_id or style_id == "_all":
            style_ids = [s["id"] for s in VIDGO_STYLES]
            style_id = random.choice(style_ids)

        style = get_style_by_id(style_id)
        if not style:
            logger.warning(f"[DemoCache] Unknown style: {style_id}")
            return None

        style_prompt = get_style_prompt(style_id)

        # Step 1: Generate source image (a product photo)
        source_prompts = [
            "A cup of bubble milk tea with tapioca pearls, appetizing food photography, studio lighting, white background",
            "Crispy fried chicken cutlet on a plate, Taiwanese street food photography, studio lighting",
            "Glass skincare serum bottle with dropper, clean cosmetics product photo, white background",
            "Canvas tote bag with minimalist design, clean studio product photo, white background",
            "Fresh roasted coffee beans in kraft paper bag, artisan coffee product photo, white background",
        ]
        source_prompt = random.choice(source_prompts)

        logger.info(f"[DemoCache] Effect: generating source image...")
        t2i_result = await provider.route(
            TaskType.T2I,
            {"prompt": source_prompt, "width": 1024, "height": 1024},
        )

        if not t2i_result.get("success"):
            return {"success": False, "error": f"T2I failed: {t2i_result}"}

        source_url = t2i_result.get("output", {}).get("image_url")
        if not source_url:
            return {"success": False, "error": "No image URL from T2I"}

        # Step 2: Apply style via I2I
        logger.info(f"[DemoCache] Effect: applying style {style_id}...")
        i2i_result = await provider.route(
            TaskType.I2I,
            {
                "image_url": source_url,
                "prompt": style_prompt,
                "strength": 0.65,
            },
        )

        if not i2i_result.get("success"):
            return {"success": False, "error": f"I2I failed: {i2i_result}"}

        result_url = i2i_result.get("output", {}).get("image_url")
        if not result_url:
            return {"success": False, "error": "No image URL from I2I"}

        return {
            "success": True,
            "topic": style_id,
            "prompt": f"{source_prompt} | Style: {style_prompt}",
            "effect_prompt": style_prompt,
            "input_image_url": source_url,
            "result_image_url": result_url,
            "input_params": {"style_id": style_id, "source_prompt": source_prompt},
        }

    async def _generate_background_removal(self, provider, TaskType, topic: Optional[str]) -> Optional[Dict]:
        """Generate a background removal example on-demand."""
        prompts_by_topic = {
            "drinks": "A cup of bubble milk tea with tapioca pearls on white background, food photography",
            "snacks": "Crispy fried chicken cutlet on white background, Taiwanese street food, food photography",
            "desserts": "Mango shaved ice dessert on white background, colorful toppings, food photography",
            "meals": "Braised pork rice bento box on white background, Taiwanese comfort food",
            "packaging": "Eco-friendly drink cup with straw on white background, beverage packaging",
            "equipment": "Commercial blender on white background, restaurant equipment, product shot",
            "signage": "LED menu board display on white background, restaurant signage",
            "ingredients": "Fresh tapioca pearls in bowl on white background, bubble tea ingredient",
        }
        prompt = prompts_by_topic.get(topic, random.choice(list(prompts_by_topic.values())))

        # Step 1: Generate source image
        logger.info(f"[DemoCache] BG removal: generating source image...")
        t2i_result = await provider.route(
            TaskType.T2I,
            {"prompt": prompt, "width": 1024, "height": 1024},
        )
        if not t2i_result.get("success"):
            return {"success": False, "error": "T2I failed"}

        source_url = t2i_result.get("output", {}).get("image_url")
        if not source_url:
            return {"success": False, "error": "No image URL from T2I"}

        # Step 2: Remove background
        logger.info(f"[DemoCache] BG removal: removing background...")
        rembg_result = await provider.route(
            TaskType.BACKGROUND_REMOVAL,
            {"image_url": source_url},
        )
        if not rembg_result.get("success"):
            return {"success": False, "error": "RemBG failed"}

        result_url = rembg_result.get("output", {}).get("image_url")
        if not result_url:
            return {"success": False, "error": "No image URL from RemBG"}

        return {
            "success": True,
            "topic": topic or "general",
            "prompt": prompt,
            "input_image_url": source_url,
            "result_image_url": result_url,
        }

    async def _generate_product_scene(self, provider, TaskType, topic: Optional[str]) -> Optional[Dict]:
        """Generate a product scene example on-demand."""
        product_prompt = "Studio product photo of a clear cup of bubble milk tea with tapioca pearls, centered, clean white background, 8K"

        scene_prompts = {
            "studio": "professional studio lighting, solid color background, product photography",
            "nature": "outdoor nature setting, sunlight, leaves, natural environment",
            "elegant": "warm elegant background, cozy lighting, refined atmosphere",
            "minimal": "minimalist abstract background, soft shadows, clean composition",
            "lifestyle": "lifestyle home setting, cozy atmosphere, everyday context",
            "urban": "urban city backdrop, modern architecture, street style",
        }
        scene_prompt = scene_prompts.get(topic, random.choice(list(scene_prompts.values())))

        # Step 1: Generate product
        logger.info(f"[DemoCache] Product scene: generating product...")
        t2i_result = await provider.route(TaskType.T2I, {"prompt": product_prompt, "width": 1024, "height": 1024})
        if not t2i_result.get("success"):
            return {"success": False}

        product_url = t2i_result.get("output", {}).get("image_url")
        if not product_url:
            return {"success": False}

        # Step 2: Remove background
        logger.info(f"[DemoCache] Product scene: removing background...")
        rembg = await provider.route(TaskType.BACKGROUND_REMOVAL, {"image_url": product_url})
        if not rembg.get("success"):
            return {"success": False}

        # Step 3: Generate scene (using I2I for simplicity, or just return the product in clean bg)
        logger.info(f"[DemoCache] Product scene: generating scene...")
        full_scene_prompt = f"{scene_prompt}, product placement, commercial photography, 8K"
        scene_result = await provider.route(TaskType.T2I, {"prompt": full_scene_prompt, "width": 1024, "height": 1024})

        result_url = scene_result.get("output", {}).get("image_url") if scene_result.get("success") else product_url

        return {
            "success": True,
            "topic": topic or "studio",
            "prompt": f"{product_prompt} | {scene_prompt}",
            "input_image_url": product_url,
            "result_image_url": result_url,
        }

    async def _generate_room_redesign(self, provider, TaskType, topic: Optional[str]) -> Optional[Dict]:
        """Generate a room redesign example on-demand."""
        room_urls = {
            "living_room": "https://images.unsplash.com/photo-1554995207-c18c203602cb?w=800",
            "bedroom": "https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=800",
            "kitchen": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800",
            "bathroom": "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800",
        }
        room_type = topic if topic in room_urls else random.choice(list(room_urls.keys()))
        room_url = room_urls[room_type]

        style_prompt = "modern minimalist style, clean lines, neutral colors, photorealistic interior design, 8K"

        logger.info(f"[DemoCache] Room redesign: I2I transform...")
        result = await provider.route(
            TaskType.I2I,
            {"image_url": room_url, "prompt": style_prompt, "strength": 0.65},
        )
        if not result.get("success"):
            return {"success": False}

        result_url = result.get("output", {}).get("image_url")
        if not result_url:
            return {"success": False}

        return {
            "success": True,
            "topic": room_type,
            "prompt": style_prompt,
            "input_image_url": room_url,
            "result_image_url": result_url,
        }

    async def _generate_short_video(self, provider, TaskType, topic: Optional[str]) -> Optional[Dict]:
        """Generate a short video example on-demand."""
        prompts = {
            "product_showcase": "Cinematic close-up of bubble milk tea being poured, tapioca pearls swirling, 4K",
            "brand_intro": "Cozy drink shop interior, barista preparing beverage, warm lighting, brand story",
            "tutorial": "Step by step bubble tea preparation, adding tapioca and milk, instruction video",
            "promo": "Buy one get one free drink promotion, two colorful beverages, festive graphics",
        }
        prompt = prompts.get(topic, random.choice(list(prompts.values())))

        # Step 1: T2I
        logger.info(f"[DemoCache] Short video: generating source image...")
        t2i = await provider.route(TaskType.T2I, {"prompt": prompt, "width": 1024, "height": 1024})
        if not t2i.get("success"):
            return {"success": False}

        source_url = t2i.get("output", {}).get("image_url")
        if not source_url:
            return {"success": False}

        # Step 2: I2V
        logger.info(f"[DemoCache] Short video: generating video from image...")
        i2v = await provider.route(TaskType.I2V, {"image_url": source_url, "prompt": prompt})
        if not i2v.get("success"):
            return {"success": False}

        video_url = i2v.get("output", {}).get("video_url")
        if not video_url:
            return {"success": False}

        return {
            "success": True,
            "topic": topic or "product_showcase",
            "prompt": prompt,
            "input_image_url": source_url,
            "result_video_url": video_url,
        }

    async def _generate_pattern(self, provider, TaskType, topic: Optional[str]) -> Optional[Dict]:
        """Generate a pattern example on-demand."""
        prompts = {
            "seamless": "Elegant floral pattern for packaging, rose and navy, seamless tile",
            "floral": "Cherry blossom pattern for cafe branding, soft pink and white",
            "geometric": "Modern geometric pattern, triangles black and gold, professional",
            "abstract": "Marble texture pattern for cosmetics packaging, gold veins",
            "traditional": "Chinese cloud pattern, red and gold, auspicious design",
        }
        prompt = prompts.get(topic, random.choice(list(prompts.values())))
        full_prompt = f"Seamless pattern design, {prompt}, tileable, high quality, 8K"

        logger.info(f"[DemoCache] Pattern: generating...")
        t2i = await provider.route(TaskType.T2I, {"prompt": full_prompt, "width": 1024, "height": 1024})
        if not t2i.get("success"):
            return {"success": False}

        result_url = t2i.get("output", {}).get("image_url")
        if not result_url:
            return {"success": False}

        return {
            "success": True,
            "topic": topic or "seamless",
            "prompt": prompt,
            "result_image_url": result_url,
        }

    async def _generate_try_on(self, provider, TaskType, topic: Optional[str]) -> Optional[Dict]:
        """
        Generate a virtual try-on example on-demand.

        Try-on has NO MCP path (neither piapi_mcp nor pollo_mcp implements it).
        We call PiAPI's REST `kling ai_try_on` directly via the same client the
        live tools.py:/try-on endpoint uses, with a fixed apparel garment +
        female-1 model. Result is persisted to Material DB so the next visitor
        click on this preset hits the cache.
        """
        from scripts.services.piapi_client import PiAPIClient
        import os

        # Hardcoded demo seed inputs that have proven Kling-acceptable
        # (>=512px on both sides, real apparel images on a public CDN).
        DEMO_SEEDS = [
            {
                "topic": "tshirt",
                "prompt": "white cotton t-shirt try-on",
                "model_url": "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=768&fit=crop",
                "garment_url": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=768&fit=crop",
            },
            {
                "topic": "dress",
                "prompt": "floral summer dress try-on",
                "model_url": "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=768&fit=crop",
                "garment_url": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=768&fit=crop",
            },
            {
                "topic": "blouse",
                "prompt": "white blouse try-on",
                "model_url": "https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?w=768&fit=crop",
                "garment_url": "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=768&fit=crop",
            },
        ]
        seed = next((s for s in DEMO_SEEDS if s["topic"] == topic), None) or random.choice(DEMO_SEEDS)

        logger.info(f"[DemoCache] Try-On: generating model={seed['model_url'][:60]}... garment={seed['garment_url'][:60]}...")

        piapi = PiAPIClient(api_key=os.getenv("PIAPI_KEY", ""))
        result = await piapi.virtual_try_on(
            model_image_url=seed["model_url"],
            garment_image_url=seed["garment_url"],
            save_locally=False,
        )

        if not result or not result.get("success"):
            err = result.get("error") if result else "unknown"
            logger.warning(f"[DemoCache] Try-On generation failed: {err}")
            return {"success": False, "error": err}

        result_url = result.get("image_url")
        if not result_url:
            return {"success": False, "error": "No image URL from PiAPI try-on"}

        return {
            "success": True,
            "topic": seed["topic"],
            "prompt": seed["prompt"],
            "input_image_url": seed["garment_url"],
            "result_image_url": result_url,
            "input_params": {
                "model_url": seed["model_url"],
                "garment_url": seed["garment_url"],
            },
        }

    async def _generate_ai_avatar(self, provider, TaskType, topic: Optional[str]) -> Optional[Dict]:
        """
        Generate an AI avatar example on-demand.

        Routes through provider_router with TaskType.AVATAR — primary is
        piapi_mcp's `generate_video_kling`, fallback is REST piapi. Uses a
        hardcoded portrait + short script seed per topic.
        """
        DEMO_SCRIPTS = [
            {
                "topic": "presenter",
                "language": "en",
                "image_url": "https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?w=768&fit=crop",
                "script": "Welcome to VidGo AI. Let me show you what we can do.",
            },
            {
                "topic": "teacher",
                "language": "en",
                "image_url": "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=768&fit=crop",
                "script": "Today we'll learn how to create amazing visuals with AI.",
            },
            {
                "topic": "spokesperson",
                "language": "zh-TW",
                "image_url": "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=768&fit=crop",
                "script": "歡迎使用 VidGo AI，讓我們一起創造精彩的視覺內容。",
            },
        ]
        seed = next((s for s in DEMO_SCRIPTS if s["topic"] == topic), None) or random.choice(DEMO_SCRIPTS)

        logger.info(f"[DemoCache] AI Avatar: generating script={seed['script'][:40]}... lang={seed['language']}")

        result = await provider.route(
            TaskType.AVATAR,
            {
                "image_url": seed["image_url"],
                "script": seed["script"],
                "language": seed["language"],
                "duration": 10,
                "resolution": "720p",
                "aspect_ratio": "9:16",
            },
        )

        if not result or not result.get("success"):
            err = result.get("error") if result else "unknown"
            logger.warning(f"[DemoCache] AI Avatar generation failed: {err}")
            return {"success": False, "error": err}

        output = result.get("output", {})
        video_url = output.get("video_url") or output.get("url")
        if not video_url:
            return {"success": False, "error": "No video URL from avatar provider"}

        return {
            "success": True,
            "topic": seed["topic"],
            "prompt": seed["script"][:100],
            "input_image_url": seed["image_url"],
            "result_video_url": video_url,
            "input_params": {
                "language": seed["language"],
                "script": seed["script"],
            },
        }

    async def _store_generated_result(
        self,
        tool_type: str,
        topic: str,
        prompt: str,
        effect_prompt: Optional[str] = None,
        input_image_url: Optional[str] = None,
        result_image_url: Optional[str] = None,
        result_video_url: Optional[str] = None,
        input_params: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """Store an on-demand generated result into Material DB and return as dict."""
        try:
            # Resolve tool_type to enum
            tt = tool_type
            if isinstance(tool_type, str):
                tt_lower = tool_type.lower()
                tt = _TOOL_TYPE_MAP.get(tt_lower, tool_type)

            lookup_hash = _generate_lookup_hash(
                str(tool_type), prompt, effect_prompt, input_image_url
            )

            # Check duplicate
            existing = await self.db.execute(
                select(Material).where(Material.lookup_hash == lookup_hash)
            )
            existing_mat = existing.scalar_one_or_none()
            if existing_mat:
                return self._material_to_dict(existing_mat)

            # Watermarked URL = result URL for now (watermarking happens at display)
            watermarked = result_image_url or result_video_url

            material = Material(
                lookup_hash=lookup_hash,
                tool_type=tt,
                topic=topic,
                prompt=prompt,
                effect_prompt=effect_prompt,
                input_image_url=input_image_url,
                result_image_url=result_image_url,
                result_video_url=result_video_url,
                result_watermarked_url=watermarked,
                input_params=input_params or {},
                source=MaterialSource.SEED,
                status=MaterialStatus.APPROVED,
                is_active=True,
                quality_score=0.8,
                is_featured=False,
            )
            self.db.add(material)
            await self.db.commit()
            await self.db.refresh(material)

            logger.info(f"[DemoCache] Stored on-demand result: {tool_type}/{topic}")
            return self._material_to_dict(material)

        except Exception as e:
            logger.error(f"[DemoCache] Failed to store generated result: {e}", exc_info=True)
            try:
                await self.db.rollback()
            except Exception:
                pass
            # Return the result even if DB storage failed
            return {
                "id": "temp",
                "tool_type": str(tool_type),
                "topic": topic,
                "prompt": prompt,
                "input_image_url": input_image_url,
                "result_url": result_image_url or result_video_url,
                "result_image_url": result_image_url,
                "result_video_url": result_video_url,
            }

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
        await self.redis.set(key, json.dumps(items))

    async def invalidate_cache(self, tool_type: str, topic: Optional[str] = None):
        if not self.redis:
            return
        await self.redis.delete(_cache_key(tool_type, topic or "_all"))

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    async def _get_from_db(self, tool_type: str, topic: Optional[str]) -> Optional[Dict[str, Any]]:
        query = select(Material).where(
            Material.tool_type == tool_type,
            Material.is_active == True,
            Material.status.in_([MaterialStatus.APPROVED, MaterialStatus.FEATURED]),
        )
        if topic:
            query = query.where(Material.topic == topic)
        query = query.order_by(func.random()).limit(1)
        result = await self.db.execute(query)
        m = result.scalars().first()
        return self._material_to_dict(m) if m else None

    async def _get_many_from_db(self, tool_type: str, topic: Optional[str], limit: int = 50) -> List[Dict[str, Any]]:
        query = select(Material).where(
            Material.tool_type == tool_type,
            Material.is_active == True,
            Material.status.in_([MaterialStatus.APPROVED, MaterialStatus.FEATURED]),
        )
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
