"""Add effect to tooltype enum

Revision ID: e1f2a3b4c5d6
Revises: r1s2t3u4v5w6
Create Date: 2026-02-21

The Python ToolType enum has EFFECT = 'effect', but the PostgreSQL tooltype enum
was never updated to include it. This causes InvalidTextRepresentationError
when seed_materials_if_empty or any query filters by tool_type = 'effect'.
"""
from alembic import op

revision = 'e1f2a3b4c5d6'
down_revision = 'r1s2t3u4v5w6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE tooltype ADD VALUE IF NOT EXISTS 'effect'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values
    pass
