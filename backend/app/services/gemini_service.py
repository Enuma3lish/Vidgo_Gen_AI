"""
Gemini AI Service
Prompt enhancement, content moderation, and embedding generation.
Uses Google's Gemini API for LLM capabilities.
"""
import asyncio
import logging
import hashlib
from typing import Optional, Dict, Any, List, Tuple
import httpx
import json

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Content moderation categories
BLOCKED_CATEGORIES = [
    "adult",
    "violence",
    "hate_speech",
    "harassment",
    "dangerous_content",
    "illegal_activities",
    "weapons",
    "drugs",
    "gambling"
]


class GeminiService:
    """
    Gemini AI Service for prompt enhancement and content moderation.

    Features:
    - Prompt enhancement for better image/video generation
    - Content moderation (detect illegal/18+ content)
    - Text embedding generation for similarity matching
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'GEMINI_API_KEY', '')

    def _get_headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json"}

    # =========================================================================
    # Prompt Enhancement
    # =========================================================================

    async def enhance_prompt(
        self,
        user_prompt: str,
        category: str = "product",
        style: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enhance user prompt for better image/video generation.

        Args:
            user_prompt: Original user prompt
            category: Content category (product, fashion, food, etc.)
            style: Optional style preference

        Returns:
            Dict with enhanced_prompt, keywords, etc.
        """
        if not self.api_key:
            # Return original prompt if no API key
            return {
                "success": True,
                "original_prompt": user_prompt,
                "enhanced_prompt": user_prompt,
                "keywords": [],
                "category": category
            }

        system_prompt = """You are an expert prompt engineer for AI image and video generation.
Your task is to enhance user prompts to create better, more detailed prompts for product advertising images and videos.

Guidelines:
1. Keep the core intent of the original prompt
2. Add specific visual details (lighting, angle, background)
3. Include quality enhancers (high quality, detailed, professional)
4. Make it suitable for product advertising
5. Keep it concise but descriptive (max 100 words)
6. Output ONLY the enhanced prompt, nothing else

Category context: {category}
Style preference: {style}"""

        prompt = f"""Enhance this prompt for AI image generation:

Original: {user_prompt}

Enhanced prompt:"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/models/gemini-2.0-flash:generateContent",
                    params={"key": self.api_key},
                    headers=self._get_headers(),
                    json={
                        "contents": [
                            {
                                "role": "user",
                                "parts": [{"text": system_prompt.format(category=category, style=style or "any")}]
                            },
                            {
                                "role": "model",
                                "parts": [{"text": "I understand. I will enhance prompts for product advertising images. Please provide the prompt."}]
                            },
                            {
                                "role": "user",
                                "parts": [{"text": prompt}]
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.7,
                            "maxOutputTokens": 200
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            enhanced = parts[0].get("text", "").strip()
                            # Clean up the response
                            enhanced = enhanced.replace("Enhanced prompt:", "").strip()
                            enhanced = enhanced.strip('"').strip()

                            return {
                                "success": True,
                                "original_prompt": user_prompt,
                                "enhanced_prompt": enhanced if enhanced else user_prompt,
                                "category": category,
                                "style": style
                            }

                    return {
                        "success": True,
                        "original_prompt": user_prompt,
                        "enhanced_prompt": user_prompt,
                        "category": category
                    }
                else:
                    logger.error(f"Gemini API error: {response.status_code} - {response.text[:200]}")
                    return {
                        "success": False,
                        "original_prompt": user_prompt,
                        "enhanced_prompt": user_prompt,
                        "error": f"API error: {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Gemini enhance prompt error: {e}")
            return {
                "success": False,
                "original_prompt": user_prompt,
                "enhanced_prompt": user_prompt,
                "error": str(e)
            }

    # =========================================================================
    # Content Moderation
    # =========================================================================

    async def moderate_content(self, text: str) -> Dict[str, Any]:
        """
        Check if content is safe (no illegal or 18+ content).

        Args:
            text: Text to moderate

        Returns:
            Dict with is_safe, categories, reason
        """
        if not self.api_key:
            # Allow all content if no API key (for testing)
            return {
                "success": True,
                "is_safe": True,
                "categories": [],
                "reason": None
            }

        moderation_prompt = """Analyze the following text and determine if it contains any inappropriate content.

Check for:
1. Adult/sexual content
2. Violence or gore
3. Hate speech or discrimination
4. Harassment or bullying
5. Dangerous activities
6. Illegal activities
7. Weapons or explosives
8. Drug-related content
9. Gambling promotion

Text to analyze:
"{text}"

Respond in JSON format:
{{"is_safe": true/false, "categories": ["list of violated categories"], "reason": "explanation if not safe"}}"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/models/gemini-2.0-flash:generateContent",
                    params={"key": self.api_key},
                    headers=self._get_headers(),
                    json={
                        "contents": [
                            {
                                "role": "user",
                                "parts": [{"text": moderation_prompt.format(text=text)}]
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.1,
                            "maxOutputTokens": 200
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            result_text = parts[0].get("text", "").strip()
                            # Try to parse JSON from response
                            try:
                                # Extract JSON from response
                                start = result_text.find("{")
                                end = result_text.rfind("}") + 1
                                if start >= 0 and end > start:
                                    json_str = result_text[start:end]
                                    result = json.loads(json_str)
                                    return {
                                        "success": True,
                                        "is_safe": result.get("is_safe", True),
                                        "categories": result.get("categories", []),
                                        "reason": result.get("reason")
                                    }
                            except json.JSONDecodeError:
                                pass

                    # Default to safe if parsing fails
                    return {
                        "success": True,
                        "is_safe": True,
                        "categories": [],
                        "reason": None
                    }
                else:
                    logger.error(f"Gemini moderation error: {response.status_code}")
                    return {
                        "success": False,
                        "is_safe": True,  # Default to safe on API error
                        "error": f"API error: {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Gemini moderation error: {e}")
            return {
                "success": False,
                "is_safe": True,  # Default to safe on error
                "error": str(e)
            }

    # =========================================================================
    # Image Description and Analysis (for Material System)
    # =========================================================================

    async def describe_image(
        self,
        image_url: str = None,
        image_base64: str = None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Generate a detailed description of an image for Material DB primary key.
        Uses Gemini Vision to analyze the image.

        Args:
            image_url: URL of the image to analyze
            image_base64: Base64-encoded image data (alternative to URL)
            language: Output language (en, zh, ja)

        Returns:
            Dict with description, tags, category, etc.
        """
        if not self.api_key:
            return {
                "success": False,
                "description": "Image analysis unavailable",
                "error": "No API key configured"
            }

        if not image_url and not image_base64:
            return {
                "success": False,
                "description": "",
                "error": "No image provided"
            }

        lang_instruction = {
            "en": "Respond in English.",
            "zh": "請用繁體中文回答。",
            "ja": "日本語で回答してください。"
        }.get(language, "Respond in English.")

        analysis_prompt = f"""Analyze this image and provide a detailed description for an e-commerce/product database.

{lang_instruction}

Respond in JSON format:
{{
  "description": "A concise but detailed description (2-3 sentences) of the main subject",
  "category": "product/fashion/food/interior/portrait/other",
  "tags": ["list", "of", "relevant", "tags"],
  "style": "modern/vintage/minimal/luxury/casual/professional",
  "colors": ["list", "of", "dominant", "colors"],
  "subject": "main subject of the image",
  "background": "description of background",
  "quality_score": 0.0-1.0
}}"""

        try:
            # Build the image part
            image_parts = []
            if image_base64:
                # Determine mime type
                mime_type = "image/jpeg"
                if image_base64.startswith("/9j/"):
                    mime_type = "image/jpeg"
                elif image_base64.startswith("iVBOR"):
                    mime_type = "image/png"
                elif image_base64.startswith("R0lGOD"):
                    mime_type = "image/gif"

                image_parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_base64
                    }
                })
            elif image_url:
                # Fetch image and convert to base64
                async with httpx.AsyncClient(timeout=30.0) as client:
                    img_response = await client.get(image_url)
                    if img_response.status_code == 200:
                        import base64
                        content_type = img_response.headers.get("content-type", "image/jpeg")
                        image_data = base64.b64encode(img_response.content).decode()
                        image_parts.append({
                            "inline_data": {
                                "mime_type": content_type.split(";")[0],
                                "data": image_data
                            }
                        })
                    else:
                        return {
                            "success": False,
                            "description": "",
                            "error": f"Failed to fetch image: {img_response.status_code}"
                        }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/models/gemini-2.0-flash:generateContent",
                    params={"key": self.api_key},
                    headers=self._get_headers(),
                    json={
                        "contents": [
                            {
                                "role": "user",
                                "parts": image_parts + [{"text": analysis_prompt}]
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.3,
                            "maxOutputTokens": 500
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            result_text = parts[0].get("text", "").strip()
                            try:
                                # Extract JSON from response
                                start = result_text.find("{")
                                end = result_text.rfind("}") + 1
                                if start >= 0 and end > start:
                                    json_str = result_text[start:end]
                                    result = json.loads(json_str)
                                    return {
                                        "success": True,
                                        "description": result.get("description", ""),
                                        "category": result.get("category", "other"),
                                        "tags": result.get("tags", []),
                                        "style": result.get("style", ""),
                                        "colors": result.get("colors", []),
                                        "subject": result.get("subject", ""),
                                        "background": result.get("background", ""),
                                        "quality_score": result.get("quality_score", 0.5)
                                    }
                            except json.JSONDecodeError:
                                # Return raw description if JSON parsing fails
                                return {
                                    "success": True,
                                    "description": result_text[:200],
                                    "category": "other",
                                    "tags": []
                                }

                    return {
                        "success": False,
                        "description": "",
                        "error": "No response from API"
                    }
                else:
                    logger.error(f"Gemini image analysis error: {response.status_code} - {response.text[:200]}")
                    return {
                        "success": False,
                        "description": "",
                        "error": f"API error: {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Gemini image description error: {e}")
            return {
                "success": False,
                "description": "",
                "error": str(e)
            }

    async def moderate_image(
        self,
        image_url: str = None,
        image_base64: str = None
    ) -> Dict[str, Any]:
        """
        Check if an image is safe (no illegal or 18+ content).
        Uses Gemini Vision for image content moderation.

        Args:
            image_url: URL of the image to moderate
            image_base64: Base64-encoded image data

        Returns:
            Dict with is_safe, categories, reason
        """
        if not self.api_key:
            return {
                "success": True,
                "is_safe": True,
                "categories": [],
                "reason": None
            }

        if not image_url and not image_base64:
            return {
                "success": False,
                "is_safe": False,
                "error": "No image provided"
            }

        moderation_prompt = """Analyze this image for content safety. Check for:
1. Adult/sexual content or nudity
2. Violence, gore, or disturbing imagery
3. Hate symbols or discriminatory content
4. Dangerous activities
5. Illegal content (drugs, weapons, counterfeit)
6. Personal information (IDs, credit cards)

Respond in JSON format:
{"is_safe": true/false, "categories": ["list of violated categories"], "reason": "explanation if not safe", "confidence": 0.0-1.0}"""

        try:
            # Build the image part
            image_parts = []
            if image_base64:
                mime_type = "image/jpeg"
                if image_base64.startswith("/9j/"):
                    mime_type = "image/jpeg"
                elif image_base64.startswith("iVBOR"):
                    mime_type = "image/png"

                image_parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_base64
                    }
                })
            elif image_url:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    img_response = await client.get(image_url)
                    if img_response.status_code == 200:
                        import base64
                        content_type = img_response.headers.get("content-type", "image/jpeg")
                        image_data = base64.b64encode(img_response.content).decode()
                        image_parts.append({
                            "inline_data": {
                                "mime_type": content_type.split(";")[0],
                                "data": image_data
                            }
                        })

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/models/gemini-2.0-flash:generateContent",
                    params={"key": self.api_key},
                    headers=self._get_headers(),
                    json={
                        "contents": [
                            {
                                "role": "user",
                                "parts": image_parts + [{"text": moderation_prompt}]
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.1,
                            "maxOutputTokens": 200
                        },
                        "safetySettings": [
                            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                        ]
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            result_text = parts[0].get("text", "").strip()
                            try:
                                start = result_text.find("{")
                                end = result_text.rfind("}") + 1
                                if start >= 0 and end > start:
                                    json_str = result_text[start:end]
                                    result = json.loads(json_str)
                                    return {
                                        "success": True,
                                        "is_safe": result.get("is_safe", True),
                                        "categories": result.get("categories", []),
                                        "reason": result.get("reason"),
                                        "confidence": result.get("confidence", 0.8)
                                    }
                            except json.JSONDecodeError:
                                pass

                    return {
                        "success": True,
                        "is_safe": True,
                        "categories": [],
                        "reason": None
                    }
                else:
                    logger.error(f"Gemini image moderation error: {response.status_code}")
                    return {
                        "success": False,
                        "is_safe": True,
                        "error": f"API error: {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Gemini image moderation error: {e}")
            return {
                "success": False,
                "is_safe": True,
                "error": str(e)
            }

    # =========================================================================
    # Topic Prompt Generation (for Material System pre-generation)
    # =========================================================================

    async def generate_topic_prompts(
        self,
        tool: str,
        topic: str,
        count: int = 30,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Generate topic-related prompts for Material System pre-generation.

        Args:
            tool: Tool type (background_removal, product_scene, try_on, room_redesign, short_video)
            topic: Topic category (fashion, food, electronics, etc.)
            count: Number of prompts to generate
            language: Output language

        Returns:
            Dict with list of prompts
        """
        if not self.api_key:
            return {
                "success": False,
                "prompts": [],
                "error": "No API key configured"
            }

        tool_context = {
            "background_removal": "product photography with white or transparent backgrounds, e-commerce style",
            "product_scene": "product placement in beautiful scenes, lifestyle photography",
            "try_on": "fashion items, clothing, accessories on models",
            "room_redesign": "interior design, room decoration, furniture arrangement",
            "short_video": "dynamic product videos, motion effects, promotional content"
        }.get(tool, "general product content")

        lang_instruction = {
            "en": "Generate prompts in English.",
            "zh": "請用繁體中文生成提示詞。",
            "ja": "日本語でプロンプトを生成してください。"
        }.get(language, "Generate prompts in English.")

        generation_prompt = f"""Generate {count} unique, detailed prompts for AI image/video generation.

Context:
- Tool: {tool} ({tool_context})
- Topic: {topic}
- Purpose: E-commerce product advertising and marketing

{lang_instruction}

Requirements:
1. Each prompt should be 15-40 words
2. Include specific details (colors, materials, lighting, style)
3. Suitable for commercial product advertising
4. Diverse variety within the topic
5. No inappropriate content

Respond in JSON format:
{{"prompts": ["prompt1", "prompt2", ...]}}"""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/models/gemini-2.0-flash:generateContent",
                    params={"key": self.api_key},
                    headers=self._get_headers(),
                    json={
                        "contents": [
                            {
                                "role": "user",
                                "parts": [{"text": generation_prompt}]
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.9,
                            "maxOutputTokens": 4000
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            result_text = parts[0].get("text", "").strip()
                            try:
                                start = result_text.find("{")
                                end = result_text.rfind("}") + 1
                                if start >= 0 and end > start:
                                    json_str = result_text[start:end]
                                    result = json.loads(json_str)
                                    prompts = result.get("prompts", [])
                                    return {
                                        "success": True,
                                        "prompts": prompts[:count],
                                        "count": len(prompts[:count]),
                                        "tool": tool,
                                        "topic": topic
                                    }
                            except json.JSONDecodeError:
                                pass

                    return {
                        "success": False,
                        "prompts": [],
                        "error": "Failed to parse response"
                    }
                else:
                    return {
                        "success": False,
                        "prompts": [],
                        "error": f"API error: {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Gemini topic prompt generation error: {e}")
            return {
                "success": False,
                "prompts": [],
                "error": str(e)
            }

    # =========================================================================
    # Text Embedding for Similarity Matching
    # =========================================================================

    async def get_embedding(self, text: str) -> Dict[str, Any]:
        """
        Generate text embedding for similarity matching.

        Args:
            text: Text to embed

        Returns:
            Dict with embedding vector
        """
        if not self.api_key:
            # Return hash-based pseudo-embedding if no API key
            return {
                "success": True,
                "embedding": self._generate_pseudo_embedding(text),
                "dimensions": 256
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/models/text-embedding-004:embedContent",
                    params={"key": self.api_key},
                    headers=self._get_headers(),
                    json={
                        "model": "models/text-embedding-004",
                        "content": {
                            "parts": [{"text": text}]
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    embedding = data.get("embedding", {}).get("values", [])
                    return {
                        "success": True,
                        "embedding": embedding,
                        "dimensions": len(embedding)
                    }
                else:
                    logger.error(f"Gemini embedding error: {response.status_code}")
                    return {
                        "success": False,
                        "embedding": self._generate_pseudo_embedding(text),
                        "error": f"API error: {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Gemini embedding error: {e}")
            return {
                "success": False,
                "embedding": self._generate_pseudo_embedding(text),
                "error": str(e)
            }

    def _generate_pseudo_embedding(self, text: str, dimensions: int = 256) -> List[float]:
        """
        Generate a pseudo-embedding based on text hash.
        Used as fallback when API is unavailable.
        """
        # Create a deterministic hash
        text_hash = hashlib.sha256(text.lower().encode()).hexdigest()

        # Convert hash to list of floats
        embedding = []
        for i in range(0, min(len(text_hash), dimensions * 2), 2):
            val = int(text_hash[i:i+2], 16) / 255.0 - 0.5
            embedding.append(val)

        # Pad to desired dimensions
        while len(embedding) < dimensions:
            embedding.append(0.0)

        return embedding[:dimensions]

    # =========================================================================
    # Combined Processing
    # =========================================================================

    async def process_user_prompt(
        self,
        prompt: str,
        category: str = "product",
        style: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Full prompt processing: moderate, enhance, and embed.

        Args:
            prompt: User's original prompt
            category: Content category
            style: Optional style

        Returns:
            Dict with all processing results
        """
        # Step 1: Content moderation
        moderation = await self.moderate_content(prompt)
        if not moderation.get("is_safe", True):
            return {
                "success": False,
                "is_safe": False,
                "blocked_reason": moderation.get("reason", "Content violates usage policy"),
                "blocked_categories": moderation.get("categories", [])
            }

        # Step 2: Enhance prompt
        enhancement = await self.enhance_prompt(prompt, category, style)
        enhanced_prompt = enhancement.get("enhanced_prompt", prompt)

        # Step 3: Generate embedding for similarity matching
        embedding_result = await self.get_embedding(enhanced_prompt)

        return {
            "success": True,
            "is_safe": True,
            "original_prompt": prompt,
            "enhanced_prompt": enhanced_prompt,
            "embedding": embedding_result.get("embedding", []),
            "category": category,
            "style": style
        }


# Singleton instance
_gemini_service: Optional[GeminiService] = None


def get_gemini_service() -> GeminiService:
    """Get or create Gemini service singleton"""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
