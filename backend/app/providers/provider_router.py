"""
Provider Router — Routes AI tasks to the correct provider.

Architecture (MCP-based):
1. Pollo.ai MCP  — PRIMARY for video tasks (I2V, T2V, V2V)
2. PiAPI MCP     — PRIMARY for image/specialized tasks (T2I, I2I, Try-On, Interior, Avatar, TTS, Upscale, 3D)
                 — BACKUP for video tasks when Pollo fails
3. Gemini        — BACKUP for image tasks when PiAPI fails + Moderation + Material generation
4. A2E           — BACKUP for avatar tasks when PiAPI fails
5. GCS Storage   — Persists CDN URLs to Google Cloud Storage

Legacy direct-API providers (PiAPI REST, Pollo REST) are kept as fallback
when MCP servers are unavailable.
"""
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import logging

from app.providers.piapi_mcp_provider import PiAPIMCPProvider
from app.providers.pollo_mcp_provider import PolloMCPProvider
from app.providers.piapi_provider import PiAPIProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.pollo_provider import PolloProvider
from app.providers.a2e_provider import A2EProvider
from app.services.gcs_storage_service import get_gcs_storage

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Supported task types."""
    T2I = "text_to_image"
    I2V = "image_to_video"
    T2V = "text_to_video"
    V2V = "video_style_transfer"
    INTERIOR = "interior_design"
    AVATAR = "avatar"
    UPSCALE = "upscale"
    EFFECTS = "effects"
    MODERATION = "moderation"
    BACKGROUND_REMOVAL = "background_removal"
    INTERIOR_3D = "interior_3d"
    I2I = "image_to_image"
    MATERIAL_GENERATION = "material_generation"


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class ProviderRouter:
    """
    Routes AI tasks to the correct provider.

    Primary routing (MCP-based):
      - Video tasks (I2V, T2V, V2V) → Pollo MCP (primary) → PiAPI MCP (backup)
      - Image tasks (T2I, I2I, Effects) → PiAPI MCP (primary) → Gemini (backup)
      - Specialized (Try-On, Interior, Avatar, Upscale, 3D, TTS) → PiAPI MCP (primary)
      - Moderation / Material Gen → Gemini (only)
      - BG Removal → Local rembg (via PiAPI MCP provider)

    Fallback: If MCP servers are unavailable, falls back to direct REST providers.
    """

    # ── Routing config ──
    # "primary" is tried first, "backup" on failure, "fallback" if MCP is down
    ROUTING_CONFIG = {
        # Video tasks — Pollo MCP primary, PiAPI MCP backup
        TaskType.I2V: {"primary": "pollo_mcp", "backup": "piapi_mcp", "fallback": "pollo"},
        TaskType.T2V: {"primary": "pollo_mcp", "backup": "piapi_mcp", "fallback": "pollo"},
        TaskType.V2V: {"primary": "pollo_mcp", "backup": "piapi_mcp", "fallback": "pollo"},

        # Image tasks — PiAPI MCP primary, Gemini backup
        TaskType.T2I:                {"primary": "piapi_mcp", "backup": "gemini", "fallback": "piapi"},
        TaskType.I2I:                {"primary": "piapi_mcp", "backup": "gemini", "fallback": "piapi"},
        TaskType.EFFECTS:            {"primary": "piapi_mcp", "backup": "gemini", "fallback": "piapi"},
        TaskType.UPSCALE:            {"primary": "piapi_mcp", "backup": "gemini", "fallback": "piapi"},
        TaskType.BACKGROUND_REMOVAL: {"primary": "piapi_mcp", "backup": "gemini", "fallback": "piapi"},

        # Specialized tasks — PiAPI MCP only (no other provider supports these)
        TaskType.INTERIOR:    {"primary": "piapi_mcp", "backup": "gemini", "fallback": "piapi"},
        TaskType.INTERIOR_3D: {"primary": "piapi_mcp", "backup": None,    "fallback": "piapi"},
        TaskType.AVATAR:      {"primary": "piapi_mcp", "backup": "a2e",   "fallback": "piapi"},

        # Gemini-only tasks
        TaskType.MODERATION:          {"primary": "gemini", "backup": None, "fallback": None},
        TaskType.MATERIAL_GENERATION: {"primary": "gemini", "backup": None, "fallback": None},
    }

    def __init__(self):
        # MCP providers (primary)
        self.pollo_mcp = PolloMCPProvider()
        self.piapi_mcp = PiAPIMCPProvider()

        # Legacy REST providers (fallback)
        self.piapi = PiAPIProvider()
        self.gemini = GeminiProvider()
        self.pollo = PolloProvider()
        self.a2e = A2EProvider()

        self._status_cache: Dict[str, Dict] = {}
        self._last_health_check: Dict[str, datetime] = {}
        self._failure_counts: Dict[str, int] = {}

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN ROUTING METHOD
    # ─────────────────────────────────────────────────────────────────────────

    async def route(
        self,
        task_type: TaskType,
        params: Dict[str, Any],
        user_tier: str = "starter",
        persist_to_gcs: bool = True,
    ) -> Dict[str, Any]:
        """
        Route request to the appropriate provider.
        Tries: primary (MCP) → backup → fallback (REST).
        Optionally persists result to GCS.
        """
        config = self.ROUTING_CONFIG.get(task_type)
        if not config:
            raise ValueError(f"Unknown task type: {task_type}")

        providers_to_try = []
        for key in ("primary", "backup", "fallback"):
            p = config.get(key)
            if p and p not in providers_to_try:
                providers_to_try.append(p)

        last_error = None
        for i, provider_name in enumerate(providers_to_try):
            try:
                result = await self._execute_on_provider(
                    provider_name, task_type, params
                )
                self._record_success(provider_name)

                # Persist to GCS if enabled
                if persist_to_gcs:
                    result = await self._persist_result_to_gcs(result, task_type)

                return {
                    **result,
                    "used_backup": i > 0,
                    "primary_provider": providers_to_try[0],
                    "provider_used": provider_name,
                    **({"backup_provider": provider_name, "primary_failed": True} if i > 0 else {}),
                }
            except Exception as e:
                logger.error(f"Provider {provider_name} failed for {task_type}: {e}")
                self._record_failure(provider_name, str(e))
                last_error = str(e)

        error_msg = self._get_user_friendly_error(
            task_type, providers_to_try[0],
            providers_to_try[1] if len(providers_to_try) > 1 else None,
            last_error or "All providers failed",
        )
        raise Exception(error_msg)

    # ─────────────────────────────────────────────────────────────────────────
    # GCS PERSISTENCE
    # ─────────────────────────────────────────────────────────────────────────

    async def _persist_result_to_gcs(
        self, result: Dict[str, Any], task_type: TaskType
    ) -> Dict[str, Any]:
        """Download CDN URL and persist to GCS, replacing the URL in result."""
        gcs = get_gcs_storage()
        if not gcs.enabled:
            return result

        output = result.get("output", {})
        media_type = self._task_to_media_type(task_type)

        for key in ("image_url", "video_url", "audio_url", "model_url"):
            url = output.get(key)
            if url and url.startswith("http"):
                try:
                    persisted_url = await gcs.persist_url(url, media_type=media_type)
                    output[key] = persisted_url
                except Exception as e:
                    logger.warning(f"GCS persist failed for {key}, keeping CDN URL: {e}")

        result["output"] = output
        return result

    def _task_to_media_type(self, task_type: TaskType) -> str:
        video_tasks = {TaskType.I2V, TaskType.T2V, TaskType.V2V, TaskType.AVATAR}
        if task_type in video_tasks:
            return "video"
        if task_type == TaskType.INTERIOR_3D:
            return "model"
        return "image"

    # ─────────────────────────────────────────────────────────────────────────
    # PROVIDER EXECUTION
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_tier_overrides(
        self,
        task_type: TaskType,
        params: Dict[str, Any],
        user_tier: str,
    ) -> Dict[str, Any]:
        """Apply tier-based parameter overrides."""
        from app.services.tier_config import FREE_TIER, PAID_TIER

        tier_cfg = FREE_TIER if user_tier == "free" else PAID_TIER

        type_key_map = {
            TaskType.T2I: "t2i",
            TaskType.I2V: "i2v",
            TaskType.T2V: "t2v",
            TaskType.V2V: "t2v",
            TaskType.INTERIOR: "interior",
            TaskType.INTERIOR_3D: "interior_3d",
            TaskType.AVATAR: "avatar",
            TaskType.BACKGROUND_REMOVAL: "bg_removal",
            TaskType.EFFECTS: "effect",
            TaskType.I2I: "i2i",
        }

        key = type_key_map.get(task_type)
        if not key:
            return params

        model_cfg = tier_cfg["models"].get(key, {})

        if "resolution" in model_cfg:
            params["resolution"] = model_cfg["resolution"]
        elif "resolution" in params:
            params["resolution"] = tier_cfg["max_resolution"]

        if "duration" in params:
            params["duration"] = min(
                params["duration"], tier_cfg["max_duration"]
            )
        elif "duration" in model_cfg:
            params["duration"] = model_cfg["duration"]

        if "size" in model_cfg and "size" not in params:
            params["size"] = model_cfg["size"]

        if task_type == TaskType.AVATAR:
            params["audio_enabled"] = tier_cfg["audio_enabled"]

        params["_user_tier"] = user_tier
        return params

    async def _execute_on_provider(
        self,
        provider: str,
        task_type: TaskType,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute task on specific provider."""
        # MCP providers
        if provider == "pollo_mcp":
            return await self._execute_pollo_mcp(task_type, params)
        elif provider == "piapi_mcp":
            return await self._execute_piapi_mcp(task_type, params)
        # Legacy REST providers
        elif provider == "piapi":
            return await self._execute_piapi(task_type, params)
        elif provider == "gemini":
            return await self._execute_gemini(task_type, params)
        elif provider == "pollo":
            return await self._execute_pollo(task_type, params)
        elif provider == "a2e":
            return await self._execute_a2e(task_type, params)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    # ── MCP Providers ──

    async def _execute_pollo_mcp(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute on Pollo MCP — primary for video."""
        if task_type == TaskType.I2V:
            return await self.pollo_mcp.image_to_video(params)
        elif task_type == TaskType.T2V:
            return await self.pollo_mcp.text_to_video(params)
        elif task_type == TaskType.V2V:
            return await self.pollo_mcp.video_style_transfer(params)
        else:
            raise ValueError(f"Pollo MCP doesn't support: {task_type}")

    async def _execute_piapi_mcp(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute on PiAPI MCP — primary for image/specialized, backup for video."""
        if task_type == TaskType.T2I:
            return await self.piapi_mcp.text_to_image(params)
        elif task_type == TaskType.I2I:
            return await self.piapi_mcp.image_to_image(params)
        elif task_type == TaskType.I2V:
            return await self.piapi_mcp.image_to_video(params)
        elif task_type == TaskType.T2V:
            return await self.piapi_mcp.text_to_video(params)
        elif task_type == TaskType.V2V:
            return await self.piapi_mcp.video_style_transfer(params)
        elif task_type == TaskType.INTERIOR:
            return await self.piapi_mcp.doodle_interior(params)
        elif task_type == TaskType.UPSCALE:
            return await self.piapi_mcp.upscale(params)
        elif task_type == TaskType.BACKGROUND_REMOVAL:
            return await self.piapi_mcp.background_removal(params)
        elif task_type == TaskType.EFFECTS:
            return await self.piapi_mcp.image_to_image(params)
        elif task_type == TaskType.INTERIOR_3D:
            return await self.piapi_mcp.trellis_3d(params)
        elif task_type == TaskType.AVATAR:
            return await self.piapi_mcp.generate_avatar(params)
        else:
            raise ValueError(f"PiAPI MCP doesn't support: {task_type}")

    # ── Legacy REST Providers ──

    async def _execute_piapi(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute on PiAPI REST (legacy fallback)."""
        if task_type == TaskType.T2I:
            return await self.piapi.text_to_image(params)
        elif task_type == TaskType.I2V:
            return await self.piapi.image_to_video(params)
        elif task_type == TaskType.T2V:
            return await self.piapi.text_to_video(params)
        elif task_type == TaskType.V2V:
            return await self.piapi.video_style_transfer(params)
        elif task_type == TaskType.INTERIOR:
            return await self.piapi.doodle_interior(params)
        elif task_type == TaskType.UPSCALE:
            return await self.piapi.upscale(params)
        elif task_type == TaskType.BACKGROUND_REMOVAL:
            return await self.piapi.background_removal(params)
        elif task_type == TaskType.I2I:
            return await self.piapi.image_to_image(params)
        elif task_type == TaskType.EFFECTS:
            return await self.piapi.image_to_image(params)
        elif task_type == TaskType.INTERIOR_3D:
            return await self.piapi.trellis_3d(params)
        elif task_type == TaskType.AVATAR:
            return await self.piapi.generate_avatar(params)
        else:
            raise ValueError(f"PiAPI doesn't support: {task_type}")

    async def _execute_gemini(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute on Gemini (backup for image tasks)."""
        if task_type == TaskType.MODERATION:
            return await self.gemini.moderate_content(params)
        elif task_type == TaskType.MATERIAL_GENERATION:
            return await self.gemini.generate_material(params)
        elif task_type == TaskType.T2I:
            return await self.gemini.text_to_image(params)
        elif task_type == TaskType.I2I:
            return await self.gemini.image_to_image(params)
        elif task_type == TaskType.INTERIOR:
            return await self.gemini.doodle_interior(params)
        elif task_type == TaskType.BACKGROUND_REMOVAL:
            return await self.gemini.background_removal(params)
        elif task_type == TaskType.UPSCALE:
            return await self.gemini.upscale(params)
        elif task_type == TaskType.EFFECTS:
            return await self.gemini.image_to_image(params)
        elif task_type == TaskType.I2V:
            return await self.gemini.image_to_video(params)
        elif task_type == TaskType.T2V:
            return await self.gemini.text_to_video(params)
        elif task_type == TaskType.V2V:
            return await self.gemini.video_style_transfer(params)
        elif task_type == TaskType.AVATAR:
            return await self.gemini.generate_avatar(params)
        else:
            raise ValueError(f"Gemini doesn't support: {task_type}")

    async def _execute_pollo(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute on Pollo REST (legacy fallback for video)."""
        if task_type == TaskType.I2V:
            return await self.pollo.image_to_video(params)
        elif task_type == TaskType.T2V:
            return await self.pollo.text_to_video(params)
        elif task_type == TaskType.V2V:
            if params.get("video_url"):
                return await self.pollo.effects(params)
            return await self.pollo.multi_model(params)
        else:
            raise ValueError(f"Pollo doesn't support: {task_type}")

    async def _execute_a2e(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute on A2E (backup for avatar)."""
        if task_type == TaskType.AVATAR:
            return await self.a2e.generate_avatar(params)
        raise ValueError(f"A2E doesn't support: {task_type}")

    # ─────────────────────────────────────────────────────────────────────────
    # HEALTH CHECKING
    # ─────────────────────────────────────────────────────────────────────────

    async def _check_provider_health(self, provider: str) -> bool:
        if provider in self._last_health_check:
            if datetime.now() - self._last_health_check[provider] < timedelta(seconds=60):
                cached = self._status_cache.get(provider, {})
                return cached.get("status") == ProviderStatus.HEALTHY

        try:
            provider_instance = self._get_provider_instance(provider)
            if provider_instance is None:
                return False
            is_healthy = await provider_instance.health_check()
            self._status_cache[provider] = {
                "status": ProviderStatus.HEALTHY if is_healthy else ProviderStatus.DOWN,
                "last_check": datetime.now(),
            }
            self._last_health_check[provider] = datetime.now()
            return is_healthy
        except Exception as e:
            logger.error(f"Health check failed for {provider}: {e}")
            self._status_cache[provider] = {
                "status": ProviderStatus.DOWN,
                "error": str(e),
                "last_check": datetime.now(),
            }
            return False

    async def is_piapi_healthy(self) -> bool:
        # Check MCP first, then REST fallback
        mcp_ok = await self._check_provider_health("piapi_mcp")
        if mcp_ok:
            return True
        return await self._check_provider_health("piapi")

    def _get_provider_instance(self, provider: str):
        providers = {
            "pollo_mcp": self.pollo_mcp,
            "piapi_mcp": self.piapi_mcp,
            "piapi": self.piapi,
            "gemini": self.gemini,
            "pollo": self.pollo,
            "a2e": self.a2e,
        }
        return providers.get(provider)

    # ─────────────────────────────────────────────────────────────────────────
    # METRICS
    # ─────────────────────────────────────────────────────────────────────────

    def _record_success(self, provider: str):
        self._failure_counts[provider] = 0
        self._status_cache[provider] = {
            "status": ProviderStatus.HEALTHY,
            "last_success": datetime.now(),
        }

    def _record_failure(self, provider: str, error: str):
        count = self._failure_counts.get(provider, 0) + 1
        self._failure_counts[provider] = count
        if count >= 3:
            self._status_cache[provider] = {
                "status": ProviderStatus.DOWN,
                "error": error,
                "failure_count": count,
                "last_failure": datetime.now(),
            }

    def _get_user_friendly_error(
        self,
        task_type: TaskType,
        primary_provider: str,
        backup_provider: Optional[str],
        error: str,
    ) -> str:
        video_tasks = {TaskType.I2V, TaskType.T2V, TaskType.V2V}
        if task_type in video_tasks:
            return "Video generation services are experiencing issues on all providers. Please try again in a few minutes."
        if task_type == TaskType.AVATAR:
            return "Avatar generation services are experiencing issues. Please try again in a few minutes."
        image_tasks = {TaskType.T2I, TaskType.I2I, TaskType.INTERIOR, TaskType.BACKGROUND_REMOVAL, TaskType.UPSCALE, TaskType.EFFECTS}
        if task_type in image_tasks:
            return "Image generation services are experiencing issues. Please try again in a few minutes."
        if "credit" in error.lower() or "balance" in error.lower():
            return "Service credits are currently depleted. Please try again later."
        if "timeout" in error.lower():
            return "The request timed out. Please try again with a simpler prompt."
        return "Our service is currently experiencing technical difficulties. Please wait a moment and try again!"

    # ─────────────────────────────────────────────────────────────────────────
    # STATUS REPORTING
    # ─────────────────────────────────────────────────────────────────────────

    async def get_all_status(self) -> Dict[str, Any]:
        status = {}
        for provider in ["pollo_mcp", "piapi_mcp", "piapi", "gemini", "pollo", "a2e"]:
            await self._check_provider_health(provider)
            cached = self._status_cache.get(provider, {})
            status[provider] = {
                "status": cached.get("status", ProviderStatus.DOWN).value
                if isinstance(cached.get("status"), ProviderStatus)
                else cached.get("status", "unknown"),
                "last_check": cached.get("last_check", datetime.now()).isoformat()
                if cached.get("last_check")
                else None,
                "failure_count": self._failure_counts.get(provider, 0),
            }
        return status

    async def check_service_status(self) -> Dict[str, Any]:
        status = {}
        all_providers = [
            ("pollo_mcp", self.pollo_mcp),
            ("piapi_mcp", self.piapi_mcp),
            ("piapi", self.piapi),
            ("gemini", self.gemini),
            ("pollo", self.pollo),
            ("a2e", self.a2e),
        ]
        for name, provider in all_providers:
            try:
                is_healthy = await provider.health_check()
                status[name] = {
                    "status": "ok" if is_healthy else "error",
                    "message": f"{name} is operational" if is_healthy else f"{name} is not responding",
                }
            except Exception as e:
                status[name] = {"status": "error", "error": str(e)}
        return status

    async def close(self):
        await asyncio.gather(
            self.piapi.close(),
            self.gemini.close(),
            self.pollo.close(),
            self.a2e.close(),
        )
        # MCP providers don't need explicit close — managed by MCPClientManager


# Global router instance
_router_instance: Optional[ProviderRouter] = None


def get_provider_router() -> ProviderRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = ProviderRouter()
    return _router_instance
