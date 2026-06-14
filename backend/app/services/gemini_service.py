"""
Gemini AI Service — Prompt enhancement, content moderation, and embedding generation.

Uses Google Gemini API (AI Studio) by default. Falls back to Vertex AI if no API key.

Auth priority:
  1. GEMINI_API_KEY — Gemini API (aistudio.google.com), no GCP project needed
  2. VERTEX_AI_PROJECT — Vertex AI ADC (service account / gcloud ADC)

Env vars:
  - GEMINI_API_KEY: Gemini API key (preferred)
  - GEMINI_MODEL: Model name, default "gemini-2.5-pro"
  - VERTEX_AI_PROJECT: GCP project ID (fallback if no API key)
  - VERTEX_AI_LOCATION: Region, default "us-central1"
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

    Uses Gemini API (GEMINI_API_KEY) by default; falls back to Vertex AI if no key is set.
    """

    # Legacy fallback endpoint (unused but kept for reference)
    LEGACY_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        self.project = os.getenv("VERTEX_AI_PROJECT", "")
        # Vertex Gen AI text/image models live in us-central1 (Gemini 2.5
        # flash is NOT published to asia-east1). The infra-side
        # VERTEX_AI_LOCATION env var (set to asia-east1 to colocate the
        # Cloud Run / Cloud SQL layout) does NOT apply to Gen AI calls.
        # We override with VERTEX_AI_GENAI_LOCATION (defaulting to
        # us-central1) so text-gen and image-gen both work without
        # depending on which region runs the service.
        self.location = os.getenv("VERTEX_AI_GENAI_LOCATION", "us-central1")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        self._genai_client = None
        # Vertex AI ADC takes priority when a project is configured. The
        # standalone Gemini API key path is only used as a fallback for local
        # dev where ADC isn't available — on Cloud Run we always have ADC via
        # the service account, and our previous GEMINI_API_KEY was reported
        # as leaked by Google so we must not send it. The legacy "API key
        # wins" priority caused 403 PERMISSION_DENIED loops in
        # prompt_refinement_service / video_dubbing translation. Flip it.
        self._use_vertex = bool(self.project)

    def _get_genai_client(self):
        """Lazy-init the google-genai client (Gemini API preferred, Vertex AI fallback)."""
        if self._genai_client is None:
            from google import genai

            if self._use_vertex:
                self._genai_client = genai.Client(
                    vertexai=True,
                    project=self.project,
                    location=self.location,
                )
                logger.info("[GeminiService] Using Vertex AI backend (no GEMINI_API_KEY set)")
            else:
                self._genai_client = genai.Client(api_key=self.api_key)
                logger.info("[GeminiService] Using Gemini API backend")
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

        category_context = {
            "product": (
                "commercial product photography — think studio hero shots, lifestyle scenes, "
                "dramatic accent lighting, clean or contextual backgrounds, bokeh, "
                "sharp detail on textures and materials"
            ),
            "food": (
                "culinary/food photography — think steam, glistening surfaces, vibrant colour, "
                "moody overhead or 45° angles, shallow depth-of-field, rustic or minimal props, "
                "natural side-window light or warm golden-hour warmth"
            ),
            "fashion": (
                "editorial fashion photography — think confident model poses, dynamic movement, "
                "on-location or minimalist studio, directional key light, rich fabric texture, "
                "depth from foreground/background separation"
            ),
            "interior": (
                "architectural interior photography — think wide-angle perspective, balanced "
                "natural + artificial light, cohesive colour palette, lifestyle props, "
                "high ceilings, styled vignettes, premium materials"
            ),
            "portrait": (
                "professional portrait photography — think catchlights in eyes, soft diffused "
                "key light, subtle background separation, natural skin tones, "
                "genuine expression, clean or complementary background"
            ),
            "lifestyle": (
                "lifestyle brand photography — think authentic human moments, sun-drenched or "
                "golden-hour colour grading, aspirational yet approachable setting, "
                "product integrated naturally into scene"
            ),
        }.get(category, "commercial advertising photography — visually compelling, high production value")

        style_hint = f"Preferred visual style: {style}." if style else ""

        system_prompt = (
            "You are a senior creative director and AI image-generation prompt specialist.\n"
            "You write prompts for Flux, DALL-E 3, Stable Diffusion, and Imagen that consistently "
            "produce commercially stunning, print-quality visuals.\n\n"
            "When you enhance a prompt, follow this mental checklist:\n"
            "  • SUBJECT — what is the hero element? make it specific.\n"
            "  • COMPOSITION — angle (eye-level / overhead / low-angle / three-quarter), "
            "framing, negative space.\n"
            "  • LIGHTING — source (softbox / window light / rim light / golden hour), "
            "quality (diffused / dramatic), colour temperature (warm / cool / neutral).\n"
            "  • ATMOSPHERE — mood, season, time of day, weather, story.\n"
            "  • TECHNICAL — lens (50mm / 85mm macro / wide angle), depth of field, "
            "aspect ratio, film grain or digital clean.\n"
            "  • QUALITY MARKERS — cinematic, hyper-realistic, award-winning photography, "
            "8K, sharp focus, colour-graded.\n\n"
            "Rules:\n"
            "  1. Keep the user's core intent — never change the subject.\n"
            "  2. Final prompt must be 30–80 words — rich but not bloated.\n"
            "  3. Output ONLY the enhanced prompt text, no preamble, no quotes, no labels.\n\n"
            f"Category: {category_context}\n"
            f"{style_hint}"
        )

        prompt = (
            f"Original prompt:\n{user_prompt}\n\n"
            "Write the enhanced prompt now:"
        )

        try:
            client = self._get_genai_client()
            from google.genai import types

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=system_prompt)],
                    ),
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=(
                            "Understood. I'll enhance each prompt by refining subject specificity, "
                            "composition, lighting, atmosphere, and quality markers — keeping your "
                            "core intent intact. Ready."
                        ))],
                    ),
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=prompt)],
                    ),
                ],
                config=types.GenerateContentConfig(
                    temperature=0.75, max_output_tokens=300
                ),
            )

            enhanced = (response.text or "").strip()
            # Strip any label prefix the model may accidentally emit
            for prefix in ("Enhanced prompt:", "Enhanced:", "Output:"):
                if enhanced.lower().startswith(prefix.lower()):
                    enhanced = enhanced[len(prefix):].strip()
            enhanced = enhanced.strip('"').strip("'")

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

    async def translate_text(self, text: str, target_language: str) -> Dict[str, Any]:
        """Translate spoken-script text into ``target_language`` ('zh-TW' | 'en').

        Added 2026-06-12 for the avatar tool: the script is auto-translated to
        the selected voice language instead of being rejected (zh-TW mode +
        English text used to 400) or mispronounced (en mode + Chinese text
        spoke Chinese). Fail-open: any error returns the original text.
        """
        if not text or not text.strip() or (not self.api_key and not self._use_vertex):
            return {"success": False, "translated": text}
        lang_name = {
            "zh-TW": "Traditional Chinese (繁體中文, Taiwan usage)",
            "en": "natural English",
        }.get(target_language, target_language)
        try:
            client = self._get_genai_client()
            from google.genai import types

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=(
                            f"Translate the following text into {lang_name}. It is a "
                            "spoken script for a presenter video — keep the meaning, "
                            "tone, and approximate length, and make it sound natural "
                            "when read aloud. Output ONLY the translated text, with no "
                            "preamble, no quotes, no labels.\n\n"
                            f"{text}"
                        ))],
                    ),
                ],
                config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=800),
            )
            out = (response.text or "").strip().strip('"').strip("'")
            return {"success": bool(out), "translated": out or text}
        except Exception as e:
            logger.warning(f"Gemini translate_text error (fail-open): {e}")
            return {"success": False, "translated": text}

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

            parts.append(types.Part.from_text(text=analysis_prompt))

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

    async def analyze_floorplan_for_growth(
        self,
        image_url: str = None,
        image_base64: str = None,
        style_label: str = "",
        room_type_label: str = "",
        extra_prompt: str = "",
        language: str = "en",
    ) -> Dict[str, Any]:
        """Vision analysis of a 2D architectural floor plan for the
        "floor plan grows into a 3D room" pipeline (Step 1 — the brain).

        Returns two engineered production prompts derived from THIS plan:
          - render_prompt        → the photorealistic 3D interior END frame
          - video_motion_prompt  → the Kling first→last-frame growth animation
        plus structure_notes (layout/lighting read off the plan).

        Fail-soft: on any error returns ``{"success": False, ...}`` so the
        orchestrator can fall back to style/room templates and still run.
        Locally (where ADC is unavailable) it retries with the standalone
        Gemini API key so the analysis still works off Cloud Run.
        """
        if not self.api_key and not self._use_vertex:
            return {"success": False, "error": "No Gemini credentials configured"}
        if not image_url and not image_base64:
            return {"success": False, "error": "No image provided"}

        style_hint = f" The user picked this design style: {style_label}." if style_label else ""
        room_hint = f" Primary room type: {room_type_label}." if room_type_label else ""
        extra_hint = f" Extra user request to honour: {extra_prompt}." if extra_prompt else ""

        instruction = (
            "You are an architectural-visualization director. The attached image is a "
            "2D floor plan (top-down blueprint)."
            f"{style_hint}{room_hint}{extra_hint}\n\n"
            "Read the plan: infer room layout, wall positions, door/window openings, and the "
            "most likely natural-light direction. Then write TWO production prompts that stay "
            "faithful to THIS exact layout.\n\n"
            "Respond ONLY with minified JSON, exactly these keys:\n"
            '{"render_prompt": "<one detailed English prompt to render ONE photorealistic '
            "interior of this exact layout: walls ~2.8m tall, realistic materials, the chosen "
            "style, soft natural daylight from the correct side, correct perspective, no people, "
            'no dimension labels>", "video_motion_prompt": "<one English prompt for a smooth 4-5s '
            "animation where the flat 2D plan EXTRUDES and GROWS upward into the finished 3D room: "
            "walls rise from the plan lines, materials and textures spread across floor and walls, "
            'furniture and lighting materialize in place, gentle cinematic camera push-in>", '
            '"structure_notes": "<one sentence on the layout/light you detected>"}'
        )

        def _run(use_api_key: bool):
            from google import genai
            from google.genai import types
            import base64 as b64

            if use_api_key:
                client = genai.Client(api_key=self.api_key)
            else:
                client = self._get_genai_client()

            parts = []
            if image_base64:
                mime = "image/png" if image_base64.startswith("iVBOR") else "image/jpeg"
                parts.append(types.Part.from_bytes(data=b64.b64decode(image_base64), mime_type=mime))
            else:
                img = httpx.get(image_url, timeout=30.0, follow_redirects=True)
                img.raise_for_status()
                ct = img.headers.get("content-type", "image/jpeg").split(";")[0]
                parts.append(types.Part.from_bytes(data=img.content, mime_type=ct))
            parts.append(types.Part.from_text(text=instruction))

            return client.models.generate_content(
                model=self.model_name,
                contents=parts,
                config=types.GenerateContentConfig(temperature=0.4, max_output_tokens=800),
            )

        async def _attempt(use_api_key: bool) -> Dict[str, Any]:
            response = await asyncio.to_thread(_run, use_api_key)
            text = (response.text or "").strip()
            start, end = text.find("{"), text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                rp = (data.get("render_prompt") or "").strip()
                vp = (data.get("video_motion_prompt") or "").strip()
                if rp and vp:
                    return {
                        "success": True,
                        "render_prompt": rp,
                        "video_motion_prompt": vp,
                        "structure_notes": (data.get("structure_notes") or "").strip(),
                        "backend": "vertex" if (self._use_vertex and not use_api_key) else "api_key",
                    }
            return {"success": False, "error": "Gemini returned no usable prompts", "raw": text[:200]}

        try:
            return await _attempt(use_api_key=False)
        except Exception as primary_exc:  # noqa: BLE001
            # On Cloud Run ADC works and this never fires. Locally the Vertex
            # client 401s (no ADC) — retry with the standalone API key so the
            # analysis still works in dev.
            if self.api_key:
                try:
                    return await _attempt(use_api_key=True)
                except Exception as fallback_exc:  # noqa: BLE001
                    logger.warning("Floorplan growth analysis failed (api-key fallback): %s", fallback_exc)
                    return {"success": False, "error": str(fallback_exc)}
            logger.warning("Floorplan growth analysis failed: %s", primary_exc)
            return {"success": False, "error": str(primary_exc)}

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

            parts.append(types.Part.from_text(text=prompt))

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

            parts.append(types.Part.from_text(text=moderation_prompt))

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

        tool_config = {
            "background_removal": {
                "purpose": "Clean, isolated product shots for e-commerce listings — subject sharp, background removed",
                "dimensions": ["hero angle", "material texture", "brand aesthetic", "product category"],
                "examples": [
                    "Sleek stainless-steel insulated water bottle, hero front view, sharp metallic sheen, matte finish lid, isolated",
                    "Artisan leather handbag in caramel brown, three-quarter angle showing stitching detail and gold hardware, isolated",
                    "Running shoes in neon coral and white mesh, dynamic side profile, clean sole, isolated",
                ],
            },
            "product_scene": {
                "purpose": "Product placed in aspirational lifestyle or studio scenes for advertising",
                "dimensions": ["setting/environment", "lighting mood", "props and context", "camera perspective"],
                "examples": [
                    "Luxury perfume bottle on a marble vanity table, warm golden morning light streaming through sheer curtains, soft bokeh",
                    "Protein supplement canister on a gym locker bench, early-morning dramatic side lighting, towel and water bottle props",
                    "Artisan coffee bag beside a ceramic mug on a rustic wooden café counter, moody window light, steam wisps",
                ],
            },
            "try_on": {
                "purpose": "Fashion items shown on models in editorial or lifestyle contexts",
                "dimensions": ["garment fit and drape", "model pose and movement", "setting/backdrop", "lighting and mood"],
                "examples": [
                    "Oversized cream linen blazer on a confident female model, breezy outdoor terrace, golden afternoon sun, relaxed power stance",
                    "Fitted navy suit on a male model in a modern city lobby, cool directional key light, sharp lapels, dynamic walking pose",
                    "Floral midi dress in soft pastels, female model in sunlit botanical garden, natural backlight, flowing movement",
                ],
            },
            "room_redesign": {
                "purpose": "Interior spaces redesigned in specific styles for inspiration and marketing",
                "dimensions": ["design style", "colour palette", "lighting (natural/artificial)", "key furniture and materials"],
                "examples": [
                    "Scandinavian living room, warm oak floors, cream bouclé sofa, fiddle-leaf fig, large window with diffused morning light",
                    "Industrial loft bedroom, exposed brick, black steel bed frame, Edison bulb pendant, warm amber evening light",
                    "Japanese minimalist bathroom, terrazzo floor, teak bath caddy, washi paper pendant lamp, natural side light",
                ],
            },
            "short_video": {
                "purpose": "Cinematic short-form product or brand videos optimised for social media",
                "dimensions": ["motion type", "visual hook", "colour grade", "pacing energy"],
                "examples": [
                    "Slow-motion pour of golden honey into glass jar, macro lens, warm amber colour grade, studio backlight",
                    "Sneaker unboxing with dramatic reveal, hands lifting lid, cool blue tones, quick cuts, product hero close-ups",
                    "Perfume bottle rotating on a mirrored surface, light refractions, luxury black-and-gold palette, cinematic zoom",
                ],
            },
            "ai_avatar": {
                "purpose": "AI spokesperson or avatar delivering a product message naturally and engagingly",
                "dimensions": ["presenter style", "background setting", "delivery tone", "brand alignment"],
                "examples": [
                    "Professional female presenter in a modern office, business casual, warm confident delivery, clean blurred background",
                    "Casual male presenter outdoors in a bright urban setting, friendly direct tone, relaxed styling",
                    "Expert skincare presenter in a clean white studio, soft beauty lighting, reassuring instructional tone",
                ],
            },
        }.get(tool, {
            "purpose": "commercial AI-generated product content",
            "dimensions": ["visual style", "lighting", "composition", "mood"],
            "examples": [
                "Premium product in elegant setting, professional studio lighting, hero angle",
                "Lifestyle brand moment, natural light, authentic feel, aspirational mood",
            ],
        })

        lang_instruction = {
            "en": "Write every prompt in English.",
            "zh": "Write every prompt in Traditional Chinese (繁體中文).",
            "ja": "Write every prompt in Japanese.",
        }.get(language, "Write every prompt in English.")

        dims = "\n".join(f"  - {d}" for d in tool_config["dimensions"])
        examples_block = "\n".join(f'  "{ex}"' for ex in tool_config["examples"])

        generation_prompt = (
            f"You are an expert AI image/video generation prompt writer specialising in "
            f"e-commerce and brand advertising content.\n\n"
            f"TASK: Generate exactly {count} unique prompts for the following brief.\n\n"
            f"Tool: {tool}\n"
            f"Purpose: {tool_config['purpose']}\n"
            f"Topic / theme: {topic}\n\n"
            f"Each prompt must vary across these dimensions (do not repeat the same combination):\n"
            f"{dims}\n\n"
            f"Quality examples (match this level of specificity):\n"
            f"{examples_block}\n\n"
            f"Rules:\n"
            f"1. Each prompt is 20–60 words — vivid, specific, commercially polished.\n"
            f"2. Cover the full range of {topic}: different sub-styles, moods, angles, settings.\n"
            f"3. Every prompt must be immediately usable — no placeholders like [color] or [item].\n"
            f"4. No repetition across prompts; aim for maximum creative diversity.\n"
            f"5. {lang_instruction}\n"
            f"6. No inappropriate or adult content.\n\n"
            f'Output ONLY valid JSON: {{"prompts": ["prompt 1", "prompt 2", ...]}}'
        )

        try:
            client = self._get_genai_client()
            from google.genai import types

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.model_name,
                contents=[generation_prompt],
                config=types.GenerateContentConfig(
                    temperature=0.95,
                    max_output_tokens=8000,
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
