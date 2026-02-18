"""
PiAPI Trellis 3D Provider - Image-to-3D and Text-to-3D model generation.

Uses the same PiAPI API key and endpoint pattern as the existing PiAPI provider.
Outputs GLB mesh files that can be rendered in Three.js on the frontend.

API Reference: https://piapi.ai/docs/trellis-api/create-task
Pricing: $0.04 per generation
"""
import httpx
import asyncio
import logging
import os
from typing import Dict, Any, Optional

from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class TrellisProvider(BaseProvider):
    """
    PiAPI Trellis 3D Provider for interior design 3D model generation.

    Supports:
    - image-to-3d: Convert a 2D interior design image to a 3D model (GLB)
    - text-to-3d: Generate a 3D model from text description
    """

    name = "trellis"
    BASE_URL = "https://api.piapi.ai/api/v1"

    def __init__(self):
        self.api_key = os.getenv("PIAPI_KEY", "")
        if not self.api_key:
            logger.warning("PIAPI_KEY not set - Trellis 3D provider unavailable")

        self.client = httpx.AsyncClient(
            timeout=300.0,  # 5 minutes for 3D generation
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
        )

    async def health_check(self) -> bool:
        """Check if Trellis API is reachable."""
        try:
            return bool(self.api_key)
        except Exception as e:
            logger.error(f"Trellis health check failed: {e}")
            return False

    async def image_to_3d(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a 2D image to a 3D model using Trellis.

        Args:
            params: {
                "image_url": str,           # URL of the 2D image
                "mesh_simplify": float,     # 0.0-1.0, default 0.95
                "texture_size": int,        # 512 or 1024, default 1024
                "generate_model": bool,     # Generate mesh, default True
                "generate_color": bool,     # Generate texture, default True
                "generate_normal": bool,    # Generate normal map, default False
            }

        Returns:
            {
                "success": True,
                "task_id": str,
                "output": {
                    "model_url": str,  # URL to GLB file
                }
            }
        """
        self._log_request("image_to_3d", params)

        payload = {
            "model": "Qubico/trellis",
            "task_type": "image-to-3d",
            "input": {
                "image": params["image_url"],
                "mesh_simplify": params.get("mesh_simplify", 0.95),
                "texture_size": params.get("texture_size", 1024),
                "generate_model": params.get("generate_model", True),
                "generate_color": params.get("generate_color", True),
                "generate_normal": params.get("generate_normal", False),
                "ss_sampling_steps": params.get("ss_sampling_steps", 12),
                "slat_sampling_steps": params.get("slat_sampling_steps", 12),
                "ss_guidance_strength": params.get("ss_guidance_strength", 7.5),
                "slat_guidance_strength": params.get("slat_guidance_strength", 3.0),
            }
        }

        return await self._submit_and_poll(payload)

    async def text_to_3d(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a 3D model from text description using Trellis.

        Args:
            params: {
                "prompt": str,              # Text description of 3D model
                "mesh_simplify": float,     # 0.0-1.0, default 0.95
                "texture_size": int,        # 512 or 1024, default 1024
            }

        Returns:
            {
                "success": True,
                "task_id": str,
                "output": {
                    "model_url": str,  # URL to GLB file
                }
            }
        """
        self._log_request("text_to_3d", params)

        payload = {
            "model": "Qubico/trellis",
            "task_type": "text-to-3d",
            "input": {
                "prompt": params["prompt"],
                "mesh_simplify": params.get("mesh_simplify", 0.95),
                "texture_size": params.get("texture_size", 1024),
                "generate_model": True,
                "generate_color": True,
                "ss_sampling_steps": params.get("ss_sampling_steps", 12),
                "slat_sampling_steps": params.get("slat_sampling_steps", 12),
                "ss_guidance_strength": params.get("ss_guidance_strength", 7.5),
                "slat_guidance_strength": params.get("slat_guidance_strength", 3.0),
            }
        }

        return await self._submit_and_poll(payload)

    async def _submit_and_poll(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit task and poll for result (same pattern as PiAPI provider)."""
        try:
            response = await self.client.post(
                f"{self.BASE_URL}/task",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            self._log_response(payload.get("task_type", "unknown"), False, str(e))
            raise Exception(f"Trellis request failed: {e.response.text}")
        except Exception as e:
            self._log_response(payload.get("task_type", "unknown"), False, str(e))
            raise

        # Extract task_id
        if "data" in data and "task_id" in data["data"]:
            task_id = data["data"]["task_id"]
        elif "task_id" in data:
            task_id = data["task_id"]
        else:
            if "output" in data or "result" in data:
                output = data.get("output") or data.get("result")
                self._log_response(payload.get("task_type", "unknown"), True)
                return {"success": True, "task_id": "immediate", "output": output}
            raise Exception(f"Invalid Trellis response: {data}")

        # Poll for result
        max_attempts = 120  # 10 minutes max
        for attempt in range(max_attempts):
            try:
                status_response = await self.client.get(
                    f"{self.BASE_URL}/task/{task_id}"
                )
                status_data = status_response.json()

                task_data = status_data.get("data", status_data)
                task_status = task_data.get("status", "").lower()

                if task_status in ["completed", "success", "done"]:
                    output = task_data.get("output") or task_data.get("result", {})
                    self._log_response(payload.get("task_type", "unknown"), True)
                    return {
                        "success": True,
                        "task_id": task_id,
                        "output": output
                    }
                elif task_status in ["failed", "error"]:
                    error_msg = task_data.get("error", "Unknown error")
                    self._log_response(payload.get("task_type", "unknown"), False, error_msg)
                    raise Exception(error_msg)

                await asyncio.sleep(5)

            except httpx.HTTPStatusError:
                if attempt < max_attempts - 1:
                    await asyncio.sleep(5)
                    continue
                raise Exception("Failed to poll Trellis task status")

        raise Exception("Trellis task timeout - 3D generation took too long")

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
