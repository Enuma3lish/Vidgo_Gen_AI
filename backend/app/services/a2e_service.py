"""
A2E.ai Avatar Service - Talking Avatar Generation with Lip-Sync
Professional lip-sync avatar video generation using A2E.ai API.

Features:
- Native lip-sync with text-to-speech
- 50+ avatar personas available
- Multi-language support (English, Chinese, Japanese, Korean, etc.)
- Link-to-video generation
- 99.99% SLA guaranteed
- Asian-only avatar filtering (Chinese/Taiwanese/Asian avatars only)
- Gender-voice matching enforcement

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

# ---------------------------------------------------------------------------
# Asian Avatar Filter Keywords
# Used to identify Asian/Chinese/Taiwanese avatars from character lists.
# Avatars whose name, tag, or description match any of these keywords
# (case-insensitive) are considered valid. All others are rejected.
# ---------------------------------------------------------------------------
ASIAN_AVATAR_KEYWORDS: List[str] = [
    # Ethnicity / region tags
    "asian", "chinese", "taiwanese", "china", "taiwan",
    "japanese", "korean", "vietnamese", "thai", "filipino",
    "東方", "亞洲", "中文", "華人", "台灣", "中國",
    # Common Chinese / Taiwanese given-name fragments
    "xiao", "wei", "mei", "ling", "yu", "jia", "min", "hui",
    "chen", "wang", "zhang", "liu", "li", "yang", "huang", "zhou",
    "lin", "wu", "xu", "sun", "zhu", "gao", "he", "guo",
    # Common Chinese character name components
    "小", "大", "曉", "雲", "美", "麗", "華", "明", "志", "文",
    "婷", "萱", "欣", "宜", "芳", "玲", "珍", "淑", "惠", "雅",
    # Japanese name fragments
    "yuki", "hana", "sato", "taka", "nana", "keita", "miku",
    # Korean name fragments
    "kim", "park", "choi", "jung", "yoon", "seo", "hyun",
]

# ---------------------------------------------------------------------------
# Voice-to-Gender Mapping
# Maps every known A2E voice ID to its gender so we can enforce that
# male avatars only use male voices and female avatars only use female voices.
# ---------------------------------------------------------------------------
VOICE_GENDER_MAP: Dict[str, str] = {
    # English voices
    "en-US-alloy": "neutral",
    "en-US-echo": "male",
    "en-US-fable": "female",
    "en-US-onyx": "male",
    "en-US-nova": "female",
    "en-US-shimmer": "female",
    # Traditional Chinese (Taiwan) voices
    "zh-TW-xiaoxiao": "female",
    "zh-TW-xiaochen": "female",
    "zh-TW-xiaomeng": "female",
    "zh-TW-xiaoxuan": "female",
    "zh-TW-yunxi": "male",
    "zh-TW-yunyang": "male",
    "zh-TW-yunjie": "male",
    "zh-TW-yunhao": "male",
    # Japanese voices
    "ja-JP-nanami": "female",
    "ja-JP-keita": "male",
    # Korean voices
    "ko-KR-sunhi": "female",
    "ko-KR-injoon": "male",
}

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
        {"id": "zh-TW-xiaochen", "name": "小晨", "gender": "female", "style": "friendly"},
        {"id": "zh-TW-xiaomeng", "name": "曉夢", "gender": "female", "style": "warm"},
        {"id": "zh-TW-xiaoxuan", "name": "小萱", "gender": "female", "style": "casual"},
        {"id": "zh-TW-yunxi", "name": "雲熙", "gender": "male", "style": "professional"},
        {"id": "zh-TW-yunyang", "name": "雲揚", "gender": "male", "style": "casual"},
        {"id": "zh-TW-yunjie", "name": "雲傑", "gender": "male", "style": "friendly"},
        {"id": "zh-TW-yunhao", "name": "雲皓", "gender": "male", "style": "professional"},
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

# Default avatar images - SYNCED with frontend AIAvatar.vue (Asian/Chinese, color)
DEFAULT_AVATARS = {
    "en": [
        "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=512&fit=crop&crop=faces",
        "https://images.unsplash.com/photo-1758600431229-191932ccee81?w=512&fit=crop&crop=faces",
        "https://images.unsplash.com/photo-1534751516642-a1af1ef26a56?w=512&fit=crop&crop=faces",
        "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=512&fit=crop&crop=faces",
    ],
    "zh-TW": [
        "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=512&fit=crop&crop=faces",
        "https://images.unsplash.com/photo-1758600431229-191932ccee81?w=512&fit=crop&crop=faces",
        "https://images.unsplash.com/photo-1534751516642-a1af1ef26a56?w=512&fit=crop&crop=faces",
        "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=512&fit=crop&crop=faces",
    ],
}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def filter_asian_avatars(characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter a list of avatar characters to include only Asian avatars.

    An avatar is considered Asian if any of its searchable text fields
    (name, tag, description, ethnicity, region) contain at least one of
    the keywords defined in ASIAN_AVATAR_KEYWORDS (case-insensitive match).

    Args:
        characters: Raw list of character dicts from the A2E API.

    Returns:
        Filtered list containing only Asian/Chinese/Taiwanese avatars.
        If the filter yields zero results, the original list is returned
        with a warning logged (to avoid breaking production).
    """
    if not characters:
        return characters

    keywords_lower = [kw.lower() for kw in ASIAN_AVATAR_KEYWORDS]

    filtered: List[Dict[str, Any]] = []
    for char in characters:
        # Build a single searchable string from all relevant fields
        searchable_parts = [
            str(char.get("name", "")),
            str(char.get("tag", "")),
            str(char.get("tags", "")),
            str(char.get("description", "")),
            str(char.get("ethnicity", "")),
            str(char.get("region", "")),
            str(char.get("category", "")),
            str(char.get("label", "")),
        ]
        searchable = " ".join(searchable_parts).lower()

        if any(kw in searchable for kw in keywords_lower):
            filtered.append(char)

    if not filtered:
        logger.warning(
            "Asian avatar filter matched 0 out of %d characters. "
            "Returning original list to avoid empty results. "
            "Consider updating ASIAN_AVATAR_KEYWORDS.",
            len(characters),
        )
        return characters

    logger.info(
        "Asian avatar filter: %d/%d characters passed",
        len(filtered),
        len(characters),
    )
    return filtered


def validate_avatar_voice_gender(avatar_gender: str, voice_id: str) -> None:
    """
    Validate that the avatar gender matches the voice gender.

    Rules:
    - Male avatars can ONLY use male or neutral voices.
    - Female avatars can ONLY use female or neutral voices.
    - Neutral avatars can use any voice.
    - Unknown voice IDs are rejected to prevent accidental mismatches.

    Args:
        avatar_gender: Gender of the avatar ("male", "female", or "neutral").
        voice_id: The voice identifier string (e.g. "en-US-echo").

    Raises:
        ValueError: If the combination is invalid.
    """
    avatar_gender = avatar_gender.strip().lower()
    voice_id = voice_id.strip()

    # Neutral avatars accept any voice
    if avatar_gender == "neutral":
        return

    voice_gender = VOICE_GENDER_MAP.get(voice_id)

    if voice_gender is None:
        raise ValueError(
            f"Unknown voice ID '{voice_id}'. Cannot verify gender match. "
            f"Known voices: {sorted(VOICE_GENDER_MAP.keys())}"
        )

    # Neutral voices are acceptable for any avatar gender
    if voice_gender == "neutral":
        return

    if avatar_gender != voice_gender:
        raise ValueError(
            f"Gender mismatch: {avatar_gender} avatar cannot use "
            f"{voice_gender} voice '{voice_id}'. "
            f"Please select a {avatar_gender} or neutral voice."
        )


class A2EAvatarService:
    """
    A2E.ai Avatar Service for generating talking avatar videos with native lip-sync.

    Workflow:
    1. Generate TTS audio: POST /api/v1/video/send_tts
    2. Generate video: POST /api/v1/video/generate (with audioSrc)
    3. Check status: GET /api/v1/video/awsResult?_id={task_id}

    Features:
    - Native lip-sync with text-to-speech
    - 50+ voice personas across multiple languages
    - High-quality video output
    - Fast generation (~1:5 ratio for processing)
    - 99.99% SLA guaranteed
    - Asian-only avatar enforcement
    - Gender-voice matching validation

    API Documentation: https://api.a2e.ai/
    """

    # Default TTS voice ID (Brian - English)
    DEFAULT_TTS_ID = "6625ebd4613f49985c349f95"

    def __init__(self, api_key: Optional[str] = None, anchor_id: Optional[str] = None):
        """
        Initialize A2E Avatar Service.

        Args:
            api_key: A2E API Bearer token (from settings.A2E_API_KEY)
            anchor_id: Default anchor/avatar ID (from settings.A2E_DEFAULT_CREATOR_ID)
        """
        self.api_key = api_key or settings.A2E_API_KEY
        # Default anchor_id for avatars
        self.default_anchor_id = anchor_id or settings.A2E_DEFAULT_CREATOR_ID

        # Headers for Bearer token auth
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            "x-lang": "en-US"
        }

    def get_voices(self, language: str = "en") -> List[Dict[str, str]]:
        """Get available voices for a language."""
        return A2E_VOICES.get(language, A2E_VOICES["en"])

    def get_voices_for_gender(self, language: str = "en", gender: str = "neutral") -> List[Dict[str, str]]:
        """
        Get available voices filtered by avatar gender compatibility.

        Args:
            language: Language code.
            gender: Avatar gender ("male", "female", "neutral").

        Returns:
            List of voice dicts that are compatible with the given avatar gender.
        """
        all_voices = self.get_voices(language)
        gender = gender.strip().lower()

        if gender == "neutral":
            return all_voices

        compatible = []
        for voice in all_voices:
            voice_gender = voice.get("gender", "neutral").lower()
            if voice_gender == gender or voice_gender == "neutral":
                compatible.append(voice)

        return compatible if compatible else all_voices

    def get_default_avatars(self, language: str = "en") -> List[str]:
        """Get default avatar images for a language."""
        return DEFAULT_AVATARS.get(language, DEFAULT_AVATARS["en"])

    async def get_character_list(self, asian_only: bool = True) -> Dict[str, Any]:
        """
        Get list of available avatar characters/anchors.

        Args:
            asian_only: If True (default), filter to Asian avatars only.

        Returns:
            Dict with success status and list of anchors
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{A2E_BASE_URL}/api/v1/anchor/character_list",
                    headers=self.headers
                )

                if response.status_code == 200:
                    data = response.json()
                    anchors = data.get("data", [])
                    logger.info(f"A2E character list: {len(anchors)} anchors found (raw)")

                    # Apply Asian-only filter
                    if asian_only:
                        anchors = filter_asian_avatars(anchors)
                        logger.info(f"A2E character list: {len(anchors)} anchors after Asian filter")

                    return {"success": True, "anchors": anchors}
                else:
                    logger.error(f"A2E character list failed: {response.status_code}")
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"A2E character list error: {e}")
            return {"success": False, "error": str(e)}

    async def generate_tts_audio(
        self,
        text: str,
        tts_id: Optional[str] = None,
        speech_rate: float = 1.0
    ) -> Tuple[bool, str]:
        """
        Generate TTS audio from text.

        Args:
            text: Text to convert to speech
            tts_id: TTS voice ID (24-char hex, default: Brian)
            speech_rate: Speech speed (1.0 = normal)

        Returns:
            Tuple of (success, audio_url or error)
        """
        tts_id = tts_id or self.DEFAULT_TTS_ID

        payload = {
            "msg": text,
            "tts_id": tts_id,
            "speechRate": speech_rate
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{A2E_BASE_URL}/api/v1/video/send_tts",
                    headers=self.headers,
                    json=payload
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        audio_url = data.get("data")
                        logger.info(f"A2E TTS generated: {audio_url[:50]}...")
                        return True, audio_url
                    else:
                        error = data.get("msg", "TTS generation failed")
                        logger.error(f"A2E TTS error: {error}")
                        return False, error
                else:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"A2E TTS error: {error}")
                    return False, error

        except Exception as e:
            logger.error(f"A2E TTS error: {e}")
            return False, str(e)

    async def generate_avatar_video(
        self,
        image_url: str,
        text: str,
        language: str = "en",
        voice_id: Optional[str] = None,
        aspect_ratio: str = "9:16",
        resolution: str = "720p",
        anchor_id: Optional[str] = None,
        avatar_gender: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Generate a talking avatar video with lip-sync.

        Enforces:
        - Gender-voice matching when avatar_gender is provided.

        Workflow:
        1. Validate gender-voice combination (if avatar_gender supplied)
        2. Generate TTS audio from text
        3. Submit video generation with audio and anchor

        Args:
            image_url: Not used (kept for compatibility)
            text: The text script for the avatar to speak
            language: Language code ('en', 'zh-TW', 'ja', 'ko')
            voice_id: TTS voice ID (24-char hex string)
            aspect_ratio: Not used by this endpoint
            resolution: Not used by this endpoint
            anchor_id: Specific anchor/avatar ID (uses default if not provided)
            avatar_gender: Gender of the selected avatar ("male"/"female"/"neutral").
                           When provided, the voice_id is validated against it.

        Returns:
            Tuple of (success, task_id or error, None)
        """
        if not self.api_key:
            return False, "A2E API key not configured", None

        # Use provided anchor_id or default
        use_anchor_id = anchor_id or self.default_anchor_id
        if not use_anchor_id:
            return False, "No anchor_id configured. Get one from /api/v1/anchor/character_list", None

        # --- Gender-voice validation ---
        if avatar_gender and voice_id:
            try:
                validate_avatar_voice_gender(avatar_gender, voice_id)
                logger.info(
                    f"Gender-voice validation passed: {avatar_gender} avatar + voice {voice_id}"
                )
            except ValueError as e:
                logger.warning(f"Gender-voice validation failed: {e}")
                return False, str(e), None

        # Step 1: Generate TTS audio
        logger.info(f"Step 1: Generating TTS audio for: {text[:50]}...")
        tts_success, audio_result = await self.generate_tts_audio(text, voice_id)
        if not tts_success:
            return False, f"TTS failed: {audio_result}", None

        audio_url = audio_result

        # Step 2: Generate video
        logger.info(f"Step 2: Generating video with anchor_id={use_anchor_id}")
        payload = {
            "anchor_id": use_anchor_id,
            "audioSrc": audio_url,
            "anchor_type": 0  # 0 = public/shared anchor
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{A2E_BASE_URL}/api/v1/video/generate",
                    headers=self.headers,
                    json=payload
                )

                logger.info(f"A2E video generate status: {response.status_code}")
                logger.debug(f"A2E video generate response: {response.text[:500]}")

                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        task_data = data.get("data", {})
                        task_id = task_data.get("_id")
                        if task_id:
                            logger.info(f"A2E video task created: {task_id}")
                            return True, str(task_id), None
                        return False, "No task ID in response", None
                    else:
                        error = data.get("msg", "Video generation failed")
                        logger.error(f"A2E video error: {error}")
                        return False, error, None
                else:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"A2E video error: {error}")
                    return False, error, None

        except Exception as e:
            logger.error(f"A2E video error: {e}")
            return False, str(e), None

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Check avatar generation task status.

        A2E Status: POST /api/v1/video/awsResult with {"_id": task_id}
        Status values: init, process, success, failed

        Returns:
            Dict with status, video_url when complete
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # A2E requires POST with _id in body
                response = await client.post(
                    f"{A2E_BASE_URL}/api/v1/video/awsResult",
                    headers=self.headers,
                    json={"_id": task_id}
                )

                logger.debug(f"A2E status check for {task_id}: HTTP {response.status_code}")

                if response.status_code == 200:
                    data = response.json()

                    if data.get("code") == 0:
                        # Response is in data array
                        tasks = data.get("data", [])
                        if tasks:
                            task = tasks[0]  # First matching task
                            status = task.get("status", "").lower()
                            video_url = task.get("result")
                            error_msg = task.get("error") or task.get("fail_reason")
                            progress = task.get("process", 0)

                            logger.debug(f"A2E task {task_id}: status={status}, progress={progress}%")

                            # Normalize status
                            if status == "success":
                                status = "succeed"
                            elif status in ["failed", "error", "fail"]:
                                status = "failed"
                            elif status in ["init", "process", "processing"]:
                                status = "pending"

                            return {
                                "success": True,
                                "status": status,
                                "video_url": video_url if video_url else None,
                                "progress": progress,
                                "error": error_msg if error_msg else None,
                                "raw": task
                            }
                        else:
                            return {
                                "success": False,
                                "status": "error",
                                "error": "Task not found"
                            }
                    else:
                        error = data.get("msg", "Status check failed")
                        return {
                            "success": False,
                            "status": "error",
                            "error": error
                        }
                else:
                    return {
                        "success": False,
                        "status": "error",
                        "error": f"HTTP {response.status_code}: {response.text[:100] if response.text else ''}"
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
        save_locally: bool = True,
        avatar_gender: Optional[str] = None
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
            avatar_gender: Avatar gender for voice validation ("male"/"female"/"neutral")

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
            voice_id=voice_id,
            avatar_gender=avatar_gender
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
        """Test API connection and configuration validity"""
        # Check required configuration
        if not self.api_key:
            return {
                "success": False,
                "error": "A2E_API_KEY not configured",
                "config": {
                    "api_key_set": False,
                    "anchor_id_set": bool(self.default_anchor_id)
                }
            }

        try:
            # Test by fetching the character list (with Asian filter)
            result = await self.get_character_list(asian_only=True)

            if result.get("success"):
                anchors = result.get("anchors", [])
                anchor_info = f"{len(anchors)} Asian anchors available"

                if not self.default_anchor_id:
                    return {
                        "success": True,
                        "message": f"A2E.ai connected - {anchor_info}",
                        "warning": "A2E_DEFAULT_CREATOR_ID not set. Using first available anchor.",
                        "suggested_anchor": anchors[0].get("_id") if anchors else None
                    }

                return {
                    "success": True,
                    "message": f"A2E.ai connected - {anchor_info}",
                    "config": {
                        "anchor_id": self.default_anchor_id
                    }
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to fetch character list"),
                    "note": "Check if A2E_API_KEY is valid"
                }

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
