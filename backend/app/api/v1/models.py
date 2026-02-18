"""Model registry and notification endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.model_registry import get_model_registry, ModelInfo

router = APIRouter()


@router.get("/available")
async def get_available_models(
    tier: Optional[str] = Query(default=None, description="Filter by tier: free or paid"),
    provider: Optional[str] = Query(default=None, description="Filter by provider"),
    model_type: Optional[str] = Query(default=None, description="Filter by type: t2i, i2v, etc."),
):
    """Get list of available AI models."""
    registry = get_model_registry()

    if provider:
        models = registry.get_models_by_provider(provider)
    elif model_type:
        models = registry.get_models_by_type(model_type)
    elif tier:
        models = registry.get_models_for_tier(tier)
    else:
        models = registry.get_all_models()

    return {
        "models": [m.model_dump() for m in models],
        "total": len(models)
    }


@router.get("/new")
async def get_new_models(
    days: int = Query(default=7, ge=1, le=30),
):
    """Get recently announced models for homepage banner."""
    registry = get_model_registry()
    announcements = registry.get_new_models(days)
    return {
        "announcements": announcements,
        "count": len(announcements)
    }


class AnnounceModelRequest(BaseModel):
    model_id: str
    message: str = ""
    message_zh: str = ""


@router.post("/announce")
async def announce_new_model(
    request: AnnounceModelRequest,
    current_user: User = Depends(get_current_user)
):
    """Admin: Announce a new model (triggers homepage banner)."""
    if not current_user.is_superuser:
        raise HTTPException(403, "Admin access required")

    registry = get_model_registry()
    success = registry.announce_model(request.model_id, request.message, request.message_zh)

    if not success:
        raise HTTPException(404, f"Model '{request.model_id}' not found in registry")

    return {"success": True, "message": f"Model {request.model_id} announced"}
