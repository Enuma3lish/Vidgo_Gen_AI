"""
PiAPI MCP Provider — SUPPLEMENT provider for tasks Pollo.ai doesn't cover,
and BACKUP for video generation when Pollo is down.

Communicates with the piapi-mcp-server via MCP protocol.

Handles (supplement — Pollo doesn't have these):
  - Text-to-Image (Flux)
  - Image-to-Image (Flux derive/variation)
  - Virtual Try-On (Kling) — NOT available via MCP, falls through to REST
  - Interior Design (Flux Kontext/Doodle)
  - Avatar (Kling Video)
  - TTS (F5-TTS)
  - Upscale (Image Toolkit)
  - Background Removal (Image Toolkit)

Handles (backup — when Pollo is down):
  - Image-to-Video (Wan)
  - Text-to-Video (Wan)

PiAPI MCP tools (from piapi-mcp-server src/index.ts):
  - generate_image: Flux T2I (prompt, referenceImage, width, height, model)
  - derive_image: Flux variation/I2I (prompt, referenceImage, width, height)
  - generate_video_wan: Wan T2V/I2V (prompt, referenceImage, aspectRatio, model)
  - generate_video_kling: Kling video (prompt, referenceImage, aspectRatio, duration)
  - generate_video_effect_kling: Kling effects (image, effectName)
  - generate_video_luma: Luma video (prompt, duration, aspectRatio, keyFrame)
  - generate_video_hunyuan: Hunyuan video (prompt, referenceImage, aspectRatio)
  - generate_3d_model: Trellis I2-3D (image)
  - image_upscale: upscale (image, scale, faceEnhance)
  - image_rmbg: background removal (image)
  - tts_zero_shot: TTS (genText, refAudio, refText)
  - midjourney_imagine: Midjourney (prompt, aspectRatio)

NOTE: Virtual Try-On (kling_virtual_try_on) does NOT exist on the PiAPI MCP
server. The provider raises NotImplementedError so ProviderRouter falls through
to the REST fallback.
"""
import logging
from typing import Any, Dict

from app.providers.base import BaseProvider
from app.services.mcp_client import get_mcp_manager

logger = logging.getLogger(__name__)


class PiAPIMCPProvider(BaseProvider):
    """
    PiAPI via MCP — supplement provider for non-video tasks,
    backup provider for video when Pollo is unavailable.
    """

    name = "piapi_mcp"

    # Map of internal task names → actual PiAPI MCP tool names
    # These MUST match the tool names registered in piapi-mcp-server/src/index.ts
    TOOL_MAP = {
        "text_to_image": "generate_image",
        "image_to_image": "derive_image",
        "image_to_video": "generate_video_wan",
        "text_to_video": "generate_video_wan",
        "video_effects": "generate_video_effect_kling",
        "interior_design": "generate_image",  # Flux with referenceImage
        "avatar": "generate_video_kling",
        "tts": "tts_zero_shot",
        "upscale": "image_upscale",
        "video_style_transfer": "generate_video_wan",
        "image_to_3d": "generate_3d_model",
        "background_removal_mcp": "image_rmbg",
    }

    async def health_check(self) -> bool:
        manager = get_mcp_manager()
        return manager.is_available("piapi")

    async def close(self):
        pass  # Lifecycle managed by MCPClientManager

    # ─────────────────────────────────────────────────────────────────────────
    # IMAGE GENERATION
    # ─────────────────────────────────────────────────────────────────────────

    async def text_to_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate image from text using Flux via PiAPI MCP."""
        self._log_request("text_to_image", params)
        arguments = {
            "prompt": params["prompt"],
            "width": int(params.get("size", "1024*1024").split("*")[0]),
            "height": int(params.get("size", "1024*1024").split("*")[1]),
        }
        # PiAPI generate_image supports model: "schnell" (fast) or "dev" (quality)
        if params.get("model"):
            arguments["model"] = params["model"]
        result = await self._call_tool("text_to_image", arguments)
        return self._normalize_result(result, "image")

    async def image_to_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Image-to-image variation via Flux derive_image."""
        self._log_request("image_to_image", params)
        # derive_image uses: prompt, referenceImage, width, height
        # NOTE: no "strength" param exists on MCP — derive_image always does variation
        result = await self._call_tool("image_to_image", {
            "prompt": params.get("prompt", ""),
            "referenceImage": params["image_url"],
        })
        return self._normalize_result(result, "image")

    async def kontext_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Context-aware image editing via Flux generate_image with referenceImage."""
        self._log_request("kontext_image", params)
        result = await self._call_tool("text_to_image", {
            "prompt": params.get("prompt", ""),
            "referenceImage": params.get("image_url", ""),
        })
        return self._normalize_result(result, "image")

    # ─────────────────────────────────────────────────────────────────────────
    # VIDEO GENERATION (backup for Pollo)
    # ─────────────────────────────────────────────────────────────────────────

    async def image_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Image-to-video via Wan (backup when Pollo is down)."""
        self._log_request("image_to_video", params)
        # generate_video_wan: prompt, referenceImage, aspectRatio, model
        result = await self._call_tool("image_to_video", {
            "prompt": params.get("prompt", ""),
            "referenceImage": params["image_url"],
        })
        return self._normalize_result(result, "video")

    async def text_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Text-to-video via Wan (backup when Pollo is down)."""
        self._log_request("text_to_video", params)
        # generate_video_wan: prompt, aspectRatio, model
        result = await self._call_tool("text_to_video", {
            "prompt": params["prompt"],
        })
        return self._normalize_result(result, "video")

    async def video_style_transfer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Video style transfer via Wan — use referenceImage + style prompt."""
        self._log_request("video_style_transfer", params)
        image_url = params.get("image_url") or params.get("video_url", "")
        result = await self._call_tool("video_style_transfer", {
            "prompt": params.get("prompt", "stylized video"),
            "referenceImage": image_url,
        })
        return self._normalize_result(result, "video")

    # ─────────────────────────────────────────────────────────────────────────
    # SPECIALIZED TASKS (only PiAPI supports these)
    # ─────────────────────────────────────────────────────────────────────────

    async def virtual_try_on(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Virtual try-on — NOT available via PiAPI MCP server.
        Raises so ProviderRouter falls through to REST fallback.
        """
        raise NotImplementedError(
            "Virtual try-on is not available via PiAPI MCP. "
            "Use PiAPI REST API (kling ai_try_on) instead."
        )

    async def doodle_interior(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Interior design via Flux generate_image with referenceImage."""
        self._log_request("interior_design", params)
        result = await self._call_tool("interior_design", {
            "prompt": params.get("prompt", ""),
            "referenceImage": params.get("image_url", ""),
        })
        return self._normalize_result(result, "image")

    async def generate_avatar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Avatar generation via Kling video generation."""
        self._log_request("avatar", params)
        # generate_video_kling: prompt, referenceImage, aspectRatio, duration
        # NOTE: audio_url is NOT a valid MCP param — Kling MCP does video only
        arguments = {
            "prompt": params.get("text", params.get("prompt", "")),
        }
        if params.get("image_url"):
            arguments["referenceImage"] = params["image_url"]
        result = await self._call_tool("avatar", arguments)
        return self._normalize_result(result, "video")

    async def upscale(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Image upscale via PiAPI image_upscale tool."""
        self._log_request("upscale", params)
        # image_upscale: image (URL), scale (2-10), faceEnhance (bool)
        result = await self._call_tool("upscale", {
            "image": params["image_url"],
            "scale": params.get("scale", 2),
        })
        return self._normalize_result(result, "image")

    async def text_to_speech(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Text-to-speech via F5-TTS."""
        self._log_request("tts", params)
        # tts_zero_shot: genText (required), refAudio (required URL), refText (optional)
        ref_audio = params.get("voice", "")
        if not ref_audio:
            raise ValueError(
                "PiAPI tts_zero_shot requires refAudio (a reference voice URL). "
                "Pass a voice URL in params['voice']."
            )
        arguments = {
            "genText": params.get("text", ""),
            "refAudio": ref_audio,
        }
        if params.get("ref_text"):
            arguments["refText"] = params["ref_text"]
        result = await self._call_tool("tts", arguments)
        return self._normalize_result(result, "audio")

    async def trellis_3d(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Image to 3D model via Trellis."""
        self._log_request("image_to_3d", params)
        # generate_3d_model: image (URL)
        result = await self._call_tool("image_to_3d", {
            "image": params["image_url"],
        })
        return self._normalize_result(result, "model")

    async def background_removal(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Background removal — try MCP image_rmbg first, fall back to local rembg.
        """
        try:
            self._log_request("background_removal_mcp", params)
            result = await self._call_tool("background_removal_mcp", {
                "image": params["image_url"],
            })
            return self._normalize_result(result, "image")
        except Exception as e:
            logger.warning(f"[PiAPI MCP] image_rmbg failed ({e}), falling back to local rembg")
            from app.providers.piapi_provider import PiAPIProvider
            local = PiAPIProvider()
            try:
                return await local.background_removal(params)
            finally:
                await local.close()

    # ─────────────────────────────────────────────────────────────────────────
    # INTERNAL
    # ─────────────────────────────────────────────────────────────────────────

    async def _call_tool(
        self, task_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call the mapped PiAPI MCP tool."""
        manager = get_mcp_manager()
        tool_name = self.TOOL_MAP.get(task_name, task_name)

        # Check if the tool actually exists on the server
        available = manager.list_tools("piapi")
        available_names = [t["name"] for t in available]
        if available_names and tool_name not in available_names:
            logger.warning(
                f"[PiAPI MCP] Tool '{tool_name}' not found. "
                f"Available: {available_names}"
            )

        return await manager.call("piapi", tool_name, arguments)

    def _normalize_result(
        self, mcp_result: Dict[str, Any], media_type: str
    ) -> Dict[str, Any]:
        """Normalize MCP result to standard provider response format."""
        import re

        # PiAPI MCP tools return the task result after internal polling
        # Response varies by tool; try common patterns

        # Direct URL in result
        for key in ("image_url", "video_url", "audio_url", "model_url", "url", "output_url"):
            if mcp_result.get(key):
                output_key = f"{media_type}_url"
                self._log_response("generation", True)
                return {
                    "success": True,
                    "task_id": mcp_result.get("task_id", ""),
                    "output": {output_key: mcp_result[key]},
                }

        # Nested output
        output = mcp_result.get("output", {})
        if isinstance(output, dict):
            for key in ("image_url", "video_url", "audio_url", "model_url", "url"):
                if output.get(key):
                    output_key = f"{media_type}_url"
                    self._log_response("generation", True)
                    return {
                        "success": True,
                        "task_id": mcp_result.get("task_id", ""),
                        "output": {output_key: output[key]},
                    }

        # Raw text with URL
        raw = mcp_result.get("raw", "")
        if raw:
            urls = re.findall(r'https?://[^\s"\'<>]+', raw)
            if urls:
                output_key = f"{media_type}_url"
                self._log_response("generation", True)
                return {
                    "success": True,
                    "task_id": "",
                    "output": {output_key: urls[0]},
                }

        self._log_response("generation", False, f"Unexpected result: {mcp_result}")
        raise Exception(f"PiAPI MCP returned unexpected result: {mcp_result}")
