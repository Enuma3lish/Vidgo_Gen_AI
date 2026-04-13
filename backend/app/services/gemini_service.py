"""
Gemini AI Service — Prompt enhancement, content moderation, and embedding generation.

Uses Google Vertex AI (google-genai SDK) for LLM capabilities.
Replaces the old API-key-based generativelanguage.googleapis.com approach.

Auth: Uses Google Application Default Credentials (ADC) via Vertex AI.
  - On GCP: automatic via service account
  - Local dev: GOOGLE_APPLICATION_CREDENTIALS or `gcloud auth application-default login`
  - Fallback: GEMINI_API_KEY (legacy, uses AI Studio endpoint)

Env vars:
  - VERTEX_AI_PROJECT: GCP project ID
  - VERTEX_AI_LOCATION: Region, default "us-central1"
  - GEMINI_API_KEY: Legacy fallback if Vertex AI not configured
"""
import asyncio
import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

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
    "gambling",
]


class GeminiService:
    """
    Gemini AI Service for prompt enhancement and content moderation.

    Prefers Vertex AI (ADC auth). Falls back to API key if Vertex AI not configured.
    """

    # Legacy fallback endpoint
    LEGACY_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        self.project = os.getenv("VERTEX_AI_PROJECT", "")
        self.location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self._genai_client = None
        self._use_vertex = bool(self.project)

    def _get_genai_client(self):
        """Lazy-init the google-genai client."""
        if self._genai_client is None:
            from google import genai

            if self._use_vertex:
                self._genai_client = genai.Client(
                    vertexai=True,
                    project=self.project,
                    location=self.location,
                )
                logger.info("[GeminiService] Using Vertex AI backend")
            else:
                self._genai_client = genai.Client(api_key=self.api_key)
                logger.info("[GeminiService] Using legacy API key backend")
        return self._genai_client

    # =========================================================================
    # Prompt Enhancement
    # =========================================================================

    async def enhance_prompt(
        self,
        user_prompt: str,
        category: str = "product",
        style: Optional[str] = None,
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
        if not self.api_key and not self._use_vertex:
            return {
                "success": True,
                "original_prompt": user_prompt,
                "enhanced_prompt": user_prompt,
                "keywords": [],
                "category": category,
            }

        system_prompt = (
            "You are an expert prompt engineer for AI image and video generation.\n"
            "Your task is to enhance user prompts to create better, more detailed prompts for product advertising.\n\n"
            "Guidelines:\n"
            "1. Keep the core intent of the original prompt\n"
            "2. Add specific visual details (lighting, angle, background)\n"
            "3. Include quality enhancers (high quality, detailed, professional)\n"
            "4. Make it suitable for product advertising\n"
            "5. Keep it concise but descriptive (max 100 words)\n"
            "6. Output ONLY the enhanced prompt, nothing else\n\n"
            f"Category context: {category}\n"
            f"Style preference: {style or 'any'}"
        )

        prompt = f"Enhance this prompt for AI image generation:\n\nOriginal: {user_prompt}\n\nEnhanced prompt:"

        try:
            client = self._get_genai_client()
            from google.genai import types

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(system_prompt)],
                    ),
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text("I understand. I will enhance prompts for product advertising images. Please provide the prompt.")],
                    ),
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(prompt)],
                    ),
                ],
                config=types.GenerateContentConfig(
                    temperature=0.7, max_output_tokens=200
                ),
            )

            enhanced = (response.text or "").strip()
            enhanced = enhanced.replace("Enhanced prompt:", "").strip().strip('"')

            return {
                "success": True,
                "original_prompt": user_prompt,
                "enhanced_prompt": enhanced if enhanced else user_prompt,
                "category": category,
                "style": style,
            }
        except Exception as e:
            logger.error(f"Gemini enhance prompt error: {e}")
            return {
                "success": False,
                "original_prompt": user_prompt,
                "enhanced_prompt": user_prompt,
                "error": str(e),
            }

    # =========================================================================
    # Content Moderation
    # =========================================================================

    async def moderate_content(self, text: str) -> Dict[str, Any]:
        """Check if content is safe (no illegal or 18+ content)."""
        if not self.api_key and not self._use_vertex:
            return {"success": True, "is_safe": True, "categories": [], "reason": None}

        moderation_prompt = (
            "Analyze the following text and determine if it contains any inappropriate content.\n\n"
            "Check for:\n"
            "1. Adult/sexual content\n"
            "2. Violence or gore\n"
            "3. Hate speech or discrimination\n"
            "4. Harassment or bullying\n"
            "5. Dangerous activities\n"
            "6. Illegal activities\n"
            "7. Weapons or explosives\n"
            "8. Drug-related content\n"
            "9. Gambling promotion\n\n"
            f'Text to analyze:\n"{text}"\n\n'
            'Respond in JSON format:\n'
            '{"is_safe": true/false, "categories": ["list of violated categories"], "reason": "explanation if not safe"}'
        )

        try:
            client = self._get_genai_client()
            from google.genai import types

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.model_name,
                contents=[moderation_prompt],
                config=types.GenerateContentConfig(
                    temperature=0.1, max_output_tokens=200
                ),
            )

            result_text = (response.text or "").strip()
            start = result_text.find("{")
            end = result_text.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(result_text[start:end])
                return {
                    "success": True,
                    "is_safe": result.get("is_safe", True),
                    "categories": result.get("categories", []),
                    "reason": result.get("reason"),
                }

            return {"success": True, "is_safe": True, "categories": [], "reason": None}
        except Exception as e:
            logger.error(f"Gemini moderation error: {e}")
            return {"success": False, "is_safe": True, "error": str(e)}

    # =========================================================================
    # Image Description and Analysis (for Material System)
    # =========================================================================

    async def describe_image(
        self,
        image_url: str = None,
        image_base64: str = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Generate a detailed description of an image for Material DB primary key.
        """
        if not self.api_key and not self._use_vertex:
            return {
                "success": False,
                "description": "Image analysis unavailable",
                "error": "No API key configured",
            }

        if not image_url and not image_base64:
            return {"success": False, "description": "", "error": "No image provided"}

        lang_instruction = {
            "en": "Respond in English.",
            "zh": "Please respond in Traditional Chinese.",
            "ja": "Please respond in Japanese.",
        }.get(language, "Respond in English.")

        analysis_prompt = (
            f"Analyze this image and provide a detailed description for an e-commerce/product database.\n\n"
            f"{lang_instruction}\n\n"
            'Respond in JSON format:\n'
            '{\n'
            '  "description": "A concise but detailed description (2-3 sentences)",\n'
            '  "category": "product/fashion/food/interior/portrait/other",\n'
            '  "tags": ["list", "of", "relevant", "tags"],\n'
            '  "style": "modern/vintage/minimal/luxury/casual/professional",\n'
            '  "colors": ["list", "of", "dominant", "colors"],\n'
            '  "subject": "main subject of the image",\n'
            '  "background": "description of background",\n'
            '  "quality_score": 0.0-1.0\n'
            '}'
        )

        try:
            client = self._get_genai_client()
            from google.genai import types
            import base64 as b64

            parts = []

            if image_base64:
                mime_type = "image/jpeg"
                if image_base64.startswith("iVBOR"):
                    mime_type = "image/png"
                elif image_base64.startswith("R0lGOD"):
                    mime_type = "image/gif"
                parts.append(
                    types.Part.from_bytes(
                        data=b64.b64decode(image_base64), mime_type=mime_type
                    )
                )
            elif image_url:
                async with httpx.AsyncClient(timeout=30.0) as http:
                    img_resp = await http.get(image_url)
                    if img_resp.status_code != 200:
                        return {
                            "success": False,
                            "description": "",
                            "error": f"Failed to fetch image: {img_resp.status_code}",
                        }
                    content_type = img_resp.headers.get("content-type", "image/jpeg").split(";")[0]
                    parts.append(
                        types.Part.from_bytes(
                            data=img_resp.content, mime_type=content_type
                        )
                    )

            parts.append(types.Part.from_text(analysis_prompt))

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.model_name,
                contents=parts,
                config=types.GenerateContentConfig(
                    temperature=0.3, max_output_tokens=500
                ),
            )

            result_text = (response.text or "").strip()
            start = result_text.find("{")
            end = result_text.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(result_text[start:end])
                return {
                    "success": True,
                    "description": result.get("description", ""),
                    "category": result.get("category", "other"),
                    "tags": result.get("tags", []),
                    "style": result.get("style", ""),
                    "colors": result.get("colors", []),
                    "subject": result.get("subject", ""),
                    "background": result.get("background", ""),
                    "quality_score": result.get("quality_score", 0.5),
                }

            return {
                "success": True,
                "description": result_text[:200],
                "category": "other",
                "tags": [],
            }
        except Exception as e:
            logger.error(f"Gemini image description error: {e}")
            return {"success": False, "description": "", "error": str(e)}

    async def generate_effect_prompt_for_image(
        self,
        image_url: str = None,
        image_base64: str = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Generate a style/effect prompt for image-to-image transformation."""
        if not self.api_key and not self._use_vertex:
            return {"success": False, "effect_prompt": "", "error": "No API key configured"}

        if not image_url and not image_base64:
            return {"success": False, "effect_prompt": "", "error": "No image provided"}

        prompt = (
            "Analyze this image and suggest ONE art style for transformation.\n\n"
            "Output a short effect prompt (15-30 words) suitable for image-to-image style transfer.\n"
            "The prompt should describe ONLY the art style. Do NOT describe the subject.\n\n"
            'Respond in JSON:\n{"effect_prompt": "your style prompt here", "style_name": "short name"}'
        )

        if language.startswith("zh"):
            prompt = (
                "Analyze this image and suggest one art style for transformation.\n"
                'Respond in JSON:\n{"effect_prompt": "style prompt", "style_name": "name"}'
            )

        try:
            client = self._get_genai_client()
            from google.genai import types
            import base64 as b64

            parts = []
            if image_base64:
                mime_type = "image/png" if image_base64.startswith("iVBOR") else "image/jpeg"
                parts.append(
                    types.Part.from_bytes(
                        data=b64.b64decode(image_base64), mime_type=mime_type
                    )
                )
            elif image_url:
                async with httpx.AsyncClient(timeout=30.0) as http:
                    img_resp = await http.get(image_url)
                    if img_resp.status_code != 200:
                        return {
                            "success": False,
                            "effect_prompt": "",
                            "error": f"Failed to fetch image: {img_resp.status_code}",
                        }
                    content_type = img_resp.headers.get("content-type", "image/jpeg").split(";")[0]
                    parts.append(
                        types.Part.from_bytes(data=img_resp.content, mime_type=content_type)
                    )

            if not parts:
                return {"success": False, "effect_prompt": "", "error": "Could not load image"}

            parts.append(types.Part.from_text(prompt))

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.model_name,
                contents=parts,
                config=types.GenerateContentConfig(
                    temperature=0.5, max_output_tokens=150
                ),
            )

            text = (response.text or "").strip()
            start, end = text.find("{"), text.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(text[start:end])
                return {
                    "success": True,
                    "effect_prompt": result.get("effect_prompt", "artistic style illustration"),
                    "style_name": result.get("style_name", "artistic"),
                }

            return {
                "success": True,
                "effect_prompt": text[:100] or "artistic style illustration",
                "style_name": "custom",
            }
        except Exception as e:
            logger.error(f"Gemini effect prompt error: {e}")
            return {"success": False, "effect_prompt": "", "error": str(e)}

    async def moderate_image(
        self, image_url: str = None, image_base64: str = None
    ) -> Dict[str, Any]:
        """Check if an image is safe using Gemini Vision."""
        if not self.api_key and not self._use_vertex:
            return {"success": True, "is_safe": True, "categories": [], "reason": None}

        if not image_url and not image_base64:
            return {"success": False, "is_safe": False, "error": "No image provided"}

        moderation_prompt = (
            "Analyze this image for content safety. Check for:\n"
            "1. Adult/sexual content or nudity\n"
            "2. Violence, gore, or disturbing imagery\n"
            "3. Hate symbols or discriminatory content\n"
            "4. Dangerous activities\n"
            "5. Illegal content\n"
            "6. Personal information\n\n"
            'Respond in JSON format:\n'
            '{"is_safe": true/false, "categories": ["list"], "reason": "explanation if not safe", "confidence": 0.0-1.0}'
        )

        try:
            client = self._get_genai_client()
            from google.genai import types
            import base64 as b64

            parts = []

            if image_base64:
                mime_type = "image/jpeg"
                if image_base64.startswith("iVBOR"):
                    mime_type = "image/png"
                parts.append(
                    types.Part.from_bytes(
                        data=b64.b64decode(image_base64), mime_type=mime_type
                    )
                )
            elif image_url:
                async with httpx.AsyncClient(timeout=30.0) as http:
                    img_resp = await http.get(image_url)
                    if img_resp.status_code == 200:
                        content_type = img_resp.headers.get("content-type", "image/jpeg").split(";")[0]
                        parts.append(
                            types.Part.from_bytes(data=img_resp.content, mime_type=content_type)
                        )

            parts.append(types.Part.from_text(moderation_prompt))

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.model_name,
                contents=parts,
                config=types.GenerateContentConfig(
                    temperature=0.1, max_output_tokens=200
                ),
            )

            result_text = (response.text or "").strip()
            start = result_text.find("{")
            end = result_text.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(result_text[start:end])
                return {
                    "success": True,
                    "is_safe": result.get("is_safe", True),
                    "categories": result.get("categories", []),
                    "reason": result.get("reason"),
                    "confidence": result.get("confidence", 0.8),
                }

            return {"success": True, "is_safe": True, "categories": [], "reason": None}
        except Exception as e:
            logger.error(f"Gemini image moderation error: {e}")
            return {"success": False, "is_safe": True, "error": str(e)}

    # =========================================================================
    # Topic Prompt Generation (for Material System)
    # =========================================================================

    async def generate_topic_prompts(
        self, tool: str, topic: str, count: int = 30, language: str = "en"
    ) -> Dict[str, Any]:
        """Generate topic-related prompts for Material System pre-generation."""
        if not self.api_key and not self._use_vertex:
            return {"success": False, "prompts": [], "error": "No API key configured"}

        tool_context = {
            "background_removal": "product photography with white or transparent backgrounds",
            "product_scene": "product placement in beautiful scenes, lifestyle photography",
            "try_on": "fashion items, clothing, accessories on models",
            "room_redesign": "interior design, room decoration, furniture arrangement",
            "short_video": "dynamic product videos, motion effects, promotional content",
        }.get(tool, "general product content")

        lang_instruction = {
            "en": "Generate prompts in English.",
            "zh": "Generate prompts in Traditional Chinese.",
            "ja": "Generate prompts in Japanese.",
        }.get(language, "Generate prompts in English.")

        generation_prompt = (
            f"Generate {count} unique, detailed prompts for AI image/video generation.\n\n"
            f"Context:\n- Tool: {tool} ({tool_context})\n- Topic: {topic}\n"
            f"- Purpose: E-commerce product advertising and marketing\n\n"
            f"{lang_instruction}\n\n"
            "Requirements:\n"
            "1. Each prompt should be 15-40 words\n"
            "2. Include specific details (colors, materials, lighting, style)\n"
            "3. Suitable for commercial product advertising\n"
            "4. Diverse variety within the topic\n"
            "5. No inappropriate content\n\n"
            'Respond in JSON format:\n{"prompts": ["prompt1", "prompt2", ...]}'
        )

        try:
            client = self._get_genai_client()
            from google.genai import types

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.model_name,
                contents=[generation_prompt],
                config=types.GenerateContentConfig(
                    temperature=0.9, max_output_tokens=4000
                ),
            )

            result_text = (response.text or "").strip()
            start = result_text.find("{")
            end = result_text.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(result_text[start:end])
                prompts = result.get("prompts", [])
                return {
                    "success": True,
                    "prompts": prompts[:count],
                    "count": len(prompts[:count]),
                    "tool": tool,
                    "topic": topic,
                }

            return {"success": False, "prompts": [], "error": "Failed to parse response"}
        except Exception as e:
            logger.error(f"Gemini topic prompt generation error: {e}")
            return {"success": False, "prompts": [], "error": str(e)}

    # =========================================================================
    # Text Embedding for Similarity Matching
    # =========================================================================

    async def get_embedding(self, text: str) -> Dict[str, Any]:
        """Generate text embedding for similarity matching."""
        if not self.api_key and not self._use_vertex:
            return {
                "success": True,
                "embedding": self._generate_pseudo_embedding(text),
                "dimensions": 256,
            }

        try:
            client = self._get_genai_client()

            response = await asyncio.to_thread(
                client.models.embed_content,
                model="text-embedding-004",
                contents=text,
            )

            embedding = response.embeddings[0].values if response.embeddings else []
            return {
                "success": True,
                "embedding": embedding,
                "dimensions": len(embedding),
            }
        except Exception as e:
            logger.error(f"Gemini embedding error: {e}")
            return {
                "success": False,
                "embedding": self._generate_pseudo_embedding(text),
                "error": str(e),
            }

    def _generate_pseudo_embedding(self, text: str, dimensions: int = 256) -> List[float]:
        """Generate a pseudo-embedding based on text hash (fallback)."""
        text_hash = hashlib.sha256(text.lower().encode()).hexdigest()
        embedding = []
        for i in range(0, min(len(text_hash), dimensions * 2), 2):
            val = int(text_hash[i : i + 2], 16) / 255.0 - 0.5
            embedding.append(val)
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
        style: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Full prompt processing: moderate, enhance, and embed."""
        moderation = await self.moderate_content(prompt)
        if not moderation.get("is_safe", True):
            return {
                "success": False,
                "is_safe": False,
                "blocked_reason": moderation.get("reason", "Content violates usage policy"),
                "blocked_categories": moderation.get("categories", []),
            }

        enhancement = await self.enhance_prompt(prompt, category, style)
        enhanced_prompt = enhancement.get("enhanced_prompt", prompt)
        embedding_result = await self.get_embedding(enhanced_prompt)

        return {
            "success": True,
            "is_safe": True,
            "original_prompt": prompt,
            "enhanced_prompt": enhanced_prompt,
            "embedding": embedding_result.get("embedding", []),
            "category": category,
            "style": style,
        }


# Singleton instance
_gemini_service: Optional[GeminiService] = None


def get_gemini_service() -> GeminiService:
    """Get or create Gemini service singleton"""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
