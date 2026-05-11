"""Prompt refinement service backed by Gemini.

The service rewrites generation prompts into provider-friendly, specific prompts
that keep the user's intent while reducing hallucinated subjects, layout changes,
extra text, and unwanted people/objects.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.services.gemini_service import get_gemini_service

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class PromptRefinementResult:
    original_prompt: str
    refined_prompt: str
    success: bool
    changed: bool = False
    skipped: bool = False
    error: Optional[str] = None

    def to_metadata(self) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "success": self.success,
            "changed": self.changed,
            "skipped": self.skipped,
        }
        if self.changed:
            metadata["original_prompt"] = self.original_prompt
            metadata["refined_prompt"] = self.refined_prompt
        if self.error:
            metadata["error"] = self.error
        return metadata


class PromptRefinementService:
    """Refine prompts for image/video generation without making tools brittle."""

    TOOL_PROFILES: Dict[str, Dict[str, Any]] = {
        "product_scene": {
            "purpose": "Generate a clean commercial background scene for later product compositing.",
            "constraints": [
                "Keep the center area open for the product.",
                "Do not invent products, labels, logos, people, hands, or extra hero objects.",
                "Describe lighting, surface, camera angle, depth of field, and commercial mood clearly.",
            ],
            "max_words": 95,
        },
        "room_redesign": {
            "purpose": "Create an interior redesign/edit prompt from an existing room photo.",
            "constraints": [
                "Preserve the original room layout, camera angle, walls, windows, and structural boundaries.",
                "Do not add people, pets, impossible architecture, or unrelated rooms.",
                "Specify materials, palette, furniture style, lighting, and realism.",
            ],
            "max_words": 100,
        },
        "short_video": {
            "purpose": "Create an image-to-video motion prompt from a still product or brand image.",
            "constraints": [
                "Preserve the source subject identity and composition.",
                "Describe camera motion, subject micro-motion, lighting transition, and pacing.",
                "Do not introduce new products, people, text, logos, scene changes, or unrealistic physics.",
            ],
            "max_words": 80,
        },
        "video_transform": {
            "purpose": "Create a video-to-video style transfer prompt.",
            "constraints": [
                "Preserve the original subjects, actions, timing, framing, and brand identity.",
                "Describe style, lighting, color grade, texture, and mood without changing the story.",
                "Do not add new scenes, people, logos, text, or objects.",
            ],
            "max_words": 85,
        },
        "image_transform": {
            "purpose": "Create an image-to-image edit prompt.",
            "constraints": [
                "Preserve the source image subject, proportions, recognizable product details, and brand marks.",
                "Describe only the requested transformation and the quality/lighting needed.",
                "Do not invent text, logos, people, new products, or unrelated background elements.",
            ],
            "max_words": 90,
        },
        "image_translation": {
            "purpose": "Create an image text translation/editing prompt.",
            "constraints": [
                "Translate visible text only and preserve the original layout, typography weight, product, faces, and colors.",
                "Keep brand names, URLs, numbers, currency, and logos unchanged unless normal words must be localized.",
                "Do not add new objects, extra slogans, changed products, or decorative text.",
            ],
            "max_words": 115,
        },
        "try_on": {
            "purpose": "Create a virtual try-on prompt for AI Kling Try-On (garment transferred onto a model).",
            "constraints": [
                "Preserve the model's identity, ethnicity, skin tone, age, hairstyle, body proportions, and pose exactly.",
                "Preserve the garment's color, fabric, pattern, sleeve length, neckline, and overall silhouette exactly.",
                "Describe only realistic studio lighting, fit, draping, and natural fabric physics.",
                "Do not invent accessories, jewelry, brand logos, text, additional people, or background props.",
            ],
            "max_words": 80,
        },
        "ai_avatar": {
            "purpose": "Create a talking-head avatar prompt for lip-synced spokesperson video.",
            "constraints": [
                "Preserve the headshot subject's exact facial identity, ethnicity, age, gender, hairstyle, eye color, and clothing.",
                "Describe only natural micro-expression, subtle head movement, friendly presenter posture, and stable studio lighting.",
                "Do not change face shape, skin tone, hair, or wardrobe; do not add second person, hands, gestures, captions, or background text.",
                "Keep the script language and meaning intact when referenced; never paraphrase the script content.",
            ],
            "max_words": 70,
        },
        "pattern_generate": {
            "purpose": "Create a tileable brand pattern prompt (Flux T2I) for packaging/fabric/wallpaper.",
            "constraints": [
                "Honor the requested style family (seamless, floral, geometric, abstract, traditional, 3d, interior, mockup) literally.",
                "Specify color palette in concrete hex-or-name terms, motif scale, repeat structure, and surface texture.",
                "Forbid readable text, logos, watermarks, recognizable real brands, faces, and product photography.",
                "Keep composition flat or near-flat unless 3d style is explicitly requested; ensure tile-friendly edges for seamless style.",
            ],
            "max_words": 85,
        },
        "background_removal": {
            "purpose": "Refine optional background-replacement prompts after subject cutout.",
            "constraints": [
                "Preserve the cut-out subject's exact silhouette, pose, color, lighting direction, and edge fidelity.",
                "Describe only the new background scene, depth, and ambient lighting that matches the subject's existing illumination.",
                "Do not add additional subjects, text, watermarks, or duplicate the foreground product.",
            ],
            "max_words": 60,
        },
    }

    def __init__(self) -> None:
        self.enabled = bool(getattr(settings, "GEMINI_PROMPT_REFINEMENT_ENABLED", True))

    async def refine_for_tool(
        self,
        prompt: str,
        tool_name: str,
        prompt_role: str = "generation prompt",
        user_prompt: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> PromptRefinementResult:
        cleaned = " ".join((prompt or "").split())
        if not cleaned:
            return PromptRefinementResult(prompt, prompt, success=True, skipped=True)

        if not self.enabled:
            return PromptRefinementResult(cleaned, cleaned, success=True, skipped=True)

        gemini = get_gemini_service()
        if not getattr(gemini, "api_key", "") and not getattr(gemini, "_use_vertex", False):
            return PromptRefinementResult(cleaned, cleaned, success=True, skipped=True)

        profile = self.TOOL_PROFILES.get(tool_name, {})
        max_words = int(profile.get("max_words", 90))
        constraints = profile.get("constraints", [])
        context = context or {}

        system_prompt = (
            "You are a senior prompt engineer for commercial AI image and video generation. "
            "Rewrite prompts so the downstream model produces precise, on-brief output that "
            "faithfully preserves the source subject (identity, count, color, proportions, pose, "
            "and existing brand marks) while adding only the requested transformation. "
            "NEVER invent subjects, brands, slogans, watermarks, on-image text, additional people, "
            "hands, animals, props, or scene elements that were not requested. Use realistic "
            "photographic/video language (lens, lighting direction, depth-of-field, materials, "
            "camera motion, pacing) and respect every tool constraint exactly. Output ONLY valid JSON."
        )
        payload = {
            "tool": tool_name,
            "purpose": profile.get("purpose", "Refine a commercial AI generation prompt."),
            "prompt_role": prompt_role,
            "is_user_prompt": user_prompt,
            "max_words": max_words,
            "constraints": constraints,
            "context": context,
            "original_prompt": cleaned,
            "output_schema": {"prompt": "refined prompt only"},
        }
        user_message = (
            "Rewrite the original prompt according to the tool purpose and constraints. "
            f"Keep it under {max_words} words. Return JSON only, with exactly one key: prompt.\n\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

        try:
            from google.genai import types

            client = gemini._get_genai_client()
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=getattr(gemini, "model_name", "gemini-2.5-pro"),
                contents=[
                    types.Content(role="user", parts=[types.Part.from_text(text=system_prompt)]),
                    types.Content(role="user", parts=[types.Part.from_text(text=user_message)]),
                ],
                config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=500),
            )
            refined = self._extract_prompt(response.text or "")
            if not refined:
                return PromptRefinementResult(cleaned, cleaned, success=False, error="empty Gemini response")
            refined = self._normalize_refined_prompt(refined)
            changed = refined != cleaned
            return PromptRefinementResult(cleaned, refined, success=True, changed=changed)
        except Exception as exc:
            logger.warning("Prompt refinement fallback for %s: %s", tool_name, exc)
            return PromptRefinementResult(cleaned, cleaned, success=False, error=str(exc))

    def _extract_prompt(self, raw_text: str) -> str:
        text = (raw_text or "").strip()
        if not text:
            return ""

        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
                prompt = data.get("prompt") or data.get("refined_prompt")
                if isinstance(prompt, str):
                    return prompt
            except json.JSONDecodeError:
                pass

        for prefix in ("Refined prompt:", "Enhanced prompt:", "Prompt:", "Output:"):
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
                break
        return text.strip().strip('"').strip("'")

    def _normalize_refined_prompt(self, prompt: str) -> str:
        return " ".join((prompt or "").replace("\n", " ").split()).strip().strip('"').strip("'")


_prompt_refinement_service: Optional[PromptRefinementService] = None


def get_prompt_refinement_service() -> PromptRefinementService:
    global _prompt_refinement_service
    if _prompt_refinement_service is None:
        _prompt_refinement_service = PromptRefinementService()
    return _prompt_refinement_service