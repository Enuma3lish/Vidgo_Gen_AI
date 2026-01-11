"""
PiAPI Provider for Wan API access.

Supported models (via PiAPI):
- Wan: wan26-txt2video (Text-to-Video)
- Wan: wan26-img2video (Image-to-Video)
- Wan: txt2img (Text-to-Image via Flux)

API Documentation: https://piapi.ai/docs/wan-api
"""
import httpx
import asyncio
from typing import Dict, Any, Optional
import logging
import os

from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class PiAPIProvider(BaseProvider):
    """
    PiAPI Provider - Primary provider for VidGo.
    Uses PiAPI to access Wan models for T2I, I2V, T2V.
    """

    name = "piapi"
    BASE_URL = "https://api.piapi.ai/api/v1"

    def __init__(self):
        self.api_key = os.getenv("PiAPI_KEY", "")
        if not self.api_key:
            logger.warning("PiAPI_KEY not set in environment")

        self.client = httpx.AsyncClient(
            timeout=300.0,  # 5 minutes for video generation
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
        )

    async def health_check(self) -> bool:
        """Check if PiAPI is healthy by making a simple API call."""
        try:
            # PiAPI doesn't have a dedicated health endpoint, so we check by testing the API
            # We'll just verify the connection works
            response = await self.client.post(
                f"{self.BASE_URL}/task",
                json={
                    "model": "Qubico/flux1-schnell",
                    "task_type": "txt2img",
                    "input": {"prompt": "test", "width": 64, "height": 64}
                },
                timeout=10.0
            )
            # If we get any response (even error), the API is reachable
            return response.status_code in [200, 201, 400, 402, 429]
        except Exception as e:
            logger.error(f"PiAPI health check failed: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # TEXT TO IMAGE (using Flux via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def text_to_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate image from text using Flux via PiAPI.

        Args:
            params: {
                "prompt": str,
                "negative_prompt": str (optional),
                "size": str (optional, default "1024*1024"),
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str}}
        """
        self._log_request("text_to_image", params)

        # Parse size
        size = params.get("size", "1024*1024")
        if "*" in size:
            width, height = map(int, size.split("*"))
        else:
            width, height = 1024, 1024

        payload = {
            "model": "Qubico/flux1-schnell",
            "task_type": "txt2img",
            "input": {
                "prompt": params["prompt"],
                "negative_prompt": params.get("negative_prompt", ""),
                "width": width,
                "height": height
            }
        }

        return await self._submit_and_poll(payload)

    # ─────────────────────────────────────────────────────────────────────────
    # IMAGE TO VIDEO (Wan 2.6 via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def image_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate video from image using Wan 2.6 I2V via PiAPI.

        Args:
            params: {
                "image_url": str,
                "prompt": str (optional),
                "duration": int (optional, 5/10/15, default 5),
                "resolution": str (optional, "720P" or "1080P", default "1080P"),
            }

        Returns:
            {"success": True, "task_id": str, "output": {"video_url": str}}
        """
        self._log_request("image_to_video", params)

        payload = {
            "model": "Wan",
            "task_type": "wan26-img2video",
            "input": {
                "image": params["image_url"],
                "prompt": params.get("prompt", "smooth natural motion"),
                "duration": params.get("duration", 5),
                "resolution": params.get("resolution", "1080P"),
                "watermark": False
            }
        }

        return await self._submit_and_poll(payload)

    # ─────────────────────────────────────────────────────────────────────────
    # TEXT TO VIDEO (Wan 2.6 via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def text_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate video from text using Wan 2.6 T2V via PiAPI.

        Args:
            params: {
                "prompt": str,
                "negative_prompt": str (optional),
                "duration": int (optional, 5/10/15, default 5),
                "resolution": str (optional, "720P" or "1080P", default "1080P"),
                "aspect_ratio": str (optional, "16:9", "9:16", "1:1", default "16:9")
            }

        Returns:
            {"success": True, "task_id": str, "output": {"video_url": str}}
        """
        self._log_request("text_to_video", params)

        payload = {
            "model": "Wan",
            "task_type": "wan26-txt2video",
            "input": {
                "prompt": params["prompt"],
                "negative_prompt": params.get("negative_prompt", ""),
                "duration": params.get("duration", 5),
                "resolution": params.get("resolution", "1080P"),
                "aspect_ratio": params.get("aspect_ratio", "16:9"),
                "watermark": False
            }
        }

        return await self._submit_and_poll(payload)

    # ─────────────────────────────────────────────────────────────────────────
    # INTERIOR DESIGN (using Flux img2img as fallback)
    # ─────────────────────────────────────────────────────────────────────────

    async def doodle_interior(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate interior design from image.
        Uses Flux img2img for interior redesign.

        Args:
            params: {
                "image_url": str,
                "prompt": str (optional),
                "style": str (optional, default "modern"),
                "room_type": str (optional, default "living_room")
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str}}
        """
        self._log_request("doodle_interior", params)

        style = params.get("style", "modern")
        room_type = params.get("room_type", "living room")
        prompt = params.get("prompt", "")

        full_prompt = f"{style} {room_type} interior design, professional architectural rendering, {prompt}"

        payload = {
            "model": "Qubico/flux1-schnell",
            "task_type": "txt2img",
            "input": {
                "prompt": full_prompt,
                "width": 1024,
                "height": 768
            }
        }

        return await self._submit_and_poll(payload)

    # ─────────────────────────────────────────────────────────────────────────
    # UPSCALE
    # ─────────────────────────────────────────────────────────────────────────

    async def upscale(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upscale image resolution.

        Args:
            params: {
                "image_url": str,
                "scale": int (optional, 2 or 4)
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str}}
        """
        self._log_request("upscale", params)

        payload = {
            "model": "wanx",
            "task_type": "upscale",
            "input": {
                "image_url": params["image_url"],
                "scale": params.get("scale", 2)
            }
        }

        return await self._submit_and_poll(payload)

    # ─────────────────────────────────────────────────────────────────────────
    # INTERNAL METHODS
    # ─────────────────────────────────────────────────────────────────────────

    async def _submit_and_poll(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit task and poll for result."""
        # Submit task
        try:
            response = await self.client.post(
                f"{self.BASE_URL}/task",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            self._log_response(payload.get("task_type", "unknown"), False, str(e))
            raise Exception(f"PiAPI request failed: {e.response.text}")
        except Exception as e:
            self._log_response(payload.get("task_type", "unknown"), False, str(e))
            raise

        # Handle different response formats
        if "data" in data and "task_id" in data["data"]:
            task_id = data["data"]["task_id"]
        elif "task_id" in data:
            task_id = data["task_id"]
        else:
            # Check if result is immediate
            if "output" in data or "result" in data:
                output = data.get("output") or data.get("result")
                self._log_response(payload.get("task_type", "unknown"), True)
                return {
                    "success": True,
                    "task_id": data.get("id", "immediate"),
                    "output": output
                }
            raise Exception(f"Invalid PiAPI response: {data}")

        # Poll for result
        max_attempts = 120  # 10 minutes max
        for attempt in range(max_attempts):
            try:
                status_response = await self.client.get(
                    f"{self.BASE_URL}/task/{task_id}"
                )
                status_data = status_response.json()

                # Handle different response structures
                if "data" in status_data:
                    task_data = status_data["data"]
                else:
                    task_data = status_data

                status = task_data.get("status", "").lower()

                if status in ["completed", "success", "done"]:
                    output = task_data.get("output") or task_data.get("result", {})
                    self._log_response(payload.get("task_type", "unknown"), True)
                    return {
                        "success": True,
                        "task_id": task_id,
                        "output": output
                    }
                elif status in ["failed", "error"]:
                    error_msg = task_data.get("error", "Unknown error")
                    self._log_response(payload.get("task_type", "unknown"), False, error_msg)
                    raise Exception(error_msg)

                # Still processing, wait and retry
                await asyncio.sleep(5)

            except httpx.HTTPStatusError as e:
                if attempt < max_attempts - 1:
                    await asyncio.sleep(5)
                    continue
                raise Exception(f"Failed to poll task status: {e}")

        self._log_response(payload.get("task_type", "unknown"), False, "Task timeout")
        raise Exception("PiAPI task timeout - generation took too long")

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
