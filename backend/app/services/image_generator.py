"""
Image Generation Service using Gemini (Nano Banana)
Generates images from text prompts using Google's Gemini API.
"""
import logging
import base64
import httpx
from typing import Optional, Dict, Any, Tuple
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ImageGeneratorService:
    """
    Image generation service using Gemini (Nano Banana).
    Supports text-to-image generation.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'GEMINI_API_KEY', '')
        # Use gemini-2.0-flash-exp for image generation
        self.model = "gemini-2.0-flash-exp"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def generate_image(
        self,
        prompt: str,
        style: Optional[str] = None,
        aspect_ratio: str = "1:1",
        negative_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate an image from a text prompt.

        Args:
            prompt: Text description of the image to generate
            style: Optional style modifier (e.g., "anime", "realistic", "cinematic")
            aspect_ratio: Image aspect ratio (default "1:1")
            negative_prompt: What to avoid in the image

        Returns:
            Dict with success status, image_data (base64), and metadata
        """
        if not self.api_key:
            return {"success": False, "error": "Gemini API key not configured"}

        # Build the full prompt with style
        full_prompt = self._build_prompt(prompt, style, negative_prompt)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}",
                    json={
                        "contents": [{
                            "parts": [{
                                "text": full_prompt
                            }]
                        }],
                        "generationConfig": {
                            "responseModalities": ["image", "text"],
                            "responseMimeType": "image/png"
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return self._parse_response(data, prompt, style)
                else:
                    error_msg = f"Gemini API error: {response.status_code}"
                    logger.error(f"{error_msg} - {response.text[:200]}")
                    return {"success": False, "error": error_msg}

        except httpx.TimeoutException:
            return {"success": False, "error": "Image generation timed out"}
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            return {"success": False, "error": str(e)}

    def _build_prompt(
        self,
        prompt: str,
        style: Optional[str] = None,
        negative_prompt: Optional[str] = None
    ) -> str:
        """Build the full prompt with style modifiers."""
        parts = [f"Generate a high-quality image: {prompt}"]

        if style:
            style_modifiers = {
                "anime": "in anime art style, vibrant colors, detailed",
                "realistic": "photorealistic, highly detailed, 8K quality",
                "cinematic": "cinematic lighting, movie scene, dramatic",
                "watercolor": "watercolor painting style, soft colors, artistic",
                "oil_painting": "oil painting style, classical art, textured",
                "cyberpunk": "cyberpunk style, neon lights, futuristic",
                "fantasy": "fantasy art style, magical, ethereal",
                "minimalist": "minimalist style, clean, simple",
            }
            modifier = style_modifiers.get(style, style)
            parts.append(modifier)

        if negative_prompt:
            parts.append(f"Avoid: {negative_prompt}")

        return ". ".join(parts)

    def _parse_response(
        self,
        data: Dict[str, Any],
        prompt: str,
        style: Optional[str]
    ) -> Dict[str, Any]:
        """Parse Gemini response and extract image data."""
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                return {"success": False, "error": "No image generated"}

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            for part in parts:
                if "inlineData" in part:
                    inline_data = part["inlineData"]
                    return {
                        "success": True,
                        "image_data": inline_data.get("data"),
                        "mime_type": inline_data.get("mimeType", "image/png"),
                        "prompt": prompt,
                        "style": style
                    }

            return {"success": False, "error": "No image data in response"}

        except Exception as e:
            logger.error(f"Error parsing Gemini response: {e}")
            return {"success": False, "error": str(e)}

    async def save_image_to_storage(
        self,
        image_data: str,
        filename: str,
        mime_type: str = "image/png"
    ) -> Optional[str]:
        """
        Save base64 image data to storage and return URL.
        For now, returns a data URL. In production, upload to S3/GCS.
        """
        # TODO: Implement actual cloud storage upload
        # For now, return base64 data URL
        return f"data:{mime_type};base64,{image_data}"


# Singleton instance
_image_generator: Optional[ImageGeneratorService] = None


def get_image_generator() -> ImageGeneratorService:
    """Get or create image generator singleton"""
    global _image_generator
    if _image_generator is None:
        _image_generator = ImageGeneratorService()
    return _image_generator
