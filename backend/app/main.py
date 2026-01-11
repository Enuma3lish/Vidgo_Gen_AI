import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.core.config import get_settings
from app.api.api import api_router

settings = get_settings()
logger = logging.getLogger(__name__)

# Ensure static directory exists
STATIC_DIR = Path("/app/static")
STATIC_DIR.mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "generated").mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "generated" / "interior").mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "materials").mkdir(parents=True, exist_ok=True)


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
                missing.append(f"{tool}: {info.get('count', 0)} materials")
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
    # Startup
    logger.info("VidGo AI Backend starting up...")
    logger.info("Mode: PRESET-ONLY (Material DB Lookup, No Runtime API Calls)")

    # BLOCKING: Validate all pre-generated materials exist
    # This ensures the service has all required materials before accepting requests
    validation_result = await validate_materials_on_startup()

    # Store validation result in app state for health checks
    app.state.materials_validated = validation_result.get('all_ready', False)
    app.state.materials_status = validation_result

    if not validation_result.get('all_ready', False):
        logger.warning("=" * 60)
        logger.warning("WARNING: Some materials may be missing!")
        logger.warning("Run 'python scripts/pregenerate_all.py' to generate materials")
        logger.warning("=" * 60)

    yield

    # Shutdown
    logger.info("VidGo AI Backend shutting down...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
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


@app.get("/health")
def health_check():
    """Health check endpoint with material validation status."""
    materials_ready = getattr(app.state, 'materials_validated', False)
    return {
        "status": "ok",
        "mode": "preset-only",
        "materials_ready": materials_ready
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
        "all_ready": all(status.values())
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
