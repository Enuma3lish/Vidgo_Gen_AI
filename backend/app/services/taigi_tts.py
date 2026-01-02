"""
Taigi (Taiwanese/閩南語) TTS Service

Integrates with Taigi TTS API for Taiwanese text-to-speech synthesis.
API Documentation: https://learn-language.tokyo/en/taiwanese-taigi-tts-api

Supported input formats:
- Han Characters (漢字): 你好，台灣！
- Tailo (台羅拼音): Lí-hó, Tâi-uân!

This replaces ATEN 優聲學 as the primary Taiwanese TTS provider.
"""
import httpx
import logging
import asyncio
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


class TaigiTTSClient:
    """
    Client for Taigi TTS API.

    API Features:
    - Supports Taiwanese (台語/閩南語)
    - Input: Han Characters or Tailo romanization
    - Output: WAV audio file
    - Response time: <500ms average
    """

    # API endpoint (placeholder - replace with actual endpoint)
    BASE_URL = "https://api.learn-language.tokyo/v1"

    # Available voice models
    MODELS = {
        "default": "model5",      # Standard voice
        "natural": "model6",      # More natural voice
        "female": "model5_f",     # Female voice (if available)
        "male": "model5_m",       # Male voice (if available)
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Taigi TTS client.

        Args:
            api_key: API key for authentication. Falls back to settings.TAIGI_TTS_API_KEY
        """
        self.api_key = api_key or getattr(settings, 'TAIGI_TTS_API_KEY', None)
        self.timeout = httpx.Timeout(30.0, connect=10.0)

        if not self.api_key:
            logger.warning("Taigi TTS API key not configured. TTS features will be disabled.")

    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def synthesize(
        self,
        text: str,
        model: str = "default",
        output_format: str = "wav"
    ) -> Dict[str, Any]:
        """
        Synthesize Taiwanese speech from text.

        Args:
            text: Taiwanese text (Han Characters or Tailo)
            model: Voice model to use ("default", "natural", "female", "male")
            output_format: Audio format ("wav", "mp3")

        Returns:
            Dict with:
                - success: bool
                - audio_url: URL to generated audio file
                - duration: Audio duration in seconds (if available)
                - error: Error message (if failed)
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": "Taigi TTS API key not configured",
                "pending": True
            }

        # Map model name to API model ID
        model_id = self.MODELS.get(model, self.MODELS["default"])

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.BASE_URL}/tts",
                    headers=self._get_headers(),
                    json={
                        "text": text,
                        "model": model_id,
                        "format": output_format
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "audio_url": data.get("audio_url"),
                        "duration": data.get("duration"),
                        "model": model_id,
                        "text": text
                    }
                elif response.status_code == 401:
                    return {
                        "success": False,
                        "error": "Invalid API key"
                    }
                elif response.status_code == 429:
                    return {
                        "success": False,
                        "error": "Rate limit exceeded"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code}",
                        "details": response.text
                    }

        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "Request timeout"
            }
        except Exception as e:
            logger.error(f"Taigi TTS error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def synthesize_with_retry(
        self,
        text: str,
        model: str = "default",
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        Synthesize with automatic retry on failure.

        Args:
            text: Taiwanese text
            model: Voice model
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            Synthesis result dict
        """
        last_error = None

        for attempt in range(max_retries):
            result = await self.synthesize(text, model)

            if result.get("success"):
                return result

            last_error = result.get("error")

            # Don't retry on auth errors
            if "Invalid API key" in str(last_error):
                return result

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))

        return {
            "success": False,
            "error": f"Failed after {max_retries} attempts: {last_error}"
        }

    async def get_available_voices(self) -> Dict[str, Any]:
        """
        Get list of available voice models.

        Returns:
            Dict with available voices and their descriptions
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": "API key not configured"
            }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.BASE_URL}/voices",
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    return {
                        "success": True,
                        "voices": response.json()
                    }
                else:
                    # Return default voices if endpoint not available
                    return {
                        "success": True,
                        "voices": [
                            {"id": "model5", "name": "標準", "description": "Standard Taiwanese voice"},
                            {"id": "model6", "name": "自然", "description": "Natural sounding voice"}
                        ],
                        "note": "Using default voice list"
                    }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Alternative: Direct integration with tai5-uan5 self-hosted service
class Tai5Uan5Client:
    """
    Client for self-hosted tai5-uan5 (臺灣言語服務) instance.

    GitHub: https://github.com/i3thuan5/tai5-uan5_gian5-gi2_hok8-bu7

    Note: This requires deploying your own instance of the service.
    The repository is archived but the code is still functional.

    Supports:
    - Taiwanese (臺語)
    - Hakka dialects (客話四海大平安五腔)
    - Pangcah (Amis)
    """

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize tai5-uan5 client.

        Args:
            base_url: Base URL of your tai5-uan5 instance
        """
        self.base_url = base_url or getattr(settings, 'TAI5UAN5_BASE_URL', None)
        self.timeout = httpx.Timeout(30.0)

    @property
    def is_configured(self) -> bool:
        """Check if service URL is configured."""
        return bool(self.base_url)

    async def synthesize(
        self,
        text: str,
        language: str = "taiwanese"  # taiwanese, hakka, pangcah
    ) -> Dict[str, Any]:
        """
        Synthesize speech from text.

        Args:
            text: Text in target language
            language: Language code (taiwanese, hakka, pangcah)

        Returns:
            Synthesis result
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": "tai5-uan5 service URL not configured",
                "pending": True
            }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/synthesize",
                    json={
                        "text": text,
                        "language": language
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "audio_url": data.get("audio_url"),
                        "audio_data": data.get("audio_data"),  # Base64 encoded
                        "language": language
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Service error: {response.status_code}"
                    }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Factory function to get the appropriate TTS client
def get_taiwanese_tts_client() -> TaigiTTSClient:
    """
    Get the configured Taiwanese TTS client.

    Priority:
    1. TaigiTTSClient (commercial API)
    2. Tai5Uan5Client (self-hosted)

    Returns:
        TTS client instance
    """
    # Prefer commercial API if configured
    taigi_client = TaigiTTSClient()
    if taigi_client.is_configured:
        return taigi_client

    # Fallback to self-hosted
    tai5uan5_client = Tai5Uan5Client()
    if tai5uan5_client.is_configured:
        return tai5uan5_client

    # Return unconfigured client (will return pending status)
    logger.warning("No Taiwanese TTS service configured")
    return taigi_client
