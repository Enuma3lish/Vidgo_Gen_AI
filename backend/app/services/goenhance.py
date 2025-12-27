"""
GoEnhance AI API Client
- Nano Banana: Text-to-Image generation
- Video-to-Video: Style transformation
API Docs: https://docs.goenhance.ai/
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any, Tuple
import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Available GoEnhance V2V styles (from API modellist)
GOENHANCE_STYLES = {
    # Popular styles
    1016: {"name": "Anime Style 3", "slug": "anime_v4", "version": "v4"},
    1033: {"name": "GPT Anime Style", "slug": "gpt_anime", "version": "v4"},
    5: {"name": "Cute Anime Style", "slug": "cute_anime", "version": "v1"},
    2: {"name": "Anime Style 2", "slug": "anime_v1", "version": "v1"},
    2000: {"name": "Anime Style", "slug": "anime_v5", "version": "v5"},
    2004: {"name": "Pixar Style", "slug": "pixar", "version": "v5"},
    2005: {"name": "Clay Style", "slug": "clay", "version": "v5"},
    2006: {"name": "Oil Painting", "slug": "oil_painting", "version": "v5"},
    2007: {"name": "Watercolor", "slug": "watercolor", "version": "v5"},
    2008: {"name": "Cyberpunk", "slug": "cyberpunk", "version": "v5"},
    2009: {"name": "Realistic", "slug": "realistic", "version": "v5"},
    2010: {"name": "Cinematic", "slug": "cinematic", "version": "v5"},
}


class GoEnhanceClient:
    """
    GoEnhance AI API Client

    Supports:
    - Nano Banana: Text-to-Image generation
    - Video-to-Video: Style transformation
    """

    BASE_URL = "https://api.goenhance.ai/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'GOENHANCE_API_KEY', '')
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    # =========================================================================
    # Nano Banana - Text-to-Image Generation
    # =========================================================================

    async def generate_image(
        self,
        prompt: str,
        style: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Generate image from text prompt using Nano Banana API.

        Args:
            prompt: Text description of the image to generate
            style: Optional style modifier to append to prompt

        Returns:
            Tuple of (success, task_id or error, None)
        """
        if not self.api_key:
            return False, "GoEnhance API key not configured", None

        # Build prompt with style
        full_prompt = prompt
        if style:
            full_prompt = f"{prompt}, {style} style, high quality, detailed"

        payload = {
            "args": {
                "prompt": full_prompt
            }
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/nano-banana",
                    headers=self.headers,
                    json=payload
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        task_id = data["data"]["img_uuid"]
                        cost = data["data"].get("cost", 0)
                        logger.info(f"Nano Banana task created: {task_id} (cost: {cost})")
                        return True, task_id, None
                    else:
                        error_msg = data.get("msg", "Unknown error")
                        logger.error(f"Nano Banana failed: {error_msg}")
                        return False, error_msg, None
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"Nano Banana request failed: {error_msg}")
                    return False, error_msg, None

        except Exception as e:
            logger.error(f"Nano Banana error: {e}")
            return False, str(e), None

    async def get_image_result(self, task_id: str) -> Dict[str, Any]:
        """
        Get image generation result.

        Returns:
            Dict with status, image_url when complete
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/jobs/detail",
                    params={"img_uuid": task_id},
                    headers=self.headers
                )

                if response.status_code == 200:
                    data = response.json()
                    job_data = data.get("data", {})
                    status = job_data.get("status", "unknown")

                    # Image URL is in json array
                    image_url = None
                    json_data = job_data.get("json", [])
                    if json_data and len(json_data) > 0:
                        image_url = json_data[0].get("value")

                    return {
                        "success": True,
                        "status": status,
                        "image_url": image_url,
                        "raw": job_data
                    }
                else:
                    return {
                        "success": False,
                        "status": "error",
                        "error": f"HTTP {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Get image result error: {e}")
            return {"success": False, "status": "error", "error": str(e)}

    async def generate_image_and_wait(
        self,
        prompt: str,
        style: Optional[str] = None,
        timeout: int = 120,
        poll_interval: int = 3
    ) -> Dict[str, Any]:
        """
        Generate image and wait for completion.

        Args:
            prompt: Text prompt
            style: Optional style
            timeout: Max wait time in seconds
            poll_interval: Seconds between status checks

        Returns:
            Dict with image_url on success
        """
        success, task_id, _ = await self.generate_image(prompt, style)

        if not success:
            return {"success": False, "error": task_id}

        elapsed = 0
        while elapsed < timeout:
            result = await self.get_image_result(task_id)

            if result.get("status") == "success":
                return {
                    "success": True,
                    "task_id": task_id,
                    "image_url": result.get("image_url"),
                    "prompt": prompt,
                    "style": style
                }
            elif result.get("status") == "failed":
                return {
                    "success": False,
                    "task_id": task_id,
                    "error": "Image generation failed"
                }

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return {"success": False, "task_id": task_id, "error": "Image generation timed out"}

    # =========================================================================
    # Video-to-Video Style Transformation
    # =========================================================================

    async def get_model_list(self) -> List[Dict[str, Any]]:
        """Get available V2V models/styles"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/video2video/modellist",
                headers=self.headers
            )

            if response.status_code == 200:
                data = response.json()
                models = []
                for category in data.get("data", []):
                    for model in category.get("list", []):
                        models.append({
                            "id": model.get("value"),
                            "name": model.get("label"),
                            "version": model.get("version"),
                            "is_vip": model.get("isVip", False),
                            "thumbnail": model.get("url"),
                            "category": category.get("label")
                        })
                return models
            else:
                logger.error(f"Failed to get model list: {response.status_code}")
                return []

    async def generate_v2v(
        self,
        video_url: str,
        model_id: int = 2000,
        duration: int = 5,
        seed: int = -1,
        prompt: Optional[str] = None,
        resolution: str = "720p"
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Generate video-to-video transformation.

        Args:
            video_url: Source video URL (HTTPS, MP4/MOV, max 50MB)
            model_id: Style model ID from GOENHANCE_STYLES
            duration: Output duration in seconds (3-30)
            seed: Random seed (-1 for random)
            prompt: Optional text prompt
            resolution: "540p" or "720p"

        Returns:
            Tuple of (success, task_id or error, None)
        """
        payload = {
            "args": {
                "model": model_id,
                "duration": min(max(duration, 3), 30),
                "reference_video_url": video_url,
                "seed": seed,
                "resolution": resolution
            },
            "type": "mx-v2v"
        }

        if prompt:
            payload["args"]["prompt"] = prompt[:500]

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/video2video/generate",
                    headers=self.headers,
                    json=payload
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        task_id = data.get("data", {}).get("img_uuid")
                        logger.info(f"V2V task created: {task_id}")
                        return True, task_id, None
                    else:
                        error_msg = data.get("msg", "Unknown error")
                        logger.error(f"V2V generation failed: {error_msg}")
                        return False, error_msg, None
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"V2V request failed: {error_msg}")
                    return False, error_msg, None

        except Exception as e:
            logger.error(f"GoEnhance V2V error: {e}")
            return False, str(e), None

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Check task status and get result.

        Returns:
            Dict with status, video_url, thumbnail_url when complete
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/jobs/detail",
                    params={"img_uuid": task_id},
                    headers=self.headers
                )

                if response.status_code == 200:
                    data = response.json()
                    job_data = data.get("data", {})
                    output = job_data.get("output", {})

                    return {
                        "success": True,
                        "status": job_data.get("status", "unknown"),
                        "progress": job_data.get("progress", 0),
                        "video_url": output.get("video_url"),
                        "thumbnail_url": output.get("thumbnail_url"),
                        "raw": data
                    }
                else:
                    return {
                        "success": False,
                        "status": "error",
                        "error": f"HTTP {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Task status error: {e}")
            return {"success": False, "status": "error", "error": str(e)}

    async def wait_for_v2v_completion(
        self,
        task_id: str,
        timeout: int = 300,
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """
        Wait for V2V task to complete.

        Returns:
            Final task status with video_url and thumbnail_url
        """
        elapsed = 0
        while elapsed < timeout:
            status = await self.get_task_status(task_id)

            if status.get("status") == "completed":
                logger.info(f"V2V task {task_id} completed")
                return status
            elif status.get("status") in ["failed", "error"]:
                logger.error(f"V2V task {task_id} failed: {status}")
                return status

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return {"success": False, "status": "timeout", "error": "Task timed out"}

    async def enhance_video(
        self,
        video_url: str,
        model_id: int = 2000,
        prompt: Optional[str] = None,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Enhance video with style transformation and wait for completion.

        Args:
            video_url: Source video URL
            model_id: Style model ID
            prompt: Optional prompt
            timeout: Max wait time

        Returns:
            Dict with video_url on success
        """
        style_info = GOENHANCE_STYLES.get(model_id, {})

        success, task_id, _ = await self.generate_v2v(
            video_url=video_url,
            model_id=model_id,
            duration=5,
            prompt=prompt,
            resolution="720p"
        )

        if not success:
            return {
                "success": False,
                "error": task_id,
                "style_id": model_id,
                "style_name": style_info.get("name"),
                "style_slug": style_info.get("slug")
            }

        result = await self.wait_for_v2v_completion(task_id, timeout)

        if result.get("status") == "completed":
            return {
                "success": True,
                "task_id": task_id,
                "video_url": result.get("video_url"),
                "thumbnail_url": result.get("thumbnail_url"),
                "style_id": model_id,
                "style_name": style_info.get("name"),
                "style_slug": style_info.get("slug")
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Enhancement failed"),
                "task_id": task_id,
                "style_id": model_id,
                "style_name": style_info.get("name"),
                "style_slug": style_info.get("slug")
            }

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def get_credits(self) -> Dict[str, Any]:
        """Get current token/credit balance"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/user/tokens",
                    headers=self.headers
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "credits": data.get("data", {}).get("count", 0),
                        "queue_limit": data.get("data", {}).get("queueLimit", 3),
                        "user_id": data.get("data", {}).get("user_id")
                    }
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton instance
_goenhance_client: Optional[GoEnhanceClient] = None


def get_goenhance_client() -> GoEnhanceClient:
    """Get or create GoEnhance client singleton"""
    global _goenhance_client
    if _goenhance_client is None:
        _goenhance_client = GoEnhanceClient()
    return _goenhance_client
