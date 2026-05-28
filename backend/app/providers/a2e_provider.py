"""
A2E.ai Provider - Avatar/Digital Human Video Generation.

Supports:
- Text-to-speech with lip sync
- Multiple voices and languages
- High quality avatar videos
"""
from typing import Dict, Any, List, Optional
import logging
import os

from app.providers.base import BaseProvider
from app.services.a2e_service import A2EAvatarService

logger = logging.getLogger(__name__)


class A2EProvider(BaseProvider):
    """
    A2E.ai Provider - Best value for avatar/digital human videos.
    No backup provider - A2E is the primary for avatars.
    """

    name = "a2e"
    BASE_URL = "https://video.a2e.ai/api/v1"

    SUPPORTED_LANGUAGES = ["en", "zh-TW", "zh-CN", "ja", "ko", "es", "fr", "de"]

    def __init__(self, service: Optional[A2EAvatarService] = None):
        self.api_key = os.getenv("A2E_API_KEY", "")
        self.default_anchor_id = os.getenv("A2E_DEFAULT_CREATOR_ID", "")
        if not self.api_key:
            logger.warning("A2E_API_KEY not set in environment")
        self.service = service or A2EAvatarService(
            api_key=self.api_key,
            anchor_id=self.default_anchor_id,
        )

    async def health_check(self) -> bool:
        """Check if A2E.ai is healthy by validating API/auth access."""
        if not self.api_key:
            return False

        try:
            result = await self.service.test_connection()
            return bool(result.get("success"))
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

        if not self.api_key:
            return {"success": False, "error": "A2E_API_KEY is not configured"}

        language = params.get("language", "en")
        if language not in self.SUPPORTED_LANGUAGES:
            logger.warning(f"Unsupported language: {language}, defaulting to en")
            language = "en"

        image_url = params.get("image_url")
        text = params.get("text") or params.get("script")
        if not image_url:
            return {"success": False, "error": "image_url is required for A2E avatar generation"}
        if not text:
            return {"success": False, "error": "text or script is required for A2E avatar generation"}

        result = await self.service.generate_and_wait(
            image_url=image_url,
            script=text,
            language=language,
            voice_id=params.get("voice_id") or params.get("voice"),
            duration=int(params.get("duration", 30)),
            timeout=int(params.get("timeout", 1200)),
            save_locally=False,
        )
        if not result.get("success"):
            return {"success": False, "error": result.get("error", "A2E avatar generation failed")}

        video_url = result.get("video_url") or result.get("remote_url")
        if not video_url:
            return {"success": False, "error": "A2E completed without a video URL"}

        return {
            "success": True,
            "task_id": result.get("task_id"),
            "output": {
                "video_url": video_url,
                "audio_url": result.get("audio_url"),
            },
        }

    async def get_voices(self, language: str = "en") -> List[Dict[str, Any]]:
        """Get available voices for a language."""
        try:
            return self.service.get_voices(language)
        except Exception as e:
            logger.error(f"Failed to get voices: {e}")
            return []

    async def close(self):
        """A2E service creates short-lived HTTP clients per request."""
        return None
