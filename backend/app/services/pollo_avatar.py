"""
Pollo AI Avatar Service
Photo-to-Avatar video generation with lip sync and natural expressions.
Supports English and zh-TW (Traditional Chinese) languages.

Based on Pollo AI Avatar feature:
- Transform photo to talking avatar video
- Natural lip sync and facial expressions
- Up to 2 minutes video length
- Multiple voice options per language

API Pattern: https://pollo.ai/api/platform/generation/{model}/{version}
"""
import asyncio
import logging
import uuid
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import httpx
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Static directory for storing generated materials
STATIC_DIR = Path("/app/static/materials")


# Available voices for each language
AVATAR_VOICES = {
    "en": [
        {"id": "en-US-1", "name": "Emily", "gender": "female", "style": "professional"},
        {"id": "en-US-2", "name": "James", "gender": "male", "style": "professional"},
        {"id": "en-US-3", "name": "Sarah", "gender": "female", "style": "friendly"},
        {"id": "en-US-4", "name": "Michael", "gender": "male", "style": "casual"},
    ],
    "zh-TW": [
        {"id": "zh-TW-1", "name": "小雅", "gender": "female", "style": "professional"},
        {"id": "zh-TW-2", "name": "建明", "gender": "male", "style": "professional"},
        {"id": "zh-TW-3", "name": "思婷", "gender": "female", "style": "friendly"},
        {"id": "zh-TW-4", "name": "志豪", "gender": "male", "style": "casual"},
    ],
}

# Default avatar images for each language (professional headshots)
DEFAULT_AVATARS = {
    "en": [
        "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=512",  # Professional woman
        "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=512",  # Professional man
        "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=512",  # Business woman
        "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=512",  # Business man
    ],
    "zh-TW": [
        "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=512",  # Asian professional woman
        "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=512",  # Asian professional man
        "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=512",  # Asian business woman
        "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=512",  # Asian business man
    ],
}


class PolloAvatarService:
    """
    Pollo AI Avatar Service for generating talking avatar videos.

    Supports:
    - English (en) and Traditional Chinese (zh-TW)
    - Multiple voice options per language
    - Photo-to-avatar with lip sync
    - Natural facial expressions
    """

    BASE_URL = "https://pollo.ai/api/platform"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'POLLO_API_KEY', '')
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }

    def get_voices(self, language: str = "en") -> List[Dict[str, str]]:
        """Get available voices for a language."""
        return AVATAR_VOICES.get(language, AVATAR_VOICES["en"])

    def get_default_avatars(self, language: str = "en") -> List[str]:
        """Get default avatar images for a language."""
        return DEFAULT_AVATARS.get(language, DEFAULT_AVATARS["en"])

    async def generate_avatar_video(
        self,
        image_url: str,
        script: str,
        language: str = "en",
        voice_id: Optional[str] = None,
        duration: int = 30,
        aspect_ratio: str = "9:16",
        resolution: str = "720p"
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Generate an avatar video from a photo with speech.

        Args:
            image_url: URL of the avatar photo (clear headshot recommended)
            script: The text script for the avatar to speak
            language: Language code ('en' or 'zh-TW')
            voice_id: Voice ID to use (defaults to first voice for language)
            duration: Target video duration in seconds (max 120)
            aspect_ratio: Video aspect ratio ('9:16', '16:9', '1:1')
            resolution: Video resolution ('720p', '1080p')

        Returns:
            Tuple of (success, task_id or error, None)
        """
        if not self.api_key:
            return False, "Pollo API key not configured", None

        # Validate language
        if language not in ["en", "zh-TW"]:
            language = "en"

        # Get default voice if not specified
        if not voice_id:
            voices = self.get_voices(language)
            voice_id = voices[0]["id"] if voices else "en-US-1"

        # Limit duration
        duration = min(max(duration, 5), 120)

        # Note: The actual Pollo Avatar API endpoint may differ
        # This is based on their documented pattern for video generation
        payload = {
            "input": {
                "image": image_url,
                "script": script,
                "language": language,
                "voice": voice_id,
                "duration": duration,
                "aspectRatio": aspect_ratio,
                "resolution": resolution,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Try the avatar-specific endpoint first
                # Based on Pollo API pattern: /generation/{provider}/{model}
                response = await client.post(
                    f"{self.BASE_URL}/generation/pollo/pollo-avatar",
                    headers=self.headers,
                    json=payload
                )

                # If avatar endpoint doesn't exist, try alternative
                if response.status_code == 404:
                    logger.info("Avatar endpoint not found, trying pollo-v2-0 with image")
                    # Fallback: Use regular video generation with the image
                    # Pollo v2-0 only accepts length of 5 or 10 seconds
                    video_length = 5 if duration <= 7 else 10
                    payload = {
                        "input": {
                            "image": image_url,
                            "prompt": f"A person speaking naturally, professional presentation: {script[:100]}",
                            "length": video_length,
                            "negativePrompt": "static, frozen, no movement, blurry"
                        }
                    }
                    response = await client.post(
                        f"{self.BASE_URL}/generation/pollo/pollo-v2-0",
                        headers=self.headers,
                        json=payload
                    )

                logger.info(f"Pollo Avatar API response status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Pollo Avatar API response: {data}")

                    if data.get("code") == "SUCCESS":
                        task_id = data["data"]["taskId"]
                        logger.info(f"Pollo Avatar task created: {task_id}")
                        return True, task_id, None
                    else:
                        error = data.get("message", "Unknown error")
                        logger.error(f"Pollo Avatar API error: {error}")
                        return False, error, None
                else:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"Pollo Avatar API error: {error}")
                    return False, error, None

        except Exception as e:
            logger.error(f"Pollo Avatar API error: {e}")
            return False, str(e), None

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Check avatar task status.

        Returns:
            Dict with status, video_url when complete
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/generation/{task_id}/status",
                    headers=self.headers
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"Avatar status response: {data}")

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

                    return {
                        "success": True,
                        "status": "pending",
                        "video_url": None
                    }
                else:
                    return {
                        "success": False,
                        "status": "error",
                        "error": f"HTTP {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Avatar status error: {e}")
            return {"success": False, "status": "error", "error": str(e)}

    async def wait_for_completion(
        self,
        task_id: str,
        timeout: int = 300,
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """
        Wait for avatar task completion with polling.

        Args:
            task_id: Task ID from generate_avatar_video
            timeout: Max wait time in seconds
            poll_interval: Seconds between status checks

        Returns:
            Final task status with video_url
        """
        elapsed = 0
        logger.info(f"Waiting for avatar task {task_id} (timeout: {timeout}s)")

        while elapsed < timeout:
            status = await self.get_task_status(task_id)
            task_status = status.get("status", "").lower()

            logger.info(f"Avatar task {task_id}: {task_status} ({elapsed}s elapsed)")

            if task_status == "succeed":
                logger.info(f"Avatar task {task_id} completed successfully")
                return status
            elif task_status == "failed":
                error_msg = status.get("error", "Unknown error")
                logger.error(f"Avatar task {task_id} failed: {error_msg}")
                return status

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        logger.error(f"Avatar task {task_id} timed out after {timeout}s")
        return {"success": False, "status": "timeout", "error": "Task timed out"}

    async def generate_and_wait(
        self,
        image_url: str,
        script: str,
        language: str = "en",
        voice_id: Optional[str] = None,
        duration: int = 30,
        timeout: int = 300,
        save_locally: bool = True
    ) -> Dict[str, Any]:
        """
        Generate avatar video and wait for completion.

        Args:
            image_url: Source photo URL
            script: Speech script
            language: Language code ('en' or 'zh-TW')
            voice_id: Optional voice ID
            duration: Video duration in seconds
            timeout: Max wait time in seconds
            save_locally: Save video to local storage

        Returns:
            Dict with video_url on success
        """
        logger.info(f"Starting avatar generation - language: {language}")
        logger.info(f"Image URL: {image_url}")
        logger.info(f"Script: {script[:100]}...")

        success, task_id, _ = await self.generate_avatar_video(
            image_url=image_url,
            script=script,
            language=language,
            voice_id=voice_id,
            duration=duration
        )

        if not success:
            return {"success": False, "error": task_id}

        result = await self.wait_for_completion(task_id, timeout)

        if result.get("status") == "succeed":
            video_url = result.get("video_url")
            local_url = video_url

            # Save locally if requested
            if save_locally and video_url:
                try:
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        video_response = await client.get(video_url)
                        if video_response.status_code == 200:
                            STATIC_DIR.mkdir(parents=True, exist_ok=True)
                            filename = f"avatar_{language}_{uuid.uuid4().hex[:8]}.mp4"
                            filepath = STATIC_DIR / filename
                            filepath.write_bytes(video_response.content)
                            local_url = f"/static/materials/{filename}"
                            logger.info(f"Avatar saved to: {local_url}")
                except Exception as e:
                    logger.error(f"Failed to save avatar locally: {e}")

            return {
                "success": True,
                "task_id": task_id,
                "video_url": local_url,
                "remote_url": video_url,
                "language": language,
                "script": script
            }
        else:
            return {
                "success": False,
                "task_id": task_id,
                "error": result.get("error", "Generation failed")
            }


# Singleton instance
_avatar_service: Optional[PolloAvatarService] = None


def get_avatar_service() -> PolloAvatarService:
    """Get or create Avatar service singleton"""
    global _avatar_service
    if _avatar_service is None:
        _avatar_service = PolloAvatarService()
    return _avatar_service
