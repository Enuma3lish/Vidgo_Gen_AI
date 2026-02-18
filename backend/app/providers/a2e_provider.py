"""
A2E.ai Provider - Avatar/Digital Human Video Generation.

Supports:
- Text-to-speech with lip sync
- Multiple voices and languages
- High quality avatar videos
"""
import httpx
import asyncio
from typing import Dict, Any, List
import logging
import os

from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class A2EProvider(BaseProvider):
    """
    A2E.ai Provider - Best value for avatar/digital human videos.
    No backup provider - A2E is the primary for avatars.
    """

    name = "a2e"
    BASE_URL = "https://api.a2e.ai"

    SUPPORTED_LANGUAGES = ["en", "zh-TW", "zh-CN", "ja", "ko", "es", "fr", "de"]

    def __init__(self):
        self.api_key = os.getenv("A2E_API_KEY", "")
        if not self.api_key:
            logger.warning("A2E_API_KEY not set in environment")

        self.client = httpx.AsyncClient(
            timeout=300.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )

    async def health_check(self) -> bool:
        """Check if A2E.ai is healthy by testing API connection."""
        try:
            # A2E main page check
            response = await self.client.get(
                f"{self.BASE_URL}/",
                timeout=10.0
            )
            # Accept any response (200, 401, 403, 404) as it means API is reachable
            return response.status_code in [200, 401, 403, 404, 405]
        except Exception as e:
            logger.error(f"A2E.ai health check failed: {e}")
            return False

    async def test_connection(self) -> Dict[str, Any]:
        """Test API connection."""
        try:
            healthy = await self.health_check()
            return {
                "success": healthy,
                "message": "A2E.ai API is accessible" if healthy else "Connection failed"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def generate_avatar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate avatar video with lip sync.

        Args:
            params: {
                "image_url": str (avatar/presenter image),
                "text": str (script to speak),
                "voice": str (voice ID or preset),
                "language": str (default "en"),
                "emotion": str (optional, "neutral", "happy", "serious")
            }

        Returns:
            {"success": True, "output": {"video_url": str, "audio_url": str}}
        """
        self._log_request("generate_avatar", params)

        language = params.get("language", "en")
        if language not in self.SUPPORTED_LANGUAGES:
            logger.warning(f"Unsupported language: {language}, defaulting to en")
            language = "en"

        payload = {
            "image_url": params["image_url"],
            "text": params["text"],
            "voice": params.get("voice", "default"),
            "language": language,
            "emotion": params.get("emotion", "neutral"),
            "quality": params.get("quality", "high"),
            "output_format": "mp4"
        }

        return await self._submit_and_poll(payload)

    async def get_voices(self, language: str = "en") -> List[Dict[str, Any]]:
        """Get available voices for a language."""
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/voices",
                params={"language": language}
            )
            response.raise_for_status()
            return response.json().get("voices", [])
        except Exception as e:
            logger.error(f"Failed to get voices: {e}")
            return []

    async def _submit_and_poll(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit avatar generation task and poll for result."""
        try:
            response = await self.client.post(
                f"{self.BASE_URL}/avatar/generate",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            self._log_response("generate_avatar", False, str(e))
            raise Exception(f"A2E.ai request failed: {e.response.text}")

        task_id = data.get("task_id") or data.get("id")
        if not task_id:
            if data.get("video_url") or data.get("output"):
                self._log_response("generate_avatar", True)
                output = data.get("output") or {}
                return {
                    "success": True,
                    "output": {
                        "video_url": data.get("video_url") or output.get("video_url"),
                        "audio_url": data.get("audio_url") or output.get("audio_url")
                    }
                }
            raise Exception(f"Invalid A2E.ai response: {data}")

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
                    output = status_data.get("output") or {}
                    self._log_response("generate_avatar", True)
                    return {
                        "success": True,
                        "task_id": task_id,
                        "output": {
                            "video_url": output.get("video_url") or status_data.get("video_url"),
                            "audio_url": output.get("audio_url") or status_data.get("audio_url")
                        }
                    }
                elif status in ["failed", "error"]:
                    error = status_data.get("error", "Avatar generation failed")
                    self._log_response("generate_avatar", False, error)
                    raise Exception(error)

                await asyncio.sleep(5)
            except Exception as e:
                if "failed" in str(e).lower() or "error" in str(e).lower():
                    raise
                await asyncio.sleep(5)

        raise Exception("A2E.ai avatar generation timeout")

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
