"""Add model_registry_overrides + model_registry_audit + Generation metrics columns

Revision ID: a3b4c5d6e7f8
Revises: z1a2b3c4d5e6
Create Date: 2026-05-14

Phase B + C of the AI model management roadmap:

1. `model_registry_overrides` — admin-editable current model/version per
   service_key. ModelRegistryService reads this first; falls back to env vars
   then hardcoded defaults in model_registry.py. Lets ops swap to a newer
   PiAPI model alias (e.g. Kling 2.6 → 2.5 → 2.1-master) without redeploy.

2. `model_registry_audit` — full change history (before/after/who/when/why)
   so we can prove who flipped Kling Avatar to a broken version at 03:00.

3. Adds metrics columns to `generations`:
     - provider_used VARCHAR(32)       — 'piapi' / 'pollo' / 'vertex_ai' / 'a2e'
     - model_used VARCHAR(128)         — actual model string sent to provider
     - duration_ms INTEGER             — end-to-end latency
     - api_cost_usd NUMERIC(10, 4)     — provider cost for this call

These columns power the per-model success-rate / latency / cost dashboard
on the admin model registry page.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = 'a3b4c5d6e7f8'
down_revision = 'z1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── model_registry_overrides ────────────────────────────────────────
    op.create_table(
        'model_registry_overrides',
        sa.Column('service_key', sa.String(length=64), primary_key=True),
        sa.Column('current_model', sa.String(length=128), nullable=False),
        sa.Column('current_version', sa.String(length=64), nullable=True),
        sa.Column('updated_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
    )

    # ─── model_registry_audit ────────────────────────────────────────────
    op.create_table(
        'model_registry_audit',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('service_key', sa.String(length=64), nullable=False, index=True),
        sa.Column('before_model', sa.String(length=128), nullable=True),
        sa.Column('before_version', sa.String(length=64), nullable=True),
        sa.Column('after_model', sa.String(length=128), nullable=False),
        sa.Column('after_version', sa.String(length=64), nullable=True),
        sa.Column('changed_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column('reason', sa.Text(), nullable=True),
    )

    # ─── Generation metrics columns ──────────────────────────────────────
    op.add_column('generations', sa.Column('provider_used', sa.String(length=32), nullable=True))
    op.add_column('generations', sa.Column('model_used', sa.String(length=128), nullable=True))
    op.add_column('generations', sa.Column('duration_ms', sa.Integer(), nullable=True))
    op.add_column('generations', sa.Column('api_cost_usd', sa.Numeric(10, 4), nullable=True))
    op.create_index('ix_generations_provider_model', 'generations', ['provider_used', 'model_used'])
    op.create_index('ix_generations_model_used_created', 'generations', ['model_used', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_generations_model_used_created', table_name='generations')
    op.drop_index('ix_generations_provider_model', table_name='generations')
    op.drop_column('generations', 'api_cost_usd')
    op.drop_column('generations', 'duration_ms')
    op.drop_column('generations', 'model_used')
    op.drop_column('generations', 'provider_used')
    op.drop_table('model_registry_audit')
    op.drop_table('model_registry_overrides')
