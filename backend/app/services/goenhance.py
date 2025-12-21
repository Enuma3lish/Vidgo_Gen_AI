"""
GoEnhance AI API Client
Video-to-Video style transformation
API Docs: https://docs.goenhance.ai/

For image demos, we use short video transformations and capture frames.
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
    """GoEnhance AI API Client for video/image transformation"""

    BASE_URL = "https://api.goenhance.ai/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GOENHANCE_API_KEY
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    async def get_model_list(self) -> List[Dict[str, Any]]:
        """Get available V2V models/styles"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/video2video/modellist",
                headers=self.headers
            )

            if response.status_code == 200:
                data = response.json()
                # Flatten the nested structure
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
        duration: int = 3,
        seed: int = -1,
        prompt: Optional[str] = None,
        resolution: str = "720p"
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Generate video-to-video transformation.
        For image demos, use short duration (3 sec) and capture frames.

        Args:
            video_url: Source video URL (HTTPS, MP4/MOV, max 50MB)
            model_id: Style model ID from GOENHANCE_STYLES
            duration: Output duration in seconds (3-30)
            seed: Random seed (-1 for random)
            prompt: Optional text prompt to modify content
            resolution: "540p" or "720p"

        Returns:
            Tuple of (success, task_id or error message, None)
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
            Dict with status, progress, video_url, and thumbnail_url when complete
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

    async def wait_for_completion(
        self,
        task_id: str,
        timeout: int = 300,
        poll_interval: int = 5,
        callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Wait for task to complete with polling.

        Args:
            task_id: Task ID from generate_v2v
            timeout: Max wait time in seconds
            poll_interval: Seconds between status checks
            callback: Optional callback function(status_dict) for progress updates

        Returns:
            Final task status with video_url and thumbnail_url
        """
        elapsed = 0
        while elapsed < timeout:
            status = await self.get_task_status(task_id)

            if callback:
                callback(status)

            if status.get("status") == "completed":
                logger.info(f"Task {task_id} completed successfully")
                return status
            elif status.get("status") in ["failed", "error"]:
                logger.error(f"Task {task_id} failed: {status}")
                return status

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            logger.debug(f"Task {task_id}: {status.get('status')} - {status.get('progress', 0)}%")

        return {"success": False, "status": "timeout", "error": "Task timed out"}

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

    async def generate_image_demo(
        self,
        source_video_url: str,
        model_id: int,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate an image demo by transforming a short video.
        Returns the video URL and thumbnail which can be used as before/after images.

        Args:
            source_video_url: Source video (3-5 seconds recommended)
            model_id: Style model ID
            prompt: Optional descriptive prompt

        Returns:
            Dict with video_url, thumbnail_url, and style info
        """
        style_info = GOENHANCE_STYLES.get(model_id, {})

        success, task_id, _ = await self.generate_v2v(
            video_url=source_video_url,
            model_id=model_id,
            duration=3,  # Short for demo
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

        # Wait for completion
        result = await self.wait_for_completion(task_id, timeout=180)

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
                "error": result.get("error", "Generation failed"),
                "task_id": task_id,
                "style_id": model_id,
                "style_name": style_info.get("name"),
                "style_slug": style_info.get("slug")
            }


# Singleton instance
_goenhance_client: Optional[GoEnhanceClient] = None


def get_goenhance_client() -> GoEnhanceClient:
    """Get or create GoEnhance client singleton"""
    global _goenhance_client
    if _goenhance_client is None:
        _goenhance_client = GoEnhanceClient()
    return _goenhance_client
