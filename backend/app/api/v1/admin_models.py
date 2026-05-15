"""Admin endpoints for the AI model registry.

GET    /api/v1/admin/models                       — list every service_key with effective state + override row + default
GET    /api/v1/admin/models/{service_key}         — single key view
PUT    /api/v1/admin/models/{service_key}         — upsert override + audit row
GET    /api/v1/admin/models/{service_key}/audit   — full change history
GET    /api/v1/admin/models/{service_key}/metrics — success rate / latency / cost from `generations`

PiAPI vendor model bumps (Kling 2.6 → 2.5 etc.) flow through here so ops can
swap models in seconds without a redeploy. See ``ModelRegistryService`` for
the DB → env → hardcoded fallback chain.

Caveat — until a follow-up ships in-process cache refresh + pub/sub, admin
edits propagate to running provider code only after the Cloud Run instance
restarts. A `gcloud run services update --update-env-vars MODEL_REGISTRY_RESEED=$(date +%s)`
forces a rolling restart in ~30 seconds.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.models.billing import Generation
from app.models.user import User
from app.services.model_registry_service import ModelRegistryService


router = APIRouter()


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Reuse admin.py's pattern — superuser only."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ─── Pydantic schemas ────────────────────────────────────────────────────


class ModelEffective(BaseModel):
    model: str
    version: Optional[str] = None
    source: str  # 'db' | 'env' | 'default' | 'missing'


class ModelOverrideRow(BaseModel):
    model: str
    version: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: Optional[str] = None
    notes: Optional[str] = None


class ModelDefault(BaseModel):
    model: str
    version: Optional[str] = None


class ModelEntry(BaseModel):
    service_key: str
    effective: ModelEffective
    override: Optional[ModelOverrideRow] = None
    default: ModelDefault
    env_var: Optional[str] = None


class ModelListResponse(BaseModel):
    entries: List[ModelEntry]


class ModelOverrideUpdate(BaseModel):
    model: str = Field(..., min_length=1, max_length=128)
    version: Optional[str] = Field(default=None, max_length=64)
    reason: Optional[str] = Field(default=None, max_length=1000)


class AuditEntry(BaseModel):
    id: str
    service_key: str
    before_model: Optional[str]
    before_version: Optional[str]
    after_model: str
    after_version: Optional[str]
    changed_by: Optional[str]
    changed_at: str
    reason: Optional[str]


class AuditListResponse(BaseModel):
    entries: List[AuditEntry]


class ModelMetrics(BaseModel):
    """Aggregated metrics for a model_used string over a time window."""
    model_used: str
    window_days: int
    total_calls: int
    success_count: int
    failure_count: int
    success_rate: float            # 0.0–1.0
    avg_duration_ms: Optional[int] = None
    p95_duration_ms: Optional[int] = None
    total_cost_usd: float


class ModelMetricsResponse(BaseModel):
    service_key: str
    window_days: int
    metrics_by_model: List[ModelMetrics]


# ─── Endpoints ──────────────────────────────────────────────────────────


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List every known service_key with effective + override + default."""
    redis_client = await get_redis()
    svc = ModelRegistryService(db, redis_client)
    raw = await svc.list_all()
    entries = [
        ModelEntry(service_key=key, **info)
        for key, info in raw.items()
    ]
    return ModelListResponse(entries=entries)


@router.get("/models/{service_key}", response_model=ModelEntry)
async def get_model(
    service_key: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    redis_client = await get_redis()
    svc = ModelRegistryService(db, redis_client)
    raw = await svc.list_all()
    if service_key not in raw:
        raise HTTPException(status_code=404, detail=f"Unknown service_key: {service_key}")
    return ModelEntry(service_key=service_key, **raw[service_key])


@router.put("/models/{service_key}", response_model=ModelEntry)
async def update_model(
    service_key: str,
    payload: ModelOverrideUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Upsert override + write audit row.

    Returns the refreshed ModelEntry so the admin UI can render the new
    effective state without a follow-up GET.
    """
    redis_client = await get_redis()
    svc = ModelRegistryService(db, redis_client)
    await svc.set_override(
        service_key=service_key,
        model=payload.model,
        version=payload.version,
        changed_by=str(admin.id),
        reason=payload.reason,
    )
    raw = await svc.list_all()
    if service_key not in raw:
        # set_override succeeded so the entry should now be in list_all; this
        # branch is a defensive guard against an unknown key the service
        # didn't reject earlier.
        raise HTTPException(status_code=500, detail="Override saved but lookup failed")
    return ModelEntry(service_key=service_key, **raw[service_key])


@router.get("/models/{service_key}/audit", response_model=AuditListResponse)
async def get_audit(
    service_key: str,
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    redis_client = await get_redis()
    svc = ModelRegistryService(db, redis_client)
    rows = await svc.get_audit(service_key, limit=limit)
    entries = [
        AuditEntry(
            id=str(row.id),
            service_key=row.service_key,
            before_model=row.before_model,
            before_version=row.before_version,
            after_model=row.after_model,
            after_version=row.after_version,
            changed_by=str(row.changed_by) if row.changed_by else None,
            changed_at=row.changed_at.isoformat() if row.changed_at else "",
            reason=row.reason,
        )
        for row in rows
    ]
    return AuditListResponse(entries=entries)


@router.get("/models/{service_key}/metrics", response_model=ModelMetricsResponse)
async def get_model_metrics(
    service_key: str,
    window_days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Phase C: aggregate success rate / avg latency / cost from generations.

    Groups by model_used so admins can compare "Kling 2.6 vs 2.5 vs 2.1-master"
    side-by-side. service_key is used here as a label / filter hint via the
    Generation.service_type column when populated; otherwise the dashboard
    just shows all model_used values that produced traffic in the window.
    """
    since = datetime.now(timezone.utc) - timedelta(days=window_days)

    # Aggregate per model_used. We don't filter by service_key in the SQL
    # because Generation.service_type uses the credit-cost service slug
    # (image_generation_premium, video_flagship, ...) while service_key is
    # the registry slug (kling_video, flux_t2i, ...). The admin UI groups by
    # model_used regardless. Caller can pass service_key="all" to see global.
    base = (
        select(
            Generation.model_used,
            func.count().label("total_calls"),
            func.sum(
                func.case((Generation.status == "completed", 1), else_=0)
            ).label("success_count"),
            func.avg(Generation.duration_ms).label("avg_duration_ms"),
            func.sum(Generation.api_cost_usd).label("total_cost_usd"),
        )
        .where(Generation.created_at >= since)
        .where(Generation.model_used.isnot(None))
        .group_by(Generation.model_used)
    )
    result = await db.execute(base)

    metrics_by_model: List[ModelMetrics] = []
    for row in result.all():
        model_used = row[0]
        total = int(row[1] or 0)
        success = int(row[2] or 0)
        avg_ms = row[3]
        cost = row[4] or 0
        metrics_by_model.append(
            ModelMetrics(
                model_used=model_used,
                window_days=window_days,
                total_calls=total,
                success_count=success,
                failure_count=max(0, total - success),
                success_rate=(success / total) if total > 0 else 0.0,
                avg_duration_ms=int(avg_ms) if avg_ms is not None else None,
                p95_duration_ms=None,  # populate from a separate percentile_cont call when needed
                total_cost_usd=float(cost),
            )
        )

    return ModelMetricsResponse(
        service_key=service_key,
        window_days=window_days,
        metrics_by_model=metrics_by_model,
    )
