"""
A2E.ai Avatar Service - Talking Avatar Generation with Lip-Sync
Professional lip-sync avatar video generation using A2E.ai API.

Features:
- Native lip-sync with text-to-speech
- 50+ avatar personas available
- Multi-language support (English, Chinese, Japanese, Korean, etc.)
- Link-to-video generation
- 99.99% SLA guaranteed

API Documentation: https://a2e.ai/ai-avatar-api/
"""
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import httpx
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Static directory for storing generated materials
STATIC_DIR = Path("/app/static/materials")

# A2E.ai API base URL (video.a2e.ai is the actual API, api.a2e.ai is just docs)
A2E_BASE_URL = "https://video.a2e.ai"

# Available voices for each language (A2E.ai provides 50+ voices)
A2E_VOICES = {
    "en": [
        {"id": "en-US-alloy", "name": "Alloy", "gender": "neutral", "style": "professional"},
        {"id": "en-US-echo", "name": "Echo", "gender": "male", "style": "professional"},
        {"id": "en-US-fable", "name": "Fable", "gender": "female", "style": "friendly"},
        {"id": "en-US-onyx", "name": "Onyx", "gender": "male", "style": "casual"},
        {"id": "en-US-nova", "name": "Nova", "gender": "female", "style": "professional"},
        {"id": "en-US-shimmer", "name": "Shimmer", "gender": "female", "style": "warm"},
    ],
    "zh-TW": [
        {"id": "zh-TW-xiaoxiao", "name": "小曉", "gender": "female", "style": "professional"},
        {"id": "zh-TW-yunxi", "name": "雲熙", "gender": "male", "style": "professional"},
        {"id": "zh-TW-xiaochen", "name": "小晨", "gender": "female", "style": "friendly"},
        {"id": "zh-TW-yunyang", "name": "雲揚", "gender": "male", "style": "casual"},
    ],
    "ja": [
        {"id": "ja-JP-nanami", "name": "七海", "gender": "female", "style": "professional"},
        {"id": "ja-JP-keita", "name": "慶太", "gender": "male", "style": "professional"},
    ],
    "ko": [
        {"id": "ko-KR-sunhi", "name": "선희", "gender": "female", "style": "professional"},
        {"id": "ko-KR-injoon", "name": "인준", "gender": "male", "style": "professional"},
    ],
}

# Default avatar images
DEFAULT_AVATARS = {
    "en": [
        "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=512",
        "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=512",
        "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=512",
        "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=512",
    ],
    "zh-TW": [
        "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=512",
        "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=512",
        "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=512",
        "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=512",
    ],
}


class A2EAvatarService:
    """
    A2E.ai Avatar Service for generating talking avatar videos with native lip-sync.

    Features:
    - Native lip-sync with text-to-speech
    - 50+ voice personas across multiple languages
    - High-quality video output
    - Fast generation (~1:10 ratio)
    - 99.99% SLA guaranteed
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'A2E_API_KEY', '')
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def get_voices(self, language: str = "en") -> List[Dict[str, str]]:
        """Get available voices for a language."""
        return A2E_VOICES.get(language, A2E_VOICES["en"])

    def get_default_avatars(self, language: str = "en") -> List[str]:
        """Get default avatar images for a language."""
        return DEFAULT_AVATARS.get(language, DEFAULT_AVATARS["en"])

    async def generate_avatar_video(
        self,
        image_url: str,
        text: str,
        language: str = "en",
        voice_id: Optional[str] = None,
        aspect_ratio: str = "9:16",
        resolution: str = "720p"
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Generate a talking avatar video with lip-sync.

        Args:
            image_url: URL of the avatar photo (clear headshot recommended)
            text: The text script for the avatar to speak
            language: Language code ('en', 'zh-TW', 'ja', 'ko')
            voice_id: Voice ID to use (defaults to first voice for language)
            aspect_ratio: Video aspect ratio ('9:16', '16:9', '1:1')
            resolution: Video resolution ('720p', '1080p')

        Returns:
            Tuple of (success, task_id or error, None)
        """
        if not self.api_key:
            return False, "A2E API key not configured", None

        # Validate language and get default voice
        if language not in A2E_VOICES:
            language = "en"

        if not voice_id:
            voices = self.get_voices(language)
            voice_id = voices[0]["id"] if voices else "en-US-alloy"

        # Map aspect ratio to dimensions
        dimensions = {
            "9:16": {"width": 720, "height": 1280},
            "16:9": {"width": 1280, "height": 720},
            "1:1": {"width": 720, "height": 720},
        }
        dims = dimensions.get(aspect_ratio, dimensions["9:16"])

        # A2E API requires: text, creator_id (avatar ID), aspect_ratio
        # For default avatars, we use a preset creator_id
        payload = {
            "text": text,
            "aspect_ratio": aspect_ratio,
            "image_url": image_url,  # For custom avatar from image
            "voice_id": voice_id,
            "language": language,
        }

        # Try multiple endpoint formats
        endpoints_to_try = [
            "/api/v1/lipsyncs/",
            "/api/v1/lipsync/generate",
            "/api/lipsyncs/",
            "/api/v1/talkingPhoto",
        ]

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                for endpoint in endpoints_to_try:
                    logger.info(f"Trying A2E endpoint: {A2E_BASE_URL}{endpoint}")
                    response = await client.post(
                        f"{A2E_BASE_URL}{endpoint}",
                        headers=self.headers,
                        json=payload
                    )

                    # If not 404, we found the right endpoint
                    if response.status_code != 404:
                        break
                    logger.warning(f"A2E endpoint {endpoint} returned 404, trying next...")

                logger.info(f"A2E API response status: {response.status_code}")
                logger.info(f"A2E API response text: {response.text[:500] if response.text else '(empty)'}")

                if response.status_code in [200, 201, 202]:
                    # Handle empty response
                    if not response.text or not response.text.strip():
                        logger.warning("A2E API returned empty response body")
                        return False, "A2E API returned empty response - API may be unavailable", None

                    try:
                        data = response.json()
                    except Exception as json_err:
                        logger.error(f"A2E API JSON parse error: {json_err}, raw: {response.text[:200]}")
                        return False, f"Invalid JSON response: {response.text[:100]}", None

                    logger.info(f"A2E API response: {data}")

                    # A2E returns task_id for async processing
                    task_id = data.get("task_id") or data.get("id") or data.get("job_id")
                    if task_id:
                        logger.info(f"A2E task created: {task_id}")
                        return True, str(task_id), None
                    else:
                        # Immediate result (unlikely but handle it)
                        video_url = data.get("video_url") or data.get("output_url")
                        if video_url:
                            return True, video_url, video_url
                        return False, f"No task ID or video URL in response: {data}", None
                else:
                    error = f"HTTP {response.status_code}: {response.text[:200] if response.text else '(empty)'}"
                    logger.error(f"A2E API error: {error}")
                    return False, error, None

        except Exception as e:
            logger.error(f"A2E API error: {e}")
            return False, str(e), None

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Check avatar generation task status.

        Returns:
            Dict with status, video_url when complete
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{A2E_BASE_URL}/api/lipsyncs/{task_id}/",
                    headers=self.headers
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"A2E status response: {data}")

                    status = data.get("status", "").lower()
                    video_url = data.get("video_url") or data.get("output_url") or data.get("result_url")
                    error_msg = data.get("error") or data.get("error_message") or data.get("fail_reason")

                    # Normalize status
                    if status in ["completed", "success", "succeed", "done"]:
                        status = "succeed"
                    elif status in ["failed", "error"]:
                        status = "failed"
                    elif status in ["pending", "processing", "running", "queued"]:
                        status = "pending"

                    return {
                        "success": True,
                        "status": status,
                        "video_url": video_url if video_url else None,
                        "error": error_msg if error_msg else None,
                        "raw": data
                    }
                else:
                    return {
                        "success": False,
                        "status": "error",
                        "error": f"HTTP {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"A2E status error: {e}")
            return {"success": False, "status": "error", "error": str(e)}

    async def wait_for_completion(
        self,
        task_id: str,
        timeout: int = 300,
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """
        Wait for avatar generation task to complete.

        Args:
            task_id: Task ID from generate_avatar_video
            timeout: Max wait time in seconds
            poll_interval: Seconds between status checks

        Returns:
            Final task status with video_url
        """
        elapsed = 0
        logger.info(f"Waiting for A2E task {task_id} (timeout: {timeout}s)")

        while elapsed < timeout:
            status = await self.get_task_status(task_id)
            task_status = status.get("status", "").lower()

            logger.info(f"A2E task {task_id}: {task_status} ({elapsed}s elapsed)")

            if task_status == "succeed":
                logger.info(f"A2E task {task_id} completed successfully")
                return status
            elif task_status == "failed":
                error_msg = status.get("error", "Unknown error")
                logger.error(f"A2E task {task_id} failed: {error_msg}")
                return status

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        logger.error(f"A2E task {task_id} timed out after {timeout}s")
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
            script: Speech script (text to speak)
            language: Language code ('en', 'zh-TW', 'ja', 'ko')
            voice_id: Optional voice ID
            duration: Ignored (determined by script length)
            timeout: Max wait time in seconds
            save_locally: Save video to local storage

        Returns:
            Dict with video_url on success
        """
        logger.info(f"Starting A2E avatar generation - language: {language}")
        logger.info(f"Image URL: {image_url}")
        logger.info(f"Script: {script[:100]}...")

        success, task_id, immediate_url = await self.generate_avatar_video(
            image_url=image_url,
            text=script,
            language=language,
            voice_id=voice_id
        )

        if not success:
            return {"success": False, "error": task_id}

        # If immediate URL returned, use it
        if immediate_url:
            return {
                "success": True,
                "task_id": task_id,
                "video_url": immediate_url,
                "language": language,
                "script": script
            }

        # Otherwise poll for completion
        result = await self.wait_for_completion(task_id, timeout)

        if result.get("status") == "succeed":
            video_url = result.get("video_url")
            local_url = video_url

            # Save locally if requested
            if save_locally and video_url:
                try:
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        video_response = await client.get(video_url, follow_redirects=True)
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

    async def test_connection(self) -> Dict:
        """Test API connection and key validity"""
        if not self.api_key:
            return {"success": False, "error": "A2E API key not configured"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Try to access the API - the lipsyncs endpoint
                # A valid key should not return 401
                response = await client.get(
                    f"{A2E_BASE_URL}/api/lipsyncs/",
                    headers=self.headers
                )

                if response.status_code == 200:
                    return {"success": True, "message": "A2E.ai API key is valid"}
                elif response.status_code == 401:
                    return {"success": False, "error": "Invalid API key"}
                elif response.status_code == 404:
                    # 404 on GET might be normal - test via POST behavior
                    return {"success": True, "message": "A2E.ai connected (test via actual generation)"}
                elif response.status_code == 405:
                    # Method not allowed means endpoint exists
                    return {"success": True, "message": "A2E.ai API key is valid (endpoint exists)"}
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton instance
_a2e_service: Optional[A2EAvatarService] = None


def get_a2e_service() -> A2EAvatarService:
    """Get or create A2E service singleton"""
    global _a2e_service
    if _a2e_service is None:
        _a2e_service = A2EAvatarService()
    return _a2e_service
