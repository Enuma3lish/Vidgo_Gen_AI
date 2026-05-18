"""
Image-understanding service — server-side preprocessing that fuses an
uploaded image with the user's text prompt to reduce hallucination.

Motivation (2026-05-18 — owner request):
    "we provide explainer about the upload image ... user and input text
    to enhance the input but this need to check if input has big gap with
    image — just ignore user input."

Workflow (one Gemini Vision call):
    1. Send the image + user prompt + tool context to Gemini.
    2. Gemini returns strict JSON:
         { image_summary, key_subjects, fused_prompt,
           user_prompt_aligned, gap_reason, confidence }
    3. We expose `image_summary` so the tool UI can show
       "this is what we see in your image" alongside the result.
    4. `fused_prompt` becomes the prompt sent to the downstream
       generator (Flux / Kling / Gemini Image / etc.), regardless of
       whether the user's text was used. When `user_prompt_aligned`
       is False, the user's text is dropped and `fused_prompt` is
       anchored entirely on the image content — preventing
       "user typed kitchen but uploaded a bedroom" hallucinations.

Used by:
    - /api/v1/interior/redesign  (RoomRedesign URL form)
    - /api/v1/interior/demo/redesign  (RoomRedesign upload form)
    - /api/v1/tools/room-redesign
    - /api/v1/tools/product-scene
    - /api/v1/tools/effect
    - /api/v1/tools/kling-video (I2V branch)
    - /api/v1/tools/luma-video  (I2V branch)
    - /api/v1/tools/short-video
    - /api/v1/tools/avatar (face photo + script)

Fail-open policy: if the Gemini call errors out, we return the user's
original prompt unchanged with `used_user_prompt=True` and
`image_summary=""`. The tool keeps working — it just loses the
hallucination guardrail for that one request.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# Free-form so callers can pass any short identifier; the model uses it
# for additional context but the prompt works for unknown values too.
ToolContext = str


@dataclass
class ImageFusionResult:
    """Result of running a single image+prompt through Gemini Vision."""

    image_summary: str
    """Plain-language one-sentence description of what's in the image.
    Surfaced to the user as "We see: __" so they can correct ambiguity.
    Empty string when the fail-open fallback runs."""

    fused_prompt: str
    """The final prompt to send to the downstream generator. When the
    user's prompt is aligned with the image, this combines image-facts
    and user intent. When the user contradicts the image, this is
    anchored on the image alone (user text dropped)."""

    used_user_prompt: bool
    """False only when the user's prompt contradicts the image enough
    that we suppressed it. True in every other case, including the
    fail-open fallback."""

    gap_reason: Optional[str]
    """Human-readable one-sentence explanation when `used_user_prompt`
    is False. e.g. "Your prompt mentions a kitchen but the image shows
    a bedroom." None when user prompt was kept."""

    confidence: float
    """Model self-confidence in the fusion, 0.0–1.0. Used to log /
    surface low-confidence cases; not currently a gating threshold."""


_SYSTEM_INSTRUCTION = (
    "You are a vision pre-processor for an image-generation pipeline. "
    "You receive a user's uploaded image and a user-typed text prompt. "
    "Your job is to (a) describe the image in one short sentence, "
    "(b) detect whether the user's text is consistent with the image, "
    "and (c) produce a single fused prompt for the downstream generator.\n\n"
    "Rules:\n"
    "- If the user's prompt describes changes that are reasonable for "
    "this image (e.g. 'make it Scandinavian style' on a room photo), "
    "set user_prompt_aligned=true and fuse user intent with image facts.\n"
    "- If the user's prompt contradicts the image (e.g. 'redesign as a "
    "kitchen' on a bedroom photo, or 'add Asian model' on a product-only "
    "shot), set user_prompt_aligned=false, include a one-sentence "
    "gap_reason, and build fused_prompt from the image alone with the "
    "downstream tool's default styling.\n"
    "- An empty or whitespace-only user prompt is NOT a contradiction — "
    "set user_prompt_aligned=true and build fused_prompt from image facts.\n"
    "- Always return strict JSON. No prose, no markdown fences.\n\n"
    "Output schema (all keys required):\n"
    "{\n"
    '  "image_summary": "<one short sentence describing the image>",\n'
    '  "key_subjects": ["<3-6 short noun phrases>"],\n'
    '  "fused_prompt": "<final prompt for the generator>",\n'
    '  "user_prompt_aligned": true|false,\n'
    '  "gap_reason": "<one sentence | null>",\n'
    '  "confidence": 0.0\n'
    "}\n"
)


class ImageUnderstandingService:
    """Wraps a single Gemini Vision call into a dataclass result.

    Reuses the existing VertexAIProvider's gemini text client so auth
    (GEMINI_API_KEY → Vertex ADC fallback) is identical to the rest of
    the pipeline. No extra env vars to set.
    """

    def __init__(self):
        from app.providers.vertex_ai_provider import VertexAIProvider

        # Lightweight handle — the underlying client is lazy-initialised
        # on first use inside VertexAIProvider, so this constructor is
        # free to call from app startup.
        self._provider = VertexAIProvider()

    async def describe_and_fuse(
        self,
        *,
        image_bytes: Optional[bytes] = None,
        image_url: Optional[str] = None,
        user_prompt: str,
        tool_context: ToolContext = "generic",
        language: str = "zh-TW",
        mime_type: str = "image/jpeg",
    ) -> ImageFusionResult:
        """Run one Gemini Vision call. Returns ImageFusionResult.

        Pass exactly one of `image_bytes` (raw bytes) or `image_url`
        (publicly reachable HTTP/HTTPS URL — the model fetches it).

        On any error, returns a fail-open result that keeps the user's
        original prompt unchanged. The caller's tool flow always works.
        """
        if not image_bytes and not image_url:
            return self._fail_open(user_prompt)

        try:
            import httpx  # type: ignore
            from google.genai import types  # type: ignore

            # Vertex AI's Part.from_uri only accepts gs:// URIs, not https.
            # When given an https URL, fetch the bytes ourselves (matches the
            # rest of vertex_ai_provider.py which does the same).
            if not image_bytes and image_url:
                async with httpx.AsyncClient(timeout=20.0) as http:
                    resp = await http.get(image_url)
                if resp.status_code != 200:
                    logger.warning(
                        "image_understanding fetch failed: %s -> HTTP %s",
                        image_url,
                        resp.status_code,
                    )
                    return self._fail_open(user_prompt)
                image_bytes = resp.content
                detected_mime = (
                    resp.headers.get("content-type", "image/jpeg")
                    .split(";")[0]
                    .strip()
                )
                if detected_mime in {"image/jpeg", "image/png", "image/webp"}:
                    mime_type = detected_mime

            client = self._provider._get_gemini_text_client()

            user_prompt_clean = (user_prompt or "").strip()
            language_hint = (
                "Respond with image_summary, gap_reason, and fused_prompt in zh-TW (繁體中文)."
                if language.startswith("zh")
                else f"Respond in {language}."
            )

            parts: list = [
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                (
                    f"Tool context: {tool_context}\n"
                    f"User text prompt: {user_prompt_clean or '(none)'}\n"
                    f"{language_hint}"
                ),
            ]

            response = await client.aio.models.generate_content(
                model=self._provider.gemini_model,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )

            text = (getattr(response, "text", None) or "").strip()
            if not text:
                return self._fail_open(user_prompt)

            data = json.loads(text)

        except Exception as exc:  # pragma: no cover — exercised in prod
            logger.warning(
                "image_understanding_fail_open tool=%s err=%s",
                tool_context,
                exc,
            )
            return self._fail_open(user_prompt)

        aligned = bool(data.get("user_prompt_aligned", True))
        return ImageFusionResult(
            image_summary=str(data.get("image_summary", "")).strip(),
            fused_prompt=(
                str(data.get("fused_prompt", "")).strip() or user_prompt
            ),
            used_user_prompt=aligned,
            gap_reason=(
                str(data["gap_reason"]).strip()
                if not aligned and data.get("gap_reason")
                else None
            ),
            confidence=float(data.get("confidence", 0.5)),
        )

    @staticmethod
    def _fail_open(user_prompt: str) -> ImageFusionResult:
        """When the vision call errors, fall back to the user's prompt
        unchanged so the tool still works. The hallucination guardrail
        is lost for this one request but nothing breaks."""
        return ImageFusionResult(
            image_summary="",
            fused_prompt=user_prompt or "",
            used_user_prompt=True,
            gap_reason=None,
            confidence=0.0,
        )


_instance: Optional[ImageUnderstandingService] = None


def get_image_understanding_service() -> ImageUnderstandingService:
    """Singleton accessor — same pattern as get_provider_router() etc."""
    global _instance
    if _instance is None:
        _instance = ImageUnderstandingService()
    return _instance
