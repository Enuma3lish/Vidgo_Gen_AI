"""
GoEnhance AI Service - Video-to-Video Style Transformation
With Redis caching for generated results
"""
import httpx
import asyncio
import hashlib
import json
from typing import Optional, Dict, Any, List
from datetime import timedelta
import redis.asyncio as redis
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

GOENHANCE_BASE_URL = "https://api.goenhance.ai/api/v1"


class GoEnhanceService:
    def __init__(self):
        self.api_key = settings.GOENHANCE_API_KEY
        self.redis: Optional[redis.Redis] = None
        self.cache_ttl = timedelta(hours=24)

    async def init_redis(self):
        """Initialize Redis connection"""
        if not self.redis:
            self.redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _cache_key(self, prefix: str, params: Dict) -> str:
        """Generate cache key from parameters"""
        param_str = json.dumps(params, sort_keys=True)
        hash_val = hashlib.md5(param_str.encode()).hexdigest()
        return f"goenhance:{prefix}:{hash_val}"

    async def _get_cached(self, key: str) -> Optional[Dict]:
        """Get cached result"""
        if not self.redis:
            await self.init_redis()
        try:
            cached = await self.redis.get(key)
            if cached:
                logger.info(f"Cache hit for {key}")
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None

    async def _set_cached(self, key: str, value: Dict):
        """Set cached result"""
        if not self.redis:
            await self.init_redis()
        try:
            await self.redis.setex(
                key,
                int(self.cache_ttl.total_seconds()),
                json.dumps(value)
            )
            logger.info(f"Cached result for {key}")
        except Exception as e:
            logger.error(f"Cache set error: {e}")

    async def get_model_list(self) -> Dict:
        """Get available video transformation models"""
        cache_key = "goenhance:models"
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GOENHANCE_BASE_URL}/video2video/modellist",
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 0:
                await self._set_cached(cache_key, data)
            return data

    async def get_popular_models(self) -> List[Dict]:
        """Get popular models for quick selection"""
        models = await self.get_model_list()
        popular = []

        if models.get("code") == 0:
            for category in models.get("data", []):
                if category.get("value") == "default":  # Popular category
                    for model in category.get("list", [])[:10]:
                        popular.append({
                            "id": model.get("value"),
                            "name": model.get("label"),
                            "version": model.get("version"),
                            "preview": model.get("url"),
                            "is_vip": model.get("isVip", False)
                        })
                    break

        return popular

    async def video_to_video(
        self,
        video_url: str,
        model_id: int = 2000,  # Default: Anime Style v5
        prompt: str = "",
        use_cache: bool = True
    ) -> Dict:
        """
        Transform video using style model - USES CORRECT GoEnhance API

        Verified model IDs (from effects_service.py):
        - 2000: Anime Style (v5)
        - 1033: GPT Anime Style (Ghibli-like, v4)
        - 2005: Clay Style (v5)
        - 2004: Pixar Style (v5)
        - 2006: Oil Painting (v5)
        - 2007: Watercolor (v5)
        - 2008: Cyberpunk (v5)
        - 2010: Cinematic (v5)
        """
        params = {
            "video_url": video_url,
            "model_id": model_id,
            "prompt": prompt
        }

        if use_cache:
            cache_key = self._cache_key("v2v", params)
            cached = await self._get_cached(cache_key)
            if cached:
                return cached

        async with httpx.AsyncClient(timeout=300.0) as client:
            # CORRECT API format: /video2video/generate with reference_video_url
            payload = {
                "args": {
                    "model": model_id,
                    "duration": 5,
                    "reference_video_url": video_url,  # KEY: use reference_video_url to transform INPUT
                    "seed": -1,
                    "resolution": "720p"
                },
                "type": "mx-v2v"
            }

            if prompt:
                payload["args"]["prompt"] = prompt[:500]

            logger.info(f"GoEnhance V2V request: model={model_id}, video={video_url[:50]}...")

            response = await client.post(
                f"{GOENHANCE_BASE_URL}/video2video/generate",  # CORRECT endpoint
                headers=self._get_headers(),
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                logger.error(f"GoEnhance V2V failed: {data}")
                return {
                    "success": False,
                    "error": data.get("msg", "Failed to start transformation")
                }

            # Task ID is in img_uuid for this endpoint
            task_id = data.get("data", {}).get("img_uuid") or data.get("data", {}).get("task_id")
            if task_id:
                result = await self._poll_task_v2(client, task_id)  # Use new polling method
                if use_cache and result.get("success"):
                    await self._set_cached(cache_key, result)
                return result

            return {"success": False, "error": "No task ID returned"}

    async def image_to_video(
        self,
        image_url: str,
        model_id: int = 2000,
        prompt: str = "",
        duration: int = 4,
        use_cache: bool = True
    ) -> Dict:
        """
        Convert image to animated video with style

        duration: Video length in seconds (2-8)
        """
        params = {
            "image_url": image_url,
            "model_id": model_id,
            "prompt": prompt,
            "duration": duration
        }

        if use_cache:
            cache_key = self._cache_key("i2v", params)
            cached = await self._get_cached(cache_key)
            if cached:
                return cached

        async with httpx.AsyncClient(timeout=300.0) as client:
            payload = {
                "image_url": image_url,
                "model": model_id,
                "prompt": prompt or "smooth animation, high quality",
                "duration": min(max(duration, 2), 8)
            }

            response = await client.post(
                f"{GOENHANCE_BASE_URL}/image2video",
                headers=self._get_headers(),
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                return {
                    "success": False,
                    "error": data.get("msg", "Failed to start generation")
                }

            task_id = data.get("data", {}).get("task_id")
            if task_id:
                result = await self._poll_task(client, task_id)
                if use_cache and result.get("success"):
                    await self._set_cached(cache_key, result)
                return result

            return {"success": False, "error": "No task ID returned"}

    async def _poll_task(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        max_attempts: int = 180,
        interval: float = 5.0
    ) -> Dict:
        """Poll for task completion (legacy endpoint)"""
        for attempt in range(max_attempts):
            try:
                response = await client.get(
                    f"{GOENHANCE_BASE_URL}/task/{task_id}",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()

                if data.get("code") != 0:
                    await asyncio.sleep(interval)
                    continue

                task_data = data.get("data", {})
                status = task_data.get("status")

                if status == "completed":
                    return {
                        "success": True,
                        "task_id": task_id,
                        "video_url": task_data.get("video_url"),
                        "thumbnail_url": task_data.get("thumbnail_url"),
                        "duration": task_data.get("duration")
                    }
                elif status == "failed":
                    return {
                        "success": False,
                        "error": task_data.get("error", "Task failed")
                    }
                elif status in ["pending", "processing"]:
                    logger.info(f"Task {task_id} status: {status} (attempt {attempt + 1})")
                    await asyncio.sleep(interval)
                else:
                    await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Poll error: {e}")
                await asyncio.sleep(interval)

        return {"success": False, "error": "Task timeout"}

    async def _poll_task_v2(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        max_attempts: int = 180,
        interval: float = 5.0
    ) -> Dict:
        """Poll for task completion using /jobs/detail endpoint (for V2V generate API)"""
        for attempt in range(max_attempts):
            try:
                response = await client.get(
                    f"{GOENHANCE_BASE_URL}/jobs/detail",
                    params={"img_uuid": task_id},
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()

                job_data = data.get("data", {})
                status = job_data.get("status", "unknown")

                # Response format: json field contains array with video info
                # Example: {"json": [{"type": "video", "value": "https://...", "duration": 196.629}]}
                json_results = job_data.get("json", [])

                if status == "completed" or status == "success":
                    # Extract video URL from json array
                    video_url = None
                    thumbnail_url = None
                    duration = None

                    if json_results and len(json_results) > 0:
                        first_result = json_results[0]
                        if isinstance(first_result, dict):
                            video_url = first_result.get("value")
                            duration = first_result.get("duration")

                    # Fallback to output format (for legacy compatibility)
                    if not video_url:
                        output = job_data.get("output", {})
                        video_url = output.get("video_url")
                        thumbnail_url = output.get("thumbnail_url")

                    logger.info(f"V2V task {task_id} completed: {video_url}")
                    return {
                        "success": True,
                        "task_id": task_id,
                        "video_url": video_url,
                        "thumbnail_url": thumbnail_url,
                        "duration": duration
                    }
                elif status == "failed" or status == "error":
                    return {
                        "success": False,
                        "error": job_data.get("error", "Task failed")
                    }
                elif status in ["pending", "processing", "queued"]:
                    progress = job_data.get("progress", 0)
                    logger.info(f"V2V task {task_id} status: {status}, progress: {progress}% (attempt {attempt + 1})")
                    await asyncio.sleep(interval)
                else:
                    await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Poll V2 error: {e}")
                await asyncio.sleep(interval)

        return {"success": False, "error": "Task timeout"}

    async def face_swap(
        self,
        source_image_url: str,
        target_image_url: str,
        use_cache: bool = True
    ) -> Dict:
        """
        Swap face from source to target image
        """
        params = {
            "source": source_image_url,
            "target": target_image_url,
            "action": "face_swap"
        }

        if use_cache:
            cache_key = self._cache_key("faceswap", params)
            cached = await self._get_cached(cache_key)
            if cached:
                return cached

        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "source_image_url": source_image_url,
                "target_image_url": target_image_url
            }

            response = await client.post(
                f"{GOENHANCE_BASE_URL}/faceswap",
                headers=self._get_headers(),
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                return {
                    "success": False,
                    "error": data.get("msg", "Face swap failed")
                }

            task_id = data.get("data", {}).get("task_id")
            if task_id:
                result = await self._poll_task(client, task_id)
                if use_cache and result.get("success"):
                    await self._set_cached(cache_key, result)
                return result

            return {"success": False, "error": "No task ID returned"}


# Singleton instance
goenhance_service = GoEnhanceService()


# Style model mapping - VERIFIED from GoEnhance API /video2video/modellist
# These IDs match effects_service.py VIDGO_STYLES
STYLE_MODELS = {
    # Artistic Styles
    "anime": {"id": 2000, "name": "Anime Style", "version": "v5"},
    "ghibli": {"id": 1033, "name": "GPT Anime Style (Ghibli)", "version": "v4"},  # FIXED: was 2002
    "cartoon": {"id": 2004, "name": "Pixar Style", "version": "v5"},
    "clay": {"id": 2005, "name": "Clay Style", "version": "v5"},  # FIXED: was 2003
    "cute_anime": {"id": 5, "name": "Cute Anime Style", "version": "v1"},
    "oil_painting": {"id": 2006, "name": "Oil Painting", "version": "v5"},
    "watercolor": {"id": 2007, "name": "Watercolor", "version": "v5"},

    # Modern Styles
    "cyberpunk": {"id": 2008, "name": "Cyberpunk", "version": "v5"},
    "realistic": {"id": 2009, "name": "Realistic", "version": "v5"},

    # Professional Styles
    "cinematic": {"id": 2010, "name": "Cinematic", "version": "v5"},  # FIXED: was 1016
    "anime_classic": {"id": 1016, "name": "Anime Style 3", "version": "v4"},
}
