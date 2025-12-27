"""
Pollo AI API Client
Image-to-Video generation using Pollo AI's API platform.
Supports multiple models: Kling AI, Pixverse, Luma, etc.
API Docs: https://docs.pollo.ai/
"""
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
import httpx
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Available I2V models on Pollo AI
POLLO_MODELS = {
    "pixverse_v4.5": {
        "endpoint": "/generation/pixverse/pixverse-v4-5",
        "name": "Pixverse 4.5",
        "description": "Fast and affordable, good quality",
        "lengths": [5, 8]  # Only 5 or 8 seconds supported
    },
    "pixverse_v5": {
        "endpoint": "/generation/pixverse/pixverse-v5",
        "name": "Pixverse 5.0",
        "description": "Creative animations",
        "lengths": [5, 8]
    },
    "kling_v2": {
        "endpoint": "/generation/kling-ai/kling-v2",
        "name": "Kling AI 2.0",
        "description": "High quality, lifelike movements",
        "lengths": [5, 10]
    },
    "kling_v1.5": {
        "endpoint": "/generation/kling-ai/kling-v1-5",
        "name": "Kling AI 1.5",
        "description": "Fast generation, good quality",
        "lengths": [5, 10]
    },
    "luma_ray2": {
        "endpoint": "/generation/luma/luma-ray-2-0",
        "name": "Luma Ray 2.0",
        "description": "Cinematic quality",
        "lengths": [5, 10]
    },
}


class PolloAIClient:
    """Pollo AI API Client for Image-to-Video generation"""

    BASE_URL = "https://pollo.ai/api/platform"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'POLLO_API_KEY', '')
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }

    async def generate_video(
        self,
        image_url: str,
        prompt: str,
        model: str = "pixverse_v4.5",
        negative_prompt: str = "blurry, distorted, low quality, jerky motion",
        length: int = 5
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Generate video from image.

        Args:
            image_url: URL of the source image (must be publicly accessible HTTPS URL)
            prompt: Motion/animation description
            model: Model to use (default: pixverse_v4.5 - cheapest option)
            negative_prompt: What to avoid
            length: Video length in seconds (5 or 8 for Pixverse)

        Returns:
            Tuple of (success, task_id or error, None)
        """
        if not self.api_key:
            return False, "Pollo API key not configured", None

        model_info = POLLO_MODELS.get(model, POLLO_MODELS["pixverse_v4.5"])
        endpoint = model_info["endpoint"]

        # Validate and adjust length to supported values
        valid_lengths = model_info.get("lengths", [5, 8])
        if length not in valid_lengths:
            length = valid_lengths[0]  # Default to shortest

        payload = {
            "input": {
                "image": image_url,
                "prompt": f"{prompt}, smooth motion, cinematic",
                "negativePrompt": negative_prompt,
                "length": length
            }
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}{endpoint}",
                    headers=self.headers,
                    json=payload
                )

                logger.info(f"Pollo API response status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Pollo API response: {data}")

                    if data.get("code") == "SUCCESS":
                        task_id = data["data"]["taskId"]
                        logger.info(f"Pollo I2V task created: {task_id}")
                        return True, task_id, None
                    else:
                        error = data.get("message", "Unknown error")
                        logger.error(f"Pollo API error: {error}")
                        return False, error, None
                else:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"Pollo API error: {error}")
                    return False, error, None

        except Exception as e:
            logger.error(f"Pollo API error: {e}")
            return False, str(e), None

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Check task status using the correct Pollo API endpoint.

        Returns:
            Dict with status, video_url when complete
            Status values: "pending", "processing", "succeed", "failed"
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/generation/{task_id}/status",
                    headers=self.headers
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"Pollo status response: {data}")

                    # Status is in generations[0]
                    generations = data.get("data", {}).get("generations", [])
                    if generations:
                        gen = generations[0]
                        task_status = gen.get("status", "unknown")
                        video_url = gen.get("url", "")
                        fail_msg = gen.get("failMsg", "")

                        return {
                            "success": True,
                            "status": task_status,
                            "video_url": video_url if video_url else None,
                            "error": fail_msg if fail_msg else None,
                            "raw": data
                        }

                    # No generations yet, still processing
                    return {
                        "success": True,
                        "status": "pending",
                        "video_url": None
                    }
                else:
                    logger.error(f"Status check failed: {response.status_code}")
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
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """
        Wait for task completion with polling.

        Args:
            task_id: Task ID from generate_video
            timeout: Max wait time in seconds (default 5 min for video generation)
            poll_interval: Seconds between status checks

        Returns:
            Final task status with video_url
        """
        elapsed = 0
        logger.info(f"Waiting for Pollo task {task_id} (timeout: {timeout}s)")

        while elapsed < timeout:
            status = await self.get_task_status(task_id)
            task_status = status.get("status", "").lower()

            logger.info(f"Task {task_id}: {task_status} ({elapsed}s elapsed)")

            if task_status == "succeed":
                logger.info(f"Task {task_id} completed successfully")
                return status
            elif task_status == "failed":
                error_msg = status.get("error", "Unknown error")
                logger.error(f"Task {task_id} failed: {error_msg}")
                return status

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        logger.error(f"Task {task_id} timed out after {timeout}s")
        return {"success": False, "status": "timeout", "error": "Task timed out"}

    async def generate_and_wait(
        self,
        image_url: str,
        prompt: str,
        model: str = "pixverse_v4.5",
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Generate video and wait for completion.

        Args:
            image_url: Source image URL (must be publicly accessible HTTPS)
            prompt: Animation prompt
            model: Model to use (default: pixverse_v4.5 - cheapest)
            timeout: Max wait time in seconds

        Returns:
            Dict with video_url on success
        """
        logger.info(f"Starting I2V generation with {model}")
        logger.info(f"Image URL: {image_url}")
        logger.info(f"Prompt: {prompt}")

        success, task_id, _ = await self.generate_video(
            image_url=image_url,
            prompt=prompt,
            model=model
        )

        if not success:
            return {"success": False, "error": task_id}

        result = await self.wait_for_completion(task_id, timeout)

        if result.get("status") == "succeed":
            return {
                "success": True,
                "task_id": task_id,
                "video_url": result.get("video_url"),
                "model": model,
                "model_name": POLLO_MODELS.get(model, {}).get("name", model)
            }
        else:
            return {
                "success": False,
                "task_id": task_id,
                "error": result.get("error", "Generation failed"),
                "model": model
            }


# Singleton instance
_pollo_client: Optional[PolloAIClient] = None


def get_pollo_client() -> PolloAIClient:
    """Get or create Pollo AI client singleton"""
    global _pollo_client
    if _pollo_client is None:
        _pollo_client = PolloAIClient()
    return _pollo_client
