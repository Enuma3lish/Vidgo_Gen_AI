"""PendingProviderTask — durable record of an in-flight upstream job.

Why this exists
---------------
Long-running upstream tasks (Kling Avatar / A2E / Veo / Kling Omni) can poll
for tens of minutes. The synchronous request path is fragile:
- Cloud Run can SIGTERM the container at the request-timeout boundary.
- Cold migrations between Cloud Run revisions kill in-flight asyncio loops.
- A worker OOM tears down every active poll without unwinding the stack.

In all three cases the upstream provider keeps rendering — they don't know
we hung up — but we lose the task_id and can never reclaim the result.
The user paid (credits already deducted) and got a 504 with no recovery
path.

PendingProviderTask is written **before** the poll loop starts, so even if
the foreground request dies the worker can re-poll the upstream by task_id
later, materialise the result into a `UserGeneration` row, and either
deliver the asset or refund the credits.

Lifecycle
---------
  status = "submitting"  → row inserted before route() is called
  status = "polling"     → on_submit() callback fired with task_id
  status = "completed"   → poll loop finished successfully; result_url filled
  status = "failed"      → upstream reported failure; reclaim refunded
  status = "abandoned"   → exceeded MAX_RECLAIM_AGE_HOURS; refund + give up
"""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


PENDING_TASK_STATUS_CHOICES = (
    "submitting",  # row created, route() not yet returned a task_id
    "polling",     # task_id captured, foreground polling in progress
    "completed",   # upstream completed; result captured
    "failed",      # upstream returned failure; refund issued
    "abandoned",   # reclaim job gave up after MAX_RECLAIM_AGE_HOURS
)


class PendingProviderTask(Base):
    __tablename__ = "pending_provider_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Tool / service classification — duplicates the values used by
    # `_check_and_deduct_credits(service_type=…)` so the reclaim job can
    # issue the right refund tag without re-deriving from tool_type.
    tool_type = Column(String(64), nullable=False, index=True)
    service_type = Column(String(64), nullable=False)

    # Provider identity — once known. May be NULL while status="submitting"
    # because we insert the row before the provider chain runs.
    provider_name = Column(String(32), nullable=True, index=True)
    provider_task_id = Column(String(200), nullable=True, index=True)

    # What the user paid up-front; the reclaim job refunds this on abandon.
    credits_charged = Column(Integer, nullable=False, default=0)

    # The original route() params (image_url, script, prompt, …) so the
    # reclaim job can rebuild the UserGeneration row on success.
    input_params = Column(JSONB, default={})

    # Lifecycle marker. See PENDING_TASK_STATUS_CHOICES above.
    status = Column(String(20), nullable=False, default="submitting", index=True)

    # Result URL (filled on success either by foreground poll or reclaim job).
    result_url = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)   # task_id captured
    completed_at = Column(DateTime(timezone=True), nullable=True)   # terminal status reached
    last_polled_at = Column(DateTime(timezone=True), nullable=True) # last reclaim-job touch

    __table_args__ = (
        # The reclaim worker scans WHERE status IN ('submitting','polling')
        # ORDER BY created_at. Composite index keeps that scan O(log N).
        Index("ix_pending_provider_tasks_status_created", "status", "created_at"),
    )
