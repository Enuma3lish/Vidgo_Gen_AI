"""
Pollo.ai MCP Provider — PRIMARY provider for video generation.

Communicates with the pollo-mcp server (npm: pollo-mcp v3.x) via MCP protocol.

IMPORTANT — Pollo MCP tool architecture (from pollo-mcp v3.0.4 source):
  Tool names are DYNAMIC, constructed per-model at startup:
    - text2video_{modelAlias}  (e.g. text2video_pollo-v1-6, text2video_kling-v2)
    - img2video_{modelAlias}   (e.g. img2video_pollo-v1-6, img2video_kling-v2)
    - getTaskStatus            (static name)

  The model is NOT passed as a parameter — it's encoded in the tool name.
  Each tool's input schema comes from the API's mcp_config.json and varies by model.
  All schemas have additionalProperties: false, so unknown keys cause errors.

  text2video tools return IMMEDIATELY with a taskId (no internal polling).
  img2video tools return IMMEDIATELY with a taskId (no internal polling).
  getTaskStatus must be called separately to poll for completion.

  Response format from text2video_*/img2video_*:
    Text: "The generation task status is {status}, and task id is {taskId}."
    structuredContent: {"taskId": "..."}

  Response format from getTaskStatus (completed):
    Text: "The task[{id}] generation has been completed. You can download
           the video through the link below...\n\t{url1}\n\t{url2}"
    structuredContent: {"urls": ["..."]}

Common parameter schemas (vary by model, check mcp_config.json):
  pollo-v1-6 t2v: prompt(required), resolution(required), length, mode, aspectRatio, seed
  pollo-v1-6 i2v: image(required), prompt, resolution, mode, length, seed, imageTail
  kling-v2 t2v:   prompt(required), aspectRatio, negativePrompt, strength, length
  kling-v2 i2v:   image(required), prompt, negativePrompt, strength, length
"""
import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from app.providers.base import BaseProvider, VideoGenerationProvider
from app.services.mcp_client import get_mcp_manager

logger = logging.getLogger(__name__)

# Default model alias when none specified
DEFAULT_VIDEO_MODEL = "pollo-v1-6"

# Polling config for getTaskStatus
POLL_INTERVAL_SECONDS = 10
POLL_MAX_ATTEMPTS = 60  # 10 minutes max


def _resolve_model_alias(model_str: Optional[str]) -> str:
    """Return a clean model alias string, defaulting to pollo-v1-6."""
    return model_str.strip() if model_str and model_str.strip() else DEFAULT_VIDEO_MODEL


class PolloMCPProvider(VideoGenerationProvider):
    """
    Pollo.ai via MCP — primary video generation provider.
    Supports 50+ models via dynamic per-model MCP tools.
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

        model_alias = _resolve_model_alias(params.get("model"))
        tool_name = self._resolve_tool_name(model_alias, "t2v")

        arguments: Dict[str, Any] = {
            "prompt": params["prompt"],
        }
        if params.get("duration"):
            arguments["length"] = params["duration"]
        if params.get("resolution"):
            arguments["resolution"] = params["resolution"]
        if params.get("aspect_ratio"):
            arguments["aspectRatio"] = params["aspect_ratio"]

        return await self._submit_and_poll(tool_name, arguments)

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

        model_alias = _resolve_model_alias(params.get("model"))
        tool_name = self._resolve_tool_name(model_alias, "i2v")

        arguments: Dict[str, Any] = {
            "image": params["image_url"],
        }
        if params.get("prompt"):
            arguments["prompt"] = params["prompt"]
        if params.get("duration"):
            arguments["length"] = params["duration"]
        if params.get("aspect_ratio"):
            arguments["aspectRatio"] = params["aspect_ratio"]

        return await self._submit_and_poll(tool_name, arguments)

    async def video_style_transfer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Video style transfer — use img2video with a style prompt.
        Pollo doesn't have a dedicated V2V tool, so we approximate.
        """
        self._log_request("video_style_transfer", params)

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
    # TOOL NAME RESOLUTION
    # ─────────────────────────────────────────────────────────────────────────

    def _resolve_tool_name(self, model_alias: str, capability: str) -> str:
        """
        Resolve the dynamic MCP tool name for a given model and capability.

        Pollo MCP v3.x creates per-model tools:
          text2video_{modelAlias}  (capability "t2v")
          img2video_{modelAlias}   (capability "i2v")

        Falls back to checking the available tools list if the expected name
        isn't found (e.g. model alias mismatch).
        """
        prefix = "text2video" if capability == "t2v" else "img2video"
        expected_name = f"{prefix}_{model_alias}"

        manager = get_mcp_manager()
        available = manager.list_tools("pollo")
        available_names = [t["name"] for t in available]

        if expected_name in available_names:
            return expected_name

        # Try to find an alternative tool with the same prefix
        matching = [n for n in available_names if n.startswith(f"{prefix}_")]
        if matching:
            fallback = matching[0]
            logger.warning(
                f"[Pollo MCP] Tool '{expected_name}' not found. "
                f"Using fallback: '{fallback}'. Available: {available_names}"
            )
            return fallback

        # No tools found — return expected name and let the call fail
        # (this handles the case where tools haven't been cached yet)
        logger.warning(
            f"[Pollo MCP] No {prefix}_* tools found. "
            f"Attempting '{expected_name}'. Available: {available_names}"
        )
        return expected_name

    # ─────────────────────────────────────────────────────────────────────────
    # SUBMIT + POLL WORKFLOW
    # ─────────────────────────────────────────────────────────────────────────

    async def _submit_and_poll(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Submit a generation task and poll getTaskStatus until completion.

        1. Call text2video_*/img2video_* → get taskId
        2. Poll getTaskStatus(taskId) every POLL_INTERVAL_SECONDS
        3. Return normalized result when task completes or raise on failure/timeout
        """
        manager = get_mcp_manager()

        # Step 1: Submit the generation task
        submit_result = await manager.call("pollo", tool_name, arguments)
        task_id = self._extract_task_id(submit_result)

        if not task_id:
            # If we somehow got a final URL already, return it
            url = self._extract_url_from_result(submit_result)
            if url:
                self._log_response("generation", True)
                return {
                    "success": True,
                    "task_id": "",
                    "output": {"video_url": url},
                }
            raise Exception(
                f"Pollo MCP '{tool_name}' did not return a taskId: {submit_result}"
            )

        logger.info(f"[Pollo MCP] Task submitted: {task_id} via {tool_name}")

        # Step 2: Poll getTaskStatus
        for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

            try:
                status_result = await manager.call(
                    "pollo", "getTaskStatus", {"taskId": task_id}
                )
            except Exception as e:
                logger.warning(
                    f"[Pollo MCP] getTaskStatus attempt {attempt} failed: {e}"
                )
                continue

            raw = status_result.get("raw", "")

            # Check for failure
            if "has failed" in raw:
                self._log_response("generation", False, f"Task {task_id} failed")
                raise Exception(f"Pollo MCP task {task_id} failed")

            # Check for processing (still in progress)
            if "is processing" in raw or "is not found" in raw:
                logger.info(
                    f"[Pollo MCP] Task {task_id} still processing "
                    f"(attempt {attempt}/{POLL_MAX_ATTEMPTS})"
                )
                continue

            # Check for completion — extract URLs
            url = self._extract_url_from_result(status_result)
            if url:
                self._log_response("generation", True)
                logger.info(
                    f"[Pollo MCP] Task {task_id} completed after {attempt} polls"
                )
                return {
                    "success": True,
                    "task_id": task_id,
                    "output": {"video_url": url},
                }

            # Unknown status — keep polling
            logger.info(
                f"[Pollo MCP] Task {task_id} unknown status "
                f"(attempt {attempt}/{POLL_MAX_ATTEMPTS}): {raw[:200]}"
            )

        # Timeout
        self._log_response("generation", False, f"Task {task_id} timed out")
        raise Exception(
            f"Pollo MCP task {task_id} timed out after "
            f"{POLL_MAX_ATTEMPTS * POLL_INTERVAL_SECONDS}s"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # RESULT PARSING
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_task_id(self, mcp_result: Dict[str, Any]) -> Optional[str]:
        """
        Extract taskId from a Pollo MCP submit response.

        The MCP tool returns text like:
          "The generation task status is waiting, and task id is abc123."
        Or structured: {"taskId": "abc123"}
        """
        # Try structured fields first
        task_id = mcp_result.get("taskId", "")
        if task_id:
            return task_id

        # Parse from raw text
        raw = mcp_result.get("raw", "")
        if raw:
            # Pattern: "task id is {id}"
            match = re.search(r"task\s+id\s+is\s+([a-zA-Z0-9_-]+)", raw)
            if match:
                return match.group(1)
            # Pattern: "task[{id}]"
            match = re.search(r"task\[([a-zA-Z0-9_-]+)\]", raw)
            if match:
                return match.group(1)

        return None

    def _extract_url_from_result(self, mcp_result: Dict[str, Any]) -> Optional[str]:
        """
        Extract a video URL from a Pollo MCP response (submit or getTaskStatus).

        getTaskStatus returns text like:
          "The task[abc123] generation has been completed.
           You can download the video through the link below...
           \thttps://cdn.pollo.ai/..."
        Or structured: {"urls": ["https://..."]}
        """
        # Try structured fields
        urls = mcp_result.get("urls", [])
        if urls and isinstance(urls, list):
            return urls[0]

        url = mcp_result.get("url", "")
        if url:
            return url

        # Parse from raw text
        raw = mcp_result.get("raw", "")
        if raw:
            found = re.findall(r'https?://[^\s"\'<>]+', raw)
            if found:
                return found[0]

        return None
