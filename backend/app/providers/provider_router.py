"""
Provider Router — Routes AI tasks to the correct provider.

Architecture (2026-06-23):
1. PiAPI      — PRIMARY for every generation task.
2. Pollo.ai   — BACKUP for every task it can serve: image_to_video, text_to_video,
                text_to_image, image_to_image (and Kling/Sora I2V). Upscale +
                background-removal have no Pollo endpoint → PiAPI-only.
3. A2E        — BACKUP for avatar tasks when PiAPI's Kling avatar fails.
4. Vertex AI  — NOT a generation backup anymore; used ONLY as the primary for
                the Gemini moderation + material-generation tasks.
5. GCS Storage — Persists CDN URLs to Google Cloud Storage.
"""
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import logging
import os

# Both MCP providers (Pollo MCP + PiAPI MCP) deleted 2026-05-26.
#   * Pollo MCP — tool catalog drifted; every img2video_seedance call
#     returned 404. Killed first.
#   * PiAPI MCP — had been disabled in prod via PIAPI_MCP_ENABLED=false
#     for weeks; REST `piapi` was already primary for every task. Kept
#     wasting build time on the npm install + node subprocess for no
#     production benefit. Owner directive (2026-05-26): migrate fully
#     to the REST `piapi` provider, drop the MCP code path.
# Re-enabling would mean restoring app/providers/piapi_mcp_provider.py,
# app/services/mcp_client.py, mcp-servers/piapi-mcp-server/, and the
# Dockerfile build step — see git history for the exact files.
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
    # V2V (video_style_transfer) removed 2026-05-31 — see commit history.
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
    # Sora 2 Pro added 2026-06-09. PiAPI is primary (proxies OpenAI Sora 2 /
    # Sora 2 Pro), Pollo is the I2V backup. Billed at 80 credits via the
    # existing video_sora2 ServicePricing row — mirrors Veo 3.1 in price tier.
    SORA2_VIDEO    = "sora2_video_generation"
    # NOTE: LUMA_VIDEO was removed 2026-05-19. The /tools/luma-video endpoint
    # and its tier-table slot are gone; short-video / kling-video / the new
    # Seedance / Hailuo / Hunyuan / Wan tiers cover every prior use case.


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
    #
    # 2026-05-25 — MCP removal (owner directive):
    #   * piapi_mcp was disabled in prod via PIAPI_MCP_ENABLED=false weeks
    #     ago and was being silently filtered out by _route_candidates on
    #     every request. Leaving it in `primary` just confused the routing
    #     logs without affecting behaviour.
    #   * pollo_mcp's tool catalog is stale — it has only `img2video_pollo-v1-6`
    #     while the frontend now sends `seedance`, `kling_omni`, etc. Every
    #     I2V/T2V request burned 0-300ms tripping over MCP before falling
    #     through to the REST provider.
    #   The fix: REST `piapi` is primary for everything PiAPI covers
    #   (which is most tasks), `pollo` is kept only where it actually works
    #   (Kling I2V via Pollo's image_to_video endpoint), and `vertex_ai`
    #   remains the final fallback for video tasks. MCP provider files
    #   stay on disk so we can re-enable later by editing this config only.
    ROUTING_CONFIG = {
        # 2026-06-23 — owner directive: Pollo.ai is the BACKUP for every task
        # it can serve; Vertex AI is removed from the generation fallback
        # chains entirely (it stays ONLY as the primary for the Gemini
        # moderation / material-generation tasks below). Pollo now implements
        # text_to_image + image_to_image (verified /generation/<vendor>/<slug>/
        # image endpoints) and text_to_video, in addition to its existing
        # image_to_video — see pollo_provider.py + services/pollo_ai.py.
        #
        # Video tasks — PiAPI primary, Pollo backup. The _get_providers_for_task
        # model-aware override below still promotes Pollo to PRIMARY when an
        # explicit Pollo-supported model_id is requested (POLLO_VIDEO_MODEL_IDS).
        TaskType.I2V: {"primary": "piapi", "backup": "pollo", "tertiary": None, "fallback": None},
        TaskType.T2V: {"primary": "piapi", "backup": "pollo", "tertiary": None, "fallback": None},

        # Image tasks — PiAPI primary, Pollo backup.
        # UPSCALE + BACKGROUND_REMOVAL have NO Pollo endpoint, so they run
        # PiAPI-only and surface a clean error on failure rather than routing
        # to a backup that cannot serve them.
        TaskType.T2I:                {"primary": "piapi", "backup": "pollo", "tertiary": None, "fallback": None},
        TaskType.I2I:                {"primary": "piapi", "backup": "pollo", "tertiary": None, "fallback": None},
        TaskType.EFFECTS:            {"primary": "piapi", "backup": "pollo", "tertiary": None, "fallback": None},
        TaskType.UPSCALE:            {"primary": "piapi", "backup": None,    "tertiary": None, "fallback": None},
        TaskType.BACKGROUND_REMOVAL: {"primary": "piapi", "backup": None,    "tertiary": None, "fallback": None},

        # Specialized tasks
        TaskType.INTERIOR:    {"primary": "piapi", "backup": "pollo", "tertiary": None, "fallback": None},
        TaskType.INTERIOR_3D: {"primary": "piapi", "backup": None,        "tertiary": None, "fallback": None},
        # Avatar uses PiAPI first, then A2E.ai for avatar/digital-human fallback.
        TaskType.AVATAR:      {"primary": "piapi", "backup": "a2e",       "tertiary": None, "fallback": None},

        # Vertex AI-only tasks
        TaskType.MODERATION:          {"primary": "vertex_ai", "backup": None, "fallback": None},
        TaskType.MATERIAL_GENERATION: {"primary": "vertex_ai", "backup": None, "fallback": None},

        # Premium tiers — PiAPI REST is the only path. Pollo/Vertex don't expose
        # these models with comparable params, so we deliberately don't list a
        # backup; failure surfaces as a user error rather than silently routing
        # to a cheaper substitute (would defeat the purpose of charging the
        # flagship credit cost).
        TaskType.MIDJOURNEY_T2I: {"primary": "piapi", "backup": None, "tertiary": None, "fallback": None},
        # Kling: PiAPI primary, Pollo fallback for I2V mode (Pollo exposes
        # kling_v1.5/kling_v2 via its image_to_video endpoint). T2V mode lacks
        # an image_url so the Pollo branch soft-fails and the router surfaces
        # the PiAPI error — same UX as before for that path.
        TaskType.KLING_VIDEO:    {"primary": "piapi", "backup": "pollo", "tertiary": None, "fallback": None},
        # Sora 2 Pro: PiAPI primary (sora-2-pro-video task), Pollo backup via
        # /generation/sora/sora-2. Pollo only ingests the I2V path; T2V soft-
        # fails through to the PiAPI error in _execute_pollo, identical to
        # how KLING_VIDEO degrades.
        TaskType.SORA2_VIDEO:    {"primary": "piapi", "backup": "pollo", "tertiary": None, "fallback": None},
    }

    # Models Pollo's REST endpoint actually covers. Trimmed 2026-05-25 to
    # remove entries that were 404ing in prod (the 2026-05-19 batch added
    # `seedance`, `seedance_v2`, `hunyuan`, `hunyuan_v1` speculatively;
    # log audit on 2026-05-25 showed Pollo returning HTTP 404 for every
    # `seedance` attempt and "not implemented" for any T2V mode). Keeping
    # only the IDs whose Pollo endpoint actually returns a video.
    POLLO_VIDEO_MODEL_IDS = {
        "pixverse_v4.5",
        "pixverse_v5",
        "kling_v1.5",
        "kling_v1_5",
        "kling_v2",
        "kling_v3",
        "kling_omni",
        "hailuo",
        "hailuo_fast",
        "minimax",
        # NOTE: "wan", "wan2.6", "kling2.5" were REMOVED 2026-06-23 — Pollo has
        # no endpoint for them, so promoting Pollo to primary only forced a
        # silent Pixverse substitution. They now stay PiAPI-primary (which
        # serves the real Wan/Kling-2.5). _normalize_model also soft-fails any
        # un-mapped slug as a second line of defense.
        "pollo-v1-6",
        # 2026-06-09 — Sora 2 lives at Pollo's /generation/sora/sora-2; an
        # explicit model_id="sora-2" promotes Pollo to PRIMARY when the
        # caller is bypassing the dedicated SORA2_VIDEO task type (e.g. a
        # generic I2V call with model_id chosen on the frontend).
        "sora-2",
        "sora2",
    }

    # Models where the secondary lane is Vertex AI Veo (NOT Pollo). Pollo
    # has no Veo endpoint, so the dual-provider directive ("must have two
    # providers") is satisfied via Vertex's Veo 3 — same model family on a
    # different backend. 2026-06-23 owner directive: re-added Veo to the
    # short-video menu with this PiAPI → Vertex backup chain.
    VERTEX_VIDEO_MODEL_IDS = {
        "veo",
        "veo_31",
        "veo-31",
        "veo_3",
        "veo3",
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
        # MCP providers removed entirely 2026-05-26 — see import block
        # header for the migration story.

        # Vertex AI (replaces old GeminiProvider)
        self.vertex_ai = VertexAIProvider()

        # Legacy REST providers (fallback)
        self.piapi = PiAPIProvider()
        self.pollo = PolloProvider()
        self.a2e = A2EProvider()
        # 2026-05-20: OpenAI / Sora 2 provider removed per owner rule
        # "no provider unless it's in PiAPI or Pollo." Sora is OpenAI-direct
        # so it didn't belong here. Veo 3.1 still ships via Vertex AI; Wan
        # 2.6 covers the niche specialty slot in the SaaS tier table.

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
        # Tracks which TaskTypes we have already warned about for missing
        # user_tier — keeps the migration log from spamming once-per-call.
        self._tier_warn_seen: set = set()

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN ROUTING METHOD
    # ─────────────────────────────────────────────────────────────────────────

    async def route(
        self,
        task_type: TaskType,
        params: Dict[str, Any],
        user_tier: Optional[str] = None,
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

        # Normalize the user_tier string so the gate works regardless of
        # which casing/legacy alias callers send ("starter" ≡ "basic" in
        # tier_config; some callers still send legacy "pro_plus").
        # If the caller didn't pass a tier we default to "pro" (permissive)
        # — the gate was dead code until now, so silently downgrading
        # everyone to "basic" would be a regression. The warning fires at
        # most once per process per task_type so unmigrated service-layer
        # paths don't spam logs.
        if user_tier is None:
            if task_type not in self._tier_warn_seen:
                logger.warning(
                    "provider_router.route called without user_tier for task=%s — "
                    "defaulting to 'pro' (permissive). Pass user_tier so the "
                    "margin gate can enforce premium-model gating.",
                    task_type.value if hasattr(task_type, "value") else task_type,
                )
                self._tier_warn_seen.add(task_type)
            user_tier = "pro"
        user_tier = user_tier.lower()
        if user_tier in ("starter",):
            user_tier = "basic"
        if user_tier in ("pro_plus", "premium", "enterprise", "paid"):
            user_tier = "pro"

        # Apply tier overrides BEFORE provider selection so a downgraded
        # model_type / dropped concrete slug routes to the correct vendor.
        params = self._apply_tier_overrides(task_type, params, user_tier)

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

        if has_explicit_model:
            if task_type in {TaskType.I2V, TaskType.T2V} and model_id in self.VERTEX_VIDEO_MODEL_IDS:
                # Veo: PiAPI primary, Vertex AI Veo as the dual-provider
                # backup. Pollo has no Veo endpoint, so the "must have two
                # providers" rule is satisfied via Vertex's native Veo 3
                # (VEO_MODEL env var, default veo-3.0-fast-generate-001).
                return ["piapi", "vertex_ai"]

            if task_type in {TaskType.I2V, TaskType.T2V} and model_id in self.POLLO_VIDEO_MODEL_IDS:
                # When a model_id IS one Pollo genuinely supports (kling_v1.5 /
                # kling_v2 I2V, pixverse, seedance, hailuo, pollo-v1-6,
                # sora-2), try Pollo first then fall back to PiAPI. Vertex is
                # only in the chain for Veo (see VERTEX_VIDEO_MODEL_IDS above).
                return self._provider_order_with_first(
                    "pollo",
                    ["piapi"],
                )

            if task_type in {
                TaskType.T2I,
                TaskType.I2I,
                TaskType.I2V,
                TaskType.T2V,
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
        if provider == "piapi":
            return not os.getenv("PIAPI_KEY", "")
        if provider == "pollo":
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
        # KLING_VIDEO must be classified as video: without it the Kling growth
        # MP4 was persisted under media_type="image" and, when the Kling CDN
        # returned octet-stream, stored as image/png — the <video> element then
        # silently failed to play and the result appeared blank with no error.
        video_tasks = {TaskType.I2V, TaskType.T2V, TaskType.AVATAR, TaskType.KLING_VIDEO}
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
        """Apply tier-based parameter overrides.

        2026-06 margin pass: this used to be dead code (never invoked from
        route()). Now it runs on every route() call and additionally enforces
        TIER_ALLOWED_MODELS — a free/basic user requesting a premium model
        (Kling 2.1-master, Veo, Nano Banana Pro, …) is silently downgraded to
        the tier's default model rather than triggering a $0.50+ upstream
        call we can't charge for.
        """
        from app.services.tier_config import (
            FREE_TIER, BASIC_TIER, PAID_TIER, TIER_ALLOWED_MODELS,
        )

        if user_tier == "free":
            tier_cfg = FREE_TIER
        elif user_tier == "basic":
            tier_cfg = BASIC_TIER
        else:
            tier_cfg = PAID_TIER

        type_key_map = {
            TaskType.T2I: "t2i",
            TaskType.I2V: "i2v",
            TaskType.T2V: "t2v",
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

        # ── Model whitelist enforcement ──────────────────────────────────
        # `model_type` is the abstract tier we expose in tier_config
        # ("default" / "wan_pro" / "gemini_pro" / "veo" / "midjourney").
        # `model` is the concrete upstream slug ("kling", "veo3.1",
        # "Qubico/flux1-dev-advanced", …). We gate on model_type first; if
        # only a concrete `model` slug is set we map it back to its tier
        # via PREMIUM_MODEL_SLUGS below.
        allowed = set(TIER_ALLOWED_MODELS.get(user_tier, ["default"]))

        requested_tier = params.get("model_type")
        concrete_model = (params.get("model") or "").lower()

        # Concrete-slug → abstract-tier mapping. Anything matching a
        # substring here is a premium upstream that costs ≥$0.40/call.
        PREMIUM_MODEL_SLUGS = {
            "veo": "veo",
            "veo3": "veo",
            "kling-3": "wan_pro",
            "kling_v3": "wan_pro",
            "kling-omni": "wan_pro",
            "2.1-master": "wan_pro",
            "nano-banana-pro": "gemini_pro",
            "midjourney": "midjourney",
            "flux1-dev-advanced": "wan_pro",
        }

        inferred_tier = None
        for slug, tier in PREMIUM_MODEL_SLUGS.items():
            if slug in concrete_model:
                inferred_tier = tier
                break

        effective_tier = requested_tier or inferred_tier
        if effective_tier and effective_tier not in allowed:
            logger.warning(
                "tier_gate: user_tier=%s requested model_type=%s (concrete=%s) "
                "not allowed — downgrading to default",
                user_tier, effective_tier, concrete_model or "<none>",
            )
            params["model_type"] = "default"
            # Drop the concrete model so the provider picks its default upstream
            # (Hailuo/Seedance fast for video, Flux schnell for image).
            params.pop("model", None)

        params["_user_tier"] = user_tier
        return params

    async def _execute_on_provider(
        self,
        provider: str,
        task_type: TaskType,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute task on specific provider."""
        # MCP providers removed entirely 2026-05-26. The dispatch now only
        # touches REST providers + Vertex AI.
        if provider == "vertex_ai":
            return await self._execute_vertex_ai(task_type, params)
        elif provider == "piapi":
            return await self._execute_piapi(task_type, params)
        elif provider == "pollo":
            return await self._execute_pollo(task_type, params)
        elif provider == "a2e":
            return await self._execute_a2e(task_type, params)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    # _execute_piapi_mcp + _execute_pollo_mcp deleted 2026-05-26 along
    # with their provider classes. Video fallback chain is now:
    #   piapi (REST) → vertex_ai → pollo (REST, Kling I2V only).

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
        elif task_type == TaskType.SORA2_VIDEO:
            return await self.piapi.sora2_video_generation(params)
        else:
            raise ValueError(f"PiAPI doesn't support: {task_type}")

    async def _execute_pollo(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute on Pollo REST — image + video backup for PiAPI."""
        if task_type == TaskType.T2I:
            return await self.pollo.text_to_image(params)
        elif task_type in (TaskType.I2I, TaskType.EFFECTS, TaskType.INTERIOR):
            # Image-edit backup. INTERIOR is a styled image-to-image on the
            # room/sketch photo; effects/I2I likewise carry an input image.
            return await self.pollo.image_to_image(params)
        elif task_type == TaskType.I2V:
            return await self.pollo.image_to_video(params)
        elif task_type == TaskType.T2V:
            return await self.pollo.text_to_video(params)
        elif task_type == TaskType.KLING_VIDEO:
            # Pollo as a backup when PiAPI Kling is out of credit or rate-limited.
            # Pollo only exposes Kling via its I2V endpoint, so a true T2V Kling
            # request (no image_url) returns success=false here and the soft-fail
            # path surfaces PiAPI's original error to the user.
            if not (params.get("image_url") or params.get("image")):
                return {
                    "success": False,
                    "error": "Pollo Kling backup requires image_url (T2V Kling not supported by Pollo REST).",
                }
            # Map tier → Pollo Kling slug so the backup matches what the user
            # paid for. "omni" (Kling 3.0 PRO, with audio) → kling_v3;
            # "flagship" → kling_v2; "default" → kling_v1.5. Without the omni
            # branch a 130-credit omni request silently degraded to kling_v1.5
            # (no audio) on the failover path.
            tier = (params.get("tier") or "default").lower()
            pollo_model = {"omni": "kling_v3", "flagship": "kling_v2"}.get(tier, "kling_v1.5")
            pollo_params = {**params, "model": pollo_model}
            return await self.pollo.image_to_video(pollo_params)
        elif task_type == TaskType.SORA2_VIDEO:
            # Pollo backup for Sora 2 — only the I2V path is wired (Pollo's
            # /generation/sora/sora-2 endpoint takes input.image + prompt).
            # T2V Sora 2 requests have no image_url and soft-fail through,
            # which surfaces the original PiAPI error to the caller. Same
            # degradation pattern as KLING_VIDEO above.
            if not (params.get("image_url") or params.get("image")):
                return {
                    "success": False,
                    "error": "Pollo Sora 2 backup requires image_url (T2V Sora 2 not supported by Pollo REST).",
                }
            pollo_params = {**params, "model": "sora-2"}
            return await self.pollo.image_to_video(pollo_params)
        else:
            raise ValueError(f"Pollo doesn't support: {task_type}")

    async def _execute_a2e(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute on A2E (backup for avatar)."""
        if task_type == TaskType.AVATAR:
            return await self.a2e.generate_avatar(params)
        raise ValueError(f"A2E doesn't support: {task_type}")

    # _execute_openai removed 2026-05-20 (OpenAI/Sora 2 not in PiAPI or Pollo).

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
        # PiAPI REST is the only path now — MCP wrapper removed 2026-05-26.
        return await self._check_provider_health("piapi")

    def _get_provider_instance(self, provider: str):
        providers = {
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
        # Credit/balance issues from upstream win over the task-type generic
        # message — without this branch first, INTERIOR_3D / KLING_VIDEO /
        # LUMA_VIDEO failures from PiAPI's account being out of credit got
        # rewritten to the vague "experiencing issues" text below, hiding
        # the actionable reason from the user.
        if "credit" in error.lower() or "balance" in error.lower():
            return "Service credits are currently depleted. Please try again later."
        if "timeout" in error.lower():
            return "The request timed out. Please try again with a simpler prompt."
        # Surface the actionable reason for the two most common image-input
        # failures BEFORE the vague task-type generic below. Sora 2 / Kling
        # reject many uploads at the provider's content filter (real faces,
        # public figures, logos), and providers 403 on images they can't
        # fetch — both were previously masked as "services experiencing issues".
        _el = error.lower()
        if any(k in _el for k in ("moderation", "content policy", "nsfw", "safety", "blocked by")):
            return (
                "This image or prompt was rejected by the model's content policy — "
                "it usually triggers on a real person's face, a public figure, logos, "
                "or otherwise restricted content. Try a different image or rephrase the prompt."
            )
        if ("403" in _el or "forbidden" in _el or ("download" in _el and ("image" in _el or "url" in _el))):
            return (
                "The model couldn't fetch your input image. Please re-upload the image "
                "and try again (external image links sometimes block the provider)."
            )
        video_tasks = {TaskType.I2V, TaskType.T2V, TaskType.KLING_VIDEO, TaskType.SORA2_VIDEO}
        if task_type in video_tasks:
            return "Video generation services are experiencing issues on all providers. Please try again in a few minutes."
        if task_type == TaskType.AVATAR:
            return "Avatar generation services are experiencing issues. Please try again in a few minutes."
        if task_type == TaskType.INTERIOR_3D:
            return "3D model generation is temporarily unavailable. Please try again in a few minutes."
        image_tasks = {TaskType.T2I, TaskType.I2I, TaskType.INTERIOR, TaskType.BACKGROUND_REMOVAL, TaskType.UPSCALE, TaskType.EFFECTS, TaskType.MIDJOURNEY_T2I}
        if task_type in image_tasks:
            return "Image generation services are experiencing issues. Please try again in a few minutes."
        return "Our service is currently experiencing technical difficulties. Please wait a moment and try again!"

    # ─────────────────────────────────────────────────────────────────────────
    # STATUS REPORTING
    # ─────────────────────────────────────────────────────────────────────────

    async def get_all_status(self) -> Dict[str, Any]:
        status = {}
        for provider in ["vertex_ai", "piapi", "pollo", "a2e"]:
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
            ("vertex_ai", self.vertex_ai),
            ("piapi", self.piapi),
            ("pollo", self.pollo),
            ("a2e", self.a2e),
        ]
        # MCP provider entries removed 2026-05-26 — both Pollo MCP and
        # PiAPI MCP deleted in favor of their REST counterparts.
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
            tier = params.get("tier") or "default"
            version = params.get("version") or (
                "3.0" if tier == "omni" else "2.1-master" if tier == "flagship" else "2.6"
            )
            return f"kling-{version}"
        if task_type == TaskType.INTERIOR_3D:
            return f"trellis-{params.get('model_version') or 'v1'}"
        if task_type in (TaskType.I2V, TaskType.T2V):
            # Tier-revision default is Seedance 2.0 Fast; piapi_provider's
            # _resolve_video_model() maps params["model"] to the family.
            model = (params.get("model") or "").lower()
            if "hailuo" in model or "minimax" in model:
                return "hailuo-fast"
            if "hunyuan" in model:
                return "hunyuan"
            if model.startswith("wan"):
                return "wan-2.6"
            return "seedance-2-fast"
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
            cohort = params.get("_cohort")    # populated by an experiment runner; NULL when no experiment active

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
                        cohort=cohort,
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
