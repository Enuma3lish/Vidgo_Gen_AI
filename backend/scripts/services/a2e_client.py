"""
A2E.ai Client - Avatar Video with Lip-Sync

API: https://video.a2e.ai/api/v1
Two-step process:
1. Generate TTS audio via /video/send_tts
2. Generate avatar video via /video/generate

IMPORTANT: Anchors must be created first via video.a2e.ai web interface.
Set A2E_DEFAULT_ANCHOR_ID environment variable with your anchor ID.

Cost: ~$0.10 per video
"""
import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List

import httpx

logger = logging.getLogger(__name__)

# Output directory
OUTPUT_DIR = Path("/app/static/materials")


class A2EClient:
    """A2E.ai client for avatar video generation with lip-sync."""

    # Docs: https://api.a2e.ai/ai-avatar-api-766435m0
    # Note: historically this API has been served from video.a2e.ai; the path is /api/v1.
    BASE_URL = os.getenv("A2E_BASE_URL", "https://video.a2e.ai/api/v1")

    def __init__(self, api_key: str, default_anchor_id: Optional[str] = None):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # Get default anchor from param or environment
        self.default_anchor_id = default_anchor_id or os.getenv("A2E_DEFAULT_ANCHOR_ID", "")
        self._voices_cache: Optional[List[Dict]] = None

    def has_anchor(self) -> bool:
        """Check if a default anchor is configured."""
        return bool(self.default_anchor_id)

    async def get_characters(self, char_type: str = None) -> List[Dict[str, Any]]:
        """
        Get available character/anchor list from A2E.

        Args:
            char_type: Filter by type ('default', 'public', 'custom'). None for all.

        Returns:
            List of characters with _id (anchor_id), name, lang, video_cover, etc.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {"type": char_type} if char_type else {}
                response = await client.get(
                    f"{self.BASE_URL}/anchor/character_list",
                    headers=self.headers,
                    params=params
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        characters = data.get("data", [])
                        logger.info(f"[A2E] Found {len(characters)} characters")
                        return characters
                logger.warning(f"[A2E] Failed to get characters: {response.text[:200]}")
        except Exception as e:
            logger.error(f"[A2E] Error getting characters: {e}")
        return []

    async def get_voices(self) -> List[Dict[str, Any]]:
        """
        Get available TTS voice list (flattened).

        Returns list of voices with: value (tts_id), label (name), ttsRate, gender
        """
        if self._voices_cache:
            return self._voices_cache

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/anchor/voice_list",
                    headers=self.headers
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        # Flatten nested structure: [{label: "female", children: [...]}]
                        voices = []
                        for gender_group in data.get("data", []):
                            gender = gender_group.get("value", "")
                            for voice in gender_group.get("children", []):
                                voice["gender"] = gender
                                voice["tts_id"] = voice.get("value")  # Add tts_id alias
                                voices.append(voice)
                        self._voices_cache = voices
                        logger.info(f"[A2E] Found {len(self._voices_cache)} voices")
                        return self._voices_cache
                logger.warning(f"[A2E] Failed to get voices: {response.text[:200]}")
        except Exception as e:
            logger.error(f"[A2E] Error getting voices: {e}")
        return []

    async def generate_tts(
        self,
        text: str,
        tts_id: str,
        speech_rate: float = 1.0
    ) -> Dict[str, Any]:
        """
        Generate TTS audio from text.

        Args:
            text: Text to convert to speech
            tts_id: Voice ID from voice_list
            speech_rate: Speed multiplier (default 1.0)

        Returns:
            {
                "success": True/False,
                "audio_url": str (URL of generated audio),
                "error": str (if failed)
            }
        """
        if not self.api_key:
            return {"success": False, "error": "A2E API key not configured"}

        logger.info(f"[A2E] Generating TTS: {text[:50]}...")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/video/send_tts",
                    headers=self.headers,
                    json={
                        "msg": text,
                        "speechRate": speech_rate,
                        "tts_id": tts_id
                    }
                )

                if response.status_code != 200:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"[A2E] TTS failed: {error}")
                    return {"success": False, "error": error}

                data = response.json()
                if data.get("code") == 0:
                    audio_url = data.get("data")
                    if audio_url:
                        logger.info(f"[A2E] TTS generated: {audio_url[:60]}...")
                        return {"success": True, "audio_url": audio_url}
                    return {"success": False, "error": "No audio URL in response"}

                error = data.get("msg", "Unknown TTS error")
                return {"success": False, "error": error}

        except Exception as e:
            logger.exception(f"[A2E] TTS Exception: {e}")
            return {"success": False, "error": str(e)}

    async def generate_video(
        self,
        anchor_id: str,
        audio_url: str,
        anchor_type: int = 0,
        save_locally: bool = True,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Generate avatar video with audio.

        Args:
            anchor_id: Avatar ID from character_list or custom anchor
            audio_url: URL of audio file (from TTS or external)
            anchor_type: 0=public character, 1=photo, 2=video (default 0)
            save_locally: Save to local file (default True)
            language: Language code for filename

        Returns:
            {
                "success": True/False,
                "video_url": str (local path or remote URL),
                "error": str (if failed)
            }
        """
        if not self.api_key:
            return {"success": False, "error": "A2E API key not configured"}

        logger.info(f"[A2E] Generating video with anchor={anchor_id}")

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Create video generation task
                response = await client.post(
                    f"{self.BASE_URL}/video/generate",
                    headers=self.headers,
                    json={
                        "anchor_id": anchor_id,
                        "anchor_type": anchor_type,
                        "audioSrc": audio_url
                    }
                )

                if response.status_code not in [200, 201, 202]:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"[A2E] Generate failed: {error}")
                    return {"success": False, "error": error}

                data = response.json()

                if data.get("code") != 0:
                    error = data.get("msg", "Unknown error")
                    logger.error(f"[A2E] Generate error: {error}")
                    return {"success": False, "error": error}

                # Task ID is in _id field
                task_id = data.get("data", {}).get("_id")
                if not task_id:
                    return {"success": False, "error": "No _id in response"}

                logger.info(f"[A2E] Task created: {task_id}")

                # Poll for result
                # Docs: POST /api/v1/video/awsResult with body {"_id": "..."}
                # Response: data: [{status: "success"|"fail"|..., result: "<mp4 url>"}]
                for _attempt in range(120):
                    await asyncio.sleep(5)

                    status_resp = await client.post(
                        f"{self.BASE_URL}/video/awsResult",
                        headers=self.headers,
                        json={"_id": task_id}
                    )

                    if status_resp.status_code != 200:
                        continue

                    status_data = status_resp.json()
                    if status_data.get("code") != 0:
                        continue

                    items = status_data.get("data") or []
                    task_info = items[0] if isinstance(items, list) and items else {}

                    status = (task_info.get("status") or "").lower()
                    # Status values per docs: init/start/pending/process/copy/success/fail
                    if status in {"success", "completed"}:
                        video_url = task_info.get("result") or task_info.get("video_url")
                        if not video_url:
                            return {"success": False, "error": "No result URL in completed task"}

                        if save_locally:
                            local_path = await self._download(client, video_url, language)
                            if local_path:
                                logger.info(f"[A2E] Saved: {local_path}")
                                return {"success": True, "video_url": local_path}

                        return {"success": True, "video_url": video_url}

                    if status in {"fail", "failed", "error"}:
                        error = task_info.get("msg") or task_info.get("error") or "Task failed"
                        logger.error(f"[A2E] Task failed: {error}")
                        return {"success": False, "error": error}

                return {"success": False, "error": "Timeout (10 min)"}

        except Exception as e:
            logger.exception(f"[A2E] Exception: {e}")
            return {"success": False, "error": str(e)}

    async def generate_avatar(
        self,
        script: str,
        language: str = "en",
        anchor_id: Optional[str] = None,
        tts_id: Optional[str] = None,
        save_locally: bool = True
    ) -> Dict[str, Any]:
        """
        Generate avatar video with lip-sync (full pipeline).

        Two-step process:
        1. Generate TTS audio from script
        2. Generate avatar video with audio

        Args:
            script: Text for avatar to speak
            language: Language code (en, zh-TW, ja, ko, es)
            anchor_id: Anchor ID (uses default_anchor_id if not specified)
            tts_id: Optional TTS voice ID (uses first available if not specified)
            save_locally: Save to local file (default True)

        Returns:
            {
                "success": True/False,
                "video_url": str (local path or remote URL),
                "audio_url": str (TTS audio URL),
                "error": str (if failed)
            }
        """
        if not self.api_key:
            return {"success": False, "error": "A2E API key not configured"}

        logger.info(f"[A2E] Generating avatar ({language}): {script[:50]}...")

        try:
            # Step 0: Get anchor_id
            if not anchor_id:
                anchor_id = self.default_anchor_id

            if not anchor_id:
                # Try to get from public character list
                characters = await self.get_characters()
                if characters:
                    # Use first available character
                    anchor_id = characters[0].get("_id")
                    logger.info(f"[A2E] Using public character: {anchor_id}")
                else:
                    return {
                        "success": False,
                        "error": "No anchors available. Set A2E_DEFAULT_ANCHOR_ID or check API access."
                    }
            else:
                logger.info(f"[A2E] Using anchor: {anchor_id}")

            if not tts_id:
                voices = await self.get_voices()
                if not voices:
                    return {"success": False, "error": "No voices available"}
                # Try to find matching language voice
                for voice in voices:
                    voice_lang = voice.get("language", "").lower()
                    if language.lower() in voice_lang or voice_lang in language.lower():
                        tts_id = voice.get("tts_id")
                        break
                if not tts_id:
                    # Use first available voice
                    tts_id = voices[0].get("tts_id")
                logger.info(f"[A2E] Using voice: {tts_id}")

            # Step 1: Generate TTS audio
            tts_result = await self.generate_tts(script, tts_id)
            if not tts_result.get("success"):
                return {"success": False, "error": f"TTS failed: {tts_result.get('error')}"}

            audio_url = tts_result["audio_url"]

            # Step 2: Generate video with audio
            video_result = await self.generate_video(
                anchor_id=anchor_id,
                audio_url=audio_url,
                save_locally=save_locally,
                language=language
            )

            if video_result.get("success"):
                video_result["audio_url"] = audio_url

            return video_result

        except Exception as e:
            logger.exception(f"[A2E] Exception: {e}")
            return {"success": False, "error": str(e)}

    async def _download(self, client: httpx.AsyncClient, url: str, language: str) -> Optional[str]:
        """Download video and save locally."""
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            response = await client.get(url, follow_redirects=True)
            if response.status_code == 200:
                filename = f"avatar_{language}_{uuid.uuid4().hex[:8]}.mp4"
                filepath = OUTPUT_DIR / filename
                filepath.write_bytes(response.content)
                return f"/static/materials/{filename}"
        except Exception as e:
            logger.warning(f"[A2E] Download failed: {e}")
        return None
