import asyncio
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.core.config import get_settings
from app.api.api import api_router

settings = get_settings()
logger = logging.getLogger(__name__)


# ── Media Cleanup Background Task ─────────────────────────────────────────────
async def _media_cleanup_loop():
    """後台任務：每小時執行一次媒體清理，清除超過14天的媒體 URL。"""
    from app.core.database import AsyncSessionLocal
    from app.services.media_cleanup_service import run_media_cleanup
    while True:
        try:
            await asyncio.sleep(3600)
            async with AsyncSessionLocal() as db:
                result = await run_media_cleanup(db)
                if result['expired_count'] > 0:
                    logger.info(f"[MediaCleanup] Expired {result['expired_count']} generation(s)")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[MediaCleanup] Error during cleanup: {e}")


# Ensure static directory exists. Default to the container path but allow a
# STATIC_DIR env override, and fall back to a writable temp dir when the
# configured path can't be created — importing this module (e.g. under pytest
# or in CI, where `/app` is read-only or absent) must never crash, and the
# StaticFiles mount below needs the directory to exist.
_STATIC_SUBDIRS = ("generated", "generated/interior", "materials", "uploads", "tryon_garments")


def _prepare_static_dir() -> Path:
    base = Path(os.getenv("STATIC_DIR", "/app/static"))
    try:
        base.mkdir(parents=True, exist_ok=True)
        for sub in _STATIC_SUBDIRS:
            (base / sub).mkdir(parents=True, exist_ok=True)
        return base
    except OSError as exc:
        fallback = Path(tempfile.gettempdir()) / "vidgo-static"
        logger.warning("STATIC_DIR %s not writable (%s); falling back to %s", base, exc, fallback)
        for sub in ("",) + _STATIC_SUBDIRS:
            (fallback / sub).mkdir(parents=True, exist_ok=True)
        return fallback


STATIC_DIR = _prepare_static_dir()


async def validate_materials_on_startup() -> dict:
    """
    BLOCKING VALIDATION: Check if all required preset materials exist in Material DB.

    PRESET-ONLY MODE requires all materials to be pre-generated before service starts.
    If materials are missing, the service will NOT accept requests until they are ready.

    Returns:
        dict: Validation result with 'all_ready' flag and details
    """
    try:
        from app.services.material_generator import get_material_generator
        from app.core.database import AsyncSessionLocal

        logger.info("=" * 60)
        logger.info("BLOCKING STARTUP: VALIDATING PRE-GENERATED MATERIALS")
        logger.info("=" * 60)

        generator = get_material_generator()
        async with AsyncSessionLocal() as session:
            status = await generator.check_all_materials(session)

        # Count missing materials
        missing = []
        for tool, info in status.items():
            if isinstance(info, dict) and not info.get('ready', False):
                missing_topics = info.get("missing_topics", [])
                prompt_issues = info.get("prompt_issues", {})
                prompt_missing = prompt_issues.get("missing_prompt", 0)
                prompt_zh_missing = prompt_issues.get("missing_prompt_zh", 0)
                missing.append(
                    f"{tool}: missing_topics={missing_topics} prompt_missing={prompt_missing} prompt_zh_missing={prompt_zh_missing}"
                )
            elif info is False:
                missing.append(f"{tool}: not ready")

        all_ready = len(missing) == 0

        if all_ready:
            logger.info("ALL MATERIALS VALIDATED - Service ready to accept requests")
        else:
            logger.warning(f"MISSING MATERIALS: {missing}")
            logger.warning("Service will start but materials may be incomplete")

        logger.info("=" * 60)

        return {
            'all_ready': all_ready,
            'missing': missing,
            'status': status
        }

    except Exception as e:
        logger.error(f"Error during material validation: {e}")
        # Return validation failed but don't crash startup
        return {
            'all_ready': False,
            'error': str(e),
            'missing': ['validation_failed']
        }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup/shutdown events.

    PRESET-ONLY MODE: Uses BLOCKING validation to ensure all materials
    are ready before accepting requests.
    """
    # Startup — must be fast so Cloud Run health check passes
    logger.info("VidGo AI Backend starting up...")

    # NON-BLOCKING: validate materials in background (don't block server start)
    app.state.materials_validated = False
    app.state.materials_status = {}

    async def _background_init():
        """Run DB-dependent init tasks after server is already listening."""
        await asyncio.sleep(5)  # let server fully start first
        try:
            result = await asyncio.wait_for(validate_materials_on_startup(), timeout=30)
            app.state.materials_validated = result.get('all_ready', False)
            app.state.materials_status = result
            if not result.get('all_ready', False):
                logger.warning("Some materials may be missing — generate via admin endpoint")
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Material validation failed (non-fatal): {e}")

        try:
            from app.core.database import AsyncSessionLocal
            from app.services.media_cleanup_service import run_media_cleanup
            async with AsyncSessionLocal() as db:
                cleanup = await run_media_cleanup(db)
                logger.info(f"[MediaCleanup] Startup cleanup: {cleanup['expired_count']} expired")
        except Exception as e:
            logger.warning(f"[MediaCleanup] Startup cleanup failed (non-fatal): {e}")

    asyncio.create_task(_background_init())

    # MCP startup removed 2026-05-26 — both Pollo MCP and PiAPI MCP
    # providers were deleted in favor of their REST equivalents. No
    # subprocess to launch, no MCP manager to manage.

    # Start hourly background tasks
    cleanup_task = asyncio.create_task(_media_cleanup_loop())
    logger.info("[Background] Hourly media cleanup task started")

    # Model-registry live cache subscriber. Listens on a Redis channel for
    # admin overrides published by ModelRegistryService.set_override and
    # refreshes the in-process PIAPI_MODELS dict so each Cloud Run instance
    # picks up flips within seconds instead of waiting for a redeploy.
    # Best-effort: if Redis is unavailable, providers still work using the
    # DB-on-write + env-on-restart fallback chain.
    model_registry_task = None
    try:
        from app.api.deps import get_redis
        from app.services.model_registry_pubsub import (
            model_registry_subscriber_loop,
            refresh_in_process_cache,
        )
        redis_client = await get_redis()
        if redis_client:
            await refresh_in_process_cache(redis_client)
            model_registry_task = asyncio.create_task(model_registry_subscriber_loop(redis_client))
            logger.info("[Background] Model registry pub/sub subscriber started")
    except Exception as e:
        logger.warning(f"[Background] Model registry subscriber failed to start: {e}")

    yield

    # Shutdown: cancel cleanup task and MCP servers
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    if model_registry_task:
        model_registry_task.cancel()
        try:
            await model_registry_task
        except asyncio.CancelledError:
            pass
    # MCP shutdown removed 2026-05-26 alongside MCP startup.
    logger.info("VidGo AI Backend shutting down...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set all CORS enabled origins
# On GCP Cloud Run, frontend/backend have dynamic URLs — use wildcard when CORS_ALLOW_ALL=True
if settings.CORS_ALLOW_ALL:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,  # Must be False when using wildcard origins (auth uses Bearer tokens, not cookies)
        allow_methods=["*"],
        allow_headers=["*"],
    )
elif settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount static files for generated images
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


_health_cache: dict = {"ready": False, "ts": 0.0}
_HEALTH_CACHE_TTL = 120  # re-check DB at most every 2 minutes


@app.get("/health")
async def health_check():
    """Health check endpoint — live DB check for materials_ready (cached 2 min)."""
    import time
    now = time.monotonic()
    if now - _health_cache["ts"] > _HEALTH_CACHE_TTL:
        try:
            from app.services.material_generator import get_material_generator
            from app.core.database import AsyncSessionLocal
            generator = get_material_generator()
            async with AsyncSessionLocal() as session:
                status = await asyncio.wait_for(
                    generator.check_all_materials(session), timeout=10
                )
            ready = all(v.get("ready", False) for v in status.values() if isinstance(v, dict))
            _health_cache["ready"] = ready
            _health_cache["ts"] = now
            app.state.materials_validated = ready
        except Exception as exc:
            logger.warning(f"Health check materials query failed: {exc}")
    return {
        "status": "ok",
        "mode": "preset-only",
        "materials_ready": _health_cache["ready"],
    }


@app.get("/materials/status")
async def materials_status():
    """Check status of showcase materials in database."""
    from app.services.material_generator import get_material_generator
    from app.core.database import AsyncSessionLocal

    generator = get_material_generator()
    async with AsyncSessionLocal() as session:
        status = await generator.check_all_materials(session)

    return {
        "status": "ok",
        "materials": status,
        "all_ready": all(
            v.get("ready", False) if isinstance(v, dict) else bool(v)
            for v in status.values()
        )
    }


@app.post("/materials/generate")
async def generate_materials(force: bool = False):
    """
    Manually trigger material generation.
    Use force=true to regenerate all materials.
    """
    from app.services.material_generator import check_and_generate_materials

    results = await check_and_generate_materials(force=force)

    return {
        "status": "ok",
        "results": results
    }
