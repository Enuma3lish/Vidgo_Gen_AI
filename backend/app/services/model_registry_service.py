"""DB-first model registry resolver with Redis cache + env + hardcoded fallback.

Lookup order for any service_key:

    1. DB row in ``model_registry_overrides``     (admin-editable, primary)
    2. Environment variable                         (emergency hotfix)
    3. Hardcoded default in app.core.model_registry (safety net)

Reads are cached in Redis for 60 seconds so admin edits propagate to all
worker instances within one cache cycle without requiring a Cloud Run
restart. Writes invalidate the cache eagerly.

Used by:
- provider_router._execute_piapi etc. (via app.core.model_registry.get())
- /api/admin/models endpoints
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import model_registry as static_registry
from app.models.model_registry import ModelRegistryOverride, ModelRegistryAudit

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60
CACHE_KEY_PREFIX = "model_registry:"

# Mapping from registry key → the env var name used by the static defaults.
# Keeps the env-fallback layer in sync with the keys we expose. New keys
# should be appended here; missing entries simply skip the env lookup.
KEY_TO_ENV_VAR: Dict[str, str] = {
    "kling_video":         "PIAPI_KLING_VIDEO_MODEL",
    "kling_video_effects": "PIAPI_KLING_EFFECTS_MODEL",
    "kling_try_on":        "PIAPI_KLING_TRYON_MODEL",
    "kling_avatar":        "PIAPI_KLING_AVATAR_MODEL",
    "kling_lip_sync":      "PIAPI_KLING_LIPSYNC_MODEL",
    "trellis_v1":          "PIAPI_TRELLIS_V1_MODEL",
    "trellis_v2":          "PIAPI_TRELLIS_V2_MODEL",
    "flux_t2i":            "PIAPI_FLUX_T2I_MODEL",
    "flux_i2i":            "PIAPI_FLUX_I2I_MODEL",
    "flux_kontext":        "PIAPI_FLUX_KONTEXT_MODEL",
    "wan_video":           "PIAPI_WAN_VIDEO_MODEL",
    "wan_i2v_task":        "PIAPI_WAN_I2V_TASK",
    "wan_t2v_task":        "PIAPI_WAN_T2V_TASK",
    "image_toolkit":       "PIAPI_IMAGE_TOOLKIT_MODEL",
    "tts_f5":              "PIAPI_TTS_F5_MODEL",
    "tts_openai":          "PIAPI_TTS_OPENAI_MODEL",
    "midjourney":          "PIAPI_MIDJOURNEY_MODEL",
    "luma_video":          "PIAPI_LUMA_VIDEO_MODEL",
    "luma_ray_version":    "PIAPI_LUMA_RAY_VERSION",
    # Kling video version pin (separate from model field which is always "kling")
    "kling_video_version":  "PIAPI_KLING_VIDEO_VERSION",
    "kling_flagship_version": "PIAPI_KLING_VIDEO_FLAGSHIP_VERSION",
}


class ModelRegistryService:
    """DB-first resolver with Redis cache.

    Synchronous static fallback is always available via ``static_registry``;
    the async ``resolve`` adds DB + cache + env layers on top.
    """

    def __init__(self, db: AsyncSession, redis_client: Optional[redis.Redis] = None):
        self.db = db
        self.redis = redis_client

    # ─── public read ─────────────────────────────────────────────────────

    async def resolve(self, service_key: str) -> Dict[str, Optional[str]]:
        """Return {"model": str, "version": Optional[str], "source": str}.

        ``source`` is one of "db", "env", "default", "missing" so callers can
        log which layer served the lookup. Used by /admin/models to display
        the current effective state next to the configured override.
        """
        # 1. cache
        if self.redis:
            cached = await self._cache_get(service_key)
            if cached is not None:
                return cached

        # 2. DB
        row = await self._fetch_db(service_key)
        if row is not None:
            result = {
                "model": row.current_model,
                "version": row.current_version,
                "source": "db",
            }
            await self._cache_set(service_key, result)
            return result

        # 3. env
        env_var = KEY_TO_ENV_VAR.get(service_key)
        env_val = os.environ.get(env_var) if env_var else None
        if env_val:
            result = {"model": env_val, "version": None, "source": "env"}
            await self._cache_set(service_key, result)
            return result

        # 4. hardcoded default
        default = static_registry.PIAPI_MODELS.get(service_key)
        if default is not None:
            version = None
            if service_key == "kling_video_version":
                version = static_registry.PIAPI_KLING_VERSIONS.get("default")
            result = {"model": default, "version": version, "source": "default"}
            await self._cache_set(service_key, result)
            return result

        return {"model": "", "version": None, "source": "missing"}

    async def list_all(self) -> Dict[str, Dict[str, Any]]:
        """Return every known service_key with its effective state + override row.

        Effective state is the resolved {model, version, source} as a normal
        ``resolve()`` would return; ``override`` is the raw DB row (or None).
        Powers the admin model list endpoint.
        """
        # All known keys come from the static registry + any DB rows that
        # happen to reference keys not yet in the static table (defensive).
        known_keys = set(static_registry.PIAPI_MODELS.keys())
        known_keys.add("kling_video_version")
        known_keys.add("kling_flagship_version")

        db_rows: Dict[str, ModelRegistryOverride] = {}
        result = await self.db.execute(select(ModelRegistryOverride))
        for row in result.scalars().all():
            db_rows[row.service_key] = row
            known_keys.add(row.service_key)

        out: Dict[str, Dict[str, Any]] = {}
        for key in sorted(known_keys):
            effective = await self.resolve(key)
            override = db_rows.get(key)
            out[key] = {
                "effective": effective,
                "override": (
                    {
                        "model": override.current_model,
                        "version": override.current_version,
                        "updated_by": str(override.updated_by) if override.updated_by else None,
                        "updated_at": override.updated_at.isoformat() if override.updated_at else None,
                        "notes": override.notes,
                    }
                    if override
                    else None
                ),
                "default": {
                    "model": static_registry.PIAPI_MODELS.get(key, ""),
                    "version": (
                        static_registry.PIAPI_KLING_VERSIONS.get("default")
                        if key == "kling_video_version"
                        else None
                    ),
                },
                "env_var": KEY_TO_ENV_VAR.get(key),
            }
        return out

    # ─── public write ────────────────────────────────────────────────────

    async def set_override(
        self,
        service_key: str,
        model: str,
        version: Optional[str],
        changed_by: Optional[str],
        reason: Optional[str] = None,
    ) -> ModelRegistryOverride:
        """Upsert override + write audit row + invalidate cache.

        ``changed_by`` is the admin user UUID (string); audit log keeps full
        before/after so we can prove who flipped what at when.
        """
        # Capture before state for audit
        before = await self._fetch_db(service_key)
        before_model = before.current_model if before else None
        before_version = before.current_version if before else None

        if before is None:
            override = ModelRegistryOverride(
                service_key=service_key,
                current_model=model,
                current_version=version,
                updated_by=changed_by,
                notes=reason,
            )
            self.db.add(override)
        else:
            before.current_model = model
            before.current_version = version
            before.updated_by = changed_by
            before.notes = reason
            override = before

        audit = ModelRegistryAudit(
            service_key=service_key,
            before_model=before_model,
            before_version=before_version,
            after_model=model,
            after_version=version,
            changed_by=changed_by,
            reason=reason,
        )
        self.db.add(audit)

        await self.db.commit()
        await self._cache_invalidate(service_key)

        # Publish cross-instance invalidate so other Cloud Run instances
        # refresh their in-process PIAPI_MODELS dict. Best-effort —
        # admin's write succeeded regardless of publish outcome.
        try:
            from app.services.model_registry_pubsub import publish_invalidate
            await publish_invalidate(self.redis, service_key, model, version)
        except Exception as exc:  # pragma: no cover
            logger.warning("model_registry: publish_invalidate failed for %s: %s", service_key, exc)

        logger.info(
            "model_registry override: key=%s %s/%s -> %s/%s by=%s reason=%s",
            service_key, before_model, before_version, model, version, changed_by, reason,
        )
        return override

    async def get_audit(self, service_key: str, limit: int = 50):
        """Return audit rows for one key, most recent first."""
        result = await self.db.execute(
            select(ModelRegistryAudit)
            .where(ModelRegistryAudit.service_key == service_key)
            .order_by(ModelRegistryAudit.changed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ─── internals ───────────────────────────────────────────────────────

    async def _fetch_db(self, service_key: str) -> Optional[ModelRegistryOverride]:
        result = await self.db.execute(
            select(ModelRegistryOverride).where(
                ModelRegistryOverride.service_key == service_key
            )
        )
        return result.scalar_one_or_none()

    def _cache_key(self, service_key: str) -> str:
        return f"{CACHE_KEY_PREFIX}{service_key}"

    async def _cache_get(self, service_key: str) -> Optional[Dict[str, Any]]:
        if not self.redis:
            return None
        try:
            raw = await self.redis.get(self._cache_key(service_key))
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.warning("model_registry cache_get failed for %s: %s", service_key, exc)
        return None

    async def _cache_set(self, service_key: str, value: Dict[str, Any]) -> None:
        if not self.redis:
            return
        try:
            await self.redis.set(
                self._cache_key(service_key),
                json.dumps(value),
                ex=CACHE_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning("model_registry cache_set failed for %s: %s", service_key, exc)

    async def _cache_invalidate(self, service_key: str) -> None:
        if not self.redis:
            return
        try:
            await self.redis.delete(self._cache_key(service_key))
        except Exception as exc:
            logger.warning("model_registry cache_invalidate failed for %s: %s", service_key, exc)
