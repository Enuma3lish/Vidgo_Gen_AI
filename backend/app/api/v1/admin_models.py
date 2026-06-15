"""Admin endpoints for the AI model registry.

GET    /api/v1/admin/models                       — list every service_key with effective state + override row + default
GET    /api/v1/admin/models/{service_key}         — single key view
PUT    /api/v1/admin/models/{service_key}         — upsert override + audit row
GET    /api/v1/admin/models/{service_key}/audit   — full change history
GET    /api/v1/admin/models/{service_key}/metrics — success rate / latency / cost from `generations`

PiAPI vendor model bumps (Kling 2.6 → 2.5 etc.) flow through here so ops can
swap models in seconds without a redeploy. See ``ModelRegistryService`` for
the DB → env → hardcoded fallback chain.

Propagation — admin edits publish a Redis pub/sub invalidate (``set_override`` →
``publish_invalidate``) and every instance refreshes its in-process model cache
within one pub/sub cycle (subscriber started in the FastAPI lifespan; see
``model_registry_pubsub.py``). This path is **Redis-gated** (``if not redis_client:
return``): it is active wherever Redis is reachable, e.g. local dev. PROD removed
Memorystore Redis in the 2026-06 cost pass, so there pub/sub is inactive and edits
propagate on instance restart — force a ~30s rolling restart with
`gcloud run services update --update-env-vars MODEL_REGISTRY_RESEED=$(date +%s)`.

SCOPE — what this registry DOES and does NOT do (read before writing tests):
  ✅ Supported: per-``service_key`` override of the MODEL STRING + version
     (``current_model`` / ``current_version``), with audit history. This is the
     "hot model-string override" capability.
  ❌ NOT supported (roadmap): admin enable/disable of a provider, or reordering
     provider PRIORITY (e.g. promoting Pollo from Backup → Primary). The
     ``ROUTING_CONFIG`` in ``provider_router`` is static; ``_route_candidates``
     only skips a provider on a missing API key or an open circuit breaker —
     there is no admin-controllable ``enabled``/``priority`` field on
     ``ModelRegistryOverride``. Acceptance tests must NOT assert these; verify
     the model-string override instead. Building enable/disable + priority is a
     deliberate follow-up (new columns + provider_router DB-merge + propagation).
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.models.billing import ServicePricing
from app.models.model_registry import GenerationMetric
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
    """Phase C: aggregate success rate / avg latency from generation_metrics.

    Groups by model_used so admins can compare "Kling 2.6 vs 2.5 vs 2.1-master"
    side-by-side. The ``service_key`` URL param is informational only —
    metrics are keyed by ``model_used`` strings produced by ProviderRouter's
    derivation, which don't map 1:1 to registry service_keys.

    Cost is computed at query time as call_count × api_cost_usd if we can
    resolve a matching ServicePricing row for the derived model; otherwise
    falls back to 0.0 (TODO: improve once provider_router exposes per-call
    cost from PiAPI/Pollo responses).
    """
    since = datetime.now(timezone.utc) - timedelta(days=window_days)

    base = (
        select(
            GenerationMetric.model_used,
            GenerationMetric.task_type,
            func.count().label("total_calls"),
            func.sum(
                func.case((GenerationMetric.success.is_(True), 1), else_=0)
            ).label("success_count"),
            func.avg(GenerationMetric.duration_ms).label("avg_duration_ms"),
        )
        .where(GenerationMetric.created_at >= since)
        .where(GenerationMetric.model_used.isnot(None))
        .group_by(GenerationMetric.model_used, GenerationMetric.task_type)
    )
    result = await db.execute(base)
    rows = result.all()

    # Approximate cost per call = ServicePricing.api_cost_usd of the row whose
    # tool_type matches our task_type. Imperfect (one task_type can map to
    # multiple service_types with different costs — e.g. kling-2.6 vs
    # kling-2.1-master both have task_type="kling_video_generation") but it's
    # the best estimate we have without the provider returning per-call cost.
    task_types = {r[1] for r in rows if r[1]}
    cost_map = {}
    if task_types:
        cost_q = await db.execute(
            select(ServicePricing.tool_type, func.avg(ServicePricing.api_cost_usd))
            .where(ServicePricing.tool_type.in_(task_types))
            .group_by(ServicePricing.tool_type)
        )
        cost_map = {t: float(c or 0) for t, c in cost_q.all()}

    # Collapse model_used groups across task_types in case the same model
    # served multiple task_types in the window (rare but possible).
    aggregated: Dict[str, Dict[str, Any]] = {}
    for model_used, task_type, total_calls, success, avg_ms in rows:
        total = int(total_calls or 0)
        succ = int(success or 0)
        cost = cost_map.get(task_type, 0.0) * total
        entry = aggregated.setdefault(model_used, {
            "total": 0, "success": 0, "duration_ms_sum": 0, "duration_ms_count": 0, "cost": 0.0
        })
        entry["total"] += total
        entry["success"] += succ
        if avg_ms is not None:
            entry["duration_ms_sum"] += float(avg_ms) * total
            entry["duration_ms_count"] += total
        entry["cost"] += cost

    metrics_by_model: List[ModelMetrics] = []
    for model_used, agg in aggregated.items():
        total = agg["total"]
        avg_ms = (agg["duration_ms_sum"] / agg["duration_ms_count"]) if agg["duration_ms_count"] else None
        metrics_by_model.append(
            ModelMetrics(
                model_used=model_used,
                window_days=window_days,
                total_calls=total,
                success_count=agg["success"],
                failure_count=max(0, total - agg["success"]),
                success_rate=(agg["success"] / total) if total > 0 else 0.0,
                avg_duration_ms=int(avg_ms) if avg_ms is not None else None,
                p95_duration_ms=None,
                total_cost_usd=round(agg["cost"], 4),
            )
        )

    return ModelMetricsResponse(
        service_key=service_key,
        window_days=window_days,
        metrics_by_model=metrics_by_model,
    )
