"""SQLAlchemy models for the admin-editable model registry + audit log
and the provider-router metrics sink.

Companion to ``app/core/model_registry.py`` (the in-process registry) and
``app/services/model_registry_service.py`` (the DB-first resolver).
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.core.database import Base


class ModelRegistryOverride(Base):
    """Current admin-set model/version for a service_key.

    One row per service_key (e.g. 'kling_video', 'flux_t2i'). When present,
    ModelRegistryService prefers this over env vars and hardcoded defaults.
    Admins edit via /admin/models.
    """
    __tablename__ = "model_registry_overrides"

    service_key = Column(String(64), primary_key=True)
    current_model = Column(String(128), nullable=False)
    current_version = Column(String(64), nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notes = Column(Text, nullable=True)


class ModelRegistryAudit(Base):
    """Append-only history of every change made via the admin UI.

    Captures before/after model + version, who, when, and an optional reason
    string so we can answer 'who flipped Kling Avatar to a broken version at
    03:00' without trawling git history.
    """
    __tablename__ = "model_registry_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_key = Column(String(64), nullable=False, index=True)
    before_model = Column(String(128), nullable=True)
    before_version = Column(String(64), nullable=True)
    after_model = Column(String(128), nullable=False)
    after_version = Column(String(64), nullable=True)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    reason = Column(Text, nullable=True)


class GenerationMetric(Base):
    """One row per provider call from ProviderRouter.route().

    Lightweight metrics sink that doesn't depend on tools.py creating a row
    in ``generations`` or ``user_generations``. Captures only what the
    router can observe by itself: which provider answered, derived
    model_used string, elapsed time, success/error, and whether the
    primary failed and a backup served the request.

    Aggregated by /api/v1/admin/models/{service_key}/metrics for the
    admin model registry dashboard.
    """
    __tablename__ = "generation_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(String(64), nullable=False)        # 'image_to_video', 'midjourney_imagine', ...
    provider_used = Column(String(32), nullable=False)    # 'piapi' / 'pollo' / 'vertex_ai' / 'a2e'
    model_used = Column(String(128), nullable=True)       # 'kling-2.6' / 'midjourney' / 'luma-ray-v2' / ...
    duration_ms = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    used_backup = Column(Boolean, nullable=False, default=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
