"""
Pollo.ai REST Provider — primary REST lane for explicit Pollo model choices
(seedance_v2, hailuo_fast, hunyuan_v1, kling_v3, pixverse_v4.5, …).

Pollo's REST API is per-model; the path is:
    POST https://pollo.ai/api/platform/generation/{vendor}/{model-slug}
with body:
    {"input": {"image": "<https url>", "prompt": "...", "negativePrompt": "...", "length": 5}}
and header:
    x-api-key: <POLLO_API_KEY>

Status:
    GET https://pollo.ai/api/platform/generation/{taskId}/status
returns generations[0].{status,url,failMsg}.

This provider thin-wraps app.services.pollo_ai.PolloAIClient (which already
implements the correct per-model endpoint table + payload shape) so the
ProviderRouter sees the standard {"success", "output": {"video_url": ...}}
response shape used by every other provider.
"""
import logging
import os
from typing import Any, Dict, List, Optional

from app.providers.base import BaseProvider
from app.core.model_registry import POLLO_MODELS as _POLLO_REG
from app.services.pollo_ai import POLLO_MODELS, PolloAIClient

logger = logging.getLogger(__name__)


class PolloProvider(BaseProvider):
    """Pollo.ai via REST — primary for explicit model choices."""

    name = "pollo"

    def __init__(self):
        api_key = os.getenv("POLLO_API_KEY", "")
        if not api_key:
            logger.warning("POLLO_API_KEY not set in environment")
        self._client = PolloAIClient(api_key=api_key)

    async def health_check(self) -> bool:
        return bool(self._client.api_key)

    async def close(self):
        # PolloAIClient creates a fresh httpx.AsyncClient per call.
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC METHODS
    # ─────────────────────────────────────────────────────────────────────────

    async def text_to_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Pollo does not expose a generic T2I REST endpoint that we use; the
        # router will fall through to PiAPI/Vertex.
        return {
            "success": False,
            "error": "Pollo REST does not implement text_to_image; falling through.",
        }

    async def text_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Pollo's per-model T2V endpoints differ per model and are not yet
        # wired here. Reject so the router falls back to Pollo MCP / PiAPI Wan.
        return {
            "success": False,
            "error": "Pollo REST text_to_video not implemented; falling through.",
        }

    async def image_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate I2V via Pollo per-model REST endpoint.

        Required: image_url
        Optional: prompt, model (one of POLLO_MODELS), duration|length, negative_prompt
        """
        self._log_request("image_to_video", params)

        image_url = params.get("image_url") or params.get("image")
        if not image_url:
            return {"success": False, "error": "image_url required for Pollo I2V"}

        model = self._normalize_model(params.get("model"))
        prompt = params.get("prompt") or "smooth motion, cinematic quality"
        negative_prompt = params.get("negative_prompt") or (
            "blurry, distorted, low quality, jerky motion"
        )
        length = self._normalize_length(model, params.get("duration") or params.get("length"))
        # 20-minute default — Kling / Pixverse / Hailuo / Seedance video
        # jobs can idle 8-15 min on long prompts. tools.py passes this
        # explicitly for short-video; ad-hoc callers also get 1200 now.
        timeout = int(params.get("timeout", 1200))

        success, task_id, _ = await self._client.generate_video(
            image_url=image_url,
            prompt=prompt,
            model=model,
            negative_prompt=negative_prompt,
            length=length,
        )
        if not success:
            return {"success": False, "error": task_id, "model": model}

        result = await self._client.wait_for_completion(task_id, timeout=timeout)
        status = (result.get("status") or "").lower()
        if status == "succeed" and result.get("video_url"):
            return {
                "success": True,
                "task_id": task_id,
                "model": model,
                "output": {"video_url": result["video_url"]},
            }
        return {
            "success": False,
            "task_id": task_id,
            "model": model,
            "error": result.get("error") or f"Pollo task ended with status={status}",
        }

    async def video_style_transfer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pollo doesn't expose a true V2V endpoint; approximate by feeding the
        first frame (image_url) into I2V with a style prompt.
        """
        self._log_request("video_style_transfer", params)
        image_url = params.get("image_url") or params.get("first_frame_url")
        if not image_url:
            return {
                "success": False,
                "error": "Pollo V2V requires image_url (first frame); no native V2V endpoint.",
            }
        return await self.image_to_video({**params, "image_url": image_url})

    async def keyframes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": False,
            "error": "Pollo REST keyframes not implemented in this client.",
        }

    async def effects(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": False,
            "error": "Pollo REST effects not implemented in this client.",
        }

    async def camera_control(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": False,
            "error": "Pollo REST camera_control not implemented in this client.",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # INTERNAL
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_model(model: Optional[str]) -> str:
        """Map frontend model_id aliases to keys present in POLLO_MODELS."""
        default_model = _POLLO_REG["pixverse_default"]
        if not model:
            return default_model
        m = str(model).strip()
        aliases = {
            "pixverse": _POLLO_REG["pixverse_default"],
            "pixverse_v4_5": "pixverse_v4.5",
            "pixverse-v4.5": "pixverse_v4.5",
            "pixverse-v4-5": "pixverse_v4.5",
            "pixverse_v5": _POLLO_REG["pixverse_creative"],
            "pixverse-v5": "pixverse_v5",
            "kling": _POLLO_REG["kling_video"],
            "kling_v1_5": "kling_v1.5",
            "kling-v1-5": "kling_v1.5",
            "kling-v2": "kling_v2",
            # 2026-05-19 tier revision — Pollo is the backup for PiAPI on
            # these models. Aliases mirror what callers might pass after
            # picking a tier on the frontend (frontend sends the family
            # name; Pollo normalizes to its slug here).
            "seedance":      _POLLO_REG["seedance_default"],
            "seedance_v2":   _POLLO_REG["seedance_default"],
            "seedance-fast": _POLLO_REG["seedance_default"],
            "hailuo":        _POLLO_REG["hailuo_default"],
            "hailuo_fast":   _POLLO_REG["hailuo_default"],
            "minimax":       _POLLO_REG["hailuo_default"],
            "hunyuan":       _POLLO_REG["hunyuan_default"],
            "kling_omni":    _POLLO_REG["kling_omni"],
            "kling-3":       _POLLO_REG["kling_omni"],
            "kling_v3":      _POLLO_REG["kling_omni"],
        }
        m = aliases.get(m, m)
        if m in POLLO_MODELS:
            return m
        logger.warning(f"[Pollo REST] Unknown model '{model}', defaulting to {default_model}")
        return default_model

    @staticmethod
    def _normalize_length(model: str, length: Any) -> int:
        valid: List[int] = POLLO_MODELS.get(model, {}).get("lengths", [5, 8])
        try:
            n = int(length) if length is not None else valid[0]
        except (TypeError, ValueError):
            n = valid[0]
        if n not in valid:
            n = min(valid, key=lambda v: abs(v - n))
        return n
