"""
Gemini Provider - Content Moderation and Emergency Backup.

Supports:
- Content moderation (NSFW detection)
- Interior design (emergency backup for PiAPI)
- Image analysis
"""
import httpx
import asyncio
from typing import Dict, Any
import logging
import os
import base64

from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseProvider):
    """
    Gemini Provider - Content moderation and emergency interior design backup.
    """

    name = "gemini"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set in environment")

        self.client = httpx.AsyncClient(
            timeout=60.0,
            headers={"Content-Type": "application/json"}
        )

    async def health_check(self) -> bool:
        """Check if Gemini is healthy."""
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/models?key={self.api_key}",
                timeout=10.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # CONTENT MODERATION
    # ─────────────────────────────────────────────────────────────────────────

    async def moderate_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check content for moderation issues.

        Args:
            params: {
                "text": str (optional),
                "image_url": str (optional),
                "image_base64": str (optional)
            }

        Returns:
            {
                "success": True,
                "is_safe": bool,
                "categories": {"nsfw": float, "violence": float, ...}
            }
        """
        self._log_request("moderate_content", {"has_text": bool(params.get("text")), "has_image": bool(params.get("image_url") or params.get("image_base64"))})

        parts = []

        # Add moderation prompt
        parts.append({
            "text": """Analyze this content for safety. Rate each category from 0.0 (safe) to 1.0 (unsafe):
- nsfw: Adult or sexual content
- violence: Violent or graphic content
- hate: Hate speech or discrimination
- self_harm: Self-harm or suicide content
- illegal: Illegal activities

Respond ONLY with JSON: {"nsfw": 0.0, "violence": 0.0, "hate": 0.0, "self_harm": 0.0, "illegal": 0.0, "is_safe": true}"""
        })

        # Add text if provided
        if params.get("text"):
            parts.append({"text": f"Content to analyze: {params['text']}"})

        # Add image if provided
        if params.get("image_base64"):
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": params["image_base64"]
                }
            })
        elif params.get("image_url"):
            # Fetch and convert image
            try:
                img_response = await self.client.get(params["image_url"])
                img_data = base64.b64encode(img_response.content).decode()
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": img_data
                    }
                })
            except Exception as e:
                logger.error(f"Failed to fetch image for moderation: {e}")

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 256
            }
        }

        try:
            response = await self.client.post(
                f"{self.BASE_URL}/models/gemini-1.5-flash:generateContent?key={self.api_key}",
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            # Parse response
            text_response = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

            # Try to extract JSON
            import json
            import re

            json_match = re.search(r'\{[^}]+\}', text_response)
            if json_match:
                result = json.loads(json_match.group())
                is_safe = all(v < 0.5 for k, v in result.items() if k != "is_safe")
                result["is_safe"] = is_safe
                return {"success": True, **result}

            # Default safe response
            return {
                "success": True,
                "is_safe": True,
                "categories": {"nsfw": 0.0, "violence": 0.0, "hate": 0.0}
            }

        except Exception as e:
            logger.error(f"Moderation failed: {e}")
            # Default to safe on error
            return {"success": False, "is_safe": True, "error": str(e)}

    # ─────────────────────────────────────────────────────────────────────────
    # INTERIOR DESIGN (Emergency Backup)
    # ─────────────────────────────────────────────────────────────────────────

    async def interior_design(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate interior design suggestions (emergency backup for PiAPI).

        Note: Gemini doesn't generate images directly, so this returns
        a detailed description that can be used with another image generator.

        Args:
            params: {
                "image_url": str,
                "style": str,
                "room_type": str,
                "prompt": str (optional)
            }

        Returns:
            {"success": True, "output": {"description": str, "suggestions": list}}
        """
        self._log_request("interior_design", params)

        parts = [
            {
                "text": f"""As an interior design expert, analyze this room image and provide detailed redesign suggestions.

Style requested: {params.get('style', 'modern')}
Room type: {params.get('room_type', 'living room')}
Additional requirements: {params.get('prompt', 'No specific requirements')}

Provide:
1. A detailed description of the redesigned room (be specific about furniture, colors, materials)
2. Key design elements to add
3. Color palette recommendations
4. Furniture suggestions
5. Lighting recommendations

Format your response as JSON:
{{
  "description": "Detailed room description...",
  "suggestions": ["suggestion1", "suggestion2", ...],
  "color_palette": ["#hex1", "#hex2", ...],
  "furniture": ["item1", "item2", ...],
  "lighting": "Lighting description..."
}}"""
            }
        ]

        # Add image
        if params.get("image_url"):
            try:
                img_response = await self.client.get(params["image_url"])
                img_data = base64.b64encode(img_response.content).decode()
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": img_data
                    }
                })
            except Exception as e:
                logger.error(f"Failed to fetch image: {e}")
                raise Exception(f"Failed to process image: {e}")

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048
            }
        }

        try:
            response = await self.client.post(
                f"{self.BASE_URL}/models/gemini-1.5-pro:generateContent?key={self.api_key}",
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            text_response = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

            # Try to parse JSON response
            import json
            import re

            json_match = re.search(r'\{[\s\S]+\}', text_response)
            if json_match:
                result = json.loads(json_match.group())
                self._log_response("interior_design", True)
                return {"success": True, "output": result}

            # Return raw text if JSON parsing fails
            self._log_response("interior_design", True)
            return {
                "success": True,
                "output": {
                    "description": text_response,
                    "suggestions": [],
                    "is_text_only": True
                }
            }

        except Exception as e:
            self._log_response("interior_design", False, str(e))
            raise Exception(f"Gemini interior design failed: {e}")

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
