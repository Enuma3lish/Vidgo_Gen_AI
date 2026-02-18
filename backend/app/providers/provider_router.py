"""
Provider Router - Smart routing between AI providers with automatic failover.

Priority:
1. PiAPI (Wan) - Primary for T2I, I2V, T2V, V2V, Interior, Background Removal
2. Pollo.ai - Backup + Advanced features (Keyframes, Effects, Multi-model)
3. A2E.ai - Avatar (no backup)
4. Gemini - Moderation + Emergency backup for Interior
"""
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import logging

from app.providers.piapi_provider import PiAPIProvider
from app.providers.pollo_provider import PolloProvider
from app.providers.a2e_provider import A2EProvider
from app.providers.gemini_provider import GeminiProvider

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
    KEYFRAMES = "keyframes"
    EFFECTS = "effects"
    MULTI_MODEL = "multi_model"
    MODERATION = "moderation"
    BACKGROUND_REMOVAL = "background_removal"


class ProviderStatus(str, Enum):
    """Provider health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class ProviderRouter:
    """
    Smart routing between AI providers with automatic failover.

    Routing Configuration:
    - T2I: PiAPI (primary) -> Pollo (backup)
    - I2V: PiAPI (primary) -> Pollo (backup)
    - T2V: PiAPI (primary) -> Pollo (backup)
    - V2V: PiAPI Wan VACE (primary) -> Pollo (backup)
    - Interior: PiAPI (primary) -> Gemini (emergency backup)
    - Avatar: A2E.ai (no backup)
    - Background Removal: PiAPI (primary)
    - Keyframes/Effects/MultiModel: Pollo only
    - Moderation: Gemini only
    """

    ROUTING_CONFIG = {
        TaskType.T2I: {
            "primary": "piapi",
            "backup": "pollo",
            "model": "flux1-schnell"
        },
        TaskType.I2V: {
            "primary": "piapi",
            "backup": "pollo",
            "model": "wan2.6-i2v"
        },
        TaskType.T2V: {
            "primary": "piapi",
            "backup": "pollo",
            "model": "wan2.6-t2v"
        },
        TaskType.V2V: {
            "primary": "piapi",
            "backup": "pollo",
            "model": "wan2.1-vace"
        },
        TaskType.INTERIOR: {
            "primary": "piapi",
            "backup": "gemini",
            "model": "wan2.1-doodle"
        },
        TaskType.AVATAR: {
            "primary": "a2e",
            "backup": None,
        },
        TaskType.UPSCALE: {
            "primary": "piapi",
            "backup": None,
        },
        TaskType.KEYFRAMES: {
            "primary": "pollo",
            "backup": None,
        },
        TaskType.EFFECTS: {
            "primary": "pollo",
            "backup": None,
        },
        TaskType.MULTI_MODEL: {
            "primary": "pollo",
            "backup": None,
        },
        TaskType.MODERATION: {
            "primary": "gemini",
            "backup": None,
        },
        TaskType.BACKGROUND_REMOVAL: {
            "primary": "piapi",
            "backup": None,
        },
    }

    def __init__(self):
        # Initialize providers
        self.piapi = PiAPIProvider()
        self.pollo = PolloProvider()
        self.a2e = A2EProvider()
        self.gemini = GeminiProvider()

        # Provider status cache
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
        Route request to appropriate provider with automatic failover.

        Args:
            task_type: Type of task to perform
            params: Task parameters
            user_tier: User subscription tier (starter, pro, pro_plus)

        Returns:
            Provider response with output
        """
        config = self.ROUTING_CONFIG.get(task_type)
        if not config:
            raise ValueError(f"Unknown task type: {task_type}")

        # Check primary provider health
        primary_provider = config["primary"]
        primary_healthy = await self._check_provider_health(primary_provider)

        if primary_healthy:
            try:
                result = await self._execute_on_provider(
                    primary_provider, task_type, params
                )
                self._record_success(primary_provider)
                return result
            except Exception as e:
                logger.error(f"Primary provider {primary_provider} failed: {e}")
                self._record_failure(primary_provider, str(e))

        # Try backup if available
        backup_provider = config.get("backup")
        if backup_provider:
            logger.info(f"Attempting backup provider: {backup_provider}")
            backup_healthy = await self._check_provider_health(backup_provider)

            if backup_healthy:
                try:
                    result = await self._execute_on_provider(
                        backup_provider, task_type, params
                    )
                    self._record_success(backup_provider)
                    result["used_backup"] = True
                    result["backup_provider"] = backup_provider
                    return result
                except Exception as e:
                    logger.error(f"Backup provider {backup_provider} failed: {e}")
                    self._record_failure(backup_provider, str(e))

        # All providers failed
        raise Exception(f"All providers failed for task: {task_type}")

    # ─────────────────────────────────────────────────────────────────────────
    # PROVIDER EXECUTION
    # ─────────────────────────────────────────────────────────────────────────

    async def _execute_on_provider(
        self,
        provider: str,
        task_type: TaskType,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute task on specific provider."""

        if provider == "piapi":
            return await self._execute_piapi(task_type, params)
        elif provider == "pollo":
            return await self._execute_pollo(task_type, params)
        elif provider == "a2e":
            return await self.a2e.generate_avatar(params)
        elif provider == "gemini":
            return await self._execute_gemini(task_type, params)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _execute_piapi(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute task on PiAPI (Wan)."""

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
        else:
            raise ValueError(f"PiAPI doesn't support: {task_type}")

    async def _execute_pollo(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute task on Pollo.ai (Backup + Advanced)."""

        if task_type in [TaskType.T2I, TaskType.I2V, TaskType.T2V]:
            return await self.pollo.generate(task_type.value, params)
        elif task_type == TaskType.KEYFRAMES:
            return await self.pollo.keyframes(params)
        elif task_type == TaskType.EFFECTS:
            return await self.pollo.effects(params)
        elif task_type == TaskType.MULTI_MODEL:
            return await self.pollo.multi_model(params)
        else:
            raise ValueError(f"Pollo doesn't support: {task_type}")

    async def _execute_gemini(
        self, task_type: TaskType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute task on Gemini (Emergency backup + Moderation)."""

        if task_type == TaskType.INTERIOR:
            return await self.gemini.interior_design(params)
        elif task_type == TaskType.MODERATION:
            return await self.gemini.moderate_content(params)
        else:
            raise ValueError(f"Gemini doesn't support: {task_type}")

    # ─────────────────────────────────────────────────────────────────────────
    # HEALTH CHECKING
    # ─────────────────────────────────────────────────────────────────────────

    async def _check_provider_health(self, provider: str) -> bool:
        """Check if provider is healthy (with caching)."""

        # Check cache first (valid for 60 seconds)
        if provider in self._last_health_check:
            if datetime.now() - self._last_health_check[provider] < timedelta(seconds=60):
                cached = self._status_cache.get(provider, {})
                return cached.get("status") == ProviderStatus.HEALTHY

        # Perform health check
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

    def _get_provider_instance(self, provider: str):
        """Get provider instance by name."""
        providers = {
            "piapi": self.piapi,
            "pollo": self.pollo,
            "a2e": self.a2e,
            "gemini": self.gemini
        }
        return providers.get(provider)

    # ─────────────────────────────────────────────────────────────────────────
    # METRICS
    # ─────────────────────────────────────────────────────────────────────────

    def _record_success(self, provider: str):
        """Record successful API call."""
        self._failure_counts[provider] = 0
        self._status_cache[provider] = {
            "status": ProviderStatus.HEALTHY,
            "last_success": datetime.now()
        }

    def _record_failure(self, provider: str, error: str):
        """Record failed API call."""
        count = self._failure_counts.get(provider, 0) + 1
        self._failure_counts[provider] = count

        # Mark as down if too many failures
        if count >= 3:
            self._status_cache[provider] = {
                "status": ProviderStatus.DOWN,
                "error": error,
                "failure_count": count,
                "last_failure": datetime.now()
            }

    # ─────────────────────────────────────────────────────────────────────────
    # STATUS REPORTING
    # ─────────────────────────────────────────────────────────────────────────

    async def get_all_status(self) -> Dict[str, Any]:
        """Get status of all providers."""
        providers = ["piapi", "pollo", "a2e", "gemini"]
        status = {}

        for provider in providers:
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

        # Check each provider
        for name, provider in [
            ("piapi", self.piapi),
            ("pollo", self.pollo),
            ("a2e", self.a2e),
            ("gemini", self.gemini)
        ]:
            try:
                is_healthy = await provider.health_check()
                status[name] = {
                    "status": "ok" if is_healthy else "error",
                    "message": f"{name} is operational" if is_healthy else f"{name} is not responding"
                }
            except Exception as e:
                status[name] = {
                    "status": "error",
                    "error": str(e)
                }

        return status

    async def close(self):
        """Close all provider connections."""
        await asyncio.gather(
            self.piapi.close(),
            self.pollo.close(),
            self.a2e.close(),
            self.gemini.close()
        )


# Global router instance
_router_instance: Optional[ProviderRouter] = None


def get_provider_router() -> ProviderRouter:
    """Get or create global provider router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ProviderRouter()
    return _router_instance
