"""
Pollo.ai MCP Provider — PRIMARY provider for video generation.

Communicates with the pollo-mcp server (npm: mcp-server-pollo) via MCP protocol.
Handles: text2video, img2video (50+ models including Kling, Wan, Runway, Sora, etc.)

Pollo MCP tools:
  - text2video: text prompt → video
  - img2video: image URL → video
  - getTaskStatus: poll task and auto-download result

IMPORTANT — MCP tool parameter schema (from docs.pollo.ai/mcp-server):
  text2video: {
    model: {modelBrand: str, modelAlias: str},  // required nested object
    prompt: str,
    length: number,        // seconds (5, 10)
    resolution: str,       // "480p", "720p", "1080p"
    aspectRatio: str,      // "16:9", "9:16", "1:1"
    mode: str,             // "basic" or "pro"
  }
  img2video: {
    model: {modelBrand: str, modelAlias: str},
    image: str,            // HTTPS URL (not base64)
    prompt: str,
    length: number,
    resolution: str,
    aspectRatio: str,
  }

Model alias → brand mapping examples:
  pollo-v1-6, pollo-v2-0       → brand "pollo"
  kling-v2, kling-v2-master    → brand "kling-ai"
  wan-2.1, wan-2.6             → brand "wan"
  runway-gen-4-turbo           → brand "runway"
  veo3                         → brand "google"
  sora-2                       → brand "sora"
"""
import logging
from typing import Any, Dict, Optional

from app.providers.base import BaseProvider, VideoGenerationProvider
from app.services.mcp_client import get_mcp_manager

logger = logging.getLogger(__name__)

# Default models for Pollo.ai
DEFAULT_VIDEO_MODEL = "pollo-v1-6"

# Model alias → brand mapping
# The MCP server requires model as {modelBrand, modelAlias}
MODEL_BRAND_MAP = {
    "pollo": "pollo",
    "kling": "kling-ai",
    "wan": "wan",
    "runway": "runway",
    "veo": "google",
    "sora": "sora",
    "luma": "luma",
    "pika": "pika",
    "pixverse": "pixverse",
    "hailuo": "hailuo",
    "hunyuan": "hunyuan",
    "seedance": "seedance",
    "vidu": "vidu",
}


def _parse_model(model_str: Optional[str]) -> Dict[str, str]:
    """
    Parse a model alias string into the nested {modelBrand, modelAlias} object
    that the Pollo MCP server requires.

    Examples:
        "pollo-v1-6"         → {"modelBrand": "pollo", "modelAlias": "pollo-v1-6"}
        "kling-v2"           → {"modelBrand": "kling-ai", "modelAlias": "kling-v2"}
        "wan-2.6"            → {"modelBrand": "wan", "modelAlias": "wan-2.6"}
        "runway-gen-4-turbo" → {"modelBrand": "runway", "modelAlias": "runway-gen-4-turbo"}
        "veo3"               → {"modelBrand": "google", "modelAlias": "veo3"}
    """
    if not model_str:
        model_str = DEFAULT_VIDEO_MODEL

    # Match the alias prefix against known brands
    alias_lower = model_str.lower()
    for prefix, brand in MODEL_BRAND_MAP.items():
        if alias_lower.startswith(prefix):
            return {"modelBrand": brand, "modelAlias": model_str}

    # Fallback: assume pollo brand
    logger.warning(f"[Pollo MCP] Unknown model brand for '{model_str}', defaulting to 'pollo'")
    return {"modelBrand": "pollo", "modelAlias": model_str}


class PolloMCPProvider(VideoGenerationProvider):
    """
    Pollo.ai via MCP — primary video generation provider.
    Supports 50+ models via a unified API.
    """

    name = "pollo_mcp"

    async def health_check(self) -> bool:
        manager = get_mcp_manager()
        return manager.is_available("pollo")

    async def close(self):
        pass  # Lifecycle managed by MCPClientManager

    # ─────────────────────────────────────────────────────────────────────────
    # VIDEO GENERATION
    # ─────────────────────────────────────────────────────────────────────────

    async def text_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate video from text prompt via Pollo MCP.

        params:
            prompt: str (required)
            model: str (optional, default pollo-v1-6)
            duration: int (optional, 5 or 10)
            resolution: str (optional, "480p"|"720p"|"1080p")
            aspect_ratio: str (optional, "16:9"|"9:16"|"1:1")
        """
        self._log_request("text_to_video", params)
        manager = get_mcp_manager()

        arguments = {
            "model": _parse_model(params.get("model")),
            "prompt": params["prompt"],
        }

        if params.get("duration"):
            arguments["length"] = params["duration"]
        if params.get("resolution"):
            arguments["resolution"] = params["resolution"]
        if params.get("aspect_ratio"):
            arguments["aspectRatio"] = params["aspect_ratio"]

        result = await manager.call("pollo", "text2video", arguments)
        return self._normalize_result(result, "video")

    async def image_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate video from image via Pollo MCP.

        params:
            image_url: str (required, HTTPS URL)
            prompt: str (optional)
            model: str (optional)
            duration: int (optional)
        """
        self._log_request("image_to_video", params)
        manager = get_mcp_manager()

        arguments = {
            "model": _parse_model(params.get("model")),
            "image": params["image_url"],
        }
        if params.get("prompt"):
            arguments["prompt"] = params["prompt"]
        if params.get("duration"):
            arguments["length"] = params["duration"]
        if params.get("aspect_ratio"):
            arguments["aspectRatio"] = params["aspect_ratio"]

        result = await manager.call("pollo", "img2video", arguments)
        return self._normalize_result(result, "video")

    async def video_style_transfer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Video style transfer — use img2video with a style prompt.
        Pollo doesn't have a dedicated V2V tool, so we approximate.
        """
        self._log_request("video_style_transfer", params)

        # Extract a frame URL if available, otherwise use image_url
        image_url = params.get("image_url") or params.get("video_url")
        if not image_url:
            raise ValueError("image_url or video_url required for style transfer")

        return await self.image_to_video({
            "image_url": image_url,
            "prompt": params.get("prompt", "stylized video"),
            "model": params.get("model", DEFAULT_VIDEO_MODEL),
            "duration": params.get("duration", 5),
        })

    # ─────────────────────────────────────────────────────────────────────────
    # RESULT NORMALIZATION
    # ─────────────────────────────────────────────────────────────────────────

    def _normalize_result(
        self, mcp_result: Dict[str, Any], media_type: str
    ) -> Dict[str, Any]:
        """
        Normalize MCP tool result to the standard provider response format.

        Standard format:
            {"success": True, "task_id": str, "output": {"video_url": str}}
        """
        # Pollo MCP getTaskStatus returns {taskId, generations: [{url, status}]}
        # text2video/img2video may return taskId for polling or final result

        task_id = mcp_result.get("taskId", "")
        generations = mcp_result.get("generations", [])

        # If we got generations with a URL, it's done
        if generations:
            gen = generations[0]
            url = gen.get("url", "")
            if url:
                self._log_response("generation", True)
                output_key = "video_url" if media_type == "video" else "image_url"
                return {
                    "success": True,
                    "task_id": task_id,
                    "output": {output_key: url},
                }

        # If we only got a taskId, the MCP tool handled polling internally
        # but returned before completion — check for url in raw
        url = mcp_result.get("url", "")
        if url:
            self._log_response("generation", True)
            output_key = "video_url" if media_type == "video" else "image_url"
            return {
                "success": True,
                "task_id": task_id,
                "output": {output_key: url},
            }

        # Check raw text response for URL
        raw = mcp_result.get("raw", "")
        if raw and ("http://" in raw or "https://" in raw):
            # Extract URL from raw text
            import re
            urls = re.findall(r'https?://[^\s"\'<>]+', raw)
            if urls:
                self._log_response("generation", True)
                output_key = "video_url" if media_type == "video" else "image_url"
                return {
                    "success": True,
                    "task_id": task_id,
                    "output": {output_key: urls[0]},
                }

        # Task submitted but not yet complete
        if task_id:
            self._log_response("generation", True)
            return {
                "success": True,
                "task_id": task_id,
                "output": {"status": "processing"},
            }

        self._log_response("generation", False, f"Unexpected result: {mcp_result}")
        raise Exception(f"Pollo MCP returned unexpected result: {mcp_result}")
