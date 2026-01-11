"""
Pollo.ai Provider - Backup provider for advanced features.

Supports:
- Multi-model generation (Kling, Hailuo, etc.)
- Keyframes mode
- Video effects
- Camera control
"""
import httpx
import asyncio
from typing import Dict, Any, Optional, List
import logging
import os

from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class PolloProvider(BaseProvider):
    """
    Pollo.ai Provider - Backup provider and advanced features.
    Used for keyframes, effects, multi-model selection.
    """

    name = "pollo"
    BASE_URL = "https://pollo.ai/api/platform"

    def __init__(self):
        self.api_key = os.getenv("POLLO_API_KEY", "")
        if not self.api_key:
            logger.warning("POLLO_API_KEY not set in environment")

        self.client = httpx.AsyncClient(
            timeout=300.0,
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
        )

    async def health_check(self) -> bool:
        """Check if Pollo.ai is healthy by checking credit balance."""
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/credit/balance",
                timeout=10.0
            )
            # Accept 200 or 401/403 (means API is reachable)
            return response.status_code in [200, 401, 403]
        except Exception as e:
            logger.error(f"Pollo.ai health check failed: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # GENERATION METHODS
    # ─────────────────────────────────────────────────────────────────────────

    async def generate(self, task_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generic generation method for T2I, I2V, T2V.

        Args:
            task_type: "text_to_image", "image_to_video", "text_to_video"
            params: Task-specific parameters

        Returns:
            {"success": True, "output": {...}}
        """
        self._log_request(task_type, params)

        endpoint_map = {
            "text_to_image": "/generate/image",
            "image_to_video": "/generate/video",
            "text_to_video": "/generate/video"
        }

        endpoint = endpoint_map.get(task_type)
        if not endpoint:
            raise ValueError(f"Unknown task type: {task_type}")

        payload = self._build_payload(task_type, params)
        return await self._submit_and_poll(endpoint, payload)

    async def text_to_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate image from text."""
        return await self.generate("text_to_image", params)

    async def image_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate video from image."""
        return await self.generate("image_to_video", params)

    async def text_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate video from text."""
        return await self.generate("text_to_video", params)

    # ─────────────────────────────────────────────────────────────────────────
    # ADVANCED FEATURES
    # ─────────────────────────────────────────────────────────────────────────

    async def keyframes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate video with keyframes control.

        Args:
            params: {
                "keyframes": [
                    {"image_url": str, "timestamp": float},
                    ...
                ],
                "prompt": str,
                "duration": int
            }
        """
        self._log_request("keyframes", params)

        payload = {
            "model": params.get("model", "kling2.5"),
            "keyframes": params.get("keyframes", []),
            "prompt": params.get("prompt", ""),
            "duration": params.get("duration", 5),
            "mode": "keyframe"
        }

        return await self._submit_and_poll("/generate/video/keyframe", payload)

    async def effects(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply video effects.

        Args:
            params: {
                "video_url": str,
                "effect": str (e.g., "zoom_in", "pan_left", "rotate"),
                "intensity": float (0-1)
            }
        """
        self._log_request("effects", params)

        payload = {
            "video_url": params["video_url"],
            "effect": params.get("effect", "zoom_in"),
            "intensity": params.get("intensity", 0.5)
        }

        return await self._submit_and_poll("/effects/apply", payload)

    async def multi_model(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate with specific model selection.

        Args:
            params: {
                "model": str (e.g., "kling2.5", "hailuo", "wan2.6"),
                "prompt": str,
                "image_url": str (optional),
                ...other params
            }
        """
        self._log_request("multi_model", params)

        model = params.get("model", "kling2.5")
        task_type = "image_to_video" if params.get("image_url") else "text_to_video"

        payload = {
            "model": model,
            "prompt": params.get("prompt", ""),
            "duration": params.get("duration", 5)
        }

        if params.get("image_url"):
            payload["image_url"] = params["image_url"]

        endpoint = "/generate/video"
        return await self._submit_and_poll(endpoint, payload)

    async def camera_control(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate video with camera movement control.

        Args:
            params: {
                "image_url": str,
                "prompt": str,
                "camera_movement": str (e.g., "zoom_in", "pan_right", "tilt_up"),
                "duration": int
            }
        """
        self._log_request("camera_control", params)

        payload = {
            "model": params.get("model", "kling2.5"),
            "image_url": params["image_url"],
            "prompt": params.get("prompt", ""),
            "camera_movement": params.get("camera_movement", "zoom_in"),
            "duration": params.get("duration", 5)
        }

        return await self._submit_and_poll("/generate/video/camera", payload)

    # ─────────────────────────────────────────────────────────────────────────
    # INTERNAL METHODS
    # ─────────────────────────────────────────────────────────────────────────

    def _build_payload(self, task_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build request payload based on task type."""
        base_payload = {
            "model": params.get("model", "wan2.6"),
            "prompt": params.get("prompt", "")
        }

        if task_type == "text_to_image":
            base_payload.update({
                "negative_prompt": params.get("negative_prompt", ""),
                "size": params.get("size", "1024x1024"),
                "n": params.get("n", 1)
            })
        elif task_type in ["image_to_video", "text_to_video"]:
            base_payload.update({
                "duration": params.get("duration", 5),
                "aspect_ratio": params.get("aspect_ratio", "16:9")
            })
            if params.get("image_url"):
                base_payload["image_url"] = params["image_url"]

        return base_payload

    async def _submit_and_poll(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit task and poll for result."""
        try:
            response = await self.client.post(
                f"{self.BASE_URL}{endpoint}",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            self._log_response("generation", False, str(e))
            raise Exception(f"Pollo.ai request failed: {e.response.text}")

        # Get task ID
        task_id = data.get("task_id") or data.get("id")
        if not task_id:
            # Immediate result
            if data.get("output") or data.get("result"):
                self._log_response("generation", True)
                return {
                    "success": True,
                    "output": data.get("output") or data.get("result")
                }
            raise Exception(f"Invalid Pollo.ai response: {data}")

        # Poll for result
        max_attempts = 120
        for _ in range(max_attempts):
            try:
                status_response = await self.client.get(
                    f"{self.BASE_URL}/task/{task_id}"
                )
                status_data = status_response.json()

                status = status_data.get("status", "").lower()

                if status in ["completed", "success", "done"]:
                    self._log_response("generation", True)
                    return {
                        "success": True,
                        "task_id": task_id,
                        "output": status_data.get("output") or status_data.get("result", {})
                    }
                elif status in ["failed", "error"]:
                    error = status_data.get("error", "Unknown error")
                    self._log_response("generation", False, error)
                    raise Exception(error)

                await asyncio.sleep(5)
            except Exception as e:
                if "failed" in str(e).lower():
                    raise
                await asyncio.sleep(5)

        raise Exception("Pollo.ai task timeout")

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
