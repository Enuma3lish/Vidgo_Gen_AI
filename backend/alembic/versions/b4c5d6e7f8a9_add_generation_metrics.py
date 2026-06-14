"""Add generation_metrics table for provider-router latency / success / model telemetry

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-05-14

Phase C.2 — the actual metrics pipeline. The previous migration
(a3b4c5d6e7f8) added metric columns to ``generations`` but tools.py writes
to ``user_generations``, so the columns never got populated. This table
sidesteps that mismatch: ProviderRouter.route() writes one row per provider
call, success or failure, capturing only what the router itself sees
(provider name, derived model_used, duration, ok/err). No FK to user
because router doesn't always know the caller; aggregation queries don't
need it for the per-model dashboard.

The previous migration's columns on ``generations`` stay (harmless, NULL
everywhere) — dropping them would require another migration that doesn't
buy anything until tools.py is refactored to write Generation rows.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = 'b4c5d6e7f8a9'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'generation_metrics',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('task_type', sa.String(length=64), nullable=False),
        sa.Column('provider_used', sa.String(length=32), nullable=False),
        sa.Column('model_used', sa.String(length=128), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, default=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('used_backup', sa.Boolean(), nullable=False, default=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Indexes power the admin dashboard's "last 7d per model" aggregation
    op.create_index('ix_gen_metrics_model_created', 'generation_metrics', ['model_used', 'created_at'])
    op.create_index('ix_gen_metrics_task_created', 'generation_metrics', ['task_type', 'created_at'])
    op.create_index('ix_gen_metrics_provider_created', 'generation_metrics', ['provider_used', 'created_at'])
    op.create_index('ix_gen_metrics_created', 'generation_metrics', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_gen_metrics_created', table_name='generation_metrics')
    op.drop_index('ix_gen_metrics_provider_created', table_name='generation_metrics')
    op.drop_index('ix_gen_metrics_task_created', table_name='generation_metrics')
    op.drop_index('ix_gen_metrics_model_created', table_name='generation_metrics')
    op.drop_table('generation_metrics')
