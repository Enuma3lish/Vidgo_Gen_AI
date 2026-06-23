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
    - /api/v1/tools/short-video (Seedance/Hailuo/Hunyuan/Wan I2V)
    - /api/v1/tools/avatar (face photo + script)
    (Luma I2V branch dropped 2026-05-19 with the Luma tool itself.)

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
        """Disabled 2026-05-24 (owner directive — PiAPI prompt-fidelity parity).
        Previously ran the image + user text through Gemini Vision, which
        was free to drop or rewrite the user's prompt whenever it judged
        the text "misaligned" with the image. That made the platform feel
        like it was ignoring what users typed (matched the symptom
        "I prompt but get a different effect"). The Gemini call is now
        skipped entirely — we return the user's prompt verbatim, exactly
        like piapi.ai does.

        Same dataclass shape so all 8+ callers keep working without edits.
        """
        return self._fail_open(user_prompt)

    async def extract_structure_constraints(
        self,
        *,
        image_url: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        space_kind: str = "interior",
    ) -> str:
        """Additive structure-preservation pass (2026-06-03, owner-approved).

        Unlike the retired ``describe_and_fuse`` — which could DROP or REWRITE
        the user's prompt — this only READS the photo and returns an extra
        clause describing the permanent architectural shell to preserve, ready
        to be APPENDED to the prompt. The user's wording is never touched.

        Returns "" (empty, no clause) on any error/timeout so callers fail
        open and the render proceeds exactly as before.
        """
        try:
            notes = await self._provider.describe_structure(
                {"image_url": image_url, "image_bytes": image_bytes, "space_kind": space_kind}
            )
        except Exception:
            notes = None
        if not notes:
            return ""

        notes = notes.strip().rstrip(".")
        if (space_kind or "").lower() == "exterior":
            return (
                f" Preserve the building's existing architecture exactly as in the source photo "
                f"— {notes}. Restyle only cladding, surfaces, materials, finishes, landscaping and "
                f"lighting; do NOT change the massing, rooflines, window positions, or footprint."
            )
        if (space_kind or "").lower() == "landscape":
            return (
                f" Preserve the site's existing terrain, building footprint and hardscape exactly "
                f"as in the source photo — {notes}. Restyle only planting, lawn, garden features and "
                f"outdoor lighting; do NOT enclose the space as a room, add interior furniture, or "
                f"alter the site boundary or built structures."
            )
        return (
            f" Preserve the space's existing architecture exactly as in the source photo "
            f"— {notes}. Restyle only finishes, materials, lighting, furniture and decor; do NOT "
            f"move or alter walls, windows, doors, or the room geometry."
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
