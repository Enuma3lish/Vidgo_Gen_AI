"""Add pending_provider_tasks for orphaned upstream task reclaim.

Revision ID: i3c4d5e6f7g8
Revises: h2b3c4d5e6f7
Create Date: 2026-06-03

Backs the PendingProviderTask model. See app/models/pending_provider_task.py
for the full motivation — TL;DR: long-poll endpoints (avatar, video,
veo3, kling omni) can be killed by Cloud Run mid-poll, orphaning the
upstream provider task. This table durably stores task_id + payload so
a worker can reclaim the result later.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "i3c4d5e6f7g8"
down_revision: Union[str, None] = "h2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pending_provider_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("tool_type", sa.String(length=64), nullable=False),
        sa.Column("service_type", sa.String(length=64), nullable=False),
        sa.Column("provider_name", sa.String(length=32), nullable=True),
        sa.Column("provider_task_id", sa.String(length=200), nullable=True),
        sa.Column("credits_charged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_params", postgresql.JSONB(astext_type=sa.Text()), server_default="{}"),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="submitting",
        ),
        sa.Column("result_url", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_pending_provider_tasks_user_id",
        "pending_provider_tasks", ["user_id"],
    )
    op.create_index(
        "ix_pending_provider_tasks_tool_type",
        "pending_provider_tasks", ["tool_type"],
    )
    op.create_index(
        "ix_pending_provider_tasks_provider_name",
        "pending_provider_tasks", ["provider_name"],
    )
    op.create_index(
        "ix_pending_provider_tasks_provider_task_id",
        "pending_provider_tasks", ["provider_task_id"],
    )
    op.create_index(
        "ix_pending_provider_tasks_status",
        "pending_provider_tasks", ["status"],
    )
    op.create_index(
        "ix_pending_provider_tasks_created_at",
        "pending_provider_tasks", ["created_at"],
    )
    # The reclaim worker scans WHERE status IN ('submitting','polling')
    # ORDER BY created_at. Composite index makes that scan cheap.
    op.create_index(
        "ix_pending_provider_tasks_status_created",
        "pending_provider_tasks", ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pending_provider_tasks_status_created", table_name="pending_provider_tasks")
    op.drop_index("ix_pending_provider_tasks_created_at", table_name="pending_provider_tasks")
    op.drop_index("ix_pending_provider_tasks_status", table_name="pending_provider_tasks")
    op.drop_index("ix_pending_provider_tasks_provider_task_id", table_name="pending_provider_tasks")
    op.drop_index("ix_pending_provider_tasks_provider_name", table_name="pending_provider_tasks")
    op.drop_index("ix_pending_provider_tasks_tool_type", table_name="pending_provider_tasks")
    op.drop_index("ix_pending_provider_tasks_user_id", table_name="pending_provider_tasks")
    op.drop_table("pending_provider_tasks")
