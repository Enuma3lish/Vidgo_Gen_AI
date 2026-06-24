"""Add client_task_id to user_generations and pending_provider_tasks (P0-2)

Revision ID: c1ta2sk3id45
Revises: b1c2d3e4f5a6, d4e5f6a7b8c9
Create Date: 2026-06-23

Single source of truth for task state via a client-minted correlation id.
The frontend generates a UUID per generation and sends it as the
``X-Client-Task-Id`` header. The tool endpoints stamp it onto the
``pending_provider_tasks`` row (in-flight) and the ``user_generations`` row
(on success); the reclaim worker copies it through when it materialises a
killed job. A new ``GET /api/v1/user/tasks/{client_task_id}`` endpoint then
lets the client poll for live status / recover a result whose synchronous
request timed out client-side or whose page was refreshed mid-generation —
so a backend success can never surface as a UI error.

This also MERGES the two outstanding heads (b1c2d3e4f5a6 watermark/invoice
merge, d4e5f6a7b8c9 subscription billing cycle) into one.

Idempotent ADD COLUMN IF NOT EXISTS + CREATE INDEX IF NOT EXISTS so it is
safe to replay (prod alembic history has multiple heads and is applied
manually).
"""
from alembic import op
import sqlalchemy as sa


revision = "c1ta2sk3id45"
down_revision = ("b1c2d3e4f5a6", "d4e5f6a7b8c9")
branch_labels = None
depends_on = None


_TABLES = ("user_generations", "pending_provider_tasks")


def upgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES:
        existing = {
            row[0] for row in bind.exec_driver_sql(
                f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'"
            ).fetchall()
        }
        if "client_task_id" not in existing:
            op.add_column(table, sa.Column("client_task_id", sa.String(length=64), nullable=True))
        # Indexed: the status endpoint looks up by (user_id, client_task_id).
        bind.exec_driver_sql(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_client_task_id "
            f"ON {table} (client_task_id)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES:
        bind.exec_driver_sql(f"DROP INDEX IF EXISTS ix_{table}_client_task_id")
        existing = {
            row[0] for row in bind.exec_driver_sql(
                f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'"
            ).fetchall()
        }
        if "client_task_id" in existing:
            op.drop_column(table, "client_task_id")
