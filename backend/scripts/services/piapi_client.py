"""
PiAPI Client - Text-to-Image using Flux model

API: https://api.piapi.ai
Model: Qubico/flux1-schnell
Cost: ~$0.005 per image
"""
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Output directory
OUTPUT_DIR = Path("/app/static/generated")


class PiAPIClient:
    """PiAPI client for T2I generation."""

    BASE_URL = "https://api.piapi.ai/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }

    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        save_locally: bool = True
    ) -> Dict[str, Any]:
        """
        Generate image from text prompt.

        Args:
            prompt: Text description
            width: Image width (default 1024)
            height: Image height (default 1024)
            save_locally: Save to local file (default True)

        Returns:
            {
                "success": True/False,
                "image_url": str (local path or remote URL),
                "error": str (if failed)
            }
        """
        if not self.api_key:
            return {"success": False, "error": "PiAPI key not configured"}

        logger.info(f"[PiAPI] Generating: {prompt[:50]}...")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Create task
                response = await client.post(
                    f"{self.BASE_URL}/task",
                    headers=self.headers,
                    json={
                        "model": "Qubico/flux1-schnell",
                        "task_type": "txt2img",
                        "input": {
                            "prompt": prompt,
                            "width": width,
                            "height": height
                        }
                    }
                )

                if response.status_code not in [200, 201]:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"[PiAPI] Create task failed: {error}")
                    return {"success": False, "error": error}

                data = response.json()
                task_id = data.get("data", {}).get("task_id")

                if not task_id:
                    return {"success": False, "error": "No task_id in response"}

                logger.info(f"[PiAPI] Task created: {task_id}")

                # Poll for result
                for attempt in range(60):
                    await asyncio.sleep(2)

                    status_resp = await client.get(
                        f"{self.BASE_URL}/task/{task_id}",
                        headers=self.headers
                    )

                    if status_resp.status_code != 200:
                        continue

                    status_data = status_resp.json()
                    status = status_data.get("data", {}).get("status", "")

                    if status == "completed":
                        output = status_data.get("data", {}).get("output", {})

                        # PiAPI returns image_url directly in output
                        image_url = output.get("image_url")

                        if not image_url:
                            # Fallback: check for images array
                            images = output.get("images", [])
                            if images:
                                image_url = images[0].get("url")

                        if not image_url:
                            logger.error(f"[PiAPI] Output structure: {output}")
                            return {"success": False, "error": "No image_url in output"}

                        if save_locally:
                            local_path = await self._download(client, image_url)
                            if local_path:
                                logger.info(f"[PiAPI] Saved: {local_path}")
                                return {"success": True, "image_url": local_path}

                        return {"success": True, "image_url": image_url}

                    elif status == "failed":
                        error = status_data.get("data", {}).get("error", "Unknown error")
                        logger.error(f"[PiAPI] Task failed: {error}")
                        return {"success": False, "error": error}

                return {"success": False, "error": "Timeout (2 min)"}

        except Exception as e:
            logger.exception(f"[PiAPI] Exception: {e}")
            return {"success": False, "error": str(e)}

    async def _download(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """Download image and save locally."""
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            response = await client.get(url, follow_redirects=True)
            if response.status_code == 200:
                filename = f"piapi_{uuid.uuid4().hex[:8]}.png"
                filepath = OUTPUT_DIR / filename
                filepath.write_bytes(response.content)
                return f"/static/generated/{filename}"
        except Exception as e:
            logger.warning(f"[PiAPI] Download failed: {e}")
        return None
