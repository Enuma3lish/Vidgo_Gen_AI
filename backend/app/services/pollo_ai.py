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
from app.core.model_registry import POLLO_MODELS as _POLLO_REG

logger = logging.getLogger(__name__)
settings = get_settings()

# Default model when caller omits ``model`` (env-overridable via
# POLLO_PIXVERSE_DEFAULT_MODEL — see app/core/model_registry.py).
DEFAULT_MODEL = _POLLO_REG["pixverse_default"]


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
    # Pollo's own model — supports BOTH text-to-video and image-to-video
    # (verified body shape against docs.pollo.ai 2026-06-23). Used as the
    # default endpoint for the text_to_video backup path.
    "pollo-v1-6": {
        "endpoint": "/generation/pollo/pollo-v1-6",
        "name": "Pollo 1.6",
        "description": "Pollo's own T2V/I2V model",
        "lengths": [5, 8]
    },
    # ── New tier (2026-05-19) — Pollo as backup to PiAPI on these models.
    # Endpoint slugs follow Pollo's documented pattern /generation/<vendor>/<slug>.
    # If Pollo renames any of these we rotate via the env vars in
    # core/model_registry.py — code stays unchanged.
    # 2026-06-23: verified slugs against docs.pollo.ai. The prior
    # /generation/seedance/seedance-2-fast and /generation/minimax/hailuo-fast
    # 404'd in prod — Pollo's actual vendor prefix is `bytedance` for Seedance
    # and the Hailuo Fast slug is the explicit version (minimax-hailuo-2.3-fast).
    "seedance_v2": {
        "endpoint": "/generation/bytedance/seedance-2-0-fast",
        "name": "Seedance 2.0 Fast",
        "description": "Best CP value / stable / high-success default (480p/720p)",
        "lengths": [5, 10]
    },
    # Full Seedance 2.0 task — needed for 1080p. Frontend's seedance_1080p
    # routes here; the -fast variant tops out at 720p.
    "seedance_2_0": {
        "endpoint": "/generation/bytedance/seedance-2-0",
        "name": "Seedance 2.0",
        "description": "Full Seedance (supports 1080p)",
        "lengths": [5, 10]
    },
    "hailuo_fast": {
        "endpoint": "/generation/minimax/minimax-hailuo-2.3-fast",
        "name": "Hailuo Fast",
        "description": "Cheapest, fastest tier",
        # Pollo's hailuo-2.3-fast accepts ONLY 6 or 10 seconds (verified
        # 2026-06-23). Was [5,6]; 5 → 6 via _normalize_length.
        "lengths": [6, 10]
    },
    # Hunyuan removed 2026-06-23: NOT in Pollo's catalog. Was 404ing every
    # call in prod (`/generation/hunyuan/hunyuan-v1` doesn't exist). With no
    # Pollo backup and PiAPI's Qubico/hunyuan rejecting our payload, the model
    # is being removed from the user-facing menu in frontend ShortVideo.vue.
    "kling_v3": {
        "endpoint": "/generation/kling-ai/kling-v3",
        "name": "Kling AI 3.0 / Omni",
        "description": "Premium tier — top quality + audio",
        "lengths": [5, 10]
    },
    # OpenAI Sora 2 via Pollo's unified platform (2026-06-09). Used as the
    # backup when the PiAPI Sora 2 lane errors / rate-limits. Pollo accepts
    # the same input.image + input.prompt shape as the rest of the table, so
    # the existing generate_video() flow handles it without a code branch.
    "sora-2": {
        "endpoint": "/generation/sora/sora-2",
        "name": "OpenAI Sora 2",
        "description": "Photorealistic motion, synchronized audio (flagship)",
        # 2026-06-12 fix: Pollo's sora-2 validates length against this enum
        # (it rejected our 5 with options [4,8,12,16,20]); _normalize_length
        # snaps requests to the nearest allowed value.
        "lengths": [4, 8, 12, 16, 20]
    },
}


# ── Pollo IMAGE models (text-to-image + image-to-image) ──────────────────────
# Endpoint pattern (verified against docs.pollo.ai 2026-06-23):
#   POST /generation/<vendor>/<slug>/image
#   body {"input": {"prompt", "aspectRatio", "resolution", ["imageUrl"|"images"]}}
#   resp {"taskId", "status"}  (status polled via the SAME /generation/{id}/status)
# nano-banana-2 is the safe default (T2I + I2I both verified end-to-end). The
# other slugs are env-overridable so ops can rotate without a rebuild; the
# provider normalizer falls back to the default for any unknown model so the
# image backup never hard-fails on an unverified slug.
POLLO_IMAGE_MODELS = {
    "nano_banana_2": {
        "endpoint": "/generation/google/nano-banana-2/image",
        "name": "Nano Banana 2",
        "resolutions": ["1K", "2K", "4K"],
    },
    "nano_banana_pro": {
        "endpoint": "/generation/google/nano-banana-pro/image",
        "name": "Nano Banana Pro",
        "resolutions": ["1K", "2K", "4K"],
    },
    "gpt_image_2": {
        "endpoint": "/generation/openai/gpt-image-2-0/image",
        "name": "GPT Image 2",
        "resolutions": ["1K", "2K", "4K"],
    },
    "seedream_5_lite": {
        "endpoint": "/generation/seedream/seedream-5-0-lite/image",
        "name": "Seedream 5.0 Lite",
        "resolutions": ["1K", "2K", "4K"],
    },
    "pollojourney": {
        "endpoint": "/generation/pollo/pollojourney/image",
        "name": "Pollojourney",
        "resolutions": ["1K", "2K"],
    },
}

DEFAULT_IMAGE_MODEL = "nano_banana_2"


class PolloAIClient:
    """Pollo AI API Client — image-to-video, text-to-image, image-to-image, text-to-video."""

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
        model: str = DEFAULT_MODEL,
        negative_prompt: str = "blurry, distorted, low quality, jerky motion",
        length: int = 5,
        aspect_ratio: Optional[str] = None,
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

        model_info = POLLO_MODELS.get(model, POLLO_MODELS[DEFAULT_MODEL])
        endpoint = model_info["endpoint"]

        # Validate and adjust length to supported values
        valid_lengths = model_info.get("lengths", [5, 8])
        if length not in valid_lengths:
            length = valid_lengths[0]  # Default to shortest

        _input = {
            "image": image_url,
            "prompt": f"{prompt}, smooth motion, cinematic",
            "negativePrompt": negative_prompt,
            "length": length
        }
        # Forward the requested aspect ratio when the caller supplied one (the
        # Kling/Sora I2V backup path passes 9:16 / 1:1 etc.); omit it otherwise
        # so Pollo keeps its per-model default.
        if aspect_ratio:
            _input["aspectRatio"] = aspect_ratio
        payload = {"input": _input}

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

    async def _create_task(
        self,
        endpoint: str,
        input_payload: Dict[str, Any],
        timeout: float = 60.0,
    ) -> Tuple[bool, str, Optional[str]]:
        """POST a generation task to any Pollo per-model endpoint.

        Shared by image / text-to-video / (future) paths. Parses the taskId
        defensively because Pollo returns it either at the root ({"taskId": …})
        or wrapped ({"code": "SUCCESS", "data": {"taskId": …}}) depending on the
        model family. Returns (success, task_id_or_error, None).
        """
        if not self.api_key:
            return False, "Pollo API key not configured", None

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.BASE_URL}{endpoint}",
                    headers=self.headers,
                    json={"input": input_payload},
                )

                if response.status_code != 200:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"Pollo create-task error ({endpoint}): {error}")
                    return False, error, None

                data = response.json()
                logger.info(f"Pollo create-task response ({endpoint}): {data}")

                code = data.get("code")
                if code is not None and code != "SUCCESS":
                    return False, data.get("message", "Unknown error"), None

                task_id = (data.get("data") or {}).get("taskId") or data.get("taskId")
                if not task_id:
                    return False, data.get("message", "Pollo returned no taskId"), None
                return True, task_id, None
        except Exception as e:
            logger.error(f"Pollo create-task exception ({endpoint}): {e}")
            return False, str(e), None

    async def generate_image(
        self,
        prompt: str,
        endpoint: str,
        aspect_ratio: str = "1:1",
        resolution: str = "1K",
        image_url: Optional[str] = None,
        images: Optional[list] = None,
        timeout: int = 600,
    ) -> Dict[str, Any]:
        """Text-to-image (no image) or image-to-image (imageUrl/images) via Pollo.

        Returns {"success", "image_url"} on success. Reuses the shared status
        poller — the completed task's media URL lands in generations[0].url.
        """
        input_payload: Dict[str, Any] = {
            "prompt": prompt or "",
            "aspectRatio": aspect_ratio or "1:1",
            "resolution": resolution or "1K",
        }
        if images:
            input_payload["images"] = images
        elif image_url:
            input_payload["imageUrl"] = image_url

        success, task_id, _ = await self._create_task(endpoint, input_payload)
        if not success:
            return {"success": False, "error": task_id}

        result = await self.wait_for_completion(task_id, timeout=timeout)
        if (result.get("status") or "").lower() == "succeed" and result.get("media_url"):
            return {"success": True, "task_id": task_id, "image_url": result["media_url"]}
        return {
            "success": False,
            "task_id": task_id,
            "error": result.get("error") or f"Pollo image task ended with status={result.get('status')}",
        }

    async def generate_text_to_video(
        self,
        prompt: str,
        endpoint: str,
        resolution: str = "720p",
        length: int = 5,
        aspect_ratio: str = "16:9",
        timeout: int = 1200,
    ) -> Dict[str, Any]:
        """Pure text-to-video (no source image) via a Pollo per-model endpoint."""
        input_payload = {
            "prompt": prompt or "",
            "resolution": resolution or "720p",
            "length": length,
            "aspectRatio": aspect_ratio or "16:9",
        }
        success, task_id, _ = await self._create_task(endpoint, input_payload)
        if not success:
            return {"success": False, "error": task_id}

        result = await self.wait_for_completion(task_id, timeout=timeout)
        if (result.get("status") or "").lower() == "succeed" and result.get("media_url"):
            return {"success": True, "task_id": task_id, "video_url": result["media_url"]}
        return {
            "success": False,
            "task_id": task_id,
            "error": result.get("error") or f"Pollo T2V task ended with status={result.get('status')}",
        }

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Check task status using the correct Pollo API endpoint.

        Returns:
            Dict with status, media_url/video_url when complete
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
                        media_url = gen.get("url", "")
                        fail_msg = gen.get("failMsg", "")

                        return {
                            "success": True,
                            "status": task_status,
                            # media_url is modality-agnostic (image OR video);
                            # video_url kept for backward-compat with I2V callers.
                            "media_url": media_url if media_url else None,
                            "media_type": gen.get("mediaType"),
                            "video_url": media_url if media_url else None,
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
        timeout: int = 1200,
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """
        Wait for task completion with polling.

        Args:
            task_id: Task ID from generate_video
            timeout: Max wait time in seconds (default 20 min — short-video
                jobs on Kling / Seedance / Wan can idle 8-15 min before
                yielding a video; lower defaults aborted healthy renders)
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
        model: str = DEFAULT_MODEL,
        timeout: int = 1200
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
