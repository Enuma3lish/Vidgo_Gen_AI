"""
Pollo AI Client - Video Generation (T2V, I2V)

API: https://pollo.ai/api
Models: pollo-v2-0, pixverse-v4-5
Cost: ~$0.10 per video
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


class PolloClient:
    """Pollo AI client for video generation."""

    BASE_URL = "https://pollo.ai/api/platform"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }

    async def generate_video(
        self,
        prompt: str,
        image_url: Optional[str] = None,
        model: str = "pollo-v2-0",
        length: int = 5,
        save_locally: bool = True
    ) -> Dict[str, Any]:
        """
        Generate video from text prompt (T2V) or image (I2V).

        Args:
            prompt: Video description
            image_url: Optional source image for I2V
            model: Model to use (pollo-v2-0 or pixverse-v4-5)
            length: Video length in seconds (5, 10, 15)
            save_locally: Save to local file (default True)

        Returns:
            {
                "success": True/False,
                "video_url": str (local path or remote URL),
                "error": str (if failed)
            }
        """
        if not self.api_key:
            return {"success": False, "error": "Pollo API key not configured"}

        mode = "I2V" if image_url else "T2V"
        logger.info(f"[Pollo] {mode}: {prompt[:50]}...")

        # Model endpoints
        endpoints = {
            "pollo-v2-0": "/generation/pollo/pollo-v2-0",
            "pixverse-v4-5": "/generation/pixverse/pixverse-v4-5",
        }
        endpoint = endpoints.get(model, endpoints["pollo-v2-0"])

        # Build payload
        payload = {
            "input": {
                "prompt": prompt,
                "length": length,
                "resolution": "720p"
            }
        }
        if image_url:
            payload["input"]["image_url"] = image_url

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Create task
                response = await client.post(
                    f"{self.BASE_URL}{endpoint}",
                    headers=self.headers,
                    json=payload
                )

                if response.status_code not in [200, 201, 202]:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"[Pollo] Create task failed: {error}")
                    return {"success": False, "error": error}

                data = response.json()
                task_id = data.get("id") or data.get("data", {}).get("taskId")

                if not task_id:
                    return {"success": False, "error": "No task_id in response"}

                logger.info(f"[Pollo] Task created: {task_id}")

                # Poll for result
                for attempt in range(60):
                    await asyncio.sleep(5)

                    status_resp = await client.get(
                        f"{self.BASE_URL}/generation/{task_id}/status",
                        headers=self.headers
                    )

                    if status_resp.status_code != 200:
                        continue

                    status_data = status_resp.json()
                    generations = status_data.get("data", {}).get("generations", [])

                    if generations:
                        gen = generations[0]
                        status = gen.get("status", "")

                        if status == "succeed":
                            video_url = gen.get("url")

                            if save_locally:
                                local_path = await self._download(client, video_url, task_id)
                                if local_path:
                                    logger.info(f"[Pollo] Saved: {local_path}")
                                    return {"success": True, "video_url": local_path}

                            return {"success": True, "video_url": video_url}

                        elif status == "failed":
                            error = gen.get("failMsg", "Unknown error")
                            logger.error(f"[Pollo] Task failed: {error}")
                            return {"success": False, "error": error}

                return {"success": False, "error": "Timeout (5 min)"}

        except Exception as e:
            logger.exception(f"[Pollo] Exception: {e}")
            return {"success": False, "error": str(e)}

    async def _download(self, client: httpx.AsyncClient, url: str, task_id: str) -> Optional[str]:
        """Download video and save locally."""
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            response = await client.get(url, follow_redirects=True)
            if response.status_code == 200:
                filename = f"video_{task_id[:20]}_{uuid.uuid4().hex[:8]}.mp4"
                filepath = OUTPUT_DIR / filename
                filepath.write_bytes(response.content)
                return f"/static/generated/{filename}"
        except Exception as e:
            logger.warning(f"[Pollo] Download failed: {e}")
        return None
