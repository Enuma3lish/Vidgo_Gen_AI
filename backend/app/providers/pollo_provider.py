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
from app.services.pollo_ai import (
    POLLO_MODELS,
    POLLO_IMAGE_MODELS,
    DEFAULT_IMAGE_MODEL,
    PolloAIClient,
)

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
        """Text-to-image via Pollo's per-model /generation/<vendor>/<slug>/image endpoint.

        Pollo is the backup for PiAPI on image generation. Endpoint + body
        verified against docs.pollo.ai 2026-06-23.
        """
        self._log_request("text_to_image", params)

        prompt = params.get("prompt") or ""
        if not prompt:
            return {"success": False, "error": "prompt required for Pollo text_to_image"}

        endpoint = self._image_endpoint(params.get("model"))
        result = await self._client.generate_image(
            prompt=prompt,
            endpoint=endpoint,
            aspect_ratio=self._aspect_ratio(params),
            resolution=self._image_resolution(params),
            timeout=int(params.get("timeout", 600)),
        )
        if result.get("success") and result.get("image_url"):
            return {"success": True, "task_id": result.get("task_id"), "output": {"image_url": result["image_url"]}}
        return {"success": False, "error": result.get("error") or "Pollo text_to_image failed"}

    async def image_to_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Image-to-image / image-edit via Pollo image models (input.imageUrl).

        Backs up PiAPI for I2I, effects, recolor and interior (styled I2I).
        """
        self._log_request("image_to_image", params)

        image_url = params.get("image_url") or params.get("image")
        if not image_url:
            return {"success": False, "error": "image_url required for Pollo image_to_image"}

        endpoint = self._image_endpoint(params.get("model"))
        result = await self._client.generate_image(
            prompt=params.get("prompt") or params.get("custom_prompt") or "",
            endpoint=endpoint,
            aspect_ratio=self._aspect_ratio(params),
            resolution=self._image_resolution(params),
            image_url=image_url,
            timeout=int(params.get("timeout", 600)),
        )
        if result.get("success") and result.get("image_url"):
            return {"success": True, "task_id": result.get("task_id"), "output": {"image_url": result["image_url"]}}
        return {"success": False, "error": result.get("error") or "Pollo image_to_image failed"}

    async def virtual_try_on(
        self,
        model_image_url: str,
        garment_image_url: str,
        category: str = "dress",
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Backup virtual try-on via Pollo nano-banana-2 multi-image composition.

        Pollo has no dedicated Kling try-on endpoint, but nano-banana-2 takes a
        multi-image `input.images` array and follows an edit instruction well
        enough to composite a garment onto a model photo — used as the failover
        for PiAPI Kling AI Try-On. Returns the provider-router shape
        {"success", "output": {"image_url"}}.
        """
        self._log_request("virtual_try_on", {
            "model_image_url": model_image_url,
            "garment_image_url": garment_image_url,
            "category": category,
        })
        if not (model_image_url and garment_image_url):
            return {"success": False, "error": "model and garment image URLs are required"}

        instruction = prompt or (
            "Image 1 is a person; image 2 is a clothing garment. Dress the person "
            "from image 1 in the garment from image 2. Keep the person's face, "
            "hair, skin, body, pose, and the background EXACTLY the same — same "
            "person, never a mannequin. Replace ONLY their outfit with the "
            "garment, matching its exact color, pattern, and shape. Photorealistic, "
            "natural fabric drape and fit, consistent studio lighting."
        )
        endpoint = self._image_endpoint("nano-banana-2")
        result = await self._client.generate_image(
            prompt=instruction,
            endpoint=endpoint,
            aspect_ratio="3:4",
            resolution="2K",
            images=[model_image_url, garment_image_url],
            timeout=600,
        )
        if result.get("success") and result.get("image_url"):
            return {"success": True, "task_id": result.get("task_id"), "output": {"image_url": result["image_url"]}}
        return {"success": False, "error": result.get("error") or "Pollo nano-banana-2 try-on failed"}

    async def text_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Pure text-to-video via a Pollo per-model video endpoint (no source image).

        Body verified against docs.pollo.ai 2026-06-23 (pollo-v1-6 T2V).
        """
        self._log_request("text_to_video", params)

        prompt = params.get("prompt") or ""
        if not prompt:
            return {"success": False, "error": "prompt required for Pollo text_to_video"}

        # pollo-v1-6 is the verified T2V default; an explicit model_id still wins
        # (e.g. kling/hailuo, which also accept the prompt-only T2V body).
        requested = params.get("model")
        model = self._normalize_model(requested) if requested else "pollo-v1-6"
        endpoint = POLLO_MODELS.get(model, {}).get("endpoint")
        if not endpoint:
            return {"success": False, "error": f"Pollo has no T2V endpoint for model '{model}'"}

        result = await self._client.generate_text_to_video(
            prompt=prompt,
            endpoint=endpoint,
            resolution=str(params.get("resolution") or "720p"),
            length=self._normalize_length(model, params.get("duration") or params.get("length")),
            aspect_ratio=self._aspect_ratio(params, default="16:9"),
            timeout=int(params.get("timeout", 1200)),
        )
        if result.get("success") and result.get("video_url"):
            return {"success": True, "task_id": result.get("task_id"), "output": {"video_url": result["video_url"]}}
        return {"success": False, "error": result.get("error") or "Pollo text_to_video failed"}

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
        if model is None:
            # Explicit model Pollo can't serve → soft-fail so the router falls
            # back to PiAPI (which serves the real Wan/Veo/etc.) instead of
            # silently rendering a Pixverse substitute the user didn't pick.
            return {
                "success": False,
                "error": f"Pollo has no endpoint for requested model '{params.get('model')}'",
            }
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
            # Honor a caller-supplied ratio (Kling/Sora I2V backup sends 9:16
            # etc.); None on the short-video I2V tab → Pollo's model default.
            aspect_ratio=params.get("aspect_ratio") or params.get("aspectRatio"),
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

    # video_style_transfer removed 2026-05-31 — V2V surface dropped repo-wide.

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
    def _image_endpoint(model: Optional[str]) -> str:
        """Map a requested image model to a Pollo image endpoint.

        The router's backup path usually passes the PiAPI slug (flux/qwen/…) or
        'default'; Pollo has its own image catalogue, so we map known families
        to their Pollo analog and fall back to the verified default
        (nano-banana-2) for anything unrecognized — the backup must never
        hard-fail on routing.
        """
        m = str(model or "").strip().lower()
        aliases = {
            "nano-banana": "nano_banana_2",
            "nano_banana": "nano_banana_2",
            "nano-banana-2": "nano_banana_2",
            "nano-banana-pro": "nano_banana_pro",
            "nano_banana_pro": "nano_banana_pro",
            "gpt-image": "gpt_image_2",
            "gpt_image_2": "gpt_image_2",
            "seedream": "seedream_5_lite",
            "seedream_5_lite": "seedream_5_lite",
            "midjourney": "pollojourney",
            "pollojourney": "pollojourney",
        }
        key = aliases.get(m, DEFAULT_IMAGE_MODEL)
        info = POLLO_IMAGE_MODELS.get(key) or POLLO_IMAGE_MODELS[DEFAULT_IMAGE_MODEL]
        return info["endpoint"]

    @staticmethod
    def _aspect_ratio(params: Dict[str, Any], default: str = "1:1") -> str:
        ar = params.get("aspect_ratio") or params.get("aspectRatio") or params.get("ratio")
        return str(ar) if ar else default

    @staticmethod
    def _image_resolution(params: Dict[str, Any]) -> str:
        """Map our quality/resolution hints to Pollo's 1K/2K/4K enum."""
        res = str(params.get("resolution") or "").upper()
        if res in ("1K", "2K", "4K"):
            return res
        quality = str(params.get("quality") or "").lower()
        if quality in ("high", "hd", "ultra"):
            return "2K"
        return "1K"

    @staticmethod
    def _normalize_model(model: Optional[str]) -> Optional[str]:
        """Map a requested model id to a key in POLLO_MODELS.

        Returns the pixverse default ONLY when the caller requested no specific
        model. For an explicitly-requested model that Pollo cannot serve this
        returns None, so the caller soft-fails and the router falls through to
        PiAPI — rather than silently substituting a different (cheaper) model
        the user never picked (the wan/wan2.6/kling2.5 → pixverse defect).
        """
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
            # Frontend's 1080p tier requires the full seedance-2 task — the
            # -fast variant tops out at 720p (verified docs.pollo.ai 2026-06-23).
            "seedance_1080p": _POLLO_REG["seedance_full"],
            "seedance_2_0":   _POLLO_REG["seedance_full"],
            "hailuo":        _POLLO_REG["hailuo_default"],
            "hailuo_fast":   _POLLO_REG["hailuo_default"],
            "minimax":       _POLLO_REG["hailuo_default"],
            # Hunyuan removed 2026-06-23 — Pollo doesn't expose it (404 in prod);
            # PiAPI's Qubico/hunyuan also rejects the payload. Frontend menu
            # dropped the option, but soft-failing here protects any cached
            # client still sending model_id=hunyuan.
            "kling_omni":    _POLLO_REG["kling_omni"],
            "kling-3":       _POLLO_REG["kling_omni"],
            "kling_v3":      _POLLO_REG["kling_omni"],
            # Sora 2 Pro (2026-06-09). Frontend / router may pass any of these
            # marketing aliases; normalize them all onto Pollo's "sora-2" slug.
            "sora":          _POLLO_REG["sora2"],
            "sora2":         _POLLO_REG["sora2"],
            "sora_2":        _POLLO_REG["sora2"],
            "sora-2":        _POLLO_REG["sora2"],
            "sora2_pro":     _POLLO_REG["sora2"],
            "sora2-pro":     _POLLO_REG["sora2"],
            "sora-2-pro":    _POLLO_REG["sora2"],
        }
        m = aliases.get(m, m)
        if m in POLLO_MODELS:
            return m
        logger.warning(
            f"[Pollo REST] No Pollo endpoint for requested model '{model}' — "
            f"soft-failing so the router falls back to PiAPI (no silent substitution)."
        )
        return None

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
