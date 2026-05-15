"""
Provider Router — Routes AI tasks to the correct provider.

Architecture:
1. PiAPI MCP/REST — PRIMARY for normal generation flows
2. Pollo.ai       — BACKUP when PiAPI paths fail, especially video
3. Vertex AI      — FINAL backup for image/video tasks and primary for Gemini workflows
4. A2E            — BACKUP for avatar tasks when PiAPI fails
5. GCS Storage   — Persists CDN URLs to Google Cloud Storage
"""
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import logging
import os

from app.providers.piapi_mcp_provider import PiAPIMCPProvider
from app.providers.pollo_mcp_provider import PolloMCPProvider
from app.providers.piapi_provider import PiAPIProvider
from app.providers.vertex_ai_provider import VertexAIProvider
from app.providers.pollo_provider import PolloProvider
from app.providers.a2e_provider import A2EProvider
from app.core.config import get_settings
from app.services.gcs_storage_service import get_gcs_storage
from app.services.email_service import email_service

logger = logging.getLogger(__name__)
settings = get_settings()


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
    # Premium / flagship tiers — PiAPI-only, no fallback path. These map to
    # the new ServicePricing rows (image_generation_premium, video_generation_
    # professional, video_flagship) and bypass the model-override routing in
    # _get_providers_for_task since the model identity is baked into the
    # task type itself.
    MIDJOURNEY_T2I = "midjourney_imagine"
    KLING_VIDEO    = "kling_video_generation"
    LUMA_VIDEO     = "luma_video_generation"


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class ProviderRouter:
    """
    Routes AI tasks to the correct provider.

    Routing:
            - Normal generation → PiAPI MCP/REST first, then Pollo, then Vertex/Gemini
            - Explicit model choices → REST first so provider-specific model IDs are honored
            - 3D generation → PiAPI REST Trellis only
            - Moderation / Material Gen → Vertex AI Gemini (primary)

        Fallback: If the primary path is unavailable, tries the configured backups.
    """

    # ── Routing config ──
    # "primary" is tried first, then "backup", "tertiary", "fallback".
    # REST-first exceptions are handled in _get_providers_for_task.
    ROUTING_CONFIG = {
        # Video tasks — PiAPI first, then Pollo.ai, then Vertex AI/Veo.
        TaskType.I2V: {"primary": "piapi_mcp", "backup": "piapi", "tertiary": "pollo_mcp", "fallback": "pollo", "final": "vertex_ai"},
        TaskType.T2V: {"primary": "piapi_mcp", "backup": "piapi", "tertiary": "pollo_mcp", "fallback": "pollo", "final": "vertex_ai"},
        TaskType.V2V: {"primary": "piapi_mcp", "backup": "pollo", "tertiary": "pollo_mcp", "fallback": "vertex_ai"},

        # Image tasks — PiAPI first. Pollo is included where useful, then Gemini via Vertex AI.
        TaskType.T2I:                {"primary": "piapi_mcp", "backup": "piapi", "tertiary": "pollo", "fallback": "vertex_ai"},
        TaskType.I2I:                {"primary": "piapi_mcp", "backup": "piapi", "tertiary": "vertex_ai", "fallback": None},
        TaskType.EFFECTS:            {"primary": "piapi_mcp", "backup": "piapi", "tertiary": "vertex_ai", "fallback": None},
        TaskType.UPSCALE:            {"primary": "piapi_mcp", "backup": "piapi", "tertiary": "vertex_ai", "fallback": None},
        TaskType.BACKGROUND_REMOVAL: {"primary": "piapi_mcp", "backup": "piapi", "tertiary": "vertex_ai", "fallback": None},

        # Specialized tasks — MCP primary except REST-only 3D
        TaskType.INTERIOR:    {"primary": "piapi_mcp", "backup": "piapi", "tertiary": "vertex_ai", "fallback": None},
        TaskType.INTERIOR_3D: {"primary": "piapi",     "backup": None,    "tertiary": None,        "fallback": None},
        # Avatar uses PiAPI first, then A2E.ai for avatar/digital-human fallback.
        TaskType.AVATAR:      {"primary": "piapi",     "backup": "a2e",   "tertiary": None,        "fallback": None},

        # Vertex AI-only tasks
        TaskType.MODERATION:          {"primary": "vertex_ai", "backup": None, "fallback": None},
        TaskType.MATERIAL_GENERATION: {"primary": "vertex_ai", "backup": None, "fallback": None},

        # Premium tiers — PiAPI REST is the only path. Pollo/Vertex don't expose
        # these models with comparable params, so we deliberately don't list a
        # backup; failure surfaces as a user error rather than silently routing
        # to a cheaper substitute (would defeat the purpose of charging the
        # flagship credit cost).
        TaskType.MIDJOURNEY_T2I: {"primary": "piapi", "backup": None, "tertiary": None, "fallback": None},
        TaskType.KLING_VIDEO:    {"primary": "piapi", "backup": None, "tertiary": None, "fallback": None},
        TaskType.LUMA_VIDEO:     {"primary": "piapi", "backup": None, "tertiary": None, "fallback": None},
    }

    POLLO_VIDEO_MODEL_IDS = {
        "pixverse_v4.5",
        "pixverse_v5",
        "kling_v1.5",
        "kling_v1_5",
        "kling_v2",
        "luma_ray2",
        "kling2.5",
        "hailuo",
        "wan2.6",
        "pollo-v1-6",
    }

    SYSTEM_FAILURE_HINTS = (
        "internal",
        "http 500",
        "http 502",
        "http 503",
        "http 504",
        "server error",
        "service unavailable",
        "temporarily unavailable",
        "timeout",
        "timed out",
        "connection",
        "connect",
        "unreachable",
        "unhealthy",
        "health check",
        "not responding",
        "not configured",
        "quota",
        "rate limit",
        "balance",
        "credit",
    )

    NON_ALERT_FAILURE_HINTS = (
        "required",
        "validation",
        "invalid",
        "unsupported",
        "unknown task type",
        "doesn't support",
        "valueerror",
    )

    def __init__(self):
        # MCP providers
        self.pollo_mcp = PolloMCPProvider()
        self.piapi_mcp = PiAPIMCPProvider()

        # Vertex AI (replaces old GeminiProvider)
        self.vertex_ai = VertexAIProvider()

        # Legacy REST providers (fallback)
        self.piapi = PiAPIProvider()
        self.pollo = PolloProvider()
        self.a2e = A2EProvider()

        self._status_cache: Dict[str, Dict] = {}
        self._last_health_check: Dict[str, datetime] = {}
        self._failure_counts: Dict[str, int] = {}
        self._last_provider_alert: Dict[str, datetime] = {}
        self._provider_alert_cooldown = timedelta(
            minutes=max(1, settings.PROVIDER_ALERT_COOLDOWN_MINUTES)
        )
        self._provider_health_cache_ttl = timedelta(
            seconds=max(5, settings.PROVIDER_HEALTH_CACHE_SECONDS)
        )
        self._provider_circuit_breaker_failures = max(
            1, settings.PROVIDER_CIRCUIT_BREAKER_FAILURES
        )
        self._provider_circuit_breaker_cooldown = timedelta(
            seconds=max(30, settings.PROVIDER_CIRCUIT_BREAKER_COOLDOWN_SECONDS)
        )

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
        Tries: primary → backup → tertiary → fallback (REST).
        Optionally persists result to GCS.
        """
        config = self.ROUTING_CONFIG.get(task_type)
        if not config:
            raise ValueError(f"Unknown task type: {task_type}")

        providers_to_try = self._get_providers_for_task(task_type, params)
        candidate_providers, skipped_providers = self._route_candidates(providers_to_try)

        if not candidate_providers:
            error_msg = self._get_user_friendly_error(
                task_type,
                providers_to_try[0],
                providers_to_try[1] if len(providers_to_try) > 1 else None,
                "No configured providers available",
            )
            raise Exception(error_msg)

        last_error = None
        for provider_name in candidate_providers:
            provider_index = providers_to_try.index(provider_name)
            attempt_started = datetime.utcnow()
            try:
                result = await self._execute_on_provider(
                    provider_name, task_type, params
                )

                # A provider returning {"success": false, ...} is a soft failure;
                # do NOT record success and do NOT return — raise so the loop
                # falls through to the next provider in the chain.
                if isinstance(result, dict) and result.get("success") is False:
                    err_msg = result.get("error") or result.get("message") or "provider returned success=false"
                    raise Exception(f"{provider_name} soft-failed: {err_msg}")

                self._record_success(provider_name)

                # Persist to GCS if enabled
                if persist_to_gcs:
                    result = await self._persist_result_to_gcs(result, task_type)

                # Normalize backend-local static paths to absolute public URLs so the
                # frontend can load results from a separate origin like vidgo.co.
                result = self._absolutize_local_media_urls(result)

                # Telemetry: which provider in the configured chain actually
                # served this task and how long it took. Lets us spot when the
                # primary (e.g. piapi_mcp) is consistently being skipped or
                # falling through to the REST backup on Cloud Run.
                elapsed_ms = int((datetime.utcnow() - attempt_started).total_seconds() * 1000)
                logger.info(
                    "provider_router.route ok task=%s primary=%s chain=%s used=%s rank=%d elapsed_ms=%d skipped=%s",
                    task_type.value if hasattr(task_type, "value") else task_type,
                    providers_to_try[0],
                    "->".join(providers_to_try),
                    provider_name,
                    provider_index,
                    elapsed_ms,
                    skipped_providers or [],
                )

                # Persist a metrics row (best-effort; failures here must not
                # surface as user errors). Powers /admin/models/<key>/metrics.
                await self._record_metric(
                    task_type=task_type,
                    provider=provider_name,
                    params=params,
                    duration_ms=elapsed_ms,
                    success=True,
                    used_backup=(provider_index > 0),
                )

                return {
                    **result,
                    "used_backup": provider_index > 0,
                    "primary_provider": providers_to_try[0],
                    "provider_used": provider_name,
                    **({"backup_provider": provider_name, "primary_failed": True} if provider_index > 0 else {}),
                    **({"skipped_providers": skipped_providers} if skipped_providers else {}),
                }
            except Exception as e:
                elapsed_ms = int((datetime.utcnow() - attempt_started).total_seconds() * 1000)
                logger.error(
                    "provider_router.route fail task=%s provider=%s rank=%d elapsed_ms=%d error=%s",
                    task_type.value if hasattr(task_type, "value") else task_type,
                    provider_name,
                    provider_index,
                    elapsed_ms,
                    e,
                )
                # Per-attempt failure metric. If a later provider in the chain
                # succeeds the user still gets a result; the dashboard groups
                # by model_used so the failed attempt of the primary still
                # shows up as a failure for THAT model.
                await self._record_metric(
                    task_type=task_type,
                    provider=provider_name,
                    params=params,
                    duration_ms=elapsed_ms,
                    success=False,
                    used_backup=False,
                    error_message=str(e),
                )
                self._record_failure(provider_name, str(e))
                await self._maybe_alert_provider_failure(
                    provider_name=provider_name,
                    task_type=task_type,
                    error=str(e),
                    fallback_provider=self._next_candidate_provider(candidate_providers, provider_name),
                    request_params=params,
                )
                last_error = str(e)

        error_msg = self._get_user_friendly_error(
            task_type, providers_to_try[0],
            providers_to_try[1] if len(providers_to_try) > 1 else None,
            last_error or "All providers failed",
        )
        raise Exception(error_msg)

    def _get_providers_for_task(
        self,
        task_type: TaskType,
        params: Dict[str, Any],
    ) -> list[str]:
        """Return provider order for a task, with model-aware overrides where needed."""
        config = self.ROUTING_CONFIG[task_type]

        model_id = str(params.get("model") or "").strip()
        has_explicit_model = bool(model_id and model_id != "default")

        if task_type == TaskType.INTERIOR_3D:
            return ["piapi"]

        if task_type == TaskType.V2V:
            return self._provider_order_from_config(config)

        if has_explicit_model:
            if task_type in {TaskType.I2V, TaskType.T2V, TaskType.V2V} and model_id in self.POLLO_VIDEO_MODEL_IDS:
                return self._provider_order_with_first(
                    "pollo",
                    ["pollo_mcp", "piapi_mcp", "piapi", "vertex_ai"],
                )

            if task_type in {
                TaskType.T2I,
                TaskType.I2I,
                TaskType.I2V,
                TaskType.T2V,
                TaskType.V2V,
                TaskType.INTERIOR,
                TaskType.AVATAR,
                TaskType.UPSCALE,
                TaskType.EFFECTS,
                TaskType.BACKGROUND_REMOVAL,
            }:
                return self._provider_order_with_first(
                    "piapi",
                    self._provider_order_from_config(config),
                )

        return self._provider_order_from_config(config)

    def _provider_order_from_config(self, config: Dict[str, Optional[str]]) -> list[str]:
        providers_to_try: list[str] = []
        for key in ("primary", "backup", "tertiary", "fallback", "final"):
            provider_name = config.get(key)
            if provider_name and provider_name not in providers_to_try:
                providers_to_try.append(provider_name)

        return providers_to_try

    def _provider_order_with_first(self, first_provider: str, providers: list[str]) -> list[str]:
        ordered = [first_provider]
        for provider_name in providers:
            if provider_name and provider_name not in ordered:
                ordered.append(provider_name)
        return ordered

    def _route_candidates(self, providers: list[str]) -> tuple[list[str], list[str]]:
        """Skip disabled providers and providers with open circuits."""
        if not providers:
            return [], []

        candidates = []
        skipped = []
        for provider_name in providers:
            if self._is_provider_disabled_by_config(provider_name):
                skipped.append(provider_name)
            elif self._is_provider_circuit_open(provider_name):
                skipped.append(provider_name)
            else:
                candidates.append(provider_name)

        if candidates:
            return candidates, skipped

        logger.warning("No provider candidates available for route %s; skipped=%s", providers, skipped)
        return [], skipped

    def _is_provider_disabled_by_config(self, provider: str) -> bool:
        if provider == "piapi_mcp":
            enabled = os.getenv("PIAPI_MCP_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
            return not enabled or not os.getenv("PIAPI_KEY", "")
        if provider == "piapi":
            return not os.getenv("PIAPI_KEY", "")
        if provider in {"pollo", "pollo_mcp"}:
            return not os.getenv("POLLO_API_KEY", "")
        if provider == "a2e":
            return not os.getenv("A2E_API_KEY", "")
        return False

    def _next_candidate_provider(self, candidates: list[str], current_provider: str) -> Optional[str]:
        try:
            index = candidates.index(current_provider)
        except ValueError:
            return None
        return candidates[index + 1] if index + 1 < len(candidates) else None

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

    def _absolutize_local_media_urls(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert backend-local /static media paths into public absolute URLs."""
        output = result.get("output", {})
        public_base = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
        if not public_base:
            return result

        for key in ("image_url", "video_url", "audio_url", "model_url"):
            url = output.get(key)
            if isinstance(url, str) and url.startswith("/"):
                output[key] = f"{public_base}{url}"

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
        if provider == "piapi_mcp":
            return await self._execute_piapi_mcp(task_type, params)
        elif provider == "pollo_mcp":
            return await self._execute_pollo_mcp(task_type, params)
        # Vertex AI (Gemini + Veo)
        elif provider == "vertex_ai":
            return await self._execute_vertex_ai(task_type, params)
        # Legacy REST providers
        elif provider == "piapi":
            return await self._execute_piapi(task_type, params)
        elif provider == "pollo":
            return await self._execute_pollo(task_type, params)
        elif provider == "a2e":
            return await self._execute_a2e(task_type, params)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    # ── MCP Providers ──

    async def _execute_piapi_mcp(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute on PiAPI MCP — primary for video + image/specialized."""
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

    async def _execute_pollo_mcp(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute on Pollo MCP — backup for video."""
        if task_type == TaskType.I2V:
            return await self.pollo_mcp.image_to_video(params)
        elif task_type == TaskType.T2V:
            return await self.pollo_mcp.text_to_video(params)
        elif task_type == TaskType.V2V:
            return await self.pollo_mcp.video_style_transfer(params)
        else:
            raise ValueError(f"Pollo MCP doesn't support: {task_type}")

    # ── Vertex AI (Gemini + Veo) ──

    async def _execute_vertex_ai(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute on Vertex AI — Gemini for image/moderation, Veo for video."""
        if task_type == TaskType.MODERATION:
            return await self.vertex_ai.moderate_content(params)
        elif task_type == TaskType.MATERIAL_GENERATION:
            return await self.vertex_ai.generate_material(params)
        elif task_type == TaskType.T2I:
            return await self.vertex_ai.text_to_image(params)
        elif task_type == TaskType.I2I:
            return await self.vertex_ai.image_to_image(params)
        elif task_type == TaskType.INTERIOR:
            return await self.vertex_ai.doodle_interior(params)
        elif task_type == TaskType.BACKGROUND_REMOVAL:
            return await self.vertex_ai.background_removal(params)
        elif task_type == TaskType.UPSCALE:
            return await self.vertex_ai.upscale(params)
        elif task_type == TaskType.EFFECTS:
            return await self.vertex_ai.image_to_image(params)
        elif task_type == TaskType.I2V:
            return await self.vertex_ai.image_to_video(params)
        elif task_type == TaskType.T2V:
            return await self.vertex_ai.text_to_video(params)
        elif task_type == TaskType.V2V:
            return await self.vertex_ai.video_style_transfer(params)
        elif task_type == TaskType.AVATAR:
            return await self.vertex_ai.generate_avatar(params)
        else:
            raise ValueError(f"Vertex AI doesn't support: {task_type}")

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
        elif task_type == TaskType.MIDJOURNEY_T2I:
            return await self.piapi.midjourney_imagine(params)
        elif task_type == TaskType.KLING_VIDEO:
            return await self.piapi.kling_video_generation(params)
        elif task_type == TaskType.LUMA_VIDEO:
            return await self.piapi.luma_video_generation(params)
        else:
            raise ValueError(f"PiAPI doesn't support: {task_type}")

    async def _execute_pollo(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute on Pollo REST — T2I backup + video fallback."""
        if task_type == TaskType.T2I:
            return await self.pollo.text_to_image(params)
        elif task_type == TaskType.I2V:
            return await self.pollo.image_to_video(params)
        elif task_type == TaskType.T2V:
            return await self.pollo.text_to_video(params)
        elif task_type == TaskType.V2V:
            # Pollo has no native V2V endpoint; route through video_style_transfer,
            # which feeds the first frame (image_url) into per-model I2V.
            return await self.pollo.video_style_transfer(params)
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
            if datetime.now() - self._last_health_check[provider] < self._health_cache_ttl():
                cached = self._status_cache.get(provider, {})
                return cached.get("status") == ProviderStatus.HEALTHY

        try:
            provider_instance = self._get_provider_instance(provider)
            if provider_instance is None:
                self._record_failure(provider, "Provider instance unavailable or not configured")
                await self._maybe_alert_provider_failure(
                    provider_name=provider,
                    task_type="health_check",
                    error="Provider instance unavailable or not configured",
                    fallback_provider=None,
                    request_params={},
                )
                return False
            is_healthy = await provider_instance.health_check()
            now = datetime.now()
            if is_healthy:
                self._record_success(provider)
                self._status_cache[provider]["last_check"] = now
            else:
                self._record_failure(provider, "Provider health check reported unhealthy status")
                self._status_cache.setdefault(provider, {})["last_check"] = now
            self._last_health_check[provider] = now
            if not is_healthy:
                await self._maybe_alert_provider_failure(
                    provider_name=provider,
                    task_type="health_check",
                    error="Provider health check reported unhealthy status",
                    fallback_provider=None,
                    request_params={},
                )
            return is_healthy
        except Exception as e:
            logger.error(f"Health check failed for {provider}: {e}")
            self._record_failure(provider, str(e))
            self._status_cache.setdefault(provider, {})["last_check"] = datetime.now()
            await self._maybe_alert_provider_failure(
                provider_name=provider,
                task_type="health_check",
                error=f"Health check failed: {e}",
                fallback_provider=None,
                request_params={},
            )
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
            "vertex_ai": self.vertex_ai,
            "piapi": self.piapi,
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
        now = datetime.now()
        status = (
            ProviderStatus.DOWN
            if count >= self._circuit_breaker_failure_threshold()
            else ProviderStatus.DEGRADED
        )
        status_entry = {
            "status": status,
            "error": error,
            "failure_count": count,
            "last_failure": now,
        }
        if status == ProviderStatus.DOWN:
            status_entry["circuit_open_until"] = now + self._circuit_breaker_cooldown()
        self._status_cache[provider] = status_entry

    def _is_provider_circuit_open(self, provider: str) -> bool:
        cached = self._status_cache.get(provider, {})
        open_until = cached.get("circuit_open_until")
        if not isinstance(open_until, datetime):
            return False

        if datetime.now() >= open_until:
            cached.pop("circuit_open_until", None)
            return False

        return True

    def _health_cache_ttl(self) -> timedelta:
        return getattr(self, "_provider_health_cache_ttl", timedelta(seconds=60))

    def _circuit_breaker_failure_threshold(self) -> int:
        return getattr(self, "_provider_circuit_breaker_failures", 3)

    def _circuit_breaker_cooldown(self) -> timedelta:
        return getattr(self, "_provider_circuit_breaker_cooldown", timedelta(seconds=180))

    def _should_alert_provider_failure(self, provider: str, error: str) -> bool:
        if not provider:
            return False

        normalized_error = error.lower()
        if any(token in normalized_error for token in self.NON_ALERT_FAILURE_HINTS):
            return False

        return any(token in normalized_error for token in self.SYSTEM_FAILURE_HINTS)

    async def _maybe_alert_provider_failure(
        self,
        provider_name: str,
        task_type: TaskType | str,
        error: str,
        fallback_provider: Optional[str],
        request_params: Dict[str, Any],
    ) -> None:
        if not self._should_alert_provider_failure(provider_name, error):
            return

        now = datetime.now()
        last_alert = self._last_provider_alert.get(provider_name)
        if last_alert and now - last_alert < self._provider_alert_cooldown:
            return

        self._last_provider_alert[provider_name] = now

        task_label = task_type.value if isinstance(task_type, TaskType) else str(task_type)

        try:
            await email_service.send_provider_failure_alert(
                provider_name=provider_name,
                task_type=task_label,
                error=error,
                fallback_provider=fallback_provider,
                request_params=request_params,
            )
        except Exception as alert_error:
            logger.error(
                "Failed to send provider failure alert for %s: %s",
                provider_name,
                alert_error,
            )

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
        for provider in ["piapi_mcp", "pollo_mcp", "vertex_ai", "piapi", "pollo", "a2e"]:
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
                "last_success": cached.get("last_success").isoformat()
                if cached.get("last_success")
                else None,
                "last_failure": cached.get("last_failure").isoformat()
                if cached.get("last_failure")
                else None,
                "circuit_open": self._is_provider_circuit_open(provider),
                "circuit_open_until": cached.get("circuit_open_until").isoformat()
                if cached.get("circuit_open_until")
                else None,
                "error": cached.get("error"),
            }
        return status

    async def check_service_status(self) -> Dict[str, Any]:
        status = {}
        all_providers = [
            ("piapi_mcp", self.piapi_mcp),
            ("pollo_mcp", self.pollo_mcp),
            ("vertex_ai", self.vertex_ai),
            ("piapi", self.piapi),
            ("pollo", self.pollo),
            ("a2e", self.a2e),
        ]
        # Treat MCP providers as 'disabled' (not an error) when their
        # underlying MCP server is intentionally not started — this avoids
        # spamming admin alerts for a deliberately-off optional provider.
        mcp_disabled = {
            "piapi_mcp": os.getenv("PIAPI_MCP_ENABLED", "false").lower() not in {"1", "true", "yes", "on"},
            "pollo_mcp": not os.getenv("POLLO_API_KEY", ""),
        }
        for name, provider in all_providers:
            if mcp_disabled.get(name):
                status[name] = {
                    "status": "disabled",
                    "message": f"{name} is disabled (MCP server not enabled)",
                }
                continue
            try:
                is_healthy = await provider.health_check()
                status[name] = {
                    "status": "ok" if is_healthy else "error",
                    "message": f"{name} is operational" if is_healthy else f"{name} is not responding",
                }
            except Exception as e:
                status[name] = {"status": "error", "error": str(e)}
        return status

    # ─────────────────────────────────────────────────────────────────────
    # METRICS (Phase C)
    # Lightweight per-call telemetry written to generation_metrics. Powers
    # /api/v1/admin/models/<key>/metrics — success rate / avg latency / per-
    # model call counts. Cost is intentionally NOT captured here: it's
    # derived at query time from ServicePricing.api_cost_usd × call count.
    # ─────────────────────────────────────────────────────────────────────

    def _derive_model_used(self, task_type: TaskType, params: Dict[str, Any]) -> Optional[str]:
        """Best-effort label for the model that handled this call.

        Returns None when we can't tell — the metrics row stores NULL and
        the dashboard groups it under "unknown". Explicit ``params["model"]``
        always wins; otherwise falls back to per-task heuristics for the
        flagship endpoints where we know the convention.
        """
        explicit = str(params.get("model") or "").strip()
        if explicit and explicit != "default":
            return explicit[:128]

        if task_type == TaskType.MIDJOURNEY_T2I:
            mode = params.get("process_mode") or "fast"
            return f"midjourney-{mode}"
        if task_type == TaskType.KLING_VIDEO:
            version = params.get("version") or (
                "2.1-master" if params.get("tier") == "flagship" else "2.6"
            )
            return f"kling-{version}"
        if task_type == TaskType.LUMA_VIDEO:
            return f"luma-{params.get('model_name') or 'ray-v2'}"
        if task_type == TaskType.INTERIOR_3D:
            return f"trellis-{params.get('model_version') or 'v1'}"
        if task_type in (TaskType.I2V, TaskType.T2V):
            return "wan-2.6"
        if task_type == TaskType.AVATAR:
            return "kling-avatar"
        if task_type == TaskType.BACKGROUND_REMOVAL:
            return "image-toolkit"
        if task_type == TaskType.UPSCALE:
            return "image-toolkit-upscale"
        return None

    async def _record_metric(
        self,
        task_type: TaskType,
        provider: str,
        params: Dict[str, Any],
        duration_ms: int,
        success: bool,
        used_backup: bool,
        error_message: Optional[str] = None,
    ) -> None:
        """Best-effort insert into generation_metrics.

        Uses its own AsyncSession so router callers don't need to thread a
        request-scoped session through. NEVER raises — metrics infrastructure
        failure must not surface as user error.
        """
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.model_registry import GenerationMetric

            task_label = task_type.value if hasattr(task_type, "value") else str(task_type)
            model_used = self._derive_model_used(task_type, params)
            err_short = (error_message or "")[:1000] or None
            user_id = params.get("user_id")  # tools.py doesn't pass this today; kept for future opt-in

            async with AsyncSessionLocal() as session:
                session.add(
                    GenerationMetric(
                        task_type=task_label,
                        provider_used=provider,
                        model_used=model_used,
                        duration_ms=duration_ms,
                        success=success,
                        error_message=err_short,
                        used_backup=used_backup,
                        user_id=user_id,
                    )
                )
                await session.commit()
        except Exception as exc:  # pragma: no cover
            logger.warning("metrics write failed task=%s provider=%s: %s", task_type, provider, exc)

    async def close(self):
        await asyncio.gather(
            self.piapi.close(),
            self.vertex_ai.close(),
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
