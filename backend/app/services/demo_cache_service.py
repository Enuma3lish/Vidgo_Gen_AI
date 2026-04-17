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
        product_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a demo result — from cache if available, otherwise generate on-demand.

        For product_scene, `product_id` narrows lookup to a specific product.
        For ai_avatar, `product_id` = avatar_id and `language` picks the script
        language (zh-TW or en).

        Returns dict: {result_url, input_image_url, prompt, tool_type, topic}
        """
        # 1. Material DB (filtered by product_id if provided). Skip Redis cache when
        # product_id is set, since the cache key only includes topic.
        demo = await self._get_from_db(
            tool_type, topic, product_id=product_id, language=language
        )
        if demo:
            if self.redis and not product_id:
                await self._warm_cache(tool_type, topic)
            return demo

        if self.redis and not product_id and not language:
            cached = await self._get_from_cache(tool_type, topic)
            if cached:
                return cached

        # 3. On-demand generation
        logger.info(
            "[DemoCache] Cache miss for %s:%s product=%s lang=%s — on-demand gen.",
            tool_type, topic, product_id, language,
        )
        generated = await self._generate_on_demand(
            tool_type, topic, product_id=product_id, language=language
        )
        if generated:
            return generated

        logger.warning(
            "[DemoCache] On-demand generation failed for %s:%s product=%s.",
            tool_type, topic, product_id,
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
        product_id: Optional[str] = None,
        language: Optional[str] = None,
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
                result = await self._generate_effect(provider, TaskType, topic, product_id)
            elif tool_type in ("background_removal", "BACKGROUND_REMOVAL"):
                result = await self._generate_background_removal(provider, TaskType, topic)
            elif tool_type in ("product_scene", "PRODUCT_SCENE"):
                result = await self._generate_product_scene(provider, TaskType, topic, product_id)
            elif tool_type in ("room_redesign", "ROOM_REDESIGN"):
                result = await self._generate_room_redesign(provider, TaskType, topic)
            elif tool_type in ("short_video", "SHORT_VIDEO"):
                result = await self._generate_short_video(provider, TaskType, topic)
            elif tool_type in ("pattern_generate", "PATTERN_GENERATE"):
                result = await self._generate_pattern(provider, TaskType, topic)
            elif tool_type in ("try_on", "TRY_ON"):
                result = await self._generate_try_on(provider, TaskType, topic, product_id)
            elif tool_type in ("ai_avatar", "AI_AVATAR"):
                result = await self._generate_ai_avatar(
                    provider, TaskType, topic, product_id, language
                )
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

    async def _generate_effect(
        self,
        provider,
        TaskType,
        topic: Optional[str],
        product_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """Generate an effect (style transfer) example on-demand.

        Source images are the 8 frozen product photos (gs://.../static/products/)
        — no more T2I-generated source each run. Only the I2I style application
        is non-deterministic. `topic` = style_id, `product_id` = source product.
        """
        from app.services.effects_service import VIDGO_STYLES, get_style_by_id, get_style_prompt

        # Resolve style
        style_id = topic
        if not style_id or style_id == "_all":
            style_id = random.choice([s["id"] for s in VIDGO_STYLES])
        style = get_style_by_id(style_id)
        if not style:
            logger.warning(f"[DemoCache] Unknown style: {style_id}")
            return None
        style_prompt = get_style_prompt(style_id)

        # Frozen source photos (reuse the curated product library)
        source_urls = {
            "product-1": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-1.png",
            "product-2": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-2.png",
            "product-3": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-3.png",
            "product-4": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-4.png",
            "product-5": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-5.png",
            "product-6": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-6.png",
            "product-7": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-7.png",
            "product-8": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-8.png",
        }
        resolved_pid = product_id if product_id in source_urls else random.choice(list(source_urls.keys()))
        source_url = source_urls[resolved_pid]

        logger.info(f"[DemoCache] Effect: {resolved_pid} -> style={style_id}")
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
            "prompt": f"{resolved_pid} | Style: {style_prompt}",
            "effect_prompt": style_prompt,
            "input_image_url": source_url,
            "result_image_url": result_url,
            "input_params": {
                "style_id": style_id,
                "product_id": resolved_pid,
            },
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

    async def _generate_product_scene(
        self,
        provider,
        TaskType,
        topic: Optional[str],
        product_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """Generate a product scene example on-demand for the given (product_id, scene).

        Uses frozen, human-reviewed product photos as inputs (no T2I product step)
        so every on-demand run produces the same product image for the same id.
        """
        # Fixed curated product URLs — must stay in sync with
        # scripts/main_pregenerate.py PRODUCT_SCENE_MAPPING and the GCS assets at
        # gs://vidgo-media-vidgo-ai/static/products/.
        product_urls = {
            "product-1": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-1.png",
            "product-2": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-2.png",
            "product-3": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-3.png",
            "product-4": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-4.png",
            "product-5": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-5.png",
            "product-6": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-6.png",
            "product-7": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-7.png",
            "product-8": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-8.png",
        }
        product_labels = {
            "product-1": "bubble milk tea",
            "product-2": "canvas tote bag",
            "product-3": "handmade silver jewelry set",
            "product-4": "skincare serum glass bottle",
            "product-5": "roasted coffee beans in kraft bag",
            "product-6": "stainless steel espresso machine",
            "product-7": "handmade soy candle in glass jar",
            "product-8": "premium retail gift box set",
        }
        resolved_pid = product_id if product_id in product_urls else random.choice(list(product_urls.keys()))
        product_url = product_urls[resolved_pid]
        product_label = product_labels[resolved_pid]

        scene_prompts = {
            "studio": "professional studio lighting, solid color background, product photography",
            "nature": "outdoor nature setting, sunlight, leaves, natural environment",
            "elegant": "warm elegant background, cozy lighting, refined atmosphere",
            "minimal": "minimalist abstract background, soft shadows, clean composition",
            "lifestyle": "lifestyle home setting, cozy atmosphere, everyday context",
            "urban": "urban city backdrop, modern architecture, street style",
            "seasonal": "seasonal autumn leaves background, warm golden colors, cozy seasonal mood",
            "holiday": "festive holiday decoration background, warm holiday lights, celebration",
        }
        scene_prompt = scene_prompts.get(topic, scene_prompts["studio"])

        # Step 1: Remove background from the frozen product image
        logger.info(f"[DemoCache] Product scene: removing background from {resolved_pid}...")
        rembg = await provider.route(TaskType.BACKGROUND_REMOVAL, {"image_url": product_url})
        if not rembg.get("success"):
            logger.warning(f"[DemoCache] rembg failed: {rembg}")
            return {"success": False}

        # Step 2: Generate scene background via T2I (only non-deterministic step)
        logger.info(f"[DemoCache] Product scene: generating {topic} scene...")
        full_scene_prompt = f"{scene_prompt}, empty background for product placement, commercial photography, 8K"
        scene_result = await provider.route(
            TaskType.T2I, {"prompt": full_scene_prompt, "width": 1024, "height": 1024}
        )
        if not scene_result.get("success"):
            logger.warning(f"[DemoCache] scene T2I failed: {scene_result}")
            return {"success": False}

        # Compositing is handled by the live /tools/product-scene endpoint via PIL.
        # Here we return the generated scene; tools.py or the pregen script will
        # composite when writing to the Material DB.
        result_url = scene_result.get("output", {}).get("image_url")
        if not result_url:
            return {"success": False}

        return {
            "success": True,
            "topic": topic or "studio",
            "prompt": f"{product_label} | {scene_prompt}",
            "input_image_url": product_url,
            "result_image_url": result_url,
            "input_params": {
                "product_id": resolved_pid,
                "scene_type": topic or "studio",
            },
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

    async def _generate_try_on(
        self,
        provider,
        TaskType,
        topic: Optional[str],
        product_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Generate a virtual try-on example on-demand using the frozen curated
        model + garment photos from GCS. `topic` is the clothing category
        (tshirt/dress/jacket/blouse/sweater/coat). `product_id` carries the
        model_id (female-1..3 / male-1..3) — we overload the name since the
        on-demand endpoint only exposes one extra param.

        Try-on has NO MCP path — we call PiAPI's REST `kling ai_try_on`
        directly via the same client the live /tools/try-on endpoint uses.
        Result is persisted to Material DB so the next visitor click hits cache.
        """
        from scripts.services.piapi_client import PiAPIClient
        import os

        _GCS_TRYON = "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon"

        MODELS = {
            "female-1": {"gender": "female", "url": f"{_GCS_TRYON}/models/female-1.png"},
            "female-2": {"gender": "female", "url": f"{_GCS_TRYON}/models/female-2.png"},
            "female-3": {"gender": "female", "url": f"{_GCS_TRYON}/models/female-3.png"},
            "male-1":   {"gender": "male",   "url": f"{_GCS_TRYON}/models/male-1.png"},
            "male-2":   {"gender": "male",   "url": f"{_GCS_TRYON}/models/male-2.png"},
            "male-3":   {"gender": "male",   "url": f"{_GCS_TRYON}/models/male-3.png"},
        }

        GARMENTS = {
            "tshirt": {"name": "plain white t-shirt", "url": f"{_GCS_TRYON}/garments/garment-tshirt.png", "female_only": False},
            "dress":  {"name": "floral midi dress",   "url": f"{_GCS_TRYON}/garments/garment-dress.png",  "female_only": True},
            "jacket": {"name": "denim jacket",        "url": f"{_GCS_TRYON}/garments/garment-jacket.png", "female_only": False},
            "blouse": {"name": "silk blouse",         "url": f"{_GCS_TRYON}/garments/garment-blouse.png", "female_only": True},
            "sweater":{"name": "knit sweater",        "url": f"{_GCS_TRYON}/garments/garment-sweater.png","female_only": False},
            "coat":   {"name": "trench coat",         "url": f"{_GCS_TRYON}/garments/garment-coat.png",   "female_only": False},
        }

        # Resolve model_id (passed via product_id for API reuse)
        model_id = product_id if product_id in MODELS else "female-1"
        model = MODELS[model_id]

        # Resolve garment from topic; fall back to tshirt if unknown
        garment_key = topic if topic in GARMENTS else "tshirt"
        garment = GARMENTS[garment_key]

        # Enforce gender restriction
        if garment["female_only"] and model["gender"] == "male":
            logger.info(
                f"[DemoCache] Try-On: {garment_key} is female-only, "
                f"model={model_id} is male — falling back to tshirt"
            )
            garment_key = "tshirt"
            garment = GARMENTS["tshirt"]

        logger.info(
            f"[DemoCache] Try-On: model={model_id} garment={garment_key}"
        )

        piapi = PiAPIClient(api_key=os.getenv("PIAPI_KEY", ""))
        result = await piapi.virtual_try_on(
            model_image_url=model["url"],
            garment_image_url=garment["url"],
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
            "topic": garment_key,
            "prompt": f"{model['gender']} model trying on {garment['name']}",
            "input_image_url": garment["url"],
            "result_image_url": result_url,
            "input_params": {
                "model_id": model_id,
                "model_url": model["url"],
                "clothing_id": f"garment-{garment_key}",
                "garment_url": garment["url"],
            },
        }

    async def _generate_ai_avatar(
        self,
        provider,
        TaskType,
        topic: Optional[str],
        product_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Generate an AI avatar example on-demand.

        `product_id` → avatar_id (female-1..3 / male-1..3). Picks the correct
        frozen portrait so the gender the visitor chose is honored.
        `language`   → zh-TW or en. Picks the right script + TTS language.
        `topic`      → script category (spokesperson / product_intro / etc.),
                       optional — defaults to spokesperson.
        """
        # Dedicated head-and-shoulders portraits for Kling Avatar (full-body
        # try-on models don't pass Kling's face detector — "failed to freeze
        # point"). These are frozen curated assets in a separate GCS path.
        _GCS_AVATARS = "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/avatars"

        AVATAR_URLS = {
            "female-1": f"{_GCS_AVATARS}/female-1.png",
            "female-2": f"{_GCS_AVATARS}/female-2.png",
            "female-3": f"{_GCS_AVATARS}/female-3.png",
            "male-1":   f"{_GCS_AVATARS}/male-1.png",
            "male-2":   f"{_GCS_AVATARS}/male-2.png",
            "male-3":   f"{_GCS_AVATARS}/male-3.png",
        }
        # One short script per (category, language). Kept brief so the
        # talking-head video stays ~10s. Longer scripts live in Material DB
        # via pregen; this is only the on-demand fallback.
        SCRIPTS = {
            ("spokesperson", "zh-TW"): "歡迎認識我們的品牌故事，我們用心做好每一件產品。",
            ("spokesperson", "en"):    "Welcome to our brand story. Every product is made with care.",
            ("product_intro", "zh-TW"): "讓我介紹這款產品，品質優良、價格實惠，限時特惠中。",
            ("product_intro", "en"):    "Let me introduce this product. Great quality, great price, on sale now.",
            ("customer_service", "zh-TW"): "有任何問題都可以聯絡我們，我們會在兩小時內回覆您。",
            ("customer_service", "en"):    "Contact us anytime with questions. We reply within two hours.",
            ("social_media", "zh-TW"): "記得按讚訂閱追蹤，更多精彩內容即將推出，不要錯過！",
            ("social_media", "en"):    "Like, subscribe, and follow for more. You do not want to miss this!",
        }

        resolved_avatar_id = product_id if product_id in AVATAR_URLS else "female-1"
        image_url = AVATAR_URLS[resolved_avatar_id]

        resolved_language = language if language in ("zh-TW", "en") else "zh-TW"
        resolved_topic = topic if (topic, resolved_language) in SCRIPTS else "spokesperson"
        script = SCRIPTS[(resolved_topic, resolved_language)]

        logger.info(
            f"[DemoCache] AI Avatar: avatar={resolved_avatar_id} lang={resolved_language} "
            f"topic={resolved_topic}"
        )

        result = await provider.route(
            TaskType.AVATAR,
            {
                "image_url": image_url,
                "script": script,
                "language": resolved_language,
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
            "topic": resolved_topic,
            "language": resolved_language,
            "prompt": script[:100],
            "input_image_url": image_url,
            "result_video_url": video_url,
            "input_params": {
                "avatar_id": resolved_avatar_id,
                "language": resolved_language,
                "script": script,
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

    async def _get_from_db(
        self,
        tool_type: str,
        topic: Optional[str],
        product_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        query = select(Material).where(
            Material.tool_type == tool_type,
            Material.is_active == True,
            Material.status.in_([MaterialStatus.APPROVED, MaterialStatus.FEATURED]),
        )
        if topic:
            query = query.where(Material.topic == topic)
        if product_id:
            # For ai_avatar the input_params key is avatar_id; for other tools it's product_id.
            is_avatar = (
                tool_type == "ai_avatar"
                or (hasattr(tool_type, "value") and tool_type.value == "ai_avatar")
            )
            key = "avatar_id" if is_avatar else "product_id"
            query = query.where(Material.input_params[key].astext == product_id)
        if language:
            query = query.where(Material.language == language)
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
