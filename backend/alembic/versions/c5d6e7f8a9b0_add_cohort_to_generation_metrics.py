"""Add cohort column to generation_metrics + index

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-05-14

A/B test data foundation. Populated by ProviderRouter when an experiment
is active for the task type; NULL otherwise. The experiment-management UI
(create / activate / compare) is a separate follow-up — this migration
ships only the column so metrics aggregation can group by cohort once
data flows in.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c5d6e7f8a9b0'
down_revision = 'b4c5d6e7f8a9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'generation_metrics',
        sa.Column('cohort', sa.String(length=32), nullable=True),
    )
    op.create_index('ix_gen_metrics_cohort_model_created', 'generation_metrics',
                    ['cohort', 'model_used', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_gen_metrics_cohort_model_created', table_name='generation_metrics')
    op.drop_column('generation_metrics', 'cohort')
