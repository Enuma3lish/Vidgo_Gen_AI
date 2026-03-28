"""
Provider Router - Routes AI tasks to the correct provider.

Architecture:
1. PiAPI — Primary provider for ALL generation tasks
2. Gemini — Backup provider for image tasks when PiAPI has no credits
   - Supports: T2I, I2I, Interior, Background Removal, Upscale
3. Pollo — Backup provider for video tasks when PiAPI fails
   - Supports: I2V, T2V, V2V (via effects method)
4. A2E — Backup provider for avatar tasks when PiAPI fails
   - Supports: Avatar generation with lip sync
5. When PiAPI fails, the appropriate backup is used for compatible tasks
"""
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import logging

from app.providers.piapi_provider import PiAPIProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.pollo_provider import PolloProvider
from app.providers.a2e_provider import A2EProvider

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
    # Gemini-only tasks
    MATERIAL_GENERATION = "material_generation"


class ProviderStatus(str, Enum):
    """Provider health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class ProviderRouter:
    """
    Routes AI tasks to the correct provider.

    PiAPI is primary for all tasks. Gemini is backup for image tasks.
    Pollo is backup for video tasks (I2V, T2V, V2V).
    A2E is backup for avatar tasks. INTERIOR_3D has no backup.
    """

    # Routing configuration with Gemini as backup for image tasks
    ROUTING_CONFIG = {
        # Image tasks with Gemini backup
        TaskType.T2I:                {"primary": "piapi", "backup": "gemini", "model": "flux1-schnell"},
        TaskType.I2I:                {"primary": "piapi", "backup": "gemini", "model": "flux1-schnell"},
        TaskType.INTERIOR:           {"primary": "piapi", "backup": "gemini", "model": "wan2.1-doodle"},
        TaskType.BACKGROUND_REMOVAL: {"primary": "piapi", "backup": "gemini"},
        TaskType.UPSCALE:            {"primary": "piapi", "backup": "gemini"},
        TaskType.EFFECTS:            {"primary": "piapi", "backup": "gemini", "model": "flux1-schnell"},
        
        # Video tasks - Pollo backup
        TaskType.I2V:                {"primary": "piapi", "backup": "pollo", "model": "wan2.6-i2v"},
        TaskType.T2V:                {"primary": "piapi", "backup": "pollo", "model": "wan2.6-t2v"},
        TaskType.V2V:                {"primary": "piapi", "backup": "pollo", "model": "wan2.1-vace"},
        # Avatar - A2E backup
        TaskType.AVATAR:             {"primary": "piapi", "backup": "a2e"},
        TaskType.INTERIOR_3D:        {"primary": "piapi", "backup": None},
        
        # Gemini-only tasks
        TaskType.MODERATION:         {"primary": "gemini", "backup": None},
        TaskType.MATERIAL_GENERATION:{"primary": "gemini", "backup": None},
    }

    def __init__(self):
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
        user_tier: str = "starter"
    ) -> Dict[str, Any]:
        """
        Route request to the appropriate provider.
        Tries primary provider first, falls back to backup if available.
        """
        config = self.ROUTING_CONFIG.get(task_type)
        if not config:
            raise ValueError(f"Unknown task type: {task_type}")

        primary_provider = config["primary"]
        backup_provider = config.get("backup")

        # Try primary provider first
        try:
            result = await self._execute_on_provider(
                primary_provider, task_type, params
            )
            self._record_success(primary_provider)
            return {
                **result,
                "used_backup": False,
                "primary_provider": primary_provider
            }
        except Exception as e:
            logger.error(f"Primary provider {primary_provider} failed for {task_type}: {e}")
            self._record_failure(primary_provider, str(e))
            
            # Try backup provider if available
            if backup_provider:
                try:
                    logger.info(f"Trying backup provider {backup_provider} for {task_type}")
                    result = await self._execute_on_provider(
                        backup_provider, task_type, params
                    )
                    self._record_success(backup_provider)
                    return {
                        **result,
                        "used_backup": True,
                        "backup_provider": backup_provider,
                        "primary_failed": True
                    }
                except Exception as backup_error:
                    logger.error(f"Backup provider {backup_provider} also failed for {task_type}: {backup_error}")
                    self._record_failure(backup_provider, str(backup_error))
            
            # No backup available or backup also failed
            error_msg = self._get_user_friendly_error(task_type, primary_provider, backup_provider, str(e))
            raise Exception(error_msg)

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
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute task on specific provider."""
        if provider == "piapi":
            return await self._execute_piapi(task_type, params)
        elif provider == "gemini":
            return await self._execute_gemini(task_type, params)
        elif provider == "pollo":
            return await self._execute_pollo(task_type, params)
        elif provider == "a2e":
            return await self._execute_a2e(task_type, params)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _execute_piapi(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute task on PiAPI — handles ALL generation."""
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
        """Execute task on Gemini — supports image tasks as backup."""
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
            # Effects is similar to image-to-image
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
        """Execute task on Pollo — backup for video tasks."""
        if task_type == TaskType.I2V:
            return await self.pollo.image_to_video(params)
        elif task_type == TaskType.T2V:
            return await self.pollo.text_to_video(params)
        elif task_type == TaskType.V2V:
            # Pollo has no dedicated video_style_transfer method.
            # Use effects() as best-effort approximation.
            if params.get("video_url"):
                return await self.pollo.effects(params)
            else:
                return await self.pollo.multi_model(params)
        else:
            raise ValueError(f"Pollo doesn't support: {task_type}")

    async def _execute_a2e(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute task on A2E — backup for avatar tasks."""
        if task_type == TaskType.AVATAR:
            return await self.a2e.generate_avatar(params)
        else:
            raise ValueError(f"A2E doesn't support: {task_type}")

    # ─────────────────────────────────────────────────────────────────────────
    # HEALTH CHECKING
    # ─────────────────────────────────────────────────────────────────────────

    async def _check_provider_health(self, provider: str) -> bool:
        """Check if provider is healthy (with caching)."""
        if provider in self._last_health_check:
            if datetime.now() - self._last_health_check[provider] < timedelta(seconds=60):
                cached = self._status_cache.get(provider, {})
                return cached.get("status") == ProviderStatus.HEALTHY

        try:
            provider_instance = self._get_provider_instance(provider)
            is_healthy = await provider_instance.health_check()

            self._status_cache[provider] = {
                "status": ProviderStatus.HEALTHY if is_healthy else ProviderStatus.DOWN,
                "last_check": datetime.now()
            }
            self._last_health_check[provider] = datetime.now()
            return is_healthy
        except Exception as e:
            logger.error(f"Health check failed for {provider}: {e}")
            self._status_cache[provider] = {
                "status": ProviderStatus.DOWN,
                "error": str(e),
                "last_check": datetime.now()
            }
            return False

    async def is_piapi_healthy(self) -> bool:
        """Check if PiAPI is available. If not, service should be unavailable."""
        return await self._check_provider_health("piapi")

    def _get_provider_instance(self, provider: str):
        """Get provider instance by name."""
        providers = {
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
            "last_success": datetime.now()
        }

    def _record_failure(self, provider: str, error: str):
        count = self._failure_counts.get(provider, 0) + 1
        self._failure_counts[provider] = count
        if count >= 3:
            self._status_cache[provider] = {
                "status": ProviderStatus.DOWN,
                "error": error,
                "failure_count": count,
                "last_failure": datetime.now()
            }

    def _get_user_friendly_error(
        self, 
        task_type: TaskType, 
        primary_provider: str, 
        backup_provider: Optional[str], 
        error: str
    ) -> str:
        """
        Generate user-friendly error messages based on task type and available backups.
        """
        # Check if it's a video task
        video_tasks = {TaskType.I2V, TaskType.T2V, TaskType.V2V}

        if task_type in video_tasks:
            if backup_provider:
                return "Video generation services are experiencing issues on all providers. Please try again in a few minutes."
            return "Video generation services are temporarily unavailable. Please try again later or contact support."

        if task_type == TaskType.AVATAR:
            if backup_provider:
                return "Avatar generation services are experiencing issues on all providers. Please try again in a few minutes."
            return "Avatar generation service is temporarily unavailable. Please try again later or contact support."
        
        # Check if it's an image task with Gemini backup
        image_tasks_with_backup = {
            TaskType.T2I, TaskType.I2I, TaskType.INTERIOR, 
            TaskType.BACKGROUND_REMOVAL, TaskType.UPSCALE, TaskType.EFFECTS
        }
        
        if task_type in image_tasks_with_backup and backup_provider:
            # Both primary and backup failed
            return "Image generation services are experiencing issues. Please try again in a few minutes."
        elif task_type in image_tasks_with_backup and not backup_provider:
            # Image task but no backup configured
            return "Image generation service is temporarily unavailable. Please try again later."
        
        # Default error message
        if "credit" in error.lower() or "balance" in error.lower() or "payment" in error.lower():
            return "Service credits are currently depleted. Please try again later or contact support to add credits."
        elif "timeout" in error.lower():
            return "The request timed out. Please try again with a simpler prompt or smaller image."
        elif "connection" in error.lower() or "network" in error.lower():
            return "Network connection issue. Please check your internet connection and try again."
        else:
            return "Our service is currently experiencing technical difficulties. Please wait a moment and try again!"

    # ─────────────────────────────────────────────────────────────────────────
    # STATUS REPORTING
    # ─────────────────────────────────────────────────────────────────────────

    async def get_all_status(self) -> Dict[str, Any]:
        """Get status of all providers."""
        status = {}
        for provider in ["piapi", "gemini", "pollo", "a2e"]:
            await self._check_provider_health(provider)
            cached = self._status_cache.get(provider, {})
            status[provider] = {
                "status": cached.get("status", ProviderStatus.DOWN).value if isinstance(cached.get("status"), ProviderStatus) else cached.get("status", "unknown"),
                "last_check": cached.get("last_check", datetime.now()).isoformat() if cached.get("last_check") else None,
                "failure_count": self._failure_counts.get(provider, 0)
            }
        return status

    async def check_service_status(self) -> Dict[str, Any]:
        """Check status of all services (for admin dashboard)."""
        status = {}
        for name, provider in [("piapi", self.piapi), ("gemini", self.gemini), ("pollo", self.pollo), ("a2e", self.a2e)]:
            try:
                is_healthy = await provider.health_check()
                status[name] = {
                    "status": "ok" if is_healthy else "error",
                    "message": f"{name} is operational" if is_healthy else f"{name} is not responding"
                }
            except Exception as e:
                status[name] = {"status": "error", "error": str(e)}
        return status

    async def close(self):
        """Close all provider connections."""
        await asyncio.gather(
            self.piapi.close(),
            self.gemini.close(),
            self.pollo.close(),
            self.a2e.close(),
        )


# Global router instance
_router_instance: Optional[ProviderRouter] = None


def get_provider_router() -> ProviderRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = ProviderRouter()
    return _router_instance
